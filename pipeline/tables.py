"""Montering av lösa tabellceller till riktiga tabellelement.

Transkriptionen av vissa böcker (grundregelboken) lägger tabeller som en följd
av `table_header`- och `table_cell`-element i läsordning i stället för ett
`table`-element med `headers`/`rows`. Innehållet är korrekt läst men saknar
struktur, vilket gjorde att läsexporten skrev en rad per cell.

Monteringen är rent deterministisk (AGENTER.md Regel 5 — skript före LLM):
kolumnantalet ges av antalet `table_header` i följd, och cellerna fylls
radvis. Går det inte jämnt ut monteras ingenting — då saknas celler eller finns
rubrikgrupper, och det kräver mänsklig granskning i stället för en gissning.
"""

CELL_TYPES = ("table_header", "table_cell")

# Hur nära i y två celler måste ligga för att räknas till samma tryckta rad,
# som andel av cellernas medianhöjd. Samma mått som i pipeline/preflight.py:
# uppmätt spridning inom en rad är 0,002–0,005 mot ett radavstånd på ~0,015.
ROW_TOLERANCE = 0.6


def _text(element):
    return (element.get("text") or "").strip()


def _bbox(element):
    box = (element.get("source") or {}).get("bbox")
    if isinstance(box, (list, tuple)) and len(box) == 4:
        try:
            return [float(v) for v in box]
        except (TypeError, ValueError):
            return None
    return None


def _median(values):
    vals = sorted(values)
    if not vals:
        return None
    mid = len(vals) // 2
    if len(vals) % 2:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2


def _rows_by_geometry(cells):
    """Dela cellerna i tryckta rader efter bbox-y, eller None om bbox saknas.

    y räknas från sidans NEDERKANT, så raderna kommer i läsordning när man
    sorterar fallande. Radens referens är dess ÖVERSTA cell.
    """
    boxes = [(cell, _bbox(cell)) for cell in cells]
    if any(box is None for _, box in boxes):
        return None
    tolerance = max(_median([box[3] for _, box in boxes]) * ROW_TOLERANCE,
                    0.004)
    rows, ref = [], None
    for cell, box in sorted(boxes, key=lambda t: -t[1][1]):
        if ref is None or ref - box[1] > tolerance:
            rows.append([])
            ref = box[1]
        rows[-1].append((box[0], cell))
    # Inom raden är läsordningen vänster till höger, inte fallande y — annars
    # blir radens etikett en godtycklig värdecell i stället för dess första
    # kolumn ("rad 2 ’12’" i stället för "rad 2 ’Helare’").
    return [[cell for _, cell in sorted(row, key=lambda t: t[0])]
            for row in rows]


def _row_diagnosis(cells, columns):
    """Vilken rad som är kort — annars måste felet räknas fram för hand.

    Med bbox går raderna att läsa direkt ur geometrin, och då pekas varje rad
    som avviker från kolumnantalet ut med sin egen etikett (första cellens
    text). Saknas bbox delas cellerna sekventiellt i kolumnbreda grupper, och
    då är det den sista, ofullständiga gruppen som går att namnge.
    """
    rows = _rows_by_geometry(cells)
    if rows is None:
        rows = [cells[i:i + columns] for i in range(0, len(cells), columns)]
        korta = [(i, row) for i, row in enumerate(rows) if len(row) != columns]
    else:
        korta = [(i, row) for i, row in enumerate(rows) if len(row) != columns]
    if not korta:
        return "", []
    detalj = []
    for i, row in korta:
        detalj.append({"row": i + 1, "cells": len(row),
                       "label": _text(row[0]) or "(tom)",
                       "ids": [c.get("id") for c in row]})
    visade = "; ".join(
        "rad %d ’%s’ har %d av %d celler (%s)"
        % (d["row"], d["label"], d["cells"], columns, ", ".join(d["ids"]))
        for d in detalj[:6])
    if len(detalj) > 6:
        visade += "; … och %d rader till" % (len(detalj) - 6)
    return visade, detalj


def _runs(elements):
    """Dela upp elementlistan i (är_celler, [element])-block i läsordning."""
    blocks = []
    for element in elements:
        is_cell = (element.get("type") in CELL_TYPES
                   and not element.get("removed"))
        if blocks and blocks[-1][0] == is_cell:
            blocks[-1][1].append(element)
        else:
            blocks.append((is_cell, [element]))
    return blocks


def assemble(elements, page=None):
    """Returnera (nya_element, rapportposter) med cellblock monterade.

    Konsumerade celler behålls i listan med `removed: true` — inget kastas, så
    den omonterade läsningen finns kvar för spårbarhet. Ett block som inte går
    jämnt ut lämnas orört och rapporteras som `skipped`.
    """
    out, report = [], []
    counter = 0
    for is_cell, block in _runs(elements):
        if not is_cell:
            out.extend(block)
            continue
        headers = [e for e in block if e.get("type") == "table_header"]
        cells = [e for e in block if e.get("type") == "table_cell"]
        columns = len(headers)
        reason, rader = None, []
        if columns < 2:
            reason = ("hittade %d rubrik(er) — kolumnantalet går inte att "
                      "härleda" % columns)
        elif not cells:
            reason = "rubriker utan celler"
        elif len(cells) % columns:
            visade, rader = _row_diagnosis(cells, columns)
            reason = ("%d celler går inte jämnt upp på %d kolumner "
                      "(rubrikgrupper eller saknade celler)"
                      % (len(cells), columns))
            if visade:
                reason += ". Avvikande rader: " + visade
        if reason:
            out.extend(block)
            report.append({"status": "skipped", "page": page,
                           "ids": [e.get("id") for e in block],
                           "reason": reason, "rows": rader})
            continue
        rows = [[_text(c) for c in cells[i:i + columns]]
                for i in range(0, len(cells), columns)]
        counter += 1
        consumed = [e.get("id") for e in block]
        table = {
            "id": "%s_tbl%02d" % (headers[0].get("id", "tabell"), counter),
            "type": "table",
            "text": "",
            "data": {"headers": [_text(h) for h in headers], "rows": rows},
            "source": {"merged_from": consumed,
                       "assembled_by": "pipeline.tables.assemble"},
            # Spelvärden i en grundregelbok ska stickprovskontrolleras mot
            # PNG:n innan exporten används som facit (Regel 8a: siffror rättas
            # aldrig automatiskt).
            "needs_review": True,
            "review_reasons": [
                "Tabellen är monterad deterministiskt ur %d lösa celler i "
                "läsordning (%d kolumner × %d rader). Cellernas text är "
                "oförändrad, men rad-/kolumnplaceringen bygger på läsordningen "
                "och bör stickprovskontrolleras mot sidans PNG."
                % (len(cells), columns, len(rows))],
        }
        out.append(table)
        for element in block:
            element["removed"] = True
            element.setdefault("source", {})["merged_into"] = table["id"]
            out.append(element)
        report.append({"status": "assembled", "page": page,
                       "table_id": table["id"], "columns": columns,
                       "rows": len(rows), "ids": consumed})
    return out, report
