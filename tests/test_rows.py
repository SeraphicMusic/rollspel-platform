"""Tester för den deterministiska uppmätningen av radboxar (pipeline/rows.py).

Bilderna byggs syntetiskt så att facit är känt exakt. De två fällor som
faktiskt sänkte de första versionerna mot riktiga skanningar har egna tester:
rastrerat papper (per-pixel-tröskling går sönder) och gråtonade tabellrader
(medelsvärta går sönder).
"""
import unittest

import numpy as np

from pipeline.rows import (EDGE_BAND, KIND_GRAPHIC, KIND_ROW, _columns,
                           _extent, _merge_and_classify, _segments, darkness,
                           ink_share, measure_dark, summarise)

HEIGHT, WIDTH = 800, 600
LINE_H, PITCH = 10, 24


def blank(value=255):
    return np.full((HEIGHT, WIDTH), value, dtype=np.uint8)


def write_line(page, top, lo, hi, ink=40):
    """Lägg en 'textrad' som omväxlande mörka och ljusa pixlar (bokstäver)."""
    row = page[top:top + LINE_H, lo:hi]
    row[:, ::3] = ink
    row[:, 1::3] = ink + 30


def page_with_lines(count, top0=100, lo=60, hi=280, pitch=PITCH):
    page = blank()
    tops = [top0 + i * pitch for i in range(count)]
    for top in tops:
        write_line(page, top, lo, hi)
    return page, tops


class TestRowDetection(unittest.TestCase):
    def test_raknar_raderna_i_en_spalt(self):
        page, tops = page_with_lines(8)
        rows, _ = measure_dark(darkness(page))
        body = [r for r in rows if r["region"] not in ("sidhuvud", "sidfot")]
        self.assertEqual(len(body), 8)

    def test_bbox_har_y_fran_nederkanten(self):
        """Repots konvention: y = avstånd från sidans NEDERKANT till underkant."""
        page, tops = page_with_lines(6)
        rows, _ = measure_dark(darkness(page))
        body = [r for r in rows if r["region"] not in ("sidhuvud", "sidfot")]
        # Första raden i läsordning är den ÖVERSTA, alltså den med störst y.
        forsta = body[0]["bbox"]
        vantad_y = (HEIGHT - (tops[0] + LINE_H)) / HEIGHT
        self.assertAlmostEqual(forsta[1], vantad_y, places=2)
        self.assertGreater(forsta[1], body[-1]["bbox"][1])

    def test_bbox_mater_radens_faktiska_x(self):
        page, _ = page_with_lines(6, lo=90, hi=300)
        rows, _ = measure_dark(darkness(page))
        body = [r for r in rows if r["region"] not in ("sidhuvud", "sidfot")]
        x, _, bredd, _ = body[0]["bbox"]
        self.assertAlmostEqual(x, 90 / WIDTH, places=2)
        self.assertAlmostEqual(bredd, 210 / WIDTH, places=2)

    def test_rastrerat_papper_ger_inga_falska_rader(self):
        """Skanningens papper är brus, inte vitt — per-pixel-tröskling faller.

        Uppmätt på del I s. 58: 27 % av pixlarna i ett TOMT radmellanrum ligger
        under Otsu-tröskeln, så en metod som räknar mörka pixlar hittar text
        överallt. Måttet är att varje TRYCKT rad ska täckas av ett band — inte
        att bandantalet är exakt, vilket är samma mått som kalibreringen mot
        den färdiga del I använder.
        """
        rng = np.random.default_rng(20260731)
        page, tops = page_with_lines(8)
        # Rastret sitter i satsytan; marginalerna är rent papper. Så ser de
        # verkliga skanningarna ut — profilen i en tom marginal mätte 0,5 av
        # 255 medan den i ett radmellanrum inne i satsen mätte 66.
        yta = (slice(90, 290), slice(50, 290))
        brus = rng.integers(190, 256, size=page[yta].shape, dtype=np.uint16)
        page[yta] = np.minimum(page[yta].astype(np.uint16), brus)
        rows, _ = measure_dark(darkness(page))
        body = [r for r in rows if r["region"] not in ("sidhuvud", "sidfot")]
        for top in tops:
            mitt = (HEIGHT - (top + LINE_H / 2)) / HEIGHT
            self.assertTrue(
                any(r["bbox"][1] <= mitt <= r["bbox"][1] + r["bbox"][3]
                    for r in body), "rad vid y=%.3f saknar band" % mitt)

    def test_gratonad_tabellrad_delas_pa_texten(self):
        """Medelsvärta slår ihop en skuggad tabell till ett enda band.

        Del II s. 27: fyllningen mätte 85–90 i medelsvärta med OCH utan text.
        Kontrasten skilde dem (19–25 mot 65–69), och det är den profilen som
        används.
        """
        page = blank()
        page[100:100 + 6 * PITCH, 60:280] = 170          # grå fyllning
        tops = [100 + i * PITCH + 6 for i in range(6)]
        for top in tops:
            write_line(page, top, 70, 270, ink=20)
        rows, _ = measure_dark(darkness(page))
        body = [r for r in rows if r["region"] not in ("sidhuvud", "sidfot")]
        self.assertEqual(len(body), 6)
        self.assertTrue(all(r["kind"] == KIND_ROW for r in body))

    def test_jamn_ton_utan_sats_ger_ingen_rad(self):
        """En gråplatta är inte text, hur mörk den än är.

        Det är den egenskapen som gör att kontrastprofilen klarar skuggade
        tabeller: fyllningen i sig får aldrig bli en rad. (Att medelsvärtan
        misslyckas med samma tabell är mätt i trycket, se `row_profile` —
        det går inte att visa trovärdigt på en syntetisk bild utan att
        skräddarsy fixturen tills den ger rätt svar.)
        """
        page = blank()
        page[100:280, 60:280] = 170
        rows, _ = measure_dark(darkness(page))
        self.assertEqual(
            [r for r in rows if r["region"] not in ("sidhuvud", "sidfot")], [])


