"""Export av konverterad JSON, Markdown och konverteringsrapport."""
import json
import os
from pathlib import Path

from .export import _statblock_md, _table_md


def atomic_write(path, content):
    """Skriv via .part och byt namn först när hela filen är färdig."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = Path(str(path) + ".part")
    mode = "wb" if isinstance(content, bytes) else "w"
    kwargs = {} if isinstance(content, bytes) else {"encoding": "utf-8"}
    with open(part, mode, **kwargs) as target:
        target.write(content)
        target.flush()
        os.fsync(target.fileno())
    os.replace(part, path)


def atomic_json(path, data):
    atomic_write(path, json.dumps(
        data, ensure_ascii=False, indent=2, sort_keys=False) + "\n")


def markdown_from_book(book):
    title = ((book.get("source") or {}).get("metadata") or {}).get("title")
    if not title:
        title = Path((book.get("source") or {}).get("path", "Äventyr")).stem
    lines = ["# %s" % title, ""]
    for page in book.get("pages", []):
        lines.append("<!-- sida %d -->" % page["page"])
        for element in page.get("elements", []):
            if element.get("removed"):
                continue
            etype = element.get("type")
            text = (element.get("text") or "").strip()
            if etype == "page_artifact":
                continue
            if etype == "heading":
                level = min(int(element.get("level", 2)) + 1, 6)
                lines.extend(["#" * level + " " + text, ""])
            elif etype in ("paragraph", "toc_entry", "index_entry"):
                lines.extend(
                    ["*%s*" % text if element.get("style") == "italic"
                     else text, ""])
            elif etype == "boxed_text":
                lines.extend(["> " + text.replace("\n", "\n> "), ""])
            elif etype == "list":
                lines.extend(["- %s" % item for item in
                              (element.get("data") or {}).get("items", [])])
                lines.append("")
            elif etype == "table":
                lines.extend(_table_md(element))
            elif etype == "statblock":
                lines.extend(_statblock_md(element))
            elif text:
                lines.extend([text, ""])
    return "\n".join(lines)


def conversion_report(source, source_sha256, profile, analysis,
                      extraction_review, status, publication_paths=None):
    counts = analysis["counts"]
    lines = [
        "# Konverteringsrapport",
        "",
        "## Källa och profil",
        "",
        "- Källa: `%s`" % source,
        "- SHA-256: `%s`" % source_sha256,
        "- Profil: `%s` version %s" %
        (profile["id"], profile["version"]),
        "- Befintliga granskningsposter från extraktionen: %d" %
        extraction_review,
        "",
        "## Sammanfattning",
        "",
        "- Applicerade regelkonverteringar: %d" % counts["applied"],
        "- Blockerande konverteringsbeslut: %d" % counts.get(
            "blocking", counts["needs_review"]),
        "- Noteringar utan blockering: %d" % (
            counts["needs_review"] - counts.get(
                "blocking", counts["needs_review"])),
        "- Ej applicerade kandidater: %d" % counts["unchanged"],
        "- Genomsökta element: %d" % counts["elements_scanned"],
        "",
        "| Regelkategori | Applicerade | Behöver granskas |",
        "| --- | ---: | ---: |",
    ]
    for category, values in sorted(analysis["categories"].items()):
        lines.append("| %s | %d | %d |" % (
            category, values["applied"], values["needs_review"]))

    applied = [r for r in analysis["candidates"] if r["applied"]]
    proposed = [r for r in analysis["candidates"] if not r["applied"]]
    lines.extend(["", "## Applicerade konverteringar", ""])
    if applied:
        for record in applied:
            lines.append(
                "- Sida %s, `%s`: `%s` → `%s` — %s" %
                (record["source"]["page"], record["element_id"],
                 record["original"], record["converted"], record["reason"]))
    else:
        lines.append("Inga.")

    def _is_note(record):
        """Redovisad men avgjord: needs_review utan blockering."""
        return record["needs_review"] and not record.get("blocking")

    notes = [r for r in proposed if _is_note(r)]
    if notes:
        lines.extend(["", "## Noteringar — avgjort av profilen", "",
                      "Redovisas för spårbarhet men stoppar inte publicering: "
                      "utfallet följer en regel som redan är fastställd.", ""])
        for record in notes:
            lines.append(
                "- Sida %s, `%s` [%s]: `%s` — %s" %
                (record["source"]["page"], record["element_id"],
                 record["rule"], record["original"], record["reason"]))

    lines.extend(["", "## Ej applicerade förslag och omatchade termer", ""])
    proposed = [r for r in proposed if not _is_note(r)]
    if proposed:
        for record in proposed:
            lines.append(
                "- Sida %s, `%s` [%s]: `%s` — %s" %
                (record["source"]["page"], record["element_id"],
                 record["rule"], record["original"], record["reason"]))
    else:
        lines.append("Inga.")

    lines.extend(["", "## Publiceringsstatus", "",
                  "- Status: `%s`" % status])
    if status == "complete":
        lines.append("- Konverteringen saknar blockerande beslut.")
        for path in publication_paths or []:
            lines.append("- Publicerad: `%s`" % path)
    elif status == "needs_review":
        lines.append(
            "- Ingen publicering gjordes; mänsklig granskning krävs.")
    else:
        lines.append("- Dry-run: ingen konverterad MD/JSON publicerades.")
    lines.append("")
    return "\n".join(lines)

