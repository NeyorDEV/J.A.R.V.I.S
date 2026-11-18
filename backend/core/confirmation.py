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

MOTS_OUI = {"oui", "ouais", "yes", "confirme", "confirmer", "je confirme", "vas y", "go", "ok",
            "okay", "d accord", "daccord", "bien sur", "absolument", "exactement", "fais le",
            "c est bon", "allez y", "oui oui"}
MOTS_NON = {"non", "no", "nan", "annule", "annuler", "stop", "cancel", "surtout pas",
            "pas question", "laisse tomber", "arrete", "non merci", "attends"}


def _normaliser_reponse(texte: str) -> str:
    """Minuscules, sans accents ni ponctuation : Whisper écrit « Oui. », « Oui, vas-y. »,
    alors que seuls « oui » / « non » exacts étaient reconnus (la confirmation expirait)."""
    import re
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFD", texte.lower()) if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _correspond(t: str, mots: set) -> bool:
    return any(t == m or t.startswith(m + " ") for m in mots)


def _historique():
    """Résumé des confirmations passées (journal d'audit) pour le HUD ; None si illisible."""
    try:
        from core.audit_log import resume_confirmations
        return resume_confirmations()
    except Exception:
        return None


def confirmation_en_attente() -> bool:
    return _pending is not None


async def demander_confirmation(websocket, message: str, timeout: float = 20.0, details: list | None = None, question: bool = False) -> bool:
    """Affiche la confirmation au HUD et parle la question ; attend une réponse (maintien de l'hexagone ou voix).

    `details` : liste facultative [{"t": titre, "d": précision}] de ce qui sera supprimé, calculée avant l'action.
    `question` : simple question oui / non qui n'a rien de destructif (installer une appli…) : le HUD l'affiche en bleu avec deux boutons
    au lieu de l'hexagone à maintenir, et rien n'est inscrit au journal d'audit."""
    global _pending

    if _pending is not None and not _pending["future"].done():
        _pending["future"].set_result(False)

    confirm_id = uuid.uuid4().hex
    future = asyncio.get_running_loop().create_future()
    _pending = {"id": confirm_id, "future": future, "strict": not question}

    # Popup sur tous les HUD connectés (une action déclenchée à la voix n'a pas de
    # websocket : sans diffusion, aucun popup ne s'affichait).
    import core.shared as shared
    destinataires = set(shared.CONNECTED_CLIENTS)
    if websocket is not None:
        destinataires.add(websocket)

    resultat = None  # None tant que non résolue (délai écoulé) ; sert au message de fermeture
    try:
        demande = json.dumps({"type": "confirm_request", "id": confirm_id, "message": message,
                              "details": details or [], "timeout": timeout, "historique": None if question else _historique(), "question": bool(question)})
        for ws in destinataires:
            try:
                await ws.send(demande)
            except Exception:
                pass
        # Session vocale ouverte : « oui » / « non » sans redire « Jarvis » (avant, une
        # confirmation demandée depuis le HUD ignorait la réponse vocale sans mot de réveil).
        import time
        shared.jarvis_actif = True
        shared.dernier_message = time.time()
        try:
            import builtins
            builtins.parler(f"{message} Répondez par oui ou par non." if question else f"{message} Dites oui pour confirmer, ou non pour annuler.")
        except Exception:
            pass

        try:
            resultat = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            resultat = None
            if not question:
                consigner("confirmation_timeout", message=message)
            return False
        if not question:
            consigner("confirmation_resolue", message=message, confirme=resultat)
        return resultat
    finally:
        if _pending is not None and _pending["id"] == confirm_id:
            _pending = None
        # Ferme le popup sur tous les HUD (réponse vocale, autre fenêtre ou délai écoulé)
        fermeture = json.dumps({"type": "confirm_closed", "id": confirm_id, "confirmed": resultat})
        for ws in destinataires:
            try:
                await ws.send(fermeture)
            except Exception:
                pass


def resoudre_confirmation(confirm_id: str, confirmed: bool) -> bool:
    """Résout la confirmation en attente depuis un clic HUD. True si elle correspondait."""
    if _pending is None or _pending["id"] != confirm_id:
        return False
    if not _pending["future"].done():
        _pending["future"].set_result(confirmed)
    return True


