"""Relais local des webcams Windy pour God's Eye View.

Les adresses d'image de l'API Windy Webcams (offre gratuite) expirent au bout de 10 à 15 minutes et ne doivent être utilisées que telles que
l'API les fournit : on ne peut donc pas les écrire dans le fichier de caméras de God's Eye View (module/gev_cameras_fr.py). Ce relais, qui n'écoute
que sur 127.0.0.1, sert `/windy/<identifiant>.jpg` : il redemande à Windy une liste fraîche (au plus une fois toutes les 8 minutes pour TOUTES les
webcams de la zone), télécharge l'image à l'adresse fournie par l'API et la rend. God's Eye View le prend pour une caméra ordinaire.

Respect des conditions de Windy (api.windy.com/webcams/terms, account.windy.com/agreements/windy-webcams-api-terms-of-use) :
  * adresses d'image uniquement celles de l'API, image jamais agrandie ni stockée sur disque ;
  * pas de balayage massif : zone limitée (CENTRES_WINDY, par défaut 50 km autour de Saint-Étienne), 1 appel de liste par 8 minutes au plus,
    jamais l'historique, jamais « toutes les webcams » ;
  * mention « Webcams provided by windy.com » portée par le champ `credit` de chaque caméra (voir gev_cameras_fr.py) ;
  * seules les webcams de la zone chargée sont servies (ce n'est pas un relais ouvert) ; la clé n'est jamais renvoyée ni journalisée.
Clé : WINDY_WEBCAMS_API_KEY dans le .env (api.windy.com/keys, « Webcams API »). Test : scratch/outils_test/test_windy_relais.py.
"""

import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

HOTE, PORT = "127.0.0.1", 8766
API = "https://api.windy.com/webcams/api/v3/webcams"
CENTRES_WINDY = [(45.4397, 4.3872, 50)]   # (latitude, longitude, rayon en km) : Saint-Étienne ; rayon maximal de l'API : 250 km
VALIDITE_LISTE_S = 8 * 60                 # liste fraîche ré-demandée au plus toutes les 8 minutes (les adresses d'image valent 10 à 15 minutes)
INTERVALLE_MIN_S = 30                     # jamais deux appels de liste à moins de 30 s d'écart, même en cas d'échec
UA = {"User-Agent": "JARVIS-Assistant/1.0 (personal use)"}

_verrou = threading.Lock()
_etat = {"t": 0.0, "dernier_appel": 0.0, "webcams": {}}
_serveur = {"actif": None}
_ID = re.compile(r"^/windy/(\d{6,12})\.jpg$")


def cle() -> str:
    from module import gev_cles   # .env de God's Eye View (panneau POWER UP), puis environnement de JARVIS
    return gev_cles.lire("WINDY_WEBCAMS_API_KEY")


def disponible() -> bool:
    return bool(cle()) and "VOTRE" not in cle().upper()


def _extraire(w: dict) -> dict:
    loc = w.get("location") or {}
    courant = ((w.get("images") or {}).get("current")) or {}
    return {
        "id": str(w.get("webcamId")), "title": str(w.get("title") or "").strip(), "status": w.get("status"),
        "city": str(loc.get("city") or ""), "lat": loc.get("latitude"), "lon": loc.get("longitude"),
        "image": courant.get("preview") or courant.get("thumbnail") or courant.get("icon") or "",
        "page": str((w.get("urls") or {}).get("detail") or ""),
    }


def charger(forcer: bool = False, timeout: float = 20.0) -> dict:
    """Webcams de la zone (actives ou non), par identifiant, avec une adresse d'image fraîche. Résultat gardé 8 minutes ; ancien résultat gardé si l'appel échoue."""
    with _verrou:
        maintenant = time.monotonic()
        if not disponible():
            return dict(_etat["webcams"])
        if _etat["webcams"] and not forcer and maintenant - _etat["t"] < VALIDITE_LISTE_S:
            return dict(_etat["webcams"])
        if maintenant - _etat["dernier_appel"] < INTERVALLE_MIN_S:
            return dict(_etat["webcams"])
        _etat["dernier_appel"] = maintenant
        trouvees = {}
        try:
            for lat, lon, rayon in CENTRES_WINDY:
                r = requests.get(API, headers={**UA, "x-windy-api-key": cle()}, timeout=timeout,
                                 params={"nearby": f"{lat},{lon},{int(rayon)}", "limit": 50, "offset": 0, "lang": "fr", "include": "location,images,urls"})
                r.raise_for_status()
                for w in r.json().get("webcams", []):
                    info = _extraire(w)
                    # les webcams inactives sont GARDÉES (elles peuvent redevenir actives d'un moment à l'autre) ; image() ne les sert qu'une fois actives
                    if info["image"] and info["lat"] is not None and info["lon"] is not None:
                        trouvees[info["id"]] = info
        except Exception as e:  # noqa: BLE001 : réseau, quota, format : on garde la liste précédente
            print(f"[WINDY] Liste indisponible : {type(e).__name__}")
            return dict(_etat["webcams"])
        if trouvees:
            _etat["webcams"], _etat["t"] = trouvees, time.monotonic()
        return dict(_etat["webcams"])


def image(identifiant: str):
    """Octets de l'image actuelle d'une webcam de la zone, ou None. Une adresse refusée (expirée) déclenche UNE nouvelle liste."""
    for tentative in range(2):
        info = charger(forcer=tentative == 1).get(identifiant)
        if not info or info["status"] != "active":   # inactive : l'image de Windy est ancienne, on ne la montre pas
            return None
        try:
            r = requests.get(info["image"], headers=UA, timeout=20)
        except requests.RequestException:
            return None
        if r.status_code in (401, 403) and tentative == 0:
            continue
        ok = r.status_code == 200 and r.headers.get("content-type", "").startswith("image/") and len(r.content) > 500
        return r.content if ok else None
    return None


class _Gestionnaire(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        m = _ID.match(self.path.split("?", 1)[0])
        octets = image(m.group(1)) if m else None
        if not octets:
            self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(octets)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(octets)

    def log_message(self, *args):  # silence : pas d'adresses ni de clés dans la console
        pass


def demarrer_relais() -> bool:
    """Lance le relais (une seule fois, tâche de fond, 127.0.0.1 uniquement). Renvoie True s'il écoute."""
    with _verrou:
        if _serveur["actif"] is not None:
            return True
        try:
            s = ThreadingHTTPServer((HOTE, PORT), _Gestionnaire)
        except OSError:
            return False   # port pris (autre JARVIS ?) : les caméras Windy resteront sans image
        threading.Thread(target=s.serve_forever, daemon=True).start()
        _serveur["actif"] = s
        return True


def arreter_relais() -> None:
    with _verrou:
        s, _serveur["actif"] = _serveur["actif"], None
    if s is not None:
        s.shutdown(); s.server_close()


def url_relais(identifiant: str) -> str:
    return f"http://{HOTE}:{PORT}/windy/{identifiant}.jpg"