class TestColumns(unittest.TestCase):
    def _tvaspaltig(self):
        page = blank()
        for i in range(8):
            write_line(page, 100 + i * PITCH, 40, 270)
            write_line(page, 100 + i * PITCH, 330, 560)
        return page

    def test_tva_spalter_hittas_och_namnges(self):
        rows, columns = measure_dark(darkness(self._tvaspaltig()))
        self.assertEqual([c["region"] for c in columns],
                         ["vänsterkolumn", "högerkolumn"])

    def test_lasordningen_ar_hela_vansterspalten_forst(self):
        """Transkriptionskontraktet kräver spaltvis ordning, inte radvis."""
        rows, _ = measure_dark(darkness(self._tvaspaltig()))
        body = [r for r in rows if r["region"] not in ("sidhuvud", "sidfot")]
        regioner = [r["region"] for r in body]
        self.assertEqual(regioner, ["vänsterkolumn"] * 8 + ["högerkolumn"] * 8)

    def test_spalter_mats_per_avsnitt(self):
        """Del I s. 61: tvåspaltig löptext överst, fullbredds tabell nedtill.

        Mäts spalterna en gång för hela sidan fyller tabellen rännan, och
        vänster- och högerspaltens rader slås ihop till gemensamma band.
        """
        page = self._tvaspaltig()
        for i in range(5):                       # fullbredds tabell längre ned
            write_line(page, 460 + i * PITCH, 40, 560)
        rows, columns = measure_dark(darkness(page))
        self.assertIn("sidbredd", [c["region"] for c in columns])
        self.assertEqual(
            len([r for r in rows if r["region"] == "vänsterkolumn"]), 8)


