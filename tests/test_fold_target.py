"""Struktur und Zugaenglichkeit der Ziel-RNA (PHASEN.md 4.3).

Der Test, den PHASEN.md verlangt, steht oben: ein Transkript von etwa 500
Basen, und das Zugaenglichkeitsprofil muss an bekannten Haarnadeln einbrechen.
"""

from __future__ import annotations

import pytest

from app import fold, fold_target as ft

pytestmark = pytest.mark.skipif(
    not fold.VIENNA_AVAILABLE, reason="ViennaRNA ist nicht installiert"
)

#: Eine Haarnadel, die sicher faltet: neun Basenpaare um eine Schleife.
HAARNADEL = "GGGGGCCCCUUUUGGGGCCCCC"   # 22 nt
#: Ein Abschnitt, der mit nichts paart.
OFFEN = "AAAAAAAAAAAAAAAAAAAAAAAAAA"    # 26 nt
#: Zehn Wiederholungen ergeben ein Transkript von 480 Basen.
TRANSKRIPT = (OFFEN + HAARNADEL) * 10

#: Mitten der offenen Abschnitte und der Haarnadelstaemme, 1-basiert.
OFFENE_MITTEN = [i * 48 + 5 for i in range(10)]
HAARNADEL_MITTEN = [i * 48 + 28 for i in range(10)]


# ================================================== der geforderte Test


def test_zugaenglichkeitsprofil_bricht_an_haarnadeln_ein():
    """Der Test aus PHASEN.md, Abschnitt 4.

    Ohne diesen Einbruch waere das Profil wertlos: es soll ja gerade zeigen,
    wo eine Sonde ankommt und wo nicht.
    """
    assert len(TRANSKRIPT) == 480

    profil = ft.accessibility(TRANSKRIPT, probe_length=15)
    assert profil.available

    offen = [profil.value_at(p) for p in OFFENE_MITTEN]
    verschlossen = [profil.value_at(p) for p in HAARNADEL_MITTEN]

    assert all(wert is not None for wert in offen + verschlossen)
    assert min(offen) > 0.5, "die offenen Abschnitte müssen zugänglich sein"
    assert max(verschlossen) < 0.01, "die Haarnadeln müssen einbrechen"
    # Der Unterschied ist kein Rauschen, sondern Größenordnungen.
    assert min(offen) / max(max(verschlossen), 1e-12) > 100


# ========================================================= Verankerung


def test_profil_ist_am_fensteranfang_verankert():
    """`profile[p]` heißt: ab Position p sind die nächsten L offen.

    ViennaRNA gibt das Fenster zurück, das an einer Position ENDET. Wird das
    nicht umgerechnet, zeigt das ganze Profil um L-1 Positionen verschoben —
    und man legt die Sonde an die falsche Stelle.
    """
    sequenz = OFFEN + HAARNADEL + OFFEN
    profil = ft.accessibility(sequenz, probe_length=10)

    # Position 1 bis 17: das Fenster 1..10 liegt ganz im offenen Anfang.
    assert profil.value_at(1) > 0.9
    # Position 27 liegt mitten im Stamm, Fenster 27..36 ebenfalls.
    assert profil.value_at(27) < 0.01


def test_die_letzten_positionen_haben_kein_volles_fenster():
    """Dort gibt es keinen Wert — eine 0 wäre eine Falschaussage."""
    profil = ft.accessibility(OFFEN, probe_length=10)
    assert profil.profile[-1] is None
    assert profil.profile[-9] is None
    assert profil.profile[-10] is not None
    assert sum(1 for wert in profil.profile if wert is None) == 9


def test_einzelne_ungepaart_wahrscheinlichkeit():
    profil = ft.accessibility(OFFEN + HAARNADEL + OFFEN, probe_length=5)
    assert len(profil.unpaired) == len(OFFEN) * 2 + len(HAARNADEL)
    assert all(0.0 <= wert <= 1.0 for wert in profil.unpaired)
    assert profil.unpaired[0] > 0.9      # offener Anfang
    assert profil.unpaired[27] < 0.1     # Stamm


# ====================================================== Bereichsauswahl


def test_bereich_beschneiden():
    assert ft.slice_region("ACGUACGU", 3, 5) == ("GUA", 3, 5)
    # Über die Enden hinaus wird beschnitten, nicht gemeckert.
    assert ft.slice_region("ACGU", 0, 99) == ("ACGU", 1, 4)
    assert ft.slice_region("", 1, 5) == ("", 1, 0)


