"""Sidrendering till PNG — idempotent och atomisk (Släktforskaren-mönstret).

Endast sidor som behöver vision-transkription renderas (klass image_* / ocr_layer),
om inte `all_pages=True`. Redan renderade sidor hoppas över.
"""
import os
from pathlib import Path

import fitz

from .analyze import NEEDS_VISION
from .log import setup_logging
from .manifest import Manifest, now_iso, page_file

DEFAULT_DPI = 150
MAX_DIM = 1950  # Claudes bildgräns för multi-image-läsning


def render_page(page, out_path, dpi=DEFAULT_DPI, max_dim=MAX_DIM):
    w_px = page.rect.width * dpi / 72
    h_px = page.rect.height * dpi / 72
    if max(w_px, h_px) > max_dim:
        dpi = int(dpi * max_dim / max(w_px, h_px))
    pix = page.get_pixmap(dpi=dpi)
    tmp = str(out_path) + ".part"
    pix.save(tmp, output="png")
    os.replace(tmp, out_path)
    return pix.width, pix.height, dpi


def render(pdf_path, workdir, pages=None, dpi=DEFAULT_DPI, all_pages=False,
           grayscale=False):
    """Rendera nödvändiga sidor. `pages` begränsar urvalet (lista av sidnummer)."""
    log = setup_logging(workdir)
    m = Manifest.load(workdir)
    doc = fitz.open(pdf_path)
    done = skipped = 0
    try:
        for no in m.page_numbers():
            if pages and no not in pages:
                continue
            p = m.page(no)
            if not all_pages and p["class"] not in NEEDS_VISION:
                continue
            out = page_file(workdir, no, "png")
            if out.is_file() and out.stat().st_size > 0:
                skipped += 1
                if not m.state_at_least(no, "rendered"):
                    m.set_state(no, "rendered")
                continue
            try:
                w, h, used_dpi = render_page(doc[no - 1], out, dpi=dpi)
                if grayscale:
                    _to_grayscale(out)
                # NEDGRADERA ALDRIG. Skip-grenen ovan har spärren, den här
                # hade den inte — och `rendera --alla` på en färdig bok satte
                # 29 av MUT-AVE-terminal-states sidor tillbaka från `validated`
                # till `rendered`. Ingenting varnade; felet syntes först när
                # `arkivera` vägrade med 29 hinder, långt efter att sidorna var
                # korrekturlästa. Att rendera en PNG säger ingenting om vad
                # sidan redan gått igenom.
                if not m.state_at_least(no, "rendered"):
                    m.set_state(no, "rendered")
                else:
                    m.page(no)["steps"]["rendered"] = now_iso()
                done += 1
                log.debug("renderade sida %d (%dx%d @ %d DPI)", no, w, h, used_dpi)
            except Exception as e:  # felisolering per sida
                p["error"] = "render: %s" % e
                log.exception("sida %d kunde inte renderas", no)
        m.save()
        log.info("rendera: %d nya, %d fanns redan", done, skipped)
        return done, skipped
    finally:
        doc.close()


def _to_grayscale(png_path):
    pix = fitz.Pixmap(str(png_path))
    gray = fitz.Pixmap(fitz.csGRAY, pix)
    tmp = str(png_path) + ".part"
    gray.save(tmp, output="png")
    os.replace(tmp, png_path)
