"""Bindning av element till uppmätta rader efter en ommätning.

Testerna fäster de egenskaper som gör att verktyget inte kan skriva en
gissning som data. Bakgrunden står i `scripts/binda_rader.py`: efter att
`pipeline/rows.py` lagats hade tio sidor i del II rätt radmätning men inga
element som pekade på den, och utan `source.rader` räknar pipelinen aldrig
fram någon bbox — läsexporten bryter då varje TRYCKT rad till ett eget stycke.
"""
import unittest

from scripts.binda_rader import (SVARTA_GRAFIK, _betrodda, _djuplangd,
                                 _domare, _flerradig_regim, _hoppstraff,
                                 _indragna, _kor, _radkostnad, _radregioner,
                                 _raggedstraff, _rubrikband,
                                 _skala_ur_bevarande, _tvaspaltsdelar,
                                 binda_sida)

SKALA = 120.0
TAKT = 0.015


def rad(y, bredd, region="vänsterkolumn", höjd=0.008, x=0.06):
    return {"region": region, "bbox": [x, y, bredd, höjd]}


def spalt(bredder, region="vänsterkolumn", y0=0.90, höjd=0.008):
    """Rader i satsens radtakt, uppifrån och ned (y räknas från nederkanten)."""
    return [rad(y0 - i * TAKT, b, region, höjd) for i, b in enumerate(bredder)]


def stycke(texter, region="vänsterkolumn"):
    return [{"type": "paragraph", "text": t, "confidence": 0.95,
             "source": {"region": region}} for t in texter]


def text(tecken):
    """En rad vars teckenlängd stämmer med bredden `bredd` vid SKALA."""
    return "x" * tecken


class TestDjuplangd(unittest.TestCase):
    """Behållarnas text bor i `data`, och den måste räknas.

    Ett statblock vars längd räknades till noll blev gratis att sträcka över
    hur många band som helst — på del II s. 30 svalde ett sådant 40 rader i
    stället för 14.
    """

    def test_statblock_har_langd(self):
        el = {"type": "statblock",
              "data": {"name": "Skogsvätte", "stats": {"STY": 10, "STO": 4},
                       "weapons": [{"name": "Bett", "damage": "1T6"}]}}
        self.assertGreater(_djuplangd(el["data"]), 20)

    def test_lista_och_tabell_raknas(self):
        self.assertEqual(_djuplangd({"items": ["abc", "de"]}), 5 + len("items"))
        self.assertGreater(_djuplangd({"headers": ["A"], "rows": [["bb"]]}), 3)


class TestBandklassning(unittest.TestCase):
    """Vilka band som är text och vilka som är illustration."""

    def test_band_i_takt_ar_text(self):
        rader = spalt([0.42] * 6)
        self.assertTrue(all(h == max(_hoppstraff(rader)) for h in _hoppstraff(rader)))

    def test_svart_band_raknas_som_grafik(self):
        rader = spalt([0.42] * 6)
        svarta = [0.25] * 6
        svarta[3] = SVARTA_GRAFIK + 0.1
        straff = _hoppstraff(rader, svarta)
        self.assertLess(straff[3], straff[0],
                        "ett svart band ska vara billigt att hoppa över")

    def test_band_utanfor_radtakten_raknas_som_grafik(self):
        rader = spalt([0.42] * 4)
        # ett band långt under spalten, i egen takt och egen höjd
        rader.append(rad(0.40, 0.42, höjd=0.030))
        straff = _hoppstraff(rader)
        self.assertLess(straff[-1], straff[0])


class TestKorningar(unittest.TestCase):
    def test_delas_vid_radglapp(self):
        lösn = [(0, [0], 1.0), (1, [1], 1.0), (2, [4], 1.0), (3, [5], 1.0)]
        self.assertEqual([[p[0] for p in k] for k in _kor(lösn)],
                         [[0, 1], [2, 3]])


