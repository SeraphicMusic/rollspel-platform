#!/usr/bin/env python3
"""Härled rubriknivåer ur bokens EGEN innehållsförteckning.

Användning:
    python3 scripts/rubriknivaer.py <slug> --toc 2            # visa planen
    python3 scripts/rubriknivaer.py <slug> --toc 2 --verkstall # skriv den

Serien Drakar och Demoner 1991 graderas **kapitel 1 / sektion 2 / underrubrik 3**
(användarens beslut C, 2026-08-01). Skalan går inte att läsa ur en enskild sidas
typografi — trycket blandar versaler och kapitäler i jämnstora rubriker — men den
står tydligt i böckernas innehållsförteckning, som sätts i tre spalter med tre
indragslägen per spalt:

    kapitel   spaltens vänsterkant
    sektion   +0,019 av sidbredden
    underrubrik  +0,039

Indraget MÄTS i sidbilden (vänstraste svarta pixeln i radens band). De lagrade
bboxarna duger inte till just detta: radbandet för `VARELSER` i del II börjar
0,016 för långt in, vilket räcker för att flytta ett kapitel ett steg ned.

En rubrik som inte står i innehållsförteckningen kan aldrig vara ett kapitel —
alla kapitel OCH sektioner är listade där. Den behåller därför draftens
inbördes ordning, förskjuten ett steg ned.
"""
import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.manifest import page_file, pages_dir, read_json  # noqa: E402

INDENT = 0.0195       # indragssteget, uppmätt i båda böckerna
COLUMN_GAP = 0.15     # minsta sidledsavstånd mellan två TOC-spalter
DARK = 128            # tröskel för "svart pixel" i sidbilden
MAX_LEVEL = 3         # kontraktets djupaste rubriknivå

_LEADER = re.compile(r"\s*\.{2,}.*$|\s+\.\.\.\s.*$")


def normalise(text):
    """Jämförbar form: utan punktledare, utan skiljetecken, versalt."""
    text = _LEADER.sub("", text or "").strip()
    return re.sub(r"[\s ]+", " ", text).upper().rstrip(":.").strip()


def columns_of(lefts):
    """Spalternas vänsterkanter, klustrade på avstånd."""
    out = []
    for x in sorted(lefts):
        if not out or x - out[-1] > COLUMN_GAP:
            out.append(x)
    return out


def indent_levels(measured):
    """[(nyckel, nivå)] ur (nyckel, spaltindex, uppmätt vänsterkant).

    Nivån är antalet indragssteg från spaltens egen vänsterkant, plus ett.
    Djupare indrag än kontraktets tre nivåer klipps till 3.
    """
    bases = {}
    for _key, column, left in measured:
        bases[column] = min(bases.get(column, left), left)
    out = []
    for key, column, left in measured:
        step = int(round((left - bases[column]) / INDENT))
        out.append((key, min(max(step, 0) + 1, MAX_LEVEL)))
    return out


def measure_toc(workdir, toc_page):
    """{normaliserad titel: nivå} ur innehållsförteckningens indrag."""
    import numpy as np
    from PIL import Image

    pagedir = pages_dir(workdir)
    data = read_json(page_file(workdir, toc_page, "final.json"))
    image = np.asarray(Image.open(pagedir / ("page_%03d.png" % toc_page))
                       .convert("L"))
    height, width = image.shape
    entries = []
    for el in data["elements"]:
        bbox = (el.get("source") or {}).get("bbox")
        if el.get("type") == "toc_entry" and bbox:
            entries.append((el, bbox))
    if not entries:
        raise SystemExit("s.%d har inga toc_entry med bbox" % toc_page)
    columns = columns_of(bbox[0] for _el, bbox in entries)
    measured = []
    for el, (x0, y, _w, h) in entries:
        index = max(i for i, c in enumerate(columns) if x0 >= c - 0.01)
        lo = columns[index] - 0.02
        hi = (columns[index + 1] - 0.02) if index + 1 < len(columns) else 0.99
        # y räknas från sidans nederkant (se AGENTER.md Regel 9).
        top = max(0, int((1 - (y + h)) * height) - 1)
        band = image[top:int((1 - y) * height) + 1,
                     int(lo * width):int(hi * width)] < DARK
        hits = np.flatnonzero(band.any(axis=0))
        left = lo + hits[0] / width if len(hits) else x0
        measured.append((normalise(el.get("text")), index, left))
    levels = {}
    for key, level in indent_levels(measured):
        levels.setdefault(key, level)
    return levels


