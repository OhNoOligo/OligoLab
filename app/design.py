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


# ------------------------------------------- 5.5 Modifikationen aufbringen


@dataclass
class ModificationChange:
    """Was ein Muster an einer Stelle geaendert hat."""

    kind: str
    position: int | None
    description: str
    in_core: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "position": self.position,
            "description": self.description,
            "in_core": self.in_core,
        }


@dataclass
class ModificationResult:
    sequence: str
    changes: list[ModificationChange] = field(default_factory=list)
    touched_core: bool = False
    blocked: bool = False
    message: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "changes": [c.as_dict() for c in self.changes],
            "touched_core": self.touched_core,
            "blocked": self.blocked,
            "message": self.message,
        }


PATTERNS = {
    "arms_phosphorothioate": "Alle Arme als Phosphorothioat",
    "lna_ends": "Die äußersten Positionen jedes Endes als LNA",
    "galnac_5prime": "5'-GalNAc anhängen",
    "replace_position": "Position durch eigenen Baustein ersetzen",
}


def apply_pattern(
    sequence: str,
    pattern: str,
    core_range: tuple[int, int] | None = None,
    count: int = 3,
    position: int | None = None,
    code: str | None = None,
    allow_core: bool = False,
    registry: Registry | None = None,
) -> ModificationResult:
    """Ein Muster auf einen Strang legen (PHASEN.md 5.5).

    Der katalytische Kern bleibt voreingestellt unangetastet. Ein Eingriff
    dort verlangt `allow_core=True` — und das ist keine Formalie: eine
    Modifikation im Kern kostet haeufig die gesamte Aktivitaet (CLAUDE.md,
    Regel 6).
    """
    from dataclasses import replace as _replace

    from app.models import Conjugate, Linkage, Monomer
    from app.notation import to_string

    from app import dnazyme

    reg = registry or get_registry()
    oligo = parse(sequence, reg)
    laenge = oligo.length

    # Schickt der Aufrufer keinen Kern mit, wird er GESUCHT — nicht
    # angenommen, es gebe keinen. Sonst haette ein vergessener Parameter
    # stillschweigend den Kern freigegeben, und genau das verbietet
    # CLAUDE.md, Regel 6. Findet sich keiner, steht das in der Antwort.
    kern_gefunden = core_range is not None
    if core_range is None:
        teile = dnazyme.detect_parts(oligo, reg)
        gefunden = teile.core_part
        if gefunden is not None:
            core_range = (gefunden.start, gefunden.end)
            kern_gefunden = True

    def im_kern(pos: int) -> bool:
        return core_range is not None and core_range[0] <= pos <= core_range[1]

    aenderungen: list[ModificationChange] = []
    monomere = list(oligo.monomers)
    bindungen = list(oligo.linkages)
    konjugate = list(oligo.conjugates)
    kern_beruehrt = False

    def mit_modifikation(monomer: Monomer, mod_code: str) -> Monomer | None:
        spec = reg.modification(mod_code)
        if spec is None:
            return None
        if any(m.code == mod_code for m in monomer.modifications):
            return monomer
        return _replace(
            monomer,
            modifications=monomer.modifications + (spec,),
            source=f"[{mod_code}-{monomer.spec.code}]",
        )

    if pattern == "arms_phosphorothioate":
        thioat = reg.modification("Thioat")
        for index, bindung in enumerate(bindungen):
            # Eine Bindung gehoert zum Kern, wenn BEIDE Nachbarn darin liegen.
            drin = im_kern(bindung.position) and im_kern(bindung.position + 1)
            if drin and not allow_core:
                continue
            if drin:
                kern_beruehrt = True
            if bindung.kind == "phosphorothioate":
                continue
            bindungen[index] = Linkage(
                position=bindung.position,
                kind="phosphorothioate",
                modification=thioat,
            )
            aenderungen.append(
                ModificationChange(
                    "phosphorothioate", bindung.position,
                    f"Bindung {bindung.position}–{bindung.position + 1} "
                    "als Phosphorothioat",
                    in_core=drin,
                )
            )

    elif pattern == "lna_ends":
        if count < 1:
            raise ValueError("Es müssen mindestens eine Position sein.")
        stellen = set(range(1, min(count, laenge) + 1))
        stellen |= set(range(max(1, laenge - count + 1), laenge + 1))
        for pos in sorted(stellen):
            drin = im_kern(pos)
            if drin and not allow_core:
                continue
            neu = mit_modifikation(monomere[pos - 1], "LNA")
            if neu is None:
                continue
            if drin:
                kern_beruehrt = True
            monomere[pos - 1] = neu
            aenderungen.append(
                ModificationChange("lna", pos, f"Position {pos} als LNA", in_core=drin)
            )

    elif pattern == "galnac_5prime":
        spec = reg.modification("5GalNAc")
        if spec is None:
            return ModificationResult(
                sequence=sequence, blocked=True,
                message="5GalNAc ist in modifications.yaml nicht angelegt.",
            )
        if any(k.code == "5GalNAc" and k.attach == "5prime" for k in konjugate):
            return ModificationResult(
                sequence=sequence,
                message="Am 5'-Ende hängt schon ein GalNAc.",
            )
        konjugate.insert(0, Conjugate(spec=spec, attach="5prime"))
        aenderungen.append(
            ModificationChange("conjugate", None, "5'-GalNAc angehängt")
        )

    elif pattern == "replace_position":
        if position is None or code is None:
            raise ValueError(
                "Zum Ersetzen braucht es eine Position und einen Bausteincode."
            )
        if not (1 <= position <= laenge):
            raise ValueError(f"Position {position} liegt nicht im Strang (1–{laenge}).")
        drin = im_kern(position)
        if drin and not allow_core:
            return ModificationResult(
                sequence=sequence, blocked=True, touched_core=True,
                message=(
                    f"Position {position} liegt im katalytischen Kern. "
                    "Eingriffe dort kosten häufig die gesamte Aktivität und "
                    "verlangen eine ausdrückliche Bestätigung."
                ),
            )
        spec = reg.monomer(code)
        if spec is None:
            mod = reg.modification(code)
            alt = monomere[position - 1]
            neu = mit_modifikation(alt, code) if mod else None
            if neu is None:
                return ModificationResult(
                    sequence=sequence, blocked=True,
                    message=f"`{code}` ist weder ein Baustein noch eine Modifikation.",
                )
        else:
            neu = Monomer(
                position=position, spec=spec, modifications=(),
                source=spec.code if len(spec.code) == 1 else f"[{spec.code}]",
            )
        if drin:
            kern_beruehrt = True
        monomere[position - 1] = neu
        aenderungen.append(
            ModificationChange(
                "replace", position,
                f"Position {position} durch {code} ersetzt", in_core=drin,
            )
        )

    else:
        raise ValueError(f"Unbekanntes Muster `{pattern}`.")

    neues_oligo = Oligo(
        monomers=monomere, linkages=bindungen, conjugates=konjugate,
        name=oligo.name, notes=oligo.notes,
    )

    nachricht = None
    if core_range and not allow_core and pattern != "galnac_5prime":
        ausgelassen = sum(
            1
            for pos in range(core_range[0], core_range[1] + 1)
            if not any(c.position == pos for c in aenderungen)
        )
        if ausgelassen:
            nachricht = (
                f"Der katalytische Kern (Position {core_range[0]}–{core_range[1]}) "
                "blieb unangetastet. Eingriffe dort verlangen eine ausdrückliche "
                "Bestätigung."
            )
    if not kern_gefunden and pattern != "galnac_5prime":
        hinweis = (
            "In diesem Strang wurde kein katalytischer Kern gefunden — die "
            "Änderungen liefen ohne Kernschutz."
        )
        nachricht = f"{nachricht} {hinweis}" if nachricht else hinweis
    if kern_beruehrt:
        nachricht = (
            f"ACHTUNG: {sum(1 for c in aenderungen if c.in_core)} Änderung(en) "
            "liegen im katalytischen Kern. Das kostet häufig die gesamte "
            "Aktivität."
        )

    return ModificationResult(
        sequence=to_string(neues_oligo),
        changes=aenderungen,
        touched_core=kern_beruehrt,
        message=nachricht,
    )


