"""Registre des moteurs LLM cloud "génériques" (priorités 1-3 de demander_ia).

Groq / Claude / Mistral partagent tous la même forme d'appel (fonction async,
vérification de quota via api_quota, gestion d'erreur identique) — les
enregistrer ici évite de dupliquer ce bloc à chaque nouveau provider et
centralise l'ordre de priorité : ajouter un provider dans ce palier revient à
appeler register() une fois, plutôt qu'à copier ~15 lignes de routage.

Volontairement NON inclus ici : Gemini (streaming multi-modèles avec Google
Search et cooldown par modèle individuel), Grok (routage conditionnel via
detecter_cerveau), Ollama et SerpAPI (fallbacks de dernier recours avec leur
propre logique métier). Ces chemins ont chacun un comportement trop
spécifique pour être généralisés sans réécriture complète et re-test
approfondi — les regrouper de force ici aurait ajouté du risque sans gain.
"""

from dataclasses import dataclass
from typing import Awaitable, Callable, Optional


@dataclass
class LLMEngine:
    name: str          # clé utilisée par api_quota (ex: "groq")
    label: str         # nom affiché dans les logs (ex: "Groq (GPT-OSS 120B)")
    priority: int
    is_configured: Callable[[], bool]
    call: Callable[..., Awaitable[Optional[str]]]


_engines: list[LLMEngine] = []


def register(name: str, label: str, priority: int,
             is_configured: Callable[[], bool],
             call: Callable[..., Awaitable[Optional[str]]]) -> None:
    _engines[:] = [e for e in _engines if e.name != name]
    _engines.append(LLMEngine(name=name, label=label, priority=priority,
                               is_configured=is_configured, call=call))
    _engines.sort(key=lambda e: e.priority)


def available_engines() -> list[LLMEngine]:
    """Moteurs enregistrés et configurés (clé API présente), triés par priorité.

    Ne filtre PAS sur le quota/cooldown : c'est à l'appelant de vérifier via
    api_quota (le cooldown peut changer entre le moment où la liste est
    consultée et celui où le moteur est réellement appelé).
    """
    return [e for e in _engines if e.is_configured()]
