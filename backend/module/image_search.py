import requests
import json
import os
import re as _re
from dotenv import load_dotenv
from google.genai import types

load_dotenv()
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
if SERPAPI_API_KEY == "VOTRE_CLE_ICI":
    SERPAPI_API_KEY = None

def cle_utilisable(key):
    return bool(key) and key != "VOTRE_CLE_ICI"

def images_par_gemini(query, nb_images=6):
    """Cherche des images en demandant à Gemini (recherche Google activée) de lister des URL."""
    import builtins
    if not hasattr(builtins, "client") or builtins.client is None:
        print("[IMAGE] Client Gemini introuvable dans builtins.")
        return []
    
    try:
        print(f"[IMAGE] Images via Gemini + Google pour : {query}")
        prompt = (
            f"Trouve sur internet des images de '{query}'. "
            f"Fournis {nb_images} adresses d'images valides (fichiers .jpg, .png ou .jpeg, ou images de banques d'images ou d'articles). "
            f"Réponds par un tableau JSON des adresses, rien d'autre (exemple : [\"https://site.com/image.jpg\", ...]). "
            f"Pas de phrase avant ou après, pas de balise ```json : le tableau brut seulement."
        )
        
        model_name = getattr(builtins, "CHOSEN_MODEL", "gemini-2.5-flash")
        
        response = builtins.client.models.generate_content(
            model=model_name,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                system_instruction="Tu trouves des images sur internet. Ta réponse est exclusivement un tableau JSON d'adresses."
            )
        )
        text = response.text.strip()
        
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
            
        urls = json.loads(text)
        if isinstance(urls, list):
            valid_urls = [u for u in urls if isinstance(u, str) and (u.startswith("http://") or u.startswith("https://"))]
            print(f"[IMAGE] {len(valid_urls)} image(s) trouvées via Gemini.")
            return valid_urls[:nb_images]
    except Exception as e:
        print(f"[IMAGE] Échec de la recherche Gemini : {e}")
    return []

def images_par_moteur(query, nb_images=6, engine="serpapi"):
    """Cherche des images sur internet avec le moteur choisi (serpapi, gemini ou duckduckgo)."""
    urls = []
    
    # ── Moteur SerpAPI ───────────────────────────────────────────────────────
    from core.ai_clients import api_activee
    if engine == "serpapi" and cle_utilisable(SERPAPI_API_KEY) and api_activee("serpapi"):
        try:
            print(f"[IMAGE] Images via SerpAPI pour : {query}")
            params = {
                "engine": "google_images",
                "q": query,
                "api_key": SERPAPI_API_KEY,
                "hl": "fr",
                "gl": "fr",
                "num": nb_images,
            }
            r = requests.get("https://serpapi.com/search.json", params=params, timeout=6)
            data = r.json()
            images_results = data.get("images_results", [])
            for img in images_results[:nb_images]:
                src = img.get("original") or img.get("thumbnail")
                if src:
                    urls.append(src)
            if urls:
                print(f"[IMAGE] {len(urls)} image(s) obtenue(s) par SerpAPI.")
                return urls
        except Exception as e:
            print(f"[IMAGE] Erreur/Timeout SerpAPI Images ({e}). Bascule sur Gemini/DDG...")

    # ── Moteur Gemini (En premier recours si SerpAPI désactivé/échoué) ────────
    import builtins
    if hasattr(builtins, "client") and builtins.client is not None:
        try:
            urls = images_par_gemini(query, nb_images)
            if urls:
                return urls
        except Exception as e:
            print(f"[IMAGE] Échec recherche Gemini : {e}")

    # ── Moteur DuckDuckGo (Dernier recours gratuit et robuste) ────────────────
    try:
        print(f"[IMAGE] Images via DuckDuckGo pour : {query}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "fr,fr-FR;q=0.9,en;q=0.8",
            "Referer": "https://duckduckgo.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "X-Requested-With": "XMLHttpRequest"
        }
        r = requests.get(
            "https://duckduckgo.com/",
            params={"q": query, "iax": "images", "ia": "images"},
            headers=headers, timeout=8
        )
        vqd_match = _re.search(r'vqd=([\d-]+)', r.text)
        if vqd_match:
            vqd = vqd_match.group(1)
            r2 = requests.get(
                "https://duckduckgo.com/i.js",
                params={"l": "fr-fr", "o": "json", "q": query, "vqd": vqd, "f": ",,,,,", "p": "1"},
                headers=headers, timeout=8
            )
            data2 = r2.json()
            for item in data2.get("results", [])[:nb_images]:
                img_url = item.get("image")
                if img_url:
                    urls.append(img_url)
            if urls:
                print(f"[IMAGE] {len(urls)} image(s) obtenue(s) par DuckDuckGo.")
                return urls
    except Exception as e:
        print(f"[IMAGE] Échec de DuckDuckGo : {e}")

    print(f"[IMAGE] Rien trouvé pour : {query}")
    return []
