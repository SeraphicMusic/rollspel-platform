#!/usr/bin/env python3
"""Skriver ut `verdict: "avvisad"` på poster som redan är avvisade i klartext.

Fältet `verdict` kom till efter att korrekturen var gjord. En advokat som
avvisade ett förslag skrev domen i `reason` ("AVVISAD som dubblett: …") och lät
posten ligga kvar med `applied: false`. Sakligt är den avgjord, men eftersom
domen bara står i prosa räknas posten som odömd av varje fältkontroll — fyra
advokater i efterkörningen har rapporterat det som brus.

Villkoret är avsiktligt strikt: posten måste vara oapplicerad, sakna `verdict`,
och ha ordet AVVISAD som eget ord i `reason`. Ingen tolkning, ingen gissning.
`adjudicated_by` sätts till en svepningsmarkering, inte till en påhittad
författare — vem som skrev domen står i postens `source`.

    python3 materialisera_verdict.py <arbetskatalog> [--verkstall]
"""
import argparse
import json
import pathlib
import re

# Två formuleringar räknas som en utskriven dom: advokatens "AVVISAD" och
# heuristikens "DUBBLETT" (rättningen är redan verkställd via en annan post på
# samma element, och heuristikposten ligger kvar enbart för spårbarhet).
AVVISAD = re.compile(r"\bAVVISAD\b|\bDUBBLETT\b|\bDubblett av heuristiken\b")


def sveep(workdir, verkstall):
    pages = pathlib.Path(workdir) / "pages"
    rorda = []
    for f in sorted(pages.glob("page_*.final.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        andrad = False
        for el in data.get("elements", []):
            for c in el.get("corrections", []) or []:
                if c.get("applied") or c.get("verdict"):
                    continue
                if not AVVISAD.search(c.get("reason") or ""):
                    continue
                c["verdict"] = "avvisad"
                c["adjudicated_by"] = (
                    "%s (dom fanns i reason, fältsatt i svepning 2026-08-02)"
                    % c.get("source", "okänd"))
                rorda.append((f.name, el.get("id"), c.get("source")))
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
    print("%s: %d poster fältsatta som avvisade" %
          ("SKRIVET" if args.verkstall else "TORRKÖRNING", len(rorda)))
    for f, eid, kalla in rorda:
        print("   ", f, eid, kalla)


if __name__ == "__main__":
    main()
