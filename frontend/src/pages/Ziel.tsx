/* Seite "Ziel" (PHASEN.md 4.4).
 *
 * Oben die Sequenz in Festbreitenschrift mit Positionslineal, abgesetzten
 * Abschnitten und Suchfeld. Darunter die Spurdarstellung — dieselbe Sprache
 * wie die Sequenzkarte in Phase 3, damit man sich nicht umgewöhnen muss.
 *
 * Ein Transkript hat Tausende von Basen. Darum zwei Ebenen: die
 * Übersichtsleiste zeigt die ganze Länge mit dem Zugänglichkeitsprofil und
 * dem gewählten Bereich darin, die Detailkarte den Bereich selbst. Gefaltet
 * und gerechnet wird nur der Bereich — bei mehreren Kilobasen spart das viel
 * Zeit, und mehr sagt eine Gesamtfaltung ohnehin nicht.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "../api";
import { Handoff } from "../components/AreaShell";
import { Overview, TargetMap, type Range } from "../components/TargetMap";
import {
  Card,
  Empty,
  Field,
  Notice,
  NumberInput,
  ResultNumber,
  formatNumber,
} from "../components/ui";
import { useStore } from "../state/store";
import type {
  AccessibilityView,
  FetchChoice,
  LibraryTarget,
  RegionKind,
  RegionView,
  TargetFoldView,
} from "../types";

/** Wie viele Basen die Detailkarte anfangs zeigt. */
const DEFAULT_WINDOW = 200;

const REGION_COLOR: Record<RegionKind, string> = {
  "5utr": "var(--role-settings)",
  cds: "var(--role-result)",
  "3utr": "var(--role-settings)",
  other: "var(--text-faint)",
};

/* ------------------------------------------------------ Sequenztext oben */

function SequenceText({
  sequence,
  regions,
  range,
  search,
  onPick,
}: {
  sequence: string;
  regions: RegionView[];
  range: Range;
  search: string;
  onPick: (position: number) => void;
}) {
  const PER_BLOCK = 10;
  const PER_ROW = 60;

  const regionAt = useCallback(
    (position: number): RegionView | undefined =>
      regions.find((r) => position >= r.start && position <= r.end),
    [regions],
  );

  const treffer = useMemo(() => {
    const sauber = search.trim().toUpperCase().replace(/[^ACGUN]/g, "");
    if (sauber.length < 2) return new Set<number>();
    const gefunden = new Set<number>();
    let index = sequence.indexOf(sauber);
    while (index !== -1) {
      for (let k = 0; k < sauber.length; k += 1) gefunden.add(index + k + 1);
      index = sequence.indexOf(sauber, index + 1);
    }
    return gefunden;
  }, [sequence, search]);

  // Nur den gewählten Bereich zeigen: ein ganzes Transkript als Text zu
  // rendern legt den Browser lahm.
  const von = range.start;
  const bis = Math.min(range.end, von + 3000 - 1);

  const zeilen: number[] = [];
  for (let start = von; start <= bis; start += PER_ROW) zeilen.push(start);

  const gutter = String(bis).length + 1;

  return (
    <div className="ol-mono overflow-x-auto text-xs" style={{ lineHeight: 1.8 }}>
      {zeilen.map((zeilenStart) => (
        <div key={zeilenStart} className="whitespace-nowrap">
          <span
            style={{
              display: "inline-block",
              width: `${gutter}ch`,
              textAlign: "right",
              color: "var(--text-faint)",
              marginRight: "1.5ch",
            }}
          >
            {zeilenStart}
          </span>
          {Array.from(
            { length: Math.min(PER_ROW, bis - zeilenStart + 1) },
            (_, k) => {
              const position = zeilenStart + k;
              const region = regionAt(position);
              const gefunden = treffer.has(position);
              return (
                <span key={position}>
                  {k > 0 && k % PER_BLOCK === 0 ? " " : ""}
                  <span
                    onClick={() => onPick(position)}
                    title={`Position ${position}${region ? ` · ${region.label}` : ""}`}
                    style={{
                      color: region ? REGION_COLOR[region.kind] : "var(--text)",
                      fontWeight: region?.kind === "cds" ? 600 : 400,
                      background: gefunden
                        ? "color-mix(in srgb, var(--rating-warn) 35%, transparent)"
                        : undefined,
                      cursor: "pointer",
                    }}
                  >
                    {sequence[position - 1]}
                  </span>
                </span>
              );
            },
          )}
        </div>
      ))}
      {range.end > bis && (
        <p className="mt-2" style={{ color: "var(--text-faint)" }}>
          Gezeigt werden die ersten 3000 Basen des gewählten Bereichs. Für den
          Rest den Bereich verschieben.
        </p>
      )}
    </div>
  );
}

