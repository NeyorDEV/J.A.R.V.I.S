"""
webview_cache.py — Nettoyage du cache WebView2 (pywebview/EBWebView).

Purge automatique après changement de version et purge manuelle (bouton HUD).
Extrait de main2.py.
"""

import os

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── NETTOYAGE CACHE WEBVIEW (anti-cache après mise à jour) ─────────────────
def purger_cache_webview_si_mise_a_jour(CURRENT_VERSION):
    """
    Efface le cache WebView2 (EBWebView/Default/*) quand la version
    notée dans le fichier marqueur diffère de CURRENT_VERSION.
    L'interface est ainsi rechargée à neuf après une mise à jour.
    """
    import shutil
    app_dir = _BASE_DIR
    marker_file = os.path.join(app_dir, ".jarvis_cache_version")

    # Lire la version précédente
    version_en_cache = None
    try:
        if os.path.exists(marker_file):
            with open(marker_file, "r", encoding="utf-8") as f:
                version_en_cache = f.read().strip()
    except Exception:
        pass

    if version_en_cache == CURRENT_VERSION:
        # Même version → rien à faire
        return

    # Nouvelle version ou premier lancement → vider le cache WebView2
    print(f"[CACHE] Version changée ({version_en_cache} → {CURRENT_VERSION}) : cache WebView2 vidé...")
    # Libérer les verrous en fermant les processus WebView2 résiduels
    import subprocess
    try:
        subprocess.run(["taskkill", "/F", "/IM", "msedgewebview2.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    # Libérer les verrous en fermant les processus WebView2 résiduels
    import subprocess
    try:
        subprocess.run(["taskkill", "/F", "/IM", "msedgewebview2.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    # Le cache pywebview est dans %APPDATA%\pywebview\EBWebView\Default\
    appdata = os.environ.get("APPDATA", "")
    webview_data_dir = os.path.join(appdata, "pywebview", "EBWebView", "Default")

    # Sous-dossiers à supprimer (cache pur, pas les données utilisateur critiques)
    cache_folders = [
        "Cache",
        "Code Cache",
        "Service Worker",
        "GPUCache",
        "DawnGraphiteCache",
        "DawnWebGPUCache",
        "blob_storage",
        "Session Storage",
    ]

    if os.path.isdir(webview_data_dir):
        for folder in cache_folders:
            target = os.path.join(webview_data_dir, folder)
            if os.path.isdir(target):
                try:
                    shutil.rmtree(target)
                    print(f"[CACHE]   ✓ Supprimé : {folder}")
                except Exception as e:
                    print(f"[CACHE]   ✗ Erreur sur {folder} : {e}")
        print("[CACHE] Cache WebView2 vidé.")
    else:
        print("[CACHE] Pas de dossier WebView2 : sans doute un premier démarrage.")

    # Mettre à jour le marqueur de version
    try:
        with open(marker_file, "w", encoding="utf-8") as f:
            f.write(CURRENT_VERSION)
    except Exception as e:
        print(f"[CACHE] Marqueur de version non écrit : {e}")


def purger_cache_webview():
    """
    Vide le cache WebView2 (appelé manuellement via le bouton frontend).
    Sans tuer les processus actifs pour éviter tout écran noir ou crash de fenêtre.
    Retourne True si succès, False sinon.
    """
    import shutil
    appdata = os.environ.get("APPDATA", "")
    webview_data_dir = os.path.join(appdata, "pywebview", "EBWebView", "Default")
    cache_folders = [
        "Cache",
        "Code Cache",
        "Service Worker",
        "GPUCache",
        "DawnGraphiteCache",
        "DawnWebGPUCache",
        "blob_storage",
        "Session Storage",
    ]
    success = True
    if os.path.isdir(webview_data_dir):
        for folder in cache_folders:
            target = os.path.join(webview_data_dir, folder)
            if os.path.isdir(target):
                try:
                    shutil.rmtree(target)
                    print(f"[CACHE] Manuel — Supprimé : {folder}")
                except Exception as e:
                    print(f"[CACHE] Manuel — Erreur : {folder} : {e}")
                    success = False
    # Réinitialiser le marqueur pour forcer un rechargement au prochain lancement
    app_dir = _BASE_DIR
    marker_file = os.path.join(app_dir, ".jarvis_cache_version")
    try:
        if os.path.exists(marker_file):
            os.remove(marker_file)
    except Exception:
        pass
    return success

