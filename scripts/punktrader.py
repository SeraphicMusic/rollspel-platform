#!/usr/bin/env python3
"""Typar om punktrader som ligger som `paragraph` till `list_item`.

En rad som börjar med punkttecken ÄR en listpunkt. Ligger den som `paragraph`
behandlar läsexportens omflödning den som vanlig löptext och fogar in den i
föregående stycke: `bok.md` fick raden

    Hjältepoäng kan användas till följande tre saker: • Höja CL

där trycket har en rubrikmening och tre punkter under. Listan är då borta som
struktur, och punkttecknet står kvar mitt i en mening som skräp.

Hittad av `forbesikta`s driftregel: `list` användes på del I:s sidor 10–37 och
sedan aldrig mer, trots att boken har punktlistor ända till s. 65.

Texten rörs inte — punkttecknet stannar i raden enligt transkriptionskontraktet
(`• Köpa ras`). Bara elementtypen ändras.

    python3 punktrader.py <arbetskatalog> [--verkstall]
"""
import argparse
import json
import pathlib

# Punkttecken som förekommer i trycket. Bindestreck och tankstreck är med
# flit UTESLUTNA: en rad som börjar med streck är oftast ett radbrutet
# sammansättningsled eller en linjeregelrest, inte en listpunkt.
BULLETS = ("•", "·", "●", "▪", "‣")


def _post(text):
    return {
        "original": "type: paragraph",
        "corrected": "type: list_item",
        "applied": True,
        "confidence": 0.97,
        "reason": (
            "Raden inleds med punkttecken och är alltså en listpunkt, men låg "
            "som `paragraph`. Läsexportens omflödning behandlade den då som "
            "löptext och fogade in den i föregående stycke — punkten försvann "
            "som struktur och punkttecknet blev skräp mitt i en mening. "
            "Texten %r är oförändrad; punkttecknet stannar i raden enligt "
            "transkriptionskontraktet." % text[:60]),
        "source": "svepning (punktrader)",
        "kind": "ocr",
        "verdict": "applicerad",
        "adjudicated_by": "svepning (punktrader)",
        "timestamp": "2026-08-02T00:00:00Z",
    }


def sveep(workdir, verkstall):
    pages = pathlib.Path(workdir) / "pages"
    rorda = []
    for f in sorted(pages.glob("page_*.final.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        no = int(f.name[5:8])
        andrad = False
        for el in data.get("elements", []):
            if el.get("type") != "paragraph":
                continue
            text = (el.get("text") or "").strip()
            if not text.startswith(BULLETS):
                continue
            el.setdefault("corrections", []).append(_post(text))
            el["type"] = "list_item"
            rorda.append((no, el.get("id"), text[:50]))
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
    print("%s: %d punktrader omtypade"
          % ("SKRIVET" if args.verkstall else "TORRKÖRNING", len(rorda)))
    for no, eid, text in rorda:
        print("   s.%-3d %-14s %s" % (no, eid, text))


if __name__ == "__main__":
    main()
