"""Der Gesamtbericht (PHASEN.md 6.6).

Ein Blatt, das ins Laborbuch wandert: Sequenz, Masse, Ladungsleiter, Tm und
ΔG der Arme, Eigenfaltung, Zugaenglichkeit, Befunde, Punktzahl, dazu die
Bilder — Sequenzkarte, Paarungsdarstellung, 3D-Ansicht. Im Fussbereich
Datum und alle verwendeten Einstellungen, damit die Rechnung reproduzierbar
ist.

**Zum PDF:** erzeugt wird HTML mit einem Druckstil; das PDF schreibt der
Browser. Eine PDF-Bibliothek haette Systembibliotheken nachgezogen
(Cairo, Pango), und das Ergebnis waere dasselbe Blatt — nur mit einer
weiteren Abhaengigkeit, die ohne Netz nicht zu installieren ist. Der Weg
ueber den Druckdialog laeuft lokal und ohne Zusatz (CLAUDE.md, Regel 4).

Die Bilder kommen als SVG-Text von der Oberflaeche. Sie hier noch einmal zu
zeichnen hiesse, dieselbe Darstellung zweimal zu pflegen — und die zweite
waere irgendwann die falsche.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app import __version__


@dataclass
class ReportSection:
    """Ein Abschnitt: Ueberschrift und Zeilen aus Groesse, Wert, Verfahren."""

    title: str
    rows: list[tuple[str, str, str]] = field(default_factory=list)
    note: str | None = None


def _esc(value: Any) -> str:
    """Maskiert fuer Text, nicht fuer Attribute.

    `quote=False`, weil hier nichts in einem Attributwert landet: ein
    Apostroph in „Tm 5'-Arm" soll ein Apostroph bleiben und nicht als
    `&#x27;` im Quelltext stehen.
    """
    return html.escape("" if value is None else str(value), quote=False)


def _number(value: Any, digits: int = 2, unit: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        text = f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")
        return f"{text} {unit}".strip()
    return str(value)


#: Nur diese Elemente bleiben in einem mitgeschickten Bild stehen.
#:
#: Das SVG kommt aus der eigenen Oberflaeche, aber es laeuft ueber eine
#: Anfrage — und was ueber eine Anfrage kommt, wird geprueft. Ein `<script>`
#: im Bild wuerde beim Oeffnen des Berichts ausgefuehrt.
def sanitise_svg(svg: str) -> str:
    """Schrift und Zeichnung bleiben, alles Ausfuehrbare fliegt raus."""
    import re

    ohne_script = re.sub(
        r"<script\b.*?</script\s*>", "", svg, flags=re.IGNORECASE | re.DOTALL
    )
    ohne_fremd = re.sub(
        r"<(foreignObject|iframe|object|embed)\b.*?</\1\s*>",
        "",
        ohne_script,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Ereignis-Attribute: onclick und die ganze Verwandtschaft.
    ohne_ereignisse = re.sub(r"\son[a-z]+\s*=\s*\"[^\"]*\"", "", ohne_fremd, flags=re.I)
    ohne_ereignisse = re.sub(r"\son[a-z]+\s*=\s*'[^']*'", "", ohne_ereignisse, flags=re.I)

    # Verweise: nur was eine Zeichnung wirklich braucht. Ein `javascript:`
    # bloss wegzustreichen reicht nicht — mit Entities geschrieben
    # (`&#106;avascript:`) stuende es wieder da, sobald der Browser die
    # Zeichenfolge aufloest. Darum eine Erlaubnisliste statt einer
    # Verbotsliste: Sprungmarke oder eingebettetes Bild, sonst nichts.
    def verweis(treffer: re.Match[str]) -> str:
        name, wert = treffer.group(1), treffer.group(2)
        erlaubt = wert.startswith("#") or wert.startswith("data:image/")
        return f' {name}="{wert}"' if erlaubt else ""

    return re.sub(
        r"\s(href|xlink:href)\s*=\s*\"([^\"]*)\"", verweis, ohne_ereignisse, flags=re.I
    )


STYLE = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body {
  font-family: ui-sans-serif, system-ui, sans-serif;
  color: #1a1a1a; background: #fff;
  margin: 0; padding: 24px; line-height: 1.5;
}
h1 { font-size: 20px; margin: 0 0 4px; }
h2 { font-size: 14px; margin: 24px 0 8px; padding-bottom: 4px;
     border-bottom: 1px solid #d8d8d8; }
.kopf { color: #666; font-size: 12px; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
td, th { text-align: left; padding: 3px 8px 3px 0; vertical-align: top; }
tr + tr td { border-top: 1px solid #eee; }
td.wert { font-family: ui-monospace, monospace; text-align: right;
          white-space: nowrap; }
td.verfahren { color: #777; font-size: 11px; }
.mono { font-family: ui-monospace, monospace; word-break: break-all; }
.bild { margin: 8px 0 16px; overflow: hidden; }
.bild svg { max-width: 100%; height: auto; }
.hinweis { border: 1px solid #c8a200; background: #fdf6e0;
           padding: 8px 10px; font-size: 12px; border-radius: 6px;
           margin: 8px 0; }
.ampel { font-weight: 600; }
.gut { color: #1f7a3f; } .mittel { color: #9a6700; } .schwach { color: #b02020; }
footer { margin-top: 28px; padding-top: 10px; border-top: 1px solid #d8d8d8;
         color: #666; font-size: 11px; }
@media print {
  body { padding: 0; }
  h2 { break-after: avoid; }
  .bild, table { break-inside: avoid; }
  .kein-druck { display: none; }
}
"""

