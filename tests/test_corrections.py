"""Tester för reparationsalgoritmer och korrektionspostens invarianter."""
import json
import unittest
from pathlib import Path

from pipeline.manifest import Manifest

from pipeline.corrections import (KIND_EMENDATION, KIND_OCR,
                                  apply_corrections_to_text,
                                  close_review_reason, make_correction,
                                  review_flag_counts,
                                  repair_dice_token, repair_word,
                                  scan_dice_in_text)
from pipeline.systems import load

DOD = load("dod")
M2089 = load("mutant2089")


class TestDiceRepair(unittest.TestCase):
    def test_itg_blir_1t6(self):
        status, corr = repair_dice_token("ITG", DOD.dice)
        self.assertEqual(status, "fixed")
        self.assertEqual(corr["corrected"], "1T6")
        self.assertTrue(corr["applied"])
        self.assertEqual(corr["original"], "ITG")

    def test_2i6_blir_2t6(self):
        status, corr = repair_dice_token("2I6", DOD.dice)
        self.assertEqual(status, "fixed")
        self.assertEqual(corr["corrected"], "2T6")

    def test_1t2o_blir_1t20(self):
        status, corr = repair_dice_token("1T2O", DOD.dice)
        self.assertEqual(status, "fixed")
        self.assertEqual(corr["corrected"], "1T20")

    def test_giltig_notation_lamnas(self):
        self.assertEqual(repair_dice_token("1T6", DOD.dice)[0], "ok")
        self.assertEqual(repair_dice_token("3T6+2", DOD.dice)[0], "ok")

    def test_rena_tal_repareras_aldrig(self):
        # "1984" får inte bli tärningsnotation (7->T-fällan)
        self.assertEqual(repair_dice_token("1984", DOD.dice)[0], "skip")

    def test_sifferlost_ord_utan_separator_repareras_aldrig(self):
        # "SIG" blev "5T6" (S->5, I->T, G->6) och sabbade rubriken
        # "ATT TA SIG UT UR EXPROD5". Sifferlös token utan bokstavligt T/D
        # är inte tärningsnotation.
        self.assertEqual(repair_dice_token("SIG", M2089.dice)[0], "skip")
        self.assertEqual(repair_dice_token("SIG", DOD.dice)[0], "skip")
        # ITG har kvar sitt T och ska fortfarande repareras
        self.assertEqual(repair_dice_token("ITG", DOD.dice)[0], "fixed")

    def test_scan_ror_inte_versalord_i_rubrik(self):
        text = "7.4.3. ATT TA SIG UT UR EXPROD5"
        corrections, _ = scan_dice_in_text(text, M2089.dice, M2089.words)
        self.assertEqual(corrections, [])

    def test_ogiltiga_sidor_flaggas(self):
        # 3T7: ser ut som notation men T7 finns inte i DoD
        status, _ = repair_dice_token("3T7", DOD.dice)
        self.assertIn(status, ("invalid", "ambiguous"))

    def test_mutant_accepterar_d(self):
        self.assertEqual(repair_dice_token("2D6", M2089.dice)[0], "fixed")

    def test_mutant_accepterar_t3(self):
        # 1T3 (slå 1T6, halvera uppåt) förekommer i trycket, t.ex. Sinkadus 34
        # "efter ytterligare 1T3 dagar". Saknades i sides och flaggades som
        # ogiltig notation — en adapterlucka, inte ett OCR-fel.
        self.assertEqual(repair_dice_token("1T3", M2089.dice)[0], "ok")
        self.assertEqual(repair_dice_token("1T3", DOD.dice)[0], "ok")

    def test_mutant_accepterar_t2(self):
        # 1T2 förekommer i trycket, t.ex. Sinkadus 1989 "I drakens klor"
        # ("1T2 Personal från relaxavdelningen", "1T2-1 man"). Samma
        # adapterlucka som T3 — sides kompletteras evidensdrivet.
        self.assertEqual(repair_dice_token("1T2", M2089.dice)[0], "ok")
        self.assertEqual(repair_dice_token("1T2", DOD.dice)[0], "ok")

    def test_scan_i_lopande_text(self):
        text = "Vakten gör ITG i skada och har 1T2O kroppspoäng."
        corrections, flags = scan_dice_in_text(text, DOD.dice, DOD.words)
        fixed = {c["original"]: c["corrected"] for c in corrections}
        self.assertEqual(fixed, {"ITG": "1T6", "1T2O": "1T20"})
        text2 = apply_corrections_to_text(text, corrections)
        self.assertIn("1T6 i skada", text2)
        self.assertIn("1T20 kroppspoäng", text2)

    def test_scan_ror_inte_artal_och_ord(self):
        text = "År 1984 gav Äventyrsspel ut den andra utgåvan."
        corrections, flags = scan_dice_in_text(text, DOD.dice, DOD.words)
        self.assertEqual(corrections, [])


