"""Kataloge laden und eigene Bausteine schreiben."""

from __future__ import annotations

import shutil

import pytest

from app.registry import (
    EXCEL_AMIDITE,
    EXCEL_CONC,
    EXCEL_MASS_RESIDUE,
    Registry,
    remove_monomer_override,
    save_modification,
    save_monomer,
)


@pytest.fixture
def datenverzeichnis(tmp_path):
    """Eine Kopie von `data/`, damit die Tests nicht in die echten Dateien schreiben."""
    for name in (
        "monomers.yaml",
        "protecting_groups.yaml",
        "modifications.yaml",
        "extinction.yaml",
    ):
        shutil.copy(f"data/{name}", tmp_path / name)
    return tmp_path


def test_excel_konstanten_stimmen_mit_der_datei(registry):
    """Die Abschrift in `monomers.yaml` muss mit CLAUDE.md uebereinstimmen."""
    for code, sollwert in EXCEL_MASS_RESIDUE.items():
        spec = registry.monomer(code)
        assert spec is not None, f"Baustein {code} fehlt"
        assert spec.mass_residue == pytest.approx(sollwert, abs=1e-9)
    for code, sollwert in EXCEL_AMIDITE.items():
        assert registry.monomer(code).mass_amidite == pytest.approx(sollwert, abs=1e-9)
    for code, sollwert in EXCEL_CONC.items():
        assert registry.monomer(code).conc_molar == pytest.approx(sollwert, abs=1e-9)


def test_keine_falsche_abweichungsmarkierung(registry):
    """Solange nichts geaendert wurde, ist kein Baustein als abweichend markiert."""
    for code in EXCEL_MASS_RESIDUE:
        assert registry.monomer(code).deviates_from_excel is False


def test_schutzgruppen_und_endgruppen(registry):
    assert registry.protecting_group_for_base("A") == ("Bz", 104.03)
    assert registry.protecting_group_for_base("G") == ("iBu", 70.05)
    assert registry.protecting_group_for_base("C") == ("Ac", 42.02)
    assert registry.protecting_group_for_base("T") == (None, 0.0)
    assert registry.dmt_mass == 302.34
    assert registry.phosphate_offset == 61.96
    assert registry.cyanoethyl_mass == 53.03


def test_modifikationen_aus_claude_md(registry):
    erwartet = {
        "RNA": 16.0, "OMe": 30.0, "MOE": 74.04, "LNA": 12.0,
        "Me-Phosphonat": -2.0, "Thioat": 16.0,
        "6-FAM": 537.46, "TET": 675.24, "HEX": 744.13, "TBDMS": 114.09,
    }
    for code, sollwert in erwartet.items():
        spec = registry.modification(code)
        assert spec is not None, f"Modifikation {code} fehlt"
        assert spec.mass_diff == pytest.approx(sollwert, abs=1e-9)


def test_galnac_ist_angelegt_aber_ohne_masse(registry):
    """Die Masse haengt am Linker und stand nicht im Excel — sie wird nicht erfunden."""
    spec = registry.modification("5GalNAc")
    assert spec is not None
    assert spec.mass_diff is None
    assert spec.formula is None
    assert spec.needs_review is True
    assert spec.counts_as_base is False
    assert spec.scope == "terminus"


def test_eigene_aenderung_wird_als_abweichung_markiert(datenverzeichnis):
    registry = Registry(datenverzeichnis)
    assert registry.monomer("A").deviates_from_excel is False

    save_monomer(
        {"code": "A", "mass_residue": 313.21, "quelle": "von Hand"}, datenverzeichnis
    )
    registry.reload()

    spec = registry.monomer("A")
    assert spec.mass_residue == 313.21
    assert spec.deviates_from_excel is True, (
        "Eine geaenderte Konstante muss als Abweichung sichtbar sein."
    )
    # Was nicht ueberschrieben wurde, bleibt stehen.
    assert spec.name == "dA — Desoxyadenosin"
    assert spec.formula_residue == "C10H12N5O5P"


def test_excel_datei_bleibt_unberuehrt(datenverzeichnis):
    """Eigene Aenderungen landen in einer Nachbardatei, nicht in monomers.yaml."""
    vorher = (datenverzeichnis / "monomers.yaml").read_text(encoding="utf-8")
    save_monomer({"code": "A", "mass_residue": 999.0}, datenverzeichnis)
    nachher = (datenverzeichnis / "monomers.yaml").read_text(encoding="utf-8")
    assert vorher == nachher
    assert (datenverzeichnis / "monomers_custom.yaml").exists()


def test_eigener_baustein_anlegen(datenverzeichnis):
    registry = Registry(datenverzeichnis)
    assert registry.monomer("X42") is None

    save_monomer(
        {
            "code": "X42",
            "name": "Eigener Baustein",
            "mass_residue": 400.0,
            "mass_amidite": 900.0,
            "conc_molar": 0.07,
            "base_parent": "A",
        },
        datenverzeichnis,
    )
    registry.reload()

    spec = registry.monomer("X42")
    assert spec.name == "Eigener Baustein"
    assert spec.base_parent == "A"
    assert spec.deviates_from_excel is True, "Was es im Excel nicht gab, ist Abweichung."


def test_aenderung_zuruecknehmen(datenverzeichnis):
    registry = Registry(datenverzeichnis)
    save_monomer({"code": "A", "mass_residue": 999.0}, datenverzeichnis)
    registry.reload()
    assert registry.monomer("A").mass_residue == 999.0

    assert remove_monomer_override("A", datenverzeichnis) is True
    registry.reload()
    assert registry.monomer("A").mass_residue == 312.05
    assert registry.monomer("A").deviates_from_excel is False
    assert remove_monomer_override("A", datenverzeichnis) is False


def test_eigene_modifikation_anlegen(datenverzeichnis):
    registry = Registry(datenverzeichnis)
    save_modification(
        {"code": "2F", "name": "2'-Fluor", "mass_diff": 4.0, "scope": "monomer",
         "klasse": "zucker"},
        datenverzeichnis,
    )
    registry.reload()
    spec = registry.modification("2F")
    assert spec.mass_diff == 4.0
    assert spec.klasse == "zucker"


def test_eigener_baustein_ist_in_der_sequenz_nutzbar(datenverzeichnis):
    """Ein neuer Baustein muss sofort in der Synthi-Sprache funktionieren."""
    from app.notation import parse
    from app import mass

    registry = Registry(datenverzeichnis)
    save_monomer(
        {"code": "X42", "name": "Eigener", "mass_residue": 400.0,
         "mass_amidite": 900.0, "conc_molar": 0.07, "base_parent": "A"},
        datenverzeichnis,
    )
    registry.reload()

    oligo = parse("AC[X42]GT", registry)
    assert oligo.monomers[2].code == "X42"
    assert oligo.monomers[2].base_parent == "A"
    ergebnis = mass.compute(oligo, registry)
    assert ergebnis.fully_deprotected.value is not None
    # X42 zaehlt ueber base_parent als A: bei AC[X42]GT sind das zwei.
    assert ergebnis.breakdown.n_a == 2
