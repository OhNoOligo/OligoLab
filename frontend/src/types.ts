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

/* ----------------------------------------------------- Seite "Strang" */

export type Severity = "kritisch" | "warnung" | "hinweis";

export interface CoreSpecView {
  id: string;
  name: string;
  sequence: string;
  length: number;
  target_type: string;
  preferred_junctions: string[];
  metal_requirement: string | null;
  arm_length_default: number;
  quelle: string | null;
  note: string | null;
}

export interface PartView {
  kind: "arm5" | "core" | "arm3";
  label: string;
  start: number;
  end: number;
  length: number;
}

export interface PartsView {
  found: boolean;
  core: CoreSpecView | null;
  parts: PartView[];
  approximated: string[];
  note: string | null;
}

export interface HairpinView {
  start: number;
  end: number;
  loop_start: number;
  loop_end: number;
  stem_length: number;
  energy: number | null;
}

export interface FoldingView {
  available: boolean;
  sequence_used: string;
  structure: string;
  mfe: Quantity | null;
  ensemble_energy: Quantity | null;
  pair_probabilities: { i: number; j: number; p: number }[];
  unpaired: number[];
  hairpins: HairpinView[];
  homodimer_structure: string | null;
  homodimer_energy: Quantity | null;
  reliability: Reliability;
  approximated: string[];
  note: string | null;
}

export interface FindingView {
  code: string;
  severity: Severity;
  severity_label: string;
  start: number;
  end: number;
  title: string;
  message: string;
  detail: string | null;
  /** "strand" heißt: gilt dem Strang als Ganzem, nicht einzelnen Stellen. */
  scope: "position" | "region" | "strand";
}

export interface CriticalView {
  findings: FindingView[];
  worst: Severity | null;
  counts: Record<Severity, number>;
  checked: string[];
  skipped: string[];
  thresholds: {
    hairpin_kcal: number;
    homodimer_kcal: number;
    min_arm_length: number;
    arm_imbalance: number;
    homopolymer_run: number;
  };
}

export interface StrandView {
  oligo: OligoView;
  problems: NotationProblem[];
  parts: PartsView | null;
  folding: FoldingView | null;
  critical: CriticalView | null;
}

/* ------------------------------------------------------- Seite "Ziel" */

export type RegionKind = "5utr" | "cds" | "3utr" | "other";

export interface RegionView {
  kind: RegionKind;
  label: string;
  start: number;
  end: number;
  length: number;
}

export interface TargetView {
  name: string;
  sequence: string;
  length: number;
  source: string;
  identifier: string | null;
  fetched_at: string | null;
  regions: RegionView[];
  organism: string | null;
  description: string | null;
  note: string | null;
}

export interface FetchChoice {
  id: string;
  name: string;
  biotype: string | null;
  length: number;
  canonical: boolean;
  longest: boolean;
}

export interface FetchResultView {
  available: boolean;
  target: TargetView | null;
  choices: FetchChoice[];
  from_cache: boolean;
  message: string | null;
}

export interface TargetFoldView {
  available: boolean;
  start: number;
  end: number;
  length: number;
  structure: string | null;
  mfe: Quantity | null;
  ensemble_energy: Quantity | null;
  note: string | null;
}

export interface AccessibilityView {
  available: boolean;
  start: number;
  end: number;
  probe_length: number;
  window: number;
  max_span: number;
  /** Je Position: Wahrscheinlichkeit, dass ab hier L Nukleotide offen sind. */
  profile: (number | null)[];
  unpaired: number[];
  chunks: number;
  seconds: number;
  method: string;
  note: string | null;
}

export interface UpView {
  available: boolean;
  site_start: number;
  site_end: number;
  opening_target: Quantity | null;
  opening_oligo: Quantity | null;
  hybridisation: Quantity | null;
  total: Quantity | null;
  duplex_structure: string | null;
  note: string | null;
}

export interface LibraryTarget {
  id: number;
  name: string;
  sequence: string;
  length: number;
  source: string;
  identifier: string | null;
  organism: string | null;
  description: string | null;
  regions: RegionView[];
  fetched_at: string | null;
  updated_at: string;
}

/* ------------------------------------------------- Phase 5: Entwurf */

export interface TmView {
  available: boolean;
  tm: Quantity | null;
  dg: Quantity | null;
  dh: Quantity | null;
  ds: Quantity | null;
  source: string;
  parameter_set: string;
  sequence_used: string;
  hybridisation_type: string;
  second_opinion_c: number | null;
  divergence_c: number | null;
  reliability: string;
  warnings: string[];
  approximated: string[];
  note: string | null;
}

export interface CleavageSiteView {
  position: number;
  junction: string;
  quality: "gut" | "mäßig" | "schlecht";
  purine_unpaired: number | null;
  pyrimidine_paired: number | null;
  accessibility: number | null;
  matches_pattern: boolean | null;
}

export interface ScanView {
  sites: CleavageSiteView[];
  hidden_poor: number;
  counts: Record<string, number>;
  start: number;
  end: number;
  note: string | null;
}

