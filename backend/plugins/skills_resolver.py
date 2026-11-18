"""Skills à script (module/skills.py) : « mes skills », « autorise le skill espace disque »,
« lance le skill espace disque », ou directement une phrase déclencheur du skill (« combien d'espace libre »)."""

import asyncio
import builtins
import re

from core.audit_log import consigner
from core.confirmation import demander_confirmation
from core.interlocuteur import nom_virgule
from module import skills

_RE_LISTE = re.compile(r"\b(mes|les|quels|quelles|liste|lister)\b.*\bskills?\b|\bskills?\b.*\b(disponibles|installes)\b")
_RE_APPROUVER = re.compile(r"\b(autorise|approuve|valide)\b.*\bskills?\b")
_RE_IMPORT = re.compile(r"\b(importe|installe|telecharge|ajoute)\b.*\bskill\b")
_RE_URL = re.compile(r"https?://\S+")
_RE_LANCER = re.compile(r"\b(lance|execute|utilise|demarre|active)\b.*\bskills?\b")


def _arguments(texte, nom):
    """Ce qui suit le nom du skill dans la phrase (« avec », « sur »… retirés)."""
    t = skills.normaliser(texte)
    n = skills.normaliser(nom)
    suite = t.split(n, 1)[1] if n in t else ""
    return re.sub(r"^(avec|sur|pour|de|du|a)\s+", "", suite.strip())


async def _lancer(nom, arguments):
    info = skills.lister()[nom]
    detail = f" avec « {arguments} »" if arguments else ""
    if not await demander_confirmation(None, f"Lancer le skill {nom}{detail} ? {info['description']}".strip()):
        consigner("skill_refuse", skill=nom)
        return f"C'est annulé{nom_virgule()}."
    ok, texte = await asyncio.to_thread(skills.executer, nom, arguments)
    consigner("skill_execute", skill=nom, ok=ok, arguments=arguments[:80])
    return texte if ok else f"Le skill {nom} a échoué : {texte}."


async def _importer(url):
    from module import skills_import
    try:
        skills_import.decouper_url(url)
    except ValueError as e:
        return f"{e}"
    if not await demander_confirmation(None, f"Télécharger le skill {url} depuis GitHub ? Il ne sera pas approuvé : il ne tournera qu'après relecture."):
        return f"Import annulé{nom_virgule()}."
    try:
        nom, fichiers, ignores, a_script = await asyncio.to_thread(
            skills_import.importer, url, skills.DOSSIER_SKILLS, skills_import.get_json_reseau, skills_import.get_texte_reseau)
    except Exception as e:
        consigner("skill_import_echec", url=url[:200], erreur=str(e)[:120])
        return f"Import impossible : {e}."
    consigner("skill_importe", skill=nom, url=url[:200], fichiers=len(fichiers), ignores=len(ignores))
    suite = "Relisez-le puis dites « autorise le skill " + nom.replace("-", " ") + " »." if a_script else "Il n'a pas de script à lancer : c'est une simple fiche d'instructions."
    return f"Skill {nom.replace('-', ' ')} importé, {len(fichiers)} fichiers, non approuvé. {suite}"


async def resoudre_skills(texte):
    t = skills.normaliser(texte)
    if not t:
        return None

    m_url = _RE_URL.search(texte)
    if _RE_IMPORT.search(t) and m_url:
        return await _importer(m_url.group(0).rstrip(".,;)"))

    if _RE_LISTE.search(t) and not skills.trouver_par_nom(t):
        dispo = skills.lister()
        if not dispo:
            return f"Aucun skill à script n'est installé{nom_virgule()}."
        morceaux = []
        for nom in dispo:
            statut = {"approuve": "", "modifie": " (modifié, à réapprouver)"}.get(skills.etat(nom), " (non approuvé)")
            morceaux.append(f"{nom.replace('-', ' ')}{statut}")
        return f"Vos skills : {', '.join(morceaux)}."

    if _RE_APPROUVER.search(t):
        nom = skills.trouver_par_nom(t)
        if not nom:
            return None
        if not await demander_confirmation(
                None, f"Approuver le skill {nom} ? Le script pourra s'exécuter sur ce PC. Ne confirmez que si vous l'avez relu."):
            return f"Approbation annulée{nom_virgule()}."
        empreinte = await asyncio.to_thread(skills.approuver, nom)
        consigner("skill_approuve", skill=nom, sha256=empreinte)
        return f"Le skill {nom.replace('-', ' ')} est approuvé{nom_virgule()}."

    if _RE_LANCER.search(t):
        nom = skills.trouver_par_nom(t)
        if not nom:
            return None
        return await _lancer(nom, _arguments(texte, nom))

    nom = skills.trouver_par_declencheur(t)
    if nom and skills.etat(nom) == "approuve":
        return await _lancer(nom, "")
    return None


builtins.resoudre_skills = resoudre_skills
