"""Tester för den deterministiska förbesiktningen (pipeline/preflight.py).

Varje regel motsvarar ett mönster som faktiskt återkom sida efter sida i
korrekturen av DoD-grundreglerna 1991 — fallen nedan är hämtade därifrån.
"""
import json
import tempfile
import unittest
from pathlib import Path

from pipeline.manifest import Manifest, page_file, read_json
from pipeline.preflight import (decisions_file, ensure_decisions_file,
                                preflight, rule_column_interleaving,
                                rule_column_merge, rule_heading_dash,
                                rule_plusminus, rule_reading_order,
                                rule_straight_quotes, scan_page)


def el(id_, text, bbox=None, region=None, **extra):
    e = {"id": id_, "type": "paragraph", "text": text, "confidence": 1}
    if bbox is not None:
        e["source"] = {"bbox": bbox, "region": region or "vänsterkolumn"}
    elif region:
        e["source"] = {"region": region}
    e.update(extra)
    return e


def dash_hits(text):
    """(regel, korrigerad text) för varje kandidat linjeregelregeln ger."""
    return [(rule, corr["corrected"])
            for rule, corr in rule_heading_dash(el("e", text))]


class TestHeadingDash(unittest.TestCase):
    def test_kapitalrubrik_med_streck_ger_kandidat(self):
        # Sida 42: linjeregelns vänstra ände lästes som ett bindestreck.
        hits = rule_heading_dash(el("e1", "- LYSSNA"))
        self.assertEqual(len(hits), 1)
        rule, corr = hits[0]
        self.assertEqual(rule, "linjeregel-prefix")
        self.assertEqual(corr["corrected"], "LYSSNA")
        self.assertEqual(corr["kind"], "ocr")
        self.assertFalse(corr["applied"])
        self.assertEqual(corr["source"], "heuristik:linjeregel-prefix")

    def test_flerordig_rubrik_och_snedstreck(self):
        self.assertEqual(dash_hits("- LÄSA/SKRIVA MODERSMÅL"),
                         [("linjeregel-prefix", "LÄSA/SKRIVA MODERSMÅL")])

    def test_gemen_punktlista_lamnas(self):
        # Riktiga punktlistor och avstavningar får inte röras.
        self.assertEqual(rule_heading_dash(el("e3", "- alver, dvärgar")), [])
        self.assertEqual(rule_heading_dash(el("e4", "- Bluffa (KAR)")), [])

    def test_rubrik_utan_streck_lamnas(self):
        self.assertEqual(rule_heading_dash(el("e5", "LYSSNA")), [])

    def test_suffix_ar_hogra_linjeregelns_ande(self):
        # Sidorna 45, 48, 49: `STJÄLA FÖREMÅL-`, `FÖRFALSKNING -`, `GEOGRAFI -`.
        # Heuristiken fångade tidigare bara prefixet, så varje suffix fick
        # hittas för hand av en agent.
        self.assertEqual(dash_hits("GEOGRAFI -"),
                         [("linjeregel-suffix", "GEOGRAFI")])
        self.assertEqual(dash_hits("STJÄLA FÖREMÅL-"),
                         [("linjeregel-suffix", "STJÄLA FÖREMÅL")])

    def test_punkt_som_suffix(self):
        # Sida 51: högerregelns spets lästes som en kula, inte ett streck.
        self.assertEqual(dash_hits("HASARDSPEL•"),
                         [("linjeregel-suffix", "HASARDSPEL")])

    def test_bada_andarna_i_samma_rubrik(self):
        # Sida 52: `- KUNSKAP OM MAGI -` — den gamla regeln lämnade suffixet.
        self.assertEqual(dash_hits("- KUNSKAP OM MAGI -"),
                         [("linjeregel-suffix", "KUNSKAP OM MAGI")])

    def test_osaker_markering_behalls(self):
        # `[?]` hör till en annan regel och ska inte städas bort på köpet.
        self.assertEqual(dash_hits("LÅSDYRKNING - [?]"),
                         [("linjeregel-suffix", "LÅSDYRKNING [?]")])

    def test_tabellcell_med_parentes_ar_inte_rubrik(self):
        # Sida 68, träfftabellen: `MAGE (-` är en cell vars vänsterparentes hör
        # till kolumnrubriken — inte en rubrik med linjeregelände.
        self.assertEqual(rule_heading_dash(el("e6", "MAGE (-")), [])
        self.assertEqual(rule_heading_dash(el("e7", "V. BEN ( -")), [])

    def test_negativa_tabellvarden_ror_inte(self):
        for text in ("-1", "-10", "- 5", "± 0"):
            self.assertEqual(rule_heading_dash(el("e8", text)), [], text)