/* -------------------------------------------------------------- die Seite */

export function Ziel({ navigate }: { navigate: (path: string) => void }) {
  const { state, setTarget, patchTarget, markComputed } = useStore();
  const target = state.activeTarget;
  const sequence = target?.sequence ?? "";
  const length = sequence.length;

  const [regions, setRegions] = useState<RegionView[]>([]);
  const [range, setRange] = useState<Range>({ start: 1, end: DEFAULT_WINDOW });
  const [folding, setFolding] = useState<TargetFoldView | null>(null);
  const [access, setAccess] = useState<AccessibilityView | null>(null);
  const [probeLength, setProbeLength] = useState<number | "">(15);
  const [window_, setWindow] = useState<number | "">(80);
  const [maxSpan, setMaxSpan] = useState<number | "">(40);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  // Eingabe
  const [rawText, setRawText] = useState("");
  const [fetchSource, setFetchSource] = useState<
    "ensembl" | "ncbi" | "rnacentral"
  >("ncbi");
  const [fetchId, setFetchId] = useState("");
  const [choices, setChoices] = useState<FetchChoice[]>([]);
  const [fetchNote, setFetchNote] = useState<string | null>(null);
  const [library, setLibrary] = useState<LibraryTarget[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  const refreshLibrary = useCallback(() => {
    api
      .libraryTargets()
      .then((result) => setLibrary(result.targets))
      .catch(() => setLibrary([]));
  }, []);

  useEffect(refreshLibrary, [refreshLibrary]);

  // Bereich zurechtrücken, wenn eine neue Sequenz kommt.
  useEffect(() => {
    if (!length) return;
    setRange((alt) => ({
      start: Math.min(alt.start, length),
      end: Math.min(Math.max(alt.end, Math.min(DEFAULT_WINDOW, length)), length),
    }));
  }, [length]);

  /* Das Zugänglichkeitsprofil gilt für die ganze Länge: es rechnet lokal und
   * kostet auch bei Kilobasen wenig. Die Faltung dagegen nur für den
   * gewählten Bereich. */
  useEffect(() => {
    if (!sequence) {
      setAccess(null);
      setFolding(null);
      return;
    }
    if (probeLength === "" || window_ === "" || maxSpan === "") return;

    let cancelled = false;
    setBusy(true);
    const timer = globalThis.setTimeout(() => {
      Promise.all([
        api.targetAccessibility({
          sequence,
          probe_length: probeLength,
          window: window_,
          max_span: maxSpan,
        }),
        api.targetFold(sequence, range.start, range.end),
      ])
        .then(([profil, faltung]) => {
          if (cancelled) return;
          setAccess(profil);
          setFolding(faltung);
          setError(null);
          markComputed("ziel");
        })
        .catch((cause: unknown) => {
          if (cancelled) return;
          setError(
            cause instanceof ApiError
              ? cause.message
              : "Die Rechnung ist fehlgeschlagen.",
          );
        })
        .finally(() => !cancelled && setBusy(false));
    }, 300);

    return () => {
      cancelled = true;
      globalThis.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sequence, range.start, range.end, probeLength, window_, maxSpan]);

  /* ------------------------------------------------------------ Eingabe */

  async function readText(text: string, name?: string) {
    setError(null);
    setFetchNote(null);
    try {
      const { target: gelesen } = await api.targetRead(text, name);
      setTarget({
        name: gelesen.name,
        sequence: gelesen.sequence,
        source: gelesen.source,
        region: null,
      });
      setRegions(gelesen.regions);
      setRange({ start: 1, end: Math.min(DEFAULT_WINDOW, gelesen.length) });
      setRawText("");
    } catch (cause) {
      if (cause instanceof ApiError && cause.detail && typeof cause.detail === "object") {
        const detail = cause.detail as { message?: string };
        setError(detail.message ?? cause.message);
      } else {
        setError(cause instanceof ApiError ? cause.message : "Nicht lesbar.");
      }
    }
  }

  async function fetchTarget(identifier: string) {
    setError(null);
    setChoices([]);
    setFetchNote(null);
    try {
      const result = await api.targetFetch({
        source: fetchSource,
        identifier,
      });
      setFetchNote(result.message);
      if (result.choices.length) {
        setChoices(result.choices);
        return;
      }
      if (result.target) {
        setTarget({
          name: result.target.name,
          sequence: result.target.sequence,
          source: `${result.target.source}${result.from_cache ? " (Zwischenspeicher)" : ""}`,
          region: null,
        });
        setRegions(result.target.regions);
        setRange({ start: 1, end: Math.min(DEFAULT_WINDOW, result.target.length) });
      }
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Abruf fehlgeschlagen.");
    }
  }

  async function saveTarget() {
    if (!target?.name.trim() || !sequence) return;
    try {
      await api.saveTarget({
        name: target.name,
        sequence,
        source: target.source,
        regions,
      });
      refreshLibrary();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Nicht gespeichert.");
    }
  }

  const selectedLength = range.end - range.start + 1;

  /* ------------------------------------------------------------ Ansicht */

  return (
    <div className="flex flex-col gap-4">
      {error && <Notice level="bad">{error}</Notice>}

      {/* ------------------------------------------------- Ziel holen --- */}
      <Card
        title="Ziel-RNA"
        subtitle={
          target && sequence
            ? `${target.name} · ${length} Basen · ${target.source}`
            : "einfügen, hochladen oder aus einer Datenbank holen"
        }
        actions={
          sequence ? (
            <>
              <button type="button" className="ol-button" onClick={saveTarget}>
                speichern
              </button>
              <button
                type="button"
                className="ol-button"
                onClick={() => {
                  setTarget(null);
                  setRegions([]);
                  setAccess(null);
                  setFolding(null);
                }}
              >
                verwerfen
              </button>
            </>
          ) : undefined
        }
      >
        {!sequence && (
          <div className="flex flex-col gap-4">
            <Field
              label="Sequenz einfügen"
              helpId="field.target"
              hint="Rohsequenz, FASTA oder GenBank — das Format wird erkannt. DNA wird zu RNA."
            >
              <textarea
                className="ol-textarea ol-mono"
                rows={5}
                value={rawText}
                onChange={(event) => setRawText(event.target.value)}
                placeholder="ACGUACGU… oder >NM_000546.6 …"
              />
            </Field>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="ol-button"
                data-variant="primary"
                onClick={() => readText(rawText)}
                disabled={!rawText.trim()}
              >
                übernehmen
              </button>
              <button
                type="button"
                className="ol-button"
                onClick={() => fileRef.current?.click()}
              >
                Datei öffnen
              </button>
              <input
                ref={fileRef}
                type="file"
                accept=".fa,.fasta,.gb,.gbk,.genbank,.txt"
                className="hidden"
                onChange={async (event) => {
                  const datei = event.target.files?.[0];
                  if (!datei) return;
                  await readText(await datei.text(), datei.name);
                  event.target.value = "";
                }}
              />
            </div>

            <div
              className="grid gap-3 pt-3 sm:grid-cols-[160px_minmax(0,1fr)_auto]"
              style={{ borderTop: "1px solid var(--border)" }}
            >
              <Field label="Datenbank" role="settings">
                <select
                  className="ol-select"
                  value={fetchSource}
                  onChange={(event) =>
                    setFetchSource(event.target.value as typeof fetchSource)
                  }
                >
                  <option value="ncbi">NCBI</option>
                  <option value="ensembl">Ensembl</option>
                  <option value="rnacentral">RNAcentral</option>
                </select>
              </Field>
              <Field
                label="Kennung oder Gensymbol"
                hint={
                  fetchSource === "ensembl"
                    ? "z. B. TP53 oder ENST00000269305"
                    : fetchSource === "ncbi"
                      ? "z. B. NM_000546"
                      : "z. B. URS00000478B7"
                }
              >
                <input
                  className="ol-input ol-mono"
                  data-role="input"
                  value={fetchId}
                  onChange={(event) => setFetchId(event.target.value)}
                />
              </Field>
              <div className="flex items-end">
                <button
                  type="button"
                  className="ol-button"
                  onClick={() => fetchTarget(fetchId)}
                  disabled={!fetchId.trim()}
                >
                  holen
                </button>
              </div>
            </div>

            {fetchNote && <Notice level="info">{fetchNote}</Notice>}

            {choices.length > 0 && (
              <table className="ol-table">
                <caption
                  className="pb-2 text-left text-xs"
                  style={{ color: "var(--text-faint)", captionSide: "top" }}
                >
                  Welches Transkript? Kanonisches und längstes sind
                  gekennzeichnet — die Wahl gehört dem Nutzer, nicht dem Programm.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Kennung</th>
                    <th scope="col">Typ</th>
                    <th scope="col">Länge</th>
                    <th scope="col" />
                  </tr>
                </thead>
                <tbody>
                  {choices.map((choice) => (
                    <tr key={choice.id}>
                      <td className="ol-mono" style={{ textAlign: "left" }}>
                        {choice.name}
                        {choice.canonical && (
                          <span className="ol-chip ol-role-result ml-2">
                            kanonisch
                          </span>
                        )}
                        {choice.longest && (
                          <span className="ol-chip ol-role-settings ml-2">
                            längstes
                          </span>
                        )}
                      </td>
                      <td>{choice.biotype ?? "—"}</td>
                      <td className="ol-mono tabular-nums">{choice.length}</td>
                      <td>
                        <button
                          type="button"
                          className="ol-button"
                          style={{ padding: "1px 8px", fontSize: 11 }}
                          onClick={() => fetchTarget(choice.id)}
                        >
                          holen
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {library.length > 0 && (
              <div className="pt-3" style={{ borderTop: "1px solid var(--border)" }}>
                <h3
                  className="mb-2 text-xs font-semibold"
                  style={{ color: "var(--text-muted)" }}
                >
                  Gespeicherte Ziele
                </h3>
                <ul className="flex flex-wrap gap-2">
                  {library.map((eintrag) => (
                    <li key={eintrag.id}>
                      <button
                        type="button"
                        className="ol-button"
                        style={{ fontSize: 11 }}
                        onClick={() => {
                          setTarget({
                            name: eintrag.name,
                            sequence: eintrag.sequence,
                            source: eintrag.source,
                            region: null,
                          });
                          setRegions(eintrag.regions);
                          setRange({
                            start: 1,
                            end: Math.min(DEFAULT_WINDOW, eintrag.length),
                          });
                        }}
                      >
                        {eintrag.name}
                        <span style={{ color: "var(--text-faint)" }}>
                          {" "}
                          {eintrag.length} nt
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {sequence && (
          <>
            <div className="mb-3 grid gap-3 sm:grid-cols-4">
              <Field label="Name">
                <input
                  className="ol-input"
                  data-role="input"
                  value={target?.name ?? ""}
                  onChange={(event) => patchTarget({ name: event.target.value })}
                />
              </Field>
              <Field label="Bereich von" helpId="field.region" role="settings">
                <NumberInput
                  value={range.start}
                  onChange={(wert) =>
                    typeof wert === "number" &&
                    setRange((alt) => ({ ...alt, start: Math.max(1, wert) }))
                  }
                  step={1}
                  min={1}
                />
              </Field>
              <Field label="bis" helpId="field.region" role="settings">
                <NumberInput
                  value={range.end}
                  onChange={(wert) =>
                    typeof wert === "number" &&
                    setRange((alt) => ({ ...alt, end: Math.min(length, wert) }))
                  }
                  step={1}
                  min={1}
                />
              </Field>
              <Field label="Im Ziel suchen" role="settings">
                <input
                  className="ol-input ol-mono"
                  data-role="settings"
                  type="search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="z. B. GGUA"
                />
              </Field>
            </div>

            <SequenceText
              sequence={sequence}
              regions={regions}
              range={range}
              search={search}
              onPick={(position) =>
                setRange({
                  start: Math.max(1, position - 50),
                  end: Math.min(length, position + 50),
                })
              }
            />
          </>
        )}
      </Card>

      {/* ------------------------------------------------ Spuren --------- */}
      {sequence && (
        <Card
          title="Zugänglichkeit und Faltung"
          subtitle={`Bereich ${range.start}–${range.end} (${selectedLength} Basen)${
            busy ? " · rechnet …" : ""
          }`}
          helpId="result.accessibility"
        >
          <Overview
            length={length}
            regions={regions}
            accessibility={access}
            selection={range}
            onSelect={setRange}
          />

          <div className="mt-3">
            <TargetMap
              sequence={sequence}
              regions={regions}
              folding={folding}
              accessibility={access}
              range={range}
            />
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <Field
              label="Sondenlänge"
              helpId="field.probe_length"
              role="settings"
              hint="Wie lang der Arm ist, der hier binden soll"
            >
              <NumberInput value={probeLength} onChange={setProbeLength} step={1} min={1} />
            </Field>
            <Field label="Fensterbreite" helpId="field.plfold_window" role="settings">
              <NumberInput value={window_} onChange={setWindow} step={10} min={2} />
            </Field>
            <Field label="Maximalspannweite" helpId="field.plfold_span" role="settings">
              <NumberInput value={maxSpan} onChange={setMaxSpan} step={10} min={2} />
            </Field>
          </div>

          {access?.available && (
            <p className="mt-2 text-xs" style={{ color: "var(--text-faint)" }}>
              {access.method}
              {access.chunks > 1 &&
                ` · in ${access.chunks} Stücken gerechnet, ${formatNumber(
                  access.seconds,
                  2,
                )} s`}
            </p>
          )}

          {folding && !folding.available && folding.note && (
            <div className="mt-3">
              <Notice level="info" title="Gesamtfaltung ausgelassen">
                {folding.note}
              </Notice>
            </div>
          )}

          {folding?.available && (
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              {folding.mfe && (
                <ResultNumber label="MFE des Bereichs" quantity={folding.mfe} helpId="result.mfe" />
              )}
              {folding.ensemble_energy && (
                <ResultNumber
                  label="Ensemble-Energie"
                  quantity={folding.ensemble_energy}
                  helpId="result.ensemble"
                />
              )}
            </div>
          )}
        </Card>
      )}

      {!sequence && (
        <Card title="Zugänglichkeit und Faltung">
          <Empty>Erst eine Ziel-RNA setzen.</Empty>
        </Card>
      )}

      <Handoff
        label="Spaltstellen suchen"
        disabled={!sequence}
        reason="Erst eine Ziel-RNA setzen"
        onClick={() => {
          patchTarget({ region: { start: range.start, end: range.end } });
          markComputed("ziel");
          navigate("/entwurf");
        }}
      />
    </div>
  );
}
