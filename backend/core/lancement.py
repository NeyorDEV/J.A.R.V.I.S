"""Démarrage de l'interface : statut des services, ports, frontend (Vite/dist), fenêtre pywebview ou navigateur."""

import os
import subprocess
import sys
import threading
import time

import core.shared as shared


try:
    import webview
    _WEBVIEW_OK = True
except ImportError:
    webview = None
    _WEBVIEW_OK = False


def afficher_statut_services():
    """Annonce les services démarrés (l'état détaillé est dans le bandeau de la console)."""
    print("[SERVICES] Backend actif · WebSocket ws://localhost:8765 · mot-clé « Jarvis »")


def _est_instance_jarvis(proc):
    """True si le processus appartient à ce projet (ancien JARVIS, ou son serveur Vite)."""
    racine = os.path.normcase(os.path.abspath(shared.RACINE_PROJET))
    try:
        if os.path.normcase(proc.cwd()).startswith(racine):
            return True
    except Exception:
        pass
    try:
        return any(racine in os.path.normcase(arg) for arg in proc.cmdline())
    except Exception:
        return False


def liberer_ports_occupes():
    """Termine une éventuelle instance précédente de JARVIS qui occuperait les ports 8765 ou 5173.

    Avant : `netstat` analysé comme du texte, avec « :5173 » cherché en sous-chaîne (ce qui
    visait aussi les ports 51730 à 51739), et tout programme trouvé était tué d'office,
    même un autre projet Vite en cours de développement (5173 est le port par défaut de
    Vite). Sur un Windows en français, « ÉCOUTE » était en outre mal décodé, si bien
    qu'aucune ancienne instance n'était jamais arrêtée. On interroge maintenant psutil,
    et seul un processus appartenant à ce projet est arrêté.
    """
    import psutil
    for port in (8765, 5173):
        try:
            pids = {c.pid for c in psutil.net_connections(kind="inet")
                    if c.laddr and c.laddr.port == port and c.status == psutil.CONN_LISTEN and c.pid}
        except Exception as e:
            print(f"[DÉMARRAGE] Impossible de vérifier le port {port} : {e}")
            continue
        for pid in pids:
            if pid == os.getpid():
                continue
            try:
                proc = psutil.Process(pid)
                nom = proc.name()
                if _est_instance_jarvis(proc):
                    proc.kill()
                    print(f"[DÉMARRAGE] Port {port} libéré (ancienne instance {nom}, PID {pid}).")
                else:
                    print(f"[DÉMARRAGE] ⚠ Le port {port} est utilisé par un autre programme ({nom}, PID {pid}) : "
                          f"il n'est pas arrêté, JARVIS risque de ne pas pouvoir démarrer.")
            except Exception as e:
                print(f"[DÉMARRAGE] Port {port} : {e}")


