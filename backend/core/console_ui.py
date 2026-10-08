"""Console du terminal : tableau de bord en direct et fil des échanges (rich).

installer_console() (tout début de main.py) remplace builtins.print, sys.stdout et sys.stderr :
chaque ligne écrite par JARVIS ou une bibliothèque passe par _Console.ligne(), qui
  - l'écrit telle quelle, horodatée, dans data/jarvis_run.log (journal complet) ;
  - la classe : échange (ce que dit la personne / ce que répond JARVIS), événement essentiel
    (action notable, avertissement, erreur) ou détail technique ;
  - n'affiche que les deux premiers. « "console_detail": true » dans jarvis_config.json (ou la
    variable d'environnement JARVIS_CONSOLE_DETAIL=1) réaffiche tout le détail.
Un bandeau d'état (micro, voix reconnue, session, moteur IA, moteurs en pause, musique,
Ollama, CPU/RAM, HUD) reste épinglé en bas du terminal et se rafraîchit en direct ; le fil
défile au-dessus, l'historique du terminal reste consultable et copiable.

Étiquettes reconnues dans les print() du projet :
  « [DIT] »                          phrase prononcée par JARVIS (core/speech.parler)
  « [VAD ENTENDU] », « [HUD] Commande clavier : »   phrase de l'utilisateur
  « [SPEAKER] »                      voix reconnue (nom, similarité)
  « [DEBUG] Commande résolue par », « [CERVEAU] Essai modele », « [CERVEAU] Tentative avec »,
  « [OLLAMA] Essai modele local », « [INTENT] Fonction choisie »   qui a répondu
"""

import atexit
import json
import os
import re
import sys
import threading
import time
from collections import deque

import core.shared as shared

# Étiquette en début de ligne, éventuellement précédée d'un symbole (« 🎙  [SPEAKER] … »)
_RE_TAG = re.compile(r"^\s*([^\[\w]{0,8}?)\s*\[([^\]\n]{1,40})\]\s?(.*)$", re.S)
_RE_ERREUR = re.compile(r"❌|\b(erreur|error|échec|echec|exception|traceback|impossible|introuvable|failed|fatal)\b",
                        re.I)
_RE_ALERTE = re.compile(r"⚠|\b(quota|avertissement|warning|indisponible|limite atteinte|hors[- ]ligne|offline|refusé)\b",
                        re.I)
# Étiquettes toujours affichées (actions notables)
_ESSENTIELS = {"ALARME", "CONFIRMATION", "CONFIRM", "AUDIT", "AV LIVE", "AV", "UPDATE", "SERVICES",
               "UNINSTALLER", "WINGET", "VOICE VAULT", "BIOMETRICS", "QUOTA"}
# Noms lisibles des resolvers locaux (« [DEBUG] Commande résolue par : … »)
_RESOLVEURS = {
    "resoudre_infos_systeme_localement": "heure / système", "alarmes": "alarmes", "echecs": "échecs",
    "commandes_locales": "commandes", "resoudre_commandes_systeme": "système",
    "resoudre_tv_localement": "télé", "resoudre_temps_localement": "heure mondiale",
    "resoudre_listes_locales": "listes", "resoudre_apps_localement": "applications",
    "resoudre_memoire_locale": "mémoire", "resoudre_globe_localement": "globe",
}
# Libellés courts (colonne de 8 caractères)
_LIBELLES = {"BIOMETRICS": "VOIX", "SPEAKER": "VOIX", "AV LIVE": "ANTIVIR.", "AV": "ANTIVIR.",
             "VOICE VAULT": "COFFRE", "UNINSTALLER": "DÉSINST.", "CONFIRMATION": "CONFIRM.",
             "AUDIOSTREAMMANAGER": "AUDIO", "IA RELOAD": "IA", "DEEZER CDP": "DEEZER", "DEEZER UIA": "DEEZER",
             "VECTOR DB": "MÉMOIRE", "MEMORY MANAGER": "MÉMOIRE", "WAKEWORD": "ÉVEIL"}
