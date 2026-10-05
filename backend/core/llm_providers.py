"""Appels aux fournisseurs LLM secondaires (Grok, Ollama, Groq, Claude, Mistral) et leur registre."""

import asyncio
import re

import requests
from google.genai import types

import core.llm_registry as llm_registry
import core.shared as shared
from core.api_quota import _quota_mgr, _QuotaExceededError
from core.etat_parole import get_stop_parler
from core.prompt_builder import construire_system_prompt
from core.speech import parler
from module.memory_manager import _sauvegarder_echange_conv
from module.vector_memory import ajouter_souvenir, rechercher_souvenirs


async def demander_grok(texte, update_hist=True):
    if not shared.grok_client:
        return None
    
    try:
        # SYNC : On utilise le même prompt système que Gemini (incluant la mémoire)
        souvenirs = rechercher_souvenirs(texte)
        system_prompt = construire_system_prompt(souvenirs=souvenirs)
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
            _sauvegarder_echange_conv(texte, rep)
            ajouter_souvenir(texte, rep)
        
        return rep
    except Exception as e:
        if _quota_mgr.is_quota_error(e):
            _quota_mgr.mark_quota_exceeded("grok")
            raise _QuotaExceededError(f"Grok quota: {e}")
        print(f"[ERREUR GROK] {e}")
        return None


async def demander_ollama(texte, update_hist=True):
    """Appelle un modèle local via Ollama (100% offline)."""
    try:
        # SYNC : On utilise le même prompt système que Gemini (incluant la mémoire)
        souvenirs = rechercher_souvenirs(texte)
        system_prompt = construire_system_prompt(souvenirs=souvenirs) + "\n\nIMPORTANT: Réponds uniquement avec le texte de la réponse, n'utilise JAMAIS de format JSON."
        messages = [{"role": "system", "content": system_prompt}]
        
        # Optimisation : On limite à 16 entrées (8 échanges complets) pour Ollama afin de rester fluide et rapide
        for h in shared.historique[-16:]:
            role = "user" if h.role == "user" else "assistant"
            messages.append({"role": role, "content": h.parts[0].text})
        messages.append({"role": "user", "content": texte})
        
        last_err = None
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
                            "stream": False,
                            "keep_alive": -1
                        },
                        timeout=30
                    ),
                    timeout=35.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    rep = data.get("message", {}).get("content", "")
                    if rep:
                        shared.historique.append(types.Content(role="user", parts=[types.Part(text=texte)]))
                        shared.historique.append(types.Content(role="model", parts=[types.Part(text=rep)]))
                        _sauvegarder_echange_conv(texte, rep)
                        ajouter_souvenir(texte, rep)
                        print(f"[OLLAMA] Reponse recue de {model_name}")
                        return rep
                else:
                    print(f"[OLLAMA] Erreur HTTP {resp.status_code} pour {model_name}")
                    last_err = Exception(f"HTTP {resp.status_code}")
            except Exception as e:
                print(f"[OLLAMA] Echec {model_name} : {e}")
                last_err = e
                continue
        
        print(f"[OLLAMA] Tous les modeles locaux ont echoue")
        return None
    except Exception as e:
        print(f"[ERREUR OLLAMA] {e}")
        return None


async def demander_groq(texte, update_hist=True, skip_local=False):
    """Appelle Groq (Llama 3.3) avec streaming de parole à la volée (vitesse extrême)."""
    if not shared.groq_client:
        return None

    def safe_next(iterator):
        try:
            return next(iterator)
        except StopIteration:
            return None

    try:
        # Recherche de souvenirs
        souvenirs = rechercher_souvenirs(texte)
        system_prompt = construire_system_prompt(souvenirs=souvenirs)
        messages = [{"role": "system", "content": system_prompt}]
        
        for h in shared.historique[-30:]:
            role = "user" if h.role == "user" else "assistant"
            messages.append({"role": role, "content": h.parts[0].text})
            
        messages.append({"role": "user", "content": texte})

        # Démarrage de la complétion en mode streaming (borné dans le temps :
        # une création de stream qui ne répond jamais bloquait sinon toute la
        # conversation, sans qu'aucun fournisseur de secours ne prenne le relais).
        stream = await asyncio.wait_for(
            asyncio.to_thread(
                shared.groq_client.chat.completions.create,
                model="openai/gpt-oss-120b",  # llama-3.3-70b-versatile retiré du catalogue Groq
                messages=messages,
                temperature=0.7,
                stream=True
            ),
            timeout=15.0
        )

        full_text = ""
        sentence_buffer = ""
        iterator = iter(stream)

        while True:
            if get_stop_parler():
                print("[CERVEAU] Interruption de la génération Groq car stop_parler=True")
                break
            # Chaque lecture de chunk est bornée : sans ce timeout, un simple
            # aléa réseau pendant le streaming bloquait next() indéfiniment —
            # aucune exception, aucun fallback, JARVIS restait planté sur
            # « Réflexion (Cloud)... » jusqu'au redémarrage.
            try:
                chunk = await asyncio.wait_for(asyncio.to_thread(safe_next, iterator), timeout=15.0)
            except asyncio.TimeoutError:
                print("[CERVEAU] Groq : flux de streaming bloqué (> 15s sans donnée). Abandon.")
                raise
            if chunk is None:
                break

            chunk_text = chunk.choices[0].delta.content or ""
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

        if update_hist:
            shared.historique.append(types.Content(role="user", parts=[types.Part(text=texte)]))
            shared.historique.append(types.Content(role="model", parts=[types.Part(text=full_text)]))
            _sauvegarder_echange_conv(texte, full_text)
            ajouter_souvenir(texte, full_text)

        # Lire la phrase finale restante
        if not skip_local and '{' not in full_text and sentence_buffer.strip() and not get_stop_parler():
            shared._derniere_reponse_streamed = True
            parler(sentence_buffer.strip())
            shared.phrases_streamed.append(sentence_buffer.strip())

        return full_text
    except Exception as e:
        if _quota_mgr.is_quota_error(e):
            _quota_mgr.mark_quota_exceeded("groq")
            raise _QuotaExceededError(f"Groq quota: {e}")
        # str(e) peut être vide pour certaines exceptions (ex: asyncio.TimeoutError) —
        # sans le nom du type en secours, le log "[ERREUR GROQ]" ne dit rien d'exploitable.
        print(f"[ERREUR GROQ] {e or type(e).__name__}")
        return None


