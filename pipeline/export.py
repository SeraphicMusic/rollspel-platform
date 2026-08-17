"""Export från kanonisk bok-JSON till Markdown, CSV och DOCX.

All export genereras från export/bok.json (kör `sammanfoga` först).
DOCX återanvänder befintliga .claude/skills/extrahera/create-docx.js.
"""
import csv
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from . import provenance, tables
from .log import setup_logging
from .manifest import export_dir, read_json

DOCX_SCRIPT = Path(__file__).resolve().parent.parent / \
    ".claude" / "skills" / "extrahera" / "create-docx.js"


def _load_book(workdir):
    path = export_dir(workdir) / "bok.json"
    if not path.is_file():
        raise SystemExit("export/bok.json saknas — kör `sammanfoga` först")
    return read_json(path)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

# Transkriberingsmetadata som beskriver hur källans attacktabell såg ut. Den
# renderade vapentabellen ersätter den — nyckeln ska inte ut i läsexporten.
_INTERNAL_KEYS = {"attacktabell_rubrik"}

# Transkriptionen använder en finare elementvokabulär än exportörens grundfall.
# Typer som inte står här renderades tidigare som vanliga stycken av en tyst
# catch-all — därför föll t.ex. grundregelbokens tabellceller ut som en rad per
# cell utan att någon varnades. Okända typer skrivs fortfarande ut (innehåll får
# aldrig tappas) men loggas nu så att luckan syns.
_CAPTION_TYPES = ("illustration", "table_caption", "table_note")
_BULLET_TYPES = ("list_item", "requirement")
# Punkttecken som trycket sätter i början av en listpunkt. De står kvar i
# elementets `text` — den är print-trogen — men renderas inte, eftersom
# markdownens egen `- ` betyder exakt samma sak. Utan det här visar bok.md två
# punkttecken (`- • Köpa ras`) där boken har ett.
_BULLET_GLYPHS = "•·●▪‣"
_HANDLED_TYPES = frozenset(
    ("heading", "paragraph", "toc_entry", "index_entry", "boxed_text",
     "list", "table", "statblock", "page_artifact",
     "table_cell", "table_header") + _CAPTION_TYPES + _BULLET_TYPES)


# Element vars innehåll ligger i `data`, med nyckeln som bär det. Hamnar
# nyttolasten på elementets toppnivå i stället — `el["rows"]` i stället för
# `el["data"]["rows"]` — renderar exportören ingenting alls, och eftersom
# elementet varken har `text` eller okänd typ säger ingen varning ifrån.
# Del I s. 56 föll ur `bok.md` precis så: sju tabellrader borta, och bara en
# ordmängdsdiff mot en tidigare export avslöjade det.
_PAYLOAD_KEYS = {"table": ("rows",), "list": ("items",),
                 "statblock": ("stats", "skills", "weapons", "other")}


def warn_empty_payloads(book, log):
    """Strukturelement som inte renderar något — innehållet är tappat."""
    lost = []
    for page in book["pages"]:
        for el in page["elements"]:
            keys = _PAYLOAD_KEYS.get(el.get("type"))
            if not keys or el.get("removed"):
                continue
            data = el.get("data") or {}
            if any(data.get(k) for k in keys):
                continue
            misplaced = [k for k in keys if el.get(k)]
            lost.append((page["page"], el.get("id"), el.get("type"),
                         misplaced))
    for page, eid, etype, misplaced in lost:
        log.warning(
            "%s %s (sida %d) renderar INGENTING: %s. Innehållet hamnar inte i "
            "bok.md — lägg nyttolasten under `data`.", etype, eid, page,
            ("nyttolasten ligger på elementets toppnivå (%s) i stället för "
             "under `data`" % ", ".join(misplaced)) if misplaced
            else "`data` saknar innehåll")
    return lost


def _warn_unknown_types(book, log):
    """Logga elementtyper exportören inte har någon egen rendering för."""
    unknown = {}
    for page in book["pages"]:
        for el in page["elements"]:
            etype = el.get("type")
            if etype in _HANDLED_TYPES or el.get("removed"):
                continue
            if (el.get("text") or "").strip():
                unknown.setdefault(etype, []).append(page["page"])
    for etype, pages in sorted(unknown.items()):
        log.warning(
            "okänd elementtyp %r på %d element (sidor %s) — renderas som "
            "stycke; lägg till en gren i export.py om den behöver egen form",
            etype, len(pages), ", ".join(str(p) for p in sorted(set(pages))))
    return unknown


