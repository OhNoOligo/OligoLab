"""Kritische Stellen (PHASEN.md 3.3).

Der Test, den PHASEN.md ausdrücklich verlangt, steht ganz oben: ein DNAzym mit
absichtlicher LNA im katalytischen Kern muss die kritische Warnung auslösen.
"""

from __future__ import annotations

import pytest

from app import critical, fold
from app.dnazyme import detect_parts
from app.notation import parse

from .conftest import REFERENCE_SEQUENCE

# Kern 10-23 an Position 10 bis 24; Position 13 ist die vierte Kernposition.
LNA_IM_KERN = "TTGGGGTAAGGC[LNA-T]AGCTACAACGAGGTGCATGT"


def befunde(sequenz: str, registry, mit_faltung: bool = True):
    oligo = parse(sequenz, registry)
    teile = detect_parts(oligo, registry)
    faltung = fold.compute(oligo) if mit_faltung else None
    return oligo, teile, critical.compute(oligo, teile, faltung, registry)


# ===================================================== der geforderte Test


def test_lna_im_katalytischen_kern_ist_kritisch(registry):
    """Der Test aus PHASEN.md, Abschnitt 3.

    Das ist der wichtigste Befund des ganzen Programms: ein Eingriff im Kern
    kostet häufig die gesamte Aktivität, und man sieht es dem Strang nicht an.
    """
    _, teile, ergebnis = befunde(LNA_IM_KERN, registry)

    assert teile.found, "ohne erkannten Kern kann der Befund nicht entstehen"

    treffer = [f for f in ergebnis.findings if f.code == "core_modification"]
    assert len(treffer) == 1, "genau ein Befund erwartet"

    befund = treffer[0]
    assert befund.severity == "kritisch"
    assert befund.start == befund.end == 13
    assert "LNA" in befund.title
    assert "Kern" in befund.message
    assert ergebnis.worst == "kritisch"
    assert ergebnis.as_dict()["counts"]["kritisch"] == 1


def test_dieselbe_lna_ausserhalb_des_kerns_ist_kein_kritischer_befund(registry):
    """Die Gegenprobe. Sonst wäre der Test oben nichtssagend."""
    _, _, ergebnis = befunde(
        "TTGG[LNA-T]GTAAGGCTAGCTACAACGAGGTGCATGT", registry
    )
    assert not [f for f in ergebnis.findings if f.code == "core_modification"]


def test_unmodifizierter_referenzstrang_hat_keinen_kritischen_befund(registry):
    _, _, ergebnis = befunde(REFERENCE_SEQUENCE, registry)
    assert not [f for f in ergebnis.findings if f.severity == "kritisch"]


# ========================================== Modifikation im Kern, Feinheiten


def test_unbekannt_erprobt_zaehlt_wie_nicht_erprobt(registry):
    """`unbekannt` ist kein Freibrief.

    Wer nicht weiß, ob ein Baustein im Kern funktioniert, hat denselben Grund
    zur Vorsicht wie jemand, der weiß, dass er es nicht tut.
    """
    # rG (Code Z) hat core_tested: unbekannt.
    _, _, ergebnis = befunde(
        "TTGGGGTAAZGCTAGCTACAACGAGGTGCATGT", registry
    )
    treffer = [f for f in ergebnis.findings if f.code == "core_modification"]
    assert len(treffer) == 1
    assert treffer[0].severity == "kritisch"
    assert "unbekannt" in treffer[0].message


def test_befund_entsteht_auch_ohne_faltung(registry):
    """Ohne ViennaRNA fehlen nur die strukturellen Befunde."""
    _, _, ergebnis = befunde(LNA_IM_KERN, registry, mit_faltung=False)
    assert any(f.code == "core_modification" for f in ergebnis.findings)
    assert any("Haarnadeln" in eintrag for eintrag in ergebnis.skipped)


def test_ohne_kern_wird_nicht_auf_kern_geprueft(registry):
    _, teile, ergebnis = befunde("AC[LNA-T]GTACGTACGT", registry)
    assert teile.found is False
    assert not [f for f in ergebnis.findings if f.code == "core_modification"]
    assert any("kein katalytischer Kern" in e for e in ergebnis.skipped)


