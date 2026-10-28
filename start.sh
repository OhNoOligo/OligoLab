#!/usr/bin/env bash
# OligoLab starten — Linux und macOS.
#
# Ein Aufruf, der alles tut: prüfen, was fehlt, nachinstallieren, die
# Oberfläche bauen, das Backend starten und den Browser öffnen.
#
#     ./start.sh              normal starten
#     ./start.sh --dev        mit Neuladen bei Codeänderungen
#     ./start.sh --no-browser ohne Browser
#     ./start.sh --port 8080  auf einem anderen Port
#
# Alles läuft lokal. Es wird nichts ins Netz geschickt und kein Schlüssel
# gebraucht.

set -euo pipefail
cd "$(dirname "$0")"

PORT=8000
DEV=0
BROWSER=1
for arg in "$@"; do
  case "$arg" in
    --dev) DEV=1 ;;
    --no-browser) BROWSER=0 ;;
    --port) ;;                      # Wert kommt im nächsten Durchlauf
    --port=*) PORT="${arg#*=}" ;;
    [0-9]*) PORT="$arg" ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "Unbekannte Angabe: $arg"; exit 2 ;;
  esac
done

sagen() { printf '\n\033[1m%s\033[0m\n' "$1"; }
fehlt() { printf '\n\033[31m%s\033[0m\n' "$1" >&2; }

# ---------------------------------------------------------------- Python
PY=""
for kandidat in python3.13 python3.12 python3; do
  if command -v "$kandidat" >/dev/null 2>&1; then
    version=$("$kandidat" -c 'import sys; print(sys.version_info[0]*100+sys.version_info[1])')
    if [ "$version" -ge 312 ]; then PY="$kandidat"; break; fi
  fi
done
if [ -z "$PY" ]; then
  fehlt "Python 3.12 oder neuer wird gebraucht und ist nicht da."
  echo "  Linux:  sudo apt install python3 python3-venv   (oder die Paketverwaltung der Distribution)"
  echo "  macOS:  brew install python@3.12"
  exit 1
fi

# ------------------------------------------------------- Virtuelle Umgebung
if [ ! -x .venv/bin/python ]; then
  sagen "Richte die Python-Umgebung ein."
  "$PY" -m venv .venv
fi

# Die Abhängigkeiten nur nachziehen, wenn sich die Liste geändert hat.
STEMPEL=".venv/.requirements-stempel"
if [ ! -f "$STEMPEL" ] || [ requirements.txt -nt "$STEMPEL" ]; then
  sagen "Installiere die Python-Pakete."
  # Bewusst NICHT --quiet: hier werden einige hundert Megabyte geladen
  # (RDKit, ViennaRNA, Biopython). Ohne Ausgabe sieht das minutenlang wie
  # ein Absturz aus, und man bricht ab, obwohl alles läuft.
  echo "Das sind rund 500 MB — je nach Leitung 2 bis 15 Minuten."
  echo "Solange Zeilen erscheinen, läuft es. Nicht abbrechen."
  echo
  .venv/bin/pip install --upgrade pip
  if ! .venv/bin/pip install -r requirements.txt; then
    fehlt "Die Pakete ließen sich nicht installieren."
    echo "  Ohne Netz geht das nicht. Mit Netz noch einmal versuchen:"
    echo "      .venv/bin/pip install -r requirements.txt"
    exit 1
  fi
  touch "$STEMPEL"
fi

# ------------------------------------------------------------- Oberfläche
if [ ! -f frontend/dist/index.html ] || [ "$DEV" = "1" ]; then
  if ! command -v npm >/dev/null 2>&1; then
    if [ "$DEV" = "1" ]; then
      fehlt "Der Entwicklungsbetrieb braucht Node.js (npm fehlt)."
      echo "  Ohne --dev läuft OligoLab mit der mitgelieferten Oberfläche."
    else
      fehlt "Die gebaute Oberfläche fehlt, und Node.js ist nicht da."
      echo
      echo "  Normalerweise liegt sie unter frontend/dist/ bei und muss nicht"
      echo "  gebaut werden. Fehlt sie, hilft eines von beiden:"
      echo
      echo "  * OligoLab noch einmal herunterladen — dann ist sie dabei."
      echo "  * Node.js installieren und das Skript erneut starten:"
      echo "      https://nodejs.org   (die LTS-Fassung genügt)"
      echo "      Linux:  sudo apt install nodejs npm"
      echo "      macOS:  brew install node"
      echo
      echo "  Auch ohne Oberfläche läuft die Schnittstelle unter /docs."
    fi
    exit 1
  fi
  if [ ! -d frontend/node_modules ]; then
    sagen "Installiere die Pakete der Oberfläche — noch einmal ein bis zwei Minuten."
    (cd frontend && npm install)
  fi
  if [ "$DEV" = "0" ]; then
    sagen "Baue die Oberfläche — eine halbe Minute."
    (cd frontend && npm run build)
  fi
fi

# ----------------------------------------------------------------- Starten
ADRESSE="http://127.0.0.1:$PORT"

if [ "$BROWSER" = "1" ]; then
  # Erst öffnen, wenn der Dienst wirklich antwortet.
  (
    for _ in $(seq 1 60); do
      if curl -fsS "$ADRESSE/api/health" >/dev/null 2>&1; then
        if command -v xdg-open >/dev/null 2>&1; then xdg-open "$ADRESSE" >/dev/null 2>&1
        elif command -v open >/dev/null 2>&1; then open "$ADRESSE"
        fi
        break
      fi
      sleep 0.5
    done
  ) &
fi

sagen "OligoLab läuft auf $ADRESSE — zum Beenden Strg+C."
if [ "$DEV" = "1" ]; then
  echo "Entwicklungsbetrieb: die Oberfläche startet gleich zusätzlich auf Port 5173."
  (cd frontend && npm run dev) &
  trap 'kill 0' EXIT
  exec .venv/bin/uvicorn app.main:app --reload --port "$PORT"
else
  exec .venv/bin/uvicorn app.main:app --port "$PORT"
fi
