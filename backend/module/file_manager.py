import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
try:
    import pyautogui
except ImportError:
    pyautogui = None
import ctypes
import time
from core.interlocuteur import nom_virgule
try:
    import pypdf
except ImportError:
    pypdf = None  # type: ignore
try:
    import docx
except ImportError:
    docx = None  # type: ignore

user32 = ctypes.windll.user32

dossier_courant = None

EXTENSIONS = {
    "Images"   : [".jpg", ".jpeg", ".png", ".gif", ".bmp",
                  ".tiff", ".tif", ".webp", ".svg", ".ico",
                  ".heic", ".raw", ".cr2", ".nef"],
    "Videos"   : [".mp4", ".avi", ".mkv", ".mov", ".wmv",
                  ".flv", ".webm", ".m4v", ".mpg", ".mpeg",
                  ".3gp", ".ts"],
    "Musique"  : [".mp3", ".wav", ".flac", ".aac", ".ogg",
                  ".wma", ".m4a", ".opus", ".aiff"],
    "Documents": [".pdf", ".doc", ".docx", ".xls", ".xlsx",
                  ".ppt", ".pptx", ".txt", ".odt", ".ods",
                  ".odp", ".rtf", ".csv", ".epub"],
    "Archives" : [".zip", ".rar", ".7z", ".tar", ".gz",
                  ".bz2", ".xz", ".iso"],
    "Code"     : [".py", ".js", ".html", ".css", ".java",
                  ".cpp", ".c", ".h", ".cs", ".php",
                  ".json", ".xml", ".yaml", ".yml",
                  ".sh", ".bat", ".ps1", ".ts", ".jsx",
                  ".tsx", ".vue", ".go", ".rs", ".rb"],
    "Executables": [".exe", ".msi", ".apk", ".dmg", ".deb"],
}

def interpreter_chemin(chemin):
    if not chemin:
        return None
    chemin = chemin.strip().strip('"').strip("'")
    # Dossiers personnels : emplacement réel donné par Windows (souvent sous OneDrive) ;
    # avant, USERPROFILE\Desktop, \Documents… écrits en dur visaient d'autres dossiers.
    from core.dossiers import dossier_connu
    if chemin.lower() == "corbeille":
        return "shell:RecycleBinFolder"
    chemin_resolu = dossier_connu(chemin) or chemin
    return chemin_resolu

def deduire_extension(ext):
    for categorie, extensions in EXTENSIONS.items():
        if ext.lower() in extensions:
            return categorie
    return "Autres"

def afficher_dossier(chemin):
    global dossier_courant
    chemin_resolu = interpreter_chemin(chemin)
    if not chemin_resolu or (not os.path.exists(chemin_resolu) and not chemin_resolu.startswith("shell:")):
        return False, f"Dossier introuvable : {chemin_resolu}"
    dossier_courant = chemin_resolu
    # Utilisation de Popen pour ne pas bloquer
    subprocess.Popen(['explorer', chemin_resolu])   # sans shell : « shell:… » est compris par explorer lui-même
    return True, chemin_resolu

def disposer_fenetres_dossiers():
    """Affiche en mosaïque les dossiers Documents, Téléchargements, Images et Vidéos."""
    dossiers = [
        ("document", 0, 0),             # Haut Gauche
        ("téléchargement", 1, 0),       # Haut Droite
        ("image", 0, 1),               # Bas Gauche
        ("vidéo", 1, 1)                # Bas Droite
    ]
    
    sw, sh = pyautogui.size()
    w, h = sw // 2, (sh - 40) // 2  # -40 pour la barre des tâches approximative
    
    for nom, qx, qy in dossiers:
        afficher_dossier(nom)
        time.sleep(0.8) # Laisser le temps à Explorer de s'ouvrir
        
        # On tente de trouver la fenêtre active qui vient d'être ouverte
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            x = qx * w
            y = qy * h
            # SWP_SHOWWINDOW = 0x0040
            user32.SetWindowPos(hwnd, 0, x, y, w, h, 0x0040)
    
    return f"J'ai ouvert et disposé vos dossiers principaux en mosaïque{nom_virgule()}."

