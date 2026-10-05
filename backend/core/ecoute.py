"""Boucle d'écoute vocale continue : VAD, wake word, transcription, biométrie, envoi des commandes."""

import asyncio
import builtins
import io
import json
import os
import threading
import time
import wave

import numpy as np
import speech_recognition as sr

import core.shared as shared
import core.speech as speech
from controller.actions_pc import executer_action_pc
from core.audio_stream import AudioStreamManager
from core.ecoute_outils import _protocole_enrolement_vocal, transcribe_audio_groq
from core.etat_parole import get_dernier_parle_time, get_is_speaking, set_stop_parler
from core.micro import detecter_microphone
from core.speech import parler
from core.traitement import nettoyer_commande, traiter_reponse_ia
from core.web_bridge import envoyer_carte_contextuelle, _safe_ws_send, send_web_state


def ecouter():
    r = sr.Recognizer()
    mic_index = detecter_microphone()
    
    # Paramètres VAD
    RATE = 16000
    CHUNK = 1024
    
    # Seuil d'énergie (ajustable dynamiquement)
    cfg_eco = {}
    try:
        config_path = os.path.join(shared.RACINE_PROJET, "jarvis_config.json")
        if os.path.exists(config_path):
            import json
            with open(config_path, "r", encoding="utf-8") as f:
                cfg_eco = json.load(f)
    except Exception:
        pass
    ENERGY_THRESHOLD = cfg_eco.get("energy_threshold", 250)
    SILENCE_LIMIT = 0.7 if shared.VAD_MODEL is not None else 1.0  # s de silence avant de couper
    # Durée maximale d'un énoncé capté avant troncature (garde-fou mémoire)
    MAX_UTTERANCE_SEC = 45
    _MAX_CHUNKS_ENONCE = int(MAX_UTTERANCE_SEC * RATE / CHUNK)
    
    audio_manager = AudioStreamManager()
    try:
        audio_manager.start(mic_index)
        queue_ecoute = audio_manager.subscribe()
    except Exception as e:
        print(f"[MIC] Erreur abonnement au flux : {e}")
        return

    print("[JARVIS] Streaming VAD actif via AudioStreamManager. En attente de parole...")

    audio_buffer = []
    is_recording = False
    silence_start = None
    
    # --- Transcription intérimaire en temps réel ---
    INTERIM_INTERVAL = 1.2  # secondes entre chaque transcription partielle
    last_interim_time = 0.0
    _interim_lock = threading.Lock()
    
    
    while True:
        try:
            if shared.MIC_NEED_RELOAD:
                print("[MIC] Rechargement du micro demande...")
                mic_index = detecter_microphone()
                try:
                    audio_manager.reload(mic_index)
                except Exception as e:
                    print(f"[MIC] Erreur redemarrage : {e}")
                shared.MIC_NEED_RELOAD = False
                continue

            if shared.MIC_MUTED:
                while not queue_ecoute.empty():
                    try:
                        queue_ecoute.get_nowait()
                    except:
                        break
                time.sleep(0.1)
                continue



            # Synchronisation du dernier message depuis les modules/plugins
            if hasattr(builtins, "dernier_message"):
                shared.dernier_message = builtins.dernier_message
                delattr(builtins, "dernier_message")

            # 1. Gestion du timeout de session
            if shared.jarvis_actif and (time.time() - shared.dernier_message > shared.SESSION_TIMEOUT):
                print(f"[JARVIS] Timeout session ({shared.SESSION_TIMEOUT}s). Retour en veille.")
                shared.jarvis_actif = False
                _safe_ws_send(json.dumps({"action": "jarvis_text", "text": ""}))
                try:
                    asyncio.run(send_web_state("idle"))
                except: pass
                
                # Consolidation automatique de la mémoire en arrière-plan (non bloquante)
                try:
                    from module.memory_manager import consolider_memoire_ia
                    from module.vector_memory import consolider_memoire_vectorielle_ia
                    def _run_consolidation():
                        try:
                            loop = asyncio.new_event_loop()
                            loop.run_until_complete(consolider_memoire_ia())
                            # Séquentiel après la mémoire clé-valeur : les deux appellent Gemini,
                            # les lancer en parallèle doublerait juste la pression sur le quota
                            # pour un gain de temps négligeable (tâche de fond, pas de délai perçu).
                            loop.run_until_complete(consolider_memoire_vectorielle_ia())
                            loop.close()
                        except Exception as e_thread:
                            print(f"[JARVIS] Erreur thread consolidation : {e_thread}")

                    threading.Thread(target=_run_consolidation, daemon=True).start()
                except Exception as ce:
                    print(f"[JARVIS] Échec du déclenchement de la consolidation automatique : {ce}")

            # 2. Lecture du flux audio
            try:
                data = queue_ecoute.get(timeout=0.2)
                audio_chunk_int16 = np.frombuffer(data, dtype=np.int16)
            except Exception:
                continue

            # 3. BARGE-IN AUTOMATIQUE DÉSACTIVÉ (À la demande de l'utilisateur)
            # JARVIS ne s'arrête plus au bruit ambiant, seulement sur commande vocale "Stop/Silence"
            else:
                ecouter._noise_count = 0

            # 4. LOGIQUE VAD (Capture de la phrase)
            is_speech = False
            if shared.VAD_MODEL is not None:
                try:
                    speech_prob = shared.VAD_MODEL(audio_chunk_int16, RATE)
                    # Seuil abaissé de 0.65 à 0.55 : au-dessus de 0.65, une voix
                    # un peu douce ou du bruit de fond ne franchissait jamais le
                    # seuil, donc aucun enregistrement ne démarrait — l'utilisateur
                    # devait répéter, sans qu'aucune erreur ne l'indique. 0.55 reste
                    # nettement au-dessus du seuil d'enrôlement (0.45) pour limiter
                    # le risque de faux positifs sur bruit ambiant/TV.
                    is_speech = speech_prob > 0.55
                except Exception as ev:
                    energy = np.sqrt(np.mean(audio_chunk_int16.astype(np.float64)**2))
                    is_speech = energy > ENERGY_THRESHOLD
            else:
                energy = np.sqrt(np.mean(audio_chunk_int16.astype(np.float64)**2))
                is_speech = energy > ENERGY_THRESHOLD

            # Alimente openWakeWord en continu quand JARVIS est en veille (détection locale du wake word)
            if shared.WAKEWORD_MODEL is not None and not shared.jarvis_actif and not get_is_speaking():
                try:
                    ww_score = shared.WAKEWORD_MODEL(audio_chunk_int16)
                    if ww_score > getattr(ecouter, "_wake_score", 0.0):
                        ecouter._wake_score = ww_score
                except Exception:
                    pass

            if is_speech:
                if not is_recording:
                    if not get_is_speaking():
                        try: asyncio.run(send_web_state("listening"))
                        except: pass
                    is_recording = True
                    audio_buffer = [data]
                    ecouter._buffer_sature = False
                    last_interim_time = time.time()  # Reset timer interim
                    ecouter._recorded_during_speech = get_is_speaking()
                else:
                    # Plafond de sécurité : sans lui, un bruit continu détecté comme
                    # parole (TV, musique, VAD bloqué haut) faisait grossir la liste
                    # indéfiniment, jusqu'à un b"".join() de plusieurs centaines de Mo
                    # envoyé au STT. On coupe l'énoncé à MAX_UTTERANCE_SEC.
                    if len(audio_buffer) < _MAX_CHUNKS_ENONCE:
                        audio_buffer.append(data)
                    elif not getattr(ecouter, "_buffer_sature", False):
                        ecouter._buffer_sature = True
                        print(f"[VAD] Énoncé trop long (> {MAX_UTTERANCE_SEC}s) : capture tronquée.")
                    if get_is_speaking():
                        ecouter._recorded_during_speech = True
                    # --- TRANSCRIPTION INTÉRIMAIRE EN TEMPS RÉEL (Active uniquement si réveillé) ---
                    now = time.time()
                    if shared.jarvis_actif and (now - last_interim_time >= INTERIM_INTERVAL) and shared.groq_client:
                        last_interim_time = now
                        # Copie du buffer pour le thread (évite les race conditions)
                        buffer_copy = list(audio_buffer)
                        threading.Thread(
                            target=_envoyer_interim,
                            args=(buffer_copy, RATE),
                            daemon=True
                        ).start()
                silence_start = None
            elif is_recording:
                if len(audio_buffer) < _MAX_CHUNKS_ENONCE:
                    audio_buffer.append(data)
                if get_is_speaking():
                    ecouter._recorded_during_speech = True
                if silence_start is None:
                    silence_start = time.time()
                
                if time.time() - silence_start > SILENCE_LIMIT:
                    is_recording = False
                    if shared.VAD_MODEL is not None:
                        shared.VAD_MODEL.reset_states()
                    try: asyncio.run(send_web_state("idle"))
                    except: pass
                    
                    raw_audio = b"".join(audio_buffer)
                    
                    try:
                        was_during_speech = getattr(ecouter, "_recorded_during_speech", False)
                        
                        # Si l'enregistrement a eu lieu pendant que Jarvis parlait, qu'il n'a pas été interrompu,
                        # et qu'on est configuré pour ignorer le micro pendant la parole, on rejette directement.
                        if was_during_speech and cfg_eco.get("ignore_mic_while_speaking", True) and not shared.STOP_PARLER:
                            # print("[JARVIS] Phrase complète ignorée sans transcription (auto-audition de Jarvis).")
                            audio_buffer = []
                            continue

                        # GATE OPENWAKEWORD : en veille, on ne paie l'appel STT que si le wake word
                        # a été détecté localement. La vérification "WAKE_WORD in texte" plus bas
                        # reste l'autorité finale (un faux positif ne coûte qu'une transcription).
                        if shared.WAKEWORD_MODEL is not None and not shared.jarvis_actif and not was_during_speech:
                            wake_score = getattr(ecouter, "_wake_score", 0.0)
                            ecouter._wake_score = 0.0  # Fenêtre de détection consommée
                            if wake_score < shared.WAKEWORD_THRESHOLD:
                                print(f"[WAKEWORD] Phrase ignorée sans STT (score {wake_score:.2f} < seuil {shared.WAKEWORD_THRESHOLD}).")
                                audio_buffer = []
                                continue
                            print(f"[WAKEWORD] Wake word détecté localement (score {wake_score:.2f}) → transcription.")

                        # Transcription Groq Whisper avec fallback Google STT
                        texte = transcribe_audio_groq(raw_audio, RATE, r)
                        
                        if time.time() - get_dernier_parle_time() < 0.8:
                            audio_buffer = []
                            continue

                        if texte:
                            is_relevant = (shared.WAKE_WORD in texte.lower()) or shared.jarvis_actif
                            if not is_relevant:
                                if shared.WAKEWORD_MODEL is not None:
                                    print(f"[WAKEWORD] Détection locale mais aucun 'jarvis' dans la transcription : « {texte} » — ignoré (pas d'activation).")
                                _safe_ws_send(json.dumps({"action": "jarvis_text", "text": ""}))
                                audio_buffer = []
                                continue
                                
                            print(f"[VAD ENTENDU] {texte}")
                            shared.dernier_message = time.time()
                            
                            # --- BIOMÉTRIE : IDENTIFIER LE LOCUTEUR ---
                            if shared.VOICE_BIOMETRICS:
                                try:
                                    name, score = shared.VOICE_BIOMETRICS.identify_speaker(raw_audio, RATE)
                                    voiceprints = shared.VOICE_BIOMETRICS.load_voiceprints()
                                    if not voiceprints:
                                        shared.ACTIVE_SPEAKER = "mylane"
                                        builtins.ACTIVE_SPEAKER = shared.ACTIVE_SPEAKER
                                        print(f"🎙  [SPEAKER] Aucun profil enregistré. Par défaut : {shared.ACTIVE_SPEAKER}")
                                    else:
                                        shared.ACTIVE_SPEAKER = name
                                        builtins.ACTIVE_SPEAKER = shared.ACTIVE_SPEAKER
                                        if name != "guest":
                                            print(f"🎙  [SPEAKER] Utilisateur authentifié : {name} (Similarité: {score:.2f})")
                                        else:
                                            print(f"🎙  [SPEAKER] Utilisateur inconnu (max Similarité: {score:.2f}). Mode invité activé.")
                                            
                                    # Annonce vocale unique si changement de locuteur dans la session
                                    if shared.SPEAKER_ANNOUNCED != shared.ACTIVE_SPEAKER:
                                        shared.SPEAKER_ANNOUNCED = shared.ACTIVE_SPEAKER
                                        if shared.ACTIVE_SPEAKER == "guest":
                                            parler("Voix inconnue détectée, connexion en mode invité restreint.")
                                        elif shared.ACTIVE_SPEAKER == "mylane":
                                            parler("Voix de Mylane détectée, toutes les permissions sont accordées.")
                                        else:
                                            parler(f"Voix de {shared.ACTIVE_SPEAKER.capitalize()} détectée, connexion sécurisée établie.")
                                except Exception as eb:
                                    print(f"❌  [SPEAKER] Erreur lors de l'identification : {eb}")
                            
                            was_during_speech = getattr(ecouter, "_recorded_during_speech", False)
                            
                            if was_during_speech and any(w in texte for w in ["tais-toi", "silence", "stop", "chut", "arrête-toi", "arrête toi", "stoppe"]):
                                shared.STOP_PARLER = True
                                set_stop_parler(True)
                                speech.vider_files()
                                audio_buffer = []
                                print("[JARVIS] Interruption forcée (barge-in) : File de parole vidée.")
                                continue
                            
                            if was_during_speech and cfg_eco.get("ignore_mic_while_speaking", True):
                                print(f"[JARVIS] Commande ignorée (enregistrement pendant que Jarvis parlait) : {texte}")
                                audio_buffer = []
                                continue
                            
                            if shared.WAKE_WORD in texte or shared.jarvis_actif:
                                if shared.WAKE_WORD in texte: shared.jarvis_actif = True
                                commande = nettoyer_commande(texte)
                                
                                if commande:
                                    shared.STOP_PARLER = False
                                    set_stop_parler(False)


                                    # --- TEST CARTES CONTEXTUELLES ---
                                    if "test carte" in commande or "affiche carte" in commande:
                                        loop = asyncio.new_event_loop()
                                        loop.run_until_complete(envoyer_carte_contextuelle(
                                            "Test Protocole", 
                                            "Ceci est une carte de test générée par le nouveau système contextuel. Tous les capteurs sont opérationnels.",
                                            type_carte="info",
                                            icon="◈"
                                        ))
                                        parler("Carte de test affichée sur le HUD, mylane.")
                                        loop.close()
                                        audio_buffer = []
                                        continue
                                    
                                    # --- ENREGISTREMENT VOCAL / BIOMÉTRIE ---
                                    if "enregistre la voix de" in commande or "apprends la voix de" in commande or "enregistre ma voix" in commande:
                                        _protocole_enrolement_vocal(commande, queue_ecoute, RATE, CHUNK, SILENCE_LIMIT, ENERGY_THRESHOLD)

                                        audio_buffer = []
                                        continue

                                    action_pc = executer_action_pc(commande)
                                    if action_pc:
                                        parler(action_pc)
                                    else:
                                        # On exécute la commande sur la boucle du WebSocket, pas sur
                                        # une boucle jetable. L'ancienne version créait une boucle,
                                        # la fermait aussitôt, et emportait avec elle :
                                        #   - les asyncio.create_task() lancés pendant le traitement
                                        #     (ex. le dev swarm ne démarrait jamais à la voix),
                                        #   - les envois WebSocket, dont les objets appartiennent à
                                        #     WS_LOOP (HUD jamais mis à jour, échec silencieux),
                                        #   - les futures de capture d'écran (« regarde l'écran »
                                        #     attendait systématiquement les 15 s de timeout).
                                        if shared.WS_LOOP is not None and not shared.WS_LOOP.is_closed():
                                            _fut_cmd = asyncio.run_coroutine_threadsafe(
                                                traiter_reponse_ia(commande, from_voice=True), shared.WS_LOOP
                                            )
                                            _fut_cmd.result()   # bloquant, comme l'ancien comportement
                                        else:
                                            # Repli si le serveur WebSocket n'est pas encore prêt
                                            loop = asyncio.new_event_loop()
                                            try:
                                                loop.run_until_complete(
                                                    traiter_reponse_ia(commande, from_voice=True)
                                                )
                                            finally:
                                                loop.close()
                                elif shared.WAKE_WORD in texte:
                                    parler("Oui mylane, je vous écoute.")
                        else:
                            _safe_ws_send(json.dumps({"action": "jarvis_text", "text": ""}))
                                    
                    except Exception as e:
                        print(f"[VAD] Erreur reconnaissance : {e}")
                    
                    audio_buffer = []

        except Exception as e:
            print(f"[VAD] Erreur boucle principale : {e}")
            time.sleep(1)

    audio_manager.unsubscribe(queue_ecoute)


