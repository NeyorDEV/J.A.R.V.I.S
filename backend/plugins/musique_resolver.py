"""musique_resolver.py — « c'est quoi cette musique ? », « qui chante ça ? », « reconnais cette chanson » : identifie le morceau (core/musique_id.py).

Si Deezer joue sur ce PC, son titre est donné directement (aucun envoi) ; sinon, ou si on précise « avec le micro », « dans la pièce », JARVIS écoute 10 secondes et interroge AudD.
"""
import asyncio
import builtins
import re
import unicodedata

from core.interlocuteur import nom_virgule

_DEMANDE = re.compile(
    r"^(?:jarvis )?(?:"
    r"(?:c est quoi|quelle est|quel est|c est quelle|c est quel|dis moi quelle est|dis moi quel est) (?:cette|ce|la|le) (?:musique|chanson|morceau|titre)(?: la| qui passe| qui joue| en ce moment)?|"
    r"(?:qui chante|qui joue|qui est l artiste de) (?:ca|cette chanson|cette musique|ce morceau)|"
    r"(?:shazam|shazame)(?: moi)?(?: (?:ca|cette musique|cette chanson|ce morceau))?|"
    r"(?:reconnais|identifie)(?: moi)? (?:(?:cette|ce|la|le) (?:musique|chanson|morceau|titre)|ca|(?:musique|chanson|morceau))|"
    r"quelle musique (?:est ce|passe|joue)|"
    r"qu est ce que (?:c est|ca) comme (?:musique|chanson)"
    r")(?: dans la piece| autour de moi| avec le micro| ambiante| au micro)?(?: s il te plait)?$")
_FORCER_MICRO = re.compile(r"\b(piece|micro|autour|ambiante|ecoute)\b")
SECONDES = 10


def _clean(t: str) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", t)).strip()


def est_demande(texte: str) -> bool:
    return bool(_DEMANDE.match(_clean(texte)))


async def _carte(titre: str, texte: str):
    try:
        await builtins.envoyer_carte_contextuelle(titre, texte, type_carte="info", icon="♪")
    except Exception:
        pass


async def _titre_deezer():
    """Le morceau que Deezer est en train de jouer sur ce PC, ou None."""
    try:
        from module.weather_music_service import get_media_info
        info = await asyncio.wait_for(get_media_info(), timeout=4)
        if info and info.get("status") == "Playing" and info.get("title") and "DEEZER_OFF" not in str(info.get("title")):
            return info["title"].title(), str(info.get("artist") or "").title()
    except Exception:
        pass
    return None


def _ecouter_et_reconnaitre():
    """Capte l'extrait puis le fait reconnaître (bloquant : lancé dans un fil)."""
    from core import musique_id as mid
    import core.shared as shared
    from core.audio_stream import AudioStreamManager
    gestionnaire = AudioStreamManager()
    file = gestionnaire.subscribe()
    etait_coupe = shared.MIC_MUTED
    shared.MIC_MUTED = True   # la boucle d'écoute ignore le micro : la musique ne sera pas transcrite comme de la parole
    try:
        pcm = mid.collecter(file, SECONDES)
    finally:
        gestionnaire.unsubscribe(file)
        shared.MIC_MUTED = etait_coupe
    if len(pcm) < SECONDES * mid.OCTETS_PAR_SECONDE * 0.6:
        raise mid.MusiqueErreur("Je n'ai pas pu écouter : le micro ne répond pas.")
    if mid.niveau_sonore(pcm) < 0.02:
        raise mid.MusiqueErreur("Je n'entends presque rien. Rapprochez la source ou augmentez le volume.")
    return mid.identifier(mid.en_wav(pcm))   # (morceau ou None, fournisseur)


async def resoudre_musique(cmd: str):
    if not est_demande(cmd):
        return None
    t = _clean(cmd)
    if not _FORCER_MICRO.search(t):
        deezer = await _titre_deezer()
        if deezer:
            titre, artiste = deezer
            await _carte("Musique", f"{titre} · {artiste}" if artiste else titre)
            return f"Sur Deezer, c'est « {titre} »" + (f" de {artiste}" if artiste else "") + f"{nom_virgule()}."
    from core import musique_id as mid
    if not mid.fournisseurs_disponibles():
        return (f"Je ne peux pas reconnaître de musique pour l'instant{nom_virgule()} : ni la bibliothèque Shazam, ni une clé AudD ne sont disponibles. "
                "Installez shazamio, ou ajoutez la ligne AUDD_API_TOKEN dans le fichier .env.")
    try:
        builtins.parler(f"J'écoute pendant {SECONDES} secondes.")
    except Exception:
        pass
    try:
        trouve, _fournisseur = await asyncio.get_running_loop().run_in_executor(None, _ecouter_et_reconnaitre)
    except mid.MusiqueErreur as e:
        return str(e)
    if not trouve:
        return f"Je n'ai pas reconnu ce morceau{nom_virgule()}. Essayez plus près de la source, ou avec une partie plus claire."
    await _carte("Musique reconnue", f"{trouve['titre']} · {trouve['artiste']}" if trouve["artiste"] else trouve["titre"])
    return mid.phrase_resultat(trouve)


builtins.resoudre_musique = resoudre_musique
