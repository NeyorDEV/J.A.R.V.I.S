"""
Test manuel ("fuzzy") du contrôleur Deezer.

Le fichier d'origine s'est retrouvé corrompu (contenu enregistré comme une
chaîne échappée tronquée, dupliquant en plus une ancienne version de
backend/controller/deezer_controller.py). Reconstruit ici pour importer et
exercer directement les fonctions réelles et à jour du contrôleur, plutôt
que de dupliquer leur code.

Nécessite Deezer installé et lancé (ou lançable). Menu interactif : à
utiliser pour vérifier à la main que chaque commande agit bien sur la
fenêtre Deezer, pas une suite d'assertions automatiques.
"""
import os
import sys
import asyncio

# Ajout du chemin du backend dans le sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from backend.controller.deezer_controller import (
    deezer_ouvrir,
    deezer_lecture_pause,
    deezer_suivant,
    deezer_precedent,
    deezer_stop,
    deezer_volume,
    deezer_rechercher,
    deezer_lancer_playlist,
    deezer_obtenir_titre_encours,
)

ACTIONS = {
    "1": ("Ouvrir Deezer",              lambda: deezer_ouvrir()),
    "2": ("Lecture / Pause",            lambda: deezer_lecture_pause()),
    "3": ("Piste suivante",             lambda: deezer_suivant()),
    "4": ("Piste précédente",           lambda: deezer_precedent()),
    "5": ("Stop",                       lambda: deezer_stop()),
    "6": ("Volume +",                   lambda: deezer_volume("up")),
    "7": ("Volume -",                   lambda: deezer_volume("down")),
    "8": ("Rechercher (saisie)",        None),  # géré à part : demande une saisie
    "9": ("Lancer la dernière playlist", lambda: deezer_lancer_playlist()),
    "0": ("Titre en cours",             lambda: asyncio.sleep(0, result=deezer_obtenir_titre_encours())),
}


async def menu():
    print("[TEST] Test manuel du contrôleur Deezer — Deezer doit être installé.")
    while True:
        print("\n--- Actions disponibles ---")
        for cle, (label, _) in ACTIONS.items():
            print(f"  {cle}. {label}")
        print("  q. Quitter")

        choix = input("\n[?] Action : ").strip().lower()
        if choix == "q":
            break

        if choix == "8":
            recherche = input("[?] Terme à rechercher : ").strip()
            if recherche:
                resultat = await deezer_rechercher(recherche)
                print(f"[RESULTAT] {resultat}")
            continue

        action = ACTIONS.get(choix)
        if not action:
            print("[!] Choix invalide.")
            continue

        label, fn = action
        print(f"[TEST] {label}...")
        try:
            resultat = await fn()
            print(f"[RESULTAT] {resultat}")
        except Exception as e:
            print(f"[ERREUR] {e}")

    print("[TEST] Terminé.")


if __name__ == "__main__":
    asyncio.run(menu())
