"""
visual_web_agent.py — Autopilote IA Visuel Universel de JARVIS
================================================================
Utilise Playwright en mode headful (navigateur visible) + Gemini Vision
pour accomplir n'importe quelle tâche complexe sur le web de façon autonome.

Flux : LLM Planning → Boucle (Screenshot → Vision → Action → Confirm) → Résultat vocal
"""

import asyncio
import base64
import json
import os
import re
import builtins
from pathlib import Path
from PIL import Image
from dotenv import load_dotenv
from core.interlocuteur import nom_espace, nom_ou_utilisateur, nom_virgule

try:
    from playwright.async_api import async_playwright, Page, BrowserContext
except ImportError:
    async_playwright = None

load_dotenv()

# --- Chemin vers Opera GX ---
# (chemin construit pour le compte courant : il était écrit en dur pour un seul compte Windows)
OPERA_GX_PATH = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Opera GX", "opera.exe")
OPERA_GX_PROFILE_PATH = os.path.expandvars(r"%APPDATA%\Opera Software\Opera GX Stable")

# --- Constantes ---
MAX_STEPS     = 18   # Nombre max d'étapes avant de s'arrêter
MAX_RETRIES   = 3    # Retries par étape en cas d'échec vision
STEP_DELAY    = 1.2  # Secondes entre chaque étape
SCREENSHOT_W  = 1440
SCREENSHOT_H  = 900


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _b64_screenshot(screenshot_bytes: bytes) -> str:
    """Encode les bytes d'un screenshot en base64."""
    return base64.b64encode(screenshot_bytes).decode("utf-8")


def _extract_json(text: str) -> dict | None:
    """Extrait le premier bloc JSON valide d'un texte."""
    try:
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass
    # Fallback : chercher un tableau JSON
    try:
        start = text.find("[")
        end   = text.rfind("]") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass
    return None


def _dire(msg: str):
    """Appelle la fonction parler() de JARVIS si disponible."""
    try:
        parler_fn = builtins.parler
        if parler_fn:
            parler_fn(msg)
    except Exception:
        pass
    print(f"[VISUAL_AGENT] 🔊 {msg}")


# ---------------------------------------------------------------------------
# VisualWebAgent
# ---------------------------------------------------------------------------

