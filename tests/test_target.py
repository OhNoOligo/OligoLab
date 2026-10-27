"""Die Ziel-RNA holen und verwalten (PHASEN.md 4.1)."""

from __future__ import annotations

import json

import pytest

from app import target

FASTA = """>NM_000546.6 Homo sapiens tumor protein p53 (TP53), mRNA
GGCAGCUACGGUUUCCGUCUGGGCUUCUUGCAUUCUGGGACAGCCAAGUCUGUGACUUGC
ACGUACUCCCCUGCCCUCAACAAGAUGUUUUGCCAACUGGCCAAGACCUGCCCUGUGCAG
"""

GENBANK = """LOCUS       TESTSEQ                   60 bp    mRNA    linear   PRI 01-JAN-2020
DEFINITION  Konstruierte Testsequenz.
ACCESSION   TESTSEQ
VERSION     TESTSEQ.1
SOURCE      Homo sapiens
  ORGANISM  Homo sapiens
FEATURES             Location/Qualifiers
     source          1..60
                     /organism="Homo sapiens"
     CDS             11..40
                     /product="Testprotein"
ORIGIN
        1 aaaaaaaaaa atgggggggg gggggggggg ggggggggta aaaaaaaaaa aaaaaaaaaa
//
"""


# ------------------------------------------------------------- einlesen


def test_dna_wird_stillschweigend_zu_rna():
    """PHASEN.md 4.1: T wird zu U, ohne Nachfrage."""
    assert target.normalise("ACGT") == "ACGU"
    assert target.normalise("acgt") == "ACGU"


def test_leerraum_und_zahlen_fallen_weg():
    """Positionsangaben aus einem Alignment sollen nicht stören."""
    assert target.normalise("   1 ACGT\n  61 ACGT  ") == "ACGUACGU"
    assert target.normalise("AC GT\tAC\r\nGT") == "ACGUACGU"


def test_unbekanntes_zeichen_ist_ein_fehler_mit_position():
    """CLAUDE.md, Regel 5 — auch für Zielsequenzen."""
    with pytest.raises(target.TargetError) as fehler:
        target.normalise("ACGXU")
    assert fehler.value.position == 4
    assert fehler.value.character == "X"
    assert "Position 4" in str(fehler.value)


def test_position_zaehlt_die_bereinigte_sequenz():
    """Der Nutzer sieht hinterher die bereinigte Sequenz, nicht seinen Rohtext."""
    with pytest.raises(target.TargetError) as fehler:
        target.normalise("  1 ACG\n  4 XU")
    assert fehler.value.position == 4


def test_n_ist_erlaubt():
    """N heißt ausdrücklich `unbekannt` und ist keine Schlamperei."""
    assert target.normalise("ACGNU") == "ACGNU"


def test_leere_eingabe():
    assert target.normalise("") == ""
    assert target.normalise("   \n  ") == ""


def test_direkteingabe():
    ziel = target.from_text("ACGT ACGT", name="Mein Ziel")
    assert ziel.sequence == "ACGUACGU"
    assert ziel.name == "Mein Ziel"
    assert ziel.source == "Direkteingabe"
    assert ziel.length == 8


# ----------------------------------------------------------------- FASTA


def test_fasta_wird_geparst():
    ziel = target.from_fasta(FASTA)
    assert ziel.source == "FASTA"
    assert ziel.identifier == "NM_000546.6"
    assert "TP53" in (ziel.description or "")
    assert ziel.length == 120
    assert set(ziel.sequence) <= set("ACGUN")


def test_fasta_mit_mehreren_eintraegen_sagt_es():
    doppelt = FASTA + ">zweiter\nACGUACGU\n"
    ziel = target.from_fasta(doppelt)
    assert ziel.identifier == "NM_000546.6"
    assert ziel.note and "zwei" in ziel.note.lower() or "2" in (ziel.note or "")


def test_leere_fasta_datei():
    with pytest.raises(ValueError):
        target.from_fasta("kein fasta hier")


# --------------------------------------------------------------- GenBank


def test_genbank_wird_geparst():
    ziel = target.from_genbank(GENBANK)
    assert ziel.source == "GenBank"
    assert ziel.organism == "Homo sapiens"
    assert ziel.length == 60


def test_genbank_leitet_die_utr_aus_dem_cds_ab():
    """Stehen die UTR nicht als Merkmal da, ergeben sie sich aus der Lage des CDS."""
    ziel = target.from_genbank(GENBANK)
    nach_art = {r.kind: (r.start, r.end) for r in ziel.regions}
    assert nach_art["cds"] == (11, 40)
    assert nach_art["5utr"] == (1, 10)
    assert nach_art["3utr"] == (41, 60)
    # Nach Position sortiert, damit die Oberfläche sie der Reihe nach malen kann.
    assert [r.start for r in ziel.regions] == sorted(r.start for r in ziel.regions)


def test_genbank_ohne_cds_hat_keine_abschnitte():
    ohne = GENBANK.replace("     CDS             11..40\n", "").replace(
        '                     /product="Testprotein"\n', ""
    )
    assert target.from_genbank(ohne).regions == []


# ------------------------------------------------------- Zwischenspeicher


def test_zwischenspeicher_schreiben_und_lesen(data_dir):
    ziel = target.Target(
        name="Test", sequence="ACGU", source="ncbi", identifier="NM_1",
        fetched_at="2026-10-27T10:00:00+00:00",
        regions=[target.Region("cds", 1, 4)],
    )
    target.write_cache(ziel)

    geladen = target.read_cache("ncbi", "NM_1")
    assert geladen is not None
    assert geladen.sequence == "ACGU"
    assert geladen.fetched_at == ziel.fetched_at
    assert [r.kind for r in geladen.regions] == ["cds"]


