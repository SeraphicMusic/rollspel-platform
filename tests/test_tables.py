"""Tester för deterministisk montering av lösa tabellceller."""
import unittest

from pipeline import tables


def cell(eid, text, kind="table_cell"):
    return {"id": eid, "type": kind, "text": text}


def header(eid, text):
    return cell(eid, text, "table_header")


def _mät(eid, text, x, y, kind="table_cell", bredd=0.06):
    """Cell med uppmätt bbox. y räknas från sidans nederkant."""
    e = cell(eid, text, kind)
    e["source"] = {"bbox": [x, y, bredd, 0.014]}
    return e


def _krav_block():
    """Två rader ur tabellen över grundegenskapskrav (s. 12), med `Lärd man`
    gles: yrket har krav på STY men inte på FYS. Lägena är de uppmätta."""
    return [_mät("h1", "Yrke", 0.195, 0.308, "table_header"),
            _mät("h2", "STY", 0.320, 0.308, "table_header"),
            _mät("h3", "FYS", 0.396, 0.308, "table_header"),
            _mät("r1a", "Krigare", 0.195, 0.260),
            _mät("r1b", "14", 0.326, 0.262),
            _mät("r1c", "12", 0.400, 0.263),
            _mät("r2a", "Lärd man", 0.195, 0.245),
            _mät("r2b", "16", 0.326, 0.246)]


