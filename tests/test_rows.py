"""Tester för den deterministiska uppmätningen av radboxar (pipeline/rows.py).

Bilderna byggs syntetiskt så att facit är känt exakt. De två fällor som
faktiskt sänkte de första versionerna mot riktiga skanningar har egna tester:
rastrerat papper (per-pixel-tröskling går sönder) och gråtonade tabellrader
(medelsvärta går sönder).
"""
import unittest

import numpy as np

from pipeline.rows import (KIND_GRAPHIC, KIND_ROW, darkness, measure_dark,
                           summarise)

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

    def test_summering_ar_tyst_pa_en_vanlig_textsida(self):
        rader = [{"region": "vänsterkolumn", "kind": KIND_ROW}] * 20
        summering = summarise(rader)
        self.assertFalse(summering["dominerande_grafik"])
        self.assertEqual(summering["rader"], 20)

    def test_tom_sida_ger_inga_rader(self):
        rows, columns = measure_dark(darkness(blank()))
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
