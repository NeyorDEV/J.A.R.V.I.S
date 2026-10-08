import os
import subprocess
try:
    import psutil
except ImportError:
    psutil = None
import asyncio
import shutil
import time
from typing import TYPE_CHECKING
from core.interlocuteur import nom_espace, nom_virgule

if TYPE_CHECKING:
    async def parler(text: str) -> None: ...

# MODE BOULOT
# ==========================================

def _boulot_trouver_exe(noms_exe: list, chemins_hints: list = None) -> str:
    """Trouve un exécutable sur n'importe quel Windows.
    Ordre : registre App Paths → PATH système → chemins connus."""
    # 1. Registre Windows (le plus fiable — tous les apps installées y sont)
    try:
        import winreg
        for exe in noms_exe:
            for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                try:
                    key = winreg.OpenKey(
                        hive,
                        f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{exe}"
                    )
                    path, _ = winreg.QueryValueEx(key, "")
                    winreg.CloseKey(key)
                    p = os.path.expandvars(path.strip('"'))
                    if os.path.exists(p):
                        return p
                except Exception:
                    pass
    except ImportError:
        pass

    # 2. PATH système
    for exe in noms_exe:
        found = shutil.which(exe)
        if found:
            return found

    # 3. Chemins connus communs
    if chemins_hints:
        for hint in chemins_hints:
            p = os.path.expandvars(hint)
            if os.path.exists(p):
                return p

    return ""


def _boulot_lancer(label: str, noms_exe: list,
                   chemins_hints: list = None, env_key: str = None) -> bool:
    """Lance une application — détection universelle, sans popup d'erreur Windows."""
    # Override via .env (priorité absolue)
    if env_key:
        env_val = os.path.expandvars(os.getenv(env_key, ""))
        if env_val and os.path.exists(env_val):
            try:
                subprocess.Popen([env_val])
                return True
            except Exception:
                pass

    # Détection automatique (registre → PATH → hints)
    exe_path = _boulot_trouver_exe(noms_exe, chemins_hints)
    if exe_path:
        try:
            subprocess.Popen([exe_path])
            return True
        except Exception:
            pass

    # Pas trouvé — on log silencieusement, aucune popup Windows
    print(f"[BOULOT] {label} introuvable sur ce PC (registre, PATH et hints épuisés)")
    return False


# « Update.exe » est le nom générique de l'installeur Squirrel, partagé par de nombreuses applis :
# le fermer pour Discord tuait aussi les mises à jour des autres.
_JAMAIS_FERMER = {"update.exe"}


def _fermer_app(noms_process: list, forcer: bool = False):
    """Ferme les processus nommés : demande de fermeture d'abord (l'application peut proposer
    d'enregistrer), puis, si `forcer`, arrêt forcé de ceux qui résistent au bout de 3 s.
    Avant, tout était tué d'office (proc.terminate) : « ferme Word » perdait le document en cours.

    Renvoie None si aucun n'était lancé, True s'ils sont fermés, False s'ils résistent."""
    if psutil is None:
        return False
    noms = [n for n in noms_process if n.lower() not in _JAMAIS_FERMER]
    cibles = {n.lower() for n in noms}

    def vivants():
        trouves = []
        for proc in psutil.process_iter(['name']):
            try:
                if (proc.info['name'] or "").lower() in cibles:
                    trouves.append(proc)
            except Exception:
                pass
        return trouves

    if not vivants():
        return None
    for n in noms:
        subprocess.run(["taskkill", "/IM", n], capture_output=True)
    for _ in range(15):
        time.sleep(0.2)
        if not vivants():
            return True
    if forcer:
        for proc in vivants():
            try:
                proc.kill()
            except Exception:
                pass
        time.sleep(0.5)
    return not vivants()


