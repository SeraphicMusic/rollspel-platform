"""Export från kanonisk bok-JSON till Markdown, CSV och DOCX.

All export genereras från export/bok.json (kör `sammanfoga` först).
DOCX återanvänder befintliga .claude/skills/extrahera/create-docx.js.
"""
import csv
import json
import subprocess
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
            lines.append("- **%s:** %s" % (k, v))
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


def export_markdown(workdir, include_artifacts=False):
    log = setup_logging(workdir)
    book = _load_book(workdir)
    lines = []
    title = (book["source"].get("metadata") or {}).get("title") \
        or Path(book["source"]["path"]).stem
    lines += ["# %s" % title, ""]
    for page in book["pages"]:
        lines.append("<!-- sida %d -->" % page["page"])
        elements, _ = tables.assemble(page["elements"], page["page"])
        for el in elements:
            etype = el.get("type")
            text = (el.get("text") or "").strip()
            if el.get("removed"):
                continue
            if etype == "page_artifact" and not include_artifacts:
                continue
            if etype == "heading":
                level = min(int(el.get("level", 2)) + 1, 6)
                lines += ["#" * level + " " + text, ""]
            elif etype in ("paragraph", "toc_entry", "index_entry"):
                if el.get("style") == "italic":
                    lines += ["*%s*" % text, ""]
                else:
                    lines += [text, ""]
            elif etype == "boxed_text":
                lines += ["> " + text.replace("\n", "\n> "), ""]
            elif etype == "list":
                items = (el.get("data") or {}).get("items") or []
                lines += ["- %s" % i for i in items] + [""]
            elif etype == "table":
                lines += _table_md(el)
            elif etype == "statblock":
                lines += _statblock_md(el)
            elif etype in _BULLET_TYPES:
                lines += ["- %s" % text]
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
