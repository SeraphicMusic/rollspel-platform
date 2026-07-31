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


def _text(element):
    return (element.get("text") or "").strip()


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
        reason = None
        if columns < 2:
            reason = ("hittade %d rubrik(er) — kolumnantalet går inte att "
                      "härleda" % columns)
        elif not cells:
            reason = "rubriker utan celler"
        elif len(cells) % columns:
            reason = ("%d celler går inte jämnt upp på %d kolumner "
                      "(rubrikgrupper eller saknade celler)"
                      % (len(cells), columns))
        if reason:
            out.extend(block)
            report.append({"status": "skipped", "page": page,
                           "ids": [e.get("id") for e in block],
                           "reason": reason})
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
