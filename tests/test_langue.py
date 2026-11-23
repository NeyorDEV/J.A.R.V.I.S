"""Langue de JARVIS (core/i18n.py, plugins/langue_resolver.py) : réglages STT / voix, détection du français, commandes de changement de langue. Sans réseau."""
import asyncio

import pytest

from core import i18n
from plugins import langue_resolver as lr


@pytest.fixture
def langue(monkeypatch, tmp_path):
    monkeypatch.setattr(i18n, "_CONFIG", str(tmp_path / "jarvis_config.json"))
    monkeypatch.setattr(i18n, "_CACHE_FICHIER", str(tmp_path / "trad.json"))
    monkeypatch.setattr(i18n, "_cache", None)
    monkeypatch.setattr(lr, "prevenir_hud", lambda code: None)
    monkeypatch.setattr(i18n, "_langue", "fr")
    return i18n


def test_reglages_par_langue(langue):
    assert (langue.stt_whisper(), langue.stt_google(), langue.voix_edge("homme"), langue.voix_edge("femme")) == ("fr", "fr-FR", "fr-FR-HenriNeural", "fr-FR-DeniseNeural")
    assert langue.consigne_langue() == ""
    langue.definir("en")
    assert (langue.stt_whisper(), langue.stt_google(), langue.voix_edge("homme"), langue.voix_edge("femme")) == ("en", "en-US", "en-GB-RyanNeural", "en-GB-SoniaNeural")
    assert "English" in langue.consigne_langue() and "stop" in langue.amorce_stop()
    assert not langue.definir("de") and langue.langue() == "en"


def test_langue_sauvegardee(langue, tmp_path):
    langue.definir("en")
    assert '"langue": "en"' in (tmp_path / "jarvis_config.json").read_text(encoding="utf-8")


@pytest.mark.parametrize("texte,francais", [("Très bien, je lance Spotify.", True), ("Alarme réglée", True), ("Je ne trouve pas le fichier", True), ("Done, sir.", False), ("Spotify", False),
                                            ("Playing Daft Punk on Deezer", False), ("Il est trois heures", True)])
def test_parait_francais(texte, francais):
    assert i18n.parait_francais(texte) is francais


def test_traduction_inactive_en_francais_ou_deja_anglais(langue):
    assert asyncio.run(langue.traduire("Très bien, je lance Spotify.")) == "Très bien, je lance Spotify."
    langue.definir("en")
    assert asyncio.run(langue.traduire("Done, sir.")) == "Done, sir."
    langue._cache = {"Très bien, je lance Spotify.": "Very well, launching Spotify."}
    assert langue.traduire_sync("Très bien, je lance Spotify.") == "Very well, launching Spotify."   # cache : pas d'appel réseau


@pytest.mark.parametrize("phrase,attendu", [("passe en anglais", "en"), ("Jarvis, parle en anglais s'il te plait", "en"), ("switch to english", "en"), ("speak English please", "en"),
                                            ("parle en français", "fr"), ("repasse en francais", "fr"), ("speak french", "fr"), ("mets de la musique anglaise", None), ("lance spotify", None)])
def test_commande_de_langue(langue, phrase, attendu):
    rep = asyncio.run(lr.resoudre_langue(phrase))
    if attendu is None:
        assert rep is None
    elif attendu == langue.langue() and "déjà" not in rep and "already" not in rep:
        assert rep
    else:
        assert rep  # « déjà » : la langue demandée était déjà active
    if attendu:
        assert langue.langue() == attendu


@pytest.mark.parametrize("texte,secondes", [("five minutes", 300), ("in 10 minutes", 600), ("half an hour", 1800), ("a quarter of an hour", 900), ("two hours thirty", 9000), ("90 seconds", 90),
                                            ("twenty-five minutes", 1500), ("5 minutes", 300), ("une demi-heure", 1800)])
def test_durees_en_anglais(texte, secondes):
    from module.alarm_manager import parser_duree
    assert parser_duree(texte) == secondes


@pytest.mark.parametrize("texte,heure,minute", [("7 pm", 19, 0), ("7:30 am", 7, 30), ("12 am", 0, 0), ("12 pm", 12, 0), ("tomorrow at 6 am", 6, 0), ("noon", 12, 0)])
def test_heures_en_anglais(texte, heure, minute):
    from module.alarm_manager import parser_heure
    d = parser_heure(texte)
    assert d and (d.hour, d.minute) == (heure, minute)


class _Reponse:
    def __init__(self, text):
        self.text = text


class _FauxClient:
    """Remplace client_gemini : compte les appels, renvoie la phrase préparée (ou lève)."""
    def __init__(self, texte, erreurs_avant=0):
        self.appels, self.texte, self.erreurs = [], texte, erreurs_avant
        outer = self

        class _Models:
            async def generate_content(self, model, contents, config):
                outer.appels.append((model, contents, config))
                if outer.erreurs:
                    outer.erreurs -= 1
                    raise RuntimeError("429")
                return _Reponse(outer.texte)

        class _Aio:
            models = _Models()
        self.aio = _Aio()


def _brancher(monkeypatch, faux):
    pytest.importorskip("google.genai")   # absent de l'environnement minimal de la CI
    import core.ai_clients as ac
    monkeypatch.setattr(ac, "client_gemini", faux)
    reel = asyncio.sleep
    monkeypatch.setattr(asyncio, "sleep", lambda s: reel(0))   # la seconde chance n'attend pas 1,5 s en test


