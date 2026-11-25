"""Sauvegarde automatique des données de JARVIS (mémoire, alarmes, routines, macros) et restauration.

Une copie par jour dans data/sauvegardes/AAAA-MM-JJ/, faite au démarrage (les 14 plus récentes sont gardées).
Restauration (« restaure la sauvegarde d'hier ») : l'état actuel est d'abord copié dans data/sauvegardes/avant_restauration/, rien n'est perdu.
Pur sauf les chemins : testé dans tests/test_sauvegarde.py avec un dossier temporaire.
"""
import datetime
import os
import shutil

_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DATA = os.path.join(_RACINE, "data")
DOSSIER = os.path.join(_DATA, "sauvegardes")
FICHIERS = ("jarvis_memoire.json", "alarmes.json", "routines.json", "macros.json")
GARDER = 14
AVANT = "avant_restauration"


def _copier(source: str, cible: str) -> list:
    copies = []
    for nom in FICHIERS:
        chemin = os.path.join(source, nom)
        if os.path.isfile(chemin):
            os.makedirs(cible, exist_ok=True)   # dossier créé seulement s'il y a quelque chose à y mettre
            shutil.copy2(chemin, os.path.join(cible, nom))
            copies.append(nom)
    return copies


def sauvegarder(jour: datetime.date | None = None, forcer: bool = False) -> str | None:
    """Copie les fichiers de données dans data/sauvegardes/<jour>/. Renvoie le dossier, ou None si la copie du jour existe déjà (sauf forcer)."""
    cible = os.path.join(DOSSIER, (jour or datetime.date.today()).isoformat())
    if os.path.isdir(cible) and not forcer:
        return None
    if not _copier(_DATA, cible):
        return None
    _purger()
    return cible


def lister() -> list:
    """Jours sauvegardés, du plus récent au plus ancien (objets date)."""
    jours = []
    try:
        for nom in os.listdir(DOSSIER):
            try:
                jours.append(datetime.date.fromisoformat(nom))
            except ValueError:
                continue
    except OSError:
        pass
    return sorted(jours, reverse=True)


def _purger() -> None:
    for jour in lister()[GARDER:]:
        shutil.rmtree(os.path.join(DOSSIER, jour.isoformat()), ignore_errors=True)


def choisir(jour: datetime.date | None = None, avant: datetime.date | None = None):
    """Sauvegarde à restaurer : celle du jour demandé, sinon la plus récente antérieure à `avant` (« d'hier » = avant aujourd'hui), sinon la plus récente."""
    jours = lister()
    if jour:
        return jour if jour in jours else None
    if avant:
        jours = [j for j in jours if j < avant]
    return jours[0] if jours else None


def restaurer(jour: datetime.date) -> list:
    """Remet les fichiers du jour en place ; l'état actuel est gardé dans avant_restauration/. Renvoie les fichiers restaurés."""
    source = os.path.join(DOSSIER, jour.isoformat())
    if not os.path.isdir(source):
        return []
    _copier(_DATA, os.path.join(DOSSIER, AVANT))
    return _copier(source, _DATA)
