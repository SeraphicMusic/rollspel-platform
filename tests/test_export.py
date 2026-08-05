"""Tester för läsexportens elementrendering.

Bakgrund: exportören hade en tyst catch-all som renderade varje okänd
elementtyp som ett eget stycke. Grundregelbokens tabellceller föll därför ut
som en rad per cell utan att något syntes i loggen.
"""
import json
import tempfile
import unittest
from pathlib import Path

from pipeline.export import export_csv, export_markdown


def book(elements):
    return {
        "source": {"path": "/tmp/test.pdf", "metadata": {"title": "Testbok"},
                   "pages": 1},
        "system": {"id": "dod"},
        "stats": {"missing_pages": [], "needs_review": 0},
        "pages": [{"page": 1, "elements": elements}],
    }


class TestExportMarkdown(unittest.TestCase):
    def render(self, elements):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            (workdir / "export").mkdir()
            (workdir / "export" / "bok.json").write_text(
                json.dumps(book(elements), ensure_ascii=False),
                encoding="utf-8")
            return export_markdown(workdir).read_text(encoding="utf-8")

    def test_illustration_is_a_caption_not_body_text(self):
        md = self.render([
            {"id": "e01", "type": "paragraph", "text": "Brödtext."},
            {"id": "e02", "type": "illustration",
             "text": "Karta över kustbyn Springvatten."},
        ])
        self.assertIn("*Karta över kustbyn Springvatten.*", md)
        self.assertIn("Brödtext.", md)

    def test_list_item_and_requirement_become_bullets(self):
        md = self.render([
            {"id": "e01", "type": "list_item", "text": "Första punkten"},
            {"id": "e02", "type": "list_item", "text": "Andra punkten"},
            {"id": "e03", "type": "requirement", "text": "STY 12"},
        ])
        self.assertIn("- Första punkten", md)
        self.assertIn("- Andra punkten", md)
        self.assertIn("- STY 12", md)

    def test_loose_cells_are_assembled_into_a_table(self):
        md = self.render([
            {"id": "e01", "type": "table_header", "text": "Ras"},
            {"id": "e02", "type": "table_header", "text": "Kostnad i BP"},
            {"id": "e03", "type": "table_cell", "text": "Alv"},
            {"id": "e04", "type": "table_cell", "text": "25"},
            {"id": "e05", "type": "table_cell", "text": "Anka"},
            {"id": "e06", "type": "table_cell", "text": "0"},
        ])
        self.assertIn("| Ras | Kostnad i BP |", md)
        self.assertIn("| Alv | 25 |", md)
        self.assertIn("| Anka | 0 |", md)
        # Ingen cell får ligga kvar som eget stycke.
        self.assertNotIn("\nAlv\n", md)

    def test_unassemblable_cells_keep_their_values(self):
        """Ojämnt cellblock monteras inte — men värdena får inte tappas."""
        md = self.render([
            {"id": "e01", "type": "table_header", "text": "A"},
            {"id": "e02", "type": "table_header", "text": "B"},
            {"id": "e03", "type": "table_header", "text": "C"},
            {"id": "e04", "type": "table_cell", "text": "x"},
            {"id": "e05", "type": "table_cell", "text": "y"},
        ])
        for value in ("A", "B", "C", "x", "y"):
            self.assertIn(value, md)

    def test_statblock_weapons_are_rendered(self):
        md = self.render([{
            "id": "e01", "type": "statblock", "text": "",
            "data": {"name": "GRIP", "stats": {"STY": 19},
                     "weapons": [{"name": "2 Klor", "attack": "80%",
                                  "damage": "1T6+SB"}]},
        }])
        self.assertIn("| Vapen | Attack | Skada |", md)
        self.assertIn("| 2 Klor | 80% | 1T6+SB |", md)

    def test_internal_statblock_key_is_hidden(self):
        md = self.render([{
            "id": "e01", "type": "statblock", "text": "",
            "data": {"name": "GRIP", "stats": {"STY": 19},
                     "other": {"Skydd": "4 poäng hud",
                               "attacktabell_rubrik": "Attacker / CL / Skada"}},
        }])
        self.assertIn("**Skydd:** 4 poäng hud", md)
        self.assertNotIn("attacktabell_rubrik", md)

    def test_nested_statblock_field_is_rendered_readably(self):
        """Spöket (s. 47) bär en hel kolumn ur rutan i `extraStats`.

        Utan uppackning föll den ut som en rå Python-dict i `bok.md`:
        `- **Multipel:** {'STY': '0', 'STO': 'x1'}`.
        """
        md = self.render([{
            "id": "e01", "type": "statblock", "text": "",
            "data": {"name": "SPÖKE", "stats": {"STO": 11},
                     "extraStats": {"Multipel": {"STY": "0", "STO": "x1"}}},
        }])
        self.assertIn("**Multipel:** STY 0, STO x1", md)
        self.assertNotIn("{", md)

    def test_genuinely_unknown_type_is_kept_and_warned(self):
        md = self.render([
            {"id": "e01", "type": "nyuppfunnen_typ", "text": "Viktigt värde"},
        ])
        self.assertIn("Viktigt värde", md)


