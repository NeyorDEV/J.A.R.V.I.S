"""Prénom dit dans la réponse (changement de personne ou premier échange du jour), à la place de l'annonce « Voix de X détectée »."""
from types import SimpleNamespace

import pytest

from core import nommer

AUJ = "2026-11-16"


# --- la règle : qui doit être nommé ----------------------------------------------------------------------------------------------------------------------------------------------------------
def test_premier_echange_du_jour_puis_plus():
    assert nommer.doit_nommer("neyor", None, {}, AUJ) is True                       # premier échange (JARVIS vient de démarrer ou de la journée)
    assert nommer.doit_nommer("neyor", "neyor", {"neyor": AUJ}, AUJ) is False         # même personne, déjà nommée aujourd'hui
    assert nommer.doit_nommer("neyor", "neyor", {"neyor": "2026-11-15"}, AUJ) is True  # nouveau jour : on nomme à nouveau


def test_changement_de_personne_nomme_a_chaque_fois():
    nomme = {"neyor": AUJ, "clara": AUJ}
    assert nommer.doit_nommer("clara", "neyor", nomme, AUJ) is True
    assert nommer.doit_nommer("neyor", "clara", nomme, AUJ) is True


def test_une_voix_inconnue_n_est_jamais_nommee_mais_compte_comme_un_changement():
    assert nommer.doit_nommer("guest", "neyor", {}, AUJ) is False
    assert nommer.doit_nommer("neyor", "guest", {"neyor": AUJ}, AUJ) is True        # A, invité, A : A est nommé de nouveau
    assert nommer.doit_nommer(None, "neyor", {}, AUJ) is False


# --- la phrase ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("texte,attendu", [
    ("Il est 14 heures.", "Il est 14 heures, Clara."),
    ("Très bien, je lance Spotify.", "Très bien, je lance Spotify, Clara."),
    ("Que puis-je pour vous ?", "Que puis-je pour vous, Clara ?"),
    ("C'est fait !", "C'est fait, Clara !"),
    ("Je vérifie...", "Je vérifie, Clara..."),
    ("Il fait beau", "Il fait beau, Clara"),                              # sans ponctuation finale
    ("Il est 14 heures.  ", "Il est 14 heures, Clara."),                  # espaces en fin de phrase
    ("C'est « One More Time » de Daft Punk.", "C'est « One More Time » de Daft Punk, Clara."),
    ("3 alarmes sont actives.", "3 alarmes sont actives, Clara."),
])
def test_prenom_place_a_la_fin_avant_la_ponctuation(texte, attendu):
    assert nommer.inserer_nom(texte, "Clara") == attendu


@pytest.mark.parametrize("texte,attendu", [
    ("Voici la liste :", "Clara, voici la liste :"),
    ("Trois choses ;", "Clara, trois choses ;"),
    ("IA en marche :", "Clara, IA en marche :"),
])
def test_phrase_qui_annonce_une_suite_prenom_devant(texte, attendu):
    assert nommer.inserer_nom(texte, "Clara") == attendu


@pytest.mark.parametrize("texte", ["Mes circuits ne s'en portent que mieux, Clara.", "Très bien Clara, je lance Spotify.", "Clara, il est 14 heures.", "il fait beau, CLARA", "Bonjour Néyor."])
def test_prenom_deja_present_rien_n_est_ajoute(texte):
    nom = "Neyor" if "Néyor" in texte else "Clara"
    assert nommer.inserer_nom(texte, nom) == texte


def test_un_prenom_n_est_pas_cherche_dans_un_autre_mot():
    assert nommer.inserer_nom("Le clarinettiste joue.", "Clara") == "Le clarinettiste joue, Clara."


def test_texte_vide():
    assert nommer.inserer_nom("   ", "Clara") == "   "
    assert nommer.inserer_nom("", "Clara") == ""


# --- le scénario d'une pièce à trois ---------------------------------------------------------------------------------------------------------------------------------------------------------
def nouvel_etat():
    return SimpleNamespace(LOCUTEUR_PRECEDENT=None, NOMME_LE={}, NOM_A_DIRE=None)


NOMS = {"neyor": "Neyor", "clara": "Clara", "guest": ""}


def parle(etat, locuteur, reponse, maintenant=1000.0):
    """Une personne parle, JARVIS répond : renvoie ce qu'il dit."""
    nommer.armer(etat, locuteur, nom_fn=lambda: NOMS[locuteur], maintenant=maintenant)
    return nommer.appliquer(etat, reponse, maintenant=maintenant + 1)


def test_scenario_trois_personnes_sans_annonce_parasite():
    e = nouvel_etat()
    assert parle(e, "neyor", "Il est 14 heures.") == "Il est 14 heures, Neyor."               # premier échange
    assert parle(e, "neyor", "Il fait 12 degrés.") == "Il fait 12 degrés."                    # même personne : rien
    assert parle(e, "clara", "La musique est en pause.") == "La musique est en pause, Clara."  # changement
    assert parle(e, "clara", "C'est fait.") == "C'est fait."
    assert parle(e, "guest", "Je ne peux pas faire ça en mode invité.") == "Je ne peux pas faire ça en mode invité."   # jamais nommé
    assert parle(e, "neyor", "Voilà.") == "Voilà, Neyor."                                     # après l'invité : changement
    assert parle(e, "clara", "Voilà.") == "Voilà, Clara."                                     # Neyor -> Clara : changement


def test_le_prenom_n_est_dit_qu_une_fois_meme_si_jarvis_parle_plusieurs_fois():
    e = nouvel_etat()
    nommer.armer(e, "clara", nom_fn=lambda: "Clara", maintenant=1000.0)
    assert nommer.appliquer(e, "Première phrase.", maintenant=1001.0) == "Première phrase, Clara."
    assert nommer.appliquer(e, "Deuxième phrase.", maintenant=1002.0) == "Deuxième phrase."


def test_reponse_silencieuse_le_prenom_reste_arme_jusqu_a_la_prochaine_phrase_puis_expire():
    e = nouvel_etat()
    nommer.armer(e, "neyor", nom_fn=lambda: "Neyor", maintenant=1000.0)
    assert e.NOM_A_DIRE is not None                                                           # JARVIS n'a rien dit : toujours armé
    assert nommer.appliquer(e, "Une alarme sonne.", maintenant=1000.0 + nommer.EXPIRE_S + 5) == "Une alarme sonne."   # trop tard : hors contexte
    assert e.NOM_A_DIRE is None and e.NOMME_LE == {}                                          # expiré : pas considéré comme nommé


def test_si_le_prenom_est_deja_dans_la_reponse_il_compte_comme_dit():
    e = nouvel_etat()
    assert parle(e, "neyor", "Mes circuits ne s'en portent que mieux, Neyor.") == "Mes circuits ne s'en portent que mieux, Neyor."
    assert e.NOMME_LE == {"neyor": __import__("datetime").date.today().isoformat()}
    assert parle(e, "neyor", "Autre réponse.") == "Autre réponse."


def test_aucun_prenom_arme_pour_une_voix_inconnue():
    e = nouvel_etat()
    assert nommer.armer(e, "guest", nom_fn=lambda: "", maintenant=1000.0) is False
    assert nommer.appliquer(e, "Bonjour.", maintenant=1001.0) == "Bonjour."