class TestPageFurniture(unittest.TestCase):
    def test_sidhuvud_och_sidfot_skiljs_ut(self):
        page, _ = page_with_lines(6, top0=200)
        write_line(page, 30, 200, 400)            # sidhuvud
        write_line(page, HEIGHT - 40, 290, 310)   # foliosiffra
        rows, _ = measure_dark(darkness(page))
        self.assertEqual([r["region"] for r in rows][0], "sidhuvud")
        self.assertEqual([r["region"] for r in rows][-1], "sidfot")

    def test_liten_foliosiffra_dranks_inte_av_linjeregeln(self):
        """Alla 13 foliosiffror i del I föll bort innan kantzonerna mättes
        fönstervis: linjeregeln spänner över hela bredden och satte tröskeln,
        och en siffra på 0,017 av sidbredden nådde aldrig dit.
        """
        page, _ = page_with_lines(6, top0=200)
        page[HEIGHT - 70:HEIGHT - 67, 40:560] = 20   # linjeregel över sidfoten
        write_line(page, HEIGHT - 40, 292, 308)      # foliosiffra
        rows, _ = measure_dark(darkness(page))
        fot = [r for r in rows if r["region"] == "sidfot"]
        mitt = (HEIGHT - (HEIGHT - 40 + LINE_H / 2)) / HEIGHT
        self.assertTrue(
            any(r["bbox"][1] <= mitt <= r["bbox"][1] + r["bbox"][3]
                for r in fot), "foliosiffran saknar band: %s" % fot)

    def test_hog_texturerad_yta_klassas_som_grafik(self):
        """En illustration är texturerad, inte jämn — den ger ett högt band.

        En HELT jämn svart platta ger däremot ingen kontrast alls och syns
        bara som sina kanter. Det är riktigt: en jämn ton är inte sats.
        """
        # Ett bildparti har kontrast i VARJE bildrad över hela sin höjd (här
        # en skraffering), till skillnad från sats som växlar rad och
        # mellanrum. Bandet blir ett enda, och lika högt som de verkliga
        # illustrationsbanden i trycket: 20–55 radhöjder.
        page, _ = page_with_lines(6)
        page[380:700, 60:280:4] = 30
        rows, _ = measure_dark(darkness(page))
        self.assertIn(KIND_GRAPHIC, [r["kind"] for r in rows])

    def test_summering_varnar_nar_grafiken_dominerar(self):
        rader = [{"region": "vänsterkolumn", "kind": KIND_GRAPHIC},
                 {"region": "sidbredd", "kind": KIND_ROW},
                 {"region": "vänsterkolumn", "kind": KIND_ROW}]
        self.assertTrue(summarise(rader)["dominerande_grafik"])

    def test_skrafferad_bild_flaggas_pa_blackandel(self):
        """Bandfördelningen ensam missar en streckskrafferad illustration.

        Del III s. 3 är en helsidesbild med bara en rubrik och en foliosiffra,
        men mätningen gav 176 "rader" varav 136 i SPALTREGIONER — skrafferingen
        ser ut som vanliga textrader. Andelen grafik- och fullbreddsband blev
        24 % och flaggan tego. Bläckandelen avslöjar sidan direkt: 52 % mot
        textsidornas 9-13 % (median över del II och III: 11 %).
        """
        rader = [{"region": "vänsterkolumn", "kind": KIND_ROW}] * 136
        self.assertFalse(summarise(rader)["dominerande_grafik"])
        self.assertFalse(summarise(rader, 0.11)["dominerande_grafik"])
        flaggad = summarise(rader, 0.52)
        self.assertTrue(flaggad["dominerande_grafik"])
        self.assertEqual(flaggad["black_andel"], 0.52)

    def test_blackandel_raknas_i_satsytan(self):
        """Marginalerna räknas bort — de är alltid papper."""
        page = blank()
        page[100:700, 60:540] = 0            # svart platta mitt på sidan
        andel = ink_share(darkness(page))
        self.assertGreater(andel, 0.3)
        self.assertLess(ink_share(darkness(blank())), 0.01)

    def test_summering_ar_tyst_pa_en_vanlig_textsida(self):
        rader = [{"region": "vänsterkolumn", "kind": KIND_ROW}] * 20
        summering = summarise(rader)
        self.assertFalse(summering["dominerande_grafik"])
        self.assertEqual(summering["rader"], 20)

    def test_tom_sida_ger_inga_rader(self):
        rows, columns = measure_dark(darkness(blank()))
        self.assertEqual(rows, [])


