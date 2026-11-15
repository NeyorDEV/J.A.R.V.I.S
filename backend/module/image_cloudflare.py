"""Génération d'images gratuite : Cloudflare Workers AI (FLUX.1 schnell).

Palier gratuit de Cloudflare : ~10 000 « neurones » par jour (remis à zéro à 00h00 UTC), sans carte bancaire. Deux variables dans le .env :
  CLOUDFLARE_ACCOUNT_ID   identifiant du compte (tableau de bord Cloudflare, colonne de droite)
  CLOUDFLARE_API_TOKEN    jeton d'API avec la permission « Workers AI » (modèle « Workers AI » des jetons d'API)
Sans elles, `disponible()` renvoie False et l'appelant passe à son repli (Pollinations). Jamais de clé dans les journaux.
"""

import base64
import os
import threading
import time

import requests

MODELE = "@cf/black-forest-labs/flux-1-schnell"
DELAI_S = 60
PAUSE_QUOTA_S = 3600        # quota du jour épuisé ou limite atteinte : on n'insiste pas avant une heure

_verrou = threading.Lock()
_pause_jusqu = 0.0


def _identifiants():
    compte = (os.environ.get("CLOUDFLARE_ACCOUNT_ID") or "").strip()
    jeton = (os.environ.get("CLOUDFLARE_API_TOKEN") or "").strip()
    return compte, jeton


def disponible() -> bool:
    """Les deux identifiants sont renseignés (et ne sont pas le texte d'exemple de l'installateur) et le service n'est pas en pause."""
    compte, jeton = _identifiants()
    if not compte or not jeton or "VOTRE" in compte.upper() or "VOTRE" in jeton.upper():
        return False
    return time.monotonic() >= _pause_jusqu


def _image_valide(octets: bytes) -> bool:
    return octets[:3] == b"\xff\xd8\xff" or octets[:8] == b"\x89PNG\r\n\x1a\n" or (octets[:4] == b"RIFF" and octets[8:12] == b"WEBP")


def generer_image_flux(prompt: str, etapes: int = 4):
    """Renvoie les octets de l'image (JPEG ou PNG) ou None (non configuré, quota atteint, erreur réseau, réponse inattendue)."""
    global _pause_jusqu
    if not disponible():
        return None
    compte, jeton = _identifiants()
    url = f"https://api.cloudflare.com/client/v4/accounts/{compte}/ai/run/{MODELE}"
    try:
        r = requests.post(url, json={"prompt": prompt[:2000], "steps": max(1, min(8, int(etapes)))},
                          headers={"Authorization": f"Bearer {jeton}"}, timeout=DELAI_S)
    except requests.RequestException as e:
        print(f"[IMAGE CLOUDFLARE] Réseau : {type(e).__name__}")
        return None
    if r.status_code in (401, 403):
        print("[IMAGE CLOUDFLARE] Jeton refusé : vérifiez CLOUDFLARE_API_TOKEN (permission « Workers AI ») et CLOUDFLARE_ACCOUNT_ID.")
        with _verrou:
            _pause_jusqu = time.monotonic() + PAUSE_QUOTA_S
        return None
    if r.status_code == 429 or (r.status_code >= 400 and "neurons" in r.text.lower()):
        print("[IMAGE CLOUDFLARE] Limite du palier gratuit atteinte : repli pendant une heure.")
        with _verrou:
            _pause_jusqu = time.monotonic() + PAUSE_QUOTA_S
        return None
    if not r.ok:
        print(f"[IMAGE CLOUDFLARE] Erreur HTTP {r.status_code}")
        return None
    if _image_valide(r.content):          # certains modèles répondent l'image brute
        return r.content
    try:
        b64 = (r.json().get("result") or {}).get("image")
        octets = base64.b64decode(b64) if b64 else b""
    except (ValueError, AttributeError):
        octets = b""
    if not _image_valide(octets):
        print("[IMAGE CLOUDFLARE] Réponse inattendue (pas d'image).")
        return None
    return octets
