"""Deterministisk uppmätning av tryckta radboxar ur sidbilden (Regel 5).

Bakgrund: skanningarna i det här repot har inget användbart textlager — både
DoD-grundreglernas del I och del II har **bara vattenstämpeln** i PDF:ens
textlager. Ändå är `source.bbox` det som bär hela den nedströms geometrin:
`forbesikta`s regler för kolumnsammanslagning, vertikal radsammanslagning,
läsordning och tabellkandidat är alla verkningslösa utan den, och korrektur-
teamets forensik (bläckbandsräkning, spaltmarginalklippning) likaså.

Den här modulen mäter fram boxarna ur bilden i stället för att låta en
språkmodell gissa dem. Metoden är ren bläckprojektion — ingen OCR, ingen modell:

  1. Sidan renderas till gråskala i mäthög upplösning (~2800 px längsta sidan;
     den inbäddade skanningen är ~1950×2820, så inget detaljvärde tappas).
  2. Varje bildrad reduceras till ett mått på hur mycket SATS den innehåller.
     Två naiva mått fungerar inte, båda uteslutna genom mätning:
     per-pixel-tröskling faller på att skanningen är rastrerad (27 % av
     pixlarna i ett tomt radmellanrum ligger under varje rimlig gråtröskel),
     och medelsvärta faller på gråtonade tabellrader (fyllningen är lika mörk
     som satsen). Måttet är i stället **kontrasten** längs raden — se
     `row_profile`.
  3. Tröskeln är **lokal**, inte global: raderna hakar i varandra via staplar
     och diakriter, så dalen mellan två rader når aldrig noll. Tröskeln sätts
     mitt emellan lokalt golv och lokal topp (se `_profile_bands`).
  4. Sidhuvud och sidfot mäts som EGNA zoner, mot sin egen profil och fönstervis
     — se `zone_profile`. Mätta mot hela sidan drunknar de.
  5. Kroppen delas i lodräta avsnitt vid stora luckor, och spalterna mäts per
     avsnitt: en sida kan vara tvåspaltig upptill och ha en fullbredds tabell
     nedtill (del I, s. 61).
  6. Inom varje spalt ger profilen ett band per tryckt rad, och bandet mäts i
     x-led inom sin egen spalt.

Utfallet skrivs som `page_NNN.radboxar.json` och matas till transkriberaren,
som fyller i `source.bbox` ur mätningen i stället för att uppskatta
koordinater. Boxarna är ett STÖD, inte ett facit för elementindelningen: en
tabell blir fortfarande ETT `table`-element, med de täckta radernas union som
bbox — se transkriptionskontraktet.

Kalibrerat mot den färdigkorrekturlästa del I, **alla 67 sidor med facit,
4107 element med känd bbox: 98,5 % träffas av ett uppmätt band.** 46 sidor
ligger på exakt 100 %, 62 sidor på minst 95 %, tre under: blanketterna s. 67
(58 %) och s. 68 (87 %) samt s. 3 (93 %, kollofonsida med illustration). Av de
62 missarna ligger 25 på de två blanketterna och 6 på sidor som mätningen
själv flaggar som grafikdominerade — där ska PNG:n läsas oavsett. Resten är
~0,5 element per sida.

Blanketter är den kända svagheten och kräver ingen fix här: fältens etiketter
sitter i streckade rutor, linjalerna blir sidans vanligaste "band" (7 px) och
förgiftar radhöjdsmedianen. Bok 1:s egna beslut säger redan att blanketter
serialiseras fältgrupp för fältgrupp av den som läser sidan.

Koordinatkonventionen är repots: `[x, y, bredd, höjd]`, normaliserat mot
sidans mått, med **y räknat från sidans NEDERKANT** till boxens underkant.
"""
import numpy as np

try:  # PyMuPDF importeras likadant i render.py
    import fitz
except ImportError:  # pragma: no cover - samma beroende som övriga pipelinen
    fitz = None

from .log import setup_logging
from .manifest import Manifest, atomic_write_json, page_file

