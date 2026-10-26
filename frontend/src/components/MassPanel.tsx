/* Die Massenkarte und die Gegenrechnung (PHASEN.md 1.3, 1.4, 1.8).
 *
 * Die fuenf Massen stehen untereinander, klar beschriftet, jede mit
 * Kopierknopf. Darunter die unabhaengige Rechnung aus der Summenformel mit
 * der Differenz: unter 0,5 Da gruen, darueber eine Warnung mit dem Hinweis,
 * woran es liegt.
 */

import { useState } from "react";
import { HelpTip } from "./HelpTip";
import type { Comparison, ExactResult, MassResult } from "../types";
import {
  Card,
  CopyButton,
  Empty,
  Notice,
  Rating,
  ReliabilityMark,
  ResultNumber,
  formatNumber,
} from "./ui";

const HELP_BY_KEY: Record<string, string> = {
  fully_deprotected: "result.fully_deprotected",
  plus_dmt: "result.plus_dmt",
  plus_3_phosphate: "result.plus_3_phosphate",
  protected_dmt_off: "result.protected_dmt_off",
  protected_ce: "result.protected_ce",
};

export function MassCard({ mass }: { mass: MassResult | null }) {
  if (!mass) {
    return (
      <Card title="Massen">
        <Empty>Erst eine gültige Sequenz eingeben.</Empty>
      </Card>
    );
  }

  const breakdown = mass.breakdown;

  return (
    <Card
      title="Massen"
      subtitle="Excel-Rechnung, unverändert übernommen"
      helpId="method.excel_constants"
    >
      <ul className="flex flex-col gap-3">
        {mass.masses.map((entry) => (
          <li
            key={entry.key}
            className="flex items-baseline justify-between gap-3"
            data-help={HELP_BY_KEY[entry.key]}
          >
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                  {entry.label}
                </span>
                {HELP_BY_KEY[entry.key] && (
                  <HelpTip id={HELP_BY_KEY[entry.key]!} />
                )}
                <ReliabilityMark
                  reliability={entry.reliability}
                  note={entry.note}
                />
              </div>
              <p className="text-xs" style={{ color: "var(--text-faint)" }}>
                {entry.value === null && entry.note ? entry.note : entry.method}
              </p>
            </div>
            <div className="flex shrink-0 items-baseline gap-2">
              <span
                className="ol-mono font-semibold tabular-nums"
                style={{
                  fontSize: 19,
                  color:
                    entry.value === null ? "var(--text-faint)" : "var(--text)",
                }}
              >
                {formatNumber(entry.value, 2)}
              </span>
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                Da
              </span>
              {entry.value !== null && (
                <CopyButton value={String(entry.value)} label={entry.label} />
              )}
            </div>
          </li>
        ))}
      </ul>

      <dl
        className="mt-4 grid grid-cols-2 gap-x-4 gap-y-1 pt-3 text-xs"
        style={{ borderTop: "1px solid var(--border)", color: "var(--text-muted)" }}
      >
        <dt>Bausteine L</dt>
        <dd className="ol-mono text-right tabular-nums">{breakdown.length}</dd>
        <dt>Basenzählung A / C / G</dt>
        <dd className="ol-mono text-right tabular-nums">
          {breakdown.n_A} / {breakdown.n_C} / {breakdown.n_G}
        </dd>
        <dt>Σ Restmassen</dt>
        <dd className="ol-mono text-right tabular-nums">
          {formatNumber(breakdown.residues)} Da
        </dd>
        {breakdown.monomer_modifications !== 0 && (
          <>
            <dt>Σ Modifikationen am Baustein</dt>
            <dd className="ol-mono text-right tabular-nums">
              {formatNumber(breakdown.monomer_modifications)} Da
            </dd>
          </>
        )}
        {breakdown.linkage_modifications !== 0 && (
          <>
            <dt>Σ Rückgratmodifikationen</dt>
            <dd className="ol-mono text-right tabular-nums">
              {formatNumber(breakdown.linkage_modifications)} Da
            </dd>
          </>
        )}
        {breakdown.conjugates !== 0 && (
          <>
            <dt>Σ Konjugate</dt>
            <dd className="ol-mono text-right tabular-nums">
              {formatNumber(breakdown.conjugates)} Da
            </dd>
          </>
        )}
      </dl>

      {breakdown.approximated.length > 0 && (
        <div className="mt-3">
          <Notice level="info" title="Genähert">
            <ul className="list-inside list-disc">
              {breakdown.approximated.map((entry) => (
                <li key={entry}>{entry}</li>
              ))}
            </ul>
          </Notice>
        </div>
      )}
    </Card>
  );
}

