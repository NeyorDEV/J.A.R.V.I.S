"""Resolver local du globe 3D : navigation, itinéraires, position et zoom (sans IA).

Seul resolver du globe : l'ancien plugins/globe_resolver.py s'enregistrait sous le même
nom (builtins.resoudre_globe_localement) et l'emportait ou non selon l'ordre de
chargement au démarrage ; il a été supprimé.
"""

import asyncio
import builtins
import json
import os
import re
import subprocess
import time

import core.shared as shared
from core.interlocuteur import nom_virgule
from core.web_bridge import geocode_lieu_detaille, nom_lieu_inverse, send_globe_command

# Un lieu n'est retenu que si Nominatim le juge assez important : les faux positifs
# (« La Terre », lieu-dit près de La Rochelle ; « Ma position », un centre au Bénin ;
# une rue, un restaurant...) sont sous 0,2, les vrais lieux au-dessus de 0,5, même les
# petits villages (Retournac : 0,52).
IMPORTANCE_MIN = 0.3

# « Montre-moi la Terre » doit afficher le globe, pas chercher un lieu nommé « Terre »
_LA_TERRE = {"terre", "la terre", "planete", "planète", "la planete", "la planète", "planete terre",
             "planète terre", "le globe", "globe", "monde", "le monde", "globe terrestre"}

_mots_fermer = ["ferme la carte", "ferme le globe", "ferme globe", "cache la carte",
                "cache le globe", "ferme la navigation", "quitte le globe", "quitte globe",
                "sors du globe", "sortir du globe", "quitter le globe", "quitter globe",
                "retour à jarvis", "masque la carte"]

_mots_globe = ["affiche la terre", "montre la terre", "montre-moi la terre", "montre moi la terre",
               "globe terrestre", "affiche le globe", "vue de la terre", "zoom sur la terre",
               "vue spatiale", "vue depuis l'espace", "vue de l'espace",
               "montre la planète", "affiche la planète",
               "zoom arrière total", "zoom arriere total", "dézoom total", "dezoom total"]

# Déclencheurs explicitement géographiques : si le lieu est introuvable, on le dit.
_mots_lieu_explicites = ["survole", "navigue vers", "va vers", "vol vers", "vole vers", "zoome sur",
                         "zoom sur", "fais un survol de", "localise", "situe sur la carte"]
# Déclencheurs génériques (« trouve », « où est »...) : servent aussi hors géographie ;
# sans vrai lieu, on laisse la phrase aux autres resolvers / à l'IA.
_mots_lieu_generiques = ["affiche-moi", "affiche moi", "affiche", "montre-moi", "montre moi", "montre",
                         "trouve", "où est", "ou est", "situe", "où se trouve", "ou se trouve", "direction"]

_mots_route = ["trace un itinéraire", "trace l'itinéraire", "itinéraire de", "itineraire de",
               "route de", "chemin de", "comment aller de",
               "trace une route de", "trajet de", "trajet depuis"]

_mots_position = ["ma position", "où suis-je", "ou suis-je",
                  "affiche ma position", "montre ma position",
                  "localise-moi", "localise moi", "où je suis"]

_mots_dezoom = ["dézoome", "dezoome", "dézoom", "dezoom", "zoom arrière", "zoom arriere",
                "éloigne", "eloigne", "prends de la hauteur", "plus loin"]
_mots_zoom = ["zoome", "zoom avant", "rapproche", "plus près", "plus pres"]

# Après le déclencheur : les mots à retirer devant le nom du lieu
_ARTICLES = ["sur la carte ", "sur le globe ", "la ville de ", "la ville ", "le pays ", "le ", "la ", "l'",
             "les ", "ma ville ", "mon pays "]


def _distance_vol(rang):
    """Distance de la caméra au centre de la Terre (rayon 100) selon le type de lieu :
    plus loin pour un continent ou un pays, plus près pour une ville. Reste au-dessus du
    seuil de 175 où le globe bascule sur la carte 2D détaillée."""
    if rang <= 4:
        return 380
    if rang <= 12:
        return 300
    return 230


def _position_configuree():
    """(lat, lon, ville) enregistrés dans jarvis_config.json, ou None."""
    try:
        with open(os.path.join(shared.RACINE_PROJET, "jarvis_config.json"), "r", encoding="utf-8") as f:
            cfg = json.load(f)
        lat, lon = cfg.get("latitude"), cfg.get("longitude")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            return float(lat), float(lon), cfg.get("city") or ""
    except Exception:
        pass
    return None


