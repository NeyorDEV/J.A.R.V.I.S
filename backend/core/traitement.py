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
from core.llm_chat import demander_ia
from core.llm_providers import demander_grok
from core.speech import parler
from core.web_bridge import send_web_state
from module.commandes_locales import resoudre_commandes_locales
from module.echecs_local import resoudre_echecs_localement
from core.interlocuteur import nom_ou_utilisateur, nom_virgule


def nettoyer_commande(texte):
    t = texte.lower().strip()
    for variante in ["jarvis,", "jarvis", "jervis,", "jervis", "service,", "service"]:
        if t.startswith(variante):
            t = t[len(variante):].strip()
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
    return lettres >= 3


async def _essayer_resolvers_statiques(texte):
    """Chaîne des resolvers par mots-clés, dans l'ordre de priorité.

    Appelée avec la phrase de l'utilisateur, puis éventuellement une seconde
    fois avec la phrase canonique produite par le dispatch function calling.
    """
    reponse = None
    if not reponse: reponse = await builtins.resoudre_dom_hud(texte)
    if not reponse: reponse = await resoudre_commandes_locales(texte)
    if not reponse:
        if hasattr(builtins, "resoudre_creation_site_web"):
            reponse = await builtins.resoudre_creation_site_web(texte)
    if not reponse: reponse = await builtins.resoudre_commandes_systeme(texte)
    if not reponse: reponse = await builtins.resoudre_tv_localement(texte)
    if not reponse: reponse = await builtins.resoudre_apps_localement(texte)
    if not reponse: reponse = await builtins.resoudre_infos_systeme_localement(texte)
    if not reponse: reponse = await builtins.resoudre_memoire_locale(texte)
    if not reponse: reponse = await builtins.resoudre_temps_localement(texte)
    if not reponse: reponse = await builtins.resoudre_listes_locales(texte)
    if not reponse: reponse = await builtins.resoudre_francais_localement(texte)
    if not reponse: reponse = await builtins.resoudre_conversion_localement(texte)
    if not reponse: reponse = await builtins.resoudre_traduction_localement(texte)
    if not reponse: reponse = await builtins.resoudre_globe_localement(texte)
    if not reponse: reponse = await builtins.resoudre_extras_locaux(texte)
    return reponse


async def traiter_reponse_ia(texte_utilisateur, mobile_ws=None, from_voice=False, de_confiance=False):
    """Enveloppe garantissant que l'état « réflexion » est toujours relâché.

    Sans ce try/finally, is_thinking restait à True dès qu'une commande était
    traitée par un resolver local (le cas le plus fréquent) : seul le chemin LLM
    le réinitialisait. Conséquence : la détection de claps se désactivait
    définitivement après la première commande, et le HUD ne repassait jamais
    en état « idle ».
    """
    try:
        return await _traiter_reponse_ia_impl(
            texte_utilisateur, mobile_ws=mobile_ws,
            from_voice=from_voice, de_confiance=de_confiance
        )
    finally:
        shared.is_thinking = False
        try:
            await send_web_state("idle")
        except Exception:
            pass


