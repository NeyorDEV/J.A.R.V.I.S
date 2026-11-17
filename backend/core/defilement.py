"""Défilement du fil des échanges dans le tableau de bord plein écran de la console (core/console_ui.py).

Le tableau plein écran n'a pas d'historique de terminal (écran alternatif) : sans cela, on ne voyait que les dernières lignes. Touches : Page haut / Page bas (une page), flèches haut / bas (une rangée),
Début (le plus ancien), Fin (retour au plus récent). Avec la molette, certains terminaux envoient les flèches dans l'écran alternatif (selon le terminal).
Pur et testé : tests/test_defilement.py.
"""

# code de la deuxième partie d'une touche étendue (msvcrt.getwch renvoie « \x00 » ou « \xe0 » puis ce code)
TOUCHES = {"H": "haut", "P": "bas", "G": "debut", "O": "fin"}


def nom_touche(premier: str, second: str = ""):
    """Touche étendue Windows (Page haut…) -> « page_haut »… ; None pour toute autre touche."""
    if premier in ("\x00", "\xe0"):
        return TOUCHES.get(second or "")
    return None


# séquences envoyées quand la console est en mode « entrée terminal » (un autre programme a pu l'activer) : ESC [ 5 ~ pour Page haut…
TOUCHES_VT = {"\x1b[A": "haut", "\x1bOA": "haut", "\x1b[B": "bas", "\x1bOB": "bas",
              "\x1b[H": "debut", "\x1bOH": "debut", "\x1b[1~": "debut", "\x1b[F": "fin", "\x1bOF": "fin", "\x1b[4~": "fin"}


def nom_touche_vt(sequence: str):
    """Séquence « terminal » (« \\x1b[5~ ») -> « page_haut »… ; None si inconnue."""
    return TOUCHES_VT.get(sequence)


def decaler(decalage: int, nb_rangees: int, nb_visibles: int, touche: str) -> int:
    """Nouveau décalage (nombre de rangées remontées depuis le bas du fil, 0 = le plus récent) après une touche ; toujours entre 0 et nb_rangees - 1."""
    dernier = max(0, nb_rangees - 1)
    page = max(1, nb_visibles - 1)
    if touche == "page_haut":
        decalage += page
    elif touche == "page_bas":
        decalage -= page
    elif touche == "haut":
        decalage += 1
    elif touche == "bas":
        decalage -= 1
    elif touche == "debut":
        decalage = dernier
    elif touche == "fin":
        decalage = 0
    return max(0, min(decalage, dernier))


def apres_nouvelle_rangee(decalage: int, nb_rangees: int) -> int:
    """Une rangée arrive : si on lit l'historique, on garde la même rangée à l'écran (le décalage grandit d'un cran) ; au bas du fil, on suit le plus récent."""
    return min(decalage + 1, max(0, nb_rangees - 1)) if decalage > 0 else 0
