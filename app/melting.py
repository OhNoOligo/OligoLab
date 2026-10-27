"""Schmelztemperatur und Thermodynamik eines Arms (PHASEN.md 5.1).

Zwei Wege, und beide werden gegangen:

* **MELTING 5** als Unterprozess, wenn `MELTING_DIR` in der `.env` steht.
  Immer mit vollem Pfad und `shell=False` (CLAUDE.md, Technik) — eine
  Sequenz ist Nutzereingabe, und die hat in keiner Shell etwas zu suchen.
* **Biopython** mit der DNA/RNA-Hybridtabelle `R_DNA_NN1`.

Ist MELTING da, ist es die Hauptquelle und Biopython die Zweitmeinung; bei
mehr als 3 °C Abweichung gibt es eine Warnung (PHASEN.md 5.1). Fehlt MELTING,
rechnet Biopython allein — und sagt das.

ΔH und ΔS werden aus derselben Tabelle summiert, aus der auch der Tm kommt.
Die eigene Rechnung ist gegen `Bio.SeqUtils.MeltingTemp.Tm_NN` geprueft und
stimmt auf 0,01 °C; dadurch gehoeren Tm, ΔH, ΔS und ΔG zusammen, statt aus
zwei Quellen zu stammen, die sich leise widersprechen.

Modifikationen kennt keiner der beiden Wege vollstaendig. Was uebersetzt
werden kann, wird uebersetzt; alles andere laeuft ueber `base_parent` und
wird als genaehert gekennzeichnet (CLAUDE.md, Regel 3).
"""

from __future__ import annotations

import math
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import settings
from app.models import Monomer, Oligo, Quantity, Reliability

#: Gaskonstante in cal/(mol·K) — so wie in den Nearest-Neighbor-Tabellen.
R_CAL = 1.987

#: Ab hier gelten die beiden Wege als uneinig (PHASEN.md 5.1).
DIVERGENCE_WARNING_C = 3.0

#: Uebersetzung fuer MELTING (PHASEN.md 5.1).
#: LNA bekommt den Buchstaben mit angehaengtem `l`, Inosin ist `I`.
MELTING_LNA_SUFFIX = "l"
MELTING_INOSINE = "I"

#: 2'-OMe-Arme sind fuer MELTING kein DNA/RNA-Hybrid mehr, sondern RNA/RNA.
MELTING_HYBRID_DNA_RNA = "dnarna"
MELTING_HYBRID_RNA_RNA = "mrnarna"


@dataclass
class TmResult:
    """Tm, Thermodynamik und woher sie kommen."""

    available: bool = True
    tm: Quantity | None = None
    dg: Quantity | None = None
    dh: Quantity | None = None
    ds: Quantity | None = None
    source: str = "biopython"
    parameter_set: str = ""
    sequence_used: str = ""
    hybridisation_type: str = MELTING_HYBRID_DNA_RNA
    second_opinion_c: float | None = None
    divergence_c: float | None = None
    warnings: list[str] = field(default_factory=list)
    approximated: list[str] = field(default_factory=list)
    note: str | None = None

    @property
    def reliability(self) -> Reliability:
        if not self.available:
            return Reliability.MISSING
        return Reliability.APPROX if self.approximated else Reliability.PARAMETER

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "tm": self.tm.as_dict(2) if self.tm else None,
            "dg": self.dg.as_dict(2) if self.dg else None,
            "dh": self.dh.as_dict(1) if self.dh else None,
            "ds": self.ds.as_dict(1) if self.ds else None,
            "source": self.source,
            "parameter_set": self.parameter_set,
            "sequence_used": self.sequence_used,
            "hybridisation_type": self.hybridisation_type,
            "second_opinion_c": (
                None if self.second_opinion_c is None else round(self.second_opinion_c, 2)
            ),
            "divergence_c": (
                None if self.divergence_c is None else round(self.divergence_c, 2)
            ),
            "reliability": self.reliability.value,
            "warnings": self.warnings,
            "approximated": self.approximated,
            "note": self.note,
        }


