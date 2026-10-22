import time
import asyncio
import subprocess
import os
import requests
import re
from datetime import datetime
import contextlib
import unicodedata
from core.interlocuteur import nom_espace, nom_virgule
import controller.deezer_cdp as cdp

try:
    import pyautogui
    pyautogui.FAILSAFE = False
except ImportError:
    pyautogui = None

try:
    import uiautomation as auto
except ImportError:
    auto = None

# Chemins d'installation de Deezer
DEEZER_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "deezer-desktop")
DEEZER_EXE = os.path.join(DEEZER_DIR, "Deezer.exe")

_cached_deezer_pids = []

def _normalize(text):
    """Normalise le texte pour comparaison robuste (sans accents, sans ponctuation, minuscules)."""
    if not text:
        return ""
    text = unicodedata.normalize('NFD', text)
    text = "".join(c for c in text if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^a-zA-Z0-9]', '', text)
    return text.lower().strip()

def _titre_court(titre):
    """Titre sans les mentions entre parenthèses/crochets (« (feat. X) », « [Remastered] »)
    que Deezer n'affiche pas toujours de la même façon partout."""
    court = re.sub(r"\(.*?\)|\[.*?\]", "", titre or "").strip()
    return court or (titre or "")

# Repérage par position dans la fenêtre Deezer (pixels, relatifs à la fenêtre) :
# - la barre du lecteur est collée en bas. L'ancien repérage par boutons voisins
#   (« Précédent »/« Suivant ») confondait les carrousels de la page avec le lecteur ;
# - le bandeau du haut contient la barre de recherche, qui affiche la requête tapée ;
# - l'en-tête d'une page (titre de la piste, de l'album...) est dans sa partie haute.
HAUTEUR_BARRE_LECTEUR = 120
HAUTEUR_BANDEAU = 110
ZONE_TITRE_PAGE = 330
LARGEUR_BARRE_LATERALE = 260
NOMS_BOUTON_PAUSE = ["Pause", "Mettre en pause"]
NOMS_LECTURE = ["Écouter", "Lecture", "Mix", "Reprendre"]

def _limite_barre_lecteur(deezer_ctrl):
    """Ordonnée à partir de laquelle commence la barre du lecteur."""
    try:
        return deezer_ctrl.BoundingRectangle.bottom - HAUTEUR_BARRE_LECTEUR
    except Exception:
        return 10 ** 6

def _initialize_com():
    """Initialise COM en MTA pour le thread actuel si ce n'est pas déjà fait."""
    import ctypes
    try:
        ctypes.windll.ole32.CoInitializeEx(None, 0)
    except:
        try:
            ctypes.windll.ole32.CoInitialize(None)
        except:
            pass

def _get_deezer_pids():
    """Récupère rapidement les PIDs de Deezer.exe via les processus actifs."""
    global _cached_deezer_pids
    import psutil
    
    # Vérifier si les PIDs en cache sont toujours valides
    if _cached_deezer_pids:
        valides = []
        for pid in _cached_deezer_pids:
            try:
                if psutil.pid_exists(pid):
                    p = psutil.Process(pid)
                    if 'deezer' in p.name().lower():
                        valides.append(pid)
            except:
                pass
        if valides:
            return valides
            
    deezer_pids = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and 'deezer' in proc.info['name'].lower():
                deezer_pids.append(proc.info['pid'])
        except:
            pass
            
    _cached_deezer_pids = deezer_pids
    return deezer_pids

def _attendre_deezer_prete(timeout=8.0):
    """Attend dynamiquement que le contrôle principal de Deezer soit accessible."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        ctrl = get_deezer_main_control()
        if ctrl:
            try:
                children = ctrl.GetChildren()
                if children:
                    print(f"[DEEZER] Prêt détecté après {time.time() - t0:.2f}s.")
                    return ctrl
            except:
                pass
        time.sleep(0.15)
    print(f"[DEEZER] Timeout attente prête après {timeout}s.")
    return get_deezer_main_control()

def get_deezer_main_control():
    """Trouve le DocumentControl (Chrome_RenderWidgetHostHWND) principal de Deezer."""
    if not auto:
        return None
    try:
        _initialize_com()
        import win32gui
        import win32process
        
        deezer_pids = _get_deezer_pids()
        if not deezer_pids:
            return None
            
        render_hwnds = []
        def enum_windows_callback(hwnd, extra):
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid in deezer_pids:
                    def child_callback(child_hwnd, _):
                        try:
                            c_class = win32gui.GetClassName(child_hwnd)
                            if c_class == "Chrome_RenderWidgetHostHWND":
                                render_hwnds.append(child_hwnd)
                        except:
                            pass
                        return True
                    try:
                        win32gui.EnumChildWindows(hwnd, child_callback, None)
                    except:
                        pass
            except:
                pass
            return True

        try:
            win32gui.EnumWindows(enum_windows_callback, None)
        except:
            pass
        
        best_ctrl = None
        max_buttons = -1
        
        for r_hwnd in render_hwnds:
            try:
                # Activer l'accessibilité Chromium
                win32gui.SendMessage(r_hwnd, 0x003D, 0, 0xFFFFFFFC)
            except:
                pass
                
            try:
                ctrl = auto.ControlFromHandle(r_hwnd)
                if ctrl and ctrl.Exists(0.1):
                    buttons_count = 0
                    def count_buttons(c):
                        nonlocal buttons_count
                        if c.ControlTypeName == "ButtonControl":
                            buttons_count += 1
                        for child in c.GetChildren():
                            count_buttons(child)
                    count_buttons(ctrl)
                    
                    if buttons_count > max_buttons:
                        max_buttons = buttons_count
                        best_ctrl = ctrl
            except:
                pass
                
        return best_ctrl
    except Exception as e:
        print(f"[DEEZER UIA] Erreur get_deezer_main_control : {e}")
    return None

def _restore_focus(hwnd):
    """Restaure le focus sur la fenêtre d'origine."""
    if not hwnd:
        return
    try:
        import win32gui
        import win32con
        import ctypes
        if not win32gui.IsWindow(hwnd):
            return
        active_now = win32gui.GetForegroundWindow()
        if active_now == hwnd:
            return
        # Simulation touche Alt pour contourner restriction SetForegroundWindow
        ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
        time.sleep(0.01)
        ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except Exception as e:
        print(f"[DEEZER UIA] Impossible de restaurer le focus : {e}")

@contextlib.contextmanager
def prevent_focus_theft():
    """Contexte empêchant Deezer de voler le focus actif de l'utilisateur."""
    modified_hwnds = []
    try:
        import win32gui
        import win32process
        import win32con
        
        deezer_pids = _get_deezer_pids()
        if deezer_pids:
            hwnds = []
            def enum_windows_callback(hwnd, extra):
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid in deezer_pids:
                        classname = win32gui.GetClassName(hwnd)
                        if "Chrome_WidgetWin" in classname:
                            hwnds.append(hwnd)
                except:
                    pass
                return True
            try:
                win32gui.EnumWindows(enum_windows_callback, None)
            except:
                pass
            
            for hwnd in hwnds:
                try:
                    style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                    if not (style & 0x08000000): # WS_EX_NOACTIVATE
                        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | 0x08000000)
                        win32gui.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 
                                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | 
                                              win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED | 
                                              win32con.SWP_NOACTIVATE)
                        modified_hwnds.append((hwnd, style))
                except:
                    pass
    except Exception as e:
        print(f"[DEEZER UIA] Échec prevent_focus_theft : {e}")
        
    try:
        yield
    finally:
        for hwnd, old_style in modified_hwnds:
            try:
                import win32gui
                import win32con
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, old_style)
                win32gui.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 
                                      win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | 
                                      win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED | 
                                      win32con.SWP_NOACTIVATE)
            except:
                pass

