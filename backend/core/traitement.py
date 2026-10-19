"""Traitement d'une commande : resolvers locaux, intention LLM, réponse IA, parole puis actions."""

import asyncio
import builtins
import json
import re
import time

import core.shared as shared
from core.actions_ia import executer_action
from core.confirmation import confirmation_en_attente, resoudre_confirmation_vocale
from core.etat_parole import set_stop_parler
from core.llm_chat import interroger_ia
from core.llm_providers import interroger_grok
from core.speech import parler
from core.web_bridge import envoyer_etat_hud
from module.commandes_locales import traiter_commandes_locales
from module.echecs_local import resoudre_echecs_localement
from module.alarmes_local import resoudre_alarmes_localement
from core.interlocuteur import nom_ou_utilisateur, nom_virgule


# « Deezer » (« dizeur ») est transcrit « 10 heures » par Whisper (mesuré : « Jarvis, ferme
# Deezer » → « jarvis, ferme 10 heures »). Après un verbe d'application ou « sur », une heure
# n'a pas de sens : c'est Deezer. « mets une alarme à 10 heures » n'est pas touché (« à »).
_DEEZER_ENTENDU = r"(?:10 ?heures?|10 ?h|dix heures?|dizz?e?u?r|deesear|dieser)"
_RE_DEEZER_MAL_ENTENDU = re.compile(
    r"\b(ferme|fermes|quitte|ouvre|ouvres|lance|lances|relance|redemarre|redémarre|coupe|sur|dans)\s+"
    + _DEEZER_ENTENDU + r"(?=\s*[.!?]*\s*$|\s+(?:stp|s'il te pla[iî]t|svp)\b)")


def epurer_commande(texte):
    t = texte.lower().strip()
    for variante in ["jarvis,", "jarvis", "jervis,", "jervis", "service,", "service"]:
        if t.startswith(variante):
            t = t[len(variante):].strip()
    # (« fermes », « lances » : conjugaisons fantaisistes de Whisper, ramenées à l'impératif)
    t = _RE_DEEZER_MAL_ENTENDU.sub(lambda m: re.sub(r"(ferme|ouvre|lance)s$", r"\1", m.group(1)) + " deezer", t)
    return t


def est_action_oriented(texte):
    t = texte.lower()
    mots_actions = [
        "oublie", "oublier", "supprime", "supprimer", "efface", "effacer", "vide", "vider", "annule", "annuler", "retire", "retirer",
        "met", "alarme", "reveil", "réveil", "minuteur", "lance", "joue", "ouvre", "ferme", "éteins", "allume", "active", "désactive",
        "spotify", "deezer", "trie", "crée", "creer", "renomme", "déplace", "cherche", "recherche", "analyse", "weather", "météo", "meteo",
        "ajoute", "ajouter", "tâche", "tache", "valide", "valider", "complete", "completer", "termine", "terminer", "drive",
        "envoie", "envoyer", "réponds", "repondre", "reponds", "agenda", "calendrier", "partage", "partager", "tableur", "ligne",
        "cellule", "mail", "email", "courriel", "doc", "document", "téléverse", "televerse", "téléverser", "televerser", "charge",
        "charger", "dossier", "sheet", "sheets", "docs"
    ]
    return any(m in t for m in mots_actions)


def _texte_substantiel(texte: str) -> bool:
    """False pour du bruit (ponctuation seule, interjection isolée, « ! »…).

    Sert de garde-fou avant d'interroger le dispatcher d'intentions LLM : sans
    elle, dire juste « Jarvis ! » (rien après le mot de réveil) envoyait « ! »
    au modèle de function calling, qui pouvait halluciner un appel de fonction
    sur une entrée aussi pauvre — vécu en réel : « ! » a été classé comme
    « crée un site web », déclenchant tout un swarm de 6 agents pour rien.
    """
    lettres = sum(1 for c in texte if c.isalpha())
    if lettres < 3:
        return False
    # Acquiescement ou interjection seuls (« oui », « d'accord », « merci »…) : pas une
    # commande. Vécu : « Jarvis, oui. » a été classé « montre le calendrier ».
    mots = re.findall(r"[a-zà-ÿœ']+", texte.lower())
    return not mots or not all(m in _INTERJECTIONS for m in mots)


