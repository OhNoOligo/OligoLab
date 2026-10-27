"""Schmelztemperatur und Thermodynamik (PHASEN.md 5.1)."""

from __future__ import annotations

import pytest

from app import melting
from app.notation import parse

ARM = "TTGGGGTAA"


@pytest.fixture
def bedingungen() -> melting.Conditions:
    return melting.Conditions(
        oligo_conc_nm=1000, na_mm=50, k_mm=0, tris_mm=10, mg_mm=2, temperature_c=37
    )


# ============================================================= Biopython


def test_eigene_rechnung_stimmt_mit_biopython_ueberein(bedingungen):
    """Tm, ΔH, ΔS und ΔG stammen aus derselben Tabelle.

    Käme der Tm aus Biopython und ΔH/ΔS aus einer eigenen Summe, könnten sich
    beide leise widersprechen. Darum wird hier gegengerechnet.
    """
    from Bio.Seq import Seq
    from Bio.SeqUtils import MeltingTemp as mt

    ergebnis = melting.biopython_tm(ARM, bedingungen)
    ueber_biopython = mt.Tm_NN(
        Seq(ARM),
        nn_table=mt.R_DNA_NN1,
        Na=bedingungen.na_mm,
        K=bedingungen.k_mm,
        Tris=bedingungen.tris_mm,
        Mg=bedingungen.mg_mm,
        dnac1=bedingungen.oligo_conc_nm,
        dnac2=0,
        saltcorr=5,
    )
    assert ergebnis.tm.value == pytest.approx(ueber_biopython, abs=0.01)


def test_hybridtabelle_wird_benutzt(bedingungen):
    """Ein DNAzym-Arm bindet RNA, nicht DNA."""
    ergebnis = melting.biopython_tm(ARM, bedingungen)
    assert "DNA/RNA" in ergebnis.tm.method
    assert "Sugimoto" in ergebnis.parameter_set


def test_thermodynamik_haengt_zusammen(bedingungen):
    """ΔG = ΔH − T·ΔS, mit T aus den Bedingungen."""
    ergebnis = melting.biopython_tm(ARM, bedingungen)
    temperatur = bedingungen.temperature_c + 273.15
    erwartet = ergebnis.dh.value - temperatur * ergebnis.ds.value / 1000.0
    assert ergebnis.dg.value == pytest.approx(erwartet, abs=1e-9)
    assert ergebnis.dh.value < 0, "Hybridisierung setzt Enthalpie frei"
    assert ergebnis.ds.value < 0, "und ordnet"


def test_mehr_salz_hebt_den_tm(bedingungen):
    wenig = melting.biopython_tm(ARM, melting.Conditions(na_mm=10, mg_mm=0))
    viel = melting.biopython_tm(ARM, melting.Conditions(na_mm=200, mg_mm=10))
    assert viel.tm.value > wenig.tm.value


def test_hoehere_konzentration_hebt_den_tm(bedingungen):
    duenn = melting.biopython_tm(ARM, melting.Conditions(oligo_conc_nm=10))
    dicht = melting.biopython_tm(ARM, melting.Conditions(oligo_conc_nm=10000))
    assert dicht.tm.value > duenn.tm.value


def test_laengerer_arm_bindet_fester(bedingungen):
    kurz = melting.biopython_tm("GCGCGC", bedingungen)
    lang = melting.biopython_tm("GCGCGCGCGCGC", bedingungen)
    assert lang.tm.value > kurz.tm.value
    assert lang.dg.value < kurz.dg.value


@pytest.mark.parametrize("sequenz", ["", "A", "ACGTN", "ACGTX"])
def test_unbrauchbare_sequenz(sequenz, bedingungen):
    ergebnis = melting.biopython_tm(sequenz, bedingungen)
    assert ergebnis.available is False
    assert ergebnis.note


def test_grund_steht_vor_dem_hinweis_auf_melting(bedingungen):
    """Wer zwei Basen eingibt, soll nicht lesen, er müsse Java installieren."""
    ergebnis = melting.compute("A", bedingungen)
    assert ergebnis.available is False
    assert ergebnis.note.startswith("Für eine Nearest-Neighbor-Rechnung")


