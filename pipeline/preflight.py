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
  8. `plusminus-varde` — `±` framför en NOLLSKILD siffra. Notationen har `+N`,
     `-N` och `±0`; `±2` finns inte och är alltid en felläsning.
  9. `punktledare` — fyra eller fler punkter i följd. En tryckt ledarlinje som
     transkriberats som tecken, vilket betyder att ett rutnät blivit löptext.
 10. `kolumnkollaps` — ett `table` vars rutnät är en kolumn brett.

Reglerna 8–10 läser även TABELLCELLERNA (`data.headers`/`data.rows`), inte bara
`el["text"]`. Att de äldre reglerna bara såg elementets egen text var skälet
till att `Dvärg PSY ±2` i rastabellen (s. 11) överlevde tre agentvarv med
confidence 1,0: felet satt i en cell, och ingen regel tittade dit. Det hittades
först när boken jämfördes mot en oberoende rippning.

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
# ±0-garblet har en spegelbild som kostade en riktig felläsning: `±` framför en
# NOLLSKILD siffra. Boken sätter modifikationer som `+2`, `-2` eller `±0` — ett
# `±2` finns inte i notationen och kan bara vara ett felläst `+2` (eller `-2`).
# Uppmätt: `Dvärg PSY ±2` i rastabellen s. 11, funnen först när en oberoende
# rippning jämfördes mot vår. Elementet låg på confidence 1.0 och ingen regel
# tittade in i tabellcellerna, så ingenting flaggade den.
PLUSMINUS_SIGNED = re.compile(r"^±([1-9]\d*)$")
# Punktledare som ätit radstrukturen: `1....... DYRKEN GÅR SÖNDER`. Tre punkter
# kan vara ett tryckt uteslutningstecken; fyra eller fler är en ledarlinje, och
# en ledarlinje betyder att ett rutnät har blivit löptext (s. 53).
DOT_LEADER = re.compile(r"\.{4,}")
# Kolumnkollaps: ett `table` vars rutnät är EN kolumn brett. Värdena finns kvar
# men kolumntillhörigheten är borta — läsexporten skriver då en rad per cell.
COLLAPSE_MIN_ROWS = 3

STRAIGHT_QUOTES = {"'": "’", '"': "”"}

# Kolumnsammanslagning: hur mycket bredare än sidans spaltbredd ett element
# måste vara, minsta antal element för att bredden alls ska kunna uppskattas,
# och minsta textlängd (en sammanslagen rad är två hela rader; en centrerad
# kapitälrubrik är bred men kort). Uppmätt på DoD-grundreglerna: spaltrader
# ~0,43, sammanslagna ~0,89.
MERGE_FACTOR = 1.4
MIN_COLUMN_ELEMENTS = 5
MIN_MERGE_TEXT = 40
# Textlängden får inte ensam avgöra. Ett KORT element kan också bära en
# sammanslagen rad: s. 6 hade `page_artifact` `MAGI` (4 tecken) på bredden
# 0,655 = 1,56× spaltbredden, och längdfiltret dolde det — felet hittades
# först för hand. Men att bara ta bort filtret ger 30 falska larm i den boken,
# eftersom sidhuvudselementet normalt bär hela linjebandet. Skillnaden är
# mätbar utan bild: ett sidhuvud spänner HELA satsytan (~2× spaltbredden plus
# rännan), medan en sammanslagning av två spaltrader börjar i vänsterspalten
# och slutar inne i högerspalten — bredare än en spalt, smalare än satsytan.
MERGE_SHORT_LO = 1.3
MERGE_SHORT_HI = 1.9

# Bbox-felkoppling: hur stor andel av sidans renderande element som måste ha
# uppmätt box för att en bbox-lös RUBRIK alls ska betyda felkoppling. Under
# gränsen har uppmätningen fallit på hela sidan (Regel 9) och rubriken saknar
# box av samma skäl som allt annat.
MIN_MEASURED_SHARE = 0.5

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
# Den ANDRA varianten: båda radernas text hamnade i elementet. Då saknas ingen
# boktext — det är strukturen som gått förlorad — men bredden per tecken
# halveras och faller under bandet ovan, så regeln var blind för den. S. 5
# p005_e53 passerade höjdtestet med 2,65× medianradhöjden men gav noll
# kandidater på glyfkvoten 0,49×. Kvoten ligger då kring 1/n, där n är antalet
# rader bandet spänner över. n skattas ur radAVSTÅNDET, inte ur ink-höjden:
# höjdfaktorn 2,65 för ett tvåradsband skulle ge n=3.
ROW_MERGE_JOINED_LO = 0.8
ROW_MERGE_JOINED_HI = 1.25
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
         "plusminus", "plusminus-varde", "punktledare", "kolumnkollaps",
         "kolumnsammanslagning", "lasordning", "radsammanslagning",
         "tabellkandidat", "tabellrad-i-element", "bbox-felkoppling",
         "tabell-svalt-titelband", "forskjuten-kedja", "tomt-radband",
         "bandbredd")

# En cell i en tryckt tabellrad som ligger radbruten i ett textlagerblock.
# Taket är rundligare än TABLE_CELL_MAX_TEXT (som gäller ett HELT element) men
# håller löptext utanför: uppmätt på MUT-AVE-terminal-state är den längsta
# äkta cellen 21 tecken (`Reflecrustning (20/1)`) medan bokens kortaste
# brödtextrad är 34.
EMBEDDED_CELL_MAX_TEXT = 28
# Två rader räcker — en vapentabell är ofta bara rubrikrad plus ett vapen.
EMBEDDED_TABLE_MIN_ROWS = 2


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


