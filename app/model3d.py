"""Ein Modell bauen (PHASEN.md 6.2).

Das Verfahren: die Sequenz des Kandidaten auf eine Referenzstruktur faedeln.
Gleiche Position, gleiche Rueckgratkoordinaten, ausgetauschte Base. Was in
den Armen ueber die Referenz hinausragt, wird als ideale Rueckgratspur
verlaengert.

**Das ist ein Modell.** Die Koordinaten stammen aus der Referenz, nur die
Sequenz ist die eigene. Jede Position traegt deshalb mit, wie sie zustande
kam — genau wie jede Zahl im Rest des Programms (CLAUDE.md, Regel 3):

    uebernommen   Base gleich, alle Atome aus der Referenz
    geruest       Purin gegen Purin (oder Pyrimidin gegen Pyrimidin):
                  das gemeinsame Ringgeruest bleibt, die unterschiedlichen
                  Substituenten fallen weg
    nur_zucker    Purin gegen Pyrimidin: nur Zucker und Phosphat bleiben.
                  Die Base wird NICHT geraten
    ideal         ausserhalb der Referenz, ideale Spur

Was hier NICHT passiert: eine Base an eine Stelle setzen, deren Geometrie
niemand gerechnet hat. Ein hingeschobenes Ringatom sieht im Bild genauso
aus wie ein gemessenes — und das ist der Grund, es zu lassen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

from app.models import Oligo, Reliability
from app.notation import parse
from app.pdb import Atom, Structure, atoms_of, read_text
from app.registry import Registry, get_registry

Provenance = Literal["uebernommen", "geruest", "nur_zucker", "ideal"]

PROVENANCE_LABEL: dict[Provenance, str] = {
    "uebernommen": "aus der Referenz übernommen",
    "geruest": "Ringgerüst der Referenz, Substituenten entfernt",
    "nur_zucker": "nur Zucker und Phosphat, Base nicht modelliert",
    "ideal": "ideale Rückgratspur, nicht aus der Referenz",
}

PROVENANCE_RELIABILITY: dict[Provenance, Reliability] = {
    "uebernommen": Reliability.PARAMETER,
    "geruest": Reliability.APPROX,
    "nur_zucker": Reliability.APPROX,
    "ideal": Reliability.APPROX,
}

PURINES = {"A", "G", "I"}
PYRIMIDINES = {"C", "T", "U"}

#: Atome, die alle Nukleotide teilen — Zucker und Phosphat.
BACKBONE = {
    "P", "OP1", "OP2", "O1P", "O2P", "O5'", "C5'", "C4'", "O4'",
    "C3'", "O3'", "C2'", "O2'", "C1'",
}
#: Das gemeinsame Ringgeruest der Purine und der Pyrimidine.
PURINE_CORE = {"N9", "C8", "N7", "C5", "C6", "N1", "C2", "N3", "C4"}
PYRIMIDINE_CORE = {"N1", "C2", "N3", "C4", "C5", "C6"}


def residue_name(letter: str, is_rna: bool) -> str:
    """Wie der Rest in der Datei heissen muss."""
    buchstabe = letter.upper()
    if is_rna:
        return "U" if buchstabe == "T" else buchstabe
    return "D" + ("T" if buchstabe == "U" else buchstabe)


@dataclass
class ModelPosition:
    """Eine Position im Modell und wie sie zustande kam."""

    position: int
    code: str
    base: str
    residue_number: int
    chain: str
    provenance: Provenance
    #: Welche Modifikation hier sitzt, falls eine sitzt.
    modification: str | None = None
    klasse: str = "dna"
    note: str | None = None

    @property
    def reliability(self) -> Reliability:
        return PROVENANCE_RELIABILITY[self.provenance]

    def as_dict(self) -> dict[str, Any]:
        return {
            "position": self.position,
            "code": self.code,
            "base": self.base,
            "residue_number": self.residue_number,
            "chain": self.chain,
            "provenance": self.provenance,
            "provenance_label": PROVENANCE_LABEL[self.provenance],
            "reliability": self.reliability.value,
            "modification": self.modification,
            "klasse": self.klasse,
            "note": self.note,
        }


@dataclass
class Model:
    """Das fertige Modell: PDB-Text und was darin wie entstanden ist."""

    available: bool = True
    pdb: str = ""
    reference_id: str | None = None
    positions: list[ModelPosition] = field(default_factory=list)
    substrate: list[ModelPosition] = field(default_factory=list)
    chain_dnazyme: str = "A"
    chain_substrate: str = "B"
    #: Position des Rests, hinter dem geschnitten wird (im Substrat).
    cleavage_residue: int | None = None
    warnings: list[str] = field(default_factory=list)
    note: str | None = None

    @property
    def disclaimer(self) -> str:
        return (
            "Das ist ein Modell. Die Koordinaten stammen aus der Referenz "
            f"{self.reference_id or '—'}, nur die Sequenz ist deine. Jede "
            "Position trägt mit, wie sie zustande kam."
        )

    def counts(self) -> dict[str, int]:
        gezaehlt: dict[str, int] = {}
        for eintrag in self.positions + self.substrate:
            gezaehlt[eintrag.provenance] = gezaehlt.get(eintrag.provenance, 0) + 1
        return gezaehlt

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "pdb": self.pdb,
            "reference_id": self.reference_id,
            "positions": [p.as_dict() for p in self.positions],
            "substrate": [p.as_dict() for p in self.substrate],
            "chain_dnazyme": self.chain_dnazyme,
            "chain_substrate": self.chain_substrate,
            "cleavage_residue": self.cleavage_residue,
            "counts": self.counts(),
            "disclaimer": self.disclaimer,
            "warnings": self.warnings,
            "note": self.note,
        }


# ------------------------------------------------------------- faedeln


def _by_residue(atome: list[Atom], chain: str) -> dict[int, list[Atom]]:
    nach_rest: dict[int, list[Atom]] = {}
    for atom in atome:
        if atom.chain != chain:
            continue
        if atom.alt not in ("", "A"):
            # Mehrfachbesetzungen: die erste genuegt fuer ein Modell.
            continue
        nach_rest.setdefault(atom.residue_number, []).append(atom)
    return nach_rest


def _base_letter(residue: str) -> str:
    name = residue.strip().upper()
    if name.startswith("D") and len(name) == 2:
        return name[1]
    return name[:1]


def _keep_atoms(alt: str, neu: str) -> tuple[set[str] | None, Provenance]:
    """Welche Atome eines Rests beim Austausch stehen bleiben duerfen."""
    if alt == neu:
        return None, "uebernommen"  # None heisst: alle
    if alt in PURINES and neu in PURINES:
        return BACKBONE | PURINE_CORE, "geruest"
    if alt in PYRIMIDINES and neu in PYRIMIDINES:
        return BACKBONE | PYRIMIDINE_CORE, "geruest"
    return set(BACKBONE), "nur_zucker"


def thread(
    oligo: Oligo | str,
    structure: Structure,
    structure_text: str | None = None,
    core_range: tuple[int, int] | None = None,
    registry: Registry | None = None,
) -> Model:
    """Die Sequenz auf die Referenz faedeln.

    Ausgerichtet wird am katalytischen Kern: er ist in der Referenz und im
    Kandidaten dieselbe Sequenz und damit der einzige Anker, der nicht
    geraten ist. Hat die Referenz keinen erkennbaren Kern, wird am Anfang
    der Kette ausgerichtet und das steht als Warnung dabei.
    """
    from app import dnazyme

    reg = registry or get_registry()
    strang = parse(oligo, reg) if isinstance(oligo, str) else oligo

    if not structure.available:
        return Model(
            available=False,
            reference_id=structure.id,
            note=structure.note or "Die Referenzstruktur ist nicht geladen.",
        )

    kette = structure.dnazyme_chain
    if kette is None:
        return Model(
            available=False,
            reference_id=structure.id,
            note=(
                "Diese Struktur enthält keine DNA-Kette. Auf eine reine "
                "RNA-Struktur lässt sich kein DNAzym fädeln."
            ),
        )

    text = structure_text
    if text is None:
        if structure.path is None:
            return Model(
                available=False,
                reference_id=structure.id,
                note="Zu dieser Struktur liegt keine Datei vor.",
            )
        text = read_text(structure.path)

    atome = atoms_of(text)
    reste = _by_residue(atome, kette.id)
    nummern = sorted(reste)

    # Den Kern in BEIDEN finden: im Kandidaten und in der Referenzkette.
    teile = dnazyme.detect_parts(strang, reg)
    kern_im_strang = (
        (teile.core_part.start, teile.core_part.end)
        if teile.core_part
        else core_range
    )

    warnungen: list[str] = []
    versatz = 0
    if kern_im_strang and teile.core is not None:
        index = kette.sequence.find(teile.core.sequence)
        if index >= 0:
            # Rest-Nummer, an der der Kern in der Referenz beginnt.
            kern_in_referenz = nummern[index]
            versatz = kern_in_referenz - kern_im_strang[0]
        else:
            warnungen.append(
                "In der Referenz steckt der katalytische Kern nicht als "
                "zusammenhängende Sequenz. Ausgerichtet wurde am Anfang der "
                "Kette — die Zuordnung der Positionen ist damit eine Annahme."
            )
            versatz = (nummern[0] if nummern else 1) - 1
    else:
        warnungen.append(
            "Im Kandidaten wurde kein katalytischer Kern gefunden. "
            "Ausgerichtet wurde am Anfang der Kette."
        )
        versatz = (nummern[0] if nummern else 1) - 1

    zeilen: list[str] = []
    positionen: list[ModelPosition] = []
    seriennummer = 1

    for monomer in strang.monomers:
        rest_nummer = monomer.position + versatz
        neue_base = (monomer.spec.base_parent or monomer.spec.code or "N").upper()
        ist_rna = monomer.spec.typ.lower().startswith("rna")
        modifikation = (
            monomer.modifications[0].code if monomer.modifications else None
        )

        vorlage = reste.get(rest_nummer)
        if not vorlage:
            # Ausserhalb der Referenz: ideale Spur, spaeter angehaengt.
            positionen.append(
                ModelPosition(
                    position=monomer.position,
                    code=monomer.spec.code,
                    base=neue_base,
                    residue_number=rest_nummer,
                    chain=kette.id,
                    provenance="ideal",
                    modification=modifikation,
                    klasse=monomer.klasse,
                )
            )
            continue

        alte_base = _base_letter(vorlage[0].residue)
        behalten, herkunft = _keep_atoms(alte_base, neue_base)
        name = residue_name(neue_base, ist_rna)

        for atom in vorlage:
            if behalten is not None and atom.name not in behalten:
                continue
            # Eine 2'-OH gibt es nur in RNA; eine DNA-Vorlage hat sie nicht,
            # und erfunden wird sie nicht.
            zeilen.append(
                _pdb_line(seriennummer, atom.name, name, kette.id, rest_nummer, atom)
            )
            seriennummer += 1

        positionen.append(
            ModelPosition(
                position=monomer.position,
                code=monomer.spec.code,
                base=neue_base,
                residue_number=rest_nummer,
                chain=kette.id,
                provenance=herkunft,
                modification=modifikation,
                klasse=monomer.klasse,
                note=(
                    None
                    if herkunft == "uebernommen"
                    else f"{alte_base} → {neue_base} auf der Vorlage"
                ),
            )
        )

    # Das Substrat bleibt, wie es ist: es ist nicht unsere Sequenz.
    substrat: list[ModelPosition] = []
    substrat_kette = structure.substrate_chain
    if substrat_kette is not None:
        for nummer, atome_des_rests in sorted(
            _by_residue(atome, substrat_kette.id).items()
        ):
            for atom in atome_des_rests:
                zeilen.append(
                    _pdb_line(
                        seriennummer,
                        atom.name,
                        atom.residue,
                        substrat_kette.id,
                        nummer,
                        atom,
                    )
                )
                seriennummer += 1
            substrat.append(
                ModelPosition(
                    position=nummer,
                    code=_base_letter(atome_des_rests[0].residue),
                    base=_base_letter(atome_des_rests[0].residue),
                    residue_number=nummer,
                    chain=substrat_kette.id,
                    provenance="uebernommen",
                    klasse="rna",
                )
            )

    # Ionen mitnehmen: sie sind fuer die Abstandsmessung wichtig.
    for ion in structure.ions:
        zeilen.append(
            _hetatm_line(
                seriennummer, ion["residue"], ion["chain"], ion["number"], ion["xyz"],
                ion["element"],
            )
        )
        seriennummer += 1

    ideal = sum(1 for p in positionen if p.provenance == "ideal")
    if ideal:
        warnungen.append(
            f"{ideal} Position(en) liegen außerhalb der Referenz. Sie haben "
            "keine Koordinaten aus der Struktur und sind im Bild nicht "
            "dargestellt."
        )
    nur_zucker = sum(1 for p in positionen if p.provenance == "nur_zucker")
    if nur_zucker:
        warnungen.append(
            f"An {nur_zucker} Position(en) steht ein Purin gegen ein Pyrimidin. "
            "Dort bleiben nur Zucker und Phosphat — die Base wird nicht geraten."
        )

    return Model(
        available=True,
        pdb="\n".join(zeilen) + "\nEND\n",
        reference_id=structure.id,
        positions=positionen,
        substrate=substrat,
        chain_dnazyme=kette.id,
        chain_substrate=substrat_kette.id if substrat_kette else "",
        warnings=warnungen,
    )


def _pdb_line(
    serial: int, name: str, residue: str, chain: str, number: int, atom: Atom
) -> str:
    return _format_atom(
        "ATOM", serial, name, residue, chain, number,
        (atom.x, atom.y, atom.z), atom.element,
    )


def _hetatm_line(
    serial: int, residue: str, chain: str, number: int,
    xyz: list[float], element: str,
) -> str:
    return _format_atom(
        "HETATM", serial, residue, residue, chain, number, tuple(xyz), element
    )


def _format_atom(
    kind: str, serial: int, name: str, residue: str, chain: str,
    number: int, xyz: tuple[float, float, float], element: str,
) -> str:
    """Eine Zeile im PDB-Format, Spalte fuer Spalte.

    Das Format ist spaltengenau: ein Zeichen daneben, und jeder Betrachter
    liest etwas anderes.
    """
    gesetzt = name if len(name) >= 4 else f" {name:<3}"
    return (
        f"{kind:<6}{serial:>5} {gesetzt:<4}{'':1}{residue:>3} {chain:1}"
        f"{number:>4}{'':4}{xyz[0]:>8.3f}{xyz[1]:>8.3f}{xyz[2]:>8.3f}"
        f"{1.00:>6.2f}{0.00:>6.2f}{'':10}{element:>2}"
    )


# --------------------------------------------------- ideale Rueckgratspur

#: A-Form: Anstieg je Rest und Drehung je Rest. Fiber-Standardwerte.
A_FORM_RISE_A = 2.81
A_FORM_TWIST_DEG = 32.7
A_FORM_P_RADIUS_A = 8.8


def ideal_trace(
    count: int,
    start_angle_deg: float = 0.0,
    start_z: float = 0.0,
    rise: float = A_FORM_RISE_A,
    twist: float = A_FORM_TWIST_DEG,
    radius: float = A_FORM_P_RADIUS_A,
) -> list[tuple[float, float, float]]:
    """Phosphorlagen einer idealen A-Helix.

    Bewusst NUR die Phosphate: eine vollstaendige Nukleotidgeometrie aus
    Standardwerten zusammenzusetzen hiesse, Atomlagen zu erfinden, die
    hinterher wie gemessene aussehen. Die Spur reicht, um zu zeigen, wo ein
    verlaengerter Arm entlanglaeuft — und mehr behauptet sie nicht.
    """
    punkte: list[tuple[float, float, float]] = []
    for index in range(count):
        winkel = math.radians(start_angle_deg + index * twist)
        punkte.append(
            (
                radius * math.cos(winkel),
                radius * math.sin(winkel),
                start_z + index * rise,
            )
        )
    return punkte
