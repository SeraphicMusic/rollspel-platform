"""Integrationstester för explicit, idempotent äventyrskonvertering."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.convert_adventure import (SourceError, WriteError,
                                        convert_adventure)


class TestConvertAdventure(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rippare-convert-"))
        self.source = self.tmp / "arbete" / "aventyr" / "export" / "bok.json"
        self.source.parent.mkdir(parents=True)
        self.book = {
            "generated": "2026-01-01T00:00:00Z",
            "source": {
                "path": "/original/aventyr.pdf",
                "metadata": {"title": "Provets torn"},
            },
            "system": {"id": "dod", "confidence": 1.0},
            "doc_type": {},
            "stats": {"pages": 1, "elements": 1, "needs_review": 2,
                      "missing_pages": []},
            "pages": [{"page": 1, "stage": "final",
                       "elements": [{
                           "id": "p001_e01", "type": "paragraph",
                           "text": "Simma 50%",
                           "source": {"page": 1, "region": "kolumn 1"},
                       }]}],
        }
        self.source.write_text(
            json.dumps(self.book, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_conversion(self, **kwargs):
        return convert_adventure(
            self.source, "dod-t100", "dod91",
            public_root=self.tmp / "konverterat", **kwargs)

    def test_complete_publish_and_source_unchanged(self):
        before = self.source.read_bytes()
        result = self.run_conversion()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(self.source.read_bytes(), before)
        state = Path(result["state_dir"])
        converted = json.loads(
            (state / "bok.konverterad.json").read_text(encoding="utf-8"))
        self.assertEqual(converted["conversion"]["status"], "complete")
        self.assertEqual(converted["conversion"]["counts"]["needs_review"], 0)
        self.assertEqual(
            converted["pages"][0]["elements"][0]["text"], "Simma FV 10")
        for path in result["published"]:
            self.assertTrue(Path(path).is_file())
        report = (state / "konverteringsrapport.md").read_text(
            encoding="utf-8")
        self.assertIn(
            "Befintliga granskningsposter från extraktionen: 2", report)

    def test_second_run_is_idempotent(self):
        first = self.run_conversion()
        manifest = Path(first["state_dir"]) / "manifest.json"
        before = manifest.read_bytes()
        second = self.run_conversion()
        self.assertTrue(second["skipped"])
        self.assertEqual(manifest.read_bytes(), before)

    def test_force_rebuilds_from_original_source(self):
        first = self.run_conversion()
        converted_path = Path(first["state_dir"]) / "bok.konverterad.json"
        damaged = json.loads(converted_path.read_text(encoding="utf-8"))
        damaged["pages"][0]["elements"][0]["text"] = "Simma FV 2"
        converted_path.write_text(json.dumps(damaged), encoding="utf-8")
        rebuilt = self.run_conversion(force=True)
        self.assertFalse(rebuilt["skipped"])
        converted = json.loads(converted_path.read_text(encoding="utf-8"))
        self.assertEqual(
            converted["pages"][0]["elements"][0]["text"], "Simma FV 10")

    def test_dry_run_writes_no_converted_book_or_publication(self):
        result = self.run_conversion(dry_run=True)
        state = Path(result["state_dir"])
        self.assertEqual(result["status"], "analyzed")
        self.assertTrue((state / "manifest.json").is_file())
        self.assertTrue((state / "analys.json").is_file())
        self.assertTrue((state / "konverteringsrapport.md").is_file())
        self.assertFalse((state / "bok.konverterad.json").exists())
        self.assertEqual(list((self.tmp / "konverterat").glob("**/*")), [])

    def test_interrupted_write_does_not_commit_manifest(self):
        with patch("pipeline.convert_adventure.atomic_write",
                   side_effect=OSError("simulerat avbrott")):
            with self.assertRaises(WriteError):
                self.run_conversion()
        state = (self.tmp / "arbete" / "aventyr" / "konvertering" /
                 "dod91" / "provets-torn")
        self.assertFalse((state / "manifest.json").exists())

    def test_unmatched_term_blocks_publication(self):
        self.book["pages"][0]["elements"][0]["text"] = "Flyga 55%"
        self.source.write_text(
            json.dumps(self.book, ensure_ascii=False), encoding="utf-8")
        result = self.run_conversion()
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["published"], [])

    def test_rejects_unfinished_merge(self):
        self.book["stats"]["missing_pages"] = [2]
        self.source.write_text(json.dumps(self.book), encoding="utf-8")
        with self.assertRaises(SourceError):
            self.run_conversion()

    def test_standard_prefix_is_not_duplicated(self):
        self.book["source"]["metadata"] = {}
        prefixed = (self.tmp / "arbete" / "DOD-AVE-provets-torn" /
                    "export" / "bok.json")
        prefixed.parent.mkdir(parents=True)
        prefixed.write_text(json.dumps(self.book), encoding="utf-8")
        result = convert_adventure(
            prefixed, "dod-t100", "dod91",
            public_root=self.tmp / "konverterat")
        self.assertTrue(any(
            Path(path).name == "DOD-AVE-provets-torn.json"
            for path in result["published"]))


if __name__ == "__main__":
    unittest.main()
