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
DEEZER_EXE = r"C:\Users\mylan\AppData\Local\Programs\deezer-desktop\Deezer.exe"
DEEZER_DIR = r"C:\Users\mylan\AppData\Local\Programs\deezer-desktop"

_cached_deezer_pids = []

def _normalize(text):
    """Normalise le texte pour comparaison robuste (sans accents, sans ponctuation, minuscules)."""
    if not text:
        return ""
    text = unicodedata.normalize('NFD', text)
    text = "".join(c for c in text if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^a-zA-Z0-9]', '', text)
    return text.lower().strip()

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

def _sauter_deezer_accessible():
    """Vérifie si Deezer tourne avec l'accessibilité activée."""
    return get_deezer_main_control()

def _focus_deezer():
    """Met la fenêtre Deezer au premier plan."""
    try:
        ctrl = get_deezer_main_control()
        if ctrl:
            top = ctrl.GetTopLevelControl()
            if top:
                import win32gui, win32con
                hwnd = top.NativeWindowHandle
                if hwnd:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    try: top.SetActive()
                    except: pass
                    try: top.SetFocus()
                    except: pass
                    try: win32gui.SetForegroundWindow(hwnd)
                    except: pass
                    time.sleep(0.3)
                    return True
    except Exception as e:
        print(f"[DEEZER UIA] Échec _focus_deezer UIA: {e}")
        
    try:
        import win32gui, win32con
        candidats = []
        def _cb(hwnd, _):
            try:
                if win32gui.IsWindowVisible(hwnd):
                    titre = win32gui.GetWindowText(hwnd)
                    if "Deezer" in titre:
                        candidats.append(hwnd)
            except:
                pass
            return True
        try:
            win32gui.EnumWindows(_cb, None)
        except:
            pass
        if not candidats:
            return False
        hwnd = candidats[0]
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.4)
        return True
    except Exception:
        return False

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
                if legacy_pat:
                    legacy_pat.DoDefaultAction()
                    time.sleep(0.1)
                    active_now = win32gui.GetForegroundWindow()
                    if active_now != hwnd_before and hwnd_before != 0:
                        _restore_focus(hwnd_before)
                    return True
            except Exception as e:
                pass

            # 2. InvokePattern
            try:
                pattern = btn.GetInvokePattern()
                if pattern:
                    pattern.Invoke()
                    _restore_focus(hwnd_before)
                    return True
            except Exception as e:
                pass

            # 3. Fallback clic physique
            try:
                btn.Click(simulateMove=False)
                _restore_focus(hwnd_before)
                return True
            except Exception as e:
                pass
                
            return False
        except Exception as ex:
            print(f"[DEEZER UIA] Erreur clic contrôle : {ex}")
            return False

def find_player_button(deezer_ctrl, button_names):
    """Trouve un bouton du player principal."""
    buttons = []
    def _collect_buttons(control):
        if control.ControlTypeName == "ButtonControl":
            name = control.Name or ""
            if name in button_names or any(b in name for b in button_names):
                buttons.append(control)
        for child in control.GetChildren():
            _collect_buttons(child)
            
    _collect_buttons(deezer_ctrl)
    
    for btn in buttons:
        curr = btn
        for _ in range(5):
            if not curr:
                break
            parent = curr.GetParentControl()
            if not parent:
                break
            sibling_names = [c.Name for c in parent.GetChildren() if c.ControlTypeName == "ButtonControl"]
            if any(s in sibling_names for s in ["Suivant", "Précédent", "Activer la lecture aléatoire", "Répéter", "Muet"]):
                return btn
            curr = parent
            
    if buttons:
        return buttons[0]
    return None

