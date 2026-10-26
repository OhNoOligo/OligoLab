"""Synthesizer-Verbrauch (PHASEN.md 1.5).

Die Sollwerte stehen in CLAUDE.md: bei 0,12 mL je Kupplung
A 8 -> 41,2 mg, C 5 -> 23,2 mg, G 12 -> 60,5 mg, T 8 -> 35,8 mg,
Summe 160,6 mg und mit 10 % Reserve 176,6 mg.
"""

from __future__ import annotations

import pytest

from app import synthesis
from app.notation import parse

from .conftest import (
    REFERENCE_CONSUMPTION,
    REFERENCE_CONSUMPTION_TOTAL,
    REFERENCE_CONSUMPTION_TOTAL_RESERVE,
    REFERENCE_SEQUENCE,
)


@pytest.fixture
def tabelle(registry):
    return synthesis.compute(parse(REFERENCE_SEQUENCE, registry), registry=registry)


@pytest.mark.parametrize("code", sorted(REFERENCE_CONSUMPTION))
def test_verbrauch_je_baustein(tabelle, code):
    kupplungen, masse = REFERENCE_CONSUMPTION[code]
    zeile = next(z for z in tabelle.rows if z.code == code)
    assert zeile.couplings == kupplungen
    assert round(zeile.mass_mg, 1) == pytest.approx(masse, abs=0.05)


def test_summe_und_reserve(tabelle):
    assert tabelle.total_mass_mg == pytest.approx(
        REFERENCE_CONSUMPTION_TOTAL, abs=0.05
    )
    assert tabelle.total_mass_with_reserve_mg == pytest.approx(
        REFERENCE_CONSUMPTION_TOTAL_RESERVE, abs=0.05
    )


def test_volumen_je_kupplung(tabelle):
    """Volumen = Anzahl · 0,12 mL, und die Summe passt zu 33 Kupplungen."""
    for zeile in tabelle.rows:
        assert zeile.volume_ml == pytest.approx(zeile.couplings * 0.12, abs=1e-9)
    assert tabelle.total_volume_ml == pytest.approx(33 * 0.12, abs=1e-9)


def test_hinweis_zur_reserve_steht_dabei(tabelle):
    """Der Hinweis muss sichtbar neben der Tabelle stehen (PHASEN.md 1.5)."""
    assert "10 %" in tabelle.hint


def test_kupplungsvolumen_ist_einstellbar(registry):
    doppelt = synthesis.compute(
        parse(REFERENCE_SEQUENCE, registry), coupling_volume_ml=0.24, registry=registry
    )
    assert doppelt.total_mass_mg == pytest.approx(
        2 * REFERENCE_CONSUMPTION_TOTAL, abs=0.1
    )


def test_zahl_der_synthesen_ist_ein_faktor(registry):
    drei = synthesis.compute(
        parse(REFERENCE_SEQUENCE, registry), syntheses=3, registry=registry
    )
    assert drei.total_mass_mg == pytest.approx(3 * REFERENCE_CONSUMPTION_TOTAL, abs=0.2)
    assert all(z.couplings % 3 == 0 for z in drei.rows)


def test_null_synthesen_ist_ein_fehler(registry):
    with pytest.raises(ValueError):
        synthesis.compute(parse("ACGT", registry), syntheses=0, registry=registry)


def test_gezaehlt_wird_nach_synthi_buchstabe(registry):
    """Ein rA kommt aus einer anderen Flasche als ein dA."""
    tabelle = synthesis.compute(parse("AAOO", registry), registry=registry)
    codes = {z.code: z.couplings for z in tabelle.rows}
    assert codes == {"A": 2, "O": 2}
