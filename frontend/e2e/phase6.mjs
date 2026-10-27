/* Abnahmetest zu Phase 6 (PHASEN.md, Abschnitt 6).
 *
 * Der geforderte Test lautet: „8E9A laden, einen Kandidaten darauf fädeln,
 * In-line-Winkel und Abstände auf Plausibilität prüfen."
 *
 * 8E9A lässt sich hier nicht laden — diese Umgebung kommt nicht an die
 * RCSB-PDB. Geprüft wird deshalb mit `fixtures/TESTREF.pdb`: einer
 * Struktur mit BEKANNTER Geometrie. Das ist für ein Messgerät sogar der
 * bessere Prüfstein, denn bei 8E9A müsste die richtige Antwort erst wieder
 * gemessen werden. Der Weg über das Netz ist derselbe Knopf daneben; was an
 * ihm ungeprüft bleibt, steht im README.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import { BASE, createChecker, finish, openPage, setOligo } from "./support.mjs";

const HIER = dirname(fileURLToPath(import.meta.url));
const STRUKTUR = readFileSync(join(HIER, "fixtures", "TESTREF.pdb"), "utf-8");

/* Dieselbe Sequenz, die auch in der Struktur steht — bis auf zwei LNA und
 * einen ausgetauschten Baustein. */
const KERN = "GGCTAGCTACAACGA";
const DNAZYM = "[LNA-T]TGG" + KERN + "CAT[LNA-G]";

/** Der Winkel, der in der Datei steht. */
const SOLL_WINKEL = 168.0;
const SOLL_ANGRIFF = 3.2;
const SOLL_ABGANG = 1.6;

const { check, failures } = createChecker();
const { browser, page, problems } = await openPage(1600, 1400);

