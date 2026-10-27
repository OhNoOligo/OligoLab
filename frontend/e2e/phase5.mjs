/* Abnahmetest zu Phase 5 (PHASEN.md, Abschnitt 5).
 *
 * Der geforderte Test: „Ein Transkript mit einer bekannten guten
 * Spaltstelle; die muss weit oben in der Rangliste stehen." Dazu die
 * Zusagen aus 5.6 — Einstellungen, sortierbare Tabelle mit Ampel je Zeile,
 * das Profil mit Kandidatenmarken, die Paarungsdarstellung, „Als Oligo
 * übernehmen", CSV und SVG, und der sichtbare Hinweis aus 5.4.
 */

import { BASE, createChecker, finish, openPage } from "./support.mjs";

/* Dasselbe Transkript wie im pytest-Fall: in der Mitte ein offener
 * Abschnitt mit einer GU-Junktion, links und rechts stabile Haarnadeln,
 * deren Junktionen verschlossen sind. */
const OFFEN_LINKS = "ACACCACACCACAC";
const OFFEN_RECHTS = "ACCACACCACACCA";
const HAARNADEL = "GGGGGCCCCTTTTGGGGCCCCC";
const FUELLER = "AAAAAAAA";
const TRANSKRIPT =
  HAARNADEL + FUELLER + OFFEN_LINKS + "GT" + OFFEN_RECHTS + FUELLER + HAARNADEL;
/** 1-basierte Position des G in der bekannten guten Junktion. */
const GUTE_STELLE = HAARNADEL.length + FUELLER.length + OFFEN_LINKS.length + 1;

const { check, failures } = createChecker();
const { browser, page, problems } = await openPage(1600, 1300);

const zeilen = () =>
  page.evaluate(() => {
    const tabelle = [...document.querySelectorAll("table")].find((t) =>
      t.textContent?.includes("/"),
    );
    if (!tabelle) return [];
    return [...tabelle.querySelectorAll("tbody tr")].map((tr) => {
      const zellen = [...tr.querySelectorAll("td")].map((td) =>
        td.textContent?.trim(),
      );
      return {
        ampel: zellen[0],
        position: Number(zellen[1]?.split("/")[0]),
        punktzahl: Number(zellen[7]),
      };
    });
  });

