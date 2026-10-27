/* Die 3D-Ansicht mit 3Dmol.js (PHASEN.md 6.4).
 *
 * Cartoon für das Rückgrat, Stick für ausgewählte Reste. Die Einfärbung ist
 * umschaltbar — und die Einfärbung nach Modifikationstyp benutzt DIESELBEN
 * Farben wie die Sequenzkarte. Gleiche Sprache in 2D und 3D ist keine
 * Spielerei: wer orange in der Karte als Basenmodifikation gelernt hat, darf
 * es im Modell nicht neu lernen müssen (CLAUDE.md, Designsprache).
 *
 * 3Dmol.js arbeitet außerhalb von React auf einem eigenen Element. Darum
 * wird der Betrachter einmal gebaut und danach nur noch angewiesen — ein
 * Neuaufbau bei jeder Änderung würde die Ansicht jedes Mal zurückdrehen,
 * und man verlöre, was man gerade eingestellt hat.
 */

import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ModelPositionView } from "../types";
import { KLASSE_COLOR } from "./SequenceEditor";

export type ColorMode = "chain" | "part" | "modification";

export const COLOR_MODE_LABEL: Record<ColorMode, string> = {
  chain: "nach Kette",
  part: "nach Bauteil",
  modification: "nach Modifikation",
};

/** Die Farben der Bauteile — grau, blau, grau wie in der Sequenzkarte. */
const PART_COLOR = {
  arm: "#8a8f98",
  core: "#1f6fb2",
  substrate: "#b06ec4",
};

const CHAIN_COLORS = ["#8a8f98", "#1f6fb2", "#c98b2e", "#4a9d6a"];

/** Die Farbtokens aufgelöst — 3Dmol kennt kein `var(--…)`. */
function resolveColor(token: string): string {
  const name = token.match(/var\((--[^)]+)\)/)?.[1];
  if (!name) return token;
  const wert = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  return wert || "#888888";
}

export interface ViewerProps {
  /** Der PDB-Text des Modells. */
  pdb: string;
  positions: ModelPositionView[];
  chainDnazyme: string;
  chainSubstrate: string;
  coreRange: [number, number] | null;
  /** Rest der Substratkette, hinter dem geschnitten wird. */
  cleavageResidue: number | null;
  colorMode: ColorMode;
  /** Ausgewählte Position im STRANG (nicht die Restnummer). */
  selected: number | null;
  onPick?: (position: number | null) => void;
  height?: number;
}

export interface StructureViewerHandle {
  /** Auf die Spaltstelle zentrieren (PHASEN.md 6.4). */
  centerOnCleavage: () => void;
  /** Wieder alles zeigen. */
  reset: () => void;
}

