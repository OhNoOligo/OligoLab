"""Die Endpunkte (PHASEN.md 1.8 — was die Oberflaeche braucht)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

from .conftest import (
    REFERENCE_CONSUMPTION_TOTAL,
    REFERENCE_MASSES,
    REFERENCE_SEQUENCE,
)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    antwort = client.get("/api/health")
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["status"] == "ok"
    assert daten["monomers"] >= 10


def test_profile_liefert_die_sollmassen(client):
    antwort = client.post("/api/profile", json={"sequence": REFERENCE_SEQUENCE})
    assert antwort.status_code == 200
    daten = antwort.json()

    assert daten["problems"] == []
    assert daten["oligo"]["length"] == 33
    assert daten["grouped"] == REFERENCE_SEQUENCE

    nach_schluessel = {m["key"]: m for m in daten["mass"]["masses"]}
    for schluessel, sollwert in REFERENCE_MASSES.items():
        assert nach_schluessel[schluessel]["value"] == pytest.approx(
            sollwert, abs=0.005
        )
        # CLAUDE.md, Regel 3: nie eine nackte Zahl.
        assert nach_schluessel[schluessel]["reliability"]
        assert nach_schluessel[schluessel]["method"]


def test_profile_enthaelt_alles_fuer_den_steckbrief(client):
    daten = client.post(
        "/api/profile", json={"sequence": REFERENCE_SEQUENCE}
    ).json()
    for block in ("mass", "exact", "comparison", "extinction", "synthesis"):
        assert daten[block] is not None, f"{block} fehlt"
    assert daten["exact"]["formula"] == "C325H405N131O196P32"
    assert len(daten["exact"]["isotopes"]) == 5
    assert len(daten["charge_ladder"]) == 14
    assert daten["synthesis"]["total"]["mass_mg"] == pytest.approx(
        REFERENCE_CONSUMPTION_TOTAL, abs=0.05
    )


def test_profile_rechnet_nicht_mit_fehlerhafter_sequenz(client):
    """Lieber keine Zahl als eine falsche (CLAUDE.md, Regel 5)."""
    daten = client.post("/api/profile", json={"sequence": "ACGX T"}).json()
    assert daten["problems"][0]["position"] == 4
    assert daten["problems"][0]["text"] == "X"
    assert daten["mass"] is None
    assert daten["exact"] is None


def test_parse_markiert_jede_stelle(client):
    """Die Oberflaeche braucht Start und Ende, um zu unterkringeln."""
    daten = client.post("/api/parse", json={"sequence": "ACGXTQ"}).json()
    assert [(p["position"], p["text"]) for p in daten["problems"]] == [
        (4, "X"), (6, "Q")
    ]
    for problem in daten["problems"]:
        assert problem["end"] == problem["start"] + 1


def test_parse_liefert_farbklasse_und_analogon(client):
    daten = client.post("/api/parse", json={"sequence": "A[LNA-T]O*G"}).json()
    monomere = daten["oligo"]["monomers"]
    assert [m["klasse"] for m in monomere] == ["dna", "zucker", "rna", "dna"]
    assert monomere[1]["base_parent"] == "T"
    assert monomere[1]["modifications"][0]["code"] == "LNA"
    # Das Phosphorothioat sitzt an der Bindung, nicht am Baustein.
    thioiert = [l for l in daten["oligo"]["linkages"] if l["kind"] == "phosphorothioate"]
    assert [l["position"] for l in thioiert] == [3]


def test_translate(client):
    antwort = client.post(
        "/api/translate", json={"sequence": "ACG T", "to": "rna"}
    )
    assert antwort.json()["sequence"] == "OIZ U"


def test_translate_meldet_fehler_statt_zu_uebersetzen(client):
    daten = client.post("/api/translate", json={"sequence": "ACGX", "to": "rna"}).json()
    assert daten["sequence"] is None
    assert daten["problems"][0]["text"] == "X"


def test_synthesis_einstellungen_wirken(client):
    daten = client.post(
        "/api/synthesis",
        json={"sequence": REFERENCE_SEQUENCE, "syntheses": 2, "reserve_fraction": 0.2},
    ).json()
    assert daten["total"]["mass_mg"] == pytest.approx(
        2 * REFERENCE_CONSUMPTION_TOTAL, abs=0.1
    )
    assert daten["total"]["mass_with_reserve_mg"] == pytest.approx(
        2 * REFERENCE_CONSUMPTION_TOTAL * 1.2, abs=0.1
    )
    assert "10 %" in daten["hint"]


def test_synthesis_mit_fehlerhafter_sequenz_ist_422(client):
    antwort = client.post("/api/synthesis", json={"sequence": "ACGX"})
    assert antwort.status_code == 422
    assert antwort.json()["detail"]["position"] == 4


def test_ms_ladder_bereich(client):
    daten = client.post(
        "/api/ms/ladder",
        json={"sequence": REFERENCE_SEQUENCE, "charge_min": 5, "charge_max": 8},
    ).json()
    assert [p["charge"] for p in daten["ladder"]] == [5, 6, 7, 8]
    assert daten["formula"] == "C325H405N131O196P32"


def test_ms_ladder_ungueltiger_bereich(client):
    antwort = client.post(
        "/api/ms/ladder",
        json={"sequence": "ACGT", "charge_min": 9, "charge_max": 3},
    )
    assert antwort.status_code == 422


def test_loading_page(client):
    daten = client.post(
        "/api/loading/page",
        json={"n_loading_pmol": 500, "n_stock_nmol": 50, "v_stock_ul": 100},
    ).json()
    assert daten["oligo_ul"]["value"] == pytest.approx(2.0)
    assert daten["water_ul"]["value"] == pytest.approx(8.0)
    assert daten["total_ul"] == pytest.approx(20.0)


def test_loading_lcms(client):
    daten = client.post(
        "/api/loading/lcms",
        json={
            "n_injection_pmol": 100, "n_stock_nmol": 50, "v_stock_ul": 100,
            "v_sample_ul": 50, "v_injection_ul": 5,
        },
    ).json()
    assert daten["oligo_ul"]["value"] == pytest.approx(2.0)
    assert daten["buffer_ul"] is None


def test_loading_warnt_bei_knappem_vial(client):
    daten = client.post(
        "/api/loading/page",
        json={"n_loading_pmol": 400, "n_stock_nmol": 1, "v_stock_ul": 5},
    ).json()
    assert daten["warnings"]


def test_concentration_od(client):
    daten = client.post(
        "/api/concentration/od",
        json={"eps260": 325400, "molar_mass": 10241.26, "od": 1.0},
    ).json()
    assert daten["nmol"]["value"] == pytest.approx(3.07, abs=0.01)
    assert daten["microgram"]["value"] == pytest.approx(31.47, abs=0.05)


def test_concentration_absorbance_braucht_genau_ein_feld(client):
    beides = client.post(
        "/api/concentration/absorbance",
        json={"eps260": 325400, "a260": 1.0, "conc_molar": 1e-6},
    )
    assert beides.status_code == 422
    keines = client.post(
        "/api/concentration/absorbance", json={"eps260": 325400}
    )
    assert keines.status_code == 422
    eines = client.post(
        "/api/concentration/absorbance", json={"eps260": 325400, "a260": 1.0}
    )
    assert eines.status_code == 200


def test_monomers_liste(client):
    daten = client.get("/api/monomers").json()
    codes = {m["code"] for m in daten["monomers"]}
    assert {"A", "C", "G", "T", "O", "I", "Z", "U", "E", "L"} <= codes
    nach_code = {m["code"]: m for m in daten["monomers"]}
    assert nach_code["A"]["mass_residue"] == 312.05
    assert nach_code["A"]["deviates_from_excel"] is False
    assert daten["protecting_groups"]["CE"]["mass"] == 53.03
    assert daten["termini"]["DMT"]["mass"] == 302.34


def test_modifications_liste(client):
    daten = client.get("/api/modifications").json()
    nach_code = {m["code"]: m for m in daten["modifications"]}
    assert nach_code["LNA"]["mass_diff"] == 12.0
    assert nach_code["5GalNAc"]["needs_review"] is True
    assert nach_code["5GalNAc"]["mass_diff"] is None


def test_neuer_baustein_braucht_masse_oder_smiles(client):
    antwort = client.post("/api/monomers", json={"code": "LEER"})
    assert antwort.status_code == 422
    assert "Restmasse" in antwort.json()["detail"]


def test_bibliothek_speichern_suchen_loeschen(client):
    angelegt = client.post(
        "/api/library/oligos",
        json={"name": "DZ-10-23", "sequence": REFERENCE_SEQUENCE, "notes": "Referenz"},
    )
    assert angelegt.status_code == 200
    record_id = angelegt.json()["id"]

    liste = client.get("/api/library/oligos").json()["oligos"]
    assert len(liste) == 1
    assert liste[0]["length"] == 33
    assert liste[0]["mass_fully_deprotected"] == pytest.approx(10241.26, abs=0.005)

    gefunden = client.get("/api/library/oligos", params={"q": "referenz"}).json()
    assert len(gefunden["oligos"]) == 1
    assert client.get("/api/library/oligos", params={"q": "nix"}).json()["oligos"] == []

    assert client.delete(f"/api/library/oligos/{record_id}").status_code == 200
    assert client.delete(f"/api/library/oligos/{record_id}").status_code == 404


def test_bibliothek_speichert_keine_fehlerhafte_sequenz(client):
    antwort = client.post(
        "/api/library/oligos", json={"name": "Kaputt", "sequence": "ACGX"}
    )
    assert antwort.status_code == 422
    assert antwort.json()["detail"]["problems"][0]["text"] == "X"
    assert client.get("/api/library/oligos").json()["oligos"] == []


def test_bibliothek_csv_export(client):
    client.post(
        "/api/library/oligos",
        json={"name": "DZ-10-23", "sequence": REFERENCE_SEQUENCE},
    )
    antwort = client.get("/api/library/oligos.csv")
    assert antwort.status_code == 200
    assert "text/csv" in antwort.headers["content-type"]
    zeilen = antwort.text.strip().splitlines()
    assert zeilen[0].startswith("Name;Sequenz")
    assert "DZ-10-23" in zeilen[1]


def test_probenliste(client):
    client.post(
        "/api/library/samples",
        json={"name": "Probe A", "n_stock_nmol": 50, "v_stock_ul": 100},
    )
    proben = client.get("/api/library/samples").json()["samples"]
    assert [p["name"] for p in proben] == ["Probe A"]
    assert client.delete(f"/api/library/samples/{proben[0]['id']}").status_code == 200


def test_hilfe_hat_eintraege_fuer_alle_namensraeume(client):
    eintraege = client.get("/api/help").json()["entries"]
    assert len(eintraege) >= 30
    for praefix in ("field.", "result.", "method."):
        assert any(k.startswith(praefix) for k in eintraege)
    for schluessel, eintrag in eintraege.items():
        assert eintrag.get("short"), f"{schluessel} ohne Kurztext"


# ----------------------------------------------- Eingaben, die abgewiesen werden


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_oligo_ohne_namen_wird_abgewiesen(client, name):
    """Gespeichert wird per Name — ein leerer Name liesse alle namenlosen
    Eintraege zu einem verschmelzen."""
    antwort = client.post(
        "/api/library/oligos", json={"name": name, "sequence": "ACGT"}
    )
    assert antwort.status_code == 422
    assert client.get("/api/library/oligos").json()["oligos"] == []


def test_name_wird_beschnitten(client):
    antwort = client.post(
        "/api/library/oligos", json={"name": "  DZ 1  ", "sequence": "ACGT"}
    )
    assert antwort.json()["name"] == "DZ 1"


def test_probe_ohne_namen_wird_abgewiesen(client):
    antwort = client.post(
        "/api/library/samples",
        json={"name": " ", "n_stock_nmol": 1, "v_stock_ul": 10},
    )
    assert antwort.status_code == 422


def test_baustein_mit_leerem_code_wird_abgewiesen(client):
    """Auch ein Code aus lauter Leerzeichen ist leer."""
    for code in ("", "   "):
        antwort = client.post("/api/monomers", json={"code": code, "mass_residue": 1})
        assert antwort.status_code == 422, code


@pytest.mark.parametrize("feld", ["od", "nmol", "microgram"])
def test_negative_stoffmenge_wird_abgewiesen(client, feld):
    antwort = client.post(
        "/api/concentration/od",
        json={"eps260": 1000, "molar_mass": 1000, feld: -5},
    )
    assert antwort.status_code == 422


def test_ladungsbereich_ist_nach_oben_begrenzt(client):
    assert (
        client.post(
            "/api/ms/ladder", json={"sequence": "ACGT", "charge_max": 500}
        ).status_code
        == 422
    )


def test_ladungsleiter_nennt_die_chemische_grenze(client):
    """Mehr negative Ladungen als Phosphate kann ein Oligo nicht tragen."""
    daten = client.post(
        "/api/ms/ladder", json={"sequence": "ACGT", "charge_max": 20}
    ).json()
    assert daten["max_physical_charge"] == 3
    assert "Phosphate" in daten["note"]

    ohne_hinweis = client.post(
        "/api/ms/ladder", json={"sequence": REFERENCE_SEQUENCE, "charge_max": 15}
    ).json()
    assert ohne_hinweis["note"] is None


def test_bibliothek_nennt_die_gesamtzahl(client):
    for index in range(3):
        client.post(
            "/api/library/oligos",
            json={"name": f"Oligo {index}", "sequence": "ACGT"},
        )
    assert client.get("/api/library/oligos").json()["total"] == 3
    assert client.get("/api/library/oligos", params={"q": "Oligo 1"}).json()["total"] == 1


def test_unbekannter_endpunkt_bleibt_404(client):
    """Der SPA-Rückfall darf keinen Tippfehler in einer Adresse verdecken."""
    assert client.get("/api/gibtesnicht").status_code == 404


def test_tests_schreiben_nicht_ins_echte_datenverzeichnis(client):
    """Ein angelegter Baustein darf nicht im Projektverzeichnis landen.

    Genau das ist einmal passiert: ein Probelauf schrieb einen Baustein mit
    dem Code '  ' in die echte `data/monomers_custom.yaml`, und sie wurde
    mitcommittet.
    """
    from .conftest import REAL_DATA_DIR

    antwort = client.post(
        "/api/monomers",
        json={"code": "TESTX", "name": "Nur für den Test", "mass_residue": 300.0},
    )
    assert antwort.status_code == 200

    # Geschrieben wurde in die Kopie, nicht ins Projektverzeichnis.
    assert not (REAL_DATA_DIR / "monomers_custom.yaml").exists()
    assert "TESTX" in {m["code"] for m in client.get("/api/monomers").json()["monomers"]}
