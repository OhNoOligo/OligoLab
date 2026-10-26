/* Gemeinsames Gerüst der fünf Bereiche (PHASEN.md 2.3 und 2.4).
 *
 * Jeder Bereich zeigt oben seinen Stand und endet unten mit einem Knopf, der
 * das Ergebnis in den nächsten Bereich trägt. Ist ein Ergebnis veraltet, wird
 * das gesagt und „Neu berechnen" angeboten — statt alte Zahlen stehen zu
 * lassen, als wären sie noch gültig.
 */

import type { ReactNode } from "react";
import { AREA_STATUS_LABEL, useStore, type AreaId } from "../state/store";
import { Card, Notice } from "./ui";

/* ------------------------------------------------------------ Standzeile */

export function AreaStatusBar({
  area,
  onRecompute,
}: {
  area: AreaId;
  onRecompute?: () => void;
}) {
  const { statusOf, state } = useStore();
  const status = statusOf(area);
  const result = state.results[area];

  if (status === "empty") return null;

  if (status === "computed") {
    return (
      <p className="text-xs" style={{ color: "var(--text-faint)" }}>
        Berechnet
        {result && ` um ${new Date(result.at).toLocaleTimeString("de-DE")}`}.
      </p>
    );
  }

  return (
    <Notice level="warn" title="Veraltet">
      Die Eingaben haben sich geändert, seit hier zuletzt gerechnet wurde.
      {onRecompute && (
        <button
          type="button"
          className="ol-button ml-2"
          style={{ padding: "1px 8px", fontSize: 11 }}
          onClick={onRecompute}
        >
          Neu berechnen
        </button>
      )}
    </Notice>
  );
}

/* ------------------------------------------------------------- Übergabe */

export function Handoff({
  label,
  onClick,
  disabled,
  reason,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  /** Warum der Knopf gerade nicht geht. Steht daneben, nicht im Tooltip. */
  reason?: string | null;
}) {
  return (
    <div className="flex flex-wrap items-center justify-end gap-2">
      {disabled && reason && (
        <span className="text-xs" style={{ color: "var(--text-faint)" }}>
          {reason}
        </span>
      )}
      <button
        type="button"
        className="ol-button"
        data-variant={disabled ? undefined : "primary"}
        onClick={onClick}
        disabled={disabled}
      >
        {label} →
      </button>
    </div>
  );
}

/* ------------------------------------------------- noch nicht gefüllt */

export function AreaPlaceholder({
  area,
  title,
  phase,
  what,
  needs,
  children,
}: {
  area: AreaId;
  title: string;
  phase: number;
  /** Was dieser Bereich später kann, in einem Satz. */
  what: string;
  /** Was er dafür braucht — damit man vorher schon das Richtige setzt. */
  needs: ReactNode;
  children?: ReactNode;
}) {
  const { statusOf } = useStore();
  return (
    <Card
      title={title}
      subtitle={what}
      actions={
        <span className="ol-chip ol-role-settings">
          {AREA_STATUS_LABEL[statusOf(area)]}
        </span>
      }
    >
      <Notice level="info" title={`Kommt in Phase ${phase}`}>
        Dieser Bereich ist angelegt und erreichbar, rechnet aber noch nicht.
        Die Navigation, der Zustand und die Übergaben stehen bereits — Phase{" "}
        {phase} füllt nur noch den Inhalt ein.
      </Notice>

      <div className="mt-4">
        <h3 className="mb-1 text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
          Was er dafür braucht
        </h3>
        <div className="text-xs" style={{ color: "var(--text-muted)" }}>
          {needs}
        </div>
      </div>

      {children && <div className="mt-4">{children}</div>}
    </Card>
  );
}

/* -------------------------------------------------- fehlende Voraussetzung */

export function Missing({ children }: { children: ReactNode }) {
  return (
    <Notice level="warn" title="Fehlt noch">
      {children}
    </Notice>
  );
}