# =========================================================== Uebersetzung


def test_lna_bekommt_den_melting_buchstaben(registry):
    uebersetzung = melting.translate(parse("AC[LNA-T]GA", registry))
    assert uebersetzung.melting_sequence == "ACTlGA"
    assert uebersetzung.plain_sequence == "ACTGA"
    assert any("LNA" in eintrag for eintrag in uebersetzung.approximated)


def test_2ome_macht_daraus_ein_rna_duplex(registry):
    """PHASEN.md 5.1: 2'-OMe → Typ `mrnarna`."""
    uebersetzung = melting.translate(parse("AC[OMe-A]GT", registry))
    assert uebersetzung.hybridisation == melting.MELTING_HYBRID_RNA_RNA
    assert any("2'-OMe" in eintrag for eintrag in uebersetzung.approximated)


def test_ohne_modifikation_bleibt_es_ein_hybrid(registry):
    uebersetzung = melting.translate(parse("ACGT", registry))
    assert uebersetzung.hybridisation == melting.MELTING_HYBRID_DNA_RNA
    assert uebersetzung.approximated == []


def test_rna_baustein_wird_zu_t(registry):
    """U und T sind für die Nearest-Neighbor-Tabelle dasselbe."""
    assert melting.translate(parse("OIZU", registry)).plain_sequence == "ACGT"


def test_baustein_ohne_analogon_wird_benannt(registry):
    uebersetzung = melting.translate(parse("ACEGT", registry))
    assert "N" in uebersetzung.plain_sequence
    assert any("kein natürliches Analogon" in e for e in uebersetzung.approximated)


def test_modifizierter_arm_ist_genaehert(registry, bedingungen):
    """CLAUDE.md, Regel 3 — die Tabelle kennt keine LNA."""
    ergebnis = melting.compute(parse("AC[LNA-T]GAACGT", registry), bedingungen)
    assert ergebnis.reliability.value == "genähert über natürliches Analogon"


# =============================================================== MELTING


def test_ohne_melting_rechnet_biopython_allein(bedingungen):
    """CLAUDE.md, Regel 4: fehlt ein externes Programm, läuft der Rest weiter."""
    assert melting.melting_executable() is None
    ergebnis = melting.compute(ARM, bedingungen)
    assert ergebnis.available is True
    assert ergebnis.source == "biopython"
    assert "MELTING ist nicht eingerichtet" in (ergebnis.note or "")


def test_melting_wird_nur_dort_gesucht_wo_es_stehen_soll(monkeypatch, tmp_path):
    """Nichts wird geraten und nichts über die Shell aufgelöst."""
    from app.config import settings

    monkeypatch.setattr(settings, "melting_dir", "")
    assert melting.melting_executable() is None

    monkeypatch.setattr(settings, "melting_dir", str(tmp_path))
    assert melting.melting_executable() is None

    (tmp_path / "melting").write_text("#!/bin/sh\n", encoding="utf-8")
    gefunden = melting.melting_executable()
    assert gefunden == tmp_path / "melting"


def test_melting_wird_ohne_shell_aufgerufen(monkeypatch, tmp_path):
    """Eine Sequenz ist Nutzereingabe und hat in keiner Shell etwas zu suchen."""
    from app.config import settings

    (tmp_path / "melting").write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(settings, "melting_dir", str(tmp_path))

    gesehen: dict = {}

    class Antwort:
        returncode = 0
        stdout = (
            "Enthalpy: -81.8 kcal/mol\n"
            "Entropy: -235.6 cal/mol/K\n"
            "Melting temperature: 37.9 deg C\n"
        )
        stderr = ""

    def aufzeichnen(befehl, **kwargs):
        gesehen["befehl"] = befehl
        gesehen["kwargs"] = kwargs
        return Antwort()

    monkeypatch.setattr(melting.subprocess, "run", aufzeichnen)

    uebersetzung = melting.Translation("ACGTACGT", "ACGTACGT", "dnarna")
    ergebnis = melting.melting_tm(uebersetzung, melting.Conditions())

    assert gesehen["kwargs"]["shell"] is False
    assert gesehen["befehl"][0] == str(tmp_path / "melting")
    assert "-S" in gesehen["befehl"]
    assert "dnarna" in gesehen["befehl"]
    assert ergebnis.available is True
    assert ergebnis.tm.value == pytest.approx(37.9)
    assert ergebnis.dh.value == pytest.approx(-81.8)


