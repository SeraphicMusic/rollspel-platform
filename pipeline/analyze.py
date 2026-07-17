"""PDF-analys: dokumenttyps-detektering per sida + boilerplate-igenkänning.

Klasser per sida:
    digital_text          — användbart textlager
    ocr_layer             — skanning med (opålitligt) OCR-lager
    image_only            — enbart bild
    image_with_stub_text  — bild med obetydligt textlager (t.ex. vattenstämpel)
    empty                 — varken text eller bild
"""
from collections import Counter

import fitz

from .manifest import Manifest, default_workdir
from .log import setup_logging

# Trösklar (validerade mot Spindelkonungen-PDF:en, se docs/ANALYS.md)
MIN_CHARS = 20          # färre tecken än så = inget riktigt textlager
STUB_COVERAGE = 0.02    # textarea/sidarea under detta = stub-text
IMG_COVERAGE = 0.5      # bildarea/sidarea över detta = skannad sida
BOILERPLATE_SHARE = 0.5  # samma text på > 50 % av sidorna = boilerplate


def measure_page(page):
    text = page.get_text("text").strip()
    words = page.get_text("words")
    area = page.rect.width * page.rect.height or 1.0

    text_area = sum((w[2] - w[0]) * (w[3] - w[1]) for w in words)
    img_area = 0.0
    for img in page.get_images(full=True):
        try:
            for r in page.get_image_rects(img[0]):
                img_area += r.width * r.height
        except Exception:
            pass

    return {
        "chars": len(text),
        "words": len(words),
        "text_coverage": round(text_area / area, 4),
        "image_coverage": round(min(img_area / area, 1.0), 4),
        "sample": text[:100],
    }


def classify(m):
    if m["chars"] < MIN_CHARS:
        return "image_only" if m["image_coverage"] > IMG_COVERAGE else "empty"
    if m["text_coverage"] < STUB_COVERAGE and m["image_coverage"] > IMG_COVERAGE:
        return "image_with_stub_text"
    if m["image_coverage"] > IMG_COVERAGE and m["text_coverage"] >= STUB_COVERAGE:
        return "ocr_layer"
    return "digital_text"


NEEDS_VISION = {"image_only", "image_with_stub_text", "ocr_layer"}
HAS_TEXT_LAYER = {"digital_text", "ocr_layer"}


def analyze(pdf_path, workdir=None):
    """Skapa/uppdatera manifestet med dokumenttyp per sida. Idempotent."""
    workdir = workdir or default_workdir(pdf_path)
    log = setup_logging(workdir)

    doc = fitz.open(pdf_path)
    try:
        if Manifest.exists(workdir):
            m = Manifest.load(workdir)
            if not m.source_matches(pdf_path):
                raise SystemExit(
                    "Arbetskatalogen %s hör till en annan PDF (sha256 skiljer). "
                    "Välj annan --workdir." % workdir)
            if m.data.get("doc_type"):
                log.info("analysera: redan gjord, hoppar över (%s)", workdir)
                return m
        else:
            meta = {k: v for k, v in doc.metadata.items() if v}
            m = Manifest.create(workdir, pdf_path, len(doc), metadata=meta)

        measures = []
        for i, page in enumerate(doc):
            mm = measure_page(page)
            mm["page"] = i + 1
            measures.append(mm)

        # Boilerplate: identisk textsträng på majoriteten av sidorna
        # (minst 2 förekomster — en ensam sida är inte boilerplate)
        samples = Counter(x["sample"] for x in measures if x["chars"] > 0)
        boilerplate = [s for s, c in samples.items()
                       if c >= 2 and c > len(measures) * BOILERPLATE_SHARE]

        counts = Counter()
        for mm in measures:
            cls = classify(mm)
            # Sidor vars hela textlager är boilerplate är i praktiken stub-text
            if cls in ("digital_text", "ocr_layer") and mm["sample"] in boilerplate:
                cls = ("image_with_stub_text"
                       if mm["image_coverage"] > IMG_COVERAGE else "empty")
            counts[cls] += 1
            p = m.page(mm["page"])
            p["class"] = cls
            p["metrics"] = {k: mm[k] for k in
                            ("chars", "words", "text_coverage", "image_coverage")}

        m.data["doc_type"] = {
            "class_counts": dict(counts),
            "boilerplate": boilerplate,
        }
        m.save()
        log.info("analysera: %d sidor — %s%s",
                 len(measures), dict(counts),
                 (" | boilerplate: %s" % boilerplate) if boilerplate else "")
        return m
    finally:
        doc.close()
