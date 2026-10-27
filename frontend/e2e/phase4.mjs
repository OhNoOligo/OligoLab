/* Abnahmetest zu Phase 4 (PHASEN.md, Abschnitt 4).
 *
 * Der geforderte Test lautet: „Transkript von etwa 500 Basen; das
 * Zugänglichkeitsprofil muss an bekannten Haarnadeln einbrechen."
 *
 * Dazu die übrigen Zusagen aus Abschnitt 4.4: Sequenztext mit Lineal und
 * Suchfeld, die Spurdarstellung wie in Phase 3, Übersichtsleiste und
 * Bereichsauswahl, und der Knopf „Spaltstellen suchen".
 */

import { BASE, createChecker, finish, openPage } from "./support.mjs";

/* Ein Transkript, dessen Struktur man kennt: zehnmal ein offener Abschnitt
 * von 26 Basen und eine Haarnadel von 22. Zusammen 480 Basen. */
const HAARNADEL = "GGGGGCCCCTTTTGGGGCCCCC";
const OFFEN = "AAAAAAAAAAAAAAAAAAAAAAAAAA";
const TRANSKRIPT = (OFFEN + HAARNADEL).repeat(10);

const { check, failures } = createChecker();
const { browser, page, problems } = await openPage(1500, 1200);

/** Die Spurbeschriftungen der Zielkarte, von oben nach unten. */
const spuren = () =>
  page.evaluate(() => {
    const svg = document.querySelector('svg[aria-label^="Zielkarte"]');
    if (!svg) return [];
    return [...svg.querySelectorAll('text[text-anchor="end"]')]
      .map((t) => t.textContent?.trim())
      .filter((t) => t && !["5′", "1,0 offen", "0"].includes(t));
  });

const gewaehlterBereich = () =>
  page.evaluate(() => {
    const label = document
      .querySelector('svg[aria-label^="Zielkarte"]')
      ?.getAttribute("aria-label");
    const treffer = label?.match(/Position (\d+) bis (\d+)/);
    return treffer ? [Number(treffer[1]), Number(treffer[2])] : null;
  });

try {
  await page.goto(`${BASE}/ziel`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);

  check(
    "ohne Ziel steht ein Eingabefeld da",
    await page.locator("textarea").count(),
    1,
  );

  // ---- Sequenz übernehmen
  await page.locator("textarea").fill(TRANSKRIPT);
  await page.getByRole("button", { name: "übernehmen" }).click();
  await page.waitForTimeout(2600);

  check(
    "die Kopfzeile kennt das Ziel",
    (await page.getByRole("banner").textContent())?.includes("480 nt"),
    true,
  );
  check(
    "DNA wurde stillschweigend zu RNA",
    (await page.locator("div.ol-mono").first().textContent())?.includes("U"),
    true,
  );

  // ==================================================== der geforderte Test
  //
  // Das Profil liegt im SVG als Flächendiagramm. Statt Pixel zu messen wird
  // es direkt beim Backend geholt — geprüft werden soll die Rechnung, nicht
  // die Rundung des Renderers.
  const profil = await page.evaluate(async (sequenz) => {
    const antwort = await fetch("/api/target/accessibility", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sequence: sequenz, probe_length: 15 }),
    });
    return antwort.json();
  }, TRANSKRIPT);

  const offeneMitten = Array.from({ length: 10 }, (_, i) => i * 48 + 5);
  const haarnadelMitten = Array.from({ length: 10 }, (_, i) => i * 48 + 28);
  const wert = (p) => profil.profile[p - 1];

  check(
    "das Profil deckt die ganze Länge ab",
    profil.profile.length,
    TRANSKRIPT.length,
  );
  check(
    "offene Abschnitte sind zugänglich",
    offeneMitten.every((p) => wert(p) > 0.5),
    true,
  );
  check(
    "das Profil bricht an den Haarnadeln ein",
    haarnadelMitten.every((p) => wert(p) < 0.01),
    true,
  );
  check(
    "der Unterschied ist Größenordnungen, kein Rauschen",
    Math.min(...offeneMitten.map(wert)) /
      Math.max(1e-12, Math.max(...haarnadelMitten.map(wert))) >
      100,
    true,
  );

  // ============================================= 4.4 die Spurdarstellung
  check("Übersichtsleiste vorhanden", await page.locator('svg[aria-label^="Übersicht"]').count(), 1);
  check("Zielkarte vorhanden", await page.locator('svg[aria-label^="Zielkarte"]').count(), 1);
  check("die Spuren in dieser Reihenfolge", await spuren(), [
    "Position",
    "Abschnitte",
    "Faltung",
    "zugänglich",
    "Spaltstellen",
  ]);
  check(
    "das Zugänglichkeitsprofil ist ein Flächendiagramm",
    await page.evaluate(
      () =>
        document.querySelector('svg[aria-label^="Zielkarte"]').querySelectorAll("polygon")
          .length > 0,
    ),
    true,
  );
  check(
    "die Faltung wird als Bogendiagramm gezeichnet",
    await page.evaluate(
      () =>
        document.querySelector('svg[aria-label^="Zielkarte"]').querySelectorAll("path")
          .length > 0,
    ),
    true,
  );

  // ================================================== Bereich auswählen
  const vorher = await gewaehlterBereich();
  const leiste = await page.locator('svg[aria-label^="Übersicht"]').boundingBox();
  await page.mouse.move(leiste.x + leiste.width * 0.6, leiste.y + leiste.height / 2);
  await page.mouse.down();
  await page.mouse.move(leiste.x + leiste.width * 0.8, leiste.y + leiste.height / 2, {
    steps: 8,
  });
  await page.mouse.up();
  await page.waitForTimeout(2200);
  const nachher = await gewaehlterBereich();

  check("Ziehen in der Übersicht wählt einen Bereich", nachher !== null, true);
  check(
    "und zwar einen anderen als vorher",
    JSON.stringify(vorher) !== JSON.stringify(nachher),
    true,
  );
  check(
    "der Bereich liegt im Transkript",
    nachher[0] >= 1 && nachher[1] <= 480 && nachher[0] < nachher[1],
    true,
  );

  // ========================================================= Suchfeld
  await page.getByLabel("Im Ziel suchen").fill("GGGGG");
  await page.waitForTimeout(600);
  check(
    "die Suche hebt Treffer hervor",
    (await page.locator('span[style*="rating-warn"]').count()) > 0,
    true,
  );
  await page.getByLabel("Im Ziel suchen").fill("");

  // ================================================= Übergabe in Phase 5
  check(
    "der Knopf „Spaltstellen suchen“ führt weiter",
    await page.getByRole("button", { name: /Spaltstellen suchen/ }).count(),
    1,
  );
  await page.getByRole("button", { name: /Spaltstellen suchen/ }).click();
  await page.waitForTimeout(700);
  check("er landet im Entwurf", new URL(page.url()).pathname, "/entwurf");

  // Das Ziel bleibt gesetzt — der Zustand aus Phase 2 trägt es.
  await page.goto(`${BASE}/ziel`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2200);
  check(
    "das Ziel übersteht den Wechsel",
    (await page.getByRole("banner").textContent())?.includes("480 nt"),
    true,
  );

  check("keine Fehler in der Konsole", problems, []);
} finally {
  await browser.close();
}

finish(failures());
