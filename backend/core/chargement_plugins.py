"""Chargement en arrière-plan des plugins de résolution (gain de temps au démarrage)."""

import core.shared as shared


def _charger_plugins():
    import plugins.tv_resolver
    import plugins.local_resolver
    import plugins.system_resolver
    import plugins.extras
    import plugins.globe_resolver
    import plugins.memory_resolver
    import plugins.list_manager
    import plugins.time_resolver
    import plugins.app_launcher_resolver
    import plugins.dom_controller_resolver
    import plugins.developer_resolver
    import plugins.recipe_resolver
    import plugins.os_autopilot_resolver
    import plugins.local_mode_resolver
    import plugins.network_resolver
    import plugins.dev_swarm_resolver
    import plugins.image_search_resolver
    import plugins.uninstaller_resolver
    import plugins.website_resolver
    import plugins.image_edit_resolver
    import plugins.document_generator_resolver
    shared._plugins_prets.set()