def test_commande_anglaise_traduite_en_francais(langue, monkeypatch):
    faux = _FauxClient("Ma journée")
    _brancher(monkeypatch, faux)
    langue.definir("en")
    assert asyncio.run(langue.commande_en_francais("my day")) == "Ma journée"
    assert asyncio.run(langue.commande_en_francais("my day")) == "Ma journée" and len(faux.appels) == 1   # 2e fois : cache
    prompt = faux.appels[0][2].system_instruction
    assert "PRIORITY examples" in prompt and "Ouvre le coffre-fort" in prompt and "Monte le volume" in prompt   # exemples de l'aide + exemples prioritaires
    assert asyncio.run(langue.commande_en_francais("Monte le volume")) == "Monte le volume" and len(faux.appels) == 1   # déjà français : pas d'appel


def test_commande_inchangee_en_francais_et_apres_echec(langue, monkeypatch):
    faux = _FauxClient("x", erreurs_avant=5)
    _brancher(monkeypatch, faux)
    assert asyncio.run(langue.commande_en_francais("open the vault")) == "open the vault" and not faux.appels   # langue fr : rien n'est fait
    langue.definir("en")
    assert asyncio.run(langue.commande_en_francais("open the vault")) == "open the vault" and len(faux.appels) == 2   # 2 essais puis la phrase d'origine
    faux.erreurs = 1
    faux.texte = "Ouvre le coffre-fort"
    assert asyncio.run(langue.commande_en_francais("open the vault please")) == "Ouvre le coffre-fort"   # la seconde chance réussit


def test_reponse_traduite_et_deja_anglaise_laissee(langue, monkeypatch):
    faux = _FauxClient("Very well, launching Spotify.")
    _brancher(monkeypatch, faux)
    langue.definir("en")
    assert asyncio.run(langue.traduire("Très bien, je lance Spotify.")) == "Very well, launching Spotify."
    assert asyncio.run(langue.traduire("Done, sir.")) == "Done, sir." and len(faux.appels) == 1


def test_prompt_systeme_anglais(langue):
    pytest.importorskip("google.genai")
    from core.prompt_builder import composer_prompt_systeme
    fr = composer_prompt_systeme()
    assert "FINAL REMINDER" not in fr and "LANGUAGE:" not in fr
    langue.definir("en")
    en = composer_prompt_systeme()
    assert en.startswith("LANGUAGE:") and en.endswith("only the text you say is English.")


def test_heuristique_phrases_sans_mot_outil():
    assert i18n.parait_francais("12 fois 8 font 96, Neyor.") and not i18n.parait_francais("Playing Daft Punk on Deezer")


def test_message_ws_traduire(langue, monkeypatch):
    """Le HUD en anglais demande la traduction de textes dynamiques : réponse « traduction » avec le même id et les textes dans l'ordre."""
    pytest.importorskip("google.genai")
    from core.ws_reglages import ws_traduire
    faux = _FauxClient("Firewall rules added.")
    _brancher(monkeypatch, faux)
    langue.definir("en")
    envoyes = []

    class _Ws:
        async def send(self, m):
            envoyes.append(m)
    asyncio.run(ws_traduire(_Ws(), {"id": "tr7", "textes": ["Règles pare-feu ajoutées.", "Done, sir."]}))
    import json as _j
    rep = _j.loads(envoyes[0])
    assert rep == {"type": "traduction", "id": "tr7", "textes": ["Firewall rules added.", "Done, sir."]}


def test_console_traduite_par_modeles(langue, monkeypatch, tmp_path):
    """Messages de la console : modèles à variables ({0}), inchangés en français et quand le message est inconnu ; jamais d'appel réseau."""
    import json as _j
    f = tmp_path / "console_fr_en.json"
    f.write_text(_j.dumps({"Whisper local OK ({0}s) : {1}": "Local Whisper OK ({0}s): {1}", "Micro retenu : {0}": "Selected mic: {0}"}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(i18n, "_CONSOLE_FICHIER", str(f))
    monkeypatch.setattr(i18n, "_console_modeles", None)
    assert i18n.console("Whisper local OK (0.42s) : bonjour") == "Whisper local OK (0.42s) : bonjour"   # français : inchangé
    langue.definir("en")
    assert i18n.console("Whisper local OK (0.42s) : bonjour") == "Local Whisper OK (0.42s): bonjour"
    assert i18n.console("Micro retenu : [3] Microphone (Realtek)") == "Selected mic: [3] Microphone (Realtek)"
    assert i18n.console("Message jamais vu") == "Message jamais vu"


def test_libelles_console_et_phrase_dite(langue):
    assert i18n.ui_console("PRÊT") == "PRÊT" and i18n.depuis_cache("Très bien.") is None
    langue.definir("en")
    assert i18n.ui_console("PRÊT") == "READY" and i18n.ui_console("inconnu") == "inconnu"
    langue._cache = {"Très bien.": "Very well."}
    assert i18n.depuis_cache("Très bien.") == "Very well."


def test_ligne_dit_de_la_console_en_anglais(langue, capsys):
    """Mode anglais : « [DIT] » montre la phrase traduite si elle est connue ; sinon elle attend la traduction (affichée par le fil de la parole)."""
    pytest.importorskip("edge_tts")
    pytest.importorskip("pygame")
    from core import speech
    langue.definir("en")
    langue._cache = {"Très bien, je lance Spotify.": "Very well, launching Spotify."}
    speech.parler("Très bien, je lance Spotify.")
    speech.parler("Phrase jamais traduite : il fait beau.")
    sortie = capsys.readouterr().out
    assert "[DIT] Very well, launching Spotify." in sortie and "jamais traduite" not in sortie   # la 2e attend sa traduction
    assert "Phrase jamais traduite : il fait beau." in speech._DIT_APRES_TRADUCTION
    speech._DIT_APRES_TRADUCTION.clear()
    langue.definir("fr")
    speech.parler("Très bien, je lance Spotify.")
    assert "[DIT] Très bien, je lance Spotify." in capsys.readouterr().out   # français : comme avant
    speech.vider_files()
