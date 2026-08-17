#!/usr/bin/env python3
"""Dela flerstyckeselement vid tryckets uppmätta styckeindrag (BQ-001).

Edsbrytarna i Erebos är transkriberad med ETT element per spaltavsnitt på nio
av tio sidor: s. 2:s `e01` bär fyra tryckta stycken i ett element om 53 rader,
och `bok.md` flödar då ihop tryckets stycken till ett enda. Styckegränserna
står emellertid I MÄTNINGEN: en tryckt styckestart är indragen, och indraget
är uppmätt i `page_NNN.radboxar.json`.

Uppmätt på bokens egna redan delade sidor (s. 1 och s. 6, fem kända
styckegränser): styckeindraget är +0,014–0,020 av sidbredden mot spaltens
baslinje, medan fortsättningsradernas spridning ligger inom ±0,002. Tröskeln
0,008 skiljer de två klustren med god marginal åt båda håll. Ett "indrag"
över 0,035 är inget indrag utan en annan spalt eller en mätartefakt (s. 1
rad 24–25 mäter UTANFÖR spalten åt vänster — utfall, inte indrag — och rör
aldrig tröskeln eftersom baslinjen är typvärdet, inte medelvärdet).

Delningen omfördelar `source.rader` och `bbox`; texten berörs inte: varje ny
del är en radrange ur originalets egen text, och `"\\n".join(delarna) ==
originaltexten` kontrolleras innan något skrivs. Originalet behålls med
`removed: true` och `source.split_into` (montagens mönster, jfr
`pipeline.tables.assemble`); de nya elementen bär `source.split_from` och en
`resolved_reasons`-post med det uppmätta indraget — samma dokumentationsform
som terminal-states delade fältrader (`p035_e01a` …). Ingen `added_by`: ordens
redovisning är att de aldrig lämnar boken (samma skäl som i
`scripts/materialisera_added_by.py` — en delning är inget tillägg).

Spärrar (alla ger refusering med skäl, aldrig en gissning):

* **1:1-kravet.** Elementets textrader måste gå jämnt ihop med dess uppmätta
  band — `len(text.split("\\n")) == len(source.rader)` och radserien
  sammanhängande. 14 band mot 13 tryckta rader är en mätfråga (klass B),
  inte en delningsfråga.
* **Avstavningsvetot.** En rad vars företrädare slutar på avstavningsbinde-
  streck kan inte inleda ett stycke — ordet fortsätter. Pekar indraget dit
  ändå motsäger geometrin typografin, och HELA elementet refuseras: någon av
  mätningen och bindningen är fel, och det ska utredas, inte överröstas.
* **Ensamt indrag.** Ett styckeindrag står ensamt; ett HÄNGANDE indrag delas
  av flera rader i följd (citatpartier, punktlistor). Samma regel som
  exportens `_starts_paragraph`. Raderna i ett hängande parti delas aldrig.
  Undantaget är mätt, inte tolkat: TVÅ styckestarter kan stå vägg i vägg när
  det första stycket är en enda rad (brevets signaturrad `— Kodnamn Bl.` följd
  av `Brevet är skrivet…`, s. 6 rad 55–56). Skiljelinjen mot hängblocket är
  företrädarraden: före en äkta styckestart är den KORT (utsluten sats slutar
  stycket på en kort rad — 0,20 respektive 0,15 mot spaltens 0,415), medan
  hängblockets rader föregås av fulla rader (s. 5:s punktblock: 0,388–0,409
  mot spaltbredden 0,39–0,41). Gränsen 0,92 av spaltens fulla bredd är samma
  som exportens `_FULL_LINE` och `binda_rader`:s `RAGGED_SHARE`.
* **Gränsfall.** Ett indrag i [0,005, 0,008) delas inte men redovisas, så att
  en advokat kan döma det mot PNG:n i stället för att ingen ser det.

Utvärdera alltid mot bokens egna facitsidor först (Regel 9a): verktyget får
sina kända delningar ur s. 1/s. 6 genom att foga ihop redan delade grannar
till ett syntetiskt element och kräva att gränserna återuppstår ur enbart
geometrin. Avvikelser DÖMS mot trycket, de räknas inte: facit är en tidigare
transkription, och en extra gräns med fullt uppmätt indrag är verktyget som
ser något facit missade — de redovisas var för sig med sina mått.

    python3 scripts/dela_stycken.py arbete/<slug> --utvardera
    python3 scripts/dela_stycken.py arbete/<slug> [--sidor 2,3]
    python3 scripts/dela_stycken.py arbete/<slug> --verkstall

Idempotent: delade original är `removed` och hoppas över; delarna är
enstyckeselement utan inre indrag och delas inte igen.
"""
import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.corrections import now_iso  # noqa: E402

