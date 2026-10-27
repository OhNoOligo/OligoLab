"""Eine Struktur mit bekannter Geometrie, für die Tests der Phase 6.

Ein Messgerät prüft man an einem bekannten Maß, nicht an einem unbekannten.
Darum wird hier eine Struktur erzeugt, deren Winkel und Abstände vorher
feststehen — und nicht eine echte geladen, deren richtige Antwort erst
wieder gemessen werden müsste.

Die Koordinaten sind frei gewählt und stellen keine Nukleinsäure dar. Sie
müssen nur eines können: die Messfunktionen auf die Probe stellen.
"""

from __future__ import annotations

PURINE_ATOMS = ["N9", "C8", "N7", "C5", "C6", "N1", "C2", "N3", "C4"]
PYRIMIDINE_ATOMS = ["N1", "C2", "N3", "C4", "C5", "C6"]
EXTRA = {
    "A": ["N6"], "G": ["O6", "N2"], "C": ["N4"],
    "T": ["O4", "C7"], "U": ["O4"],
}
BACKBONE = ["P", "OP1", "OP2", "O5'", "C5'", "C4'", "O4'", "C3'", "O3'", "C1'"]


def _atoms_for(letter: str, is_rna: bool) -> list[str]:
    namen = list(BACKBONE)
    if is_rna:
        namen.append("O2'")
    namen += PURINE_ATOMS if letter in "AGI" else PYRIMIDINE_ATOMS
    namen += EXTRA.get(letter, [])
    return namen


def _line(serial, name, residue, chain, number, x, y, z, element, kind="ATOM"):
    gesetzt = name if len(name) >= 4 else f" {name:<3}"
    return (
        f"{kind:<6}{serial:>5} {gesetzt:<4} {residue:>3} {chain:1}"
        f"{number:>4}{'':4}{x:>8.3f}{y:>8.3f}{z:>8.3f}"
        f"{1.00:>6.2f}{0.00:>6.2f}{'':10}{element:>2}"
    )


def build_pdb(
    dna: str,
    rna: str,
    dna_chain: str = "A",
    rna_chain: str = "B",
    first_dna: int = 1,
    first_rna: int = 1,
    inline_residue: int | None = None,
    inline_angle_deg: float = 180.0,
    ions: list[tuple[str, float, float, float]] | None = None,
) -> str:
    """Eine Strukturdatei mit zwei Ketten.

    `inline_residue` legt fest, an welchem Rest der Substratkette O2', P und
    O5' so gesetzt werden, dass genau `inline_angle_deg` herauskommt.
    """
    import math

    zeilen = [
        "TITLE     EINE ERFUNDENE STRUKTUR FUER DIE TESTS",
        "EXPDTA    THEORETICAL MODEL",
        "REMARK   2 RESOLUTION.    1.80 ANGSTROM.",
    ]
    seriennummer = 1

    def kette(sequenz: str, kennung: str, erster: int, ist_rna: bool, versatz: float):
        nonlocal seriennummer
        for index, buchstabe in enumerate(sequenz):
            nummer = erster + index
            name = ("" if ist_rna else "D") + buchstabe
            # Jeder Rest auf einer eigenen Höhe, die Atome dicht beieinander.
            z = index * 3.4
            for atom_index, atom in enumerate(_atoms_for(buchstabe, ist_rna)):
                winkel = atom_index * 0.6
                x = versatz + 1.4 * math.cos(winkel)
                y = 1.4 * math.sin(winkel)
                zeilen.append(
                    _line(
                        seriennummer, atom, name, kennung, nummer,
                        x, y, z + atom_index * 0.05, atom[0],
                    )
                )
                seriennummer += 1

    kette(dna, dna_chain, first_dna, False, 0.0)
    kette(rna, rna_chain, first_rna, True, 12.0)

    if inline_residue is not None:
        # Die drei Atome neu setzen: O2' am Rest n, P und O5' am Rest n+1.
        # Der Winkel O2'–P–O5' wird genau der gewünschte.
        bogen = math.radians(180.0 - inline_angle_deg)
        gesetzt = {
            (rna_chain, inline_residue, "O2'"): (0.0, 0.0, 0.0),
            (rna_chain, inline_residue + 1, "P"): (3.2, 0.0, 0.0),
            (rna_chain, inline_residue + 1, "O5'"): (
                3.2 + 1.6 * math.cos(bogen),
                1.6 * math.sin(bogen),
                0.0,
            ),
        }
        neu = []
        for zeile in zeilen:
            if not zeile.startswith(("ATOM", "HETATM")):
                neu.append(zeile)
                continue
            schluessel = (zeile[21], int(zeile[22:26]), zeile[12:16].strip())
            if schluessel in gesetzt:
                x, y, z = gesetzt[schluessel]
                zeile = zeile[:30] + f"{x:>8.3f}{y:>8.3f}{z:>8.3f}" + zeile[54:]
            neu.append(zeile)
        zeilen = neu

    for index, (name, x, y, z) in enumerate(ions or [], start=1):
        zeilen.append(
            _line(
                seriennummer + index, name, name, "C", 900 + index,
                x, y, z, name[:2], kind="HETATM",
            )
        )

    zeilen.append("END")
    return "\n".join(zeilen) + "\n"


def build_cif(dna: str, rna: str) -> str:
    """Dieselbe Struktur als mmCIF — zum Prüfen des zweiten Lesewegs."""
    zeilen = [
        "data_TEST",
        "_struct.title 'Eine erfundene Struktur'",
        "_exptl.method 'THEORETICAL MODEL'",
        "_refine.ls_d_res_high 1.80",
        "_citation.title 'Kein echtes Zitat'",
        "loop_",
        "_atom_site.group_PDB",
        "_atom_site.id",
        "_atom_site.type_symbol",
        "_atom_site.label_atom_id",
        "_atom_site.label_comp_id",
        "_atom_site.label_seq_id",
        "_atom_site.auth_asym_id",
        "_atom_site.auth_seq_id",
        "_atom_site.Cartn_x",
        "_atom_site.Cartn_y",
        "_atom_site.Cartn_z",
    ]
    seriennummer = 1
    for sequenz, kennung, ist_rna, versatz in ((dna, "A", False, 0.0), (rna, "B", True, 12.0)):
        for index, buchstabe in enumerate(sequenz):
            name = ("" if ist_rna else "D") + buchstabe
            for atom_index, atom in enumerate(_atoms_for(buchstabe, ist_rna)):
                zeilen.append(
                    f"ATOM {seriennummer} {atom[0]} \"{atom}\" {name} {index + 1} "
                    f"{kennung} {index + 1} {versatz + atom_index * 0.1:.3f} "
                    f"{atom_index * 0.1:.3f} {index * 3.4:.3f}"
                )
                seriennummer += 1
    zeilen.append("#")
    return "\n".join(zeilen) + "\n"
