"""Tester för den deterministiska förbesiktningen (pipeline/preflight.py).

Varje regel motsvarar ett mönster som faktiskt återkom sida efter sida i
korrekturen av DoD-grundreglerna 1991 — fallen nedan är hämtade därifrån.
"""
import json
import tempfile
import unittest
from pathlib import Path

from pipeline.manifest import Manifest, page_file, read_json
from pipeline.preflight import (PAGE_FORM, PAGE_PROSE, PAGE_TABLE,
                                classify_page, decisions_file,
                                ensure_decisions_file, preflight,
                                rule_column_interleaving, rule_column_merge,
                                rule_heading_dash, rule_plusminus,
                                rule_reading_order, rule_row_merge,
                                rule_straight_quotes, rule_table_candidate,
                                scan_page, table_blocks)


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

    def test_felmarkt_region_doljer_inte_felet(self):
        """Geometrin gäller, inte etiketten.

        På s. 4 låg högerspaltens avsnittsrubrik som element nr 2, före hela
        vänsterspalten, med regionen felaktigt satt till `sidhuvud`. Filtrerar
        regeln på etiketten passerar läsordningsfelet obemärkt — exporten följer
        arrayordningen literalt, så vänsterspalten hamnade under fel rubrik.
        """
        elements = self._sida("de färdigheter, t. ex. Hantverk. Det som avgör")
        elements[1]["source"]["region"] = "sidhuvud"
        hits = rule_column_interleaving(elements)
        self.assertEqual([e["id"] for e, _ in hits], ["e02"])

    def test_felplacerad_rubrik_flaggas_trots_kort_text(self):
        """Sida 4:s verkliga fel: `ATT LEDA SPELET` (15 tecken) i högerspalten,
        placerad före hela vänsterspalten. Längdfiltret får inte tysta den —
        exporten renderar då vänsterspalten under fel rubrik."""
        elements = self._sida("x")
        elements[1]["type"] = "heading"
        elements[1]["text"] = "ATT LEDA SPELET"
        elements[1]["source"]["region"] = "sidhuvud"
        elements[1]["source"]["bbox"] = [0.58788, 0.91286, 0.2702, 0.015]
        hits = rule_column_interleaving(elements)
        self.assertEqual([e["id"] for e, _ in hits], ["e02"])

    def test_sidbrett_element_tillhor_ingen_spalt(self):
        """Ett sidhuvud som verkligen ÄR sidbrett ska inte dömas som spaltrad."""
        elements = self._sida("de färdigheter, t. ex. Hantverk. Det som avgör")
        elements[1]["source"]["region"] = "sidhuvud"
        elements[1]["source"]["bbox"] = [0.06, 0.95, 0.87, 0.018]
        self.assertEqual(rule_column_interleaving(elements), [])


def rutnat(prefix, rows, xs, y0=0.70, dy=0.0155, h=0.0145,
           region="vänsterkolumn", regions=None):
    """Bygg ett tabellrutnät med uppmätt geometri ur DoD-grundreglerna.

    `regions` kan ge en egen region per kolumn — tabellen på s. 61 har sina
    två första kolumner i vänsterkolumnen och den tredje i högerkolumnen.
    """
    elements = []
    for r, cells in enumerate(rows):
        for c, text in enumerate(cells):
            elements.append(el("%s_r%dc%d" % (prefix, r, c), text,
                               bbox=[xs[c], y0 - r * dy, 0.09, h],
                               region=regions[c] if regions else region))
    return elements


TEKNIKLISTAN = [("Teknik", "Grundkostnad"), ("Avväpning", "1,0"),
                ("Bakåtspark", "0,5"), ("Bedövningsslag†", "1,0"),
                ("Blind strid", "2,0")]


def loptext(prefix, n=10, x=0.067, y0=0.90, region="vänsterkolumn"):
    return [el("%s%d" % (prefix, i), LANG_RAD + " ytterligare ord här",
               bbox=[x, y0 - i * 0.016, 0.435, 0.016], region=region)
            for i in range(n)]