@dataclass
class Conditions:
    """Die Puffereinstellungen aus der Kopfzeile (PHASEN.md 2.1)."""

    oligo_conc_nm: float = 1000.0
    na_mm: float = 50.0
    k_mm: float = 0.0
    tris_mm: float = 10.0
    mg_mm: float = 2.0
    temperature_c: float = 37.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "oligo_conc_nm": self.oligo_conc_nm,
            "na_mm": self.na_mm,
            "k_mm": self.k_mm,
            "tris_mm": self.tris_mm,
            "mg_mm": self.mg_mm,
            "temperature_c": self.temperature_c,
        }


# ------------------------------------------------------------ Uebersetzung


@dataclass
class Translation:
    """Was MELTING beziehungsweise Biopython zu sehen bekommt."""

    melting_sequence: str
    plain_sequence: str
    hybridisation: str
    approximated: list[str] = field(default_factory=list)


def translate(oligo: Oligo) -> Translation:
    """Einen Arm in die Schreibweise von MELTING uebersetzen.

    LNA wird zu `Al`, `Cl`, `Gl`, `Tl`; Inosin zu `I`; ein 2'-OMe-Arm macht
    aus dem DNA/RNA-Hybrid ein RNA/RNA-Duplex. Alles andere laeuft ueber
    `base_parent` und wird benannt.
    """
    melting_teile: list[str] = []
    plain_teile: list[str] = []
    approximated: list[str] = []
    hat_ome = False

    for monomer in oligo.monomers:
        parent = monomer.base_parent
        if parent is None:
            approximated.append(
                f"Position {monomer.position} ({monomer.code}): kein natürliches "
                "Analogon — nicht übersetzbar"
            )
            melting_teile.append("N")
            plain_teile.append("N")
            continue

        buchstabe = "T" if parent.upper() == "U" else parent.upper()
        mod_codes = {m.code for m in monomer.modifications}

        if "LNA" in mod_codes:
            melting_teile.append(buchstabe + MELTING_LNA_SUFFIX)
            plain_teile.append(buchstabe)
            approximated.append(
                f"Position {monomer.position}: LNA — Biopython kennt sie nicht "
                "und rechnet über das DNA-Analogon"
            )
        elif "OMe" in mod_codes:
            hat_ome = True
            melting_teile.append(buchstabe)
            plain_teile.append(buchstabe)
            approximated.append(
                f"Position {monomer.position}: 2'-OMe — als RNA/RNA-Duplex "
                "gerechnet"
            )
        elif monomer.spec.code == "I" and not monomer.modifications:
            # Der Synthi-Buchstabe I ist rC, nicht Inosin. Echtes Inosin
            # bekaeme einen eigenen Baustein; fuer den steht die Zuordnung hier.
            melting_teile.append(buchstabe)
            plain_teile.append(buchstabe)
        elif mod_codes & {"Inosin", "dI"}:
            melting_teile.append(MELTING_INOSINE)
            plain_teile.append(buchstabe)
            approximated.append(
                f"Position {monomer.position}: Inosin — Biopython rechnet über "
                f"{buchstabe}"
            )
        else:
            melting_teile.append(buchstabe)
            plain_teile.append(buchstabe)
            if monomer.modifications:
                namen = ", ".join(m.name for m in monomer.modifications)
                approximated.append(
                    f"Position {monomer.position}: {namen} — über das natürliche "
                    f"Analogon {buchstabe} gerechnet"
                )

    return Translation(
        melting_sequence="".join(melting_teile),
        plain_sequence="".join(plain_teile),
        hybridisation=(
            MELTING_HYBRID_RNA_RNA if hat_ome else MELTING_HYBRID_DNA_RNA
        ),
        approximated=approximated,
    )


# ------------------------------------------------------------- Biopython


