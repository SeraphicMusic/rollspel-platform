#!/usr/bin/env python3
"""Härled kursivspans ur den arkiverade PDF:ens textlager (BQ-004).

Elementschemat bär bara `style` på HELA element, så en stilväxling INUTI ett
stycke — brev, citerade repliker, exempelstycken, fartygsnamn — tappas i
`bok.md`. Stilen står emellertid i den arkiverade PDF:ens OCR-textlager:
varje span bär fontnamn (`Times-Italic` mot `Times-Roman`), och attributionen
är prövad mot bokens dokumenterade facit innan verktyget fick skriva något
(`--utvardera`):

* `Gyllene Hinden` klassas RAK inuti Valentins kursiva replik (s. 6) — den
  inversa konventionen beslut.md dokumenterar.
* `Sjösvalan` klassas kursiv i rak brödtext och RAK inuti kursiva repliker
  (s. 7) — samma konvention, båda hållen.
* Rubrikraden `SJÖSVALANS` är kursiv medan `ÅTERKOMST` i SAMMA rubrik är rak
  (s. 7, pixelverifierat i skanningen 2026-08-18) — stilen växlar alltså även
  inuti rubriker, och även de behöver spans, inte bara ett elementfält.

Metod: PDF-sidans spans läses i blockordning till en teckenström med
kursivflagga per tecken; varje elements text justeras mot strömmen med
`difflib.SequenceMatcher`, flaggorna mappas tecken för tecken, och stilen
SNAPPAS till hela ord — ett ord är kursivt när mer än hälften av dess matchade
tecken är det, och omatchade tecken (OCR-brus som `Mlls` för `hålls`) ärver
ordets majoritet. Två avstavningsfragment av samma ord tvingas till samma stil
(majoriteten), annars kan en brusig OCR-klassning lägga en spangräns mitt i
ett avstavat ord och bryta radläkningen i exporten.

Lagring (SCHEMA_VERSION 2):

* Helt kursiva element får `style: "italic"` (befintligt fält — exporten
  renderar redan det för löptext, och `heading`-grenen lagas i samma svep).
* Partiellt kursiva får `data.style_spans`: en lista
  `{"start": N, "end": N, "style": "italic"}` med teckenintervall i
  elementets `text` (end exklusiv), alltid på ordgränser.
* `list`-element får `{"item": i, "start": N, "end": N, "style": "italic"}`
  med intervall i `data.items[i]` (kartlegendens kursiva post 5, s. 10).

Spärrar: ett element vars justering mot OCR-strömmen är för svag
(matchkvot < 0,5) lämnas orört med anteckning — hellre en saknad stil än en
gissad. Statblock, tabeller, illustrationer och sidartefakter rörs aldrig.
Verktyget ändrar ingen text: bara `style`/`data.style_spans` skrivs.

    python3 scripts/kursivspans.py arbete/<slug> --pdf arkiv/<slug>.pdf --utvardera
    python3 scripts/kursivspans.py arbete/<slug> --pdf arkiv/<slug>.pdf [--sidor 7]
    python3 scripts/kursivspans.py arbete/<slug> --pdf arkiv/<slug>.pdf --verkstall

Idempotent: körningen räknar fram samma spans ur samma textlager och skriver
bara filer vars innehåll ändras.
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

STILBARA = {"paragraph", "boxed_text", "list_item", "heading"}
MIN_KVOT = 0.5
_ORD = re.compile(r"\S+")


def _kursiv_font(namn):
    return "Italic" in namn or "Oblique" in namn


def _sidstrom(pdf, sida0):
    """OCR-textlagrets teckenström för en sida: (text, [kursivflagga per tecken])."""
    d = pdf[sida0].get_text("dict")
    text, flagg = [], []
    for bl in d.get("blocks", []):
        for ln in bl.get("lines", []):
            for sp in ln.get("spans", []):
                t = sp.get("text") or ""
                if not t:
                    continue
                k = _kursiv_font(sp.get("font") or "")
                text.append(t)
                flagg.extend([k] * len(t))
            text.append("\n")
            flagg.append(False)
    return "".join(text), flagg


def _mappa(elem_text, strom, flagg):
    """Kursivflagga per tecken i elem_text, via justering mot OCR-strömmen.

    Returnerar (flaggor, matchkvot) där flaggor[i] är True/False/None
    (None = omatchat tecken) och kvoten är andelen matchade tecken.
    """
    sm = difflib.SequenceMatcher(None, strom, elem_text, autojunk=False)
    ut = [None] * len(elem_text)
    träff = 0
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            ut[b + k] = flagg[a + k]
            träff += 1
    kvot = träff / len(elem_text) if elem_text else 0.0
    return ut, kvot


def _ordstil(text, flaggor):
    """Snappa teckenflaggor till hela ord. Returnerar [(start, end, kursiv)]
    per ord (end exklusiv), där kursiv avgörs av ordets matchade majoritet."""
    ord_ = []
    for m in _ORD.finditer(text):
        bitar = [f for f in flaggor[m.start():m.end()] if f is not None]
        kursiv = bool(bitar) and sum(bitar) > len(bitar) / 2
        ord_.append((m.start(), m.end(), kursiv))
    # Avstavningsläkning: ett ordfragment med bindestreck i radslut och dess
    # fortsättning på nästa rad är SAMMA tryckta ord — samma stil, majoriteten
    # vinner (viktat på längd).
    i = 0
    while i + 1 < len(ord_):
        a0, a1, ak = ord_[i]
        b0, b1, bk = ord_[i + 1]
        frag = text[a0:a1]
        if (frag.endswith("-") and not frag.endswith(("--", " -"))
                and "\n" in text[a1:b0] and ak != bk):
            vinnare = ak if (a1 - a0) >= (b1 - b0) else bk
            ord_[i] = (a0, a1, vinnare)
            ord_[i + 1] = (b0, b1, vinnare)
        i += 1
    return ord_


def _runs(ord_, text):
    """Maximala följder av kursiva ord → [(start, end)] (end exklusiv).

    En run som består av ETT ord kortare än fyra tecken kastas: OCR:ns
    stilattribution darrar på småord, och `På` på s. 7 klassades kursivt där
    trycket är rakt (pixelverifierat 2026-08-18). Bokens attesterade äkta
    ensamordskursiver (`mycket`, `Sjösvalan`, ledorden `Erbolsus.`) är alla
    längre.
    """
    ut = []
    for a, b, k in ord_:
        if not k:
            continue
        if ut and text[ut[-1][1]:a].strip() == "":
            ut[-1][1] = b
        else:
            ut.append([a, b])
    return [(a, b) for a, b in ut if b - a >= 4 or " " in text[a:b].strip()
            or "\n" in text[a:b]]


def _element_spans(el, strom, flagg):
    """(status, payload) för ett element.

    status: 'helkursiv' | 'spans' | 'ren' | 'svag' | 'hoppad'
    payload: spanslista, eller matchkvoten för 'svag'.
    """
    typ = el.get("type")
    if el.get("removed") or typ not in STILBARA:
        return "hoppad", None
    text = el.get("text") or ""
    if not text.strip():
        return "hoppad", None
    flaggor, kvot = _mappa(text, strom, flagg)
    if kvot < MIN_KVOT:
        return "svag", kvot
    ord_ = _ordstil(text, flaggor)
    if not ord_:
        return "ren", []
    runs = _runs(ord_, text)
    if not runs:
        return "ren", []
    if len(runs) == 1 and runs[0][0] == ord_[0][0] and runs[0][1] == ord_[-1][1]:
        return "helkursiv", runs
    return "spans", runs


def _list_spans(el, strom, flagg):
    """Spans för ett list-elements data.items.

    En post där NÅGOT ord om minst fem tecken är kursivklassat markeras i sin
    HELHET: legenderna sätts i versaler/kapitäler, där OCR:ns stilattribution
    bevisligen underdetekterar (s. 7:s rubrik `SJÖSVALANS` fångas men
    grannordet i samma stil missas ofta), och beslut.md:s pixeldom för
    kartlegendens post 5 säger att HELA posten lutar (s. 10 `p010_e08`,
    verifierad 2026-08-11). Delposter är inte belagda någonstans i boken.
    """
    items = (el.get("data") or {}).get("items") or []
    ut = []
    for i, item in enumerate(items):
        if not (item or "").strip():
            continue
        flaggor, kvot = _mappa(item, strom, flagg)
        if kvot < MIN_KVOT:
            continue
        ord_ = _ordstil(item, flaggor)
        if any(k and b - a >= 5 for a, b, k in ord_):
            m0 = ord_[0][0]
            m1 = ord_[-1][1]
            ut.append({"item": i, "start": m0, "end": m1, "style": "italic"})
    return ut


def berakna(workdir, pdf, urval=None):
    """Räkna fram stilarna. Returnerar {sida: {el_id: (status, payload)}}."""
    import fitz
    doc = fitz.open(str(pdf))
    ut = {}
    for f in sorted((workdir / "pages").glob("page_*.final.json")):
        n = int(f.name[5:8])
        if urval and n not in urval:
            continue
        if n - 1 >= len(doc):
            continue
        strom, flagg = _sidstrom(doc, n - 1)
        d = json.loads(f.read_text(encoding="utf-8"))
        sida = {}
        for el in d.get("elements") or []:
            if el.get("type") == "list" and not el.get("removed"):
                spans = _list_spans(el, strom, flagg)
                if spans:
                    sida[el["id"]] = ("listspans", spans)
                continue
            status, payload = _element_spans(el, strom, flagg)
            if status in ("helkursiv", "spans", "svag"):
                sida[el["id"]] = (status, payload)
        ut[n] = (f, d, sida)
    return ut


# Dokumenterat facit ur beslut.md/resolved_reasons — verktyget måste återge
# det ur enbart textlagret innan det får skriva något (Regel 9a: en avvikelse
# döms mot trycket, den räknas inte — pixelbeläggen står i beslut.md).
FACIT = [
    # (sida, element, delsträng, ska_vara_kursiv)
    (6, "p006_e04", "Käre Valentin!", True),          # brevet
    (6, "p006_e07", "Gyllene Hinden", False),          # rak inuti kursiv replik
    (6, "p006_e07", "kölsvinet", True),                # repliken själv
    (6, "p006_e12b", "Exempel:", True),                # exempelstycket (delen
                                                       # ur §1:s styckedelning)
    (7, "p007_e02", "SJÖSVALANS", True),               # kursiv rubrikrad
    (7, "p007_e02", "ÅTERKOMST", False),               # rak rad i samma rubrik
    (7, "p007_e06", "SANNINGEN", False),               # rak underrubrik
]


def _kursiv_i(payload, status, text, delstr):
    pos = text.find(delstr)
    if pos < 0:
        return None
    if status == "helkursiv":
        return True
    if status == "spans":
        return any(a <= pos < b for a, b in payload)
    return False


def utvardera(workdir, pdf):
    resultat = berakna(workdir, pdf)
    fel = 0
    print("Facitprov mot bokens dokumenterade stilfall:")
    for sida, elid, delstr, vantat in FACIT:
        if sida not in resultat:
            print("  s.%d %s: SIDAN SAKNAS" % (sida, elid))
            fel += 1
            continue
        _f, d, sd = resultat[sida]
        el = next((e for e in d["elements"] if e["id"] == elid), None)
        if el is None:
            print("  s.%d %s: ELEMENTET SAKNAS" % (sida, elid))
            fel += 1
            continue
        status, payload = sd.get(elid, ("ren", []))
        blev = _kursiv_i(payload, status, el.get("text") or "", delstr)
        ok = blev == vantat
        if not ok:
            fel += 1
        print("  s.%d %-10s %-18r väntat=%-5s blev=%-5s %s"
              % (sida, elid, delstr, vantat, blev, "OK" if ok else "FEL"))
    print()
    for n, (_f, _d, sd) in sorted(resultat.items()):
        for elid, (status, payload) in sorted(sd.items()):
            if status == "svag":
                print("  s.%d %s: SVAG justering (kvot %.2f) — lämnas orörd"
                      % (n, elid, payload))
    return 1 if fel else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workdir", type=Path)
    ap.add_argument("--pdf", type=Path, required=True,
                    help="den ARKIVERADE käll-PDF:en (arkiv/<slug>.pdf)")
    ap.add_argument("--sidor")
    ap.add_argument("--utvardera", action="store_true")
    ap.add_argument("--verkstall", action="store_true")
    a = ap.parse_args(argv)
    if not (a.workdir / "pages").is_dir():
        ap.error("%s ser inte ut som en arbetskatalog" % a.workdir)
    if not a.pdf.is_file():
        ap.error("PDF saknas: %s" % a.pdf)

    if a.utvardera:
        return utvardera(a.workdir, a.pdf)

    urval = None
    if a.sidor:
        urval = set()
        for bit in a.sidor.split(","):
            if "-" in bit:
                lo, hi = bit.split("-")
                urval.update(range(int(lo), int(hi) + 1))
            else:
                urval.add(int(bit))

    rörda = 0
    for n, (f, d, sd) in sorted(berakna(a.workdir, a.pdf, urval).items()):
        ändrad = False
        for el in d.get("elements") or []:
            status, payload = sd.get(el.get("id"), (None, None))
            if status is None:
                continue
            text = el.get("text") or ""
            if status == "svag":
                print("s.%d %s: SVAG justering (kvot %.2f) — orörd"
                      % (n, el["id"], payload))
                continue
            # Också ett HELT kursivt element lagras som en span över hela
            # texten, aldrig som `style: "italic"`: elementstilen bryter
            # exportens flödesföljder, och flera av de helkursiva elementen
            # är fortsättningar av föregående sidas stycke — p007_e01 börjar
            # mitt i e12b:s avstavade »behö-«/»va«, och en stilbruten följd
            # hade lämnat ordet itu i bok.md. Spanformen flödar genom
            # skarven och markörskarvarna läks i exporten.
            if status == "listspans":
                spans = payload
            else:
                spans = [{"start": s, "end": e, "style": "italic"}
                         for s, e in payload]
            gamla = (el.get("data") or {}).get("style_spans")
            if gamla == spans:
                continue
            for sp in spans[:6]:
                if "item" in sp:
                    utdrag = ((el.get("data") or {}).get("items")
                              or [""] * (sp["item"] + 1))[sp["item"]][sp["start"]:sp["end"]]
                else:
                    utdrag = text[sp["start"]:sp["end"]]
                print("s.%d %s: kursiv %r" % (n, el["id"], utdrag[:60]))
            if len(spans) > 6:
                print("s.%d %s: … och %d spans till" % (n, el["id"], len(spans) - 6))
            rörda += 1
            if a.verkstall:
                el.setdefault("data", {})["style_spans"] = spans
                ändrad = True
        if a.verkstall and ändrad:
            f.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8")
    print("\n%d element %s." % (rörda, "uppdaterade" if a.verkstall
                                else "skulle uppdateras (torrkörning)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
