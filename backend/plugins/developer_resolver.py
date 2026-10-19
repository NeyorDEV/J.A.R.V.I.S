import os
import sys
import subprocess
import importlib
import builtins
import json
import re
import asyncio
from google.genai import types
from core.config import CHOSEN_MODEL
from core.interlocuteur import nom_ou_utilisateur, nom_virgule

# Client Gemini différé (core/ai_clients.py) : pas de plantage à l'import sans clé,
# et une clé changée dans les Paramètres est prise en compte sans redémarrer.
from core.ai_clients import client_gemini as client

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

Voici la structure de ton projet pour t'orienter (chemins relatifs à la racine) :
- main.py : point d'entrée (ordre de démarrage). Ne le modifie pas pour ajouter une commande.
- backend/core/traitement.py : aiguillage des commandes (_ORDRE_RESOLVEURS).
- backend/core/chargement_plugins.py : liste _PLUGINS des plugins importés au démarrage.
- backend/core/speech.py : synthèse vocale (parler()).
- backend/core/interlocuteur.py : nom_espace(), nom_virgule(), nom_ou_utilisateur() pour s'adresser à la personne qui parle.
- backend/plugins/ : un resolver de commandes vocales par fichier (ex : recipe_resolver.py, tv_resolver.py, system_resolver.py, time_resolver.py).
- backend/module/ : services (alarmes, fichiers, mémoire, météo...).
- interfaces/frontend/index.html : structure HTML du HUD (widgets, panneaux).
- interfaces/frontend/src/ : TypeScript du HUD. main.ts n'orchestre que le démarrage ; les messages WebSocket sont traités dans src/ws/messages_*.ts, les panneaux dans src/panels/, l'état partagé dans src/hud/state.ts.
- interfaces/frontend/src/css/ : feuilles 01 à 12 (ordre de cascade important), widgets.css pour les widgets.

Tu dois renvoyer obligatoirement un OBJET JSON ayant ce schéma précis :
{
  "edits": [
    {
      "file_path": "chemin/relatif/depuis/la/racine.ts",
      "target_code": "code exact à remplacer, y compris l'indentation et les espaces",
      "replacement_code": "nouveau code complet à insérer"
    }
  ],
  "test_instructions": "Une phrase courte et naturelle en français expliquant comment l'utilisateur peut tester la fonctionnalité ajoutée ou modifiée. Exemple : 'Pour tester cette fonctionnalité, demandez-moi : \\"donne-moi la recette des crêpes\\".'"
}

Pour CRÉER un nouveau fichier (ex: backend/plugins/nouveau_resolver.py), mets "target_code" à "" (chaîne vide) et fournis le code complet dans "replacement_code".
Pour MODIFIER un fichier existant, fournis une portion de code existant extrêmement précise dans "target_code" afin qu'elle puisse être localisée de façon infaillible par un simple string.replace(). Évite de remplacer de trop grands blocs de code d'un coup.

Ne renvoie aucun texte explicatif en dehors du JSON. Sois extrêmement rigoureux sur la syntaxe TypeScript, CSS et Python.

---------------------------------------------------------
AJOUTER UNE COMMANDE VOCALE (nouveau resolver) :
1. Crée backend/plugins/<nom>_resolver.py sur le modèle ci-dessous : la fonction s'enregistre
   elle-même dans builtins. Elle est chargée à chaud dès que tes modifications sont validées
   et intégrée automatiquement à l'aiguillage (aucune modification de traitement.py n'est
   nécessaire).
2. Ajoute "plugins.<nom>_resolver" à la liste _PLUGINS de backend/core/chargement_plugins.py
   pour qu'il soit aussi chargé aux démarrages suivants.
3. Retourne None si la phrase ne concerne pas ton resolver ; compare des mots entiers
   (re.search(r"\\bmot\\b", t)) et non des sous-chaînes, pour ne pas intercepter d'autres commandes.