class TestMatdefekterBok2(unittest.TestCase):
    """De sex mätdefekterna i beslut.md D för DoD-grundreglerna del II.

    Ingen av dem rör texten; alla rör `source.bbox`. Varje test återskapar
    defektens geometri syntetiskt, så att facit är känt exakt.
    """

    # Tryckets proportioner, till skillnad från modulens övriga fixturer:
    # radhöjden är STÖRRE än radavståndet (uppmätt i del II: 25 px sats,
    # 10 px mellanrum). Det är den ordningen `EDGE_GAP_FACTOR` vilar på.
    RAD_H, RAD_PITCH = 18, 26

    def _glyfrad(self, page, top, lo, hi, ink=30):
        """Rad med LODRÄT struktur — bokstäver fyller inte hela radhöjden.

        Fixturens `write_line` fyller hela bandet med samma värde, och då har
        en kolumn ingen spridning i y-led alls. Verklig sats har det, och det
        är den spridningen som skiljer glyf från tonplatta.
        """
        page[top + 3:top + self.RAD_H - 3, lo:hi:3] = ink
        page[top + 1:top + self.RAD_H - 1, lo + 1:hi:6] = ink + 40

    def _tvaspaltig(self, top0, count=8):
        page = blank()
        tops = [top0 + i * self.RAD_PITCH for i in range(count)]
        for top in tops:
            self._glyfrad(page, top, 40, 270)
            self._glyfrad(page, top, 330, 560)
        return page, tops

    # -- D 1 -------------------------------------------------------------
    def test_hog_satsyta_lagger_inte_forsta_raden_i_sidhuvudet(self):
        """Satsytan börjar ovanför 8 %-gränsen — raden är ändå kropp.

        Med lägeskriteriet hamnade spalternas översta rad i sidhuvudzonen och
        mättes om som ETT fullbreddsband; ~16 av del II:s sidor har artefakten,
        med `bbox_saknas` på spaltens första element som symptom.
        """
        top0 = int(HEIGHT * EDGE_BAND) - self.RAD_PITCH
        page, tops = self._tvaspaltig(top0)
        rows, _ = measure_dark(darkness(page))
        self.assertEqual([r for r in rows if r["region"] == "sidhuvud"], [])
        overst = max(r["bbox"][1] for r in rows)
        vantad = (HEIGHT - (tops[0] + self.RAD_H)) / HEIGHT
        self.assertAlmostEqual(overst, vantad, places=2)

    def test_isolerad_kolumntitel_ar_fortfarande_sidhuvud(self):
        """Motprovet: det som STÅR FÖR SIG upptill är ett sidhuvud."""
        page, _ = self._tvaspaltig(200)
        self._glyfrad(page, 30, 200, 400)
        rows, _ = measure_dark(darkness(page))
        self.assertEqual(rows[0]["region"], "sidhuvud")
        self.assertEqual(len([r for r in rows if r["region"] == "sidhuvud"]), 1)

    # -- D 2 -------------------------------------------------------------
    def test_ingen_enstegsforskjutning_av_spaltens_band(self):
        """Varje spalt ska ha exakt ett band per tryckt rad, inte ett för lite.

        Artefakten i D 1 yttrade sig ibland inte som saknad box utan som en
        förskjutning: banden flyttades upp ett steg och två element bar
        grannradens koordinater (s. 55; kandidatlista för sju sidor).
        """
        page, tops = self._tvaspaltig(int(HEIGHT * EDGE_BAND) - self.RAD_PITCH)
        rows, _ = measure_dark(darkness(page))
        for region in ("vänsterkolumn", "högerkolumn"):
            spalt = [r for r in rows if r["region"] == region]
            self.assertEqual(len(spalt), len(tops), region)
            for band, top in zip(spalt, tops):
                self.assertAlmostEqual(
                    band["bbox"][1], (HEIGHT - (top + self.RAD_H)) / HEIGHT,
                    places=2, msg="%s: band mot fel rad" % region)

    # -- D 3 -------------------------------------------------------------
    def test_folion_overlever_sidans_radhojdsgolv(self):
        """En foliosiffra är tunn mätt mot brödtexten — men är ingen brus.

        Kantzonens band mättes mot SIDANS radhöjd, och en folio som
        `zone_profile` bryter i 2-4 px höga bitar föll då under brusgolvet.
        Det som märktes `sidfot` blev i stället föregående rads underlängder
        eller vattenstämpeln (s. 19, 26, 43, 57, 59).
        """
        page, _ = page_with_lines(6, top0=200)
        # Brödtext i normal grad, folio i mycket liten grad längst ned.
        page[HEIGHT - 40:HEIGHT - 37, 295:305] = 20
        rows, _ = measure_dark(darkness(page))
        fot = [r for r in rows if r["region"] == "sidfot"]
        self.assertTrue(fot, "folion föll bort som skanningsbrus")
        self.assertLess(fot[-1]["bbox"][1], 0.1)

    def test_stank_i_sidfoten_ar_ingen_rad(self):
        """Zonens eget brusgolv får inte släppa igenom enstaka stänk."""
        page, _ = page_with_lines(6, top0=200)
        # Tryckets proportioner: stänk mäter 1-5 px av 1980, folion 12 px.
        page[HEIGHT - 40:HEIGHT - 37, 300:300 + int(0.0025 * WIDTH)] = 20
        rows, _ = measure_dark(darkness(page))
        self.assertEqual([r for r in rows if r["region"] == "sidfot"], [])

    def test_ensam_smal_foliosiffra_kastas_inte_av_breddsparren(self):
        """En folio `1` är den smalaste VERKLIGA raden på en sida.

        Bokens smala kantband ligger på 1-5 px (stänk) och sedan 12 px, som
        är s. 2:s folio. En spärr satt över 12 px tar tillbaka just det som
        kantzonernas egna brusgolv (D 3) nyss vunnit.
        """
        page, _ = page_with_lines(6, top0=200)
        bredd = int(0.0061 * WIDTH)                   # s. 2:s folio: 12/1980
        page[HEIGHT - 40:HEIGHT - 34, 300:300 + bredd] = 20
        rows, _ = measure_dark(darkness(page))
        fot = [r for r in rows if r["region"] == "sidfot"]
        self.assertTrue(fot, "den smala folion kastades som stänk")

    # -- D 4 -------------------------------------------------------------
    def test_linjeornament_och_folio_blir_skilda_band(self):
        """Sidfotens ornament får inte hamna i folions `source.rader` (s. 48).

        Banden är hämtade ur sidfotszonen på del II s. 43 (bildhöjd 2800):
        linjeregeln, tre fragment av foliosiffran och vattenstämpeln. Regeln
        och folion ligger 36 px isär och ska förbli skilda; fragmenten ligger
        6-14 px isär och hör till samma siffra.
        """
        zonband = [(2626, 2630), (2666, 2668), (2682, 2684), (2690, 2693),
                   (2707, 2738)]
        ut = _merge_and_classify(zonband, page_median=22,
                                 noise_from_page=False)
        spann = [(a, b) for a, b, _ in ut]
        self.assertIn((2626, 2630), spann, "linjeregeln slogs ihop med folion")
        self.assertTrue(any(a >= 2666 and b <= 2700 for a, b in spann),
                        "folion saknas: %s" % spann)
        self.assertIn((2707, 2738), spann, "vattenstämpeln slogs ihop")

    # -- D 5 -------------------------------------------------------------
    def test_skuggad_och_oskuggad_rad_mats_lika_brett(self):
        """Samma text i en tonad och en otonad tabellrad ska ge samma bredd.

        Rå svärta kan inte skilja tonplattan från satsen — rastret når lika
        höga toppvärden — så den skuggade raden mättes ut till cellens fulla
        bredd (0,408) medan den oskuggade mättes till bläckets (0,219-0,395).
        Samma tabell fick två bredder och `forbesikta`s
        kolumnsammanslagningsregel larmade på var och en av de skuggade
        raderna (s. 62). Tonens och satsens spridning är tryckets egna,
        uppmätta i Hunddjurstabellen: 19-25 mot 65-69.
        """
        rng = np.random.default_rng(20260803)
        hojd, bredd, text = 26, 220, slice(40, 180)

        def cell(ton, raster):
            block = np.full((hojd, bredd), float(ton))
            block += rng.normal(0, raster, block.shape)   # ytans eget raster
            block[:, text] = ton
            block[4:hojd - 4, text] += rng.normal(0, 67, (hojd - 8, 140))
            return np.clip(block, 0, 255)

        # Pappret har lågt raster, tonplattan högt — tryckets egna tal.
        oskuggad = _extent(cell(2, 3), 0, hojd, 0, bredd)
        skuggad = _extent(cell(90, 22), 0, hojd, 0, bredd)
        self.assertIsNotNone(skuggad)
        self.assertLess(abs(skuggad[0] - oskuggad[0]), 8,
                        "vänsterkant: %s mot %s" % (skuggad, oskuggad))
        self.assertLess(abs(skuggad[1] - oskuggad[1]), 8,
                        "högerkant: %s mot %s" % (skuggad, oskuggad))
        self.assertLess(skuggad[1] - skuggad[0], bredd * 0.9,
                        "den skuggade raden mättes ut till hela cellen")

    # -- D 6 -------------------------------------------------------------
    def test_liten_grad_tappar_ingen_rad(self):
        """Registersidornas sättning delar varje rad i två band.

        Medianbandhöjden blir då fragmentets (5 px) i stället för radens
        (26 px). `_segments` bröt sidan i ett avsnitt PER RAD, spaltprofilen
        mättes över skivor som var för korta för den lokala tröskeln, och sista
        raden i vardera spalten föll bort (s. 63).
        """
        page = blank()
        tops = [100 + i * 30 for i in range(12)]
        for top in tops:
            page[top:top + 3, 60:66] = 30        # versalfragment
            page[top + 6:top + 14, 60:280:3] = 30  # radens kropp
            page[top + 6:top + 14, 330:560:3] = 30
        rows, _ = measure_dark(darkness(page))
        for region in ("vänsterkolumn", "högerkolumn"):
            spalt = [r for r in rows if r["region"] == region]
            self.assertEqual(len(spalt), len(tops),
                             "%s: %d band mot %d tryckta rader"
                             % (region, len(spalt), len(tops)))

    def test_avsnitten_teglar_ihop_kroppen(self):
        """Ingen yta mellan två avsnitt får lämnas omätt.

        En rad som helsidesprofilen missar — blek, och bara i den ena spalten —
        hamnade annars i ett hål mellan två avsnitt och mättes aldrig av någon
        spalt (s. 2: sista posten i var och en av innehållsförteckningens tre
        spalter; s. 60: tre rader).
        """
        body = [(100, 120, KIND_ROW), (300, 320, KIND_ROW)]
        segments = _segments(body)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0][1], segments[1][0],
                         "avsnitten lämnar ett hål: %s" % (segments,))
        self.assertEqual((segments[0][0], segments[-1][1]), (100, 320))


