"""Der Gesamtbericht (PHASEN.md 6.6)."""

from __future__ import annotations

import pytest

from app import report

DATEN = {
    "name": "DNAzym gegen XYZ",
    "sequence": "TTGGGGTAA[LNA-G]GCTAGCTACAACGAGGTGCATGT",
    "length": 33,
    "modifications": ["LNA an Position 10"],
    "mass": {"fully_deprotected": 10253.26, "with_dmt": 10555.60, "method": "Excel"},
    "ms_ladder": [{"charge": 5, "mz": 2049.6}, {"charge": 6, "mz": 1707.9}],
    "arms": {"tm5": 37.9, "tm3": 36.1, "dg_sum": -17.07, "imbalance": 0.45,
             "method": "DNA/RNA-Hybrid"},
    "self_fold_mfe": -0.5,
    "site": {"position": 45, "junction": "GU", "quality": "gut", "accessibility": 0.44},
    "score": 0.803,
    "rating": "good",
    "geometry": {
        "inline": {
            "angle": {"value": 168.2, "method": "aus den Koordinaten"},
            "distance_attack": {"value": 3.2},
            "distance_leaving": {"value": 1.6},
            "assessment": "nahe an der Linie",
        }
    },
    "findings": [{"position": 10, "level": "warn", "message": "LNA nahe am Kern"}],
    "disclaimers": ["Die Punktzahl ist eine Rangfolge, keine Vorhersage."],
    "settings": {"Na": "50 mM", "Reaktionstemperatur": "37 °C"},
}


@pytest.fixture
def bericht() -> str:
    return report.candidate_report(DATEN)


def test_der_bericht_ist_eine_eigenstaendige_seite(bericht):
    assert bericht.startswith("<!doctype html>")
    assert "</html>" in bericht
    # Keine fremden Adressen: der Bericht muss offline funktionieren.
    assert "http://" not in bericht and "https://" not in bericht


def test_alles_geforderte_steht_drin(bericht):
    """PHASEN.md 6.6 zählt auf, was zusammengefasst werden muss."""
    for stueck in (
        "Sequenz", "Masse", "Ladungsleiter", "Tm 5'-Arm", "ΣΔG",
        "Eigenfaltung", "Zugänglichkeit", "Punktzahl", "Befunde",
        "In-line-Winkel",
    ):
        assert stueck in bericht, f"{stueck} fehlt im Bericht"


def test_zahlen_stehen_mit_einheit_und_komma(bericht):
    assert "10 253,26 g/mol" in bericht
    assert "37,9 °C" in bericht
    assert "168,2 °" in bericht


def test_datum_und_einstellungen_im_fuss(bericht):
    """Damit die Rechnung reproduzierbar ist."""
    from datetime import datetime

    assert datetime.now().strftime("%d.%m.%Y") in bericht
    assert "Na: 50 mM" in bericht
    assert "Reaktionstemperatur: 37 °C" in bericht


def test_der_hinweis_zur_punktzahl_steht_oben(bericht):
    assert "keine Vorhersage" in bericht


def test_der_bericht_rechnet_nichts_nach():
    """Eine zweite Rechnung könnte von der Anzeige abweichen."""
    veraendert = dict(DATEN, score=0.111)
    assert "0,111" in report.candidate_report(veraendert)


def test_bilder_werden_eingebettet():
    html = report.candidate_report(
        DATEN, images={"Paarungsdarstellung": "<svg><text>Bild</text></svg>"}
    )
    assert "Paarungsdarstellung" in html
    assert "<text>Bild</text>" in html


def test_leere_angaben_erfinden_nichts():
    html = report.candidate_report({"name": "Leer"})
    assert "—" in html
    assert "None" not in html


# ------------------------------------------------- mitgeschickte Bilder


def test_skript_im_bild_wird_entfernt():
    """Ein SVG kommt über eine Anfrage — und wird deshalb geprüft."""
    sauber = report.sanitise_svg("<svg><script>alert(1)</script><text>ok</text></svg>")
    assert "<script>" not in sauber
    assert "<text>ok</text>" in sauber


def test_ereignis_attribute_fliegen_raus():
    sauber = report.sanitise_svg('<svg onload="x()"><rect onclick=\'y()\'/></svg>')
    assert "onload" not in sauber and "onclick" not in sauber
    assert "<rect" in sauber


@pytest.mark.parametrize(
    "boese",
    [
        '<svg><a href="javascript:alert(1)">x</a></svg>',
        '<svg><a href="&#106;avascript:alert(1)">x</a></svg>',
        '<svg><a xlink:href="JavaScript:alert(1)">x</a></svg>',
    ],
)
def test_verweise_werden_nach_erlaubnisliste_gefiltert(boese):
    """Ein `javascript:` wegzustreichen reicht nicht — es kommt verkleidet."""
    sauber = report.sanitise_svg(boese)
    assert "href" not in sauber


def test_was_eine_zeichnung_braucht_bleibt_stehen():
    svg = '<svg><use href="#muster"/><image href="data:image/png;base64,AA"/></svg>'
    assert report.sanitise_svg(svg) == svg


def test_eingebettete_fremdinhalte_fliegen_raus():
    sauber = report.sanitise_svg(
        "<svg><foreignObject><iframe src='x'></iframe></foreignObject></svg>"
    )
    assert "foreignObject" not in sauber and "iframe" not in sauber


def test_text_wird_maskiert():
    html = report.build_html("<b>Titel</b>", [])
    assert "&lt;b&gt;Titel&lt;/b&gt;" in html