def enumerer_dossier(chemin=None):
    cible = interpreter_chemin(chemin) or dossier_courant
    if not cible or not os.path.exists(cible):
        return None, "Aucun dossier ouvert ou chemin invalide."
    fichiers  = []
    dossiers  = []
    for item in os.scandir(cible):
        if item.is_file():
            fichiers.append(item.name)
        elif item.is_dir():
            dossiers.append(item.name)
    return {"chemin": cible, "fichiers": fichiers, "dossiers": dossiers}, None

def _tri_interdit(cible):
    """Raison pour laquelle on ne trie JAMAIS ce dossier (système, programmes, racine de disque, profil), ou None. Le dossier à trier vient de l'IA :
    {"chemin": "C:\\Windows"} rangeait les fichiers de Windows dans des sous-dossiers « Images », « Documents »…"""
    p = os.path.normcase(os.path.abspath(cible))
    if os.path.dirname(p) == p:
        return "la racine d'un disque"
    for nom in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData", "APPDATA", "LOCALAPPDATA"):
        d = os.environ.get(nom)
        if d:
            d = os.path.normcase(os.path.abspath(d))
            if p == d or p.startswith(d + os.sep):
                return "un dossier système ou de programmes"
    profil = os.environ.get("USERPROFILE")
    if profil and p == os.path.normcase(os.path.abspath(profil)):
        return "le dossier du profil utilisateur"
    return None


def apercu_tri(chemin=None):
    """(dossier, nombre de fichiers du niveau supérieur) que le tri déplacerait ; (None, 0) si invalide ou interdit."""
    cible = interpreter_chemin(chemin) or dossier_courant
    if not cible or not os.path.isdir(cible) or _tri_interdit(cible):
        return None, 0
    try:
        return cible, sum(1 for e in os.scandir(cible) if e.is_file())
    except OSError:
        return None, 0


def classer_par_type(chemin=None):
    cible = interpreter_chemin(chemin) or dossier_courant
    if not cible or not os.path.exists(cible):
        return False, "Aucun dossier ouvert ou invalide."
    raison = _tri_interdit(cible)
    if raison:
        return False, f"Je ne trie pas {raison}."
    deplacements = 0
    erreurs      = 0
    categories   = {}
    for item in os.scandir(cible):
        if not item.is_file():
            continue
        ext       = Path(item.name).suffix
        categorie = deduire_extension(ext)
        dest_dir  = os.path.join(cible, categorie)
        try:
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, item.name)
            if os.path.exists(dest_path):
                base  = Path(item.name).stem
                ext2  = Path(item.name).suffix
                dest_path = os.path.join(dest_dir, f"{base}_{int(time.time())}{ext2}")
            shutil.move(item.path, dest_path)
            deplacements += 1
            categories[categorie] = categories.get(categorie, 0) + 1
        except Exception as e:
            print(f"[FICHIER] Erreur deplacement {item.name} : {e}")
            erreurs += 1
    resume = ", ".join([f"{v} {k}" for k, v in categories.items()])
    return True, f"{deplacements} fichiers tries : {resume}. {erreurs} erreurs."

def classer_par_date(chemin=None):
    cible = interpreter_chemin(chemin) or dossier_courant
    if not cible or not os.path.exists(cible):
        return False, "Aucun dossier ouvert ou invalide."
    raison = _tri_interdit(cible)
    if raison:
        return False, f"Je ne trie pas {raison}."
    deplacements = 0
    erreurs      = 0
    for item in os.scandir(cible):
        if not item.is_file():
            continue
        try:
            mtime     = item.stat().st_mtime
            date      = datetime.fromtimestamp(mtime)
            annee     = str(date.year)
            mois      = date.strftime("%m - %B")
            dest_dir  = os.path.join(cible, annee, mois)
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, item.name)
            if os.path.exists(dest_path):
                base      = Path(item.name).stem
                ext2      = Path(item.name).suffix
                dest_path = os.path.join(dest_dir, f"{base}_{int(time.time())}{ext2}")
            shutil.move(item.path, dest_path)
            deplacements += 1
        except Exception as e:
            print(f"[FICHIER] Erreur deplacement {item.name} : {e}")
            erreurs += 1
    return True, f"{deplacements} fichiers tries par date. {erreurs} erreurs."

