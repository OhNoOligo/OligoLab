"""Fragmente für ORCA (PHASEN.md 6.5)."""

from __future__ import annotations

import pytest

from app import orca, pdb
from tests.structures import build_pdb

DNA = "TTGGGGTAA" + "GGCTAGCTACAACGA" + "GGTGCATGT"
RNA = "ACGUACGUACGUACGUAC"


def atom(name, chain, number, x, y, z, element=None, residue="DA"):
    return pdb.Atom(
        serial=1, name=name, residue=residue, chain=chain,
        residue_number=number, x=x, y=y, z=z, element=element or name[0],
    )


def test_fragment_hat_die_gewaehlten_reste():
    atome = pdb.atoms_of(build_pdb(DNA, RNA))
    fragment = orca.cut(atome, [("B", 9), ("B", 10)])
    assert fragment.residues == ["B:10:C", "B:9:A"]
    assert fragment.atom_count > 20


def test_abgeschnittene_bindung_wird_abgesaettigt():
    """Ein Partner knapp außerhalb muss einen Wasserstoff bekommen."""
    atome = [
        atom("C3'", "A", 1, 0.0, 0.0, 0.0, "C"),
        # 1,6 Å entfernt und außerhalb der Auswahl: eine Bindung.
        atom("P", "A", 2, 1.6, 0.0, 0.0, "P"),
    ]
    fragment = orca.cut(atome, [("A", 1)])
    assert fragment.added_hydrogens == 1
    element, x, y, z = fragment.atoms[-1]
    assert element == "H"
    # Der Wasserstoff sitzt auf der Richtung der Bindung, in C–H-Abstand.
    assert (x, y, z) == pytest.approx((1.09, 0.0, 0.0))
    assert "Näherung" in (fragment.note or "")


def test_weit_entfernte_nachbarn_sind_keine_bindung():
    atome = [
        atom("C3'", "A", 1, 0.0, 0.0, 0.0, "C"),
        atom("P", "A", 2, 4.0, 0.0, 0.0, "P"),
    ]
    assert orca.cut(atome, [("A", 1)]).added_hydrogens == 0


def test_ladung_folgt_den_phosphaten():
    atome = pdb.atoms_of(build_pdb(DNA, RNA))
    fragment = orca.cut(atome, [("B", 9), ("B", 10)])
    assert fragment.charge == -2


def test_zucker_gegen_methyl_tauschen():
    atome = pdb.atoms_of(build_pdb(DNA, RNA))
    mit = orca.cut(atome, [("B", 9)])
    ohne = orca.cut(atome, [("B", 9)], replace_sugar_with_methyl=True)
    assert ohne.atom_count < mit.atom_count
    assert ohne.charge == 0, "ohne Phosphat keine Ladung"


def test_leere_auswahl():
    fragment = orca.cut([], [("A", 1)])
    assert fragment.atom_count == 0
    assert "keine Atome" in (fragment.note or "")


@pytest.mark.parametrize("zweck", list(orca.PURPOSES))
def test_jeder_zweck_schreibt_eine_eingabe(zweck):
    atome = pdb.atoms_of(build_pdb(DNA, RNA))
    text = orca.write_input(orca.cut(atome, [("B", 9)]), zweck)
    assert orca.PURPOSES[zweck]["keywords"] in text
    assert text.rstrip().endswith("*")
    assert "* xyz" in text


def test_die_eingabe_sagt_dass_hier_nichts_gerechnet_wurde():
    """PHASEN.md 6.5: nichts selbst rechnen."""
    atome = pdb.atoms_of(build_pdb(DNA, RNA))
    text = orca.write_input(orca.cut(atome, [("B", 9)]))
    assert "nichts gerechnet" in text


def test_grosse_fragmente_bekommen_eine_warnung():
    atome = pdb.atoms_of(build_pdb(DNA, RNA))
    alle = [("A", n) for n in range(1, len(DNA) + 1)]
    fragment = orca.cut(atome, alle)
    assert fragment.sensible is False
    assert "ACHTUNG" in orca.write_input(fragment)
    assert str(orca.SENSIBLE_ATOM_COUNT) in fragment.as_dict()["size_hint"]


def test_unbekannter_zweck():
    with pytest.raises(ValueError, match="Unbekannter Zweck"):
        orca.write_input(orca.Fragment(), "irgendwas")  # type: ignore[arg-type]
