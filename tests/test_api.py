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


# ------------------------------------------------------------ Seite "Strang"


def test_strand_liefert_bauteile_faltung_und_befunde(client):
    daten = client.post("/api/strand", json={"sequence": REFERENCE_SEQUENCE}).json()

    teile = daten["parts"]
    assert teile["found"] is True
    assert teile["core"]["id"] == "10-23"
    assert [(p["kind"], p["start"], p["end"]) for p in teile["parts"]] == [
        ("arm5", 1, 9),
        ("core", 10, 24),
        ("arm3", 25, 33),
    ]

    faltung = daten["folding"]
    assert faltung["available"] is True
    assert len(faltung["structure"]) == 33
    assert len(faltung["unpaired"]) == 33
    assert faltung["mfe"]["unit"] == "kcal/mol"
    assert faltung["reliability"] == "Parameter vorhanden"

    befunde = daten["critical"]
    assert befunde["counts"]["kritisch"] == 0
    assert befunde["thresholds"]["hairpin_kcal"] == -2.0


def test_strand_meldet_lna_im_kern_als_kritisch(client):
    """Der Testfall aus PHASEN.md, über den Endpunkt."""
    daten = client.post(
        "/api/strand",
        json={"sequence": "TTGGGGTAAGGC[LNA-T]AGCTACAACGAGGTGCATGT"},
    ).json()

    kritisch = [f for f in daten["critical"]["findings"] if f["severity"] == "kritisch"]
    assert len(kritisch) == 1
    assert kritisch[0]["code"] == "core_modification"
    assert kritisch[0]["start"] == 13
    assert daten["critical"]["worst"] == "kritisch"
    # Die Faltung läuft über das Analogon und sagt das.
    assert daten["folding"]["reliability"] == "genähert über natürliches Analogon"


def test_strand_rechnet_nicht_mit_fehlerhafter_sequenz(client):
    daten = client.post("/api/strand", json={"sequence": "ACGX"}).json()
    assert daten["problems"][0]["position"] == 4
    assert daten["parts"] is None
    assert daten["folding"] is None
    assert daten["critical"] is None


def test_strand_ohne_kern_ist_kein_fehler(client):
    daten = client.post("/api/strand", json={"sequence": "ACACACACACAC"}).json()
    assert daten["parts"]["found"] is False
    assert daten["folding"]["available"] is True
    assert any("kein katalytischer Kern" in e for e in daten["critical"]["skipped"])


def test_homodimer_abschaltbar(client):
    daten = client.post(
        "/api/strand",
        json={"sequence": REFERENCE_SEQUENCE, "with_homodimer": False},
    ).json()
    assert daten["folding"]["homodimer_energy"] is None


def test_cores_endpunkt(client):
    kerne = client.get("/api/cores").json()["cores"]
    assert [k["id"] for k in kerne] == ["10-23"]
    assert kerne[0]["sequence"] == "GGCTAGCTACAACGA"
    assert kerne[0]["quelle"]


# ------------------------------------------------------------ Seite "Ziel"


def test_target_read_erkennt_das_format(client):
    """`auto` erkennt FASTA am `>`, GenBank am `LOCUS`, sonst Rohtext."""
    rein = client.post("/api/target/read", json={"text": "ACGT ACGT"}).json()
    assert rein["detected_format"] == "plain"
    assert rein["target"]["sequence"] == "ACGUACGU"

    fasta = client.post(
        "/api/target/read", json={"text": ">NM_1 Beschreibung\nACGTACGT\n"}
    ).json()
    assert fasta["detected_format"] == "fasta"
    assert fasta["target"]["identifier"] == "NM_1"


def test_target_read_meldet_unbekanntes_zeichen_mit_position(client):
    antwort = client.post("/api/target/read", json={"text": "ACGXT"})
    assert antwort.status_code == 422
    assert antwort.json()["detail"]["position"] == 4
    assert antwort.json()["detail"]["character"] == "X"


