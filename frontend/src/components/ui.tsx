/* Die kleinen gemeinsamen Bausteine der Oberflaeche.
 *
 * Designsprache aus CLAUDE.md: Karten mit duennem Rahmen und 8 px Radius,
 * Ergebniszahlen gross mit Einheit und darunter klein die Methode, keine
 * Verlaeufe, keine Schatten.
 *
 * Jedes Feld und jede Ergebnisgroesse traegt ein `data-help`-Attribut mit
 * sprechender ID. Die Fragezeichen-Hilfe gehoert zu Phase 2 und wird dort nur
 * noch eingehaengt — die IDs stehen hier bereits.
 */

import type { ReactElement, ReactNode } from "react";
import { cloneElement, isValidElement, useId, useState } from "react";
import { HelpTip } from "./HelpTip";
import type { Quantity, Reliability } from "../types";

/* ----------------------------------------------------------------- Karte */

export function Card({
  title,
  subtitle,
  actions,
  children,
  helpId,
}: {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  helpId?: string;
}) {
  return (
    <section className="ol-card" data-help={helpId}>
      {(title || actions) && (
        <header
          className="flex items-start justify-between gap-4 px-4 py-3"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <div>
            {title && (
              <h2 className="flex items-center gap-1.5 text-sm font-semibold">
                {title}
                {helpId && <HelpTip id={helpId} />}
              </h2>
            )}
            {subtitle && (
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                {subtitle}
              </p>
            )}
          </div>
          {actions && <div className="flex shrink-0 gap-2">{actions}</div>}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

/* ------------------------------------------------------- Verlaesslichkeit */

/* Bewusst NICHT die Ampel: die ist laut CLAUDE.md allein fuer Bewertungen da.
 * Die Verlaesslichkeit bekommt ein eigenes, ruhiges Zeichen. */
const RELIABILITY_MARK: Record<Reliability, { mark: string; short: string }> = {
  exakt: { mark: "●", short: "exakt" },
  "Parameter vorhanden": { mark: "◐", short: "Parameter" },
  "genähert über natürliches Analogon": { mark: "○", short: "genähert" },
  "nicht hinterlegt": { mark: "—", short: "fehlt" },
};

export function ReliabilityMark({
  reliability,
  note,
  showLabel = false,
}: {
  reliability: Reliability;
  note?: string | null;
  showLabel?: boolean;
}) {
  const entry = RELIABILITY_MARK[reliability];
  const title = note ? `${reliability} — ${note}` : reliability;
  return (
    <span
      className="inline-flex cursor-help items-center gap-1 text-xs"
      style={{ color: "var(--text-faint)" }}
      title={title}
      data-help="method.reliability"
      aria-label={title}
    >
      <span aria-hidden="true">{entry.mark}</span>
      {showLabel && <span>{entry.short}</span>}
    </span>
  );
}

/* ------------------------------------------------------------ Kopierknopf */

export function CopyButton({ value, label }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // Ohne Zwischenablage-Rechte: der Wert steht ja daneben und ist
      // markierbar. Kein Grund fuer eine Fehlermeldung.
      return;
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  return (
    <button
      type="button"
      className="ol-button"
      style={{ padding: "2px 8px", fontSize: 11 }}
      onClick={copy}
      title={label ? `${label} kopieren` : "Wert kopieren"}
      aria-label={label ? `${label} kopieren` : "Wert kopieren"}
    >
      {copied ? "kopiert" : "kopieren"}
    </button>
  );
}

/* --------------------------------------------------------- Ergebniszahlen */

export function formatNumber(
  value: number | null | undefined,
  digits = 2,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString("de-DE", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** Gross die Zahl mit Einheit, klein darunter die Methode. */
export function ResultNumber({
  label,
  quantity,
  digits = 2,
  helpId,
  copy = false,
  size = "normal",
}: {
  label: string;
  quantity: Quantity;
  digits?: number;
  helpId?: string;
  copy?: boolean;
  size?: "normal" | "large";
}) {
  const missing = quantity.value === null;
  const text = formatNumber(quantity.value, digits);

  return (
    <div data-help={helpId}>
      {/* Der Kopierknopf sitzt in der Beschriftungszeile. Neben der Zahl
          wuerde er in schmalen Spalten darueberlaufen. */}
      <div className="flex items-center justify-between gap-2">
        <span
          className="flex min-w-0 items-center gap-1.5 text-xs"
          style={{ color: "var(--text-muted)" }}
        >
          {label}
          {helpId && <HelpTip id={helpId} />}
        </span>
        <span className="flex shrink-0 items-center gap-1.5">
          <ReliabilityMark
            reliability={quantity.reliability}
            note={quantity.note}
          />
          {copy && !missing && (
            <CopyButton value={String(quantity.value)} label={label} />
          )}
        </span>
      </div>
      <div className="flex items-baseline gap-2">
        <span
          className="ol-mono font-semibold tabular-nums"
          style={{
            fontSize: size === "large" ? 24 : 19,
            color: missing ? "var(--text-faint)" : "var(--text)",
          }}
        >
          {text}
        </span>
        {!missing && quantity.unit && (
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            {quantity.unit}
          </span>
        )}
      </div>
      <p className="mt-0.5 text-xs" style={{ color: "var(--text-faint)" }}>
        {quantity.note && missing ? quantity.note : quantity.method}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ Chips */

export function Chip({
  role,
  children,
  title,
}: {
  role: "input" | "settings" | "result";
  children: ReactNode;
  title?: string;
}) {
  return (
    <span className={`ol-chip ol-role-${role}`} title={title}>
      {children}
    </span>
  );
}

/** Die Ampel — nur fuer Bewertungen, nie dekorativ. */
export function Rating({
  level,
  children,
  title,
}: {
  level: "good" | "warn" | "bad";
  children: ReactNode;
  title?: string;
}) {
  return (
    <span className={`ol-chip ol-rating-${level}`} title={title}>
      <span aria-hidden="true">
        {level === "good" ? "●" : level === "warn" ? "▲" : "■"}
      </span>
      {children}
    </span>
  );
}

/* ----------------------------------------------------------------- Felder */

export function Field({
  label,
  helpId,
  role = "input",
  hint,
  htmlFor,
  children,
}: {
  label: string;
  helpId?: string;
  role?: "input" | "settings";
  hint?: string;
  /** Nur noetig, wenn mehrere Bedienelemente im Feld stehen. */
  htmlFor?: string;
  children: ReactNode;
}) {
  // Kein `<label>` um das Ganze: ein Knopf (das Fragezeichen) in einem Label
  // loeste beim Klick das zugehoerige Feld mit aus. Die Beziehung zwischen
  // Beschriftung und Feld stellt darum `htmlFor` auf `id` her — ohne sie
  // haette das Feld keinen vorlesbaren Namen.
  const generatedId = useId();
  const controlId = htmlFor ?? generatedId;

  // Das einzelne Bedienelement bekommt die ID untergeschoben. Hat es schon
  // eine oder sind es mehrere, setzt der Aufrufer `htmlFor` selbst.
  const control =
    htmlFor === undefined && isValidElement(children)
      ? cloneElement(children as ReactElement<{ id?: string }>, {
          id: (children.props as { id?: string }).id ?? controlId,
        })
      : children;

  return (
    <div className="block" data-help={helpId}>
      <label
        htmlFor={controlId}
        className="mb-1 flex items-center gap-1.5 text-xs font-medium"
        style={{ color: "var(--text-muted)" }}
      >
        {label}
        <span
          aria-hidden="true"
          title={role === "input" ? "Eingabe" : "Einstellung"}
          style={{
            width: 6,
            height: 6,
            borderRadius: 999,
            background:
              role === "input" ? "var(--role-input)" : "var(--role-settings)",
          }}
        />
        {helpId && <HelpTip id={helpId} />}
      </label>
      {control}
      {hint && (
        <span
          className="mt-1 block text-xs"
          style={{ color: "var(--text-faint)" }}
        >
          {hint}
        </span>
      )}
    </div>
  );
}

export function NumberInput({
  value,
  onChange,
  step = "any",
  min,
  role = "settings",
  helpId,
  id,
}: {
  value: number | "";
  onChange: (value: number | "") => void;
  step?: string | number;
  min?: number;
  role?: "input" | "settings";
  helpId?: string;
  /** Wird von `Field` gesetzt, damit die Beschriftung darauf zeigen kann. */
  id?: string;
}) {
  return (
    <input
      id={id}
      type="number"
      className="ol-input ol-mono tabular-nums"
      data-role={role}
      data-help={helpId}
      step={step}
      min={min}
      value={value}
      onChange={(event) => {
        const raw = event.target.value;
        onChange(raw === "" ? "" : Number(raw));
      }}
    />
  );
}

/* --------------------------------------------------------------- Meldungen */

export function Notice({
  level,
  title,
  children,
}: {
  level: "info" | "warn" | "bad";
  title?: string;
  children: ReactNode;
}) {
  const color =
    level === "info"
      ? "var(--role-result)"
      : level === "warn"
        ? "var(--rating-warn)"
        : "var(--rating-bad)";
  return (
    <div
      className="rounded-lg px-3 py-2 text-xs"
      style={{
        border: `1px solid ${color}`,
        background: `color-mix(in srgb, ${color} 10%, transparent)`,
        color: "var(--text)",
      }}
      role={level === "info" ? undefined : "alert"}
    >
      {title && <strong className="block">{title}</strong>}
      {children}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="py-6 text-center text-xs" style={{ color: "var(--text-faint)" }}>
      {children}
    </p>
  );
}
