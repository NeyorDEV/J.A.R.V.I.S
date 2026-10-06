import os
import sys
import subprocess
import importlib
import builtins
import json
import re
import asyncio
import google.genai as genai
from google.genai import types
from core.config import GEMINI_API_KEY, CHOSEN_MODEL
from core.interlocuteur import nom_ou_utilisateur, nom_virgule

# Initialisation du client de vision/génération Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

# Détermination du dossier racine de JARVIS de manière dynamique (compatible toutes installations)
_dir_courant = os.path.dirname(os.path.abspath(__file__))
# backend/plugins/ → racine du projet = 3 niveaux au-dessus. L'ancien calcul
# s'arrêtait à backend/, si bien que « frontend/ » et « main.py » étaient
# introuvables : toute tentative d'auto-édition du code échouait à chaque essai.
ROOT_DIR = os.path.dirname(os.path.dirname(_dir_courant))

def nettoyer_accent(texte):
    """Supprime les accents pour faciliter la comparaison."""
    import unicodedata
    return "".join(c for c in unicodedata.normalize('NFD', texte) if unicodedata.category(c) != 'Mn')

SYSTEM_INSTRUCTION = """
Tu es l'intelligence artificielle de JARVIS. Ton but est de modifier ou d'ajouter de nouvelles fonctionnalités à ta propre codebase à la demande de l'utilisateur.
Tu as un accès complet de lecture/écriture sur ton code source.

Voici la structure de ton projet pour t'orienter :
- main.py : Orchestrateur principal Python (gestion des resolvers de commandes et exécution)
- core/
  - brain.py : Client de génération Gemini/Groq
  - speech.py : Moteur de synthèse vocale (TTS)
- plugins/
  - dom_controller_resolver.py : Commandes vocales -> actions DOM/HUD
  - app_launcher_resolver.py : Lancement d'applications PC
  - system_resolver.py : Commandes volume, screenshot, processeur, batterie
  - time_resolver.py : Commandes heure et date
- frontend/
  - index.html : Structure HTML du HUD, widgets, orbe 3D
  - src/
    - main.ts : Orchestration du HUD, WebSocket, queue d'actions DOM
    - widgets.ts : Logique des widgets (Musique, Météo, Calendrier)
    - widgets.css : Style CSS des widgets (.hud-widget, .hud-revealed)
    - style.css : Styles néon Iron Man globaux du HUD

Tu dois renvoyer obligatoirement un OBJET JSON ayant ce schéma précis :
{
  "edits": [
    {
      "file_path": "chemin/relatif/depuis/racine.ts",
      "target_code": "code exact à remplacer, y compris l'indentation et les espaces",
      "replacement_code": "nouveau code complet à insérer"
    }
  ],
  "test_instructions": "Une phrase courte et naturelle en français expliquant comment l'utilisateur peut tester la fonctionnalité ajoutée ou modifiée. Exemple : 'Pour tester cette fonctionnalité, demandez-moi : \"donne-moi la recette des crêpes\".'"
}

Pour CRÉER un nouveau fichier (ex: plugins/nouveau_resolver.py), mets "target_code" à "" (chaîne vide) et fournis le code complet dans "replacement_code".
Pour MODIFIER un fichier existant, fournis une portion de code existant extrêmement précise dans "target_code" afin qu'elle puisse être localisée de façon infaillible par un simple string.replace(). Évite de remplacer de trop grands blocs de code d'un coup.

Ne renvoie aucun texte explicatif en dehors du JSON. Sois extrêmement rigoureux sur la syntaxe TypeScript, CSS et Python.

---------------------------------------------------------
CONSIGNES D'ÉDITIONS CRITIQUES POUR MAIN.PY :
Si tu dois importer et enregistrer un nouveau resolver (ex : plugins.recipe_resolver) dans main.py, voici les blocs EXACTS du fichier sur lesquels faire tes remplacements :

1. Bloc d'importation des resolvers dans main.py :
---------------------------------------------
import plugins.dom_controller_resolver
import plugins.developer_resolver
---------------------------------------------
Remplacement type pour ajouter ton import :
target_code: "import plugins.dom_controller_resolver\nimport plugins.developer_resolver"
replacement_code: "import plugins.dom_controller_resolver\nimport plugins.developer_resolver\nimport plugins.recipe_resolver"

2. Bloc de la chaîne de résolution locale dans traiter_reponse_ia (main.py) :
---------------------------------------------
        # TENTATIVE DE RÉSOLUTION LOCALE (Commandes, Math, Français, etc.)
        print(f"[DEBUG] Tentative de résolution locale pour : {texte_utilisateur}")
        reponse = await builtins.resoudre_developpement(texte_utilisateur)
        if not reponse: reponse = await builtins.resoudre_dom_hud(texte_utilisateur)
---------------------------------------------
Remplacement type pour ajouter l'appel à ton nouveau resolver :
target_code: "        reponse = await builtins.resoudre_developpement(texte_utilisateur)\n        if not reponse: reponse = await builtins.resoudre_dom_hud(texte_utilisateur)"
replacement_code: "        reponse = await builtins.resoudre_developpement(texte_utilisateur)\n        if not reponse: reponse = await builtins.resoudre_recipe(texte_utilisateur)\n        if not reponse: reponse = await builtins.resoudre_dom_hud(texte_utilisateur)"

---------------------------------------------------------
EXEMPLE DE STRUCTURE POUR UN NOUVEAU RESOLVER (plugins/mon_resolver.py) :
---------------------------------------------
import builtins
import json

def nettoyer_accent(texte):
    import unicodedata
    return "".join(c for c in unicodedata.normalize('NFD', texte) if unicodedata.category(c) != 'Mn')

async def resoudre_mon_resolver(cmd):
    t = nettoyer_accent(cmd.lower().strip())
    # Logique de commande ...
    return None

builtins.resoudre_mon_resolver = resoudre_mon_resolver
---------------------------------------------
"""

