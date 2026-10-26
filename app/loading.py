"""Beladung fuer PAGE und LC-MS.

Einheiten durchgehend:

    n_stock      nmol   Stoffmenge im Vial
    v_stock      µL     Volumen im Vial
    n_loading    pmol   gewuenschte Stoffmenge auf dem Gel
    n_injection  pmol   gewuenschte Stoffmenge auf der Saeule

Die Stammkonzentration ist

    c = n_stock · 1000 / v_stock        [µM]

und weil 1 µM = 1 pmol/µL ist, liefert `pmol / µM` direkt Mikroliter. Daher
kommt der Faktor 1000 in der Formel.

PAGE (Formeln aus PHASEN.md 1.6):

    V(Oligo)  = n_loading / c · 2
    V(Wasser) = 10 − V(Oligo)
    dazu 10 µL 2× DNA-Puffer, zusammen 20 µL

LC-MS:

    V(Oligo)  = n_injection / c · (V_probe / V_injektion)
    V(Wasser) = V_probe − V(Oligo)

Bleiben im Vial weniger als 4 µL uebrig, wird gewarnt — dann lohnt es sich,
vorher zu verduennen, statt das Vial leerzuziehen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import Quantity, Reliability

# Voreinstellungen, in der Oberflaeche aenderbar.
PAGE_TOTAL_WATER_UL = 10.0      # Wasser + Oligo ergeben zusammen 10 µL
PAGE_BUFFER_UL = 10.0           # dazu 10 µL 2× DNA-Puffer
PAGE_FACTOR = 2.0               # Faktor aus der bestehenden Rechnung
MIN_REST_IN_VIAL_UL = 4.0       # darunter wird gewarnt


def stock_concentration_um(n_stock_nmol: float, v_stock_ul: float) -> Quantity:
    """c = n · 1000 / V, Ergebnis in µM (= pmol/µL)."""
    if v_stock_ul <= 0:
        raise ValueError("Das Stammvolumen muss groesser als 0 sein.")
    if n_stock_nmol < 0:
        raise ValueError("Die Stoffmenge im Vial darf nicht negativ sein.")
    return Quantity(
        n_stock_nmol * 1000.0 / v_stock_ul, "µM", Reliability.EXACT,
        "n(Stock) · 1000 / V(Stock)",
    )


@dataclass
class LoadingRecipe:
    """Ein Pipettierschema."""

    kind: str
    oligo_ul: Quantity
    water_ul: Quantity
    buffer_ul: Quantity | None
    total_ul: float
    stock_conc_um: Quantity
    rest_in_vial_ul: float | None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "oligo_ul": self.oligo_ul.as_dict(2),
            "water_ul": self.water_ul.as_dict(2),
            "buffer_ul": None if self.buffer_ul is None else self.buffer_ul.as_dict(2),
            "total_ul": round(self.total_ul, 2),
            "stock_conc_um": self.stock_conc_um.as_dict(2),
            "rest_in_vial_ul": (
                None if self.rest_in_vial_ul is None else round(self.rest_in_vial_ul, 2)
            ),
            "warnings": self.warnings,
        }


def _check_rest(
    v_stock_ul: float, used_ul: float, warnings: list[str]
) -> float:
    rest = v_stock_ul - used_ul
    if rest < 0:
        warnings.append(
            f"Es werden {used_ul:.2f} µL gebraucht, im Vial sind aber nur "
            f"{v_stock_ul:.2f} µL. So geht es nicht."
        )
    elif rest < MIN_REST_IN_VIAL_UL:
        warnings.append(
            f"Im Vial blieben nur {rest:.2f} µL übrig (Schwelle "
            f"{MIN_REST_IN_VIAL_UL:.0f} µL). Besser vorher verdünnen."
        )
    return rest


def page(
    n_loading_pmol: float,
    n_stock_nmol: float,
    v_stock_ul: float,
    water_total_ul: float = PAGE_TOTAL_WATER_UL,
    buffer_ul: float = PAGE_BUFFER_UL,
    factor: float = PAGE_FACTOR,
) -> LoadingRecipe:
    """Beladung fuer ein PAGE-Gel."""
    conc = stock_concentration_um(n_stock_nmol, v_stock_ul)
    if conc.value == 0:
        raise ValueError("Die Stammkonzentration ist 0 — Beladung nicht moeglich.")

    oligo_ul = n_loading_pmol / conc.value * factor
    water_ul = water_total_ul - oligo_ul
    warnings: list[str] = []

    if water_ul < 0:
        warnings.append(
            f"Das Oligo braucht schon {oligo_ul:.2f} µL, mehr als die "
            f"{water_total_ul:.0f} µL, die zur Verfügung stehen. "
            "Mehr Stammkonzentration oder weniger Beladung."
        )
    rest = _check_rest(v_stock_ul, oligo_ul, warnings)

    return LoadingRecipe(
        kind="PAGE",
        oligo_ul=Quantity(
            oligo_ul, "µL", Reliability.EXACT,
            f"n(Beladung) / c(Stock) · {factor:g}",
        ),
        water_ul=Quantity(
            water_ul, "µL", Reliability.EXACT,
            f"{water_total_ul:g} µL − V(Oligo)",
        ),
        buffer_ul=Quantity(
            buffer_ul, "µL", Reliability.EXACT, "2× DNA-Puffer, fester Zusatz",
        ),
        total_ul=water_total_ul + buffer_ul,
        stock_conc_um=conc,
        rest_in_vial_ul=rest,
        warnings=warnings,
    )


def lcms(
    n_injection_pmol: float,
    n_stock_nmol: float,
    v_stock_ul: float,
    v_sample_ul: float,
    v_injection_ul: float,
) -> LoadingRecipe:
    """Beladung fuer eine LC-MS-Probe."""
    if v_injection_ul <= 0:
        raise ValueError("Das Injektionsvolumen muss groesser als 0 sein.")
    if v_sample_ul <= 0:
        raise ValueError("Das Probenvolumen muss groesser als 0 sein.")

    conc = stock_concentration_um(n_stock_nmol, v_stock_ul)
    if conc.value == 0:
        raise ValueError("Die Stammkonzentration ist 0 — Beladung nicht moeglich.")

    oligo_ul = n_injection_pmol / conc.value * (v_sample_ul / v_injection_ul)
    water_ul = v_sample_ul - oligo_ul
    warnings: list[str] = []

    if water_ul < 0:
        warnings.append(
            f"Das Oligo braucht schon {oligo_ul:.2f} µL, mehr als die "
            f"{v_sample_ul:.2f} µL Probenvolumen."
        )
    if v_injection_ul > v_sample_ul:
        warnings.append(
            f"Das Injektionsvolumen ({v_injection_ul:.2f} µL) ist größer als das "
            f"Probenvolumen ({v_sample_ul:.2f} µL)."
        )
    rest = _check_rest(v_stock_ul, oligo_ul, warnings)

    return LoadingRecipe(
        kind="LC-MS",
        oligo_ul=Quantity(
            oligo_ul, "µL", Reliability.EXACT,
            "n(Injektion) / c(Stock) · (V(Probe) / V(Injektion))",
        ),
        water_ul=Quantity(
            water_ul, "µL", Reliability.EXACT, "V(Probe) − V(Oligo)",
        ),
        buffer_ul=None,
        total_ul=v_sample_ul,
        stock_conc_um=conc,
        rest_in_vial_ul=rest,
        warnings=warnings,
    )
