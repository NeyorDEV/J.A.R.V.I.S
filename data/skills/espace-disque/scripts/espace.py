"""Espace libre par disque, en français, une phrase par lecteur. Lecture seule."""
import os
import shutil
import string


def go(octets):
    return f"{octets / 1024 ** 3:.0f}".replace(".", ",")


phrases = []
for lettre in string.ascii_uppercase:
    racine = f"{lettre}:\\"
    if not os.path.exists(racine):
        continue
    try:
        total, _utilise, libre = shutil.disk_usage(racine)
    except OSError:
        continue
    if total:
        phrases.append(f"Disque {lettre} : {go(libre)} Go libres sur {go(total)}")
print(". ".join(phrases) + "." if phrases else "Aucun disque lisible.")
