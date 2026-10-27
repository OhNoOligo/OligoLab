"""Bauteile eines DNAzyms erkennen: 5'-Arm, katalytischer Kern, 3'-Arm.

Gesucht wird ueber `base_parent`, nicht ueber den Synthi-Buchstaben. Ein Kern,
in dem eine Position durch LNA-A ersetzt wurde, ist immer noch derselbe Kern —
und genau diesen Fall muss `critical.py` spaeter als kritisch melden koennen.
Wuerde hier stur auf Buchstaben verglichen, faende sich der Kern nicht mehr und
die wichtigste Warnung des ganzen Programms bliebe aus.

Wird kein Kern gefunden, ist das kein Fehler (PHASEN.md 3.1). Nicht jedes
Oligo im Programm ist ein DNAzym.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.models import Oligo
from app.registry import Registry, get_registry

PartKind = Literal["arm5", "core", "arm3"]

PART_LABEL: dict[PartKind, str] = {
    "arm5": "5'-Arm",
    "core": "Katalytischer Kern",
    "arm3": "3'-Arm",
}


@dataclass(frozen=True)
class CoreSpec:
    """Ein Eintrag aus `data/cores.yaml`."""

    id: str
    name: str
    sequence: str
    target_type: str = "rna"
    preferred_junctions: tuple[str, ...] = ()
    metal_requirement: str | None = None
    arm_length_default: int = 9
    quelle: str | None = None
    note: str | None = None

    @property
    def length(self) -> int:
        return len(self.sequence)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "sequence": self.sequence,
            "length": self.length,
            "target_type": self.target_type,
            "preferred_junctions": list(self.preferred_junctions),
            "metal_requirement": self.metal_requirement,
            "arm_length_default": self.arm_length_default,
            "quelle": self.quelle,
            "note": self.note,
        }


def load_cores(registry: Registry | None = None) -> list[CoreSpec]:
    reg = registry or get_registry()
    cores: list[CoreSpec] = []
    for entry in reg.cores:
        cores.append(
            CoreSpec(
                id=str(entry.get("id") or entry.get("name")),
                name=str(entry.get("name") or entry.get("id")),
                sequence=str(entry["sequence"]).upper(),
                target_type=entry.get("target_type", "rna"),
                preferred_junctions=tuple(entry.get("preferred_junctions") or ()),
                metal_requirement=entry.get("metal_requirement"),
                arm_length_default=int(entry.get("arm_length_default") or 9),
                quelle=entry.get("quelle"),
                note=entry.get("note"),
            )
        )
    return cores


@dataclass(frozen=True)
class Part:
    """Ein zusammenhaengender Abschnitt, 1-basiert und einschliesslich Enden."""

    kind: PartKind
    start: int
    end: int

    @property
    def label(self) -> str:
        return PART_LABEL[self.kind]

    @property
    def length(self) -> int:
        return self.end - self.start + 1

    def contains(self, position: int) -> bool:
        return self.start <= position <= self.end

    def overlaps(self, start: int, end: int) -> bool:
        return not (end < self.start or start > self.end)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label,
            "start": self.start,
            "end": self.end,
            "length": self.length,
        }


@dataclass
class PartsResult:
    core: CoreSpec | None = None
    parts: list[Part] = field(default_factory=list)
    approximated: list[str] = field(default_factory=list)
    note: str | None = None

    @property
    def found(self) -> bool:
        return self.core is not None

    @property
    def core_part(self) -> Part | None:
        return next((p for p in self.parts if p.kind == "core"), None)

    @property
    def arm5(self) -> Part | None:
        return next((p for p in self.parts if p.kind == "arm5"), None)

    @property
    def arm3(self) -> Part | None:
        return next((p for p in self.parts if p.kind == "arm3"), None)

    def part_at(self, position: int) -> Part | None:
        return next((p for p in self.parts if p.contains(position)), None)

    def as_dict(self) -> dict[str, Any]:
        return {
            "found": self.found,
            "core": self.core.as_dict() if self.core else None,
            "parts": [p.as_dict() for p in self.parts],
            "approximated": self.approximated,
            "note": self.note,
        }


def base_letters(oligo: Oligo) -> list[str | None]:
    """Je Position der Buchstabe des natuerlichen Analogons.

    `None`, wo es keines gibt — dann kann an dieser Stelle weder ein Kern
    erkannt noch gefaltet werden. U und T werden gleichgesetzt, damit ein
    RNA-Baustein im Kern den DNA-Kern trotzdem trifft.
    """
    letters: list[str | None] = []
    for monomer in oligo.monomers:
        parent = monomer.base_parent
        if parent is None:
            letters.append(None)
        else:
            letters.append("T" if parent.upper() == "U" else parent.upper())
    return letters


def detect_parts(
    oligo: Oligo, registry: Registry | None = None
) -> PartsResult:
    """5'-Arm, Kern und 3'-Arm bestimmen.

    Sucht jeden Kern aus `cores.yaml` in der Reihenfolge der Datei; der erste
    Treffer gewinnt. Gibt es keinen, bleibt `core` None — das ist kein Fehler.
    """
    reg = registry or get_registry()
    letters = base_letters(oligo)

    if not oligo.monomers:
        return PartsResult(note="Kein Baustein im Strang.")

    # Positionen ohne natuerliches Analogon koennen nie Teil eines Kerns sein.
    # Ein Zeichen, das in keiner Kernsequenz vorkommt, sorgt dafuer.
    haystack = "".join(letter or "." for letter in letters)

    for core in load_cores(reg):
        index = haystack.find(core.sequence)
        if index < 0:
            continue

        core_start = index + 1
        core_end = index + core.length

        parts: list[Part] = []
        if core_start > 1:
            parts.append(Part("arm5", 1, core_start - 1))
        parts.append(Part("core", core_start, core_end))
        if core_end < oligo.length:
            parts.append(Part("arm3", core_end + 1, oligo.length))

        # Welche Kernpositionen wurden nur ueber das Analogon getroffen?
        approximated: list[str] = []
        for monomer in oligo.monomers[core_start - 1 : core_end]:
            if monomer.modifications or monomer.spec.typ != "dna":
                approximated.append(
                    f"Position {monomer.position} ({monomer.source or monomer.code}): "
                    f"im Kern über das natürliche Analogon "
                    f"{monomer.base_parent} erkannt"
                )

        note = None
        if approximated:
            note = (
                f"Kern {core.name} erkannt, aber nicht in reiner DNA — "
                f"{len(approximated)} Position(en) über das Analogon."
            )

        return PartsResult(
            core=core, parts=parts, approximated=approximated, note=note
        )

    missing = sum(1 for letter in letters if letter is None)
    note = "Kein katalytischer Kern aus cores.yaml gefunden."
    if missing:
        note += (
            f" {missing} Position(en) haben kein natürliches Analogon und "
            "können nie zu einem Kern gehören."
        )
    return PartsResult(note=note)
