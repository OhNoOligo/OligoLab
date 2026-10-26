/* Seite "Bausteine" (PHASEN.md 1.8).
 *
 * Alle Werte ansehen und bearbeiten, eigene Bausteine ueber ein Formular
 * anlegen. Abweichungen von den Excel-Konstanten werden farblich hervorgehoben
 * (CLAUDE.md, Regel 2) — und zwar nicht mit der Ampel, denn die ist allein
 * fuer Bewertungen da. Eine Abweichung ist keine Bewertung, sondern eine
 * Tatsache, darum die Rollenfarbe.
 *
 * Geschrieben wird nach `data/monomers_custom.yaml`. `monomers.yaml` bleibt
 * die unangetastete, kommentierte Abschrift des Excel. Darum laesst sich jede
 * Aenderung mit einem Knopf zuruecknehmen.
 */

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { ModificationSpecView, MonomerCatalog, MonomerSpecView } from "../types";
import { Card, Chip, Empty, Field, Notice, formatNumber } from "../components/ui";

type Draft = {
  code: string;
  name: string;
  mass_residue: string;
  mass_amidite: string;
  conc_molar: string;
  eps260: string;
  base_parent: string;
  smiles: string;
  formula_residue: string;
  core_tested: "ja" | "nein" | "unbekannt";
};

const EMPTY_DRAFT: Draft = {
  code: "",
  name: "",
  mass_residue: "",
  mass_amidite: "",
  conc_molar: "",
  eps260: "",
  base_parent: "",
  smiles: "",
  formula_residue: "",
  core_tested: "unbekannt",
};

function toPayload(draft: Draft): Record<string, unknown> {
  const numeric = (raw: string) => (raw.trim() === "" ? null : Number(raw));
  const text = (raw: string) => (raw.trim() === "" ? null : raw.trim());
  return {
    code: draft.code.trim(),
    name: text(draft.name),
    typ: "custom",
    mass_residue: numeric(draft.mass_residue),
    mass_amidite: numeric(draft.mass_amidite),
    conc_molar: numeric(draft.conc_molar),
    eps260: numeric(draft.eps260),
    base_parent: text(draft.base_parent)?.toUpperCase() ?? null,
    smiles: text(draft.smiles),
    formula_residue: text(draft.formula_residue),
    core_tested: draft.core_tested,
    quelle: "in OligoLab angelegt",
  };
}

