import os
import pickle
import webbrowser
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from core.interlocuteur import nom_virgule

try:
    import google.oauth2.credentials  # noqa: F401  (test de disponibilité)
    _google_apis_ok = True
except ImportError:
    _google_apis_ok = False

# Globaux persistants pour le doc en cours
dernier_doc_id      = None
dernier_doc_titre   = None
dernier_sheet_id    = None
dernier_sheet_titre = None
dernier_msg_id      = None
dernier_msg_sujet   = None


# SCOPES pour Google API (privilèges d'écriture et de gestion complets)
SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive',
    'https://mail.google.com/',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks'
]

def identifiants_google():
    if not _google_apis_ok:
        print("[GOOGLE] google-auth-oauthlib non installe — fonctions Google desactivees.")
        return None

    # Chemins absolus basés sur l'emplacement de la racine de JARVIS
    # backend/module/google_services.py → racine du projet = 3 niveaux au-dessus.
    # L'ancien calcul s'arrêtait à backend/, donc les identifiants étaient cherchés
    # dans backend/config/ (dossier vide) : TOUS les services Google (Gmail, Drive,
    # Agenda, Docs, Sheets) échouaient silencieusement avec « credentials introuvable ».
    _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    token_path       = os.path.join(_root, "config", "token.pickle")
    credentials_path = os.path.join(_root, "config", "credentials.json")
    os.makedirs(os.path.dirname(token_path), exist_ok=True)  # sinon l'écriture du token échoue

    creds = None
    if os.path.exists(token_path):
        with open(token_path, "rb") as f:
            creds = pickle.load(f)
    
    scopes_match = True
    if creds and hasattr(creds, "scopes"):
        scopes_match = all(s in creds.scopes for s in SCOPES)

    if not creds or not creds.valid or not scopes_match:
        if creds and creds.expired and creds.refresh_token and scopes_match:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"[GOOGLE] Erreur de rafraichissement du token : {e}. Lancement d'une nouvelle authentification...")
                if os.path.exists(token_path):
                    try:
                        os.remove(token_path)
                    except Exception as err:
                        print(f"[GOOGLE] Impossible de supprimer le token expire : {err}")
                if not os.path.exists(credentials_path):
                    print(f"[GOOGLE] credentials.json introuvable à : {credentials_path}")
                    return None
                flow  = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            if not os.path.exists(credentials_path):
                print(f"[GOOGLE] credentials.json introuvable à : {credentials_path}")
                return None
            flow  = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)
    return creds

def service_docs():
    creds = identifiants_google()
    return build("docs", "v1", credentials=creds) if creds else None

def service_drive():
    creds = identifiants_google()
    return build("drive", "v3", credentials=creds) if creds else None

def service_gmail():
    creds = identifiants_google()
    return build("gmail", "v1", credentials=creds) if creds else None

def service_sheets():
    creds = identifiants_google()
    return build("sheets", "v4", credentials=creds) if creds else None

def service_agenda():
    creds = identifiants_google()
    return build("calendar", "v3", credentials=creds) if creds else None

def _trouver_par_titre(elements, titre, cle):
    """Élément dont le titre correspond (exact d'abord, sinon inclusion), ou None.

    Avant, « titre contenu dans » sans garde-fou : un titre vide correspondait au premier
    élément de la liste (supprimé sans confirmation), un titre court au mauvais élément.
    """
    cherche = (titre or "").strip().lower()
    if not cherche:
        return None
    for e in elements:
        if (e.get(cle) or "").strip().lower() == cherche:
            return e
    if len(cherche) < 4:
        return None
    for e in elements:
        nom = (e.get(cle) or "").strip().lower()
        if nom and (cherche in nom or (len(nom) >= 4 and nom in cherche)):
            return e
    return None


_JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
         "septembre", "octobre", "novembre", "décembre"]


def _date_lisible(debut):
    """« 2026-10-08T14:00:00+02:00 » → « jeudi 8 octobre à 14 h » (lu par la synthèse vocale)."""
    from datetime import datetime as _dt
    try:
        if "T" in debut:
            d = _dt.fromisoformat(debut)
            heure = f"{d.hour} h" + (f" {d.minute:02d}" if d.minute else "")
            return f"{_JOURS[d.weekday()]} {d.day} {_MOIS[d.month - 1]} à {heure}"
        d = _dt.fromisoformat(debut)
        return f"{_JOURS[d.weekday()]} {d.day} {_MOIS[d.month - 1]}, toute la journée"
    except Exception:
        return debut


