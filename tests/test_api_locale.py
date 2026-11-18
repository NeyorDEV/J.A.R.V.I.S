"""API locale compatible OpenAI : jeton, hôte, corps, forme de la réponse."""
import json

from core import api_locale as a

JETON = "x" * 20
H = {"host": "127.0.0.1:8770", "authorization": f"Bearer {JETON}"}


def _post(corps, entetes=H, repondre=lambda q: f"re:{q}"):
    return a.traiter("POST", "/v1/chat/completions", entetes, corps if isinstance(corps, bytes) else json.dumps(corps).encode(), JETON, repondre)


def test_reponse_openai():
    code, d = _post({"messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "salut"}]})
    assert code == 200 and d["choices"][0]["message"] == {"role": "assistant", "content": "re:salut"} and d["object"] == "chat.completion"


def test_contenu_en_parties():
    code, d = _post({"messages": [{"role": "user", "content": [{"type": "text", "text": "a"}, {"type": "image_url"}, {"type": "text", "text": "b"}]}]})
    assert d["choices"][0]["message"]["content"] == "re:a b"


def test_jeton_obligatoire():
    assert _post({"messages": []}, {"host": "127.0.0.1"})[0] == 401
    assert _post({"messages": []}, {"host": "127.0.0.1", "authorization": "Bearer faux"})[0] == 401
    assert a.traiter("GET", "/v1/models", H, b"", "", None)[0] == 401   # jeton serveur vide : jamais ouvert


def test_hote_controle_contre_rebinding():
    assert _post({"messages": []}, {**H, "host": "evil.example.com"})[0] == 403
    assert a.traiter("GET", "/v1/models", {**H, "host": "localhost:8770"}, b"", JETON, None)[0] == 200


def test_entrees_invalides():
    assert _post(b"pas du json")[0] == 400
    assert _post({"messages": [{"role": "assistant", "content": "x"}]})[0] == 400
    assert _post(b"x" * (a.MAX_CORPS + 1))[0] == 413
    assert a.traiter("GET", "/autre", H, b"", JETON, None)[0] == 404


def test_panne_du_cerveau_donne_502_sans_detail():
    def casse(q):
        raise RuntimeError("clé secrète AIza…")
    code, d = _post({"messages": [{"role": "user", "content": "x"}]}, repondre=casse)
    assert code == 502 and "AIza" not in json.dumps(d)