# Catalogue d'applications ouvrables / fermables par commande vocale
_APPS_CATALOGUE = {
    # ── Navigateurs ──────────────────────────────────────────
    "chrome": {
        "label": "Google Chrome", "noms": ["chrome.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
            r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe",
            r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe",
        ],
    },
    "firefox": {
        "label": "Firefox", "noms": ["firefox.exe"],
        "hints": [r"%PROGRAMFILES%\Mozilla Firefox\firefox.exe", r"%PROGRAMFILES(X86)%\Mozilla Firefox\firefox.exe"],
    },
    "edge": {
        "label": "Microsoft Edge", "noms": ["msedge.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe",
            r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe",
        ],
    },
    "opera": {
        "label": "Opera", "noms": ["opera.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Programs\Opera\opera.exe",
            r"%LOCALAPPDATA%\Programs\Opera GX\opera.exe",
            r"%APPDATA%\Opera Software\Opera Stable\opera.exe",
            r"%APPDATA%\Opera Software\Opera GX Stable\opera.exe",
        ],
    },
    "brave": {
        "label": "Brave", "noms": ["brave.exe"],
        "hints": [
            r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"%PROGRAMFILES%\BraveSoftware\Brave-Browser\Application\brave.exe",
        ],
    },
    # ── Jeux / Launchers ─────────────────────────────────────
    "steam": {
        "label": "Steam", "noms": ["steam.exe"],
        "hints": [r"%PROGRAMFILES(X86)%\Steam\steam.exe", r"%PROGRAMFILES%\Steam\steam.exe"],
    },
    "epic": {
        "label": "Epic Games", "noms": ["EpicGamesLauncher.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe",
            r"%PROGRAMFILES%\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe",
        ],
    },
    "origin": {
        "label": "Origin", "noms": ["Origin.exe"],
        "hints": [r"%PROGRAMFILES(X86)%\Origin\Origin.exe", r"%PROGRAMFILES%\Origin\Origin.exe"],
    },
    "ea": {
        "label": "EA App", "noms": ["EADesktop.exe", "EA.exe"],
        "hints": [
            r"%PROGRAMFILES%\Electronic Arts\EA Desktop\EA Desktop.exe",
            r"%PROGRAMFILES(X86)%\Electronic Arts\EA Desktop\EA Desktop.exe",
        ],
    },
    "ubisoft": {
        "label": "Ubisoft Connect", "noms": ["UbisoftConnect.exe", "upc.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\Ubisoft\Ubisoft Game Launcher\UbisoftConnect.exe",
            r"%PROGRAMFILES%\Ubisoft\Ubisoft Game Launcher\UbisoftConnect.exe",
        ],
    },
    "gog": {
        "label": "GOG Galaxy", "noms": ["GalaxyClient.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\GOG Galaxy\GalaxyClient.exe",
            r"%PROGRAMFILES%\GOG Galaxy\GalaxyClient.exe",
        ],
    },
    "minecraft": {
        "label": "Minecraft", "noms": ["Minecraft.exe", "MinecraftLauncher.exe"],
        "hints": [
            r"%PROGRAMFILES(X86)%\Minecraft Launcher\MinecraftLauncher.exe",
            r"%LOCALAPPDATA%\Packages\Microsoft.4297127D64EC6_8wekyb3d8bbwe\Minecraft.exe",
        ],
    },
    # ── Communication ────────────────────────────────────────
    "discord": {
        "label": "Discord", "noms": ["Discord.exe", "Update.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Discord\Update.exe",
            r"%LOCALAPPDATA%\Discord\app-*\Discord.exe",
            r"%APPDATA%\Discord\Update.exe",
        ],
    },
    "teams": {
        "label": "Microsoft Teams", "noms": ["ms-teams.exe", "Teams.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\ms-teams.exe",
            r"%LOCALAPPDATA%\Microsoft\Teams\current\Teams.exe",
            r"%PROGRAMFILES%\Microsoft\Teams\current\Teams.exe",
        ],
    },
    "whatsapp": {
        "label": "WhatsApp", "noms": ["WhatsApp.exe"],
        "hints": [
            r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe",
            r"%LOCALAPPDATA%\Programs\WhatsApp\WhatsApp.exe",
        ],
    },
    "telegram": {
        "label": "Telegram", "noms": ["Telegram.exe"],
        "hints": [
            r"%APPDATA%\Telegram Desktop\Telegram.exe",
            r"%LOCALAPPDATA%\Telegram Desktop\Telegram.exe",
        ],
    },
    "zoom": {
        "label": "Zoom", "noms": ["Zoom.exe"],
        "hints": [
            r"%APPDATA%\Zoom\bin\Zoom.exe",
            r"%PROGRAMFILES%\Zoom\bin\Zoom.exe",
            r"%PROGRAMFILES(X86)%\Zoom\bin\Zoom.exe",
        ],
    },
    "skype": {
        "label": "Skype", "noms": ["Skype.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\Skype.exe",
            r"%PROGRAMFILES(X86)%\Microsoft\Skype for Desktop\Skype.exe",
        ],
    },
    # ── Bureautique / Office ─────────────────────────────────
    "word": {
        "label": "Microsoft Word", "noms": ["WINWORD.EXE", "winword.exe"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\WINWORD.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\WINWORD.EXE",
            r"%PROGRAMFILES%\Microsoft Office\Office16\WINWORD.EXE",
        ],
    },
    "excel": {
        "label": "Microsoft Excel", "noms": ["EXCEL.EXE", "excel.exe"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\EXCEL.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\EXCEL.EXE",
            r"%PROGRAMFILES%\Microsoft Office\Office16\EXCEL.EXE",
        ],
    },
    "powerpoint": {
        "label": "Microsoft PowerPoint", "noms": ["POWERPNT.EXE", "powerpnt.exe"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\POWERPNT.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\POWERPNT.EXE",
        ],
    },
    "outlook": {
        "label": "Outlook", "noms": ["OUTLOOK.EXE", "outlook.exe", "olk.exe"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\OUTLOOK.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\OUTLOOK.EXE",
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\olk.exe",
        ],
    },
    "onenote": {
        "label": "OneNote", "noms": ["ONENOTE.EXE", "onenote.exe"],
        "hints": [
            r"%PROGRAMFILES%\Microsoft Office\root\Office16\ONENOTE.EXE",
            r"%PROGRAMFILES(X86)%\Microsoft Office\root\Office16\ONENOTE.EXE",
        ],
    },
    # ── Créatif / Design ─────────────────────────────────────
    "photoshop": {
        "label": "Photoshop", "noms": ["Photoshop.exe"],
        "hints": [
            r"%PROGRAMFILES%\Adobe\Adobe Photoshop 2024\Photoshop.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Photoshop 2025\Photoshop.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Photoshop CC 2023\Photoshop.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Photoshop 2023\Photoshop.exe",
        ],
    },
    "premiere": {
        "label": "Premiere Pro", "noms": ["Adobe Premiere Pro.exe"],
        "hints": [
            r"%PROGRAMFILES%\Adobe\Adobe Premiere Pro 2024\Adobe Premiere Pro.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Premiere Pro CC 2023\Adobe Premiere Pro.exe",
        ],
    },
    "after effects": {
        "label": "After Effects", "noms": ["AfterFX.exe"],
        "hints": [
            r"%PROGRAMFILES%\Adobe\Adobe After Effects 2024\Support Files\AfterFX.exe",
            r"%PROGRAMFILES%\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe",
            r"%PROGRAMFILES%\Adobe\Adobe After Effects 2023\Support Files\AfterFX.exe",
        ],
    },
    "illustrator": {
        "label": "Illustrator", "noms": ["Illustrator.exe"],
        "hints": [
            r"%PROGRAMFILES%\Adobe\Adobe Illustrator 2024\Support Files\Contents\Windows\Illustrator.exe",
            r"%PROGRAMFILES%\Adobe\Adobe Illustrator 2025\Support Files\Contents\Windows\Illustrator.exe",
        ],
    },
    "capcut": {
        "label": "CapCut", "noms": ["CapCut.exe"],
        "hints": [
            r"%LOCALAPPDATA%\CapCut\Apps\CapCut.exe",
            r"%PROGRAMFILES%\CapCut\CapCut.exe",
        ],
    },
    "obs": {
        "label": "OBS Studio", "noms": ["obs64.exe", "obs32.exe"],
        "hints": [
            r"%PROGRAMFILES%\obs-studio\bin\64bit\obs64.exe",
            r"%PROGRAMFILES(X86)%\obs-studio\bin\64bit\obs64.exe",
        ],
    },
    "blender": {
        "label": "Blender", "noms": ["blender.exe"],
        "hints": [
            r"%PROGRAMFILES%\Blender Foundation\Blender 4.0\blender.exe",
            r"%PROGRAMFILES%\Blender Foundation\Blender 3.6\blender.exe",
            r"%PROGRAMFILES%\Blender Foundation\Blender\blender.exe",
        ],
    },
    "gimp": {
        "label": "GIMP", "noms": ["gimp-2.10.exe", "gimp.exe"],
        "hints": [
            r"%PROGRAMFILES%\GIMP 2\bin\gimp-2.10.exe",
            r"%PROGRAMFILES(X86)%\GIMP 2\bin\gimp-2.10.exe",
        ],
    },
    # ── Développement ────────────────────────────────────────
    "vscode": {
        "label": "Visual Studio Code", "noms": ["Code.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe",
            r"%PROGRAMFILES%\Microsoft VS Code\Code.exe",
        ],
    },
    "claude": {
        "label": "Claude", "noms": ["claude.exe", "Claude.exe"],
        "hints": [
            r"%LOCALAPPDATA%\AnthropicClaude\claude.exe",
            r"%PROGRAMFILES%\AnthropicClaude\claude.exe",
            r"%APPDATA%\AnthropicClaude\claude.exe",
        ],
    },
    "terminal": {
        "label": "Terminal", "noms": ["wt.exe", "WindowsTerminal.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe",
        ],
    },
    # ── Multimédia ───────────────────────────────────────────
    "vlc": {
        "label": "VLC", "noms": ["vlc.exe"],
        "hints": [
            r"%PROGRAMFILES%\VideoLAN\VLC\vlc.exe",
            r"%PROGRAMFILES(X86)%\VideoLAN\VLC\vlc.exe",
        ],
    },
    "spotify": {
        "label": "Spotify", "noms": ["Spotify.exe"],
        "hints": [
            r"%APPDATA%\Spotify\Spotify.exe",
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe",
        ],
    },
    # ── Utilitaires ──────────────────────────────────────────
    "filezilla": {
        "label": "FileZilla", "noms": ["filezilla.exe"],
        "hints": [
            r"%PROGRAMFILES%\FileZilla FTP Client\filezilla.exe",
            r"%PROGRAMFILES(X86)%\FileZilla FTP Client\filezilla.exe",
        ],
    },
    "winrar": {
        "label": "WinRAR", "noms": ["WinRAR.exe"],
        "hints": [
            r"%PROGRAMFILES%\WinRAR\WinRAR.exe",
            r"%PROGRAMFILES(X86)%\WinRAR\WinRAR.exe",
        ],
    },
    "7zip": {
        "label": "7-Zip", "noms": ["7zFM.exe"],
        "hints": [
            r"%PROGRAMFILES%\7-Zip\7zFM.exe",
            r"%PROGRAMFILES(X86)%\7-Zip\7zFM.exe",
        ],
    },
    "antigravity": {
        "label": "Antigravity", "noms": ["Antigravity.exe", "antigravity.exe"],
        "hints": [
            r"%LOCALAPPDATA%\Antigravity\Antigravity.exe",
            r"%PROGRAMFILES%\Antigravity\Antigravity.exe",
            r"%PROGRAMFILES(X86)%\Antigravity\Antigravity.exe",
            r"%APPDATA%\Antigravity\Antigravity.exe",
            r"%LOCALAPPDATA%\Programs\Antigravity\Antigravity.exe",
        ],
    },
}
# Alias — plusieurs façons de nommer la même app
_APPS_CATALOGUE["ea app"]          = _APPS_CATALOGUE["ea"]
_APPS_CATALOGUE["microsoft edge"]  = _APPS_CATALOGUE["edge"]
_APPS_CATALOGUE["opera gx"]        = _APPS_CATALOGUE["opera"]
_APPS_CATALOGUE["google chrome"]   = _APPS_CATALOGUE["chrome"]
_APPS_CATALOGUE["epic games"]      = _APPS_CATALOGUE["epic"]
_APPS_CATALOGUE["epic game"]       = _APPS_CATALOGUE["epic"]
_APPS_CATALOGUE["ubisoft connect"] = _APPS_CATALOGUE["ubisoft"]
_APPS_CATALOGUE["uplay"]          = _APPS_CATALOGUE["ubisoft"]
_APPS_CATALOGUE["gog galaxy"]     = _APPS_CATALOGUE["gog"]
_APPS_CATALOGUE["visual studio code"] = _APPS_CATALOGUE["vscode"]
_APPS_CATALOGUE["vs code"]        = _APPS_CATALOGUE["vscode"]
_APPS_CATALOGUE["code"]           = _APPS_CATALOGUE["vscode"]
_APPS_CATALOGUE["premiere pro"]   = _APPS_CATALOGUE["premiere"]
_APPS_CATALOGUE["adobe premiere"] = _APPS_CATALOGUE["premiere"]
_APPS_CATALOGUE["adobe photoshop"]= _APPS_CATALOGUE["photoshop"]
_APPS_CATALOGUE["adobe after effects"] = _APPS_CATALOGUE["after effects"]
_APPS_CATALOGUE["adobe illustrator"] = _APPS_CATALOGUE["illustrator"]
_APPS_CATALOGUE["microsoft word"] = _APPS_CATALOGUE["word"]
_APPS_CATALOGUE["microsoft excel"]= _APPS_CATALOGUE["excel"]
_APPS_CATALOGUE["microsoft powerpoint"] = _APPS_CATALOGUE["powerpoint"]
_APPS_CATALOGUE["powerpoint"]     = _APPS_CATALOGUE["powerpoint"]
_APPS_CATALOGUE["ppt"]            = _APPS_CATALOGUE["powerpoint"]
_APPS_CATALOGUE["microsoft outlook"] = _APPS_CATALOGUE["outlook"]
_APPS_CATALOGUE["microsoft teams"]= _APPS_CATALOGUE["teams"]
_APPS_CATALOGUE["obs studio"]     = _APPS_CATALOGUE["obs"]
_APPS_CATALOGUE["sept zip"]       = _APPS_CATALOGUE["7zip"]
_APPS_CATALOGUE["7 zip"]          = _APPS_CATALOGUE["7zip"]