class TestBindning(unittest.TestCase):
    def test_entydig_spalt_binds(self):
        """Sista raden är kort — då kan körningen inte skjutas ett steg."""
        rader = spalt([0.42, 0.42, 0.42, 0.42, 0.15])
        els = stycke([text(50), text(50), text(50), text(50), text(18)])
        bind, _ = binda_sida(els, rader, SKALA)
        self.assertEqual(bind, {0: [0], 1: [1], 2: [2], 3: [3], 4: [4]})

    def test_element_over_illustration_binds_inte(self):
        """Bandet under spalten har rätt bredd men fel takt och fel höjd."""
        rader = spalt([0.42, 0.42, 0.15]) + [rad(0.40, 0.42, höjd=0.030)]
        els = stycke([text(50), text(50), text(18)])
        bind, _ = binda_sida(els, rader, SKALA)
        self.assertNotIn(3, bind.values())
        self.assertEqual(bind.get(2), [2])

    def test_likbred_korning_utan_ankare_lamnas_obunden(self):
        """Alla rader lika breda och en rad över: läget är inte uppmätt.

        Det här är felet som fällde indexsidan (del II s. 63): punktledarna
        gör varje rad lika bred, mätningen har färre band än poster, och
        varje tänkbar förskjutning kostar exakt lika mycket.
        """
        rader = spalt([0.42] * 5)
        els = stycke([text(50)] * 4)
        bind, anm = binda_sida(els, rader, SKALA)
        self.assertEqual(bind, {})
        self.assertTrue(anm)

    def test_element_binds_aldrig_utanfor_sin_region(self):
        rader = spalt([0.42, 0.15]) + spalt([0.42, 0.15], "högerkolumn",
                                            y0=0.90)
        els = stycke([text(50), text(18)], "sidfot")
        bind, anm = binda_sida(els, rader, SKALA)
        self.assertEqual(bind, {})
        self.assertTrue(any("sidfot" in a for a in anm))

    def test_saknad_matrad_skjuter_inte_resten_ur_led(self):
        """Ett element utan band får stå obundet i stället för att flytta alla.

        Kravet att varje element MÅSTE få en rad var det värsta felet i
        första versionen: på del II s. 37 saknade `perfekta.` band, och 63 av
        80 element hamnade ett steg fel.
        """
        # Bredderna är olika, så tilldelningen är tvingad: mätningen saknar
        # band för elementet på 25 tecken.
        rader = spalt([0.42, 0.30, 0.12])
        els = stycke([text(50), text(36), text(25), text(14)])
        bind, _ = binda_sida(els, rader, SKALA)
        self.assertEqual(bind.get(0), [0])
        self.assertEqual(bind.get(1), [1])
        self.assertEqual(bind.get(3), [2], "sista elementet ligger kvar sist")
        self.assertNotIn(2, bind, "elementet utan band ska stå obundet")


class TestDomare(unittest.TestCase):
    """Avvikelser mot facit ska DÖMAS mot trycket, inte summeras.

    Facit är en tidigare transkription med egna fel — i del II binder den
    sidhuvudet till rad 60 mitt på s. 6. Räknas sådant som verktygets fel
    förkastas ett verktyg som är bättre än det jämförs med (AGENTER.md
    Regel 9a).
    """

    def setUp(self):
        self.rader = spalt([0.42, 0.12])

    def test_verktyget_vinner_nar_bredden_talar_for_det(self):
        el = stycke([text(50)])[0]
        self.assertEqual(
            _domare(el, self.rader, [1], [0], SKALA, None), "mitt")

    def test_facit_vinner_nar_bredden_talar_for_facit(self):
        el = stycke([text(50)])[0]
        self.assertEqual(
            _domare(el, self.rader, [0], [1], SKALA, None), "facit")

    def test_likbredda_rader_gar_inte_att_skilja_at(self):
        rader = spalt([0.42, 0.42])
        el = stycke([text(50)])[0]
        self.assertIsNone(_domare(el, rader, [0], [1], SKALA, None))


class TestIdempotens(unittest.TestCase):
    def test_samma_indata_ger_samma_bindning(self):
        rader = spalt([0.42, 0.42, 0.15])
        els = stycke([text(50), text(50), text(18)])
        först, _ = binda_sida(els, rader, SKALA)
        igen, _ = binda_sida(els, rader, SKALA)
        self.assertEqual(först, igen)