def line(eid, text, x=0.06, w=0.43, y=0.9, etype="paragraph"):
    """Ett element = EN tryckt rad, som i transkriptionen."""
    return {"id": eid, "type": etype, "text": text,
            "source": {"bbox": [x, y, w, 0.016]}}


class TestReflow(unittest.TestCase):
    """Rader ska fogas ihop till stycken igen.

    Utan detta blev varje tryckt rad ett eget markdown-stycke — hela
    DoD-grundregelboken föll ut med 3150 enradiga stycken.
    """

    def render(self, elements):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            (workdir / "export").mkdir()
            (workdir / "export" / "bok.json").write_text(
                json.dumps(book(elements), ensure_ascii=False),
                encoding="utf-8")
            return export_markdown(workdir).read_text(encoding="utf-8")

    def test_lines_of_one_paragraph_are_joined(self):
        md = self.render([line("e01", "Den hand som du normalt använder"),
                          line("e02", "kallas för svärdshand.")])
        self.assertIn("Den hand som du normalt använder kallas för "
                      "svärdshand.", md)

    def test_indent_starts_a_new_paragraph(self):
        md = self.render([line("e01", "Slutet på första stycket."),
                          line("e02", "Nytt stycke börjar här.", x=0.085),
                          line("e03", "och fortsätter här.")])
        self.assertIn("Slutet på första stycket.\n\nNytt stycke börjar här. "
                      "och fortsätter här.", md)

    def test_hanging_indent_is_not_a_paragraph_break(self):
        """`Rundspark:` i marginalen med indragna fortsättningsrader (s. 59).

        Polariteten är omvänd mot ett styckeindrag: här är det FORTSÄTTNINGEN
        som är indragen. Läses indraget som styckestart delas varje sådant
        stycke i en rad per stycke.
        """
        md = self.render([line("e01", "Rundspark: För att få fart"),
                          line("e02", "snurrar man ett varv.", x=0.09),
                          line("e03", "Sparken gör 1T8 i skada.", x=0.09)])
        self.assertIn("Rundspark: För att få fart snurrar man ett varv. "
                      "Sparken gör 1T8 i skada.", md)

    def test_short_line_ends_the_paragraph(self):
        """Satsen är utsluten: bara styckets sista rad fyller inte spalten."""
        md = self.render([line("e01", "En rad som fyller hela spalten."),
                          line("e02", "Sista raden.", w=0.18),
                          line("e03", "Ett nytt stycke tar vid.")])
        self.assertIn("En rad som fyller hela spalten. Sista raden.\n\n"
                      "Ett nytt stycke tar vid.", md)

    def test_exempelrutans_stycken_blir_ETT_citatblock(self):
        """En tryckt ruta är EN ruta även när den rymmer flera stycken.

        Skiljs styckena av en tom rad blir de två citatblock i markdown och
        rutan går synligt itu. Felet blev synligt först när raderna började
        mätas på sin egen bredd i stället för på rutans ram: dessförinnan var
        varje rad i rutan lika bred, och kortradsregeln kunde aldrig bryta
        stycket alls (del II s. 10, HINDER och SLUMPMÄSSIGA MÖTEN).
        """
        md = self.render([
            line("e01", "Exempel: hindret är att finna den glömda dalen.",
                 etype="boxed_text"),
            line("e02", "Sista raden.", w=0.18, etype="boxed_text"),
            line("e03", "Vad som än händer måste RPna till borgen.",
                 etype="boxed_text"),
        ])
        rutan = [rad for rad in md.split("\n") if rad.startswith(">")]
        self.assertEqual(len(rutan), 3, md)
        self.assertEqual(rutan[1], ">", "styckena blev tva citatblock:\n" + md)
        self.assertNotIn("\n\n>", md.split("Exempel")[1])

    def test_hyphenation_at_line_break_is_healed(self):
        md = self.render([line("e01", "Texten korrigerades och komplette-"),
                          line("e02", "rades inför utgåvan.")])
        self.assertIn("korrigerades och kompletterades inför utgåvan.", md)
        self.assertNotIn("komplette-", md)

    def test_hanging_hyphen_in_a_coordination_is_kept(self):
        """`djur-` + `växt- och mineralriket` är ingen avstavning."""
        md = self.render([line("e01", "gifter, både från djur-"),
                          line("e02", "växt- och mineralriket.")])
        self.assertIn("från djur- växt- och mineralriket.", md)
        self.assertNotIn("djurväxt", md)

    def test_compound_hyphen_after_a_capital_abbreviation_is_kept(self):
        """`PSY-` + `poäng` är ett sammansättningsstreck, inte en avstavning.

        BQ-024: felet stod LIVE i `bok.md` som `PSYpoäng` och `STYkrav` medan
        sidfilerna hela tiden återgav trycket rätt.
        """
        md = self.render([line("e01", "Hur man återvinner PSY-"),
                          line("e02", "poäng efter en besvärjelse.")])
        self.assertIn("återvinner PSY-poäng efter", md)
        self.assertNotIn("PSYpoäng", md)

    def test_hyphenation_of_a_capitalised_word_is_healed(self):
        """Ett VERSALSATT ord som bryts över radslutet ska också läkas.

        Läkningen krävde tidigare att nästa rad börjar gement, så tolv
        besvärjelsenamn stod med ett påhittat streck i sig i `bok.md`
        (`ANTI- MAGI`, `MÖRK- RET`, `TELEPORTE- RING` …). Fortsättningens
        versalform skiljer arten från sammansättningsstrecket: `ANTI-` + `MAGI`
        är ett avstavat `ANTIMAGI` (beslut s. 14), medan `PSY-` + `poäng` är
        två ord i en sammansättning.
        """
        md = self.render([line("e01", "besvärjelsen ANTI-"),
                          line("e02", "MAGI har effektgrad 3.")])
        self.assertIn("besvärjelsen ANTIMAGI har effektgrad 3.", md)
        self.assertNotIn("ANTI- MAGI", md)

    def test_avstavning_haller_ihop_stycket_aven_utan_geometri(self):
        """En rad som slutar på bindestreck kan inte avsluta ett stycke.

        Femton stycken i del III föll isär därför att FORTSÄTTNINGEN saknade
        uppmätt rad: `…kommunicera med levan-` blev ett stycke och `de ting.`
        nästa. Utan geometri fogade exporten ingenting ihop — men strecket är
        i sig ett bevis på att ordet fortsätter.
        """
        md = self.render([line("e01", "kommunicera med levan-"),
                          {"id": "e02", "type": "paragraph",
                           "text": "de ting."}])
        self.assertIn("kommunicera med levande ting.", md)
        self.assertNotIn("levan-", md)

    def test_radbrytningar_inuti_ett_element_fogas_ocksa_ihop(self):
        """Exempelrutan på s. 8 är ETT element med fem tryckta rader i `text`.

        `_reflow` hade då ingenting att foga ihop, och rutan föll ut rad för
        rad med ett påhittat streck i `PARA-` / `LYSERING`.
        """
        md = self.render([{
            "id": "e01", "type": "boxed_text",
            "text": "Exempel: En magiker som lär sig PARA-\n"
                    "LYSERING ur kodexen Liber Necro-\nsophicus.",
            "source": {"bbox": [0.53, 0.12, 0.38, 0.05]}}])
        self.assertIn("lär sig PARALYSERING ur kodexen Liber Necrosophicus.",
                      md)
        self.assertNotIn("PARA-", md)

    def test_tom_rad_inuti_rutan_ar_en_styckegrans(self):
        """Blankraden skiljer rutans stycken och får inte fogas bort."""
        md = self.render([{
            "id": "e01", "type": "boxed_text",
            "text": "Första stycket i rutan.\n\nAndra stycket i rutan.",
            "source": {"bbox": [0.53, 0.12, 0.38, 0.05]}}])
        self.assertIn("> Första stycket i rutan.\n> \n> Andra stycket i "
                      "rutan.", md)

    def test_avstavning_slar_utslutningsregeln(self):
        """En avstavad rad är aldrig styckets sista, hur kort den än är.

        Exempelrutan på s. 10 bröts vid `…och mina kamra-` därför att raden
        mättes till 0,3805 mot spaltens 0,4222 — under regel 1b:s gräns. Rutan
        gick synligt itu och `ter skriker förtvivlat` blev ett eget citatblock.
        """
        md = self.render([line("e01", "Det är varmt och mina kamra-", w=0.38),
                          line("e02", "ter skriker förtvivlat.", w=0.42)])
        self.assertIn("Det är varmt och mina kamrater skriker förtvivlat.", md)

    def test_utan_geometri_och_utan_streck_fogas_inget_ihop(self):
        """Motprovet: saknad geometri utan avstavning bryter som förut."""
        md = self.render([line("e01", "Ett helt stycke som slutar här."),
                          {"id": "e02", "type": "paragraph",
                           "text": "Ett nytt stycke."}])
        self.assertIn("Ett helt stycke som slutar här.\n\nEtt nytt stycke.",
                      md)

    def test_versalt_ord_med_gemen_andelse_lakas_ocksa(self):
        """`LJU-` + `Sets` är ett brutet `LJUSets` — inte två ord.

        Läkningen krävde TVÅ versaler i fortsättningen, och missade därmed
        precis de bryt där versalordet bär en gement satt böjningsändelse.
        Två fall stod live i `bok.md` (del III): `LJU- Sets` (s. 19, formeln
        LJUS i `MÖRKRETs grad mot LJUSets grad`) och `MOTSTÅNDSKRAF- Ten`
        (s. 39). Båda med ett påhittat streck och ett mellanrum mitt i ordet.
        """
        md = self.render([line("e01", "måste MÖRKRETs grad övervinna LJU-"),
                          line("e02", "Sets grad på motståndstabellen.")])
        self.assertIn("övervinna LJUSets grad", md)
        self.assertNotIn("LJU- Sets", md)

    def test_hangande_streck_slar_den_vidgade_versalregeln(self):
        """`ÄVENTYRS-` + `OCH` får inte skrivas ihop.

        Motprovet mot att versalregeln blev för vid när den slutade kräva två
        versaler i fortsättningen: ett hängande streck framför ett samordnande
        `OCH` prövas FÖRE den, och strecket behåller sitt mellanrum.
        """
        md = self.render([line("e01", "i kapitlet ÄVENTYRS-"),
                          line("e02", "OCH REGELTABELLER finns listan.")])
        self.assertIn("ÄVENTYRS- OCH REGELTABELLER", md)
        self.assertNotIn("ÄVENTYRSOCH", md)

    def test_hanging_hyphen_wins_over_the_abbreviation_rule(self):
        """`SMI-` + `och` är hängande, inte en sammansättning.

        Prövas förkortningsregeln först skrivs de ihop till `SMI-och`.
        """
        md = self.render([line("e01", "slag mot SMI-"),
                          line("e02", "och STY-baserade färdigheter.")])
        self.assertIn("mot SMI- och STY-baserade", md)
        self.assertNotIn("SMI-och", md)

    def test_hanging_hyphen_before_a_coordinating_word_is_kept(self):
        """`mynt-` + `och penningsystemet` — strecket är hängande.

        Den gamla `_HANGING_HYPHEN` såg bara varianten där NÄSTA rad själv
        börjar med ett streckförsett ord (`djur-` + `växt- och …`); den sade
        ingenting om ett naket `och`, och därför skrevs `myntoch`.
        """
        md = self.render([line("e01", "en värld där mynt-"),
                          line("e02", "och penningsystemet är outvecklat.")])
        self.assertIn("där mynt- och penningsystemet", md)
        self.assertNotIn("myntoch", md)

    def test_field_lines_are_not_glued_together(self):
        """Örtposterna (s. 53–61) sätts `Etikett: värde`, en per tryckt rad.

        Raderna fyller inte spalten, men breddreferensen räknas ur dem själva,
        så varken kortrads- eller utslutningsregeln biter. Utan en egen regel
        föll hela posten ut som en rad.
        """
        md = self.render([
            line("e01", "Tillredning: Brygges", w=0.16),
            line("e02", "Intagning: Dricks", w=0.14),
            line("e03", "Växtplats: Ljus lövskog", w=0.19),
        ])
        self.assertIn("Tillredning: Brygges\n\nIntagning: Dricks\n\n"
                      "Växtplats: Ljus lövskog", md)

    def test_prose_with_a_colon_is_still_reflowed(self):
        """En löptextrad som råkar bära ett kolon är ingen fältrad."""
        md = self.render([
            line("e01", "Han sade följande till spelledaren i stridens hetta:"),
            line("e02", "att en parering alltid kostar en handling."),
        ])
        self.assertIn("stridens hetta: att en parering", md)

    def test_slash_at_line_break_is_healed(self):
        """`(liten/medelstor/` + `stor)` fick ett felaktigt mellanslag."""
        md = self.render([line("e01", "Välj storlek (liten/medelstor/"),
                          line("e02", "stor) innan slaget.")])
        self.assertIn("(liten/medelstor/stor) innan slaget.", md)
        self.assertNotIn("medelstor/ stor", md)

    def test_spaced_slash_is_a_separator_and_keeps_its_space(self):
        """`Teknik /` + `Grundkostnad` skiljer två fält åt — ingen bindning."""
        md = self.render([line("e01", "Slå mot Smyga /"),
                          line("e02", "Gömma sig i strid.", w=0.18)])
        self.assertIn("Slå mot Smyga / Gömma sig i strid.", md)

    def test_toc_entries_are_never_reflowed(self):
        """En innehållspost är en rad; fogas de ihop förstörs uppställningen."""
        md = self.render([line("e01", "Rollpersonen 5", etype="toc_entry"),
                          line("e02", "Färdigheter 40", etype="toc_entry")])
        self.assertIn("Rollpersonen 5\n\nFärdigheter 40", md)

    def test_table_cells_typed_as_paragraphs_are_not_glued_together(self):
        """Celler som ligger som `paragraph` får inte bli cellsoppa.

        Simtabellen på s. 56 blev `Hyfsad simmare 2 3` när breddreferensen
        räknades ur cellerna själva. En rad som är mycket kortare än sidans
        löptext är ingen löptextrad.
        """
        md = self.render([
            line("e01", "Simning delas in i följande FN, vilket innebär:"),
            line("e02", "Hyfsad simmare", w=0.14),
            line("e03", "2", w=0.02),
            line("e04", "3", w=0.02),
            line("e05", "God simmare", w=0.13),
            line("e06", "En full rad löptext som fyller hela spalten här."),
        ])
        self.assertNotIn("Hyfsad simmare 2", md)
        self.assertIn("Hyfsad simmare\n\n2\n\n3\n\nGod simmare", md)

    def test_a_short_final_line_still_joins_backwards(self):
        """Kortregeln gäller bara framåt — styckets sista rad hör till stycket."""
        md = self.render([
            line("e01", "En rad som fyller hela spalten med löptext."),
            line("e02", "tion.", w=0.05),
            line("e03", "Ett nytt stycke tar vid och fyller spalten igen."),
        ])
        self.assertIn("En rad som fyller hela spalten med löptext. tion.", md)

    def test_lines_without_geometry_are_left_alone(self):
        """Utan bbox finns inget facit — då fogas ingenting ihop."""
        md = self.render([{"id": "e01", "type": "paragraph", "text": "Ett."},
                          {"id": "e02", "type": "paragraph", "text": "Två."}])
        self.assertIn("Ett.\n\nTvå.", md)


