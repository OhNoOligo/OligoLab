"""Extinktionskoeffizient bei 260 nm und die Umrechnungen daraus.

Nearest-Neighbor-Modell:

    eps260 = Σ(i=1..N-1) eps(d_i d_i+1) − Σ(i=2..N-1) eps(d_i)

Die Nachbarpaare tragen, die inneren Einzelbausteine werden einmal
abgezogen, weil sie in zwei Paaren stecken.

Modifizierte Bausteine: hat der Baustein ein eigenes `eps260`, wird das
genommen und als `Parameter vorhanden` gekennzeichnet. Sonst laeuft er ueber
`base_parent` — und dann ist das Ergebnis `genähert über natürliches Analogon`
(CLAUDE.md, Regel 3). Fehlt beides, wird nicht geraten.

Die Tabellen stehen in `data/extinction.yaml` und nicht im Excel; sie sind
deshalb Parameter dieses Programms, nie `exakt`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import Oligo, Quantity, Reliability, worst
from app.registry import Registry, get_registry

# Welcher Satz Nachbartabellen gilt? Entscheidet die Mehrheit der Bausteine.
RNA_CODES = {"O", "I", "Z", "U"}


@dataclass
class ExtinctionResult:
    eps260: Quantity
    table: str
    per_position: list[dict] = field(default_factory=list)
    approximated: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "eps260": self.eps260.as_dict(0),
            "table": self.table,
            "per_position": self.per_position,
            "approximated": self.approximated,
            "missing": self.missing,
        }


def _letters(oligo: Oligo, registry: Registry) -> tuple[list[str | None], list[str], list[str], list[str]]:
    """Je Position den Buchstaben fuer die Nachbartabelle.

    Gibt zusaetzlich zurueck, welche Positionen genaehert und welche gar nicht
    aufloesbar sind.
    """
    letters: list[str | None] = []
    approximated: list[str] = []
    missing: list[str] = []
    own_eps: list[str] = []

    for m in oligo.monomers:
        code = m.spec.code
        if code in RNA_CODES and not m.modifications:
            letters.append({"O": "A", "I": "C", "Z": "G", "U": "U"}[code])
            continue
        if code in ("A", "C", "G", "T") and not m.modifications:
            letters.append(code)
            continue
        # Modifiziert oder eigener Baustein.
        #
        # Ein eigenes eps260 zaehlt nur, wenn es zu DIESEM Baustein gehoert:
        # bei einem modifizierten Baustein also an der Modifikation. Das
        # eps260 der Basisspezies ist das des unmodifizierten Analogons —
        # `[LNA-T]` ueber das eps260 von T zu rechnen ist eine Naeherung und
        # wird auch so gekennzeichnet (CLAUDE.md, Regel 3).
        eps = None
        if m.modifications:
            for mod in m.modifications:
                if mod.eps260 is not None:
                    eps = mod.eps260
        else:
            eps = m.spec.eps260
        parent = m.base_parent
        if parent:
            letters.append(parent)
            if eps is None:
                approximated.append(
                    f"Position {m.position} ({m.source or code}): eps260 über "
                    f"natürliches Analogon {parent}"
                )
            else:
                own_eps.append(f"Position {m.position}: eigenes eps260 {eps:.0f}")
        else:
            letters.append(None)
            missing.append(
                f"Position {m.position} ({code}): kein eps260 und kein "
                "natürliches Analogon — nicht berechenbar"
            )
    return letters, approximated, missing, own_eps


def compute(oligo: Oligo, registry: Registry | None = None) -> ExtinctionResult:
    """eps260 des ganzen Oligos nach dem Nearest-Neighbor-Modell."""
    reg = registry or get_registry()
    tables = reg.extinction or {}

    rna_share = sum(1 for m in oligo.monomers if m.spec.typ == "rna")
    table_name = "rna" if rna_share * 2 > oligo.length else "dna"
    table = tables.get(table_name, {})
    dimers = table.get("dimers", {})
    monomers = table.get("monomers", {})

    letters, approximated, missing, own_eps = _letters(oligo, reg)

    if oligo.length == 0:
        return ExtinctionResult(
            eps260=Quantity(
                None, "L·mol⁻¹·cm⁻¹", Reliability.MISSING,
                "Nearest-Neighbor", "Keine Bausteine."
            ),
            table=table_name,
        )

    if oligo.length == 1:
        code = letters[0]
        value = monomers.get(code) if code else None
        return ExtinctionResult(
            eps260=Quantity(
                value, "L·mol⁻¹·cm⁻¹",
                Reliability.PARAMETER if value else Reliability.MISSING,
                f"Einzelbaustein, Tabelle {table_name.upper()}",
                None if value else "Baustein nicht in der Tabelle.",
            ),
            table=table_name,
            approximated=approximated,
            missing=missing,
        )

    if missing:
        return ExtinctionResult(
            eps260=Quantity(
                None, "L·mol⁻¹·cm⁻¹", Reliability.MISSING,
                f"Nearest-Neighbor, Tabelle {table_name.upper()}",
                "Nicht berechenbar — " + "; ".join(missing) + ".",
            ),
            table=table_name,
            approximated=approximated,
            missing=missing,
        )

    total = 0.0
    per_position: list[dict] = []
    unknown_pairs: list[str] = []

    for i in range(oligo.length - 1):
        pair = f"{letters[i]}{letters[i + 1]}"
        value = dimers.get(pair)
        if value is None:
            unknown_pairs.append(f"Position {i + 1}-{i + 2}: Paar {pair} fehlt")
            continue
        total += value
        per_position.append({"position": i + 1, "pair": pair, "eps260": value})

    for i in range(1, oligo.length - 1):
        value = monomers.get(letters[i])
        if value is None:
            unknown_pairs.append(f"Position {i + 1}: Baustein {letters[i]} fehlt")
            continue
        total -= value

    if unknown_pairs:
        return ExtinctionResult(
            eps260=Quantity(
                None, "L·mol⁻¹·cm⁻¹", Reliability.MISSING,
                f"Nearest-Neighbor, Tabelle {table_name.upper()}",
                "Nicht berechenbar — " + "; ".join(unknown_pairs) + ".",
            ),
            table=table_name,
            per_position=per_position,
            approximated=approximated,
            missing=unknown_pairs,
        )

    reliability = Reliability.APPROX if approximated else Reliability.PARAMETER
    note = None
    if approximated:
        note = "Genähert: " + "; ".join(approximated) + "."
    if own_eps:
        extra = "Eigenes eps260 verwendet: " + "; ".join(own_eps) + "."
        note = f"{note} {extra}" if note else extra

    return ExtinctionResult(
        eps260=Quantity(
            total, "L·mol⁻¹·cm⁻¹", reliability,
            f"Nearest-Neighbor, Tabelle {table_name.upper()}", note,
        ),
        table=table_name,
        per_position=per_position,
        approximated=approximated,
        missing=[],
    )


# ----------------------------------------------------------- Umrechnungen


def absorbance_to_concentration(
    a260: float, eps260: float, path_cm: float = 1.0
) -> Quantity:
    """Lambert-Beer: c = A / (eps · l). Ergebnis in mol/L."""
    if eps260 <= 0:
        raise ValueError("eps260 muss groesser als 0 sein.")
    if path_cm <= 0:
        raise ValueError("Die Schichtdicke muss groesser als 0 sein.")
    return Quantity(
        a260 / (eps260 * path_cm), "mol/L", Reliability.EXACT,
        f"Lambert-Beer: A₂₆₀ / (ε₂₆₀ · {path_cm:g} cm)",
    )


def concentration_to_absorbance(
    conc_molar: float, eps260: float, path_cm: float = 1.0
) -> Quantity:
    """Lambert-Beer rueckwaerts: A = eps · c · l."""
    return Quantity(
        eps260 * conc_molar * path_cm, "", Reliability.EXACT,
        f"Lambert-Beer: ε₂₆₀ · c · {path_cm:g} cm",
    )


# 1 OD260 = die Stoffmenge, die in 1 mL bei 1 cm Schichtdicke A260 = 1 ergibt.
#   c = 1/eps mol/L, n = c · 1 mL = 1e-3/eps mol = 1e6/eps nmol
_OD_TO_NMOL_FACTOR = 1e6


def nmol_per_od(eps260: float) -> float:
    if eps260 <= 0:
        raise ValueError("eps260 muss groesser als 0 sein.")
    return _OD_TO_NMOL_FACTOR / eps260


@dataclass
class OdConversion:
    od: Quantity
    nmol: Quantity
    microgram: Quantity
    solved_for: str
    warning: str | None = None

    def as_dict(self) -> dict:
        return {
            "od": self.od.as_dict(3),
            "nmol": self.nmol.as_dict(2),
            "microgram": self.microgram.as_dict(2),
            "solved_for": self.solved_for,
            "warning": self.warning,
        }


def convert_od(
    eps260: float,
    molar_mass: float,
    od: float | None = None,
    nmol: float | None = None,
    microgram: float | None = None,
) -> OdConversion:
    """OD ↔ nmol ↔ µg.

    Zwei der drei Felder eingeben, das dritte kommt heraus (PHASEN.md 1.7).
    Sind alle drei gesetzt, wird aus dem ersten gerechnet und eine
    Unstimmigkeit ausdruecklich gemeldet statt stillschweigend uebergangen.
    """
    if eps260 <= 0:
        raise ValueError("eps260 muss groesser als 0 sein.")
    if molar_mass <= 0:
        raise ValueError("Die molare Masse muss groesser als 0 sein.")

    factor_nmol = nmol_per_od(eps260)          # nmol je OD
    factor_ug = molar_mass / 1000.0            # µg je nmol

    given = [k for k, v in (("od", od), ("nmol", nmol), ("microgram", microgram))
             if v is not None]
    if not given:
        raise ValueError("Mindestens ein Feld muss gesetzt sein.")

    source = given[0]
    if source == "od":
        od_v = float(od)                        # type: ignore[arg-type]
        nmol_v = od_v * factor_nmol
    elif source == "nmol":
        nmol_v = float(nmol)                    # type: ignore[arg-type]
        od_v = nmol_v / factor_nmol
    else:
        nmol_v = float(microgram) / factor_ug   # type: ignore[arg-type]
        od_v = nmol_v / factor_nmol
    ug_v = nmol_v * factor_ug

    warning = None
    if len(given) > 1:
        computed = {"od": od_v, "nmol": nmol_v, "microgram": ug_v}
        supplied = {"od": od, "nmol": nmol, "microgram": microgram}
        clashes = [
            f"{key}: eingegeben {supplied[key]:.3f}, "
            f"aus {source} berechnet {computed[key]:.3f}"
            for key in given[1:]
            if supplied[key] is not None
            and abs(supplied[key] - computed[key]) > 0.01 * max(
                abs(computed[key]), 1e-9
            )
        ]
        if clashes:
            warning = (
                f"Mehr als ein Feld gesetzt; gerechnet wurde aus `{source}`. "
                "Unstimmig — " + "; ".join(clashes) + "."
            )

    method_od = f"OD ↔ nmol über 10⁶/ε₂₆₀ = {factor_nmol:.3f} nmol je OD"
    method_ug = f"nmol ↔ µg über M/1000 = {factor_ug:.3f} µg je nmol"
    return OdConversion(
        od=Quantity(od_v, "OD₂₆₀", Reliability.EXACT, method_od, warning),
        nmol=Quantity(nmol_v, "nmol", Reliability.EXACT, method_od, warning),
        microgram=Quantity(ug_v, "µg", Reliability.EXACT, method_ug, warning),
        solved_for=",".join(k for k in ("od", "nmol", "microgram") if k not in given),
        warning=warning,
    )
