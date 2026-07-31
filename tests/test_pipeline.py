"""Tester för analys, rendering, textextraktion, state och systemdetektering."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from pipeline.analyze import analyze
from pipeline.detect_system import detect
from pipeline.extract_text import extract_text
from pipeline.jobs import ingest_transcripts, transcription_jobs
from pipeline.manifest import Manifest, page_file, read_json
from pipeline.render import render

from . import fixtures


class PipelineCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rippare-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def wd(self, name):
        return self.tmp / "arbete" / name


class TestAnalyze(PipelineCase):
    def test_text_pdf_klassas_digital(self):
        pdf = self.tmp / "text.pdf"
        fixtures.text_pdf(pdf)
        m = analyze(pdf, self.wd("text"))
        counts = m.data["doc_type"]["class_counts"]
        self.assertEqual(counts.get("digital_text"), 3)

    def test_bild_pdf_klassas_image_only(self):
        pdf = self.tmp / "bild.pdf"
        fixtures.image_pdf(pdf, watermark=False)
        m = analyze(pdf, self.wd("bild"))
        counts = m.data["doc_type"]["class_counts"]
        self.assertEqual(counts.get("image_only"), 3)

    def test_vattenstampel_ger_stub_text(self):
        pdf = self.tmp / "stub.pdf"
        fixtures.image_pdf(pdf, watermark=True)
        m = analyze(pdf, self.wd("stub"))
        counts = m.data["doc_type"]["class_counts"]
        self.assertEqual(counts.get("image_with_stub_text"), 3)
        self.assertIn(fixtures.WATERMARK,
                      m.data["doc_type"]["boilerplate"][0])

    def test_blandad_pdf(self):
        pdf = self.tmp / "mix.pdf"
        fixtures.mixed_pdf(pdf)
        m = analyze(pdf, self.wd("mix"))
        self.assertEqual(m.page(1)["class"], "digital_text")
        self.assertEqual(m.page(2)["class"], "image_only")
        self.assertEqual(m.page(3)["class"], "image_with_stub_text")

    def test_idempotent(self):
        pdf = self.tmp / "text.pdf"
        fixtures.text_pdf(pdf)
        m1 = analyze(pdf, self.wd("idem"))
        stamp = m1.data["created"]
        m2 = analyze(pdf, self.wd("idem"))
        self.assertEqual(m2.data["created"], stamp)


class TestRender(PipelineCase):
    def test_idempotent_och_atomisk(self):
        pdf = self.tmp / "bild.pdf"
        fixtures.image_pdf(pdf)
        wd = self.wd("bild")
        analyze(pdf, wd)
        done, skipped = render(pdf, wd)
        self.assertEqual((done, skipped), (3, 0))
        done, skipped = render(pdf, wd)
        self.assertEqual((done, skipped), (0, 3))
        # Simulerat avbrott: kvarlämnad .part-fil stör inte omkörning
        part = str(page_file(wd, 1, "png")) + ".part"
        Path(part).write_bytes(b"trasig")
        done, skipped = render(pdf, wd)
        self.assertEqual((done, skipped), (0, 3))

    def test_digital_text_renderas_inte(self):
        pdf = self.tmp / "text.pdf"
        fixtures.text_pdf(pdf)
        wd = self.wd("text")
        analyze(pdf, wd)
        done, skipped = render(pdf, wd)
        self.assertEqual((done, skipped), (0, 0))


class TestExtractText(PipelineCase):
    def test_kolumnordning(self):
        pdf = self.tmp / "kolumner.pdf"
        fixtures.two_column_pdf(pdf)
        wd = self.wd("kolumner")
        analyze(pdf, wd)
        extract_text(pdf, wd)
        data = read_json(page_file(wd, 1, "embedded.json"))
        text = " ".join(el["text"] for el in data["elements"])
        self.assertLess(text.find("VANSTER-09"), text.find("HOGER-00"),
                        "vänsterspalten ska komma före högerspalten")

    def test_sidnummer_och_sidhuvud_blir_artefakter(self):
        pdf = self.tmp / "text.pdf"
        fixtures.text_pdf(pdf)
        wd = self.wd("text")
        analyze(pdf, wd)
        extract_text(pdf, wd)
        data = read_json(page_file(wd, 2, "embedded.json"))
        artifacts = [el["text"] for el in data["elements"]
                     if el["type"] == "page_artifact"]
        self.assertTrue(any(a.strip() == "2" for a in artifacts),
                        "sidnumret ska vara page_artifact: %r" % artifacts)
        self.assertTrue(any("Regelboken" in a for a in artifacts),
                        "sidhuvudet ska vara page_artifact: %r" % artifacts)
        headings = [el for el in data["elements"] if el["type"] == "heading"]
        self.assertTrue(any("Kapitel 2" in el["text"] for el in headings))


class TestDetectSystem(PipelineCase):
    def test_dod_identifieras(self):
        pdf = self.tmp / "dod-aventyr.pdf"
        fixtures.dod_text_pdf(pdf)
        results = detect(pdf)
        self.assertEqual(results[0]["system"], "dod")
        self.assertGreater(results[0]["score"], results[1]["score"])


class TestTranscriptIngest(PipelineCase):
    def _setup_scanned(self):
        pdf = self.tmp / "bild.pdf"
        fixtures.image_pdf(pdf)
        wd = self.wd("bild")
        analyze(pdf, wd)
        render(pdf, wd)
        return wd

    def test_giltigt_transkript_bokfors(self):
        wd = self._setup_scanned()
        out = page_file(wd, 1, "transcript.json")
        out.write_text(json.dumps({
            "page": 1,
            "elements": [{"type": "paragraph", "text": "Hej"}],
        }), encoding="utf-8")
        ok, rejected = ingest_transcripts(wd)
        self.assertEqual(ok, [1])
        self.assertEqual(rejected, [])
        self.assertEqual(Manifest.load(wd).page(1)["state"], "transcribed")

    def test_ren_illustrationssida_kan_hoppas_over(self):
        wd = self._setup_scanned()
        out = page_file(wd, 1, "transcript.json")
        out.write_text(json.dumps({
            "page": 1,
            "layout": {"columns": 0},
            "elements": [],
            "skipped": {"reason": "illustration_only"},
        }), encoding="utf-8")
        ok, rejected = ingest_transcripts(wd)
        self.assertEqual(ok, [1])
        self.assertEqual(rejected, [])
        self.assertEqual(Manifest.load(wd).page(1)["state"], "transcribed")

    def test_tomt_transkript_utan_bildmarkering_avvisas(self):
        wd = self._setup_scanned()
        out = page_file(wd, 1, "transcript.json")
        out.write_text(json.dumps({"page": 1, "elements": []}),
                       encoding="utf-8")
        ok, rejected = ingest_transcripts(wd)
        self.assertEqual(ok, [])
        self.assertEqual(len(rejected), 1)
        self.assertIn("illustration_only", rejected[0][1])

    def test_trasigt_transkript_avvisas(self):
        wd = self._setup_scanned()
        out = page_file(wd, 1, "transcript.json")
        out.write_text(json.dumps({"page": 2, "elements": []}),
                       encoding="utf-8")
        ok, rejected = ingest_transcripts(wd)
        self.assertEqual(ok, [])
        self.assertEqual(len(rejected), 1)
        self.assertFalse(out.is_file(), ".rejected-omdöpning")
        # Sidan ska ligga kvar i jobblistan
        jobs = transcription_jobs(wd)
        self.assertIn(1, [j["page"] for j in jobs])


if __name__ == "__main__":
    unittest.main()
