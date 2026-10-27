"""Faltung mit ViennaRNA und DNA-Parametern (PHASEN.md 3.2)."""

from __future__ import annotations

import pytest

from app import fold
from app.notation import parse

from .conftest import REFERENCE_SEQUENCE

# Eine Sequenz, die zwangslaeufig eine Haarnadel bildet: neun Basenpaare um
# eine Schleife aus vier T.
HAIRPIN = "GGGGGCCCCTTTTGGGGCCCCC"

pytestmark = pytest.mark.skipif(
    not fold.VIENNA_AVAILABLE, reason="ViennaRNA ist nicht installiert"
)


def test_dna_parameter_aendern_das_ergebnis():
    """Der Unterschied ist keine Feinheit.

    Dieselbe Haarnadel liegt mit RNA-Parametern bei rund -23 kcal/mol und mit
    DNA-Parametern bei rund -12. Daran haengt, ob sie als kritisch gilt.
    """
    import RNA

    mit_rna = RNA.fold_compound(HAIRPIN).mfe()[1]
    with fold.dna_parameters():
        mit_dna = RNA.fold_compound(HAIRPIN).mfe()[1]

    assert mit_rna == pytest.approx(-23.0, abs=1.0)
    assert mit_dna == pytest.approx(-12.3, abs=1.0)
    assert mit_dna > mit_rna, "DNA muss weniger stabil sein als RNA"


def test_parametersatz_wird_wiederhergestellt():
    """Sonst faltet Phase 4 ihre Ziel-RNA mit DNA-Parametern.

    Das waere ein Fehler, den niemand bemerkt, weil die Zahlen plausibel
    aussehen.
    """
    import RNA

    vorher = RNA.fold_compound(HAIRPIN).mfe()[1]
    with fold.dna_parameters():
        pass
    assert RNA.fold_compound(HAIRPIN).mfe()[1] == pytest.approx(vorher, abs=1e-6)


def test_parametersatz_auch_nach_einem_fehler_wiederhergestellt():
    import RNA

    vorher = RNA.fold_compound(HAIRPIN).mfe()[1]
    with pytest.raises(RuntimeError):
        with fold.dna_parameters():
            raise RuntimeError("absichtlich")
    assert RNA.fold_compound(HAIRPIN).mfe()[1] == pytest.approx(vorher, abs=1e-6)


def test_referenzsequenz_faltet(registry):
    ergebnis = fold.compute(parse(REFERENCE_SEQUENCE, registry))
    assert ergebnis.available
    assert ergebnis.sequence_used == REFERENCE_SEQUENCE.replace(" ", "")
    assert len(ergebnis.structure) == 33
    assert set(ergebnis.structure) <= set(".()")
    assert ergebnis.mfe is not None and ergebnis.mfe.value is not None
    # Ein 10-23-DNAzym ist absichtlich wenig strukturiert.
    assert ergebnis.mfe.value > -5.0
    assert ergebnis.mfe.reliability.value == "Parameter vorhanden"


def test_ensemble_ist_nie_hoeher_als_das_minimum(registry):
    ergebnis = fold.compute(parse(HAIRPIN, registry))
    assert ergebnis.ensemble_energy is not None
    assert ergebnis.ensemble_energy.value <= ergebnis.mfe.value + 1e-6


def test_ungepaart_je_position(registry):
    """Die Schleife ist offen, der Stamm ist zu."""
    ergebnis = fold.compute(parse(HAIRPIN, registry))
    unpaired = ergebnis.unpaired
    assert len(unpaired) == len(HAIRPIN)
    assert all(0.0 <= wert <= 1.0 for wert in unpaired)
    # Positionen 10 bis 13 sind die Schleife (1-basiert).
    assert min(unpaired[9:13]) > 0.8
    # Der Stamm am 5'-Ende ist gepaart.
    assert max(unpaired[1:5]) < 0.2


def test_paarungswahrscheinlichkeiten(registry):
    ergebnis = fold.compute(parse(HAIRPIN, registry))
    paare = ergebnis.pair_probabilities
    assert paare, "es muss Paare geben"
    assert all(p["p"] >= fold.MIN_PAIR_PROBABILITY for p in paare)
    assert all(p["i"] < p["j"] for p in paare)
    # Das wahrscheinlichste Paar gehört zum Stamm.
    bestes = max(paare, key=lambda p: p["p"])
    assert bestes["p"] > 0.9


def test_haarnadel_wird_gefunden_und_bewertet(registry):
    ergebnis = fold.compute(parse(HAIRPIN, registry))
    assert len(ergebnis.hairpins) == 1
    haarnadel = ergebnis.hairpins[0]
    assert haarnadel.start == 1
    assert haarnadel.end == len(HAIRPIN)
    assert haarnadel.energy is not None
    assert haarnadel.energy < -10.0
    assert haarnadel.stem_length == 9


def test_strang_ohne_struktur_hat_keine_haarnadel(registry):
    ergebnis = fold.compute(parse("AAAAAAAAAAAAAAAA", registry))
    assert ergebnis.structure == "." * 16
    assert ergebnis.hairpins == []


