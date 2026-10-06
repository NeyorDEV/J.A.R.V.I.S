import os
import asyncio
import builtins
from core.interlocuteur import nom_espace, nom_virgule

_attente_modif_image = {"actif": False, "chemin": None}

_MOTS_ANNULATION = ["annule", "laisse tomber", "rien finalement", "oublie ca", "oublie ça", "stop"]

_MOTS_MODIF_IMAGE = [
    "modifie une image", "modifie une photo", "modifie l'image", "modifie la photo",
    "modifie mon image", "modifie ma photo", "edite une image", "edite une photo",
    "edite l'image", "edite la photo", "retouche une image", "retouche une photo",
    "retouche l'image", "retouche la photo", "modifie une image de mon pc",
    "modifie une photo de mon pc", "change une image", "transforme une image",
    "transforme une photo",
]


def nettoyer_accent(texte):
    import unicodedata
    return "".join(c for c in unicodedata.normalize('NFD', texte) if unicodedata.category(c) != 'Mn')


def _choisir_fichier_image_dialog():
    """Ouvre l'explorateur de fichiers Windows pour sélectionner une image. Bloquant : appeler via asyncio.to_thread."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    chemin = filedialog.askopenfilename(
        title="Sélectionnez l'image à modifier",
        filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp *.gif"), ("Tous les fichiers", "*.*")]
    )
    root.destroy()
    return chemin or None


async def resoudre_modifier_image(cmd):
    """
    Détecte les demandes de modification d'une image locale : ouvre l'explorateur de
    fichiers pour la sélection, demande l'instruction de retouche, puis modifie l'image
    via l'IA d'édition d'image (Gemini).
    """
    t = nettoyer_accent(cmd.lower().strip())

    # ── Étape 2 : une image est déjà sélectionnée, cette phrase EST l'instruction ──
    if _attente_modif_image["actif"]:
        chemin = _attente_modif_image["chemin"]
        instruction = cmd.strip()

        if any(k in t for k in _MOTS_ANNULATION):
            _attente_modif_image["actif"] = False
            _attente_modif_image["chemin"] = None
            return f"Très bien, j'annule la modification{nom_virgule()}."

        _attente_modif_image["actif"] = False
        _attente_modif_image["chemin"] = None

        if not instruction:
            return f"Je n'ai pas compris quelle modification appliquer{nom_virgule()}."

        builtins.parler(f"Très bien{nom_espace()}, je modifie l'image. Un instant...")

        from module.image_generator import modifier_image_ia
        img_data = await asyncio.to_thread(modifier_image_ia, chemin, instruction)

        if img_data:
            await builtins.envoyer_image_web(img_data, instruction)
            return f"Voici l'image modifiée{nom_virgule()}. Elle s'affiche sur votre interface."
        return f"Désolé{nom_espace()}, je n'ai pas réussi à modifier cette image."

    # ── Étape 1 : détecter la demande et ouvrir l'explorateur de fichiers ──
    if not any(k in t for k in _MOTS_MODIF_IMAGE):
        return None

    chemin = await asyncio.to_thread(_choisir_fichier_image_dialog)
    if not chemin:
        return f"Aucune image sélectionnée{nom_virgule()}."

    _attente_modif_image["actif"] = True
    _attente_modif_image["chemin"] = chemin

    nom_fichier = os.path.basename(chemin)
    return f"J'ai sélectionné « {nom_fichier} »{nom_virgule()}. Quelle modification voulez-vous que je fasse dessus ?"


builtins.resoudre_modifier_image = resoudre_modifier_image
