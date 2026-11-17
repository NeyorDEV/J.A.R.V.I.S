"""Compteur de consommation de la reconnaissance vocale (Groq Whisper, repli Google) : requêtes, secondes d'audio, refus pour excès de requêtes.

Groq (offre gratuite, whisper-large-v3-turbo) plafonne : 20 requêtes / minute, 2 000 requêtes / jour, 7 200 s d'audio / heure, 28 800 s / jour (page officielle des limites de Groq ;
chiffres modifiables dans jarvis_config.json, clé `groq_limites_stt`, si vous êtes sur une offre payante). Chaque segment de parole détecté par le micro est envoyé : ce compteur dit si on s'approche des plafonds.
Persisté dans data/usage_stt.json (non versionné) : les événements des dernières 24 h + les totaux des 30 derniers jours. Pur et testé : tests/test_usage_stt.py.
"""
import json
import os
import threading
import time
from collections import deque
from datetime import datetime

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FICHIER = os.path.join(RACINE, "data", "usage_stt.json")
LIMITES_DEFAUT = {"rpm": 20, "rpj": 2000, "sh": 7200, "sj": 28800}   # requêtes/min, requêtes/jour, secondes d'audio/heure, secondes d'audio/jour
SEUIL_ALERTE = 0.8
GARDER_JOURS = 30


def _jour(t: float) -> str:
    return datetime.fromtimestamp(t).strftime("%Y-%m-%d")