def lancer_frontend():
    """Démarre l'interface web (Vite, sinon dist/ servi en Python). Retourne (processus, URL)."""
    # Lancer le serveur Frontend
    frontend_dir = os.path.join(shared.RACINE_PROJET, "interfaces", "frontend")
    frontend_process = None
    FRONTEND_URL = "http://localhost:5173"

    # Nettoyage automatique des instances WebView2 orphelines pour libérer les verrous sur le dossier utilisateur
    if sys.platform.startswith("win"):
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "msedgewebview2.exe"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

    def _service_ecoute_sur(port, timeout=4.0):
        """Indique si un service répond déjà sur ce port."""
        import socket
        debut = time.time()
        while time.time() - debut < timeout:
            for host in ("localhost", "127.0.0.1", "::1"):
                try:
                    with socket.create_connection((host, port), timeout=0.3):
                        return True
                except (ConnectionRefusedError, OSError):
                    pass
            time.sleep(0.2)
        return False

    def _publier_dist_python(port=5173):
        """Publie le dossier dist/ par un petit serveur HTTP Python (secours sans npm)."""
        import http.server, socketserver, functools
        dist_dir = os.path.join(frontend_dir, "dist")
        # On passe le dossier au handler au lieu de faire os.chdir() : cette fonction
        # tourne dans un thread d'arrière-plan, et os.chdir() change le répertoire de
        # travail de TOUT le process — tous les chemins relatifs (jarvis_run.log, les
        # fichiers TTS temporaires…) se seraient mis à pointer dans dist/.
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=dist_dir)
        handler.log_message = lambda *a: None  # silencieux
        with socketserver.TCPServer(("", port), handler) as httpd:
            print(f"[JARVIS] Interface servie par Python sur http://localhost:{port}")
            httpd.serve_forever()

    vite_ok = False
    if os.path.exists(frontend_dir):
        # Tentative 1 : Vite (npm run dev) — seulement dans un dossier de développement
        # (node_modules présent). Une version installée n'a que dist/ : on le sert directement.
        try:
            if not os.path.isdir(os.path.join(frontend_dir, "node_modules")):
                raise FileNotFoundError("version installée : pas de node_modules, dist/ sera servi")
            print("[JARVIS] Démarrage de Vite (npm run dev)...")
            log_path = os.path.join(frontend_dir, "vite_output.log")
            with open(log_path, "w", encoding="utf-8") as f_log:
                frontend_process = subprocess.Popen(
                    ["npm", "run", "dev"], cwd=frontend_dir, shell=True,
                    stdout=f_log, stderr=f_log
                )
            # Timeout augmenté légèrement à 6.0s au cas où le système ralentit
            vite_ok = _service_ecoute_sur(5173, timeout=6.0)
            if vite_ok:
                print("[JARVIS] Interface locale (Vite) initialisée.")
            else:
                print("[JARVIS] Vite ne s'est pas lancé (npm ou vite manquant, ou erreur).")
                if frontend_process:
                    frontend_process.terminate()
                    frontend_process = None
                # Afficher le contenu des logs en cas d'échec
                try:
                    if os.path.exists(log_path):
                        with open(log_path, "r", encoding="utf-8") as f_log:
                            logs = f_log.read().strip()
                            if logs:
                                print("[JARVIS] --- LOGS VITE ---")
                                print(logs)
                                print("[JARVIS] -----------------")
                except Exception:
                    pass
        except Exception as e:
            print(f"[JARVIS] Vite non utilisé : {e}")
            frontend_process = None

        # Tentative 2 : servir dist/ avec Python (pas besoin de npm)
        if not vite_ok:
            dist_dir = os.path.join(frontend_dir, "dist")
            if os.path.exists(dist_dir) and os.path.exists(os.path.join(dist_dir, "index.html")):
                print("[JARVIS] Secours : dist/ servi par Python...")
                t_dist = threading.Thread(target=_publier_dist_python, args=(5173,), daemon=True)
                t_dist.start()
                vite_ok = _service_ecoute_sur(5173, timeout=3.0)
                if vite_ok:
                    print("[JARVIS] dist/ est en ligne.")
            else:
                print("[JARVIS] Pas de dossier dist/ : l'interface n'est pas disponible.")
                print("[JARVIS] Pour la construire : cd frontend && npm install && npm run build")

    if not vite_ok:
        print("[JARVIS] Attention : pas d'interface visuelle cette fois.")
        print("[JARVIS] Le mode vocal reste utilisable.")

    return frontend_process, FRONTEND_URL


