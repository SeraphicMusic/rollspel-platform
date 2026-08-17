"""Tester för systemvalidering, statblock, formler samt end-to-end-flödet."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from pipeline.analyze import analyze
from pipeline.export import export_csv, export_markdown
from pipeline.jobs import ingest_transcripts, review_jobs
from pipeline.manifest import Manifest, page_file, read_json
from pipeline.merge import merge
from pipeline.render import render
from pipeline.report import build_report
from pipeline.systems import load
from pipeline.validate import eval_formula, validate, validate_element

from . import fixtures

DOD = load("dod")
M2089 = load("mutant2089")


class TestFormula(unittest.TestCase):
    def test_dod_kp(self):
        self.assertEqual(
            eval_formula("ceil((FYS + STO) / 2)", {"FYS": 11, "STO": 14}), 13)

    def test_saknat_namn_ger_none(self):
        self.assertIsNone(eval_formula("STO + FYS", {"STO": 10}))


class TestStatblockValidation(unittest.TestCase):
    def test_skadat_attributnamn_repareras(self):
        el = {"type": "statblock",
              "data": {"name": "Troll",
                       "stats": {"SIY": 18, "FYS": 12, "STO": 20}}}
        validate_element(el, DOD)
        self.assertIn("STY", el["data"]["stats"])
        self.assertNotIn("SIY", el["data"]["stats"])
        corr = el["corrections"][0]
        self.assertEqual((corr["original"], corr["corrected"]), ("SIY", "STY"))

    def test_varde_utanfor_intervall_flaggas(self):
        el = {"type": "statblock",
              "data": {"name": "Jätte", "stats": {"STY": 180}}}
        validate_element(el, DOD)
        self.assertTrue(el["needs_review"])
        self.assertTrue(any("utanför intervall" in r
                            for r in el["review_reasons"]))

    def test_mutant_kp_formel_korsvalideras(self):
        el = {"type": "statblock",
              "data": {"name": "Korp",
                       "stats": {"STO": 7, "FYS": 10, "KP": 99}}}
        validate_element(el, M2089)
        self.assertTrue(any("STO + FYS" in r for r in el["review_reasons"]))

    def test_forflyttning_i_other_korsvalideras(self):
        """Härledda fält står i `other`, inte i `stats` — och kontrolleras ändå.

        `Förflyttning` ligger i `data.other` i praktiskt taget varje statblock i
        materialet, medan `KP` ligger i `stats`. Så länge uppslaget bara gick i
        `stats` gällde derived_checks alltså KP men aldrig Förflyttning, utan
        att någonting sa ifrån. Sju avvikelser låg dolda bakom det.
        """
        el = {"type": "statblock",
              "data": {"name": "Franz", "stats": {"FYS": 14, "SMI": 17},
                       "other": {"Förflyttning": 32}}}
        validate_element(el, M2089)
        self.assertTrue(any("Förflyttning=32" in r and "FYS + SMI" in r
                            for r in el["review_reasons"]),
                        el.get("review_reasons"))

    def test_korrekt_forflyttning_i_other_flaggas_inte(self):
        el = {"type": "statblock",
              "data": {"name": "Franz", "stats": {"FYS": 14, "SMI": 17},
                       "other": {"Förflyttning": 31}}}
        validate_element(el, M2089)
        self.assertFalse(el.get("needs_review"), el.get("review_reasons"))

    def test_varde_med_enhet_kontrolleras_anda(self):
        """`29 m/SR` är ett tal med sin enhet, inte ett oläsbart värde.

        `_as_int` gav `None` för allt som inte var ett rent heltal, och
        `derived_checks` hoppade då över formeln TYST. KP fyrade (rent tal)
        medan `Förflyttning = FYS + SMI` aldrig gjorde det — kontrollen gällde
        halva sin lista och rapporten såg komplett ut. På
        MUT-AVE-terminal-state räknade advokaterna formeln för hand på nitton
        rutor och fann åtta avvikelser som ingen kod hade sett (BQ-001).
        """
        el = {"type": "statblock",
              "data": {"name": "Eldritch", "stats": {"FYS": 18, "SMI": 11},
                       "other": {"Förflyttning": "25 m/SR"}}}
        validate_element(el, M2089)
        self.assertTrue(any("Förflyttning" in r and "FYS + SMI" in r
                            for r in el.get("review_reasons") or []),
                        el.get("review_reasons"))

    def test_ratt_varde_med_enhet_flaggas_inte(self):
        el = {"type": "statblock",
              "data": {"name": "Eldritch", "stats": {"FYS": 18, "SMI": 11},
                       "other": {"Förflyttning": "29 m/SR"}}}
        validate_element(el, M2089)
        self.assertFalse(el.get("needs_review"), el.get("review_reasons"))

    def test_olasbart_varde_ger_flagga_inte_tystnad(self):
        """En ÖVERHOPPAD kontroll får aldrig se ut som en godkänd."""
        el = {"type": "statblock",
              "data": {"name": "Eldritch", "stats": {"FYS": 18, "SMI": 11},
                       "other": {"Förflyttning": "snabb"}}}
        validate_element(el, M2089)
        self.assertTrue(any("hoppades över" in r
                            for r in el.get("review_reasons") or []),
                        el.get("review_reasons"))

    def test_tarningsvarde_lases_inte_som_tal(self):
        """`3T6+2` får inte bli 3 — spärren mot att en formel räknar på en tärning."""
        el = {"type": "statblock",
              "data": {"name": "Gil", "stats": {"STO": 16, "FYS": 17},
                       "other": {"SB": "3T6+2", "KP": 33}}}
        validate_element(el, M2089)
        self.assertFalse(any("SB" in r and "hoppades över" in r
                             for r in el.get("review_reasons") or []),
                         el.get("review_reasons"))

    def test_kp_i_other_korsvalideras(self):
        """Samma fält kan hamna i `stats` hos en transkription och `other` hos
        nästa; skillnaden är inte en egenskap hos boken."""
        el = {"type": "statblock",
              "data": {"name": "Gil", "stats": {"STO": 16, "FYS": 17},
                       "other": {"KP": 37}}}
        validate_element(el, M2089)
        self.assertTrue(any("KP=37" in r for r in el["review_reasons"]),
                        el.get("review_reasons"))

    def test_mutant_procent_delbar_med_5(self):
        el = {"type": "statblock",
              "data": {"name": "Korp", "stats": {"STO": 7, "FYS": 10},
                       "skills": {"Datorkunskap": 37}}}
        validate_element(el, M2089)
        self.assertTrue(any("delbar med 5" in r for r in el["review_reasons"]))
        # 95 är OK
        el2 = {"type": "statblock",
               "data": {"name": "Korp", "stats": {"STO": 7, "FYS": 10},
                        "skills": {"Datorkunskap": 95}}}
        validate_element(el2, M2089)
        self.assertFalse(el2.get("needs_review"))

    def test_tabell_med_fel_cellantal_flaggas(self):
        el = {"type": "table",
              "data": {"headers": ["Vapen", "Skada"],
                       "rows": [["Svärd", "1T8"], ["Yxa"]]}}
        validate_element(el, DOD)
        self.assertTrue(any("celler" in r for r in el["review_reasons"]))

    def test_tarning_i_tabellcell_repareras(self):
        el = {"type": "table",
              "data": {"headers": ["Vapen", "Skada"],
                       "rows": [["Svärd", "ITG+2"]]}}
        validate_element(el, DOD)
        self.assertEqual(el["data"]["rows"][0][1], "1T6+2")


class TestStatblockAdapterluckor(unittest.TestCase):
    """Krugal BQ-002/004/008/009: luckor som gav falska larm eller tysta hål.

    Print-trogna värden (streck, bestiarieform, varelseintervall) får inte
    larma; de kontroller som FAKTISKT hittar tryckfel (sb_table, typvärde)
    måste finnas. En avvikelse flaggas alltid, rättas aldrig."""

    def test_streckvarde_ar_giltigt(self):
        """KAR — på odöda är tryckets "ej tillämpligt", inte ett läsfel."""
        el = {"type": "statblock",
              "data": {"name": "Skelett",
                       "stats": {"STY": 12, "STO": 10, "KAR": "—"}}}
        validate_element(el, DOD)
        self.assertFalse(any("inte ett tal" in r
                             for r in el.get("review_reasons", [])))

    def test_varelsevarden_flaggas_inte(self):
        """DRAKE STY 100 / JÄTTEBLÄCKFISK STO 125 / SPÖKE FYS 0 är tryckta."""
        el = {"type": "statblock",
              "data": {"name": "Drake",
                       "stats": {"STY": 100, "STO": 125, "FYS": 0}}}
        validate_element(el, DOD)
        self.assertFalse(any("utanför intervall" in r
                             for r in el.get("review_reasons", [])))

    def test_varde_over_varelseintervall_flaggas_fortfarande(self):
        el = {"type": "statblock",
              "data": {"name": "Jätte", "stats": {"STY": 180}}}
        validate_element(el, DOD)
        self.assertTrue(any("utanför intervall" in r
                            for r in el["review_reasons"]))

    def test_bestiarieform_godkanns_nar_kolumnerna_stammer(self):
        """`1T6+6 (10)`: medel 9,5 avrundas till 10 — formen är giltig."""
        el = {"type": "statblock",
              "data": {"name": "Vättar",
                       "stats": {"STY": "1T6+6 (10)", "SMI": "3T6 (11)"}}}
        validate_element(el, DOD)
        self.assertFalse(el.get("review_reasons"))

    def test_bestiarieform_avvikande_typvarde_ger_upplysning(self):
        """Megas SMI `1T4+11 (4)` (Krugal s. 16): medel 13,5 mot tryckt 4.

        UPPLYSNING, inte needs_review — trycket är print-troget."""
        el = {"type": "statblock",
              "data": {"name": "Megas", "stats": {"SMI": "1T4+11 (4)"}}}
        validate_element(el, DOD)
        self.assertTrue(any("typvärde" in n
                            for n in el.get("validation_notes", [])))
        self.assertFalse(el.get("needs_review"))

    def test_sb_streck_stammer_mot_sb_table(self):
        """STY+STO 22 ligger i raden 1–26 (bonus 0); tryckt `—` betyder 0."""
        el = {"type": "statblock",
              "data": {"name": "Zombie",
                       "stats": {"STY": 12, "STO": 10, "SB": "—"}}}
        validate_element(el, DOD)
        self.assertFalse(any("sb_table" in n
                             for n in el.get("validation_notes", [])))

    def test_sb_avvikelse_ger_upplysning_inte_flagga(self):
        """STY 15 + STO 13 = 28 ger +1 enligt tabellen; tryckt `—` avviker."""
        el = {"type": "statblock",
              "data": {"name": "Livsmästare",
                       "stats": {"STY": 15, "STO": 13, "SB": "—"}}}
        validate_element(el, DOD)
        self.assertTrue(any("sb_table" in n
                            for n in el["validation_notes"]))
        self.assertFalse(el.get("needs_review"))

    def test_sb_tarningsbonus_stammer_mot_sb_table(self):
        """STY 20 + STO 15 = 35 ger +1T4; tryckt `1T4` utan plus är samma värde."""
        el = {"type": "statblock",
              "data": {"name": "Troll",
                       "stats": {"STY": 20, "STO": 15, "SB": "1T4"}}}
        validate_element(el, DOD)
        self.assertFalse(any("sb_table" in n
                             for n in el.get("validation_notes", [])))

    def test_bestiarietabellens_ledarkolumn_flaggas_inte(self):
        """Tre datakolumner under två rubriker är tryckets form (BQ-009ii)."""
        el = {"type": "table",
              "data": {"headers": ["Grundegenskaper", "Typvärde"],
                       "rows": [["STY", "3T6+6", "17"],
                                ["STO", "2T6+6", "13"]]}}
        validate_element(el, DOD)
        self.assertFalse(any("celler" in r
                             for r in el.get("review_reasons", [])))

    def test_tabellburen_typvardesavvikelse_ger_upplysning(self):
        """Snaga STO `2T4+6` mot tryckt typvärde 8 (medel 11) — Krugal s. 17."""
        el = {"type": "table",
              "data": {"headers": ["Grundegenskaper", "Typvärde"],
                       "rows": [["STY", "2T6+3", "10"],
                                ["STO", "2T4+6", "8"]]}}
        validate_element(el, DOD)
        self.assertTrue(any("typvärde" in n
                            for n in el["validation_notes"]))
        self.assertFalse(el.get("needs_review"))

    def test_tabellburen_sb_avvikelse_ger_upplysning(self):
        """Uruk-hai (Krugal s. 17): STY 17 + STO 13 = 30 ger +1T2, tryckt 0."""
        el = {"type": "table",
              "data": {"headers": ["Grundegenskaper", "Typvärde"],
                       "rows": [["STY", "3T6+6", "17"],
                                ["STO", "2T6+6", "13"],
                                ["SB", "", "0"]]}}
        validate_element(el, DOD)
        self.assertTrue(any("sb_table" in n
                            for n in el["validation_notes"]))
        self.assertFalse(el.get("needs_review"))


class TestGeometrirapport(unittest.TestCase):
    """Sidor utan bbox måste synas — läsexporten tystnar annars om dem.

    `export.py` fogar aldrig ihop rader utan geometri, så varje tryckt rad
    blir ett eget stycke i `bok.md`. Det ser ut som smal, ihoptryckt sättning,
    texten är komplett och ingenting flaggas. Del II s. 8 föll ut så: en
    helsidesbred illustration i samma avsnitt som den tvåspaltiga satsen
    fyllde rännan, spalterna hittades inte, och samtliga 42 element blev utan
    bbox.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        source = self.tmp / "kalla.pdf"
        source.write_bytes(b"%PDF-1.4 attrapp")
        Manifest.create(self.tmp, source, 2)
        m = Manifest.load(self.tmp)
        for no in (1, 2):
            m.page(no)["state"] = "validated"
        m.save()

    def _skriv(self, no, elements):
        path = page_file(self.tmp, no, "final.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"page": no, "elements": elements}),
                        encoding="utf-8")

    def _rader(self, n, prefix, bbox=True):
        return [{"id": "%s_e%d" % (prefix, i), "type": "paragraph",
                 "text": "rad",
                 "source": ({"bbox": [0.1, 0.5, 0.4, 0.01]} if bbox
                            else {"bbox_saknas": "x"})} for i in range(n)]

    def test_sida_utan_geometri_listas(self):
        self._skriv(1, self._rader(4, "p1"))
        self._skriv(2, self._rader(4, "p2", bbox=False))
        rapport = build_report(self.tmp).read_text(encoding="utf-8")
        self.assertIn("Sidor utan användbar geometri", rapport)
        avsnitt = rapport.split("Sidor utan användbar geometri")[1]
        self.assertIn("| 2 | 4 | 4 |", avsnitt)
        self.assertNotIn("| 1 |", avsnitt.split("##")[0])

    def test_tyst_nar_all_geometri_finns(self):
        self._skriv(1, self._rader(4, "p1"))
        self._skriv(2, self._rader(4, "p2"))
        rapport = build_report(self.tmp).read_text(encoding="utf-8")
        self.assertNotIn("Sidor utan användbar geometri", rapport)