def nouveau_google_doc(titre="Nouveau Document", contenu=""):
    global dernier_doc_id, dernier_doc_titre
    try:
        service = service_docs()
        if not service:
            return "Google Docs non disponible."
        doc    = service.documents().create(body={"title": titre}).execute()
        doc_id = doc["documentId"]
        dernier_doc_id    = doc_id
        dernier_doc_titre = titre
        if contenu:
            requests_body = [{"insertText": {"location": {"index": 1}, "text": contenu}}]
            service.documents().batchUpdate(documentId=doc_id, body={"requests": requests_body}).execute()
        webbrowser.open(f"https://docs.google.com/document/d/{doc_id}/edit")
        return f"Document {titre} cree et ouvert{nom_virgule()}."
    except Exception as e:
        return f"Erreur Google Docs : {e}"

def editer_google_doc(contenu, doc_id=None):
    global dernier_doc_id
    try:
        service   = service_docs()
        if not service:
            return "Google Docs non disponible."
        target_id = doc_id or dernier_doc_id
        if not target_id:
            return "Aucun document n'est ouvert pour l'instant."
        doc       = service.documents().get(documentId=target_id).execute()
        end_index = doc["body"]["content"][-1]["endIndex"] - 1
        requests_body = [{"insertText": {"location": {"index": end_index}, "text": "\n" + contenu}}]
        service.documents().batchUpdate(documentId=target_id, body={"requests": requests_body}).execute()
        webbrowser.open(f"https://docs.google.com/document/d/{target_id}/edit")
        return f"Texte ajoute dans le document {dernier_doc_titre}."
    except Exception as e:
        return f"Erreur modification doc : {e}"

def consulter_emails(max_results=5):
    global dernier_msg_id, dernier_msg_sujet
    try:
        service  = service_gmail()
        if not service:
            return "Gmail non disponible."
        results  = service.users().messages().list(
            userId="me", 
            maxResults=max_results, 
            labelIds=["INBOX"], 
            q="is:unread category:primary"
        ).execute()
        messages = results.get("messages", [])
        if not messages:
            return "Aucun nouvel email non lu."
        reponse = ""
        msg_ids = []
        for idx, msg in enumerate(messages):
            m       = service.users().messages().get(userId="me", id=msg["id"], format="metadata").execute()
            headers = {h["name"]: h["value"] for h in m["payload"]["headers"]}
            from_val = headers.get('From', '?')
            subject_val = headers.get('Subject', '?')
            
            if idx == 0:
                dernier_msg_id = msg["id"]
                dernier_msg_sujet = subject_val
                
            reponse += f"De: {from_val} | Sujet: {subject_val}\n"
            msg_ids.append(msg["id"])
            
        # (Les messages ne sont plus marqués comme lus : seuls l'expéditeur et le sujet
        #  sont énoncés, le message n'a pas été lu.)
        return reponse.strip()
    except Exception as e:
        return f"Erreur Gmail : {e}"

def evenements_agenda():
    try:
        service = service_agenda()
        if not service:
            return "Google Agenda est indisponible."
        from datetime import datetime, timezone
        now    = datetime.now(timezone.utc).isoformat()
        events = service.events().list(calendarId="primary", timeMin=now, maxResults=5, singleEvents=True, orderBy="startTime").execute()
        items = events.get("items", [])
        if not items:
            return "Aucun evenement a venir."
        reponse = ""
        for e in items:
            start    = e["start"].get("dateTime", e["start"].get("date"))
            reponse += f"{_date_lisible(start)} : {e.get('summary', 'sans titre')}\n"
        return reponse.strip()
    except Exception as e:
        return f"Erreur Calendar : {e}"

