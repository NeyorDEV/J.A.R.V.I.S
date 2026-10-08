"""Commandes locales sans IA : point d'entrée, compétences, système, images, voix."""

import asyncio
import json
import re

import core.shared as shared
from core.speech import parler
from core.web_bridge import envoyer_carte_contextuelle, envoyer_image_web
from module.commandes_locales_sections import (
    _commandes_apps_musique, _commandes_identite_hud, _PAS_TROUVE,
)
from module.competences import (
    executer_competence_vocale, jarvis_creer_competence, jarvis_supprimer_competence,
)
from module.image_generator import generer_affiche_ia, generer_image_ia
from core.interlocuteur import nom_espace, nom_virgule


def _est_invite():
    """True si la voix qui parle n'a pas été reconnue (mode invité)."""
    return getattr(shared, "ACTIVE_SPEAKER", "guest") == "guest"


def _parser_demande_affiche(t):
    """
    Extrait d'une demande d'affiche vocale : le sujet visuel (pour l'IA image),
    les dates/lieu, et le texte explicite à superposer ("... met le texte : ...").
    Heuristique volontairement simple (regex), pas de NLP lourd.
    """
    import re
    texte_bas = None
    m_texte = re.search(r"texte\s*:\s*(.+)$", t)
    if m_texte:
        texte_bas = m_texte.group(1).strip().rstrip(".")
        t_sans_texte = t[:m_texte.start()]
    else:
        t_sans_texte = t

    m_dates = re.search(r"du\s+\d{1,2}/\d{1,2}\s+au\s+\d{1,2}/\d{1,2}", t_sans_texte)
    dates_str = m_dates.group(0) if m_dates else None

    m_lieu = re.search(r"(?<![\wÀ-ÖØ-öø-ÿ])(?:a|à)\s+([A-Za-zÀ-ÖØ-öø-ÿ\-]{3,})\s+du\s+\d{1,2}/\d{1,2}", t_sans_texte)
    lieu = m_lieu.group(1).title() if m_lieu else None

    m_visuel = re.search(
        r"image\s+d['’](?:un|une)\s+(.+?)(?:\s+avec\s+les\s+dates|\s+avec\s+la\s+date|\s+met\s|$)",
        t_sans_texte
    )
    visuel = m_visuel.group(1).strip() if m_visuel else t_sans_texte.strip()

    lignes_bas = []
    if lieu and dates_str:
        lignes_bas.append(f"{lieu} — {dates_str}".title())
    elif dates_str:
        lignes_bas.append(dates_str)
    if texte_bas:
        lignes_bas.append(texte_bas)

    return visuel, lignes_bas


async def resoudre_commandes_locales(texte):
    """Détecte et exécute les commandes locales (Spotify, dossiers, apps) sans IA."""
    t = texte.lower().strip()

    _res = await _commandes_competences_systeme(t)
    if _res is not _PAS_TROUVE:
        return _res

    _res = await _commandes_carte_voix(t)
    if _res is not _PAS_TROUVE:
        return _res


    # --- GESTION DU CONTEXTE MULTI-TOURS ---
    if shared.attente_nom_dossier:
        t = f"ouvre le dossier {t}"
        shared.attente_nom_dossier = False
    elif shared.attente_nom_app:
        t = f"ouvre l'application {t}"
        shared.attente_nom_app = False
    else:
        # Interception des commandes incompletes
        if t in ["ouvre le dossier", "ouvre mon dossier", "ouvre un dossier"]:
            shared.attente_nom_dossier = True
            return f"Quel dossier voulez-vous ouvrir{nom_virgule()} ?"
        elif t in ["ouvre l'application", "lance l'application", "ouvre le logiciel", "lance le logiciel", "ouvre", "lance"]:
            shared.attente_nom_app = True
            return f"Quelle application voulez-vous lancer{nom_virgule()} ?"

        # --- FERMETURE DU NAVIGATEUR EXTERNE (musique/vidéo en fond) ---
        # Fermeture du navigateur. Avant, « arrête la musique », « ferme la page des
        # paramètres » ou « quitte la fenêtre du globe » fermaient TOUS les navigateurs
        # (et Deezer continuait de jouer) : il faut maintenant nommer un navigateur.
        navigateurs = {
            "chrome": ["chrome.exe"], "edge": ["msedge.exe"], "firefox": ["firefox.exe"],
            "opera": ["opera.exe"], "brave": ["brave.exe"],
        }
        mots_generiques = ["navigateur", "internet", "le web", "youtube"]
        if re.search(r"\b(ferme|fermer|quitte|quitter)\b", t) and not _est_invite():
            cibles = [proc for nom, procs in navigateurs.items() if re.search(rf"\b{nom}\b", t) for proc in procs]
            if not cibles and any(w in t for w in mots_generiques):
                cibles = [proc for procs in navigateurs.values() for proc in procs]
            if cibles:
                import subprocess
                for proc in cibles:
                    try:
                        subprocess.run(["taskkill", "/IM", proc], capture_output=True)
                    except Exception as e:
                        print(f"[BROWSER] Erreur de fermeture douce de {proc} : {e}")
                return f"Je ferme le navigateur{nom_virgule()}."


    _res = await _commandes_identite_hud(t)
    if _res is not _PAS_TROUVE:
        return _res

    return await _commandes_apps_musique(t)