class CompteurQuota:
    def __init__(self, fichier=None, limites=None):
        self.fichier = fichier
        self.limites = {**LIMITES_DEFAUT, **(limites or {})}
        self._verrou = threading.Lock()
        self._evenements = deque()   # (heure, service, secondes, ok, code)
        self._jours = {}             # "2026-11-16" -> {"requetes", "secondes", "refus", "google", "erreurs"}
        self._alertes_dites = {}     # clé de limite -> heure de la dernière alerte (une par heure au plus)
        self._derniere_ecriture = 0.0
        self._charger()

    # --- enregistrement -------------------------------------------------------------------------------------------------------------------------
    def noter(self, service: str, secondes: float = 0.0, ok: bool = True, code=None, maintenant=None) -> list:
        """Note un appel (service « groq » ou « google ») ; renvoie les messages d'alerte à afficher (limite approchée), le plus souvent une liste vide."""
        t = time.time() if maintenant is None else maintenant
        with self._verrou:
            self._evenements.append((t, service, float(secondes), bool(ok), code))
            self._purger(t)
            j = self._jours.setdefault(_jour(t), {"requetes": 0, "secondes": 0.0, "refus": 0, "google": 0, "erreurs": 0})
            if service == "groq":
                j["requetes"] += 1
                j["secondes"] = round(j["secondes"] + float(secondes), 2)
                if code == 429:
                    j["refus"] += 1
                elif not ok:
                    j["erreurs"] += 1
            elif service == "google":
                j["google"] += 1
            alertes = self._alertes(t)
            self._ecrire_si_utile(t)
        return alertes

    def _purger(self, t):
        while self._evenements and t - self._evenements[0][0] > 86400:
            self._evenements.popleft()
        for jour in sorted(self._jours)[:-GARDER_JOURS]:
            del self._jours[jour]

    # --- lecture ----------------------------------------------------------------------------------------------------------------------------------
    def _fenetre(self, t, duree):
        n, s = 0, 0.0
        for h, service, secondes, _ok, _code in self._evenements:
            if service == "groq" and t - h <= duree:
                n += 1
                s += secondes
        return n, s

    def etat(self, maintenant=None) -> dict:
        t = time.time() if maintenant is None else maintenant
        with self._verrou:
            self._purger(t)
            n_min, _ = self._fenetre(t, 60)
            n_h, s_h = self._fenetre(t, 3600)
            n_24, s_24 = self._fenetre(t, 86400)
            auj = self._jours.get(_jour(t), {"requetes": 0, "secondes": 0.0, "refus": 0, "google": 0, "erreurs": 0})
            pic_rpm = self._pic_requetes_minute()
        L = self.limites
        return {"minute": n_min, "heure_requetes": n_h, "heure_secondes": round(s_h), "jour_requetes": auj["requetes"], "jour_secondes": round(auj["secondes"]), "refus_jour": auj["refus"], "repli_google_jour": auj["google"],
                "erreurs_jour": auj["erreurs"], "dernieres_24h_requetes": n_24, "dernieres_24h_secondes": round(s_24), "pic_requetes_minute_24h": pic_rpm, "limites": dict(L),
                "pourcent": {"minute": round(100 * n_min / L["rpm"]), "heure": round(100 * s_h / L["sh"]), "jour_requetes": round(100 * auj["requetes"] / L["rpj"]), "jour_secondes": round(100 * auj["secondes"] / L["sj"])}}

    def _pic_requetes_minute(self):
        heures = [h for h, service, *_ in self._evenements if service == "groq"]
        pic, i = 0, 0
        for j, h in enumerate(heures):
            while h - heures[i] > 60:
                i += 1
            pic = max(pic, j - i + 1)
        return pic

    def resume_parle(self, maintenant=None) -> str:
        e = self.etat(maintenant)
        p, L = e["pourcent"], e["limites"]
        morceaux = [f"Sur la dernière heure, {e['heure_requetes']} requêtes et {e['heure_secondes']} secondes d'audio envoyées à Groq, soit {p['heure']} % de la limite horaire.",
                    f"Aujourd'hui, {e['jour_requetes']} requêtes ({p['jour_requetes']} % de {L['rpj']}) et {e['jour_secondes']} secondes d'audio ({p['jour_secondes']} % de {L['sj']})."]
        if e["pic_requetes_minute_24h"] >= L["rpm"] * SEUIL_ALERTE:
            morceaux.append(f"Pic de {e['pic_requetes_minute_24h']} requêtes en une minute sur 24 heures, pour une limite de {L['rpm']}.")
        if e["refus_jour"]:
            morceaux.append(f"{e['refus_jour']} refus pour excès de requêtes aujourd'hui.")
        if e["repli_google_jour"]:
            morceaux.append(f"{e['repli_google_jour']} reconnaissances faites par Google en secours.")
        return " ".join(morceaux)

    def _alertes(self, t) -> list:
        """Messages quand une limite est approchée à 80 % ou plus ; une alerte par limite et par heure au plus."""
        L = self.limites
        n_min, _ = self._fenetre(t, 60)
        n_h, s_h = self._fenetre(t, 3600)
        auj = self._jours.get(_jour(t), {})
        mesures = {"rpm": (n_min, L["rpm"], "requêtes par minute"), "sh": (s_h, L["sh"], "secondes d'audio par heure"), "rpj": (auj.get("requetes", 0), L["rpj"], "requêtes par jour"),
                   "sj": (auj.get("secondes", 0), L["sj"], "secondes d'audio par jour")}
        sortie = []
        for cle, (valeur, limite, nom) in mesures.items():
            if limite and valeur >= SEUIL_ALERTE * limite and t - self._alertes_dites.get(cle, 0) > 3600:
                self._alertes_dites[cle] = t
                sortie.append(f"Reconnaissance vocale Groq : {round(valeur)} / {limite} {nom} ({round(100 * valeur / limite)} %)")
        return sortie

    # --- persistance ----------------------------------------------------------------------------------------------------------------------------
    def _charger(self):
        if not self.fichier:
            return
        try:
            with open(self.fichier, encoding="utf-8") as f:
                d = json.load(f)
            self._evenements = deque(tuple(e) for e in d.get("evenements", []))
            self._jours = d.get("jours", {})
        except (OSError, ValueError, TypeError):
            pass

    def _ecrire_si_utile(self, t, force=False):
        if not self.fichier or (not force and t - self._derniere_ecriture < 30):
            return
        self._derniere_ecriture = t
        try:
            os.makedirs(os.path.dirname(self.fichier), exist_ok=True)
            tmp = self.fichier + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"evenements": list(self._evenements), "jours": self._jours}, f, separators=(",", ":"))
            os.replace(tmp, self.fichier)
        except OSError:
            pass

    def enregistrer(self):
        with self._verrou:
            self._ecrire_si_utile(time.time(), force=True)


_compteur = None


def compteur() -> CompteurQuota:
    """Compteur partagé de JARVIS (limites lues dans jarvis_config.json : groq_limites_stt)."""
    global _compteur
    if _compteur is None:
        limites = None
        try:   # jarvis_config.json (à la racine) : {"groq_limites_stt": {"rpm": 20, "rpj": 2000, "sh": 7200, "sj": 28800}} ; seules les clés données sont remplacées
            with open(os.path.join(RACINE, "jarvis_config.json"), encoding="utf-8") as f:
                limites = json.load(f).get("groq_limites_stt")
        except (OSError, ValueError, AttributeError):
            pass
        _compteur = CompteurQuota(FICHIER, limites if isinstance(limites, dict) else None)
    return _compteur
