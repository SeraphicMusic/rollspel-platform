"""Tester för reparationsalgoritmer och korrektionspostens invarianter."""
import unittest

from pipeline.corrections import (apply_corrections_to_text, make_correction,
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

    def test_ogiltiga_sidor_flaggas(self):
        # 3T7: ser ut som notation men T7 finns inte i DoD
        status, _ = repair_dice_token("3T7", DOD.dice)
        self.assertIn(status, ("invalid", "ambiguous"))

    def test_mutant_accepterar_d(self):
        self.assertEqual(repair_dice_token("2D6", M2089.dice)[0], "fixed")

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
        status, corr = repair_word("Sypox", M2089)
        self.assertEqual(status, "fixed")
        self.assertEqual(corr["corrected"], "Syopox")


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


if __name__ == "__main__":
    unittest.main()