# ============================================================= Armlängen


def test_kurzer_arm_ist_eine_warnung(registry):
    """Fünf Nukleotide, Schwelle ist sieben."""
    _, _, ergebnis = befunde("ACGTA" + "GGCTAGCTACAACGA" + "ACGTACGTA", registry)
    treffer = [f for f in ergebnis.findings if f.code == "short_arm"]
    assert len(treffer) == 1
    assert treffer[0].severity == "warnung"
    assert (treffer[0].start, treffer[0].end) == (1, 5)


def test_armlaengen_von_neun_sind_in_ordnung(registry):
    _, _, ergebnis = befunde(REFERENCE_SEQUENCE, registry)
    assert not [f for f in ergebnis.findings if f.code == "short_arm"]
    assert not [f for f in ergebnis.findings if f.code == "arm_imbalance"]


def test_stark_unterschiedliche_arme_sind_ein_hinweis(registry):
    """Sieben gegen zwölf: Unterschied fünf, Schwelle drei."""
    _, _, ergebnis = befunde(
        "ACGTACG" + "GGCTAGCTACAACGA" + "ACGTACGTACGT", registry
    )
    treffer = [f for f in ergebnis.findings if f.code == "arm_imbalance"]
    assert len(treffer) == 1
    assert treffer[0].severity == "hinweis"
    assert "Hausregel" in (treffer[0].detail or "")


# ====================================================== gleiche Basen in Folge


def test_vier_gleiche_basen_sind_ein_hinweis(registry):
    """Die Referenzsequenz hat GGGG an Position 3 bis 6."""
    _, _, ergebnis = befunde(REFERENCE_SEQUENCE, registry)
    treffer = [f for f in ergebnis.findings if f.code == "homopolymer"]
    assert len(treffer) == 1
    assert (treffer[0].start, treffer[0].end) == (3, 6)
    assert treffer[0].severity == "hinweis"


def test_drei_gleiche_basen_reichen_nicht(registry):
    _, _, ergebnis = befunde("ACGTTTACGTACGTACGT", registry)
    assert not [f for f in ergebnis.findings if f.code == "homopolymer"]


def test_lauf_am_ende_wird_gefunden(registry):
    """Ein Lauf, der an der letzten Position endet, darf nicht durchrutschen."""
    _, _, ergebnis = befunde("ACGTACGTAAAA", registry)
    treffer = [f for f in ergebnis.findings if f.code == "homopolymer"]
    assert [(f.start, f.end) for f in treffer] == [(9, 12)]


def test_mehrere_laeufe(registry):
    _, _, ergebnis = befunde("AAAACGTTTTT", registry)
    treffer = sorted(
        (f for f in ergebnis.findings if f.code == "homopolymer"),
        key=lambda f: f.start,
    )
    assert [(f.start, f.end) for f in treffer] == [(1, 4), (7, 11)]


# ============================================================ G-Quadruplex


def test_g_quadruplex_muster(registry):
    """Vier Läufe aus mindestens drei G, Schleifen von eins bis sieben."""
    sequenz = "GGGTAGGGTAGGGTAGGG"
    _, _, ergebnis = befunde(sequenz, registry)
    treffer = [f for f in ergebnis.findings if f.code == "g_quadruplex"]
    assert len(treffer) == 1
    assert treffer[0].severity == "warnung"
    assert treffer[0].start == 1


def test_drei_g_laeufe_sind_kein_quadruplex(registry):
    _, _, ergebnis = befunde("GGGTAGGGTAGGGTACGT", registry)
    assert not [f for f in ergebnis.findings if f.code == "g_quadruplex"]


def test_zu_grosser_abstand_ist_kein_quadruplex(registry):
    """Acht Nukleotide zwischen den Läufen, erlaubt sind bis zu sieben."""
    _, _, ergebnis = befunde(
        "GGG" + "ACGTACGT" + "GGG" + "ACGTACGT" + "GGG" + "ACGTACGT" + "GGG",
        registry,
    )
    assert not [f for f in ergebnis.findings if f.code == "g_quadruplex"]


# ============================================================== Selbstdimer


