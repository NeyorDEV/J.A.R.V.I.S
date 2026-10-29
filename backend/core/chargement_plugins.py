"""Chargement en arrière-plan des plugins de résolution (gain de temps au démarrage)."""

import importlib

import core.shared as shared

# Ordre d'import d'origine conservé.
_PLUGINS = [
    "plugins.tv_resolver",
    "plugins.steam_resolver",
    "plugins.navigateur_resolver",
    "plugins.discord_resolver",
    "plugins.skills_resolver",
    "plugins.local_resolver",
    "plugins.system_resolver",
    "plugins.extras",
    "plugins.memory_resolver",
    "plugins.list_manager",
    "plugins.time_resolver",
    "plugins.app_launcher_resolver",
    "plugins.dom_controller_resolver",
    "plugins.developer_resolver",
    "plugins.recipe_resolver",
    "plugins.os_autopilot_resolver",
    "plugins.local_mode_resolver",
    "plugins.network_resolver",
    "plugins.dev_swarm_resolver",
    "plugins.image_search_resolver",
    "plugins.uninstaller_resolver",
    "plugins.website_resolver",
    "plugins.image_edit_resolver",
    "plugins.document_generator_resolver",
    "plugins.plugin_creator_resolver",   # n'était importé nulle part (« crée un plugin » ne faisait rien)
]


def _charger_plugins():
    # Chaque plugin est importé séparément : avant, une seule erreur d'import (par
    # exemple un client Gemini créé sans clé) arrêtait le thread et tous les plugins
    # suivants manquaient, sans le moindre message.
    try:
        for nom in _PLUGINS:
            try:
                importlib.import_module(nom)
            except Exception as e:
                print(f"[PLUGINS] ⚠ {nom} non chargé : {type(e).__name__} : {e}")
    finally:
        shared._plugins_prets.set()
