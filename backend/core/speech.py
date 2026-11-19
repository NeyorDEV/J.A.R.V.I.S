import asyncio
import threading
import queue
from core import i18n
import time
import os
import math
import random
import re
import edge_tts
from core import voix_registre
import builtins

try:
    import pygame
except ImportError:
    pygame = None

# Sortie HomePod optionnelle (USE_HOMEPOD_AUDIO=true dans .env)
_USE_HOMEPOD = os.getenv("USE_HOMEPOD_AUDIO", "false").lower() == "true"
if _USE_HOMEPOD:
    try:
        from module.homepod_audio import jouer_sur_homepod
        print("[SPEECH] Mode HomePod activé — sortie audio via AirPlay.")
    except ImportError:
        _USE_HOMEPOD = False
        print("[SPEECH] homepod_audio introuvable — fallback sur pygame.")

import tempfile
_DOSSIER_TTS = os.path.join(tempfile.gettempdir(), "jarvis_tts")

is_speaking = False
speak_volume = 0.0
STOP_PARLER = False
stop_depuis = 0.0   # instant du dernier « stop » (cf. parler)
parole_queue = queue.Queue()
_SANS_ORBE = set()  # phrases dites sans animer l'orbe du HUD (accueil du lancement)
parole_stop_event = threading.Event()
dernier_parle_time = 0

def preparer_mixer():
    if pygame and not pygame.mixer.get_init():
        pygame.mixer.init()

lecture_queue = queue.Queue()

async def _generer_tts_fichier(texte) -> str | None:
    """Génère le fichier TTS en arrière-plan et renvoie le chemin temporaire."""
    if not texte or not texte.strip():
        return None
        
    texte_tts = texte.replace("**", "").replace("*", "").replace("#", "").replace("`", "").strip()
    # Prononciation : « Neyor » se dit « Néyor » (le texte affiché garde « Neyor »)
    texte_tts = re.sub(r"\bneyor\b", "Néyor", texte_tts, flags=re.IGNORECASE)
    # Un fragment sans lettre ni chiffre (ex. un « » » isolé) fait échouer edge_tts
    if not any(c.isalnum() for c in texte_tts):
        return None
    os.makedirs(_DOSSIER_TTS, exist_ok=True)
    tmp = os.path.join(_DOSSIER_TTS, f"jarvis_tts_{int(time.time()*1000)}")   # dossier temporaire dédié : relatif, ils atterrissaient à la racine du projet et un arrêt brutal les y laissait
    
    try:
        return await voix_registre.generer(texte_tts, tmp)   # moteurs essayés dans l'ordre (core/voix_registre.py), un moteur en échec est mis de côté 30 s
    except Exception as e:
        print(f"[SPEECH GENERATION ERROR] {e}")
        return None


async def _moteur_edge_tts(texte_tts, base):
    from core.config import VOIX_ACTUELLE
    chemin = base + ".mp3"
    voix = i18n.voix_edge(VOIX_ACTUELLE)
    await asyncio.wait_for(edge_tts.Communicate(texte_tts, voice=voix, rate="+20%").save(chemin), 12)   # réseau qui stagne : moteur suivant au bout de 12 s
    return chemin


async def _moteur_sapi(texte_tts, base):
    """Voix Windows (SAPI5, hors ligne) par pyttsx3."""
    import pyttsx3
    chemin = base + ".wav"

    def _synthetiser():
        engine = pyttsx3.init()
        engine.setProperty("rate", engine.getProperty("rate") + 25)
        for voice in engine.getProperty("voices"):
            if i18n.mot_voix_windows() in voice.name.lower() or i18n.langue() in voice.languages or i18n.stt_google().lower() in voice.id.lower():
                engine.setProperty("voice", voice.id)
                break
        engine.save_to_file(texte_tts, chemin)
        engine.runAndWait()
    await voix_registre.synthese_http(_synthetiser)
    return chemin


