/* Die Fragezeichen-Hilfe (PHASEN.md 2.6).
 *
 * Alle Texte kommen aus einer einzigen `help/help.yaml`. Neben jedem
 * Formularfeld und jeder Ergebniszahl steht ein kleines graues Fragezeichen:
 * Überfahren oder Fokussieren zeigt zwei bis drei Sätze, ein Klick öffnet ein
 * Panel mit den Einzelheiten.
 *
 * Bedienbar mit Maus, Tastatur und Finger. Auf einem Touchgerät gibt es kein
 * Überfahren, darum muss der Klick allein genügen — er tut es.
 *
 * `aria-describedby` zeigt vom Fragezeichen auf den Kurztext, damit ein
 * Screenreader ihn beim Fokussieren vorliest.
 */

import {
  createContext,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api } from "../api";
import type { HelpEntry } from "../types";

/* ----------------------------------------------------------------- Context */

interface HelpStore {
  entries: Record<string, HelpEntry>;
  loaded: boolean;
}

const HelpContext = createContext<HelpStore>({ entries: {}, loaded: false });

export function HelpProvider({ children }: { children: ReactNode }) {
  const [store, setStore] = useState<HelpStore>({ entries: {}, loaded: false });

  useEffect(() => {
    let cancelled = false;
    api
      .help()
      .then((result) => {
        if (!cancelled) setStore({ entries: result.entries ?? {}, loaded: true });
      })
      .catch(() => {
        // Ohne Hilfetexte bleibt die App voll bedienbar; die Fragezeichen
        // verschwinden dann einfach.
        if (!cancelled) setStore({ entries: {}, loaded: true });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return <HelpContext.Provider value={store}>{children}</HelpContext.Provider>;
}

export function useHelpEntries(): HelpStore {
  return useContext(HelpContext);
}

export function useHelpEntry(id: string | undefined): HelpEntry | null {
  const { entries } = useHelpEntries();
  return id ? (entries[id] ?? null) : null;
}

/* ------------------------------------------------------------------- Tip */

export function HelpTip({ id }: { id: string }) {
  const entry = useHelpEntry(id);
  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState(false);
  const containerRef = useRef<HTMLSpanElement>(null);
  const describedById = useId();

  // Das Panel schließt bei Klick nach außen und auf Escape — sonst bliebe es
  // auf einem Touchgerät offen stehen.
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

  // Gibt es zu dieser ID keinen Text, steht da auch kein Fragezeichen —
  // ein Fragezeichen, das nichts erklärt, ist schlimmer als keines.
  if (!entry) return null;

  const showTooltip = hovered && !open;

  return (
    <span className="relative inline-flex" ref={containerRef}>
      <button
        type="button"
        className="ol-helptip"
        aria-label={`Hilfe zu ${entry.title ?? id}`}
        aria-describedby={describedById}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onFocus={() => setHovered(true)}
        onBlur={() => setHovered(false)}
      >
        ?
      </button>

      {/* Immer im Baum, damit `aria-describedby` greift; sichtbar nur beim
          Überfahren oder Fokussieren. */}
      <span
        id={describedById}
        role="tooltip"
        className="ol-helptip-bubble"
        data-visible={showTooltip ? "true" : "false"}
      >
        {entry.short}
      </span>

      {open && (
        <span className="ol-helptip-panel" role="dialog" aria-label={entry.title ?? id}>
          {entry.title && <strong className="mb-1 block">{entry.title}</strong>}
          <span className="block">{entry.short}</span>
          {entry.long && (
            <span
              className="mt-2 block"
              style={{ color: "var(--text-muted)" }}
            >
              {entry.long}
            </span>
          )}
        </span>
      )}
    </span>
  );
}

/* --------------------------------------------------------------- Glossar */

/** Alle Einträge, nach Namensraum gruppiert — für die Seite /hilfe. */
export function useHelpGroups(query: string) {
  const { entries, loaded } = useHelpEntries();
  return useMemo(() => {
    const needle = query.trim().toLowerCase();
    const matching = Object.entries(entries).filter(([id, entry]) => {
      if (!needle) return true;
      return (
        id.toLowerCase().includes(needle) ||
        (entry.title ?? "").toLowerCase().includes(needle) ||
        entry.short.toLowerCase().includes(needle) ||
        (entry.long ?? "").toLowerCase().includes(needle)
      );
    });

    const groups: Record<string, [string, HelpEntry][]> = {};
    for (const [id, entry] of matching) {
      const namespace = id.split(".")[0] ?? "sonstige";
      (groups[namespace] ??= []).push([id, entry]);
    }
    for (const list of Object.values(groups)) list.sort((a, b) => a[0].localeCompare(b[0]));
    return { groups, loaded, count: matching.length, total: Object.keys(entries).length };
  }, [entries, loaded, query]);
}

export const NAMESPACE_LABEL: Record<string, string> = {
  field: "Eingabefelder und Einstellungen",
  result: "Ergebniszahlen",
  method: "Verfahren und Kennzeichen",
};
