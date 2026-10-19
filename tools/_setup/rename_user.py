import sys
import os

def remplacer_prenom(nouveau_prenom):
    if not nouveau_prenom or nouveau_prenom.strip().lower() == "mickael":
        return
    prenom = nouveau_prenom.strip()
    prenom_lower = prenom.lower()

    fichiers = ["main.py"]
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    for nom_fichier in fichiers:
        chemin = os.path.join(base, nom_fichier)
        if not os.path.exists(chemin):
            continue
        try:
            with open(chemin, "r", encoding="utf-8") as f:
                contenu = f.read()
            contenu = contenu.replace("Mickael", prenom)
            contenu = contenu.replace("mickael", prenom_lower)
            with open(chemin, "w", encoding="utf-8") as f:
                f.write(contenu)
            print(f"[OK] {nom_fichier} personnalise pour {prenom}")
        except Exception as e:
            print(f"[ERREUR] {nom_fichier} : {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: rename_user.py <prenom>")
        sys.exit(1)
    remplacer_prenom(sys.argv[1])