export function Bausteine() {
  const [catalog, setCatalog] = useState<MonomerCatalog | null>(null);
  const [modifications, setModifications] = useState<ModificationSpecView[]>([]);
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [editing, setEditing] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api
      .monomers()
      .then(setCatalog)
      .catch((cause: unknown) =>
        setError(
          cause instanceof ApiError
            ? cause.message
            : "Die Bausteine konnten nicht geladen werden.",
        ),
      );
    api
      .modifications()
      .then((result) => setModifications(result.modifications))
      .catch(() => setModifications([]));
  }, []);

  useEffect(refresh, [refresh]);

  async function save() {
    setError(null);
    setMessage(null);
    if (!draft.code.trim()) {
      setError("Der Code darf nicht leer sein.");
      return;
    }
    try {
      const result = await api.saveMonomer(toPayload(draft));
      setMessage(`${result.saved} gespeichert in ${result.file}.`);
      setDraft(EMPTY_DRAFT);
      setEditing(null);
      refresh();
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? typeof cause.detail === "string"
            ? cause.detail
            : cause.message
          : "Nicht gespeichert.",
      );
    }
  }

  async function revert(code: string) {
    setError(null);
    setMessage(null);
    try {
      await api.dropMonomerOverride(code);
      setMessage(`Eigene Änderung an ${code} zurückgenommen — der Excel-Wert gilt wieder.`);
      refresh();
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? typeof cause.detail === "string"
            ? cause.detail
            : cause.message
          : "Nicht zurückgenommen.",
      );
    }
  }

  function startEdit(spec: MonomerSpecView) {
    setEditing(spec.code);
    setDraft({
      code: spec.code,
      name: spec.name,
      mass_residue: spec.mass_residue?.toString() ?? "",
      mass_amidite: spec.mass_amidite?.toString() ?? "",
      conc_molar: spec.conc_molar?.toString() ?? "",
      eps260: spec.eps260?.toString() ?? "",
      base_parent: spec.base_parent ?? "",
      smiles: spec.smiles ?? "",
      formula_residue: spec.formula_residue ?? "",
      core_tested: spec.core_tested,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const deviating = catalog?.monomers.filter((m) => m.deviates_from_excel) ?? [];

  return (
    <div className="flex flex-col gap-4">
      {error && <Notice level="bad">{error}</Notice>}
      {message && <Notice level="info">{message}</Notice>}

      {deviating.length > 0 && (
        <Notice
          level="warn"
          title={`${deviating.length} ${
            deviating.length === 1 ? "Baustein weicht" : "Bausteine weichen"
          } von den Excel-Konstanten ab`}
        >
          {deviating.map((m) => m.code).join(", ")} — die Excel-Werte gelten als
          verbindlich. Eine Änderung ist kein Fehler, sie wird nur nie
          stillschweigend übernommen.
        </Notice>
      )}

      <Card
        title={editing ? `Baustein ${editing} ändern` : "Eigenen Baustein anlegen"}
        subtitle="Gespeichert wird in data/monomers_custom.yaml; monomers.yaml bleibt unberührt"
        actions={
          <>
            {editing && (
              <button
                type="button"
                className="ol-button"
                onClick={() => {
                  setEditing(null);
                  setDraft(EMPTY_DRAFT);
                }}
              >
                abbrechen
              </button>
            )}
            <button
              type="button"
              className="ol-button"
              data-variant="primary"
              onClick={save}
              disabled={!draft.code.trim()}
            >
              speichern
            </button>
          </>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Code" helpId="field.monomer_code" hint="Ein Zeichen, oder länger für [Klammern]">
            <input
              className="ol-input ol-mono"
              data-role="input"
              value={draft.code}
              readOnly={editing !== null}
              onChange={(event) => setDraft({ ...draft, code: event.target.value })}
            />
          </Field>
          <Field label="Name">
            <input
              className="ol-input"
              data-role="input"
              value={draft.name}
              onChange={(event) => setDraft({ ...draft, name: event.target.value })}
            />
          </Field>
          <Field
            label="Restmasse (Da)"
            helpId="field.mass_residue"
            hint="Oder ein SMILES, daraus wird sie abgeleitet"
          >
            <input
              className="ol-input ol-mono"
              data-role="input"
              inputMode="decimal"
              value={draft.mass_residue}
              onChange={(event) =>
                setDraft({ ...draft, mass_residue: event.target.value })
              }
            />
          </Field>
          <Field label="Amiditmasse (g/mol)" helpId="field.mass_amidite">
            <input
              className="ol-input ol-mono"
              data-role="input"
              inputMode="decimal"
              value={draft.mass_amidite}
              onChange={(event) =>
                setDraft({ ...draft, mass_amidite: event.target.value })
              }
            />
          </Field>
          <Field label="Kupplungskonzentration (mol/L)" helpId="field.conc_molar">
            <input
              className="ol-input ol-mono"
              data-role="input"
              inputMode="decimal"
              value={draft.conc_molar}
              onChange={(event) =>
                setDraft({ ...draft, conc_molar: event.target.value })
              }
            />
          </Field>
          <Field
            label="ε₂₆₀ (L·mol⁻¹·cm⁻¹)"
            helpId="field.eps260"
            hint="Leer lassen: dann über das natürliche Analogon, gekennzeichnet als genähert"
          >
            <input
              className="ol-input ol-mono"
              data-role="input"
              inputMode="decimal"
              value={draft.eps260}
              onChange={(event) => setDraft({ ...draft, eps260: event.target.value })}
            />
          </Field>
          <Field
            label="Natürliches Analogon"
            helpId="method.base_parent"
            hint="A, C, G, T oder U — Grundlage aller Näherungen"
          >
            <select
              className="ol-select"
              value={draft.base_parent}
              onChange={(event) =>
                setDraft({ ...draft, base_parent: event.target.value })
              }
            >
              <option value="">keines</option>
              {["A", "C", "G", "T", "U"].map((base) => (
                <option key={base} value={base}>
                  {base}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Summenformel der Restmasse">
            <input
              className="ol-input ol-mono"
              data-role="input"
              placeholder="z. B. C10H12N5O5P"
              value={draft.formula_residue}
              onChange={(event) =>
                setDraft({ ...draft, formula_residue: event.target.value })
              }
            />
          </Field>
          <Field label="Im katalytischen Kern erprobt?" role="settings">
            <select
              className="ol-select"
              value={draft.core_tested}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  core_tested: event.target.value as Draft["core_tested"],
                })
              }
            >
              <option value="unbekannt">unbekannt</option>
              <option value="ja">ja</option>
              <option value="nein">nein</option>
            </select>
          </Field>
          <div className="sm:col-span-2 lg:col-span-3">
            <Field label="SMILES des freien Nukleosids">
              <input
                className="ol-input ol-mono"
                data-role="input"
                value={draft.smiles}
                onChange={(event) => setDraft({ ...draft, smiles: event.target.value })}
              />
            </Field>
          </div>
        </div>
      </Card>

      <Card
        title="Bausteine"
        subtitle={`${catalog?.monomers.length ?? 0} Einträge`}
        helpId="method.excel_constants"
      >
        {!catalog ? (
          <Empty>Lädt …</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="ol-table">
              <thead>
                <tr>
                  <th scope="col">Code</th>
                  <th scope="col">Name</th>
                  <th scope="col">Typ</th>
                  <th scope="col">Restmasse</th>
                  <th scope="col">Amidit</th>
                  <th scope="col">c (mol/L)</th>
                  <th scope="col">ε₂₆₀</th>
                  <th scope="col">Analogon</th>
                  <th scope="col">Kern</th>
                  <th scope="col">Formel</th>
                  <th scope="col" />
                </tr>
              </thead>
              <tbody>
                {catalog.monomers.map((spec) => (
                  <tr
                    key={spec.code}
                    style={
                      spec.deviates_from_excel
                        ? {
                            background:
                              "color-mix(in srgb, var(--rating-warn) 10%, transparent)",
                          }
                        : undefined
                    }
                  >
                    <td>
                      <span className="ol-mono font-semibold">{spec.code}</span>
                      {spec.deviates_from_excel && (
                        <span
                          className="ml-2"
                          title={
                            spec.is_override
                              ? "Eigene Änderung — weicht von den Excel-Konstanten ab"
                              : "Im Excel nicht enthalten"
                          }
                          style={{ color: "var(--rating-warn)" }}
                        >
                          ▲
                        </span>
                      )}
                    </td>
                    <td style={{ textAlign: "left" }}>{spec.name}</td>
                    <td style={{ textAlign: "left" }}>{spec.typ}</td>
                    <td className="ol-mono tabular-nums">
                      {formatNumber(spec.mass_residue)}
                    </td>
                    <td className="ol-mono tabular-nums">
                      {formatNumber(spec.mass_amidite)}
                    </td>
                    <td className="ol-mono tabular-nums">
                      {formatNumber(spec.conc_molar)}
                    </td>
                    <td className="ol-mono tabular-nums">
                      {spec.eps260 === null ? "—" : formatNumber(spec.eps260, 0)}
                    </td>
                    <td className="ol-mono">{spec.base_parent ?? "—"}</td>
                    <td>{spec.core_tested}</td>
                    <td className="ol-mono" style={{ textAlign: "left" }}>
                      {spec.formula_residue ?? "—"}
                    </td>
                    <td>
                      <div className="flex justify-end gap-1">
                        <button
                          type="button"
                          className="ol-button"
                          style={{ padding: "1px 6px", fontSize: 11 }}
                          onClick={() => startEdit(spec)}
                        >
                          ändern
                        </button>
                        {spec.is_override && (
                          <button
                            type="button"
                            className="ol-button"
                            style={{ padding: "1px 6px", fontSize: 11 }}
                            onClick={() => revert(spec.code)}
                            title="Eigene Änderung verwerfen"
                          >
                            zurück
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="mt-3 text-xs" style={{ color: "var(--text-faint)" }}>
          ▲ markiert eine Abweichung von den Excel-Konstanten. Fehlt eine
          Summenformel, gilt die Restmasse trotzdem — die Gegenrechnung meldet
          den Baustein dann als unvollständig.
        </p>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Schutzgruppen" subtitle="Massen unverändert aus dem Excel">
          {!catalog ? (
            <Empty>Lädt …</Empty>
          ) : (
            <table className="ol-table">
              <thead>
                <tr>
                  <th scope="col">Code</th>
                  <th scope="col">Name</th>
                  <th scope="col">Masse (Da)</th>
                  <th scope="col">wirkt an</th>
                </tr>
              </thead>
              <tbody>
                {Object.values(catalog.protecting_groups).map((group) => (
                  <tr key={group.code} title={group.note}>
                    <td className="ol-mono font-semibold">{group.code}</td>
                    <td style={{ textAlign: "left" }}>{group.name}</td>
                    <td className="ol-mono tabular-nums">
                      {formatNumber(group.mass)}
                    </td>
                    <td>{group.typ ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {catalog && (
            <dl
              className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 pt-3 text-xs"
              style={{
                borderTop: "1px solid var(--border)",
                color: "var(--text-muted)",
              }}
            >
              {Object.entries(catalog.termini).map(([key, value]) => (
                <div key={key} className="contents">
                  <dt>{value.name ?? key}</dt>
                  <dd className="ol-mono text-right tabular-nums">
                    {formatNumber(value.mass)} Da
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </Card>

        <Card title="Modifikationen" subtitle="Massendifferenzen">
          <table className="ol-table">
            <thead>
              <tr>
                <th scope="col">Code</th>
                <th scope="col">Name</th>
                <th scope="col">Δ Masse (Da)</th>
                <th scope="col">wirkt an</th>
              </tr>
            </thead>
            <tbody>
              {modifications.map((mod) => (
                <tr key={mod.code} title={mod.note ?? undefined}>
                  <td className="ol-mono font-semibold">{mod.code}</td>
                  <td style={{ textAlign: "left" }}>
                    {mod.name}
                    {mod.needs_review && (
                      <span className="ml-2">
                        <Chip
                          role="settings"
                          title={mod.quelle ?? "Masse nicht hinterlegt"}
                        >
                          zu ergänzen
                        </Chip>
                      </span>
                    )}
                  </td>
                  <td className="ol-mono tabular-nums">
                    {mod.mass_diff === null ? "—" : formatNumber(mod.mass_diff)}
                  </td>
                  <td>{mod.scope}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-xs" style={{ color: "var(--text-faint)" }}>
            „zu ergänzen" heißt: im Excel stand keine Masse und OligoLab erfindet
            keine. Bis ein Wert eingetragen ist, meldet die Rechnung den Eintrag
            als unvollständig — statt mit einer Null weiterzurechnen.
          </p>
        </Card>
      </div>
    </div>
  );
}