_INTERJECTIONS = {
    "oui", "ouais", "ouaip", "non", "nan", "ok", "okay", "d'accord", "dac", "merci", "beaucoup",
    "super", "cool", "parfait", "génial", "genial", "top", "bien", "très", "tres", "bon", "voilà",
    "voila", "exactement", "carrément", "carrement", "ah", "oh", "eh", "euh", "hein", "hmm", "bof",
    "quoi", "salut", "bonjour", "bonsoir", "coucou", "yo", "ça", "ca", "marche", "c'est", "si",
    "pas", "grave", "vas-y", "vas", "y", "allez", "et", "alors", "bah", "ben", "enfin", "jarvis",
}


# Ordre de priorité des resolvers, du plus spécifique au plus générique.
# Avant, une boucle passait d'abord TOUS les builtins.resoudre_* dans l'ordre
# ALPHABÉTIQUE, puis la chaîne « statique » : l'ordre voulu était ignoré, et des
# resolvers génériques (lanceur d'applis par sous-chaîne, calcul, système…) passaient
# avant des commandes précises (« lance le radar réseau » lançait EA App).
# Les resolvers ajoutés à chaud (compétences, plugins créés en cours de route) sont
# insérés à la place marquée par None ; la mémoire (et son cache sémantique, qui
# répond à toute phrase ressemblant à un ancien échange) reste en tout dernier.
_ORDRE_RESOLVEURS = [
    # Commandes précises (phrases ou mots-clés explicites)
    "resoudre_dom_hud", "resoudre_developpement", "resoudre_uninstaller_localement", "resoudre_local_mode",
    "resoudre_lancer_enigme", "resoudre_os_autopilot", "resoudre_creation_plugin",
    "resoudre_generation_document", "resoudre_images_locales", "resoudre_modifier_image",
    "resoudre_recipe", "resoudre_connexions_reseau",
    "resoudre_dev_swarm", "resoudre_lance_sandbox", "resoudre_creation_site_web",
    "resoudre_ouvrir_site_web", "resoudre_tv_localement",
    None,  # ← resolvers ajoutés à chaud
    # Commandes générales
    "commandes_locales", "resoudre_commandes_systeme", "traiter_infos_systeme",
    "resoudre_listes_locales", "resoudre_temps_localement", "traiter_conversion_locale",
    "traiter_traduction_locale", "traiter_question_francais", "traiter_extras_locaux",
    # Globe : déclencheurs génériques (« montre… », « affiche… ») suivis d'un géocodage réseau
    "traiter_globe_local", "resoudre_apps_localement",
    # En dernier : mémoire (cache sémantique)
    "resoudre_memoire_locale",
]
# Resolvers refusés à une voix non reconnue (mode invité) : ils agissent sur le PC, le
# code ou des fichiers. (Les commandes sensibles de commandes_locales — coffre-fort,
# compétences, fermeture des navigateurs — vérifient le locuteur elles-mêmes.)
_INTERDITS_INVITE = {
    "resoudre_os_autopilot", "resoudre_creation_plugin", "resoudre_dev_swarm",
    "resoudre_lance_sandbox", "resoudre_creation_site_web", "resoudre_uninstaller_localement",
    "resoudre_local_mode", "resoudre_generation_document", "resoudre_modifier_image",
    "resoudre_memoire_locale", "resoudre_developpement",
}
# Fonctions builtins.resoudre_* qui ne sont pas des resolvers de commande
_HORS_CHAINE = {"interpreter_chemin", "resoudre_echecs_localement",
                "resoudre_mon_resolver"}


def _sequence_resolveurs():
    connus = set(_ORDRE_RESOLVEURS) | _HORS_CHAINE
    a_chaud = sorted(n for n in dir(builtins) if n.startswith("resoudre_") and n not in connus)
    sequence = []
    for nom in _ORDRE_RESOLVEURS:
        sequence.extend(a_chaud if nom is None else [nom])
    return sequence


