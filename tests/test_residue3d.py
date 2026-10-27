"""Eine eigene Base in 3D bauen (Ergänzung zu PHASEN.md 6.2).

Geprüft wird an einem Zucker mit bekannter Lage: die gebaute Base muss
dort hängen, wo die glykosidische Bindung sie hinzwingt — und das Rückgrat
darf sich dabei nicht bewegen.
"""

from __future__ import annotations

import math

import pytest

from app import model3d, pdb, residue3d
from app.notation import parse
from app.registry import save_monomer
from tests.structures import build_pdb

#: 2'-Desoxyguanosin und die Abwandlung: statt des O6 ein Imidazolring.
DG = "Nc1nc2n(cnc2c(=O)[nH]1)[C@H]1C[C@H](O)[C@@H](CO)O1"
IMIDAZOL_G = "Nc1nc2n(cnc2c(n3ccnc3)n1)[C@H]1C[C@H](O)[C@@H](CO)O1"

#: Ein Zucker mit brauchbaren Abständen — nicht gemessen, aber plausibel.
ZUCKER = {
    "C1'": (1.00, 0.00, 0.00),
    "C2'": (2.00, 0.80, 0.40),
    "C3'": (3.00, 0.00, 1.00),
    "C4'": (2.60, -1.30, 0.60),
    "O4'": (1.30, -1.20, 0.00),
}


def test_die_base_wird_gebaut():
    ergebnis = residue3d.graft(IMIDAZOL_G, ZUCKER)
    assert ergebnis.available is True
    assert ergebnis.atoms, "es müssen Atome herauskommen"
    assert ergebnis.formula == "C13H15N7O3"
    assert ergebnis.anchors == list(residue3d.SUGAR_NAMES)


def test_nur_die_base_kommt_zurueck():
    """Zucker und Phosphat bleiben die der Referenz — Regel des Fädelns."""
    ergebnis = residue3d.graft(IMIDAZOL_G, ZUCKER)
    namen = {name for name, *_ in ergebnis.atoms}
    assert not any("'" in name for name in namen), "kein Zuckeratom im Ergebnis"
    # Guanin hat 11 Schweratome, der Imidazolring bringt 4 dazu, das O6 fällt weg.
    assert len(ergebnis.atoms) == 15


def test_die_base_haengt_am_c1():
    """Die glykosidische Bindung muss stimmen, sonst schwebt die Base."""
    ergebnis = residue3d.graft(IMIDAZOL_G, ZUCKER)
    c1 = ZUCKER["C1'"]
    abstaende = sorted(
        math.dist(c1, (x, y, z)) for _, element, x, y, z in ergebnis.atoms
        if element == "N"
    )
    # Der nächste Stickstoff ist der glykosidische: rund 1,5 Å.
    assert 1.3 < abstaende[0] < 1.7


def test_der_zucker_passt_genau():
    ergebnis = residue3d.graft(IMIDAZOL_G, ZUCKER)
    assert ergebnis.rmsd is not None
    assert ergebnis.rmsd < 0.5, "sonst steht die Base schief"
    assert ergebnis.note is None


def test_schlechte_passung_wird_gemeldet():
    """Ein verzerrter Zucker darf nicht stillschweigend durchgehen."""
    verzerrt = dict(ZUCKER, **{"C3'": (9.0, 9.0, 9.0)})
    ergebnis = residue3d.graft(IMIDAZOL_G, verzerrt)
    assert ergebnis.available is True
    assert ergebnis.rmsd is not None and ergebnis.rmsd > 0.5
    assert "ungenauer" in (ergebnis.note or "")


def test_dieselbe_eingabe_gibt_dieselbe_geometrie():
    """Sonst sähe das Modell bei jedem Aufruf anders aus."""
    a = residue3d.graft(DG, ZUCKER)
    b = residue3d.graft(DG, ZUCKER)
    assert a.rmsd == pytest.approx(b.rmsd or 0.0, abs=1e-9)
    for (_, _, x1, y1, z1), (_, _, x2, y2, z2) in zip(a.atoms, b.atoms):
        assert (x1, y1, z1) == pytest.approx((x2, y2, z2), abs=1e-6)


def test_ohne_zucker_im_smiles():
    ergebnis = residue3d.graft("c1ccncc1", ZUCKER)
    assert ergebnis.available is False
    assert "Furanosering" in (ergebnis.note or "")
    assert "Nukleosid" in (ergebnis.note or "")


