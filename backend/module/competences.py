"""
competences.py — Système de compétences autonomes de JARVIS.

Génération de plugins Python par LLM (jarvis_creer_competence), suppression
et exécution à chaud. Extrait de main2.py.

send_web_broadcast_sync est un hook injecté par main2.py après import
(évite l'import circulaire).
"""

import ast
import os

from core.audit_log import consigner

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Hook remplacé par main2.py après import (envoi d'un payload au HUD web)
def send_web_broadcast_sync(payload):
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
}

_APPELS_INTERDITS = {
    "eval", "exec", "compile", "__import__", "breakpoint",
    "system", "popen", "spawn", "spawnl", "spawnv", "execv", "execve",
    "rmtree", "remove", "unlink", "rmdir", "removedirs", "chmod", "chown",
    "kill", "killpg", "startfile",
}


def scanner_appels_dangereux(code: str):
    """Scan générique : imports et appels destructeurs. (True, "") si propre.

    Réutilisable pour tout code Python généré par un LLM (compétences, plugins).
    """
    try:
        arbre = ast.parse(code)
    except SyntaxError as e:
        return False, f"code Python invalide (ligne {e.lineno} : {e.msg})"

    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                if alias.name.split(".")[0] in _MODULES_INTERDITS:
                    return False, f"import interdit : {alias.name}"
        elif isinstance(noeud, ast.ImportFrom):
            if (noeud.module or "").split(".")[0] in _MODULES_INTERDITS:
                return False, f"import interdit : {noeud.module}"
        elif isinstance(noeud, ast.Call):
            f = noeud.func
            nom = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
            if nom in _APPELS_INTERDITS:
                return False, f"appel interdit : {nom}() (ligne {getattr(noeud, 'lineno', '?')})"
    return True, ""


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

    # 2. Interdictions globales (y compris à l'intérieur des fonctions)
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                racine = alias.name.split(".")[0]
                if racine in _MODULES_INTERDITS:
                    return False, f"import interdit : {alias.name}"
        elif isinstance(noeud, ast.ImportFrom):
            racine = (noeud.module or "").split(".")[0]
            if racine in _MODULES_INTERDITS:
                return False, f"import interdit : {noeud.module}"
        elif isinstance(noeud, ast.Call):
            f = noeud.func
            nom = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
            if nom in _APPELS_INTERDITS:
                return False, f"appel interdit : {nom}() (ligne {getattr(noeud, 'lineno', '?')})"

    if not any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "executer"
               for n in arbre.body):
        return False, "la fonction obligatoire executer() est absente"

    return True, ""

# ── ANIMATION VISUELLE & SYSTEME DE COMPETENCES AUTONOMES ─────────────────────

def _effet_visuel_iron_man(stop_event):
    """Affiche un effet de défilement de code et logs style Iron Man HUD dans la console et sur l'écran web."""
    import random
    import time

    # Passer l'orbe en état thinking immédiatement pour l'animer à l'écran
    send_web_broadcast_sync({"action": "set_state", "state": "thinking"})

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
    caracteres = "0123456789ABCDEFghijklmnopqrstuvwxyz[]{}()$#@!*&%^-_=+"

    print("\n\033[93m" + "="*60)
    print("   J.A.R.V.I.S — PLUGINS SYSTEM: COMPILING NEW SKILL")
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
            send_web_broadcast_sync({"action": "jarvis_text", "text": f"[HUD] {log_texte}"})
            
        iteration += 1
        time.sleep(0.04)

    print("\n\033[92m" + "="*60)
    print("   J.A.R.V.I.S — SKILL SUCCESSFULLY INTEGRATED")
    print("="*60 + "\033[0m\n")

    # Restaurer l'état d'origine de l'orbe et du texte
    send_web_broadcast_sync({"action": "set_state", "state": "idle"})
    send_web_broadcast_sync({"action": "jarvis_text", "text": "COMPILATION TERMINÉE — COMPÉTENCE CHARGÉE"})