def _field_value(value):
    """Läsbar text för ett statblockfält som inte är en enkel sträng.

    `extraStats` bär ibland en hel kolumn ur rutan — spöket på s. 47 har
    multiplikatorerna `{"STY": "0", "STO": "x1", …}` som härleder attributen ur
    offrets egna värden. Utan detta föll de ut som en rå Python-dict i
    `bok.md` (`- **Multipel:** {'STY': '0', …}`).
    """
    if isinstance(value, dict):
        return ", ".join("%s %s" % (k, v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return value


def _samma_namn(a, b):
    """Samma namn bortsett från skiftläge och skiljetecken?

    Skiftläget MÅSTE bortses från: rubriken bär tryckets versaler
    (`JIM BRONCO`) medan `data.name` bär korpusens kapitälform (`Jim Bronco`),
    och det är två skrivningar av ett namn, inte två namn.
    """
    if not a or not b:
        return False
    rensa = str.maketrans("", "", " .,:;!?—–-")
    return a.casefold().translate(rensa) == b.casefold().translate(rensa)


def _statblock_md(el, foregaende_rubrik=None):
    """Statblocket som markdown.

    `foregaende_rubrik` är texten i elementet närmast före, när det är en
    `heading`. Bär den samma namn som statblocket skrivs namnet INTE en gång
    till: trycket sätter NPC-namnet en gång, i rutans displaygrad, och en
    transkription som både typar det som `heading` (tryckets form) och lagrar
    det i `data.name` (statblockets metadata) fick läsexporten att skriva

        #### JIM BRONCO
        **Jim Bronco**

    Dubbleringen hittades av ordgrinden på MUT-AVE-terminal-state — nitton
    statblock, nitton namn för mycket. Referensboken `MUT-AVE-harda-bud` har
    ingen egen rubrik och märkte det aldrig.
    """
    data = el.get("data") or {}
    lines = []
    name = data.get("name") or el.get("text") or "Statblock"
    if not _samma_namn(name, foregaende_rubrik):
        lines.append("**%s**" % name)
        lines.append("")
    stats = data.get("stats") or {}
    if stats:
        lines.append("| " + " | ".join(stats.keys()) + " |")
        lines.append("|" + "---|" * len(stats))
        lines.append("| " + " | ".join(str(v) for v in stats.values()) + " |")
        lines.append("")
    for section in ("extraStats", "other"):
        for k, v in (data.get(section) or {}).items():
            if k in _INTERNAL_KEYS:
                continue
            lines.append("- **%s:** %s" % (k, _field_value(v)))
    skills = data.get("skills") or {}
    if data.get("skills_text"):
        # Rutans färdighetsrad ORDAGRANT, när transkriptionen sparat den.
        #
        # Uppdelningen i `data.skills` är en dict, och en dict kan inte bära
        # skiljetecknen MELLAN sina poster. Sammanfogningen skrev därför alltid
        # `, `, och på MUT-AVE-terminal-state s. 19 sätter trycket en PUNKT
        # efter `Markfordon 80%` — läsexporten emenderade alltså ett
        # skiljetecken som Regel 8a förbjuder att emendera, och avvikelsen
        # kunde bara redovisas, inte undvikas (BQ-009). Bokens övriga arton
        # rutor har komma överallt och rörs inte av det här.
        lines.append("- **%s:** %s" % (data.get("skills_label") or "Färdigheter",
                                       data["skills_text"]))
    elif skills:
        lines.append("- **Färdigheter:** " + ", ".join(
            "%s %s" % (k, v) for k, v in skills.items()))
    lines.extend(_weapons_md(data.get("weapons"), data.get("weapons_label")))
    lines.append("")
    return lines


# Kolumner i den ordning en spelare läser dem; nycklar som inte står här är
# katalogmetadata (pris, vikt, vapengrupp) och hör inte hemma i statblocket.
# `gc` (Grundchans) står FÖRE skadan — så sätter DoD-bestiariet sitt
# vapenhuvud (`Naturliga vapen  GC  Skada`, Krugal s. 16, BQ-010).
_WEAPON_COLUMNS = (("attack", "Attack"), ("gc", "GC"), ("damage", "Skada"),
                   ("bv", "BV"), ("range", "Räckvidd"),
                   ("rackvidd", "Räckvidd"), ("styKrav", "STY-krav"))


def _weapons_md(weapons, label=None):
    """Vapenrader — utan den här förlorade md-exporten hela vapenblocket.

    `label` är tryckets eget kolumnhuvud för namnkolumnen när det avviker
    från det generiska (`Naturliga vapen` i bestiariet, BQ-010) — det bärs i
    `data.weapons_label` och faller tillbaka på `Vapen`.
    """
    if not weapons:
        return []
    rows = [w if isinstance(w, dict) else {"name": str(w)} for w in weapons]
    columns = [(key, label_) for key, label_ in _WEAPON_COLUMNS
               if any(row.get(key) not in (None, "") for row in rows)]
    esc = lambda cell: str(cell).replace("|", "\\|")
    lines = ["", "| %s | " % esc(label or "Vapen")
             + " | ".join(label_ for _, label_ in columns) +
             " |", "|---|" + "---|" * len(columns)]
    for row in rows:
        cells = [esc(row.get(key, "—") if row.get(key) not in (None, "")
                     else "—") for key, _ in columns]
        lines.append("| %s | %s |" % (esc(row.get("name", "?")),
                                      " | ".join(cells)))
    return lines


def _table_md(el):
    data = el.get("data") or {}
    headers = data.get("headers") or []
    rows = data.get("rows") or []
    if not rows:
        return []
    esc = lambda cell: str(cell).replace("|", "\\|")
    lines = []
    caption = (el.get("text") or "").strip()
    if caption:
        lines += ["**%s**" % esc(caption), ""]
    # En spännrubrik står över flera kolumner i trycket och kan inte uttryckas
    # i en markdown-tabell. Utan raden nedan faller den tryckta texten helt ur
    # läsexporten — `diffa` fångade `Grundegenskapskrav` (s. 12) på just det.
    for span in data.get("spans") or []:
        etikett = str(span.get("label") or "").strip()
        kolumner = [str(c) for c in (span.get("columns") or []) if str(c)]
        if etikett and kolumner:
            lines += ["*%s — gemensam rubrik över %s*"
                      % (esc(etikett), esc(", ".join(kolumner))), ""]
    if headers:
        lines += ["| " + " | ".join(esc(h) for h in headers) + " |",
                 "|" + " --- |" * len(headers)]
        for row in rows:
            lines.append("| " + " | ".join(esc(c) for c in row) + " |")
    else:
        # Cellavskiljaren är ett vanligt BINDESTRECK, inte ett tankstreck.
        #
        # Skillnaden ser kosmetisk ut och är det inte. `freeze.words` sållar
        # bort ett ensamt `-` som markering men räknar ett ensamt `—` som ord,
        # och det är rätt: korpusen har 723 tryckta tabellceller som INNEHÅLLER
        # ett tankstreck och där betyder »inget värde«. En avskiljare av samma
        # tecken går inte att skilja från dem. MUT-AVE-terminal-states
        # rollformulär gav 56 sådana fantomord i ordgrinden — ord som aldrig
        # stått i boken, i en export som annars var riktig.
        for row in rows:
            lines.append("- " + " - ".join(esc(c) for c in row))
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Återflödning: ett element är EN tryckt rad
# ---------------------------------------------------------------------------

# Transkriptionen ger ett element per tryckt rad. Renderas raderna var för sig
# blir varje rad ett eget markdown-stycke — hela DoD-grundregelboken föll ut så,
# 3150 brödtextrader med tomrad emellan. Raderna fogas därför ihop till stycken
# igen, med tryckets egen geometri som facit i stället för gissningar om språket.
#
# Två signaler, båda uppmätta på grundregelboken (68 sidor, 3510 rader):
#   1. INDRAG. bbox-bruset inom en spalt ligger på ≤0,015 medan styckeindraget
#      ligger på 0,020–0,030. Tröskeln sätts däremellan.
#   2. KORT RAD. Satsen är utsluten, så varje rad utom styckets sista fyller
#      spalten (0,43–0,44 av sidbredden). En kortare rad avslutar ett stycke.
# Signalerna är oberoende och ORas — endera räcker för att bryta stycket.
# Listpunkter flödas om av samma skäl: en punkt som räknar upp färdigheter
# löper över åtta tryckta rader och blev åtta punkter (s. 17).
_REFLOW_TYPES = ("paragraph", "boxed_text") + _BULLET_TYPES
_INDENT_MIN = 0.018
_FULL_LINE = 0.92
# Andel av sidans löptextbredd under vilken en rad inte kan vara löptext alls.
# Uppmätt: brödtextrader 0,35–0,44, tabellceller under 0,22.
_MIN_PROSE_LINE = 0.5
# Rader inom så här långt avstånd i sidled räknas till samma spalt. Fönstret
# måste rymma indraget (0,020–0,030) men utesluta grannspalter — på de sidor som
# blandar tabell och brödtext ligger närmaste andra kolumn 0,05 bort.
_COLUMN_WINDOW = 0.04
_X_BUCKET = 0.005

# Ett hängande bindestreck i en samordning (`djur-` + `växt- och mineralriket`)
# ser ut som en avstavning men får inte fogas ihop.
_HANGING_HYPHEN = re.compile(r"^\S*-(?:\s|$)")

# Ett bindestreck vid radslut är inte alltid en avstavning. Två fall till, båda
# mätta i DoD-grundreglernas del III (BQ-024), och båda kändes igen först när
# felet stod LIVE i `bok.md`:
#
#   `PSY-` + `poäng`  ⇒ `PSY-poäng`      (sammansättningsstreck, inget mellanrum)
#   `mynt-` + `och penningsystemet` ⇒ `mynt- och penningsystemet` (hängande)
#
# Utan dem skrevs `PSYpoäng`, `STYkrav` och `myntoch` — ord som inte finns i
# boken — medan sidfilerna hela tiden återgav trycket rätt.
#
# (a) Ett VERSALT förled är en förkortning eller ett spelvärde (`PSY`, `STY`,
#     `BV`, `FV`), aldrig ett avstavat ordfragment. Motprovet som gör regeln
#     säker: en äkta avstavning av ett versalsatt ord fortsätter också i
#     versaler (`MOTSTÅNDSKRAF-` / `TEN`), och den fångas redan av kravet att
#     nästa rad ska börja gement.
_COMPOUND_ABBR = re.compile(r"(?:^|[\s(\[»„\"'])([A-ZÅÄÖ]{2,4})-$")
# (b) Ett fristående samordnande småord kan aldrig vara fortsättningen på ett
#     avstavat ord — då är strecket hängande och behåller sitt mellanrum.
_HANGING_NEXT = re.compile(r"^(?:och|eller|samt)\b", re.IGNORECASE)

# Ett VERSALSATT ord som bryts över radslutet läks också — men det gjorde det
# inte, eftersom läkningen krävde att nästa rad börjar GEMENT. Följden stod
# live i `bok.md`: `ANTI- MAGI`, `MÖRK- RET`, `TELEPORTE- RING`,
# `VARSE- BLIVNING` … tolv besvärjelsenamn med ett påhittat streck mitt i sig.
# Fortsättningens versalform är just det som skiljer arten från
# sammansättningsstrecket ovan: `ANTI-` + `MAGI` är ett avstavat `ANTIMAGI`
# (beslut s. 14), medan `PSY-` + `poäng` är två ord i en sammansättning.
_ALLCAPS_TAIL = re.compile(r"(?:^|[\s(\[»„\"'])[A-ZÅÄÖ]{2,}-$")
# Fortsättningen behöver bara EN versal. Kravet på två släppte igenom just de
# bryt där versalordet får en gement satt böjningsändelse — `LJU-` + `Sets`
# (del III s. 19, besvärjelsen LJUS i genitivliknande form `LJUSets`) och
# `MOTSTÅNDSKRAF-` + `Ten` (del III s. 39). Båda stod LIVE i `bok.md` med ett
# påhittat streck och ett mellanrum mitt i ordet, och båda är samma art som
# `ANTI-`/`MAGI`: versalt ord brutet över radslutet. Motprovet mot att regeln
# blir för vid är mätt över hela `bibliotek/` — mönstret VERSALER + bindestreck
# + versal förekommer i fyra fall totalt, och det fjärde (`ÄVENTYRS- OCH`) är
# ett hängande streck som fångas av `_HANGING_NEXT` FÖRE den här regeln.
_ALLCAPS_HEAD = re.compile(r"^[A-ZÅÄÖ]")

# `Tillredning:`, `Växtplats:`, `Effekt:` — en kort inledande etikett med
# kolon. Ett eller två ord räcker (`Naturligt skydd:`); längre än så är det
# löptext med ett kolon i sig, inte en fältrad.
_FIELD_LINE = re.compile(r"^[A-ZÅÄÖ][\wåäöÅÄÖ]*(?: [\wåäöÅÄÖ]+)?:(?:\s|$)")


def _bbox(el):
    return (el.get("source") or {}).get("bbox")


# ---------------------------------------------------------------------------
# Kursivspans (BQ-004): tryckets stilväxling INUTI ett element
# ---------------------------------------------------------------------------

def _stilmarkera(text, spans):
    """Sätt markdown-asterisker runt de kursiva intervallen i `text`.

    `spans` är [(start, end)] i teckenindex (end exklusiv), ordsnappade av
    `scripts/kursivspans.py` — de börjar och slutar alltid vid ordgränser, så
    markörerna hamnar aldrig mitt i ett ord. Ogiltiga intervall hoppas över i
    stället för att gissas till rätta.
    """
    if not spans:
        return text
    ut, pos = [], 0
    for a, b in sorted(spans):
        if not (isinstance(a, int) and isinstance(b, int)
                and pos <= a < b <= len(text)):
            continue
        ut.append(text[pos:a])
        ut.append("*")
        ut.append(text[a:b])
        ut.append("*")
        pos = b
    ut.append(text[pos:])
    return "".join(ut)


def _el_spans(el):
    """Elementets kursivintervall (utan liststyckenas `item`-poster)."""
    return [(sp.get("start"), sp.get("end"))
            for sp in ((el.get("data") or {}).get("style_spans") or [])
            if sp.get("style") == "italic" and "item" not in sp]


def _styled_text(el):
    """Elementtexten med tryckets kursivspans som `*…*`."""
    return _stilmarkera(el.get("text") or "", _el_spans(el))


# När två markerade element flödas ihop uppstår skarvar som `…i* *hans…`
# (kursivföljden fortsätter över element-/sidgränsen) och `…behö-* *va…`
# (ett avstavat ord inuti kursivföljden bryts av gränsen). Båda är samma
# tryckta kursivlöpning och läks till en: markörparet i skarven tas bort,
# och avstavningen läks som i löptext. Mönstren kan bara uppstå ur
# `_stilmarkera`s markörer — boken sätter aldrig `-* *` eller `* *` i sats.
_MARKOR_AVSTAVNING = re.compile(r"-\*(\s+)\*(?=[a-zåäöé])")
_MARKOR_SKARV = re.compile(r"\*(\s+)\*(?!\*)")


def _laka_markorskarvar(text):
    text = _MARKOR_AVSTAVNING.sub("", text)
    return _MARKOR_SKARV.sub(r"\1", text)


_ORDTECKEN = re.compile(r"[^0-9A-Za-zÅÄÖÉÜåäöéü\-]+")


def _ordnyckel(ord_):
    """Jämförbar form av ett ord: skiljetecken bort, skiftläge bort.

    Skiftläget måste bort. Blanketterna i MUT-AVE-terminal-state är satta i ett
    displaysnitt som ritar gemena kodpunkter som versaler, så samma ord står
    `killer-kängor` på s. 20 och `KILLER-KÄNGOR` på s. 29 — samma tryck, två
    skrivningar.
    """
    return _ORDTECKEN.sub("", ord_).casefold()


def mid_line_words(book):
    """Ord som står MITT PÅ en rad någonstans i boken.

    Ett bindestreck vid radslutet är tvetydigt: det kan vara avstavningens
    (faller bort) eller ett tryckt sammansättningsstreck (står kvar). Men
    samma ord står ofta någon annanstans i boken utan att en radbrytning kan
    ha skapat strecket, och DÅ är formen mätt i stället för gissad. Det är
    `beslut.md`-metoden »leta serie innan du beskär«, i kod.

    Bara ord som inte är sist på sin rad räknas — ett ord i radslutsposition
    är just det som frågan gäller och kan inte vittna om sig självt.
    """
    ord_ = set()
    for page in book.get("pages", []):
        for el in page.get("elements", []):
            if el.get("removed"):
                continue
            for rad in (el.get("text") or "").split("\n"):
                delar = rad.split()
                for token in delar[:-1]:
                    nyckel = _ordnyckel(token)
                    if nyckel:
                        ord_.add(nyckel)
    return ord_


def _join_text(prev, nxt, mittpa=None):
    """Foga ihop två tryckta rader och läk radbrytningen vid radslutet.

    Två radslut binder ihop orden utan mellanslag: avstavningens bindestreck
    (som faller bort) och sättarens snedstreck (som står kvar). Trycket bryter
    gärna en uppräkning mitt i — `(liten/medelstor/` + `stor)` — och utan
    läkningen faller den ut som `(liten/medelstor/ stor)`. Ett snedstreck som
    är satt MED mellanslag omkring sig (`Teknik / Grundkostnad`) är en
    avskiljare, inte en bindning, och läks därför inte.

    Bindestrecket faller bara bort när det verkligen är en avstavning. Ett
    sammansättningsstreck efter ett versalt förled (`PSY-` / `poäng`) och ett
    hängande streck framför ett samordnande småord (`mynt-` / `och`) står kvar
    i trycket och ska stå kvar här — se `_COMPOUND_ABBR` och `_HANGING_NEXT`.
    """
    prev, nxt = (prev or "").rstrip(), (nxt or "").lstrip()
    if not prev or not nxt:
        return prev or nxt
    if prev.endswith("-") and not prev.endswith((" -", "--")):
        # Hängande streck FÖRST — annars fångar förkortningsregeln `SMI-` + `och`
        # och skriver ihop dem till `SMI-och`.
        if _HANGING_HYPHEN.match(nxt) or _HANGING_NEXT.match(nxt):
            return prev + " " + nxt
        # BOKEN SJÄLV ÄR FACIT före varje regel. Står ordet någon annanstans i
        # boken MITT PÅ en rad — alltså utan att en radbrytning kan ha skapat
        # strecket — är den formen tryckets, och gissning behövs inte.
        #
        # Det var så MUT-AVE-terminal-states fem radslutsstreck avgjordes: alla
        # fem visade sig vara tryckta sammansättningsstreck, för `SVOT-utbildning`
        # står mitt på raden på s. 19 och `killer-kängor` mitt på raden på s. 20.
        # Reglerna nedan hade läkt fyra av dem, och `40års` och `30års` stod
        # live i `bok.md`. Det motsatta utfallet är lika bindande: hittas den
        # HOPSKRIVNA formen mitt på en rad ska strecket falla.
        if mittpa:
            forled = prev.split()[-1]                    # bär strecket
            efterled = nxt.split()[0] if nxt.split() else ""
            med_streck = _ordnyckel(forled + efterled)
            utan_streck = _ordnyckel(forled[:-1] + efterled)
            if med_streck and med_streck in mittpa:
                return prev + nxt
            if utan_streck and utan_streck in mittpa:
                return prev[:-1] + nxt
        if nxt[:1].islower():
            if _COMPOUND_ABBR.search(prev):
                # Sammansättningsstreck: strecket står kvar, utan mellanrum.
                return prev + nxt
            return prev[:-1] + nxt
        if _ALLCAPS_TAIL.search(prev) and _ALLCAPS_HEAD.match(nxt):
            # Avstavat versalsatt ord: strecket faller bort som i löptext.
            return prev[:-1] + nxt
    if prev.endswith("/") and not prev.endswith((" /", "//")):
        return prev + nxt
    return prev + " " + nxt


def _unwrap(text, mittpa=None):
    """Foga ihop de tryckta radbrytningarna INUTI ett elements egen text.

    Transkriptionskontraktet ger ett element per tryckt rad — men inte
    överallt. Exempelrutorna står ibland som ETT element med radbrytningarna
    kvar i `text` (s. 8:s `p008_e41` bär fem tryckta rader). `_reflow` ser då
    bara ett element och har ingenting att foga ihop, så rutan föll ut rad för
    rad i `bok.md` och ett avstavat ord vid radslutet behöll sitt streck:
    `lära sig PARA-` / `LYSERING ur den magiska kodexen Liber Necro-` /
    `sophicus …`.

    En TOM rad är däremot en styckegräns inne i rutan och bevaras — det är den
    som håller ihop en flerstyckesruta till ETT citatblock i markdown.
    """
    if "\n" not in (text or ""):
        return text
    stycken = []
    for stycke in re.split(r"\n[ \t]*\n", text):
        hopfogad = ""
        for rad in stycke.split("\n"):
            if rad.strip():
                hopfogad = _join_text(hopfogad, rad.strip(), mittpa)
        if hopfogad:
            stycken.append(hopfogad)
    return "\n\n".join(stycken)


def _median(values):
    values = sorted(values)
    if not values:
        return None
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2.0


def _local_column(bb, boxes):
    """(vänsterkant, radbredd) för spalten som raden `bb` tillhör.

    Måtten räknas ur de rader som ligger NÄRMAST i sidled, inte ur en global
    spaltindelning av sidan. Skälet är uppmätt: en sida som blandar tabell och
    brödtext har kolumner bara några hundradelar isär (s. 61: tabellens
    högerkolumn på 0,49 mot brödtextens 0,518). En global indelning slår ihop
    dem, och då ser varenda brödtextrad indragen ut mot tabellkolumnens
    vänsterkant — stycket sprängs vid varje rad.

    Vänsterkanten är det VANLIGASTE x-värdet, inte det minsta: i en spalt börjar
    de allra flesta rader vid marginalen, medan indragen och enstaka avvikande
    element är minoriteten. Bredden är medianen av samma skäl.
    """
    near = [b for b in boxes if abs(b[0] - bb[0]) <= _COLUMN_WINDOW]
    if not near:
        return None
    counts = Counter(int(round(b[0] / _X_BUCKET)) for b in near)
    left = min(counts, key=lambda bucket: (-counts[bucket], bucket)) * _X_BUCKET
    return left, _median([b[2] for b in near])


def _prose_width(boxes):
    """Sidans typiska radbredd för löptext, som 75:e percentilen.

    Medianen duger inte: på en tabelltung sida är den dominerad av celler
    (s. 61 har median 0,126 mot brödtextens 0,42). 75:e percentilen ligger
    stabilt på 0,40–0,44 även där.
    """
    widths = sorted(b[2] for b in boxes)
    if not widths:
        return None
    return widths[min(len(widths) - 1, int(len(widths) * 0.75))]


def _starts_paragraph(el, prev, nxt, boxes, prev_boxes,
                      bb=None, pbb=None, nbb=None):
    """Inleder `el` ett nytt stycke, eller fortsätter det föregående raden?

    Raden och dess föregångare mäts mot SIN EGEN sidas rader — ett stycke som
    löper över en sidbrytning har en rad på var sida, och sidorna kan ha olika
    spaltgeometri.

    `bb`/`pbb`/`nbb` är rad-precisa boxar för STYCKEFORMADE element (ett
    element = flera tryckta rader): elementets union-bbox har spaltens
    vänsterkant och fulla bredd oavsett hur styckena ser ut, så första radens
    indrag och sista radens utslutna korta rad — de två signaler hela
    omflödningen vilar på — är osynliga i den. Edsbrytarna i Erebos s. 6:s
    fyra styckedelade repliker flödades ihop till ETT stycke av exakt det
    skälet (BQ-001). Anroparen skickar första radens box för `el`/`nxt` och
    SISTA radens för `prev`, uppslagna ur sidans radmätning; utan mätning
    faller allt tillbaka på elementboxarna och ingenting ändras.
    """
    # 0. En fältrad inleder alltid sitt eget block. Örtposterna (s. 53–61) sätts
    #    `Etikett: värde` med en etikett per tryckt rad, och raderna fyller inte
    #    spalten — men på en sådan sida räknas breddreferensen ur etikettraderna
    #    själva, så varken kortradsregeln eller utslutningsregeln nedan biter.
    #    Utan detta faller hela posten ut som en enda rad:
    #    `Tillredning: Brygges Intagning: Appliceras Växtplats: Ljus lövskog`.
    if _FIELD_LINE.match((el.get("text") or "").lstrip()):
        return True
    # 0b. En tryckt rad som slutar på ett bindestreck kan INTE avsluta ett
    #     stycke — ordet fortsätter på nästa rad. Det är ett typografiskt
    #     faktum och väger tyngre än varje geometrisk signal nedan, så det
    #     prövas först.
    #
    #     Två fall i del III visar varför båda vägarna behövs:
    #     * UTAN geometri. Femton stycken föll isär med samma form:
    #       `…kommunicera med levan-` som eget stycke och `de ting.` som ett
    #       nästa (s. 4), `…’magiker och utbygdsjäga-` + `re’.` (s. 4),
    #       `…VARSEBLIV-` + `NING.` (s. 49). Fortsättningen är kort, och
    #       `pipeline/rows.py` mätte inget eget band för den — 64 av bokens
    #       2 474 element saknar bbox. `scripts/binda_rader.py` band 3 av dem;
    #       för de övriga SAKNAS bandet i mätningen (BQ-002/013/021).
    #     * MED geometri, mot utslutningsregeln. Exempelrutan på s. 10 bryts
    #       vid `…och mina kamra-` (bredd 0,3805 mot spaltens 0,4222 — under
    #       regel 1b:s gräns 0,92) och `ter skriker förtvivlat…` blev ett eget
    #       citatblock. Men en rad som slutar på avstavning är per definition
    #       inte styckets sista, hur kort den än råkar vara uppmätt.
    #
    #     Läkningen av strecket självt sköter `_join_text`, som skiljer
    #     avstavning från sammansättnings- och hängande streck. Här avgörs
    #     bara att raderna hör till SAMMA stycke — vilket gäller för alla tre
    #     arterna.
    prev_text = (prev.get("text") or "").rstrip()
    if prev_text.endswith("-") and not prev_text.endswith((" -", "--")):
        return False
    bb = bb if bb is not None else _bbox(el)
    pbb = pbb if pbb is not None else _bbox(prev)
    if bb is None or pbb is None:
        # Utan geometri finns inget facit — då fogas ingenting ihop.
        return True
    # 1a. En rad som är MYCKET kortare än sidans löptext är ingen löptextrad —
    #     den är en tabellcell. Utan detta fogas celler som ligger som
    #     `paragraph` ihop till cellsoppa (`Hyfsad simmare 2 3`, s. 56), för då
    #     räknas breddreferensen ur cellerna själva och blir meningslös.
    #     Regeln gäller bara framåt: en kort SISTA rad i ett stycke får
    #     fortfarande fogas till raden före sig.
    prose = _prose_width(prev_boxes)
    if prose and pbb[2] < _MIN_PROSE_LINE * prose:
        return True
    # 1b. Utsluten sats: fyllde föregående rad inte spalten tog stycket slut.
    pcol = _local_column(pbb, prev_boxes)
    if pcol and pbb[2] < _FULL_LINE * pcol[1]:
        return True
    # 2. Indrag inleder ett stycke — men bara ett ENSAMT indrag.
    #    Boken sätter också HÄNGANDE indrag (`Rundspark:` i marginalen med
    #    fortsättningsraderna indragna, s. 59; punktlistor på s. 65). Där är
    #    polariteten den omvända, och att läsa indraget som styckestart delar
    #    varje sådant stycke i en rad per stycke. Skillnaden är att ett hängande
    #    indrag DELAS av flera rader i följd, medan ett styckeindrag står ensamt.
    col = _local_column(bb, boxes)
    if col and bb[0] - col[0] >= _INDENT_MIN:
        if abs(bb[0] - pbb[0]) < _INDENT_MIN:
            return False
        if nbb is None:
            nbb = _bbox(nxt) if nxt is not None else None
        if nbb is not None and abs(nbb[0] - bb[0]) < _INDENT_MIN:
            return False
        return True
    return False


def _radbox(el, page, radrows, forsta):
    """Första eller sista tryckta radens box för ett element, ur radmätningen.

    Ger `None` när elementet saknar `source.rader` eller sidan saknar mätning
    — anroparen faller då tillbaka på elementets egen bbox. För ett enradigt
    element är svaret per definition samma box som elementets, så de
    radformade böckerna (del I–III) berörs inte av uppslaget.

    Kravet att textraderna går 1:1 med banden är bärande: ett element vars
    bindning inte går ihop (Edsbrytarna s. 5 `e05`: fem tryckta rader på tre
    band) pekar inte ut sin verkliga första/sista rad, och dess "sista rad"
    var där en kort bandstump som fick styckeregeln att läsa den som
    tabellcell och bryta ett stycke mitt i meningen (»…skött sig otroligt« /
    »klantigt så blir de…«). En trasig bindning ger union-boxen, aldrig en
    gissad rad.
    """
    rows = (radrows or {}).get(page)
    rader = (el.get("source") or {}).get("rader")
    if not rows or not rader:
        return None
    if (len(rader) >= 2
            and len((el.get("text") or "").split("\n")) != len(rader)):
        return None
    i = rader[0] if forsta else rader[-1]
    if not (0 <= i < len(rows)):
        return None
    b = rows[i].get("bbox")
    return b if b and len(b) == 4 else None


def _nasta_tryckta_rad(el, page, nxt, npage, radrows):
    """Boxen för den tryckta rad som FÖLJER elementets första.

    Indragsregelns grannvakt ("ett hängande indrag delas av nästa rad") måste
    jämföra med nästa TRYCKTA rad. För ett enradigt element är det nästa
    elements första rad — det gamla beteendet — men för ett styckeformat
    element är det elementets EGEN andra rad. Utan den skillnaden jämförs två
    styckens förstarader med varandra: på Edsbrytarna s. 6 dödade vakten den
    äkta gränsen mellan två indragna styckestarter tre tryckta rader isär, och
    på s. 5 lästes ett hängande citatblocks förstarad som styckestart eftersom
    "nästa rad" hämtades ur fel element och blocket bröts mitt i meningen.
    """
    rows = (radrows or {}).get(page)
    rader = (el.get("source") or {}).get("rader")
    if (rows and rader and len(rader) >= 2
            and len((el.get("text") or "").split("\n")) == len(rader)):
        i = rader[1]
        if 0 <= i < len(rows):
            b = rows[i].get("bbox")
            return b if b and len(b) == 4 else None
        return None
    return _radbox(nxt, npage, radrows, True) if nxt is not None else None


def _reflow(run, mittpa=None, radrows=None):
    """Dela en rad-följd i stycken och foga ihop varje styckes rader.

    Returnerar (sida, text, första_elementet) per stycke. Det sista behövs för
    att en punktlista och den löptext som följer under den kan ligga i SAMMA
    följd: blocket renderas efter vad det inleds av, inte efter följdens typ.

    `run` är (sida, element)-par och får spänna över en sidbrytning — det är
    just så ett stycke som fortsätter på nästa sida fogas ihop. Varje returnerat
    stycke bär därför sidan för sin EGEN första rad, inte följdens: annars
    tappas sidmarkören för varje sida som ett stycke råkar sträcka sig in i.

    Spaltmåtten räknas fram PER SIDA ur följdens egna rader. Båda avgränsningarna
    är nödvändiga: tas de ur sidan i stort mäts en smal exempelruta mot
    brödtextspalten och sprängs vid varje rad, och tas de ur hela följden blandas
    flera sidors spalter och tabellceller ihop till en obrukbar median.
    """
    per_page = {}
    for page, el in run:
        if _bbox(el):
            per_page.setdefault(page, []).append(_bbox(el))
    filled = [(page, el) for page, el in run
              if (el.get("text") or "").strip()]
    blocks = []
    for position, (page, el) in enumerate(filled):
        if blocks:
            ppage, pel = blocks[-1][-1]
            nxt = filled[position + 1][1] \
                if position + 1 < len(filled) else None
            npage = filled[position + 1][0] \
                if position + 1 < len(filled) else None
            fresh = _starts_paragraph(el, pel, nxt, per_page.get(page) or [],
                                      per_page.get(ppage) or [],
                                      bb=_radbox(el, page, radrows, True),
                                      pbb=_radbox(pel, ppage, radrows, False),
                                      nbb=_nasta_tryckta_rad(
                                          el, page, nxt, npage, radrows))
        else:
            fresh = True
        if fresh:
            blocks.append([(page, el)])
        else:
            blocks[-1].append((page, el))
    out = []
    for block in blocks:
        text = ""
        for _, el in block:
            text = _join_text(text, _unwrap(_styled_text(el).strip(), mittpa),
                              mittpa)
        text = _laka_markorskarvar(text)
        # Anmärkningarna samlas från HELA blocket, inte bara ledarelementet.
        # Ett tryckfel sitter sällan på styckets första rad — s. 65:s
        # "baserade på färdigheten" står på dess sista — och hade noten
        # hämtats ur `block[0]` skulle den tystna just där den behövs.
        out.append((block[0][0], text, block[0][1], _notes(block)))
    return out


def _notes(block):
    """Redaktionella anmärkningar på blockets element, i ordning."""
    ut = []
    for _, el in block:
        note = (el.get("anmarkning") or "").strip()
        if note and note not in ut:
            ut.append(note)
    return ut


def _note_md(notes):
    """Anmärkningen som en rad som INTE går att förväxla med boktext.

    Klamrar och kursiv är den gängse redaktionella konventionen. Kursiv ensam
    duger inte — bildtexter och tabellnoter är redan kursiva — och citatblock
    är upptaget av tryckets egna exempelrutor.
    """
    return ["*[Anmärkning: %s]*" % n for n in notes] + ([""] if notes else [])


# ---------------------------------------------------------------------------
# Hopfogning av tabeller över sidbrytning
# ---------------------------------------------------------------------------

# `tables.assemble` arbetar per sida och kan därför inte se att en tabell
# fortsätter på nästa. I grundregelboken bröts Särskilda förmågor-tabellen mitt
# i rad 78 (`INT-basera-`) och raderna 79–81 föll ut som listpunkter utanför
# tabellen.
_ROW_SPLIT = re.compile(r"^(\S+)\s+—\s+(.+)$", re.S)


def _same_table(a, b):
    ha = (a.get("data") or {}).get("headers") or []
    hb = (b.get("data") or {}).get("headers") or []
    return bool(ha) and ha == hb


def _stitch_list(table, lst):
    """Foga in en lista som i själva verket är tabellens fortsättning.

    Returnerar False och rör ingenting om någon punkt inte har radens form —
    att tappa text vore värre än en ful lista.
    """
    data = table.get("data") or {}
    rows = data.get("rows") or []
    items = [i.strip() for i in ((lst.get("data") or {}).get("items") or [])
             if i and i.strip()]
    if len(data.get("headers") or []) != 2 or not rows or not items:
        return False
    continuation, new_rows = None, []
    for idx, item in enumerate(items):
        match = _ROW_SPLIT.match(item)
        if match:
            new_rows.append([match.group(1), match.group(2)])
        elif idx == 0 and item[:1].islower():
            continuation = item
        else:
            return False
    if continuation:
        rows[-1] = list(rows[-1])
        rows[-1][-1] = _join_text(rows[-1][-1], continuation)
    data["rows"] = rows + new_rows
    table["data"] = data
    return True


def _stitch(items):
    """Slå ihop tabeller som löper över en SIDBRYTNING.

    Sidbrytningen är villkoret, inte en omständighet. Sammanfogningen fanns
    till för en tabell vars fortsättning hamnat på nästa sida, men prövade bara
    att rubrikerna var lika — och två tryckta tabeller med samma rubriker är
    inget ovanligt. MUT-AVE-terminal-state har NITTON vapentabeller med exakt
    `Vapen | GCL | Skada`, en per NPC, och tre av dem står på s. 14 (BQ-002).
    Där räddades de av att varje ruta inleds med sitt eget statblock, alltså av
    en tillfällighet i elementströmmen — hade två rutor stått intill varandra
    hade två olika personers vapen smält ihop till en tabell utan att något
    varnade, och ingen orddiff hade sett det: samma ord, en rad färre.

    Inom en och samma sida finns ingen sidbrytning att överbrygga, och då är
    två tabeller två tabeller.
    """
    out = []
    for page, el in items:
        prev_page, prev = out[-1] if out else (None, None)
        if prev is not None and prev.get("type") == "table":
            if (el.get("type") == "table" and _same_table(prev, el)
                    and page != prev_page):
                prev_data = prev.setdefault("data", {})
                prev_data["rows"] = (prev_data.get("rows") or []) + \
                    ((el.get("data") or {}).get("rows") or [])
                continue
            if el.get("type") == "list" and _stitch_list(prev, el):
                continue
        out.append((page, el))
    return out


# En cell som är ett TAL eller ett talintervall: `5`, `2.500`, `22,5`, `0–11`,
# `–2`, `1T6+2`, med eventuell fotnotssiffra efter (`5¹⁾`).
_NUMERIC_CELL = re.compile(r"^[+\-–±]?\d[\d\s.,:/T×x+\-–]*[⁰-⁹⁽⁾]*$")
# Ett rent streck är ingen uppgift alls — det betyder "gäller ej" i tabellerna
# och får inte rösta om kolumnens art.
_EMPTY_CELL = re.compile(r"^[—–\-]?$")


def _column_shapes(rows):
    """Kolumnernas art: `tal` eller `text`, mätt ur cellerna själva.

    Två tabeller med lika många kolumner är inte nödvändigtvis samma tabell.
    Formen är det som skiljer dem åt, och den går att mäta i stället för att
    antas.
    """
    if not rows:
        return None
    bredd = max(len(r) for r in rows)
    shapes = []
    for col in range(bredd):
        tal = text = 0
        for row in rows:
            cell = str(row[col]).strip() if col < len(row) else ""
            if _EMPTY_CELL.match(cell):
                continue
            if _NUMERIC_CELL.match(cell):
                tal += 1
            else:
                text += 1
        shapes.append("tal" if tal > text else "text" if text else None)
    return shapes


def _inherit_headers(items):
    """Ge en rubriklös deltabell tryckets egna kolumnrubriker.

    Rustningstabellen (del III s. 38) är EN tryckt tabell med EN rubrikrad —
    `Namn (kroppsdel) | Absorbering | Vikt i kg | Pris i sm` — och därunder nio
    delposter under var sin spännrubrik (`HJÄLM (HUVUD)`, `ARMSKYDD (ARM)³⁾`,
    `HARNESK (BRÖSTKORG OCH MAGE)` …). Bara den första deltabellen bär
    rubrikraden i trycket; de övriga står under samma kolumner. Transkriptionen
    återger det troget med tomma rubriker, och exporten skrev då ut en TOM
    rubrikrad (`| | | | |`) över var och en. Tabellen såg ut att sakna data,
    och en läsare som landar på `BRYNJEHOSOR (BEN)` har ingen aning om att
    `5 | 15 | 2.500` betyder absorbering, vikt och pris.

    Rubrikerna ärvs bara när det bevisligen är samma tryckta tabell som
    fortsätter: SAMMA sida, SAMMA antal kolumner, SAMMA kolumnform, och
    ingenting mellan tabellerna utom tabellrubriker och tabellnoter. Bryts
    kedjan av löptext, en överskrift eller en sidbrytning är det en ny tabell,
    och då ärvs ingenting — en påhittad kolumnrubrik är värre än en tom.

    Kolumnformen är den spärr som kostade mest att upptäcka. Antalet kolumner
    räcker inte: s. 25 sätter `Rasmodifikationer` (`Anka | –2`) direkt under
    förflyttningstabellen (`0–11 | 7`) under en egen spännrubrik, och med bara
    kolumnräkningen som villkor ärvde den rubrikerna `STO+FYS+SMI` och
    `Förflyttning` — som är fel, för dess kolumner är ras och modifikation.
    Skillnaden syns i cellerna: moderns första kolumn är TAL, dotterns är
    TEXT. Rustningstabellens delposter har samma form som modern hela vägen
    (text, tal, tal, tal) och ärver därför.

    En tabell som saknar rubriker i trycket OCH inte har någon sådan förlaga
    (skräcktabellen s. 10, fummeltabellerna) lämnas orörd med tom rubrikrad.
    Det är inte snyggt, men det är sant.
    """
    forlaga = None          # (sida, rubriker, kolumnform) att ärva från
    for page, el in items:
        etype = el.get("type")
        if etype in _CAPTION_TYPES:
            continue        # spännrubriken bryter inte tabellen
        if etype != "table":
            forlaga = None
            continue
        data = el.get("data") or {}
        headers = data.get("headers") or []
        rows = data.get("rows") or []
        if any(str(h).strip() for h in headers):
            # En TITELRAD är ingen förlaga. Prislistorna i MUT-REG-hacking
            # s. 4 bär `headers: ["MJUKVARA", ""]` — en spännande titel över
            # två omärkta kolumner, inte kolumnrubriker. Ärvs den sätts ett
            # tryckt ord över en tabell där det inte står (flödesschemat fick
            # `MJUKVARA`), osynligt för orddiffen eftersom ordet redan finns i
            # boken. Bara en rad som faktiskt etiketterar kolumner — minst två
            # icke-tomma celler — får bli förlaga; rustningstabellens
            # rubrikrad har fyra.
            if sum(1 for h in headers if str(h).strip()) >= 2:
                forlaga = (page, list(headers), _column_shapes(rows))
            else:
                forlaga = None
            continue
        if not (headers and rows and forlaga and forlaga[0] == page
                and len(forlaga[1]) == len(headers)):
            continue
        if _column_shapes(rows) != forlaga[2]:
            continue
        data["headers"] = list(forlaga[1])
        el["data"] = data
        el["headers_inherited"] = True
    return items


def _falt_etiketter(book):
    """Fältetiketter som bokens statblock faktiskt använder.

    Fogning B (nedan) matchar inget annat: etiketten ska vara tryckets egen,
    belagd i bokens andra rutor, inte en gissning. Färdighetsfamiljen läggs
    till uttryckligen — transkriptionen lagrar färdigheterna i `skills` och
    tappar då tryckets egen rubrikvariant (`Färdigheter & Förmågor`,
    DoD-bestiariet), så den syns inte bland `other`-nycklarna.
    """
    etiketter = set()
    for page in book["pages"]:
        for el in page["elements"]:
            if el.get("type") != "statblock":
                continue
            data = el.get("data") or {}
            etiketter.update((data.get("other") or {}).keys())
            if data.get("skills_label"):
                etiketter.add(data["skills_label"])
    etiketter.update({"Färdigheter", "Färdigheter & Förmågor"})
    return etiketter


_FORTS_RAD = re.compile(r"^([^:\n]{2,40}):\s*(.+)$")


def _stitch_fortsattningar(items, book):
    """Foga statblock som trycket bryter över en sidgräns (Krugal BQ-005).

    Sidfilerna ändras ALDRIG — var sida innehåller det som är tryckt på den.
    Fogningen sker här i läsexporten, och redovisas i `export/fogningar.json`
    så att ordgrinden kan attribuera den. Två mätta signaturer:

    A) Ett statblock med TOMMA `stats` sist på sidan + ett statblock med
       fyllda `stats` och samma (eller inget) namn först på nästa — samma
       tryckta ruta, satt över uppslaget. Utan fogningen skrev `bok.md`
       namnet två gånger (»5 livsmästare«, s. 7–8: först rubrik med två
       fält, sedan fet namnrad med tabellen). Fortsättningens fält renderas
       i huvudets block och namnraden faller bort — det ordborttaget är
       fogningens enda frekvensändring.

    B) Ett statblock sist på sidan + löptextrader först på nästa som börjar
       med en fältetikett bokens statblock använder (`Förflyttning: L4/F10`,
       `Färdigheter & Förmågor: …` — Megas, s. 16→17). Fälten hör till rutan
       och absorberas som fältrader; inga ordfrekvenser ändras.

    Returnerar (items, fogningar).
    """
    etiketter = _falt_etiketter(book)
    ut = []
    fogningar = []
    i, n = 0, len(items)
    while i < n:
        page, el = items[i]
        ut.append(items[i])
        i += 1
        if el.get("type") != "statblock":
            continue
        if i >= n or items[i][0] == page or items[i][0] != page + 1:
            continue  # inte sist på sidan, eller ingen direkt följande sida
        data = el.get("data") or {}
        cont_page, cont = items[i]
        # --- Signatur A ---------------------------------------------------
        cdata = cont.get("data") or {}
        if cont.get("type") == "statblock" and not (data.get("stats") or {}) \
                and (cdata.get("stats") or {}):
            cnamn = cdata.get("name") or ""
            if not cnamn or _samma_namn(cnamn, data.get("name")):
                for falt in ("stats", "extraStats", "skills", "weapons"):
                    if cdata.get(falt) and not data.get(falt):
                        data[falt] = cdata[falt]
                for falt in ("skills_text", "skills_label"):
                    if cdata.get(falt) and not data.get(falt):
                        data[falt] = cdata[falt]
                other = data.setdefault("other", {})
                for k, v in (cdata.get("other") or {}).items():
                    if k not in other:
                        other[k] = v
                el["data"] = data
                fogningar.append({
                    "typ": "statblock-fortsattning",
                    "sida_fran": page, "sida_till": cont_page,
                    "huvud": el.get("id"), "fortsattning": cont.get("id"),
                    "namn": data.get("name") or cnamn,
                    # Namnraden som inte längre renderas — ordgrindens kredit.
                    "ord_borta": [cnamn] if cnamn else [],
                    "belagg": "Krugal BQ-005: rutan är satt över sidgränsen; "
                              "sidfilerna oförändrade, fogning i läsexporten.",
                })
                i += 1
                continue
        # --- Signatur B ---------------------------------------------------
        # Fortsättningselementet kan bära FLERA fält som radbrutna
        # `Etikett: värde`-rader (mervyn-peak s. 5→6: Förflyttning +
        # Cybernetik + Färdigheter i samma paragraph), och ett värde kan
        # fortsätta på nästa tryckta rad utan egen etikett. Parsningen går
        # därför rad för rad: känd etikett öppnar ett fält, en etikettlös
        # rad hör till det öppna fältet, och allt annat refuserar HELA
        # elementet — hellre en orörd brödtextrad än en gissad absorption.
        while i < n and items[i][0] == page + 1:
            kand = items[i][1]
            text = (kand.get("text") or "").strip()
            if kand.get("type") != "paragraph" or not text:
                break
            other = data.setdefault("other", {})
            nya_falt, oppet, ok = [], None, True
            for rad in text.split("\n"):
                rad = rad.strip()
                if not rad:
                    continue
                m = _FORTS_RAD.match(rad)
                if m and m.group(1).strip() in etiketter:
                    falt = m.group(1).strip()
                    if falt in other or any(f[0] == falt for f in nya_falt):
                        ok = False  # fältet finns redan — inte rutans rad
                        break
                    nya_falt.append([falt, m.group(2).strip()])
                    oppet = falt
                elif oppet:
                    nya_falt[-1][1] += " " + rad
                else:
                    ok = False
                    break
            if not ok or not nya_falt:
                break
            for falt, varde in nya_falt:
                other[falt] = varde
            el["data"] = data
            fogningar.append({
                "typ": "faltrad-fortsattning",
                "sida_fran": page, "sida_till": items[i][0],
                "huvud": el.get("id"), "fortsattning": kand.get("id"),
                "namn": data.get("name"),
                "ord_borta": [],
                "belagg": "Krugal BQ-005: fältetiketterna %s är belagda i "
                          "bokens statblock; raderna hör till rutan. Inga "
                          "ordfrekvenser ändras."
                          % ", ".join(repr(f) for f, _ in nya_falt),
            })
            i += 1
    return ut, fogningar


def _stream(book, include_artifacts):
    """(sida, element) för hela boken, med cellblock monterade."""
    for page in book["pages"]:
        elements, _ = tables.assemble(page["elements"], page["page"])
        for el in elements:
            if el.get("removed"):
                continue
            if el.get("type") == "page_artifact" and not include_artifacts:
                continue
            yield page["page"], el


def _load_radrows(workdir, book):
    """Radmätningen per sida, för de styckeformade elementens omflödning.

    Läses direkt ur `pages/page_NNN.radboxar.json` — bok.json bär elementens
    `source.rader` men inte banden de pekar på. En sida utan mätfil ger bara
    att omflödningen faller tillbaka på elementboxarna, aldrig ett fel.
    """
    ut = {}
    for page in book.get("pages") or []:
        n = page.get("page")
        f = Path(workdir) / "pages" / ("page_%03d.radboxar.json" % n)
        if not f.is_file():
            continue
        try:
            ut[n] = read_json(f).get("rows") or []
        except (ValueError, OSError):
            continue
    return ut


def export_markdown(workdir, include_artifacts=False):
    log = setup_logging(workdir)
    book = _load_book(workdir)
    radrows = _load_radrows(workdir, book)
    lines = []
    title = (book["source"].get("metadata") or {}).get("title") \
        or Path(book["source"]["path"]).stem
    lines += ["# %s" % title, ""]
    items = _inherit_headers(_stitch(list(_stream(book, include_artifacts))))
    items, fogningar = _stitch_fortsattningar(items, book)
    fogfil = export_dir(workdir) / "fogningar.json"
    if fogningar:
        log.info("sidgränsfogningar: %d (se export/fogningar.json)",
                 len(fogningar))
        fogfil.write_text(json.dumps(fogningar, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    elif fogfil.is_file():
        fogfil.unlink()  # idempotens: inga fogningar -> ingen kvarglömd fil
    arvda = [el.get("id") for _, el in items if el.get("headers_inherited")]
    if arvda:
        # Ingen tyst ändring: rubrikraden står inte i trycket över just den
        # deltabellen, den är hämtad från tabellens egen rubrik ovanför.
        log.info("ärvda kolumnrubriker i %d deltabeller: %s",
                 len(arvda), ", ".join(str(i) for i in arvda))
    last_page = None
    index = 0
    # Senaste rubrik, för att statblocket inte ska upprepa NPC-namnet.
    senaste_rubrik = None
    # Bokens egna ord i mittradsposition — facit för radslutets bindestreck.
    mittpa = mid_line_words(book)
    while index < len(items):
        page, el = items[index]
        etype = el.get("type")
        # En rad-följd samlas ihop och flödas om till stycken. Följden bryts av
        # varje annan elementtyp, och av att stilen växlar (kursiv exempelruta).
        if etype in _REFLOW_TYPES:
            run, style = [], el.get("style")
            # En listpunkt spänner ofta över flera tryckta rader: bara den
            # första bär punkttecknet, resten är vanliga rader. Bryts följden
            # vid typbytet hamnar fortsättningen i ett eget stycke, och ett
            # avstavat ord över radslutet läker aldrig (`motstån-` / `daren.`,
            # del I s. 51). Följden får därför svälja efterföljande löptext, och
            # `_reflow` avgör var punkten slutar — blocket renderas sedan efter
            # vad det INLEDS av, så löptexten under listan blir stycke igen.
            svalj = (etype,) + (("paragraph",) if etype in _BULLET_TYPES
                                else ())
            while index < len(items):
                nxt_page, nxt = items[index]
                if nxt.get("type") not in svalj or nxt.get("style") != style:
                    break
                run.append((nxt_page, nxt))
                index += 1
            blocks = _reflow(run, mittpa, radrows)
            for blk_page, text, lead, notes in blocks:
                if blk_page != last_page:
                    lines += ["<!-- sida %d -->" % blk_page, ""]
                    last_page = blk_page
                if lead.get("type") in _BULLET_TYPES:
                    # Punkterna hålls ihop utan tomrad emellan, annars blir
                    # varje punkt en egen lista i markdown.
                    lines += ["- %s" % text.lstrip(_BULLET_GLYPHS).lstrip()]
                elif lead.get("type") == "boxed_text":
                    # En tryckt exempelruta är EN ruta även när den rymmer
                    # flera stycken. Skiljs styckena av en TOM rad blir de två
                    # citatblock i markdown och rutan går synligt itu — s. 10:s
                    # HINDER- och SLUMPMÄSSIGA MÖTEN-exempel bröt av precis så
                    # sedan raderna började mätas på sin egen bredd i stället
                    # för på rutans ram. Separatorn är därför en CITERAD
                    # tomrad, samma grepp som håller ihop punktlistorna.
                    if lines and lines[-1].startswith(">"):
                        lines += [">"]
                    lines += ["> " + text.replace("\n", "\n> ")]
                elif style == "italic":
                    lines += ["*%s*" % text, ""]
                else:
                    lines += [text, ""]
                lines += _note_md(notes)
            if blocks and (etype in _BULLET_TYPES or etype == "boxed_text"):
                lines += [""]
            continue
        index += 1
        text = (el.get("text") or "").strip()
        if page != last_page:
            lines += ["<!-- sida %d -->" % page, ""]
            last_page = page
        if etype == "heading":
            level = min(int(el.get("level", 2)) + 1, 6)
            # Rubrikens kursivspans renderas — stilen kan växla inuti EN
            # rubrik (SJÖSVALANS kursiv, ÅTERKOMST rak, s. 7). Ett helkursivt
            # `style`-fält på rubriken hedras också; grenen läste det aldrig
            # förrän BQ-004.
            rubrik = _styled_text(el).strip()
            if el.get("style") == "italic" and not _el_spans(el):
                rubrik = "*%s*" % rubrik
            lines += ["#" * level + " " + rubrik, ""]
            senaste_rubrik = text
        elif etype in ("toc_entry", "index_entry"):
            # Flödas ALDRIG om: en innehålls- eller registerpost är en rad,
            # och att foga ihop dem skulle förstöra uppställningen.
            lines += ["*%s*" % text, ""] if el.get("style") == "italic" \
                else [text, ""]
        elif etype == "list":
            # Kursivspans per listpost (`item`-formen): kartlegendens post 5
            # lutar i sin helhet i trycket (s. 10, BQ-004).
            per_post = {}
            for sp in (el.get("data") or {}).get("style_spans") or []:
                if sp.get("style") == "italic" and "item" in sp:
                    per_post.setdefault(sp["item"], []).append(
                        (sp.get("start"), sp.get("end")))
            lines += ["- %s" % _stilmarkera(item, per_post.get(i) or [])
                      for i, item in
                      enumerate((el.get("data") or {}).get("items") or [])]
            lines += [""]
        elif etype == "table":
            lines += _table_md(el)
        elif etype == "statblock":
            lines += _statblock_md(el, senaste_rubrik)
            senaste_rubrik = None
        elif etype in _CAPTION_TYPES:
            # Bildtext/tabellnot är inte brödtext; kursiv skiljer den åt.
            lines += ["*%s*" % text, ""] if text else []
        elif etype in tables.CELL_TYPES:
            # Cellblock som monteringen inte kunde tyda (ojämnt antal
            # celler). Att tappa värdena är värre än en ful rad, så de
            # skrivs ut — och sidan syns i varningsloggen.
            lines += ["| %s |" % text] if text else []
        elif text:
            lines += [text, ""]
        lines += _note_md(_notes([(page, el)]))
    _warn_unknown_types(book, log)
    warn_empty_payloads(book, log)
    out = export_dir(workdir) / "bok.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    # Stämpeln ligger i `export/proveniens.json`, inte i bok.md: filen är
    # ordkonserveringens facit och en revisionssträng i den skulle ge en ny
    # "nytt ord"-rad vid varje commit (se pipeline/provenance.py).
    provenance.record(workdir, "bok.md")
    log.info("export markdown -> %s", out)
    return out


# ---------------------------------------------------------------------------
# CSV (en fil per tabell)
# ---------------------------------------------------------------------------

def export_csv(workdir):
    log = setup_logging(workdir)
    book = _load_book(workdir)
    outdir = export_dir(workdir) / "tabeller"
    outdir.mkdir(exist_ok=True)
    # En tabell som bryts över en SIDBRYTNING är EN tabell. Fragmenten pekar på
    # huvudelementet med `data.fortsattning_av` (BQ-010), men fältet var inert:
    # varje fragment blev en egen csv, och Skräcktabellen föll ut som två filer
    # som såg ut att vara skilda tabeller. Här fogas de ihop i SIDORDNING under
    # huvudelementets namn, med huvudets `headers` skrivna en gång. Se BQ-011.
    fragment = {}
    for page in book["pages"]:
        elements, _ = tables.assemble(page["elements"], page["page"])
        for el in elements:
            if el.get("removed") or el.get("type") != "table":
                continue
            huvud = (el.get("data") or {}).get("fortsattning_av")
            if huvud:
                fragment.setdefault(huvud, []).append((page["page"], el))

    n = 0
    for page in book["pages"]:
        # Samma montering som md/docx, annars saknas de tabeller som ligger
        # som lösa celler i CSV-exporten.
        elements, _ = tables.assemble(page["elements"], page["page"])
        # ...och samma rubrikarv: rustningstabellens delposter (s. 38) skulle
        # annars falla ut som åtta csv-filer med en tom rubrikrad var, medan
        # markdownen har tryckets kolumnnamn. Arvet är sidlokalt, så det
        # räcker att köra det per sida här.
        _inherit_headers([(page["page"], el) for el in elements
                          if not el.get("removed")])
        for el in elements:
            if el.get("removed"):
                continue
            if el.get("type") != "table":
                continue
            data = el.get("data") or {}
            if data.get("fortsattning_av"):
                continue  # skrivs med sitt huvudelement
            headers, rows = data.get("headers"), list(data.get("rows") or [])
            for _, bit in sorted(fragment.get(el.get("id"), []),
                                 key=lambda t: t[0]):
                rows.extend((bit.get("data") or {}).get("rows") or [])
            if not rows:
                continue
            n += 1
            out = outdir / ("sida%03d_%s.csv" % (page["page"],
                                                 el.get("id", "tabell")))
            with open(out, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                if headers:
                    w.writerow(headers)
                w.writerows(rows)
    provenance.record(workdir, "tabeller/")
    log.info("export csv: %d tabeller -> %s", n, outdir)
    return outdir, n


# ---------------------------------------------------------------------------
# DOCX (via befintliga create-docx.js)
# ---------------------------------------------------------------------------

def _to_docx_content(book):
    """Konvertera kanonisk modell till create-docx.js innehållsformat."""
    content = []
    for page in book["pages"]:
        if content:
            content.append({"type": "pagebreak", "page": page["page"]})
        elements, _ = tables.assemble(page["elements"], page["page"])
        for el in elements:
            etype = el.get("type")
            text = (el.get("text") or "").strip()
            if el.get("removed"):
                continue
            if etype == "page_artifact":
                continue
            if etype == "heading":
                level = min(int(el.get("level", 2)), 3)
                content.append({"type": "heading%d" % level, "text": text})
            elif etype in ("paragraph", "toc_entry", "index_entry"):
                content.append({"type": "italic" if el.get("style") == "italic"
                                else "paragraph", "text": text})
            elif etype == "boxed_text":
                content.append({"type": "italic", "text": text})
            elif etype == "list":
                items = (el.get("data") or {}).get("items") or []
                content.append({"type": "list", "items": items})
            elif etype == "table":
                data = el.get("data") or {}
                content.append({"type": "table",
                                "headers": data.get("headers") or [],
                                "rows": data.get("rows") or []})
            elif etype == "statblock":
                data = el.get("data") or {}
                content.append({"type": "statblock",
                                "name": data.get("name"),
                                "stats": data.get("stats") or {},
                                "skills": data.get("skills") or {},
                                "other": data.get("other") or {}})
            elif etype in _BULLET_TYPES:
                content.append({"type": "list", "items": [text]})
            elif etype in _CAPTION_TYPES:
                content.append({"type": "italic", "text": text})
            elif text:
                content.append({"type": "paragraph", "text": text})
    return content


def export_docx(workdir):
    """Avvecklad — markdown är läsformatet (användarbeslut 2026-07-29).

    Behållen för den som uttryckligen begär --format docx, men generatorn
    saknar rendering för statblockens vapentabeller och producerar därför
    ofullständiga filer. Ingår inte längre i `alla`.
    """
    log = setup_logging(workdir)
    log.warning("docx-exporten är avvecklad och saknar statblockens "
                "vapentabeller — markdown är läsformatet")
    book = _load_book(workdir)
    title = (book["source"].get("metadata") or {}).get("title") \
        or Path(book["source"]["path"]).stem
    payload = {"title": title, "content": _to_docx_content(book)}
    tmp = export_dir(workdir) / "bok.docx.json"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    out = export_dir(workdir) / "bok.docx"
    result = subprocess.run(
        ["node", str(DOCX_SCRIPT), str(tmp), str(out)],
        capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit("create-docx.js misslyckades: %s" % result.stderr)
    log.info("export docx -> %s", out)
    return out
