"""
competences.py — Système de compétences autonomes de JARVIS.

Génération de plugins Python par LLM (fabriquer_competence), suppression
et exécution à chaud. Extrait de main2.py.

diffuser_web_sync est un hook injecté par main2.py après import
(évite l'import circulaire).
"""

import ast
import os

from core.audit_log import consigner
from core.interlocuteur import nom_espace, nom_virgule

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Hook remplacé par main2.py après import (envoi d'un payload au HUD web)
def diffuser_web_sync(payload):
    pass


# ── CONTRÔLE DE SÛRETÉ DU CODE GÉNÉRÉ ─────────────────────────────────────────
# Une compétence est du code Python écrit par un LLM, puis importé dans le
# processus JARVIS avec tous les droits de l'utilisateur. Sans filtrage, un code
# malformé ou détourné (injection de prompt) s'exécutait DÈS L'IMPORT — donc
# avant même l'appel à executer() — et pouvait par exemple effacer le disque.
# On analyse donc l'AST avant d'écrire le fichier ET avant de l'exécuter.

_MODULES_INTERDITS = {
    "subprocess", "ctypes", "shutil", "winreg", "_winreg",
    "multiprocessing", "pty", "pickle", "marshal",
    # Contournements de l'analyse : import dynamique, accès aux builtins, exécution de code
    "importlib", "builtins", "runpy", "code", "codeop", "imp", "pydoc", "gc", "inspect",
    "win32api", "win32con", "win32file", "win32process", "winshell", "send2trash",
}

_APPELS_INTERDITS = {
    "eval", "exec", "compile", "__import__", "breakpoint",
    "system", "popen", "spawn", "spawnl", "spawnv", "execv", "execve",
    "rmtree", "unlink", "rmdir", "removedirs", "chmod", "chown",
    "kill", "killpg", "startfile",
    # Écriture / déplacement de fichiers (pathlib, os) et accès indirects aux fonctions
    "write_text", "write_bytes", "rename", "renames", "truncate",
    "getattr", "setattr", "delattr", "globals", "locals", "vars", "import_module",
}

# Noms qu'il est interdit de seulement mentionner (même sans appel) : ils donnent accès
# à tout le reste (« getattr(__builtins__, "__imp"+"ort__")("os") » passait l'ancien scan).
# Noms courants aussi pour les chaînes et les listes (« texte.replace », « liste.remove ») :
# interdits seulement appelés sur os (os.remove, os.replace) ou importés seuls depuis os.
_APPELS_AMBIGUS = {"remove", "replace"}

_NOMS_INTERDITS = {"__builtins__", "__import__", "getattr", "setattr", "delattr", "globals",
                   "locals", "vars", "eval", "exec", "compile"}


def scanner_appels_dangereux(code: str, autoriser_builtins: bool = False):
    """Scan générique : imports et appels destructeurs. (True, "") si propre.

    Réutilisable pour tout code Python généré par un LLM (compétences, plugins).
    `autoriser_builtins` : un plugin a besoin d'« import builtins » pour s'enregistrer
    (builtins.resoudre_x = …) ; ses attributs dangereux restent interdits.
    """
    try:
        arbre = ast.parse(code)
    except SyntaxError as e:
        return False, f"code Python invalide (ligne {e.lineno} : {e.msg})"

    interdits = _MODULES_INTERDITS - ({"builtins"} if autoriser_builtins else set())
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                if alias.name.split(".")[0] in interdits:
                    return False, f"import interdit : {alias.name}"
        elif isinstance(noeud, ast.ImportFrom):
            if (noeud.module or "").split(".")[0] in _MODULES_INTERDITS:
                return False, f"import interdit : {noeud.module}"
        elif isinstance(noeud, ast.Name) and noeud.id in _NOMS_INTERDITS:
            return False, f"nom interdit : {noeud.id} (ligne {getattr(noeud, 'lineno', '?')})"
        elif isinstance(noeud, ast.Attribute) and (noeud.attr.startswith("__") or noeud.attr in _NOMS_INTERDITS):
            # __class__, __subclasses__, __globals__…, builtins.getattr / builtins.eval :
            # remontée vers les fonctions interdites
            return False, f"attribut interdit : {noeud.attr} (ligne {getattr(noeud, 'lineno', '?')})"
        elif isinstance(noeud, ast.Call):
            f = noeud.func
            nom = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
            if nom in _APPELS_INTERDITS:
                return False, f"appel interdit : {nom}() (ligne {getattr(noeud, 'lineno', '?')})"
            if nom in _APPELS_AMBIGUS and (isinstance(f, ast.Name) or (
                    isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "os")):
                return False, f"appel interdit : {nom}() (ligne {getattr(noeud, 'lineno', '?')})"
            if nom == "open" and not _ouverture_en_lecture(noeud):
                return False, f"ouverture de fichier en écriture interdite (ligne {getattr(noeud, 'lineno', '?')})"
    return True, ""


def _ouverture_en_lecture(appel):
    """True si open(...) est en lecture seule (mode littéral sans w / a / x / +)."""
    mode = None
    if len(appel.args) >= 2:
        mode = appel.args[1]
    for kw in appel.keywords:
        if kw.arg == "mode":
            mode = kw.value
    if mode is None:
        return True
    return isinstance(mode, ast.Constant) and isinstance(mode.value, str) \
        and not any(c in mode.value for c in "wax+")


def valider_code_competence(code: str):
    """Retourne (True, "") si le code est acceptable, sinon (False, raison)."""
    try:
        arbre = ast.parse(code)
    except SyntaxError as e:
        return False, f"code Python invalide (ligne {e.lineno} : {e.msg})"

    # 1. Aucun effet de bord au niveau module : seuls imports, définitions et
    #    constantes sont tolérés. C'est ce qui neutralise le code « qui s'exécute
    #    à l'import », et le contrat impose de toute façon une fonction executer().
    autorises_au_module = (
        ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef,
        ast.ClassDef, ast.Assign, ast.AnnAssign, ast.Pass,
    )
    for noeud in arbre.body:
        if isinstance(noeud, ast.Expr) and isinstance(noeud.value, ast.Constant):
            continue  # docstring
        if isinstance(noeud, ast.If):
            # Tolère uniquement le garde if __name__ == "__main__":
            test = ast.dump(noeud.test)
            if "__name__" in test:
                continue
            return False, "instruction conditionnelle exécutée à l'import"
        if not isinstance(noeud, autorises_au_module):
            return False, (f"instruction exécutée à l'import "
                           f"({type(noeud).__name__}, ligne {getattr(noeud, 'lineno', '?')})")

    # 2. Interdictions globales (y compris à l'intérieur des fonctions) : même analyse que
    #    pour les plugins (une copie plus faible, ici, laissait passer open(..., "w") et
    #    les remontées par __class__ / __subclasses__)
    ok, raison = scanner_appels_dangereux(code)
    if not ok:
        return False, raison

    if not any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "executer"
               for n in arbre.body):
        return False, "la fonction obligatoire executer() est absente"

    return True, ""