# Längsta sidan i mätbilden. Den inbäddade skanningen ligger på ~1950×2820 i
# båda böckerna; att gå högre ger bara interpolation (se docs), att gå lägre
# suddar ihop rader som ligger tätt.
MEASURE_DIM = 2800

# Övre/nedre andel av sidan där ett band ÖVER HUVUD TAGET kan vara sidhuvud
# eller sidfot. Samma tal som extract_text.EDGE_BAND, av samma skäl. Läget
# ensamt räcker dock inte som kriterium — se `_edge_block`.
EDGE_BAND = 0.08
# Luckan (i radhöjder) som skiljer sidhuvud/sidfot från satsytan. Ett sidhuvud
# är ISOLERAT, inte bara högt upp: mellan kolumntiteln och första textraden
# ligger alltid mer än ett radavstånd, mellan två textrader mindre. Uppmätt på
# del II: separerande luckor 1,1-5,5 radhöjder, luckor inne i satsen 0,2-0,8.
EDGE_GAP_FACTOR = 1.0

# Fönstret som lokalt golv och lokal topp mäts över, som andel av sidhöjden.
# ~3 % är två radavstånd vid den här sättningen: tillräckligt för att fånga
# både dalen och toppen kring varje rad, för litet för att en rubrik i stor
# grad ska dra upp golvet för brödtexten under.
LOCAL_WINDOW = 0.03
# Var tröskeln läggs mellan lokalt golv och lokal topp.
LOCAL_FRACTION = 0.5
# Absolut golv, som andel av sidans mörkaste profilvärde. Utan det får en helt
# blank sidyta (profil ≈ 0) en tröskel på ≈ 0 och blir ett enda långt band.
MIN_DARKNESS_SHARE = 0.08
# En strukturlös men kontrastrik yta — en rastrerad bildton — får den lokala
# tröskeln att skära genom bruset och ger skenrader (128 på pärmsidan, del I
# s. 66). Ett krav på lokalt dynamiskt omfång tar bort dem, men kostade 3 %
# täckning på VERKLIGA textsidor (s. 61 föll 95→83 %, s. 63 100→62 %), eftersom
# en sida med ett mörkt bildparti får ett stort sidomfång som brödtexten sedan
# mäts mot. Det bytet är fel: skenrader på en illustrationssida fångas redan av
# `dominerande_grafik` i sammanfattningen, och där ska PNG:n läsas ändå.

# Lodrät ränna: en bildkolumn med mindre svärta än så här (andel av sidans
# maxprofil) räknas som tom. Rännan mellan spalterna är verklig pappersyta.
GUTTER_DARKNESS_SHARE = 0.05
# Fönsterbredd vid fönstervis kontrastmätning, som andel av sidbredden. ~5 %
# rymmer en foliosiffra med marginal och är smalt nog att inte dränka den.
ZONE_WINDOW = 0.05
# Minsta rännbredd respektive spaltbredd, som andel av sidbredden.
MIN_GUTTER_WIDTH = 0.015
MIN_COLUMN_WIDTH = 0.12
# Lucka (i radhöjder) som bryter kroppen i ett nytt lodrätt avsnitt med egen
# spaltindelning. Uppmätt på s. 61: luckan mellan den tvåspaltiga löptexten
# och fullbreddstabellen är ~8 radhöjder, luckan mellan två stycken ~1.
SEGMENT_GAP_FACTOR = 2.5

