"""Gegenrechnung aus der Summenformel (PHASEN.md 1.4)."""

from __future__ import annotations

import pytest

from app import mass_exact as mx
from app.notation import parse

from .conftest import REFERENCE_SEQUENCE


# ------------------------------------------------------------ Summenformeln


def test_formel_zerlegen_und_zusammensetzen():
    counts = mx.parse_formula("C10H12N5O5P")
    assert counts == {"C": 10, "H": 12, "N": 5, "O": 5, "P": 1}
    assert mx.format_formula(counts) == "C10H12N5O5P"


def test_hill_schreibweise_sortiert_richtig():
    """C, dann H, dann alles weitere alphabetisch."""
    counts = mx.parse_formula("PNaO3SH2C")
    assert mx.format_formula(counts) == "CH2NaO3PS"


@pytest.mark.parametrize("formel", ["", "c10", "C10Xx3", "10C", "C-10"])
def test_unsinnige_formel_ist_ein_fehler(formel):
    with pytest.raises(ValueError):
        mx.parse_formula(formel)


def test_massen_einzelner_elemente():
    """Gegen Tabellenwerte: Wasser und Phosphorsaeureanhydrid."""
    wasser = mx.parse_formula("H2O")
    assert mx.monoisotopic_mass(wasser) == pytest.approx(18.010565, abs=1e-5)
    assert mx.average_mass(wasser) == pytest.approx(18.0153, abs=1e-3)
    assert mx.monoisotopic_mass(mx.parse_formula("HPO3")) == pytest.approx(
        79.96633, abs=1e-4
    )


# -------------------------------------------------------------- Kettenaufbau


def test_kettenaufbau_an_tpt(registry):
    """TpT mit 5'-OH und 3'-OH wiegt monoisotopisch 546,1365 Da.

    Gegenprobe von Hand: Thymidin (242,0903) + Thymidin-3'-phosphat
    (322,0566) − H2O (18,0106) = 546,1363.
    """
    ergebnis = mx.compute(parse("TT", registry), registry=registry)
    assert ergebnis.formula == "C20H27N4O12P"
    assert ergebnis.monoisotopic.value == pytest.approx(546.1363, abs=1e-3)


def test_dreiphosphat_form_ist_um_hpo3_schwerer(registry):
    oligo = parse("TT", registry)
    ohne = mx.compute(oligo, form="fully_deprotected", registry=registry)
    mit = mx.compute(oligo, form="plus_3_phosphate", registry=registry)
    differenz = mit.monoisotopic.value - ohne.monoisotopic.value
    assert differenz == pytest.approx(79.96633, abs=1e-4)


def test_phosphorothioat_tauscht_o_gegen_s(registry):
    ohne = mx.compute(parse("TTT", registry), registry=registry)
    mit = mx.compute(parse("T*T*T", registry), registry=registry)
    assert mit.counts["S"] == 2
    assert mit.counts["O"] == ohne.counts["O"] - 2
    # S − O = 31,97207 − 15,99491 = 15,97716 je Bindung
    differenz = mit.monoisotopic.value - ohne.monoisotopic.value
    assert differenz == pytest.approx(2 * 15.97716, abs=1e-4)


def test_summenformel_der_referenzsequenz(registry):
    ergebnis = mx.compute(parse(REFERENCE_SEQUENCE, registry), registry=registry)
    assert ergebnis.formula == "C325H405N131O196P32"
    # 33 Bausteine, 32 internukleotidische Phosphate.
    assert ergebnis.counts["P"] == 32
    assert ergebnis.sodium_count == 32


def test_natriumsalz_ersetzt_protonen(registry):
    """Das Salz ist freie Saeure − n·H + n·Na, kein Natrium-Addukt."""
    ergebnis = mx.compute(parse("TTT", registry), registry=registry)
    differenz = ergebnis.monoisotopic_na.value - ergebnis.monoisotopic.value
    je_natrium = 22.9897692809 - 1.00782503207
    assert differenz == pytest.approx(2 * je_natrium, abs=1e-5)
    assert "freie Säure" in ergebnis.monoisotopic_na.method


def test_fehlende_summenformel_wird_benannt(registry):
    """E hat im Excel keine Struktur — das wird gesagt, nicht geraten."""
    ergebnis = mx.compute(parse("ACEGT", registry), registry=registry)
    assert ergebnis.monoisotopic.value is None
    assert any("Position 3" in eintrag for eintrag in ergebnis.missing_formula)


# ----------------------------------------------------------- Isotopenmuster


