"""Laedt die YAML-Kataloge und haelt sie als Objekte bereit.

Diese Datei steht nicht in der Verzeichnisstruktur von CLAUDE.md; sie ist
Infrastruktur, damit `mass.py`, `notation.py` und die uebrigen Module nicht
jeder fuer sich YAML lesen. Alle Dateien werden mit `encoding='utf-8'`
gelesen und geschrieben (Regel 7).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from app.config import settings
from app.models import ModificationSpec, MonomerSpec

# Die Konstanten, die laut CLAUDE.md verbindlich sind. Weicht eine geladene
# Datei davon ab, wird der Baustein als `deviates_from_excel` markiert und die
# Oberflaeche hebt ihn hervor — nie stillschweigend (Regel 2).
EXCEL_MASS_RESIDUE = {
    "A": 312.05, "C": 289.18, "G": 328.05, "T": 303.04,
    "O": 328.05, "I": 304.03, "Z": 344.04, "U": 305.02,
    "E": 250.00, "L": 371.04,
}
EXCEL_AMIDITE = {
    "A": 857.95, "C": 771.85, "G": 839.92, "T": 744.83,
    "U": 760.82, "O": 887.97, "I": 801.88, "Z": 869.97,
    "E": 948.85, "L": 800.00,
}
EXCEL_CONC = {
    "A": 0.05, "C": 0.05, "G": 0.05, "T": 0.05,
    "U": 0.07, "O": 0.07, "I": 0.07, "Z": 0.07,
    "E": 0.10, "L": 0.07,
}


# Die Ueberlagerungsdateien. Angelegt werden sie erst, wenn der Nutzer etwas
# eintraegt; fehlen sie, aendert das nichts.
CUSTOM_MONOMERS_FILE = "monomers_custom.yaml"
CUSTOM_MODIFICATIONS_FILE = "modifications_custom.yaml"


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _close(a: float | None, b: float | None, tol: float = 1e-9) -> bool:
    if a is None or b is None:
        return a is b
    return abs(a - b) <= tol


class Registry:
    """Alle Kataloge an einer Stelle."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or settings.data_dir
        self.monomers: dict[str, MonomerSpec] = {}
        self.modifications: dict[str, ModificationSpec] = {}
        self.protecting_groups: dict[str, float] = {}
        self.protecting_group_by_base: dict[str, str | None] = {}
        self.termini: dict[str, dict[str, Any]] = {}
        self.extinction: dict[str, Any] = {}
        self.reload()

    # ---------------------------------------------------------------- laden

    def reload(self) -> None:
        self._load_monomers()
        self._load_modifications()
        self._load_protecting_groups()
        self._load_extinction()

    def _load_monomers(self) -> None:
        raw = _read_yaml(self._data_dir / "monomers.yaml")
        self.protecting_group_by_base = raw.get("protecting_group_by_base", {})

        # Eigene Bausteine und Aenderungen des Nutzers stehen in einer
        # SEPARATEN Datei. Damit bleibt `monomers.yaml` samt Kommentaren die
        # unangetastete Abschrift des Excel — und jede Abweichung ist schon
        # dadurch sichtbar, dass sie woanders steht (CLAUDE.md, Regel 2).
        overlay = _read_yaml(self._data_dir / CUSTOM_MONOMERS_FILE)
        entries = list(raw.get("monomers") or [])
        by_code = {str(e["code"]).upper(): i for i, e in enumerate(entries)}
        for extra in overlay.get("monomers") or []:
            code = str(extra["code"]).upper()
            if code in by_code:
                merged = dict(entries[by_code[code]])
                merged.update(extra)
                entries[by_code[code]] = merged
            else:
                entries.append(extra)

        self.monomers = {}
        self.custom_codes = {
            str(e["code"]).upper() for e in (overlay.get("monomers") or [])
        }
        for entry in entries:
            spec = MonomerSpec(
                code=str(entry["code"]).upper(),
                name=entry.get("name", entry["code"]),
                typ=entry.get("typ", "custom"),
                mass_residue=entry.get("mass_residue"),
                mass_amidite=entry.get("mass_amidite"),
                conc_molar=entry.get("conc_molar"),
                formula_residue=entry.get("formula_residue"),
                eps260=entry.get("eps260"),
                base_parent=(entry.get("base_parent") or None),
                core_tested=entry.get("core_tested", "unbekannt"),
                smiles=entry.get("smiles"),
                quelle=entry.get("quelle"),
            )
            code = spec.code
            deviates = False
            if code in EXCEL_MASS_RESIDUE:
                deviates = (
                    not _close(spec.mass_residue, EXCEL_MASS_RESIDUE[code])
                    or not _close(spec.mass_amidite, EXCEL_AMIDITE.get(code))
                    or not _close(spec.conc_molar, EXCEL_CONC.get(code))
                )
            else:
                # Ein Baustein, den es im Excel nicht gab, ist per se eine
                # Abweichung und wird in der Oberflaeche hervorgehoben.
                deviates = True
            self.monomers[code] = replace(spec, deviates_from_excel=deviates)

    def _load_modifications(self) -> None:
        raw = _read_yaml(self._data_dir / "modifications.yaml")
        overlay = _read_yaml(self._data_dir / CUSTOM_MODIFICATIONS_FILE)
        entries = (
            list(raw.get("modifications") or [])
            + list(raw.get("custom") or [])
            + list(overlay.get("modifications") or [])
        )
        self.modifications = {}
        for entry in entries:
            spec = ModificationSpec(
                code=str(entry["code"]),
                name=entry.get("name", entry["code"]),
                mass_diff=entry.get("mass_diff"),
                scope=entry.get("scope", "monomer"),
                klasse=entry.get("klasse", "sonstige"),
                formula=entry.get("formula"),
                counts_as_base=entry.get("counts_as_base", True),
                base_parent=entry.get("base_parent"),
                core_tested=entry.get("core_tested", "unbekannt"),
                needs_review=entry.get("needs_review", False),
                eps260=entry.get("eps260"),
                note=entry.get("note"),
                quelle=entry.get("quelle"),
            )
            self.modifications[spec.code] = spec
        # Nachschlagen soll auch ohne Ruecksicht auf Gross-/Kleinschreibung gehen.
        self._modifications_ci = {k.upper(): k for k in self.modifications}

    def _load_protecting_groups(self) -> None:
        raw = _read_yaml(self._data_dir / "protecting_groups.yaml")
        self.protecting_groups = {
            str(g["code"]): float(g["mass"]) for g in raw.get("groups", [])
        }
        self.protecting_group_details = {
            str(g["code"]): g for g in raw.get("groups", [])
        }
        self.termini = raw.get("termini", {}) or {}

    def _load_extinction(self) -> None:
        path = self._data_dir / "extinction.yaml"
        self.extinction = _read_yaml(path) if path.exists() else {}

    # ------------------------------------------------------------ zugreifen

    def monomer(self, code: str) -> MonomerSpec | None:
        return self.monomers.get(code.upper())

    def modification(self, code: str) -> ModificationSpec | None:
        direct = self.modifications.get(code)
        if direct is not None:
            return direct
        key = self._modifications_ci.get(code.upper())
        return self.modifications.get(key) if key else None

    def protecting_group_for_base(self, base: str | None) -> tuple[str | None, float]:
        """Schutzgruppe und ihre Masse fuer ein natuerliches Analogon."""
        if not base:
            return None, 0.0
        code = self.protecting_group_by_base.get(base.upper())
        if not code:
            return None, 0.0
        return code, self.protecting_groups.get(code, 0.0)

    @property
    def dmt_mass(self) -> float:
        return float(self.termini.get("DMT", {}).get("mass", 302.34))

    @property
    def phosphate_offset(self) -> float:
        return float(self.termini.get("phosphate_offset", {}).get("mass", 61.96))

    @property
    def cyanoethyl_mass(self) -> float:
        return float(self.protecting_groups.get("CE", 53.03))