# ── ANIMATION VISUELLE & SYSTEME DE COMPETENCES AUTONOMES ─────────────────────

def _effet_hud_matrice(stop_event):
    """Joue un défilement de caractères façon HUD dans la console et sur l'interface web."""
    import random
    import time

    # Passer l'orbe en état thinking immédiatement pour l'animer à l'écran
    diffuser_web_sync({"action": "set_state", "state": "thinking"})

    logs_fictifs = [
        ">System: Allocating compilation segment on core_0...",
        ">Connecting to Gemini Neural Correlator (Model: gemini-3.5-flash)...",
        ">Enabling thinking mode (Budget: 2048)...",
        ">Synchronizing thought matrix constraints...",
        ">Heap alloc: 0x7ffa4c9e0000 [64mb]",
        "[System] Loading libraries: importlib.util, os, time, sys",
        "[Compile] Generating function signature: def executer(texte_utilisateur=None)",
        "[Parser] Enforcing raw python rules: no markdown tags, pure source...",
        "[Compiler] Building AST Nodes...",
        "[System] Compiling resource: plugins/competence_*.py",
        ">Compacting source code buffer...",
        ">Injecting voice output return strings...",
        ">Shield power stability: 98.4%",
        ">Scanning corrupted sectors... OK",
        "[Log] Dynamic loader thread instantiated.",
        "[Info] Code integrity check: 100% compliant.",
        "[Debug] Temperature: 0.1 | Top-P: 0.95 | Top-K: 40",
    ]
    caracteres = "ABCDEF0123456789ghijklmnopqrstuvwxyz{}[]()#$@!&%*+=-_^"

    print("\n\033[93m" + "="*60)
    print("   JARVIS · ATELIER DE COMPÉTENCES : COMPILATION")
    print("="*60 + "\033[0m\n")

    iteration = 0
    while not stop_event.is_set():
        val = random.random()
        log_texte = ""
        if val < 0.3:
            log_texte = random.choice(logs_fictifs)
            print(f"\033[94m[HUD_LOG] {log_texte}\033[0m")
        elif val < 0.6:
            addr = f"0x{random.randint(0x10000000, 0xFFFFFFFF):X}"
            data = "".join(random.choice(caracteres) for _ in range(40))
            log_texte = f"{addr} : {data}"
            print(f"\033[92m[MATRICE] {log_texte}\033[0m")
        else:
            progress = random.randint(0, 100)
            bar = "=" * (progress // 5) + " " * (20 - (progress // 5))
            log_texte = f"COMPILING: [{bar}] {progress}%"
            print(f"\033[96m[SYSTEM] {log_texte}\033[0m")
            
        # Toutes les 2 itérations (~80ms), envoyer le log actuel au HUD web pour le défilement
        if iteration % 2 == 0:
            diffuser_web_sync({"action": "jarvis_text", "text": f"[HUD] {log_texte}"})
            
        iteration += 1
        time.sleep(0.04)

    print("\n\033[92m" + "="*60)
    print("   JARVIS · COMPÉTENCE INTÉGRÉE")
    print("="*60 + "\033[0m\n")

    # Restaurer l'état d'origine de l'orbe et du texte
    diffuser_web_sync({"action": "set_state", "state": "idle"})
    diffuser_web_sync({"action": "jarvis_text", "text": "COMPÉTENCE PRÊTE ET CHARGÉE"})


def fabriquer_competence(nom_competence: str, description_demande: str) -> str:
    """
    Demande à Gemini (réflexion activée) d'écrire une compétence Python autonome.
    Le code est enregistré dans plugins/competence_<nom>.py.
    """
    import re
    import threading
    import os
    import builtins
    from google.genai import types as _gtypes

    # Valider le client API
    if not hasattr(builtins, "client") or not builtins.client:
        return "Impossible de générer la compétence : Gemini n'est pas prêt (client absent ou clé refusée)."

    nom_formate = re.sub(r'[^a-zA-Z0-9_]', '', nom_competence.lower().replace(" ", "_"))
    dossier_plugins = os.path.join(_BASE_DIR, "plugins")
    if not os.path.exists(dossier_plugins):
        os.makedirs(dossier_plugins, exist_ok=True)
    
    filename = os.path.join(dossier_plugins, f"competence_{nom_formate}.py")

    # Animation Iron Man
    stop_event = threading.Event()
    thread_anim = threading.Thread(target=_effet_hud_matrice, args=(stop_event,), daemon=True)
    thread_anim.start()

    try:
        system_instruction = (
            "Tu rédiges des compétences Python autonomes pour l'assistant JARVIS.\n"
            "Le code doit être valide, propre et sans fioritures.\n\n"
            "CONTRAINTES À RESPECTER :\n"
            "1. Réponds avec le code Python seul : aucune balise markdown (pas de ```python ni de ```), aucun commentaire hors du code.\n"
            "2. Le script doit se suffire à lui-même.\n"
            "3. Définis obligatoirement `executer(texte_utilisateur=None)` : un argument texte facultatif, et le retour DOIT être une chaîne (la phrase que JARVIS dira à voix haute).\n"
            "4. N'utilise aucun service demandant des identifiants que tu n'as pas (clés d'API tierces) : reste sur des API publiques ou des données simulées. La bibliothèque standard et requests sont permises."
        )

        prompt = (
            f"Écris le code de la compétence nommée '{nom_competence}'.\n"
            f"But recherché : {description_demande}\n\n"
            "Respecte toutes les contraintes de structure indiquées."
        )

        # Appel Gemini-3.5-flash avec configuration Thinking
        response = builtins.client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
            config=_gtypes.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.1,
                thinking_config=_gtypes.ThinkingConfig(thinking_budget=2048)
            )
        )

        code_genere = response.text.strip()
        
        # Nettoyage de sécurité en cas de balises markdown résiduelles
        if code_genere.startswith("```"):
            lines = code_genere.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            code_genere = "\n".join(lines).strip()

        # Contrôle de sûreté AVANT écriture : on refuse d'installer du code
        # comportant des effets de bord à l'import ou des appels destructeurs.
        ok, raison = valider_code_competence(code_genere)
        if not ok:
            stop_event.set()
            thread_anim.join()
            print(f"[JARVIS PLUGINS] ⛔ Compétence refusée par le contrôle de sûreté : {raison}")
            consigner("competence_refusee", nom=nom_competence, raison=raison)
            return (f"J'ai refusé d'installer cette compétence{nom_virgule()} : le code généré "
                    f"n'a pas passé le contrôle de sûreté ({raison}).")

        # Écriture du fichier compétence
        with open(filename, "w", encoding="utf-8") as f:
            f.write(code_genere)

        stop_event.set()
        thread_anim.join()

        print(f"[COMPÉTENCES] Fichier créé : {filename}")
        consigner("competence_creee", nom=nom_competence, description=description_demande, fichier=filename)
        return f"La compétence '{nom_competence}' est créée et installée. Vous pouvez la lancer."

    except Exception as e:
        stop_event.set()
        thread_anim.join()
        print(f"[COMPÉTENCES] Échec de la création : {e}")
        consigner("competence_erreur_creation", nom=nom_competence, erreur=str(e))
        return f"Désolé{nom_espace()}, la génération de la compétence a échoué. Détail de l'erreur : {e}"


