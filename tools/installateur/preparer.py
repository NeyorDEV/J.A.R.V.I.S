"""Prépare le dossier à empaqueter dans l'installateur (build/stage) : uniquement les fichiers suivis
par Git (aucune donnée personnelle : .env, clés, empreintes vocales, mémoire, venv) et l'interface
déjà construite (dist/). Lancer depuis la racine du projet :

    venv\\Scripts\\python.exe tools\\installateur\\preparer.py [--sans-front]

Puis compiler tools\\installateur\\JARVIS.iss avec Inno Setup (voir construire.bat).
"""
import os
import re
import shutil
import subprocess
import sys

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STAGE = os.path.join(RACINE, "tools", "installateur", "build", "stage")
FRONT = os.path.join(RACINE, "interfaces", "frontend")

# Fichiers suivis par Git qui ne servent pas à une version installée
CRLF, LF = bytes([13, 10]), bytes([10])
EXCLUS = ("tools/tests/", "tools/sandbox/", "tools/git-hooks/", "tools/installateur/", ".github/",
          "interfaces/frontend/", "interfaces/chrome_extension/", "CLAUDE.md", "install.bat", ".gitignore")


def version():
    with open(os.path.join(RACINE, "backend", "core", "config.py"), encoding="utf-8") as f:
        return re.search(r'CURRENT_VERSION\s*=\s*"([^"]+)"', f.read()).group(1)


def main():
    sans_front = "--sans-front" in sys.argv
    if not sans_front:
        print("[1/3] Construction de l'interface (npm run build)...")
        subprocess.run("npm run build", cwd=FRONT, shell=True, check=True)
    if not os.path.isfile(os.path.join(FRONT, "dist", "index.html")):
        sys.exit("dist/index.html introuvable : construisez l'interface d'abord.")

    print("[2/3] Copie des fichiers suivis par Git...")
    if os.path.isdir(STAGE):
        shutil.rmtree(STAGE)
    os.makedirs(STAGE)
    fichiers = subprocess.run(["git", "ls-files", "-z"], cwd=RACINE, capture_output=True, check=True).stdout.decode("utf-8").split("\0")
    n = 0
    for rel in filter(None, fichiers):
        if rel.startswith(EXCLUS) or rel in EXCLUS:
            continue
        src = os.path.join(RACINE, rel)
        if not os.path.isfile(src):
            continue
        dst = os.path.join(STAGE, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        if rel.endswith(".bat"):  # cmd exige des fins de ligne CRLF (blocs et étiquettes mal lus avec LF seul)
            with open(dst, "rb") as f:
                brut = f.read().replace(CRLF, LF).replace(LF, CRLF)
            with open(dst, "wb") as f:
                f.write(brut)
        n += 1
    print(f"      {n} fichiers")

    print("[3/3] Interface construite (dist/)...")
    shutil.copytree(os.path.join(FRONT, "dist"), os.path.join(STAGE, "interfaces", "frontend", "dist"))

    taille = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(STAGE) for f in fs) / 1e6
    print(f"Version {version()} prête dans {STAGE} ({taille:.1f} Mo).")
    # Interdit : tout fichier privé qui aurait échappé au filtre
    for d, _, fs in os.walk(STAGE):
        for f in fs:
            if f in (".env", "credentials.json", "adb_key", "memory.json") or f.endswith((".pickle", ".pem", ".key")):
                sys.exit(f"Fichier privé dans le dossier d'empaquetage : {os.path.join(d, f)}")


if __name__ == "__main__":
    main()
