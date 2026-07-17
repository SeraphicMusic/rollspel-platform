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


if __name__ == "__main__":
    unittest.main()
