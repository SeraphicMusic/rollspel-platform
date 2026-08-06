"""Avbildningen av transkriptens fria regionnamn på mätningens vokabulär.

Poängen med modulen är inte att översätta så många namn som möjligt, utan att
vägra översätta de tvetydiga. Testerna nedan speglar den prioriteringen: lika
många prov på vad den LÄMNAR som på vad den avbildar.
"""
import unittest

from pipeline.regions import column_count, measured_columns, normalize

TRE = ["vänsterkolumn", "mittkolumn", "högerkolumn"]
TVA = ["vänsterkolumn", "högerkolumn"]


class TestSpaltantalUrTranskriptet(unittest.TestCase):
    def test_vanster_och_hoger_ar_tva(self):
        self.assertEqual(column_count(["vänsterkolumn", "högerkolumn"]), 2)

    def test_namngiven_mitt_ar_tre(self):
        self.assertEqual(
            column_count(["vänsterkolumn", "mittkolumn", "högerkolumn"]), 3)

    def test_kolumn_2_utan_kolumn_3_ar_tva(self):
        """I en tvåspaltig bok ÄR `kolumn 2` högerspalten."""
        self.assertEqual(column_count(["kolumn 1", "kolumn 2"]), 2)

    def test_kolumn_3_ar_tre(self):
        self.assertEqual(column_count(["kolumn 1", "kolumn 2", "kolumn 3"]), 3)

    def test_kolumn_4_ar_fyra(self):
        self.assertEqual(
            column_count(["kolumn 1", "kolumn 3", "kolumn 4"]), 4)

    def test_spaltvokabularet_raknas_ocksa(self):
        self.assertEqual(
            column_count(["vänsterspalt", "mittspalt", "högerspalt"]), 3)

    def test_bara_mobler_ger_inget_spaltantal(self):
        self.assertIsNone(column_count(["sidhuvud", "sidfot", "huvudtext"]))

    def test_tomt_ger_none(self):
        self.assertIsNone(column_count([]))
        self.assertIsNone(column_count([None, ""]))


class TestMattaSpalter(unittest.TestCase):
    def _kol(self, *poster):
        return {"columns": [{"region": r, "x": x, "y": y, "höjd": h}
                            for r, x, y, h in poster]}

    def test_x_ordning(self):
        mat = self._kol(("högerkolumn", 0.7, 0.1, 0.8),
                        ("vänsterkolumn", 0.0, 0.1, 0.8),
                        ("mittkolumn", 0.35, 0.1, 0.8))
        self.assertEqual(measured_columns(mat), TRE)

    def test_bredaste_avsnittet_vinner(self):
        """En sida kan vara tvåspaltig upptill och trespaltig nedtill."""
        mat = self._kol(("vänsterkolumn", 0.0, 0.6, 0.3),
                        ("högerkolumn", 0.5, 0.6, 0.3),
                        ("vänsterkolumn", 0.0, 0.1, 0.4),
                        ("mittkolumn", 0.35, 0.1, 0.4),
                        ("högerkolumn", 0.7, 0.1, 0.4))
        self.assertEqual(measured_columns(mat), TRE)

    def test_mobler_och_sidbredd_raknas_inte_som_spalter(self):
        mat = self._kol(("sidbredd", 0.0, 0.1, 0.8),
                        ("sidhuvud", 0.0, 0.9, 0.1))
        self.assertEqual(measured_columns(mat), [])

    def test_utan_spaltinfo(self):
        self.assertEqual(measured_columns({}), [])


