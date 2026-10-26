# OligoLab

Lokales Programm zum Rechnen und Visualisieren für modifizierte DNAzyme
(10-23). Die Projektregeln stehen in [`CLAUDE.md`](CLAUDE.md), die
Arbeitsschritte in [`PHASEN.md`](PHASEN.md).

**Stand: Phase 1 abgeschlossen** — Massenrechner und Steckbrief.

---

## Inbetriebnahme

```bash
# Backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload        # http://127.0.0.1:8000

# Oberfläche, im Entwicklungsbetrieb
cd frontend && npm install && npm run dev      # http://localhost:5173
```

`npm run build` legt die gebaute Oberfläche in `frontend/dist`. Liegt sie
dort, liefert das Backend sie unter `http://127.0.0.1:8000` gleich mit aus —
dann genügt Uvicorn allein.

Tests:

```bash
.venv/bin/python -m pytest          # 171 Fälle
cd frontend && npm run typecheck
```

`.env` enthält nur Pfade zu externen Programmen (MELTING ab Phase 5, ORCA ab
Phase 6) und keine Zugangsdaten — OligoLab braucht keine. Maschinenspezifische
Abweichungen gehören in `.env.local`, das nicht versioniert wird.

---

## Was Phase 1 kann

| Bereich | Datei | |
| --- | --- | --- |
| Synthi-Sprache lesen und schreiben | `app/notation.py` | `*`, `[code]`, `/NAME/`, Übersetzer DNA ↔ RNA |
| Die fünf Massen der Excel-Rechnung | `app/mass.py` | |
| Gegenrechnung aus der Summenformel | `app/mass_exact.py` | Isotopenmuster, Natriumsalz, ESI-Ladungsleiter |
| Verbrauch am Synthesizer | `app/synthesis.py` | |
| Beladung PAGE und LC-MS | `app/loading.py` | |
| ε₂₆₀ und OD-Umrechnung | `app/extinction.py` | Nearest-Neighbor |
| Bibliothek und Probenliste | `app/library.py` | SQLite, CSV-Export |

Die Oberfläche hat zwei Seiten: **Steckbrief** (Sequenz, Massen, Reiter für
Synthese, Beladung, MS und Konzentration, Bibliothek) und **Bausteine** (alle
Konstanten ansehen, ändern, eigene anlegen).

Die Sollwerte aus `CLAUDE.md` stehen als pytest-Fälle im Projekt und stimmen:
alle fünf Massen auf 0,01 Da, die Verbrauchstabelle einschließlich Summe und
Reserve.

---

## Was die Gegenrechnung über das Excel sagt

Die unabhängige Rechnung aus der Summenformel weicht bei der Referenzsequenz
um **+32,4 Da** ab. Die Aufschlüsselung je Baustein zeigt, woher das kommt:

| Code | Excel | Isotopenmittel | Δ | monoisotopisch | Δ |
| --- | --- | --- | --- | --- | --- |
| A | 312,05 | 313,207 | −1,157 | 313,058 | **−1,008** |
| C | 289,18 | 289,182 | **−0,002** | 289,046 | +0,134 |
| G | 328,05 | 329,207 | −1,157 | 329,053 | **−1,003** |
| T | 303,04 | 304,194 | −1,154 | 304,046 | **−1,006** |

Zwei Konventionen in einer Tabelle: **C** stimmt mit dem Isotopenmittel
überein, **A, G und T** liegen je rund 1,00 Da unter ihrer monoisotopischen
Masse — also um ein Wasserstoffatom zu leicht.

Die Werte bleiben trotzdem verbindlich (`CLAUDE.md`, Regel 2). OligoLab
korrigiert nichts, sondern zeigt die Differenz an. Der Befund ist als
pytest-Fall festgehalten
(`tests/test_mass_exact.py::test_dokumentierte_abweichung_der_excel_restmassen`),
damit er nicht unbemerkt verschwindet — und damit auffällt, falls jemand die
Konstanten doch anfasst.

**Zu entscheiden:** ob die Restmassen auf eine einheitliche Konvention
gebracht werden sollen. Dagegen spricht, dass dann alle bisherigen
Excel-Rechnungen nicht mehr vergleichbar sind; dafür spricht, dass die
LC-MS-Messung um 32 Da danebenliegt. Bis das entschieden ist, bleibt alles wie
es war und die Oberfläche zeigt beide Zahlen nebeneinander.

---

## Offene Punkte aus Phase 1