class TestLexiconRepair(unittest.TestCase):
    def test_fardighet_far_diakritik(self):
        status, corr = repair_word("Fardighet", DOD)
        self.assertEqual(status, "fixed")
        self.assertEqual(corr["corrected"], "Färdighet")

    def test_alias_kortssvard(self):
        status, corr = repair_word("kortssvard", DOD)
        self.assertEqual(status, "fixed")
        self.assertEqual(corr["corrected"], "Kortsvärd")

    def test_skiftlage_rattas_inte(self):
        # Korrekt svenska med annat skiftläge ska lämnas orörd
        self.assertEqual(repair_word("förflyttning", DOD)[0], "ok")
        self.assertEqual(repair_word("Färdighet", DOD)[0], "ok")

    def test_vanlig_svenska_lamnas(self):
        self.assertEqual(repair_word("bordet", DOD)[0], "skip")
        self.assertEqual(repair_word("springa", DOD)[0], "skip")

    def test_mutant_egennamn(self):
        status, corr = repair_word("Toyfox", M2089)
        self.assertEqual(status, "fixed")
        self.assertEqual(corr["corrected"], "Toytox")

    def test_gement_vanligt_ord_matchar_inte_versal_systemterm(self):
        # Återkommande falsk positiv: diakritisk normalisering (ä->a) matchade
        # vanliga svenska ord mot versala systemtermer utan hänsyn till
        # versalisering. "läser" blev vapentermen "Laser" i meningar som
        # "när du läser av på olyckstabellen" (Sinkadus 34, två gånger i samma
        # bok) och "när rollpersonerna läser igenom papperen" (Sinkadus 32).
        self.assertEqual(repair_word("läser", M2089)[0], "skip")
        # Samma felklass i dod-adaptern, med färdighets- och besvärjelsenamn.
        for ord_ in ("vardera", "laga", "knacka", "skara", "vänlighet"):
            self.assertEqual(repair_word(ord_, DOD)[0], "skip", ord_)

    def test_versalmatchning_blockerar_inte_akta_diakritikfel(self):
        # Skyddet får bara träffa versaliseringskrockar — ord som matchar
        # systemtermen i skiftläge ska fortfarande få sin diakritik rättad.
        status, corr = repair_word("Fardighet", DOD)
        self.assertEqual(status, "fixed")
        self.assertEqual(corr["corrected"], "Färdighet")

    def test_harledd_matchning_foreslas_men_appliceras_inte(self):
        # Versaliseringsspärren fångar bara en del av felklassen: står både
        # ordet och systemtermen med versal passerar den, och då rättade
        # valideraren tryckets korrekta plural `Halvlängdsmän` till singular
        # (DoD-grundreglerna s. 43 — krävde en advokatkörning att revertera).
        # Härledda ordindexmatchningar är därför förslag, inte appliceringar.
        status, corr = repair_word("Dodsgast", DOD)
        self.assertEqual(status, "fixed")
        self.assertEqual(corr["corrected"], "Dödsgast")
        self.assertFalse(corr["applied"])
        self.assertIn("FÖRSLAG", corr["reason"])

    def test_handkurerat_alias_appliceras_fortfarande(self):
        # Aliasposter är avsiktliga och bär sitt eget belägg — de appliceras.
        for word, adapter in (("kortssvard", DOD), ("Toyfox", M2089)):
            status, corr = repair_word(word, adapter)
            self.assertEqual(status, "fixed", word)
            self.assertTrue(corr["applied"], word)

    def test_plural_i_lexikonet_ger_ingen_falsk_positiv(self):
        # Efter att pluralformen lagts till evidensdrivet matchar ordet exakt,
        # och den avdiakritiserade formen blir tvetydig i stället för "rättad".
        self.assertEqual(repair_word("Halvlängdsmän", DOD)[0], "ok")
        self.assertEqual(repair_word("Halvlangdsman", DOD)[0], "ambiguous")

    def test_sypox_normaliseras_inte(self):
        # Trycket i Attentat Sypox säger "Sypox" i både displaytitel och prosa
        # (pixelverifierat). Aliaset sypox->Syopox rättade FRÅN den tryckta
        # formen och är borttaget — namnet ska lämnas orört.
        self.assertEqual(repair_word("Sypox", M2089)[0], "skip")


