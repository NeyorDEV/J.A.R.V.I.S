"""
voice_vault.py — Coffre-Fort Crypté AES-256 pour J.A.R.V.I.S v9.0

Permet de chiffrer, déchiffrer, verrouiller et déverrouiller des fichiers
confidentiels dans un dossier sécurisé via mot de passe / code PIN ou commande vocale.
"""

import os
import json
import base64
import hashlib
import hmac
import time
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

VAULT_DIR = os.path.join(os.path.expanduser("~"), ".jarvis_vault")
ENCRYPTED_FILES_DIR = os.path.join(VAULT_DIR, "encrypted_files")
CONFIG_FILE = os.path.join(VAULT_DIR, "vault_config.json")
TENTATIVES_FILE = os.path.join(VAULT_DIR, "vault_tentatives.json")

# Dérivation de la clé : 600 000 itérations pour les coffres créés ou migrés maintenant.
# Les anciens coffres (sans champ « iterations ») ont été créés avec 100 000.
ITERATIONS = 600000
ITERATIONS_ANCIEN = 100000
LONGUEUR_MIN = 8            # caractères, à la création du coffre
ECHECS_AVANT_DELAI = 3      # puis 30 s, 60 s, 120 s… (plafond 1 h)
_message = ""               # raison du dernier refus, affichable dans le HUD


def dernier_message() -> str:
    return _message

_unlocked_fernet = None
_is_unlocked = False
# Le coffre restait ouvert jusqu'au redémarrage : il se reverrouille seul après
# DELAI_VERROUILLAGE secondes sans utilisation.
DELAI_VERROUILLAGE = 600
_derniere_activite = 0.0


def _activite():
    global _derniere_activite
    import time
    _derniere_activite = time.time()


def _verifier_expiration():
    """Reverrouille le coffre s'il n'a pas servi depuis DELAI_VERROUILLAGE secondes."""
    import time
    if _is_unlocked and time.time() - _derniere_activite > DELAI_VERROUILLAGE:
        print("[VOICE VAULT] Verrouillage automatique (inactivité).")
        lock_vault()


def _nom_libre(dossier, nom, suffixe=""):
    """« rapport.pdf » → « rapport (2).pdf » si le nom est déjà pris (pas d'écrasement)."""
    base, ext = os.path.splitext(nom)
    candidat, n = nom, 2
    while os.path.exists(os.path.join(dossier, candidat + suffixe)):
        candidat = f"{base} ({n}){ext}"
        n += 1
    return candidat

def _ensure_dirs():
    os.makedirs(VAULT_DIR, exist_ok=True)
    os.makedirs(ENCRYPTED_FILES_DIR, exist_ok=True)

def _derive_key(password: str, salt: bytes, iterations: int = ITERATIONS) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def _ecrire_json_atomique(chemin, donnees):
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(donnees, f, indent=2)
    os.replace(tmp, chemin)


def _ecrire_octets_atomique(chemin, octets):
    tmp = chemin + ".tmp"
    with open(tmp, "wb") as f:
        f.write(octets)
    os.replace(tmp, chemin)


