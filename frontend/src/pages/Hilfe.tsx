/* Die Glossarseite /hilfe (PHASEN.md 2.6).
 *
 * Alle Einträge aus `help/help.yaml` mit Suchfeld, nach Namensraum gruppiert.
 * Dieselbe Quelle wie die Fragezeichen neben den Feldern — es gibt nur eine
 * Stelle, an der ein Text steht.
 */

import { useState } from "react";
import {
  NAMESPACE_LABEL,
  useHelpGroups,
} from "../components/HelpTip";
import { Card, Empty } from "../components/ui";

export function Hilfe() {
  const [query, setQuery] = useState("");
  const { groups, loaded, count, total } = useHelpGroups(query);
  const namespaces = Object.keys(groups).sort((a, b) => {
    const order = ["field", "result", "method"];
    return order.indexOf(a) - order.indexOf(b);
  });

  return (
    <div className="flex flex-col gap-4">
      <Card
        title="Hilfe"
        subtitle={
          loaded
            ? query
              ? `${count} von ${total} Einträgen`
              : `${total} Einträge`
            : "lädt …"
        }
      >
        <input
          className="ol-input"
          data-role="settings"
          type="search"
          placeholder="Suchen in Begriffen und Erklärungen"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Hilfe durchsuchen"
        />
        <p className="mt-2 text-xs" style={{ color: "var(--text-faint)" }}>
          Dieselben Texte stehen hinter den Fragezeichen neben den Feldern. Wer
          sie dort ändern will, ändert <code className="ol-mono">help/help.yaml</code> —
          es gibt nur diese eine Quelle.
        </p>
      </Card>

      {loaded && count === 0 && (
        <Card>
          <Empty>
            {query ? "Nichts gefunden." : "Es sind keine Hilfetexte hinterlegt."}
          </Empty>
        </Card>
      )}

      {namespaces.map((namespace) => (
        <Card
          key={namespace}
          title={NAMESPACE_LABEL[namespace] ?? namespace}
          subtitle={`${groups[namespace]!.length} Einträge · ${namespace}.*`}
        >
          <dl className="flex flex-col gap-4">
            {groups[namespace]!.map(([id, entry]) => (
              <div key={id}>
                <dt className="flex flex-wrap items-baseline gap-2">
                  <span className="text-sm font-semibold">
                    {entry.title ?? id}
                  </span>
                  <code
                    className="ol-mono text-[11px]"
                    style={{ color: "var(--text-faint)" }}
                  >
                    {id}
                  </code>
                </dt>
                <dd className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>
                  {entry.short}
                  {entry.long && (
                    <span
                      className="mt-1 block"
                      style={{ color: "var(--text-faint)" }}
                    >
                      {entry.long}
                    </span>
                  )}
                </dd>
              </div>
            ))}
          </dl>
        </Card>
      ))}
    </div>
  );
}
