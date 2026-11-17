"""« Répète » : reconnaissance de la demande, mémoire par tour, annonces système écartées."""
import pytest

from core import repeter

DEMANDES = ["répète", "Répète !", "redis", "répète ça", "répète moi ça", "peux-tu répéter", "tu peux répéter s'il te plaît", "j'ai pas compris", "je n'ai pas bien compris", "j'ai pas compris, tu peux répéter",
            "répète ce que tu as dit", "redis-le encore", "jarvis répète", "répète ta dernière phrase", "dis encore une fois"]
PAS_DES_DEMANDES = ["répète après moi bonjour", "répète le mot chat trois fois", "mets de la musique", "quelle heure est-il", "répétition générale", "redis bonjour à Clara", ""]


@pytest.fixture(autouse=True)
def vide():
    repeter.oublier()
    yield
    repeter.oublier()


@pytest.mark.parametrize("phrase", DEMANDES)
def test_demande_reconnue(phrase):
    assert repeter.est_demande_repetition(phrase) is True


@pytest.mark.parametrize("phrase", PAS_DES_DEMANDES)
def test_autres_phrases_ignorees(phrase):
    assert repeter.est_demande_repetition(phrase) is False


def test_redit_le_dernier_tour_en_entier_sans_le_melanger_au_precedent():
    repeter.nouveau_tour()                       # commande 1
    repeter.noter("Une ancienne réponse.", maintenant=1000.0)
    repeter.nouveau_tour()                       # commande 2
    repeter.noter("Il fait 12 degrés à Lyon.", maintenant=1005.0)
    repeter.noter("Pas de pluie prévue.", maintenant=1007.0)
    repeter.nouveau_tour()                       # commande 3 : « répète »
    assert repeter.derniere_reponse(maintenant=1010.0) == "Il fait 12 degrés à Lyon. Pas de pluie prévue."


def test_cas_du_journal_les_annonces_systeme_ne_sont_pas_redites():
    # tour 1 : un invité parle, JARVIS répond ; tour 2 : annonce de la voix de Neyor PUIS réponse ; tour 3 : « répète »
    repeter.nouveau_tour()
    repeter.noter("Répéter n'a jamais amélioré le contenu, mais comme vous y tenez...", maintenant=1000.0)
    repeter.noter("Voix de Neyor détectée, toutes les permissions sont accordées.", maintenant=1010.0)
    repeter.nouveau_tour()
    repeter.noter("Mes circuits ne s'en portent que mieux, Neyor.", maintenant=1013.0)
    repeter.noter("Que puis-je pour vous ?", maintenant=1014.0)
    repeter.nouveau_tour()
    assert repeter.derniere_reponse(maintenant=1020.0) == "Mes circuits ne s'en portent que mieux, Neyor."


@pytest.mark.parametrize("annonce", ["Que puis-je pour vous ?", "Clara, que puis-je pour vous ?", "Que puis-je pour vous, Clara ?", "Voix inconnue détectée, connexion en mode invité restreint.", "Voix de Clara détectée, connexion sécurisée établie.", "Je vous écoute.",
                                     "J'écoute pendant 10 secondes.", "Dites oui pour confirmer, ou non pour annuler."])
def test_annonces_ecartees(annonce):
    repeter.nouveau_tour()
    repeter.noter(annonce, maintenant=1000.0)
    repeter.nouveau_tour()
    assert repeter.derniere_reponse(maintenant=1001.0) == ""


def test_un_tour_sans_parole_est_saute():
    repeter.nouveau_tour()
    repeter.noter("La réponse qui compte.", maintenant=1000.0)
    repeter.nouveau_tour()                       # action silencieuse
    repeter.nouveau_tour()                       # « répète »
    assert repeter.derniere_reponse(maintenant=1005.0) == "La réponse qui compte."


def test_rien_de_recent_ou_rien_du_tout():
    assert repeter.derniere_reponse(maintenant=5000.0) == ""
    repeter.nouveau_tour()
    repeter.noter("Bonjour monsieur.", maintenant=1000.0)
    repeter.nouveau_tour()
    assert repeter.derniere_reponse(maintenant=1000.0 + 700) == ""   # plus de 10 minutes


def test_la_repetition_n_est_pas_notee_deux_fois_et_peut_etre_redemandee():
    repeter.nouveau_tour()
    repeter.noter("Il est 14 heures.", maintenant=100.0)
    repeter.nouveau_tour()                       # « répète »
    texte = repeter.derniere_reponse(maintenant=101.0)
    repeter.ignorer_prochaine(texte)
    repeter.noter(texte, maintenant=102.0)       # la répétition est dite à son tour
    repeter.nouveau_tour()                       # « répète » encore
    assert repeter.derniere_reponse(maintenant=103.0) == "Il est 14 heures."


def test_longue_reponse_coupee_a_une_phrase():
    repeter.nouveau_tour()
    for i in range(20):
        repeter.noter(f"Phrase numéro {i} qui est assez longue pour remplir la limite de caractères du texte redit.", maintenant=100.0 + i)
    repeter.nouveau_tour()
    r = repeter.derniere_reponse(maintenant=130.0)
    assert len(r) <= repeter.MAX_CARACTERES and r.startswith("Phrase numéro 0") and r.endswith("redit.")
