"""Reconnaissance de musique (« c'est quoi cette musique ? ») : capture quelques secondes du micro, puis demande à AudD de reconnaître l'extrait.

  - Rien n'est envoyé sauf sur demande vocale, et seulement l'extrait (10 s par défaut) ; la clé est lue dans l'environnement (`AUDD_API_TOKEN`, fichier .env).
  - L'extrait vient du flux du micro de JARVIS (AudioStreamManager : 16 kHz, mono) : pas de second accès au micro. L'écoute vocale est coupée pendant la capture, sinon la musique serait transcrite comme de la parole.
  - Deux fournisseurs : Shazam (bibliothèque shazamio, gratuite, sans clé, mais NON officielle) puis AudD (officiel, clé `AUDD_API_TOKEN`, 300 requêtes d'essai puis payant), dans l'ordre de
    `musique_fournisseurs` (jarvis_config.json, défaut ["shazamio", "audd"]) ; on passe au suivant seulement en cas de PANNE, pas quand un fournisseur répond « inconnu ».
Pur et testé là où c'est possible (collecte, WAV, lecture de la réponse) : tests/test_musique_id.py.
"""
import io
import os
import queue
import time
import wave

URL_AUDD = "https://api.audd.io/"
RATE = 16000
OCTETS_PAR_SECONDE = RATE * 2   # 16 bits, mono


class MusiqueErreur(Exception):
    """Erreur lisible à dire à voix haute (clé absente ou refusée, réseau…)."""


def cle() -> str:
    return (os.environ.get("AUDD_API_TOKEN") or "").strip()


def collecter(file_attente, secondes: float = 10.0, delai_max: float = None) -> bytes:
    """Lit la file de morceaux audio (octets 16 bits) jusqu'à avoir `secondes` d'audio, ou jusqu'au délai ; renvoie les octets reçus."""
    voulu = int(secondes * OCTETS_PAR_SECONDE)
    limite = time.time() + (delai_max if delai_max is not None else secondes + 5)
    recu = bytearray()
    while len(recu) < voulu and time.time() < limite:
        try:
            recu += file_attente.get(timeout=0.5)
        except queue.Empty:
            continue
    return bytes(recu[:voulu])


def en_wav(pcm: bytes) -> bytes:
    sortie = io.BytesIO()
    with wave.open(sortie, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)
    return sortie.getvalue()


