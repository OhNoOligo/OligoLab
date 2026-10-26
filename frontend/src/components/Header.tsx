/* Die Kopfzeile (PHASEN.md 2.2).
 *
 * Immer sichtbar, drei Plätze: links das aktive DNAzym, in der Mitte die
 * aktive Ziel-RNA, rechts die Bedingungen.
 *
 * Ist ein Platz leer, steht dort ein Eingabefeld — keine leere Zeile. Wer
 * eine Oberfläche zum ersten Mal öffnet, soll sehen, was sie von ihm will.
 *
 * Die Masse holt die Kopfzeile selbst über `/api/summary`. Eine im Zustand
 * mitgeführte Kopie liefe irgendwann gegen die Rechnung im Steckbrief.
 */

import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import {
  describeBuffer,
  describeOligoConc,
  useStore,
  type BufferSettings,
} from "../state/store";
import { HelpTip } from "./HelpTip";
import { formatNumber } from "./ui";

function SlotLabel({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="text-[10px] uppercase tracking-wide"
      style={{ color: "var(--text-faint)" }}
    >
      {children}
    </span>
  );
}

/* ------------------------------------------------------- aktives DNAzym */

function OligoSlot() {
  const { state, setOligo, patchOligo } = useStore();
  const oligo = state.activeOligo;
  const [summary, setSummary] = useState<{
    length: number;
    mass: number | null;
    problems: number;
  } | null>(null);
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const sequence = oligo?.sequence ?? "";

  useEffect(() => {
    if (!sequence.trim()) {
      setSummary(null);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      api
        .summary(sequence)
        .then((result) => {
          if (cancelled) return;
          setSummary({
            length: result.length,
            mass: result.mass_fully_deprotected,
            problems: result.problems,
          });
        })
        .catch(() => !cancelled && setSummary(null));
    }, 300);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [sequence]);

  useEffect(() => {
    if (!switcherOpen) return;
    const onPointer = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setSwitcherOpen(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSwitcherOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [switcherOpen]);

  if (!oligo || !oligo.sequence.trim()) {
    return (
      <div className="ol-header-slot min-w-0 flex-1">
        <SlotLabel>DNAzym</SlotLabel>
        <input
          className="ol-input"
          data-role="input"
          data-help="field.sequence"
          style={{ padding: "2px 6px", fontSize: 12 }}
          placeholder="Sequenz einfügen, um zu beginnen"
          value={oligo?.sequence ?? ""}
          onChange={(event) =>
            setOligo({
              name: oligo?.name ?? "Unbenannt",
              sequence: event.target.value,
              notes: oligo?.notes ?? "",
            })
          }
          aria-label="Sequenz des DNAzyms"
        />
      </div>
    );
  }

  const others = state.recentOligos.filter(
    (entry) => entry.sequence !== oligo.sequence || entry.name !== oligo.name,
  );

  return (
    <div className="relative min-w-0 flex-1" ref={containerRef}>
      <button
        type="button"
        className="ol-header-slot w-full"
        onClick={() => setSwitcherOpen((open) => !open)}
        aria-expanded={switcherOpen}
        aria-haspopup="listbox"
        title="Zuletzt benutzte DNAzyme"
      >
        <SlotLabel>DNAzym</SlotLabel>
        <span className="flex items-baseline gap-2">
          <span className="truncate text-sm font-medium">
            {oligo.name || "Unbenannt"}
          </span>
          <span
            className="ol-mono shrink-0 text-xs tabular-nums"
            style={{ color: "var(--text-muted)" }}
          >
            {summary ? `${summary.length} nt` : "…"}
            {summary?.mass != null && ` · ${formatNumber(summary.mass)} Da`}
            {summary != null && summary.problems > 0 && (
              <span style={{ color: "var(--rating-bad)" }}>
                {` · ${summary.problems} unklar`}
              </span>
            )}
          </span>
        </span>
      </button>

      {switcherOpen && (
        <div
          className="ol-card absolute left-0 top-full z-40 mt-1 w-80 p-2"
          role="listbox"
          aria-label="Zuletzt benutzte DNAzyme"
        >
          <input
            className="ol-input mb-2"
            data-role="input"
            style={{ fontSize: 12 }}
            value={oligo.name}
            placeholder="Name"
            onChange={(event) => patchOligo({ name: event.target.value })}
            aria-label="Name des DNAzyms"
          />
          {others.length === 0 ? (
            <p className="px-1 py-2 text-xs" style={{ color: "var(--text-faint)" }}>
              Noch keine weiteren. Was du im Steckbrief lädst, landet hier.
            </p>
          ) : (
            <ul>
              {others.map((entry) => (
                <li key={`${entry.name}-${entry.sequence}`}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={false}
                    className="ol-header-slot w-full"
                    onClick={() => {
                      setOligo(entry);
                      setSwitcherOpen(false);
                    }}
                  >
                    <span className="truncate text-sm">
                      {entry.name || "Unbenannt"}
                    </span>
                    <span
                      className="ol-mono truncate text-xs"
                      style={{ color: "var(--text-faint)" }}
                    >
                      {entry.sequence.slice(0, 40)}
                      {entry.sequence.length > 40 ? "…" : ""}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

/* --------------------------------------------------------- aktive Ziel-RNA */

function TargetSlot() {
  const { state, setTarget } = useStore();
  const target = state.activeTarget;

  if (!target || !target.sequence.trim()) {
    return (
      <div className="ol-header-slot min-w-0 flex-1">
        <SlotLabel>Ziel-RNA</SlotLabel>
        <input
          className="ol-input"
          data-role="input"
          style={{ padding: "2px 6px", fontSize: 12 }}
          placeholder="Zielsequenz einfügen"
          value={target?.sequence ?? ""}
          onChange={(event) =>
            setTarget({
              name: target?.name ?? "Unbenannt",
              sequence: event.target.value,
              source: target?.source ?? "Direkteingabe",
              region: null,
            })
          }
          aria-label="Sequenz der Ziel-RNA"
        />
      </div>
    );
  }

  const length = target.sequence.replace(/\s/g, "").length;
  const region = target.region
    ? `${target.region.start}–${target.region.end}`
    : "ganze Länge";

  return (
    <div className="ol-header-slot min-w-0 flex-1">
      <SlotLabel>Ziel-RNA</SlotLabel>
      <span className="flex items-baseline gap-2">
        <span className="truncate text-sm font-medium">
          {target.name || "Unbenannt"}
        </span>
        <span
          className="ol-mono shrink-0 text-xs tabular-nums"
          style={{ color: "var(--text-muted)" }}
        >
          {length} nt · {region}
        </span>
      </span>
    </div>
  );
}

/* ------------------------------------------------------------ Bedingungen */

const BUFFER_FIELDS: {
  key: keyof BufferSettings;
  label: string;
  unit: string;
  step: number;
}[] = [
  { key: "oligoConcNm", label: "Oligo", unit: "nM", step: 50 },
  { key: "naMm", label: "Na⁺", unit: "mM", step: 10 },
  { key: "kMm", label: "K⁺", unit: "mM", step: 10 },
  { key: "trisMm", label: "Tris", unit: "mM", step: 5 },
  { key: "mgMm", label: "Mg²⁺", unit: "mM", step: 1 },
  { key: "reactionTempC", label: "Reaktion", unit: "°C", step: 1 },
];

function BufferSlot() {
  const { state, patchBuffer, resetBuffer } = useStore();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="relative shrink-0" ref={containerRef}>
      <button
        type="button"
        className="ol-header-slot"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        title="Bedingungen ändern"
      >
        <SlotLabel>Bedingungen</SlotLabel>
        <span className="ol-mono text-xs tabular-nums">
          {describeBuffer(state.buffer)}
        </span>
      </button>

      {open && (
        <div className="ol-card absolute right-0 top-full z-40 mt-1 w-72 p-3">
          <div className="mb-2 flex items-center justify-between">
            <strong className="text-xs">Bedingungen</strong>
            <button
              type="button"
              className="ol-button"
              style={{ padding: "1px 6px", fontSize: 11 }}
              onClick={resetBuffer}
            >
              zurücksetzen
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {BUFFER_FIELDS.map((field) => (
              <label key={field.key} className="block">
                <span
                  className="mb-0.5 flex items-center gap-1 text-[11px]"
                  style={{ color: "var(--text-muted)" }}
                >
                  {field.label} ({field.unit})
                  <span
                    aria-hidden="true"
                    style={{
                      width: 5,
                      height: 5,
                      borderRadius: 999,
                      background: "var(--role-settings)",
                    }}
                  />
                </span>
                <input
                  type="number"
                  className="ol-input ol-mono tabular-nums"
                  data-role="settings"
                  style={{ padding: "3px 6px", fontSize: 12 }}
                  step={field.step}
                  min={0}
                  value={state.buffer[field.key]}
                  onChange={(event) =>
                    patchBuffer({ [field.key]: Number(event.target.value) })
                  }
                />
              </label>
            ))}
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Oligo-Konzentration entspricht {describeOligoConc(state.buffer)}. Diese
            Werte gehen ab Phase 5 in Tm und ΔG ein.
          </p>
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------- Kopfzeile */

export function Header() {
  return (
    <header
      // Ausdrueckliche Landmarke: die Karten im Inhalt benutzen ebenfalls
      // `<header>`, und ein Screenreader soll wissen, welches davon die
      // Kopfzeile der Seite ist.
      role="banner"
      aria-label="Aktives DNAzym, Ziel-RNA und Bedingungen"
      className="ol-card sticky top-0 z-30 flex flex-wrap items-stretch gap-2 px-3 py-2"
      style={{ background: "var(--surface)" }}
    >
      <OligoSlot />
      <div
        aria-hidden="true"
        className="hidden w-px shrink-0 sm:block"
        style={{ background: "var(--border)" }}
      />
      <TargetSlot />
      <div
        aria-hidden="true"
        className="hidden w-px shrink-0 sm:block"
        style={{ background: "var(--border)" }}
      />
      <div className="ol-helptip-right flex items-center gap-1">
        <BufferSlot />
        <HelpTip id="field.buffer" />
      </div>
    </header>
  );
}
