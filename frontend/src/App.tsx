/* Rahmen, Navigation und Routing (PHASEN.md 2.2 bis 2.4).
 *
 * Aufbau: die Kopfzeile ist immer sichtbar, links die Seitenleiste mit den
 * fünf Bereichen, rechts der Inhalt. Die Bereiche Ziel, Entwurf, Strang und
 * 3D sind angelegt und erreichbar; ihren Inhalt füllen die Phasen 3 bis 6.
 */

import { useEffect, useState } from "react";
import { api } from "./api";
import { Header } from "./components/Header";
import { HelpProvider } from "./components/HelpTip";
import { AREAS, Sidebar } from "./components/Sidebar";
import { Notice } from "./components/ui";
import { Bausteine } from "./pages/Bausteine";
import { Entwurf } from "./pages/Entwurf";
import { Modell3D } from "./pages/Modell3D";
import { Ziel } from "./pages/Ziel";
import { Strang } from "./pages/Strang";
import { Hilfe } from "./pages/Hilfe";
import { Steckbrief } from "./pages/Steckbrief";
import { useRoute } from "./router";
import { StoreProvider } from "./state/store";

function Inhalt({
  path,
  navigate,
}: {
  path: string;
  navigate: (path: string) => void;
}) {
  switch (path) {
    case "/":
    case "/steckbrief":
      return <Steckbrief navigate={navigate} />;
    case "/ziel":
      return <Ziel navigate={navigate} />;
    case "/entwurf":
      return <Entwurf navigate={navigate} />;
    case "/strang":
      return <Strang navigate={navigate} />;
    case "/3d":
      return <Modell3D navigate={navigate} />;
    case "/bausteine":
      return <Bausteine />;
    case "/hilfe":
      return <Hilfe />;
    default:
      return (
        <Notice level="warn" title="Diese Seite gibt es nicht">
          <button
            type="button"
            className="underline"
            style={{ color: "var(--role-result)" }}
            onClick={() => navigate("/")}
          >
            Zurück zum Steckbrief
          </button>
        </Notice>
      );
  }
}

function Rahmen() {
  const [path, navigate] = useRoute();
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

  // Der Titel des Fensters folgt dem Bereich — hilft bei mehreren Tabs.
  useEffect(() => {
    const area = AREAS.find((entry) => entry.path === path);
    document.title = area ? `${area.label} · OligoLab` : "OligoLab";
  }, [path]);

  return (
    <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col gap-4 p-4">
      <Header />

      <div className="flex flex-col gap-4 sm:flex-row">
        <div className="shrink-0 sm:w-56">
          <Sidebar path={path} navigate={navigate} />
          <p
            className="mt-2 px-2 text-[11px]"
            style={{ color: "var(--text-faint)" }}
          >
            OligoLab {version ? `${version}` : ""}
            <br />
            Alles läuft lokal.
          </p>
        </div>

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
          <Inhalt path={path} navigate={navigate} />
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <StoreProvider>
      <HelpProvider>
        <Rahmen />
      </HelpProvider>
    </StoreProvider>
  );
}
