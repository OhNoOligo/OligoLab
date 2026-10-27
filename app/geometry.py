"""Winkel und Abstände messen (PHASEN.md 6.3).

Die wichtigste Messung ist der **In-line-Winkel** an der Spaltstelle:

    2'-O ··· P ··· O5'

Das 2'-OH greift das Phosphat an, und die Abgangsgruppe ist das O5' des
naechsten Rests. Steht alles auf einer Linie — 180 Grad —, kann die
Umesterung ablaufen; steht es quer, nicht. Der Winkel ist damit kein Beiwerk,
sondern die Frage, ob die Geometrie ueberhaupt zur Reaktion passt.

Jede Messung sagt dazu, woher ihre Koordinaten stammen. Eine Zahl aus einer
Kristallstruktur und eine aus einer idealen Spur sehen gleich aus und sind
es nicht (CLAUDE.md, Regel 3).

Fehlt ein Atom, gibt es keine Zahl, sondern den Grund. Ein DNA-Rest hat
kein 2'-O — wer dort einen Winkel ausgibt, hat ihn erfunden.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.models import Quantity, Reliability
from app.pdb import ION_RESIDUES, Atom

Point = tuple[float, float, float]


def distance(a: Point, b: Point) -> float:
    return math.dist(a, b)


def angle(a: Point, b: Point, c: Point) -> float:
    """Winkel a–b–c in Grad, b ist der Scheitel."""
    v1 = (a[0] - b[0], a[1] - b[1], a[2] - b[2])
    v2 = (c[0] - b[0], c[1] - b[1], c[2] - b[2])
    n1 = math.sqrt(sum(k * k for k in v1))
    n2 = math.sqrt(sum(k * k for k in v2))
    if n1 == 0 or n2 == 0:
        raise ValueError("Zwei Atome liegen aufeinander — da gibt es keinen Winkel.")
    kosinus = sum(p * q for p, q in zip(v1, v2)) / (n1 * n2)
    # Rundungsfehler koennen den Kosinus knapp ueber 1 schieben.
    return math.degrees(math.acos(max(-1.0, min(1.0, kosinus))))


def xyz(atom: Atom) -> Point:
    return (atom.x, atom.y, atom.z)


# ------------------------------------------------------------- auswaehlen


def find_atom(
    atoms: list[Atom], chain: str, residue_number: int, name: str
) -> Atom | None:
    """Ein Atom ueber Kette, Restnummer und Name — ohne Raten."""
    gesuchte = {name.upper(), name.upper().replace("'", "*")}
    for atom in atoms:
        if (
            atom.chain == chain
            and atom.residue_number == residue_number
            and atom.name.upper() in gesuchte
            and atom.alt in ("", "A")
        ):
            return atom
    return None


def parse_selection(text: str) -> tuple[str, int, str]:
    """`A:12:P` in Kette, Rest und Atomnamen zerlegen."""
    teile = text.split(":")
    if len(teile) != 3:
        raise ValueError(
            f"`{text}` ist keine Atomangabe. Erwartet wird Kette:Rest:Atom, "
            "zum Beispiel `A:12:P`."
        )
    kette, rest, atom = teile
    try:
        nummer = int(rest)
    except ValueError as error:
        raise ValueError(f"`{rest}` ist keine Restnummer.") from error
    return kette.strip(), nummer, atom.strip()


# ------------------------------------------------------------ Messungen


@dataclass
class InlineAngle:
    """Der In-line-Winkel samt beider Abstaende."""

    available: bool = True
    angle: Quantity | None = None
    distance_attack: Quantity | None = None
    distance_leaving: Quantity | None = None
    #: Die drei beteiligten Atome, damit man sie im Bild wiederfindet.
    atoms: list[str] = field(default_factory=list)
    assessment: str | None = None
    rating: str | None = None
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "angle": self.angle.as_dict(1) if self.angle else None,
            "distance_attack": (
                self.distance_attack.as_dict(2) if self.distance_attack else None
            ),
            "distance_leaving": (
                self.distance_leaving.as_dict(2) if self.distance_leaving else None
            ),
            "atoms": self.atoms,
            "assessment": self.assessment,
            "rating": self.rating,
            "note": self.note,
        }


#: Ab hier gilt die Anordnung als linienfoermig genug.
INLINE_GOOD_DEG = 150.0
INLINE_WARN_DEG = 120.0


def inline_angle(
    atoms: list[Atom],
    chain: str,
    residue_number: int,
    reliability: Reliability = Reliability.PARAMETER,
) -> InlineAngle:
    """2'-O ··· P ··· O5' an der angegebenen Stelle.

    `residue_number` ist der Rest, dessen 2'-OH angreift; geschnitten wird
    zwischen ihm und dem folgenden.
    """
    o2 = find_atom(atoms, chain, residue_number, "O2'")
    phosphor = find_atom(atoms, chain, residue_number + 1, "P")
    o5 = find_atom(atoms, chain, residue_number + 1, "O5'")

    fehlend = [
        name
        for name, atom in (("O2'", o2), ("P", phosphor), ("O5'", o5))
        if atom is None
    ]
    if fehlend:
        grund = (
            f"In Kette {chain} fehlen an Rest {residue_number}/"
            f"{residue_number + 1}: {', '.join(fehlend)}."
        )
        if "O2'" in fehlend:
            grund += (
                " Ohne 2'-OH gibt es keinen In-line-Angriff — ein DNA-Rest "
                "kann hier nicht geschnitten werden."
            )
        return InlineAngle(available=False, note=grund)

    assert o2 and phosphor and o5
    grad = angle(xyz(o2), xyz(phosphor), xyz(o5))
    methode = "2'-O ··· P ··· O5' aus den Koordinaten"

    if grad >= INLINE_GOOD_DEG:
        bewertung, text = "good", "nahe an der Linie — günstig für den Angriff"
    elif grad >= INLINE_WARN_DEG:
        bewertung, text = "warn", "schief, aber nicht ausgeschlossen"
    else:
        bewertung, text = (
            "bad",
            "quer zur Linie — in dieser Stellung läuft die Umesterung nicht",
        )

    return InlineAngle(
        angle=Quantity(grad, "°", reliability, methode),
        distance_attack=Quantity(
            distance(xyz(o2), xyz(phosphor)), "Å", reliability, "2'-O bis P"
        ),
        distance_leaving=Quantity(
            distance(xyz(phosphor), xyz(o5)), "Å", reliability, "P bis O5'"
        ),
        atoms=[
            f"{chain}:{residue_number}:O2'",
            f"{chain}:{residue_number + 1}:P",
            f"{chain}:{residue_number + 1}:O5'",
        ],
        assessment=text,
        rating=bewertung,
    )


@dataclass
class PositionDistance:
    """Wie weit eine Position von etwas entfernt ist."""

    position: int
    code: str
    modification: str | None
    #: In Nukleotiden — zaehlbar, unabhaengig von jeder Struktur.
    nucleotides: int | None = None
    #: In Ångström — nur mit Koordinaten.
    angstrom: float | None = None
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "position": self.position,
            "code": self.code,
            "modification": self.modification,
            "nucleotides": self.nucleotides,
            "angstrom": None if self.angstrom is None else round(self.angstrom, 2),
            "note": self.note,
        }


def _representative(atoms: list[Atom], chain: str, number: int) -> Atom | None:
    """Ein Atom, das einen Rest vertritt: C1' — und sonst das erste."""
    fuer_rest = [
        a for a in atoms if a.chain == chain and a.residue_number == number
    ]
    if not fuer_rest:
        return None
    return next((a for a in fuer_rest if a.name.upper() in ("C1'", "C1*")), fuer_rest[0])


