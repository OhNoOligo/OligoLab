"""Beladung fuer PAGE und LC-MS (PHASEN.md 1.6)."""

from __future__ import annotations

import pytest

from app import loading


def test_stammkonzentration():
    """50 nmol in 100 µL sind 500 µM."""
    assert loading.stock_concentration_um(50, 100).value == pytest.approx(500.0)


def test_page_rechnung():
    """V(Oligo) = n / c · 2, V(Wasser) = 10 − V(Oligo), dazu 10 µL Puffer."""
    rezept = loading.page(n_loading_pmol=500, n_stock_nmol=50, v_stock_ul=100)
    assert rezept.oligo_ul.value == pytest.approx(2.0)
    assert rezept.water_ul.value == pytest.approx(8.0)
    assert rezept.buffer_ul.value == pytest.approx(10.0)
    assert rezept.total_ul == pytest.approx(20.0)
    assert rezept.warnings == []


def test_page_warnt_wenn_das_oligo_nicht_hineinpasst():
    """Mehr als 10 µL Oligo gehen nicht — das wird gesagt."""
    rezept = loading.page(n_loading_pmol=5000, n_stock_nmol=5, v_stock_ul=100)
    assert rezept.water_ul.value < 0
    assert any("µL" in w for w in rezept.warnings)


def test_lcms_rechnung():
    """V(Oligo) = n / c · (V(Probe) / V(Injektion))."""
    rezept = loading.lcms(
        n_injection_pmol=100,
        n_stock_nmol=50,
        v_stock_ul=100,
        v_sample_ul=50,
        v_injection_ul=5,
    )
    assert rezept.oligo_ul.value == pytest.approx(2.0)
    assert rezept.water_ul.value == pytest.approx(48.0)
    assert rezept.buffer_ul is None
    assert rezept.total_ul == pytest.approx(50.0)


def test_warnung_wenn_zu_wenig_im_vial_bleibt():
    """Unter 4 µL Rest wird gewarnt (PHASEN.md 1.6)."""
    # 1 nmol in 5 µL = 200 µM; 400 pmol · 2 / 200 µM = 4 µL -> 1 µL Rest.
    rezept = loading.page(n_loading_pmol=400, n_stock_nmol=1, v_stock_ul=5)
    assert rezept.oligo_ul.value == pytest.approx(4.0)
    assert rezept.rest_in_vial_ul == pytest.approx(1.0)
    assert any("übrig" in w for w in rezept.warnings)


def test_warnung_wenn_das_vial_nicht_reicht():
    rezept = loading.page(n_loading_pmol=2000, n_stock_nmol=1, v_stock_ul=5)
    assert rezept.rest_in_vial_ul < 0
    assert any("nur" in w for w in rezept.warnings)


def test_kein_falscher_alarm_bei_vollem_vial():
    rezept = loading.page(n_loading_pmol=500, n_stock_nmol=50, v_stock_ul=100)
    assert rezept.rest_in_vial_ul == pytest.approx(98.0)
    assert rezept.warnings == []


def test_lcms_warnt_bei_zu_grossem_injektionsvolumen():
    rezept = loading.lcms(
        n_injection_pmol=10,
        n_stock_nmol=50,
        v_stock_ul=100,
        v_sample_ul=5,
        v_injection_ul=20,
    )
    assert any("Injektionsvolumen" in w for w in rezept.warnings)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n_loading_pmol": 100, "n_stock_nmol": 50, "v_stock_ul": 0},
        {"n_loading_pmol": 100, "n_stock_nmol": -1, "v_stock_ul": 10},
    ],
)
def test_unsinnige_eingaben_sind_fehler(kwargs):
    with pytest.raises(ValueError):
        loading.page(**kwargs)


def test_lcms_braucht_ein_injektionsvolumen():
    with pytest.raises(ValueError):
        loading.lcms(
            n_injection_pmol=100,
            n_stock_nmol=50,
            v_stock_ul=100,
            v_sample_ul=50,
            v_injection_ul=0,
        )


def test_warntexte_schreiben_deutsche_zahlen():
    """Die Warnung landet unveraendert in der Oberflaeche — dort steht
    sonst ueberall ein Dezimalkomma."""
    rezept = loading.page(n_loading_pmol=400, n_stock_nmol=1, v_stock_ul=5)
    warnung = rezept.warnings[0]
    assert "1,00 µL" in warnung
    assert "1.00" not in warnung


def test_jede_zahl_traegt_ihre_methode():
    rezept = loading.page(n_loading_pmol=500, n_stock_nmol=50, v_stock_ul=100)
    for groesse in (rezept.oligo_ul, rezept.water_ul, rezept.stock_conc_um):
        assert groesse.method
        assert groesse.unit
