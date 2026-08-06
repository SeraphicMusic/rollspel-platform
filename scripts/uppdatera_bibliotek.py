#!/usr/bin/env python3
"""Uppdatera `bibliotek/` ur `arbete/<slug>/export/bok.md`.

Läskopiorna är det man matar till andra agenter och verktyg, och de har ingen
egen historik — de är kopior. Ändå har de drivit isär från exporterna varje
gång: `bibliotek/…del2` bar brytfel som redan var lagade i `pipeline/export.py`
(CLAUDE.md), och Spindelkonungens två kopior var från 20 juli mot en export
byggd 5 augusti. Orsaken är alltid densamma — kopieringen var en punkt i en
README, alltså en instruktion till en människa, och ingenting körde den.

Kopieringen kontrollerar ORDMÄNGDEN, inte bara filstorleken. En omflödning får
ändra styckeindelning och radbrytning hur mycket som helst; går ord förlorade
är det ett fel och kopian skrivs inte.

Men en korrekturläst bok TAPPAR ord med flit — `spårar` blir `spöar`, `annnan`
blir `annan` — och en spärr som fäller varje sådan bok lär användaren att köra
förbi den. Bortfallet attribueras därför mot sidfilernas applicerade
korrektionsposter (`scripts/oforklarade_ord.py`): är varje förlorat ord täckt
av en post som utger sig för att ha orsakat det, skrivs kopian och posterna
redovisas. Det som ingen post bär spärrar fortfarande.

    python3 scripts/uppdatera_bibliotek.py            # torrkörning
    python3 scripts/uppdatera_bibliotek.py --verkstall
"""
import argparse
import sys
from pathlib import Path

ROT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROT))

from pipeline.freeze import words  # noqa: E402
from scripts.oforklarade_ord import oforklarat_pa_karna  # noqa: E402

# Böcker vars läskopia inte heter som arbetskatalogen. Spindelkonungen är en
# fysisk bok med två fristående äventyr och delas av `dela_spindelkonungen.py`;
# den hanteras inte här.
NAMN = {
    "40-drakar-och-demoner-grundregler-fjarde-utgavan-1991-i-rollpersonen-riotminds":
        "DOD-REG-grundregler-1991-del1-rollpersonen",
}
DELAS = {"DOD-AVE-spindelkonungens-pyramid-och-skelettbyns-hemlighet"}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--verkstall", action="store_true")
    a = p.parse_args(argv)

    bib = ROT / "bibliotek"
    ändrade = fel = 0
    for d in sorted((ROT / "arbete").iterdir()):
        if not (d / "book.json").is_file() or d.name in DELAS:
            continue
        md = d / "export" / "bok.md"
        if not md.is_file():
            print("%-58s SAKNAR export/bok.md" % d.name[:58])
            fel += 1
            continue
        ny = md.read_text(encoding="utf-8")
        mål = bib / (NAMN.get(d.name, d.name) + ".md")
        gammal = mål.read_text(encoding="utf-8") if mål.is_file() else None
        if gammal == ny:
            continue
        a_ord = words(gammal) if gammal is not None else None
        b_ord = words(ny)
        borta = (a_ord - b_ord) if a_ord is not None else {}
        forklarade = 0
        if borta:
            kvar, _ = oforklarat_pa_karna(d, borta, b_ord - a_ord)
            obetalt = {k: v for k, v in kvar["borta"].items() if v}
            if obetalt:
                print("%-58s ORD BORTA UTAN POST: %s — INTE skriven"
                      % (mål.name[:58], dict(list(obetalt.items())[:6])))
                fel += 1
                continue
            forklarade = sum(borta.values())
        ändrade += 1
        n_gammal = sum(a_ord.values()) if a_ord is not None else 0
        print("%-58s %s  %d -> %d ord%s"
              % (mål.name[:58], "SKRIVEN" if a.verkstall else "SKULLE SKRIVAS",
                 n_gammal, sum(b_ord.values()),
                 "  (%d rättade ord, alla med post)" % forklarade
                 if forklarade else ""))
        if a.verkstall:
            mål.write_text(ny, encoding="utf-8")
    print()
    print("%d läskopior %s, %d fel"
          % (ändrade, "uppdaterade" if a.verkstall else "att uppdatera", fel))
    return 1 if fel else 0


if __name__ == "__main__":
    sys.exit(main())
