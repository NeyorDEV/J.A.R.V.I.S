"""Confirmation avant actions destructrices (désinstallation, suppression...).

Une seule confirmation à la fois : elle peut être résolue soit via un clic sur
le popup HUD (message WS "confirm_response"), soit via une réponse vocale
("oui"/"non") interceptée en tout début de traitement_reponse_ia, avant même
le verrou de traitement — sans quoi la réponse vocale resterait bloquée
derrière l'action en cours d'attente de confirmation.
"""

import asyncio
import json
import uuid

from core.audit_log import consigner

_pending = None  # {"id": str, "future": asyncio.Future}

MOTS_OUI = {"oui", "ouais", "yes", "confirme", "confirmé", "vas-y", "go"}
MOTS_NON = {"non", "no", "annule", "annulé", "stop", "cancel"}


def confirmation_en_attente() -> bool:
    return _pending is not None


async def demander_confirmation(websocket, message: str, timeout: float = 20.0) -> bool:
    """Affiche un popup HUD et parle la question ; attend une réponse (clic ou voix)."""
    global _pending

    if _pending is not None and not _pending["future"].done():
        _pending["future"].set_result(False)

    confirm_id = uuid.uuid4().hex
    future = asyncio.get_running_loop().create_future()
    _pending = {"id": confirm_id, "future": future}

    try:
        if websocket is not None:
            try:
                await websocket.send(json.dumps({
                    "type": "confirm_request",
                    "id": confirm_id,
                    "message": message,
                }))
            except Exception:
                pass
        try:
            import builtins
            builtins.parler(f"{message} Dites oui pour confirmer, ou non pour annuler.")
        except Exception:
            pass

        try:
            resultat = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            resultat = False
            consigner("confirmation_timeout", message=message)
            return resultat
        consigner("confirmation_resolue", message=message, confirme=resultat)
        return resultat
    finally:
        if _pending is not None and _pending["id"] == confirm_id:
            _pending = None


def resoudre_confirmation(confirm_id: str, confirmed: bool) -> bool:
    """Résout la confirmation en attente depuis un clic HUD. True si elle correspondait."""
    if _pending is None or _pending["id"] != confirm_id:
        return False
    if not _pending["future"].done():
        _pending["future"].set_result(confirmed)
    return True


def resoudre_confirmation_vocale(texte: str) -> bool:
    """Tente de résoudre la confirmation en attente depuis une réponse vocale.

    Retourne True si le texte a été consommé comme réponse (positive ou
    négative) à la confirmation en attente — dans ce cas l'appelant ne doit
    pas continuer le traitement normal de la commande.
    """
    if _pending is None:
        return False
    t = texte.lower().strip()
    if any(t == m or t.startswith(m + " ") for m in MOTS_OUI):
        resoudre_confirmation(_pending["id"], True)
        return True
    if any(t == m or t.startswith(m + " ") for m in MOTS_NON):
        resoudre_confirmation(_pending["id"], False)
        return True
    return False
