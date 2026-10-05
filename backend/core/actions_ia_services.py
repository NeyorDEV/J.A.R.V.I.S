"""Actions JSON du LLM liées aux services : Google, météo, web, sport, vision, alarmes, Deezer."""

import asyncio
import json
import time

import core.shared as shared
from controller.actions_pc import action_whatsapp_appel
from controller.deezer_controller import (
    deezer_lecture_pause, deezer_ouvrir, deezer_precedent, deezer_rechercher, deezer_stop,
    deezer_suivant, deezer_volume,
)
from core.llm_chat import demander_ia
from core.llm_providers import demander_grok
from core.micro import _charger_config
from core.speech import parler
from module.alarm_manager import ajouter_alarme, annuler_alarme, lister_alarmes
from module.google_services import (
    ajouter_ligne_sheet, archiver_email, charger_fichier_drive, complete_google_task,
    creer_dossier_drive, creer_evenement_calendar, creer_google_doc, creer_google_sheet,
    creer_google_task, delete_google_task, envoyer_email, lire_contenu_doc, lire_detail_email,
    lire_donnees_sheet, lire_emails, lister_evenements_calendar, lister_google_tasks,
    modifier_evenement_calendar, modifier_google_doc, ouvrir_google_drive,
    partager_fichier_drive, rechercher_google_drive, repondre_email, supprimer_email,
    supprimer_evenement_calendar,
)
from module.image_search import recherche_images_web
from module.meteo_domotique import get_alertes_meteo, get_meteo_actuelle
from module.sports_web import (
    get_classement_football, get_resultats_football, get_resultats_sport_gemini,
    recherche_web_serpapi,
)
from module.vision_module import (
    jarvis_vision_analyse_live, jarvis_vision_camera, jarvis_vision_cliquer,
    jarvis_vision_ecrire, jarvis_vision_navigateur, jarvis_vision_rechercher_sur_site,
)
from module.visual_web_agent import run_visual_agent, stop_visual_agent


