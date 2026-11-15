"""Vue de Dieu : God's Eye View (bilawalsidhu/gods-eye-view, MIT) installé à la demande, lancé à la demande, affiché dans le HUD.

God's Eye View est une appli web complète (globe 3D Cesium, avions, bateaux, satellites, séismes, caméras publiques…) qui tourne sur un petit
serveur Vite local. Elle n'est PAS dans le dépôt de JARVIS : au premier « active la vue de Dieu », JARVIS propose de l'installer depuis la
dernière release GitHub dans data/gods_eye_view/ (non versionné), puis propose les mises à jour quand une release plus récente existe.

  data/gods_eye_view/app/            l'appli (release GitHub, sans ses GIF de démonstration) + jarvis.vite.config.mjs écrit par JARVIS
  data/gods_eye_view/node/           Node.js 24 portable, seulement si l'ordinateur n'a pas Node 24.14+ (rien n'est installé dans le système)
  data/gods_eye_view/version.json    version installée, dernière vérification, version refusée

Le HUD (interfaces/frontend/src/hud/vue_de_dieu.ts) l'affiche en plein écran dans une iframe. L'appli refuse d'être cadrée par défaut :
jarvis.vite.config.mjs (fichier à nous, l'appli n'est jamais modifiée) ajoute un en-tête qui n'autorise que les origines du HUD (localhost).
"""

import atexit
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import zipfile

import requests

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.path.join(RACINE, "data", "gods_eye_view")
DOSSIER = os.path.join(DATA, "app")
NODE_DIR = os.path.join(DATA, "node")
TMP = os.path.join(DATA, "tmp")
FICHIER_VERSION = os.path.join(DATA, "version.json")
VITE = os.path.join(DOSSIER, "node_modules", "vite", "bin", "vite.js")
CONFIG_JARVIS = "jarvis.vite.config.mjs"
JOURNAL = os.path.join(RACINE, "data", "gods_eye_view.log")
DEPOT = "bilawalsidhu/gods-eye-view"
API = f"https://api.github.com/repos/{DEPOT}"
UA = {"User-Agent": "JARVIS-Assistant/1.0 (personal use)", "Accept": "application/vnd.github+json"}
HOTE, PORT = "127.0.0.1", 4173
URL = f"http://{HOTE}:{PORT}/"
ORIGINES_HUD = "http://localhost:5173 http://127.0.0.1:5173"
NODE_MIN = (24, 14)
VERIF_TOUS_LES_JOURS = 24 * 3600

_proc = None
_verrou = threading.Lock()
_annuler = threading.Event()
ouverte = False              # le HUD affiche la vue (message vue_de_dieu_state) : sert à diriger « va à Tokyo » vers elle
retours = {}                # ordres vocaux en attente de réponse de la vue : id -> Future (résolu par ws_handler)
installation_en_cours = False


class Annule(Exception):
    """Installation annulée par l'utilisateur (le HUD a été fermé)."""


class ErreurInstall(Exception):
    """Échec d'installation avec un message prêt à être dit."""