class TestArvdaKolumnrubriker(unittest.TestCase):
    """En deltabell under en spännrubrik ärver tabellens egna rubriker.

    Rustningstabellen (del III s. 38) har EN tryckt rubrikrad och därunder nio
    delposter under var sin spännrubrik. Bara den första bär rubrikerna, så
    exporten skrev en TOM rubrikrad (`| | | | |`) över de åtta andra — och en
    läsare som landar på `BRYNJEHOSOR (BEN)` såg `5 | 15 | 2.500` utan att veta
    att kolumnerna är absorbering, vikt och pris.
    """

    def render(self, pages):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            (workdir / "export").mkdir()
            data = book([])
            data["pages"] = pages
            (workdir / "export" / "bok.json").write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return export_markdown(workdir).read_text(encoding="utf-8")

    RUBRIKER = ["Namn (kroppsdel)", "Absorbering", "Vikt i kg", "Pris i sm"]

    @staticmethod
    def tom_rubrikrad(kolumner):
        """Så ser en tom rubrikrad ut i markdown — `|  |  |  |  |`."""
        return "| " + " | ".join([""] * kolumner) + " |"

    def sida(self, mellanled, andra_rubriker=None):
        return [{"page": 1, "elements": [
            {"id": "e01", "type": "table", "text": "",
             "data": {"headers": self.RUBRIKER,
                      "rows": [["Tyghjälm", "1", "1", "30"]]}},
            mellanled,
            {"id": "e03", "type": "table", "text": "",
             "data": {"headers": andra_rubriker
                      if andra_rubriker is not None else ["", "", "", ""],
                      "rows": [["Ringbrynja", "5", "15", "2.500"]]}},
        ]}]

    def test_spannrubrik_bryter_inte_tabellen(self):
        md = self.render(self.sida(
            {"id": "e02", "type": "table_caption",
             "text": "BRYNJEHOSOR (BEN)"}))
        self.assertEqual(md.count("| Namn (kroppsdel) | Absorbering "
                                  "| Vikt i kg | Pris i sm |"), 2)
        self.assertNotIn(self.tom_rubrikrad(4), md)

    def test_loptext_emellan_bryter_arvet(self):
        """Löptext mellan tabellerna betyder att en NY tabell börjar."""
        md = self.render(self.sida(
            {"id": "e02", "type": "paragraph",
             "text": "Sköldar behandlas i nästa avsnitt."}))
        self.assertEqual(md.count("| Namn (kroppsdel) | Absorbering "
                                  "| Vikt i kg | Pris i sm |"), 1)
        self.assertIn(self.tom_rubrikrad(4), md)

    def test_egna_rubriker_skrivs_aldrig_over(self):
        md = self.render(self.sida(
            {"id": "e02", "type": "table_caption", "text": "SKÖLDAR"},
            andra_rubriker=["Sköld", "BV", "Vikt", "Pris"]))
        self.assertIn("| Sköld | BV | Vikt | Pris |", md)

    def test_annan_kolumnform_arver_inte(self):
        """s. 25: `Rasmodifikationer` under förflyttningstabellen.

        Lika många kolumner, egen spännrubrik — och ändå en annan tabell.
        Skillnaden står i cellerna: modern har TAL i första kolumnen
        (`0–11`), dottern TEXT (`Anka`).
        """
        md = self.render([{"page": 1, "elements": [
            {"id": "e01", "type": "table_caption",
             "text": "TABELL FÖR FÖRFLYTTNINGSFÖRMÅGA"},
            {"id": "e02", "type": "table", "text": "",
             "data": {"headers": ["STO+FYS+SMI", "Förflyttning"],
                      "rows": [["0–11", "7"], ["12–13", "8"]]}},
            {"id": "e03", "type": "table_caption", "text": "Rasmodifikationer"},
            {"id": "e04", "type": "table", "text": "",
             "data": {"headers": ["", ""],
                      "rows": [["Anka", "–2"], ["Dvärg", "–1"]]}},
        ]}])
        self.assertEqual(md.count("| STO+FYS+SMI | Förflyttning |"), 1)
        self.assertIn(self.tom_rubrikrad(2), md)

    def test_olika_antal_kolumner_arver_inte(self):
        """Stämmer inte kolumnantalet är det inte samma tryckta tabell."""
        md = self.render(self.sida(
            {"id": "e02", "type": "table_caption", "text": "HJÄLMAR"},
            andra_rubriker=["", "", ""]))
        self.assertIn(self.tom_rubrikrad(3), md)
        self.assertEqual(md.count("| Namn (kroppsdel) | Absorbering "
                                  "| Vikt i kg | Pris i sm |"), 1)

    def test_sidbrytning_bryter_arvet(self):
        md = self.render([
            {"page": 1, "elements": [
                {"id": "e01", "type": "table", "text": "",
                 "data": {"headers": self.RUBRIKER,
                          "rows": [["Tyghjälm", "1", "1", "30"]]}}]},
            {"page": 2, "elements": [
                {"id": "e02", "type": "table_caption", "text": "BRYNJA"},
                {"id": "e03", "type": "table", "text": "",
                 "data": {"headers": ["", "", "", ""],
                          "rows": [["Ringbrynja", "5", "15", "2.500"]]}}]},
        ])
        self.assertIn(self.tom_rubrikrad(4), md)

    def test_csv_arver_samma_rubriker_som_markdown(self):
        """Läsformatet och CSV:n får inte säga olika saker om samma tabell."""
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            (workdir / "export").mkdir()
            data = book([])
            data["pages"] = self.sida(
                {"id": "e02", "type": "table_caption", "text": "BRYNJA"})
            (workdir / "export" / "bok.json").write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8")
            outdir, _ = export_csv(workdir)
            csvar = sorted(p.read_text(encoding="utf-8")
                           for p in outdir.glob("*.csv"))
        self.assertEqual(len(csvar), 2)
        for text in csvar:
            self.assertEqual(text.splitlines()[0],
                             "Namn (kroppsdel),Absorbering,Vikt i kg,Pris i sm")

    def test_tabell_helt_utan_rubriker_ror_vi_inte(self):
        """Skräcktabellen s. 10 har ingen rubrikrad i trycket och ingen förlaga.

        Den ska falla ut som förut — en tom rubrikrad är fulare än en ärvd,
        men den är sann.
        """
        md = self.render([{"page": 1, "elements": [
            {"id": "e01", "type": "table", "text": "",
             "data": {"headers": ["", ""],
                      "rows": [["1–5", "Effektgraden halveras."]]}}]}])
        self.assertIn(self.tom_rubrikrad(2), md)
        self.assertIn("| 1–5 | Effektgraden halveras. |", md)


