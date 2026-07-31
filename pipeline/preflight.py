"""Deterministisk förbesiktning av validerade sidor (AGENTER.md Regel 5).

Fem mönster återkom på varje sida i korrekturen av DoD-grundreglerna och är
rent mekaniska — de ska inte kosta hundratusentals tokens per sida i en
språkmodell:

  1. `linjeregel-prefix` — kapitälrubriker sätts mellan två tunna linjeregler,
     och linjens vänstra ände läses som ett inledande bindestreck (`- LYSSNA`).
  2. `raka-citattecken` — transkriptionen sätter `'…'`/`"…"` där trycket har
     `’…’`/`”…”`, även runt siffror (`slå ’6’ eller lägre`).
  3. `plusminus` — `±0` i tabellceller läses som `t0`, `I0`, `l0`, `*0`, `+0`.
  4. `kolumnsammanslagning` — ett element slår ihop vänster- och högerkolumnens
     rader på samma y-höjd; bbox blir då markant bredare än spaltmedianen.
  5. `lasordning` — elementlistans ordning avviker från bbox-y inom en spalt.
     Exporten följer arrayordningen literalt, så det är ett verkligt fel.

Utfallet är **kandidater, aldrig ändringar**: korrektionsposter med
`applied: false` och `source: "heuristik:<regel>"`, plus `review_reasons` för
strukturfynden. Specialisterna och advokaten börjar från listan i stället för
att leta, och advokaten avgör som alltid mot PNG:n.

Geometrifakta (verifierat): bbox ligger under `source.bbox` som
`[x, y, bredd, höjd]`, normaliserat, med y räknat från sidans NEDERKANT.
"""
import re
from pathlib import Path

from .corrections import KIND_OCR, make_correction
from .manifest import Manifest, atomic_write_json, page_file, read_json

# En kapitälrubrik satt mellan två tunna linjeregler, där endera linjens ände
# smugit in i texten. Vänsterregeln läses som ett bindestreck framför rubriken,
# högerregeln som ett bindestreck eller en punkt/kula efter den — och en rubrik
# kan bära båda (`- KUNSKAP OM MAGI -`, s. 52). Rubriken måste vara versal rakt
# igenom, annars är strecket sannolikt tryckt (punktlista, avstavat ord).
# Parenteser utesluts medvetet: `MAGE (-` i en träfftabell är en cell vars
# vänsterparentes hör till kolumnrubriken, inte en rubrik med linjeregelände.
HEADING_CORE = r"[A-ZÅÄÖ][A-ZÅÄÖ0-9 /.:’]*[A-ZÅÄÖ0-9.:’]"
HEADING_RULE_MARK = re.compile(
    r"^(?P<pre>[-–—]\s*)?(?P<rubrik>%s)(?P<post>\s*[-–—•])?"
    r"(?P<tail>\s*\[\?\])?$" % HEADING_CORE)

# Entydiga ±0-garbel. `10` utesluts medvetet: det går inte att skilja från
# talet tio, och siffror emenderas aldrig (Regel 8a).
PLUSMINUS_GARBLE = re.compile(r"^(?:[tTIil*+|]0|±[Oo])$")
PLUSMINUS_AMBIGUOUS = re.compile(r"^10$")

STRAIGHT_QUOTES = {"'": "’", '"': "”"}

# Kolumnsammanslagning: hur mycket bredare än sidans spaltbredd ett element
# måste vara, minsta antal element för att bredden alls ska kunna uppskattas,
# och minsta textlängd (en sammanslagen rad är två hela rader; en centrerad
# kapitälrubrik är bred men kort). Uppmätt på DoD-grundreglerna: spaltrader
# ~0,43, sammanslagna ~0,89.
MERGE_FACTOR = 1.4
MIN_COLUMN_ELEMENTS = 5
MIN_MERGE_TEXT = 40

# Läsordning: hur långt utanför grannarnas y-intervall ett element måste ligga
# för att det ska räknas som felplacerat i arrayen och inte som en snedställd
# rad, en tabellcell på samma höjd som sin etikett eller en spaltväxling.
# 0,05 av sidhöjden är ~2-3 textrader.
ORDER_TOLERANCE = 0.05

# Hur stor andel av vänsterspalten som måste ligga EFTER ett högerspaltselement
# i arrayen för att det ska räknas som felplacerat i början och inte som en
# vanlig spaltväxling mitt på sidan.
INTERLEAVE_SHARE = 0.8

RULES = ("linjeregel-prefix", "linjeregel-suffix", "raka-citattecken",
         "plusminus", "kolumnsammanslagning", "lasordning")


def _bbox(el):
    box = (el.get("source") or {}).get("bbox")
    if isinstance(box, (list, tuple)) and len(box) == 4:
        try:
            return [float(v) for v in box]
        except (TypeError, ValueError):
            return None
    return None


