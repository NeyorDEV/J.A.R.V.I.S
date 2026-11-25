"""suivi_resolver.py — « où en sont mes colis », « mes factures à payer », « j'ai payé la facture 2 », « active le suivi des colis et factures » (module/suivi_mails.py). Refusé à l'invité (mails privés)."""
import asyncio
import builtins
import json
import re
import threading
import time
import unicodedata
from datetime import datetime

from core.interlocuteur import nom_virgule
from module import suivi_mails as S

_derniere_liste: dict = {"colis": [], "facture": []}   # numérotation de la dernière liste dite
_PERIME_S = 600   # un suivi relu depuis moins de 10 minutes n'est pas relu


def _norm(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower().replace("’", "'")) if unicodedata.category(c) != "Mn")


def _config(valeur=None):
    """Lit (valeur None) ou écrit le réglage `suivi_mails` de jarvis_config.json (chemin de core/i18n)."""
    from core import i18n
    try:
        try:
            with open(i18n._CONFIG, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
        if valeur is None:
            return bool(cfg.get("suivi_mails"))
        cfg["suivi_mails"] = bool(valeur)
        with open(i18n._CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _service():
    from module.briefing import _google_pret
    if not _google_pret():
        return None
    from module.google_services import service_gmail
    return service_gmail()


def _rafraichir(force: bool = False):
    """Relit Gmail si le suivi est périmé. Renvoie True si Gmail était lisible (ou le suivi assez récent), False sinon."""
    d = S.charger()
    if not force and d["maj"] and (datetime.now() - datetime.fromisoformat(d["maj"])).total_seconds() < _PERIME_S:
        return True
    service = _service()
    if not service:
        return False
    S.rafraichir(service)
    return True


async def resoudre_suivi(cmd: str):
    t = _norm(cmd.strip())
    if not re.search(r"\b(?:colis|factures?|echeances?|suivi des (?:mails|colis))\b", t):
        return None
    if re.search(r"\b(?:active|desactive|arrete|coupe)\b.*\bsuivi\b", t):
        actif = not re.search(r"\b(?:desactive|arrete|coupe)\b", t)
        _config(actif)
        return (f"Suivi activé{nom_virgule()} : je relis vos mails toutes les 30 minutes et je vous préviens quand un colis arrive ou qu'une facture approche. "
                "Je ne lis que l'expéditeur, l'objet et le début de chaque mail." if actif else f"Suivi désactivé{nom_virgule()}.")
    force = bool(re.search(r"\b(?:verifie|actualise|mets a jour|relis|rafraichis)\b", t))
    m = re.search(r"\b(colis|facture)\s*(?:numero\s*|n°\s*)?(\d+)\b", t)
    clos = re.search(r"\b(?:paye\w*|arrive\w*|recu\w*|livre\w*)\b", t)
    ignore = re.search(r"\b(?:ignore|oublie|supprime)\b", t)
    if m and (clos or ignore):
        type_, n = m.group(1), int(m.group(2))
        liste = _derniere_liste[type_]
        if not 1 <= n <= len(liste):
            return f"Je n'ai pas de {type_} numéro {n}{nom_virgule()}. Demandez d'abord la liste."
        d = S.charger()
        for i in d["items"]:
            if i["id"] == liste[n - 1]["id"]:
                if ignore:
                    i["ignore"] = True
                else:
                    i["statut"] = "payee" if type_ == "facture" else "livre"
        S.sauver(d)
        return f"C'est noté{nom_virgule()}."
    if not re.search(r"\b(?:colis|factures?|echeances?)\b", t):
        return None
    type_ = "colis" if re.search(r"\bcolis\b", t) else "facture"
    lisible = await asyncio.to_thread(_rafraichir, force)
    d = S.charger()
    liste = S.actifs(d, type_)
    _derniere_liste[type_] = liste
    if not liste:
        if not lisible and not d["items"]:
            return f"Je n'ai pas accès à votre messagerie Google{nom_virgule()} : connectez-vous d'abord."
        return f"Aucun colis à suivre{nom_virgule()}." if type_ == "colis" else f"Aucune facture à suivre{nom_virgule()}."
    aujourdhui = datetime.now().date()
    lignes = [f"{i}. {S.decrire(x, aujourdhui)}" for i, x in enumerate(liste[:6], 1)]
    return (f"{len(liste)} {type_}{'s' if len(liste) > 1 and type_ != 'colis' else ''} à suivre : " + " ; ".join(lignes) + ".") + ("" if lisible else " Attention, je n'ai pas pu relire vos mails, ces informations peuvent être anciennes.")


# ── veille en arrière-plan (activée par « active le suivi des colis et factures ») ──────────────────────────────
def _veiller():
    time.sleep(180)
    while True:
        try:
            if _config() and _rafraichir(force=True):
                maintenant = datetime.now()
                if 8 <= maintenant.hour < 21:
                    with S._VERROU:
                        d = S.charger()
                        phrases = S.alertes(d, maintenant)
                        S.sauver(d)
                    for p in phrases:
                        _annoncer(p)
        except Exception as e:
            print(f"[SUIVI] Erreur : {e}")
        time.sleep(1800)


def _annoncer(phrase: str) -> None:
    import core.shared as shared
    from core.web_bridge import envoyer_carte_contextuelle
    if shared.WS_LOOP is not None:
        asyncio.run_coroutine_threadsafe(envoyer_carte_contextuelle("Suivi", phrase, "info", "◈", 12000), shared.WS_LOOP)
    parler = getattr(builtins, "parler", None)
    if parler:
        parler(phrase, role="alerte")


def demarrer_veille():
    t = threading.Thread(target=_veiller, daemon=True, name="SuiviMails")
    t.start()
    return t


builtins.resoudre_suivi = resoudre_suivi