class TestStraightQuotes(unittest.TestCase):
    def test_raka_citattecken_ger_typografiska(self):
        corr = rule_straight_quotes(el("e1", 'Han sa "hej" och gick'))
        self.assertEqual(corr[0]["corrected"], "Han sa ”hej” och gick")
        self.assertFalse(corr[0]["applied"])

    def test_apostrof_runt_siffra_bevaras_som_par(self):
        # Sida 40/41: trycket har ’6’ och ’8’ — apostrofen ska INTE strykas.
        corr = rule_straight_quotes(el("e2", "så måste han slå '6' eller lägre"))
        self.assertEqual(corr[0]["corrected"], "så måste han slå ’6’ eller lägre")

    def test_text_utan_raka_tecken_ger_inget(self):
        self.assertEqual(rule_straight_quotes(el("e3", "slå ’6’ eller lägre")), [])


class TestPlusMinus(unittest.TestCase):
    def test_kanda_garbel_ger_kandidat(self):
        for text in ("t0", "I0", "l0", "*0", "+0", "|0"):
            corr = rule_plusminus(el("e", text))
            self.assertEqual(corr[0]["corrected"], "±0", text)
            self.assertFalse(corr[0]["applied"], text)

    def test_tio_rattas_aldrig_bara_flaggas(self):
        # `10` går inte att skilja från talet tio — siffror emenderas aldrig.
        self.assertEqual(rule_plusminus(el("e", "10")), [])
        out, counts = scan_page({"page": 1, "elements": [el("e1", "10")]})
        self.assertTrue(out["elements"][0]["needs_review"])
        self.assertEqual(counts["plusminus"], 1)
        self.assertEqual(out["elements"][0].get("corrections", []), [])

    def test_lopande_text_med_10_ror_inte(self):
        self.assertEqual(rule_plusminus(el("e", "Smyga 10 steg")), [])


LANG_RAD = "Med ett lyckat färdighetsslag i denna färdighet har man"


class TestColumnMerge(unittest.TestCase):
    def _spalt(self, n=6, width=0.43):
        return [el("e%d" % i, LANG_RAD, bbox=[0.04, 0.9 - i * 0.02, width, 0.018])
                for i in range(n)]

    def test_dubbelbred_bbox_flaggas(self):
        # Sida 41: sex element slog ihop vänster- och högerkolumnens rader.
        elements = self._spalt()
        elements.append(el("e9", LANG_RAD + " horisontellt och halva sin längd",
                           bbox=[0.04, 0.75, 0.887, 0.018]))
        hits = rule_column_merge(elements)
        self.assertEqual([e["id"] for e, _ in hits], ["e9"])
        self.assertIn("kolumnsammanslagning", hits[0][1])

    def test_normala_spaltrader_ger_inget(self):
        self.assertEqual(rule_column_merge(self._spalt()), [])

    def test_korta_vardeelement_ger_inte_falska_positiver(self):
        # Sida 45: en sida med många korta tabellceller drog medianen till 0,206
        # så att varje normal brödtextrad såg dubbelbred ut. Percentilen ska
        # hålla emot.
        elements = self._spalt(n=8)
        elements += [el("v%d" % i, str(i), bbox=[0.30, 0.5 - i * 0.02, 0.03, 0.016])
                     for i in range(20)]
        self.assertEqual(rule_column_merge(elements), [])

    def test_centrerad_kapitalrubrik_ar_inte_sammanslagning(self):
        # Bred men kort: sidhuvudet spänner över båda spalterna i alla böcker.
        elements = self._spalt()
        elements.append(el("e9", "PRIMÄRA FÄRDIGHETER",
                           bbox=[0.134, 0.95, 0.704, 0.02]))
        self.assertEqual(rule_column_merge(elements), [])

    def test_element_utan_bbox_kraschar_inte(self):
        self.assertEqual(rule_column_merge([el("e1", "text")]), [])


