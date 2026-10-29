---
name: gros-fichiers
description: Liste les 5 fichiers les plus volumineux d'un dossier (Téléchargements par défaut), lecture seule.
declencheurs: plus gros fichiers, fichiers les plus lourds, fichiers volumineux
script: scripts/gros.py
timeout: 30
---

# Gros fichiers

Parcourt le dossier Téléchargements (ou « bureau », « documents » si l'argument le dit), trie par taille
et annonce les cinq plus gros. Ne supprime ni ne déplace rien : c'est seulement un état des lieux.