def _fenetre_deezer(hwnd):
    """Vrai si la fenêtre appartient au processus Deezer."""
    try:
        import win32process
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return pid in _get_deezer_pids()
    except Exception:
        return False

@contextlib.contextmanager
def _garder_focus_utilisateur():
    """Rend le focus à la fenêtre de l'utilisateur si Deezer l'a pris pendant l'opération.

    Deezer s'active parfois de lui-même après un clic, avec un temps de retard que la
    vérification de _clic_control (0,1 s après le clic) ne voit pas."""
    avant = None
    try:
        import win32gui
        avant = win32gui.GetForegroundWindow()
    except Exception:
        pass
    try:
        yield
    finally:
        try:
            if avant and not _fenetre_deezer(avant):
                time.sleep(0.3)
                if _fenetre_deezer(win32gui.GetForegroundWindow()):
                    _restore_focus(avant)
        except Exception:
            pass

def reparer_fenetres_deezer():
    """Rend les fenêtres de Deezer de nouveau affichables si une opération en arrière-plan les a
    laissées « non activables » (clic dans la barre des tâches sans effet) ou transparentes
    (invisibles) : opération interrompue, ancienne version de JARVIS… Sans effet sinon.
    Appelée au démarrage de JARVIS, à « ouvre Deezer » et après chaque opération invisible."""
    try:
        import ctypes
        import win32gui, win32con, win32process
        pids = set(_get_deezer_pids())
        if not pids:
            return 0
        lire_calque = ctypes.windll.user32.GetLayeredWindowAttributes
        reparees = []

        def examiner(h, _):
            try:
                _, pid = win32process.GetWindowThreadProcessId(h)
                if pid not in pids or "Chrome_WidgetWin" not in win32gui.GetClassName(h):
                    return True
                ex = win32gui.GetWindowLong(h, win32con.GWL_EXSTYLE)
                nouveau = ex & ~0x08000000 & ~win32con.WS_EX_TRANSPARENT   # WS_EX_NOACTIVATE, clics traversants
                if nouveau != ex:
                    win32gui.SetWindowLong(h, win32con.GWL_EXSTYLE, nouveau)
                    reparees.append(h)
                if nouveau & win32con.WS_EX_LAYERED:
                    alpha, drapeaux, cle = ctypes.c_ubyte(), ctypes.c_uint(), ctypes.c_uint()
                    if lire_calque(h, ctypes.byref(cle), ctypes.byref(alpha), ctypes.byref(drapeaux)) \
                            and (drapeaux.value & win32con.LWA_ALPHA) and alpha.value < 255:
                        win32gui.SetLayeredWindowAttributes(h, 0, 255, win32con.LWA_ALPHA)
                        reparees.append(h)
                if h in reparees:
                    win32gui.SetWindowPos(h, 0, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
                                          | win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED | win32con.SWP_NOACTIVATE)
            except Exception:
                pass
            return True

        win32gui.EnumWindows(examiner, None)
        if reparees:
            print(f"[DEEZER] Fenêtre de Deezer réparée (de nouveau affichable) : {len(set(reparees))} fenêtre(s).")
        return len(set(reparees))
    except Exception as e:
        print(f"[DEEZER] Réparation des fenêtres impossible : {e}")
        return 0


@contextlib.contextmanager
def _deezer_actionnable():
    """Rend Deezer réceptif aux actions d'accessibilité sans jamais l'afficher.

    Fenêtre réduite (ou cachée dans la zone de notification), Deezer refuse clics et
    saisies par accessibilité (erreur 0x80040200). Le temps de l'opération, la fenêtre
    est donc sortie de cet état de façon invisible : totalement transparente, ignorant
    la souris, sans activation et tout en bas de la pile des fenêtres. Elle retrouve
    ensuite son état d'origine. Recouverte par une autre fenêtre (jeu plein écran...),
    elle reste réceptive : rien à faire dans ce cas."""
    hwnd = _get_deezer_hwnd_rapide()
    etat = None
    try:
        import win32gui, win32con
        if hwnd:
            if win32gui.IsIconic(hwnd):
                etat = "reduite"
            elif not win32gui.IsWindowVisible(hwnd):
                etat = "cachee"
    except Exception:
        hwnd = None
    if not etat:
        yield
        return
    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    try:
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                               ex_style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT)
        win32gui.SetLayeredWindowAttributes(hwnd, 0, 0, win32con.LWA_ALPHA)
        win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
        win32gui.SetWindowPos(hwnd, win32con.HWND_BOTTOM, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
        time.sleep(0.4)
    except Exception as e:
        print(f"[DEEZER UIA] Échec sortie invisible de la fenêtre : {e}")
    try:
        yield
    finally:
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOWMINNOACTIVE if etat == "reduite" else win32con.SW_HIDE)
            time.sleep(0.2)
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
            # Fenêtre déjà « calque » avant (fréquent sous Electron) : rendre au style d'origine
            # gardait le calque ET l'opacité 0 posée plus haut — Deezer restait invisible, même
            # JARVIS fermé, et impossible à afficher depuis la barre des tâches.
            if ex_style & win32con.WS_EX_LAYERED:
                win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_ALPHA)
        except Exception as e:
            print(f"[DEEZER UIA] Échec remise en état de la fenêtre : {e}")
        reparer_fenetres_deezer()

def _clic_control(btn):
    """Effectue un clic sur un contrôle UIA de manière silencieuse (background)."""
    with prevent_focus_theft():
        hwnd_before = None
        try:
            import win32gui
            hwnd_before = win32gui.GetForegroundWindow()
        except:
            pass

        try:
            rect = btn.BoundingRectangle
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            if width <= 0 or height <= 0:
                print(f"[DEEZER UIA] Clic ignoré : dimensions nulles ({width}x{height})")
                return False
                
            # 1. LegacyIAccessible (virtuel, n'affecte pas le focus)
            try:
                legacy_pat = btn.GetLegacyIAccessiblePattern()
                if legacy_pat and legacy_pat.DoDefaultAction():
                    time.sleep(0.1)
                    active_now = win32gui.GetForegroundWindow()
                    if active_now != hwnd_before and hwnd_before != 0:
                        _restore_focus(hwnd_before)
                    return True
            except Exception:
                pass

            # 2. InvokePattern
            try:
                pattern = btn.GetInvokePattern()
                if pattern and pattern.Invoke():
                    _restore_focus(hwnd_before)
                    return True
            except Exception:
                pass

            # Pas de clic souris réel en secours : il faudrait afficher Deezer, ce qui
            # dérangerait l'utilisateur (en pleine partie, par exemple).
            print(f"[DEEZER UIA] Clic refusé par Deezer sur '{btn.Name}'")
            return False
        except Exception as ex:
            print(f"[DEEZER UIA] Erreur clic contrôle : {ex}")
            return False

def find_player_button(deezer_ctrl, button_names):
    """Trouve un bouton de la barre du lecteur (en bas de la fenêtre), ou None.

    Ne renvoie jamais un bouton de la page : l'ancienne version se rabattait sur le
    premier « Écouter » trouvé (une carte de la page d'accueil), d'où des « La musique
    est déjà en pause » alors qu'elle jouait."""
    limite = _limite_barre_lecteur(deezer_ctrl)
    exacts, partiels = [], []
    def _collect_buttons(control):
        if control.ControlTypeName == "ButtonControl":
            name = control.Name or ""
            if name in button_names or any(b in name for b in button_names):
                try:
                    rect = control.BoundingRectangle
                    if rect.right - rect.left > 0 and rect.top >= limite:
                        (exacts if name in button_names else partiels).append(control)
                except:
                    pass
        for child in control.GetChildren():
            _collect_buttons(child)

    _collect_buttons(deezer_ctrl)
    boutons = exacts + partiels
    return boutons[0] if boutons else None

