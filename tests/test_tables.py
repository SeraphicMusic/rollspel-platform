"""Tester för deterministisk montering av lösa tabellceller."""
import unittest

from pipeline import tables


def cell(eid, text, kind="table_cell"):
    return {"id": eid, "type": kind, "text": text}


def header(eid, text):
    return cell(eid, text, "table_header")


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

    def test_book_without_cells_is_untouched(self):
        elements = [{"id": "e01", "type": "paragraph", "text": "Bara text."}]
        out, report = tables.assemble(elements)
        self.assertEqual(out, elements)
        self.assertEqual(report, [])


if __name__ == "__main__":
    unittest.main()
