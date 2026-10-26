"""Gegenrechnung: Masse aus der Summenformel.

Zweck ist NICHT, die Excel-Rechnung in `app/mass.py` zu ersetzen, sondern sie
zu pruefen. Die Excel-Konstanten bleiben verbindlich (CLAUDE.md, Regel 2);
weicht diese Rechnung ab, wird die Differenz angezeigt — nicht die Konstante
geaendert.

Kettenaufbau. `formula_residue` ist Nukleosid-3'-monophosphat minus Wasser.
Eine Kette aus L solchen Resten ergibt:

    5'-OH, 3'-Phosphat   =  Σ Reste + H2O
    5'-OH, 3'-OH         =  Σ Reste + H2O − HPO3        (freie Saeure)

Nachgerechnet an TpT: 2 · C10H13N2O7P + H2O − HPO3 = 546,1365 Da, und das
stimmt mit Thymidin + Thymidin-3'-phosphat − H2O ueberein.

Je Phosphorothioat wird ein O gegen ein S getauscht.

Natriumsalz: die aciden Protonen der Phosphate gegen Natrium, also
freie Saeure − n·H + n·Na mit n = Zahl der Phosphate und Phosphorothioate.
Das ist das Salz, nicht ein Natrium-Addukt der Saeure — die Methode steht an
jeder Zahl dran.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from app.models import Oligo, Quantity, Reliability
from app.registry import Registry, get_registry

# Isotope: Masse in Da und Haeufigkeit. Quelle: IUPAC/NIST.
ISOTOPES: dict[str, list[tuple[float, float]]] = {
    "H":  [(1.00782503207, 0.999885), (2.0141017778, 0.000115)],
    "C":  [(12.0, 0.9893), (13.0033548378, 0.0107)],
    "N":  [(14.0030740048, 0.99632), (15.0001088982, 0.00368)],
    "O":  [(15.9949146196, 0.99757), (16.9991317, 0.00038), (17.9991596, 0.00205)],
    "F":  [(18.99840322, 1.0)],
    "Na": [(22.9897692809, 1.0)],
    "P":  [(30.97376163, 1.0)],
    "S":  [(31.97207100, 0.9493), (32.97145876, 0.0076),
           (33.96786690, 0.0429), (35.96708076, 0.0002)],
    "Cl": [(34.96885268, 0.7578), (36.96590259, 0.2422)],
    "Br": [(78.9183371, 0.5069), (80.9162906, 0.4931)],
    "I":  [(126.904473, 1.0)],
}

MASS_PROTON = 1.00794  # wie in PHASEN.md 1.4 vorgegeben

_FORMULA_TOKEN = re.compile(r"([A-Z][a-z]?)(\d*)")
_FORMULA_VALID = re.compile(r"^(?:[A-Z][a-z]?\d*)+$")

ElementCounts = dict[str, int]


# ------------------------------------------------------------ Summenformeln


def parse_formula(formula: str) -> ElementCounts:
    """`C10H12N5O5P` in ein Zaehlwerk zerlegen."""
    cleaned = formula.replace(" ", "")
    if not cleaned or not _FORMULA_VALID.match(cleaned):
        raise ValueError(f"Keine gueltige Summenformel: {formula!r}")
    counts: ElementCounts = {}
    for symbol, digits in _FORMULA_TOKEN.findall(cleaned):
        if symbol not in ISOTOPES:
            raise ValueError(f"Unbekanntes Element {symbol!r} in {formula!r}")
        counts[symbol] = counts.get(symbol, 0) + (int(digits) if digits else 1)
    return counts


def format_formula(counts: ElementCounts) -> str:
    """Hill-Schreibweise: C, dann H, dann alles weitere alphabetisch."""
    parts: list[str] = []
    for symbol in ("C", "H"):
        n = counts.get(symbol, 0)
        if n:
            parts.append(symbol + (str(n) if n != 1 else ""))
    for symbol in sorted(k for k in counts if k not in ("C", "H")):
        n = counts[symbol]
        if n:
            parts.append(symbol + (str(n) if n != 1 else ""))
    return "".join(parts)


def add_formula(a: ElementCounts, b: ElementCounts, factor: int = 1) -> ElementCounts:
    out = dict(a)
    for symbol, n in b.items():
        out[symbol] = out.get(symbol, 0) + n * factor
    return {k: v for k, v in out.items() if v}


def monoisotopic_mass(counts: ElementCounts) -> float:
    """Masse mit dem jeweils haeufigsten Isotop."""
    total = 0.0
    for symbol, n in counts.items():
        mass, _ = max(ISOTOPES[symbol], key=lambda iso: iso[1])
        total += mass * n
    return total


def average_mass(counts: ElementCounts) -> float:
    """Masse mit dem Haeufigkeitsmittel der Isotope."""
    total = 0.0
    for symbol, n in counts.items():
        mean = sum(mass * abundance for mass, abundance in ISOTOPES[symbol])
        weight = sum(abundance for _, abundance in ISOTOPES[symbol])
        total += (mean / weight) * n
    return total


# ------------------------------------------------------------ Isotopenmuster


def _convolve(
    a: dict[int, tuple[float, float]], b: dict[int, tuple[float, float]], floor: float
) -> dict[int, tuple[float, float]]:
    """Zwei Verteilungen falten.

    Schluessel ist die Zahl zusaetzlicher Neutronen, Wert
    (Intensitaet, Intensitaet·Masse) — so bleibt die genaue Peakmasse erhalten,
    obwohl nach Nominalmasse zusammengefasst wird.
    """
    out: dict[int, tuple[float, float]] = {}
    for shift_a, (int_a, wm_a) in a.items():
        if int_a < floor:
            continue
        for shift_b, (int_b, wm_b) in b.items():
            if int_b < floor:
                continue
            intensity = int_a * int_b
            if intensity < floor:
                continue
            shift = shift_a + shift_b
            # Masse des Produktpeaks = Mittelwert_a + Mittelwert_b
            mass = wm_a / int_a + wm_b / int_b
            prev_i, prev_wm = out.get(shift, (0.0, 0.0))
            out[shift] = (prev_i + intensity, prev_wm + intensity * mass)
    return out


def isotope_pattern(
    counts: ElementCounts, top: int = 5, floor: float = 1e-10
) -> list[dict]:
    """Die `top` haeufigsten Peaks, Intensitaet relativ zum groessten."""
    dist: dict[int, tuple[float, float]] = {0: (1.0, 0.0)}
    for symbol, n in counts.items():
        isotopes = ISOTOPES[symbol]
        lightest = min(mass for mass, _ in isotopes)
        single: dict[int, tuple[float, float]] = {}
        for mass, abundance in isotopes:
            if abundance <= 0:
                continue
            shift = int(round(mass - lightest))
            prev_i, prev_wm = single.get(shift, (0.0, 0.0))
            single[shift] = (prev_i + abundance, prev_wm + abundance * mass)
        # Potenzieren durch wiederholtes Quadrieren.
        remaining = n
        power = single
        while remaining:
            if remaining & 1:
                dist = _convolve(dist, power, floor)
            remaining >>= 1
            if remaining:
                power = _convolve(power, power, floor)

    if not dist:
        return []
    peaks = [
        {"mass": wm / intensity, "intensity": intensity}
        for intensity, wm in (dist[s] for s in dist)
        if intensity > 0
    ]
    peaks.sort(key=lambda p: p["intensity"], reverse=True)
    biggest = peaks[0]["intensity"]
    selected = peaks[:top]
    selected.sort(key=lambda p: p["mass"])
    return [
        {
            "mass": round(p["mass"], 4),
            "intensity_rel": round(p["intensity"] / biggest, 4),
        }
        for p in selected
    ]


# ------------------------------------------------- Formel des ganzen Oligos

H2O = {"H": 2, "O": 1}
HPO3 = {"H": 1, "P": 1, "O": 3}


def residue_formula(
    code: str, registry: Registry | None = None
) -> ElementCounts | None:
    """Restformel eines Bausteins.

    Erst `formula_residue`. Fehlt die, wird sie aus dem SMILES des freien
    Nukleosids abgeleitet: Nukleosid + HPO3 − H2O. Fehlt beides, `None`.
    """
    reg = registry or get_registry()
    spec = reg.monomer(code)
    if spec is None:
        return None
    if spec.formula_residue:
        return parse_formula(spec.formula_residue)
    if spec.smiles:
        try:
            from rdkit import Chem
            from rdkit.Chem.rdMolDescriptors import CalcMolFormula
        except ImportError:  # pragma: no cover - RDKit gehoert zu requirements
            return None
        mol = Chem.MolFromSmiles(spec.smiles)
        if mol is None:
            return None
        nucleoside = parse_formula(CalcMolFormula(mol).rstrip("+-"))
        return add_formula(add_formula(nucleoside, HPO3), H2O, factor=-1)
    return None


@dataclass
class ExactResult:
    formula: str | None
    counts: ElementCounts
    monoisotopic: Quantity
    average: Quantity
    monoisotopic_na: Quantity
    average_na: Quantity
    sodium_count: int
    isotopes: list[dict]
    missing_formula: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "formula": self.formula,
            "monoisotopic": self.monoisotopic.as_dict(4),
            "average": self.average.as_dict(2),
            "monoisotopic_na": self.monoisotopic_na.as_dict(4),
            "average_na": self.average_na.as_dict(2),
            "sodium_count": self.sodium_count,
            "isotopes": self.isotopes,
            "missing_formula": self.missing_formula,
        }


def compute(
    oligo: Oligo,
    form: str = "fully_deprotected",
    registry: Registry | None = None,
) -> ExactResult:
    """Summenformel und Massen des ganzen Oligos.

    `form`:
      `fully_deprotected` — 5'-OH, 3'-OH, freie Saeure (Vergleichsgroesse)
      `plus_3_phosphate`  — 5'-OH, 3'-Phosphat
    """
    reg = registry or get_registry()
    counts: ElementCounts = {}
    missing: list[str] = []

    for m in oligo.monomers:
        formula = residue_formula(m.spec.code, reg)
        if formula is None:
            missing.append(
                f"Position {m.position} ({m.code}): keine Summenformel und kein SMILES"
            )
            continue
        counts = add_formula(counts, formula)
        for mod in m.modifications:
            if mod.formula:
                counts = add_formula(counts, parse_formula(mod.formula))
            else:
                missing.append(
                    f"Position {m.position}: Modifikation {mod.code} "
                    "ohne Summenformel"
                )

    if oligo.monomers:
        counts = add_formula(counts, H2O)
        if form == "fully_deprotected":
            counts = add_formula(counts, HPO3, factor=-1)

    # Phosphorothioat: ein O gegen ein S.
    n_ps = oligo.phosphorothioate_count()
    if n_ps:
        if counts.get("O", 0) < n_ps:
            missing.append("Mehr Phosphorothioate als Sauerstoffatome — Formel unklar.")
        else:
            counts = add_formula(counts, {"O": n_ps}, factor=-1)
            counts = add_formula(counts, {"S": n_ps})

    for conj in oligo.conjugates:
        if conj.spec.formula:
            counts = add_formula(counts, parse_formula(conj.spec.formula))
        else:
            missing.append(
                f"Konjugat {conj.code}: keine Summenformel hinterlegt"
                + (f" ({conj.spec.quelle})" if conj.spec.quelle else "")
            )

    # Zahl der Phosphate und Phosphorothioate in dieser Form.
    n_linkages = max(oligo.length - 1, 0)
    n_phosphate = n_linkages + (1 if form == "plus_3_phosphate" else 0)

    if missing or not counts:
        note = "Unvollständig — " + "; ".join(missing) if missing else "Kein Baustein."
        unknown = Quantity(None, "Da", Reliability.MISSING, "Summenformel", note)
        return ExactResult(
            formula=format_formula(counts) if counts else None,
            counts=counts,
            monoisotopic=unknown,
            average=unknown,
            monoisotopic_na=unknown,
            average_na=unknown,
            sodium_count=n_phosphate,
            isotopes=[],
            missing_formula=missing,
        )

    label = {
        "fully_deprotected": "5'-OH / 3'-OH, freie Säure",
        "plus_3_phosphate": "5'-OH / 3'-Phosphat, freie Säure",
    }.get(form, form)

    salt = add_formula(
        add_formula(counts, {"H": n_phosphate}, factor=-1), {"Na": n_phosphate}
    )

    return ExactResult(
        formula=format_formula(counts),
        counts=counts,
        monoisotopic=Quantity(
            monoisotopic_mass(counts), "Da", Reliability.EXACT,
            f"Summenformel {format_formula(counts)} ({label}), häufigste Isotope",
        ),
        average=Quantity(
            average_mass(counts), "Da", Reliability.EXACT,
            f"Summenformel {format_formula(counts)} ({label}), Isotopenmittel",
        ),
        monoisotopic_na=Quantity(
            monoisotopic_mass(salt), "Da", Reliability.EXACT,
            f"Natriumsalz: freie Säure − {n_phosphate}·H + {n_phosphate}·Na",
        ),
        average_na=Quantity(
            average_mass(salt), "Da", Reliability.EXACT,
            f"Natriumsalz: freie Säure − {n_phosphate}·H + {n_phosphate}·Na",
        ),
        sodium_count=n_phosphate,
        isotopes=isotope_pattern(counts),
        missing_formula=missing,
    )


# --------------------------------------------------------- ESI-Ladungsleiter


def charge_ladder(
    mass: float | None,
    charge_min: int = 2,
    charge_max: int = 15,
) -> list[dict]:
    """Negative ESI-Ladungsleiter nach `(M − n·1,00794)/n`."""
    if mass is None:
        return []
    if charge_min < 1 or charge_max < charge_min:
        raise ValueError("Ladungsbereich muss bei mindestens 1 beginnen und steigen.")
    return [
        {"charge": n, "mz": round((mass - n * MASS_PROTON) / n, 3)}
        for n in range(charge_min, charge_max + 1)
    ]


# ------------------------------------------- Vergleich mit der Excel-Rechnung

# Unterhalb dieser Differenz gilt die Gegenrechnung als bestaetigt (PHASEN.md 1.4).
AGREEMENT_THRESHOLD_DA = 0.5


@dataclass
class Comparison:
    excel: float | None
    exact: float | None
    difference: float | None
    agrees: bool
    threshold: float
    message: str
    per_code: list[dict] = field(default_factory=list)
    missing_formula: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "excel": None if self.excel is None else round(self.excel, 2),
            "exact": None if self.exact is None else round(self.exact, 2),
            "difference": (
                None if self.difference is None else round(self.difference, 2)
            ),
            "agrees": self.agrees,
            "threshold": self.threshold,
            "message": self.message,
            "per_code": self.per_code,
            "missing_formula": self.missing_formula,
        }


def compare(oligo: Oligo, registry: Registry | None = None) -> Comparison:
    """Excel-Rechnung gegen Summenformel, mit Aufschluesselung je Baustein.

    Die Aufschluesselung ist der eigentliche Nutzen: eine Gesamtdifferenz sagt
    nur, DASS etwas abweicht. `per_code` zeigt, WO — Restmasse aus dem Excel
    gegen die aus der Summenformel, je Synthi-Buchstabe und mal Anzahl.
    """
    from app import mass as excel_mass  # lokal, um Ringimport zu vermeiden

    reg = registry or get_registry()
    excel = excel_mass.compute(oligo, reg).fully_deprotected.value
    exact_result = compute(oligo, form="fully_deprotected", registry=reg)
    exact = exact_result.average.value

    per_code: list[dict] = []
    for code, count in sorted(oligo.code_counts().items()):
        spec = reg.monomer(code)
        formula = residue_formula(code, reg)
        row = {
            "code": code,
            "count": count,
            "excel": spec.mass_residue if spec else None,
            "formula": format_formula(formula) if formula else None,
            "average": round(average_mass(formula), 4) if formula else None,
            "monoisotopic": (
                round(monoisotopic_mass(formula), 4) if formula else None
            ),
        }
        if row["excel"] is not None and row["average"] is not None:
            delta = row["excel"] - row["average"]
            row["delta"] = round(delta, 4)
            row["delta_total"] = round(delta * count, 3)
            # Auch gegen die monoisotopische Masse, weil das Excel die
            # Konventionen mischt: fuer manche Bausteine liegt der Wert dicht
            # am Isotopenmittel, fuer andere dicht an der monoisotopischen
            # Masse. Beide Spalten machen das auf einen Blick sichtbar.
            row["delta_mono"] = round(row["excel"] - row["monoisotopic"], 4)
        else:
            row["delta"] = None
            row["delta_total"] = None
            row["delta_mono"] = None
        per_code.append(row)

    if excel is None or exact is None:
        missing = exact_result.missing_formula
        hint = (
            " Ohne Summenformel: " + "; ".join(missing) + "."
            if missing
            else ""
        )
        return Comparison(
            excel=excel,
            exact=exact,
            difference=None,
            agrees=False,
            threshold=AGREEMENT_THRESHOLD_DA,
            message="Vergleich nicht möglich." + hint,
            per_code=per_code,
            missing_formula=missing,
        )

    difference = exact - excel
    agrees = abs(difference) < AGREEMENT_THRESHOLD_DA
    if agrees:
        message = (
            f"Excel-Rechnung und Summenformel stimmen überein "
            f"(Differenz {difference:+.2f} Da)."
        )
    else:
        worst_rows = sorted(
            (r for r in per_code if r.get("delta_total") is not None),
            key=lambda r: abs(r["delta_total"]),
            reverse=True,
        )[:3]
        drivers = ", ".join(
            f"{r['code']} ({r['delta']:+.2f} Da × {r['count']} = "
            f"{r['delta_total']:+.2f} Da)"
            for r in worst_rows
        )
        message = (
            f"Differenz {difference:+.2f} Da — über der Schwelle von "
            f"{AGREEMENT_THRESHOLD_DA} Da. Größte Beiträge: {drivers}."
        )
        if exact_result.missing_formula:
            message += (
                " Ohne Summenformel: "
                + "; ".join(exact_result.missing_formula)
                + "."
            )

    return Comparison(
        excel=excel,
        exact=exact,
        difference=difference,
        agrees=agrees,
        threshold=AGREEMENT_THRESHOLD_DA,
        message=message,
        per_code=per_code,
        missing_formula=exact_result.missing_formula,
    )