def find_page_play_button(deezer_ctrl, button_names, sous=None):
    """Recherche le bouton de lecture au sein de la page (hors barre du lecteur).

    Avec `sous` (ordonnée de l'en-tête de la page), ne retient que les boutons placés
    sous cet en-tête et prend le plus proche ; sinon le premier dans l'ordre de la page.
    Les noms exacts passent avant les noms qui ne font que les contenir."""
    limite = _limite_barre_lecteur(deezer_ctrl)
    candidats = []
    def _collect_buttons(control):
        if control.ControlTypeName == "ButtonControl":
            name = control.Name or ""
            if name in button_names or any(b in name for b in button_names):
                try:
                    rect = control.BoundingRectangle
                    if rect.right - rect.left > 0 and rect.top < limite and (sous is None or rect.top >= sous):
                        candidats.append((name not in button_names, rect.top, rect.left, control))
                except:
                    pass
        for child in control.GetChildren():
            _collect_buttons(child)

    _collect_buttons(deezer_ctrl)
    if not candidats:
        return None
    if sous is not None:
        candidats.sort(key=lambda c: (c[0], c[1], c[2]))
    else:
        candidats.sort(key=lambda c: c[0])  # tri stable : garde l'ordre de la page
    return candidats[0][3]

def _attendre_titre_page(titre, timeout=12):
    """Attend que la page affiche `titre` (ou l'un des titres d'une liste) dans son en-tête
    et renvoie l'ordonnée de ce titre, ou None. Ignore le bandeau du haut, la barre
    latérale et le lecteur."""
    titres = titre if isinstance(titre, (list, tuple)) else [titre]
    cibles = {_normalize(t) for t in titres if _normalize(t)}
    if not cibles:
        return None
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            ctrl = get_deezer_main_control()
            if ctrl:
                R = ctrl.BoundingRectangle
                haut, bas = R.top + HAUTEUR_BANDEAU, R.top + ZONE_TITRE_PAGE
                trouve = []
                def _walk(c, depth=0):
                    if trouve or depth > 25:
                        return
                    if c.ControlTypeName in ("TextControl", "HeaderControl") and _normalize(c.Name or "") in cibles:
                        r = c.BoundingRectangle
                        if r.right - r.left > 0 and haut <= r.top <= bas and r.right > LARGEUR_BARRE_LATERALE:
                            trouve.append(r.top)
                            return
                    for child in c.GetChildren():
                        _walk(child, depth + 1)
                _walk(ctrl)
                if trouve:
                    return trouve[0]
        except Exception:
            pass
        time.sleep(0.3)
    return None

def _verifier_lecture(titre=None, artiste=None, timeout=8):
    """Vérifie que Deezer joue (bouton Pause dans la barre du lecteur) et, si fournis,
    que le titre et l'artiste figurent dans le titre de la fenêtre, qui suit le morceau
    en cours (« TITRE - ARTISTE - Deezer »)."""
    titre_n = _normalize(_titre_court(titre)) if titre else ""
    artiste_n = _normalize(artiste) if artiste else ""
    fenetre = ""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            ctrl = get_deezer_main_control()
            if ctrl:
                fenetre = ctrl.Name or ""
                f_n = _normalize(fenetre)
                if (find_player_button(ctrl, NOMS_BOUTON_PAUSE)
                        and (not titre_n or titre_n in f_n) and (not artiste_n or artiste_n in f_n)):
                    return True
        except Exception:
            pass
        time.sleep(0.4)
    print(f"[DEEZER] Lecture non confirmée (attendu : {titre or '-'} / {artiste or '-'} ; fenêtre : {fenetre})")
    return False

def _uia_clic_bouton(noms_boutons):
    """Recherche le bouton dans le lecteur et clique dessus."""
    if not auto:
        return False
    try:
        deezer_ctrl = get_deezer_main_control()
        if not deezer_ctrl:
            return False
        btn = find_player_button(deezer_ctrl, noms_boutons)
        if btn:
            return _clic_control(btn)
    except Exception as e:
        print(f"[DEEZER UIA] Échec clic bouton {noms_boutons} : {e}")
    return False

def _uia_clic_bouton_page_dynamique(noms_boutons, timeout=12, wait_for_title=None):
    """Attend le chargement de la page et clique sur son bouton de lecture.

    Avec wait_for_title, attend que la page affiche ce titre dans son en-tête, puis
    clique le bouton le plus proche sous ce titre ; sans en-tête, ne clique rien.
    (L'ancienne version comparait au titre de la FENÊTRE, qui contient toujours
    « Deezer » et désigne le morceau en cours : elle ne patientait jamais et cliquait
    le premier « Écouter » de la page encore affichée, lançant un autre contenu.)"""
    if not auto:
        return False
    t0 = time.time()
    sous = None
    if wait_for_title:
        sous = _attendre_titre_page(wait_for_title, timeout)
        if sous is None:
            print(f"[DEEZER UIA] Page « {wait_for_title} » non affichée après {timeout}s : aucun clic.")
            return False
    fin = time.time() + max(3.0, timeout - (time.time() - t0))
    while time.time() < fin:
        try:
            deezer_ctrl = get_deezer_main_control()
            if deezer_ctrl:
                btn = find_page_play_button(deezer_ctrl, noms_boutons, sous=sous)
                if btn:
                    print(f"[DEEZER UIA] Clic sur le bouton de la page : '{btn.Name}'")
                    if _clic_control(btn):
                        return True
        except:
            pass
        time.sleep(0.3)
    return False

def _uia_clic_bouton_piste_album(track_title, artist_name=None, timeout=15):
    """Clique le bouton « Écouter <titre> par <artiste> » d'une ligne de morceau
    (résultats de recherche, page d'artiste...).

    Ne retient que les boutons dont le nom commence par « Écouter », hors bandeau du
    haut et barre du lecteur : l'ancienne version cliquait le premier élément contenant
    le titre et l'artiste, souvent le bouton de la barre de recherche, qui affiche la
    requête tapée — rien ne se lançait."""
    if not auto:
        return False
    titre = _normalize(_titre_court(track_title))
    artiste = _normalize(artist_name) if artist_name else None
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            deezer_ctrl = get_deezer_main_control()
            if deezer_ctrl:
                haut = deezer_ctrl.BoundingRectangle.top + HAUTEUR_BANDEAU
                limite = _limite_barre_lecteur(deezer_ctrl)
                trouve = []
                def _walk(c, depth=0):
                    if trouve or depth > 25:
                        return
                    if c.ControlTypeName == "ButtonControl":
                        n = _normalize(c.Name or "")
                        if n.startswith("ecouter") and titre in n and (not artiste or artiste in n):
                            r = c.BoundingRectangle
                            if r.right - r.left > 0 and haut <= r.top < limite:
                                trouve.append(c)
                                return
                    for child in c.GetChildren():
                        _walk(child, depth + 1)
                _walk(deezer_ctrl)
                if trouve:
                    print(f"[DEEZER UIA] Clic sur le bouton de lecture de la ligne : '{trouve[0].Name}'")
                    if _clic_control(trouve[0]):
                        return True
        except Exception as e:
            print(f"[DEEZER UIA] Avertissement _uia_clic_bouton_piste_album : {e}")
        time.sleep(0.3)
    return False

