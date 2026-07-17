"""Export från kanonisk bok-JSON till Markdown, CSV och DOCX.

All export genereras från export/bok.json (kör `sammanfoga` först).
DOCX återanvänder befintliga .claude/skills/extrahera/create-docx.js.
"""
import csv
import json
import subprocess
from pathlib import Path

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
            lines.append("- **%s:** %s" % (k, v))
    skills = data.get("skills") or {}
    if skills:
        lines.append("- **Färdigheter:** " + ", ".join(
            "%s %s" % (k, v) for k, v in skills.items()))
    lines.append("")
    return lines


def _table_md(el):
    data = el.get("data") or {}
    headers = data.get("headers") or []
    rows = data.get("rows") or []
    if not headers:
        return []
    esc = lambda cell: str(cell).replace("|", "\\|")
    lines = ["| " + " | ".join(esc(h) for h in headers) + " |",
             "|" + " --- |" * len(headers)]
    for row in rows:
        lines.append("| " + " | ".join(esc(c) for c in row) + " |")
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
        for el in page["elements"]:
            etype = el.get("type")
            text = (el.get("text") or "").strip()
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
            elif text:
                lines += [text, ""]
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
        for el in page["elements"]:
            if el.get("type") != "table":
                continue
            data = el.get("data") or {}
            headers, rows = data.get("headers"), data.get("rows")
            if not headers or rows is None:
                continue
            n += 1
            out = outdir / ("sida%03d_%s.csv" % (page["page"],
                                                 el.get("id", "tabell")))
            with open(out, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
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
        for el in page["elements"]:
            etype = el.get("type")
            text = (el.get("text") or "").strip()
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
            elif text:
                content.append({"type": "paragraph", "text": text})
    return content


def export_docx(workdir):
    log = setup_logging(workdir)
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
