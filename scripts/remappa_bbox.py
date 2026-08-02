#!/usr/bin/env python3
"""Kopplar om föråldrade radboxar till den lagade mätningen.

Bakgrund: mätningen före 2026-08-01 hade sex defekter (commit 4014959). Den
grövsta för de här elementen är att sidor satta i liten grad — registret s. 63 —
fick varje tryckt rad delad i TVÅ band, så den sparade boxen är ett fragment av
den riktiga raden. Remappen efter lagningen matchade på radindex, och för 87
element gick det inte; de fick i stället flaggan att bboxen är den gamla
mätningens och ska verifieras.

Fragmentet ligger per konstruktion inuti den riktiga raden. Därför finns en
deterministisk återkoppling: den nya mätningens rad vars band innehåller
fragmentets mittpunkt. Är det exakt en rad är tilldelningen entydig och hämtad
ur mätningen — ingen gissning. Täcker ingen rad fragmentet tas bboxen bort:
en saknad box är en lucka i en heuristik, en påhittad box är ett fel som ser ut
som data.

Gamla koordinater bevaras i korrektionspostens `original`.

    python3 remappa_bbox.py <arbetskatalog> [--verkstall]
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path.cwd()))

from pipeline.corrections import close_review_reason  # noqa: E402

FLAGGA = "radboxar ommätta"


def _tacker(rad, cx, cy):
    x, y, w, h = rad
    return x <= cx <= x + w and y <= cy <= y + h


def sveep(workdir, verkstall):
    pages = pathlib.Path(workdir) / "pages"
    remappade, borttagna, utan = [], [], []
    for f in sorted(pages.glob("page_*.final.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        no = int(f.name[5:8])
        rbf = pages / ("page_%03d.radboxar.json" % no)
        rader = (json.loads(rbf.read_text(encoding="utf-8"))["rows"]
                 if rbf.exists() else [])
        andrad = False
        for el in data.get("elements", []):
            skal = [str(r) for r in el.get("review_reasons") or []]
            if not any(FLAGGA in r for r in skal):
                continue
            kalla = el.setdefault("source", {})
            bb = kalla.get("bbox")
            if not bb:
                utan.append((no, el.get("id")))
                _stang(el, skal, "Elementet har ingen bbox att verifiera — "
                                 "flaggan gäller geometri som inte finns.")
                andrad = True
                continue
            cx, cy = bb[0] + bb[2] / 2.0, bb[1] + bb[3] / 2.0
            inne = [r for r in rader if _tacker(r["bbox"], cx, cy)]
            if len(inne) == 1:
                ny = inne[0]["bbox"]
                el.setdefault("corrections", []).append({
                    "original": "source.bbox: %s" % json.dumps(bb),
                    "corrected": "source.bbox: %s" % json.dumps(ny),
                    "applied": True,
                    "confidence": 0.95,
                    "reason": (
                        "Bboxen kom från mätningen före lagningen 2026-08-01 "
                        "(commit 4014959) och var ett fragment av den tryckta "
                        "raden. Den lagade mätningen i page_%03d.radboxar.json "
                        "har exakt EN rad vars band innehåller fragmentets "
                        "mittpunkt (%.4f, %.4f); den raden är elementets box. "
                        "Tilldelningen är hämtad ur mätningen, inte gissad, och "
                        "regionen sätts från samma rad." % (no, cx, cy)),
                    "source": "pipeline.rows (remap 2026-08-02)",
                    "kind": "ocr",
                    "verdict": "applicerad",
                    "adjudicated_by": "pipeline.rows (deterministisk remap)",
                    "timestamp": "2026-08-02T00:00:00Z",
                })
                kalla["bbox"] = ny
                if inne[0].get("region"):
                    kalla["region"] = inne[0]["region"]
                kalla["bbox_source"] = "pipeline.rows (remap 2026-08-02)"
                remappade.append((no, el.get("id")))
                _stang(el, skal, "Bboxen är omkopplad till den lagade "
                                 "mätningens rad; se korrektionsposten.")
            else:
                el.setdefault("corrections", []).append({
                    "original": "source.bbox: %s" % json.dumps(bb),
                    "corrected": "source.bbox: saknas",
                    "applied": True,
                    "confidence": 0.9,
                    "reason": (
                        "Bboxen kom från mätningen före lagningen 2026-08-01 "
                        "och ingen rad i den lagade mätningen täcker dess "
                        "mittpunkt (%.4f, %.4f) — %d kandidater. Måttet är "
                        "alltså inte bekräftat av mätningen och tas bort i "
                        "stället för att behållas eller gissas om. Texten är "
                        "orörd." % (cx, cy, len(inne))),
                    "source": "pipeline.rows (remap 2026-08-02)",
                    "kind": "ocr",
                    "verdict": "applicerad",
                    "adjudicated_by": "pipeline.rows (deterministisk remap)",
                    "timestamp": "2026-08-02T00:00:00Z",
                })
                kalla.pop("bbox", None)
                kalla["bbox_source"] = "borttagen 2026-08-02 (obekräftad)"
                borttagna.append((no, el.get("id")))
                _stang(el, skal, "Den obekräftade bboxen är borttagen; "
                                 "se korrektionsposten.")
            andrad = True
        if andrad and verkstall:
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    return remappade, borttagna, utan


def _stang(el, skal, losning):
    """Avgör geometriflaggan via pipelinens egen stängning."""
    for r in skal:
        if FLAGGA in r:
            close_review_reason(el, r, losning,
                                "pipeline.rows (remap 2026-08-02)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workdir")
    ap.add_argument("--verkstall", action="store_true")
    args = ap.parse_args()
    r, b, u = sveep(args.workdir, args.verkstall)
    print("%s: %d remappade, %d borttagna, %d utan bbox"
          % ("SKRIVET" if args.verkstall else "TORRKÖRNING",
             len(r), len(b), len(u)))


if __name__ == "__main__":
    main()
