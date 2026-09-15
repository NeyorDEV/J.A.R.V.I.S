"""
Plugin Spatial Explorer — Backend WebSocket
Gère toutes les actions de l'explorateur de fichiers spatial 3D.
Réutilise les fonctions existantes de module/file_manager.py.
"""

import os
import json
import shutil
import builtins
from pathlib import Path

# Réutilisation des fonctions existantes du file_manager
from module.file_manager import (
    lister_dossier,
    ouvrir_fichier_ou_dossier,
    deplacer_fichier,
    resoudre_chemin,
    EXTENSIONS,
)

# ── Catégorisation des fichiers pour le rendu 3D ──────────────────────

# Mapping extension → type d'icône pour couleur/forme dans la scène 3D
_ICON_TYPES = {
    "image":    [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico", ".heic", ".tiff", ".tif"],
    "video":    [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"],
    "audio":    [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus"],
    "document": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".odt", ".rtf", ".csv", ".epub"],
    "code":     [".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".h", ".cs", ".php", ".json", ".xml",
                 ".yaml", ".yml", ".sh", ".bat", ".ps1", ".jsx", ".tsx", ".vue", ".go", ".rs", ".rb", ".md"],
    "archive":  [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"],
    "exe":      [".exe", ".msi", ".apk", ".dmg", ".deb"],
}

# Cache inversé : extension → type
_EXT_TO_TYPE = {}
for _type, _exts in _ICON_TYPES.items():
    for _ext in _exts:
        _EXT_TO_TYPE[_ext] = _type


def get_icon_type(filename: str) -> str:
    """Retourne le type d'icône 3D pour un fichier donné."""
    ext = Path(filename).suffix.lower()
    return _EXT_TO_TYPE.get(ext, "other")


def get_file_size_display(path: str) -> str:
    """Retourne la taille d'un fichier en format lisible."""
    try:
        size = os.path.getsize(path)
        if size < 1024:
            return f"{size} o"
        elif size < 1024 * 1024:
            return f"{size // 1024} Ko"
        elif size < 1024 * 1024 * 1024:
            return f"{size // (1024 * 1024)} Mo"
        else:
            return f"{round(size / (1024 * 1024 * 1024), 1)} Go"
    except Exception:
        return ""


def resolve_original_name(item) -> str:
    """
    Retourne le nom de base d'origine d'un élément de la Corbeille en préservant 
    correctement l'extension même si Windows la cache dans les API du Shell.
    """
    try:
        orig_path = item.original_filename()
        real_path = item.real_filename()
        name = os.path.basename(orig_path)
        
        _, real_ext = os.path.splitext(real_path)
        if real_ext and not name.lower().endswith(real_ext.lower()):
            name += real_ext
        return name
    except Exception:
        try:
            return os.path.basename(item.original_filename())
        except Exception:
            return "Fichier inconnu"


# ── Handlers d'actions WebSocket ──────────────────────────────────────

async def _handle_list(data: dict, websocket) -> None:
    """Liste le contenu d'un dossier et renvoie les métadonnées au client."""
    chemin = data.get("path", "")

    if chemin == "corbeille":
        items = []
        try:
            import winshell
            recycle_bin = winshell.recycle_bin()
            for item in recycle_bin:
                try:
                    real_path = item.real_filename()
                    name = resolve_original_name(item)
                    
                    is_dir = os.path.isdir(real_path)
                    if is_dir:
                        child_count = -1
                        try:
                            child_count = len(list(os.scandir(real_path)))
                        except Exception:
                            pass
                        items.append({
                            "name": name,
                            "type": "folder",
                            "path": real_path,
                            "children": child_count,
                        })
                    else:
                        items.append({
                            "name": name,
                            "type": "file",
                            "path": real_path,
                            "icon": get_icon_type(name),
                            "size": get_file_size_display(real_path),
                        })
                except Exception:
                    continue
        except Exception as e:
            print(f"[SPATIAL] Erreur d'accès à la corbeille: {e}")
            await websocket.send(json.dumps({
                "type": "spatial_result",
                "action": "list",
                "success": False,
                "error": f"Erreur d'accès à la corbeille : {e}"
            }))
            return

        await websocket.send(json.dumps({
            "type": "spatial_result",
            "action": "list",
            "success": True,
            "path": "corbeille",
            "parent": str(Path(os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"))),
            "folder_name": "Corbeille",
            "items": items,
        }))
        print(f"[SPATIAL] Liste de la corbeille envoyée ({len(items)} éléments)")
        return

    chemin_resolu = resoudre_chemin(chemin) if chemin else None

    # Fallback : Téléchargements par défaut
    if not chemin_resolu or not os.path.exists(chemin_resolu):
        chemin_resolu = os.path.join(os.environ.get("USERPROFILE", ""), "Downloads")
        # Variante française si le dossier anglais n'existe pas
        if not os.path.exists(chemin_resolu):
            chemin_resolu = os.path.join(os.environ.get("USERPROFILE", ""), "Téléchargements")

    if not os.path.exists(chemin_resolu):
        await websocket.send(json.dumps({
            "type": "spatial_result",
            "action": "list",
            "success": False,
            "error": f"Dossier introuvable : {chemin_resolu}"
        }))
        return

    items = []
    try:
        for entry in os.scandir(chemin_resolu):
            # Ignorer les fichiers/dossiers cachés et système
            if entry.name.startswith(".") or entry.name.startswith("$"):
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    # Compter les enfants pour donner une idée de la taille du dossier
                    child_count = 0
                    try:
                        child_count = len(list(os.scandir(entry.path)))
                    except (PermissionError, OSError):
                        child_count = -1  # Accès refusé
                    items.append({
                        "name": entry.name,
                        "type": "folder",
                        "path": entry.path,
                        "children": child_count,
                    })
                elif entry.is_file(follow_symlinks=False):
                    items.append({
                        "name": entry.name,
                        "type": "file",
                        "path": entry.path,
                        "icon": get_icon_type(entry.name),
                        "size": get_file_size_display(entry.path),
                    })
            except (PermissionError, OSError):
                continue  # Ignorer les éléments inaccessibles
    except PermissionError:
        await websocket.send(json.dumps({
            "type": "spatial_result",
            "action": "list",
            "success": False,
            "error": f"Accès refusé au dossier : {chemin_resolu}"
        }))
        return

    await websocket.send(json.dumps({
        "type": "spatial_result",
        "action": "list",
        "success": True,
        "path": chemin_resolu,
        "parent": str(Path(chemin_resolu).parent),
        "folder_name": os.path.basename(chemin_resolu),
        "items": items,
    }))
    print(f"[SPATIAL] Liste envoyée : {chemin_resolu} ({len(items)} éléments)")


async def _handle_open(data: dict, websocket) -> None:
    """Ouvre un fichier ou dossier avec l'application par défaut du système."""
    chemin = data.get("path", "")
    if not chemin:
        await websocket.send(json.dumps({
            "type": "spatial_result",
            "action": "open",
            "success": False,
            "error": "Chemin vide"
        }))
        return

    if chemin == "corbeille":
        from module.file_manager import ouvrir_dossier
        ok, msg = ouvrir_dossier("corbeille")
    else:
        if not os.path.exists(chemin):
            await websocket.send(json.dumps({
                "type": "spatial_result",
                "action": "open",
                "success": False,
                "error": f"Élément introuvable : {chemin}"
            }))
            return
        ok, msg = ouvrir_fichier_ou_dossier(chemin)

    await websocket.send(json.dumps({
        "type": "spatial_result",
        "action": "open",
        "success": ok,
        "message": msg,
        "path": chemin,
    }))
    if ok:
        print(f"[SPATIAL] Ouvert : {chemin}")


async def _handle_move(data: dict, websocket) -> None:
    """Déplace un fichier/dossier vers un dossier de destination."""
    source = data.get("source_path", "")
    dest_folder = data.get("dest_path", "")

    if not source or not os.path.exists(source):
        await websocket.send(json.dumps({
            "type": "spatial_result",
            "action": "move",
            "success": False,
            "error": f"Source introuvable : {source}"
        }))
        return

    if not dest_folder or not os.path.isdir(dest_folder):
        await websocket.send(json.dumps({
            "type": "spatial_result",
            "action": "move",
            "success": False,
            "error": f"Destination invalide : {dest_folder}"
        }))
        return

    try:
        nom = os.path.basename(source)
        # Si le fichier provient de la Corbeille ($Recycle.Bin), restaurer son nom d'origine avec l'extension correcte !
        if "$recycle.bin" in source.lower():
            try:
                import winshell
                for item in winshell.recycle_bin():
                    try:
                        if os.path.abspath(item.real_filename()) == os.path.abspath(source):
                            nom = resolve_original_name(item)
                            break
                    except Exception:
                        continue
            except Exception as re_err:
                print(f"[SPATIAL] Erreur lors de la résolution du nom d'origine depuis la Corbeille: {re_err}")

        dest_final = os.path.join(dest_folder, nom)

        # Si le fichier source est identique à la destination finale (même dossier), c'est un no-op
        if os.path.abspath(source) == os.path.abspath(dest_final):
            await websocket.send(json.dumps({
                "type": "spatial_result",
                "action": "move",
                "success": True,
                "message": f"{nom} est déjà dans ce dossier",
                "source": source,
                "dest": dest_final,
            }))
            return

        # Éviter l'écrasement avec un index de copie propre (ex: fichier (2).txt)
        if os.path.exists(dest_final):
            base, ext = os.path.splitext(nom)
            counter = 2
            while True:
                dest_final = os.path.join(dest_folder, f"{base} ({counter}){ext}")
                if not os.path.exists(dest_final):
                    break
                counter += 1

        shutil.move(source, dest_final)
        await websocket.send(json.dumps({
            "type": "spatial_result",
            "action": "move",
            "success": True,
            "message": f"{nom} déplacé dans {os.path.basename(dest_folder)}",
            "source": source,
            "dest": dest_final,
        }))
        print(f"[SPATIAL] Déplacé : {source} → {dest_final}")
    except Exception as e:
        await websocket.send(json.dumps({
            "type": "spatial_result",
            "action": "move",
            "success": False,
            "error": f"Erreur déplacement : {e}"
        }))


async def _handle_delete(data: dict, websocket) -> None:
    """Supprime un fichier ou dossier (envoi à la corbeille Windows si possible)."""
    chemin = data.get("path", "")
    if not chemin or not os.path.exists(chemin):
        await websocket.send(json.dumps({
            "type": "spatial_result",
            "action": "delete",
            "success": False,
            "error": f"Élément introuvable : {chemin}"
        }))
        return

    nom = os.path.basename(chemin)

    from core.confirmation import demander_confirmation
    if not await demander_confirmation(websocket, f"Supprimer {nom} ?"):
        await websocket.send(json.dumps({
            "type": "spatial_result",
            "action": "delete",
            "success": False,
            "cancelled": True,
            "error": "Suppression annulée."
        }))
        return

    try:
        # Tentative d'envoi à la corbeille Windows via send2trash
        try:
            from send2trash import send2trash
            send2trash(chemin)
            msg = f"{nom} envoyé à la corbeille"
        except ImportError:
            # Fallback : suppression définitive
            if os.path.isdir(chemin):
                shutil.rmtree(chemin)
            else:
                os.remove(chemin)
            msg = f"{nom} supprimé définitivement"

        await websocket.send(json.dumps({
            "type": "spatial_result",
            "action": "delete",
            "success": True,
            "message": msg,
            "path": chemin,
        }))
        print(f"[SPATIAL] Supprimé : {chemin}")
    except Exception as e:
        await websocket.send(json.dumps({
            "type": "spatial_result",
            "action": "delete",
            "success": False,
            "error": f"Erreur suppression : {e}"
        }))


# ── Dispatcher principal ──────────────────────────────────────────────

_ACTION_HANDLERS = {
    "list":   _handle_list,
    "open":   _handle_open,
    "move":   _handle_move,
    "delete": _handle_delete,
}


async def handle_spatial_ws(data: dict, websocket) -> None:
    """
    Point d'entrée unique appelé depuis main2.py ws_handler.
    Dispatch vers le bon handler selon data["action"].
    """
    action = data.get("action", "")
    handler = _ACTION_HANDLERS.get(action)

    if handler:
        try:
            await handler(data, websocket)
        except Exception as e:
            print(f"[SPATIAL] Erreur inattendue ({action}): {e}")
            try:
                await websocket.send(json.dumps({
                    "type": "spatial_result",
                    "action": action,
                    "success": False,
                    "error": str(e)
                }))
            except Exception:
                pass
    else:
        print(f"[SPATIAL] Action inconnue : {action}")
