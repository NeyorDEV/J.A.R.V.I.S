# ============================================================
#  meteo_domotique.py — Météo (Open-Meteo) & API REST Home Assistant
#  Le pilotage vocal de la domotique passe par le client MCP
#  (backend/core/ha_mcp_client.py) ; ce fichier ne sert plus que pour
#  la météo et le tableau de bord HUD (clic direct sur les entités).
# ============================================================

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

import json
import asyncio

def _charger_user_name():
    try:
        _dir = os.path.dirname(os.path.abspath(__file__))
        _root = os.path.dirname(os.path.dirname(_dir))  # backend/module/ -> racine projet
        _p = os.path.join(_root, "jarvis_config.json")
        with open(_p, "r", encoding="utf-8") as _f:
            return json.load(_f).get("user_name", "Mylane")
    except Exception:
        return "Mylane"

def _update_ha_env():
    global HA_URL, HA_TOKEN, HA_HEADERS
    _dir = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.dirname(os.path.dirname(_dir))  # backend/module/ -> racine projet
    load_dotenv(os.path.join(_root, ".env"), override=True)
    HA_URL    = os.getenv("HA_URL", "").rstrip("/")
    HA_TOKEN  = os.getenv("HA_TOKEN", "")
    HA_HEADERS = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type" : "application/json"
    }

HA_URL = ""
HA_TOKEN = ""
HA_HEADERS = {}
_update_ha_env()

def ha_active() -> bool:
    return bool(HA_URL) and "votre_ip_ha" not in HA_URL.lower()


# ═══════════════════════════════════════════════════════════════
#  SECTION 1 — MÉTÉO PAR DÉFAUT
#  Remplacez par votre ville et ses coordonnées GPS.
#  Coordonnées : https://www.latlong.net/
# ═══════════════════════════════════════════════════════════════
VILLE_PAR_DEFAUT = "Monistrol-sur-Loire"   # ← Votre ville
LAT_PAR_DEFAUT   = 45.2917                 # ← Latitude
LON_PAR_DEFAUT   = 4.1722                  # ← Longitude

# ── Codes météo Open-Meteo (ne pas modifier) ─────────────────
CODES_METEO = {
    0:  "ciel degage",
    1:  "principalement clair", 2: "partiellement nuageux", 3: "couvert",
    45: "brouillard", 48: "brouillard givrant",
    51: "bruine legere", 53: "bruine moderee", 55: "bruine dense",
    61: "pluie faible", 63: "pluie moderee", 65: "pluie forte",
    71: "neige faible", 73: "neige moderee", 75: "neige forte",
    80: "averses faibles", 81: "averses moderees", 82: "averses violentes",
    85: "averses de neige", 86: "averses de neige fortes",
    95: "orage", 96: "orage avec grele", 99: "orage violent avec grele",
}

# ════════════════════════════════════════════════════════════════
#  FONCTIONS API HOME ASSISTANT
#  Ne modifiez pas ces fonctions — elles appellent l'API HA.
# ════════════════════════════════════════════════════════════════

def ha_appeler_service(domaine, service, entity_id, donnees=None):
    if not ha_active():
        return False
    try:
        payload = {"entity_id": entity_id}
        if donnees:
            payload.update(donnees)
        print(f"[HA DEBUG] Calling {domaine}/{service} for {entity_id} with {donnees}")
        r = requests.post(
            f"{HA_URL}/api/services/{domaine}/{service}",
            headers=HA_HEADERS, json=payload, timeout=5
        )
        print(f"[HA DEBUG] Response {r.status_code}: {r.text}")
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"[HA] Erreur service : {e}")
        return False

# ════════════════════════════════════════════════════════════════
#  FONCTIONS MÉTÉO
#  Utilisent Open-Meteo (gratuit) + Home Assistant en fallback.
# ════════════════════════════════════════════════════════════════

OPEN_METEO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

def geocoder_ville(ville):
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": ville, "count": 1, "language": "fr", "format": "json"},
            headers=OPEN_METEO_HEADERS,
            timeout=5
        )
        data = r.json()
        if data.get("results"):
            res = data["results"][0]
            return res["latitude"], res["longitude"], res.get("name", ville), res.get("country", "")
    except Exception as e:
        print(f"[METEO] Erreur geocoding : {e}")
    return None, None, ville, ""