class TestTableCandidate(unittest.TestCase):
    def test_tekniklistan_flaggas(self):
        # Sida 58: 22 rader × 2 celler typade `paragraph`. Strukturen gick
        # förlorad och ingenting nedströms kunde återskapa den.
        hits = rule_table_candidate(rutnat("t", TEKNIKLISTAN, [0.112, 0.373]))
        self.assertEqual(len(hits), 1)
        el_, reason = hits[0]
        self.assertEqual(el_["id"], "t_r0c0")
        self.assertIn("tabellkandidat", reason)
        self.assertIn("2 kolumner × 5 rader", reason)

    def test_kolumn_i_annan_region_racker_med_de_ovriga(self):
        # Sida 61: vapengruppstabellens tredje kolumn ligger i högerkolumnen.
        # De två första räcker för att slå ut.
        rows = [("Dolkar", "SMI", "Dolk, Parerdolk"),
                ("Enhandssvärd", "STY", "Alla svärd med en hand"),
                ("Enhandsyxor", "STY", "Alla yxor med en hand"),
                ("Stickvapen", "STY", "Kortspjut, Långspjut")]
        elements = rutnat("v", rows, [0.115, 0.350, 0.467], y0=0.42,
                          regions=["vänsterkolumn", "vänsterkolumn",
                                   "högerkolumn"])
        blocks = table_blocks(elements)
        self.assertEqual([b["region"] for b in blocks], ["vänsterkolumn"])
        self.assertEqual(blocks[0]["columns"], 2)
        self.assertEqual(blocks[0]["rows"], 4)

    def test_ren_loptext_ar_tyst(self):
        # Sidorna 46, 47, 49–55: rena löptextsidor får inte ge ett larm.
        self.assertEqual(rule_table_candidate(loptext("v")), [])

    def test_styckens_korta_slutrader_ar_inte_kolumner(self):
        """Korta rader i EN vänsterkant bildar ingen tabell."""
        elements = loptext("v", n=8)
        elements += [el("k%d" % i, "och marginaler.",
                        bbox=[0.067, 0.70 - i * 0.05, 0.13, 0.016])
                     for i in range(5)]
        self.assertEqual(rule_table_candidate(elements), [])

    def test_blankettens_faltgrupper_parar_inte_ihop_sig(self):
        # Sidorna 67–68: två rutor kan råka börja på samma y-höjd utan att
        # höra ihop (beslut s. 67). Raderna ligger 0,06 isär, inte 0,015.
        rows = [("Skadebonus", "Tot. KP"), ("Bärförmåga", "PSY"),
                ("Vapen/Sköld", "BV"), ("Utrustning", "Vikt")]
        elements = rutnat("b", rows, [0.057, 0.335], y0=0.584, dy=0.061,
                          h=0.016)
        self.assertEqual(rule_table_candidate(elements), [])

    def test_for_fa_rader_racker_inte(self):
        elements = rutnat("t", TEKNIKLISTAN[:2], [0.112, 0.373])
        self.assertEqual(rule_table_candidate(elements), [])

    def test_reservformen_flaggas_inte(self):
        """`table_cell` är RÄTT reservform — den monteras, inte klandras."""
        elements = rutnat("t", TEKNIKLISTAN, [0.112, 0.373])
        for e in elements:
            e["type"] = "table_cell"
        self.assertEqual(rule_table_candidate(elements), [])

    def test_element_utan_bbox_kraschar_inte(self):
        self.assertEqual(rule_table_candidate([el("e1", "kort")]), [])

    def test_typningsfel_ger_flagga_inte_korrektionspost(self):
        """Fel elementtyp är ett typningsfel, inte ett textfel."""
        data = {"page": 58, "elements": rutnat("t", TEKNIKLISTAN,
                                               [0.112, 0.373])}
        out, counts = scan_page(data)
        self.assertEqual(counts["tabellkandidat"], 1)
        flaggade = [e for e in out["elements"] if e.get("needs_review")]
        self.assertEqual([e["id"] for e in flaggade], ["t_r0c0"])
        self.assertEqual([e.get("corrections") for e in out["elements"]],
                         [None] * len(out["elements"]))


LANG_RUBRIK = "PRIMÄRA FÄRDIGHETER"


