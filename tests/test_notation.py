"""Die Synthi-Sprache lesen und schreiben (PHASEN.md 1.2).

Gefordert sind mindestens 12 Faelle, darunter die Beispielsequenz, ein voll
thioiertes Rueckgrat, ein `[code]`-Baustein und ein Konjugat.
"""

from __future__ import annotations

import pytest

from app.notation import (
    NotationError,
    analyse,
    parse,
    to_string,
    translate,
)

from .conftest import REFERENCE_SEQUENCE


# 1 — die Beispielsequenz aus CLAUDE.md
def test_beispielsequenz(registry):
    oligo = parse(REFERENCE_SEQUENCE, registry)
    assert oligo.length == 33
    assert oligo.code_counts() == {"A": 8, "C": 5, "G": 12, "T": 8}
    # 33 Bausteine haben 32 Bindungen, alle unmodifiziert.
    assert len(oligo.linkages) == 32
    assert oligo.phosphorothioate_count() == 0


# 2 — Leerzeichen, Tabulatoren und Zeilenumbrueche werden ignoriert
def test_whitespace_wird_ignoriert(registry):
    gedraengt = parse("ACGT", registry)
    verteilt = parse("  A C\tG\nT \r\n", registry)
    assert [m.code for m in gedraengt.monomers] == [m.code for m in verteilt.monomers]
    assert verteilt.length == 4


# 3 — Kleinbuchstaben werden akzeptiert und abgebildet
def test_kleinbuchstaben(registry):
    oligo = parse("acgt oizu", registry)
    assert [m.code for m in oligo.monomers] == ["A", "C", "G", "T", "O", "I", "Z", "U"]


# 4 — alle zehn Bausteine des Excel sind bekannt
def test_alle_bausteine(registry):
    oligo = parse("ACGTOIZUEL", registry)
    assert [m.code for m in oligo.monomers] == list("ACGTOIZUEL")
    assert oligo.length == 10


# 5 — voll thioiertes Rueckgrat
def test_voll_thioiertes_rueckgrat(registry):
    oligo = parse("A*C*G*T*A", registry)
    assert oligo.length == 5
    assert oligo.phosphorothioate_count() == 4
    assert all(l.kind == "phosphorothioate" for l in oligo.linkages)


# 6 — ein einzelnes Phosphorothioat sitzt an der richtigen Bindung
def test_einzelnes_phosphorothioat(registry):
    oligo = parse("AC*GT", registry)
    thioiert = [l.position for l in oligo.linkages if l.kind == "phosphorothioate"]
    # `*` stand zwischen dem zweiten und dritten Baustein.
    assert thioiert == [2]
    assert oligo.phosphorothioate_count() == 1


# 7 — ein `[code]`-Baustein
def test_bracket_baustein(registry):
    oligo = parse("AC[LNA-T]GA", registry)
    assert oligo.length == 5
    modifiziert = oligo.monomers[2]
    assert modifiziert.position == 3
    assert modifiziert.spec.code == "T"
    assert [m.code for m in modifiziert.modifications] == ["LNA"]
    # Das natuerliche Analogon bleibt T, darum zaehlt es als T.
    assert modifiziert.base_parent == "T"
    assert oligo.base_counts() == {"A": 2, "C": 1, "T": 1, "G": 1}


# 8 — ein Konjugat am 5'-Ende
def test_konjugat_am_5_ende(registry):
    oligo = parse("/5GalNAc/ACGT", registry)
    assert oligo.length == 4, "Ein Konjugat zaehlt nicht zur Basenzahl."
    assert len(oligo.conjugates) == 1
    assert oligo.conjugates[0].code == "5GalNAc"
    assert oligo.conjugates[0].attach == "5prime"


# 9 — ein Konjugat am 3'-Ende
def test_konjugat_am_3_ende(registry):
    oligo = parse("ACGT/6-FAM/", registry)
    assert oligo.length == 4
    assert oligo.conjugates[0].attach == "3prime"