# Band som ligger närmare varandra än så här (av medianbandhöjden) hör till
# samma tryckta rad — annars bryts diakriter och understrukna rader loss.
MERGE_GAP_FACTOR = 0.4
# ... men medianBANDHÖJDEN duger inte ensam som mått. På sidor med liten grad
# (registret, s. 63) delas varje tryckt rad i två band — versalernas/staplarnas
# fragment och x-höjdens kropp — och då blir medianhöjden fragmentets, inte
# radens: 5 px i stället för 26. Tröskeln 0,4 x 5 = 2 px fogar inte ihop något,
# medianen förblir fel, `_segments` bryter sidan i ETT segment PER RAD (luckan
# 21 px > 2,5 x 5), och spaltprofilen mäts då över 26 px höga skivor där den
# lokala tröskeln inte har något att arbeta med. Resultatet är kapade band och
# en tappad sista rad i vardera spalten (beslut.md D 6).
# Luckorna är däremot bimodala och robusta: inom en rad 5 px, mellan rader
# 21 px. Degenerationen känns igen på att medianhöjden UNDERSTIGER mediangapet
# — ett band som är lägre än luckan till nästa kan inte vara en tryckt rad.
# Bara då byts måttet ut; på varje sida där medianhöjden är en verklig radhöjd
# gäller höjdregeln oförändrad. (Att i stället ta MAX av de två måtten fogar
# ihop de sista raderna i en spalt på sidor med gles sättning — uppmätt: s. 2,
# 60 och del I s. 61 tappade då 4-6 element var.)
MERGE_GAP_SHARE = 0.5
# Band lägre än så här (av medianen) är skanningsbrus, inte en rad.
MIN_BAND_FACTOR = 0.25
# Band högre än så här (mot SIDANS radhöjd) är en illustration, inte en textrad.
# Faktorn ligger medvetet högt. Felen är osymmetriska: ett bildband som slinker
# igenom som rad kostar transkriberaren en blick, medan sats som stämplas som
# bild försvinner ur listan. Uppmätt: verkliga illustrationsband ligger på
# 20–55 radhöjder, kapitelrubriker i stor grad på 2–3 (`KRIGARE` s. 15,
# `LÄRD MAN` s. 16), och sammanslagna tabellband däremellan. Vid 3,0 föll varje
# uppslagsrubrik bort; svepet 6/8/10/12/16 gav 97,5/97,6/97,9/97,9/98,1 %.
GRAPHIC_HEIGHT_FACTOR = 16.0
# Smalaste band som räknas som en tryckt rad, som andel av sidbredden.
# Guarden behövs först sedan kantzonerna fick sitt eget brusgolv (D 3): mot
# sidans radhöjd sållades stänket bort på köpet, mot zonens egen median gör
# det inte det.
#
# Nivån är uppmätt, inte gissad. Bokens smala kantband fördelar sig
# 1, 1, 1, 2, 3, 4, 5 px (stänk) — sedan 12 px, som är s. 2:s folio `1` —
# sedan 16 och 17 px (s. 22:s sidhuvud, s. 4:s folio `3`). Tröskeln måste
# ligga i luckan mellan 5 och 12; en ensam smal siffra är den svåraste
# verkliga raden på en sida. Vid 0,008 (16 px) kastades folion `1`, vilket
# tog tillbaka en del av det defekt 3 just hade vunnit.
MIN_ROW_WIDTH = 0.004
# Bandets bakgrundsnivå i `_extent` tas som den här percentilen av svärtan
# längs bandet — låg nog att träffa pappret på en vanlig rad, hög nog att inte
# fastna i en enstaka ljus pixel mitt i en tonplatta.
SHADE_PERCENTILE = 10
# Ligger bakgrunden så här högt mot bandets mörkaste kolumn är bandet satt på
# en fylld platta (tonad tabellrad, ornament) och tröskeln räknas relativt
# bakgrunden. Uppmätt på del II s. 62: oskuggad rad 0,07, skuggad rad 0,45.
SHADE_SHARE = 0.3

KIND_ROW = "rad"
KIND_GRAPHIC = "grafik"


def _runs(mask):
    """[(start, stop)) för varje sammanhängande True-block i en 1D-boolmask."""
    edges = np.flatnonzero(np.diff(np.concatenate(([False], mask, [False]))))
    return list(zip(edges[::2], edges[1::2]))


def _rolling(prof, window, fn):
    """Glidande min/max över profilen, kantutfylld så längden bevaras."""
    window = max(3, int(window) | 1)
    pad = window // 2
    view = np.lib.stride_tricks.sliding_window_view(
        np.pad(prof, pad, mode="edge"), window)
    return fn(view, axis=1)