export const StructureViewer = forwardRef<StructureViewerHandle, ViewerProps>(
  function StructureViewer(
    {
      pdb,
      positions,
      chainDnazyme,
      chainSubstrate,
      coreRange,
      cleavageResidue,
      colorMode,
      selected,
      onPick,
      height = 460,
    },
    ref,
  ) {
    const halter = useRef<HTMLDivElement | null>(null);
    const betrachter = useRef<any>(null);
    const [fehler, setFehler] = useState<string | null>(null);
  /* Der Betrachter entsteht erst, wenn 3Dmol geladen ist — und das dauert.
   * Ohne diesen Zustand lief der Zeichen-Effekt einmal ins Leere (der
   * Betrachter war noch null) und danach nie wieder, weil sich keine seiner
   * Abhängigkeiten mehr änderte. Die Ansicht blieb leer. */
  const [bereit, setBereit] = useState(false);

    useImperativeHandle(
      ref,
      () => ({
        centerOnCleavage: () => {
          const ansicht = betrachter.current;
          if (!ansicht) return;
          if (cleavageResidue === null || !chainSubstrate) {
            ansicht.zoomTo();
          } else {
            ansicht.zoomTo({
              chain: chainSubstrate,
              resi: [cleavageResidue, cleavageResidue + 1],
            });
          }
          ansicht.render();
        },
        reset: () => {
          betrachter.current?.zoomTo();
          betrachter.current?.render();
        },
      }),
      [cleavageResidue, chainSubstrate],
    );

    // Position im Strang → Restnummer in der Datei und zurück.
    const nachRest = useMemo(() => {
      const hin = new Map<number, number>();
      const rueck = new Map<number, number>();
      for (const eintrag of positions) {
        hin.set(eintrag.position, eintrag.residue_number);
        rueck.set(eintrag.residue_number, eintrag.position);
      }
      return { hin, rueck };
    }, [positions]);

    // ---- einmal aufbauen
    useEffect(() => {
      let abgebrochen = false;
      (async () => {
        if (!halter.current) return;
        try {
          const modul = await import("3dmol");
          if (abgebrochen || !halter.current) return;
          const dreiD = (modul as any).default ?? modul;
          betrachter.current = dreiD.createViewer(halter.current, {
            backgroundColor: resolveColor("var(--surface)") || "#ffffff",
          });
          setBereit(true);
        } catch (grund) {
          setFehler(
            "Die 3D-Ansicht konnte nicht geladen werden: " +
              (grund instanceof Error ? grund.message : String(grund)),
          );
        }
      })();
      return () => {
        abgebrochen = true;
        betrachter.current?.clear?.();
        betrachter.current = null;
        setBereit(false);
      };
    }, []);

    // ---- bei jeder Änderung neu zeichnen, aber nicht neu aufbauen
    useEffect(() => {
      const ansicht = betrachter.current;
      if (!bereit || !ansicht || !pdb) return;

      const warBelegt = ansicht.getModel?.() != null;
      ansicht.removeAllModels();
      ansicht.removeAllLabels();
      ansicht.removeAllShapes();
      ansicht.addModel(pdb, "pdb");

      // --- Rückgrat als Cartoon
      if (colorMode === "chain") {
        const ketten = [...new Set(positions.map((p) => p.chain))];
        ansicht.setStyle({}, { cartoon: { color: CHAIN_COLORS[0] } });
        ketten.forEach((kette, index) => {
          ansicht.setStyle(
            { chain: kette },
            { cartoon: { color: CHAIN_COLORS[index % CHAIN_COLORS.length] } },
          );
        });
        ansicht.setStyle(
          { chain: chainSubstrate },
          { cartoon: { color: PART_COLOR.substrate } },
        );
      } else if (colorMode === "part") {
        ansicht.setStyle(
          { chain: chainDnazyme },
          { cartoon: { color: PART_COLOR.arm } },
        );
        if (coreRange) {
          const [von, bis] = coreRange;
          const reste = positions
            .filter((p) => p.position >= von && p.position <= bis)
            .map((p) => p.residue_number);
          if (reste.length) {
            ansicht.setStyle(
              { chain: chainDnazyme, resi: reste },
              { cartoon: { color: PART_COLOR.core } },
            );
          }
        }
        ansicht.setStyle(
          { chain: chainSubstrate },
          { cartoon: { color: PART_COLOR.substrate } },
        );
      } else {
        // Nach Modifikationstyp — mit den Farben der Sequenzkarte.
        ansicht.setStyle(
          { chain: chainDnazyme },
          { cartoon: { color: resolveColor(KLASSE_COLOR.dna) } },
        );
        ansicht.setStyle(
          { chain: chainSubstrate },
          { cartoon: { color: resolveColor(KLASSE_COLOR.rna) } },
        );
        const nachKlasse = new Map<string, number[]>();
        for (const eintrag of positions) {
          if (!eintrag.modification) continue;
          const liste = nachKlasse.get(eintrag.klasse) ?? [];
          liste.push(eintrag.residue_number);
          nachKlasse.set(eintrag.klasse, liste);
        }
        for (const [klasse, reste] of nachKlasse) {
          const farbe = resolveColor(
            KLASSE_COLOR[klasse as keyof typeof KLASSE_COLOR] ??
              KLASSE_COLOR.dna,
          );
          ansicht.setStyle(
            { chain: chainDnazyme, resi: reste },
            {
              cartoon: { color: farbe },
              stick: { color: farbe, radius: 0.18 },
            },
          );
        }
      }

      // --- modifizierte Positionen immer als Stick hervorheben
      const modifiziert = positions
        .filter((p) => p.modification)
        .map((p) => p.residue_number);
      if (modifiziert.length) {
        ansicht.addStyle(
          { chain: chainDnazyme, resi: modifiziert },
          { stick: { radius: 0.2 } },
        );
      }

      // --- die Spaltstelle: immer markiert und beschriftet
      if (cleavageResidue !== null && chainSubstrate) {
        ansicht.addStyle(
          {
            chain: chainSubstrate,
            resi: [cleavageResidue, cleavageResidue + 1],
          },
          { stick: { radius: 0.24 } },
        );
        ansicht.addLabel(
          `Spaltstelle ${cleavageResidue}/${cleavageResidue + 1}`,
          {
            fontSize: 12,
            backgroundColor: resolveColor("var(--rating-bad)"),
            backgroundOpacity: 0.85,
            fontColor: "white",
            alignment: "center",
            // An den Rest gehängt, damit die Beschriftung mitdreht.
            sel: { chain: chainSubstrate, resi: cleavageResidue, atom: "P" },
          },
        );
      }

      // --- die Auswahl
      if (selected !== null) {
        const rest = nachRest.hin.get(selected);
        if (rest !== undefined) {
          ansicht.addStyle(
            { chain: chainDnazyme, resi: rest },
            {
              stick: {
                radius: 0.35,
                color: resolveColor("var(--role-result)"),
              },
            },
          );
        }
      }

      // --- Klick in der Ansicht wählt die Position
      if (onPick) {
        ansicht.setClickable({}, true, (atom: any) => {
          if (!atom) return;
          const position = nachRest.rueck.get(atom.resi);
          onPick(position ?? null);
        });
      }

      if (!warBelegt) {
        ansicht.zoomTo();
      }
      ansicht.render();
    }, [
      pdb,
      positions,
      colorMode,
      coreRange,
      cleavageResidue,
      selected,
      chainDnazyme,
      chainSubstrate,
      nachRest,
      onPick,
      bereit,
    ]);

    /* Eine angeklickte Position wird herangeholt. Ohne das liegt sie
     * irgendwo in einem Strang von dreißig Bausteinen, und man sucht genau
     * das, was man gerade ausgewählt hat. */
    useEffect(() => {
      const ansicht = betrachter.current;
      if (!bereit || !ansicht || selected === null) return;
      const rest = nachRest.hin.get(selected);
      if (rest === undefined) return;
      ansicht.zoomTo({ chain: chainDnazyme, resi: rest });
      ansicht.render();
    }, [bereit, selected, chainDnazyme, nachRest]);

    if (fehler) {
      return (
        <div
          className="rounded-lg p-4 text-xs"
          style={{
            border: "1px solid var(--rating-bad)",
            color: "var(--text)",
          }}
        >
          {fehler}
        </div>
      );
    }

    return (
      <div
        ref={halter}
        data-testid="viewer3d"
        className="relative w-full overflow-hidden rounded-lg"
        style={{ height, border: "1px solid var(--border)" }}
      />
    );
  },
);
