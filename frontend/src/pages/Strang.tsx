/* Seite "Strang" (PHASEN.md 3.4).
 *
 * Links die Sequenzkarte, rechts die Befundliste nach Schweregrad sortiert.
 * Ein Klick auf einen Warnmarker in der Karte rollt zur Erklärung, ein Klick
 * auf einen Befund hebt seinen Bereich in der Karte hervor — beide Richtungen,
 * damit man nicht zählen muss, wo etwas liegt.
 *
 * Darunter die Vergleichsansicht: zwei bis drei Varianten, Karten exakt
 * übereinander, gleiche Zellbreite und gleicher linker Rand. Nur so lässt sich
 * ablesen, was eine Änderung bewirkt hat.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "../api";
import { Handoff } from "../components/AreaShell";
import { HelpTip } from "../components/HelpTip";
import {
  DEFAULT_CELL,
  MAX_CELL,
  MIN_CELL,
  SEVERITY_COLOR,
  SequenceMap,
  type MapSelection,
} from "../components/SequenceMap";
import {
  Card,
  Empty,
  Notice,
  ResultNumber,
  formatNumber,
} from "../components/ui";
import { exportPng, exportSvg, safeFilename } from "../lib/svgExport";
import { useStore } from "../state/store";
// Die Befunde kommen bereits nach Schweregrad sortiert aus dem Backend.
import type { FindingView, StrandView } from "../types";

/** Eine festgehaltene Variante samt frisch gerechnetem Ergebnis. */
interface Variant {
  name: string;
  sequence: string;
  data: StrandView | null;
}

/* ------------------------------------------------------------ Befundliste */

