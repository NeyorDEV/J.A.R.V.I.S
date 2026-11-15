"""Radar de pluie français (Météo-France) pour God's Eye View (Vue de Dieu), sans toucher à l'appli.

Source : API « Données radar » de Météo-France (portail-api.meteofrance.fr, clé gratuite dans .env : METEOFRANCE_API_KEY), mosaïque France métropolitaine,
« lame d'eau » au pas de 500 m, une image toutes les 5 minutes (fichier HDF5 ODIM : cumul de pluie sur 5 minutes en mm, projection stéréographique polaire).
Le fichier est converti en équivalent dBZ (relation de Marshall-Palmer, Z = 200 R^1.6 : la réflectivité brute n'est livrée qu'en BUFR à tables locales, illisible
sans leurs tables), reprojeté sur une grille longitude / latitude (-12..12, 40..52, 4096 x 2048, ratio 2:1 comme le veut la couche) et gardé sur disque (13 images au plus).
Un petit serveur local (127.0.0.1) rend à la demande une image ou une tuile PNG pour n'importe quelle fenêtre : le plugin « jarvisMeteosat » de module/vue_de_dieu.py
(produit « radar-france » de la couche « Rain radar ») lui parle comme il parlerait à un service WMS.
Licence : Licence Ouverte Etalab 2.0, crédit « Source : Météo-France ». Test : scratch/outils_test/test_gev_radar_fr_reel.py.
"""

import gzip
import io
import json
import math
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np
import requests

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOSSIER = os.path.join(RACINE, "data", "gods_eye_view", "radar_fr")
PORT = int(os.environ.get("JARVIS_RADAR_FR_PORT", "8767"))
API = "https://public-api.meteofrance.fr/public/DPRadar/v1/mosaiques/METROPOLE/observations/LAME_D_EAU"
ENTETES = {"User-Agent": "JARVIS-Assistant/1.0 (personal use)"}
LIMITES = {"west": -12.0, "south": 40.0, "east": 12.0, "north": 52.0}   # 2:1, couvre la métropole et la Corse
LARGEUR, HAUTEUR = 4096, 2048
GARDER = 13
PERIODE_S = 150
# bandes de la légende de la couche (dBZ -> couleur), identiques à celles du radar américain ; en dessous de 10 dBZ : transparent
BANDES = [(10, "00ecec"), (20, "0000f6"), (30, "00c800"), (40, "ffff00"), (50, "ff9000"), (60, "dc0000"), (70, "ff00ff"), (80, "05ede0")]
_verrou = threading.Lock()
_images = {}          # heure ISO -> pyramide de grilles (cache mémoire, 3 au plus)
_etat = {"serveur": None, "stop": threading.Event(), "fil": None, "derniere_erreur": ""}


def cle() -> str:
    from module import gev_cles   # .env de God's Eye View (panneau POWER UP), puis environnement de JARVIS
    return gev_cles.lire("METEOFRANCE_API_KEY")


# --- projection stéréographique polaire (ellipsoïde WGS84, latitude vraie 45°, méridien 0°), celle du fichier -------------------------------------------------------
_A, _E = 6378137.0, math.sqrt(0.0066943799901413165)


def _t(phi):
    s = np.sin(phi)
    return np.tan(np.pi / 4 - phi / 2) / ((1 - _E * s) / (1 + _E * s)) ** (_E / 2)


def _m(phi):
    return np.cos(phi) / np.sqrt(1 - (_E * np.sin(phi)) ** 2)


def projeter(lat, lon, x0=619652.07, y0=5262818.34):
    """(lat, lon) en degrés -> (X, Y) en mètres dans le repère de la mosaïque (origine en bas à gauche)."""
    phi, lam, phic = np.radians(lat), np.radians(lon), math.radians(45.0)
    rho = _A * float(_m(phic)) * _t(phi) / float(_t(phic))
    return rho * np.sin(lam) + x0, -rho * np.cos(lam) + y0


