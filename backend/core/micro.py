"""Configuration jarvis_config.json, détection du microphone et détection des applaudissements."""

import json
import os
import re
import time

import speech_recognition as sr

import core.shared as shared
import core.speech as speech
from core.audio_stream import AudioStreamManager, pyaudio
from core.etat_parole import get_is_speaking, set_stop_parler
from core.speech import parler
from core.web_bridge import _safe_ws_send


_JARVIS_CONFIG_PATH = os.path.join(shared.RACINE_PROJET, "jarvis_config.json")


def _charger_config() -> dict:
    """Charge jarvis_config.json ou retourne un dict vide si absent/corrompu."""
    try:
        if os.path.exists(_JARVIS_CONFIG_PATH):
            import json
            with open(_JARVIS_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _sauvegarder_config(data: dict) -> None:
    """Sauvegarde les données dans jarvis_config.json."""
    try:
        import json
        cfg = _charger_config()
        cfg.update(data)
        with open(_JARVIS_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[MIC] Impossible de sauvegarder la config : {e}")


def detecter_microphone() -> int | None:
    """
    Détecte le meilleur microphone disponible.

    Stratégie :
      1. Essaie l'index mémorisé dans jarvis_config.json
      2. Essaie le micro par défaut du système (index None)
      3. Parcourt tous les périphériques d'entrée disponibles
      4. Sauvegarde l'index retenu pour le prochain lancement

    Retourne l'index (int) du micro retenu, ou None si aucun trouvé
    (dans ce cas sr.Microphone() utilisera le défaut OS).
    """
    import json

    # ── Lister tous les périphériques PyAudio ────────────────
    if pyaudio:
        try:
            p = pyaudio.PyAudio()
            nb = p.get_device_count()
            inputs = []
            raw_devices = []
            for i in range(nb):
                try:
                    info = p.get_device_info_by_index(i)
                    if info.get("maxInputChannels", 0) > 0:
                        nom = info.get("name", f"Périphérique {i}")
                        inputs.append((i, nom))
                        
                        # Normaliser et filtrer les périphériques système/virtuels indésirables
                        nom_normalise = nom.lower().strip()
                        exclus = ["mappeur de sons", "capture audio principal", "mixage", "stereo mix", "ivcam", "entrée ligne", "line input", "realtek hd audio mic input"]
                        if any(x in nom_normalise for x in exclus):
                            continue
                            
                        # Nettoyage cosmétique du nom pour fusionner les doublons physiques
                        nom_propre = re.sub(r'\d+-\s*', '', nom) # Retirer les préfixes comme "3- " ou "6- "
                        nom_propre = re.sub(r'sur casque', '', nom_propre, flags=re.IGNORECASE)
                        nom_propre = nom_propre.replace("Headset Microphone", "Microphone")
                        # Supprimer les parenthèses vides ou ne contenant que des espaces
                        nom_propre = re.sub(r'\(\s*\)', '', nom_propre)
                        nom_propre = re.sub(r'\s+', ' ', nom_propre).strip() # Normaliser les espaces doubles
                        
                        # Ignorer si le nom est trop générique ou vide
                        if nom_propre.lower() in ["microphone", ""]:
                            continue
                            
                        raw_devices.append({"index": i, "clean_name": nom_propre})
                except Exception:
                    pass
            p.terminate()

            # Déduplication intelligente par longueur décroissante (priorité aux noms complets non tronqués)
            raw_devices.sort(key=lambda d: len(d["clean_name"]), reverse=True)
            seen_clean_names = set()
            filtered_devices = []
            
            for dev in raw_devices:
                name_lower = dev["clean_name"].lower()
                # Ignorer si c'est un préfixe ou une sous-chaîne d'un nom plus complet déjà enregistré
                is_truncated_duplicate = any(name_lower in seen or seen.startswith(name_lower) for seen in seen_clean_names)
                if not is_truncated_duplicate:
                    seen_clean_names.add(name_lower)
                    filtered_devices.append(dev)
            
            # Réordonner par index croissant pour l'affichage console final
            filtered_devices.sort(key=lambda d: d["index"])
            
            # print("[MIC] Périphériques audio détectés (filtrés et nettoyés) :")
            # for dev in filtered_devices:
            #     print(f"      [{dev['index']}] {dev['clean_name']}")

            if not inputs:
                print("[MIC] ⚠ Aucun périphérique d'entrée détecté par PyAudio.")
        except Exception as e:
            # print(f"[MIC] Impossible de lister les périphériques : {e}")
            pass
    else:
        inputs = []
        # print("[MIC] PyAudio absent — mode fallback speech_recognition uniquement.")
        pass

    # ── Récupérer l'index mémorisé ───────────────────────────
    cfg = _charger_config()
    index_memo = cfg.get("mic_device_index", None)

    # ── Fonction de test d'un index ──────────────────────────
    def _tester_index(idx):
        """Retourne True si sr.Microphone(device_index=idx) s'ouvre correctement."""
        try:
            kwargs = {} if idx is None else {"device_index": idx}
            mic_test = sr.Microphone(**kwargs)
            r_test = sr.Recognizer()
            with mic_test as src:
                r_test.adjust_for_ambient_noise(src, duration=0.3)
            return True
        except Exception as e:
            # label = "défaut" if idx is None else str(idx)
            # print(f"[MIC]   Index {label} → KO ({e})")
            return False

    # ── Priorité 1 : index mémorisé ──────────────────────────
    if index_memo is not None:
        nom_memo = next((n for i, n in inputs if i == index_memo), None)
        if nom_memo is not None:
            print(f"[MIC] [OK] Micro retenu (mémorisé et présent) : [{index_memo}] {nom_memo}")
            return index_memo
        else:
            # print(f"[MIC] Micro mémorisé [{index_memo}] introuvable, recherche d'un remplaçant…")
            pass

    # ── Priorité 2 : micro par défaut OS ─────────────────────
    # print("[MIC] Test du micro par défaut système…")
    if _tester_index(None):
        # Identifier son index réel si possible
        idx_reel = None
        if pyaudio:
            try:
                p = pyaudio.PyAudio()
                idx_reel = p.get_default_input_device_info().get("index", None)
                p.terminate()
            except Exception:
                pass
        nom_defaut = next((n for i, n in inputs if i == idx_reel), "Défaut système")
        print(f"[MIC] [OK] Micro retenu (défaut) : [{idx_reel}] {nom_defaut}")
        _sauvegarder_config({"mic_device_index": idx_reel})
        return idx_reel

    # ── Priorité 3 : parcourir tous les périphériques ────────
    # print("[MIC] Recherche sur tous les périphériques disponibles…")
    for idx, nom in inputs:
        # print(f"[MIC]   Test [{idx}] {nom}…")
        if _tester_index(idx):
            print(f"[MIC] [OK] Micro retenu (fallback) : [{idx}] {nom}")
            _sauvegarder_config({"mic_device_index": idx})
            return idx

    # ── Aucun micro fonctionnel ───────────────────────────────
    print("[MIC] ⚠ Aucun microphone fonctionnel trouvé.")
    print("[MIC]   Vérifiez que votre micro est branché et autorisé dans")
    print("[MIC]   Paramètres Windows → Confidentialité → Microphone.")
    _sauvegarder_config({"mic_device_index": None})
    return None


def monitor_claps():
    if not pyaudio:
        print("[CLAP] PyAudio absent — detection des applaudissements desactivee.")
        return
    try:
        import audioop
        audio_manager = AudioStreamManager()
        cfg_clap = _charger_config()
        
        # 1. Permettre la désactivation complète depuis le fichier de config
        if not cfg_clap.get("enable_claps", True):
            print("[CLAP] Détection des applaudissements désactivée par configuration.")
            return
            
        # 2. Récupérer le seuil de clap configurable (par défaut CLAP_THRESHOLD global)
        threshold = cfg_clap.get("clap_threshold", shared.CLAP_THRESHOLD)
        
        mic_idx_clap = cfg_clap.get("mic_device_index", None)
        if mic_idx_clap is None:
            mic_idx_clap = detecter_microphone()
            
        audio_manager.start(mic_idx_clap)
        queue_clap = audio_manager.subscribe()
        print(f"[CLAP] Détection des applaudissements activée via AudioStreamManager (Seuil: {threshold}, Double clap = réveiller, Simple clap = couper la parole).")
        
        last_clap_time = 0
        rms_history = []
        
        try:
            while True:
                try:
                    data = queue_clap.get(timeout=1.0)
                    rms  = audioop.rms(data, 2)
                    
                    # Ignorer uniquement si Jarvis réfléchit pour éviter les surcharges
                    if shared.is_thinking:
                        last_clap_time = 0
                        rms_history = []
                        continue

                    # Enregistrer la mesure dans l'historique glissant
                    rms_history.append(rms)
                    if len(rms_history) > 3:
                        rms_history.pop(0)
                    
                    # Attendre d'avoir au moins 3 blocs pour pouvoir analyser le caractère transitoire
                    if len(rms_history) < 3:
                        continue

                    # Le candidat au clap est l'élément d'il y a 2 blocs (rms_history[0])
                    candidate_rms = rms_history[0]
                    if candidate_rms > threshold:
                        # Vérification transitoire : l'énergie doit avoir chuté immédiatement après
                        # (dans rms_history[1] et rms_history[2]). Si c'est le cas, c'est un bruit sec (clap).
                        # Sinon, l'énergie reste élevée (parole ou bruit continu), on l'ignore.
                        if rms_history[1] < threshold * 0.75 and rms_history[2] < threshold * 0.75:
                            # Clap validé ! On vide l'historique pour éviter des détections multiples du même pic.
                            rms_history = []
                            
                            current_time = time.time()
                            diff = current_time - last_clap_time
                            
                            # 4. SIMPLE CLAP : Si Jarvis est en train de parler, on l'interrompt immédiatement
                            if get_is_speaking():
                                shared.STOP_PARLER = True
                                set_stop_parler(True)
                                speech.vider_files()
                                print("[CLAP] Parole interrompue via simple clap.")
                            
                            # 5. DOUBLE CLAP : Si l'intervalle correspond, et que Jarvis n'est pas déjà actif
                            if 0.1 < diff < 0.8:
                                if not shared.jarvis_actif:
                                    print(f"\n[CLAP] !!! DOUBLE CLAP DÉTECTÉ !!! Réveil de Jarvis")
                                    
                                    shared.jarvis_actif = True
                                    shared.dernier_message = current_time
                                    
                                    # Mettre à jour l'interface Web et WebSocket
                                    _safe_ws_send(json.dumps({"action": "set_state", "state": "listening"}))
                                    _safe_ws_send(json.dumps({"action": "jarvis_text", "text": "Oui mylane, je vous écoute."}))
                                    
                                    # Dire la phrase d'accueil
                                    parler("Oui mylane, je vous écoute.")
                                    
                                    # Debounce pour éviter la boucle de claps
                                    time.sleep(2.0)
                                    last_clap_time = 0
                                else:
                                    # Déjà actif, on ignore la réactivation mais on réinitialise le timer
                                    last_clap_time = 0
                            else:
                                # Premier clap enregistré
                                last_clap_time = current_time
                except Exception as e:
                    time.sleep(0.1)
                    continue
        finally:
            audio_manager.unsubscribe(queue_clap)

    except Exception as e:
        print(f"[CLAP] Erreur fatale détection claps : {e}")
