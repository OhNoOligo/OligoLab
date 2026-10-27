/* Die Paarungsdarstellung (PHASEN.md 5.6).
 *
 * „Ziel-RNA oben, DNAzym darunter, Basenpaare als senkrechte Striche, der
 * Kern als Schleife, die Spaltstelle mit einem Pfeil, Modifikationen in
 * ihren Farben."
 *
 * Die Geometrie folgt dem, was wirklich passiert: ein DNAzym ist
 * `revcomp(stromab) + Kern + revcomp(stromauf)`. Der 5'-Arm bindet also
 * STROMAB der Spaltstelle, der 3'-Arm STROMAUF. Zeichnet man das Ziel von
 * links nach rechts in 5'→3', dann läuft der Strang darunter
 * gegenläufig — links sein 3'-Ende, rechts sein 5'-Ende. Genau so stehen
 * die Endbeschriftungen hier, und deshalb liegt der Kern als Schleife
 * mitten über der Schnittstelle: im Strang steht er zwischen den Armen,
 * im Bild zwischen stromauf und stromab.
 *
 * Gezeichnet wird aus den Monomer-Objekten, nicht aus dem Sequenztext —
 * sonst hätte `[LNA-T]` sieben Zellen (CLAUDE.md, Regel 1).
 */

import { useMemo, useRef } from "react";
import type {
  CandidateView,
  ConjugateView,
  LinkageView,
  MonomerView,
} from "../types";
import { KLASSE_COLOR } from "./SequenceEditor";
import { exportSvg, safeFilename } from "../lib/svgExport";

const CELL = 15;
const GUTTER = 34;
const PAD_RIGHT = 34;

const Y_RULER = 12;
const Y_TARGET = 32;
const Y_PAIR_TOP = 40;
const Y_PAIR_BOTTOM = 58;
const Y_STRAND = 72;
const LOOP_CENTER_DY = 34;

/** Watson-Crick-Paare zwischen DNAzym (DNA) und Ziel (RNA). */
const COMPLEMENT: Record<string, string> = {
  A: "U",
  T: "A",
  G: "C",
  C: "G",
};

type Bond = "wc" | "wobble" | "none";

function bond(strand: string, target: string): Bond {
  const s = strand.toUpperCase();
  const t = target.toUpperCase() === "T" ? "U" : target.toUpperCase();
  if (COMPLEMENT[s] === t) return "wc";
  // G·U ist ein echtes, nur schwächeres Paar — und darf nicht als
  // Fehlpaarung durchgehen.
  if ((s === "G" && t === "U") || (s === "T" && t === "G")) return "wobble";
  return "none";
}

/** Welcher Buchstabe steht in der Zelle: das natürliche Analogon. */
function letterOf(monomer: MonomerView): string {
  if (monomer.code.length === 1) return monomer.code;
  return (monomer.base_parent ?? monomer.code.slice(0, 1)).toUpperCase();
}

interface Placed {
  monomer: MonomerView;
  x: number;
  y: number;
  /** Nur die Arme haben einen Gegenüber im Ziel. */
  targetIndex: number | null;
}