# Annonces de JARVIS sur la voix reconnue : pas la réponse à la question
_RE_ANNONCE_VOIX = re.compile(r"^(voix inconnue détectée|voix de .{1,30} détectée)", re.I)
# Couleurs : une pour l'utilisateur (doré), une pour JARVIS (cyan) ; modules et événements
# techniques en gris-bleu discret, à ne pas confondre avec les échanges.
_STYLE_UTILISATEUR = "bold gold1"


def _nom_moteur(brut):
    """« gemini-3.5-flash-lite (Streaming)... » → « Gemini 3.5 Flash-Lite »."""
    brut = re.sub(r"\s*\((streaming|flux)\).*$", "", brut.strip(), flags=re.I).rstrip(". ")
    if brut.lower().startswith("gemini"):
        mots = brut.split("-")
        nom = " ".join(m.capitalize() if not m[:1].isdigit() else m for m in mots)
        return nom.replace("Flash Lite", "Flash-Lite")
    return brut


def _duree(s):
    return f"{s:.1f} s".replace(".", ",")


class _Console:
    def __init__(self, detail, chemin_journal):
        from rich.console import Console
        self.detail = detail
        self.console = Console(file=sys.__stdout__, highlight=False, soft_wrap=False)
        self.lock = threading.RLock()
        self.journal = None
        try:
            os.makedirs(os.path.dirname(chemin_journal), exist_ok=True)
            self.journal = open(chemin_journal, "w", encoding="utf-8", errors="replace")
        except Exception:
            pass
        self.pret = False                # boucle d'écoute démarrée
        self.attente = None              # (texte, instant) : phrase entendue, voix pas encore identifiée
        self.echange = None              # échange en cours : t0, route, intention, lignes, qui
        self.voix = None                 # (nom, score, instant)
        self.moteur = None               # dernier moteur ayant répondu
        self.ollama = None               # modèle Ollama chargé en mémoire vidéo (sondé)
        self.recents = deque(maxlen=40)  # (texte, instant) des alertes/erreurs affichées : anti-doublon
        self.live = None
        self._suite_jarvis = False       # la dernière rangée affichée est une phrase de JARVIS
        self._derniere = ("", 0.0)       # (libellé, instant) de la dernière rangée : pas de répétition

    # ── Entrée de toutes les sorties ────────────────────────────────────────
    def ligne(self, texte, source="stdout"):
        for brut in str(texte).splitlines():
            if not brut.strip():
                continue
            with self.lock:
                self._journaliser(brut)
                try:
                    self._traiter(brut, source)
                except Exception as e:  # la console ne doit jamais faire tomber JARVIS
                    self._journaliser(f"[CONSOLE] Erreur d'affichage : {e}")

    def _journaliser(self, brut):
        if self.journal:
            try:
                t = time.time()
                self.journal.write(f"{time.strftime('%H:%M:%S', time.localtime(t))}.{int(t % 1 * 1000):03d} {brut}\n")
                self.journal.flush()
            except Exception:
                pass

    # ── Classement ──────────────────────────────────────────────────────────
    def _traiter(self, brut, source):
        m = _RE_TAG.match(brut)
        symbole, tag, reste = (m.group(1).strip(), m.group(2).strip(), m.group(3).strip()) if m else ("", "", brut.strip())
        TAG = tag.upper()
        bas = brut.lower()

        # Échanges
        if TAG == "DIT":
            return self._jarvis(reste)
        if TAG == "VAD ENTENDU":
            self._vider_attente()
            self.attente = (reste, time.time())
            return
        if TAG == "HUD" and reste.lower().startswith("commande clavier"):
            self._vider_attente()
            return self._utilisateur(reste.split(":", 1)[-1].strip(), "CLAVIER", None)
        if TAG == "SPEAKER":
            self._noter_voix(reste)
            if not self.detail:
                return
        # Qui répond (sert à l'échange en cours et au bandeau)
        self._noter_route(TAG, reste)

        if "streaming vad actif" in bas and not self.pret:
            self.pret = True
            return self._rangee("", "PRÊT", "J'écoute : dites « Jarvis », ou écrivez dans le HUD.",
                                style_qui="bold green", style_texte="green")

        # Niveau
        if (source == "stderr" and not tag) or _RE_ERREUR.search(brut):
            # Échec d'un modèle suivi d'une bascule sur le suivant : avertissement, pas erreur
            niveau = "alerte" if TAG in ("CERVEAU", "OLLAMA", "STT") else "erreur"
        elif _RE_ALERTE.search(brut) and "en cooldown" not in bas \
                and not (TAG == "CERVEAU" and "quota" in bas):  # pauses : bandeau + ligne [QUOTA]
            niveau = "alerte"
        elif TAG in _ESSENTIELS or (TAG == "JARVIS" and "interruption" in bas) \
                or ("✔" in brut and not self.pret):
            niveau = "info"
        else:
            niveau = "detail"

        if niveau in ("erreur", "alerte"):
            maintenant = time.time()
            cle = re.sub(r"[^\w]+", " ", bas).strip()
            if any(t == cle and maintenant - i < 10 for t, i in self.recents):
                return  # même message il y a moins de 10 s
            self.recents.append((cle, maintenant))
        if niveau == "detail" and not self.detail:
            return

        texte = re.sub(r"^\s*(?:[✔⚠❌⚡]\ufe0f?\s*)+", "", reste if tag else brut.strip())
        texte = re.sub(r"\s{2,}", " ", texte)
        if TAG == "JARVIS" and "interruption" in bas:
            return self._rangee(time.strftime("%H:%M:%S"), "■ STOP", "Parole interrompue.", style_qui="bold yellow",
                                style_texte="yellow")
        etiquette = _LIBELLES.get(TAG, TAG or ("ERREUR" if niveau == "erreur" else ""))[:8]
        styles = {"erreur": ("bold red", "red"), "alerte": ("bold yellow", "yellow"),
                  "info": ("steel_blue", "grey70"), "detail": ("grey42", "grey50")}[niveau]
        self._rangee(time.strftime("%H:%M:%S"), etiquette, texte, style_qui=styles[0], style_texte=styles[1])

    def _noter_voix(self, reste):
        m = re.search(r"authentifié\s*:\s*([\w-]+).*?([\d.]+)\)", reste) \
            or re.search(r"^([\w-]+) maintenu \(Similarité ([\d.]+)", reste)
        if m:
            self.voix = (m.group(1), float(m.group(2)), time.time())
        else:
            m = re.search(r"inconnu.*?([\d.]+)\)", reste)
            if m:
                self.voix = ("guest", float(m.group(1)), time.time())
        if self.attente:
            texte, t = self.attente
            self.attente = None
            self._utilisateur(texte, self.voix[0] if self.voix else None, self.voix[1] if self.voix else None, t)

    def _noter_route(self, TAG, reste):
        route = None
        if TAG == "DEBUG" and "résolue par" in reste:
            nom = reste.split(":", 1)[-1].strip()
            route = "local · " + _RESOLVEURS.get(nom, nom.replace("resoudre_", "").replace("_localement", "")
                                                 .replace("_locale", "").replace("_", " "))
        elif TAG == "CERVEAU" and "essai modele" in reste.lower():
            route = _nom_moteur(reste.split(":", 1)[-1])
        elif TAG == "CERVEAU" and reste.lower().startswith("tentative avec"):
            route = reste[len("tentative avec"):].strip(" .")
        elif TAG == "OLLAMA" and "essai modele local" in reste.lower():
            route = "Ollama " + reste.split(":", 1)[-1].strip()
        elif TAG == "INTENT" and "fonction choisie" in reste.lower() and self.echange:
            self.echange["intention"] = True
        if route and self.echange and not self.echange["lignes"]:
            self.echange["route"] = route

    # ── Affichage des échanges ──────────────────────────────────────────────
    @staticmethod
    def _personne(nom):
        """Libellé de la personne qui parle ; une seule couleur pour l'utilisateur, quel qu'il soit."""
        if not nom:
            libelle = "VOUS"
        elif nom == "CLAVIER":
            libelle = "CLAVIER"
        elif nom == "guest":
            libelle = "INVITÉ"
        else:
            libelle = nom.upper()[:8]
        return libelle, _STYLE_UTILISATEUR

    def _utilisateur(self, texte, nom, score, instant=None):
        instant = instant or time.time()
        qui, style = self._personne(nom)
        self.console.print()
        meta = f"voix {score:.2f}".replace(".", ",") if score is not None and nom != "CLAVIER" else ""
        self._rangee(time.strftime("%H:%M:%S", time.localtime(instant)), qui, f"› {texte}", meta,
                     style_qui=style, style_texte="bold white")
        self.echange = {"t0": instant, "route": None, "intention": False, "lignes": 0}

    def _vider_attente(self):
        """Phrase entendue dont la voix n'a pas été identifiée (biométrie absente ou lente)."""
        if self.attente:
            texte, t = self.attente
            self.attente = None
            self._utilisateur(texte, None, None, t)

    def _jarvis(self, texte):
        self._vider_attente()
        if _RE_ANNONCE_VOIX.match(texte):
            return self._rangee(time.strftime("%H:%M:%S"), "VOIX", texte, style_qui="grey62", style_texte="grey62")
        e = self.echange
        if e and e["lignes"] == 0 and time.time() - e["t0"] < 60:
            route = e["route"] or "local"
            if e["intention"]:
                route = "intention → " + route
            meta = f"{route} · {_duree(time.time() - e['t0'])}"
            if e["route"] and not e["route"].startswith("local"):
                self.moteur = e["route"]
            self._rangee("", "JARVIS", texte, meta, style_qui="bold cyan", style_texte="cyan")
        elif e and e["lignes"] and self._suite_jarvis:
            self._rangee("", "", texte, style_texte="cyan")
        else:  # parole spontanée (alarme, accueil, alerte)
            self.console.print()
            self._rangee(time.strftime("%H:%M:%S"), "JARVIS", texte, style_qui="bold cyan", style_texte="cyan")
            self.echange = {"t0": time.time(), "route": None, "intention": False, "lignes": 0}
        if self.echange:
            self.echange["lignes"] += 1
        self._suite_jarvis = True

    def _rangee(self, heure, qui, texte, meta="", style_qui="", style_texte=""):
        from rich.table import Table
        from rich.text import Text
        grille = Table.grid(expand=True, padding=(0, 1))
        grille.add_column(width=8, no_wrap=True, style="grey50")
        grille.add_column(width=8, no_wrap=True)
        grille.add_column(ratio=1, overflow="fold")
        grille.add_column(no_wrap=True, justify="right", style="grey50")
        # Rangées successives de même libellé (erreur sur plusieurs lignes…) : libellé et heure une fois
        maintenant = time.time()
        qui_affiche = qui
        if qui and qui == self._derniere[0] and qui != "JARVIS" and maintenant - self._derniere[1] < 2:
            heure, qui_affiche = "", ""
        if qui:
            self._derniere = (qui, maintenant)
        self._suite_jarvis = False
        grille.add_row(heure, Text(qui_affiche, style=style_qui), Text(texte, style=style_texte), meta)
        self.console.print(grille)

    # ── Bandeau d'état ──────────────────────────────────────────────────────
    def _bandeau(self):
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        def segment(t, etiquette, valeur, style=""):
            t.append(f"{etiquette} ", style="grey62")
            t.append(valeur, style=style)
            t.append("    ")

        speech = sys.modules.get("core.speech")
        parle = bool(speech and (speech.is_speaking or not speech.parole_queue.empty()))
        l1, l2, l3 = Text(), Text(), Text()

        if not self.pret:
            micro = ("… démarrage", "grey62")
        elif getattr(shared, "MIC_MUTED", False):
            micro = ("✕ coupé", "bold red")
        elif parle:
            micro = ("▶ parle", "bold cyan")
        elif getattr(shared, "is_thinking", False):
            micro = ("◐ réfléchit", "bold yellow")
        elif getattr(shared, "ETAT_HUD", None) == "listening":
            micro = ("● écoute", "bold green")
        elif getattr(shared, "jarvis_actif", False):
            micro = ("● session", "green")
        else:
            micro = ("○ veille", "grey62")
        segment(l1, "MICRO", *micro)
        if self.voix and time.time() - self.voix[2] < 600:
            nom, score, _ = self.voix
            segment(l1, "VOIX", f"{'invité' if nom == 'guest' else nom} {score:.2f}".replace(".", ","),
                    "yellow" if nom == "guest" else "bold white")
        if getattr(shared, "jarvis_actif", False):
            dernier = max(getattr(shared, "dernier_message", 0), getattr(speech, "dernier_parle_time", 0) if speech else 0)
            reste = shared.SESSION_TIMEOUT - (time.time() - dernier)
            segment(l1, "SESSION", "en cours" if parle or shared.is_thinking else f"{max(0, int(reste))} s", "white")
        clients = getattr(shared, "CONNECTED_CLIENTS", set()) - getattr(shared, "CLIENTS_EXTENSION", set())
        segment(l1, "HUD", f"{len(clients)} connecté{'s' if len(clients) > 1 else ''}" if clients else "aucun",
                "white" if clients else "yellow")

        segment(l2, "IA", self.moteur or "—", "bold white")
        pauses = []
        try:
            from core.api_quota import _quota_mgr
            for api in list(_quota_mgr._cooldowns):
                restant = _quota_mgr.remaining_cooldown(api)
                if restant > 0:
                    pauses.append(f"{api[7:] if api.startswith('gemini_') else api.upper()} {restant} s")
        except Exception:
            pass
        if pauses:
            segment(l2, "EN PAUSE", " · ".join(pauses[:3]), "yellow")
        try:
            import psutil
            segment(l2, "CPU", f"{psutil.cpu_percent(None):.0f} %", "white")
            segment(l2, "RAM", f"{psutil.virtual_memory().percent:.0f} %", "white")
        except Exception:
            pass

        musique = getattr(shared, "MUSIQUE_EN_COURS", None)
        if musique and musique.get("status") in ("Playing", "Paused") and musique.get("title"):
            titre = f"{musique.get('title', '').title()} — {musique.get('artist', '').title()}"[:48]
            segment(l3, "MUSIQUE", ("▶ " if musique["status"] == "Playing" else "❚❚ ") + titre,
                    "bold white" if musique["status"] == "Playing" else "white")
        else:
            segment(l3, "MUSIQUE", "■ —", "grey62")
        segment(l3, "OLLAMA", f"● {self.ollama}" if self.ollama else "○ libre", "green" if self.ollama else "grey62")
        if not self.detail:
            segment(l3, "DÉTAIL", "data/jarvis_run.log", "grey62")

        corps = Table.grid()
        for ligne in (l1, l2, l3):
            corps.add_row(ligne)
        version = getattr(shared, "CURRENT_VERSION", "")
        return Panel(corps, title=f"[bold cyan]J.A.R.V.I.S[/] [grey62]{version}[/]",
                     title_align="left", border_style="cyan", padding=(0, 1),
                     subtitle=f"[grey62]{time.strftime('%H:%M:%S')}[/]", subtitle_align="right")

    # ── Tâches de fond ──────────────────────────────────────────────────────
    def demarrer(self):
        if self.console.is_terminal:
            from rich.live import Live
            self.live = Live(get_renderable=self._bandeau, console=self.console, refresh_per_second=2,
                             transient=True, redirect_stdout=False, redirect_stderr=False)
            self.live.start()
        threading.Thread(target=self._veille, daemon=True, name="console-veille").start()
        atexit.register(self.arreter)

    def arreter(self):
        try:
            if self.live:
                self.live.stop()
        except Exception:
            pass

    def _veille(self):
        dernier_sondage = 0
        while True:
            time.sleep(0.5)
            with self.lock:
                if self.attente and time.time() - self.attente[1] > 1.5:
                    self._vider_attente()
            if time.time() - dernier_sondage > 15:
                dernier_sondage = time.time()
                self.ollama = self._sonder_ollama()

    @staticmethod
    def _sonder_ollama():
        try:
            import urllib.request
            url = getattr(shared, "OLLAMA_URL", "http://127.0.0.1:11434") + "/api/ps"
            with urllib.request.urlopen(url, timeout=0.5) as r:
                modeles = json.load(r).get("models", [])
            return ", ".join(m.get("name", "?") for m in modeles) or None
        except Exception:
            return None