async def _commandes_competences_systeme(t):
    """Compétences autonomes, Winget, antivirus, génération d'images, garde-fou des commandes complexes."""
    import re
    # Mode invité : compétences (code exécuté), mises à jour et antivirus sont réservés
    # aux voix reconnues (avant, seules les actions JSON du LLM étaient filtrées).
    if _est_invite() and re.search(r"competence|compétence|winget|mise.? a jour|mises? à jour|logiciels|antivirus|virus|scanne|analyse mon (pc|ordinateur)", t):
        return f"Désolé, cette commande est réservée aux utilisateurs reconnus{nom_virgule()}."
    # ── SYSTEME DE PLUGINS DE COMPETENCES AUTONOMES ────────────────────────────
    # 1. Création / Apprentissage de compétence
    if "crée la compétence" in t or "cree la competence" in t or "apprends la compétence" in t or "apprends la competence" in t:
        # Format attendu : "Crée la compétence [nom] pour [description]" ou "Apprends la compétence [nom] : [description]"
        match = re.search(r'(?:crée|cree|apprends)\s+la\s+compétence\s+(.+?)\s+(?:pour|qui|de|:)\s+(.+)', t)
        if match:
            nom = match.group(1).strip()
            desc = match.group(2).strip()
            res = await asyncio.to_thread(jarvis_creer_competence, nom, desc)
            return res
        else:
            return f"Désolé{nom_espace()}, le format pour créer une compétence est : 'Crée la compétence [nom] pour [description]'."

    # 2. Suppression de compétence
    if "supprime la compétence" in t or "supprime la competence" in t or "désinstalle la compétence" in t or "desinstalle la competence" in t:
        match = re.search(r'(?:supprime|désinstalle|desinstalle)\s+la\s+compétence\s+(.+)', t)
        if match:
            nom = match.group(1).strip()
            res = jarvis_supprimer_competence(nom)
            return res

    # 3. Exécution explicite de compétence
    if "exécute la compétence" in t or "execute la competence" in t or "lance la compétence" in t or "lance la competence" in t:
        match = re.search(r'(?:exécute|execute|lance)\s+la\s+compétence\s+(.+?)(?:\s+avec\s+(.+))?$', t)
        if match:
            nom = match.group(1).strip()
            param = match.group(2).strip() if match.group(2) else None
            res = await asyncio.to_thread(executer_competence_vocale, nom, param)
            return res

    # 4. Liste des compétences personnalisées
    if any(k in t for k in ["liste les compétences", "liste mes compétences", "liste tes compétences", "quelles sont mes compétences", "affiche mes compétences", "liste toutes mes compétences", "liste toutes tes compétences"]):
        import os
        # Les compétences sont écrites dans backend/plugins/ (module/competences.py) :
        # la racine du projet n'a pas de dossier plugins/.
        dossier_plugins = os.path.join(shared.RACINE_PROJET, "backend", "plugins")
        if not os.path.exists(dossier_plugins):
            return "Vous n'avez actuellement aucune compétence personnalisée installée."
        files = [f for f in os.listdir(dossier_plugins) if f.startswith("competence_") and f.endswith(".py")]
        if not files:
            return "Vous n'avez actuellement aucune compétence personnalisée installée."
        noms = []
        for f in files:
            nom_skill = f[len("competence_"):-len(".py")].replace("_", " ")
            noms.append(nom_skill)
        noms_str = ", ".join(noms)
        return f"Voici vos compétences personnalisées installées : {noms_str}."

    # ══ MISES À JOUR LOGICIELS (WINGET) ═════════════════════════════
    _winget_phrases = [
        "mets à jour mes logiciels", "lance les mises à jour", "ouvre les mises à jour", 
        "vérifie les mises à jour", "mise à jour logiciels", "ouvre winget", "lance winget"
    ]
    for p in _winget_phrases:
        if p in t:
            if shared.CONNECTED_CLIENTS:
                msg = json.dumps({"action": "winget_open"})
                await asyncio.gather(*[ws.send(msg) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)
            return f"J'ouvre le gestionnaire de mise à jour système et je lance la recherche des mises à jour disponibles{nom_virgule()}."

    # ══ ANALYSE ANTIVIRUS ══════════════════════════════════════════
    _av_phrases = [
        "analyse mon pc", "analyse mon ordinateur", "scanne mon pc", "scanne mon ordinateur",
        "recherche des virus", "recherche si j'ai des virus", "lance l'antivirus",
        "lance un scan antivirus", "analyse antivirus", "vérifie les virus", "lance le scan antivirus"
    ]
    for p in _av_phrases:
        if p in t:
            if shared.CONNECTED_CLIENTS:
                msg = json.dumps({"type": "av_open"})
                await asyncio.gather(*[ws.send(msg) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)
            return f"J'ouvre la console de sécurité et j'initialise le scan antivirus de votre ordinateur{nom_virgule()}."

    # --- GÉNÉRATION D'IMAGES / AFFICHES (Priorité 0.5) ---
    # Placé avant le garde-fou "commande complexe" ci-dessous : un prompt d'image
    # contient très souvent " et " (ex: "noir et blanc") et se faisait sinon
    # avaler par ce garde-fou avant d'atteindre le vrai bloc de génération plus bas.
    if any(k in t for k in ["génère", "genere", "crée une image", "cree une image", "dessine"]):
        import re
        prompt = re.sub(r'(jarvis|génère(-moi| moi|)?|genere(-moi| moi|)?|crée|cree|dessine(-moi| moi|)?)( une| l\'| des| de l\'|) ?(image|photo|dessin|illustration)? ?(de |d\'|d\'une |d\'un |des )?', '', t).strip()

        if prompt:
            # Demande d'AFFICHE (poster) avec texte explicite à superposer (dates, infos...) :
            # un modèle d'image ne sait pas écrire du texte lisible, donc on sépare le
            # visuel (généré par l'IA) du texte (superposé proprement avec Pillow).
            if "affiche" in t and ("texte" in t or re.search(r"\d{1,2}/\d{1,2}", t)):
                visuel, lignes_bas = _parser_demande_affiche(t)
                parler(f"Très bien{nom_espace()}, je compose l'affiche. Un instant...")
                img_data = await asyncio.to_thread(generer_affiche_ia, visuel, lignes_bas)
            else:
                parler(f"Très bien{nom_espace()}, je génère l'image de {prompt}. Un instant...")
                img_data = await asyncio.to_thread(generer_image_ia, prompt)
            if img_data:
                await envoyer_image_web(img_data, prompt)
                return f"Voici l'image demandée{nom_virgule()}. Elle s'affiche sur votre interface."
            return f"Désolé{nom_espace()}, la génération d'image a échoué."
        return f"Que souhaitez-vous que je dessine{nom_virgule()} ?"

    # S'il s'agit d'une commande complexe avec des enchaînements ou des actions DOM/saisie,
    # on renvoie None pour laisser le "cerveau" IA (LLM) s'en occuper de façon autonome.
    if any(k in t for k in ["saisis", "clique", "tape", "ecris", "ecrit", "remplace", "dans la", "barre de", " et ", " puis "]):
        return None
    return _PAS_TROUVE


async def _commandes_carte_voix(t):
    """Carte de test du HUD et changement de voix."""
    # --- TEST CARTES CONTEXTUELLES ---
    if ("carte" in t and "test" in t) or "affiche une carte" in t:
        await envoyer_carte_contextuelle(
            "Test Protocole", 
            "Ceci est une carte de test générée par le système contextuel. Tous les capteurs sont opérationnels.",
            type_carte="info",
            icon="◈"
        )
        return f"Carte de test affichée sur le HUD{nom_virgule()}."

    # --- CHANGEMENT DE VOIX ---
    # speech.py lit core.config.VOIX_ACTUELLE : modifier seulement shared.VOIX_ACTUELLE
    # annonçait le changement sans l'appliquer.
    import core.config as config
    if any(kw in t for kw in ["prends la voix d'homme", "prends la voix de l'homme", "voix d'homme", "voix masculine"]):
        if config.VOIX_ACTUELLE == "homme":
            return f"Ma voix est déjà configurée sur le mode masculin{nom_virgule()}."
        config.VOIX_ACTUELLE = shared.VOIX_ACTUELLE = "homme"
        return f"Très bien{nom_espace()}, je reprends ma voix habituelle."

    if any(kw in t for kw in ["prends la voix de femme", "prends la voix d'une femme", "voix de femme", "voix féminine"]):
        if config.VOIX_ACTUELLE == "femme":
            return f"Ma voix est déjà configurée sur le mode féminin{nom_virgule()}."
        config.VOIX_ACTUELLE = shared.VOIX_ACTUELLE = "femme"
        return f"C'est entendu{nom_espace()}, je passe sur une fréquence vocale féminine."
    return _PAS_TROUVE
