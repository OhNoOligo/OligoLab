/* Reiter "Synthese" — Verbrauchstabelle (PHASEN.md 1.5). */

import { useEffect, useState } from "react";
import { api, ApiError } from "../../api";
import type { ConsumptionTable } from "../../types";
import { HelpTip } from "../HelpTip";
import { Card, Empty, Field, Notice, NumberInput, formatNumber } from "../ui";

export function SynthesisTab({
  sequence,
  initial,
  blocked = false,
}: {
  sequence: string;
  initial: ConsumptionTable | null;
  /** Die Sequenz hat Fehler. Dann wird gar nicht erst gefragt — eine rohe
   *  422-Meldung waere nur Laerm neben der Befundliste oben. */
  blocked?: boolean;
}) {
  const [couplingVolume, setCouplingVolume] = useState<number | "">(0.12);
  const [reserve, setReserve] = useState<number | "">(10);
  const [syntheses, setSyntheses] = useState<number | "">(1);
  const [table, setTable] = useState<ConsumptionTable | null>(initial);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sequence.trim() || blocked) {
      setTable(null);
      setError(null);
      return;
    }
    if (couplingVolume === "" || reserve === "" || syntheses === "") return;

    let cancelled = false;
    api
      .synthesis({
        sequence,
        coupling_volume_ml: couplingVolume,
        reserve_fraction: reserve / 100,
        syntheses,
      })
      .then((result) => {
        if (!cancelled) {
          setTable(result);
          setError(null);
        }
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setTable(null);
        setError(
          cause instanceof ApiError
            ? cause.message
            : "Die Verbrauchstabelle konnte nicht berechnet werden.",
        );
      });
    return () => {
      cancelled = true;
    };
  }, [sequence, couplingVolume, reserve, syntheses, blocked]);

  return (
    <Card
      title="Verbrauch am Synthesizer"
      subtitle={table?.hint}
      actions={
        <span className="ol-chip ol-role-settings">
          {formatNumber(table?.settings.coupling_volume_ml ?? 0.12, 2)} mL je Kupplung
        </span>
      }
    >
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Field label="Volumen je Kupplung (mL)" helpId="field.coupling_volume" role="settings">
          <NumberInput
            value={couplingVolume}
            onChange={setCouplingVolume}
            step={0.01}
            min={0.01}
          />
        </Field>
        <Field label="Reserve (%)" helpId="field.reserve" role="settings">
          <NumberInput value={reserve} onChange={setReserve} step={1} min={0} />
        </Field>
        <Field label="Zahl der Synthesen" helpId="field.syntheses" role="settings">
          <NumberInput value={syntheses} onChange={setSyntheses} step={1} min={1} />
        </Field>
      </div>

      {error && <Notice level="bad">{error}</Notice>}

      {blocked && (
        <Empty>
          Die Sequenz hat Fehler — es wird nicht gerechnet. Die Stellen stehen
          oben beim Sequenzfeld.
        </Empty>
      )}

      {!table && !error && !blocked && (
        <Empty>Erst eine gültige Sequenz eingeben.</Empty>
      )}

      {table && (
        <>
          <table className="ol-table">
            <thead>
              <tr>
                <th scope="col">Baustein</th>
                <th scope="col">Kupplungen</th>
                <th scope="col">Volumen (mL)</th>
                <th scope="col">c (mol/L)</th>
                <th scope="col" data-help="result.consumption_mass">
                  <span className="inline-flex items-center gap-1.5">
                    Masse (mg)
                    <HelpTip id="result.consumption_mass" />
                  </span>
                </th>
                <th scope="col">
                  + {formatNumber(table.settings.reserve_fraction * 100, 0)} %
                </th>
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row) => (
                <tr key={row.code} title={row.note ?? undefined}>
                  <td>
                    <span className="ol-mono font-semibold">{row.code}</span>
                    <span
                      className="ml-2 text-xs"
                      style={{ color: "var(--text-faint)" }}
                    >
                      {row.name}
                    </span>
                  </td>
                  <td className="ol-mono tabular-nums">{row.couplings}</td>
                  <td className="ol-mono tabular-nums">
                    {formatNumber(row.volume_ml, 2)}
                  </td>
                  <td className="ol-mono tabular-nums">
                    {row.conc_molar === null ? "—" : formatNumber(row.conc_molar, 2)}
                  </td>
                  <td className="ol-mono tabular-nums">
                    {formatNumber(row.mass_mg, 1)}
                  </td>
                  <td className="ol-mono tabular-nums">
                    {formatNumber(row.mass_with_reserve_mg, 1)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr data-help="result.consumption_total">
                <td>
                  <span className="inline-flex items-center gap-1.5">
                    Summe
                    <HelpTip id="result.consumption_total" />
                  </span>
                </td>
                <td className="ol-mono tabular-nums">
                  {table.rows.reduce((sum, row) => sum + row.couplings, 0)}
                </td>
                <td className="ol-mono tabular-nums">
                  {formatNumber(table.total.volume_ml, 2)}
                </td>
                <td />
                <td className="ol-mono tabular-nums">
                  {formatNumber(table.total.mass_mg, 1)}
                </td>
                <td className="ol-mono tabular-nums">
                  {formatNumber(table.total.mass_with_reserve_mg, 1)}
                </td>
              </tr>
            </tfoot>
          </table>

          <p className="mt-3 text-xs" style={{ color: "var(--text-muted)" }}>
            {table.hint} Masse = Volumen · Konzentration · Amiditmasse; in diesen
            Einheiten kommt das direkt in mg heraus.
          </p>

          {table.rows.some((row) => row.note) && (
            <div className="mt-3">
              <Notice level="warn" title="Unvollständig">
                <ul className="list-inside list-disc">
                  {table.rows
                    .filter((row) => row.note)
                    .map((row) => (
                      <li key={row.code}>
                        {row.code}: {row.note}
                      </li>
                    ))}
                </ul>
              </Notice>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