class _Flux:
    """Remplace sys.stdout / sys.stderr : les lignes écrites directement (bibliothèques,
    tracebacks) suivent le même chemin que print()."""

    def __init__(self, console, source):
        self._console = console
        self._source = source
        self._tampon = ""
        self.encoding = "utf-8"

    def write(self, s):
        self._tampon += str(s)
        if "\n" in self._tampon:
            *lignes, self._tampon = self._tampon.split("\n")
            for l in lignes:
                self._console.ligne(l, self._source)
        return len(s)

    def flush(self):
        pass

    def reconfigure(self, **kwargs):
        pass

    @property
    def buffer(self):
        return (sys.__stderr__ if self._source == "stderr" else sys.__stdout__).buffer

    def isatty(self):
        return False  # pas de barres de progression animées dans le fil

    def fileno(self):
        return (sys.__stderr__ if self._source == "stderr" else sys.__stdout__).fileno()


_CONSOLE = None


def _detail_demande():
    if os.environ.get("JARVIS_CONSOLE_DETAIL", "").strip() in ("1", "true", "oui"):
        return True
    try:
        with open(os.path.join(shared.RACINE_PROJET, "jarvis_config.json"), encoding="utf-8") as f:
            return bool(json.load(f).get("console_detail", False))
    except Exception:
        return False


