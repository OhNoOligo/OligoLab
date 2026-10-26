/* Die Navigation (PHASEN.md 2.3).
 *
 * Fünf Bereiche in fester Reihenfolge, als Seitenleiste links — nicht als
 * Reiter oben. Reiter suggerieren Gleichrangigkeit; hier gibt es aber einen
 * Weg: vom Ziel über den Entwurf zum Strang, zum Steckbrief und ins 3D.
 *
 * Jeder Eintrag zeigt seinen Stand: leer, berechnet oder veraltet. Der Punkt
 * benutzt bewusst nicht die Ampel — `veraltet` ist keine Bewertung, sondern
 * eine Tatsache über den Rechenstand.
 *
 * Strg+1 bis Strg+5 springen in die fünf Bereiche.
 */

import { useEffect } from "react";
import {
  AREA_STATUS_LABEL,
  useStore,
  type AreaId,
  type AreaStatus,
} from "../state/store";

export interface AreaDefinition {
  id: AreaId;
  path: string;
  label: string;
  hint: string;
  /** Ab welcher Phase der Bereich wirklich rechnet. */
  phase: number;
}

export const AREAS: AreaDefinition[] = [
  { id: "ziel", path: "/ziel", label: "Ziel", hint: "Zielsequenz und Faltung", phase: 4 },
  { id: "entwurf", path: "/entwurf", label: "Entwurf", hint: "Spaltstellen und Kandidaten", phase: 5 },
  { id: "strang", path: "/strang", label: "Strang", hint: "Sequenzkarte und Befunde", phase: 3 },
  { id: "steckbrief", path: "/", label: "Steckbrief", hint: "Massen, Verbrauch, MS", phase: 1 },
  { id: "3d", path: "/3d", label: "3D", hint: "Geometrie und Modell", phase: 6 },
];

export const EXTRA_PAGES = [
  { path: "/bausteine", label: "Bausteine", hint: "Monomere und Konstanten" },
  { path: "/hilfe", label: "Hilfe", hint: "Glossar aller Begriffe" },
];

function StatusDot({ status }: { status: AreaStatus }) {
  return (
    <span
      className={`ol-status-dot ol-status-${status}`}
      title={AREA_STATUS_LABEL[status]}
      aria-hidden="true"
    />
  );
}

export function Sidebar({
  path,
  navigate,
}: {
  path: string;
  navigate: (path: string) => void;
}) {
  const { statusOf } = useStore();

  // Strg+1 bis Strg+5.
  //
  // Auch im Sequenzfeld: Strg+Ziffer ist keine Eingabe und keine gaengige
  // Bearbeitungskombination. Wer eine Sequenz tippt und dann in den Strang
  // springen will, soll das koennen, ohne vorher irgendwohin zu klicken.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) return;
      const index = Number(event.key) - 1;
      if (!Number.isInteger(index) || index < 0 || index >= AREAS.length) return;
      event.preventDefault();
      navigate(AREAS[index]!.path);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate]);

  const entry = (
    item: { path: string; label: string; hint: string },
    status: AreaStatus | null,
    shortcut: string | null,
  ) => {
    const active = item.path === path;
    return (
      <li key={item.path}>
        <button
          type="button"
          className="w-full rounded-lg px-2 py-1.5 text-left"
          aria-current={active ? "page" : undefined}
          onClick={() => navigate(item.path)}
          style={{
            background: active
              ? "color-mix(in srgb, var(--role-result) 12%, transparent)"
              : "transparent",
            border: `1px solid ${active ? "var(--role-result)" : "transparent"}`,
            color: active ? "var(--role-result)" : "var(--text)",
            cursor: "pointer",
          }}
        >
          <span className="flex items-center gap-2">
            {/* Auch ohne Status die Breite des Punktes freihalten, damit die
                Beschriftungen aller Eintraege auf einer Linie stehen. */}
            {status ? (
              <StatusDot status={status} />
            ) : (
              <span className="ol-status-dot" aria-hidden="true" />
            )}
            <span className="flex-1 text-sm font-medium">{item.label}</span>
            {shortcut && (
              <kbd
                className="ol-mono text-[10px]"
                style={{ color: "var(--text-faint)" }}
              >
                {shortcut}
              </kbd>
            )}
          </span>
          <span
            className="block pl-4 text-xs"
            style={{ color: "var(--text-faint)" }}
          >
            {status === "stale" ? "veraltet — neu berechnen" : item.hint}
          </span>
        </button>
      </li>
    );
  };

  return (
    <nav
      className="ol-card shrink-0 self-start p-2 sm:sticky sm:top-20 sm:w-56"
      aria-label="Bereiche"
    >
      <ul className="flex gap-1 sm:flex-col">
        {AREAS.map((area, index) =>
          entry(area, statusOf(area.id), `Strg+${index + 1}`),
        )}
      </ul>

      <hr
        className="my-2"
        style={{ border: "none", borderTop: "1px solid var(--border)" }}
      />

      <ul className="flex gap-1 sm:flex-col">
        {EXTRA_PAGES.map((page) => entry(page, null, null))}
      </ul>
    </nav>
  );
}
