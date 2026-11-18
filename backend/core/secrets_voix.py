"""Filtre de secrets : une clé API, un jeton ou une longue chaîne opaque n'est jamais prononcé (ni envoyé au TTS edge de Microsoft).

Appelé par speech.parler. Pur : testé dans tests/test_secrets_voix.py.
"""
import re

MARQUE = "secret masqué"

_MOTIFS = [re.compile(p) for p in (
    r"\bsk-[A-Za-z0-9_\-]{16,}",                       # OpenAI, Anthropic (sk-ant-…)
    r"\bAIza[0-9A-Za-z_\-]{30,}",                      # clés Google
    r"\b(?:gsk|xai|ghp|gho|ghs|github_pat|glpat|xox[abp])[_\-][A-Za-z0-9_\-]{16,}",   # Groq, xAI, GitHub, GitLab, Slack
    r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}",               # jeton JWT
    r"(?i)\bbearer\s+[A-Za-z0-9._\-]{16,}",
    r"\b[A-Fa-f0-9]{32,}\b",                           # empreinte / clé hexadécimale
    r"\b(?=[A-Za-z0-9+/_\-]*[A-Za-z])(?=[A-Za-z0-9+/_\-]*\d)[A-Za-z0-9+/_\-]{40,}={0,2}",   # longue chaîne mêlant lettres et chiffres
)]


def masquer(texte: str) -> str:
    """Remplace chaque secret reconnu par « secret masqué » ; le texte ordinaire (mots, phrases, nombres) ne change pas."""
    if not texte:
        return texte
    for motif in _MOTIFS:
        texte = motif.sub(MARQUE, texte)
    return texte
