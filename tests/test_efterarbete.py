"""Efterarbetsskripten: migrationer som städar state utan att röra texten.

Alla fyra kör mot en färdig bok och måste vara idempotenta — en andra körning
ska röra noll poster. Den egenskapen är hela poängen: skripten körs om varje
gång en bok byggs om, och en migration som inte har en fixpunkt sprider i
stället nya poster för varje körning (det var precis felet i rubriknivaer.py
innan level_source infördes).
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.materialisera_kind import sveep as sveep_kind
from scripts.materialisera_verdict import sveep as sveep_verdict
from scripts.remappa_bbox import sveep as sveep_bbox
from scripts.tomma_artefakter import sveep as sveep_artefakt


class Bokbadd(unittest.TestCase):
    """En arbetskatalog med en sida, för migrationerna att arbeta på."""

    def setUp(self):
        self.wd = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.wd, ignore_errors=True)
        (self.wd / "pages").mkdir()

    def skriv(self, elements, rader=None):
        (self.wd / "pages" / "page_001.final.json").write_text(
            json.dumps({"page": 1, "elements": elements}), encoding="utf-8")
        if rader is not None:
            (self.wd / "pages" / "page_001.radboxar.json").write_text(
                json.dumps({"page": 1, "rows": rader}), encoding="utf-8")

    def las(self):
        return json.loads((self.wd / "pages" / "page_001.final.json")
                          .read_text(encoding="utf-8"))["elements"]


class TestMaterialiseraKind(Bokbadd):
    def _post(self, **extra):
        p = {"original": "a", "corrected": "b", "applied": True,
             "confidence": 0.9, "reason": "…", "source": "agent:x"}
        p.update(extra)
        return p

    def test_harleder_och_skriver_ut(self):
        self.skriv([{"id": "e1", "text": "x", "corrections": [self._post()]}])
        total, per, _ = sveep_kind(self.wd, True)
        self.assertEqual(total, 1)
        self.assertEqual(self.las()[0]["corrections"][0]["kind"], "ocr")

    def test_boknivabeslut_blir_emendering(self):
        self.skriv([{"id": "e1", "text": "x", "corrections": [
            self._post(source="anvandare:boknivabeslut")]}])
        sveep_kind(self.wd, True)
        self.assertEqual(self.las()[0]["corrections"][0]["kind"], "emendering")

    def test_befintligt_kind_ror_ingenting(self):
        self.skriv([{"id": "e1", "text": "x", "corrections": [
            self._post(kind="emendering")]}])
        total, _, _ = sveep_kind(self.wd, True)
        self.assertEqual(total, 0)
        self.assertEqual(self.las()[0]["corrections"][0]["kind"], "emendering")

    def test_idempotent(self):
        self.skriv([{"id": "e1", "text": "x", "corrections": [self._post()]}])
        sveep_kind(self.wd, True)
        self.assertEqual(sveep_kind(self.wd, True)[0], 0)


class TestMaterialiseraVerdict(Bokbadd):
    def _forslag(self, reason):
        return {"original": "a", "corrected": "b", "applied": False,
                "confidence": 0.5, "reason": reason, "source": "agent:x",
                "kind": "ocr"}

    def test_dom_i_prosa_blir_falt(self):
        self.skriv([{"id": "e1", "text": "x",
                     "corrections": [self._forslag("AVVISAD som dubblett")]}])
        self.assertEqual(len(sveep_verdict(self.wd, True)), 1)
        self.assertEqual(self.las()[0]["corrections"][0]["verdict"], "avvisad")

    def test_dubblett_raknas_som_dom(self):
        self.skriv([{"id": "e1", "text": "x",
                     "corrections": [self._forslag("DUBBLETT — redan gjord")]}])
        self.assertEqual(len(sveep_verdict(self.wd, True)), 1)

    def test_odomt_forslag_lamnas(self):
        """Ett förslag utan nedskriven dom får inte tystas maskinellt."""
        self.skriv([{"id": "e1", "text": "x",
                     "corrections": [self._forslag("OCR har läst fel här")]}])
        self.assertEqual(len(sveep_verdict(self.wd, True)), 0)
        self.assertNotIn("verdict", self.las()[0]["corrections"][0])

    def test_applicerad_post_ror_inte(self):
        post = self._forslag("AVVISAD")
        post["applied"] = True
        self.skriv([{"id": "e1", "text": "x", "corrections": [post]}])
        self.assertEqual(len(sveep_verdict(self.wd, True)), 0)


class TestTommaArtefakter(Bokbadd):
    def _tomd(self, conf):
        return {"id": "e1", "type": "page_artifact", "text": "",
                "confidence": conf,
                "corrections": [{"original": "signatur", "corrected": "",
                                 "applied": True, "confidence": 0.99,
                                 "reason": "…", "source": "agent:x",
                                 "kind": "ocr"}]}

    def test_hojer_tomd_artefakt(self):
        self.skriv([self._tomd(0.3)])
        self.assertEqual(len(sveep_artefakt(self.wd, True)), 1)
        self.assertEqual(self.las()[0]["confidence"], 1.0)

    def test_ror_inte_element_med_text(self):
        el = self._tomd(0.3)
        el["text"] = "kvar"
        self.skriv([el])
        self.assertEqual(len(sveep_artefakt(self.wd, True)), 0)

    def test_ror_inte_odomt_tomt_element(self):
        """Tomt utan applicerad tömningspost är inte advokatens verk."""
        el = self._tomd(0.3)
        el["corrections"] = []
        self.skriv([el])
        self.assertEqual(len(sveep_artefakt(self.wd, True)), 0)

    def test_redan_hog_confidence_ror_inte(self):
        self.skriv([self._tomd(0.99)])
        self.assertEqual(len(sveep_artefakt(self.wd, True)), 0)


class TestRemappaBbox(Bokbadd):
    FLAGGA = ("radboxar ommätta 2026-08-01: radindexen gick inte att matcha "
              "geometriskt mot den nya mätningen")

    def _element(self, bbox):
        return {"id": "e1", "type": "paragraph", "text": "rad",
                "needs_review": True, "review_reasons": [self.FLAGGA],
                "source": {"bbox": bbox}}

    def test_fragment_kopplas_till_sin_rad(self):
        """Den gamla mätningen delade raden i två band; fragmentet ligger i den."""
        self.skriv([self._element([0.1, 0.50, 0.4, 0.004])],
                   rader=[{"region": "vänsterkolumn",
                           "bbox": [0.1, 0.495, 0.4, 0.016]}])
        remap, bort, _ = sveep_bbox(self.wd, True)
        self.assertEqual((len(remap), len(bort)), (1, 0))
        el = self.las()[0]
        self.assertEqual(el["source"]["bbox"], [0.1, 0.495, 0.4, 0.016])
        self.assertEqual(el["source"]["region"], "vänsterkolumn")
        self.assertEqual(el["review_reasons"], [])
        self.assertFalse(el["needs_review"])

    def test_obekraftad_box_tas_bort_inte_behalls(self):
        """En box som mätningen inte känner igen är inte data att lita på."""
        self.skriv([self._element([0.9, 0.05, 0.05, 0.004])],
                   rader=[{"region": "vänsterkolumn",
                           "bbox": [0.1, 0.495, 0.4, 0.016]}])
        remap, bort, _ = sveep_bbox(self.wd, True)
        self.assertEqual((len(remap), len(bort)), (0, 1))
        self.assertNotIn("bbox", self.las()[0]["source"])

    def test_gamla_koordinater_bevaras_i_posten(self):
        self.skriv([self._element([0.1, 0.50, 0.4, 0.004])],
                   rader=[{"region": "x", "bbox": [0.1, 0.495, 0.4, 0.016]}])
        sveep_bbox(self.wd, True)
        post = self.las()[0]["corrections"][0]
        self.assertIn("0.5", post["original"])
        self.assertEqual(post["verdict"], "applicerad")

    def test_oflaggat_element_ror_ingenting(self):
        el = self._element([0.1, 0.50, 0.4, 0.004])
        el["review_reasons"] = []
        self.skriv([el], rader=[{"region": "x", "bbox": [0.1, 0.495, 0.4, 0.016]}])
        self.assertEqual(sveep_bbox(self.wd, True)[0], [])
        self.assertEqual(self.las()[0]["source"]["bbox"], [0.1, 0.50, 0.4, 0.004])

    def test_idempotent(self):
        self.skriv([self._element([0.1, 0.50, 0.4, 0.004])],
                   rader=[{"region": "x", "bbox": [0.1, 0.495, 0.4, 0.016]}])
        sveep_bbox(self.wd, True)
        remap, bort, utan = sveep_bbox(self.wd, True)
        self.assertEqual((len(remap), len(bort), len(utan)), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
