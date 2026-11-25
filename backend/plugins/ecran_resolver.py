"""ecran_resolver.py — « explique-moi cette erreur », « résume cette page », « qu'est-ce que je regarde » : JARVIS lit la fenêtre active (module/ecran_contexte.py)."""
import builtins

from module import ecran_contexte as ec


async def resoudre_ecran(cmd: str):
    analyse = ec.analyser(ec.norm(cmd))
    if analyse is None:
        return None
    return await ec.comprendre(analyse, cmd.strip())


builtins.resoudre_ecran = resoudre_ecran
