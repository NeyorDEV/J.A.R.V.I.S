"""Appels aux fournisseurs LLM secondaires (Grok, Ollama, Groq, Claude, Mistral) et leur registre."""

import asyncio
import builtins
import json
import re
import threading

import requests
from google.genai import types

import core.llm_registry as llm_registry
import core.shared as shared
from core.api_quota import _quota_mgr, _ErreurQuotaApi
from core.etat_parole import get_stop_parler
from core.prompt_builder import composer_prompt_systeme
from core.speech import parler
from module.memory_manager import _archiver_echange
from module.vector_memory import ajouter_souvenir, rechercher_souvenirs


async def interroger_grok(texte, update_hist=True):
    if not shared.grok_client:
        return None
    
    try:
        # SYNC : On utilise le même prompt système que Gemini (incluant la mémoire)
        souvenirs = rechercher_souvenirs(texte)
        system_prompt = composer_prompt_systeme(souvenirs=souvenirs)
        messages = [{"role": "system", "content": system_prompt}]
        
        for h in shared.historique[-30:]: # Limiter aux 30 derniers messages
            role = "user" if h.role == "user" else "assistant"
            msg_text = h.parts[0].text
            messages.append({"role": role, "content": msg_text})
        
        messages.append({"role": "user", "content": texte})
        
        completion = shared.grok_client.chat.completions.create(
            model="grok-4.6",
            messages=messages,
            temperature=0.7,
        )
        
        rep = completion.choices[0].message.content
        
        # On synchronise l'historique Gemini
        if update_hist:
            shared.historique.append(types.Content(role="user", parts=[types.Part(text=texte)]))
            shared.historique.append(types.Content(role="model", parts=[types.Part(text=rep)]))
            _archiver_echange(texte, rep)
            ajouter_souvenir(texte, rep)
        
        return rep
    except Exception as e:
        if _quota_mgr.est_erreur_quota(e):
            _quota_mgr.declarer_quota_atteint("grok")
            raise _ErreurQuotaApi(f"Grok quota: {e}")
        print(f"[ERREUR GROK] {e}")
        return None


# Ollama (local, sur la carte graphique) : le 1er appel charge le modèle en mémoire vidéo (~8 Go) ;
# 26 à 45 s mesurés à froid, d'où le délai large. Le modèle est libéré après 10 min sans usage
# (1 h en mode local forcé) : avant (keep_alive=-1) un seul secours gardait 8 Go de VRAM occupés
# jusqu'au redémarrage.
DELAI_OLLAMA = 120.0


def _garder_ollama():
    return "60m" if getattr(builtins, "FORCE_LOCAL_MODE", False) else "10m"


def prechauffer_ollama():
    """Charge le 1er modèle local en mémoire vidéo sans attendre une question (mode local activé) :
    la première réponse n'attend plus le chargement."""
    def _charger():
        try:
            requests.post(f"{shared.OLLAMA_URL}/api/generate",
                          json={"model": shared.OLLAMA_MODELS[0], "keep_alive": _garder_ollama()},
                          timeout=DELAI_OLLAMA)
            print(f"[OLLAMA] {shared.OLLAMA_MODELS[0]} chargé en mémoire vidéo.")
        except Exception as e:
            print(f"[OLLAMA] Préchargement impossible : {str(e) or type(e).__name__}")
    threading.Thread(target=_charger, daemon=True).start()


async def interroger_ollama(texte, update_hist=True, skip_local=False):
    """Appelle un modèle local via Ollama (100% offline), phrases lues au fil du flux."""
    try:
        # Même prompt système que les autres moteurs (mémoire comprise) ; 16 entrées
        # d'historique (8 échanges) pour rester rapide en local
        messages = _messages_openai(texte, nb_historique=16)
        messages[0]["content"] += "\n\nIMPORTANT: Réponds uniquement avec le texte de la réponse, n'utilise JAMAIS de format JSON."
    except Exception as e:
        print(f"[ERREUR OLLAMA] {str(e) or type(e).__name__}")
        return None

    for model_name in shared.OLLAMA_MODELS:
        try:
            print(f"[OLLAMA] Essai modele local : {model_name}")
            resp = await asyncio.wait_for(
                asyncio.to_thread(
                    requests.post,
                    f"{shared.OLLAMA_URL}/api/chat",
                    json={
                        "model": model_name,
                        "messages": messages,
                        "stream": True,
                        "think": False,  # pas de « réflexion » préalable : la voix doit démarrer vite
                        "keep_alive": _garder_ollama(),
                    },
                    stream=True,
                    timeout=DELAI_OLLAMA
                ),
                timeout=DELAI_OLLAMA + 5
            )
            if resp.status_code != 200:
                print(f"[OLLAMA] Erreur HTTP {resp.status_code} pour {model_name} : {resp.text[:150]}")
                continue
            rep = await _lire_flux_en_parlant(
                (ligne for ligne in resp.iter_lines() if ligne),
                lambda ligne: json.loads(ligne).get("message", {}).get("content", ""),
                f"Ollama {model_name}", skip_local, delai=DELAI_OLLAMA)
            if rep:
                if update_hist:
                    _memoriser_echange(texte, rep)
                print(f"[OLLAMA] Reponse recue de {model_name}")
                return rep
        except Exception as e:
            print(f"[OLLAMA] Echec {model_name} : {str(e) or type(e).__name__}")
            # Réponse déjà en partie prononcée : ne pas la reprendre avec le modèle suivant
            if shared._derniere_reponse_streamed:
                return " ".join(shared.phrases_streamed)

    print("[OLLAMA] Aucun modèle local n'a répondu")
    return None


