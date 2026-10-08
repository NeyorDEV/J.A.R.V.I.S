import os
import winreg
import re
import shutil
import subprocess

def clean_name_for_search(name):
    """Nettoie le nom de l'application pour la recherche heuristique de traces."""
    # Retirer les parenthèses et les mentions de version
    name = re.sub(r'\(.*?\)|v\d+(\.\d+)*|\d+\.\d+(\.\d+)*', '', name)
    # Retirer les caractères spéciaux
    name = re.sub(r'[^a-zA-Z0-9\s-]', '', name)
    return name.strip()

def _cle_nom(nom):
    """Nom réduit à ses lettres et chiffres, en minuscules (« Node.js » → « nodejs »)."""
    return re.sub(r'[^a-z0-9]', '', (nom or "").lower())


def _cle_recherche(app_name):
    """Clé de comparaison des résidus, ou "" si le nom est trop court ou partagé.

    Avant, un dossier ou une clé de registre était un « résidu » dès qu'il CONTENAIT le
    nom du programme : « Node.js » visait aussi AppData\\Local\\claude-cli-nodejs, et
    « Python 3.12 » tout AppData\\Local\\Programs\\Python (autres versions comprises).
    Désormais le nom doit être identique, et un nom que porte encore un autre programme
    installé (Python 3.12 / Python 3.14 → « Python ») n'est pas utilisé du tout.
    """
    cle = _cle_nom(clean_name_for_search(app_name))
    if len(cle) < 4:
        return ""
    for p in list_installed_programs():
        if p["name"] != app_name and _cle_nom(clean_name_for_search(p["name"])) == cle:
            return ""
    return cle


def _dossier_en_cours_utilisation(chemin):
    """True si un processus en cours d'exécution a son exécutable dans ce dossier."""
    try:
        import psutil
        racine = os.path.normcase(os.path.abspath(chemin)) + os.sep
        for proc in psutil.process_iter(['exe']):
            exe = proc.info.get('exe')
            if exe and os.path.normcase(exe).startswith(racine):
                return True
    except Exception:
        pass
    return False


def list_installed_programs():
    """Énumère toutes les applications installées sur la machine à partir du Registre."""
    paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall")
    ]
    
    programs = []
    seen = set()
    
    for hive, path in paths:
        try:
            key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
            info = winreg.QueryInfoKey(key)
            num_subkeys = info[0]
            
            for i in range(num_subkeys):
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name, 0, winreg.KEY_READ)
                    
                    try:
                        name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                        uninstall_string, _ = winreg.QueryValueEx(subkey, "UninstallString")
                        
                        name = name.strip()
                        if not name or name in seen:
                            winreg.CloseKey(subkey)
                            continue
                            
                        seen.add(name)
                        
                        # Fallbacks facultatifs
                        publisher = ""
                        try: publisher, _ = winreg.QueryValueEx(subkey, "Publisher")
                        except OSError: pass
                        
                        version = ""
                        try: version, _ = winreg.QueryValueEx(subkey, "DisplayVersion")
                        except OSError: pass
                        
                        install_location = ""
                        try: install_location, _ = winreg.QueryValueEx(subkey, "InstallLocation")
                        except OSError: pass
                        
                        icon_path = ""
                        try: icon_path, _ = winreg.QueryValueEx(subkey, "DisplayIcon")
                        except OSError: pass
                        
                        programs.append({
                            "name": name,
                            "subkey": subkey_name,
                            "publisher": publisher.strip(),
                            "version": version.strip(),
                            "uninstall_string": uninstall_string.strip(),
                            "install_location": install_location.strip(),
                            "icon_path": icon_path.strip(),
                            "hive": "HKLM" if hive == winreg.HKEY_LOCAL_MACHINE else "HKCU"
                        })
                    except OSError:
                        pass
                    finally:
                        winreg.CloseKey(subkey)
                except OSError:
                    continue
            winreg.CloseKey(key)
        except OSError:
            continue
            
    programs.sort(key=lambda x: x["name"].lower())
    return programs