class TestAvgjordFlaggaIRapporten(unittest.TestCase):
    """En avgjord flagga håller inte elementet öppet, men den räknas.

    Del II bar 29 flaggor som var protokoll över UTFÖRDA kontroller ("671
    celler omlästa, inga fynd"). De listades som öppna punkter för alltid, och
    då drunknar de frågor som verkligen väntar på någon. Att radera
    beläggstexten vore i stället att kasta bort det som gör kontrollen
    spårbar — därför flyttas flaggan, den försvinner inte.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        source = self.tmp / "kalla.pdf"
        source.write_bytes(b"%PDF-1.4 attrapp")
        Manifest.create(self.tmp, source, 1)
        m = Manifest.load(self.tmp)
        m.page(1)["state"] = "validated"
        m.save()

    def _skriv(self, el):
        path = page_file(self.tmp, 1, "final.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"page": 1, "elements": [el]}),
                        encoding="utf-8")

    def test_oppen_flagga_listas(self):
        self._skriv({"id": "p001_e01", "type": "paragraph", "text": "x",
                     "review_reasons": ["geometrin ska verifieras"]})
        rapport = build_report(self.tmp).read_text(encoding="utf-8")
        self.assertIn("Flagga: geometrin ska verifieras", rapport)

    def test_avgjord_flagga_listas_inte_men_raknas(self):
        self._skriv({"id": "p001_e01", "type": "paragraph", "text": "x",
                     "review_reasons": [],
                     "resolved_reasons": [
                         {"reason": "geometrin ska verifieras",
                          "resolution": "omkopplad mot mätningen",
                          "closed_by": "pipeline.rows"}]})
        rapport = build_report(self.tmp).read_text(encoding="utf-8")
        self.assertNotIn("Flagga: geometrin ska verifieras", rapport)
        self.assertIn("1 avgjorda flaggor", rapport)

    def test_kvarvarande_oppen_flagga_haller_elementet_kvar(self):
        self._skriv({"id": "p001_e01", "type": "paragraph", "text": "x",
                     "review_reasons": ["den andra frågan"],
                     "resolved_reasons": [
                         {"reason": "den forsta", "resolution": "avgjord",
                          "closed_by": "skript"}]})
        rapport = build_report(self.tmp).read_text(encoding="utf-8")
        self.assertIn("Flagga: den andra frågan", rapport)
        self.assertIn("1 avgjorda flaggor", rapport)


class TestEndToEnd(unittest.TestCase):
    """Skanning -> transkript -> validering -> sammanfogning -> export."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rippare-e2e-"))
        self.pdf = self.tmp / "bok.pdf"
        fixtures.image_pdf(self.pdf, n_pages=3, watermark=True)
        self.wd = self.tmp / "arbete" / "bok"
        analyze(self.pdf, self.wd)
        render(self.pdf, self.wd)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_transcript(self, page_no, elements):
        out = page_file(self.wd, page_no, "transcript.json")
        out.write_text(json.dumps({"page": page_no, "elements": elements},
                                  ensure_ascii=False), encoding="utf-8")

    def test_hela_flodet(self):
        self._write_transcript(1, [
            {"type": "heading", "level": 1, "text": "Monster"},
            {"type": "paragraph",
             "text": "Trollet gör ITG i skada per lyckad Fardighet."},
            {"type": "statblock",
             "data": {"name": "Grottroll",
                      "stats": {"SIY": 18, "FYS": 12, "STO": 20},
                      "skills": {"Klubba": 14}}},
            {"type": "table",
             "data": {"headers": ["Vapen", "Skada"],
                      "rows": [["Klubba", "2T6"], ["Bett", "1T4"]]}},
            {"type": "page_artifact", "text": fixtures.WATERMARK},
        ])
        self._write_transcript(2, [
            {"type": "paragraph", "text": "Sida två utan konstigheter."},
        ])
        ok, rejected = ingest_transcripts(self.wd)
        self.assertEqual(ok, [1, 2])

        n_pages, n_corr, n_flags = validate(self.wd, DOD)
        self.assertEqual(n_pages, 2)
        self.assertGreaterEqual(n_corr, 2)  # ITG->1T6 (+ Fardighet, SIY)

        # Korrektur-triage (bantat team): tabell -> layoutverifierare;
        # advokaten (alltid sist) äger domänkontroll och forensik.
        jobs = review_jobs(self.wd)
        job1 = [j for j in jobs if j["page"] == 1][0]
        self.assertEqual(job1["agents"],
                         ["sprakgranskare", "layoutverifierare", "djavulens-advokat"])
        job2 = [j for j in jobs if j["page"] == 2][0]
        self.assertEqual(job2["agents"],
                         ["sprakgranskare", "djavulens-advokat"])

        book, path = merge(self.wd)
        self.assertEqual(book["stats"]["pages"], 2)
        self.assertIn(3, book["stats"]["missing_pages"])

        # Spårbarhet: ITG-korrektionen finns bokförd med original kvar
        page1 = [p for p in book["pages"] if p["page"] == 1][0]
        all_corr = [c for el in page1["elements"]
                    for c in el.get("corrections", [])]
        itg = [c for c in all_corr if c["original"] == "ITG"]
        self.assertEqual(len(itg), 1)
        self.assertEqual(itg[0]["corrected"], "1T6")

        report = build_report(self.wd)
        text = report.read_text(encoding="utf-8")
        self.assertIn("ITG", text)

        md = export_markdown(self.wd)
        md_text = md.read_text(encoding="utf-8")
        self.assertIn("## Monster", md_text)
        self.assertIn("1T6", md_text)
        self.assertNotIn(fixtures.WATERMARK, md_text,
                         "artefakter ska inte med i läsexporten")

        outdir, n_tables = export_csv(self.wd)
        self.assertEqual(n_tables, 1)

    def test_omkorning_gor_ingenting(self):
        self._write_transcript(1, [{"type": "paragraph", "text": "Text."}])
        ingest_transcripts(self.wd)
        validate(self.wd, DOD)
        first = read_json(page_file(self.wd, 1, "validated.json"))
        n_pages, _, _ = validate(self.wd, DOD)
        self.assertEqual(n_pages, 0, "redan validerad sida ska inte köras om")
        second = read_json(page_file(self.wd, 1, "validated.json"))
        self.assertEqual(first, second)

    def test_illustrationssida_bevaras_utan_korrekturjobb(self):
        out = page_file(self.wd, 1, "transcript.json")
        out.write_text(json.dumps({
            "page": 1,
            "layout": {"columns": 0},
            "elements": [],
            "skipped": {"reason": "illustration_only"},
        }), encoding="utf-8")
        ok, rejected = ingest_transcripts(self.wd)
        self.assertEqual(ok, [1])
        self.assertEqual(rejected, [])

        validate(self.wd, DOD)
        validated = read_json(page_file(self.wd, 1, "validated.json"))
        self.assertEqual(validated["skipped"]["reason"], "illustration_only")
        self.assertEqual(review_jobs(self.wd), [])

        book, _ = merge(self.wd)
        page = [p for p in book["pages"] if p["page"] == 1][0]
        self.assertEqual(page["elements"], [])
        self.assertEqual(page["skipped"]["reason"], "illustration_only")


