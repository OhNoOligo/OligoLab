/* Reiter "Beladung" — PAGE und LC-MS mit Probenliste (PHASEN.md 1.6). */

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../api";
import type { LibrarySample, LoadingRecipe } from "../../types";
import {
  Card,
  Empty,
  Field,
  Notice,
  NumberInput,
  ResultNumber,
  formatNumber,
} from "../ui";

function RecipeResult({ recipe }: { recipe: LoadingRecipe | null }) {
  if (!recipe) return null;
  return (
    <div className="mt-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <ResultNumber
          label="V(Oligo)"
          quantity={recipe.oligo_ul}
          helpId="result.loading_oligo"
          copy
        />
        <ResultNumber
          label="V(Wasser)"
          quantity={recipe.water_ul}
          helpId="result.loading_water"
        />
        {recipe.buffer_ul && (
          <ResultNumber label="V(2× DNA-Puffer)" quantity={recipe.buffer_ul} />
        )}
        <ResultNumber label="c(Stock)" quantity={recipe.stock_conc_um} />
      </div>

      <dl
        className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 pt-3 text-xs"
        style={{ borderTop: "1px solid var(--border)", color: "var(--text-muted)" }}
      >
        <dt>Gesamtvolumen</dt>
        <dd className="ol-mono text-right tabular-nums">
          {formatNumber(recipe.total_ul)} µL
        </dd>
        <dt>Rest im Vial</dt>
        <dd className="ol-mono text-right tabular-nums">
          {formatNumber(recipe.rest_in_vial_ul)} µL
        </dd>
      </dl>

      {recipe.warnings.length > 0 && (
        <div className="mt-3">
          <Notice level="warn" title="Aufgepasst">
            <ul className="list-inside list-disc">
              {recipe.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </Notice>
        </div>
      )}
    </div>
  );
}

export function LoadingTab() {
  const [nStock, setNStock] = useState<number | "">(50);
  const [vStock, setVStock] = useState<number | "">(100);

  const [nLoading, setNLoading] = useState<number | "">(500);
  const [page, setPage] = useState<LoadingRecipe | null>(null);

  const [nInjection, setNInjection] = useState<number | "">(100);
  const [vSample, setVSample] = useState<number | "">(50);
  const [vInjection, setVInjection] = useState<number | "">(5);
  const [lcms, setLcms] = useState<LoadingRecipe | null>(null);

  const [error, setError] = useState<string | null>(null);

  const [samples, setSamples] = useState<LibrarySample[]>([]);
  const [sampleName, setSampleName] = useState("");

  const refreshSamples = useCallback(() => {
    api
      .samples()
      .then((result) => setSamples(result.samples))
      .catch(() => setSamples([]));
  }, []);

  useEffect(refreshSamples, [refreshSamples]);

  useEffect(() => {
    if (nStock === "" || vStock === "" || nLoading === "") {
      setPage(null);
      return;
    }
    let cancelled = false;
    api
      .loadingPage({
        n_loading_pmol: nLoading,
        n_stock_nmol: nStock,
        v_stock_ul: vStock,
      })
      .then((result) => !cancelled && setPage(result))
      .catch((cause: unknown) => {
        if (cancelled) return;
        setPage(null);
        setError(cause instanceof ApiError ? cause.message : "Rechnung fehlgeschlagen.");
      });
    return () => {
      cancelled = true;
    };
  }, [nStock, vStock, nLoading]);

  useEffect(() => {
    if (
      nStock === "" ||
      vStock === "" ||
      nInjection === "" ||
      vSample === "" ||
      vInjection === ""
    ) {
      setLcms(null);
      return;
    }
    let cancelled = false;
    api
      .loadingLcms({
        n_injection_pmol: nInjection,
        n_stock_nmol: nStock,
        v_stock_ul: vStock,
        v_sample_ul: vSample,
        v_injection_ul: vInjection,
      })
      .then((result) => !cancelled && setLcms(result))
      .catch((cause: unknown) => {
        if (cancelled) return;
        setLcms(null);
        setError(cause instanceof ApiError ? cause.message : "Rechnung fehlgeschlagen.");
      });
    return () => {
      cancelled = true;
    };
  }, [nStock, vStock, nInjection, vSample, vInjection]);

  async function saveSample() {
    if (!sampleName.trim() || nStock === "" || vStock === "") return;
    try {
      await api.saveSample({
        name: sampleName.trim(),
        n_stock_nmol: nStock,
        v_stock_ul: vStock,
      });
      setSampleName("");
      refreshSamples();
    } catch (cause) {
      setError(
        cause instanceof ApiError ? cause.message : "Die Probe wurde nicht gespeichert.",
      );
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card
        title="Stammlösung"
        subtitle="Gilt für beide Rechnungen darunter"
        actions={
          <span className="ol-chip ol-role-result">
            {nStock !== "" && vStock !== "" && vStock > 0
              ? `${formatNumber((nStock * 1000) / vStock)} µM`
              : "—"}
          </span>
        }
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="n(Stock) (nmol)" helpId="field.n_stock">
            <NumberInput value={nStock} onChange={setNStock} step={0.1} min={0} role="input" />
          </Field>
          <Field label="V(Stock) (µL)" helpId="field.v_stock">
            <NumberInput value={vStock} onChange={setVStock} step={1} min={0.1} role="input" />
          </Field>
          <Field
            label="Als Probe merken"
            hint="Name vergeben und speichern"
            htmlFor="probenname"
          >
            <div className="flex gap-2">
              <input
                id="probenname"
                className="ol-input"
                data-role="input"
                value={sampleName}
                placeholder="Probenname"
                onChange={(event) => setSampleName(event.target.value)}
              />
              <button
                type="button"
                className="ol-button"
                onClick={saveSample}
                disabled={!sampleName.trim()}
              >
                merken
              </button>
            </div>
          </Field>
        </div>

        {samples.length > 0 && (
          <table className="ol-table mt-4">
            <caption
              className="pb-2 text-left text-xs"
              style={{ color: "var(--text-faint)", captionSide: "top" }}
            >
              Gespeicherte Proben — anklicken, um die Werte zu übernehmen
            </caption>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">n(Stock) (nmol)</th>
                <th scope="col">V(Stock) (µL)</th>
                <th scope="col">c (µM)</th>
                <th scope="col" />
              </tr>
            </thead>
            <tbody>
              {samples.map((sample) => (
                <tr key={sample.id}>
                  <td>
                    <button
                      type="button"
                      className="underline"
                      style={{ color: "var(--role-result)" }}
                      onClick={() => {
                        setNStock(sample.n_stock_nmol);
                        setVStock(sample.v_stock_ul);
                      }}
                    >
                      {sample.name}
                    </button>
                  </td>
                  <td className="ol-mono tabular-nums">
                    {formatNumber(sample.n_stock_nmol)}
                  </td>
                  <td className="ol-mono tabular-nums">
                    {formatNumber(sample.v_stock_ul)}
                  </td>
                  <td className="ol-mono tabular-nums">
                    {formatNumber((sample.n_stock_nmol * 1000) / sample.v_stock_ul)}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="ol-button"
                      style={{ padding: "1px 6px", fontSize: 11 }}
                      onClick={() =>
                        api.deleteSample(sample.id).then(refreshSamples).catch(() => {})
                      }
                      aria-label={`${sample.name} löschen`}
                    >
                      löschen
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {error && <Notice level="bad">{error}</Notice>}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="PAGE" subtitle="V(Oligo) = n(Beladung) / c · 2, dazu 10 µL 2× DNA-Puffer">
          <Field label="n(Beladung) (pmol)" helpId="field.n_loading">
            <NumberInput value={nLoading} onChange={setNLoading} step={10} min={0.1} role="input" />
          </Field>
          {page ? <RecipeResult recipe={page} /> : <Empty>Werte eingeben.</Empty>}
        </Card>

        <Card
          title="LC-MS"
          subtitle="V(Oligo) = n(Injektion) / c · (V(Probe) / V(Injektion))"
        >
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="n(Injektion) (pmol)" helpId="field.n_injection">
              <NumberInput value={nInjection} onChange={setNInjection} step={10} min={0.1} role="input" />
            </Field>
            <Field label="V(Probe) (µL)" helpId="field.v_sample" role="settings">
              <NumberInput value={vSample} onChange={setVSample} step={1} min={0.1} />
            </Field>
            <Field label="V(Injektion) (µL)" helpId="field.v_injection" role="settings">
              <NumberInput value={vInjection} onChange={setVInjection} step={0.5} min={0.1} />
            </Field>
          </div>
          {lcms ? <RecipeResult recipe={lcms} /> : <Empty>Werte eingeben.</Empty>}
        </Card>
      </div>
    </div>
  );
}