def test_zwischenspeicher_ohne_kennung_schreibt_nicht(data_dir):
    target.write_cache(target.Target(name="X", sequence="ACGU"))
    assert list((data_dir / "targets").glob("*.json")) == []


def test_kaputter_zwischenspeicher_stuerzt_nicht_ab(data_dir):
    pfad = data_dir / "targets" / "ncbi_NM_1.json"
    pfad.write_text("{kaputt", encoding="utf-8")
    assert target.read_cache("ncbi", "NM_1") is None


def test_kennung_mit_schraegstrich_wird_entschaerft(data_dir):
    """Eine Kennung ist Fremdeingabe und darf nicht aus dem Verzeichnis führen."""
    ziel = target.Target(
        name="X", sequence="ACGU", source="ncbi", identifier="../../entwischt"
    )
    target.write_cache(ziel)
    geschrieben = list((data_dir / "targets").glob("*.json"))
    assert len(geschrieben) == 1
    assert geschrieben[0].parent == data_dir / "targets"


# ---------------------------------------------------------------- abrufen


@pytest.mark.parametrize("quelle,kennung", [
    ("ensembl", "TP53"),
    ("ncbi", "NM_000546"),
    ("rnacentral", "URS0000000001"),
])
def test_abruf_ohne_netz_bleibt_ruhig(quelle, kennung, monkeypatch, data_dir):
    """CLAUDE.md, Regel 4: ohne Netz bleibt die App voll bedienbar.

    Ein fehlgeschlagener Abruf ist kein Fehler, sondern ein Zustand — und der
    Hinweis sagt, wie es trotzdem weitergeht.
    """
    import httpx

    def kein_netz(*args, **kwargs):
        raise httpx.ConnectError("kein Netz")

    monkeypatch.setattr(httpx.Client, "get", kein_netz)

    ergebnis = target.FETCHERS[quelle](kennung)
    assert ergebnis.available is False
    assert ergebnis.target is None
    assert ergebnis.message
    assert "nicht erreichbar" in ergebnis.message
    assert "voll bedienbar" in ergebnis.message


def test_ohne_netz_kommt_der_zwischenspeicher_zum_zug(monkeypatch, data_dir):
    """Was einmal geholt wurde, bleibt auch offline verfügbar."""
    import httpx

    target.write_cache(
        target.Target(
            name="Gespeichert", sequence="ACGUACGU", source="ncbi",
            identifier="NM_000546", fetched_at="2026-01-01T00:00:00+00:00",
        )
    )

    monkeypatch.setattr(
        httpx.Client, "get",
        lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("kein Netz")),
    )

    ergebnis = target.fetch_ncbi("NM_000546")
    assert ergebnis.available is True
    assert ergebnis.from_cache is True
    assert ergebnis.target is not None
    assert ergebnis.target.sequence == "ACGUACGU"
    assert "Zwischenspeicher" in (ergebnis.message or "")


def test_ratenbremse_wartet(monkeypatch):
    """Die Grenzen stehen in den Nutzungsbedingungen der Anbieter.

    Sie zu überschreiten führt zu Sperren — und zwar für den Nutzer.
    """
    gewartet: list[float] = []
    monkeypatch.setattr(target.time, "sleep", gewartet.append)
    monkeypatch.setattr(target, "_last_request", {})

    target._throttle("ncbi")
    assert gewartet == [], "die erste Anfrage wartet nicht"

    target._throttle("ncbi")
    assert len(gewartet) == 1
    # NCBI erlaubt drei je Sekunde, also ein Drittel Sekunde Abstand.
    assert gewartet[0] == pytest.approx(1 / 3, abs=0.05)


def test_grenzen_wie_dokumentiert():
    assert target.RATE_LIMITS["ncbi"] == 3.0
    assert target.RATE_LIMITS["rnacentral"] == 20.0


def test_ncbi_schickt_die_kennmail_nur_wenn_sie_gesetzt_ist(monkeypatch, data_dir):
    """Die Adresse wird nicht erraten und nicht fest eingebaut."""
    import httpx

    from app.config import settings

    gesehen: list[dict] = []

    class Antwort:
        text = GENBANK

        def raise_for_status(self) -> None:
            return None

    def aufzeichnen(self, url, params=None, **kwargs):
        gesehen.append(dict(params or {}))
        return Antwort()

    monkeypatch.setattr(httpx.Client, "get", aufzeichnen)

    monkeypatch.setattr(settings, "ncbi_email", "")
    target.fetch_ncbi("TESTSEQ")
    assert "email" not in gesehen[-1]
    assert gesehen[-1]["tool"] == "OligoLab"

    monkeypatch.setattr(settings, "ncbi_email", "jemand@example.org")
    target.fetch_ncbi("TESTSEQ")
    assert gesehen[-1]["email"] == "jemand@example.org"


def test_erfolgreicher_abruf_landet_im_zwischenspeicher(monkeypatch, data_dir):
    import httpx

    class Antwort:
        text = GENBANK

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(httpx.Client, "get", lambda *a, **k: Antwort())

    ergebnis = target.fetch_ncbi("TESTSEQ")
    assert ergebnis.available and ergebnis.target is not None
    assert ergebnis.target.source == "ncbi"
    assert ergebnis.target.fetched_at

    pfad = data_dir / "targets" / "ncbi_TESTSEQ.json"
    assert pfad.exists()
    with pfad.open(encoding="utf-8") as fh:
        assert json.load(fh)["identifier"] == "TESTSEQ"
