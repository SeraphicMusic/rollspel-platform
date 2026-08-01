"""Export från kanonisk bok-JSON till Markdown, CSV och DOCX.

All export genereras från export/bok.json (kör `sammanfoga` först).
DOCX återanvänder befintliga .claude/skills/extrahera/create-docx.js.
"""
import csv
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from . import tables
from .log import setup_logging
from .manifest import export_dir, read_json

DOCX_SCRIPT = Path(__file__).resolve().parent.parent / \
    ".claude" / "skills" / "extrahera" / "create-docx.js"


def _load_book(workdir):
    path = export_dir(workdir) / "bok.json"
    if not path.is_file():
        raise SystemExit("export/bok.json saknas — kör `sammanfoga` först")
    return read_json(path)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

# Transkriberingsmetadata som beskriver hur källans attacktabell såg ut. Den
# renderade vapentabellen ersätter den — nyckeln ska inte ut i läsexporten.
_INTERNAL_KEYS = {"attacktabell_rubrik"}

# Transkriptionen använder en finare elementvokabulär än exportörens grundfall.
# Typer som inte står här renderades tidigare som vanliga stycken av en tyst
# catch-all — därför föll t.ex. grundregelbokens tabellceller ut som en rad per
# cell utan att någon varnades. Okända typer skrivs fortfarande ut (innehåll får
# aldrig tappas) men loggas nu så att luckan syns.
_CAPTION_TYPES = ("illustration", "table_caption", "table_note")
_BULLET_TYPES = ("list_item", "requirement")
_HANDLED_TYPES = frozenset(
    ("heading", "paragraph", "toc_entry", "index_entry", "boxed_text",
     "list", "table", "statblock", "page_artifact",
     "table_cell", "table_header") + _CAPTION_TYPES + _BULLET_TYPES)


def _warn_unknown_types(book, log):
    """Logga elementtyper exportören inte har någon egen rendering för."""
    unknown = {}
    for page in book["pages"]:
        for el in page["elements"]:
            etype = el.get("type")
            if etype in _HANDLED_TYPES or el.get("removed"):
                continue
            if (el.get("text") or "").strip():
                unknown.setdefault(etype, []).append(page["page"])
    for etype, pages in sorted(unknown.items()):
        log.warning(
            "okänd elementtyp %r på %d element (sidor %s) — renderas som "
            "stycke; lägg till en gren i export.py om den behöver egen form",
            etype, len(pages), ", ".join(str(p) for p in sorted(set(pages))))
    return unknown


