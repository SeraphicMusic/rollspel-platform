"""Montering av lösa tabellceller till riktiga tabellelement.

Transkriptionen av vissa böcker (grundregelboken) lägger tabeller som en följd
av `table_header`- och `table_cell`-element i läsordning i stället för ett
`table`-element med `headers`/`rows`. Innehållet är korrekt läst men saknar
struktur, vilket gjorde att läsexporten skrev en rad per cell.

Monteringen är rent deterministisk (AGENTER.md Regel 5 — skript före LLM) och
sker i två steg. **Geometrin går först:** har varje cell en uppmätt `source.bbox`
läses kolumnen ur cellens x-läge och raden ur dess y-läge. Det är den enda
metod som klarar en GLES tabell — grundreglernas tabell över
grundegenskapskrav (s. 12) har 7 attributkolumner där varje yrke bara fyller
två eller tre, och en sekventiell påfyllning kan inte veta vilka som är tomma.
Bboxen är mätt av `pipeline/rows.py`, inte gissad, så den är det som ska styra.

Saknas bbox faller monteringen tillbaka på **läsordningen**: kolumnantalet ges
av antalet `table_header` i följd och cellerna fylls radvis. Går det inte jämnt
ut monteras ingenting — då saknas celler eller finns rubrikgrupper, och det
kräver mänsklig granskning i stället för en gissning.

Varje guard i geometrivägen leder till fallback, aldrig till en gissning: två
celler som landar i samma ruta, en cell som inte hör hemma under någon kolumn
eller en rubrikrad som inte går att läsa ut avbryter mätningen. Hellre en
oskyldig `skipped`-post än en tabell vars siffror står i fel kolumn.
"""

CELL_TYPES = ("table_header", "table_cell")

# Hur nära i y två celler måste ligga för att räknas till samma tryckta rad,
# som andel av cellernas medianhöjd. Samma mått som i pipeline/preflight.py:
# uppmätt spridning inom en rad är 0,002–0,005 mot ett radavstånd på ~0,015.
ROW_TOLERANCE = 0.6

# Hur långt från en kolumns mitt en cellmitt får ligga och ändå räknas till
# kolumnen, som andel av det minsta avståndet mellan två kolumnmitter. Uppmätt
# på s. 12: kolumnerna ligger 0,074 isär och cellmitterna avviker 0,000–0,003
# från sin rubrikmitt, alltså under 5 % av spelrummet. Halva kolumnavståndet
# är därför en vid gräns som ändå aldrig kan råka välja grannkolumnen.
COLUMN_TOLERANCE = 0.5


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


def _bands(boxes, tolerance):
    """Gruppera (box, element) i y-band uppifrån och ned.

    Samma enkellänkning som `_rows_by_geometry`, men mot en given tolerans så
    att rubriker och celler kan bandas var för sig.
    """
    bands, ref = [], None
    for box, element in sorted(boxes, key=lambda t: -t[0][1]):
        if ref is None or ref - box[1] > tolerance:
            bands.append([])
            ref = box[1]
        bands[-1].append((box, element))
    return bands


def _overlaps(a, b):
    """Överlappar två x-intervall [lo, hi] varandra?"""
    return a[0] < b[1] and b[0] < a[1]


def _span_block(träffar, columns, ensam):
    """Kolumnerna en spännrubrik står över — inte bara dem dess BLÄCK täcker.

    En centrerad grupprubrik överlappar aldrig sitt blocks ändkolumner: mätt på
    del III s. 25 har `Grundegenskapskrav` bläck x 498–786 medan kolumnblocket
    STY–STO spänner 324–846, så överlappningen ensam namnger fem av sju
    kolumner. Bokstavligt sant om bläcket, men fel som påstående om trycket —
    och påståendet hamnar i `bok.json` och i granskningsrapportens kontrollfråga
    (»kontrollera mot PNG:n att den spänner just de kolumnerna«). Se BQ-017.

    Två steg:

      1. INTERVALLFYLLNAD — alla kolumner mellan första och sista träffen. En
         rubrik kan inte spänna över ett hål.
      2. Är rubriken ENSAM spännrubrik i sitt band får den HELA värdeblocket,
         alltså kolumnerna till höger om radetikettkolumnen. Det är beslut
         s. 25:s formulering ordagrant — »`columns` listar HELA det block
         rubriken står över, inte bara de kolumner bläcket råkar överlappa«.

    Centrering PRÖVADES som diskriminator och förkastades på mätningen: s. 25:s
    etikettmitt ligger 57 px från blockmitten medan en halv kolumn är 37 px, så
    provet fäller det fall det skulle rädda. Ensamhetsvillkoret är dessutom det
    som gör steg 2 säkert — delar två rubriker på ett band värdeblocket mellan
    sig är intervallfyllnaden den enda uppgift som finns.
    """
    fyllt = list(range(min(träffar), max(träffar) + 1))
    if not ensam:
        return fyllt
    block = [i for i in range(1, len(columns))]
    if block and set(fyllt) <= set(block):
        return block
    return fyllt