def retirer_competence(nom_competence: str) -> str:
    """Retire le fichier de la compétence demandée."""
    import re
    import os
    nom_formate = re.sub(r'[^a-zA-Z0-9_]', '', nom_competence.lower().replace(" ", "_"))
    filename = os.path.join(_BASE_DIR, "plugins", f"competence_{nom_formate}.py")

    if os.path.exists(filename):
        try:
            os.remove(filename)
            print(f"[COMPÉTENCES] Retirée : {filename}")
            consigner("competence_supprimee", nom=nom_competence, fichier=filename)
            return f"La compétence '{nom_competence}' est désinstallée, son fichier est effacé."
        except Exception as e:
            return f"Suppression du fichier impossible : {e}"
    else:
        return f"La compétence '{nom_competence}' n'est pas installée."


def lancer_competence_vocale(nom_competence: str, texte_recu: str = None) -> str:
    """Charge puis lance la compétence demandée à la voix."""
    import re
    import os
    import sys
    import importlib.util

    nom_formate = re.sub(r'[^a-zA-Z0-9_]', '', nom_competence.lower().replace(" ", "_"))
    filename = os.path.join(_BASE_DIR, "plugins", f"competence_{nom_formate}.py")

    if not os.path.exists(filename):
        return f"Désolé{nom_espace()}, la compétence '{nom_competence}' n'est pas disponible."

    # Second contrôle, juste avant exécution : couvre les fichiers déjà présents
    # sur le disque (générés avant l'ajout du filtre, ou modifiés à la main).
    try:
        with open(filename, "r", encoding="utf-8") as _fc:
            _code_disque = _fc.read()
        ok, raison = valider_code_competence(_code_disque)
        if not ok:
            print(f"[JARVIS PLUGINS] ⛔ Exécution refusée ({nom_formate}) : {raison}")
            consigner("competence_execution_refusee", nom=nom_competence, raison=raison)
            return (f"J'ai refusé d'exécuter la compétence '{nom_competence}' : "
                    f"son code ne passe pas le contrôle de sûreté ({raison}).")
    except Exception as e_val:
        return f"Impossible de vérifier la compétence '{nom_competence}' : {e_val}"

    try:
        # Importation à chaud
        module_name = f"plugins.competence_{nom_formate}"
        spec = importlib.util.spec_from_file_location(module_name, filename)
        if spec is None or spec.loader is None:
            return "Le module de la compétence ne peut pas être chargé."

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        if hasattr(module, "executer"):
            res = module.executer(texte_recu)
            consigner("competence_executee", nom=nom_competence)
            return str(res)
        else:
            return "Cette compétence n'expose pas de fonction 'executer'."

    except Exception as e:
        print(f"[COMPÉTENCES] Échec à l'exécution de {nom_competence} : {e}")
        consigner("competence_erreur_execution", nom=nom_competence, erreur=str(e))
        return f"La compétence '{nom_competence}' : {e}"