def _lire_tentatives() -> dict:
    try:
        with open(TENTATIVES_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        return {"echecs": int(d.get("echecs", 0)), "jusqu_a": float(d.get("jusqu_a", 0.0))}
    except Exception:
        return {"echecs": 0, "jusqu_a": 0.0}


def _attente_restante() -> int:
    """Secondes à attendre avant un nouvel essai (0 si le coffre peut être tenté)."""
    return max(0, int(_lire_tentatives()["jusqu_a"] - time.time() + 0.999))


def _enregistrer_echec():
    global _message
    d = _lire_tentatives()
    d["echecs"] += 1
    if d["echecs"] >= ECHECS_AVANT_DELAI:
        delai = min(3600, 30 * 2 ** (d["echecs"] - ECHECS_AVANT_DELAI))
        d["jusqu_a"] = time.time() + delai
        _message = f"Trop d'essais. Patientez {delai} s avant de réessayer."
    try:
        _ensure_dirs()
        _ecrire_json_atomique(TENTATIVES_FILE, d)
    except Exception:
        pass


def _reinitialiser_echecs():
    try:
        if os.path.exists(TENTATIVES_FILE):
            os.remove(TENTATIVES_FILE)
    except Exception:
        pass


def _migrer_vers_nouvelle_derivation(password: str, salt: bytes, ancienne_cle: bytes):
    """Passe un ancien coffre (100 000 itérations) à ITERATIONS : tous les fichiers sont
    rechiffrés dans des .new, puis remplacés ; la config n'est réécrite qu'à la fin."""
    nouvelle_cle = _derive_key(password, salt, ITERATIONS)
    ancien, nouveau = Fernet(ancienne_cle), Fernet(nouvelle_cle)
    fichiers = [f for f in os.listdir(ENCRYPTED_FILES_DIR) if f.endswith(".jvault")]
    # 1. tout rechiffrer à côté (si une étape échoue, rien n'a changé)
    for nom in fichiers:
        with open(os.path.join(ENCRYPTED_FILES_DIR, nom), "rb") as f:
            clair = ancien.decrypt(f.read())
        with open(os.path.join(ENCRYPTED_FILES_DIR, nom + ".new"), "wb") as f:
            f.write(nouveau.encrypt(clair))
    # 2. remplacer, puis écrire la config
    for nom in fichiers:
        os.replace(os.path.join(ENCRYPTED_FILES_DIR, nom + ".new"), os.path.join(ENCRYPTED_FILES_DIR, nom))
    _ecrire_json_atomique(CONFIG_FILE, {
        "salt_b64": base64.b64encode(salt).decode("utf-8"),
        "validation_hash": hashlib.sha256(nouvelle_cle).hexdigest(),
        "iterations": ITERATIONS,
    })
    return nouvelle_cle

def is_vault_configured() -> bool:
    _ensure_dirs()
    return os.path.exists(CONFIG_FILE)

def setup_vault(password: str) -> bool:
    """Initialise le coffre-fort avec un mot de passe maître ou un PIN."""
    global _unlocked_fernet, _is_unlocked, _message
    _ensure_dirs()
    if len(password) < LONGUEUR_MIN:
        _message = f"Le mot de passe du coffre doit faire au moins {LONGUEUR_MIN} caractères."
        print(f"[VOICE VAULT] Création refusée : {_message}")
        return False
    salt = os.urandom(16)
    key = _derive_key(password, salt, ITERATIONS)

    val_hash = hashlib.sha256(key).hexdigest()

    cfg_data = {
        "salt_b64": base64.b64encode(salt).decode("utf-8"),
        "validation_hash": val_hash,
        "iterations": ITERATIONS,
    }

    _ecrire_json_atomique(CONFIG_FILE, cfg_data)
    _reinitialiser_echecs()
    _message = ""

    _unlocked_fernet= Fernet(key)
    _is_unlocked = True
    _activite()
    print("[VOICE VAULT] Coffre-fort créé et déverrouillé avec succès.")
    return True

def unlock_vault(password: str) -> bool:
    """Déverrouille le coffre-fort si le mot de passe est valide."""
    global _unlocked_fernet, _is_unlocked, _message
    _message = ""
    if not is_vault_configured():
        return setup_vault(password)

    attente = _attente_restante()
    if attente > 0:
        _message = f"Trop d'essais. Patientez {attente} s avant de réessayer."
        print(f"[VOICE VAULT] Déverrouillage refusé : {_message}")
        return False

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        salt = base64.b64decode(cfg["salt_b64"])
        val_hash = cfg["validation_hash"]
        iterations = int(cfg.get("iterations", ITERATIONS_ANCIEN))

        key = _derive_key(password, salt, iterations)
        test_hash = hashlib.sha256(key).hexdigest()

        if hmac.compare_digest(test_hash, val_hash):
            if iterations < ITERATIONS:
                try:
                    key = _migrer_vers_nouvelle_derivation(password, salt, key)
                    print(f"[VOICE VAULT] Coffre migré vers {ITERATIONS} itérations.")
                except Exception as e_mig:
                    # Rien n'a été remplacé : on continue avec l'ancienne clé
                    print(f"[VOICE VAULT] Migration impossible ({e_mig}) — ancien format conservé.")
                    for f in os.listdir(ENCRYPTED_FILES_DIR):
                        if f.endswith(".new"):
                            try: os.remove(os.path.join(ENCRYPTED_FILES_DIR, f))
                            except Exception: pass
            _unlocked_fernet = Fernet(key)
            _is_unlocked = True
            _activite()
            _reinitialiser_echecs()
            print("[VOICE VAULT] Coffre-fort déverrouillé avec succès.")
            return True
        else:
            _enregistrer_echec()
            if not _message:
                _message = "Mot de passe ou PIN incorrect."
            print("[VOICE VAULT] Échec de déverrouillage : mot de passe incorrect.")
            return False
    except Exception as e:
        print(f"[VOICE VAULT] Erreur déverrouillage : {e}")
        return False

def lock_vault():
    """Verrouille le coffre-fort et détruit la clé en mémoire."""
    global _unlocked_fernet, _is_unlocked
    _unlocked_fernet = None
    _is_unlocked = False
    print("[VOICE VAULT] Coffre-fort verrouillé.")
    return True

def is_vault_unlocked() -> bool:
    _verifier_expiration()
    return _is_unlocked

def list_vault_files() -> list:
    """Liste tous les fichiers chiffrés contenus dans le coffre."""
    _verifier_expiration()
    if _is_unlocked:
        _activite()
    _ensure_dirs()
    if not _is_unlocked:
        return []
        
    files = []
    for f in os.listdir(ENCRYPTED_FILES_DIR):
        if f.endswith(".jvault"):
            original_name = f[:-7]
            full_path = os.path.join(ENCRYPTED_FILES_DIR, f)
            size_bytes = os.path.getsize(full_path)
            files.append({
                "filename": original_name,
                "encrypted_file": f,
                "size_kb": round(size_bytes / 1024, 1)
            })
    return files

def add_file_to_vault(file_path: str) -> bool:
    """Chiffre un fichier et l'ajoute au coffre-fort."""
    _verifier_expiration()
    if _is_unlocked:
        _activite()
    if not _is_unlocked or not _unlocked_fernet:
        print("[VOICE VAULT] Impossible d'ajouter : le coffre est verrouillé.")
        return False
        
    if not os.path.exists(file_path):
        print(f"[VOICE VAULT] Fichier introuvable : {file_path}")
        return False
        
    try:
        with open(file_path, "rb") as f:
            data = f.read()
            
        encrypted_data = _unlocked_fernet.encrypt(data)
        original_name = _nom_libre(ENCRYPTED_FILES_DIR, os.path.basename(file_path), ".jvault")
        dest_path = os.path.join(ENCRYPTED_FILES_DIR, f"{original_name}.jvault")
        
        _ecrire_octets_atomique(dest_path, encrypted_data)

        print(f"[VOICE VAULT] Fichier chiffré et stocké: {original_name}")
        return True
    except Exception as e:
        print(f"[VOICE VAULT] Erreur chiffrement fichier : {e}")
        return False

def export_file_from_vault(filename: str, dest_dir: str) -> str:
    """Déchiffre un fichier du coffre vers un dossier de destination."""
    _verifier_expiration()
    if _is_unlocked:
        _activite()
    if not _is_unlocked or not _unlocked_fernet:
        return ""
        
    enc_path = os.path.join(ENCRYPTED_FILES_DIR, f"{filename}.jvault")
    if not os.path.exists(enc_path):
        return ""
        
    try:
        with open(enc_path, "rb") as f:
            enc_data = f.read()
            
        decrypted_data = _unlocked_fernet.decrypt(enc_data)
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, _nom_libre(dest_dir, os.path.basename(filename)))
        
        with open(dest_path, "wb") as f:
            f.write(decrypted_data)
            
        print(f"[VOICE VAULT] Fichier déchiffré et exporté vers : {dest_path}")
        return dest_path
    except Exception as e:
        print(f"[VOICE VAULT] Erreur déchiffrement export : {e}")
        return ""

def delete_file_from_vault(filename: str) -> bool:
    """Supprime définitivement un fichier du coffre."""
    _verifier_expiration()
    if _is_unlocked:
        _activite()
    if not _is_unlocked:
        return False
        
    enc_path = os.path.join(ENCRYPTED_FILES_DIR, f"{filename}.jvault")
    if os.path.exists(enc_path):
        try:
            os.remove(enc_path)
            print(f"[VOICE VAULT] Fichier supprimé du coffre : {filename}")
            return True
        except Exception as e:
            print(f"[VOICE VAULT] Erreur suppression fichier : {e}")
            return False
    return False