# Position actuelle donnée par le service de localisation de Windows (Wi-Fi / réseau,
# précision de l'ordre de la ville). La fenêtre JARVIS n'a pas accès à la géolocalisation
# du navigateur, et la ville de la configuration est le domicile, pas la position du moment.
_PS_POSITION = r"""
Add-Type -AssemblyName System.Device
$w = New-Object System.Device.Location.GeoCoordinateWatcher([System.Device.Location.GeoPositionAccuracy]::High)
if ($w.Permission -eq 'Denied') { exit 4 }
if (-not $w.TryStart($false, [TimeSpan]::FromSeconds(10))) { exit 2 }
$fin = (Get-Date).AddSeconds(8)
while ($w.Position.Location.IsUnknown -and (Get-Date) -lt $fin) { Start-Sleep -Milliseconds 200 }
$c = $w.Position.Location
$w.Stop()
if ($c.IsUnknown) { exit 3 }
[string]::Format([Globalization.CultureInfo]::InvariantCulture, '{0};{1};{2}', $c.Latitude, $c.Longitude, $c.HorizontalAccuracy)
"""
_cache_position = {"t": 0.0, "pos": None}


def _position_windows_sync():
    """(lat, lon, précision en mètres) via la localisation de Windows, ou None."""
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_POSITION],
            capture_output=True, text=True, timeout=25,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if res.returncode != 0:
            print(f"[GLOBE] Localisation Windows indisponible (code {res.returncode} : "
                  f"{ {2: 'service non démarré', 3: 'position inconnue', 4: 'accès refusé'}.get(res.returncode, '?') })")
            return None
        lat, lon, precision = (float(x) for x in res.stdout.strip().split(";"))
        return lat, lon, precision
    except Exception as e:
        print(f"[GLOBE] Erreur localisation Windows : {e}")
        return None


async def _position_actuelle():
    """Position actuelle (mise en cache 5 minutes : la mesure prend quelques secondes)."""
    if _cache_position["pos"] and time.time() - _cache_position["t"] < 300:
        return _cache_position["pos"]
    pos = await asyncio.to_thread(_position_windows_sync)
    if pos:
        _cache_position.update(t=time.time(), pos=pos)
    return pos


async def _lieu_fiable(nom):
    """Résultat de géocodage si le lieu est assez important pour être un vrai lieu, sinon None."""
    lieu = await geocode_lieu_detaille(nom)
    if lieu and lieu["importance"] >= IMPORTANCE_MIN:
        return lieu
    if lieu:
        print(f"[GLOBE] « {nom} » écarté : {lieu['nom'][:60]} (importance {lieu['importance']:.2f})")
    return None


def _extraire_lieu(t, mot):
    """Texte qui suit le déclencheur, débarrassé des articles et de la ponctuation."""
    reste = t[t.find(mot) + len(mot):].strip()
    if reste.startswith("-"):
        reste = reste[1:].strip()
    if reste.startswith("moi "):
        reste = reste[4:].strip()
    for art in _ARTICLES:
        if reste.startswith(art):
            reste = reste[len(art):]
    for fin in [" sur la carte", " sur le globe"]:
        if reste.endswith(fin):
            reste = reste[: -len(fin)]
    return reste.rstrip(".,?!;").strip()


