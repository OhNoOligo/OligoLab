"""Eine eigene Base in 3D bauen und auf das Rückgrat setzen.

Das Fädeln in `model3d.py` nimmt Koordinaten aus der Referenz. Fuer einen
selbst entworfenen Baustein — etwa ein Guanin, bei dem statt des O6 ein
Imidazolring sitzt — gibt es dort nichts zu nehmen: diese Atome stehen in
keiner Kristallstruktur.

Hier werden sie gebaut:

1. Das SMILES des Nukleosids wird mit RDKit in 3D gebracht (ETKDG) und mit
   MMFF entspannt. Das ist eine Kraftfeldgeometrie, keine gemessene.
2. Im gebauten Moleküel wird der Zucker gesucht — der Fuenfring mit genau
   einem Sauerstoff — und seine Atome bekommen ihre Namen: O4', C1' (das am
   Basen-Stickstoff), C4' (das mit dem C5' daran), C3', C2'.
3. Dieser Zucker wird auf den Zucker der Referenz gelegt (Kabsch). Die
   Drehung, die das tut, wird auf die ganze Base angewandt.
4. Zurueck kommen NUR die Basenatome. Zucker und Phosphat bleiben die der
   Referenz — am Rueckgrat wird nichts erfunden.

Damit steht die eigene Base dort, wo sie am Rueckgrat haengen muesste, und
in der Stellung, die der glykosidischen Bindung entspricht. Was sie NICHT
ist: eine Vorhersage, wie sich die Base im Duplex wirklich dreht. Sie traegt
darum das Kennzeichen `gebaut` und nicht `uebernommen`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Die Zuckeratome, auf die ausgerichtet wird — in dieser Reihenfolge.
SUGAR_NAMES = ("C1'", "C2'", "C3'", "C4'", "O4'")
#: So viele davon muessen in der Referenz stehen, sonst wird nicht gebaut.
MIN_ANCHORS = 3


@dataclass
class BuiltResidue:
    """Eine gebaute Base samt dem, was an ihr unsicher ist."""

    available: bool = True
    #: (Name, Element, x, y, z) je Atom der Base.
    atoms: list[tuple[str, str, float, float, float]] = field(default_factory=list)
    #: Wie gut der Zucker auf den der Referenz passt, in Ångström (RMSD).
    rmsd: float | None = None
    anchors: list[str] = field(default_factory=list)
    formula: str | None = None
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "atom_count": len(self.atoms),
            "rmsd": None if self.rmsd is None else round(self.rmsd, 3),
            "anchors": self.anchors,
            "formula": self.formula,
            "note": self.note,
        }


def _embed(smiles: str):
    """Das Nukleosid in 3D bringen. Gibt (mol_ohne_H, conf) oder None."""
    from rdkit import Chem
    from rdkit.Chem import AllChem

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None, "Das SMILES ließ sich nicht lesen."

    mit_h = Chem.AddHs(mol)
    parameter = AllChem.ETKDGv3()
    parameter.randomSeed = 0xC0FFEE  # dieselbe Eingabe, dieselbe Geometrie
    if AllChem.EmbedMolecule(mit_h, parameter) != 0:
        return None, "RDKit konnte für dieses Molekül keine 3D-Lage finden."
    try:
        AllChem.MMFFOptimizeMolecule(mit_h, maxIters=500)
    except ValueError:
        # Ohne MMFF-Parameter bleibt die ETKDG-Lage stehen. Das ist
        # gröber, aber brauchbar — und es wird gesagt.
        pass
    return Chem.RemoveHs(mit_h), None


def _find_sugar(mol) -> dict[str, int] | None:
    """Den Zucker finden und seine Atome benennen.

    Gesucht wird der Fuenfring mit genau einem Sauerstoff und vier
    Kohlenstoffen. Die Namen folgen danach aus der Verknuepfung, nicht aus
    einer Mustererkennung: C1' haengt am Basen-Stickstoff, C4' traegt das
    C5'.
    """
    for ring in mol.GetRingInfo().AtomRings():
        if len(ring) != 5:
            continue
        sauerstoff = [i for i in ring if mol.GetAtomWithIdx(i).GetSymbol() == "O"]
        kohlenstoff = [i for i in ring if mol.GetAtomWithIdx(i).GetSymbol() == "C"]
        if len(sauerstoff) != 1 or len(kohlenstoff) != 4:
            continue

        o4, im_ring = sauerstoff[0], set(ring)

        # C1': der Ringkohlenstoff am Sauerstoff, der einen Stickstoff
        # ausserhalb des Rings trägt — die glykosidische Bindung.
        c1 = c4 = None
        for nachbar in mol.GetAtomWithIdx(o4).GetNeighbors():
            index = nachbar.GetIdx()
            if index not in im_ring:
                continue
            stickstoff = [
                n.GetIdx()
                for n in nachbar.GetNeighbors()
                if n.GetSymbol() == "N" and n.GetIdx() not in im_ring
            ]
            exo_c = [
                n.GetIdx()
                for n in nachbar.GetNeighbors()
                if n.GetSymbol() == "C" and n.GetIdx() not in im_ring
            ]
            if stickstoff:
                c1 = index
            elif exo_c:
                c4 = index
        if c1 is None or c4 is None:
            continue

        # C2' hängt am C1', C3' am C4' — beide im Ring.
        nachbarn = lambda i: {n.GetIdx() for n in mol.GetAtomWithIdx(i).GetNeighbors()}
        c2 = next(iter(nachbarn(c1) & im_ring - {o4}), None)
        c3 = next(iter(nachbarn(c4) & im_ring - {o4}), None)
        if c2 is None or c3 is None or c2 == c3:
            # Ein Ring, bei dem das nicht aufgeht, ist nicht der Zucker.
            continue

        return {"C1'": c1, "C2'": c2, "C3'": c3, "C4'": c4, "O4'": o4}
    return None


def _base_atoms(mol, sugar: dict[str, int]) -> list[int]:
    """Alles, was über die glykosidische Bindung am C1' hängt."""
    im_zucker = set(sugar.values())
    # Auch die Substituenten des Zuckers gehören nicht zur Base: C5', OH.
    anhang: set[int] = set()
    for index in im_zucker:
        for nachbar in mol.GetAtomWithIdx(index).GetNeighbors():
            if nachbar.GetIdx() in im_zucker:
                continue
            if index == sugar["C1'"] and nachbar.GetSymbol() == "N":
                continue  # das ist die Base
            anhang.add(nachbar.GetIdx())
    # Vom Zucker-Anhang aus weiterlaufen (C5' → O5' → P …).
    rand = list(anhang)
    while rand:
        aktuell = rand.pop()
        for nachbar in mol.GetAtomWithIdx(aktuell).GetNeighbors():
            index = nachbar.GetIdx()
            if index in im_zucker or index in anhang:
                continue
            anhang.add(index)
            rand.append(index)

    ausgeschlossen = im_zucker | anhang
    return [a.GetIdx() for a in mol.GetAtoms() if a.GetIdx() not in ausgeschlossen]


