# Beispiele

## `demo-ziel.fasta`

**Konstruiert, nicht aus einer Datenbank.** Das ist Absicht: bei diesem Ziel
steht die richtige Antwort vorher fest, und man kann prüfen, ob OligoLab sie
findet.

Aufbau, 112 Basen:

| Abschnitt | Was es ist |
| --- | --- |
| 1–23 und 90–112 | zwei gleiche Haarnadeln, stabil gepaart |
| 24–31 und 82–89 | A-Strecken als Abstandhalter |
| 32–55 und 58–81 | offene, C-reiche Abschnitte |
| **56/57** | die einzige **GU**-Junktion im ganzen Strang |

Was OligoLab daraus machen muss:

* **eine** GU-Junktion, acht GC, neunzehn AC (ausgeblendet)
* Rang 1: Position 56/57, Punktzahl 0,75, **grüne Ampel**
* der Strang dazu: `TGGTGTGGAGGCTAGCTACAACGACTGTGGTGT`
* ΣΔG −17,0 kcal/mol, Tm 41,6 und 32,3 °C, Eigenfaltung −1,2 kcal/mol
* im Zugänglichkeitsprofil: hoch im offenen Teil, eingebrochen an den
  Haarnadeln

Weicht etwas davon ab, stimmt etwas nicht — entweder an den Einstellungen
oder am Programm.

## Für echte Arbeit

Eine echte Ziel-RNA holt man sich im Bereich **Ziel** über „Abrufen": ein
Gensymbol bei Ensembl eingeben, aus der Liste das gewünschte Transkript
wählen. Das braucht einmal Netz; danach liegt die Sequenz im
Zwischenspeicher und OligoLab rechnet wieder offline.
