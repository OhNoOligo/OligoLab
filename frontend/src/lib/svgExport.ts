/* Die Sequenzkarte als SVG und PNG ausgeben (PHASEN.md 3.4).
 *
 * Ein Haken: die Karte faerbt sich ueber CSS-Variablen (`var(--mod-dna)` und
 * so weiter). Die stehen im Stylesheet der Seite, nicht im SVG. Eine
 * herausgeloeste Datei waere darum schwarz-weiss oder unsichtbar. Vor dem
 * Export werden sie deshalb durch ihre errechneten Werte ersetzt.
 *
 * Dasselbe gilt fuer die Schrift: `font-family` steht am <svg>, aber die
 * Variable darin muss aufgeloest werden, sonst faellt die Datei auf eine
 * Standardschrift zurueck und die Zellen sitzen nicht mehr.
 */

const VAR_PATTERN = /var\(\s*(--[\w-]+)\s*(?:,[^)]*)?\)/g;

const COLOR_ATTRIBUTES = ["fill", "stroke", "color"] as const;

function resolveVariables(value: string, styles: CSSStyleDeclaration): string {
  return value.replace(VAR_PATTERN, (_match, name: string) => {
    const resolved = styles.getPropertyValue(name).trim();
    // Eine Variable, die es nicht gibt, lieber sichtbar lassen als die Datei
    // mit einem kaputten Wert zu schreiben.
    return resolved || "currentColor";
  });
}

/** Eine Kopie des SVG, in der alle CSS-Variablen aufgeloest sind. */
export function withInlinedVariables(svg: SVGSVGElement): SVGSVGElement {
  const styles = window.getComputedStyle(document.documentElement);
  const clone = svg.cloneNode(true) as SVGSVGElement;

  const alle = [clone, ...Array.from(clone.querySelectorAll("*"))];
  for (const element of alle) {
    for (const attribute of COLOR_ATTRIBUTES) {
      const value = element.getAttribute(attribute);
      if (value && value.includes("var(")) {
        element.setAttribute(attribute, resolveVariables(value, styles));
      }
    }
    const inline = element.getAttribute("style");
    if (inline && inline.includes("var(")) {
      element.setAttribute("style", resolveVariables(inline, styles));
    }
  }

  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  return clone;
}

function serialize(svg: SVGSVGElement): string {
  return new XMLSerializer().serializeToString(withInlinedVariables(svg));
}

function download(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  // Erst freigeben, wenn der Browser den Download begonnen hat.
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function exportSvg(svg: SVGSVGElement, filename: string): void {
  const text = `<?xml version="1.0" encoding="UTF-8"?>\n${serialize(svg)}`;
  download(new Blob([text], { type: "image/svg+xml;charset=utf-8" }), filename);
}

/**
 * Als PNG. `scale` ist die Vergroesserung gegenueber der Bildschirmgroesse;
 * 2 ergibt ein Bild, das auch gedruckt noch scharf ist.
 */
export async function exportPng(
  svg: SVGSVGElement,
  filename: string,
  scale = 2,
): Promise<void> {
  const text = serialize(svg);
  const width = Number(svg.getAttribute("width")) || svg.clientWidth;
  const height = Number(svg.getAttribute("height")) || svg.clientHeight;

  const url = URL.createObjectURL(
    new Blob([text], { type: "image/svg+xml;charset=utf-8" }),
  );

  try {
    const bild = await new Promise<HTMLImageElement>((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error("Das SVG ließ sich nicht laden."));
      image.src = url;
    });

    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(width * scale));
    canvas.height = Math.max(1, Math.round(height * scale));
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Kein 2D-Kontext verfügbar.");

    context.scale(scale, scale);
    context.drawImage(bild, 0, 0);

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/png"),
    );
    if (!blob) throw new Error("Das PNG ließ sich nicht erzeugen.");
    download(blob, filename);
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** Dateiname aus einem Oligonamen, ohne Zeichen, die Dateisysteme stören. */
export function safeFilename(name: string, extension: string): string {
  const basis =
    name
      .trim()
      .replace(/[^\w\s-]/g, "")
      .replace(/\s+/g, "-")
      .slice(0, 60) || "oligolab-sequenzkarte";
  return `${basis}.${extension}`;
}
