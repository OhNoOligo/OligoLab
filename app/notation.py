"""Die Synthi-Sprache lesen und schreiben.

| Zeichen        | Bedeutung                                         |
| -------------- | ------------------------------------------------- |
| `A C G T`      | DNA                                               |
| `O I Z U`      | rA, rC, rG, rU                                    |
| `E L`          | eigene Bausteine aus `data/monomers.yaml`          |
| Leerzeichen    | wird ignoriert (auch Tab und Zeilenumbruch)        |
| `*`            | Phosphorothioat an genau dieser Bindung            |
| `[code]`       | eigener Baustein an genau dieser Position          |
| `/NAME/`       | Konjugat oder Endmodifikation                      |

Kleinbuchstaben werden akzeptiert und auf Grossbuchstaben abgebildet.

CLAUDE.md, Regel 5: ein unbekanntes Zeichen ist ein Fehler MIT Positionsangabe
und wird nie stillschweigend uebersprungen. Genau das war der Fehler im Excel.

Zwei Einstiege:

* `parse()` bricht beim ersten Problem mit `NotationError` ab — fuer alles,
  was danach rechnet.
* `analyse()` sammelt ALLE Probleme ein und gibt sie mit zurueck — dafuer, dass
  die Oberflaeche jedes unbekannte Zeichen rot unterkringeln kann.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from app.models import (
    Conjugate,
    Linkage,
    ModificationSpec,
    Monomer,
    MonomerSpec,
    Oligo,
)
from app.registry import Registry, get_registry

WHITESPACE = " \t\r\n "

# Uebersetzer DNA <-> Synthi-RNA, wie im Excel.
DNA_TO_RNA = {"A": "O", "C": "I", "G": "Z", "T": "U"}
RNA_TO_DNA = {v: k for k, v in DNA_TO_RNA.items()}


@dataclass(frozen=True)
class NotationProblem:
    """Ein Befund im Sequenztext, mit Stelle und Erklaerung.

    `position` ist 1-basiert und zaehlt Zeichen der EINGABE, einschliesslich
    der ignorierten Leerzeichen — damit die Oberflaeche genau dort unterkringeln
    kann, wo der Nutzer getippt hat.
    """

    position: int
    text: str
    message: str
    hint: str | None = None
    span: tuple[int, int] = (0, 0)

    def as_dict(self) -> dict:
        return {
            "position": self.position,
            "text": self.text,
            "message": self.message,
            "hint": self.hint,
            "start": self.span[0],
            "end": self.span[1],
        }


class NotationError(ValueError):
    """Wird von `parse()` beim ersten Problem geworfen."""

    def __init__(self, problem: NotationProblem) -> None:
        self.problem = problem
        detail = f" {problem.hint}" if problem.hint else ""
        super().__init__(
            f"Position {problem.position}: {problem.message}{detail}"
        )


# --------------------------------------------------------------------- lesen


def _resolve_bracket(
    code: str, registry: Registry
) -> tuple[MonomerSpec, tuple[ModificationSpec, ...]] | None:
    """`[LNA-T]` aufloesen.

    Zuerst als eigener Baustein aus `monomers.yaml`. Sonst als Kombination
    `MOD-BASE` oder `BASE-MOD`, wobei MOD eine Modifikation mit `scope: monomer`
    und BASE ein bekannter Baustein ist.
    """
    direct = registry.monomer(code)
    if direct is not None:
        return direct, ()

    if "-" in code:
        for cut in range(len(code)):
            if code[cut] != "-":
                continue
            left, right = code[:cut], code[cut + 1:]
            for mod_code, base_code in ((left, right), (right, left)):
                mod = registry.modification(mod_code)
                base = registry.monomer(base_code)
                if mod is None or base is None:
                    continue
                if mod.scope != "monomer":
                    continue
                return base, (mod,)
    return None


def analyse(
    seq: str,
    registry: Registry | None = None,
    name: str | None = None,
) -> tuple[Oligo, list[NotationProblem]]:
    """Sequenztext zerlegen und ALLE Probleme einsammeln.

    Gibt immer ein `Oligo` zurueck — es enthaelt die Bausteine, die gelesen
    werden konnten. Ist die Liste der Probleme nicht leer, darf damit nicht
    gerechnet werden; die Oberflaeche zeigt sie an.
    """
    reg = registry or get_registry()
    monomers: list[Monomer] = []
    problems: list[NotationProblem] = []
    thioate_at: set[int] = set()
    pending_conjugates: list[tuple[ModificationSpec, int, tuple[int, int]]] = []

    i = 0
    n = len(seq)
    pending_star: tuple[int, int] | None = None  # (1-basierte Position, offset)

    def add_monomer(
        spec: MonomerSpec,
        mods: tuple[ModificationSpec, ...],
        span: tuple[int, int],
        source: str,
    ) -> None:
        nonlocal pending_star
        position = len(monomers) + 1
        monomers.append(
            Monomer(
                position=position,
                spec=spec,
                modifications=mods,
                span=span,
                source=source,
            )
        )
        if pending_star is not None:
            # Das `*` stand vor diesem Baustein, betrifft also die Bindung
            # zwischen dem vorigen und diesem.
            thioate_at.add(position - 1)
            pending_star = None

    while i < n:
        ch = seq[i]

        if ch in WHITESPACE:
            i += 1
            continue

        # ---- Phosphorothioat ----
        if ch == "*":
            if not monomers:
                problems.append(
                    NotationProblem(
                        position=i + 1,
                        text="*",
                        message="`*` steht vor dem ersten Baustein.",
                        hint="Ein Phosphorothioat braucht links und rechts einen Baustein.",
                        span=(i, i + 1),
                    )
                )
            elif pending_star is not None:
                problems.append(
                    NotationProblem(
                        position=i + 1,
                        text="*",
                        message="Zwei `*` hintereinander.",
                        hint="Je Bindung ist nur ein `*` moeglich.",
                        span=(i, i + 1),
                    )
                )
            else:
                pending_star = (i + 1, i)
            i += 1
            continue

        # ---- eigener Baustein [code] ----
        if ch == "[":
            close = seq.find("]", i + 1)
            if close == -1:
                problems.append(
                    NotationProblem(
                        position=i + 1,
                        text=seq[i:],
                        message="`[` ohne schliessende `]`.",
                        hint="Schreibweise: `[LNA-T]`.",
                        span=(i, n),
                    )
                )
                break
            token = seq[i + 1 : close].strip()
            resolved = _resolve_bracket(token, reg)
            if resolved is None:
                problems.append(
                    NotationProblem(
                        position=i + 1,
                        text=seq[i : close + 1],
                        message=f"Unbekannter Baustein `{token}`.",
                        hint=(
                            "Entweder als Code in data/monomers.yaml anlegen oder "
                            "als `MODIFIKATION-BASE` schreiben, z. B. `[LNA-T]`."
                        ),
                        span=(i, close + 1),
                    )
                )
            else:
                spec, mods = resolved
                add_monomer(spec, mods, (i, close + 1), seq[i : close + 1])
            i = close + 1
            continue

        # ---- Konjugat /NAME/ ----
        if ch == "/":
            close = seq.find("/", i + 1)
            if close == -1:
                problems.append(
                    NotationProblem(
                        position=i + 1,
                        text=seq[i:],
                        message="`/` ohne schliessendes `/`.",
                        hint="Schreibweise: `/5GalNAc/`.",
                        span=(i, n),
                    )
                )
                break
            token = seq[i + 1 : close].strip()
            mod = reg.modification(token)
            if mod is None:
                problems.append(
                    NotationProblem(
                        position=i + 1,
                        text=seq[i : close + 1],
                        message=f"Unbekanntes Konjugat `{token}`.",
                        hint="In data/modifications.yaml mit `scope: terminus` anlegen.",
                        span=(i, close + 1),
                    )
                )
            else:
                pending_conjugates.append((mod, len(monomers), (i, close + 1)))
            i = close + 1
            continue

        # ---- einzelner Buchstabe ----
        upper = ch.upper()
        spec = reg.monomer(upper)
        if spec is None:
            known = ", ".join(sorted(reg.monomers))
            problems.append(
                NotationProblem(
                    position=i + 1,
                    text=ch,
                    message=f"Unbekanntes Zeichen `{ch}`.",
                    hint=f"Bekannte Bausteine: {known}.",
                    span=(i, i + 1),
                )
            )
        else:
            add_monomer(spec, (), (i, i + 1), ch)
        i += 1

    if pending_star is not None:
        pos, off = pending_star
        problems.append(
            NotationProblem(
                position=pos,
                text="*",
                message="`*` steht nach dem letzten Baustein.",
                hint="Ein Phosphorothioat braucht links und rechts einen Baustein.",
                span=(off, off + 1),
            )
        )

    linkages = [
        Linkage(
            position=k + 1,
            kind="phosphorothioate" if (k + 1) in thioate_at else "phosphate",
            modification=reg.modification("Thioat") if (k + 1) in thioate_at else None,
        )
        for k in range(max(len(monomers) - 1, 0))
    ]

    total = len(monomers)
    conjugates = []
    for mod, after, span in pending_conjugates:
        if after == 0:
            attach = "5prime"
            after_position = None
        elif after >= total:
            attach = "3prime"
            after_position = total or None
        else:
            attach = "internal"
            after_position = after
        conjugates.append(
            Conjugate(spec=mod, attach=attach, after_position=after_position, span=span)
        )

    oligo = Oligo(
        monomers=monomers,
        linkages=linkages,
        conjugates=conjugates,
        name=name,
    )
    return oligo, problems


def parse(seq: str, registry: Registry | None = None, name: str | None = None) -> Oligo:
    """Sequenztext in ein `Oligo` zerlegen.

    Wirft `NotationError` beim ersten Problem — mit Positionsangabe.
    """
    oligo, problems = analyse(seq, registry=registry, name=name)
    if problems:
        raise NotationError(problems[0])
    return oligo


# -------------------------------------------------------------- schreiben


def to_string(
    oligo: Oligo | Iterable[Monomer],
    group: int = 0,
) -> str:
    """Umkehrung von `parse`.

    `group=3` setzt Leerzeichen nach je drei Bausteinen, so wie das Excel die
    Sequenz anzeigt. Phosphorothioate und Konjugate bleiben erhalten.
    """
    if isinstance(oligo, Oligo):
        monomers = oligo.monomers
        linkages = {l.position: l for l in oligo.linkages}
        conjugates = oligo.conjugates
    else:
        monomers = list(oligo)
        linkages = {}
        conjugates = []

    def token(m: Monomer) -> str:
        if m.modifications:
            mods = "-".join(mod.code for mod in m.modifications)
            return f"[{mods}-{m.spec.code}]"
        return m.spec.code

    parts: list[str] = []
    for conj in conjugates:
        if conj.attach == "5prime":
            parts.append(f"/{conj.code}/")

    for idx, m in enumerate(monomers):
        if idx and group and idx % group == 0:
            # Kein Leerzeichen direkt hinter einem `*`, sonst liest es sich falsch.
            if not parts or not parts[-1].endswith("*"):
                parts.append(" ")
        parts.append(token(m))
        link = linkages.get(m.position)
        if link is not None and link.kind == "phosphorothioate":
            parts.append("*")
        for conj in conjugates:
            if conj.attach == "internal" and conj.after_position == m.position:
                parts.append(f"/{conj.code}/")

    for conj in conjugates:
        if conj.attach == "3prime":
            parts.append(f"/{conj.code}/")

    return "".join(parts)


# ------------------------------------------------------------- uebersetzen


def translate(
    oligo: Oligo,
    to: Literal["rna", "dna"],
    registry: Registry | None = None,
) -> tuple[Oligo, list[str]]:
    """DNA <-> Synthi-RNA, wie im Excel: T<->U, C<->I, A<->O, G<->Z.

    Gibt das uebersetzte Oligo und die Liste der Bausteine zurueck, die nicht
    uebersetzt werden konnten — die bleiben unveraendert, werden aber genannt.
    """
    reg = registry or get_registry()
    table = DNA_TO_RNA if to == "rna" else RNA_TO_DNA
    untouched: list[str] = []
    new_monomers: list[Monomer] = []

    for m in oligo.monomers:
        target_code = table.get(m.spec.code)
        if target_code is None or m.modifications:
            if m.spec.code not in table.values():
                untouched.append(f"Position {m.position}: {m.source or m.spec.code}")
            new_monomers.append(m)
            continue
        target = reg.monomer(target_code)
        if target is None:
            untouched.append(f"Position {m.position}: {m.spec.code}")
            new_monomers.append(m)
            continue
        new_monomers.append(
            Monomer(
                position=m.position,
                spec=target,
                modifications=m.modifications,
                span=m.span,
                source=target_code,
            )
        )

    translated = Oligo(
        monomers=new_monomers,
        linkages=list(oligo.linkages),
        conjugates=list(oligo.conjugates),
        name=oligo.name,
        notes=oligo.notes,
    )
    return translated, untouched