# 10 — unbekanntes Zeichen ist ein Fehler MIT Position (CLAUDE.md, Regel 5)
def test_unbekanntes_zeichen_mit_position(registry):
    with pytest.raises(NotationError) as fehler:
        parse("ACGX T", registry)
    problem = fehler.value.problem
    assert problem.position == 4, "Position ist 1-basiert und zaehlt die Eingabe."
    assert problem.text == "X"
    assert "X" in str(fehler.value)


# 11 — `analyse` sammelt ALLE Befunde, damit die Oberflaeche jeden markieren kann
def test_analyse_sammelt_alle_befunde(registry):
    _, probleme = analyse("ACGXTQ", registry)
    assert [(p.position, p.text) for p in probleme] == [(4, "X"), (6, "Q")]


# 12 — Hin und zurueck, mit Dreiergruppen wie im Excel
def test_roundtrip_mit_dreiergruppen(registry):
    oligo = parse(REFERENCE_SEQUENCE, registry)
    assert to_string(oligo, group=3) == REFERENCE_SEQUENCE
    assert to_string(oligo) == REFERENCE_SEQUENCE.replace(" ", "")


# 13 — Hin und zurueck mit Phosphorothioat, Bracket und Konjugat
def test_roundtrip_mit_allen_zusaetzen(registry):
    text = "/5GalNAc/A*C[LNA-T]G*T"
    oligo = parse(text, registry)
    assert to_string(oligo) == text


# 14 — Uebersetzer DNA -> Synthi-RNA und zurueck
def test_uebersetzer_hin_und_zurueck(registry):
    dna = parse("ACGT", registry)
    rna, offen = translate(dna, "rna", registry)
    assert to_string(rna) == "OIZU", "T->U, C->I, A->O, G->Z"
    assert offen == []
    zurueck, _ = translate(rna, "dna", registry)
    assert to_string(zurueck) == "ACGT"


# 15 — der Uebersetzer nennt, was er nicht uebersetzen konnte
def test_uebersetzer_nennt_offene_bausteine(registry):
    oligo = parse("ACEGT", registry)
    _, offen = translate(oligo, "rna", registry)
    assert len(offen) == 1
    assert "E" in offen[0] and "Position 3" in offen[0]


# 16 — `*` am Rand ist ein Fehler, kein stillschweigendes Ignorieren
@pytest.mark.parametrize(
    "text,erwartete_position",
    [("*ACGT", 1), ("ACGT*", 5), ("AC**GT", 4)],
)
def test_phosphorothioat_am_rand_ist_fehler(registry, text, erwartete_position):
    with pytest.raises(NotationError) as fehler:
        parse(text, registry)
    assert fehler.value.problem.position == erwartete_position


# 17 — unvollstaendige Klammer und unvollstaendiger Schraegstrich
@pytest.mark.parametrize("text", ["AC[LNA-T", "AC/5GalNAc"])
def test_unvollstaendige_klammer(registry, text):
    with pytest.raises(NotationError) as fehler:
        parse(text, registry)
    assert fehler.value.problem.position == 3


# 18 — ein unbekannter Baustein in Klammern nennt den Namen
def test_unbekannter_bracket_baustein(registry):
    with pytest.raises(NotationError) as fehler:
        parse("AC[GIBTESNICHT]GT", registry)
    assert "GIBTESNICHT" in fehler.value.problem.message


# 19 — die Position zaehlt von 5' nach 3' und beginnt bei 1
def test_positionen_sind_eins_basiert(registry):
    oligo = parse("ACGT", registry)
    assert [m.position for m in oligo.monomers] == [1, 2, 3, 4]


# 20 — die leere Sequenz ist kein Fehler, nur leer
def test_leere_sequenz(registry):
    oligo = parse("   ", registry)
    assert oligo.length == 0
    assert oligo.linkages == []
