"""Textlagerextraktion för digital_text-sidor (och som hint för ocr_layer).

Producerar page_NNN.embedded.json med element enligt den kanoniska modellen:
kolumnmedveten läsordning, rubriknivåer via typsnittsstorlek och detektering av
återkommande sidhuvuden/sidfötter/sidnummer (klassas som page_artifact).
"""
import re
import statistics
from collections import Counter

import fitz

from .analyze import HAS_TEXT_LAYER
from .log import setup_logging
from .manifest import Manifest, atomic_write_json, page_file

EDGE_BAND = 0.08          # övre/nedre 8 % av sidan = kandidatzon för sidhuvud/-fot
REPEAT_SHARE = 0.35       # mönster på >35 % av sidorna = återkommande artefakt
HEADING_RATIO = 1.25      # > 125 % av brödtextstorleken = rubrik


def _block_text(block):
    lines = []
    for line in block.get("lines", []):
        txt = "".join(span["text"] for span in line.get("spans", []))
        lines.append(txt)
    return "\n".join(lines).strip()


def _block_font_size(block):
    sizes = [span["size"] for line in block.get("lines", [])
             for span in line.get("spans", [])]
    return statistics.median(sizes) if sizes else 0.0


def _dominant_font_size(blocks):
    weighted = []
    for b in blocks:
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                weighted.extend([span["size"]] * max(len(span["text"]), 1))
    return statistics.median(weighted) if weighted else 10.0


def _split_block_columns(block, page_width):
    """Dela block vars rader ligger i horisontellt åtskilda kluster (spalter).

    OCR-lager (och PyMuPDF:s radgruppering) slår ibland ihop text från två
    spalter på samma baslinje till ett block — det förstör läsordningen.
    """
    lines = block.get("lines", [])
    if len(lines) < 2:
        return [block]
    mids = sorted(((ln["bbox"][0] + ln["bbox"][2]) / 2, i)
                  for i, ln in enumerate(lines))
    best_gap, split = 0.0, None
    for (a, _), (b, _) in zip(mids, mids[1:]):
        if b - a > best_gap:
            best_gap, split = b - a, (a + b) / 2
    if split is None or best_gap < page_width * 0.2:
        return [block]
    groups = ([], [])
    for ln in lines:
        mid = (ln["bbox"][0] + ln["bbox"][2]) / 2
        groups[0 if mid < split else 1].append(ln)
    out = []
    for grp in groups:
        if not grp:
            continue
        bbox = [min(l["bbox"][0] for l in grp), min(l["bbox"][1] for l in grp),
                max(l["bbox"][2] for l in grp), max(l["bbox"][3] for l in grp)]
        out.append({"type": 0, "bbox": bbox,
                    "lines": sorted(grp, key=lambda l: l["bbox"][1])})
    return out if len(out) > 1 else [block]


def _columns(blocks, page_width):
    """Dela in block i kolumner via x-mittpunkt; returnera sorterad läsordning."""
    if not blocks:
        return []
    mids = sorted((b["bbox"][0] + b["bbox"][2]) / 2 for b in blocks)
    # Hitta största gapet i mittpunkterna; > 20 % av sidbredden => två kolumner
    best_gap, split = 0.0, None
    for a, b in zip(mids, mids[1:]):
        if b - a > best_gap:
            best_gap, split = b - a, (a + b) / 2
    if split is None or best_gap < page_width * 0.2:
        return [sorted(blocks, key=lambda b: b["bbox"][1])]
    left = [b for b in blocks if (b["bbox"][0] + b["bbox"][2]) / 2 < split]
    right = [b for b in blocks if (b["bbox"][0] + b["bbox"][2]) / 2 >= split]
    return [sorted(c, key=lambda b: b["bbox"][1]) for c in (left, right) if c]


def _artifact_key(text, y_rel):
    """Nyckel för återkommande topp-/bottentexter; sidnummer normaliseras."""
    norm = re.sub(r"\d+", "#", text.strip().lower())
    return (norm[:60], "top" if y_rel < 0.5 else "bottom")


def collect_artifacts(doc, manifest):
    """Hitta text som återkommer i sidkanten över många sidor (sidhuvud/-fot)."""
    counter = Counter()
    text_pages = 0
    for no in manifest.page_numbers():
        if manifest.page(no)["class"] not in HAS_TEXT_LAYER:
            continue
        text_pages += 1
        page = doc[no - 1]
        h = page.rect.height or 1.0
        for b in page.get_text("dict")["blocks"]:
            if b.get("type") != 0:
                continue
            y_rel = b["bbox"][1] / h
            if y_rel < EDGE_BAND or (b["bbox"][3] / h) > 1 - EDGE_BAND:
                txt = _block_text(b)
                if txt:
                    counter[_artifact_key(txt, y_rel)] += 1
    threshold = max(2, int(text_pages * REPEAT_SHARE))
    return {k for k, c in counter.items() if c >= threshold}


