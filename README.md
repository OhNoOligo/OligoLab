# OligoLab

Lokales Programm zum Rechnen und Visualisieren für modifizierte DNAzyme
(10-23). Die Projektregeln stehen in [`CLAUDE.md`](CLAUDE.md), die
Arbeitsschritte in [`PHASEN.md`](PHASEN.md).

**Stand: Phase 4 abgeschlossen** — Massenrechner, Steckbrief, Oberfläche,
Navigation, Sequenzkarte und die Ziel-RNA.

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
.venv/bin/python -m pytest          # 309 Fälle
cd frontend && npm run typecheck
cd frontend && npm run e2e          # Abnahmetests zu Phase 2, 3 und 4
```

Der Abnahmetest fährt die gebaute Oberfläche gegen das laufende Backend. Er
braucht einmalig einen Browser (`npx playwright install chromium`); liegt
schon einer auf dem Rechner, genügt sein Pfad in `CHROMIUM_PATH`.

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
| Bauteile erkennen | `app/dnazyme.py` | 5'-Arm, Kern, 3'-Arm über `base_parent` |
| Faltung | `app/fold.py` | ViennaRNA mit DNA-Parametern |
| Kritische Stellen | `app/critical.py` | acht Befunde mit Schweregrad |
| Ziel-RNA holen | `app/target.py` | Text, FASTA, GenBank, drei Datenbanken |
| Zugänglichkeit | `app/fold_target.py` | RNAplfold-Profil, RNAup-Zerlegung |

Die Oberfläche hat vier gefüllte Seiten: **Ziel** (Zielsequenz,
Zugänglichkeit, Faltung), **Strang** (Sequenzkarte, Faltung, Befunde),
**Steckbrief** (Massen, Synthese, Beladung, MS, Konzentration, Bibliothek) und
**Bausteine** (alle Konstanten ansehen, ändern, eigene anlegen).

Die Sollwerte aus `CLAUDE.md` stehen als pytest-Fälle im Projekt und stimmen:
alle fünf Massen auf 0,01 Da, die Verbrauchstabelle einschließlich Summe und
Reserve.

---

## Was Phase 2 kann

**Ein Zustand für alles.** `activeOligo`, `activeTarget` und die Bedingungen
liegen in `frontend/src/state/store.tsx` und nirgends sonst. Keine Seite hält
eine eigene Kopie der Sequenz — sonst liefe sie irgendwann auseinander, ohne
dass es jemandem auffiele. Gespiegelt in `localStorage`, ein Neuladen verliert
nichts.

**Veraltete Ergebnisse sagen es.** Jeder Bereich merkt sich einen
Fingerabdruck der Eingaben, mit denen er gerechnet hat. Ändert sich etwas
daran, steht in der Seitenleiste `veraltet` und der Bereich bietet
„Neu berechnen" an, statt alte Zahlen als gültig auszugeben. Welche Eingaben
zählen, ist je Bereich festgelegt: ein Dreh am Magnesium entwertet den
Entwurf, aber nicht den Steckbrief.

**Kopfzeile, immer sichtbar.** Links das aktive DNAzym mit Name, Länge und
Masse und einem Schnellwechsler auf die zuletzt benutzten; in der Mitte die
Ziel-RNA; rechts die Bedingungen. Ist ein Platz leer, steht dort ein
Eingabefeld statt einer leeren Zeile. Die Masse holt die Kopfzeile über
`/api/summary` aus derselben Quelle wie der Steckbrief.

**Fünf Bereiche, eine Reihenfolge.** Ziel · Entwurf · Strang · Steckbrief · 3D
als Seitenleiste links, jeder mit seinem Stand und mit Strg+1 bis Strg+5
erreichbar. Vier davon sind angelegt und erreichbar, rechnen aber noch nicht —
sie sagen, was sie brauchen, und die Phasen 3 bis 6 füllen sie.

**Übergaben.** Jeder Bereich endet mit einem Knopf in den nächsten.

**Fragezeichen-Hilfe.** `<HelpTip />` zieht aus `help/help.yaml`; Überfahren
zeigt zwei bis drei Sätze, Klick ein Panel mit Details, Escape schließt.
`aria-describedby` ist gesetzt, Tastatur und Finger gehen. Die Glossarseite
`/hilfe` listet alle 49 Einträge mit Suchfeld. Weil die `data-help`-IDs schon
in Phase 1 an jedem Feld standen, musste die Komponente nur eingehängt werden.

---

## Was Phase 3 kann

**Bauteile erkennen.** `data/cores.yaml` hält das 10-23 mit Kernsequenz,
Zieltyp, bevorzugten Spaltstellen, Metallionenbedarf und Quelle. Gesucht wird
der Kern über das natürliche Analogon, nicht über den Synthi-Buchstaben: ein
Kern, in dem eine Position durch LNA-T ersetzt wurde, ist immer noch derselbe
Kern — und genau dieser Fall soll ja gemeldet werden. Kein Kern gefunden ist
kein Fehler.

**Faltung mit DNA-Parametern.** Der Unterschied ist keine Feinheit: dieselbe
Haarnadel liegt mit RNA-Parametern bei −23 kcal/mol und mit DNA-Parametern bei
−12. ViennaRNA hält den Parametersatz global, darum läuft jede Rechnung durch
einen Kontextmanager, der hinterher wieder auf RNA stellt — sonst faltete
Phase 4 ihre Ziel-RNA mit DNA-Parametern, ein Fehler, den niemand bemerkt,
weil die Zahlen plausibel aussehen.

**Acht Befunde** mit Bereich, Schweregrad und einem Satz Erklärung. Die
Schwellen stehen als benannte Konstanten beieinander und gehen mit in die
Antwort, damit die Oberfläche sagen kann, woran gemessen wurde. Wo eine
Schwelle eine Hausregel ist und kein Literaturwert, steht das dabei.

**Die Sequenzkarte** als SVG mit sechs Spuren: Positionslineal, Bausteine
(Phosphorothioat als Punkt in der Lücke, denn dort sitzt es chemisch),
Bauteile, Bogendiagramm der Faltung mit Strichstärke nach
Paarungswahrscheinlichkeit, Balken für die Ungepaart-Wahrscheinlichkeit und
die Warnspur. Zoom, Export als SVG und PNG, und eine Vergleichsansicht für bis
zu drei Varianten, deren Karten Position für Position fluchten.

Zwischen Karte und Befundliste geht es in beide Richtungen: Klick auf einen
Befund hebt seinen Bereich hervor, Klick auf einen Marker rollt zur Erklärung.

---

## Was Phase 4 kann

**Vier Wege zum Ziel.** Rohsequenz einfügen, FASTA oder GenBank hochladen,
oder aus Ensembl, NCBI und RNAcentral holen. Das Format wird erkannt. DNA
wird stillschweigend zu RNA, Leerraum und Zahlen fallen weg — aber jedes
andere unbekannte Zeichen ist ein Fehler mit Positionsangabe.

**Ohne Netz bleibt alles bedienbar.** Ein fehlgeschlagener Abruf ist kein
Fehler, sondern ein Zustand: die Antwort sagt ruhig, dass OligoLab lokal
rechnet, und greift auf den Zwischenspeicher in `data/targets/` zurück. Die
Ratenbremsen folgen den Angaben der Anbieter — sie zu überschreiten führt zu
Sperren, und zwar für den Nutzer.

**Das Zugänglichkeitsprofil** über RNAplfold, je Position die
Wahrscheinlichkeit, dass ab hier L Nukleotide offen sind. Es ist am
Fensteranfang verankert: ViennaRNA gibt die Wahrscheinlichkeit für das
Fenster zurück, das an einer Position *endet* — ohne Umrechnung läge das
ganze Profil um L−1 Positionen verschoben, und man legte die Sonde an die
falsche Stelle.

**Kilobasen gehen.** Das Profil rechnet lokal und läuft über jede Länge, in
überlappenden Stücken mit Fortschrittsmeldung. Die Gesamtfaltung wird ab 3000
Basen mit Begründung ausgelassen: sie kostet viel Zeit und sagt wenig, weil
ein Transkript dieser Länge in der Zelle nicht als ein Stück faltet.

**Die Seite „Ziel"** zeigt den Sequenztext mit Lineal, abgesetzten
Abschnitten und Suchfeld, darunter dieselbe Spurdarstellung wie Phase 3.
Weil ein Transkript Tausende von Basen hat, gibt es zwei Ebenen: die
Übersichtsleiste über die ganze Länge und die Detailkarte für den gewählten
Bereich.

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

**Die Datenbankabrufe sind ungetestet gegen die echten Dienste.** Ensembl,
NCBI und RNAcentral sind aus der Entwicklungsumgebung nicht erreichbar. Die
Adressen, Parameter und Ratenbremsen folgen der Dokumentation der Anbieter,
und das Verhalten ohne Netz ist geprüft — der erfolgreiche Abruf selbst aber
nur gegen eine nachgebildete Antwort. Wer eine Verbindung hat, sollte ihn
einmal durchspielen.

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

**Kein Plotly, auch nicht für die Sequenzkarte.** Fünf Balken für das
Isotopenmuster rechtfertigten keine 4-MB-Bibliothek, und die Sequenzkarte
schreibt PHASEN.md ohnehin als SVG vor. Beides ist eingebettetes SVG, erbt die
Farbtoken und kann hell und dunkel. Für den Export werden die CSS-Variablen
durch ihre errechneten Werte ersetzt — eine herausgelöste Datei wäre sonst
farblos.

**Nur `data-help`-Attribute, noch keine Fragezeichen-Hilfe** — erledigt in
Phase 2.

**Ein eigener kleiner Router statt react-router.** Sechs feste Pfade
rechtfertigen keine Bibliothek; `frontend/src/router.tsx` sind vierzig Zeilen
über `history.pushState`. Damit ein Direktaufruf von `/hilfe` nicht ins Leere
läuft, liefert das Backend für alles außerhalb von `/api` die `index.html`
aus — ein unbekannter Endpunkt unter `/api` bleibt ein 404.

**Ein zusätzlicher Endpunkt `/api/summary`.** Nur Länge, Masse und Zahl der
Befunde, für die immer sichtbare Kopfzeile. Sie soll nicht bei jedem
Tastendruck die volle Rechnung samt Isotopenmuster anstoßen, und die Masse
dort soll aus derselben Quelle kommen wie im Steckbrief.

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

Phase 5 — DNAzym-Entwurf und Bewertung (`PHASEN.md`, Abschnitt 5):
Spaltstellen finden, Kandidaten bauen und bewerten, MELTING anbinden.
