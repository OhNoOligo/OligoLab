# OligoLab — Projektregeln

Lokales Programm zum **Rechnen und Visualisieren** für modifizierte DNAzyme
(10-23), gebaut für die Festphasensynthese mit Basenmodifikationen,
Phosphorothioat- und LNA-Rückgrat sowie 5'-GalNAc-Konjugaten.

Es übernimmt einen bestehenden Excel-Rechner und baut ihn aus. Die
Arbeitsschritte stehen in `PHASEN.md`.

---

## Harte Regeln

1. **Ein Oligo ist nie eine Zeichenkette.** Immer eine Liste von
   Monomer-Objekten mit Position. Jede Funktion, die `str` erwartet, ist ein
   Entwurfsfehler.
2. **Die Excel-Konstanten sind verbindlich.** Restmassen, Amiditmassen,
   Konzentrationen, Schutzgruppen- und Modifikationsmassen werden nicht
   „korrigiert". Wird eine Konstante geändert, wird das in der Oberfläche
   farblich kenntlich gemacht — nie stillschweigend.
3. **Jede Zahl trägt ihre Verlässlichkeit mit**, als eines von drei Kennzeichen:
   `exakt` · `Parameter vorhanden` · `genähert über natürliches Analogon`.
   Bei modifizierten Oligos ist das die wichtigste Information auf dem Schirm.
4. **Keine KI, keine kostenpflichtige API, kein API-Schlüssel.** Alles läuft
   lokal. Netzzugriff nur für optionale Sequenz- und Strukturabrufe, immer mit
   lokalem Zwischenspeicher, und die App bleibt ohne Netz voll bedienbar.
5. **Unbekannte Zeichen in einer Sequenz sind ein Fehler** mit Positionsangabe.
   Niemals stillschweigend überspringen — genau das ist der Fehler im Excel.
6. **Der katalytische Kern wird nie stillschweigend verändert.** Eingriffe dort
   verlangen eine ausdrückliche Bestätigung und zeigen eine Warnung.
7. Dateien immer mit `encoding='utf-8'` lesen und schreiben.
8. Lange Rechnungen melden Fortschritt; die Oberfläche friert nie ein.

---

## Regressionstest — diese Werte müssen stimmen

Sequenz (Synthi-Sprache): `TTG GGG TAA GGC TAG CTA CAA CGA GGT GCA TGT`
Das ist ein 10-23-DNAzym: Arm `TTGGGGTAA` (9) + Kern `GGCTAGCTACAACGA` (15)
+ Arm `GGTGCATGT` (9), zusammen 33 Bausteine.

| Größe | Sollwert |
| --- | --- |
| vollständig entschützt | 10 241,26 |
| + DMT | 10 543,60 |
| + 3'-Phosphat | 10 303,22 |
| geschützt, DMT off | 13 821,16 |
| geschützt, ohne CE | 12 124,20 |

Synthesizer-Verbrauch bei 0,12 mL je Kupplung:
A 8 Kupplungen → 41,2 mg · C 5 → 23,2 mg · G 12 → 60,5 mg · T 8 → 35,8 mg ·
Summe 160,6 mg (mit 10 % Reserve 176,6 mg).

Diese Werte stehen als pytest-Fälle im Projekt und dürfen nie brechen.

---

## Sequenznotation (Synthi-Sprache)

Die bestehende Notation bleibt unverändert gültig:

| Zeichen | Bedeutung |
| --- | --- |
| `A C G T` | DNA |
| `O I Z U` | rA, rC, rG, rU |
| `E L` | eigene Bausteine, in der Monomer-Datei definiert |
| Leerzeichen | wird ignoriert |

Zwei rückwärtskompatible Zusätze:

| Zusatz | Bedeutung |
| --- | --- |
| `*` zwischen zwei Zeichen | Phosphorothioat an genau dieser Bindung |
| `[code]` | eigener Baustein an genau dieser Position, z. B. `[LNA-T]` |
| `/NAME/` | Konjugat oder Endmodifikation, z. B. `/5GalNAc/` |

Kleinbuchstaben werden akzeptiert und auf Großbuchstaben abgebildet.

---

## Technik

Backend: Python 3.12, FastAPI, Uvicorn, SQLite über SQLModel, RDKit, Biopython,
ViennaRNA, pydantic-settings.
Frontend: React, Vite, TypeScript, Tailwind, 3Dmol.js, Plotly.
Externe Programme: MELTING 5 (Java, Pfad in `.env` als `MELTING_DIR`),
optional ORCA (`ORCA_EXE`).

