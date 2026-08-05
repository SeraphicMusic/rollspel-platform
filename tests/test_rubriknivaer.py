"""Rubriknivåer härledda ur innehållsförteckningens indrag (beslut C)."""
import unittest

from scripts.rubriknivaer import (columns_of, indent_levels, normalise,
                                  plan_level)


class TestNormalisering(unittest.TestCase):
    def test_punktledare_faller_bort(self):
        self.assertEqual(normalise("Att leda spelet ... 3"), "ATT LEDA SPELET")
        self.assertEqual(normalise("Grip .................37"), "GRIP")

    def test_versalisering_och_kolon(self):
        # Trycket sätter rubriken versalt och TOC:n gement — samma rubrik.
        self.assertEqual(normalise("ATT LEDA SPELET"),
                         normalise("Att leda spelet ... 3"))
        self.assertEqual(normalise("PROJEKTLEDNING:"), "PROJEKTLEDNING")

    def test_sidintervall_i_ledaren(self):
        self.assertEqual(normalise("Tabeller ... 31 - 34"), "TABELLER")


class TestSpalter(unittest.TestCase):
    def test_tre_spalter_klustras(self):
        # Uppmätt i del II: spaltkanterna 0,075 / 0,370 / 0,666 med tre
        # indragslägen i varje.
        lefts = [0.075, 0.094, 0.114, 0.370, 0.390, 0.408, 0.666, 0.685, 0.704]
        self.assertEqual([round(x, 3) for x in columns_of(lefts)],
                         [0.075, 0.370, 0.666])

    def test_indrag_inom_spalt_ar_ingen_ny_spalt(self):
        self.assertEqual(len(columns_of([0.075, 0.094, 0.114])), 1)


class TestIndragsnivaer(unittest.TestCase):
    def test_tre_lagen_ger_tre_nivaer(self):
        measured = [("KAPITEL", 0, 0.0742), ("SEKTION", 0, 0.0943),
                    ("UNDERAVSNITT", 0, 0.1145)]
        self.assertEqual(dict(indent_levels(measured)),
                         {"KAPITEL": 1, "SEKTION": 2, "UNDERAVSNITT": 3})

    def test_varje_spalt_mats_mot_sin_egen_kant(self):
        """Samma rang i spalt 2 och 3 ska ge samma nivå.

        Varelsenamnen ligger på 0,408 i mittspalten och 0,704 i högerspalten
        — mätt mot en gemensam nollpunkt hade de hamnat på olika nivåer.
        """
        measured = [("VARELSER", 1, 0.3697), ("DJUR", 1, 0.3898),
                    ("ALV", 1, 0.4100),
                    ("ÖRTER", 2, 0.6658), ("GIFTER", 2, 0.6851),
                    ("GRIP", 2, 0.7045)]
        levels = dict(indent_levels(measured))
        self.assertEqual(levels["ALV"], levels["GRIP"])
        self.assertEqual(levels["DJUR"], levels["GIFTER"])
        self.assertEqual(levels["VARELSER"], 1)

    def test_djupare_indrag_klipps_till_kontraktets_tre(self):
        measured = [("A", 0, 0.07), ("B", 0, 0.07 + 4 * 0.0195)]
        self.assertEqual(dict(indent_levels(measured))["B"], 3)


class TestPlan(unittest.TestCase):
    LEVELS = {"STRID": 1, "STRIDSRUNDAN": 2, "TURORDNING": 3}

    def test_toc_bestammer_nivan(self):
        for text, level in (("STRID", 1), ("STRIDSRUNDAN", 2),
                            ("TURORDNING", 3)):
            el = {"text": text, "level": 1}
            self.assertEqual(plan_level(15, el, self.LEVELS, 2),
                             (level, "TOC"))

    def test_rubrik_utanfor_toc_sjunker_ett_steg(self):
        el = {"text": "STRIDSDIAGRAM", "level": 1}
        self.assertEqual(plan_level(32, el, self.LEVELS, 2),
                         (2, "utanför TOC"))

    def test_stamplad_rubrik_rakas_aldrig_om(self):
        """Utan stämpeln sjunker rubriken ett steg vid varje körning."""
        el = {"text": "STRIDSDIAGRAM", "level": 2,
              "level_source": "utanför TOC"}
        self.assertEqual(plan_level(32, el, self.LEVELS, 2),
                         (2, "utanför TOC"))

    def test_titelsidan_harmoniseras_mot_del_i(self):
        el = {"text": "BOK II:", "level": 2}
        self.assertEqual(plan_level(2, el, self.LEVELS, 2)[0], 1)

    def test_omslaget_rors_inte(self):
        el = {"text": "Drakar", "level": 1}
        self.assertEqual(plan_level(1, el, self.LEVELS, 2), (1, "omslag — orört"))


if __name__ == "__main__":
    unittest.main()


class TestHomonymerIToc(unittest.TestCase):
    """BQ-009: vid namnar inuti TOC:t vinner den GRUNDASTE nivån.

    `levels.setdefault(key, level)` behöll den FÖRSTA posten i läsordning, så
    en underpost som råkade stå före sitt kapitel bestämde kapitlets nivå.
    Ett kapitel står alltid grundast av sina namnar, så minimum är rätt urval
    — och det behöver varken folio eller läsordning.
    """

    def _levels(self, measured):
        levels = {}
        for key, level in indent_levels(measured):
            if key not in levels or level < levels[key]:
                levels[key] = level
        return levels

    def test_grundaste_nivan_vinner_oavsett_lasordning(self):
        # Underposten `Tabeller ... 23-26` står FÖRE kapitlet `TABELLER`.
        measured = [("KAPITEL", 0, 0.0742),
                    ("TABELLER", 0, 0.1145),
                    ("TABELLER", 0, 0.0742)]
        self.assertEqual(self._levels(measured)["TABELLER"], 1)

    def test_setdefault_hade_gett_underpostens_niva(self):
        """Motprovet: den gamla regeln ger 3 på exakt samma indata."""
        measured = [("KAPITEL", 0, 0.0742),
                    ("TABELLER", 0, 0.1145),
                    ("TABELLER", 0, 0.0742)]
        gammal = {}
        for key, level in indent_levels(measured):
            gammal.setdefault(key, level)
        self.assertEqual(gammal["TABELLER"], 3)