async def _essayer_resolvers_statiques(texte):
    """Chaîne des resolvers par mots-clés, dans l'ordre de priorité (_ORDRE_RESOLVEURS).

    Appelée avec la phrase de l'utilisateur, puis éventuellement une seconde
    fois avec la phrase canonique produite par le dispatch function calling.
    """
    global dernier_resolveur
    for nom in _sequence_resolveurs():
        if nom in _INTERDITS_INVITE and getattr(shared, "ACTIVE_SPEAKER", "guest") == "guest":
            continue   # mode invité (avant, seules les actions JSON du LLM étaient filtrées)
        fn = traiter_commandes_locales if nom == "commandes_locales" else getattr(builtins, nom, None)
        if fn is None:
            continue
        try:
            reponse = await fn(texte) if asyncio.iscoroutinefunction(fn) else fn(texte)
        except Exception as e:
            # Un resolver en erreur ne doit pas priver l'utilisateur de réponse
            # (avant, l'exception remontait et la commande restait sans suite).
            print(f"[RESOLVEUR] Erreur dans {nom} : {type(e).__name__} : {e}")
            continue
        if reponse:
            dernier_resolveur = nom
            print(f"[DEBUG] Commande résolue par : {nom}")
            return reponse
    return None


dernier_resolveur = None   # nom du resolver qui a répondu à la dernière commande (journal, tests)


async def _resoudre_localement(texte_utilisateur):
    """Résolution sans IA : échecs, alarmes, contextes en attente, puis les resolvers."""
    global dernier_resolveur
    dernier_resolveur = None
    reponse = None
    # Échecs (Priorité absolue pour intercepter les coups et éviter de charger la DB vectorielle de la mémoire locale)
    if not reponse:
        reponse = await resoudre_echecs_localement(texte_utilisateur)
        if reponse: dernier_resolveur = "echecs"

    # Alarmes, minuteurs, rappels : avant tout plugin, sinon « mets une alarme à 7 h »
    # partait dans la recherche Deezer de secours (phrases commençant par « mets »).
    if not reponse:
        reponse = await resoudre_alarmes_localement(texte_utilisateur)
        if reponse: dernier_resolveur = "alarmes"

    # Modification d'image en attente d'instruction (Priorité absolue pour éviter qu'un
    # mot de l'instruction de retouche ne soit intercepté par un autre resolver avant elle)
    if not reponse and hasattr(builtins, "resoudre_modifier_image"):
        from plugins.image_edit_resolver import _attente_modif_image
        if _attente_modif_image["actif"]:
            reponse = await builtins.resoudre_modifier_image(texte_utilisateur)
            if reponse: dernier_resolveur = "resoudre_modifier_image"

    # Interception prioritaire des compétences vocales personnalisées pour éviter les conflits avec les plugins (ex: radar réseau)
    if not reponse and any(k in texte_utilisateur.lower() for k in ["compétence", "competence"]):
        reponse = await traiter_commandes_locales(texte_utilisateur)
        if reponse: dernier_resolveur = "commandes_locales"

    if not reponse:
        reponse = await _essayer_resolvers_statiques(texte_utilisateur)
    return reponse


async def gerer_reponse_ia(texte_utilisateur, from_voice=False, de_confiance=False):
    """Enveloppe garantissant que l'état « réflexion » est toujours relâché.

    Sans ce try/finally, is_thinking restait à True dès qu'une commande était
    traitée par un resolver local (le cas le plus fréquent) : seul le chemin LLM
    le réinitialisait. Conséquence : la détection de claps se désactivait
    définitivement après la première commande, et le HUD ne repassait jamais
    en état « idle ».
    """
    try:
        return await _traiter_reponse_ia_impl(
            texte_utilisateur, from_voice=from_voice, de_confiance=de_confiance
        )
    finally:
        shared.is_thinking = False
        try:
            await envoyer_etat_hud("idle")
        except Exception:
            pass