if __name__ == "__main__":
    unittest.main()


class TestStyckeformadRegim(unittest.TestCase):
    """De 29 äventyrsböckerna är transkriberade STYCKE för stycke.

    Medianparagrafen är 103–525 tecken mot en tryckt rad på ungefär 50–60,
    alltså två till tio rader per element. Med kravet att ett element täcker
    exakt en rad gick ingen tilldelning alls att räkna fram, och böckerna
    lämnades helt obundna.
    """

    def test_regimen_mats_inte_gissas(self):
        rows = spalt([0.42] * 20)
        radformad = stycke([text(50) for _ in range(20)])
        styckeformad = stycke([text(250) for _ in range(12)])
        self.assertFalse(_flerradig_regim([(radformad, rows, {})], SKALA))
        self.assertTrue(_flerradig_regim([(styckeformad, rows, {})], SKALA))

    def test_for_fa_prov_ger_radformad_regim(self):
        """Hellre den spärrade regimen än ett hopp i mörkret på fyra stycken.

        Spärren biter aldrig i praktiken — de 29 böckerna har 20–239 paragrafer
        var — men den ska finnas: styckeregimen släpper en säkerhetsspärr, och
        den får inte slås av på ett tunt underlag.
        """
        rows = spalt([0.42] * 20)
        self.assertFalse(
            _flerradig_regim([(stycke([text(250) for _ in range(4)]),
                               rows, {})], SKALA))

    def test_flerradigt_stycke_binds_i_styckeregimen(self):
        rows = spalt([0.42, 0.42, 0.42, 0.20])
        els = stycke([text(int(SKALA * (0.42 * 3 + 0.20)))])
        bind, _ = binda_sida(els, rows, SKALA, flerradiga=True)
        self.assertEqual(bind.get(0), [0, 1, 2, 3])

    def test_samma_stycke_binds_inte_i_radregimen(self):
        """Motprovet: spärren står kvar där transkriptet är radformat."""
        rows = spalt([0.42, 0.42, 0.42, 0.20])
        els = stycke([text(int(SKALA * (0.42 * 3 + 0.20)))])
        bind, _ = binda_sida(els, rows, SKALA, flerradiga=False)
        self.assertEqual(bind, {})


class TestRaggedGrans(unittest.TestCase):
    """Ett stycke slutar på en KORT rad — det är den raka sättningens signal.

    Utan måttet var styckeregimens gränser fria att flytta: ett femradigt
    stycke som skjuts ett steg tappar en kort rad i ena änden och vinner en i
    den andra, och totalbredden ändras mindre än brödtextens tolerans.
    """

    FULL = 0.42

    def test_full_sista_rad_straffas(self):
        rows = spalt([self.FULL] * 4)
        el = stycke([text(100)])[0]
        self.assertGreater(_raggedstraff(el, rows, 0, 3, True, self.FULL), 0)

    def test_kort_sista_rad_ar_gratis(self):
        rows = spalt([self.FULL, self.FULL, 0.20])
        el = stycke([text(100)])[0]
        self.assertEqual(_raggedstraff(el, rows, 0, 3, True, self.FULL), 0.0)

    def test_kort_rad_INNE_i_stycket_straffas(self):
        """Där slutade i själva verket ett stycke."""
        rows = spalt([self.FULL, 0.20, self.FULL, 0.20])
        el = stycke([text(100)])[0]
        self.assertGreater(_raggedstraff(el, rows, 0, 4, True, self.FULL), 0)

    def test_rubriker_bar_inte_signalen(self):
        """En rubrik är kort av andra skäl än att stycket tog slut."""
        rows = spalt([self.FULL] * 3)
        rubrik = {"type": "heading", "text": "X", "source": {}}
        self.assertEqual(_raggedstraff(rubrik, rows, 0, 3, True, self.FULL),
                         0.0)

    def test_matet_ar_avstangt_i_radregimen(self):
        rows = spalt([self.FULL] * 4)
        el = stycke([text(100)])[0]
        self.assertEqual(_raggedstraff(el, rows, 0, 3, False, self.FULL), 0.0)


