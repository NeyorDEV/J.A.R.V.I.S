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
    "traiter_infos_systeme": "heure / système", "alarmes": "alarmes", "echecs": "échecs",
    "commandes_locales": "commandes", "resoudre_commandes_systeme": "système",
    "resoudre_tv_localement": "télé", "resoudre_temps_localement": "heure mondiale",
    "resoudre_listes_locales": "listes", "resoudre_apps_localement": "applications",
    "resoudre_memoire_locale": "mémoire", "traiter_globe_local": "globe",
}
# Libellés courts (colonne de 8 caractères)
_LIBELLES = {"BIOMETRICS": "VOIX", "SPEAKER": "VOIX", "AV LIVE": "ANTIVIR.", "AV": "ANTIVIR.",
             "VOICE VAULT": "COFFRE", "UNINSTALLER": "DÉSINST.", "CONFIRMATION": "CONFIRM.",
             "AUDIOSTREAMMANAGER": "AUDIO", "IA RELOAD": "IA", "DEEZER CDP": "DEEZER", "DEEZER UIA": "DEEZER",
             "VECTOR DB": "MÉMOIRE", "MEMORY MANAGER": "MÉMOIRE"}
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


_FOND = "#050b12"
_NEON = {"cyan": "#00e5ff", "green": "#3ddc97", "yellow": "#ffb020", "red": "#ff5a5f", "steel_blue": "#3d8bff"}


def _pastille(libelle, style):
    """Libellé en pastille pleine (texte sombre sur la couleur du style) ; vide si pas de libellé."""
    from rich.text import Text
    if not libelle:
        return Text("")
    couleur = style.split()[-1] if style else "grey50"
    return Text(f" {libelle} ", style=f"bold {_FOND} on {_NEON.get(couleur, couleur)}")