async def _traiter_reponse_ia_impl(texte_utilisateur, from_voice=False, de_confiance=False):
    shared.dernier_message = time.time()
    shared._derniere_reponse_streamed = False
    shared.phrases_streamed = []

    # Une confirmation d'action destructrice est en attente : "oui"/"non" doit
    # la résoudre immédiatement, AVANT le verrou de traitement (traiter_lock),
    # sinon la réponse resterait bloquée derrière l'action qui attend justement
    # cette confirmation pour continuer (deadlock logique).
    if confirmation_en_attente():
        if resoudre_confirmation_vocale(epurer_commande(texte_utilisateur)):
            return
    if from_voice:
        shared.jarvis_actif = True  # Seules les commandes vocales ouvrent/maintiennent la session
    elif de_confiance:
        # Clavier du HUD local : l'utilisateur est physiquement devant la machine.
        shared.ACTIVE_SPEAKER = "neyor"
        builtins.ACTIVE_SPEAKER = "neyor"

    if shared.traiter_lock.locked():
        # La commande attend son tour (avant, elle était purement et simplement jetée).
        parler(f"Je termine ce que je fais{nom_virgule()}, je m'en occupe juste après.")

    async with shared.traiter_lock:
        # STOP_PARLER doit être réarmé APRÈS l'obtention du verrou : le remettre à
        # False dès l'entrée annulait le barge-in (« stop ») d'une réponse encore
        # en cours d'énonciation, qui repartait alors de plus belle.
        shared.STOP_PARLER = False
        set_stop_parler(False)
        shared.is_thinking = True
        reponse = None
        
        # NETTOYAGE DU TEXTE (Enlever 'Jarvis' au début pour ne pas perturber les plugins)
        texte_utilisateur = epurer_commande(texte_utilisateur)

        # TENTATIVE DE RÉSOLUTION LOCALE (Commandes, Math, Français, etc.)
        print(f"[DEBUG] Tentative de résolution locale pour : {texte_utilisateur}")
        reponse = await _resoudre_localement(texte_utilisateur)

        # FUNCTION CALLING GEMINI : aucun resolver par mots-clés n'a compris la phrase.
        # Un modèle rapide la mappe sur une intention connue (→ phrase canonique) qu'on
        # repasse dans les resolvers. Tout échec suit le chemin historique (interroger_ia).
        if (not reponse and shared._USE_LLM_INTENT and _texte_substantiel(texte_utilisateur)
                and (est_action_oriented(texte_utilisateur) or len(texte_utilisateur.split()) <= 12)):
            try:
                from core.intent_dispatcher import resoudre_intention_llm
                phrase_canonique = await resoudre_intention_llm(texte_utilisateur)
                if phrase_canonique and phrase_canonique.lower().strip() != texte_utilisateur.lower().strip():
                    # Résolution locale complète : avec la seule chaîne des plugins, alarmes,
                    # minuteurs et échecs (traités avant elle) n'étaient jamais atteints —
                    # « mets une alarme à 10h » repartait à l'IA
                    reponse = await _resoudre_localement(phrase_canonique)
                    if reponse:
                        print(f"[INTENT] Résolu via phrase canonique : « {phrase_canonique} »")
            except Exception as e:
                print(f"[INTENT] Erreur dispatch function calling : {e}")

        if not reponse:
            force_skip_local = est_action_oriented(texte_utilisateur)
            reponse = await interroger_ia(texte_utilisateur, skip_local=force_skip_local)
        
        # print(f"[JARVIS] {reponse}")

        # Robustesse type : Si le résolveur a retourné un booléen, le convertir en chaîne
        if isinstance(reponse, bool):
            reponse = "Commande exécutée." if reponse else ""
        # ... et si ce n'est toujours pas du texte (None, dict, etc.), normaliser :
        # extract_json_blocks() itère sur la valeur et levait un TypeError hors de
        # tout try, ce qui interrompait le traitement avant la moindre parole et
        # laissait is_thinking bloqué à True.
        if reponse is None:
            reponse = ""
        elif not isinstance(reponse, str):
            reponse = str(reponse)

        # 1. Extraction robuste des blocs JSON
        def extract_json_blocks(text):
            blocks = []
            stack = []
            start = -1
            for i, char in enumerate(text):
                if char == '{':
                    if not stack: start = i
                    stack.append('{')
                elif char == '}':
                    if stack:
                        stack.pop()
                        if not stack:
                            blocks.append(text[start:i+1])
            return blocks

        json_blocks = extract_json_blocks(reponse)
        reponse_propre = reponse
        for b in json_blocks:
            reponse_propre = reponse_propre.replace(b, "")
        reponse_propre = reponse_propre.strip()

        # Si la réponse contient une action système (autre que auto_memoriser), on supprime la parole conversationnelle
        contient_action_systeme = False
        for block in json_blocks:
            try:
                data = json.loads(block)
                action = data.get("action", "")
                if action and action != "auto_memoriser":
                    contient_action_systeme = True
                    break
            except:
                pass

        # 2. PAROLE (avant d'exécuter les actions pour respecter l'ordre naturel d'énonciation)
        texte_a_parler = "" if contient_action_systeme else reponse_propre
        if texte_a_parler and shared.phrases_streamed:
            for phrase in shared.phrases_streamed:
                phrase_strip = phrase.strip()
                if texte_a_parler.strip().startswith(phrase_strip):
                    idx = texte_a_parler.find(phrase_strip)
                    texte_a_parler = texte_a_parler[idx + len(phrase_strip):].strip()

        if texte_a_parler:
            texte_reel = re.sub(r'[^\w\s]', '', texte_a_parler).strip()
            if texte_reel:
                builtins.parler(texte_a_parler, print_console=True)

        # 3. EXÉCUTION DES ACTIONS
        for block in json_blocks:
            try:
                if any(x in block for x in ["NOM_DU_CONTACT", "VALEUR_ICI", "CLE_ICI", "chemin/complet"]):
                    continue

                print(f"[JARVIS] Action en cours : {block}")
                data = json.loads(block)
                action = data.get("action", "")
                
                # Sécurité mode invité : bloquer uniquement les actions définies comme sensibles (fichiers, vision/écrans, Google APIs)
                restricted_actions = {
                    # Fichiers / Sécurité
                    "afficher_dossier", "enumerer_dossier", "classer_par_type", "classer_par_date", 
                    "trier_complet", "creer_dossier", "changer_nom_fichier", "transferer_fichier", 
                    "rechercher_fichier", "ouvrir_element", "analyser_fichier", "antivirus_scan",
                    # Vision / Screenshots / Autopilot
                    "voir_ecran", "vision_ecrire", "vision_chercher_sur_site", "vision_navigateur",
                    "analyse_live", "web_agent_task",
                    # Google APIs
                    "open_drive", "search_drive", "create_doc", "write_doc", "create_sheet",
                    "read_sheet", "read_doc", "upload_file", "share_file", "create_folder", "append_sheet",
                    "read_emails", "send_email", "reply_email", "read_full_email", "archive_email", "delete_email",
                    "read_calendar", "create_event", "update_event", "delete_event",
                    "create_task", "list_tasks", "complete_task", "delete_task",
                    # Code, sites, saisie, appels, mémoire de l'utilisateur
                    "creer_site_web", "creer_site", "generer_site", "dictee", "whatsapp_appel",
                    "memoriser", "auto_memoriser", "oublier", "lister_memoire", "github_action",
                }
                if getattr(shared, "ACTIVE_SPEAKER", "neyor") == "guest" and action in restricted_actions:
                    print(f"🔒 [SPEAKER] Action '{action}' bloquée en mode invité.")
                    parler("Désolé, cette action est restreinte en mode invité. Veuillez vous authentifier.")
                    continue

                await executer_action(action, data, block, texte_utilisateur, reponse_propre)

            except Exception as e:
                print(f"[ACTION ERROR] Block failed: {block} | Error: {e}")
                if shared.grok_client:
                    print("[JARVIS] Action en échec : relais à Grok...")
                    res_grok = await interroger_grok(f"{nom_ou_utilisateur()} m'a demandé : {texte_utilisateur}. Mon action a échoué sur une erreur technique ({e}). Réponds-lui à ma place, avec élégance.")
                    if res_grok: parler(res_grok)
                continue

        return
