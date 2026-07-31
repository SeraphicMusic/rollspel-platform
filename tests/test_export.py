"""Tester för läsexportens elementrendering.

Bakgrund: exportören hade en tyst catch-all som renderade varje okänd
elementtyp som ett eget stycke. Grundregelbokens tabellceller föll därför ut
som en rad per cell utan att något syntes i loggen.
"""
import json
import tempfile
import unittest
from pathlib import Path

from pipeline.export import export_markdown


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

    def test_genuinely_unknown_type_is_kept_and_warned(self):
        md = self.render([
            {"id": "e01", "type": "nyuppfunnen_typ", "text": "Viktigt värde"},
        ])
        self.assertIn("Viktigt värde", md)


if __name__ == "__main__":
    unittest.main()