RATING_TEXT = {"good": ("gut", "gut"), "warn": ("mittel", "mittel"), "bad": ("schwach", "schwach")}


def build_html(
    title: str,
    sections: list[ReportSection],
    images: dict[str, str] | None = None,
    settings: dict[str, Any] | None = None,
    disclaimers: list[str] | None = None,
) -> str:
    """Den Bericht als eigenstaendige HTML-Seite bauen."""
    jetzt = datetime.now().strftime("%d.%m.%Y, %H:%M")
    teile: list[str] = [
        "<!doctype html>",
        '<html lang="de"><head><meta charset="utf-8">',
        f"<title>{_esc(title)}</title>",
        f"<style>{STYLE}</style></head><body>",
        f"<h1>{_esc(title)}</h1>",
        f'<p class="kopf">OligoLab {_esc(__version__)} · {jetzt} · alles lokal gerechnet</p>',
        '<p class="kein-druck"><button onclick="window.print()">Drucken oder als PDF sichern</button></p>',
    ]

    for hinweis in disclaimers or []:
        teile.append(f'<div class="hinweis">{_esc(hinweis)}</div>')

    for abschnitt in sections:
        teile.append(f"<h2>{_esc(abschnitt.title)}</h2>")
        if abschnitt.rows:
            teile.append("<table>")
            for name, wert, verfahren in abschnitt.rows:
                teile.append(
                    f"<tr><td>{_esc(name)}</td>"
                    f'<td class="wert">{_esc(wert)}</td>'
                    f'<td class="verfahren">{_esc(verfahren)}</td></tr>'
                )
            teile.append("</table>")
        if abschnitt.note:
            teile.append(f'<div class="hinweis">{_esc(abschnitt.note)}</div>')
        bild = (images or {}).get(abschnitt.title)
        if bild:
            teile.append(f'<div class="bild">{sanitise_svg(bild)}</div>')

    for name, bild in (images or {}).items():
        if any(a.title == name for a in sections):
            continue
        teile.append(f"<h2>{_esc(name)}</h2>")
        teile.append(f'<div class="bild">{sanitise_svg(bild)}</div>')

    teile.append("<footer>")
    teile.append("<strong>Verwendete Einstellungen</strong><br>")
    for schluessel, wert in sorted((settings or {}).items()):
        teile.append(f"{_esc(schluessel)}: {_esc(wert)}<br>")
    teile.append(
        "Erzeugt von OligoLab. Keine KI, keine fremde Rechnung — alles lokal."
    )
    teile.append("</footer></body></html>")
    return "\n".join(teile)


