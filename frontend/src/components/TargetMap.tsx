/* Die Spurdarstellung der Ziel-RNA (PHASEN.md 4.4).
 *
 * Bewusst dieselbe Sprache wie die Sequenzkarte aus Phase 3: gleicher linker
 * Rand, gleiche Spurbeschriftungen, gleiche Farben. Wer zwischen Strang und
 * Ziel wechselt, soll sich nicht umgewöhnen müssen.
 *
 * Der Unterschied zum Strang ist die Größe. Ein DNAzym hat 33 Nukleotide, ein
 * Transkript hat Tausende — eine Zelle je Base gibt es hier also nicht. Statt
 * dessen zwei Darstellungen:
 *
 *   `Overview`   die ganze Länge auf eine Breite gestaucht, mit dem
 *                Zugänglichkeitsprofil und dem gewählten Bereich darin.
 *                Zum Auswählen anklicken oder ziehen.
 *   `TargetMap`  der gewählte Bereich in Spuren: Lineal, Abschnitte,
 *                Bogendiagramm, Zugänglichkeit als Flächendiagramm
 *                (hoch = offen) und die Spur für die Spaltstellen, die
 *                Phase 5 füllt.
 */

import { useMemo, useRef } from "react";
import type {
  AccessibilityView,
  RegionKind,
  RegionView,
  TargetFoldView,
} from "../types";

const GUTTER = 92;
const PAD_RIGHT = 16;

const TRACK = {
  ruler: 20,
  regions: 18,
  arcs: 56,
  access: 46,
  sites: 14,
} as const;

const GAP = 6;

/* Abschnittsfarben. Nicht aus der Modifikationstabelle — ein 5'UTR ist keine
 * Modifikation. Darum die Rollenfarben, die ohnehin für Einordnung stehen. */
const REGION_COLOR: Record<RegionKind, string> = {
  "5utr": "var(--role-settings)",
  cds: "var(--role-result)",
  "3utr": "var(--role-settings)",
  other: "var(--text-faint)",
};

export interface Range {
  start: number;
  end: number;
}

function layout() {
  let y = 0;
  const tops: Record<keyof typeof TRACK, number> = {} as never;
  for (const key of Object.keys(TRACK) as (keyof typeof TRACK)[]) {
    tops[key] = y;
    y += TRACK[key] + GAP;
  }
  return { tops, height: y - GAP };
}

/** Punkte für ein Flächendiagramm, auf `breite` Pixel heruntergerechnet. */
function areaPoints(
  values: (number | null)[],
  width: number,
  height: number,
  offsetX: number,
  baseline: number,
): string {
  if (values.length === 0) return "";
  const schritte = Math.min(width, values.length);
  const proSchritt = values.length / schritte;
  const punkte: string[] = [`${offsetX},${baseline}`];

  for (let k = 0; k < schritte; k += 1) {
    const von = Math.floor(k * proSchritt);
    const bis = Math.max(von + 1, Math.floor((k + 1) * proSchritt));
    // Beim Stauchen das Maximum nehmen: eine offene Stelle darf nicht
    // verschwinden, nur weil ihre Nachbarn zu sind. Der Mittelwert würde
    // genau das tun.
    let hoechster = 0;
    for (let i = von; i < bis && i < values.length; i += 1) {
      const wert = values[i];
      if (wert !== null && wert !== undefined && wert > hoechster) hoechster = wert;
    }
    const x = offsetX + (k / schritte) * width;
    punkte.push(`${x.toFixed(1)},${(baseline - hoechster * height).toFixed(1)}`);
  }

  punkte.push(`${offsetX + width},${baseline}`);
  return punkte.join(" ");
}

/* ------------------------------------------------------- Übersichtsleiste */

