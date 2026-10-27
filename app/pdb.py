"""Referenzstrukturen (PHASEN.md 6.1).

Strukturen kommen aus drei Quellen, in dieser Reihenfolge:

1. dem lokalen Ablageort `data/structures/`,
2. einer Datei, die der Nutzer selbst einlegt,
3. der RCSB-PDB, falls Netz da ist.

Punkt 3 ist der freiwillige: ohne Netz bleibt alles bedienbar (CLAUDE.md,
Regel 4). Was einmal geholt wurde, bleibt liegen.

Was NICHT hier steht: Methode, Aufloesung, Literatur und die Zuordnung der
Ketten. Die stehen in der Strukturdatei selbst und werden von dort gelesen.
Ein von Hand abgeschriebener Wert waere eine zweite Quelle, die beim ersten
Tippfehler von der ersten abweicht — und niemand merkt es.
"""

from __future__ import annotations

import gzip
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from app.config import settings

# --------------------------------------------------------------- Katalog


@dataclass(frozen=True)
class ReferenceSpec:
    """Ein Eintrag aus `references.yaml` — nur das, was wir selbst wissen."""

    id: str
    title: str
    role: str
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title, "role": self.role, "note": self.note}


def load_references() -> tuple[list[ReferenceSpec], str | None]:
    path = settings.references_path
    if not path.exists():
        return [], None
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    eintraege = [
        ReferenceSpec(
            id=str(entry["id"]).upper(),
            title=str(entry.get("title", entry["id"])),
            role=str(entry.get("role", "unbekannt")),
            note=entry.get("note"),
        )
        for entry in raw.get("references", [])
    ]
    voreinstellung = raw.get("default")
    return eintraege, str(voreinstellung).upper() if voreinstellung else None


# ---------------------------------------------------------------- Ketten

ChainKind = Literal["dna", "rna", "protein", "ion", "wasser", "anderes"]

#: Wie die Restenamen in PDB- und mmCIF-Dateien heissen.
DNA_RESIDUES = {"DA", "DC", "DG", "DT", "DU", "DI"}
RNA_RESIDUES = {"A", "C", "G", "U", "I"}
#: Ionen, die in DNAzym-Strukturen eine Rolle spielen (PHASEN.md 6.3).
ION_RESIDUES = {"MG", "MN", "CA", "ZN", "NA", "K", "PB", "TB", "SR", "BA"}
WATER_RESIDUES = {"HOH", "WAT", "DOD"}


@dataclass
class Chain:
    """Eine Kette der Struktur, mit dem, was sie ist."""

    id: str
    kind: ChainKind
    length: int
    sequence: str
    #: Erste und letzte Restnummer, wie sie in der Datei stehen.
    first: int | None = None
    last: int | None = None
    #: Welche Rolle sie im Modell spielt — vom Zuordner gesetzt.
    role: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "length": self.length,
            "sequence": self.sequence,
            "first": self.first,
            "last": self.last,
            "role": self.role,
        }


@dataclass
class Structure:
    """Eine geladene Struktur samt dem, was die Datei über sich sagt."""

    id: str
    path: Path | None = None
    format: str = "pdb"
    title: str | None = None
    method: str | None = None
    resolution_a: float | None = None
    citation: str | None = None
    chains: list[Chain] = field(default_factory=list)
    ions: list[dict[str, Any]] = field(default_factory=list)
    available: bool = True
    source: str = "cache"
    note: str | None = None

    @property
    def dnazyme_chain(self) -> Chain | None:
        return next((c for c in self.chains if c.role == "dnazyme"), None)

    @property
    def substrate_chain(self) -> Chain | None:
        return next((c for c in self.chains if c.role == "substrate"), None)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": str(self.path) if self.path else None,
            "format": self.format,
            "title": self.title,
            "method": self.method,
            "resolution_a": self.resolution_a,
            "citation": self.citation,
            "chains": [c.as_dict() for c in self.chains],
            "ions": self.ions,
            "available": self.available,
            "source": self.source,
            "note": self.note,
        }


# ------------------------------------------------------------ Dateien

OFFLINE_HINT = (
    "Die RCSB-PDB ist gerade nicht erreichbar. Das ist kein Fehler: OligoLab "
    "rechnet lokal weiter. Eine Strukturdatei lässt sich auch von Hand in "
    "`data/structures/` ablegen oder hochladen — und ohne Referenz baut "
    "OligoLab das Modell als ideale Hybridhelix."
)