def test_homodimer(registry):
    ergebnis = fold.compute(parse(HAIRPIN, registry))
    assert ergebnis.homodimer_energy is not None
    assert ergebnis.homodimer_energy.value is not None
    # Das Trennzeichen zwischen beiden Straengen setzt `fold.py` wieder ein;
    # RNAcofold liefert ein Wort doppelter Laenge ohne Grenze.
    struktur = ergebnis.homodimer_structure or ""
    assert struktur.count("&") == 1
    links, rechts = struktur.split("&")
    assert len(links) == len(rechts) == len(HAIRPIN)
    # Zwei Straenge zusammen sind stabiler als einer allein.
    assert ergebnis.homodimer_energy.value < ergebnis.mfe.value


def test_homodimer_abschaltbar(registry):
    ergebnis = fold.compute(parse(HAIRPIN, registry), with_homodimer=False)
    assert ergebnis.homodimer_energy is None


def test_modifizierter_baustein_wird_als_genaehert_gekennzeichnet(registry):
    """ViennaRNA kennt weder LNA noch 2'-OMe (CLAUDE.md, Regel 3)."""
    ergebnis = fold.compute(parse("AC[LNA-T]GTACGTACGT", registry))
    assert ergebnis.mfe.reliability.value == "genähert über natürliches Analogon"
    assert any("LNA" in eintrag for eintrag in ergebnis.approximated)
    assert ergebnis.sequence_used == "ACTGTACGTACGT"


def test_rna_baustein_wird_als_genaehert_gekennzeichnet(registry):
    """Ein RNA-Baustein mit DNA-Parametern gerechnet ist eine Näherung."""
    ergebnis = fold.compute(parse("ACZTACGTACGT", registry))
    assert ergebnis.mfe.reliability.value == "genähert über natürliches Analogon"
    assert any("RNA-Baustein" in eintrag for eintrag in ergebnis.approximated)


def test_baustein_ohne_analogon_faltet_als_n(registry):
    """Ein Baustein, von dem wir nichts wissen, darf keine Struktur vortäuschen."""
    ergebnis = fold.compute(parse("ACEGTACGTACGT", registry))
    assert ergebnis.available
    assert ergebnis.sequence_used == "ACNGTACGTACGT"
    assert any("kein natürliches Analogon" in e for e in ergebnis.approximated)
    # Position 3 ist N und darf in keinem Paar vorkommen.
    assert all(p["i"] != 3 and p["j"] != 3 for p in ergebnis.pair_probabilities)


def test_leerer_strang(registry):
    ergebnis = fold.compute(parse("", registry))
    assert ergebnis.available is False
    assert ergebnis.note


# ------------------------------------------------------- Klammern und Paare


def test_paare_aus_der_klammerstruktur():
    paare = fold.pairs_from_structure("((..))")
    assert paare == {1: 6, 2: 5, 5: 2, 6: 1}
    assert fold.pairs_from_structure("......") == {}


def test_unbalancierte_klammern_stuerzen_nicht_ab():
    """Kommt von ViennaRNA zwar nicht, aber die Funktion ist öffentlich."""
    assert fold.pairs_from_structure(")((") == {}


def test_haarnadeln_in_einer_mehrfachschleife():
    """Zwei getrennte Stamm-Schleifen werden als zwei gezählt."""
    sequenz = "GGGGAAAACCCCTTTTGGGGAAAACCCC"
    struktur = "((((....))))....((((....))))"
    haarnadeln = fold.find_hairpins(sequenz, struktur)
    assert [(h.start, h.end) for h in haarnadeln] == [(1, 12), (17, 28)]


def test_find_hairpins_haengt_nicht_am_zufaelligen_parametersatz():
    """Die Funktion ist öffentlich und muss für sich allein stimmen.

    Ohne eigene Absicherung käme dieselbe Haarnadel einmal mit -23 und einmal
    mit -12 kcal/mol heraus, je nachdem was zuletzt geladen wurde.
    """
    import RNA

    sequenz = "AAAAGGGGGCCCCTTTTGGGGCCCCCAAAA"
    struktur = "....(((((((((....)))))))))...."

    RNA.params_load_RNA_Turner2004()
    ohne_kontext = fold.find_hairpins(sequenz, struktur)[0].energy
    with fold.dna_parameters():
        im_kontext = fold.find_hairpins(sequenz, struktur)[0].energy

    assert ohne_kontext == pytest.approx(im_kontext, abs=1e-6)
    assert ohne_kontext == pytest.approx(-12.3, abs=1.0)


def test_dna_parameters_ist_wiedereintrittsfaehig():
    """Ein verschachtelter Block darf dem äußeren nichts wegziehen."""
    import RNA

    hairpin = "GGGGGCCCCTTTTGGGGCCCCC"
    with fold.dna_parameters():
        with fold.dna_parameters():
            pass
        # Nach dem inneren Block muss DNA noch gelten.
        assert RNA.fold_compound(hairpin).mfe()[1] == pytest.approx(-12.3, abs=1.0)
    # Nach dem äußeren wieder RNA.
    assert RNA.fold_compound(hairpin).mfe()[1] == pytest.approx(-23.0, abs=1.0)


def test_trennzeichen_verschiebt_die_positionen_nicht():
    """`&` steht zwischen zwei Strängen und belegt keine Position.

    Würde es mitgezählt, säße jede Position des zweiten Strangs um eins
    verschoben — und die Duplexstruktur zeigte auf die falschen Bausteine.
    """
    paare = fold.pairs_from_structure("((..))&((..))")
    assert paare[1] == 6 and paare[2] == 5
    # Zweiter Strang: Positionen 7 bis 12, nicht 8 bis 13.
    assert paare[7] == 12 and paare[8] == 11
    assert 13 not in paare