def _profile_bands(prof, height):
    """Band i en svärtprofil, med LOKALT satt tröskel.

    Ett globalt tröskelvärde fungerar inte på tryckt sats: staplar och
    diakriter från raderna ovanför och under gör att dalen mellan två rader
    aldrig når noll (uppmätt ~66 av 150 på s. 58). Tröskeln läggs därför mitt
    emellan lokalt golv och lokal topp, med ett absolut golv så att en helt
    blank sidyta inte blir ett enda långt band.
    """
    if not len(prof) or not prof.max():
        return []
    window = max(3, int(LOCAL_WINDOW * height))
    low = _rolling(prof, window, np.min)
    high = _rolling(prof, window, np.max)
    threshold = low + LOCAL_FRACTION * (high - low)
    floor = MIN_DARKNESS_SHARE * prof.max()
    return _runs(prof >= np.maximum(threshold, floor))


def darkness(gray):
    """Svärta 0–255 (255 = helsvart). Papper är inte vitt, det är rastrerat."""
    return 255.0 - gray.astype(np.float32)


def row_profile(block):
    """Radprofil = KONTRAST längs raden, inte medelsvärta.

    Medelsvärtan kan inte skilja en gråtonad tabellrad från text: fyllningen
    är lika mörk som satsen. Kontrasten kan — en jämn ton har låg spridning,
    en rad med bokstäver hög. Uppmätt i Hunddjurstabellen (del II, s. 27):
    fyllning utan text std 19–25, samma fyllning med text std 65–69, medan
    medelsvärtan låg på 85–90 i båda fallen och slog ihop hela tabellen till
    ett enda band.
    """
    return block.std(axis=1)


