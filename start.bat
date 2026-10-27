@echo off
rem OligoLab starten - Windows.
rem
rem Doppelklick genuegt. Das Skript prueft, was fehlt, installiert nach,
rem baut die Oberflaeche, startet das Backend und oeffnet den Browser.
rem
rem     start.bat              normal starten
rem     start.bat --no-browser ohne Browser
rem     start.bat --port 8080  auf einem anderen Port
rem
rem Alles laeuft lokal. Es wird nichts ins Netz geschickt.

setlocal enabledelayedexpansion
cd /d "%~dp0"

set PORT=8000
set BROWSER=1
:argumente
if "%~1"=="" goto argumente_fertig
if /i "%~1"=="--no-browser" set BROWSER=0
if /i "%~1"=="--port" (set PORT=%~2& shift)
shift
goto argumente
:argumente_fertig

rem ------------------------------------------------------------- Python
set PY=
for %%K in (py python) do (
  if not defined PY (
    %%K -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3,12) else 1)" >nul 2>&1
    if !errorlevel! equ 0 set PY=%%K
  )
)
if not defined PY (
  echo.
  echo   Python 3.12 oder neuer wird gebraucht und ist nicht da.
  echo   Herunterladen von https://www.python.org/downloads/
  echo   Beim Installieren "Add Python to PATH" ankreuzen.
  echo.
  pause
  exit /b 1
)

rem --------------------------------------------------- Virtuelle Umgebung
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo   Richte die Python-Umgebung ein - das dauert beim ersten Mal einige Minuten.
  %PY% -m venv .venv
  if errorlevel 1 (
    echo   Die Umgebung liess sich nicht anlegen.
    pause
    exit /b 1
  )
)

if not exist ".venv\.requirements-stempel" (
  echo.
  echo   Installiere die Python-Pakete.
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
  if errorlevel 1 (
    echo.
    echo   Die Pakete liessen sich nicht installieren. Ohne Netz geht das nicht.
    pause
    exit /b 1
  )
  echo fertig> ".venv\.requirements-stempel"
)

rem --------------------------------------------------------- Oberflaeche
if not exist "frontend\dist\index.html" (
  where npm >nul 2>&1
  if errorlevel 1 (
    echo.
    echo   Fuer die Oberflaeche wird Node.js gebraucht ^(npm fehlt^).
    echo   Herunterladen von https://nodejs.org - die LTS-Fassung genuegt.
    echo.
    echo   Ohne Oberflaeche laeuft nur die Schnittstelle unter /docs.
    pause
    exit /b 1
  )
  if not exist "frontend\node_modules" (
    echo   Installiere die Pakete der Oberflaeche.
    pushd frontend
    call npm install --silent
    popd
  )
  echo   Baue die Oberflaeche.
  pushd frontend
  call npm run build
  popd
)

rem ------------------------------------------------------------- Starten
echo.
echo   OligoLab laeuft auf http://127.0.0.1:%PORT% - zum Beenden dieses Fenster schliessen.
echo.
if "%BROWSER%"=="1" start "" "http://127.0.0.1:%PORT%"
".venv\Scripts\python.exe" -m uvicorn app.main:app --port %PORT%

endlocal
