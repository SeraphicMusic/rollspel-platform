"""Tester för reparationsalgoritmer och korrektionspostens invarianter."""
import unittest

from pipeline.corrections import (KIND_EMENDATION, KIND_OCR,
                                  apply_corrections_to_text, make_correction,
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
