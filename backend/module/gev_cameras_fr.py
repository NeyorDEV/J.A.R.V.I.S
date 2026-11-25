"""Caméras françaises pour God's Eye View (Vue de Dieu) : un « pack de sources » personnalisé, sans toucher à l'appli.

God's Eye View charge, en plus de ses caméras intégrées, un fichier JSON de caméras (variable CCTV_SOURCES_FILE). Ce module construit ce fichier
à partir de données OUVERTES, sans clé :

  Métropole de Lyon — « Caméras Web Criter » (Licence Ouverte 2.0), 15 caméras, une image par minute.
      catalogue : service WFS data.grandlyon.com (coordonnées + identifiant) ; image : download.data.grandlyon.com/files/rdata/.../<identifiant>.JPG
  Windy Webcams (clé gratuite WINDY_WEBCAMS_API_KEY) — webcams d'une zone, actives ou non (une inactive est gardée : le relais ne sert son image qu'une fois active) (module/windy_relais.py : 50 km autour de Saint-Étienne par défaut) ;
      leurs images passent par un relais local (127.0.0.1) car les adresses de l'API expirent en 10 à 15 minutes.

Le fichier est refait au plus une fois par jour (en tâche de fond) ; sans réseau, l'ancien fichier est gardé. Les images ne sont jamais copiées :
God's Eye View les télécharge lui-même, une à une, depuis les adresses officielles.
Ajouter une source = une fonction `_source_xxx()` qui renvoie une liste de dictionnaires, ajoutée à SOURCES.
Voir docs/fr/VUE_DE_DIEU.md. Test sans réseau : scratch/outils_test/test_gev_cameras_fr.py.
"""

import json
import os
import threading
import time

import requests

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FICHIER = os.path.join(RACINE, "data", "gods_eye_view", "cameras_france.json")
VALIDITE_S = 24 * 3600
UA = {"User-Agent": "JARVIS-Assistant/1.0 (personal use)"}

_verrou = threading.Lock()
_en_cours = {"actif": False}

LYON_WFS = "https://data.grandlyon.com/geoserver/metropole-de-lyon/ows"
LYON_IMAGE = "https://download.data.grandlyon.com/files/rdata/pvo_patrimoine_voirie.pvocameracriter/{numero}.JPG"
LYON_LICENCE = "Licence Ouverte 2.0 — Métropole de Lyon (data.grandlyon.com), caméras Web Criter."


def _source_lyon(timeout: float = 15.0) -> list:
    r = requests.get(LYON_WFS, headers=UA, timeout=timeout, params={
        "SERVICE": "WFS", "VERSION": "2.0.0", "request": "GetFeature", "typename": "metropole-de-lyon:pvo_patrimoine_voirie.pvocameracriter",
        "outputFormat": "application/json", "SRSNAME": "EPSG:4326"})
    r.raise_for_status()
    sortie = []
    for f in r.json().get("features", []):
        p = f.get("properties") or {}
        coord = (f.get("geometry") or {}).get("coordinates") or []
        numero = str(p.get("numeromaintenance") or "").strip()
        if not numero or len(coord) < 2:
            continue
        lieu = str(p.get("libellelong") or "").strip()
        nom = str(p.get("nom") or numero).strip()
        url = LYON_IMAGE.format(numero=numero)
        sortie.append({
            "id": f"lyon-criter-{numero.lower()}", "name": f"{nom} · {lieu}" if lieu else nom, "city": "Lyon", "provider": "Métropole de Lyon",
            "credit": "Métropole de Lyon", "sourceKind": "municipal-webcam", "feedType": "image", "url": url, "snapshotUrl": url,
            "lat": float(coord[1]), "lon": float(coord[0]), "pitchDeg": -20, "fovDeg": 70, "mountHeightM": 8, "license": LYON_LICENCE,
        })
    return sortie


