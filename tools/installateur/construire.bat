@echo off
rem Construit JARVIS-Setup-<version>.exe dans tools\installateur\build\ (Inno Setup 6 requis).
cd /d "%~dp0\..\.."
"venv\Scripts\python.exe" tools\installateur\preparer.py %*
if errorlevel 1 exit /b 1
for /f "tokens=2 delims==" %%V in ('findstr /B "CURRENT_VERSION" backend\core\config.py') do set "VERSION=%%~V"
set "VERSION=%VERSION: =%"
set "ISCC="
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe") do if exist %%P set "ISCC=%%~P"
if not defined ISCC (
    echo Inno Setup 6 introuvable : installez-le ^(winget install JRSoftware.InnoSetup^) puis relancez.
    exit /b 1
)
"%ISCC%" /DVersion=%VERSION% tools\installateur\JARVIS.iss