EXEMPLE DE STRUCTURE POUR UN NOUVEAU RESOLVER (backend/plugins/mon_resolver.py) :
---------------------------------------------
import builtins
import re
from core.interlocuteur import nom_virgule

def nettoyer_accent(texte):
    import unicodedata
    return "".join(c for c in unicodedata.normalize('NFD', texte) if unicodedata.category(c) != 'Mn')

async def resoudre_mon_resolver(cmd):
    t = nettoyer_accent(cmd.lower().strip())
    if not re.search(r"\\bmon mot cle\\b", t):
        return None
    return f"Voici la réponse{nom_virgule()}."

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
    # Tout backend/ (pas seulement plugins/ : l'IA peut aussi modifier core/ ou module/)
    import py_compile
    backend_dir = os.path.join(ROOT_DIR, "backend")
    for dossier, sous_dossiers, fichiers in os.walk(backend_dir):
        sous_dossiers[:] = [d for d in sous_dossiers if d not in ("sandbox", "__pycache__", "voiceprints")]
        for file in fichiers:
            if file.endswith(".py"):
                try:
                    py_compile.compile(os.path.join(dossier, file), doraise=True)
                except py_compile.PyCompileError as e:
                    return False, f"Erreur de syntaxe Python dans {os.path.relpath(os.path.join(dossier, file), ROOT_DIR)} :\n{e.msg}"
                
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
        # Modifier le code de JARVIS : réservé au créateur reconnu à la voix (ou au clavier
        # du HUD local), jamais à une voix invitée ni à un autre profil.
        from core.interlocuteur import CREATEUR
        if (getattr(builtins, "ACTIVE_SPEAKER", "guest") or "guest").lower() != CREATEUR:
            return f"Seul mon créateur peut modifier mon code{nom_virgule()}."
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
            "- Le HUD possède déjà la structure HTML '#recipe-modal' dans interfaces/frontend/index.html.\n"
            "- Le HUD possède déjà le style CSS pour le widget recette dans interfaces/frontend/src/css/01_base_hud.css.\n"
            "- Le HUD possède déjà le gestionnaire de messages 'show_recipe' dans interfaces/frontend/src/ws/messages_hud.ts qui attend un message WebSocket de type 'show_recipe' avec les champs 'recipe_title' (string), 'ingredients' (array of strings) et 'instructions' (array of strings).\n"
            "- Ainsi, pour la demande de widget de recette, TU NE DOIS PAS MODIFIER les fichiers frontend (index.html, main.ts, etc.). Il te suffit de créer le plugin Python backend 'backend/plugins/recipe_resolver.py' qui va capter la demande vocale, utiliser un appel LLM interne si nécessaire pour générer la recette demandée de manière structurée, puis renvoyer l'action WebSocket 'show_recipe' correspondante via le courtier d'actions génériques de main.py, et enfin importer et enregistrer ce resolver dans main.py."
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
                
                response = await asyncio.to_thread(
                    client.models.generate_content,
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
                
                if attempt == 0:
                    from core.confirmation import demander_confirmation
                    fichiers = sorted({str(e.get("file_path", "?")) for e in edits})
                    if not edits or not await demander_confirmation(
                            None, f"Je vais modifier {len(fichiers)} fichier{'s' if len(fichiers) > 1 else ''} : "
                                  f"{', '.join(fichiers[:4])}{'…' if len(fichiers) > 4 else ''}. J'applique ?"):
                        return f"Modifications annulées, aucun fichier n'a été touché{nom_virgule()}."
                print(f"[MUTATOR] Application des modifications (tentative {attempt+1})...")
                # On mémorise les fichiers touchés pour pouvoir les restaurer
                # individuellement en cas d'échec (annulation ciblée).
                _fichiers_touches = appliquer_edits(edits)
                
                # Validation par compilation
                valid, msg = await asyncio.to_thread(compiler_et_valider)
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