function FindingList({
  data,
  selected,
  onSelect,
  refs,
}: {
  data: StrandView;
  selected: FindingView | null;
  onSelect: (finding: FindingView | null) => void;
  refs: React.MutableRefObject<Map<string, HTMLLIElement>>;
}) {
  const critical = data.critical;
  if (!critical) return null;

  const key = (finding: FindingView) =>
    `${finding.code}-${finding.start}-${finding.end}`;

  return (
    <Card
      title="Befunde"
      subtitle={
        critical.findings.length === 0
          ? "nichts zu beanstanden"
          : `${critical.counts.kritisch} kritisch · ${critical.counts.warnung} Warnungen · ${critical.counts.hinweis} Hinweise`
      }
      helpId="result.findings"
    >
      {critical.findings.length === 0 ? (
        <Empty>
          Keiner der geprüften Punkte ist auffällig. Geprüft wurde:{" "}
          {critical.checked.join(", ")}.
        </Empty>
      ) : (
        <ul className="flex flex-col gap-2">
          {critical.findings.map((finding) => {
            const id = key(finding);
            const aktiv = selected !== null && key(selected) === id;
            return (
              <li
                key={id}
                ref={(node) => {
                  if (node) refs.current.set(id, node);
                  else refs.current.delete(id);
                }}
              >
                <button
                  type="button"
                  className="w-full rounded-lg p-2 text-left"
                  onClick={() => onSelect(aktiv ? null : finding)}
                  aria-pressed={aktiv}
                  style={{
                    border: `1px solid ${
                      aktiv ? "var(--role-result)" : "var(--border)"
                    }`,
                    background: aktiv
                      ? "color-mix(in srgb, var(--role-result) 8%, transparent)"
                      : "transparent",
                    cursor: "pointer",
                  }}
                >
                  <span className="flex items-start gap-2">
                    <span
                      aria-hidden="true"
                      className="mt-1 shrink-0"
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: 2,
                        background: SEVERITY_COLOR[finding.severity],
                      }}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-baseline gap-2">
                        <span className="text-sm font-medium">
                          {finding.title}
                        </span>
                        <span
                          className="ol-mono text-[11px]"
                          style={{ color: "var(--text-faint)" }}
                        >
                          {finding.start === finding.end
                            ? `Position ${finding.start}`
                            : `Position ${finding.start}–${finding.end}`}
                        </span>
                      </span>
                      <span
                        className="mt-0.5 block text-xs"
                        style={{ color: "var(--text-muted)" }}
                      >
                        {finding.message}
                      </span>
                      {aktiv && finding.detail && (
                        <span
                          className="mt-1 block text-xs"
                          style={{ color: "var(--text-faint)" }}
                        >
                          {finding.detail}
                        </span>
                      )}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {critical.skipped.length > 0 && (
        <div className="mt-3">
          <Notice level="info" title="Nicht geprüft">
            <ul className="list-inside list-disc">
              {critical.skipped.map((entry) => (
                <li key={entry}>{entry}</li>
              ))}
            </ul>
          </Notice>
        </div>
      )}

      <p className="mt-3 text-xs" style={{ color: "var(--text-faint)" }}>
        Schwellen: Haarnadel unter {critical.thresholds.hairpin_kcal} kcal/mol,
        Selbstdimer unter {critical.thresholds.homodimer_kcal} kcal/mol, Arme ab{" "}
        {critical.thresholds.min_arm_length} Nukleotiden.
      </p>
    </Card>
  );
}

/* ------------------------------------------------------------------ Seite */

export function Strang({ navigate }: { navigate: (path: string) => void }) {
  const { state, markComputed, addComparison, clearComparison } = useStore();
  const sequence = state.activeOligo?.sequence ?? "";
  const name = state.activeOligo?.name ?? "Unbenannt";

  const [data, setData] = useState<StrandView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cell, setCell] = useState(DEFAULT_CELL);
  const [selected, setSelected] = useState<FindingView | null>(null);
  // Die Liste der festgehaltenen Straenge steht im globalen Zustand; hier
  // liegen nur ihre gerechneten Ergebnisse, die beim Anzeigen frisch geholt
  // werden.
  const [variants, setVariants] = useState<Variant[]>([]);

  const svgRef = useRef<HTMLDivElement>(null);
  const findingRefs = useRef(new Map<string, HTMLLIElement>());

  useEffect(() => {
    if (!sequence.trim()) {
      setData(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setBusy(true);
    const timer = window.setTimeout(() => {
      api
        .strand(sequence)
        .then((result) => {
          if (cancelled) return;
          setData(result);
          setSelected(null);
          setError(null);
          if (result.problems.length === 0 && result.oligo.length > 0) {
            markComputed("strang");
          }
        })
        .catch((cause: unknown) => {
          if (cancelled) return;
          setData(null);
          setError(
            cause instanceof ApiError
              ? cause.message
              : "Der Strang ließ sich nicht berechnen.",
          );
        })
        .finally(() => !cancelled && setBusy(false));
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
    // `markComputed` bewusst nicht in der Liste — es wechselt mit jedem
    // Zustandswechsel und würde die Rechnung endlos neu anstoßen.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sequence]);

  // Zu jedem festgehaltenen Strang das Ergebnis holen. Gespeichert ist nur
  // der Text — so gilt eine geaenderte Monomerdatei auch fuer die Varianten.
  useEffect(() => {
    let cancelled = false;
    if (state.comparison.length === 0) {
      setVariants([]);
      return;
    }
    Promise.all(
      state.comparison.map(async (entry) => {
        try {
          return { ...entry, data: await api.strand(entry.sequence, false) };
        } catch {
          return { ...entry, data: null };
        }
      }),
    ).then((geladen) => {
      if (!cancelled) setVariants(geladen);
    });
    return () => {
      cancelled = true;
    };
  }, [state.comparison]);

  /** Klick auf einen Warnmarker in der Karte: zur Erklärung rollen. */
  const pickFinding = useCallback((finding: FindingView) => {
    setSelected(finding);
    const id = `${finding.code}-${finding.start}-${finding.end}`;
    findingRefs.current
      .get(id)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);

  const highlight: MapSelection | null = useMemo(
    () => (selected ? { start: selected.start, end: selected.end } : null),
    [selected],
  );

  const addVariant = () => {
    if (!data || data.problems.length > 0) return;
    addComparison({ name, sequence, notes: state.activeOligo?.notes ?? "" });
  };

  const currentSvg = () =>
    svgRef.current?.querySelector("svg") as SVGSVGElement | null;

  if (!sequence.trim()) {
    return (
      <div className="flex flex-col gap-4">
        <Card title="Strang" subtitle="Sequenzkarte und kritische Stellen">
          <Empty>
            Es ist kein DNAzym gesetzt. Die Sequenz gehört in die Kopfzeile oder
            in den Steckbrief.
          </Empty>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {error && <Notice level="bad">{error}</Notice>}

      {data && data.problems.length > 0 && (
        <Notice
          level="bad"
          title={`${data.problems.length} unklare ${
            data.problems.length === 1 ? "Stelle" : "Stellen"
          } — es wird nicht gerechnet`}
        >
          <ul className="list-inside list-disc">
            {data.problems.map((problem) => (
              <li key={`${problem.position}-${problem.text}`}>
                <strong className="ol-mono">Position {problem.position}</strong>{" "}
                {problem.message}
              </li>
            ))}
          </ul>
        </Notice>
      )}

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        {/* ---------------------------------------------- Sequenzkarte --- */}
        <Card
          title="Sequenzkarte"
          subtitle={
            data?.parts?.found
              ? `Kern ${data.parts.core?.name} erkannt`
              : "kein katalytischer Kern erkannt"
          }
          actions={
            <>
              <label
                className="flex items-center gap-1.5 text-xs"
                style={{ color: "var(--text-muted)" }}
              >
                Zoom
                <input
                  type="range"
                  min={MIN_CELL}
                  max={MAX_CELL}
                  value={cell}
                  onChange={(event) => setCell(Number(event.target.value))}
                  aria-label="Zellbreite der Sequenzkarte"
                  style={{ width: 80 }}
                />
              </label>
              <button
                type="button"
                className="ol-button"
                onClick={() => {
                  const svg = currentSvg();
                  if (svg) exportSvg(svg, safeFilename(name, "svg"));
                }}
                disabled={!data?.oligo.length}
              >
                SVG
              </button>
              <button
                type="button"
                className="ol-button"
                onClick={() => {
                  const svg = currentSvg();
                  if (svg) {
                    exportPng(svg, safeFilename(name, "png")).catch(() =>
                      setError("Das PNG ließ sich nicht erzeugen."),
                    );
                  }
                }}
                disabled={!data?.oligo.length}
              >
                PNG
              </button>
            </>
          }
        >
          {busy && !data && <Empty>rechnet …</Empty>}

          {data && data.problems.length === 0 && (
            <>
              <div className="overflow-x-auto" ref={svgRef}>
                <SequenceMap
                  oligo={data.oligo}
                  parts={data.parts}
                  folding={data.folding}
                  critical={data.critical}
                  cell={cell}
                  highlight={highlight}
                  onPickFinding={pickFinding}
                  title={`Sequenzkarte von ${name}`}
                />
              </div>

              {selected && (
                <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
                  Hervorgehoben: {selected.title} (Position {selected.start}
                  {selected.end !== selected.start && `–${selected.end}`}).{" "}
                  <button
                    type="button"
                    className="underline"
                    style={{ color: "var(--role-result)" }}
                    onClick={() => setSelected(null)}
                  >
                    Hervorhebung lösen
                  </button>
                </p>
              )}

              <p className="mt-2 text-xs" style={{ color: "var(--text-faint)" }}>
                Beim Überfahren einer Position stehen Nummer, Baustein, Rückgrat,
                Paarungspartner und Befunde. Ein Klick auf einen Marker in der
                Warnspur rollt zur Erklärung.
              </p>
            </>
          )}
        </Card>

        {/* ------------------------------------------------- Seitenspalte */}
        <div className="flex flex-col gap-4">
          {data?.folding && (
            <Card
              title="Faltung"
              subtitle={data.folding.available ? undefined : "nicht verfügbar"}
              helpId="result.folding"
            >
              {!data.folding.available ? (
                <Notice level="warn">{data.folding.note}</Notice>
              ) : (
                <>
                  <div className="grid gap-4">
                    {data.folding.mfe && (
                      <ResultNumber
                        label="MFE-Struktur"
                        quantity={data.folding.mfe}
                        helpId="result.mfe"
                        copy
                      />
                    )}
                    {data.folding.ensemble_energy && (
                      <ResultNumber
                        label="Ensemble-Energie"
                        quantity={data.folding.ensemble_energy}
                        helpId="result.ensemble"
                      />
                    )}
                    {data.folding.homodimer_energy && (
                      <ResultNumber
                        label="Homodimer"
                        quantity={data.folding.homodimer_energy}
                        helpId="result.homodimer"
                      />
                    )}
                  </div>

                  <div
                    className="ol-mono mt-3 overflow-x-auto whitespace-pre pt-3 text-xs"
                    style={{
                      borderTop: "1px solid var(--border)",
                      color: "var(--text-muted)",
                    }}
                  >
                    {data.folding.sequence_used}
                    {"\n"}
                    {data.folding.structure}
                  </div>

                  {data.folding.approximated.length > 0 && (
                    <div className="mt-3">
                      <Notice level="info" title="Genähert">
                        <ul className="list-inside list-disc">
                          {data.folding.approximated.map((entry) => (
                            <li key={entry}>{entry}</li>
                          ))}
                        </ul>
                      </Notice>
                    </div>
                  )}
                </>
              )}
            </Card>
          )}

          {data && (
            <FindingList
              data={data}
              selected={selected}
              onSelect={setSelected}
              refs={findingRefs}
            />
          )}

          {data?.parts?.found && data.parts.core && (
            <Card title="Katalytischer Kern" subtitle={data.parts.core.name}>
              <dl
                className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs"
                style={{ color: "var(--text-muted)" }}
              >
                <dt>Sequenz</dt>
                <dd className="ol-mono text-right">{data.parts.core.sequence}</dd>
                <dt>Länge</dt>
                <dd className="ol-mono text-right">
                  {data.parts.core.length} nt
                </dd>
                <dt>Spaltstellen</dt>
                <dd className="text-right">
                  {data.parts.core.preferred_junctions.join(", ")}
                </dd>
                <dt>Metallionen</dt>
                <dd className="text-right">
                  {data.parts.core.metal_requirement ?? "—"}
                </dd>
              </dl>
              {data.parts.core.quelle && (
                <p className="mt-2 text-xs" style={{ color: "var(--text-faint)" }}>
                  {data.parts.core.quelle}
                </p>
              )}
              {data.parts.approximated.length > 0 && (
                <div className="mt-3">
                  <Notice level="warn" title="Über das Analogon erkannt">
                    <ul className="list-inside list-disc">
                      {data.parts.approximated.map((entry) => (
                        <li key={entry}>{entry}</li>
                      ))}
                    </ul>
                  </Notice>
                </div>
              )}
            </Card>
          )}
        </div>
      </div>

      {/* ------------------------------------------------- Vergleich ----- */}
      <Card
        title="Varianten vergleichen"
        subtitle="Karten exakt übereinander, gleiche Zellbreite"
        actions={
          <>
            <button
              type="button"
              className="ol-button"
              onClick={addVariant}
              disabled={
                !data ||
                data.problems.length > 0 ||
                state.comparison.length >= 2 ||
                state.comparison.some((entry) => entry.sequence === sequence)
              }
              title={
                state.comparison.length >= 2
                  ? "Mehr als drei Karten untereinander liest niemand"
                  : state.comparison.some((e) => e.sequence === sequence)
                    ? "Dieser Strang ist schon festgehalten"
                    : "Den aktuellen Strang zum Vergleich festhalten"
              }
            >
              aktuellen Strang festhalten
            </button>
            {state.comparison.length > 0 && (
              <button type="button" className="ol-button" onClick={clearComparison}>
                leeren
              </button>
            )}
          </>
        }
      >
        {state.comparison.length === 0 ? (
          <Empty>
            Noch nichts festgehalten. Halte den aktuellen Strang fest, ändere ihn
            dann im Steckbrief oder in der Kopfzeile — und du siehst beide Karten
            Position für Position untereinander.
          </Empty>
        ) : (
          <div className="flex flex-col gap-4">
            {[
              ...variants.map((variant, index) => ({
                ...variant,
                label: `Variante ${index + 1}`,
              })),
              ...(data && data.problems.length === 0
                ? [{ name, sequence, data, label: "jetzt" }]
                : []),
            ].map((variant, index) => (
              <div key={`${variant.label}-${index}`}>
                <p className="mb-1 flex flex-wrap items-baseline gap-2 text-xs">
                  <span className="font-medium">{variant.label}</span>
                  <span style={{ color: "var(--text-muted)" }}>
                    {variant.name}
                  </span>
                  <span
                    className="ol-mono"
                    style={{ color: "var(--text-faint)" }}
                  >
                    {variant.data ? `${variant.data.oligo.length} nt` : "…"}
                    {variant.data?.folding?.mfe?.value != null &&
                      ` · MFE ${formatNumber(
                        variant.data.folding.mfe.value,
                      )} kcal/mol`}
                  </span>
                </p>
                {variant.data ? (
                  <div className="overflow-x-auto">
                    <SequenceMap
                      oligo={variant.data.oligo}
                      parts={variant.data.parts}
                      folding={variant.data.folding}
                      critical={variant.data.critical}
                      cell={cell}
                      title={`Sequenzkarte von ${variant.name}`}
                    />
                  </div>
                ) : (
                  <Empty>wird geladen …</Empty>
                )}
              </div>
            ))}
            <p className="text-xs" style={{ color: "var(--text-faint)" }}>
              Die Karten teilen sich Zellbreite und linken Rand, stehen also
              Position für Position übereinander. Unterschiedlich lange Stränge
              beginnen trotzdem links bündig bei Position 1.
            </p>
          </div>
        )}
      </Card>

      <Handoff
        label="Masse und MS berechnen"
        disabled={!data || data.problems.length > 0}
        reason="Erst die unklaren Stellen klären"
        onClick={() => navigate("/")}
      />

      <p className="text-xs" style={{ color: "var(--text-faint)" }}>
        Die Faltung rechnet ViennaRNA mit DNA-Parametern.{" "}
        <HelpTip id="method.dna_parameters" />
      </p>
    </div>
  );
}