if __name__ == "__main__":
    unittest.main()


class TestGutterVote(unittest.TestCase):
    """En helsidesbred illustration får inte dölja spaltrännan.

    Uppmätt på del II: tio sidor (8, 20, 32–36, 42, 64) hade en illustration
    tvärs över rännan. Avsnittets MEDELPROFIL fylldes då av bildens bläck,
    spalterna hittades inte, och vänster- och högerspaltens rader slogs ihop
    till fullbreddsband — hela sidan föll ut utan geometri, och läsexporten
    gav en rad per tryckt rad med avstavningarna kvar.

    Omröstningen bland radbanden löser det: brödtextrader har en lucka mitt på
    satsytan, bilden har det inte, och en majoritet räcker.
    """

    def _tvaspaltig(self, rader=12):
        """Två spalter med ränna mellan x=290 och x=310."""
        page = blank()
        for i in range(rader):
            top = 100 + i * PITCH
            write_line(page, top, 60, 285)
            write_line(page, top, 315, 540)
        return page

    def _regioner(self, page):
        rows, _ = measure_dark(darkness(page))
        reg = {}
        for r in rows:
            if r["region"] in ("sidhuvud", "sidfot"):
                continue
            reg[r["region"]] = reg.get(r["region"], 0) + 1
        return reg

    def test_ren_tvaspaltssida_delas_i_spalter(self):
        reg = self._regioner(self._tvaspaltig())
        self.assertEqual(reg.get("vänsterkolumn"), 12)
        self.assertEqual(reg.get("högerkolumn"), 12)

    def test_svart_illustration_over_rannan_doljer_inte_spalterna(self):
        """Del II s. 8: nattscen med svart bottenplatta, hög bläckandel."""
        page = self._tvaspaltig()
        page[430:700, 60:540] = 20          # solid svart block tvärs rännan
        reg = self._regioner(page)
        self.assertEqual(reg.get("vänsterkolumn"), 12)
        self.assertEqual(reg.get("högerkolumn"), 12)

    def test_streckteckning_over_rannan_doljer_inte_heller(self):
        """Del II s. 20: linjekonst med bläckandel som brödtext."""
        page = self._tvaspaltig()
        for y in range(430, 700, 6):
            write_line(page, y, 60, 540, ink=60)   # bläck rakt över rännan
        reg = self._regioner(page)
        self.assertEqual(reg.get("vänsterkolumn"), 12)
        self.assertEqual(reg.get("högerkolumn"), 12)

    def test_verkligt_enspaltig_sida_delas_inte(self):
        """Rösten får inte hitta på en ränna där ingen finns."""
        page = blank()
        for i in range(12):
            write_line(page, 100 + i * PITCH, 60, 540)
        reg = self._regioner(page)
        self.assertNotIn("vänsterkolumn", reg)
        self.assertNotIn("högerkolumn", reg)

    def test_marginalens_tomrum_rostar_inte_fram_en_ranna(self):
        """Bara stråk mitt på satsytan räknas — inte vänster/höger marginal."""
        page = blank()
        for i in range(12):
            write_line(page, 100 + i * PITCH, 20, 200)   # smal spalt till vänster
        reg = self._regioner(page)
        self.assertNotIn("högerkolumn", reg)


