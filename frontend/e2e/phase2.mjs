/* Abnahmetest zu Phase 2 (PHASEN.md, Abschnitt 2).
 *
 * Der geforderte Test lautet: „Oligo im Steckbrief ändern und prüfen, dass
 * alle anderen Bereiche ihre Ergebnisse als veraltet markieren."
 *
 * Dazu die übrigen Zusagen aus Abschnitt 2: Kopfzeile, Tastaturkürzel,
 * Übergaben, Fragezeichen-Hilfe, Glossarseite und die Spiegelung in
 * localStorage.
 *
 * Voraussetzung: das Backend läuft und liefert die gebaute Oberfläche aus.
 *
 *     npm run build
 *     ../.venv/bin/uvicorn app.main:app     # im Projektverzeichnis
 *     npm run e2e
 */

import { existsSync } from "node:fs";
import { chromium } from "playwright";

const BASE = process.env.OLIGOLAB_URL ?? "http://127.0.0.1:8000";

/* Playwright sucht seinen Browser normalerweise selbst. Wo schon ein
 * Chromium liegt, das nicht zu dieser Playwright-Fassung gehoert, kann sein
 * Pfad ueber CHROMIUM_PATH mitgegeben werden — das spart einen zweiten
 * Download von einigen hundert Megabyte. */
function launchOptions() {
  const fromEnv = process.env.CHROMIUM_PATH;
  if (fromEnv && existsSync(fromEnv)) return { executablePath: fromEnv };
  return {};
}

let failed = 0;

function check(label, actual, expected) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (!ok) failed += 1;
  const mark = ok ? "ok  " : "FEHL";
  console.log(`${mark} ${label}`);
  if (!ok) {
    console.log(`     erwartet: ${JSON.stringify(expected)}`);
    console.log(`     bekommen: ${JSON.stringify(actual)}`);
  }
}

/** Der Stand jedes Bereichs, so wie die Seitenleiste ihn zeigt. */
const areaStatus = (page) =>
  page.evaluate(() => {
    const out = {};
    document
      .querySelectorAll('nav[aria-label="Bereiche"] button')
      .forEach((button) => {
        const label = button.querySelector(".flex-1")?.textContent?.trim();
        const dot = button.querySelector(".ol-status-dot");
        if (label && dot?.getAttribute("title")) {
          out[label] = dot.getAttribute("title");
        }
      });
    return out;
  });

const browser = await chromium.launch(launchOptions());
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });

const problems = [];
page.on("pageerror", (error) => problems.push(error.message));
page.on("console", (message) => {
  if (message.type() === "error") problems.push(message.text());
});

try {
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);

  // --- 2.2 Kopfzeile: ohne Oligo ein Eingabefeld, keine leere Zeile
  check(
    "Kopfzeile bietet ein Eingabefeld, solange nichts gesetzt ist",
    await page.getByLabel("Sequenz des DNAzyms").count(),
    1,
  );

  // --- 2.3 Alle fünf Bereiche sind leer
  check("alle fünf Bereiche starten leer", await areaStatus(page), {
    Ziel: "leer",
    Entwurf: "leer",
    Strang: "leer",
    Steckbrief: "leer",
    "3D": "leer",
  });

  // --- Beispielsequenz laden: der Steckbrief rechnet
  await page.getByRole("button", { name: "Beispielsequenz laden" }).click();
  await page.waitForTimeout(1400);
  check(
    "Steckbrief rechnet nach dem Laden",
    (await areaStatus(page)).Steckbrief,
    "berechnet",
  );

  // --- 2.4 Übergabe Strang -> Steckbrief
  await page.getByRole("button", { name: "Strang" }).first().click();
  await page.waitForTimeout(400);
  await page.getByRole("button", { name: /Masse und MS berechnen/ }).click();
  await page.waitForTimeout(1400);
  check(
    "Übergabe trägt in den Steckbrief und vermerkt den Strang",
    (await areaStatus(page)).Strang,
    "berechnet",
  );

  // --- DER TEST aus PHASEN.md: Oligo ändern macht abgeleitete Stände ungültig
  await page
    .locator("textarea")
    .fill("TTG GGG TAA GGC TAG CTA CAA CGA GGT GCA TG");
  await page.waitForTimeout(1500);
  const nachAenderung = await areaStatus(page);
  check(
    "Oligo geändert: der Strang ist veraltet",
    nachAenderung.Strang,
    "veraltet",
  );
  check(
    "Oligo geändert: der Steckbrief hat live nachgerechnet",
    nachAenderung.Steckbrief,
    "berechnet",
  );

  // --- 2.1 Niemand kopiert Sequenzen: die Kopfzeile zeigt dieselbe Länge
  const kopfzeile = await page.getByRole("banner").textContent();
  check(
    "Kopfzeile folgt der geänderten Sequenz",
    kopfzeile.includes("32 nt"),
    true,
  );

  // --- 2.3 Tastaturkürzel
  await page.keyboard.press("Control+1");
  await page.waitForTimeout(400);
  check("Strg+1 öffnet Ziel", new URL(page.url()).pathname, "/ziel");
  await page.keyboard.press("Control+5");
  await page.waitForTimeout(400);
  check("Strg+5 öffnet 3D", new URL(page.url()).pathname, "/3d");

  // --- 2.6 Fragezeichen-Hilfe
  await page.keyboard.press("Control+4");
  await page.waitForTimeout(900);
  const tip = page.getByRole("button", {
    name: /Hilfe zu vollständig entschützt/,
  });
  check("Fragezeichen neben der Ergebniszahl", await tip.count(), 1);
  check(
    "aria-describedby ist gesetzt",
    Boolean(await tip.getAttribute("aria-describedby")),
    true,
  );
  await tip.click();
  await page.waitForTimeout(300);
  check("Klick öffnet das Panel", await page.getByRole("dialog").count(), 1);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(250);
  check("Escape schließt das Panel", await page.getByRole("dialog").count(), 0);

  // --- 2.6 Glossarseite, direkt aufgerufen
  await page.goto(`${BASE}/hilfe`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  const eintraege = await page.locator("dt").count();
  check("/hilfe listet Einträge", eintraege > 30, true);
  await page.getByLabel("Hilfe durchsuchen").fill("phosphoro");
  await page.waitForTimeout(400);
  const gefiltert = await page.locator("dt").count();
  check("Suche grenzt ein", gefiltert > 0 && gefiltert < eintraege, true);

  // --- 2.1 Spiegelung: ein Neuladen verliert nichts
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForTimeout(1300);
  check(
    "Neuladen behält die Sequenz",
    (await page.locator("textarea").inputValue()).startsWith("TTG GGG TAA"),
    true,
  );
  check(
    "Neuladen behält die Stände",
    (await areaStatus(page)).Strang,
    "veraltet",
  );

  check("keine Fehler in der Konsole", problems, []);
} finally {
  await browser.close();
}

console.log(failed === 0 ? "\nAlle Prüfungen bestanden." : `\n${failed} fehlgeschlagen.`);
process.exit(failed === 0 ? 0 : 1);