def _is_embedded(el):
    """Kommer elementets geometri ur PDF:ens textlager i stället för mätningen?

    Skillnaden är inte en detalj i proveniensen utan avgör vilka regler som får
    tala. Två av dem vilar helt på transkriptionskontraktets *ett element = en
    tryckt rad*:

    - `forskjuten-kedja` letar efter ett element som bär FEL uppmätt band. Den
      felformen förutsätter en kedja: `radboxar` mäter banden i ett eget steg
      och `jobs.py` parar dem mot elementen på index, så kedjan KAN glida. På
      `method: "embedded"` hämtas text och bbox atomärt ur samma PDF-block —
      det finns ingen kedja att förskjuta.
    - `radsammanslagning` larmar på att elementet spänner över två tryckta
      rader och återger bara den ena, alltså att boktext SAKNAS. Ett
      textlagerblock är ett helt stycke och bär alla sina rader med `\\n`
      emellan; ingenting saknas.

    Mätt på MUT-AVE-terminal-state (korpusens enda digitala utgåva): reglerna
    gav 179 + 45 kandidater där noll är fel. De döljer det som ÄR fel —
    samma bok bär tio `tabellkandidat`, den oåterkalleliga klassen.
    """
    return (el.get("source") or {}).get("method") == "embedded"


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


def _cells(el):
    """Alla celltexter i ett `table`-element som (etikett, text).

    Etiketten pekar ut cellen för en läsare: `rad 3 ’Dvärg’, kolumn ’PSY’`.
    Utan den blir en flagga på ett tabellelement en jakt genom rutnätet.
    """
    data = el.get("data")
    if not isinstance(data, dict):
        return []
    headers = [str(h) for h in (data.get("headers") or [])]
    ut = []
    for i, header in enumerate(headers):
        ut.append(("kolumnrubrik %d" % (i + 1), header))
    for r, row in enumerate(data.get("rows") or []):
        if not isinstance(row, (list, tuple)):
            continue
        etikett = str(row[0]) if row else ""
        for c, value in enumerate(row):
            kolumn = headers[c] if c < len(headers) else "kolumn %d" % (c + 1)
            ut.append(("rad %d ’%s’, kolumn ’%s’" % (r + 1, etikett, kolumn),
                       str(value)))
    return ut


def _statblock_fields(el):
    """Alla fältvärden i ett `statblock`-element som (etikett, text).

    Ett statblock är strukturerat som ett rutnät men lagras inte som ett:
    värdena ligger i `data.stats`, `data.skills` och `data.other`, inte i
    `data.rows`. `_cells` ser dem därför inte, och reglerna såg bara
    `el["text"]` — som för ett statblock är tom.

    Det är exakt den felform CLAUDE.md redan beskriver ett steg ovanför:
    `Dvärg PSY ±2` överlevde tre agentvarv i del I därför att felet satt i
    `data.rows` och ingen regel såg dit. Reglerna lärde sig läsa tabellceller,
    men statblocken förblev en blind fläck — och det är där spelvärdena bor.
    """
    data = el.get("data")
    if not isinstance(data, dict) or data.get("rows") is not None:
        return []
    namn = str(data.get("name") or "").strip() or el.get("id") or "statblock"
    ut = []
    for grupp in ("stats", "skills", "other"):
        falt = data.get(grupp)
        if not isinstance(falt, dict):
            continue
        for nyckel, varde in falt.items():
            if isinstance(varde, (dict, list)):
                continue
            ut.append(("%s ’%s’, fältet ’%s’" % (namn, grupp, nyckel),
                       str(varde)))
    return ut


def _texts(el):
    """Elementets egen text plus dess tabellceller och statblockfält."""
    ut = [("elementets text", (el.get("text") or ""))]
    ut.extend(_cells(el))
    ut.extend(_statblock_fields(el))
    return [(etikett, text) for etikett, text in ut if text]


def rule_plusminus_signed(el):
    """`±2` -> `+2`: plusminus framför en nollskild siffra finns inte i satsen.

    Boken sätter modifikationer som `+N`, `-N` eller `±0`. `±N` är därför alltid
    en felläsning — men VILKEN är inte given: `±` är ett plus med en vågrät
    linje under, så bortfaller linjen står det `+2`, bortfaller plusets lodräta
    stapel står det `-2`. Förslaget är `+N` eftersom plustecknet är den
    gemensamma delen av glyfen, men tecknet MÅSTE läsas i PNG:n innan det
    appliceras — en teckenvändning i en grundegenskapstabell är ett spelvärde.

    Siffran rörs aldrig, bara tecknet — samma gräns som `±0`-regeln.
    """
    hits = []
    for etikett, text in _texts(el):
        m = PLUSMINUS_SIGNED.match(text.strip())
        if not m:
            continue
        siffra = m.group(1)
        skäl = (
            "Heuristik (plusminus-värde): `±%s` i %s. Trycket sätter "
            "modifikationer som `+%s`, `-%s` eller `±0` — `±` framför en "
            "nollskild siffra finns inte i notationen och är alltid en "
            "felläsning. LÄS TECKNET I PNG:N: `±` är ett plus med vågrät linje "
            "under, så både `+%s` (linjen är falsk) och `-%s` (plusets lodräta "
            "stapel är falsk) är möjliga läsningar. Siffran är oomstridd. "
            "Detta är ett spelvärde i en grundregelbok — teckenvändningen "
            "avgörs mot bilden, aldrig på sannolikhet."
            % (siffra, etikett, siffra, siffra, siffra, siffra))
        if etikett == "elementets text":
            hits.append(("korrektion", make_correction(
                el.get("text"), "+" + siffra, 0.5, skäl,
                "heuristik:plusminus-varde", applied=False, kind=KIND_OCR)))
        else:
            # En tabellcell har ingen egen korrektionspost att applicera på —
            # posten sitter på elementet och `original` skulle bli tvetydig.
            hits.append(("flagga", skäl))
    return hits


def flag_dot_leaders(el):
    """Punktledare i texten -> ett rutnät har blivit löptext.

    `1....... DYRKEN GÅR SÖNDER, men fastnar inte i låset. 2.....` (s. 53) är
    inte en mening: det är en fummeltabell vars ledarlinjer transkriberats som
    tecken och vars rader därmed flutit ihop. Ledarlinjen är typografi, inte
    boktext — men VAD den band ihop syns bara i bilden, så detta är en flagga
    och aldrig en korrektionspost.
    """
    for etikett, text in _texts(el):
        if DOT_LEADER.search(text):
            return ("Heuristik (punktledare): fyra eller fler punkter i följd i "
                    "%s. Det är en tryckt ledarlinje, inte ett uteslutnings"
                    "tecken — och en ledarlinje binder ihop en etikett med sitt "
                    "värde i ett rutnät. Elementet är alltså sannolikt en "
                    "tabellrad som transkriberats som löptext, med flera rader "
                    "hopflutna i samma element. Läs stycket i PNG:n och typa om "
                    "till `table` (eller `table_header`/`table_cell`) om det är "
                    "en tabell. Punkterna själva är typografi och ska inte stå "
                    "kvar i texten." % etikett)
    return None


