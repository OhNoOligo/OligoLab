"""Spaltstellen und Kandidaten (PHASEN.md 5.2 und 5.3).

Der Test, den PHASEN.md verlangt, steht oben: ein Transkript mit einer
bekannten guten Spaltstelle, und die muss weit oben in der Rangliste stehen.
"""

from __future__ import annotations

import pytest

from app import design, fold_target as ft, melting, scan

#: Ein Transkript, dessen Antwort man kennt.
#:
#: A und C paaren untereinander nicht — der mittlere Abschnitt bleibt also
#: offen, und die Arme, die dort binden, werden G/T-reich und binden
#: ordentlich. Links und rechts stabile Haarnadeln, deren Junktionen
#: verschlossen sind.
OFFEN_LINKS = "ACACCACACCACAC"
OFFEN_RECHTS = "ACCACACCACACCA"
HAARNADEL = "GGGGGCCCCUUUUGGGGCCCCC"
FUELLER = "AAAAAAAA"
TRANSKRIPT = (
    HAARNADEL + FUELLER + OFFEN_LINKS + "GU" + OFFEN_RECHTS + FUELLER + HAARNADEL
)
#: 1-basierte Position des G in der bekannten guten GU-Junktion.
GUTE_STELLE = len(HAARNADEL) + len(FUELLER) + len(OFFEN_LINKS) + 1


@pytest.fixture(scope="module")
def profil():
    return ft.accessibility(TRANSKRIPT, probe_length=15)


@pytest.fixture(scope="module")
def spaltstellen(profil):
    return scan.scan(
        TRANSKRIPT, folding=ft.fold_region(TRANSKRIPT), accessibility=profil
    )


@pytest.fixture(scope="module")
def entwurf(spaltstellen, profil):
    return design.design(TRANSKRIPT, spaltstellen, accessibility=profil)


# ================================================== der geforderte Test


def test_bekannte_gute_spaltstelle_steht_oben(entwurf):
    """Der Test aus PHASEN.md, Abschnitt 5."""
    assert entwurf.candidates, "es muss Kandidaten geben"

    positionen = [c.site.position for c in entwurf.candidates]
    assert GUTE_STELLE in positionen, "die bekannte Stelle muss dabei sein"

    rang = positionen.index(GUTE_STELLE) + 1
    assert rang == 1, f"die bekannte gute Stelle steht auf Rang {rang}"

    bester = entwurf.candidates[0]
    assert bester.site.junction == "GU"
    assert bester.rating == "good"
    assert bester.binds


def test_die_vergrabenen_junktionen_stehen_darunter(entwurf):
    """Die Gegenprobe — sonst sagte der Test oben nichts."""
    gut = entwurf.candidates[0]
    for anderer in entwurf.candidates[1:]:
        assert anderer.score < gut.score
        assert (anderer.site.accessibility or 0) < (gut.site.accessibility or 0)


# ================================================== 5.2 Spaltstellen


def test_nur_purin_pyrimidin_junktionen(spaltstellen):
    for stelle in spaltstellen.sites:
        assert stelle.junction[0] in scan.PURINES
        assert stelle.junction[1] in scan.PYRIMIDINES


def test_guete_der_junktionen():
    """AU und GU gut, GC mäßig, AC schlecht (PHASEN.md 5.2)."""
    assert scan.JUNCTION_QUALITY == {
        "AU": "gut",
        "GU": "gut",
        "GC": "mäßig",
        "AC": "schlecht",
    }


def test_ac_wird_standardmaessig_ausgeblendet():
    sequenz = "AAACAAACAAAC"  # drei AC-Junktionen
    ohne = scan.scan(sequenz)
    assert ohne.sites == []
    assert ohne.hidden_poor == 3
    assert ohne.note and "AC-Junktion" in ohne.note
    # Aber die Zählung nennt sie trotzdem.
    assert ohne.counts["AC"] == 3


def test_ac_laesst_sich_einblenden():
    """Ausblenden ist eine Anzeigeentscheidung, keine Zensur."""
    mit = scan.scan("AAACAAACAAAC", include_poor=True)
    assert len(mit.sites) == 3
    assert all(s.quality == "schlecht" for s in mit.sites)
    assert mit.hidden_poor == 0