class TestRannanSomKorridor(unittest.TestCase):
    """BQ-013: rännans läge är den korridor som är tom i ALLA band.

    Medianen av bandens egna rännor lägger rännan fel så snart raderna är
    korta: varje bands tomma yta börjar direkt efter dess sista ord. På del III
    s. 13 (listan över magiskolor) hamnade rännan på x 0,332 i stället för
    0,49, och vänsterspaltens fönster klippte av sin egen text.
    """

    def _sida(self, hoger_marginal):
        """Två spalter; vänsterspaltens rader slutar där anropet säger."""
        dark = np.zeros((400, 1000), dtype=np.uint8)
        for i, slut in enumerate(hoger_marginal):
            top = 20 + i * 30
            dark[top:top + 14, 80:slut] = 255      # vänsterspalt
            dark[top:top + 14, 560:900] = 255      # högerspalt
        return dark

    def test_korta_rader_flyttar_inte_rannan(self):
        # Fyra rader vars vänsterspalt slutar på vitt skilda ställen. Bara den
        # längsta når fram till den riktiga rännan vid x 480.
        dark = self._sida([300, 480, 350, 470])
        bands = [(20 + i * 30, 34 + i * 30) for i in range(4)]
        blocks = _columns(dark, 0, 400, 1000, bands)
        self.assertEqual(len(blocks), 2)
        gutter_lo, gutter_hi = blocks[0][1], blocks[1][0]
        self.assertGreaterEqual(gutter_lo, 470,
                                "rännan lades vid en KORT rads slut")
        self.assertLessEqual(gutter_hi, 570)

    def test_fullbreda_rader_ger_samma_ranna(self):
        """Motprovet: med fyllda rader ska svaret vara oförändrat."""
        dark = self._sida([480, 480, 480, 480])
        bands = [(20 + i * 30, 34 + i * 30) for i in range(4)]
        blocks = _columns(dark, 0, 400, 1000, bands)
        self.assertEqual(len(blocks), 2)
        self.assertGreaterEqual(blocks[0][1], 470)