def test_isotopenmuster_fuenf_peaks(registry):
    ergebnis = mx.compute(parse(REFERENCE_SEQUENCE, registry), registry=registry)
    muster = ergebnis.isotopes
    assert len(muster) == 5
    # Nach Masse aufsteigend, Abstand je ein Neutron.
    massen = [p["mass"] for p in muster]
    assert massen == sorted(massen)
    for links, rechts in zip(massen, massen[1:]):
        assert rechts - links == pytest.approx(1.0, abs=0.01)
    # Genau ein Peak ist der groesste.
    assert max(p["intensity_rel"] for p in muster) == 1.0


def test_isotopenmuster_von_chlor():
    """35Cl/37Cl im Verhaeltnis 0,7578 zu 0,2422 — Probe aufs Verfahren."""
    muster = mx.isotope_pattern(mx.parse_formula("Cl2"), top=3)
    intensitaeten = {round(p["mass"]): p["intensity_rel"] for p in muster}
    # Cl2: 0,5743 / 0,3671 / 0,0587 -> relativ 1 / 0,639 / 0,102
    assert intensitaeten[70] == 1.0
    assert intensitaeten[72] == pytest.approx(0.639, abs=0.005)
    assert intensitaeten[74] == pytest.approx(0.102, abs=0.005)


# --------------------------------------------------------- ESI-Ladungsleiter


def test_ladungsleiter_bereich_und_formel():
    leiter = mx.charge_ladder(10000.0, 2, 15)
    assert [p["charge"] for p in leiter] == list(range(2, 16))
    zwei = next(p for p in leiter if p["charge"] == 2)
    assert zwei["mz"] == pytest.approx((10000.0 - 2 * 1.00794) / 2, abs=1e-3)


def test_ladungsleiter_ist_einstellbar():
    assert [p["charge"] for p in mx.charge_ladder(10000.0, 5, 7)] == [5, 6, 7]


def test_ladungsleiter_ohne_masse_ist_leer():
    assert mx.charge_ladder(None) == []


def test_ungueltiger_ladungsbereich():
    with pytest.raises(ValueError):
        mx.charge_ladder(10000.0, 5, 2)


# ------------------------------------------------- Vergleich mit dem Excel


def test_vergleich_schluesselt_je_baustein_auf(registry):
    """Eine Gesamtdifferenz sagt nur DASS etwas abweicht, nicht WO."""
    vergleich = mx.compare(parse(REFERENCE_SEQUENCE, registry), registry)
    je_code = {z["code"]: z for z in vergleich.per_code}
    assert set(je_code) == {"A", "C", "G", "T"}
    for code, zeile in je_code.items():
        assert zeile["formula"], f"{code} ohne Summenformel"
        assert zeile["delta"] is not None
        assert zeile["delta_total"] == pytest.approx(
            zeile["delta"] * zeile["count"], abs=1e-3
        )


def test_dokumentierte_abweichung_der_excel_restmassen(registry):
    """Festgehalten, was die Gegenrechnung ueber das Excel aussagt.

    A, G und T liegen je etwa 1,00 Da unter ihrer monoisotopischen Restmasse,
    also um ein Wasserstoffatom zu leicht. C dagegen stimmt mit dem
    Isotopenmittel ueberein. Das Excel mischt also zwei Konventionen und hat
    bei drei Bausteinen ein H zu wenig.

    Die Werte bleiben trotzdem verbindlich (CLAUDE.md, Regel 2). Dieser Test
    haelt den Befund fest, damit er nicht unbemerkt verschwindet — und damit
    auffaellt, falls jemand die Konstanten doch anfasst.
    """
    vergleich = mx.compare(parse(REFERENCE_SEQUENCE, registry), registry)
    je_code = {z["code"]: z for z in vergleich.per_code}

    for code in ("A", "G", "T"):
        assert je_code[code]["delta_mono"] == pytest.approx(-1.005, abs=0.01), (
            f"{code} liegt nicht mehr ein H unter der monoisotopischen Masse"
        )
    assert je_code["C"]["delta"] == pytest.approx(0.0, abs=0.01), (
        "C stimmt nicht mehr mit dem Isotopenmittel überein"
    )

    # Daraus folgt die Gesamtdifferenz von etwa +32 Da auf 33 Bausteine.
    assert vergleich.difference == pytest.approx(32.4, abs=0.5)
    assert vergleich.agrees is False
    assert "Größte Beiträge" in vergleich.message


def test_vergleich_nennt_fehlende_summenformel(registry):
    vergleich = mx.compare(parse("ACEGT", registry), registry)
    assert vergleich.difference is None
    assert vergleich.agrees is False
    assert vergleich.missing_formula
    assert "Position 3" in vergleich.message


def test_schwelle_ist_ein_halbes_dalton():
    assert mx.AGREEMENT_THRESHOLD_DA == 0.5
