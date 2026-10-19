import os
import urllib.request
import numpy as np

# Ajout manuel des répertoires DLL pour Windows (CUDA + cuDNN)
if os.name == 'nt':
    cuda_bin = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\bin"
    cudnn_bin = r"C:\Program Files\NVIDIA\CUDNN\v9.23\bin\12.9\x64"
    if os.path.exists(cuda_bin):
        try: os.add_dll_directory(cuda_bin)
        except: pass
        os.environ["PATH"] = cuda_bin + os.pathsep + os.environ["PATH"]
    if os.path.exists(cudnn_bin):
        try: os.add_dll_directory(cudnn_bin)
        except: pass
        os.environ["PATH"] = cudnn_bin + os.pathsep + os.environ["PATH"]

import onnxruntime as ort
import sherpa_onnx

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CORE_DIR = os.path.join(_BASE_DIR, "core")

VAD_MODEL_PATH = os.path.join(_CORE_DIR, "silero_vad.onnx")
# CAM++ (3D-Speaker, 200k locuteurs zh/en), ~30 ms par phrase. WeSpeaker ResNet293-LM, meilleur
# sur le papier (VoxCeleb1-O), a été écarté : sur de vraies voix il ne séparait pas les locuteurs
# (personnes différentes jusqu'à 0,85, même personne dès 0,75 ; CAM++ : 0,46 contre 0,65).
# Changer de modèle rend les empreintes incomparables : elles sont recalculées depuis l'audio
# d'enrôlement conservé (sample_N.wav), cf. SpeakerBiometrics._adapter_au_modele.
SPEAKER_MODEL_NOM = "3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx"
SPEAKER_MODEL_URL = "https://huggingface.co/csukuangfj/speaker-embedding-models/resolve/main/" + SPEAKER_MODEL_NOM
SPEAKER_MODEL_PATH = os.path.join(_CORE_DIR, SPEAKER_MODEL_NOM)
VOICEPRINTS_DIR = os.path.join(_CORE_DIR, "voiceprints")

def _telecharger_atomique(url, destination, timeout=60, taille_min=10_000):
    """Télécharge vers un .part puis renomme, avec délai et contrôle de taille.

    urllib.request.urlretrieve() écrivait directement dans le fichier final et
    sans timeout : une coupure à mi-parcours laissait un modèle .onnx tronqué.
    Comme la garde d'installation ne teste que os.path.exists(), le fichier
    corrompu était conservé indéfiniment et onnxruntime plantait à chaque
    démarrage suivant. Une connexion qui ne répond jamais bloquait par ailleurs
    tout le démarrage.
    """
    import socket
    partiel = destination + ".part"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as reponse, open(partiel, "wb") as sortie:
            while True:
                bloc = reponse.read(65536)
                if not bloc:
                    break
                sortie.write(bloc)
        if os.path.getsize(partiel) < taille_min:
            raise IOError(f"fichier trop petit ({os.path.getsize(partiel)} octets) — téléchargement incomplet")
        os.replace(partiel, destination)
    except (socket.timeout, Exception):
        if os.path.exists(partiel):
            try:
                os.remove(partiel)
            except Exception:
                pass
        raise


def init_models():
    """Télécharge automatiquement les modèles de VAD et de biométrie vocale s'ils sont absents."""
    os.makedirs(_CORE_DIR, exist_ok=True)
    
    # 1. Silero VAD (2 Mo)
    if not os.path.exists(VAD_MODEL_PATH):
        url_vad = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
        print("🎙  [VAD] Téléchargement du modèle Silero VAD (2 Mo)...")
        try:
            _telecharger_atomique(url_vad, VAD_MODEL_PATH)
            print("✔  [VAD] Silero VAD téléchargé avec succès.")
        except Exception as e:
            print(f"❌  [VAD] Échec du téléchargement Silero VAD : {e}")
            
    # 2. Reconnaissance du locuteur, CAM++ (28 Mo)
    if not os.path.exists(SPEAKER_MODEL_PATH):
        print("🎙  [BIOMETRICS] Téléchargement du modèle de reconnaissance vocale (28 Mo)...")
        try:
            _telecharger_atomique(SPEAKER_MODEL_URL, SPEAKER_MODEL_PATH)
            print("✔  [BIOMETRICS] Modèle de reconnaissance vocale téléchargé avec succès.")
        except Exception as e:
            print(f"❌  [BIOMETRICS] Échec du téléchargement du modèle de reconnaissance vocale : {e}")