def test_melting_ausgabe_lesen():
    text = (
        "  Enthalpy : -81.8 kcal/mol\n"
        "  Entropy : -235.6 cal/mol/K\n"
        "  Melting temperature : 37.86 deg C\n"
    )
    zahlen = melting.parse_melting_output(text)
    assert zahlen["dh"] == pytest.approx(-81.8)
    assert zahlen["ds"] == pytest.approx(-235.6)
    assert zahlen["tm"] == pytest.approx(37.86)


def test_unlesbare_melting_ausgabe_erfindet_nichts():
    assert melting.parse_melting_output("irgendwas anderes") == {}


def test_zweitmeinung_warnt_bei_abweichung(monkeypatch, tmp_path):
    """PHASEN.md 5.1: bei mehr als 3 °C Abweichung eine Warnung."""
    from app.config import settings

    (tmp_path / "melting").write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(settings, "melting_dir", str(tmp_path))

    class Antwort:
        returncode = 0
        # Absichtlich weit weg von dem, was Biopython für diesen Arm liefert.
        stdout = "Melting temperature: 70.0 deg C\n"
        stderr = ""

    monkeypatch.setattr(melting.subprocess, "run", lambda *a, **k: Antwort())

    ergebnis = melting.compute(ARM, melting.Conditions())
    assert ergebnis.source == "melting"
    assert ergebnis.divergence_c > melting.DIVERGENCE_WARNING_C
    assert ergebnis.warnings
    assert "uneinig" in ergebnis.warnings[0]


def test_keine_warnung_bei_einigkeit(monkeypatch, tmp_path):
    """Die Gegenprobe — sonst wäre die Warnung nichtssagend."""
    from app.config import settings

    (tmp_path / "melting").write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(settings, "melting_dir", str(tmp_path))

    biopython = melting.biopython_tm(ARM, melting.Conditions())

    class Antwort:
        returncode = 0
        stdout = f"Melting temperature: {biopython.tm.value:.2f} deg C\n"
        stderr = ""

    monkeypatch.setattr(melting.subprocess, "run", lambda *a, **k: Antwort())

    ergebnis = melting.compute(ARM, melting.Conditions())
    assert ergebnis.divergence_c < melting.DIVERGENCE_WARNING_C
    assert ergebnis.warnings == []


def test_melting_mit_fehlercode(monkeypatch, tmp_path):
    from app.config import settings

    (tmp_path / "melting").write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(settings, "melting_dir", str(tmp_path))

    class Antwort:
        returncode = 2
        stdout = ""
        stderr = "unbekannter Hybridtyp"

    monkeypatch.setattr(melting.subprocess, "run", lambda *a, **k: Antwort())

    ergebnis = melting.melting_tm(
        melting.Translation("ACGT", "ACGT", "dnarna"), melting.Conditions()
    )
    assert ergebnis.available is False
    assert "Code 2" in ergebnis.note


def test_bedingungen_aus_der_kopfzeile():
    bedingungen = melting.arm_conditions_from(
        {"oligoConcNm": 500, "naMm": 100, "mgMm": 5, "reactionTempC": 42}
    )
    assert bedingungen.oligo_conc_nm == 500
    assert bedingungen.na_mm == 100
    assert bedingungen.mg_mm == 5
    assert bedingungen.temperature_c == 42
    # Was nicht dasteht, behält seine Voreinstellung.
    assert bedingungen.tris_mm == 10
