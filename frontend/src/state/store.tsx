/* Der globale Zustand (PHASEN.md 2.1).
 *
 * Drei Dinge liegen hier und nur hier:
 *
 *   activeOligo     das DNAzym, an dem gerade gearbeitet wird
 *   activeTarget    die Ziel-RNA samt gewähltem Bereich
 *   buffer          Oligo-Konzentration, Kationen, Reaktionstemperatur
 *
 * **Niemand kopiert Sequenzen zwischen Seiten.** Jeder Bereich liest aus
 * diesem Zustand. Hätte eine Seite ihre eigene Kopie der Sequenz, liefe sie
 * irgendwann auseinander — und niemand merkte es.
 *
 * Ändert sich etwas, werden abgeleitete Ergebnisse ungültig. Dafür merkt sich
 * jeder Bereich einen Fingerabdruck der Eingaben, mit denen er gerechnet hat.
 * Stimmt der nicht mehr, ist der Bereich `veraltet` — und zeigt das, statt
 * alte Zahlen stehen zu lassen.
 *
 * Der ganze Zustand wird in `localStorage` gespiegelt, damit ein Neuladen
 * nichts verliert.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  type ReactNode,
} from "react";

/* ------------------------------------------------------------------ Typen */

export const AREA_IDS = ["ziel", "entwurf", "strang", "steckbrief", "3d"] as const;
export type AreaId = (typeof AREA_IDS)[number];

export interface OligoRef {
  name: string;
  sequence: string;
  notes: string;
}

export interface TargetRef {
  name: string;
  sequence: string;
  source: string;
  /** Gewählter Ausschnitt, 1-basiert und einschließlich beider Enden. */
  region: { start: number; end: number } | null;
}

export interface BufferSettings {
  /** Oligo-Konzentration in nmol/L. */
  oligoConcNm: number;
  naMm: number;
  kMm: number;
  trisMm: number;
  mgMm: number;
  reactionTempC: number;
}

/** Womit ein Bereich zuletzt gerechnet hat. */
export interface AreaResult {
  fingerprint: string;
  at: string;
}

export interface AppState {
  activeOligo: OligoRef | null;
  activeTarget: TargetRef | null;
  buffer: BufferSettings;
  /** Für den Schnellwechsler in der Kopfzeile, neueste zuerst. */
  recentOligos: OligoRef[];
  results: Partial<Record<AreaId, AreaResult>>;
}

export type AreaStatus = "empty" | "computed" | "stale";

export const AREA_STATUS_LABEL: Record<AreaStatus, string> = {
  empty: "leer",
  computed: "berechnet",
  stale: "veraltet",
};

/* ---------------------------------------------------------- Voreinstellung */

export const DEFAULT_BUFFER: BufferSettings = {
  oligoConcNm: 1000,
  naMm: 50,
  kMm: 0,
  trisMm: 10,
  mgMm: 2,
  reactionTempC: 37,
};

const EMPTY_STATE: AppState = {
  activeOligo: null,
  activeTarget: null,
  buffer: DEFAULT_BUFFER,
  recentOligos: [],
  results: {},
};

const MAX_RECENT = 8;

/* ------------------------------------------------------- Fingerabdrücke
 *
 * Je Bereich: woraus hängt sein Ergebnis ab? Ändert sich eines dieser Stücke,
 * ist das Ergebnis veraltet. Die Buffereinstellungen gehen nur dort ein, wo
 * sie wirklich gebraucht werden — sonst würde ein Dreh am Magnesium den
 * Steckbrief grundlos entwerten.
 */

function fingerprintOf(state: AppState, area: AreaId): string {
  const oligo = state.activeOligo?.sequence ?? "";
  const target = state.activeTarget?.sequence ?? "";
  const region = state.activeTarget?.region
    ? `${state.activeTarget.region.start}-${state.activeTarget.region.end}`
    : "";
  const buffer = JSON.stringify(state.buffer);

  switch (area) {
    case "ziel":
      return JSON.stringify([target, region]);
    case "entwurf":
      // Tm und ΔG hängen an den Kationen und der Reaktionstemperatur.
      return JSON.stringify([target, region, buffer]);
    case "strang":
      return JSON.stringify([oligo]);
    case "steckbrief":
      return JSON.stringify([oligo]);
    case "3d":
      return JSON.stringify([oligo, target, region]);
  }
}

export function areaStatus(state: AppState, area: AreaId): AreaStatus {
  const result = state.results[area];
  if (!result) return "empty";
  return result.fingerprint === fingerprintOf(state, area) ? "computed" : "stale";
}

/* ----------------------------------------------------------------- Aktionen */

type Action =
  | { type: "setOligo"; oligo: OligoRef | null }
  | { type: "patchOligo"; patch: Partial<OligoRef> }
  | { type: "setTarget"; target: TargetRef | null }
  | { type: "patchTarget"; patch: Partial<TargetRef> }
  | { type: "patchBuffer"; patch: Partial<BufferSettings> }
  | { type: "resetBuffer" }
  | { type: "markComputed"; area: AreaId }
  | { type: "clearResult"; area: AreaId }
  | { type: "hydrate"; state: AppState };

