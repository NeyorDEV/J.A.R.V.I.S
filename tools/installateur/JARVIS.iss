; Installateur J.A.R.V.I.S (Inno Setup 6) — compilation : construire.bat
; Le programme s'installe pour l'utilisateur courant (aucun droit administrateur), puis l'installateur
; crée l'environnement Python (venv) et installe les dépendances. Le raccourci lance pythonw.exe :
; aucune console, seulement l'interface de JARVIS.
#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
AppId={{5B1E5A0C-7C1B-4C0B-9A6E-2F3A1D7E9B41}
AppName=J.A.R.V.I.S
AppVersion={#Version}
AppPublisher=NeyorDEV
AppPublisherURL=https://github.com/NeyorDEV/J.A.R.V.I.S
DefaultDirName={localappdata}\Programs\JARVIS
DefaultGroupName=J.A.R.V.I.S
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=build
OutputBaseFilename=JARVIS-Setup-{#Version}
SetupIconFile=..\..\assets\jarvis_icon.ico
UninstallDisplayIcon={app}\assets\jarvis_icon.ico
LicenseFile=..\..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "icone"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"

[Files]
Source: "build\stage\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\J.A.R.V.I.S"; Filename: "{app}\venv\Scripts\pythonw.exe"; Parameters: """{app}\main.py"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\jarvis_icon.ico"
Name: "{autodesktop}\J.A.R.V.I.S"; Filename: "{app}\venv\Scripts\pythonw.exe"; Parameters: """{app}\main.py"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\jarvis_icon.ico"; Tasks: icone

[Run]
; Installation de l'environnement Python et des dépendances (plusieurs minutes, connexion internet requise)
Filename: "{app}\tools\_setup\dependances.bat"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; StatusMsg: "Installation de Python et des dépendances (plusieurs minutes)..."
Filename: "{app}\venv\Scripts\pythonw.exe"; Parameters: """{app}\main.py"""; WorkingDir: "{app}"; Description: "Lancer J.A.R.V.I.S maintenant"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Le venv a été créé après l'installation : l'installateur ne le connaît pas. Les données de
; l'utilisateur (data\, .env, config\) sont volontairement conservées.
Type: filesandordirs; Name: "{app}\venv"
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
const
  PythonUrl = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe';

function Python312Present(): Boolean;
var
  Code: Integer;
begin
  Result := (Exec('cmd.exe', '/c py -3.12 --version', '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0))
    or FileExists(ExpandConstant('{localappdata}\Programs\Python\Python312\python.exe'));
end;

// Python 3.12 est exigé par les paquets épinglés (3.13 : plus d'audioop) : on l'installe s'il manque.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
  Fichier: String;
begin
  Result := '';
  if Python312Present() then Exit;
  Fichier := ExpandConstant('{tmp}\python-3.12.10-amd64.exe');
  WizardForm.StatusLabel.Caption := 'Téléchargement de Python 3.12...';
  if not Exec('powershell.exe', '-NoProfile -Command "try { Invoke-WebRequest -Uri ''' + PythonUrl + ''' -OutFile ''' + Fichier + ''' -UseBasicParsing } catch { exit 1 }"',
              '', SW_HIDE, ewWaitUntilTerminated, Code) or (Code <> 0) or not FileExists(Fichier) then
  begin
    Result := 'Python 3.12 est introuvable et n''a pas pu être téléchargé. Vérifiez la connexion internet, ou installez Python 3.12 depuis python.org puis relancez l''installation.';
    Exit;
  end;
  WizardForm.StatusLabel.Caption := 'Installation de Python 3.12...';
  Exec(Fichier, '/quiet InstallAllUsers=0 Include_launcher=1 PrependPath=0 Include_test=0', '', SW_HIDE, ewWaitUntilTerminated, Code);
  if not Python312Present() then
    Result := 'L''installation de Python 3.12 a échoué. Installez-le depuis python.org puis relancez l''installation.';
end;

// Fichier .env de départ (les clés se renseignent ensuite dans Paramètres, ou en éditant ce fichier)
procedure CurStepChanged(CurStep: TSetupStep);
var
  Env: String;
begin
  if CurStep = ssPostInstall then
  begin
    Env := ExpandConstant('{app}\.env');
    if not FileExists(Env) then
      SaveStringToFile(Env,
        'GEMINI_API_KEY=VOTRE_CLE_ICI' + #13#10 + 'GROQ_API_KEY=VOTRE_CLE_ICI' + #13#10 +
        'ANTHROPIC_API_KEY=VOTRE_CLE_ICI' + #13#10 + 'MISTRAL_API_KEY=VOTRE_CLE_ICI' + #13#10 +
        'OPENAI_API_KEY=VOTRE_CLE_ICI' + #13#10 + 'YOUTUBE_API_KEY=VOTRE_CLE_ICI' + #13#10 +
        'XAI_API_KEY=VOTRE_CLE_ICI' + #13#10 + 'SERPAPI_API_KEY=VOTRE_CLE_ICI' + #13#10, False);
  end;
end;