def _uia_taper_dans_recherche(query):
    """Saisit du texte dans l'EditControl de recherche sans voler le focus."""
    if not auto:
        return False
    try:
        _initialize_com()
        with prevent_focus_theft():
            search_edit = None
            def _find_edit(c, depth=0):
                if c.ControlTypeName == "EditControl" and depth < 15:
                    name = c.Name or ""
                    auto_id = c.AutomationId or ""
                    if name == "Rechercher" or "search" in auto_id.lower() or name.lower() == "search":
                        return c
                if depth < 15:
                    for child in c.GetChildren():
                        res = _find_edit(child, depth + 1)
                        if res:
                            return res
                return None
            # La barre peut mettre quelques secondes à apparaître quand Deezer vient
            # d'être ramené au premier plan : on réessaie au lieu d'abandonner.
            t0 = time.time()
            while not search_edit and time.time() - t0 < 5:
                deezer_ctrl = get_deezer_main_control()
                if deezer_ctrl:
                    search_edit = _find_edit(deezer_ctrl)
                if not search_edit:
                    time.sleep(0.4)

            if not search_edit:
                print("[DEEZER UIA] Barre de recherche introuvable")
                return False
                
            # Tenter via ValuePattern
            try:
                val_pat = search_edit.GetValuePattern()
                if val_pat:
                    val_pat.SetValue(query)
                    time.sleep(1.8)
                    return True
            except:
                pass
                
            # Tenter via LegacyIAccessiblePattern
            try:
                legacy_pat = search_edit.GetLegacyIAccessiblePattern()
                if legacy_pat:
                    legacy_pat.SetValue(query)
                    time.sleep(1.8)
                    return True
            except:
                pass
                
    except Exception as e:
        print(f"[DEEZER UIA] Échec saisie recherche : {e}")
    return False

def _get_deezer_hwnd_rapide():
    """Trouve le HWND de la fenêtre principale de Deezer (même en tray/minimisé) SANS la
    restaurer ni voler le focus. Utilisé pour les commandes média rapides (play/pause,
    suivant, précédent) et pour rendre Deezer réceptif quand il est réduit.

    Deezer peut avoir plusieurs fenêtres de premier niveau, dont certaines vides (une
    fenêtre « Deezer » sans contenu a été observée) : on prend celle qui contient la page
    web (Chrome_RenderWidgetHostHWND), sinon la première trouvée."""
    try:
        import win32gui, win32process
        deezer_pids = _get_deezer_pids()
        if not deezer_pids:
            return None
        candidats = []
        def _rappel_fenetre(hwnd, _):
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid in deezer_pids:
                    classname = win32gui.GetClassName(hwnd)
                    if "Chrome_WidgetWin" in classname and not win32gui.GetParent(hwnd):
                        candidats.append(hwnd)
            except Exception:
                pass
            return True
        try:
            win32gui.EnumWindows(_rappel_fenetre, None)
        except:
            pass
        for hwnd in candidats:
            rendus = []
            def _enfant(child, _):
                if win32gui.GetClassName(child) == "Chrome_RenderWidgetHostHWND":
                    rendus.append(child)
                    return False
                return True
            try:
                win32gui.EnumChildWindows(hwnd, _enfant, None)
            except Exception:
                pass
            if rendus:
                return hwnd
        return candidats[0] if candidats else None
    except Exception:
        return None