def find_page_play_button(deezer_ctrl, button_names):
    """Recherche le bouton de lecture au sein de la page (exclut le lecteur du bas)."""
    buttons = []
    def _collect_buttons(control):
        if control.ControlTypeName == "ButtonControl":
            name = control.Name or ""
            if name in button_names or any(b in name for b in button_names):
                try:
                    rect = control.BoundingRectangle
                    if rect.right - rect.left > 0:
                        buttons.append(control)
                except:
                    pass
        for child in control.GetChildren():
            _collect_buttons(child)
            
    _collect_buttons(deezer_ctrl)
    
    page_buttons = []
    for btn in buttons:
        is_player_bar = False
        curr = btn
        for _ in range(5):
            if not curr:
                break
            parent = curr.GetParentControl()
            if not parent:
                break
            sibling_names = [c.Name for c in parent.GetChildren() if c.ControlTypeName == "ButtonControl"]
            if any(s in sibling_names for s in ["Suivant", "Précédent", "Activer la lecture aléatoire", "Répéter", "Muet"]):
                is_player_bar = True
                break
            curr = parent
            
        if not is_player_bar:
            page_buttons.append(btn)
            
    if page_buttons:
        return page_buttons[0]
    return None

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
    """Attend le chargement de la page et clique sur son bouton de lecture."""
    if not auto:
        return False
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            deezer_ctrl = get_deezer_main_control()
            if deezer_ctrl:
                if wait_for_title:
                    doc_title = deezer_ctrl.Name or ""
                    if wait_for_title.lower() not in doc_title.lower() and "deezer" not in doc_title.lower():
                        time.sleep(0.25)
                        continue
                        
                btn = find_page_play_button(deezer_ctrl, noms_boutons)
                if btn:
                    if _clic_control(btn):
                        return True
        except:
            pass
        time.sleep(0.3)
    return False

def _uia_clic_bouton_piste_album(track_title, artist_name=None, timeout=15):
    """Trouve et clique la ligne d'un morceau ou son bouton de lecture dans les résultats ou sur une page."""
    if not auto:
        return False
    t0 = time.time()
    track_title_lower = _normalize(track_title)
    artist_lower = _normalize(artist_name) if artist_name else None
    
    while time.time() - t0 < timeout:
        try:
            deezer_ctrl = get_deezer_main_control()
            if not deezer_ctrl:
                time.sleep(0.3)
                continue
                
            # Étape 1 : Parcourir le DOM pour trouver la ligne (row/item) du morceau
            row_control = None
            def _find_row(c, depth=0):
                if depth > 18:
                    return None
                name = _normalize(c.Name or "")
                
                if track_title_lower in name:
                    if not artist_lower or artist_lower in name:
                        try:
                            rect = c.BoundingRectangle
                            if (rect.right - rect.left) > 0 and (rect.bottom - rect.top) > 0:
                                return c
                        except:
                            pass
                            
                for child in c.GetChildren():
                    res = _find_row(child, depth + 1)
                    if res:
                        return res
                return None
                
            row_control = _find_row(deezer_ctrl)
            
            if row_control:
                # Étape 2 : Chercher un bouton de lecture à l'intérieur de cette ligne
                btn_play = None
                def _find_play_btn(c, depth=0):
                    if depth > 5:
                        return None
                    ctype = c.ControlTypeName or ""
                    name = (c.Name or "").lower()
                    if ctype == "ButtonControl" and (name.startswith("écouter") or "play" in name or "lire" in name or not name):
                        return c
                    for child in c.GetChildren():
                        res = _find_play_btn(child, depth + 1)
                        if res:
                            return res
                    return None
                    
                btn_play = _find_play_btn(row_control)
                
                if btn_play:
                    print(f"[DEEZER UIA] Clic sur le bouton de lecture de la ligne : '{btn_play.Name}'")
                    if _clic_control(btn_play):
                        return True
                else:
                    # Cliquer directement sur la ligne
                    print(f"[DEEZER UIA] Clic sur la ligne elle-même : '{row_control.Name}'")
                    if _clic_control(row_control):
                        return True
                        
            # Étape 3 : Fallback historique (chercher n'importe quel bouton qui commence par écouter)
            def _find_any_button(c, depth=0):
                if depth > 15:
                    return None
                ctype = c.ControlTypeName or ""
                name = (c.Name or "").lower()
                if ctype == "ButtonControl" and name.startswith("écouter"):
                    if track_title_lower in _normalize(name):
                        if not artist_lower or artist_lower in _normalize(name):
                            return c
                for child in c.GetChildren():
                    res = _find_any_button(child, depth + 1)
                    if res:
                        return res
                return None
                
            btn = _find_any_button(deezer_ctrl)
            if btn:
                print(f"[DEEZER UIA] Clic sur le bouton global trouvé : '{btn.Name}'")
                if _clic_control(btn):
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
            deezer_ctrl = get_deezer_main_control()
            if not deezer_ctrl:
                return False
                
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
            search_edit = _find_edit(deezer_ctrl)
            
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

