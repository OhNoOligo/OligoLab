"""Faltung des Strangs mit ViennaRNA und DNA-Parametern.

Ein DNAzym ist DNA. Mit den voreingestellten RNA-Parametern kaeme Unsinn
heraus: dieselbe Haarnadel liegt mit RNA-Parametern bei -23 kcal/mol und mit
DNA-Parametern bei -12 kcal/mol. Das ist keine Feinheit, sondern entscheidet
darueber, ob eine Struktur als kritisch gilt.

ViennaRNA haelt den Parametersatz GLOBAL. Wuerde ihn hier einfach jemand
umstellen, faltete Phase 4 ihre Ziel-RNA anschliessend mit DNA-Parametern —
ein Fehler, den niemand bemerkt, weil die Zahlen plausibel aussehen. Darum
laeuft jede Rechnung durch `dna_parameters()`, das den vorigen Satz hinterher
wiederherstellt.

Modifizierte Bausteine gehen ueber `base_parent` ein: ViennaRNA kennt weder
LNA noch 2'-OMe. Jedes Ergebnis, das darauf beruht, wird gekennzeichnet
(CLAUDE.md, Regel 3) — eine LNA stabilisiert eine Helix erheblich, und ein
ueber das DNA-Analogon gerechnetes ΔG unterschaetzt das.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from app.dnazyme import base_letters
from app.models import Oligo, Quantity, Reliability
from app.registry import Registry

try:  # pragma: no cover - ohne ViennaRNA bleibt die App bedienbar
    import RNA as _RNA

    VIENNA_AVAILABLE = True
    VIENNA_VERSION: str | None = getattr(_RNA, "__version__", None)
except ImportError:  # pragma: no cover
    _RNA = None  # type: ignore[assignment]
    VIENNA_AVAILABLE = False
    VIENNA_VERSION = None

# Platzhalter fuer Bausteine ohne natuerliches Analogon. ViennaRNA behandelt
# `N` als Base, die mit nichts paart — das ist genau richtig: ein Baustein,
# von dem wir nichts wissen, darf keine Struktur vortaeuschen.
UNKNOWN_BASE = "N"


@contextmanager
def dna_parameters() -> Iterator[None]:
    """DNA-Parameter fuer die Dauer des Blocks, danach wieder RNA.

    ViennaRNA bietet kein Auslesen des aktiven Satzes an, darum wird am Ende
    der Standardsatz (Turner 2004, RNA) gesetzt. Das ist der Zustand, in dem
    ViennaRNA startet — jede Phase, die RNA faltet, findet ihn also vor.
    """
    if not VIENNA_AVAILABLE:
        raise RuntimeError("ViennaRNA ist nicht installiert.")
    _RNA.params_load_DNA_Mathews2004()
    try:
        yield
    finally:
        _RNA.params_load_RNA_Turner2004()


def pairs_from_structure(structure: str) -> dict[int, int]:
    """Klammerstruktur in Paare {i: j} und {j: i}, 1-basiert."""
    stack: list[int] = []
    pairs: dict[int, int] = {}
    for index, char in enumerate(structure, start=1):
        if char == "(":
            stack.append(index)
        elif char == ")":
            if not stack:
                continue
            opener = stack.pop()
            pairs[opener] = index
            pairs[index] = opener
    return pairs


@dataclass
class Hairpin:
    """Eine Haarnadel: ein Stamm mit genau einer Schleife darin."""

    start: int
    end: int
    loop_start: int
    loop_end: int
    energy: float | None

    @property
    def stem_length(self) -> int:
        return self.loop_start - self.start

    def as_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "loop_start": self.loop_start,
            "loop_end": self.loop_end,
            "stem_length": self.stem_length,
            "energy": None if self.energy is None else round(self.energy, 2),
        }


def find_hairpins(sequence: str, structure: str) -> list[Hairpin]:
    """Alle Stamm-Schleifen und ihre Einzelenergie.

    Gesucht wird erst die Schleife — ein Paar ohne weiteres Paar darin — und
    von dort nach aussen, solange die Helix ununterbrochen stapelt. Die
    Energie wird fuer den herausgeschnittenen Abschnitt allein bewertet, denn
    gefragt ist, wie stabil DIESE Haarnadel ist, nicht die ganze Struktur.
    """
    pairs = pairs_from_structure(structure)
    hairpins: list[Hairpin] = []

    for opener in sorted(p for p in pairs if p < pairs[p]):
        closer = pairs[opener]
        # Eine Schleife: zwischen den Partnern liegt kein weiteres Paar.
        if any(pairs.get(k, 0) for k in range(opener + 1, closer)):
            continue

        # Nach aussen, solange direkt gestapelt wird.
        outer_open, outer_close = opener, closer
        while (
            outer_open - 1 >= 1
            and pairs.get(outer_open - 1) == outer_close + 1
        ):
            outer_open -= 1
            outer_close += 1

        energy: float | None = None
        if VIENNA_AVAILABLE:
            piece_seq = sequence[outer_open - 1 : outer_close]
            piece_struct = structure[outer_open - 1 : outer_close]
            try:
                energy = float(_RNA.eval_structure_simple(piece_seq, piece_struct))
            except Exception:
                # Lieber keine Zahl als eine falsche.
                energy = None

        hairpins.append(
            Hairpin(
                start=outer_open,
                end=outer_close,
                loop_start=opener + 1,
                loop_end=closer - 1,
                energy=energy,
            )
        )

    return hairpins


@dataclass
class FoldResult:
    """Das Faltungsergebnis eines Strangs."""

    available: bool = True
    sequence_used: str = ""
    structure: str = ""
    mfe: Quantity | None = None
    ensemble_energy: Quantity | None = None
    pair_probabilities: list[dict[str, Any]] = field(default_factory=list)
    unpaired: list[float] = field(default_factory=list)
    hairpins: list[Hairpin] = field(default_factory=list)
    homodimer_structure: str | None = None
    homodimer_energy: Quantity | None = None
    approximated: list[str] = field(default_factory=list)
    note: str | None = None

    @property
    def reliability(self) -> Reliability:
        if not self.available:
            return Reliability.MISSING
        return (
            Reliability.APPROX if self.approximated else Reliability.PARAMETER
        )

    def pairs(self) -> dict[int, int]:
        return pairs_from_structure(self.structure)

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "sequence_used": self.sequence_used,
            "structure": self.structure,
            "mfe": self.mfe.as_dict(2) if self.mfe else None,
            "ensemble_energy": (
                self.ensemble_energy.as_dict(2) if self.ensemble_energy else None
            ),
            "pair_probabilities": self.pair_probabilities,
            "unpaired": [round(value, 4) for value in self.unpaired],
            "hairpins": [h.as_dict() for h in self.hairpins],
            "homodimer_structure": self.homodimer_structure,
            "homodimer_energy": (
                self.homodimer_energy.as_dict(2) if self.homodimer_energy else None
            ),
            "reliability": self.reliability.value,
            "approximated": self.approximated,
            "note": self.note,
        }


def fold_sequence_text(oligo: Oligo) -> tuple[str, list[str]]:
    """Die Sequenz, die ViennaRNA zu sehen bekommt, plus was daran genaehert ist."""
    letters = base_letters(oligo)
    approximated: list[str] = []
    text: list[str] = []

    for monomer, letter in zip(oligo.monomers, letters):
        if letter is None:
            text.append(UNKNOWN_BASE)
            approximated.append(
                f"Position {monomer.position} ({monomer.code}): kein natürliches "
                "Analogon — faltet als N und paart mit nichts"
            )
            continue
        text.append(letter)
        if monomer.modifications:
            mods = ", ".join(m.name for m in monomer.modifications)
            approximated.append(
                f"Position {monomer.position} ({monomer.source or monomer.code}): "
                f"{mods} gefaltet über das natürliche Analogon {letter}"
            )
        elif monomer.spec.typ == "rna":
            approximated.append(
                f"Position {monomer.position} ({monomer.code}): RNA-Baustein "
                "mit DNA-Parametern gefaltet"
            )

    return "".join(text), approximated


# Unterhalb dieser Wahrscheinlichkeit wird ein Basenpaar nicht mehr gezeigt;
# das Bogendiagramm waere sonst ein Netz aus Haaren.
MIN_PAIR_PROBABILITY = 0.01


def compute(
    oligo: Oligo,
    registry: Registry | None = None,
    with_homodimer: bool = True,
) -> FoldResult:
    """MFE, Ensemble, Paarungswahrscheinlichkeiten und Homodimer."""
    del registry  # noch nicht gebraucht, Signatur bleibt wie die der anderen

    if not oligo.monomers:
        return FoldResult(
            available=False, note="Kein Baustein im Strang — nichts zu falten."
        )

    if not VIENNA_AVAILABLE:
        return FoldResult(
            available=False,
            note=(
                "ViennaRNA ist nicht installiert. Alles andere im Programm "
                "bleibt bedienbar; nur die Faltung fehlt. "
                "Nachinstallieren mit `pip install ViennaRNA`."
            ),
        )

    sequence, approximated = fold_sequence_text(oligo)
    length = len(sequence)
    methode = f"ViennaRNA {VIENNA_VERSION or ''} mit DNA-Parametern (Mathews 2004)"

    with dna_parameters():
        fc = _RNA.fold_compound(sequence)
        structure, mfe_energy = fc.mfe()

        # Ohne Reskalierung laeuft die Zustandssumme bei langen Straengen ueber.
        fc.exp_params_rescale(mfe_energy)
        _, ensemble_energy = fc.pf()
        bpp = fc.bpp()

        homodimer_structure: str | None = None
        homodimer_energy_value: float | None = None
        if with_homodimer:
            try:
                duplex = _RNA.cofold(f"{sequence}&{sequence}")
                # RNAcofold gibt die Struktur beider Straenge ohne Trennzeichen
                # zurueck, also als ein Wort doppelter Laenge. So ist nicht zu
                # erkennen, wo der eine Strang aufhoert; darum wieder eingesetzt.
                roh = duplex[0]
                homodimer_structure = f"{roh[:length]}&{roh[length:]}"
                homodimer_energy_value = float(duplex[1])
            except Exception:
                homodimer_structure = None
                homodimer_energy_value = None

        hairpins = find_hairpins(sequence, structure)

    pair_probabilities: list[dict[str, Any]] = []
    paired_mass = [0.0] * (length + 1)
    for i in range(1, length + 1):
        for j in range(i + 1, length + 1):
            probability = float(bpp[i][j])
            if probability <= 0.0:
                continue
            paired_mass[i] += probability
            paired_mass[j] += probability
            if probability >= MIN_PAIR_PROBABILITY:
                pair_probabilities.append(
                    {"i": i, "j": j, "p": round(probability, 4)}
                )

    # Die Wahrscheinlichkeit, ungepaart zu sein, ist das Gegenstueck zur Summe
    # aller Paarungen dieser Position. Numerisch kann das knapp daneben
    # liegen, darum beschnitten.
    unpaired = [min(1.0, max(0.0, 1.0 - paired_mass[i])) for i in range(1, length + 1)]

    note = None
    if approximated:
        note = (
            f"{len(approximated)} Position(en) über das natürliche Analogon "
            "gefaltet — ΔG ist dort eine Näherung."
        )

    return FoldResult(
        available=True,
        sequence_used=sequence,
        structure=structure,
        mfe=Quantity(
            float(mfe_energy), "kcal/mol",
            Reliability.APPROX if approximated else Reliability.PARAMETER,
            methode, note,
        ),
        ensemble_energy=Quantity(
            float(ensemble_energy), "kcal/mol",
            Reliability.APPROX if approximated else Reliability.PARAMETER,
            f"{methode}, Ensemble über alle Strukturen", note,
        ),
        pair_probabilities=pair_probabilities,
        unpaired=unpaired,
        hairpins=hairpins,
        homodimer_structure=homodimer_structure,
        homodimer_energy=(
            None
            if homodimer_energy_value is None
            else Quantity(
                homodimer_energy_value, "kcal/mol",
                Reliability.APPROX if approximated else Reliability.PARAMETER,
                f"{methode}, RNAcofold Strang gegen sich selbst", note,
            )
        ),
        approximated=approximated,
        note=note,
    )
