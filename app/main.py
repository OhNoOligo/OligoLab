"""FastAPI-Endpunkte.

Alles laeuft lokal; es gibt keinen Schluessel und keinen Aufruf nach aussen
(CLAUDE.md, Regel 4). Die Oberflaeche liegt unter `frontend/` und wird im
Entwicklungsbetrieb von Vite ausgeliefert; ist `frontend/dist` gebaut, liefert
dieser Dienst sie gleich mit aus.

Grundsatz der Endpunkte: sie nehmen den SEQUENZTEXT und geben die Rechnung
zurueck, inklusive aller Befunde. Fehler in der Sequenz sind kein HTTP-Fehler,
sondern Teil der Antwort — die Oberflaeche soll jedes unbekannte Zeichen
markieren koennen, statt nur eine Fehlermeldung zu zeigen.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field, field_validator

from app import (
    __version__,
    critical,
    dnazyme,
    extinction,
    fold,
    library,
    loading,
    mass,
    mass_exact,
    notation,
    synthesis,
    target as target_module,
)
from app import design as design_module
from app import fold_target
from app import melting as melting_module
from app import scan as scan_module
from app.config import PROJECT_ROOT, settings
from app.registry import (
    get_registry,
    remove_monomer_override,
    save_modification,
    save_monomer,
)

app = FastAPI(
    title="OligoLab",
    version=__version__,
    description="Rechnen und Visualisieren für modifizierte DNAzyme (10-23).",
)

# Nur fuer den Entwicklungsbetrieb: Vite laeuft auf einem anderen Port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------- Modelle


def _require_name(value: str) -> str:
    """Ein Name darf nicht leer sein.

    Gespeichert wird per Name: ein leerer Name liesse alle namenlosen
    Eintraege zu einem verschmelzen, und in der Bibliothek waeren sie weder
    auseinanderzuhalten noch zu finden.
    """
    stripped = value.strip()
    if not stripped:
        raise ValueError("Der Name darf nicht leer sein.")
    return stripped


class SequenceRequest(BaseModel):
    sequence: str = Field(default="", description="Sequenz in Synthi-Sprache")
    name: str | None = None
    notes: str | None = None


class SynthesisRequest(SequenceRequest):
    coupling_volume_ml: float = Field(default=0.12, gt=0)
    reserve_fraction: float = Field(default=0.10, ge=0)
    syntheses: int = Field(default=1, ge=1)


class LadderRequest(SequenceRequest):
    # Nach oben begrenzt: mehr Ladungen als Phosphate kann ein Oligo nicht
    # tragen, und 100 liegt weit ueber allem, was je sinnvoll ist.
    charge_min: int = Field(default=2, ge=1, le=100)
    charge_max: int = Field(default=15, ge=1, le=100)
    basis: Literal["average", "monoisotopic"] = "average"


class TranslateRequest(SequenceRequest):
    to: Literal["rna", "dna"] = "rna"


class PageLoadingRequest(BaseModel):
    n_loading_pmol: float = Field(gt=0)
    n_stock_nmol: float = Field(ge=0)
    v_stock_ul: float = Field(gt=0)
    water_total_ul: float = Field(default=loading.PAGE_TOTAL_WATER_UL, gt=0)
    buffer_ul: float = Field(default=loading.PAGE_BUFFER_UL, ge=0)
    factor: float = Field(default=loading.PAGE_FACTOR, gt=0)


class LcmsLoadingRequest(BaseModel):
    n_injection_pmol: float = Field(gt=0)
    n_stock_nmol: float = Field(ge=0)
    v_stock_ul: float = Field(gt=0)
    v_sample_ul: float = Field(gt=0)
    v_injection_ul: float = Field(gt=0)


class OdRequest(BaseModel):
    eps260: float = Field(gt=0)
    molar_mass: float = Field(gt=0)
    # Eine negative Stoffmenge gibt es nicht.
    od: float | None = Field(default=None, ge=0)
    nmol: float | None = Field(default=None, ge=0)
    microgram: float | None = Field(default=None, ge=0)


class AbsorbanceRequest(BaseModel):
    eps260: float = Field(gt=0)
    a260: float | None = None
    conc_molar: float | None = None
    path_cm: float = Field(default=1.0, gt=0)


class OligoSaveRequest(SequenceRequest):
    name: str

    _check_name = field_validator("name")(_require_name)


class SampleSaveRequest(BaseModel):
    name: str
    n_stock_nmol: float = Field(ge=0)
    v_stock_ul: float = Field(gt=0)
    notes: str | None = None

    _check_name = field_validator("name")(_require_name)


class MonomerWriteRequest(BaseModel):
    """Eigenen Baustein anlegen oder vorhandenen aendern.

    Was `None` bleibt, wird nicht geschrieben — so ueberlagert eine Aenderung
    nur die Felder, die wirklich gemeint sind.
    """

    code: str
    name: str | None = None
    typ: str | None = None
    mass_residue: float | None = None
    mass_amidite: float | None = None
    conc_molar: float | None = None
    formula_residue: str | None = None
    eps260: float | None = None
    base_parent: str | None = None
    core_tested: Literal["ja", "nein", "unbekannt"] | None = None
    smiles: str | None = None
    quelle: str | None = None


class ModificationWriteRequest(BaseModel):
    code: str
    name: str | None = None
    mass_diff: float | None = None
    scope: Literal["monomer", "linkage", "terminus"] = "monomer"
    klasse: str | None = None
    formula: str | None = None
    eps260: float | None = None
    base_parent: str | None = None
    counts_as_base: bool = True
    core_tested: Literal["ja", "nein", "unbekannt"] | None = None
    quelle: str | None = None


# ------------------------------------------------------------- Hilfsmittel


def _monomer_payload(monomer) -> dict[str, Any]:
    """Ein Monomer so, wie die Sequenzkarte es braucht."""
    residue = monomer.mass_residue
    return {
        "position": monomer.position,
        "code": monomer.code,
        "source": monomer.source,
        "name": monomer.spec.name,
        "typ": monomer.spec.typ,
        "klasse": monomer.klasse,
        "base_parent": monomer.base_parent,
        "core_tested": monomer.core_tested,
        "modifications": [
            {"code": m.code, "name": m.name, "klasse": m.klasse}
            for m in monomer.modifications
        ],
        "mass_residue": residue.as_dict(2),
        "span": {"start": monomer.span[0], "end": monomer.span[1]},
        "deviates_from_excel": monomer.spec.deviates_from_excel,
    }


def _oligo_payload(oligo) -> dict[str, Any]:
    return {
        "length": oligo.length,
        "monomers": [_monomer_payload(m) for m in oligo.monomers],
        "linkages": [
            {
                "position": l.position,
                "kind": l.kind,
                "modification": None if l.modification is None else l.modification.code,
            }
            for l in oligo.linkages
        ],
        "conjugates": [
            {
                "code": c.code,
                "name": c.spec.name,
                "attach": c.attach,
                "after_position": c.after_position,
                "needs_review": c.spec.needs_review,
            }
            for c in oligo.conjugates
        ],
        "code_counts": oligo.code_counts(),
        "base_counts": oligo.base_counts(),
        "phosphorothioates": oligo.phosphorothioate_count(),
        "modified_positions": oligo.modified_positions(),
    }


# ----------------------------------------------------------------- Endpunkte


@app.get("/api/health")
def health() -> dict[str, Any]:
    registry = get_registry()
    return {
        "status": "ok",
        "version": __version__,
        "monomers": len(registry.monomers),
        "modifications": len(registry.modifications),
        # Externe Programme gehoeren zu spaeteren Phasen. Fehlen sie, bleibt
        # die App voll bedienbar (Regel 4).
        "melting_dir": settings.melting_dir or None,
        "orca_exe": settings.orca_exe or None,
    }


@app.post("/api/parse")
def parse_sequence(request: SequenceRequest) -> dict[str, Any]:
    """Sequenz zerlegen und ALLE Befunde zurueckgeben."""
    registry = get_registry()
    oligo, problems = notation.analyse(request.sequence, registry, request.name)
    return {
        "oligo": _oligo_payload(oligo),
        "problems": [p.as_dict() for p in problems],
        "grouped": notation.to_string(oligo, group=3),
    }


@app.post("/api/summary")
def summary(request: SequenceRequest) -> dict[str, Any]:
    """Das Noetigste fuer die Kopfzeile: Laenge, Masse, Zahl der Befunde.

    Eigener Endpunkt, damit die immer sichtbare Kopfzeile nicht bei jedem
    Tastendruck die volle Rechnung samt Isotopenmuster anstossen muss. Und
    damit die Masse dort aus derselben Quelle kommt wie im Steckbrief — eine
    im Zustand mitgefuehrte Kopie liefe irgendwann auseinander.
    """
    registry = get_registry()
    oligo, problems = notation.analyse(request.sequence, registry, request.name)
    mass_value = None
    if not problems and oligo.length:
        mass_value = mass.compute(oligo, registry).fully_deprotected.value
    return {
        "length": oligo.length,
        "mass_fully_deprotected": mass_value,
        "problems": len(problems),
        "phosphorothioates": oligo.phosphorothioate_count(),
        "conjugates": len(oligo.conjugates),
    }


@app.post("/api/profile")
def profile(request: SequenceRequest) -> dict[str, Any]:
    """Alles, was die Seite `Steckbrief` braucht, in einem Aufruf."""
    registry = get_registry()
    oligo, problems = notation.analyse(request.sequence, registry, request.name)
    oligo.notes = request.notes

    payload: dict[str, Any] = {
        "oligo": _oligo_payload(oligo),
        "problems": [p.as_dict() for p in problems],
        "grouped": notation.to_string(oligo, group=3),
    }

    if problems or oligo.length == 0:
        # Mit einer fehlerhaften Sequenz wird nicht gerechnet. Die Oberflaeche
        # zeigt die Befunde; alte Zahlen stehen zu lassen waere schlimmer.
        payload["mass"] = None
        payload["exact"] = None
        payload["comparison"] = None
        payload["extinction"] = None
        payload["synthesis"] = None
        return payload

    mass_result = mass.compute(oligo, registry)
    exact_result = mass_exact.compute(oligo, registry=registry)
    comparison = mass_exact.compare(oligo, registry)
    extinction_result = extinction.compute(oligo, registry)
    consumption = synthesis.compute(oligo, registry=registry)

    payload["mass"] = mass_result.as_dict()
    payload["exact"] = exact_result.as_dict()
    payload["comparison"] = comparison.as_dict()
    payload["extinction"] = extinction_result.as_dict()
    payload["synthesis"] = consumption.as_dict()
    payload["charge_ladder"] = mass_exact.charge_ladder(exact_result.average.value)
    return payload


class StrandRequest(SequenceRequest):
    # Das Homodimer ist die teuerste Teilrechnung; wer nur die Karte sehen
    # will, kann sie abschalten.
    with_homodimer: bool = True


@app.post("/api/strand")
def strand(request: StrandRequest) -> dict[str, Any]:
    """Alles, was die Seite `Strang` braucht: Bauteile, Faltung, Befunde.

    Eine fehlerhafte Sequenz ist auch hier kein HTTP-Fehler, sondern Teil der
    Antwort — die Oberflaeche soll jede unklare Stelle markieren koennen.
    """
    registry = get_registry()
    oligo, problems = notation.analyse(request.sequence, registry, request.name)

    payload: dict[str, Any] = {
        "oligo": _oligo_payload(oligo),
        "problems": [p.as_dict() for p in problems],
    }

    if problems or oligo.length == 0:
        payload["parts"] = None
        payload["folding"] = None
        payload["critical"] = None
        return payload

    parts = dnazyme.detect_parts(oligo, registry)
    folding = fold.compute(oligo, registry, with_homodimer=request.with_homodimer)
    findings = critical.compute(oligo, parts, folding, registry)

    payload["parts"] = parts.as_dict()
    payload["folding"] = folding.as_dict()
    payload["critical"] = findings.as_dict()
    return payload


class TargetTextRequest(BaseModel):
    text: str
    name: str | None = None
    format: Literal["auto", "plain", "fasta", "genbank"] = "auto"


class TargetFetchRequest(BaseModel):
    source: Literal["ensembl", "ncbi", "rnacentral"]
    identifier: str
    species: str = "homo_sapiens"


class TargetFoldRequest(BaseModel):
    sequence: str
    start: int | None = Field(default=None, ge=1)
    end: int | None = Field(default=None, ge=1)


class AccessibilityRequest(TargetFoldRequest):
    probe_length: int = Field(default=fold_target.DEFAULT_PROBE_LENGTH, ge=1, le=200)
    window: int = Field(default=fold_target.DEFAULT_WINDOW, ge=2, le=2000)
    max_span: int = Field(default=fold_target.DEFAULT_MAX_SPAN, ge=2, le=2000)


class UpRequest(BaseModel):
    target_sequence: str
    site_start: int = Field(ge=1)
    site_end: int = Field(ge=1)
    oligo_sequence: str
    temperature_c: float = 37.0


class TargetSaveRequest(BaseModel):
    name: str
    sequence: str
    source: str = "Direkteingabe"
    identifier: str | None = None
    organism: str | None = None
    description: str | None = None
    regions: list[dict[str, Any]] = Field(default_factory=list)
    fetched_at: str | None = None

    _check_name = field_validator("name")(_require_name)


class ConditionsRequest(BaseModel):
    """Die Puffereinstellungen aus der Kopfzeile."""

    oligo_conc_nm: float = 1000.0
    na_mm: float = 50.0
    k_mm: float = 0.0
    tris_mm: float = 10.0
    mg_mm: float = 2.0
    temperature_c: float = 37.0

    def to_conditions(self) -> melting_module.Conditions:
        return melting_module.Conditions(
            oligo_conc_nm=self.oligo_conc_nm,
            na_mm=self.na_mm,
            k_mm=self.k_mm,
            tris_mm=self.tris_mm,
            mg_mm=self.mg_mm,
            temperature_c=self.temperature_c,
        )


class MeltingRequest(BaseModel):
    sequence: str
    conditions: ConditionsRequest = Field(default_factory=ConditionsRequest)


class ScanRequest(BaseModel):
    sequence: str
    start: int | None = None
    end: int | None = None
    include_poor: bool = False
    #: Falten und Zugaenglichkeit mitrechnen. Ohne das gibt es die Junktionen
    #: samt Guete, nur ohne die strukturellen Angaben — und das ist schnell.
    with_structure: bool = True
    probe_length: int = 15


class DesignSettingsRequest(BaseModel):
    arm5_length: int = Field(default=9, ge=5, le=20)
    arm3_length: int = Field(default=9, ge=5, le=20)
    core_id: str | None = None
    arm_dg_target: float = -20.0
    max_imbalance: float = Field(default=4.0, ge=0)
    self_fold_limit: float = -2.0
    weight_junction: float = Field(default=0.30, ge=0)
    weight_arm_dg: float = Field(default=0.25, ge=0)
    weight_balance: float = Field(default=0.15, ge=0)
    weight_self_fold: float = Field(default=0.15, ge=0)
    weight_accessibility: float = Field(default=0.15, ge=0)
    include_poor_junctions: bool = False

    def to_settings(self) -> design_module.DesignSettings:
        return design_module.DesignSettings(**self.model_dump())


class DesignRequest(ScanRequest):
    settings: DesignSettingsRequest = Field(default_factory=DesignSettingsRequest)
    conditions: ConditionsRequest = Field(default_factory=ConditionsRequest)
    limit: int = Field(default=200, ge=1, le=2000)


class ModifyRequest(BaseModel):
    sequence: str
    pattern: str
    #: Erste und letzte Position des katalytischen Kerns, 1-basiert.
    core_start: int | None = None
    core_end: int | None = None
    count: int = Field(default=3, ge=1, le=20)
    position: int | None = None
    code: str | None = None
    #: Die ausdrueckliche Bestaetigung fuer einen Eingriff im Kern
    #: (CLAUDE.md, Regel 6).
    allow_core: bool = False
    #: Fuer den Vorher-Nachher-Vergleich.
    arm5_length: int = 9
    core_length: int = 15
    conditions: ConditionsRequest = Field(default_factory=ConditionsRequest)


class CompareRequest(BaseModel):
    before: str
    after: str
    arm5_length: int = 9
    core_length: int = 15
    conditions: ConditionsRequest = Field(default_factory=ConditionsRequest)


@app.post("/api/target/read")
def target_read(request: TargetTextRequest) -> dict[str, Any]:
    """Text als Zielsequenz einlesen.

    `auto` erkennt FASTA am `>` und GenBank am `LOCUS`. Ein unbekanntes
    Zeichen ist ein Fehler mit Positionsangabe (CLAUDE.md, Regel 5).
    """
    text = request.text
    fmt = request.format
    if fmt == "auto":
        gestrafft = text.lstrip()
        if gestrafft.startswith(">"):
            fmt = "fasta"
        elif gestrafft.startswith("LOCUS"):
            fmt = "genbank"
        else:
            fmt = "plain"

    try:
        if fmt == "fasta":
            result = target_module.from_fasta(text, request.name)
        elif fmt == "genbank":
            result = target_module.from_genbank(text, request.name)
        else:
            result = target_module.from_text(text, request.name or "Direkteingabe")
    except target_module.TargetError as error:
        raise HTTPException(
            status_code=422,
            detail={
                "message": str(error),
                "position": error.position,
                "character": error.character,
            },
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return {"target": result.as_dict(), "detected_format": fmt}


@app.post("/api/target/fetch")
def target_fetch(request: TargetFetchRequest) -> dict[str, Any]:
    """Aus Ensembl, NCBI oder RNAcentral holen.

    Ein fehlgeschlagener Abruf ist kein HTTP-Fehler: OligoLab bleibt ohne
    Netz voll bedienbar, und die Antwort sagt das ruhig (CLAUDE.md, Regel 4).
    """
    if request.source == "ensembl":
        result = target_module.fetch_ensembl(request.identifier, request.species)
    elif request.source == "ncbi":
        result = target_module.fetch_ncbi(request.identifier)
    else:
        result = target_module.fetch_rnacentral(request.identifier)
    return result.as_dict()


@app.post("/api/target/fold")
def target_fold(request: TargetFoldRequest) -> dict[str, Any]:
    try:
        sequence = target_module.normalise(request.sequence)
    except target_module.TargetError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return fold_target.fold_region(sequence, request.start, request.end).as_dict()


@app.post("/api/target/accessibility")
def target_accessibility(request: AccessibilityRequest) -> dict[str, Any]:
    try:
        sequence = target_module.normalise(request.sequence)
    except target_module.TargetError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    try:
        return fold_target.accessibility(
            sequence,
            start=request.start,
            end=request.end,
            probe_length=request.probe_length,
            window=request.window,
            max_span=request.max_span,
        ).as_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/target/up")
def target_up(request: UpRequest) -> dict[str, Any]:
    try:
        sequence = target_module.normalise(request.target_sequence)
    except target_module.TargetError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    try:
        return fold_target.rnaup(
            sequence,
            request.site_start,
            request.site_end,
            request.oligo_sequence,
            request.temperature_c,
        ).as_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


# ------------------------------------------------- Phase 5: Entwurf


@app.post("/api/melting")
def melting_route(request: MeltingRequest) -> dict[str, Any]:
    """Tm und Thermodynamik eines Arms (PHASEN.md 5.1).

    Nimmt Synthi-Sprache, damit ein modifizierter Arm dieselbe Rechnung
    durchlaeuft — die Naeherung ueber das natuerliche Analogon steht dann in
    `approximated`.
    """
    try:
        oligo = notation.parse(request.sequence, get_registry())
    except notation.NotationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return melting_module.compute(oligo, request.conditions.to_conditions()).as_dict()


def _normalised_target(sequence: str) -> str:
    try:
        return target_module.normalise(sequence)
    except target_module.TargetError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _structure_for(
    sequence: str, request: ScanRequest
) -> tuple[Any | None, Any | None]:
    """Faltung und Zugaenglichkeitsprofil — oder zweimal None."""
    if not request.with_structure:
        return None, None
    faltung = fold_target.fold_region(sequence, request.start, request.end)
    profil = fold_target.accessibility(
        sequence,
        start=request.start,
        end=request.end,
        probe_length=request.probe_length,
    )
    return faltung, profil


@app.post("/api/scan")
def scan_route(request: ScanRequest) -> dict[str, Any]:
    """Alle Purin-Pyrimidin-Junktionen im gewaehlten Bereich (PHASEN.md 5.2)."""
    sequence = _normalised_target(request.sequence)
    try:
        faltung, profil = _structure_for(sequence, request)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    ergebnis = scan_module.scan(
        sequence,
        start=request.start,
        end=request.end,
        folding=faltung,
        accessibility=profil,
        include_poor=request.include_poor,
    )
    return {
        "scan": ergebnis.as_dict(),
        "folding": faltung.as_dict() if faltung else None,
        "accessibility": profil.as_dict() if profil else None,
    }


def _design(request: DesignRequest) -> tuple[Any, Any, Any, str]:
    sequence = _normalised_target(request.sequence)
    einstellungen = request.settings.to_settings()
    einstellungen.include_poor_junctions = request.include_poor
    try:
        faltung, profil = _structure_for(sequence, request)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    spaltstellen = scan_module.scan(
        sequence,
        start=request.start,
        end=request.end,
        folding=faltung,
        accessibility=profil,
        include_poor=request.include_poor,
    )
    ergebnis = design_module.design(
        sequence,
        spaltstellen,
        settings=einstellungen,
        conditions=request.conditions.to_conditions(),
        accessibility=profil,
        limit=request.limit,
    )
    return ergebnis, spaltstellen, profil, sequence


@app.post("/api/design")
def design_route(request: DesignRequest) -> dict[str, Any]:
    """Kandidaten bauen, bewerten und ordnen (PHASEN.md 5.3).

    Gibt das Zugaenglichkeitsprofil mit zurueck, damit die Entwurfsseite die
    Kurve und die Kandidatenmarken aus einer Antwort zeichnen kann.
    """
    ergebnis, spaltstellen, profil, _ = _design(request)
    return {
        **ergebnis.as_dict(),
        "scan": spaltstellen.as_dict(),
        "accessibility": profil.as_dict() if profil else None,
        "conditions": request.conditions.to_conditions().as_dict(),
    }


@app.post("/api/design/candidates.csv", response_class=PlainTextResponse)
def design_csv(request: DesignRequest) -> str:
    """Die Kandidatentabelle als CSV (PHASEN.md 5.6)."""
    ergebnis, _, _, _ = _design(request)
    spalten = [
        "Rang", "Position", "Junktion", "Güte", "Arm 5'", "Arm 3'",
        "dG 5' (kcal/mol)", "dG 3' (kcal/mol)", "Summe dG", "Ungleichgewicht",
        "Tm 5' (°C)", "Tm 3' (°C)", "Eigenfaltung (kcal/mol)",
        "Zugänglichkeit", "Punktzahl", "Ampel", "Sequenz",
    ]
    zeilen = [";".join(spalten)]

    def z(wert: Any, stellen: int = 2) -> str:
        if wert is None:
            return ""
        if isinstance(wert, float):
            # Deutsches Dezimalkomma, damit Excel die Zahlen als Zahlen liest.
            return f"{wert:.{stellen}f}".replace(".", ",")
        return str(wert)

    for rang, kandidat in enumerate(ergebnis.candidates, start=1):
        dg5 = kandidat.tm5.dg.value if kandidat.tm5 and kandidat.tm5.dg else None
        dg3 = kandidat.tm3.dg.value if kandidat.tm3 and kandidat.tm3.dg else None
        tm5 = kandidat.tm5.tm.value if kandidat.tm5 and kandidat.tm5.tm else None
        tm3 = kandidat.tm3.tm.value if kandidat.tm3 and kandidat.tm3.tm else None
        zeilen.append(
            ";".join(
                [
                    z(rang), z(kandidat.site.position), kandidat.site.junction,
                    kandidat.site.quality, kandidat.arm5, kandidat.arm3,
                    z(dg5), z(dg3), z(kandidat.arm_dg_sum), z(kandidat.imbalance),
                    z(tm5), z(tm3),
                    z(
                        kandidat.self_fold.mfe.value
                        if kandidat.self_fold and kandidat.self_fold.mfe
                        else None
                    ),
                    z(kandidat.site.accessibility, 4),
                    z(kandidat.score, 4), kandidat.rating or "",
                    kandidat.sequence,
                ]
            )
        )
    kopf = f"# {design_module.DISCLAIMER}"
    return "\n".join([kopf, *zeilen]) + "\n"


@app.post("/api/modify")
def modify_route(request: ModifyRequest) -> dict[str, Any]:
    """Ein Muster auf einen Strang legen, mit Vorher-Nachher (PHASEN.md 5.5).

    Ein Eingriff im katalytischen Kern wird blockiert, solange er nicht
    ausdruecklich bestaetigt ist (CLAUDE.md, Regel 6). Das ist KEIN
    HTTP-Fehler — die Oberflaeche soll die Warnung zeigen und nachfragen
    koennen.
    """
    kern = None
    if request.core_start is not None and request.core_end is not None:
        kern = (request.core_start, request.core_end)
    bedingungen = request.conditions.to_conditions()
    try:
        ergebnis = design_module.apply_pattern(
            request.sequence,
            request.pattern,
            core_range=kern,
            count=request.count,
            position=request.position,
            code=request.code,
            allow_core=request.allow_core,
        )
    except (ValueError, notation.NotationError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    antwort: dict[str, Any] = {"modification": ergebnis.as_dict()}
    if not ergebnis.blocked:
        try:
            antwort["before"] = design_module.snapshot(
                request.sequence, request.arm5_length, request.core_length,
                conditions=bedingungen,
            ).as_dict()
            antwort["after"] = design_module.snapshot(
                ergebnis.sequence, request.arm5_length, request.core_length,
                conditions=bedingungen,
            ).as_dict()
        except notation.NotationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
    return antwort


@app.post("/api/compare")
def compare_route(request: CompareRequest) -> dict[str, Any]:
    """Zwei Straenge durch dieselbe Rechnung schicken (PHASEN.md 5.5)."""
    bedingungen = request.conditions.to_conditions()
    try:
        vorher = design_module.snapshot(
            request.before, request.arm5_length, request.core_length,
            conditions=bedingungen,
        )
        nachher = design_module.snapshot(
            request.after, request.arm5_length, request.core_length,
            conditions=bedingungen,
        )
    except notation.NotationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"before": vorher.as_dict(), "after": nachher.as_dict()}


@app.get("/api/design/patterns")
def design_patterns() -> dict[str, Any]:
    return {
        "patterns": [
            {"id": schluessel, "label": text}
            for schluessel, text in design_module.PATTERNS.items()
        ],
        "disclaimer": design_module.DISCLAIMER,
    }


@app.get("/api/library/targets")
def targets_list(q: str | None = Query(default=None)) -> dict[str, Any]:
    import json as _json

    return {
        "total": library.count_targets(q),
        "targets": [
            {
                "id": r.id,
                "name": r.name,
                "sequence": r.sequence,
                "length": r.length,
                "source": r.source,
                "identifier": r.identifier,
                "organism": r.organism,
                "description": r.description,
                "regions": _json.loads(r.regions_json) if r.regions_json else [],
                "fetched_at": r.fetched_at,
                "updated_at": r.updated_at.isoformat(timespec="seconds"),
            }
            for r in library.list_targets(q)
        ],
    }


@app.post("/api/library/targets")
def targets_save(request: TargetSaveRequest) -> dict[str, Any]:
    import json as _json

    try:
        sequence = target_module.normalise(request.sequence)
    except target_module.TargetError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    record = library.save_target(
        name=request.name,
        sequence=sequence,
        source=request.source,
        identifier=request.identifier,
        organism=request.organism,
        description=request.description,
        regions_json=_json.dumps(request.regions) if request.regions else None,
        fetched_at=request.fetched_at,
    )
    return {"id": record.id, "name": record.name}


@app.delete("/api/library/targets/{record_id}")
def targets_delete(record_id: int) -> dict[str, Any]:
    if not library.delete_target(record_id):
        raise HTTPException(status_code=404, detail="Ziel nicht gefunden.")
    return {"deleted": record_id}


@app.get("/api/cores")
def list_cores() -> dict[str, Any]:
    """Die katalytischen Kerne aus `data/cores.yaml`."""
    return {"cores": [core.as_dict() for core in dnazyme.load_cores(get_registry())]}


@app.post("/api/translate")
def translate(request: TranslateRequest) -> dict[str, Any]:
    """DNA <-> Synthi-RNA, wie im Excel."""
    registry = get_registry()
    oligo, problems = notation.analyse(request.sequence, registry)
    if problems:
        return {
            "sequence": None,
            "problems": [p.as_dict() for p in problems],
            "untranslated": [],
        }
    translated, untouched = notation.translate(oligo, request.to, registry)
    return {
        "sequence": notation.to_string(translated, group=3),
        "problems": [],
        "untranslated": untouched,
    }


@app.post("/api/synthesis")
def synthesis_endpoint(request: SynthesisRequest) -> dict[str, Any]:
    registry = get_registry()
    try:
        oligo = notation.parse(request.sequence, registry)
    except notation.NotationError as error:
        raise HTTPException(status_code=422, detail=error.problem.as_dict()) from error
    table = synthesis.compute(
        oligo,
        coupling_volume_ml=request.coupling_volume_ml,
        reserve_fraction=request.reserve_fraction,
        syntheses=request.syntheses,
        registry=registry,
    )
    return table.as_dict()


@app.post("/api/ms/ladder")
def ms_ladder(request: LadderRequest) -> dict[str, Any]:
    registry = get_registry()
    try:
        oligo = notation.parse(request.sequence, registry)
    except notation.NotationError as error:
        raise HTTPException(status_code=422, detail=error.problem.as_dict()) from error
    exact = mass_exact.compute(oligo, registry=registry)
    basis = exact.average if request.basis == "average" else exact.monoisotopic
    try:
        ladder = mass_exact.charge_ladder(
            basis.value, request.charge_min, request.charge_max
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    # Mehr negative Ladungen als Phosphate kann ein Oligo nicht tragen —
    # die Zeilen darueber stehen zwar da, bedeuten aber nichts.
    n_phosphate = max(oligo.length - 1, 0)
    note = None
    if ladder and request.charge_max > n_phosphate:
        note = (
            f"Das Oligo hat {n_phosphate} Phosphate. Ladungen darüber hinaus "
            "sind rechnerisch, nicht chemisch."
        )

    return {
        "basis": basis.as_dict(4),
        "ladder": ladder,
        "isotopes": exact.isotopes,
        "formula": exact.formula,
        "max_physical_charge": n_phosphate,
        "note": note,
    }


@app.post("/api/loading/page")
def loading_page(request: PageLoadingRequest) -> dict[str, Any]:
    try:
        return loading.page(
            n_loading_pmol=request.n_loading_pmol,
            n_stock_nmol=request.n_stock_nmol,
            v_stock_ul=request.v_stock_ul,
            water_total_ul=request.water_total_ul,
            buffer_ul=request.buffer_ul,
            factor=request.factor,
        ).as_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/loading/lcms")
def loading_lcms(request: LcmsLoadingRequest) -> dict[str, Any]:
    try:
        return loading.lcms(
            n_injection_pmol=request.n_injection_pmol,
            n_stock_nmol=request.n_stock_nmol,
            v_stock_ul=request.v_stock_ul,
            v_sample_ul=request.v_sample_ul,
            v_injection_ul=request.v_injection_ul,
        ).as_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/concentration/od")
def concentration_od(request: OdRequest) -> dict[str, Any]:
    try:
        return extinction.convert_od(
            eps260=request.eps260,
            molar_mass=request.molar_mass,
            od=request.od,
            nmol=request.nmol,
            microgram=request.microgram,
        ).as_dict()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/concentration/absorbance")
def concentration_absorbance(request: AbsorbanceRequest) -> dict[str, Any]:
    """A₂₆₀ <-> Konzentration. Eines der beiden Felder setzen."""
    if (request.a260 is None) == (request.conc_molar is None):
        raise HTTPException(
            status_code=422,
            detail="Genau eines von `a260` und `conc_molar` muss gesetzt sein.",
        )
    try:
        if request.a260 is not None:
            result = extinction.absorbance_to_concentration(
                request.a260, request.eps260, request.path_cm
            )
            return {"conc_molar": result.as_dict(12)}
        result = extinction.concentration_to_absorbance(
            request.conc_molar, request.eps260, request.path_cm
        )
        return {"a260": result.as_dict(4)}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


# ---------------------------------------------------------------- Kataloge


@app.get("/api/monomers")
def list_monomers() -> dict[str, Any]:
    registry = get_registry()
    return {
        "monomers": [
            {
                "code": spec.code,
                "name": spec.name,
                "typ": spec.typ,
                "mass_residue": spec.mass_residue,
                "mass_amidite": spec.mass_amidite,
                "conc_molar": spec.conc_molar,
                "formula_residue": spec.formula_residue,
                "eps260": spec.eps260,
                "base_parent": spec.base_parent,
                "core_tested": spec.core_tested,
                "smiles": spec.smiles,
                "quelle": spec.quelle,
                "deviates_from_excel": spec.deviates_from_excel,
                "is_override": spec.code in getattr(registry, "custom_codes", set()),
            }
            for spec in sorted(registry.monomers.values(), key=lambda s: s.code)
        ],
        "protecting_groups": registry.protecting_group_details,
        "protecting_group_by_base": registry.protecting_group_by_base,
        "termini": registry.termini,
    }


@app.post("/api/monomers")
def write_monomer(request: MonomerWriteRequest) -> dict[str, Any]:
    """Eigenen Baustein anlegen oder vorhandenen aendern.

    Geschrieben wird nach `data/monomers_custom.yaml`; `monomers.yaml` bleibt
    die unangetastete Abschrift des Excel (CLAUDE.md, Regel 2).
    """
    code = request.code.strip()
    if not code:
        raise HTTPException(status_code=422, detail="Der Code darf nicht leer sein.")
    entry = {
        key: value
        for key, value in request.model_dump().items()
        if value is not None or key == "code"
    }
    entry["code"] = code
    if request.mass_residue is None and request.smiles is None:
        registry = get_registry()
        if registry.monomer(request.code) is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Ein neuer Baustein braucht eine Restmasse oder ein SMILES, "
                    "aus dem sie abgeleitet werden kann."
                ),
            )
    save_monomer(entry)
    get_registry().reload()
    return {"saved": request.code, "file": "data/monomers_custom.yaml"}


@app.delete("/api/monomers/{code}")
def drop_monomer_override(code: str) -> dict[str, Any]:
    """Eine eigene Aenderung zuruecknehmen — der Excel-Wert gilt wieder."""
    removed = remove_monomer_override(code)
    get_registry().reload()
    if not removed:
        raise HTTPException(
            status_code=404, detail=f"Für {code} gibt es keine eigene Änderung."
        )
    return {"removed": code}


@app.get("/api/modifications")
def list_modifications() -> dict[str, Any]:
    registry = get_registry()
    return {
        "modifications": [
            {
                "code": spec.code,
                "name": spec.name,
                "mass_diff": spec.mass_diff,
                "scope": spec.scope,
                "klasse": spec.klasse,
                "formula": spec.formula,
                "eps260": spec.eps260,
                "base_parent": spec.base_parent,
                "counts_as_base": spec.counts_as_base,
                "core_tested": spec.core_tested,
                "needs_review": spec.needs_review,
                "note": spec.note,
                "quelle": spec.quelle,
            }
            for spec in sorted(registry.modifications.values(), key=lambda s: s.code)
        ]
    }


@app.post("/api/modifications")
def write_modification(request: ModificationWriteRequest) -> dict[str, Any]:
    entry = {
        key: value
        for key, value in request.model_dump().items()
        if value is not None or key in ("code", "scope", "counts_as_base")
    }
    save_modification(entry)
    get_registry().reload()
    return {"saved": request.code, "file": "data/modifications_custom.yaml"}


@app.post("/api/registry/reload")
def reload_registry() -> dict[str, Any]:
    """Nach dem Bearbeiten der YAML-Dateien von Hand."""
    registry = get_registry()
    registry.reload()
    return {"monomers": len(registry.monomers), "modifications": len(registry.modifications)}


# -------------------------------------------------------------- Bibliothek


@app.get("/api/library/oligos")
def library_list(q: str | None = Query(default=None)) -> dict[str, Any]:
    return {
        "total": library.count_oligos(q),
        "oligos": [
            {
                "id": r.id,
                "name": r.name,
                "sequence": r.sequence,
                "notes": r.notes,
                "length": r.length,
                "mass_fully_deprotected": r.mass_fully_deprotected,
                "created_at": r.created_at.isoformat(timespec="seconds"),
                "updated_at": r.updated_at.isoformat(timespec="seconds"),
            }
            for r in library.list_oligos(q)
        ]
    }


@app.post("/api/library/oligos")
def library_save(request: OligoSaveRequest) -> dict[str, Any]:
    """Speichern. Die Masse wird mitgeschrieben, aber nur fuer Liste und Suche.

    Gespeichert wird der Sequenztext; beim Laden wird neu gerechnet.
    """
    registry = get_registry()
    oligo, problems = notation.analyse(request.sequence, registry, request.name)
    if problems:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Die Sequenz hat Fehler und wird nicht gespeichert.",
                "problems": [p.as_dict() for p in problems],
            },
        )
    mass_value = mass.compute(oligo, registry).fully_deprotected.value
    record = library.save_oligo(
        name=request.name,
        sequence=notation.to_string(oligo, group=3),
        notes=request.notes,
        length=oligo.length,
        mass=mass_value,
    )
    return {"id": record.id, "name": record.name}


@app.delete("/api/library/oligos/{record_id}")
def library_delete(record_id: int) -> dict[str, Any]:
    if not library.delete_oligo(record_id):
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden.")
    return {"deleted": record_id}


@app.get("/api/library/oligos.csv", response_class=PlainTextResponse)
def library_csv() -> PlainTextResponse:
    return PlainTextResponse(
        library.oligos_as_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="oligolab-bibliothek.csv"'},
    )


@app.get("/api/library/samples")
def samples_list() -> dict[str, Any]:
    return {
        "samples": [
            {
                "id": r.id,
                "name": r.name,
                "n_stock_nmol": r.n_stock_nmol,
                "v_stock_ul": r.v_stock_ul,
                "notes": r.notes,
                "created_at": r.created_at.isoformat(timespec="seconds"),
            }
            for r in library.list_samples()
        ]
    }


@app.post("/api/library/samples")
def samples_save(request: SampleSaveRequest) -> dict[str, Any]:
    record = library.save_sample(
        name=request.name,
        n_stock_nmol=request.n_stock_nmol,
        v_stock_ul=request.v_stock_ul,
        notes=request.notes,
    )
    return {"id": record.id, "name": record.name}


@app.delete("/api/library/samples/{record_id}")
def samples_delete(record_id: int) -> dict[str, Any]:
    if not library.delete_sample(record_id):
        raise HTTPException(status_code=404, detail="Probe nicht gefunden.")
    return {"deleted": record_id}


# -------------------------------------------------------------------- Hilfe


@app.get("/api/help")
def help_entries() -> dict[str, Any]:
    """Alle Hilfetexte. Phase 2 haengt daran `<HelpTip />` und die Seite /hilfe."""
    path = settings.help_dir / "help.yaml"
    if not path.exists():
        return {"entries": {}}
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {"entries": {}}


# ------------------------------------------------------- gebaute Oberflaeche

_DIST = PROJECT_ROOT / "frontend" / "dist"
if _DIST.is_dir():

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        """Alles ausserhalb von `/api` liefert die Oberflaeche aus.

        Die Adressen der Oberflaeche (`/hilfe`, `/strang`, ...) sind echte
        Pfade. Ohne diesen Rueckfall liefe ein Direktaufruf oder ein
        Neuladen auf `/hilfe` in einen 404.
        """
        # Ein unbekannter Endpunkt bleibt ein 404. Ihm die Oberflaeche
        # zurueckzugeben wuerde jeden Tippfehler in einer Adresse als
        # scheinbaren Erfolg tarnen.
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Unbekannter Endpunkt.")

        candidate = (_DIST / full_path).resolve()
        if (
            full_path
            and _DIST.resolve() in candidate.parents
            and candidate.is_file()
        ):
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