def test_spaltstelle_liegt_zwischen_purin_und_pyrimidin():
    stellen = scan.scan("AAAGUAAA").sites
    assert len(stellen) == 1
    assert stellen[0].position == 4           # das G
    assert stellen[0].cut_between == (4, 5)   # geschnitten wird dahinter


def test_struktur_wird_mitgeteilt(spaltstellen):
    """PHASEN.md 5.2: ist das Purin ungepaart und das Pyrimidin gepaart?"""
    mit_struktur = [s for s in spaltstellen.sites if s.matches_pattern is not None]
    assert mit_struktur, "mit Faltung muss es eine Aussage geben"
    for stelle in mit_struktur:
        assert stelle.purine_unpaired in (0.0, 1.0)
        assert stelle.pyrimidine_paired in (0.0, 1.0)


def test_ohne_faltung_keine_strukturaussage():
    """Lieber keine Aussage als eine erfundene."""
    stellen = scan.scan("AAAGUAAA").sites
    assert stellen[0].matches_pattern is None
    assert stellen[0].purine_unpaired is None


def test_bereich_eingrenzen():
    ergebnis = scan.scan(TRANSKRIPT, start=GUTE_STELLE - 2, end=GUTE_STELLE + 2)
    assert all(
        GUTE_STELLE - 2 <= s.position <= GUTE_STELLE + 2 for s in ergebnis.sites
    )


def test_zu_kurz_fuer_eine_junktion():
    assert scan.scan("A").sites == []
    assert scan.scan("").sites == []


# ============================================= 5.3 Arme und Orientierung


def test_arme_binden_die_richtige_seite():
    """Ein DNAzym bindet antiparallel.

    Sein 3'-Arm paart mit dem Stück STROMAUF der Spaltstelle, sein 5'-Arm mit
    dem Stück STROMAB. Wäre das vertauscht, bände das ganze Programm an der
    falschen Stelle — und es fiele niemandem auf, weil die Zahlen plausibel
    aussähen.
    """
    ziel = "AAAAAGUCCCCC"
    stelle = scan.CleavageSite(position=6, junction="GU", quality="gut")
    kern = design.load_cores()[0]
    einst = design.DesignSettings(arm5_length=6, arm3_length=6)

    kandidat = design.build(ziel, stelle, einst, kern)
    assert kandidat is not None
    assert kandidat.target_upstream == "AAAAAG"
    assert kandidat.target_downstream == "UCCCCC"
    assert kandidat.arm5 == "GGGGGA"   # Komplement von stromab
    assert kandidat.arm3 == "CTTTTT"   # Komplement von stromauf
    assert kandidat.sequence == "GGGGGA" + kern.sequence + "CTTTTT"


def test_komplement_ist_dna():
    """Das DNAzym ist DNA: aus einem A im Ziel wird ein T, kein U."""
    assert design.reverse_complement("AAAA") == "TTTT"
    assert design.reverse_complement("UUUU") == "AAAA"
    assert design.reverse_complement("ACGU") == "ACGT"
    assert design.reverse_complement("GGCC") == "GGCC"


def test_ungleiche_armlaengen():
    ziel = "A" * 20 + "GU" + "C" * 20
    stelle = scan.CleavageSite(position=21, junction="GU", quality="gut")
    einst = design.DesignSettings(arm5_length=12, arm3_length=7)
    kandidat = design.build(ziel, stelle, einst, design.load_cores()[0])
    assert len(kandidat.arm5) == 12
    assert len(kandidat.arm3) == 7


def test_stelle_am_rand_ergibt_keinen_kandidaten():
    """Lieber keinen Kandidaten als einen mit gestutztem Arm.

    Ein gestutzter Arm spielte in der Rangliste mit, als wäre er vollwertig.
    """
    ziel = "AGUCCCCCCCCCCCCCCCCCCC"
    stelle = scan.CleavageSite(position=2, junction="GU", quality="gut")
    einst = design.DesignSettings(arm5_length=9, arm3_length=9)
    assert design.build(ziel, stelle, einst, design.load_cores()[0]) is None


def test_kandidat_traegt_den_kern(entwurf):
    kern = design.load_cores()[0]
    for kandidat in entwurf.candidates:
        assert kern.sequence in kandidat.sequence
        assert kandidat.core == kern.sequence
        assert len(kandidat.sequence) == (
            len(kandidat.arm5) + len(kern.sequence) + len(kandidat.arm3)
        )