async def _traiter_reponse_ia_impl(texte_utilisateur, mobile_ws=None, from_voice=False, de_confiance=False):
    shared.dernier_message = time.time()
    shared._derniere_reponse_streamed = False
    shared.phrases_streamed = []

    # Une confirmation d'action destructrice est en attente : "oui"/"non" doit
    # la résoudre immédiatement, AVANT le verrou de traitement (traiter_lock),
    # sinon la réponse resterait bloquée derrière l'action qui attend justement
    # cette confirmation pour continuer (deadlock logique).
    if confirmation_en_attente():
        if resoudre_confirmation_vocale(nettoyer_commande(texte_utilisateur)):
            return
    if from_voice:
        shared.jarvis_actif = True  # Seules les commandes vocales ouvrent/maintiennent la session
    elif de_confiance:
        # Clavier du HUD local : l'utilisateur est physiquement devant la machine.
        shared.ACTIVE_SPEAKER = "neyor"
        builtins.ACTIVE_SPEAKER = "neyor"
    # NB : les commandes distantes (mobile) ne promeuvent PLUS le locuteur.
    # Auparavant tout message écrit forçait ACTIVE_SPEAKER = "neyor" : un locuteur
    # classé « guest » par la biométrie n'avait qu'à passer par le mobile pour
    # débloquer toutes les actions sensibles pour le reste de la session.

    if shared.traiter_lock.locked():
        parler(f"Je termine ce que je fais{nom_virgule()}. Un instant.")
        return

    async with shared.traiter_lock:
        # STOP_PARLER doit être réarmé APRÈS l'obtention du verrou : le remettre à
        # False dès l'entrée annulait le barge-in (« stop ») d'une réponse encore
        # en cours d'énonciation, qui repartait alors de plus belle.
        shared.STOP_PARLER = False
        set_stop_parler(False)
        shared.is_thinking = True
        reponse = None
        # Reset du flag audio au début de chaque commande
        shared._skip_pc_audio = False
        
        # NETTOYAGE DU TEXTE (Enlever 'Jarvis' au début pour ne pas perturber les plugins)
        texte_utilisateur = nettoyer_commande(texte_utilisateur)

        # TENTATIVE DE RÉSOLUTION LOCALE (Commandes, Math, Français, etc.)
        print(f"[DEBUG] Tentative de résolution locale pour : {texte_utilisateur}")
        # Échecs (Priorité absolue pour intercepter les coups et éviter de charger la DB vectorielle de la mémoire locale)
        if not reponse: reponse = await resoudre_echecs_localement(texte_utilisateur)

        # Modification d'image en attente d'instruction (Priorité absolue pour éviter qu'un
        # mot de l'instruction de retouche ne soit intercepté par un autre resolver avant elle)
        if not reponse and hasattr(builtins, "resoudre_modifier_image"):
            from plugins.image_edit_resolver import _attente_modif_image
            if _attente_modif_image["actif"]:
                reponse = await builtins.resoudre_modifier_image(texte_utilisateur)

        # Interception prioritaire des compétences vocales personnalisées pour éviter les conflits avec les plugins (ex: radar réseau)
        if not reponse and any(k in texte_utilisateur.lower() for k in ["compétence", "competence"]):
            reponse = await resoudre_commandes_locales(texte_utilisateur)

        # Résolution locale dynamique (Pour les résolveurs additionnels enregistrés à chaud sans redémarrage)
        if not reponse:
            for attr_name in sorted(dir(builtins)):
                if attr_name.startswith("resoudre_") and attr_name not in ["resoudre_developpement", "resoudre_dom_hud", "resoudre_chemin", "resoudre_echecs_localement", "resoudre_globe_localement"]:
                    try:
                        resolver_fn = getattr(builtins, attr_name)
                        if asyncio.iscoroutinefunction(resolver_fn):
                            reponse = await resolver_fn(texte_utilisateur)
                        else:
                            reponse = resolver_fn(texte_utilisateur)
                        if reponse:
                            print(f"[DEBUG] Commande résolue dynamiquement par : {attr_name}")
                            break
                    except Exception as e:
                        print(f"[DEBUG DYNAMIC] Erreur lors de l'appel du résolveur {attr_name} : {e}")

        if not reponse: reponse = await _essayer_resolvers_statiques(texte_utilisateur)

        # FUNCTION CALLING GEMINI : aucun resolver par mots-clés n'a compris la phrase.
        # Un modèle rapide la mappe sur une intention connue (→ phrase canonique) qu'on
        # repasse dans les resolvers. Tout échec suit le chemin historique (demander_ia).
        if (not reponse and shared._USE_LLM_INTENT and _texte_substantiel(texte_utilisateur)
                and (est_action_oriented(texte_utilisateur) or len(texte_utilisateur.split()) <= 12)):
            try:
                from core.intent_dispatcher import resoudre_intention_llm
                phrase_canonique = await resoudre_intention_llm(texte_utilisateur)
                if phrase_canonique and phrase_canonique.lower().strip() != texte_utilisateur.lower().strip():
                    reponse = await _essayer_resolvers_statiques(phrase_canonique)
                    if reponse:
                        print(f"[INTENT] Résolu via phrase canonique : « {phrase_canonique} »")
            except Exception as e:
                print(f"[INTENT] Erreur dispatch function calling : {e}")

        if not reponse:
            force_skip_local = est_action_oriented(texte_utilisateur)
            reponse = await demander_ia(texte_utilisateur, skip_local=force_skip_local)
        
        # print(f"[JARVIS] {reponse}")

        # Si commande mobile : activer le flag pour couper l'audio PC et répondre via mobile
        if mobile_ws:
            shared._skip_pc_audio = True

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

                print(f"[JARVIS] Execution de l'action : {block}")
                data = json.loads(block)
                action = data.get("action", "")
                
                # Sécurité mode invité : bloquer uniquement les actions définies comme sensibles (fichiers, vision/écrans, Google APIs)
                restricted_actions = {
                    # Fichiers / Sécurité
                    "ouvrir_dossier", "lister_dossier", "trier_par_type", "trier_par_date", 
                    "trier_complet", "creer_dossier", "renommer_fichier", "deplacer_fichier", 
                    "chercher_fichier", "ouvrir_element", "analyser_fichier", "antivirus_scan",
                    # Vision / Screenshots / Autopilot
                    "voir_ecran", "vision_ecrire", "vision_chercher_sur_site", "vision_navigateur",
                    "analyse_live", "web_agent_task",
                    # Google APIs
                    "open_drive", "search_drive", "create_doc", "write_doc", "create_sheet",
                    "read_sheet", "read_doc", "upload_file", "share_file", "create_folder", "append_sheet",
                    "read_emails", "send_email", "reply_email", "read_full_email", "archive_email", "delete_email",
                    "read_calendar", "create_event", "update_event", "delete_event",
                    "create_task", "list_tasks", "complete_task", "delete_task"
                }
                if getattr(shared, "ACTIVE_SPEAKER", "neyor") == "guest" and action in restricted_actions:
                    print(f"🔒 [SPEAKER] Action '{action}' bloquée en mode invité.")
                    parler("Désolé, cette action est restreinte en mode invité. Veuillez vous authentifier.")
                    continue

                await executer_action(action, data, block, texte_utilisateur, reponse_propre)

            except Exception as e:
                print(f"[ACTION ERROR] Block failed: {block} | Error: {e}")
                if shared.grok_client:
                    print("[JARVIS] Bascule sur Grok suite a une erreur d'action...")
                    res_grok = await demander_grok(f"{nom_ou_utilisateur()} m'a demandé : {texte_utilisateur}. J'ai tenté de lancer une action mais j'ai eu une erreur technique ({e}). Peux-tu prendre le relais et lui répondre élégamment ?")
                    if res_grok: parler(res_grok)
                continue

        shared._skip_pc_audio = False
        return