def _normalized_box(bbox, width, height):
    """PyMuPDF:s `[x0, y0, x1, y1]` (punkter, y uppifrån) -> pipelinens form.

    `source.bbox` är EN storhet med EN betydelse i hela repot: normaliserad
    `[x, y, bredd, höjd]` med y från sidans NEDERKANT — så skriver
    `pipeline/rows.py` (`_box`) och så läser `pipeline/export.py` (indraget
    0,018, den fulla raden 0,92, spaltfönstret 0,04) och `pipeline/tables.py`.

    Textlagret skrev tidigare PyMuPDF:s råa kanter rakt in i samma fält. Formen
    är en annan storhet med samma namn, och ingenting varnade: `preflight`
    läser `box[2]` som BREDD, fick x1, och gav 236 `forskjuten-kedja` på
    MUT-AVE-terminal-state — 86 % av bokens screening — plus 22
    `radsammanslagning` där `box[3]` lästes som höjd men var y1. Sidfoten
    `TERMINAL STATE 14` mätte då 250,8 bred och 627,3 hög.
    """
    x0, y0, x1, y1 = bbox
    return [round(x0 / width, 6),
            round((height - y1) / height, 6),
            round((x1 - x0) / width, 6),
            round((y1 - y0) / height, 6)]


def extract_page(page, page_no, boilerplate, artifacts, dominant_size):
    h = page.rect.height or 1.0
    w = page.rect.width or 1.0
    blocks = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") == 0:
            blocks.extend(_split_block_columns(b, page.rect.width))
    elements = []
    n_cols = 0
    cols = _columns(blocks, page.rect.width)
    n_cols = len(cols)
    idx = 0
    for ci, col in enumerate(cols):
        for b in col:
            text = _block_text(b)
            if not text:
                continue
            idx += 1
            el = {
                "id": "p%03d_e%02d" % (page_no, idx),
                "type": "paragraph",
                "text": text,
                "source": {
                    "page": page_no,
                    "bbox": _normalized_box(b["bbox"], w, h),
                    "bbox_source": "pipeline.extract_text",
                    "region": ("kolumn %d" % (ci + 1)) if n_cols > 1 else "huvudtext",
                    "method": "embedded",
                },
                "confidence": 1.0,
                "corrections": [],
                "needs_review": False,
            }
            y_rel = b["bbox"][1] / h
            is_edge = y_rel < EDGE_BAND or (b["bbox"][3] / h) > 1 - EDGE_BAND
            if text in boilerplate or (
                    is_edge and _artifact_key(text, y_rel) in artifacts):
                el["type"] = "page_artifact"
            elif re.fullmatch(r"\d{1,4}", text) and is_edge:
                el["type"] = "page_artifact"
            else:
                size = _block_font_size(b)
                if size > dominant_size * HEADING_RATIO and len(text) < 120:
                    el["type"] = "heading"
                    el["level"] = 1 if size > dominant_size * 1.7 else 2
            elements.append(el)
    return {"page": page_no, "layout": {"columns": max(n_cols, 1)},
            "elements": elements}


def extract_text(pdf_path, workdir, pages=None):
    """Extrahera textlager för alla sidor med användbart textlager. Idempotent."""
    log = setup_logging(workdir)
    m = Manifest.load(workdir)
    doc = fitz.open(pdf_path)
    done = skipped = 0
    try:
        boilerplate = set(m.data.get("doc_type", {}).get("boilerplate", []))
        artifacts = collect_artifacts(doc, m)
        dominant = None
        for no in m.page_numbers():
            if pages and no not in pages:
                continue
            p = m.page(no)
            if p["class"] not in HAS_TEXT_LAYER:
                continue
            out = page_file(workdir, no, "embedded.json")
            if out.is_file():
                skipped += 1
            else:
                try:
                    page = doc[no - 1]
                    if dominant is None:
                        blocks = [b for b in page.get_text("dict")["blocks"]
                                  if b.get("type") == 0]
                        dominant = _dominant_font_size(blocks)
                    result = extract_page(page, no, boilerplate, artifacts,
                                          dominant)
                    atomic_write_json(out, result)
                    done += 1
                except Exception as e:
                    p["error"] = "extract_text: %s" % e
                    log.exception("sida %d kunde inte extraheras", no)
                    continue
            # Rena digital_text-sidor är klara för validering direkt
            if p["class"] == "digital_text" and not m.state_at_least(no, "extracted"):
                m.set_state(no, "extracted")
        m.save()
        log.info("extrahera-text: %d nya, %d fanns redan", done, skipped)
        return done, skipped
    finally:
        doc.close()