class TestCrossPageTables(unittest.TestCase):
    """En tabell som löper över en sidbrytning ska fogas ihop.

    `tables.assemble` arbetar per sida. Särskilda förmågor-tabellen bröts därför
    mitt i rad 78 (`INT-basera-`) och raderna 79–81 föll ut som listpunkter
    utanför tabellen.
    """

    def render(self, pages):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            (workdir / "export").mkdir()
            data = book([])
            data["pages"] = pages
            (workdir / "export" / "bok.json").write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return export_markdown(workdir).read_text(encoding="utf-8")

    def test_tables_with_identical_headers_are_merged(self):
        md = self.render([
            {"page": 1, "elements": [{
                "id": "e01", "type": "table", "text": "",
                "data": {"headers": ["2T20+BP", "Förmåga"],
                         "rows": [["19-20", "SEGHET."]]}}]},
            {"page": 2, "elements": [{
                "id": "e02", "type": "table", "text": "",
                "data": {"headers": ["2T20+BP", "Förmåga"],
                         "rows": [["21-22", "STARKA NYPOR."]]}}]},
        ])
        self.assertEqual(md.count("| 2T20+BP | Förmåga |"), 1)
        self.assertIn("| 19-20 | SEGHET. |", md)
        self.assertIn("| 21-22 | STARKA NYPOR. |", md)

    def test_list_continuing_a_table_is_folded_back_in(self):
        md = self.render([
            {"page": 1, "elements": [{
                "id": "e01", "type": "table", "text": "",
                "data": {"headers": ["2T20+BP", "Förmåga"],
                         "rows": [["78", "HAMNBYTARE. Utom INT-basera-"]]}}]},
            {"page": 2, "elements": [{
                "id": "e02", "type": "list", "text": "",
                "data": {"items": ["de färdigheter.",
                                   "79 — SNABB UPPFATTNING."]}}]},
        ])
        self.assertIn("| 78 | HAMNBYTARE. Utom INT-baserade färdigheter. |", md)
        self.assertIn("| 79 | SNABB UPPFATTNING. |", md)
        self.assertNotIn("- 79 —", md)

    def test_unexpected_list_shape_leaves_the_table_alone(self):
        """Hellre en ful lista än tappad text."""
        md = self.render([
            {"page": 1, "elements": [{
                "id": "e01", "type": "table", "text": "",
                "data": {"headers": ["A", "B"], "rows": [["1", "ett"]]}}]},
            {"page": 2, "elements": [{
                "id": "e02", "type": "list", "text": "",
                "data": {"items": ["Helt annan text utan radform"]}}]},
        ])
        self.assertIn("- Helt annan text utan radform", md)
        self.assertIn("| 1 | ett |", md)


