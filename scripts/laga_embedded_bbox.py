#!/usr/bin/env python3
"""Lägg om textlagrets `source.bbox` till pipelinens enda bbox-konvention.

`source.bbox` är EN storhet med EN betydelse i hela repot: normaliserad
`[x, y, bredd, höjd]` med y från sidans NEDERKANT. Så skriver
`pipeline/rows.py` (`_box`), och så läser `pipeline/export.py` (styckeindraget
0,018, den fulla raden 0,92, spaltfönstret 0,04), `pipeline/tables.py` och
samtliga bbox-baserade regler i `pipeline/preflight.py`.

Textlagerextraktionen skrev fram till 2026-08-06 in PyMuPDF:s råa blockkanter
i samma fält: `[x0, y0, x1, y1]` i absoluta punkter med y uppifrån. Det är en
ANNAN storhet under samma namn, och ingenting varnade — läsarna räknar
`box[2]` som bredd och `box[3]` som höjd, alltså x1 och y1. Utfallet var inte
tyst men det såg ut som fynd: MUT-AVE-terminal-state fick 236
`forskjuten-kedja` och 22 `radsammanslagning`, 258 av bokens 274
screeningkandidater, allihop artefakter. Sidfoten `TERMINAL STATE 14` mätte
250,8 bred och 627,3 hög på en sida som är 413 punkter bred.

Omräkningen är en MÄTNING, inte en gissning: sidans mått hämtas ur den
arkiverade PDF:en, och bara element som bär `method: "embedded"` OCH en bbox
som inte kan vara normaliserad (något värde > 1,5) rörs. En andra körning rör
noll poster.

    python3 scripts/laga_embedded_bbox.py arbete/<slug> [--pdf <sökväg>] [--verkstall]
"""
import argparse
import json
import os
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fitz  # noqa: E402

# En normaliserad box ligger i [0, 1]. Marginalen tar höjd för avrundning och
# för ett element som sticker ut någon promille utanför sidan.
NORMALISERAD_TAK = 1.5

FILMONSTER = ("page_*.embedded.json", "page_*.validated.json",
              "page_*.final.json")


def _normalisera(bbox, bredd, hojd):
    x0, y0, x1, y1 = bbox
    return [round(x0 / bredd, 6),
            round((hojd - y1) / hojd, 6),
            round((x1 - x0) / bredd, 6),
            round((y1 - y0) / hojd, 6)]


def _ar_absolut(bbox):
    return (isinstance(bbox, (list, tuple)) and len(bbox) == 4
            and all(isinstance(v, (int, float)) for v in bbox)
            and max(bbox) > NORMALISERAD_TAK)


def _hitta_pdf(workdir):
    """Den arkiverade PDF:en är sista sanningskällan — leta upp den, gissa inte."""
    slug = os.path.basename(os.path.normpath(workdir))
    rot = os.path.dirname(os.path.dirname(os.path.abspath(workdir)))
    for katalog in ("arkiv", "import"):
        kandidat = os.path.join(rot, katalog, slug + ".pdf")
        if os.path.exists(kandidat):
            return kandidat
    manifest = os.path.join(workdir, "book.json")
    if os.path.exists(manifest):
        with open(manifest, encoding="utf-8-sig") as fh:
            sokvag = (json.load(fh).get("source") or {}).get("path")
        if sokvag and os.path.exists(sokvag):
            return sokvag
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workdir")
    ap.add_argument("--pdf", help="källa för sidmåtten (default: arkiv/<slug>.pdf)")
    ap.add_argument("--verkstall", action="store_true")
    args = ap.parse_args()

    pdf = args.pdf or _hitta_pdf(args.workdir)
    if not pdf:
        print("HITTAR INGEN PDF för %s — sidmåtten går inte att mäta fram, "
              "och de får inte gissas. Ange --pdf." % args.workdir)
        return 2
    doc = fitz.open(pdf)

    andrade = 0
    filer = 0
    sidor = set()
    for monster in FILMONSTER:
        for fil in sorted(glob.glob(os.path.join(args.workdir, "pages", monster))):
            with open(fil, encoding="utf-8-sig") as fh:
                data = json.load(fh)
            sidnr = data.get("page")
            if not sidnr or sidnr > len(doc):
                continue
            rect = doc[sidnr - 1].rect
            bredd, hojd = rect.width or 1.0, rect.height or 1.0
            rord = 0
            for el in data.get("elements", []):
                kalla = el.get("source") or {}
                if kalla.get("method") != "embedded":
                    continue
                if not _ar_absolut(kalla.get("bbox")):
                    continue
                kalla["bbox"] = _normalisera(kalla["bbox"], bredd, hojd)
                kalla["bbox_source"] = "pipeline.extract_text"
                rord += 1
            if not rord:
                continue
            andrade += rord
            filer += 1
            sidor.add(sidnr)
            if args.verkstall:
                with open(fil, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False, indent=1)
                    fh.write("\n")

    prefix = "" if args.verkstall else "TORRKÖRNING: "
    print("%s%d element normaliserade i %d filer (%d sidor)"
          % (prefix, andrade, filer, len(sidor)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