# Groq et Ministral répondent d'ordinaire en 1 à 2 s : au-delà de 8 s sans donnée le flux est
# bloqué, on passe au moteur suivant (15 s faisaient attendre jusqu'à 20 s une réponse aussi
# simple que l'heure)
DELAI_FLUX = 8.0
# Ministral 8B : sur le compte gratuit, Mistral Medium / Small / Ministral 14B sont refusés
# (« Rate limit exceeded », « Not enough capacity ») ; le 8B répond en ~0,6 s
MODELE_MISTRAL = "ministral-8b-latest"


def _messages_openai(texte, nb_historique=30):
    """Prompt système + derniers échanges + question, au format chat (Groq, Mistral, Ollama)."""
    souvenirs = rechercher_souvenirs(texte)
    messages = [{"role": "system", "content": composer_prompt_systeme(souvenirs=souvenirs)}]
    for h in shared.historique[-nb_historique:]:
        role = "user" if h.role == "user" else "assistant"
        messages.append({"role": role, "content": h.parts[0].text})
    messages.append({"role": "user", "content": texte})
    return messages


async def _lire_flux_en_parlant(flux, extraire_texte, nom, skip_local=False, delai=DELAI_FLUX):
    """Lit un flux de réponse et prononce chaque phrase dès qu'elle est complète.

    Chaque lecture est bornée (delai, DELAI_FLUX par défaut) : sans ce délai, un aléa réseau pendant le flux
    bloquait next() indéfiniment, sans erreur ni moteur de secours. Renvoie le texte complet."""
    def suivant(iterateur):
        try:
            return next(iterateur)
        except StopIteration:
            return None

    iterateur = iter(flux)
    full_text = ""
    sentence_buffer = ""
    while True:
        if get_stop_parler():
            print(f"[CERVEAU] Interruption de la génération {nom} car stop_parler=True")
            break
        try:
            chunk = await asyncio.wait_for(asyncio.to_thread(suivant, iterateur), timeout=delai)
        except asyncio.TimeoutError:
            print(f"[CERVEAU] {nom} : flux bloqué (> {delai:g} s sans donnée). Abandon.")
            raise
        if chunk is None:
            break

        chunk_text = extraire_texte(chunk)
        if not isinstance(chunk_text, str):
            chunk_text = ""
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
            # 2. Sécurité de longueur : si la phrase est longue, on coupe à 60 caractères pour lancer la synthèse
            elif len(sentence_buffer) > 60 and sentence_buffer.endswith(' '):
                shared._derniere_reponse_streamed = True
                parler(sentence_buffer.strip())
                shared.phrases_streamed.append(sentence_buffer.strip())
                sentence_buffer = ""

    # Lire la phrase finale restante
    if not skip_local and '{' not in full_text and sentence_buffer.strip() and not get_stop_parler():
        shared._derniere_reponse_streamed = True
        parler(sentence_buffer.strip())
        shared.phrases_streamed.append(sentence_buffer.strip())
    return full_text


def _memoriser_echange(texte, reponse):
    shared.historique.append(types.Content(role="user", parts=[types.Part(text=texte)]))
    shared.historique.append(types.Content(role="model", parts=[types.Part(text=reponse)]))
    _archiver_echange(texte, reponse)
    ajouter_souvenir(texte, reponse)


