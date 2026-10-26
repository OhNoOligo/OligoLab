# OligoLab — Arbeitsschritte

Sechs Abschnitte. Arbeite immer genau einen ab, führe die Tests am Ende aus und
halte an. Die Regeln aus `CLAUDE.md` gelten durchgehend.

---

## Phase 1 — Massenrechner und Steckbrief

**Ziel:** Der bestehende Excel-Rechner läuft vollständig im Programm, mit
denselben Zahlen, und ist um das erweitert, was eine Tabelle nicht kann.

### 1.1 Monomer- und Konstantendateien

`data/monomers.yaml` — übernimm **exakt** diese Werte.

Restmassen (`mass_residue`), Synthi-Buchstabe als `code`:

```
A 312.05    C 289.18    G 328.05    T 303.04
O 328.05 (rA)    I 304.03 (rC)    Z 344.04 (rG)    U 305.02 (rU)
E 250.00    L 371.04
```

Amiditmassen (`mass_amidite`) und Kupplungskonzentration (`conc_molar`):

```
A 857.95 / 0.05     C 771.85 / 0.05     G 839.92 / 0.05     T 744.83 / 0.05
U 760.82 / 0.07     O 887.97 / 0.07     I 801.88 / 0.07     Z 869.97 / 0.07
E 948.85 / 0.10     L 800.00 / 0.07
```

Weitere Felder je Eintrag: `name`, `formula_residue` (Summenformel, wo
bekannt), `eps260`, `base_parent`, `core_tested` (ja/nein/unbekannt), `smiles`,
`quelle`. Fehlt eine Summenformel, bleibt das Feld leer — die Restmasse gilt
trotzdem.

`data/protecting_groups.yaml`:

```
Bz 104.03    Ac 42.02    iBu 70.05    dmf 56.06
CE 53.03     PAC 134.04  TBDMS 114.09
```

`data/modifications.yaml` — Massendifferenzen:

```
RNA +16        OMe +30        MOE +74.04     LNA +12
Me-Phosphonat -2              Thioat +16
6-FAM +537.46  TET +675.24    HEX +744.13    TBDMS +114.09
```

Dazu freie Plätze für eigene Modifikationen (Name + Massendifferenz) und einen
Eintrag für 5'-GalNAc (triantennär) als Konjugat: eigene Summenformel, kein
`base_parent`, kein Beitrag zur Basenzählung.

### 1.2 `app/notation.py` — Synthi-Sprache lesen

- `parse(seq)`: Leerzeichen und Zeilenumbrüche ignorieren, dann Zeichen für
  Zeichen in Monomere zerlegen. Notation wie in `CLAUDE.md`.
- Jedes nicht erkannte Zeichen ist ein **Fehler mit Positionsangabe**.
- Kleinbuchstaben akzeptieren und abbilden.
- `to_string(monomers)` als Umkehrung.
- Übersetzer wie im Excel: DNA → Synthi-RNA (T→U, C→I, A→O, G→Z) und zurück,
  als Funktion und als Werkzeug in der Oberfläche.
- pytest mit mindestens 12 Fällen, darunter die Beispielsequenz, ein voll
  thioiertes Rückgrat, ein `[code]`-Baustein und ein Konjugat.

### 1.3 `app/mass.py` — die Excel-Rechnung

```
Basis = Σ Restmassen + Σ Massendifferenzen der Modifikationen

fully_deprotected = Basis − 61.96
plus_dmt          = fully_deprotected + 302.34
plus_3_phosphate  = Basis
protected_dmt_off = fully_deprotected + n_A·104.03 + n_G·70.05
                    + n_C·42.02 + 53.03·(L−1)
protected_ce      = protected_dmt_off − 53.03·(L−1)
```

`L` ist die Zahl der Bausteine. Die Sollwerte aus `CLAUDE.md` werden als
pytest-Fall hinterlegt.

### 1.4 `app/mass_exact.py` — Gegenrechnung

- Summenformel des ganzen Oligos aus `formula_residue` plus Endgruppen plus
  Konjugaten, mit RDKit.
- Monoisotopische und mittlere Masse, beide als freie Säure.
- Natriumsalz: zusätzlich n Natriumionen, n = Zahl der Phosphate und
  Phosphorothioate. Beide Werte nebeneinander zeigen.
