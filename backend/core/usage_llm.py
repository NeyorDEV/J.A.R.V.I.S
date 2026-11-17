"""Suivi de la consommation Gemini : jetons et coût par jour, par mois et par modèle, avec une alerte à 80 % puis à 100 % d'un plafond journalier.

Les jetons sont lus dans la réponse de Gemini (`usage_metadata`) par core/mesure_gemini.py, pour TOUS les appels (réflexion, vision, mémoire, agents…).
Facturation Gemini : entrée = jetons du prompt hors cache (+ outils) au tarif d'entrée, jetons en cache à leur tarif, sortie = jetons générés + jetons de réflexion.
Les tarifs ci-dessous sont en dollars par million de jetons et viennent de sources tierces qui divergent (à vérifier sur ai.google.dev/pricing) : modifiables dans jarvis_config.json,
`prix_llm` = {"nom-de-modele": [entrée, sortie, cache]}. Un modèle sans tarif connu est compté en jetons et signalé « sans prix » (jamais estimé).
Autres réglages (jarvis_config.json) : `plafond_llm_eur_jour` (5.0 par défaut), `usd_en_eur` (0.92 par défaut : taux APPROXIMATIF, à ajuster).
Persisté dans data/usage_llm.json (non versionné). Pur et testé : tests/test_usage_llm.py.
"""
import json
import os
import threading
import time
from datetime import datetime

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FICHIER = os.path.join(RACINE, "data", "usage_llm.json")
# $ / million de jetons : (entrée, sortie, entrée en cache). gemini-3.8-flash : 0,75 / 3,75 jusqu'au 31/12/2026, puis probablement 1,50 / 7,50 selon certaines sources.
PRIX_DEFAUT = {"gemini-3.5-flash-lite": (0.30, 2.50, 0.03), "gemini-3.8-flash": (0.75, 3.75, 0.075)}
PLAFOND_EUR_JOUR = 5.0
USD_EN_EUR = 0.92
GARDER_JOURS = 62


def _jour(t: float) -> str:
    return datetime.fromtimestamp(t).strftime("%Y-%m-%d")


def prix_modele(modele: str, surcharges=None):
    """(entrée, sortie, cache) $/M pour un modèle, via la plus longue clé contenue dans son nom ; None si inconnu."""
    m = str(modele or "").lower().replace("models/", "")
    cles = {**PRIX_DEFAUT, **{str(k).lower(): tuple(v) for k, v in (surcharges or {}).items() if isinstance(v, (list, tuple)) and len(v) >= 2}}
    for cle in sorted(cles, key=len, reverse=True):
        if cle in m:
            p = cles[cle]
            return float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else float(p[0])
    return None


def cout_usd(prix, entree: int, sortie: int, cache: int = 0) -> float:
    """Coût en dollars : `entree` = jetons du prompt (cache compris), `cache` = part servie depuis le cache."""
    p_in, p_out, p_cache = prix
    cache = min(max(cache, 0), max(entree, 0))
    return ((entree - cache) * p_in + cache * p_cache + sortie * p_out) / 1_000_000


