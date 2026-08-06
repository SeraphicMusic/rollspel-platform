#!/usr/bin/env python3
"""Ikappkörningens mätvåg: geometri och screening, bok för bok.

Kör Etapp 3 i `docs/IKAPP-ALLA-BOCKER.md` i den ordning planen föreskriver, med
ordkonserveringen kontrollerad efter varje bok:

    radboxar -> binda_rader -> laga_radbas -> sammanfoga -> exportera
             -> diffa -> forbesikta --force

Boken FRYSES inte här. Frysningen är Etapp 0:s och ligger redan på plats; det
är just den `diffa` mäter mot, så en ny frysning mitt i vågen skulle radera
facit och göra kontrollen meningslös.

Ordkonserveringen är spärren. Ändras ordmängden avbryts boken och resten av
vågen fortsätter — en bok som tappar text ska inte döljas av trettio som inte
gör det.

    python3 scripts/matvag.py                 # alla böcker utan geometri
    python3 scripts/matvag.py --bok SLUG      # en bok
    python3 scripts/matvag.py --fran SLUG     # återuppta vid en bok
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROT = Path(__file__).resolve().parents[1]

# Böckerna som redan har geometri. De mäts inte om: del III:s 103 handmätta
# boxar är oersättliga (CLAUDE.md), och del I saknar mätfil helt.
HAR_GEOMETRI = {
    "40-drakar-och-demoner-grundregler-fjarde-utgavan-1991-i-rollpersonen-riotminds",
    "DOD-REG-grundregler-1991-del2-spelledarboken",
    "DOD-REG-grundregler-1991-del3-spelarboken",
    "MUT-AVE-terminal-state-fruncon-91",
}


def kor(*argv, **kw):
    return subprocess.run([sys.executable, *argv], cwd=ROT,
                          capture_output=True, text=True, **kw)


def bokstorlek(wd):
    n = 0
    for f in (wd / "pages").glob("page_*.final.json"):
        n += len(json.loads(f.read_text(encoding="utf-8")).get("elements") or [])
    return n


def med_bbox(wd):
    n = 0
    for f in (wd / "pages").glob("page_*.final.json"):
        for el in json.loads(f.read_text(encoding="utf-8")).get("elements") or []:
            if (el.get("source") or {}).get("bbox"):
                n += 1
    return n


def en_bok(slug, verkstall):
    wd = ROT / "arbete" / slug
    pdf = ROT / "arkiv" / (slug + ".pdf")
    if not pdf.is_file():
        return {"slug": slug, "fel": "käll-PDF saknas i arkiv/"}
    ut = {"slug": slug, "element": bokstorlek(wd), "bbox_fore": med_bbox(wd)}

    r = kor("-m", "pipeline", "radboxar", str(pdf), "--workdir", str(wd),
            "--force")
    if r.returncode:
        return dict(ut, fel="radboxar: %s" % r.stderr.strip()[-200:])

    argv = ["scripts/binda_rader.py", str(wd)]
    if verkstall:
        argv.append("--verkstall")
    r = kor(*argv)
    ut["bindning"] = (r.stdout.strip().splitlines() or ["—"])[-1]

    r = kor("scripts/laga_radbas.py", str(wd))
    ut["radbas"] = (r.stdout.strip().splitlines() or ["—"])[-1]

    for steg in (("sammanfoga",), ("exportera", "--format", "alla")):
        r = kor("-m", "pipeline", steg[0], "--workdir", str(wd), *steg[1:])
        if r.returncode:
            return dict(ut, fel="%s: %s" % (steg[0], r.stderr.strip()[-200:]))

    r = kor("-m", "pipeline", "diffa", "--workdir", str(wd))
    ut["diff"] = r.stdout.strip()
    ut["ordbevarat"] = "Ingen boktext" in r.stdout

    r = kor("-m", "pipeline", "forbesikta", "--workdir", str(wd),
            "--sidor", "1-999", "--force")
    ut["forbesikta"] = r.returncode == 0
    ut["bbox_efter"] = med_bbox(wd)
    return ut


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--bok")
    p.add_argument("--fran")
    p.add_argument("--verkstall", action="store_true",
                   help="skriv bindningen (annars mäts bara)")
    a = p.parse_args(argv)

    böcker = sorted(d.name for d in (ROT / "arbete").iterdir()
                    if (d / "book.json").is_file()
                    and d.name not in HAR_GEOMETRI)
    if a.bok:
        böcker = [b for b in böcker if b == a.bok]
    if a.fran:
        böcker = böcker[böcker.index(a.fran):] if a.fran in böcker else böcker

    fel = []
    print("%-58s %6s %6s %6s  %s" % ("bok", "elem", "bbox", "andel", "ord"))
    for slug in böcker:
        r = en_bok(slug, a.verkstall)
        if r.get("fel"):
            fel.append((slug, r["fel"]))
            print("%-58s FEL: %s" % (slug[:58], r["fel"]))
            continue
        andel = 100.0 * r["bbox_efter"] / max(r["element"], 1)
        print("%-58s %6d %6d %5.0f%%  %s"
              % (slug[:58], r["element"], r["bbox_efter"], andel,
                 "OK" if r["ordbevarat"] else "ORD ÄNDRADE — " + r["diff"][:80]))
        if not r["ordbevarat"]:
            fel.append((slug, "ordkonserveringen bruten"))
    print()
    print("%d böcker, %d fel" % (len(böcker), len(fel)))
    for slug, f in fel:
        print("   %s: %s" % (slug, f))
    return 1 if fel else 0


if __name__ == "__main__":
    sys.exit(main())
