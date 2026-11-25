"""Suivi des colis et des factures dans la boîte Gmail : « où en sont mes colis », « quelles factures j'ai à payer », alertes à l'arrivée et à l'échéance.

Vie privée : seuls l'expéditeur, l'objet et l'extrait de quelques mots que Gmail fournit sont lus (jamais le corps du mail) ; tout est analysé ICI par des règles, rien n'est envoyé à une IA.
Les 14 derniers jours sont parcourus ; le résultat est gardé dans data/suivi.json (type, expéditeur, date visée, montant, numéro de suivi, id du mail).
La lecture de Gmail ne se fait que si le jeton Google est utilisable sans fenêtre de connexion (comme le briefing) ; la surveillance en arrière-plan est à activer (« active le suivi des colis et factures »).
Pur sauf lire_mails / stockage (tests/test_suivi_mails.py : faux service Gmail, dossier temporaire).
"""
import json
import os
import re
import threading
import unicodedata
from datetime import date, datetime, timedelta

_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FICHIER = os.path.join(_RACINE, "data", "suivi.json")
_VERROU = threading.RLock()
JOURS_LUS = 14
GARDER_JOURS = 30
MAX_MAILS = 40
REQUETE = (f"newer_than:{JOURS_LUS}d (colis OR livraison OR livré OR expédié OR expédition OR suivi OR \"point relais\" OR facture OR échéance OR prélèvement OR \"à régler\")")
_MOIS = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre", "octobre", "novembre", "decembre"]
_TRANSPORTEURS = {"colissimo": "Colissimo", "chronopost": "Chronopost", "la poste": "La Poste", "ups": "UPS", "dhl": "DHL", "fedex": "FedEx", "mondial relay": "Mondial Relay",
                  "relais colis": "Relais Colis", "amazon": "Amazon", "gls": "GLS", "dpd": "DPD", "vinted": "Vinted", "cdiscount": "Cdiscount", "fnac": "Fnac",
                  "colis prive": "Colis Privé", "packlink": "Packlink", "boxtal": "Boxtal", "lpd": "LPD", "geodis": "Geodis", "tnt": "TNT"}

_COLIS_FORT = re.compile(r"\b(?:votre colis|votre commande (?:a ete |est )?(?:expediee|en cours de livraison|en route|livree|prete)|en cours de livraison|sera livre|livraison prevue|"
                         r"livraison estimee|a ete expedie\w*|a ete livre\w*|est livre\w*|est disponible (?:en|au) (?:point|relais)|disponible en point relais|numero de suivi|suivre votre colis|"
                         r"colis (?:arrive|est arrive|est en route)|en cours d'acheminement|pret a etre retire|a retirer)\b")
_LIVRE = re.compile(r"\b(?:a ete livre\w*|est livre\w*|livraison effectuee|colis livre|a ete depose\w*|a ete retire\w*|a (?:bien )?ete recupere\w*)\b")
_RELAIS = re.compile(r"\b(?:disponible (?:en|au) (?:point|relais|magasin|boutique|agence)|point relais|pret a etre retire|a retirer|a recuperer)\b")
_FACTURE = re.compile(r"\b(?:facture|avis d'echeance|echeance|prelevement|a regler|montant a payer|date limite de paiement|rappel de paiement|avis de prelevement)\b")
_PAYEE = re.compile(r"\b(?:payee|reglee|paiement (?:recu|accepte|effectue)|merci pour votre paiement|prelevement effectue|recu de paiement|acquittee|facture de (?:la |votre )?commande)\b")
_PROMO = re.compile(r"\b(?:offerte?|gratuite?|promo\w*|soldes?|code|bon plan|-\s?\d+ ?%|jusqu'a -|vente flash|newsletter)\b")
_SUIVI = re.compile(r"\b(?:[A-Z]{2}\d{9}[A-Z]{2}|1Z[0-9A-Z]{16}|\d{12,20}|\d[A-Z]\d{11,13})\b")
_MONTANT = re.compile(r"(\d{1,3}(?:[  .]\d{3})*(?:[,.]\d{2})|\d+(?:[,.]\d{2})?)\s*(?:€|(?:euros?|eur)\b)", re.IGNORECASE)


def norm(t: str) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower().replace("’", "'")) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


def transporteur(sender: str, t: str) -> str:
    for cle in sorted(_TRANSPORTEURS, key=len, reverse=True):
        if re.search(r"(?<![a-z])" + re.escape(cle) + r"(?![a-z])", sender) or re.search(r"(?<![a-z])" + re.escape(cle) + r"(?![a-z])", t):
            return _TRANSPORTEURS[cle]
    return ""


