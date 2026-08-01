#!/usr/bin/env python3
"""Montera förbesiktningens `tabellkandidat`-rutnät till riktiga `table`.

Användning:
    python3 scripts/tabellkandidat.py <slug>                 # visa förslagen
    python3 scripts/tabellkandidat.py <slug> --verkstall     # skriv dem

`pipeline/forbesikta` HITTAR tryckta tabeller som transkriberats som en följd
av `paragraph` men rättar dem aldrig — en feltypad tabell är ett typningsfel,
och typningen avgörs mot sidbilden. Det här skriptet gör den mekaniska halvan
av den rättningen: där rutnätet är en FULLSTÄNDIG rektangel (varje rad har
exakt en cell i varje kolumn) är radindelningen inte en tolkning utan en
uppmätning, och den kan monteras deterministiskt.

Ragged rutnät monteras aldrig. De rapporteras som `ojämn` och lämnas åt
advokaten — hellre en flagga kvar än en tabell med gissade celler.

Rubrikraden tas bara med när raden närmast ovanför blocket har lika många
korta element i samma kolumnlägen. Saknas den skrivs tomma strängar, aldrig
påhittade rubriker (extrahera/SKILL.md §Tabeller).
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.manifest import Manifest, page_file, read_json  # noqa: E402
from pipeline.preflight import (TABLE_CELL_MAX_TEXT, TABLE_ROW_TOLERANCE,  # noqa: E402
                                _bbox, _median, _region, _x_clusters,
                                _cluster_of, _y_rows, table_blocks)

SOURCE = "skript:tabellkandidat"


def _grid(members):
    """(kolumnlägen, rader av celler) för blockets element.

    Samma klustring och radgruppering som förbesiktningen — annars kan
    monteringen se ett annat rutnät än det som flaggades.
    """
    boxes = {id(el): _bbox(el) for el in members}
    clusters = _x_clusters([boxes[id(el)][0] for el in members])
    med_h = _median([boxes[id(el)][3] for el in members])
    rows = _y_rows([(boxes[id(el)][1], el, _cluster_of(clusters, boxes[id(el)][0]))
                    for el in members],
                   max(med_h * TABLE_ROW_TOLERANCE, 0.004))
    out = []
    for row in rows:
        cells = {}
        for _y, el, ci in row:
            if ci in cells:          # två celler i samma kolumn -> ojämn
                return clusters, None
            cells[ci] = el
        out.append(cells)
    return clusters, out


def _rectangle(clusters, rows):
    """Cellrader om rutnätet är en fullständig rektangel, annars None."""
    if not rows:
        return None
    used = sorted({ci for row in rows for ci in row})
    for row in rows:
        if sorted(row) != used:
            return None
    return [[row[ci] for ci in used] for row in rows], used


def _header_row(elements, members, used, clusters):
    """Elementen i raden närmast ovanför blocket, om den har samma form."""
    first = members[0]
    index = elements.index(first)
    region, box = _region(first), _bbox(first)
    med_h = box[3]
    above = []
    for el in reversed(elements[:index]):
        b = _bbox(el)
        text = (el.get("text") or "").strip()
        if not b or not text or _region(el) != region:
            break
        if len(text) > TABLE_CELL_MAX_TEXT:
            break
        if b[1] - box[1] > 4 * med_h:     # för långt upp — egen rubrik
            break
        above.append(el)
    if len(above) != len(used):
        return None
    above.reverse()
    order = [_cluster_of(clusters, _bbox(el)[0]) for el in above]
    if None in order or sorted(order) != sorted(order):
        # Rubrikcellerna sitter ofta något annorlunda i sidled än cellerna
        # under; kravet är bara att de kommer i samma ordning vänster->höger.
        return None
    return above


def propose(workdir, page_no):
    data = read_json(page_file(workdir, page_no, "final.json"))
    elements = data["elements"]
    out = []
    for block in table_blocks(elements):
        members = [el for el in elements if el.get("id") in set(block["ids"])]
        members.sort(key=lambda el: block["ids"].index(el.get("id")))
        clusters, rows = _grid(members)
        rect = _rectangle(clusters, rows) if rows else None
        if rect is None:
            out.append({"page": page_no, "anchor": block["ids"][0],
                        "status": "ojämn", "columns": block["columns"],
                        "rows": block["rows"], "ids": block["ids"]})
            continue
        cells, used = rect
        header = _header_row(elements, members, used, clusters)
        out.append({"page": page_no, "anchor": block["ids"][0],
                    "status": "rektangel", "columns": len(used),
                    "cells": cells, "header": header, "ids": block["ids"]})
    return data, out


def assemble(data, plan):
    """Skriv om ett rektangulärt block till ETT table-element."""
    cells, header = plan["cells"], plan["header"] or []
    members = [el for row in cells for el in row] + list(header)
    ids = [el.get("id") for el in members]
    head = members[0] if not header else header[0]
    rows = [[(el.get("text") or "").strip() for el in row] for row in cells]
    headers = [(el.get("text") or "").strip() for el in header] \
        or [""] * plan["columns"]
    boxes = [_bbox(el) for el in members]
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    table = {
        "type": "table",
        "data": {"headers": headers, "rows": rows},
        "confidence": min(el.get("confidence", 1.0) for el in members),
        "source": {
            "region": _region(head),
            "merged_from": ids,
            "bbox": [round(x0, 5), round(y0, 5),
                     round(max(b[0] + b[2] for b in boxes) - x0, 5),
                     round(max(b[1] + b[3] for b in boxes) - y0, 5)],
            "bbox_source": "pipeline.rows (union %s–%s)" % (ids[0], ids[-1]),
        },
        "id": head.get("id"),
        "corrections": [c for el in members for c in el.get("corrections") or []
                        if c.get("applied")] + [{
            "original": "%d paragraph-element (%s–%s) i ett radvist rutnät"
                        % (len(ids), ids[0], ids[-1]),
            "corrected": "ETT table-element, %d kolumner × %d rader"
                         % (len(headers), len(rows)),
            "confidence": 0.95,
            "reason": (
                "Typningsfel, aldrig en korrektionspost i sak: det tryckta "
                "partiet ÄR en tabell. Förbesiktningens `tabellkandidat` "
                "flaggade rutnätet och monteringen är deterministisk — "
                "cellernas vänsterkanter faller i %d täta x-kluster som "
                "återkommer i varenda rad, och varje rad har exakt en cell "
                "i varje kolumn. Ingen celltext är ändrad, tillagd eller "
                "borttagen; bara elementgränserna. %s"
                % (len(headers),
                   "Rubrikraden är tryckt och ligger direkt ovanför rutnätet."
                   if header else
                   "Ingen tryckt rubrikrad finns ovanför rutnätet, så "
                   "`headers` är tom i stället för påhittad.")),
            "source": SOURCE,
            "applied": True,
            "kind": "ocr",
        }],
    }
    keep = []
    for el in data["elements"]:
        if el.get("id") == head.get("id"):
            keep.append(table)
        elif el.get("id") not in set(ids):
            keep.append(el)
    data["elements"] = keep
    return table


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug")
    parser.add_argument("--verkstall", action="store_true")
    args = parser.parse_args(argv)
    workdir = ROOT / "arbete" / args.slug
    manifest = Manifest.load(workdir)
    n_ok = n_ragged = 0
    for page_no in manifest.page_numbers():
        if not page_file(workdir, page_no, "final.json").is_file():
            continue
        data, plans = propose(workdir, page_no)
        touched = False
        for plan in plans:
            if plan["status"] != "rektangel":
                n_ragged += 1
                print("s.%-3d %-11s OJÄMN %d×%d — lämnas åt advokaten"
                      % (page_no, plan["anchor"], plan["columns"],
                         plan["rows"]))
                continue
            n_ok += 1
            head = [(el.get("text") or "") for el in (plan["header"] or [])]
            print("s.%-3d %-11s %d kolumner × %d rader  rubrik=%s"
                  % (page_no, plan["anchor"], plan["columns"],
                     len(plan["cells"]), head or "(ingen tryckt)"))
            for row in plan["cells"][:3]:
                print("        | %s |" % " | ".join(
                    (el.get("text") or "").strip() for el in row))
            if len(plan["cells"]) > 3:
                print("        … %d rader till" % (len(plan["cells"]) - 3))
            if args.verkstall:
                assemble(data, plan)
                touched = True
        if touched:
            path = page_file(workdir, page_no, "final.json")
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2)
                            + "\n", encoding="utf-8")
    print("%d rektangulära block, %d ojämna" % (n_ok, n_ragged))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
