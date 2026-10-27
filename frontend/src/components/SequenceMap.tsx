/* Die Sequenzkarte (PHASEN.md 3.4).
 *
 * Als SVG, nicht als HTML-Tabelle: Bögen und Balken lassen sich in einer
 * Tabelle nicht zeichnen, und ein SVG lässt sich zudem als Bild ausgeben.
 *
 * Sechs Spuren von oben nach unten, in dieser Reihenfolge:
 *
 *   1  Positionslineal, Nummerierung alle fünf Basen, 5' links, 3' rechts
 *   2  Basenspur, eine Zelle je Position, Einfärbung nach der Farbtabelle;
 *      Phosphorothioat als Symbol IN DER LÜCKE zwischen zwei Zellen, denn
 *      dort sitzt es auch chemisch — an der Bindung, nicht am Baustein
 *   3  Bauteilspur: durchgehende Balken für 5'-Arm, Kern und 3'-Arm
 *   4  Bogendiagramm der Faltung, Strichstärke nach Paarungswahrscheinlichkeit
 *   5  Balkenspur: Wahrscheinlichkeit, ungepaart zu sein
 *   6  Warnspur: farbige Marker an den Positionen der Befunde
 *
 * Die Breite einer Zelle ist der Zoom. Alle Spuren teilen sie sich, darum
 * stehen sie exakt übereinander — und zwei Karten nebeneinander lassen sich
 * Position für Position vergleichen.
 */

import { useMemo } from "react";
import type {
  CriticalView,
  FindingView,
  FoldingView,
  MonomerKlasse,
  OligoView,
  PartsView,
  Severity,
} from "../types";
import { KLASSE_COLOR, KLASSE_LABEL } from "./SequenceEditor";

/* ------------------------------------------------------------------ Masse */

const GUTTER = 92; // Platz links für die Spurbeschriftung
const PAD_RIGHT = 16;

const TRACK = {
  ruler: 20,
  bases: 26,
  parts: 20,
  arcs: 64,
  unpaired: 34,
  warnings: 16,
} as const;

const GAP = 6;

export const MIN_CELL = 8;
export const MAX_CELL = 30;
export const DEFAULT_CELL = 15;

/* Die Ampel — hier erlaubt, denn ein Befund IST eine Bewertung. */
const SEVERITY_COLOR: Record<Severity, string> = {
  kritisch: "var(--rating-bad)",
  warnung: "var(--rating-warn)",
  // Ein Hinweis ist nicht "gut"; grün wäre irreführend. Darum die
  // Einstellungsfarbe statt der dritten Ampelfarbe.
  hinweis: "var(--role-settings)",
};

const PART_COLOR: Record<string, string> = {
  arm5: "var(--role-settings)",
  core: "var(--mod-conjugate)",
  arm3: "var(--role-settings)",
};

export interface MapSelection {
  start: number;
  end: number;
}

export interface SequenceMapProps {
  oligo: OligoView;
  parts: PartsView | null;
  folding: FoldingView | null;
  critical: CriticalView | null;
  cell?: number;
  /** Hervorgehobener Bereich, etwa aus der Befundliste angeklickt. */
  highlight?: MapSelection | null;
  onPickFinding?: (finding: FindingView) => void;
  /** Für den Export: wird auf das <svg> gelegt. */
  svgId?: string;
  title?: string;
}

function trackTops() {
  let y = 0;
  const tops: Record<keyof typeof TRACK, number> = {} as never;
  for (const key of Object.keys(TRACK) as (keyof typeof TRACK)[]) {
    tops[key] = y;
    y += TRACK[key] + GAP;
  }
  return { tops, height: y - GAP };
}

