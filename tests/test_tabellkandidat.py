"""Montering av förbesiktningens tabellkandidat-rutnät till riktiga `table`."""
import unittest

from scripts.tabellkandidat import _grid, _rectangle, assemble


def cell(eid, text, x, y, w=0.08, h=0.010):
    return {"type": "paragraph", "text": text, "id": eid, "confidence": 0.97,
            "source": {"region": "vänsterkolumn", "bbox": [x, y, w, h]}}


def rutnat(rows, columns=(0.11, 0.37)):
    """Element i läsordning för ett radvist rutnät. y räknas från nederkanten."""
    out = []
    for r, row in enumerate(rows):
        y = 0.80 - r * 0.02
        for c, text in enumerate(row):
            if text is None:
                continue
            out.append(cell("p001_e%02d" % len(out), text, columns[c], y))
    return out


class TestRutnat(unittest.TestCase):
    def test_fullstandig_rektangel_monteras(self):
        members = rutnat([["Avväpning", "1,0"], ["Bakåtspark", "0,5"],
                          ["Blind strid", "2,0"]])
        clusters, rows = _grid(members)
        result = _rectangle(clusters, rows)
        self.assertIsNotNone(result)
        cells, used = result
        self.assertEqual(len(used), 2)
        self.assertEqual([[el["text"] for el in row] for row in cells],
                         [["Avväpning", "1,0"], ["Bakåtspark", "0,5"],
                          ["Blind strid", "2,0"]])

    def test_rad_med_lucka_monteras_aldrig(self):
        """Hellre en flagga kvar åt advokaten än en tabell med gissade celler."""
        members = rutnat([["Avväpning", "1,0"], ["Bakåtspark", None],
                          ["Blind strid", "2,0"]])
        clusters, rows = _grid(members)
        self.assertIsNone(_rectangle(clusters, rows))

    def test_tva_celler_i_samma_kolumn_ar_inget_rutnat(self):
        members = rutnat([["Avväpning", "1,0"], ["Bakåtspark", "0,5"]])
        members.append(cell("p001_e99", "extra", 0.11, 0.78))
        clusters, rows = _grid(members)
        self.assertIsNone(rows)


class TestMontering(unittest.TestCase):
    def plan(self, members, header=None):
        clusters, rows = _grid(members)
        cells, _used = _rectangle(clusters, rows)
        return {"anchor": members[0]["id"], "status": "rektangel",
                "columns": 2, "cells": cells, "header": header,
                "ids": [el["id"] for el in members]}

    def test_utan_tryckt_rubrikrad_blir_headers_tomma(self):
        members = rutnat([["Skog", "+2"], ["Högt gräs", "+2"],
                          ["Buskar", "+1"]])
        data = {"elements": list(members)}
        table = assemble(data, self.plan(members))
        self.assertEqual(table["data"]["headers"], ["", ""])
        self.assertEqual(len(table["data"]["rows"]), 3)
        self.assertEqual(len(data["elements"]), 1)

    def test_applicerade_korrektioner_foljer_med(self):
        """Annars faller de ur granskningsrapportens spårbarhet."""
        members = rutnat([["Skog", "+2"], ["Högt gräs", "+2"],
                          ["Buskar", "+1"]])
        members[0]["corrections"] = [
            {"original": "Skag", "corrected": "Skog", "applied": True,
             "kind": "ocr", "confidence": 0.9, "reason": "…", "source": "x"},
            {"original": "förslag", "corrected": "avvisat", "applied": False,
             "kind": "emendering", "confidence": 0.4, "reason": "…",
             "source": "x"}]
        data = {"elements": list(members)}
        table = assemble(data, self.plan(members))
        carried = [c["original"] for c in table["corrections"]]
        self.assertIn("Skag", carried)
        # Ett oapplicerat förslag hör till raden, inte till tabellen.
        self.assertNotIn("förslag", carried)

    def test_bbox_ar_unionen_inte_en_gissning(self):
        members = rutnat([["Skog", "+2"], ["Buskar", "+1"]])
        data = {"elements": list(members)}
        table = assemble(data, self.plan(members))
        x, y, w, h = table["source"]["bbox"]
        self.assertAlmostEqual(x, 0.11, places=3)
        self.assertAlmostEqual(x + w, 0.45, places=3)
        self.assertAlmostEqual(y, 0.78, places=3)
        self.assertAlmostEqual(y + h, 0.81, places=3)

    def test_tryckt_rubrikrad_hamnar_i_headers(self):
        members = rutnat([["Mjukt", "+5"], ["Medium", "±0"]])
        header = [cell("p001_h0", "Underlag", 0.11, 0.84),
                  cell("p001_h1", "CL-modifikation", 0.37, 0.84)]
        data = {"elements": header + list(members)}
        table = assemble(data, self.plan(members, header))
        self.assertEqual(table["data"]["headers"],
                         ["Underlag", "CL-modifikation"])
        self.assertEqual(table["id"], "p001_h0")
        self.assertEqual(data["elements"], [table])


if __name__ == "__main__":
    unittest.main()
