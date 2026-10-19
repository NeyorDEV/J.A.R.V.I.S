"""
api_quota.py — Gestion des quotas/rate-limits des APIs LLM.

Formatage court des erreurs API et cooldown automatique par fournisseur
(Gemini, Groq, Grok, Claude, Ollama). Extrait de main2.py.
"""

import asyncio

class _ErreurQuotaApi(Exception):
    """Exception : une API annonce que son quota ou sa limite de débit est atteint."""
    pass

def formater_erreur_courte(e):
    if isinstance(e, asyncio.TimeoutError) or type(e).__name__ == "TimeoutError":
        return "Délai d'attente dépassé (Timeout - le serveur Gemini a mis trop de temps à répondre)"
    err_str = str(e).strip()
    if not err_str:
        return "Erreur de communication ou Timeout (Réponse vide de l'API)"
    if "You exceeded your current quota" in err_str or "quota exceeded" in err_str.lower():
        if "model:" in err_str:
            parts = err_str.split("model:")
            model_info = parts[-1].strip().split("\n")[0]
            return f"Quota Gemini dépassé pour le modèle {model_info}. (429 Too Many Requests)"
        return "Quota API Gemini dépassé. (429 Too Many Requests)"
    if len(err_str) > 120:
        if "{" in err_str and "}" in err_str:
            try:
                import json
                start_idx = err_str.find("{")
                end_idx = err_str.rfind("}") + 1
                if start_idx != -1 and end_idx != -1:
                    json_part = err_str[start_idx:end_idx]
                    data = json.loads(json_part.replace("'\n", "'").replace("'\r", "'"))
                    if isinstance(data, dict):
                        error_obj = data.get("error", {})
                        if isinstance(error_obj, dict) and error_obj.get("message"):
                            msg = error_obj.get("message")
                            if "Quota exceeded" in msg:
                                return f"Quota dépassé : {msg.split('Please retry')[0].strip()}"
                            return msg
                        elif data.get("message"):
                            return data.get("message")
            except:
                pass
        return err_str[:117] + "..."
    return err_str

class GestionnaireQuotas:
    """
    Met en pause les API dont le quota est atteint.
    Reconnaît les erreurs 429, resource_exhausted et rate_limit.
    """

    # Durée de cooldown par API (secondes)
    COOLDOWNS = {
        "claude"  : 60,
        "gemini"  : 60,
        "grok"    : 60,
        "groq"    : 30,
        "mistral" : 60,
        "ollama"  : 10,
    }

    # Mots-clés indiquant un quota épuisé (insensible à la casse).
    # Volontairement précis : « exceeded » et « context_length_exceeded » ont été
    # retirés car un simple prompt trop long était classé comme dépassement de
    # quota et mettait le fournisseur en pause 60 s, masquant le vrai problème.
    QUOTA_KEYWORDS = [
        "429", "503", "quota", "rate limit", "rate_limit", "ratelimit",
        "too many requests", "resource_exhausted", "resource exhausted",
        "quota exceeded", "quota_exceeded", "tokens per", "requests per",
        "rateLimitExceeded", "RATE_LIMIT_EXCEEDED", "insufficient_quota",
        "overloaded",
    ]

    def __init__(self):
        from datetime import datetime, timedelta
        self._datetime   = datetime
        self._timedelta  = timedelta
        self._cooldowns  = {}   # {api_name: datetime_disponible}
        self._hit_count  = {}   # {api_name: nb_fois_quota_atteint}

    def est_erreur_quota(self, error: Exception) -> bool:
        """Vrai si l'erreur vient d'un quota ou d'une limite de débit."""
        err_str = str(error).lower()
        return any(kw.lower() in err_str for kw in self.QUOTA_KEYWORDS)

    def est_disponible(self, api_name: str) -> bool:
        """Vrai si l'API n'est pas en pause."""
        if api_name not in self._cooldowns:
            return True
        return self._datetime.now() >= self._cooldowns[api_name]

    def declarer_quota_atteint(self, api_name: str) -> None:
        """Met une API en pause après dépassement de quota."""
        duration = self.COOLDOWNS.get(api_name, 60)
        self._cooldowns[api_name] = self._datetime.now() + self._timedelta(seconds=duration)
        self._hit_count[api_name] = self._hit_count.get(api_name, 0) + 1
        print(f"[QUOTA] ⚠ {api_name.upper()} quota atteint — cooldown {duration}s "
              f"(total: {self._hit_count[api_name]} fois)")

    def pause_restante(self, api_name: str) -> int:
        """Secondes avant la reprise de l'API (0 si elle est disponible)."""
        if self.est_disponible(api_name):
            return 0
        delta = self._cooldowns[api_name] - self._datetime.now()
        return max(0, int(delta.total_seconds()))

    def status(self) -> str:
        """Récapitulatif de l'état de chaque API."""
        lines = []
        for api in self.COOLDOWNS:
            if not self.est_disponible(api):
                lines.append(f"  {api.upper()}: cooldown {self.pause_restante(api)}s")
            else:
                lines.append(f"  {api.upper()}: disponible")
        return "\n".join(lines)

# Instance globale
_quota_mgr = GestionnaireQuotas()