export function ExactCard({
  exact,
  comparison,
}: {
  exact: ExactResult | null;
  comparison: Comparison | null;
}) {
  const [showTable, setShowTable] = useState(false);

  if (!exact || !comparison) {
    return (
      <Card title="Gegenrechnung aus der Summenformel">
        <Empty>Erst eine gültige Sequenz eingeben.</Empty>
      </Card>
    );
  }

  return (
    <Card
      title="Gegenrechnung aus der Summenformel"
      subtitle={exact.formula ?? "Summenformel unvollständig"}
      actions={
        comparison.difference === null ? (
          <Rating level="bad" title={comparison.message}>
            nicht vergleichbar
          </Rating>
        ) : comparison.agrees ? (
          <Rating level="good" title={comparison.message}>
            {`Δ ${formatNumber(comparison.difference)} Da`}
          </Rating>
        ) : (
          <Rating level="warn" title={comparison.message}>
            {`Δ ${formatNumber(comparison.difference)} Da`}
          </Rating>
        )
      }
    >
      {/* Bewusst einspaltig: in der schmalen Seitenspalte wuerden die
          Beschriftungen sonst abbrechen. */}
      <div className="grid gap-4">
        <ResultNumber
          label="monoisotopisch, freie Säure"
          quantity={exact.monoisotopic}
          digits={2}
          helpId="result.exact_mono"
          copy
        />
        <ResultNumber
          label="mittlere Masse, freie Säure"
          quantity={exact.average}
          digits={2}
          helpId="result.exact_average"
          copy
        />
        <ResultNumber
          label={`monoisotopisch, Na-Salz (${exact.sodium_count} Na)`}
          quantity={exact.monoisotopic_na}
          digits={2}
          helpId="result.sodium_salt"
          copy
        />
        <ResultNumber
          label={`mittlere Masse, Na-Salz (${exact.sodium_count} Na)`}
          quantity={exact.average_na}
          digits={2}
          helpId="result.sodium_salt"
          copy
        />
      </div>

      <div className="mt-4" data-help="result.difference">
        <Notice level={comparison.agrees ? "info" : "warn"}>
          <span className="float-right ml-2">
            <HelpTip id="result.difference" />
          </span>
          {comparison.message}
        </Notice>
      </div>

      {exact.missing_formula.length > 0 && (
        <div className="mt-3">
          <Notice level="warn" title="Ohne Summenformel">
            <ul className="list-inside list-disc">
              {exact.missing_formula.map((entry) => (
                <li key={entry}>{entry}</li>
              ))}
            </ul>
          </Notice>
        </div>
      )}

      {comparison.per_code.length > 0 && (
        <div className="mt-3">
          <button
            type="button"
            className="ol-button"
            style={{ padding: "2px 8px", fontSize: 11 }}
            onClick={() => setShowTable((open) => !open)}
            aria-expanded={showTable}
          >
            {showTable ? "Aufschlüsselung ausblenden" : "Aufschlüsselung je Baustein"}
          </button>

          {showTable && (
            // Die Karte ist schmal. Darum nur die Spalten, die die Aussage
            // tragen: die Summenformel steht schon im Kartentitel, die
            // absolute monoisotopische Masse hilft hier nicht weiter.
            <div className="mt-2 overflow-x-auto">
              <p className="pb-2 text-xs" style={{ color: "var(--text-faint)" }}>
                Excel-Restmasse gegen die Masse aus der Summenformel. Die
                Excel-Werte bleiben verbindlich; diese Tabelle zeigt nur, wo
                sie herkommen.
              </p>
              <table
                className="ol-table"
                style={{ fontSize: 11, whiteSpace: "nowrap" }}
              >
                <thead>
                  <tr>
                    <th scope="col">Code</th>
                    <th scope="col">n</th>
                    <th scope="col">Excel</th>
                    <th scope="col" title="Masse aus der Summenformel, Isotopenmittel">
                      Mittel
                    </th>
                    <th scope="col" title="Excel minus Isotopenmittel">
                      Δ Mittel
                    </th>
                    <th scope="col" title="Excel minus monoisotopische Masse">
                      Δ mono
                    </th>
                    <th scope="col" title="Beitrag zur Gesamtdifferenz">
                      Δ · n
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.per_code.map((row) => (
                    <tr key={row.code} title={row.formula ?? undefined}>
                      <td className="ol-mono">{row.code}</td>
                      <td className="ol-mono tabular-nums">{row.count}</td>
                      <td className="ol-mono tabular-nums">
                        {formatNumber(row.excel)}
                      </td>
                      <td className="ol-mono tabular-nums">
                        {formatNumber(row.average, 3)}
                      </td>
                      <td className="ol-mono tabular-nums">
                        {formatNumber(row.delta, 3)}
                      </td>
                      <td className="ol-mono tabular-nums">
                        {formatNumber(row.delta_mono, 3)}
                      </td>
                      <td className="ol-mono tabular-nums">
                        {formatNumber(row.delta_total, 2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
