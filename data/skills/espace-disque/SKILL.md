---
name: espace-disque
description: Dit l'espace libre sur chaque disque du PC (lecture seule).
declencheurs: espace disque, espace libre, place restante
script: scripts/espace.py
timeout: 10
---

# Espace disque

Parcourt les lettres de lecteur, lit l'espace total et libre (`shutil.disk_usage`) et le résume
en une phrase par disque. Ne modifie rien, n'utilise pas le réseau.