async def resoudre_globe_localement(texte: str):
    """Détecte les commandes du globe 3D et les envoie au frontend (globe.ts)."""
    t = texte.lower().strip()

    # 1. Fermer (priorité absolue). Les vues 3D (« ferme la carte 3D / domotique ») ont
    #    leur propre commande de fermeture.
    if any(m in t for m in _mots_fermer) and not any(k in t for k in ["3d", "domotique"]):
        await send_globe_command(globe_action="hide")
        return f"Navigation fermée. Je reviens à l'interface principale{nom_virgule()}."

    # Ne pas détourner une recherche de fichier, une demande d'image ou une info générale
    # (ni « une affiche » au sens d'un poster)
    if any(k in t for k in ["dossier", "fichier", "document", "archive", "programme", "histoire", "blague",
                            "raconte", "explique", "définition", "une affiche", "l'affiche",
                            "cette affiche", "image", "photo", "dessin"]):
        return None
    # « carte » (carte domotique, carte bancaire...) aussi, sauf « ... sur la carte »
    if "carte" in t and "sur la carte" not in t:
        return None

    # 2. Ma position : la position actuelle donnée par Windows ; à défaut le domicile
    #    réglé dans JARVIS (annoncé comme tel) ; à défaut la géolocalisation du navigateur.
    if any(m in t for m in _mots_position):
        pos = await _position_actuelle()
        if pos:
            lat, lon, precision = pos
            ville = await nom_lieu_inverse(lat, lon) or ""
            await send_globe_command(globe_action="my_location", lat=lat, lon=lon, target=ville)
            if not ville:
                return f"Voici votre position actuelle{nom_virgule()}."
            if precision <= 2000:
                return f"Vous êtes actuellement à {ville}{nom_virgule()}."
            # Localisation par Wi-Fi / réseau : souvent à quelques kilomètres près
            pres = "près d'" if ville[:1].lower() in "aeiouyàâéèêîôûh" else "près de "
            km = max(1, round(precision / 1000))
            return f"Vous êtes actuellement {pres}{ville}{nom_virgule()}, à environ {km} km près."
        domicile = _position_configuree()
        if domicile:
            lat, lon, ville = domicile
            await send_globe_command(globe_action="my_location", lat=lat, lon=lon, target=ville)
            return (f"Je n'ai pas accès à votre position actuelle{nom_virgule()} : la localisation de "
                    f"Windows ne répond pas. J'affiche votre domicile" + (f", {ville}." if ville else "."))
        await send_globe_command(globe_action="my_location")
        return f"Je tente de vous localiser{nom_virgule()}."

    # 3. Vue de la Terre entière
    if any(m in t for m in _mots_globe):
        await send_globe_command(globe_action="show_earth")
        return f"Vue depuis l'espace activée{nom_virgule()}."

    # 4. Itinéraire de X à Y (« à » accentué accepté : avant, seul « a » l'était)
    if any(m in t for m in _mots_route):
        match = re.search(r"\b(?:de|depuis)\s+(.+?)\s+(?:à|a|vers|jusqu['’ ]?à|jusqu['’ ]?a|et)\s+(.+?)\s*[?!.]*$", t)
        if match:
            from_name = match.group(1).strip().title()
            to_name = match.group(2).strip().title()
            depart = await _lieu_fiable(from_name)
            arrivee = await _lieu_fiable(to_name)
            if depart and arrivee:
                await send_globe_command(
                    globe_action="route",
                    from_lat=depart["lat"], from_lon=depart["lon"], from_name=from_name,
                    to_lat=arrivee["lat"], to_lon=arrivee["lon"], to_name=to_name,
                )
                return f"Itinéraire tracé de {from_name} à {to_name}{nom_virgule()}."
            return f"Je n'ai pas pu localiser les deux villes{nom_virgule()}. Vérifiez les noms et réessayez."
        return None

    # 5. Survol d'un lieu (avant le zoom : « zoome sur Paris » est un survol)
    for explicite, mots in [(True, _mots_lieu_explicites), (False, _mots_lieu_generiques)]:
        mot = next((m for m in mots if m in t), None)
        if not mot:
            continue
        reste = _extraire_lieu(t, mot)
        if reste in _LA_TERRE:
            await send_globe_command(globe_action="show_earth")
            return f"Vue depuis l'espace activée{nom_virgule()}."
        if len(reste) < 2:
            break
        nom_lieu = reste.title()
        lieu = await _lieu_fiable(nom_lieu)
        if lieu:
            await send_globe_command(globe_action="fly_to", lat=lieu["lat"], lon=lieu["lon"],
                                     target=nom_lieu, distance=_distance_vol(lieu["rang"]))
            return f"Survol de {nom_lieu} en cours{nom_virgule()}."
        if explicite:
            return f"Je n'ai pas réussi à localiser {nom_lieu}{nom_virgule()}. Essayez avec un nom plus précis."
        break

    # 6. Zoom avant / arrière, seulement quand le globe est affiché
    if shared.GLOBE_VISIBLE:
        if any(m in t for m in _mots_dezoom):
            await send_globe_command(globe_action="zoom_out")
            return f"Je prends de la hauteur{nom_virgule()}."
        if any(m in t for m in _mots_zoom):
            await send_globe_command(globe_action="zoom_in")
            return f"Je me rapproche{nom_virgule()}."

    return None


builtins.resoudre_globe_localement = resoudre_globe_localement
