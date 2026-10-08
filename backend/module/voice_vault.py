"""
voice_vault.py — Coffre-Fort Crypté AES-256 pour J.A.R.V.I.S v9.0

Permet de chiffrer, déchiffrer, verrouiller et déverrouiller des fichiers
confidentiels dans un dossier sécurisé via mot de passe / code PIN ou commande vocale.
"""

import os
import json
import base64
import shutil
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

VAULT_DIR = os.path.join(os.path.expanduser("~"), ".jarvis_vault")
ENCRYPTED_FILES_DIR = os.path.join(VAULT_DIR, "encrypted_files")
CONFIG_FILE = os.path.join(VAULT_DIR, "vault_config.json")

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

def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))

def is_vault_configured() -> bool:
    _ensure_dirs()
    return os.path.exists(CONFIG_FILE)

def setup_vault(password: str) -> bool:
    """Initialise le coffre-fort avec un mot de passe maître ou un PIN."""
    global _unlocked_fernet, _is_unlocked
    _ensure_dirs()
    salt = os.urandom(16)
    key = _derive_key(password, salt)
    
    val_hash = hashlib.sha256(key).hexdigest()
    
    cfg_data = {
        "salt_b64": base64.b64encode(salt).decode("utf-8"),
        "validation_hash": val_hash
    }
    
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg_data, f, indent=2)
        
    _unlocked_fernet = Fernet(key)
    _is_unlocked = True
    _activite()
    print("[VOICE VAULT] Coffre-fort créé et déverrouillé avec succès.")
    return True

def unlock_vault(password: str) -> bool:
    """Déverrouille le coffre-fort si le mot de passe est valide."""
    global _unlocked_fernet, _is_unlocked
    if not is_vault_configured():
        return setup_vault(password)
        
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            
        salt = base64.b64decode(cfg["salt_b64"])
        val_hash = cfg["validation_hash"]
        
        key = _derive_key(password, salt)
        test_hash = hashlib.sha256(key).hexdigest()
        
        if test_hash == val_hash:
            _unlocked_fernet = Fernet(key)
            _is_unlocked = True
            _activite()
            print("[VOICE VAULT] Coffre-fort déverrouillé avec succès.")
            return True
        else:
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
        
        with open(dest_path, "wb") as f:
            f.write(encrypted_data)
            
        print(f"[VOICE VAULT] Fichier chiffré et stocké : {original_name}")
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