class VisualWebAgent:
    """
    Agent web autonome et visuel.
    Lance Opera GX en mode visible, exécute des tâches complexes étape par étape
    en utilisant Gemini Vision pour analyser l'écran à chaque action.
    """

    def __init__(self):
        self.browser   = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self._pw       = None
        self._running  = False

        # Accès au client Gemini via builtins (injecté par main2.py)
        self.client       = None
        self.chosen_model = None

    def _init_gemini(self):
        """Récupère le client Gemini depuis les builtins de JARVIS."""
        try:
            self.client       = builtins.client
            self.chosen_model = builtins.CHOSEN_MODEL
        except AttributeError:
            print("[VISUAL_AGENT] ⚠️  Client Gemini non trouvé dans builtins.")

    # -----------------------------------------------------------------------
    # Browser lifecycle
    # -----------------------------------------------------------------------

    async def _start_browser(self):
        """Démarre Opera GX en mode headful (visible) et maximisé avec l'extension J.A.R.V.I.S."""
        # Vérifier si le navigateur existant est toujours vivant et connecté
        is_alive = False
        if self.context:
            try:
                pages = self.context.pages
                if pages:
                    # Tenter d'obtenir l'URL pour s'assurer que la connexion websocket Playwright est vivante
                    _ = pages[0].url
                    is_alive = True
            except Exception:
                pass
                
        if is_alive:
            return
            
        # Si le navigateur précédent est mort ou déconnecté, réinitialiser proprement
        print("[VISUAL_AGENT] 🔄 Le navigateur précédent est fermé ou déconnecté. Réinitialisation complète...")
        await self._stop_browser()

        self._pw = await async_playwright().start()

        opera_exists = os.path.exists(OPERA_GX_PATH)
        profile_exists = os.path.exists(OPERA_GX_PROFILE_PATH)
        
        # Chemin absolu vers l'extension Chrome de JARVIS
        # L'extension est dans interfaces/chrome_extension (le chemin visait backend/chrome_extension, inexistant)
        extension_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "interfaces", "chrome_extension"))

        launch_kwargs = dict(
            headless=False,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-default-browser-check",
                f"--disable-extensions-except={extension_path}",
                f"--load-extension={extension_path}",
            ],
            slow_mo=60,
        )
        if opera_exists:
            launch_kwargs["executable_path"] = OPERA_GX_PATH
            print(f"[VISUAL_AGENT] 🌐 Lancement Opera GX : {OPERA_GX_PATH}")
        else:
            print("[VISUAL_AGENT] ⚠️  Opera GX introuvable, fallback Chromium")

        if profile_exists:
            print(f"[VISUAL_AGENT] 🍪 Tentative d'utilisation du profil Opera GX d'origine : {OPERA_GX_PROFILE_PATH}")
            try:
                self.context = await self._pw.chromium.launch_persistent_context(
                    user_data_dir=OPERA_GX_PROFILE_PATH,
                    no_viewport=True, # Permet au navigateur de maximiser à 100% de l'écran nativement
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    ),
                    locale="fr-FR",
                    extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"},
                    **launch_kwargs
                )
                # Évite d'écraser les onglets de session restaurés de neyor
                blank_page = None
                for p in self.context.pages:
                    if p.url == "about:blank":
                        blank_page = p
                        break
                if blank_page:
                    self.page = blank_page
                else:
                    self.page = await self.context.new_page()

                print("[VISUAL_AGENT] ✅ Navigateur d'origine Opera GX prêt (avec cookies/paramètres de Neyor sur un onglet dédié).")
                return
            except Exception as e:
                print(f"[VISUAL_AGENT] ⚠️ Profil principal verrouillé (Opera GX est probablement déjà ouvert) : {e}")
                print("[VISUAL_AGENT] 🔄 Fallback temporaire dans une session propre pour éviter le blocage...")

        # Fallback si le profil est verrouillé ou indisponible
        self.browser = await self._pw.chromium.launch(**launch_kwargs)
        self.context = await self.browser.new_context(
            no_viewport=True, # Laisse le navigateur maximiser
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="fr-FR",
            extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"},
        )
        self.page = await self.context.new_page()
        print("[VISUAL_AGENT] ✅ Navigateur prêt (session de secours).")

    async def _stop_browser(self):
        """Ferme proprement le navigateur."""
        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass
        try:
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass
        self.browser = self.context = self.page = self._pw = None

    async def stop(self):
        """Arrête l'agent et ferme le navigateur."""
        self._running = False
        await self._stop_browser()
        print("[VISUAL_AGENT] 🛑 Agent arrêté.")

    # -----------------------------------------------------------------------
    # Popups / cookies
    # -----------------------------------------------------------------------

    async def _handle_popups(self):
        """Tente de fermer les popups classiques de cookies / consentement."""
        selectors = [
            "button:has-text('Tout accepter')",
            "button:has-text('Accepter tout')",
            "button:has-text('Accepter')",
            "button:has-text('J\\'accepte')",
            "button:has-text('Accept all')",
            "button:has-text('I agree')",
            "button:has-text('Agree')",
            "button:has-text('Autoriser')",
            "#L2AGLb",
            "[aria-label='Tout accepter']",
            "[data-cookiefirst-action='accept']",
            ".didomi-continue-without-agreeing",
        ]
        for sel in selectors:
            try:
                if await self.page.is_visible(sel, timeout=800):
                    await self.page.click(sel)
                    print(f"[VISUAL_AGENT] 🍪 Popup fermée : {sel}")
                    await asyncio.sleep(0.5)
                    break
            except Exception:
                pass

    # -----------------------------------------------------------------------
    # Vision : analyse d'un screenshot avec Gemini
    # -----------------------------------------------------------------------

    async def _screenshot_b64(self) -> tuple[bytes, str]:
        """Capture l'écran et retourne (bytes, base64_str)."""
        raw = await self.page.screenshot(type="jpeg", quality=85)
        return raw, _b64_screenshot(raw)

    async def _vision_find_element(self, instruction: str) -> dict | None:
        """
        Demande à Gemini Vision de localiser un élément sur la page.
        Retourne {"box": [ymin, xmin, ymax, xmax], "description": "...", "found": true/false} ou None.
        """
        if not self.client:
            return None
        
        # Obtenir les dimensions réelles de la page
        try:
            viewport = await self.page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })")
            width = viewport["width"]
            height = viewport["height"]
        except Exception:
            width = SCREENSHOT_W
            height = SCREENSHOT_H

        try:
            raw, b64 = await self._screenshot_b64()
            import io
            img = Image.open(io.BytesIO(raw))
        except Exception:
            # Fallback : sauvegarder en fichier temporaire
            raw = await self.page.screenshot(type="jpeg", quality=85)
            tmp = Path("jarvis_agent_tmp.jpg")
            tmp.write_bytes(raw)
            img = Image.open(tmp)

        prompt = (
            f"Tu es l'œil de JARVIS. Voici une capture de page web ({width}x{height}px).\n"
            f"Instruction : {instruction}\n"
            "Localise précisément l'élément demandé (bouton, champ, lien, icône, case à cocher).\n"
            "Réponds UNIQUEMENT en JSON : {\"box\": [ymin, xmin, ymax, xmax], \"description\": \"...\", \"found\": true/false}\n"
            "Les coordonnées sont normalisées de 0 à 1000 (0=haut-gauche, 1000=bas-droite).\n"
            "Si l'élément n'est pas visible, retourne {\"found\": false, \"description\": \"raison\"}.\n"
            "CONSIGNES CLÉS :\n"
            "- Sois très souple sur les correspondances de texte : si l'instruction demande 'le filtre Spa' et que la page affiche 'Spa et centre de bien-être', c'est le bon élément ! Marque 'found': true et retourne la box de la case à cocher ou de son texte.\n"
            "- Pour les filtres ou cases à cocher, cible précisément le carré à cocher ou le texte cliquable adjacent."
        )

        try:
            response = self.client.models.generate_content(
                model=self.chosen_model,
                contents=[prompt, img]
            )
            data = _extract_json(response.text.strip())
            if data:
                print(f"[VISUAL_AGENT] 👁️  Vision : {data.get('description', '?')}")
            return data
        except Exception as e:
            print(f"[VISUAL_AGENT] ⚠️  Vision error : {e}")
            return None

    async def _vision_analyze_page(self, question: str) -> str:
        """Analyse la page actuelle et répond à une question en langage naturel."""
        if not self.client:
            return "Vision indisponible."
        try:
            raw = await self.page.screenshot(type="jpeg", quality=80)
            tmp = Path("jarvis_agent_analysis.jpg")
            tmp.write_bytes(raw)
            img = Image.open(tmp)

            prompt = (
                f"Tu es JARVIS, l'IA de Neyor. Voici une capture de page web.\n"
                f"Question : {question}\n"
                "Réponds en français, de façon concise et précise (2-3 phrases max)."
            )
            response = self.client.models.generate_content(
                model=self.chosen_model,
                contents=[prompt, img]
            )
            return response.text.strip()
        except Exception as e:
            return f"Analyse visuelle échouée : {e}"

    async def _vision_is_task_done(self, task_description: str) -> bool:
        """Vérifie visuellement si la tâche semble accomplie."""
        if not self.client:
            return False
        try:
            raw = await self.page.screenshot(type="jpeg", quality=75)
            tmp = Path("jarvis_agent_done_check.jpg")
            tmp.write_bytes(raw)
            img = Image.open(tmp)

            prompt = (
                f"Tu es JARVIS. Voici la capture d'écran actuelle du navigateur.\n"
                f"Tâche originale : {task_description}\n"
                "Est-ce que la tâche semble COMPLÈTE ? "
                "La page affiche-t-elle des résultats pertinents, un formulaire rempli, ou un état final ?\n"
                "Réponds UNIQUEMENT en JSON : {\"done\": true/false, \"reason\": \"explication courte\"}"
            )
            response = self.client.models.generate_content(
                model=self.chosen_model,
                contents=[prompt, img]
            )
            data = _extract_json(response.text.strip())
            if data:
                done = data.get("done", False)
                print(f"[VISUAL_AGENT] ✅ Done check : {done} — {data.get('reason', '')}")
                return done
        except Exception:
            pass
        return False

    # -----------------------------------------------------------------------
    # Action executor
    # -----------------------------------------------------------------------

    async def _animate_cursor(self, cx: int, cy: int, is_click: bool = False):
        """Anime le curseur holographique virtuel de JARVIS sur la page via injection JS."""
        if not self.page:
            return
        script = f"""
        (() => {{
            let cursor = document.getElementById("jarvis-web-cursor");
            if (!cursor) {{
                cursor = document.createElement("div");
                cursor.id = "jarvis-web-cursor";
                Object.assign(cursor.style, {{
                    position: "fixed",
                    width: "30px",
                    height: "30px",
                    borderRadius: "50%",
                    background: "radial-gradient(circle, #00e5ff 0%, rgba(0,100,255,0.4) 70%)",
                    boxShadow: "0 0 25px #00e5ff, inset 0 0 12px #ffffff",
                    zIndex: "99999999",
                    pointerEvents: "none",
                    transition: "all 800ms cubic-bezier(0.25, 1, 0.5, 1)",
                    left: (window.innerWidth / 2) + "px",
                    top: (window.innerHeight / 2) + "px",
                    transform: "translate(-50%, -50%) scale(1)",
                    opacity: "0",
                    display: "block"
                }});
                document.body.appendChild(cursor);
            }}
            
            // Forcer l'affichage
            cursor.style.opacity = "1";
            
            // Déplacement vers la cible
            setTimeout(() => {{
                cursor.style.left = "{cx}px";
                cursor.style.top = "{cy}px";
            }}, 50);

            if ({str(is_click).lower()}) {{
                // Animation de clic (rétrécissement et pulsation)
                setTimeout(() => {{
                    cursor.style.transform = "translate(-50%, -50%) scale(0.6)";
                }}, 750);
                setTimeout(() => {{
                    cursor.style.transform = "translate(-50%, -50%) scale(1)";
                }}, 900);
            }}
        }})();
        """
        try:
            await self.page.evaluate(script)
        except Exception:
            pass

    async def _click_at_box(self, box: list):
        """Clique au centre d'une bounding box normalisée [ymin, xmin, ymax, xmax]."""
        ymin, xmin, ymax, xmax = box
        
        # Récupérer la taille réelle du viewport à l'instant T
        try:
            viewport = await self.page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })")
            width = viewport["width"]
            height = viewport["height"]
        except Exception:
            width = SCREENSHOT_W
            height = SCREENSHOT_H
            
        cx = int(((xmin + xmax) / 2 / 1000) * width)
        cy = int(((ymin + ymax) / 2 / 1000) * height)
        
        # Animer le curseur holographique
        await self._animate_cursor(cx, cy, is_click=True)
        await asyncio.sleep(1.0) # Laisser le temps au curseur de se déplacer fluidement
        
        await self.page.mouse.move(cx, cy)
        await asyncio.sleep(0.2)
        await self.page.mouse.click(cx, cy)
        print(f"[VISUAL_AGENT] 🖱️  Clic ({cx}, {cy}) sur viewport réel ({width}x{height})")

    async def _type_at_box(self, box: list, text: str):
        """Clique dans un champ et tape du texte."""
        ymin, xmin, ymax, xmax = box
        
        try:
            viewport = await self.page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })")
            width = viewport["width"]
            height = viewport["height"]
        except Exception:
            width = SCREENSHOT_W
            height = SCREENSHOT_H
            
        cx = int(((xmin + xmax) / 2 / 1000) * width)
        cy = int(((ymin + ymax) / 2 / 1000) * height)
        
        # Animer le curseur holographique
        await self._animate_cursor(cx, cy, is_click=True)
        await asyncio.sleep(1.0)
        
        await self.page.mouse.move(cx, cy)
        await asyncio.sleep(0.2)
        await self.page.mouse.click(cx, cy)
        await asyncio.sleep(0.3)
        await self.page.keyboard.press("Control+a")
        await asyncio.sleep(0.1)
        await self.page.keyboard.type(text, delay=55)
        print(f"[VISUAL_AGENT] ⌨️  Texte tapé à ({cx}, {cy}) sur viewport réel ({width}x{height}) : {text}")

    async def _execute_step(self, step: dict) -> bool:
        """
        Exécute une étape du plan de l'agent.
        Retourne True si l'étape réussit, False sinon.

        Étapes supportées :
        - goto          : naviguer vers une URL
        - fill_search   : trouver visuellement la barre de recherche et taper
        - click         : trouver visuellement un élément et cliquer
        - type          : trouver un champ et taper du texte
        - press_enter   : appuyer sur Entrée
        - scroll        : faire défiler la page (up/down + px)
        - wait          : attendre N secondes
        - close_popups  : fermer les popups/cookies
        - screenshot    : juste capturer (pour débogage / confirmation)
        """
        action = step.get("action", "")
        print(f"[VISUAL_AGENT] 🔧 Étape : {action} | {step}")

        # Enrichir automatiquement les instructions de date avec le jour de la semaine en français
        if "instruction" in step:
            inst = step["instruction"].lower()
            date_match = re.search(r'(\d+)\s*(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\s*(\d{4})', inst)
            if date_match:
                day_num = int(date_match.group(1))
                month_str = date_match.group(2)
                year_num = int(date_match.group(3))
                
                months_map = {
                    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
                    "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12
                }
                month_num = months_map.get(month_str)
                if month_num:
                    import datetime
                    try:
                        dt = datetime.date(year_num, month_num, day_num)
                        weekdays_fr = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
                        weekday_str = weekdays_fr[dt.weekday()]
                        
                        extra = f" ({weekday_str})"
                        if weekday_str == "dimanche":
                            extra = f" ({weekday_str}, dans la colonne des dimanches tout à fait à droite du calendrier de mai)"
                        elif weekday_str == "samedi":
                            extra = f" ({weekday_str}, dans la colonne à gauche du dimanche)"
                        elif weekday_str == "vendredi":
                            extra = f" ({weekday_str}, dans la colonne des vendredis)"
                            
                        step["instruction"] = step["instruction"] + extra
                        print(f"[VISUAL_AGENT] 📅 Instruction de date enrichie : {step['instruction']}")
                    except Exception:
                        pass

        try:
            if action == "goto":
                url = step.get("url", "")
                if not url.startswith("http"):
                    url = "https://" + url
                
                # S'assurer que l'onglet est bien au premier plan
                try:
                    await self.page.bring_to_front()
                except Exception as e:
                    print(f"[VISUAL_AGENT] ⚠️ Impossible d'amener la page au premier plan : {e}")

                # Nettoyage pré-emptif de TOUTES les données de stockage (cookies, local_storage, indexeddb, etc.) via CDP
                cdp_success = False
                try:
                    from urllib.parse import urlparse
                    parsed_url = urlparse(url)
                    origin = f"{parsed_url.scheme}://{parsed_url.netloc}"
                    print(f"[VISUAL_AGENT] 🧹 Nettoyage CDP pour l'origine {origin}...")
                    
                    cdp = await self.context.new_cdp_session(self.page)
                    await cdp.send("Storage.clearDataForOrigin", {
                        "origin": origin,
                        "storageTypes": "all"
                    })
                    print("[VISUAL_AGENT] ✅ Nettoyage CDP réussi.")
                    cdp_success = True
                except Exception as e:
                    print(f"[VISUAL_AGENT] ⚠️ Erreur nettoyage CDP : {e}")
                
                # Nettoyage standard des cookies en fallback / complément
                try:
                    await self.context.clear_cookies()
                except Exception as e:
                    print(f"[VISUAL_AGENT] ⚠️ Erreur nettoyage cookies standard : {e}")
                        
                await self.page.goto(url, timeout=30000, wait_until="domcontentloaded")
                await asyncio.sleep(1.5)
                
                # Si le nettoyage CDP a échoué, on fait le nettoyage JS + reload en fallback
                if not cdp_success:
                    try:
                        print("[VISUAL_AGENT] 🧹 Fallback : Nettoyage complet (localStorage, sessionStorage, IndexedDB)...")
                        await self.page.evaluate("""() => {
                            try { localStorage.clear(); } catch(e){}
                            try { sessionStorage.clear(); } catch(e){}
                            try {
                                if (window.indexedDB && window.indexedDB.databases) {
                                    window.indexedDB.databases().then(dbs => {
                                        dbs.forEach(db => {
                                            try { window.indexedDB.deleteDatabase(db.name); } catch(e){}
                                        });
                                    });
                                }
                            } catch(e){}
                        }""")
                        # Recharger pour forcer le site à appliquer le nettoyage complet
                        await self.page.reload(wait_until="domcontentloaded")
                        await asyncio.sleep(1.5)
                    except Exception as e:
                        print(f"[VISUAL_AGENT] ⚠️  Erreur nettoyage session fallback : {e}")
                        
                await self._handle_popups()
                return True

            elif action == "fill_search":
                text = step.get("text", step.get("value", ""))
                instruction = step.get("instruction", f"la barre de recherche principale du site pour taper '{text}'")
                for attempt in range(MAX_RETRIES):
                    data = await self._vision_find_element(instruction)
                    if data and data.get("found", True) and "box" in data:
                        box = data["box"]
                        ymin, xmin, ymax, xmax = box
                        if ymax > 800:
                            print(f"[VISUAL_AGENT] 📜 Champ bas sur la page (ymax={ymax}/1000). Défilement pour recentrer...")
                            await self.page.mouse.wheel(0, 200)
                            await asyncio.sleep(0.8)
                            data = await self._vision_find_element(instruction)
                            if not (data and data.get("found", True) and "box" in data):
                                continue
                            box = data["box"]
                        
                        await self._type_at_box(box, text)
                        await asyncio.sleep(0.3)
                        await self.page.keyboard.press("Enter")
                        await asyncio.sleep(2.0)
                        await self._handle_popups()
                        return True
                    
                    print(f"[VISUAL_AGENT] 🔍 Champ non trouvé (tentative {attempt+1}/{MAX_RETRIES}). Défilement vers le bas...")
                    await self.page.mouse.wheel(0, 300)
                    await asyncio.sleep(0.8)
                return False

            elif action == "click":
                instruction = step.get("instruction", step.get("element", "l'élément cible"))
                
                # Tenter d'extraire une date de l'instruction pour un clic hybride ultra-précis (ex: "29 mai 2026")
                date_match = re.search(r'(\d+)\s*(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\s*(\d{4})', instruction.lower())
                if date_match:
                    day_num = int(date_match.group(1))
                    month_str = date_match.group(2)
                    year_num = int(date_match.group(3))
                    months_map = {
                        "janvier": "01", "février": "02", "fevrier": "02", "mars": "03", "avril": "04", "mai": "05", "juin": "06",
                        "juillet": "07", "août": "08", "aout": "08", "septembre": "09", "octobre": "10", "novembre": "11", "décembre": "12", "decembre": "12"
                    }
                    month_str_num = months_map.get(month_str)
                    if month_str_num:
                        date_iso = f"{year_num}-{month_str_num}-{day_num:02d}"
                        
                        # --- Navigation vers le bon mois si nécessaire ---
                        # Le calendrier Booking.com n'affiche que 2 mois à la fois.
                        # Si le mois cible n'est pas visible, cliquer sur ">" pour avancer.
                        months_fr_capitalize = {
                            "01": "Janvier", "02": "Février", "03": "Mars", "04": "Avril",
                            "05": "Mai", "06": "Juin", "07": "Juillet", "08": "Août",
                            "09": "Septembre", "10": "Octobre", "11": "Novembre", "12": "Décembre"
                        }
                        target_month_label = months_fr_capitalize.get(month_str_num, "")
                        target_header_text = f"{target_month_label} {year_num}"  # ex: "Juillet 2026"
                        
                        # Naviguer vers le bon mois (max 12 clics sur la flèche ">")
                        for nav_attempt in range(12):
                            try:
                                # Vérifier si le mois cible est visible dans les en-têtes du calendrier
                                month_visible = await self.page.evaluate(f"""
                                    (() => {{
                                        const headers = document.querySelectorAll('h3, h2, [class*="month"], [class*="Month"], [data-testid*="month"]');
                                        const targetText = "{target_header_text}".toLowerCase();
                                        for (const h of headers) {{
                                            if (h.innerText.toLowerCase().includes(targetText)) return true;
                                        }}
                                        // Fallback : chercher dans tout le texte visible du calendrier
                                        const calendarEl = document.querySelector('[data-testid*="calendar"], [class*="calendar"], [class*="Calendar"], [role="dialog"]');
                                        if (calendarEl && calendarEl.innerText.toLowerCase().includes(targetText)) return true;
                                        return false;
                                    }})()
                                """)
                                
                                if month_visible:
                                    print(f"[VISUAL_AGENT] 📅 Mois cible '{target_header_text}' visible dans le calendrier.")
                                    break
                                    
                                # Le mois n'est pas visible, cliquer sur la flèche "suivant"
                                print(f"[VISUAL_AGENT] 📅 Mois '{target_header_text}' non visible (tentative {nav_attempt+1}/12). Clic sur la flèche '>' pour avancer...")
                                
                                next_clicked = False
                                # Sélecteurs pour le bouton "mois suivant" de Booking.com
                                next_selectors = [
                                    'button[aria-label="Mois suivant"]',
                                    'button[aria-label="Next month"]',
                                    '[data-testid="date-display-field-end"] ~ button',
                                    '[class*="calendar"] button[class*="next"]',
                                    '[class*="calendar"] button:last-of-type',
                                    'button:has(svg[viewBox])',
                                ]
                                for next_sel in next_selectors:
                                    try:
                                        loc = self.page.locator(next_sel).last
                                        if await loc.is_visible(timeout=500):
                                            await loc.click()
                                            next_clicked = True
                                            print(f"[VISUAL_AGENT] 📅 Flèche '>' cliquée via : {next_sel}")
                                            break
                                    except Exception:
                                        pass
                                
                                if not next_clicked:
                                    # Fallback ultime : chercher via vision le bouton ">"
                                    try:
                                        # Sur Booking.com le bouton ">" est un <button> avec une icône SVG en haut à droite du calendrier
                                        next_btn = self.page.locator('button').filter(has=self.page.locator('svg')).last
                                        if await next_btn.is_visible(timeout=500):
                                            await next_btn.click()
                                            next_clicked = True
                                            print(f"[VISUAL_AGENT] 📅 Flèche '>' cliquée via fallback SVG button")
                                    except Exception:
                                        pass
                                
                                if not next_clicked:
                                    print(f"[VISUAL_AGENT] ⚠️  Impossible de trouver la flèche '>' du calendrier. Arrêt navigation mois.")
                                    break
                                    
                                await asyncio.sleep(0.6)
                            except Exception as nav_e:
                                print(f"[VISUAL_AGENT] ⚠️  Erreur navigation mois : {nav_e}")
                                break
                        
                        # --- Clic sur la date cible ---
                        selectors = [
                            f'[data-date="{date_iso}"]',
                            f'[data-id="{date_iso}"]',
                            f'[data-day="{date_iso}"]',
                            f'[aria-label*="{day_num} {month_str} {year_num}"]',
                            f'[aria-label*="{day_num} {month_str.replace("é", "e").replace("û", "u").replace("ô", "o")} {year_num}"]'
                        ]
                        clicked = False
                        for sel in selectors:
                            try:
                                if await self.page.locator(sel).is_visible(timeout=800):
                                    box = await self.page.locator(sel).bounding_box()
                                    if box:
                                        cx = int(box["x"] + box["width"] / 2)
                                        cy = int(box["y"] + box["height"] / 2)
                                        await self._animate_cursor(cx, cy, is_click=True)
                                        await asyncio.sleep(1.0)
                                        await self.page.locator(sel).click()
                                        print(f"[VISUAL_AGENT] 📅 Clic hybride réussi sur {sel} (coordonnées DOM : {cx}, {cy})")
                                        clicked = True
                                        break
                            except Exception:
                                pass
                        if clicked:
                            await asyncio.sleep(1.2)
                            await self._handle_popups()
                            return True

                # Tenter d'extraire le texte exact à cliquer de l'instruction (ex: "Spa et centre de bien-être")
                target_text = None
                quotes_match = re.search(r"['\"«»]([^'\"]+)['\"«»]", instruction)
                if quotes_match:
                    target_text = quotes_match.group(1).strip()
                else:
                    keyword_match = re.search(r'(?:case à cocher|filtre|bouton|cliquer sur|le bouton|la case)\s+([A-ZÀ-Ÿa-zà-ÿ0-9\s\-\&]+?)(?:\s+(?:dans|pour|de|sur)\b|$)', instruction)
                    if keyword_match:
                        target_text = keyword_match.group(1).strip()

                if target_text and len(target_text) > 2 and not date_match:
                    print(f"[VISUAL_AGENT] 🔍 Recherche DOM hybride pour le texte : '{target_text}'...")
                    # Sélecteurs alternatifs pour trouver l'élément textuel
                    selectors = [
                        f"text={target_text}",
                        f"button:has-text('{target_text}')",
                        f"a:has-text('{target_text}')",
                        f"span:has-text('{target_text}')",
                        f"label:has-text('{target_text}')",
                        f"div:has-text('{target_text}')",
                    ]
                    clicked = False
                    for sel in selectors:
                        try:
                            # Cible le premier élément visible
                            locator = self.page.locator(sel).first
                            if await locator.is_visible(timeout=800):
                                await locator.scroll_into_view_if_needed()
                                await asyncio.sleep(0.3)
                                
                                box = await locator.bounding_box()
                                if box:
                                    cx = int(box["x"] + box["width"] / 2)
                                    cy = int(box["y"] + box["height"] / 2)
                                    await self._animate_cursor(cx, cy, is_click=True)
                                    await asyncio.sleep(1.0)
                                    
                                    await locator.click()
                                    print(f"[VISUAL_AGENT] 🏷️ Clic hybride réussi par texte sur : {sel} (coordonnées DOM : {cx}, {cy})")
                                    clicked = True
                                    break
                        except Exception:
                            pass
                    
                    if clicked:
                        await asyncio.sleep(1.2)
                        await self._handle_popups()
                        return True

                for attempt in range(MAX_RETRIES):
                    data = await self._vision_find_element(instruction)
                    if data and data.get("found", True) and "box" in data:
                        box = data["box"]
                        ymin, xmin, ymax, xmax = box
                        if ymax > 800:
                            print(f"[VISUAL_AGENT] 📜 Élément bas sur la page (ymax={ymax}/1000). Défilement pour recentrer...")
                            await self.page.mouse.wheel(0, 200)
                            await asyncio.sleep(0.8)
                            data = await self._vision_find_element(instruction)
                            if not (data and data.get("found", True) and "box" in data):
                                continue
                            box = data["box"]
                        
                        await self._click_at_box(box)
                        await asyncio.sleep(1.2)
                        await self._handle_popups()
                        return True
                    
                    print(f"[VISUAL_AGENT] 🔍 Élément non trouvé (tentative {attempt+1}/{MAX_RETRIES}). Défilement vers le bas...")
                    await self.page.mouse.wheel(0, 300)
                    await asyncio.sleep(0.8)
                return False

            elif action == "type":
                text = step.get("text", step.get("value", ""))
                instruction = step.get("instruction", f"le champ de saisie pour '{text}'")
                for attempt in range(MAX_RETRIES):
                    data = await self._vision_find_element(instruction)
                    if data and data.get("found", True) and "box" in data:
                        box = data["box"]
                        ymin, xmin, ymax, xmax = box
                        if ymax > 800:
                            print(f"[VISUAL_AGENT] 📜 Champ bas sur la page (ymax={ymax}/1000). Défilement pour recentrer...")
                            await self.page.mouse.wheel(0, 200)
                            await asyncio.sleep(0.8)
                            data = await self._vision_find_element(instruction)
                            if not (data and data.get("found", True) and "box" in data):
                                continue
                            box = data["box"]
                        
                        await self._type_at_box(box, text)
                        return True
                    
                    print(f"[VISUAL_AGENT] 🔍 Champ non trouvé (tentative {attempt+1}/{MAX_RETRIES}). Défilement vers le bas...")
                    await self.page.mouse.wheel(0, 300)
                    await asyncio.sleep(0.8)
                return False

            elif action == "drag":
                instruction = step.get("instruction", "l'élément à glisser")
                target_value = step.get("value")
                
                # Tenter d'extraire dynamiquement un nombre de l'instruction (ex: "180€" ou "180 euros") comme secours
                if target_value is None:
                    match = re.search(r'(\d+)\s*(?:€|euros|eur|max|maximum)?\b', instruction.lower())
                    if match:
                        target_value = int(match.group(1))
                        
                # Secours 2 : Utiliser le budget cible global extrait de la tâche
                if target_value is None:
                    target_value = getattr(self, "budget_target", None)
                        
                dx = int(step.get("dx", 0))
                dy = int(step.get("dy", 0))
                
                # =====================================================================
                # STRATÉGIE 0 : Injection URL directe (Booking.com uniquement)
                # La méthode la plus fiable : modifier l'URL pour injecter le filtre prix
                # =====================================================================
                is_booking = False
                if self.page:
                    try:
                        current_url = self.page.url
                        is_booking = "booking.com" in current_url.lower()
                    except Exception:
                        pass
                
                if is_booking and target_value is not None:
                    try:
                        print(f"[VISUAL_AGENT] 🎯 Booking.com détecté. Injection directe du filtre prix via URL (budget max: {target_value}€)...")
                        
                        # Tenter d'abord via l'input aria-valuenow (manipulation DOM directe du slider)
                        dom_success = await self.page.evaluate(f"""
                            (() => {{
                                const targetVal = {target_value};
                                // Chercher tous les sliders de prix
                                const sliders = Array.from(document.querySelectorAll('[role="slider"]'));
                                // Filtrer pour ne garder que ceux dans un contexte de prix/budget
                                let priceSliders = sliders.filter(s => {{
                                    let p = s;
                                    for (let i = 0; i < 8; i++) {{
                                        if (!p) break;
                                        const txt = ((p.id || '') + ' ' + (p.className || '') + ' ' + (p.getAttribute('data-testid') || '')).toLowerCase();
                                        if (txt.includes('price') || txt.includes('prix') || txt.includes('budget')) return true;
                                        p = p.parentElement;
                                    }}
                                    return false;
                                }});
                                if (priceSliders.length === 0) priceSliders = sliders;
                                if (priceSliders.length === 0) return false;
                                
                                // Prendre le slider max (dernier)
                                const maxSlider = priceSliders[priceSliders.length - 1];
                                const currentMax = parseFloat(maxSlider.getAttribute('aria-valuemax') || '600');
                                const currentMin = parseFloat(maxSlider.getAttribute('aria-valuemin') || '0');
                                
                                // Forcer la valeur via les propriétés React internes
                                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
                                maxSlider.setAttribute('aria-valuenow', String(targetVal));
                                
                                // Simuler les événements React/UI
                                const events = ['input', 'change', 'mousedown', 'mouseup', 'pointerdown', 'pointerup'];
                                events.forEach(evtName => {{
                                    maxSlider.dispatchEvent(new Event(evtName, {{bubbles: true}}));
                                }});
                                
                                return true;
                            }})()
                        """)
                        
                        if dom_success:
                            print(f"[VISUAL_AGENT] 🔧 Manipulation DOM du slider effectuée. Vérification...")
                            await asyncio.sleep(1.5)
                        
                        # Méthode principale : injection URL
                        current_url = self.page.url
                        import urllib.parse
                        parsed = urllib.parse.urlparse(current_url)
                        params = urllib.parse.parse_qs(parsed.query)
                        
                        # Construire/modifier le filtre nflt pour le prix
                        nflt_values = params.get('nflt', [''])
                        nflt_str = nflt_values[0] if nflt_values else ''
                        
                        # Supprimer tout filtre de prix existant
                        nflt_parts = [p for p in nflt_str.split(';') if p and not p.startswith('price=')]
                        # Ajouter le nouveau filtre de prix (prix par nuit en EUR)
                        nflt_parts.append(f'price=EUR-0-{target_value}-1')
                        params['nflt'] = [';'.join(nflt_parts)]
                        
                        new_query = urllib.parse.urlencode(params, doseq=True)
                        new_url = urllib.parse.urlunparse((
                            parsed.scheme, parsed.netloc, parsed.path,
                            parsed.params, new_query, parsed.fragment
                        ))
                        
                        print(f"[VISUAL_AGENT] 🌐 Navigation vers l'URL filtrée : ...nflt=...price=EUR-0-{target_value}-1...")
                        await self.page.goto(new_url, timeout=30000, wait_until="domcontentloaded")
                        await asyncio.sleep(3.0)
                        await self._handle_popups()
                        
                        # Vérification post-injection : lire le prix max affiché dans les filtres
                        verify_result = await self.page.evaluate(f"""
                            (() => {{
                                // Chercher le texte du filtre de prix actif
                                const priceTexts = Array.from(document.querySelectorAll('[data-testid*="price"], [class*="price"], [class*="Price"]'));
                                for (const el of priceTexts) {{
                                    const txt = el.innerText || '';
                                    const nums = txt.match(/\\d+/g);
                                    if (nums && nums.length > 0) {{
                                        return {{text: txt, maxVal: Math.max(...nums.map(Number))}};
                                    }}
                                }}
                                // Chercher aussi dans les sliders
                                const sliders = document.querySelectorAll('[role="slider"]');
                                if (sliders.length > 0) {{
                                    const last = sliders[sliders.length - 1];
                                    const val = last.getAttribute('aria-valuenow');
                                    if (val) return {{text: 'slider aria-valuenow', maxVal: parseFloat(val)}};
                                }}
                                return null;
                            }})()
                        """)
                        
                        if verify_result:
                            print(f"[VISUAL_AGENT] ✅ Filtre prix vérifié : {verify_result.get('text', '?')} (max détecté: {verify_result.get('maxVal', '?')}€, cible: {target_value}€)")
                        else:
                            print(f"[VISUAL_AGENT] ✅ URL injectée avec filtre prix max={target_value}€. Page rechargée.")
                        
                        return True
                        
                    except Exception as e:
                        print(f"[VISUAL_AGENT] ⚠️  Erreur injection URL Booking : {e}. Fallback vers slider JS...")
                
                # =====================================================================
                # STRATÉGIE 1 : Calcul JS dynamique du slider + drag en temps réel
                # =====================================================================
                if target_value is not None:
                    # Calculer un dx estimé de secours au cas où le JS échoue
                    bounded_val = max(50, min(500, target_value))
                    dx = -int((500 - bounded_val) * 0.725)
                    dx = max(-220, dx)
                    print(f"[VISUAL_AGENT] 🧮 Budget cible détecté : {target_value}€. dx de secours estimé à : {dx}px")
                    
                    try:
                        print(f"[VISUAL_AGENT] 🧮 Détection d'un budget cible de {target_value}€. Calcul dynamique des coordonnées via JS...")
                        script = f"""
                        (() => {{
                            const targetVal = parseFloat("{target_value}");
                            
                            // Trouver la sidebar en premier pour ancrer la recherche de filtres
                            let sidebar = document.querySelector('aside, [id*="filter"], [class*="sidebar"], [class*="filter"], [data-testid*="sidebar"]');
                            
                            // 1. Essayer de trouver le conteneur spécifique du filtre de prix dans la sidebar
                            let container = null;
                            if (sidebar) {{
                                container = sidebar.querySelector('[data-testid="filters-group-price"], [class*="price-filter"], [id*="price"], [class*="Price"], [data-filters-group="price"]');
                            }}
                            if (!container) {{
                                container = document.querySelector('[data-testid="filters-group-price"], [class*="price-filter"], [data-filters-group="price"]');
                            }}
                            
                            if (!container && sidebar) {{
                                const groups = Array.from(sidebar.querySelectorAll('[class*="group"], [class*="section"], [class*="filter"], section, div'));
                                for (const g of groups) {{
                                    const title = g.querySelector('[class*="title"], h3, h4, h5, legend, span');
                                    if (title) {{
                                        const text = title.innerText.toLowerCase();
                                        if (text.includes('prix') || text.includes('budget') || text.includes('tarif') || text.includes('price')) {{
                                            container = g;
                                            break;
                                        }}
                                    }}
                                }}
                            }}
                            
                            let handles = [];
                            if (container) {{
                                handles = Array.from(container.querySelectorAll('[role="slider"], [class*="handle"], [class*="pointer"], [class*="thumb"], [class*="slider__handle"], button, [role="button"], div[tabindex="0"]'));
                                if (handles.length === 0) {{
                                    const allElements = Array.from(container.querySelectorAll('*'));
                                    handles = allElements.filter(el => {{
                                        const style = el.getAttribute('style') || '';
                                        const rect = el.getBoundingClientRect();
                                        return (style.includes('left') || style.includes('transform')) && rect.width > 0 && rect.width < 35 && rect.height > 0 && rect.height < 35;
                                    }});
                                }}
                                handles = handles.filter(h => {{
                                    const rect = h.getBoundingClientRect();
                                    return rect.width > 0 && rect.height > 0;
                                }});
                            }}
                            
                            if (handles.length === 0) {{
                                let allHandles = Array.from(document.querySelectorAll('[role="slider"], [class*="slider-handle"], [class*="SliderHandle"], [class*="handle-right"], [class*="slider__handle"]'));
                                if (allHandles.length === 0) {{
                                    allHandles = Array.from(document.querySelectorAll('[aria-valuemin]'));
                                }}
                                
                                handles = allHandles.filter(h => {{
                                    let isInsideFilter = false;
                                    let p = h;
                                    for (let i = 0; i < 8; i++) {{
                                        if (p) {{
                                            const tagName = p.tagName.toLowerCase();
                                            const idOrClass = ((p.id || "") + " " + (p.className || "")).toLowerCase();
                                            if (tagName === "aside" || idOrClass.includes("sidebar") || idOrClass.includes("filter")) {{
                                                isInsideFilter = true;
                                            }}
                                            if (i <= 1) {{
                                                const txt = (p.innerText || "").toLowerCase();
                                                if (
                                                    txt.includes("chambre") || txt.includes("salle de bain") || txt.includes("salles de bains") ||
                                                    txt.includes("lit") || txt.includes("stepper") || txt.includes("bathroom") || txt.includes("bedroom") ||
                                                    txt.includes("adulte") || txt.includes("enfant")
                                                ) {{
                                                    return false;
                                                }}
                                            }}
                                            const testId = (p.getAttribute("data-testid") || "").toLowerCase();
                                            if (
                                                idOrClass.includes("stepper") || idOrClass.includes("bathroom") || idOrClass.includes("room") ||
                                                idOrClass.includes("adult") || idOrClass.includes("children") ||
                                                testId.includes("stepper") || testId.includes("bathroom") || testId.includes("room") ||
                                                testId.includes("adult") || testId.includes("children")
                                            ) {{
                                                return false;
                                            }}
                                            p = p.parentElement;
                                        }}
                                    }}
                                    return isInsideFilter;
                                }});
                            }}
                            
                            if (handles.length === 0) return null;
                            
                            let handle = handles[handles.length - 1];
                            handle.scrollIntoView({{block: "center", behavior: "auto"}});
                            
                            let track = handle.parentElement;
                            for (let i = 0; i < 5; i++) {{
                                if (track && track.clientWidth > 80) break;
                                track = track.parentElement;
                            }}
                            if (!track) return null;
                            
                            let min = parseFloat(handle.getAttribute('aria-valuemin'));
                            let max = parseFloat(handle.getAttribute('aria-valuemax'));
                            
                            if (isNaN(min) || isNaN(max) || max <= min) {{
                                min = 0;
                                max = 500;
                                let textContent = "";
                                let parent = handle;
                                for (let i = 0; i < 4; i++) {{
                                    if (parent) {{
                                        textContent += " " + parent.innerText;
                                        parent = parent.parentElement;
                                    }}
                                }}
                                const numbers = textContent.match(/\\d+/g);
                                if (numbers && numbers.length >= 2) {{
                                    const nums = numbers.map(Number).sort((a,b) => a-b);
                                    min = nums[0];
                                    max = nums[nums.length - 1];
                                    if (max === min) max = min + 300;
                                }}
                            }}
                            
                            const target = Math.max(min, Math.min(max, targetVal));
                            const rect = track.getBoundingClientRect();
                            const handleRect = handle.getBoundingClientRect();
                            const fraction = (target - min) / (max - min);
                            const targetX = rect.left + (rect.width * fraction);
                            const handleX = handleRect.left + (handleRect.width / 2);
                            const deltaX = targetX - handleX;
                            
                            return {{
                                cx: Math.round(handleX),
                                cy: Math.round(handleRect.top + handleRect.height / 2),
                                dx: Math.round(deltaX),
                                min: min,
                                max: max
                            }};
                        }})()
                        """
                        result = await self.page.evaluate(script)
                        if result:
                            cx = result["cx"]
                            cy = result["cy"]
                            calc_dx = result["dx"]
                            print(f"[VISUAL_AGENT] 🧮 Budget sur la page : {result['min']}€ à {result['max']}€. Glissement calculé par JS : {calc_dx}px pour atteindre {target_value}€.")
                            
                            print(f"[VISUAL_AGENT] 🖱️  Glissement (Drag) dynamique de ({cx}, {cy}) vers ({cx + calc_dx}, {cy})")
                            await self._animate_cursor(cx, cy, is_click=True)
                            await asyncio.sleep(0.8)
                            await self.page.mouse.move(cx, cy)
                            await asyncio.sleep(0.2)
                            await self.page.mouse.down()
                            await asyncio.sleep(0.2)
                            
                            target_val = float(target_value)
                            current_x = cx
                            step_px = 5
                            direction = -1 if calc_dx < 0 else 1
                            max_micro_steps = max(60, abs(calc_dx) // step_px + 15)
                            
                            for step_idx in range(max_micro_steps):
                                current_x += step_px * direction
                                await self.page.mouse.move(current_x, cy)
                                await asyncio.sleep(0.05)
                                
                                # Lire la valeur actuelle du slider toutes les 3 micro-étapes
                                if step_idx % 3 == 0:
                                    current_val = None
                                    try:
                                        current_val = await self.page.evaluate("""
                                            (() => {
                                                const sliders = document.querySelectorAll('[role="slider"]');
                                                if (sliders.length === 0) return null;
                                                const last = sliders[sliders.length - 1];
                                                const val = last.getAttribute('aria-valuenow');
                                                return val ? parseFloat(val) : null;
                                            })()
                                        """)
                                    except Exception:
                                        pass
                                        
                                    if current_val is not None:
                                        if step_idx % 6 == 0:
                                            print(f"[VISUAL_AGENT] 🧮 Valeur slider en direct : {current_val}€ (cible: {target_val}€)")
                                        if direction == -1 and current_val <= target_val:
                                            print(f"[VISUAL_AGENT] 🎯 Cible de budget atteinte : {current_val}€ <= {target_val}€! Libération.")
                                            break
                                        elif direction == 1 and current_val >= target_val:
                                            print(f"[VISUAL_AGENT] 🎯 Cible de budget atteinte : {current_val}€ >= {target_val}€! Libération.")
                                            break
                                        
                            await self.page.mouse.up()
                            await asyncio.sleep(2.0)
                            
                            # Post-vérification : si on est sur Booking.com et que le slider JS a été utilisé,
                            # vérifier si le prix max correspond et sinon fallback vers injection URL
                            if is_booking:
                                try:
                                    final_val = await self.page.evaluate("""
                                        (() => {
                                            const sliders = document.querySelectorAll('[role="slider"]');
                                            if (sliders.length === 0) return null;
                                            const last = sliders[sliders.length - 1];
                                            const val = last.getAttribute('aria-valuenow');
                                            return val ? parseFloat(val) : null;
                                        })()
                                    """)
                                    if final_val is not None and abs(final_val - target_val) > 30:
                                        print(f"[VISUAL_AGENT] ⚠️  Slider JS imprécis ({final_val}€ au lieu de {target_val}€). Correction par injection URL...")
                                        import urllib.parse
                                        current_url = self.page.url
                                        parsed = urllib.parse.urlparse(current_url)
                                        params = urllib.parse.parse_qs(parsed.query)
                                        nflt_values = params.get('nflt', [''])
                                        nflt_str = nflt_values[0] if nflt_values else ''
                                        nflt_parts = [p for p in nflt_str.split(';') if p and not p.startswith('price=')]
                                        nflt_parts.append(f'price=EUR-0-{int(target_val)}-1')
                                        params['nflt'] = [';'.join(nflt_parts)]
                                        new_query = urllib.parse.urlencode(params, doseq=True)
                                        new_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
                                        await self.page.goto(new_url, timeout=30000, wait_until="domcontentloaded")
                                        await asyncio.sleep(3.0)
                                        await self._handle_popups()
                                        print(f"[VISUAL_AGENT] ✅ Correction URL appliquée : prix max = {int(target_val)}€")
                                except Exception as e:
                                    print(f"[VISUAL_AGENT] ⚠️  Vérification post-drag échouée : {e}")
                            
                            return True
                        else:
                            print("[VISUAL_AGENT] ⚠️  Impossible de calculer le slider en JS. Fallback vision standard avec dx estimé...")
                    except Exception as e:
                        print(f"[VISUAL_AGENT] ⚠️  Erreur calcul dynamique slider : {e}. Fallback vision standard avec dx estimé...")

                # =====================================================================
                # STRATÉGIE 2 : Fallback vision standard avec dx estimé
                # =====================================================================
                for attempt in range(MAX_RETRIES):
                    data = await self._vision_find_element(instruction)
                    if data and data.get("found", True) and "box" in data:
                        box = data["box"]
                        ymin, xmin, ymax, xmax = box
                        
                        try:
                            viewport = await self.page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })")
                            width = viewport["width"]
                            height = viewport["height"]
                        except Exception:
                            width = SCREENSHOT_W
                            height = SCREENSHOT_H
                            
                        cx = int(((xmin + xmax) / 2 / 1000) * width)
                        cy = int(((ymin + ymax) / 2 / 1000) * height)
                        
                        print(f"[VISUAL_AGENT] 🖱️  Glissement (Drag) de ({cx}, {cy}) vers ({cx + dx}, {cy + dy})")
                        await self._animate_cursor(cx, cy, is_click=True)
                        await asyncio.sleep(0.8)
                        await self.page.mouse.move(cx, cy)
                        await asyncio.sleep(0.2)
                        await self.page.mouse.down()
                        await asyncio.sleep(0.2)
                        
                        drag_steps = 8
                        for s in range(1, drag_steps + 1):
                            px = cx + int((dx / drag_steps) * s)
                            py = cy + int((dy / drag_steps) * s)
                            await self.page.mouse.move(px, py)
                            await asyncio.sleep(0.08)
                            
                        await self.page.mouse.up()
                        await asyncio.sleep(1.5)
                        
                        # Post-vérification Booking.com : si le drag vision a raté, corriger par URL
                        if is_booking and target_value is not None:
                            try:
                                import urllib.parse
                                current_url = self.page.url
                                parsed = urllib.parse.urlparse(current_url)
                                params = urllib.parse.parse_qs(parsed.query)
                                nflt_values = params.get('nflt', [''])
                                nflt_str = nflt_values[0] if nflt_values else ''
                                # Vérifier si le filtre de prix est déjà correct
                                has_correct_price = f'price=EUR-0-{target_value}' in nflt_str
                                if not has_correct_price:
                                    print(f"[VISUAL_AGENT] ⚠️  Drag vision terminé mais filtre URL absent. Injection URL de secours...")
                                    nflt_parts = [p for p in nflt_str.split(';') if p and not p.startswith('price=')]
                                    nflt_parts.append(f'price=EUR-0-{target_value}-1')
                                    params['nflt'] = [';'.join(nflt_parts)]
                                    new_query = urllib.parse.urlencode(params, doseq=True)
                                    new_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
                                    await self.page.goto(new_url, timeout=30000, wait_until="domcontentloaded")
                                    await asyncio.sleep(3.0)
                                    await self._handle_popups()
                                    print(f"[VISUAL_AGENT] ✅ Correction URL appliquée : prix max = {target_value}€")
                            except Exception as url_err:
                                print(f"[VISUAL_AGENT] ⚠️  Erreur vérification URL post-drag : {url_err}")
                        
                        return True
                    
                    print(f"[VISUAL_AGENT] 🔍 Élément à glisser non trouvé (tentative {attempt+1}/{MAX_RETRIES}). Défilement...")
                    await self.page.mouse.wheel(0, 250)
                    await asyncio.sleep(0.8)
                return False

            elif action == "press_enter":
                await self.page.keyboard.press("Enter")
                await asyncio.sleep(1.5)
                return True

            elif action == "scroll":
                direction = step.get("direction", "down")
                amount    = int(step.get("amount", 400))
                delta = amount if direction == "down" else -amount
                await self.page.mouse.wheel(0, delta)
                await asyncio.sleep(0.8)
                return True

            elif action == "wait":
                secs = float(step.get("seconds", 2.0))
                await asyncio.sleep(secs)
                return True

            elif action == "close_popups":
                await self._handle_popups()
                return True

            elif action == "screenshot":
                # Simple confirmation visuelle, pas d'action
                return True

            else:
                print(f"[VISUAL_AGENT] ⚠️  Action inconnue : {action}")
                return False

        except Exception as e:
            print(f"[VISUAL_AGENT] ❌ Erreur étape '{action}' : {e}")
            if "closed" in str(e).lower() or "connection" in str(e).lower():
                print("[VISUAL_AGENT] 🛑 Navigateur détecté comme fermé. Réinitialisation complète de l'état...")
                self.browser = self.context = self.page = self._pw = None
            return False

    # -----------------------------------------------------------------------
    # LLM Planning
    # -----------------------------------------------------------------------

    async def _plan_task(self, task: str) -> list[dict]:
        """
        Demande à Gemini de décomposer la tâche en étapes JSON.
        Retourne une liste d'étapes [{action, ...}, ...]
        """
        if not self.client:
            print("[VISUAL_AGENT] ❌ Client Gemini non disponible pour le planning.")
            return []

        prompt = (
            "Tu es le planificateur web de JARVIS. Décompose cette tâche web en étapes précises.\n\n"
            f"Tâche : {task}\n\n"
            "Génère un plan JSON sous forme de tableau. Chaque étape doit avoir :\n"
            "- action : goto | fill_search | click | type | press_enter | scroll | wait | close_popups | drag\n"
            "- Des paramètres adaptés selon l'action :\n"
            "  • goto         → {\"action\":\"goto\", \"url\":\"https://site.com\"}\n"
            "  • fill_search  → {\"action\":\"fill_search\", \"text\":\"ma recherche\", \"instruction\":\"la barre de recherche du site\"}\n"
            "  • click        → {\"action\":\"click\", \"instruction\":\"description précise du bouton/lien à cliquer\"}\n"
            "  • type         → {\"action\":\"type\", \"text\":\"texte à saisir\", \"instruction\":\"le champ de saisie destination\"}\n"
            "  • scroll       → {\"action\":\"scroll\", \"direction\":\"down\", \"amount\":400}\n"
            "  • wait         → {\"action\":\"wait\", \"seconds\":2}\n"
            "  • close_popups → {\"action\":\"close_popups\"}\n"
            "  • drag         → {\"action\":\"drag\", \"instruction\":\"l'élément à faire glisser\", \"dx\":-150, \"dy\":0}\n\n"
            "RÈGLES IMPORTANTES :\n"
            f"- La personne qui donne la tâche s'appelle '{nom_ou_utilisateur()}' et ton créateur 'Neyor'. Ce sont des PRÉNOMS, PAS des villes, PAS des lieux, PAS des mots-clés. Ne les tape JAMAIS dans un champ de recherche, de localisation ou de destination. Ignore complètement les mentions 'pour <prénom>' ou 'de <prénom>' dans la tâche.\n"
            "- Commence TOUJOURS par une étape goto vers le site le plus pertinent.\n"
            "- Pour les sites de recherche simples (Amazon, Google, YouTube, LeBonCoin, Vinted, etc.) : goto → fill_search → scroll pour voir les résultats. Ne rajoute PAS de filtre de localisation sauf si la tâche le demande explicitement (ex: 'à Lyon', 'près de Paris').\n"
            "- Pour les formulaires multi-champs (Booking, Airbnb, train/avion, etc.) : N'utilise JAMAIS 'fill_search' sur le champ de destination ! Car 'fill_search' appuie sur 'Entrée' et valide le formulaire immédiatement, sautant l'étape des dates. Utilise TOUJOURS 'type' (sans Entrée) pour le champ de destination (ex: {\"action\":\"type\", \"text\":\"Annecy\", \"instruction\":\"le champ Où allez-vous\"}), puis procède aux étapes de dates, et clique sur le bouton Rechercher à la toute fin.\n"
            "- Ajoute close_popups après chaque goto.\n"
            "- Sois précis dans les 'instruction' pour guider la vision IA.\n"
            "- MAXIMUM 12 étapes. Ne confirme pas, ne valide pas.\n"
            "- Réponds UNIQUEMENT avec le tableau JSON, rien d'autre.\n\n"
            "- SÉLECTION DES DATES DE CALENDRIER (Booking, Airbnb, vols, trains, etc.) :\n"
            "  Ne combine JAMAIS l'ouverture du calendrier et la sélection des dates dans une seule étape !\n"
            "  Décompose TOUJOURS la sélection des dates en 3 étapes de clic successives distinctes :\n"
            "    1. Un clic pour ouvrir le calendrier (ex: {\"action\":\"click\", \"instruction\":\"le bouton ou champ de sélection des dates\"})\n"
            "    2. Un clic pour choisir la date de début (ex: {\"action\":\"click\", \"instruction\":\"la case de la date du 29 mai 2026 dans le calendrier\"})\n"
            "    3. Un clic pour choisir la date de fin (ex: {\"action\":\"click\", \"instruction\":\"la case de la date du 31 mai 2026 dans le calendrier\"})\n"
            "  *IMPORTANT* : Juste APRÈS l'ouverture du calendrier (étape 1), ajoute TOUJOURS une étape de scroll vers le bas (ex: {\"action\":\"scroll\", \"direction\":\"down\", \"amount\":250}) afin d'amener le calendrier entièrement dans le viewport avant de cliquer sur les dates, pour éviter de cliquer sur des jours de la semaine ou des éléments coupés hors-écran.\n\n"
            "- FILTRES ET CHECKBOXES (ex: Spa, Piscine, Budget) :\n"
            "  • Nom exact : Dans l'instruction du plan, utilise TOUJOURS le libellé complet et exact du filtre tel qu'il apparaît sur le site (ex: {\"action\":\"click\", \"instruction\":\"la case à cocher Spa et centre de bien-être dans la colonne de gauche\"} au lieu de simplement 'le filtre Spa').\n"
            "  • Scroll de recherche : Si le filtre n'est pas immédiatement visible au chargement de la page de résultats, l'agent utilisera son défilement de secours automatique, mais tu peux planifier une étape de défilement (ex: {\"action\":\"scroll\", \"direction\":\"down\", \"amount\":300}) pour amener la colonne latérale des filtres dans la zone visible.\n"
            "  • Réglage de budget / prix (Sliders) : Sur Booking.com, le budget ne possède PAS de case à cocher 'Jusqu'à 180€' ! Il se règle TOUJOURS à l'aide d'un curseur horizontal (slider). Utilise TOUJOURS l'action drag pour faire glisser la poignée droite du budget vers la gauche. Planifie : {\"action\":\"drag\", \"instruction\":\"le bouton de poignée droit du curseur de budget (maximum)\", \"dx\":-230, \"dy\":0} (où -230 représente la distance en pixels vers la gauche pour ramener le budget de 800€+ à environ 180€).\n"
            "  • Validation des filtres : Sur les sites qui ont des filtres dans un panneau/overlay (LeBonCoin, Vinted, etc.), APRÈS avoir saisi une valeur dans un champ de filtre (prix min/max, etc.), n'utilise JAMAIS 'press_enter' pour valider ! Tu DOIS cliquer sur le bouton de validation/application du panneau de filtres (ex: {\"action\":\"click\", \"instruction\":\"le bouton Rechercher ou Appliquer du panneau de filtres\"}). Sur ces sites, 'press_enter' ne ferme pas le panneau de filtres.\n\n"
            "- SITES DE PETITES ANNONCES (LeBonCoin, Vinted, etc.) :\n"
            "  • N'essaie JAMAIS de passer les filtres de prix ou d'autres filtres directement dans l'URL (le format change constamment et n'est pas fiable).\n"
            "  • Suis TOUJOURS le parcours utilisateur classique :\n"
            "    1. Fais la recherche principale via 'fill_search' sur le site (ex: rechercher 'PS5').\n"
            "    2. Clique sur le bouton de filtre de prix (ex: le bouton 'Prix' ou 'Budget').\n"
            "    3. Utilise 'type' pour saisir la valeur dans le champ de prix maximum (ex: '500' dans le champ de prix max).\n"
            "    4. Clique sur le bouton de validation du filtre (ex: le bouton orange 'Rechercher' ou 'Appliquer' du panneau de filtres) pour appliquer le filtre.\n"
            "  • Ne rajoute JAMAIS de filtre de localisation sauf si l'utilisatrice le demande explicitement.\n\n"
            "Exemple pour 'cherche des chaussures rouges sur Amazon' :\n"
            "[{\"action\":\"goto\",\"url\":\"https://amazon.fr\"},{\"action\":\"close_popups\"},"
            "{\"action\":\"fill_search\",\"text\":\"chaussures rouges\",\"instruction\":\"la barre de recherche Amazon (input avec placeholder Rechercher)\"},"
            "{\"action\":\"wait\",\"seconds\":2},{\"action\":\"scroll\",\"direction\":\"down\",\"amount\":300}]"
        )

        try:
            response = self.client.models.generate_content(
                model=self.chosen_model,
                contents=[prompt]
            )
            text = response.text.strip()
            print(f"[VISUAL_AGENT] 📋 Plan brut :\n{text}")

            # Extraire le tableau JSON
            start = text.find("[")
            end   = text.rfind("]") + 1
            if start != -1 and end > start:
                steps = json.loads(text[start:end])
                print(f"[VISUAL_AGENT] 📋 {len(steps)} étapes planifiées.")
                return steps
        except Exception as e:
            print(f"[VISUAL_AGENT] ❌ Erreur planning : {e}")

        return []

    # -----------------------------------------------------------------------
    # Main run loop
    # -----------------------------------------------------------------------

    async def run(self, task: str) -> str:
        """
        Point d'entrée principal.
        Lance l'agent, planifie la tâche, l'exécute et retourne un résumé vocal.
        """
        if async_playwright is None:
            return f"Désolé{nom_espace()}, Playwright n'est pas installé. Lance : pip install playwright && playwright install chromium"

        self._init_gemini()
        self._running = True

        # Extraction du budget maximum de la tâche
        self.budget_target = None
        budget_patterns = [
            r'budget(?:\s+maximum|\s+max)?(?:\s+de)?\s*(\d+)',
            r'maximum\s+de\s*(\d+)',
            r'max\s*(\d+)',
            r'(\d+)\s*(?:€|euros|eur)\s*(?:max|maximum)?'
        ]
        for pattern in budget_patterns:
            m = re.search(pattern, task.lower())
            if m:
                try:
                    self.budget_target = int(m.group(1))
                    print(f"[VISUAL_AGENT] 💰 Budget cible extrait de la tâche : {self.budget_target}€")
                    break
                except Exception:
                    pass

        print(f"\n[VISUAL_AGENT] 🚀 Nouvelle tâche : {task}")
        _dire(f"J'active l'autopilote visuel, un instant{nom_espace()}...")

        # 1. Planification
        steps = await self._plan_task(task)
        if not steps:
            return f"Je n'ai pas pu planifier la tâche. Essayez de reformuler{nom_virgule()}."

        _dire(f"Plan établi en {len(steps)} étapes. Je lance le navigateur.")

        # 2. Démarrage du navigateur
        try:
            await self._start_browser()
        except Exception as e:
            return f"Impossible de lancer le navigateur : {e}"

        # 3. Exécution des étapes
        completed = 0
        for i, step in enumerate(steps[:MAX_STEPS]):
            if not self._running:
                break

            success = await self._execute_step(step)
            if success:
                completed += 1
            else:
                _dire(f"J'ai rencontré un obstacle à cette étape{nom_virgule()}. Par sécurité, je désactive l'autopilote et je vous laisse reprendre le contrôle sur cette page.")
                break
            await asyncio.sleep(STEP_DELAY)

        # 4. Vérification visuelle finale
        await asyncio.sleep(1.5)
        done = await self._vision_is_task_done(task)

        # 5. Résumé verbal de la page actuelle
        summary = await self._vision_analyze_page(
            f"Décris brièvement ce que tu vois sur la page en rapport avec : {task}. "
            f"Donne une réponse utile et directe pour {nom_ou_utilisateur()}, 2-3 phrases max."
        )

        current_url = self.page.url if self.page else "inconnue"
        print(f"\n[VISUAL_AGENT] 🏁 Tâche terminée. URL finale : {current_url}")
        print(f"[VISUAL_AGENT] ✅ {completed}/{len(steps)} étapes réussies.")

        # Navigateur intentionnellement laissé OUVERT pour que neyor voie le résultat
        print("[VISUAL_AGENT] 🌐 Navigateur laissé ouvert. Dis 'Jarvis ferme le navigateur' pour le fermer.")

        return summary if summary else f"J'ai effectué la tâche. {completed} étapes exécutées sur {len(steps)}."


# ---------------------------------------------------------------------------
# Singleton global (accessible via builtins)
# ---------------------------------------------------------------------------

_visual_agent_instance: VisualWebAgent | None = None


def get_visual_agent() -> VisualWebAgent:
    global _visual_agent_instance
    if _visual_agent_instance is None:
        _visual_agent_instance = VisualWebAgent()
    return _visual_agent_instance


async def run_visual_agent(task: str) -> str:
    """Point d'entrée simplifié pour main2.py."""
    agent = get_visual_agent()
    return await agent.run(task)


async def stop_visual_agent() -> str:
    """Arrête et ferme le navigateur de l'agent."""
    global _visual_agent_instance
    if _visual_agent_instance:
        await _visual_agent_instance.stop()
        _visual_agent_instance = None
        return f"Navigateur fermé{nom_virgule()}."
    return f"Aucun navigateur actif à fermer{nom_virgule()}."
