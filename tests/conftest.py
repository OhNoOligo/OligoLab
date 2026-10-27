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


@pytest.fixture
def registry(data_dir) -> Registry:
    """Die Kataloge — auf einer Kopie, nie auf dem echten `data/`.

    Bewusst NICHT session-weit: eine einmal gebaute Registry haelt ihr
    Verzeichnis fest und haette die Umlenkung je Test ueberlebt. Genau daran
    ist einmal ein Test ins echte Projektverzeichnis durchgeschlagen und hat
    dort einen Baustein veraendert.
    """
    return Registry(data_dir)


@pytest.fixture
def reference_sequence() -> str:
    return REFERENCE_SEQUENCE


#: Was im echten `data/` stand, BEVOR die Tests liefen.
#:
#: Eine feste Liste ginge hier nicht: wer sich einen eigenen Baustein
#: angelegt hat, hat ein `monomers_custom.yaml` im Verzeichnis, und eine
#: Liste wuerde ihm die ganze Testsuite rotfaerben. Gesucht wird darum
#: nicht nach Unbekanntem, sondern nach NEUEM.
def _bestand() -> set[str]:
    if not REAL_DATA_DIR.exists():
        return set()
    return {
        eintrag.name
        for eintrag in REAL_DATA_DIR.iterdir()
        if not eintrag.name.startswith(".")
    }


ERLAUBT_IN_DATA = _bestand()


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    """Jeder Test arbeitet auf einer Kopie von `data/`.

    Ohne das schreiben Tests, die einen eigenen Baustein anlegen, in die
    echte `data/monomers_custom.yaml` — und landen beim naechsten Commit mit
    im Repository. Das ist zweimal passiert, darum prueft die Fixture am Ende
    nach.
    """
    from app import registry as registry_module
    from app.config import settings

    kopie = tmp_path / "data"
    (kopie / "targets").mkdir(parents=True)
    for datei in REAL_DATA_DIR.glob("*.yaml"):
        shutil.copy(datei, kopie / datei.name)

    monkeypatch.setattr(settings, "data_dir", kopie)
    # Die gemeinsame Registry haelt ihr Verzeichnis seit dem ersten Zugriff
    # fest; sie muss neu gebaut werden, sonst greift die Umlenkung nicht.
    monkeypatch.setattr(registry_module, "_registry", None)

    yield kopie

    monkeypatch.setattr(registry_module, "_registry", None)

    # Die Nachkontrolle. Lieber ein lauter Test als eine stille Aenderung
    # am Projektverzeichnis.
    neu = sorted(_bestand() - ERLAUBT_IN_DATA)
    assert not neu, (
        f"Der Test hat ins echte data/ geschrieben: {neu}. "
        "Alles Schreibende gehört auf die Kopie aus der `data_dir`-Fixture."
    )


@pytest.fixture(autouse=True)
def _isolated_database(tmp_path, monkeypatch):
    """Jeder Test bekommt seine eigene Datenbank.

    Sonst schreiben die Tests in `data/oligos.db` und damit in die echte
    Bibliothek des Nutzers.
    """
    library.reset_engine(f"sqlite:///{tmp_path / 'test.db'}")
    yield
    library.reset_engine("sqlite:///:memory:")