def _region(el):
    return (el.get("source") or {}).get("region") or "?"


def _add_candidate(el, correction):
    el.setdefault("corrections", []).append(correction)


def _add_flag(el, reason):
    el["needs_review"] = True
    reasons = el.setdefault("review_reasons", [])
    if reason not in reasons:
        reasons.append(reason)


# ---------------------------------------------------------------------------
# Regler på elementnivå
# ---------------------------------------------------------------------------

def rule_heading_dash(el):
    """`- LYSSNA`, `GEOGRAFI -`, `HASARDSPEL•` -> rubriken utan linjeregelände.

    Returnerar (regel, korrektion) så att prefix och suffix kan räknas var för
    sig. Bär rubriken båda ändarna rapporteras den som suffix — prefixet ensamt
    var det heuristiken redan fångade, och det är den kvarglömda högra änden som
    är nyheten (`- KUNSKAP OM MAGI -` fick suffixet kvar t.o.m. s. 52).
    """
    text = (el.get("text") or "").strip()
    m = HEADING_RULE_MARK.match(text)
    if not m:
        return []
    pre, post = m.group("pre"), m.group("post")
    if not (pre or post):
        return []  # ren rubrik utan linjeregelände — inget att föreslå
    rubrik = m.group("rubrik").strip()
    if len(rubrik) < 3:
        return []
    corrected = rubrik + (m.group("tail") or "")
    if post and pre:
        rule, vilken = "linjeregel-suffix", "båda linjereglernas ändar"
    elif post:
        rule, vilken = "linjeregel-suffix", "högra linjeregelns ände"
    else:
        rule, vilken = "linjeregel-prefix", "vänstra linjeregelns ände"
    return [(rule, make_correction(
        el.get("text"), corrected, 0.6,
        "Heuristik: kapitälrubrik med %s i texten. Rubriker sätts mellan två "
        "tunna linjeregler och linjens ände läses ofta som ett bindestreck "
        "(högerregelns spets ibland som en punkt/kula). Verifiera i PNG:n att "
        "inget streckglyf står i trycket — mät bredden: radbrytnings"
        "bindestreck 8–10 px vid ~236 dpi, halvfyrkant 18–20 px. Är rubriken "
        "avstavad över radbrytning är strecket tryckt och ska stå kvar."
        % vilken,
        "heuristik:%s" % rule, applied=False, kind=KIND_OCR))]


def rule_straight_quotes(el):
    """Raka citattecken -> typografiska. Ojämnt antal flaggas i stället."""
    text = el.get("text") or ""
    present = [ch for ch in STRAIGHT_QUOTES if ch in text]
    if not present:
        return []
    corrected = text
    for ch, repl in STRAIGHT_QUOTES.items():
        corrected = corrected.replace(ch, repl)
    return [make_correction(
        text, corrected, 0.6,
        "Heuristik: raka citattecken/apostrofer. Trycket har genomgående "
        "’…’ och ”…”, även runt siffror (`slå ’6’ eller lägre`). Ojämnt antal i "
        "elementet betyder att paret bryts över en elementgräns — kontrollera "
        "grannelementen innan du applicerar.",
        "heuristik:raka-citattecken", applied=False, kind=KIND_OCR)]


def rule_plusminus(el):
    """`t0`/`I0`/`*0`/`+0` -> `±0` i korta värdeelement."""
    text = (el.get("text") or "").strip()
    if PLUSMINUS_GARBLE.match(text):
        return [make_correction(
            el.get("text"), "±0", 0.6,
            "Heuristik: känt ±0-garbel i tabellvärde (plusminustecknet läses "
            "som t/I/l/*/+ följt av 0). Tecknet återställs, siffervärdet är "
            "oförändrat — verifiera glyfen i PNG:n (plus med separat vågrät "
            "linje under).",
            "heuristik:plusminus", applied=False, kind=KIND_OCR)]
    return []


def flag_plusminus_ambiguous(el):
    if PLUSMINUS_AMBIGUOUS.match((el.get("text") or "").strip()):
        return ("Heuristik (plusminus): kort värdeelement `10` kan vara ett "
                "feltytt `±0` — samma klass som t0/I0/*0. Går inte att skilja "
                "från talet tio deterministiskt; siffror emenderas aldrig. "
                "Läs cellen i PNG:n och avgör.")
    return None


# ---------------------------------------------------------------------------
# Regler på sidnivå (geometri)
# ---------------------------------------------------------------------------

def _median(values):
    vals = sorted(values)
    if not vals:
        return None
    mid = len(vals) // 2
    if len(vals) % 2:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2