# =============================================== 5.3 Bewertung


def test_jedes_kriterium_aus_der_tabelle(entwurf):
    schluessel = {k.key for k in entwurf.candidates[0].criteria}
    assert schluessel == {
        "junction",
        "arm_dg",
        "balance",
        "self_fold",
        "accessibility",
    }


def test_punktzahl_liegt_zwischen_null_und_eins(entwurf):
    for kandidat in entwurf.candidates:
        assert 0.0 <= kandidat.score <= 1.0


def test_fehlendes_kriterium_hebt_und_senkt_nicht():
    """Ohne Zugänglichkeit soll die Punktzahl nicht einfach fallen."""
    stellen = scan.scan(TRANSKRIPT)
    ohne = design.design(TRANSKRIPT, stellen)           # keine Zugänglichkeit
    for kandidat in ohne.candidates:
        zugang = next(k for k in kandidat.criteria if k.key == "accessibility")
        assert zugang.score is None
        assert kandidat.warnings
        assert any("Zugänglichkeit" in w for w in kandidat.warnings)
        assert kandidat.score > 0.0


def test_gewichte_wirken():
    stellen = scan.scan(TRANSKRIPT, accessibility=None)
    nur_junktion = design.DesignSettings(
        weight_junction=1.0, weight_arm_dg=0.0, weight_balance=0.0,
        weight_self_fold=0.0, weight_accessibility=0.0,
    )
    ergebnis = design.design(TRANSKRIPT, stellen, settings=nur_junktion)
    for kandidat in ergebnis.candidates:
        erwartet = {"gut": 1.0, "mäßig": 0.5, "schlecht": 0.0}[kandidat.site.quality]
        assert kandidat.score == pytest.approx(erwartet, abs=1e-9)


def test_ampel_wird_nicht_gruen_wenn_die_arme_nicht_binden():
    """Binden ist die Voraussetzung, nicht eines von sechs Kriterien.

    Ein positives ΔG heißt: der Duplex ist bei dieser Temperatur nicht stabil.
    Die übrigen fünf Kriterien dürfen so etwas nicht grün färben.
    """
    # Poly-A-Ziel: die Arme werden Poly-T und binden bei 37 °C nicht.
    ziel = "A" * 20 + "GU" + "A" * 20
    stellen = scan.scan(ziel)
    ergebnis = design.design(ziel, stellen)
    kandidat = ergebnis.candidates[0]

    assert kandidat.arm_dg_sum > 0
    assert kandidat.binds is False
    assert kandidat.rating != "good"
    assert any("binden" in w for w in kandidat.warnings)


def test_rangfolge_beste_zuerst(entwurf):
    punkte = [c.score for c in entwurf.candidates if not c.excluded]
    assert punkte == sorted(punkte, reverse=True)


def test_der_vorbehalt_steht_in_der_antwort(entwurf):
    """PHASEN.md 5.3: der Satz gehört in die Oberfläche, nicht nur in den Code."""
    assert "Rangfolge" in entwurf.disclaimer
    assert "63" in entwurf.disclaimer and "73" in entwurf.disclaimer
    assert entwurf.as_dict()["disclaimer"] == design.DISCLAIMER


def test_deckel_fuer_lange_transkripte():
    lang = ("ACACCACACGU" * 60)
    stellen = scan.scan(lang)
    ergebnis = design.design(lang, stellen, limit=5)
    assert len(ergebnis.candidates) <= 5
    assert ergebnis.scan_note and "durchgerechnet" in ergebnis.scan_note


# ============================================ 5.4 Mehrfachumsatz


def test_mehrfachumsatz_zu_fest(entwurf):
    kandidat = entwurf.candidates[0]
    # Bei 4 °C liegt jeder brauchbare Arm weit darüber.
    befund = design.turnover(kandidat, 4.0)
    assert befund.verdict == "zu fest"
    assert "Produkt" in befund.message


def test_mehrfachumsatz_zu_locker(entwurf):
    befund = design.turnover(entwurf.candidates[0], 90.0)
    assert befund.verdict == "zu locker"
    assert "längere Arme" in befund.message