export function SequenceMap({
  oligo,
  parts,
  folding,
  critical,
  cell = DEFAULT_CELL,
  highlight = null,
  onPickFinding,
  svgId,
  title,
}: SequenceMapProps) {
  const length = oligo.length;
  const { tops, height } = useMemo(trackTops, []);
  const width = GUTTER + length * cell + PAD_RIGHT;

  const x = (position: number) => GUTTER + (position - 1) * cell;
  const center = (position: number) => x(position) + cell / 2;

  const thioated = useMemo(
    () =>
      new Set(
        oligo.linkages
          .filter((l) => l.kind === "phosphorothioate")
          .map((l) => l.position),
      ),
    [oligo.linkages],
  );

  const findingsByPosition = useMemo(() => {
    const out = new Map<number, FindingView[]>();
    for (const finding of critical?.findings ?? []) {
      // Ein Befund über den ganzen Strang — etwa der Selbstdimer — würde
      // jede Position einfärben und die Spur unbrauchbar machen.
      if (finding.start === 1 && finding.end === length && length > 3) continue;
      for (let p = finding.start; p <= finding.end; p += 1) {
        const list = out.get(p) ?? [];
        list.push(finding);
        out.set(p, list);
      }
    }
    return out;
  }, [critical, length]);

  const pairs = useMemo(() => {
    const out = new Map<number, number>();
    for (const [index, char] of [...(folding?.structure ?? "")].entries()) {
      if (char !== "(") continue;
      let depth = 1;
      for (let k = index + 1; k < (folding?.structure.length ?? 0); k += 1) {
        const c = folding!.structure[k];
        if (c === "(") depth += 1;
        else if (c === ")") {
          depth -= 1;
          if (depth === 0) {
            out.set(index + 1, k + 1);
            out.set(k + 1, index + 1);
            break;
          }
        }
      }
    }
    return out;
  }, [folding]);

  const label = (text: string, y: number) => (
    <text
      x={GUTTER - 8}
      y={y}
      textAnchor="end"
      fontSize={9}
      fill="var(--text-faint)"
      dominantBaseline="middle"
    >
      {text}
    </text>
  );

  const fontSize = Math.min(13, Math.max(7, cell - 3));

  return (
    <svg
      id={svgId}
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      role="img"
      aria-label={
        title ??
        `Sequenzkarte mit ${length} Positionen, Lineal, Bausteinen, Bauteilen, Faltung und Befunden`
      }
      style={{ display: "block", fontFamily: "var(--font-mono)" }}
    >
      {/* Hintergrund, damit der PNG-Export nicht durchsichtig wird. */}
      <rect width={width} height={height} fill="var(--surface)" />

      {/* Hervorhebung quer durch alle Spuren */}
      {highlight && (
        <rect
          x={x(highlight.start)}
          y={0}
          width={(highlight.end - highlight.start + 1) * cell}
          height={height}
          fill="var(--role-result)"
          fillOpacity={0.12}
          stroke="var(--role-result)"
          strokeOpacity={0.5}
        />
      )}

      {/* ---------------------------------------------- 1 Positionslineal */}
      <g>
        {label("Position", tops.ruler + TRACK.ruler / 2)}
        <line
          x1={GUTTER}
          x2={GUTTER + length * cell}
          y1={tops.ruler + TRACK.ruler - 1}
          y2={tops.ruler + TRACK.ruler - 1}
          stroke="var(--border)"
        />
        {Array.from({ length }, (_, index) => index + 1)
          .filter((p) => p === 1 || p % 5 === 0 || p === length)
          .map((p) => (
            <g key={p}>
              <line
                x1={center(p)}
                x2={center(p)}
                y1={tops.ruler + TRACK.ruler - 5}
                y2={tops.ruler + TRACK.ruler - 1}
                stroke="var(--text-faint)"
              />
              <text
                x={center(p)}
                y={tops.ruler + 8}
                textAnchor="middle"
                fontSize={9}
                fill="var(--text-faint)"
              >
                {p}
              </text>
            </g>
          ))}
        <text
          x={GUTTER - 2}
          y={tops.ruler + 8}
          textAnchor="end"
          fontSize={9}
          fill="var(--text-faint)"
        >
          5′
        </text>
        <text
          x={GUTTER + length * cell + 2}
          y={tops.ruler + 8}
          fontSize={9}
          fill="var(--text-faint)"
        >
          3′
        </text>
      </g>

      {/* --------------------------------------------------- 2 Basenspur */}
      <g>
        {label("Bausteine", tops.bases + TRACK.bases / 2)}
        {oligo.monomers.map((monomer) => {
          const color = KLASSE_COLOR[monomer.klasse as MonomerKlasse];
          const partner = pairs.get(monomer.position);
          const befunde = findingsByPosition.get(monomer.position) ?? [];
          const text =
            monomer.code.length === 1 ? monomer.code : monomer.code.slice(0, 1);
          return (
            <g key={monomer.position}>
              <rect
                x={x(monomer.position) + 0.5}
                y={tops.bases}
                width={cell - 1}
                height={TRACK.bases}
                fill={color}
                fillOpacity={monomer.modifications.length ? 0.22 : 0.1}
                stroke={color}
                strokeOpacity={monomer.modifications.length ? 0.9 : 0.35}
              />
              <text
                x={center(monomer.position)}
                y={tops.bases + TRACK.bases / 2}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={fontSize}
                fontWeight={monomer.modifications.length ? 700 : 400}
                fill={color}
              >
                {text}
              </text>
              <title>
                {[
                  `Position ${monomer.position}`,
                  `${monomer.code} — ${monomer.name}`,
                  KLASSE_LABEL[monomer.klasse as MonomerKlasse],
                  monomer.modifications.length
                    ? `Modifikation: ${monomer.modifications
                        .map((m) => m.name)
                        .join(", ")}`
                    : null,
                  monomer.base_parent
                    ? `natürliches Analogon: ${monomer.base_parent}`
                    : null,
                  `Rückgrat zur nächsten Position: ${
                    thioated.has(monomer.position)
                      ? "Phosphorothioat"
                      : monomer.position < length
                        ? "Phosphat"
                        : "— (3'-Ende)"
                  }`,
                  partner
                    ? `paart mit Position ${partner}`
                    : "in der MFE-Struktur ungepaart",
                  folding
                    ? `ungepaart mit ${(
                        (folding.unpaired[monomer.position - 1] ?? 0) * 100
                      ).toFixed(0)} %`
                    : null,
                  befunde.length
                    ? `Befunde: ${befunde.map((f) => f.title).join("; ")}`
                    : null,
                ]
                  .filter(Boolean)
                  .join("\n")}
              </title>
            </g>
          );
        })}

        {/* Phosphorothioat in der Lücke zwischen zwei Zellen. */}
        {[...thioated].map((position) => (
          <g key={`ps-${position}`}>
            <circle
              cx={x(position) + cell}
              cy={tops.bases + TRACK.bases / 2}
              r={Math.max(2.2, cell * 0.16)}
              fill="var(--mod-base)"
            />
            <title>
              {`Phosphorothioat an der Bindung ${position}–${position + 1}`}
            </title>
          </g>
        ))}
      </g>

      {/* ------------------------------------------------- 3 Bauteilspur */}
      <g>
        {label("Bauteile", tops.parts + TRACK.parts / 2)}
        {(parts?.parts ?? []).map((part) => {
          const color = PART_COLOR[part.kind] ?? "var(--role-settings)";
          const barWidth = part.length * cell;
          return (
            <g key={`${part.kind}-${part.start}`}>
              <rect
                x={x(part.start) + 1}
                y={tops.parts + 3}
                width={barWidth - 2}
                height={TRACK.parts - 6}
                rx={3}
                fill={color}
                fillOpacity={0.16}
                stroke={color}
              />
              {barWidth > 70 && (
                <text
                  x={x(part.start) + barWidth / 2}
                  y={tops.parts + TRACK.parts / 2}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={9}
                  fill={color}
                >
                  {part.label}
                </text>
              )}
              <title>{`${part.label}: Position ${part.start} bis ${part.end} (${part.length} nt)`}</title>
            </g>
          );
        })}
        {!parts?.found && (
          <text
            x={GUTTER + 4}
            y={tops.parts + TRACK.parts / 2}
            dominantBaseline="central"
            fontSize={9}
            fill="var(--text-faint)"
          >
            kein katalytischer Kern erkannt
          </text>
        )}
      </g>

      {/* ---------------------------------------------- 4 Bogendiagramm */}
      <g>
        {label("Faltung", tops.arcs + TRACK.arcs / 2)}
        <line
          x1={GUTTER}
          x2={GUTTER + length * cell}
          y1={tops.arcs + TRACK.arcs}
          y2={tops.arcs + TRACK.arcs}
          stroke="var(--border)"
        />
        {(folding?.pair_probabilities ?? []).map((pair) => {
          const from = center(pair.i);
          const to = center(pair.j);
          const span = Math.abs(to - from);
          // Höhe nach Spannweite, aber nie über die Spur hinaus.
          const rise = Math.min(TRACK.arcs - 4, span * 0.45 + 6);
          const baseline = tops.arcs + TRACK.arcs;
          return (
            <path
              key={`${pair.i}-${pair.j}`}
              d={`M ${from} ${baseline} Q ${(from + to) / 2} ${
                baseline - rise * 2
              } ${to} ${baseline}`}
              fill="none"
              stroke="var(--role-result)"
              strokeOpacity={0.25 + 0.65 * pair.p}
              strokeWidth={0.6 + 2.4 * pair.p}
            >
              <title>
                {`Position ${pair.i} paart mit ${pair.j}, Wahrscheinlichkeit ${(
                  pair.p * 100
                ).toFixed(0)} %`}
              </title>
            </path>
          );
        })}
        {folding && folding.pair_probabilities.length === 0 && (
          <text
            x={GUTTER + 4}
            y={tops.arcs + TRACK.arcs - 10}
            fontSize={9}
            fill="var(--text-faint)"
          >
            keine Basenpaare über 1 % — der Strang bleibt offen
          </text>
        )}
      </g>

      {/* ------------------------------------------------ 5 Ungepaart */}
      <g>
        {label("ungepaart", tops.unpaired + TRACK.unpaired / 2)}
        <line
          x1={GUTTER}
          x2={GUTTER + length * cell}
          y1={tops.unpaired + TRACK.unpaired}
          y2={tops.unpaired + TRACK.unpaired}
          stroke="var(--border)"
        />
        {(folding?.unpaired ?? []).map((value, index) => {
          const barHeight = Math.max(0.5, value * (TRACK.unpaired - 2));
          return (
            <rect
              key={index}
              x={x(index + 1) + 1}
              y={tops.unpaired + TRACK.unpaired - barHeight}
              width={Math.max(1, cell - 2)}
              height={barHeight}
              fill="var(--role-result)"
              fillOpacity={0.55}
            >
              <title>
                {`Position ${index + 1}: zu ${(value * 100).toFixed(
                  0,
                )} % ungepaart`}
              </title>
            </rect>
          );
        })}
      </g>

      {/* -------------------------------------------------- 6 Warnspur */}
      <g>
        {label("Befunde", tops.warnings + TRACK.warnings / 2)}
        {[...findingsByPosition.entries()].map(([position, list]) => {
          // Der schlimmste Befund bestimmt die Farbe.
          const worst = list.reduce<FindingView>(
            (a, b) =>
              ({ kritisch: 0, warnung: 1, hinweis: 2 })[a.severity] <=
              ({ kritisch: 0, warnung: 1, hinweis: 2 })[b.severity]
                ? a
                : b,
            list[0]!,
          );
          return (
            <rect
              key={position}
              x={x(position) + 0.5}
              y={tops.warnings + 3}
              width={cell - 1}
              height={TRACK.warnings - 6}
              rx={2}
              fill={SEVERITY_COLOR[worst.severity]}
              style={{ cursor: onPickFinding ? "pointer" : undefined }}
              onClick={() => onPickFinding?.(worst)}
            >
              <title>
                {list.map((f) => `${f.severity_label}: ${f.title}`).join("\n")}
              </title>
            </rect>
          );
        })}
        {findingsByPosition.size === 0 && (
          <text
            x={GUTTER + 4}
            y={tops.warnings + TRACK.warnings / 2}
            dominantBaseline="central"
            fontSize={9}
            fill="var(--text-faint)"
          >
            keine Befunde an einzelnen Positionen
          </text>
        )}
      </g>
    </svg>
  );
}

export { SEVERITY_COLOR };
