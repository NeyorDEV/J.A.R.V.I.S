"""Actions JSON du LLM liées aux services : Google, météo, web, vision, alarmes, Deezer."""

import asyncio
import json

import core.shared as shared
from controller.actions_pc import appeler_via_whatsapp
from controller.deezer_controller import (
    deezer_basculer_lecture, deezer_demarrer, deezer_piste_precedente, deezer_chercher, deezer_arreter,
    deezer_piste_suivante, deezer_regler_volume,
)
from core.llm_chat import interroger_ia
from core.micro import _lire_config
from core.confirmation import demander_confirmation
from core.speech import parler
from module.alarm_manager import ajouter_alarme, annuler_alarme, lister_alarmes
from module.google_services import (
    ajouter_ligne_sheet, archiver_email, charger_fichier_drive, complete_google_task,
    creer_dossier_drive, creer_evenement_calendar, nouveau_google_doc, nouvelle_feuille_google,
    creer_google_task, delete_google_task, expedier_email, lire_contenu_doc, lire_detail_email,
    lire_donnees_sheet, consulter_emails, evenements_agenda, lister_google_tasks,
    modifier_evenement_calendar, editer_google_doc, ouvrir_google_drive,
    partager_fichier_drive, rechercher_google_drive, repondre_au_mail, effacer_email,
    supprimer_evenement_calendar,
)
from module.image_search import images_par_moteur
from module.meteo_domotique import alertes_meteo, meteo_du_moment
from module.recherche_web import resume_recherche_web
from module.vision_module import (
    jarvis_vision_analyse_live, vision_camera, vision_cliquer,
    vision_saisir, vision_sur_navigateur, vision_recherche_site,
)
from module.visual_web_agent import run_visual_agent, stop_visual_agent
from core.interlocuteur import nom_espace, nom_ou_utilisateur, nom_virgule


async def _google(fonction, *args, **kwargs):
    """Appel Google (bloquant : réseau, voire connexion OAuth) dans un thread, pour ne pas
    figer la boucle WebSocket et le HUD pendant l'appel."""
    return await asyncio.to_thread(fonction, *args, **kwargs)


