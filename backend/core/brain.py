import asyncio
import time
import json
import builtins
import google.genai as genai
from google.genai import types
from openai import OpenAI
from core.config import GEMINI_API_KEY, GROQ_API_KEY, MODELS_LIST, CHOSEN_MODEL
from core.interlocuteur import nom_virgule

# Clients API
client = genai.Client(api_key=GEMINI_API_KEY)
groq_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1") if GROQ_API_KEY else None

# Injection builtins pour compatibilité
builtins.client = client
builtins.CHOSEN_MODEL = CHOSEN_MODEL

class _QuotaExceededError(Exception):
    pass

# Modèle Groq de secours (llama-3.3-70b-versatile a été retiré du catalogue)
GROQ_FALLBACK_MODEL = "openai/gpt-oss-120b"

# Délai maximal d'attente d'une réponse LLM. Sans lui, une connexion qui reste
# ouverte sans répondre bloquait indéfiniment toute la chaîne de réponse.
TIMEOUT_LLM = 30


async def generer_reponse_ia(prompt, historique=None):
    """Gère la génération de réponse avec failover entre Gemini et Groq."""
    try:
        # Tentative Gemini (bornée dans le temps)
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=CHOSEN_MODEL,
                contents=historique or [prompt],
                config=types.GenerateContentConfig(
                    system_instruction="Tu es JARVIS, l'IA de Tony Stark. Sois concis et efficace."
                )
            ),
            timeout=TIMEOUT_LLM
        )
        return response.text
    except Exception as e:
        est_quota = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
        est_timeout = isinstance(e, asyncio.TimeoutError)
        if (est_quota or est_timeout) and groq_client:
            # Bascule RÉELLE sur Groq. Auparavant cette branche se contentait de
            # renvoyer une phrase d'excuse toute faite : le client Groq était
            # construit mais jamais appelé, donc il n'y avait aucun secours.
            raison = "Quota Gemini atteint" if est_quota else "Gemini ne répond pas"
            print(f"[BRAIN] {raison}, bascule sur Groq ({GROQ_FALLBACK_MODEL})...")
            try:
                messages = [
                    {"role": "system", "content": "Tu es JARVIS, l'IA de Tony Stark. Sois concis et efficace."},
                    {"role": "user", "content": prompt},
                ]
                completion = await asyncio.wait_for(
                    asyncio.to_thread(
                        groq_client.chat.completions.create,
                        model=GROQ_FALLBACK_MODEL,
                        messages=messages,
                        temperature=0.7,
                    ),
                    timeout=TIMEOUT_LLM
                )
                return completion.choices[0].message.content
            except Exception as e_groq:
                print(f"[BRAIN] Secours Groq indisponible : {e_groq}")
                return ("Je rencontre des difficultés avec mes serveurs principaux "
                        f"et mon système de secours{nom_virgule()}.")
        return f"Erreur système : {e}"

# Exportation
builtins.generer_reponse_ia = generer_reponse_ia
