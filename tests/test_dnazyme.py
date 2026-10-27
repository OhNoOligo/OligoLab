"""Bauteile erkennen (PHASEN.md 3.1)."""

from __future__ import annotations

import pytest

from app.dnazyme import base_letters, detect_parts, load_cores
from app.notation import parse

from .conftest import REFERENCE_SEQUENCE

CORE_10_23 = "GGCTAGCTACAACGA"


def test_kern_10_23_ist_hinterlegt(registry):
    kerne = load_cores(registry)
    assert [k.id for k in kerne] == ["10-23"]
    kern = kerne[0]
    assert kern.sequence == CORE_10_23
    assert kern.length == 15
    assert kern.target_type == "rna"
    assert "AU" in kern.preferred_junctions
    assert kern.metal_requirement
    assert kern.quelle


def test_referenzsequenz_zerfaellt_in_arm_kern_arm(registry):
    """CLAUDE.md: Arm 9 + Kern 15 + Arm 9 = 33 Bausteine."""
    teile = detect_parts(parse(REFERENCE_SEQUENCE, registry), registry)
    assert teile.found
    assert teile.core is not None and teile.core.id == "10-23"
    assert [(p.kind, p.start, p.end) for p in teile.parts] == [
        ("arm5", 1, 9),
        ("core", 10, 24),
        ("arm3", 25, 33),
    ]
    assert [p.length for p in teile.parts] == [9, 15, 9]
    assert teile.approximated == []


def test_kern_wird_auch_mit_modifikation_erkannt(registry):
    """Über `base_parent`, nicht über den Synthi-Buchstaben.

    Würde stur auf Buchstaben verglichen, fände sich der Kern nicht mehr —
    und die wichtigste Warnung des Programms bliebe aus.
    """
    oligo = parse("TTGGGGTAAGGC[LNA-T]AGCTACAACGAGGTGCATGT", registry)
    teile = detect_parts(oligo, registry)
    assert teile.found
    assert teile.core_part is not None
    assert (teile.core_part.start, teile.core_part.end) == (10, 24)
    # Die modifizierte Position wird als genähert erkannt benannt.
    assert any("Position 13" in eintrag for eintrag in teile.approximated)
    assert teile.note and "Analogon" in teile.note


def test_rna_baustein_im_kern_wird_erkannt(registry):
    """Ein rG an Kernposition 1 trifft den DNA-Kern trotzdem."""
    oligo = parse("TTGGGGTAAZGCTAGCTACAACGAGGTGCATGT", registry)
    teile = detect_parts(oligo, registry)
    assert teile.found
    assert teile.core_part is not None
    assert teile.core_part.start == 10
    assert any("Position 10" in eintrag for eintrag in teile.approximated)


def test_kein_kern_ist_kein_fehler(registry):
    """PHASEN.md 3.1 ausdrücklich: nicht jedes Oligo ist ein DNAzym."""
    teile = detect_parts(parse("ACGTACGTACGT", registry), registry)
    assert teile.found is False
    assert teile.core is None
    assert teile.parts == []
    assert teile.note and "Kein katalytischer Kern" in teile.note


def test_kern_ohne_arme(registry):
    """Nur der Kern: dann gibt es keine Armabschnitte."""
    teile = detect_parts(parse(CORE_10_23, registry), registry)
    assert teile.found
    assert [p.kind for p in teile.parts] == ["core"]


def test_kern_nur_mit_funfprime_arm(registry):
    teile = detect_parts(parse("ACGTA" + CORE_10_23, registry), registry)
    assert [p.kind for p in teile.parts] == ["arm5", "core"]
    assert teile.arm3 is None
    assert teile.arm5 is not None and teile.arm5.length == 5


def test_baustein_ohne_analogon_kann_nie_im_kern_liegen(registry):
    """E hat kein natürliches Analogon — dort kann kein Kern passen."""
    # E mitten in der Kernsequenz.
    oligo = parse("TTGGGGTAAGGCTAGCTAICAACGAGGTGCATGT".replace("I", "E"), registry)
    teile = detect_parts(oligo, registry)
    assert teile.found is False
    assert teile.note and "kein natürliches Analogon" in teile.note


def test_leerer_strang(registry):
    teile = detect_parts(parse("", registry), registry)
    assert teile.found is False
    assert teile.note


def test_base_letters_setzt_u_und_t_gleich(registry):
    """Für die Kernsuche und die Faltung ist U dasselbe wie T."""
    assert base_letters(parse("ACGT", registry)) == ["A", "C", "G", "T"]
    assert base_letters(parse("OIZU", registry)) == ["A", "C", "G", "T"]
    assert base_letters(parse("ACEGT", registry)) == ["A", "C", None, "G", "T"]


def test_part_hilfsfunktionen(registry):
    teile = detect_parts(parse(REFERENCE_SEQUENCE, registry), registry)
    kern = teile.core_part
    assert kern is not None
    assert kern.contains(10) and kern.contains(24)
    assert not kern.contains(9) and not kern.contains(25)
    assert kern.overlaps(1, 10)
    assert kern.overlaps(24, 33)
    assert not kern.overlaps(1, 9)
    assert teile.part_at(5) is teile.arm5
    assert teile.part_at(30) is teile.arm3


@pytest.mark.parametrize("position,erwartet", [(1, "arm5"), (10, "core"), (33, "arm3")])
def test_position_dem_richtigen_bauteil_zugeordnet(registry, position, erwartet):
    teile = detect_parts(parse(REFERENCE_SEQUENCE, registry), registry)
    teil = teile.part_at(position)
    assert teil is not None and teil.kind == erwartet
