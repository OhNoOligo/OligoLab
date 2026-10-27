"""Fragmente für ORCA vorbereiten (PHASEN.md 6.5, freiwillig).

**Hier wird nichts gerechnet.** Diese Datei schneidet ein Fragment aus einer
Struktur, saettigt die abgeschnittenen Bindungen mit Wasserstoff ab und
schreibt eine ORCA-Eingabedatei. Ob die jemals gerechnet wird, entscheidet
der Nutzer an seinem eigenen Rechner — Quantenchemie laeuft nicht nebenbei
im Hintergrund einer Oberflaeche.

Die Wasserstoffe sitzen auf der Richtung der abgeschnittenen Bindung, mit
einer Standard-Bindungslaenge. Das ist das uebliche Verfahren (link atoms)
und es ist eine Naeherung — sie steht als solche in der Ausgabe.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

from app.pdb import Atom

Purpose = Literal["geometrie", "wechselwirkung", "potential"]

#: Was ORCA rechnen soll, und womit (PHASEN.md 6.5).
PURPOSES: dict[Purpose, dict[str, str]] = {
    "geometrie": {
        "label": "Geometrieoptimierung",
        "keywords": "! r2SCAN-3c Opt",
        "note": "Zusammengesetztes Verfahren, für Geometrien gedacht.",
    },
    "wechselwirkung": {
        "label": "Wechselwirkungsenergie",
        "keywords": "! DLPNO-CCSD(T) def2-TZVP def2-TZVP/C TightSCF",
        "note": (
            "Mit Counterpoise-Korrektur rechnen, sonst ist die Energie durch "
            "den Basissatzüberlagerungsfehler zu günstig."
        ),
    },
    "potential": {
        "label": "Elektrostatisches Potential",
        "keywords": "! B3LYP def2-TZVP TightSCF",
        "note": "Erzeugt die Dichte; das Potential danach mit orca_vpot.",
    },
}

#: Unterhalb dieser Atomzahl ist Quantenchemie ueberhaupt sinnvoll.
SENSIBLE_ATOM_COUNT = 300

#: Uebliche Bindungslaengen zum Absaettigen, in Angstroem.
H_BOND_LENGTH = {"C": 1.09, "N": 1.01, "O": 0.96, "P": 1.42, "S": 1.34}

#: Was als Bindung zaehlt. Grob, aber fuer das Absaettigen ausreichend.
BOND_CUTOFF_A = 1.95


@dataclass
class Fragment:
    """Ein herausgeschnittenes Stueck samt dem, was daran kuenstlich ist."""

    atoms: list[tuple[str, float, float, float]] = field(default_factory=list)
    #: Wie viele Wasserstoffe zum Absaettigen dazukamen.
    added_hydrogens: int = 0
    residues: list[str] = field(default_factory=list)
    charge: int = 0
    multiplicity: int = 1
    note: str | None = None

    @property
    def atom_count(self) -> int:
        return len(self.atoms)

    @property
    def sensible(self) -> bool:
        return self.atom_count <= SENSIBLE_ATOM_COUNT

    def as_dict(self) -> dict[str, Any]:
        return {
            "atom_count": self.atom_count,
            "added_hydrogens": self.added_hydrogens,
            "residues": self.residues,
            "charge": self.charge,
            "multiplicity": self.multiplicity,
            "sensible": self.sensible,
            "size_hint": (
                f"{self.atom_count} Atome. Unter etwa {SENSIBLE_ATOM_COUNT} ist "
                "Quantenchemie sinnvoll; darüber dauert es sehr lange."
            ),
            "note": self.note,
        }


def cut(
    atoms: list[Atom],
    residues: list[tuple[str, int]],
    replace_sugar_with_methyl: bool = False,
) -> Fragment:
    """Die genannten Reste herausschneiden und absaettigen.

    `residues` ist eine Liste aus Kette und Restnummer.
    """
    gewaehlt = {(kette, nummer) for kette, nummer in residues}
    drin = [a for a in atoms if (a.chain, a.residue_number) in gewaehlt]
    draussen = [a for a in atoms if (a.chain, a.residue_number) not in gewaehlt]

    if not drin:
        return Fragment(note="Zu dieser Auswahl gibt es keine Atome.")

    if replace_sugar_with_methyl:
        # Nur C1' bleibt vom Zucker stehen; daraus wird beim Absaettigen
        # eine Methylgruppe.
        zucker = {"P", "OP1", "OP2", "O1P", "O2P", "O5'", "C5'", "C4'",
                  "O4'", "C3'", "O3'", "C2'", "O2'"}
        drin = [a for a in drin if a.name.upper() not in zucker]

    fragment = Fragment(
        atoms=[(a.element or a.name[0], a.x, a.y, a.z) for a in drin],
        residues=sorted({f"{a.chain}:{a.residue_number}:{a.residue}" for a in drin}),
    )

    # Abgeschnittene Bindungen: ein Atom im Fragment, der Partner draussen.
    for innen in drin:
        for aussen in draussen:
            abstand = math.dist(
                (innen.x, innen.y, innen.z), (aussen.x, aussen.y, aussen.z)
            )
            if abstand > BOND_CUTOFF_A or abstand == 0:
                continue
            laenge = H_BOND_LENGTH.get(innen.element.upper()[:1], 1.09)
            anteil = laenge / abstand
            fragment.atoms.append(
                (
                    "H",
                    innen.x + (aussen.x - innen.x) * anteil,
                    innen.y + (aussen.y - innen.y) * anteil,
                    innen.z + (aussen.z - innen.z) * anteil,
                )
            )
            fragment.added_hydrogens += 1

    # Jedes Phosphat traegt eine negative Ladung.
    phosphate = sum(1 for a in drin if a.name.upper() == "P")
    fragment.charge = -phosphate
    if fragment.added_hydrogens:
        fragment.note = (
            f"{fragment.added_hydrogens} Wasserstoff(e) sitzen auf "
            "abgeschnittenen Bindungen. Sie sind eine Näherung und stehen so "
            "in keiner Struktur."
        )
    return fragment


def write_input(
    fragment: Fragment,
    purpose: Purpose = "geometrie",
    title: str = "OligoLab-Fragment",
    processors: int = 4,
) -> str:
    """Eine ORCA-Eingabedatei — zum Mitnehmen, nicht zum Rechnen."""
    rezept = PURPOSES.get(purpose)
    if rezept is None:
        raise ValueError(f"Unbekannter Zweck `{purpose}`.")

    zeilen = [
        f"# {title}",
        "# Erzeugt von OligoLab. Hier wurde nichts gerechnet — diese Datei",
        "# ist die Vorbereitung. Prüfe Ladung und Multiplizität selbst.",
        f"# {rezept['note']}",
    ]
    if fragment.note:
        zeilen.append(f"# {fragment.note}")
    if not fragment.sensible:
        zeilen.append(
            f"# ACHTUNG: {fragment.atom_count} Atome. Das ist viel für eine "
            "Quantenrechnung."
        )
    zeilen += [
        rezept["keywords"],
        f"%pal nprocs {processors} end",
        "",
        f"* xyz {fragment.charge} {fragment.multiplicity}",
    ]
    for element, x, y, z in fragment.atoms:
        zeilen.append(f"  {element:<2} {x:>12.6f} {y:>12.6f} {z:>12.6f}")
    zeilen += ["*", ""]
    return "\n".join(zeilen)
