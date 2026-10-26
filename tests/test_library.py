"""Bibliothek und Probenliste."""

from __future__ import annotations

from app import library

from .conftest import REFERENCE_SEQUENCE


def test_oligo_speichern_und_lesen():
    record = library.save_oligo(
        "DZ-10-23", REFERENCE_SEQUENCE, length=33, mass=10241.26
    )
    assert record.id is not None
    geladen = library.get_oligo(record.id)
    assert geladen.sequence == REFERENCE_SEQUENCE
    assert geladen.length == 33


def test_gleicher_name_aktualisiert_statt_zu_doppeln():
    library.save_oligo("Probe", "ACGT", length=4)
    library.save_oligo("Probe", "ACGTACGT", length=8)
    eintraege = library.list_oligos()
    assert len(eintraege) == 1
    assert eintraege[0].length == 8


def test_suche_ueber_name_sequenz_und_notiz():
    library.save_oligo("Erstes", "ACGT", notes="für das Gel")
    library.save_oligo("Zweites", "TTTT", notes="Reserve")
    assert [o.name for o in library.list_oligos("zweit")] == ["Zweites"]
    assert [o.name for o in library.list_oligos("TTTT")] == ["Zweites"]
    assert [o.name for o in library.list_oligos("gel")] == ["Erstes"]
    assert library.list_oligos("gibtesnicht") == []


def test_loeschen():
    record = library.save_oligo("Weg damit", "ACGT")
    assert library.delete_oligo(record.id) is True
    assert library.get_oligo(record.id) is None
    assert library.delete_oligo(record.id) is False


def test_csv_export_hat_kopfzeile_und_eintraege():
    library.save_oligo("DZ-10-23", REFERENCE_SEQUENCE, length=33, mass=10241.26)
    csv_text = library.oligos_as_csv()
    zeilen = csv_text.strip().splitlines()
    assert zeilen[0].startswith("Name;Sequenz;Bausteine")
    assert "DZ-10-23" in zeilen[1]
    assert "10241.26" in zeilen[1]


def test_probenliste_bleibt_gespeichert():
    library.save_sample("Probe A", 50, 100)
    library.save_sample("Probe B", 20, 50, notes="verdünnt")
    namen = [p.name for p in library.list_samples()]
    assert set(namen) == {"Probe A", "Probe B"}


def test_probe_aktualisieren_und_loeschen():
    probe = library.save_sample("Probe A", 50, 100)
    library.save_sample("Probe A", 25, 100)
    assert len(library.list_samples()) == 1
    assert library.list_samples()[0].n_stock_nmol == 25
    assert library.delete_sample(probe.id) is True
    assert library.list_samples() == []
