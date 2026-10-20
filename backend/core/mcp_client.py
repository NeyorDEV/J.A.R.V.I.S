"""mcp_client.py — Client MCP générique multi-serveurs.

Contrairement à ha_mcp_client.py (client dédié et autonome pour Home
Assistant, déjà en prod et volontairement non retouché ici pour ne rien
risquer sur un module qui fonctionne), ce module permet de brancher
N'IMPORTE QUEL serveur MCP juste en l'ajoutant à MCP_SERVERS — sans écrire
de nouveau fichier à chaque fois.

Le routage reprend le même principe que ha_mcp_client.executer_action_ha :
1. lister_outils(serveur) récupère les outils exposés (mis en cache).
2. executer_action_mcp(serveur, instruction) transmet l'instruction en langage
   naturel à Gemini avec ces outils comme function declarations ; Gemini
   choisit l'outil et ses paramètres, JARVIS l'exécute via la session MCP.

Pour ajouter un serveur : une entrée dans MCP_SERVERS (via _enregistrer),
rien d'autre à coder.
"""

import os
import builtins
from dataclasses import dataclass
from dotenv import load_dotenv
from core.interlocuteur import nom_virgule

_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(os.path.dirname(_dir))  # backend/core/ -> racine projet
load_dotenv(os.path.join(_root, ".env"), override=True)


@dataclass
class MCPServerConfig:
    name: str
    transport: str  # "sse" ou "http" (Streamable HTTP)
    url: str
    headers: dict


MCP_SERVERS: dict[str, MCPServerConfig] = {}


def _enregistrer(name: str, transport: str, url: str, headers: dict) -> None:
    if url:
        MCP_SERVERS[name] = MCPServerConfig(name=name, transport=transport, url=url, headers=headers)


# ── Serveurs configurés ────────────────────────────────────────────────────

GITHUB_MCP_TOKEN = os.getenv("GITHUB_MCP_TOKEN", "")
_enregistrer(
    "github",
    "http",
    "https://api.githubcopilot.com/mcp/",
    {"Authorization": f"Bearer {GITHUB_MCP_TOKEN}"} if GITHUB_MCP_TOKEN else {},
)


_outils_cache: dict[str, list] = {}


def serveur_configure(name: str) -> bool:
    server = MCP_SERVERS.get(name)
    return bool(server and server.url and (server.headers or server.transport == "sse"))


def _ouvrir_transport(server: MCPServerConfig):
    """Retourne le context manager de transport adapté (SSE ou Streamable HTTP)."""
    if server.transport == "sse":
        from mcp.client.sse import sse_client
        return sse_client(server.url, headers=server.headers)
    import httpx
    from mcp.client.streamable_http import streamable_http_client
    return streamable_http_client(server.url, http_client=httpx.AsyncClient(headers=server.headers))


async def lister_outils(server_name: str, force_refresh: bool = False) -> list:
    """Récupère (avec cache mémoire) la liste des outils exposés par un serveur MCP."""
    if server_name in _outils_cache and not force_refresh:
        return _outils_cache[server_name]
    server = MCP_SERVERS.get(server_name)
    if not server or not serveur_configure(server_name):
        return []
    try:
        from mcp import ClientSession

        async with _ouvrir_transport(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                resultat = await session.list_tools()
                outils = [
                    {
                        "name": t.name,
                        "description": t.description or "",
                        "parameters": (getattr(t, "input_schema", None) or getattr(t, "inputSchema", None)) or {"type": "object", "properties": {}},
                    }
                    for t in resultat.tools
                ]
        _outils_cache[server_name] = outils
        print(f"[MCP:{server_name}] {len(outils)} outils découverts.")
        return outils
    except Exception as e:
        print(f"[MCP:{server_name}] Erreur récupération des outils : {e}")
        return []


async def appeler_outil(server_name: str, nom_outil: str, arguments: dict) -> str:
    """Appelle un outil MCP et retourne le texte de sa réponse."""
    server = MCP_SERVERS.get(server_name)
    if not server or not serveur_configure(server_name):
        return f"Le serveur MCP '{server_name}' n'est pas configuré."
    try:
        from mcp import ClientSession

        async with _ouvrir_transport(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                resultat = await session.call_tool(nom_outil, arguments or {})
                morceaux = [getattr(bloc, "text", "") for bloc in (resultat.content or [])]
                morceaux = [m for m in morceaux if m]
                return "\n".join(morceaux) if morceaux else "Commande exécutée."
    except Exception as e:
        print(f"[MCP:{server_name}] Erreur appel outil '{nom_outil}' : {e}")
        return f"Une erreur est survenue lors de la communication avec {server_name}."


async def executer_action_mcp(server_name: str, instruction: str) -> str:
    """Traduit une instruction en langage naturel en appel à un outil MCP du serveur donné."""
    if not serveur_configure(server_name):
        return f"Le serveur MCP '{server_name}' n'est pas configuré{nom_virgule()}."

    outils = await lister_outils(server_name)
    if not outils:
        return f"Je n'arrive pas à contacter le serveur MCP '{server_name}' pour le moment."

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
            return f"Je n'ai pas compris quelle action effectuer sur {server_name}."

        appel = appels[0]
        print(f"[MCP:{server_name}] Outil choisi : {appel.name}({dict(appel.args or {})})")
        return await appeler_outil(server_name, appel.name, dict(appel.args or {}))
    except Exception as e:
        print(f"[MCP:{server_name}] Erreur routage instruction '{instruction}' : {e}")
        return f"Une erreur est survenue lors de l'exécution de la commande sur {server_name}."
