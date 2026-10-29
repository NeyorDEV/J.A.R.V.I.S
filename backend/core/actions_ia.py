"""Exécution des actions JSON produites par le LLM (aiguillage + actions système)."""

import asyncio
import builtins
import json
import os

import chess

import controller.homepod_controller as homepod_controller
import core.shared as shared
from core import module_catalogue
from core.actions_ia_services import executer_actions_services
from core.ha_mcp_client import executer_action_ha
from core.llm_chat import interroger_ia
from core.mcp_client import executer_action_mcp
from core.speech import parler
from core.web_bridge import diffuser_echecs, envoyer_image_web, _safe_ws_send
from module.chess_manager import ChessGame
from module.echecs_local import _annonce_fin
from module.domotique_sim import domotic_route_audio
from module.file_manager import (
    rechercher_fichier, creer_dossier_enfant, transferer_fichier, lire_fichier, enumerer_dossier,
    afficher_dossier, ouvrir_fichier_ou_dossier, changer_nom_fichier, classer_par_date,
    classer_par_type, classer_par_type_et_date,
)
from module.image_generator import generer_image_ia
from module.memory_manager import noter_en_memoire, relire_memoire, oublier_memoire
from core.interlocuteur import nom_createur, nom_espace, nom_ou_utilisateur, nom_virgule


async def executer_action(action, data, block, texte_utilisateur, reponse_propre):
    """Exécute une action JSON produite par le LLM (même ordre de priorité que la chaîne d'origine)."""
    module_catalogue.annoncer_pour_action(action)
    if await _actions_systeme(action, data, block, texte_utilisateur, reponse_propre):
        return
    if await executer_actions_services(action, data, block, texte_utilisateur, reponse_propre):
        return
    # Envoi par défaut au frontend pour les actions personnalisées/inconnues
    if "action" in data or "type" in data:
        _safe_ws_send(block)