def test_selbstdimer_wird_gemeldet(registry):
    _, _, ergebnis = befunde(REFERENCE_SEQUENCE, registry)
    treffer = [f for f in ergebnis.findings if f.code == "homodimer"]
    assert len(treffer) == 1
    assert treffer[0].severity == "warnung"
    # Betrifft den ganzen Strang.
    assert (treffer[0].start, treffer[0].end) == (1, 33)


def test_strang_ohne_selbstpaarung_meldet_nichts(registry):
    _, _, ergebnis = befunde("AAAAAAAAAAAAAAAAAAAA", registry)
    assert not [f for f in ergebnis.findings if f.code == "homodimer"]


# ================================================================ Haarnadeln


def test_haarnadel_ausserhalb_des_kerns_ist_eine_warnung(registry):
    """Stabile Haarnadel in einem verlängerten 5'-Arm."""
    sequenz = "GGGGGCCCCTTTTGGGGCCCCC" + "GGCTAGCTACAACGA" + "ACGTACGTA"
    _, teile, ergebnis = befunde(sequenz, registry)
    assert teile.found
    treffer = [f for f in ergebnis.findings if f.code == "hairpin"]
    assert treffer, "die Haarnadel muss gefunden werden"
    assert all(f.severity == "warnung" for f in treffer)


def test_schwache_struktur_loest_nichts_aus(registry):
    """Über der Schwelle von -2 kcal/mol wird nicht gemeldet."""
    _, _, ergebnis = befunde(REFERENCE_SEQUENCE, registry)
    assert not [
        f for f in ergebnis.findings if f.code in ("hairpin", "hairpin_core")
    ]


# =============================================================== Sortierung


def test_befunde_nach_schweregrad_sortiert(registry):
    _, _, ergebnis = befunde(LNA_IM_KERN, registry)
    reihenfolge = [critical.SEVERITY_ORDER[f.severity] for f in ergebnis.findings]
    assert reihenfolge == sorted(reihenfolge)
    assert ergebnis.findings[0].severity == "kritisch"


def test_schwellen_stehen_in_der_antwort(registry):
    """Damit die Oberfläche sagen kann, woran gemessen wurde."""
    _, _, ergebnis = befunde(REFERENCE_SEQUENCE, registry)
    schwellen = ergebnis.as_dict()["thresholds"]
    assert schwellen["hairpin_kcal"] == -2.0
    assert schwellen["homodimer_kcal"] == -6.0
    assert schwellen["min_arm_length"] == 7


def test_jeder_befund_hat_bereich_und_erklaerung(registry):
    """PHASEN.md 3.3: Positionsbereich, Schweregrad und ein Satz Erklärung."""
    for sequenz in (REFERENCE_SEQUENCE, LNA_IM_KERN, "GGGTAGGGTAGGGTAGGG"):
        _, _, ergebnis = befunde(sequenz, registry)
        for befund in ergebnis.findings:
            assert befund.start >= 1
            assert befund.end >= befund.start
            assert befund.title
            assert befund.message.endswith(".")
            assert befund.severity in critical.SEVERITY_ORDER


def test_by_position(registry):
    _, _, ergebnis = befunde(LNA_IM_KERN, registry)
    je_position = ergebnis.by_position()
    assert any(f.code == "core_modification" for f in je_position[13])


def test_ohne_befunde_ist_worst_none(registry):
    """Nur A und C: die paaren mit nichts, also gibt es auch nichts zu melden.

    `ACGTACGT...` taugt dafuer nicht — das faltet selbst zu einer Haarnadel
    mit -3,6 kcal/mol und loest zu Recht eine Warnung aus.
    """
    _, _, ergebnis = befunde("ACACACACACACACAC", registry)
    assert ergebnis.findings == []
    assert ergebnis.worst is None


@pytest.mark.parametrize(
    "schwelle,wert",
    [
        ("HAIRPIN_THRESHOLD", -2.0),
        ("HOMODIMER_THRESHOLD", -6.0),
        ("MIN_ARM_LENGTH", 7),
        ("HOMOPOLYMER_RUN", 4),
    ],
)
def test_schwellen_wie_in_phasen_md(schwelle, wert):
    assert getattr(critical, schwelle) == wert