def classer_par_type_et_date(chemin=None):
    cible = interpreter_chemin(chemin) or dossier_courant
    if not cible or not os.path.exists(cible):
        return False, "Aucun dossier ouvert."
    ok1, msg1 = classer_par_type(cible)
    if not ok1:
        return False, msg1
    for item in os.scandir(cible):
        if item.is_dir() and item.name in EXTENSIONS.keys():
            classer_par_date(item.path)
    return True, "Dossier trie par type puis par date dans chaque categorie."

def creer_dossier_enfant(nom, chemin=None):
    cible = interpreter_chemin(chemin) or dossier_courant
    if not cible:
        return False, "Aucun dossier ouvert."
    nouveau = os.path.join(cible, nom)
    if not _dans_le_dossier(cible, nouveau):
        return False, "Le nom sort du dossier ouvert : refusé."
    try:
        os.makedirs(nouveau, exist_ok=True)
        return True, f"Dossier {nom} cree."
    except Exception as e:
        return False, f"Erreur creation dossier : {e}"

def changer_nom_fichier(ancien_nom, nouveau_nom, chemin=None):
    cible = interpreter_chemin(chemin) or dossier_courant
    if not cible:
        return False, "Aucun dossier ouvert."
    ancien = os.path.join(cible, ancien_nom)
    nouveau = os.path.join(cible, nouveau_nom)
    if not _dans_le_dossier(cible, ancien, nouveau):   # le nom vient de l'IA : « ..\\x » ou un chemin absolu déplaçait / renommait hors du dossier ouvert
        return False, "Le nom sort du dossier ouvert : refusé."
    if os.path.exists(nouveau):
        return False, "Un fichier porte déjà ce nom : je n'écrase rien."
    try:
        os.rename(ancien, nouveau)
        return True, f"Fichier renomme en {nouveau_nom}."
    except Exception as e:
        return False, f"Erreur renommage : {e}"

def transferer_fichier(nom_fichier, dossier_dest, chemin=None):
    cible = interpreter_chemin(chemin) or dossier_courant
    if not cible:
        return False, "Aucun dossier ouvert."
    source = os.path.join(cible, nom_fichier)
    dest   = os.path.join(cible, dossier_dest, nom_fichier)
    # Tout reste DANS le dossier ouvert : un chemin absolu ou « .. » (venu de l'IA) sortait de `cible`, et shutil.move écrasait en silence un fichier de même nom (copie par-dessus sous Windows).
    racine = os.path.realpath(cible)
    try:
        dedans = all(os.path.commonpath([racine, os.path.realpath(p)]) == racine for p in (source, dest))
    except ValueError:   # autre lecteur (D: contre C:)
        dedans = False
    if not dedans:
        return False, f"{dossier_dest} est en dehors du dossier ouvert."
    if os.path.exists(dest):
        return False, f"{nom_fichier} existe déjà dans {dossier_dest} : je n'écrase rien."
    try:
        os.makedirs(os.path.join(cible, dossier_dest), exist_ok=True)
        shutil.move(source, dest)
        return True, f"{nom_fichier} deplace dans {dossier_dest}."
    except Exception as e:
        return False, f"Erreur deplacement : {e}"

_DOSSIERS_IGNORES = {"appdata", "windows", "programdata", "program data", "$recycle.bin", "windowsapps", "windows.old", "system volume information"}