def get_meteo_fallback_wttr_sync(city_name):
    try:
        url = f"https://wttr.in/{requests.utils.quote(city_name)}?format=j1"
        resp = requests.get(url, headers=OPEN_METEO_HEADERS, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            curr = data.get("current_condition", [{}])[0]
            desc = curr.get("weatherDesc", [{}])[0].get("value", "Inconnu")
            translations = {
                "sunny": "ciel degage", "clear": "ciel degage", "partly cloudy": "partiellement nuageux",
                "cloudy": "nuageux", "overcast": "couvert", "mist": "brouillard", "fog": "brouillard",
                "patchy rain possible": "pluie faible", "patchy snow possible": "neige faible",
                "heavy rain": "pluie forte", "light rain": "pluie faible", "thunderstorm": "orage"
            }
            desc_fr = translations.get(desc.lower(), desc.lower())
            temp = round(float(curr.get("temp_C", 0)))
            return f"À {city_name}, il fait {temp} degrés et le ciel est {desc_fr}. C'est tout."
    except:
        pass
    return None

def get_meteo_actuelle(ville=None):
    try:
        nom_ville = ville or VILLE_PAR_DEFAUT
        lat, lon, nom_affiche, pays = geocoder_ville(nom_ville)
        if lat is None:
            lat, lon = LAT_PAR_DEFAUT, LON_PAR_DEFAUT
            nom_affiche = VILLE_PAR_DEFAUT
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude"       : lat, "longitude": lon,
                "current"        : "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,wind_direction_10m,weathercode,precipitation",
                "hourly"         : "temperature_2m,precipitation_probability",
                "daily"          : "temperature_2m_max,temperature_2m_min,weathercode,precipitation_sum,wind_speed_10m_max,sunrise,sunset",
                "timezone"       : "Europe/Paris",
                "forecast_days"  : 3,
                "wind_speed_unit": "kmh",
            },
            headers=OPEN_METEO_HEADERS,
            timeout=5
        )
        data = r.json()
        cur  = data["current"]
        code = cur.get("weathercode", 0)
        desc = CODES_METEO.get(code, "conditions inconnues")
        temp = round(float(cur.get("temperature_2m", 0)))
        return f"À {nom_affiche}, il fait {temp} degrés et le ciel est {desc}. C'est tout."
    except Exception:
        # Repli silencieux sur wttr.in si Open-Meteo est KO
        wttr_res = get_meteo_fallback_wttr_sync(nom_ville)
        if wttr_res:
            return wttr_res
        return "Je n'arrive pas à récupérer la météo pour le moment."

def get_meteo_ha():
    """Lit la météo depuis Home Assistant. Fallback quand Gemini est KO."""
    if not ha_active():
        return None
    try:
        r = requests.get(f"{HA_URL}/api/states/weather.forecast_amilly", headers=HA_HEADERS, timeout=5)
        data = r.json()
        etat  = data.get("state", "inconnu")
        attrs = data.get("attributes", {})
        temp     = attrs.get("temperature", "?")
        humidite = attrs.get("humidity", None)
        vent     = attrs.get("wind_speed", None)
        etats_fr = {
            "sunny"          : "ensoleillé",
            "clear-night"    : "clair",
            "partlycloudy"   : "partiellement nuageux",
            "cloudy"         : "nuageux",
            "rainy"          : "pluvieux",
            "pouring"        : "forte pluie",
            "snowy"          : "neigeux",
            "snowy-rainy"    : "pluie et neige mêlées",
            "windy"          : "venteux",
            "windy-variant"  : "très venteux",
            "fog"            : "brumeux",
            "hail"           : "grêle",
            "lightning"      : "orageux",
            "lightning-rainy": "orage et pluie",
            "exceptional"    : "conditions exceptionnelles",
        }
        desc    = etats_fr.get(etat, etat)
        reponse = f"À {VILLE_PAR_DEFAUT}, il fait {temp} degrés et le ciel est {desc}"
        if humidite:
            reponse += f", humidité à {humidite}%"
        if vent:
            reponse += f", vent à {vent} km/h"
        reponse += ", mylane."
        return reponse
    except Exception as e:
        print(f"[METEO HA] Erreur : {e}")
        return None

