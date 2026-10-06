import os
from PIL import Image
import base64
import time
import builtins
try:
    import pyautogui
except ImportError:
    pyautogui = None
try:
    import cv2
except ImportError:
    cv2 = None
import asyncio
import json
try:
    import requests
except ImportError:
    requests = None
from dotenv import load_dotenv
from core.interlocuteur import nom_espace, nom_ou_utilisateur, nom_virgule

# --- IDE HELPERS ---
try:
    client = builtins.client
    CHOSEN_MODEL = builtins.CHOSEN_MODEL
    parler = builtins.parler
    demander_ia_vision = builtins.demander_ia_vision
    CONNECTED_CLIENTS = builtins.CONNECTED_CLIENTS
    request_screen_capture = builtins.request_screen_capture
except AttributeError:
    # Ce module est importé AVANT que main.py n'ait injecté ses builtins : le
    # bloc ci-dessus échoue donc systématiquement au démarrage normal.
    # `parler` n'était pas réassigné ici, donc le nom restait indéfini et
    # jarvis_vision_camera() levait un NameError, présenté à l'utilisateur
    # comme « une erreur technique ». On résout maintenant à l'APPEL.
    client = CHOSEN_MODEL = demander_ia_vision = CONNECTED_CLIENTS = request_screen_capture = None

    def parler(*args, **kwargs):
        _f = getattr(builtins, "parler", None)
        if _f:
            return _f(*args, **kwargs)
        print("[VISION]", *args)

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

async def jarvis_vision_cliquer(instruction):
    if not client:
        return f"Désolé{nom_espace()}, le client Gemini Vision n'est pas initialisé ou est inactif pour le moment."
    try:
        # On attend un peu que l'UI soit stable
        time.sleep(0.5)
        path_ss = "jarvis_vision_temp.png"
        screenshot = pyautogui.screenshot()
        screenshot.save(path_ss)
        img_w, img_h = screenshot.size  # Dimensions réelles de la capture d'écran
        img = Image.open(path_ss)
        prompt_vision = (
            f"Tu es l'oeil de JARVIS. Voici une capture de l'écran de {nom_ou_utilisateur()} ({img_w}x{img_h} pixels).\n"
            f"Instruction : {instruction}\n"
            "Trouve l'élément demandé (bouton, texte, icône ou numéro dans une liste) sur l'écran.\n"
            "Si l'instruction mentionne un chiffre (ex: 'musique numéro 4'), cherche ce chiffre ou le morceau correspondant dans la liste.\n"
            "Réponds UNIQUEMENT en JSON avec ce format :\n"
            "{\"box\": [ymin, xmin, ymax, xmax], \"description\": \"description courte de l'élément\"}\n"
            "Les coordonnées sont normalisées de 0 à 1000 (0=coin haut-gauche, 1000=coin bas-droit)."
        )
        response = client.models.generate_content(model=CHOSEN_MODEL, contents=[prompt_vision, img])
        rep_text = response.text.strip()
        print(f"[VISION] Gemini a renvoyé : {rep_text}")
        start = rep_text.find('{')
        end = rep_text.rfind('}')
        if start != -1 and end != -1:
            rep_text = rep_text[start:end+1]
        data = json.loads(rep_text)

        box = data.get("box", [500, 500, 500, 500])
        ymin, xmin, ymax, xmax = box

        # Centre de la bounding box, converti en pixels réels via les dimensions de la capture
        center_y = (ymin + ymax) / 2
        center_x = (xmin + xmax) / 2
        target_x = int((center_x / 1000) * img_w)
        target_y = int((center_y / 1000) * img_h)

        print(f"[VISION] Cible identifiée : {data.get('description', 'inconnu')} à ({target_x}, {target_y})")

        pyautogui.moveTo(target_x, target_y, duration=0.5)
        time.sleep(0.2)

        # DOUBLE-CLIC si c'est une musique ou un chiffre pour être sûr de lancer la lecture
        t_inst = instruction.lower()
        if any(keyword in t_inst for keyword in ["musique", "chanson", "piste", "numéro", "numero", "titre"]):
            print(f"[VISION] Double-clic sur l'élément de liste : {target_x}, {target_y}")
            pyautogui.doubleClick()
        else:
            pyautogui.click()

        if os.path.exists(path_ss):
            os.remove(path_ss)
        desc = data.get("description", instruction)
        return f"C'est fait{nom_espace()}, j'ai cliqué sur : {desc}."
    except Exception as e:
        print(f"[VISION ERROR] {e}")
        return f"Je vois l'interface, mais je n'ai pas réussi à identifier l'élément précis{nom_virgule()}."