def test_target_fetch_ohne_netz_ist_kein_http_fehler(client, monkeypatch):
    """CLAUDE.md, Regel 4: ohne Netz bleibt die App voll bedienbar."""
    import httpx

    monkeypatch.setattr(
        httpx.Client, "get",
        lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("kein Netz")),
    )
    antwort = client.post(
        "/api/target/fetch", json={"source": "ensembl", "identifier": "TP53"}
    )
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["available"] is False
    assert "nicht erreichbar" in daten["message"]


def test_target_fold_und_accessibility(client):
    sequenz = "AAAAAAAAAAAAAAAAAAAAAAAAAA" + "GGGGGCCCCUUUUGGGGCCCCC"

    faltung = client.post("/api/target/fold", json={"sequence": sequenz}).json()
    assert faltung["available"] is True
    assert faltung["mfe"]["unit"] == "kcal/mol"
    assert "RNA-Parametern" in faltung["mfe"]["method"]

    profil = client.post(
        "/api/target/accessibility",
        json={"sequence": sequenz, "probe_length": 10},
    ).json()
    assert profil["available"] is True
    assert len(profil["profile"]) == len(sequenz)
    assert profil["profile"][0] > 0.9          # offener Anfang
    assert profil["profile"][30] < 0.05        # im Stamm
    assert profil["profile"][-1] is None       # kein volles Fenster mehr
    assert "Fensteranfang" in profil["method"]


def test_accessibility_weist_unsinnige_einstellungen_ab(client):
    antwort = client.post(
        "/api/target/accessibility",
        json={"sequence": "ACGUACGU", "probe_length": 50, "window": 10},
    )
    assert antwort.status_code == 422


def test_target_up(client):
    sequenz = "AAAAAAAAAAAAAAAAAAAAAAAAAA" + "GGGGGCCCCUUUUGGGGCCCCC"
    daten = client.post(
        "/api/target/up",
        json={
            "target_sequence": sequenz,
            "site_start": 1,
            "site_end": 10,
            "oligo_sequence": "TTTTTTTTTT",
        },
    ).json()
    assert daten["available"] is True
    assert daten["hybridisation"]["value"] < 0
    # Der Vorbehalt steht an jeder Zahl.
    assert "MELTING" in daten["hybridisation"]["note"]


def test_zielbibliothek(client):
    angelegt = client.post(
        "/api/library/targets",
        json={
            "name": "TP53 Transkript",
            "sequence": "ACGTACGT",
            "source": "ncbi",
            "identifier": "NM_000546",
            "organism": "Homo sapiens",
            "regions": [{"kind": "cds", "start": 1, "end": 8, "label": "CDS"}],
        },
    )
    assert angelegt.status_code == 200
    record_id = angelegt.json()["id"]

    liste = client.get("/api/library/targets").json()
    assert liste["total"] == 1
    eintrag = liste["targets"][0]
    # Beim Speichern wird normalisiert: T wird zu U.
    assert eintrag["sequence"] == "ACGUACGU"
    assert eintrag["identifier"] == "NM_000546"
    assert eintrag["regions"][0]["kind"] == "cds"

    assert client.get("/api/library/targets", params={"q": "NM_000"}).json()["total"] == 1
    assert client.get("/api/library/targets", params={"q": "nix"}).json()["total"] == 0

    assert client.delete(f"/api/library/targets/{record_id}").status_code == 200
    assert client.delete(f"/api/library/targets/{record_id}").status_code == 404


def test_ziel_ohne_namen_wird_abgewiesen(client):
    antwort = client.post(
        "/api/library/targets", json={"name": "  ", "sequence": "ACGU"}
    )
    assert antwort.status_code == 422


# ================================================ Phase 5: Entwurfsseite

#: Ein kurzes Ziel mit einer GU-Junktion in der Mitte.
ZIEL = "ACACCACACCACACGUACCACACCACACCA"
DNAZYM = "TTGGGGTAAGGCTAGCTACAACGAGGTGCATGT"


