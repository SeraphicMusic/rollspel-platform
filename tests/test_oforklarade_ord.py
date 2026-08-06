"""Attribuerar `diffa`s ordändringar till de poster som tar ansvar för dem.

Grinden är inte "noll ordförändringar" — formen får ändras och rättningar SKA
ändra ord. Grinden är noll *oförklarade* ordförändringar, och skillnaden
avgjordes hittills genom att en människa läste diffens ordlista mot
sidfilernas korrektionsposter. Testerna nedan håller den jämförelsen ärlig i
de tre fall där den lätt blir falskt grön: skiljetecken som sitter fast i
diffens token, en post som inte är applicerad, och `validated.json` som ligger
kvar bredvid sin `final.json` och skulle dubbelräkna varje post.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.oforklarade_ord import granska


class Bokbadd(unittest.TestCase):
    def setUp(self):
        self.wd = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.wd, ignore_errors=True)
        (self.wd / "pages").mkdir()
        (self.wd / "export").mkdir()

    def bok(self, frysning, nu):
        (self.wd / "export" / "bok.frysning.md").write_text(frysning,
                                                            encoding="utf-8")
        (self.wd / "export" / "bok.md").write_text(nu, encoding="utf-8")

    def sida(self, elements, namn="page_001.final.json"):
        (self.wd / "pages" / namn).write_text(
            json.dumps({"page": 1, "elements": elements}), encoding="utf-8")

    @staticmethod
    def post(original, corrected, applied=True, kind="ocr"):
        return {"original": original, "corrected": corrected,
                "applied": applied, "confidence": 0.9, "reason": "…",
                "kind": kind, "source": "agent:djavulens-advokat"}

    def kvar(self):
        r = granska(self.wd)
        return (sum(r["oforklarat_borta"].values())
                + sum(r["oforklarat_nya"].values()))


class TestAttribuering(Bokbadd):
    def test_applicerad_post_forklarar_sin_egen_andring(self):
        self.bok("han spårar upp dem", "han spöar upp dem")
        self.sida([{"id": "e1", "corrections": [self.post("spårar", "spöar")]}])
        self.assertEqual(self.kvar(), 0)

    def test_andring_utan_post_star_kvar_som_oforklarad(self):
        """Felklassen frysningen finns för: text som försvinner utan avsändare.

        Sju tabellrader föll ur del I:s `bok.md` och såg i diffen ut precis som
        en avsedd rättning — ända tills man frågade vilken post som bar den.
        """
        self.bok("han spårar upp dem", "han spöar upp dem")
        self.sida([{"id": "e1", "corrections": []}])
        r = granska(self.wd)
        self.assertEqual(dict(r["oforklarat_borta"]), {"spårar": 1})
        self.assertEqual(dict(r["oforklarat_nya"]), {"spöar": 1})

    def test_avvisad_post_forklarar_ingenting(self):
        """`applied: false` betyder att posten uttryckligen INTE ändrade texten.
        Att låta den kvitta en ändring vore att låta ett avslag verkställa sig.
        """
        self.bok("han spårar upp dem", "han spöar upp dem")
        self.sida([{"id": "e1",
                    "corrections": [self.post("spårar", "spöar",
                                              applied=False)]}])
        self.assertEqual(self.kvar(), 2)

    def test_skiljetecken_i_token_hindrar_inte_attribueringen(self):
        """`diffa` tokeniserar `totalsförsvaret.` med punkten kvar, medan
        posten bär ordet utan. Samma ord — och en attribuering som missar det
        rapporterar en äkta rättning som oförklarad, vilket lär användaren att
        bortse från utfallet."""
        self.bok("från städningen till totalsförsvaret.",
                 "från städningen till totalförsvaret.")
        self.sida([{"id": "e1",
                    "corrections": [self.post("totalsförsvaret",
                                              "totalförsvaret",
                                              kind="emendering")]}])
        self.assertEqual(self.kvar(), 0)

    def test_citattecken_kring_ordet_hindrar_inte_heller(self):
        self.bok('han sa ”spårar” då', 'han sa ”spöar” då')
        self.sida([{"id": "e1", "corrections": [self.post("spårar", "spöar")]}])
        self.assertEqual(self.kvar(), 0)

    def test_post_pa_helt_element_forklarar_bara_sin_ordskillnad(self):
        """En post vars `original` är hela elementtexten ska bara kvitta de ord
        som faktiskt skiljer — inte immunisera elementets övriga ord."""
        self.bok("alfa beta gamma delta", "alfa beta gamma")
        self.sida([{"id": "e1",
                    "corrections": [self.post("alfa beta gamma delta",
                                              "alfa beta gamma epsilon")]}])
        r = granska(self.wd)
        # `delta` är förklarad av posten; `epsilon` lovades men uteblev, och
        # det är ingen ordFÖRÄNDRING i boken — alltså inget oförklarat.
        self.assertEqual(dict(r["oforklarat_borta"]), {})
        self.assertEqual(dict(r["oforklarat_nya"]), {})

    def test_tva_forekomster_men_en_post_lamnar_en_kvar(self):
        """Räkningen är per förekomst. En rättning på ett ställe förklarar inte
        att samma ord försvunnit på två."""
        self.bok("spårar och spårar", "spöar och spöar")
        self.sida([{"id": "e1", "corrections": [self.post("spårar", "spöar")]}])
        r = granska(self.wd)
        self.assertEqual(dict(r["oforklarat_borta"]), {"spårar": 1})
        self.assertEqual(dict(r["oforklarat_nya"]), {"spöar": 1})


class TestSidval(Bokbadd):
    def test_validated_bredvid_final_dubbelraknas_inte(self):
        """`final.json` är sidans slutversion och `validated.json` en tidigare
        version av samma sida. Läses båda får varje post dubbel vikt, och två
        förlorade ord kvittas av en enda rättning."""
        self.bok("spårar och spårar", "spöar och spöar")
        el = [{"id": "e1", "corrections": [self.post("spårar", "spöar")]}]
        self.sida(el, "page_001.final.json")
        self.sida(el, "page_001.validated.json")
        r = granska(self.wd)
        self.assertEqual(dict(r["oforklarat_borta"]), {"spårar": 1})

    def test_validated_utan_final_raknas(self):
        """En sida som ännu inte varit hos advokaten bär sina poster i
        `validated.json`, och de är lika giltiga."""
        self.bok("han spårar upp dem", "han spöar upp dem")
        self.sida([{"id": "e1", "corrections": [self.post("spårar", "spöar")]}],
                  "page_001.validated.json")
        self.assertEqual(self.kvar(), 0)


class TestUtanFrysning(Bokbadd):
    def test_saknad_frysning_ger_filfel_inte_falskt_gront(self):
        (self.wd / "export" / "bok.md").write_text("text", encoding="utf-8")
        with self.assertRaises(FileNotFoundError):
            granska(self.wd)


if __name__ == "__main__":
    unittest.main()