def _chemin_projet(file_path: str):
    """Résout file_path sous ROOT_DIR sans permettre d'en sortir.

    Les chemins proviennent d'un plan d'édition généré par le LLM : sans ce
    contrôle, « ../../AppData/.../Startup/x.bat » ou un chemin absolu
    permettaient d'écrire n'importe où sur la machine.
    """
    if not file_path or not isinstance(file_path, str):
        return None
    if os.path.isabs(file_path) or (len(file_path) > 1 and file_path[1] == ":"):
        return None
    try:
        cible = os.path.abspath(os.path.join(ROOT_DIR, file_path))
        if os.path.commonpath([cible, ROOT_DIR]) != ROOT_DIR:
            return None
        return cible
    except Exception:
        return None


# Dernier lot de fichiers modifiés, pour le rollback demandé à la voix
_DERNIERS_FICHIERS_MODIFIES = []


def appliquer_edits(edits):
    """Applique les modifications de code de façon sécurisée.

    Retourne la liste des chemins relatifs touchés, pour permettre une annulation
    ciblée en cas d'échec de validation (cf. _annuler_modifications).
    """
    global _DERNIERS_FICHIERS_MODIFIES
    touches = []
    for edit in edits:
        file_path = edit.get("file_path", "")
        target = edit.get("target_code", "")
        replacement = edit.get("replacement_code", "")

        path = _chemin_projet(file_path)
        if path is None:
            raise ValueError(f"Chemin refusé (hors projet) : {file_path!r}")
        touches.append(file_path)

        # 1. Création de fichier
        if target == "":
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(replacement)
            print(f"[MUTATOR] Nouveau fichier créé : {path}")
        # 2. Modification de fichier existant
        else:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Fichier introuvable pour modification : {file_path}")
                
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                
            if target not in content:
                # Essayer en retirant les espaces superflus en fin de ligne si le matching échoue
                target_clean = "\n".join(l.rstrip() for l in target.splitlines())
                content_clean = "\n".join(l.rstrip() for l in content.splitlines())
                if target_clean in content_clean:
                    content = content_clean
                    target = target_clean
                else:
                    raise ValueError(f"Le code cible n'a pas été trouvé dans {file_path}. Modification avortée.")
            
            new_content = content.replace(target, replacement, 1)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"[MUTATOR] Fichier modifié : {path}")
    _DERNIERS_FICHIERS_MODIFIES = list(touches)
    return touches


