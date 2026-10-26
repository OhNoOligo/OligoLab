/* Die Bibliothek gespeicherter Oligos (PHASEN.md 1.8).
 *
 * Name, Sequenz, Masse, Datum; durchsuchbar; Export als CSV. Gespeichert wird
 * der Sequenztext — beim Laden rechnet OligoLab neu, damit eine geaenderte
 * Monomerdatei sich sofort auswirkt.
 */

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { LibraryOligo } from "../types";
import { Card, Empty, Notice, formatNumber } from "./ui";

export function LibraryPanel({
  sequence,
  name,
  notes,
  onLoad,
}: {
  sequence: string;
  name: string;
  notes: string;
  onLoad: (entry: LibraryOligo) => void;
}) {
  const [entries, setEntries] = useState<LibraryOligo[]>([]);
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback((search: string) => {
    api
      .libraryOligos(search || undefined)
      .then((result) => setEntries(result.oligos))
      .catch((cause: unknown) =>
        setError(
          cause instanceof ApiError
            ? cause.message
            : "Die Bibliothek konnte nicht geladen werden.",
        ),
      );
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => refresh(query), 200);
    return () => window.clearTimeout(timer);
  }, [query, refresh]);

  async function save() {
    setError(null);
    setMessage(null);
    if (!name.trim()) {
      setError("Für das Speichern braucht das Oligo einen Namen.");
      return;
    }
    try {
      await api.saveOligo({
        name: name.trim(),
        sequence,
        notes: notes.trim() || undefined,
      });
      setMessage(`„${name.trim()}" gespeichert.`);
      refresh(query);
    } catch (cause) {
      if (cause instanceof ApiError && cause.detail && typeof cause.detail === "object") {
        const detail = cause.detail as {
          message?: string;
          problems?: { position: number; text: string }[];
        };
        const stellen = (detail.problems ?? [])
          .map((p) => `Position ${p.position} (${p.text})`)
          .join(", ");
        setError(
          `${detail.message ?? "Nicht gespeichert."}${stellen ? ` ${stellen}.` : ""}`,
        );
      } else {
        setError(
          cause instanceof ApiError ? cause.message : "Nicht gespeichert.",
        );
      }
    }
  }

  return (
    <Card
      title="Bibliothek"
      subtitle={`${entries.length} ${entries.length === 1 ? "Eintrag" : "Einträge"}`}
      actions={
        <>
          <button
            type="button"
            className="ol-button"
            data-variant="primary"
            onClick={save}
            disabled={!sequence.trim()}
          >
            speichern
          </button>
          <a className="ol-button" href="/api/library/oligos.csv" download>
            CSV
          </a>
        </>
      }
    >
      <input
        className="ol-input"
        data-role="settings"
        type="search"
        placeholder="Suchen in Name, Sequenz und Notizen"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        aria-label="Bibliothek durchsuchen"
      />

      {message && (
        <div className="mt-3">
          <Notice level="info">{message}</Notice>
        </div>
      )}
      {error && (
        <div className="mt-3">
          <Notice level="bad">{error}</Notice>
        </div>
      )}

      {entries.length === 0 ? (
        <Empty>
          {query
            ? "Nichts gefunden."
            : "Noch nichts gespeichert. Oben einen Namen vergeben und speichern."}
        </Empty>
      ) : (
        <table className="ol-table mt-3">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Sequenz</th>
              <th scope="col">L</th>
              <th scope="col">Masse (Da)</th>
              <th scope="col">geändert</th>
              <th scope="col" />
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.id}>
                <td>
                  <button
                    type="button"
                    className="underline"
                    style={{ color: "var(--role-result)" }}
                    onClick={() => onLoad(entry)}
                    title="In den Steckbrief laden"
                  >
                    {entry.name}
                  </button>
                  {entry.notes && (
                    <p className="text-xs" style={{ color: "var(--text-faint)" }}>
                      {entry.notes}
                    </p>
                  )}
                </td>
                <td
                  className="ol-mono"
                  style={{
                    maxWidth: 220,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    textAlign: "left",
                  }}
                  title={entry.sequence}
                >
                  {entry.sequence}
                </td>
                <td className="ol-mono tabular-nums">{entry.length}</td>
                <td className="ol-mono tabular-nums">
                  {formatNumber(entry.mass_fully_deprotected)}
                </td>
                <td className="text-xs" style={{ color: "var(--text-faint)" }}>
                  {entry.updated_at.slice(0, 10)}
                </td>
                <td>
                  <button
                    type="button"
                    className="ol-button"
                    style={{ padding: "1px 6px", fontSize: 11 }}
                    onClick={() =>
                      api
                        .deleteOligo(entry.id)
                        .then(() => refresh(query))
                        .catch(() => setError("Nicht gelöscht."))
                    }
                    aria-label={`${entry.name} löschen`}
                  >
                    löschen
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="mt-3 text-xs" style={{ color: "var(--text-faint)" }}>
        Die mitgespeicherte Masse ist eine Momentaufnahme für Liste und Suche.
        Beim Laden wird neu gerechnet.
      </p>
    </Card>
  );
}