async def executer_actions_services(action, data, block, texte_utilisateur, reponse_propre):
    """Actions JSON « services » : Google, météo, web, vision, dictée, alarmes, antivirus, Deezer.

    Retourne True si l'action a été prise en charge par ce groupe.
    """
    if action == "open_drive":
        result = await _google(ouvrir_google_drive)
        parler(result)
    elif action == "search_drive":
        query = data.get("query") or None
        if query:
            parler(f"Je recherche les fichiers contenant '{query}' sur votre Google Drive...")
        else:
            parler("Je recherche vos fichiers récents sur votre Google Drive...")
        result = await _google(rechercher_google_drive, nom_fichier=query)
        parler(result)
    elif action == "create_doc":
        titre   = data.get("title",   "Document JARVIS")
        contenu = data.get("content", "")
        result  = await _google(nouveau_google_doc, titre, contenu)
        parler(result)
    elif action == "write_doc":
        contenu = data.get("content", "")
        result  = await _google(editer_google_doc, contenu)
        parler(result)
    elif action == "create_sheet":
        titre  = data.get("title", "Feuille JARVIS")
        result = await _google(nouvelle_feuille_google, titre)
        parler(result)
    elif action == "read_emails":
        result = await _google(consulter_emails)
        if "Aucun nouvel email" in result:
            parler(f"Vous n'avez aucun nouvel email non lu dans votre boîte principale{nom_virgule()}.")
        else:
            parler(f"Voici vos derniers emails non lus{nom_virgule()}. {result}")
    elif action == "read_calendar":
        result = await _google(evenements_agenda)
        parler(f"Voici vos prochains evenements{nom_espace()}. {result}")
    elif action == "create_task":
        titre = data.get("title") or data.get("titre") or ""
        notes = data.get("notes") or ""
        result = await _google(creer_google_task, titre, notes)
        parler(result)
    elif action == "list_tasks":
        result = await _google(lister_google_tasks)
        parler(f"Voici vos tâches à faire dans Google Tasks{nom_virgule()}. {result}")
    elif action == "complete_task":
        titre = data.get("title") or data.get("titre") or ""
        result = await _google(complete_google_task, titre)
        parler(result)
    elif action == "delete_task":
        titre = data.get("title") or data.get("titre") or ""
        if not await demander_confirmation(None, f"Supprimer la tâche « {titre} » ?"):
            parler(f"Suppression annulée{nom_virgule()}.")
        else:
            result = await _google(delete_google_task, titre)
            parler(result)
    elif action == "send_email":
        destinataire = data.get("to") or data.get("destinataire") or ""
        sujet = data.get("subject") or data.get("sujet") or "Message de JARVIS"
        corps = data.get("body") or data.get("corps") or ""
        if not await demander_confirmation(None, f"Envoyer un e-mail à {destinataire or 'un destinataire inconnu'}, sujet : {sujet} ?"):
            parler(f"Envoi annulé{nom_virgule()}.")
        else:
            result = await _google(expedier_email, destinataire, sujet, corps)
            parler(result)
    elif action == "reply_email":
        corps = data.get("body") or data.get("corps") or ""
        msg_id = data.get("original_msg_id") or None
        if not await demander_confirmation(None, "Envoyer cette réponse par e-mail ?"):
            parler(f"Réponse annulée{nom_virgule()}.")
        else:
            result = await _google(repondre_au_mail, corps, msg_id)
            parler(result)
    elif action == "read_full_email":
        msg_id = data.get("msg_id") or None
        result = await _google(lire_detail_email, msg_id)
        parler(f"Voici le contenu de l'e-mail : {result}")
    elif action == "archive_email":
        msg_id = data.get("msg_id") or None
        result = await _google(archiver_email, msg_id)
        parler(result)
    elif action == "delete_email":
        msg_id = data.get("msg_id") or None
        if not await demander_confirmation(None, "Mettre cet e-mail à la corbeille ?"):
            parler(f"Suppression annulée{nom_virgule()}.")
        else:
            result = await _google(effacer_email, msg_id)
            parler(result)
    elif action == "create_event":
        summary = data.get("summary") or data.get("titre") or "Événement"
        start_time = data.get("start") or data.get("debut") or ""
        end_time = data.get("end") or data.get("fin") or ""
        description = data.get("description") or None
        result = await _google(creer_evenement_calendar, summary, start_time, end_time, description)
        parler(result)
    elif action == "update_event":
        old_title = data.get("old_title") or data.get("ancien_titre") or ""
        new_title = data.get("new_title") or data.get("nouveau_titre") or None
        new_start = data.get("new_start") or data.get("nouvelle_heure") or None
        new_end = data.get("new_end") or data.get("fin_heure") or None
        result = await _google(modifier_evenement_calendar, old_title, new_title, new_start, new_end)
        parler(result)
    elif action == "delete_event":
        title = data.get("title") or data.get("titre") or ""
        if not await demander_confirmation(None, f"Supprimer l'événement « {title} » de votre agenda ?"):
            parler(f"Suppression annulée{nom_virgule()}.")
        else:
            result = await _google(supprimer_evenement_calendar, title)
            parler(result)
    elif action == "append_sheet":
        valeurs = data.get("values") or data.get("valeurs") or []
        sheet_id = data.get("spreadsheet_id") or None
        onglet = data.get("onglet") or "Feuille 1"
        result = await _google(ajouter_ligne_sheet, valeurs, sheet_id, onglet)
        parler(result)
    elif action == "read_sheet":
        cell_range = data.get("range") or data.get("plage") or "A1:Z10"
        sheet_id = data.get("spreadsheet_id") or None
        result = await _google(lire_donnees_sheet, cell_range, sheet_id)
        parler(f"Voici les données lues de la feuille : {result}")
    elif action == "read_doc":
        doc_id = data.get("doc_id") or None
        result = await _google(lire_contenu_doc, doc_id)
        parler(f"Voici le contenu du document : {result}")
    elif action == "upload_file":
        local_path = data.get("local_path") or data.get("chemin") or ""
        folder_id = data.get("folder_id") or data.get("dossier_id") or None
        result = await _google(charger_fichier_drive, local_path, folder_id)
        parler(result)
    elif action == "share_file":
        email = data.get("email") or data.get("destinataire") or ""
        role = data.get("role") or "reader"
        file_id = data.get("file_id") or None
        if not await demander_confirmation(None, f"Partager ce fichier avec {email or 'cette personne'} ?"):
            parler(f"Partage annulé{nom_virgule()}.")
        else:
            result = await _google(partager_fichier_drive, email, role, file_id)
            parler(result)
    elif action == "create_folder":
        folder_name = data.get("folder_name") or data.get("nom_dossier") or "Nouveau Dossier"
        parent_folder_id = data.get("parent_folder_id") or data.get("dossier_parent_id") or None
        result = await _google(creer_dossier_drive, folder_name, parent_folder_id)
        parler(result)
    elif action == "meteo":
        ville = data.get("ville") or None
        parler(f"Je consulte la meteo, un instant{nom_espace()}.")
        result = meteo_du_moment(ville)
        parler(result)
    elif action == "alerte_meteo":
        ville = data.get("ville") or None
        result = alertes_meteo(ville)
        parler(result)
    elif action == "recherche_web":
        query = data.get("query", "")
        parler(f"Je cherche sur internet : {query}.")
        result = resume_recherche_web(query)
        parler(result)
    elif action == "recherche_images":
        query = data.get("query", "")
        nb = int(data.get("nb", 6))
        parler(f"Je recherche des images de {query} sur internet, un instant{nom_espace()}.")
        cfg = _lire_config()
        engine = cfg.get("image_search_engine", "serpapi")
        urls = images_par_moteur(query, nb_images=nb, engine=engine)
        if urls:
            msg_json = json.dumps({
                "type": "show_images",
                "query": query,
                "images": urls,
            })
            if shared.CONNECTED_CLIENTS:
                try:
                    await asyncio.gather(*[ws.send(msg_json) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)
                except Exception as e:
                    print(f"[ERREUR WS] Broadcast images: {e}")
            parler(f"Voilà, j'affiche {len(urls)} image{'s' if len(urls) > 1 else ''} de {query} sur votre interface{nom_virgule()}.")
        else:
            parler(f"Désolé{nom_espace()}, je n'ai pas trouvé d'images pour {query}.")
    elif action == "recherche_approfondie":
        query = data.get("query", "")
        parler(f"Je lance une recherche approfondie sur {query}{nom_virgule()}. Cela peut prendre quelques secondes pendant que j'analyse les sources.")
        # Appel de l'agent autonome
        research_data = await shared.browser_agent.search_and_browse(query)
        if not research_data or "error" in research_data[0]:
            parler(f"Je suis désolé{nom_espace()}, mais je n'ai pas pu accéder aux sites web pour le moment.")
        else:
            # On prépare un prompt pour que l'IA synthétise les résultats
            context = "\n\n".join([f"Source: {d['url']}\nContenu: {d['content']}" for d in research_data])
            prompt_synthese = (
                f"Voici les résultats de ma recherche approfondie sur '{query}' :\n\n"
                f"{context}\n\n"
                f"En tant que JARVIS, fais une synthèse élégante, précise et complète de ces informations pour {nom_ou_utilisateur()}."
            )
            synthese = await interroger_ia(prompt_synthese, update_hist=False, skip_local=True)
            if synthese:
                print("\n[BROWSER] --- SOURCES CONSULTÉES ---")
                for d in research_data:
                    print(f" > {d['url']}")
                print("[BROWSER] ---------------------------\n")
                parler(synthese)

    elif action == "web_agent_task":
        task_desc = data.get("task", "")
        if not task_desc:
            parler(f"Désolé{nom_espace()}, je n'ai pas compris la tâche à effectuer.")
        else:
            result = await run_visual_agent(task_desc)
            parler(result)

    elif action == "fermer_navigateur_agent":
        result = await stop_visual_agent()
        parler(result)

    elif action == "voir_ecran":
        inst = data.get("instruction", "")
        res = await vision_cliquer(inst)
        parler(res)
    elif action == "whatsapp_appel":
        contact = data.get("contact")
        if contact:
            await appeler_via_whatsapp(contact)
            parler(f"Appel WhatsApp vers {contact} lancé.")
        else:
            parler(f"Désolé{nom_espace()}, je n'ai pas trouvé le nom du contact à appeler.")
    elif action == "vision_ecrire":
        inst = data.get("instruction", "")
        txt  = data.get("texte", "")
        res  = await vision_saisir(inst, txt)
        parler(res)
    elif action == "vision_chercher_sur_site":
        txt = data.get("texte", "")
        parler(f"Je cherche la barre de recherche sur ce site{nom_virgule()}.")
        res = await vision_recherche_site(txt)
        parler(res)
    elif action == "lance_camera":
        res = await vision_camera(texte_utilisateur)
        parler(res)
    elif action == "vision_navigateur":
        res = await vision_sur_navigateur(texte_utilisateur)
        parler(res)
    elif action == "analyse_live":
        question = data.get("question", "Analyse mon écran et aide-moi.")
        parler(f"Je jette un œil à votre écran, un instant{nom_espace()}.")
        res = await jarvis_vision_analyse_live(question)
        parler(res)

    elif action == "dictee":
        texte = data.get("texte", "")
        if texte:
            import pyautogui
            import pyperclip
            pyperclip.copy(texte)
            await asyncio.sleep(0.1)
            pyautogui.hotkey('ctrl', 'v')
            parler(f"C'est tapé{nom_virgule()}.")

    # --- ACTIONS ALARMES ---
    elif action == "alarme_set":
        heure = data.get("heure", "")
        label = data.get("label", "Alarme")
        ok, msg = ajouter_alarme(heure, label)
        parler(msg)
    elif action == "alarme_list":
        msg = lister_alarmes()
        # Si l'intro de l'IA annonce déjà les alarmes, on retire le préfixe redondant
        intro_lower = reponse_propre.lower()
        if "voici vos alarmes" in intro_lower or "voici tes alarmes" in intro_lower:
            if msg.startswith("Voici vos alarmes :"):
                msg = msg[len("Voici vos alarmes :"):].strip()
        parler(msg)
    elif action == "alarme_cancel":
        heure = data.get("heure", "")
        label = data.get("label", "")
        ok, msg = annuler_alarme(heure, label)
        parler(msg)
    elif action == "antivirus_scan":
        if shared.CONNECTED_CLIENTS:
            msg = json.dumps({"type": "av_open"})
            await asyncio.gather(*[ws.send(msg) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)
        parler(f"J'initialise le protocole d'analyse de sécurité de votre système{nom_virgule()}. Scan en cours.")
    elif action in ("spotify_ouvrir", "deezer_demarrer"):
        parler(f"J'ouvre Deezer{nom_virgule()}.")
        res = await deezer_demarrer()
        parler(res)
    elif action in ("spotify_rechercher", "deezer_chercher"):
        recherche = data.get("recherche", "")
        parler(f"Je recherche '{recherche}' sur Deezer{nom_virgule()}.")
        res = await deezer_chercher(recherche)
        parler(res)
    elif action in ("spotify_lecture_pause", "deezer_basculer_lecture"):
        res = await deezer_basculer_lecture()
        parler(res)
    elif action in ("spotify_stop", "deezer_arreter"):
        res = await deezer_arreter()
        parler(res)
    elif action in ("spotify_suivant", "deezer_piste_suivante"):
        res = await deezer_piste_suivante()
        parler(res)
    elif action in ("spotify_precedent", "deezer_piste_precedente"):
        res = await deezer_piste_precedente()
        parler(res)
    elif action in ("spotify_volume", "deezer_regler_volume"):
        direction = data.get("direction", "monter")
        paliers   = data.get("paliers", 4)
        res = await deezer_regler_volume(direction, paliers)
        parler(res)
    else:
        return False
    return True
