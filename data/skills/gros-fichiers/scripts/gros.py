"""Les 5 plus gros fichiers d'un dossier personnel. Lecture seule."""
import os
import sys
import unicodedata

CLES = {"bureau": "BUREAU", "documents": "DOCUMENTS", "telechargements": "TELECHARGEMENTS",
        "images": "IMAGES", "musique": "MUSIQUE", "videos": "VIDEOS"}


def sans_accent(texte):
    return "".join(c for c in unicodedata.normalize("NFD", texte.lower()) if unicodedata.category(c) != "Mn")


demande = sans_accent(os.environ.get("JARVIS_ARGUMENTS", ""))
cle = next((v for k, v in CLES.items() if k in demande), "TELECHARGEMENTS")
racine = os.environ.get(f"JARVIS_DOSSIER_{cle}")
if not racine or not os.path.isdir(racine):
    print("Je ne trouve pas ce dossier.")
    sys.exit(0)

fichiers = []
for dossier, _sous, noms in os.walk(racine):
    for nom in noms:
        chemin = os.path.join(dossier, nom)
        try:
            fichiers.append((os.path.getsize(chemin), nom))
        except OSError:
            pass
fichiers.sort(reverse=True)

if not fichiers:
    print("Ce dossier est vide.")
else:
    morceaux = []
    for taille, nom in fichiers[:5]:
        mo = taille / 1024 ** 2
        morceaux.append(f"{nom}, {mo / 1024:.1f} Go".replace(".", ",") if mo >= 1024 else f"{nom}, {mo:.0f} Mo")
    print("Les plus gros fichiers : " + " ; ".join(morceaux) + ".")