def _envoyer_interim(audio_chunks, rate):
    """Thread non-bloquant : transcrit le buffer partiel et envoie au HUD."""
    try:
        num_chunks = int((7.0 * rate) // 1024)
        recent_chunks = audio_chunks[-num_chunks:]
        raw = b"".join(recent_chunks)
        if len(raw) < rate:  # Moins de 0.5s d'audio (16-bit mono = 2 bytes/sample)
            return
        texte = None
        if get_is_speaking():
            # Si Jarvis parle, on utilise Google STT (gratuit et sans limite) pour détecter le barge-in ("stop")
            try:
                import speech_recognition as sr
                recognizer = sr.Recognizer()
                audio_data = sr.AudioData(raw, rate, 2)
                texte = recognizer.recognize_google(audio_data, language="fr-FR").lower().strip()
            except Exception:
                pass
        else:
            # Sinon on utilise Groq Whisper pour une précision maximale
            if not shared.groq_client:
                return
            try:
                audio_buffer = io.BytesIO()
                with wave.open(audio_buffer, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(rate)
                    wf.writeframes(raw)

                audio_buffer.seek(0)
                result = shared.groq_client.audio.transcriptions.create(
                    file=("interim.wav", audio_buffer.read()),
                    model="whisper-large-v3-turbo",
                    language="fr",
                    response_format="text",
                )
                texte = result.strip().lower() if isinstance(result, str) else str(result).strip().lower()
            except Exception as ex:
                print(f"[INTERIM] Exception Groq : {ex}")

        if texte and len(texte) > 1:
            if shared.jarvis_actif or (shared.WAKE_WORD in texte.lower()):
                _safe_ws_send(json.dumps({"action": "interim_speech", "text": texte}))

            # Interruption immédiate si un mot-clé de stop est détecté pendant qu'il parle
            is_speaking_active = speech.is_speaking or not speech.lecture_queue.empty() or not speech.parole_queue.empty()
            if is_speaking_active and any(w in texte for w in ["tais-toi", "silence", "stop", "chut", "arrête-toi", "arrête toi", "stoppe"]):
                shared.STOP_PARLER = True
                set_stop_parler(True)
                speech.vider_files()
                ecouter._recorded_during_speech = True
                print("[JARVIS] Interruption forcée (barge-in interim) : File de parole vidée.")
    except Exception as e:
        pass  # Silencieux — l'interim est cosmétique, pas critique