# Trösklarna är uppmätta på bokens egna facitsidor — se moduldocstringen.
INDRAG_MIN = 0.008
INDRAG_MAX = 0.035
GRANSFALL = 0.005
# Samma bucketbredd som exportens `_local_column`: baslinjen är spaltens
# VANLIGASTE radstart, inte den minsta — indragen är minoriteten.
X_BUCKET = 0.005
# Under så här stor andel av spaltens fulla bredd är en rad ragged, alltså ett
# styckes sista. Samma gräns som exportens `_FULL_LINE` och `binda_rader`:s
# `RAGGED_SHARE`.
RAGGED = 0.92

DELBARA = {"paragraph"}
VERKTYG = "scripts/dela_stycken.py"


def _las(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _rader(el):
    return (el.get("source") or {}).get("rader") or []


def _avstavad(rad):
    t = (rad or "").rstrip()
    return t.endswith("-") and not t.endswith((" -", "--"))


def _baslinjer(rows):
    """Spaltbaslinje per region: typvärdesbucketens median-x.

    Bara band med löptextbredd får rösta — en tabellcell eller en kort
    dekorlinje har en annan vänsterkant och skulle dra baslinjen ur led.
    """
    per = {}
    for r in rows:
        b = r.get("bbox") or []
        if len(b) == 4 and b[2] >= 0.15:
            per.setdefault(r.get("region"), []).append(b[0])
    ut = {}
    for reg, xs in per.items():
        counts = Counter(int(round(x / X_BUCKET)) for x in xs)
        bucket = min(counts, key=lambda k: (-counts[k], k))
        inne = [x for x in xs if int(round(x / X_BUCKET)) == bucket]
        ut[reg] = statistics.median(inne)
    return ut


def _fullbredder(rows):
    """Spaltens fulla radbredd per region, som p85 — samma mått som
    `binda_rader._full_bredd` och av samma skäl: en enstaka rad kan sticka ut,
    och max skulle flytta referensen."""
    per = {}
    for r in rows:
        b = r.get("bbox") or []
        if len(b) == 4 and b[2] >= 0.15:
            per.setdefault(r.get("region"), []).append(b[2])
    ut = {}
    for reg, ws in per.items():
        ws = sorted(ws)
        ut[reg] = ws[min(int(0.85 * len(ws)), len(ws) - 1)]
    return ut


def brytpunkter(el, rows, baslinjer, fullbredder):
    """Härled styckegränserna i `el` ur radboxarnas uppmätta indrag.

    Returnerar (gränser, refusering, anteckningar) där gränser är radpositioner
    INOM elementet (0-baserade; en gräns k betyder att ett nytt stycke börjar
    på elementets rad k). Refusering är en sträng när elementet inte får delas.
    """
    rr = _rader(el)
    text = el.get("text") or ""
    lines = text.split("\n")
    anm = []
    if len(rr) < 2:
        return [], None, anm
    if len(lines) != len(rr):
        return [], ("%d uppmätta band mot %d textrader — 1:1-kravet håller "
                    "inte, delningen kan inte placeras" % (len(rr), len(lines))), anm
    if any(rr[i + 1] != rr[i] + 1 for i in range(len(rr) - 1)):
        return [], "radserien är inte sammanhängande", anm
    if not all(0 <= i < len(rows) for i in rr):
        return [], "radindex utanför mätningen", anm

    dx = []
    for i in rr:
        b = rows[i].get("bbox") or []
        if len(b) != 4:
            return [], "rad %d saknar bbox i mätningen" % i, anm
        bas = baslinjer.get(rows[i].get("region"))
        if bas is None:
            return [], ("rad %d ligger i region %r utan baslinje"
                        % (i, rows[i].get("region"))), anm
        dx.append(b[0] - bas)

    def indragen(k):
        return k is not None and 0 <= k < len(dx) and dx[k] >= INDRAG_MIN

    gränser = []
    for k in range(1, len(rr)):
        if not indragen(k):
            if GRANSFALL <= dx[k] < INDRAG_MIN:
                anm.append("rad %d: gränsfall, indrag %+.4f — delas inte, "
                           "döms mot PNG:n vid behov" % (rr[k], dx[k]))
            continue
        if dx[k] > INDRAG_MAX:
            anm.append("rad %d: avvikelse %+.4f överskrider INDRAG_MAX — "
                       "mätartefakt, ingen delning" % (rr[k], dx[k]))
            continue
        # Hängande indrag: grannen på samma baslinjeavstånd delar indraget.
        # Undantag: är FÖRETRÄDARRADEN ragged har ett stycke bevisligen slutat
        # där — då är indraget en styckestart också med indragen granne (två
        # styckestarter vägg i vägg, t.ex. en enradig signatur följd av nytt
        # stycke). Ett hängblocks rader föregås av fulla rader och berörs inte.
        samma_reg_fore = rows[rr[k - 1]].get("region") == rows[rr[k]].get("region")
        samma_reg_efter = (k + 1 < len(rr)
                           and rows[rr[k + 1]].get("region") == rows[rr[k]].get("region"))
        if (samma_reg_fore and indragen(k - 1)) or (samma_reg_efter and indragen(k + 1)):
            fb = fullbredder.get(rows[rr[k - 1]].get("region"))
            pb = rows[rr[k - 1]].get("bbox") or []
            ragged_fore = (samma_reg_fore and fb and len(pb) == 4
                           and pb[2] < RAGGED * fb)
            if not ragged_fore:
                anm.append("rad %d: hängande indrag (%+.4f, grannrad delar "
                           "det) — ingen styckegräns" % (rr[k], dx[k]))
                continue
        if _avstavad(lines[k - 1]):
            return [], ("rad %d bär styckeindrag (%+.4f) men föregående rad "
                        "slutar på avstavning — geometrin motsäger typografin"
                        % (rr[k], dx[k])), anm
        gränser.append(k)
    return gränser, None, anm


def _union(rows, idx):
    boxar = [rows[j].get("bbox") for j in idx]
    boxar = [b for b in boxar if b and len(b) == 4]
    if not boxar:
        return None
    x0 = min(b[0] for b in boxar)
    y0 = min(b[1] for b in boxar)
    x1 = max(b[0] + b[2] for b in boxar)
    y1 = max(b[1] + b[3] for b in boxar)
    return [round(x0, 6), round(y0, 6), round(x1 - x0, 6), round(y1 - y0, 6)]


def _suffix(n):
    """a, b, …, z, aa, ab, … — samma serie som terminal-states delade rader."""
    ut = ""
    n += 1
    while n:
        n, rest = divmod(n - 1, 26)
        ut = chr(ord("a") + rest) + ut
    return ut


def dela_element(el, rows, gränser, dx_not):
    """Bygg delelementen. Returnerar listan nya element (texten oförändrad)."""
    rr = _rader(el)
    lines = (el.get("text") or "").split("\n")
    starter = [0] + gränser
    slut = gränser + [len(rr)]
    delar = []
    for n, (a, b) in enumerate(zip(starter, slut)):
        stycke_rader = rr[a:b]
        stycke_text = "\n".join(lines[a:b])
        källa = {k: v for k, v in (el.get("source") or {}).items()
                 if k not in ("rader", "bbox", "bbox_source")}
        källa["rader"] = stycke_rader
        box = _union(rows, stycke_rader)
        if box:
            källa["bbox"] = box
            källa["bbox_source"] = "pipeline.rows"
        källa["split_from"] = el.get("id")
        not_ = ("Del %d av %d av draftens %s (styckedelning BQ-001, rader "
                "%d–%d)." % (n + 1, len(starter), el.get("id"),
                             stycke_rader[0], stycke_rader[-1]))
        if n > 0:
            not_ += (" Brytpunkten är uppmätt, inte tolkad: styckeindrag "
                     "%+.4f mot spaltens baslinje på rad %d."
                     % (dx_not[gränser[n - 1]], stycke_rader[0]))
        delar.append({
            "id": "%s%s" % (el.get("id"), _suffix(n)),
            "type": el.get("type"),
            "text": stycke_text,
            "source": källa,
            "confidence": el.get("confidence"),
            "needs_review": False,
            "resolved_reasons": [{
                "reason": "Styckedelning enligt BQ-001",
                "resolution": not_,
                "closed_by": VERKTYG,
                "timestamp": now_iso(),
            }],
        })
        if el.get("style"):
            delar[-1]["style"] = el["style"]
    ihop = "\n".join(d["text"] for d in delar)
    if ihop != (el.get("text") or ""):
        raise SystemExit("BUG: delarnas text går inte ihop med originalets "
                         "(%s)" % el.get("id"))
    return delar


def _dx_karta(el, rows, baslinjer):
    rr = _rader(el)
    ut = {}
    for k, i in enumerate(rr):
        b = rows[i].get("bbox") or []
        bas = baslinjer.get(rows[i].get("region"))
        if len(b) == 4 and bas is not None:
            ut[k] = b[0] - bas
    return ut


def _sidor(workdir, urval=None):
    for f in sorted((workdir / "pages").glob("page_*.final.json")):
        n = int(f.name[5:8])
        if urval and n not in urval:
            continue
        rb = workdir / "pages" / ("page_%03d.radboxar.json" % n)
        if not rb.exists():
            continue
        d = _las(f)
        rows = _las(rb).get("rows") or []
        yield n, f, d, rows


def utvardera(workdir, urval=None):
    """Pröva verktyget mot bokens redan delade sidor.

    Kända styckegränser hämtas ur grannelement vars radserier fortsätter i
    varandra: de fogas ihop till ett syntetiskt element och verktyget måste
    återskapa delningen ur enbart geometrin. En känd gräns som missas fäller
    verktyget; en EXTRA gräns döms mot trycket (Regel 9a) — den redovisas med
    sitt uppmätta indrag och sin radtext i stället för att räknas som fel.
    """
    kända = återskapade = 0
    missade, extra = [], []
    for n, _f, d, rows in _sidor(workdir, urval):
        baslinjer = _baslinjer(rows)
        fullbredder = _fullbredder(rows)
        els = [e for e in d.get("elements") or [] if not e.get("removed")]
        # kedjor av delbara grannar med sammanhängande radserie
        kedja = []
        for el in els + [None]:
            passar = (el is not None and el.get("type") in DELBARA
                      and len(_rader(el)) >= 1
                      and (not kedja or _rader(el)[0] == _rader(kedja[-1])[-1] + 1))
            if passar:
                kedja.append(el)
                continue
            if len(kedja) >= 2:
                rr = [i for e in kedja for i in _rader(e)]
                text = "\n".join(e.get("text") or "" for e in kedja)
                if all(len((e.get("text") or "").split("\n")) == len(_rader(e))
                       for e in kedja):
                    syntet = {"id": "+".join(e["id"] for e in kedja),
                              "type": "paragraph", "text": text,
                              "source": {"rader": rr}}
                    # En elementgräns är styckefacit BARA inom en och samma
                    # spalt. Vid en spaltgräns säger elementbytet ingenting om
                    # stycket — s. 2:s `e01|e02` byter element för att spalten
                    # tar slut, och trycket fortsätter mitt i meningen
                    # (»…lämnat plats till« / »till att Erbolsus hustru«).
                    # Indraget är där rätteligen noll, och att räkna det som
                    # miss vore att kräva att verktyget återger en
                    # transkriptionsartefakt (Regel 9a).
                    facit = set()
                    pos = 0
                    for e in kedja[:-1]:
                        pos += len(_rader(e))
                        if (rows[rr[pos - 1]].get("region")
                                == rows[rr[pos]].get("region")):
                            facit.add(pos)
                    gr, ref, _anm = brytpunkter(syntet, rows, baslinjer, fullbredder)
                    dxk = _dx_karta(syntet, rows, baslinjer)
                    kända += len(facit)
                    if ref:
                        missade += [(n, syntet["id"], rr[p], "REFUSERAT: " + ref)
                                    for p in sorted(facit)]
                    else:
                        lines = text.split("\n")
                        for p in sorted(facit | set(gr)):
                            if p in facit and p in gr:
                                återskapade += 1
                            elif p in facit:
                                missade.append((n, syntet["id"], rr[p],
                                                "indrag %+.4f" % dxk.get(p, 0.0)))
                            else:
                                extra.append((n, syntet["id"], rr[p],
                                              dxk.get(p, 0.0), lines[p][:44]))
            kedja = [el] if (el is not None and el.get("type") in DELBARA
                             and _rader(el)) else []
    print("Utvärdering mot bokens redan delade sidor:")
    print("  kända styckegränser   : %d" % kända)
    print("  återskapade ur geometrin: %d" % återskapade)
    print("  MISSADE               : %d" % len(missade))
    for n, sid, rad, skäl in missade:
        print("    s. %d %s rad %d — %s" % (n, sid, rad, skäl))
    print("  extra gränser (döms mot trycket, Regel 9a): %d" % len(extra))
    for n, sid, rad, dxv, txt in extra:
        print("    s. %d %s rad %d indrag %+.4f | %s" % (n, sid, rad, dxv, txt))
    return 1 if missade else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workdir", type=Path)
    ap.add_argument("--sidor", help="t.ex. 2,3 eller 2-5")
    ap.add_argument("--utvardera", action="store_true")
    ap.add_argument("--verkstall", action="store_true")
    a = ap.parse_args(argv)
    if not (a.workdir / "pages").is_dir():
        ap.error("%s ser inte ut som en arbetskatalog" % a.workdir)
    urval = None
    if a.sidor:
        urval = set()
        for bit in a.sidor.split(","):
            if "-" in bit:
                lo, hi = bit.split("-")
                urval.update(range(int(lo), int(hi) + 1))
            else:
                urval.add(int(bit))

    if a.utvardera:
        return utvardera(a.workdir, urval)

    delade = refuserade = 0
    for n, f, d, rows in _sidor(a.workdir, urval):
        baslinjer = _baslinjer(rows)
        fullbredder = _fullbredder(rows)
        els = d.get("elements") or []
        ut, ändrad = [], False
        for el in els:
            ut.append(el)
            if (el.get("removed") or el.get("type") not in DELBARA
                    or (el.get("source") or {}).get("split_into")):
                continue
            gr, ref, anm = brytpunkter(el, rows, baslinjer, fullbredder)
            for m in anm:
                print("s. %d %s: %s" % (n, el.get("id"), m))
            if ref:
                if len(_rader(el)) >= 2:
                    print("s. %d %s: REFUSERAT — %s" % (n, el.get("id"), ref))
                    refuserade += 1
                continue
            if not gr:
                continue
            dxk = _dx_karta(el, rows, baslinjer)
            delar = dela_element(el, rows, gr, dxk)
            print("s. %d %s: %d stycken (gränser vid rad %s)"
                  % (n, el.get("id"), len(delar),
                     ", ".join(str(_rader(el)[k]) for k in gr)))
            for dd in delar:
                print("    %s rader %d–%d  %r"
                      % (dd["id"], dd["source"]["rader"][0],
                         dd["source"]["rader"][-1], dd["text"][:40]))
            delade += 1
            if a.verkstall:
                el["removed"] = True
                el.setdefault("source", {})["split_into"] = \
                    [dd["id"] for dd in delar]
                ut.extend(delar)
                ändrad = True
        if a.verkstall and ändrad:
            d["elements"] = ut
            f.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8")
    print("\n%d element %s, %d refuserade."
          % (delade, "delade" if a.verkstall else "skulle delas (torrkörning)",
             refuserade))
    return 0


if __name__ == "__main__":
    sys.exit(main())