def test_rueckwaerts_markierter_bereich_wird_getauscht():
    """Wer rückwärts markiert, meint denselben Bereich.

    Daraus stillschweigend eine einzelne Base zu machen wäre eine
    Falschaussage über das, was der Nutzer ausgewählt hat.
    """
    assert ft.slice_region("ACGUACGU", 5, 3) == ("GUA", 3, 5)
    assert ft.accessibility("ACGUACGU", start=6, end=2, probe_length=2).start == 2


def test_faltung_nur_des_gewaehlten_bereichs():
    ganz = ft.fold_region(TRANSKRIPT, 1, 100)
    assert ganz.start == 1 and ganz.end == 100
    assert len(ganz.sequence) == 100
    assert len(ganz.structure) == 100


def test_profil_nur_des_gewaehlten_bereichs():
    profil = ft.accessibility(TRANSKRIPT, start=50, end=150, probe_length=15)
    assert profil.start == 50 and profil.end == 150
    assert len(profil.profile) == 101


# ============================================== lange Sequenzen, Stuecke


def test_lange_sequenz_wird_in_stuecken_gerechnet():
    """CLAUDE.md, Regel 8: lange Rechnungen melden Fortschritt."""
    lang = (OFFEN + HAARNADEL) * 70      # 3360 Basen
    schritte: list[tuple[int, int]] = []

    profil = ft.accessibility(lang, probe_length=15, progress=lambda a, b: schritte.append((a, b)))

    assert profil.available
    assert profil.chunks > 1, "so eine Länge gehört in Stücke"
    assert len(schritte) == profil.chunks
    assert schritte[-1] == (profil.chunks, profil.chunks)
    assert len(profil.profile) == len(lang)


def test_stueckgrenzen_erzeugen_keine_luecken():
    """An der Naht darf das Profil nicht einbrechen.

    Die Stücke überlappen, damit jede Position ihren strukturellen
    Zusammenhang behält; ohne die Überlappung sähe man die Nähte im Profil.
    """
    lang = (OFFEN + HAARNADEL) * 70
    profil = ft.accessibility(lang, probe_length=15)

    assert profil.note is None, "keine Position darf ohne Wert bleiben"
    # Auch an den Nähten gilt: offene Abschnitte offen, Stämme zu.
    for wiederholung in range(70):
        offen = profil.value_at(wiederholung * 48 + 5)
        stamm = profil.value_at(wiederholung * 48 + 28)
        if offen is None or stamm is None:
            continue
        assert offen > 0.5, f"Wiederholung {wiederholung} ist zu"
        assert stamm < 0.05, f"Wiederholung {wiederholung} ist offen"


def test_gesamtfaltung_wird_ab_einer_laenge_ausgelassen():
    """Die MFE eines ganzen Transkripts ist langsam und sagt wenig."""
    lang = "A" * (ft.MAX_GLOBAL_FOLD + 1)
    ergebnis = ft.fold_region(lang)
    assert ergebnis.available is False
    assert ergebnis.note and str(ft.MAX_GLOBAL_FOLD) in ergebnis.note
    assert "kleineren Bereich" in ergebnis.note

    # Das Profil gilt trotzdem — es rechnet lokal.
    assert ft.accessibility(lang, probe_length=15).available is True


# ============================================================ Faltung


def test_faltung_mit_rna_parametern():
    """Die Ziel-RNA faltet mit RNA-Parametern, nicht mit denen aus Phase 3."""
    ergebnis = ft.fold_region(HAARNADEL)
    assert ergebnis.available
    assert ergebnis.mfe.value == pytest.approx(-23.0, abs=1.0)
    assert "RNA-Parametern" in ergebnis.mfe.method


def test_faltung_nach_einem_dna_block_weiter_rna():
    """Der Parametersatz aus Phase 3 darf hier nicht durchschlagen."""
    with fold.dna_parameters():
        pass
    assert ft.fold_region(HAARNADEL).mfe.value == pytest.approx(-23.0, abs=1.0)


def test_ensemble_nie_hoeher_als_das_minimum():
    ergebnis = ft.fold_region(HAARNADEL)
    assert ergebnis.ensemble_energy.value <= ergebnis.mfe.value + 1e-6


def test_leerer_bereich():
    assert ft.fold_region("").available is False
    assert ft.accessibility("").available is False


# ======================================================== Eingabepruefung


@pytest.mark.parametrize("kwargs", [
    {"probe_length": 0},
    {"probe_length": 100, "window": 50},     # Sonde größer als das Fenster
    {"window": 30, "max_span": 60},          # Spannweite größer als das Fenster
])
def test_unsinnige_einstellungen_sind_fehler(kwargs):
    with pytest.raises(ValueError):
        ft.accessibility(TRANSKRIPT, **kwargs)