@dataclass
class IonContact:
    residue: str
    element: str
    chain: str
    number: int
    angstrom: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "residue": self.residue,
            "element": self.element,
            "chain": self.chain,
            "number": self.number,
            "angstrom": round(self.angstrom, 2),
        }


@dataclass
class GeometryReport:
    available: bool = True
    inline: InlineAngle = field(default_factory=InlineAngle)
    to_cleavage: list[PositionDistance] = field(default_factory=list)
    to_core: list[PositionDistance] = field(default_factory=list)
    ion_contacts: dict[int, list[IonContact]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "inline": self.inline.as_dict(),
            "to_cleavage": [d.as_dict() for d in self.to_cleavage],
            "to_core": [d.as_dict() for d in self.to_core],
            "ion_contacts": {
                str(position): [c.as_dict() for c in kontakte]
                for position, kontakte in self.ion_contacts.items()
            },
            "warnings": self.warnings,
            "note": self.note,
        }


#: Naeher als das an einem Ion ist ein Warnsignal (PHASEN.md 6.3).
ION_WARNING_A = 6.0


def measure_model(
    model: Any,
    atoms: list[Atom],
    cleavage_residue: int | None = None,
    core_range: tuple[int, int] | None = None,
) -> GeometryReport:
    """Alle Messungen aus 6.3 für ein gefädeltes Modell.

    `model` ist ein `model3d.Model`; hier wird es nur gelesen, darum keine
    Einfuhr — das haelt die Abhaengigkeit in eine Richtung.
    """
    if not getattr(model, "available", False):
        return GeometryReport(
            available=False, note=getattr(model, "note", None) or "Kein Modell."
        )

    bericht = GeometryReport()
    substrat = model.chain_substrate
    strang = model.chain_dnazyme

    # ---- In-line-Winkel
    stelle = cleavage_residue if cleavage_residue is not None else model.cleavage_residue
    if stelle is None and model.substrate:
        # Ohne Angabe: die Mitte des Substrats ist die beste Vermutung — und
        # sie wird als Vermutung gekennzeichnet.
        mitte = model.substrate[len(model.substrate) // 2]
        stelle = mitte.residue_number
        bericht.warnings.append(
            f"Keine Spaltstelle angegeben. Gemessen wurde an Rest {stelle} der "
            "Substratkette — das ist eine Annahme, keine Zuordnung."
        )
    if stelle is not None and substrat:
        bericht.inline = inline_angle(atoms, substrat, stelle)
    else:
        bericht.inline = InlineAngle(
            available=False,
            note="Ohne Substratkette gibt es keine Spaltstelle zum Messen.",
        )

    # ---- Abstände der modifizierten Positionen
    modifiziert = [p for p in model.positions if p.modification]
    if not modifiziert:
        bericht.warnings.append(
            "Keine modifizierte Position im Strang — es gibt nichts einzuordnen."
        )

    spalt_atom = (
        _representative(atoms, substrat, stelle)
        if stelle is not None and substrat
        else None
    )

    kern = core_range
    for eintrag in modifiziert:
        eigenes = _representative(atoms, strang, eintrag.residue_number)

        if spalt_atom is not None and eigenes is not None:
            bericht.to_cleavage.append(
                PositionDistance(
                    position=eintrag.position,
                    code=eintrag.code,
                    modification=eintrag.modification,
                    angstrom=distance(xyz(eigenes), xyz(spalt_atom)),
                    note=None,
                )
            )
        else:
            bericht.to_cleavage.append(
                PositionDistance(
                    position=eintrag.position,
                    code=eintrag.code,
                    modification=eintrag.modification,
                    note=(
                        "Diese Position hat keine Koordinaten — sie liegt "
                        "außerhalb der Referenz."
                        if eigenes is None
                        else "Keine Spaltstelle zum Messen."
                    ),
                )
            )

        if kern is not None:
            if eintrag.position < kern[0]:
                abstand_nt = kern[0] - eintrag.position
            elif eintrag.position > kern[1]:
                abstand_nt = eintrag.position - kern[1]
            else:
                abstand_nt = 0
            kern_atom = None
            if eigenes is not None:
                naechster = min(
                    range(kern[0], kern[1] + 1),
                    key=lambda p: abs(p - eintrag.position),
                )
                kern_atom = _representative(
                    atoms, strang, naechster + (eintrag.residue_number - eintrag.position)
                )
            bericht.to_core.append(
                PositionDistance(
                    position=eintrag.position,
                    code=eintrag.code,
                    modification=eintrag.modification,
                    nucleotides=abstand_nt,
                    angstrom=(
                        distance(xyz(eigenes), xyz(kern_atom))
                        if eigenes is not None and kern_atom is not None
                        else None
                    ),
                    note="liegt im Kern" if abstand_nt == 0 else None,
                )
            )

        # ---- Ionen
        if eigenes is not None:
            kontakte = [
                IonContact(
                    residue=ion.residue,
                    element=ion.element,
                    chain=ion.chain,
                    number=ion.residue_number,
                    angstrom=distance(xyz(eigenes), xyz(ion)),
                )
                for ion in atoms
                if ion.residue.strip().upper() in ION_RESIDUES
            ]
            nah = sorted(
                (k for k in kontakte if k.angstrom <= ION_WARNING_A),
                key=lambda k: k.angstrom,
            )
            if nah:
                bericht.ion_contacts[eintrag.position] = nah
                bericht.warnings.append(
                    f"Position {eintrag.position} liegt {nah[0].angstrom:.1f} Å "
                    f"von {nah[0].residue} entfernt. Eine Modifikation nahe "
                    "einer Ionenbindungsstelle ist ein Warnsignal."
                )

    return bericht


@dataclass
class Measurement:
    """Das allgemeine Messwerkzeug (PHASEN.md 6.3)."""

    kind: str
    atoms: list[str]
    value: float | None = None
    unit: str = ""
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "atoms": self.atoms,
            "value": None if self.value is None else round(self.value, 3),
            "unit": self.unit,
            "note": self.note,
        }


def measure(atoms: list[Atom], selections: list[str]) -> Measurement:
    """Abstand zwischen zwei, Winkel zwischen drei Atomen."""
    if len(selections) not in (2, 3):
        return Measurement(
            kind="unbrauchbar",
            atoms=selections,
            note="Zwei Atome ergeben einen Abstand, drei einen Winkel.",
        )

    punkte: list[Point] = []
    for auswahl in selections:
        kette, nummer, name = parse_selection(auswahl)
        atom = find_atom(atoms, kette, nummer, name)
        if atom is None:
            return Measurement(
                kind="abstand" if len(selections) == 2 else "winkel",
                atoms=selections,
                note=f"`{auswahl}` gibt es in dieser Struktur nicht.",
            )
        punkte.append(xyz(atom))

    if len(punkte) == 2:
        return Measurement("abstand", selections, distance(*punkte), "Å")
    return Measurement("winkel", selections, angle(*punkte), "°")