# --- interprétation stricte (actions destructrices) ---------------------------------------------------------------------------------------------------------
# Une action destructrice n'est confirmée que par un accord NET : « oui mais mets Marie en copie », « oui, non, attends », « c'est bon ? » ne valident rien (dans le doute, on annule).
_ACCORDS = frozenset({"oui", "ouais", "ouep", "ok", "okay", "yes", "confirme", "confirmer", "valide", "valider", "parfait", "carrement", "daccord", "envoie", "fais", "go", "absolument", "exactement", "evidemment", "certainement", "volontiers"})
_ACCORDS_EXPRESSIONS = ("vas y", "allez y", "d accord", "bien sur", "c est bon", "tout a fait", "bien entendu", "je confirme")
_NEGATIONS = frozenset({"non", "nan", "no", "nope", "pas", "ne", "n", "jamais", "rien", "aucun", "aucune", "annule", "annuler", "annulez", "arrete", "arreter", "stop", "cancel", "attends", "attend", "attendez"})
_NEGATIONS_EXPRESSIONS = ("laisse tomber", "plus tard", "je sais pas", "surtout pas", "pas question")
_RESTRICTIONS = frozenset({"mais", "sauf", "plutot", "avant", "apres", "si", "et", "puis", "aussi", "avec", "sans"})   # condition, report ou ajout : pas un accord sans réserve
_INTERROGATIFS = frozenset({"quoi", "comment", "pourquoi", "lequel", "laquelle", "combien", "ou"})
_INTERROGATIFS_EXPRESSIONS = ("qu est ce", "est ce")
_VOCABULAIRE_STRICT = _ACCORDS | frozenset({"vas", "y", "allez", "d", "accord", "bien", "sur", "c", "est", "bon", "ca", "je", "tu", "peux", "le", "la", "les", "l", "maintenant", "tout", "a", "fait", "entendu",
                                            "jarvis", "merci", "s", "il", "te", "vous", "plait", "stp", "svp", "confirme"})


def interpreter_reponse(texte: str, strict: bool = True):
    """Réponse vocale à une confirmation -> True (accord), False (refus) ou None (sans rapport : la phrase suit son cours).

    Mode normal (simple question) : « oui »/« non » en début de phrase, le non l'emportant.
    Mode strict (action destructrice) : tout refus, négation, condition, ajout (« et mets… »), question ou mot hors liste blanche vaut REFUS ; seul un accord net, éventuellement poli, vaut oui."""
    t = " " + _normaliser_reponse(texte) + " "
    t = t.replace(" pas de souci ", " ").replace(" pas de probleme ", " ").replace(" pas de soucis ", " ").replace(" pas de problemes ", " ")   # « oui pas de souci » : formule positive
    mots = t.split()
    if not mots:
        return None
    if not strict:
        n = t.strip()
        if _correspond(n, MOTS_NON):
            return False
        if _correspond(n, MOTS_OUI):
            return True
        return None
    refus = any(m in _NEGATIONS for m in mots) or any(e in t for e in _NEGATIONS_EXPRESSIONS)
    accord = any(m in _ACCORDS for m in mots) or any(e in t for e in _ACCORDS_EXPRESSIONS)
    if refus:
        return False
    if not accord:
        return None   # ni oui ni non : une autre phrase (« quelle heure est-il »)
    if "?" in texte or any(m in _RESTRICTIONS or m in _INTERROGATIFS for m in mots) or any(e in t for e in _INTERROGATIFS_EXPRESSIONS):   # « c'est bon ? » : une question n'est pas un accord
        return False
    if any(m not in _VOCABULAIRE_STRICT for m in mots):
        return False   # « oui, mets Marie en copie » : une demande n'est pas un oui
    return True


def resoudre_confirmation_vocale(texte: str, accord_permis: bool = True) -> bool:
    """Tente de résoudre la confirmation en attente depuis une réponse vocale.

    `accord_permis` : False pour une voix inconnue (invité) : elle peut refuser, jamais accepter. Sans cela, un invité ou une voix de la télé
    qui disait « oui » validait l'action sensible demandée par le créateur.

    Retourne True si le texte a été consommé comme réponse (positive ou
    négative) à la confirmation en attente — dans ce cas l'appelant ne doit
    pas continuer le traitement normal de la commande.
    """
    if _pending is None:
        return False
    strict = bool(_pending.get("strict"))
    decision = interpreter_reponse(texte, strict)
    if decision is None:
        return False
    if strict and decision is False and not any(m in _NEGATIONS for m in _normaliser_reponse(texte).split()) \
            and not any(e in " " + _normaliser_reponse(texte) + " " for e in _NEGATIONS_EXPRESSIONS):
        try:   # un oui assorti d'une condition ou d'une demande : on annule et on le dit
            import builtins
            builtins.parler("Je n'ai pas entendu un oui net, j'annule.")
        except Exception:
            pass
    if decision and not accord_permis:
        print("🔒 [CONFIRMATION] « oui » d'une voix non reconnue ignoré : seul un refus est accepté d'un invité.")
        return True   # consommé, sans valider
    resoudre_confirmation(_pending["id"], bool(decision))
    return True