def _nn_sum(sequence: str, conditions: Conditions) -> tuple[float, float]:
    """ΔH und ΔS aus der DNA/RNA-Hybridtabelle, mit Salzkorrektur.

    Summiert wird ueber dieselbe Tabelle, aus der Biopython seinen Tm zieht.
    Dadurch passen Tm, ΔH, ΔS und ΔG zusammen.
    """
    from Bio.Seq import Seq
    from Bio.SeqUtils import MeltingTemp as mt

    tabelle = mt.R_DNA_NN1
    dh, ds = tabelle["init"]

    for index in range(len(sequence) - 1):
        paar = sequence[index : index + 2]
        schluessel = f"{paar}/{Seq(paar).complement()}"
        if schluessel not in tabelle:
            schluessel = f"{Seq(paar).reverse_complement()}/{paar[::-1]}"
        teil_h, teil_s = tabelle[schluessel]
        dh += teil_h
        ds += teil_s

    ds += mt.salt_correction(
        Na=conditions.na_mm,
        K=conditions.k_mm,
        Tris=conditions.tris_mm,
        Mg=conditions.mg_mm,
        seq=sequence,
        method=5,
    )
    return dh, ds


def biopython_tm(sequence: str, conditions: Conditions) -> TmResult:
    """Tm und Thermodynamik eines Arms gegen seine Ziel-RNA."""
    sauber = sequence.upper().replace("U", "T")
    if len(sauber) < 2:
        return TmResult(
            available=False,
            note="Für eine Nearest-Neighbor-Rechnung braucht es mindestens zwei Basen.",
        )
    if set(sauber) - set("ACGT"):
        return TmResult(
            available=False,
            sequence_used=sauber,
            note=(
                "Die Sequenz enthält Zeichen, für die es keine "
                "Nearest-Neighbor-Parameter gibt."
            ),
        )

    dh, ds = _nn_sum(sauber, conditions)

    # Biopythons Konvention: der hoeher konzentrierte Strang minus der halbe
    # andere. Bei Ueberschuss des Ziels ist das schlicht die Oligokonzentration.
    konzentration = conditions.oligo_conc_nm * 1e-9
    if konzentration <= 0:
        return TmResult(
            available=False,
            note="Die Oligo-Konzentration muss größer als 0 sein.",
        )

    nenner = ds + R_CAL * math.log(konzentration)
    if nenner == 0:
        return TmResult(available=False, note="Tm nicht berechenbar.")

    tm = (1000 * dh) / nenner - 273.15
    temperatur_k = conditions.temperature_c + 273.15
    dg = dh - temperatur_k * ds / 1000.0

    methode = (
        "Biopython, Nearest-Neighbor für DNA/RNA-Hybride "
        "(Sugimoto 1995), Salzkorrektur nach Owczarzy 2008"
    )
    return TmResult(
        available=True,
        tm=Quantity(tm, "°C", Reliability.PARAMETER, methode),
        dg=Quantity(
            dg, "kcal/mol", Reliability.PARAMETER,
            f"{methode}, bei {conditions.temperature_c:g} °C",
        ),
        dh=Quantity(dh, "kcal/mol", Reliability.PARAMETER, methode),
        ds=Quantity(ds, "cal/(mol·K)", Reliability.PARAMETER, methode),
        source="biopython",
        parameter_set="R_DNA_NN1 (Sugimoto 1995)",
        sequence_used=sauber,
    )


# --------------------------------------------------------------- MELTING


def melting_executable() -> Path | None:
    """Der volle Pfad zu MELTING, oder None.

    Gesucht wird nur dort, wo `MELTING_DIR` hinzeigt. Nichts wird geraten und
    nichts ueber die Shell aufgeloest.
    """
    if not settings.melting_dir:
        return None
    basis = Path(settings.melting_dir).expanduser()
    for name in ("melting", "melting.sh", "melting-batch", "MELTING"):
        kandidat = basis / name
        if kandidat.is_file():
            return kandidat
        unter_bin = basis / "bin" / name
        if unter_bin.is_file():
            return unter_bin
    gefunden = shutil.which("melting", path=str(basis))
    return Path(gefunden) if gefunden else None


