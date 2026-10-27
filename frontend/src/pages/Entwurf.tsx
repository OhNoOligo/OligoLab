/* Die Entwurfsseite (PHASEN.md 5.6).
 *
 * Aufbau von oben nach unten: Einstellungen, das Zugänglichkeitsprofil mit
 * den Kandidaten als Marken, die Rangliste, und darunter — für den
 * ausgewählten Kandidaten — die Paarungsdarstellung.
 *
 * Der Hinweis aus 5.4 steht sichtbar über der Tabelle und nicht im
 * Kleingedruckten: die Punktzahl ordnet, sie urteilt nicht.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, type DesignBody } from "../api";
import { PairingMap } from "../components/PairingMap";
import {
  Card,
  Chip,
  Empty,
  Field,
  Notice,
  NumberInput,
  Rating,
} from "../components/ui";
import { exportSvg, safeFilename } from "../lib/svgExport";
import { useStore } from "../state/store";
import type {
  CandidateView,
  DesignView,
  ModifyResultView,
  SnapshotView,
  StrandView,
} from "../types";

/* ------------------------------------------------------- Einstellungen */

interface Settings {
  arm5: number | "";
  arm3: number | "";
  armDgTarget: number | "";
  maxImbalance: number | "";
  selfFoldLimit: number | "";
  includePoor: boolean;
  withStructure: boolean;
  limit: number | "";
}

const DEFAULTS: Settings = {
  arm5: 9,
  arm3: 9,
  armDgTarget: -20,
  maxImbalance: 4,
  selfFoldLimit: -2,
  includePoor: false,
  withStructure: true,
  limit: 200,
};

const num = (value: number | "", fallback: number) =>
  value === "" ? fallback : value;

/* ------------------------------------------------------------ Sortieren */

type SortKey =
  | "score"
  | "position"
  | "quality"
  | "arm_dg_sum"
  | "imbalance"
  | "self_fold_mfe"
  | "accessibility";

const QUALITY_ORDER: Record<string, number> = { gut: 0, mäßig: 1, schlecht: 2 };

function sortValue(candidate: CandidateView, key: SortKey): number {
  switch (key) {
    case "position":
      return candidate.site.position;
    case "quality":
      return QUALITY_ORDER[candidate.site.quality] ?? 9;
    case "arm_dg_sum":
      return candidate.arm_dg_sum ?? Number.POSITIVE_INFINITY;
    case "imbalance":
      return candidate.imbalance ?? Number.POSITIVE_INFINITY;
    case "self_fold_mfe":
      // Weniger negativ ist besser, darum umgedreht.
      return -(candidate.self_fold_mfe ?? 0);
    case "accessibility":
      return -(candidate.site.accessibility ?? -1);
    default:
      return -candidate.score;
  }
}

const RATING_LABEL: Record<string, string> = {
  good: "gut",
  warn: "mittel",
  bad: "schwach",
};

const COLUMNS: { key: SortKey; label: string; help: string }[] = [
  { key: "position", label: "Position", help: "result.candidate.position" },
  { key: "quality", label: "Junktion", help: "result.candidate.junction" },
  { key: "arm_dg_sum", label: "ΣΔG", help: "result.candidate.arm_dg" },
  { key: "imbalance", label: "Δ Arme", help: "result.candidate.imbalance" },
  {
    key: "self_fold_mfe",
    label: "Eigenfaltung",
    help: "result.candidate.self_fold",
  },
  {
    key: "accessibility",
    label: "Zugang",
    help: "result.candidate.accessibility",
  },
  { key: "score", label: "Punktzahl", help: "result.candidate.score" },
];

/* --------------------------------------------------------------- Profil */

