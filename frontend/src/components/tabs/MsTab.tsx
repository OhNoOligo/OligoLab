/* Reiter "MS" — Ladungsleiter und Isotopenmuster (PHASEN.md 1.4, 1.8).
 *
 * Das Isotopenmuster ist ein Balkendiagramm aus fuenf Balken. Dafuer ist
 * eingebettetes SVG das richtige Mittel: es erbt die Farbtoken, kann hell und
 * dunkel, und spart die gesamte Plotly-Bibliothek. Die echten Diagramme der
 * spaeteren Phasen (Bogendiagramm, Zugaenglichkeitsprofil) bekommen eine
 * Diagrammbibliothek, sobald sie gebraucht wird.
 */

import { useEffect, useState } from "react";
import { api, ApiError } from "../../api";
import type { ExactResult } from "../../types";
import { Card, Empty, Field, Notice, NumberInput, formatNumber } from "../ui";

function IsotopeChart({
  peaks,
}: {
  peaks: { mass: number; intensity_rel: number }[];
}) {
  if (peaks.length === 0) return null;

  const width = 420;
  const height = 150;
  const padding = { top: 8, right: 8, bottom: 34, left: 34 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const barWidth = plotWidth / peaks.length;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      style={{ maxWidth: width }}
      role="img"
      aria-label="Isotopenmuster: die fünf häufigsten Peaks mit relativer Intensität"
    >
      {[0, 0.5, 1].map((fraction) => {
        const y = padding.top + plotHeight * (1 - fraction);
        return (
          <g key={fraction}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={y}
              y2={y}
              stroke="var(--border)"
              strokeWidth={1}
            />
            <text
              x={padding.left - 6}
              y={y + 3}
              textAnchor="end"
              fontSize={9}
              fill="var(--text-faint)"
            >
              {fraction === 0 ? "0" : fraction === 1 ? "100" : "50"}
            </text>
          </g>
        );
      })}

      {peaks.map((peak, index) => {
        const barHeight = plotHeight * peak.intensity_rel;
        const x = padding.left + index * barWidth + barWidth * 0.2;
        return (
          <g key={peak.mass}>
            <rect
              x={x}
              y={padding.top + plotHeight - barHeight}
              width={barWidth * 0.6}
              height={barHeight}
              fill="var(--role-result)"
              fillOpacity={0.75}
            >
              <title>
                {`${formatNumber(peak.mass, 3)} Da · ${formatNumber(
                  peak.intensity_rel * 100,
                  1,
                )} %`}
              </title>
            </rect>
            <text
              x={x + barWidth * 0.3}
              y={height - padding.bottom + 12}
              textAnchor="middle"
              fontSize={9}
              fill="var(--text-faint)"
            >
              {formatNumber(peak.mass, 1)}
            </text>
          </g>
        );
      })}

      <text
        x={padding.left + plotWidth / 2}
        y={height - 4}
        textAnchor="middle"
        fontSize={9}
        fill="var(--text-muted)"
      >
        Masse (Da)
      </text>
    </svg>
  );
}

export function MsTab({
  sequence,
  exact,
  blocked = false,
}: {
  sequence: string;
  exact: ExactResult | null;
  /** Siehe SynthesisTab: bei fehlerhafter Sequenz gar nicht erst fragen. */
  blocked?: boolean;
}) {
  const [chargeMin, setChargeMin] = useState<number | "">(2);
  const [chargeMax, setChargeMax] = useState<number | "">(15);
  const [basis, setBasis] = useState<"average" | "monoisotopic">("average");
  const [ladder, setLadder] = useState<{ charge: number; mz: number }[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sequence.trim() || blocked || chargeMin === "" || chargeMax === "") {
      setLadder([]);
      setError(null);
      return;
    }
    let cancelled = false;
    api
      .msLadder({
        sequence,
        charge_min: chargeMin,
        charge_max: chargeMax,
        basis,
      })
      .then((result) => {
        if (!cancelled) {
          setLadder(result.ladder);
          setNote(result.note);
          setError(null);
        }
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setLadder([]);
        setError(
          cause instanceof ApiError
            ? cause.message
            : "Die Ladungsleiter konnte nicht berechnet werden.",
        );
      });
    return () => {
      cancelled = true;
    };
  }, [sequence, chargeMin, chargeMax, basis, blocked]);

  if (!exact) {
    return (
      <Card title="Massenspektrometrie">
        <Empty>
          {blocked
            ? "Die Sequenz hat Fehler — es wird nicht gerechnet. Die Stellen stehen oben beim Sequenzfeld."
            : "Erst eine gültige Sequenz eingeben."}
        </Empty>
      </Card>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card
        title="ESI-Ladungsleiter, negativ"
        subtitle="(M − n · 1,00794) / n"
        helpId="result.charge_ladder"
      >
        <div className="mb-3 grid grid-cols-3 gap-3">
          <Field label="von" helpId="field.charge_range" role="settings">
            <NumberInput value={chargeMin} onChange={setChargeMin} step={1} min={1} />
          </Field>
          <Field label="bis" helpId="field.charge_range" role="settings">
            <NumberInput value={chargeMax} onChange={setChargeMax} step={1} min={1} />
          </Field>
          <Field label="Grundlage" role="settings">
            <select
              className="ol-select"
              value={basis}
              onChange={(event) =>
                setBasis(event.target.value as "average" | "monoisotopic")
              }
            >
              <option value="average">mittlere Masse</option>
              <option value="monoisotopic">monoisotopisch</option>
            </select>
          </Field>
        </div>

        {error && <Notice level="bad">{error}</Notice>}

        {note && (
          <div className="mb-3">
            <Notice level="warn">{note}</Notice>
          </div>
        )}

        {ladder.length > 0 && (
          <table className="ol-table">
            <thead>
              <tr>
                <th scope="col">Ladung</th>
                <th scope="col">m/z</th>
              </tr>
            </thead>
            <tbody>
              {ladder.map((entry) => (
                <tr key={entry.charge}>
                  <td className="ol-mono">{entry.charge}−</td>
                  <td className="ol-mono tabular-nums">
                    {formatNumber(entry.mz, 2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card
        title="Isotopenmuster"
        subtitle={`Die fünf häufigsten Peaks · ${exact.formula ?? "Formel unvollständig"}`}
        helpId="result.isotope_pattern"
      >
        {exact.isotopes.length === 0 ? (
          <Empty>
            Ohne vollständige Summenformel lässt sich kein Muster berechnen.
          </Empty>
        ) : (
          <>
            <IsotopeChart peaks={exact.isotopes} />
            <table className="ol-table mt-3">
              <thead>
                <tr>
                  <th scope="col">Masse (Da)</th>
                  <th scope="col">relative Intensität</th>
                </tr>
              </thead>
              <tbody>
                {exact.isotopes.map((peak) => (
                  <tr key={peak.mass}>
                    <td className="ol-mono tabular-nums">
                      {formatNumber(peak.mass, 3)}
                    </td>
                    <td className="ol-mono tabular-nums">
                      {formatNumber(peak.intensity_rel * 100, 1)} %
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-xs" style={{ color: "var(--text-faint)" }}>
              Bei einem Oligo dieser Größe ist der höchste Peak nicht der
              monoisotopische.
            </p>
          </>
        )}
      </Card>
    </div>
  );
}