def scan_file_leftovers(app_name, publisher="", install_location=""):
    """Recherche des dossiers laissés par l'application (nom identique, voir _cle_recherche)."""
    cle = _cle_recherche(app_name)
    cle_editeur = _cle_nom(clean_name_for_search(publisher)) if publisher else ""

    leftovers = []
    seen_paths = set()

    def _ajouter(chemin, desc):
        abs_path = os.path.abspath(chemin)
        # Jamais la racine d'un disque, ni un dossier dont un programme tourne encore
        if abs_path in seen_paths or len(abs_path) <= 4 or _dossier_en_cours_utilisation(abs_path):
            return
        seen_paths.add(abs_path)
        leftovers.append({"type": "folder", "path": abs_path, "desc": desc})

    # 1. Dossier d'installation officiel indiqué par le Registre
    if install_location and os.path.isdir(install_location):
        _ajouter(install_location, "Dossier d'installation officiel configuré dans le Registre Windows.")

    if not cle:
        return leftovers

    search_dirs = [
        os.environ.get("ProgramFiles", "C:\\Program Files"),
        os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
        os.environ.get("ProgramData", "C:\\ProgramData"),
        os.path.expanduser("~/AppData/Local"),
        os.path.expanduser("~/AppData/Roaming"),
        os.path.expanduser("~/AppData/LocalLow"),
        os.path.expanduser("~/AppData/Local/Programs"),
    ]
    for base_dir in search_dirs:
        if not base_dir or not os.path.isdir(base_dir):
            continue
        try:
            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                if not os.path.isdir(item_path):
                    continue
                if _cle_nom(item) == cle:
                    _ajouter(item_path, f"Dossier associé à l'application dans {os.path.basename(base_dir)}.")
                    continue
                # Niveau 2, seulement sous le dossier de l'éditeur (ex : Google\Android Studio)
                if not cle_editeur or _cle_nom(item) != cle_editeur:
                    continue
                try:
                    for subitem in os.listdir(item_path):
                        subitem_path = os.path.join(item_path, subitem)
                        if os.path.isdir(subitem_path) and _cle_nom(subitem) == cle:
                            _ajouter(subitem_path, f"Dossier associé à l'application sous l'éditeur '{item}'.")
                except OSError:
                    pass
        except OSError:
            continue

    return leftovers


def scan_registry_leftovers(app_name, publisher=""):
    """Recherche des clés de registre laissées par l'application (nom identique)."""
    cle = _cle_recherche(app_name)
    if not cle:
        return []
    cle_editeur = _cle_nom(clean_name_for_search(publisher)) if publisher else ""
    leftovers = []

    hives = [
        (winreg.HKEY_CURRENT_USER, "Software"),
        (winreg.HKEY_LOCAL_MACHINE, "Software"),
        (winreg.HKEY_LOCAL_MACHINE, "Software\\Wow6432Node")
    ]
    for hive, base_path in hives:
        hive_name = "HKCU" if hive == winreg.HKEY_CURRENT_USER else "HKLM"
        try:
            key = winreg.OpenKey(hive, base_path, 0, winreg.KEY_READ)
            num_subkeys = winreg.QueryInfoKey(key)[0]
            for i in range(num_subkeys):
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    full_path = f"{hive_name}\\{base_path}\\{subkey_name}"
                    if _cle_nom(subkey_name) == cle:
                        leftovers.append({
                            "type": "registry",
                            "hive": hive_name,
                            "path": full_path,
                            "desc": "Clé de registre associée au nom de l'application."
                        })
                        continue
                    # Niveau 2 (ex : HKLM\Software\Editeur\Application)
                    if not cle_editeur or _cle_nom(subkey_name) != cle_editeur:
                        continue
                    try:
                        pub_key = winreg.OpenKey(hive, f"{base_path}\\{subkey_name}", 0, winreg.KEY_READ)
                        for j in range(winreg.QueryInfoKey(pub_key)[0]):
                            subkey_subname = winreg.EnumKey(pub_key, j)
                            if _cle_nom(subkey_subname) == cle:
                                leftovers.append({
                                    "type": "registry",
                                    "hive": hive_name,
                                    "path": f"{full_path}\\{subkey_subname}",
                                    "desc": f"Clé de registre associée sous l'éditeur '{subkey_name}'."
                                })
                        winreg.CloseKey(pub_key)
                    except OSError:
                        pass
                except OSError:
                    continue
            winreg.CloseKey(key)
        except OSError:
            continue

    return leftovers


