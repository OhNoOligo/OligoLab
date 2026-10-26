"""Datenmodelle von OligoLab.

Zwei Regeln aus CLAUDE.md schlagen hier unmittelbar durch:

Regel 1 — ein Oligo ist nie eine Zeichenkette. `Oligo` haelt eine Liste von
`Monomer`-Objekten, jedes mit seiner Position. Keine Funktion dieses Projekts
nimmt eine Sequenz als `str` entgegen; wer eine Zeichenkette hat, schickt sie
erst durch `app.notation.parse`.

Regel 3 — jede Zahl traegt ihre Verlaesslichkeit mit. Dafuer ist `Quantity` da.
Rechenergebnisse werden nicht als nackter `float` zurueckgegeben, sondern als
`Quantity` mit Kennzeichen, Methode und Einheit.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Literal


class Reliability(str, Enum):
    """Die drei Kennzeichen aus CLAUDE.md, Regel 3."""

    EXACT = "exakt"
    PARAMETER = "Parameter vorhanden"
    APPROX = "genähert über natürliches Analogon"
    MISSING = "nicht hinterlegt"

    @property
    def rank(self) -> int:
        """Kleiner ist besser. Dient dem Zusammenfassen mehrerer Beitraege."""
        return {
            Reliability.EXACT: 0,
            Reliability.PARAMETER: 1,
            Reliability.APPROX: 2,
            Reliability.MISSING: 3,
        }[self]


def worst(*flags: Reliability) -> Reliability:
    """Das schlechteste Kennzeichen gewinnt.

    Eine Summe ist nie verlaesslicher als ihr schwaechster Beitrag.
    """
    present = [f for f in flags if f is not None]
    if not present:
        return Reliability.MISSING
    return max(present, key=lambda f: f.rank)


@dataclass(frozen=True)
class Quantity:
    """Ein Zahlenwert mit Einheit, Kennzeichen und Begruendung.

    `value is None` heisst: nicht berechenbar. Dann sagt `note`, warum —
    niemals stillschweigend 0.0 (CLAUDE.md, Regel 5 im Geiste).
    """

    value: float | None
    unit: str
    reliability: Reliability
    method: str
    note: str | None = None

    def rounded(self, digits: int = 2) -> float | None:
        return None if self.value is None else round(self.value, digits)

    def with_note(self, note: str) -> Quantity:
        joined = note if not self.note else f"{self.note} {note}"
        return replace(self, note=joined)

    def as_dict(self, digits: int = 2) -> dict:
        return {
            "value": self.rounded(digits),
            "unit": self.unit,
            "reliability": self.reliability.value,
            "method": self.method,
            "note": self.note,
        }


CoreTested = Literal["ja", "nein", "unbekannt"]


@dataclass(frozen=True)
class MonomerSpec:
    """Ein Eintrag aus `data/monomers.yaml` — der Katalog, nicht die Position."""

    code: str
    name: str
    typ: str = "custom"
    mass_residue: float | None = None
    mass_amidite: float | None = None
    conc_molar: float | None = None
    formula_residue: str | None = None
    eps260: float | None = None
    base_parent: str | None = None
    core_tested: CoreTested = "unbekannt"
    smiles: str | None = None
    quelle: str | None = None
    # Wird gesetzt, wenn der Baustein nicht aus dem Excel stammt oder dort
    # abweicht. Die Oberflaeche hebt das farblich hervor (Regel 2).
    deviates_from_excel: bool = False

    @property
    def is_natural(self) -> bool:
        return self.typ in ("dna", "rna")


@dataclass(frozen=True)
class ModificationSpec:
    """Ein Eintrag aus `data/modifications.yaml`."""

    code: str
    name: str
    mass_diff: float | None = None
    scope: Literal["monomer", "linkage", "terminus"] = "monomer"
    klasse: str = "sonstige"
    formula: str | None = None
    counts_as_base: bool = True
    base_parent: str | None = None
    core_tested: CoreTested = "unbekannt"
    needs_review: bool = False
    eps260: float | None = None
    note: str | None = None
    quelle: str | None = None

    @property
    def reliability(self) -> Reliability:
        if self.mass_diff is None and self.formula is None:
            return Reliability.MISSING
        return Reliability.PARAMETER


@dataclass(frozen=True)
class Monomer:
    """Ein Baustein an einer konkreten Stelle im Strang.

    `position` ist 1-basiert und zaehlt von 5' nach 3' — so wie am Synthesizer
    und in jeder Abbildung dieses Programms.
    """

    position: int
    spec: MonomerSpec
    modifications: tuple[ModificationSpec, ...] = ()
    span: tuple[int, int] = (0, 0)
    source: str = ""

    @property
    def code(self) -> str:
        return self.spec.code

    @property
    def base_parent(self) -> str | None:
        """Natuerliches Analogon. Grundlage jeder Naeherung in diesem Projekt."""
        for mod in self.modifications:
            if mod.base_parent:
                return mod.base_parent
        return self.spec.base_parent

    @property
    def klasse(self) -> str:
        """Farbklasse fuer alle Ansichten (CLAUDE.md, Designsprache)."""
        for mod in self.modifications:
            if mod.klasse in ("zucker", "base", "konjugat"):
                return mod.klasse
        if self.spec.typ == "rna":
            return "rna"
        if self.spec.typ == "dna":
            return "dna"
        return "custom"

    @property
    def core_tested(self) -> CoreTested:
        """Im katalytischen Kern erprobt? Das Strengste gewinnt."""
        order = {"nein": 0, "unbekannt": 1, "ja": 2}
        values = [self.spec.core_tested] + [
            m.core_tested for m in self.modifications if m.core_tested
        ]
        return min(values, key=lambda v: order.get(v, 1))  # type: ignore[arg-type]

    @property
    def mass_residue(self) -> Quantity:
        base = self.spec.mass_residue
        if base is None:
            return Quantity(
                None, "Da", Reliability.MISSING,
                "Restmasse",
                f"Baustein {self.code} hat keine Restmasse in monomers.yaml.",
            )
        total = base
        flags = [Reliability.PARAMETER]
        missing: list[str] = []
        for mod in self.modifications:
            if mod.mass_diff is None:
                flags.append(Reliability.MISSING)
                missing.append(mod.code)
            else:
                total += mod.mass_diff
        note = None
        if missing:
            note = (
                "Keine Massendifferenz hinterlegt fuer: " + ", ".join(missing) + "."
            )
        return Quantity(
            None if missing else total,
            "Da",
            worst(*flags),
            "Excel-Restmasse + Massendifferenzen",
            note,
        )


@dataclass(frozen=True)
class Linkage:
    """Eine internukleotidische Bindung.

    `position` meint die Bindung zwischen Monomer `position` und `position + 1`,
    also 1 .. L-1. Phosphorothioat sitzt hier, nicht am Monomer — darum zeichnet
    die Sequenzkarte es spaeter in die Luecke zwischen zwei Zellen.
    """

    position: int
    kind: Literal["phosphate", "phosphorothioate", "methylphosphonate"] = "phosphate"
    modification: ModificationSpec | None = None
    span: tuple[int, int] = (0, 0)

    @property
    def is_modified(self) -> bool:
        return self.kind != "phosphate"


@dataclass(frozen=True)
class Conjugate:
    """Endmodifikation oder Konjugat, z. B. `/5GalNAc/`.

    Zaehlt nicht zur Basenzahl und bekommt keine Schutzgruppe (PHASEN.md 1.1).
    """

    spec: ModificationSpec
    attach: Literal["5prime", "3prime", "internal"] = "5prime"
    after_position: int | None = None
    span: tuple[int, int] = (0, 0)

    @property
    def code(self) -> str:
        return self.spec.code


@dataclass
class Oligo:
    """Ein Oligonukleotid als Liste von Bausteinen mit Position."""

    monomers: list[Monomer] = field(default_factory=list)
    linkages: list[Linkage] = field(default_factory=list)
    conjugates: list[Conjugate] = field(default_factory=list)
    name: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        expected = max(len(self.monomers) - 1, 0)
        if self.linkages and len(self.linkages) != expected:
            raise ValueError(
                f"{len(self.monomers)} Bausteine brauchen {expected} Bindungen, "
                f"bekommen aber {len(self.linkages)}."
            )
        if not self.linkages and expected:
            self.linkages = [Linkage(position=i + 1) for i in range(expected)]

    @property
    def length(self) -> int:
        """Zahl der Bausteine L. Konjugate zaehlen bewusst nicht mit."""
        return len(self.monomers)

    def __len__(self) -> int:
        return self.length

    def base_counts(self) -> dict[str, int]:
        """Zaehlung nach natuerlichem Analogon.

        Ein 2'-OMe-A zaehlt als A, damit die Schutzgruppenterme in `mass.py`
        auch bei modifizierten Oligos stimmen.
        """
        counts: dict[str, int] = {}
        for m in self.monomers:
            key = m.base_parent or m.code
            counts[key] = counts.get(key, 0) + 1
        return counts

    def code_counts(self) -> dict[str, int]:
        """Zaehlung nach Synthi-Buchstabe — das braucht der Verbrauchsrechner."""
        counts: dict[str, int] = {}
        for m in self.monomers:
            counts[m.code] = counts.get(m.code, 0) + 1
        return counts

    def phosphorothioate_count(self) -> int:
        return sum(1 for l in self.linkages if l.kind == "phosphorothioate")

    def modified_positions(self) -> list[int]:
        return [m.position for m in self.monomers if m.modifications]