class SileroVAD:
    def __init__(self, model_path):
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        so = ort.SessionOptions()
        so.inter_op_num_threads = 1
        so.intra_op_num_threads = 1
        so.log_severity_level = 3
        
        self.session = ort.InferenceSession(model_path, providers=providers, sess_options=so)
        self.reset_states()
        
    def reset_states(self):
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, 64), dtype=np.float32)
        
    def __call__(self, audio_chunk_int16, sr=16000):
        audio_chunk = audio_chunk_int16.astype(np.float32) / 32768.0
        sub_chunk_size = 512
        probs = []
        
        for offset in range(0, len(audio_chunk), sub_chunk_size):
            sub_chunk = audio_chunk[offset:offset+sub_chunk_size]
            if len(sub_chunk) < sub_chunk_size:
                sub_chunk = np.pad(sub_chunk, (0, sub_chunk_size - len(sub_chunk)), 'constant')
                
            x = np.expand_dims(sub_chunk, axis=0)
            x_with_context = np.concatenate([self._context, x], axis=1)
            
            ort_inputs = {
                "input": x_with_context,
                "sr": np.array(sr, dtype=np.int64),
                "state": self._state
            }
            
            out, state = self.session.run(None, ort_inputs)
            self._state = state
            self._context = x_with_context[:, -64:]
            
            probs.append(out[0][0])
            
        return max(probs) if probs else 0.0