class TestIndrag(unittest.TestCase):
    """Styckeindraget är styckegränsens signal från vänster.

    Uppmätt i båda de styckeformade facitböckerna: Lovligt byte 0,0195
    (beslut.md s. 5), Tanegashima s. 4 banden 113/117/123 = exakt de tre
    styckestarterna. Kolumnklippta band (vänsterkant 0,13–0,17 höger om
    bläcket) är INTE indrag och ligger utanför fönstret.
    """

    def test_indragen_rad_flaggas_och_klippt_rad_inte(self):
        rader = spalt([0.42] * 6)
        rader[2]["bbox"][0] = 0.08    # äkta indrag, +0,02
        rader[4]["bbox"][0] = 0.20    # kolumnklippt band, +0,14
        self.assertEqual(_indragna(rader),
                         [False, False, True, False, False, False])

    def test_slukad_styckestart_kostar(self):
        """Ett indraget band INUTI spannet är en slukad styckegräns."""
        rader = spalt([0.42, 0.42, 0.42, 0.15])
        rader[2]["bbox"][0] = 0.08
        el = stycke([text(150)])[0]
        ind = _indragna(rader)
        med = _radkostnad(el, rader, 0, 4, SKALA, None, True, 0.42, ind)
        utan = _radkostnad(el, rader, 0, 4, SKALA, None, True, 0.42, None)
        self.assertGreater(med, utan)

    def test_indragen_forsta_rad_ar_gratis(self):
        """Spannets FÖRSTA rad får vara indragen — det är styckestarten.
        Texten börjar med versal: ett nytt stycke, ingen fortsättning."""
        rader = spalt([0.40, 0.42, 0.15])
        rader[0]["bbox"][0] = 0.08
        el = {"type": "paragraph", "text": "X" * 115,
              "source": {"region": "vänsterkolumn"}}
        ind = _indragna(rader)
        med = _radkostnad(el, rader, 0, 3, SKALA, None, True, 0.42, ind)
        utan = _radkostnad(el, rader, 0, 3, SKALA, None, True, 0.42, None)
        self.assertEqual(med, utan)

    def test_fortsattning_med_gemen_borjar_inte_pa_indrag(self):
        """`de tagit över...` är en fortsättning mitt i en mening — den kan
        inte börja på ett indraget band (Lovligt byte p005_e03)."""
        rader = spalt([0.40, 0.42, 0.15])
        rader[0]["bbox"][0] = 0.08
        el = {"type": "paragraph", "text": "de tagit " + text(106),
              "source": {"region": "vänsterkolumn"}}
        ind = _indragna(rader)
        med = _radkostnad(el, rader, 0, 3, SKALA, None, True, 0.42, ind)
        utan = _radkostnad(el, rader, 0, 3, SKALA, None, True, 0.42, None)
        self.assertGreater(med, utan)


class TestRaggedMedIndrag(unittest.TestCase):
    """Indraget samspelar med raggedstraffet på två uppmätta sätt."""

    FULL = 0.42

    def test_full_sista_rad_frias_av_indrag_efter_spannet(self):
        """Tanegashima s. 4, p004_e19: slutraden 112 mäter 0,96 av full-
        bredden men band 113 är indraget — stycket slutar bevisligen där."""
        rader = spalt([self.FULL] * 4)
        rader[3]["bbox"][0] = 0.08    # raden EFTER spannet är indragen
        ind = _indragna(rader)
        el = stycke([text(100)])[0]
        self.assertEqual(
            _raggedstraff(el, rader, 0, 3, True, self.FULL, None, ind), 0.0)

    def test_indragen_forsta_rad_doms_inte_som_kort(self):
        """p006_e21: startbandet 25 mätte 0,2607 mot gränsen 0,2616 —
        indraget äter en bit av bredden, och det är ingen styckegräns."""
        rader = spalt([0.40, self.FULL, 0.15])
        rader[0]["bbox"][0] = 0.08
        ind = _indragna(rader)
        el = stycke([text(100)])[0]
        self.assertEqual(
            _raggedstraff(el, rader, 0, 3, True, self.FULL, None, ind), 0.0)


