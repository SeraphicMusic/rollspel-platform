#!/usr/bin/env python3
"""Lagar transkript vars source.rader skrevs 1-baserat.

pipeline/jobs.py slår upp radindex 0-baserat. Ett transkript som skrevs
1-baserat får därför varje bbox förskjuten en rad ned, utan att något varnar —
sidan bokförs som godkänd.

Offsetten MÄTS, den gissas inte: agenten skriver själv ut `region` per element,
och mätningen har region per rad. Den offset som får agentens regioner att gå
ihop med mätningens är den rätta. Skriptet rör bara sidor där 1-baserat går
ihop UTAN fel och 0-baserat ger minst ett fel — allt annat lämnas orört.

Idempotent: efter lagningen passar offset 0 bäst och en andra körning rör noll
poster.
"""
import argparse
import json
import pathlib
import sys


def las(p):
    return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))


def passning(element, rader, offset):
    """(träffar, missar) för agentens region mot mätningens vid given offset."""
    ok = fel = 0
    for el in element:
        src = el.get("source") or {}
        idx, region = src.get("rader"), src.get("region")
        if not idx or not region:
            continue
        j = idx[0] - offset
        if 0 <= j < len(rader) and rader[j].get("region") == region:
            ok += 1
        else:
            fel += 1
    return ok, fel


def rakna_bbox(idx, rader):
    boxar = [rader[n]["bbox"] for n in idx]
    x = min(b[0] for b in boxar)
    y = min(b[1] for b in boxar)
    bredd = max(b[0] + b[2] for b in boxar) - x
    hojd = max(b[1] + b[3] for b in boxar) - y
    return [round(v, 5) for v in (x, y, bredd, hojd)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workdir")
    ap.add_argument("--verkstall", action="store_true")
    args = ap.parse_args()

    pages = pathlib.Path(args.workdir) / "pages"
    lagade = 0

    for matning in sorted(pages.glob("page_*.radboxar.json")):
        stam = matning.name.split(".")[0]
        transkript = pages / f"{stam}.transcript.json"
        avvisat = pages / f"{stam}.transcript.json.rejected"
        mal = transkript if transkript.is_file() else avvisat
        if not mal.is_file():
            continue

        rader = las(matning).get("rows") or []
        data = las(mal)
        element = data.get("elements") or []

        ok0, fel0 = passning(element, rader, 0)
        ok1, fel1 = passning(element, rader, 1)
        if not (ok0 + fel0):
            continue

        if not (fel1 == 0 and fel0 > 0 and ok1 > 0):
            print(f"{stam}: orörd (0-bas {ok0}/{fel0}, 1-bas {ok1}/{fel1})")
            continue

        rorda = 0
        for el in element:
            src = el.get("source") or {}
            idx = src.get("rader")
            if not idx:
                continue
            ny = [n - 1 for n in idx]
            if any(n < 0 or n >= len(rader) for n in ny):
                print(f"  {stam}: index {idx} går utanför även efter lagning "
                      f"— AVBRYTER sidan", file=sys.stderr)
                rorda = 0
                break
            src["rader"] = ny
            src["bbox"] = rakna_bbox(ny, rader)
            src["bbox_source"] = "pipeline.rows"
            rorda += 1

        if not rorda:
            continue

        print(f"{stam}: 1-baserad → lagar {rorda} element "
              f"(0-bas {ok0}/{fel0}, 1-bas {ok1}/{fel1})")
        lagade += 1
        if args.verkstall:
            mal.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
            if mal is avvisat:
                mal.rename(transkript)

    print(f"\n{lagade} sidor {'lagade' if args.verkstall else 'skulle lagas'}")


if __name__ == "__main__":
    main()