Externe Programme werden immer mit **vollem Pfad** und `shell=False` als
Unterprozess aufgerufen, nie über die Shell.

---

## Verzeichnisstruktur

```
oligolab/
├─ CLAUDE.md                  diese Datei
├─ PHASEN.md                  die Arbeitsschritte
├─ .env                       MELTING_DIR, ORCA_EXE, WORK_DIR
├─ app/
│  ├─ main.py                 FastAPI, Endpunkte
│  ├─ models.py               Datenmodelle
│  ├─ notation.py             Synthi-Sprache lesen und schreiben
│  ├─ mass.py                 Excel-Rechnung, exakt reproduziert
│  ├─ mass_exact.py           Gegenrechnung aus der Summenformel
│  ├─ extinction.py           eps260, OD-Umrechnung
│  ├─ synthesis.py            Synthesizer-Verbrauch
│  ├─ loading.py              PAGE- und LC-MS-Beladung
│  ├─ dnazyme.py              Kern und Arme erkennen
│  ├─ fold.py                 Faltung des Strangs
│  ├─ critical.py             kritische Stellen
│  ├─ target.py               Ziel-RNA holen und verwalten
│  ├─ fold_target.py          Struktur und Zugänglichkeit
│  ├─ melting.py              Anbindung an MELTING
│  ├─ scan.py                 Spaltstellen finden
│  ├─ design.py               Kandidaten bauen und bewerten
│  ├─ pdb.py                  Referenzstrukturen
│  ├─ model3d.py              3D-Modell bauen
│  └─ geometry.py             Winkel und Abstände
├─ data/
│  ├─ monomers.yaml           Bausteine mit allen Massen
│  ├─ protecting_groups.yaml  Schutzgruppen
│  ├─ modifications.yaml      Massendifferenzen
│  ├─ cores.yaml              katalytische Kerne
│  ├─ references.yaml         PDB-Referenzstrukturen
│  ├─ oligos.db               Bibliothek
│  ├─ targets/                geholte Zielsequenzen
│  └─ structures/             geholte PDB-Dateien
├─ help/help.yaml             alle Hilfetexte
└─ frontend/                  React + Vite
```

---

## Designsprache

**Drei Rollenfarben, nur diese:** grün für Eingaben (Sequenz, Ziel), grau für
Einstellungen (Puffer, Armlänge), blau für Ergebnisse (Masse, Tm, Energien).
Nur als Chip-Hintergrund mit 16 % Deckkraft und als Rahmenfarbe, nie als volle
Fläche.

**Eine Ampel** — grün, gelb, rot — ausschließlich für Bewertungen
(Kandidatengüte, Befunde). Nie dekorativ.

**Modifikationsfarben sind in allen Ansichten gleich** — Sequenzfeld,
Sequenzkarte, Paarungsdarstellung, 3D:

| Typ | Farbe |
| --- | --- |
| DNA, natürlich | grau |
| RNA-Baustein | blau |
| Zuckermodifikation (LNA, 2'-OMe, 2'-F) | grün |
| Basenmodifikation | orange |
| Konjugat (GalNAc, Farbstoff) | violett |
| Phosphorothioat | Symbol in der Lücke zwischen zwei Zellen |

Weitere Regeln: Sequenzen in Festbreitenschrift mit Positionslineal ab 20
Basen · Karten mit dünnem Rahmen, 8 px Radius, Abstände in 8er-Schritten ·
Ergebniszahlen groß mit Einheit, darunter klein die Methode · heller und
dunkler Modus über `prefers-color-scheme` · keine Verläufe, keine Schatten.

Jedes Formularfeld und jede Ergebnisgröße bekommt ein `data-help`-Attribut mit
sprechender ID (`field.*`, `result.*`, `method.*`), damit die
Fragezeichen-Hilfe später nur eingehängt werden muss.

---

## Vorgehen

`PHASEN.md` enthält sechs Abschnitte. Arbeite immer **genau einen** ab, führe
die darin genannten Tests aus und halte an, damit er geprüft werden kann.
Fange nie mehrere Phasen gleichzeitig an.

Reihenfolge:

1. Phase 1 — Massenrechner und Steckbrief
2. Oberfläche und Navigation
3. Phase 2 — Den Strang sichtbar machen
4. Phase 3 — Die Ziel-RNA
5. Phase 4 — DNAzym-Entwurf und Bewertung
6. Phase 5 — Geometrie und 3D
