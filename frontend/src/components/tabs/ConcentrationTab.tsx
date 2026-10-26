/* Reiter "Konzentration" — OD-Rechner (PHASEN.md 1.7). */

import { useEffect, useState } from "react";
import { api, ApiError } from "../../api";
import type { ExtinctionResult, MassResult, OdConversion } from "../../types";
import {
  Card,
  Empty,
  Field,
  Notice,
  NumberInput,
  ResultNumber,
  formatNumber,
} from "../ui";

type Entry = "od" | "nmol" | "microgram";

export function ConcentrationTab({
  extinction,
  mass,
}: {
  extinction: ExtinctionResult | null;
  mass: MassResult | null;
}) {
  const molarMass =
    mass?.masses.find((entry) => entry.key === "fully_deprotected")?.value ?? null;
  const eps260 = extinction?.eps260.value ?? null;

  const [entry, setEntry] = useState<Entry>("od");
  const [amount, setAmount] = useState<number | "">(1);
  const [conversion, setConversion] = useState<OdConversion | null>(null);

  const [a260, setA260] = useState<number | "">(0.5);
  const [pathCm, setPathCm] = useState<number | "">(1);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (eps260 === null || molarMass === null || amount === "") {
      setConversion(null);
      return;
    }
    let cancelled = false;
    api
      .convertOd({
        eps260,
        molar_mass: molarMass,
        od: entry === "od" ? amount : null,
        nmol: entry === "nmol" ? amount : null,
        microgram: entry === "microgram" ? amount : null,
      })
      .then((result) => {
        if (!cancelled) {
          setConversion(result);
          setError(null);
        }
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setConversion(null);
        setError(cause instanceof ApiError ? cause.message : "Rechnung fehlgeschlagen.");
      });
    return () => {
      cancelled = true;
    };
  }, [eps260, molarMass, entry, amount]);

  // Auch `extinction` pruefen, damit TypeScript den Zugriff unten kennt.
  if (!extinction || eps260 === null || molarMass === null) {
    return (
      <Card title="Konzentration">
        <Empty>
          {extinction?.eps260.note ??
            "Erst eine gültige Sequenz eingeben, für die ε₂₆₀ und Masse berechenbar sind."}
        </Empty>
      </Card>
    );
  }

  const concentration = a260 === "" || pathCm === "" ? null : a260 / (eps260 * pathCm);

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card
        title="ε₂₆₀ und A₂₆₀"
        subtitle={`Nearest-Neighbor, Tabelle ${extinction.table.toUpperCase()}`}
      >
        <ResultNumber
          label="ε₂₆₀ des Oligos"
          quantity={extinction.eps260}
          digits={0}
          helpId="result.eps260"
          size="large"
          copy
        />

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <Field label="A₂₆₀ (gemessen)">
            <NumberInput value={a260} onChange={setA260} step={0.01} min={0} role="input" />
          </Field>
          <Field label="Schichtdicke (cm)" helpId="field.path_length" role="settings">
            <NumberInput value={pathCm} onChange={setPathCm} step={0.1} min={0.01} />
          </Field>
        </div>

        <dl
          className="mt-4 grid grid-cols-2 gap-x-4 gap-y-1 pt-3 text-xs"
          style={{ borderTop: "1px solid var(--border)", color: "var(--text-muted)" }}
        >
          <dt>Konzentration</dt>
          <dd className="ol-mono text-right tabular-nums">
            {concentration === null
              ? "—"
              : `${formatNumber(concentration * 1e6, 3)} µM`}
          </dd>
          <dt>Lambert-Beer</dt>
          <dd className="text-right">c = A₂₆₀ / (ε₂₆₀ · l)</dd>
        </dl>

        {extinction.approximated.length > 0 && (
          <div className="mt-3">
            <Notice level="info" title="Genähert">
              <ul className="list-inside list-disc">
                {extinction.approximated.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </Notice>
          </div>
        )}
      </Card>

      <Card
        title="OD, nmol und µg"
        subtitle="Ein Feld wählen, Wert eintragen — die beiden anderen folgen"
        helpId="result.od_nmol_ug"
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Eingabefeld" role="settings">
            <select
              className="ol-select"
              value={entry}
              onChange={(event) => setEntry(event.target.value as Entry)}
            >
              <option value="od">OD₂₆₀</option>
              <option value="nmol">nmol</option>
              <option value="microgram">µg</option>
            </select>
          </Field>
          <Field label="Wert">
            <NumberInput value={amount} onChange={setAmount} step={0.1} min={0} role="input" />
          </Field>
        </div>

        {error && (
          <div className="mt-3">
            <Notice level="bad">{error}</Notice>
          </div>
        )}

        {conversion && (
          <>
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              <ResultNumber label="OD₂₆₀" quantity={conversion.od} digits={3} />
              <ResultNumber label="Stoffmenge" quantity={conversion.nmol} digits={2} />
              <ResultNumber label="Masse" quantity={conversion.microgram} digits={2} />
            </div>

            {conversion.warning && (
              <div className="mt-3">
                <Notice level="warn">{conversion.warning}</Notice>
              </div>
            )}

            <dl
              className="mt-4 grid grid-cols-2 gap-x-4 gap-y-1 pt-3 text-xs"
              style={{
                borderTop: "1px solid var(--border)",
                color: "var(--text-muted)",
              }}
            >
              <dt>je OD₂₆₀</dt>
              <dd className="ol-mono text-right tabular-nums">
                {formatNumber(1e6 / eps260, 2)} nmol
              </dd>
              <dt>molare Masse (vollständig entschützt)</dt>
              <dd className="ol-mono text-right tabular-nums">
                {formatNumber(molarMass)} Da
              </dd>
            </dl>
          </>
        )}
      </Card>
    </div>
  );
}