export function PairingMap({
  candidate,
  monomers,
  linkages,
  conjugates,
  name,
}: {
  candidate: CandidateView;
  /** Aus `/api/strand` — ohne sie wird in Grau gezeichnet. */
  monomers?: MonomerView[];
  linkages?: LinkageView[];
  conjugates?: ConjugateView[];
  name?: string;
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);

  const layout = useMemo(() => {
    const upstream = candidate.target_upstream;
    const downstream = candidate.target_downstream;
    const n5 = candidate.arm5.length;
    const n3 = candidate.arm3.length;
    const nc = candidate.core.length;
    const target = upstream + downstream;
    const cut = upstream.length; // Zellen links der Schnittstelle

    const x = (index: number) => GUTTER + index * CELL + CELL / 2;

    /* Ersatzmonomere, solange `/api/strand` noch nicht geantwortet hat.
     *
     * Die Buchstaben kommen aus Arm, Kern und Arm — NICHT aus dem
     * Sequenztext: der hat bei `[LNA-T]` sieben Zeichen statt einem, und
     * das Bild bekäme Klammern in die Zellen (CLAUDE.md, Regel 1). */
    const list: MonomerView[] =
      monomers && monomers.length === n5 + nc + n3
        ? monomers
        : ((candidate.arm5 + candidate.core + candidate.arm3)
            .split("")
            .map((code, index) => ({
              position: index + 1,
              code,
              source: code,
              name: code,
              typ: "dna",
              klasse: "dna",
              base_parent: code,
              core_tested: "unbekannt",
              modifications: [],
              mass_residue: {
                value: 0,
                unit: "g/mol",
                reliability: "exakt",
                method: "",
              },
              span: { start: index + 1, end: index + 1 },
              deviates_from_excel: false,
            })) as unknown as MonomerView[]);

    const arms: Placed[] = [];
    const core: { monomer: MonomerView; x: number; y: number }[] = [];

    /* Jeder Zugriff auf die Liste wird abgesichert. Stimmen Sequenz und
     * Monomerliste einmal nicht überein, soll das Bild eine Zelle weniger
     * haben — und nicht die ganze Seite abstürzen. */
    const at = (index: number): MonomerView | null => list[index] ?? null;

    // 5'-Arm: Monomer k paart stromab[n5 - k] (0-basiert).
    for (let k = 1; k <= n5; k += 1) {
      const targetIndex = cut + (n5 - k);
      const monomer = at(k - 1);
      if (!monomer) continue;
      arms.push({ monomer, x: x(targetIndex), y: Y_STRAND, targetIndex });
    }
    // 3'-Arm: Monomer k paart stromauf[n3 - k].
    for (let k = 1; k <= n3; k += 1) {
      const targetIndex = n3 - k;
      const monomer = at(n5 + nc + k - 1);
      if (!monomer) continue;
      arms.push({ monomer, x: x(targetIndex), y: Y_STRAND, targetIndex });
    }

    // Der Kern als Schleife über der Schnittstelle. Die Position 1 des Kerns
    // sitzt rechts (dort schließt der 5'-Arm an), die letzte links.
    const cx = GUTTER + cut * CELL;
    const radius = Math.max(30, (nc * CELL) / (2 * Math.PI) + 10);
    const cy = Y_STRAND + LOOP_CENTER_DY + radius / 3;
    const FROM = -62;
    const SWEEP = 304;
    const angleOf = (index: number) =>
      FROM + (nc <= 1 ? SWEEP / 2 : (index * SWEEP) / (nc - 1));
    for (let j = 0; j < nc; j += 1) {
      const rad = (angleOf(j) * Math.PI) / 180;
      const monomer = at(n5 + j);
      if (!monomer) continue;
      core.push({
        monomer,
        x: cx + radius * Math.cos(rad),
        y: cy + radius * Math.sin(rad),
      });
    }

    const height = cy + radius + 26;
    const width = GUTTER + target.length * CELL + PAD_RIGHT;

    return {
      target,
      upstream,
      downstream,
      cut,
      x,
      arms,
      core,
      loop: { cx, cy, radius, from: angleOf(0), to: angleOf(nc - 1) },
      width,
      height,
      n5,
      n3,
      nc,
    };
  }, [candidate, monomers]);

  const { target, cut, x } = layout;
  const cutX = GUTTER + cut * CELL;
  const firstPosition = candidate.site.position - layout.n3 + 1;

  // Thioate sitzen IN der Lücke zwischen zwei Zellen, nicht auf einer Zelle.
  const thioates = useMemo(() => {
    const result: { x: number; y: number }[] = [];
    if (!linkages) return result;
    const byPosition = new Map(layout.arms.map((p) => [p.monomer.position, p]));
    for (const linkage of linkages) {
      if (linkage.kind !== "phosphorothioate") continue;
      const left = byPosition.get(linkage.position);
      const right = byPosition.get(linkage.position + 1);
      if (!left || !right) continue; // eine Bindung am oder im Kern
      result.push({ x: (left.x + right.x) / 2, y: Y_STRAND });
    }
    return result;
  }, [linkages, layout]);

  const mismatches = layout.arms.filter(
    (placed) =>
      placed.targetIndex !== null &&
      bond(letterOf(placed.monomer), target[placed.targetIndex] ?? "") === "none",
  );

  return (
    <figure className="m-0">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <figcaption className="text-xs" style={{ color: "var(--text-faint)" }}>
          Ziel-RNA oben in 5'→3'. Das DNAzym darunter läuft gegenläufig — links
          sein 3'-Ende. Der Kern bindet nicht und steht als Schleife über der
          Schnittstelle.
        </figcaption>
        <button
          type="button"
          className="ol-button text-xs"
          onClick={() => {
            if (svgRef.current) {
              exportSvg(
                svgRef.current,
                safeFilename(
                  name ?? `paarung-${candidate.site.position}`,
                  "svg",
                ),
              );
            }
          }}
        >
          SVG
        </button>
      </div>

      <div className="overflow-x-auto">
        <svg
          ref={svgRef}
          width={layout.width}
          height={layout.height}
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          role="img"
          aria-label={`Paarung des Kandidaten an Position ${candidate.site.position}`}
          style={{ fontFamily: "var(--font-mono)" }}
        >
          <defs>
            <marker
              id="cut-arrow"
              viewBox="0 0 10 10"
              refX="5"
              refY="9"
              markerWidth="5"
              markerHeight="5"
              orient="0"
            >
              <path d="M 0 0 L 10 0 L 5 10 z" fill="var(--rating-bad)" />
            </marker>
          </defs>

          {/* Lineal: die echten Positionen im Ziel */}
          {target.split("").map((_, index) => {
            const position = firstPosition + index;
            if (position % 10 !== 0) return null;
            // Dort, wo die Beschriftung der Spaltstelle steht, bleibt das
            // Lineal still — sonst stehen zwei Zahlen uebereinander.
            if (Math.abs(index - cut) <= 3) return null;
            return (
              <text
                key={`r${index}`}
                x={x(index)}
                y={Y_RULER}
                textAnchor="middle"
                fontSize="9"
                fill="var(--text-faint)"
              >
                {position}
              </text>
            );
          })}

          {/* Ziel-RNA */}
          <text
            x={GUTTER - 8}
            y={Y_TARGET}
            textAnchor="end"
            fontSize="10"
            fill="var(--text-faint)"
          >
            5′
          </text>
          <text
            x={GUTTER + target.length * CELL + 6}
            y={Y_TARGET}
            fontSize="10"
            fill="var(--text-faint)"
          >
            3′
          </text>
          {target.split("").map((base, index) => (
            <text
              key={`t${index}`}
              x={x(index)}
              y={Y_TARGET}
              textAnchor="middle"
              fontSize="12"
              fill="var(--mod-rna)"
            >
              {base}
            </text>
          ))}

          {/* Basenpaare als senkrechte Striche */}
          {layout.arms.map((placed) => {
            if (placed.targetIndex === null) return null;
            const art = bond(
              letterOf(placed.monomer),
              target[placed.targetIndex] ?? "",
            );
            if (art === "none") {
              return (
                <circle
                  key={`m${placed.monomer.position}`}
                  cx={placed.x}
                  cy={(Y_PAIR_TOP + Y_PAIR_BOTTOM) / 2}
                  r="2.5"
                  fill="none"
                  stroke="var(--rating-bad)"
                  strokeWidth="1"
                />
              );
            }
            return (
              <line
                key={`p${placed.monomer.position}`}
                x1={placed.x}
                y1={Y_PAIR_TOP}
                x2={placed.x}
                y2={Y_PAIR_BOTTOM}
                stroke="var(--border)"
                strokeWidth={art === "wc" ? 1.2 : 1}
                strokeDasharray={art === "wobble" ? "2 2" : undefined}
              />
            );
          })}

          {/* Das DNAzym: Arme in Zellen, Modifikationen in ihren Farben */}
          <text
            x={GUTTER - 8}
            y={Y_STRAND + 4}
            textAnchor="end"
            fontSize="10"
            fill="var(--text-faint)"
          >
            3′
          </text>
          <text
            x={GUTTER + target.length * CELL + 6}
            y={Y_STRAND + 4}
            fontSize="10"
            fill="var(--text-faint)"
          >
            5′
          </text>
          {layout.arms.map((placed) => (
            <text
              key={`a${placed.monomer.position}`}
              x={placed.x}
              y={placed.y + 4}
              textAnchor="middle"
              fontSize="12"
              fill={KLASSE_COLOR[placed.monomer.klasse] ?? "var(--mod-dna)"}
            >
              {letterOf(placed.monomer)}
            </text>
          ))}

          {/* Phosphorothioat: ein Punkt in der Lücke */}
          {thioates.map((mark, index) => (
            <circle
              key={`s${index}`}
              cx={mark.x}
              cy={mark.y + 1}
              r="2"
              fill="var(--text-faint)"
            >
              <title>Phosphorothioat</title>
            </circle>
          ))}

          {/* Der Kern als Schleife */}
          <path
            d={describeLoop(layout.loop)}
            fill="none"
            stroke="var(--border)"
            strokeWidth="1"
          />
          {layout.core.map((entry) => (
            <text
              key={`c${entry.monomer.position}`}
              x={entry.x}
              y={entry.y + 4}
              textAnchor="middle"
              fontSize="11"
              fill={KLASSE_COLOR[entry.monomer.klasse] ?? "var(--mod-dna)"}
            >
              {letterOf(entry.monomer)}
            </text>
          ))}
          <text
            x={layout.loop.cx}
            y={layout.loop.cy + 4}
            textAnchor="middle"
            fontSize="10"
            fill="var(--text-faint)"
          >
            Kern
          </text>

          {/* Die Spaltstelle */}
          <line
            x1={cutX}
            y1={Y_RULER + 4}
            x2={cutX}
            y2={Y_TARGET - 14}
            stroke="var(--rating-bad)"
            strokeWidth="1.4"
            markerEnd="url(#cut-arrow)"
          />
          <text
            x={cutX + 4}
            y={Y_RULER + 2}
            fontSize="9"
            fill="var(--rating-bad)"
          >
            {candidate.site.junction} · {candidate.site.position}/
            {candidate.site.position + 1}
          </text>
        </svg>
      </div>

      {conjugates && conjugates.length > 0 && (
        <p className="mt-2 text-xs" style={{ color: "var(--mod-konjugat)" }}>
          {conjugates
            .map(
              (c) =>
                `${c.name} am ${c.attach === "5prime" ? "5'" : c.attach === "3prime" ? "3'" : "internen"}-Ende`,
            )
            .join(" · ")}
        </p>
      )}
      {mismatches.length > 0 && (
        <p className="mt-2 text-xs" style={{ color: "var(--rating-bad)" }}>
          {mismatches.length} Fehlpaarung(en) — als offener Kreis statt als
          Strich gezeichnet.
        </p>
      )}
    </figure>
  );
}

/** Der Kreisbogen der Schleife, mit der Lücke dort, wo die Arme anschließen. */
function describeLoop({
  cx,
  cy,
  radius,
  from,
  to,
}: {
  cx: number;
  cy: number;
  radius: number;
  from: number;
  to: number;
}): string {
  const point = (grad: number) => {
    const rad = (grad * Math.PI) / 180;
    return `${(cx + radius * Math.cos(rad)).toFixed(2)} ${(
      cy +
      radius * Math.sin(rad)
    ).toFixed(2)}`;
  };
  // Von der rechten Anschlussstelle im Uhrzeigersinn herum zur linken.
  return `M ${point(from)} A ${radius} ${radius} 0 1 1 ${point(to)}`;
}
