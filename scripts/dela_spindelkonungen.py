#!/usr/bin/env python3
"""Dela Spindelkonungens pyramid & Skelettbyns hemlighet i två läskopior.

En fysisk bok, två fristående äventyr. `arbete/` håller dem som EN bok — det är
riktigt, för de delar käll-PDF, sidnumrering och copyrightsida — men läskopiorna
i `bibliotek/` ska vara ett äventyr var, för det är så de matas till andra
agenter.

Delningen gjordes en gång för hand (20 juli) och blev därmed en läskopia som
inte kunde följa med exporten: den 5 augusti hade `bok.md` fått fixar som de
handdelade filerna aldrig såg. Därför är den ett skript. Gränsen är inte
gissad utan mätt i sidmarkörerna: sida 1 är det gemensamma omslaget, sida 2–16
är Spindelkonungens pyramid, sida 17–28 är Skelettbyns hemlighet.

    python3 scripts/dela_spindelkonungen.py            # torrkörning
    python3 scripts/dela_spindelkonungen.py --verkstall

Idempotent: en andra körning skriver identiskt innehåll.
"""
import argparse
import pathlib
import re
import sys

SLUG = "DOD-AVE-spindelkonungens-pyramid-och-skelettbyns-hemlighet"

# (bibliotekets filnamn, H1, första sida, sista sida)
DELAR = [
    ("DOD-AVE-spindelkonungens-pyramid.md",
     "Spindelkonungens pyramid — Drakar och Demoner (1984)", 2, 16),
    ("DOD-AVE-skelettbyns-hemlighet.md",
     "Skelettbyns hemlighet — Drakar och Demoner (1984)", 17, 28),
]

_SIDA = re.compile(r"^<!-- sida (\d+) -->$")


def dela(text):
    """Dela bok.md på sidmarkörerna. Returnerar {sidnummer: [rader]}."""
    sidor = {}
    aktuell = None
    for rad in text.splitlines():
        m = _SIDA.match(rad)
        if m:
            aktuell = int(m.group(1))
            sidor[aktuell] = [rad]
        elif aktuell is not None:
            sidor[aktuell].append(rad)
    return sidor


def bygg(sidor, rubrik, forsta, sista):
    saknade = [n for n in range(forsta, sista + 1) if n not in sidor]
    if saknade:
        raise SystemExit("saknade sidor i bok.md: %s" % saknade)
    ut = ["# %s" % rubrik, ""]
    for n in range(forsta, sista + 1):
        ut.extend(sidor[n])
    # normalisera bort inledande/avslutande tomrader mellan sidorna
    return "\n".join(ut).rstrip() + "\n"


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--rot", default=".", help="repots rot")
    p.add_argument("--verkstall", action="store_true")
    a = p.parse_args(argv)

    rot = pathlib.Path(a.rot).resolve()
    kalla = rot / "arbete" / SLUG / "export" / "bok.md"
    if not kalla.is_file():
        raise SystemExit("saknas: %s — kör `exportera` först" % kalla)
    sidor = dela(kalla.read_text(encoding="utf-8"))

    andrade = 0
    for filnamn, rubrik, forsta, sista in DELAR:
        ny = bygg(sidor, rubrik, forsta, sista)
        mal = rot / "bibliotek" / filnamn
        gammal = mal.read_text(encoding="utf-8") if mal.is_file() else None
        lika = gammal == ny
        status = "oförändrad" if lika else ("SKRIVEN" if a.verkstall else "SKULLE SKRIVAS")
        print("%-42s %-16s sida %d-%d, %d tecken"
              % (filnamn, status, forsta, sista, len(ny)))
        if not lika:
            andrade += 1
            if a.verkstall:
                mal.write_text(ny, encoding="utf-8")
    if not a.verkstall and andrade:
        print("TORRKÖRNING: %d filer skulle skrivas" % andrade)
    return 0


if __name__ == "__main__":
    sys.exit(main())
