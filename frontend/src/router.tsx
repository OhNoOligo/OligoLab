/* Ein sehr kleiner Router.
 *
 * Sechs feste Pfade rechtfertigen keine Bibliothek. Gearbeitet wird mit
 * `history.pushState` und `popstate`, damit `/hilfe` eine echte Adresse ist
 * und nicht nur ein Zustand im Kopf der Anwendung — Lesezeichen und der
 * Zurück-Knopf des Browsers funktionieren dadurch von selbst.
 *
 * Damit ein Direktaufruf von `/hilfe` nicht ins Leere läuft, liefert das
 * Backend für alle Pfade außerhalb von `/api` die `index.html` aus.
 */

import { useCallback, useEffect, useState } from "react";

function currentPath(): string {
  const path = window.location.pathname;
  return path.length > 1 && path.endsWith("/") ? path.slice(0, -1) : path;
}

export function useRoute(): [string, (path: string) => void] {
  const [path, setPath] = useState(currentPath);

  useEffect(() => {
    const onPop = () => setPath(currentPath());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((next: string) => {
    if (next === currentPath()) return;
    window.history.pushState(null, "", next);
    setPath(next);
    window.scrollTo({ top: 0 });
  }, []);

  return [path, navigate];
}
