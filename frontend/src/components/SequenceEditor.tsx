/* Das Sequenzfeld.
 *
 * Aufbau: eine durchsichtige `textarea` liegt genau ueber einer gefaerbten
 * Textschicht. Beide tragen dieselbe Schrift, Groesse, Laufweite, Zeilenhoehe
 * und denselben Innenabstand, darum stehen die Zeichen exakt uebereinander.
 * Gefaerbt wird der ROHE Text, nicht eine umformatierte Fassung — sonst
 * wuerden die Positionen auseinanderlaufen, sobald der Nutzer Leerzeichen
 * setzt.
 *
 * Die Dreiergruppen wie im Excel macht ein Knopf, nicht die Eingabe selbst:
 * waehrend des Tippens umzuformatieren wuerde dem Nutzer den Cursor
 * wegziehen.
 *
 * Unbekannte Zeichen werden rot unterkringelt und erklaeren sich beim
 * Ueberfahren (CLAUDE.md, Regel 5 — nie stillschweigend ueberspringen).
 */

import { useMemo } from "react";
import type { MonomerKlasse, NotationProblem, OligoView } from "../types";

/* Modifikationsfarben — dieselben wie in jeder anderen Ansicht. */
export const KLASSE_COLOR: Record<MonomerKlasse, string> = {
  dna: "var(--mod-dna)",
  rna: "var(--mod-rna)",
  zucker: "var(--mod-sugar)",
  base: "var(--mod-base)",
  konjugat: "var(--mod-conjugate)",
  custom: "var(--text)",
};

export const KLASSE_LABEL: Record<MonomerKlasse, string> = {
  dna: "DNA, natürlich",
  rna: "RNA-Baustein",
  zucker: "Zuckermodifikation",
  base: "Basenmodifikation",
  konjugat: "Konjugat",
  custom: "eigener Baustein",
};

type Segment =
  | { kind: "monomer"; start: number; end: number; klasse: MonomerKlasse; title: string }
  | { kind: "conjugate"; start: number; end: number; title: string }
  | { kind: "unknown"; start: number; end: number; title: string };

function buildSegments(
  oligo: OligoView | null,
  problems: NotationProblem[],
): Segment[] {
  const segments: Segment[] = [];

  for (const monomer of oligo?.monomers ?? []) {
    const mods = monomer.modifications.map((m) => m.name).join(", ");
    segments.push({
      kind: "monomer",
      start: monomer.span.start,
      end: monomer.span.end,
      klasse: monomer.klasse,
      title:
        `Position ${monomer.position} · ${monomer.name}` +
        (mods ? ` · ${mods}` : "") +
        (monomer.base_parent ? ` · Analogon ${monomer.base_parent}` : ""),
    });
  }

  for (const problem of problems) {
    segments.push({
      kind: "unknown",
      start: problem.start,
      end: problem.end,
      title: problem.hint
        ? `${problem.message} ${problem.hint}`
        : problem.message,
    });
  }

  return segments.sort((a, b) => a.start - b.start);
}