def flag_column_collapse(el):
    """Ett `table` vars rutnät är en kolumn brett — kolumntillhörigheten borta.

    Ett `table` med en kolumn är alltid fel: är det verkligen en enda spalt
    hör innehållet hemma i en `list`, och är det en tabell har kolumnerna
    kollapsat. Läsexporten skriver då en rad per cell, vilket är exakt hur
    grundreglernas tabell över grundegenskapskrav såg ut i `bok.md` — värdena
    kvar, men utan att kolumnen (grundegenskapen) gick att utläsa.
    """
    if el.get("type") != "table":
        return None
    data = el.get("data")
    if not isinstance(data, dict):
        return None
    rows = [r for r in (data.get("rows") or []) if isinstance(r, (list, tuple))]
    if len(rows) < COLLAPSE_MIN_ROWS:
        return None
    bredd = max([len(data.get("headers") or [])] + [len(r) for r in rows])
    if bredd > 1:
        return None
    return ("Heuristik (kolumnkollaps): `table` med %d rader men bara %d "
            "kolumn. Ett enkolumnigt rutnät är alltid fel — antingen har "
            "kolumnerna kollapsat och varje cell blivit sin egen rad (då är "
            "rad- och kolumntillhörigheten borta och måste läsas tillbaka ur "
            "PNG:n), eller så är innehållet ingen tabell och ska typas `list`. "
            "Cellerna själva är oftast rätt lästa; det är strukturen som "
            "saknas, så detta är ett typningsfel och aldrig en korrektionspost."
            % (len(rows), bredd))


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
        if len(el.get("text") or "") < MIN_MERGE_TEXT and not (
                el.get("type") == "page_artifact"
                and colw * MERGE_SHORT_LO < box[2] < colw * MERGE_SHORT_HI):
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


