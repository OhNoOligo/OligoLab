/* Ein Platz fuer alle Aufrufe ans Backend.
 *
 * Alles laeuft lokal; es gibt keinen Schluessel und keine fremde Adresse
 * (CLAUDE.md, Regel 4). Im Entwicklungsbetrieb leitet Vite `/api` auf Port
 * 8000 weiter, im gebauten Zustand liefert FastAPI beides aus.
 */

import type {
  AccessibilityView,
  ConsumptionTable,
  CandidateView,
  CoreSpecView,
  DesignView,
  FetchResultView,
  LibraryTarget,
  StrandView,
  TargetView,
  UpView,
  HelpEntry,
  LibraryOligo,
  LibrarySample,
  LoadingRecipe,
  ModificationSpecView,
  MonomerCatalog,
  ModifyResultView,
  NotationProblem,
  OdConversion,
  Profile,
  ScanView,
  SnapshotView,
  TargetFoldView,
  TmView,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch (cause) {
    throw new ApiError(
      0,
      cause,
      "Das Backend ist nicht erreichbar. Läuft `uvicorn app.main:app`?",
    );
  }

  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = (await response.json())?.detail ?? null;
    } catch {
      detail = await response.text().catch(() => null);
    }
    throw new ApiError(
      response.status,
      detail,
      typeof detail === "string"
        ? detail
        : `Der Aufruf ${path} ist mit ${response.status} fehlgeschlagen.`,
    );
  }

  return (await response.json()) as T;
}

const post = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

export interface DesignBody {
  sequence: string;
  start?: number;
  end?: number;
  include_poor?: boolean;
  with_structure?: boolean;
  probe_length?: number;
  settings?: Partial<{
    arm5_length: number;
    arm3_length: number;
    core_id: string | null;
    arm_dg_target: number;
    max_imbalance: number;
    self_fold_limit: number;
    weight_junction: number;
    weight_arm_dg: number;
    weight_balance: number;
    weight_self_fold: number;
    weight_accessibility: number;
  }>;
  conditions?: Record<string, number>;
  limit?: number;
}

