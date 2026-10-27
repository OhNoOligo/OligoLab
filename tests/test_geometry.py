"""Winkel und Abstände (PHASEN.md 6.3).

Geprüft wird an bekannten Maßen: eine Struktur, deren Winkel vorher
feststeht. Ein Messgerät, das man an einem unbekannten Maß prüft, prüft
man nicht.
"""

from __future__ import annotations

import pytest

from app import geometry, model3d, pdb
from tests.structures import build_pdb

KERN = "GGCTAGCTACAACGA"
DNA = "TTGGGGTAA" + KERN + "GGTGCATGT"
RNA = "ACGUACGUACGUACGUAC"


# --------------------------------------------------------- die Rechnung


def test_gerade_ist_180_grad():
    assert geometry.angle((0, 0, 0), (1, 0, 0), (2, 0, 0)) == pytest.approx(180.0)


def test_rechter_winkel():
    assert geometry.angle((0, 1, 0), (0, 0, 0), (1, 0, 0)) == pytest.approx(90.0)


def test_abstand():
    assert geometry.distance((0, 0, 0), (3, 4, 0)) == pytest.approx(5.0)


def test_zwei_atome_aufeinander_geben_keinen_winkel():
    with pytest.raises(ValueError, match="aufeinander"):
        geometry.angle((0, 0, 0), (0, 0, 0), (1, 0, 0))


def test_rundungsfehler_kippen_den_arkuskosinus_nicht():
    """Drei Punkte auf einer Linie dürfen nicht in eine Fehlermeldung laufen."""
    weit = 1e6
    assert geometry.angle((-weit, 0, 0), (0, 0, 0), (weit, 0, 0)) == pytest.approx(
        180.0
    )


# ------------------------------------------------------ In-line-Winkel


@pytest.mark.parametrize(
    "grad,bewertung",
    [(178.0, "good"), (160.0, "good"), (135.0, "warn"), (90.0, "bad")],
)
def test_in_line_winkel_wird_gemessen_und_bewertet(grad, bewertung):
    text = build_pdb(DNA, RNA, inline_residue=9, inline_angle_deg=grad)
    atome = pdb.atoms_of(text)
    ergebnis = geometry.inline_angle(atome, "B", 9)
    assert ergebnis.available is True
    assert ergebnis.angle is not None
    assert ergebnis.angle.value == pytest.approx(grad, abs=0.05)
    assert ergebnis.rating == bewertung


def test_in_line_winkel_gibt_beide_abstaende_aus():
    text = build_pdb(DNA, RNA, inline_residue=9, inline_angle_deg=180.0)
    ergebnis = geometry.inline_angle(pdb.atoms_of(text), "B", 9)
    assert ergebnis.distance_attack is not None
    assert ergebnis.distance_attack.value == pytest.approx(3.2, abs=0.01)
    assert ergebnis.distance_leaving is not None
    assert ergebnis.distance_leaving.value == pytest.approx(1.6, abs=0.01)
    assert ergebnis.atoms == ["B:9:O2'", "B:10:P", "B:10:O5'"]


def test_ohne_zwei_strich_oh_gibt_es_keinen_winkel():
    """Auf DNA gemessen gibt es keine Zahl, sondern den Grund."""
    text = build_pdb(DNA, RNA)
    ergebnis = geometry.inline_angle(pdb.atoms_of(text), "A", 5)
    assert ergebnis.available is False
    assert ergebnis.angle is None
    assert "O2'" in (ergebnis.note or "")
    assert "DNA-Rest" in (ergebnis.note or "")


def test_fehlendes_atom_wird_benannt():
    text = build_pdb(DNA, RNA)
    ergebnis = geometry.inline_angle(pdb.atoms_of(text), "B", 999)
    assert ergebnis.available is False
    assert "999" in (ergebnis.note or "")


# -------------------------------------------------------- am Modell


@pytest.fixture
def modell_und_atome(registry):
    text = build_pdb(
        DNA, RNA, inline_residue=9, inline_angle_deg=170.0,
        ions=[("MG", 1.4, 0.0, 0.3)],
    )
    struktur = pdb.parse_structure(text, "TEST")
    kandidat = "[LNA-T]TGGGGTAA" + KERN + "GGTGCATG[LNA-T]"
    modell = model3d.thread(kandidat, struktur, structure_text=text, registry=registry)
    return modell, pdb.atoms_of(modell.pdb)