async def deezer_demarrer(afficher=True):
    """Lance Deezer s'il n'est pas ouvert en s'assurant que l'accessibilité soit active.

    afficher=False (opérations internes de JARVIS : lancer un titre, pause...) : la
    fenêtre existante n'est pas touchée, et un Deezer tout juste lancé est aussitôt
    réduit en rendant le focus à l'utilisateur. Seule la commande « ouvre Deezer »
    l'affiche."""
    try:
        _initialize_com()
        import win32gui
        import win32process
        import win32con
        import psutil
        
        deezer_pids = _get_deezer_pids()
        hwnd = None
        if deezer_pids:
            def enum_windows_callback(h, extra):
                nonlocal hwnd
                try:
                    _, pid = win32process.GetWindowThreadProcessId(h)
                    if pid in deezer_pids:
                        classname = win32gui.GetClassName(h)
                        if "Chrome_WidgetWin" in classname:
                            if not win32gui.GetParent(h):
                                hwnd = h
                                return False
                except Exception:
                    pass
                return True
            try:
                win32gui.EnumWindows(enum_windows_callback, None)
            except:
                pass

        if hwnd:
            if not afficher:
                return f"Deezer est déjà ouvert{nom_virgule()}."
            reparer_fenetres_deezer()   # fenêtre restée non activable / transparente : affichable
            try:
                if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
                    if win32gui.IsIconic(hwnd):
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    _attendre_deezer_prete(3.0)
                # « Ouvre Deezer » : l'utilisateur veut la voir, au premier plan
                try:
                    win32gui.SetForegroundWindow(hwnd)
                except Exception:
                    pass
            except:
                pass
            return f"Deezer est déjà ouvert et accessible{nom_virgule()}."

        # Si processus présent mais pas de fenêtre accessible, on le redémarre (Desktop uniquement)
        if deezer_pids:
            if os.path.exists(DEEZER_EXE):
                for pid in deezer_pids:
                    try: psutil.Process(pid).kill()
                    except: pass
                await asyncio.sleep(1.5)
            else:
                return f"Deezer est déjà ouvert en arrière-plan{nom_virgule()}."

        if os.path.exists(DEEZER_EXE):
            hwnd_before = None
            try: hwnd_before = win32gui.GetForegroundWindow()
            except: pass
            
            subprocess.Popen(
                [DEEZER_EXE, "--force-renderer-accessibility", cdp.ARG_PORT],
                cwd=DEEZER_DIR,
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            _attendre_deezer_prete(8.0)
            if hwnd_before and hwnd_before != 0:
                _restore_focus(hwnd_before)
            if not afficher:
                # Lancé pour une opération interne : on le réduit aussitôt
                _h = _get_deezer_hwnd_rapide()
                if _h:
                    win32gui.ShowWindow(_h, win32con.SW_SHOWMINNOACTIVE)
            return f"Deezer lancé en mode accessible{nom_virgule()}."
        else:
            hwnd_before = None
            try: hwnd_before = win32gui.GetForegroundWindow()
            except: pass
            subprocess.Popen(
                ["explorer", "deezer:"],
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            _attendre_deezer_prete(6.0)
            if hwnd_before and hwnd_before != 0:
                _restore_focus(hwnd_before)
            if not afficher:
                # Lancé pour une opération interne : on le réduit aussitôt
                _h = _get_deezer_hwnd_rapide()
                if _h:
                    win32gui.ShowWindow(_h, win32con.SW_SHOWMINNOACTIVE)
            return f"Deezer lancé via protocole standard{nom_virgule()}."
    except Exception as e:
        return f"Deezer ne s'est pas ouvert : {e}"

async def deezer_basculer_lecture():
    """Bascule Play/Pause en arrière-plan sans vol de focus."""
    # Pilotage direct si Deezer a été lancé avec son port (jamais de relancement ici)
    if await cdp.pret(1) and await cdp.controle("bascule") is not None:
        return f"Lecture/Pause sur Deezer{nom_virgule()}."
    hwnd = _get_deezer_hwnd_rapide()
    if hwnd:
        try:
            import win32gui
            WM_APPCOMMAND = 0x0319
            APPCOMMAND_MEDIA_PLAY_PAUSE = 14
            lParam = APPCOMMAND_MEDIA_PLAY_PAUSE << 16
            win32gui.PostMessage(hwnd, WM_APPCOMMAND, hwnd, lParam)
            return f"Lecture/Pause sur Deezer{nom_virgule()}."
        except Exception as e:
            print(f"[DEEZER UIA] Échec PostMessage play/pause : {e}")
            
    await deezer_demarrer(afficher=False)
    try:
        ctrl = get_deezer_main_control()
        if ctrl:
            top = ctrl.GetTopLevelControl()
            hwnd = top.NativeWindowHandle if top else None
            if hwnd:
                import win32gui
                WM_APPCOMMAND = 0x0319
                APPCOMMAND_MEDIA_PLAY_PAUSE = 14
                lParam = APPCOMMAND_MEDIA_PLAY_PAUSE << 16
                win32gui.PostMessage(hwnd, WM_APPCOMMAND, hwnd, lParam)
                return f"Lecture/Pause sur Deezer{nom_virgule()}."
    except Exception as e:
        print(f"[DEEZER UIA] Échec fallback play/pause : {e}")
        
    if pyautogui:
        pyautogui.press('playpause')
    return f"Lecture/Pause sur Deezer{nom_virgule()}."

async def deezer_piste_suivante():
    """Piste suivante en arrière-plan sans vol de focus."""
    # Pilotage direct si Deezer a été lancé avec son port (jamais de relancement ici)
    if await cdp.pret(1) and await cdp.controle("suivant") is not None:
        return f"Piste suivante sur Deezer{nom_virgule()}."
    hwnd = _get_deezer_hwnd_rapide()
    if hwnd:
        try:
            import win32gui
            WM_APPCOMMAND = 0x0319
            APPCOMMAND_MEDIA_NEXTTRACK = 11
            lParam = APPCOMMAND_MEDIA_NEXTTRACK << 16
            win32gui.PostMessage(hwnd, WM_APPCOMMAND, hwnd, lParam)
            return f"Piste suivante sur Deezer{nom_virgule()}."
        except Exception as e:
            print(f"[DEEZER UIA] Échec PostMessage suivant : {e}")
            
    await deezer_demarrer(afficher=False)
    try:
        ctrl = get_deezer_main_control()
        if ctrl:
            top = ctrl.GetTopLevelControl()
            hwnd = top.NativeWindowHandle if top else None
            if hwnd:
                import win32gui
                WM_APPCOMMAND = 0x0319
                APPCOMMAND_MEDIA_NEXTTRACK = 11
                lParam = APPCOMMAND_MEDIA_NEXTTRACK << 16
                win32gui.PostMessage(hwnd, WM_APPCOMMAND, hwnd, lParam)
                return f"Piste suivante sur Deezer{nom_virgule()}."
    except Exception as e:
        print(f"[DEEZER UIA] Échec fallback suivant : {e}")
        
    if pyautogui:
        pyautogui.press('nexttrack')
    return f"Piste suivante sur Deezer{nom_virgule()}."

async def deezer_piste_precedente():
    """Piste précédente en arrière-plan sans vol de focus."""
    # Pilotage direct si Deezer a été lancé avec son port (jamais de relancement ici)
    if await cdp.pret(1) and await cdp.controle("precedent") is not None:
        return f"Piste précédente sur Deezer{nom_virgule()}."
    hwnd = _get_deezer_hwnd_rapide()
    if hwnd:
        try:
            import win32gui
            WM_APPCOMMAND = 0x0319
            APPCOMMAND_MEDIA_PREVTRACK = 12
            lParam = APPCOMMAND_MEDIA_PREVTRACK << 16
            win32gui.PostMessage(hwnd, WM_APPCOMMAND, hwnd, lParam)
            return f"Piste précédente sur Deezer{nom_virgule()}."
        except Exception as e:
            print(f"[DEEZER UIA] Échec PostMessage précédent : {e}")
            
    await deezer_demarrer(afficher=False)
    try:
        ctrl = get_deezer_main_control()
        if ctrl:
            top = ctrl.GetTopLevelControl()
            hwnd = top.NativeWindowHandle if top else None
            if hwnd:
                import win32gui
                WM_APPCOMMAND = 0x0319
                APPCOMMAND_MEDIA_PREVTRACK = 12
                lParam = APPCOMMAND_MEDIA_PREVTRACK << 16
                win32gui.PostMessage(hwnd, WM_APPCOMMAND, hwnd, lParam)
                return f"Piste précédente sur Deezer{nom_virgule()}."
    except Exception as e:
        print(f"[DEEZER UIA] Échec fallback précédent : {e}")
        
    if pyautogui:
        pyautogui.press('prevtrack')
    return f"Piste précédente sur Deezer{nom_virgule()}."

async def deezer_arreter():
    """Arrête la lecture (Pause)."""
    if await cdp.pret(1):
        e = await cdp.etat()
        if e is not None:
            if not e.get("joue"):
                return f"La musique est déjà en pause{nom_virgule()}."
            if await cdp.controle("pause") is not None:
                return f"Musique mise en pause sur Deezer{nom_virgule()}."
    await deezer_demarrer(afficher=False)
    try:
        def _stop_uia():
            deezer_ctrl = get_deezer_main_control()
            if deezer_ctrl:
                btn = find_player_button(deezer_ctrl, ["Écouter"] + NOMS_BOUTON_PAUSE)
                if btn:
                    if btn.Name in NOMS_BOUTON_PAUSE:
                        if _clic_control(btn):
                            return f"Musique mise en pause sur Deezer{nom_virgule()}."
                    elif btn.Name == "Écouter":
                        return f"La musique est déjà en pause{nom_virgule()}."
            return None
            
        with _garder_focus_utilisateur(), _deezer_actionnable():
            res = await asyncio.to_thread(_stop_uia)
        if res:
            return res
    except:
        pass
        
    if pyautogui:
        pyautogui.press('playpause')
    return f"Musique mise en pause sur Deezer{nom_virgule()}."

async def deezer_regler_volume(direction, paliers=4):
    """Monte ou baisse le volume général du PC."""
    if not pyautogui:
        return "Volume impossible, pyautogui non disponible."
    await asyncio.sleep(0.2)
    for _ in range(int(paliers)):
        if direction in ("monter", "up", "augmenter", "plus"):
            pyautogui.press('volumeup')
        else:
            pyautogui.press('volumedown')
        await asyncio.sleep(0.05)
    msg = "Volume monté" if direction in ("monter", "up", "augmenter", "plus") else "Volume baissé"
    return f"{msg}{nom_virgule()}."

async def _deezer_pilotable(relancer=True):
    """Vrai si Deezer est pilotable par son port local (controller/deezer_cdp.py).

    Sinon, avec relancer=True, (re)lance Deezer avec ce port, réduit et sans prendre le
    focus. Un Deezer démarré sans le port (raccourci, démarrage de Windows) est fermé puis
    relancé : la lecture en cours s'interrompt, une seule fois par session de Deezer.
    Réservé aux commandes qui lancent une musique (pas à pause/suivant)."""
    if await cdp.pret(2):
        return True
    if not relancer or not os.path.exists(DEEZER_EXE):
        return False
    try:
        import psutil, win32gui, win32con
        print("[DEEZER] (Re)lancement de Deezer avec le port de pilotage, en arrière-plan...")
        avant = win32gui.GetForegroundWindow()
        for pid in _get_deezer_pids():
            try:
                psutil.Process(pid).kill()
            except Exception:
                pass
        await asyncio.sleep(1.5)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = win32con.SW_SHOWMINNOACTIVE
        subprocess.Popen([DEEZER_EXE, "--force-renderer-accessibility", cdp.ARG_PORT], cwd=DEEZER_DIR,
                         startupinfo=si, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        def _discret():
            # Deezer s'affiche parfois au démarrage malgré la demande : on le réduit
            # aussitôt et on rend le focus à la fenêtre de l'utilisateur.
            h = _get_deezer_hwnd_rapide()
            if h and win32gui.IsWindowVisible(h) and not win32gui.IsIconic(h):
                win32gui.ShowWindow(h, win32con.SW_SHOWMINNOACTIVE)
            if avant and not _fenetre_deezer(avant) and _fenetre_deezer(win32gui.GetForegroundWindow()):
                _restore_focus(avant)

        # Surveillance rapprochée (50 ms) dans un fil dédié pendant tout le démarrage
        import threading
        stop = threading.Event()
        def _veille():
            while not stop.is_set():
                try:
                    _discret()
                except Exception:
                    pass
                time.sleep(0.05)
        threading.Thread(target=_veille, daemon=True).start()
        try:
            pret = False
            fin = time.time() + 30
            while time.time() < fin and not pret:
                pret = await cdp.pret(0.5)
                await asyncio.sleep(0.2)
            await asyncio.sleep(8)  # Deezer se réaffiche parfois quelques secondes après
        finally:
            stop.set()
        print(f"[DEEZER] Deezer pilotable : {pret}")
        return pret
    except Exception as e:
        print(f"[DEEZER] Échec du relancement pilotable : {e}")
        return False

# ── Lancement sans lien deezer:// ─────────────────────────────────────────────
# Ouvrir un lien deezer:// restaure Deezer et lui donne le focus quand il est réduit
# (et parfois même sinon) : en pleine partie, le jeu passerait en arrière-plan. Toute
# la navigation passe donc par la barre de recherche et la barre latérale, pilotées
# par accessibilité, donc sans jamais afficher Deezer.

def _uia_clic_meilleur_resultat(titre, noms_boutons, timeout=10):
    """Clique un bouton (« Écouter », « Top titres »...) de la carte « Meilleur résultat »
    de la page de recherche, si le titre de cette carte correspond à `titre`."""
    if not auto:
        return False
    cibles = {_normalize(titre), _normalize(_titre_court(titre))} - {""}
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            ctrl = get_deezer_main_control()
            if ctrl:
                limite = _limite_barre_lecteur(ctrl)
                ancre, titres, boutons = [], [], []
                def _walk(c, depth=0):
                    if depth > 25:
                        return
                    t = c.ControlTypeName
                    n = c.Name or ""
                    if t == "TextControl" and n == "Meilleur résultat":
                        ancre.append(c.BoundingRectangle.top)
                    elif t == "TextControl" and _normalize(n) in cibles:
                        titres.append(c.BoundingRectangle.top)
                    elif t == "ButtonControl" and n in noms_boutons:
                        r = c.BoundingRectangle
                        if r.right - r.left > 0 and r.top < limite:
                            boutons.append((r.top, c))
                    for child in c.GetChildren():
                        _walk(child, depth + 1)
                _walk(ctrl)
                if ancre:
                    titres_carte = [y for y in titres if ancre[0] < y < ancre[0] + 450]
                    if titres_carte:
                        y_titre = titres_carte[0]
                        sous_titre = sorted((b for b in boutons if y_titre <= b[0] <= y_titre + 160),
                                            key=lambda b: b[0])
                        if sous_titre:
                            btn = sous_titre[0][1]
                            print(f"[DEEZER UIA] Clic « {btn.Name} » sur le meilleur résultat « {titre} »")
                            if _clic_control(btn):
                                return True
        except Exception as e:
            print(f"[DEEZER UIA] Avertissement meilleur résultat : {e}")
        time.sleep(0.3)
    return False

def _trouver_playlist_barre_laterale(requete):
    """Playlist de l'utilisateur dans la barre latérale dont le nom contient `requete`."""
    deezer_ctrl = get_deezer_main_control()
    if not deezer_ctrl:
        return None
    requete = requete.lower().strip()
    trouve = []
    def _walk(c, depth=0):
        if trouve or depth > 8:
            return
        try:
            rect = c.BoundingRectangle
            if rect.left >= 350 or rect.top >= 940:
                return
            if c.ControlTypeName in ("DataItemControl", "TextControl", "HyperlinkControl"):
                if requete in (c.Name or "").lower() and rect.right < 350:
                    trouve.append(c)
                    return
        except:
            pass
        for child in c.GetChildren():
            _walk(child, depth + 1)
    _walk(deezer_ctrl)
    return trouve[0] if trouve else None

def _lancer_morceau_ui(titre, artiste):
    """Recherche « titre artiste » et lance le morceau depuis la liste « Titres » des
    résultats : Deezer enchaîne ensuite sur les titres suivants de cette liste (la page
    de la piste, elle, ne joue que ce titre)."""
    if _uia_taper_dans_recherche(f"{titre} {artiste}") and _uia_clic_bouton_piste_album(titre, artiste, timeout=10):
        return _verifier_lecture(titre, artiste)
    return False

def _lancer_meilleur_resultat_ui(requete, titre, noms_boutons, titre_attendu=None, artiste_attendu=None):
    """Recherche `requete` puis clique `noms_boutons` sur la carte « Meilleur résultat »
    intitulée `titre` (album, artiste, playlist)."""
    if _uia_taper_dans_recherche(requete) and _uia_clic_meilleur_resultat(titre, noms_boutons):
        return _verifier_lecture(titre_attendu, artiste_attendu)
    return False

def _lancer_playlist_ui(nom, requete=None):
    """Lance une playlist : celles de l'utilisateur via la barre latérale, sinon via la
    carte « Meilleur résultat » de la recherche. Renvoie le nom affiché, ou None."""
    elem = _trouver_playlist_barre_laterale(requete or nom)
    if elem:
        # La barre latérale affiche « Werenoi par Neyor », l'en-tête de la page « Werenoi ».
        nom_complet = elem.Name or nom
        nom_court = nom_complet.rsplit(" par ", 1)[0]
        if _clic_control(elem):
            _trier_si_playlist("playlist")
            if _uia_clic_bouton_page_dynamique(NOMS_LECTURE, 12, wait_for_title=[nom_complet, nom_court]) \
                    and _verifier_lecture():
                return nom_court
        return None
    if _lancer_meilleur_resultat_ui(nom, nom, ["Écouter"]):
        return nom
    return None

_MOTS_VIDES = {"de", "du", "des", "la", "le", "les", "un", "une", "et", "par", "sur", "the"}


def _resultat_fiable(requete, resultat):
    """Le titre trouvé correspond-il à la demande ? (les mots significatifs de la requête se
    retrouvent dans « titre + artiste »). Sinon, la transcription a sans doute déformé un nom."""
    cible = _normalize(f"{resultat.get('title', '')} {(resultat.get('artist') or {}).get('name', '')}")
    mots = [_normalize(m) for m in re.split(r"\s+", requete) if len(m) >= 3 and m.lower() not in _MOTS_VIDES]
    mots = [m for m in mots if m]
    if not mots:
        return True
    return sum(m in cible for m in mots) / len(mots) >= 0.75


def _proche(requete, propose):
    """La correction ressemble-t-elle à ce qui a été entendu ? (« ou est renoi » / « Werenoi » : 0,71 ;
    « nique ta mère booba » / « Nekfeu », proposé à tort par l'IA : 0,24)"""
    import difflib
    a, b = _normalize(requete), _normalize(propose)
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.5 or (len(b) >= 4 and b in a)


async def _corriger_recherche(requete):
    """Nom d'artiste ou de titre probablement prononcé, quand la transcription l'a déformé
    (« Werenoi » entendu « au renoir », « ou est renoi »). None si rien de mieux.
    1. Deezer classe parfois le bon artiste en tête de sa recherche d'artistes : retenu s'il est
       très suivi (« au renoir » → Werenoi, 2,1 M de fans).
    2. Sinon, Gemini avec recherche Google (« ou est renoi » → Werenoi)."""
    try:
        r = await asyncio.to_thread(requests.get, "https://api.deezer.com/search/artist",
                                    params={"q": requete}, timeout=4)
        artistes = r.json().get("data", []) if r.status_code == 200 else []
        if artistes and artistes[0].get("nb_fan", 0) >= 500_000 and _proche(requete, artistes[0]["name"]):
            return artistes[0]["name"]
    except Exception as e:
        print(f"[DEEZER] Correction (artistes) impossible : {e}")
    try:
        from google.genai import types
        from core.ai_clients import client_gemini, api_activee
        if not api_activee("gemini"):
            return None
        consigne = ("Commande vocale française transcrite automatiquement, avec de probables erreurs "
                    "d'homophonie sur un nom d'artiste ou de titre. L'utilisateur veut écouter : "
                    f"« {requete} ». Cherche sur le web quel artiste ou titre existant se prononce ainsi, "
                    "puis réponds uniquement par la recherche Deezer correcte, en une ligne.")
        rep = await asyncio.wait_for(client_gemini.aio.models.generate_content(
            model="gemini-3.5-flash-lite", contents=consigne,
            config=types.GenerateContentConfig(temperature=0, tools=[types.Tool(google_search=types.GoogleSearch())])),
            timeout=6)
        propose = (rep.text or "").strip().strip("«»\"' .").splitlines()[0] if rep.text else ""
        if propose and _normalize(propose) != _normalize(requete) and len(propose) <= 80 and _proche(requete, propose):
            return propose
    except Exception as e:
        print(f"[DEEZER] Correction (IA) impossible : {e}")
    return None


async def deezer_chercher(recherche, _deja_corrige=False, _preparation=None):
    """Recherche intelligente d'un morceau, album, artiste ou playlist, et lance la lecture."""
    # Deezer est rendu pilotable (et relancé si besoin, ~13 s à froid) PENDANT la recherche et
    # l'éventuelle correction du nom, au lieu d'après : « joue Werenoi » prenait 20 s.
    preparation = _preparation or asyncio.ensure_future(_deezer_pilotable())
    recherche = recherche.strip(" ?!.,;")
    recherche_lower = recherche.lower().strip()
    type_recherche = "track"
    query = recherche
    
    # Détection de l'intention de jouer un mix d'artiste
    veux_mix = "mix" in recherche_lower
    
    if veux_mix:
        type_recherche = "artist"
        query = recherche_lower.replace("un mix de", "").replace("le mix de", "").replace("mix de", "").replace("un mix", "").replace("le mix", "").replace("mix", "").strip()
    elif "playlist" in recherche_lower:
        type_recherche = "playlist"
        query = recherche_lower.replace("la playlist", "").replace("ma playlist", "").replace("playlist", "").strip()
    elif "artiste" in recherche_lower or "groupe" in recherche_lower:
        type_recherche = "artist"
        query = recherche_lower.replace("l'artiste", "").replace("artiste", "").replace("groupe", "").strip()
    elif "album" in recherche_lower:
        type_recherche = "album"
        query = recherche_lower.replace("l'album", "").replace("album", "").strip()
    else:
        # Détection automatique de type si le terme recherché correspond exactement à un nom d'artiste
        try:
            url_artist = f"https://api.deezer.com/search/artist?q={requests.utils.quote(recherche)}"
            resp_art = await asyncio.to_thread(requests.get, url_artist, timeout=3)
            if resp_art.status_code == 200:
                artists = resp_art.json().get("data", [])
                exacts = [a for a in artists if _normalize(a.get("name", "")) == _normalize(recherche)]
                if exacts:
                    type_recherche = "artist"
                    query = exacts[0].get("name", "")
                    print(f"[DEEZER] Artiste exact détecté automatiquement : '{query}'")
        except Exception as e:
            print(f"[DEEZER] Erreur auto-détection artiste : {e}")
            
    print(f"[DEEZER] Recherche type={type_recherche} pour : '{query}'")
    
    try:
        # 1. Résolution via l'API Deezer
        if type_recherche == "playlist":
            url = f"https://api.deezer.com/search/playlist?q={requests.utils.quote(query)}"
        elif type_recherche == "artist":
            url = f"https://api.deezer.com/search/artist?q={requests.utils.quote(query)}"
        elif type_recherche == "album":
            url = f"https://api.deezer.com/search/album?q={requests.utils.quote(query)}"
        else:
            url = f"https://api.deezer.com/search?q={requests.utils.quote(query)}"
            
        resp = await asyncio.to_thread(requests.get, url, timeout=5)
        if resp.status_code != 200:
            return f"Je n'ai pas trouvé '{recherche}' sur Deezer{nom_virgule()}."
            
        data = resp.json()
        results = data.get("data", [])
        if not results:
            return f"Je n'ai pas trouvé '{recherche}' sur Deezer{nom_virgule()}."
            
        first_result = results[0]
        if type_recherche == "artist":
            # L'API classe parfois un homonyme peu connu en premier (« Ziak », 252 fans,
            # avant le vrai, 627 000) : parmi les noms exacts, on prend le plus suivi.
            exacts = [r for r in results if _normalize(r.get("name", "")) == _normalize(query)]
            if exacts:
                first_result = max(exacts, key=lambda r: r.get("nb_fan", 0))
        elif type_recherche == "track" and not _deja_corrige and not _resultat_fiable(query, first_result):
            # Titre sans rapport avec la demande : nom probablement déformé à la transcription
            corrige = await _corriger_recherche(query)
            if corrige:
                print(f"[DEEZER] Recherche corrigée : « {query} » → « {corrige} »")
                return await deezer_chercher(corrige, _deja_corrige=True, _preparation=preparation)
        res_id = first_result.get("id")

        if type_recherche == "playlist":
            name = first_result.get("title")
            artist = ""
            msg = f"C'est parti{nom_espace()}, je lance la playlist « {name} » sur Deezer."
        elif type_recherche == "artist":
            name = first_result.get("name")
            artist = name
            msg = (f"C'est parti{nom_espace()}, je lance le mix de l'artiste « {name} » sur Deezer." if veux_mix
                   else f"C'est parti{nom_espace()}, je lance les titres de l'artiste « {name} » sur Deezer.")
        elif type_recherche == "album":
            name = first_result.get("title")
            artist = first_result.get("artist", {}).get("name", "")
            msg = f"C'est parti{nom_espace()}, je lance l'album « {name} » de {artist} sur Deezer."
        else:
            name = first_result.get("title")
            artist = first_result.get("artist", {}).get("name", "")
            msg = f"C'est parti{nom_espace()}, je lance « {name} » de {artist} sur Deezer."
            
        echecs = {
            "track": f"J'ai trouvé « {name} » de {artist}, mais je n'ai pas réussi à le lancer sur Deezer{nom_virgule()}.",
            "playlist": f"J'ai trouvé la playlist « {name} », mais je n'ai pas réussi à la lancer sur Deezer{nom_virgule()}.",
            "artist": f"J'ai trouvé l'artiste « {name} », mais je n'ai pas réussi à lancer sa musique sur Deezer{nom_virgule()}.",
            "album": f"J'ai trouvé l'album « {name} », mais je n'ai pas réussi à le lancer sur Deezer{nom_virgule()}.",
        }

        # 2. Pilotage direct de la page Deezer (controller/deezer_cdp.py) : tout se fait en
        #    arrière-plan, Deezer réduit ou sous un jeu, et un titre est lancé depuis la
        #    liste des résultats pour que Deezer enchaîne. Chaque lancement est vérifié.
        if await preparation:
            if type_recherche == "track":
                ok = await cdp.lancer_titre(name, artist, (first_result.get("album") or {}).get("id"),
                                            _titre_court(name), morceau_id=res_id)
            elif type_recherche == "playlist":
                # Les playlists de l'utilisateur (barre latérale) passent avant la recherche
                perso = await cdp.trouver_playlist_bibliotheque(query)
                if perso:
                    res_id, name = perso
                    msg = f"C'est parti{nom_espace()}, je lance votre playlist « {name} » sur Deezer."
                ok = await cdp.lancer_page("playlist", res_id, name)
            elif type_recherche == "artist":
                ok = await cdp.lancer_artiste(name, res_id, mix=veux_mix)
            else:
                ok = await cdp.lancer_page("album", res_id, name, artist)
            return msg if ok else echecs[type_recherche]

        # 3. Secours, si le pilotage direct est indisponible : accessibilité Windows, sans
        #    jamais de lien deezer:// (voir plus haut), avec la même vérification.
        await deezer_demarrer(afficher=False)

        with _garder_focus_utilisateur(), _deezer_actionnable(), prevent_focus_theft():
            if type_recherche == "track":
                if _lancer_morceau_ui(name, artist):
                    return msg
                return f"J'ai trouvé « {name} » de {artist}, mais je n'ai pas réussi à le lancer sur Deezer{nom_virgule()}."

            elif type_recherche == "playlist":
                nom_lance = _lancer_playlist_ui(name, requete=query)
                if nom_lance:
                    return f"C'est parti{nom_espace()}, je lance la playlist « {nom_lance} » sur Deezer."
                return f"J'ai trouvé la playlist « {name} », mais je n'ai pas réussi à la lancer sur Deezer{nom_virgule()}."

            elif type_recherche == "artist":
                bouton = ["Mix artiste", "Mix de l'artiste", "Mix"] if veux_mix else ["Top titres"]
                if _lancer_meilleur_resultat_ui(name, name, bouton, artiste_attendu=None if veux_mix else name):
                    return msg
                return f"J'ai trouvé l'artiste « {name} », mais je n'ai pas réussi à lancer sa musique sur Deezer{nom_virgule()}."

            elif type_recherche == "album":
                if _lancer_meilleur_resultat_ui(f"{name} {artist}", name, ["Écouter"], artiste_attendu=artist):
                    return msg
                return f"J'ai trouvé l'album « {name} », mais je n'ai pas réussi à le lancer sur Deezer{nom_virgule()}."

        return msg
    except Exception as e:
        return f"Erreur lors de la recherche Deezer : {e}"

def _sort_playlist_dechronologique(deezer_ctrl):
    """Détecte le tri actuel de la playlist et clique sur 'AJOUTÉ' pour trier en déchronologique."""
    try:
        header_added = auto.HeaderControl(searchFromControl=deezer_ctrl, Name="AJOUTÉ")
        if not header_added.Exists(0.5):
            return False
            
        btn = header_added.ButtonControl(Name="AJOUTÉ")
        if not btn.Exists(0.5):
            return False
            
        tracks = []
        def find_tracks(ctrl):
            if ctrl.ControlTypeName == "CustomControl" and ctrl.Name and "Écouter" in ctrl.Name:
                tracks.append(ctrl.Name)
            for child in ctrl.GetChildren():
                find_tracks(child)
                if len(tracks) >= 15:
                    return
        find_tracks(deezer_ctrl)
        
        date_pattern = re.compile(r'\b(\d{2}/\d{2}/\d{4})\b')
        dates = []
        for t in tracks:
            found = date_pattern.findall(t)
            if found:
                try:
                    dt = datetime.strptime(found[0], "%d/%m/%Y")
                    dates.append(dt)
                except: pass
                
        first_dt = None
        current_sort = 'inconnu'
        for dt in dates:
            if first_dt is None:
                first_dt = dt
            elif dt != first_dt:
                if first_dt < dt:
                    current_sort = 'asc'
                else:
                    current_sort = 'desc'
                break
                
        if current_sort in ('asc', 'inconnu'):
            _clic_control(btn)
            time.sleep(1.0)
            return True
        return False
    except Exception as e:
        print(f"[DEEZER UIA] Erreur tri : {e}")
        return False

def _trier_si_playlist(uri):
    """Détecte le chargement de la playlist et applique le tri déchronologique."""
    if "playlist" not in uri.lower():
        return
    try:
        t0 = time.time()
        deezer_ctrl = None
        while time.time() - t0 < 8:
            try:
                deezer_ctrl = get_deezer_main_control()
                if deezer_ctrl:
                    header = auto.HeaderControl(searchFromControl=deezer_ctrl, Name="AJOUTÉ")
                    if header.Exists(0.1):
                        break
            except:
                pass
            time.sleep(0.5)
            
        if deezer_ctrl:
            _sort_playlist_dechronologique(deezer_ctrl)
    except Exception as e:
        print(f"[DEEZER] Échec tri auto : {e}")

async def deezer_lancer_playlist(url=None):
    """Lance la playlist configurée (lien Deezer : playlist, album, artiste ou titre) ou,
    sans lien, reprend la lecture. Tout se fait en arrière-plan : le lien sert seulement
    à retrouver le nom via l'API Deezer, jamais à ouvrir une URI deezer:// (qui
    afficherait Deezer et lui donnerait le focus)."""
    try:
        playlist_url = url or os.getenv("DEEZER_PLAYLIST_URL")

        if playlist_url:
            if "link.deezer.com" in playlist_url:
                try:
                    r = await asyncio.to_thread(requests.head, playlist_url, allow_redirects=True, timeout=5)
                    playlist_url = r.url
                except:
                    pass
            m = re.search(r"/(playlist|album|artist|track)/(\d+)", playlist_url)
            if not m:
                print(f"[DEEZER] Lien non reconnu : {playlist_url}")
                return False
            genre, ident = m.groups()
            resp = await asyncio.to_thread(requests.get, f"https://api.deezer.com/{genre}/{ident}", timeout=5)
            info = resp.json() if resp.status_code == 200 else {}
            nom = info.get("title") or info.get("name")
            if not nom:
                print(f"[DEEZER] Impossible de retrouver le nom de {genre}/{ident}")
                return False
            artiste = (info.get("artist") or {}).get("name", "")

            if await _deezer_pilotable():
                if genre == "track":
                    return await cdp.lancer_titre(nom, artiste, (info.get("album") or {}).get("id"),
                                                  _titre_court(nom), morceau_id=ident)
                if genre == "artist":
                    return await cdp.lancer_artiste(nom, ident)
                return await cdp.lancer_page(genre, ident, nom, artiste or None)

            await deezer_demarrer(afficher=False)
            with _garder_focus_utilisateur(), _deezer_actionnable(), prevent_focus_theft():
                if genre == "playlist":
                    return bool(_lancer_playlist_ui(nom))
                if genre == "track":
                    return _lancer_morceau_ui(nom, artiste)
                if genre == "album":
                    return _lancer_meilleur_resultat_ui(f"{nom} {artiste}", nom, ["Écouter"], artiste_attendu=artiste)
                return _lancer_meilleur_resultat_ui(nom, nom, ["Top titres"], artiste_attendu=nom)
        else:
            if await cdp.pret(1):
                return await cdp.controle("lecture") is not None
            await deezer_demarrer(afficher=False)
            with _garder_focus_utilisateur(), _deezer_actionnable(), prevent_focus_theft():
                await asyncio.sleep(1)
                await asyncio.to_thread(_uia_clic_bouton, ["Écouter"])
                await asyncio.sleep(1.5)
                return True
    except Exception as e:
        print(f"[DEEZER] Erreur lancement playlist : {e}")
        return False

def deezer_obtenir_titre_encours():
    """Extrait le titre et l'artiste en cours depuis le DocumentControl UIA de Deezer."""
    if not auto:
        return None
    try:
        _initialize_com()
        deezer_ctrl = get_deezer_main_control()
        if not deezer_ctrl:
            return None
        title = deezer_ctrl.Name
        if title and " - Deezer" in title:
            song_info = title.replace(" - Deezer", "").strip()
            if " - " in song_info:
                parts = song_info.split(" - ", 1)
                return {
                    "title": parts[0].strip(),
                    "artist": parts[1].strip(),
                    "status": "Playing"
                }
            return {"title": song_info, "artist": "Deezer", "status": "Playing"}
    except:
        pass
    return None
