"""Struktur und Zugaenglichkeit der Ziel-RNA (PHASEN.md 4.3).

Drei Rechnungen:

* **MFE und Ensemble** des gewaehlten Bereichs, mit RNA-Parametern.
* **Zugaenglichkeitsprofil** ueber RNAplfold: je Position die
  Wahrscheinlichkeit, dass ein Fenster der Sondenlaenge dort offen ist.
* **RNAup-Zerlegung** fuer eine konkrete Stelle: Oeffnungsenergie des Ziels,
  Oeffnungsenergie des Oligos und Hybridisierungsenergie.

Zur Verankerung des Profils: ViennaRNA gibt die Oeffnungswahrscheinlichkeit
fuer das Fenster zurueck, das AN einer Position ENDET. Hier wird auf den
ANFANG umgerechnet, denn so liest sich das Profil als "ab hier sind die
naechsten L Nukleotide offen" — und genau das braucht man, um eine Sonde
anzulegen. Die Methode steht an jeder Zahl dran.

Die MFE des ganzen Transkripts ist O(n^3) und biologisch fragwuerdig: ein
10-kb-Transkript faltet in der Zelle nicht als ein Stueck. Darum wird sie nur
bis zu einer Laenge gerechnet und darueber mit Begruendung ausgelassen. Das
Zugaenglichkeitsprofil ist lokal und laeuft ueber jede Laenge.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from app.fold import VIENNA_AVAILABLE, VIENNA_VERSION, rna_parameters
from app.models import Quantity, Reliability

try:  # pragma: no cover
    import RNA as _RNA
except ImportError:  # pragma: no cover
    _RNA = None  # type: ignore[assignment]

#: Voreinstellungen fuer RNAplfold (PHASEN.md 4.3), alle einstellbar.
DEFAULT_PROBE_LENGTH = 15
DEFAULT_WINDOW = 80
DEFAULT_MAX_SPAN = 40

#: Bis hierher wird die MFE des ganzen Bereichs gerechnet. Darueber waere sie
#: langsam und biologisch fragwuerdig; dann nur das lokale Profil.
MAX_GLOBAL_FOLD = 3000

#: In so grossen Stuecken wird das Profil gerechnet, damit zwischendurch
#: Fortschritt gemeldet werden kann.
CHUNK = 1000

#: Gaskonstante in kcal/(mol·K).
R_KCAL = 0.0019872041

#: Ab hier ist eine "Energie" keine Energie mehr, sondern ViennaRNAs
#: Platzhalter fuer "kein Duplex moeglich" (100000 kcal/mol).
NO_DUPLEX_SENTINEL = 1000.0


def _rt(temperature_c: float) -> float:
    return R_KCAL * (temperature_c + 273.15)


def opening_energy(probability: float, temperature_c: float = 37.0) -> float | None:
    """ΔG, um eine Stelle zu oeffnen: −RT·ln(p).

    Bei p = 0 ist die Energie unendlich; dann gibt es keine Zahl, sondern
    `None` — eine willkuerlich grosse Zahl waere schlimmer als keine.
    """
    if probability <= 0.0:
        return None
    return -_rt(temperature_c) * math.log(min(1.0, probability))


# --------------------------------------------------------- Faltung des Ziels


@dataclass
class TargetFold:
    available: bool = True
    start: int = 1
    end: int = 0
    sequence: str = ""
    structure: str | None = None
    mfe: Quantity | None = None
    ensemble_energy: Quantity | None = None
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "start": self.start,
            "end": self.end,
            "length": len(self.sequence),
            "structure": self.structure,
            "mfe": self.mfe.as_dict(2) if self.mfe else None,
            "ensemble_energy": (
                self.ensemble_energy.as_dict(2) if self.ensemble_energy else None
            ),
            "note": self.note,
        }


def slice_region(
    sequence: str, start: int | None = None, end: int | None = None
) -> tuple[str, int, int]:
    """Ausschnitt 1-basiert und einschliesslich beider Enden, beschnitten.

    Eine verkehrt herum angegebene Auswahl wird getauscht. Wer in der
    Oberflaeche rueckwaerts markiert, meint denselben Bereich — daraus
    stillschweigend eine einzelne Base zu machen waere eine Falschaussage.
    """
    length = len(sequence)
    if not length:
        return "", 1, 0

    von = start or 1
    bis = end or length
    if von > bis:
        von, bis = bis, von

    first = max(1, min(von, length))
    last = max(first, min(bis, length))
    return sequence[first - 1 : last], first, last


def fold_region(
    sequence: str,
    start: int | None = None,
    end: int | None = None,
) -> TargetFold:
    """MFE und Ensemble des gewaehlten Bereichs, mit RNA-Parametern."""
    piece, first, last = slice_region(sequence, start, end)

    if not piece:
        return TargetFold(available=False, note="Kein Bereich gewählt.")

    if not VIENNA_AVAILABLE:
        return TargetFold(
            available=False, start=first, end=last, sequence=piece,
            note=(
                "ViennaRNA ist nicht installiert. Alles andere bleibt "
                "bedienbar; nur die Faltung fehlt."
            ),
        )

    if len(piece) > MAX_GLOBAL_FOLD:
        return TargetFold(
            available=False, start=first, end=last, sequence=piece,
            note=(
                f"Der Bereich ist {len(piece)} Basen lang. Ab "
                f"{MAX_GLOBAL_FOLD} wird die Gesamtfaltung ausgelassen: sie "
                "kostet viel Zeit und sagt wenig, weil ein Transkript dieser "
                "Länge in der Zelle nicht als ein Stück faltet. Das "
                "Zugänglichkeitsprofil gilt trotzdem — es rechnet lokal. "
                "Für eine Gesamtfaltung einen kleineren Bereich wählen."
            ),
        )

    methode = f"ViennaRNA {VIENNA_VERSION or ''} mit RNA-Parametern (Turner 2004)"
    with rna_parameters():
        fc = _RNA.fold_compound(piece)
        structure, mfe_energy = fc.mfe()
        fc.exp_params_rescale(mfe_energy)
        _, ensemble = fc.pf()

    return TargetFold(
        available=True,
        start=first,
        end=last,
        sequence=piece,
        structure=structure,
        mfe=Quantity(float(mfe_energy), "kcal/mol", Reliability.PARAMETER, methode),
        ensemble_energy=Quantity(
            float(ensemble), "kcal/mol", Reliability.PARAMETER,
            f"{methode}, Ensemble über alle Strukturen",
        ),
    )


# --------------------------------------------------- Zugaenglichkeitsprofil


@dataclass
class Accessibility:
    available: bool = True
    start: int = 1
    end: int = 0
    probe_length: int = DEFAULT_PROBE_LENGTH
    window: int = DEFAULT_WINDOW
    max_span: int = DEFAULT_MAX_SPAN
    #: Je Position: Wahrscheinlichkeit, dass ab hier `probe_length`
    #: Nukleotide offen sind. Die letzten `probe_length - 1` Positionen haben
    #: keinen vollen Platz mehr und stehen auf None.
    profile: list[float | None] = field(default_factory=list)
    #: Je Position die Wahrscheinlichkeit, einzeln ungepaart zu sein.
    unpaired: list[float] = field(default_factory=list)
    chunks: int = 0
    seconds: float = 0.0
    note: str | None = None

    def value_at(self, position: int) -> float | None:
        index = position - self.start
        if 0 <= index < len(self.profile):
            return self.profile[index]
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "start": self.start,
            "end": self.end,
            "probe_length": self.probe_length,
            "window": self.window,
            "max_span": self.max_span,
            "profile": [
                None if value is None else round(value, 5) for value in self.profile
            ],
            "unpaired": [round(value, 5) for value in self.unpaired],
            "chunks": self.chunks,
            "seconds": round(self.seconds, 3),
            "method": (
                f"RNAplfold, Fenster {self.window}, Spannweite {self.max_span}, "
                f"Sondenlänge {self.probe_length}; Profil am Fensteranfang "
                "verankert"
            ),
            "note": self.note,
        }


def accessibility(
    sequence: str,
    start: int | None = None,
    end: int | None = None,
    probe_length: int = DEFAULT_PROBE_LENGTH,
    window: int = DEFAULT_WINDOW,
    max_span: int = DEFAULT_MAX_SPAN,
    progress: Callable[[int, int], None] | None = None,
) -> Accessibility:
    """Oeffnungswahrscheinlichkeit je Position fuer eine Sonde der Laenge L.

    Gerechnet wird in Stuecken, damit `progress(fertig, gesamt)` zwischendurch
    melden kann — bei einem Transkript von mehreren Kilobasen dauert das sonst
    sichtbar lange, ohne dass jemand weiss, ob noch etwas passiert
    (CLAUDE.md, Regel 8).
    """
    piece, first, last = slice_region(sequence, start, end)

    if not piece:
        return Accessibility(available=False, note="Kein Bereich gewählt.")
    if not VIENNA_AVAILABLE:
        return Accessibility(
            available=False, start=first, end=last,
            note="ViennaRNA ist nicht installiert.",
        )
    if probe_length < 1:
        raise ValueError("Die Sondenlänge muss mindestens 1 sein.")
    if window < probe_length:
        raise ValueError(
            f"Die Fensterbreite ({window}) muss mindestens so groß sein wie "
            f"die Sondenlänge ({probe_length})."
        )
    if max_span > window:
        raise ValueError(
            f"Die Maximalspannweite ({max_span}) kann nicht größer sein als "
            f"die Fensterbreite ({window})."
        )

    laenge = len(piece)
    if probe_length > laenge:
        return Accessibility(
            available=False, start=first, end=last, probe_length=probe_length,
            window=window, max_span=max_span,
            note=(
                f"Die Sondenlänge {probe_length} ist größer als der Bereich "
                f"({laenge} Basen)."
            ),
        )

    begonnen = time.monotonic()

    # In Stuecken mit Ueberlappung rechnen. Die Ueberlappung muss mindestens
    # so gross sein wie die Fensterbreite, sonst fehlt den Positionen am
    # Stueckrand ihr struktureller Zusammenhang.
    overlap = max(window, probe_length) * 2
    schritt = max(CHUNK, overlap * 2)

    profil_ende: list[float] = [0.0] * (laenge + 1)   # 1-basiert, am Fensterende
    einzeln: list[float] = [0.0] * (laenge + 1)
    gesetzt = [False] * (laenge + 1)

    stuecke = max(1, math.ceil(laenge / schritt))
    with rna_parameters():
        for nummer in range(stuecke):
            von = nummer * schritt
            bis = min(laenge, von + schritt)
            # Rand nach beiden Seiten, damit die Struktur stimmt.
            von_rand = max(0, von - overlap)
            bis_rand = min(laenge, bis + overlap)
            teil = piece[von_rand:bis_rand]

            up = _RNA.pfl_fold_up(teil, probe_length, window, max_span)

            # `up[i][u]` ist die Wahrscheinlichkeit, dass das Fenster der
            # Laenge u, das AN Position i endet, offen ist — 1-basiert im
            # Teilstueck.
            for i in range(1, len(teil) + 1):
                global_pos = von_rand + i  # 1-basiert im ganzen Bereich
                if not (von < global_pos <= bis):
                    continue  # gehoert zum Rand, wird vom Nachbarstueck gesetzt
                profil_ende[global_pos] = float(up[i][probe_length])
                einzeln[global_pos] = float(up[i][1])
                gesetzt[global_pos] = True

            if progress:
                progress(nummer + 1, stuecke)

    fehlend = [i for i in range(1, laenge + 1) if not gesetzt[i]]

    # Auf den Fensteranfang umrechnen: was an Position `i` endet, beginnt an
    # `i - probe_length + 1`.
    profil: list[float | None] = []
    for anfang in range(1, laenge + 1):
        ende = anfang + probe_length - 1
        profil.append(float(profil_ende[ende]) if ende <= laenge else None)

    note = None
    if fehlend:
        note = f"{len(fehlend)} Position(en) ohne Wert — das sollte nicht vorkommen."

    return Accessibility(
        available=True,
        start=first,
        end=last,
        probe_length=probe_length,
        window=window,
        max_span=max_span,
        profile=profil,
        unpaired=[einzeln[i] for i in range(1, laenge + 1)],
        chunks=stuecke,
        seconds=time.monotonic() - begonnen,
        note=note,
    )


# ------------------------------------------------------------ RNAup-Zerlegung


@dataclass
class UpResult:
    available: bool = True
    site_start: int = 0
    site_end: int = 0
    opening_target: Quantity | None = None
    opening_oligo: Quantity | None = None
    hybridisation: Quantity | None = None
    total: Quantity | None = None
    duplex_structure: str | None = None
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "site_start": self.site_start,
            "site_end": self.site_end,
            "opening_target": (
                self.opening_target.as_dict(2) if self.opening_target else None
            ),
            "opening_oligo": (
                self.opening_oligo.as_dict(2) if self.opening_oligo else None
            ),
            "hybridisation": (
                self.hybridisation.as_dict(2) if self.hybridisation else None
            ),
            "total": self.total.as_dict(2) if self.total else None,
            "duplex_structure": self.duplex_structure,
            "note": self.note,
        }


#: Der Vorbehalt steht an jeder Zahl dieser Rechnung.
HYBRID_CAVEAT = (
    "Gerechnet mit RNA-Parametern. Ein DNA/RNA-Hybrid verhält sich anders; "
    "die belastbare Zahl liefert MELTING mit `dnarna` ab Phase 5."
)


def rnaup(
    target_sequence: str,
    site_start: int,
    site_end: int,
    oligo_sequence: str,
    temperature_c: float = 37.0,
    window: int = DEFAULT_WINDOW,
    max_span: int = DEFAULT_MAX_SPAN,
) -> UpResult:
    """Die Bindung an eine konkrete Stelle, aufgeschluesselt.

        ΔG(gesamt) = ΔG(Hybridisierung)
                   + ΔG(Ziel öffnen)
                   + ΔG(Oligo öffnen)

    So rechnet RNAup. Die Oeffnungsenergien kommen aus den
    Oeffnungswahrscheinlichkeiten (−RT·ln p), die Hybridisierungsenergie aus
    `duplexfold`.
    """
    if not VIENNA_AVAILABLE:
        return UpResult(available=False, note="ViennaRNA ist nicht installiert.")

    laenge = len(target_sequence)
    if not (1 <= site_start <= site_end <= laenge):
        raise ValueError(
            f"Die Stelle {site_start}–{site_end} liegt nicht im Ziel "
            f"(1–{laenge})."
        )
    if not oligo_sequence:
        raise ValueError("Ohne Oligosequenz gibt es nichts zu hybridisieren.")

    stellenlaenge = site_end - site_start + 1
    oligo = oligo_sequence.upper().replace("T", "U")
    methode = f"RNAup-Zerlegung, ViennaRNA {VIENNA_VERSION or ''}"

    with rna_parameters():
        # Oeffnungswahrscheinlichkeit der Zielstelle.
        up = _RNA.pfl_fold_up(target_sequence, stellenlaenge, window, max_span)
        p_ziel = float(up[site_end][stellenlaenge])

        # Das Oligo allein: wie oft ist es ganz offen?
        fc = _RNA.fold_compound(oligo)
        _, oligo_mfe = fc.mfe()
        fc.exp_params_rescale(oligo_mfe)
        _, oligo_ensemble = fc.pf()
        # p(ganz offen) = exp(-(ΔG_offen − ΔG_Ensemble)/RT); der offene
        # Zustand hat ΔG = 0.
        p_oligo = min(1.0, math.exp(oligo_ensemble / _rt(temperature_c)))

        duplex = _RNA.duplexfold(target_sequence[site_start - 1 : site_end], oligo)
        duplex_structure = duplex.structure
        hybrid: float | None = float(duplex.energy)

        # ViennaRNA meldet "kein Duplex moeglich" nicht als Fehler, sondern mit
        # einem Platzhalter von 100000 kcal/mol und einer Struktur ohne
        # Klammern. Ungeprueft durchgereicht waere das eine Zahl, die sich in
        # jede Summe und jede Rangfolge hineinrechnet und dort wie ein
        # Messwert aussieht.
        if hybrid is not None and (
            hybrid >= NO_DUPLEX_SENTINEL or "(" not in duplex_structure
        ):
            hybrid = None
            duplex_structure = None

    e_ziel = opening_energy(p_ziel, temperature_c)
    e_oligo = opening_energy(p_oligo, temperature_c)

    def q(value: float | None, label: str) -> Quantity:
        return Quantity(
            value, "kcal/mol", Reliability.APPROX, f"{methode} — {label}",
            HYBRID_CAVEAT,
        )

    gesamt = (
        None
        if hybrid is None or e_ziel is None or e_oligo is None
        else hybrid + e_ziel + e_oligo
    )

    note = HYBRID_CAVEAT
    if hybrid is None:
        note = (
            "Zwischen dieser Stelle und dem Oligo bildet sich kein Duplex — "
            "sie sind nicht komplementär genug. Ohne Hybridisierung gibt es "
            f"auch keine Summe. {HYBRID_CAVEAT}"
        )
    elif e_ziel is None:
        note = (
            "Die Stelle ist praktisch nie offen — die Öffnungsenergie wäre "
            f"unendlich. {HYBRID_CAVEAT}"
        )

    return UpResult(
        available=True,
        site_start=site_start,
        site_end=site_end,
        opening_target=q(e_ziel, "Öffnungsenergie des Ziels"),
        opening_oligo=q(e_oligo, "Öffnungsenergie des Oligos"),
        hybridisation=q(hybrid, "Hybridisierungsenergie"),
        total=q(gesamt, "Summe"),
        duplex_structure=duplex_structure,
        note=note,
    )
