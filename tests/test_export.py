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

    def test_toc_entries_are_never_reflowed(self):
        """En innehållspost är en rad; fogas de ihop förstörs uppställningen."""
        md = self.render([line("e01", "Rollpersonen 5", etype="toc_entry"),
                          line("e02", "Färdigheter 40", etype="toc_entry")])
        self.assertIn("Rollpersonen 5\n\nFärdigheter 40", md)

    def test_lines_without_geometry_are_left_alone(self):
        """Utan bbox finns inget facit — då fogas ingenting ihop."""
        md = self.render([{"id": "e01", "type": "paragraph", "text": "Ett."},
                          {"id": "e02", "type": "paragraph", "text": "Två."}])
        self.assertIn("Ett.\n\nTvå.", md)


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