async def executer_actions_services(action, data, block, texte_utilisateur, reponse_propre):
    """Actions JSON « services » : Google, météo, web, sport, vision, dictée, alarmes, antivirus, Deezer.

    Retourne True si l'action a été prise en charge par ce groupe.
    """
    if action == "open_drive":
        result = ouvrir_google_drive()
        parler(result)
    elif action == "search_drive":
        query = data.get("query") or None
        if query:
            parler(f"Je recherche les fichiers contenant '{query}' sur votre Google Drive...")
        else:
            parler("Je recherche vos fichiers récents sur votre Google Drive...")
        result = rechercher_google_drive(nom_fichier=query)
        parler(result)
    elif action == "create_doc":
        titre   = data.get("title",   "Document JARVIS")
        contenu = data.get("content", "")
        result  = creer_google_doc(titre, contenu)
        parler(result)
    elif action == "write_doc":
        contenu = data.get("content", "")
        result  = modifier_google_doc(contenu)
        parler(result)
    elif action == "create_sheet":
        titre  = data.get("title", "Feuille JARVIS")
        result = creer_google_sheet(titre)
        parler(result)
    elif action == "read_emails":
        result = lire_emails()
        if "Aucun nouvel email" in result:
            parler("Vous n'avez aucun nouvel email non lu dans votre boîte principale, mylane.")
        else:
            parler(f"Voici vos derniers emails non lus, mylane. {result}")
    elif action == "read_calendar":
        result = lister_evenements_calendar()
        parler(f"Voici vos prochains evenements mylane. {result}")
    elif action == "create_task":
        titre = data.get("title") or data.get("titre") or ""
        notes = data.get("notes") or ""
        result = creer_google_task(titre, notes)
        parler(result)
    elif action == "list_tasks":
        result = lister_google_tasks()
        parler(f"Voici vos tâches à faire dans Google Tasks, mylane. {result}")
    elif action == "complete_task":
        titre = data.get("title") or data.get("titre") or ""
        result = complete_google_task(titre)
        parler(result)
    elif action == "delete_task":
        titre = data.get("title") or data.get("titre") or ""
        result = delete_google_task(titre)
        parler(result)
    elif action == "send_email":
        destinataire = data.get("to") or data.get("destinataire") or ""
        sujet = data.get("subject") or data.get("sujet") or "Message de JARVIS"
        corps = data.get("body") or data.get("corps") or ""
        result = envoyer_email(destinataire, sujet, corps)
        parler(result)
    elif action == "reply_email":
        corps = data.get("body") or data.get("corps") or ""
        msg_id = data.get("original_msg_id") or None
        result = repondre_email(corps, msg_id)
        parler(result)
    elif action == "read_full_email":
        msg_id = data.get("msg_id") or None
        result = lire_detail_email(msg_id)
        parler(f"Voici le contenu de l'e-mail : {result}")
    elif action == "archive_email":
        msg_id = data.get("msg_id") or None
        result = archiver_email(msg_id)
        parler(result)
    elif action == "delete_email":
        msg_id = data.get("msg_id") or None
        result = supprimer_email(msg_id)
        parler(result)
    elif action == "create_event":
        summary = data.get("summary") or data.get("titre") or "Événement"
        start_time = data.get("start") or data.get("debut") or ""
        end_time = data.get("end") or data.get("fin") or ""
        description = data.get("description") or None
        result = creer_evenement_calendar(summary, start_time, end_time, description)
        parler(result)
    elif action == "update_event":
        old_title = data.get("old_title") or data.get("ancien_titre") or ""
        new_title = data.get("new_title") or data.get("nouveau_titre") or None
        new_start = data.get("new_start") or data.get("nouvelle_heure") or None
        new_end = data.get("new_end") or data.get("fin_heure") or None
        result = modifier_evenement_calendar(old_title, new_title, new_start, new_end)
        parler(result)
    elif action == "delete_event":
        title = data.get("title") or data.get("titre") or ""
        result = supprimer_evenement_calendar(title)
        parler(result)
    elif action == "append_sheet":
        valeurs = data.get("values") or data.get("valeurs") or []
        sheet_id = data.get("spreadsheet_id") or None
        onglet = data.get("onglet") or "Feuille 1"
        result = ajouter_ligne_sheet(valeurs, sheet_id, onglet)
        parler(result)
    elif action == "read_sheet":
        cell_range = data.get("range") or data.get("plage") or "A1:Z10"
        sheet_id = data.get("spreadsheet_id") or None
        result = lire_donnees_sheet(cell_range, sheet_id)
        parler(f"Voici les données lues de la feuille : {result}")
    elif action == "read_doc":
        doc_id = data.get("doc_id") or None
        result = lire_contenu_doc(doc_id)
        parler(f"Voici le contenu du document : {result}")
    elif action == "upload_file":
        local_path = data.get("local_path") or data.get("chemin") or ""
        folder_id = data.get("folder_id") or data.get("dossier_id") or None
        result = charger_fichier_drive(local_path, folder_id)
        parler(result)
    elif action == "share_file":
        email = data.get("email") or data.get("destinataire") or ""
        role = data.get("role") or "reader"
        file_id = data.get("file_id") or None
        result = partager_fichier_drive(email, role, file_id)
        parler(result)
    elif action == "create_folder":
        folder_name = data.get("folder_name") or data.get("nom_dossier") or "Nouveau Dossier"
        parent_folder_id = data.get("parent_folder_id") or data.get("dossier_parent_id") or None
        result = creer_dossier_drive(folder_name, parent_folder_id)
        parler(result)
    elif action == "meteo":
        ville = data.get("ville") or None
        parler("Je consulte la meteo, un instant mylane.")
        result = get_meteo_actuelle(ville)
        parler(result)
    elif action == "alerte_meteo":
        ville = data.get("ville") or None
        result = get_alertes_meteo(ville)
        parler(result)
    elif action == "recherche_web":
        query = data.get("query", "")
        parler(f"Je lance une recherche sur internet pour {query}.")
        result = recherche_web_serpapi(query)
        parler(result)
    elif action == "recherche_images":
        query = data.get("query", "")
        nb = int(data.get("nb", 6))
        parler(f"Je recherche des images de {query} sur internet, un instant mylane.")
        cfg = _charger_config()
        engine = cfg.get("image_search_engine", "serpapi")
        urls = recherche_images_web(query, nb_images=nb, engine=engine)
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
            parler(f"Voilà, j'affiche {len(urls)} image{'s' if len(urls) > 1 else ''} de {query} sur votre interface, mylane.")
        else:
            parler(f"Désolé mylane, je n'ai pas trouvé d'images pour {query}.")
    elif action == "recherche_approfondie":
        query = data.get("query", "")
        parler(f"Je lance une recherche approfondie sur {query}, mylane. Cela peut prendre quelques secondes pendant que j'analyse les sources.")
        # Appel de l'agent autonome
        research_data = await shared.browser_agent.search_and_browse(query)
        if not research_data or "error" in research_data[0]:
            parler("Je suis désolé mylane, mais je n'ai pas pu accéder aux sites web pour le moment.")
        else:
            # On prépare un prompt pour que l'IA synthétise les résultats
            context = "\n\n".join([f"Source: {d['url']}\nContenu: {d['content']}" for d in research_data])
            prompt_synthese = (
                f"Voici les résultats de ma recherche approfondie sur '{query}' :\n\n"
                f"{context}\n\n"
                f"En tant que JARVIS, fais une synthèse élégante, précise et complète de ces informations pour mylane."
            )
            synthese = await demander_ia(prompt_synthese, update_hist=False, skip_local=True)
            if synthese:
                print("\n[BROWSER] --- SOURCES CONSULTÉES ---")
                for d in research_data:
                    print(f" > {d['url']}")
                print("[BROWSER] ---------------------------\n")
                parler(synthese)

    elif action == "web_agent_task":
        task_desc = data.get("task", "")
        if not task_desc:
            parler("Désolé mylane, je n'ai pas compris la tâche à effectuer.")
        else:
            result = await run_visual_agent(task_desc)
            parler(result)

    elif action == "fermer_navigateur_agent":
        result = await stop_visual_agent()
        parler(result)

    elif action == "sport_resultats":
        equipe = data.get("equipe") or None
        ligue  = data.get("ligue")  or None
        print(f"[SPORT] Action sport_resultats pour {equipe or ligue}")
        parler(f"Je cherche les informations pour {equipe or ligue}, un instant.")
        result = get_resultats_football(equipe=equipe, ligue=ligue)
        if "pas trouvé" in result or "Impossible" in result:
            print(f"[SPORT] Echec recherche locale. Verification avec Grok...")
            if shared.grok_client:
                res_grok = await demander_grok(f"mylane veut savoir : {texte_utilisateur}. Je n'ai pas trouvé l'info dans ma base de données football, peux-tu chercher pour lui ?")
                if res_grok: result = res_grok
        parler(result)
    elif action == "sport_classement":
        ligue  = data.get("ligue", "Ligue 1")
        parler(f"Je recupere le classement {ligue}.")
        result = get_classement_football(ligue=ligue)
        parler(result)
    elif action == "sport_live":
        question = data.get("question", "derniers resultats sportifs 2026")
        parler("Je recherche les derniers resultats en direct, un instant mylane.")
        result = await get_resultats_sport_gemini(question)
        parler(result)
    elif action == "voir_ecran":
        inst = data.get("instruction", "")
        res = await jarvis_vision_cliquer(inst)
        parler(res)
    elif action == "whatsapp_appel":
        contact = data.get("contact")
        if contact:
            await action_whatsapp_appel(contact)
            parler(f"Appel WhatsApp vers {contact} lancé.")
        else:
            parler("Désolé mylane, je n'ai pas trouvé le nom du contact à appeler.")
    elif action == "vision_ecrire":
        inst = data.get("instruction", "")
        txt  = data.get("texte", "")
        res  = await jarvis_vision_ecrire(inst, txt)
        parler(res)
    elif action == "vision_chercher_sur_site":
        txt = data.get("texte", "")
        parler(f"Je cherche la barre de recherche sur ce site, mylane.")
        res = await jarvis_vision_rechercher_sur_site(txt)
        parler(res)
    elif action == "lance_camera":
        res = await jarvis_vision_camera(texte_utilisateur)
        parler(res)
    elif action == "vision_navigateur":
        res = await jarvis_vision_navigateur(texte_utilisateur)
        parler(res)
    elif action == "analyse_live":
        question = data.get("question", "Analyse mon écran et aide-moi.")
        parler("Je jette un œil à votre écran, un instant mylane.")
        res = await jarvis_vision_analyse_live(question)
        parler(res)

    elif action == "dictee":
        texte = data.get("texte", "")
        if texte:
            import pyautogui
            import pyperclip
            pyperclip.copy(texte)
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'v')
            parler("C'est tapé, mylane.")

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
        parler("J'initialise le protocole d'analyse de sécurité de votre système, Mylane. Scan en cours.")
    elif action in ("spotify_ouvrir", "deezer_ouvrir"):
        parler("J'ouvre Deezer, mylane.")
        res = await deezer_ouvrir()
        parler(res)
    elif action in ("spotify_rechercher", "deezer_rechercher"):
        recherche = data.get("recherche", "")
        parler(f"Je recherche '{recherche}' sur Deezer, mylane.")
        res = await deezer_rechercher(recherche)
        parler(res)
    elif action in ("spotify_lecture_pause", "deezer_lecture_pause"):
        res = await deezer_lecture_pause()
        parler(res)
    elif action in ("spotify_stop", "deezer_stop"):
        res = await deezer_stop()
        parler(res)
    elif action in ("spotify_suivant", "deezer_suivant"):
        res = await deezer_suivant()
        parler(res)
    elif action in ("spotify_precedent", "deezer_precedent"):
        res = await deezer_precedent()
        parler(res)
    elif action in ("spotify_volume", "deezer_volume"):
        direction = data.get("direction", "monter")
        paliers   = data.get("paliers", 4)
        res = await deezer_volume(direction, paliers)
        parler(res)
    else:
        return False
    return True