#: Anfragen je Sekunde an die RCSB. Bewusst zurueckhaltend.
RATE_LIMIT = 2.0
_last_request: float | None = None


def _throttle() -> None:
    global _last_request
    abstand = 1.0 / RATE_LIMIT
    if _last_request is not None:
        schon = time.monotonic() - _last_request
        if schon < abstand:
            time.sleep(abstand - schon)
    _last_request = time.monotonic()


def _dir() -> Path:
    path = settings.structures_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def cached_path(identifier: str) -> Path | None:
    """Die erste passende Datei im Ablageort — egal in welchem Format."""
    kennung = identifier.upper()
    for endung in (".cif", ".pdb", ".cif.gz", ".pdb.gz"):
        pfad = _dir() / f"{kennung}{endung}"
        if pfad.exists():
            return pfad
    return None


def read_text(path: Path) -> str:
    """Liest auch gepackte Dateien — immer als UTF-8 (CLAUDE.md, Regel 7)."""
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    return path.read_text(encoding="utf-8", errors="replace")


def fetch(identifier: str, prefer: str = "cif") -> Structure:
    """Eine Struktur holen — erst aus dem Ablageort, dann aus dem Netz."""
    kennung = identifier.strip().upper()
    if not re.fullmatch(r"[0-9A-Z]{4}|PDB_[0-9A-Z]{8}", kennung):
        return Structure(
            id=kennung,
            available=False,
            note=(
                "Das ist keine PDB-Kennung. Erwartet werden vier Zeichen wie "
                "`8E9A` — oder eine Datei, die von Hand eingelegt wird."
            ),
        )

    vorhanden = cached_path(kennung)
    if vorhanden is not None:
        struktur = parse_structure(read_text(vorhanden), kennung)
        struktur.path = vorhanden
        struktur.source = "cache"
        return struktur

    import httpx

    endung = "cif" if prefer == "cif" else "pdb"
    url = f"{settings.rcsb_url.rstrip('/')}/{kennung}.{endung}"
    try:
        _throttle()
        with httpx.Client(
            timeout=settings.network_timeout_s,
            headers={"User-Agent": "OligoLab/0.1"},
        ) as client:
            antwort = client.get(url)
            antwort.raise_for_status()
            text = antwort.text
    except Exception as error:  # httpx kennt viele Fehlerarten
        return Structure(
            id=kennung,
            available=False,
            source="netz",
            note=f"{OFFLINE_HINT} ({error.__class__.__name__})",
        )

    ziel = _dir() / f"{kennung}.{endung}"
    ziel.write_text(text, encoding="utf-8")
    struktur = parse_structure(text, kennung)
    struktur.path = ziel
    struktur.source = "netz"
    return struktur


def store_upload(identifier: str, text: str) -> Structure:
    """Eine selbst eingelegte Datei übernehmen."""
    kennung = re.sub(r"[^\w.-]", "_", identifier.strip().upper())[:40] or "EIGEN"
    endung = "cif" if _looks_like_cif(text) else "pdb"
    ziel = _dir() / f"{kennung}.{endung}"
    ziel.write_text(text, encoding="utf-8")
    struktur = parse_structure(text, kennung)
    struktur.path = ziel
    struktur.source = "eigene Datei"
    return struktur


def _looks_like_cif(text: str) -> bool:
    kopf = text[:4000]
    return "_atom_site." in kopf or kopf.lstrip().startswith("data_")


# ------------------------------------------------------------- einlesen


@dataclass
class Atom:
    """Ein Atom — mehr brauchen Messung und Modell nicht."""

    serial: int
    name: str
    residue: str
    chain: str
    residue_number: int
    x: float
    y: float
    z: float
    element: str
    insertion: str = ""
    alt: str = ""


