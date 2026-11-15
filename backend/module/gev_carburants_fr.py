"""Prix des carburants en France pour God's Eye View (Vue de Dieu), sans toucher à l'appli.

Source : « Prix des carburants en France, flux instantané » (data.economie.gouv.fr, Opendatasoft, sans clé, Licence Ouverte 2.0 : ministère de l'Économie), ~10 000 stations,
mis à jour toutes les 10 minutes. Le fichier `data/gods_eye_view/carburants_france.json` est refait au plus toutes les 30 minutes, EN TÂCHE DE FOND ; sans réseau, l'ancien est gardé.
Il est servi à la page par le plugin `jarvisCouches` de module/vue_de_dieu.py, que lit la couche « Fuel prices · France » de module/gev_couches.js.

Format : liste de [identifiant, latitude, longitude, adresse (avec code postal et ville), [gazole, sp95, e10, sp98, e85, gplc] (€/L, null si la station n'en vend pas), dernière mise à jour
(AAAA-MM-JJ hh:mm, la plus récente des prix), type de route (« R » route, « A » autoroute)]. Test : scratch/outils_test/test_gev_carburants_fr.py.
"""

import json
import math
import os
import threading
import time

import requests

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FICHIER = os.path.join(RACINE, "data", "gods_eye_view", "carburants_france.json")
VALIDITE_S = 30 * 60
URL = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/prix-des-carburants-en-france-flux-instantane-v2/exports/json"
CHAMPS = "id,geom,adresse,ville,cp,pop,gazole_prix,sp95_prix,e10_prix,sp98_prix,e85_prix,gplc_prix,gazole_maj,sp95_maj,e10_maj,sp98_maj,e85_maj,gplc_maj"
ENTETES = {"User-Agent": "JARVIS-Assistant/1.0 (personal use)", "Accept": "application/json"}
_verrou = threading.Lock()
_en_cours = {"actif": False}


def _prix(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return round(x, 3) if 0.3 < x < 5 and math.isfinite(x) else None   # une valeur hors de ces bornes est une erreur de saisie de la station


def convertir(liste: list) -> list:
    """Enregistrements de l'API -> liste compacte ; ignore tout ce qui n'a pas de position valide en France (métropole et outre-mer) ni de prix."""
    sortie = []
    for r in liste or []:
        try:
            g = r.get("geom") or {}
            lat, lon = float(g["lat"]), float(g["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (-23 < lat < 52 and -63 < lon < 56):
            continue
        prix = [_prix(r.get(k + "_prix")) for k in ("gazole", "sp95", "e10", "sp98", "e85", "gplc")]
        if not any(prix):
            continue
        maj = max((str(r.get(k + "_maj") or "")[:16].replace("T", " ") for k in ("gazole", "sp95", "e10", "sp98", "e85", "gplc") if r.get(k + "_maj")), default="")
        adresse = ", ".join(x for x in (str(r.get("adresse") or "").strip(), (str(r.get("cp") or "") + " " + str(r.get("ville") or "")).strip()) if x)
        sortie.append([str(r.get("id")), round(lat, 5), round(lon, 5), adresse[:120], prix, maj, "A" if r.get("pop") == "A" else "R"])
    return sortie


def rafraichir() -> bool:
    """Télécharge et écrit le fichier. Renvoie True si réussi ; sinon l'ancien fichier est gardé."""
    try:
        r = requests.get(URL, params={"select": CHAMPS}, headers=ENTETES, timeout=120)
        r.raise_for_status()
        donnees = convertir(r.json())
        if len(donnees) < 3000:   # un fichier tronqué ne doit pas remplacer un bon
            return False
        os.makedirs(os.path.dirname(FICHIER), exist_ok=True)
        tmp = FICHIER + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(donnees, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, FICHIER)
        return True
    except Exception as e:  # noqa: BLE001 : jamais bloquant pour la vue
        print(f"[CARBURANTS FR] Mise à jour impossible : {type(e).__name__}")
        return False


def preparer() -> dict:
    """Lance la mise à jour en tâche de fond si le fichier manque ou a plus de 30 minutes ; renvoie les variables d'environnement pour le serveur de la vue."""
    def tache():
        try:
            rafraichir()
        finally:
            _en_cours["actif"] = False
    with _verrou:
        vieux = not os.path.isfile(FICHIER) or time.time() - os.path.getmtime(FICHIER) > VALIDITE_S
        if vieux and not _en_cours["actif"]:
            _en_cours["actif"] = True
            threading.Thread(target=tache, daemon=True, name="carburants-fr").start()
    return {"JARVIS_CARBURANTS_FILE": FICHIER}