class TestReadingOrder(unittest.TestCase):
    def test_felplacerat_element_flaggas(self):
        # Sida 41: "den." låg först i högerkolumnens segment men hörde långt
        # senare. y räknas från nederkanten, dvs. minskar framåt i läsordningen.
        elements = [
            el("e1", "först", bbox=[0.5, 0.90, 0.42, 0.018], region="högerkolumn"),
            el("e2", "den.", bbox=[0.5, 0.38, 0.42, 0.018], region="högerkolumn"),
            el("e3", "sedan", bbox=[0.5, 0.86, 0.42, 0.018], region="högerkolumn"),
            el("e4", "sist", bbox=[0.5, 0.84, 0.42, 0.018], region="högerkolumn"),
        ]
        hits = rule_reading_order(elements)
        self.assertIn("e2", [e["id"] for e, _ in hits])

    def test_monoton_ordning_ger_inget(self):
        elements = [el("e%d" % i, "rad", bbox=[0.5, 0.9 - i * 0.02, 0.42, 0.018],
                       region="högerkolumn") for i in range(5)]
        self.assertEqual(rule_reading_order(elements), [])

    def test_spalter_bedoms_var_for_sig(self):
        # Ny spalt börjar om högst upp — det är inte ett läsordningsfel.
        elements = [el("v%d" % i, "v", bbox=[0.04, 0.9 - i * 0.02, 0.43, 0.018],
                       region="vänsterkolumn") for i in range(4)]
        elements += [el("h%d" % i, "h", bbox=[0.5, 0.9 - i * 0.02, 0.42, 0.018],
                        region="högerkolumn") for i in range(4)]
        self.assertEqual(rule_reading_order(elements), [])

    def test_elementet_foreslas_aldrig_som_sitt_eget_mal(self):
        # Sidorna 47, 49 och 52: motivtexten pekade ut elementet självt ("rätt
        # plats är sannolikt efter p047_e51" för e51), eftersom elementet
        # uppfyller sitt eget y-villkor. Det såg ut som en motsägelse och
        # kostade en agentkörning per sida att avfärda som falsk positiv.
        elements = [
            el("e1", "först", bbox=[0.5, 0.90, 0.42, 0.018], region="högerkolumn"),
            el("e2", "sedan", bbox=[0.5, 0.86, 0.42, 0.018], region="högerkolumn"),
            el("e3", "hoppar", bbox=[0.5, 0.40, 0.42, 0.018], region="högerkolumn"),
            el("e4", "sist", bbox=[0.5, 0.84, 0.42, 0.018], region="högerkolumn"),
        ]
        hits = dict((e["id"], reason) for e, reason in rule_reading_order(elements))
        self.assertIn("e3", hits)
        self.assertNotIn("efter e3", hits["e3"])
        # e4 ligger lägst (y=0.84) av raderna ovanför e3 — alltså rätt plats.
        self.assertIn("efter e4", hits["e3"])


