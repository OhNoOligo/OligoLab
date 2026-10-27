/* Gemeinsames für die Abnahmetests.
 *
 * Voraussetzung ist immer: das Backend läuft und liefert die gebaute
 * Oberfläche aus.
 *
 *     npm run build
 *     ../.venv/bin/uvicorn app.main:app     # im Projektverzeichnis
 *     npm run e2e
 */

import { existsSync } from "node:fs";
import { chromium } from "playwright";

export const BASE = process.env.OLIGOLAB_URL ?? "http://127.0.0.1:8000";

/* Playwright sucht seinen Browser normalerweise selbst. Wo schon ein Chromium
 * liegt, das nicht zu dieser Playwright-Fassung gehört, kann sein Pfad über
 * CHROMIUM_PATH mitgegeben werden — das spart einen zweiten Download von
 * einigen hundert Megabyte. */
export function launchOptions() {
  const fromEnv = process.env.CHROMIUM_PATH;
  if (fromEnv && existsSync(fromEnv)) return { executablePath: fromEnv };
  return {};
}

export function createChecker() {
  let failed = 0;

  function check(label, actual, expected) {
    const ok = JSON.stringify(actual) === JSON.stringify(expected);
    if (!ok) failed += 1;
    console.log(`${ok ? "ok  " : "FEHL"} ${label}`);
    if (!ok) {
      console.log(`     erwartet: ${JSON.stringify(expected)}`);
      console.log(`     bekommen: ${JSON.stringify(actual)}`);
    }
  }

  return { check, failures: () => failed };
}

export async function openPage(width = 1500, height = 1100) {
  const browser = await chromium.launch(launchOptions());
  const page = await browser.newPage({ viewport: { width, height } });

  const problems = [];
  page.on("pageerror", (error) => problems.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(message.text());
  });

  return { browser, page, problems };
}

export function finish(failed) {
  console.log(
    failed === 0 ? "\nAlle Prüfungen bestanden." : `\n${failed} fehlgeschlagen.`,
  );
  process.exit(failed === 0 ? 0 : 1);
}

/** Setzt das aktive DNAzym über das Feld in der Kopfzeile. */
export async function setOligo(page, sequence) {
  const feld = page.getByLabel("Sequenz des DNAzyms");
  if (await feld.count()) {
    await feld.fill(sequence);
  } else {
    // Ist schon eines gesetzt, zeigt die Kopfzeile den Schnellwechsler statt
    // des Eingabefelds — dann über den Steckbrief.
    await page.keyboard.press("Control+4");
    await page.waitForTimeout(800);
    await page.locator("textarea").fill(sequence);
  }
  await page.waitForTimeout(1500);
}