def parse_structure(text: str, identifier: str) -> Structure:
    """Eine PDB- oder mmCIF-Datei einlesen.

    Eigene Lesefunktion statt Biopython: gebraucht werden Koordinaten,
    Kettenzuordnung und drei Kopfzeilen. Biopythons Parser bringt dafuer ein
    ganzes Objektmodell mit und wirft bei krummen Dateien Warnungen, die
    hier nur stoeren.
    """
    if _looks_like_cif(text):
        atome, kopf = _parse_cif(text)
        format_ = "cif"
    else:
        atome, kopf = _parse_pdb(text)
        format_ = "pdb"

    struktur = Structure(id=identifier.upper(), format=format_, **kopf)
    struktur.chains = _chains_from(atome)
    struktur.ions = [
        {
            "residue": a.residue,
            "chain": a.chain,
            "number": a.residue_number,
            "element": a.element,
            "xyz": [a.x, a.y, a.z],
        }
        for a in atome
        if a.residue.strip().upper() in ION_RESIDUES
    ]
    assign_roles(struktur)
    if not struktur.chains:
        struktur.available = False
        struktur.note = "In der Datei steht kein einziges Atom."
    return struktur


def _parse_pdb(text: str) -> tuple[list[Atom], dict[str, Any]]:
    atome: list[Atom] = []
    titel: list[str] = []
    methode: str | None = None
    aufloesung: float | None = None

    for zeile in text.splitlines():
        kennung = zeile[:6]
        if kennung in ("ATOM  ", "HETATM"):
            try:
                atome.append(
                    Atom(
                        serial=int(zeile[6:11]),
                        name=zeile[12:16].strip(),
                        alt=zeile[16].strip(),
                        residue=zeile[17:20].strip(),
                        chain=zeile[21].strip() or "A",
                        residue_number=int(zeile[22:26]),
                        insertion=zeile[26].strip(),
                        x=float(zeile[30:38]),
                        y=float(zeile[38:46]),
                        z=float(zeile[46:54]),
                        element=(zeile[76:78].strip() or zeile[12:14].strip()).upper(),
                    )
                )
            except (ValueError, IndexError):
                # Eine krumme Zeile macht die Datei nicht unbrauchbar.
                continue
        elif kennung == "TITLE ":
            titel.append(zeile[10:].strip())
        elif kennung == "EXPDTA":
            methode = zeile[10:].strip() or None
        elif zeile.startswith("REMARK   2 RESOLUTION."):
            treffer = re.search(r"([\d.]+)\s*ANGSTROM", zeile)
            if treffer:
                aufloesung = float(treffer.group(1))

    return atome, {
        "title": " ".join(t for t in titel if t) or None,
        "method": methode,
        "resolution_a": aufloesung,
        "citation": None,
    }


def _cif_value(text: str, key: str) -> str | None:
    """Einen einzelnen Wert aus einer mmCIF-Datei ziehen."""
    treffer = re.search(rf"^{re.escape(key)}\s+(.+)$", text, re.MULTILINE)
    if not treffer:
        return None
    wert = treffer.group(1).strip().strip("'\"")
    return None if wert in ("?", ".") else wert


def _parse_cif(text: str) -> tuple[list[Atom], dict[str, Any]]:
    atome: list[Atom] = []
    spalten: list[str] = []
    im_block = False

    for zeile in text.splitlines():
        blank = zeile.strip()
        if blank.startswith("_atom_site."):
            spalten.append(blank.split(".", 1)[1].split()[0])
            im_block = True
            continue
        if im_block:
            if not blank or blank.startswith("#") or blank.startswith("_"):
                if spalten and atome:
                    break
                if blank.startswith("loop_") or not blank:
                    continue
                break
            felder = _split_cif_row(blank)
            if len(felder) != len(spalten):
                continue
            werte = dict(zip(spalten, felder))
            try:
                atome.append(
                    Atom(
                        serial=int(werte.get("id", "0")),
                        name=werte.get("label_atom_id", "").strip("'\""),
                        alt=(werte.get("label_alt_id") or ".").replace(".", ""),
                        residue=werte.get("label_comp_id", "").strip(),
                        # Die Ketten-Kennung der Veroeffentlichung ist die,
                        # die der Nutzer im Bild sieht.
                        chain=(
                            werte.get("auth_asym_id")
                            or werte.get("label_asym_id")
                            or "A"
                        ).strip(),
                        residue_number=int(
                            float(
                                werte.get("auth_seq_id")
                                or werte.get("label_seq_id")
                                or 0
                            )
                        ),
                        x=float(werte["Cartn_x"]),
                        y=float(werte["Cartn_y"]),
                        z=float(werte["Cartn_z"]),
                        element=werte.get("type_symbol", "").strip().upper(),
                    )
                )
            except (ValueError, KeyError):
                continue

    aufloesung = _cif_value(text, "_refine.ls_d_res_high") or _cif_value(
        text, "_em_3d_reconstruction.resolution"
    )
    zitat = _cif_value(text, "_citation.title")
    return atome, {
        "title": _cif_value(text, "_struct.title"),
        "method": _cif_value(text, "_exptl.method"),
        "resolution_a": float(aufloesung) if aufloesung else None,
        "citation": zitat,
    }