def emetteur(de: str) -> str:
    """Nom affiché de l'expéditeur : « EDF <noreply@edf.fr> » -> « EDF » ; à défaut le domaine."""
    m = re.match(r'\s*"?([^"<]+?)"?\s*<', de or "")
    nom = m.group(1).strip() if m else ""
    if not nom:
        mail = re.search(r"@([\w.-]+)", de or "")
        nom = mail.group(1).split(".")[0].capitalize() if mail else (de or "").strip()
    return nom[:40]


def date_visee(t: str, reference: date):
    """Première date citée dans le texte normalisé : aujourd'hui, demain, « 27 novembre », « 27/11 », « 27/11/2026 »."""
    if re.search(r"\b(?:aujourd'hui|ce jour|ce matin|ce soir|cet apres[- ]midi)\b", t):
        return reference
    if re.search(r"\bdemain\b", t):
        return reference + timedelta(days=1)
    m = re.search(r"\b(\d{1,2})(?:er)?\s+(" + "|".join(_MOIS) + r")(?:\s+(\d{4}))?\b", t)
    if m:
        annee = int(m.group(3)) if m.group(3) else reference.year
        try:
            d = date(annee, _MOIS.index(m.group(2)) + 1, int(m.group(1)))
        except ValueError:
            return None
        return d if m.group(3) or d >= reference - timedelta(days=60) else date(annee + 1, d.month, d.day)
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", t)
    if m:
        annee = int(m.group(3)) + (2000 if m.group(3) and len(m.group(3)) == 2 else 0) if m.group(3) else reference.year
        try:
            return date(annee, int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def classer(sujet: str, de: str, extrait: str, recu: datetime):
    """Mail -> {'type': 'colis'|'facture', ...} ou None (promotion, newsletter, autre). Aucune lecture du corps."""
    t = norm(f"{sujet} {extrait}")
    sender = norm(de)
    ref = recu.date()
    base = {"emetteur": emetteur(de), "objet": str(sujet or "")[:90], "recu": recu.isoformat(timespec="minutes")}
    if _COLIS_FORT.search(t) and not (_PROMO.search(norm(sujet)) and not re.search(r"\b(?:votre colis|votre commande)\b", t)):
        suivi = _SUIVI.search(f"{sujet} {extrait}")
        statut = "livre" if _LIVRE.search(t) else "relais" if _RELAIS.search(t) else "en_route"
        d = date_visee(t, ref)
        return dict(base, type="colis", statut=statut, transporteur=transporteur(sender, t), suivi=suivi.group(0) if suivi else "", date=d.isoformat() if d else "")
    if _FACTURE.search(t) and not (_PROMO.search(norm(sujet)) and not _MONTANT.search(t)):
        m = _MONTANT.search(f"{sujet} {extrait}")
        zone = re.search(r"(?:avant le|au plus tard le|echeance(?: le)?|prelevement(?: le)?|a regler(?: avant le)?|date limite[^0-9a-z]*|le)\s+(.{0,25})", t)
        d = date_visee(zone.group(1), ref) if zone else date_visee(t, ref)
        statut = "payee" if _PAYEE.search(t) else "a_payer"
        return dict(base, type="facture", statut=statut, montant=m.group(1).replace(" ", " ") if m else "", date=d.isoformat() if d else "")
    return None


# ── stockage ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def charger() -> dict:
    with _VERROU:
        try:
            with open(FICHIER, encoding="utf-8") as f:
                d = json.load(f)
            return {"items": list(d.get("items", [])), "maj": d.get("maj", "")}
        except Exception:
            return {"items": [], "maj": ""}


def sauver(d: dict) -> None:
    with _VERROU:
        os.makedirs(os.path.dirname(FICHIER), exist_ok=True)
        tmp = FICHIER + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        os.replace(tmp, FICHIER)


def fusionner(d: dict, nouveaux: list, maintenant: datetime) -> int:
    """Ajoute les nouveaux éléments (par id de mail), clôt les colis livrés et les factures payées qui leur correspondent, oublie les vieux. Renvoie le nombre d'ajouts."""
    connus = {i["id"] for i in d["items"]}
    ajouts = [n for n in nouveaux if n["id"] not in connus]
    d["items"].extend(ajouts)
    for n in sorted(ajouts, key=lambda x: x["recu"]):
        if n["type"] == "colis" and n["statut"] == "livre":
            for i in d["items"]:
                if i["type"] == "colis" and i["statut"] != "livre" and i["id"] != n["id"] and i["recu"] <= n["recu"] \
                        and ((n["suivi"] and i["suivi"] == n["suivi"]) or (not n["suivi"] and not i["suivi"] and i["emetteur"] == n["emetteur"]) or (not n["suivi"] and i["transporteur"] and i["transporteur"] == n["transporteur"])):
                    i["statut"] = "livre"
        if n["type"] == "facture" and n["statut"] == "payee":
            for i in d["items"]:
                if i["type"] == "facture" and i["statut"] == "a_payer" and i["emetteur"] == n["emetteur"] and i["recu"] <= n["recu"]:
                    i["statut"] = "payee"
    limite = (maintenant - timedelta(days=GARDER_JOURS)).isoformat(timespec="minutes")
    d["items"] = [i for i in d["items"] if i["recu"] >= limite]
    d["maj"] = maintenant.isoformat(timespec="seconds")
    return len(ajouts)


def lire_mails(service, maintenant: datetime) -> list:
    """Éléments (colis / factures) trouvés dans Gmail : en-têtes et extrait seulement. `service` : client Gmail déjà construit."""
    liste = service.users().messages().list(userId="me", q=REQUETE, maxResults=MAX_MAILS).execute().get("messages", [])
    sortie = []
    for m in liste:
        try:
            msg = service.users().messages().get(userId="me", id=m["id"], format="metadata", metadataHeaders=["From", "Subject"]).execute()
            en_tetes = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
            recu = datetime.fromtimestamp(int(msg.get("internalDate", 0)) / 1000) if msg.get("internalDate") else maintenant
            r = classer(en_tetes.get("subject", ""), en_tetes.get("from", ""), msg.get("snippet", ""), recu)
            if r:
                sortie.append(dict(r, id=m["id"]))
        except Exception as e:
            print(f"[SUIVI] Mail ignoré ({type(e).__name__})")
    return sortie


def actifs(d: dict, type_: str) -> list:
    """Éléments à suivre : colis pas encore livrés, factures pas encore payées ; les plus proches d'abord (sans date : à la fin)."""
    ferme = "livre" if type_ == "colis" else "payee"
    items = [i for i in d["items"] if i["type"] == type_ and i["statut"] != ferme and not i.get("ignore")]
    return sorted(items, key=lambda i: (i["date"] or "9999", i["recu"]))


def decrire(i: dict, aujourdhui: date) -> str:
    quand = ""
    if i.get("date"):
        jours = (date.fromisoformat(i["date"]) - aujourdhui).days
        quand = {0: "aujourd'hui", 1: "demain", -1: "hier"}.get(jours) or (f"dans {jours} jours" if jours > 1 else f"en retard de {-jours} jours")
    if i["type"] == "colis":
        nom = i["transporteur"] or i["emetteur"]
        etat = "à retirer en point relais" if i["statut"] == "relais" else "en route"
        return f"colis {nom}, {etat}" + (f", prévu {quand}" if quand else "")
    return f"facture {i['emetteur']}" + (f" de {i['montant']} euros" if i.get("montant") else "") + (f", à régler {quand}" if quand else "")


def alertes(d: dict, maintenant: datetime, marquer: bool = True) -> list:
    """Phrases à dire maintenant : colis prévu aujourd'hui ou à retirer, facture due dans 3 jours ou moins (ou en retard). Une alerte par élément et par jour."""
    aujourdhui, sortie = maintenant.date(), []
    for i in actifs(d, "colis") + actifs(d, "facture"):
        if i.get("alerte") == aujourdhui.isoformat():
            continue
        jours = (date.fromisoformat(i["date"]) - aujourdhui).days if i.get("date") else None
        if i["type"] == "colis" and (i["statut"] == "relais" or jours == 0):
            texte = f"Votre {decrire(i, aujourdhui)}."
        elif i["type"] == "facture" and jours is not None and jours <= 3:
            texte = f"Pensez à la {decrire(i, aujourdhui)}."
        else:
            continue
        sortie.append(texte[0].upper() + texte[1:])
        if marquer:
            i["alerte"] = aujourdhui.isoformat()
    return sortie


def rafraichir(service, maintenant: datetime | None = None) -> int:
    """Relit Gmail et met à jour data/suivi.json. Renvoie le nombre de nouveaux éléments."""
    maintenant = maintenant or datetime.now()
    nouveaux = lire_mails(service, maintenant)
    with _VERROU:
        d = charger()
        n = fusionner(d, nouveaux, maintenant)
        sauver(d)
    return n
