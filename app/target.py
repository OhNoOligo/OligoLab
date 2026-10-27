"""Die Ziel-RNA holen und verwalten (PHASEN.md 4.1).

Vier Wege hinein: Direkteingabe, FASTA, GenBank und drei Datenbanken. Alles,
was hereinkommt, laeuft durch `normalise()` und ist danach RNA in
Grossbuchstaben.

CLAUDE.md Regel 4 gilt streng: Netzzugriff nur fuer diese optionalen Abrufe,
immer mit lokalem Zwischenspeicher, und ohne Netz bleibt die Seite voll
bedienbar. Ein fehlgeschlagener Abruf ist darum kein Fehler, sondern ein
Ergebnis mit `available: False` und einem ruhigen Satz dazu.

Regel 5 gilt auch hier: ein unbekanntes Zeichen in einer Zielsequenz ist ein
Fehler mit Positionsangabe, kein stillschweigend uebersprungenes Zeichen.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from app.config import settings

# Erlaubt sind die vier RNA-Basen und N als ausdrueckliches "unbekannt".
VALID_BASES = set("ACGUN")

# Zahlen und Leerraum kommen in jeder zweiten kopierten Sequenz vor —
# Positionsangaben aus einem Alignment, Zeilenumbrueche aus FASTA. Sie werden
# entfernt, nicht als Fehler gemeldet (PHASEN.md 4.1).
_IGNORED = re.compile(r"[\s\d]+")

RegionKind = Literal["5utr", "cds", "3utr", "other"]

REGION_LABEL: dict[RegionKind, str] = {
    "5utr": "5'UTR",
    "cds": "CDS",
    "3utr": "3'UTR",
    "other": "sonstiges",
}


class TargetError(ValueError):
    """Ein unbekanntes Zeichen in der Zielsequenz, mit Positionsangabe."""

    def __init__(self, position: int, character: str) -> None:
        self.position = position
        self.character = character
        super().__init__(
            f"Position {position}: Unbekanntes Zeichen `{character}`. "
            "Erlaubt sind A, C, G, U (oder T) und N."
        )


@dataclass(frozen=True)
class Region:
    """Ein benannter Abschnitt, 1-basiert und einschliesslich beider Enden."""

    kind: RegionKind
    start: int
    end: int
    label: str | None = None

    @property
    def length(self) -> int:
        return self.end - self.start + 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label or REGION_LABEL[self.kind],
            "start": self.start,
            "end": self.end,
            "length": self.length,
        }


@dataclass
class Target:
    """Eine Ziel-RNA samt Herkunft."""

    name: str
    sequence: str
    source: str = "Direkteingabe"
    identifier: str | None = None
    fetched_at: str | None = None
    regions: list[Region] = field(default_factory=list)
    organism: str | None = None
    description: str | None = None
    note: str | None = None

    @property
    def length(self) -> int:
        return len(self.sequence)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "sequence": self.sequence,
            "length": self.length,
            "source": self.source,
            "identifier": self.identifier,
            "fetched_at": self.fetched_at,
            "regions": [r.as_dict() for r in self.regions],
            "organism": self.organism,
            "description": self.description,
            "note": self.note,
        }


# ------------------------------------------------------------- einlesen


def normalise(text: str) -> str:
    """Rohtext in RNA-Grossbuchstaben.

    Leerraum und Zahlen fallen weg, T wird zu U. Jedes andere unbekannte
    Zeichen ist ein Fehler mit Positionsangabe — die Position zaehlt dabei
    die BEREINIGTE Sequenz, denn nur die sieht der Nutzer hinterher.
    """
    cleaned = _IGNORED.sub("", text).upper().replace("T", "U")
    for index, character in enumerate(cleaned, start=1):
        if character not in VALID_BASES:
            raise TargetError(index, character)
    return cleaned


def from_text(text: str, name: str = "Direkteingabe") -> Target:
    """Direkteingabe. DNA wird stillschweigend zu RNA (PHASEN.md 4.1)."""
    return Target(name=name, sequence=normalise(text), source="Direkteingabe")


def _records(text: str, fmt: str):
    from io import StringIO

    from Bio import SeqIO

    return list(SeqIO.parse(StringIO(text), fmt))


def from_fasta(text: str, name: str | None = None) -> Target:
    """FASTA, mit Biopython geparst. Nimmt den ersten Eintrag."""
    records = _records(text, "fasta")
    if not records:
        raise ValueError("Die Datei enthält keinen FASTA-Eintrag.")
    record = records[0]
    note = (
        f"Die Datei enthält {len(records)} Einträge; genommen wurde der erste."
        if len(records) > 1
        else None
    )
    return Target(
        name=name or record.id or "FASTA",
        sequence=normalise(str(record.seq)),
        source="FASTA",
        identifier=record.id or None,
        description=record.description or None,
        note=note,
    )


def from_genbank(text: str, name: str | None = None) -> Target:
    """GenBank, mit Biopython geparst.

    Die Abschnitte kommen aus den Merkmalen: was vor dem CDS liegt, ist
    5'UTR, was danach, ist 3'UTR. Steht ein UTR ausdruecklich in der Datei,
    gilt das.
    """
    records = _records(text, "genbank")
    if not records:
        raise ValueError("Die Datei enthält keinen GenBank-Eintrag.")
    record = records[0]
    sequence = normalise(str(record.seq))

    regions: list[Region] = []
    cds: tuple[int, int] | None = None

    for feature in record.features:
        start = int(feature.location.start) + 1
        end = int(feature.location.end)
        if feature.type == "CDS" and cds is None:
            cds = (start, end)
            regions.append(Region("cds", start, end))
        elif feature.type == "5'UTR":
            regions.append(Region("5utr", start, end))
        elif feature.type == "3'UTR":
            regions.append(Region("3utr", start, end))

    # Fehlen die UTR-Merkmale, ergeben sie sich aus der Lage des CDS.
    if cds is not None:
        vorhanden = {r.kind for r in regions}
        if "5utr" not in vorhanden and cds[0] > 1:
            regions.append(Region("5utr", 1, cds[0] - 1))
        if "3utr" not in vorhanden and cds[1] < len(sequence):
            regions.append(Region("3utr", cds[1] + 1, len(sequence)))

    regions.sort(key=lambda r: r.start)

    organism = record.annotations.get("organism")
    return Target(
        name=name or record.id or "GenBank",
        sequence=sequence,
        source="GenBank",
        identifier=record.id or None,
        organism=organism,
        description=record.description or None,
        regions=regions,
    )


# --------------------------------------------------------- Zwischenspeicher


def _cache_dir() -> Path:
    path = settings.data_dir / "targets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_path(source: str, identifier: str) -> Path:
    safe = re.sub(r"[^\w.-]", "_", identifier)[:80]
    return _cache_dir() / f"{source}_{safe}.json"


def read_cache(source: str, identifier: str) -> Target | None:
    path = _cache_path(source, identifier)
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    return Target(
        name=raw.get("name", identifier),
        sequence=raw.get("sequence", ""),
        source=raw.get("source", source),
        identifier=raw.get("identifier", identifier),
        fetched_at=raw.get("fetched_at"),
        regions=[
            Region(
                kind=r["kind"], start=r["start"], end=r["end"], label=r.get("label")
            )
            for r in raw.get("regions", [])
        ],
        organism=raw.get("organism"),
        description=raw.get("description"),
        note=raw.get("note"),
    )


def write_cache(target: Target) -> None:
    if not target.identifier:
        return
    path = _cache_path(target.source, target.identifier)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as fh:
        json.dump(target.as_dict(), fh, ensure_ascii=False, indent=1)
    temporary.replace(path)


# ------------------------------------------------------------ Ratenbremse

#: Wie viele Anfragen je Sekunde die Anbieter erlauben (PHASEN.md 4.1).
RATE_LIMITS: dict[str, float] = {
    "ensembl": 15.0,
    "ncbi": 3.0,
    "rnacentral": 20.0,
}

_last_request: dict[str, float] = {}


def _throttle(source: str) -> None:
    """Wartet, bis die naechste Anfrage erlaubt ist.

    Die Grenzen stehen in den Nutzungsbedingungen der Anbieter. Sie zu
    ueberschreiten fuehrt zu Sperren — und zwar fuer den Nutzer, nicht fuer
    uns.
    """
    limit = RATE_LIMITS.get(source)
    if not limit:
        return
    abstand = 1.0 / limit
    vorher = _last_request.get(source)
    if vorher is not None:
        schon = time.monotonic() - vorher
        if schon < abstand:
            time.sleep(abstand - schon)
    _last_request[source] = time.monotonic()


# ---------------------------------------------------------------- abrufen


@dataclass
class FetchResult:
    """Ergebnis eines Abrufs. Fehlschlag ist kein Fehler, sondern ein Zustand."""

    available: bool
    target: Target | None = None
    choices: list[dict[str, Any]] = field(default_factory=list)
    from_cache: bool = False
    message: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "target": self.target.as_dict() if self.target else None,
            "choices": self.choices,
            "from_cache": self.from_cache,
            "message": self.message,
        }


OFFLINE_HINT = (
    "Die Datenbank ist gerade nicht erreichbar. Das ist kein Fehler: OligoLab "
    "rechnet lokal und bleibt ohne Netz voll bedienbar. Die Sequenz lässt sich "
    "von Hand einfügen oder als FASTA hochladen."
)


def _get(url: str, source: str, params: dict[str, Any] | None = None) -> Any:
    """Eine Anfrage, gebremst und mit Zeitlimit. Wirft bei jedem Problem."""
    import httpx

    _throttle(source)
    headers = {"Accept": "application/json", "User-Agent": "OligoLab/0.1"}
    with httpx.Client(timeout=settings.network_timeout_s, headers=headers) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch_ensembl(symbol_or_id: str, species: str = "homo_sapiens") -> FetchResult:
    """Ensembl REST.

    Ein Gensymbol liefert in der Regel mehrere Transkripte. Die werden als
    Auswahlliste zurueckgegeben, kanonisches und laengstes gekennzeichnet —
    welches Transkript gemeint ist, entscheidet der Nutzer und nicht wir.
    """
    import httpx

    cached = read_cache("ensembl", symbol_or_id)
    base = settings.ensembl_url.rstrip("/")

    try:
        if symbol_or_id.upper().startswith("ENST"):
            daten = _get(f"{base}/sequence/id/{symbol_or_id}", "ensembl",
                         {"type": "cdna", "content-type": "application/json"})
            target = Target(
                name=daten.get("display_id", symbol_or_id),
                sequence=normalise(daten["seq"]),
                source="ensembl",
                identifier=symbol_or_id,
                fetched_at=_now(),
                description=daten.get("desc"),
            )
            write_cache(target)
            return FetchResult(available=True, target=target)

        # Gensymbol: erst die Gen-Kennung, dann die Transkripte.
        gen = _get(f"{base}/lookup/symbol/{species}/{symbol_or_id}", "ensembl",
                   {"expand": "1", "content-type": "application/json"})
        transkripte = gen.get("Transcript") or []
        if not transkripte:
            return FetchResult(
                available=True,
                message=f"Zu `{symbol_or_id}` gibt es in Ensembl keine Transkripte.",
            )

        laengste = max(
            transkripte,
            key=lambda t: abs(int(t.get("end", 0)) - int(t.get("start", 0))),
        )
        choices = [
            {
                "id": t.get("id"),
                "name": t.get("display_name") or t.get("id"),
                "biotype": t.get("biotype"),
                "length": abs(int(t.get("end", 0)) - int(t.get("start", 0))) + 1,
                "canonical": bool(t.get("is_canonical")),
                "longest": t.get("id") == laengste.get("id"),
            }
            for t in transkripte
        ]
        choices.sort(key=lambda c: (not c["canonical"], not c["longest"]))
        return FetchResult(
            available=True,
            choices=choices,
            message=(
                f"{len(choices)} Transkripte zu {symbol_or_id}. "
                "Kanonisches und längstes sind gekennzeichnet."
            ),
        )

    except (httpx.HTTPError, OSError, KeyError, ValueError) as error:
        if cached:
            return FetchResult(
                available=True, target=cached, from_cache=True,
                message=f"Aus dem Zwischenspeicher — {OFFLINE_HINT}",
            )
        return FetchResult(available=False, message=f"{OFFLINE_HINT} ({error.__class__.__name__})")


def fetch_ncbi(accession: str) -> FetchResult:
    """NCBI E-utilities.

    Kennmail und Werkzeugname werden mitgeschickt, wenn sie in der `.env`
    stehen — NCBI bittet darum, um bei Problemen jemanden erreichen zu
    koennen. Die Adresse wird nicht erraten und nicht fest eingebaut.
    """
    import httpx

    cached = read_cache("ncbi", accession)
    base = settings.ncbi_url.rstrip("/")
    params: dict[str, Any] = {"db": "nuccore", "id": accession, "rettype": "gb",
                              "retmode": "text", "tool": "OligoLab"}
    if settings.ncbi_email:
        params["email"] = settings.ncbi_email

    try:
        _throttle("ncbi")
        with httpx.Client(timeout=settings.network_timeout_s) as client:
            response = client.get(f"{base}/efetch.fcgi", params=params)
            response.raise_for_status()
            target = from_genbank(response.text, name=accession)
        target.source = "ncbi"
        target.identifier = accession
        target.fetched_at = _now()
        write_cache(target)
        return FetchResult(available=True, target=target)
    except (httpx.HTTPError, OSError, ValueError) as error:
        if cached:
            return FetchResult(
                available=True, target=cached, from_cache=True,
                message=f"Aus dem Zwischenspeicher — {OFFLINE_HINT}",
            )
        return FetchResult(available=False, message=f"{OFFLINE_HINT} ({error.__class__.__name__})")


def fetch_rnacentral(urs_id: str) -> FetchResult:
    """RNAcentral. Kein Schluessel noetig."""
    import httpx

    cached = read_cache("rnacentral", urs_id)
    base = settings.rnacentral_url.rstrip("/")

    try:
        daten = _get(f"{base}/rna/{urs_id}.json", "rnacentral")
        target = Target(
            name=daten.get("description") or urs_id,
            sequence=normalise(daten["sequence"]),
            source="rnacentral",
            identifier=urs_id,
            fetched_at=_now(),
            description=daten.get("description"),
        )
        write_cache(target)
        return FetchResult(available=True, target=target)
    except (httpx.HTTPError, OSError, KeyError, ValueError) as error:
        if cached:
            return FetchResult(
                available=True, target=cached, from_cache=True,
                message=f"Aus dem Zwischenspeicher — {OFFLINE_HINT}",
            )
        return FetchResult(available=False, message=f"{OFFLINE_HINT} ({error.__class__.__name__})")


FETCHERS = {
    "ensembl": fetch_ensembl,
    "ncbi": fetch_ncbi,
    "rnacentral": fetch_rnacentral,
}
