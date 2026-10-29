"""Écrans de contenu des catégories du cylindre : ce que JARVIS vient de faire, montré dans l'écran du cylindre.

Quand `module_catalogue.annoncer` annonce une catégorie qui a un écran (Agenda, Mail, Maison, Sécurité > Journal, Télé), le
contenu est construit en arrière-plan (sans retarder la réponse parlée) puis envoyé au HUD par `module_ecran` :
  {"action": "module_ecran", "categorie", "sous", "titre", "sous_titre", "lignes": [{"t", "d", "v", "etat"}], "pied"}
  t = texte principal, d = détail (petit), v = valeur à droite, etat = "on" | "off" | "alerte" (pastille).
Jamais pour une voix inconnue (mode invité) : mails, agenda et état de la maison n'ont pas à s'afficher pour n'importe qui.
Aucune connexion interactive n'est jamais lancée ici (Google : jeton déjà valide ou rafraîchi sans interaction).
"""

import asyncio
import json
import os
import re
import time

import core.shared as shared
from core.web_bridge import _safe_ws_send

_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Catégorie -> sous-catégories qui modifient quelque chose (l'écran attend un instant que l'action soit faite)
_SOUS_MODIFIANTES = {"Ajouter", "Modifier", "Supprimer", "Lumières", "Prises", "Chauffage", "Scènes"}
_ECRANS = {"AGENDA", "MAIL", "MAISON", "SÉCURITÉ", "TÉLÉ"}
_MIN_ENTRE_ECRANS = 3.0   # deux annonces rapprochées (devinette puis précision) ne reconstruisent pas deux fois
_dernier = {"cle": None, "t": 0.0}


def a_un_ecran(categorie, sous):
    if categorie == "SÉCURITÉ":
        return sous == "Journal"
    return categorie in _ECRANS


def declencher(categorie, sous):
    """Lance la construction de l'écran en arrière-plan (appelable depuis n'importe quel thread). Sans effet sinon."""
    if not a_un_ecran(categorie, sous) or getattr(shared, "ACTIVE_SPEAKER", "neyor") == "guest":
        return
    cle = (categorie, sous)
    maintenant = time.time()
    if _dernier["cle"] == cle and maintenant - _dernier["t"] < _MIN_ENTRE_ECRANS:
        return
    _dernier["cle"], _dernier["t"] = cle, maintenant
    if shared.WS_LOOP is None or not shared.CONNECTED_CLIENTS:
        return
    asyncio.run_coroutine_threadsafe(_envoyer(categorie, sous), shared.WS_LOOP)


async def _envoyer(categorie, sous):
    try:
        if sous in _SOUS_MODIFIANTES:
            await asyncio.sleep(1.5)
        ecran = await construire(categorie, sous)
    except Exception as e:
        print(f"[ECRAN] {categorie} : construction impossible : {type(e).__name__} : {e}")
        return
    if ecran:
        _safe_ws_send(json.dumps({"action": "module_ecran", "categorie": categorie, "sous": sous, **ecran}, ensure_ascii=False))


async def construire(categorie, sous):
    """Contenu de l'écran (dict) ou None s'il n'y a rien d'honnête à montrer (service non configuré, injoignable)."""
    if categorie == "AGENDA":
        return await asyncio.to_thread(_agenda)
    if categorie == "MAIL":
        return await asyncio.to_thread(_mails)
    if categorie == "MAISON":
        return await asyncio.to_thread(_maison)
    if categorie == "SÉCURITÉ":
        return await asyncio.to_thread(_journal)
    if categorie == "TÉLÉ":
        return await asyncio.to_thread(_tele)
    return None


# ── Google : jeton valide, rafraîchi sans interaction ──
def google_pret():
    try:
        import pickle
        from google.auth.transport.requests import Request
        from module import google_services as gs
        chemin = os.path.join(_RACINE, "config", "token.pickle")
        if not os.path.exists(chemin):
            return False
        with open(chemin, "rb") as f:
            creds = pickle.load(f)
        if not all(s in (getattr(creds, "scopes", None) or []) for s in gs.SCOPES):
            return False
        if creds.valid:
            return True
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(chemin, "wb") as f:
                pickle.dump(creds, f)
            return True
    except Exception as e:
        print(f"[ECRAN] Google indisponible sans connexion interactive : {type(e).__name__}")
    return False


def _agenda():
    if not google_pret():
        return None
    from datetime import datetime, timezone
    from module import google_services as gs
    service = gs.service_agenda()
    if not service:
        return None
    items = service.events().list(calendarId="primary", timeMin=datetime.now(timezone.utc).isoformat(), maxResults=6,
                                  singleEvents=True, orderBy="startTime").execute().get("items", [])
    lignes = [{"t": e.get("summary", "Sans titre"), "d": gs._date_lisible(e["start"].get("dateTime", e["start"].get("date"))), "v": None, "etat": None} for e in items]
    return {"titre": "AGENDA", "sous_titre": "PROCHAINS ÉVÉNEMENTS", "lignes": lignes or [{"t": "Aucun événement à venir", "d": None, "v": None, "etat": None}], "pied": None}


def _expediteur(brut):
    m = re.match(r'\s*"?([^"<]+?)"?\s*<', brut or "")
    return (m.group(1) if m else (brut or "?")).strip()