def _kabsch(beweglich, fest):
    """Die Drehung, die `beweglich` am besten auf `fest` legt.

    Beide sind (n, 3). Zurueck kommen Drehmatrix, beide Schwerpunkte und
    der RMSD nach dem Legen.
    """
    import numpy as np

    b = np.asarray(beweglich, dtype=float)
    f = np.asarray(fest, dtype=float)
    mitte_b, mitte_f = b.mean(axis=0), f.mean(axis=0)
    b0, f0 = b - mitte_b, f - mitte_f

    u, _, vt = np.linalg.svd(b0.T @ f0)
    vorzeichen = np.sign(np.linalg.det(vt.T @ u.T))
    korrektur = np.diag([1.0, 1.0, vorzeichen])
    drehung = vt.T @ korrektur @ u.T

    rmsd = float(np.sqrt((((b0 @ drehung.T) - f0) ** 2).sum() / len(b)))
    return drehung, mitte_b, mitte_f, rmsd


def graft(
    smiles: str, reference_atoms: dict[str, tuple[float, float, float]]
) -> BuiltResidue:
    """Die Base aus dem SMILES bauen und auf das Rückgrat der Referenz setzen.

    `reference_atoms` sind die Atome des Rests aus der Referenz, nach Namen.
    Gebraucht werden mindestens drei der fünf Zuckeratome.
    """
    try:
        from rdkit import RDLogger

        RDLogger.DisableLog("rdApp.*")
    except ImportError:
        return BuiltResidue(available=False, note="RDKit ist nicht installiert.")

    anker = [name for name in SUGAR_NAMES if name in reference_atoms]
    if len(anker) < MIN_ANCHORS:
        return BuiltResidue(
            available=False,
            anchors=anker,
            note=(
                f"In der Referenz stehen nur {len(anker)} der fünf Zuckeratome. "
                "Zum Ausrichten werden mindestens drei gebraucht."
            ),
        )

    mol, problem = _embed(smiles)
    if mol is None:
        return BuiltResidue(available=False, note=problem)

    zucker = _find_sugar(mol)
    if zucker is None:
        return BuiltResidue(
            available=False,
            note=(
                "In diesem SMILES steckt kein Furanosering. Erwartet wird das "
                "ganze Nukleosid — Zucker und Base —, nicht die Base allein."
            ),
        )

    konformation = mol.GetConformer()
    beweglich = [
        (
            konformation.GetAtomPosition(zucker[name]).x,
            konformation.GetAtomPosition(zucker[name]).y,
            konformation.GetAtomPosition(zucker[name]).z,
        )
        for name in anker
    ]
    fest = [reference_atoms[name] for name in anker]

    drehung, mitte_b, mitte_f, rmsd = _kabsch(beweglich, fest)

    import numpy as np
    from rdkit.Chem import rdMolDescriptors

    basis = _base_atoms(mol, zucker)
    if not basis:
        return BuiltResidue(
            available=False,
            note="An diesem Zucker hängt keine Base — da ist nichts zu bauen.",
        )

    zaehler: dict[str, int] = {}
    atome: list[tuple[str, str, float, float, float]] = []
    for index in basis:
        atom = mol.GetAtomWithIdx(index)
        element = atom.GetSymbol()
        zaehler[element] = zaehler.get(element, 0) + 1
        lage = konformation.GetAtomPosition(index)
        gedreht = (np.array([lage.x, lage.y, lage.z]) - mitte_b) @ drehung.T + mitte_f
        atome.append(
            (
                f"{element}{zaehler[element]}",
                element,
                float(gedreht[0]),
                float(gedreht[1]),
                float(gedreht[2]),
            )
        )

    hinweis = None
    if rmsd > 0.5:
        hinweis = (
            f"Der gebaute Zucker passt nur auf {rmsd:.2f} Å genau auf den der "
            "Referenz. Die Base steht dadurch ungenauer, als die Zahl der "
            "Stellen vermuten lässt."
        )

    return BuiltResidue(
        atoms=atome,
        rmsd=rmsd,
        anchors=anker,
        formula=rdMolDescriptors.CalcMolFormula(mol),
        note=hinweis,
    )
