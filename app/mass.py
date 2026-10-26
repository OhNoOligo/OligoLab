"""Die Excel-Rechnung, exakt reproduziert.

    Basis             = Σ Restmassen + Σ Massendifferenzen der Modifikationen

    fully_deprotected = Basis − 61.96
    plus_dmt          = fully_deprotected + 302.34
    plus_3_phosphate  = Basis
    protected_dmt_off = fully_deprotected + n_A·104.03 + n_G·70.05
                        + n_C·42.02 + 53.03·(L−1)
    protected_ce      = protected_dmt_off − 53.03·(L−1)

`L` ist die Zahl der Bausteine; Konjugate zaehlen nicht mit (PHASEN.md 1.1).
Die Schutzgruppenterme laufen ueber `base_parent`, damit ein 2'-OMe-A dieselbe
Benzoylgruppe mitbringt wie ein dA.

Die Konstanten stehen in `data/protecting_groups.yaml` und werden hier nicht
nachgerechnet oder "korrigiert" (CLAUDE.md, Regel 2). Die unabhaengige
Gegenrechnung aus der Summenformel steht in `app/mass_exact.py`.

Fehlt irgendwo eine Massendifferenz — etwa beim GalNAc-Konjugat, dessen Masse
am Linker haengt und im Excel nicht hinterlegt ist — dann ist das Ergebnis
`None` und `note` nennt den Eintrag beim Namen. Es wird nie eine 0 eingesetzt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import Oligo, Quantity, Reliability, worst
from app.registry import Registry, get_registry


@dataclass
class MassBreakdown:
    """Woraus die Basis besteht — damit jede Zahl nachvollziehbar bleibt."""

    residues: float = 0.0
    monomer_modifications: float = 0.0
    linkage_modifications: float = 0.0
    conjugates: float = 0.0
    length: int = 0
    n_a: int = 0
    n_c: int = 0
    n_g: int = 0
    protecting_base: float = 0.0
    protecting_cyanoethyl: float = 0.0
    missing: list[str] = field(default_factory=list)
    approximated: list[str] = field(default_factory=list)

    @property
    def basis(self) -> float:
        return (
            self.residues
            + self.monomer_modifications
            + self.linkage_modifications
            + self.conjugates
        )

    def as_dict(self) -> dict:
        return {
            "residues": round(self.residues, 2),
            "monomer_modifications": round(self.monomer_modifications, 2),
            "linkage_modifications": round(self.linkage_modifications, 2),
            "conjugates": round(self.conjugates, 2),
            "basis": round(self.basis, 2),
            "length": self.length,
            "n_A": self.n_a,
            "n_C": self.n_c,
            "n_G": self.n_g,
            "protecting_base": round(self.protecting_base, 2),
            "protecting_cyanoethyl": round(self.protecting_cyanoethyl, 2),
            "missing": self.missing,
            "approximated": self.approximated,
        }


@dataclass
class MassResult:
    """Die fuenf Massen der Excel-Rechnung, jede mit Kennzeichen."""

    fully_deprotected: Quantity
    plus_dmt: Quantity
    plus_3_phosphate: Quantity
    protected_dmt_off: Quantity
    protected_ce: Quantity
    breakdown: MassBreakdown

    # Reihenfolge wie in der Karte der Oberflaeche (PHASEN.md 1.8).
    ORDER = (
        ("fully_deprotected", "vollständig entschützt"),
        ("plus_dmt", "+ DMT"),
        ("plus_3_phosphate", "+ 3'-Phosphat"),
        ("protected_dmt_off", "geschützt, DMT off"),
        ("protected_ce", "geschützt, ohne CE"),
    )

    def as_dict(self) -> dict:
        return {
            "masses": [
                {"key": key, "label": label, **getattr(self, key).as_dict()}
                for key, label in self.ORDER
            ],
            "breakdown": self.breakdown.as_dict(),
        }


def compute_basis(
    oligo: Oligo, registry: Registry | None = None
) -> tuple[float | None, MassBreakdown, Reliability]:
    """Basis = Σ Restmassen + Σ Massendifferenzen.

    Sammelt gleichzeitig ein, was fehlt oder genaehert ist.
    """
    reg = registry or get_registry()
    bd = MassBreakdown(length=oligo.length)
    flags: list[Reliability] = []

    for m in oligo.monomers:
        if m.spec.mass_residue is None:
            bd.missing.append(
                f"Position {m.position} ({m.code}): keine Restmasse in monomers.yaml"
            )
            flags.append(Reliability.MISSING)
        else:
            bd.residues += m.spec.mass_residue
            flags.append(Reliability.PARAMETER)

        for mod in m.modifications:
            if mod.mass_diff is None:
                bd.missing.append(
                    f"Position {m.position}: Modifikation {mod.code} "
                    "ohne Massendifferenz"
                )
                flags.append(Reliability.MISSING)
            else:
                bd.monomer_modifications += mod.mass_diff
                flags.append(Reliability.PARAMETER)

    for link in oligo.linkages:
        if not link.is_modified:
            continue
        mod = link.modification
        if mod is None or mod.mass_diff is None:
            bd.missing.append(
                f"Bindung {link.position}-{link.position + 1}: "
                f"{link.kind} ohne Massendifferenz"
            )
            flags.append(Reliability.MISSING)
        else:
            bd.linkage_modifications += mod.mass_diff
            flags.append(Reliability.PARAMETER)

    for conj in oligo.conjugates:
        spec = conj.spec
        if spec.mass_diff is None:
            bd.missing.append(
                f"Konjugat {spec.code}: keine Masse hinterlegt"
                + (f" ({spec.quelle})" if spec.quelle else "")
            )
            flags.append(Reliability.MISSING)
        else:
            bd.conjugates += spec.mass_diff
            flags.append(Reliability.PARAMETER)

    # Schutzgruppen ueber das natuerliche Analogon.
    counts = oligo.base_counts()
    bd.n_a = counts.get("A", 0)
    bd.n_c = counts.get("C", 0)
    bd.n_g = counts.get("G", 0)

    for m in oligo.monomers:
        if m.modifications and m.base_parent:
            bd.approximated.append(
                f"Position {m.position} ({m.source or m.code}): Schutzgruppe "
                f"über natürliches Analogon {m.base_parent}"
            )
        if m.base_parent is None and m.spec.typ == "custom":
            bd.approximated.append(
                f"Position {m.position} ({m.code}): kein natürliches Analogon, "
                "trägt keine Basenschutzgruppe"
            )

    _, bz = reg.protecting_group_for_base("A")
    _, ac = reg.protecting_group_for_base("C")
    _, ibu = reg.protecting_group_for_base("G")
    bd.protecting_base = bd.n_a * bz + bd.n_g * ibu + bd.n_c * ac
    bd.protecting_cyanoethyl = reg.cyanoethyl_mass * max(oligo.length - 1, 0)

    if not oligo.monomers:
        # Ohne Bausteine gibt es keine Basis. Sonst kaeme hier die 0 heraus und
        # `fully_deprotected` waere -61,96 Da — eine Zahl, die nichts bedeutet.
        bd.missing.append("Keine Bausteine — es gibt nichts zu rechnen.")
        return None, bd, Reliability.MISSING

    reliability = worst(*flags) if flags else Reliability.MISSING
    basis = None if bd.missing else bd.basis
    return basis, bd, reliability


def compute(oligo: Oligo, registry: Registry | None = None) -> MassResult:
    """Die fuenf Massen der Excel-Rechnung."""
    reg = registry or get_registry()
    basis, bd, reliability = compute_basis(oligo, reg)

    offset = reg.phosphate_offset
    dmt = reg.dmt_mass

    note = None
    if bd.missing:
        note = "Nicht berechenbar — " + "; ".join(bd.missing) + "."

    def q(value: float | None, method: str) -> Quantity:
        return Quantity(value, "Da", reliability, method, note)

    if basis is None:
        return MassResult(
            fully_deprotected=q(None, "Basis − 61,96"),
            plus_dmt=q(None, "vollständig entschützt + 302,34"),
            plus_3_phosphate=q(None, "Basis"),
            protected_dmt_off=q(None, "entschützt + Schutzgruppen + CE·(L−1)"),
            protected_ce=q(None, "geschützt DMT off − CE·(L−1)"),
            breakdown=bd,
        )

    fully = basis - offset
    plus_dmt = fully + dmt
    protected_dmt_off = fully + bd.protecting_base + bd.protecting_cyanoethyl
    protected_ce = protected_dmt_off - bd.protecting_cyanoethyl

    return MassResult(
        fully_deprotected=q(fully, f"Basis − {offset:.2f}"),
        plus_dmt=q(plus_dmt, f"vollständig entschützt + {dmt:.2f}"),
        plus_3_phosphate=q(basis, "Basis = Σ Restmassen + Σ Modifikationen"),
        protected_dmt_off=q(
            protected_dmt_off,
            "entschützt + n_A·104,03 + n_G·70,05 + n_C·42,02 + 53,03·(L−1)",
        ),
        protected_ce=q(protected_ce, "geschützt, DMT off − 53,03·(L−1)"),
        breakdown=bd,
    )