async def mode_boulot():
    """Lance Deezer et Discord pour démarrer la session de travail."""
    parler("Bien, je prépare votre espace de travail.")

    # ── 1. Deezer (musique de fond) ───────────────────────────
    subprocess.Popen(["explorer", "deezer:"], shell=False)
    await asyncio.sleep(0.5)

    # ── 2. Discord ────────────────────────────────────────────
    discord_lnk = r"C:\Users\mylan\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Discord Inc\Discord.lnk"
    subprocess.Popen(["explorer", discord_lnk], shell=False)
    await asyncio.sleep(0.3)

    return f"Mode boulot activé{nom_virgule()} ! Deezer et Discord sont lancés. Bonne journée !"


async def mode_gaming():
    """Lance Deezer, Discord et Epic Games Launcher pour la session gaming."""
    parler(f"C'est parti{nom_espace()}, j'active le mode gaming !")

    # ── 1. Deezer (musique) ───────────────────────────────────
    subprocess.Popen(["explorer", "deezer:"], shell=False)
    await asyncio.sleep(0.5)

    # ── 2. Discord ────────────────────────────────────────────
    discord_lnk = r"C:\Users\mylan\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Discord Inc\Discord.lnk"
    subprocess.Popen(["explorer", discord_lnk], shell=False)
    await asyncio.sleep(0.5)

    # ── 3. Epic Games Launcher ────────────────────────────────
    _boulot_lancer(
        "Epic Games", ["EpicGamesLauncher.exe"],
        chemins_hints=[
            r"%PROGRAMFILES(X86)%\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe",
            r"%PROGRAMFILES%\Epic Games\Launcher\Portal\Binaries\Win64\EpicGamesLauncher.exe",
        ]
    )
    await asyncio.sleep(0.3)

    return f"Mode gaming activé{nom_virgule()} ! Deezer, Discord et Epic Games sont lancés. Bonne session !"