class TestSparseTrailingRow(unittest.TestCase):
    """Andra svepet: den korta, glesa slutraden (BQ-002 a).

    Uppmätt i del III: en slutrad på två–tre glyfer toppar på ungefär halva
    grannradernas profil, och den lokala tröskeln i `_profile_bands` ligger
    just där — `den.` på s. 39 mätte 40,0 mot tröskeln 41,6. Mönstret är
    belagt tjugosex gånger i den bokens beslutslista, och kostnaden syns i
    `bok.md`: utan bbox bryts stycket mitt i det avstavade ordet.
    """

    # Tät sättning och RASTRERAT papper — båda krävs för att återge felet.
    # Med pitch 24 och kritvitt papper ligger den lokala tröskeln nära noll och
    # första svepet hittar raden ändå; i en verklig skanning sätter
    # grannradernas sats den lokala toppen och rastret golvet.
    TIGHT_PITCH = 16

    def _sida(self, kort_bredd=20, tom=False):
        """Sex fulla rader, en KORT gles rad, och sedan tre fulla."""
        rng = np.random.default_rng(20260805)
        page = blank()
        tops = [100 + i * self.TIGHT_PITCH for i in range(10)]
        yta = (slice(90, tops[-1] + 3 * LINE_H), slice(50, 290))
        page[yta] = rng.integers(190, 256, size=page[yta].shape,
                                 dtype=np.uint16).astype(np.uint8)
        for i, top in enumerate(tops):
            if i == 6:
                if not tom:
                    write_line(page, top, 60, 60 + kort_bredd)
                continue
            write_line(page, top, 60, 280)
        return page, tops

    def test_kort_slutrad_far_ett_band(self):
        page, tops = self._sida()
        rows, _ = measure_dark(darkness(page))
        mitt = (HEIGHT - (tops[6] + LINE_H / 2)) / HEIGHT
        träff = [r for r in rows
                 if r["bbox"][1] <= mitt <= r["bbox"][1] + r["bbox"][3]]
        self.assertTrue(träff, "den glesa raden saknar band: %s" % rows)
        self.assertEqual(träff[0].get("svep"), 2,
                         "raden hittades av första svepet — testet mäter inte "
                         "det den påstår")

    def test_banden_ligger_kvar_i_lasordning(self):
        """Läsordningen är kontraktet nedströms — den glesa raden ska in på
        sin plats i spalten, inte sist."""
        page, tops = self._sida()
        rows, _ = measure_dark(darkness(page))
        body = [r for r in rows if r["region"] not in ("sidhuvud", "sidfot")]
        ys = [r["bbox"][1] for r in body]
        self.assertEqual(ys, sorted(ys, reverse=True))

    def test_tom_lucka_ger_inget_band(self):
        """Motprovet, och det som gör svepet användbart: utan tryckt rad i
        luckan får ingen box hittas på. En box som fattas är alltid tillåten;
        en påhittad är ett fel som ser ut som data (AGENTER.md Regel 9)."""
        page, tops = self._sida(tom=True)
        rows, _ = measure_dark(darkness(page))
        mitt = (HEIGHT - (tops[6] + LINE_H / 2)) / HEIGHT
        träff = [r for r in rows
                 if r["bbox"][1] <= mitt <= r["bbox"][1] + r["bbox"][3]]
        self.assertFalse(träff, "band hittades på i en TOM lucka: %s" % träff)

    def test_understycken_blir_inte_egna_rader(self):
        """En flisa under en normal rad är inte en rad. Utan höjdkravet gav
        svepet 63 sådana band på en enda sida (del III s. 13)."""
        page, tops = self._sida(tom=True)
        # Ett par pixelrader strax under rad 5 — understycken, inte sats.
        page[tops[5] + LINE_H + 1:tops[5] + LINE_H + 4, 60:120] = 40
        rows, _ = measure_dark(darkness(page))
        låga = [r for r in rows if r.get("svep") == 2
                and r["bbox"][3] < 0.6 * LINE_H / HEIGHT]
        self.assertFalse(låga, "svepet gjorde flisor till rader: %s" % låga)