try {
  // ---- Ziel setzen
  await page.goto(`${BASE}/ziel`, { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  await page.locator("textarea").fill(TRANSKRIPT);
  await page.getByRole("button", { name: "übernehmen" }).click();
  // Auf den Zustand warten, nicht auf die Uhr: steht das Ziel noch nicht im
  // Speicher, zeigt die Entwurfsseite ihre leere Karte.
  await page.getByRole("banner").getByText("90 nt").waitFor({ timeout: 15000 });

  // ---- Entwurfsseite
  await page.goto(`${BASE}/entwurf`, { waitUntil: "networkidle" });
  await page
    .getByRole("button", { name: "Kandidaten suchen" })
    .waitFor({ timeout: 15000 });

  /* Nicht auf den exakten Text prüfen: am Label hängt das Fragezeichen der
   * Hilfe, und der Textinhalt lautet damit „5'-Arm?". Geprüft wird, dass das
   * Feld da ist UND seine Hilfe hat — CLAUDE.md verlangt an jedem Feld ein
   * `data-help`. */
  check(
    "die Einstellungen stehen oben",
    await page.evaluate(() => {
      const felder = ["field.arm5", "field.arm3", "field.arm_dg_target"];
      return felder.every(
        (id) =>
          !!document.querySelector(`[data-help="${id}"]`) &&
          !!document.getElementById(id.replace("field.", "").replace("arm_dg_target", "dg")),
      );
    }),
    true,
  );
  check(
    "und jedes Feld hat seine Hilfe",
    await page.evaluate(
      () =>
        [...document.querySelectorAll("[data-help^='field.']")].length >= 8 &&
        document.querySelectorAll("button[aria-label^='Hilfe']").length > 0,
    ),
    true,
  );
  check(
    "der Hinweis aus 5.4 ist noch nicht im Weg",
    await page.getByText("Rangfolge", { exact: false }).count(),
    0,
  );

  await page.getByRole("button", { name: "Kandidaten suchen" }).click();
  await page.waitForTimeout(9000);

  // ================================================== der geforderte Test
  const rangliste = await zeilen();
  check("es gibt Kandidaten", rangliste.length > 0, true);
  check(
    "die bekannte gute Stelle steht auf Rang 1",
    rangliste[0]?.position,
    GUTE_STELLE,
  );
  check("und bekommt grün", rangliste[0]?.ampel, "●gut");

  // ===================================================== 5.6 die Tabelle
  check(
    "jede Zeile trägt eine Ampel",
    rangliste.every((z) => ["●gut", "▲mittel", "■schwach"].includes(z.ampel)),
    true,
  );
  check(
    "der Hinweis aus 5.4 steht jetzt sichtbar da",
    (await page.getByRole("main").textContent())?.includes(
      "keine Vorhersage",
    ) ||
      (await page.getByRole("main").textContent())?.includes("Rangfolge"),
    true,
  );

  // Sortieren: nach Position ist Rang 1 nicht mehr unbedingt vorn.
  await page.getByRole("button", { name: "Position" }).click();
  await page.waitForTimeout(400);
  const nachPosition = await zeilen();
  check(
    "nach Position sortiert heißt aufsteigend",
    nachPosition.map((z) => z.position).every((p, i, a) => i === 0 || a[i - 1] <= p),
    true,
  );
  await page.getByRole("button", { name: "Punktzahl" }).click();
  await page.waitForTimeout(400);
  const nachPunkten = await zeilen();
  check(
    "nach Punktzahl sortiert heißt absteigend",
    nachPunkten.map((z) => z.punktzahl).every((p, i, a) => i === 0 || a[i - 1] >= p),
    true,
  );

  // Filtern
  const alle = (await zeilen()).length;
  await page.getByText("nur grüne").click();
  await page.waitForTimeout(400);
  const nurGruen = await zeilen();
  check("der Filter lässt nur grüne übrig", nurGruen.every((z) => z.ampel === "●gut"), true);
  check("und blendet etwas aus", nurGruen.length <= alle, true);
  await page.getByText("nur grüne").click();
  await page.waitForTimeout(400);

  // ======================================================= 5.6 das Profil
  check(
    "das Profil ist da",
    await page.locator('svg[aria-label^="Zugänglichkeitsprofil"]').count(),
    1,
  );
  check(
    "die Kandidaten stehen als Marken darin",
    await page.evaluate(
      () =>
        document
          .querySelector('svg[aria-label^="Zugänglichkeitsprofil"]')
          .querySelectorAll("circle").length,
    ),
    rangliste.length,
  );

  // ============================================ 5.6 Paarungsdarstellung
  const paarung = 'svg[aria-label^="Paarung des Kandidaten"]';
  check("die Paarungsdarstellung ist da", await page.locator(paarung).count(), 1);

  const bild = await page.evaluate((auswahl) => {
    const svg = document.querySelector(auswahl);
    const texte = [...svg.querySelectorAll("text")];
    const zahlen = (t) => ({
      text: t.textContent?.trim(),
      y: Number(t.getAttribute("y")),
      fill: t.getAttribute("fill"),
    });
    const basen = texte.map(zahlen).filter((t) => /^[ACGTU]$/.test(t.text));
    const reihen = [...new Set(basen.map((b) => b.y))].sort((a, b) => a - b);
    const oben = basen.filter((b) => b.y === reihen[0]);
    return {
      zeilen: reihen.length,
      zielIstRna: oben.every((b) => b.fill === "var(--mod-rna)"),
      zielHatU: oben.some((b) => b.text === "U"),
      zielOhneT: oben.every((b) => b.text !== "T"),
      striche: svg.querySelectorAll("line").length,
      pfade: svg.querySelectorAll("path").length,
      enden: texte.map((t) => t.textContent?.trim()).filter((t) => t === "5′" || t === "3′"),
      kernbeschriftung: texte.some((t) => t.textContent?.trim() === "Kern"),
      pfeil: !!svg.querySelector('line[marker-end]'),
    };
  }, paarung);

  check("Ziel oben, Strang darunter, Kern als dritte Reihe", bild.zeilen >= 3, true);
  check("das Ziel ist RNA und in Blau", [bild.zielIstRna, bild.zielHatU, bild.zielOhneT], [true, true, true]);
  check("Basenpaare als senkrechte Striche", bild.striche > 10, true);
  check("der Kern ist eine Schleife", [bild.pfade > 0, bild.kernbeschriftung], [true, true]);
  check("die Spaltstelle trägt einen Pfeil", bild.pfeil, true);
  check(
    "beide Stränge sind an beiden Enden beschriftet",
    bild.enden.length,
    4,
  );

  // Die Reihenfolge der Enden: oben 5'…3', unten 3'…5' (gegenläufig).
  check("der Strang läuft gegenläufig zum Ziel", bild.enden, ["5′", "3′", "3′", "5′"]);

  // ================================================ 5.5 Modifikationen
  await page.locator("#pat").selectOption("lna_ends");
  await page.getByRole("button", { name: "aufbringen" }).click();
  await page.waitForTimeout(3000);

  const vergleich = await page.evaluate(() => {
    const tabelle = [...document.querySelectorAll("table")].find((t) =>
      t.textContent?.includes("Masse, entschützt"),
    );
    if (!tabelle) return null;
    const werte = {};
    for (const tr of tabelle.querySelectorAll("tbody tr")) {
      const zellen = [...tr.querySelectorAll("td")].map((td) => td.textContent?.trim());
      werte[zellen[0]] = { vorher: zellen[1], nachher: zellen[2], diff: zellen[3] };
    }
    return werte;
  });

  check("es gibt eine Vorher-Nachher-Tabelle", vergleich !== null, true);
  check(
    "die Masse steigt um sechs LNA",
    Math.round(
      (Number(vergleich["Masse, entschützt"].nachher) -
        Number(vergleich["Masse, entschützt"].vorher)) *
        10,
    ) / 10,
    72,
  );
  check(
    "der Tm bleibt gleich",
    vergleich["Tm 5'-Arm"].diff,
    "unverändert",
  );
  check(
    "und die Seite sagt, warum er gleich bleibt",
    (await page.getByRole("main").textContent())?.includes(
      "das Modell sieht es nicht",
    ),
    true,
  );
  /* Die Farbe wird nicht aus dem Namen des Tokens geraten — der Name stand
   * schon einmal falsch da. Geprüft wird die aufgelöste Farbe, und zwar
   * gegen die, die die Legende der Zuckermodifikation gibt: in allen
   * Ansichten dieselbe (CLAUDE.md, Designsprache). */
  const farben = await page.evaluate((auswahl) => {
    const wurzel = getComputedStyle(document.documentElement);
    const zucker = wurzel.getPropertyValue("--mod-sugar").trim();
    const dna = wurzel.getPropertyValue("--mod-dna").trim();
    const svg = document.querySelector(auswahl);
    const gefaerbt = [...svg.querySelectorAll("text")]
      .filter((t) => /^[ACGT]$/.test(t.textContent?.trim() ?? ""))
      .map((t) => getComputedStyle(t).fill);
    const alsRgb = (wert) => {
      const probe = document.createElement("span");
      probe.style.color = wert;
      document.body.appendChild(probe);
      const aufgeloest = getComputedStyle(probe).color;
      probe.remove();
      return aufgeloest;
    };
    return {
      zucker: gefaerbt.filter((f) => f === alsRgb(zucker)).length,
      dna: gefaerbt.filter((f) => f === alsRgb(dna)).length,
    };
  }, paarung);
  check(
    "die sechs LNA stehen in der Farbe der Zuckermodifikation",
    farben.zucker,
    6,
  );
  // 33 Bausteine, sechs davon LNA: 12 unveränderte Armzellen plus die 15
  // Buchstaben auf der Kernschleife.
  check("der Rest bleibt DNA-grau", farben.dna, 27);

  /* Regression: eine aufgebrachte Modifikation gehört zu GENAU einem
   * Kandidaten. Wird über eine Marke im Profil ein anderer gewählt, zeigte
   * die Paarungsdarstellung sonst den alten Strang unter der neuen
   * Überschrift. */
  const marken = await page.$$('svg[aria-label^="Zugänglichkeitsprofil"] g');
  await marken[marken.length - 1].click();
  await page.waitForTimeout(2500);
  check(
    "ein Wechsel über das Profil nimmt die Modifikation mit",
    await page.evaluate(() => {
      const abschnitt = [...document.querySelectorAll("section")].find((s) =>
        s.querySelector("h2")?.textContent?.startsWith("Paarung an"),
      );
      // NICHT im ganzen Abschnitt suchen: „LNA" steht auch in der
      // Auswahlliste der Muster und wäre dort immer zu finden.
      const sequenzzeile = abschnitt?.querySelector("p.ol-mono");
      return [
        sequenzzeile?.textContent?.trim() ?? null,
        abschnitt?.querySelector("header p")?.textContent?.trim() ?? null,
      ];
    }),
    [null, null],
  );
  // Zurück zum besten Kandidaten.
  await page.getByRole("button", { name: "Punktzahl" }).click();
  await page.waitForTimeout(400);
  await page.locator("tbody tr").first().click();
  await page.waitForTimeout(2000);

  // Der Kern: ein Eingriff dort muss blockiert werden (CLAUDE.md, Regel 6).
  await page.waitForTimeout(600);
  const blockiert = await page.evaluate(async () => {
    const antwort = await fetch("/api/modify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sequence: "TTGGGGTAAGGCTAGCTACAACGAGGTGCATGT",
        pattern: "replace_position",
        position: 13,
        code: "LNA",
      }),
    });
    return antwort.json();
  });
  check(
    "ein Eingriff im Kern wird auch ohne mitgeschickten Kern blockiert",
    [blockiert.modification.blocked, blockiert.modification.sequence],
    [true, "TTGGGGTAAGGCTAGCTACAACGAGGTGCATGT"],
  );

  // ======================================================= 5.6 Ausgaben
  check("CSV-Knopf vorhanden", await page.getByRole("button", { name: "CSV" }).count(), 1);
  check("SVG-Knöpfe vorhanden", await page.getByRole("button", { name: "SVG" }).count(), 2);

  const csv = await page.evaluate(async (sequenz) => {
    const antwort = await fetch("/api/design/candidates.csv", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sequence: sequenz }),
    });
    const text = await antwort.text();
    return text.split("\n").slice(0, 3);
  }, TRANSKRIPT);
  check("die CSV beginnt mit dem Hinweis", csv[0].startsWith("# "), true);
  check("dann die Kopfzeile", csv[1].startsWith("Rang;Position;Junktion"), true);
  check("und der erste Rang ist die bekannte Stelle", csv[2].split(";")[1], String(GUTE_STELLE));

  // ============================================= 5.6 Als Oligo übernehmen
  await page.getByRole("button", { name: "Als Oligo übernehmen" }).click();
  await page.waitForTimeout(2500);

  check("der Knopf führt zum Steckbrief", new URL(page.url()).pathname, "/steckbrief");
  const kopf = await page.getByRole("banner").textContent();
  check("das DNAzym ist jetzt das aktive", kopf?.includes("33"), true);
  check(
    "und trägt die Spaltstelle im Namen",
    kopf?.includes(String(GUTE_STELLE)),
    true,
  );

  check("keine Fehler in der Konsole", problems, []);
} finally {
  await browser.close();
}

finish(failures());
