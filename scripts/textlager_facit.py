#!/usr/bin/env python3
"""Två mätningar som en digital utgåva ger gratis — och som annars kostar en agent.

En bok vars draft kommer ur PDF:ens textlager (`method: "embedded"`) har inget
OCR-brus: lydelsen ÄR textlagrets. Två frågor som på en inskannad sida kräver
att någon läser PNG:n går därför att avgöra i kod, och de gäller varje sida:

**1. Fullständighet.** Draftens ord mot textlagrets ord som multimängder. Ett
tappat eller tillagt ord är en exakt skillnad, inte en bedömning. Advokaten
gjorde just den jämförelsen för hand på s. 14 (272 mot 272) — det är samma
jobb, och det ska inte göras om 35 gånger.

**2. Tecken som inte ritar något.** Textlagret kan bära en kodpunkt vars glyf
har NOLL frammatning — den står i strängen men syns inte på sidan. I den här
boken bar 21 sidfötter `TERMINAL STATE ×27` där `×` mäter 0,000 pt bred medan
varje riktig glyf mäter 1,8–6 pt. Draften ärvde tecknet och det gick rakt in i
läsexporten. Mätningen är exakt och kräver ingen bild.

**3. Versaltypsnittet.** `MachineFont` ritar GEMENA kodpunkter som versaler.
Textlagret ger därför `Dave GahMan` där trycket står `DAVE GAHMAN`, och det
inre versala M:et som inte kan uppstå i en sättning är hela avslöjandet.
Draften ärvde kodningen rakt av. Skillnaden mot en vanlig OCR-felläsning är
att den ser SPRÅKLIGT RIKTIG ut — ett namn med versal begynnelsebokstav — och
därför aldrig upptäcks av att jämföra draften med sig själv.

Skriptet mäter, det rättar inte: utfallet är korrektionsposter med `applied:
false`, som allt annat. Advokaten dömer mot PNG:n.

    python3 scripts/textlager_facit.py arbete/<slug> [--pdf P] [--verkstall]
"""
import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fitz  # noqa: E402

# Typsnitt vars gemena kodpunkter ritas som versaler. Listan är avsiktligt en
# lista och inte en heuristik: att gissa fram klassen ur glyfhöjder är precis
# den sortens bedömning som ska göras mot PNG:n, inte i ett skript.
VERSALTYPSNITT = ("MachineFont", "KomikaHand", "KomikaSlick")

ORD = re.compile(r"\w+", re.UNICODE)

# En glyf smalare än så ritar ingenting. Marginalen är rundlig mot 0: bokens
# smalaste RIKTIGA glyf mäter 1,78 pt (mellanslaget i MachineFont 9 pt) och
# `×` i sidfoten mäter 0,000.
NOLLBREDD = 0.3


def _ord(text):
    return ORD.findall(text or "")


def _sidtext(page):
    return page.get_text("text")


def _spans(page):
    for b in page.get_text("dict")["blocks"]:
        if b.get("type"):
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                yield span


def _osynliga_tecken(page):
    """Kodpunkter som ritas med typsnittets MELLANSLAGSGLYF — alltså med intet.

    Nollbredd räcker INTE som bevis, och det misstaget är värt att skriva ut.
    Första försöket flaggade varje tecken vars glyf mäter noll överallt på
    sidan, och det hade strippat `s` ur ortnamnet `Discett` (s. 4 och 24):
    typsnittet `Lobster1.3` är subsatt så att uppslagningen misslyckas,
    PyMuPDF ger `gid = -1`, och bredden faller till noll som en följd av att
    glyfen inte gick att hitta — inte av att den är tom. Bokstaven står
    tryckt. Ett bevis är en skillnad, inte en brist på alternativ (Regel 9b).

    Skillnaden som HÅLLER: tecknet har samma glyf-id som mellanslaget i samma
    typsnitt. Sidfotens `×` bär `gid = 1` i `MachineFont`, exakt det id som
    `U+0020` bär där, och renderaren ritar därför ett mellanslag. Ett negativt
    glyf-id är en misslyckad uppslagning och räknas aldrig.
    """
    mellanslagsglyf = {}
    kandidater = {}
    for span in page.get_texttrace():
        font = span.get("font")
        for tecken, gid, _origin, bbox in span["chars"]:
            if gid < 0:
                continue
            if tecken == 0x20:
                mellanslagsglyf.setdefault(font, set()).add(gid)
                continue
            if bbox[2] - bbox[0] >= NOLLBREDD:
                continue
            if 0 <= tecken < 0x110000:
                kandidater.setdefault(chr(tecken), set()).add((font, gid))
    return {t for t, par in kandidater.items()
            if all(gid in mellanslagsglyf.get(font, ()) for font, gid in par)}


def _versaltext(page):
    """All text på sidan som är satt i ett versaltypsnitt."""
    delar = [s["text"] for s in _spans(page)
             if any(s["font"].startswith(f) for f in VERSALTYPSNITT)]
    return "".join(delar)


