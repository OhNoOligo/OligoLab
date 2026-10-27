"""Referenzstrukturen (PHASEN.md 6.1)."""

from __future__ import annotations

import pytest

from app import pdb
from tests.structures import build_cif, build_pdb

DNA = "TTGGGGTAA" + "GGCTAGCTACAACGA" + "GGTGCATGT"
RNA = "ACGUACGUACGUACGUAC"


@pytest.fixture
def text() -> str:
    return build_pdb(DNA, RNA, ions=[("MG", 5.0, 5.0, 5.0)])


# ------------------------------------------------------------- Katalog


def test_katalog_wird_gelesen():
    eintraege, voreinstellung = pdb.load_references()
    assert voreinstellung == "8E9A"
    assert "8E9A" in {e.id for e in eintraege}


def test_katalog_traegt_keine_abgeschriebenen_werte():
    """Auflösung und Literatur stehen in der Datei, nicht im Katalog.

    Ein von Hand abgeschriebener Wert wäre eine zweite Quelle, die beim
    ersten Tippfehler von der ersten abweicht.
    """
    eintraege, _ = pdb.load_references()
    for eintrag in eintraege:
        assert not hasattr(eintrag, "resolution_a")
        assert eintrag.id and eintrag.title


# -------------------------------------------------------------- Lesen


def test_pdb_wird_gelesen(text):
    struktur = pdb.parse_structure(text, "TEST")
    assert struktur.available is True
    assert struktur.format == "pdb"
    assert struktur.method == "THEORETICAL MODEL"
    assert struktur.resolution_a == pytest.approx(1.8)


def test_cif_wird_gelesen():
    struktur = pdb.parse_structure(build_cif("ACGT", "ACGU"), "TEST")
    assert struktur.format == "cif"
    assert struktur.title == "Eine erfundene Struktur"
    assert struktur.resolution_a == pytest.approx(1.8)
    assert struktur.citation == "Kein echtes Zitat"


def test_ketten_werden_nach_ihrer_art_erkannt(text):
    struktur = pdb.parse_structure(text, "TEST")
    arten = {c.id: c.kind for c in struktur.chains}
    assert arten["A"] == "dna"
    assert arten["B"] == "rna"


def test_rollen_folgen_der_art_nicht_dem_buchstaben():
    """Die DNA-Kette ist der Strang — auch wenn sie 'B' heißt."""
    struktur = pdb.parse_structure(
        build_pdb(DNA, RNA, dna_chain="B", rna_chain="A"), "TEST"
    )
    assert struktur.dnazyme_chain is not None
    assert struktur.dnazyme_chain.id == "B"
    assert struktur.substrate_chain is not None
    assert struktur.substrate_chain.id == "A"


def test_sequenz_der_kette_stimmt(text):
    struktur = pdb.parse_structure(text, "TEST")
    assert struktur.dnazyme_chain is not None
    assert struktur.dnazyme_chain.sequence == DNA
    assert struktur.dnazyme_chain.length == len(DNA)


def test_ionen_werden_eingesammelt(text):
    struktur = pdb.parse_structure(text, "TEST")
    assert len(struktur.ions) == 1
    assert struktur.ions[0]["residue"] == "MG"


def test_struktur_ohne_rna_sagt_es():
    struktur = pdb.parse_structure(build_pdb(DNA, ""), "TEST")
    assert struktur.substrate_chain is None
    assert "keine RNA-Kette" in (struktur.note or "")


def test_wasser_zaehlt_nicht_als_kette():
    zeilen = build_pdb("ACGT", "ACGU").splitlines()
    zeilen.insert(
        3,
        "HETATM 9999  O   HOH W 500      "
        "  1.000   1.000   1.000  1.00  0.00           O",
    )
    struktur = pdb.parse_structure("\n".join(zeilen), "TEST")
    assert "W" not in {c.id for c in struktur.chains}


def test_krumme_zeile_macht_die_datei_nicht_unbrauchbar(text):
    kaputt = text.replace("ATOM      5", "ATOM    xxx", 1)
    struktur = pdb.parse_structure(kaputt, "TEST")
    assert struktur.available is True
    assert struktur.dnazyme_chain is not None


def test_datei_ohne_atome():
    struktur = pdb.parse_structure("TITLE     NICHTS\nEND\n", "LEER")
    assert struktur.available is False
    assert "kein einziges Atom" in (struktur.note or "")


# -------------------------------------------------------------- Abrufen


def test_unsinnige_kennung_wird_gar_nicht_erst_abgerufen():
    ergebnis = pdb.fetch("nicht-echt")
    assert ergebnis.available is False
    assert "keine PDB-Kennung" in (ergebnis.note or "")


def test_ohne_netz_bleibt_es_bedienbar(monkeypatch):
    """CLAUDE.md, Regel 4: ein fehlgeschlagener Abruf ist kein Fehler.

    Der Ausfall wird nachgestellt, statt wirklich nach draußen zu rufen: ein
    Test, der am Netz hängt, prüft das Netz und nicht den Code — und er
    liefert auf einem Rechner mit Verbindung ein anderes Ergebnis als auf
    einem ohne.
    """
    import httpx

    def keine_verbindung(*args, **kwargs):
        raise httpx.ConnectError("nachgestellt")

    monkeypatch.setattr(httpx.Client, "get", keine_verbindung)
    ergebnis = pdb.fetch("9ZZZ")
    assert ergebnis.available is False
    assert "nicht erreichbar" in (ergebnis.note or "")
    assert "von Hand" in (ergebnis.note or "")


def test_abruf_nimmt_zuerst_den_ablageort(text, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    (tmp_path / "structures").mkdir()
    (tmp_path / "structures" / "1ABC.pdb").write_text(text, encoding="utf-8")

    ergebnis = pdb.fetch("1ABC")
    assert ergebnis.available is True
    assert ergebnis.source == "cache"
    assert ergebnis.dnazyme_chain is not None


def test_eigene_datei_wird_uebernommen(text, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    ergebnis = pdb.store_upload("mein modell", text)
    assert ergebnis.available is True
    assert ergebnis.source == "eigene Datei"
    assert ergebnis.path is not None and ergebnis.path.exists()
    # Der Name wird entschärft, nicht übernommen.
    assert " " not in ergebnis.path.name
