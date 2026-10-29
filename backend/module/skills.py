"""Skills à script : un dossier data/skills/<nom>/ avec un SKILL.md et un script (format SKILL.md ouvert).

SKILL.md commence par un en-tête simple (clé: valeur, une par ligne, entre deux lignes « --- ») :
    name: espace-disque
    description: Dit l'espace libre sur les disques.
    declencheurs: espace disque, place restante      (phrases qui lancent le skill, facultatif)
    script: scripts/espace.py                        (obligatoire : le skill ne fait rien sans)
    timeout: 15                                      (secondes, 60 au plus)

Sûreté, dans l'ordre :
  1. Un skill n'est lancé que s'il a été APPROUVÉ : on enregistre l'empreinte SHA-256 de tout le dossier
     (data/skills/_approbations.json). Le moindre fichier modifié ensuite = refus tant qu'on n'a pas réapprouvé.
  2. Confirmation voix + HUD avant chaque lancement, et chaque approbation / lancement est journalisé.
  3. Le script reçoit un environnement NETTOYÉ (aucune clé d'API de .env), tourne en mode isolé de Python (-I),
     dans un dossier de travail à part, avec un délai maximal et une sortie plafonnée.

⚠️ Ce n'est PAS une isolation : le script tourne avec les droits de l'utilisateur (fichiers, réseau).
La vraie protection est la relecture avant approbation. N'approuvez que du code que vous avez lu.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata

import core.shared as shared

DOSSIER_SKILLS = os.path.join(shared.RACINE_PROJET, "data", "skills")
_FICHIER_APPROBATIONS = os.path.join(DOSSIER_SKILLS, "_approbations.json")
_DOSSIER_TRAVAIL = os.path.join(shared.RACINE_PROJET, "backend", "sandbox", "skills")
_TIMEOUT_MAX = 60
_SORTIE_MAX = 3000
_NOM_VALIDE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")


def normaliser(texte):
    sans_accent = "".join(c for c in unicodedata.normalize("NFD", str(texte).lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", sans_accent)).strip()


def _lire_entete(chemin):
    """Dictionnaire de l'en-tête de SKILL.md, ou None si le fichier n'a pas d'en-tête lisible."""
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            lignes = f.read().replace("\r\n", "\n").split("\n")
    except Exception:
        return None
    if not lignes or lignes[0].strip() != "---":
        return None
    meta = {}
    for ligne in lignes[1:]:
        if ligne.strip() == "---":
            return meta
        if ":" in ligne and not ligne.startswith((" ", "\t", "#")):
            cle, _, valeur = ligne.partition(":")
            meta[cle.strip().lower()] = valeur.strip().strip("\"'")
    return None


def lister():
    """Les skills trouvés : {nom: {description, declencheurs, script, timeout, dossier}}. Les skills sans script
    ou au nom invalide sont ignorés (les skills « instructions seules » ne sont pas gérés ici)."""
    skills = {}
    if not os.path.isdir(DOSSIER_SKILLS):
        return skills
    for entree in sorted(os.listdir(DOSSIER_SKILLS)):
        dossier = os.path.join(DOSSIER_SKILLS, entree)
        meta = _lire_entete(os.path.join(dossier, "SKILL.md")) if os.path.isdir(dossier) else None
        if not meta or not meta.get("script"):
            continue
        nom = meta.get("name", entree).strip().lower()
        if not _NOM_VALIDE.match(nom) or nom != entree.lower():
            continue  # le nom doit être celui du dossier (pas de confusion entre skills)
        try:
            delai = max(1, min(int(meta.get("timeout", "15")), _TIMEOUT_MAX))
        except ValueError:
            delai = 15
        skills[nom] = {
            "description": meta.get("description", ""),
            "declencheurs": [normaliser(d) for d in meta.get("declencheurs", "").split(",") if normaliser(d)],
            "script": meta["script"],
            "timeout": delai,
            "dossier": dossier,
        }
    return skills


def _script_sur(skill):
    """Chemin absolu du script, ou None s'il sort du dossier du skill ou n'est pas un .py existant."""
    racine = os.path.realpath(skill["dossier"])
    chemin = os.path.realpath(os.path.join(racine, skill["script"]))
    try:
        if os.path.commonpath([chemin, racine]) != racine:
            return None
    except ValueError:
        return None
    return chemin if chemin.endswith(".py") and os.path.isfile(chemin) else None