def _annuler_modifications(fichiers):
    """Annule UNIQUEMENT les fichiers que nous venons de toucher.

    Remplace l'ancien « git reset --hard HEAD » + « git clean -fd », qui
    détruisait l'intégralité du travail non commité de l'utilisateur (y compris
    les fichiers non suivis) à chaque échec de validation.
    """
    for rel in fichiers or []:
        chemin = _chemin_projet(rel)
        if chemin is None:
            continue
        suivi = subprocess.run(["git", "ls-files", "--error-unmatch", rel],
                               cwd=ROOT_DIR, capture_output=True)
        if suivi.returncode == 0:
            subprocess.run(["git", "checkout", "--", rel], cwd=ROOT_DIR, capture_output=True)
            print(f"[MUTATOR] Restauré depuis git : {rel}")
        else:
            # Fichier créé par nous et non suivi : on le retire
            try:
                if os.path.exists(chemin):
                    os.remove(chemin)
                    print(f"[MUTATOR] Fichier créé supprimé : {rel}")
            except Exception as e:
                print(f"[MUTATOR] Impossible de supprimer {rel} : {e}")


def compiler_et_valider():
    """Valide les modifications par compilation statique TypeScript et vérification Python."""
    # 1. Validation Frontend (TypeScript)
    print("[MUTATOR] Lancement de la validation statique TypeScript...")
    _dir_front = os.path.join(ROOT_DIR, "interfaces", "frontend")  # ex-« frontend/ » avant réorg
    if not os.path.isdir(_dir_front):
        return False, f"Dossier frontend introuvable : {_dir_front}"
    res_ts = subprocess.run("npx tsc --noEmit", shell=True, cwd=_dir_front, capture_output=True, text=True)
    if res_ts.returncode != 0:
        return False, f"TypeScript compilation error:\n{res_ts.stderr or res_ts.stdout}"
        
    # 2. Validation Backend (Python)
    print("[MUTATOR] Lancement de la validation des modules Python...")
    plugins_dir = os.path.join(ROOT_DIR, "backend", "plugins")  # ex-« plugins/ » avant réorg
    for file in os.listdir(plugins_dir):
        if file.endswith(".py"):
            res_py = subprocess.run([sys.executable, "-m", "py_compile", os.path.join(plugins_dir, file)], capture_output=True, text=True)
            if res_py.returncode != 0:
                return False, f"Erreur de syntaxe Python dans {file} :\n{res_py.stderr}"
                
    return True, "Validation réussie !"

def recharger_plugins_python():
    """Recharge dynamiquement à chaud tous les modules du package plugins et charge les nouveaux."""
    # 1. Scanner et importer les nouveaux modules plugins
    plugins_dir = os.path.join(ROOT_DIR, "backend", "plugins")  # ex-« plugins/ » avant réorg
    if os.path.exists(plugins_dir):
        for file in os.listdir(plugins_dir):
            if file.endswith(".py") and not file.startswith("__"):
                module_name = f"plugins.{file[:-3]}"
                if module_name not in sys.modules:
                    try:
                        importlib.import_module(module_name)
                        print(f"[MUTATOR] Nouveau module Python importé à chaud : {module_name}")
                    except Exception as e:
                        print(f"[MUTATOR] Échec de l'import à chaud de {module_name} : {e}")

    # 2. Recharger les modules déjà importés
    for name in list(sys.modules.keys()):
        if name.startswith("plugins."):
            try:
                importlib.reload(sys.modules[name])
                print(f"[MUTATOR] Module Python rechargé avec succès : {name}")
            except Exception as e:
                print(f"[MUTATOR] Échec du rechargement de {name} : {e}")