export interface CriterionView {
  key: string;
  label: string;
  raw: number | null;
  score: number | null;
  weight: number;
  note: string | null;
}

export interface CandidateView {
  site: CleavageSiteView;
  sequence: string;
  arm5: string;
  arm3: string;
  core: string;
  core_id: string;
  target_upstream: string;
  target_downstream: string;
  length: number;
  tm5: TmView | null;
  tm3: TmView | null;
  arm_dg_sum: number | null;
  imbalance: number | null;
  self_fold_mfe: number | null;
  self_fold_structure: string | null;
  criteria: CriterionView[];
  score: number;
  rating: "good" | "warn" | "bad";
  binds: boolean;
  excluded: boolean;
  exclusion_reason: string | null;
  warnings: string[];
}

export interface DesignSettingsView {
  arm5_length: number;
  arm3_length: number;
  core_id: string | null;
  arm_dg_target: number;
  max_imbalance: number;
  self_fold_limit: number;
  weights: Record<string, number>;
  include_poor_junctions: boolean;
}

export interface DesignView {
  candidates: CandidateView[];
  settings: DesignSettingsView;
  core: CoreSpecView | null;
  skipped_edges: number;
  scan_note: string | null;
  disclaimer: string;
  scan: ScanView;
  accessibility: AccessibilityView | null;
  conditions: Record<string, number>;
}

export interface SnapshotView {
  sequence: string;
  length: number;
  mass: number | null;
  tm5: number | null;
  tm3: number | null;
  arm_dg_sum: number | null;
  imbalance: number | null;
  self_fold_mfe: number | null;
  score: number | null;
  rating: string | null;
  /** Wo der Tm nur über ein natürliches Analogon gerechnet wurde. */
  tm_approximated: string[];
}

export interface ModificationView {
  sequence: string;
  changes: {
    kind: string;
    position: number | null;
    description: string;
    in_core: boolean;
  }[];
  touched_core: boolean;
  blocked: boolean;
  message: string | null;
}

export interface ModifyResultView {
  modification: ModificationView;
  before?: SnapshotView;
  after?: SnapshotView;
}

/* ------------------------------------------- Phase 6: Geometrie und 3D */

export interface ReferenceSpecView {
  id: string;
  title: string;
  role: string;
  note: string | null;
  cached: boolean;
}

export interface ChainView {
  id: string;
  kind: "dna" | "rna" | "protein" | "ion" | "wasser" | "anderes";
  length: number;
  sequence: string;
  first: number | null;
  last: number | null;
  role: string | null;
}

export interface StructureView {
  id: string;
  path: string | null;
  format: string;
  title: string | null;
  method: string | null;
  resolution_a: number | null;
  citation: string | null;
  chains: ChainView[];
  ions: {
    residue: string;
    chain: string;
    number: number;
    element: string;
    xyz: number[];
  }[];
  available: boolean;
  source: string;
  note: string | null;
}

export type Provenance =
  | "uebernommen"
  | "geruest"
  | "nur_zucker"
  | "gebaut"
  | "ideal";

export interface ModelPositionView {
  position: number;
  code: string;
  base: string;
  residue_number: number;
  chain: string;
  provenance: Provenance;
  provenance_label: string;
  reliability: string;
  modification: string | null;
  klasse: string;
  note: string | null;
}

export interface ModelView {
  available: boolean;
  pdb: string;
  reference_id: string | null;
  positions: ModelPositionView[];
  substrate: ModelPositionView[];
  chain_dnazyme: string;
  chain_substrate: string;
  cleavage_residue: number | null;
  counts: Record<string, number>;
  disclaimer: string;
  warnings: string[];
  note: string | null;
}

export interface InlineAngleView {
  available: boolean;
  angle: Quantity | null;
  distance_attack: Quantity | null;
  distance_leaving: Quantity | null;
  atoms: string[];
  assessment: string | null;
  rating: "good" | "warn" | "bad" | null;
  note: string | null;
}

export interface PositionDistanceView {
  position: number;
  code: string;
  modification: string | null;
  nucleotides: number | null;
  angstrom: number | null;
  note: string | null;
}

export interface GeometryView {
  available: boolean;
  inline: InlineAngleView;
  to_cleavage: PositionDistanceView[];
  to_core: PositionDistanceView[];
  ion_contacts: Record<
    string,
    { residue: string; element: string; chain: string; number: number; angstrom: number }[]
  >;
  warnings: string[];
  note: string | null;
}

export interface MeasurementView {
  kind: string;
  atoms: string[];
  value: number | null;
  unit: string;
  note: string | null;
}

export interface FragmentView {
  atom_count: number;
  added_hydrogens: number;
  residues: string[];
  charge: number;
  multiplicity: number;
  sensible: boolean;
  size_hint: string;
  note: string | null;
}

export interface OrcaView {
  fragment: FragmentView;
  input: string;
  purpose: { label: string; keywords: string; note: string };
}
