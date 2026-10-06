"""Routage des requêtes vers les LLM (local/cloud, failover, streaming Gemini) et vision."""

import asyncio
import base64
import builtins
import json
import re
import threading
from datetime import datetime

import google.genai as genai
from google.genai import types

import core.llm_registry as llm_registry
import core.shared as shared
from core.api_quota import formater_erreur_courte, _quota_mgr, _QuotaExceededError
from core.etat_parole import get_stop_parler
from core.llm_providers import demander_grok, demander_groq, demander_ollama
from core.prompt_builder import construire_system_prompt
from core.speech import parler
from core.web_bridge import est_connecte_internet, _safe_ws_send, send_web_state
from module.memory_manager import _sauvegarder_echange_conv
from module.meteo_domotique import get_meteo_actuelle, get_meteo_ha, HA_URL
from module.sports_web import recherche_web_serpapi
from module.vector_memory import ajouter_souvenir, rechercher_souvenirs
from core.interlocuteur import NOM_CREATEUR, nom_espace


async def demander_ia(texte, update_hist=True, skip_local=False):
    shared.is_thinking = True
    await send_web_state("thinking")
    try:
        # --- ROUTAGE HYBRIDE INTELLIGENT (LOCAL-FIRST) ---
        force_local = getattr(builtins, "FORCE_LOCAL_MODE", False)
        offline = not est_connecte_internet()
        
        # Déterminer si on utilise le cortex local par défaut (vitesse) ou si on élève vers le cloud
        utiliser_local = force_local or offline
        
        if utiliser_local:
            reason = "MODE LOCAL FORCE" if force_local else "CONNEXION OFFLINE"
            print(f"[ROUTEUR] [LOCAL] Traitement local via Ollama - Raison: {reason}")
            
            # Notifier le HUD de la réflexion locale
            _safe_ws_send(json.dumps({"state": "thinking", "status_text": "reflexion (local)..."}))
            
            # Envoyer une carte de notification HUD uniquement si hors-ligne ou forcé pour ne pas polluer l'écran en usage normal
            if (force_local or offline) and hasattr(builtins, "envoyer_carte_contextuelle"):
                await builtins.envoyer_carte_contextuelle(
                    "Traitement Local" if force_local else "Réseau Hors-Ligne",
                    "Requête traitée en local par mon cortex Ollama." if force_local else "Connexion perdue. Bascule sur mon cortex local Ollama.",
                    type_carte="info" if force_local else "alert",
                    icon="⚙" if force_local else "⚠"
                )
                
            rep_ollama = await demander_ollama(texte, update_hist=update_hist)
            if rep_ollama:
                return rep_ollama
                
            # Si le mode local forcé ou hors-ligne a échoué
            if force_local or offline:
                return f"Désolé{nom_espace()}, mon cortex local Ollama n'est pas disponible ou n'est pas lancé actuellement."
                
            # Failsafe : Si le local simple a échoué, on bascule silencieusement sur le cloud
            print("[CERVEAU] Failsafe : Échec d'Ollama local simple, bascule de secours sur le Cloud...")
            _safe_ws_send(json.dumps({"state": "thinking", "status_text": "reflexion (cloud - secours)..."}))
        else:
            print("[ROUTEUR] [CLOUD] Elevation vers le Cloud (Gemini/Claude)...")
            _safe_ws_send(json.dumps({"state": "thinking", "status_text": "reflexion (cloud)..."}))

        # ── RÉSOLUTION LOCALE DÉPORTÉE DANS LES PLUGINS ────────────

        # ── PRIORITÉS 1-3 — moteurs génériques (registre, cf. core/llm_registry) ──
        for engine in llm_registry.available_engines():
            if not _quota_mgr.is_available(engine.name):
                print(f"[CERVEAU] {engine.label} en cooldown ({_quota_mgr.remaining_cooldown(engine.name)}s). Bascule directe.")
                continue
            print(f"[CERVEAU] Tentative avec {engine.label}...")
            try:
                rep_engine = await engine.call(texte, update_hist=update_hist, skip_local=skip_local)
                if rep_engine:
                    return rep_engine
                print(f"[CERVEAU] {engine.label} KO (réponse vide). Bascule suivante.")
            except _QuotaExceededError:
                print(f"[CERVEAU] {engine.label} quota épuisé — cooldown {_quota_mgr.remaining_cooldown(engine.name)}s. Bascule.")
            except Exception as e:
                print(f"[CERVEAU] {engine.label} erreur ({e}). Bascule suivante.")

        cerveau = detecter_cerveau(texte)

        async def _call_gemini():
            if not shared.gemini_actif:
                raise Exception("Clé Gemini non configurée — agent ignoré")

            # Filtrer les modèles dont le quota est épuisé individuellement
            modeles_disponibles = [
                m for m in shared.MODELS_LIST
                if _quota_mgr.is_available(f"gemini_{m}")
            ]
            if not modeles_disponibles:
                # Tous les modèles Gemini sont en cooldown — bascule globale
                _quota_mgr.mark_quota_exceeded("gemini")
                raise _QuotaExceededError("Tous les modèles Gemini sont en cooldown")

            print(f"[CERVEAU] Modèles Gemini disponibles : {modeles_disponibles}...")
            souvenirs = rechercher_souvenirs(texte)
            temp_hist = shared.historique + [types.Content(role="user", parts=[types.Part(text=texte)])]
            prompt_actuel = construire_system_prompt(souvenirs=souvenirs)
            last_err = None
            for model_name in modeles_disponibles:
                try:
                    print(f"[CERVEAU] Essai modele : {model_name} (Streaming)...")
                    # Google Search uniquement si la question semble nécessiter des infos en temps réel
                    _mots_recherche = ["actualité", "actu", "news", "météo", "résultat", "score",
                                       "prix", "cours", "bourse", "aujourd'hui", "maintenant",
                                       "récent", "dernier", "2024", "2025", "2026", "qui est",
                                       "c'est quoi", "cherche", "recherche", "trouve"]
                    _need_search = any(m in texte.lower() for m in _mots_recherche)
                    _tools = [types.Tool(google_search=types.GoogleSearch())] if (_need_search and "3.1-flash-lite" not in model_name) else []

                    # 1. Création du stream avec un timeout adapté (plus long si recherche Google Search active)
                    response_stream = await asyncio.wait_for(
                        shared.client.aio.models.generate_content_stream(
                            model=model_name,
                            config=types.GenerateContentConfig(
                                system_instruction=prompt_actuel,
                                temperature=0.7,
                                tools=_tools if _tools else None,
                            ),
                            contents=temp_hist
                        ),
                        timeout=10.0 if _need_search else 4.0
                    )
                    
                    full_text = ""
                    sentence_buffer = ""
                    
                    # 2. Lecture du stream chunk par chunk avec un timeout de 5 secondes entre chaque chunk
                    while True:
                        if get_stop_parler():
                            print("[CERVEAU] Interruption de la génération Gemini car stop_parler=True")
                            break
                        try:
                            chunk = await asyncio.wait_for(response_stream.__anext__(), timeout=5.0)
                        except StopAsyncIteration:
                            break
                        
                        chunk_text = chunk.text
                        full_text += chunk_text
                        sentence_buffer += chunk_text
                        
                        if not skip_local and '{' not in full_text:
                            # 1. Découpage sur ponctuation forte (suivie d'un espace ou saut de ligne) ou double saut de ligne
                            if any(re.search(p, sentence_buffer) for p in [r'\. ', r'\.\n', r'\! ', r'\!\n', r'\? ', r'\?\n', r'\; ', r'\;\n', r'\: ', r'\:\n', r'\n\n']):
                                shared._derniere_reponse_streamed = True
                                parts = re.split(r'(\.(?: |\n)|\!(?: |\n)|\?(?: |\n)|\;(?: |\n)|\:(?: |\n)|\n\n)', sentence_buffer)
                                for i in range(0, len(parts)-1, 2):
                                    phrase = parts[i] + parts[i+1]
                                    if phrase.strip():
                                        parler(phrase.strip())
                                        shared.phrases_streamed.append(phrase.strip())
                                sentence_buffer = parts[-1]
                            # 2. Sécurité de longueur : si la phrase est longue sans ponctuation forte, on coupe à 60 caractères pour lancer la synthèse
                            elif len(sentence_buffer) > 60 and sentence_buffer.endswith(' '):
                                shared._derniere_reponse_streamed = True
                                parler(sentence_buffer.strip())
                                shared.phrases_streamed.append(sentence_buffer.strip())
                                sentence_buffer = ""

                    if update_hist:
                        shared.historique.append(types.Content(role="user", parts=[types.Part(text=texte)]))
                        shared.historique.append(types.Content(role="model", parts=[types.Part(text=full_text)]))
                        _sauvegarder_echange_conv(texte, full_text)
                        ajouter_souvenir(texte, full_text)
                    
                    if not skip_local and '{' not in full_text and sentence_buffer.strip() and not get_stop_parler():
                        shared._derniere_reponse_streamed = True
                        parler(sentence_buffer.strip())
                        shared.phrases_streamed.append(sentence_buffer.strip())

                    return full_text

                except Exception as e:
                    # Réinitialiser le client global pour purger le pool de connexions corrompu/bloqué
                    try:
                        print("[CERVEAU] Réinitialisation du client Gemini suite à une erreur...")
                        shared.client = genai.Client(api_key=shared.GEMINI_API_KEY) if shared.gemini_actif else None
                        builtins.client = shared.client
                    except Exception as reinit_err:
                        print(f"[CERVEAU] Échec de la réinitialisation du client : {reinit_err}")

                    if _quota_mgr.is_quota_error(e):
                        # Ce modèle spécifique est épuisé → on le met en cooldown et on continue
                        _quota_mgr.mark_quota_exceeded(f"gemini_{model_name}")
                        print(f"[CERVEAU] Gemini quota sur {model_name} — bascule modèle suivant...")
                        last_err = e
                        continue
                    print(f"[CERVEAU] Echec {model_name} : {formater_erreur_courte(e)}")
                    last_err = e
                    continue

            # Tous les modèles disponibles ont échoué
            raise _QuotaExceededError(f"Tous les modèles Gemini ont atteint leur quota : {formater_erreur_courte(last_err)}")

        async def _call_grok():
            if not _quota_mgr.is_available("grok"):
                raise _QuotaExceededError(f"Grok en cooldown ({_quota_mgr.remaining_cooldown('grok')}s)")
            print("[CERVEAU] Tentative avec Grok (xAI)...")
            rep_grok = await demander_grok(texte, update_hist=update_hist)
            if not rep_grok:
                raise Exception("Grok n'a rien renvoyé ou est mal configuré")
            return rep_grok

        # ── ROUTING DYNAMIQUE avec gestion quota ─────────────────────────────
        if cerveau == "GROK" and shared.grok_client:
            try:
                return await _call_grok()
            except _QuotaExceededError as e:
                print(f"[CERVEAU] Grok quota ({formater_erreur_courte(e)}). Bascule Gemini.")
            except Exception as e:
                print(f"[CERVEAU] Grok erreur ({formater_erreur_courte(e)}). Bascule Gemini.")
        try:
            return await _call_gemini()
        except _QuotaExceededError as e:
            print(f"[CERVEAU] Gemini quota ({formater_erreur_courte(e)}). Bascule SerpAPI/Groq/Grok.")
        except Exception as e:
            print(f"[CERVEAU] Gemini erreur ({formater_erreur_courte(e)}). Bascule SerpAPI.")

        # ── FALLBACKS (Gemini KO ou quota) ───────────────────────────────────
        # --- FALLBACK MÉTÉO/TEMP (HA + OpenMeteo) ---
        # On n'exécute ces fallbacks que si on n'est pas en mode "synthesis" (skip_local=False)
        # et que le texte est court (pour éviter les faux positifs dans de longs contenus)
        if not skip_local and len(texte) < 300:
            t_low = texte.lower()

            _mots_meteo = ["quel temps", "météo", "meteo", "il fait quel temps",
                           "temps qu'il fait", "quel temps il fait", "prévisions",
                           "previsions", "va-t-il pleuvoir", "pleut-il",
                           "fait-il beau", "il va pleuvoir", "température dehors",
                           "temperature dehors", "température extérieure",
                           "temperature exterieure", "combien fait-il dehors",
                           "il fait combien dehors"]
            # --- DOMOTIQUE (HOME ASSISTANT) ---
            has_ha = HA_URL and "votre_ip_ha" not in HA_URL.lower()

            if has_ha and any(m in t_low for m in _mots_meteo):
                print("[CERVEAU] Requête météo détectée → Home Assistant weather")
                reponse_ha = get_meteo_ha()
                if reponse_ha:
                    return reponse_ha
                return get_meteo_actuelle(None)
            elif any(m in t_low for m in _mots_meteo):
                # Fallback direct si pas de HA
                return get_meteo_actuelle(None)

            # Note : le fallback "température intérieure sans LLM" a été retiré avec
            # l'ancien système HA codé en dur. Le nouveau système (client MCP,
            # core/ha_mcp_client.py) route les demandes de domotique via un appel
            # Gemini — il ne peut donc pas servir de secours quand Gemini est
            # justement indisponible. C'est un compromis assumé : ce cas (panne
            # totale du LLM + question de température intérieure) est marginal.

        # --- FALLBACK GROQ (LLAMA 3.3) ---
        if shared.groq_client and _quota_mgr.is_available("groq"):
            print("[CERVEAU] Bascule sur Groq (Llama 3.3).")
            try:
                rep_groq = await demander_groq(texte, skip_local=skip_local)
                if rep_groq:
                    return rep_groq
            except _QuotaExceededError:
                print(f"[CERVEAU] Groq quota épuisé — cooldown {_quota_mgr.remaining_cooldown('groq')}s.")
            except Exception as e2:
                print(f"[CERVEAU] Groq erreur ({e2}).")
        elif shared.groq_client:
            print(f"[CERVEAU] Groq en cooldown ({_quota_mgr.remaining_cooldown('groq')}s). Ignoré.")

        # --- FALLBACK GROK (xAI) ---
        if shared.grok_client and _quota_mgr.is_available("grok"):
            print("[CERVEAU] Bascule sur Grok (xAI).")
            try:
                return await _call_grok()
            except _QuotaExceededError:
                print(f"[CERVEAU] Grok quota épuisé — cooldown {_quota_mgr.remaining_cooldown('grok')}s.")
            except Exception as e2:
                print(f"[ERREUR IA (Grok repli)] {e2}")
        elif shared.grok_client:
            print(f"[CERVEAU] Grok en cooldown ({_quota_mgr.remaining_cooldown('grok')}s). Ignoré.")

        # --- FALLBACK OLLAMA (100% offline) ---
        print("[CERVEAU] Gemini et Grok KO. Tentative Ollama (local)...")
        rep_ollama = await demander_ollama(texte)
        if rep_ollama:
            return rep_ollama

        # --- FALLBACK SERPAPI (Web) ---
        # On ne le met qu'à la fin pour éviter qu'il ne "vole" les questions de mémoire
        if len(texte.split()) > 2:
            res_serp = recherche_web_serpapi(texte)
            if res_serp and "VOTRE_CLE" not in res_serp and "rien trouvé" not in res_serp and "erreur" not in res_serp.lower():
                return "Voici ce que j'ai trouvé sur le web : " + res_serp

        # ── Détection : aucune API configurée ou toutes en erreur ──────────
        _aucune_api = (not shared.gemini_actif and not shared.groq_client and not shared.grok_client and not shared.anthropic_client)
        if _aucune_api:
            return (
                f"Je suis bien en ligne{nom_espace()}, mais mes moteurs d'intelligence artificielle ne sont pas encore configurés. "
                "Pour libérer tout mon potentiel, vous devez renseigner vos clés API dans le fichier .env. "
                "En attendant, je reste disponible pour toutes vos commandes locales : domotique, heure, calculs, et bien plus encore !"
            )
        return "Quota API dépassé, Monsieur. Mes capacités de réflexion sont temporairement limitées."
    finally:
        shared.is_thinking = False
        await send_web_state("idle")


