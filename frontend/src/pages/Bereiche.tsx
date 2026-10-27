/* Die Bereiche, die spätere Phasen füllen.
 *
 * Phase 2 legt sie an: Navigation, Stand und Übergaben funktionieren, der
 * Inhalt kommt später. Das ist Absicht — die Wege durch das Programm lassen
 * sich so schon prüfen, bevor die Rechnungen dahinter stehen.
 */

import { AreaPlaceholder, Handoff, Missing } from "../components/AreaShell";
import { useStore } from "../state/store";

function hasOligo(sequence: string | undefined): boolean {
  return Boolean(sequence && sequence.trim());
}

export function Ziel({ navigate }: { navigate: (path: string) => void }) {
  const { state, markComputed } = useStore();
  const target = state.activeTarget;
  const bereit = hasOligo(target?.sequence);

  return (
    <div className="flex flex-col gap-4">
      <AreaPlaceholder
        area="ziel"
        title="Ziel"
        phase={4}
        what="Zielsequenz holen, falten, Zugänglichkeitsprofil"
        needs={
          <ul className="list-inside list-disc">
            <li>
              Eine Ziel-RNA. Oben in der Kopfzeile einfügen — oder später aus
              Ensembl, NCBI und RNAcentral holen.
            </li>
            <li>Optional einen Ausschnitt, damit nicht das ganze Transkript gerechnet wird.</li>
          </ul>
        }
      >
        {!bereit && (
          <Missing>
            Es ist keine Ziel-RNA gesetzt. Das Feld dafür steht in der Kopfzeile.
          </Missing>
        )}
      </AreaPlaceholder>

      <Handoff
        label="Spaltstellen suchen"
        disabled={!bereit}
        reason="Erst eine Ziel-RNA setzen"
        onClick={() => {
          markComputed("ziel");
          navigate("/entwurf");
        }}
      />
    </div>
  );
}

export function Entwurf({ navigate }: { navigate: (path: string) => void }) {
  const { state, markComputed } = useStore();
  const bereit = hasOligo(state.activeTarget?.sequence);

  return (
    <div className="flex flex-col gap-4">
      <AreaPlaceholder
        area="entwurf"
        title="Entwurf"
        phase={5}
        what="Aus der Ziel-RNA eine Rangliste von Kandidaten"
        needs={
          <ul className="list-inside list-disc">
            <li>Eine Ziel-RNA mit Faltung aus dem Bereich Ziel.</li>
            <li>
              Die Bedingungen aus der Kopfzeile — Kationen und
              Reaktionstemperatur gehen in Tm und ΔG ein.
            </li>
            <li>MELTING 5, als <code className="ol-mono">MELTING_DIR</code> in der .env.</li>
          </ul>
        }
      >
        {!bereit && <Missing>Es ist keine Ziel-RNA gesetzt.</Missing>}
      </AreaPlaceholder>

      <div className="flex flex-wrap items-center justify-end gap-2">
        <button
          type="button"
          className="ol-button"
          disabled
          title="Kommt in Phase 5 mit der Kandidatenliste"
        >
          ← Nächster Kandidat
        </button>
        <Handoff
          label="Als Oligo übernehmen"
          disabled={!bereit}
          reason="Erst eine Ziel-RNA setzen"
          onClick={() => {
            markComputed("entwurf");
            navigate("/strang");
          }}
        />
      </div>
    </div>
  );
}

export function Modell3D() {
  const { state } = useStore();
  const bereit = hasOligo(state.activeOligo?.sequence);

  return (
    <div className="flex flex-col gap-4">
      <AreaPlaceholder
        area="3d"
        title="3D"
        phase={6}
        what="Räumlich einordnen, wo die Modifikationen sitzen"
        needs={
          <ul className="list-inside list-disc">
            <li>Ein DNAzym, am besten mit erkanntem katalytischem Kern.</li>
            <li>
              Eine Referenzstruktur von der RCSB-PDB, voreingestellt 8E9A für
              das 10-23.
            </li>
          </ul>
        }
      >
        {!bereit && <Missing>Es ist kein DNAzym gesetzt.</Missing>}
      </AreaPlaceholder>
    </div>
  );
}
