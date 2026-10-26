/* Typen zu den Antworten aus `app/main.py`. */

/** CLAUDE.md, Regel 3 — die drei Kennzeichen. */
export type Reliability =
  | "exakt"
  | "Parameter vorhanden"
  | "genähert über natürliches Analogon"
  | "nicht hinterlegt";

/** Jede Zahl traegt Einheit, Kennzeichen und Methode mit. */
export interface Quantity {
  value: number | null;
  unit: string;
  reliability: Reliability;
  method: string;
  note: string | null;
}

/** Farbklasse eines Bausteins — in allen Ansichten dieselbe. */
export type MonomerKlasse =
  | "dna"
  | "rna"
  | "zucker"
  | "base"
  | "konjugat"
  | "custom";

export interface MonomerView {
  position: number;
  code: string;
  source: string;
  name: string;
  typ: string;
  klasse: MonomerKlasse;
  base_parent: string | null;
  core_tested: "ja" | "nein" | "unbekannt";
  modifications: { code: string; name: string; klasse: string }[];
  mass_residue: Quantity;
  span: { start: number; end: number };
  deviates_from_excel: boolean;
}

export interface LinkageView {
  position: number;
  kind: "phosphate" | "phosphorothioate" | "methylphosphonate";
  modification: string | null;
}

export interface ConjugateView {
  code: string;
  name: string;
  attach: "5prime" | "3prime" | "internal";
  after_position: number | null;
  needs_review: boolean;
}

export interface OligoView {
  length: number;
  monomers: MonomerView[];
  linkages: LinkageView[];
  conjugates: ConjugateView[];
  code_counts: Record<string, number>;
  base_counts: Record<string, number>;
  phosphorothioates: number;
  modified_positions: number[];
}

export interface NotationProblem {
  position: number;
  text: string;
  message: string;
  hint: string | null;
  start: number;
  end: number;
}

export interface MassEntry extends Quantity {
  key: string;
  label: string;
}

export interface MassResult {
  masses: MassEntry[];
  breakdown: {
    residues: number;
    monomer_modifications: number;
    linkage_modifications: number;
    conjugates: number;
    basis: number;
    length: number;
    n_A: number;
    n_C: number;
    n_G: number;
    protecting_base: number;
    protecting_cyanoethyl: number;
    missing: string[];
    approximated: string[];
  };
}

export interface ExactResult {
  formula: string | null;
  monoisotopic: Quantity;
  average: Quantity;
  monoisotopic_na: Quantity;
  average_na: Quantity;
  sodium_count: number;
  isotopes: { mass: number; intensity_rel: number }[];
  missing_formula: string[];
}

export interface ComparisonRow {
  code: string;
  count: number;
  excel: number | null;
  formula: string | null;
  average: number | null;
  monoisotopic: number | null;
  delta: number | null;
  delta_total: number | null;
  delta_mono: number | null;
}

export interface Comparison {
  excel: number | null;
  exact: number | null;
  difference: number | null;
  agrees: boolean;
  threshold: number;
  message: string;
  per_code: ComparisonRow[];
  missing_formula: string[];
}

export interface ExtinctionResult {
  eps260: Quantity;
  table: string;
  per_position: { position: number; pair: string; eps260: number }[];
  approximated: string[];
  missing: string[];
}

export interface ConsumptionRow {
  code: string;
  name: string;
  couplings: number;
  volume_ml: number;
  conc_molar: number | null;
  mass_mg: number | null;
  mass_with_reserve_mg: number | null;
  reliability: Reliability;
  note: string | null;
}

export interface ConsumptionTable {
  rows: ConsumptionRow[];
  total: {
    volume_ml: number;
    mass_mg: number | null;
    mass_with_reserve_mg: number | null;
  };
  settings: {
    coupling_volume_ml: number;
    reserve_fraction: number;
    syntheses: number;
  };
  hint: string;
}

export interface Profile {
  oligo: OligoView;
  problems: NotationProblem[];
  grouped: string;
  mass: MassResult | null;
  exact: ExactResult | null;
  comparison: Comparison | null;
  extinction: ExtinctionResult | null;
  synthesis: ConsumptionTable | null;
  charge_ladder?: { charge: number; mz: number }[];
}

export interface LoadingRecipe {
  kind: string;
  oligo_ul: Quantity;
  water_ul: Quantity;
  buffer_ul: Quantity | null;
  total_ul: number;
  stock_conc_um: Quantity;
  rest_in_vial_ul: number | null;
  warnings: string[];
}

export interface OdConversion {
  od: Quantity;
  nmol: Quantity;
  microgram: Quantity;
  solved_for: string;
  warning: string | null;
}

export interface MonomerSpecView {
  code: string;
  name: string;
  typ: string;
  mass_residue: number | null;
  mass_amidite: number | null;
  conc_molar: number | null;
  formula_residue: string | null;
  eps260: number | null;
  base_parent: string | null;
  core_tested: "ja" | "nein" | "unbekannt";
  smiles: string | null;
  quelle: string | null;
  deviates_from_excel: boolean;
  is_override: boolean;
}

export interface ModificationSpecView {
  code: string;
  name: string;
  mass_diff: number | null;
  scope: "monomer" | "linkage" | "terminus";
  klasse: string;
  formula: string | null;
  eps260: number | null;
  base_parent: string | null;
  counts_as_base: boolean;
  core_tested: string;
  needs_review: boolean;
  note: string | null;
  quelle: string | null;
}

export interface MonomerCatalog {
  monomers: MonomerSpecView[];
  protecting_groups: Record<
    string,
    { code: string; name: string; mass: number; typ?: string; note?: string }
  >;
  protecting_group_by_base: Record<string, string | null>;
  termini: Record<string, { name?: string; mass: number; note?: string }>;
}

export interface LibraryOligo {
  id: number;
  name: string;
  sequence: string;
  notes: string | null;
  length: number;
  mass_fully_deprotected: number | null;
  created_at: string;
  updated_at: string;
}

export interface LibrarySample {
  id: number;
  name: string;
  n_stock_nmol: number;
  v_stock_ul: number;
  notes: string | null;
  created_at: string;
}

export interface HelpEntry {
  title?: string;
  short: string;
  long?: string;
}