def rechercher_fichier(nom, scan_global=True, type_cible=None, delai=20.0):
    """
    Cherche un fichier ou un dossier par son nom.
    Si scan_global est True, cherche dans tous les dossiers utilisateurs et sur les disques.
    type_cible peut être 'fichier', 'dossier' ou None (les deux).
    """
    resultats = []
    fin = time.monotonic() + delai   # un disque entier se parcourt en minutes : on s'arrête à `delai` s et on rend ce qu'on a trouvé
    trop_long = (f"La recherche a pris plus de {int(delai)} secondes sans rien trouver.")

    if scan_global:
        userprofile = os.environ.get("USERPROFILE", "")
        from core.dossiers import dossiers_personnels
        # Dossiers prioritaires (plus rapide)
        dossiers_prioritaires = [
            *dossiers_personnels(),
            os.path.join(userprofile, "Saved Games"),
            "C:\\"
        ]
        
        # On ajoute les autres lecteurs si présents
        import string
        from ctypes import windll
        bitmask = windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drive = f"{letter}:\\"
                if drive not in dossiers_prioritaires and os.path.exists(drive):
                    dossiers_prioritaires.append(drive)
            bitmask >>= 1
            
        for base in dossiers_prioritaires:
            if not os.path.exists(base): continue
            try:
                for root, dirs, files in os.walk(base):
                    if time.monotonic() > fin:
                        return resultats, (None if resultats else trop_long)
                    # On évite certains dossiers système trop profonds ou verrouillés : le NOM du dossier, pas tout le chemin
                    # (avant, « D:\Jeux\Windows Games » ou « Documents\Mes notes Windows » n'étaient jamais fouillés)
                    if os.path.basename(root).lower() in _DOSSIERS_IGNORES:
                        dirs.clear() # Ne pas descendre plus bas
                        continue
                        
                    # 1. On cherche les DOSSIERS
                    if type_cible is None or type_cible == "dossier":
                        for d in dirs:
                            if nom.lower() == d.lower(): # Match exact
                                resultats.insert(0, os.path.join(root, d))
                            elif nom.lower() in d.lower():
                                resultats.append(os.path.join(root, d))
                            
                            if len(resultats) >= 5: return resultats, None
                            
                    # 2. On cherche les FICHIERS
                    if type_cible is None or type_cible == "fichier":
                        for f in files:
                            if nom.lower() == f.lower(): # Match exact
                                resultats.insert(0, os.path.join(root, f))
                            elif nom.lower() in f.lower():
                                resultats.append(os.path.join(root, f))
                                
                            if len(resultats) >= 5: return resultats, None
            except Exception:
                continue
    else:
        # Recherche locale uniquement
        cible = dossier_courant or os.getcwd()
        for root, dirs, files in os.walk(cible):
            if time.monotonic() > fin:
                return resultats, (None if resultats else trop_long)
            if type_cible is None or type_cible == "dossier":
                for d in dirs:
                    if nom.lower() in d.lower():
                        resultats.append(os.path.join(root, d))
            if type_cible is None or type_cible == "fichier":
                for f in files:
                    if nom.lower() in f.lower():
                        resultats.append(os.path.join(root, f))
                    
    return resultats, None

