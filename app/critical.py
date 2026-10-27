"""Kritische Stellen im Strang (PHASEN.md 3.3).

Die Befundtabelle aus PHASEN.md, Zeile fuer Zeile umgesetzt:

| Befund                                                      | Schweregrad |
| ----------------------------------------------------------- | ----------- |
| Modifikation im Kern, deren `core_tested` nicht `ja` ist      | kritisch    |
| Haarnadel unter -2 kcal/mol im Kern oder ueberlappend         | kritisch    |
| Haarnadel unter -2 kcal/mol sonst                             | Warnung     |
| Selbstdimer unter -6 kcal/mol                                 | Warnung     |
| G-Quadruplex-Muster (vier G-Laeufe, Abstaende 1-7)            | Warnung     |
| Arm kuerzer als 7 Nukleotide                                  | Warnung     |
| Vier oder mehr gleiche Basen hintereinander                   | Hinweis     |
| Stark unterschiedliche Armlaengen                             | Hinweis     |

Der erste Befund ist der wichtigste des ganzen Programms. Ein Eingriff im
katalytischen Kern kostet haeufig die gesamte Aktivitaet, und man sieht es dem
Strang nicht an — darum steht er hier an erster Stelle und wird als einziger
auch dann gemeldet, wenn die Faltung gar nicht laeuft.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from app.dnazyme import Part, PartsResult, base_letters
from app.fold import FoldResult
from app.models import Oligo
from app.registry import Registry

Severity = Literal["kritisch", "warnung", "hinweis"]

SEVERITY_ORDER: dict[Severity, int] = {"kritisch": 0, "warnung": 1, "hinweis": 2}

SEVERITY_LABEL: dict[Severity, str] = {
    "kritisch": "kritisch",
    "warnung": "Warnung",
    "hinweis": "Hinweis",
}

# --- Schwellen. Alle an einer Stelle, damit sie nachvollziehbar bleiben. ---

#: Ab hier gilt eine Haarnadel als stabil genug, um zu stoeren (PHASEN.md 3.3).
HAIRPIN_THRESHOLD = -2.0

#: Ab hier gilt der Strang als selbstdimerisierend.
HOMODIMER_THRESHOLD = -6.0

#: Kuerzere Arme binden das Ziel nicht zuverlaessig.
MIN_ARM_LENGTH = 7

#: Ab diesem Unterschied gelten die Arme als stark ungleich. Nicht aus der
#: Literatur, sondern eine Hausregel — darum steht sie in der Erklaerung dabei.
ARM_IMBALANCE = 3

#: Vier gleiche Basen hintereinander erschweren Synthese und Reinigung.
HOMOPOLYMER_RUN = 4

#: Kanonisches G-Quadruplex-Motiv: vier Laeufe aus mindestens drei G,
#: dazwischen Schleifen von einem bis sieben Nukleotiden.
G_QUADRUPLEX = re.compile(r"(G{3,})(.{1,7})(G{3,})(.{1,7})(G{3,})(.{1,7})(G{3,})")


#: Wie weit ein Befund reicht.
#:
#: `strand` heisst: der Befund gilt dem Strang als Ganzem und nicht einzelnen
#: Stellen. Die Sequenzkarte laesst solche Befunde in der Warnspur aus — sonst
#: faerbten sie jede Position ein und die Spur zeigte ueberall dasselbe. In der
#: Befundliste stehen sie natuerlich trotzdem.
#:
#: Das muss am Befund stehen und darf nicht aus seiner Laenge geraten werden:
#: ein Armungleichgewicht umspannt zufaellig auch den ganzen Strang, und eine
#: Haarnadel ueber die volle Laenge tut es ebenfalls — gemeint ist aber etwas
#: anderes.
Scope = Literal["position", "region", "strand"]


@dataclass(frozen=True)
class Finding:
    """Ein Befund mit Positionsbereich, Schweregrad und einem Satz Erklaerung."""

    code: str
    severity: Severity
    start: int
    end: int
    title: str
    message: str
    detail: str | None = None
    scope: Scope = "region"

    @property
    def positions(self) -> range:
        return range(self.start, self.end + 1)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "severity_label": SEVERITY_LABEL[self.severity],
            "start": self.start,
            "end": self.end,
            "title": self.title,
            "message": self.message,
            "detail": self.detail,
            "scope": self.scope,
        }


@dataclass
class CriticalResult:
    findings: list[Finding] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def worst(self) -> Severity | None:
        if not self.findings:
            return None
        return min(self.findings, key=lambda f: SEVERITY_ORDER[f.severity]).severity

    def by_position(self) -> dict[int, list[Finding]]:
        out: dict[int, list[Finding]] = {}
        for finding in self.findings:
            for position in finding.positions:
                out.setdefault(position, []).append(finding)
        return out

    def as_dict(self) -> dict[str, Any]:
        return {
            "findings": [f.as_dict() for f in self.findings],
            "worst": self.worst,
            "counts": {
                severity: sum(1 for f in self.findings if f.severity == severity)
                for severity in ("kritisch", "warnung", "hinweis")
            },
            "checked": self.checked,
            "skipped": self.skipped,
            "thresholds": {
                "hairpin_kcal": HAIRPIN_THRESHOLD,
                "homodimer_kcal": HOMODIMER_THRESHOLD,
                "min_arm_length": MIN_ARM_LENGTH,
                "arm_imbalance": ARM_IMBALANCE,
                "homopolymer_run": HOMOPOLYMER_RUN,
            },
        }


# ----------------------------------------------------- einzelne Pruefungen


def _core_modifications(oligo: Oligo, parts: PartsResult) -> list[Finding]:
    """Der wichtigste Befund des Programms.

    Gemeldet wird jede Position im Kern, deren `core_tested` nicht `ja` ist —
    also sowohl `nein` als auch `unbekannt`. `unbekannt` ist kein Freibrief:
    wer nicht weiss, ob ein Baustein im Kern funktioniert, hat denselben
    Grund zur Vorsicht wie jemand, der weiss, dass er es nicht tut.
    """
    core = parts.core_part
    if core is None or parts.core is None:
        return []

    findings: list[Finding] = []
    for monomer in oligo.monomers[core.start - 1 : core.end]:
        # Entschieden wird allein an `core_tested`. Vorher stand hier
        # zusaetzlich, dass unmodifizierte DNA nie gemeldet wird — damit waere
        # ein Baustein, den jemand in monomers.yaml ausdruecklich auf
        # `core_tested: nein` setzt, stillschweigend durchgerutscht. Fuer die
        # vier DNA-Standardbausteine aendert sich nichts: die stehen auf `ja`.
        if monomer.core_tested == "ja":
            continue

        erprobt = monomer.core_tested

        was = (
            ", ".join(m.name for m in monomer.modifications)
            if monomer.modifications
            else monomer.spec.name
        )
        grund = (
            "ist im Kern nachweislich nicht erprobt"
            if erprobt == "nein"
            else "ist im Kern nicht erprobt (unbekannt)"
        )
        findings.append(
            Finding(
                code="core_modification",
                severity="kritisch",
                scope="position",
                start=monomer.position,
                end=monomer.position,
                title=f"Modifikation im katalytischen Kern: {was}",
                message=(
                    f"Position {monomer.position} liegt im Kern "
                    f"{parts.core.name} und {grund}."
                ),
                detail=(
                    "Eingriffe im katalytischen Kern kosten häufig die gesamte "
                    "Aktivität. Wenn die Modifikation dort gewollt ist, gehört "
                    "ein Aktivitätstest dazu — und der Baustein sollte in "
                    "monomers.yaml auf core_tested: ja gesetzt werden, sobald "
                    "er sich bewährt hat."
                ),
            )
        )
    return findings


def _hairpins(folding: FoldResult, parts: PartsResult) -> list[Finding]:
    core = parts.core_part
    findings: list[Finding] = []

    for hairpin in folding.hairpins:
        if hairpin.energy is None or hairpin.energy >= HAIRPIN_THRESHOLD:
            continue

        trifft_kern = core is not None and core.overlaps(hairpin.start, hairpin.end)
        severity: Severity = "kritisch" if trifft_kern else "warnung"
        wo = (
            "im katalytischen Kern oder überlappend"
            if trifft_kern
            else "außerhalb des Kerns"
        )
        findings.append(
            Finding(
                code="hairpin_core" if trifft_kern else "hairpin",
                severity=severity,
                start=hairpin.start,
                end=hairpin.end,
                title=f"Haarnadel {hairpin.energy:.1f} kcal/mol {wo}",
                message=(
                    f"Position {hairpin.start} bis {hairpin.end} faltet in eine "
                    f"Haarnadel mit {hairpin.energy:.1f} kcal/mol "
                    f"(Schwelle {HAIRPIN_THRESHOLD:.0f})."
                ),
                detail=(
                    "Eine Haarnadel im Kern hält den Strang in einer Form, in "
                    "der er nicht arbeiten kann."
                    if trifft_kern
                    else "Eine Haarnadel im Arm konkurriert mit der Bindung ans Ziel."
                ),
            )
        )
    return findings


def _homodimer(folding: FoldResult, length: int) -> list[Finding]:
    energy = folding.homodimer_energy
    if energy is None or energy.value is None:
        return []
    if energy.value >= HOMODIMER_THRESHOLD:
        return []
    return [
        Finding(
            code="homodimer",
            severity="warnung",
            scope="strand",
            start=1,
            end=length,
            title=f"Selbstdimer {energy.value:.1f} kcal/mol",
            message=(
                f"Der Strang paart mit sich selbst, {energy.value:.1f} kcal/mol "
                f"(Schwelle {HOMODIMER_THRESHOLD:.0f})."
            ),
            detail=(
                "Was sich mit seinesgleichen zusammenlegt, steht für das Ziel "
                "nicht zur Verfügung. Betrifft den ganzen Strang, darum ist "
                "kein einzelner Bereich markiert."
            ),
        )
    ]


def _quadruplex(letters: list[str | None]) -> list[Finding]:
    text = "".join(letter or "." for letter in letters)
    findings: list[Finding] = []
    for match in G_QUADRUPLEX.finditer(text):
        findings.append(
            Finding(
                code="g_quadruplex",
                severity="warnung",
                start=match.start() + 1,
                end=match.end(),
                title="G-Quadruplex-Muster",
                message=(
                    f"Position {match.start() + 1} bis {match.end()} passt auf vier "
                    "G-Läufe mit Abständen von eins bis sieben."
                ),
                detail=(
                    "Ein Quadruplex ist eine eigene, sehr stabile Faltung, die "
                    "die übliche Strukturvorhersage nicht erfasst. Das Muster "
                    "ist ein Verdacht, kein Nachweis — es sagt, wo man "
                    "nachsehen sollte."
                ),
            )
        )
    return findings


def _arms(parts: PartsResult) -> list[Finding]:
    findings: list[Finding] = []
    arme = [(part, part.label) for part in parts.parts if part.kind != "core"]

    for part, label in arme:
        if part.length < MIN_ARM_LENGTH:
            findings.append(
                Finding(
                    code="short_arm",
                    severity="warnung",
                    start=part.start,
                    end=part.end,
                    title=f"{label} nur {part.length} Nukleotide",
                    message=(
                        f"Der {label} ist {part.length} Nukleotide lang, "
                        f"weniger als {MIN_ARM_LENGTH}."
                    ),
                    detail=(
                        "Kurze Arme binden das Ziel zu schwach und zu wenig "
                        "spezifisch."
                    ),
                )
            )

    if len(arme) == 2:
        (erster, _), (zweiter, _) = arme
        unterschied = abs(erster.length - zweiter.length)
        if unterschied >= ARM_IMBALANCE:
            findings.append(
                Finding(
                    code="arm_imbalance",
                    severity="hinweis",
                    scope="strand",
                    start=min(erster.start, zweiter.start),
                    end=max(erster.end, zweiter.end),
                    title=f"Armlängen unterschiedlich: {erster.length} und {zweiter.length}",
                    message=(
                        f"Die Arme sind {erster.length} und {zweiter.length} "
                        f"Nukleotide lang, Unterschied {unterschied}."
                    ),
                    detail=(
                        f"Ab {ARM_IMBALANCE} Nukleotiden Unterschied wird das hier "
                        "gemeldet — eine Hausregel, kein Literaturwert. Ungleiche "
                        "Arme lösen sich ungleich schnell vom Produkt, was den "
                        "Mehrfachumsatz bremsen kann."
                    ),
                )
            )
    return findings


def _homopolymers(letters: list[str | None]) -> list[Finding]:
    findings: list[Finding] = []
    lauf_start = 0
    for index in range(1, len(letters) + 1):
        gleich = (
            index < len(letters)
            and letters[index] is not None
            and letters[index] == letters[lauf_start]
        )
        if gleich:
            continue
        laenge = index - lauf_start
        if laenge >= HOMOPOLYMER_RUN and letters[lauf_start] is not None:
            base = letters[lauf_start]
            findings.append(
                Finding(
                    code="homopolymer",
                    severity="hinweis",
                    start=lauf_start + 1,
                    end=index,
                    title=f"{laenge}× {base} hintereinander",
                    message=(
                        f"Position {lauf_start + 1} bis {index} ist ein Lauf aus "
                        f"{laenge} gleichen Basen."
                    ),
                    detail=(
                        "Lange gleiche Läufe erschweren Synthese und Reinigung "
                        "und können Fehlpaarungen begünstigen."
                    ),
                )
            )
        lauf_start = index
    return findings


# --------------------------------------------------------------- Zusammenbau


def compute(
    oligo: Oligo,
    parts: PartsResult,
    folding: FoldResult | None = None,
    registry: Registry | None = None,
) -> CriticalResult:
    """Alle Befunde, nach Schweregrad sortiert.

    Was ohne Faltung geprueft werden kann, wird auch ohne sie geprueft — die
    Modifikation im Kern vor allem. Ist ViennaRNA nicht da, fehlen nur die
    strukturellen Befunde, und das steht in `skipped`.
    """
    del registry

    letters = base_letters(oligo)
    findings: list[Finding] = []
    checked: list[str] = []
    skipped: list[str] = []

    if parts.found:
        findings += _core_modifications(oligo, parts)
        findings += _arms(parts)
        checked += ["Modifikation im Kern", "Armlängen"]
    else:
        skipped += [
            "Modifikation im Kern — kein katalytischer Kern erkannt",
            "Armlängen — kein katalytischer Kern erkannt",
        ]

    findings += _quadruplex(letters)
    findings += _homopolymers(letters)
    checked += ["G-Quadruplex-Muster", "gleiche Basen hintereinander"]

    if folding is not None and folding.available:
        findings += _hairpins(folding, parts)
        findings += _homodimer(folding, oligo.length)
        checked += ["Haarnadeln", "Selbstdimer"]
    else:
        grund = folding.note if folding else "Faltung nicht gerechnet"
        skipped += [f"Haarnadeln — {grund}", f"Selbstdimer — {grund}"]

    findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.start, f.code))
    return CriticalResult(findings=findings, checked=checked, skipped=skipped)