class TestRowMerge(unittest.TestCase):
    def _sida(self, n=12):
        return [el("e%d" % i, LANG_RAD,
                   bbox=[0.067, 0.90 - i * 0.016, 0.435, 0.016])
                for i in range(n)]

    def test_dubbelhog_bbox_med_normala_glyfer_flaggas(self):
        # Sida 60: elementet spände över två tryckrader och återgav bara den
        # undre — raden ovanför saknades helt i draften. Glyfbredden är
        # normal (1,03× sidans median), bara boxen är dubbelt så hög.
        elements = self._sida()
        elements.append(el("e99", "Genma Frigke a Vands for at lara sig slas",
                           bbox=[0.067, 0.60, 0.325, 0.0336]))
        hits = rule_row_merge(elements)
        self.assertEqual([e["id"] for e, _ in hits], ["e99"])
        self.assertIn("radsammanslagning", hits[0][1])

    def test_normala_rader_ger_inget(self):
        self.assertEqual(rule_row_merge(self._sida()), [])

    def test_rubrik_i_stor_grad_ar_inte_sammanslagning(self):
        """Rubriken är hög för att GLYFERNA är stora — bbox är inte för hög."""
        elements = self._sida()
        elements.append(el("e99", LANG_RUBRIK,
                           bbox=[0.134, 0.95, 0.30, 0.0336]))
        self.assertEqual(rule_row_merge(elements), [])

    def test_kolumnsammanslagning_agas_av_sin_egen_regel(self):
        """Samma element ska inte flaggas av två regler."""
        elements = self._sida()
        elements.append(el("e99", (LANG_RAD + " ") * 2,
                           bbox=[0.067, 0.60, 0.89, 0.0336]))
        self.assertEqual(rule_row_merge(elements), [])
        self.assertEqual([e["id"] for e, _ in rule_column_merge(elements)],
                         ["e99"])

    def test_liten_sida_kraschar_inte(self):
        self.assertEqual(rule_row_merge([el("e1", "text", bbox=[0, 0, 1, 1])]),
                         [])


class TestClassifyPage(unittest.TestCase):
    def test_tvaspaltig_loptext(self):
        elements = loptext("v", n=10)
        elements += loptext("h", n=10, x=0.517, region="högerkolumn")
        self.assertEqual(classify_page(elements), PAGE_PROSE)

    def test_tabellsida(self):
        elements = rutnat("t", TEKNIKLISTAN, [0.112, 0.373])
        elements += loptext("v", n=6, y0=0.95)
        self.assertEqual(classify_page(elements), PAGE_TABLE)

    def test_blankett(self):
        # Sida 68: bara korta fältetiketter, utspridda över flera x-lägen.
        elements = []
        for i, x in enumerate((0.057, 0.335, 0.62)):
            elements += [el("f%d_%d" % (i, r), "Bärförmåga",
                            bbox=[x, 0.80 - r * 0.061, 0.10, 0.016])
                         for r in range(5)]
        self.assertEqual(classify_page(elements), PAGE_FORM)

    def test_for_liten_sida_klassas_inte(self):
        self.assertNotEqual(classify_page(loptext("v", n=3)), PAGE_PROSE)


class TestLasordningKorsBaraPaLoptext(unittest.TestCase):
    def test_loptextsida_ger_lasordningstraff(self):
        vanster = loptext("v", n=8)
        # Ett element vars y hör långt senare i spalten, inklämt på plats 3.
        vanster.insert(3, el("x1", LANG_RAD + " ytterligare ord här",
                             bbox=[0.067, 0.40, 0.435, 0.016]))
        elements = vanster + loptext("h", n=8, x=0.517, region="högerkolumn")
        out, counts = scan_page({"page": 1, "elements": elements})
        self.assertEqual(out["sidtyp"], PAGE_PROSE)
        self.assertGreater(counts["lasordning"], 0)

    def test_tabellsida_tystar_lasordningen(self):
        """Tabellrader läses tvärs över spalterna, inte spaltvis.

        Sidorna 61, 67 och 68 gav 23 läsordningslarm på en FÄRDIGKORREKTURLÄST
        bok — alla falska, alla skapade av advokatens korrekta omordning.
        """
        elements = rutnat("t", TEKNIKLISTAN, [0.112, 0.373])
        elements += loptext("v", n=6, y0=0.95)
        # Arrayordningen bryter mot y-ordningen: tabellen (y 0,70 och nedåt)
        # ligger före brödtexten (y 0,95 och nedåt). Regeln SKULLE larma.
        self.assertTrue(rule_reading_order(elements))
        out, counts = scan_page({"page": 58, "elements": elements})
        self.assertEqual(out["sidtyp"], PAGE_TABLE)
        self.assertEqual(counts["lasordning"], 0)
        self.assertEqual(counts["tabellkandidat"], 1)


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
