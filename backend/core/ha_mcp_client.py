"""
ha_mcp_client.py — Client MCP pour Home Assistant.

Remplace l'ancien système de domotique codé en dur (main.py avait un bloc de
~200 lignes avec un "elif action == ha_xxx" par type d'appareil, plus des
dictionnaires de correspondance "nom vocal" -> "entity_id" à maintenir à la
main dans meteo_domotique.py). Home Assistant expose nativement un serveur MCP
(intégration "Model Context Protocol Server") qui génère dynamiquement un
outil par entité exposée — plus besoin de coder chaque type d'appareil ni de
maintenir une liste d'entités : on ajoute/retire un appareil côté HA, JARVIS
le voit immédiatement.

Le routage se fait en deux temps :
1. lister_outils_ha() récupère la liste des outils MCP disponibls (mise en
   cache après le premier appel, rafraîchissable).
2. executer_action_ha(instruction) transmet l'instruction en langage naturel
   à Gemini avec ces outils comme function declarations ; Gemini choisit le
   bon outil et ses paramètres, JARVIS l'exécute via la session MCP.
"""

import os
import builtins
from dotenv import load_dotenv

_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(os.path.dirname(_dir))  # backend/core/ -> racine projet
load_dotenv(os.path.join(_root, ".env"), override=True)

HA_URL = os.getenv("HA_URL", "").rstrip("/")
HA_TOKEN = os.getenv("HA_TOKEN", "")
HA_MCP_SSE_URL = f"{HA_URL}/mcp_server/sse" if HA_URL else ""

_outils_cache: list | None = None


def ha_mcp_configure() -> bool:
    """Home Assistant est-il configuré (URL réelle + token) ?"""
    return bool(HA_URL) and "votre_ip_ha" not in HA_URL.lower() and bool(HA_TOKEN)


def _headers_auth() -> dict:
    return {"Authorization": f"Bearer {HA_TOKEN}"}


async def lister_outils_ha(force_refresh: bool = False) -> list:
    """Récupère (avec cache mémoire) la liste des outils exposés par le serveur MCP HA."""
    global _outils_cache
    if _outils_cache is not None and not force_refresh:
        return _outils_cache
    if not ha_mcp_configure():
        return []
    try:
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        async with sse_client(HA_MCP_SSE_URL, headers=_headers_auth()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                resultat = await session.list_tools()
                _outils_cache = [
                    {
                        "name": t.name,
                        "description": t.description or "",
                        "parameters": t.inputSchema or {"type": "object", "properties": {}},
                    }
                    for t in resultat.tools
                ]
        print(f"[HA MCP] {len(_outils_cache)} outils découverts sur Home Assistant.")
        return _outils_cache
    except Exception as e:
        print(f"[HA MCP] Erreur récupération des outils : {e}")
        return []


async def appeler_outil_ha(nom_outil: str, arguments: dict) -> str:
    """Appelle un outil MCP Home Assistant et retourne le texte de sa réponse."""
    if not ha_mcp_configure():
        return "Home Assistant n'est pas configuré."
    try:
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        async with sse_client(HA_MCP_SSE_URL, headers=_headers_auth()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                resultat = await session.call_tool(nom_outil, arguments or {})
                morceaux = [getattr(bloc, "text", "") for bloc in (resultat.content or [])]
                morceaux = [m for m in morceaux if m]
                return "\n".join(morceaux) if morceaux else "Commande exécutée."
    except Exception as e:
        print(f"[HA MCP] Erreur appel outil '{nom_outil}' : {e}")
        return f"Une erreur est survenue lors de la communication avec Home Assistant."


async def executer_action_ha(instruction: str) -> str:
    """Traduit une instruction en langage naturel en appel à un outil MCP Home Assistant."""
    if not ha_mcp_configure():
        return "Home Assistant n'est pas configuré, mylane."

    outils = await lister_outils_ha()
    if not outils:
        return "Je n'arrive pas à contacter Home Assistant pour le moment."

    try:
        from google.genai import types

        function_declarations = [
            {"name": o["name"], "description": o["description"], "parameters": o["parameters"]}
            for o in outils
        ]

        response = await builtins.client.aio.models.generate_content(
            model=getattr(builtins, "CHOSEN_MODEL", "gemini-2.5-flash"),
            contents=[instruction],
            config=types.GenerateContentConfig(
                tools=[types.Tool(function_declarations=function_declarations)],
                temperature=0.0,
            ),
        )
        appels = response.function_calls
        if not appels:
            return "Je n'ai pas compris quelle action domotique effectuer."

        appel = appels[0]
        print(f"[HA MCP] Outil choisi : {appel.name}({dict(appel.args or {})})")
        return await appeler_outil_ha(appel.name, dict(appel.args or {}))
    except Exception as e:
        print(f"[HA MCP] Erreur routage instruction '{instruction}' : {e}")
        return "Une erreur est survenue lors de l'exécution de la commande domotique."
