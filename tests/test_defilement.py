"""Défilement du fil des échanges (touches, bornes, suivi des nouvelles rangées)."""
import pytest

from core.defilement import apres_nouvelle_rangee, decaler, nom_touche, nom_touche_vt


@pytest.mark.parametrize("premier,second,attendu", [("\xe0", "I", None), ("\x00", "Q", None),("\xe0", "H", "haut"), ("\xe0", "P", "bas"), ("\xe0", "G", "debut"), ("\xe0", "O", "fin"),
                                                    ("a", "", None), ("\x03", "", None), ("\xe0", "Z", None), ("\xe0", "", None)])
def test_nom_touche(premier, second, attendu):
    assert nom_touche(premier, second) == attendu


@pytest.mark.parametrize("sequence,attendu", [("[5~", None), ("[6~", None), ("[A", "haut"), ("OB", "bas"), ("[H", "debut"), ("[4~", "fin"), ("[Z", None), ("", None), ("", None)])
def test_nom_touche_vt(sequence, attendu):
    assert nom_touche_vt(sequence) == attendu


def test_remonter_et_redescendre_par_pages():
    d = 0
    d = decaler(d, 100, 10, "page_haut")
    assert d == 9                                    # une page = hauteur - 1 (une rangée de recouvrement pour se repérer)
    d = decaler(d, 100, 10, "page_haut")
    assert d == 18
    d = decaler(d, 100, 10, "page_bas")
    assert d == 9
    d = decaler(d, 100, 10, "page_bas")
    d = decaler(d, 100, 10, "page_bas")
    assert d == 0                                    # on ne descend pas sous le plus récent


def test_fleches_une_rangee():
    assert decaler(0, 50, 10, "haut") == 1
    assert decaler(5, 50, 10, "bas") == 4
    assert decaler(0, 50, 10, "bas") == 0


def test_debut_et_fin():
    assert decaler(3, 50, 10, "debut") == 49          # le plus ancien : la dernière rangée remontable
    assert decaler(49, 50, 10, "fin") == 0


def test_bornes_fil_court_ou_vide():
    assert decaler(0, 0, 10, "page_haut") == 0
    assert decaler(0, 1, 10, "haut") == 0
    assert decaler(0, 3, 50, "page_haut") == 2         # jamais au-delà de la plus ancienne rangée
    assert decaler(0, 5, 0, "page_haut") == 1           # hauteur inconnue : au moins une rangée


def test_touche_inconnue_ne_change_rien():
    assert decaler(7, 50, 10, "autre") == 7


def test_nouvelle_rangee_suit_le_bas_ou_garde_la_rangee_lue():
    assert apres_nouvelle_rangee(0, 20) == 0            # au bas du fil : on suit
    assert apres_nouvelle_rangee(5, 20) == 6            # on lit l'historique : la même rangée reste à l'écran
    assert apres_nouvelle_rangee(19, 20) == 19          # déjà tout en haut : borné


# --- intégration avec la console (rich requis : ignoré en CI, où seuls pytest et requests sont installés) -------------------------------------------------------------------------------
def _console(tmp_path):
    pytest.importorskip("rich")
    from core.console_ui import _Console
    c = _Console(False, str(tmp_path / "journal.log"))
    c.tableau = True
    return c


def _texte(groupe, console):
    from io import StringIO

    from rich.console import Console
    sortie = StringIO()
    Console(file=sortie, width=60, force_terminal=False, color_system=None).print(groupe)
    return sortie.getvalue()


def test_fil_visible_remonte_et_suit_les_nouvelles_rangees(tmp_path):
    c = _console(tmp_path)               # ignore le test si rich est absent (CI) : à faire AVANT tout import de rich
    from rich.text import Text
    for i in range(30):
        c._afficher(Text(f"ligne {i}"))
    bas = _texte(c._fil_visible(50, 8), c)
    assert "ligne 29" in bas and "ligne 21" not in bas and c.nb_visibles == 8
    from core.defilement import decaler
    c.decalage = decaler(c.decalage, len(c.fil), c.nb_visibles, "page_haut")          # on remonte d'une page
    haut = _texte(c._fil_visible(50, 8), c)
    assert "ligne 29" not in haut and "ligne 22" in haut
    c._afficher(Text("ligne 30"))                                                        # une rangée arrive pendant qu'on lit l'historique
    assert _texte(c._fil_visible(50, 8), c) == haut                                       # la même page reste à l'écran
    c.decalage = decaler(c.decalage, len(c.fil), c.nb_visibles, "fin")
    assert "ligne 30" in _texte(c._fil_visible(50, 8), c)                                 # Fin : retour au plus récent


def test_le_fil_garde_beaucoup_plus_que_400_rangees(tmp_path):
    c = _console(tmp_path)
    from rich.text import Text
    for i in range(1500):
        c._afficher(Text(f"r{i}"))
    assert len(c.fil) == 1500