def _source_windy(timeout: float = 15.0) -> list:
    from module import windy_relais
    if not windy_relais.disponible():
        return []
    sortie = []
    for info in windy_relais.charger(forcer=True, timeout=timeout).values():
        sortie.append({
            "id": f"windy-{info['id']}", "name": info["title"] or f"Webcam {info['id']}", "city": info["city"], "provider": "Windy.com",
            "credit": "Webcams provided by windy.com", "sourceKind": "windy-webcam", "feedType": "image",
            "url": windy_relais.url_relais(info["id"]), "snapshotUrl": windy_relais.url_relais(info["id"]),
            "lat": float(info["lat"]), "lon": float(info["lon"]), "pitchDeg": -15, "fovDeg": 70, "mountHeightM": 10,
            "license": "Images des exploitants des webcams, via l'API Windy Webcams (usage personnel). Webcams provided by windy.com. Page : " + info["page"],
        })
    return sortie


SOURCES = [("lyon", _source_lyon), ("windy", _source_windy)]


def construire(timeout: float = 15.0) -> list:
    """Toutes les caméras des sources ; une source en panne est ignorée (les autres restent)."""
    cameras = []
    for nom, fonction in SOURCES:
        try:
            cameras.extend(fonction(timeout))
        except Exception as e:  # noqa: BLE001 : réseau, format : on garde les autres sources
            print(f"[CAMERAS FR] Source {nom} indisponible : {type(e).__name__}")
    ids = set()
    return [c for c in cameras if not (c["id"] in ids or ids.add(c["id"]))]


def _ecrire(cameras: list) -> None:
    os.makedirs(os.path.dirname(FICHIER), exist_ok=True)
    tmp = FICHIER + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cameras, f, ensure_ascii=False, indent=1)
    os.replace(tmp, FICHIER)


def _age_s() -> float:
    try:
        return time.time() - os.path.getmtime(FICHIER)
    except OSError:
        return float("inf")


def rafraichir(timeout: float = 15.0) -> bool:
    """Refait le fichier ; sans caméra reçue, l'ancien est gardé. Renvoie True si le fichier a été remplacé."""
    with _verrou:
        cameras = construire(timeout)
        if not cameras:
            return False
        _ecrire(cameras)
        print(f"[CAMERAS FR] {len(cameras)} caméras écrites")
        return True


def _manque_windy() -> bool:
    """La clé Windy existe mais le fichier actuel n'a aucune webcam Windy (clé ajoutée après sa dernière fabrication)."""
    from module import windy_relais
    if not windy_relais.disponible():
        return False
    try:
        with open(FICHIER, encoding="utf-8") as f:
            return not any(str(c.get("id", "")).startswith("windy-") for c in json.load(f))
    except (OSError, ValueError):
        return True


def preparer() -> dict:
    """À appeler juste avant de lancer le serveur de God's Eye View. Renvoie les variables d'environnement à lui donner (vide si aucun fichier).
    Pas de fichier : un essai rapide (8 s) tout de suite ; fichier vieux de plus d'un jour : rafraîchi en tâche de fond."""
    try:   # le relais Windy tourne tant que JARVIS tourne (il ne sert que les webcams de la zone chargée)
        from module import windy_relais
        if windy_relais.disponible():
            windy_relais.demarrer_relais()
    except Exception as e:  # noqa: BLE001
        print(f"[CAMERAS FR] Relais Windy indisponible : {type(e).__name__}")
    if not os.path.isfile(FICHIER) or _manque_windy():
        rafraichir(timeout=12.0)
    elif _age_s() > VALIDITE_S and not _en_cours["actif"]:
        _en_cours["actif"] = True

        def _fond():
            try:
                rafraichir()
            finally:
                _en_cours["actif"] = False
        threading.Thread(target=_fond, daemon=True).start()
    if not os.path.isfile(FICHIER):
        return {}
    # CCTV_FORCE_AUSTIN=1 : sans lui, God's Eye View ne charge QUE ce fichier et abandonne ses caméras intégrées (Tallinn, Londres, Sydney…)
    return {"CCTV_SOURCES_FILE": FICHIER, "CCTV_FORCE_AUSTIN": "1"}