def get_alertes_meteo(ville=None):
    try:
        nom_ville = ville or VILLE_PAR_DEFAUT
        lat, lon, nom_affiche, _ = geocoder_ville(nom_ville)
        if lat is None:
            lat, lon, nom_affiche = LAT_PAR_DEFAUT, LON_PAR_DEFAUT, VILLE_PAR_DEFAUT
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "daily"   : "weathercode,precipitation_sum,wind_speed_10m_max",
                "timezone": "Europe/Paris", "forecast_days": 3,
            },
            headers=OPEN_METEO_HEADERS,
            timeout=8
        )
        data    = r.json()
        daily   = data["daily"]
        alertes = []
        for i in range(len(daily["weathercode"])):
            code  = daily["weathercode"][i]
            pluie = daily.get("precipitation_sum", [0]*3)[i] or 0
            vent  = daily.get("wind_speed_10m_max", [0]*3)[i] or 0
            jour  = ["aujourd hui", "demain", "apres-demain"][i]
            if code in [95, 96, 99]:
                alertes.append(f"Orage prevu {jour}")
            if code in [71, 73, 75, 85, 86]:
                alertes.append(f"Neige prevue {jour}")
            if pluie > 20:
                alertes.append(f"Fortes pluies {jour} ({pluie}mm)")
            if vent > 60:
                alertes.append(f"Vents forts {jour} ({vent} km/h)")
        if alertes:
            return f"Alertes meteo pour {nom_affiche} : " + ", ".join(alertes) + "."
        return f"Aucune alerte meteo pour {nom_affiche} dans les 3 prochains jours."
    except Exception as e:
        return f"Impossible de verifier les alertes meteo : {e}"


# ════════════════════════════════════════════════════════════════
# NOUVEAUX SERVICES - DASHBOARD CENTRAL DE DOMOTIQUE
# ════════════════════════════════════════════════════════════════

def ha_get_all_states() -> list:
    """Récupère tous les états des entités de Home Assistant."""
    _update_ha_env()
    if not ha_active():
        return []
    try:
        url = f"{HA_URL}/api/states"
        print(f"[HA] Récupération de tous les états depuis {url}")
        r = requests.get(url, headers=HA_HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"[HA] Échec récupération états. Code : {r.status_code}")
            return []
    except Exception as e:
        print(f"[HA] Erreur lors de la récupération de tous les états : {e}")
        return []

def ha_get_etat_complet(entity_id: str) -> dict | None:
    """Récupère l'état complet d'une entité spécifique."""
    _update_ha_env()
    if not ha_active():
        return None
    try:
        url = f"{HA_URL}/api/states/{entity_id}"
        r = requests.get(url, headers=HA_HEADERS, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[HA] Erreur ha_get_etat_complet pour {entity_id} : {e}")
    return None

async def handle_ha_ws_message(data: dict, websocket, connected_clients: set) -> bool:
    """Gère les messages WebSocket liés à Home Assistant."""
    msg_type = data.get("type", "")

    if msg_type == "ha_get_states":
        states = await asyncio.to_thread(ha_get_all_states)
        await websocket.send(json.dumps({
            "type": "ha_states",
            "success": len(states) > 0 or HA_URL != "",
            "states": states
        }))
        return True

    elif msg_type == "ha_call_service":
        domain = data.get("domain", "")
        service = data.get("service", "")
        entity_id = data.get("entity_id", "")
        service_data = data.get("service_data", None)

        success = await asyncio.to_thread(ha_appeler_service, domain, service, entity_id, service_data)

        updated_state = None
        if success:
            updated_state = await asyncio.to_thread(ha_get_etat_complet, entity_id)

        await websocket.send(json.dumps({
            "type": "ha_service_result",
            "success": success,
            "entity_id": entity_id,
            "state": updated_state
        }))

        # Diffuser le changement d'état à tous les clients connectés pour synchroniser l'UI
        if success and updated_state:
            await _broadcast_ha(connected_clients, {
                "type": "ha_state_changed",
                "entity_id": entity_id,
                "state": updated_state
            })
        return True

    return False

async def _broadcast_ha(clients: set, message: dict):
    if not clients:
        return
    msg = json.dumps(message)
    try:
        await asyncio.gather(*[c.send(msg) for c in clients], return_exceptions=True)
    except Exception as e:
        print(f"[HA-WS] Erreur broadcast : {e}")