async def demander_ia_vision(texte, img_b64):
    """Analyse une image (capture d'écran) avec Gemini Vision."""
    if not shared.gemini_actif or shared.client is None:
        return "La vision nécessite une clé Gemini valide. Configurez-la dans le fichier .env."
    shared.is_thinking = True
    await send_web_state("thinking")
    try:
        print("[VISION] Analyse de l'image avec Gemini...")
        
        # Conversion base64 en bytes pour l'API
        img_bytes = base64.b64decode(img_b64)
        image_part = types.Part.from_bytes(
            data=img_bytes,
            mime_type="image/jpeg"
        )
        
        # Recherche de souvenirs
        souvenirs = rechercher_souvenirs(texte)
        prompt_actuel = construire_system_prompt(souvenirs=souvenirs) + "\n\nIMPORTANT: Réponds uniquement avec le texte de la réponse, n'utilise JAMAIS de format JSON ou de balises structurées. Analyse l'image et réponds."
        
        # On envoie l'image et le texte avec retry en cas de 503
        contents = [
            types.Content(role="user", parts=[image_part, types.Part(text=texte)])
        ]
        
        rep = None
        last_err = None
        for model_name in shared.MODELS_LIST:
            print(f"[VISION] Essai modele : {model_name}")
            for attempt in range(2): # 2 tentatives par modele
                try:
                    print(f"[VISION] Appel modele : {model_name} (Timeout 15s)")
                    response = await asyncio.wait_for(
                        asyncio.to_thread(
                            shared.client.models.generate_content,
                            model=model_name,
                            config=types.GenerateContentConfig(
                                system_instruction=prompt_actuel,
                                temperature=0.7,
                                tools=[types.Tool(google_search=types.GoogleSearch())],
                            ),
                            contents=contents
                        ),
                        timeout=15.0
                    )
                    rep = response.text
                    break
                except Exception as e:
                    if ("503" in str(e) or "overloaded" in str(e).lower()) and attempt < 1:
                        print(f"[VISION] Surcharge {model_name} (503). Retente...")
                        await asyncio.sleep(1)
                        continue
                    print(f"[VISION] Erreur {model_name} : {e}")
                    last_err = e
                    break
            if rep: break
        
        if not rep:
            err_str = str(last_err).lower() if last_err else ""
            if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                print("[VISION] Quota Gemini epuise — vision impossible sans Gemini.")
                return (f"Désolé{nom_espace()}, mon quota Gemini est épuisé pour aujourd'hui. "
                        "La vision par caméra et écran fonctionne uniquement avec Gemini — "
                        "je ne peux donc pas analyser d'images en ce moment. "
                        "Réessayez demain quand le quota sera réinitialisé.")
            print("[VISION] Tous les modeles Gemini ont echoue. Bascule sur Grok (Texte uniquement)...")
            if shared.grok_client:
                return await demander_grok(texte + " (Note: Je n'ai pas pu voir ton écran car mes serveurs de vision sont indisponibles, je réponds donc uniquement à ton texte).")
            raise last_err or Exception("Aucun modele n'a pu analyser l'image")

        # On ajoute la trace dans l'historique (sans l'image pour éviter de saturer la mémoire)
        shared.historique.append(types.Content(role="user", parts=[types.Part(text=f"[Analyse d'écran] {texte}")]))
        shared.historique.append(types.Content(role="model", parts=[types.Part(text=rep)]))
        
        return rep
    except Exception as e:
        print(f"[VISION] Erreur Gemini Vision : {e}")
        # On évite les accolades dans le message d'erreur pour ne pas perturber l'extracteur JSON
        err_msg = str(e).replace("{", "[").replace("}", "]")
        return f"Désolé{nom_espace()}, je n'ai pas pu analyser votre écran. Erreur : {err_msg}"
    finally:
        shared.is_thinking = False
        await send_web_state("idle")