def _percentile(values, q):
    vals = sorted(values)
    if not vals:
        return None
    idx = min(len(vals) - 1, max(0, int(round(q * (len(vals) - 1)))))
    return vals[idx]


def column_width(elements):
    """Sidans typiska spaltbredd, mätt som 90:e percentilen av elementbredderna.

    Medianen duger inte: en sida med många korta värdeelement (tabelletiketter,
    enstaka siffror) drar den ner till halva spaltbredden, och då ser varje
    normal brödtextrad "dubbelbred" ut. Percentilen fångar i stället den
    fullbreda raden som är spaltens faktiska mått, och stiger av sig själv på
    sidor där layouten verkligen är fullbred (då flaggas inget).
    """
    widths = [_bbox(el)[2] for el in elements if _bbox(el)]
    if len(widths) < MIN_COLUMN_ELEMENTS:
        return None
    return _percentile(widths, 0.90)


def rule_column_merge(elements):
    """Element som är markant bredare än sidans spaltbredd.

    Signaturen för en sammanslagen rad är att den täcker båda spalterna: bredden
    blir ~2× spaltbredden. Korta element filtreras bort — en centrerad
    kapitälrubrik spänner också över rännan men är inte en sammanslagning.
    """
    colw = column_width(elements)
    if not colw:
        return []
    hits = []
    for el in elements:
        box = _bbox(el)
        if not box or box[2] <= colw * MERGE_FACTOR:
            continue
        if len(el.get("text") or "") < MIN_MERGE_TEXT:
            continue
        hits.append((el,
                     "Heuristik (kolumnsammanslagning): bbox-bredd %.3f mot "
                     "sidans spaltbredd %.3f (faktor %.2f), x=%.3f–%.3f. "
                     "Elementet täcker båda spalterna och slår sannolikt ihop "
                     "två rader på samma y-höjd. Bryt ut halvorna med uppmätt "
                     "bbox och ange läsordning — gissa inte gränsen."
                     % (box[2], colw, box[2] / colw, box[0], box[0] + box[2])))
    return hits


def rule_column_interleaving(elements):
    """Högerkolumnselement som ligger före vänsterkolumnen i arrayen.

    Läsordningen på en tvåspaltssida är hela vänsterspalten, sedan hela
    högerspalten. Ett högerkolumnselement inklämt före vänsterspalten är
    felplacerat — det inträffade på sida 40, där högerkolumnens första rad låg
    som element nr 2, före hela vänsterspalten. Den varianten syns inte i den
    y-baserade kontrollen nedan, eftersom elementet ligger först i sin egen spalt.
    """
    left_idx = [i for i, el in enumerate(elements)
                if _region(el) == "vänsterkolumn" and _bbox(el)]
    right = [(i, el) for i, el in enumerate(elements)
             if _region(el) == "högerkolumn" and _bbox(el)]
    if len(left_idx) < MIN_COLUMN_ELEMENTS or len(right) < MIN_COLUMN_ELEMENTS:
        return []
    hits = []
    for idx, el in right:
        after = sum(1 for i in left_idx if i > idx)
        # Nästan hela vänsterspalten ligger EFTER elementet — det är inte en
        # spaltväxling mitt i sidan utan en rad som hamnat i början av arrayen.
        if after < INTERLEAVE_SHARE * len(left_idx):
            continue
        # Korta element är sidhuvud/tabellceller, inte brödtextrader ur spalten.
        if len(el.get("text") or "") < MIN_MERGE_TEXT:
            continue
        hits.append((el,
                     "Heuristik (läsordning): elementet hör till högerkolumnen "
                     "men ligger på plats %d i arrayen, före %d av "
                     "vänsterkolumnens %d element. Läsordningen är hela "
                     "vänsterspalten, sedan hela högerspalten, och exporten "
                     "följer arrayordningen literalt. Kontrollera mot PNG:n var "
                     "raden hör — högerspaltens första rad fortsätter ofta "
                     "grammatiskt ur vänsterspaltens sista."
                     % (idx, after, len(left_idx))))
    return hits