# --- lecture du fichier HDF5 et conversion ---------------------------------------------------------------------------------------------------------------------------
def lire_hdf(octets: bytes):
    """Fichier ODIM HDF5 de la lame d'eau -> (heure ISO de fin d'observation, grille uint8 de la pyramide L0 en codes dBZ x 2, 0 = rien)."""
    import h5py
    with h5py.File(io.BytesIO(octets), "r") as f:
        quoi = f["dataset1/what"].attrs
        fin = datetime.strptime(quoi["enddate"].decode() + quoi["endtime"].decode(), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        d = f["dataset1/data1/what"].attrs
        brut = f["dataset1/data1/data"][...]
        gain, offset, nodata, undetect = float(d["gain"]), float(d["offset"]), float(d["nodata"]), float(d["undetect"])
        taille = int(f["where"].attrs["xscale"])
        if taille != 500 or brut.shape != (3472, 3472) or d["quantity"].decode() != "ACRR":
            raise ValueError("format de mosaïque inattendu")
    mm = brut.astype(np.float32) * gain + offset                     # cumul sur 5 minutes
    mm[(brut == nodata) | (brut == undetect)] = 0.0
    taux = mm * 12.0                                                 # mm/h
    with np.errstate(divide="ignore"):
        dbz = 10.0 * np.log10(200.0 * np.power(taux, 1.6))
    dbz[~np.isfinite(dbz)] = 0.0
    code = np.clip(np.rint(dbz * 2.0), 0, 255).astype(np.uint8)      # 0 à 127 dBZ par pas de 0,5
    code[dbz < 10.0] = 0
    return fin.strftime("%Y-%m-%dT%H:%M:%S.000Z"), _regrille(code)


def _regrille(code: np.ndarray) -> np.ndarray:
    """Grille de la mosaïque (lignes du nord au sud, pixels de 500 m) -> grille longitude / latitude LARGEUR x HAUTEUR (plus proche voisin)."""
    lon = LIMITES["west"] + (np.arange(LARGEUR) + 0.5) * (LIMITES["east"] - LIMITES["west"]) / LARGEUR
    lat = LIMITES["north"] - (np.arange(HAUTEUR) + 0.5) * (LIMITES["north"] - LIMITES["south"]) / HAUTEUR
    LON, LAT = np.meshgrid(lon, lat)
    X, Y = projeter(LAT, LON)
    col = np.floor(X / 500.0).astype(np.int32)
    lig = np.floor((3472 * 500.0 - Y) / 500.0).astype(np.int32)
    dedans = (col >= 0) & (col < 3472) & (lig >= 0) & (lig < 3472)
    sortie = np.zeros((HAUTEUR, LARGEUR), np.uint8)
    sortie[dedans] = code[lig[dedans], col[dedans]]
    return sortie


def _pyramide(g0: np.ndarray) -> list:
    """Niveaux de plus en plus grossiers (maximum de 2 x 2) : une fenêtre dézoomée garde les petites cellules au lieu de les perdre."""
    niveaux = [g0]
    while niveaux[-1].shape[1] > 256:
        g = niveaux[-1]
        niveaux.append(g.reshape(g.shape[0] // 2, 2, g.shape[1] // 2, 2).max(axis=(1, 3)))
    return niveaux


# --- images et tuiles -------------------------------------------------------------------------------------------------------------------------------------------------
def _palette() -> np.ndarray:
    lut = np.zeros((256, 4), np.uint8)
    for code in range(256):
        dbz = code / 2.0
        couleur = None
        for seuil, hexa in BANDES:
            if dbz >= seuil:
                couleur = hexa
        if code and couleur:
            lut[code] = (int(couleur[0:2], 16), int(couleur[2:4], 16), int(couleur[4:6], 16), 255)
    return lut


_LUT = _palette()


def rendre(pyramide: list, fenetre: tuple, largeur: int, hauteur: int) -> bytes:
    """PNG RGBA de la fenêtre (ouest, sud, est, nord) en degrés, largeur x hauteur ; transparent hors de la mosaïque."""
    from PIL import Image
    ouest, sud, est, nord = fenetre
    lon = ouest + (np.arange(largeur) + 0.5) * (est - ouest) / largeur
    lat = nord - (np.arange(hauteur) + 0.5) * (nord - sud) / hauteur
    px_sortie = (est - ouest) / largeur                                  # degrés par pixel demandé
    px_source = (LIMITES["east"] - LIMITES["west"]) / LARGEUR
    niveau = 0
    while niveau + 1 < len(pyramide) and px_source * 2 ** (niveau + 1) <= px_sortie * 1.0001:
        niveau += 1
    g = pyramide[niveau]
    h, w = g.shape
    col = np.floor((lon - LIMITES["west"]) / (LIMITES["east"] - LIMITES["west"]) * w).astype(np.int64)
    lig = np.floor((LIMITES["north"] - lat) / (LIMITES["north"] - LIMITES["south"]) * h).astype(np.int64)
    bon_c, bon_l = (col >= 0) & (col < w), (lig >= 0) & (lig < h)
    codes = np.zeros((hauteur, largeur), np.uint8)
    if bon_c.any() and bon_l.any():
        sous = g[np.ix_(np.clip(lig, 0, h - 1), np.clip(col, 0, w - 1))]
        sous[~bon_l, :] = 0
        sous[:, ~bon_c] = 0
        codes = sous
    tampon = io.BytesIO()
    Image.fromarray(_LUT[codes], "RGBA").save(tampon, "PNG", compress_level=3)
    return tampon.getvalue()


# --- images gardées sur disque ----------------------------------------------------------------------------------------------------------------------------------------
def _chemin(heure: str) -> str:
    return os.path.join(DOSSIER, heure.replace(":", "") + ".npz")


def heures() -> list:
    """Heures ISO des images disponibles, de la plus ancienne à la plus récente (13 au plus)."""
    try:
        noms = sorted(n[:-4] for n in os.listdir(DOSSIER) if n.endswith(".npz"))
    except OSError:
        return []
    sortie = []
    for n in noms:
        h = f"{n[:13]}:{n[13:15]}:{n[15:]}"   # 2026-11-13T134000.000Z -> 2026-11-13T13:40:00.000Z
        sortie.append(h)
    return sortie[-GARDER:]


def _charger(heure: str):
    with _verrou:
        if heure in _images:
            return _images[heure]
    try:
        g0 = np.load(_chemin(heure))["g"]
    except (OSError, ValueError, KeyError):
        return None
    py = _pyramide(g0)
    with _verrou:
        _images[heure] = py
        while len(_images) > 3:
            _images.pop(next(iter(_images)))
    return py


def _enregistrer(heure: str, g0: np.ndarray) -> None:
    os.makedirs(DOSSIER, exist_ok=True)
    tmp = _chemin(heure) + ".tmp.npz"
    np.savez_compressed(tmp, g=g0)
    os.replace(tmp, _chemin(heure))
    for h in heures()[:-GARDER]:
        pass
    for n in sorted(x for x in os.listdir(DOSSIER) if x.endswith(".npz") and ".tmp" not in x)[:-GARDER]:
        try:
            os.remove(os.path.join(DOSSIER, n))
        except OSError:
            pass


def _telecharger() -> bytes:
    r = requests.get(API + "/produit", params={"maille": 500}, headers={**ENTETES, "apikey": cle()}, timeout=90)
    r.raise_for_status()
    return r.content


def rafraichir() -> bool:
    """Télécharge la mosaïque la plus récente si elle est nouvelle. Renvoie True si une image a été ajoutée. Sans clé ou sans réseau : ne fait rien."""
    if not cle():
        _etat["derniere_erreur"] = "clé METEOFRANCE_API_KEY absente de .env"
        return False
    try:
        # l'API ne sert que la dernière image : on évite de la télécharger (1,7 Mo) si l'heure annoncée est déjà là
        info = requests.get(API, headers={**ENTETES, "apikey": cle()}, timeout=30)
        info.raise_for_status()
        annoncee = ""
        for lien in info.json().get("links", []):
            if "maille=500" in lien.get("href", "") and lien.get("validity_time"):
                annoncee = lien["validity_time"]
        if annoncee:
            fin = datetime.strptime(annoncee, "%Y-%m-%dT%H:%M:%SZ")
            # validity_time = début du cumul de 5 minutes ; l'heure d'observation gardée est la fin (début + 5 min)
            deja = {h[:19] for h in heures()}
            if (fin.replace(tzinfo=timezone.utc).timestamp() + 300) in {datetime.strptime(h[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp() for h in heures()} or annoncee[:19] in deja:
                return False
        heure, g0 = lire_hdf(_telecharger())
        if heure in heures():
            return False
        _enregistrer(heure, g0)
        _etat["derniere_erreur"] = ""
        return True
    except Exception as e:  # noqa: BLE001 : jamais bloquant
        _etat["derniere_erreur"] = f"{type(e).__name__}: {e}"[:200]
        return False


def _boucle() -> None:
    while not _etat["stop"].is_set():
        rafraichir()
        _etat["stop"].wait(PERIODE_S)


# --- serveur local ----------------------------------------------------------------------------------------------------------------------------------------------------
class _Relais(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def _repondre(self, code, corps, type_="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", type_)
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/frames":
                hs = heures()
                return self._repondre(200, json.dumps({"bounds": LIMITES, "times": hs, "error": _etat["derniere_erreur"]}).encode())
            if u.path == "/render":
                heure = q.get("time", "")
                if heure not in heures():
                    return self._repondre(404, b'{"error":"unknown_time"}')
                ouest, sud, est, nord = (float(v) for v in q["bbox"].split(","))
                largeur, hauteur = (int(v) for v in q["size"].split("x"))
                if not (est > ouest and nord > sud and 0 < largeur <= 4096 and 0 < hauteur <= 4096):
                    return self._repondre(400, b'{"error":"invalid"}')
                py = _charger(heure)
                if py is None:
                    return self._repondre(404, b'{"error":"unknown_time"}')
                return self._repondre(200, rendre(py, (ouest, sud, est, nord), largeur, hauteur), "image/png")
        except (KeyError, ValueError):
            return self._repondre(400, b'{"error":"invalid"}')
        except Exception:  # noqa: BLE001
            return self._repondre(500, b'{"error":"internal"}')
        self._repondre(404, b'{"error":"not_found"}')


def demarrer() -> dict:
    """Lance le serveur local et la mise à jour en tâche de fond (une seule fois). Renvoie les variables d'environnement à passer au serveur de la vue."""
    if not cle():
        return {}
    if _etat["serveur"] is None:
        try:
            _etat["serveur"] = ThreadingHTTPServer(("127.0.0.1", PORT), _Relais)
        except OSError:
            return {}   # port pris (autre JARVIS) : pas de radar plutôt qu'un conflit
        threading.Thread(target=_etat["serveur"].serve_forever, daemon=True, name="radar-fr-relais").start()
        _etat["stop"].clear()
        _etat["fil"] = threading.Thread(target=_boucle, daemon=True, name="radar-fr-maj")
        _etat["fil"].start()
    return {"JARVIS_RADAR_FR_URL": f"http://127.0.0.1:{PORT}"}


def arreter() -> None:
    _etat["stop"].set()
    s, _etat["serveur"] = _etat["serveur"], None
    if s is not None:
        try:
            s.shutdown()
            s.server_close()
        except Exception:  # noqa: BLE001
            pass
