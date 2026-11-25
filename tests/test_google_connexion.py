"""Connexion Google (module/google_services.py) : JARVIS le dit à voix haute et abandonne au bout du délai au lieu de rester muet."""
import builtins

from module import google_services as G


class _Flux:
    def __init__(self, resultat=None, erreur=None):
        self.resultat, self.erreur, self.kw = resultat, erreur, None

    def run_local_server(self, **kw):
        self.kw = kw
        if self.erreur:
            raise self.erreur
        return self.resultat


def test_connexion_reussie_previent_et_borne_l_attente(monkeypatch):
    dit = []
    monkeypatch.setattr(builtins, "parler", lambda t, *a, **k: dit.append(t), raising=False)
    flux = _Flux(resultat="CREDS")
    assert G._connexion_google(flux) == "CREDS"
    assert flux.kw["timeout_seconds"] == 120 and len(dit) == 1 and "navigateur" in dit[0]


def test_connexion_abandonnee_rend_none_et_le_dit(monkeypatch):
    dit = []
    monkeypatch.setattr(builtins, "parler", lambda t, *a, **k: dit.append(t), raising=False)
    assert G._connexion_google(_Flux(erreur=TimeoutError("délai"))) is None
    assert len(dit) == 2 and "n'a pas abouti" in dit[1]