def nouvelle_feuille_google(titre="Nouvelle Feuille"):
    global dernier_sheet_id, dernier_sheet_titre
    try:
        service  = service_sheets()
        if not service:
            return "Google Sheets non disponible."
        sheet    = service.spreadsheets().create(body={"properties": {"title": titre}}).execute()
        sheet_id = sheet["spreadsheetId"]
        dernier_sheet_id = sheet_id
        dernier_sheet_titre = titre
        webbrowser.open(f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
        return f"Feuille {titre} creee et ouverte."
    except Exception as e:
        return f"Erreur Google Sheets : {e}"

def get_tasks_service():
    creds = identifiants_google()
    return build("tasks", "v1", credentials=creds) if creds else None

def creer_google_task(titre, notes=None):
    try:
        service = get_tasks_service()
        if not service:
            return "Google Tasks non disponible."
        body = {'title': titre}
        if notes:
            body['notes'] = notes
        service.tasks().insert(tasklist='@default', body=body).execute()
        return f"Tâche '{titre}' ajoutée dans Google Tasks{nom_virgule()}."
    except Exception as e:
        return f"Erreur Google Tasks : {e}"

def lister_google_tasks():
    try:
        service = get_tasks_service()
        if not service:
            return "Google Tasks non disponible."
        results = service.tasks().list(tasklist='@default', showCompleted=False).execute()
        items = results.get('items', [])
        if not items:
            return "Aucune tâche à faire dans votre liste Google Tasks."
        
        reponse = ""
        for item in items:
            title = item.get('title', 'Sans titre')
            notes = item.get('notes')
            if notes:
                reponse += f"- {title} ({notes})\n"
            else:
                reponse += f"- {title}\n"
        return reponse.strip()
    except Exception as e:
        return f"Erreur de lecture Google Tasks : {e}"

def complete_google_task(titre):
    try:
        service = get_tasks_service()
        if not service:
            return "Google Tasks non disponible."
        
        results = service.tasks().list(tasklist='@default', showCompleted=False).execute()
        items = results.get('items', [])
        
        trouvee = _trouver_par_titre(items, titre, 'title')
        task_id = trouvee['id'] if trouvee else None
        exact_title = trouvee.get('title') if trouvee else None
        
        if not task_id:
            return f"Tâche '{titre}' introuvable dans votre Google Tasks{nom_virgule()}."
        
        task = service.tasks().get(tasklist='@default', task=task_id).execute()
        task['status'] = 'completed'
        service.tasks().update(tasklist='@default', task=task_id, body=task).execute()
        return f"Tâche '{exact_title}' validée dans Google Tasks{nom_virgule()}."
    except Exception as e:
        return f"Erreur lors de la validation de la tâche : {e}"

def delete_google_task(titre):
    try:
        service = get_tasks_service()
        if not service:
            return "Google Tasks non disponible."
        
        results = service.tasks().list(tasklist='@default', showCompleted=True).execute()
        items = results.get('items', [])
        
        trouvee = _trouver_par_titre(items, titre, 'title')
        task_id = trouvee['id'] if trouvee else None
        exact_title = trouvee.get('title') if trouvee else None
        
        if not task_id:
            return f"Tâche '{titre}' introuvable dans votre Google Tasks{nom_virgule()}."
        
        service.tasks().delete(tasklist='@default', task=task_id).execute()
        return f"Tâche '{exact_title}' supprimée de Google Tasks{nom_virgule()}."
    except Exception as e:
        return f"Erreur lors de la suppression de la tâche : {e}"

def ouvrir_google_drive():
    try:
        webbrowser.open("https://drive.google.com/")
        return f"J'ai ouvert votre Google Drive{nom_virgule()}."
    except Exception as e:
        return f"Erreur lors de l'ouverture du Google Drive : {e}"

def rechercher_google_drive(nom_fichier=None, max_results=5):
    try:
        service = service_drive()
        if not service:
            return "Google Drive non disponible."
        
        q = "trashed = false"
        
        # Liste de termes génériques à ne pas chercher littéralement
        generiques = ["mes documents", "mes fichiers", "mes docs", "documents", "fichiers", "drive", "mon drive", "tout", "tous"]
        
        if nom_fichier and nom_fichier.lower().strip() not in generiques:
            escaped_name = nom_fichier.replace("'", "\\'")
            q += f" and name contains '{escaped_name}'"
            
        results = service.files().list(
            q=q,
            pageSize=max_results,
            fields="files(id, name, webViewLink, modifiedTime)",
            orderBy="modifiedTime desc"
        ).execute()
        
        files = results.get("files", [])
        if not files:
            if nom_fichier and nom_fichier.lower().strip() not in generiques:
                return f"Aucun fichier trouvé sur votre Drive contenant '{nom_fichier}'."
            return "Aucun fichier trouvé sur votre Google Drive."
            
        reponse = ""
        for f in files:
            nom = f.get("name", "Sans titre")
            lien = f.get("webViewLink", "#")
            reponse += f"- {nom} : {lien}\n"
        return reponse.strip()
    except Exception as e:
        return f"Erreur de recherche Google Drive : {e}"

def expedier_email(destinataire, sujet, corps):
    import base64
    from email.mime.text import MIMEText
    try:
        service = service_gmail()
        if not service:
            return "Gmail non disponible."
        
        message = MIMEText(corps)
        message['to'] = destinataire
        message['subject'] = sujet
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        body = {'raw': raw_message}
        
        service.users().messages().send(userId="me", body=body).execute()
        return f"E-mail envoyé avec succès à {destinataire}{nom_virgule()}."
    except Exception as e:
        return f"Erreur lors de l'envoi de l'e-mail : {e}"

def repondre_au_mail(corps, original_msg_id=None):
    global dernier_msg_id, dernier_msg_sujet
    import base64
    from email.mime.text import MIMEText
    try:
        service = service_gmail()
        if not service:
            return "Gmail non disponible."
        
        msg_id = original_msg_id or dernier_msg_id
        if not msg_id:
            return f"Aucun e-mail récent à qui répondre en session{nom_virgule()}."
        
        orig_msg = service.users().messages().get(userId="me", id=msg_id, format="metadata").execute()
        thread_id = orig_msg.get('threadId')
        headers = {h["name"]: h["value"] for h in orig_msg["payload"]["headers"]}
        
        original_msg_id_header = headers.get('Message-ID')
        original_subject = headers.get('Subject', '')
        original_from = headers.get('From', '')
        
        sujet = original_subject
        if not sujet.lower().startswith('re:'):
            sujet = 'Re: ' + sujet
            
        message = MIMEText(corps)
        message['to'] = original_from
        message['subject'] = sujet
        
        if original_msg_id_header:
            message['In-Reply-To'] = original_msg_id_header
            message['References'] = original_msg_id_header
            
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        body = {'raw': raw_message, 'threadId': thread_id}
        
        service.users().messages().send(userId="me", body=body).execute()
        return f"Réponse envoyée avec succès à {original_from}{nom_virgule()}."
    except Exception as e:
        return f"Erreur lors de la réponse à l'e-mail : {e}"

def lire_detail_email(msg_id=None):
    global dernier_msg_id
    try:
        service = service_gmail()
        if not service:
            return "Gmail non disponible."
        
        target_id = msg_id or dernier_msg_id
        if not target_id:
            return f"Aucun e-mail trouvé en session{nom_virgule()}."
            
        msg = service.users().messages().get(userId="me", id=target_id).execute()
        payload = msg.get('payload', {})
        
        corps = ""
        
        def extraire_texte(partie):
            text = ""
            mime_type = partie.get('mimeType', '')
            body_data = partie.get('body', {}).get('data', '')
            if mime_type == 'text/plain' and body_data:
                import base64
                text += base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
            elif 'parts' in partie:
                for subpart in partie['parts']:
                    text += extraire_texte(subpart)
            return text
            
        corps = extraire_texte(payload)
        if not corps:
            body_data = payload.get('body', {}).get('data', '')
            if body_data:
                import base64
                corps = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
                
        if not corps:
            return "Impossible d'extraire le texte brut de cet e-mail."
            
        res_preview = corps.strip()
        if len(res_preview) > 800:
            res_preview = res_preview[:800] + "..."
        return res_preview
    except Exception as e:
        return f"Erreur de lecture détaillée de l'e-mail : {e}"

def archiver_email(msg_id=None):
    global dernier_msg_id
    try:
        service = service_gmail()
        if not service:
            return "Gmail non disponible."
        
        target_id = msg_id or dernier_msg_id
        if not target_id:
            return f"Aucun e-mail récent à archiver{nom_virgule()}."
            
        service.users().messages().batchModify(
            userId="me",
            body={"ids": [target_id], "removeLabelIds": ["INBOX"]}
        ).execute()
        return f"L'e-mail a été archivé avec succès{nom_virgule()}."
    except Exception as e:
        return f"Erreur lors de l'archivage de l'e-mail : {e}"

def effacer_email(msg_id=None):
    global dernier_msg_id
    try:
        service = service_gmail()
        if not service:
            return "Gmail non disponible."
        
        target_id = msg_id or dernier_msg_id
        if not target_id:
            return f"Aucun e-mail récent à supprimer{nom_virgule()}."
            
        service.users().messages().trash(userId="me", id=target_id).execute()
        return f"L'e-mail a été déplacé dans la corbeille avec succès{nom_virgule()}."
    except Exception as e:
        return f"Erreur lors de la suppression de l'e-mail : {e}"

def creer_evenement_calendar(summary, start_time, end_time, description=None):
    try:
        service = service_agenda()
        if not service:
            return "Google Agenda est indisponible."
        
        event = {
            'summary': summary,
            'start': {
                'dateTime': start_time,
                'timeZone': 'Europe/Paris',
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'Europe/Paris',
            }
        }
        if description:
            event['description'] = description
            
        service.events().insert(calendarId="primary", body=event).execute()
        return f"Événement '{summary}' créé avec succès dans votre agenda{nom_virgule()}."
    except Exception as e:
        return f"Erreur de création de l'événement Calendar : {e}"

def modifier_evenement_calendar(ancien_titre, nouveau_titre=None, nouvelle_heure=None, fin_heure=None):
    try:
        service = service_agenda()
        if not service:
            return "Google Agenda est indisponible."
        
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        events = service.events().list(calendarId="primary", timeMin=now, maxResults=20, singleEvents=True, orderBy="startTime").execute()
        items = events.get("items", [])
        
        event_id = None
        exact_summary = None
        event_data = None
        cible = _trouver_par_titre(items, ancien_titre, "summary")
        for e in ([cible] if cible else []):
                event_id = e["id"]
                exact_summary = e.get("summary")
                event_data = e
                break
                
        if not event_id:
            return f"Événement '{ancien_titre}' introuvable dans votre agenda{nom_virgule()}."
            
        if nouveau_titre:
            event_data['summary'] = nouveau_titre
        if nouvelle_heure:
            event_data['start']['dateTime'] = nouvelle_heure
            if fin_heure:
                event_data['end']['dateTime'] = fin_heure
            else:
                try:
                    from datetime import datetime, timedelta
                    clean_time = nouvelle_heure.replace('Z', '+00:00')
                    dt = datetime.fromisoformat(clean_time)
                    event_data['end']['dateTime'] = (dt + timedelta(hours=1)).isoformat()
                except:
                    event_data['end']['dateTime'] = nouvelle_heure
            
        service.events().update(calendarId="primary", event=event_id, body=event_data).execute()
        return f"Événement '{exact_summary}' modifié avec succès dans votre agenda{nom_virgule()}."
    except Exception as e:
        return f"Erreur lors de la modification de l'événement : {e}"

def supprimer_evenement_calendar(titre):
    try:
        service = service_agenda()
        if not service:
            return "Google Agenda est indisponible."
        
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        events = service.events().list(calendarId="primary", timeMin=now, maxResults=20, singleEvents=True, orderBy="startTime").execute()
        items = events.get("items", [])
        
        event_id = None
        exact_summary = None
        cible = _trouver_par_titre(items, titre, "summary")
        for e in ([cible] if cible else []):
                event_id = e["id"]
                exact_summary = e.get("summary")
                break
                
        if not event_id:
            return f"Événement '{titre}' introuvable dans votre agenda{nom_virgule()}."
            
        service.events().delete(calendarId="primary", event=event_id).execute()
        return f"Événement '{exact_summary}' supprimé de votre agenda avec succès{nom_virgule()}."
    except Exception as e:
        return f"Erreur lors de la suppression de l'événement : {e}"

def ajouter_ligne_sheet(valeurs, spreadsheet_id=None, onglet="Feuille 1"):
    global dernier_sheet_id
    try:
        service = service_sheets()
        if not service:
            return "Google Sheets non disponible."
        
        target_id = spreadsheet_id or dernier_sheet_id
        if not target_id:
            return f"Aucune feuille de calcul active en session{nom_virgule()}."
            
        if not isinstance(valeurs, list):
            valeurs = [valeurs]
            
        range_name = f"{onglet}!A:Z"
        body = {
            'values': [valeurs]
        }
        service.spreadsheets().values().append(
            spreadsheetId=target_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()
        
        return f"Données insérées avec succès dans la feuille{nom_virgule()}."
    except Exception as e:
        return f"Erreur lors de l'écriture dans Google Sheets : {e}"

def lire_donnees_sheet(cell_range, spreadsheet_id=None):
    global dernier_sheet_id
    try:
        service = service_sheets()
        if not service:
            return "Google Sheets non disponible."
        
        target_id = spreadsheet_id or dernier_sheet_id
        if not target_id:
            return f"Aucune feuille de calcul active en session{nom_virgule()}."
            
        result = service.spreadsheets().values().get(
            spreadsheetId=target_id,
            range=cell_range
        ).execute()
        
        values = result.get('values', [])
        if not values:
            return "Aucune donnée trouvée dans cette plage."
            
        reponse = ""
        for row in values:
            reponse += " | ".join(row) + "\n"
        return reponse.strip()
    except Exception as e:
        return f"Erreur de lecture Google Sheets : {e}"

def lire_contenu_doc(doc_id=None):
    global dernier_doc_id
    try:
        service = service_docs()
        if not service:
            return "Google Docs non disponible."
        
        target_id = doc_id or dernier_doc_id
        if not target_id:
            return f"Aucun document actif en session{nom_virgule()}."
            
        doc = service.documents().get(documentId=target_id).execute()
        
        contenu = doc.get('body', {}).get('content', [])
        texte = ""
        for item in contenu:
            if 'paragraph' in item:
                for element in item['paragraph'].get('elements', []):
                    if 'textRun' in element:
                        texte += element['textRun'].get('content', '')
                        
        if not texte.strip():
            return "Le document est vide."
            
        res_preview = texte.strip()
        if len(res_preview) > 1000:
            res_preview = res_preview[:1000] + "..."
        return res_preview
    except Exception as e:
        return f"Erreur lors de la lecture du document : {e}"

def charger_fichier_drive(local_path, parent_folder_id=None):
    try:
        service = service_drive()
        if not service:
            return "Google Drive non disponible."
        
        import os
        if not os.path.exists(local_path):
            return f"Fichier local introuvable au chemin : {local_path}"
            
        filename = os.path.basename(local_path)
        
        import mimetypes
        mime_type, _ = mimetypes.guess_type(local_path)
        if not mime_type:
            mime_type = 'application/octet-stream'
            
        from googleapiclient.http import MediaFileUpload
        file_metadata = {'name': filename}
        if parent_folder_id:
            file_metadata['parents'] = [parent_folder_id]
            
        media = MediaFileUpload(local_path, mimetype=mime_type, resumable=True)
        file_uploaded = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        
        lien = file_uploaded.get('webViewLink')
        return f"Fichier '{filename}' téléversé avec succès. Lien : {lien}"
    except Exception as e:
        return f"Erreur de téléversement Drive : {e}"

def partager_fichier_drive(email, role="reader", file_id=None):
    global dernier_doc_id
    try:
        service = service_drive()
        if not service:
            return "Google Drive non disponible."
        
        target_id = file_id or dernier_doc_id
        if not target_id:
            return f"Aucun document actif en session à partager{nom_virgule()}."
            
        permission = {
            'type': 'user',
            'role': role,
            'emailAddress': email
        }
        service.permissions().create(fileId=target_id, body=permission).execute()
        return f"Le document a été partagé avec succès avec {email} en tant que {role}{nom_virgule()}."
    except Exception as e:
        return f"Erreur de partage du fichier : {e}"

def creer_dossier_drive(nom_dossier, parent_folder_id=None):
    try:
        service = service_drive()
        if not service:
            return "Google Drive non disponible."
        
        file_metadata = {
            'name': nom_dossier,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_folder_id:
            file_metadata['parents'] = [parent_folder_id]
            
        folder = service.files().create(body=file_metadata, fields='id, webViewLink').execute()
        lien = folder.get('webViewLink')
        return f"Dossier '{nom_dossier}' créé avec succès. Lien : {lien}"
    except Exception as e:
        return f"Erreur lors de la création du dossier Drive : {e}"