class TestCorrectionInvariants(unittest.TestCase):
    def test_original_bevaras(self):
        c = make_correction("ITG", "1T6", 0.95, "test", "validator:test")
        self.assertEqual(c["original"], "ITG")
        self.assertTrue(c["applied"])

    def test_lag_confidence_appliceras_inte(self):
        c = make_correction("x", "y", 0.6, "test", "validator:test")
        self.assertFalse(c["applied"])

    def test_oapplicerad_andrar_inte_text(self):
        c = make_correction("häst", "get", 0.5, "test", "validator:test")
        self.assertEqual(apply_corrections_to_text("en häst", [c]), "en häst")

    def test_kind_defaultar_till_ocr(self):
        c = make_correction("ITG", "1T6", 0.95, "test", "validator:test")
        self.assertEqual(c["kind"], KIND_OCR)

    def test_emendering_bevarar_tryckets_lydelse(self):
        """Print-trogen text måste gå att återskapa ur posten."""
        c = make_correction(
            "Ing försök", "Inget försök", 0.96,
            "Sättningsfel: 'et' saknas i trycket",
            "agent:djavulens-advokat", kind=KIND_EMENDATION)
        self.assertEqual(c["original"], "Ing försök")
        self.assertEqual(c["kind"], KIND_EMENDATION)
        self.assertTrue(c["applied"])

    def test_okant_korrektionsslag_avvisas(self):
        with self.assertRaises(ValueError):
            make_correction("a", "b", 1.0, "test", "validator:test",
                            kind="gissning")


if __name__ == "__main__":
    unittest.main()


class TestDom(unittest.TestCase):
    """Advokatens dom över ett förslag den inte applicerar."""

    def test_utan_dom_ligger_falten_inte_med(self):
        post = make_correction("a", "b", 0.5, "skäl", "agent:x", applied=False)
        self.assertNotIn("verdict", post)
        self.assertNotIn("adjudicated_by", post)

    def test_dom_skrivs_ned(self):
        post = make_correction("a", "b", 0.5, "skäl", "agent:x", applied=False,
                               verdict="avvisad",
                               adjudicated_by="agent:djavulens-advokat")
        self.assertEqual(post["verdict"], "avvisad")
        self.assertEqual(post["adjudicated_by"], "agent:djavulens-advokat")

    def test_okand_dom_avvisas(self):
        with self.assertRaises(ValueError):
            make_correction("a", "b", 0.5, "skäl", "agent:x", applied=False,
                            verdict="kanske")


class TestAvgjordFlagga(unittest.TestCase):
    """En granskningsflagga kan vara avgjord utan att kastas bort."""

    def _element(self, *skal):
        return {"id": "p001_e01", "text": "x", "needs_review": True,
                "review_reasons": list(skal)}

    def test_flaggan_flyttas_med_sin_losning(self):
        el = self._element("bbox ska verifieras")
        self.assertTrue(close_review_reason(
            el, "bbox ska verifieras", "omkopplad mot mätningen", "skript"))
        self.assertEqual(el["review_reasons"], [])
        self.assertEqual(len(el["resolved_reasons"]), 1)
        stangd = el["resolved_reasons"][0]
        self.assertEqual(stangd["reason"], "bbox ska verifieras")
        self.assertEqual(stangd["resolution"], "omkopplad mot mätningen")
        self.assertEqual(stangd["closed_by"], "skript")

    def test_texten_bevaras_ordagrant(self):
        """Beläggstexten är det som gör kontrollen spårbar — den raderas inte."""
        skal = "GENOMRÄKNING: 671 celler omlästa, inga fynd"
        el = self._element(skal)
        close_review_reason(el, skal, "protokoll, ingen fråga", "skript")
        self.assertEqual(el["resolved_reasons"][0]["reason"], skal)

    def test_sista_flaggan_slacker_needs_review(self):
        el = self._element("a", "b")
        close_review_reason(el, "a", "avgjord", "skript")
        self.assertTrue(el["needs_review"])
        close_review_reason(el, "b", "avgjord", "skript")
        self.assertFalse(el["needs_review"])

    def test_okand_flagga_ror_ingenting(self):
        el = self._element("a")
        self.assertFalse(close_review_reason(el, "b", "avgjord", "skript"))
        self.assertEqual(el["review_reasons"], ["a"])
        self.assertNotIn("resolved_reasons", el)

    def test_element_utan_flaggor_klarar_anropet(self):
        el = {"id": "p001_e02", "text": "x"}
        self.assertFalse(close_review_reason(el, "a", "avgjord", "skript"))


