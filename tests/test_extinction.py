"""eps260 und die Umrechnungen daraus (PHASEN.md 1.7)."""

from __future__ import annotations

import pytest

from app import extinction as ex, mass
from app.notation import parse

from .conftest import REFERENCE_SEQUENCE


def test_nearest_neighbor_von_hand_nachgerechnet(registry):
    """ACGT: (AC + CG + GT) − (C + G) = 59 200 − 18 900 = 40 300."""
    ergebnis = ex.compute(parse("ACGT", registry), registry)
    assert ergebnis.eps260.value == pytest.approx(40300, abs=1)
    assert ergebnis.table == "dna"
    assert ergebnis.eps260.reliability.value == "Parameter vorhanden"


def test_einzelner_baustein(registry):
    ergebnis = ex.compute(parse("A", registry), registry)
    assert ergebnis.eps260.value == pytest.approx(15400, abs=1)


def test_referenzsequenz_liegt_im_erwarteten_bereich(registry):
    """Ein 33mer DNA liegt bei ungefaehr 10 000 je Baustein."""
    ergebnis = ex.compute(parse(REFERENCE_SEQUENCE, registry), registry)
    assert ergebnis.eps260.value == pytest.approx(325400, abs=1)
    assert 250000 < ergebnis.eps260.value < 400000


def test_rna_nutzt_die_rna_tabelle(registry):
    ergebnis = ex.compute(parse("OIZU", registry), registry)
    assert ergebnis.table == "rna"
    # (AC + CG + GU) − (C + G) = 21 000 + 17 800 + 21 200 − 7 200 − 11 500
    assert ergebnis.eps260.value == pytest.approx(41300, abs=1)


def test_modifizierter_baustein_wird_als_genaehert_gekennzeichnet(registry):
    """CLAUDE.md, Regel 3: das eps260 von T gilt fuer LNA-T nur genaehert."""
    ergebnis = ex.compute(parse("AC[LNA-T]GA", registry), registry)
    assert ergebnis.eps260.value is not None
    assert ergebnis.eps260.reliability.value == "genähert über natürliches Analogon"
    assert any("LNA-T" in eintrag for eintrag in ergebnis.approximated)


def test_ohne_analogon_wird_nicht_geraten(registry):
    """E hat kein eps260 und kein natuerliches Analogon."""
    ergebnis = ex.compute(parse("ACEGT", registry), registry)
    assert ergebnis.eps260.value is None
    assert ergebnis.eps260.reliability.value == "nicht hinterlegt"
    assert any("Position 3" in eintrag for eintrag in ergebnis.missing)


def test_leeres_oligo(registry):
    ergebnis = ex.compute(parse("", registry), registry)
    assert ergebnis.eps260.value is None


# --------------------------------------------------------- Lambert-Beer


def test_absorption_und_konzentration_sind_umkehrbar():
    eps = 325400.0
    konzentration = ex.absorbance_to_concentration(0.5, eps).value
    assert konzentration == pytest.approx(0.5 / eps, abs=1e-12)
    zurueck = ex.concentration_to_absorbance(konzentration, eps).value
    assert zurueck == pytest.approx(0.5, abs=1e-9)


def test_schichtdicke_geht_ein():
    eps = 100000.0
    halbe = ex.absorbance_to_concentration(1.0, eps, path_cm=0.2).value
    assert halbe == pytest.approx(1.0 / (eps * 0.2), abs=1e-12)


@pytest.mark.parametrize("eps,weg", [(0, 1.0), (-1, 1.0), (1000, 0), (1000, -1)])
def test_unsinnige_eingaben_sind_fehler(eps, weg):
    with pytest.raises(ValueError):
        ex.absorbance_to_concentration(1.0, eps, path_cm=weg)


# ------------------------------------------------------- OD / nmol / µg


def test_od_nmol_ug_an_der_referenzsequenz(registry):
    """1 OD eines 33mer sind rund 3 nmol und rund 31 µg."""
    oligo = parse(REFERENCE_SEQUENCE, registry)
    eps = ex.compute(oligo, registry).eps260.value
    molmasse = mass.compute(oligo, registry).fully_deprotected.value

    ergebnis = ex.convert_od(eps, molmasse, od=1.0)
    assert ergebnis.nmol.value == pytest.approx(1e6 / eps, abs=1e-6)
    assert ergebnis.nmol.value == pytest.approx(3.07, abs=0.01)
    assert ergebnis.microgram.value == pytest.approx(31.47, abs=0.05)


def test_jedes_der_drei_felder_als_eingang(registry):
    """Zwei eingeben, das dritte bekommen — in jeder Richtung gleich."""
    eps, molmasse = 325400.0, 10241.26
    aus_od = ex.convert_od(eps, molmasse, od=2.0)
    aus_nmol = ex.convert_od(eps, molmasse, nmol=aus_od.nmol.value)
    aus_ug = ex.convert_od(eps, molmasse, microgram=aus_od.microgram.value)

    for ergebnis in (aus_nmol, aus_ug):
        assert ergebnis.od.value == pytest.approx(2.0, abs=1e-9)
        assert ergebnis.microgram.value == pytest.approx(
            aus_od.microgram.value, abs=1e-9
        )


def test_widerspruechliche_eingaben_werden_gemeldet():
    """Lieber eine klare Meldung als eine stillschweigend verworfene Eingabe."""
    ergebnis = ex.convert_od(325400.0, 10241.26, od=1.0, nmol=99.0)
    assert ergebnis.warning is not None
    assert "Unstimmig" in ergebnis.warning


def test_stimmige_mehrfacheingabe_meldet_nichts():
    eps, molmasse = 325400.0, 10241.26
    nur_od = ex.convert_od(eps, molmasse, od=1.0)
    beides = ex.convert_od(eps, molmasse, od=1.0, nmol=nur_od.nmol.value)
    assert beides.warning is None


def test_ohne_eingabe_ist_ein_fehler():
    with pytest.raises(ValueError):
        ex.convert_od(325400.0, 10241.26)