if __name__ == "__main__":
    unittest.main()


class TestTomNyttolast(unittest.TestCase):
    """Ett strukturelement vars nyttolast hamnat fel renderar ingenting.

    Del I s. 56 föll ur `bok.md` precis så: `rows` skrevs på elementets
    toppnivå i stället för under `data`, exportören läste `data` och skrev
    inget — och eftersom elementet varken hade `text` eller okänd typ sa
    ingen varning ifrån. Sju tabellrader försvann tyst.
    """

    def lost(self, elements):
        from pipeline.export import warn_empty_payloads

        class Log:
            def __init__(self):
                self.lines = []

            def warning(self, *args):
                self.lines.append(args)

        log = Log()
        return warn_empty_payloads(book(elements), log), log.lines

    def test_rader_pa_toppnivan_flaggas(self):
        lost, lines = self.lost([{"type": "table", "id": "p001_e01",
                                  "rows": [["FN", "Förflyttning"]]}])
        self.assertEqual(len(lost), 1)
        self.assertEqual(lost[0][3], ["rows"])
        self.assertIn("toppnivå", str(lines[0]))

    def test_tabell_med_data_rows_ar_tyst(self):
        lost, _ = self.lost([{"type": "table", "id": "p001_e01",
                              "data": {"headers": ["a"], "rows": [["1"]]}}])
        self.assertEqual(lost, [])

    def test_tom_lista_flaggas(self):
        lost, _ = self.lost([{"type": "list", "id": "p001_e01",
                              "data": {"items": []}}])
        self.assertEqual(len(lost), 1)

    def test_borttaget_element_flaggas_inte(self):
        lost, _ = self.lost([{"type": "table", "id": "p001_e01",
                              "removed": True}])
        self.assertEqual(lost, [])

    def test_statblock_racker_med_ett_falt(self):
        lost, _ = self.lost([{"type": "statblock", "id": "p001_e01",
                              "data": {"stats": {"STY": 10}}}])
        self.assertEqual(lost, [])


