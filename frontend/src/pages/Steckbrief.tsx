/* Seite "Steckbrief" (PHASEN.md 1.8).
 *
 * Links das grosse Sequenzfeld mit Syntaxhervorhebung, rechts die Karte mit
 * den fuenf Massen und der Gegenrechnung. Darunter die Reiter Synthese,
 * Beladung, MS und Konzentration, dann die Bibliothek.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api";
import {
  KLASSE_COLOR,
  KLASSE_LABEL,
  SequenceEditor,
  SequenceRuler,
  groupInThrees,
} from "../components/SequenceEditor";
import { ExactCard, MassCard } from "../components/MassPanel";
import { LibraryPanel } from "../components/LibraryPanel";
import { ConcentrationTab } from "../components/tabs/ConcentrationTab";
import { LoadingTab } from "../components/tabs/LoadingTab";
import { MsTab } from "../components/tabs/MsTab";
import { SynthesisTab } from "../components/tabs/SynthesisTab";
import { Card, Chip, Field, Notice } from "../components/ui";
import type { MonomerKlasse, Profile } from "../types";

/* Die Regressionssequenz aus CLAUDE.md — ein 10-23-DNAzym. */
const EXAMPLE = "TTG GGG TAA GGC TAG CTA CAA CGA GGT GCA TGT";

