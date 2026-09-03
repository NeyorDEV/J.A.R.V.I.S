"""
weather_music_service.py — Diffusion météo et infos musique vers le HUD.

Météo : Open-Meteo avec repli wttr.in, localisation client (reverse geocoding).
Musique : titre en cours Deezer (UIA local, repli API ARL, repli titre fenêtre).
CLIENT_LOCATION est un dict partagé, muté en place par main2.py (set_location).
Extrait de main2.py.
"""

import os
import time
import json
import asyncio
import builtins

import requests

from controller.deezer_controller import deezer_obtenir_titre_encours

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # racine projet


def _clients():
    """Clients websocket connectés (renseignés par main2 via builtins)."""
    return getattr(builtins, "CONNECTED_CLIENTS", set())


def _charger_config():
    try:
        p = os.path.join(_BASE_DIR, "jarvis_config.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

_location_cfg = _charger_config()
CLIENT_LOCATION = {
    "lat": _location_cfg.get("latitude", 45.2933),
    "lon": _location_cfg.get("longitude", 4.1720),
    "city": _location_cfg.get("city", "Monistrol-sur-Loire")
} 

async def update_client_city():
    global CLIENT_LOCATION
    if _location_cfg.get("city"):
        CLIENT_LOCATION["city"] = _location_cfg.get("city")
        print(f"[METEO] Localisation configurée : {CLIENT_LOCATION['city']}")
        return
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={CLIENT_LOCATION['lat']}&lon={CLIENT_LOCATION['lon']}&format=json"
        headers = {"User-Agent": "JARVIS-Assistant/1.0"}
        resp = await asyncio.to_thread(requests.get, url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            city = data.get("address", {}).get("city") or data.get("address", {}).get("town") or data.get("address", {}).get("village") or "Ma position"
            CLIENT_LOCATION["city"] = city
            print(f"[METEO] Localisation mise a jour : {city}")
    except Exception as e:
        print(f"[METEO] Erreur reverse geocoding : {e}")

async def get_weather_fallback_wttr(city_name):
    try:
        url = f"https://wttr.in/{requests.utils.quote(city_name)}?format=j1"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        resp = await asyncio.to_thread(requests.get, url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            curr = data.get("current_condition", [{}])[0]
            day = data.get("weather", [{}])[0]
            
            desc = curr.get("weatherDesc", [{}])[0].get("value", "Inconnu")
            translations = {
                "sunny": "Ensoleillé", "clear": "Clair", "partly cloudy": "Partiellement nuageux",
                "cloudy": "Nuageux", "overcast": "Couvert", "mist": "Brume", "fog": "Brouillard",
                "patchy rain possible": "Possibilité de pluie", "patchy snow possible": "Possibilité de neige",
                "heavy rain": "Forte pluie", "light rain": "Pluie faible", "thunderstorm": "Orage"
            }
            desc_fr = translations.get(desc.lower(), desc)
            
            return {
                "city": city_name,
                "temp": float(curr.get("temp_C", 0)),
                "apparent": float(curr.get("FeelsLikeC", 0)),
                "humidity": float(curr.get("humidity", 0)),
                "wind": float(curr.get("windspeedKmph", 0)),
                "desc": desc_fr,
                "max": float(day.get("maxtempC", 0)),
                "min": float(day.get("mintempC", 0))
            }
    except Exception as e:
        print(f"[METEO] Échec du repli wttr.in pour {city_name} : {e}")
    return None

async def get_raw_weather(lat, lon, city_name):
    try:
        # print(f"[METEO] Recuperation pour {city_name} ({lat}, {lon})...")
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weathercode",
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": "auto", "forecast_days": 1
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        resp = await asyncio.to_thread(requests.get, url, params=params, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            cur = data["current"]
            day = data["daily"]
            from module.meteo_domotique import CODES_METEO
            return {
                "city": city_name,
                "temp": cur["temperature_2m"],
                "apparent": cur["apparent_temperature"],
                "humidity": cur["relative_humidity_2m"],
                "wind": cur["wind_speed_10m"],
                "desc": CODES_METEO.get(cur["weathercode"], "Inconnu"),
                "max": day["temperature_2m_max"][0],
                "min": day["temperature_2m_min"][0]
            }
    except Exception:
        # Open-Meteo indisponible (SSL/timeout) → repli silencieux sur wttr.in
        wttr_weather = await get_weather_fallback_wttr(city_name)
        if wttr_weather:
            return wttr_weather
        # Les deux sources ont échoué — on loggue une seule fois
        print(f"[METEO] ⚠ Météo indisponible pour {city_name} (Open-Meteo + wttr.in KO).")
    return None

async def broadcast_weather_stats_once():
    """Diffuse la météo immédiatement sans attendre la boucle de 10 min."""
    if _clients():
        try:
            local_weather = await get_raw_weather(CLIENT_LOCATION["lat"], CLIENT_LOCATION["lon"], CLIENT_LOCATION["city"])
            if local_weather:
                msg = json.dumps({"action": "weather_update", "weather_type": "local", "weather": local_weather})
                await asyncio.gather(*[ws.send(msg) for ws in _clients()], return_exceptions=True)
            
            mon_weather = await get_raw_weather(45.2917, 4.1722, "Monistrol-sur-Loire")
            if mon_weather:
                msg = json.dumps({"action": "weather_update", "weather_type": "monistrol", "weather": mon_weather})
                await asyncio.gather(*[ws.send(msg) for ws in _clients()], return_exceptions=True)
        except Exception as e:
            print(f"[METEO] Erreur critique broadcast : {e}")

async def broadcast_weather_stats():
    """Diffuse la météo locale et celle de Monistrol périodiquement."""
    while True:
        try:
            if _clients():
                await broadcast_weather_stats_once()
        except Exception as e:
            print(f"[METEO] Erreur broadcast : {e}")
        await asyncio.sleep(600) # Toutes les 10 minutes

# Variables de suivi pour la progression
DEEZER_API_TOKEN = None
CURRENT_TRACK_ID = None
TRACK_START_TIME = None

async def get_deezer_api_token():
    """Récupère le jeton API nécessaire pour les requêtes Deezer via ARL."""
    global DEEZER_API_TOKEN
    arl = os.getenv("DEEZER_ARL")
    if not arl: return None
    try:
        url = "https://www.deezer.com/ajax/gw-light.php?method=deezer.getUserData&api_version=1.0&api_token="
        cookies = {"arl": arl}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = await asyncio.to_thread(requests.get, url, cookies=cookies, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            DEEZER_API_TOKEN = data.get("results", {}).get("checkForm")
            return DEEZER_API_TOKEN
    except: pass
    return None

async def get_media_info_deezer_api():
    """Récupère le morceau en cours et estime la progression temporelle."""
    global DEEZER_API_TOKEN, CURRENT_TRACK_ID, TRACK_START_TIME
    arl = os.getenv("DEEZER_ARL")
    if not arl: return None

    if not DEEZER_API_TOKEN:
        await get_deezer_api_token()
    
    try:
        url = f"https://www.deezer.com/ajax/gw-light.php?method=user.getHistory&api_version=1.0&api_token={DEEZER_API_TOKEN}"
        cookies = {"arl": arl}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = await asyncio.to_thread(requests.get, url, cookies=cookies, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            tracks = data.get("results", {}).get("data", [])
            if tracks:
                track = tracks[0]
                track_id = track.get("SNG_ID")
                title = track.get("SNG_TITLE", "INCONNU")
                artist = track.get("ART_NAME", "DEEZER")
                duration_sec = int(track.get("DURATION", 0))
                
                now = time.time()
                if track_id != CURRENT_TRACK_ID:
                    CURRENT_TRACK_ID = track_id
                    TRACK_START_TIME = now
                
                elapsed = int(now - TRACK_START_TIME)
                if elapsed > duration_sec: elapsed = duration_sec
                
                percent = (elapsed / duration_sec * 100) if duration_sec > 0 else 0
                
                def fmt_time(s):
                    m, s = divmod(int(s), 60)
                    return f"{m:02d}:{s:02d}"

                return {
                    "title": title.upper(),
                    "artist": artist.upper(),
                    "status": "Playing",
                    "position": fmt_time(elapsed),
                    "duration": fmt_time(duration_sec),
                    "percent": percent
                }
    except:
        DEEZER_API_TOKEN = None
    return None

async def get_media_info():
    """Récupère les infos média (Priorité UIA local, Fallback API Deezer, Fallback Windows)."""
    # 1. Tenter par UIA local (instantané et n'a pas besoin de réseau)
    try:
        info_local = await asyncio.to_thread(deezer_obtenir_titre_encours)
        if info_local:
            return {
                "title": info_local["title"].upper(),
                "artist": info_local["artist"].upper(),
                "status": "Playing",
                "position": "00:00",
                "duration": "00:00",
                "percent": 0
            }
    except Exception as uia_err:
        pass

    # 2. Fallback sur l'API Deezer en ligne
    info = await get_media_info_deezer_api()
    if info:
        return info


    import ctypes
    try:
        GetWindowText = ctypes.windll.user32.GetWindowTextW
        GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
        titles = []
        def foreach_window(hwnd, lParam):
            length = GetWindowTextLength(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                GetWindowText(hwnd, buff, length + 1)
                titles.append(buff.value)
            return True
        ctypes.windll.user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)(foreach_window), 0)
        
        for t in titles:
            if "Deezer" in t and " - " in t:
                parts = t.split(" - ")
                return {
                    "title": parts[0].strip().upper(), 
                    "artist": parts[1].replace("Deezer","").strip().upper(), 
                    "status": "Playing"
                }
    except: pass
    return None

async def broadcast_music_stats():
    """Diffuse les infos Deezer/Media toutes les 2 secondes."""
    while True:
        try:
            if _clients():
                info = await get_media_info()
                if info:
                    msg = json.dumps({"action": "music_update", "data": info})
                    await asyncio.gather(*[ws.send(msg) for ws in _clients()], return_exceptions=True)
                else:
                    msg = json.dumps({"action": "music_update", "data": {"status": "Stopped", "title": "DEEZER_OFFLINE", "artist": "APPLICATION_NON_DETECTEE"}})
                    await asyncio.gather(*[ws.send(msg) for ws in _clients()], return_exceptions=True)
        except Exception as e:
            pass
        await asyncio.sleep(2)