class TestPunktlistor(unittest.TestCase):
    """En listpunkt spänner ofta över flera tryckta rader.

    Bara den första raden bär punkttecknet; resten är vanliga rader. Bröts
    följden vid typbytet hamnade fortsättningen i ett eget stycke och ett
    avstavat ord över radslutet läkte aldrig — del I s. 51 fick `motstån-` och
    `daren.` som två stycken.
    """

    def render(self, elements):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            (workdir / "export").mkdir()
            (workdir / "export" / "bok.json").write_text(
                json.dumps(book(elements), ensure_ascii=False),
                encoding="utf-8")
            return export_markdown(workdir).read_text(encoding="utf-8")

    def test_punkttecknet_dubbleras_inte(self):
        """Trycket har EN punkt; markdownens `- ` säger redan samma sak."""
        md = self.render([line("e01", "• Köpa ras", etype="list_item")])
        self.assertIn("- Köpa ras", md)
        self.assertNotIn("- • Köpa ras", md)

    def test_texten_i_datan_behaller_punkttecknet(self):
        """Renderingen droppar glyfen — elementet är fortfarande print-troget."""
        el = line("e01", "• Köpa ras", etype="list_item")
        self.assertEqual(el["text"], "• Köpa ras")

    def test_flerradig_punkt_fogas_ihop(self):
        md = self.render([
            line("e01", "• SL slår dolt 1T10 för rollpersonen och för motstån-",
                 etype="list_item"),
            line("e02", "daren och adderar resultaten.", y=0.88)])
        self.assertIn("- SL slår dolt 1T10 för rollpersonen och för "
                      "motståndaren och adderar resultaten.", md)

    def test_loptext_under_listan_blir_stycke_igen(self):
        """Följden sväljer löptexten, men blocket renderas efter vad det inleds av."""
        md = self.render([
            line("e01", "• Höja CL", etype="list_item"),
            line("e02", "Nytt stycke som inte hör till listan.", x=0.085,
                 y=0.86)])
        self.assertIn("- Höja CL", md)
        self.assertIn("\nNytt stycke som inte hör till listan.", md)
        self.assertNotIn("- Nytt stycke", md)


