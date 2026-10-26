/* Rahmen und Navigation.
 *
 * Phase 1 bringt zwei Seiten: "Steckbrief" und "Bausteine". Die Seitenleiste
 * mit den fuenf Bereichen Ziel, Entwurf, Strang, Steckbrief und 3D samt
 * Statusanzeige und Tastaturkuerzeln gehoert zu Phase 2 — hier steht nur, was
 * schon rechnet.
 */

import { useEffect, useState } from "react";
import { api } from "./api";
import { Bausteine } from "./pages/Bausteine";
import { Steckbrief } from "./pages/Steckbrief";
import { Notice } from "./components/ui";

const PAGES = [
  { id: "steckbrief", label: "Steckbrief", hint: "Sequenz, Massen, Verbrauch" },
  { id: "bausteine", label: "Bausteine", hint: "Monomere und Konstanten" },
] as const;

type PageId = (typeof PAGES)[number]["id"];

export default function App() {
  const [page, setPage] = useState<PageId>("steckbrief");
  const [version, setVersion] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    api
      .health()
      .then((result) => {
        setVersion(result.version);
        setOffline(false);
      })
      .catch(() => setOffline(true));
  }, []);

  return (
    <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col gap-4 p-4 sm:flex-row">
      <nav
        className="ol-card shrink-0 self-start p-2 sm:sticky sm:top-4 sm:w-52"
        aria-label="Bereiche"
      >
        <div className="px-2 pb-3 pt-1">
          <p className="text-sm font-semibold">OligoLab</p>
          <p className="text-xs" style={{ color: "var(--text-faint)" }}>
            {version ? `Version ${version}` : "nicht verbunden"}
          </p>
        </div>
        <ul className="flex gap-1 sm:flex-col">
          {PAGES.map((entry) => {
            const active = entry.id === page;
            return (
              <li key={entry.id}>
                <button
                  type="button"
                  className="w-full rounded-lg px-2 py-1.5 text-left"
                  aria-current={active ? "page" : undefined}
                  onClick={() => setPage(entry.id)}
                  style={{
                    background: active
                      ? "color-mix(in srgb, var(--role-result) 12%, transparent)"
                      : "transparent",
                    border: `1px solid ${active ? "var(--role-result)" : "transparent"}`,
                    color: active ? "var(--role-result)" : "var(--text)",
                    cursor: "pointer",
                  }}
                >
                  <span className="block text-sm font-medium">{entry.label}</span>
                  <span className="block text-xs" style={{ color: "var(--text-faint)" }}>
                    {entry.hint}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      <main className="min-w-0 flex-1">
        {offline && (
          <div className="mb-4">
            <Notice level="bad" title="Backend nicht erreichbar">
              OligoLab rechnet lokal. Starte das Backend mit{" "}
              <code className="ol-mono">uvicorn app.main:app --reload</code> und
              lade die Seite neu.
            </Notice>
          </div>
        )}
        {page === "steckbrief" && <Steckbrief />}
        {page === "bausteine" && <Bausteine />}
      </main>
    </div>
  );
}