def _field_value(value):
    """Läsbar text för ett statblockfält som inte är en enkel sträng.

    `extraStats` bär ibland en hel kolumn ur rutan — spöket på s. 47 har
    multiplikatorerna `{"STY": "0", "STO": "x1", …}` som härleder attributen ur
    offrets egna värden. Utan detta föll de ut som en rå Python-dict i
    `bok.md` (`- **Multipel:** {'STY': '0', …}`).
    """
    if isinstance(value, dict):
        return ", ".join("%s %s" % (k, v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return value


def _statblock_md(el):
    data = el.get("data") or {}
    lines = []
    name = data.get("name") or el.get("text") or "Statblock"
    lines.append("**%s**" % name)
    lines.append("")
    stats = data.get("stats") or {}
    if stats:
        lines.append("| " + " | ".join(stats.keys()) + " |")
        lines.append("|" + "---|" * len(stats))
        lines.append("| " + " | ".join(str(v) for v in stats.values()) + " |")
        lines.append("")
    for section in ("extraStats", "other"):
        for k, v in (data.get(section) or {}).items():
            if k in _INTERNAL_KEYS:
                continue
            lines.append("- **%s:** %s" % (k, _field_value(v)))
    skills = data.get("skills") or {}
    if skills:
        lines.append("- **Färdigheter:** " + ", ".join(
            "%s %s" % (k, v) for k, v in skills.items()))
    lines.extend(_weapons_md(data.get("weapons")))
    lines.append("")
    return lines


# Kolumner i den ordning en spelare läser dem; nycklar som inte står här är
# katalogmetadata (pris, vikt, vapengrupp) och hör inte hemma i statblocket.
_WEAPON_COLUMNS = (("attack", "Attack"), ("damage", "Skada"),
                   ("bv", "BV"), ("range", "Räckvidd"),
                   ("rackvidd", "Räckvidd"), ("styKrav", "STY-krav"))


def _weapons_md(weapons):
    """Vapenrader — utan den här förlorade md-exporten hela vapenblocket."""
    if not weapons:
        return []
    rows = [w if isinstance(w, dict) else {"name": str(w)} for w in weapons]
    columns = [(key, label) for key, label in _WEAPON_COLUMNS
               if any(row.get(key) not in (None, "") for row in rows)]
    esc = lambda cell: str(cell).replace("|", "\\|")
    lines = ["", "| Vapen | " + " | ".join(label for _, label in columns) +
             " |", "|---|" + "---|" * len(columns)]
    for row in rows:
        cells = [esc(row.get(key, "—") if row.get(key) not in (None, "")
                     else "—") for key, _ in columns]
        lines.append("| %s | %s |" % (esc(row.get("name", "?")),
                                      " | ".join(cells)))
    return lines


def _table_md(el):
    data = el.get("data") or {}
    headers = data.get("headers") or []
    rows = data.get("rows") or []
    if not rows:
        return []
    esc = lambda cell: str(cell).replace("|", "\\|")
    lines = []
    caption = (el.get("text") or "").strip()
    if caption:
        lines += ["**%s**" % esc(caption), ""]
    if headers:
        lines += ["| " + " | ".join(esc(h) for h in headers) + " |",
                 "|" + " --- |" * len(headers)]
        for row in rows:
            lines.append("| " + " | ".join(esc(c) for c in row) + " |")
    else:
        for row in rows:
            lines.append("- " + " — ".join(esc(c) for c in row))
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Återflödning: ett element är EN tryckt rad
# ---------------------------------------------------------------------------

# Transkriptionen ger ett element per tryckt rad. Renderas raderna var för sig
# blir varje rad ett eget markdown-stycke — hela DoD-grundregelboken föll ut så,
# 3150 brödtextrader med tomrad emellan. Raderna fogas därför ihop till stycken
# igen, med tryckets egen geometri som facit i stället för gissningar om språket.
#
# Två signaler, båda uppmätta på grundregelboken (68 sidor, 3510 rader):
#   1. INDRAG. bbox-bruset inom en spalt ligger på ≤0,015 medan styckeindraget
#      ligger på 0,020–0,030. Tröskeln sätts däremellan.
#   2. KORT RAD. Satsen är utsluten, så varje rad utom styckets sista fyller
#      spalten (0,43–0,44 av sidbredden). En kortare rad avslutar ett stycke.
# Signalerna är oberoende och ORas — endera räcker för att bryta stycket.
# Listpunkter flödas om av samma skäl: en punkt som räknar upp färdigheter
# löper över åtta tryckta rader och blev åtta punkter (s. 17).
_REFLOW_TYPES = ("paragraph", "boxed_text") + _BULLET_TYPES
_INDENT_MIN = 0.018
_FULL_LINE = 0.92
# Andel av sidans löptextbredd under vilken en rad inte kan vara löptext alls.
# Uppmätt: brödtextrader 0,35–0,44, tabellceller under 0,22.
_MIN_PROSE_LINE = 0.5
# Rader inom så här långt avstånd i sidled räknas till samma spalt. Fönstret
# måste rymma indraget (0,020–0,030) men utesluta grannspalter — på de sidor som
# blandar tabell och brödtext ligger närmaste andra kolumn 0,05 bort.
_COLUMN_WINDOW = 0.04
_X_BUCKET = 0.005

# Ett hängande bindestreck i en samordning (`djur-` + `växt- och mineralriket`)
# ser ut som en avstavning men får inte fogas ihop.
_HANGING_HYPHEN = re.compile(r"^\S*-(?:\s|$)")

# `Tillredning:`, `Växtplats:`, `Effekt:` — en kort inledande etikett med
# kolon. Ett eller två ord räcker (`Naturligt skydd:`); längre än så är det
# löptext med ett kolon i sig, inte en fältrad.
_FIELD_LINE = re.compile(r"^[A-ZÅÄÖ][\wåäöÅÄÖ]*(?: [\wåäöÅÄÖ]+)?:(?:\s|$)")


def _bbox(el):
    return (el.get("source") or {}).get("bbox")


def _join_text(prev, nxt):
    """Foga ihop två tryckta rader och läk radbrytningen vid radslutet.

    Två radslut binder ihop orden utan mellanslag: avstavningens bindestreck
    (som faller bort) och sättarens snedstreck (som står kvar). Trycket bryter
    gärna en uppräkning mitt i — `(liten/medelstor/` + `stor)` — och utan
    läkningen faller den ut som `(liten/medelstor/ stor)`. Ett snedstreck som
    är satt MED mellanslag omkring sig (`Teknik / Grundkostnad`) är en
    avskiljare, inte en bindning, och läks därför inte.
    """
    prev, nxt = (prev or "").rstrip(), (nxt or "").lstrip()
    if not prev or not nxt:
        return prev or nxt
    if (prev.endswith("-") and not prev.endswith((" -", "--"))
            and nxt[:1].islower() and not _HANGING_HYPHEN.match(nxt)):
        return prev[:-1] + nxt
    if prev.endswith("/") and not prev.endswith((" /", "//")):
        return prev + nxt
    return prev + " " + nxt


def _median(values):
    values = sorted(values)
    if not values:
        return None
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2.0


def _local_column(bb, boxes):
    """(vänsterkant, radbredd) för spalten som raden `bb` tillhör.

    Måtten räknas ur de rader som ligger NÄRMAST i sidled, inte ur en global
    spaltindelning av sidan. Skälet är uppmätt: en sida som blandar tabell och
    brödtext har kolumner bara några hundradelar isär (s. 61: tabellens
    högerkolumn på 0,49 mot brödtextens 0,518). En global indelning slår ihop
    dem, och då ser varenda brödtextrad indragen ut mot tabellkolumnens
    vänsterkant — stycket sprängs vid varje rad.

    Vänsterkanten är det VANLIGASTE x-värdet, inte det minsta: i en spalt börjar
    de allra flesta rader vid marginalen, medan indragen och enstaka avvikande
    element är minoriteten. Bredden är medianen av samma skäl.
    """
    near = [b for b in boxes if abs(b[0] - bb[0]) <= _COLUMN_WINDOW]
    if not near:
        return None
    counts = Counter(int(round(b[0] / _X_BUCKET)) for b in near)
    left = min(counts, key=lambda bucket: (-counts[bucket], bucket)) * _X_BUCKET
    return left, _median([b[2] for b in near])


def _prose_width(boxes):
    """Sidans typiska radbredd för löptext, som 75:e percentilen.

    Medianen duger inte: på en tabelltung sida är den dominerad av celler
    (s. 61 har median 0,126 mot brödtextens 0,42). 75:e percentilen ligger
    stabilt på 0,40–0,44 även där.
    """
    widths = sorted(b[2] for b in boxes)
    if not widths:
        return None
    return widths[min(len(widths) - 1, int(len(widths) * 0.75))]


def _starts_paragraph(el, prev, nxt, boxes, prev_boxes):
    """Inleder `el` ett nytt stycke, eller fortsätter det föregående raden?

    Raden och dess föregångare mäts mot SIN EGEN sidas rader — ett stycke som
    löper över en sidbrytning har en rad på var sida, och sidorna kan ha olika
    spaltgeometri.
    """
    # 0. En fältrad inleder alltid sitt eget block. Örtposterna (s. 53–61) sätts
    #    `Etikett: värde` med en etikett per tryckt rad, och raderna fyller inte
    #    spalten — men på en sådan sida räknas breddreferensen ur etikettraderna
    #    själva, så varken kortradsregeln eller utslutningsregeln nedan biter.
    #    Utan detta faller hela posten ut som en enda rad:
    #    `Tillredning: Brygges Intagning: Appliceras Växtplats: Ljus lövskog`.
    if _FIELD_LINE.match((el.get("text") or "").lstrip()):
        return True
    bb, pbb = _bbox(el), _bbox(prev)
    if bb is None or pbb is None:
        # Utan geometri finns inget facit — då fogas ingenting ihop.
        return True
    # 1a. En rad som är MYCKET kortare än sidans löptext är ingen löptextrad —
    #     den är en tabellcell. Utan detta fogas celler som ligger som
    #     `paragraph` ihop till cellsoppa (`Hyfsad simmare 2 3`, s. 56), för då
    #     räknas breddreferensen ur cellerna själva och blir meningslös.
    #     Regeln gäller bara framåt: en kort SISTA rad i ett stycke får
    #     fortfarande fogas till raden före sig.
    prose = _prose_width(prev_boxes)
    if prose and pbb[2] < _MIN_PROSE_LINE * prose:
        return True
    # 1b. Utsluten sats: fyllde föregående rad inte spalten tog stycket slut.
    pcol = _local_column(pbb, prev_boxes)
    if pcol and pbb[2] < _FULL_LINE * pcol[1]:
        return True
    # 2. Indrag inleder ett stycke — men bara ett ENSAMT indrag.
    #    Boken sätter också HÄNGANDE indrag (`Rundspark:` i marginalen med
    #    fortsättningsraderna indragna, s. 59; punktlistor på s. 65). Där är
    #    polariteten den omvända, och att läsa indraget som styckestart delar
    #    varje sådant stycke i en rad per stycke. Skillnaden är att ett hängande
    #    indrag DELAS av flera rader i följd, medan ett styckeindrag står ensamt.
    col = _local_column(bb, boxes)
    if col and bb[0] - col[0] >= _INDENT_MIN:
        if abs(bb[0] - pbb[0]) < _INDENT_MIN:
            return False
        nbb = _bbox(nxt) if nxt is not None else None
        if nbb is not None and abs(nbb[0] - bb[0]) < _INDENT_MIN:
            return False
        return True
    return False


def _reflow(run):
    """Dela en rad-följd i stycken och foga ihop varje styckes rader.

    `run` är (sida, element)-par och får spänna över en sidbrytning — det är
    just så ett stycke som fortsätter på nästa sida fogas ihop. Varje returnerat
    stycke bär därför sidan för sin EGEN första rad, inte följdens: annars
    tappas sidmarkören för varje sida som ett stycke råkar sträcka sig in i.

    Spaltmåtten räknas fram PER SIDA ur följdens egna rader. Båda avgränsningarna
    är nödvändiga: tas de ur sidan i stort mäts en smal exempelruta mot
    brödtextspalten och sprängs vid varje rad, och tas de ur hela följden blandas
    flera sidors spalter och tabellceller ihop till en obrukbar median.
    """
    per_page = {}
    for page, el in run:
        if _bbox(el):
            per_page.setdefault(page, []).append(_bbox(el))
    filled = [(page, el) for page, el in run
              if (el.get("text") or "").strip()]
    blocks = []
    for position, (page, el) in enumerate(filled):
        if blocks:
            ppage, pel = blocks[-1][-1]
            nxt = filled[position + 1][1] \
                if position + 1 < len(filled) else None
            fresh = _starts_paragraph(el, pel, nxt, per_page.get(page) or [],
                                      per_page.get(ppage) or [])
        else:
            fresh = True
        if fresh:
            blocks.append([(page, el)])
        else:
            blocks[-1].append((page, el))
    out = []
    for block in blocks:
        text = ""
        for _, el in block:
            text = _join_text(text, (el.get("text") or "").strip())
        out.append((block[0][0], text))
    return out


# ---------------------------------------------------------------------------
# Hopfogning av tabeller över sidbrytning
# ---------------------------------------------------------------------------

# `tables.assemble` arbetar per sida och kan därför inte se att en tabell
# fortsätter på nästa. I grundregelboken bröts Särskilda förmågor-tabellen mitt
# i rad 78 (`INT-basera-`) och raderna 79–81 föll ut som listpunkter utanför
# tabellen.
_ROW_SPLIT = re.compile(r"^(\S+)\s+—\s+(.+)$", re.S)


def _same_table(a, b):
    ha = (a.get("data") or {}).get("headers") or []
    hb = (b.get("data") or {}).get("headers") or []
    return bool(ha) and ha == hb


def _stitch_list(table, lst):
    """Foga in en lista som i själva verket är tabellens fortsättning.

    Returnerar False och rör ingenting om någon punkt inte har radens form —
    att tappa text vore värre än en ful lista.
    """
    data = table.get("data") or {}
    rows = data.get("rows") or []
    items = [i.strip() for i in ((lst.get("data") or {}).get("items") or [])
             if i and i.strip()]
    if len(data.get("headers") or []) != 2 or not rows or not items:
        return False
    continuation, new_rows = None, []
    for idx, item in enumerate(items):
        match = _ROW_SPLIT.match(item)
        if match:
            new_rows.append([match.group(1), match.group(2)])
        elif idx == 0 and item[:1].islower():
            continuation = item
        else:
            return False
    if continuation:
        rows[-1] = list(rows[-1])
        rows[-1][-1] = _join_text(rows[-1][-1], continuation)
    data["rows"] = rows + new_rows
    table["data"] = data
    return True


def _stitch(items):
    """Slå ihop tabeller som löper över en sidbrytning."""
    out = []
    for page, el in items:
        prev = out[-1][1] if out else None
        if prev is not None and prev.get("type") == "table":
            if el.get("type") == "table" and _same_table(prev, el):
                prev_data = prev.setdefault("data", {})
                prev_data["rows"] = (prev_data.get("rows") or []) + \
                    ((el.get("data") or {}).get("rows") or [])
                continue
            if el.get("type") == "list" and _stitch_list(prev, el):
                continue
        out.append((page, el))
    return out


def _stream(book, include_artifacts):
    """(sida, element) för hela boken, med cellblock monterade."""
    for page in book["pages"]:
        elements, _ = tables.assemble(page["elements"], page["page"])
        for el in elements:
            if el.get("removed"):
                continue
            if el.get("type") == "page_artifact" and not include_artifacts:
                continue
            yield page["page"], el


def export_markdown(workdir, include_artifacts=False):
    log = setup_logging(workdir)
    book = _load_book(workdir)
    lines = []
    title = (book["source"].get("metadata") or {}).get("title") \
        or Path(book["source"]["path"]).stem
    lines += ["# %s" % title, ""]
    items = _stitch(list(_stream(book, include_artifacts)))
    last_page = None
    index = 0
    while index < len(items):
        page, el = items[index]
        etype = el.get("type")
        # En rad-följd samlas ihop och flödas om till stycken. Följden bryts av
        # varje annan elementtyp, och av att stilen växlar (kursiv exempelruta).
        if etype in _REFLOW_TYPES:
            run, style = [], el.get("style")
            while index < len(items):
                nxt_page, nxt = items[index]
                if nxt.get("type") != etype or nxt.get("style") != style:
                    break
                run.append((nxt_page, nxt))
                index += 1
            blocks = _reflow(run)
            for blk_page, text in blocks:
                if blk_page != last_page:
                    lines += ["<!-- sida %d -->" % blk_page, ""]
                    last_page = blk_page
                if etype in _BULLET_TYPES:
                    # Punkterna hålls ihop utan tomrad emellan, annars blir
                    # varje punkt en egen lista i markdown.
                    lines += ["- %s" % text]
                elif etype == "boxed_text":
                    # En tryckt exempelruta är EN ruta även när den rymmer
                    # flera stycken. Skiljs styckena av en TOM rad blir de två
                    # citatblock i markdown och rutan går synligt itu — s. 10:s
                    # HINDER- och SLUMPMÄSSIGA MÖTEN-exempel bröt av precis så
                    # sedan raderna började mätas på sin egen bredd i stället
                    # för på rutans ram. Separatorn är därför en CITERAD
                    # tomrad, samma grepp som håller ihop punktlistorna.
                    if lines and lines[-1].startswith(">"):
                        lines += [">"]
                    lines += ["> " + text.replace("\n", "\n> ")]
                elif style == "italic":
                    lines += ["*%s*" % text, ""]
                else:
                    lines += [text, ""]
            if blocks and (etype in _BULLET_TYPES or etype == "boxed_text"):
                lines += [""]
            continue
        index += 1
        text = (el.get("text") or "").strip()
        if page != last_page:
            lines += ["<!-- sida %d -->" % page, ""]
            last_page = page
        if etype == "heading":
            level = min(int(el.get("level", 2)) + 1, 6)
            lines += ["#" * level + " " + text, ""]
        elif etype in ("toc_entry", "index_entry"):
            # Flödas ALDRIG om: en innehålls- eller registerpost är en rad,
            # och att foga ihop dem skulle förstöra uppställningen.
            lines += ["*%s*" % text, ""] if el.get("style") == "italic" \
                else [text, ""]
        elif etype == "list":
            lines += ["- %s" % i
                      for i in ((el.get("data") or {}).get("items") or [])]
            lines += [""]
        elif etype == "table":
            lines += _table_md(el)
        elif etype == "statblock":
            lines += _statblock_md(el)
        elif etype in _CAPTION_TYPES:
            # Bildtext/tabellnot är inte brödtext; kursiv skiljer den åt.
            lines += ["*%s*" % text, ""] if text else []
        elif etype in tables.CELL_TYPES:
            # Cellblock som monteringen inte kunde tyda (ojämnt antal
            # celler). Att tappa värdena är värre än en ful rad, så de
            # skrivs ut — och sidan syns i varningsloggen.
            lines += ["| %s |" % text] if text else []
        elif text:
            lines += [text, ""]
    _warn_unknown_types(book, log)
    out = export_dir(workdir) / "bok.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    log.info("export markdown -> %s", out)
    return out


# ---------------------------------------------------------------------------
# CSV (en fil per tabell)
# ---------------------------------------------------------------------------

def export_csv(workdir):
    log = setup_logging(workdir)
    book = _load_book(workdir)
    outdir = export_dir(workdir) / "tabeller"
    outdir.mkdir(exist_ok=True)
    n = 0
    for page in book["pages"]:
        # Samma montering som md/docx, annars saknas de tabeller som ligger
        # som lösa celler i CSV-exporten.
        elements, _ = tables.assemble(page["elements"], page["page"])
        for el in elements:
            if el.get("removed"):
                continue
            if el.get("type") != "table":
                continue
            data = el.get("data") or {}
            headers, rows = data.get("headers"), data.get("rows")
            if not rows:
                continue
            n += 1
            out = outdir / ("sida%03d_%s.csv" % (page["page"],
                                                 el.get("id", "tabell")))
            with open(out, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                if headers:
                    w.writerow(headers)
                w.writerows(rows)
    log.info("export csv: %d tabeller -> %s", n, outdir)
    return outdir, n


# ---------------------------------------------------------------------------
# DOCX (via befintliga create-docx.js)
# ---------------------------------------------------------------------------

def _to_docx_content(book):
    """Konvertera kanonisk modell till create-docx.js innehållsformat."""
    content = []
    for page in book["pages"]:
        if content:
            content.append({"type": "pagebreak", "page": page["page"]})
        elements, _ = tables.assemble(page["elements"], page["page"])
        for el in elements:
            etype = el.get("type")
            text = (el.get("text") or "").strip()
            if el.get("removed"):
                continue
            if etype == "page_artifact":
                continue
            if etype == "heading":
                level = min(int(el.get("level", 2)), 3)
                content.append({"type": "heading%d" % level, "text": text})
            elif etype in ("paragraph", "toc_entry", "index_entry"):
                content.append({"type": "italic" if el.get("style") == "italic"
                                else "paragraph", "text": text})
            elif etype == "boxed_text":
                content.append({"type": "italic", "text": text})
            elif etype == "list":
                items = (el.get("data") or {}).get("items") or []
                content.append({"type": "list", "items": items})
            elif etype == "table":
                data = el.get("data") or {}
                content.append({"type": "table",
                                "headers": data.get("headers") or [],
                                "rows": data.get("rows") or []})
            elif etype == "statblock":
                data = el.get("data") or {}
                content.append({"type": "statblock",
                                "name": data.get("name"),
                                "stats": data.get("stats") or {},
                                "skills": data.get("skills") or {},
                                "other": data.get("other") or {}})
            elif etype in _BULLET_TYPES:
                content.append({"type": "list", "items": [text]})
            elif etype in _CAPTION_TYPES:
                content.append({"type": "italic", "text": text})
            elif text:
                content.append({"type": "paragraph", "text": text})
    return content


def export_docx(workdir):
    """Avvecklad — markdown är läsformatet (användarbeslut 2026-07-29).

    Behållen för den som uttryckligen begär --format docx, men generatorn
    saknar rendering för statblockens vapentabeller och producerar därför
    ofullständiga filer. Ingår inte längre i `alla`.
    """
    log = setup_logging(workdir)
    log.warning("docx-exporten är avvecklad och saknar statblockens "
                "vapentabeller — markdown är läsformatet")
    book = _load_book(workdir)
    title = (book["source"].get("metadata") or {}).get("title") \
        or Path(book["source"]["path"]).stem
    payload = {"title": title, "content": _to_docx_content(book)}
    tmp = export_dir(workdir) / "bok.docx.json"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    out = export_dir(workdir) / "bok.docx"
    result = subprocess.run(
        ["node", str(DOCX_SCRIPT), str(tmp), str(out)],
        capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit("create-docx.js misslyckades: %s" % result.stderr)
    log.info("export docx -> %s", out)
    return out
