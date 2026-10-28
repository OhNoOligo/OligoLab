# Erste Schritte

Eine Stunde, fünf Stationen. Jede endet mit Zahlen, die du nachprüfen kannst
— bei der ersten sogar gegen dein eigenes Excel.

Gestartet wird mit `start.bat` (Windows) oder `./start.sh`; der Browser geht
dann von selbst auf `http://127.0.0.1:8000` auf.

> **Das Fragezeichen.** Neben jedem Feld und jeder Ergebniszahl steht ein
> kleines `?`. Ein Klick erklärt, was die Zahl bedeutet und wie sie
> zustande kommt. Das ist der schnellste Weg, das Programm kennenzulernen —
> schneller als diese Datei.

---

## 1 · Der Massenrechner (10 Minuten)

Das ist der Teil, den du schon hast: er bildet dein Excel nach. Wenn er
stimmt, stimmt die Grundlage.

**Einfügen** (Bereich **Steckbrief**, Feld oben):

```
TTG GGG TAA GGC TAG CTA CAA CGA GGT GCA TGT
```

Leerzeichen dürfen drin bleiben. Das ist ein 10-23-DNAzym: Arm 9 + Kern 15 +
Arm 9 = 33 Bausteine.

**Was dastehen muss:**

| Größe | Wert |
| --- | --- |
| vollständig entschützt | 10 241,26 |
| + DMT | 10 543,60 |
| + 3'-Phosphat | 10 303,22 |
| geschützt, DMT off | 13 821,16 |
| geschützt, ohne CE | 12 124,20 |
| ε₂₆₀ | 325 400 L·mol⁻¹·cm⁻¹ |

Der Synthesizer-Verbrauch bei 0,12 mL je Kupplung:

```
A   8 Kupplungen   41,2 mg
C   5 Kupplungen   23,2 mg
G  12 Kupplungen   60,5 mg
T   8 Kupplungen   35,8 mg
Summe 160,6 mg · mit 10 % Reserve 176,6 mg
```

**Vergleich mit deinem Excel.** Weicht etwas ab, liegt es an einer Konstante,
und die siehst du im Bereich **Bausteine** — geänderte Werte sind dort
farblich hervorgehoben.

**Woran du dich gewöhnen solltest:** hinter jeder Zahl steht ein kleines
Zeichen für ihre Verlässlichkeit — `●` exakt, `◐` Parameter vorhanden,
`○` genähert über das natürliche Analogon. Bei modifizierten Oligos ist das
die wichtigste Information auf dem Schirm.

---

## 2 · Der Strang (10 Minuten)

Bereich **Strang**, Strg+3.

Dieselbe Sequenz zeigt sich jetzt als Karte: Lineal, Bausteine, Bauteile
(Arm 1–9, Kern 10–24, Arm 25–33), Faltung als Bogen, Befunde.

**Was dastehen muss:** Faltung −0,5 kcal/mol, dazu zwei Befunde —
ein Selbstdimer mit −8,4 kcal/mol (Warnung) und „4× G hintereinander" an
Position 3–6 (Hinweis).

**Jetzt der lehrreiche Teil.** Setz eine LNA mitten in den katalytischen
Kern — Position 17:

```
TTGGGGTAAGGCTAGC[LNA-T]ACAACGAGGTGCATGT
```

Sofort erscheint ein **kritischer** Befund:

> Modifikation im katalytischen Kern: LNA (verbrückte Nukleinsäure)
> Position 17 liegt im Kern 10-23 und ist im Kern nachweislich nicht erprobt.

Genau dafür ist das Programm da. Der Kern wird nie stillschweigend
verändert.

Probier auch die Schreibweisen aus: `*` zwischen zwei Zeichen setzt ein
Phosphorothioat an genau diese Bindung (`T*T*G`), `/5GalNAc/` am Anfang
hängt ein Konjugat an.

---

## 3 · Die Ziel-RNA (10 Minuten)

Bereich **Ziel**, Strg+1.

Nimm die mitgelieferte Datei `beispiele/demo-ziel.fasta` — **konstruiert,
nicht aus einer Datenbank.** Das ist Absicht: bei diesem Ziel steht die
richtige Antwort vorher fest.

Entweder hochladen oder den Inhalt einfügen:

```
GGGCGCCCGGAAACCGGGCGCCCAAAAAAAAACACCACACCACACCAACACCACAGUCCACACCAACACCACACCACACAAAAAAAAAAGGGCGCCCGGAAACCGGGCGCCC
```

112 Basen. Aufbau: zwei stabile Haarnadeln außen, dazwischen ein offener
Abschnitt, und genau in der Mitte — Position 56/57 — die einzige
**GU**-Junktion des ganzen Strangs.

**Was dastehen muss:** das Zugänglichkeitsprofil liegt im offenen Teil hoch
und bricht an den beiden Haarnadeln ein. Genau dort will man nicht
schneiden, und genau das soll man sehen.