def _ouvrir_uri_deezer(uri):
    """Ouvre une URI Deezer en ciblant directement l'exécutable de l'instance en cours si elle tourne,
    ou l'exécutable standard sinon (évite d'ouvrir de nouvelles fenêtres unlinked)."""
    try:
        import psutil
        running_exe = None
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                if proc.info['name'] and 'deezer' in proc.info['name'].lower():
                    exe = proc.info['exe']
                    if exe and os.path.exists(exe):
                        running_exe = exe
                        break
            except:
                pass
                
        if running_exe:
            print(f"[DEEZER UIA] Envoi URI à l'exécutable en cours : {running_exe}")
            subprocess.Popen([running_exe, uri], shell=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif os.path.exists(DEEZER_EXE):
            print(f"[DEEZER UIA] Envoi URI à l'exécutable par défaut : {DEEZER_EXE}")
            subprocess.Popen([DEEZER_EXE, uri], shell=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            print(f"[DEEZER UIA] Envoi URI via explorer")
            subprocess.Popen(["explorer", uri], shell=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[DEEZER UIA] Échec ouverture URI {uri} : {e}")

def _get_deezer_hwnd_rapide():
    """Trouve le HWND de Deezer (même en tray/minimisé) SANS le restaurer ni voler le focus.
    Utilisé pour les commandes média rapides : play/pause, suivant, précédent."""
    try:
        import win32gui, win32process
        deezer_pids = _get_deezer_pids()
        if not deezer_pids:
            return None
        hwnd_result = [None]
        def _cb(hwnd, _):
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid in deezer_pids:
                    classname = win32gui.GetClassName(hwnd)
                    if "Chrome_WidgetWin" in classname and not win32gui.GetParent(hwnd):
                        hwnd_result[0] = hwnd
                        return False
            except Exception:
                pass
            return True
        try:
            win32gui.EnumWindows(_cb, None)
        except:
            pass
        return hwnd_result[0]
    except Exception:
        return None

async def deezer_ouvrir():
    """Lance Deezer s'il n'est pas ouvert en s'assurant que l'accessibilité soit active."""
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
            try:
                if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
                    if win32gui.IsIconic(hwnd):
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    _attendre_deezer_prete(3.0)
            except:
                pass
            return f"Deezer est déjà ouvert et accessible{nom_virgule()}."

        # Si processus présent mais pas de fenêtre accessible, on le redémarre (Desktop uniquement)
        if deezer_pids:
            if os.path.exists(DEEZER_EXE):
                for pid in deezer_pids:
                    try: psutil.Process(pid).kill()
                    except: pass
                time.sleep(1.5)
            else:
                return f"Deezer est déjà ouvert en arrière-plan{nom_virgule()}."

        if os.path.exists(DEEZER_EXE):
            hwnd_before = None
            try: hwnd_before = win32gui.GetForegroundWindow()
            except: pass
            
            subprocess.Popen(
                [DEEZER_EXE, "--force-renderer-accessibility"],
                cwd=DEEZER_DIR,
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            _attendre_deezer_prete(8.0)
            if hwnd_before and hwnd_before != 0:
                _restore_focus(hwnd_before)
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
            return f"Deezer lancé via protocole standard{nom_virgule()}."
    except Exception as e:
        return f"Je n'ai pas réussi à ouvrir Deezer : {e}"

async def deezer_lecture_pause():
    """Bascule Play/Pause en arrière-plan sans vol de focus."""
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
            
    await deezer_ouvrir()
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

async def deezer_suivant():
    """Piste suivante en arrière-plan sans vol de focus."""
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
            
    await deezer_ouvrir()
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

async def deezer_precedent():
    """Piste précédente en arrière-plan sans vol de focus."""
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
            
    await deezer_ouvrir()
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

async def deezer_stop():
    """Arrête la lecture (Pause)."""
    await deezer_ouvrir()
    try:
        def _stop_uia():
            deezer_ctrl = get_deezer_main_control()
            if deezer_ctrl:
                btn = find_player_button(deezer_ctrl, ["Écouter", "Pause", "Mettre en pause"])
                if btn:
                    if btn.Name in ["Pause", "Mettre en pause"]:
                        if _clic_control(btn):
                            return f"Musique mise en pause sur Deezer{nom_virgule()}."
                    elif btn.Name == "Écouter":
                        return f"La musique est déjà en pause{nom_virgule()}."
            return None
            
        res = await asyncio.to_thread(_stop_uia)
        if res:
            return res
    except:
        pass
        
    if pyautogui:
        pyautogui.press('playpause')
    return f"Musique mise en pause sur Deezer{nom_virgule()}."

async def deezer_volume(direction, paliers=4):
    """Monte ou baisse le volume général du PC."""
    if not pyautogui:
        return "Volume impossible, pyautogui non disponible."
    time.sleep(0.2)
    for _ in range(int(paliers)):
        if direction in ("monter", "up", "augmenter", "plus"):
            pyautogui.press('volumeup')
        else:
            pyautogui.press('volumedown')
        time.sleep(0.05)
    msg = "Volume monté" if direction in ("monter", "up", "augmenter", "plus") else "Volume baissé"
    return f"{msg}{nom_virgule()}."

async def deezer_rechercher(recherche):
    """Recherche intelligente d'un morceau, album, artiste ou playlist, et lance la lecture."""
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
                if artists:
                    top_artist = artists[0]
                    top_artist_name = top_artist.get("name", "")
                    if _normalize(top_artist_name) == _normalize(recherche):
                        type_recherche = "artist"
                        query = top_artist_name
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
        res_id = first_result.get("id")
        
        if type_recherche == "playlist":
            name = first_result.get("title")
            artist = ""
            msg = f"C'est parti{nom_espace()}, je lance la playlist « {name} » sur Deezer."
        elif type_recherche == "artist":
            name = first_result.get("name")
            artist = name
            msg = f"C'est parti{nom_espace()}, je lance les titres de l'artiste « {name} » sur Deezer."
        elif type_recherche == "album":
            name = first_result.get("title")
            artist = first_result.get("artist", {}).get("name", "")
            msg = f"C'est parti{nom_espace()}, je lance l'album « {name} » de {artist} sur Deezer."
        else:
            name = first_result.get("title")
            artist = first_result.get("artist", {}).get("name", "")
            msg = f"C'est parti{nom_espace()}, je lance « {name} » de {artist} sur Deezer."
            
        # 2. Exécution avec contrôle d'accessibilité
        await deezer_ouvrir()
        
        with prevent_focus_theft():
            if type_recherche == "track":
                search_query = f"{name} {artist}"
                if _uia_taper_dans_recherche(search_query):
                    ok = _uia_clic_bouton_piste_album(name, artist, timeout=10)
                    if ok:
                        time.sleep(1.5)
                        return msg
                
                # Fallback direct : ouvrir la piste sans passer par l'album complet
                print(f"[DEEZER] Fallback page piste directe pour '{name}'")
                _ouvrir_uri_deezer(f"deezer://track/{res_id}")
                _uia_clic_bouton_page_dynamique(
                    ["Écouter", "Lecture", "Mix", "Reprendre", "À l'écoute", "Pause", "Mettre en pause"],
                    12, wait_for_title=name
                )
                return msg
                
            elif type_recherche == "playlist":
                # Vérifier la barre latérale en premier
                deezer_ctrl = get_deezer_main_control()
                elem_playlist = None
                if deezer_ctrl:
                    query_lower = query.lower().strip()
                    def _find_sidebar(c, depth=0):
                        nonlocal elem_playlist
                        if elem_playlist or depth > 8:
                            return
                        try:
                            rect = c.BoundingRectangle
                            if rect.left >= 350 or rect.top >= 940:
                                return
                            n = c.Name or ""
                            ctype = c.ControlTypeName or ""
                            if ctype in ("DataItemControl", "TextControl", "HyperlinkControl"):
                                if query_lower in n.lower() and rect.right < 350:
                                    elem_playlist = c
                                    return
                        except:
                            pass
                        for child in c.GetChildren():
                            _find_sidebar(child, depth + 1)
                            
                    _find_sidebar(deezer_ctrl)
                    
                if elem_playlist:
                    if _clic_control(elem_playlist):
                        _trier_si_playlist("playlist")
                        _uia_clic_bouton_page_dynamique(
                            ["Écouter", "Lecture", "Mix", "Reprendre", "À l'écoute", "Pause", "Mettre en pause"],
                            12, wait_for_title=query
                        )
                        time.sleep(1.5)
                        return f"C'est parti{nom_espace()}, je lance votre playlist « {query} » sur Deezer."
                
                # Navigation directe via URI
                _ouvrir_uri_deezer(f"deezer://playlist/{res_id}")
                _trier_si_playlist(f"deezer://playlist/{res_id}")
                _uia_clic_bouton_page_dynamique(
                    ["Écouter", "Lecture", "Mix", "Reprendre", "À l'écoute", "Pause", "Mettre en pause"],
                    12, wait_for_title=name
                )
                return msg
                
            elif type_recherche == "artist":
                _ouvrir_uri_deezer(f"deezer://artist/{res_id}")
                if veux_mix:
                    print(f"[DEEZER UIA] Lancement du Mix de l'artiste {name}")
                    _uia_clic_bouton_page_dynamique(
                        ["Mix de l'artiste", "Mix"],
                        12, wait_for_title=name
                    )
                else:
                    print(f"[DEEZER UIA] Lancement des Top Titres de l'artiste {name}")
                    first_track_name = None
                    try:
                        url_top = f"https://api.deezer.com/artist/{res_id}/top"
                        resp_top = await asyncio.to_thread(requests.get, url_top, timeout=3)
                        if resp_top.status_code == 200:
                            top_tracks = resp_top.json().get("data", [])
                            if top_tracks:
                                first_track_name = top_tracks[0].get("title", "")
                                print(f"[DEEZER UIA] Premier top morceau détecté : '{first_track_name}'")
                    except Exception as e:
                        print(f"[DEEZER UIA] Impossible de récupérer le premier morceau : {e}")
                        
                    clicked = False
                    if first_track_name:
                        clicked = _uia_clic_bouton_piste_album(first_track_name, name, timeout=12)
                        
                    if not clicked:
                        _uia_clic_bouton_page_dynamique(
                            ["Écouter", "Lecture", "Reprendre", "À l'écoute", "Pause", "Mettre en pause"],
                            12, wait_for_title=name
                        )
                return msg
                
            elif type_recherche == "album":
                _ouvrir_uri_deezer(f"deezer://album/{res_id}")
                _uia_clic_bouton_page_dynamique(
                    ["Écouter", "Lecture", "Mix", "Reprendre", "À l'écoute", "Pause", "Mettre en pause"],
                    12, wait_for_title=name
                )
                return msg
                
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
    """Lance la playlist configurée ou par défaut, puis démarre la lecture."""
    try:
        playlist_url = url or os.getenv("DEEZER_PLAYLIST_URL")
        
        if playlist_url:
            if "link.deezer.com" in playlist_url:
                try:
                    r = await asyncio.to_thread(requests.head, playlist_url, allow_redirects=True, timeout=5)
                    playlist_url = r.url
                except:
                    pass
            if "/playlist/" in playlist_url:
                p_id = playlist_url.split("/playlist/")[-1].split("?")[0]
                deezer_uri = f"deezer://playlist/{p_id}"
            else:
                deezer_uri = playlist_url
                
            _ouvrir_uri_deezer(deezer_uri)
            _trier_si_playlist(deezer_uri)
            
            # Clic lecture
            await asyncio.to_thread(
                _uia_clic_bouton_page_dynamique,
                ["Écouter", "Lecture", "Mix", "Reprendre", "À l'écoute", "Pause", "Mettre en pause"],
                12
            )
            time.sleep(1.5)
            return True
        else:
            await deezer_ouvrir()
            with prevent_focus_theft():
                time.sleep(1)
                await asyncio.to_thread(_uia_clic_bouton, ["Écouter", "Pause", "Mettre en pause"])
                time.sleep(1.5)
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