def _barre(valeur, largeur=12, couleur="#00e5ff", suffixe=None):
    from rich.text import Text
    pleins = max(0, min(largeur, round(valeur / 100 * largeur)))
    t = Text()
    t.append("▰" * pleins, style=couleur)
    t.append("▱" * (largeur - pleins), style="#1c3140")
    t.append(suffixe if suffixe is not None else f" {valeur:>3.0f} %", style="grey62")
    return t


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
        self.stats = {"local": 0, "ia": 0, "durees": deque(maxlen=20)}  # réponses de la session
        self.alarme = None               # prochaine alarme (texte), relevée dans la veille
        self.gpu = None                  # (utilisation %, VRAM %) échantillonné toutes les 5 s
        self.recents = deque(maxlen=40)  # (texte, instant) des alertes/erreurs affichées : anti-doublon
        self.live = None
        self.fil = deque(maxlen=400)     # rangées du fil (mode tableau plein écran)
        self.tableau = False             # tableau de bord plein écran (sinon fil défilant + bandeau épinglé)
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
                                                 .replace("_locales", "").replace("_locale", "").replace("_", " "))
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
        self._afficher()
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
            self.stats["ia" if e["route"] and not e["route"].startswith("local") else "local"] += 1
            self.stats["durees"].append(time.time() - e["t0"])
            self._rangee("", "JARVIS", texte, meta, style_qui="bold cyan", style_texte="cyan")
        elif e and e["lignes"] and self._suite_jarvis:
            self._rangee("", "", texte, style_texte="cyan")
        else:  # parole spontanée (alarme, accueil, alerte)
            self._afficher()
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
        grille.add_column(width=10, no_wrap=True)
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
        corps = Text(texte, style=style_texte)
        if self.tableau and meta:  # fil étroit : la précision passe sous la phrase
            corps.append("\n" + meta, style="grey50")
            meta = ""
        grille.add_row(heure, _pastille(qui_affiche, style_qui), corps, meta)
        self._afficher(grille)

    def _afficher(self, rangee=None):
        """Écrit une rangée du fil : défilement du terminal, ou mémorisation pour le tableau plein écran."""
        if self.tableau:
            self.fil.append(rangee if rangee is not None else "")
        elif rangee is None:
            self.console.print()
        else:
            self.console.print(rangee)

    def _fil_visible(self, largeur, hauteur):
        """Dernières rangées du fil qui tiennent dans largeur x hauteur (les plus récentes en bas)."""
        from rich.console import Group
        from rich.text import Text
        options = self.console.options.update(width=largeur)
        choisies, total = [], 0
        for r in reversed(list(self.fil)):
            n = len(self.console.render_lines(r, options, pad=False)) if r != "" else 1
            if total + n > hauteur:
                break
            choisies.append(r if r != "" else Text(""))
            total += n
        return Group(*reversed(choisies))

    # ── Bandeau d'état ──────────────────────────────────────────────────────
    def _bandeau(self):
        try:
            if self.tableau:
                return self._ecran()
            if self.console.size.height >= 30 and self.console.size.width >= 100:
                return self._tableau_de_bord()
        except Exception:
            pass
        return self._bandeau_compact()

    def _composants(self):
        """Pièces du tableau de bord : en-tête, panneaux moteurs / voix / ressources, état du micro."""
        from rich import box
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        cy, bl, am, ve, gr = "#00e5ff", "#3d8bff", "#ffb020", "#3ddc97", "grey50"
        speech = sys.modules.get("core.speech")
        parle = bool(speech and (speech.is_speaking or not speech.parole_queue.empty()))
        if not self.pret:
            micro = ("démarrage", gr)
        elif getattr(shared, "MIC_MUTED", False):
            micro = ("micro coupé", "bold #ff5a5f")
        elif parle:
            micro = ("JARVIS parle", f"bold {cy}")
        elif getattr(shared, "is_thinking", False):
            micro = ("réfléchit", f"bold {am}")
        elif getattr(shared, "ETAT_HUD", None) == "listening":
            micro = ("écoute", f"bold {ve}")
        elif getattr(shared, "jarvis_actif", False):
            micro = ("session ouverte", ve)
        else:
            micro = ("veille", gr)
        clients = getattr(shared, "CONNECTED_CLIENTS", set()) - getattr(shared, "CLIENTS_EXTENSION", set())

        tete = Text()
        tete.append(" J.A.R.V.I.S ", style=f"bold {_FOND} on {cy}")
        tete.append("  " + micro[0].upper(), style=micro[1])
        if self.voix and time.time() - self.voix[2] < 600:
            nom, score, _ = self.voix
            tete.append("    locuteur ", style=gr)
            tete.append(f"{'invité' if nom == 'guest' else nom} {score:.2f}".replace(".", ","),
                        style=am if nom == "guest" else "bold white")
        if getattr(shared, "jarvis_actif", False) and speech:
            dernier = max(getattr(shared, "dernier_message", 0), getattr(speech, "dernier_parle_time", 0))
            reste = shared.SESSION_TIMEOUT - (time.time() - dernier)
            tete.append("    session ", style=gr)
            tete.append("en cours" if parle or shared.is_thinking else f"{max(0, int(reste))} s", style="white")
        tete.append("    HUD ", style=gr)
        tete.append(f"{len(clients)} connecté{'s' if len(clients) > 1 else ''}" if clients else "aucun",
                    style="white" if clients else am)
        musique = getattr(shared, "MUSIQUE_EN_COURS", None)
        if musique and musique.get("status") in ("Playing", "Paused") and musique.get("title"):
            tete.append("    musique ", style=gr)
            tete.append(("▶ " if musique["status"] == "Playing" else "❚❚ ")
                        + f"{musique.get('title', '').title()} — {musique.get('artist', '').title()}"[:40], style="white")

        # Moteurs d'IA : actif (a répondu en dernier), pause (quota), prêt, absent
        quotas = None
        try:
            from core.api_quota import _quota_mgr as quotas
        except Exception:
            pass

        def pause_de(cle):
            return quotas.pause_restante(cle) if quotas else 0

        moteurs = Table.grid(padding=(0, 2))
        gem_pause = [pause_de(c) for c in list(getattr(quotas, "_cooldowns", {})) if c.startswith("gemini")]
        gem_pause = max(gem_pause) if gem_pause else 0
        lignes = [("Gemini", self.moteur if self.moteur and self.moteur.startswith("Gemini") else None, gem_pause)]
        try:
            from core.llm_registry import available_engines
            for e in available_engines():
                lignes.append((e.label.split(" (")[0], self.moteur if self.moteur and e.label.split(" ")[0] in self.moteur else None,
                               pause_de(e.name)))
        except Exception:
            pass
        for nom, actif, pause in lignes[:5]:
            if pause > 0:
                etat = Text(f"● pause {pause} s", style=am)
            elif actif:
                etat = Text("● actif", style=ve)
            else:
                etat = Text("● prêt", style=gr)
            moteurs.add_row(Text(nom, style="white"), etat)
        moteurs.add_row(Text("Ollama", style="white"),
                        Text(f"● {self.ollama}", style=ve) if self.ollama else Text("○ libre", style=gr))

        voix = Table.grid(padding=(0, 2))
        voix.add_row(Text("micro", style=gr), Text(micro[0], style=micro[1]))
        voix.add_row(Text("empreinte", style=gr),
                     Text(f"{self.voix[0]} {self.voix[1]:.2f}".replace(".", ","), style="white") if self.voix else Text("—", style=gr))
        voix.add_row(Text("mémoire", style=gr), Text(self._souvenirs(), style="white"))
        voix.add_row(Text("détail", style=gr), Text("jarvis_run.log" if not self.detail else "affiché", style=gr))

        res = Table.grid(padding=(0, 1))
        try:
            import psutil
            res.add_row(Text("CPU", style=gr), _barre(psutil.cpu_percent(None), couleur=cy))
            res.add_row(Text("RAM", style=gr), _barre(psutil.virtual_memory().percent, couleur=bl))
        except Exception:
            pass
        if self.gpu:
            res.add_row(Text("GPU", style=gr), _barre(self.gpu[0], couleur=ve))
            res.add_row(Text("VRAM", style=gr), _barre(self.gpu[1], couleur=am))

        def panneau(titre, corps, couleur):
            return Panel(corps, title=f"[bold {couleur}]{titre}[/]", title_align="left", box=box.ROUNDED,
                         border_style=couleur, padding=(0, 1))

        version = getattr(shared, "CURRENT_VERSION", "")
        entete = Panel(tete, box=box.ROUNDED, border_style=cy, padding=(0, 1),
                       title=f"[bold {cy}]◈ SYSTÈME[/] [grey62]{version}[/]", title_align="left",
                       subtitle=f"[grey62]{time.strftime('%H:%M:%S')}[/]", subtitle_align="right")
        return entete, panneau("MOTEURS D'IA", moteurs, cy), panneau("VOIX", voix, bl), panneau("RESSOURCES", res, ve), micro

    def _tableau_de_bord(self):
        """Bandeau épinglé en bas (mode défilant) : état, puis trois panneaux côte à côte."""
        from rich.console import Group
        from rich.table import Table
        entete, p1, p2, p3, _ = self._composants()
        rangee = Table.grid(expand=True, padding=(0, 1))
        rangee.add_column(ratio=1)
        rangee.add_column(ratio=1)
        rangee.add_column(ratio=1)
        rangee.add_row(p1, p2, p3)
        return Group(entete, rangee)

    def _panneau_session(self):
        from rich import box
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        gr = "grey50"
        audio = sys.modules.get("core.audio_stream")
        niveau = getattr(audio, "NIVEAU_MICRO", 0.0) if audio and self.pret and not getattr(shared, "MIC_MUTED", False) else 0.0
        local, ia = self.stats["local"], self.stats["ia"]
        total = local + ia
        durees = self.stats["durees"]
        moyenne = sum(durees) / len(durees) if durees else 0.0
        lignes = Table.grid(padding=(0, 1))
        lignes.add_row(Text("MIC", style=gr), _barre(niveau * 100, couleur="#00e5ff"))
        lignes.add_row(Text("LOCAL", style=gr), _barre(local / total * 100 if total else 0, couleur="#3ddc97"))
        lignes.add_row(Text("IA", style=gr), _barre(ia / total * 100 if total else 0, couleur="#3d8bff"))
        lignes.add_row(Text("LATENCE", style=gr),
                       _barre(min(100.0, moyenne / 6 * 100), couleur="#ffb020", suffixe=f" {moyenne:.1f} s".replace(".", ",").rjust(6)))
        lignes.add_row(Text("ÉCHANGES", style=gr), Text(str(total), style="white"))
        return Panel(lignes, title="[bold #b388ff]SESSION[/]", title_align="left", box=box.ROUNDED,
                     border_style="#b388ff", padding=(0, 1))

    def _panneau_services(self, compact=False):
        from rich import box
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        ve, am, gr = "#3ddc97", "#ffb020", "grey50"
        clients = getattr(shared, "CONNECTED_CLIENTS", set()) - getattr(shared, "CLIENTS_EXTENSION", set())
        musique = getattr(shared, "MUSIQUE_EN_COURS", None) or {}
        ha = bool(os.getenv("HA_URL", "").strip() and os.getenv("HA_TOKEN", "").strip())
        av = bool(getattr(shared, "AV_LIVE_PROTECTION_ENABLED", False))
        lignes = Table.grid(padding=(0, 2))

        def etat(actif, texte_on, texte_off):
            return Text("● " + texte_on, style=ve) if actif else Text("○ " + texte_off, style=gr)

        lignes.add_row(Text("HUD", style=gr), etat(bool(clients), f"{len(clients)} connecté{'s' if len(clients) > 1 else ''}", "aucun"))
        if not compact:
            lignes.add_row(Text("WebSocket", style=gr), etat(self.pret, "ws://localhost:8765", "démarrage"))
        lignes.add_row(Text("Home Assistant", style=gr), etat(ha, "configuré", "non configuré"))
        lignes.add_row(Text("Antivirus", style=gr), etat(av, "protection active", "inactif"))
        if not compact:
            lignes.add_row(Text("Musique", style=gr),
                           etat(musique.get("status") == "Playing", "lecture", "en pause" if musique.get("status") == "Paused" else "arrêt"))
        lignes.add_row(Text("Alarme", style=gr), Text("● " + self.alarme, style=am) if self.alarme else Text("○ aucune", style=gr))
        return Panel(lignes, title="[bold #ff7ac6]SERVICES[/]", title_align="left", box=box.ROUNDED,
                     border_style="#ff7ac6", padding=(0, 1))

    def _panneaux_bas(self, p1, p2, p3):
        """SESSION puis SERVICES sous les trois premiers panneaux, tant que la hauteur le permet ;
        le dernier est étiré jusqu'en bas pour qu'il ne reste aucun vide."""
        taille = self.console.size
        options = self.console.options.update(width=max(30, taille.width * 2 // 5 - 2))

        def hauteur(p):
            return len(self.console.render_lines(p, options, pad=False))

        libre = taille.height - 4 - sum(hauteur(p) for p in (p1, p2, p3))
        # Priorité aux services ; en version réduite s'il manque de la place, puis la session si elle tient
        services = self._panneau_services()
        if hauteur(services) > libre:
            services = self._panneau_services(compact=True)
        choisis = []
        if hauteur(services) <= libre:
            choisis.append((services, hauteur(services)))
            libre -= choisis[-1][1]
        session = self._panneau_session()
        if hauteur(session) <= libre:
            choisis.append((session, hauteur(session)))
            libre -= choisis[-1][1]
        # Le reste de la hauteur est réparti entre les panneaux ajoutés (plus aucun vide en bas)
        for i, (p, h) in enumerate(choisis):
            part = libre // len(choisis) + (1 if i < libre % len(choisis) else 0)
            p.height = h + part
        return [p for p, _ in choisis]

    def _ecran(self):
        """Tableau de bord plein écran : état en haut, fil encadré à gauche, panneaux à droite."""
        from rich import box
        from rich.console import Group
        from rich.layout import Layout
        from rich.panel import Panel
        from rich.text import Text
        entete, p1, p2, p3, micro = self._composants()
        taille = self.console.size
        largeur_fil = max(30, taille.width * 3 // 5 - 6)
        hauteur_fil = max(3, taille.height - 3 - 1 - 4)
        lay = Layout()
        lay.split_column(Layout(name="haut", size=3), Layout(name="corps"), Layout(name="bas", size=1))
        lay["haut"].update(entete)
        lay["corps"].split_row(
            Layout(Panel(self._fil_visible(largeur_fil, hauteur_fil), box=box.ROUNDED, border_style="#3d8bff",
                         padding=(1, 2), title="[bold #3d8bff]FIL DES ÉCHANGES[/]", title_align="left"), ratio=3),
            Layout(Group(*([p1, p2, p3] + self._panneaux_bas(p1, p2, p3))), ratio=2, minimum_size=38))
        rouet = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"[int(time.time() * 8) % 10]
        lay["bas"].update(Text(f" {rouet} {micro[0]}   ·   journal complet : data/jarvis_run.log   ·   Ctrl+C pour quitter",
                               style="grey50"))
        return lay

    @staticmethod
    def _souvenirs():
        try:
            vm = sys.modules.get("module.vector_memory")
            n = vm._collection.count() if vm and getattr(vm, "_collection", None) else None
            return f"{n} souvenirs" if n is not None else "—"
        except Exception:
            return "—"

    def _bandeau_compact(self):
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
                restant = _quota_mgr.pause_restante(api)
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
            taille = self.console.size
            self.tableau = _tableau_demande() and taille.height >= 30 and taille.width >= 100
            self.live = Live(get_renderable=self._bandeau, console=self.console, refresh_per_second=4 if self.tableau else 2,
                             transient=True, screen=self.tableau, redirect_stdout=False, redirect_stderr=False)
            self.live.start()
        threading.Thread(target=self._veille, daemon=True, name="console-veille").start()
        atexit.register(self.arreter)

    def arreter(self):
        try:
            if self.live:
                self.live.stop()
                self.live = None
                if self.tableau:  # l'écran alternatif disparaît : le fil reste dans l'historique du terminal
                    self.tableau = False
                    for r in self.fil:
                        self.console.print(r)
        except Exception:
            pass

    def _veille(self):
        dernier_sondage = dernier_gpu = dernier_alarme = 0
        while True:
            time.sleep(0.5)
            with self.lock:
                if self.attente and time.time() - self.attente[1] > 1.5:
                    self._vider_attente()
            if time.time() - dernier_alarme > 10:
                dernier_alarme = time.time()
                self.alarme = self._prochaine_alarme()
            if time.time() - dernier_gpu > 5:
                dernier_gpu = time.time()
                self.gpu = self._sonder_gpu()
            if time.time() - dernier_sondage > 15:
                dernier_sondage = time.time()
                self.ollama = self._sonder_ollama()

    @staticmethod
    def _prochaine_alarme():
        try:
            from datetime import datetime
            am = sys.modules.get("module.alarm_manager")
            if not am:
                return None
            actives = [a for a in am._charger_alarmes() if not a.get("sonne")]
            if not actives:
                return None
            a = min(actives, key=lambda x: x["heure"])
            return datetime.fromisoformat(a["heure"]).strftime("%H:%M")
        except Exception:
            return None

    @staticmethod
    def _sonder_gpu():
        try:
            import subprocess
            sortie = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.splitlines()[0]
            util, utilisee, totale = (float(x) for x in sortie.split(","))
            return util, utilisee / totale * 100
        except Exception:
            return None

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


def _tableau_demande():
    """Tableau plein écran (fil encadré + panneaux) ; « console_tableau »: false dans jarvis_config.json
    ou JARVIS_CONSOLE_TABLEAU=0 pour garder le fil défilant dans le terminal."""
    if os.environ.get("JARVIS_CONSOLE_TABLEAU", "").strip() in ("0", "false", "non"):
        return False
    try:
        with open(os.path.join(shared.RACINE_PROJET, "jarvis_config.json"), encoding="utf-8") as f:
            return bool(json.load(f).get("console_tableau", True))
    except Exception:
        return True


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
