# OligoLab

Lokales Programm zum Rechnen und Visualisieren für modifizierte DNAzyme
(10-23). Die Projektregeln stehen in [`CLAUDE.md`](CLAUDE.md), die
Arbeitsschritte in [`PHASEN.md`](PHASEN.md).

**Stand: alle sechs Phasen abgeschlossen** — Massenrechner, Steckbrief,
Oberfläche, Sequenzkarte, Ziel-RNA, DNAzym-Entwurf, Geometrie und 3D.

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
.venv/bin/python -m pytest          # 313 Fälle
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

## Was Phase 5 kann

**Schmelztemperatur und Thermodynamik.** Tm, ΔH, ΔS und ΔG eines Arms über
die Nearest-Neighbor-Tabelle für DNA/RNA-Hybride (Sugimoto 1995) — ein
DNAzym-Arm bindet RNA, nicht DNA. Tm und Thermodynamik stammen aus derselben
Rechnung, damit sie sich nicht leise widersprechen können; ein Test rechnet
gegen Biopython gegen. Ist MELTING 5 eingerichtet (`MELTING_DIR` in `.env`),
läuft es als Zweitmeinung mit vollem Pfad und `shell=False` mit; weichen
beide um mehr als 3 °C ab, steht eine Warnung dabei.

**Spaltstellen.** Alle Purin-Pyrimidin-Junktionen im gewählten Bereich, mit
Güte: AU und GU gut, GC mäßig, AC schlecht. AC ist voreingestellt
ausgeblendet — aber gezählt und einblendbar. Dazu je Stelle, ob das Purin
offen und das Pyrimidin gepaart ist: ein veröffentlichter Anhaltspunkt, der
mitgeteilt und nicht zum Ausschluss benutzt wird.

**Kandidaten.** Für jede Stelle ein Strang aus `revcomp(stromab) + Kern +
revcomp(stromauf)`, bewertet über sechs Kriterien. Kriterien ohne Wert
werden weggelassen, nicht als Null gewertet — sonst zöge eine fehlende
Zugänglichkeit jeden Kandidaten gleichmäßig nach unten. Binden die Arme bei
den gewählten Bedingungen gar nicht (ΣΔG positiv), kommt kein Grün zustande,
auch wenn die übrigen fünf Kriterien die Punktzahl hochtragen.

**Die Punktzahl ordnet, sie urteilt nicht.** Der Hinweis steht sichtbar über
der Tabelle und im CSV-Kopf: das beste veröffentlichte Modell erreicht 63 bis
73 Prozent Trefferquote auf 38 DNAzymen.

**Die Seite „Entwurf"** zeigt oben die Einstellungen, darunter das
Zugänglichkeitsprofil mit jedem Kandidaten als Marke in seiner Ampelfarbe,
dann die sortier- und filterbare Rangliste mit einer Ampel je Zeile, und für
den gewählten Kandidaten die **Paarungsdarstellung**: Ziel-RNA oben in
5'→3', das DNAzym darunter gegenläufig, Basenpaare als senkrechte Striche,
Fehlpaarungen als offener Kreis, der Kern als Schleife über der
Schnittstelle, die Spaltstelle mit einem Pfeil, Modifikationen in ihren
Farben. Dazu CSV und SVG und „Als Oligo übernehmen".

**Modifikationen als Muster**, mit Vorher-Nachher-Vergleich durch dieselbe
Rechnung. Ein Eingriff in den katalytischen Kern wird blockiert und verlangt
eine ausdrückliche Bestätigung (CLAUDE.md, Regel 6) — das ist kein
HTTP-Fehler, sondern eine Rückfrage.

**Was dabei ehrlich bleiben muss:** eine LNA hebt die Masse um 12 Da je
Baustein, den gerechneten Tm aber um nichts — die Nearest-Neighbor-Tabelle
kennt sie nicht und rechnet über das DNA-Analogon. In einer
Vorher-Nachher-Tabelle läse sich „unverändert" wie „die LNA bewirkt nichts".
Darum trägt jeder Vergleich die Liste der genäherten Positionen mit und sagt
ausdrücklich: *das Modell sieht es nicht*.

---

## Was Phase 6 kann

**Referenzstrukturen** aus `data/structures/`, von der RCSB-PDB oder als
eigene Datei. Methode, Auflösung und Literatur werden aus der Datei gelesen,
nicht von Hand in den Katalog geschrieben: ein abgeschriebener Wert wäre eine
zweite Quelle, die beim ersten Tippfehler von der ersten abweicht. Welche
Kette das DNAzym ist und welche das Substrat, entscheidet die Art der Reste —
nicht der Buchstabe der Kette.

**Das Modell** entsteht, indem die Sequenz auf die Referenz gefädelt wird:
gleiche Position, gleiche Rückgratkoordinaten, ausgetauschte Base. Ausgerichtet
wird am katalytischen Kern, dem einzigen Anker, der nicht geraten ist.

**Jede Position trägt mit, woher ihre Koordinaten stammen** — genau wie jede
Zahl im übrigen Programm:

