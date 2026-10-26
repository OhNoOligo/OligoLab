"""Die Excel-Rechnung (PHASEN.md 1.3).

Die Tabelle aus CLAUDE.md ist der Regressionstest des ganzen Projekts.
Bricht hier etwas, stimmt das Programm nicht mehr mit dem Excel ueberein —
und dann ist das Programm falsch, nicht das Excel (CLAUDE.md, Regel 2).
"""

from __future__ import annotations

import pytest

from app import mass
from app.notation import parse

from .conftest import REFERENCE_MASSES, REFERENCE_SEQUENCE


@pytest.fixture
def ergebnis(registry):
    return mass.compute(parse(REFERENCE_SEQUENCE, registry), registry)


@pytest.mark.parametrize("schluessel,sollwert", sorted(REFERENCE_MASSES.items()))
def test_sollmassen_aus_claude_md(ergebnis, schluessel, sollwert):
    """Die fuenf Sollwerte, auf 0,01 Da."""
    gemessen = getattr(ergebnis, schluessel).rounded(2)
    assert gemessen == pytest.approx(sollwert, abs=0.005), (
        f"{schluessel}: {gemessen} statt {sollwert}"
    )


def test_basis_ist_die_summe_der_restmassen(ergebnis):
    """Basis = Σ Restmassen, und sie ist gleich `+ 3'-Phosphat`."""
    bd = ergebnis.breakdown
    assert bd.residues == pytest.approx(10303.22, abs=0.005)
    assert bd.monomer_modifications == 0.0
    assert bd.linkage_modifications == 0.0
    assert ergebnis.plus_3_phosphate.value == pytest.approx(bd.basis, abs=1e-9)


def test_basenzaehlung_und_laenge(ergebnis):
    bd = ergebnis.breakdown
    assert (bd.length, bd.n_a, bd.n_c, bd.n_g) == (33, 8, 5, 12)


def test_schutzgruppenterme(ergebnis):
    """n_A·104,03 + n_G·70,05 + n_C·42,02 und 53,03·(L−1)."""
    bd = ergebnis.breakdown
    assert bd.protecting_base == pytest.approx(
        8 * 104.03 + 12 * 70.05 + 5 * 42.02, abs=1e-9
    )
    assert bd.protecting_cyanoethyl == pytest.approx(53.03 * 32, abs=1e-9)


def test_differenz_der_geschuetzten_formen(ergebnis):
    """`geschützt, DMT off` minus `geschützt, ohne CE` ist genau 53,03·(L−1)."""
    differenz = (
        ergebnis.protected_dmt_off.value - ergebnis.protected_ce.value
    )
    assert differenz == pytest.approx(53.03 * 32, abs=1e-9)


def test_dmt_term(ergebnis):
    differenz = ergebnis.plus_dmt.value - ergebnis.fully_deprotected.value
    assert differenz == pytest.approx(302.34, abs=1e-9)


def test_phosphorothioat_bringt_16_da_je_bindung(registry):
    """Thioat ist +16 je Bindung, nicht je Baustein."""
    ohne = mass.compute(parse("ACGTA", registry), registry)
    mit = mass.compute(parse("A*C*G*T*A", registry), registry)
    differenz = mit.plus_3_phosphate.value - ohne.plus_3_phosphate.value
    assert differenz == pytest.approx(4 * 16.0, abs=1e-9)


def test_modifikation_am_baustein_wird_addiert(registry):
    """`[LNA-T]` ist T + 12,00."""
    ohne = mass.compute(parse("ACTGA", registry), registry)
    mit = mass.compute(parse("AC[LNA-T]GA", registry), registry)
    differenz = mit.plus_3_phosphate.value - ohne.plus_3_phosphate.value
    assert differenz == pytest.approx(12.0, abs=1e-9)


def test_modifizierter_baustein_behaelt_seine_schutzgruppe(registry):
    """Ein LNA-T zaehlt weiter als T — also keine Basenschutzgruppe."""
    ohne = mass.compute(parse("ACTGA", registry), registry)
    mit = mass.compute(parse("AC[LNA-T]GA", registry), registry)
    assert mit.breakdown.protecting_base == ohne.breakdown.protecting_base
    assert mit.breakdown.n_a == ohne.breakdown.n_a == 2


def test_konjugat_zaehlt_nicht_zur_basenzahl(registry):
    """Ein Konjugat erhoeht L nicht und bekommt keine Schutzgruppe."""
    ohne = mass.compute(parse("ACGT", registry), registry)
    mit = mass.compute(parse("/6-FAM/ACGT", registry), registry)
    assert mit.breakdown.length == ohne.breakdown.length == 4
    assert mit.breakdown.protecting_cyanoethyl == ohne.breakdown.protecting_cyanoethyl
    differenz = mit.plus_3_phosphate.value - ohne.plus_3_phosphate.value
    assert differenz == pytest.approx(537.46, abs=1e-9)


def test_fehlende_masse_ergibt_none_und_nennt_den_eintrag(registry):
    """Nie eine 0 einsetzen, wenn eine Masse fehlt.

    Das GalNAc-Konjugat hat bewusst keine Masse hinterlegt: sie haengt am
    Linker und stand nicht im Excel.
    """
    ergebnis = mass.compute(parse("/5GalNAc/ACGT", registry), registry)
    assert ergebnis.fully_deprotected.value is None
    assert ergebnis.fully_deprotected.reliability.value == "nicht hinterlegt"
    assert "5GalNAc" in ergebnis.fully_deprotected.note
    assert any("5GalNAc" in eintrag for eintrag in ergebnis.breakdown.missing)


def test_jede_masse_traegt_methode_und_kennzeichen(ergebnis):
    """CLAUDE.md, Regel 3 — keine nackte Zahl."""
    for schluessel, _ in mass.MassResult.ORDER:
        groesse = getattr(ergebnis, schluessel)
        assert groesse.method, f"{schluessel} ohne Methode"
        assert groesse.unit == "Da"
        assert groesse.reliability.value == "Parameter vorhanden"


def test_leeres_oligo_rechnet_nicht_mit_null(registry):
    ergebnis = mass.compute(parse("", registry), registry)
    assert ergebnis.breakdown.length == 0
    assert ergebnis.fully_deprotected.value is None
