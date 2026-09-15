@echo off
SETLOCAL EnableDelayedExpansion
cd /d "%~dp0\.."

:: ======================================================
::  J.A.R.V.I.S - Installation des dependances
::  Appele par l'installateur Inno Setup
:: ======================================================

set "ERRORS=0"
set "WARNINGS=0"

:: ======================================================
:: [1/6] Detection de Python
:: ======================================================
echo [1/6] Detection de Python...

set "PYTHON_CMD="
python --version >nul 2>&1 && set "PYTHON_CMD=python"
if not defined PYTHON_CMD (
    py --version >nul 2>&1 && set "PYTHON_CMD=py"
)

if not defined PYTHON_CMD (
    echo [ERREUR] Python introuvable. Impossible de continuer.
    echo [ERREUR] Installez Python 3.12 depuis https://python.org
    set /a ERRORS+=1
    goto bilan
)

echo [OK] Python detecte :
%PYTHON_CMD% --version

:: ======================================================
:: [2/6] Creation de l'environnement virtuel
:: ======================================================
echo [2/6] Creation de l'environnement virtuel...

if not exist "venv" (
    "%PYTHON_CMD%" -m venv venv
    if !errorlevel! neq 0 (
        echo [ERREUR] Impossible de creer le venv.
        set /a ERRORS+=1
        goto bilan
    )
    echo [OK] Environnement virtuel cree.
) else (
    echo [OK] Environnement virtuel deja present.
)

set "V_PY=.\venv\Scripts\python.exe"

:: ======================================================
:: [3/6] Mise a jour pip, setuptools, wheel
:: ======================================================
echo [3/6] Mise a jour de pip, setuptools et wheel...
"%V_PY%" -m pip install --upgrade pip setuptools wheel --quiet
if !errorlevel! neq 0 (
    echo [AVERTISSEMENT] Mise a jour pip partielle.
    set /a WARNINGS+=1
)
echo [OK] Outils d'installation a jour.

:: ======================================================
:: [4/6] Installation des modules IA et Google APIs
:: ======================================================
echo [4/6] Installation des modules IA et Google APIs...
"%V_PY%" -m pip install --quiet python-dotenv google-genai google-generativeai groq openai flask flask-cors requests websockets colorama tenacity google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client anthropic mistralai httpx aiohttp pydantic psutil
if !errorlevel! neq 0 (
    echo [AVERTISSEMENT] Certains modules IA n'ont pas pu etre installes.
    set /a WARNINGS+=1
) else (
    echo [OK] Modules IA installes.
)

:: ======================================================
:: [5/6] Installation Audio et Vision (wheels pre-compiles)
:: ======================================================
echo [5/6] Installation des modules Audio et Vision...

:: --- Modules sans compilation ---
"%V_PY%" -m pip install --quiet SpeechRecognition edge-tts pyttsx3 pyautogui Pillow screeninfo pyperclip tabulate tqdm numpy comtypes opencv-python pycaw screen-brightness-control
if !errorlevel! neq 0 (
    echo [AVERTISSEMENT] Certains modules audio/vision n'ont pas pu etre installes.
    set /a WARNINGS+=1
)

:: --- Pygame : FORCER le wheel pre-compile (pas de compilation C++) ---
echo [SYSTEME] Installation de Pygame (wheel pre-compile, pas de compilation)...
"%V_PY%" -m pip install pygame --only-binary :all: --quiet
if !errorlevel! neq 0 (
    echo [SYSTEME] Tentative avec version flexible...
    "%V_PY%" -m pip install "pygame>=2.5.0" --only-binary :all: --quiet
    if !errorlevel! neq 0 (
        echo [AVERTISSEMENT] Pygame non installe - audio TTS desactive.
        set /a WARNINGS+=1
    ) else (
        echo [OK] Pygame installe.
    )
) else (
    echo [OK] Pygame installe.
)

:: --- PyAudio : wheel pre-compile, fallback pipwin ---
echo [SYSTEME] Installation de PyAudio (wheel pre-compile)...
"%V_PY%" -m pip install pyaudio --only-binary :all: --quiet
if !errorlevel! neq 0 (
    echo [SYSTEME] Tentative via pipwin...
    "%V_PY%" -m pip install pipwin --quiet 2>nul
    "%V_PY%" -m pipwin install pyaudio 2>nul
    if !errorlevel! neq 0 (
        echo [AVERTISSEMENT] PyAudio non installe - micro desactive.
        set /a WARNINGS+=1
    ) else (
        echo [OK] PyAudio installe via pipwin.
    )
) else (
    echo [OK] PyAudio installe.
)

:: --- PyWebView : fenetre native (remplace Chrome) ---
echo [SYSTEME] Installation de PyWebView (fenetre application native)...
"%V_PY%" -m pip install pywebview --quiet
if !errorlevel! neq 0 (
    echo [AVERTISSEMENT] PyWebView non installe - JARVIS s'ouvrira dans Chrome.
    set /a WARNINGS+=1
) else (
    echo [OK] PyWebView installe.
)

:: --- Edge WebView2 Runtime (moteur requis par PyWebView sur Windows) ---
echo [SYSTEME] Verification de Edge WebView2 Runtime...
set "WEBVIEW2_OK=0"

:: Verifier via le registre (x64)
reg query "HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" >nul 2>&1
if !errorlevel! equ 0 set "WEBVIEW2_OK=1"

:: Verifier via le registre (x86)
if "!WEBVIEW2_OK!"=="0" (
    reg query "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" >nul 2>&1
    if !errorlevel! equ 0 set "WEBVIEW2_OK=1"
)

:: Verifier via le dossier d'installation (fallback)
if "!WEBVIEW2_OK!"=="0" (
    if exist "%ProgramFiles(x86)%\Microsoft\EdgeWebView\Application" set "WEBVIEW2_OK=1"
)
if "!WEBVIEW2_OK!"=="0" (
    if exist "%ProgramFiles%\Microsoft\EdgeWebView\Application" set "WEBVIEW2_OK=1"
)

if "!WEBVIEW2_OK!"=="1" (
    echo [OK] Edge WebView2 Runtime deja installe.
) else (
    echo [SYSTEME] Edge WebView2 absent - telechargement en cours...
    powershell -Command "try { Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile 'MicrosoftEdgeWebview2Setup.exe' -UseBasicParsing } catch { exit 1 }"
    if exist "MicrosoftEdgeWebview2Setup.exe" (
        echo [SYSTEME] Installation de Edge WebView2 Runtime (silencieux)...
        start /wait MicrosoftEdgeWebview2Setup.exe /silent /install
        del MicrosoftEdgeWebview2Setup.exe 2>nul
        echo [OK] Edge WebView2 Runtime installe.
    )
)

:: ======================================================
:: [6/6] Generation du fichier de lancement
:: ======================================================
echo [6/6] Generation du fichier de lancement 'start.bat'...
(
echo @echo off
echo TITLE J.A.R.V.I.S
echo COLOR 0B
echo cd /d "%%~dp0"
echo ".\venv\Scripts\python.exe" "main.py"
echo pause
) > "start.bat"

:: Hook pre-commit (verification py_compile + tsc avant chaque commit)
if exist "tools\git-hooks\pre-commit" if exist ".git" (
    copy /Y "tools\git-hooks\pre-commit" ".git\hooks\pre-commit" >nul
)

:bilan
echo.
echo ======================================================
echo           INSTALLATION TERMINEE !
echo ======================================================
echo [INFO] Erreurs : %ERRORS%
echo [INFO] Alertes : %WARNINGS%
echo.
exit /b %ERRORS%