- Isotopenmuster: die fünf häufigsten Peaks mit relativer Intensität.
- ESI-Ladungsleiter negativ, Ladungen 2− bis 15−, nach
  `(M − n·1.00794)/n`, Bereich einstellbar.
- **Vergleich mit 1.3:** Differenz anzeigen. Unter 0,5 Da grün, darüber eine
  Warnung mit dem Hinweis, welcher Baustein keine Summenformel hat.

### 1.5 `app/synthesis.py` — Synthesizer-Verbrauch

- Verbrauch je Kupplung 0,12 mL, einstellbar.
- Je Baustein: Volumen = Anzahl · 0,12 mL, Masse = Volumen · Konzentration ·
  Amiditmasse.
- Tabelle mit Volumen, Konzentration, Masse und Masse + 10 % Reserve, dazu eine
  Summenzeile. Der Hinweis „immer mindestens 10 % aufschlagen" steht sichtbar
  daneben.
- Zahl der Synthesen als Faktor einstellbar.

### 1.6 `app/loading.py` — Beladung

- PAGE: Oligo-Volumen = `n_loading / (n_stock · 1000 / V_stock) · 2`,
  Wasser = `10 − Oligo-Volumen`, dazu 10 µL 2× DNA-Puffer.
- LC-MS: Oligo-Volumen = `n_injection / (n_stock · 1000 / V_stock) ·
  (V_sample / V_injection)`, Wasser = `V_sample − Oligo-Volumen`.
- Probenliste mit Name, n(Stock), V(Stock), die gespeichert bleibt.
- Warnung, wenn im Vial weniger als 4 µL übrig blieben.

### 1.7 `app/extinction.py`

- ε₂₆₀ nach dem Nearest-Neighbor-Modell für die natürlichen Bausteine.
- Modifizierte Bausteine mit eigenem ε₂₆₀, sonst über `base_parent`, markiert.
- Umrechnung A₂₆₀ ↔ Konzentration, OD ↔ nmol ↔ µg: drei Felder, zwei eingeben,
  das dritte bekommen.

### 1.8 Oberfläche: Seite „Steckbrief"

- Großes Sequenzfeld in Festbreitenschrift, Dreiergruppen wie im Excel, mit
  Syntaxhervorhebung nach der Farbtabelle in `CLAUDE.md`. Unbekannte Zeichen
  rot unterkringelt mit Erklärung.
- Rechts eine Karte mit den fünf Massen untereinander, klar beschriftet, jede
  mit Kopierknopf. Darunter die Gegenrechnung mit Differenz.
- Reiter: **Synthese** (Verbrauchstabelle) · **Beladung** (PAGE und LC-MS) ·
  **MS** (Ladungsleiter und Isotopenmuster als Balkendiagramm) ·
  **Konzentration** (OD-Rechner).
- Bibliothek gespeicherter Oligos: Name, Sequenz, Masse, Datum, durchsuchbar,
  Export als CSV.
- Seite „Bausteine": alle Werte ansehen und bearbeiten, eigene Bausteine über
  ein Formular anlegen (Code, Name, Restmasse oder SMILES, Amiditmasse,
  Konzentration, ε₂₆₀). Abweichungen von den Excel-Konstanten farblich
  hervorheben.

**Test:** Beispielsequenz gegen die fünf Sollmassen und die Verbrauchstabelle
aus `CLAUDE.md`.

---

## Phase 2 — Oberfläche und Navigation

**Ziel:** Eine Oberfläche, die sich von selbst erklärt. Sende diesen Abschnitt,
sobald Phase 1 läuft; er gilt danach für alles Weitere.

### 2.1 Zustand

Ein globaler Zustand hält `activeOligo` (Monomerliste, Name, Notizen),
`activeTarget` (Sequenz, Quelle, gewählter Bereich) und `bufferSettings`
(Oligo-Konzentration, Na, K, Tris, Mg, Reaktionstemperatur).

- Alle Bereiche lesen daraus. **Niemand kopiert Sequenzen zwischen Seiten.**
- Änderungen machen abgeleitete Ergebnisse ungültig: sichtbar als veraltet
  markieren und „Neu berechnen" anbieten, statt alte Zahlen stehen zu lassen.
- Zustand in `localStorage` spiegeln, damit ein Neuladen nichts verliert.

### 2.2 Kopfzeile, immer sichtbar

- Links das aktive DNAzym: Name, Länge, Masse. Klick öffnet einen
  Schnellwechsler mit den zuletzt benutzten.