**Das GalNAc-Konjugat hat keine Masse.** Sie hängt vollständig am Linker —
THA-C6 und GalNAc3-1a unterscheiden sich um einige hundert Dalton — und stand
im Excel nicht. Einen Wert zu erfinden wäre genau das, was Regel 2 und Regel 5
verbieten. Der Eintrag ist angelegt und als `needs_review` markiert; bis eine
Masse oder Summenformel eingetragen ist, meldet die Rechnung ihn als
unvollständig, statt mit einer Null weiterzurechnen. Einzutragen in
`data/modifications.yaml` beim Eintrag `5GalNAc`:

```yaml
mass_diff: <Masse des eigenen Konstrukts>
# oder
formula: <Summenformel>
```

**`E` und `L` haben keine Struktur.** Im Excel stand keine, also bleiben
`formula_residue` und `smiles` leer. Die Restmasse gilt trotzdem; nur die
Gegenrechnung meldet diese Bausteine als unvollständig.

---

## Entscheidungen, die von `CLAUDE.md` abweichen

Jede einzeln begründet, damit sie bei Bedarf zurückgedreht werden kann.

**Drei Module mehr als in der Verzeichnisstruktur.** `app/config.py`
(Einstellungen), `app/registry.py` (YAML-Kataloge) und `app/library.py`
(SQLite). Ohne sie läge das Laden der Datendateien in jedem Rechenmodul
einzeln. Die in `CLAUDE.md` genannten Dateien gibt es alle und sie tun, was
dort steht.

**Zwei Datendateien mehr.** `data/extinction.yaml` hält die
Nearest-Neighbor-Tabellen; die stehen nicht im Excel und sind deshalb
Parameter dieses Programms, nie `exakt`. `data/monomers_custom.yaml` nimmt
eigene Bausteine und Änderungen auf, damit `monomers.yaml` die unangetastete,
kommentierte Abschrift des Excel bleibt — jede Änderung ist dadurch schon
sichtbar, dass sie woanders steht, und lässt sich mit einem Knopf
zurücknehmen.

**Das Natriumsalz wird als Salz gerechnet, nicht als Addukt.** `PHASEN.md 1.4`
sagt „zusätzlich n Natriumionen". Wörtlich genommen wäre das die freie Säure
plus n·22,99 — chemisch ein Natrium-Addukt, nicht das Salz. Gerechnet wird
freie Säure − n·H + n·Na. Die Methode steht an jeder dieser Zahlen, ist in der
Oberfläche sichtbar und als Test festgehalten.

**Kein Plotly für das Isotopenmuster.** Fünf Balken rechtfertigen keine
4-MB-Bibliothek. Das Diagramm ist eingebettetes SVG, erbt die Farbtoken und
kann hell und dunkel. Die echten Diagramme der späteren Phasen
(Bogendiagramm, Zugänglichkeitsprofil) bekommen eine Bibliothek, sobald sie
gebraucht wird.

**Nur `data-help`-Attribute, noch keine Fragezeichen-Hilfe.** Die Komponente
`<HelpTip />` und die Seite `/hilfe` gehören zu Phase 2. `help/help.yaml` ist
mit 42 Einträgen angelegt, und jedes Formularfeld und jede Ergebnisgröße trägt
die passende ID — Phase 2 hängt die Komponente nur noch ein.

**Die Navigation hat zwei Einträge.** Die Seitenleiste mit Ziel, Entwurf,
Strang, Steckbrief und 3D samt Statusanzeige und Tastaturkürzeln ist
Phase 2. Hier steht nur, was schon rechnet.

---

## Grundsätze, die im Code durchschlagen

- **Ein Oligo ist nie eine Zeichenkette.** `Oligo` hält eine Liste von
  `Monomer`-Objekten mit Position. Phosphorothioate sitzen als `Linkage`
  zwischen zwei Monomeren — darum zeichnet die Oberfläche das Symbol in die
  Lücke. Konjugate stehen außerhalb der Basenzählung.
- **Jede Zahl trägt ihre Verlässlichkeit mit.** `Quantity` hält Wert, Einheit,
  Kennzeichen, Methode und Begründung. Eine Summe ist nie verlässlicher als
  ihr schwächster Beitrag.
- **Fehlt ein Wert, kommt `None` heraus und die Notiz nennt den Eintrag beim
  Namen.** Nie eine stillschweigende 0.
- **Ein unbekanntes Zeichen ist ein Fehler mit Positionsangabe.** `parse()`
  bricht beim ersten ab, `analyse()` sammelt alle ein, damit die Oberfläche
  jede Stelle einzeln rot unterkringeln kann. Hat die Sequenz Fehler, wird gar
  nicht gerechnet — alte Zahlen stehen zu lassen wäre schlimmer.

---

## Nächster Schritt

Phase 2 — Oberfläche und Navigation (`PHASEN.md`, Abschnitt 2).