def detecter_cerveau(texte):
    # Heuristique pour basculer sur Grok uniquement pour X/Twitter
    mots_cles_grok = ["sur x", "twitter", "grok", "elon", "x.com"]
    cmd = texte.lower()
    if any(m in cmd for m in mots_cles_grok):
        return "GROK"
    return "GEMINI"


def generer_salutation_demarrage(timeout=6.0):
    """Phrase d'accueil du démarrage, générée par l'IA (style JARVIS, différente à chaque fois).

    Retourne None si Gemini est indisponible ou trop lent : l'appelant prononce alors
    une phrase de secours. Aucun enregistrement dans l'historique ni la mémoire.
    """
    if not shared.client:
        return None
    resultat = {}

    def _appel():
        try:
            maintenant = datetime.now()
            jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
            consigne = (
                f"Tu viens de démarrer. Nous sommes {jours[maintenant.weekday()]}, il est "
                f"{maintenant.strftime('%H:%M')}. Salue {NOM_CREATEUR}, ton créateur, en une seule phrase courte "
                "(8 à 18 mots), adaptée au moment de la journée, dans ton style. "
                "Varie la formulation : ne dis pas 'Je suis prêt', 'Que puis-je faire pour vous' "
                "ni 'Tous mes systèmes sont opérationnels'. Aucune flatterie, aucune action JSON."
            )
            rep = shared.client.models.generate_content(
                model=shared.MODELS_LIST[0],
                contents=consigne,
                config=types.GenerateContentConfig(system_instruction=construire_system_prompt(), temperature=1.0),
            )
            resultat["texte"] = (rep.text or "").strip()
        except Exception as e:
            print(f"[JARVIS] Accueil généré indisponible ({formater_erreur_courte(e)}) — phrase de secours.")

    t = threading.Thread(target=_appel, daemon=True)
    t.start()
    t.join(timeout)
    texte = resultat.get("texte")
    if not texte or "{" in texte or len(texte) > 220:
        return None
    return texte


builtins.demander_ia_vision = demander_ia_vision