# ---------------------------------------- 5.5 vorher gegen nachher stellen


@dataclass
class Snapshot:
    """Die vergleichbaren Groessen eines Strangs (PHASEN.md 5.5)."""

    sequence: str
    length: int
    mass: float | None
    tm5: float | None
    tm3: float | None
    arm_dg_sum: float | None
    imbalance: float | None
    self_fold_mfe: float | None
    score: float | None
    rating: str | None
    #: Wo der Tm nur ueber ein natuerliches Analogon gerechnet wurde.
    #:
    #: Wichtig fuer den Vorher-Nachher-Vergleich: eine LNA hebt den Tm
    #: erheblich, aber die Nearest-Neighbor-Tabelle kennt sie nicht. Ohne
    #: diesen Vermerk laese sich "Tm unveraendert" als "LNA bewirkt nichts" —
    #: gemeint ist aber "das Modell sieht es nicht".
    tm_approximated: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        def r(value: float | None, digits: int = 2) -> float | None:
            return None if value is None else round(value, digits)

        return {
            "sequence": self.sequence,
            "length": self.length,
            "mass": r(self.mass),
            "tm5": r(self.tm5),
            "tm3": r(self.tm3),
            "arm_dg_sum": r(self.arm_dg_sum),
            "imbalance": r(self.imbalance),
            "self_fold_mfe": r(self.self_fold_mfe),
            "score": r(self.score, 4),
            "rating": self.rating,
            "tm_approximated": self.tm_approximated,
        }