def test_mehrfachumsatz_passend(entwurf):
    kandidat = entwurf.candidates[0]
    mittel = design.turnover(kandidat, 37.0).tm_mean
    assert design.turnover(kandidat, mittel).verdict == "passend"


def test_ohne_tm_keine_aussage():
    kandidat = design.Candidate(
        site=scan.CleavageSite(1, "GU", "gut"),
        sequence="", arm5="", arm3="", core="", core_id="10-23",
        target_upstream="", target_downstream="",
    )
    assert design.turnover(kandidat, 37.0).verdict == "unbekannt"


def test_schwelle_ist_eine_hausregel():
    assert design.TURNOVER_MARGIN_C == 10.0


# ================================================= Uebergabe


def test_kandidat_laesst_sich_als_oligo_lesen(entwurf, registry):
    oligo = design.as_oligo(entwurf.candidates[0], registry)
    assert oligo.length == len(entwurf.candidates[0].sequence)
    assert oligo.monomers[0].code in "ACGT"


# =============================================== 5.5 Muster aufbringen

#: Das Regressions-DNAzym aus CLAUDE.md, Arm 9 + Kern 15 + Arm 9.
DNAZYM = "TTGGGGTAAGGCTAGCTACAACGAGGTGCATGT"
KERN = (10, 24)


def test_thioat_nur_in_den_armen(registry):
    ergebnis = design.apply_pattern(
        DNAZYM, "arms_phosphorothioate", core_range=KERN, registry=registry
    )
    assert ergebnis.blocked is False
    assert ergebnis.touched_core is False
    # 8 Bindungen im 5'-Arm, 8 im 3'-Arm, plus die beiden Bindungen vom Arm
    # in den Kern — die gehören noch zum Arm, weil nur eine Seite im Kern liegt.
    assert len(ergebnis.changes) == 18
    assert "GGCTAGCTACAACGA" in ergebnis.sequence, "der Kern bleibt unberührt"
    assert ergebnis.sequence.startswith("T*T*G*")


def test_lna_setzt_sich_an_die_enden(registry):
    ergebnis = design.apply_pattern(
        DNAZYM, "lna_ends", core_range=KERN, count=3, registry=registry
    )
    assert ergebnis.sequence.startswith("[LNA-T][LNA-T][LNA-G]")
    assert ergebnis.sequence.endswith("[LNA-T][LNA-G][LNA-T]")
    assert len(ergebnis.changes) == 6
    assert ergebnis.touched_core is False


def test_galnac_haengt_vorn(registry):
    ergebnis = design.apply_pattern(
        DNAZYM, "galnac_5prime", core_range=KERN, registry=registry
    )
    assert ergebnis.sequence.startswith("/5GalNAc/")
    assert len(ergebnis.changes) == 1


def test_eingriff_in_den_kern_wird_blockiert(registry):
    """CLAUDE.md, Regel 6 — nie stillschweigend."""
    ergebnis = design.apply_pattern(
        DNAZYM, "replace_position", core_range=KERN,
        position=13, code="LNA", registry=registry,
    )
    assert ergebnis.blocked is True
    assert ergebnis.sequence == DNAZYM, "nichts darf geändert worden sein"
    assert "katalytischen Kern" in (ergebnis.message or "")


def test_eingriff_in_den_kern_nach_bestaetigung(registry):
    ergebnis = design.apply_pattern(
        DNAZYM, "replace_position", core_range=KERN,
        position=13, code="LNA", allow_core=True, registry=registry,
    )
    assert ergebnis.blocked is False
    assert ergebnis.touched_core is True
    assert "ACHTUNG" in (ergebnis.message or "")
    assert ergebnis.changes[0].in_core is True


def test_unbekanntes_muster(registry):
    """Ein unbekanntes Muster ist ein Aufruffehler, keine Nutzerentscheidung.

    `blocked` ist dem Kernschutz vorbehalten — der heißt „darf, aber nur mit
    Bestätigung". Hier dagegen gibt es nichts zu bestätigen.
    """
    with pytest.raises(ValueError, match="Unbekanntes Muster"):
        design.apply_pattern(DNAZYM, "irgendwas", registry=registry)


# =========================================== 5.5 vorher gegen nachher


@pytest.fixture
def stelle():
    return scan.CleavageSite(50, "GU", "gut", accessibility=0.8)