voix_registre.enregistrer("edge_tts", 10, lambda: True, _moteur_edge_tts)
voix_registre.enregistrer("sapi", 90, lambda: True, _moteur_sapi)
try:
    from core import voix_elevenlabs
    voix_elevenlabs.enregistrer()   # désactivé sans réglage « elevenlabs.actif » et clé ELEVENLABS_API_KEY
except Exception as _e:
    print(f"[SPEECH] ElevenLabs indisponible : {_e}")


async def _jouer_tts_fichier(texte, tmp_path):
    """Joue physiquement le fichier TTS pré-généré et notifie le HUD."""
    global is_speaking, speak_volume, STOP_PARLER, dernier_parle_time
    
    if STOP_PARLER:
        try:
            if os.path.exists(tmp_path): os.remove(tmp_path)
        except: pass
        return

    envoyer_etat_hud = getattr(builtins, "envoyer_etat_hud", None)
    envoyer_texte_hud = getattr(builtins, "envoyer_texte_hud", None)
    envoyer_volume_hud = getattr(builtins, "envoyer_volume_hud", None)
    if texte in _SANS_ORBE:  # l'orbe reste en veille : ni état « speaking », ni volume
        _SANS_ORBE.discard(texte)
        envoyer_etat_hud = envoyer_volume_hud = None

    is_speaking = True
    if envoyer_etat_hud: await envoyer_etat_hud("speaking")
    if envoyer_texte_hud: await envoyer_texte_hud(texte)

    try:
        if _USE_HOMEPOD:
            # Lecture sur le HomePod via AirPlay — PC reste silencieux
            speak_volume = 0.8
            if envoyer_volume_hud: await envoyer_volume_hud(speak_volume)
            ok = await jouer_sur_homepod(tmp_path, stop_checker=lambda: STOP_PARLER)
            if not ok:
                # Fallback pygame si le HomePod n'est pas joignable
                print("[SPEECH] HomePod indisponible — fallback casque.")
                if pygame:
                    preparer_mixer()
                    pygame.mixer.music.load(tmp_path)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        if STOP_PARLER:
                            pygame.mixer.music.stop()
                            break
                        await asyncio.sleep(0.05)
            speak_volume = 0.0
            if envoyer_volume_hud: await envoyer_volume_hud(speak_volume)
        elif pygame:
            preparer_mixer()
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                if STOP_PARLER:
                    pygame.mixer.music.stop()
                    break

                t_audio = time.time() * 20
                base_vol = 0.4 + 0.3 * math.sin(t_audio) + 0.2 * math.sin(t_audio * 0.5)
                speak_volume = max(0.1, min(1.0, base_vol + random.uniform(-0.1, 0.1)))

                if envoyer_volume_hud: await envoyer_volume_hud(speak_volume)
                await asyncio.sleep(0.05)
    except Exception as e:
        print(f"[SPEECH PLAYBACK ERROR] {e}")
    finally:
        speak_volume = 0.0
        is_speaking = False
        if envoyer_etat_hud: await envoyer_etat_hud("idle")
        dernier_parle_time = time.time()
        try:
            if pygame and pygame.mixer.get_init():
                pygame.mixer.music.unload()
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except: pass

