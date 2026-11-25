"""macros_resolver.py — « quand je dis mode cinéma, … », « mode cinéma », « teste à blanc mode cinéma » (module/macros.py)."""
import builtins

from module import macros


async def resoudre_macros(cmd: str):
    return await macros.resoudre_macros(cmd)


builtins.resoudre_macros = resoudre_macros
