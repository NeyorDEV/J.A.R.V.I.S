"""Outils de la boucle d'écoute : transcription (Groq Whisper / Google) et enrôlement vocal."""

import asyncio
import builtins
import io
import re
import time
import wave

import numpy as np
import speech_recognition as sr

import core.shared as shared
from core.etat_parole import get_is_speaking
from core.speech import parler
from core.web_bridge import send_web_state


def transcribe_audio_groq(raw_audio_bytes, sample_rate=16000, recognizer=None):
    """
    Transcrit un segment audio brut (PCM 16-bit mono) via Groq Whisper.
    Fallback automatique sur Google STT si Groq échoue.
    
    Args:
        raw_audio_bytes: bytes PCM bruts (int16, mono)
        sample_rate: fréquence d'échantillonnage (défaut 16000)
        recognizer: instance sr.Recognizer pour le fallback Google
    
    Returns:
        str: texte transcrit en minuscules, ou None si échec total
    """
    # --- TENTATIVE 1 : Groq Whisper (ultra-rapide, ~150ms) ---
    if shared.groq_client:
        try:
            t0 = time.time()
            # Utilisation d'un buffer mémoire (io.BytesIO) au lieu du disque
            audio_buffer = io.BytesIO()
            with wave.open(audio_buffer, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit = 2 bytes
                wf.setframerate(sample_rate)
                wf.writeframes(raw_audio_bytes)
            
            audio_buffer.seek(0)
            # Appel API Groq Whisper
            transcription = shared.groq_client.audio.transcriptions.create(
                file=("audio.wav", audio_buffer.read()),
                model="whisper-large-v3-turbo",
                language="fr",
                response_format="text",
            )
            
            elapsed = time.time() - t0
            texte = transcription.strip().lower() if isinstance(transcription, str) else str(transcription).strip().lower()
            
            # Filtrer les hallucinations Whisper courantes sur le silence/bruit
            texte_clean = texte.rstrip('.!? ')
            hallucinations = {
                "merci", "merci beaucoup", "merci à tous", "je vous remercie",
                "bonjour", "you", "thank you", "subtitles", "sous-titres",
                "sous-titres par amara.org", "sous-titres réalisés par la communauté d'amara.org",
                "subtitles by amara.org",
                "sous-titrage société radio-canada", "sous-titrage société radio canada",
                "sous-titres société radio-canada", "sous-titres société radio canada",
                "sous-titres par la société radio-canada", "société radio-canada", "radio-canada",
                "sous-titrage st' 501", "sous-titrage st 501", "sous-titres st' 501", "sous-titres st 501",
                "sous-titrage", "sous-titres par"
            }
            if texte_clean in hallucinations:
                if shared.jarvis_actif or (shared.WAKE_WORD in texte):
                    print(f"[STT] Groq Whisper : Hallucination potentielle détectée ('{texte}'), repli sur Google.")
                return None

            if texte and len(texte) > 1:
                if shared.jarvis_actif or (shared.WAKE_WORD in texte):
                    print(f"[STT] Groq Whisper OK ({elapsed:.2f}s) : {texte}")
                return texte
            else:
                if shared.jarvis_actif:
                    print(f"[STT] Groq Whisper : réponse vide, fallback Google.")
        except Exception as e:
            if shared.jarvis_actif:
                print(f"[STT] Groq Whisper erreur : {e} — fallback Google.")
    
    # --- TENTATIVE 2 : Google STT (fallback fiable) ---
    if recognizer:
        try:
            audio_data = sr.AudioData(raw_audio_bytes, sample_rate, 2)
            texte = recognizer.recognize_google(audio_data, language="fr-FR").lower().strip()
            if texte:
                if shared.jarvis_actif or (shared.WAKE_WORD in texte):
                    print(f"[STT] Google STT (fallback) : {texte}")
                return texte
        except sr.UnknownValueError:
            pass  # Silence ou parole non reconnue
        except Exception as e:
            print(f"[STT] Google STT erreur : {e}")
    
    return None


def _protocole_enrolement_vocal(commande, queue_ecoute, RATE, CHUNK, SILENCE_LIMIT, ENERGY_THRESHOLD):
    """Protocole d'enrôlement biométrique : 5 phrases répétées, une empreinte vocale par phrase."""
    import queue
    prenom = "neyor"
    if "enregistre la voix de" in commande:
        prenom = commande.split("enregistre la voix de")[-1].strip()
    elif "apprends la voix de" in commande:
        prenom = commande.split("apprends la voix de")[-1].strip()

    prenom = re.sub(r'[^a-zA-Z0-9_-]', '', prenom).lower()
    if not prenom:
        prenom = "neyor"

    # Liste des phrases à répéter proposées et validées par l'utilisateur
    phrases = [
        "Il fait un temps magnifique aujourd'hui pour aller se promener.",
        "J'utilise cet assistant vocal pour contrôler mes applications au quotidien.",
        "La reconnaissance vocale s'adapte parfaitement à ma façon de parler.",
        "Chaque voix possède une empreinte unique, comme une signature acoustique.",
        "Merci de m'avoir aidé à mieux reconnaître votre voix aujourd'hui."
    ]

    parler(f"Très bien. Pour créer un profil robuste pour {prenom.capitalize()}, je vais enregistrer votre voix cinq fois avec des phrases différentes. Répétez distinctement chaque phrase après mon signal.")

    idx_phrase = 0
    enrolement_annule = False
    while idx_phrase < len(phrases):
        # Un appui sur STOP (mobile/HUD) doit annuler tout le protocole,
        # pas seulement couper la phrase en cours : avant ce correctif,
        # la boucle continuait à capturer sans plus rien annoncer, et
        # enregistrait n'importe quel bruit ambiant comme échantillon
        # vocal valide, écrasant au passage de bons échantillons.
        if shared.STOP_PARLER:
            print("🛑 [BIOMETRICS] Enrôlement annulé : signal STOP reçu.")
            enrolement_annule = True
            break

        phrase = phrases[idx_phrase]

        # Attendre la fin de la parole précédente de JARVIS
        while get_is_speaking():
            if shared.STOP_PARLER:
                break
            time.sleep(0.1)
        time.sleep(0.5)

        # Annoncer la phrase à répéter
        parler(f"Phrase numéro {idx_phrase + 1} : Répétez : {phrase}")

        # Attendre la fin du TTS
        while get_is_speaking():
            time.sleep(0.1)
        time.sleep(0.5)

        # Indiquer visuellement l'écoute sur le HUD
        try:
            asyncio.run(send_web_state("listening"))
        except:
            pass

        # Vider la file d'écoute audio pour enlever les bruits accumulés pendant le TTS
        while not queue_ecoute.empty():
            try:
                queue_ecoute.get_nowait()
            except:
                break

        # Boucle de capture VAD pour enregistrer la phrase de l'utilisateur
        enroll_buffer = []
        is_recording_local = False
        silence_start_local = None
        phrase_start_time = time.time()
        speech_detected_local = False
        timeout_local = 15.0  # Limite de temps par phrase (15s)
        # Silence toléré plus long qu'en écoute normale : les phrases
        # d'enrôlement sont volontairement longues (plusieurs mots),
        # et une simple respiration/hésitation en cours de phrase avec
        # le SILENCE_LIMIT normal (0.7-1.0s) coupait l'enregistrement
        # en cours de route, ne capturant que les 2-3 premiers mots —
        # une empreinte vocale bien trop courte pour être fiable.
        silence_limit_local = max(SILENCE_LIMIT, 1.5)
        # Durée minimale d'audio acceptée : 1.5s (24 chunks de 1024
        # échantillons à 16kHz). L'ancien seuil (5 chunks = 0.32s)
        # acceptait des empreintes bien trop courtes pour être stables.
        min_chunks_local = int(1.5 * RATE / CHUNK)

        while time.time() - phrase_start_time < timeout_local:
            if shared.STOP_PARLER:
                print("🛑 [BIOMETRICS] Enrôlement annulé pendant la capture : signal STOP reçu.")
                enrolement_annule = True
                break
            try:
                chunk_data = queue_ecoute.get(timeout=0.1)
                chunk_int16 = np.frombuffer(chunk_data, dtype=np.int16)
            except queue.Empty:
                continue

            # Appliquer le Silero VAD ou fallback sur l'énergie
            is_speech_local = False
            if shared.VAD_MODEL is not None:
                try:
                    speech_prob = shared.VAD_MODEL(chunk_int16, RATE)
                    is_speech_local = speech_prob > 0.45
                except:
                    energy = np.sqrt(np.mean(chunk_int16.astype(np.float64)**2))
                    is_speech_local = energy > ENERGY_THRESHOLD
            else:
                energy = np.sqrt(np.mean(chunk_int16.astype(np.float64)**2))
                is_speech_local = energy > ENERGY_THRESHOLD

            if is_speech_local:
                if not is_recording_local:
                    is_recording_local = True
                    speech_detected_local = True
                    enroll_buffer = [chunk_data]
                else:
                    enroll_buffer.append(chunk_data)
                silence_start_local = None
            elif is_recording_local:
                enroll_buffer.append(chunk_data)
                if silence_start_local is None:
                    silence_start_local = time.time()

                # Si l'utilisateur a fini de parler (silence > silence_limit_local)
                if time.time() - silence_start_local > silence_limit_local:
                    break

        try:
            asyncio.run(send_web_state("idle"))
        except:
            pass

        if enrolement_annule:
            break

        # Validation de l'audio de l'utilisateur
        if not speech_detected_local or len(enroll_buffer) < min_chunks_local:
            parler("Je n'ai pas entendu la phrase en entier, ou elle était trop courte. Recommençons, en parlant bien jusqu'au bout sans vous arrêter.")
            continue

        raw_enroll_audio = b"".join(enroll_buffer)
        if shared.VOICE_BIOMETRICS:
            try:
                emb = shared.VOICE_BIOMETRICS.get_embedding(raw_enroll_audio, RATE)
                if emb is not None:
                    shared.VOICE_BIOMETRICS.save_voiceprint(prenom, emb)
                    print(f"✔  [BIOMETRICS] Échantillon {idx_phrase + 1} enregistré pour : {prenom}")
                    parler(f"Très bien, échantillon {idx_phrase + 1} validé.")
                    idx_phrase += 1
                else:
                    parler("Désolé, je n'ai pas réussi à extraire une empreinte nette. Veuillez répéter cette phrase bien distinctement.")
            except Exception as eb:
                print(f"❌  [BIOMETRICS] Erreur : {eb}")
                parler("Une erreur technique est survenue lors de l'analyse. Recommençons cette phrase.")
        else:
            parler("Le système de biométrie vocale n'est pas initialisé.")
            break

    # Fin du protocole complet
    if enrolement_annule:
        print(f"🛑 [BIOMETRICS] Enrôlement de {prenom} interrompu par l'utilisateur ({idx_phrase}/{len(phrases)} échantillons capturés avant l'annulation).")
    elif idx_phrase == len(phrases):
        shared.ACTIVE_SPEAKER = prenom
        builtins.ACTIVE_SPEAKER = shared.ACTIVE_SPEAKER
        parler(f"C'est parfait {prenom.capitalize()}, le protocole d'enregistrement est terminé. Votre profil vocal multi-empreintes est maintenant actif et sécurisé.")
