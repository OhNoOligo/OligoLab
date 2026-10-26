"""Gemeinsame Vorrichtungen fuer die Tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.registry import Registry
from app import library

REAL_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Die Regressionssequenz aus CLAUDE.md. Ein 10-23-DNAzym:
# Arm TTGGGGTAA (9) + Kern GGCTAGCTACAACGA (15) + Arm GGTGCATGT (9) = 33.
REFERENCE_SEQUENCE = "TTG GGG TAA GGC TAG CTA CAA CGA GGT GCA TGT"

# Die Sollwerte aus CLAUDE.md. Diese Tabelle darf nie brechen.
REFERENCE_MASSES = {
    "fully_deprotected": 10241.26,
    "plus_dmt": 10543.60,
    "plus_3_phosphate": 10303.22,
    "protected_dmt_off": 13821.16,
    "protected_ce": 12124.20,
}

# Synthesizer-Verbrauch bei 0,12 mL je Kupplung, aus CLAUDE.md.
REFERENCE_CONSUMPTION = {
    "A": (8, 41.2),
    "C": (5, 23.2),
    "G": (12, 60.5),
    "T": (8, 35.8),
}
REFERENCE_CONSUMPTION_TOTAL = 160.6
REFERENCE_CONSUMPTION_TOTAL_RESERVE = 176.6


@pytest.fixture(scope="session")
def registry() -> Registry:
    """Die echten YAML-Kataloge aus `data/`."""
    return Registry()


@pytest.fixture
def reference_sequence() -> str:
    return REFERENCE_SEQUENCE


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    """Jeder Test arbeitet auf einer Kopie von `data/`.

    Ohne das schreiben Tests, die einen eigenen Baustein anlegen, in die
    echte `data/monomers_custom.yaml` des Nutzers — und landen beim naechsten
    Commit mit im Repository. Genau das ist einmal passiert.
    """
    from app import registry as registry_module
    from app.config import settings

    kopie = tmp_path / "data"
    kopie.mkdir()
    for datei in REAL_DATA_DIR.glob("*.yaml"):
        shutil.copy(datei, kopie / datei.name)

    monkeypatch.setattr(settings, "data_dir", kopie)
    # Die gemeinsame Registry haelt ihr Verzeichnis seit dem ersten Zugriff
    # fest; sie muss neu gebaut werden, sonst greift die Umlenkung nicht.
    monkeypatch.setattr(registry_module, "_registry", None)
    yield
    monkeypatch.setattr(registry_module, "_registry", None)


@pytest.fixture(autouse=True)
def _isolated_database(tmp_path, monkeypatch):
    """Jeder Test bekommt seine eigene Datenbank.

    Sonst schreiben die Tests in `data/oligos.db` und damit in die echte
    Bibliothek des Nutzers.
    """
    library.reset_engine(f"sqlite:///{tmp_path / 'test.db'}")
    yield
    library.reset_engine("sqlite:///:memory:")
