/* Die Seite „3D" (PHASEN.md 6.4 bis 6.6).
 *
 * Von oben nach unten: die Referenzstruktur wählen, das Modell bauen, die
 * Ansicht, die Messungen, das Messwerkzeug, die ORCA-Vorbereitung und der
 * Gesamtbericht.
 *
 * Der eigentliche Gewinn der Phase steht in der Mitte: Sequenzkarte und
 * 3D-Fenster teilen sich eine Auswahl. Ein Klick in der Karte hebt die
 * Position im Modell hervor, ein Klick im Modell die Zelle in der Karte.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "../api";
import { SequenceMap } from "../components/SequenceMap";
import {
  COLOR_MODE_LABEL,
  StructureViewer,
  type ColorMode,
  type StructureViewerHandle,
} from "../components/StructureViewer";
import {
  Card,
  Chip,
  Empty,
  Field,
  Notice,
  NumberInput,
  Rating,
  ReliabilityMark,
} from "../components/ui";
import { safeFilename } from "../lib/svgExport";
import { useStore, type BufferSettings } from "../state/store";
import type {
  CriticalView,
  GeometryView,
  MeasurementView,
  ModelView,
  OrcaView,
  ReferenceSpecView,
  StrandView,
  StructureView,
} from "../types";

const PROVENANCE_ORDER = [
  "uebernommen",
  "geruest",
  "nur_zucker",
  "gebaut",
  "ideal",
] as const;

const PROVENANCE_SHORT: Record<string, string> = {
  uebernommen: "aus der Referenz",
  geruest: "Ringgerüst",
  nur_zucker: "nur Zucker",
  gebaut: "aus SMILES gebaut",
  ideal: "ideal",
};

function download(name: string, text: string, type: string) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function Modell3D({ navigate }: { navigate: (path: string) => void }) {
  const { state, markComputed } = useStore();
  const oligo = state.activeOligo;

  const [references, setReferences] = useState<ReferenceSpecView[]>([]);
  const [structureId, setStructureId] = useState<string>("");
  const [structure, setStructure] = useState<StructureView | null>(null);
  const [model, setModel] = useState<ModelView | null>(null);
  const [geometry, setGeometry] = useState<GeometryView | null>(null);
  const [strand, setStrand] = useState<StrandView | null>(null);

  const [cleavage, setCleavage] = useState<number | "">("");
  const [colorMode, setColorMode] = useState<ColorMode>("modification");
  const [selected, setSelected] = useState<number | null>(null);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);

  const viewer = useRef<StructureViewerHandle | null>(null);

  // ---- Katalog
  useEffect(() => {
    api
      .structures()
      .then((result) => {
        setReferences(result.references);
        const erste =
          result.references.find((r) => r.cached)?.id ??
          result.default ??
          result.references[0]?.id ??
          "";
        setStructureId(erste);
      })
      .catch(() => setReferences([]));
  }, []);

  // ---- Die Sequenzkarte braucht den Strang
  useEffect(() => {
    if (!oligo?.sequence) {
      setStrand(null);
      return;
    }
    let abgebrochen = false;
    api
      .strand(oligo.sequence, false)
      .then((result) => !abgebrochen && setStrand(result))
      .catch(() => !abgebrochen && setStrand(null));
    return () => {
      abgebrochen = true;
    };
  }, [oligo?.sequence]);

  const coreRange = useMemo((): [number, number] | null => {
    const kern = strand?.parts?.parts.find((p) => p.kind === "core");
    return kern ? [kern.start, kern.end] : null;
  }, [strand]);

  const holeStruktur = async () => {
    if (!structureId) return;
    setBusy(true);
    setError(null);
    setHint(null);
    try {
      const ergebnis = await api.structureFetch(structureId);
      if (!ergebnis.available) {
        setHint(ergebnis.note);
        setStructure(null);
      } else {
        setStructure(ergebnis);
        setReferences((alt) =>
          alt.map((r) => (r.id === ergebnis.id ? { ...r, cached: true } : r)),
        );
      }
    } catch (grund) {
      setError(grund instanceof ApiError ? grund.message : String(grund));
    } finally {
      setBusy(false);
    }
  };

  const ladeVorhandene = useCallback(async (kennung: string) => {
    try {
      setStructure(await api.structure(kennung));
      setHint(null);
    } catch {
      setStructure(null);
    }
  }, []);

  useEffect(() => {
    const eintrag = references.find((r) => r.id === structureId);
    if (eintrag?.cached) void ladeVorhandene(structureId);
    else setStructure(null);
    setModel(null);
    setGeometry(null);
  }, [structureId, references, ladeVorhandene]);

  const hochladen = async (datei: File) => {
    setBusy(true);
    setError(null);
    try {
      const text = await datei.text();
      const ergebnis = await api.structureUpload(
        datei.name.replace(/\.(pdb|cif|ent)(\.gz)?$/i, ""),
        text,
      );
      setStructure(ergebnis);
      setStructureId(ergebnis.id);
      setReferences((alt) =>
        alt.some((r) => r.id === ergebnis.id)
          ? alt.map((r) => (r.id === ergebnis.id ? { ...r, cached: true } : r))
          : [
              ...alt,
              {
                id: ergebnis.id,
                title: ergebnis.title ?? ergebnis.id,
                role: "eigene Datei",
                note: null,
                cached: true,
              },
            ],
      );
      setHint(null);
    } catch (grund) {
      setError(grund instanceof ApiError ? grund.message : String(grund));
    } finally {
      setBusy(false);
    }
  };

  const baueModell = async () => {
    if (!oligo?.sequence || !structure) return;
    setBusy(true);
    setError(null);
    try {
      const ergebnis = await api.model({
        sequence: oligo.sequence,
        structure_id: structure.id,
        core_start: coreRange?.[0] ?? null,
        core_end: coreRange?.[1] ?? null,
        cleavage_residue: cleavage === "" ? null : cleavage,
      });
      setModel(ergebnis.model);
      setGeometry(ergebnis.geometry);
      if (ergebnis.model.available) markComputed("3d");
    } catch (grund) {
      setError(grund instanceof ApiError ? grund.message : String(grund));
    } finally {
      setBusy(false);
    }
  };

  if (!oligo?.sequence) {
    return (
      <Card title="3D" helpId="field.model3d">
        <Empty>
          Für ein Modell braucht OligoLab erst ein DNAzym.{" "}
          <button
            type="button"
            className="underline"
            style={{ color: "var(--role-input)" }}
            onClick={() => navigate("/steckbrief")}
          >
            Zum Steckbrief
          </button>
        </Empty>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Card
        title="Referenzstruktur"
        subtitle="Aus dem Ablageort, von der RCSB-PDB oder als eigene Datei."
        helpId="field.reference"
        actions={
          <>
            <button
              type="button"
              className="ol-button"
              onClick={holeStruktur}
              disabled={busy || !structureId}
            >
              holen
            </button>
            <label className="ol-button cursor-pointer">
              Datei …
              <input
                type="file"
                accept=".pdb,.cif,.ent,.txt"
                className="hidden"
                onChange={(event) => {
                  const datei = event.target.files?.[0];
                  if (datei) void hochladen(datei);
                }}
              />
            </label>
          </>
        }
      >
        <div className="flex flex-wrap items-end gap-4">
          <Field label="Struktur" role="settings" helpId="field.reference" htmlFor="ref">
            <select
              id="ref"
              className="ol-input"
              data-role="settings"
              value={structureId}
              onChange={(event) => setStructureId(event.target.value)}
            >
              {references.map((eintrag) => (
                <option key={eintrag.id} value={eintrag.id}>
                  {eintrag.id} — {eintrag.title}
                  {eintrag.cached ? " (da)" : ""}
                </option>
              ))}
            </select>
          </Field>
          <Field
            label="Spaltstelle im Substrat"
            role="settings"
            hint="Restnummer"
            helpId="field.cleavage_residue"
            htmlFor="cut"
          >
            <NumberInput
              id="cut"
              value={cleavage}
              min={1}
              step={1}
              onChange={setCleavage}
            />
          </Field>
          <button
            type="button"
            className="ol-button"
            data-role="input"
            onClick={baueModell}
            disabled={busy || !structure}
          >
            {busy ? "rechnet …" : "Modell bauen"}
          </button>
        </div>

        {hint && (
          <div className="mt-3">
            <Notice level="warn" title="Kein Netz">
              {hint}
            </Notice>
          </div>
        )}

        {structure && (
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            <Chip role="result">{structure.id}</Chip>
            {structure.method && <Chip role="settings">{structure.method}</Chip>}
            {structure.resolution_a !== null && (
              <Chip role="result">{structure.resolution_a.toFixed(2)} Å</Chip>
            )}
            {structure.chains
              .filter((kette) => kette.role)
              .map((kette) => (
                <Chip key={kette.id} role="settings">
                  Kette {kette.id}: {kette.role === "dnazyme" ? "DNAzym" : "Substrat"}{" "}
                  ({kette.length})
                </Chip>
              ))}
            {structure.citation && (
              <span style={{ color: "var(--text-faint)" }}>{structure.citation}</span>
            )}
          </div>
        )}
        {structure?.note && (
          <p className="mt-2 text-xs" style={{ color: "var(--rating-warn)" }}>
            {structure.note}
          </p>
        )}
      </Card>

      {error && (
        <Notice level="bad" title="Das hat nicht geklappt">
          {error}
        </Notice>
      )}

      {model && !model.available && (
        <Notice level="warn" title="Kein Modell">
          {model.note}
        </Notice>
      )}

      {model?.available && (
        <>
          <Notice level="info" title="Das ist ein Modell">
            {model.disclaimer}
          </Notice>

          <Card
            title="Ansicht"
            helpId="result.viewer3d"
            actions={
              <>
                <select
                  className="ol-input text-xs"
                  data-role="settings"
                  aria-label="Einfärbung"
                  value={colorMode}
                  onChange={(event) => setColorMode(event.target.value as ColorMode)}
                >
                  {(Object.keys(COLOR_MODE_LABEL) as ColorMode[]).map((modus) => (
                    <option key={modus} value={modus}>
                      {COLOR_MODE_LABEL[modus]}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="ol-button text-xs"
                  onClick={() => viewer.current?.centerOnCleavage()}
                >
                  Auf Spaltstelle zentrieren
                </button>
                <button
                  type="button"
                  className="ol-button text-xs"
                  onClick={() =>
                    download(
                      safeFilename(`${oligo.name || "modell"}`, "pdb"),
                      model.pdb,
                      "chemical/x-pdb",
                    )
                  }
                >
                  PDB
                </button>
              </>
            }
          >
            <StructureViewer
              ref={viewer}
              pdb={model.pdb}
              positions={model.positions}
              chainDnazyme={model.chain_dnazyme}
              chainSubstrate={model.chain_substrate}
              coreRange={coreRange}
              cleavageResidue={cleavage === "" ? null : cleavage}
              colorMode={colorMode}
              selected={selected}
              onPick={setSelected}
            />

            {/* Die Kopplung: dieselbe Auswahl in beiden Darstellungen. */}
            {strand?.oligo && (
              <div className="mt-3 overflow-x-auto">
                <SequenceMap
                  oligo={strand.oligo}
                  parts={strand.parts}
                  folding={null}
                  critical={strand.critical}
                  svgId="karte-3d"
                  title={`Sequenzkarte von ${oligo.name || "dem DNAzym"}`}
                  highlight={
                    selected === null ? null : { start: selected, end: selected }
                  }
                  onPickPosition={(position) =>
                    setSelected((alt) => (alt === position ? null : position))
                  }
                />
              </div>
            )}

            <p className="mt-2 text-xs" style={{ color: "var(--text-faint)" }}>
              Klick auf eine Position in der Karte hebt sie im Modell hervor —
              und umgekehrt.
              {selected !== null && (
                <>
                  {" "}
                  Gewählt: Position {selected}
                  {(() => {
                    const eintrag = model.positions.find(
                      (p) => p.position === selected,
                    );
                    return eintrag
                      ? ` (${eintrag.code}, Rest ${eintrag.residue_number}, ${eintrag.provenance_label})`
                      : "";
                  })()}
                </>
              )}
            </p>

            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              {PROVENANCE_ORDER.filter((art) => model.counts[art]).map((art) => (
                <Chip key={art} role="settings" title={PROVENANCE_SHORT[art]}>
                  {model.counts[art]}× {PROVENANCE_SHORT[art]}
                </Chip>
              ))}
            </div>
            {model.warnings.map((warnung) => (
              <p
                key={warnung}
                className="mt-2 text-xs"
                style={{ color: "var(--rating-warn)" }}
              >
                {warnung}
              </p>
            ))}
          </Card>

          {geometry && (
            <GeometryCard
              geometry={geometry}
              structureId={structure?.id ?? ""}
              pdb={model.pdb}
            />
          )}

          <OrcaCard
            structureId={structure?.id ?? ""}
            pdb={model.pdb}
            chain={model.chain_substrate}
            cleavage={cleavage === "" ? null : cleavage}
          />

          <ReportCard
            oligo={oligo}
            model={model}
            geometry={geometry}
            buffer={state.buffer}
            findings={strand?.critical ?? null}
          />
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------- 6.3 Messungen */