export function Overview({
  length,
  regions,
  accessibility,
  selection,
  onSelect,
  width = 900,
}: {
  length: number;
  regions: RegionView[];
  accessibility: AccessibilityView | null;
  selection: Range;
  onSelect: (range: Range) => void;
  width?: number;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const height = 54;
  const plot = width - GUTTER - PAD_RIGHT;
  const baseline = height - 14;

  const x = (position: number) =>
    GUTTER + ((position - 1) / Math.max(1, length - 1)) * plot;

  /** Welche Position liegt unter dem Mauszeiger? */
  const positionAt = (clientX: number): number => {
    const box = svgRef.current?.getBoundingClientRect();
    if (!box) return 1;
    const relativ = ((clientX - box.left) / box.width) * width;
    const anteil = (relativ - GUTTER) / plot;
    return Math.max(1, Math.min(length, Math.round(anteil * (length - 1)) + 1));
  };

  const ziehen = (event: React.PointerEvent<SVGSVGElement>) => {
    const anfang = positionAt(event.clientX);
    const breite = Math.max(1, selection.end - selection.start);

    const bewegen = (e: PointerEvent) => {
      const jetzt = positionAt(e.clientX);
      onSelect({
        start: Math.min(anfang, jetzt),
        end: Math.max(anfang, jetzt),
      });
    };
    const loslassen = (e: PointerEvent) => {
      window.removeEventListener("pointermove", bewegen);
      window.removeEventListener("pointerup", loslassen);
      // Ein Klick ohne Ziehen verschiebt das Fenster, statt es auf eine
      // einzelne Base zusammenzuziehen.
      if (Math.abs(positionAt(e.clientX) - anfang) <= 1) {
        const halb = Math.round(breite / 2);
        onSelect({
          start: Math.max(1, anfang - halb),
          end: Math.min(length, anfang - halb + breite),
        });
      }
    };
    window.addEventListener("pointermove", bewegen);
    window.addEventListener("pointerup", loslassen);
  };

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height={height}
      role="img"
      aria-label={`Übersicht über ${length} Basen; gewählt ist ${selection.start} bis ${selection.end}`}
      style={{ display: "block", cursor: "ew-resize", touchAction: "none" }}
      onPointerDown={ziehen}
    >
      <rect width={width} height={height} fill="var(--surface)" />
      <text
        x={GUTTER - 8}
        y={height / 2}
        textAnchor="end"
        fontSize={9}
        fill="var(--text-faint)"
        dominantBaseline="middle"
      >
        Übersicht
      </text>

      {/* Zugänglichkeit über die ganze Länge */}
      {accessibility?.available && (
        <polygon
          points={areaPoints(accessibility.profile, plot, baseline - 6, GUTTER, baseline)}
          fill="var(--role-result)"
          fillOpacity={0.3}
        />
      )}

      {/* Abschnitte als dünner Streifen darunter */}
      {regions.map((region) => (
        <rect
          key={`${region.kind}-${region.start}`}
          x={x(region.start)}
          y={baseline + 2}
          width={Math.max(1, x(region.end) - x(region.start))}
          height={5}
          fill={REGION_COLOR[region.kind]}
          fillOpacity={0.6}
        >
          <title>{`${region.label}: ${region.start}–${region.end}`}</title>
        </rect>
      ))}

      <line
        x1={GUTTER}
        x2={GUTTER + plot}
        y1={baseline}
        y2={baseline}
        stroke="var(--border)"
      />

      {/* Der gewählte Bereich */}
      <rect
        x={x(selection.start)}
        y={2}
        width={Math.max(2, x(selection.end) - x(selection.start))}
        height={height - 4}
        fill="var(--role-result)"
        fillOpacity={0.14}
        stroke="var(--role-result)"
      />

      <text x={GUTTER} y={height - 2} fontSize={9} fill="var(--text-faint)">
        1
      </text>
      <text
        x={GUTTER + plot}
        y={height - 2}
        textAnchor="end"
        fontSize={9}
        fill="var(--text-faint)"
      >
        {length}
      </text>
    </svg>
  );
}

/* ----------------------------------------------------------- Detailkarte */

