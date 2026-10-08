"""Emplacements réels des dossiers personnels Windows (Bureau, Documents, Téléchargements…).

Les chemins étaient écrits en dur (USERPROFILE\\Desktop, \\Documents…). Or, quand le
Bureau, les Documents ou les Images sont synchronisés par OneDrive (ou déplacés par
l'utilisateur), ils sont ailleurs : « trie mon bureau » visait un autre dossier, et
les documents générés partaient dans un dossier « Desktop » invisible. On demande donc
à Windows (SHGetKnownFolderPath) où ils se trouvent vraiment.
"""

import os

# Identifiants Windows des dossiers connus (KNOWNFOLDERID)
_GUIDS = {
    "bureau": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
    "documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
    "telechargements": "{374DE290-123F-4565-9164-39C4925E467B}",
    "images": "{33E28130-4E1E-4676-835A-98395C3BC3BB}",
    "musique": "{4BD8D571-6D19-48D3-BE97-422220080E43}",
    "videos": "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}",
}
_NOMS_PAR_DEFAUT = {"bureau": "Desktop", "documents": "Documents", "telechargements": "Downloads",
                    "images": "Pictures", "musique": "Music", "videos": "Videos"}
# Synonymes acceptés (sans accents)
_SYNONYMES = {
    "bureau": "bureau", "desktop": "bureau",
    "document": "documents", "documents": "documents",
    "telechargement": "telechargements", "telechargements": "telechargements",
    "download": "telechargements", "downloads": "telechargements",
    "image": "images", "images": "images", "photo": "images", "photos": "images", "pictures": "images",
    "musique": "musique", "musiques": "musique", "music": "musique",
    "video": "videos", "videos": "videos",
}
_cache = {}


def _sans_accent(texte):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")


def _chemin_windows(guid):
    import ctypes
    import uuid
    from ctypes import wintypes

    class _GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

    u = uuid.UUID(guid)
    g = _GUID(u.time_low, u.time_mid, u.time_hi_version,
              (ctypes.c_ubyte * 8)(u.clock_seq_hi_variant, u.clock_seq_low, *u.node.to_bytes(6, "big")))
    chemin = ctypes.c_wchar_p()
    if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(chemin)) != 0:
        return None
    try:
        return chemin.value
    finally:
        ctypes.windll.ole32.CoTaskMemFree(chemin)


def dossier_connu(nom):
    """Chemin réel d'un dossier personnel (« bureau », « documents », « téléchargements »,
    « images », « musique », « vidéos » et synonymes), ou None si le nom n'en est pas un."""
    cle = _SYNONYMES.get(_sans_accent((nom or "").lower().strip()))
    if not cle:
        return None
    if cle not in _cache:
        chemin = None
        try:
            chemin = _chemin_windows(_GUIDS[cle])
        except Exception:
            pass
        _cache[cle] = chemin or os.path.join(os.path.expanduser("~"), _NOMS_PAR_DEFAUT[cle])
    return _cache[cle]


def dossiers_personnels():
    """Les six dossiers personnels réels (pour les recherches de fichiers)."""
    return [dossier_connu(c) for c in _GUIDS]