_NUMBER = r"([-+]?\d+(?:[.,]\d+)?)"
_PATTERNS = {
    "dh": re.compile(rf"enthalpy[^-\d]*{_NUMBER}", re.IGNORECASE),
    "ds": re.compile(rf"entropy[^-\d]*{_NUMBER}", re.IGNORECASE),
    "tm": re.compile(rf"melting temperature[^-\d]*{_NUMBER}", re.IGNORECASE),
}


def parse_melting_output(text: str) -> dict[str, float]:
    """Die Zahlen aus MELTINGs Ausgabe.

    MELTING schreibt eine Zusammenfassung in Klartext. Gesucht werden
    Enthalpie, Entropie und Schmelztemperatur; was nicht dasteht, fehlt eben.
    """
    out: dict[str, float] = {}
    for schluessel, muster in _PATTERNS.items():
        treffer = muster.search(text)
        if treffer:
            try:
                out[schluessel] = float(treffer.group(1).replace(",", "."))
            except ValueError:
                continue
    return out


def melting_tm(
    translation: Translation, conditions: Conditions, timeout_s: float = 30.0
) -> TmResult:
    """MELTING als Unterprozess, mit vollem Pfad und ohne Shell."""
    programm = melting_executable()
    if programm is None:
        return TmResult(
            available=False,
            source="melting",
            note=(
                "MELTING ist nicht eingerichtet. Ohne es rechnet Biopython "
                "allein; alles andere im Programm bleibt unberührt. "
                "Einzurichten über MELTING_DIR in der .env."
            ),
        )

    # Ionen in mol/L, so erwartet MELTING sie.
    ionen = (
        f"Na={conditions.na_mm / 1000:g}"
        f":Mg={conditions.mg_mm / 1000:g}"
        f":K={conditions.k_mm / 1000:g}"
        f":Tris={conditions.tris_mm / 1000:g}"
    )
    befehl = [
        str(programm),
        "-S", translation.melting_sequence,
        "-H", translation.hybridisation,
        "-P", f"{conditions.oligo_conc_nm * 1e-9:g}",
        "-E", ionen,
    ]

    try:
        # shell=False ist der Standard und steht hier ausdruecklich: eine
        # Sequenz ist Nutzereingabe und hat in keiner Shell etwas zu suchen.
        ergebnis = subprocess.run(  # noqa: S603
            befehl,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as fehler:
        return TmResult(
            available=False,
            source="melting",
            note=f"MELTING ließ sich nicht ausführen: {fehler}",
        )

    if ergebnis.returncode != 0:
        kurz = (ergebnis.stderr or ergebnis.stdout or "").strip()[:200]
        return TmResult(
            available=False,
            source="melting",
            note=f"MELTING endete mit Code {ergebnis.returncode}: {kurz}",
        )

    zahlen = parse_melting_output(ergebnis.stdout)
    if "tm" not in zahlen:
        return TmResult(
            available=False,
            source="melting",
            note=(
                "Aus MELTINGs Ausgabe ließ sich keine Schmelztemperatur lesen. "
                "Möglicherweise hat sich das Ausgabeformat geändert."
            ),
        )

    dh = zahlen.get("dh")
    ds = zahlen.get("ds")
    methode = f"MELTING 5, Hybridtyp {translation.hybridisation}"
    temperatur_k = conditions.temperature_c + 273.15
    dg = None if dh is None or ds is None else dh - temperatur_k * ds / 1000.0

    def q(value: float | None, unit: str, extra: str = "") -> Quantity | None:
        if value is None:
            return None
        return Quantity(
            value, unit, Reliability.PARAMETER, f"{methode}{extra}"
        )

    return TmResult(
        available=True,
        tm=q(zahlen["tm"], "°C"),
        dg=q(dg, "kcal/mol", f", bei {conditions.temperature_c:g} °C"),
        dh=q(dh, "kcal/mol"),
        ds=q(ds, "cal/(mol·K)"),
        source="melting",
        parameter_set=f"MELTING, Hybridtyp {translation.hybridisation}",
        sequence_used=translation.melting_sequence,
        hybridisation_type=translation.hybridisation,
    )


# ------------------------------------------------------------ beides


def compute(
    arm: Oligo | str,
    conditions: Conditions | None = None,
) -> TmResult:
    """Tm eines Arms, mit Zweitmeinung.

    Ist MELTING eingerichtet, fuehrt es; Biopython prueft nach. Weichen die
    beiden um mehr als 3 °C voneinander ab, steht das als Warnung dabei —
    nicht als stiller Mittelwert.
    """
    bedingungen = conditions or Conditions()

    if isinstance(arm, str):
        uebersetzung = Translation(
            melting_sequence=arm.upper().replace("U", "T"),
            plain_sequence=arm.upper().replace("U", "T"),
            hybridisation=MELTING_HYBRID_DNA_RNA,
        )
    else:
        uebersetzung = translate(arm)

    ueber_melting = melting_tm(uebersetzung, bedingungen)
    ueber_biopython = biopython_tm(uebersetzung.plain_sequence, bedingungen)

    for ergebnis in (ueber_melting, ueber_biopython):
        ergebnis.approximated = list(uebersetzung.approximated)
        ergebnis.hybridisation_type = uebersetzung.hybridisation

    if ueber_melting.available and ueber_biopython.available:
        haupt = ueber_melting
        zweit = ueber_biopython.tm.value if ueber_biopython.tm else None
        if zweit is not None and haupt.tm and haupt.tm.value is not None:
            abweichung = abs(haupt.tm.value - zweit)
            haupt.second_opinion_c = zweit
            haupt.divergence_c = abweichung
            if abweichung > DIVERGENCE_WARNING_C:
                haupt.warnings.append(
                    f"MELTING und Biopython sind sich uneinig: "
                    f"{haupt.tm.value:.1f} °C gegen {zweit:.1f} °C, "
                    f"{abweichung:.1f} °C Unterschied. Bei mehr als "
                    f"{DIVERGENCE_WARNING_C:.0f} °C lohnt ein Blick auf die "
                    "Parameter, bevor man sich auf eine der beiden Zahlen verlässt."
                )
        return haupt

    if ueber_biopython.available:
        ueber_biopython.note = ueber_melting.note
        return ueber_biopython

    # Beide ohne Ergebnis. Dann zaehlt der Grund von Biopython: der sagt
    # etwas ueber die Eingabe ("zu kurz", "unbekannte Zeichen"), waehrend
    # MELTINGs Grund meist nur lautet, dass es nicht eingerichtet ist. Wer
    # eine Sequenz aus zwei Zeichen eingibt, soll nicht lesen, er muesse
    # erst ein Java-Programm installieren.
    ueber_biopython.warnings = list(ueber_melting.warnings)
    if ueber_melting.note and ueber_biopython.note:
        ueber_biopython.note = f"{ueber_biopython.note} {ueber_melting.note}"
    elif ueber_melting.note:
        ueber_biopython.note = ueber_melting.note
    return ueber_biopython


def arm_conditions_from(buffer: dict[str, Any] | None) -> Conditions:
    """Die Bedingungen aus der Kopfzeile in `Conditions` uebersetzen."""
    if not buffer:
        return Conditions()
    return Conditions(
        oligo_conc_nm=float(buffer.get("oligoConcNm", 1000.0)),
        na_mm=float(buffer.get("naMm", 50.0)),
        k_mm=float(buffer.get("kMm", 0.0)),
        tris_mm=float(buffer.get("trisMm", 10.0)),
        mg_mm=float(buffer.get("mgMm", 2.0)),
        temperature_c=float(buffer.get("reactionTempC", 37.0)),
    )