def installer_console():
    """Installe la console (appelé tout au début de main.py, avant les imports lourds)."""
    global _CONSOLE
    import builtins
    try:
        _CONSOLE = _Console(_detail_demande(), os.path.join(shared.RACINE_PROJET, "data", "jarvis_run.log"))
    except Exception as e:  # rich absent : console brute
        print(f"[CONSOLE] Tableau de bord indisponible ({e}) : sortie brute.")
        return
    print_original = builtins.print

    def _print(*args, sep=" ", end="\n", file=None, flush=False):
        if file is not None and file not in (sys.stdout, sys.stderr, sys.__stdout__, sys.__stderr__):
            return print_original(*args, sep=sep, end=end, file=file, flush=flush)
        _CONSOLE.ligne(sep.join(str(a) for a in args),
                       "stderr" if file in (sys.stderr, sys.__stderr__) else "stdout")

    builtins.print = _print
    sys.stdout = _Flux(_CONSOLE, "stdout")
    sys.stderr = _Flux(_CONSOLE, "stderr")
    _CONSOLE.console.print()
    _CONSOLE.console.rule(f"[bold cyan]J.A.R.V.I.S[/]  [grey62]{getattr(shared, 'CURRENT_VERSION', '')} · démarrage[/]",
                          style="cyan")
    _CONSOLE.demarrer()