function Profile({
  design,
  selected,
  onSelect,
}: {
  design: DesignView;
  selected: number | null;
  onSelect: (position: number) => void;
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const profile = design.accessibility;
  if (!profile || !profile.available) {
    return (
      <Empty>
        Ohne Faltung gibt es kein Profil. Die Junktionen und ihre Güte stehen
        trotzdem in der Tabelle.
      </Empty>
    );
  }

  const width = 900;
  const height = 150;
  const left = 34;
  const bottom = 118;
  const top = 14;
  const values = profile.profile;
  const span = Math.max(1, values.length - 1);
  const x = (index: number) => left + (index / span) * (width - left - 14);
  const y = (value: number) => bottom - value * (bottom - top);

  // Maximum je Pixelspalte, nicht Mittelwert: eine offene Stelle darf nicht
  // von ihren verschlossenen Nachbarn weggemittelt werden.
  const columns = Math.min(values.length, width - left - 14);
  const points: string[] = [];
  for (let column = 0; column < columns; column += 1) {
    const from = Math.floor((column * values.length) / columns);
    const to = Math.max(
      from + 1,
      Math.floor(((column + 1) * values.length) / columns),
    );
    let best: number | null = null;
    for (let index = from; index < to; index += 1) {
      const value = values[index] ?? null;
      if (value !== null && (best === null || value > best)) best = value;
    }
    if (best !== null)
      points.push(`${x(from).toFixed(1)},${y(best).toFixed(1)}`);
  }

  return (
    <figure className="m-0">
      <div className="mb-1 flex items-center justify-between">
        <figcaption className="text-xs" style={{ color: "var(--text-faint)" }}>
          Wahrscheinlichkeit, dass ab dieser Position {profile.probe_length}{" "}
          Nukleotide offen sind. Jede Marke ist ein Kandidat.
        </figcaption>
        <button
          type="button"
          className="ol-button text-xs"
          onClick={() =>
            svgRef.current &&
            exportSvg(svgRef.current, safeFilename("profil", "svg"))
          }
        >
          SVG
        </button>
      </div>
      <div className="overflow-x-auto">
        <svg
          ref={svgRef}
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label="Zugänglichkeitsprofil mit den Kandidaten"
        >
          {[0, 0.5, 1].map((tick) => (
            <g key={tick}>
              <line
                x1={left}
                y1={y(tick)}
                x2={width - 14}
                y2={y(tick)}
                stroke="var(--border)"
                strokeWidth="0.5"
              />
              <text x={4} y={y(tick) + 3} fontSize="9" fill="var(--text-faint)">
                {tick.toFixed(1)}
              </text>
            </g>
          ))}
          <polyline
            points={points.join(" ")}
            fill="none"
            stroke="var(--role-result)"
            strokeWidth="1.2"
          />
          {design.candidates.map((candidate) => {
            const index = candidate.site.position - profile.start;
            if (index < 0 || index >= values.length) return null;
            const istGewaehlt = candidate.site.position === selected;
            return (
              <g
                key={candidate.site.position}
                onClick={() => onSelect(candidate.site.position)}
                style={{ cursor: "pointer" }}
              >
                <title>
                  {`Position ${candidate.site.position} · ${candidate.site.junction} · Punktzahl ${candidate.score.toFixed(2)}`}
                </title>
                <line
                  x1={x(index)}
                  y1={top}
                  x2={x(index)}
                  y2={bottom + 10}
                  stroke={`var(--rating-${candidate.rating})`}
                  strokeWidth={istGewaehlt ? 1.6 : 0.8}
                  strokeDasharray={istGewaehlt ? undefined : "2 3"}
                />
                <circle
                  cx={x(index)}
                  cy={bottom + 14}
                  r={istGewaehlt ? 4 : 2.5}
                  fill={`var(--rating-${candidate.rating})`}
                />
              </g>
            );
          })}
          <text x={left} y={height - 4} fontSize="9" fill="var(--text-faint)">
            {profile.start}
          </text>
          <text
            x={width - 14}
            y={height - 4}
            textAnchor="end"
            fontSize="9"
            fill="var(--text-faint)"
          >
            {profile.end}
          </text>
        </svg>
      </div>
    </figure>
  );
}

/* ------------------------------------------------- Vorher gegen nachher */

const SNAPSHOT_ROWS: {
  key: keyof SnapshotView;
  label: string;
  unit: string;
  digits: number;
}[] = [
  { key: "mass", label: "Masse, entschützt", unit: "g/mol", digits: 2 },
  { key: "tm5", label: "Tm 5'-Arm", unit: "°C", digits: 1 },
  { key: "tm3", label: "Tm 3'-Arm", unit: "°C", digits: 1 },
  { key: "arm_dg_sum", label: "ΣΔG der Arme", unit: "kcal/mol", digits: 2 },
  {
    key: "imbalance",
    label: "Unterschied der Arme",
    unit: "kcal/mol",
    digits: 2,
  },
  { key: "self_fold_mfe", label: "Eigenfaltung", unit: "kcal/mol", digits: 2 },
];

function Comparison({
  before,
  after,
}: {
  before: SnapshotView;
  after: SnapshotView;
}) {
  return (
    <div>
      <table className="w-full text-xs tabular-nums">
        <thead>
          <tr style={{ color: "var(--text-faint)" }}>
            <th className="py-1 text-left font-normal">Größe</th>
            <th className="py-1 text-right font-normal">vorher</th>
            <th className="py-1 text-right font-normal">nachher</th>
            <th className="py-1 text-right font-normal">Änderung</th>
          </tr>
        </thead>
        <tbody>
          {SNAPSHOT_ROWS.map((row) => {
            const alt = before[row.key] as number | null;
            const neu = after[row.key] as number | null;
            const diff = alt === null || neu === null ? null : neu - alt;
            return (
              <tr
                key={row.key}
                style={{ borderTop: "1px solid var(--border)" }}
              >
                <td className="py-1">{row.label}</td>
                <td className="ol-mono py-1 text-right">
                  {alt === null ? "—" : alt.toFixed(row.digits)}
                </td>
                <td className="ol-mono py-1 text-right">
                  {neu === null ? "—" : neu.toFixed(row.digits)}
                </td>
                <td
                  className="ol-mono py-1 text-right"
                  style={{
                    color:
                      diff === null || Math.abs(diff) < 1e-9
                        ? "var(--text-faint)"
                        : "var(--role-result)",
                  }}
                >
                  {diff === null
                    ? "—"
                    : Math.abs(diff) < 1e-9
                      ? "unverändert"
                      : `${diff > 0 ? "+" : ""}${diff.toFixed(row.digits)} ${row.unit}`}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {after.tm_approximated.length > 0 && (
        <div className="mt-3">
          <Notice level="warn" title="Der Tm kann die Modifikation nicht sehen">
            Die Nearest-Neighbor-Tabelle kennt diese Bausteine nicht und rechnet
            über ihr natürliches Analogon. „Unverändert" heißt hier also{" "}
            <em>das Modell sieht es nicht</em> — nicht, dass die Modifikation
            nichts bewirkt. Eine LNA hebt den Tm in Wirklichkeit deutlich.
            <ul className="mt-1 list-inside list-disc">
              {after.tm_approximated.slice(0, 6).map((entry) => (
                <li key={entry}>{entry}</li>
              ))}
            </ul>
          </Notice>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------- Die Seite */

export function Entwurf({ navigate }: { navigate: (path: string) => void }) {
  const { state, setOligo, markComputed } = useStore();
  const target = state.activeTarget;

  const [settings, setSettings] = useState<Settings>(DEFAULTS);
  const [design, setDesign] = useState<DesignView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [onlyGood, setOnlyGood] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);

  const [strand, setStrand] = useState<StrandView | null>(null);
  const [pattern, setPattern] = useState("arms_phosphorothioate");
  const [patterns, setPatterns] = useState<{ id: string; label: string }[]>([]);
  const [modified, setModified] = useState<ModifyResultView | null>(null);
  const [modifyBusy, setModifyBusy] = useState(false);

  useEffect(() => {
    api
      .patterns()
      .then((result) => setPatterns(result.patterns))
      .catch(() => setPatterns([]));
  }, []);

  const body = useCallback(
    (): DesignBody => ({
      sequence: target?.sequence ?? "",
      start: target?.region?.start,
      end: target?.region?.end,
      include_poor: settings.includePoor,
      with_structure: settings.withStructure,
      limit: num(settings.limit, 200),
      settings: {
        arm5_length: num(settings.arm5, 9),
        arm3_length: num(settings.arm3, 9),
        arm_dg_target: num(settings.armDgTarget, -20),
        max_imbalance: num(settings.maxImbalance, 4),
        self_fold_limit: num(settings.selfFoldLimit, -2),
      },
      conditions: {
        oligo_conc_nm: state.buffer.oligoConcNm,
        na_mm: state.buffer.naMm,
        k_mm: state.buffer.kMm,
        tris_mm: state.buffer.trisMm,
        mg_mm: state.buffer.mgMm,
        temperature_c: state.buffer.reactionTempC,
      },
    }),
    [target, settings, state.buffer],
  );

  const run = async () => {
    if (!target?.sequence) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.design(body());
      setDesign(result);
      setSelected(result.candidates[0]?.site.position ?? null);
      setModified(null);
      markComputed("entwurf");
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : String(cause));
      setDesign(null);
    } finally {
      setBusy(false);
    }
  };

  const candidates = useMemo(() => {
    if (!design) return [];
    const liste = onlyGood
      ? design.candidates.filter((c) => c.rating === "good")
      : design.candidates;
    return [...liste].sort(
      (a, b) => sortValue(a, sortKey) - sortValue(b, sortKey),
    );
  }, [design, sortKey, onlyGood]);

  const current = useMemo(
    () => design?.candidates.find((c) => c.site.position === selected) ?? null,
    [design, selected],
  );

  /* Eine aufgebrachte Modifikation gehört zu GENAU dem Kandidaten, auf dem
   * sie aufgebracht wurde. Beim Wechsel der Auswahl muss sie weg — sonst
   * zeigte die Paarungsdarstellung den Strang des vorigen Kandidaten unter
   * der Überschrift des neuen. Das hier fängt beide Wege ab: die Tabelle
   * und die Marken im Profil. */
  useEffect(() => {
    setModified(null);
  }, [selected]);

  // Die Farben der Paarungsdarstellung kommen aus den Monomer-Objekten.
  const shownSequence =
    modified?.modification.sequence ?? current?.sequence ?? null;
  useEffect(() => {
    if (!shownSequence) {
      setStrand(null);
      return;
    }
    let abgebrochen = false;
    api
      .strand(shownSequence, false)
      .then((result) => !abgebrochen && setStrand(result))
      .catch(() => !abgebrochen && setStrand(null));
    return () => {
      abgebrochen = true;
    };
  }, [shownSequence]);

  const coreRange = current
    ? {
        start: current.arm5.length + 1,
        end: current.arm5.length + current.core.length,
      }
    : null;

  const applyPattern = async (allowCore = false) => {
    if (!current || !coreRange) return;
    setModifyBusy(true);
    try {
      const result = await api.modify({
        sequence: modified?.modification.sequence ?? current.sequence,
        pattern,
        core_start: coreRange.start,
        core_end: coreRange.end,
        allow_core: allowCore,
        arm5_length: current.arm5.length,
        core_length: current.core.length,
        conditions: {
          oligo_conc_nm: state.buffer.oligoConcNm,
          na_mm: state.buffer.naMm,
          k_mm: state.buffer.kMm,
          tris_mm: state.buffer.trisMm,
          mg_mm: state.buffer.mgMm,
          temperature_c: state.buffer.reactionTempC,
        },
      });
      setModified(result);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : String(cause));
    } finally {
      setModifyBusy(false);
    }
  };

  const takeOver = () => {
    if (!current) return;
    const sequence = modified?.modification.sequence ?? current.sequence;
    setOligo({
      name: `${target?.name ?? "Ziel"} · ${current.site.position}${current.site.junction}`,
      sequence,
      notes:
        `Entworfen gegen ${target?.name ?? "ein Ziel"}, Spaltstelle ` +
        `${current.site.position}/${current.site.position + 1} (${current.site.junction}), ` +
        `Kern ${current.core_id}. Punktzahl ${current.score.toFixed(2)} — ` +
        `eine Rangfolge, keine Vorhersage.`,
    });
    navigate("/steckbrief");
  };

  const downloadCsv = async () => {
    try {
      const text = await api.designCsv(body());
      const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = safeFilename(
        `kandidaten-${target?.name ?? "ziel"}`,
        "csv",
      );
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : String(cause));
    }
  };

  if (!target?.sequence) {
    return (
      <Card title="Entwurf" helpId="field.design">
        <Empty>
          Für einen Entwurf braucht OligoLab erst eine Ziel-RNA.{" "}
          <button
            type="button"
            className="underline"
            style={{ color: "var(--role-input)" }}
            onClick={() => navigate("/ziel")}
          >
            Zum Bereich Ziel
          </button>
        </Empty>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Card
        title="Einstellungen"
        subtitle={`Ziel: ${target.name || "ohne Namen"} · ${target.sequence.length} Basen${
          target.region
            ? ` · Bereich ${target.region.start}–${target.region.end}`
            : ""
        }`}
        helpId="field.design.settings"
        actions={
          <button
            type="button"
            className="ol-button"
            data-role="input"
            onClick={run}
            disabled={busy}
          >
            {busy ? "rechnet …" : "Kandidaten suchen"}
          </button>
        }
      >
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <Field
            label="5'-Arm"
            role="settings"
            helpId="field.arm5"
            htmlFor="arm5"
          >
            <NumberInput
              id="arm5"
              value={settings.arm5}
              min={5}
              step={1}
              onChange={(value) => setSettings({ ...settings, arm5: value })}
            />
          </Field>
          <Field
            label="3'-Arm"
            role="settings"
            helpId="field.arm3"
            htmlFor="arm3"
          >
            <NumberInput
              id="arm3"
              value={settings.arm3}
              min={5}
              step={1}
              onChange={(value) => setSettings({ ...settings, arm3: value })}
            />
          </Field>
          <Field
            label="ΣΔG Zielwert"
            role="settings"
            hint="kcal/mol"
            helpId="field.arm_dg_target"
            htmlFor="dg"
          >
            <NumberInput
              id="dg"
              value={settings.armDgTarget}
              onChange={(value) =>
                setSettings({ ...settings, armDgTarget: value })
              }
            />
          </Field>
          <Field
            label="Unterschied höchstens"
            role="settings"
            hint="kcal/mol"
            helpId="field.max_imbalance"
            htmlFor="imb"
          >
            <NumberInput
              id="imb"
              value={settings.maxImbalance}
              min={0}
              onChange={(value) =>
                setSettings({ ...settings, maxImbalance: value })
              }
            />
          </Field>
          <Field
            label="Eigenfaltung ab"
            role="settings"
            hint="kcal/mol"
            helpId="field.self_fold_limit"
            htmlFor="sf"
          >
            <NumberInput
              id="sf"
              value={settings.selfFoldLimit}
              onChange={(value) =>
                setSettings({ ...settings, selfFoldLimit: value })
              }
            />
          </Field>
          <Field
            label="höchstens Kandidaten"
            role="settings"
            helpId="field.design.limit"
            htmlFor="limit"
          >
            <NumberInput
              id="limit"
              value={settings.limit}
              min={1}
              step={10}
              onChange={(value) => setSettings({ ...settings, limit: value })}
            />
          </Field>
        </div>

        <div className="mt-3 flex flex-wrap gap-4 text-xs">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={settings.includePoor}
              data-help="field.include_poor"
              onChange={(event) =>
                setSettings({ ...settings, includePoor: event.target.checked })
              }
            />
            AC-Junktionen mitnehmen (die schlechteste der vier)
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={settings.withStructure}
              data-help="field.with_structure"
              onChange={(event) =>
                setSettings({
                  ...settings,
                  withStructure: event.target.checked,
                })
              }
            />
            Faltung und Zugänglichkeit mitrechnen (dauert länger)
          </label>
        </div>
      </Card>

      {error && (
        <Notice level="bad" title="Das hat nicht geklappt">
          {error}
        </Notice>
      )}

      {design && (
        <>
          <Notice level="info" title="Was die Punktzahl ist — und was nicht">
            {design.disclaimer}
          </Notice>

          <Card title="Zugänglichkeit und Kandidaten" helpId="result.profile">
            <Profile
              design={design}
              selected={selected}
              onSelect={setSelected}
            />
          </Card>

          <Card
            title={`Rangliste · ${candidates.length} von ${design.candidates.length}`}
            subtitle={
              design.core
                ? `Kern ${design.core.id} (${design.core.sequence.length} Bausteine)`
                : undefined
            }
            helpId="result.candidates"
            actions={
              <>
                <label className="flex items-center gap-1.5 text-xs">
                  <input
                    type="checkbox"
                    checked={onlyGood}
                    onChange={(event) => setOnlyGood(event.target.checked)}
                  />
                  nur grüne
                </label>
                <button
                  type="button"
                  className="ol-button text-xs"
                  onClick={downloadCsv}
                >
                  CSV
                </button>
              </>
            }
          >
            {design.scan_note && (
              <div className="mb-3">
                <Notice level="warn">{design.scan_note}</Notice>
              </div>
            )}

            {candidates.length === 0 ? (
              <Empty>
                Keine Kandidaten. Vielleicht hilft ein kürzerer Arm, ein anderer
                Bereich oder das Mitnehmen der AC-Junktionen.
              </Empty>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs tabular-nums">
                  <thead>
                    <tr style={{ color: "var(--text-faint)" }}>
                      <th className="py-1 text-left font-normal">Güte</th>
                      {COLUMNS.map((column) => (
                        <th
                          key={column.key}
                          className="py-1 text-right font-normal"
                          data-help={column.help}
                        >
                          <button
                            type="button"
                            className="underline-offset-2 hover:underline"
                            onClick={() => setSortKey(column.key)}
                            style={{
                              color:
                                sortKey === column.key
                                  ? "var(--role-result)"
                                  : "inherit",
                              fontWeight: sortKey === column.key ? 600 : 400,
                            }}
                          >
                            {column.label}
                          </button>
                        </th>
                      ))}
                      <th className="py-1 pl-4 text-left font-normal">
                        Arme 5' / 3'
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.map((candidate) => {
                      const istGewaehlt = candidate.site.position === selected;
                      return (
                        <tr
                          key={candidate.site.position}
                          onClick={() => {
                            setSelected(candidate.site.position);
                            setModified(null);
                          }}
                          style={{
                            borderTop: "1px solid var(--border)",
                            cursor: "pointer",
                            background: istGewaehlt
                              ? "color-mix(in srgb, var(--role-result) 10%, transparent)"
                              : undefined,
                          }}
                        >
                          <td className="py-1">
                            <Rating
                              level={candidate.rating}
                              title={
                                candidate.excluded
                                  ? (candidate.exclusion_reason ?? undefined)
                                  : !candidate.binds
                                    ? "Die Arme binden bei diesen Bedingungen nicht."
                                    : undefined
                              }
                            >
                              {RATING_LABEL[candidate.rating]}
                            </Rating>
                          </td>
                          <td className="py-1 text-right">
                            {candidate.site.position}/
                            {candidate.site.position + 1}
                          </td>
                          <td className="py-1 text-right">
                            {candidate.site.junction} · {candidate.site.quality}
                          </td>
                          <td className="py-1 text-right">
                            {candidate.arm_dg_sum?.toFixed(2) ?? "—"}
                          </td>
                          <td className="py-1 text-right">
                            {candidate.imbalance?.toFixed(2) ?? "—"}
                          </td>
                          <td className="py-1 text-right">
                            {candidate.self_fold_mfe?.toFixed(2) ?? "—"}
                          </td>
                          <td className="py-1 text-right">
                            {candidate.site.accessibility === null
                              ? "—"
                              : candidate.site.accessibility.toFixed(3)}
                          </td>
                          <td className="py-1 text-right">
                            {candidate.score.toFixed(3)}
                          </td>
                          <td className="ol-mono py-1 pl-4">
                            {candidate.arm5} / {candidate.arm3}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}

      {current && (
        <Card
          title={`Paarung an ${current.site.position}/${current.site.position + 1}`}
          subtitle={
            modified && !modified.modification.blocked
              ? "mit der aufgebrachten Modifikation"
              : undefined
          }
          helpId="result.pairing"
          actions={
            <button
              type="button"
              className="ol-button"
              data-role="input"
              onClick={takeOver}
            >
              Als Oligo übernehmen
            </button>
          }
        >
          <PairingMap
            candidate={current}
            monomers={strand?.oligo.monomers}
            linkages={strand?.oligo.linkages}
            conjugates={strand?.oligo.conjugates}
            name={`paarung-${current.site.position}`}
          />

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div>
              <h3 className="mb-2 text-xs font-semibold">
                Die sechs Kriterien
              </h3>
              <table className="w-full text-xs tabular-nums">
                <tbody>
                  {current.criteria.map((criterion) => (
                    <tr
                      key={criterion.key}
                      style={{ borderTop: "1px solid var(--border)" }}
                    >
                      <td className="py-1">{criterion.label}</td>
                      <td className="ol-mono py-1 text-right">
                        {criterion.raw === null
                          ? "—"
                          : criterion.raw.toFixed(2)}
                      </td>
                      <td className="ol-mono py-1 text-right">
                        {criterion.score === null
                          ? "nicht gewertet"
                          : criterion.score.toFixed(2)}
                      </td>
                      <td
                        className="ol-mono py-1 text-right"
                        style={{ color: "var(--text-faint)" }}
                      >
                        ×{criterion.weight.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {current.warnings.length > 0 && (
                <ul className="mt-2 list-inside list-disc text-xs">
                  {current.warnings.map((warning) => (
                    <li key={warning} style={{ color: "var(--rating-warn)" }}>
                      {warning}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <h3 className="mb-2 text-xs font-semibold">
                Modifikation aufbringen
              </h3>
              <div className="flex flex-wrap items-end gap-2">
                <Field
                  label="Muster"
                  role="settings"
                  helpId="field.pattern"
                  htmlFor="pat"
                >
                  <select
                    id="pat"
                    className="ol-input"
                    data-role="settings"
                    value={pattern}
                    onChange={(event) => setPattern(event.target.value)}
                  >
                    {patterns.map((entry) => (
                      <option key={entry.id} value={entry.id}>
                        {entry.label}
                      </option>
                    ))}
                  </select>
                </Field>
                <button
                  type="button"
                  className="ol-button"
                  onClick={() => applyPattern(false)}
                  disabled={modifyBusy}
                >
                  aufbringen
                </button>
                {modified && (
                  <button
                    type="button"
                    className="ol-button text-xs"
                    onClick={() => setModified(null)}
                  >
                    zurücksetzen
                  </button>
                )}
              </div>

              {modified?.modification.blocked && (
                <div className="mt-3">
                  <Notice
                    level="bad"
                    title="Das greift in den katalytischen Kern ein"
                  >
                    {modified.modification.message}
                    <button
                      type="button"
                      className="ol-button mt-2 block text-xs"
                      onClick={() => applyPattern(true)}
                    >
                      Ich weiß es und will es trotzdem
                    </button>
                  </Notice>
                </div>
              )}

              {modified?.modification.touched_core && (
                <div className="mt-3">
                  <Notice level="warn" title="Der Kern wurde verändert">
                    {modified.modification.message}
                  </Notice>
                </div>
              )}

              {modified?.before && modified.after && (
                <div className="mt-3">
                  <Comparison before={modified.before} after={modified.after} />
                  <p className="ol-mono mt-2 break-all text-xs">
                    {modified.modification.sequence}
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2 text-xs">
            <Chip role="result" title="Summe über beide Arme">
              ΣΔG {current.arm_dg_sum?.toFixed(2) ?? "—"} kcal/mol
            </Chip>
            <Chip role="result">
              Tm {current.tm5?.tm?.value?.toFixed(1) ?? "—"} /{" "}
              {current.tm3?.tm?.value?.toFixed(1) ?? "—"} °C
            </Chip>
            <Chip role="result">{current.length} Bausteine</Chip>
            {current.tm5?.source === "biopython" && (
              <Chip role="settings" title={current.tm5.parameter_set}>
                {current.tm5.parameter_set}
              </Chip>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
