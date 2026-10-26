"""Synthesizer-Verbrauch.

Je Kupplung geht ein festes Volumen Amiditloesung durch die Saeule
(Voreinstellung 0,12 mL, in der Oberflaeche einstellbar). Daraus:

    Volumen = Anzahl Kupplungen · Volumen je Kupplung
    Masse   = Volumen · Konzentration · Amiditmasse

In Einheiten: mL · mol/L = mmol, und mmol · g/mol = mg. Die Tabelle rechnet
also direkt in mg, ohne Zwischenumrechnung.

Gezaehlt wird nach Synthi-Buchstabe, nicht nach natuerlichem Analogon: ein
2'-OMe-A kommt aus einer anderen Flasche als ein dA.

Die Zahl der Kupplungen je Baustein ist seine Anzahl im Strang — so wie im
Excel, einschliesslich des 3'-endstaendigen Bausteins.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.models import Oligo, Quantity, Reliability
from app.registry import Registry, get_registry

# Steht sichtbar neben der Tabelle (PHASEN.md 1.5).
RESERVE_HINT = "Immer mindestens 10 % aufschlagen."


@dataclass
class ConsumptionRow:
    code: str
    name: str
    couplings: int
    volume_ml: float
    conc_molar: float | None
    mass_mg: float | None
    mass_with_reserve_mg: float | None
    reliability: Reliability
    note: str | None = None

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "couplings": self.couplings,
            "volume_ml": round(self.volume_ml, 3),
            "conc_molar": self.conc_molar,
            "mass_mg": None if self.mass_mg is None else round(self.mass_mg, 1),
            "mass_with_reserve_mg": (
                None
                if self.mass_with_reserve_mg is None
                else round(self.mass_with_reserve_mg, 1)
            ),
            "reliability": self.reliability.value,
            "note": self.note,
        }


@dataclass
class ConsumptionTable:
    rows: list[ConsumptionRow]
    total_volume_ml: float
    total_mass_mg: float | None
    total_mass_with_reserve_mg: float | None
    coupling_volume_ml: float
    reserve_fraction: float
    syntheses: int
    hint: str = RESERVE_HINT

    def as_dict(self) -> dict:
        return {
            "rows": [r.as_dict() for r in self.rows],
            "total": {
                "volume_ml": round(self.total_volume_ml, 3),
                "mass_mg": (
                    None if self.total_mass_mg is None else round(self.total_mass_mg, 1)
                ),
                "mass_with_reserve_mg": (
                    None
                    if self.total_mass_with_reserve_mg is None
                    else round(self.total_mass_with_reserve_mg, 1)
                ),
            },
            "settings": {
                "coupling_volume_ml": self.coupling_volume_ml,
                "reserve_fraction": self.reserve_fraction,
                "syntheses": self.syntheses,
            },
            "hint": self.hint,
        }


def compute(
    oligo: Oligo,
    coupling_volume_ml: float | None = None,
    reserve_fraction: float | None = None,
    syntheses: int = 1,
    registry: Registry | None = None,
) -> ConsumptionTable:
    """Verbrauchstabelle fuer einen Strang.

    `syntheses` ist ein reiner Faktor: zwei Synthesen brauchen doppelt so viel.
    """
    reg = registry or get_registry()
    volume_per_coupling = (
        settings.coupling_volume_ml if coupling_volume_ml is None else coupling_volume_ml
    )
    reserve = settings.reserve_fraction if reserve_fraction is None else reserve_fraction
    if syntheses < 1:
        raise ValueError("Die Zahl der Synthesen muss mindestens 1 sein.")

    counts = oligo.code_counts()
    rows: list[ConsumptionRow] = []
    total_volume = 0.0
    total_mass: float | None = 0.0
    any_missing = False

    for code in sorted(counts):
        spec = reg.monomer(code)
        couplings = counts[code] * syntheses
        volume = couplings * volume_per_coupling
        total_volume += volume

        conc = spec.conc_molar if spec else None
        amidite = spec.mass_amidite if spec else None
        name = spec.name if spec else code

        if conc is None or amidite is None:
            any_missing = True
            rows.append(
                ConsumptionRow(
                    code=code,
                    name=name,
                    couplings=couplings,
                    volume_ml=volume,
                    conc_molar=conc,
                    mass_mg=None,
                    mass_with_reserve_mg=None,
                    reliability=Reliability.MISSING,
                    note=(
                        "Keine Amiditmasse oder Konzentration in monomers.yaml — "
                        "Masse nicht berechenbar."
                    ),
                )
            )
            continue

        mass_mg = volume * conc * amidite
        if total_mass is not None:
            total_mass += mass_mg
        rows.append(
            ConsumptionRow(
                code=code,
                name=name,
                couplings=couplings,
                volume_ml=volume,
                conc_molar=conc,
                mass_mg=mass_mg,
                mass_with_reserve_mg=mass_mg * (1 + reserve),
                reliability=Reliability.PARAMETER,
            )
        )

    if any_missing:
        total_mass = None

    return ConsumptionTable(
        rows=rows,
        total_volume_ml=total_volume,
        total_mass_mg=total_mass,
        total_mass_with_reserve_mg=(
            None if total_mass is None else total_mass * (1 + reserve)
        ),
        coupling_volume_ml=volume_per_coupling,
        reserve_fraction=reserve,
        syntheses=syntheses,
    )