export const api = {
  health: () => request<{ status: string; version: string }>("/api/health"),

  summary: (sequence: string) =>
    post<{
      length: number;
      mass_fully_deprotected: number | null;
      problems: number;
      phosphorothioates: number;
      conjugates: number;
    }>("/api/summary", { sequence }),

  strand: (sequence: string, withHomodimer = true) =>
    post<StrandView>("/api/strand", {
      sequence,
      with_homodimer: withHomodimer,
    }),

  cores: () => request<{ cores: CoreSpecView[] }>("/api/cores"),

  /* ------------------------------------------------------ Ziel-RNA */

  targetRead: (text: string, name?: string) =>
    post<{ target: TargetView; detected_format: string }>("/api/target/read", {
      text,
      name,
    }),

  targetFetch: (body: {
    source: "ensembl" | "ncbi" | "rnacentral";
    identifier: string;
    species?: string;
  }) => post<FetchResultView>("/api/target/fetch", body),

  targetFold: (sequence: string, start?: number, end?: number) =>
    post<TargetFoldView>("/api/target/fold", { sequence, start, end }),

  targetAccessibility: (body: {
    sequence: string;
    start?: number;
    end?: number;
    probe_length?: number;
    window?: number;
    max_span?: number;
  }) => post<AccessibilityView>("/api/target/accessibility", body),

  targetUp: (body: {
    target_sequence: string;
    site_start: number;
    site_end: number;
    oligo_sequence: string;
    temperature_c?: number;
  }) => post<UpView>("/api/target/up", body),

  libraryTargets: (query?: string) =>
    request<{ total: number; targets: LibraryTarget[] }>(
      `/api/library/targets${query ? `?q=${encodeURIComponent(query)}` : ""}`,
    ),

  saveTarget: (body: Record<string, unknown>) =>
    post<{ id: number; name: string }>("/api/library/targets", body),

  deleteTarget: (id: number) =>
    request<{ deleted: number }>(`/api/library/targets/${id}`, {
      method: "DELETE",
    }),

  profile: (sequence: string, name?: string, notes?: string) =>
    post<Profile>("/api/profile", { sequence, name, notes }),

  translate: (sequence: string, to: "rna" | "dna") =>
    post<{
      sequence: string | null;
      problems: NotationProblem[];
      untranslated: string[];
    }>("/api/translate", { sequence, to }),

  synthesis: (body: {
    sequence: string;
    coupling_volume_ml: number;
    reserve_fraction: number;
    syntheses: number;
  }) => post<ConsumptionTable>("/api/synthesis", body),

  msLadder: (body: {
    sequence: string;
    charge_min: number;
    charge_max: number;
    basis?: "average" | "monoisotopic";
  }) =>
    post<{
      basis: import("./types").Quantity;
      ladder: { charge: number; mz: number }[];
      isotopes: { mass: number; intensity_rel: number }[];
      formula: string | null;
      max_physical_charge: number;
      note: string | null;
    }>("/api/ms/ladder", body),

  loadingPage: (body: {
    n_loading_pmol: number;
    n_stock_nmol: number;
    v_stock_ul: number;
  }) => post<LoadingRecipe>("/api/loading/page", body),

  loadingLcms: (body: {
    n_injection_pmol: number;
    n_stock_nmol: number;
    v_stock_ul: number;
    v_sample_ul: number;
    v_injection_ul: number;
  }) => post<LoadingRecipe>("/api/loading/lcms", body),

  convertOd: (body: {
    eps260: number;
    molar_mass: number;
    od?: number | null;
    nmol?: number | null;
    microgram?: number | null;
  }) => post<OdConversion>("/api/concentration/od", body),

  /* -------------------------------------------- Phase 5: Entwurf */

  melting: (sequence: string, conditions?: Record<string, number>) =>
    post<TmView>("/api/melting", { sequence, conditions }),

  scan: (body: {
    sequence: string;
    start?: number;
    end?: number;
    include_poor?: boolean;
    with_structure?: boolean;
    probe_length?: number;
  }) =>
    post<{
      scan: ScanView;
      folding: TargetFoldView | null;
      accessibility: import("./types").AccessibilityView | null;
    }>("/api/scan", body),

  design: (body: DesignBody) => post<DesignView>("/api/design", body),

  /** Dieselbe Anfrage, aber als CSV-Text (PHASEN.md 5.6). */
  designCsv: async (body: DesignBody): Promise<string> => {
    const response = await fetch("/api/design/candidates.csv", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      throw new ApiError(response.status, null, "Der CSV-Export ist fehlgeschlagen.");
    }
    return response.text();
  },

  modify: (body: {
    sequence: string;
    pattern: string;
    core_start?: number | null;
    core_end?: number | null;
    count?: number;
    position?: number | null;
    code?: string | null;
    allow_core?: boolean;
    arm5_length?: number;
    core_length?: number;
    conditions?: Record<string, number>;
  }) => post<ModifyResultView>("/api/modify", body),

  compare: (body: {
    before: string;
    after: string;
    arm5_length?: number;
    core_length?: number;
    conditions?: Record<string, number>;
  }) => post<{ before: SnapshotView; after: SnapshotView }>("/api/compare", body),

  patterns: () =>
    request<{ patterns: { id: string; label: string }[]; disclaimer: string }>(
      "/api/design/patterns",
    ),

  monomers: () => request<MonomerCatalog>("/api/monomers"),

  saveMonomer: (body: Record<string, unknown>) =>
    post<{ saved: string; file: string }>("/api/monomers", body),

  dropMonomerOverride: (code: string) =>
    request<{ removed: string }>(`/api/monomers/${encodeURIComponent(code)}`, {
      method: "DELETE",
    }),

  modifications: () =>
    request<{ modifications: ModificationSpecView[] }>("/api/modifications"),

  libraryOligos: (query?: string) =>
    request<{ total: number; oligos: LibraryOligo[] }>(
      `/api/library/oligos${query ? `?q=${encodeURIComponent(query)}` : ""}`,
    ),

  saveOligo: (body: { name: string; sequence: string; notes?: string }) =>
    post<{ id: number; name: string }>("/api/library/oligos", body),

  deleteOligo: (id: number) =>
    request<{ deleted: number }>(`/api/library/oligos/${id}`, {
      method: "DELETE",
    }),

  samples: () => request<{ samples: LibrarySample[] }>("/api/library/samples"),

  saveSample: (body: {
    name: string;
    n_stock_nmol: number;
    v_stock_ul: number;
  }) => post<{ id: number; name: string }>("/api/library/samples", body),

  deleteSample: (id: number) =>
    request<{ deleted: number }>(`/api/library/samples/${id}`, {
      method: "DELETE",
    }),

  help: () => request<{ entries: Record<string, HelpEntry> }>("/api/help"),
};
