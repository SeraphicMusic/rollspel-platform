"""Sammanfogning: bästa tillgängliga version per sida -> kanonisk bok-JSON.

Prioritet per sida: final > validated > transcript > embedded.
"""
from .log import setup_logging
from .manifest import (Manifest, atomic_write_json, export_dir, now_iso,
                       page_file, read_json)
from .provenance import STAMP_KEY, stamp

PRIORITY = ("final.json", "validated.json", "transcript.json", "embedded.json")


def best_page_file(workdir, page_no):
    for suffix in PRIORITY:
        path = page_file(workdir, page_no, suffix)
        if path.is_file():
            return path, suffix.split(".")[0]
    return None, None


def merge(workdir):
    log = setup_logging(workdir)
    m = Manifest.load(workdir)
    pages_out = []
    missing = []
    n_elements = 0
    review_total = 0
    for no in m.page_numbers():
        p = m.page(no)
        if p["class"] == "empty":
            continue
        path, stage = best_page_file(workdir, no)
        if path is None:
            missing.append(no)
            continue
        data = read_json(path)
        elements = data.get("elements", data if isinstance(data, list) else [])
        for i, el in enumerate(elements):
            el.setdefault("id", "p%03d_e%02d" % (no, i + 1))
            el.setdefault("source", {}).setdefault("page", no)
            if el.get("needs_review"):
                review_total += 1
        n_elements += len(elements)
        page_out = {"page": no, "stage": stage, "class": p["class"],
                    "elements": elements}
        if data.get("skipped"):
            page_out["skipped"] = data["skipped"]
        pages_out.append(page_out)

    book = {
        "generated": now_iso(),
        # `generated` säger NÄR filen skrevs, inte av VAD. En export som ligger
        # kvar från före en lagning ser annars ut precis som en färsk — se
        # `pipeline/provenance.py` för de två mätta fallen.
        STAMP_KEY: stamp(),
        "source": m.data["source"],
        "system": m.data.get("system"),
        "doc_type": m.data.get("doc_type"),
        "stats": {"pages": len(pages_out), "elements": n_elements,
                  "needs_review": review_total,
                  "missing_pages": missing},
        "pages": pages_out,
    }
    out = export_dir(workdir) / "bok.json"
    atomic_write_json(out, book)
    log.info("sammanfoga: %d sidor, %d element -> %s%s",
             len(pages_out), n_elements, out,
             (" | SAKNAS: sidor %s" % missing) if missing else "")
    return book, out