def rule_reading_order(elements):
    """Arrayordning mot bbox-y inom varje spalt (y minskar framåt)."""
    hits = []
    by_region = {}
    for idx, el in enumerate(elements):
        box = _bbox(el)
        if box:
            by_region.setdefault(_region(el), []).append((idx, el, box[1]))
    for region, items in by_region.items():
        if len(items) < 3:
            continue
        for pos, (idx, el, y) in enumerate(items):
            before = items[pos - 1][2] if pos else None
            after = items[pos + 1][2] if pos + 1 < len(items) else None
            if before is None or after is None:
                continue
            # Elementet ligger tydligt utanför sina grannars y-intervall =
            # felplacerat i arrayen, inte bara en snedställd rad eller en
            # tabellcell på samma höjd som sin etikett.
            if not (after - ORDER_TOLERANCE <= y <= before + ORDER_TOLERANCE):
                # Elementet självt uppfyller o_y >= y och blev därför sitt eget
                # föreslagna mål ("rätt plats är efter p047_e51" för e51) när
                # det låg sist bland grannarna ovanför. Det såg ut som en
                # motsägelse och kostade en agentkörning per sida att avfärda
                # (s. 47, 49, 52) — uteslut det ur urvalet.
                bracket = [(o_idx, o_el.get("id"))
                           for o_idx, o_el, o_y in items
                           if o_y >= y and o_idx != idx]
                efter = bracket[-1][1] if bracket else "?"
                hits.append((el,
                             "Heuristik (läsordning): elementet ligger på plats "
                             "%d i arrayen men dess y=%.3f hör mellan grannar "
                             "med y=%.3f och y=%.3f i %s. Exporten följer "
                             "arrayordningen literalt, så detta är ett verkligt "
                             "fel. Rätt plats är sannolikt efter %s — verifiera "
                             "mot PNG:n."
                             % (idx, y, before, after, region, efter)))
    return hits


# ---------------------------------------------------------------------------
# Sida och körning
# ---------------------------------------------------------------------------

def scan_page(data):
    """Kör alla regler på en validerad sid-JSON.

    Returnerar (ny_data, summering). Indata muteras inte.
    """
    import copy
    out = copy.deepcopy(data)
    elements = out.get("elements", [])
    counts = {rule: 0 for rule in RULES}

    for el in elements:
        # Linjeregelregeln avgör själv om träffen är prefix eller suffix.
        for rule, corr in rule_heading_dash(el):
            _add_candidate(el, corr)
            counts[rule] += 1
        for rule, fn in (("raka-citattecken", rule_straight_quotes),
                         ("plusminus", rule_plusminus)):
            for corr in fn(el):
                _add_candidate(el, corr)
                counts[rule] += 1
        flag = flag_plusminus_ambiguous(el)
        if flag:
            _add_flag(el, flag)
            counts["plusminus"] += 1

    for rule, fn in (("kolumnsammanslagning", rule_column_merge),
                     ("lasordning", rule_reading_order),
                     ("lasordning", rule_column_interleaving)):
        for el, reason in fn(elements):
            _add_flag(el, reason)
            counts[rule] += 1

    out["source"] = "heuristik"
    out["regler"] = counts
    return out, counts


def preflight(workdir, pages=None, force=False):
    """Skriv page_NNN.review/heuristik.json för sidor som väntar på korrektur.

    Idempotent: en sida med befintlig heuristik.json hoppas över om inte
    `force`. Sidor som redan har final.json besiktas inte.
    """
    workdir = Path(workdir)
    m = Manifest.load(workdir)
    results = []
    for no in m.page_numbers():
        if pages and no not in pages:
            continue
        validated = page_file(workdir, no, "validated.json")
        if not validated.is_file() or page_file(workdir, no, "final.json").is_file():
            continue
        data = read_json(validated)
        if (data.get("skipped") or {}).get("reason") == "illustration_only":
            continue
        target = Path(str(page_file(workdir, no, "review"))) / "heuristik.json"
        if target.is_file() and not force:
            results.append((no, None))
            continue
        out, counts = scan_page(data)
        atomic_write_json(target, out)
        results.append((no, counts))
    ensure_decisions_file(workdir)
    return results


DECISIONS_TEMPLATE = """# Boknivåbeslut och precedens

Denna fil är korrekturteamets gemensamma minne för **hela boken**. Alla tre
agenterna läser den innan de börjar; **djävulens advokat** — och bara den —
skriver till den när en fråga är avgjord.

Syftet är att samma fråga inte ska utredas om på varje sida. Skriv kort, med
sidan där beslutet togs som belägg.

## Avgjort

<!-- Exempel på formen:
- **Vattenstämpeln `... © ...` under sidfoten** läggs INTE till: digital
  utgåvas stämpel, utanför satsytan, utelämnad i alla drafter. (s. 40, 42)
- **Kapitälrubrikers `- `-prefix** är linjeregelns vänstra ände, tas bort som
  `kind: ocr`. Motsatsen (lägga till `- `) avvisas. (s. 41)
-->

## Öppet — avgörs en gång för hela boken

<!-- T.ex. elementtypning av sidhuvud/rubriker, halvfyrkant i negativa
tabellvärden, tryckfelskandidater som väntar på användarens beslut. -->
"""


def decisions_file(workdir):
    return Path(workdir) / "beslut.md"


def ensure_decisions_file(workdir):
    path = decisions_file(workdir)
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DECISIONS_TEMPLATE, encoding="utf-8")
    return path