def snapshot(
    sequence: str,
    arm5_length: int,
    core_length: int,
    site: CleavageSite | None = None,
    settings: DesignSettings | None = None,
    conditions: melting.Conditions | None = None,
    registry: Registry | None = None,
) -> Snapshot:
    """Masse, Tm, ΔG, Eigenfaltung und Punktzahl eines Strangs.

    Arbeitet auf dem Sequenztext, nicht auf einem `Candidate` — damit laesst
    sich derselbe Strang vor und nach dem Aufbringen einer Modifikation
    durch dieselbe Rechnung schicken.
    """
    from app import mass as mass_module

    reg = registry or get_registry()
    einst = settings or DesignSettings()
    bed = conditions or melting.Conditions()

    oligo = parse(sequence, reg)

    # Die Arme in der Monomerliste, nicht im Text: eine `[LNA-T]`-Schreibweise
    # macht den Text laenger, den Strang aber nicht.
    arm5_monomere = oligo.monomers[:arm5_length]
    arm3_monomere = oligo.monomers[arm5_length + core_length :]

    def teil(monomere: list) -> Oligo:
        return Oligo(
            monomers=[
                replace(m, position=index + 1) for index, m in enumerate(monomere)
            ],
            linkages=[],
        )

    tm5 = melting.compute(teil(arm5_monomere), bed) if arm5_monomere else None
    tm3 = melting.compute(teil(arm3_monomere), bed) if arm3_monomere else None
    eigen = fold.compute(oligo, reg, with_homodimer=False)
    masse = mass_module.compute(oligo, reg).fully_deprotected.value

    def dg(result: melting.TmResult | None) -> float | None:
        return result.dg.value if result and result.dg else None

    dg5, dg3 = dg(tm5), dg(tm3)
    summe = None if dg5 is None or dg3 is None else dg5 + dg3
    unterschied = None if dg5 is None or dg3 is None else abs(dg5 - dg3)

    punktzahl: float | None = None
    bewertung: str | None = None
    if site is not None:
        ersatz = Candidate(
            site=site, sequence=sequence,
            arm5="", arm3="", core="", core_id="",
            target_upstream="", target_downstream="",
            tm5=tm5, tm3=tm3, self_fold=eigen,
        )
        bewertet = score(ersatz, einst, reg)
        punktzahl = bewertet.score
        bewertung = bewertet.rating

    genaehert: list[str] = []
    for ergebnis in (tm5, tm3):
        if ergebnis:
            genaehert += ergebnis.approximated

    return Snapshot(
        sequence=sequence,
        length=oligo.length,
        mass=masse,
        tm5=tm5.tm.value if tm5 and tm5.tm else None,
        tm3=tm3.tm.value if tm3 and tm3.tm else None,
        arm_dg_sum=summe,
        imbalance=unterschied,
        self_fold_mfe=eigen.mfe.value if eigen.mfe else None,
        score=punktzahl,
        rating=bewertung,
        tm_approximated=genaehert,
    )