def empreinte(dossier):
    """SHA-256 de tout le contenu du dossier du skill (chemins relatifs + octets)."""
    h = hashlib.sha256()
    for racine, sous_dossiers, fichiers in os.walk(dossier):
        sous_dossiers[:] = sorted(d for d in sous_dossiers if d != "__pycache__")
        for f in sorted(fichiers):
            chemin = os.path.join(racine, f)
            h.update(os.path.relpath(chemin, dossier).replace("\\", "/").encode("utf-8") + b"\0")
            with open(chemin, "rb") as fh:
                h.update(fh.read())
            h.update(b"\0")
    return h.hexdigest()


def _approbations():
    try:
        with open(_FICHIER_APPROBATIONS, "r", encoding="utf-8") as f:
            donnees = json.load(f)
        return donnees if isinstance(donnees, dict) else {}
    except Exception:
        return {}


def approuver(nom):
    """Enregistre l'empreinte actuelle du skill. Retourne l'empreinte."""
    skills = lister()
    if nom not in skills:
        raise KeyError(nom)
    valeur = empreinte(skills[nom]["dossier"])
    donnees = _approbations()
    donnees[nom] = {"sha256": valeur, "date": time.strftime("%Y-%m-%d %H:%M:%S")}
    with open(_FICHIER_APPROBATIONS, "w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=2)
    return valeur


def etat(nom):
    """« approuve », « modifie » (changé depuis l'approbation) ou « non_approuve »."""
    skills = lister()
    if nom not in skills:
        return "inconnu"
    enregistre = _approbations().get(nom)
    if not isinstance(enregistre, dict) or not enregistre.get("sha256"):
        return "non_approuve"
    return "approuve" if enregistre["sha256"] == empreinte(skills[nom]["dossier"]) else "modifie"


def trouver_par_nom(texte):
    """Nom du skill dont le nom (tirets = espaces) apparaît dans la phrase, le plus long d'abord."""
    t = f" {normaliser(texte)} "
    for nom in sorted(lister(), key=len, reverse=True):
        if f" {normaliser(nom)} " in t:
            return nom
    return None


def trouver_par_declencheur(texte):
    t = f" {normaliser(texte)} "
    for nom, info in lister().items():
        if any(f" {d} " in t for d in info["declencheurs"]):
            return nom
    return None


def _environnement(arguments):
    """Environnement minimal : rien de .env (clés d'API) n'est transmis."""
    from core import dossiers
    env = {k: os.environ[k] for k in ("SystemRoot", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "PATH")
           if k in os.environ}
    for cle, nom in (("BUREAU", "bureau"), ("DOCUMENTS", "documents"), ("TELECHARGEMENTS", "telechargements"),
                     ("IMAGES", "images"), ("MUSIQUE", "musique"), ("VIDEOS", "videos")):
        chemin = dossiers.dossier_connu(nom)
        if chemin:
            env[f"JARVIS_DOSSIER_{cle}"] = chemin
    env["JARVIS_ARGUMENTS"] = arguments or ""
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def executer(nom, arguments=""):
    """Lance le skill approuvé (bloquant : à appeler dans un thread). Retourne (ok, texte)."""
    skills = lister()
    if nom not in skills:
        return False, "skill inconnu"
    situation = etat(nom)
    if situation == "non_approuve":
        return False, "ce skill n'a pas été approuvé"
    if situation == "modifie":
        return False, "ce skill a été modifié depuis son approbation"
    script = _script_sur(skills[nom])
    if not script:
        return False, "script introuvable ou hors du dossier du skill"
    python = os.path.join(shared.RACINE_PROJET, "venv", "Scripts", "python.exe")
    if not os.path.exists(python):
        python = sys.executable
    travail = os.path.join(_DOSSIER_TRAVAIL, nom)
    os.makedirs(travail, exist_ok=True)
    try:
        r = subprocess.run([python, "-I", script, *([arguments] if arguments else [])], cwd=travail,
                           env=_environnement(arguments), capture_output=True, timeout=skills[nom]["timeout"],
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return False, f"délai dépassé ({skills[nom]['timeout']} s), script interrompu"
    except Exception as e:
        return False, f"lancement impossible ({type(e).__name__})"
    sortie = r.stdout.decode("utf-8", errors="replace").strip()[:_SORTIE_MAX]
    if r.returncode != 0:
        erreur = r.stderr.decode("utf-8", errors="replace").strip().splitlines()
        return False, (erreur[-1][:200] if erreur else f"code de sortie {r.returncode}")
    return True, sortie or "terminé, sans message"