def _column_axis(headers):
    """Kolumnaxeln ur rubrikernas uppmätta lägen, eller None.

    Rubrikerna behöver inte ligga på en rad. På s. 12 står `Yrke` och
    spännrubriken `Grundegenskapskrav` ett band ovanför `STY … STO`. Det
    NEDERSTA bandet definierar kolumnerna — där står de enskilda
    kolumnrubrikerna. En rubrik i ett högre band bedöms mot dem:

      * täcker den två eller fler är den en SPÄNNRUBRIK över ett block och blir
        ingen egen kolumn (`Grundegenskapskrav`),
      * täcker den exakt en är den kolumnrubrikens andra rad och läggs till
        kolumnens etikett,
      * täcker den ingen är den en egen kolumn (radetiketternas `Yrke`).

    Returnerar (kolumner, spännrubriker) där varje kolumn är
    {label, center, span} och varje spännrubrik {label, columns}.
    """
    boxes = [(_bbox(h), h) for h in headers]
    if any(box is None for box, _ in boxes):
        return None
    tolerance = max(_median([box[3] for box, _ in boxes]) * ROW_TOLERANCE,
                    0.004)
    bands = _bands(boxes, tolerance)
    base = sorted(bands[-1], key=lambda t: t[0][0])
    columns = [{"label": _text(el), "span": (box[0], box[0] + box[2])}
               for box, el in base]
    spans = []
    for band in bands[:-1]:
        rad = sorted(band, key=lambda t: t[0][0])
        # Hur många av bandets rubriker som ÄR spännrubriker avgör om en av dem
        # får hela värdeblocket — se `_span_block`.
        antal_spann = sum(
            1 for box, _ in rad
            if len([c for c in columns
                    if _overlaps((box[0], box[0] + box[2]), c["span"])]) >= 2)
        for box, el in rad:
            span = (box[0], box[0] + box[2])
            träffar = [i for i, col in enumerate(columns)
                       if _overlaps(span, col["span"])]
            if len(träffar) >= 2:
                träffar = _span_block(träffar, columns, antal_spann == 1)
                spans.append({"label": _text(el),
                              "columns": [columns[i]["label"]
                                          for i in träffar]})
            elif len(träffar) == 1:
                col = columns[träffar[0]]
                col["label"] = (_text(el) + " " + col["label"]).strip()
            else:
                columns.append({"label": _text(el), "span": span})
    columns.sort(key=lambda col: col["span"][0])
    for col in columns:
        col["center"] = (col["span"][0] + col["span"][1]) / 2.0
    return columns, spans


def _assemble_by_geometry(headers, cells):
    """Montera glesa celler i rutnätet med hjälp av uppmätt bbox.

    Returnerar (montering, orsak). `montering` är
    (kolumnetiketter, rader, spännrubriker) eller None, och `orsak` säger då
    varför mätningen inte räckte. En orsak betyder ALLTID "mät inte vidare, gå
    till läsordningen" — aldrig "gissa".

    Orsaken kastas inte bort. Att bboxen finns men MOTSÄGER sig själv är ett
    eget fynd — det är signaturen för `bbox-felkoppling` — och det får inte
    försvinna bara för att läsordningen råkar gå jämnt ut.
    """
    axis = _column_axis(headers)
    if axis is None:
        return None, "rubrikerna saknar uppmätt bbox"
    columns, spans = axis
    if len(columns) < 2:
        return None, "rubrikernas lägen ger färre än två kolumner"
    centers = [col["center"] for col in columns]
    avstånd = min(b - a for a, b in zip(centers, centers[1:]))
    if avstånd <= 0:
        return None, "två kolumnrubriker ligger på samma x-läge"
    gräns = avstånd * COLUMN_TOLERANCE

    boxes = [(_bbox(c), c) for c in cells]
    if any(box is None for box, _ in boxes):
        return None, "en eller flera celler saknar uppmätt bbox"
    tolerance = max(_median([box[3] for box, _ in boxes]) * ROW_TOLERANCE,
                    0.004)

    rader = []
    for band in _bands(boxes, tolerance):
        rad = [""] * len(columns)
        for box, el in band:
            mitt = box[0] + box[2] / 2.0
            i = min(range(len(centers)), key=lambda j: abs(centers[j] - mitt))
            if abs(centers[i] - mitt) > gräns:
                return None, ("cellen %s (’%s’) ligger inte under någon kolumn"
                              % (el.get("id"), _text(el)))
            if rad[i]:
                return None, ("cellerna ’%s’ och ’%s’ hamnar i samma ruta "
                              "(rad %d, kolumn ’%s’)"
                              % (rad[i], _text(el), len(rader) + 1,
                                 columns[i]["label"]))
            rad[i] = _text(el)
        rader.append(rad)
    if not rader:
        return None, "cellerna bildar inga rader"
    return ([col["label"] for col in columns], rader, spans), None


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