def _mails():
    if not google_pret():
        return None
    from module import google_services as gs
    service = gs.service_gmail()
    if not service:
        return None
    non_lus = service.users().labels().get(userId="me", id="INBOX").execute().get("messagesUnread", 0)
    messages = service.users().messages().list(userId="me", maxResults=6, labelIds=["INBOX"], q="is:unread category:primary").execute().get("messages", [])
    lignes = []
    for msg in messages:
        m = service.users().messages().get(userId="me", id=msg["id"], format="metadata", metadataHeaders=["From", "Subject"]).execute()
        h = {x["name"]: x["value"] for x in m["payload"]["headers"]}
        lignes.append({"t": h.get("Subject", "(sans objet)"), "d": _expediteur(h.get("From")), "v": None, "etat": "on"})
    return {"titre": "MAIL", "sous_titre": "NON LUS", "lignes": lignes or [{"t": "Aucun nouveau mail non lu", "d": None, "v": None, "etat": None}],
            "pied": f"{non_lus} non lu(s) dans la boîte de réception"}


def _maison():
    from module import meteo_domotique as md
    md._maj_env_ha()   # relit HA_URL / HA_TOKEN (chargés après l'import du module)
    if not md.ha_active():
        return None
    etats = md.ha_tous_les_etats() or []
    appareils = [e for e in etats if e.get("entity_id", "").startswith(("light.", "switch."))]
    lignes, allumes = [], 0
    for e in appareils[:10]:
        on = e.get("state") == "on"
        allumes += on
        attrs = e.get("attributes", {})
        lum = attrs.get("brightness")
        lignes.append({"t": attrs.get("friendly_name", e["entity_id"]), "d": (f"{round(lum / 255 * 100)} %" if on and lum else None),
                       "v": "ALLUMÉ" if on else "ÉTEINT", "etat": "on" if on else "off"})
    if not lignes:
        return None
    return {"titre": "MAISON", "sous_titre": "LUMIÈRES ET PRISES", "lignes": lignes, "pied": f"{allumes} allumé(s) sur {len(appareils)}"}


_EVENEMENTS = {"skill_execute": "Skill lancé", "skill_approuve": "Skill approuvé", "confirmation_resolue": "Confirmation", "competence_executee": "Compétence lancée"}


def _journal():
    chemin = os.path.join(_RACINE, "jarvis_audit.log")
    if not os.path.exists(chemin):
        return None
    with open(chemin, "rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - 12000))
        brut = f.read().decode("utf-8", "replace").splitlines()
    entrees = []
    for ligne in brut[-10:]:
        try:
            entrees.append(json.loads(ligne))
        except Exception:
            continue
    lignes = []
    for e in reversed(entrees[-8:]):
        nom = e.get("event", "?")
        detail = e.get("skill") or e.get("message") or e.get("nom") or ""
        lignes.append({"t": _EVENEMENTS.get(nom, nom.replace("_", " ").capitalize()), "d": str(detail)[:48] or None, "v": str(e.get("ts", ""))[11:16], "etat": "alerte" if e.get("confirme") is False else None})
    return {"titre": "SÉCURITÉ", "sous_titre": "JOURNAL DES ACTIONS SENSIBLES", "lignes": lignes or [{"t": "Journal vide", "d": None, "v": None, "etat": None}], "pied": None}


_APPS_TELE = {"youtube": "YouTube", "netflix": "Netflix", "disney": "Disney+", "primevideo": "Prime Video", "amazon": "Prime Video", "spotify": "Spotify",
              "launcher": "Accueil", "tvlauncher": "Accueil", "settings": "Réglages", "twitch": "Twitch", "plex": "Plex"}


def _tele():
    """État de la télé par ADB (lecture seule). Éteinte ou hors réseau : on le dit, sans rien tenter d'autre."""
    from plugins import tv_resolver as tv
    ligne_etat = {"t": "Télé", "d": None, "v": "INJOIGNABLE", "etat": "off"}
    device = None
    try:
        device = tv.AdbDeviceTcp(tv._tv_ip(), 5555, default_transport_timeout_s=3)
        device.connect(rsa_keys=[tv.get_adb_signer()], auth_timeout_s=3)
        reveillee = "Awake" in (device.shell("dumpsys power | grep -m1 mWakefulness=") or "")
        focus = device.shell("dumpsys window | grep -m1 mCurrentFocus") or ""
        m = re.search(r"u0 ([\w.]+)/", focus)
        paquet = m.group(1) if m else ""
        appli = next((nom for cle, nom in _APPS_TELE.items() if cle in paquet.lower()), paquet.split(".")[-1].capitalize() if paquet else None)
        lignes = [{"t": "Télé", "d": None, "v": "ALLUMÉE" if reveillee else "EN VEILLE", "etat": "on" if reveillee else "off"}]
        if reveillee and appli:
            lignes.append({"t": "Application", "d": None, "v": appli.upper(), "etat": None})
        return {"titre": "TÉLÉ", "sous_titre": "ÉTAT DE LA TÉLÉ", "lignes": lignes, "pied": None}
    except Exception as e:
        print(f"[ECRAN] Télé injoignable : {type(e).__name__}")
        return {"titre": "TÉLÉ", "sous_titre": "ÉTAT DE LA TÉLÉ", "lignes": [ligne_etat], "pied": "Éteinte ou hors réseau"}
    finally:
        if device is not None:
            try:
                device.close()
            except Exception:
                pass