| Kennzeichen | Bedeutung |
| --- | --- |
| aus der Referenz | Base gleich, alle Atome übernommen |
| Ringgerüst | Purin gegen Purin: das gemeinsame Gerüst bleibt, die unterschiedlichen Substituenten fallen weg |
| nur Zucker | Purin gegen Pyrimidin: nur Zucker und Phosphat. Die Base wird **nicht geraten** |
| ideal | außerhalb der Referenz, ohne gemessene Koordinaten |

Ein hingeschobenes Ringatom sieht im Bild genauso aus wie ein gemessenes —
das ist der Grund, es zu lassen.

**Der In-line-Winkel** 2'-O ··· P ··· O5' an der Spaltstelle, mit beiden
Abständen und einer Ampel. Auf einem DNA-Rest gibt es keine Zahl, sondern den
Grund: ohne 2'-OH gibt es keinen In-line-Angriff. Dazu der Abstand jeder
modifizierten Position zur Spaltstelle, zum Kern (in Å **und** in Nukleotiden)
und zu Metallionen — unter 6 Å ist das ein Warnsignal.

**Die 3D-Ansicht** mit 3Dmol.js: Cartoon für das Rückgrat, Stäbchen für
Ausgewähltes, Einfärbung nach Kette, Bauteil oder Modifikationstyp — mit
denselben Farben wie die Sequenzkarte. Die Spaltstelle ist immer markiert und
beschriftet. Sequenzkarte und 3D-Fenster teilen sich eine Auswahl: ein Klick
in der Karte hebt die Position im Modell hervor und umgekehrt.

**ORCA-Vorbereitung** (freiwillig): Fragment schneiden, abgeschnittene
Bindungen mit Wasserstoff absättigen, Eingabedatei schreiben — für
Geometrieoptimierung, Wechselwirkungsenergie oder elektrostatisches Potential.
**Gerechnet wird hier nichts.** Quantenchemie läuft nicht nebenbei im
Hintergrund einer Oberfläche.

**Der Gesamtbericht** fasst alles auf einem Blatt zusammen, mit Datum und allen
Einstellungen im Fuß. Er rechnet nichts nach — eine zweite Rechnung könnte von
der Anzeige abweichen, und dann glaubte man der falschen.

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

**Fünf Module mehr als in der Verzeichnisstruktur.** `app/config.py`
(Einstellungen), `app/registry.py` (YAML-Kataloge), `app/library.py`
(SQLite), `app/orca.py` (die freiwillige Brücke aus 6.5) und `app/report.py`
(der Gesamtbericht aus 6.6). Die beiden letzten haben in `CLAUDE.md` keinen
Platz, weil die Verzeichnisstruktur dort vor Phase 6 geschrieben wurde; sie
gehören zu Abschnitten, die es dort gibt. Ohne sie läge das Laden der Datendateien in jedem Rechenmodul
einzeln. Die in `CLAUDE.md` genannten Dateien gibt es alle und sie tun, was
dort steht.

**Das PDF schreibt der Browser.** `PHASEN.md` 6.6 verlangt HTML und PDF.
Erzeugt wird HTML mit einem Druckstil, das PDF entsteht im Druckdialog. Eine
PDF-Bibliothek hätte Systembibliotheken nachgezogen (Cairo, Pango), die sich
ohne Netz nicht nachinstallieren lassen — für dasselbe Blatt.

**Die ideale Helix ist nur eine Rückgratspur.** `PHASEN.md` 6.2 will
Längenunterschiede als ideale Hybridhelix verlängern. Erzeugt werden dafür
Phosphorlagen, keine vollständigen Nukleotide: eine ganze Nukleotidgeometrie
aus Standardwerten zusammenzusetzen hieße, Atomlagen zu erfinden, die
hinterher wie gemessene aussehen. Positionen außerhalb der Referenz werden
darum als `ideal` gekennzeichnet und nicht im Modell dargestellt.

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

## Was ungeprüft bleibt

Drei Wege gehen nach außen und ließen sich in dieser Umgebung nicht bis zum
Ende prüfen. Sie sind alle freiwillig — ohne sie bleibt OligoLab voll
bedienbar.

**Die Sequenzabrufe** (Ensembl, NCBI, RNAcentral) sind von hier nicht
erreichbar. Geprüft ist der Weg mit einer nachgebildeten Antwort, der
Zwischenspeicher und das Verhalten ohne Netz.

**MELTING 5** ist nicht installiert. Geprüft ist der Aufruf — voller Pfad,
`shell=False`, Rückgabecode — und das Lesen einer nachgebildeten Ausgabe,
nicht die Ausgabe des echten Programms.

**Die RCSB-PDB** ist von hier nicht erreichbar, also auch nicht `8E9A`. Der
Abnahmetest der Phase 6 läuft deshalb auf `frontend/e2e/fixtures/TESTREF.pdb`:
einer Struktur mit **bekannter** Geometrie. Für ein Messgerät ist das sogar
der bessere Prüfstein — bei `8E9A` müsste die richtige Antwort erst wieder
gemessen werden. Mit Netz:

```
# In der Oberfläche: Bereich 3D → Struktur „8E9A" → „holen"
curl -o data/structures/8E9A.cif https://files.rcsb.org/download/8E9A.cif
```

Liegt die Datei im Ablageort, läuft alles Weitere ohne Netz.
