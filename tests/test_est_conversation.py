"""est_conversation (core/traitement.py) : les phrases de conversation sautent l'appel d'intention au LLM ; une commande, jamais."""
import pytest

try:   # la CI n'installe que pytest et requests : sans les dépendances de l'appli, ce fichier est ignoré (il tourne dans le venv de JARVIS)
    from core.traitement import est_conversation
except ModuleNotFoundError as e:
    pytest.skip(f"dépendance absente : {e.name}", allow_module_level=True)


@pytest.mark.parametrize("phrase", ["raconte moi une histoire", "Raconte-moi une histoire longue", "parle moi de la physique quantique des particules",
                                    "explique-moi comment marche un trou noir", "pourquoi le ciel est bleu", "c'est quoi un trou noir", "qu'est-ce qu'un électron",
                                    "s'il te plaît raconte une blague"])
def test_conversation(phrase):
    assert est_conversation(phrase)


@pytest.mark.parametrize("phrase", ["explique-moi la météo de demain", "parle moi de mon agenda", "mets de la musique", "joue du jazz", "baisse la lumière",
                                    "ouvre discord", "dis moi l'heure", "quelle heure est-il"])
def test_commande_ou_autre(phrase):
    assert not est_conversation(phrase)


@pytest.mark.parametrize("phrase,attendu", [
    ("mets de la musique", True), ("mettre la télé", True), ("jouer du jazz", True), ("lance spotify", True), ("ouvre le doc", True),
    ("il permet de voir", False), ("mon docteur", False), ("quelle balance", False), ("un alignement", False), ("il commet une erreur", False),
])
def test_est_action_oriented_mots_entiers(phrase, attendu):
    from core.traitement import est_action_oriented
    assert est_action_oriented(phrase) is attendu   # « met » dans « permet », « lance » dans « balance » : plus de faux positifs, la conjugaison reste reconnue
