"""Deterministisk förbesiktning av validerade sidor (AGENTER.md Regel 5).

Mönstren nedan återkom sida efter sida i korrekturen av DoD-grundreglerna och
är rent mekaniska — de ska inte kosta hundratusentals tokens per sida i en
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
  6. `radsammanslagning` — ett element spänner över TVÅ tryckta rader vertikalt
     men återger bara den ena; bbox-höjden blir ~2× sidans medianradhöjd.
  7. `tabellkandidat` — en tryckt tabell som transkriberats som en följd av
     `paragraph` i stället för ett `table`-element. Strukturen går då förlorad
     för gott: ingenting nedströms kan återskapa rad- och kolumnindelningen.

Utfallet är **kandidater, aldrig ändringar**: korrektionsposter med
`applied: false` och `source: "heuristik:<regel>"`, plus `review_reasons` för
strukturfynden. En feltypad tabell är ett TYPNINGSfel, inte ett textfel, och
flaggas därför alltid som `needs_review` — aldrig som korrektionspost.
Specialisterna och advokaten börjar från listan i stället för att leta, och
advokaten avgör som alltid mot PNG:n.

Läsordningsreglerna (4 nedan) förutsätter tvåspaltig löptext och ger falska
larm på tabellsidor och blanketter. `classify_page` klassificerar därför sidan
geometriskt först, och de reglerna körs bara på löptextsidor.

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

# Ett element bredare än så här (mot spaltbredden) spänner över båda spalterna
# och tillhör därför ingendera — sidhuvud, linjaler och sidbreda tabeller.
WIDE_ELEMENT = 1.2

# Vertikal radsammanslagning: ett element som spänner över två tryckta rader
# men bara återger den ena. Uppmätt på s. 60 (0,0336 mot medianen 0,0161 =
# 2,09×) och bekräftat som mönster på s. 68. Faktorn ligger med avsikt högt:
# rubriker, diakritband och spärrad sats gör 1,2–1,4× helt normalt, och en
# regel som larmar där kostar mer agenttid än den sparar.
ROW_MERGE_FACTOR = 1.8
MIN_HEIGHT_ELEMENTS = 8
# Höjden ensam räcker inte: en rubrik satt i stor grad är också hög. Skillnaden
# är att rubrikens GLYFER är stora medan en sammanslagen rad har normalstora
# glyfer — bara bboxen är för hög. Måttet är bbox-bredd per tecken, jämförd med
# sidans median. Uppmätt på hela boken: sammanslagningen på s. 60 ligger på
# 1,03×, rubrikerna på 1,7–9,2× och skanningsgarblet i illustrationerna
# (s. 31, 37, 39) på 0,06–0,5×. Bandet nedan släpper bara igenom det första.
ROW_MERGE_GLYPH_MIN = 0.7
ROW_MERGE_GLYPH_MAX = 1.4
# Elementtyper som per definition rymmer flera rader och därför aldrig kan
# vara en "sammanslagen rad".
MULTIROW_TYPES = ("table", "statblock", "list")

# Tabellkandidat. En tabellcell är kort; en brödtextrad är det inte. 40 tecken
# skiljer dem i DoD-grundreglerna (spaltrader ligger på 45–55 tecken).
TABLE_CELL_MAX_TEXT = 40
# Hur tätt två vänsterkanter måste ligga för att räknas till samma kolumn.
# Uppmätt: kolumn 1 på s. 61 sprider sig 0,111–0,117, kolumn 2 ligger på 0,348.
TABLE_X_TOLERANCE = 0.03
# Andelen av medianradhöjden som två celler får skilja i y och ändå räknas till
# samma rad. Uppmätt spridning inom en rad: 0,002–0,005 mot radavstånd 0,015.
TABLE_ROW_TOLERANCE = 0.6
# En tabells rader följer tätt på varandra. Fältgrupperna i en blankett gör det
# inte: teckenrutorna på s. 67–68 ligger 0,06–0,38 isär trots att två av dem
# råkar börja på samma y-höjd. Att två rutor delar y betyder INTE att de hör
# ihop (beslut s. 67) — så rader räknas bara i sammanhängande följd, med
# högst tre radhöjders lucka mellan två rader. Tre räcker för en tabell vars
# celler radbryts till två rader (2× radhöjd) men stänger ute blankettens
# fältgrupper (4× och uppåt). Bryts en tabell på mitten rapporteras den som
# två block, vilket är rätt: en lucka den storleken är oftast två tabeller.
TABLE_ROW_GAP_FACTOR = 3.0
TABLE_MIN_ROWS = 3
TABLE_MIN_COLUMNS = 2
# Typer som transkriptionen felaktigt kan ha valt för en tabellcell. `table_cell`
# är INTE med: den är rätt reservform och monteras av pipeline.tables.assemble.
TABLE_SUSPECT_TYPES = ("paragraph", "boxed_text")

# Sidtyper (geometrisk klassificering, se classify_page).
PAGE_PROSE = "löptext"
PAGE_TABLE = "tabellsida"
PAGE_FORM = "blankett"
PAGE_OTHER = "annat"
# Hur stor andel av sidans element som måste ingå i ett tabellblock för att
# sidan ska räknas som tabellsida och inte som löptext med en liten tabell i.
PAGE_TABLE_SHARE = 0.30
# Blankett: nästan bara korta element, utspridda över många x-lägen.
PAGE_FORM_SHORT_SHARE = 0.60
PAGE_FORM_MIN_CLUSTERS = 3

RULES = ("linjeregel-prefix", "linjeregel-suffix", "raka-citattecken",
         "plusminus", "kolumnsammanslagning", "lasordning",
         "radsammanslagning", "tabellkandidat")


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


def _column_of(el, elements):
    """Vilken spalt elementets bbox FAKTISKT ligger i — etiketten struntar vi i.

    Regionnamnet kommer ur uppmätningen och kan vara fel. På sida 4 låg
    högerspaltens avsnittsrubrik som element nr 2, före hela vänsterspalten,
    med regionen felaktigt satt till `sidhuvud` — och eftersom regeln filtrerade
    på etiketten passerade läsordningsfelet obemärkt. Geometrin ljuger inte:
    ett element vars vänsterkant ligger bortom sidans mitt hör till högerspalten,
    oavsett vad etiketten påstår.
    """
    box = _bbox(el)
    if not box:
        return None
    colw = column_width(elements)
    # Utan uppmätt spaltbredd finns ingen tvåspaltsgeometri att döma mot.
    if not colw or box[2] > colw * WIDE_ELEMENT:
        return None
    return "högerkolumn" if box[0] >= 0.5 else "vänsterkolumn"


def rule_column_interleaving(elements):
    """Högerkolumnselement som ligger före vänsterkolumnen i arrayen.

    Läsordningen på en tvåspaltssida är hela vänsterspalten, sedan hela
    högerspalten. Ett högerkolumnselement inklämt före vänsterspalten är
    felplacerat — det inträffade på sida 40, där högerkolumnens första rad låg
    som element nr 2, före hela vänsterspalten. Den varianten syns inte i den
    y-baserade kontrollen nedan, eftersom elementet ligger först i sin egen spalt.
    """
    left_idx = [i for i, el in enumerate(elements)
                if _column_of(el, elements) == "vänsterkolumn"]
    right = [(i, el) for i, el in enumerate(elements)
             if _column_of(el, elements) == "högerkolumn"]
    if len(left_idx) < MIN_COLUMN_ELEMENTS or len(right) < MIN_COLUMN_ELEMENTS:
        return []
    hits = []
    for idx, el in right:
        after = sum(1 for i in left_idx if i > idx)
        # Nästan hela vänsterspalten ligger EFTER elementet — det är inte en
        # spaltväxling mitt i sidan utan en rad som hamnat i början av arrayen.
        if after < INTERLEAVE_SHARE * len(left_idx):
            continue
        # Korta element är sidhuvud/tabellceller, inte brödtextrader ur spalten
        # — men en RUBRIK undantas: den är kort av naturen, och det är just
        # rubriker som hamnar först i arrayen (s. 4: högerspaltens
        # `ATT LEDA SPELET` låg som element nr 2, så hela vänsterspalten
        # renderades under en rubrik den inte tillhör).
        if (el.get("type") != "heading"
                and len(el.get("text") or "") < MIN_MERGE_TEXT):
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


def _renders(el):
    """Bidrar elementet med något till exporten?

    Ett element som tömts och typats om (sidgrafik, konsumerad halva av en
    kolumnsammanslagning) har kvar sin gamla bbox men skriver ingenting. Dess
    plats i arrayen kan därför inte vara ett läsordningsfel — och på de
    färdiga sidorna 24, 26, 49, 64 och 65 var det precis sådana element som
    stod för larmen.
    """
    if el.get("removed"):
        return False
    return bool((el.get("text") or "").strip() or el.get("data"))


def rule_reading_order(elements):
    """Arrayordning mot bbox-y inom varje spalt (y minskar framåt)."""
    hits = []
    by_region = {}
    for idx, el in enumerate(elements):
        box = _bbox(el)
        if box and _renders(el):
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


def rule_row_merge(elements):
    """Element vars bbox-HÖJD är ~2× sidans medianradhöjd.

    `rule_column_merge` mäter bara bredd och missar därför den vertikala
    varianten: elementet spänner över två tryckta rader men återger bara den
    ena, så en hel rad boktext saknas i draften utan att något ser tomt ut.
    Hittad på s. 60 (`Genma Frigke a Vands…`, 2,09× medianen — raden ovanför
    var helt borta) och bekräftad som mönster på s. 68.

    Glyfstorleken avgör om höjden är misstänkt: en rubrik i stor grad är hög
    för att bokstäverna är stora, en sammanslagen rad har normalstora
    bokstäver i en för hög box. Se ROW_MERGE_GLYPH_MIN/MAX.
    """
    boxes = [(el, _bbox(el)) for el in elements
             if _bbox(el) and not el.get("removed")
             and el.get("type") not in MULTIROW_TYPES
             and (el.get("text") or "").strip()]
    if len(boxes) < MIN_HEIGHT_ELEMENTS:
        return []
    med_h = _median([box[3] for _, box in boxes])
    med_glyph = _median([box[2] / len((el.get("text") or "").strip())
                         for el, box in boxes])
    colw = column_width(elements)
    if not med_h or not med_glyph:
        return []
    # Bär två element SAMMA uppmätta box har mätningen slagit ihop två tätt
    # satta rader till ETT band, och transkriptionen har gett båda elementen
    # bandet. Då finns båda de tryckta raderna i draften — regelns antagande
    # ("återger bara den ena") gäller inte, och larmet är alltid falskt.
    # Uppmätt: del II s. 6 och 13, sex kandidater, sex falska positiver.
    delad = set()
    sedd = set()
    for _, box in boxes:
        nyckel = tuple(round(v, 6) for v in box)
        if nyckel in sedd:
            delad.add(nyckel)
        sedd.add(nyckel)

    hits = []
    for el, box in boxes:
        if box[3] < med_h * ROW_MERGE_FACTOR:
            continue
        if tuple(round(v, 6) for v in box) in delad:
            continue
        # Ett element som också är för BRETT är en kolumnsammanslagning och
        # ägs av rule_column_merge — flagga inte samma element två gånger.
        if colw and box[2] > colw * MERGE_FACTOR:
            continue
        glyph = box[2] / len((el.get("text") or "").strip())
        if not (ROW_MERGE_GLYPH_MIN <= glyph / med_glyph
                <= ROW_MERGE_GLYPH_MAX):
            continue
        hits.append((el,
                     "Heuristik (radsammanslagning): bbox-höjd %.4f mot sidans "
                     "medianradhöjd %.4f (faktor %.2f), men glyfbredden är "
                     "normal (%.2f× sidans median) — elementet är alltså inte "
                     "satt i större grad. Det spänner sannolikt över TVÅ "
                     "tryckta rader och återger bara den ena; den andra saknas "
                     "då helt i draften utan att något ser tomt ut. Räkna "
                     "bläckband i PNG:n över elementets y-intervall (dra bort "
                     "diakritband för ä/ö/å) och lägg till den saknade raden "
                     "med uppmätt bbox."
                     % (box[3], med_h, box[3] / med_h, glyph / med_glyph)))
    return hits


# ---------------------------------------------------------------------------
# Tabellkandidat och sidtypsklassificering
# ---------------------------------------------------------------------------

def _x_clusters(values, tolerance=TABLE_X_TOLERANCE):
    """Enkellänksklustring av vänsterkanter -> lista av (lo, hi)."""
    groups = []
    for v in sorted(values):
        if groups and v - groups[-1][1] <= tolerance:
            groups[-1][1] = v
        else:
            groups.append([v, v])
    return [tuple(g) for g in groups]


def _cluster_of(clusters, value):
    for i, (lo, hi) in enumerate(clusters):
        if lo <= value <= hi:
            return i
    return None


def _y_rows(items, tolerance):
    """Gruppera (y, ...)-poster till rader uppifrån och ned.

    Radens referens är dess ÖVERSTA element; nästa element hör till samma rad
    så länge det ligger inom toleransen därifrån. Enkellänkning duger inte —
    den kedjar ihop hela spalten när radavståndet är litet.
    """
    rows = []
    ref = None
    for item in sorted(items, key=lambda t: -t[0]):
        if ref is None or ref - item[0] > tolerance:
            rows.append([])
            ref = item[0]
        rows[-1].append(item)
    return rows


def table_blocks(elements):
    """Följder av korta `paragraph`/`boxed_text` som bildar ett radvist rutnät.

    Detta är felet som kostade mest i DoD-grundreglerna: från sida 40 typade
    transkriptionen varje tabell som en följd av `paragraph`, och då är
    rad-/kolumnstrukturen borta för gott — `tables.assemble` har inget att
    montera och exporten skriver lösa stycken.

    Signalen är rent geometrisk: korta element vars vänsterkanter faller i två
    eller flera täta x-kluster som ÅTERKOMMER radvis. Ett block räknas först
    när minst TABLE_MIN_ROWS rader parar ihop minst TABLE_MIN_COLUMNS sådana
    kolumner — en enstaka etikett med sitt värde bredvid räcker inte.

    Bedömningen görs per region: på s. 61 ligger tabellens tredje kolumn i
    `högerkolumn` medan de två första ligger i `vänsterkolumn`, och de två
    första räcker gott för att slå ut.

    Returnerar en lista av dict: {region, columns, rows, ids, anchor}.
    """
    order = {id(el): i for i, el in enumerate(elements)}
    by_region = {}
    for el in elements:
        if el.get("type") not in TABLE_SUSPECT_TYPES or el.get("removed"):
            continue
        box = _bbox(el)
        text = (el.get("text") or "").strip()
        if not box or not text or len(text) > TABLE_CELL_MAX_TEXT:
            continue
        by_region.setdefault(_region(el), []).append((el, box))

    blocks = []
    for region, items in by_region.items():
        if len(items) < TABLE_MIN_ROWS * TABLE_MIN_COLUMNS:
            continue
        clusters = _x_clusters([box[0] for _, box in items])
        if len(clusters) < TABLE_MIN_COLUMNS:
            continue
        med_h = _median([box[3] for _, box in items])
        rows = _y_rows([(box[1], el, _cluster_of(clusters, box[0]))
                        for el, box in items],
                       max(med_h * TABLE_ROW_TOLERANCE, 0.004))
        # En kolumn räknas bara om den återkommer radvis; en enstaka
        # indragen rubrik bildar annars sin egen "kolumn".
        per_cluster = {}
        for row in rows:
            for _, _, ci in row:
                per_cluster[ci] = per_cluster.get(ci, 0) + 1
        recurring = {ci for ci, n in per_cluster.items()
                     if n >= TABLE_MIN_ROWS}
        if len(recurring) < TABLE_MIN_COLUMNS:
            continue
        paired = []
        for row in rows:
            cells = [(el, ci) for _, el, ci in row if ci in recurring]
            if len({ci for _, ci in cells}) < TABLE_MIN_COLUMNS:
                continue
            paired.append((row[0][0], cells))
        # Bara rader i sammanhängande följd bildar en tabell — se
        # TABLE_ROW_GAP_FACTOR. En blankett faller isär här.
        gap = max(med_h * TABLE_ROW_GAP_FACTOR, 0.02)
        runs, prev = [], None
        for y, cells in paired:
            if prev is None or prev - y > gap:
                runs.append([])
            runs[-1].append(cells)
            prev = y
        for run in runs:
            if len(run) < TABLE_MIN_ROWS:
                continue
            members = [el for cells in run for el, _ in cells]
            members.sort(key=lambda el: order[id(el)])
            used = {ci for cells in run for _, ci in cells}
            blocks.append({"region": region, "columns": len(used),
                           "rows": len(run),
                           "ids": [el.get("id") for el in members],
                           "anchor": members[0]})
    blocks.sort(key=lambda b: order[id(b["anchor"])])
    return blocks


def rule_table_candidate(elements):
    """Tryckt tabell som typats `paragraph` -> needs_review, aldrig korrektion.

    Att elementtypen är fel är ett TYPNINGSfel, inte ett textfel: texten är
    riktig, det är strukturen som saknas. Det finns därför ingen `corrected`
    att föreslå — utfallet är en flagga med gissat kolumnantal och de
    deltagande elementens id:n, och advokaten avgör mot PNG:n.
    """
    hits = []
    for block in table_blocks(elements):
        ids = block["ids"]
        visade = ", ".join(ids[:12]) + (" …" if len(ids) > 12 else "")
        hits.append((block["anchor"],
                     "Heuristik (tabellkandidat): %d korta element i %s bildar "
                     "ett rutnät på %d kolumner × %d rader — det ser ut som en "
                     "tryckt tabell som typats `paragraph` i stället för "
                     "`table` med `data.headers`/`data.rows`. Strukturen går "
                     "inte att återskapa nedströms, så detta måste rättas i "
                     "elementtypningen, inte i exporten. Deltagande element: "
                     "%s. Verifiera mot PNG:n: är det en tabell, typa om till "
                     "`table` (eller till `table_header`/`table_cell` om "
                     "raderna inte går att para ihop säkert — "
                     "`pipeline.tables.assemble` monterar dem). Detta är ett "
                     "typningsfel och ska aldrig bli en korrektionspost."
                     % (len(ids), block["region"], block["columns"],
                        block["rows"], visade)))
    return hits


def classify_page(elements):
    """Sidtyp ur ren geometri: löptext, tabellsida, blankett eller annat.

    Läsordningsreglerna bygger på att sidan är tvåspaltig löptext med hela
    vänsterspalten före hela högerspalten. På tabellsidor är den ordningen
    radvis i stället för spaltvis, och på blanketter går den fältgrupp för
    fältgrupp — där ger reglerna falska larm som kostar ren agenttid
    (s. 61, 64, 65, 67, 68 i DoD-grundreglerna).
    """
    body = [el for el in elements
            if el.get("type") != "page_artifact" and not el.get("removed")
            and _bbox(el) and (el.get("text") or "").strip()]
    if len(body) < MIN_COLUMN_ELEMENTS * 2:
        return PAGE_OTHER

    i_tabell = set()
    for block in table_blocks(elements):
        i_tabell.update(block["ids"])
    if len(i_tabell) >= PAGE_TABLE_SHARE * len(body):
        return PAGE_TABLE

    korta = [el for el in body
             if len((el.get("text") or "").strip()) <= TABLE_CELL_MAX_TEXT]
    clusters = _x_clusters([_bbox(el)[0] for el in body])
    if (len(korta) >= PAGE_FORM_SHORT_SHARE * len(body)
            and len(clusters) >= PAGE_FORM_MIN_CLUSTERS):
        return PAGE_FORM

    regions = {}
    for el in body:
        regions[_region(el)] = regions.get(_region(el), 0) + 1
    if (regions.get("vänsterkolumn", 0) >= MIN_COLUMN_ELEMENTS
            and regions.get("högerkolumn", 0) >= MIN_COLUMN_ELEMENTS):
        return PAGE_PROSE
    return PAGE_OTHER


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

    sidtyp = classify_page(elements)
    sidnivå = [("radsammanslagning", rule_row_merge),
               ("tabellkandidat", rule_table_candidate)]
    # Kolumnsammanslagningen mäter mot medianen av sidans elementbredder. På en
    # blankett är medianen de korta fältraderna ("Typ: Buske"), så satsytans
    # normalbreda rader ser ut att spänna över rännan. Uppmätt: del II s. 53,
    # fyra kandidater, fyra falska positiver — spaltrännan korsades aldrig.
    if sidtyp != PAGE_FORM:
        sidnivå.insert(0, ("kolumnsammanslagning", rule_column_merge))
    # Läsordningsreglerna gäller bara tvåspaltig löptext. På tabellsidor läses
    # raderna tvärs över spalterna och på blanketter fältgrupp för fältgrupp,
    # så där pekar de ut fel destination och kostar bara agenttid att avfärda.
    if sidtyp == PAGE_PROSE:
        sidnivå += [("lasordning", rule_reading_order),
                    ("lasordning", rule_column_interleaving)]

    for rule, fn in sidnivå:
        for el, reason in fn(elements):
            _add_flag(el, reason)
            counts[rule] += 1

    out["source"] = "heuristik"
    out["sidtyp"] = sidtyp
    out["regler"] = counts
    return out, counts


def preflight(workdir, pages=None, force=False):
    """Skriv page_NNN.review/heuristik.json för sidor som väntar på korrektur.

    Idempotent: en sida med befintlig heuristik.json hoppas över om inte
    `force`. En FÄRDIG sida (final.json) besiktas inte i normalflödet — den är
    redan korrekturläst.

    Med `force` besiktas den ändå, mot sin final.json. Utan det går en färdig
    bok inte att screena alls, och det är ett verkligt hål: reglerna kommer
    till efter hand, och en bok som extraherades innan en regel fanns blir
    aldrig prövad mot den. DoD-grundreglernas del I är korrekturläst och klar
    men aldrig screenad en enda gång — den ger 66 kandidater på sex regler,
    däribland 16 tryckta tabeller som ligger som lösa `paragraph`. Samma sak
    behövs efter en lagning av `pipeline/rows.py`: fyra av åtta regler bygger
    på bbox, och deras utfall ändras när geometrin mäts om.
    """
    workdir = Path(workdir)
    m = Manifest.load(workdir)
    results = []
    for no in m.page_numbers():
        if pages and no not in pages:
            continue
        final = page_file(workdir, no, "final.json")
        validated = page_file(workdir, no, "validated.json")
        if final.is_file() and not force:
            continue
        source = final if final.is_file() else validated
        if not source.is_file():
            continue
        data = read_json(source)
        if (data.get("skipped") or {}).get("reason") == "illustration_only":
            continue
        target = Path(str(page_file(workdir, no, "review"))) / "heuristik.json"
        if target.is_file() and not force:
            results.append((no, None))
            continue
        out, counts = scan_page(data)
        # Provenienssträngen måste följa med: en heuristik.json kan nu vara
        # räknad antingen ur draften eller ur den färdiga sidan, och utan det
        # går de två inte att skilja åt i efterhand.
        out["source_file"] = source.name
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


# ---------------------------------------------------------------------------
# Typdrift över boken
# ---------------------------------------------------------------------------
#
# En lång transkription tappar sina egna typkonventioner mitt i boken. I
# DoD-grundreglerna del I slutade `heading` förekomma efter s. 38, `boxed_text`
# efter s. 32, och sidhuvudena bytte från `page_artifact` till `paragraph` vid
# s. 40. Ingenting larmade: varje sida var för sig fullt rimlig, och boken
# förklarades klar med hela sin andra halva strukturlös i läsexporten.
#
# Det krävs TVÅ signaler, för de tre fallen ser olika ut i datan:
#
#   * `heading` och `boxed_text` upphör helt — de fångas av att typen slutar
#     förekomma.
#   * Sidhuvudena gör det INTE. Foliesiffrorna håller `page_artifact` vid liv
#     på varje sida, så typen försvinner aldrig. Signalen är i stället att en
#     återkommande sträng på samma plats byter typ mitt i boken.
#
# Reglerna är boknivå och kan därför inte köras i sidloopen.

# Hur många sidor en typ måste ha använts på innan ett upphörande är ett larm.
DRIFT_MIN_PAGES = 5
# Hur många sidor tystnaden måste vara för att inte vara ett kapitel utan tabeller.
DRIFT_MIN_SILENCE = 8
# Hur många sidor i rad ett sidhuvud måste stå på för att räknas som möblemang.
FURNITURE_MIN_RUN = 3
# Typer som är två representationer av SAMMA sak räknas ihop. Kontraktet
# tillåter en lista som ett `list` med alla punkter i `data.items` eller som en
# följd av `list_item`, och en tabell som `table` eller som reservformen
# `table_header`/`table_cell`. Byter en bok representation är det ingen drift —
# räknas de var för sig larmar regeln på varje bok som gör det.
DRIFT_FAMILIES = (
    ("heading", ("heading",)),
    ("boxed_text", ("boxed_text",)),
    ("table", ("table", "table_cell", "table_header")),
    ("list", ("list", "list_item")),
)
# Hur mycket större grad som räcker för att skillnaden ska vara
# typografisk och inte drift.
GRADE_FACTOR = 1.5


def _topmost(elements):
    """Sidans översta element enligt mätningen (y räknas från nederkant)."""
    med = [el for el in elements if _bbox(el)]
    if not med:
        return None
    return max(med, key=lambda el: _bbox(el)[1])


def drift_ceased_types(pages):
    """Typer som användes stadigt och sedan slutade förekomma.

    `pages` är [(sidnummer, elementlista)] i sidordning.
    """
    sidor = [no for no, _ in pages]
    if not sidor:
        return []
    sista = sidor[-1]
    # Tystnaden mäts i LÖPTEXTsidor. Ett register, en blankett och en pärm har
    # inga exempelrutor, och en bok slutar nästan alltid med sådana sidor —
    # räknas de med larmar regeln på var enda bok vid dess sista uppslag.
    prosa = {no for no, els in pages if classify_page(els) == PAGE_PROSE}
    hits = []
    for typ, familj in DRIFT_FAMILIES:
        med = [no for no, els in pages
               if any(e.get("type") in familj for e in els)]
        if len(med) < DRIFT_MIN_PAGES:
            continue
        tystnad = sum(1 for no in prosa if no > med[-1])
        if tystnad < DRIFT_MIN_SILENCE:
            continue
        hits.append(
            "Typdrift: `%s` användes på %d sidor upp till s. %d och förekommer "
            "sedan inte alls på bokens %d återstående löptextsidor (s. %d–%d). En bok byter "
            "sällan struktur så — kontrollera om transkriptionen tappade typen "
            "mitt i körningen. I del I slutade `heading` efter s. 38 och "
            "`boxed_text` efter s. 32, och hela andra halvan blev strukturlös "
            "i läsexporten."
            % (typ, len(med), med[-1], tystnad, med[-1] + 1, sista))
    return hits


def drift_furniture_retyped(pages):
    """Återkommande sidmöblemang som byter elementtyp mitt i boken.

    Ett löpande sidhuvud står med samma lydelse högst upp på sida efter sida.
    Byter det typ är antingen den gamla eller den nya typningen fel, och båda
    kan inte gälla i samma bok.
    """
    per_text = {}
    for no, els in pages:
        # Ett löpande sidhuvud är definierat i förhållande till en sida med
        # sats. En kapitelavdelare — bara kapitelnamnet på en i övrigt tom sida
        # — har inget sidhuvud, och dess titel har ofta samma lydelse. Räknas
        # den med larmar regeln på varje kapitelöppning (del III s. 3: `MAGI`
        # som heading på avdelarsidan, page_artifact på sidorna efter).
        kropp = [e for e in els
                 if e.get("type") != "page_artifact" and _bbox(e)
                 and (e.get("text") or "").strip()]
        if len(kropp) < MIN_COLUMN_ELEMENTS:
            continue
        topp = _topmost(els)
        if topp is None:
            continue
        text = (topp.get("text") or "").strip()
        if not text or len(text) > 60:
            continue
        per_text.setdefault(text, []).append((no, topp.get("type"),
                                              _bbox(topp)[3]))

    hits = []
    for text, forekomster in sorted(per_text.items()):
        if len(forekomster) < FURNITURE_MIN_RUN:
            continue
        typer = {}
        for no, typ, _ in forekomster:
            typer.setdefault(typ, []).append(no)
        if len(typer) < 2:
            continue
        # Sektionens FÖRSTA sida bär ofta titeln med samma lydelse som det
        # löpande sidhuvudet — men satt i egen grad. Då är typskillnaden
        # typografiskt motiverad, inte drift. Del I: sidhuvuden mäter
        # 0,010–0,015, sektionstitlarna 0,028–0,038; utan det testet larmar
        # regeln på var enda sektionsöppning i boken.
        hojder = sorted(h for _, _, h in forekomster if h)
        if hojder and hojder[-1] >= hojder[len(hojder) // 2] * GRADE_FACTOR:
            continue
        beskrivning = "; ".join(
            "`%s` på s. %s" % (typ, _sidlista(nos))
            for typ, nos in sorted(typer.items(), key=lambda x: -len(x[1])))
        hits.append(
            "Typdrift: sidhuvudet %r står överst på %d sidor men är typat på "
            "%d olika sätt — %s. Samma möblemang kan inte vara två saker i "
            "samma bok. Kontraktet säger `page_artifact` för sidhuvud; i del I "
            "typades det `paragraph` från s. 40 och sidhuvudena flöt då in i "
            "läsexporten som brödtext, mitt i meningar och mitt i ett avstavat "
            "ord över sidbrytningen."
            % (text, len(forekomster), len(typer), beskrivning))
    return hits


def _sidlista(nos, max_visade=6):
    if len(nos) <= max_visade:
        return ", ".join(str(n) for n in nos)
    return "%s … %s (%d st)" % (", ".join(str(n) for n in nos[:3]),
                                nos[-1], len(nos))


def scan_drift(pages):
    """Alla boknivåsignaler om typdrift, i en lista."""
    return drift_ceased_types(pages) + drift_furniture_retyped(pages)


def book_pages(workdir):
    """[(sidnummer, elementlista)] från bästa tillgängliga version per sida."""
    from .merge import best_page_file
    m = Manifest.load(workdir)
    out = []
    for no in m.page_numbers():
        path, _ = best_page_file(workdir, no)
        if path is None:
            continue
        out.append((no, read_json(path).get("elements", [])))
    return out
