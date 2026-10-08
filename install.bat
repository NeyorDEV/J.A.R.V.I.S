@echo off
SETLOCAL EnableDelayedExpansion
TITLE J.A.R.V.I.S - Installation
COLOR 0A
cd /d "%~dp0"

echo J.A.R.V.I.S
echo Installation locale
echo.

:: 1. Vérification des droits Administrateur
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Ce script n'est pas lance en tant qu'administrateur.
    echo Pour eviter d'eventuelles erreurs de droits :
    echo   clic droit sur install.bat, puis "Executer en tant qu'administrateur".
    echo.
    pause
    exit /b
)

:: 1b. Analyse du système (Détection dynamique)
set "PY_STATUS=a installer"
set "NODE_STATUS=a installer"
set "VENV_STATUS=a creer"
set "WEB_STATUS=a installer"
set "ROOT_STATUS=NON"
set "CHROME_STATUS=NON"

:: Vérification Racine (présence de main.py dans le même dossier que le script)
if exist "%~dp0main.py" (
    set "ROOT_STATUS=OUI"
) else (
    set "ROOT_STATUS=NON"
)

:: Vérification Chrome (Registre et Chemins)
reg query "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" >nul 2>&1 && set "CHROME_STATUS=OUI"
reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" >nul 2>&1 && set "CHROME_STATUS=OUI"
if "!CHROME_STATUS!"=="NON" (
    if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set "CHROME_STATUS=OUI"
    if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" set "CHROME_STATUS=OUI"
    if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME_STATUS=OUI"
)


:: Détection versions
py -3.12 --version >nul 2>&1 && set "PY_STATUS=deja present"
python -c "import sys; sys.exit(0 if sys.version_info[:2]==(3,12) else 1)" >nul 2>&1 && set "PY_STATUS=deja present"
where npm >nul 2>&1 && set "NODE_STATUS=deja present"
if exist "venv" set "VENV_STATUS=deja present"
if exist "interfaces\frontend\node_modules" set "WEB_STATUS=deja present"

:: 1c. Récapitulatif et Validation
if "!ROOT_STATUS!"=="NON" (
    COLOR 0C
    echo emplacement incorrect
    echo.
    echo install.bat doit se trouver dans le dossier JARVIS, a cote de main.py.
    echo.
    echo   1. deplacez ce fichier dans ce dossier
    echo   2. relancez-le depuis la
    echo.
    pause
    exit /b
)

echo Python 3.12 ........... !PY_STATUS!
echo Node.js / npm ......... !NODE_STATUS!
echo Environnement virtuel . !VENV_STATUS!
echo Interface web ......... !WEB_STATUS!
echo Navigateur Chrome ..... !CHROME_STATUS!
echo.
if "!CHROME_STATUS!"=="NON" (
    echo Chrome est introuvable et JARVIS s'appuie dessus pour son interface.
    echo Installez-le avant de continuer si possible.
    echo.
)
echo Seuls les elements "a installer" seront traites ci-dessous.
echo Espace disque necessaire : environ 2 Go.
echo.
echo [ENTREE] pour continuer...
pause >nul
echo.

:: 2. Détection / Installation de Python
echo [1/7] Python
:: JARVIS demande Python 3.12 : avec 3.13 et plus, audioop (claquements de mains) n'existe
:: plus et certains paquets epingles ne s'installent pas. Le Python du PATH n'est donc
:: utilise que s'il est bien en 3.12.
set "PYTHON_CMD="
py -3.12 --version >nul 2>&1 && set "PYTHON_CMD=py -3.12"
if not defined PYTHON_CMD (
    python -c "import sys; sys.exit(0 if sys.version_info[:2]==(3,12) else 1)" >nul 2>&1 && set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo   telechargement de Python 3.12...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe' -OutFile 'python_installer.exe'"
    echo   lancement de l'installateur.
    echo   pensez a cocher "Add Python to PATH" a l'ecran suivant ^!
    start /wait python_installer.exe
    del python_installer.exe
    echo   relancez install.bat une fois Python installe.
    pause && exit /b
)
%PYTHON_CMD% --version

:: 3. Détection / Installation de Node.js
echo [2/7] Node.js
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo   telechargement...
    powershell -Command "Invoke-WebRequest -Uri 'https://nodejs.org/dist/v22.12.0/node-v22.12.0-x64.msi' -OutFile 'node_installer.msi'"
    echo   installation en cours...
    start /wait node_installer.msi
    del node_installer.msi
    echo   installe. Un redemarrage peut etre necessaire si npm reste introuvable.
) else (
    echo   deja installe.
)

