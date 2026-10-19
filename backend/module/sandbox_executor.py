import os
import sys
import subprocess
import asyncio
import time

# Répertoire sandbox par défaut
SANDBOX_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sandbox"))
os.makedirs(SANDBOX_BASE_DIR, exist_ok=True)


_VERSION_NODE = None


def _option_permission_node():
    """« --permission » (Node ≥ 22.13), « --experimental-permission » (Node 20 à 22.12), ou
    None si Node est trop ancien pour limiter les accès."""
    global _VERSION_NODE
    if _VERSION_NODE is None:
        try:
            sortie = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5).stdout
            _VERSION_NODE = tuple(int(x) for x in sortie.strip().lstrip("v").split(".")[:2])
        except Exception:
            _VERSION_NODE = (0, 0)
    if _VERSION_NODE >= (22, 13):
        return "--permission"
    if _VERSION_NODE >= (20, 0):
        return "--experimental-permission"
    return None


def _permissions_node(dossier: str) -> list:
    """Options du modèle de permissions de Node : lecture/écriture limitées au dossier du
    projet, pas de processus enfants ni de modules natifs. Sans modèle de permissions
    (Node < 20), le script n'est pas exécuté (option invalide → échec immédiat)."""
    racine = os.path.abspath(dossier)
    option = _option_permission_node()
    if option is None:
        return ["--node-trop-ancien-pour-la-sandbox"]
    return [option, f"--allow-fs-read={racine}{os.sep}*", f"--allow-fs-write={racine}{os.sep}*"]


def _dans_sandbox(chemin: str):
    """Résout `chemin` et vérifie qu'il reste DANS SANDBOX_BASE_DIR.

    Retourne le chemin absolu, ou None s'il s'en échappe. Indispensable : sans ce
    contrôle, `working_dir` acceptait n'importe quel dossier existant de la machine
    et `executer_fichier_sandbox` exécutait n'importe quel .py/.js du disque.

    ⚠️ ATTENTION — ceci n'est PAS une isolation de sécurité. Le processus enfant
    tourne avec le même compte utilisateur et les mêmes droits que JARVIS : il peut
    lire/écrire ailleurs et accéder au réseau. Le confinement ci-dessous limite le
    point d'entrée (quels fichiers on accepte de lancer), pas ce que le code fait
    une fois lancé. Ne jamais y exécuter du code non fiable sans relecture.
    """
    if not chemin or not isinstance(chemin, str):
        return None
    try:
        absolu = os.path.abspath(chemin)
        if os.path.commonpath([absolu, SANDBOX_BASE_DIR]) != SANDBOX_BASE_DIR:
            return None
        return absolu
    except Exception:
        return None


async def executer_fichier_sandbox(
    file_path: str,
    timeout: int = 15
) -> dict:
    """
    Exécute un fichier de code existant dans la sandbox.
    """
    # Confinement : on n'exécute QUE des fichiers situés dans la sandbox.
    chemin_sur = _dans_sandbox(file_path)
    if chemin_sur is None:
        return {
            "success": False,
            "return_code": -1,
            "stdout": "",
            "stderr": ("Refusé : ce fichier est en dehors de la sandbox "
                       f"({SANDBOX_BASE_DIR}). Chemin demandé : {file_path}"),
            "execution_time": 0
        }
    file_path = chemin_sur

    if not os.path.exists(file_path):
        return {
            "success": False,
            "return_code": -1,
            "stdout": "",
            "stderr": f"Fichier introuvable : {file_path}",
            "execution_time": 0
        }

    ext = os.path.splitext(file_path)[1].lower()
    working_dir = os.path.dirname(file_path)

    if ext == ".py":
        # venv à la racine du projet (le chemin visait backend/venv, inexistant)
        python_exe = os.path.join(os.path.dirname(__file__), "..", "..", "venv", "Scripts", "python.exe")
        if not os.path.exists(python_exe):
            python_exe = sys.executable
        # La « sandbox » ne fait que fixer le dossier de travail : le code a tous les droits
        # de l'utilisateur. Le code Python généré passe donc d'abord le contrôle de sûreté
        # des compétences (imports et appels destructeurs, écriture de fichiers…).
        from module.competences import scanner_appels_dangereux
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                ok_sur, raison = scanner_appels_dangereux(f.read())
        except Exception as e:
            ok_sur, raison = False, f"lecture impossible ({e})"
        if not ok_sur:
            return {
                "success": False,
                "return_code": -1,
                "stdout": "",
                "stderr": f"Non exécuté : contrôle de sûreté refusé ({raison}).",
                "execution_time": 0
            }
        cmd = [python_exe, file_path]
    elif ext == ".js":
        cmd = ["node", *_permissions_node(working_dir), file_path]
    else:
        return {
            "success": False,
            "return_code": -1,
            "stdout": "",
            "stderr": f"Extension '{ext}' non supportée pour l'exécution directe.",
            "execution_time": 0
        }

    start_time = time.time()
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_dir
        )
        stdout_data, stderr_data = await asyncio.wait_for(process.communicate(), timeout=timeout)
        execution_time = round(time.time() - start_time, 3)

        return {
            "success": process.returncode == 0,
            "return_code": process.returncode,
            "stdout": stdout_data.decode("utf-8", errors="replace").strip(),
            "stderr": stderr_data.decode("utf-8", errors="replace").strip(),
            "execution_time": execution_time
        }
    except asyncio.TimeoutError:
        try:
            process.kill()
        except Exception:
            pass
        return {
            "success": False,
            "return_code": -1,
            "stdout": "",
            "stderr": f"Dépassement du temps d'exécution limite ({timeout}s). Processus interrompu.",
            "execution_time": timeout
        }
    except Exception as e:
        return {
            "success": False,
            "return_code": -1,
            "stdout": "",
            "stderr": f"Erreur d'exécution : {str(e)}",
            "execution_time": 0
        }