def niveau_sonore(pcm: bytes) -> float:
    """Niveau moyen 0..1 de l'extrait : pour dire « je n'entends presque rien » plutôt que d'envoyer du silence."""
    if len(pcm) < 2:
        return 0.0
    import array
    a = array.array("h")
    a.frombytes(pcm[: len(pcm) // 2 * 2])
    return min(1.0, (sum(abs(x) for x in a) / len(a)) / 6000.0)


def lire_reponse(donnees) -> "dict | None":
    """Réponse JSON d'AudD -> {"titre", "artiste", "album", "annee", "lien"} ; None si rien n'est reconnu ; MusiqueErreur si le service refuse."""
    if not isinstance(donnees, dict):
        raise MusiqueErreur("Réponse inattendue du service de reconnaissance.")
    if donnees.get("status") == "error":
        err = donnees.get("error") or {}
        code, message = err.get("error_code"), str(err.get("error_message") or "")
        if code in (900, 901):
            raise MusiqueErreur("Le service de reconnaissance refuse la clé AudD (invalide, ou quota gratuit épuisé).")
        raise MusiqueErreur(f"Le service de reconnaissance a répondu une erreur ({code}) : {message[:80]}")
    r = donnees.get("result")
    if not r or not r.get("title"):
        return None
    return {"titre": str(r.get("title") or "").strip(), "artiste": str(r.get("artist") or "").strip(), "album": str(r.get("album") or "").strip(),
            "annee": str(r.get("release_date") or "")[:4], "lien": str(r.get("song_link") or "")}


def reconnaitre(wav: bytes, jeton: str = None, timeout: float = 30.0) -> "dict | None":
    """Envoie l'extrait à AudD."""
    import requests
    jeton = jeton or cle()
    if not jeton:
        raise MusiqueErreur("Il manque la clé AudD.")
    try:
        r = requests.post(URL_AUDD, data={"api_token": jeton}, files={"file": ("extrait.wav", wav, "audio/wav")}, timeout=timeout)
        r.raise_for_status()
        return lire_reponse(r.json())
    except MusiqueErreur:
        raise
    except Exception as e:
        raise MusiqueErreur("Je n'arrive pas à joindre le service de reconnaissance de musique.") from e


def phrase_resultat(m: dict) -> str:
    texte = f"C'est « {m['titre']} »"
    if m["artiste"]:
        texte += f" de {m['artiste']}"
    if m["album"] and m["album"].lower() != m["titre"].lower():
        texte += f", sur l'album {m['album']}"
    if m["annee"].isdigit():
        texte += f" ({m['annee']})"
    return texte + "."


# --- Shazam (bibliothèque shazamio, NON officielle : elle copie l'API de Shazam, peut cesser de fonctionner sans préavis) ----------------------------------------------------------------
_CHAMPS_ANNEE = ("released", "sortie", "date de sortie", "annee", "année", "year")


def lire_reponse_shazam(donnees) -> "dict | None":
    """Réponse de shazamio -> même forme que lire_reponse ; None si rien n'est reconnu."""
    if not isinstance(donnees, dict):
        raise MusiqueErreur("Réponse inattendue du service Shazam.")
    t = donnees.get("track")
    if not t or not t.get("title"):
        return None
    album, annee = "", ""
    for section in t.get("sections") or []:
        for m in section.get("metadata") or []:
            nom = str(m.get("title") or "").strip().lower()
            if nom == "album" and not album:
                album = str(m.get("text") or "").strip()
            elif nom in _CHAMPS_ANNEE and not annee:
                chiffres = "".join(c for c in str(m.get("text") or "") if c.isdigit())
                annee = chiffres[:4] if len(chiffres) >= 4 else ""
    return {"titre": str(t.get("title") or "").strip(), "artiste": str(t.get("subtitle") or "").strip(), "album": album, "annee": annee, "lien": str(t.get("url") or "")}


def shazam_disponible() -> bool:
    try:
        import shazamio  # noqa: F401
        return True
    except ImportError:
        return False


def reconnaitre_shazam(wav: bytes, timeout: float = 30.0) -> "dict | None":
    import asyncio

    async def _appel():
        from shazamio import Shazam
        s = Shazam(language="fr-FR", endpoint_country="FR")
        try:
            return await asyncio.wait_for(s.recognize(wav), timeout)
        finally:
            try:
                await s.close()
            except Exception:
                pass
    if not shazam_disponible():
        raise MusiqueErreur("La bibliothèque Shazam n'est pas installée.")
    try:
        donnees = asyncio.run(_appel())
    except Exception as e:
        raise MusiqueErreur("Je n'arrive pas à joindre le service Shazam.") from e
    return lire_reponse_shazam(donnees)


# --- choix du fournisseur ---------------------------------------------------------------------------------------------------------------------------------------------------------------------
FOURNISSEURS_DEFAUT = ["shazamio", "audd"]


def _fournisseurs_configures() -> list:
    """Ordre d'essai : jarvis_config.json, clé `musique_fournisseurs` (liste parmi « shazamio » et « audd »)."""
    try:
        import json
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "jarvis_config.json"), encoding="utf-8") as f:
            liste = json.load(f).get("musique_fournisseurs")
        if isinstance(liste, list) and liste:
            return [str(x).lower() for x in liste if str(x).lower() in ("shazamio", "audd")] or FOURNISSEURS_DEFAUT
    except (OSError, ValueError, AttributeError):
        pass
    return list(FOURNISSEURS_DEFAUT)


def fournisseurs_disponibles(ordre=None) -> list:
    """Fournisseurs utilisables maintenant (Shazam si la bibliothèque est installée, AudD s'il y a une clé), dans l'ordre voulu."""
    return [f for f in (ordre or _fournisseurs_configures()) if (f == "shazamio" and shazam_disponible()) or (f == "audd" and cle())]


def identifier(wav: bytes, ordre=None):
    """Essaie les fournisseurs dans l'ordre. Renvoie (morceau ou None, fournisseur). Un fournisseur qui répond « inconnu » est définitif (l'autre n'est pas interrogé : même résultat probable, et il consomme un quota) ;
    seule une PANNE (réseau, clé refusée, bibliothèque cassée) passe au suivant. Lève MusiqueErreur si aucun n'a pu répondre."""
    dispo = fournisseurs_disponibles(ordre)
    if not dispo:
        raise MusiqueErreur("Aucun service de reconnaissance n'est disponible.")
    derniere = None
    for nom in dispo:
        try:
            return (reconnaitre_shazam(wav) if nom == "shazamio" else reconnaitre(wav)), nom
        except MusiqueErreur as e:
            derniere = e
    raise derniere
