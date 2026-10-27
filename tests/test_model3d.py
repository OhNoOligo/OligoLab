"""Das Modell bauen (PHASEN.md 6.2)."""

from __future__ import annotations

import pytest

from app import model3d, pdb
from tests.structures import build_pdb

KERN = "GGCTAGCTACAACGA"
REFERENZ_DNA = "TTGGGGTAA" + KERN + "GGTGCATGT"
RNA = "ACGUACGUACGUACGUAC"


@pytest.fixture
def text() -> str:
    return build_pdb(REFERENZ_DNA, RNA)


@pytest.fixture
def struktur(text):
    return pdb.parse_structure(text, "TEST")


def test_gleiche_sequenz_wird_vollstaendig_uebernommen(struktur, text, registry):
    modell = model3d.thread(REFERENZ_DNA, struktur, structure_text=text, registry=registry)
    assert modell.available is True
    assert modell.counts() == {"uebernommen": len(REFERENZ_DNA) + len(RNA)}
    assert all(p.provenance == "uebernommen" for p in modell.positions)


def test_purin_gegen_purin_behaelt_das_ringgeruest(struktur, text, registry):
    # Position 1 ist in der Referenz ein T; ein A dort ist ein Austausch
    # Pyrimidin gegen Purin, Position 3 (G) gegen A bleibt Purin.
    kandidat = "TTAGGGTAA" + KERN + "GGTGCATGT"
    modell = model3d.thread(kandidat, struktur, structure_text=text, registry=registry)
    dritte = modell.positions[2]
    assert dritte.provenance == "geruest"
    assert dritte.note == "G → A auf der Vorlage"


def test_purin_gegen_pyrimidin_laesst_die_base_weg(struktur, text, registry):
    """Geraten wird nicht: lieber kein Ringatom als ein erfundenes."""
    # In der Referenz steht an Position 3 ein G. Ein C dort ist Purin
    # gegen Pyrimidin — das gemeinsame Ringgerüst gibt es da nicht.
    kandidat = "TTCGGGTAA" + KERN + "GGTGCATGT"
    modell = model3d.thread(kandidat, struktur, structure_text=text, registry=registry)
    erste = modell.positions[2]
    assert erste.provenance == "nur_zucker"
    assert any("nicht geraten" in w for w in modell.warnings)

    # Im PDB-Text darf an dieser Stelle kein Basenatom mehr stehen.
    atome = [
        a
        for a in pdb.atoms_of(modell.pdb)
        if a.chain == "A" and a.residue_number == erste.residue_number
    ]
    assert {a.name for a in atome} <= model3d.BACKBONE


def test_ausgerichtet_wird_am_kern(struktur, text, registry):
    """Der Kern ist der einzige Anker, der nicht geraten ist."""
    # Ein Kandidat mit kürzerem 5'-Arm: ohne Kernanker läge alles daneben.
    kandidat = "GGGTAA" + KERN + "GGTGCATGT"
    modell = model3d.thread(kandidat, struktur, structure_text=text, registry=registry)
    kern_positionen = [p for p in modell.positions if 7 <= p.position <= 21]
    # Der Kern des Kandidaten muss auf den Kern der Referenz fallen,
    # also auf die Reste 10 bis 24.
    assert [p.residue_number for p in kern_positionen] == list(range(10, 25))
    assert all(p.provenance == "uebernommen" for p in kern_positionen)


def test_was_ueber_die_referenz_hinausragt_heisst_ideal(struktur, text, registry):
    kandidat = "AAATTGGGGTAA" + KERN + "GGTGCATGTAAA"
    modell = model3d.thread(kandidat, struktur, structure_text=text, registry=registry)
    ideal = [p for p in modell.positions if p.provenance == "ideal"]
    assert len(ideal) == 6
    assert any("außerhalb der Referenz" in w for w in modell.warnings)


def test_modifikationen_werden_mitgefuehrt(struktur, text, registry):
    kandidat = "[LNA-T]TGGGGTAA" + KERN + "GGTGCATGT"
    modell = model3d.thread(kandidat, struktur, structure_text=text, registry=registry)
    assert modell.positions[0].modification == "LNA"
    assert modell.positions[0].klasse == "zucker"
    # Die Koordinaten bleiben die der Referenz — die LNA verschiebt nichts.
    assert modell.positions[0].provenance == "uebernommen"


def test_das_substrat_bleibt_unangetastet(struktur, text, registry):
    modell = model3d.thread(REFERENZ_DNA, struktur, structure_text=text, registry=registry)
    assert [p.code for p in modell.substrate] == list(RNA)
    assert all(p.provenance == "uebernommen" for p in modell.substrate)


def test_der_hinweis_steht_am_modell(struktur, text, registry):
    """PHASEN.md 6.2: in der Oberfläche deutlich schreiben."""
    modell = model3d.thread(REFERENZ_DNA, struktur, structure_text=text, registry=registry)
    assert "Das ist ein Modell" in modell.disclaimer
    assert "TEST" in modell.disclaimer


def test_ohne_dna_kette_kein_modell(registry):
    nur_rna = pdb.parse_structure(build_pdb("", RNA), "NURRNA")
    modell = model3d.thread("ACGT", nur_rna, structure_text=build_pdb("", RNA), registry=registry)
    assert modell.available is False
    assert "keine DNA-Kette" in (modell.note or "")


def test_ohne_referenz_kein_modell(registry):
    leer = pdb.Structure(id="9ZZZ", available=False, note="nicht erreichbar")
    modell = model3d.thread("ACGT", leer, registry=registry)
    assert modell.available is False
    assert "nicht erreichbar" in (modell.note or "")


def test_das_ergebnis_ist_lesbares_pdb(struktur, text, registry):
    modell = model3d.thread(REFERENZ_DNA, struktur, structure_text=text, registry=registry)
    wieder = pdb.parse_structure(modell.pdb, "MODELL")
    assert wieder.available is True
    assert wieder.dnazyme_chain is not None
    assert wieder.dnazyme_chain.sequence == REFERENZ_DNA
    assert wieder.substrate_chain is not None
    assert wieder.substrate_chain.sequence == RNA


def test_ideale_spur_ist_eine_helix():
    spur = model3d.ideal_trace(12)
    assert len(spur) == 12
    # Gleichmäßiger Anstieg …
    hoehen = [p[2] for p in spur]
    schritte = {round(b - a, 6) for a, b in zip(hoehen, hoehen[1:])}
    assert schritte == {round(model3d.A_FORM_RISE_A, 6)}
    # … und gleichbleibender Radius.
    radien = {round((p[0] ** 2 + p[1] ** 2) ** 0.5, 6) for p in spur}
    assert radien == {round(model3d.A_FORM_P_RADIUS_A, 6)}