def ouvrir_interface(frontend_process, FRONTEND_URL):
    """Ouvre le HUD : fenêtre native pywebview (bloquante, thread principal) ou navigateur en secours."""
    # Choisir le mode d'affichage
    use_native = _WEBVIEW_OK and webview is not None and not shared.FORCE_BROWSER_MODE

    if use_native:
        # MODE FENETRE NATIVE (pywebview)
        print("[JARVIS] Ouverture de la fenêtre native (pywebview)...")

        # Calcul de la taille et position centrée selon la résolution de l'écran
        try:
            from screeninfo import get_monitors
            _mon = get_monitors()[0]
            _sw, _sh = _mon.width, _mon.height
        except Exception:
            _sw, _sh = 1920, 1080

        # 85% de l'écran, min 1280x780
        _win_w = max(1280, int(_sw * 0.85))
        _win_h = max(780,  int(_sh * 0.85))
        _win_x = (_sw - _win_w) // 2
        _win_y = (_sh - _win_h) // 2

        shared._WEBVIEW_WINDOW = webview.create_window(
            title            = "J.A.R.V.I.S",
            url              = FRONTEND_URL,
            width            = _win_w,
            height           = _win_h,
            x                = _win_x,
            y                = _win_y,
            resizable        = True,
            min_size         = (900, 600),
            background_color = "#0a0a0f",
            maximized        = True,
        )

        def _a_la_fermeture():
            print("\n[JARVIS] Fenêtre close : arrêt de JARVIS...")
            # Arrêter le radar réseau proprement avant la fermeture
            try:
                import plugins.network_resolver as _nr
                _nr._radar_active = False
                if _nr._radar_task and not _nr._radar_task.done():
                    _nr._radar_task.cancel()
            except Exception:
                pass
            if frontend_process:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(frontend_process.pid)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )

        shared._WEBVIEW_WINDOW.events.closed += _a_la_fermeture

        _jarvis_loaded_once = False

        def _au_chargement():
            nonlocal _jarvis_loaded_once
            if _jarvis_loaded_once:
                return  # Ignorer les appels dupliqués (2ème fenêtre pywebview)
            _jarvis_loaded_once = True
            try:
                import ctypes
                import os
                # Groupement dans la barre des taches (detache de python.exe)
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Neyor.Jarvis.App")

                # Remplacement de l'icone de la fenetre webview
                hwnd = ctypes.windll.user32.FindWindowW(None, "J.A.R.V.I.S")
                if hwnd:
                    icon_path = os.path.abspath(os.path.join("assets", "jarvis_icon.ico"))
                    if os.path.exists(icon_path):
                        hicon = ctypes.windll.user32.LoadImageW(0, icon_path, 1, 0, 0, 0x0010)
                        if hicon:
                            ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon) # ICON_SMALL
                            ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon) # ICON_BIG
            except Exception as e:
                print(f"[JARVIS] Icône illisible : {e}")

        shared._WEBVIEW_WINDOW.events.loaded += _au_chargement

        # webview.start() DOIT etre appele depuis le thread principal
        try:
            # 1ère tentative : Edge Chromium (WebView2) par défaut
            _app_data = os.getenv("LOCALAPPDATA", os.getenv("APPDATA", os.path.expanduser("~")))
            _storage_path = os.path.join(_app_data, "JARVIS_Local")
            webview.start(private_mode=False, storage_path=_storage_path, debug=False)
        except Exception as e:
            print(f"[JARVIS] PyWebView avec WebView2 impossible ({e}) — tentative avec le moteur natif EdgeHTML...")
            try:
                # 2ème tentative : Forcer le moteur EdgeHTML natif sans dépendance externe WebView2
                webview.start(gui="edgehtml", private_mode=False, storage_path=_storage_path, debug=False)
            except Exception as e2:
                print(f"[JARVIS] Deuxieme tentative PyWebView avec EdgeHTML impossible ({e2}) — tentative de nettoyage du cache...")
                try:
                    import shutil
                    eb_path = os.path.join(_storage_path, "EBWebView")
                    if os.path.exists(eb_path):
                        shutil.rmtree(eb_path, ignore_errors=True)
                    # 3ème tentative : Edge Chromium après nettoyage complet du cache
                    webview.start(private_mode=False, storage_path=_storage_path, debug=False)
                except Exception as e3:
                    print(f"[JARVIS] Troisieme tentative PyWebView impossible : {e3} — bascule sur navigateur")
                    _ouvrir_navigateur_secours(FRONTEND_URL, frontend_process)
    else:
        # MODE NAVIGATEUR (fallback si pywebview absent)
        _ouvrir_navigateur_secours(FRONTEND_URL, frontend_process)


def _trouver_chemin_navigateur():
    """Tente de trouver le chemin de Chrome ou Edge pour le mode --app."""
    paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def _ouvrir_navigateur_secours(url, frontend_process):
    """
    Ouvre JARVIS dans un navigateur, de préférence en mode 'app' (sans barres).
    """
    print(f"[JARVIS] Preparation de l'interface sur {url}...")
    navigateur = _trouver_chemin_navigateur()
    
    if navigateur:
        print(f"[JARVIS] Lancement du mode App (sans bordures) avec profil persistant via : {os.path.basename(navigateur)}")
        try:
            profile_path = r"C:\Users\mylan\.gemini\antigravity\chrome_profile"
            if not os.path.exists(profile_path):
                os.makedirs(profile_path, exist_ok=True)
            subprocess.Popen([navigateur, f"--app={url}", f"--user-data-dir={profile_path}"])
        except Exception as e:
            print(f"[JARVIS] Erreur lors du lancement mode App, fallback standard : {e}")
            import webbrowser
            webbrowser.open(url)
    else:
        print(f"[JARVIS] Aucun navigateur compatible App trouve. Ouverture standard...")
        import webbrowser
        webbrowser.open(url)
    
    _attendre_hud(frontend_process)


def _attendre_hud(frontend_process):
    """Boucle d'attente du HUD et arrêt de JARVIS."""
    try:
        while True:
            time.sleep(1)
            # On ne ferme que si l'interface a été connectée au moins une fois
            if shared.interface_deja_connectee and not (shared.CONNECTED_CLIENTS - shared.CLIENTS_EXTENSION):
                print("\n[JARVIS] HUD déconnecté, 60 s pour se reconnecter...")
                time.sleep(60)
                if not (shared.CONNECTED_CLIENTS - shared.CLIENTS_EXTENSION):
                    print("[JARVIS] Pas de reconnexion : arrêt automatique...")
                    break
                else:
                    print("[JARVIS] HUD de retour, on continue.")
    except KeyboardInterrupt:
        print("\n[JARVIS] Arret manuel.")

    if frontend_process:
        print("[JARVIS] Arrêt du serveur web...")
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(frontend_process.pid)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
