"""Adaptern system/dod — luckor som produktionskörningen av del II blottade.

Ett test per lucka (beslut.md F i
arbete/DOD-REG-grundregler-1991-del2-spelledarboken/). Testerna låser fast
DATAN i system/dod/, inte pipelinelogiken: adaptern är ren data och kan
regenereras av scripts/bygg_adapter.py, så de här fyra rättningarna måste ha
ett larm som går om de försvinner.
"""
import re
import unittest

from pipeline.corrections import repair_dice_token, scan_dice_in_text
from pipeline.systems import load

DOD = load("dod")


def _sb_bonus(sum_sto_sty):
    """Slå upp skadebonus i adapterns tabell. None om summan ligger utanför."""
    for row in DOD.system["sb_table"]["rows"]:
        if row["min"] <= sum_sto_sty <= row["max"]:
            return row["bonus"]
    return None


class TestSkadebonustabellen(unittest.TestCase):
    """DRAKE (del II s. 31) har STY 100 + STO 100 = 200 och tryckt SB +6T6.

    Tabellen slutade på 141-180 (+5T6) och kunde inte slå upp varelsen alls.
    Utökningen följer tabellens egen steglängd — varelsens värde emenderas
    aldrig för att passa adaptern.
    """

    def test_drakens_summa_slar_upp_till_tryckt_bonus(self):
        self.assertEqual(_sb_bonus(100 + 100), "+6T6")

    def test_tabellen_ar_sammanhangande_och_stigande(self):
        rows = DOD.system["sb_table"]["rows"]
        for prev, row in zip(rows, rows[1:]):
            self.assertEqual(row["min"], prev["max"] + 1,
                             "glapp eller överlapp vid %r" % row)

    def test_extrapolerad_rad_ar_markt_som_sadan(self):
        # Raden står inte i det tryckta originalet; det får inte gå förlorat.
        rows = DOD.system["sb_table"]["rows"]
        self.assertTrue(rows[-1].get("extrapolated"))
        self.assertNotIn("extrapolated", rows[-2],
                         "tryckta rader ska inte vara märkta som härledda")


class TestSkolvarde(unittest.TestCase):
    """SV = Skolvärde, inte Skyddsvärde.

    Bokens egen förkortningsnyckel (del II s. 62: `| SV | Skolvärde |`) är
    auktoritativ, och del I:s extraktion har samma form
    (`| Skolvärde | Grundkostnad |`). Felet fanns på två ställen i adaptern —
    lexikonposten är den farliga, eftersom den matar validatorns ordindex.
    """

    def test_derived_label(self):
        self.assertEqual(DOD.system["derived_labels"]["SV"], "Skolvärde")

    def test_lexikonterm(self):
        self.assertEqual(DOD.lexicon["terms"]["SV"], "Skolvärde")

    def test_ordindexet_kanner_igen_skolvarde(self):
        self.assertIn("Skolvärde", DOD.words["skolvarde"])
        self.assertNotIn("skyddsvarde", DOD.words)


class TestTankstreckINotationen(unittest.TestCase):
    """`3T6–2` (del II s. 34) sätts med TANKSTRECK, inte bindestreck-minus.

    Före rättningen föll token utanför `DICE_TOKEN` helt: ingen reparation,
    ingen flagga — ett tyst hål i täckningen. Båda tecknen är giltig notation,
    och teckenvalet är sättning: det normaliseras aldrig bort.
    """

    TANKSTRECK = "3T6–2"
    BINDESTRECK = "3T6-2"

    def test_bada_formerna_ar_giltig_notation(self):
        for token in (self.TANKSTRECK, self.BINDESTRECK):
            status, corr = repair_dice_token(token, DOD.dice)
            self.assertEqual(status, "ok", token)
            self.assertIsNone(corr)

    def test_tankstrecket_normaliseras_inte_bort(self):
        text = "Draken andas eld för %s kroppspoäng." % self.TANKSTRECK
        corrections, flags = scan_dice_in_text(text, DOD.dice, DOD.words)
        self.assertEqual(corrections, [])
        self.assertEqual(flags, [])

    def test_datafilens_grammatik_speglar_koden(self):
        notation = re.compile(DOD.dice["notation"])
        self.assertTrue(notation.match(self.TANKSTRECK))
        self.assertTrue(notation.match(self.BINDESTRECK))

    def test_skadad_token_med_tankstreck_repareras_till_tankstreck(self):
        # Tecknet som trycket sätter följer med reparationen.
        status, corr = repair_dice_token("3I6–Z", DOD.dice)
        self.assertEqual(status, "fixed")
        self.assertEqual(corr["corrected"], self.TANKSTRECK)


class TestForflyttningArIngenHarledd(unittest.TestCase):
    """Förflyttning får INTE bli en `derived_checks`-kontroll.

    Del I:s tabell (STO+FYS+SMI -> Förflyttning) gäller rollpersoner. Prövad
    mot del II:s varelsekapitel avviker 18 av 29 landvarelser med hela
    STO/FYS/SMI — KENTAUR 48 ger tabell 12 mot tryckt L24, DRAKE 157 ger 25 mot
    L14. Kroppsbyggnaden styr värdet och finns inte i statblocket. En kontroll
    skulle alltså larma på korrekt tryckta värden. Skälet står i adaptern så att
    frågan inte utreds om.
    """

    def test_ingen_kontroll_pa_forflyttning(self):
        fields = [c["field"] for c in DOD.system.get("derived_checks", [])]
        self.assertNotIn("Förflyttning", fields)

    def test_uteslutningen_ar_dokumenterad_med_skal(self):
        excluded = {c["field"]: c
                    for c in DOD.system.get("derived_checks_excluded", [])}
        self.assertIn("Förflyttning", excluded)
        post = excluded["Förflyttning"]
        for key in ("reason", "evidence", "source"):
            self.assertTrue(post.get(key), "%s saknas" % key)


if __name__ == "__main__":
    unittest.main()