async def _actions_systeme(action, data, block, texte_utilisateur, reponse_propre):
    """Actions JSON « système » : échecs, mémoire, fichiers, images, domotique, GitHub, DOM, HomePod.

    Retourne True si l'action a été prise en charge par ce groupe.
    """
    if action == "chess_start":
        shared.CHESS_GAME = ChessGame()
        shared.CHESS_GAME_ACTIVE = False
        state = shared.CHESS_GAME.get_state()
        await diffuser_echecs({
            "action": "chess_start",
            "state": state
        })
        parler(f"Très bien{nom_espace()}. J'ai disposé le plateau 3D sur le HUD. Veuillez configurer la partie et la démarrer.")
    elif action == "chess_stop":
        shared.CHESS_GAME = None
        shared.CHESS_GAME_ACTIVE = False
        await diffuser_echecs({
            "action": "chess_stop"
        })
        parler(f"Partie d'échecs interrompue{nom_virgule()}. Retour au HUD standard.")
    elif action == "chess_play":
        if not shared.CHESS_GAME:
            parler(f"Aucune partie d'échecs n'est en cours{nom_virgule()}.")
        else:
            move_str = data.get("move", "")
            try:
                # Jouer coup du joueur
                move, state = shared.CHESS_GAME.play_player_move(move_str)
                await diffuser_echecs({
                    "action": "chess_game_state",
                    "state": state,
                    "last_move": {
                        "from": chess.square_name(move.from_square),
                        "to": chess.square_name(move.to_square),
                        "color": "white" if shared.CHESS_GAME.player_color == chess.WHITE else "black"
                    }
                })
                if state["is_game_over"]:
                    couleur = shared.CHESS_GAME.player_color
                    shared.CHESS_GAME = None
                    parler(_annonce_fin(state["result"], couleur))
                else:
                    # Faire réfléchir JARVIS et jouer
                    await diffuser_echecs({
                        "action": "chess_thinking",
                        "thinking": True
                    })
                    thinking_time = shared.CHESS_GAME.calculate_thinking_time()
                    print(f"[CHESS] JARVIS réfléchit pendant {thinking_time:.2f} secondes (Elo: {shared.CHESS_GAME.difficulty})...")
                    await asyncio.sleep(thinking_time)
                    j_move, remark, j_state = shared.CHESS_GAME.play_jarvis_move()
                    await diffuser_echecs({
                        "action": "chess_game_state",
                        "state": j_state,
                        "last_move": {
                            "from": chess.square_name(j_move.from_square),
                            "to": chess.square_name(j_move.to_square),
                            "color": "black" if shared.CHESS_GAME.player_color == chess.WHITE else "white"
                        }
                    })
                    if j_state["is_game_over"]:
                        couleur = shared.CHESS_GAME.player_color
                        shared.CHESS_GAME = None
                        parler(_annonce_fin(j_state["result"], couleur, remark))
                    else:
                        parler(remark)
            except ValueError as e:
                parler(str(e))
    elif action == "mode_iron_man":
        # `etat` n'était jamais lu depuis le JSON : NameError systématique,
        # avalé par le catch-all → le mode ne s'activait jamais.
        etat = data.get("etat", "on")
        shared.MODE_IRON_MAN = (etat == "on")
        msg = f"Mode Iron Man activé{nom_virgule()}. Je reste à l'écoute de vos signaux." if shared.MODE_IRON_MAN else "Mode Iron Man désactivé. Je repasse en veille domotique."
        parler(msg)
    elif action == "auto_memoriser":
        cle    = data.get("cle",    "info")
        valeur = data.get("valeur", "")
        noter_en_memoire(cle, valeur)
        if hasattr(builtins, "_notify_factual_memory_added"):
            builtins._notify_factual_memory_added(cle, valeur)
    elif action == "memoriser":
        cle    = data.get("cle",    "info")
        valeur = data.get("valeur", "")
        noter_en_memoire(cle, valeur)
        if hasattr(builtins, "_notify_factual_memory_added"):
            builtins._notify_factual_memory_added(cle, valeur)
        parler(f"Bien note{nom_espace()}, je me souviendrai que {valeur}.")
    elif action == "oublier":
        cle     = data.get("cle", "")
        # Supprimer de la mémoire clé-valeur
        success_kv = oublier_memoire(cle)
        # Supprimer également de la DB vectorielle
        from module.vector_memory import supprimer_souvenir_semantique
        success_vect = supprimer_souvenir_semantique(cle)

        if success_kv or success_vect:
            if success_kv:
                _safe_ws_send(json.dumps({"action": "cortex_update", "deleted_id": f"kv_{cle}"}))
            if success_vect:
                _safe_ws_send(json.dumps({"action": "cortex_update", "deleted_id": cle}))
            parler(f"Information oubliee{nom_virgule()}.")
        else:
            parler("Cette information n'était pas dans ma mémoire.")
    elif action == "lister_memoire":
        memoire = relire_memoire()
        if not memoire:
            parler(f"Aucune information personnalisee en memoire{nom_virgule()}.")
        else:
            lignes = [f"Voici ce que je sais sur vous{nom_espace()}."]
            for cle, data_m in memoire.items():
                lignes.append(f"{cle} : {data_m['valeur']}.")
            parler(" ".join(lignes))
    elif action in ["creer_site_web", "creer_site", "generer_site"]:
        desc = data.get("description") or data.get("sujet") or data.get("prompt") or "un site web"
        # (« backend.plugins… » chargeait le module une seconde fois, sous un autre nom)
        from plugins.dev_swarm_resolver import run_dev_swarm_process
        from core.web_bridge import demarrer_tache_fond
        demarrer_tache_fond(run_dev_swarm_process(desc))
        parler(f"Très bien{nom_espace()}, je mobilise l'essaim d'agents d'élite pour coder votre projet. Suivi actif sur le HUD.")
    elif action == "generer_image":
        prompt = data.get("prompt", "")
        if prompt:
            parler(f"Très bien{nom_espace()}, je génère l'image de {prompt}. Un instant...")
            img_data = await asyncio.to_thread(generer_image_ia, prompt)
            if img_data:
                await envoyer_image_web(img_data, prompt)
                parler(f"Voici l'image demandée{nom_virgule()}. Elle s'affiche sur votre interface.")
            else:
                parler(f"Désolé{nom_espace()}, la génération d'image a échoué.")
        else:
            parler(f"Que souhaitez-vous que je dessine{nom_virgule()} ?")
    elif action == "afficher_dossier":
        chemin = data.get("chemin", "bureau")
        ok, resultat = afficher_dossier(chemin)
        if ok:
            parler(f"Dossier ouvert{nom_virgule()}. Dites-moi si vous voulez que je le trie.")
        else:
            parler(f"Je n ai pas trouve ce dossier{nom_virgule()}. {resultat}")
    elif action == "analyser_fichier":
        nom = data.get("nom", "")
        question = data.get("question", "Peux-tu me résumer ce document ?")
        if nom:
            parler(f"Je lis le fichier {nom}... Un instant.")
            texte_fichier, err_ou_chemin = lire_fichier(nom, chemin=data.get("chemin"))
            if texte_fichier is None:
                parler(err_ou_chemin)
            else:
                prompt_analyse = (
                    f"URGENT : Tu es JARVIS, l'assistant personnel de {nom_createur()}. Tu réponds à {nom_ou_utilisateur()}.\n"
                    f"Tu viens d'extraire le contenu du fichier '{nom}'.\n"
                    f"Voici ce contenu :\n\n{texte_fichier}\n\n"
                    f"L'utilisateur demande : {question}\n"
                    f"Analyse ce contenu et réponds directement en restant dans ton personnage de JARVIS (poli, efficace, un peu sarcastique)."
                )
                rep_analyse = await interroger_ia(prompt_analyse, update_hist=False, skip_local=True)
                if rep_analyse:
                    parler(rep_analyse)
                else:
                    parler(f"Désolé{nom_espace()}, j'ai lu le fichier mais je n'arrive pas à synthétiser une réponse.")
        else:
            parler("Je n'ai pas compris quel fichier vous souhaitez que j'analyse.")
    elif action == "enumerer_dossier":
        contenu, err = enumerer_dossier()
        if err:
            parler(err)
        else:
            nb_fichiers = len(contenu["fichiers"])
            nb_dossiers = len(contenu["dossiers"])
            parler(f"Le dossier contient {nb_fichiers} fichiers et {nb_dossiers} sous-dossiers{nom_virgule()}.")
    elif action == "classer_par_type":
        parler(f"Je trie vos fichiers par type{nom_virgule()}. Un instant.")
        ok, msg = classer_par_type()
        parler(msg if ok else f"Probleme lors du tri : {msg}")
    elif action == "classer_par_date":
        parler(f"Je trie vos fichiers par date{nom_virgule()}. Un instant.")
        ok, msg = classer_par_date()
        parler(msg if ok else f"Probleme lors du tri : {msg}")
    elif action == "trier_complet":
        parler(f"Je trie vos fichiers par type puis par date dans chaque categorie{nom_virgule()}.")
        ok, msg = classer_par_type_et_date()
        parler(msg if ok else f"Probleme lors du tri : {msg}")
    elif action == "creer_dossier":
        nom     = data.get("nom", "Nouveau Dossier")
        ok, msg = creer_dossier_enfant(nom)
        parler(msg if ok else f"Erreur : {msg}")
    elif action == "changer_nom_fichier":
        ancien  = data.get("ancien", "")
        nouveau = data.get("nouveau", "")
        ok, msg = changer_nom_fichier(ancien, nouveau)
        parler(msg if ok else f"Erreur : {msg}")
    elif action == "transferer_fichier":
        fichier = data.get("fichier",     "")
        dest    = data.get("destination", "")
        ok, msg = transferer_fichier(fichier, dest)
        parler(msg if ok else f"Erreur : {msg}")
    elif action == "rechercher_fichier":
        nom = data.get("nom", "")

        # Détection du type demandé AVANT nettoyage
        type_demande = None
        if "dossier" in nom.lower() or "repertoire" in nom.lower():
            type_demande = "dossier"
        elif "fichier" in nom.lower() or "document" in nom.lower():
            type_demande = "fichier"

        # Nettoyage intelligent du nom (suppression des articles et mots parasites)
        parasites = ["trouve moi le dossier ", "trouve moi le fichier ", "trouve moi le ", 
                     "recherche le dossier ", "recherche le fichier ", "recherche le ",
                     "le dossier ", "le fichier ", "un dossier ", "un fichier ",
                     "dossier ", "fichier ", "mon dossier ", "mon fichier ", 
                     "le ", "la ", "les ", "un ", "une ", "des ", "moi "]

        nom_clean = nom.lower()
        for p in parasites:
            if nom_clean.startswith(p):
                nom_clean = nom_clean[len(p):].strip()
                break

        # On nettoie encore les petits mots si besoin
        mots = nom_clean.split()
        if mots and mots[0] in ["le", "la", "un", "une", "moi", "mon", "ma"]:
            mots = mots[1:]
        nom_final = " ".join(mots) if mots else nom_clean
        if not nom_final: nom_final = nom

        # Message plus précis
        type_msg = "le dossier" if type_demande == "dossier" else ("le fichier" if type_demande == "fichier" else "l'élément")
        parler(f"Recherche de {type_msg} '{nom_final}' en cours...")

        resultats, err = rechercher_fichier(nom_final, scan_global=True, type_cible=type_demande)
        if err:
            parler(err)
        elif not resultats:
            parler(f"Je n'ai rien trouvé correspondant à '{nom}'{nom_virgule()}.")
        else:
            cible = resultats[0]
            ok, msg = ouvrir_fichier_ou_dossier(cible)
            if ok:
                parler(f"J'ai trouvé {os.path.basename(cible)} et je l'ouvre immédiatement.")
            else:
                parler(f"J'ai trouvé {os.path.basename(cible)} mais je n'ai pas pu l'ouvrir : {msg}")
    elif action == "ouvrir_element":
        chemin = data.get("chemin", "")
        ok, msg = ouvrir_fichier_ou_dossier(chemin)
        parler(msg if ok else f"Erreur : {msg}")
    elif action == "ha_action":
        # Domotique générique via le client MCP Home Assistant : Gemini
        # reformule la demande en instruction, un second appel Gemini
        # (dans executer_action_ha) choisit l'outil MCP exposé par HA
        # et ses paramètres. Remplace l'ancien bloc d'actions codées en
        # dur par type d'appareil (voir core/ha_mcp_client.py).
        instruction = data.get("instruction", "")
        if instruction:
            resultat = await executer_action_ha(instruction)
            parler(resultat)
    elif action == "github_action":
        # GitHub via le client MCP générique (core/mcp_client.py) :
        # même principe que ha_action, mais réutilisable pour
        # n'importe quel futur serveur MCP (server_name différent).
        instruction = data.get("instruction", "")
        if instruction:
            resultat = await executer_action_mcp("github", instruction)
            parler(resultat)
    elif action == "dom_sequence":
        steps = data.get("steps", [])
        if hasattr(builtins, "send_web_action"):
            remaining_steps = []
            for step in steps:
                action_type = step.get("action_type", "click")
                text = step.get("text", "")

                # Si c'est une ouverture d'URL, on le fait localement via le navigateur par défaut
                if action_type == "open_url" and text:
                    import webbrowser
                    webbrowser.open(text, new=2)
                    await asyncio.sleep(5.0)  # Laisser le temps au navigateur de charger le site
                    continue

                remaining_steps.append(step)

            # Envoyer toutes les étapes DOM restantes en un seul bloc à l'extension
            if remaining_steps:
                payload = {"type": "dom_action", "action": "dom_sequence", "steps": remaining_steps}
                _safe_ws_send(json.dumps(payload))
                from core.extension_bridge import diffuser as diffuser_extension
                await diffuser_extension(payload)  # extensions authentifiées seulement
    elif action == "homepod_action":
        cmd   = data.get("commande", "play")
        val   = data.get("valeur")
        piece = data.get("piece")
        ok, res = await homepod_controller.send_command(cmd, val, identifier=piece)
        if ok:
            if cmd == "volume":
                parler(f"Volume du HomePod {piece or ''} réglé à {val}%.")
            else:
                parler(f"Commande {cmd} exécutée sur le HomePod {piece or ''}.")
    elif action == "domotic_route_audio":
        source = data.get("source", "salon")
        dest   = data.get("destination", "chambre")
        await domotic_route_audio(source, dest)
    else:
        return False
    return True