def _montera(block):
    """Montera ETT cellblock. Returnerar (montering, orsak, avvikande_rader).

    `montering` är (kolumnetiketter, rader, spännrubriker, metod, geometrifel)
    eller None. Geometrin prövas först och läsordningen är fallback; se
    modulens docstring.
    """
    headers = [e for e in block if e.get("type") == "table_header"]
    cells = [e for e in block if e.get("type") == "table_cell"]
    if len(headers) < 2:
        return None, ("hittade %d rubrik(er) — kolumnantalet går inte att "
                      "härleda" % len(headers)), []
    if not cells:
        return None, "rubriker utan celler", []

    geometri, geometrifel = _assemble_by_geometry(headers, cells)
    if geometri is not None:
        etiketter, rader, spans = geometri
        return (etiketter, rader, spans, "geometri", None), None, []

    columns = len(headers)
    if len(cells) % columns:
        visade, avvikande = _row_diagnosis(cells, columns)
        reason = ("%d celler går inte jämnt upp på %d kolumner "
                  "(rubrikgrupper eller saknade celler)"
                  % (len(cells), columns))
        if visade:
            reason += ". Avvikande rader: " + visade
        reason += ". Geometrin gick inte att använda: %s" % geometrifel
        return None, reason, avvikande
    rader = [[_text(c) for c in cells[i:i + columns]]
             for i in range(0, len(cells), columns)]
    return (([_text(h) for h in headers], rader, [], "läsordning", geometrifel),
            None, [])


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
        montering, reason, rader = _montera(block)
        if montering is None:
            out.extend(block)
            report.append({"status": "skipped", "page": page,
                           "ids": [e.get("id") for e in block],
                           "reason": reason, "rows": rader})
            continue
        header_texts, rows, spans, metod, geometrifel = montering
        headers = [e for e in block if e.get("type") == "table_header"]
        cells = [e for e in block if e.get("type") == "table_cell"]
        columns = len(header_texts)
        counter += 1
        consumed = [e.get("id") for e in block]
        data = {"headers": header_texts, "rows": rows}
        if spans:
            # Markdown kan inte uttrycka en rubrik som spänner över flera
            # kolumner, så den skulle annars falla bort ur läsexporten trots
            # att den står i trycket. Den bevaras i det kanoniska bok.json.
            data["spans"] = spans
        härkomst = (
            "uppmätt geometri (kolumn ur cellens x-läge mot kolumnrubrikerna, "
            "rad ur dess y-läge)" if metod == "geometri" else
            "läsordning (bbox saknades, cellerna fylldes radvis)")
        reasons = [
            "Tabellen är monterad deterministiskt ur %d lösa celler efter %s "
            "— %d kolumner × %d rader. Cellernas text är oförändrad, men "
            "rad-/kolumnplaceringen är härledd och bör stickprovskontrolleras "
            "mot sidans PNG." % (len(cells), härkomst, columns, len(rows))]
        if metod == "läsordning" and geometrifel:
            reasons.append(
                "Cellerna ÄR uppmätta, men geometrin gick inte ihop: %s. "
                "Raderna bygger därför på läsordningen, som är den svagare "
                "källan. Att en uppmätt box motsäger sig själv är samma klass "
                "av fynd som `bbox-felkoppling` — kontrollera mätningen, inte "
                "bara tabellens innehåll." % geometrifel)
        tomma = sum(1 for row in rows for cell in row if not cell)
        if tomma:
            # Geometrin ser ett HÅL, inte varför det finns. En tom ruta kan
            # vara tom i trycket (yrket har inget krav på den grundegenskapen)
            # eller en cell som transkriptionen tappat. Skillnaden syns bara i
            # PNG:n, och den får inte döljas av att tabellen nu monterar.
            reasons.append(
                "%d av %d rutor är tomma. Geometrin kan inte skilja en ruta "
                "som är tom i TRYCKET från en cell som transkriptionen TAPPAT "
                "— läs av dem mot PNG:n innan tabellen används som facit. "
                "Tomma rutor: %s."
                % (tomma, columns * len(rows),
                   ", ".join("rad %d ’%s’ saknar %s"
                             % (i + 1, row[0] or "(tom)",
                                ", ".join(header_texts[j] or "kolumn %d" % (j + 1)
                                          for j, v in enumerate(row) if not v))
                             for i, row in enumerate(rows)
                             if not all(row))))
        for span in spans:
            reasons.append(
                "Spännrubriken ’%s’ står över kolumnerna %s och kan inte "
                "uttryckas i en markdown-tabell. Den finns kvar under "
                "`data.spans` i bok.json — kontrollera mot PNG:n att den "
                "spänner just de kolumnerna."
                % (span["label"], ", ".join(span["columns"])))
        table = {
            "id": "%s_tbl%02d" % (headers[0].get("id", "tabell"), counter),
            "type": "table",
            "text": "",
            "data": data,
            "source": {"merged_from": consumed,
                       "assembled_by": "pipeline.tables.assemble",
                       "assembly_method": metod},
            # Spelvärden i en grundregelbok ska stickprovskontrolleras mot
            # PNG:n innan exporten används som facit (Regel 8a: siffror rättas
            # aldrig automatiskt).
            "needs_review": True,
            "review_reasons": reasons,
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