def _row_pitch(boxes, med_h):
    """Sidans radAVSTÅND — avståndet mellan två rader, inte deras ink-höjd.

    Höjdfaktorn mot medianradhöjden duger för att LARMA men inte för att räkna
    rader: ett tvåradsband mäter 2,65× medianen, eftersom medianen är bara
    bläckets höjd medan bandet också rymmer radmellanrummet. Pitchen mäts som
    medianen av y-avstånden mellan lodrätt intilliggande rader inom samma
    region.
    """
    per_region = {}
    for el, box in boxes:
        per_region.setdefault(_region(el), []).append(box[1])
    deltas = []
    for ys in per_region.values():
        ys = sorted(set(ys), reverse=True)
        for hi, lo in zip(ys, ys[1:]):
            steg = hi - lo
            # Uteslut spaltbyten och luckor kring rubriker/bilder.
            if 0 < steg <= med_h * 4:
                deltas.append(steg)
    return _median(deltas) if deltas else None


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
             and not _is_embedded(el)
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
    pitch = _row_pitch(boxes, med_h)
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
        # Ett element som KONSUMERAR lika många uppmätta band som dess höjd
        # rymmer har inte svalt någon rad — bboxen är unionen av banden, och
        # höjdfaktorn är då en artefakt av unionen och inte ett band som täckt
        # två tryckta rader. Signalen är gratis, rent index-baserad och skiljer
        # arterna exakt. Mätt över DoD del III: av regelns 14 kandidater hade 12
        # två eller flera band i `source.rader` och var falska larm som fyra
        # advokater avvisade var för sig (s. 7, 8, 22, 23 ×3, 28 ×3, 32, 34, 39)
        # — bara s. 35 `p035_e32` och s. 44 `p044_e71` bar ETT band och var
        # äkta. Att i stället undanta `list_item` räcker inte: tre av de tolv är
        # `heading` och ett är `paragraph`. Se BQ-015.
        src = el.get("source") or {}
        rader = src.get("rader") or []
        # Räkna med FLOOR, inte round: en tvåradig RUBRIK är satt i större grad
        # än brödtexten, så dess höjd spänner 2,5–2,6 brödtextspitchar utan att
        # rymma en tredje rad. Med avrundning uppåt larmade s. 7, 34 och 39 —
        # alla tre tvåradiga rubriker med båda banden i `rader`.
        if pitch and len(rader) >= max(2, int(box[3] // pitch)):
            continue
        # En box som en agent MÄTT FRAM är inte mätningens utfall utan en redan
        # fälld dom, och regelns premiss ("mätningen slog ihop två rader")
        # gäller inte för den. s. 38 `Hela rustningar` bär halva ett band som
        # advokaten delade vågrätt med y/höjd ÄRVD från det odelade bandet
        # (beslut s. 6 b) — höjden är därför ramlinjens, inte en svald rads.
        # Villkoret prövar att boxen är AGENTSATT, inte att den är
        # `pipeline.rows`: en box helt utan `bbox_source` kommer från en äldre
        # mätning (del I har 3953 sådana) och är alltså mätningens utfall.
        if str(src.get("bbox_source") or "").startswith("agent:"):
            continue
        # Ett element som också är för BRETT är en kolumnsammanslagning och
        # ägs av rule_column_merge — flagga inte samma element två gånger.
        if colw and box[2] > colw * MERGE_FACTOR:
            continue
        glyph = box[2] / len((el.get("text") or "").strip())
        kvot = glyph / med_glyph
        if not (ROW_MERGE_GLYPH_MIN <= kvot <= ROW_MERGE_GLYPH_MAX):
            # Andra varianten: ingen rad SAKNAS, men båda radernas text ligger
            # i samma element och radindelningen är därmed borta. Kvoten faller
            # då mot 1/n. Antalet rader räknas ur pitchen — höjdfaktorn skulle
            # ge n=3 för ett tvåradsband och därmed leta i fel band.
            n = round(box[3] / pitch) if pitch else 0
            # Bara `paragraph`. En rubrik, en punkt eller en rutrad som
            # radbryts är ETT typografiskt element och SKA bära båda radernas
            # text — s. 7:s tvåradsrubrik är sidans rätta form, inte ett fel.
            # Det är löptexten som har en rad per element, och det är där
            # förlorad radindelning gör skada i läsexporten.
            if (el.get("type") == "paragraph" and n >= 2
                    and (ROW_MERGE_JOINED_LO / n <= kvot
                         <= ROW_MERGE_JOINED_HI / n)):
                hits.append((el,
                             "Heuristik (radsammanslagning, hopslagen text): "
                             "bbox-höjden %.4f rymmer %d tryckta rader "
                             "(radavstånd %.4f) och glyfbredden är %.2f× "
                             "sidans median — nära 1/%d. Ingen boktext saknas: "
                             "BÅDA radernas text ligger i elementet, vilket är "
                             "varför bredden per tecken halverats. Det som gått "
                             "förlorat är radindelningen. Dela elementet i %d "
                             "och ge varje del sin uppmätta bbox — utelämnad "
                             "box spränger stycket i läsexporten."
                             % (box[3], n, pitch, kvot, n, n)))
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


def rule_bbox_miscoupling(elements):
    """En RUBRIK utan uppmätt bbox — mätningens rader har glidit ett steg.

    Mönstret har setts två gånger och båda gångerna hittades det för hand, inte
    av en regel: s. 6 mätte de två spaltrubrikerna som ETT band som draften gav
    åt sidhuvudet, så båda rubrikerna blev utan box; s. 9 lät rubriken stå utan
    box medan de två följande elementen bar rubrikens och varandras rader.

    Signalen är billig och kräver ingen bild: en rubrik är kraftigt svärtad och
    mäts praktiskt taget alltid. En bbox-lös rubrik är därför nästan aldrig den
    art av mätlucka som drabbar korta, glesa SLUTRADER (kön: BQ-002 a) — den är
    en felkoppling, och då bär något annat element rubrikens rad.

    Regeln larmar bara. Vilket element som ska ha vilken box går inte att
    avgöra ur JSON:en; det kräver att bandet läses i skanningen.

    Den kompletterande signal kön nämner — luckor i radindexföljden — är INTE
    implementerad: ett element utan `rader` ger konsekutiva grannindex både när
    kolonnen glidit och när raden aldrig mättes, så den skiljer inte
    felkoppling från äkta mätlucka och skulle larma på varje kort slutrad.
    """
    # På en sida där uppmätningen i praktiken FALLIT saknar nästan allt box, och
    # då säger en bbox-lös rubrik ingenting om felkoppling. Det är AGENTER.md
    # Regel 9 — en annan art med en annan orsak, och den ägs inte av den här
    # regeln. Uppmätt i denna bok: pärmsidan 0 % och s. 13 4 % mätta, mot
    # 95–99 % på sidorna där en ensam rubrik verkligen tappat sin box.
    renderade = [el for el in elements
                 if not el.get("removed")
                 and ((el.get("text") or "").strip() or el.get("data"))]
    if not renderade:
        return []
    matta = sum(1 for el in renderade if _bbox(el))
    if matta / len(renderade) < MIN_MEASURED_SHARE:
        return []

    hits = []
    for el in elements:
        # `table_caption` hör hit av samma skäl som `heading`: en tabelltitel är
        # lika kraftigt svärtad och mäts lika säkert. Utan den saknades
        # `p040_e25` och `p042_e03`, där tabellen svalt titelbandet och
        # bildtexten blev utan box — systerregeln `tabell-svalt-titelband` kan
        # inte se dem, eftersom en bildtext utan band inte gör anspråk på något.
        if el.get("type") not in ("heading", "table_caption") or el.get("removed"):
            continue
        if not (el.get("text") or "").strip():
            continue
        if _bbox(el):
            continue
        hits.append((el,
                     "Heuristik (bbox-felkoppling): rubriken/bildtexten saknar "
                     "source.bbox. Rubriker är kraftigt svärtade och mäts "
                     "nästan alltid, så detta är sannolikt inte en mätlucka "
                     "utan en felkoppling — något annat element på sidan bär "
                     "rubrikens radband. Läs bandet i skanningen och koppla om; "
                     "gissa inte koordinater."))
    return hits


# En `paragraph` vars bredd-per-tecken avviker mer än så här från sidans median
# bär antingen fel band eller en felmätt bandbredd. Uppmätt över DoD del III:
# tröskeln 2,0 ger sju kandidater på 31 sidor — en hanterlig lista där fem var
# äkta fel.
CHAR_WIDTH_FACTOR = 2.0
MIN_CHAR_WIDTH_ELEMENTS = 8


def rule_table_ate_caption(elements):
    """Ett `table` som gör anspråk på ett band en `table_caption` också vill ha.

    En tabells `rader` börjar på dess tryckta RUBRIKRAD och slutar på sista
    DATARAD; titelbandet hör till bildtexten och ramen är sättningsgrafik
    (beslut s. 12, 25, 26). Har tabellen svalt titelraden blir bildtexten utan
    box, eller — värre — pekar båda på samma band och kedjan under dem glider.

    Signalen är gratis och rent index-baserad, och den fyller luckan efter
    `rule_bbox_miscoupling`: på en RUTNÄTSSIDA har varje element en box, så den
    regeln tiger. s. 25 gav noll kandidater där fem elements radlistor var fel.

    Regeln larmar bara. Vilket element som ska ha bandet kräver att bandet läses
    i skanningen — precis som systerregeln. Den fångar INTE följdfelet där ett
    band glidit mellan två helt skilda element (s. 25 band 46,
    `SVÄRDSHAND`/`TABELL FÖR SOCIALT STÅND`). Se BQ-018.
    """
    # Bildtexten måste vara tabellens EGEN, alltså den närmast föregående i
    # arrayen. På en RUTNÄTSSIDA mäts ett FULLBRETT band per radhöjd tvärs hela
    # satsytan, så en tabell delar rutinmässigt band med grannrutans bildtext —
    # och det bandet ska stanna i BÅDA elementens `rader` (beslut s. 25 b).
    # Utan det villkoret ger regeln fem kandidater på s. 25 där två är äkta, och
    # fyra överlever advokatens rättning.
    egen = {}
    senaste = None
    for el in elements:
        if el.get("removed"):
            continue
        if el.get("type") == "table_caption":
            senaste = el
        elif el.get("type") == "table":
            egen[el["id"]] = senaste

    anspråk = {}
    for el in elements:
        if el.get("removed"):
            continue
        for band in (el.get("source") or {}).get("rader") or []:
            anspråk.setdefault(band, []).append(el)
    hits = []
    for el in elements:
        if el.get("type") != "table" or el.get("removed"):
            continue
        titel = egen.get(el["id"])
        if titel is None:
            continue
        # Har bildtextens box MÄTTS FRAM av en agent är delningen redan dömd:
        # på s. 24 står bildtexten på SAMMA tryckta rad som tabellens första
        # kolumnetikett, så bandet omsluter båda, och advokaten smalnade
        # bildtexten medan tabellens bbox med rätta stod kvar (beslut s. 24).
        # Att larma om samma band igen är brus.
        if str((titel.get("source") or {}).get("bbox_source")
               or "").startswith("agent:"):
            continue
        delade = sorted({b for b in (el.get("source") or {}).get("rader") or []
                         if any(o is titel for o in anspråk.get(b, []))})
        if not delade:
            continue
        titlar = [titel["id"]]
        hits.append((el,
                     "Heuristik (tabell-svalt-titelband): tabellens "
                     "source.rader innehåller band %s som ocksa gors anspråk "
                     "på av %s. En tabells rader ska börja på den tryckta "
                     "RUBRIKRADEN och sluta på sista DATARAD — titelbandet hör "
                     "till bildtexten och ramen är sättningsgrafik (beslut "
                     "s. 12, 25). Läs bandet i skanningen och koppla om; gissa "
                     "inte koordinater."
                     % (", ".join(str(b) for b in delade), ", ".join(titlar))))
    return hits


def rule_shifted_chain(elements):
    """En `paragraph` vars bredd per tecken avviker grovt från sidans median.

    `rule_bbox_miscoupling` larmar bara på en bbox-LÖS rubrik. På s. 32 hade
    ALLA element en box fast fyra av dem bar fel band — en falsk mätrad inne i
    illustrationen hade konsumerats och sköt kedjan ett steg. Det var bokens
    femte felkoppling och den första som ingen agent larmade på.

    Signalen är gratis och kräver ingen bild: bbox-BREDDEN delat på antalet
    tecken är nästan konstant inom en typ och en spalt, så ett `paragraph` som
    avviker mer än CHAR_WIDTH_FACTOR från sidans median bär antingen fel band
    eller en felmätt bandbredd (BQ-020). Regeln skiljer INTE de två arterna åt
    men fångar båda.

    Begränsad till `paragraph` med flit: kvoten är meningslös för `heading`
    (rubrikgrad), `page_artifact` (sidhuvud över hela satsytan), `table_caption`
    och flerradiga `list_item` (text som fortsätter på nästa rad).

    MOTMETOD att inte förväxla den med: att mäta bläcket INOM elementets lagrade
    band kan ALDRIG upptäcka en förskjuten kedja — kvoten blir 1,00 ändå
    (beslut s. 32). Det som gäller är att para spaltens bläckrader i ORDNING mot
    spaltens element i ordning. Se BQ-022.
    """
    kandidater = []
    for el in elements:
        if el.get("type") != "paragraph" or el.get("removed"):
            continue
        if _is_embedded(el):
            continue
        box = _bbox(el)
        text = (el.get("text") or "").strip()
        if not box or len(text) < 4:
            continue
        kandidater.append((el, box[2] / len(text)))
    if len(kandidater) < MIN_CHAR_WIDTH_ELEMENTS:
        return []
    median = _median([kvot for _, kvot in kandidater])
    if not median:
        return []
    hits = []
    for el, kvot in kandidater:
        faktor = max(kvot / median, median / kvot)
        if faktor < CHAR_WIDTH_FACTOR:
            continue
        hits.append((el,
                     "Heuristik (förskjuten kedja): bredd per tecken %.5f mot "
                     "sidans median %.5f för paragraph (faktor %.2f). "
                     "Elementet bär antingen FEL BAND — kedjan har glidit, och "
                     "då är grannarna också fel — eller ett band vars bredd är "
                     "felmätt. Para spaltens bläckrader i ORDNING mot spaltens "
                     "element i ordning; att mäta bläcket INOM elementets eget "
                     "band ger 1,00 även när kedjan är förskjuten."
                     % (kvot, median, faktor)))
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


def rule_embedded_table_rows(elements):
    """Tryckt tabellRAD som ligger som ETT element med cellerna radbrutna.

    `rule_table_candidate` letar efter många KORTA element vars vänsterkanter
    bildar x-kluster. Den signaturen uppstår när en transkription typar varje
    cell för sig. En DIGITAL utgåva ger den aldrig: PDF:ens textlager samlar
    hela den tryckta raden i ETT block och skiljer cellerna med radbrytning, så
    tabellen ser ut som en handfull vanliga `paragraph` och rutnätet finns
    ingenstans att mäta.

    Följden är densamma och lika oåterkallelig (CLAUDE.md §Tabeller): rad- och
    kolumnstrukturen är borta, `tables.assemble` har inget att montera, och
    läsexporten skriver cellerna som löptext. MUT-AVE-terminal-state bär 19
    vapentabeller (`Vapen\\nGCL\\nSkada` följt av `Laservärja\\n80 %\\n3T6+2`)
    och 57 statblockrader (`STY\\n10\\nINT\\n13\\nPER\\n8/15`) i den formen, och
    ingen regel såg en enda av dem.

    Signalen är rent index-baserad och kräver varken bild eller bbox: två eller
    flera element i FÖLJD som var för sig delas av radbrytning i lika många
    korta fält. Löptext slås ut av båda villkoren — ett styckes rader är olika
    många i varje block och långa var för sig.
    """
    hits = []
    kedja = []

    def _fält(el):
        if el.get("type") not in TABLE_SUSPECT_TYPES or el.get("removed"):
            return None
        if not _is_embedded(el):
            return None
        delar = [d.strip() for d in (el.get("text") or "").split("\n")]
        if len(delar) < TABLE_MIN_COLUMNS or not all(delar):
            return None
        if max(len(d) for d in delar) > EMBEDDED_CELL_MAX_TEXT:
            return None
        return delar

    def _stäng():
        if len(kedja) < EMBEDDED_TABLE_MIN_ROWS:
            return
        ids = [el["id"] for el, _ in kedja]
        kolumner = len(kedja[0][1])
        hits.append((kedja[0][0],
                     "Heuristik (tabellrad i element): %d element i följd bär "
                     "var sitt tryckta tabellRAD med %d celler åtskilda av "
                     "radbrytning — en tryckt tabell som typats `paragraph` i "
                     "stället för `table` med `data.headers`/`data.rows`. Så ser "
                     "en tabell ut när den kommer ur PDF:ens textlager: hela "
                     "raden i ett block, rutnätet ingenstans. Strukturen går "
                     "inte att återskapa nedströms. Deltagande element: %s. "
                     "Verifiera mot PNG:n — är det en tabell, typa om till "
                     "`table` (första raden är oftast rubrikraden); är det ett "
                     "statblock, typa om till `statblock` med "
                     "`data.stats`/`skills`/`other`. Detta är ett typningsfel "
                     "och ska aldrig bli en korrektionspost."
                     % (len(ids), kolumner, ", ".join(ids))))

    for el in elements:
        delar = _fält(el)
        if delar and kedja and len(delar) != len(kedja[0][1]):
            _stäng()
            kedja = []
        if delar:
            kedja.append((el, delar))
        else:
            _stäng()
            kedja = []
    _stäng()
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

def scan_page(data, image=None, bands=None, regions=None):
    """Kör alla regler på en validerad sid-JSON.

    `image` (gråskale-array av sidbilden) och `bands` (mätningens bboxar) är
    valfria. Utan dem hoppas de två PIXELBASERADE reglerna över — `tomt-radband`
    och `bandbredd` — medan de rent index-baserade körs som förut. Det gör
    `scan_page` anropbar utan bild i test och i äldre flöden.

    Returnerar (ny_data, summering). Indata muteras inte.
    """
    import copy
    out = copy.deepcopy(data)
    elements = out.get("elements", [])
    counts = {rule: 0 for rule in RULES}

    for el in elements:
        # Ett KONSUMERAT element (`removed: true`) har gått upp i ett annat och
        # renderas inte — men det behåller sin tryckta text, eftersom ingenting
        # kastas (beslut s. 26). Utan spärren läser per-elementreglerna om den
        # texten och ger kandidater som aldrig går att avfärda för gott: på
        # s. 11 gav `punktledare` sju träffar, varav två satt på de två element
        # som just hade konsumerats. De fjorton sidnivåreglerna hoppar redan
        # över dem. Se BQ-027.
        if el.get("removed"):
            continue
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
        # Reglerna nedan tittar också IN i tabellcellerna. Att de tidigare bara
        # läste `el["text"]` var skälet till att `Dvärg PSY ±2` överlevde tre
        # agentvarv: cellen låg i `data.rows` och ingen regel såg den.
        for slag, träff in rule_plusminus_signed(el):
            if slag == "korrektion":
                _add_candidate(el, träff)
            else:
                _add_flag(el, träff)
            counts["plusminus-varde"] += 1
        for regel, fn in (("punktledare", flag_dot_leaders),
                          ("kolumnkollaps", flag_column_collapse)):
            flag = fn(el)
            if flag:
                _add_flag(el, flag)
                counts[regel] += 1

    sidtyp = classify_page(elements)
    sidnivå = [("radsammanslagning", rule_row_merge),
               ("tabellkandidat", rule_table_candidate),
               ("tabellrad-i-element", rule_embedded_table_rows),
               ("bbox-felkoppling", rule_bbox_miscoupling),
               ("tabell-svalt-titelband", rule_table_ate_caption),
               ("forskjuten-kedja", rule_shifted_chain)]
    if image is not None and bands:
        sidnivå += [("tomt-radband",
                     lambda els: rule_empty_band(els, image, bands)),
                    ("bandbredd",
                     lambda els: scan_band_widths(els, image, bands,
                                                  regions)[0])]
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

    if image is not None and bands:
        obundna = scan_band_widths(elements, image, bands, regions)[1]
        if obundna:
            # Ett för brett band som INGET element bär kan inte flaggas på ett
            # element — men det får inte tappas heller, för nästa bindning kan
            # råka fastna i det.
            out["bandbredd_obundna"] = obundna
            counts["bandbredd"] += len(obundna)

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
        matfil = Path(str(page_file(workdir, no, "radboxar.json")))
        matning = (read_json(matfil) or {}) if matfil.is_file() else {}
        bands = [r.get("bbox") for r in (matning.get("rows") or [])]
        regioner = [r.get("region") for r in (matning.get("rows") or [])]
        out, counts = scan_page(data, _page_gray(workdir, no),
                                bands if all(bands) else None, regioner)
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


def drift_split_tables(pages):
    """Tabeller som bryts över en SIDBRYTNING utan att vara märkta som det.

    En tryckt tabell som fortsätter på nästa sida är EN tabell, och
    fortsättningen ska bära `data.fortsattning_av` som pekar på huvudelementet
    (BQ-010). Är märkningen borta faller tabellen ut som två csv-filer som ser
    ut att vara skilda tabeller, och läsaren av `export/tabeller/` kan inte veta
    att de hör ihop.

    Signalen är gratis och rent strukturell: FÖREGÅENDE sidas sista renderande
    element är ett `table`, och den nya sidans FÖRSTA är ett `table` vars
    `headers` är tomma eller saknas — en tabell som börjar om trycker sin
    rubrikrad.

    Den nyckelform posten föreslog (`^\s*[<>]?\d+\+?\s*\.{2,}`) är prövad och
    förkastad: den kräver en nyckelkolumn med utfyllnadspunkter och ger NOLL på
    s. 45→46, som är bokens tredje sidbrutna fall och en ren namnlista. Den
    strukturella signalen fångar alla tre.

    Kan bara ses på boknivå — sidloopen har ingen granne. Se BQ-011.
    """
    def renderande(elements):
        return [el for el in elements if not el.get("removed")
                and el.get("type") not in ("page_artifact",)
                and ((el.get("text") or "").strip() or el.get("data"))]

    def rubrikslos(el):
        if el.get("type") != "table" or el.get("removed"):
            return False
        data = el.get("data") or {}
        if data.get("fortsattning_av") or not data.get("rows"):
            return False
        headers = data.get("headers")
        return not (headers and any(str(h).strip() for h in headers))

    def nyckel(rad):
        m = re.match(r"^\s*(\d+)\s*$", str(rad[0]) if rad else "")
        return int(m.group(1)) if m else None

    hits = []
    for (fno, fel), (nno, nel) in zip(pages, pages[1:]):
        fore, nasta = renderande(fel), renderande(nel)
        if not fore or not nasta:
            continue
        # (1) STRUKTURELLT: sidan slutar med en tabell och nästa INLEDS med en
        #     rubrikslös. Ger noll falska larm i hela boken.
        if fore[-1].get("type") == "table" and rubrikslos(nasta[0]):
            hits.append(
                "sidbruten tabell: s. %d slutar med `table` %s och s. %d inleds "
                "med `table` %s utan egen rubrikrad, men `data.fortsattning_av` "
                "saknas. Är det samma tryckta tabell ska fortsättningen peka på "
                "HUVUDELEMENTET (BQ-010); annars ska den ha sin egen rubrikrad."
                % (fno, fore[-1].get("id"), nno, nasta[0].get("id")))
            continue
        # (2) NYCKELFÖLJDEN: den strukturella signalen missar en fortsättning
        #     som inte står FÖRST på sin sida — s. 11 inleds med löptexten som
        #     fortsätter från s. 10, och Skräcktabellens fortsättning kommer
        #     först därefter. Fortsätter nyckelkolumnen på nästa heltal är det
        #     samma tabell, och det provet är i praktiken utan falska larm: de
        #     rubrikslösa etikett/värde-tabellerna (s. 9, 10, 25, 38) har namn i
        #     nyckelkolumnen, inte tal i följd.
        for tabell in fore:
            if tabell.get("type") != "table":
                continue
            rader = (tabell.get("data") or {}).get("rows") or []
            sist = nyckel(rader[-1]) if rader else None
            if sist is None:
                continue
            for kandidat in nasta:
                if not rubrikslos(kandidat):
                    continue
                forst = nyckel(((kandidat.get("data") or {})
                                .get("rows") or [None])[0])
                if forst == sist + 1:
                    hits.append(
                        "sidbruten tabell: s. %d `table` %s slutar på nyckeln "
                        "%d och s. %d `table` %s börjar på %d utan egen "
                        "rubrikrad — nyckelkolumnen fortsätter över "
                        "sidbrytningen, men `data.fortsattning_av` saknas "
                        "(BQ-010)."
                        % (fno, tabell.get("id"), sist, nno,
                           kandidat.get("id"), forst))
    return hits


# Svärtningströskeln är en PARAMETER, inte 150. På rutnätssidorna ligger det
# grå zebrarastret på ~200 och en profil vid 150 fångar rastrets punkter: en
# fullbreddsprofil av del III s. 26 gav då SEX band för hela sidan. Tröskel 100
# skiljer text från raster rent; s. 36 krävde 80, eftersom rastret där är en
# halvtonspunktskärm och inte en jämn ton.
BAND_DARK = 100
# Ett band som ett TEXTbärande element gör anspråk på men som har färre än så
# här mörka pixlar är en ramlinje eller en rasterkant, inte en textrad.
EMPTY_BAND_PIXELS = 8
# Ett band vars bredd är mer än så här gånger bläckets egen utbredning är
# felmätt i x-led (BQ-020).
BAND_WIDTH_FACTOR = 2.0


def _page_gray(workdir, page_no):
    """Sidbilden som gråskale-array, eller None om den inte går att läsa."""
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        return None
    png = Path(str(page_file(workdir, page_no, "png")))
    if not png.is_file():
        return None
    try:
        return np.asarray(Image.open(png).convert("L"))
    except Exception:
        return None


def _band_window(image, box):
    """Bildutsnittet för ett band. y räknas från sidans NEDERKANT."""
    h, w = image.shape
    x, y, bredd, hojd = box
    top = max(0, int(round((1 - (y + hojd)) * h)))
    bot = min(h, int(round((1 - y) * h)) + 1)
    lo = max(0, int(round(x * w)))
    hi = min(w, int(round((x + bredd) * w)) + 1)
    if bot <= top or hi <= lo:
        return None
    return image[top:bot, lo:hi]


def rule_empty_band(elements, image, bands):
    """Ett TEXTbärande element som gör anspråk på ett band UTAN bläck.

    Signalen är gratis, deterministisk och rent pixelbaserad: bär bandet noll
    text är det en ramlinje eller en rasterkant, och då har kopplingen glidit.
    På del III s. 26 gällde det fem band (49, 50, 51, 77, 78) som sköt sex
    element ur läge, medan `bbox-felkoppling` teg (varje element HADE en box)
    och `tabell-svalt-titelband` teg (ingen bildtext gjorde anspråk på samma
    band).

    Regeln larmar bara. Vilket element som ska ha bandet kräver att banden mäts
    om per ruta — det kan ingen indexsignal avgöra. Se BQ-019.
    """
    if image is None or not bands:
        return []
    hits = []
    for el in elements:
        # "TEXTbärande" måste rymma `table` och `list` också: deras innehåll
        # ligger i `data`, inte i `text`. Utan det missades s. 26 `p026_e10`,
        # tabellen som svalt de tre ramlinjebanden — alltså precis det fall
        # regeln skrevs för.
        if el.get("removed"):
            continue
        if not ((el.get("text") or "").strip() or el.get("data")):
            continue
        tomma = []
        for i in (el.get("source") or {}).get("rader") or []:
            if not (0 <= i < len(bands)):
                continue
            ruta = _band_window(image, bands[i])
            if ruta is None:
                continue
            # Tomheten måste hålla vid BÅDA trösklarna. En liten, svagt tryckt
            # glyf — folion på en avdelarsida — ger bara 5 pixlar under 100 men
            # 80 under 150, och är alltså text. En ramlinje som ligger mellan
            # två mätta rader ger noll vid båda (s. 26 banden 49, 50, 51, 77, 78).
            if (int((ruta < BAND_DARK).sum()) < EMPTY_BAND_PIXELS
                    and int((ruta < 150).sum()) < EMPTY_BAND_PIXELS):
                tomma.append(i)
        if not tomma:
            continue
        hits.append((el,
                     "Heuristik (tomt-radband): elementet gör anspråk på band "
                     "%s som har färre än %d pixlar under svärtningströskeln "
                     "%d — det är en RAMLINJE eller en rasterkant, inte en "
                     "textrad, och ramen ingår aldrig i ett elements rader "
                     "(beslut s. 12, 26). Kopplingen har alltså glidit. Mät "
                     "banden om per ruta i eget x-fönster och koppla om; gissa "
                     "inte koordinater."
                     % (", ".join(str(i) for i in tomma), EMPTY_BAND_PIXELS,
                        BAND_DARK)))
    return hits


COLUMN_REGIONS = ("vänsterkolumn", "högerkolumn", "mittkolumn")


def scan_band_widths(elements, image, bands, regions=None):
    """Band vars BREDD är mycket större än bläckets egen utbredning.

    Arten är varken BQ-002:s mätlucka (bandet finns och sitter rätt) eller en
    felkoppling (elementet har rätt band) — det är en felmätt x-utbredning, och
    den syns bara om någon läser bläcket. Mätt på del III s. 29: band 5 bär
    `Sx1 SR` med rätt y men bredden 0,3519, sju gånger radens faktiska bläck.

    Varför den ska larma trots att effekten där blev noll:
    `pipeline/export.py::_starts_paragraph` jämför bandbredden med spaltbredden
    för att avgöra om raden FYLLDE spalten, och 0,3519 låg på 89 % av den
    gränsen — ytterligare någon hundradel och ASTRALVAPEN-stycket hade fogats
    in i statblockets sista rad i `bok.md`.

    Signalen läser MÄTNINGENS band, inte elementens bbox. Det är nödvändigt:
    på s. 29 hade elementet ingen box alls i draften, så en elementbaserad
    regel såg ingenting. Returnerar (element-träffar, obundna band) — ett band
    som inget element bär kan inte flaggas på ett element, men det får inte
    tappas heller. Se BQ-020.
    """
    if image is None or not bands:
        return [], []
    _, w = image.shape
    # Bara SPALTBAND prövas. På en rutnätssida mäts ett FULLBRETT band per
    # radhöjd tvärs hela satsytan (beslut s. 25) — där ÄR bandet mycket bredare
    # än bläcket i den enskilda rutan, och det är mätningens avsedda form, inte
    # ett fel. Utan den avgränsningen ger regeln 47 träffar över boken, varav
    # de flesta ligger på s. 24–27 och 45; med den återstår de fall där en
    # spaltrad fått en bredd som inte är radens.
    barare = {}
    for el in elements:
        if el.get("removed"):
            continue
        for i in (el.get("source") or {}).get("rader") or []:
            barare.setdefault(i, el)

    hits, obundna = [], []
    for i, box in enumerate(bands):
        if not box:
            continue
        if regions and regions[i] not in COLUMN_REGIONS:
            continue
        ruta = _band_window(image, box)
        if ruta is None or ruta.shape[1] < 4:
            continue
        kolumner = (ruta < BAND_DARK).any(axis=0)
        if not kolumner.any():
            continue  # tomt band — det ägs av `tomt-radband`
        forsta = int(kolumner.argmax())
        sista = len(kolumner) - 1 - int(kolumner[::-1].argmax())
        black = (sista - forsta + 1) / float(w)
        if black <= 0 or box[2] / black < BAND_WIDTH_FACTOR:
            continue
        text = ("bandets bredd %.4f är %.1f× bläckets egen utbredning %.4f "
                "inom samma band. Bandet sitter rätt i y — det är "
                "x-utbredningen som är felmätt. `_starts_paragraph` läser "
                "bandbredden som »fyllde raden spalten«, så en felmätt bredd "
                "kan foga ihop två stycken som ska stå isär."
                % (box[2], box[2] / black, black))
        el = barare.get(i)
        # Bara `paragraph`. En TABELL har legitim vitrymd inne i raden — en
        # nyckelkolumn till vänster och text till höger ger ett bläckspann som
        # inte fyller bandet — och en `table_caption` är centrerad. Premissen
        # "bandet ska vara radens egen bredd" håller bara för löptext. Utan den
        # avgränsningen ger regeln 20 träffar över boken i stället för fyra.
        if el is not None and el.get("type") != "paragraph":
            continue
        # En box som en agent MÄTT FRAM är en redan fälld dom: advokaten har
        # ersatt det felmätta bandet med bläckets egen utbredning, och att
        # larma om samma band igen är brus. Samma spärr som i `rule_row_merge`.
        if el is not None and str((el.get("source") or {}).get("bbox_source")
                                  or "").startswith("agent:"):
            continue
        if el is None:
            obundna.append("band %d: %s" % (i, text))
        else:
            hits.append((el, "Heuristik (bandbredd): band %d — %s" % (i, text)))
    return hits, obundna


def scan_drift(pages):
    """Alla boknivåsignaler om typdrift, i en lista."""
    return (drift_ceased_types(pages) + drift_furniture_retyped(pages)
            + drift_split_tables(pages))


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
