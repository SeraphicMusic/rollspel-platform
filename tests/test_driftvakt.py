"""Driftvakten, boknivåkön och ordkonserveringen.

Alla tre är svar på samma sorts fel: något som inte syns på någon enskild sida
och därför aldrig larmar, men som förstör boken sedd som helhet.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from pipeline.decisions import enqueue, next_id, open_questions, queue_items
from pipeline.freeze import diff, freeze, words
from pipeline.preflight import drift_split_tables, drift_ceased_types, drift_furniture_retyped


LOPTEXT = "en tillräckligt lång rad brödtext för att inte räknas som cell"


def rad(typ, text="rad", y=0.5, h=0.014, x=0.07, w=0.42, region="sidbredd"):
    return {"type": typ, "text": text,
            "source": {"bbox": [x, y, w, h], "region": region}}


def prosasida(*extra):
    """En sida som classify_page räknar som löptext (tvåspaltig sats)."""
    els = []
    for i in range(14):
        els.append(rad("paragraph", "%s %d" % (LOPTEXT, i), y=0.9 - i * 0.02,
                       region="vänsterkolumn"))
        els.append(rad("paragraph", "%s %d" % (LOPTEXT, i), y=0.9 - i * 0.02,
                       x=0.52, region="högerkolumn"))
    return els + list(extra)


class TestUpphordTyp(unittest.TestCase):
    """`heading` och `boxed_text` upphörde mitt i del I utan att något larmade."""

    def _bok(self, sista_med_typ, antal=40, typ="boxed_text"):
        pages = []
        for no in range(1, antal + 1):
            extra = [rad(typ, "ruta")] if no <= sista_med_typ else []
            pages.append((no, prosasida(*extra)))
        return pages

    def test_typ_som_upphor_larmar(self):
        hits = drift_ceased_types(self._bok(10))
        self.assertEqual(len(hits), 1)
        self.assertIn("boxed_text", hits[0])
        self.assertIn("s. 10", hits[0])

    def test_typ_som_anvands_hela_boken_larmar_inte(self):
        self.assertEqual(drift_ceased_types(self._bok(40)), [])

    def test_kort_tystnad_larmar_inte(self):
        """Ett kapitel utan tabeller är inte drift."""
        self.assertEqual(drift_ceased_types(self._bok(36)), [])

    def test_enstaka_forekomst_larmar_inte(self):
        """En typ som bara använts på ett par sidor har ingen konvention."""
        self.assertEqual(drift_ceased_types(self._bok(2)), [])

    def test_tystnaden_raknas_i_loptextsidor(self):
        """Register och blanketter i slutet är inte bevis på drift.

        Nästan varje bok slutar med sidor utan exempelrutor. Räknas de med
        larmar regeln på alla böcker, och då är den värdelös.
        """
        # Fyra löptextsidor efter sista rutan — under tystnadsgränsen.
        pages = self._bok(10, antal=14)
        # Sedan tolv blankettsidor: många korta element, spridda x-lägen. Utan
        # löptextfiltret räcker de för att larma, och då larmar regeln på varje
        # bok som slutar med register eller rollformulär.
        for no in range(15, 27):
            korta = [rad("paragraph", "Typ: X", y=0.9 - i * 0.03,
                         x=0.05 + (i % 4) * 0.2, w=0.08) for i in range(12)]
            pages.append((no, korta))
        hits = drift_ceased_types(pages)
        self.assertEqual(hits, [])


class TestMoblemangByterTyp(unittest.TestCase):
    """Sidhuvudsdriften syns INTE på att en typ försvinner.

    Foliesiffrorna håller `page_artifact` vid liv på varje sida, så typen
    finns kvar hela boken igenom. Signalen är att samma sträng högst upp byter
    typ mitt i boken.
    """

    def _bok(self, byte_vid, antal=12, h_sidhuvud=0.013):
        pages = []
        for no in range(1, antal + 1):
            typ = "page_artifact" if no < byte_vid else "paragraph"
            topp = rad(typ, "FÄRDIGHETER", y=0.96, h=h_sidhuvud, w=0.12)
            pages.append((no, [topp] + prosasida()))
        return pages

    def test_sidhuvud_som_byter_typ_larmar(self):
        hits = drift_furniture_retyped(self._bok(7))
        self.assertEqual(len(hits), 1)
        self.assertIn("FÄRDIGHETER", hits[0])
        self.assertIn("page_artifact", hits[0])
        self.assertIn("paragraph", hits[0])

    def test_konsekvent_sidhuvud_larmar_inte(self):
        self.assertEqual(drift_furniture_retyped(self._bok(99)), [])

    def test_sektionstitel_i_egen_grad_ar_inte_drift(self):
        """Sektionens första sida bär titeln med samma lydelse som sidhuvudet.

        Där ÄR typskillnaden riktig, och skiljs de inte åt larmar regeln på
        varje sektionsöppning i boken. Det som skiljer dem är uppmätt grad:
        del I:s sidhuvuden mäter 0,010–0,015, sektionstitlarna 0,028–0,038.
        """
        pages = self._bok(99, antal=8)
        titel = rad("heading", "FÄRDIGHETER", y=0.92, h=0.037, w=0.70)
        pages[0] = (1, [titel] + prosasida())
        self.assertEqual(drift_furniture_retyped(pages), [])

    def test_for_fa_sidor_ar_inte_moblemang(self):
        self.assertEqual(drift_furniture_retyped(self._bok(2, antal=2)), [])


class TestBoknivako(unittest.TestCase):
    """Uppskjutna frågor måste ha en mottagare."""

    def setUp(self):
        self.wd = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.wd, ignore_errors=True)

    def _skriv(self, text):
        (self.wd / "beslut.md").write_text(text, encoding="utf-8")

    def test_tom_fil_ger_tom_ko(self):
        self.assertEqual(open_questions(self.wd), [])

    def test_obesvarad_och_besvarad_skiljs(self):
        self._skriv("# B\n\n## Öppen kö\n\n- [ ] BQ-001 Sidhuvudens typ?\n"
                    "- [x] BQ-002 Halvfyrkant i tabellvärden.\n")
        self.assertEqual(queue_items(self.wd), [
            ("BQ-001", "Sidhuvudens typ?", False),
            ("BQ-002", "Halvfyrkant i tabellvärden.", True)])
        self.assertEqual(open_questions(self.wd),
                         [("BQ-001", "Sidhuvudens typ?")])

    def test_punktlistor_utanfor_kon_raknas_inte(self):
        """Beslutsfilen är full av vanliga punktlistor — de är inga frågor."""
        self._skriv("# B\n\n## Avgjort\n\n- [ ] ser ut som en fråga\n"
                    "- en vanlig punkt\n")
        self.assertEqual(open_questions(self.wd), [])

    def test_enqueue_skapar_ko_och_ger_id(self):
        self._skriv("# B\n\n## Avgjort\n\n- något\n")
        qid = enqueue(self.wd, "Ska sidhuvuden vara page_artifact?")
        self.assertEqual(qid, "BQ-001")
        self.assertEqual(open_questions(self.wd),
                         [("BQ-001", "Ska sidhuvuden vara page_artifact?")])

    def test_enqueue_ar_idempotent_pa_texten(self):
        """Samma boknivåfråga stöts på av en advokat per sida."""
        a = enqueue(self.wd, "Samma fråga")
        b = enqueue(self.wd, "Samma  fråga")
        self.assertEqual(a, b)
        self.assertEqual(len(open_questions(self.wd)), 1)

    def test_nasta_id_hoppar_over_upptagna(self):
        self._skriv("## Öppen kö\n\n- [x] BQ-001 klar\n- [ ] BQ-007 öppen\n")
        self.assertEqual(next_id(self.wd), "BQ-008")

    def test_enqueue_behaller_efterfoljande_avsnitt(self):
        self._skriv("## Öppen kö\n\n- [ ] BQ-001 ett\n\n## Avgjort\n\n- text\n")
        enqueue(self.wd, "två")
        innehall = (self.wd / "beslut.md").read_text(encoding="utf-8")
        self.assertIn("- [ ] BQ-002 [beslut] två", innehall)
        self.assertIn("## Avgjort", innehall)
        self.assertLess(innehall.index("BQ-002"), innehall.index("## Avgjort"))


class TestOrdkonservering(unittest.TestCase):
    """Ett strukturingrepp får ändra formen, aldrig orden."""

    def setUp(self):
        self.wd = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.wd, ignore_errors=True)
        (self.wd / "export").mkdir()

    def _bok(self, text):
        (self.wd / "export" / "bok.md").write_text(text, encoding="utf-8")

    def test_ren_omflodning_ger_ingen_diff(self):
        self._bok("# T\n\nen rad\noch en till\n")
        freeze(self.wd)
        self._bok("# T\n\nen rad och en till\n")
        d = diff(self.wd)
        self.assertEqual(d["borta"], {})
        self.assertEqual(d["nya"], {})

    def test_forlorad_text_syns(self):
        self._bok("# T\n\nrad ett\nrad två\n")
        freeze(self.wd)
        self._bok("# T\n\nrad ett\n")
        self.assertEqual(diff(self.wd)["borta"], {"rad": 1, "två": 1})

    def test_markdownens_egna_tecken_raknas_inte(self):
        """Rubriker och citatblock tillkommer vid omtypning och är inte ord."""
        self.assertEqual(words("# Rubrik\n\n> citat | *kursiv*"),
                         words("Rubrik citat kursiv"))

    def test_frysning_kravs_innan_diff(self):
        self._bok("# T\n")
        with self.assertRaises(FileNotFoundError):
            diff(self.wd)


if __name__ == "__main__":
    unittest.main()


class TestDriftfamiljer(unittest.TestCase):
    """Två representationer av samma sak är ingen drift.

    Kontraktet tillåter en lista som ett `list` med alla punkter i
    `data.items` ELLER som en följd av `list_item`, och en tabell som `table`
    eller som reservformen `table_header`/`table_cell`. Räknas formerna var
    för sig larmar regeln på varje bok som byter representation mitt i.
    """

    def _bok(self, forsta_halvan, andra_halvan, antal=40):
        pages = []
        for no in range(1, antal + 1):
            typ = forsta_halvan if no <= antal // 2 else andra_halvan
            pages.append((no, prosasida(rad(typ, "punkt"))))
        return pages

    def test_byte_av_listform_larmar_inte(self):
        self.assertEqual(drift_ceased_types(self._bok("list", "list_item")), [])

    def test_byte_av_tabellform_larmar_inte(self):
        self.assertEqual(
            drift_ceased_types(self._bok("table", "table_cell")), [])

    def test_hela_familjen_som_upphor_larmar(self):
        pages = self._bok("list", "list_item")
        pages = [(no, [e for e in els
                       if e.get("type") not in ("list", "list_item")]
                  if no > 20 else els) for no, els in pages]
        hits = drift_ceased_types(pages)
        self.assertEqual(len(hits), 1)
        self.assertIn("list", hits[0])


class TestKapitelavdelare(unittest.TestCase):
    """En sida utan sats har inget löpande sidhuvud.

    Kapitelavdelaren bär bara kapitelnamnet, ofta med samma lydelse som
    sidhuvudet på sidorna efter — men som `heading`, vilket är rätt. Räknas
    den med larmar regeln på varje kapitelöppning (del III s. 3: `MAGI`).
    """

    def test_avdelarsida_drar_inte_in_sidhuvudet(self):
        pages = [(1, [rad("heading", "MAGI", y=0.90, h=0.0004, w=0.86)])]
        for no in range(2, 8):
            pages.append((no, [rad("page_artifact", "MAGI", y=0.95, h=0.010,
                                   w=0.29)] + prosasida()))
        self.assertEqual(drift_furniture_retyped(pages), [])


def _tab(eid, rows, headers=None, fortsattning=None):
    data = {"rows": rows, "headers": headers if headers is not None else []}
    if fortsattning:
        data["fortsattning_av"] = fortsattning
    return {"id": eid, "type": "table", "data": data}


def _par(eid, text="Ett stycke löptext som fortsätter."):
    return {"id": eid, "type": "paragraph", "text": text}


class TestSidbrutnaTabeller(unittest.TestCase):
    """BQ-011 (b): en tabell som bryts över en sidbrytning ska vara märkt."""

    def test_strukturell_signal(self):
        pages = [(41, [_tab("a", [["11", "x"]], ["1T20", "Effekt"])]),
                 (42, [_tab("b", [["12", "y"]])])]
        self.assertEqual(len(drift_split_tables(pages)), 1)

    def test_markt_fortsattning_larmar_inte(self):
        pages = [(41, [_tab("a", [["11", "x"]], ["1T20", "Effekt"])]),
                 (42, [_tab("b", [["12", "y"]], fortsattning="a")])]
        self.assertEqual(drift_split_tables(pages), [])

    def test_egen_rubrikrad_ar_en_ny_tabell(self):
        pages = [(46, [_tab("a", [["Öl", "4"]], ["Namn", "Pris"])]),
                 (47, [_tab("b", [["Sovsal", "10"]], ["Namn", "Pris per dygn"])])]
        self.assertEqual(drift_split_tables(pages), [])

    def test_nyckelfoljden_fangar_fortsattning_som_inte_star_forst(self):
        """s. 11 inleds med löptexten från s. 10 — tabellen kommer först sedan."""
        pages = [(10, [_tab("a", [["18", "x"], ["19", "y"]], ["Resultat", "Effekt"])]),
                 (11, [_par("p1"), _par("p2"), _tab("b", [["20", "z"]])])]
        träffar = drift_split_tables(pages)
        self.assertEqual(len(träffar), 1)
        self.assertIn("nyckelkolumnen fortsätter", träffar[0])

    def test_rubrikslos_etikettabell_med_namn_larmar_inte(self):
        """Bokens rubrikslösa etikett/värde-tabeller har namn, inte tal i följd."""
        pages = [(9, [_tab("a", [["1–5", "x"]], ["Slag", "Effekt"])]),
                 (10, [_par("p1"), _tab("b", [["Död kropp", "1"]])])]
        self.assertEqual(drift_split_tables(pages), [])


class TestKoklass(unittest.TestCase):
    """Kön skiljer `[beslut]` från `[verktyg]` — bara det förra blockerar.

    Regeln fanns i CLAUDE.md men var oframtvingad, och kön drev till en
    att-göra-lista: i del III var 24 av 27 poster verktygsarbete, och de
    blockerade boken lika hårt som de tre verkliga frågorna. Följden blev att
    användaren fick ta ställning till buggar i `pipeline/`.
    """

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def _skriv(self, *rader):
        (self.dir / "beslut.md").write_text(
            "## Öppen kö\n\n" + "\n".join(rader) + "\n", encoding="utf-8")

    def test_verktygspost_blockerar_inte(self):
        from pipeline.decisions import blocking_questions, tool_questions
        self._skriv("- [ ] BQ-001 [verktyg] Regeln mäter fel storhet.")
        self.assertEqual(blocking_questions(self.dir), [])
        self.assertEqual([q for q, _ in tool_questions(self.dir)], ["BQ-001"])

    def test_beslutspost_blockerar(self):
        from pipeline.decisions import blocking_questions
        self._skriv("- [ ] BQ-001 [beslut] Bevara tryckfelet eller emendera?")
        self.assertEqual([q for q, _ in blocking_questions(self.dir)], ["BQ-001"])

    def test_oklassad_post_blockerar(self):
        """Defaulten gör kön för sträng och aldrig för slapp."""
        from pipeline.decisions import blocking_questions
        self._skriv("- [ ] BQ-001 En gammal post utan klassmarkör.")
        self.assertEqual([q for q, _ in blocking_questions(self.dir)], ["BQ-001"])

    def test_klassmarkoren_visas_inte_i_lydelsen(self):
        from pipeline.decisions import tool_questions
        self._skriv("- [ ] BQ-001 [verktyg] Regeln mäter fel storhet.")
        self.assertEqual(tool_questions(self.dir)[0][1],
                         "Regeln mäter fel storhet.")

    def test_besvarad_post_raknas_inte(self):
        from pipeline.decisions import blocking_questions, tool_questions
        self._skriv("- [x] BQ-001 [beslut] Avgjord.",
                    "- [x] BQ-002 [verktyg] Lagad.")
        self.assertEqual(blocking_questions(self.dir), [])
        self.assertEqual(tool_questions(self.dir), [])

    def test_enqueue_skriver_klassen(self):
        from pipeline.decisions import CLASS_TOOL, enqueue, tool_questions
        enqueue(self.dir, "Regeln mäter fel storhet.", CLASS_TOOL)
        self.assertIn("[verktyg]",
                      (self.dir / "beslut.md").read_text(encoding="utf-8"))
        self.assertEqual(len(tool_questions(self.dir)), 1)

    def test_enqueue_vagrar_okand_klass(self):
        from pipeline.decisions import enqueue
        with self.assertRaises(ValueError):
            enqueue(self.dir, "En fråga.", "kanske")

    def test_arkivering_hindras_inte_av_verktygspost(self):
        """Kärnan: en bugg i pipelinen får aldrig hålla en färdig bok gisslan."""
        from pipeline.decisions import blocking_questions
        self._skriv("- [ ] BQ-001 [verktyg] Mätmotorn delar inte spalter.",
                    "- [ ] BQ-002 [verktyg] Regeln läser inte i celler.")
        self.assertEqual(blocking_questions(self.dir), [])


class TestPunkttecknetRaknasInteSomOrd(unittest.TestCase):
    """`•` är listans märke, inte bokens text.

    `scripts/punktrader.py` typar om en rad som börjar med punkttecken från
    `paragraph` till `list_item` — en RÄTTELSE, för som löptext fogas raden in
    i föregående stycke och listan försvinner som struktur. Markdownen skriver
    då `-` i stället för tryckets `•`, och diffen larmade för två borta ord i
    Edsbrytarna. Larmet var riktigt räknat och fel i sak, och ett instrument
    som fäller en korrekt omtypning lär användaren att bortse från det.
    """

    def test_punkttecken_och_bindestreck_ar_samma_ordmangd(self):
        self.assertEqual(words("• Handelshuset sålde lasten"),
                         words("- Handelshuset sålde lasten"))

    def test_orden_raknas_fortfarande(self):
        self.assertEqual(sum(words("• ett två tre").values()), 3)

    def test_bindestreck_inne_i_ord_vags_fortfarande(self):
        """Sammansättningar och talintervall bär betydelse och räknas."""
        self.assertEqual(words("halv-elva 3-5 x"),
                         words("halv-elva 3-5 x"))
        self.assertIn("halv-elva", words("halv-elva"))
        self.assertIn("3-5", words("3-5"))
