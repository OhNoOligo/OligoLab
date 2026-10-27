"""Spaltstellen in der Ziel-RNA finden (PHASEN.md 5.2).

Das 10-23 schneidet zwischen einem Purin (A oder G) und einem darauf
folgenden Pyrimidin (U oder C). Vier Junktionen kommen in Frage, und sie sind
unterschiedlich gut:

    AU, GU   gut
    GC       maessig
    AC       schlecht — standardmaessig ausgeblendet, aber einblendbar

Das Ausblenden ist eine Anzeigeentscheidung, keine Zensur: wer AC sehen will,
schaltet es ein, und die Zahl der ausgeblendeten Stellen steht dabei.

Dazu das Muster aus PHASEN.md 5.2: ist das Purin ungepaart und das Pyrimidin
gepaart? Das ist ein veroeffentlichter Anhaltspunkt und keine Bedingung —
darum wird es mitgeteilt und nicht zum Ausschluss benutzt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.fold_target import Accessibility, TargetFold
from app.fold import pairs_from_structure

PURINES = frozenset("AG")
PYRIMIDINES = frozenset("UC")

Quality = Literal["gut", "mäßig", "schlecht"]

#: Welche Junktion wie gut ist (PHASEN.md 5.2).
JUNCTION_QUALITY: dict[str, Quality] = {
    "AU": "gut",
    "GU": "gut",
    "GC": "mäßig",
    "AC": "schlecht",
}

QUALITY_ORDER: dict[Quality, int] = {"gut": 0, "mäßig": 1, "schlecht": 2}


@dataclass(frozen=True)
class CleavageSite:
    """Eine Purin-Pyrimidin-Junktion im Ziel.

    `position` ist die Position des PURINS, 1-basiert. Geschnitten wird
    zwischen `position` und `position + 1`.
    """

    position: int
    junction: str
    quality: Quality
    #: Wahrscheinlichkeit, dass das Purin ungepaart ist (aus der Faltung).
    purine_unpaired: float | None = None
    #: Wahrscheinlichkeit, dass das Pyrimidin gepaart ist.
    pyrimidine_paired: float | None = None
    #: Zugaenglichkeit aus dem Profil der Phase 4, am Purin verankert.
    accessibility: float | None = None
    #: Trifft das Muster "Purin offen, Pyrimidin gepaart" zu?
    matches_pattern: bool | None = None

    @property
    def cut_between(self) -> tuple[int, int]:
        return (self.position, self.position + 1)

    def as_dict(self) -> dict[str, Any]:
        return {
            "position": self.position,
            "junction": self.junction,
            "quality": self.quality,
            "purine_unpaired": (
                None if self.purine_unpaired is None else round(self.purine_unpaired, 4)
            ),
            "pyrimidine_paired": (
                None
                if self.pyrimidine_paired is None
                else round(self.pyrimidine_paired, 4)
            ),
            "accessibility": (
                None if self.accessibility is None else round(self.accessibility, 4)
            ),
            "matches_pattern": self.matches_pattern,
        }


@dataclass
class ScanResult:
    sites: list[CleavageSite] = field(default_factory=list)
    hidden_poor: int = 0
    counts: dict[str, int] = field(default_factory=dict)
    start: int = 1
    end: int = 0
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "sites": [s.as_dict() for s in self.sites],
            "hidden_poor": self.hidden_poor,
            "counts": self.counts,
            "start": self.start,
            "end": self.end,
            "note": self.note,
        }


#: Ab dieser Wahrscheinlichkeit gilt eine Position als ungepaart.
UNPAIRED_THRESHOLD = 0.5


def scan(
    sequence: str,
    start: int | None = None,
    end: int | None = None,
    folding: TargetFold | None = None,
    accessibility: Accessibility | None = None,
    include_poor: bool = False,
) -> ScanResult:
    """Alle Purin-Pyrimidin-Junktionen im gewaehlten Bereich.

    `folding` und `accessibility` sind freiwillig: ohne sie gibt es die
    Junktionen samt Guete, nur ohne die strukturellen Angaben.
    """
    laenge = len(sequence)
    if laenge < 2:
        return ScanResult(start=1, end=laenge, note="Zu kurz für eine Junktion.")

    von = max(1, min(start or 1, laenge))
    bis = max(von, min(end or laenge, laenge))
    if von > bis:
        von, bis = bis, von

    # Paarungen aus der MFE-Struktur des gefalteten Bereichs, auf die
    # Positionen des ganzen Ziels umgerechnet.
    gepaart: set[int] = set()
    gefaltet_von = gefaltet_bis = 0
    if folding and folding.available and folding.structure:
        paare = pairs_from_structure(folding.structure)
        gefaltet_von, gefaltet_bis = folding.start, folding.end
        gepaart = {folding.start + index - 1 for index in paare}

    def strukturwert(position: int) -> tuple[float | None, float | None]:
        """Ungepaart beim Purin, gepaart beim Pyrimidin — oder None."""
        if not gefaltet_bis:
            return None, None
        if not (gefaltet_von <= position and position + 1 <= gefaltet_bis):
            # Ausserhalb des gefalteten Bereichs gibt es keine Aussage.
            return None, None
        purin_offen = 0.0 if position in gepaart else 1.0
        pyrimidin_zu = 1.0 if (position + 1) in gepaart else 0.0
        return purin_offen, pyrimidin_zu

    sites: list[CleavageSite] = []
    versteckt = 0
    counts: dict[str, int] = {}

    for position in range(von, min(bis, laenge - 1) + 1):
        purin = sequence[position - 1]
        pyrimidin = sequence[position]
        if purin not in PURINES or pyrimidin not in PYRIMIDINES:
            continue

        junktion = f"{purin}{pyrimidin}"
        guete = JUNCTION_QUALITY[junktion]
        counts[junktion] = counts.get(junktion, 0) + 1

        if guete == "schlecht" and not include_poor:
            versteckt += 1
            continue

        offen, zu = strukturwert(position)
        zugang = accessibility.value_at(position) if accessibility else None

        sites.append(
            CleavageSite(
                position=position,
                junction=junktion,
                quality=guete,
                purine_unpaired=offen,
                pyrimidine_paired=zu,
                accessibility=zugang,
                matches_pattern=(
                    None
                    if offen is None or zu is None
                    else offen >= UNPAIRED_THRESHOLD and zu >= UNPAIRED_THRESHOLD
                ),
            )
        )

    note = None
    if versteckt:
        note = (
            f"{versteckt} AC-Junktion(en) ausgeblendet. AC ist die schlechteste "
            "der vier und schneidet oft gar nicht — einblendbar, wenn nichts "
            "Besseres da ist."
        )

    return ScanResult(
        sites=sites, hidden_poor=versteckt, counts=counts, start=von, end=bis, note=note
    )