class SpeakerBiometrics:
    def __init__(self, model_path, voiceprints_dir):
        self.model_path = model_path
        self.voiceprints_dir = voiceprints_dir
        os.makedirs(self.voiceprints_dir, exist_ok=True)
        
        config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=self.model_path,
            num_threads=2,
            debug=False,
        )
        self.extractor = sherpa_onnx.SpeakerEmbeddingExtractor(config)
        self.dim = self.extractor.dim
        self.modele = os.path.basename(self.model_path)
        self._adapter_au_modele()

    def _adapter_au_modele(self):
        """Après un changement de modèle, recalcule les empreintes depuis l'audio d'enrôlement
        conservé (sample_N.wav). Une empreinte sans audio (enrôlée avant la conservation) est
        mise de côté (sample_N.npy.<ancien modèle>, ignorée) : le profil est à réenregistrer."""
        import wave
        marqueur = os.path.join(self.voiceprints_dir, "_modele.txt")
        ancien = ""
        if os.path.exists(marqueur):
            with open(marqueur, encoding="utf-8") as f:
                ancien = f.read().strip()
        if ancien == self.modele:
            return
        # Sans marqueur (installation antérieure) : les empreintes de la bonne dimension sont
        # supposées venir de ce modèle et gardées telles quelles
        sans_marqueur = not ancien
        suffixe = os.path.splitext(ancien)[0] if ancien else "ancien_modele"
        recalcules, ecartes = 0, 0
        for profil in os.listdir(self.voiceprints_dir):
            dossier = os.path.join(self.voiceprints_dir, profil)
            if not os.path.isdir(dossier):
                continue
            for f in os.listdir(dossier):
                if not f.endswith(".npy"):
                    continue
                chemin = os.path.join(dossier, f)
                if sans_marqueur:
                    try:
                        if np.load(chemin).shape == (self.dim,):
                            continue
                    except Exception:
                        pass
                wav = chemin[:-4] + ".wav"
                emb = None
                if os.path.exists(wav):
                    try:
                        with wave.open(wav, "rb") as w:
                            emb = self.get_embedding(w.readframes(w.getnframes()), w.getframerate())
                    except Exception as e:
                        print(f"[BIOMETRICS] Audio illisible {wav} : {e}")
                if emb is not None:
                    np.save(chemin, emb)
                    recalcules += 1
                else:
                    os.replace(chemin, f"{chemin}.{suffixe}")
                    ecartes += 1
        with open(marqueur, "w", encoding="utf-8") as f:
            f.write(self.modele)
        if recalcules or ecartes:
            print(f"[BIOMETRICS] Modèle {self.modele} : {recalcules} empreinte(s) recalculée(s), "
                  f"{ecartes} mise(s) de côté (profil à réenregistrer).")

    def get_embedding(self, raw_audio_bytes, sample_rate=16000):
        samples = np.frombuffer(raw_audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        
        stream = self.extractor.create_stream()
        stream.accept_waveform(sample_rate=sample_rate, waveform=samples)
        stream.input_finished()
        
        if self.extractor.is_ready(stream):
            emb = self.extractor.compute(stream)
            return np.array(emb)
        return None
        
    def save_voiceprint(self, username, embedding, audio=None, sample_rate=16000):
        """Enregistre l'empreinte, et l'audio d'enrôlement (sample_N.wav) s'il est fourni :
        il permet de recalculer l'empreinte si le modèle change, sans réenregistrer la voix."""
        username_clean = username.lower().strip()
        user_dir = os.path.join(self.voiceprints_dir, username_clean)
        os.makedirs(user_dir, exist_ok=True)

        max_samples = 5
        chosen_file = None
        
        # Trouver un emplacement d'échantillon libre de 1 à 5
        for i in range(1, max_samples + 1):
            filepath = os.path.join(user_dir, f"sample_{i}.npy")
            if not os.path.exists(filepath):
                chosen_file = filepath
                break
                
        # S'ils sont tous pris, on écrase le plus ancien (basé sur le temps de modification)
        if not chosen_file:
            oldest_time = float('inf')
            oldest_file = None
            for i in range(1, max_samples + 1):
                filepath = os.path.join(user_dir, f"sample_{i}.npy")
                if os.path.exists(filepath):
                    mtime = os.path.getmtime(filepath)
                    if mtime < oldest_time:
                        oldest_time = mtime
                        oldest_file = filepath
            chosen_file = oldest_file or os.path.join(user_dir, "sample_1.npy")
            
        np.save(chosen_file, embedding)
        wav = chosen_file[:-4] + ".wav"
        if audio:
            import wave
            with wave.open(wav, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sample_rate)
                w.writeframes(audio)
        elif os.path.exists(wav):
            os.remove(wav)  # audio d'une ancienne empreinte, qui ne correspond plus
        print(f"[BIOMETRICS] Empreinte sauvegardée dans : {chosen_file}")
        
    def load_voiceprints(self):
        import re
        import shutil
        voiceprints = {}
        if not os.path.exists(self.voiceprints_dir):
            return voiceprints

        # 1. Migration automatique des anciens fichiers en vrac de la racine vers leurs sous-dossiers respectifs
        for f in os.listdir(self.voiceprints_dir):
            fpath = os.path.join(self.voiceprints_dir, f)
            if os.path.isfile(fpath) and f.endswith(".npy"):
                raw_name = f[:-4]
                # Identifier le nom de profil en retirant le suffixe de numéro (ex: neyor ou neyor_1)
                name = re.sub(r'_\d+$', '', raw_name).lower()
                
                # Détecter l'index
                match = re.search(r'_(\d+)$', raw_name)
                index = match.group(1) if match else "1"
                
                # Créer le sous-dossier et déplacer le fichier
                user_dir = os.path.join(self.voiceprints_dir, name)
                os.makedirs(user_dir, exist_ok=True)
                new_fpath = os.path.join(user_dir, f"sample_{index}.npy")
                
                try:
                    shutil.move(fpath, new_fpath)
                    print(f"[BIOMETRICS] Migration : {f} déplacé vers {name}/sample_{index}.npy")
                except Exception as me:
                    print(f"[BIOMETRICS] Échec de la migration de {f} : {me}")
        
        # 2. Chargement depuis les sous-dossiers par profil
        for entry in os.listdir(self.voiceprints_dir):
            dir_path = os.path.join(self.voiceprints_dir, entry)
            if os.path.isdir(dir_path):
                username = entry.lower()
                for f in os.listdir(dir_path):
                    if f.endswith(".npy"):
                        try:
                            emb = np.load(os.path.join(dir_path, f))
                            if emb.shape != (self.dim,):
                                continue  # empreinte d'un autre modèle : incomparable
                            if username not in voiceprints:
                                voiceprints[username] = []
                            voiceprints[username].append(emb)
                        except Exception:
                            pass
        return voiceprints
        
    def identify_speaker(self, raw_audio_bytes, sample_rate=16000, threshold=0.60):
        emb = self.get_embedding(raw_audio_bytes, sample_rate)
        if emb is None:
            return "guest", 0.0
            
        voiceprints = self.load_voiceprints()
        if not voiceprints:
            return "guest", 0.0
            
        best_name = "guest"
        best_score = 0.0

        # Normalisation du vecteur d'entrée
        emb_norm = emb / (np.linalg.norm(emb) + 1e-8)

        for name, emb_list in voiceprints.items():
            # Score 1 : meilleur échantillon individuel (comme avant). Un seul
            # échantillon de référence propre suffit à reconnaître l'utilisateur.
            for ref_emb in emb_list:
                ref_norm = ref_emb / (np.linalg.norm(ref_emb) + 1e-8)
                score = float(np.dot(emb_norm, ref_norm))
                if score > best_score:
                    best_score = score
                    best_name = name

            # Score 2 : centroïde des échantillons du profil. Chaque échantillon
            # individuel peut être bruité (enrôlement trop court, micro), mais le
            # bruit tend à s'annuler en moyenne — le centroïde capture mieux la
            # direction "vraie" de la voix. On ne garde ce score que s'il est
            # meilleur : le centroïde ne peut donc jamais faire baisser la
            # reconnaissance par rapport à l'ancien comportement.
            if len(emb_list) >= 2:
                refs_norm = [e / (np.linalg.norm(e) + 1e-8) for e in emb_list]
                centroid = np.mean(refs_norm, axis=0)
                centroid_norm = centroid / (np.linalg.norm(centroid) + 1e-8)
                centroid_score = float(np.dot(emb_norm, centroid_norm))
                if centroid_score > best_score:
                    best_score = centroid_score
                    best_name = name

        if best_score >= threshold:
            return best_name, best_score
        return "guest", best_score
