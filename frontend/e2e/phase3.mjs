/* Abnahmetest zu Phase 3 (PHASEN.md, Abschnitt 3).
 *
 * Der geforderte Test lautet: „Ein DNAzym mit absichtlicher LNA im
 * katalytischen Kern — die kritische Warnung muss erscheinen."
 *
 * Dazu die übrigen Zusagen aus Abschnitt 3.4: die sechs Spuren der
 * Sequenzkarte, beide Richtungen zwischen Karte und Befundliste, Zoom,
 * Export und die Vergleichsansicht.
 */

import { BASE, createChecker, finish, openPage, setOligo } from "./support.mjs";

const MIT_LNA = "TTGGGGTAAGGC[LNA-T]AGCTACAACGAGGTGCATGT";
const OHNE_LNA = "TTGGGGTAAGGCTAGCTACAACGAGGTGCATGT";

const { check, failures } = createChecker();
const { browser, page, problems } = await openPage();

/** Die Beschriftungen der Spuren, von oben nach unten. */
const spuren = () =>
  page.evaluate(() => {
    const svg = document.querySelector('svg[aria-label^="Sequenzkarte"]');
    if (!svg) return [];
    // Die Spurbeschriftungen stehen linksbündig am Rand, als einzige
    // Texte mit text-anchor="end" — bis auf das 5′ über dem Lineal.
    return [...svg.querySelectorAll('text[text-anchor="end"]')]
      .map((t) => t.textContent?.trim())
      .filter((t) => t && t !== "5′");
  });

/** Die Titel der Befunde in der Liste, in ihrer Reihenfolge. */
const befunde = () =>
  page.evaluate(() =>
    [...document.querySelectorAll("li button[aria-pressed]")].map((button) =>
      button.querySelector(".text-sm")?.textContent?.trim(),
    ),
  );

try {
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);

  // ================================================== der geforderte Test
  await setOligo(page, MIT_LNA);
  await page.keyboard.press("Control+3");
  await page.waitForTimeout(2200);

  const liste = await befunde();
  check(
    "LNA im Kern erzeugt den kritischen Befund",
    liste[0],
    "Modifikation im katalytischen Kern: LNA (verbrückte Nukleinsäure)",
  );
  check(
    "die Zählung nennt genau einen kritischen Befund",
    await page
      .locator("text=/1 kritisch/")
      .count()
      .then((n) => n > 0),
    true,
  );

  // ============================================ 3.4 die sechs Spuren
  check("Sequenzkarte vorhanden", await page.locator('svg[aria-label^="Sequenzkarte"]').count(), 1);
  check("sechs Spuren in dieser Reihenfolge", await spuren(), [
    "Position",
    "Bausteine",
    "Bauteile",
    "Faltung",
    "ungepaart",
    "Befunde",
  ]);

  const karte = await page.evaluate(() => {
    const svg = document.querySelector('svg[aria-label^="Sequenzkarte"]');
    return {
      bausteine: svg.querySelectorAll("g > rect + text").length,
      bauteile: [...svg.querySelectorAll("text")]
        .map((t) => t.textContent)
        .filter((t) => ["5'-Arm", "Katalytischer Kern", "3'-Arm"].includes(t)),
      boegen: svg.querySelectorAll("path").length,
    };
  });
  check("Bauteilspur beschriftet", karte.bauteile, [
    "5'-Arm",
    "Katalytischer Kern",
    "3'-Arm",
  ]);
  check("Bogendiagramm gezeichnet", karte.boegen > 0, true);

  // ===================================== beide Richtungen Karte <-> Liste
  await page.locator("li button[aria-pressed]").first().click();
  await page.waitForTimeout(400);
  const hervorhebung = await page.evaluate(() => {
    const svg = document.querySelector('svg[aria-label^="Sequenzkarte"]');
    const rect = svg.querySelector('rect[stroke="var(--role-result)"]');
    return rect ? Number(rect.getAttribute("width")) : null;
  });
  check(
    "Klick auf den Befund hebt genau eine Position hervor",
    hervorhebung,
    15, // eine Zelle bei der Voreinstellung
  );

  await page.locator("li button[aria-pressed]").first().click(); // lösen
  await page.waitForTimeout(300);
  await page
    .locator('svg[aria-label^="Sequenzkarte"] rect[fill="var(--rating-bad)"]')
    .first()
    .click();
  await page.waitForTimeout(500);
  check(
    "Klick auf den Warnmarker wählt den Befund",
    await page.locator('li button[aria-pressed="true"]').count(),
    1,
  );

  // =============================================================== Zoom
  await page.getByLabel("Zellbreite der Sequenzkarte").fill("28");
  await page.waitForTimeout(500);
  check(
    "Zoom ändert die Breite",
    await page.evaluate(() =>
      Number(
        document
          .querySelector('svg[aria-label^="Sequenzkarte"]')
          .getAttribute("width"),
      ),
    ),
    92 + 33 * 28 + 16,
  );
  await page.getByLabel("Zellbreite der Sequenzkarte").fill("15");
  await page.waitForTimeout(400);

  // ============================================================= Export
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "SVG", exact: true }).click();
  const datei = await download;
  const { readFileSync } = await import("node:fs");
  const svgText = readFileSync(await datei.path(), "utf8");
  check("SVG-Export beginnt mit der XML-Zeile", svgText.startsWith("<?xml"), true);
  check(
    "im Export sind alle CSS-Variablen aufgelöst",
    (svgText.match(/var\(/g) ?? []).length,
    0,
  );
  check("der Export enthält echte Farben", /#[0-9a-f]{6}|rgb\(/i.test(svgText), true);

  // =================================================== Vergleichsansicht
  await page.getByRole("button", { name: /aktuellen Strang festhalten/ }).click();
  await page.waitForTimeout(600);

  // Der einzige Weg, die Sequenz zu ändern, führt aus dem Bereich heraus —
  // die festgehaltene Variante muss das überstehen.
  await setOligo(page, OHNE_LNA);
  await page.keyboard.press("Control+3");
  await page.waitForTimeout(2600);

  const breiten = await page.evaluate(() =>
    [...document.querySelectorAll('svg[aria-label^="Sequenzkarte"]')].map((svg) =>
      Number(svg.getAttribute("width")),
    ),
  );
  check("drei Karten: oben plus zwei im Vergleich", breiten.length, 3);
  check(
    "alle Karten gleich breit, also fluchtend",
    new Set(breiten).size,
    1,
  );

  // Die Variante überlebt auch ein Neuladen.
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(2800);
  check(
    "der Vergleich übersteht das Neuladen",
    await page.locator('svg[aria-label^="Sequenzkarte"]').count(),
    3,
  );

  // Ohne LNA darf kein kritischer Befund mehr stehen.
  const jetzt = await befunde();
  check(
    "ohne LNA kein Befund zum katalytischen Kern",
    jetzt.some((titel) => titel?.includes("katalytischen Kern")),
    false,
  );

  check("keine Fehler in der Konsole", problems, []);
} finally {
  await browser.close();
}

finish(failures());