class TestSpanningHeaders(unittest.TestCase):
    """En rubrik över flera kolumner får inte tyst falla ur läsexporten.

    `Grundegenskapskrav` (s. 12) står över hela attributblocket. Markdown kan
    inte uttrycka det, och `diffa` visade att ordet försvann helt ur bok.md
    när tabellen väl monterades. Det renderas därför som en bildtext.
    """

    def render(self, elements):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            (workdir / "export").mkdir()
            (workdir / "export" / "bok.json").write_text(
                json.dumps(book(elements), ensure_ascii=False),
                encoding="utf-8")
            return export_markdown(workdir).read_text(encoding="utf-8")

    def _tabell(self, spans):
        data = {"headers": ["Yrke", "STY", "FYS"],
                "rows": [["Krigare", "14", "12"], ["Tjuv", "", "16"]]}
        if spans is not None:
            data["spans"] = spans
        return [{"id": "e01", "type": "table", "text": "", "data": data}]

    def test_spannrubriken_renderas_som_bildtext(self):
        md = self.render(self._tabell(
            [{"label": "Grundegenskapskrav", "columns": ["STY", "FYS"]}]))
        self.assertIn("*Grundegenskapskrav — gemensam rubrik över STY, FYS*",
                      md)
        self.assertIn("| Yrke | STY | FYS |", md)

    def test_tabell_utan_spann_ar_oforandrad(self):
        md = self.render(self._tabell(None))
        self.assertNotIn("gemensam rubrik", md)
        self.assertIn("| Yrke | STY | FYS |", md)

    def test_ofullstandigt_spann_hoppas_over(self):
        md = self.render(self._tabell([{"label": "", "columns": ["STY"]},
                                       {"label": "Utan kolumner",
                                        "columns": []}]))
        self.assertNotIn("gemensam rubrik", md)