async def jarvis_vision_ecrire(instruction, texte_a_taper):
    if not client:
        return f"Désolé{nom_espace()}, le client Gemini Vision n'est pas initialisé ou est inactif pour le moment."
    try:
        import pyperclip
        path_ss = "jarvis_vision_temp.png"
        screenshot = pyautogui.screenshot()
        screenshot.save(path_ss)
        img_w, img_h = screenshot.size
        img = Image.open(path_ss)
        prompt_vision = (
            f"Tu es la vision de JARVIS. {nom_ou_utilisateur()} veut écrire dans le champ : {instruction}.\n"
            f"Résolution de la capture : {img_w}x{img_h} pixels.\n"
            "Trouve EXACTEMENT la position de ce champ de saisie de texte.\n"
            "Les coordonnées sont normalisées de 0 à 1000.\n"
            "Réponds UNIQUEMENT en JSON :\n"
            "{\"box\": [ymin, xmin, ymax, xmax], \"description\": \"description du champ\"}\n"
            "Exemple : {\"box\": [250, 480, 290, 520], \"description\": \"champ de recherche Google\"}"
        )
        response = client.models.generate_content(model=CHOSEN_MODEL, contents=[prompt_vision, img])
        rep_text = response.text.strip()
        start = rep_text.find('{')
        end = rep_text.rfind('}')
        if start != -1 and end != -1:
            rep_text = rep_text[start:end+1]
        data = json.loads(rep_text)

        box = data.get("box", [500, 500, 500, 500])
        ymin, xmin, ymax, xmax = box

        center_y = (ymin + ymax) / 2
        center_x = (xmin + xmax) / 2
        target_x = int((center_x / 1000) * img_w)
        target_y = int((center_y / 1000) * img_h)

        pyautogui.moveTo(target_x, target_y, duration=0.5)
        time.sleep(0.15)
        pyautogui.click()
        time.sleep(0.3)
        pyautogui.hotkey('ctrl', 'a')  # Effacer le contenu existant
        time.sleep(0.1)
        # Coller via presse-papiers pour supporter les accents et caractères spéciaux
        pyperclip.copy(texte_a_taper)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.1)
        pyautogui.press('enter')

        if os.path.exists(path_ss):
            os.remove(path_ss)
        return f"C'est fait{nom_espace()}. J'ai saisi '{texte_a_taper}' dans {instruction}."
    except Exception as e:
        print(f"[VISION ERROR] {e}")
        return f"J'ai eu un petit souci technique pour taper le texte{nom_virgule()}."


async def jarvis_vision_rechercher_sur_site(texte_recherche):
    """Trouve la barre de recherche sur la page actuelle et tape la requête."""
    if not client:
        return f"Désolé{nom_espace()}, le client Gemini Vision n'est pas initialisé ou est inactif pour le moment."
    try:
        import pyperclip
        path_ss = "jarvis_vision_temp.png"
        screenshot = pyautogui.screenshot()
        screenshot.save(path_ss)
        img_w, img_h = screenshot.size
        img = Image.open(path_ss)
        prompt_vision = (
            f"Tu es la vision de JARVIS. {nom_ou_utilisateur()} veut faire une recherche sur le site affiché à l'écran.\n"
            f"Résolution de la capture : {img_w}x{img_h} pixels.\n"
            "Localise la BARRE DE RECHERCHE principale du site (champ search, zone avec icône loupe, "
            "placeholder 'Rechercher', 'Search', 'Chercher'...).\n"
            "Si tu vois une barre d'adresse de navigateur ET une barre de recherche du site, "
            "préfère la barre de recherche du site.\n"
            "Les coordonnées sont normalisées de 0 à 1000 (0=haut-gauche, 1000=bas-droite).\n"
            "Réponds UNIQUEMENT en JSON :\n"
            "{\"box\": [ymin, xmin, ymax, xmax], \"description\": \"description de la barre trouvée\"}\n"
            "Exemple : {\"box\": [48, 220, 78, 820], \"description\": \"barre de recherche YouTube\"}"
        )
        response = client.models.generate_content(model=CHOSEN_MODEL, contents=[prompt_vision, img])
        rep_text = response.text.strip()
        start = rep_text.find('{')
        end = rep_text.rfind('}')
        if start != -1 and end != -1:
            rep_text = rep_text[start:end+1]
        data = json.loads(rep_text)

        box = data.get("box", [500, 500, 500, 500])
        ymin, xmin, ymax, xmax = box

        center_y = (ymin + ymax) / 2
        center_x = (xmin + xmax) / 2
        target_x = int((center_x / 1000) * img_w)
        target_y = int((center_y / 1000) * img_h)

        pyautogui.moveTo(target_x, target_y, duration=0.5)
        time.sleep(0.15)
        pyautogui.click()
        time.sleep(0.35)
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        pyperclip.copy(texte_recherche)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.15)
        pyautogui.press('enter')

        if os.path.exists(path_ss):
            os.remove(path_ss)
        desc = data.get("description", "barre de recherche")
        return f"C'est fait{nom_espace()} ! J'ai tapé '{texte_recherche}' dans la {desc} et j'ai validé."
    except Exception as e:
        print(f"[VISION ERROR] {e}")
        return f"Je n'ai pas réussi à trouver la barre de recherche sur ce site{nom_virgule()}."