:: 4. Création de l'environnement virtuel
echo [3/7] Environnement virtuel Python
if not exist "venv" (
    %PYTHON_CMD% -m venv venv
    if %errorlevel% neq 0 (
        echo   echec de la creation. Verifiez vos droits d'ecriture ici.
        pause && exit /b
    )
    echo   cree.
) else (
    echo   deja present.
)

set "V_PY=.\venv\Scripts\python.exe"

:: 5. Mise à jour des outils de base (EVITE LES ERREURS DE COMPILATION)
"%V_PY%" -m pip install --upgrade pip setuptools wheel --quiet
"%V_PY%" -m pip install --upgrade pipwin --quiet 2>nul

:: 6. Installation des modules
echo [4/7] Dependances Python
echo   IA (Gemini, Groq, Claude, Mistral, OpenAI, Google Auth)
"%V_PY%" -m pip install python-dotenv google-genai google-generativeai groq openai anthropic mistralai flask flask-cors requests websockets colorama tenacity google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client psutil
if %errorlevel% neq 0 (
    echo   echec partiel, verifiez votre connexion internet.
)

echo   audio, vision, interface native
:: SpeechRecognition installe en premier, seul, pour ne pas etre bloque par pyaudio
"%V_PY%" -m pip install SpeechRecognition edge-tts pyttsx3 pyautogui Pillow screeninfo opencv-python

:: --- PYWEBVIEW : fenetre native (remplace Chrome) ---
"%V_PY%" -m pip install pywebview
if !errorlevel! neq 0 (
    echo   PyWebView indisponible, JARVIS s'ouvrira dans Chrome a la place.
)

:: --- Edge WebView2 Runtime (moteur requis par PyWebView sur Windows) ---
set "WEBVIEW2_OK=0"

reg query "HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" >nul 2>&1
if !errorlevel! equ 0 set "WEBVIEW2_OK=1"

if "!WEBVIEW2_OK!"=="0" (
    reg query "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" >nul 2>&1
    if !errorlevel! equ 0 set "WEBVIEW2_OK=1"
)

if "!WEBVIEW2_OK!"=="0" (
    if exist "%ProgramFiles(x86)%\Microsoft\EdgeWebView\Application" set "WEBVIEW2_OK=1"
)
if "!WEBVIEW2_OK!"=="0" (
    if exist "%ProgramFiles%\Microsoft\EdgeWebView\Application" set "WEBVIEW2_OK=1"
)

if "!WEBVIEW2_OK!"=="0" (
    echo   Edge WebView2 absent, telechargement...
    powershell -Command "try { Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile 'MicrosoftEdgeWebview2Setup.exe' -UseBasicParsing } catch { exit 1 }"
    if exist "MicrosoftEdgeWebview2Setup.exe" (
        start /wait MicrosoftEdgeWebview2Setup.exe /silent /install
        del MicrosoftEdgeWebview2Setup.exe 2>nul
        echo   Edge WebView2 installe.
    ) else (
        echo   telechargement impossible, JARVIS utilisera Chrome si besoin.
    )
)

:: --- PYGAME : installation avec wheel pre-compile (PAS de compilation C++) ---
"%V_PY%" -m pip install pygame --only-binary :all:
if !errorlevel! neq 0 (
    "%V_PY%" -m pip install pygame>=2.5.0 --only-binary :all:
    if !errorlevel! neq 0 (
        echo   Pygame indisponible, JARVIS fonctionnera sans sortie audio.
    )
)

:: --- PYAUDIO : installation avec wheel pre-compile, fallback pipwin ---
"%V_PY%" -m pip install pyaudio --only-binary :all:
if !errorlevel! neq 0 (
    "%V_PY%" -m pipwin install pyaudio 2>nul
    if !errorlevel! neq 0 (
        echo   PyAudio indisponible, le micro sera limite.
        echo   installation manuelle possible : pip install pipwin ^&^& pipwin install pyaudio
    )
)

:: --- Controle volume + luminosite (fonctions locales JARVIS) ---
"%V_PY%" -m pip install pycaw screen-brightness-control 2>nul

echo   finalisation (requirements.txt)
if exist "requirements.txt" (
    "%V_PY%" -m pip install -r requirements.txt
)

:: 7. Interface Web
echo [5/7] Interface web
where npm >nul 2>&1
if %errorlevel% equ 0 (
    if exist "interfaces\frontend\package.json" (
        pushd interfaces\frontend && call npm install & popd
    )
) else (
    echo   npm introuvable, etape ignoree.
)