try {
  await page.goto(`${BASE}/steckbrief`, { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  await setOligo(page, DNAZYM);

  await page.goto(`${BASE}/3d`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Modell bauen" }).waitFor({ timeout: 15000 });

  check(
    "ohne geladene Struktur geht es nicht los",
    await page.getByRole("button", { name: "Modell bauen" }).isDisabled(),
    true,
  );

  // ---- Struktur einlegen
  await page.locator('input[type="file"]').setInputFiles({
    name: "TESTREF.pdb",
    mimeType: "chemical/x-pdb",
    buffer: Buffer.from(STRUKTUR, "utf-8"),
  });
  await page.getByText("Kette A: DNAzym").waitFor({ timeout: 15000 });

  check(
    "die Ketten werden zugeordnet",
    await page.evaluate(() => {
      const text = document.querySelector("main")?.textContent ?? "";
      return [text.includes("Kette A: DNAzym"), text.includes("Kette B: Substrat")];
    }),
    [true, true],
  );
  check(
    "Methode und Auflösung kommen aus der Datei",
    (await page.getByRole("main").textContent())?.includes("1.80 Å"),
    true,
  );

  // ---- Modell bauen
  await page.locator("#cut").fill("6");
  await page.getByRole("button", { name: "Modell bauen" }).click();
  await page.getByText("Das ist ein Modell").waitFor({ timeout: 30000 });

  check(
    "der Hinweis steht da, dass es ein Modell ist",
    (await page.getByRole("main").textContent())?.includes(
      "nur die Sequenz ist deine",
    ),
    true,
  );

  // =============================================== der geforderte Test
  const winkel = await page.evaluate(() => {
    const zellen = [...document.querySelectorAll("td")].map(
      (td) => td.textContent?.trim() ?? "",
    );
    const nach = (name) => {
      const index = zellen.indexOf(name);
      return index < 0 ? null : zellen[index + 1];
    };
    const gross = document.querySelector("main")?.textContent ?? "";
    const treffer = gross.match(/(\d+[.,]\d)\s*°/);
    return {
      winkel: treffer ? Number(treffer[1].replace(",", ".")) : null,
      angriff: nach("2'-O bis P"),
      abgang: nach("P bis O5'"),
    };
  });

  check("der In-line-Winkel stimmt", winkel.winkel, SOLL_WINKEL);
  check("der Abstand 2'-O bis P stimmt", winkel.angriff, `${SOLL_ANGRIFF.toFixed(2)} Å`);
  check("der Abstand P bis O5' stimmt", winkel.abgang, `${SOLL_ABGANG.toFixed(2)} Å`);
  check(
    "und wird als günstig bewertet",
    (await page.getByRole("main").textContent())?.includes("nahe an der Linie"),
    true,
  );

  // ---- Abstände der Modifikationen
  check(
    "jede Modifikation bekommt ihre Abstände",
    await page.evaluate(() => {
      const tabelle = [...document.querySelectorAll("table")].find((t) =>
        t.textContent?.includes("zur Spaltstelle"),
      );
      return [...(tabelle?.querySelectorAll("tbody tr") ?? [])].map((tr) => {
        const zellen = [...tr.querySelectorAll("td")].map((td) => td.textContent?.trim());
        return { position: zellen[0], spalt: zellen[1], kern: zellen[2] };
      });
    }),
    /* Die Sollwerte sind nicht geschätzt, sondern unabhängig nachgerechnet
     * (app/geometry.py auf derselben Datei). Position 1 trägt zusätzlich die
     * Ionenwarnung — das Magnesium liegt in der Datei 1,2 Å daneben. */
    [
      { position: "1 T · LNA ▲ MG 1.2 Å", spalt: "20.8 Å", kern: "4 nt · 13.6 Å" },
      { position: "23 G · LNA", spalt: "59.0 Å", kern: "4 nt · 13.6 Å" },
    ],
  );
  check(
    "die Nähe zum Ion ist ein Warnsignal",
    (await page.getByRole("main").textContent())?.includes("Warnsignal"),
    true,
  );

  // =========================================== 6.4 die Ansicht selbst
  check("das 3D-Fenster ist da", await page.getByTestId("viewer3d").count(), 1);
  /* Auf die Leinwand warten, nicht blind zählen: 3Dmol wird erst beim
   * Öffnen der Seite nachgeladen und legt sie danach an. */
  await page
    .locator('[data-testid="viewer3d"] canvas')
    .first()
    .waitFor({ timeout: 20000 });
  check(
    "und zeichnet auf eine Leinwand",
    await page.locator('[data-testid="viewer3d"] canvas').count(),
    1,
  );
  /* Dass eine Leinwand da ist, heißt noch nicht, dass etwas darauf steht:
   * genau so blieb die Ansicht einmal leer, weil 3Dmol erst nach dem
   * Zeichnen fertig geladen war. Geprüft wird darum das Bild selbst. Ein
   * leeres PNG dieser Größe ist rund 2 kB; alles Gezeichnete ist deutlich
   * größer. */
  const gezeichnet = await page.getByTestId("viewer3d").screenshot();
  check("und es steht wirklich etwas darauf", gezeichnet.length > 4000, true);

  check(
    "die Einfärbung ist umschaltbar",
    await page.evaluate(() =>
      [...document.querySelectorAll("option")]
        .map((o) => o.textContent)
        .filter((t) => t?.startsWith("nach ")),
    ),
    ["nach Kette", "nach Bauteil", "nach Modifikation"],
  );
  check(
    "es gibt den Knopf zum Zentrieren",
    await page.getByRole("button", { name: "Auf Spaltstelle zentrieren" }).count(),
    1,
  );

  // Nach dem Umschalten der Einfärbung muss immer noch etwas zu sehen sein.
  await page.selectOption('select[aria-label="Einfärbung"]', "part");
  await page.waitForTimeout(1500);
  const nachUmschalten = await page.getByTestId("viewer3d").screenshot();
  check("auch nach dem Umschalten der Einfärbung", nachUmschalten.length > 4000, true);
  await page.getByRole("button", { name: "Auf Spaltstelle zentrieren" }).click();
  await page.waitForTimeout(1200);
  check(
    "und nach dem Zentrieren",
    (await page.getByTestId("viewer3d").screenshot()).length > 4000,
    true,
  );

  // ---- die Kopplung: Karte und Modell teilen eine Auswahl
  check("die Sequenzkarte liegt daneben", await page.locator("#karte-3d").count(), 1);
  check(
    "noch ist nichts gewählt",
    (await page.getByRole("main").textContent())?.includes("Gewählt: Position"),
    false,
  );

  const zelle = await page.locator("#karte-3d g").filter({ hasText: "G" }).nth(5);
  await zelle.click();
  await page.waitForTimeout(500);

  const auswahl = await page.evaluate(() => {
    const text = document.querySelector("main")?.textContent ?? "";
    const treffer = text.match(/Gewählt: Position (\d+) \(([^)]+)\)/);
    const hervorgehoben = document
      .querySelector("#karte-3d")
      ?.querySelectorAll("rect[stroke-dasharray], rect[data-highlight]").length;
    return { treffer: treffer ? treffer[1] : null, beschreibung: treffer?.[2] ?? null, hervorgehoben };
  });
  check("ein Klick in der Karte wählt eine Position", auswahl.treffer !== null, true);
  check(
    "und die Herkunft der Koordinaten steht dabei",
    auswahl.beschreibung?.includes("Referenz") ||
      auswahl.beschreibung?.includes("Ringgerüst") ||
      auswahl.beschreibung?.includes("Zucker"),
    true,
  );

  // ---- die Herkunft jeder Position
  check(
    "die Zählung der Herkünfte steht am Modell",
    await page.evaluate(() => {
      const text = document.querySelector("main")?.textContent ?? "";
      return ["aus der Referenz", "Ringgerüst", "nur Zucker"].filter((w) =>
        text.includes(w),
      ).length > 0;
    }),
    true,
  );

  // ================================================= 6.3 Messwerkzeug
  await page.locator("#sel").fill("B:6:O2',B:7:P,B:7:O5'");
  await page.getByRole("button", { name: "messen" }).click();
  await page.waitForTimeout(800);
  /* Mit Toleranz, nicht auf die letzte Stelle: die Datei trifft die 168,0
   * nur auf Rundungsgenauigkeit, und die Karte rundet auf eine Stelle,
   * das Messwerkzeug auf zwei. */
  const gemessen = await page.evaluate(() => {
    const text = document.querySelector("main")?.textContent ?? "";
    return Number(/winkel: ([\d.]+) °/.exec(text)?.[1] ?? NaN);
  });
  check(
    "das Messwerkzeug misst denselben Winkel",
    Math.abs(gemessen - SOLL_WINKEL) < 0.05,
    true,
  );

  await page.locator("#sel").fill("B:6:XX,B:7:P");
  await page.getByRole("button", { name: "messen" }).click();
  await page.waitForTimeout(800);
  check(
    "ein unbekanntes Atom gibt keinen Wert, sondern den Grund",
    (await page.getByRole("main").textContent())?.includes(
      "gibt es in dieser Struktur nicht",
    ),
    true,
  );

  // ======================================================= 6.5 ORCA
  await page.getByRole("button", { name: "Fragment schneiden" }).click();
  await page.waitForTimeout(1200);
  const orca = await page.evaluate(() => {
    const text = document.querySelector("main")?.textContent ?? "";
    const pre = document.querySelector("pre")?.textContent ?? "";
    return {
      atome: /(\d+) Atome/.exec(text)?.[1] ?? null,
      hatEingabe: pre.includes("* xyz"),
      sagtNichtsGerechnet: pre.includes("nichts gerechnet"),
      hatVerfahren: pre.includes("r2SCAN-3c"),
    };
  });
  check("das Fragment hat eine Atomzahl", orca.atome !== null, true);
  check("die ORCA-Eingabe wird geschrieben", orca.hatEingabe, true);
  check("sie sagt, dass hier nichts gerechnet wurde", orca.sagtNichtsGerechnet, true);
  check("und trägt das gewählte Verfahren", orca.hatVerfahren, true);

  // ===================================================== 6.6 Bericht
  const [bericht] = await Promise.all([
    page.waitForEvent("popup", { timeout: 30000 }),
    page.getByRole("button", { name: "Bericht erzeugen" }).click(),
  ]);
  await bericht.waitForLoadState("domcontentloaded");
  const inhalt = await bericht.content();
  await bericht.close();

  check(
    "der Bericht fasst alles zusammen",
    ["Sequenz", "Masse", "Punktzahl", "In-line-Winkel", "Befunde"].every((w) =>
      inhalt.includes(w),
    ),
    true,
  );
  check("er trägt die Sequenzkarte als Bild", inhalt.includes("<svg"), true);
  check(
    "und im Fuß stehen Datum und Einstellungen",
    [
      inhalt.includes("Verwendete Einstellungen"),
      inhalt.includes("Reaktionstemperatur"),
      inhalt.includes(
        new Date().toLocaleDateString("de-DE", {
          day: "2-digit", month: "2-digit", year: "numeric",
        }),
      ),
    ],
    [true, true, true],
  );

  check("keine Fehler in der Konsole", problems, []);
} finally {
  await browser.close();
}

finish(failures());