**Für echte Arbeit:** über „Abrufen" ein Gensymbol bei Ensembl eingeben und
aus der Liste das Transkript wählen. Das braucht einmal Netz; danach liegt
es im Zwischenspeicher.

---

## 4 · Der Entwurf (15 Minuten)

Bereich **Entwurf**, Strg+2. Das ist das Herzstück.

„Kandidaten suchen" drücken. Dauert ein paar Sekunden.

**Was dastehen muss:**

```
Junktionen: 1× GU, 8× GC, 19× AC (ausgeblendet)

Rang 1   56/57   GU (gut)      0,751   ● gut
Rang 2   18/19   GC (mäßig)    0,567   ▲ mittel
Rang 3   20/21   GC (mäßig)    0,467   ▲ mittel
```

Der beste Kandidat: `TGGTGTGGAGGCTAGCTACAACGACTGTGGTGT`, ΣΔG −17,0 kcal/mol,
Tm 41,6 und 32,3 °C.

**Was du dir ansehen solltest:**

* **Die 19 ausgeblendeten AC-Junktionen.** Sie sind nicht verschwunden,
  sondern gezählt — ein Haken blendet sie ein. AC schneidet oft gar nicht,
  aber wenn nichts Besseres da ist, will man sie sehen.
* **Die Paarungsdarstellung** unter der Tabelle. Ziel-RNA oben in 5'→3', das
  DNAzym darunter *gegenläufig*, Basenpaare als senkrechte Striche, der Kern
  als Schleife über der Schnittstelle. Das ist die wichtigste Abbildung des
  Programms — an ihr sieht man sofort, ob ein Entwurf sitzt.
* **Die sechs Kriterien** links daneben, jedes einzeln mit Rohwert, Punktwert
  und Gewicht. Fehlt ein Wert, wird das Kriterium weggelassen und nicht als
  Null gewertet.
* **„Modifikation aufbringen"** rechts: wähl „Die äußersten Positionen jedes
  Endes als LNA" und drück „aufbringen". Die Vorher-Nachher-Tabelle zeigt
  +72 g/mol — und beim Tm **„unverändert"**, mit der Erklärung darunter: die
  Nearest-Neighbor-Tabelle kennt LNA nicht. Das Modell *sieht* die
  Modifikation nicht; sie bewirkt trotzdem etwas. Diesen Unterschied muss
  man im Kopf behalten.
* **„Als Oligo übernehmen"** schiebt den Kandidaten in den Steckbrief —
  dann kannst du bei Station 1 weitermachen und seine Masse rechnen.

Der Hinweis über der Tabelle ist keine Floskel: die Punktzahl **ordnet**,
sie sagt keine Rate voraus.

---

## 5 · Geometrie und 3D (15 Minuten)

Bereich **3D**, Strg+5. Braucht eine Referenzstruktur.

Oben „Struktur: 8E9A" wählen und **„holen"** drücken — das lädt sie einmalig
von der RCSB-PDB. Ohne Netz: eine eigene `.pdb` oder `.cif` über „Datei …"
einlegen.

Dann „Modell bauen". Was du bekommst:

* **Das Modell** — und darüber den Satz, dass es eines ist: die Koordinaten
  stammen aus der Referenz, nur die Sequenz ist deine.
* **Die Herkunft jeder Position**: aus der Referenz übernommen, Ringgerüst,
  nur Zucker, aus SMILES gebaut, ideal. Eine Base wird nie geraten.
* **Den In-line-Winkel** 2'-O ··· P ··· O5' an der Spaltstelle. Nahe 180°
  kann die Umesterung ablaufen, quer dazu nicht.
* **Die Kopplung**: ein Klick auf eine Position in der Sequenzkarte holt sie
  im Modell heran — und umgekehrt.

**Der eigene Baustein.** Im Bereich **Bausteine** einen anlegen, mit dem
SMILES des *ganzen Nukleosids*. Dann steht er als `[Kürzel]` in der Sequenz
und wird im Modell wirklich gebaut statt übertragen. Siehe README,
Abschnitt „Einen eigenen Baustein einbauen".

---

## Was du dabei über die Grenzen lernst

Drei Dinge, die das Programm **nicht** kann und auch nicht vorgibt zu können:

1. **Kein Modell kennt deine Modifikationen.** Tm, ΔG und Faltung rechnen
   über das natürliche Analogon. Für unmodifizierte Entwürfe sind die Zahlen
   belastbar; für modifizierte ist es die Masse.
2. **Die Punktzahl ist nicht geeicht.** Sie ordnet Kandidaten, sie sagt
   keine Spaltrate voraus.
3. **Das 3D-Modell ist eine Fädelung.** Es zeigt, *wo* eine Modifikation
   sitzt — nicht, wie sie die Struktur verändert.

Darum trägt jede Zahl ihre Verlässlichkeit mit. Das ist keine Zierde,
sondern die eigentliche Botschaft des Programms.