_registry: Registry | None = None


def get_registry() -> Registry:
    """Gemeinsame Instanz. `reload()` nach dem Bearbeiten der YAML-Dateien."""
    global _registry
    if _registry is None:
        _registry = Registry()
    return _registry


# --------------------------------------------------------------- schreiben


def _write_overlay(path: Path, key: str, entry: dict[str, Any], header: str) -> None:
    """Einen Eintrag in eine Ueberlagerungsdatei schreiben.

    Gleicher Code ersetzt den vorhandenen Eintrag. Geschrieben wird erst in
    eine Nachbardatei und dann umbenannt, damit ein Abbruch mitten im
    Schreiben die Datei nicht halb zuruecklaesst.
    """
    data = _read_yaml(path)
    entries = list(data.get(key) or [])
    code = str(entry["code"])
    for index, existing in enumerate(entries):
        if str(existing.get("code")).upper() == code.upper():
            entries[index] = entry
            break
    else:
        entries.append(entry)
    data[key] = entries

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as fh:
        fh.write(header)
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)
    temporary.replace(path)


MONOMER_OVERLAY_HEADER = """# OligoLab — eigene Bausteine und Aenderungen
#
# Diese Datei wird vom Programm geschrieben. Was hier steht, ueberlagert
# `monomers.yaml` je Code. `monomers.yaml` selbst bleibt die unangetastete
# Abschrift des Excel.
#
# Jeder Eintrag hier gilt als Abweichung von den Excel-Konstanten und wird in
# der Oberflaeche farblich hervorgehoben.

"""

MODIFICATION_OVERLAY_HEADER = """# OligoLab — eigene Modifikationen
#
# Diese Datei wird vom Programm geschrieben und ergaenzt
# `modifications.yaml`.

"""


def save_monomer(entry: dict[str, Any], data_dir: Path | None = None) -> None:
    """Einen eigenen Baustein anlegen oder einen vorhandenen aendern."""
    directory = data_dir or settings.data_dir
    _write_overlay(
        directory / CUSTOM_MONOMERS_FILE, "monomers", entry, MONOMER_OVERLAY_HEADER
    )


def save_modification(entry: dict[str, Any], data_dir: Path | None = None) -> None:
    """Eine eigene Modifikation anlegen oder eine vorhandene aendern."""
    directory = data_dir or settings.data_dir
    _write_overlay(
        directory / CUSTOM_MODIFICATIONS_FILE,
        "modifications",
        entry,
        MODIFICATION_OVERLAY_HEADER,
    )


def remove_monomer_override(code: str, data_dir: Path | None = None) -> bool:
    """Eine eigene Aenderung zuruecknehmen — der Excel-Wert gilt wieder."""
    directory = data_dir or settings.data_dir
    path = directory / CUSTOM_MONOMERS_FILE
    data = _read_yaml(path)
    entries = list(data.get("monomers") or [])
    rest = [e for e in entries if str(e.get("code")).upper() != code.upper()]
    if len(rest) == len(entries):
        return False
    data["monomers"] = rest
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as fh:
        fh.write(MONOMER_OVERLAY_HEADER)
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)
    temporary.replace(path)
    return True