_SUFFIXES_EXECUTABLES = {".exe", ".bat", ".cmd", ".ps1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".msi", ".scr", ".com", ".lnk", ".hta", ".jar", ".reg", ".pif"}
_SUFFIXES_SECRETS = {".pem", ".key", ".pfx", ".p12", ".pickle", ".kdbx"}
_FICHIERS_SECRETS = {"jarvis_config.json", "token.json", "credentials.json", "client_secret.json", "token.pickle"}


def _fichier_sensible(chemin):
    """Clés, jetons, .env, empreintes vocales, coffre-fort : jamais lus pour l'IA (leur contenu partirait dans le prompt d'un LLM cloud, et pourrait être prononcé)."""
    p = os.path.normcase(os.path.abspath(chemin))
    nom = os.path.basename(p)
    parties = set(p.split(os.sep))
    return (nom.startswith(".env") or nom in _FICHIERS_SECRETS or os.path.splitext(nom)[1] in _SUFFIXES_SECRETS
            or bool(parties & {"voiceprints", ".jarvis_vault"}))


def _dans_le_dossier(cible, *chemins):
    """True si tous les chemins restent DANS `cible` (ni chemin absolu, ni « .. », ni autre lecteur)."""
    racine = os.path.realpath(cible)
    try:
        return all(os.path.commonpath([racine, os.path.realpath(p)]) == racine for p in chemins)
    except ValueError:
        return False


def ouvrir_fichier_ou_dossier(chemin):
    """Ouvre un fichier avec son application par défaut ou un dossier dans l'explorateur."""
    if not chemin or not os.path.exists(chemin):
        return False, "Élément introuvable."
    # Un chemin choisi par l'IA (« trouve le fichier install » -> install.bat) ne doit jamais LANCER un programme
    if os.path.isfile(chemin) and os.path.splitext(chemin)[1].lower() in _SUFFIXES_EXECUTABLES:
        return False, "Je n'ouvre pas les programmes et scripts de cette façon : ouvrez-le vous-même."
    
    try:
        os.startfile(chemin)
        return True, f"Ouverture de : {os.path.basename(chemin)}"
    except Exception:
        # Fallback subprocess
        try:
            subprocess.Popen(['explorer', chemin] if os.path.isdir(chemin) else [chemin])
            return True, f"Ouverture (via shell) de : {os.path.basename(chemin)}"
        except Exception as e2:
            return False, f"Erreur lors de l'ouverture : {e2}"

def lire_fichier(nom_fichier, chemin=None):
    """
    Lit le contenu d'un fichier (txt, md, pdf, docx, csv, py, etc.).
    Si aucun chemin n'est fourni, scanne automatiquement les dossiers communs.
    """
    if chemin:
        cible = interpreter_chemin(chemin)
        dossiers_a_scanner = [cible] if cible else []
    else:
        from core.dossiers import dossiers_personnels
        dossiers_a_scanner = [d for d in [dossier_courant, *dossiers_personnels()] if d and os.path.isdir(d)]

    chemin_complet = None

    # Chemin absolu direct ?
    if os.path.exists(nom_fichier):
        chemin_complet = nom_fichier
    # 1. Priorité à l'exactitude : on cherche d'abord le nom EXACT dans tous les dossiers
    for dossier in dossiers_a_scanner:
        test = os.path.join(dossier, nom_fichier)
        if os.path.exists(test):
            chemin_complet = test
            break
    
    # 2. Si non trouvé, on cherche en mode "intelligent"
    if not chemin_complet:
        for dossier in dossiers_a_scanner:
            for root, dirs, files in os.walk(dossier):
                depth = root.replace(dossier, "").count(os.sep)
                if depth > 5:
                    dirs.clear()
                    continue
                for f in files:
                    # Si le fichier contient le nom demandé (insensible à la casse)
                    if nom_fichier.lower() in f.lower():
                        # Si le fichier demandé est très court (ex: c.txt), on évite les correspondances partielles trop larges
                        if len(nom_fichier) <= 5 and nom_fichier.lower() != f.lower():
                            continue
                        chemin_complet = os.path.join(root, f)
                        break
                if chemin_complet: break
            if chemin_complet: break

    if not chemin_complet or not os.path.exists(chemin_complet):
        return None, f"Le fichier '{nom_fichier}' est introuvable."
    if _fichier_sensible(chemin_complet):
        return None, "Je ne lis pas ce fichier : il contient des secrets."

    print(f"[FILE_MANAGER] Lecture du fichier : {chemin_complet}")

    ext = Path(chemin_complet).suffix.lower()
    texte = ""

    try:
        if ext == '.pdf':
            if pypdf is None:
                return None, "La bibliothèque pypdf n'est pas installée."
            with open(chemin_complet, 'rb') as f:
                reader = pypdf.PdfReader(f)
                for page in reader.pages:
                    texte += page.extract_text() + "\n"
        elif ext in ['.doc', '.docx']:
            if docx is None:
                return None, "La bibliothèque python-docx n'est pas installée."
            doc = docx.Document(chemin_complet)
            for para in doc.paragraphs:
                texte += para.text + "\n"
        else:
            with open(chemin_complet, 'r', encoding='utf-8', errors='ignore') as f:
                texte = f.read()

        if len(texte) > 50000:
            texte = texte[:50000] + "... [CONTENU TRONQUÉ CAR TROP LONG]"

        return texte, chemin_complet
    except Exception as e:
        return None, f"Impossible de lire le fichier : {e}"


# mais si mon fichier fait moins de 100 caracteres il le considerera comme une commande, je veux que rien de ce qu'il lise dans aucun fichier ne soit considéré comme une commande lorsque je lui demande une action sur un fichier 