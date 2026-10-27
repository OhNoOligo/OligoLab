"""DNAzym-Kandidaten bauen und bewerten (PHASEN.md 5.3).

Orientierung — daran haengt alles Weitere, darum von Hand durchgespielt:

    Ziel    5'- A A A A A G | U C C C C C -3'
    DNAzym  3'- T T T T T C  [KERN]  A G G G G G -5'

Das DNAzym bindet antiparallel. Sein **3'-Arm** paart also mit dem Stueck
STROMAUF der Spaltstelle, sein **5'-Arm** mit dem Stueck STROMAB. In der
Leserichtung 5' nach 3' heisst das:

    DNAzym = revcomp(stromab) + Kern + revcomp(stromauf)

Die Bewertung folgt der Tabelle aus PHASEN.md 5.3. Jedes Kriterium wird auf
0 bis 1 gebracht und gewichtet; die Gewichte und Schwellen sind einstellbar.

**Die Punktzahl ist eine Rangfolge, keine Vorhersage der katalytischen Rate.**
Das beste veroeffentlichte Modell erreicht 63 bis 73 Prozent Trefferquote auf
38 DNAzymen. Dieser Satz steht als `DISCLAIMER` bereit und gehoert in die
Oberflaeche, nicht nur in diesen Kommentar.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from app import fold, melting
from app.dnazyme import CoreSpec, load_cores
from app.fold_target import Accessibility
from app.models import Oligo, Quantity, Reliability
from app.notation import parse
from app.registry import Registry, get_registry
from app.scan import CleavageSite, ScanResult

DISCLAIMER = (
    "Die Punktzahl ist eine Rangfolge, keine Vorhersage der katalytischen "
    "Rate. Das beste veröffentlichte Modell erreicht 63 bis 73 Prozent "
    "Trefferquote auf 38 DNAzymen. Sie sagt, welche Kandidaten einen Versuch "
    "wert sind — nicht, welcher der beste sein wird."
)

COMPLEMENT = str.maketrans("ACGUT", "UGCAA")


def reverse_complement(rna: str) -> str:
    """Komplement als DNA, 5' nach 3' gelesen."""
    return rna.upper().translate(COMPLEMENT)[::-1].replace("U", "T")


@dataclass
class DesignSettings:
    """Einstellungen und Schwellen (PHASEN.md 5.3 und 5.6)."""

    arm5_length: int = 9
    arm3_length: int = 9
    core_id: str | None = None

    #: Richtwerte aus der Tabelle in PHASEN.md.
    arm_dg_target: float = -20.0
    max_imbalance: float = 4.0
    self_fold_limit: float = -2.0

    #: Gewichte der sechs Kriterien. Werden auf die Summe 1 normiert.
    weight_junction: float = 0.30
    weight_arm_dg: float = 0.25
    weight_balance: float = 0.15
    weight_self_fold: float = 0.15
    weight_accessibility: float = 0.15

    include_poor_junctions: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "arm5_length": self.arm5_length,
            "arm3_length": self.arm3_length,
            "core_id": self.core_id,
            "arm_dg_target": self.arm_dg_target,
            "max_imbalance": self.max_imbalance,
            "self_fold_limit": self.self_fold_limit,
            "weights": {
                "junction": self.weight_junction,
                "arm_dg": self.weight_arm_dg,
                "balance": self.weight_balance,
                "self_fold": self.weight_self_fold,
                "accessibility": self.weight_accessibility,
            },
            "include_poor_junctions": self.include_poor_junctions,
        }


@dataclass
class Criterion:
    """Ein Kriterium: Rohwert, auf 0..1 gebrachter Wert, Gewicht."""

    key: str
    label: str
    raw: float | None
    score: float | None
    weight: float
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "raw": None if self.raw is None else round(self.raw, 3),
            "score": None if self.score is None else round(self.score, 3),
            "weight": round(self.weight, 3),
            "note": self.note,
        }


@dataclass
class Candidate:
    """Ein fertiger DNAzym-Entwurf fuer eine Spaltstelle."""

    site: CleavageSite
    sequence: str
    arm5: str
    arm3: str
    core: str
    core_id: str
    #: Die Stuecke des Ziels, an die die Arme binden.
    target_upstream: str
    target_downstream: str

    tm5: melting.TmResult | None = None
    tm3: melting.TmResult | None = None
    self_fold: fold.FoldResult | None = None

    criteria: list[Criterion] = field(default_factory=list)
    score: float = 0.0
    excluded: bool = False
    exclusion_reason: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def arm_dg_sum(self) -> float | None:
        if not (self.tm5 and self.tm3 and self.tm5.dg and self.tm3.dg):
            return None
        if self.tm5.dg.value is None or self.tm3.dg.value is None:
            return None
        return self.tm5.dg.value + self.tm3.dg.value

    @property
    def imbalance(self) -> float | None:
        if not (self.tm5 and self.tm3 and self.tm5.dg and self.tm3.dg):
            return None
        if self.tm5.dg.value is None or self.tm3.dg.value is None:
            return None
        return abs(self.tm5.dg.value - self.tm3.dg.value)

    @property
    def binds(self) -> bool:
        """Bilden die Arme bei den gewaehlten Bedingungen ueberhaupt ein Duplex?

        Ein positives ΔG heisst: der Duplex ist bei dieser Temperatur nicht
        stabil. Dann ist es kein Kandidat, sondern eine Sequenz.
        """
        summe = self.arm_dg_sum
        return summe is None or summe < 0.0

    @property
    def rating(self) -> str:
        """Die Ampel je Zeile (PHASEN.md 5.6).

        Die Punktzahl folgt den Gewichten aus den Einstellungen — die Ampel
        nicht blind. Binden die Arme gar nicht, kommt kein Gruen zustande,
        auch wenn die uebrigen fuenf Kriterien die Punktzahl hochtragen:
        Binden ist die Voraussetzung fuer alles andere, nicht eines von
        sechs gleichrangigen Kriterien.
        """
        if self.excluded:
            return "bad"
        if not self.binds:
            return "warn"
        if self.score >= 0.7:
            return "good"
        if self.score >= 0.45:
            return "warn"
        return "bad"

    def as_dict(self) -> dict[str, Any]:
        return {
            "site": self.site.as_dict(),
            "sequence": self.sequence,
            "arm5": self.arm5,
            "arm3": self.arm3,
            "core": self.core,
            "core_id": self.core_id,
            "target_upstream": self.target_upstream,
            "target_downstream": self.target_downstream,
            "length": len(self.sequence),
            "tm5": self.tm5.as_dict() if self.tm5 else None,
            "tm3": self.tm3.as_dict() if self.tm3 else None,
            "arm_dg_sum": (
                None if self.arm_dg_sum is None else round(self.arm_dg_sum, 2)
            ),
            "imbalance": None if self.imbalance is None else round(self.imbalance, 2),
            "self_fold_mfe": (
                self.self_fold.mfe.rounded(2)
                if self.self_fold and self.self_fold.mfe
                else None
            ),
            "self_fold_structure": self.self_fold.structure if self.self_fold else None,
            "criteria": [c.as_dict() for c in self.criteria],
            "score": round(self.score, 4),
            "rating": self.rating,
            "binds": self.binds,
            "excluded": self.excluded,
            "exclusion_reason": self.exclusion_reason,
            "warnings": self.warnings,
        }


# --------------------------------------------------------------- bauen


def build(
    target_sequence: str,
    site: CleavageSite,
    settings: DesignSettings,
    core: CoreSpec,
) -> Candidate | None:
    """Einen Kandidaten fuer eine Spaltstelle bauen.

    Gibt None zurueck, wenn an der Stelle nicht genug Ziel fuer beide Arme
    uebrig ist — lieber keinen Kandidaten als einen mit gestutztem Arm, der
    in der Rangliste mitspielt, als waere er vollwertig.
    """
    position = site.position
    laenge = len(target_sequence)

    stromauf_von = position - settings.arm3_length + 1
    stromab_bis = position + settings.arm5_length

    if stromauf_von < 1 or stromab_bis > laenge:
        return None

    stromauf = target_sequence[stromauf_von - 1 : position]
    stromab = target_sequence[position : stromab_bis]

    arm5 = reverse_complement(stromab)
    arm3 = reverse_complement(stromauf)
    sequenz = f"{arm5}{core.sequence}{arm3}"

    return Candidate(
        site=site,
        sequence=sequenz,
        arm5=arm5,
        arm3=arm3,
        core=core.sequence,
        core_id=core.id,
        target_upstream=stromauf,
        target_downstream=stromab,
    )


# --------------------------------------------------------------- bewerten


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def bedingungen_text(settings: DesignSettings) -> str:
    """Kurzer Verweis darauf, worauf sich ein ΔG bezieht."""
    del settings
    return "den eingestellten Bedingungen"


def _junction_score(quality: str) -> float:
    return {"gut": 1.0, "mäßig": 0.5, "schlecht": 0.0}.get(quality, 0.0)


def _arm_dg_score(summe: float | None, ziel: float) -> float | None:
    """Unter dem Richtwert voll, darueber linear abfallend.

    Noch negativer als der Richtwert bringt nichts mehr: ein Arm, der zu fest
    bindet, loest sich nicht mehr vom Produkt. Die Strafe dafuer steht beim
    Mehrfachumsatz, nicht hier.
    """
    if summe is None:
        return None
    if summe <= ziel:
        return 1.0
    # Zehn kcal/mol ueber dem Richtwert gilt als unbrauchbar.
    return _clamp(1.0 - (summe - ziel) / 10.0)


def _balance_score(unterschied: float | None, hoechstens: float) -> float | None:
    if unterschied is None:
        return None
    if hoechstens <= 0:
        return 1.0
    return _clamp(1.0 - unterschied / hoechstens)


def _self_fold_score(mfe: float | None, grenze: float) -> float | None:
    """Ueber der Grenze voll, darunter abfallend."""
    if mfe is None:
        return None
    if mfe >= grenze:
        return 1.0
    return _clamp(1.0 - (grenze - mfe) / 6.0)


def score(
    candidate: Candidate,
    settings: DesignSettings,
    registry: Registry | None = None,
) -> Candidate:
    """Die sechs Kriterien aus PHASEN.md 5.3, gewichtet."""
    reg = registry or get_registry()

    kriterien: list[Criterion] = []

    kriterien.append(
        Criterion(
            "junction", "Spaltstellentyp",
            raw=None, score=_junction_score(candidate.site.quality),
            weight=settings.weight_junction,
            note=f"{candidate.site.junction} gilt als {candidate.site.quality}",
        )
    )

    summe = candidate.arm_dg_sum
    kriterien.append(
        Criterion(
            "arm_dg", "ΔG beider Arme",
            raw=summe, score=_arm_dg_score(summe, settings.arm_dg_target),
            weight=settings.weight_arm_dg,
            note=f"Richtwert unter {settings.arm_dg_target:g} kcal/mol",
        )
    )

    unterschied = candidate.imbalance
    kriterien.append(
        Criterion(
            "balance", "Armbalance",
            raw=unterschied,
            score=_balance_score(unterschied, settings.max_imbalance),
            weight=settings.weight_balance,
            note="Betrag der ΔG-Differenz, möglichst klein",
        )
    )

    eigen = (
        candidate.self_fold.mfe.value
        if candidate.self_fold and candidate.self_fold.mfe
        else None
    )
    kriterien.append(
        Criterion(
            "self_fold", "Eigenfaltung",
            raw=eigen, score=_self_fold_score(eigen, settings.self_fold_limit),
            weight=settings.weight_self_fold,
            note=f"nicht stabiler als {settings.self_fold_limit:g} kcal/mol",
        )
    )

    zugang = candidate.site.accessibility
    kriterien.append(
        Criterion(
            "accessibility", "Zugänglichkeit",
            raw=zugang, score=None if zugang is None else _clamp(zugang),
            weight=settings.weight_accessibility,
            note="aus dem Profil der Ziel-RNA",
        )
    )

    # Modifikation im Kern ist ein Ausschlusskriterium, keine Abwertung.
    # Hier entsteht der Kandidat frisch aus `cores.yaml`, also kann es nur
    # auftreten, wenn jemand den Kern in der Monomerdatei geaendert hat.
    ausgeschlossen = False
    grund: str | None = None
    try:
        kern_oligo = parse(candidate.core, reg)
        untauglich = [
            m for m in kern_oligo.monomers if m.core_tested != "ja"
        ]
        if untauglich:
            ausgeschlossen = True
            stellen = ", ".join(str(m.position) for m in untauglich)
            grund = (
                f"Im katalytischen Kern stehen Bausteine, die dort nicht "
                f"erprobt sind (Position {stellen}). Das ist ein "
                "Ausschlusskriterium, keine Abwertung."
            )
    except Exception:  # pragma: no cover - der Kern kommt aus unserer Datei
        pass

    # Gewichtet mitteln, aber nur ueber die Kriterien, die einen Wert haben.
    # Ein fehlendes Kriterium darf die Punktzahl weder heben noch senken.
    bewertbar = [k for k in kriterien if k.score is not None]
    gewicht_summe = sum(k.weight for k in bewertbar)
    punktzahl = (
        0.0
        if not bewertbar or gewicht_summe <= 0
        else sum(k.score * k.weight for k in bewertbar) / gewicht_summe
    )

    warnungen: list[str] = []

    if summe is not None and summe >= 0.0:
        warnungen.append(
            f"Die Arme binden bei {bedingungen_text(settings)} nicht: ΔG ist "
            f"mit {summe:+.1f} kcal/mol positiv, der Duplex ist also nicht "
            "stabil. Längere Arme oder mildere Bedingungen."
        )

    fehlend = [k.label for k in kriterien if k.score is None]
    if fehlend:
        warnungen.append(
            "Ohne Wert geblieben und darum nicht in die Punktzahl eingegangen: "
            + ", ".join(fehlend)
            + "."
        )

    return replace(
        candidate,
        criteria=kriterien,
        score=0.0 if ausgeschlossen else punktzahl,
        excluded=ausgeschlossen,
        exclusion_reason=grund,
        warnings=warnungen,
    )


# ------------------------------------------------------- Mehrfachumsatz


#: Ab dieser Abweichung von der Reaktionstemperatur wird gewarnt
#: (PHASEN.md 5.4). Kein Literaturwert, sondern eine Hausregel.
TURNOVER_MARGIN_C = 10.0


@dataclass
class TurnoverCheck:
    tm_mean: float | None
    reaction_c: float
    verdict: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "tm_mean": None if self.tm_mean is None else round(self.tm_mean, 2),
            "reaction_c": self.reaction_c,
            "verdict": self.verdict,
            "message": self.message,
        }


def turnover(candidate: Candidate, reaction_c: float) -> TurnoverCheck:
    """Bindet das DNAzym sein Produkt zu fest fuer Mehrfachumsatz?

    Liegt der Tm der Arme deutlich ueber der Reaktionstemperatur, loest sich
    das geschnittene Produkt nicht; liegt er darunter, bindet das DNAzym sein
    Ziel gar nicht erst lange genug.
    """
    werte = [
        r.tm.value
        for r in (candidate.tm5, candidate.tm3)
        if r and r.tm and r.tm.value is not None
    ]
    if not werte:
        return TurnoverCheck(
            None, reaction_c, "unbekannt",
            "Ohne Tm der Arme lässt sich dazu nichts sagen.",
        )

    mittel = sum(werte) / len(werte)
    if mittel > reaction_c + TURNOVER_MARGIN_C:
        return TurnoverCheck(
            mittel, reaction_c, "zu fest",
            f"Der Tm der Arme liegt mit {mittel:.1f} °C deutlich über den "
            f"{reaction_c:g} °C der Reaktion. Das DNAzym bindet sein Produkt "
            "zu fest und kommt kaum zum nächsten Substrat — für Mehrfachumsatz "
            "kürzere Arme wählen.",
        )
    if mittel < reaction_c - TURNOVER_MARGIN_C:
        return TurnoverCheck(
            mittel, reaction_c, "zu locker",
            f"Der Tm der Arme liegt mit {mittel:.1f} °C deutlich unter den "
            f"{reaction_c:g} °C der Reaktion. Das DNAzym bindet sein Ziel "
            "kaum lange genug zum Schneiden — längere Arme wählen.",
        )
    return TurnoverCheck(
        mittel, reaction_c, "passend",
        f"Der Tm der Arme liegt mit {mittel:.1f} °C nahe den {reaction_c:g} °C "
        "der Reaktion. Das ist der Bereich, in dem Mehrfachumsatz möglich ist.",
    )


# ------------------------------------------------------------ alles zusammen


@dataclass
class DesignResult:
    candidates: list[Candidate] = field(default_factory=list)
    settings: DesignSettings = field(default_factory=DesignSettings)
    core: CoreSpec | None = None
    skipped_edges: int = 0
    scan_note: str | None = None
    disclaimer: str = DISCLAIMER

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidates": [c.as_dict() for c in self.candidates],
            "settings": self.settings.as_dict(),
            "core": self.core.as_dict() if self.core else None,
            "skipped_edges": self.skipped_edges,
            "scan_note": self.scan_note,
            "disclaimer": self.disclaimer,
        }


def design(
    target_sequence: str,
    scan_result: ScanResult,
    settings: DesignSettings | None = None,
    conditions: melting.Conditions | None = None,
    accessibility: Accessibility | None = None,
    registry: Registry | None = None,
    limit: int = 200,
) -> DesignResult:
    """Fuer jede Spaltstelle einen Kandidaten bauen und bewerten.

    `limit` deckelt die Zahl der durchgerechneten Kandidaten: je Kandidat
    laufen zwei Tm-Rechnungen und eine Faltung, und ein Transkript von
    mehreren Kilobasen hat Tausende von Junktionen.
    """
    reg = registry or get_registry()
    einst = settings or DesignSettings()
    bed = conditions or melting.Conditions()

    kerne = load_cores(reg)
    if not kerne:
        return DesignResult(settings=einst, scan_note="Kein Kern in cores.yaml.")
    kern = next(
        (k for k in kerne if k.id == einst.core_id), kerne[0]
    )

    kandidaten: list[Candidate] = []
    am_rand = 0

    for stelle in scan_result.sites[:limit]:
        roh = build(target_sequence, stelle, einst, kern)
        if roh is None:
            am_rand += 1
            continue

        roh.tm5 = melting.compute(roh.arm5, bed)
        roh.tm3 = melting.compute(roh.arm3, bed)
        roh.self_fold = fold.compute(parse(roh.sequence, reg), reg, with_homodimer=False)
        kandidaten.append(score(roh, einst, reg))

    # Beste zuerst; bei Gleichstand die bessere Junktion, dann die Position.
    from app.scan import QUALITY_ORDER

    kandidaten.sort(
        key=lambda c: (
            c.excluded,
            -c.score,
            QUALITY_ORDER.get(c.site.quality, 9),
            c.site.position,
        )
    )

    note = scan_result.note
    if am_rand:
        rand_hinweis = (
            f"{am_rand} Spaltstelle(n) liegen zu nah am Rand des Ziels — dort "
            "ist für beide Arme nicht genug Sequenz übrig."
        )
        note = f"{note} {rand_hinweis}" if note else rand_hinweis
    if len(scan_result.sites) > limit:
        gedeckelt = (
            f"Von {len(scan_result.sites)} Spaltstellen wurden die ersten "
            f"{limit} durchgerechnet. Für mehr den Bereich enger wählen."
        )
        note = f"{note} {gedeckelt}" if note else gedeckelt

    return DesignResult(
        candidates=kandidaten, settings=einst, core=kern,
        skipped_edges=am_rand, scan_note=note,
    )


def as_oligo(candidate: Candidate, registry: Registry | None = None) -> Oligo:
    """Den Kandidaten als Oligo, zur Uebergabe an Strang und Steckbrief."""
    return parse(candidate.sequence, registry or get_registry())


def quantity_or_none(result: melting.TmResult | None, key: str) -> Quantity | None:
    if result is None:
        return None
    return getattr(result, key, None)


__all__ = [
    "Candidate",
    "Criterion",
    "DESIGN_DISCLAIMER",
    "DISCLAIMER",
    "DesignResult",
    "DesignSettings",
    "TURNOVER_MARGIN_C",
    "TurnoverCheck",
    "as_oligo",
    "build",
    "design",
    "reverse_complement",
    "score",
    "turnover",
]

#: Alias, damit der Hinweis auch unter dem sprechenderen Namen zu finden ist.
DESIGN_DISCLAIMER = DISCLAIMER
