"""Rapporten listar osäkerheter läsaren kan MÖTA — inte spöken.

Ett `removed: true`-element når aldrig läsexporten, så låg confidence på det
är ingen osäkerhet för någon läsare. Sypox s. 8:s strukna sidfot (confidence
0,3, noll öppna frågor) listades ändå i varje rapport som falsk
lågkonfidenspost. Öppna flaggor på ett borttaget element ska däremot synas —
en öppen fråga om själva borttagandet är en riktig fråga.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from pipeline.manifest import Manifest
from pipeline.report import build_report


class Rapportbadd(unittest.TestCase):
    def setUp(self):
        self.wd = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.wd, ignore_errors=True)
        (self.wd / "pages").mkdir()
        pdf = self.wd / "kalla.pdf"
        pdf.write_bytes(b"%PDF-1.4 testfixtur")
        Manifest.create(self.wd, pdf, 1).save()

    def rapport(self, elements):
        (self.wd / "pages" / "page_001.final.json").write_text(
            json.dumps({"page": 1, "elements": elements}), encoding="utf-8")
        return build_report(self.wd).read_text(encoding="utf-8")


class TestBevaradePrintFynd(Rapportbadd):
    def test_print_fynd_markering_ger_egen_sektion(self):
        """BQ-006(c), fastställt 2026-08-12: bevarade sättningsfel märks
        aldrig i läsexporten — granskningsrapportens sektion är facit. En
        resolved_reason vars resolution bär PRINT-FYND-prefixet listas i
        sektionen; en vanlig avgjord flagga gör det inte."""
        md = self.rapport([
            {"id": "e03", "type": "paragraph", "text": "har absorberar",
             "confidence": 0.95,
             "resolved_reasons": [{
                 "reason": "dubbelt hjälpverb, pixelverifierat",
                 "resolution": "PRINT-FYND: 'har absorberar' — dubbelt "
                               "hjälpverb i trycket, bevaras ordagrant.",
                 "closed_by": "session:test"}]},
            {"id": "e04", "type": "paragraph", "text": "vanlig text",
             "confidence": 0.95,
             "resolved_reasons": [{
                 "reason": "kollad", "resolution": "ingen åtgärd",
                 "closed_by": "session:test"}]},
        ])
        self.assertIn("## Bevarade print-fynd", md)
        self.assertIn("dubbelt \nhjälpverb i trycket".replace("\n", ""), md)
        sektion = md.split("## Bevarade print-fynd")[1].split("## ")[0]
        self.assertIn("e03", sektion)
        self.assertNotIn("e04", sektion)

    def test_utan_fynd_star_sektionen_tom(self):
        md = self.rapport([{"id": "e01", "type": "paragraph",
                            "text": "ren sida", "confidence": 0.95}])
        sektion = md.split("## Bevarade print-fynd")[1].split("## ")[0]
        self.assertIn("| — | — | — |", sektion)


class TestBorttagnaElement(Rapportbadd):
    def test_borttaget_lagkonfidenselement_listas_inte(self):
        md = self.rapport([{"id": "e10", "type": "page_artifact",
                            "text": "SIDFOT", "removed": True,
                            "confidence": 0.3}])
        self.assertNotIn("e10", md)

    def test_borttaget_element_med_oppen_flagga_listas(self):
        md = self.rapport([{"id": "e10", "type": "page_artifact",
                            "text": "SIDFOT", "removed": True,
                            "confidence": 0.3, "needs_review": True,
                            "review_reasons": ["är borttagandet rätt?"]}])
        self.assertIn("e10", md)

    def test_kvarvarande_lagkonfidenselement_listas_fortfarande(self):
        md = self.rapport([{"id": "e07", "type": "paragraph",
                            "text": "svårläst stycke", "confidence": 0.3}])
        self.assertIn("e07", md)


if __name__ == "__main__":
    unittest.main()