/** Zeichen fuer Zeichen die passende Farbe. */
function highlight(
  text: string,
  oligo: OligoView | null,
  problems: NotationProblem[],
) {
  const segments = buildSegments(oligo, problems);
  const nodes: React.ReactNode[] = [];
  let index = 0;
  let key = 0;

  // Die Konjugate stehen nicht in `monomers`; ihre Spannen kommen nicht aus
  // der Antwort. Sie werden direkt im Text gefunden — ein Paar Schraegstriche,
  // das keine gemeldete Fehlstelle ist.
  const conjugateSpans: [number, number][] = [];
  if (oligo && oligo.conjugates.length > 0) {
    const pattern = /\/[^/]*\//g;
    let found: RegExpExecArray | null;
    while ((found = pattern.exec(text)) !== null) {
      conjugateSpans.push([found.index, found.index + found[0].length]);
    }
  }

  const covering = (position: number): Segment | undefined =>
    segments.find((s) => position >= s.start && position < s.end);

  while (index < text.length) {
    const segment = covering(index);

    if (segment) {
      const slice = text.slice(segment.start, segment.end);
      if (segment.kind === "unknown") {
        nodes.push(
          <span key={key++} className="ol-seq-unknown" title={segment.title}>
            {slice}
          </span>,
        );
      } else if (segment.kind === "monomer") {
        nodes.push(
          <span
            key={key++}
            title={segment.title}
            style={{
              color: KLASSE_COLOR[segment.klasse],
              textDecoration:
                segment.klasse === "custom" ? "underline dotted" : undefined,
              textUnderlineOffset: 3,
            }}
          >
            {slice}
          </span>,
        );
      }
      index = segment.end;
      continue;
    }

    const conjugate = conjugateSpans.find(
      ([start, end]) => index >= start && index < end,
    );
    if (conjugate) {
      nodes.push(
        <span
          key={key++}
          style={{ color: "var(--mod-conjugate)", fontWeight: 600 }}
          title="Konjugat — zählt nicht zur Basenzahl"
        >
          {text.slice(conjugate[0], conjugate[1])}
        </span>,
      );
      index = conjugate[1];
      continue;
    }

    const character = text[index] ?? "";
    if (character === "*") {
      // Phosphorothioat: sitzt an der Bindung, darum steht das Symbol in der
      // Luecke zwischen zwei Zellen.
      nodes.push(
        <span
          key={key++}
          className="ol-seq-ps"
          title="Phosphorothioat an dieser Bindung"
        >
          {character}
        </span>,
      );
    } else {
      nodes.push(<span key={key++}>{character}</span>);
    }
    index += 1;
  }

  // Ein Abschlusszeichen, damit eine letzte leere Zeile nicht wegfaellt.
  nodes.push(<span key={key++}>{"​"}</span>);
  return nodes;
}

/** Rohen Text in Dreiergruppen setzen, wie das Excel ihn anzeigt. */
export function groupInThrees(text: string): string {
  // Erst in Zeichen zerlegen, die zusammengehoeren: [..], /../, X* und X.
  const tokens: string[] = [];
  let index = 0;
  while (index < text.length) {
    const character = text[index] ?? "";
    if (/\s/.test(character)) {
      index += 1;
      continue;
    }
    let token: string;
    if (character === "[") {
      const close = text.indexOf("]", index);
      token = close === -1 ? text.slice(index) : text.slice(index, close + 1);
    } else if (character === "/") {
      const close = text.indexOf("/", index + 1);
      token = close === -1 ? text.slice(index) : text.slice(index, close + 1);
    } else {
      token = character;
    }
    index += token.length;
    // Ein folgendes `*` gehoert an den Baustein, nicht in die naechste Gruppe.
    if (text[index] === "*") {
      token += "*";
      index += 1;
    }
    tokens.push(token);
  }

  const groups: string[] = [];
  for (let start = 0; start < tokens.length; start += 3) {
    groups.push(tokens.slice(start, start + 3).join(""));
  }
  return groups.join(" ");
}