def test_vergleich_zeigt_was_sich_aendert(registry, stelle):
    vorher = design.snapshot(DNAZYM, 9, 15, site=stelle, registry=registry)
    nachher_sequenz = design.apply_pattern(
        DNAZYM, "lna_ends", core_range=KERN, count=3, registry=registry
    ).sequence
    nachher = design.snapshot(nachher_sequenz, 9, 15, site=stelle, registry=registry)

    # Die Länge zählt Bausteine, nicht Zeichen.
    assert vorher.length == nachher.length == 33
    # Sechs LNA, jede 12,0 Da mehr (Methylenbrücke).
    assert nachher.mass - vorher.mass == pytest.approx(72.0, abs=0.05)
    assert vorher.mass == pytest.approx(10241.26, abs=0.01)


def test_unveraenderter_tm_wird_als_genaehert_erklaert(registry, stelle):
    """Der Tm bleibt gleich, weil die Tabelle keine LNA kennt.

    Ohne diesen Vermerk läse sich die Vorher-Nachher-Tabelle wie „LNA bewirkt
    nichts" — gemeint ist „das Modell sieht es nicht" (CLAUDE.md, Regel 3).
    """
    vorher = design.snapshot(DNAZYM, 9, 15, site=stelle, registry=registry)
    assert vorher.tm_approximated == []

    nachher_sequenz = design.apply_pattern(
        DNAZYM, "lna_ends", core_range=KERN, count=3, registry=registry
    ).sequence
    nachher = design.snapshot(nachher_sequenz, 9, 15, site=stelle, registry=registry)

    assert nachher.tm5 == pytest.approx(vorher.tm5, abs=0.001)
    assert nachher.tm_approximated, "die Näherung muss benannt werden"
    assert all("LNA" in e for e in nachher.tm_approximated)
    assert len(nachher.tm_approximated) == 6


def test_vergleich_ohne_spaltstelle_laesst_die_punktzahl_weg(registry):
    """Ohne Ziel gibt es keine Zugänglichkeit und damit keine Bewertung."""
    ohne = design.snapshot(DNAZYM, 9, 15, registry=registry)
    assert ohne.score is None and ohne.rating is None
    assert ohne.mass is not None and ohne.tm5 is not None


def test_thioat_hebt_die_masse_aber_nicht_den_tm(registry, stelle):
    vorher = design.snapshot(DNAZYM, 9, 15, site=stelle, registry=registry)
    nachher = design.snapshot(
        design.apply_pattern(
            DNAZYM, "arms_phosphorothioate", core_range=KERN, registry=registry
        ).sequence,
        9, 15, site=stelle, registry=registry,
    )
    # 18 Thioate, je +15,977 Da (O gegen S).
    assert nachher.mass - vorher.mass == pytest.approx(18 * 15.977, abs=0.5)
    assert nachher.tm5 == pytest.approx(vorher.tm5, abs=0.001)


# ======================================= Regression: der Kernschutz greift
#
# Vorher hing der Schutz daran, dass der Aufrufer `core_range` mitschickte.
# Wer es vergaß, veränderte den Kern stillschweigend — genau das, was
# CLAUDE.md, Regel 6 verbietet.


def test_kern_wird_auch_ohne_angabe_geschuetzt(registry):
    ergebnis = design.apply_pattern(
        DNAZYM, "replace_position", position=13, code="LNA", registry=registry
    )
    assert ergebnis.blocked is True
    assert ergebnis.sequence == DNAZYM
    assert "katalytischen Kern" in (ergebnis.message or "")


def test_muster_greifen_ohne_angabe_nicht_in_den_kern(registry):
    """Auch ein Muster mit zu großer Reichweite bleibt in den Armen."""
    ergebnis = design.apply_pattern(DNAZYM, "lna_ends", count=20, registry=registry)
    assert ergebnis.touched_core is False
    kern_positionen = {c.position for c in ergebnis.changes if c.position}
    assert kern_positionen.isdisjoint(range(10, 25))


def test_strang_ohne_kern_sagt_es(registry):
    """Kein Kern ist kein Fehler — aber es muss dastehen."""
    ergebnis = design.apply_pattern("ACGTACGTACGT", "lna_ends", count=2, registry=registry)
    assert ergebnis.blocked is False
    assert "kein katalytischer Kern" in (ergebnis.message or "")