def candidate_report(
    data: dict[str, Any], images: dict[str, str] | None = None
) -> str:
    """Den Bericht für einen Kandidaten bauen.

    `data` ist das, was die Oberflaeche ohnehin schon hat: Steckbrief,
    Entwurf, Geometrie. Hier wird nichts nachgerechnet — ein Bericht, der
    eigene Zahlen erzeugt, kann von der Anzeige abweichen, und dann glaubt
    man der falschen.
    """
    name = data.get("name") or "DNAzym"
    sequenz = data.get("sequence", "")
    abschnitte: list[ReportSection] = []

    abschnitte.append(
        ReportSection(
            "Sequenz",
            rows=[
                ("Schreibweise", sequenz, "Synthi-Sprache"),
                ("Bausteine", _number(data.get("length"), 0), "gezählt"),
                (
                    "Modifikationen",
                    ", ".join(data.get("modifications") or []) or "keine",
                    "aus der Sequenz",
                ),
            ],
        )
    )

    masse = data.get("mass") or {}
    ladungen = data.get("ms_ladder") or []
    abschnitte.append(
        ReportSection(
            "Masse und Massenspektrum",
            rows=[
                (
                    "vollständig entschützt",
                    _number(masse.get("fully_deprotected"), 2, "g/mol"),
                    masse.get("method", ""),
                ),
                ("+ DMT", _number(masse.get("with_dmt"), 2, "g/mol"), ""),
                ("+ 3'-Phosphat", _number(masse.get("with_phosphate"), 2, "g/mol"), ""),
                (
                    "Ladungsleiter",
                    " · ".join(
                        f"{e.get('charge')}− {_number(e.get('mz'), 1)}"
                        for e in ladungen[:6]
                    )
                    or "—",
                    "m/z",
                ),
            ],
        )
    )

    arme = data.get("arms") or {}
    abschnitte.append(
        ReportSection(
            "Arme und Bindung",
            rows=[
                ("Tm 5'-Arm", _number(arme.get("tm5"), 1, "°C"), arme.get("method", "")),
                ("Tm 3'-Arm", _number(arme.get("tm3"), 1, "°C"), ""),
                ("ΣΔG", _number(arme.get("dg_sum"), 2, "kcal/mol"), ""),
                ("Unterschied", _number(arme.get("imbalance"), 2, "kcal/mol"), ""),
                (
                    "Eigenfaltung",
                    _number(data.get("self_fold_mfe"), 2, "kcal/mol"),
                    "ViennaRNA, DNA-Parameter",
                ),
            ],
        )
    )

    stelle = data.get("site") or {}
    bewertung = data.get("rating")
    klasse, text = RATING_TEXT.get(str(bewertung), ("", "—"))
    abschnitte.append(
        ReportSection(
            "Spaltstelle und Bewertung",
            rows=[
                (
                    "Position",
                    f"{stelle.get('position', '—')}/{stelle.get('position', 0) + 1}"
                    if stelle.get("position")
                    else "—",
                    "im Ziel",
                ),
                ("Junktion", f"{stelle.get('junction', '—')} · {stelle.get('quality', '')}", ""),
                ("Zugänglichkeit", _number(stelle.get("accessibility"), 3), "RNAplfold"),
                ("Punktzahl", _number(data.get("score"), 3), "gewichtetes Mittel"),
                ("Ampel", text, "Rangfolge, keine Vorhersage"),
            ],
        )
    )

    geometrie = data.get("geometry") or {}
    inline = geometrie.get("inline") or {}
    if inline:
        winkel = inline.get("angle") or {}
        abschnitte.append(
            ReportSection(
                "Geometrie",
                rows=[
                    (
                        "In-line-Winkel",
                        _number(winkel.get("value"), 1, "°"),
                        winkel.get("method", ""),
                    ),
                    (
                        "2'-O bis P",
                        _number((inline.get("distance_attack") or {}).get("value"), 2, "Å"),
                        "",
                    ),
                    (
                        "P bis O5'",
                        _number((inline.get("distance_leaving") or {}).get("value"), 2, "Å"),
                        "",
                    ),
                    ("Beurteilung", inline.get("assessment") or "—", ""),
                ],
                note=inline.get("note"),
            )
        )

    befunde = data.get("findings") or []
    if befunde:
        abschnitte.append(
            ReportSection(
                "Befunde",
                rows=[
                    (
                        f"Position {b.get('position', '—')}",
                        str(b.get("level", "")),
                        str(b.get("message", "")),
                    )
                    for b in befunde
                ],
            )
        )

    hinweise = list(data.get("disclaimers") or [])
    return build_html(
        title=f"{name} — Gesamtbericht",
        sections=abschnitte,
        images=images,
        settings=data.get("settings") or {},
        disclaimers=hinweise,
    )
