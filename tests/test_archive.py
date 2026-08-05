"""Arkiveringen: käll-PDF → arkiv/, läsexport → bibliotek/.

Steget fanns bara som punkt 5 i import/README.md — en instruktion till en
agent, ingen kod. Ingenting körde den och ingenting märkte att den uteblev, så
DoD-grundreglernas tre käll-PDF:er blev kvar i import/ tills de raderades för
hand. Testerna nedan fäster de två egenskaper som gör att det inte kan hända
igen: en oavslutad bok arkiveras ALDRIG, och en färdig bok vars PDF står kvar i
inkorgen syns i `status`.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from pipeline.archive import (archive, plan, readiness, standard_name,
                              uncorrected_pages, unarchived_source)
from pipeline.manifest import Manifest


class Arkivbadd(unittest.TestCase):
    """Ett litet repo: <rot>/import, <rot>/arkiv, <rot>/arbete/<namn>."""

    def setUp(self):
        self.rot = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.rot, ignore_errors=True)
        (self.rot / "import").mkdir()
        (self.rot / "arbete").mkdir()
        self.pdf = self.rot / "import" / "nagon-bok.pdf"
        self.pdf.write_bytes(b"%PDF-1.4 lattsam testbok")

    def bok(self, namn="DOD-REG-testbok", sidor=2, state="validated",
            export=True, final=None, skippade=()):
        """`final` = sidor med final.json (default alla), `skippade` = sidor
        avförda med skipped.reason och som därför inte behöver korrektur."""
        wd = self.rot / "arbete" / namn
        wd.mkdir()
        m = Manifest.create(wd, self.pdf, sidor)
        for i in range(1, sidor + 1):
            m.set_state(i, state)
        m.save()
        (wd / "pages").mkdir(exist_ok=True)
        klara = range(1, sidor + 1) if final is None else final
        for i in range(1, sidor + 1):
            if i in klara:
                (wd / "pages" / ("page_%03d.final.json" % i)).write_text(
                    json.dumps({"page": i, "elements": []}), encoding="utf-8")
            skip = {"skipped": {"reason": "illustration_only"}} if i in skippade else {}
            (wd / "pages" / ("page_%03d.validated.json" % i)).write_text(
                json.dumps(dict({"page": i, "elements": []}, **skip)),
                encoding="utf-8")
        if export:
            (wd / "export").mkdir(exist_ok=True)
            (wd / "export" / "bok.json").write_text("{}", encoding="utf-8")
            (wd / "export" / "bok.md").write_text("# Testbok\n",
                                                  encoding="utf-8")
        return wd

    def ko(self, wd, rader):
        (wd / "beslut.md").write_text(
            "# Beslut\n\n## Öppen kö\n\n" + "\n".join(rader) + "\n",
            encoding="utf-8")


class TestBeredskap(Arkivbadd):
    def test_fardig_bok_har_inga_hinder(self):
        self.assertEqual(readiness(self.bok()), [])

    def test_oppen_boknivafraga_stoppar_arkivering(self):
        wd = self.bok()
        self.ko(wd, ["- [ ] BQ-001 Rastabellens BP-kostnad är overifierad"])
        hinder = readiness(wd)
        self.assertTrue(any("BQ-001" in h for h in hinder), hinder)

    def test_avbockad_fraga_stoppar_inte(self):
        wd = self.bok()
        self.ko(wd, ["- [x] BQ-001 Avgjord mot s. 11"])
        self.assertEqual(readiness(wd), [])

    def test_sida_som_inte_ar_validerad_stoppar(self):
        hinder = readiness(self.bok(state="transcribed"))
        self.assertTrue(any("state" in h for h in hinder), hinder)

    def test_saknad_export_stoppar(self):
        hinder = readiness(self.bok(export=False))
        self.assertTrue(any("bok.md" in h for h in hinder), hinder)


class TestNamn(Arkivbadd):
    def test_standardnamn_tas_ur_arbetskatalogen(self):
        namn, fel = standard_name(self.rot / "arbete" / "DOD-REG-testbok")
        self.assertEqual(namn, "DOD-REG-testbok")
        self.assertIsNone(fel)

    def test_oststandardiserat_katalognamn_kraver_namn(self):
        namn, fel = standard_name(self.rot / "arbete" / "40-drakar-och-demoner")
        self.assertIsNone(namn)
        self.assertIn("NAMNSTANDARD", fel)

    def test_namnet_gissas_aldrig_fram(self):
        """Typkoden (REG/AVE/VRL) är ett redaktionellt beslut, inte en regex."""
        p = plan(self.bok(namn="nagot-oststandardiserat"))
        self.assertIsNone(p["namn"])
        self.assertTrue(p["hinder"])
        self.assertEqual(p["atgarder"], [])


class TestArkivering(Arkivbadd):
    def test_pdf_flyttas_och_bok_md_kopieras(self):
        wd = self.bok()
        r = archive(wd, verkstall=True)
        self.assertEqual(r["hinder"], [])
        self.assertFalse(self.pdf.exists())
        self.assertTrue((self.rot / "arkiv" / "DOD-REG-testbok.pdf").exists())
        self.assertEqual(
            (self.rot / "bibliotek" / "DOD-REG-testbok.md")
            .read_text(encoding="utf-8"), "# Testbok\n")

    def test_torrkorning_ror_ingenting(self):
        wd = self.bok()
        r = archive(wd, verkstall=False)
        self.assertEqual(len(r["atgarder"]), 2)
        self.assertEqual(r["utfort"], [])
        self.assertTrue(self.pdf.exists())

    def test_andra_korningen_ar_en_nolloperation(self):
        wd = self.bok()
        archive(wd, verkstall=True)
        r = archive(wd, verkstall=True)
        self.assertTrue(r["klart"])
        self.assertEqual(r["utfort"], [])

    def test_oavslutad_bok_arkiveras_aldrig(self):
        wd = self.bok()
        self.ko(wd, ["- [ ] BQ-001 Fortfarande öppen"])
        r = archive(wd, verkstall=True)
        self.assertTrue(r["hinder"])
        self.assertEqual(r["utfort"], [])
        self.assertTrue(self.pdf.exists(),
                        "PDF:en måste ligga kvar där forensiken når den")

    def test_fel_pdf_arkiveras_inte(self):
        """sha256 skiljer sig -> det är inte boken som extraherades."""
        wd = self.bok()
        self.pdf.write_bytes(b"%PDF-1.4 en helt annan bok")
        r = archive(wd, verkstall=True)
        self.assertTrue(any("sha256" in h for h in r["hinder"]), r["hinder"])
        self.assertTrue(self.pdf.exists())

    def test_bok_md_uppdateras_om_exporten_andrats(self):
        wd = self.bok()
        archive(wd, verkstall=True)
        (wd / "export" / "bok.md").write_text("# Testbok, rättad\n",
                                              encoding="utf-8")
        archive(wd, verkstall=True)
        self.assertEqual(
            (self.rot / "bibliotek" / "DOD-REG-testbok.md")
            .read_text(encoding="utf-8"), "# Testbok, rättad\n")

    def test_pdf_raderas_aldrig_utan_flyttas(self):
        wd = self.bok()
        innan = self.pdf.read_bytes()
        archive(wd, verkstall=True)
        self.assertEqual(
            (self.rot / "arkiv" / "DOD-REG-testbok.pdf").read_bytes(), innan)


class TestOarkiverad(Arkivbadd):
    def test_pdf_kvar_i_import_rapporteras(self):
        # Manifestet lagrar en resolve():ad sökväg; på macOS är /var en
        # symlänk till /private/var, så jämför upplöst mot upplöst.
        self.assertEqual(unarchived_source(self.bok()), self.pdf.resolve())

    def test_arkiverad_bok_rapporteras_inte(self):
        wd = self.bok()
        archive(wd, verkstall=True)
        self.assertIsNone(unarchived_source(wd))

    def test_pdf_utanfor_import_ar_inte_oarkiverad(self):
        annan = self.rot / "nagon-annanstans.pdf"
        annan.write_bytes(b"%PDF-1.4 lattsam testbok")
        wd = self.rot / "arbete" / "DOD-REG-annan"
        wd.mkdir()
        Manifest.create(wd, annan, 1)
        self.assertIsNone(unarchived_source(wd))


class TestKoText(unittest.TestCase):
    """En fråga ska gå att förstå där den VISAS, inte bara i beslut.md.

    Kön skrivs med indragna fortsättningsrader eftersom filen läses av
    människor. Parsern läste bara postens första rad, så BQ-002 slutade
    "…A och vi har olika" mitt i meningen i både `status` och rapporten.
    """

    def setUp(self):
        self.wd = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.wd, ignore_errors=True)

    def skriv(self, text):
        (self.wd / "beslut.md").write_text(text, encoding="utf-8")

    def test_indragna_fortsattningsrader_hor_till_posten(self):
        from pipeline.decisions import open_questions
        self.skriv("## Öppen kö\n\n"
                   "- [ ] BQ-002 Särskilda förmågor 68, 72 och 77: A och vi\n"
                   "      har olika grundegenskap. Läs om hela 61–80 mot s. 27.\n")
        (qid, text), = open_questions(self.wd)
        self.assertEqual(qid, "BQ-002")
        self.assertIn("Läs om hela 61–80 mot s. 27.", text)
        self.assertNotIn("\n", text)

    def test_nasta_post_avslutar_foregaende(self):
        from pipeline.decisions import queue_items
        self.skriv("## Öppen kö\n\n"
                   "- [ ] BQ-001 Första frågan\n"
                   "      med en fortsättning\n"
                   "- [x] BQ-002 Andra frågan\n")
        items = queue_items(self.wd)
        self.assertEqual(items[0], ("BQ-001", "Första frågan med en "
                                              "fortsättning", False))
        self.assertEqual(items[1], ("BQ-002", "Andra frågan", True))

    def test_text_efter_kons_slut_sugs_inte_in(self):
        from pipeline.decisions import open_questions
        self.skriv("## Öppen kö\n\n"
                   "- [ ] BQ-001 Enda frågan\n\n"
                   "## Ett senare avsnitt\n\n"
                   "  en indragen rad som inte hör till kön\n")
        (_, text), = open_questions(self.wd)
        self.assertEqual(text, "Enda frågan")


class TestOkorrigerade(Arkivbadd):
    """Manifestets `state` duger inte som mått på att korrekturet är gjort.

    Pipelinen lyfter aldrig en sida över `validated`, så del III av
    DoD-grundreglerna — 23 korrekturlästa sidor av 50 — såg i `status` exakt ut
    som den färdiga del I. `merge` väljer final > validated, så de 26 orörda
    sidorna hade bidragit med sin maskinläsning och boken sett klar ut.
    """

    def test_sida_utan_final_json_stoppar_arkivering(self):
        wd = self.bok(sidor=4, final=[1, 2])
        hinder = readiness(wd)
        self.assertTrue(any("aldrig korrekturlästs" in h for h in hinder),
                        hinder)
        self.assertTrue(any("s. 3, s. 4" in h for h in hinder), hinder)

    def test_alla_sidor_korrekturlasta_ger_inget_hinder(self):
        self.assertEqual(readiness(self.bok(sidor=4)), [])

    def test_skippad_sida_behover_inget_korrektur(self):
        """En illustrationssida har inget korrektur att göra."""
        wd = self.bok(sidor=4, final=[1, 2, 3], skippade=[4])
        self.assertEqual(uncorrected_pages(wd), [])
        self.assertEqual(readiness(wd), [])

    def test_halvkorrigerad_bok_arkiveras_inte_ens_med_tom_ko(self):
        wd = self.bok(sidor=4, final=[1, 2])
        r = archive(wd, verkstall=True)
        self.assertTrue(r["hinder"])
        self.assertEqual(r["utfort"], [])
        self.assertTrue(self.pdf.exists())