class TestAssemble(unittest.TestCase):
    def test_even_block_becomes_table(self):
        elements = [
            {"id": "e01", "type": "paragraph", "text": "Före tabellen."},
            header("e02", "Ras"), header("e03", "Kostnad i BP"),
            cell("e04", "Alv"), cell("e05", "25"),
            cell("e06", "Anka"), cell("e07", "0"),
            {"id": "e08", "type": "paragraph", "text": "Efter tabellen."},
        ]
        out, report = tables.assemble(elements, page=10)
        table = [e for e in out if e["type"] == "table"]
        self.assertEqual(len(table), 1)
        self.assertEqual(table[0]["data"]["headers"], ["Ras", "Kostnad i BP"])
        self.assertEqual(table[0]["data"]["rows"],
                         [["Alv", "25"], ["Anka", "0"]])
        self.assertEqual([r["status"] for r in report], ["assembled"])
        # Brödtexten runt om ligger kvar i läsordning.
        kept = [e["id"] for e in out if not e.get("removed")]
        self.assertEqual(kept[0], "e01")
        self.assertEqual(kept[-1], "e08")

    def test_consumed_cells_are_kept_but_removed(self):
        """Inget kastas — den omonterade läsningen finns kvar för spårbarhet."""
        elements = [header("e01", "A"), header("e02", "B"),
                    cell("e03", "1"), cell("e04", "2")]
        out, _ = tables.assemble(elements)
        consumed = [e for e in out if e["type"] in tables.CELL_TYPES]
        self.assertEqual(len(consumed), 4)
        self.assertTrue(all(e["removed"] for e in consumed))
        table = next(e for e in out if e["type"] == "table")
        self.assertEqual(table["source"]["merged_from"],
                         ["e01", "e02", "e03", "e04"])
        self.assertTrue(all(e["source"]["merged_into"] == table["id"]
                            for e in consumed))

    def test_uneven_block_is_left_alone(self):
        """Gles tabell med rubrikgrupp (sida 12) får inte gissas ihop."""
        elements = [header("e%02d" % i, "H%d" % i) for i in range(1, 10)]
        elements += [cell("c%02d" % i, str(i)) for i in range(1, 34)]
        out, report = tables.assemble(elements, page=12)
        self.assertEqual([e["type"] for e in out if e["type"] == "table"], [])
        self.assertEqual(report[0]["status"], "skipped")
        self.assertIn("går inte jämnt upp", report[0]["reason"])
        self.assertFalse(any(e.get("removed") for e in out))

    def test_single_header_is_not_enough(self):
        out, report = tables.assemble(
            [header("e01", "Bara en"), cell("e02", "x"), cell("e03", "y")])
        self.assertEqual(report[0]["status"], "skipped")
        self.assertIn("kolumnantalet", report[0]["reason"])
        self.assertEqual([e["type"] for e in out if e["type"] == "table"], [])

    def test_headers_without_cells_are_skipped(self):
        out, report = tables.assemble([header("e01", "A"), header("e02", "B")])
        self.assertEqual(report[0]["status"], "skipped")
        self.assertEqual([e["type"] for e in out if e["type"] == "table"], [])

    def test_two_separate_blocks_give_two_tables(self):
        elements = [
            header("a1", "A"), header("a2", "B"),
            cell("a3", "1"), cell("a4", "2"),
            {"id": "mid", "type": "heading", "text": "Mellanrubrik"},
            header("b1", "C"), header("b2", "D"),
            cell("b3", "3"), cell("b4", "4"),
        ]
        out, report = tables.assemble(elements)
        made = [e for e in out if e["type"] == "table"]
        self.assertEqual(len(made), 2)
        self.assertNotEqual(made[0]["id"], made[1]["id"])
        self.assertEqual([r["status"] for r in report],
                         ["assembled", "assembled"])

    def test_assembled_table_is_flagged_for_review(self):
        """Spelvärden ska stickprovskontrolleras — raderna bygger på läsordning."""
        out, _ = tables.assemble(
            [header("e01", "A"), header("e02", "B"),
             cell("e03", "1"), cell("e04", "2")])
        table = next(e for e in out if e["type"] == "table")
        self.assertTrue(table["needs_review"])
        self.assertTrue(table["review_reasons"])

    def test_short_row_is_assembled_from_geometry(self):
        """Sida 12: en GLES rad monteras med tom ruta i stället för att skippas.

        Tabellen över grundegenskapskrav har 33 celler på 9 rubriker och gick
        aldrig jämnt upp — en sekventiell påfyllning kan inte veta vilka rutor
        som är tomma. Bboxen vet: kolumnen läses ur cellens x-läge.
        """
        out, report = tables.assemble(_krav_block(), page=12)
        table = next(e for e in out if e["type"] == "table")
        self.assertEqual(report[0]["status"], "assembled")
        self.assertEqual(table["source"]["assembly_method"], "geometri")
        self.assertEqual(table["data"]["headers"], ["Yrke", "STY", "FYS"])
        self.assertEqual(table["data"]["rows"],
                         [["Krigare", "14", "12"], ["Lärd man", "16", ""]])

    def test_empty_cells_are_flagged_not_glossed_over(self):
        """Tom i trycket eller tappad av transkriptionen syns inte i geometrin."""
        out, _ = tables.assemble(_krav_block(), page=12)
        table = next(e for e in out if e["type"] == "table")
        skäl = " ".join(table["review_reasons"])
        self.assertIn("1 av 6 rutor är tomma", skäl)
        self.assertIn("rad 2 ’Lärd man’ saknar FYS", skäl)
        self.assertIn("TAPPAT", skäl)

    def test_spanning_header_is_not_a_column(self):
        """`Grundegenskapskrav` står över STY…FYS och blir ingen egen kolumn."""
        block = _krav_block()
        block.insert(3, _mät("h4", "Grundegenskapskrav", 0.307, 0.321,
                             "table_header", bredd=0.174))
        out, _ = tables.assemble(block, page=12)
        table = next(e for e in out if e["type"] == "table")
        self.assertEqual(table["data"]["headers"], ["Yrke", "STY", "FYS"])
        self.assertEqual(table["data"]["spans"],
                         [{"label": "Grundegenskapskrav",
                           "columns": ["STY", "FYS"]}])
        self.assertTrue(any("Spännrubriken" in r
                            for r in table["review_reasons"]))

    def test_two_cells_in_one_slot_falls_back_instead_of_guessing(self):
        """Tvetydig geometri gissas aldrig ihop — då gäller läsordningen."""
        block = _krav_block()
        block.append(_mät("r2c", "99", 0.326, 0.246))  # andra cellen i STY
        out, report = tables.assemble(block, page=12)
        table = next(e for e in out if e["type"] == "table")
        self.assertEqual(report[0]["status"], "assembled")
        self.assertEqual(table["source"]["assembly_method"], "läsordning")

    def test_contradictory_geometry_is_reported_not_swallowed(self):
        """Bbox som motsäger sig själv är ett eget fynd, inte en tyst fallback.

        Går läsordningen jämnt ut monteras tabellen ändå — men att MÄTNINGEN
        inte gick ihop får inte försvinna, för det är signaturen för
        `bbox-felkoppling`.
        """
        block = _krav_block()
        block.append(_mät("r2c", "99", 0.326, 0.246))
        out, _ = tables.assemble(block, page=12)
        table = next(e for e in out if e["type"] == "table")
        skäl = " ".join(table["review_reasons"])
        self.assertIn("hamnar i samma ruta", skäl)
        self.assertIn("bbox-felkoppling", skäl)

    def test_cell_outside_every_column_falls_back(self):
        """En cell långt utanför axeln betyder att mätningen inte går ihop."""
        block = _krav_block()
        block.append(_mät("strö", "7", 0.90, 0.245))
        out, _ = tables.assemble(block, page=12)
        table = next(e for e in out if e["type"] == "table")
        self.assertEqual(table["source"]["assembly_method"], "läsordning")
        self.assertIn("ligger inte under någon kolumn",
                      " ".join(table["review_reasons"]))

    def test_short_row_is_named_when_geometry_cannot_be_used(self):
        """Utan användbar geometri pekas den avvikande raden fortfarande ut."""
        block = [_mät("h1", "Yrke", 0.195, 0.308, "table_header"),
                 _mät("h2", "STY", 0.320, 0.308, "table_header"),
                 _mät("h3", "FYS", 0.396, 0.308, "table_header"),
                 _mät("r1a", "Krigare", 0.195, 0.260),
                 _mät("r1b", "14", 0.326, 0.262),
                 _mät("r1c", "12", 0.400, 0.263),
                 _mät("r1d", "99", 0.326, 0.261),   # krockar med r1b
                 _mät("r2a", "Lärd man", 0.195, 0.245),
                 _mät("r2b", "16", 0.326, 0.246),
                 _mät("r2c", "11", 0.400, 0.246)]
        _, report = tables.assemble(block, page=12)
        self.assertEqual(report[0]["status"], "skipped")
        self.assertIn("rad 1 ’Krigare’ har 4 av 3 celler", report[0]["reason"])
        self.assertIn("hamnar i samma ruta", report[0]["reason"])

    def test_short_row_without_bbox_falls_back_to_sequence(self):
        """Utan bbox går bara den sista, ofullständiga gruppen att namnge."""
        elements = [header("h1", "Ras"), header("h2", "Kostnad"),
                    cell("c1", "Alv"), cell("c2", "25"),
                    cell("c3", "Dvärg")]
        _, report = tables.assemble(elements)
        self.assertIn("rad 2 ’Dvärg’ har 1 av 2 celler", report[0]["reason"])

    def test_book_without_cells_is_untouched(self):
        elements = [{"id": "e01", "type": "paragraph", "text": "Bara text."}]
        out, report = tables.assemble(elements)
        self.assertEqual(out, elements)
        self.assertEqual(report, [])