function GeometryCard({
  geometry,
  structureId,
  pdb,
}: {
  geometry: GeometryView;
  structureId: string;
  pdb: string;
}) {
  const [selections, setSelections] = useState("B:9:O2',B:10:P");
  const [result, setResult] = useState<MeasurementView | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const messen = async () => {
    setProblem(null);
    try {
      setResult(
        await api.measure({
          structure_id: structureId,
          pdb,
          selections: selections
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        }),
      );
    } catch (grund) {
      setResult(null);
      setProblem(grund instanceof ApiError ? grund.message : String(grund));
    }
  };

  const inline = geometry.inline;

  return (
    <Card title="Geometrie" helpId="result.geometry">
      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <h3 className="mb-2 text-xs font-semibold">
            In-line-Winkel an der Spaltstelle
          </h3>
          {inline.available && inline.angle ? (
            <>
              <div className="flex items-baseline gap-2">
                <span className="ol-mono text-2xl tabular-nums">
                  {inline.angle.value === null ? "—" : inline.angle.value.toFixed(1)}
                </span>
                <span className="text-sm">°</span>
                {inline.rating && (
                  <Rating level={inline.rating}>{inline.assessment ?? ""}</Rating>
                )}
              </div>
              <p className="text-xs" style={{ color: "var(--text-faint)" }}>
                {inline.angle.method} <ReliabilityMark reliability={inline.angle.reliability} />
              </p>
              <table className="mt-2 w-full text-xs tabular-nums">
                <tbody>
                  <tr>
                    <td>2'-O bis P</td>
                    <td className="ol-mono text-right">
                      {inline.distance_attack?.value?.toFixed(2) ?? "—"} Å
                    </td>
                  </tr>
                  <tr style={{ borderTop: "1px solid var(--border)" }}>
                    <td>P bis O5'</td>
                    <td className="ol-mono text-right">
                      {inline.distance_leaving?.value?.toFixed(2) ?? "—"} Å
                    </td>
                  </tr>
                  <tr style={{ borderTop: "1px solid var(--border)" }}>
                    <td>gemessen an</td>
                    <td className="ol-mono text-right">{inline.atoms.join(" · ")}</td>
                  </tr>
                </tbody>
              </table>
            </>
          ) : (
            <Notice level="warn">{inline.note}</Notice>
          )}
        </div>

        <div>
          <h3 className="mb-2 text-xs font-semibold">Wo die Modifikationen sitzen</h3>
          {geometry.to_cleavage.length === 0 ? (
            <Empty>Keine modifizierte Position.</Empty>
          ) : (
            <table className="w-full text-xs tabular-nums">
              <thead>
                <tr style={{ color: "var(--text-faint)" }}>
                  <th className="text-left font-normal">Position</th>
                  <th className="text-right font-normal">zur Spaltstelle</th>
                  <th className="text-right font-normal">zum Kern</th>
                </tr>
              </thead>
              <tbody>
                {geometry.to_cleavage.map((eintrag) => {
                  const kern = geometry.to_core.find(
                    (k) => k.position === eintrag.position,
                  );
                  const ionen = geometry.ion_contacts[String(eintrag.position)];
                  return (
                    <tr
                      key={eintrag.position}
                      style={{ borderTop: "1px solid var(--border)" }}
                    >
                      <td>
                        {eintrag.position} {eintrag.code}
                        {eintrag.modification && ` · ${eintrag.modification}`}
                        {ionen?.[0] && (
                          <span style={{ color: "var(--rating-warn)" }}>
                            {" "}
                            ▲ {ionen[0].residue} {ionen[0].angstrom.toFixed(1)} Å
                          </span>
                        )}
                      </td>
                      <td className="ol-mono text-right">
                        {eintrag.angstrom === null
                          ? "—"
                          : `${eintrag.angstrom.toFixed(1)} Å`}
                      </td>
                      <td className="ol-mono text-right">
                        {kern?.nucleotides === undefined
                          ? "—"
                          : `${kern.nucleotides} nt`}
                        {kern?.angstrom != null && ` · ${kern.angstrom.toFixed(1)} Å`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          {geometry.to_cleavage.some((e) => e.angstrom === null) && (
            <p className="mt-2 text-xs" style={{ color: "var(--text-faint)" }}>
              „—" heißt: diese Position liegt außerhalb der Referenz und hat
              keine Koordinaten.
            </p>
          )}
        </div>
      </div>

      <div className="mt-4">
        <h3 className="mb-2 text-xs font-semibold">Messwerkzeug</h3>
        <div className="flex flex-wrap items-end gap-2">
          <Field
            label="Atome"
            role="settings"
            hint="Kette:Rest:Atom, zwei oder drei, mit Komma"
            helpId="field.measure"
            htmlFor="sel"
          >
            <input
              id="sel"
              className="ol-input ol-mono"
              data-role="settings"
              value={selections}
              onChange={(event) => setSelections(event.target.value)}
            />
          </Field>
          <button type="button" className="ol-button" onClick={messen}>
            messen
          </button>
          {result && (
            <span className="ol-mono text-sm">
              {result.value === null
                ? result.note
                : `${result.kind}: ${result.value.toFixed(2)} ${result.unit}`}
            </span>
          )}
          {problem && (
            <span className="text-xs" style={{ color: "var(--rating-bad)" }}>
              {problem}
            </span>
          )}
        </div>
      </div>

      {geometry.warnings.map((warnung) => (
        <p
          key={warnung}
          className="mt-2 text-xs"
          style={{ color: "var(--rating-warn)" }}
        >
          {warnung}
        </p>
      ))}
    </Card>
  );
}

/* --------------------------------------------------------- 6.5 ORCA */

function OrcaCard({
  structureId,
  pdb,
  chain,
  cleavage,
}: {
  structureId: string;
  pdb: string;
  chain: string;
  cleavage: number | null;
}) {
  const [purposes, setPurposes] = useState<
    { id: string; label: string; keywords: string; note: string }[]
  >([]);
  const [purpose, setPurpose] = useState("geometrie");
  const [methyl, setMethyl] = useState(false);
  const [result, setResult] = useState<OrcaView | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    api
      .orcaPurposes()
      .then((daten) => setPurposes(daten.purposes))
      .catch(() => setPurposes([]));
  }, []);

  const schneiden = async () => {
    setProblem(null);
    if (cleavage === null || !chain) {
      setProblem("Ohne Spaltstelle weiß OligoLab nicht, was es ausschneiden soll.");
      return;
    }
    try {
      setResult(
        await api.orca({
          structure_id: structureId,
          pdb,
          residues: [
            [chain, cleavage],
            [chain, cleavage + 1],
          ],
          purpose,
          replace_sugar_with_methyl: methyl,
        }),
      );
    } catch (grund) {
      setResult(null);
      setProblem(grund instanceof ApiError ? grund.message : String(grund));
    }
  };

  return (
    <Card
      title="Quantenchemie vorbereiten"
      subtitle="OligoLab rechnet hier nichts — es schreibt die Eingabedatei."
      helpId="field.orca"
    >
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Zweck" role="settings" helpId="field.orca_purpose" htmlFor="zweck">
          <select
            id="zweck"
            className="ol-input"
            data-role="settings"
            value={purpose}
            onChange={(event) => setPurpose(event.target.value)}
          >
            {purposes.map((eintrag) => (
              <option key={eintrag.id} value={eintrag.id}>
                {eintrag.label}
              </option>
            ))}
          </select>
        </Field>
        <label className="flex items-center gap-2 pb-2 text-xs">
          <input
            type="checkbox"
            checked={methyl}
            onChange={(event) => setMethyl(event.target.checked)}
          />
          Zucker durch Methyl ersetzen
        </label>
        <button type="button" className="ol-button" onClick={schneiden}>
          Fragment schneiden
        </button>
      </div>

      {problem && (
        <p className="mt-2 text-xs" style={{ color: "var(--rating-bad)" }}>
          {problem}
        </p>
      )}

      {result && (
        <div className="mt-3">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Chip role="result">{result.fragment.atom_count} Atome</Chip>
            <Chip role="result">Ladung {result.fragment.charge}</Chip>
            {result.fragment.added_hydrogens > 0 && (
              <Chip role="settings">
                {result.fragment.added_hydrogens} H abgesättigt
              </Chip>
            )}
            <button
              type="button"
              className="ol-button text-xs"
              onClick={() =>
                download(safeFilename("fragment", "inp"), result.input, "text/plain")
              }
            >
              .inp sichern
            </button>
          </div>
          <p className="mt-1 text-xs" style={{ color: "var(--text-faint)" }}>
            {result.fragment.size_hint}
          </p>
          {!result.fragment.sensible && (
            <div className="mt-2">
              <Notice level="warn">
                Das ist viel für eine Quantenrechnung. Kleiner schneiden.
              </Notice>
            </div>
          )}
          <pre
            className="ol-mono mt-2 max-h-48 overflow-auto rounded-lg p-2 text-[11px]"
            style={{ border: "1px solid var(--border)" }}
          >
            {result.input}
          </pre>
        </div>
      )}
    </Card>
  );
}

/* ------------------------------------------------------ 6.6 Bericht */

function ReportCard({
  oligo,
  model,
  geometry,
  buffer,
  findings,
}: {
  oligo: { name: string; sequence: string; notes: string };
  model: ModelView;
  geometry: GeometryView | null;
  buffer: BufferSettings;
  findings: CriticalView | null;
}) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const erzeugen = async () => {
    setBusy(true);
    setProblem(null);
    try {
      // Die Zahlen kommen aus demselben Steckbrief, den die Oberfläche
      // zeigt — nicht aus einer zweiten Rechnung.
      const steckbrief = await api.profile(oligo.sequence, oligo.name, oligo.notes);
      // Die Massen kommen als Liste mit Schlüsseln, nicht als benannte
      // Felder — der Typ hat es gesagt, bevor es der Bericht zeigen konnte.
      const masse = (schluessel: string) =>
        steckbrief.mass?.masses.find((e) => e.key === schluessel)?.value ?? null;

      // Die Bilder, die gerade auf dem Schirm stehen.
      const bilder: Record<string, string> = {};
      for (const [titel, kennung] of [
        ["Sequenzkarte", "karte-3d"],
      ] as const) {
        const svg = document.getElementById(kennung);
        if (svg) bilder[titel] = svg.outerHTML;
      }

      const html = await api.report(
        {
          name: oligo.name || "DNAzym",
          sequence: oligo.sequence,
          length: steckbrief.oligo.length,
          modifications: steckbrief.oligo.monomers
            .filter((m) => m.modifications.length)
            .map((m) => `${m.modifications[0]?.name ?? m.code} an Position ${m.position}`),
          mass: {
            fully_deprotected: masse("fully_deprotected"),
            with_dmt: masse("plus_dmt"),
            with_phosphate: masse("plus_3_phosphate"),
            method:
              steckbrief.mass?.masses.find((e) => e.key === "fully_deprotected")
                ?.method ?? "",
          },
          ms_ladder: steckbrief.charge_ladder ?? [],
          self_fold_mfe: null,
          geometry: geometry
            ? { inline: geometry.inline as unknown as Record<string, unknown> }
            : null,
          findings:
            findings?.findings.map((f) => ({
              position: f.start,
              level: f.severity_label,
              message: f.message,
            })) ?? [],
          disclaimers: [model.disclaimer],
          settings: {
            Referenz: model.reference_id ?? "—",
            "Na⁺": `${buffer.naMm} mM`,
            "Mg²⁺": `${buffer.mgMm} mM`,
            Oligo: `${buffer.oligoConcNm} nM`,
            Reaktionstemperatur: `${buffer.reactionTempC} °C`,
          },
        },
        bilder,
      );

      const fenster = window.open("", "_blank");
      if (fenster) {
        fenster.document.write(html);
        fenster.document.close();
      } else {
        download(safeFilename(oligo.name || "bericht", "html"), html, "text/html");
      }
    } catch (grund) {
      setProblem(grund instanceof ApiError ? grund.message : String(grund));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      title="Gesamtbericht"
      subtitle="Ein Blatt fürs Laborbuch, mit Datum und allen Einstellungen."
      helpId="field.report"
      actions={
        <button
          type="button"
          className="ol-button"
          data-role="input"
          onClick={erzeugen}
          disabled={busy}
        >
          {busy ? "sammelt …" : "Bericht erzeugen"}
        </button>
      }
    >
      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
        Der Bericht fasst zusammen, was OligoLab zu diesem Strang gerechnet
        hat: Sequenz, Masse, Arme, Spaltstelle, Befunde, Geometrie und die
        Bilder. Er öffnet sich als eigene Seite; das PDF schreibt der
        Druckdialog des Browsers.
      </p>
      {problem && (
        <p className="mt-2 text-xs" style={{ color: "var(--rating-bad)" }}>
          {problem}
        </p>
      )}
    </Card>
  );
}