# ───────────────────────────── État installé, versions ─────────────────────────────
def _lire_version() -> dict:
    try:
        with open(FICHIER_VERSION, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _ecrire_version(d: dict) -> None:
    os.makedirs(DATA, exist_ok=True)
    with open(FICHIER_VERSION, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def installee() -> bool:
    return os.path.isfile(VITE)


def version_installee():
    return _lire_version().get("tag")


def _semver(tag) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", str(tag or ""))[:3]) or (0,)


def notes_structurees(corps: str, max_car: int = 5000) -> list:
    """Notes d'une release GitHub (markdown, en anglais, avec images) -> liste de [genre, texte] pour le HUD : « h » titre, « li » point de liste, « p » paragraphe.
    Images, balises HTML et commentaires retirés, liens et gras réduits au texte, coupé proprement à `max_car` caractères."""
    texte = re.sub(r"<!--.*?-->|<[^>]+>|!\[[^\]]*\]\([^)]*\)", "", corps or "", flags=re.S)
    lignes, total = [], 0
    for brut in texte.splitlines():
        ligne = brut.strip()
        if ligne.startswith("#"):
            genre, ligne = "h", ligne.lstrip("#").strip()
        elif ligne[:2] in ("- ", "* "):   # reconnu AVANT de retirer le gras (« * » est aussi un marqueur de gras)
            genre, ligne = "li", ligne[2:].strip()
        else:
            genre = "p"
        ligne = re.sub(r"[*_`]", "", re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", ligne)).strip()
        if not ligne:
            continue
        if total + len(ligne) > max_car:
            break
        lignes.append([genre, ligne])
        total += len(ligne)
    return lignes


def derniere_release():
    """{tag, nom, publiee, zip, notes (liste [genre, texte], voir notes_structurees)} de la dernière release GitHub, ou None (hors ligne, limite de requêtes…)."""
    try:
        r = requests.get(f"{API}/releases/latest", headers=UA, timeout=8)
        r.raise_for_status()
        d = r.json()
        return {"tag": d["tag_name"], "nom": d.get("name") or d["tag_name"], "publiee": (d.get("published_at") or "")[:10], "zip": d["zipball_url"], "notes": notes_structurees(d.get("body"))}
    except Exception:
        return None


def mise_a_jour_disponible(forcer: bool = False):
    """La release plus récente que la version installée (ou None). Une vérification par jour sauf `forcer` ; une version déjà refusée
    n'est plus proposée (sauf `forcer`, c'est-à-dire « mets à jour la vue de Dieu »)."""
    v = _lire_version()
    if not installee() or not v.get("tag"):
        return None
    if not forcer and time.time() - v.get("derniere_verif", 0) < VERIF_TOUS_LES_JOURS and not v.get("nouvelle"):
        return None
    rel = derniere_release()
    v["derniere_verif"] = time.time()
    plus_recente = rel if rel and _semver(rel["tag"]) > _semver(v["tag"]) else None
    v["nouvelle"] = plus_recente["tag"] if plus_recente else None
    _ecrire_version(v)
    if plus_recente and not forcer and v.get("refusee") == plus_recente["tag"]:
        return None
    return plus_recente


def refuser_version(tag: str) -> None:
    v = _lire_version(); v["refusee"] = tag; _ecrire_version(v)


# ───────────────────────────── Node.js ─────────────────────────────
def _version_ok(chemin: str) -> bool:
    try:
        sortie = subprocess.run([chemin, "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return False
    m = re.match(r"v(\d+)\.(\d+)", sortie)
    if not m:
        return False
    maj, mino = int(m.group(1)), int(m.group(2))
    return (maj == 24 and (maj, mino) >= NODE_MIN) or maj >= 26


def _node():
    """Chemin d'un Node 24.14+ (ou 26+) : celui du système, sinon le Node portable installé dans data/gods_eye_view/node. None sinon."""
    portable = os.path.join(NODE_DIR, "node.exe")
    for chemin in (shutil.which("node"), os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "nodejs", "node.exe"), portable):
        if chemin and os.path.isfile(chemin) and _version_ok(chemin):
            return chemin
    return None


def _npm_cli(node: str):
    chemin = os.path.join(os.path.dirname(node), "node_modules", "npm", "bin", "npm-cli.js")
    return chemin if os.path.isfile(chemin) else None


# ───────────────────────────── Téléchargement ─────────────────────────────
def _telecharger(url: str, dest: str, progres, etiquette: str) -> None:
    """Télécharge `url` dans `dest` en rendant compte de l'avancement ; s'arrête dès que l'installation est annulée."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with requests.get(url, headers=UA, stream=True, timeout=30) as r:
        r.raise_for_status()
        total, recu, dernier = int(r.headers.get("Content-Length") or 0), 0, 0.0
        with open(dest, "wb") as f:
            for morceau in r.iter_content(chunk_size=256 * 1024):
                if _annuler.is_set():
                    raise Annule()
                f.write(morceau)
                recu += len(morceau)
                if time.time() - dernier > 0.4:
                    dernier = time.time()
                    progres(f"{etiquette} · {recu / 1e6:.0f}" + (f" / {total / 1e6:.0f} MO" if total else " MO"), (recu / total) if total else None)


def _sha256(chemin: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def _installer_node_portable(progres) -> str:
    """Télécharge le Node 24 LTS officiel (zip, somme de contrôle vérifiée) dans data/gods_eye_view/node : aucune installation système."""
    import platform
    if os.name != "nt" or platform.machine().lower() not in ("amd64", "x86_64"):
        raise ErreurInstall("L'installation automatique de Node.js n'est prévue que pour Windows 64 bits.")
    progres("RECHERCHE DE NODE.JS 24…", None)
    index = requests.get("https://nodejs.org/dist/index.json", headers=UA, timeout=15).json()
    version = next((x["version"] for x in index if x["version"].startswith("v24.") and x.get("lts")), None)
    if not version:
        raise ErreurInstall("Je ne trouve pas Node.js 24 sur nodejs.org.")
    nom = f"node-{version}-win-x64.zip"
    archive = os.path.join(TMP, nom)
    sommes = requests.get(f"https://nodejs.org/dist/{version}/SHASUMS256.txt", headers=UA, timeout=15).text
    attendue = next((l.split()[0] for l in sommes.splitlines() if l.strip().endswith(nom)), None)
    _telecharger(f"https://nodejs.org/dist/{version}/{nom}", archive, progres, f"TÉLÉCHARGEMENT DE NODE.JS {version[1:]}")
    if not attendue or _sha256(archive) != attendue:
        raise ErreurInstall("Le fichier Node.js téléchargé est corrompu (somme de contrôle différente) : je ne l'installe pas.")
    progres("EXTRACTION DE NODE.JS…", None)
    shutil.rmtree(NODE_DIR, ignore_errors=True)
    os.makedirs(NODE_DIR, exist_ok=True)
    racine_zip = f"node-{version}-win-x64/"
    with zipfile.ZipFile(archive) as z:
        for m in z.infolist():
            if _annuler.is_set():
                raise Annule()
            if m.is_dir() or not m.filename.startswith(racine_zip):
                continue
            cible = os.path.join(NODE_DIR, *m.filename[len(racine_zip):].split("/"))
            os.makedirs(os.path.dirname(cible), exist_ok=True)
            with z.open(m) as src, open(cible, "wb") as dst:
                shutil.copyfileobj(src, dst)
    exe = os.path.join(NODE_DIR, "node.exe")
    if not _version_ok(exe):
        raise ErreurInstall("Node.js n'a pas pu être installé correctement.")
    return exe


# ───────────────────────────── Installation ─────────────────────────────
_CONFIG_VITE = r"""// Écrit par JARVIS (backend/module/vue_de_dieu.py) : God's Eye View lui-même n'est jamais modifié.
// L'appli refuse d'être cadrée par une autre page (X-Frame-Options: DENY, frame-ancestors 'none') sauf en mode ?embed=1, qui masque tout son HUD.
// Ce fichier la laisse cadrer par les seules origines de GEV_EMBED_FRAME_ANCESTORS (le HUD de JARVIS, sur localhost).
import base from './server/standalone/vite.config.js';
import { mergeConfig } from 'vite';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Bouton « utiliser la clé de JARVIS » dans les cartes OpenAI / Gemini des Paramètres de l'appli : un petit script (jarvis-partage.js, écrit par JARVIS)
// ajouté à la page au moment de la servir, sans toucher aux fichiers de l'appli.
const SCRIPT_PARTAGE = path.join(path.dirname(fileURLToPath(import.meta.url)), 'jarvis-partage.js');
function jarvisPartage() {
  return {
    name: 'jarvis-partage',
    configureServer(server) {
      server.middlewares.use('/__jarvis/partage.js', (req, res) => {
        res.setHeader('Content-Type', 'text/javascript; charset=utf-8');
        res.setHeader('Cache-Control', 'no-store');
        try { res.end(fs.readFileSync(SCRIPT_PARTAGE, 'utf8')); } catch { res.statusCode = 404; res.end(); }
      });
    },
    transformIndexHtml: () => [{ tag: 'script', attrs: { src: '/__jarvis/partage.js', defer: true }, injectTo: 'body' }],
  };
}

const ANCESTORS = (process.env.GEV_EMBED_FRAME_ANCESTORS || '').trim();
const FRAMING = new Set(['x-frame-options', 'content-security-policy']);

function jarvisFraming() {
  const install = (server) => {
    server.middlewares.use((req, res, next) => {
      let pathname = '/';
      try { pathname = new URL(req.url || '/', 'http://localhost').pathname; } catch { /* adresse illisible : page par défaut */ }
      if (!ANCESTORS || !(pathname === '/' || pathname.endsWith('.html'))) return next();
      const setHeader = res.setHeader.bind(res);
      res.setHeader = (name, value) => {
        const key = String(name).toLowerCase();
        if (!FRAMING.has(key)) return setHeader(name, value);
        if (key === 'content-security-policy') {
          const gardees = String(value ?? '').split(';').map((d) => d.trim()).filter(Boolean).filter((d) => !/^frame-ancestors\b/i.test(d));
          return setHeader(name, [...gardees, `frame-ancestors ${ANCESTORS}`].join('; '));
        }
        return res; // X-Frame-Options retiré : la CSP ci-dessus décide
      };
      next();
    });
  };
  return { name: 'jarvis-framing', configureServer: install, configurePreviewServer: install };
}

// Cadence de rechargement des images des caméras : l'appli la fixe par fournisseur (src/data/cctvLod.js, 5 minutes pour un fournisseur inconnu). Le pack de JARVIS déclare
// ses fournisseurs ici, au moment où le fichier est servi : l'appli n'est pas modifiée, et si son code change (la phrase cherchée disparaît) rien n'est appliqué.
const CADENCES_JARVIS = { 'métropole de lyon': 60 * 1000 };   // Lyon publie une nouvelle image par minute
function jarvisCadence() {
  const MARQUE = 'const PROVIDER_STATIC_REFRESH_MS = Object.freeze({';
  return {
    name: 'jarvis-cadence',
    enforce: 'pre',
    transform(code, id) {
      const chemin = id.split(String.fromCharCode(92)).join('/').split('?')[0];   // caractère 92 = antislash (chemins Windows)
      if (!chemin.endsWith('/src/data/cctvLod.js') || !code.includes(MARQUE)) return null;
      const NL = String.fromCharCode(10);
      const lignes = Object.entries(CADENCES_JARVIS).map(([k, v]) => `  ${JSON.stringify(k)}: ${v},`).join(NL);
      return { code: code.replace(MARQUE, () => MARQUE + NL + lignes), map: null };
    },
  };
}

// Vélos en libre-service français (flux GBFS publiés sur transport.data.gouv.fr) : la couche Bike Share de l'appli n'a aucune ville française. Deux ajouts, sans toucher à l'appli :
//  1. les réseaux sont ajoutés au registre de la couche (src/layers/bikeshare/registry.js) au moment où le fichier est servi (rien n'est appliqué si la marque cherchée disparaît) ;
//  2. le relais /api/gbfs de l'appli n'accepte que ses hôtes à elle : ce plugin, placé avant le sien, relaie les hôtes français ci-dessous (https, stations seulement, 5 Mo, sans redirection).
const cyclocity = (id, city, lat, lon, contrat, provider, r = 40) => ({ id, city, centerLat: lat, centerLon: lon, loadRadiusKm: r, provider,
  stationInformationUrl: `https://api.cyclocity.fr/contracts/${contrat}/gbfs/station_information.json`,
  stationStatusUrl: `https://api.cyclocity.fr/contracts/${contrat}/gbfs/station_status.json` });
const flux = (id, city, lat, lon, info, statut, provider, r = 40) => ({ id, city, centerLat: lat, centerLon: lon, loadRadiusKm: r, provider, stationInformationUrl: info, stationStatusUrl: statut });
const VELOS_FR = [
  flux('saint-etienne-velivert', 'Saint-Étienne, France', 45.4503, 4.4016, 'https://gbfs.sigma.fifteen.eu/gbfs/2.2/saint-etienne/en/station_information.json', 'https://gbfs.sigma.fifteen.eu/gbfs/2.2/saint-etienne/en/station_status.json', 'VéliVert'),
  cyclocity('lyon-velov', 'Lyon, France', 45.764, 4.8357, 'lyon', "Vélo'v", 40),
  flux('paris-velib', 'Paris, France', 48.8574, 2.342, 'https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_information.json', 'https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_status.json', "Vélib' Métropole", 50),
  flux('lille-vlille', 'Lille, France', 50.6505, 3.0915, 'https://media.ilevia.fr/opendata/station_information.json', 'https://media.ilevia.fr/opendata/station_status.json', "V'Lille"),
  flux('marseille-levelo', 'Marseille, France', 43.2878, 5.3902, 'https://gbfs.omega.fifteen.eu/gbfs/2.2/marseille/en/station_information.json', 'https://gbfs.omega.fifteen.eu/gbfs/2.2/marseille/en/station_status.json', 'LeVélo'),
  cyclocity('toulouse-velo', 'Toulouse, France', 43.6047, 1.4442, 'toulouse', 'VélôToulouse'),
  cyclocity('nantes-bicloo', 'Nantes, France', 47.2184, -1.5536, 'nantes', 'Bicloo'),
  flux('strasbourg-velhop', 'Strasbourg, France', 48.5844, 7.7369, 'https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_ae/fr/station_information.json', 'https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_ae/fr/station_status.json', 'Vélhop', 30),
  flux('montpellier-velomagg', 'Montpellier, France', 43.6107, 3.8759, 'https://gbfs.theta.fifteen.eu/gbfs/2.2/montpellier/en/station_information.json', 'https://gbfs.theta.fifteen.eu/gbfs/2.2/montpellier/en/station_status.json', 'Vélomagg'),
  flux('rennes-star', 'Rennes, France', 48.1105, -1.6744, 'https://eu.ftp.opendatasoft.com/star/gbfs/station_information.json', 'https://eu.ftp.opendatasoft.com/star/gbfs/station_status.json', 'Le Vélo STAR'),
  flux('clermont-cvelo', 'Clermont-Ferrand, France', 45.772, 3.112, 'https://clermontferrand.publicbikesystem.net/customer/gbfs/v2/fr/station_information', 'https://clermontferrand.publicbikesystem.net/customer/gbfs/v2/fr/station_status', 'C.Vélo', 30),
  flux('annecy-velonecy', 'Annecy, France', 45.8963, 6.12, 'https://gbfs.partners.fifteen.eu/gbfs/2.2/annecy/en/station_information.json', 'https://gbfs.partners.fifteen.eu/gbfs/2.2/annecy/en/station_status.json', 'Vélonecy', 30),
  cyclocity('amiens-velam', 'Amiens, France', 49.8941, 2.2958, 'amiens', 'Vélam', 30),
  cyclocity('mulhouse-velocite', 'Mulhouse, France', 47.7508, 7.3359, 'mulhouse', 'VéloCité', 30),
  cyclocity('nancy-velostanlib', 'Nancy, France', 48.6921, 6.1844, 'nancy', 'vélOstan’lib', 30),
  cyclocity('besancon-velocite', 'Besançon, France', 47.2378, 6.0241, 'besancon', 'VéloCité', 30),
];
const HOTES_VELOS_FR = new Set(['gbfs.sigma.fifteen.eu', 'velib-metropole-opendata.smovengo.cloud', 'media.ilevia.fr', 'gbfs.omega.fifteen.eu', 'gbfs.theta.fifteen.eu', 'eu.ftp.opendatasoft.com', 'gbfs.partners.fifteen.eu']);
function jarvisVelosFrance() {
  const MARQUE = 'const RAW_GBFS_CITY_REGISTRY = [';
  let minute = 0, compte = 0;
  const reponse = (res, code, corps, cache = 'no-store') => { res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': cache }); res.end(JSON.stringify(corps)); };
  const relais = async (req, res, next) => {
    let cible;
    try { cible = new URL(decodeURIComponent((req.url || '/').split('?')[0].replace(/^\/+/, ''))); } catch { return next(); }
    if (req.method !== 'GET' || !HOTES_VELOS_FR.has(cible.hostname.toLowerCase())) return next();   // les autres hôtes : le relais de l'appli
    if (cible.protocol !== 'https:' || !/\/station_(information|status)(\.json)?$/i.test(cible.pathname)) return reponse(res, 400, { error: 'Only https station_information/station_status endpoints are allowed' });
    const maintenant = Date.now();
    if (maintenant - minute > 60000) { minute = maintenant; compte = 0; }
    if (++compte > 240) return reponse(res, 429, { error: 'Rate limit exceeded' });
    const ctl = new AbortController(), minuteur = setTimeout(() => ctl.abort(), 12000);
    try {
      const amont = await fetch(cible.toString(), { method: 'GET', headers: { Accept: 'application/json', 'User-Agent': 'gods-eye-view-gbfs-proxy/1.0' }, redirect: 'manual', signal: ctl.signal });
      if (amont.status >= 300 && amont.status < 400) return reponse(res, 502, { error: 'GBFS upstream redirect refused' });
      const octets = Buffer.from(await amont.arrayBuffer());
      if (octets.length > 5 * 1024 * 1024) return reponse(res, 502, { error: 'GBFS upstream response too large' });
      let donnees;
      try { donnees = JSON.parse(octets.toString('utf8')); } catch { return reponse(res, 502, { error: 'GBFS upstream returned non-JSON' }); }
      reponse(res, amont.status, donnees, /\/station_information(\.json)?$/i.test(cible.pathname) ? 'public, max-age=300' : 'no-store');
    } catch (e) {
      reponse(res, e && e.name === 'AbortError' ? 504 : 502, { error: 'GBFS proxy error' });
    } finally { clearTimeout(minuteur); }
  };
  const installer = (server) => { server.middlewares.use('/api/gbfs', relais); };   // ne rien renvoyer : Vite appellerait la valeur de retour comme un rappel
  return {
    name: 'jarvis-velos-france',
    enforce: 'pre',   // avant le relais de l'appli, qui répondrait 403 aux hôtes qu'il ne connaît pas
    configureServer: installer,
    configurePreviewServer: installer,
    transform(code, id) {
      const chemin = id.split(String.fromCharCode(92)).join('/').split('?')[0];
      if (!chemin.endsWith('/src/layers/bikeshare/registry.js') || !code.includes(MARQUE)) return null;
      const NL = String.fromCharCode(10);
      return { code: code.replace(MARQUE, () => MARQUE + NL + JSON.stringify(VELOS_FR).slice(1, -1) + ','), map: null };
    },
  };
}

// Transports en commun français (flux GTFS-RT VehiclePositions de transport.data.gouv.fr, liste dans jarvis-transit-fr.json, écrite par JARVIS) : la couche Transit de l'appli n'a que 16 régions
// codées en dur. Même principe que les vélos : 1. le registre servi au navigateur reçoit les réseaux français (src/data/transitFeeds.js, rien n'est appliqué si la marque disparaît) ;
// 2. le relais /api/transit de l'appli ne connaît que son registre : ce plugin, placé avant lui, répond pour les identifiants français (décodage et format identiques, cache de 15 s,
// https seulement, 8 Mo, 3 redirections au plus, adresses locales refusées) et ajoute les réseaux au catalogue /api/transit/feeds.
// Décodage GTFS-RT et en-têtes de l'appli, chargés au démarrage : si une mise à jour de l'appli les déplace ou les renomme, SEUL le transit français est désactivé (un import statique ferait échouer toute la Vue de Dieu).
let buildTransitSnapshot = null, transitResponseHeaders = null;
const TRANSIT_FR = (() => {
  try { return JSON.parse(fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), 'jarvis-transit-fr.json'), 'utf8')); } catch { return []; }
})();
const TRANSIT_FR_PAR_ID = new Map(TRANSIT_FR.map((f) => [f.id, f]));
const hoteLocal = (h) => h === 'localhost' || h.endsWith('.local') || h.endsWith('.localhost') || h.endsWith('.internal') || /^[0-9.]+$/.test(h) || h.includes(':');
async function lireFluxTransit(url, signal) {
  let courant = url;
  for (let saut = 0; saut <= 3; saut += 1) {
    const u = new URL(courant);
    if (u.protocol !== 'https:' || hoteLocal(u.hostname.toLowerCase())) throw new Error('adresse refusée');   // les adresses de transport.data.gouv.fr redirigent vers le flux de l'exploitant : tout hôte public en https est admis
    const rep = await fetch(courant, { signal, redirect: 'manual', headers: { 'User-Agent': 'gods-eye-view-transit-proxy/1.0', Accept: 'application/x-protobuf, application/octet-stream;q=0.9, */*;q=0.1' } });
    if (rep.status >= 300 && rep.status < 400) {
      const ailleurs = rep.headers.get('location');
      try { await rep.body?.cancel(); } catch { /* sans effet */ }
      if (!ailleurs || saut === 3) throw new Error('trop de redirections');
      courant = new URL(ailleurs, courant).toString();
      continue;
    }
    if (!rep.ok) throw new Error('HTTP ' + rep.status);
    const octets = new Uint8Array(await rep.arrayBuffer());
    if (octets.length > 8 * 1024 * 1024) throw new Error('réponse trop grosse');
    return { octets, hote: new URL(courant).hostname };
  }
  throw new Error('trop de redirections');
}
function jarvisTransitFrance() {
  const MARQUE = 'export const TRANSIT_FEED_REGISTRY = Object.freeze([';
  const cache = new Map(), enCours = new Map();
  let minute = 0, compte = 0;
  const repondre = (res, code, corps, entetes) => { res.writeHead(code, entetes || { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' }); res.end(typeof corps === 'string' ? corps : JSON.stringify(corps)); };
  async function actualiser(feed) {
    const ctl = new AbortController(), minuteur = setTimeout(() => ctl.abort(), 15000);
    try {
      const { octets, hote } = await lireFluxTransit(feed.url, ctl.signal);
      const instantane = buildTransitSnapshot({ id: feed.id, name: feed.name }, octets, Date.now());
      const entree = { at: instantane.fetchedAt, hote, corps: JSON.stringify(instantane) };
      cache.set(feed.id, entree);
      return entree;
    } finally { clearTimeout(minuteur); }
  }
  const relais = async (req, res, next) => {
    const chemin = (req.url || '/').split('?')[0];
    if (req.method === 'GET' && (chemin === '/feeds' || chemin === '/feeds/') && TRANSIT_FR.length) {
      const fin = res.end.bind(res);
      res.end = (corps, ...suite) => {
        try { const j = JSON.parse(String(corps)); if (Array.isArray(j.feeds)) { j.feeds.push(...TRANSIT_FR.map((f) => ({ id: f.id, name: f.name, operator: f.operator, region: f.region, center: f.center, loadRadiusKm: f.loadRadiusKm, license: f.license, licenseUrl: f.licenseUrl, attribution: f.attribution, historyRetention: false }))); corps = JSON.stringify(j); } } catch { /* catalogue inchangé */ }
        return fin(corps, ...suite);
      };
      return next();
    }
    const m = /^\/vehicles\/([^/]+)\/?$/.exec(chemin);
    const feed = m && TRANSIT_FR_PAR_ID.get((() => { try { return decodeURIComponent(m[1]); } catch { return ''; } })());
    if (!feed) return next();   // les autres identifiants : le relais de l'appli
    if (req.method !== 'GET') return repondre(res, 405, { error: 'Method Not Allowed' });
    const maintenant = Date.now();
    if (maintenant - minute > 60000) { minute = maintenant; compte = 0; }
    const gardee = cache.get(feed.id);
    if (gardee && maintenant - gardee.at < 15000) return repondre(res, 200, gardee.corps, transitResponseHeaders('HIT', gardee.hote, gardee.at));
    if (++compte > 240) return repondre(res, 429, { error: 'Rate limit exceeded' });
    try {
      if (!enCours.has(feed.id)) enCours.set(feed.id, actualiser(feed).finally(() => enCours.delete(feed.id)));
      const e = await enCours.get(feed.id);
      return repondre(res, 200, e.corps, transitResponseHeaders('MISS', e.hote, e.at));
    } catch (erreur) {
      if (gardee && maintenant - gardee.at < 10 * 60000) return repondre(res, 200, gardee.corps, transitResponseHeaders('STALE-ERROR', gardee.hote, gardee.at));
      return repondre(res, 503, { error: 'Transit feed unavailable', feedId: feed.id, retryInSec: 30 }, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'Retry-After': '30' });
    }
  };
  const installer = (server) => { server.middlewares.use('/api/transit', relais); };
  return {
    name: 'jarvis-transit-france',
    enforce: 'pre',
    configureServer: installer,
    configurePreviewServer: installer,
    transform(code, id) {
      const chemin = id.split(String.fromCharCode(92)).join('/').split('?')[0];
      if (!TRANSIT_FR.length || !chemin.endsWith('/src/data/transitFeeds.js') || !code.includes(MARQUE)) return null;
      const NL = String.fromCharCode(10);
      const note = 'Données ouvertes publiées sur transport.data.gouv.fr par l’exploitant ou l’autorité organisatrice, réutilisables avec mention de la source (licence indiquée sur la fiche du jeu de données).';
      const entrees = TRANSIT_FR.map((f) => ({ id: f.id, name: f.name, operator: f.operator, region: f.region, center: f.center, loadRadiusKm: f.loadRadiusKm, url: f.url, license: f.license, licenseUrl: f.licenseUrl, attribution: f.attribution, defaultEnabled: true, terms: { quote: null, note }, defaultMode: 'bus' }));
      return { code: code.replace(MARQUE, () => MARQUE + NL + JSON.stringify(entrees).slice(1, -1) + ','), map: null };
    },
  };
}

// Radars automatiques français (OpenStreetMap, fichier radars_france.json fait par JARVIS en tâche de fond, voir module/gev_radars_fr.py) : l'appli n'a qu'un calque « ALPR » (caméras de
// lecture de plaques, États-Unis et Canada seulement). Sans le remplacer : sur la France, sa source de données lit les radars ; ailleurs elle lit les tuiles ALPR d'origine.
// Les fiches, le titre du calque et les messages disent « radar » pour un radar. Chaque remplacement est indépendant : si une phrase de l'appli change, les autres restent appliqués
// (au pire un radar s'appelle « ALPR »). Fichier servi à la page sur /__jarvis/radars-fr.json (503 tant que le téléchargement n'est pas fini : le calque réessaie tout seul).
const RADARS_FR = process.env.JARVIS_RADARS_FILE || '';
function radarsFranceSource(base) {   // injectée telle quelle (toString) dans src/layers/alpr/source.js : ne dépend d'aucune variable extérieure
  const FRANCE = { south: 41, west: -5.6, north: 51.3, east: 9.9 };
  let radars = null;
  async function charger(signal) {
    if (radars) return radars;
    // Le fichier se prépare au lancement (quelques secondes, davantage sans réseau) : on patiente ICI, requête annulable (le calque annule et relance à chaque déplacement), au lieu
    // de faire échouer le calque, dont la boucle de réessai monte à 4 minutes et y reste à chaque zoom. 503 = pas encore prêt ; toute autre erreur : échec franc.
    let rep;
    for (let essai = 0; ; essai += 1) {
      rep = await fetch('/__jarvis/radars-fr.json', { signal, headers: { Accept: 'application/json' } });
      if (rep.ok || rep.status !== 503 || essai >= 100) break;
      await new Promise((fini, annule) => {
        const t = setTimeout(fini, 3000);
        signal?.addEventListener('abort', () => { clearTimeout(t); annule(signal.reason); }, { once: true });
      });
    }
    if (!rep.ok) throw new Error('French speed cameras are not available yet, retrying shortly');
    const liste = await rep.json();
    if (!Array.isArray(liste)) throw new Error('Malformed speed camera list');
    radars = liste.map((r) => ({ id: 'radar:' + r[0], osmId: parseInt(String(r[0]).replace(/\D/g, ''), 10) || 0, kind: 'radar', latitude: r[1], longitude: r[2], maxspeed: r[3], directionDeg: r[4], cameraType: r[5], ref: r[6], operator: null, manufacturer: null, zone: null, lastVerified: null, source: 'Sécurité routière' }));
    return radars;
  }
  return {
    ...base,
    // « name » reste « OpenStreetMap » : l'appli s'en sert pour ses fiches ALPR ; seuls le texte et la description ajoutent la source des radars
    attribution: { ...base.attribution, description: base.attribution.description + ' ; radars : Sécurité routière (radars.securite-routiere.gouv.fr)', text: base.attribution.text + ' · Sécurité routière' },
    async fetch(box, signal) {
      const enFrance = box.east >= FRANCE.west && box.west <= FRANCE.east && box.north >= FRANCE.south && box.south <= FRANCE.north;
      if (!enFrance) return base.fetch(box, signal);
      const tous = await charger(signal);
      signal?.throwIfAborted();
      const records = tous.filter((r) => r.latitude >= box.south && r.latitude <= box.north && r.longitude >= box.west && r.longitude <= box.east);
      return { records, stale: false, saturated: false, coverage: { ...box } };   // la zone demandée, pas la France : le calque réutilise les enregistrements tant que la vue reste dans `coverage`
    },
  };
}
function jarvisRadarsFrance() {
  const NL = String.fromCharCode(10);
  const DETAILS = 'function jarvisRadarDetails(record) {' + NL
    + "  const d = ['SÉCURITÉ ROUTIÈRE'];" + NL
    + "  if (Number.isFinite(record.directionDeg)) d.push('DIRECTION ' + Math.round(record.directionDeg) + '°');" + NL
    + "  d.push((record.cameraType && record.cameraType !== 'radar' ? 'RADAR ' + record.cameraType : 'RADAR').toUpperCase() + (record.maxspeed ? ' · ' + record.maxspeed + ' KM/H' : ''));" + NL
    + "  d.push('DONNÉES OFFICIELLES');" + NL + '  return d;' + NL + '}' + NL;
  const MODIFS = {
    '/src/layers/alpr/source.js': { remplacer: [['export function createAlprTileSource({', 'function createAlprTileSourceBase({']],
      ajouter: NL + 'export function createAlprTileSource(options) { return (' + radarsFranceSource.toString() + ')(createAlprTileSourceBase(options)); }' + NL },
    '/src/layers/alpr/visuals.js': { remplacer: [
      ['return `ALPR-${String(record.osmId)', "return `${record.kind === 'radar' ? 'RADAR' : 'ALPR'}-${String(record.osmId)"],
      ['export function alprLabelDetails(record, source) {', DETAILS + 'export function alprLabelDetails(record, source) {' + NL + "  if (record.kind === 'radar') return jarvisRadarDetails(record);" + NL + '  return alprLabelDetailsOriginal(record, source);' + NL + '}' + NL + 'function alprLabelDetailsOriginal(record, source) {']] },
    '/src/layers/alpr/presentation.js': { remplacer: [
      ["layerName: 'ALPR Cameras',", "layerName: record.kind === 'radar' ? 'Speed Cameras' : 'ALPR Cameras',"],
      ["label: msg('ALPR camera'),", "label: record.kind === 'radar' ? 'Speed camera' : msg('ALPR camera'),"],
      ['ref: record.ref,', 'ref: record.ref, maxspeedKmh: record.maxspeed ?? null,']] },
    '/src/layers/alpr/index.js': { remplacer: [["t('No ALPR data for this area — US and Canada only')", "t('No ALPR data for this area — US, Canada and France only')"]] },
    '/src/ui/layerNames.js': { remplacer: [["msg('ALPR Cameras')", "msg('ALPR and Speed Cameras')"], ["msg('Mapped ALPR Cameras')", "msg('Mapped ALPR and Speed Cameras')"]] },
  };
  const installer = (server) => {
    server.middlewares.use((req, res, next) => {
      if (!RADARS_FR || (req.url || '').split('?')[0] !== '/__jarvis/radars-fr.json') return next();
      fs.readFile(RADARS_FR, (erreur, donnees) => {
        if (erreur) { res.writeHead(503, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'Retry-After': '30' }); return res.end('{"error":"downloading"}'); }
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'public, max-age=3600' });
        res.end(donnees);
      });
    });
  };
  return {
    name: 'jarvis-radars-france',
    enforce: 'pre',
    configureServer: installer,
    configurePreviewServer: installer,
    transform(code, id) {
      const chemin = id.split(String.fromCharCode(92)).join('/').split('?')[0];
      const cle = Object.keys(MODIFS).find((k) => chemin.endsWith(k));
      if (!cle || !RADARS_FR) return null;
      let resultat = code, change = false;
      for (const [de, vers] of MODIFS[cle].remplacer) if (resultat.includes(de)) { resultat = resultat.replace(de, () => vers); change = true; }
      if (change && MODIFS[cle].ajouter) resultat += MODIFS[cle].ajouter;
      return change ? { code: resultat, map: null } : null;
    },
  };
}

// Départ de la vue : l'appli s'ouvre sur Austin (src/camera.js, flyToAustin) ; on l'ouvre sur la France (Saint-Étienne, vue d'ensemble puis descente). Mêmes règles que les autres surcharges :
// chaque remplacement est indépendant et sans effet si la phrase cherchée disparaît (verifier_surcharges() le dit dans le journal).
function jarvisDepartFrance() {
  const MODIFS = {
    '/src/camera.js': [
      ['Cesium.Cartesian3.fromDegrees(-97.7431, 30.2672, 25000)', 'Cesium.Cartesian3.fromDegrees(4.39, 45.43, 2000000)'],
      ['Cesium.Cartesian3.fromDegrees(-97.7431, 30.2672, 600)', 'Cesium.Cartesian3.fromDegrees(4.39, 45.43, 400000)'],
      ['heading: Cesium.Math.toRadians(15),', 'heading: Cesium.Math.toRadians(0),'],
      ['pitch: Cesium.Math.toRadians(-30),', 'pitch: Cesium.Math.toRadians(-90),']],
    '/src/app/controls.js': [["t('Flying to Austin, TX...')", "t('Flying to Saint-Étienne, France...')"]],
  };
  return {
    name: 'jarvis-depart-france',
    enforce: 'pre',
    transform(code, id) {
      const chemin = id.split(String.fromCharCode(92)).join('/').split('?')[0];
      const cle = Object.keys(MODIFS).find((k) => chemin.endsWith(k));
      if (!cle) return null;
      let resultat = code;
      for (const [de, vers] of MODIFS[cle]) resultat = resultat.replace(de, () => vers);
      return resultat === code ? null : { code: resultat, map: null };
    },
  };
}

// Nuages Meteosat (EUMETSAT, service EUMETView, WMS sans clé, produits « Core » : licence CC BY 4.0, attribution « Contains modified EUMETSAT Meteosat data »). La couche « Satellite clouds » n'a que GOES (Amériques)
// et une mosaïque mondiale en retard de 2 à 3 h. Un TROISIÈME produit « clouds-europe » (infrarouge 10,5 µm de Meteosat Troisième Génération, une image toutes les 10 minutes, Europe et Afrique) est ajouté, avec ses
// vraies heures d'observation : 1. le relais /api/weather de l'appli répond pour ce produit seulement (les autres : le relais de l'appli) ; 2. les fichiers de la couche reçoivent le produit, son bouton « Europe » et son
// ouverture par défaut (chaque remplacement est indépendant et sans effet si la phrase cherchée disparaît : verifier_surcharges() le dit dans le journal).
const METEOSAT = {
  'clouds-europe': {
    couche: 'mtg_fd:ir105_hrfi', service: 'mtg_fd/ir105_hrfi', pas: 10 * 60000,
    title: 'Meteosat infrared · Europe and Africa',
    coverage: 'Meteosat 0° disc (Europe, Africa, Atlantic, Middle East), 70°S–70°N; not a global image.',
    description: 'Meteosat Third Generation FCI infrared 10.5 µm cloud and surface temperature patterns, 10-minute updates with about 25 minutes of latency. Not a cloud-only mask.',
  },
  'lightning-europe': {
    couche: 'mtg_fd:li_afa', service: 'mtg_fd/li_afa', pas: 5 * 60000,
    title: 'Meteosat lightning · accumulated flash area · 5 min',
    coverage: 'Meteosat 0° disc (Europe, Africa, Atlantic, Middle East), 70°S–70°N.',
    description: 'Meteosat Third Generation Lightning Imager accumulated flash area: optical flashes counted per 2 km pixel over 5 minutes, about 15 minutes of latency. Not a safety warning.',
  },
};
// Radar de pluie de Météo-France (lame d'eau, mosaïque métropole, clé .env METEOFRANCE_API_KEY) : un QUATRIÈME produit « radar-france » pour la couche « Rain radar » (États-Unis seulement), servi par le
// petit relais local de module/gev_radar_fr.py (lecture HDF5, reprojection, PNG à la demande) comme un service WMS. Sans clé : produit absent, la couche reste celle d'origine.
const RADAR_FR = process.env.JARVIS_RADAR_FR_URL || '';
if (RADAR_FR) METEOSAT['radar-france'] = {
  relais: true, pas: 5 * 60000,
  title: 'Météo-France radar · rain depth as dBZ equivalent',
  coverage: 'Metropolitan France and neighbouring seas (12°W–12°E, 40°N–52°N); gaps are not proof of no rain.',
  description: 'Météo-France radar mosaic: 500 m rain depth over 5 minutes, converted to a reflectivity equivalent (Marshall-Palmer), every 5 minutes. Not a rain forecast or a warning.',
};
function jarvisMeteosat() {
  const NL = String.fromCharCode(10);
  const metas = new Map(), images = new Map(), enCours = new Map(), attente = [];
  let octetsCache = 0, actifs = 0, minute = 0, compte = 0;
  const json = (res, code, corps) => { res.writeHead(code, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', ...(code === 429 ? { 'Retry-After': '2' } : {}) }); res.end(JSON.stringify(corps)); };
  const echec = (code, status = 503) => Object.assign(new Error(code), { code, status });
  async function prendre() { if (actifs >= 6) { if (attente.length >= 96) throw echec('weather_busy', 429); await new Promise((r) => attente.push(r)); } actifs += 1; }
  function rendre() { actifs -= 1; attente.shift()?.(); }
  async function amont(url, max, png) {   // hôte fixe, https, sans redirection, taille plafonnée
    const u = new URL(url);
    if (!(RADAR_FR && url.startsWith(RADAR_FR + '/')) && (u.protocol !== 'https:' || u.hostname !== 'view.eumetsat.int')) throw echec('hote');
    const ctl = new AbortController(), minuteur = setTimeout(() => ctl.abort(), 12000);
    try {
      const rep = await fetch(url, { signal: ctl.signal, redirect: 'error', headers: { Accept: png ? 'image/png' : 'text/xml', 'User-Agent': 'jarvis-gods-eye-view-meteosat/1.0' } });
      if (!rep.ok || (png && !/^image\/png/i.test(rep.headers.get('content-type') || ''))) { try { await rep.body?.cancel(); } catch { /* sans effet */ } throw echec('weather_upstream_unavailable HTTP ' + rep.status + ' ' + rep.headers.get('content-type')); }
      const morceaux = []; let total = 0;
      for await (const m of rep.body) { total += m.length; if (total > max) { ctl.abort(); throw echec('trop_gros'); } morceaux.push(m); }
      return Buffer.concat(morceaux);
    } finally { clearTimeout(minuteur); }
  }
  async function meta(produit) {
    const vieux = metas.get(produit), spec = METEOSAT[produit];
    if (vieux && Date.now() - vieux.at < (spec.relais ? 45000 : 120000)) return vieux;
    if (spec.relais) {   // relais local : les heures des images gardées (13 au plus), fenêtre de la mosaïque
      try {
        const j = JSON.parse((await amont(RADAR_FR + '/frames', 65536, false)).toString('utf8'));
        const times = Array.isArray(j.times) ? j.times.filter((t) => /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.000Z$/.test(t)).slice(-13) : [];
        const b = j.bounds || {};
        const limites = { west: Number(b.west), south: Number(b.south), east: Number(b.east), north: Number(b.north) };
        const dernier = Date.parse(times.at(-1) || '');
        if (!times.length || !Number.isFinite(dernier) || Date.now() - dernier > 3 * 3600000 || dernier > Date.now() + 300000 || !Object.values(limites).every(Number.isFinite)) throw echec('invalid_weather_metadata');
        const nouveau = { at: Date.now(), bounds: limites, times, stale: false };
        metas.set(produit, nouveau);
        return nouveau;
      } catch (e) {
        if (vieux && Date.now() - vieux.at < 3600000) return { ...vieux, stale: true };
        throw echec('weather_metadata_unavailable');
      }
    }
    try {
      const xml = (await amont(`https://view.eumetsat.int/geoserver/${spec.service}/wms?service=WMS&version=1.3.0&request=GetCapabilities`, 512 * 1024, false)).toString('utf8');
      const dim = /<Dimension\b[^>]*\bname="time"[^>]*>/.exec(xml);
      const dernier = dim && /\bdefault="([^"]+)"/.exec(dim[0])?.[1];
      const limites = {};
      for (const [k, tag] of [['west', 'westBoundLongitude'], ['south', 'southBoundLatitude'], ['east', 'eastBoundLongitude'], ['north', 'northBoundLatitude']]) limites[k] = Number(new RegExp('<' + tag + '>([^<]+)</' + tag + '>').exec(xml)?.[1]);
      if (!dernier || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(dernier) || !Number.isFinite(Date.parse(dernier)) || Date.now() - Date.parse(dernier) > 24 * 3600000 || Date.parse(dernier) > Date.now() + 300000) throw echec('invalid_weather_metadata');
      if (!Object.values(limites).every(Number.isFinite) || limites.west < -180 || limites.east > 180 || limites.south < -90 || limites.north > 90 || limites.west >= limites.east || limites.south >= limites.north) throw echec('invalid_weather_metadata');
      const times = Array.from({ length: 13 }, (_, i) => new Date(Date.parse(dernier) - (12 - i) * spec.pas).toISOString());
      const nouveau = { at: Date.now(), bounds: limites, times, stale: false };
      metas.set(produit, nouveau);
      return nouveau;
    } catch (e) {
      if (vieux && Date.now() - vieux.at < 3600000) return { ...vieux, stale: true };
      throw echec('weather_metadata_unavailable');
    }
  }
  function decrire(produit, m) {
    const spec = METEOSAT[produit], t = m?.times.at(-1) ?? null;
    return { schemaVersion: 1, product: produit, title: spec.title, coverage: spec.coverage, description: spec.description, source: spec.relais ? 'Météo-France radar' : 'EUMETSAT EUMETView', attribution: spec.relais ? 'Source : Météo-France (Licence Ouverte 2.0)' : 'Contains modified EUMETSAT Meteosat data ' + new Date().getUTCFullYear(),
      bounds: m?.bounds ?? null, times: m?.times ?? [], latest: t, time: t, observedAt: t, fetchedAt: m?.at ?? null, stale: m?.stale ?? true, unavailable: !m, reason: !m ? 'Weather imagery unavailable' : m.stale ? 'Cached weather metadata; upstream unavailable' : null,
      tileSize: 256, maxLevel: 6, tilingScheme: 'geographic',
      tileTemplate: t ? `/api/weather/tile?product=${produit}&time=${encodeURIComponent(t)}&z={z}&x={x}&y={y}` : null, imageUrl: t ? `/api/weather/image?product=${produit}&time=${encodeURIComponent(t)}` : null, imageSize: { width: 4096, height: 2048 } };
  }
  const arrondi = (n) => Math.round(n / 0.25) * 0.25 + 0;
  async function image(produit, req, url) {
    const complet = url.pathname === '/image', spec = METEOSAT[produit];
    const m = await meta(produit);
    if (m.stale) throw echec('weather_metadata_stale');
    const time = url.searchParams.get('time');
    if (!m.times.includes(time)) throw echec('unknown_weather_time', 400);
    let boite, largeur, hauteur;
    if (complet) {
      const brut = url.searchParams.get('bbox');
      if (brut) {
        const p = brut.split(',');
        if (p.length !== 4 || p.some((v) => !/^-?\d{1,3}(?:\.\d{1,6})?$/.test(v))) throw echec('invalid_weather_bbox', 400);
        boite = p.map((v) => arrondi(Number(v)));
        if (boite[0] >= boite[2] || boite[1] >= boite[3] || Math.abs((boite[2] - boite[0]) / (boite[3] - boite[1]) / 2 - 1) > 0.01 || boite[0] < m.bounds.west || boite[1] < m.bounds.south || boite[2] > m.bounds.east || boite[3] > m.bounds.north) throw echec('invalid_weather_bbox', 400);
      } else boite = [m.bounds.west, m.bounds.south, m.bounds.east, m.bounds.north];
      const taille = url.searchParams.get('size') ?? '4096x2048';
      if (!['1024x512', '2048x1024', '4096x2048'].includes(taille)) throw echec('invalid_weather_image_size', 400);
      [largeur, hauteur] = taille.split('x').map(Number);
    } else {
      const c = ['z', 'x', 'y'].map((k) => url.searchParams.get(k));
      if (c.some((v) => !/^(?:0|[1-9]\d{0,2})$/.test(v ?? ''))) throw echec('invalid_weather_tile', 400);
      const [z, x, y] = c.map(Number);
      if (z > 6 || x >= 2 ** (z + 1) || y >= 2 ** z) throw echec('invalid_weather_tile', 400);
      const pas = 180 / 2 ** z;
      boite = [-180 + x * pas, 90 - (y + 1) * pas, -180 + (x + 1) * pas, 90 - y * pas];
      largeur = hauteur = Number(url.searchParams.get('size') ?? '256');
      if (![256, 512, 1024].includes(largeur)) throw echec('invalid_weather_tile_size', 400);
    }
    const cle = `${produit}:${time}:${boite.join(',')}:${largeur}x${hauteur}`;
    let corps = images.get(cle);
    if (corps) { images.delete(cle); images.set(cle, corps); return corps.octets; }
    if (!enCours.has(cle)) {
      const adresse = spec.relais ? RADAR_FR + '/render?' + new URLSearchParams({ time, bbox: boite.join(','), size: largeur + 'x' + hauteur }).toString()
        : 'https://view.eumetsat.int/geoserver/wms?' + new URLSearchParams({ service: 'WMS', version: '1.1.1', request: 'GetMap', layers: spec.couche, styles: '', srs: 'EPSG:4326', bbox: boite.join(','), width: String(largeur), height: String(hauteur), format: 'image/png', transparent: 'true', time }).toString();
      enCours.set(cle, (async () => {
        await prendre();
        try {
          const plafond = complet ? 16 * 1024 * 1024 : Math.max(1024 * 1024, largeur * largeur * 4 + 65536);
          // EUMETView répond parfois 502 / 503 ou très lentement sous charge : une seconde tentative avant d'échouer (l'appli en refait 3 de son côté sur un 503)
          const octets = await amont(adresse, plafond, true).catch(async () => { await new Promise((r) => setTimeout(r, 700)); return amont(adresse, plafond, true); });
          if (octets.length < 33 || !octets.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])) || octets.readUInt32BE(16) !== largeur || octets.readUInt32BE(20) !== hauteur) throw echec('invalid_weather_image');
          while (images.size >= 96 || octetsCache + octets.length > 32 * 1024 * 1024) { const ancien = images.keys().next().value; octetsCache -= images.get(ancien).octets.length; images.delete(ancien); }
          images.set(cle, { octets }); octetsCache += octets.length;
          return octets;
        } finally { rendre(); }
      })().finally(() => enCours.delete(cle)));
    }
    return enCours.get(cle);
  }
  const relais = async (req, res, next) => {
    let url;
    try { url = new URL(req.url || '/', 'http://localhost'); } catch { return next(); }
    const produit = url.searchParams.get('product');
    if (!Object.hasOwn(METEOSAT, produit || '')) return next();   // les autres produits : le relais de l'appli
    if (req.method !== 'GET') return json(res, 405, { error: 'method_not_allowed' });
    const permis = { '/manifest': ['product'], '/image': ['product', 'time', 'size', 'bbox'], '/tile': ['product', 'time', 'z', 'x', 'y', 'size'] }[url.pathname];
    if (!permis || (req.url || '').length > 512 || [...url.searchParams.keys()].some((k) => !permis.includes(k) || url.searchParams.getAll(k).length !== 1)) return json(res, 400, { error: 'invalid_weather_query' });
    const maintenant = Date.now();
    if (maintenant - minute > 60000) { minute = maintenant; compte = 0; }
    if (++compte > 1200) return json(res, 429, { error: 'rate_limited' });
    try {
      if (url.pathname === '/manifest') {
        try { return json(res, 200, decrire(produit, await meta(produit))); } catch { return json(res, 200, decrire(produit, null)); }
      }
      const octets = await image(produit, req, url);
      res.writeHead(200, { 'Content-Type': 'image/png', 'Cache-Control': 'public, max-age=86400, immutable', 'X-Content-Type-Options': 'nosniff' });
      res.end(octets);
    } catch (e) { if (e.status !== 400) console.warn('[JARVIS] Meteosat ' + produit + ' ' + url.pathname + ' : ' + (e && (e.code ? e.code : e.stack)));
      json(res, e.status === 400 || e.status === 429 ? e.status : 503, { error: e.status === 400 || e.status === 429 ? e.code : 'weather_upstream_unavailable' }); }
  };
  const installer = (server) => { server.middlewares.use('/api/weather', relais); };
  const MODIFS = {
    '/src/layers/weather/source.js': [[/'clouds-regional',(\s*)'lightning',/, (m, s) => `'clouds-regional',${s}'clouds-europe',${s}'lightning',${s}'lightning-europe',`],
      ["lightning: Object.freeze({ width: 4096, height: 2048 }),", "lightning: Object.freeze({ width: 4096, height: 2048 }), 'lightning-europe': Object.freeze({ width: 4096, height: 2048 }),"],
      ["'clouds-regional': Object.freeze({ width: 4096, height: 2048 }),", "'clouds-regional': Object.freeze({ width: 4096, height: 2048 }), 'clouds-europe': Object.freeze({ width: 4096, height: 2048 }),"]],
    '/src/layers/weather/infraredImage.js': [["product === 'clouds' || product === 'clouds-regional'", "product === 'clouds' || product === 'clouds-regional' || product === 'clouds-europe'"]],
    '/src/layers/weather/rendering.js': [[/snapshot\.product === 'lightning'(\s*\? 3)/, (m, a) => `(snapshot.product === 'lightning' || snapshot.product === 'lightning-europe')${a}`], ["snapshot.product === 'clouds-regional'", "(snapshot.product === 'clouds-regional' || snapshot.product === 'clouds-europe')"],
      [": 'NOAA nowCOAST · NESDIS GOES / global satellite partners',", ": snapshot.product.endsWith('-europe') ? 'Contains modified EUMETSAT Meteosat data' : 'NOAA nowCOAST · NESDIS GOES / global satellite partners',"]],
    '/src/layers/weather/shellRendering.js': [["'clouds-regional': 5_800,", "'clouds-regional': 5_800, 'clouds-europe': 5_800,"], ["lightning: 6_600,", "lightning: 6_600, 'lightning-europe': 6_600,"],
      ["product === 'clouds' || product === 'clouds-regional'", "product === 'clouds' || product === 'clouds-regional' || product === 'clouds-europe'"]],
    '/src/data/layerState.js': [[/('weather-lightning': Object\.freeze\(\[\s*enumOption\('opacity', 'o', 'strong', \['light', 'strong'\], \{\s*light: 'l',\s*strong: 's',\s*\}\),)/, (m, a) => `${a} enumOption('product', 'p', 'lightning-europe', ['lightning', 'lightning-europe'], { lightning: 'a', 'lightning-europe': 'e' }, { absentValue: 'lightning' }),`], [/'clouds-regional',(\s*)\['clouds', 'clouds-regional'\],(\s*)\{ clouds: 'g', 'clouds-regional': 'r' \},/, (m, a, b) => `'clouds-europe',${a}['clouds', 'clouds-regional', 'clouds-europe'],${b}{ clouds: 'g', 'clouds-regional': 'r', 'clouds-europe': 'e' }, { absentValue: 'clouds-regional' },`]],
    '/src/layers/weather/index.js': [
      ["lightning ? 'lightning' : 'clouds-regional'", "lightning ? 'lightning-europe' : 'clouds-europe'"],
      ["['clouds', 'clouds-regional'].includes(params.product)", "['clouds', 'clouds-regional', 'clouds-europe'].includes(params.product)"],
      ["(product === 'clouds' ? 240 : lightning ? 45 : 20)", "(product === 'clouds' ? 240 : lightning || product === 'clouds-europe' ? 45 : 20)"],
      [": t('GOES INFRARED · ~5 min')", ": product === 'clouds-europe' ? t('METEOSAT INFRARED · ~10 min') : t('GOES INFRARED · ~5 min')"],
      [": t('North America · infrared imagery')", ": product === 'clouds-europe' ? t('Europe + Africa · infrared imagery') : t('North America · infrared imagery')"],
      [/(\? t\('Global · 60°S–60°N'\)\s*): t\('North America'\),/, (m, a) => `${a}: product === 'clouds-europe' ? t('Europe + Africa') : t('North America'),`],
      ["['clouds-regional', t('N. America')],", "['clouds-europe', t('Europe')], ['clouds-regional', t('N. America')],"],
      [/satellite &&(\s*)\['clouds', 'clouds-regional', 'clouds-europe'\]\.includes\(params\.product\) &&/, (m, a) => `(satellite || lightning) &&${a}(satellite ? ['clouds', 'clouds-regional', 'clouds-europe'] : ['lightning', 'lightning-europe']).includes(params.product) &&`],
      ["(lightning && lon > 0 && lon < 110)", "(lightning && product === 'lightning' && lon > 0 && lon < 110)"],
      [/const b = lightning(\s*\? \{ west: 110)/, (m, a) => `const b = lightning && product === 'lightning'${a}`],
      ["? t('LIGHTNING DENSITY · 15 min accumulation')", "? (product === 'lightning-europe' ? t('METEOSAT LIGHTNING · 5 min accumulated flash area') : t('LIGHTNING DENSITY · 15 min accumulation'))"],
      ["t('Americas + Pacific · not individual strikes')", "(product === 'lightning-europe' ? t('Europe + Africa · flashes counted per pixel') : t('Americas + Pacific · not individual strikes'))"],
      ["t('Color: strikes/km²/min ×10³')", "(product === 'lightning-europe' ? t('Color: flashes per 5 min') : t('Color: strikes/km²/min ×10³'))"],
      ["? t('Lightning density · 15 min')", "? (product === 'lightning-europe' ? t('Lightning · Meteosat 5 min') : t('Lightning density · 15 min'))"],
      ["? t('Americas + Pacific')", "? (product === 'lightning-europe' ? t('Europe + Africa') : t('Americas + Pacific'))"],
      ["lightning ? t('strikes/km²/min ×10³') : ''", "lightning ? (product === 'lightning-europe' ? t('flashes / 5 min') : t('strikes/km²/min ×10³')) : ''"],
      ["? t('View Americas & Pacific')", "? (product === 'lightning-europe' ? t('View Europe & Africa') : t('View Americas & Pacific'))"],
      ["const LIGHTNING_STOPS = [", "const LI_STOPS = [['1', '#FFFFCC'], ['5', '#FFA400'], ['10', '#FF4500'], ['20+', '#8B0020']];" + NL + "const LIGHTNING_STOPS = ["],
      ["(lightning ? LIGHTNING_STOPS : STOPS)", "(lightning ? (product === 'lightning-europe' ? LI_STOPS : LIGHTNING_STOPS) : STOPS)"],
      ["? t('{value} strikes/km²/min ×10³ (15-minute density)', {", "? t(product === 'lightning-europe' ? '{value} flashes per 5 minutes' : '{value} strikes/km²/min ×10³ (15-minute density)', {"],
      [/'NOAA\/NWS 15-minute lightning density derived from Vaisala NLDN\/GLD360\. Coverage 110°E[^']*'/, (m) => `(product === 'lightning-europe' ? 'Meteosat Third Generation Lightning Imager (EUMETSAT): optical flashes counted per 2 km pixel over 5 minutes; Europe, Africa and the Atlantic, 70°S–70°N. Not a safety warning.' : ${m})`],
      [/\.\.\.\['light', 'strong'\]\.map\(\(value\) => \(\{/, (m) => `...(lightning ? [['lightning-europe', t('Europe')], ['lightning', t('Americas')]].map(([value, label]) => ({ id: value, label, active: product === value, params: { product: value }, title: value === 'lightning' ? t('NOAA 15-minute lightning density; Americas and Pacific') : t('Meteosat 5-minute accumulated flash area; Europe and Africa') })) : []),${NL}          ${m}`],
      [/\{(\s*)id: 'opacity',(\s*)label: t\('OPACITY'\),/, (m, a, b) => `...(lightning ? [{ id: 'region', label: t('REGION'), chips: controls.chips.filter(({ params }) => params.product) }] : []), {${a}id: 'opacity',${b}label: t('OPACITY'),`],
      ["source: 'NOAA nowCOAST · OBSERVED',", "get source() { return product.endsWith('-europe') ? 'EUMETSAT Meteosat · OBSERVED' : 'NOAA nowCOAST · OBSERVED'; },"],
      [": t('GOES regional clouds; approximately 5-minute updates')", ": value === 'clouds-europe' ? t('Meteosat clouds over Europe and Africa; 10-minute updates') : t('GOES regional clouds; approximately 5-minute updates')"]],
    '/src/data/dataCredits.js': [[/\{(\s*)key: 'weather-noaa',/, (m, s) => `{ key: 'weather-eumetsat', html: 'Satellite clouds: Contains modified <a href="https://www.eumetsat.int/" target="_blank" rel="noopener">EUMETSAT</a> Meteosat data ' + new Date().getFullYear() + ' (<a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC BY 4.0</a>; images resampled and filtered for display)' },${NL}  { key: 'effis', html: 'Burnt areas in Europe: <a href="https://forest-fire.emergency.copernicus.eu/" target="_blank" rel="noopener">EFFIS</a> (European Commission, Joint Research Centre), <a href="https://forest-fire.emergency.copernicus.eu/about-effis/data-license" target="_blank" rel="noopener">CC BY 4.0</a>; geometry rounded, areas in hectares' },${NL}  {${s}key: 'weather-noaa',`]],
  };
  if (RADAR_FR) {   // radar de pluie français : appliqué APRÈS les remplacements ci-dessus (ceux de index.js partent de leur résultat)
    const ajouter = (fichier, liste) => { (MODIFS[fichier] ||= []).push(...liste); };
    ajouter('/src/layers/weather/source.js', [[/'radar',(\s*)'clouds',/, (m, s) => `'radar',${s}'radar-france',${s}'clouds',`],
      ["radar: Object.freeze({ width: 4096, height: 2048 }),", "radar: Object.freeze({ width: 4096, height: 2048 }), 'radar-france': Object.freeze({ width: 4096, height: 2048 }),"]]);
    ajouter('/src/layers/weather/rendering.js', [[/snapshot\.product === 'radar'(\s*\? 2)/, (m, a) => `(snapshot.product === 'radar' || snapshot.product === 'radar-france')${a}`],
      [/snapshot\.product === 'radar'(\s*)\? 'NOAA nowCOAST · NWS\/OAR MRMS'/, (m, s) => `snapshot.product === 'radar-france'${s}? 'Source : Météo-France'${s}: snapshot.product === 'radar'${s}? 'NOAA nowCOAST · NWS/OAR MRMS'`]]);
    ajouter('/src/layers/weather/shellRendering.js', [["radar: 6_200,", "radar: 6_200, 'radar-france': 6_200,"]]);
    ajouter('/src/data/layerState.js', [[/('weather-radar': Object\.freeze\(\[\s*enumOption\('opacity', 'o', 'strong', \['light', 'strong'\], \{\s*light: 'l',\s*strong: 's',\s*\}\),)/, (m, a) => `${a} enumOption('product', 'p', 'radar-france', ['radar', 'radar-france'], { radar: 'a', 'radar-france': 'f' }, { absentValue: 'radar' }),`]]);
    ajouter('/src/layers/weather/index.js', [
      ["radar ? 'radar' : lightning ? 'lightning-europe'", "radar ? 'radar-france' : lightning ? 'lightning-europe'"],
      ["(satellite || lightning) &&", "(satellite || lightning || radar) &&"],
      [": ['lightning', 'lightning-europe']).includes(params.product)", ": radar ? ['radar', 'radar-france'] : ['lightning', 'lightning-europe']).includes(params.product)"],
      [/return radar(\s*)\? \{ opacity \}/, (m, s) => `return radar${s}? { product, opacity }`],
      ["...(lightning ? [['lightning-europe', t('Europe')],", "...(radar ? [['radar-france', t('France')], ['radar', t('US')]].map(([value, label]) => ({ id: value, label, active: product === value, params: { product: value }, title: value === 'radar' ? t('NOAA MRMS radar; contiguous US') : t('Météo-France radar mosaic; metropolitan France') })) : [])," + NL + "          ...(lightning ? [['lightning-europe', t('Europe')],"],
      ["...(lightning ? [{ id: 'region',", "...(lightning || radar ? [{ id: 'region',"],
      ["t('RADAR REFLECTIVITY · dBZ')", "(product === 'radar-france' ? t('RAIN RADAR · Météo-France · dBZ equivalent') : t('RADAR REFLECTIVITY · dBZ'))"],
      ["t('Contiguous US · gaps ≠ no rain')", "(product === 'radar-france' ? t('France · gaps ≠ no rain') : t('Contiguous US · gaps ≠ no rain'))"],
      ["t('Rain radar · US')", "(product === 'radar-france' ? t('Rain radar · France') : t('Rain radar · US'))"],
      ["? 'CONUS'", "? (product === 'radar-france' ? 'France' : 'CONUS')"],
      ["t('View US radar')", "(product === 'radar-france' ? t('View France radar') : t('View US radar'))"],
      [/'NOAA MRMS radar echoes[^']*'/, (m) => `(product === 'radar-france' ? 'Météo-France radar mosaic (500 m rain depth over 5 minutes, shown as a dBZ equivalent by the Marshall-Palmer relation): precipitation patterns, not a rain forecast or a warning. Metropolitan France and nearby seas; gaps are not proof of no rain. History fills in as frames arrive (up to 13).' : ${m})`]]);
    ajouter('/src/data/dataCredits.js', [[/\{(\s*)key: 'weather-noaa',/, (m, s) => `{ key: 'weather-meteofrance', html: 'Rain radar France: Source <a href="https://meteo.data.gouv.fr/" target="_blank" rel="noopener">Météo-France</a> (Licence Ouverte 2.0); rain depth converted to a reflectivity equivalent, resampled for display' },${NL}  {${s}key: 'weather-noaa',`]]);
  }
  return {
    name: 'jarvis-meteosat',
    enforce: 'pre',   // avant le relais de l'appli, qui répondrait « produit inconnu » (400)
    configureServer: installer,
    configurePreviewServer: installer,
    transform(code, id) {
      const chemin = id.split(String.fromCharCode(92)).join('/').split('?')[0];
      const cle = Object.keys(MODIFS).find((k) => chemin.endsWith(k));
      if (!cle) return null;
      let resultat = code;
      for (const [de, vers] of MODIFS[cle]) resultat = typeof de === 'string' ? resultat.replace(de, () => vers) : resultat.replace(de, vers);
      return resultat === code ? null : { code: resultat, map: null };
    },
  };
}

// Couches ajoutées par JARVIS (script jarvis-couches.js, copié de module/gev_couches.js : voir son en-tête) : le script est ajouté à la page, et les fichiers de données (prix des carburants…) sont servis
// sur /__jarvis/<nom>.json (503 tant que JARVIS ne les a pas téléchargés en tâche de fond : la couche patiente).
const SCRIPT_COUCHES = path.join(path.dirname(fileURLToPath(import.meta.url)), 'jarvis-couches.js');
const FICHIERS_COUCHES = { '/__jarvis/carburants-fr.json': process.env.JARVIS_CARBURANTS_FILE || '' };
const DONNEES_DIR = process.env.JARVIS_DONNEES_DIR || '';
// Rangement des couches de JARVIS dans les catégories du panneau de l'appli (sans lui, elles tomberaient dans « Other layers ») : la liste PANEL_GROUPS de src/ui/layerPanel.js reçoit leurs identifiants.
// Chaque remplacement est indépendant ; verifier_surcharges() surveille la phrase la plus fragile.
const PLACEMENT_COUCHES = [
  ["'bikeshare',", "'bikeshare', 'fuel-prices-fr', 'ev-chargers-fr',"],
  ["'earthquakes',", "'earthquakes', 'earthquakes-fr',"],
  [/('air-quality',)(\s*'wind',)/, (m, a, b) => `${a} 'air-quality-fr',${b}`],
  [/('weather-cyclones',)(\s*\],\s*\},\s*\{\s*label: msg\('Utilities'\))/, (m, a, b) => `${a} 'flood-vigilance-fr', 'weather-alerts-fr',${b}`],
  ["ids: ['directions', 'radio'],", "ids: ['directions', 'radio', 'drone-zones-fr'],"],
];
// Français : langue ajoutée à la liste de l'appli (src/i18n/locale.js, index.js) et choisie PAR DÉFAUT à la place de la langue du navigateur ; le choix du sélecteur de langue (stocké) ou ?lang= reste prioritaire.
// Le catalogue (src/i18n/locales/fr.json) est écrit dans l'appli par `_ecrire_config` à chaque lancement.
const MODIFS_FR = {
  '/src/i18n/locale.js': [
    ["export const LOCALES = Object.freeze(['en', 'es', 'ru', 'zh-CN']);", "export const LOCALES = Object.freeze(['en', 'es', 'ru', 'zh-CN', 'fr']);"],
    ["'zh-CN': '简体中文',", "'zh-CN': '简体中文', fr: 'Français',"],
    ["  for (const candidate of Array.isArray(languages) ? languages : []) {", "  if (LOCALES.includes('fr')) return 'fr';   // JARVIS : français par défaut\n  for (const candidate of Array.isArray(languages) ? languages : []) {"],
  ],
  '/src/i18n/index.js': [
    ["import zhCN from './locales/zh-CN.json' with { type: 'json' };", "import zhCN from './locales/zh-CN.json' with { type: 'json' };\nimport fr from './locales/fr.json' with { type: 'json' };"],
    ["const CATALOGS = Object.freeze({ es, ru, 'zh-CN': zhCN });", "const CATALOGS = Object.freeze({ es, ru, 'zh-CN': zhCN, fr });"],
  ],
  '/src/ui/layerPanel.js': PLACEMENT_COUCHES,
  // villes du tiroir POSITION : New York, Paris et Tokyo en premier (avant : Austin, San Francisco, New York), les autres gardent leur ordre
  '/src/cityPois.js': [[/\n\};\s*$/, (m) => m + "\nfor (const cle of ['nyc', 'paris', 'tokyo', ...Object.keys(CITY_POIS).filter((k) => !['nyc', 'paris', 'tokyo'].includes(k))]) { const ville = CITY_POIS[cle]; delete CITY_POIS[cle]; CITY_POIS[cle] = ville; }\n"]],
};
function jarvisCouches() {
  return {
    name: 'jarvis-couches',
    enforce: 'pre',
    transform(code, id) {
      const chemin = id.split(String.fromCharCode(92)).join('/').split('?')[0];
      const cle = Object.keys(MODIFS_FR).find((k) => chemin.endsWith(k));
      if (!cle) return null;
      let resultat = code;
      for (const [de, vers] of MODIFS_FR[cle]) resultat = typeof de === 'string' ? resultat.replace(de, () => vers) : resultat.replace(de, vers);
      return resultat === code ? null : { code: resultat, map: null };
    },
    configureServer(server) {
      server.middlewares.use('/__jarvis/couches.js', (req, res) => {
        res.setHeader('Content-Type', 'text/javascript; charset=utf-8');
        res.setHeader('Cache-Control', 'no-store');
        try { res.end(fs.readFileSync(SCRIPT_COUCHES, 'utf8')); } catch { res.statusCode = 404; res.end(); }
      });
      // jeux de données téléchargés par module/gev_donnees_fr.py (liste blanche de noms, aucun chemin venant de la page)
      server.middlewares.use('/__jarvis/donnees', (req, res) => {
        const nom = /^\/(recharge|crues|seismes|air|vigilance)\.json$/.exec((req.url || '').split('?')[0])?.[1];
        if (req.method !== 'GET' || !nom || !DONNEES_DIR) { res.statusCode = nom ? 405 : 404; return res.end(); }
        try { const corps = fs.readFileSync(path.join(DONNEES_DIR, nom + '.json')); res.setHeader('Content-Type', 'application/json; charset=utf-8'); res.setHeader('Cache-Control', 'no-store'); res.end(corps); }
        catch { res.statusCode = 503; res.setHeader('Retry-After', '3'); res.end(); }
      });
      // restrictions de drones (IGN Géoplateforme, ~90 000 polygones : demandés par fenêtre visible, allégés, gardés 10 minutes) ; hôte fixe, fenêtre limitée à 1,2°
      const cacheDrones = new Map();
      // précision selon le zoom : ~1/1500 de la largeur de la fenêtre (4 m pour une vue de 60 m ... 70 m pour une vue de 1°), bornée ; un seul niveau grossier déformait les petites zones vues de près
      const allegerAnneau = (a, tol) => { const sortie = []; let dernier = null; for (const [x, y] of a) { if (!dernier || Math.abs(x - dernier[0]) > tol || Math.abs(y - dernier[1]) > tol) { dernier = [x, y]; sortie.push([Math.round(x * 1e5) / 1e5, Math.round(y * 1e5) / 1e5]); } } return sortie.length >= 4 ? sortie : null; };
      server.middlewares.use('/__jarvis/drones', async (req, res) => {
        const reponse = (code, corps) => { res.statusCode = code; res.setHeader('Content-Type', 'application/json; charset=utf-8'); res.setHeader('Cache-Control', 'no-store'); res.end(JSON.stringify(corps)); };
        let perime = null;
        try {
          const b = (new URL(req.url || '/', 'http://localhost').searchParams.get('bbox') || '').split(',').map(Number);
          if (req.method !== 'GET' || b.length !== 4 || !b.every(Number.isFinite) || b[0] >= b[2] || b[1] >= b[3] || b[2] - b[0] > 1.2 || b[3] - b[1] > 1.2 || b[0] < -180 || b[2] > 180 || b[1] < -90 || b[3] > 90) return reponse(400, { error: 'invalid_bbox' });
          const r = [Math.floor(b[0] * 100) / 100, Math.floor(b[1] * 100) / 100, Math.ceil(b[2] * 100) / 100, Math.ceil(b[3] * 100) / 100], cle = r.join(',');
          const vu = cacheDrones.get(cle); perime = vu || null;
          if (vu && Date.now() - vu.at < 600000) return reponse(200, vu.corps);
          const lire = async () => {
          const rep = await fetch('https://data.geopf.fr/wfs/ows?' + new URLSearchParams({ SERVICE: 'WFS', VERSION: '2.0.0', REQUEST: 'GetFeature', TYPENAMES: 'TRANSPORTS.DRONES.RESTRICTIONS:carte_restriction_drones_lf', COUNT: '600', OUTPUTFORMAT: 'application/json', BBOX: cle + ',EPSG:4326' }).toString(),
            { signal: AbortSignal.timeout(20000), redirect: 'error', headers: { 'User-Agent': 'jarvis-gods-eye-view-drones/1.0', Accept: 'application/json' } });
          if (!rep.ok) throw new Error('HTTP ' + rep.status);
          const texte = await rep.text();
          if (texte.length > 24 * 1024 * 1024) throw new Error('trop_gros');
          return JSON.parse(texte);   // texte de métriques ou page d'erreur au lieu de JSON : l'exception déclenche un nouvel essai
          };
          let geo = null;
          for (let essai = 0; essai < 3 && !geo; essai++) { try { geo = await lire(); } catch (e) { if (essai === 2 || (e && e.message === 'trop_gros')) throw e; await new Promise((ok) => setTimeout(ok, 600)); } }
          const corps = [], tol = Math.max(0.00004, Math.min(0.0008, (b[2] - b[0]) / 1500));
          for (const f of geo.features || []) {
            const g = f.geometry || {}, polys = g.type === 'MultiPolygon' ? g.coordinates : g.type === 'Polygon' ? [g.coordinates] : [];
            const lourds = polys.map((p) => p.map((an) => allegerAnneau(an, tol)).filter(Boolean)).filter((p) => p.length);
            if (lourds.length) corps.push([String((f.properties || {}).limite || ''), lourds, String((f.properties || {}).remarque || '').slice(0, 200)]);
          }
          if (cacheDrones.size >= 40) cacheDrones.delete(cacheDrones.keys().next().value);
          cacheDrones.set(cle, { at: Date.now(), corps });
          reponse(200, corps);
        } catch (e) { console.warn('[JARVIS] Drones IGN : ' + (e && e.message)); if (perime) return reponse(200, perime.corps); reponse(502, { error: 'upstream_unavailable' }); }
      });
      for (const [chemin, fichier] of Object.entries(FICHIERS_COUCHES)) {
        server.middlewares.use(chemin, (req, res) => {
          if (req.method !== 'GET') { res.statusCode = 405; return res.end(); }
          try {
            const corps = fs.readFileSync(fichier);
            res.setHeader('Content-Type', 'application/json; charset=utf-8'); res.setHeader('Cache-Control', 'no-store'); res.end(corps);
          } catch { res.statusCode = 503; res.setHeader('Retry-After', '3'); res.end(); }
        });
      }
    },
    transformIndexHtml: () => [{ tag: 'script', attrs: { src: '/__jarvis/couches.js', defer: true }, injectTo: 'body' }],
  };
}

// Clés de JARVIS dans le panneau « POWER UP » de l'appli (même forme que les autres : titre, ce qu'elle débloque, lien pour la créer, champ, état configuré). La liste des clés de l'appli est figée côté serveur
// ET plafonnée à 512 caractères (le jeton Météo-France en fait ~1 500) : on intercepte donc /api/setup/status (ajout de nos lignes) et /api/setup/keys (nos clés sont écrites dans le .env de l'appli
// avec la même écriture sûre : fichier temporaire 0600, durci, renommé ; les autres clés sont rejouées telles quelles à l'appli). Côté Python, module/gev_cles.py relit ce .env : rien n'est copié dans l'environnement.
const CLES_JARVIS = [
  { id: 'meteofrance', title: 'MÉTÉO-FRANCE', unlocks: 'Rain radar over France (free "Données radar" API key). Restart the view after saving.', getUrl: 'https://portail-api.meteofrance.fr/', envVars: ['METEOFRANCE_API_KEY'], tier: 'free', clientExposed: false },
  { id: 'windy', title: 'WINDY WEBCAMS', unlocks: 'Live webcams in the French camera pack (free Webcams API key). Restart the view after saving.', getUrl: 'https://api.windy.com/keys', envVars: ['WINDY_WEBCAMS_API_KEY'], tier: 'free', clientExposed: false },
];
function jarvisCles() {
  const DIR = path.dirname(fileURLToPath(import.meta.url)), FICHIER = path.join(DIR, '.env'), noms = new Set(CLES_JARVIS.flatMap((c) => c.envVars));
  const lire = () => { try { return fs.readFileSync(FICHIER, 'utf8'); } catch (e) { if (e && e.code === 'ENOENT') return ''; throw e; } };
  const valeurs = () => { const o = {}; try { for (const l of lire().split(/\r?\n/)) { const m = /^\s*(?:export\s+)?([A-Z0-9_]+)\s*=\s*(\S*)\s*$/.exec(l); if (m && noms.has(m[1])) o[m[1]] = m[2]; } } catch { /* illisible : rien de configuré */ } return o; };
  const entrees = () => { const v = valeurs(); return CLES_JARVIS.map((c) => { const set = c.envVars.every((n) => (v[n] || '').length > 0); return { ...c, envVars: [...c.envVars], set, managed: set ? 'file' : null }; }); };
  const repondre = (res, code, corps) => { res.statusCode = code; res.setHeader('Content-Type', 'application/json'); res.setHeader('Cache-Control', 'no-store'); res.setHeader('X-Frame-Options', 'DENY'); res.setHeader('Content-Security-Policy', "frame-ancestors 'none'"); res.end(JSON.stringify(corps)); };
  async function ecrire(mises) {   // mêmes précautions que l'appli : jamais à travers un lien symbolique, fichier temporaire 0600 durci avant d'y mettre le secret, puis renommé
    const core = await import(pathToFileURL(path.join(DIR, 'src', 'keySetupCore.mjs')).href);
    const { hardenCredentialFile } = await import(pathToFileURL(path.join(DIR, 'server', 'standalone', 'key-setup-hardening.mjs')).href);
    try { if (fs.lstatSync(FICHIER).isSymbolicLink()) throw new Error('lien symbolique'); } catch (e) { if (e && e.code !== 'ENOENT') throw e; }
    const tmp = path.join(DIR, '.env.' + Math.random().toString(16).slice(2, 10) + '.tmp'), fd = fs.openSync(tmp, 'wx', 0o600);
    let pret = false;
    try {
      if (!hardenCredentialFile(tmp)) throw Object.assign(new Error('durcissement'), { code: 'GEV_HARDEN_FAILED' });
      const tampon = Buffer.from(core.upsertDotenvValues(lire(), mises), 'utf8');
      for (let ecrit = 0; ecrit < tampon.length;) ecrit += fs.writeSync(fd, tampon, ecrit, tampon.length - ecrit);
      fs.fsyncSync(fd); pret = true;
    } finally { fs.closeSync(fd); if (!pret) fs.rmSync(tmp, { force: true }); }
    try { fs.renameSync(tmp, FICHIER); } catch (e) { fs.rmSync(tmp, { force: true }); throw e; }
    return core;
  }
  return {
    name: 'jarvis-cles',
    enforce: 'pre',
    apply: (_c, { command, isPreview }) => command === 'serve' && !isPreview,
    configureServer(server) {
      server.middlewares.use('/api/setup/status', (req, res, next) => {
        if (req.method !== 'GET') return next();
        const fin = res.end.bind(res);
        res.end = (donnees, ...suite) => {
          try {
            const j = JSON.parse(String(donnees));
            if (res.statusCode === 200 && Array.isArray(j.keys)) { j.keys.push(...entrees()); j.total = j.keys.length; j.setCount = j.keys.filter((k) => k.set).length; donnees = JSON.stringify(j); }
          } catch { /* réponse d'une autre forme (refus) : telle quelle */ }
          return fin(donnees, ...suite);
        };
        next();
      });
      server.middlewares.use('/api/setup/keys', (req, res, next) => {
        if (req.method !== 'POST') return next();
        let corps = '', lu = false;
        req.on('data', (c) => { if (!lu) { corps += c; if (corps.length > 16384) req.destroy(); } });
        req.on('end', async () => {
          if (lu) return;   // le rejeu ci-dessous refait émettre « end » à la requête : il ne doit pas nous rappeler
          lu = true;
          const rejouer = (texte) => { next(); setImmediate(() => { if (texte) req.emit('data', texte); req.emit('end'); }); };   // l'appli reçoit le corps (les écouteurs sont posés pendant next())
          let j;
          try { j = JSON.parse(corps || '{}'); } catch { return rejouer(corps); }
          if (!j || typeof j !== 'object' || Array.isArray(j)) return rejouer(corps);
          const miens = Object.keys(j).filter((n) => noms.has(n));
          if (!miens.length) return rejouer(corps);
          const autres = Object.fromEntries(Object.entries(j).filter(([n]) => !noms.has(n)));
          try {
            const core = await import(pathToFileURL(path.join(DIR, 'src', 'keySetupCore.mjs')).href);
            const adm = core.admitKeySetupRequest({ method: req.method, remoteAddress: req.socket?.remoteAddress, hostHeader: req.headers?.host, protocol: req.socket?.encrypted ? 'https:' : 'http:', origin: req.headers?.origin, contentType: req.headers?.['content-type'], proxyHeaders: req.headers || {}, env: process.env });
            if (!adm.ok) return repondre(res, adm.status, { error: adm.error, code: adm.code });
            const mises = {};
            for (const n of miens) {
              const v = j[n];
              if (v === null) { mises[n] = null; continue; }
              if (typeof v !== 'string') return repondre(res, 400, { error: n + ' must be a string', code: 'not-string', params: { name: n } });
              const t = v.trim();
              if (!t) return repondre(res, 400, { error: n + ' is empty', code: 'empty', params: { name: n } });
              if (t.length > 4096 || !/^[\x21-\x7e]+$/.test(t)) return repondre(res, 400, { error: n + ' is not a valid key', code: 'too-long', params: { name: n, limit: 4096 } });
              mises[n] = t;
            }
            if (Object.keys(autres).length) {   // les autres clés : l'appli répond, comme d'habitude (et redémarre) ; les nôtres sont écrites APRÈS sa réponse (le .env surveillé par Vite relancerait le serveur en pleine requête)
              res.on('finish', () => { if (res.statusCode === 200) ecrire(mises).catch((e) => console.warn('[JARVIS] Clé non enregistrée : ' + (e && e.message))); });
              return rejouer(JSON.stringify(autres));
            }
            await ecrire(mises);
            const statut = core.keySetupStatus(process.env);
            for (const k of statut.keys) k.managed = k.set ? 'file' : null;
            statut.keys.push(...entrees()); statut.total = statut.keys.length; statut.setCount = statut.keys.filter((k) => k.set).length; statut.store = 'env-file';
            repondre(res, 200, { ok: true, saved: miens, status: statut, restarting: true });
            setTimeout(() => { server.restart().catch((e) => console.warn('[JARVIS] Redémarrage après clé : ' + (e && e.message))); }, 250);
          } catch (e) {
            repondre(res, 500, { error: 'The key was not saved', code: e && e.code === 'GEV_HARDEN_FAILED' ? 'harden-failed' : 'write-failed', params: { store: 'env-file' } });
          }
        });
      });
    },
  };
}

// Zones brûlées en Europe (EFFIS, Commission européenne / Centre commun de recherche, service WFS public sans clé, couche « Burnt Areas MODIS, 30 derniers jours », licence CC BY 4.0, crédit « EFFIS »).
// La couche « Fire Perimeters » n'a que les États-Unis (NIFC) : le relais /api/fire-perimeters de l'appli répond comme d'habitude, et ce plugin AJOUTE à sa réponse les zones EFFIS, converties au format de ses lignes
// (le validateur de géométrie est celui de l'appli, chargé au démarrage : s'il disparaît, seul EFFIS est désactivé). Surface en hectares (champ « hectares », fiche adaptée), date de l'incendie et de mise à jour.
let normaliserPerimetres = null;
function jarvisEffis() {
  const URL_EFFIS = 'https://maps.effis.emergency.copernicus.eu/effis?service=WFS&version=2.0.0&request=GetFeature&typeNames=ms:modis.ba.poly.month&outputFormat=geojson&count=3000&sortBy=FIREDATE+D';
  let gardee = null, enCours = null;
  const arrondir = (c) => (typeof c === 'number' ? Math.round(c * 1e5) / 1e5 : Array.isArray(c) ? c.map(arrondir) : c);
  const ms = (texte) => { const v = Date.parse(String(texte || '').replace(' ', 'T') + 'Z'); return Number.isFinite(v) ? v : null; };
  async function charger() {
    const ctl = new AbortController(), minuteur = setTimeout(() => ctl.abort(), 30000);
    try {
      const rep = await fetch(URL_EFFIS, { signal: ctl.signal, redirect: 'error', headers: { Accept: 'application/json', 'User-Agent': 'jarvis-gods-eye-view-effis/1.0' } });
      if (!rep.ok || !/json/i.test(rep.headers.get('content-type') || '')) throw new Error('HTTP ' + rep.status);
      const morceaux = []; let total = 0;
      for await (const m of rep.body) { total += m.length; if (total > 24 * 1024 * 1024) { ctl.abort(); throw new Error('réponse trop grosse'); } morceaux.push(m); }
      const liste = JSON.parse(Buffer.concat(morceaux).toString('utf8'));
      if (!Array.isArray(liste.features)) throw new Error('réponse inattendue');
      const hectares = new Map();
      const features = liste.features.filter((f) => f && f.properties && f.geometry).map((f) => {
        const p = f.properties, id = 'effis:' + String(p.id);
        const lieu = [p.COMMUNE, p.PROVINCE].find((v) => v && v !== 'N.A.');
        hectares.set(id, Number(p.AREA_HA));
        return { type: 'Feature', id, geometry: { type: f.geometry.type, coordinates: arrondir(f.geometry.coordinates) }, properties: {
          attr_UniqueFireIdentifier: id, poly_IncidentName: (lieu || 'Burnt area') + ' (' + (p.COUNTRY || '?') + ')',   // le pays dans le nom : jamais pris pour un incendie américain de même nom (liens InciWeb)
          attr_POOState: [p.COUNTRY, p.PROVINCE && p.PROVINCE !== 'N.A.' ? p.PROVINCE : null].filter(Boolean).join(' · ') || null,
          attr_IncidentTypeCategory: 'Burnt area (EFFIS)', attr_FireDiscoveryDateTime: ms(p.FIREDATE), poly_DateCurrent: ms(p.LASTUPDATE) } };
      });
      return normaliserPerimetres({ features }).map((r) => ({ ...r, hectares: Number.isFinite(hectares.get(r.stableId)) ? hectares.get(r.stableId) : null }));
    } finally { clearTimeout(minuteur); }
  }
  async function lignes() {
    if (gardee && Date.now() - gardee.at < 15 * 60000) return gardee.rows;
    try {
      if (!enCours) enCours = charger().finally(() => { enCours = null; });
      const rows = await enCours;
      gardee = { at: Date.now(), rows };
      return rows;
    } catch { return gardee && Date.now() - gardee.at < 6 * 3600000 ? gardee.rows : []; }   // EFFIS indisponible : les États-Unis seuls
  }
  const relais = (req, res, next) => {
    const chemin = (req.url || '/').split('?')[0];
    if (req.method !== 'GET' || (chemin !== '/' && chemin !== '')) return next();
    const fin = res.end.bind(res);
    res.end = (corps, ...suite) => {
      if (res.statusCode !== 200) return fin(corps, ...suite);
      lignes().then((rows) => {
        let sortie = corps;
        try { const j = JSON.parse(String(corps)); if (Array.isArray(j.rows)) { j.rows.push(...rows); sortie = JSON.stringify(j); } } catch { /* réponse inchangée */ }
        fin(sortie, ...suite);
      }, () => fin(corps, ...suite));
      return res;
    };
    next();
  };
  const installer = (server) => { server.middlewares.use('/api/fire-perimeters', relais); };
  const MODIFS = { '/src/layers/perimeters/cards.js': [
    ['const facts = [];', "const facts = []; if (Number.isFinite(row.hectares)) facts.push(Math.round(row.hectares).toLocaleString('en-US') + ' ha');"],
    ["const details = [facts.join(' · ')];", "const details = [facts.filter((f) => !(row.hectares != null && f === t('containment unknown'))).join(' · ')];"]] };
  return {
    name: 'jarvis-effis',
    enforce: 'pre',
    configureServer: installer,
    configurePreviewServer: installer,
    transform(code, id) {
      const chemin = id.split(String.fromCharCode(92)).join('/').split('?')[0];
      const cle = Object.keys(MODIFS).find((k) => chemin.endsWith(k));
      if (!cle) return null;
      let resultat = code;
      for (const [de, vers] of MODIFS[cle]) resultat = resultat.replace(de, () => vers);
      return resultat === code ? null : { code: resultat, map: null };
    },
  };
}

export default async (env) => {
  const cfg = typeof base === 'function' ? await base(env) : base;
  try {
    ({ normalizeFirePerimeterSnapshot: normaliserPerimetres } = await import(pathToFileURL(path.join(path.dirname(fileURLToPath(import.meta.url)), 'src', 'layers', 'perimeters', 'records.js')).href));
    if (typeof normaliserPerimetres !== 'function') throw new Error('fonction absente');
  } catch (e) { normaliserPerimetres = null; console.warn('[JARVIS] Zones brûlées EFFIS désactivées : ' + (e && e.message)); }
  try {
    ({ buildTransitSnapshot, transitResponseHeaders } = await import(pathToFileURL(path.join(path.dirname(fileURLToPath(import.meta.url)), 'src', 'data', 'transitProxy.js')).href));
    if (typeof buildTransitSnapshot !== 'function' || typeof transitResponseHeaders !== 'function') throw new Error('fonctions absentes');
  } catch (e) { buildTransitSnapshot = null; console.warn('[JARVIS] Transit français désactivé : ' + (e && e.message)); }
  return mergeConfig(cfg, { plugins: [jarvisFraming(), jarvisPartage(), jarvisCadence(), jarvisVelosFrance(), ...(buildTransitSnapshot ? [jarvisTransitFrance()] : []), jarvisRadarsFrance(), jarvisMeteosat(), jarvisCles(), jarvisCouches(), ...(normaliserPerimetres ? [jarvisEffis()] : []), jarvisDepartFrance()] });
};
"""

_SCRIPT_PARTAGE = r"""// Écrit par JARVIS (backend/module/vue_de_dieu.py). Dans les Paramètres de l'appli, sur les cartes OpenAI et Gemini SANS clé, propose « utiliser la clé de JARVIS » :
// le clic demande au HUD de JARVIS (page parente) de faire copier la clé du .env de JARVIS dans le .env de l'appli (par le point d'entrée des Paramètres de l'appli).
// Inactif hors du HUD de JARVIS (page ouverte seule). La clé ne passe jamais par cette page.
(() => {
  if (window.parent === window) return;
  // Bandeau « SUMMARY » du HUD : l'appli le coupe en « … » à 420 px sur une seule ligne ; on le laisse passer sur deux lignes.
  const css = document.createElement('style');
  css.textContent = '#intel-hud .hud-summary-wrap{max-width:420px}'
    + '#intel-hud .hud-summary{white-space:normal!important;overflow:visible!important;text-overflow:clip!important;line-height:1.45;max-height:none!important}';
  document.head.append(css);
  const FOURNISSEURS = { openai: 'OpenAI', gemini: 'Gemini' };
  const bouton = (id) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'jarvis-partage';
    b.dataset.fournisseur = id;
    b.textContent = 'UTILISER LA CLÉ DE JARVIS';
    b.title = 'Copie la clé ' + FOURNISSEURS[id] + ' du .env de JARVIS dans le .env de cette appli (les deux restent ensuite indépendants)';
    b.style.cssText = 'margin:6px 0 2px;padding:5px 10px;font:inherit;font-size:10px;letter-spacing:.12em;cursor:pointer;color:#7fdcff;background:rgba(10,40,60,.55);border:1px solid rgba(127,220,255,.55);border-radius:3px';
    b.addEventListener('click', () => {
      if (b.disabled) return;
      b.disabled = true; b.textContent = 'COPIE EN COURS…';
      window.parent.postMessage({ jarvis: 'partager-cle', fournisseur: id }, '*');
    });
    return b;
  };
  const rafraichir = () => {
    for (const ligne of document.querySelectorAll('.key-setup-row[data-key-id]')) {
      const id = ligne.dataset.keyId;
      if (!FOURNISSEURS[id]) continue;
      const present = ligne.querySelector('.jarvis-partage');
      if (ligne.dataset.set !== 'false') { present?.remove(); continue; }
      if (!present) ligne.append(bouton(id));
    }
  };
  window.addEventListener('message', (e) => {
    if (e.source !== window.parent || !e.data || e.data.jarvis !== 'partage-resultat') return;
    const b = document.querySelector('.jarvis-partage[data-fournisseur="' + e.data.fournisseur + '"]');
    if (!b) return;
    b.textContent = String(e.data.texte || '').toUpperCase();
    b.disabled = !e.data.ok ? false : true;
    if (!e.data.ok) setTimeout(() => { b.textContent = 'UTILISER LA CLÉ DE JARVIS'; }, 6000);
  });
  new MutationObserver(rafraichir).observe(document.documentElement, { childList: true, subtree: true });
  rafraichir();
})();
"""


def _ecrire_si_different(chemin: str, contenu: str) -> None:
    try:
        with open(chemin, encoding="utf-8") as f:
            if f.read() == contenu:
                return
    except OSError:
        pass
    with open(chemin, "w", encoding="utf-8", newline="\n") as f:
        f.write(contenu)


def _ecrire_config(dossier: str) -> None:
    _ecrire_si_different(os.path.join(dossier, CONFIG_JARVIS), _CONFIG_VITE)
    _ecrire_si_different(os.path.join(dossier, "jarvis-partage.js"), _SCRIPT_PARTAGE)
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "gev_couches.js"), encoding="utf-8") as f:
            _ecrire_si_different(os.path.join(dossier, "jarvis-couches.js"), f.read())
    except OSError:
        pass
    try:   # traduction française complète (catalogue de l'appli, module/gev_fr.json) : un fichier de plus à côté de es.json / ru.json, enregistré par la surcharge de src/i18n
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "gev_fr.json"), encoding="utf-8") as f:
            os.makedirs(os.path.join(dossier, "src", "i18n", "locales"), exist_ok=True)
            _ecrire_si_different(os.path.join(dossier, "src", "i18n", "locales", "fr.json"), f.read())
    except OSError:
        pass
    _ecrire_si_different(os.path.join(dossier, "jarvis-transit-fr.json"), _catalogue_transit_fr())


# Phrases de l'appli que les surcharges de _CONFIG_VITE cherchent pour s'y accrocher. Si une mise à jour de l'appli en change une, la surcharge correspondante
# ne s'applique plus SANS erreur : verifier_surcharges() le dit dans le journal au lancement.
_ACCROCHES = (
    ("src/data/cctvLod.js", "const PROVIDER_STATIC_REFRESH_MS = Object.freeze({", "cadence des caméras de Lyon"),
    ("src/layers/bikeshare/registry.js", "const RAW_GBFS_CITY_REGISTRY = [", "vélos en libre-service français"),
    ("src/data/transitFeeds.js", "export const TRANSIT_FEED_REGISTRY = Object.freeze([", "transports en commun français"),
    ("src/layers/alpr/source.js", "export function createAlprTileSource({", "radars français (source de données)"),
    ("src/layers/alpr/visuals.js", "export function alprLabelDetails(record, source) {", "radars français (fiche)"),
    ("src/layers/alpr/presentation.js", "layerName: 'ALPR Cameras',", "radars français (nom du calque)"),
    ("src/camera.js", "Cesium.Cartesian3.fromDegrees(-97.7431, 30.2672, 600)", "ouverture de la vue sur la France"),
    ("src/layers/weather/source.js", "'clouds-regional': Object.freeze({ width: 4096, height: 2048 }),", "nuages Meteosat (produit)"),
    ("src/layers/weather/infraredImage.js", "product === 'clouds' || product === 'clouds-regional'", "nuages Meteosat (traitement de l'image)"),
    ("src/layers/weather/rendering.js", "snapshot.product === 'clouds-regional'", "nuages Meteosat (rendu)"),
    ("src/layers/weather/shellRendering.js", "'clouds-regional': 5_800,", "nuages Meteosat (rendu 3D)"),
    ("src/layers/weather/index.js", "['clouds-regional', t('N. America')],", "nuages Meteosat (bouton Europe)"),
    ("src/layers/weather/index.js", "lightning ? 'lightning' : 'clouds-regional'", "nuages Meteosat (produit par défaut)"),
    ("src/data/layerState.js", "{ clouds: 'g', 'clouds-regional': 'r' },", "nuages Meteosat (état partagé)"),
    ("src/layers/weather/source.js", "lightning: Object.freeze({ width: 4096, height: 2048 }),", "foudre Meteosat (produit)"),
    ("src/layers/weather/index.js", "const LIGHTNING_STOPS = [", "foudre Meteosat (légende)"),
    ("src/layers/weather/index.js", "? t('View Americas & Pacific')", "foudre Meteosat (textes et bouton Europe)"),
    ("src/data/layerState.js", "'weather-lightning': Object.freeze([", "foudre Meteosat (état partagé)"),
    ("src/data/dataCredits.js", "key: 'weather-noaa',", "crédits Meteosat et EFFIS"),
    ("src/ui/layerPanel.js", "ids: ['directions', 'radio'],", "couches ajoutées par JARVIS : rangement dans les catégories du panneau"),
    ("src/cityPois.js", "export const CITY_POIS = {", "ordre des villes du tiroir POSITION"),
    ("src/i18n/locale.js", "export const LOCALES = Object.freeze(['en', 'es', 'ru', 'zh-CN']);", "français (liste des langues)"),
    ("src/i18n/locale.js", "for (const candidate of Array.isArray(languages) ? languages : []) {", "français par défaut"),
    ("src/i18n/index.js", "const CATALOGS = Object.freeze({ es, ru, 'zh-CN': zhCN });", "français (catalogue)"),
    ("src/app/data.js", "window.__gevQaRegisterLayer = (targetManager, layerModule) => {", "couches ajoutées par JARVIS (carburants…) : point d'entrée de l'appli"),
    ("src/main.js", "allowQaRegistration: import.meta.env.DEV,", "couches ajoutées par JARVIS (carburants…) : mode développement"),
    ("src/layers/weather/source.js", "radar: Object.freeze({ width: 4096, height: 2048 }),", "radar de pluie Météo-France (produit)"),
    ("src/layers/weather/rendering.js", "? 'NOAA nowCOAST · NWS/OAR MRMS'", "radar de pluie Météo-France (rendu)"),
    ("src/layers/weather/shellRendering.js", "radar: 6_200,", "radar de pluie Météo-France (rendu 3D)"),
    ("src/data/layerState.js", "'weather-radar': Object.freeze([", "radar de pluie Météo-France (état partagé)"),
    ("src/layers/weather/index.js", "t('Rain radar · US')", "radar de pluie Météo-France (textes)"),
    ("src/layers/weather/index.js", "t('View US radar')", "radar de pluie Météo-France (bouton France)"),
    ("src/layers/perimeters/cards.js", "const details = [facts.join(' · ')];", "zones brûlées EFFIS (fiche en hectares)"),
)


def verifier_surcharges(dossier: str = None) -> list:
    """Noms des surcharges dont la phrase d'accroche a disparu de l'appli (liste vide si tout est en place). Affiche un avertissement par surcharge."""
    dossier = dossier or DOSSIER
    perdues = []
    for chemin, phrase, nom in _ACCROCHES:
        try:
            with open(os.path.join(dossier, *chemin.split("/")), encoding="utf-8") as f:
                present = phrase in f.read()
        except OSError:
            present = False
        if not present:
            perdues.append(nom)
            print(f"[VUE DE DIEU] Surcharge inactive : {nom} ({chemin} a changé dans l'appli, à adapter dans backend/module/vue_de_dieu.py)")
    return perdues


def _catalogue_transit_fr() -> str:
    """Réseaux français de transport en commun (module/gev_transit_fr_catalogue.json), lus par le plugin jarvisTransitFrance. « [] » si le fichier manque : le plugin ne fait alors rien."""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "gev_transit_fr_catalogue.json"), encoding="utf-8") as f:
            reseaux = json.load(f)
        champs = ("id", "name", "operator", "region", "center", "loadRadiusKm", "url", "license", "licenseUrl", "attribution")
        return json.dumps([{k: r[k] for k in champs} for r in reseaux], ensure_ascii=False)
    except (OSError, ValueError, KeyError) as e:
        print(f"[VUE DE DIEU] Catalogue des transports français illisible : {e}")
        return "[]"


def _inutile(nom: str) -> bool:
    """Fichiers de la release inutiles à l'exécution (démonstrations animées, modèles de tickets) : ils pèsent ~70 Mo."""
    return "/docs/media/" in nom or "/.github/" in nom or "/changelog.d/" in nom or "/pinokio/" in nom


def _extraire(archive: str, dest: str, progres) -> str:
    """Extrait la release (dossier racine `<auteur>-<dépôt>-<sha>/`) dans `dest` sans les fichiers inutiles ; renvoie le dossier de l'appli."""
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        membres = z.infolist()
        racine = membres[0].filename.split("/")[0] + "/"
        for i, m in enumerate(membres):
            if _annuler.is_set():
                raise Annule()
            if m.is_dir() or not m.filename.startswith(racine) or _inutile("/" + m.filename):
                continue
            cible = os.path.join(dest, *m.filename[len(racine):].split("/"))
            os.makedirs(os.path.dirname(cible), exist_ok=True)
            with z.open(m) as src, open(cible, "wb") as dst:
                shutil.copyfileobj(src, dst)
            if i % 150 == 0:
                progres("EXTRACTION DES FICHIERS…", i / len(membres))
    if not os.path.isfile(os.path.join(dest, "package.json")):
        raise ErreurInstall("L'archive téléchargée ne ressemble pas à God's Eye View.")
    return dest


_VARIABLES_SYSTEME = {
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "TEMP", "TMP", "USERNAME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
    "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432", "COMMONPROGRAMFILES", "COMMONPROGRAMFILES(X86)",
    "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "OS", "LANG", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY", "NODE_EXTRA_CA_CERTS",
}


def _environnement(extra: dict) -> dict:
    """Environnement d'un processus de God's Eye View : seulement ce que Windows et Node demandent. JARVIS charge son .env dans son propre
    environnement (Gemini, OpenAI, Groq, Home Assistant…) : le copier en entier donnerait toutes ses clés à une appli tierce, qui les afficherait
    « configurées en externe » (lecture seule). Les clés de God's Eye View vivent dans SON .env ; JARVIS ne les y copie que sur demande
    (bouton « utiliser la clé de JARVIS », voir partager_cle)."""
    env = {k: v for k, v in os.environ.items() if k.upper() in _VARIABLES_SYSTEME}
    env.update(extra)
    return env


# Clés de JARVIS que God's Eye View sait utiliser (contrôle vocal) : copiées dans le .env de God's Eye View sur demande, jamais partagées.
CLES_PARTAGEABLES = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}


def partager_cle(fournisseur: str):
    """Copie la clé OpenAI ou Gemini de JARVIS dans le .env de God's Eye View, par SON propre point d'entrée (POST /api/setup/keys, celui de son
    panneau Paramètres : il écrit son .env en lecture réservée au propriétaire puis redémarre). Après la copie, les deux .env sont indépendants.
    Renvoie (ok, message) ; la clé n'est jamais journalisée ni renvoyée."""
    nom = CLES_PARTAGEABLES.get(str(fournisseur).lower())
    if not nom:
        return False, "Fournisseur inconnu."
    valeur = (os.environ.get(nom) or "").strip()
    if not valeur:
        return False, f"JARVIS n'a pas de clé {fournisseur} dans son .env."
    if not en_ecoute():
        return False, "La vue de Dieu n'est pas ouverte."
    try:
        r = requests.post(f"{URL}api/setup/keys", json={nom: valeur}, headers={"Origin": f"http://{HOTE}:{PORT}"}, timeout=15)
    except requests.RequestException:
        return False, "La vue de Dieu ne répond pas."
    try:
        corps = r.json()
    except ValueError:
        corps = {}
    if r.ok and corps.get("ok"):
        return True, "Clé copiée."
    if corps.get("code") == "external":
        return False, "Cette clé est déjà fournie à la vue de Dieu par l'environnement."
    return False, "La vue de Dieu a refusé la clé."


def _npm_ci(node: str, dossier: str, progres) -> None:
    npm = _npm_cli(node)
    if not npm:
        raise ErreurInstall("npm est introuvable avec ce Node.js.")
    env = _environnement({"PUPPETEER_SKIP_DOWNLOAD": "1", "PATH": os.path.dirname(node) + os.pathsep + os.environ.get("PATH", "")})
    progres("INSTALLATION DES DÉPENDANCES · 2 À 5 MINUTES", None)
    os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
    with open(JOURNAL, "ab") as journal:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        p = subprocess.Popen([node, npm, "ci", "--no-audit", "--no-fund"], cwd=dossier, env=env, stdout=journal, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, creationflags=flags)
        debut = time.time()
        while p.poll() is None:
            if _annuler.is_set() or time.time() - debut > 20 * 60:
                _tuer(p)
                raise Annule() if _annuler.is_set() else ErreurInstall("L'installation des dépendances est trop longue : abandon.")
            time.sleep(0.5)
    if p.returncode != 0:
        raise ErreurInstall("L'installation des dépendances a échoué (détails dans data/gods_eye_view.log).")


def _tuer(p) -> None:
    try:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, timeout=10)
    except Exception:
        try:
            p.terminate()
        except Exception:
            pass


_job = None   # poignée du « job » Windows qui tue le serveur de la vue quand JARVIS disparaît (doit rester vivante tant que JARVIS tourne)


def _lier_a_jarvis(p) -> None:
    """Windows : place le serveur dans un « job » à fermeture forcée : quand JARVIS disparaît, de quelque façon que ce soit (fenêtre fermée, processus tué, plantage),
    Windows tue le serveur et ses fils. Sans cela, atexit ne passe que pour une sortie propre et un serveur orphelin restait en route (ancienne configuration réutilisée).
    Jamais bloquant : en cas d'échec le serveur tourne comme avant (arrêt par arreter() et atexit)."""
    global _job
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes

        class _Compteurs(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in ("lectures", "ecritures", "autres", "octets_lus", "octets_ecrits", "octets_autres")]

        class _Base(ctypes.Structure):
            _fields_ = [("temps_processus", ctypes.c_longlong), ("temps_job", ctypes.c_longlong), ("drapeaux", wintypes.DWORD),
                        ("memoire_min", ctypes.c_size_t), ("memoire_max", ctypes.c_size_t), ("limite_processus", wintypes.DWORD),
                        ("affinite", ctypes.c_size_t), ("priorite", wintypes.DWORD), ("ordonnancement", wintypes.DWORD)]

        class _Etendu(ctypes.Structure):
            _fields_ = [("base", _Base), ("compteurs", _Compteurs), ("memoire_processus", ctypes.c_size_t), ("memoire_job", ctypes.c_size_t),
                        ("pic_processus", ctypes.c_size_t), ("pic_job", ctypes.c_size_t)]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        if _job is None:
            job = k32.CreateJobObjectW(None, None)
            if not job:
                raise OSError(ctypes.get_last_error(), "CreateJobObject")
            info = _Etendu()
            info.base.drapeaux = 0x2000   # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):   # 9 = JobObjectExtendedLimitInformation
                raise OSError(ctypes.get_last_error(), "SetInformationJobObject")
            _job = job
        if not k32.AssignProcessToJobObject(_job, int(p._handle)):
            raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject")
    except Exception as e:  # noqa: BLE001
        print(f"[VUE DE DIEU] Arrêt automatique avec JARVIS indisponible : {type(e).__name__} {e}")


def _deplacer(src: str, dst: str) -> None:
    """Renomme un dossier. Sous Windows, l'antivirus ou l'indexation peuvent tenir un fichier ouvert quelques secondes (PermissionError) :
    on réessaie, puis on retombe sur une copie suivie d'une suppression."""
    derniere = None
    for _ in range(10):
        try:
            os.replace(src, dst)
            return
        except PermissionError as e:
            derniere = e
            time.sleep(1.5)
    try:
        shutil.move(src, dst)
    except Exception:
        raise derniere


def _conserver_reglages(ancien: str, nouveau: str) -> list:
    """Reprend dans la nouvelle version les fichiers de réglages de l'utilisateur : les clés API saisies dans l'appli (bouton « ALLUMER »)
    sont écrites par God's Eye View dans le `.env` de son propre dossier, jamais dans celui de JARVIS. Sans cette copie, une mise à jour
    (qui remplace tout le dossier) les effacerait. Renvoie les noms copiés."""
    copies = []
    if not os.path.isdir(ancien):
        return copies
    for nom in os.listdir(ancien):
        if nom == ".env" or (nom.startswith(".env.") and nom != ".env.example"):
            try:
                shutil.copy2(os.path.join(ancien, nom), os.path.join(nouveau, nom))
                copies.append(nom)
            except OSError:
                pass
    return copies


def installer(release: dict, progres):
    """Installe (ou met à jour) l'appli depuis `release` ; bloquant : à lancer dans un thread. `progres(texte, fraction ou None)`.
    L'ancienne version n'est remplacée qu'à la toute fin : un échec ou une annulation la laisse intacte. Renvoie (ok, message à dire)."""
    global installation_en_cours
    installation_en_cours = True
    _annuler.clear()
    nouveau = os.path.join(DATA, "app_nouveau")
    ancien = os.path.join(DATA, "app_ancien")
    try:
        if os.name != "nt":
            raise ErreurInstall("L'installation automatique n'est prévue que pour Windows.")
        os.makedirs(TMP, exist_ok=True)
        node = _node() or _installer_node_portable(progres)
        archive = os.path.join(TMP, "gods-eye-view.zip")
        _telecharger(release["zip"], archive, progres, f"TÉLÉCHARGEMENT DE GOD'S EYE VIEW {release['tag']}")
        _extraire(archive, nouveau, progres)
        _ecrire_config(nouveau)
        _npm_ci(node, nouveau, progres)
        if not os.path.isfile(os.path.join(nouveau, "node_modules", "vite", "bin", "vite.js")):
            raise ErreurInstall("L'installation est incomplète (le serveur de l'appli est absent).")
        progres("FINALISATION…", 0.97)
        _conserver_reglages(DOSSIER, nouveau)    # clés API et réglages de l'utilisateur : survivent à la mise à jour
        arreter()                             # un serveur en cours verrouillerait les fichiers de l'ancienne version
        shutil.rmtree(ancien, ignore_errors=True)
        if os.path.isdir(DOSSIER):
            _deplacer(DOSSIER, ancien)
        try:
            _deplacer(nouveau, DOSSIER)
        except Exception:
            if os.path.isdir(ancien) and not os.path.isdir(DOSSIER):
                _deplacer(ancien, DOSSIER)
            raise
        shutil.rmtree(ancien, ignore_errors=True)
        v = _lire_version()
        v.update({"tag": release["tag"], "installee_le": time.strftime("%Y-%m-%d"), "nouvelle": None, "refusee": None, "derniere_verif": time.time()})
        _ecrire_version(v)
        return True, None
    except Annule:
        return False, "Installation annulée."
    except ErreurInstall as e:
        return False, str(e)
    except requests.RequestException:
        return False, "Le téléchargement a échoué : vérifiez la connexion internet."
    except Exception as e:
        return False, f"L'installation a échoué ({type(e).__name__})."
    finally:
        installation_en_cours = False
        shutil.rmtree(nouveau, ignore_errors=True)
        shutil.rmtree(TMP, ignore_errors=True)


# ───────────────────────────── Serveur local ─────────────────────────────
def en_ecoute() -> bool:
    try:
        with socket.create_connection((HOTE, PORT), timeout=0.3):
            return True
    except OSError:
        return False


def _serveurs_de_la_vue() -> list:
    """Processus (psutil) qui sont un serveur de la vue de CE dossier : leur ligne de commande contient notre config et le dossier de l'appli.
    Cherchés dans la liste des processus et non par le port : psutil ne montre pas toujours le socket en écoute, et un serveur sans réponse n'écoute plus."""
    import psutil
    norm = os.path.normcase(os.path.abspath(DOSSIER))
    trouves = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            ligne = os.path.normcase(" ".join(proc.info["cmdline"] or []))
        except Exception:  # noqa: BLE001
            continue
        if CONFIG_JARVIS.lower() in ligne and norm in ligne and proc.pid != os.getpid():
            trouves.append(proc)
    return trouves


def _arreter_serveur_orphelin() -> bool:
    """Arrête un serveur de la vue laissé par un JARVIS précédent (fermé sans passer par atexit : fenêtre fermée, processus tué, plantage), ou resté après la fermeture de la vue.
    Sans cela, le nouveau JARVIS le réutilise : ancienne configuration, ancien script injecté, ancien état. Ne touche qu'un processus dont la ligne de commande est celle
    de CE dossier d'appli avec notre config : un serveur lancé à la main ou un autre programme sur le port restent intacts. Renvoie True si le port est libre à la fin."""
    try:
        import psutil
        for proc in _serveurs_de_la_vue():
            try:
                for fils in proc.children(recursive=True):
                    try:
                        fils.kill()
                    except psutil.Error:
                        pass   # conhost.exe (fenêtre de console) refuse d'être tué : sans importance, il disparaît avec le serveur
                proc.kill()
                proc.wait(timeout=5)
            except psutil.NoSuchProcess:
                continue
            except (psutil.AccessDenied, psutil.TimeoutExpired):
                # psutil n'a pas pu l'arrêter : secours par taskkill (arbre entier), toujours limité à un processus reconnu comme le nôtre
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for _ in range(20):
            if not en_ecoute():
                print("[VUE DE DIEU] Ancien serveur arrêté")
                return True
            time.sleep(0.25)
    except Exception:  # noqa: BLE001 : jamais bloquant, on retombe sur la réutilisation
        pass
    return not en_ecoute()


def demarrer():
    """Lance le serveur s'il ne tourne pas (sans attendre qu'il réponde : le HUD patiente). Renvoie (ok, message d'erreur à dire)."""
    global _proc
    with _verrou:
        if en_ecoute():
            if _proc is not None and _proc.poll() is None:
                return True, None   # c'est celui de cette session
            if not (installee() and _arreter_serveur_orphelin()):
                return True, None   # pas le nôtre ou impossible à arrêter : on l'utilise tel quel
        if not installee():
            return False, "God's Eye View n'est pas installé sur cet ordinateur."
        node = _node()
        if not node:
            return False, "God's Eye View demande Node.js 24 ou plus, qui n'est pas disponible sur cet ordinateur."
        try:   # caméras françaises (Lyon…) : pack de sources personnalisé, voir module/gev_cameras_fr.py
            from module import gev_cameras_fr
            cameras_fr = gev_cameras_fr.preparer()
        except Exception as e:  # noqa: BLE001 : jamais bloquant pour l'ouverture de la vue
            print(f"[CAMERAS FR] Pack indisponible : {type(e).__name__}")
            cameras_fr = {}
        try:   # radars français : téléchargement en tâche de fond, voir module/gev_radars_fr.py
            from module import gev_radars_fr
            radars_fr = gev_radars_fr.preparer()
        except Exception as e:  # noqa: BLE001
            print(f"[RADARS FR] Indisponibles : {type(e).__name__}")
            radars_fr = {}
        try:   # radar de pluie Météo-France : relais local + mise à jour en tâche de fond (clé METEOFRANCE_API_KEY), voir module/gev_radar_fr.py
            from module import gev_radar_fr
            radar_fr = gev_radar_fr.demarrer()
        except Exception as e:  # noqa: BLE001
            print(f"[RADAR FR] Indisponible : {type(e).__name__}")
            radar_fr = {}
        try:   # prix des carburants : téléchargement en tâche de fond, voir module/gev_carburants_fr.py
            from module import gev_carburants_fr
            carburants_fr = gev_carburants_fr.preparer()
        except Exception as e:  # noqa: BLE001
            print(f"[CARBURANTS FR] Indisponibles : {type(e).__name__}")
            carburants_fr = {}
        try:   # recharge, crues, séismes, qualité de l'air : téléchargements en tâche de fond, voir module/gev_donnees_fr.py
            from module import gev_donnees_fr
            donnees_fr = gev_donnees_fr.demarrer()
        except Exception as e:  # noqa: BLE001
            print(f"[DONNEES FR] Indisponibles : {type(e).__name__}")
            donnees_fr = {}
        env = _environnement({"HOST": HOTE, "PORT": str(PORT), "GEV_EMBED_FRAME_ANCESTORS": ORIGINES_HUD, "BROWSER": "none", "PUPPETEER_SKIP_DOWNLOAD": "1",
                              "PATH": os.path.dirname(node) + os.pathsep + os.environ.get("PATH", ""), **cameras_fr, **radars_fr, **radar_fr, **carburants_fr, **donnees_fr})
        try:
            _ecrire_config(DOSSIER)
            verifier_surcharges()
            os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
            journal = open(JOURNAL, "ab")
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            _proc = subprocess.Popen([node, VITE, "--config", CONFIG_JARVIS, "--strictPort"], cwd=DOSSIER, env=env, stdout=journal,
                                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=flags)
            _lier_a_jarvis(_proc)
        except Exception as e:
            return False, f"God's Eye View n'a pas pu démarrer ({type(e).__name__})."
        return True, None


def arreter() -> None:
    """Arrête le serveur de la vue (et ses processus fils) : celui de cette session, et aussi un serveur laissé par un JARVIS précédent
    (reconnu à sa ligne de commande : notre config dans le dossier de l'appli), sans quoi « ferme la vue de Dieu », la croix du HUD et la sortie de JARVIS
    le laissaient tourner."""
    global _proc, ouverte
    ouverte = False
    with _verrou:
        p, _proc = _proc, None
    if p is not None and p.poll() is None:
        _tuer(p)
    if en_ecoute():
        _arreter_serveur_orphelin()
    try:
        from module import gev_radar_fr, gev_donnees_fr
        gev_radar_fr.arreter()
        gev_donnees_fr.arreter()
    except Exception:  # noqa: BLE001
        pass


def signaler_hud(visible: bool) -> None:
    """Le HUD annonce que la vue est affichée ou fermée (croix, Échap, ou commande vocale). Fermée pendant une installation : on l'annule."""
    global ouverte
    ouverte = bool(visible)
    if not visible:
        if installation_en_cours:
            _annuler.set()
        arreter()


def _arreter_a_la_sortie() -> None:
    """À la fermeture du processus : n'arrête QUE le serveur lancé par ce processus, jamais celui d'un autre. Avant, `arreter()` (qui supprime aussi les serveurs « orphelins »)
    passait ici : tout programme Python qui importait ce module (banc de test, script d'essai) tuait en se terminant le serveur de la vue de JARVIS en cours (vécu le 13/11/2026)."""
    global _proc
    with _verrou:
        p, _proc = _proc, None
    if p is not None and p.poll() is None:
        _tuer(p)


atexit.register(_arreter_a_la_sortie)