def test_unlesbares_smiles():
    ergebnis = residue3d.graft("kein smiles", ZUCKER)
    assert ergebnis.available is False
    assert "ließ sich nicht lesen" in (ergebnis.note or "")


def test_zu_wenige_ankerpunkte():
    ergebnis = residue3d.graft(IMIDAZOL_G, {"C1'": (0, 0, 0), "O4'": (1, 0, 0)})
    assert ergebnis.available is False
    assert "mindestens drei" in (ergebnis.note or "")


def test_drei_anker_genuegen():
    wenig = {name: ZUCKER[name] for name in ("C1'", "C3'", "O4'")}
    ergebnis = residue3d.graft(IMIDAZOL_G, wenig)
    assert ergebnis.available is True
    assert len(ergebnis.anchors) == 3


# ------------------------------------------- im Modell zusammengesetzt

KERN = "GGCTAGCTACAACGA"
REFERENZ = "TTGG" + KERN + "CATG"


@pytest.fixture
def eigener_baustein(data_dir, registry):
    """Einen eigenen Baustein anlegen, wie es der Nutzer täte."""
    import app.registry as registry_module

    save_monomer(
        {
            "code": "ImiG",
            "name": "Guanin mit Imidazol statt O6",
            "typ": "custom",
            "base_parent": "G",
            "core_tested": "unbekannt",
            "smiles": IMIDAZOL_G,
        },
        data_dir=data_dir,
    )
    registry_module._registry = None
    from app.registry import Registry

    return Registry(data_dir)


def test_eigener_baustein_landet_im_modell(eigener_baustein):
    """Der ganze Weg: Katalog → Sequenz → Modell → Atome."""
    text = build_pdb(REFERENZ, "ACGUACGUACGU")
    struktur = pdb.parse_structure(text, "TESTREF")
    oligo = parse("TTGG" + "GGCTA[ImiG]CTACAACGA" + "CATG", eigener_baustein)

    modell = model3d.thread(
        oligo, struktur, structure_text=text, registry=eigener_baustein
    )
    assert modell.available is True

    gebaut = [p for p in modell.positions if p.provenance == "gebaut"]
    assert len(gebaut) == 1
    assert gebaut[0].code == "IMIG"
    assert "aus dem SMILES gebaut" in (gebaut[0].note or "")

    atome = [
        a
        for a in pdb.atoms_of(modell.pdb)
        if a.chain == "A" and a.residue_number == gebaut[0].residue_number
    ]
    namen = {a.name for a in atome}
    # Das Rückgrat stammt weiter aus der Referenz …
    assert "P" in namen and "O4'" in namen and "C1'" in namen
    # … und die Base ist dazugekommen.
    assert len([a for a in atome if "'" not in a.name and a.name != "P"]) >= 14


def test_die_herkunft_steht_am_modell(eigener_baustein):
    text = build_pdb(REFERENZ, "ACGUACGUACGU")
    struktur = pdb.parse_structure(text, "TESTREF")
    oligo = parse("TTGG" + "GGCTA[ImiG]CTACAACGA" + "CATG", eigener_baustein)
    modell = model3d.thread(
        oligo, struktur, structure_text=text, registry=eigener_baustein
    )
    assert any("aus ihrem SMILES gebaut" in w for w in modell.warnings)
    assert modell.counts()["gebaut"] == 1


def test_ohne_smiles_wird_nichts_erfunden(data_dir, registry):
    """Ein eigener Baustein ohne SMILES bekommt keine gebaute Base."""
    import app.registry as registry_module
    from app.registry import Registry

    save_monomer(
        {"code": "Xyz", "name": "ohne Struktur", "typ": "custom",
         "base_parent": "G", "core_tested": "unbekannt"},
        data_dir=data_dir,
    )
    registry_module._registry = None
    eigene = Registry(data_dir)

    text = build_pdb(REFERENZ, "ACGUACGUACGU")
    struktur = pdb.parse_structure(text, "TESTREF")
    oligo = parse("TTGG" + "GGCTA[Xyz]CTACAACGA" + "CATG", eigene)
    modell = model3d.thread(oligo, struktur, structure_text=text, registry=eigene)
    assert "gebaut" not in modell.counts()