async def interroger_groq(texte, update_hist=True, skip_local=False):
    """Appelle Groq (GPT-OSS 120B) avec lecture des phrases au fil du flux."""
    if not shared.groq_client:
        return None
    try:
        # Création du flux bornée dans le temps : une création qui ne répond jamais bloquait
        # sinon toute la conversation, sans qu'aucun fournisseur de secours ne prenne le relais.
        stream = await asyncio.wait_for(
            asyncio.to_thread(
                shared.groq_client.chat.completions.create,
                model="openai/gpt-oss-120b",  # llama-3.3-70b-versatile retiré du catalogue Groq
                messages=_messages_openai(texte),
                temperature=0.7,
                stream=True
            ),
            timeout=DELAI_FLUX
        )
        full_text = await _lire_flux_en_parlant(
            stream, lambda c: c.choices[0].delta.content if c.choices else "", "Groq", skip_local)
        if update_hist:
            _memoriser_echange(texte, full_text)
        return full_text
    except Exception as e:
        if _quota_mgr.est_erreur_quota(e):
            _quota_mgr.declarer_quota_atteint("groq")
            raise _ErreurQuotaApi(f"Groq quota: {e}")
        # str(e) peut être vide pour certaines exceptions (ex: asyncio.TimeoutError) —
        # sans le nom du type en secours, le log "[ERREUR GROQ]" ne dit rien d'exploitable.
        print(f"[ERREUR GROQ] {str(e) or type(e).__name__}")
        return None


async def interroger_claude(texte, update_hist=True):
    """Interroge Claude (Anthropic), moteur principal (priorité 0)."""
    if not shared.anthropic_client:
        return None
    try:
        # Recherche de souvenirs
        souvenirs = rechercher_souvenirs(texte)
        system_prompt = composer_prompt_systeme(souvenirs=souvenirs)
        
        # Conversion historique Gemini → format Anthropic
        messages = []
        for h in shared.historique[-30:]:
            role = "user" if h.role == "user" else "assistant"
            messages.append({"role": role, "content": h.parts[0].text})
        messages.append({"role": "user", "content": texte})

        message = await asyncio.wait_for(
            asyncio.to_thread(
                shared.anthropic_client.messages.create,
                model="claude-sonnet-5",
                max_tokens=2048,
                system=system_prompt,
                messages=messages
            ),
            timeout=15.0
        )
        rep = str(message.content[0].text)

        # Sync historique global
        if update_hist:
            shared.historique.append(types.Content(role="user", parts=[types.Part(text=texte)]))
            shared.historique.append(types.Content(role="model", parts=[types.Part(text=rep)]))
            _archiver_echange(texte, rep)
            ajouter_souvenir(texte, rep)

        return rep
    except Exception as e:
        if _quota_mgr.est_erreur_quota(e):
            _quota_mgr.declarer_quota_atteint("claude")
            raise _ErreurQuotaApi(f"Claude quota: {e}")
        print(f"[ERREUR CLAUDE] {e}")
        return None


async def interroger_mistral(texte, update_hist=True, skip_local=False):
    """Appelle Mistral (Ministral 8B) avec lecture des phrases au fil du flux (avant : réponse
    complète attendue avant de dire un mot)."""
    if not shared.mistral_client:
        return None
    try:
        stream = await asyncio.wait_for(
            asyncio.to_thread(
                shared.mistral_client.chat.stream,
                model=MODELE_MISTRAL,
                messages=_messages_openai(texte),
            ),
            timeout=DELAI_FLUX
        )
        full_text = await _lire_flux_en_parlant(
            stream, lambda ev: ev.data.choices[0].delta.content if ev.data.choices else "", "Mistral", skip_local)
        if update_hist:
            _memoriser_echange(texte, full_text)
        return full_text
    except Exception as e:
        if _quota_mgr.est_erreur_quota(e):
            _quota_mgr.declarer_quota_atteint("mistral")
            raise _ErreurQuotaApi(f"Mistral quota: {e}")
        print(f"[ERREUR MISTRAL] {str(e) or type(e).__name__}")
        return None


# ── Registre des moteurs LLM génériques (priorités 1-3) ──────────────────
# Ajouter un nouveau provider à ce palier = un register() ici, plutôt que de
# dupliquer le bloc de routage (cf. core/llm_registry.py pour le détail).
async def _call_groq_engine(texte, update_hist=True, skip_local=False):
    return await interroger_groq(texte, update_hist=update_hist, skip_local=skip_local)


async def _call_claude_engine(texte, update_hist=True, skip_local=False):
    return await interroger_claude(texte, update_hist=update_hist)


async def _call_mistral_engine(texte, update_hist=True, skip_local=False):
    return await interroger_mistral(texte, update_hist=update_hist, skip_local=skip_local)


llm_registry.register("groq", "Groq (GPT-OSS 120B)", 1, lambda: bool(shared.groq_client), _call_groq_engine)
llm_registry.register("claude", "Claude (Anthropic)", 2, lambda: bool(shared.anthropic_client), _call_claude_engine)
llm_registry.register("mistral", "Mistral (Ministral 8B)", 3, lambda: bool(shared.mistral_client), _call_mistral_engine)