:: 8. Creation du demarreur
echo [6/7] Fichiers de configuration
echo   start.bat
(
echo @echo off
echo TITLE J.A.R.V.I.S
echo COLOR 0B
echo cd /d "%%~dp0"
echo ".\venv\Scripts\python.exe" "main.py"
echo pause
) > "start.bat"

:: 8b. Hook pre-commit (verification py_compile + tsc avant chaque commit)
if exist "tools\git-hooks\pre-commit" if exist ".git" (
    echo   hook pre-commit
    copy /Y "tools\git-hooks\pre-commit" ".git\hooks\pre-commit" >nul
)

:: 9. Création du modèle .env si absent
if not exist ".env" (
    echo   .env
    (
    echo GEMINI_API_KEY=VOTRE_CLE_ICI
    echo GROQ_API_KEY=VOTRE_CLE_ICI
    echo ANTHROPIC_API_KEY=VOTRE_CLE_ICI
    echo MISTRAL_API_KEY=VOTRE_CLE_ICI
    echo OPENAI_API_KEY=VOTRE_CLE_ICI
    echo YOUTUBE_API_KEY=VOTRE_CLE_ICI
    echo XAI_API_KEY=VOTRE_CLE_ICI
    echo SERPAPI_API_KEY=VOTRE_CLE_ICI
    echo GITHUB_MCP_TOKEN=VOTRE_TOKEN_GITHUB_ICI
    echo HA_URL=http://192.168.1.XX:8123
    echo HA_TOKEN=VOTRE_TOKEN_ICI
    ) > ".env"
)

:: 10. Personnalisation du Prénom
echo [7/7] Personnalisation
echo   Prenom a utiliser (facultatif, modifiable plus tard dans les parametres) :
set "PN="
set /p "PN=  > "

:: ── Validation de l'input avec !PN! (EnableDelayedExpansion requis) ──────────

:: 1. Vide ou non renseigne -> rien a faire, configurable plus tard dans l'appli
if "!PN!"=="" goto skip_name

:: 2. Longueur max 30 caracteres (securite)
set "PN_TEST=!PN:~30!"
if not "!PN_TEST!"=="" (
    echo   trop long ^(30 caracteres max^), ignore.
    goto skip_name
)

:: 3. Refus des caracteres dangereux pour le batch et Python
::    On teste chaque caractere interdit en cherchant s'il est present dans !PN!
set "PN_INVALIDE=0"
for %%C in ("!" "%" "^" "&" "|" "<" ">" "(" ")" ";" "," "@" "#" "$" "`" "~" "\" "/" "*" "?" "{" "}" "[" "]") do (
    set "PN_CHK=!PN:%%~C=!"
    if not "!PN_CHK!"=="!PN!" set "PN_INVALIDE=1"
)
:: Tester le guillemet separement (ne peut pas etre dans la liste FOR)
set "PN_CHK2=!PN:"=!"
if not "!PN_CHK2!"=="!PN!" set "PN_INVALIDE=1"

if "!PN_INVALIDE!"=="1" (
    echo   caractere non autorise, ignore.
    goto skip_name
)

:: 4. Appliquer la personnalisation dans jarvis_config.json (lu au demarrage
::    par main.py — remplace l'ancien mecanisme de remplacement de texte dans
::    le code source, devenu obsolete depuis que le prenom vient de ce fichier).
echo import json, os > temp_config.py
echo n = "!PN!" >> temp_config.py
echo p = "jarvis_config.json" >> temp_config.py
echo cfg = {} >> temp_config.py
echo if os.path.exists(p^): >> temp_config.py
echo     try: >> temp_config.py
echo         with open(p, "r", encoding="utf-8"^) as f: cfg = json.load(f^) >> temp_config.py
echo     except Exception: cfg = {} >> temp_config.py
echo cfg["user_name"] = n >> temp_config.py
echo with open(p, "w", encoding="utf-8"^) as f: json.dump(cfg, f, ensure_ascii=False, indent=2^) >> temp_config.py

".\venv\Scripts\python.exe" temp_config.py
del temp_config.py

echo   enregistre : !PN!

:skip_name

echo.
echo Installation terminee.
echo.
echo   1. ouvrez .env et renseignez au moins une cle API (Gemini par exemple^)
echo   2. si des erreurs sont apparues, installez les "Build Tools C++"
echo   3. lancez start.bat pour demarrer JARVIS
echo.
pause