const TABS = [
  { id: "synthese", label: "Synthese" },
  { id: "beladung", label: "Beladung" },
  { id: "ms", label: "MS" },
  { id: "konzentration", label: "Konzentration" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function Steckbrief() {
  const [sequence, setSequence] = useState(EXAMPLE);
  const [name, setName] = useState("DZ 10-23 Referenz");
  const [notes, setNotes] = useState("");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<TabId>("synthese");
  const [translation, setTranslation] = useState<string | null>(null);

  /* Die Rechnung laeuft entkoppelt vom Tippen. 250 ms reichen, damit die
   * Oberflaeche nie einruckelt (CLAUDE.md, Regel 8). */
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setBusy(true);
      api
        .profile(sequence, name, notes)
        .then((result) => {
          setProfile(result);
          setError(null);
        })
        .catch((cause: unknown) =>
          setError(
            cause instanceof ApiError
              ? cause.message
              : "Die Rechnung ist fehlgeschlagen.",
          ),
        )
        .finally(() => setBusy(false));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [sequence, name, notes]);

  const oligo = profile?.oligo ?? null;
  const problems = profile?.problems ?? [];

  /* Welche Farbklassen kommen vor? Nur die werden erklaert — eine Legende mit
   * fuenf ungenutzten Zeilen hilft niemandem. */
  const usedKlassen = useMemo(() => {
    const seen = new Set<MonomerKlasse>();
    for (const monomer of oligo?.monomers ?? []) seen.add(monomer.klasse);
    return [...seen];
  }, [oligo]);

  const translate = useCallback(
    async (to: "rna" | "dna") => {
      try {
        const result = await api.translate(sequence, to);
        setTranslation(
          result.sequence ??
            "Übersetzung nicht möglich — die Sequenz hat Fehler.",
        );
      } catch {
        setTranslation("Übersetzung nicht möglich.");
      }
    },
    [sequence],
  );

  return (
    <div className="flex flex-col gap-4">
      {error && <Notice level="bad">{error}</Notice>}

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        {/* ------------------------------------------------ Sequenz ------- */}
        <Card
          title="Sequenz"
          subtitle="Synthi-Sprache, 5′ nach 3′"
          actions={
            <>
              <button
                type="button"
                className="ol-button"
                onClick={() => setSequence(groupInThrees(sequence))}
                title="In Dreiergruppen setzen, wie das Excel sie anzeigt"
              >
                Dreiergruppen
              </button>
              <button
                type="button"
                className="ol-button"
                onClick={() => translate("rna")}
                title="DNA in Synthi-RNA übersetzen: T→U, C→I, A→O, G→Z"
              >
                → RNA
              </button>
              <button
                type="button"
                className="ol-button"
                onClick={() => translate("dna")}
                title="Synthi-RNA in DNA übersetzen"
              >
                → DNA
              </button>
            </>
          }
        >
          <SequenceEditor
            value={sequence}
            onChange={setSequence}
            oligo={oligo}
            problems={problems}
          />

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Chip role="result" title="Zahl der Bausteine; Konjugate zählen nicht mit">
              L = {oligo?.length ?? 0}
            </Chip>
            {oligo && oligo.phosphorothioates > 0 && (
              <Chip role="result" title="Phosphorothioate im Rückgrat">
                {oligo.phosphorothioates} × PS
              </Chip>
            )}
            {/* Gleiche Konjugate zusammengefasst — fuenf gleiche Chips
                nebeneinander sagen nicht mehr als einer mit Anzahl. */}
            {Object.entries(
              (oligo?.conjugates ?? []).reduce<Record<string, number>>(
                (zaehler, conjugate) => ({
                  ...zaehler,
                  [conjugate.code]: (zaehler[conjugate.code] ?? 0) + 1,
                }),
                {},
              ),
            ).map(([code, anzahl]) => (
              <Chip
                key={code}
                role="result"
                title={`${
                  oligo?.conjugates.find((c) => c.code === code)?.name ?? code
                } — zählt nicht zur Basenzahl`}
              >
                {anzahl > 1 ? `${anzahl} × ${code}` : code}
              </Chip>
            ))}
            {busy && (
              <span className="text-xs" style={{ color: "var(--text-faint)" }}>
                rechnet …
              </span>
            )}
          </div>

          {problems.length > 0 && (
            <div className="mt-3">
              <Notice
                level="bad"
                title={`${problems.length} ${
                  problems.length === 1 ? "Stelle" : "Stellen"
                } unklar — es wird nicht gerechnet`}
              >
                <ul className="list-inside list-disc">
                  {problems.map((problem) => (
                    <li key={`${problem.position}-${problem.text}`}>
                      <strong className="ol-mono">
                        Position {problem.position}
                      </strong>{" "}
                      {problem.message} {problem.hint}
                    </li>
                  ))}
                </ul>
              </Notice>
            </div>
          )}

          {translation && (
            <div className="mt-3">
              <Notice level="info" title="Übersetzung">
                <code className="ol-mono">{translation}</code>
                <button
                  type="button"
                  className="ol-button ml-2"
                  style={{ padding: "1px 6px", fontSize: 11 }}
                  onClick={() => {
                    setSequence(translation);
                    setTranslation(null);
                  }}
                >
                  übernehmen
                </button>
              </Notice>
            </div>
          )}

          {usedKlassen.length > 0 && (
            <ul className="mt-3 flex flex-wrap gap-3 text-xs">
              {usedKlassen.map((klasse) => (
                <li key={klasse} className="flex items-center gap-1.5">
                  <span
                    aria-hidden="true"
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: 2,
                      display: "inline-block",
                      // Aus derselben Tabelle wie das Sequenzfeld. Die
                      // Token heissen `sugar` und `conjugate`, die Klassen
                      // `zucker` und `konjugat` — von Hand zusammengesetzt
                      // ergaebe das zwei Namen, die es nicht gibt.
                      background: KLASSE_COLOR[klasse],
                    }}
                  />
                  <span style={{ color: "var(--text-muted)" }}>
                    {KLASSE_LABEL[klasse]}
                  </span>
                </li>
              ))}
            </ul>
          )}

          {oligo && oligo.length >= 20 && problems.length === 0 && (
            <div className="mt-4 pt-3" style={{ borderTop: "1px solid var(--border)" }}>
              <SequenceRuler oligo={oligo} />
            </div>
          )}

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Field label="Name" helpId="field.name">
              <input
                className="ol-input"
                data-role="input"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </Field>
            <Field label="Notizen" helpId="field.notes">
              <input
                className="ol-input"
                data-role="input"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="Charge, Reinigung, Zweck"
              />
            </Field>
          </div>
        </Card>

        {/* ------------------------------------------------ Massen --------- */}
        <div className="flex flex-col gap-4">
          <MassCard mass={profile?.mass ?? null} />
          <ExactCard
            exact={profile?.exact ?? null}
            comparison={profile?.comparison ?? null}
          />
        </div>
      </div>

      {/* -------------------------------------------------- Reiter --------- */}
      <div>
        <div
          role="tablist"
          aria-label="Weitere Rechnungen"
          className="flex flex-wrap gap-1 pb-3"
        >
          {TABS.map((entry) => {
            const active = entry.id === tab;
            return (
              <button
                key={entry.id}
                type="button"
                role="tab"
                aria-selected={active}
                className="ol-button"
                data-variant={active ? "primary" : undefined}
                onClick={() => setTab(entry.id)}
              >
                {entry.label}
              </button>
            );
          })}
        </div>

        <div role="tabpanel">
          {tab === "synthese" && (
            <SynthesisTab
              sequence={sequence}
              initial={profile?.synthesis ?? null}
              blocked={problems.length > 0}
            />
          )}
          {tab === "beladung" && <LoadingTab />}
          {tab === "ms" && (
            <MsTab
              sequence={sequence}
              exact={profile?.exact ?? null}
              blocked={problems.length > 0}
            />
          )}
          {tab === "konzentration" && (
            <ConcentrationTab
              extinction={profile?.extinction ?? null}
              mass={profile?.mass ?? null}
            />
          )}
        </div>
      </div>

      <LibraryPanel
        sequence={sequence}
        name={name}
        notes={notes}
        onLoad={(entry) => {
          setSequence(entry.sequence);
          setName(entry.name);
          setNotes(entry.notes ?? "");
        }}
      />
    </div>
  );
}
