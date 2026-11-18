"""API locale compatible OpenAI : d'autres outils du PC (éditeur, scripts, Open WebUI…) parlent à JARVIS comme à un modèle.

Désactivée par défaut. Activation : JARVIS_API_TOKEN dans .env (au moins 16 caractères, écrite à la main) ET "api_locale": {"actif": true, "port": 8770} dans jarvis_config.json.
  POST http://127.0.0.1:8770/v1/chat/completions   (Authorization: Bearer <JARVIS_API_TOKEN>)   GET /v1/models
Sûreté : écoute 127.0.0.1 seulement ; jeton obligatoire (comparaison à temps constant) ; en-tête Host contrôlé (contre le « DNS rebinding » d'une page web) ;
corps limité à 100 Ko ; AUCUNE action n'est exécutée (texte seulement : `skip_local=True`, comme la synthèse de recherche) ; rien n'est ajouté à l'historique ni à la mémoire.
⚠️ La réponse vient du même cerveau que la voix : il reçoit la mémoire persistante et la fenêtre d'historique de la session, donc le porteur du jeton peut les faire citer.
La logique (`traiter`) est pure et testée (tests/test_api_locale.py) ; seul `demarrer` ouvre un port.
"""
import hmac
import json
import os
import threading
import time

MAX_CORPS = 100_000
MODELE = "jarvis"
_HOTES_OK = ("127.0.0.1", "localhost", "[::1]")


def _hote_ok(entete_host: str) -> bool:
    h = (entete_host or "").strip().lower()
    nom = h.rsplit(":", 1)[0] if (":" in h and not h.endswith("]")) else h
    return nom in _HOTES_OK


def _derniere_question(messages) -> str:
    """Texte du dernier message « user » (contenu texte ou liste de parties texte) ; vide si aucun."""
    for m in reversed(messages if isinstance(messages, list) else []):
        if isinstance(m, dict) and m.get("role") == "user":
            c = m.get("content")
            if isinstance(c, str):
                return c.strip()
            if isinstance(c, list):
                return " ".join(str(p.get("text", "")) for p in c if isinstance(p, dict) and p.get("type") == "text").strip()
    return ""


def _erreur(code: int, message: str, type_: str = "invalid_request_error"):
    return code, {"error": {"message": message, "type": type_}}


def traiter(methode: str, chemin: str, entetes: dict, corps: bytes, jeton: str, repondre_ia):
    """(code HTTP, JSON à renvoyer). `repondre_ia(question) -> str` est synchrone (injecté)."""
    if not _hote_ok(entetes.get("host", "")):
        return _erreur(403, "hôte refusé")
    auth = entetes.get("authorization", "")
    fourni = auth[7:] if auth.lower().startswith("bearer ") else ""
    if not jeton or not hmac.compare_digest(fourni.encode(), jeton.encode()):
        return _erreur(401, "jeton invalide", "authentication_error")
    chemin = chemin.split("?", 1)[0]
    if methode == "GET" and chemin == "/v1/models":
        return 200, {"object": "list", "data": [{"id": MODELE, "object": "model", "owned_by": "jarvis"}]}
    if methode == "POST" and chemin == "/v1/chat/completions":
        if len(corps) > MAX_CORPS:
            return _erreur(413, "corps trop gros")
        try:
            data = json.loads(corps.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return _erreur(400, "JSON illisible")
        question = _derniere_question(data.get("messages") if isinstance(data, dict) else None)
        if not question:
            return _erreur(400, "aucun message utilisateur")
        try:
            texte = repondre_ia(question[:4000])
        except Exception as e:
            return _erreur(502, f"JARVIS n'a pas pu répondre ({type(e).__name__})", "api_error")
        return 200, {"id": f"chatcmpl-{int(time.time() * 1000)}", "object": "chat.completion", "created": int(time.time()), "model": MODELE,
                     "choices": [{"index": 0, "message": {"role": "assistant", "content": texte or ""}, "finish_reason": "stop"}],
                     "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
    return _erreur(404, "route inconnue")


def _repondre_ia(question: str) -> str:
    import asyncio

    import core.shared as shared
    from core.llm_chat import interroger_ia
    if shared.WS_LOOP is None:
        raise RuntimeError("JARVIS pas prêt")

    async def _run():
        async with shared.traiter_lock:   # une seule demande à la fois, comme pour la voix
            return await interroger_ia(question, update_hist=False, skip_local=True)
    return asyncio.run_coroutine_threadsafe(_run(), shared.WS_LOOP).result(90) or ""


def demarrer():
    """Lance le serveur si le réglage et le jeton sont présents ; rend le thread, ou None."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    racine = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        with open(os.path.join(racine, "jarvis_config.json"), encoding="utf-8") as f:
            cfg = json.load(f).get("api_locale") or {}
    except Exception:
        cfg = {}
    jeton = os.getenv("JARVIS_API_TOKEN", "").strip()
    if not (isinstance(cfg, dict) and cfg.get("actif")):
        return None
    if len(jeton) < 16:
        print("[API] Activée dans la config mais JARVIS_API_TOKEN (16 caractères au moins) manque dans .env : non démarrée.")
        return None
    port = int(cfg.get("port", 8770))

    class H(BaseHTTPRequestHandler):
        def _repondre(self, methode):
            n = int(self.headers.get("Content-Length") or 0)
            corps = self.rfile.read(min(n, MAX_CORPS + 1)) if methode == "POST" else b""
            code, data = traiter(methode, self.path, {k.lower(): v for k, v in self.headers.items()}, corps, jeton, _repondre_ia)
            sortie = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(sortie)))
            self.end_headers()
            self.wfile.write(sortie)

        def do_GET(self):
            self._repondre("GET")

        def do_POST(self):
            self._repondre("POST")

        def log_message(self, *a):
            pass   # jamais de jeton ni de question dans les journaux

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True, name="ApiLocale")
    t.start()
    print(f"[API] Compatible OpenAI sur http://127.0.0.1:{port}/v1 (jeton requis).")
    return t