def test_schmelztemperatur_eines_arms(client):
    antwort = client.post("/api/melting", json={"sequence": "TTGGGGTAA"})
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["available"] is True
    assert 20 < daten["tm"]["value"] < 60
    assert "DNA/RNA" in daten["tm"]["method"]


def test_schmelztemperatur_eines_modifizierten_arms(client):
    """Die Näherung muss in der Antwort stehen (CLAUDE.md, Regel 3)."""
    antwort = client.post("/api/melting", json={"sequence": "TTGG[LNA-T]GTAA"})
    daten = antwort.json()
    assert daten["reliability"] == "genähert über natürliches Analogon"
    assert any("LNA" in e for e in daten["approximated"])


def test_schmelztemperatur_mit_kaputter_sequenz(client):
    assert client.post("/api/melting", json={"sequence": "ACGX"}).status_code == 422


def test_spaltstellen_suchen(client):
    antwort = client.post("/api/scan", json={"sequence": ZIEL, "with_structure": False})
    assert antwort.status_code == 200
    daten = antwort.json()
    positionen = [s["position"] for s in daten["scan"]["sites"]]
    assert ZIEL.index("GU") + 1 in positionen
    assert daten["folding"] is None and daten["accessibility"] is None


def test_schlechte_junktionen_werden_gezaehlt_nicht_verschwiegen(client):
    """AC ist ausgeblendet, aber die Zahl steht dabei (PHASEN.md 5.2)."""
    ohne = client.post(
        "/api/scan", json={"sequence": ZIEL, "with_structure": False}
    ).json()["scan"]
    assert ohne["hidden_poor"] > 0
    assert "AC" in (ohne["note"] or "")

    mit = client.post(
        "/api/scan",
        json={"sequence": ZIEL, "with_structure": False, "include_poor": True},
    ).json()["scan"]
    assert len(mit["sites"]) == len(ohne["sites"]) + ohne["hidden_poor"]
    assert mit["hidden_poor"] == 0


def test_entwurf_liefert_kandidaten_und_profil(client):
    """Eine Antwort muss für Tabelle UND Kurve reichen (PHASEN.md 5.6)."""
    antwort = client.post("/api/design", json={"sequence": ZIEL})
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["candidates"], "es muss Kandidaten geben"
    assert daten["accessibility"] is not None, "die Kurve kommt mit"
    assert daten["core"]["id"]
    assert daten["disclaimer"]

    bester = daten["candidates"][0]
    assert len(bester["arm5"]) == 9 and len(bester["arm3"]) == 9
    assert bester["rating"] in {"good", "warn", "bad"}
    assert bester["criteria"], "jedes Kriterium einzeln, nicht nur die Summe"


def test_entwurf_mit_eigenen_armlaengen(client):
    antwort = client.post(
        "/api/design",
        json={
            "sequence": ZIEL,
            "with_structure": False,
            "settings": {"arm5_length": 7, "arm3_length": 11},
        },
    )
    bester = antwort.json()["candidates"][0]
    assert len(bester["arm5"]) == 7
    assert len(bester["arm3"]) == 11


def test_unsinnige_armlaenge_wird_abgewiesen(client):
    antwort = client.post(
        "/api/design", json={"sequence": ZIEL, "settings": {"arm5_length": 2}}
    )
    assert antwort.status_code == 422


def test_kandidaten_als_csv(client):
    antwort = client.post("/api/design/candidates.csv", json={"sequence": ZIEL})
    assert antwort.status_code == 200
    zeilen = antwort.text.splitlines()
    assert zeilen[0].startswith("# ")
    assert "Rangfolge" in zeilen[0], "der Hinweis steht über der Tabelle"
    assert zeilen[1].startswith("Rang;Position;Junktion")
    assert len(zeilen) > 2
    # Deutsches Dezimalkomma, und kein Objekt im Text.
    assert "Quantity" not in antwort.text
    felder = zeilen[2].split(";")
    assert felder[0] == "1"
    assert "," in felder[6], "ΔG muss eine Zahl mit Komma sein"