class TestNormalisering(unittest.TestCase):
    def test_ordningstal_mot_tre_spalter(self):
        self.assertEqual(normalize("kolumn 1", TRE), "vänsterkolumn")
        self.assertEqual(normalize("kolumn 2", TRE), "mittkolumn")
        self.assertEqual(normalize("kolumn 3", TRE), "högerkolumn")

    def test_ordningstal_mot_tva_spalter(self):
        self.assertEqual(normalize("kolumn 1", TVA), "vänsterkolumn")
        self.assertEqual(normalize("kolumn 2", TVA), "högerkolumn")

    def test_synonymer(self):
        self.assertEqual(normalize("vänsterspalt", TRE), "vänsterkolumn")
        self.assertEqual(normalize("mittenkolumn", TRE), "mittkolumn")
        self.assertEqual(normalize("högerspalt", TRE), "högerkolumn")

    def test_hoger_ar_den_sista_spalten_inte_den_andra(self):
        self.assertEqual(normalize("högerkolumn", TRE), "högerkolumn")
        self.assertEqual(normalize("högerkolumn", TVA), "högerkolumn")

    def test_kvalificerare_stor_inte(self):
        self.assertEqual(
            normalize("vänsterkolumn (dubblett av sida 18)", TRE),
            "vänsterkolumn")
        self.assertEqual(normalize("vänsterkolumn, spelartext", TRE),
                         "vänsterkolumn")

    def test_mobler(self):
        self.assertEqual(normalize("sidfot", TRE), "sidfot")
        self.assertEqual(normalize("sidfot, sidnummer", TRE), "sidfot")
        self.assertEqual(normalize("sidfot höger", TRE), "sidfot")
        self.assertEqual(normalize("sidhuvud, dekorativ bård", TRE), "sidhuvud")

    def test_mobeln_gar_fore_vaderstrecket(self):
        """`sidfot höger` är sidfot, inte högerspalten."""
        self.assertEqual(normalize("sidfot vänster", TVA), "sidfot")

    def test_helbredd(self):
        self.assertEqual(normalize("huvudtext", TRE), "sidbredd")
        self.assertEqual(normalize("introduktion, helbredd", TRE), "sidbredd")

    # -- det den ska VÄGRA översätta ---------------------------------------

    def test_spann_over_tva_spalter_avbildas_inte(self):
        for namn in ("mittkolumn–högerkolumn", "vänster/mittkolumn",
                     "mittkolumn+högerkolumn", "vänsterkolumn—mittkolumn",
                     "vänsterkolumn nederst, fortsätter i mittkolumn",
                     "mittenkolumn fortsätter i högerkolumn",
                     "vänsterkolumn till mittenkolumn"):
            self.assertIsNone(normalize(namn, TRE), namn)

    def test_bindestreck_i_sammansattning_ar_inget_spann(self):
        """`äventyrsförslag-ruta` får inte kastas som ett spaltspann."""
        self.assertEqual(normalize("äventyrsförslag-ruta (vänster)", TRE),
                         "vänsterkolumn")

    def test_fortsattning_over_SIDGRANS_ar_inget_spaltspann(self):
        """Det är antalet utpekade SPALTER som avgör, inte ordet »fortsätt«.

        `vänsterkolumn, fortsättning från föregående sida` pekar ut en enda
        spalt — elementet fortsätter över en SIDGRÄNS, inte över en spaltgräns.
        En regel som gick på skiljetecken och ord kastade bort dem, och det är
        vanliga namn: piloten har dem på tre av fem sidor.
        """
        self.assertEqual(
            normalize("vänsterkolumn, fortsättning från föregående sida", TRE),
            "vänsterkolumn")
        self.assertEqual(
            normalize("högerkolumn, fortsätter på nästa sida", TRE),
            "högerkolumn")
        self.assertEqual(normalize("kolumn 1, forts. från sidan 5", TRE),
                         "vänsterkolumn")

    def test_mitt_ar_tvetydigt_pa_en_tvaspaltig_sida(self):
        self.assertIsNone(normalize("mittkolumn", TVA))

    def test_oense_om_spaltantalet_ger_ingen_avbildning(self):
        """Trycket säger tre, mätningen hittade två — då är två hopslagna."""
        self.assertIsNone(normalize("vänsterkolumn", TVA, transcript_columns=3))
        self.assertIsNone(normalize("högerkolumn", TVA, transcript_columns=3))

    def test_ense_om_spaltantalet_avbildas(self):
        self.assertEqual(
            normalize("kolumn 3", TRE, transcript_columns=3), "högerkolumn")

    def test_ordningstal_utanfor_matningen(self):
        self.assertIsNone(normalize("kolumn 4", TRE))

    def test_okant_namn(self):
        self.assertIsNone(normalize("faktaruta", TRE))
        self.assertIsNone(normalize("kolofon", TRE))
        self.assertIsNone(normalize("byline", TRE))

    def test_utan_uppmatta_spalter(self):
        self.assertIsNone(normalize("vänsterkolumn", []))

    def test_tomt(self):
        self.assertIsNone(normalize(None, TRE))
        self.assertIsNone(normalize("", TRE))