def jarvis_creer_competence(nom_competence: str, description_demande: str) -> str:
    """
    Appelle Gemini-3.5-flash avec thinking activé pour générer une compétence Python autonome.
    Sauvegarde le code généré dans le dossier plugins/ sous competence_<nom>.py.
    """
    import re
    import threading
    import os
    import builtins
    from google.genai import types as _gtypes

    # Valider le client API
    if not hasattr(builtins, "client") or not builtins.client:
        return "Erreur : le client Gemini n'est pas initialisé ou la clé API est invalide."

    nom_formate = re.sub(r'[^a-zA-Z0-9_]', '', nom_competence.lower().replace(" ", "_"))
    dossier_plugins = os.path.join(_BASE_DIR, "plugins")
    if not os.path.exists(dossier_plugins):
        os.makedirs(dossier_plugins, exist_ok=True)
    
    filename = os.path.join(dossier_plugins, f"competence_{nom_formate}.py")

    # Animation Iron Man
    stop_event = threading.Event()
    thread_anim = threading.Thread(target=_effet_visuel_iron_man, args=(stop_event,), daemon=True)
    thread_anim.start()

    try:
        system_instruction = (
            "Tu es l'agent de génération de compétences autonomes de JARVIS.\n"
            "Tu dois écrire du code Python strict, propre et valide.\n\n"
            "RÈGLES CRITIQUES :\n"
            "1. Renvoie UNIQUEMENT le code Python pur. Ne mets AUCUNE balise de code markdown comme ```python ou ```. Pas de texte explicatif en dehors du code.\n"
            "2. Le script doit être entièrement autonome.\n"
            "3. Tu dois obligatoirement implémenter une fonction principale nommée `executer(texte_utilisateur=None)` qui prend un argument optionnel (string) et qui RETOURNE obligatoirement une string (le texte formaté que JARVIS lira à voix haute).\n"
            "4. Évite tout appel externe nécessitant des credentials non fournis (clés d'APIs tierces) à moins que ce ne soit faisable via des APIs publiques ou des mocks. Tu peux utiliser des bibliothèques standards ou requests."
        )

        prompt = (
            f"Génère le code complet pour la compétence : '{nom_competence}'.\n"
            f"Objectif de la compétence : {description_demande}\n\n"
            "Écris le code Python pur respectant toutes les règles de structure."
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
            return (f"J'ai refusé d'installer cette compétence, Mylane : le code généré "
                    f"n'a pas passé le contrôle de sûreté ({raison}).")

        # Écriture du fichier compétence
        with open(filename, "w", encoding="utf-8") as f:
            f.write(code_genere)

        stop_event.set()
        thread_anim.join()

        print(f"[JARVIS PLUGINS] Nouvelle compétence écrite dans {filename}")
        consigner("competence_creee", nom=nom_competence, description=description_demande, fichier=filename)
        return f"La compétence '{nom_competence}' a été générée et installée avec succès. Elle est prête à être exécutée."

    except Exception as e:
        stop_event.set()
        thread_anim.join()
        print(f"[JARVIS PLUGINS] Erreur lors de la création de compétence : {e}")
        consigner("competence_erreur_creation", nom=nom_competence, erreur=str(e))
        return f"Désolé Mylane, la génération de la compétence a échoué. Détail de l'erreur : {e}"


def jarvis_supprimer_competence(nom_competence: str) -> str:
    """Supprime proprement le fichier de compétence ciblée."""
    import re
    import os
    nom_formate = re.sub(r'[^a-zA-Z0-9_]', '', nom_competence.lower().replace(" ", "_"))
    filename = os.path.join(_BASE_DIR, "plugins", f"competence_{nom_formate}.py")

    if os.path.exists(filename):
        try:
            os.remove(filename)
            print(f"[JARVIS PLUGINS] Compétence supprimée : {filename}")
            consigner("competence_supprimee", nom=nom_competence, fichier=filename)
            return f"La compétence '{nom_competence}' a été désinstallée et son fichier a été supprimé."
        except Exception as e:
            return f"Erreur lors de la suppression du fichier : {e}"
    else:
        return f"La compétence '{nom_competence}' n'est pas installée."


def executer_competence_vocale(nom_competence: str, texte_recu: str = None) -> str:
    """Importe et exécute dynamiquement la compétence vocale."""
    import re
    import os
    import sys
    import importlib.util

    nom_formate = re.sub(r'[^a-zA-Z0-9_]', '', nom_competence.lower().replace(" ", "_"))
    filename = os.path.join(_BASE_DIR, "plugins", f"competence_{nom_formate}.py")

    if not os.path.exists(filename):
        return f"Désolé Mylane, la compétence '{nom_competence}' n'est pas disponible."

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
            return "Impossible de charger la spécification du module."

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        if hasattr(module, "executer"):
            res = module.executer(texte_recu)
            consigner("competence_executee", nom=nom_competence)
            return str(res)
        else:
            return "Erreur : cette compétence ne possède pas de point d'entrée 'executer'."

    except Exception as e:
        print(f"[JARVIS PLUGINS] Erreur lors de l'exécution de {nom_competence} : {e}")
        consigner("competence_erreur_execution", nom=nom_competence, erreur=str(e))
        return f"Erreur d'exécution dans la compétence '{nom_competence}' : {e}"