def _split_cif_row(zeile: str) -> list[str]:
    """Eine mmCIF-Zeile zerlegen, Anführungszeichen beachtet."""
    felder: list[str] = []
    rest = zeile.strip()
    while rest:
        if rest[0] in "'\"":
            zeichen = rest[0]
            ende = rest.find(zeichen, 1)
            if ende < 0:
                felder.append(rest[1:])
                break
            felder.append(rest[1:ende])
            rest = rest[ende + 1 :].lstrip()
        else:
            stueck, _, rest = rest.partition(" ")
            felder.append(stueck)
            rest = rest.lstrip()
    return felder


def _kind_of(residues: list[str]) -> ChainKind:
    namen = [r.strip().upper() for r in residues]
    if all(n in WATER_RESIDUES for n in namen):
        return "wasser"
    if all(n in ION_RESIDUES for n in namen):
        return "ion"
    ohne_wasser = [n for n in namen if n not in WATER_RESIDUES]
    if not ohne_wasser:
        return "wasser"
    dna = sum(1 for n in ohne_wasser if n in DNA_RESIDUES)
    rna = sum(1 for n in ohne_wasser if n in RNA_RESIDUES)
    if dna and dna >= rna:
        return "dna"
    if rna:
        return "rna"
    if any(len(n) == 3 and n.isalpha() for n in ohne_wasser):
        return "protein"
    return "anderes"


ONE_LETTER = {
    "DA": "A", "DC": "C", "DG": "G", "DT": "T", "DU": "U", "DI": "I",
    "A": "A", "C": "C", "G": "G", "U": "U", "I": "I", "T": "T",
}


def _chains_from(atome: list[Atom]) -> list[Chain]:
    """Je Kette: Art, Laenge und Sequenz — aus den Resten, nicht geraten."""
    nach_kette: dict[str, list[tuple[int, str]]] = {}
    for atom in atome:
        reste = nach_kette.setdefault(atom.chain, [])
        schluessel = (atom.residue_number, atom.residue.strip().upper())
        if not reste or reste[-1] != schluessel:
            if schluessel not in reste:
                reste.append(schluessel)

    ketten: list[Chain] = []
    for kennung, reste in nach_kette.items():
        geordnet = sorted(set(reste))
        namen = [name for _, name in geordnet]
        art = _kind_of(namen)
        if art in ("wasser",):
            continue
        sequenz = "".join(ONE_LETTER.get(name, "") for name in namen)
        ketten.append(
            Chain(
                id=kennung,
                kind=art,
                length=len(geordnet),
                sequence=sequenz,
                first=geordnet[0][0] if geordnet else None,
                last=geordnet[-1][0] if geordnet else None,
            )
        )
    return sorted(ketten, key=lambda c: c.id)


def assign_roles(structure: Structure) -> None:
    """DNAzym-Strang und RNA-Substrat zuordnen (PHASEN.md 6.1).

    Entschieden wird nach der Art der Kette, nicht nach ihrem Buchstaben:
    die laengste DNA-Kette ist der Strang, die laengste RNA-Kette das
    Substrat. Gibt es beides nicht, bleibt die Rolle offen — geraten wird
    nicht.
    """
    dna = [c for c in structure.chains if c.kind == "dna"]
    rna = [c for c in structure.chains if c.kind == "rna"]
    if dna:
        max(dna, key=lambda c: c.length).role = "dnazyme"
    if rna:
        max(rna, key=lambda c: c.length).role = "substrate"

    if not dna or not rna:
        fehlt = "DNA-Kette" if not dna else "RNA-Kette"
        hinweis = (
            f"In dieser Struktur steckt keine {fehlt}. Als Referenz für ein "
            "DNAzym mit Substrat ist sie damit nur eingeschränkt brauchbar."
        )
        structure.note = f"{structure.note} {hinweis}" if structure.note else hinweis


def atoms_of(text: str) -> list[Atom]:
    """Nur die Atome — fuer Modell und Messung."""
    return (_parse_cif(text) if _looks_like_cif(text) else _parse_pdb(text))[0]