class TestRubrikband(unittest.TestCase):
    """Ett band i rubrikhöjd hör aldrig hemma i ett brödtextspann.

    Advokatens tredje diskriminant (beslut.md Lovligt byte s. 5): rubrikband
    0,0079–0,0082 mot brödtext 0,0039–0,0071. Det var så p005_e12:s
    sväljning av rubrikstumpen »2. SIDODÖRR« (band 78) fälldes.
    """

    def test_rubrikhojt_band_flaggas(self):
        rader = spalt([0.42] * 5)
        rader[2]["bbox"][3] = 0.012   # 1,5 x medianhöjden
        self.assertEqual(_rubrikband(rader),
                         [False, False, True, False, False])

    def test_brodtext_over_rubrikband_kostar(self):
        rader = spalt([0.42, 0.42, 0.42, 0.15])
        rader[1]["bbox"][3] = 0.012
        rub = _rubrikband(rader)
        el = stycke([text(150)])[0]
        med = _radkostnad(el, rader, 0, 4, SKALA, None, True, 0.42, None,
                          None, None, None, rub)
        utan = _radkostnad(el, rader, 0, 4, SKALA, None, True, 0.42, None,
                           None, None, None, None)
        self.assertGreater(med, utan)

    def test_rubriken_sjalv_gar_fri(self):
        rader = spalt([0.12] * 3)
        rader[1]["bbox"][3] = 0.012
        rub = _rubrikband(rader)
        rubrik = {"type": "heading", "text": text(9), "source": {}}
        self.assertEqual(
            _radkostnad(rubrik, rader, 1, 2, SKALA, None, True, 0.42, None,
                        None, None, None, rub),
            _radkostnad(rubrik, rader, 1, 2, SKALA, None, True, 0.42))


class TestBetrodda(unittest.TestCase):
    """Ett kolumnklippt band mäter skivan, inte bläcket — bara y, höjd och
    den oklippta kanten bär information (beslut.md Lovligt byte s. 5)."""

    def test_klippt_vansterkant_underkanns(self):
        rader = spalt([0.42] * 5)
        rader[2]["bbox"][0] = 0.20    # 0,14 höger om kanten
        self.assertEqual(_betrodda(rader),
                         [True, True, False, True, True])

    def test_overbred_hogerkant_underkanns(self):
        """Band 105–107 på Lovligt s. 5: högerkant 0,999 mot spaltens 0,958."""
        rader = spalt([0.42] * 8)
        rader[2]["bbox"][2] = 0.60
        self.assertEqual(_betrodda(rader),
                         [True, True, False, True, True, True, True, True])

    def test_bindning_utan_betrott_band_skrivs_aldrig(self):
        """Unionen av enbart klippta band omsluter inte elementets bläck —
        en sådan box är ett fel som ser ut som data (p005_e11@78)."""
        rader = spalt([0.42, 0.42, 0.15], y0=0.90)
        extra = rad(0.90 - 3 * TAKT, 0.05, x=0.30)   # klippt stump
        rader.append(extra)
        els = stycke([text(50), text(50), text(18), text(8)])
        bind, anm = binda_sida(els, rader, SKALA, flerradiga=True)
        self.assertNotIn(3, bind)