def test_muster_aufbringen_mit_vorher_nachher(client):
    antwort = client.post(
        "/api/modify",
        json={
            "sequence": DNAZYM, "pattern": "lna_ends",
            "core_start": 10, "core_end": 24, "count": 3,
        },
    )
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["modification"]["blocked"] is False
    assert daten["modification"]["touched_core"] is False
    assert daten["before"]["mass"] == pytest.approx(10241.26, abs=0.01)
    assert daten["after"]["mass"] - daten["before"]["mass"] == pytest.approx(72, abs=0.1)
    # Der Tm bleibt gleich — und die Antwort sagt, warum.
    assert daten["after"]["tm5"] == pytest.approx(daten["before"]["tm5"], abs=0.01)
    assert len(daten["after"]["tm_approximated"]) == 6


def test_eingriff_im_kern_wird_blockiert_aber_ist_kein_fehler(client):
    """CLAUDE.md, Regel 6 — die Oberfläche soll nachfragen können."""
    antwort = client.post(
        "/api/modify",
        json={
            "sequence": DNAZYM, "pattern": "replace_position",
            "core_start": 10, "core_end": 24, "position": 13, "code": "LNA",
        },
    )
    assert antwort.status_code == 200, "kein HTTP-Fehler, sondern eine Rückfrage"
    daten = antwort.json()
    assert daten["modification"]["blocked"] is True
    assert daten["modification"]["sequence"] == DNAZYM
    assert "Kern" in daten["modification"]["message"]
    assert "before" not in daten, "ohne Änderung gibt es nichts zu vergleichen"


def test_eingriff_im_kern_nach_bestaetigung(client):
    antwort = client.post(
        "/api/modify",
        json={
            "sequence": DNAZYM, "pattern": "replace_position",
            "core_start": 10, "core_end": 24, "position": 13, "code": "LNA",
            "allow_core": True,
        },
    )
    daten = antwort.json()["modification"]
    assert daten["blocked"] is False
    assert daten["touched_core"] is True
    assert "ACHTUNG" in daten["message"]


def test_unbekanntes_muster_ist_ein_fehler(client):
    antwort = client.post(
        "/api/modify", json={"sequence": DNAZYM, "pattern": "frei erfunden"}
    )
    assert antwort.status_code == 422


def test_zwei_straenge_vergleichen(client):
    antwort = client.post(
        "/api/compare",
        json={"before": DNAZYM, "after": "/5GalNAc/" + DNAZYM},
    )
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["before"]["length"] == daten["after"]["length"] == 33
    # GalNAc hat keine hinterlegte Masse — die Antwort erfindet keine.
    assert daten["after"]["mass"] is None or daten["after"]["mass"] > 0


def test_musterliste(client):
    daten = client.get("/api/design/patterns").json()
    kennungen = {m["id"] for m in daten["patterns"]}
    assert "arms_phosphorothioate" in kennungen
    assert "lna_ends" in kennungen
    assert daten["disclaimer"]


def test_kernschutz_auch_ohne_mitgeschickten_kern(client):
    """Regression: ein vergessener Parameter gab den Kern nicht frei."""
    antwort = client.post(
        "/api/modify",
        json={
            "sequence": DNAZYM,
            "pattern": "replace_position",
            "position": 13,
            "code": "LNA",
        },
    )
    daten = antwort.json()["modification"]
    assert daten["blocked"] is True
    assert daten["sequence"] == DNAZYM


def test_schlechte_junktionen_auch_ueber_die_einstellungen(client):
    """Regression: `settings.include_poor_junctions` wurde überschrieben."""
    daten = client.post(
        "/api/design",
        json={
            "sequence": ZIEL,
            "with_structure": False,
            "settings": {"include_poor_junctions": True},
        },
    ).json()
    assert daten["settings"]["include_poor_junctions"] is True
    assert daten["scan"]["hidden_poor"] == 0