export function SequenceEditor({
  value,
  onChange,
  oligo,
  problems,
  rows = 4,
}: {
  value: string;
  onChange: (value: string) => void;
  oligo: OligoView | null;
  problems: NotationProblem[];
  rows?: number;
}) {
  const nodes = useMemo(
    () => highlight(value, oligo, problems),
    [value, oligo, problems],
  );

  // Beide Schichten tragen exakt dieselben Textmasse, sonst laufen die Zeichen
  // auseinander. Rahmen und Hintergrund gehoeren an den Container: haette die
  // Textarea einen eigenen Hintergrund, wuerde sie die Farbschicht verdecken.
  const shared: React.CSSProperties = {
    margin: 0,
    padding: "10px 12px",
    border: "none",
    minHeight: `${rows * 29 + 20}px`,
  };

  return (
    <div
      className="relative overflow-hidden"
      data-help="field.sequence"
      style={{
        background: "var(--surface)",
        border:
          "1px solid color-mix(in srgb, var(--role-input) 55%, var(--border))",
        borderRadius: "var(--radius-card)",
      }}
    >
      {/* Die Farbschicht. Liest nur, nimmt keine Eingaben. */}
      <div
        aria-hidden="true"
        className="ol-seq pointer-events-none absolute inset-0 overflow-hidden"
        style={shared}
      >
        {nodes}
      </div>

      {/* Die Eingabe. Durchsichtige Schrift, sichtbarer Cursor. */}
      <textarea
        className="ol-seq relative block w-full resize-y"
        style={{
          ...shared,
          background: "transparent",
          color: "transparent",
          caretColor: "var(--text)",
          outlineOffset: -2,
        }}
        spellCheck={false}
        autoCapitalize="characters"
        rows={rows}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="z. B. TTG GGG TAA GGC TAG CTA CAA CGA GGT GCA TGT"
        aria-label="Sequenz in Synthi-Sprache"
      />
    </div>
  );
}

/** Die Sequenz mit Positionslineal, ab 20 Bausteinen (Designsprache).
 *
 * Klassischer Blocksatz: Zehnerbloecke, je Zeile 30 Bausteine, links die
 * Startposition. Das liest sich ohne Zaehlen und braucht keine Tricks mit
 * Spaltenbreiten. Die ausfuehrliche Sequenzkarte als SVG gehoert zu Phase 3.
 */
export function SequenceRuler({ oligo }: { oligo: OligoView }) {
  if (oligo.length < 20) return null;

  const PER_ROW = 30;
  const PER_BLOCK = 10;

  const thioated = new Set(
    oligo.linkages
      .filter((l) => l.kind === "phosphorothioate")
      .map((l) => l.position),
  );

  const rows: { start: number; items: OligoView["monomers"] }[] = [];
  for (let start = 0; start < oligo.monomers.length; start += PER_ROW) {
    rows.push({
      start: start + 1,
      items: oligo.monomers.slice(start, start + PER_ROW),
    });
  }

  const gutter = String(oligo.length).length + 1;

  return (
    <div className="ol-mono overflow-x-auto text-xs" style={{ lineHeight: 1.8 }}>
      {rows.map((row) => (
        <div key={row.start} className="whitespace-nowrap">
          <span
            style={{
              display: "inline-block",
              width: `${gutter}ch`,
              textAlign: "right",
              color: "var(--text-faint)",
              marginRight: "1.5ch",
            }}
          >
            {row.start}
          </span>
          {row.items.map((monomer, offset) => (
            <span key={monomer.position}>
              {offset > 0 && offset % PER_BLOCK === 0 ? " " : ""}
              <span
                title={
                  `Position ${monomer.position} · ${monomer.name}` +
                  (monomer.modifications.length
                    ? ` · ${monomer.modifications.map((m) => m.name).join(", ")}`
                    : "") +
                  (thioated.has(monomer.position)
                    ? " · Phosphorothioat zur nächsten Position"
                    : "")
                }
                style={{
                  color: KLASSE_COLOR[monomer.klasse],
                  fontWeight: monomer.modifications.length ? 700 : 400,
                  textDecoration:
                    monomer.klasse === "custom" ? "underline dotted" : undefined,
                }}
              >
                {monomer.code.length === 1 ? monomer.code : "\u25c6"}
              </span>
              {thioated.has(monomer.position) && (
                <span className="ol-seq-ps" aria-hidden="true">
                  *
                </span>
              )}
            </span>
          ))}
        </div>
      ))}
      <p className="mt-2" style={{ color: "var(--text-faint)" }}>
        5′ links, 3′ rechts · ◆ steht für einen Baustein mit
        mehrstelligem Code · * markiert ein Phosphorothioat in der Lücke
      </p>
    </div>
  );
}
