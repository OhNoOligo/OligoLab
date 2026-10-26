"""Bibliothek: gespeicherte Oligos und Probenliste.

SQLite ueber SQLModel, Datei `data/oligos.db`. Alles lokal (CLAUDE.md,
Regel 4). Gespeichert wird immer der SEQUENZTEXT in Synthi-Sprache, nie ein
vorgerechnetes Ergebnis als einzige Quelle: beim Laden wird neu geparst und
neu gerechnet, damit eine geaenderte Monomerdatei sich sofort auswirkt.

Die mitgespeicherte Masse ist nur fuer Liste und Suche da — eine Momentaufnahme
mit Datum, kein Ersatz fuer die Rechnung.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from sqlalchemy import Engine, func
from sqlmodel import Field, Session, SQLModel, col, create_engine, select

from app.config import settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OligoRecord(SQLModel, table=True):
    """Ein Eintrag der Oligo-Bibliothek."""

    __tablename__ = "oligos"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    sequence: str
    notes: str | None = None
    length: int = 0
    mass_fully_deprotected: float | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class SampleRecord(SQLModel, table=True):
    """Eine Probe fuer die Beladungsrechnung (PHASEN.md 1.6)."""

    __tablename__ = "samples"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    n_stock_nmol: float
    v_stock_ul: float
    notes: str | None = None
    created_at: datetime = Field(default_factory=_now)


_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(settings.database_url, echo=False)
        SQLModel.metadata.create_all(_engine)
    return _engine


def reset_engine(database_url: str | None = None) -> Engine:
    """Fuer Tests: die Verbindung auf eine andere Datenbank umlegen."""
    global _engine
    _engine = create_engine(database_url or settings.database_url, echo=False)
    SQLModel.metadata.create_all(_engine)
    return _engine


def session() -> Session:
    return Session(get_engine())


# ------------------------------------------------------------------- Oligos


def save_oligo(
    name: str,
    sequence: str,
    notes: str | None = None,
    length: int = 0,
    mass: float | None = None,
) -> OligoRecord:
    """Anlegen oder, bei gleichem Namen, aktualisieren."""
    with session() as s:
        existing = s.exec(select(OligoRecord).where(OligoRecord.name == name)).first()
        if existing is None:
            record = OligoRecord(
                name=name,
                sequence=sequence,
                notes=notes,
                length=length,
                mass_fully_deprotected=mass,
            )
            s.add(record)
        else:
            existing.sequence = sequence
            existing.notes = notes
            existing.length = length
            existing.mass_fully_deprotected = mass
            existing.updated_at = _now()
            record = existing
            s.add(record)
        s.commit()
        s.refresh(record)
        return record


def _like_pattern(query: str) -> str:
    """Suchtext in ein LIKE-Muster uebersetzen.

    `%` und `_` sind in LIKE Platzhalter. Ein Oligo darf aber "100 % rein"
    heissen, und ein Unterstrich kommt in Namen staendig vor — beide werden
    darum maskiert, sonst faende die Suche nach `_` einfach alles.
    """
    escaped = (
        query.strip()
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    return f"%{escaped}%"


def list_oligos(query: str | None = None, limit: int = 500) -> list[OligoRecord]:
    """Alle Eintraege, optional durchsucht ueber Name, Sequenz und Notiz.

    Gesucht wird in SQL, nicht hinterher in Python. Wuerde erst das Limit
    greifen und dann der Filter, waeren aeltere Eintraege unauffindbar,
    sobald die Bibliothek ueber `limit` hinauswaechst.
    """
    with session() as s:
        statement = select(OligoRecord)
        if query and query.strip():
            pattern = _like_pattern(query)
            statement = statement.where(
                col(OligoRecord.name).ilike(pattern, escape="\\")
                | col(OligoRecord.sequence).ilike(pattern, escape="\\")
                | col(OligoRecord.notes).ilike(pattern, escape="\\")
            )
        statement = statement.order_by(OligoRecord.updated_at.desc()).limit(limit)
        return list(s.exec(statement))


def count_oligos(query: str | None = None) -> int:
    """Wie viele Eintraege es wirklich gibt — unabhaengig vom Limit."""
    with session() as s:
        statement = select(func.count()).select_from(OligoRecord)
        if query and query.strip():
            pattern = _like_pattern(query)
            statement = statement.where(
                col(OligoRecord.name).ilike(pattern, escape="\\")
                | col(OligoRecord.sequence).ilike(pattern, escape="\\")
                | col(OligoRecord.notes).ilike(pattern, escape="\\")
            )
        return int(s.exec(statement).one())


def get_oligo(record_id: int) -> OligoRecord | None:
    with session() as s:
        return s.get(OligoRecord, record_id)


def delete_oligo(record_id: int) -> bool:
    with session() as s:
        record = s.get(OligoRecord, record_id)
        if record is None:
            return False
        s.delete(record)
        s.commit()
        return True


def oligos_as_csv() -> str:
    """Export der Bibliothek als CSV (PHASEN.md 1.8)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        ["Name", "Sequenz", "Bausteine", "vollständig entschützt (Da)",
         "Notizen", "angelegt", "geändert"]
    )
    for r in list_oligos(limit=1_000_000):
        writer.writerow([
            r.name,
            r.sequence,
            r.length,
            "" if r.mass_fully_deprotected is None
            else f"{r.mass_fully_deprotected:.2f}",
            r.notes or "",
            r.created_at.isoformat(timespec="seconds"),
            r.updated_at.isoformat(timespec="seconds"),
        ])
    return buffer.getvalue()


# ------------------------------------------------------------------- Proben


def save_sample(
    name: str, n_stock_nmol: float, v_stock_ul: float, notes: str | None = None
) -> SampleRecord:
    with session() as s:
        existing = s.exec(select(SampleRecord).where(SampleRecord.name == name)).first()
        if existing is None:
            record = SampleRecord(
                name=name,
                n_stock_nmol=n_stock_nmol,
                v_stock_ul=v_stock_ul,
                notes=notes,
            )
        else:
            existing.n_stock_nmol = n_stock_nmol
            existing.v_stock_ul = v_stock_ul
            existing.notes = notes
            record = existing
        s.add(record)
        s.commit()
        s.refresh(record)
        return record


def list_samples(limit: int = 500) -> list[SampleRecord]:
    with session() as s:
        return list(
            s.exec(
                select(SampleRecord)
                .order_by(SampleRecord.created_at.desc())
                .limit(limit)
            )
        )


def delete_sample(record_id: int) -> bool:
    with session() as s:
        record = s.get(SampleRecord, record_id)
        if record is None:
            return False
        s.delete(record)
        s.commit()
        return True