class TestFrameRuleExtent(unittest.TestCase):
    """Ramlinjen är inte radens bläck (BQ-013).

    Del III s. 13 är inramad, och `_extent` mätte varje band från ramen: alla
    47 vänsterband fick x 0,0735 och styckeindragen — som är hela postens
    facit — försvann.
    """

    def _inramad(self, indrag=0):
        page = blank()
        page[80:700, 40:42] = 30                     # ramens vänstra linje
        tops = [100 + i * PITCH for i in range(8)]
        for i, top in enumerate(tops):
            lo = 90 + (indrag if i == 3 else 0)
            write_line(page, top, lo, 280)
        return page, tops

    def test_ramen_satter_inte_radens_x(self):
        page, _ = self._inramad()
        rows, _ = measure_dark(darkness(page))
        body = [r for r in rows if r["region"] not in ("sidhuvud", "sidfot")]
        self.assertTrue(body)
        for r in body:
            self.assertGreater(r["bbox"][0], 60 / WIDTH,
                               "bandet mättes från ramlinjen: %s" % r["bbox"])

    def test_styckeindraget_syns(self):
        page, _ = self._inramad(indrag=12)
        rows, _ = measure_dark(darkness(page))
        body = [r for r in rows if r["region"] not in ("sidhuvud", "sidfot")]
        xs = [r["bbox"][0] for r in body]
        self.assertAlmostEqual(max(xs) - min(xs), 12 / WIDTH, places=2)

    def test_skrafferad_illustration_ates_inte_av_masken(self):
        """Motprovet som fällde det förra ramförsöket: en skraffering är också
        smala lodräta streck, men dussintals — då maskas ingenting."""
        page, _ = page_with_lines(6)
        page[380:700, 60:280:4] = 30
        rows, _ = measure_dark(darkness(page))
        self.assertIn(KIND_GRAPHIC, [r["kind"] for r in rows])