- Mitte die aktive Ziel-RNA: Name, Länge, gewählter Bereich.
- Rechts die Bedingungen kompakt („50 mM Na, 2 mM Mg, 37 °C").
- Ist nichts gesetzt, steht dort ein Eingabefeld statt einer leeren Zeile.

### 2.3 Navigation

Fünf Bereiche in fester Reihenfolge: **Ziel · Entwurf · Strang · Steckbrief ·
3D**, als Seitenleiste links, nicht als Reiter oben. Jeder Eintrag zeigt einen
Status (leer, berechnet, veraltet). Tastaturkürzel Strg+1 bis Strg+5.

### 2.4 Übergaben

Jeder Bereich endet mit einem Knopf, der das Ergebnis in den nächsten trägt:

```
Ziel       → „Spaltstellen suchen"     → Entwurf
Entwurf    → „Als Oligo übernehmen"    → Strang
Strang     → „Masse und MS berechnen"  → Steckbrief
Steckbrief → „3D-Modell bauen"         → 3D
Entwurf    → „Nächsten Kandidaten"     → zurück in die Liste
```

Der Zielbereich öffnet sich bereits gefüllt und rechnet sofort los.

### 2.5 Verlässlichkeit sichtbar machen

Jede Zahl trägt ein kleines Zeichen: exakt, aus Parametern berechnet, oder über
ein natürliches Analogon genähert. Beim Überfahren erscheint die Begründung.

### 2.6 Fragezeichen-Hilfe

Komponente `<HelpTip id="..." />`, die Texte aus einer einzigen `help/help.yaml`
zieht. Neben jedem Formularfeld und jeder Ergebniszahl ein kleines graues
Fragezeichen: Überfahren zeigt zwei bis drei Sätze, Klick ein Panel mit
Details. Tastatur- und Touch-tauglich, `aria-describedby` korrekt gesetzt.
Eine Glossarseite `/hilfe` listet alle Einträge mit Suchfeld.

**Test:** Oligo im Steckbrief ändern und prüfen, dass alle anderen Bereiche ihre
Ergebnisse als veraltet markieren.

---

## Phase 3 — Den Strang sichtbar machen

**Ziel:** Der Strang als Karte, auf der man kritische Stellen sofort sieht.

### 3.1 `app/dnazyme.py` — Bauteile erkennen

`data/cores.yaml` mit den katalytischen Kernen. Nimm das **10-23** auf:
`5'-GGCTAGCTACAACGA-3'`, 15 Nukleotide, schneidet RNA. Pro Eintrag: Name,
Kernsequenz, Zieltyp, bevorzugte Spaltstellen, Metallionenbedarf, Quelle.

`detect_parts(oligo)` sucht die Kernsequenz im Strang — über `base_parent`,
damit modifizierte Bausteine erkannt werden — und gibt die Indexbereiche von
5'-Arm, Kern und 3'-Arm zurück. Wird kein Kern gefunden, ist das kein Fehler.

### 3.2 `app/fold.py` — Faltung

ViennaRNA mit **DNA-Parametern**: MFE-Struktur, Ensemble-Energie,
Basenpaar-Wahrscheinlichkeiten und daraus je Position die Wahrscheinlichkeit,
ungepaart zu sein. Homodimer über RNAcofold. Modifizierte Bausteine gehen über
`base_parent` ein; jedes Ergebnis, das darauf beruht, wird markiert.

### 3.3 `app/critical.py` — kritische Stellen

Liste von Befunden mit Positionsbereich, Schweregrad und einem Satz Erklärung:

| Befund | Schweregrad |
| --- | --- |
| Modifikation im katalytischen Kern, deren `core_tested` nicht `ja` ist | kritisch |
| Haarnadel mit ΔG unter −2 kcal/mol im Kern oder überlappend | kritisch |
| Haarnadel mit ΔG unter −2 kcal/mol sonst | Warnung |
| Selbstdimer unter −6 kcal/mol | Warnung |
| G-Quadruplex-Muster (vier G-Läufe, Abstände 1–7) | Warnung |
| Arm kürzer als 7 Nukleotide | Warnung |
| Vier oder mehr gleiche Basen hintereinander | Hinweis |
| Stark unterschiedliche Armlängen | Hinweis |

Der erste Befund ist der wichtigste des ganzen Programms: Eingriffe im Kern
kosten häufig die gesamte Aktivität.

### 3.4 Oberfläche: Seite „Strang" — die Sequenzkarte

Als **SVG** zeichnen, nicht mit HTML-Tabellen; zoom- und scrollbar, bei 50
Nukleotiden gut lesbar. Spuren von oben nach unten:

1. Positionslineal, Nummerierung alle 5 Basen, 5' links, 3' rechts
2. Basenspur, eine Zelle je Position, Einfärbung nach der Farbtabelle;
   Phosphorothioat als Symbol **in der Lücke**, nicht in der Zelle
3. Bauteilspur: durchgehende Balken für „5'-Arm", „Katalytischer Kern",
   „3'-Arm", beschriftet
4. Bogendiagramm der Faltung: Basenpaare als Bögen über der Sequenz,
   Strichstärke nach Paarungswahrscheinlichkeit
5. Balkenspur: Wahrscheinlichkeit, ungepaart zu sein
6. Warnspur: farbige Marker an den Positionen aus 3.3

Beim Überfahren einer Position: Nummer, Baustein, Name, Rückgrat,
Paarungspartner, Befunde. Klick auf einen Warnmarker rollt zur Erklärung.

Rechts die Befundliste, nach Schweregrad sortiert; Klick hebt den Bereich in
der Karte hervor. Dazu eine Vergleichsansicht für zwei bis drei Varianten,
Karten exakt aneinander ausgerichtet. Export der Karte als SVG und PNG.

**Test:** Ein DNAzym mit absichtlicher LNA im katalytischen Kern — die kritische
Warnung muss erscheinen.

---

## Phase 4 — Die Ziel-RNA

**Ziel:** Zielsequenz eingeben oder holen, falten, Zugänglichkeitsprofil.

### 4.1 `app/target.py` — Ziel eingeben

- Direkteingabe: Sequenz einfügen, DNA wird stillschweigend in RNA übersetzt
  (T → U), Leerzeichen und Zahlen entfernt.
- FASTA oder GenBank hochladen, mit Biopython geparst.
- Optional aus Datenbanken holen, jeweils mit Zwischenspeicher in
  `data/targets/`:
  - **Ensembl REST** (`rest.ensembl.org`): Gensuche über `/lookup/symbol`,
    Transkripte über `/lookup/id?expand=1`, Sequenz über `/sequence/id` mit
    `type=cdna`. Bei mehreren Isoformen eine Auswahlliste, kanonische und
    längste gekennzeichnet.
  - **NCBI E-utilities**: `esearch` und `efetch`, Kennmail mitschicken,
    höchstens drei Anfragen pro Sekunde.
  - **RNAcentral**: `https://rnacentral.org/api/v1/rna/{URS_ID}.json`,
    höchstens 20 Anfragen pro Sekunde, kein Schlüssel.
- Ohne Netz bleibt die Seite voll bedienbar; dann ein ruhiger Hinweis statt
  einer Fehlermeldung.
- Jedes Ziel bekommt Name, Quelle, Kennung, Abrufdatum und steht in einer
  Bibliothek.

### 4.2 Abschnitte und Bereichsauswahl

5'UTR, CDS und 3'UTR farblich absetzen, wo bekannt. Der Nutzer kann einen
Ausschnitt wählen und nur darauf rechnen — bei Transkripten von mehreren
Kilobasen spart das viel Zeit.

### 4.3 `app/fold_target.py`

- MFE-Struktur und Ensemble des gewählten Bereichs, RNA-Parameter.
- `RNAplfold` mit einstellbarer Fensterbreite und Maximalspannweite, daraus das
  Profil der Öffnungswahrscheinlichkeit pro Position für eine gewählte
  Sondenlänge (Standard 15).
- `RNAup` für eine konkrete Stelle: aufgeschlüsselt in Öffnungsenergie des
  Ziels, Öffnungsenergie des Oligos und Hybridisierungsenergie.
- Lange Sequenzen in Abschnitten rechnen, Fortschritt melden.

### 4.4 Oberfläche: Seite „Ziel"

Oben die Sequenz in Festbreitenschrift mit Positionslineal, abgesetzten
Abschnitten und Suchfeld. Darunter **dieselbe Spurdarstellung wie in Phase 3**,
damit man sich nicht umgewöhnen muss: Positionslineal · Bogendiagramm ·
Zugänglichkeitsprofil als Flächendiagramm (hoch = offen) · Spur mit
Spaltstellen-Kandidaten (Phase 5 füllt sie). Zoom und Scrollen über die ganze
Länge, mit Übersichtsleiste. Knopf „Spaltstellen suchen".

**Test:** Transkript von etwa 500 Basen; das Zugänglichkeitsprofil muss an
bekannten Haarnadeln einbrechen.

---

## Phase 5 — DNAzym-Entwurf und Bewertung

**Ziel:** Aus der Ziel-RNA eine Rangliste von Kandidaten.

### 5.1 `app/melting.py`

- MELTING als Unterprozess, voller Pfad, `shell=False`.
- Hybridisierungstyp `dnarna` für Arm gegen Ziel-RNA.
- Oligo-Konzentration und Kationen aus den Puffereinstellungen der Kopfzeile.
- Übersetzung: LNA → `Al/Cl/Gl/Tl`, 2'-OMe → Typ `mrnarna`, Inosin → `I`. Alles
  andere über `base_parent`, als genähert markiert.
- Tm, ΔG, ΔH, ΔS und den verwendeten Parametersatz auslesen.
- Zweitmeinung mit Biopython; bei mehr als 3 °C Abweichung eine Warnung.

### 5.2 `app/scan.py` — Spaltstellen

Jede Junktion aus Purin (A, G) gefolgt von Pyrimidin (U, C) finden und
klassifizieren: **AU und GU gut**, GC mäßig, **AC schlecht** (standardmäßig
ausblenden, einblendbar lassen). Mit dem Faltungsergebnis aus Phase 4 prüfen,
ob das Purin ungepaart und das Pyrimidin gepaart ist.

### 5.3 `app/design.py` — Kandidaten bauen und bewerten

Für jede Spaltstelle: beide Arme als Komplement bauen (Standard 9+9, auch
ungleich erlaubt), Kern aus `cores.yaml` dazwischen, dann berechnen:

| Kriterium | Richtwert |
| --- | --- |
| Spaltstellentyp | AU und GU bevorzugt |
| ΔG beider Arme zusammen | unter −20 kcal/mol |
| Armbalance (Betrag der ΔG-Differenz) | möglichst klein |
| Eigenfaltung des DNAzyms | nicht stabiler als −2 kcal/mol |
| Zugänglichkeit der Spaltstelle | aus Phase 4 |
| Modifikation im Kern | Ausschlusskriterium |

Daraus eine Gesamtpunktzahl mit einstellbaren Gewichten und Schwellen.

**Die Punktzahl ist eine Rangfolge, keine Vorhersage der katalytischen Rate.**
Das beste publizierte Modell erreicht 63–73 % Trefferquote auf 38 DNAzymen.
Schreibe das in die Oberfläche, nicht nur in den Code.

### 5.4 Mehrfachumsatz

Feld „Reaktionstemperatur", Standard 37 °C. Liegt der Tm der Arme deutlich
darüber, warnen: das DNAzym bindet das Produkt zu fest für Mehrfachumsatz.
Liegt er darunter, andersherum warnen. Die Spanne grafisch als Balken mit der
Reaktionstemperatur als Markierung.

### 5.5 Modifikationen aufbringen

Ein Werkzeug, das ein Muster auf einen Kandidaten legt: „alle Arme als
Phosphorothioat", „die drei Positionen an jedem Ende als LNA", „5'-GalNAc
anhängen", „Position X durch eigenen Baustein ersetzen". Der katalytische Kern
bleibt per Voreinstellung unangetastet; Eingriffe dort verlangen eine
ausdrückliche Bestätigung. Nach dem Aufbringen alles neu rechnen und vorher
gegen nachher stellen: Masse, Tm, ΔG, Eigenfaltung, Punktzahl.

### 5.6 Oberfläche: Seite „Entwurf"

- Oben die Einstellungen: Armlängen, Spaltstellentypen, Schwellen.
- Kandidatentabelle: Position, Junktionstyp, beide Armsequenzen, ΔG je Arm,
  Balance, Tm, Eigenfaltung, Zugänglichkeit, Punktzahl. Sortierbar, filterbar,
  Ampel je Zeile.
- Darüber das Zugänglichkeitsprofil mit den Kandidaten als Markern.
- Klick auf einen Kandidaten öffnet die **Paarungsdarstellung**: Ziel-RNA oben,
  DNAzym darunter, Basenpaare als senkrechte Striche, der Kern als Schleife,
  die Spaltstelle mit einem Pfeil, Modifikationen in ihren Farben. Das ist die
  wichtigste Abbildung der Seite.
- Knopf „Als Oligo übernehmen". Export als CSV und SVG.

**Test:** Ein Transkript mit einer bekannten guten Spaltstelle — sie muss weit
oben in der Rangliste stehen.

---

## Phase 6 — Geometrie und 3D

**Ziel:** Räumlich einordnen, wo die Modifikationen sitzen.

### 6.1 `app/pdb.py` — Referenzstrukturen

Strukturen von der RCSB-PDB über ihre Kennung laden, lokal in
`data/structures/` ablegen. `data/references.yaml` mit **8E9A** für das 10-23
als Voreinstellung, je Eintrag Kennung, Beschreibung, Methode, Auflösung,
Literatur. Ketten erkennen und zuordnen: DNAzym-Strang und RNA-Substrat.

### 6.2 `app/model3d.py` — Modell bauen

Die Sequenz des gewählten Kandidaten auf die Referenzstruktur fädeln: gleiche
Position, gleiche Rückgratkoordinaten, ausgetauschte Base. Längenunterschiede
in den Armen als ideale Hybridhelix verlängern oder kürzen. Modifizierte
Bausteine über das SMILES austauschen, ohne die Rückgratkoordinaten
anzutasten. Ausgabe als PDB.

**In der Oberfläche deutlich schreiben:** Das ist ein Modell. Die Koordinaten
stammen aus der Referenz, nur die Sequenz ist deine.

### 6.3 `app/geometry.py` — messen

- **In-line-Winkel** an der Spaltstelle: 2'-O ··· P ··· O5'. Werte nahe 180°
  sind günstig. Winkel und beide Abstände ausgeben.
- Abstand jeder modifizierten Position zur Spaltstelle, in Å und in Nukleotiden.
- Abstand jeder modifizierten Position zum katalytischen Kern.
- Falls Metallionen in der Referenz enthalten sind: Abstände dorthin. Eine
  Modifikation nahe einer Ionenbindungsstelle ist ein Warnsignal.
- Allgemeines Messwerkzeug für Abstand und Winkel zwischen ausgewählten Atomen.

### 6.4 Darstellung mit 3Dmol.js

Cartoon für das Rückgrat, Stick für ausgewählte Reste. Einfärbung umschaltbar:
nach Kette, nach Bauteil (Arm / Kern / Substrat) oder **nach Modifikationstyp
mit denselben Farben wie die Sequenzkarte** — gleiche Sprache in 2D und 3D.
Spaltstelle immer markiert und beschriftet, modifizierte Positionen
hervorgehoben. Knopf „Auf Spaltstelle zentrieren".

**Kopplung mit der Sequenzkarte:** Klick auf eine Position in der Karte hebt sie
im 3D-Fenster hervor und umgekehrt. Das ist der eigentliche Gewinn der Phase.

### 6.5 Brücke zu ORCA (optional)

Fragment herausschneiden (Basenpaar, Stapel oder Spaltstellenumgebung),
abgeschnittene Bindungen mit Wasserstoff absättigen, Zucker optional durch
Methyl ersetzen. ORCA-Eingabedatei schreiben, mit wählbarem Zweck:
Geometrieoptimierung (`r2SCAN-3c`), Wechselwirkungsenergie (`DLPNO-CCSD(T)` mit
Counterpoise-Korrektur) oder elektrostatisches Potential. **Nichts selbst
rechnen** — diese Phase bereitet nur vor. Atomzahl anzeigen mit dem Hinweis,
dass unter etwa 300 Atomen Quantenchemie sinnvoll ist.

### 6.6 Gesamtbericht

Knopf „Bericht erzeugen", der für den aktiven Kandidaten alles zusammenfasst:
Sequenz mit Modifikationen, Masse und MS-Ladungsleiter, Tm und ΔG der Arme,
Eigenfaltung, Zugänglichkeit der Spaltstelle, Befundliste, Punktzahl,
Sequenzkarte als Bild, Paarungsdarstellung und 3D-Ansicht. Ausgabe als HTML und
PDF, mit Datum und allen verwendeten Einstellungen im Fußbereich — damit ist
die Rechnung reproduzierbar und das Blatt wandert ins Laborbuch.

**Test:** 8E9A laden, einen Kandidaten darauf fädeln, In-line-Winkel und
Abstände auf Plausibilität prüfen.