class TestAnmarkning(unittest.TestCase):
    """Redaktionell notis i läsexporten utan att trycket rörs.

    Boken säger på s. 65 "de färdigheter som är baserade på färdigheten" där
    sammanhanget kräver "grundegenskapen". Regel 8a förbjuder att ordet byts —
    men lämnas meningen helt okommenterad är den obegriplig för en läsare.
    """

    def render(self, elements):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            (workdir / "export").mkdir()
            (workdir / "export" / "bok.json").write_text(
                json.dumps(book(elements), ensure_ascii=False),
                encoding="utf-8")
            return export_markdown(workdir).read_text(encoding="utf-8")

    def test_anmarkning_renderas_efter_stycket(self):
        md = self.render([
            {"id": "e01", "type": "paragraph", "text": "Höjningen är permanent.",
             "anmarkning": "trycket har ”färdigheten”, ska vara ”grundegenskapen”"},
        ])
        self.assertIn("Höjningen är permanent.", md)
        self.assertIn("*[Anmärkning: trycket har ”färdigheten”, ska vara "
                      "”grundegenskapen”]*", md)
        self.assertLess(md.index("Höjningen"), md.index("Anmärkning"))

    def test_trycket_ror_inte(self):
        md = self.render([
            {"id": "e01", "type": "paragraph", "text": "baserade på färdigheten.",
             "anmarkning": "ska vara grundegenskapen"},
        ])
        self.assertIn("baserade på färdigheten.", md)
        self.assertNotIn("baserade på grundegenskapen.", md)

    def test_anmarkning_pa_rad_mitt_i_stycket_overlever_omflodningen(self):
        """Tryckfelet sitter sällan på styckets FÖRSTA rad."""
        md = self.render([
            {"id": "e01", "type": "paragraph",
             "text": "För 5 HP får man höja en grundegenskap en poäng och",
             "source": {"bbox": [0.5, 0.30, 0.44, 0.016]}},
            {"id": "e02", "type": "paragraph",
             "text": "detta påverkar de färdigheter som baseras på färdigheten.",
             "source": {"bbox": [0.5, 0.284, 0.44, 0.016]},
             "anmarkning": "ska vara grundegenskapen"},
        ])
        self.assertIn("Anmärkning: ska vara grundegenskapen", md)

    def test_element_utan_anmarkning_far_ingen_rad(self):
        md = self.render([{"id": "e01", "type": "paragraph", "text": "Vanlig text."}])
        self.assertNotIn("Anmärkning", md)