async def demander_claude(texte, update_hist=True):
    """Appelle Claude (Anthropic) — agent IA principal (priorité 0)."""
    if not shared.anthropic_client:
        return None
    try:
        # Recherche de souvenirs
        souvenirs = rechercher_souvenirs(texte)
        system_prompt = construire_system_prompt(souvenirs=souvenirs)
        
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
            _sauvegarder_echange_conv(texte, rep)
            ajouter_souvenir(texte, rep)

        return rep
    except Exception as e:
        if _quota_mgr.is_quota_error(e):
            _quota_mgr.mark_quota_exceeded("claude")
            raise _QuotaExceededError(f"Claude quota: {e}")
        print(f"[ERREUR CLAUDE] {e}")
        return None


async def demander_mistral(texte, update_hist=True):
    """Appelle Mistral AI (Large) — agent IA priorité 3, après Groq et Claude."""
    if not shared.mistral_client:
        return None
    try:
        souvenirs = rechercher_souvenirs(texte)
        system_prompt = construire_system_prompt(souvenirs=souvenirs)

        messages = [{"role": "system", "content": system_prompt}]
        for h in shared.historique[-30:]:
            role = "user" if h.role == "user" else "assistant"
            messages.append({"role": role, "content": h.parts[0].text})
        messages.append({"role": "user", "content": texte})

        response = await asyncio.wait_for(
            asyncio.to_thread(
                shared.mistral_client.chat.complete,
                model="mistral-medium-latest",
                messages=messages,
            ),
            timeout=15.0
        )
        rep = str(response.choices[0].message.content)

        if update_hist:
            shared.historique.append(types.Content(role="user", parts=[types.Part(text=texte)]))
            shared.historique.append(types.Content(role="model", parts=[types.Part(text=rep)]))
            _sauvegarder_echange_conv(texte, rep)
            ajouter_souvenir(texte, rep)

        return rep
    except Exception as e:
        if _quota_mgr.is_quota_error(e):
            _quota_mgr.mark_quota_exceeded("mistral")
            raise _QuotaExceededError(f"Mistral quota: {e}")
        print(f"[ERREUR MISTRAL] {e}")
        return None


# ── Registre des moteurs LLM génériques (priorités 1-3) ──────────────────
# Ajouter un nouveau provider à ce palier = un register() ici, plutôt que de
# dupliquer le bloc de routage (cf. core/llm_registry.py pour le détail).
async def _call_groq_engine(texte, update_hist=True, skip_local=False):
    return await demander_groq(texte, update_hist=update_hist, skip_local=skip_local)


async def _call_claude_engine(texte, update_hist=True, skip_local=False):
    return await demander_claude(texte, update_hist=update_hist)


async def _call_mistral_engine(texte, update_hist=True, skip_local=False):
    return await demander_mistral(texte, update_hist=update_hist)


llm_registry.register("groq", "Groq (GPT-OSS 120B)", 1, lambda: bool(shared.groq_client), _call_groq_engine)
llm_registry.register("claude", "Claude (Anthropic)", 2, lambda: bool(shared.anthropic_client), _call_claude_engine)
llm_registry.register("mistral", "Mistral (Large)", 3, lambda: bool(shared.mistral_client), _call_mistral_engine)
