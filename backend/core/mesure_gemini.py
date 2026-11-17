"""Mesure de TOUS les appels à Gemini, en un seul endroit : les méthodes du SDK (`generate_content`, `generate_content_stream`, synchrones et asynchrones) sont enveloppées une fois pour toutes.

Chaque réponse porte `usage_metadata` (jetons du prompt, du cache, de la réflexion, de sortie) : on la transmet à core/usage_llm. Les ~20 endroits qui appellent Gemini (réflexion, vision, mémoire, agents,
génération d'images…) sont ainsi comptés sans être modifiés un par un. Une erreur de comptage ne doit JAMAIS gêner un appel : tout est dans des try/except.
"""
import functools

_installe = False


def _noter(modele, reponse):
    try:
        u = getattr(reponse, "usage_metadata", None)
        if u is None:
            return
        entree = (getattr(u, "prompt_token_count", 0) or 0) + (getattr(u, "tool_use_prompt_token_count", 0) or 0)
        sortie = (getattr(u, "candidates_token_count", 0) or 0) + (getattr(u, "thoughts_token_count", 0) or 0)   # la réflexion est facturée comme de la sortie
        cache = getattr(u, "cached_content_token_count", 0) or 0
        from core.usage_llm import compteur
        for niveau, texte in compteur().noter(modele, entree, sortie, cache):
            print(f"[COUT IA] {texte}")
            if niveau >= 100:
                try:
                    import builtins
                    builtins.parler("Attention, j'ai atteint le plafond de dépenses Gemini pour aujourd'hui.")
                except Exception:
                    pass
    except Exception:
        pass


def _modele(args, kwargs):
    return kwargs.get("model") or (args[0] if args and isinstance(args[0], str) else "")


def installer() -> bool:
    """Enveloppe les méthodes du SDK (une seule fois) ; renvoie True si c'est fait."""
    global _installe
    if _installe:
        return True
    try:
        from google.genai import models as m
    except Exception:
        return False

    def sync(orig):
        @functools.wraps(orig)
        def f(self, *args, **kwargs):
            r = orig(self, *args, **kwargs)
            _noter(_modele(args, kwargs), r)
            return r
        return f

    def asynchrone(orig):
        @functools.wraps(orig)
        async def f(self, *args, **kwargs):
            r = await orig(self, *args, **kwargs)
            _noter(_modele(args, kwargs), r)
            return r
        return f

    def flux_sync(orig):
        @functools.wraps(orig)
        def f(self, *args, **kwargs):
            derniere = None
            try:
                for morceau in orig(self, *args, **kwargs):
                    if getattr(morceau, "usage_metadata", None) is not None:
                        derniere = morceau   # l'usage est cumulé : le dernier morceau qui en porte fait foi
                    yield morceau
            finally:
                if derniere is not None:
                    _noter(_modele(args, kwargs), derniere)
        return f

    def flux_asynchrone(orig):
        @functools.wraps(orig)
        async def f(self, *args, **kwargs):
            source = await orig(self, *args, **kwargs)

            async def suivre():
                derniere = None
                try:
                    async for morceau in source:
                        if getattr(morceau, "usage_metadata", None) is not None:
                            derniere = morceau
                        yield morceau
                finally:
                    if derniere is not None:
                        _noter(_modele(args, kwargs), derniere)
            return suivre()
        return f

    try:
        m.Models.generate_content = sync(m.Models.generate_content)
        m.Models.generate_content_stream = flux_sync(m.Models.generate_content_stream)
        m.AsyncModels.generate_content = asynchrone(m.AsyncModels.generate_content)
        m.AsyncModels.generate_content_stream = flux_asynchrone(m.AsyncModels.generate_content_stream)
    except Exception:
        return False
    _installe = True
    return True