async def mode_rocket_league():
    """Lance Deezer, Discord, Rocket League et JoyToKey."""
    parler(f"C'est parti{nom_espace()} ! Préparation de la session Rocket League.")

    # ── 1. Deezer ─────────────────────────────────────────────
    subprocess.Popen(["explorer", "deezer:"], shell=False)
    await asyncio.sleep(0.5)

    # ── 2. Discord ────────────────────────────────────────────
    discord_lnk = r"C:\Users\mylan\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Discord Inc\Discord.lnk"
    subprocess.Popen(["explorer", discord_lnk], shell=False)
    await asyncio.sleep(0.5)

    # ── 3. JoyToKey ───────────────────────────────────────────
    joy_lnk = r"C:\Users\mylan\AppData\Roaming\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar\JoyToKey.lnk"
    subprocess.Popen(["explorer", joy_lnk], shell=False)
    await asyncio.sleep(0.5)

    # ── 4. Rocket League (Epic Games) ─────────────────────────
    # URI pour lancer Rocket League directement sur Epic
    rl_uri = "com.epicgames.launcher://apps/Sugar?action=launch&silent=true"
    subprocess.Popen(["explorer", rl_uri], shell=False)

    return f"Mode Rocket League activé{nom_virgule()} ! Deezer, Discord, JoyToKey et le jeu sont lancés. Bonne chance sur le terrain !"