function rememberOligo(list: OligoRef[], oligo: OligoRef | null): OligoRef[] {
  if (!oligo || !oligo.sequence.trim()) return list;
  const without = list.filter(
    (entry) => entry.sequence !== oligo.sequence || entry.name !== oligo.name,
  );
  return [oligo, ...without].slice(0, MAX_RECENT);
}

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "hydrate":
      return action.state;

    case "setOligo":
      return {
        ...state,
        activeOligo: action.oligo,
        recentOligos: rememberOligo(state.recentOligos, action.oligo),
      };

    case "patchOligo": {
      const base: OligoRef = state.activeOligo ?? {
        name: "",
        sequence: "",
        notes: "",
      };
      return { ...state, activeOligo: { ...base, ...action.patch } };
    }

    case "setTarget":
      return { ...state, activeTarget: action.target };

    case "patchTarget": {
      const base: TargetRef = state.activeTarget ?? {
        name: "",
        sequence: "",
        source: "",
        region: null,
      };
      return { ...state, activeTarget: { ...base, ...action.patch } };
    }

    case "patchBuffer":
      return { ...state, buffer: { ...state.buffer, ...action.patch } };

    case "resetBuffer":
      return { ...state, buffer: DEFAULT_BUFFER };

    case "markComputed":
      return {
        ...state,
        results: {
          ...state.results,
          [action.area]: {
            fingerprint: fingerprintOf(state, action.area),
            at: new Date().toISOString(),
          },
        },
      };

    case "clearResult": {
      const results = { ...state.results };
      delete results[action.area];
      return { ...state, results };
    }
  }
}

/* -------------------------------------------------------------- Spiegelung */

const STORAGE_KEY = "oligolab.state.v1";

function loadFromStorage(): AppState {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY_STATE;
    const parsed = JSON.parse(raw) as Partial<AppState>;
    // Nachsichtig lesen: eine ältere oder von Hand verbogene Fassung darf die
    // App nicht lahmlegen. Fehlende Stücke bekommen ihre Voreinstellung.
    return {
      activeOligo: parsed.activeOligo ?? null,
      activeTarget: parsed.activeTarget ?? null,
      buffer: { ...DEFAULT_BUFFER, ...(parsed.buffer ?? {}) },
      recentOligos: Array.isArray(parsed.recentOligos) ? parsed.recentOligos : [],
      results: parsed.results ?? {},
    };
  } catch {
    // Privater Modus, volle Quota, kaputter Inhalt — die App läuft trotzdem.
    return EMPTY_STATE;
  }
}

/* ------------------------------------------------------------------ Context */

interface Store {
  state: AppState;
  setOligo: (oligo: OligoRef | null) => void;
  patchOligo: (patch: Partial<OligoRef>) => void;
  setTarget: (target: TargetRef | null) => void;
  patchTarget: (patch: Partial<TargetRef>) => void;
  patchBuffer: (patch: Partial<BufferSettings>) => void;
  resetBuffer: () => void;
  markComputed: (area: AreaId) => void;
  clearResult: (area: AreaId) => void;
  statusOf: (area: AreaId) => AreaStatus;
}

const StoreContext = createContext<Store | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, EMPTY_STATE, loadFromStorage);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // Nicht schreiben zu können ist kein Grund, die Arbeit abzubrechen.
    }
  }, [state]);

  const value = useMemo<Store>(
    () => ({
      state,
      setOligo: (oligo) => dispatch({ type: "setOligo", oligo }),
      patchOligo: (patch) => dispatch({ type: "patchOligo", patch }),
      setTarget: (target) => dispatch({ type: "setTarget", target }),
      patchTarget: (patch) => dispatch({ type: "patchTarget", patch }),
      patchBuffer: (patch) => dispatch({ type: "patchBuffer", patch }),
      resetBuffer: () => dispatch({ type: "resetBuffer" }),
      markComputed: (area) => dispatch({ type: "markComputed", area }),
      clearResult: (area) => dispatch({ type: "clearResult", area }),
      statusOf: (area) => areaStatus(state, area),
    }),
    [state],
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore(): Store {
  const store = useContext(StoreContext);
  if (!store) {
    throw new Error("useStore braucht einen <StoreProvider> darüber.");
  }
  return store;
}

/** Die Bedingungen kompakt, wie sie in der Kopfzeile stehen. */
export function describeBuffer(buffer: BufferSettings): string {
  const parts = [`${buffer.naMm} mM Na`];
  if (buffer.kMm > 0) parts.push(`${buffer.kMm} mM K`);
  if (buffer.mgMm > 0) parts.push(`${buffer.mgMm} mM Mg`);
  if (buffer.trisMm > 0) parts.push(`${buffer.trisMm} mM Tris`);
  parts.push(`${buffer.reactionTempC} °C`);
  return parts.join(", ");
}

/** Die Oligo-Konzentration lesbar: nM unter 1000, sonst µM. */
export function describeOligoConc(buffer: BufferSettings): string {
  return buffer.oligoConcNm >= 1000
    ? `${(buffer.oligoConcNm / 1000).toLocaleString("de-DE")} µM`
    : `${buffer.oligoConcNm.toLocaleString("de-DE")} nM`;
}

export const useAreaStatus = (area: AreaId): AreaStatus => useStore().statusOf(area);

export function useCallbackMarkComputed(area: AreaId) {
  const { markComputed } = useStore();
  return useCallback(() => markComputed(area), [markComputed, area]);
}
