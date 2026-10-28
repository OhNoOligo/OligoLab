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
rem
rem Nicht einfach "neu genug": auch zu NEU ist ein Problem. Fuer eine frisch
rem erschienene Python-Fassung gibt es noch keine fertigen Pakete von
rem ViennaRNA und PyYAML, und pip versucht dann, sie aus dem Quelltext zu
rem uebersetzen - was ohne Visual-C++-Compiler scheitert. Darum eine
rem gepruefte Spanne, und die neueste passende wird zuerst genommen.
set PY=
call :pruefe py -3.14
call :pruefe py -3.13
call :pruefe py -3.12
call :pruefe py
call :pruefe python
if defined PY goto python_da

echo.
echo   Keine brauchbare Python-Fassung gefunden.
echo.
rem Kein ">" in diesen Zeilen: cmd.exe liest es auch in Anfuehrungszeichen
rem innerhalb eines Klammerblocks als Umleitung. struct.calcsize tut dasselbe.
for %%K in (py python) do (
  %%K -c "import sys, struct; print('   Gefunden: Python', sys.version.split()[0], str(struct.calcsize('P') * 8) + '-Bit')" 2>nul
)
echo.
echo   Gebraucht wird Python 3.12, 3.13 oder 3.14 in 64 Bit.
echo.
echo   Neuer geht NICHT: fuer Python 3.15 gibt es ViennaRNA und PyYAML noch
echo   nicht fertig gebaut. pip versucht dann zu uebersetzen und scheitert
echo   mit "failed-wheel-build-for-install". 32 Bit geht auch nicht -
echo   ViennaRNA gibt es nur in 64 Bit.
echo.
echo   Herunterladen: https://www.python.org/downloads/release/python-3137/
echo   Die Datei heisst "Windows installer (64-bit)".
echo   Beim Installieren "Add Python to PATH" ankreuzen.
echo.
echo   Eine zu neue Fassung darf ruhig installiert bleiben - dieses Skript
echo   sucht sich die passende heraus.
echo.
pause
exit /b 1

:pruefe
rem Nimmt den ersten Kandidaten, der in der Spanne liegt UND 64 Bit ist.
if defined PY exit /b
%* -c "import sys, struct; sys.exit(0 if (3,12) <= sys.version_info[:2] <= (3,14) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
if errorlevel 1 exit /b
set PY=%*
exit /b

:python_da
for /f "delims=" %%V in ('%PY% -c "import sys; print(sys.version.split()[0])"') do set PYVER=%%V
echo.
echo   Python %PYVER% wird benutzt.

rem --------------------------------------------------- Virtuelle Umgebung
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo   Richte die Python-Umgebung ein.
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
  rem Bewusst NICHT --quiet: hier werden einige hundert Megabyte geladen
  rem (RDKit, ViennaRNA, Biopython). Ohne Ausgabe sieht das minutenlang wie
  rem ein Absturz aus, und man bricht ab, obwohl alles laeuft.
  echo   Das sind rund 500 MB - je nach Leitung 2 bis 15 Minuten.
  echo   Solange Zeilen erscheinen, laeuft es. Nicht abbrechen.
  echo.
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
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
    echo   Die gebaute Oberflaeche fehlt, und Node.js ist nicht da.
    echo.
    echo   Normalerweise liegt sie unter frontend\dist\ bei und muss nicht
    echo   gebaut werden. Fehlt sie, hilft eines von beiden:
    echo.
    echo     * OligoLab noch einmal herunterladen - dann ist sie dabei.
    echo     * Node.js installieren und start.bat erneut starten:
    echo         https://nodejs.org   ^(die LTS-Fassung genuegt^)
    echo.
    echo   Auch ohne Oberflaeche laeuft die Schnittstelle unter /docs.
    echo.
    pause
    exit /b 1
  )
  if not exist "frontend\node_modules" (
    echo   Installiere die Pakete der Oberflaeche - noch einmal ein bis zwei Minuten.
    pushd frontend
    call npm install
    popd
  )
  echo   Baue die Oberflaeche - eine halbe Minute.
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
