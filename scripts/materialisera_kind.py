#!/usr/bin/env python3
"""Skriver ut `kind` på korrektionsposter som saknar fältet.

Regeln är exakt den som `pipeline/report.py:_correction_kind` redan tillämpar
när fältet saknas, så rapporten ser samma sak före och efter. Skillnaden är att
härledningen nu står i filen i stället för att göras om vid varje läsning —
vilket är hela poängen med ett obligatoriskt fält.

Idempotent: en post som redan har `kind` rörs aldrig.

    python3 materialisera_kind.py <arbetskatalog> [--verkstall]
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path.cwd()))

from pipeline.report import _correction_kind  # noqa: E402


def sveep(workdir, verkstall):
    pages = pathlib.Path(workdir) / "pages"
    total = 0
    per_kind = {}
    rorda_filer = 0
    for f in sorted(pages.glob("page_*.final.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        andrad = False
        for el in data.get("elements", []):
            for c in el.get("corrections", []) or []:
                if c.get("kind"):
                    continue
                kind = _correction_kind(c)
                per_kind[kind] = per_kind.get(kind, 0) + 1
                total += 1
                andrad = True
                if verkstall:
                    c["kind"] = kind
        if andrad and verkstall:
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                         encoding="utf-8")
            rorda_filer += 1
        elif andrad:
            rorda_filer += 1
    return total, per_kind, rorda_filer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workdir")
    ap.add_argument("--verkstall", action="store_true")
    args = ap.parse_args()
    total, per_kind, filer = sveep(args.workdir, args.verkstall)
    lage = "SKRIVET" if args.verkstall else "TORRKÖRNING"
    print("%s: %d poster utan kind i %d sidor" % (lage, total, filer))
    for k, n in sorted(per_kind.items()):
        print("   %-12s %d" % (k, n))


if __name__ == "__main__":
    main()
