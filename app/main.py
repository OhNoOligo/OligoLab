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
)
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