class TestOrdningshallare(unittest.TestCase):
    """Ett tvåspaltselement håller sin plats i läsordningen men binds aldrig
    — unionen av två spalters band vore innehållslös (p006_e18)."""

    def test_tvaspaltsdelar(self):
        kol = ["vänsterkolumn", "mittkolumn", "högerkolumn"]
        self.assertEqual(_tvaspaltsdelar("vänster-/mittkolumn", kol),
                         ["vänsterkolumn", "mittkolumn"])
        self.assertEqual(_tvaspaltsdelar("mittkolumn/högerkolumn", kol),
                         ["mittkolumn", "högerkolumn"])
        self.assertEqual(_tvaspaltsdelar("högerkolumn, spelartext", kol), [])

    def test_hallaren_binds_aldrig(self):
        rader = spalt([0.42] * 6, "vänsterkolumn")
        els = stycke([text(50), text(50), text(18)])
        els.append({"type": "paragraph", "text": text(300),
                    "confidence": 0.9,
                    "source": {"region": "vänster-/mittkolumn"}})
        mat = {"columns": [
            {"region": "vänsterkolumn", "x": 0.05, "bredd": 0.42,
             "y": 0.9, "höjd": 0.1},
            {"region": "mittkolumn", "x": 0.50, "bredd": 0.2,
             "y": 0.9, "höjd": 0.1},
            {"region": "högerkolumn", "x": 0.72, "bredd": 0.2,
             "y": 0.9, "höjd": 0.1}]}
        bind, _ = binda_sida(els, rader, SKALA, flerradiga=True, radboxar=mat)
        self.assertNotIn(3, bind, "ordningshållaren får aldrig en skriven "
                                  "bindning")


class TestUteslutna(unittest.TestCase):
    """Tömda element och illustrationer deltar aldrig i bindningen."""

    def test_removed_binds_aldrig(self):
        rader = spalt([0.42, 0.15])
        els = stycke([text(50), text(18)])
        els[0]["removed"] = True
        bind, _ = binda_sida(els, rader, SKALA)
        self.assertNotIn(0, bind)

    def test_illustration_binds_aldrig(self):
        rader = spalt([0.42, 0.15])
        els = stycke([text(50), text(18)])
        els[0]["type"] = "illustration"
        bind, _ = binda_sida(els, rader, SKALA)
        self.assertNotIn(0, bind)


class TestRadregioner(unittest.TestCase):
    """Mätningen är inte enig med sig själv: `kolumn 3` i en y-skiva är
    samma spalt som `högerkolumn` i nästa (Lovligt byte s. 5, band 78–79)."""

    def test_ordinal_oversatts_mot_spaltnamnen(self):
        rader = [rad(0.9, 0.4, "vänsterkolumn"),
                 rad(0.8, 0.4, "kolumn 1"),
                 rad(0.7, 0.4, "kolumn 3"),
                 rad(0.6, 0.4, "sidfot")]
        kol = ["vänsterkolumn", "mittkolumn", "högerkolumn"]
        self.assertEqual(_radregioner(rader, kol),
                         ["vänsterkolumn", "vänsterkolumn",
                          "högerkolumn", "sidfot"])


class TestDomskillnad(unittest.TestCase):
    """En dom kräver en mätbar skillnad — 0,003 i kostnad är brus, och
    domen fälls i bokens regim (flerradiga spann var förr alltid oavgjorda)."""

    def test_flerradigt_spann_kan_domas(self):
        rader = spalt([0.42, 0.20])
        el = stycke([text(74)])[0]
        self.assertEqual(
            _domare(el, rader, [0, 1], [0], SKALA, None, True, 0.42),
            "facit")

    def test_brusskillnad_ar_oavgjord(self):
        rader = spalt([0.42, 0.421])
        el = stycke([text(50)])[0]
        self.assertIsNone(_domare(el, rader, [0], [1], SKALA, None))


class TestSkalaUtanBundnaRader(unittest.TestCase):
    """Skalan måste gå att mäta i en bok som aldrig burit `source.rader`."""

    def test_bevarandeidentiteten_ger_skalan(self):
        rows = spalt([0.42] * 10)
        for r in rows:
            r["region"] = "vänsterkolumn"
        els = stycke([text(int(0.42 * SKALA * 2)) for _ in range(5)])
        ur = _skala_ur_bevarande([(els, rows, {})])
        self.assertIsNotNone(ur)
        self.assertAlmostEqual(ur, SKALA, delta=SKALA * 0.05)

    def test_for_fa_element_ger_ingen_skala(self):
        """Hellre ingen skala än en mätt på ett enda stycke."""
        rows = spalt([0.42] * 10)
        self.assertIsNone(_skala_ur_bevarande([(stycke([text(50)]), rows, {})]))
