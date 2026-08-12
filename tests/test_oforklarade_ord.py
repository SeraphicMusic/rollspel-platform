"""Attribuerar `diffa`s ordändringar till de poster som tar ansvar för dem.

Grinden är inte "noll ordförändringar" — formen får ändras och rättningar SKA
ändra ord. Grinden är noll *oförklarade* ordförändringar, och skillnaden
avgjordes hittills genom att en människa läste diffens ordlista mot
sidfilernas korrektionsposter. Testerna nedan håller den jämförelsen ärlig i
de tre fall där den lätt blir falskt grön: skiljetecken som sitter fast i
diffens token, en post som inte är applicerad, och `validated.json` som ligger
kvar bredvid sin `final.json` och skulle dubbelräkna varje post.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.oforklarade_ord import granska


class Bokbadd(unittest.TestCase):
    def setUp(self):
        self.wd = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.wd, ignore_errors=True)
        (self.wd / "pages").mkdir()
        (self.wd / "export").mkdir()

    def bok(self, frysning, nu):
        (self.wd / "export" / "bok.frysning.md").write_text(frysning,
                                                            encoding="utf-8")
        (self.wd / "export" / "bok.md").write_text(nu, encoding="utf-8")

    def sida(self, elements, namn="page_001.final.json"):
        (self.wd / "pages" / namn).write_text(
            json.dumps({"page": 1, "elements": elements}), encoding="utf-8")

    @staticmethod
    def post(original, corrected, applied=True, kind="ocr"):
        return {"original": original, "corrected": corrected,
                "applied": applied, "confidence": 0.9, "reason": "…",
                "kind": kind, "source": "agent:djavulens-advokat"}

    def kvar(self):
        r = granska(self.wd)
        return (sum(r["oforklarat_borta"].values())
                + sum(r["oforklarat_nya"].values()))


class TestAttribuering(Bokbadd):
    def test_applicerad_post_forklarar_sin_egen_andring(self):
        self.bok("han spårar upp dem", "han spöar upp dem")
        self.sida([{"id": "e1", "corrections": [self.post("spårar", "spöar")]}])
        self.assertEqual(self.kvar(), 0)

    def test_andring_utan_post_star_kvar_som_oforklarad(self):
        """Felklassen frysningen finns för: text som försvinner utan avsändare.

        Sju tabellrader föll ur del I:s `bok.md` och såg i diffen ut precis som
        en avsedd rättning — ända tills man frågade vilken post som bar den.
        """
        self.bok("han spårar upp dem", "han spöar upp dem")
        self.sida([{"id": "e1", "corrections": []}])
        r = granska(self.wd)
        self.assertEqual(dict(r["oforklarat_borta"]), {"spårar": 1})
        self.assertEqual(dict(r["oforklarat_nya"]), {"spöar": 1})

    def test_avvisad_post_forklarar_ingenting(self):
        """`applied: false` betyder att posten uttryckligen INTE ändrade texten.
        Att låta den kvitta en ändring vore att låta ett avslag verkställa sig.
        """
        self.bok("han spårar upp dem", "han spöar upp dem")
        self.sida([{"id": "e1",
                    "corrections": [self.post("spårar", "spöar",
                                              applied=False)]}])
        self.assertEqual(self.kvar(), 2)

    def test_skiljetecken_i_token_hindrar_inte_attribueringen(self):
        """`diffa` tokeniserar `totalsförsvaret.` med punkten kvar, medan
        posten bär ordet utan. Samma ord — och en attribuering som missar det
        rapporterar en äkta rättning som oförklarad, vilket lär användaren att
        bortse från utfallet."""
        self.bok("från städningen till totalsförsvaret.",
                 "från städningen till totalförsvaret.")
        self.sida([{"id": "e1",
                    "corrections": [self.post("totalsförsvaret",
                                              "totalförsvaret",
                                              kind="emendering")]}])
        self.assertEqual(self.kvar(), 0)

    def test_citattecken_kring_ordet_hindrar_inte_heller(self):
        self.bok('han sa ”spårar” då', 'han sa ”spöar” då')
        self.sida([{"id": "e1", "corrections": [self.post("spårar", "spöar")]}])
        self.assertEqual(self.kvar(), 0)

    def test_post_pa_helt_element_forklarar_bara_sin_ordskillnad(self):
        """En post vars `original` är hela elementtexten ska bara kvitta de ord
        som faktiskt skiljer — inte immunisera elementets övriga ord."""
        self.bok("alfa beta gamma delta", "alfa beta gamma")
        self.sida([{"id": "e1",
                    "corrections": [self.post("alfa beta gamma delta",
                                              "alfa beta gamma epsilon")]}])
        r = granska(self.wd)
        # `delta` är förklarad av posten; `epsilon` lovades men uteblev, och
        # det är ingen ordFÖRÄNDRING i boken — alltså inget oförklarat.
        self.assertEqual(dict(r["oforklarat_borta"]), {})
        self.assertEqual(dict(r["oforklarat_nya"]), {})

    def test_tva_forekomster_men_en_post_lamnar_en_kvar(self):
        """Räkningen är per förekomst. En rättning på ett ställe förklarar inte
        att samma ord försvunnit på två."""
        self.bok("spårar och spårar", "spöar och spöar")
        self.sida([{"id": "e1", "corrections": [self.post("spårar", "spöar")]}])
        r = granska(self.wd)
        self.assertEqual(dict(r["oforklarat_borta"]), {"spårar": 1})
        self.assertEqual(dict(r["oforklarat_nya"]), {"spöar": 1})


class TestSkiljeteckensbyte(Bokbadd):
    """En post kan byta skiljetecknen runt ett ord utan att röra ordet.

    Advokaten skrev om `"N 2420"/"IN 2421"` till `"…N 2421"` på
    sieger-bauhaus-block s. 1. Kärnan `n` står då i både `original` och
    `corrected`, nettar till noll — medan `diffa` ser två olika tokens och
    rapporterar både ett bortfall och ett tillskott.
    """

    def test_kvittas_nar_posten_ror_ordet(self):
        self.bok('skylten "N 2420"', 'skylten "…N 2421"')
        self.sida([{"id": "e1",
                    "corrections": [self.post('skylten "N 2420"',
                                              'skylten "…N 2421"')]}])
        self.assertEqual(self.kvar(), 0)

    def test_kvittas_inte_nar_ingen_post_ror_ordet(self):
        self.bok('skylten "N 2420"', 'skylten "…N 2421"')
        self.sida([{"id": "e1", "corrections": []}])
        self.assertEqual(self.kvar(), 4)

    def test_kvittningen_har_ett_tak(self):
        """Kvittningen får aldrig gå längre än vad som tar ut sig självt.

        Tre förekomster försvinner och en kommer tillbaka i ny skepnad: EN är
        skiljeteckensbyte, de andra två är verkliga bortfall och ska stå kvar.
        Utan taket skulle en post om ett enda tecken frita hela förlusten.
        """
        self.bok('"alfa" "alfa" "alfa"', "alfa")
        self.sida([{"id": "e1", "corrections": [self.post('"alfa"', "alfa")]}])
        r = granska(self.wd)
        self.assertEqual(sum(r["oforklarat_borta"].values()), 2)
        self.assertEqual(sum(r["oforklarat_nya"].values()), 0)


class TestTillagdaElement(Bokbadd):
    """Ett räddat element bär inga korrektionsposter — men är redovisat.

    Advokaten på sieger-bauhaus-block s. 2 fann en hel illustration som
    saknades i draften: porträttet fanns som element, den stora interiörbilden
    som texten flödar om fanns inte. Ingen `forbesikta`-regel och ingen
    textjämförelse ser det, bara att bilderna räknas. Tillägget är en
    komplettering, och ett instrument som fäller den lär användaren att bortse
    från utfallet.
    """

    def test_tillagt_element_forklarar_sina_egna_ord(self):
        self.bok("alfa beta", "alfa beta gamma delta")
        self.sida([{"id": "e1", "corrections": []},
                   {"id": "e2", "text": "gamma delta",
                    "added_by": "agent:djavulens-advokat", "corrections": []}])
        self.assertEqual(self.kvar(), 0)

    def test_element_utan_added_by_forklarar_ingenting(self):
        """Skillnaden mellan en redovisad komplettering och tyst tillskott är
        just fältet som säger vem som gjorde det."""
        self.bok("alfa beta", "alfa beta gamma delta")
        self.sida([{"id": "e1", "corrections": []},
                   {"id": "e2", "text": "gamma delta", "corrections": []}])
        self.assertEqual(self.kvar(), 2)

    def test_tillagt_element_forklarar_inte_bortfall(self):
        """Ett tillägg kan aldrig förklara att ord FÖRSVUNNIT."""
        self.bok("alfa beta gamma", "alfa beta")
        self.sida([{"id": "e2", "text": "gamma",
                    "added_by": "agent:djavulens-advokat", "corrections": []}])
        r = granska(self.wd)
        self.assertEqual(dict(r["oforklarat_borta"]), {"gamma": 1})

    def test_tillagt_statblock_raknar_sin_data(self):
        self.bok("alfa", "alfa MARYAM NOM")
        self.sida([{"id": "e1", "corrections": []},
                   {"id": "e2", "type": "statblock",
                    "added_by": "agent:djavulens-advokat", "corrections": [],
                    "data": {"name": "MARYAM", "other": {"Klass": "NOM"}}}])
        self.assertEqual(self.kvar(), 0)


class TestSidval(Bokbadd):
    def test_validated_bredvid_final_dubbelraknas_inte(self):
        """`final.json` är sidans slutversion och `validated.json` en tidigare
        version av samma sida. Läses båda får varje post dubbel vikt, och två
        förlorade ord kvittas av en enda rättning."""
        self.bok("spårar och spårar", "spöar och spöar")
        el = [{"id": "e1", "corrections": [self.post("spårar", "spöar")]}]
        self.sida(el, "page_001.final.json")
        self.sida(el, "page_001.validated.json")
        r = granska(self.wd)
        self.assertEqual(dict(r["oforklarat_borta"]), {"spårar": 1})

    def test_validated_utan_final_raknas(self):
        """En sida som ännu inte varit hos advokaten bär sina poster i
        `validated.json`, och de är lika giltiga."""
        self.bok("han spårar upp dem", "han spöar upp dem")
        self.sida([{"id": "e1", "corrections": [self.post("spårar", "spöar")]}],
                  "page_001.validated.json")
        self.assertEqual(self.kvar(), 0)


class TestOrordaIllustrationer(Bokbadd):
    def test_orord_bildbeskrivning_krediterar_ingenting(self):
        """Ett orört bildelement nettar redan till noll i `diffa` — en kredit
        för dess text har ingen motpart i diffen och ligger och väntar på att
        sluka en obesläktad ändring av samma ord. På elefanten s. 5 åt kart-
        beskrivningens `stora` upp nya-sidan av citatbytet `"stora`→`”stora`,
        och borta-sidan strandade som oförklarad. Samma överkreditklass som
        `TERMINAL` ×9."""
        self.bok('Palle antyder att "stora saker" väntar',
                 'Palle antyder att ”stora saker” väntar')
        self.sida([
            {"id": "e1", "type": "illustration",
             "text": "Karta över den stora staden.", "corrections": []},
            {"id": "e2", "corrections": [self.post('"stora saker"',
                                                   "”stora saker”")]},
        ])
        self.assertEqual(self.kvar(), 0)

    def test_rattad_bildbeskrivning_redovisas_fortfarande_pa_bada_sidor(self):
        self.bok("beskrivning: en gammal karta", "beskrivning: en ny plan")
        self.sida([{"id": "e1", "type": "illustration", "text": "en ny plan",
                    "corrections": [self.post("en gammal karta",
                                              "en ny plan")]}])
        self.assertEqual(self.kvar(), 0)

    def test_forlegad_post_krediterar_ingenting(self):
        """Skymningslandet: en juli-revert (`är inte`→`inte`) var redan inbakad
        i augusti-frysningen, men postens borta-kredit för `är` låg kvar och
        konsumerade motparten till s. 7:s färska `...är`→`... är` — vars
        nya-sida då strandade som oförklarad. En post vars `corrected` står i
        frysningen medan `original` inte gör det är äldre än frysningen och
        krediteras inte."""
        self.bok("bilfärder inte någon utflykt. Vi ...är klara",
                 "bilfärder inte någon utflykt. Vi ... är klara")
        self.sida([
            {"id": "e1", "corrections": [self.post(
                "bilfärder är inte någon utflykt",
                "bilfärder inte någon utflykt")]},
            {"id": "e2", "corrections": [self.post("Vi ...är klara",
                                                   "Vi ... är klara")]},
        ])
        self.assertEqual(self.kvar(), 0)

    def test_strukturpost_krediterar_inga_ord(self):
        """Del I: tabellmontagens poster har `corrected` = tabellens
        JSON-form och omtypningarnas `original`/`corrected` = `type: …`.
        Ingendera är löptext som `bok.md` återger, så deras orddeltor har
        inga motparter i diffen — men kärnorna (siffrorna ur JSON-raderna)
        låg kvar som krediter och åt borta-sidan av sex färska
        citatglyfbyten i tabellceller: `'lyckat'`→`’lyckat’` strandade som
        OFÖRKLARAT NYA fast posten fanns. En strukturpost krediterar aldrig
        ord; en flerradig eller omflödad PROSA-post krediterar som förut."""
        self.bok("resultat 'lyckat' i cellen", "resultat ’lyckat’ i cellen")
        self.sida([
            {"id": "e1", "corrections": [self.post(
                "gammal lös cellrad med resultat 'lyckat' som inte längre finns",
                '{"headers":["lyckat"],"rows":[["gammal","lös"]]}')]},
            {"id": "e1b", "corrections": [self.post("type: paragraph",
                                                    "type: table")]},
            {"id": "e2", "corrections": [self.post("resultat 'lyckat' i cellen",
                                                   "resultat ’lyckat’ i cellen")]},
        ])
        self.assertEqual(self.kvar(), 0)

    def test_flerradig_prosapost_krediterar_som_forut(self):
        """En färsk post vars `original` inte återges ordagrant i
        frysningen (versen radbryts annorlunda i `bok.md`) ska INTE falla
        på något åldersprov — Tanegashimas versapostrofer strandade när ett
        sådant prövades."""
        self.bok("here's the consequence of murder",
                 "here’s the consequence of murder")
        self.sida([{"id": "e1", "corrections": [self.post(
            "1.\nhere's the consequence\nof murder",
            "1.\nhere’s the consequence\nof murder")]}])
        self.assertEqual(self.kvar(), 0)

    def test_tillagd_bild_fore_frysningen_krediterar_inte_sin_text(self):
        """Gripeborg: två bildelement tillagda i juli bar `added_by` när boken
        omfrystes i augusti. Deras beskrivningar stod därmed på BÅDA sidor av
        frysningen och nettade till noll i diffen — men fulltextkrediten låg
        kvar och åt upp nykvittningen för fyra obesläktade citatglyfbyten
        (`av.”`, `in”.`, `’Händer’`, `’Klor’`). Står beskrivningen ordagrant i
        frysningen är elementet äldre än den, och tillägget krediteras inte."""
        self.bok('En vandrare med stav i öknen. Han gav sig "av."',
                 'En vandrare med stav i öknen. Han gav sig ”av.”')
        self.sida([
            {"id": "e1", "type": "illustration",
             "text": "En vandrare med stav i öknen.",
             "added_by": "agent:layoutverifierare", "corrections": []},
            {"id": "e2", "corrections": [self.post('sig "av."',
                                                   "sig ”av.”")]},
        ])
        self.assertEqual(self.kvar(), 0)

    def test_tillagd_bild_efter_frysningen_krediteras_fortfarande(self):
        """Motfallet: beskrivningen finns INTE i frysningen — elementet är ett
        äkta tillägg och dess ord är nya (Mervyn Peak s. 5)."""
        self.bok("bara brödtext här", "bara brödtext här\n\n*En ny målning.*")
        self.sida([
            {"id": "e1", "type": "illustration", "text": "En ny målning.",
             "added_by": "agent:djavulens-advokat", "corrections": []},
        ])
        self.assertEqual(self.kvar(), 0)

    def test_andrad_bildbeskrivning_krediterar_inte_sin_oforandrade_del(self):
        """Krugal s. 10: kartbeskrivningen (ändrad i EN detalj) innehöll orden
        `Krugals komplex`, och fulltextkrediten åt upp kvittningen för
        citatbytet `"Krugals komplex"` → `”…”` på s. 1. Bara postens egen
        ordändring får krediteras — beskrivningens oförändrade del nettar
        redan till noll i diffen."""
        self.bok('vid "Krugals komplex" står vakter',
                 'vid ”Krugals komplex” står vakter')
        self.sida([
            {"id": "e1", "type": "illustration",
             "text": "Karta över Krugals komplex med fyra detaljrutor.",
             "corrections": [self.post("tre detaljrutor", "fyra detaljrutor")]},
            {"id": "e2", "corrections": [self.post('"Krugals komplex"',
                                                   "”Krugals komplex”")]},
        ])
        self.assertEqual(self.kvar(), 0)


class TestUtanFrysning(Bokbadd):
    def test_saknad_frysning_ger_filfel_inte_falskt_gront(self):
        (self.wd / "export" / "bok.md").write_text("text", encoding="utf-8")
        with self.assertRaises(FileNotFoundError):
            granska(self.wd)


if __name__ == "__main__":
    unittest.main()
