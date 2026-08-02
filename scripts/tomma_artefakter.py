#!/usr/bin/env python3
"""Sätter confidence 1.0 på tömda `page_artifact`-element.

Ett element som en advokat har tömt (illustratörssignatur i motivet,
vattenstämpel) har inget innehåll kvar att vara osäker på — men det behåller
transkriptionens gamla confidence, typiskt 0,30, och dyker därför upp som
lågkonfidenspost i varje framtida screening. Tre advokater i rad har rapporterat
det som brus (s. 14, 20, 65).

Villkoret är snävt med flit: tom text, typen `page_artifact`, och minst en
applicerad korrektionspost som tömde elementet (`corrected` == ""). Ett tomt
element som ingen har dömt om rörs inte.

    python3 tomma_artefakter.py <arbetskatalog> [--verkstall]
"""
import argparse
import json
import pathlib

REASON = ("Elementet är tömt av advokat; det finns inget innehåll kvar att vara "
          "osäker på. Confidence höjd till 1,0 så att det inte återkommer som "
          "falsk lågkonfidenspost i screeningarna. Ingen text ändrad.")


def sveep(workdir, verkstall):
    pages = pathlib.Path(workdir) / "pages"
    rorda = []
    for f in sorted(pages.glob("page_*.final.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        andrad = False
        for el in data.get("elements", []):
            if el.get("type") != "page_artifact":
                continue
            if (el.get("text") or "") != "":
                continue
            # Samma gräns som screeningen använder — ett element på 0,99 är
            # ingen lågkonfidenspost och behöver ingen post om saken.
            if (el.get("confidence") or 1.0) >= 0.8:
                continue
            tomd = any(c.get("applied") and c.get("corrected") == ""
                       for c in (el.get("corrections") or []))
            if not tomd:
                continue
            fore = el.get("confidence")
            el["confidence"] = 1.0
            el.setdefault("corrections", []).append({
                "original": "", "corrected": "",
                "applied": True, "confidence": 1.0,
                "reason": REASON + " Tidigare confidence: %s." % fore,
                "source": "agent:djavulens-advokat",
                "kind": "ocr",
                "verdict": "applicerad",
                "adjudicated_by": "agent:djavulens-advokat (svepning 2026-08-02)",
                "timestamp": "2026-08-02T00:00:00Z",
            })
            rorda.append((f.name, el.get("id"), fore))
            andrad = True
        if andrad and verkstall:
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    return rorda


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workdir")
    ap.add_argument("--verkstall", action="store_true")
    args = ap.parse_args()
    rorda = sveep(args.workdir, args.verkstall)
    print("%s: %d tömda artefakter" %
          ("SKRIVET" if args.verkstall else "TORRKÖRNING", len(rorda)))
    for f, eid, fore in rorda:
        print("   ", f, eid, fore)


if __name__ == "__main__":
    main()