def test_sonde_laenger_als_der_bereich():
    ergebnis = ft.accessibility("ACGUACGU", probe_length=15)
    assert ergebnis.available is False
    assert ergebnis.note and "größer als der Bereich" in ergebnis.note


# ======================================================== RNAup-Zerlegung


def test_oeffnungsenergie():
    """ΔG = −RT·ln(p). Bei p = 1 ist nichts zu öffnen."""
    assert ft.opening_energy(1.0) == pytest.approx(0.0, abs=1e-9)
    assert ft.opening_energy(0.5) == pytest.approx(0.427, abs=0.01)
    # Eine Stelle, die nie offen ist, hat keine endliche Energie.
    assert ft.opening_energy(0.0) is None


def test_rnaup_zerlegt_die_bindung():
    """ΔG(gesamt) = ΔG(Hybrid) + ΔG(Ziel öffnen) + ΔG(Oligo öffnen)."""
    sequenz = OFFEN + HAARNADEL + OFFEN
    ergebnis = ft.rnaup(sequenz, 1, 15, "UUUUUUUUUUUUUUU")

    assert ergebnis.available
    summe = (
        ergebnis.hybridisation.value
        + ergebnis.opening_target.value
        + ergebnis.opening_oligo.value
    )
    assert ergebnis.total.value == pytest.approx(summe, abs=1e-6)
    assert ergebnis.hybridisation.value < 0, "Hybridisierung setzt Energie frei"
    assert ergebnis.opening_target.value >= -1e-9, "Öffnen kostet Energie"
    assert "&" in (ergebnis.duplex_structure or "")


def test_offene_stelle_kostet_weniger_als_eine_verschlossene():
    """Der eigentliche Nutzen der Zerlegung."""
    sequenz = OFFEN + HAARNADEL + OFFEN
    sonde = "UUUUUUUUUU"
    offen = ft.rnaup(sequenz, 1, 10, sonde)
    im_stamm = ft.rnaup(sequenz, 27, 36, sonde)

    assert offen.opening_target.value == pytest.approx(0.0, abs=0.1)
    assert (
        im_stamm.opening_target.value is None
        or im_stamm.opening_target.value > offen.opening_target.value
    )


def test_rnaup_traegt_seinen_vorbehalt():
    """Ein DNA/RNA-Hybrid mit RNA-Parametern ist eine Näherung.

    Die belastbare Zahl liefert MELTING ab Phase 5; das muss an jeder dieser
    Zahlen stehen (CLAUDE.md, Regel 3).
    """
    ergebnis = ft.rnaup(OFFEN + HAARNADEL, 1, 10, "UUUUUUUUUU")
    for groesse in (
        ergebnis.hybridisation,
        ergebnis.opening_target,
        ergebnis.opening_oligo,
        ergebnis.total,
    ):
        assert groesse.reliability.value == "genähert über natürliches Analogon"
        assert "MELTING" in (groesse.note or "")


@pytest.mark.parametrize("start,ende", [(0, 5), (1, 999), (10, 5)])
def test_stelle_ausserhalb_des_ziels(start, ende):
    with pytest.raises(ValueError):
        ft.rnaup(OFFEN, start, ende, "UUUU")


def test_rnaup_ohne_oligo():
    with pytest.raises(ValueError):
        ft.rnaup(OFFEN, 1, 5, "")


def test_kein_duplex_ist_keine_zahl():
    """ViennaRNA meldet "kein Duplex möglich" als 100000 kcal/mol.

    Ungeprüft durchgereicht wäre das eine Zahl, die sich in jede Summe und
    jede Rangfolge hineinrechnet und dort wie ein Messwert aussieht.
    """
    ziel = "A" * 30 + HAARNADEL + "A" * 30

    # A gegen A paart nicht.
    ohne = ft.rnaup(ziel, 1, 10, "A" * 10)
    assert ohne.hybridisation.value is None
    assert ohne.total.value is None
    assert ohne.duplex_structure is None
    assert "kein Duplex" in (ohne.note or "")

    # Die Gegenprobe: U gegen A paart sehr wohl.
    mit = ft.rnaup(ziel, 1, 10, "U" * 10)
    assert mit.hybridisation.value is not None
    assert mit.hybridisation.value < 0
    assert mit.hybridisation.value > -ft.NO_DUPLEX_SENTINEL


def test_oligo_laenger_als_die_stelle_erfindet_keine_energie():
    ziel = "A" * 30 + HAARNADEL + "A" * 30
    ergebnis = ft.rnaup(ziel, 1, 5, "A" * 50)
    assert ergebnis.hybridisation.value is None