async def jarvis_vision_camera(question_utilisateur=None):
    """Capture une image depuis la caméra et l'analyse avec Gemini Vision."""
    if cv2 is None:
        return f"Désolé{nom_espace()}, le module de vision par caméra (OpenCV) n'est pas installé."

    cap = None
    try:
        # Tenter plusieurs index
        for idx in [0, 1]:
            print(f"[CAMERA] Tentative d'ouverture sur l'index {idx}...")
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if cap and cap.isOpened():
                break
            cap.release()

        if not cap or not cap.isOpened():
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return f"Désolé{nom_espace()}, je n'arrive pas à accéder à votre caméra. Vérifiez qu'elle n'est pas utilisée ailleurs."

        # Configurer la résolution
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        # Ajustement asynchrone (évite le freeze de l'UI)
        print("[CAMERA] Ajustement automatique de l'image (2s)...")
        start_time = time.time()
        while time.time() - start_time < 2.0:
            cap.read()
            await asyncio.sleep(0.1)

        ret, frame = cap.read()
        if not ret or frame is None:
            return f"Désolé{nom_espace()}, la capture a échoué."

        path_cam = "jarvis_camera_temp.jpg"
        cv2.imwrite(path_cam, frame)

        with open(path_cam, "rb") as f:
            img_bytes = f.read()
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')

        if os.path.exists(path_cam):
            os.remove(path_cam)

        prompt_cam = f"{nom_ou_utilisateur()} te montre une image via sa caméra. Sa demande : '{question_utilisateur or 'Décris ce que tu vois'}'. Analyse l'image et réponds précisément."

        parler(f"C'est fait{nom_espace()}, je regarde ce que votre caméra voit...")

        return await demander_ia_vision(prompt_cam, img_b64)

    except Exception as e:
        print(f"[CAMERA ERROR] {e}")
        return f"Désolé{nom_espace()}, une erreur technique est survenue : {e}"
    finally:
        if cap:
            cap.release()
            print("[CAMERA] Ressource libérée.")


async def jarvis_vision_navigateur(question_utilisateur=None):
    """Capture une image depuis le navigateur via WebSocket et l'analyse avec Gemini Vision."""
    try:
        if not CONNECTED_CLIENTS:
            return f"Désolé{nom_espace()}, l'interface web (navigateur) n'est pas connectée actuellement."

        parler(f"J'active la vision du navigateur, un instant{nom_espace()}...")

        img_b64 = await request_screen_capture()

        if not img_b64:
            return f"Désolé{nom_espace()}, le flux vidéo est inactif. Pensez bien à cliquer sur le bouton 'Activer la vision' en haut à droite de l'interface web."

        if question_utilisateur:
            prompt_vision = f"{nom_ou_utilisateur()} te montre son navigateur/écran. Sa demande : '{question_utilisateur}'. Analyse l'image et réponds précisément."
        else:
            prompt_vision = f"Analyse cette capture du navigateur/écran de {nom_ou_utilisateur()} et décris-lui ce que tu vois en détail."

        reponse = await demander_ia_vision(prompt_vision, img_b64)
        return reponse

    except Exception as e:
        print(f"[VISION NAVIGATEUR ERROR] {e}")
        return f"Désolé{nom_espace()}, une erreur est survenue lors de l'accès à la vision du navigateur : {e}"


async def jarvis_vision_analyse_live(question_utilisateur):
    """Analyse l'écran actuel pour aider l'utilisateur ou répondre à une question contextuelle."""
    try:
        # `main2` n'existe plus (l'orchestrateur s'appelle main.py) : cet import
        # levait un ModuleNotFoundError avalé plus bas, si bien que l'action
        # « analyse_live » répondait toujours « j'ai une difficulté technique ».
        # On récupère le client via builtins, comme le reste du module.
        client = getattr(builtins, "client", None)
        CHOSEN_MODEL = getattr(builtins, "CHOSEN_MODEL", None)
        if client is None:
            return f"Ma vision nécessite une clé Gemini valide{nom_virgule()}."
        path_ss = "jarvis_vision_live.png"
        screenshot = pyautogui.screenshot()
        screenshot.save(path_ss)
        img = Image.open(path_ss)

        prompt_vision = (
            f"Tu es JARVIS, l'assistant personnel de Neyor. Tu vois actuellement l'écran de {nom_ou_utilisateur()}.\n"
            f"Question de {nom_ou_utilisateur()} : {question_utilisateur}\n\n"
            "Analyse l'image pour comprendre le contexte (quelle application est ouverte, quel texte est affiché, quel est le problème éventuel).\n"
            f"Réponds avec précision, élégance et empathie. Si {nom_ou_utilisateur()} semble bloqué, propose une solution concrète."
        )

        response = await client.aio.models.generate_content(model=CHOSEN_MODEL, contents=[prompt_vision, img])

        if os.path.exists(path_ss):
            os.remove(path_ss)

        return response.text
    except Exception as e:
        print(f"[VISION ERROR] Analyse live failed : {e}")
        return f"Je vois votre écran{nom_espace()}, mais j'ai une difficulté technique pour l'analyser en profondeur."
