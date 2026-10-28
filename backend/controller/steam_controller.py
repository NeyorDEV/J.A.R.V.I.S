"""Steam : liste des jeux installés (lecture seule des fichiers de Steam) et lancement par le lien officiel.

Rien n'est piloté dans l'interface de Steam (c'est une page web sans accessibilité exploitable) :
- les jeux viennent des fichiers « appmanifest_<id>.acf » de chaque bibliothèque
  (dossier steamapps, déclaré dans libraryfolders.vdf) ;
- un jeu se lance par « steam://rungameid/<id> » (Steam démarre au besoin) ;
- la bibliothèque et la boutique s'ouvrent par « steam://nav/games » et « steam://store ».
"""

import difflib
import os
import re
import time
import unicodedata

# Éléments installés par Steam qui ne sont pas des jeux
_NON_JEUX = ("steamworks common redistributables", "steam linux runtime", "proton ", "proton-", "steam controller",
             "steamvr", "wallpaper engine runtime")
_CACHE = {"quand": 0.0, "jeux": {}}
_DUREE_CACHE = 60.0


def normaliser(texte):
    """Minuscule, sans accents ni symboles (™ ® : - …), espaces simples : « Counter-Strike 2 » -> « counter strike 2 »."""
    sans_accent = "".join(c for c in unicodedata.normalize("NFD", str(texte).lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", sans_accent)).strip()


def dossier_steam():
    """Dossier d'installation de Steam (registre, sinon Program Files), ou None."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as cle:
            chemin = os.path.normpath(winreg.QueryValueEx(cle, "SteamPath")[0])
            if os.path.isdir(chemin):
                return chemin
    except Exception:
        pass
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base and os.path.isdir(os.path.join(base, "Steam")):
            return os.path.join(base, "Steam")
    return None


def bibliotheques(steam):
    """Dossiers steamapps de toutes les bibliothèques (principale + disques supplémentaires)."""
    dossiers = [os.path.join(steam, "steamapps")]
    try:
        with open(os.path.join(steam, "steamapps", "libraryfolders.vdf"), encoding="utf-8", errors="ignore") as f:
            for chemin in re.findall(r'"path"\s+"([^"]+)"', f.read()):
                dossier = os.path.join(chemin.replace("\\\\", "\\"), "steamapps")
                if dossier not in dossiers:
                    dossiers.append(dossier)
    except OSError:
        pass
    return [d for d in dossiers if os.path.isdir(d)]


def jeux_installes(force=False):
    """{identifiant: nom} des jeux installés (lu au plus une fois par minute)."""
    if not force and time.time() - _CACHE["quand"] < _DUREE_CACHE and _CACHE["jeux"]:
        return _CACHE["jeux"]
    jeux = {}
    steam = dossier_steam()
    for dossier in bibliotheques(steam) if steam else []:
        try:
            fichiers = os.listdir(dossier)
        except OSError:
            continue
        for nom_fichier in fichiers:
            if not (nom_fichier.startswith("appmanifest_") and nom_fichier.endswith(".acf")):
                continue
            try:
                with open(os.path.join(dossier, nom_fichier), encoding="utf-8", errors="ignore") as f:
                    texte = f.read()
                appid = re.search(r'"appid"\s+"(\d+)"', texte)
                nom = re.search(r'"name"\s+"([^"]+)"', texte)
                if appid and nom and not any(mot in nom.group(1).lower() for mot in _NON_JEUX):
                    jeux[appid.group(1)] = nom.group(1)
            except OSError:
                continue
    _CACHE.update(quand=time.time(), jeux=jeux)
    return jeux


def trouver_jeu(requete):
    """Cherche un jeu à partir de ce qui a été dit (la reconnaissance vocale écorche souvent les titres).

    Retourne (état, données) :
      ("ok", (appid, nom, score))  un jeu clairement identifié
      ("ambigu", [noms])           plusieurs jeux aussi proches : il faut préciser
      ("inconnu", None)            rien de ressemblant
    """
    q = normaliser(requete)
    if len(q) < 2:
        return "inconnu", None
    notes = []
    mots_q = set(q.split())
    for appid, nom in jeux_installes().items():
        n = normaliser(nom)
        if not n:
            continue
        if q == n:
            score = 1.0
        elif q in n or n in q:
            score = 0.9 - min(0.1, abs(len(n) - len(q)) / 200)  # le plus proche en longueur d'abord
        elif mots_q and mots_q <= set(n.split()):
            score = 0.85
        else:
            score = difflib.SequenceMatcher(None, q, n).ratio()
        notes.append((score, appid, nom))
    notes.sort(reverse=True)
    if not notes or notes[0][0] < 0.72:
        return "inconnu", None
    meilleur = notes[0]
    proches = [n for n in notes if n[0] >= meilleur[0] - 0.03 and n[0] < 1.0]
    if meilleur[0] < 1.0 and len(proches) > 1:
        return "ambigu", [n[2] for n in proches[:4]]
    return "ok", (meilleur[1], meilleur[2], meilleur[0])


def lancer_jeu(appid):
    os.startfile(f"steam://rungameid/{appid}")


def ouvrir(page):
    """« bibliotheque » ou « boutique » dans Steam."""
    os.startfile("steam://nav/games" if page == "bibliotheque" else "steam://store")
