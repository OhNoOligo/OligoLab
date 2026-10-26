"""Einstellungen. Alles lokal, keine Schluessel (CLAUDE.md, Regel 4).

`.env` haelt nur Pfade zu externen Programmen. Maschinenspezifische
Abweichungen gehoeren in `.env.local`, das nicht versioniert wird.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # `.env.local` ueberschreibt `.env`.
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Externe Programme. Leer heisst: nicht vorhanden, die betroffene Funktion
    # meldet das ruhig und die App bleibt bedienbar (Regel 4 und 8).
    melting_dir: str = ""
    orca_exe: str = ""

    work_dir: Path = PROJECT_ROOT / "data" / "work"
    data_dir: Path = PROJECT_ROOT / "data"
    help_dir: Path = PROJECT_ROOT / "help"

    # SQLite-Bibliothek der gespeicherten Oligos.
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'oligos.db'}"

    # Voreinstellungen des Synthesizers (PHASEN.md 1.5), in der Oberflaeche
    # einstellbar.
    coupling_volume_ml: float = 0.12
    reserve_fraction: float = 0.10

    @property
    def monomers_path(self) -> Path:
        return self.data_dir / "monomers.yaml"

    @property
    def protecting_groups_path(self) -> Path:
        return self.data_dir / "protecting_groups.yaml"

    @property
    def modifications_path(self) -> Path:
        return self.data_dir / "modifications.yaml"

    @property
    def extinction_path(self) -> Path:
        return self.data_dir / "extinction.yaml"


settings = Settings()