def _post(original, corrected, reason):
    return {"original": original, "corrected": corrected, "applied": False,
            "confidence": 0.9, "reason": reason,
            "source": "skript:textlager_facit", "kind": "ocr"}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workdir")
    ap.add_argument("--pdf")
    ap.add_argument("--verkstall", action="store_true")
    args = ap.parse_args()

    slug = os.path.basename(os.path.normpath(args.workdir))
    pdf = args.pdf
    if not pdf:
        rot = os.path.dirname(os.path.dirname(os.path.abspath(args.workdir)))
        for katalog in ("arkiv", "import"):
            kandidat = os.path.join(rot, katalog, slug + ".pdf")
            if os.path.exists(kandidat):
                pdf = kandidat
                break
    if not pdf:
        print("HITTAR INGEN PDF för %s — ange --pdf." % args.workdir)
        return 2
    doc = fitz.open(pdf)

    poster = 0
    luckor = 0
    sidor = 0
    for fil in sorted(glob.glob(os.path.join(args.workdir, "pages",
                                             "page_*.validated.json"))):
        with open(fil, encoding="utf-8-sig") as fh:
            data = json.load(fh)
        sidnr = data.get("page")
        if not sidnr or sidnr > len(doc):
            continue
        element = [el for el in data.get("elements", [])
                   if (el.get("source") or {}).get("method") == "embedded"
                   and not el.get("removed")]
        if not element:
            continue
        sidor += 1
        page = doc[sidnr - 1]

        # (1) Fullständighet — multimängd mot multimängd.
        from collections import Counter
        tryck = Counter(_ord(_sidtext(page)))
        draft = Counter()
        for el in element:
            draft.update(_ord(el.get("text")))
        saknas = tryck - draft
        extra = draft - tryck
        if saknas or extra:
            luckor += 1
            print("s.%-3d FULLSTÄNDIGHET: saknas %s | tillagt %s"
                  % (sidnr,
                     dict(list(saknas.items())[:8]) or "-",
                     dict(list(extra.items())[:8]) or "-"))

        # (2) Tecken som inte ritar något.
        osynliga = _osynliga_tecken(page)
        rord = 0
        for el in element:
            text = el.get("text") or ""
            träffar = sorted(t for t in osynliga if t in text)
            if not träffar:
                continue
            rensad = text
            for tecken in träffar:
                rensad = rensad.replace(tecken, "")
            rensad = re.sub(r" {2,}", " ", rensad)
            if any(c.get("source") == "skript:textlager_facit"
                   and c.get("original") == text
                   for c in el.get("corrections") or []):
                continue
            el.setdefault("corrections", []).append(_post(
                text, rensad,
                "Skript (textlagerfacit): kodpunkten %s står i textlagret men "
                "dess glyf har NOLL frammatning (< %.1f pt mot 1,8–6 pt för "
                "varje riktig glyf på sidan) — den ritar ingenting på papperet "
                "och står alltså inte i trycket. Draften ärvde tecknet ur "
                "textlagret. Verifiera mot PNG:n."
                % (", ".join(repr(t) for t in träffar), NOLLBREDD)))
            rord += 1
            poster += 1

        # (3) Versaltypsnittets kodning.
        versalt = _versaltext(page)
        for el in element:
            text = (el.get("text") or "").strip()
            if not text or text.isupper():
                continue
            ordlista = _ord(text)
            if not ordlista:
                continue
            # Elementet räknas som satt i versaltypsnittet när ALLA dess ord
            # står i sidans versaltypsnittstext. Kravet är hårt med flit: ett
            # element som blandar två typsnitt hör till advokaten, inte hit.
            if not all(o in versalt for o in ordlista):
                continue
            versal = text.upper()
            if versal == text:
                continue
            # Idempotens: en post som redan står där skrivs inte en gång till.
            if any(c.get("source") == "skript:textlager_facit"
                   and c.get("original") == text
                   for c in el.get("corrections") or []):
                continue
            el.setdefault("corrections", []).append(_post(
                text, versal,
                "Skript (textlagerfacit): elementet är satt i ett typsnitt vars "
                "GEMENA kodpunkter ritas som VERSALER (%s). Textlagret bär "
                "därför kodningen, inte tryckets lydelse — trycket står "
                "helversalt. Draftens blandade skiftläge är en tyst "
                "normalisering som ser språkligt riktig ut och som ingen "
                "jämförelse mot draften kan upptäcka. Verifiera mot PNG:n."
                % ", ".join(VERSALTYPSNITT)))
            rord += 1
            poster += 1
        if rord and args.verkstall:
            with open(fil, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=1)
                fh.write("\n")

    prefix = "" if args.verkstall else "TORRKÖRNING: "
    print("%s%d sidor mätta | %d sidor med ordlucka | %d versalposter"
          % (prefix, sidor, luckor, poster))
    return 0


if __name__ == "__main__":
    sys.exit(main())
