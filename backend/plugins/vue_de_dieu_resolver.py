"""
vue_de_dieu_resolver.py — « active la vue de Dieu » : God's Eye View (globe 3D en direct) dans le HUD, installé à la demande.

Commandes : ouvrir (« active / lance / ouvre la vue de Dieu »), fermer (« ferme la vue de Dieu »), mettre à jour (« mets à jour la vue de Dieu »)
et, vue ouverte, aller quelque part (« va à Tokyo », « montre-moi Paris », « survole le Mont Blanc »).

L'appli n'est pas dans le dépôt de JARVIS : si elle n'est pas installée, JARVIS pose la question (voix et HUD) puis l'installe depuis la dernière
release GitHub ; si une release plus récente existe, il propose la mise à jour (une fois par version). Voir module/vue_de_dieu.py.
"""
import asyncio
import builtins
import json
import re
import unicodedata
import uuid

from core.interlocuteur import nom_virgule
from module import vue_de_dieu as vdd


def _clean(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn").lower().strip()


# « vue de Dieu » tel que la transcription l'écrit : accents et casse ignorés, quelques variantes courantes
_NOM = re.compile(r"\b(vue de dieu|vue de dieux|oeil de dieu|god'?s? ?eye( view)?|vue divine)\b")
_FERMER = re.compile(r"\b(ferme|fermer|quitte|quitter|arrete|arreter|desactive|desactiver|coupe|couper|stop|stoppe|sors|sortir|masque|cache|eteins|annule)\b")
_METTRE_A_JOUR = re.compile(r"\b(mets? a jour|met a jour|mettre a jour|mise a jour|actualise|actualiser|update)\b")
_INSTALLER = re.compile(r"\b(installe|installer|telecharge|telecharger)\b")
_ALLER = re.compile(r"^(?:jarvis[ ,]+)?(?P<verbe>va|aller|vas|emmene[- ]moi|montre[- ]moi|affiche[- ]moi|survole|zoom sur|direction|envole[- ]toi)\s+"
                    r"(?:(?:a|au|aux|en|sur|vers|dans|chez)\s+|au[- ]dessus d[eu']\s*)?(?P<lieu>.+)$")
# « montre-moi la météo » n'est pas un lieu : ces commandes restent à leurs resolvers, vue ouverte ou non
_PAS_UN_LIEU = re.compile(r"\b(meteo|calendrier|agenda|musique|heure|date|temps|systeme|ordinateur|cpu|ram|programmes?|applications?|mails?|emails?|"
                          r"liste|courses|alarmes?|minuteurs?|aide|commandes?|parametres?|reglages?|recettes?|image|photo|video|etat|resultats?)\b")

_taches = set()   # références gardées sur les installations en cours (sinon le ramasse-miettes peut les interrompre)


async def _diffuser(data: dict) -> None:
    if builtins.CONNECTED_CLIENTS:
        msg = json.dumps(data, ensure_ascii=False)
        await asyncio.gather(*[ws.send(msg) for ws in builtins.CONNECTED_CLIENTS], return_exceptions=True)


async def _parler(texte: str) -> None:
    try:
        if hasattr(builtins, "parler"):
            r = builtins.parler(texte)
            if asyncio.iscoroutine(r):
                await r
    except Exception as e:
        print(f"[VUE DE DIEU] parole impossible : {e}")


def _altitude_et_inclinaison(rang) -> tuple:
    """Hauteur de caméra (m) et inclinaison selon l'importance du lieu : un pays se voit de l'espace, une rue de près."""
    r = rang if isinstance(rang, int) else 16
    if r <= 4:
        return 4_500_000, -90
    if r <= 8:
        return 1_200_000, -90
    if r <= 12:
        return 250_000, -75
    if r <= 16:
        return 25_000, -55
    return 5_000, -45


async def _question(message: str, details: list, timeout: float = 60.0) -> bool:
    from core.confirmation import demander_confirmation
    return await demander_confirmation(None, message, timeout=timeout, details=details, question=True)


async def _ouvrir_vue():
    ok, erreur = await asyncio.to_thread(vdd.demarrer)
    if not ok:
        return erreur
    await _diffuser({"action": "vue_de_dieu_show", "url": vdd.URL})
    return f"J'active la vue de Dieu{nom_virgule()}. Le chargement prend quelques secondes."


async def _installer_en_fond(release: dict, mise_a_jour: bool) -> None:
    loop = asyncio.get_running_loop()

    def progres(texte, fraction=None):
        asyncio.run_coroutine_threadsafe(_diffuser({"action": "vue_de_dieu_progres", "texte": texte, "pct": fraction}), loop)

    ok, message = await asyncio.to_thread(vdd.installer, release, progres)
    if ok:
        demarre, erreur = await asyncio.to_thread(vdd.demarrer)
        if not demarre:
            await _diffuser({"action": "vue_de_dieu_erreur", "texte": (erreur or "").upper()})
            await _parler(erreur or "God's Eye View est installé mais ne démarre pas.")
            return
        await _diffuser({"action": "vue_de_dieu_pret", "url": vdd.URL})
        await _parler(f"God's Eye View est {'à jour' if mise_a_jour else 'installé'}{nom_virgule()}. Je l'ouvre.")
    elif message != "Installation annulée.":
        await _diffuser({"action": "vue_de_dieu_erreur", "texte": (message or "").upper()})
        await _parler(message or "L'installation de God's Eye View a échoué.")


async def _lancer_installation(release: dict, mise_a_jour: bool) -> str:
    await _diffuser({"action": "vue_de_dieu_show", "url": vdd.URL, "installation": True})
    if release.get("notes"):   # notes de version affichées sur l'écran d'attente pendant toute la mise à jour
        await _diffuser({"action": "vue_de_dieu_notes", "tag": release["tag"], "lignes": release["notes"]})
    tache = asyncio.create_task(_installer_en_fond(release, mise_a_jour))
    _taches.add(tache)
    tache.add_done_callback(_taches.discard)
    quoi = "Je mets à jour" if mise_a_jour else "J'installe"
    return f"{quoi} God's Eye View, version {release['tag']}{nom_virgule()}. Je vous préviens dès que c'est prêt."


async def _proposer_installation() -> str:
    release = await asyncio.to_thread(vdd.derniere_release)
    if not release:
        return "God's Eye View n'est pas installé, et je ne peux pas joindre GitHub pour le télécharger. Vérifiez la connexion internet."
    details = [{"t": "Source", "d": f"Dernière version publiée sur GitHub : {release['tag']} du {release['publiee']}"},
               {"t": "Durée", "d": "Environ 100 Mo à télécharger, puis 2 à 5 minutes d'installation"},
               {"t": "Emplacement", "d": "Dans le dossier de JARVIS : rien n'est installé dans Windows"}]
    if await asyncio.to_thread(vdd._node) is None:
        details.append({"t": "Node.js 24", "d": "Téléchargé aussi (environ 30 Mo), dans le même dossier"})
    if not await _question("God's Eye View n'est pas installé sur cet ordinateur. Voulez-vous l'installer ?", details):
        return f"D'accord{nom_virgule()}, je n'installe pas God's Eye View."
    return await _lancer_installation(release, False)


async def _proposer_mise_a_jour(release: dict) -> bool:
    """Pose la question ; True si l'utilisateur veut mettre à jour (sinon la version refusée n'est plus proposée)."""
    details = [{"t": "Version installée", "d": str(vdd.version_installee())},
               {"t": "Nouvelle version", "d": f"{release['tag']} du {release['publiee']}"},
               {"t": "Durée", "d": "Quelques minutes ; l'ancienne version reste en place si quelque chose échoue"}]
    oui = await _question(f"Une nouvelle version de God's Eye View est disponible : {release['tag']}. Voulez-vous la mettre à jour ?", details, 45.0)
    if not oui:
        vdd.refuser_version(release["tag"])
    return oui


# ── Pilotage : couches, options, boutons de l'appli (l'ordre part au HUD, qui le relaie à gev_couches.js dans l'iframe) ──
_ON = r"(?:active|activer|allume|allumer|affiche|afficher|montre|montrer|mets|mettre|ajoute|ajouter)"
_OFF = r"(?:desactive|desactiver|eteins|eteindre|cache|cacher|masque|masquer|enleve|enlever|retire|retirer|supprime|supprimer|coupe|couper)"
_COUCHE_ON = re.compile(rf"^(?:jarvis[ ,]+)?{_ON}(?:[- ]moi)?\s+(?:(?:les|la|le|une?|des)\s+|l')?(?P<c>couches?\s+)?(?P<nom>.+)$")
_COUCHE_OFF = re.compile(rf"^(?:jarvis[ ,]+)?{_OFF}(?:[- ]moi)?\s+(?:(?:les|la|le|une?|des)\s+|l')?(?P<c>couches?\s+)?(?P<nom>.+)$")
_TOUTES_OFF = re.compile(rf"^(?:jarvis[ ,]+)?{_OFF}\s+(?:toutes?\s+les\s+couches|tout)\b")
_LISTE = re.compile(r"\b(quelles?|liste)\b.*\bcouches?\b.*\b(actives?|affichees?|allumees?)\b|\bcouches?\s+actives?\b")
_CHOIX = re.compile(r"^(?:jarvis[ ,]+)?(?:clique(?:r)? sur|appuie sur|appuyer sur|selectionne|selectionner|choisis|choisir|passe (?:en|au|a)(?: mode| style)?|bascule (?:en|sur)|utilise)\s+(?:(?:les|la|le|une?)\s+|l')?(?P<nom>.+)$")
_SYNONYMES = {"vision nocturne": "nvg", "thermique": "flir", "infrarouge": "flir", "ecran cathodique": "crt", "film noir": "noir", "noir et blanc": "noir", "dessin anime": "anime", "mode normal": "normal"}


async def _ordre(cmd: dict, delai: float = 6.0):
    """Envoie un ordre à la vue ouverte et attend sa réponse (ok, texte) ; None si la vue ne répond pas."""
    ident = uuid.uuid4().hex[:8]
    f = asyncio.get_running_loop().create_future()
    vdd.retours[ident] = f
    await _diffuser({"action": "vue_de_dieu_cmd", "id": ident, "cmd": cmd})
    try:
        return await asyncio.wait_for(f, delai)
    except asyncio.TimeoutError:
        vdd.retours.pop(ident, None)
        return None


_AVEC = re.compile(r"\bavec\s+(?P<c>.+)$")


def _couches_demandees(t: str) -> list:
    """« … la vue de Dieu avec les bouchons et le trafic activés » -> ["bouchons", "trafic"]."""
    m = _AVEC.search(t.strip(" .!?"))
    if not m:
        return []
    noms = []
    for morceau in re.split(r"\s+et\s+|\s*,\s*", m.group("c")):
        morceau = re.sub(r"\s+(?:activee?s?|allumee?s?|affichee?s?|ouverte?s?|d'ouverte?s?|en direct|visibles?)$", "", morceau.strip())
        morceau = re.sub(r"^(?:les|la|le|l'|une?|des|couches?)\s+", "", morceau).strip()
        morceau = re.sub(r"^(?:couches?)\s+", "", morceau).strip()
        if morceau:
            noms.append(morceau)
    return noms[:4]


async def _activer_apres_ouverture(noms: list) -> None:
    """Attend que la vue et son panneau de couches soient prêts (jusqu'à ~2 minutes) puis active chaque couche demandée."""
    await asyncio.sleep(8)
    for nom in noms:
        for _ in range(25):
            r = await _ordre({"op": "couche", "nom": nom, "etat": True, "souple": True}, 5.0)
            if r and r[0]:
                break
            await asyncio.sleep(4)
        else:
            await _parler(f"Je n'ai pas réussi à activer {nom}{nom_virgule()}.")


async def _pilotage(t: str):
    t = t.strip(" .!?")
    if _LISTE.search(t):
        r = await _ordre({"op": "liste"})
        return r[1] if r else "La vue de Dieu ne répond pas."
    if _TOUTES_OFF.match(t):
        r = await _ordre({"op": "toutes_off"})
        return r[1] if r else "La vue de Dieu ne répond pas."
    for rx, etat in ((_COUCHE_ON, True), (_COUCHE_OFF, False)):
        m = rx.match(t)
        if m:
            nom = m.group("nom").strip()
            if _PAS_UN_LIEU.search(nom) and not m.group("c"):
                return None   # « montre la météo » reste à son resolver
            r = await _ordre({"op": "couche", "nom": nom, "etat": etat})
            if r is None:
                return "La vue de Dieu ne répond pas." if m.group("c") else None
            if r[0] or m.group("c"):
                return r[1]
            return None   # pas une couche : on laisse les autres resolvers (« désactive le micro »)
    m = _CHOIX.match(t)
    if m:
        nom = m.group("nom").strip()
        nom = _SYNONYMES.get(nom, nom)
        for op in ("option", "clic"):
            r = await _ordre({"op": op, "nom": nom})
            if r and r[0]:
                return r[1]
    return None


async def resoudre_vue_de_dieu(cmd: str):
    t = _clean(cmd)

    if _NOM.search(t):
        if _FERMER.search(t):
            if vdd.installation_en_cours:
                vdd.signaler_hud(False)
                await _diffuser({"action": "vue_de_dieu_hide"})
                return f"J'annule l'installation de God's Eye View{nom_virgule()}."
            if not (vdd.ouverte or vdd.en_ecoute()):
                return "La vue de Dieu n'est pas ouverte."
            await _diffuser({"action": "vue_de_dieu_hide"})
            vdd.arreter()
            return f"Vue de Dieu fermée{nom_virgule()}."

        if vdd.installation_en_cours:
            return "L'installation de God's Eye View est déjà en cours."

        if not vdd.installee():
            return await _proposer_installation()

        if _METTRE_A_JOUR.search(t):
            release = await asyncio.to_thread(vdd.mise_a_jour_disponible, True)
            if not release:
                return f"God's Eye View est déjà à jour{nom_virgule()}, version {vdd.version_installee()}."
            return await _lancer_installation(release, True)

        if _INSTALLER.search(t):
            return f"God's Eye View est déjà installé{nom_virgule()}, version {vdd.version_installee()}."

        # Ouverture : si une release plus récente existe (une vérification par jour, une fois par version), on propose la mise à jour d'abord
        release = await asyncio.to_thread(vdd.mise_a_jour_disponible)
        if release and await _proposer_mise_a_jour(release):
            return await _lancer_installation(release, True)
        reponse = await _ouvrir_vue()
        noms = _couches_demandees(t) if reponse.startswith("J'active la vue") else []
        if noms:   # « lance la vue de Dieu avec les bouchons activés » : les couches s'allument une fois la vue prête
            tache = asyncio.create_task(_activer_apres_ouverture(noms))
            _taches.add(tache)
            tache.add_done_callback(_taches.discard)
            return reponse + " J'activerai : " + ", ".join(noms) + "."
        return reponse

    if vdd.ouverte and not vdd.installation_en_cours:
        r = await _pilotage(t)
        if r:
            return r

    # Vue ouverte : « va à Tokyo » la dirige au lieu d'ouvrir le globe de JARVIS
    if vdd.ouverte and not vdd.installation_en_cours:
        m = _ALLER.match(t)
        if m:
            lieu = m.group("lieu").strip(" .!?")
            if _PAS_UN_LIEU.search(lieu):
                return None
            if not lieu or lieu in ("la terre", "terre", "le globe", "globe", "le monde", "monde"):
                await _diffuser({"action": "vue_de_dieu_goto", "ancre": "#v=2&lat=20&lon=10&alt=20000000&heading=0&pitch=-90"})
                return f"Je recule pour voir toute la Terre{nom_virgule()}."
            from core.web_bridge import geocode_lieu_detaille
            info = await geocode_lieu_detaille(lieu)
            if not info or float(info.get("importance", 0)) < 0.2:
                if m.group("verbe") in ("montre-moi", "montre moi", "affiche-moi", "affiche moi"):
                    return None   # « montre-moi … » peut être autre chose qu'un lieu : on laisse les autres resolvers répondre
                return f"Je ne trouve pas « {lieu} » sur la carte{nom_virgule()}."
            alt, pitch = _altitude_et_inclinaison(info.get("rang"))
            ancre = f"#v=2&lat={float(info['lat']):.5f}&lon={float(info['lon']):.5f}&alt={alt}&heading=0&pitch={pitch}"
            await _diffuser({"action": "vue_de_dieu_goto", "ancre": ancre})
            return f"En route vers {info.get('nom') or lieu}{nom_virgule()}."
    return None


builtins.resoudre_vue_de_dieu = resoudre_vue_de_dieu