def test_abstand_jeder_modifikation_zur_spaltstelle(modell_und_atome):
    modell, atome = modell_und_atome
    bericht = geometry.measure_model(modell, atome, cleavage_residue=9, core_range=(10, 24))
    assert [d.position for d in bericht.to_cleavage] == [1, 33]
    assert all(d.angstrom is not None for d in bericht.to_cleavage)
    assert all(d.modification == "LNA" for d in bericht.to_cleavage)


def test_abstand_zum_kern_in_nukleotiden_und_angstrom(modell_und_atome):
    modell, atome = modell_und_atome
    bericht = geometry.measure_model(modell, atome, cleavage_residue=9, core_range=(10, 24))
    nach_position = {d.position: d for d in bericht.to_core}
    # Position 1 liegt neun Bausteine vor dem Kern, Position 33 neun dahinter.
    assert nach_position[1].nucleotides == 9
    assert nach_position[33].nucleotides == 9
    assert nach_position[1].angstrom is not None


def test_naehe_zu_einem_ion_ist_ein_warnsignal(modell_und_atome):
    """PHASEN.md 6.3: eine Modifikation nahe einer Ionenbindungsstelle."""
    modell, atome = modell_und_atome
    bericht = geometry.measure_model(modell, atome, cleavage_residue=9, core_range=(10, 24))
    assert 1 in bericht.ion_contacts
    assert bericht.ion_contacts[1][0].residue == "MG"
    assert any("Warnsignal" in w for w in bericht.warnings)


def test_position_ausserhalb_der_referenz_hat_keinen_abstand(registry):
    text = build_pdb(DNA, RNA)
    struktur = pdb.parse_structure(text, "TEST")
    kandidat = "[LNA-A][LNA-A]ATTGGGGTAA" + KERN + "GGTGCATGT"
    modell = model3d.thread(kandidat, struktur, structure_text=text, registry=registry)
    bericht = geometry.measure_model(modell, pdb.atoms_of(modell.pdb), cleavage_residue=9)
    ohne = [d for d in bericht.to_cleavage if d.angstrom is None]
    assert ohne, "die Positionen vor der Referenz dürfen keine Zahl bekommen"
    assert "außerhalb der Referenz" in (ohne[0].note or "")


def test_ohne_modifikation_sagt_der_bericht_es(registry):
    text = build_pdb(DNA, RNA)
    struktur = pdb.parse_structure(text, "TEST")
    modell = model3d.thread(DNA, struktur, structure_text=text, registry=registry)
    bericht = geometry.measure_model(modell, pdb.atoms_of(modell.pdb), cleavage_residue=9)
    assert bericht.to_cleavage == []
    assert any("nichts einzuordnen" in w for w in bericht.warnings)


def test_ohne_angegebene_spaltstelle_wird_die_annahme_benannt(registry):
    text = build_pdb(DNA, RNA)
    struktur = pdb.parse_structure(text, "TEST")
    modell = model3d.thread(DNA, struktur, structure_text=text, registry=registry)
    bericht = geometry.measure_model(modell, pdb.atoms_of(modell.pdb))
    assert any("Annahme" in w for w in bericht.warnings)


# ------------------------------------------------------- Messwerkzeug


def test_messwerkzeug_abstand():
    text = build_pdb(DNA, RNA, inline_residue=9, inline_angle_deg=180.0)
    ergebnis = geometry.measure(pdb.atoms_of(text), ["B:9:O2'", "B:10:P"])
    assert ergebnis.kind == "abstand"
    assert ergebnis.value == pytest.approx(3.2, abs=0.01)
    assert ergebnis.unit == "Å"


def test_messwerkzeug_winkel():
    text = build_pdb(DNA, RNA, inline_residue=9, inline_angle_deg=150.0)
    ergebnis = geometry.measure(
        pdb.atoms_of(text), ["B:9:O2'", "B:10:P", "B:10:O5'"]
    )
    assert ergebnis.kind == "winkel"
    assert ergebnis.value == pytest.approx(150.0, abs=0.05)


def test_messwerkzeug_mit_unbekanntem_atom():
    text = build_pdb(DNA, RNA)
    ergebnis = geometry.measure(pdb.atoms_of(text), ["B:9:XX", "B:10:P"])
    assert ergebnis.value is None
    assert "gibt es in dieser Struktur nicht" in (ergebnis.note or "")


def test_messwerkzeug_braucht_zwei_oder_drei_atome():
    ergebnis = geometry.measure([], ["A:1:P"])
    assert ergebnis.kind == "unbrauchbar"
    assert "Zwei Atome" in (ergebnis.note or "")


def test_unbrauchbare_atomangabe():
    with pytest.raises(ValueError, match="keine Atomangabe"):
        geometry.parse_selection("A-1-P")
