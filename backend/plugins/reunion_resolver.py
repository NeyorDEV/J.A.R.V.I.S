"""reunion_resolver.py — « démarre la réunion », « arrête la réunion », « résume la réunion », « mets les actions dans mes tâches » (module/reunion.py). Refusé à l'invité."""
import asyncio
import builtins
import re
import unicodedata

from core.interlocuteur import nom_virgule
from module import reunion

_DEBUT = re.compile(r"\b(?:demarre|commence|lance|ouvre|debute|start)\b.*\b(?:reunion|prise de notes|meeting)\b|\bprends? (?:des )?notes\b|\bprise de notes\b.*\b(?:demarre|lance)\b")
_FIN = re.compile(r"\b(?:arrete|termine|finis|cloture|stoppe|stop|fin de|end)\b.*\b(?:reunion|prise de notes|notes|meeting)\b|\bfin de la reunion\b")
_TITRE = re.compile(r"\b(?:reunion|meeting)\s+(?:(?:sur|avec|de|du|des|d'|pour)\s+|:\s*)(.+)$")


def _norm(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower().replace("’", "'")) if unicodedata.category(c) != "Mn")


def _dire(texte: str) -> None:
    f = getattr(builtins, "parler", None)
    if f:
        f(texte)


def _phrase_actions(cr: dict) -> str:
    actions = cr.get("actions") or []
    if not actions:
        return "Aucune action relevée."
    return f"{len(actions)} action{'s' if len(actions) > 1 else ''} : " + " ; ".join(f"{a['qui'] + ' doit ' if a['qui'] else ''}{a['quoi']}" + (f" ({a['echeance']})" if a['echeance'] else "") for a in actions[:6]) + "."


async def _clore_et_rediger(r: dict):
    cr = await reunion.rediger(r)
    r["compte_rendu"] = cr
    await asyncio.to_thread(reunion.sauver, r)
    return cr


async def resoudre_reunion(cmd: str):
    t = _norm(cmd.strip())
    if "reunion" not in t and "meeting" not in t and "notes" not in t and "compte rendu" not in t and "compte-rendu" not in t:
        return None
    if _FIN.search(t):
        if not reunion.en_cours():
            return f"Aucune réunion n'est en cours{nom_virgule()}."
        r = reunion.terminer()
        if not r["notes"]:
            return f"Réunion terminée{nom_virgule()}, mais je n'ai rien noté : personne n'a parlé près du micro."
        _dire(f"Je rédige le compte rendu{nom_virgule()}, un instant.")
        cr = await _clore_et_rediger(r)
        duree = reunion.duree_texte(r["duree_s"])
        if not cr:
            return f"Réunion terminée, {duree}, {len(r['notes'])} phrases notées. Je n'ai pas pu rédiger le compte rendu, la transcription est enregistrée dans data/reunions."
        return f"Réunion terminée, {duree}. {cr['resume']} {_phrase_actions(cr)} Le compte rendu est enregistré dans data/reunions."
    if _DEBUT.search(t):
        m = _TITRE.search(t)
        rid = reunion.demarrer(m.group(1).strip(" .") if m else "")
        if rid is None:
            return f"Une réunion est déjà en cours{nom_virgule()}."
        return (f"Prise de notes lancée{nom_virgule()}. J'écoute le micro et je note chaque phrase ; prévenez les participants que la conversation est transcrite. "
                "Je ne capte que ce que le micro entend. Dites « arrête la réunion » pour le compte rendu.")
    if re.search(r"\b(?:ou en est|depuis combien|statut|etat|est[- ]ce qu'il y a)\b.*\breunion\b", t):
        if not reunion.en_cours():
            return f"Aucune réunion en cours{nom_virgule()}."
        s = reunion.instantane()
        import time
        return f"Réunion en cours depuis {reunion.duree_texte(time.time() - s['debut'])}, {len(s['notes'])} phrases notées."
    if re.search(r"\b(?:mets?|ajoute|envoie|cree)\b.*\bactions?\b.*\b(?:taches|tasks|google)\b", t):
        return await _actions_vers_taches()
    if re.search(r"\b(?:resume|resumer|compte rendu|compte-rendu|actions?)\b", t) and re.search(r"\b(?:reunion|compte rendu|compte-rendu)\b", t):
        if reunion.en_cours():   # point d'étape sans fermer la réunion
            r = dict(reunion.instantane(), duree_s=0)
            if not r["notes"]:
                return f"Je n'ai encore rien noté{nom_virgule()}."
            cr = await reunion.rediger(r)
            return f"Point d'étape : {cr['resume']} {_phrase_actions(cr)}" if cr else f"Je n'ai pas pu résumer pour l'instant{nom_virgule()}."
        r = reunion.derniere()
        if not r:
            return f"Je n'ai aucune réunion enregistrée{nom_virgule()}."
        if not r.get("compte_rendu"):
            cr = await _clore_et_rediger(r)
            if not cr:
                return f"La dernière réunion n'a pas de compte rendu et je n'ai pas pu le rédiger{nom_virgule()}."
        cr = r["compte_rendu"]
        if re.search(r"\bactions?\b", t) and not re.search(r"\bresume", t):
            return _phrase_actions(cr)
        return f"{cr['resume']} {_phrase_actions(cr)}"
    return None


async def _actions_vers_taches():
    r = reunion.derniere()
    actions = ((r or {}).get("compte_rendu") or {}).get("actions") or []
    if not actions:
        return f"Je n'ai aucune action à ajouter{nom_virgule()}."
    from core.confirmation import demander_confirmation
    from module.briefing import _google_pret
    if not await asyncio.to_thread(_google_pret):
        return f"Je n'ai pas accès à Google Tasks sans connexion{nom_virgule()}."
    if not await demander_confirmation(None, f"Ajouter {len(actions)} action{'s' if len(actions) > 1 else ''} de la réunion dans Google Tasks ?"):
        return f"D'accord{nom_virgule()}, je n'ajoute rien."
    from module.google_services import creer_google_task
    faites = 0
    for a in actions[:10]:
        titre = (f"{a['qui']} : " if a["qui"] else "") + a["quoi"]
        await asyncio.to_thread(creer_google_task, titre, f"Réunion « {r.get('titre') or r['id']} »" + (f" - échéance : {a['echeance']}" if a["echeance"] else ""))
        faites += 1
    return f"{faites} tâche{'s' if faites > 1 else ''} ajoutée{'s' if faites > 1 else ''} dans Google Tasks{nom_virgule()}."


builtins.resoudre_reunion = resoudre_reunion