class TestColumnInterleaving(unittest.TestCase):
    def _sida(self, right_first_text):
        """Högerkolumnens första rad inklämd som element nr 2 (sida 40:s fel)."""
        elements = [el("e01", "PRIMÄRA FÄRDIGHETER", bbox=[0.13, 0.95, 0.70, 0.02],
                       region="vänsterkolumn"),
                    el("e02", right_first_text, bbox=[0.51, 0.90, 0.42, 0.018],
                       region="högerkolumn")]
        elements += [el("v%d" % i, LANG_RAD, bbox=[0.04, 0.90 - i * 0.02, 0.43, 0.018],
                        region="vänsterkolumn") for i in range(10)]
        elements += [el("h%d" % i, LANG_RAD, bbox=[0.51, 0.88 - i * 0.02, 0.42, 0.018],
                        region="högerkolumn") for i in range(10)]
        return elements

    def test_hogerkolumnsrad_i_borjan_flaggas(self):
        hits = rule_column_interleaving(
            self._sida("de färdigheter, t. ex. Hantverk. Det som avgör"))
        self.assertEqual([e["id"] for e, _ in hits], ["e02"])

    def test_kort_element_ar_sidhuvud_inte_brodtext(self):
        self.assertEqual(rule_column_interleaving(self._sida("Natt:")), [])

    def test_vanlig_spaltvaxling_ger_inget(self):
        elements = [el("v%d" % i, LANG_RAD, bbox=[0.04, 0.90 - i * 0.02, 0.43, 0.018],
                       region="vänsterkolumn") for i in range(10)]
        elements += [el("h%d" % i, LANG_RAD, bbox=[0.51, 0.90 - i * 0.02, 0.42, 0.018],
                        region="högerkolumn") for i in range(10)]
        self.assertEqual(rule_column_interleaving(elements), [])

    def test_enspaltssida_undantas(self):
        elements = [el("e%d" % i, LANG_RAD, bbox=[0.04, 0.9 - i * 0.02, 0.86, 0.018],
                       region="text") for i in range(10)]
        self.assertEqual(rule_column_interleaving(elements), [])


class TestScanPageOchKorning(unittest.TestCase):
    def test_indata_muteras_inte(self):
        data = {"page": 7, "elements": [el("e1", "- LYSSNA")]}
        scan_page(data)
        self.assertEqual(data["elements"][0].get("corrections"), None)

    def test_summering_raknar_per_regel(self):
        data = {"page": 7, "elements": [
            el("e1", "- LYSSNA"),
            el("e2", 'han sa "hej"'),
            el("e3", "t0"),
        ]}
        out, counts = scan_page(data)
        self.assertEqual(counts["linjeregel-prefix"], 1)
        self.assertEqual(counts["raka-citattecken"], 1)
        self.assertEqual(counts["plusminus"], 1)
        self.assertEqual(out["source"], "heuristik")


class TestPreflightKorning(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        source = self.tmp / "kalla.pdf"
        source.write_bytes(b"%PDF-1.4 attrapp")
        Manifest.create(self.tmp, source, 2)
        m = Manifest.load(self.tmp)
        for no in (1, 2):
            m.page(no)["state"] = "validated"
        m.save()
        for no in (1, 2):
            path = page_file(self.tmp, no, "validated.json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(
                {"page": no, "elements": [el("p%d_e1" % no, "- SMYGA")]}),
                encoding="utf-8")

    def _heuristik(self, no):
        return Path(str(page_file(self.tmp, no, "review"))) / "heuristik.json"

    def test_skriver_kandidater_och_beslutsfil(self):
        results = preflight(self.tmp)
        self.assertEqual([no for no, _ in results], [1, 2])
        data = read_json(self._heuristik(1))
        self.assertEqual(data["elements"][0]["corrections"][0]["corrected"],
                         "SMYGA")
        self.assertTrue(decisions_file(self.tmp).is_file())

    def test_idempotent_utan_force(self):
        preflight(self.tmp)
        self._heuristik(1).write_text('{"rord": true}', encoding="utf-8")
        results = dict(preflight(self.tmp))
        self.assertIsNone(results[1])  # hoppades över
        self.assertEqual(read_json(self._heuristik(1)), {"rord": True})
        preflight(self.tmp, force=True)
        self.assertIn("elements", read_json(self._heuristik(1)))

    def test_hoppar_over_klara_sidor(self):
        final = page_file(self.tmp, 1, "final.json")
        final.write_text('{"page": 1, "elements": []}', encoding="utf-8")
        self.assertEqual([no for no, _ in preflight(self.tmp)], [2])

    def test_beslutsfil_skrivs_inte_over(self):
        path = ensure_decisions_file(self.tmp)
        path.write_text("# Mina beslut\n", encoding="utf-8")
        ensure_decisions_file(self.tmp)
        self.assertEqual(path.read_text(encoding="utf-8"), "# Mina beslut\n")


if __name__ == "__main__":
    unittest.main()