def programme_installe(app_name, uninstall_string=""):
    """True si le programme figure encore dans la liste des programmes installés."""
    for p in list_installed_programs():
        if p["name"] == app_name or (uninstall_string and p["uninstall_string"] == uninstall_string.strip()):
            return True
    return False


def run_uninstall_process(uninstall_string, app_name="", delai_max=300):
    """Lance le désinstallateur officiel et vérifie que le programme a bien disparu.

    Avant, le code de retour était ignoré : une désinstallation annulée ou ratée était
    annoncée « terminée », puis on cherchait les « résidus » d'un programme encore
    installé. De nombreux désinstalleurs (Inno Setup, certains MSI) se relancent en
    arrière-plan et rendent la main tout de suite : on attend donc que l'entrée du
    programme disparaisse du Registre (au plus `delai_max` secondes).
    """
    try:
        print(f"[UNINSTALLER] Lancement du désinstallateur officiel : {uninstall_string}")
        p = subprocess.Popen(uninstall_string, shell=True)
        code = p.wait()
    except Exception as e:
        print(f"[UNINSTALLER] Erreur lors du lancement de la désinstallation : {e}")
        return False, str(e)

    if not app_name:
        return code == 0, ("Désinstallation officielle terminée." if code == 0
                           else f"Le désinstalleur s'est arrêté avec le code {code}.")

    import time
    debut = time.time()
    while programme_installe(app_name, uninstall_string):
        if time.time() - debut > delai_max:
            return False, (f"{app_name} est toujours installé : la désinstallation a été annulée "
                           f"ou n'est pas terminée.")
        time.sleep(2)
    return True, "Désinstallation officielle terminée."

def delete_registry_key_recursive(hive, path):
    """Supprime une clé de registre et toutes ses sous-clés récursivement."""
    # Convertir le nom de la ruche en objet winreg HKEY
    hkey_hive = winreg.HKEY_CURRENT_USER if hive == "HKCU" else winreg.HKEY_LOCAL_MACHINE
    
    try:
        # 1. Ouvrir la clé pour lister les sous-clés
        key = winreg.OpenKey(hkey_hive, path, 0, winreg.KEY_ALL_ACCESS)
        info = winreg.QueryInfoKey(key)
        num_subkeys = info[0]
        
        subkeys = []
        for i in range(num_subkeys):
            subkeys.append(winreg.EnumKey(key, i))
        winreg.CloseKey(key)
        
        # 2. Supprimer les sous-clés d'abord récursivement
        for subkey in subkeys:
            delete_registry_key_recursive(hive, f"{path}\\{subkey}")
            
        # 3. Supprimer la clé elle-même
        parent_path, key_name = path.rsplit("\\", 1)
        parent_key = winreg.OpenKey(hkey_hive, parent_path, 0, winreg.KEY_ALL_ACCESS)
        winreg.DeleteKey(parent_key, key_name)
        winreg.CloseKey(parent_key)
        return True
    except Exception as e:
        print(f"[UNINSTALLER] Échec de la suppression de la clé de registre {hive}\\{path} : {e}")
        return False

def clean_leftover_item(item):
    """Supprime un élément résiduel (dossier ou clé de registre)."""
    item_type = item.get("type")
    path = item.get("path")
    
    if item_type == "folder":
        if not path or len(path) <= 4:
            return False, "Chemin invalide ou trop court pour suppression sécurisée."
        try:
            if os.path.exists(path):
                shutil.rmtree(path)
                return True, "Dossier supprimé avec succès."
            return True, "Dossier déjà inexistant."
        except Exception as e:
            return False, f"Impossible de supprimer le dossier : {e}"
            
    elif item_type == "registry":
        hive = item.get("hive")
        # Le chemin contient la ruche au début (HKCU\ ou HKLM\), on doit le découper
        parts = path.split("\\", 1)
        if len(parts) < 2:
            return False, "Chemin de registre invalide."
        reg_path = parts[1]
        
        success = delete_registry_key_recursive(hive, reg_path)
        if success:
            return True, "Clé de registre supprimée avec succès."
        return False, "Échec de la suppression de la clé."
        
    return False, "Type de résidu inconnu."