def gestionnaire_generateur_worker():
    """Générateur d'audio en arrière-plan : génère les fichiers TTS en avance."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while not parole_stop_event.is_set():
        try:
            phrase = parole_queue.get(timeout=1.0)
            if STOP_PARLER:
                parole_queue.task_done()
                continue
                
            phrase = i18n.traduire_sync(phrase)   # mode anglais : phrase écrite en français dite en anglais (core/i18n.py)
            tmp_path = loop.run_until_complete(_generer_tts_fichier(phrase))
            if tmp_path:
                lecture_queue.put({"text": phrase, "file": tmp_path})
            parole_queue.task_done()
        except queue.Empty:
            continue
    loop.close()

def gestionnaire_lecture_worker():
    """Lecteur audio en arrière-plan : joue les fichiers TTS de manière séquentielle."""
    global STOP_PARLER
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while not parole_stop_event.is_set():
        try:
            item = lecture_queue.get(timeout=1.0)
            if STOP_PARLER:
                try:
                    if os.path.exists(item["file"]): os.remove(item["file"])
                except: pass
                lecture_queue.task_done()
                continue
                
            loop.run_until_complete(_jouer_tts_fichier(item["text"], item["file"]))
            lecture_queue.task_done()
        except queue.Empty:
            continue
    loop.close()

def gestionnaire_parole_worker():
    """Point d'entrée du thread JARVIS : pilote le générateur et le lecteur en parallèle."""
    # Nettoyage des fichiers TTS orphelins laissés par la session précédente
    try:
        _racine = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for _base in (_DOSSIER_TTS, _racine, os.path.join(_racine, "backend")):   # + anciens emplacements (racine du projet, backend/)
            if not os.path.isdir(_base):
                continue
            for _f in os.listdir(_base):
                if _f.startswith("jarvis_tts_") and (_f.endswith(".mp3") or _f.endswith(".wav")):
                    try:
                        os.remove(os.path.join(_base, _f))
                    except Exception:
                        pass
    except Exception:
        pass

    t_gen = threading.Thread(target=gestionnaire_generateur_worker, daemon=True)
    t_play = threading.Thread(target=gestionnaire_lecture_worker, daemon=True)
    t_gen.start()
    t_play.start()
    
    while not parole_stop_event.is_set():
        time.sleep(0.5)

def vider_files():
    """Vide et nettoie de façon sécurisée toutes les files d'attente de parole."""
    # 1. Vider les phrases textuelles en attente
    while not parole_queue.empty():
        try:
            parole_queue.get_nowait()
            parole_queue.task_done()
        except:
            break
            
    # 2. Vider les fichiers audio générés et les purger du disque
    while not lecture_queue.empty():
        try:
            item = lecture_queue.get_nowait()
            if os.path.exists(item["file"]):
                try: os.remove(item["file"])
                except: pass
            lecture_queue.task_done()
        except:
            break

def parler(texte, print_console=True, orbe=True):
    global STOP_PARLER
    if STOP_PARLER:
        # « Stop » coupe la réponse en cours ; mais le drapeau restait levé jusqu'à la
        # commande suivante, si bien que toute parole spontanée (alarme, alerte) était
        # muette. Passé quelques secondes, une nouvelle phrase est de nouveau dite.
        if time.time() - stop_depuis < 5:
            return
        STOP_PARLER = False
        try:   # l'autre exemplaire du drapeau (shared) restait levé : la voix de JARVIS n'était plus écartée de l'écoute
            import core.shared as _sh_stop
            _sh_stop.STOP_PARLER = False
        except Exception:
            pass
    if not texte or not texte.strip(): return
    try:   # prénom de l'interlocuteur dans la première phrase après un changement de personne (core/nommer.py)
        import core.shared as _shared
        from core import nommer
        texte = nommer.appliquer(_shared, texte)
    except Exception:
        pass
    try:   # jamais de clé ni de jeton dit à voix haute / envoyé au TTS (core/secrets_voix.py)
        from core.secrets_voix import masquer
        texte = masquer(texte)
    except Exception:
        pass
    if print_console:
        try:
            print(f"[DIT] {texte}")  # « [DIT] » : phrase prononcée (core/console_ui)
        except UnicodeEncodeError:
            try:
                import sys
                enc = sys.stdout.encoding or 'utf-8'
                safe_text = texte.encode(enc, errors='replace').decode(enc)
                print(f"[DIT] {safe_text}")
            except Exception:
                safe_text = "".join(c for c in texte if ord(c) < 128)
                print(f"[DIT] {safe_text}")
    try:   # « répète » : mémoire de ce qui vient d'être dit (core/repeter.py)
        from core.repeter import noter
        noter(texte)
    except Exception:
        pass
    if not orbe:
        _SANS_ORBE.add(texte)
    parole_queue.put(texte)

builtins.parler = parler
