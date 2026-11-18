"""Compression de la session : les échanges qui sortent de la fenêtre envoyée à l'IA (60 entrées) sont résumés au lieu d'être oubliés.

`shared.resume_session` (texte) est remis en tête de l'historique par llm_chat ; `shared.historique` est ensuite rogné à la fenêtre (il grossissait sans limite).
Le résumé passe par un modèle Gemini léger, en arrière-plan, hors du chemin de la réponse : un échec laisse tout tel quel et réessaie au prochain échange.
Pur et testé (tests/test_compression.py) : l'appel au modèle est injecté.
"""
import asyncio

FENETRE = 60        # entrées gardées telles quelles (même valeur que llm_chat)
MARGE = 10          # on ne résume que par paquets : pas un appel à chaque échange
MAX_RESUME = 1500   # caractères


def a_resumer(historique: list, fenetre: int = FENETRE, marge: int = MARGE):
    """(à_résumer, à_garder) ; à_résumer est vide tant que le dépassement est sous la marge."""
    if len(historique) <= fenetre + marge:
        return [], list(historique)
    coupe = len(historique) - fenetre
    if coupe % 2:   # ne jamais couper entre une question et sa réponse
        coupe += 1
    return list(historique[:coupe]), list(historique[coupe:])


def _texte(entree) -> str:
    parts = getattr(entree, "parts", None) or []
    return " ".join((getattr(p, "text", "") or "") for p in parts).strip()


def consigne(ancien_resume: str, anciens: list) -> str:
    dialogue = "\n".join(f"{'Utilisateur' if getattr(e, 'role', '') == 'user' else 'JARVIS'} : {_texte(e)[:400]}" for e in anciens)
    return ("Résume en français, en 10 lignes maximum, les points utiles pour la suite de cette conversation : demandes en cours, décisions, "
            "préférences exprimées, informations données. Ignore les détails passagers (heure, météo, lancement d'applications). "
            "Réponds uniquement avec le résumé.\n\n"
            f"RÉSUMÉ PRÉCÉDENT :\n{ancien_resume or '(aucun)'}\n\nÉCHANGES À INTÉGRER :\n{dialogue}")


async def compresser(historique: list, ancien_resume: str, llm, fenetre: int = FENETRE, marge: int = MARGE):
    """(nouveau_résumé, historique_rogné), ou (ancien_résumé, historique inchangé) si rien à faire ou si le modèle échoue. `llm(consigne) -> str` est asynchrone."""
    anciens, gardes = a_resumer(historique, fenetre, marge)
    if not anciens:
        return ancien_resume, historique
    try:
        resume = (await asyncio.wait_for(llm(consigne(ancien_resume, anciens)), 20) or "").strip()
    except Exception as e:
        print(f"[COMPRESSION] Résumé impossible ({type(e).__name__}) : historique conservé.")
        return ancien_resume, historique
    if not resume:
        return ancien_resume, historique
    return resume[:MAX_RESUME], gardes


async def _llm_gemini(consigne_texte: str) -> str:
    import core.shared as shared
    r = await shared.client.aio.models.generate_content(model=shared.MODELS_LIST[0], contents=consigne_texte)
    return r.text or ""


_EN_COURS = False


async def compresser_en_fond():
    """Appelée après chaque échange (non bloquant pour l'appelant, une seule à la fois) : met à jour shared.resume_session et rogne shared.historique."""
    global _EN_COURS
    import core.shared as shared
    if _EN_COURS or getattr(shared, "ACTIVE_SPEAKER", "") == "guest":
        return
    _EN_COURS = True
    try:
        n = len(shared.historique)
        resume, nouveau = await compresser(list(shared.historique), getattr(shared, "resume_session", ""), _llm_gemini)
        if nouveau is not None and len(nouveau) < n:
            ajoutes = shared.historique[n:]   # échanges arrivés pendant le résumé
            shared.historique[:] = nouveau + ajoutes
            shared.resume_session = resume
    except Exception as e:
        print(f"[COMPRESSION] {e}")
    finally:
        _EN_COURS = False
