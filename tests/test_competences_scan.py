"""Contrôle du code généré par l'IA (module/competences.py) : les contournements connus sont refusés, un code ordinaire passe."""
import pytest

try:   # la CI n'installe que pytest et requests : sans les dépendances de l'appli, ce fichier est ignoré
    from module.competences import scanner_appels_dangereux as scan
except ModuleNotFoundError as e:
    pytest.skip(f"dépendance absente : {e.name}", allow_module_level=True)

CONTOURNEMENTS = {
    "from os import system as": "from os import system as run\ndef executer(t=None):\n    run('calc')\n",
    "référence sans appel": "import os\ndef executer(t=None):\n    f = os.system\n    f('calc')\n",
    "os.execvp": "import os\ndef executer(t=None):\n    os.execvp('calc', ['calc'])\n",
    "os.spawnlp": "import os\ndef executer(t=None):\n    os.spawnlp(os.P_NOWAIT, 'calc', 'calc')\n",
    "témoin os.system": "import os\ndef executer(t=None):\n    os.system('calc')\n",
}


@pytest.mark.parametrize("code", CONTOURNEMENTS.values(), ids=CONTOURNEMENTS.keys())
def test_refuse(code):
    ok, raison = scan(code)
    assert not ok, raison


def test_code_ordinaire_passe():
    code = "import json\nimport datetime\n\ndef executer(texte_utilisateur=None):\n    return 'Il est ' + datetime.datetime.now().strftime('%H:%M') + json.dumps([1])\n"
    assert scan(code) == (True, "")