export function TargetMap({
  sequence,
  regions,
  folding,
  accessibility,
  range,
  width = 900,
  svgId,
}: {
  sequence: string;
  regions: RegionView[];
  folding: TargetFoldView | null;
  accessibility: AccessibilityView | null;
  range: Range;
  width?: number;
  svgId?: string;
}) {
  const { tops, height } = useMemo(layout, []);
  const laenge = range.end - range.start + 1;
  const plot = width - GUTTER - PAD_RIGHT;
  const cell = plot / Math.max(1, laenge);

  /** Bildposition einer Sequenzposition. */
  const x = (position: number) => GUTTER + (position - range.start) * cell;
  const center = (position: number) => x(position) + cell / 2;

  // Basenbuchstaben nur, wenn sie lesbar wären.
  const zeigeBasen = cell >= 7;

  const paare = useMemo(() => {
    const out: { i: number; j: number }[] = [];
    const struktur = folding?.structure;
    if (!struktur || !folding) return out;
    const stapel: number[] = [];
    for (let k = 0; k < struktur.length; k += 1) {
      if (struktur[k] === "(") stapel.push(k);
      else if (struktur[k] === ")") {
        const offen = stapel.pop();
        if (offen !== undefined) {
          out.push({ i: folding.start + offen, j: folding.start + k });
        }
      }
    }
    return out;
  }, [folding]);

  const profilAusschnitt = useMemo(() => {
    if (!accessibility?.available) return [];
    const von = range.start - accessibility.start;
    const bis = range.end - accessibility.start + 1;
    return accessibility.profile.slice(Math.max(0, von), Math.max(0, bis));
  }, [accessibility, range]);

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

  // Alle fünf Positionen nummerieren, wie in Phase 3 — aber nur so dicht,
  // wie die Beschriftungen noch nebeneinander passen.
  const schrittweite = Math.max(5, Math.ceil(40 / Math.max(cell, 0.01) / 5) * 5);

  return (
    <svg
      id={svgId}
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height={height}
      role="img"
      aria-label={`Zielkarte, Position ${range.start} bis ${range.end}`}
      style={{ display: "block", fontFamily: "var(--font-mono)" }}
    >
      <rect width={width} height={height} fill="var(--surface)" />

      {/* ------------------------------------------- 1 Positionslineal */}
      <g>
        {label("Position", tops.ruler + TRACK.ruler / 2)}
        <line
          x1={GUTTER}
          x2={GUTTER + plot}
          y1={tops.ruler + TRACK.ruler - 1}
          y2={tops.ruler + TRACK.ruler - 1}
          stroke="var(--border)"
        />
        {Array.from({ length: laenge }, (_, k) => range.start + k)
          .filter((p) => p === range.start || p % schrittweite === 0 || p === range.end)
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
      </g>

      {/* Basen, wenn sie lesbar wären */}
      {zeigeBasen && (
        <g>
          {Array.from({ length: laenge }, (_, k) => {
            const position = range.start + k;
            const base = sequence[position - 1] ?? "";
            return (
              <text
                key={position}
                x={center(position)}
                y={tops.ruler + TRACK.ruler + 2}
                textAnchor="middle"
                fontSize={Math.min(12, cell)}
                fill="var(--text-muted)"
              >
                {base}
              </text>
            );
          })}
        </g>
      )}

      {/* ---------------------------------------------- 2 Abschnitte */}
      <g>
        {label("Abschnitte", tops.regions + TRACK.regions / 2)}
        {regions
          .filter((r) => r.end >= range.start && r.start <= range.end)
          .map((region) => {
            const von = Math.max(region.start, range.start);
            const bis = Math.min(region.end, range.end);
            const breite = (bis - von + 1) * cell;
            const color = REGION_COLOR[region.kind];
            return (
              <g key={`${region.kind}-${region.start}`}>
                <rect
                  x={x(von)}
                  y={tops.regions + 3}
                  width={Math.max(1, breite)}
                  height={TRACK.regions - 6}
                  rx={3}
                  fill={color}
                  fillOpacity={0.16}
                  stroke={color}
                />
                {breite > 60 && (
                  <text
                    x={x(von) + breite / 2}
                    y={tops.regions + TRACK.regions / 2}
                    textAnchor="middle"
                    dominantBaseline="central"
                    fontSize={9}
                    fill={color}
                  >
                    {region.label}
                  </text>
                )}
                <title>{`${region.label}: ${region.start}–${region.end}`}</title>
              </g>
            );
          })}
        {regions.length === 0 && (
          <text
            x={GUTTER + 4}
            y={tops.regions + TRACK.regions / 2}
            dominantBaseline="central"
            fontSize={9}
            fill="var(--text-faint)"
          >
            keine Abschnitte bekannt — kommen aus GenBank oder Ensembl
          </text>
        )}
      </g>

      {/* --------------------------------------------- 3 Bogendiagramm */}
      <g>
        {label("Faltung", tops.arcs + TRACK.arcs / 2)}
        <line
          x1={GUTTER}
          x2={GUTTER + plot}
          y1={tops.arcs + TRACK.arcs}
          y2={tops.arcs + TRACK.arcs}
          stroke="var(--border)"
        />
        {paare
          .filter((p) => p.j >= range.start && p.i <= range.end)
          .map((paar) => {
            const von = center(Math.max(paar.i, range.start));
            const bis = center(Math.min(paar.j, range.end));
            const spanne = Math.abs(bis - von);
            const hoehe = Math.min(TRACK.arcs - 4, spanne * 0.45 + 4);
            const grund = tops.arcs + TRACK.arcs;
            return (
              <path
                key={`${paar.i}-${paar.j}`}
                d={`M ${von} ${grund} Q ${(von + bis) / 2} ${grund - hoehe * 2} ${bis} ${grund}`}
                fill="none"
                stroke="var(--role-result)"
                strokeOpacity={0.45}
                strokeWidth={1}
              >
                <title>{`${paar.i} paart mit ${paar.j}`}</title>
              </path>
            );
          })}
        {!folding?.available && (
          <text
            x={GUTTER + 4}
            y={tops.arcs + TRACK.arcs - 10}
            fontSize={9}
            fill="var(--text-faint)"
          >
            {folding?.note
              ? "Gesamtfaltung ausgelassen — siehe Hinweis unter der Karte"
              : "noch nicht gefaltet"}
          </text>
        )}
      </g>

      {/* -------------------------------- 4 Zugänglichkeit, hoch = offen */}
      <g>
        {label("zugänglich", tops.access + TRACK.access / 2 + 1)}
        <line
          x1={GUTTER}
          x2={GUTTER + plot}
          y1={tops.access + TRACK.access}
          y2={tops.access + TRACK.access}
          stroke="var(--border)"
        />
        {[0.5, 1].map((anteil) => (
          <line
            key={anteil}
            x1={GUTTER}
            x2={GUTTER + plot}
            y1={tops.access + TRACK.access - anteil * TRACK.access}
            y2={tops.access + TRACK.access - anteil * TRACK.access}
            stroke="var(--border)"
            strokeDasharray="2 3"
          />
        ))}
        {profilAusschnitt.length > 0 && (
          <polygon
            points={areaPoints(
              profilAusschnitt,
              plot,
              TRACK.access - 2,
              GUTTER,
              tops.access + TRACK.access,
            )}
            fill="var(--role-result)"
            fillOpacity={0.45}
            stroke="var(--role-result)"
            strokeWidth={0.8}
          />
        )}
        {/* Die Skala gehoert in den Rand, nicht ins Diagramm — dort lag sie
            ueber der Flaeche. */}
        <text
          x={GUTTER - 8}
          y={tops.access + 5}
          textAnchor="end"
          fontSize={8}
          fill="var(--text-faint)"
        >
          1,0 offen
        </text>
        <text
          x={GUTTER - 8}
          y={tops.access + TRACK.access - 2}
          textAnchor="end"
          fontSize={8}
          fill="var(--text-faint)"
        >
          0
        </text>
      </g>

      {/* ---------------------------------- 5 Spaltstellen, Phase 5 füllt */}
      <g>
        {label("Spaltstellen", tops.sites + TRACK.sites / 2)}
        <rect
          x={GUTTER}
          y={tops.sites + 3}
          width={plot}
          height={TRACK.sites - 6}
          fill="var(--surface-sunken)"
          stroke="var(--border)"
          strokeDasharray="3 3"
        />
        <text
          x={GUTTER + 6}
          y={tops.sites + TRACK.sites / 2}
          dominantBaseline="central"
          fontSize={9}
          fill="var(--text-faint)"
        >
          Phase 5 trägt hier die Kandidaten ein
        </text>
      </g>
    </svg>
  );
}