class CompteurLLM:
    def __init__(self, fichier=None, surcharges=None, plafond_eur=PLAFOND_EUR_JOUR, usd_en_eur=USD_EN_EUR):
        self.fichier = fichier
        self.surcharges = surcharges or {}
        self.plafond_eur = float(plafond_eur)
        self.usd_en_eur = float(usd_en_eur)
        self._verrou = threading.Lock()
        self._jours = {}          # "2026-11-16" -> {modele: {"appels", "entree", "sortie", "cache", "usd", "sans_prix"}}
        self._alertes_dites = {}  # jour -> {80, 100} déjà dites
        self._derniere_ecriture = 0.0
        self._charger()

    def noter(self, modele: str, entree: int, sortie: int, cache: int = 0, maintenant=None) -> list:
        """Note un appel ; renvoie les alertes [(80|100, texte)] franchies pour la première fois aujourd'hui."""
        t = time.time() if maintenant is None else maintenant
        entree, sortie, cache = int(entree or 0), int(sortie or 0), int(cache or 0)
        modele = str(modele or "inconnu").replace("models/", "")
        with self._verrou:
            m = self._jours.setdefault(_jour(t), {}).setdefault(modele, {"appels": 0, "entree": 0, "sortie": 0, "cache": 0, "usd": 0.0, "sans_prix": False})
            m["appels"] += 1
            m["entree"] += entree
            m["sortie"] += sortie
            m["cache"] += cache
            prix = prix_modele(modele, self.surcharges)
            if prix is None:
                m["sans_prix"] = True
            else:
                m["usd"] = round(m["usd"] + cout_usd(prix, entree, sortie, cache), 8)
            for jour in sorted(self._jours)[:-GARDER_JOURS]:
                del self._jours[jour]
            alertes = self._alertes(t)
            self._ecrire_si_utile(t)
        return alertes

    def _total_jour(self, jour):
        return sum(m["usd"] for m in self._jours.get(jour, {}).values()) * self.usd_en_eur

    def _alertes(self, t):
        jour = _jour(t)
        total = self._total_jour(jour)
        dites = self._alertes_dites.setdefault(jour, set())
        sortie = []
        if self.plafond_eur > 0:
            for seuil in (80, 100):
                if total >= self.plafond_eur * seuil / 100 and seuil not in dites:
                    dites.add(seuil)
                    sortie.append((seuil, f"Dépenses Gemini : {total:.2f} € aujourd'hui, {seuil} % du plafond de {self.plafond_eur:.2f} € par jour"))
        for ancien in [j for j in self._alertes_dites if j != jour]:
            del self._alertes_dites[ancien]
        return sortie

    def etat(self, maintenant=None) -> dict:
        t = time.time() if maintenant is None else maintenant
        jour, mois = _jour(t), _jour(t)[:7]
        with self._verrou:
            auj = self._jours.get(jour, {})
            usd_mois = sum(m["usd"] for j, ms in self._jours.items() if j.startswith(mois) for m in ms.values())
            sans_prix = sorted({nom for ms in ([auj] + [v for j, v in self._jours.items() if j.startswith(mois)]) for nom, m in ms.items() if m["sans_prix"]})
            return {"jour_eur": round(self._total_jour(jour), 4), "mois_eur": round(usd_mois * self.usd_en_eur, 4), "plafond_eur": self.plafond_eur, "appels_jour": sum(m["appels"] for m in auj.values()),
                    "entree_jour": sum(m["entree"] for m in auj.values()), "sortie_jour": sum(m["sortie"] for m in auj.values()), "par_modele_jour": {n: dict(m) for n, m in auj.items()}, "sans_prix": sans_prix}

    def resume_parle(self, maintenant=None) -> str:
        e = self.etat(maintenant)
        eur = lambda x: "moins d'un centime" if x < 0.005 else f"environ {x:.2f} euros"  # noqa: E731
        if not e["appels_jour"]:
            texte = f"Aucun appel à Gemini aujourd'hui. Ce mois-ci, {eur(e['mois_eur'])}."
        else:
            pct = f", soit {round(100 * e['jour_eur'] / e['plafond_eur'])} % du plafond de {e['plafond_eur']:g} euros" if e["plafond_eur"] > 0 else ""
            texte = f"Aujourd'hui, Gemini a coûté {eur(e['jour_eur'])} sur {e['appels_jour']} appels{pct}. Ce mois-ci, {eur(e['mois_eur'])}."
        if e["sans_prix"]:
            texte += " Je n'ai pas de tarif pour " + ", ".join(e["sans_prix"]) + " : ces appels ne sont pas chiffrés."
        return texte

    def _charger(self):
        if not self.fichier:
            return
        try:
            with open(self.fichier, encoding="utf-8") as f:
                self._jours = json.load(f).get("jours", {})
        except (OSError, ValueError, AttributeError):
            pass

    def _ecrire_si_utile(self, t, force=False):
        if not self.fichier or (not force and t - self._derniere_ecriture < 30):
            return
        self._derniere_ecriture = t
        try:
            os.makedirs(os.path.dirname(self.fichier), exist_ok=True)
            tmp = self.fichier + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"jours": self._jours}, f, separators=(",", ":"))
            os.replace(tmp, self.fichier)
        except OSError:
            pass

    def enregistrer(self):
        with self._verrou:
            self._ecrire_si_utile(time.time(), force=True)


_compteur = None


def compteur() -> CompteurLLM:
    """Compteur partagé (réglages lus dans jarvis_config.json : prix_llm, plafond_llm_eur_jour, usd_en_eur)."""
    global _compteur
    if _compteur is None:
        cfg = {}
        try:
            with open(os.path.join(RACINE, "jarvis_config.json"), encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, ValueError):
            pass
        _compteur = CompteurLLM(FICHIER, cfg.get("prix_llm") if isinstance(cfg.get("prix_llm"), dict) else None, cfg.get("plafond_llm_eur_jour", PLAFOND_EUR_JOUR), cfg.get("usd_en_eur", USD_EN_EUR))
    return _compteur
