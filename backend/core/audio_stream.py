"""
audio_stream.py — Gestionnaire du flux d'acquisition micro (PyAudio).

Singleton diffusant les chunks audio 16 kHz int16 à tous les abonnés
(boucle VAD, enregistrement biométrique…). Extrait de main2.py.
"""

import os
import time
import threading

import numpy as np

# --- PyAudio (micro/reconnaissance vocale) : optionnel ---
try:
    import pyaudio
except ImportError:
    pyaudio = None
    print("[AVERTISSEMENT] pyaudio non installe — le micro sera desactive.")
    print("  -> Pour l'installer : pip install pipwin && pipwin install pyaudio")

def _filtre_anticrenelage():
    """Passe-bas (FIR, coupure 7 kHz) appliqué AVANT de ramener le flux de 48 kHz à 16 kHz.

    Garder un échantillon sur trois sans filtrer (ancien `[::3]`) repliait tout ce qui dépasse
    8 kHz (sifflantes « s »/« ch », souffle, bruit) dans la bande de la voix : le spectre
    changeait d'une phrase à l'autre et l'empreinte vocale avec (0,57 à 0,66 en usage réel
    contre 0,77 à 0,89 entre échantillons d'enrôlement). None si scipy est absent."""
    try:
        from scipy.signal import firwin
        return firwin(121, 7000, fs=48000)
    except Exception as e:
        print(f"[AudioStreamManager] Filtre anti-repliement indisponible ({e}) : décimation brute.")
        return None


class AudioStreamManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(AudioStreamManager, cls).__new__(cls, *args, **kwargs)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.subscribers = []
        self.subscribers_lock = threading.Lock()
        self.p = None
        self.stream = None
        self.running = False
        self.thread = None
        self.mic_index = None
        
        self.format = pyaudio.paInt16 if pyaudio else None
        self.channels = 1
        self.rate = 16000
        self.chunk = 1024
        
        # Paramètres d'échantillonnage adaptatif
        self.active_rate = 16000
        self.downsample_factor = 1
        self.software_gain = 1.0

    def _load_gain(self):
        self.software_gain = 1.0
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "jarvis_config.json")  # backend/core/ -> racine projet
            if os.path.exists(config_path):
                import json
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.software_gain = float(cfg.get("mic_software_gain", 1.0))
                # print(f"[AudioStreamManager] Gain logiciel chargé : {self.software_gain}x")
        except Exception as e:
            # print(f"[AudioStreamManager] Erreur lecture gain : {e}")
            pass

    def subscribe(self):
        import queue
        q = queue.Queue()
        with self.subscribers_lock:
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q):
        with self.subscribers_lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def start(self, mic_index=None):
        with self._lock:
            if self.running:
                if self.mic_index != mic_index:
                    print(f"[AudioStreamManager] Micro change : {self.mic_index} -> {mic_index}. Rechargement...")
                    self._stop_unlocked()
                else:
                    return
            
            if not pyaudio:
                print("[AudioStreamManager] PyAudio non disponible.")
                return

            self._load_gain()
            self.mic_index = mic_index
            self.p = pyaudio.PyAudio()
            
            # Essayer d'ouvrir à 48000 Hz pour contourner les bugs de rééchantillonnage matériel (BIRD UM1)
            try:
                self.stream = self.p.open(
                    format=self.format,
                    channels=self.channels,
                    rate=48000,
                    input=True,
                    frames_per_buffer=self.chunk * 3,
                    input_device_index=self.mic_index
                )
                self.active_rate = 48000
                self.downsample_factor = 3
                self.running = True
                self.thread = threading.Thread(target=self._run, daemon=True)
                self.thread.start()
                # print(f"[AudioStreamManager] Flux d'acquisition démarré à 48000 Hz (avec décimation par 3) sur Micro Index: {self.mic_index}")
            except Exception as e:
                # Mode repli à 16000 Hz si 48000 Hz échoue
                try:
                    self.stream = self.p.open(
                        format=self.format,
                        channels=self.channels,
                        rate=16000,
                        input=True,
                        frames_per_buffer=self.chunk,
                        input_device_index=self.mic_index
                    )
                    self.active_rate = 16000
                    self.downsample_factor = 1
                    self.running = True
                    self.thread = threading.Thread(target=self._run, daemon=True)
                    self.thread.start()
                    # print(f"[AudioStreamManager] Flux d'acquisition démarré à 16000 Hz de repli sur Micro Index: {self.mic_index}")
                except Exception as e_fallback:
                    # print(f"[AudioStreamManager] Erreur d'ouverture du flux (48k et 16k) : {e_fallback}")
                    pass
                    self.running = False

    def stop(self):
        with self._lock:
            self._stop_unlocked()

    def _stop_unlocked(self):
        self.running = False
        # On ATTEND la fin réelle du thread de lecture avant de rouvrir un flux.
        # Auparavant la référence était simplement mise à None : l'ancien thread,
        # bloqué dans stream.read(), reprenait la main après qu'un nouveau flux
        # ait été démarré (running déjà repassé à True) et l'on se retrouvait avec
        # DEUX threads lisant le même périphérique — chunks entrelacés, donc VAD
        # et wakeword alimentés avec de l'audio corrompu jusqu'au redémarrage.
        ancien = self.thread
        self.thread = None
        if ancien is not None and ancien.is_alive() and ancien is not threading.current_thread():
            ancien.join(timeout=2.0)
            if ancien.is_alive():
                print("[AudioStreamManager] ⚠ Le thread de capture ne s'est pas arrêté dans les temps.")
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                print(f"[AudioStreamManager] Erreur lors de la fermeture du flux : {e}")
            self.stream = None
        if self.p:
            try:
                self.p.terminate()
            except Exception as e:
                print(f"[AudioStreamManager] Erreur lors de la fermeture de PyAudio : {e}")
            self.p = None

    def reload(self, mic_index):
        with self._lock:
            print(f"[AudioStreamManager] Rechargement demandé avec micro index : {mic_index}")
            self._stop_unlocked()
            if not pyaudio:
                return
            
            self._load_gain()
            self.mic_index = mic_index
            self.p = pyaudio.PyAudio()
            
            # Essayer d'ouvrir à 48000 Hz
            try:
                self.stream = self.p.open(
                    format=self.format,
                    channels=self.channels,
                    rate=48000,
                    input=True,
                    frames_per_buffer=self.chunk * 3,
                    input_device_index=self.mic_index
                )
                self.active_rate = 48000
                self.downsample_factor = 3
                self.running = True
                self.thread = threading.Thread(target=self._run, daemon=True)
                self.thread.start()
                print(f"[AudioStreamManager] Flux d'acquisition redémarré à 48000 Hz (avec décimation par 3) sur Micro Index: {self.mic_index}")
            except Exception as e:
                # Repli à 16000 Hz
                try:
                    self.stream = self.p.open(
                        format=self.format,
                        channels=self.channels,
                        rate=16000,
                        input=True,
                        frames_per_buffer=self.chunk,
                        input_device_index=self.mic_index
                    )
                    self.active_rate = 16000
                    self.downsample_factor = 1
                    self.running = True
                    self.thread = threading.Thread(target=self._run, daemon=True)
                    self.thread.start()
                    print(f"[AudioStreamManager] Flux d'acquisition redémarré à 16000 Hz de repli sur Micro Index: {self.mic_index}")
                except Exception as e_fallback:
                    print(f"[AudioStreamManager] Erreur de réouverture du flux (48k et 16k) : {e_fallback}")
                    self.running = False

    def _run(self):
        # Filtre et son état propres à ce flux (réinitialisés à chaque (re)démarrage du thread)
        fir = _filtre_anticrenelage() if self.downsample_factor == 3 else None
        etat_fir = np.zeros(len(fir) - 1) if fir is not None else None
        if fir is not None:
            from scipy.signal import lfilter
        while self.running:
            try:
                if not self.stream or not self.running:
                    time.sleep(0.01)
                    continue

                if self.downsample_factor == 3:
                    data = self.stream.read(self.chunk * 3, exception_on_overflow=False)
                    if not data:
                        continue

                    # Gain logiciel, filtre passe-bas puis 1 échantillon sur 3. L'écrêtage se fait
                    # après filtrage (avant, le gain écrêté avant filtre ajoutait de la distorsion).
                    audio_float = np.frombuffer(data, dtype=np.int16).astype(np.float32) * self.software_gain
                    if fir is not None:
                        audio_float, etat_fir = lfilter(fir, 1.0, audio_float, zi=etat_fir)
                    downsampled = np.clip(audio_float[::3], -32768, 32767).astype(np.int16)
                    data_to_send = downsampled.tobytes()
                else:
                    data = self.stream.read(self.chunk, exception_on_overflow=False)
                    if not data:
                        continue
                    
                    # Appliquer le gain logiciel si nécessaire
                    if self.software_gain != 1.0:
                        audio_chunk = np.frombuffer(data, dtype=np.int16)
                        audio_float = audio_chunk.astype(np.float32) * self.software_gain
                        data_to_send = np.clip(audio_float, -32768, 32767).astype(np.int16).tobytes()
                    else:
                        data_to_send = data
                    
                with self.subscribers_lock:
                    for q in self.subscribers:
                        q.put(data_to_send)
                _echecs = 0
            except Exception as e:
                # Un flux définitivement mort produisait une boucle silencieuse à
                # 100 Hz. On signale (une fois, puis rarement) au lieu de tourner
                # à vide sans aucun diagnostic.
                _echecs = locals().get("_echecs", 0) + 1
                if _echecs in (1, 50) or _echecs % 500 == 0:
                    print(f"[AudioStreamManager] Erreur de lecture ({_echecs}x) : {e}")
                time.sleep(0.01)