if __name__ == "__main__":
    unittest.main()


class TestForslagensTreLagen(unittest.TestCase):
    """Rapporten måste skilja odömda förslag från dömda och överspelade.

    Ett avvisat förslag ligger kvar med `applied: false` för spårbarheten.
    Listades allt utan åtskillnad drunknade det som verkligen väntade på
    någon: del I hade 336 granskningsposter, varav 131 var förslag vars text
    inte ens fanns kvar i elementet.
    """

    def _post(self, original, **extra):
        post = {"original": original, "corrected": "rättat", "applied": False,
                "confidence": 0.6, "reason": "…", "source": "agent:x",
                "kind": "ocr"}
        post.update(extra)
        return post

    def test_overspelat_nar_originalet_inte_finns_kvar(self):
        from pipeline.report import VERDICT_SUPERSEDED, _proposal_state
        el = {"type": "paragraph", "text": "texten är omskriven"}
        post = self._post("gammal lydelse")
        el["corrections"] = [post]
        self.assertEqual(_proposal_state(el, post), VERDICT_SUPERSEDED)

    def test_null_original_kraschar_inte_rapporten(self):
        """Tempokalkylatorns syntetiska TILLÄGG-rubriker skrevs med
        `original: null`, och rapporten kraschade på `None not in str` —
        vilket dolde hela bokens redovisning i stället för den ena raden.
        En null-original behandlas som tom sträng och döms på sitt verdict."""
        from pipeline.report import VERDICT_JUDGED, _proposal_state
        el = {"type": "table", "text": ""}
        post = self._post("gammal")
        post["original"] = None
        post["verdict"] = "avvisad"
        el["corrections"] = [post]
        self.assertEqual(_proposal_state(el, post), VERDICT_JUDGED)

    def test_posten_matchar_inte_sig_sjalv(self):
        """Utan undantaget för `corrections` blir inget någonsin överspelat."""
        from pipeline.report import VERDICT_SUPERSEDED, _proposal_state
        el = {"type": "paragraph", "text": "ny text",
              "corrections": [self._post("gammal lydelse")]}
        self.assertEqual(_proposal_state(el, el["corrections"][0]),
                         VERDICT_SUPERSEDED)

    def test_odomt_nar_forslaget_fortfarande_galler(self):
        from pipeline.report import VERDICT_OPEN, _proposal_state
        el = {"type": "paragraph", "text": "en gammal lydelse står kvar"}
        post = self._post("gammal lydelse")
        el["corrections"] = [post]
        self.assertEqual(_proposal_state(el, post), VERDICT_OPEN)

    def test_domt_nar_advokaten_skrivit_ned_domen(self):
        from pipeline.report import VERDICT_JUDGED, _proposal_state
        el = {"type": "paragraph", "text": "en gammal lydelse står kvar"}
        post = self._post("gammal lydelse", verdict="avvisad",
                          adjudicated_by="agent:djavulens-advokat")
        el["corrections"] = [post]
        self.assertEqual(_proposal_state(el, post), VERDICT_JUDGED)

    def test_forslag_i_tabellceller_hittas(self):
        """Originalet ligger i `data`, inte i `text`, för tabeller och listor."""
        from pipeline.report import VERDICT_OPEN, _proposal_state
        el = {"type": "table", "data": {"headers": ["a"],
                                        "rows": [["gammal lydelse"]]}}
        post = self._post("gammal lydelse")
        el["corrections"] = [post]
        self.assertEqual(_proposal_state(el, post), VERDICT_OPEN)