async def resoudre_developpement(cmd):
    """Résout les commandes d'auto-évolution et de restauration Git."""
    t = nettoyer_accent(cmd.lower().strip())
    
    # Nettoyage des variantes du mot-clé de réveil (VAD phonétique)
    t = re.sub(r'^(jarvis|jervis|jarvys|jervys|gervis)(,)?\s*', '', t)
    
    # 1. COMMANDES DE RESTAURATION / ROLLBACK GIT
    mots_cles_rollback = [
        "annule la derniere modification", "annule le dernier changement",
        "annule la modification", "annule le changement", "fais un rollback",
        "restaure le systeme", "restaure jarvis", "retour en arriere"
    ]
    if any(kw in t for kw in mots_cles_rollback):
        print("[MUTATOR] Déclenchement du protocole de rollback Git...")
        # Annulation CIBLÉE du dernier lot de fichiers modifiés par JARVIS.
        # (Avant : « git reset --hard » + « git clean -fd » sur tout le dépôt,
        #  ce qui détruisait aussi le travail non commité de l'utilisateur.)
        if not _DERNIERS_FICHIERS_MODIFIES:
            return (f"Je n'ai aucune modification récente à annuler{nom_virgule()}. "
                    "Je n'effectue plus de restauration globale du dépôt : "
                    "elle effacerait aussi vos propres changements non enregistrés.")
        _annuler_modifications(_DERNIERS_FICHIERS_MODIFIES)
        
        # Envoyer une carte visuelle au HUD
        if hasattr(builtins, "envoyer_carte_contextuelle"):
            await builtins.envoyer_carte_contextuelle(
                "Restauration",
                "Le protocole de rollback a été exécuté. La codebase a été restaurée dans son état stable précédent.",
                type_carte="system",
                icon="◈"
            )
            
        # Recharger les plugins au cas où
        recharger_plugins_python()
        
        return f"Très bien{nom_virgule()}. J'ai annulé les dernières modifications et j'ai restauré la codebase à son dernier état stable."

    # 2. COMMANDES DE MUTATION / DÉVELOPPEMENT
    mots_cles_mutation = [
        "modifie ton code", "modifie le code", "ajoute le widget", "ajoute un widget",
        "modifie le style", "ajoute un bouton", "cree un bouton", "cree le bouton",
        "ajoute une commande", "cree un resolver", "cree un nouveau resolver",
        "developpe une fonctionnalite", "developpe un nouveau widget",
        "ajoute un commentaire de test", "modifie l'orbe", "ajoute un effet",
        "ajoute-moi", "cree-moi", "crée-moi", "developpe-moi"
    ]
    # Les préfixes nus « ajoute … » / « cree … » ont été retirés : ils faisaient
    # entrer dans l'auto-modification du code des phrases du quotidien comme
    # « ajoute du lait a ma liste de courses » ou « cree une alarme a 8h », avec
    # à la clé un aller-retour LLM, des écritures de fichiers et une annulation
    # git. On exige maintenant une intention explicite (mots-clés ciblés, ou un
    # préfixe accompagné d'un terme du domaine technique).
    _termes_techniques = (
        "code", "widget", "bouton", "resolver", "plugin", "fonctionnalite",
        "orbe", "hud", "interface", "module", "script", "commande vocale",
        "effet", "animation", "style", "css", "page",
    )
    _prefixe_dev = (t.startswith("modifie ") or t.startswith("ajoute ")
                    or t.startswith("cree ") or t.startswith("developpe ")
                    or t.startswith("ajoute-moi ") or t.startswith("cree-moi "))
    is_mutation_req = (any(kw in t for kw in mots_cles_mutation)
                       or (_prefixe_dev and any(x in t for x in _termes_techniques)))
    
    if is_mutation_req:
        description = cmd
        print(f"[MUTATOR] Requête d'auto-évolution reçue : {description}")
        
        # A. Créer un point de sauvegarde Git de sécurité (sur les fichiers modifiés uniquement)
        print("[MUTATOR] Création du point de sauvegarde Git...")
        # On ne fait pas de commit pour éviter de polluer l'historique et risquer de reculer HEAD.
        # On fait juste un reset HEAD pour annuler les modifs en cours si nécessaire.
        # Le reset HEAD remettra le dépôt dans l'état exact du dernier commit stable.
        
        # B. Informer l'utilisateur
        builtins.parler(f"J'initialise les protocoles d'auto-évolution{nom_virgule()}. J'analyse le projet et je prépare les modifications de code...")
        
        # Fournir des informations de contexte supplémentaires sur la codebase
        contexte_codebase = (
            "\n\nNOTE DE CONTEXTE D'ARCHITECTURE :\n"
            "- Le HUD possède déjà la structure HTML '#recipe-modal' dans frontend/index.html.\n"
            "- Le HUD possède déjà le style CSS pour le widget recette dans frontend/src/style.css.\n"
            "- Le HUD possède déjà le gestionnaire de messages 'show_recipe' dans frontend/src/main.ts qui attend un message WebSocket de type 'show_recipe' avec les champs 'recipe_title' (string), 'ingredients' (array of strings) et 'instructions' (array of strings).\n"
            "- Ainsi, pour la demande de widget de recette, TU NE DOIS PAS MODIFIER les fichiers frontend (index.html, main.ts, etc.). Il te suffit de créer le plugin Python backend 'plugins/recipe_resolver.py' qui va capter la demande vocale, utiliser un appel LLM interne si nécessaire pour générer la recette demandée de manière structurée, puis renvoyer l'action WebSocket 'show_recipe' correspondante via le courtier d'actions génériques de main.py, et enfin importer et enregistrer ce resolver dans main.py."
        )
        prompt = f"{nom_ou_utilisateur()} demande la modification suivante :\n\"{description}\"\n{contexte_codebase}\n\nGénère le tableau JSON des modifications de code nécessaires."
        
        err_prev = ""
        edits = []
        test_instructions = ""
        success = False
        
        for attempt in range(3):
            try:
                # Si tentative ultérieure, inclure l'erreur de compilation pour correction
                if attempt > 0:
                    builtins.parler(f"La validation a échoué. Tentative d'auto-correction numéro {attempt}...")
                    prompt_actuel = (
                        f"Tu as précédemment généré ces modifications de code :\n"
                        f"{json.dumps(edits, indent=2)}\n\n"
                        f"Cependant, la compilation a échoué avec l'erreur suivante :\n"
                        f"\"{err_prev}\"\n\n"
                        f"Corrige ces erreurs et renvoie le nouvel objet JSON complet et corrigé."
                    )
                else:
                    prompt_actuel = prompt
                
                response = client.models.generate_content(
                    model=CHOSEN_MODEL,
                    contents=prompt_actuel,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        response_mime_type="application/json"
                    )
                )
                
                response_data = json.loads(response.text)
                if isinstance(response_data, list):
                    edits = response_data
                else:
                    edits = response_data.get("edits", [])
                    test_instructions = response_data.get("test_instructions", "")
                
                print(f"[MUTATOR] Application des modifications (tentative {attempt+1})...")
                # On mémorise les fichiers touchés pour pouvoir les restaurer
                # individuellement en cas d'échec (annulation ciblée).
                _fichiers_touches = appliquer_edits(edits)
                
                # Validation par compilation
                valid, msg = compiler_et_valider()
                if valid:
                    success = True
                    break
                else:
                    err_prev = msg
                    # Annuler les modifications incorrectes avant la prochaine tentative
                    # Annulation CIBLÉE : « git reset --hard » + « git clean -fd »
                    # effaçaient tout le travail non commité de l'utilisateur.
                    _annuler_modifications(locals().get("_fichiers_touches"))
                    
            except Exception as ex:
                err_prev = str(ex)
                # Annulation CIBLÉE : « git reset --hard » + « git clean -fd »
                # effaçaient tout le travail non commité de l'utilisateur.
                _annuler_modifications(locals().get("_fichiers_touches"))
                
        # D. Résultat final
        if success:
            # Recharger dynamiquement les resolvers Python
            recharger_plugins_python()
            
            # Envoyer une carte de succès au HUD
            if hasattr(builtins, "envoyer_carte_contextuelle"):
                mod_files = [e.get("file_path") for e in edits]
                await builtins.envoyer_carte_contextuelle(
                    "Évolution Réussie",
                    f"Code modifié avec succès :\n" + "\n".join(f"- {f}" for f in mod_files),
                    type_carte="info",
                    icon="◈"
                )
            
            test_msg = f" {test_instructions}" if test_instructions else ""
            return f"Les modifications ont été écrites, compilées avec succès, et injectées à chaud dans mes processeurs{nom_virgule()}. La nouvelle fonctionnalité est active.{test_msg}"
        else:
            # Restauration finale après échec de toutes les tentatives : on ne
            # restaure QUE les fichiers que nous avons touchés.
            _annuler_modifications(_DERNIERS_FICHIERS_MODIFIES)
            
            if hasattr(builtins, "envoyer_carte_contextuelle"):
                await builtins.envoyer_carte_contextuelle(
                    "Évolution Échouée",
                    f"La compilation a échoué. Le système a été restauré.\nErreur : {err_prev[:120]}...",
                    type_carte="alert",
                    icon="⚠"
                )
                
            return f"Je n'ai pas réussi à stabiliser le nouveau code après plusieurs tentatives d'auto-correction{nom_virgule()}. J'ai préféré annuler toutes les modifications et restaurer le système. L'erreur de compilation était : {err_prev}"

    return None

# Injection globale dans builtins
builtins.resoudre_developpement = resoudre_developpement
