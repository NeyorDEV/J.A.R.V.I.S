"""Import d'un skill au format ouvert (agentskills.io : un dossier avec SKILL.md, et souvent scripts/) depuis GitHub, sans jamais l'approuver.

Le skill arrive dans data/skills/<nom>/ en « non approuvé » : module/skills.py refuse de le lancer tant que l'utilisateur ne l'a pas relu et approuvé (empreinte SHA-256).
L'origine est notée dans data/skills/_origine.json (niveau « importé »). Seuls api.github.com et raw.githubusercontent.com sont contactés ; fichiers texte seulement, tailles bornées.
Si SKILL.md n'a pas de ligne `script:` et que scripts/ contient UN seul .py, la ligne est ajoutée à l'en-tête (JARVIS ne lance que ce qui la déclare) : à relire à l'approbation.
Pur sauf `importer` (réseau + disque) ; l'accès réseau est injecté pour les tests (tests/test_skills_import.py).
"""
import json
import os
import re
import time
from urllib.parse import urlparse

HOTES = ("api.github.com", "raw.githubusercontent.com")
EXT_OK = (".md", ".py", ".txt", ".json", ".yaml", ".yml", ".csv", ".toml")
MAX_FICHIERS, MAX_OCTETS_FICHIER, MAX_OCTETS_TOTAL = 40, 300_000, 2_000_000
_COMPOSANT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,80}$")
_NOM = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")


def decouper_url(url: str):
    """URL GitHub d'un dossier (…/tree/<branche>/<chemin>) -> (proprietaire, depot, branche, chemin) ; ValueError sinon."""
    u = urlparse(str(url or "").strip())
    p = [x for x in u.path.split("/") if x]
    if u.scheme != "https" or u.hostname != "github.com" or len(p) < 5 or p[2] != "tree":
        raise ValueError("URL attendue : https://github.com/<auteur>/<depot>/tree/<branche>/<dossier du skill>")
    chemin = "/".join(p[4:])
    if any(x in ("..", ".") for x in p[4:]):
        raise ValueError("chemin refusé")
    return p[0], p[1], p[3], chemin


def nom_sur(nom: str) -> str:
    """Nom de dossier du skill (minuscules, tirets) ; ValueError s'il n'est pas utilisable."""
    n = re.sub(r"[^a-z0-9_-]+", "-", str(nom or "").lower()).strip("-")
    if not _NOM.match(n):
        raise ValueError(f"nom de skill inutilisable : {nom!r}")
    return n


def _meta(texte: str) -> dict:
    lignes = texte.replace("\r\n", "\n").split("\n")
    meta = {}
    if lignes and lignes[0].strip() == "---":
        for l in lignes[1:]:
            if l.strip() == "---":
                break
            if ":" in l and not l.startswith((" ", "\t", "#")):
                k, _, v = l.partition(":")
                meta[k.strip().lower()] = v.strip().strip("\"'")
    return meta


def _ajouter_script(skill_md: str, script: str) -> str:
    t = skill_md.replace("\r\n", "\n")
    return t.replace("\n---", f"\nscript: {script}\n---", 1) if t.startswith("---") else t


def importer(url: str, dossier_skills: str, get_json, get_texte, deja=None):
    """Télécharge le skill. `get_json(url)` -> liste/dict ; `get_texte(url)` -> str (injectés). Rend (nom, fichiers_ecrits, ignores, a_script). ValueError si refusé."""
    proprio, depot, ref, chemin = decouper_url(url)
    fichiers, ignores, total = [], [], 0

    def parcourir(rel, profondeur):
        nonlocal total
        liste = get_json(f"https://api.github.com/repos/{proprio}/{depot}/contents/{chemin}{('/' + rel) if rel else ''}?ref={ref}")
        if not isinstance(liste, list):
            raise ValueError("dossier introuvable")
        for e in liste:
            nom, typ = str(e.get("name", "")), e.get("type")
            if not _COMPOSANT.match(nom):
                ignores.append(nom)
                continue
            sous = f"{rel}/{nom}" if rel else nom
            if typ == "dir" and profondeur < 2:
                parcourir(sous, profondeur + 1)
            elif typ == "file" and nom.lower().endswith(EXT_OK) and 0 < int(e.get("size", 0)) <= MAX_OCTETS_FICHIER and urlparse(str(e.get("download_url", ""))).hostname in HOTES:
                if len(fichiers) >= MAX_FICHIERS or total + e["size"] > MAX_OCTETS_TOTAL:
                    raise ValueError("skill trop gros")
                total += e["size"]
                fichiers.append((sous, e["download_url"]))
            else:
                ignores.append(sous)
    parcourir("", 0)
    contenus = {rel: get_texte(u) for rel, u in fichiers}
    if "SKILL.md" not in contenus:
        raise ValueError("pas de SKILL.md à la racine du dossier")
    meta = _meta(contenus["SKILL.md"])
    nom = nom_sur(meta.get("name") or chemin.rsplit("/", 1)[-1])
    cible = os.path.join(dossier_skills, nom)
    if os.path.exists(cible):
        raise ValueError(f"un skill « {nom} » existe déjà : rien n'est écrasé")
    a_script = bool(meta.get("script"))
    scripts = [r for r in contenus if r.startswith("scripts/") and r.count("/") == 1 and r.endswith(".py")]
    if not a_script and len(scripts) == 1:
        contenus["SKILL.md"] = _ajouter_script(contenus["SKILL.md"], scripts[0])
        a_script = True
    for rel, texte in contenus.items():
        dest = os.path.join(cible, *rel.split("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8", newline="\n") as f:
            f.write(texte)
    _noter_origine(dossier_skills, nom, url)
    return nom, sorted(contenus), ignores, a_script


def _noter_origine(dossier_skills: str, nom: str, url: str):
    fichier = os.path.join(dossier_skills, "_origine.json")
    try:
        with open(fichier, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    d[nom] = {"url": url, "niveau": "importe", "date": time.strftime("%Y-%m-%d %H:%M:%S")}
    tmp = fichier + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, fichier)


def get_json_reseau(url: str):
    import requests
    from core.injection import url_publique
    ok, raison = url_publique(url)
    if not ok or urlparse(url).hostname not in HOTES:
        raise ValueError(f"adresse refusée : {raison or url}")
    r = requests.get(url, timeout=15, headers={"Accept": "application/vnd.github+json"})
    r.raise_for_status()
    return r.json()


def get_texte_reseau(url: str) -> str:
    import requests
    from core.injection import url_publique
    ok, raison = url_publique(url)
    if not ok or urlparse(url).hostname not in HOTES:
        raise ValueError(f"adresse refusée : {raison or url}")
    r = requests.get(url, timeout=15, stream=True)
    r.raise_for_status()
    corps = r.raw.read(MAX_OCTETS_FICHIER + 1, decode_content=True)   # borné même si la taille annoncée ment
    if len(corps) > MAX_OCTETS_FICHIER:
        raise ValueError("fichier trop gros")
    return corps.decode("utf-8")