def _median_height(bands):
    heights = sorted(b - a for a, b, *_ in bands)
    return (heights[len(heights) // 2] if heights else 0) or 1


def zone_profile(block, window):
    """Radprofil för en kantzon: STARKASTE fönstret, inte hela bredden.

    Sidhuvud och sidfot innehåller små, centrerade saker — en kolumntitel som
    täcker 0,14 av sidbredden, en foliosiffra som täcker 0,017 — och bredvid
    dem en linjeregel som spänner över allt. Medelvärdesbildas kontrasten över
    hela bredden dränks siffran av regeln: den satte tröskeln, och alla 13
    foliosiffror och varje kolumntitel föll bort. Genom att dela raden i
    fönster och ta det starkaste räknas ett litet element lika högt som ett
    brett, vilket är precis vad som gäller i en kantzon.

    Gäller BARA kantzonerna. Samma mått på kroppen ger 84 % täckning mot 98,5 %
    (uppmätt över hela del I): i brödtext blir ett smalt fönster känsligt för
    diakriter och enstaka staplar, och raderna delas sönder.
    """
    width = block.shape[1]
    window = max(8, min(int(window), width))
    n = width // window
    if n < 2:
        return row_profile(block)
    trimmed = block[:, :n * window].reshape(block.shape[0], n, window)
    return trimmed.std(axis=2).max(axis=1)


def _median_gap(bands):
    """Medianlucka mellan på varandra följande band."""
    gaps = sorted(bands[i + 1][0] - bands[i][1] for i in range(len(bands) - 1))
    return gaps[len(gaps) // 2] if gaps else 0


def _merge_and_classify(bands, page_median=None, noise_from_page=True):
    """Foga ihop band som hör till samma rad och skilj text från grafik.

    `page_median` är SIDANS radhöjd och måste komma utifrån när anropet gäller
    ett enskilt avsnitt: ett avsnitt som bara innehåller en illustration får
    annars illustrationen som sin egen median, och 160 px är aldrig sex gånger
    160 px — bildpartiet klassas då som en textrad.

    `noise_from_page=False` mäter brusgolvet mot ZONENS egen median i stället
    för sidans. Kantzonerna behöver det: en foliosiffra ger genom
    `zone_profile` band på 2-4 px, och mätt mot brödtextens 22 px stämplas de
    som skanningsbrus och kastas — därför mättes folion nästan aldrig upp, och
    det som märktes `sidfot` blev i stället föregående rads underlängder eller
    vattenstämpeln (beslut.md D 3). Grafikklassningen använder alltid sidans
    median: "hög" ska betyda hög mot sidans sats.
    """
    if not bands:
        return []
    median, gap = _median_height(bands), _median_gap(bands)
    threshold = (median * MERGE_GAP_FACTOR if median >= gap
                 else gap * MERGE_GAP_SHARE)
    merged = [list(bands[0])]
    for a, b in bands[1:]:
        if a - merged[-1][1] < threshold:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    own_median = _median_height(merged)
    graphic_median = page_median or own_median
    noise_median = graphic_median if noise_from_page else own_median
    out = []
    for a, b in merged:
        height = b - a
        if height < noise_median * MIN_BAND_FACTOR:
            continue  # skanningsbrus
        kind = (KIND_GRAPHIC if height > graphic_median * GRAPHIC_HEIGHT_FACTOR
                else KIND_ROW)
        out.append((a, b, kind))
    return out


def _extent(dark, top, bottom, lo, hi):
    """Bandets faktiska x-utsträckning inom sin spalt.

    Tröskeln måste läggas mot bandets EGEN bakgrund, inte mot noll. En
    gråtonad tabellrad ligger på en platta som är nästan lika mörk som satsen,
    så en nollrelaterad tröskel släpper igenom hela plattan: den skuggade raden
    mättes ut till cellens fulla bredd (0,408) medan den oskuggade raden under
    mättes till bläckets (0,219-0,395). Samma tabell fick alltså två olika
    bredder, och `forbesikta`s kolumnsammanslagningsregel — som jämför
    bboxbredd mot spaltbredd — larmade på var och en av de skuggade
    raderna (beslut.md D 5).

    Ett massivt ornament (linjeregeln) är också fyllt, men har ingen
    glyfkontrast: där sammanfaller bakgrund och topp, tröskeln hamnar vid
    plattans egen nivå och regeln behåller sin fulla bredd.
    """
    block = dark[top:bottom, lo:hi]
    prof = block.max(axis=0)
    if not len(prof) or not prof.max():
        return None
    if np.percentile(prof, SHADE_PERCENTILE) >= SHADE_SHARE * prof.max():
        # Bandet är satt på en tonplatta. Svärtan kan inte skilja plattan från
        # satsen — rastret når lika höga toppvärden — men KONTRASTEN kan, av
        # exakt samma skäl som `row_profile` mäter kontrast i y-led: en jämn
        # ton har låg spridning, en kolumn med bokstäver hög.
        contrast = block.std(axis=0)
        if contrast.max():
            # Tröskeln sätts mitt emellan profilens golv och tak, inte vid en
            # andel av taket: tonens egen spridning (uppmätt 19-25) ligger
            # långt över 8 % av satsens (65-69) och skulle annars ta med hela
            # plattan.
            level = (contrast.min()
                     + LOCAL_FRACTION * (contrast.max() - contrast.min()))
            hits = np.flatnonzero(contrast >= level)
            if len(hits):
                return lo + int(hits[0]), lo + int(hits[-1]) + 1
        # Ingen kontrast alls: ett massivt ornament, t.ex. linjeregeln. Det
        # mäts på svärtan nedan och behåller sin fulla bredd.
    hits = np.flatnonzero(prof >= MIN_DARKNESS_SHARE * prof.max())
    if not len(hits):
        return None
    return lo + int(hits[0]), lo + int(hits[-1]) + 1


def _edge_block(bands, height):
    """(antal sidhuvudsband, antal sidfotsband) — mätt på LUCKAN, inte läget.

    Ett fast kantband räcker inte som kriterium. Där satsytan börjar högt
    hamnar spalternas översta rad innanför de 8 procenten, hela raden mäts då
    om som en enda fullbreddsrad i sidhuvudzonen, och spalternas första element
    blir antingen utan bbox eller — värre — får grannradens box, ett steg fel
    (beslut.md D 1 och 2; ~16 respektive 7 sidor i del II).

    Det som verkligen skiljer ett sidhuvud från satsen är att det står FÖR SIG:
    under kolumntiteln ligger mer än ett radavstånd, mellan två textrader
    mindre. Blocket är därför det längsta prefix (respektive suffix) som ryms
    inom kantbandet OCH följs (föregås) av en lucka på minst en radhöjd.
    Hittas ingen sådan lucka finns inget sidhuvud — att låta zonen vara tom är
    alltid tillåtet.
    """
    median = _median_height(bands)
    limit = EDGE_GAP_FACTOR * median

    def block(order):
        n = 0
        for i in range(len(order) - 1):
            top, bottom = bands[order[i]][0], bands[order[i]][1]
            centre = (top + bottom) / 2 / height
            if not (centre < EDGE_BAND or centre > 1 - EDGE_BAND):
                break
            nxt = bands[order[i + 1]]
            gap = nxt[0] - bottom if order[i + 1] > order[i] else top - nxt[1]
            if gap >= limit:
                n = i + 1
        return n

    forward = list(range(len(bands)))
    return block(forward), block(forward[::-1])


def _segments(body):
    """Kroppens band grupperade i lodräta avsnitt, brutna vid stora luckor.

    Ett avsnitt är den yta som delar spaltindelning. Luckan mellan tvåspaltig
    löptext och en fullbredds tabell är flera radhöjder; luckan mellan två
    stycken är det inte.
    """
    if not body:
        return []
    heights = sorted(b - a for a, b, _ in body)
    gap = (heights[len(heights) // 2] or 1) * SEGMENT_GAP_FACTOR
    groups = [[body[0]]]
    for band in body[1:]:
        if band[0] - groups[-1][-1][1] > gap:
            groups.append([band])
        else:
            groups[-1].append(band)
    # Avsnitten TEGLAR ihop kroppen: gränsen läggs mitt i den brytande luckan i
    # stället för vid bandens egna kanter. Annars blir mellanrummen hål som
    # ingen spaltmätning tittar i, och en tryckt rad som helsidesprofilen
    # missar — en blek rad som bara finns i den ena spalten syns inte i en
    # profil som mäts över båda — går förlorad för gott. Uppmätt: s. 2 (sista
    # posten i var och en av innehållsförteckningens tre spalter) och s. 60
    # (tre rader). Teglingen kan inte ge dubbletter: avsnitten är disjunkta,
    # så varje bläckrad ligger i exakt ett av dem.
    #
    # Spaltindelningen mäts däremot på avsnittets EGET bläck, inte på det
    # teglade spannet. Drar man in grannens tomma yta i rännmätningen räcker
    # det med att den innehåller en fullbredds rad för att rännan ska fyllas:
    # spalterna hittas då inte, och vänster- och högerspaltens rader slås ihop
    # till gemensamma fullbreddsband (uppmätt på s. 62). Varje avsnitt är
    # alltså (mätspann, bläckspann).
    segments, top = [], body[0][0]
    for i, group in enumerate(groups):
        ink_top, ink_bottom = group[0][0], group[-1][1]
        bottom = (ink_bottom if i + 1 == len(groups)
                  else (ink_bottom + groups[i + 1][0][0]) // 2)
        segments.append((top, bottom, ink_top, ink_bottom))
        top = bottom
    return segments


def _columns(dark, top, bottom, width):
    """Spaltgränser som (lo, hi) — rännorna är breda tomma lodräta stråk."""
    prof = dark[top:bottom, :].mean(axis=0)
    if not prof.max():
        return [(0, width)]
    empty = prof < GUTTER_DARKNESS_SHARE * prof.max()
    gutters = [(a, b) for a, b in _runs(empty)
               if b - a >= MIN_GUTTER_WIDTH * width]
    blocks, cursor = [], 0
    for a, b in gutters:
        if a > cursor:
            blocks.append((cursor, a))
        cursor = b
    if cursor < width:
        blocks.append((cursor, width))
    blocks = [(a, b) for a, b in blocks if b - a >= MIN_COLUMN_WIDTH * width]
    return blocks or [(0, width)]


def _region_name(lo, hi, width):
    """Regionnamn ur blockets läge, inte ur dess index.

    Indexbaserad namngivning går sönder så fort spaltindelningen mäts per
    avsnitt: ett avsnitt som bara har text i vänsterspalten får ett enda block,
    och det blocket ska ändå heta `vänsterkolumn`. Namnen är desamma som
    transkriptionen använt i bok 1.
    """
    span = (hi - lo) / width
    centre = (lo + hi) / 2 / width
    if span > 0.7:
        return "sidbredd"
    if centre < 0.45:
        return "vänsterkolumn"
    if centre > 0.55:
        return "högerkolumn"
    return "mittkolumn"


def _box(x0, x1, top, bottom, width, height):
    """Normaliserad [x, y, bredd, höjd] med y från sidans NEDERKANT."""
    return [round(x0 / width, 6),
            round((height - bottom) / height, 6),
            round((x1 - x0) / width, 6),
            round((bottom - top) / height, 6)]


def measure_dark(dark):
    """Mät radboxar ur en svärtbild. Returnerar (rader, spalter).

    Bruten ut ur `measure_page` så att den går att testa på syntetiska bilder
    utan PDF — och så att kalibrering mot en känd sida inte kräver rendering.
    """
    height, width = dark.shape

    # Kroppens utsträckning avgörs först: sidhuvud och sidfot spänner över
    # spalterna och skulle annars fylla rännan så att spaltdetekteringen
    # misslyckas. Bandet i kantzonerna mäts sedan om, var zon för sig.
    page_bands = _merge_and_classify(
        _profile_bands(row_profile(dark), height))
    n_head, n_foot = _edge_block(page_bands, height)
    body = page_bands[n_head:len(page_bands) - n_foot or None]
    # Sidans radhöjd, mätt på kroppen. Den är referens för ALLA senare anrop
    # till _merge_and_classify, så att "hög" betyder hög mot sidans sats och
    # inte mot vad som råkar finnas i samma avsnitt.
    page_median = _median_height(body) if body else None

    rows = []
    body_top = min((top for top, _, _ in body), default=0)
    body_bottom = max((bottom for _, bottom, _ in body), default=height)

    def zon(top, bottom, region):
        """Mät om en kantzon mot SIN EGEN profil.

        Sidhuvud och sidfot måste mätas för sig. Mätt mot hela sidans profil
        drunknar de: golvet sätts som en andel av sidans mörkaste rad, alltså
        en brödtextrad över hela spaltbredden, och en ensam foliosiffra (~25 px
        av 1950) når aldrig dit. Alla foliosiffror och hela vattenstämpeln föll
        bort på det viset.
        """
        if bottom - top < 2:
            return
        prof = zone_profile(dark[top:bottom, :], ZONE_WINDOW * width)
        bands = [(a + top, b + top) for a, b in _profile_bands(prof, height)]
        for a, b, kind in _merge_and_classify(bands, page_median,
                                              noise_from_page=False):
            if a <= 0 or b >= height:
                continue  # renderingens egen bildkant, inte tryck
            extent = _extent(dark, a, b, 0, width)
            if extent and extent[1] - extent[0] >= MIN_ROW_WIDTH * width:
                rows.append({"region": region, "kind": kind,
                             "bbox": _box(extent[0], extent[1], a, b,
                                          width, height)})

    zon(0, body_top, "sidhuvud")

    columns = []
    for seg_top, seg_bottom, ink_top, ink_bottom in _segments(body):
        # Spaltindelningen mäts PER AVSNITT. På s. 61 är övre halvan tvåspaltig
        # löptext och nedre halvan en fullbredds tabell som fyller rännan — en
        # enda mätning för hela sidan ger då noll spalter och slår ihop
        # vänster- och högerspaltens rader till gemensamma band.
        for lo, hi in _columns(dark, ink_top, ink_bottom, width):
            region = _region_name(lo, hi, width)
            columns.append({"region": region,
                            "x": round(lo / width, 6),
                            "bredd": round((hi - lo) / width, 6),
                            "y": round((height - seg_bottom) / height, 6),
                            "höjd": round((seg_bottom - seg_top) / height, 6)})
            # Profilen tas över SPALTEN, inte sidan: en rad i vänsterspalten
            # syns inte i en profil som medelvärdesbildas över båda.
            prof = row_profile(dark[seg_top:seg_bottom, lo:hi])
            bands = [(a + seg_top, b + seg_top)
                     for a, b in _profile_bands(prof, height)]
            for top, bottom, kind in _merge_and_classify(bands, page_median):
                extent = _extent(dark, top, bottom, lo, hi)
                if extent:
                    rows.append({"region": region, "kind": kind,
                                 "bbox": _box(extent[0], extent[1], top,
                                              bottom, width, height)})

    zon(body_bottom, height, "sidfot")

    # Ingen sortering: avsnitt uppifrån och ned, spalter vänster till höger och
    # rader uppifrån och ned emitteras redan i läsordning — hela vänsterspalten
    # före hela högerspalten, precis som transkriptionskontraktet kräver.
    return rows, columns


def summarise(rows):
    """Sidsammanfattning — och en varning när mätningen inte går att lita på.

    En illustrationssida (pärmen, s. 66 i del I) ger hundratals band som inte
    är rader alls: bildens toner bryts upp av profilen precis som sats. Det
    syns på att grafikbanden och fullbreddsbanden dominerar. Flaggan säger
    "läs PNG:n själv", den påstår inget om innehållet.
    """
    body = [r for r in rows if r["region"] not in ("sidhuvud", "sidfot")]
    graphic = [r for r in body if r["kind"] == KIND_GRAPHIC]
    full = [r for r in body if r["region"] == "sidbredd"]
    andel = (len(graphic) + len(full)) / len(body) if body else 0.0
    return {"rader": len([r for r in rows if r["kind"] == KIND_ROW]),
            "grafik": len([r for r in rows if r["kind"] == KIND_GRAPHIC]),
            "dominerande_grafik": bool(body) and andel > 0.5}


def measure_page(page, measure_dim=MEASURE_DIM):
    """Rendera sidan i mäthög upplösning och mät radboxarna."""
    scale = measure_dim / max(page.rect.width, page.rect.height)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale),
                          colorspace=fitz.csGRAY)
    gray = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.stride)[:, :pix.width]
    rows, columns = measure_dark(darkness(gray))
    return {"rows": rows, "columns": columns,
            "sammanfattning": summarise(rows),
            "source": {"measured_by": "pipeline.rows.measure_page",
                       "pixels": [pix.width, pix.height]}}


def measure(pdf_path, workdir, pages=None, force=False, measure_dim=MEASURE_DIM):
    """Skriv page_NNN.radboxar.json för varje sida. Idempotent."""
    log = setup_logging(workdir)
    m = Manifest.load(workdir)
    doc = fitz.open(pdf_path)
    results = []
    try:
        for no in m.page_numbers():
            if pages and no not in pages:
                continue
            target = page_file(workdir, no, "radboxar.json")
            if target.is_file() and not force:
                results.append((no, None))
                continue
            data = measure_page(doc[no - 1], measure_dim=measure_dim)
            data["page"] = no
            atomic_write_json(target, data)
            results.append((no, data["sammanfattning"]))
    finally:
        doc.close()
    skrivna = [n for n, c in results if c is not None]
    log.info("radboxar: %d nya, %d fanns redan",
             len(skrivna), len(results) - len(skrivna))
    return results