class TestDiceArithmeticIsNotNotation(unittest.TestCase):
    """BQ-016: `+` duger inte som ensam tärningsmarkör.

    `dice.json` mappar `+` → `T` i `misread_to_canonical`, så varje `N+M` i en
    bok kunde bli en tärning. Del III s. 23 skrev om `Dess CL är 6+2 per
    effektgrad` till `6T2` — en notation boken aldrig använder — och
    applicerade rättningen rakt på ett spelvärde.
    """

    def setUp(self):
        self.dice, self.words = DOD.dice, DOD.words

    def test_rakneillagg_rors_inte(self):
        text = "Dess CL är 6+2 per effektgrad utöver den första."
        corr, flags = scan_dice_in_text(text, self.dice, self.words)
        self.assertEqual(corr, [])
        self.assertEqual(flags, [])

    def test_akta_notation_med_tillagg_passerar_fortfarande(self):
        """`3T6+3` bär ett `T` och ska fortsätta prövas som notation."""
        corr, flags = scan_dice_in_text("Skadan är 3T6+3 mot rustning.",
                                        self.dice, self.words)
        self.assertEqual(corr, [])
        self.assertEqual(flags, [])

    def test_felavlast_notation_lagas_fortfarande(self):
        """Motprovet: en garblad token med `T`-markör repareras som förut."""
        corr, _ = scan_dice_in_text("Vakten gör ITG i skada.",
                                    self.dice, self.words)
        self.assertEqual([c["corrected"] for c in corr], ["1T6"])
        self.assertTrue(corr[0]["applied"])


class TestGranskningsflaggeRakning(unittest.TestCase):
    """`status` mätte kampanjens backlogg med manifestets `needs_review`.

    Den siffran sätts vid bokföringen och följer inte med när advokaten lägger
    till eller stänger en flagga: över de 33 böckerna sa manifestet 167 medan
    sidfilerna bar 1016. Räkningen ska läsa sidfilerna, och bara den bästa
    versionen per sida — annars räknas samma flagga en gång per version.
    """

    def setUp(self):
        import shutil
        import tempfile
        self.wd = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.wd, ignore_errors=True)
        (self.wd / "pages").mkdir()

    def _bok(self, n_sidor):
        pdf = self.wd / "kalla.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        Manifest.create(self.wd, pdf, n_sidor)

    def _sida(self, no, suffix, elements):
        (self.wd / "pages" / ("page_%03d.%s" % (no, suffix))).write_text(
            json.dumps({"page": no, "elements": elements}), encoding="utf-8")

    def test_raknar_oppna_och_avgjorda_ur_sidfilerna(self):
        self._bok(2)
        self._sida(1, "final.json", [
            {"id": "e1", "review_reasons": ["a", "b"]},
            {"id": "e2", "review_reasons": [],
             "resolved_reasons": [{"reason": "c", "resolution": "x",
                                   "closed_by": "skript"}]},
        ])
        self._sida(2, "final.json", [{"id": "e3", "review_reasons": ["d"]}])
        r = review_flag_counts(self.wd)
        self.assertEqual(r["oppna"], 3)
        self.assertEqual(r["avgjorda"], 1)
        self.assertEqual(r["sidor_med_oppna"], 2)
        self.assertEqual(r["per_sida"], {1: 2, 2: 1})

    def test_bara_basta_versionen_per_sida_raknas(self):
        """final.json vinner över validated.json — annars dubbelräknas allt."""
        self._bok(1)
        self._sida(1, "validated.json", [{"id": "e1",
                                          "review_reasons": ["gammal", "x"]}])
        self._sida(1, "final.json", [{"id": "e1", "review_reasons": ["ny"]}])
        r = review_flag_counts(self.wd)
        self.assertEqual(r["oppna"], 1)

    def test_manifestets_needs_review_paverkar_inte_rakningen(self):
        """Instrumentet ska mäta sidfilerna, inte manifestets föråldrade fält."""
        self._bok(1)
        m = Manifest.load(self.wd)
        m.page(1)["needs_review"] = 99
        m.save()
        self._sida(1, "final.json", [{"id": "e1", "review_reasons": ["a"]}])
        self.assertEqual(review_flag_counts(self.wd)["oppna"], 1)

    def test_sida_utan_sidfil_hoppas_over(self):
        self._bok(3)
        self._sida(2, "final.json", [{"id": "e1", "review_reasons": ["a"]}])
        r = review_flag_counts(self.wd)
        self.assertEqual(r["oppna"], 1)
        self.assertEqual(r["per_sida"], {2: 1})

    def test_en_stangd_flagga_flyttar_sig_mellan_hinkarna(self):
        """close_review_reason() ska synas i räkningen som -1 öppen, +1 avgjord."""
        self._bok(1)
        el = {"id": "e1", "needs_review": True, "review_reasons": ["a", "b"]}
        self._sida(1, "final.json", [el])
        self.assertEqual(review_flag_counts(self.wd)["oppna"], 2)
        close_review_reason(el, "a", "avgjord mot PNG:n", "agent:advokat")
        self._sida(1, "final.json", [el])
        r = review_flag_counts(self.wd)
        self.assertEqual((r["oppna"], r["avgjorda"]), (1, 1))
