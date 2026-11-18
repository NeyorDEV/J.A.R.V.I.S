"""Filtre de secrets avant la voix (core/secrets_voix.py)."""
import pytest

from core.secrets_voix import MARQUE, masquer


@pytest.mark.parametrize("secret", [
    "sk-ant-api03-AbCdEf1234567890AbCdEf1234567890",
    "AIzaSyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q",
    "gsk_AbCdEf1234567890AbCdEf1234567890",
    "ghp_AbCdEf1234567890AbCdEf1234567890",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcDEF123456",
    "d41d8cd98f00b204e9800998ecf8427e",
    "Bearer abcdef1234567890abcdef",
    "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0U1v2W3x4",
])
def test_un_secret_est_masque(secret):
    sortie = masquer(f"Voici la clé {secret} voilà.")
    assert secret not in sortie and MARQUE in sortie and sortie.startswith("Voici la clé ") and sortie.endswith(" voilà.")


@pytest.mark.parametrize("texte", ["Il est 14 heures 30.", "Il fait 12 degrés à Lyon.", "La capitale de l'Australie est Canberra.", "Votre numéro est 0612345678.",
                                   "anticonstitutionnellement", "C'est « One More Time » de Daft Punk.", "", "Les routines sont en pause, Neyor."])
def test_le_texte_ordinaire_ne_change_pas(texte):
    assert masquer(texte) == texte