if __name__ == "__main__":
    unittest.main()


class TestSpannrubrikensKolumner(unittest.TestCase):
    """BQ-017: en centrerad grupprubrik täcker inte sitt blocks ändkolumner.

    Mätt på del III s. 25: `Grundegenskapskrav` har bläck x 498–786 medan
    kolumnblocket STY–STO spänner 324–846, så bläckets överlappning ensam
    namnger fem av sju kolumner. Påståendet hamnar i `bok.json` och i
    granskningsrapportens kontrollfråga, och är då osant om trycket.
    """

    def _yrkestabell(self):
        # Radetikettkolumn + sju grundegenskapskolumner, mätta som på s. 25.
        kolumner = ["STY", "FYS", "SMI", "INT", "PSY", "KAR", "STO"]
        bredd = (0.846 - 0.324) / len(kolumner)
        headers = [_mät("h0", "Yrke", 0.10, 0.90, "table_header", 0.20)]
        for i, namn in enumerate(kolumner):
            headers.append(_mät("h%d" % (i + 1), namn, 0.324 + i * bredd,
                                0.90, "table_header", bredd * 0.8))
        # Spännrubriken står ett band ovanför och är centrerad över blocket.
        headers.append(_mät("hs", "Grundegenskapskrav", 0.498, 0.92,
                            "table_header", 0.786 - 0.498))
        return headers

    def test_centrerad_spannrubrik_far_hela_blocket(self):
        columns, spans = tables._column_axis(self._yrkestabell())
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0]["label"], "Grundegenskapskrav")
        self.assertEqual(spans[0]["columns"],
                         ["STY", "FYS", "SMI", "INT", "PSY", "KAR", "STO"])

    def test_radetikettkolumnen_ingar_aldrig(self):
        _, spans = tables._column_axis(self._yrkestabell())
        self.assertNotIn("Yrke", spans[0]["columns"])

    def test_tva_spannrubriker_delar_blocket_och_fyller_bara_sitt_intervall(self):
        """Delar två rubriker på bandet är intervallfyllnaden allt vi vet."""
        headers = self._yrkestabell()
        bredd = (0.846 - 0.324) / 7
        headers[-1] = _mät("hs1", "Fysiska", 0.330, 0.92,
                           "table_header", 2.2 * bredd)
        headers.append(_mät("hs2", "Mentala", 0.324 + 4.1 * bredd, 0.92,
                            "table_header", 2.2 * bredd))
        _, spans = tables._column_axis(headers)
        self.assertEqual([s["label"] for s in spans], ["Fysiska", "Mentala"])
        self.assertEqual(spans[0]["columns"], ["STY", "FYS", "SMI"])
        self.assertEqual(spans[1]["columns"], ["PSY", "KAR", "STO"])