OUTSIDE = "utanför TOC"


def plan_level(page, el, levels, toc_page):
    """(nivå, motivering) för en rubrik.

    En rubrik utanför innehållsförteckningen graderas ur draftens egen nivå,
    och den regeln har ingen fixpunkt — körs den två gånger sjunker rubriken
    två steg. Därför stämplas motiveringen i `level_source` när nivån skrivs,
    och en redan graderad rubrik räknas aldrig om. Det gör steget idempotent
    som pipelinens övriga (CLAUDE.md) och visar samtidigt VARFÖR varje rubrik
    hamnade på sin nivå.
    """
    if page < toc_page:
        return el.get("level"), "omslag — orört"
    if page == toc_page:
        # Del I lägger alla titelsidans rubriker på 1; serien harmoniseras
        # mot den (beslut.md, s. 2).
        return 1, "titelsida — harmoniserad mot del I"
    level = levels.get(normalise(el.get("text")))
    if level is not None:
        return level, "TOC"
    if el.get("level_source") == OUTSIDE:
        return el.get("level"), OUTSIDE
    return min((el.get("level") or 2) + 1, MAX_LEVEL), OUTSIDE


def plan(workdir, toc_page):
    levels = measure_toc(workdir, toc_page)
    rows = []
    for path in sorted(pages_dir(workdir).glob("page_*.final.json")):
        data = read_json(path)
        for el in data["elements"]:
            if el.get("type") != "heading":
                continue
            level, why = plan_level(data["page"], el, levels, toc_page)
            rows.append((path, data["page"], el.get("id"), el.get("level"),
                         level, why, el.get("text") or ""))
    return levels, rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug")
    parser.add_argument("--toc", type=int, default=2,
                        help="sidan med innehållsförteckningen")
    parser.add_argument("--verkstall", action="store_true",
                        help="skriv nivåerna till page_NNN.final.json")
    args = parser.parse_args(argv)

    workdir = ROOT / "arbete" / args.slug
    levels, rows = plan(workdir, args.toc)
    kapitel = sorted(k for k, v in levels.items() if v == 1)
    print("innehållsförteckningen: %d titlar, %d kapitel"
          % (len(levels), len(kapitel)))
    for title in kapitel:
        print("  kapitel  %s" % title)
    changed = [r for r in rows if r[3] != r[4]]
    print("%d rubriker, %d byter nivå" % (len(rows), len(changed)))
    for _path, page, eid, old, new, why, text in changed:
        print("  s.%-3d %-10s %s -> %s  [%s]  %s"
              % (page, eid, old, new, why, text[:52]))
    if not args.verkstall:
        return 0
    # Alla rubriker stämplas, inte bara de ändrade: stämpeln är det som gör
    # om-körningen till ett nollresultat.
    for path in sorted({r[0] for r in rows}):
        data = read_json(path)
        wanted = {r[2]: (r[4], r[5]) for r in rows if r[0] == path}
        for el in data["elements"]:
            if el.get("id") not in wanted:
                continue
            level, why = wanted[el["id"]]
            if level is not None:
                el["level"] = level
            el["level_source"] = why
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print("verkställt: %d ändrade rubriker, %d stämplade på %d sidor"
          % (len(changed), len(rows), len({r[0] for r in rows})))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
