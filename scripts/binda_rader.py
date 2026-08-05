#!/usr/bin/env python3
"""Binder element till uppmätta rader på sidor vars geometri mätts om.

Bakgrunden är del II:s BQ-001. Tio sidor mättes fel därför att en
helsidesbred illustration fyllde spaltrännan (`pipeline/rows.py`, nu lagad).
Efter ommätningen finns rätt rader — men elementen pekar inte på dem, och utan
`source.rader` räknar pipelinen aldrig fram någon `bbox`. Läsexporten fogar då
inte ihop några stycken: varje TRYCKT rad blir ett eget stycke i `bok.md`
(AGENTER.md Regel 9).

Bindningen kallades först ett transkriptionsjobb. Den bedömningen byggde på
att elementen var stycken; de är i själva verket **en per tryckt rad** — det är
vad transkriptionskontraktet föreskriver för löptext. Då är bindningen en
ordningsbevarande matchning mellan två listor som båda står i läsordning, och
den går att MÄTA:

* Ett element täcker nästan alltid exakt en rad. På bokens 53 facitsidor är
  3 424 av 3 482 bindningar enradiga; behållarna (`list`, `table`, `statblock`)
  är undantagen.
* Radens uppmätta BREDD är proportionell mot elementets teckenlängd. Över
  2 771 facitrader ligger tecken-per-breddenhet inom ±12,5 % för 90 % av
  raderna. En felskjuten tilldelning bryter det sambandet direkt.
* Ungefär en femtedel av de uppmätta raderna är inte text alls utan
  illustrationsband. De måste få stå obundna — det är därför bandöverhoppning
  är tillåten och kostar.

Skriptet löser detta med dynamisk programmering per region: elementen tas i
ordning, varje element tilldelas ett sammanhängande radintervall, band får
hoppas över mot en straffkostnad, och den billigaste tilldelningen vinner.

Tre spärrar hindrar att en gissning smyger in som data:

* **Förskjutningsprovet.** Varje körning av rad-efter-rad-bundna element prövas
  mot att skjutas ett steg åt vardera hållet. Blir det inte mätbart dyrare är
  körningens läge inte uppmätt utan bara rimligt, och den binds inte. Det är
  den bärande spärren: 62 % av alla avvikelser mot facit var hela block ett
  steg ur led.
* **Marginalkravet.** Näst bästa tilldelningen för varje enskilt element räknas
  också fram ur en framåt- och en bakåttabell. Ligger den för nära lämnas
  elementet obundet.
* **Regionkravet.** Ett element binds bara till rader i sin egen region. Går
  inte regionerna ihop (elementet säger `tvåspaltstabell`, mätningen känner
  bara `vänsterkolumn`) avstår skriptet från regionen i stället för att flytta
  elementet.

Utfallet mot bokens 53 facitsidor (3 473 element) med spärrarna på:
identiska 64 %, avvikande 2,8 %, obundna 33 %. Av de 96 avvikelserna passar
18 TRYCKET bättre än facit gör och 9 sämre; resten går inte att skilja åt på
bredden. Verktyget är alltså ungefär lika träffsäkert som den transkription
det jämförs med, och lämnar hellre en lucka än sätter en box.

Torrkörning är default. Utvärdera alltid mot facit först:

    python3 scripts/binda_rader.py <arbete/slug> --utvardera
    python3 scripts/binda_rader.py <arbete/slug> --sidor 1,8,20
    python3 scripts/binda_rader.py <arbete/slug> --sidor 1,8,20 --verkstall
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

# Elementtyper som bär sin text i `data` och därför kan spänna flera rader.
BEHALLARE = {"list", "table", "statblock"}

# Tecken per breddenhet, per elementtyp, mätt ur bokens egna facitsidor. Graden
# skiljer sig kraftigt mellan brödtext och rubrik, och en enda skala gjorde
# rubrikerna gratis att flytta — då sköts hela regionen ett steg ur led utan
# att kostnaden märkte det. Talet här är bara ett förhållande mot brödtextens
# skala, som mäts per bok; toleransen är typens uppmätta spridning.
#
# Faktorn och toleransen är p50 respektive p90 av det symmetriska felet, mätt
# över bokens facitsidor:
#
#   typ              n   faktor   p50    p90
#   paragraph     2733    1,000   0,05   0,13
#   heading        207    0,625   0,08   0,60
#   boxed_text     207    1,017   0,04   0,11
#   list_item       39    1,123   0,03   0,12
#   statblock       24    0,552   0,14   0,36
#   table           12    0,523   0,45   0,79
#
# Behållarnas faktor ligger långt under ett därför att deras teckenlängd
# räknas ur nästlad data — nycklar, etiketter och avgränsare räknas med fast
# de aldrig sätts. Faktorn mäts därför per typ i stället för att antas.
#
# Toleransen måste ligga NÄRA den uppmätta spridningen. Med de första, alltför
# generösa värdena (0,30 för brödtext) kostade en förskjutning ingenting alls:
# felet gick från 0,05 till 0,10 och båda låg under toleransen, så hela
# förskjutningsprovet blev tandlöst och s. 8:s verifierat riktiga bindning
# föll som obevisad.
#
# `toc_entry`, `index_entry` och `page_artifact` mättes till p90 mellan 0,66
# och 6,2 — punktledare och breda kolumntitlar gör bredden oanvändbar där. De
# får ingen breddkostnad alls; ordningen är det enda som binder dem.
TYPSKALA = {
    "paragraph": (1.000, 0.15),
    "boxed_text": (1.017, 0.14),
    "list_item": (1.123, 0.15),
    "list": (1.123, 0.30),
    "table_note": (1.112, 0.45),
    "table_caption": (1.05, 0.45),
    "heading": (0.625, 0.55),
    "statblock": (0.552, 0.40),
    "table": (0.523, 0.80),
}

# Kostnad för att lämna ett uppmätt band obundet. Ett band som SER UT som en
# textrad är dyrt att hoppa över; ett band med avvikande höjd är ett
# illustrationsband och kostar nästan inget. Det är den skillnaden som gör att
# en helsidesbild kan ligga mitt i spalten utan att skjuta bindningen ur led.
HOPP_TEXT = 0.60
HOPP_GRAFIK = 0.05

# Höjdintervall, som andel av regionens medianhöjd, där ett band räknas som en
# textrad. På facitsidorna ligger 98 % av de bundna raderna inom det.
TEXT_LO, TEXT_HI = 0.55, 1.70

# Ett band räknas som text bara om det dessutom står i SATSENS RADTAKT: minst
# ett av avstånden till grannbandet ligger inom PITCH_TOL av regionens
# mediantakt. Höjden ensam räckte inte — på s. 8 fick fem av illustrationens
# arton band en höjd inom textintervallet, och de fem gjorde det dyrt nog att
# hoppa över bilden att DP:n hellre lade brödtexten PÅ den och lät ett
# list-element svälja hela den riktiga textspalten.
PITCH_TOL = 0.28

# ...och bara om bandet inte är för SVART. En tryckt textrad har mellan en
# fjärdedel och drygt en tredjedel svarta bildpunkter inom sin box; en
# illustrationspanel har 0,7–0,95. Mätt över bokens 4 097 bundna facitrader
# ligger 99 % under 0,54, medan de obundna sträcker sig till 1,00. Tröskeln
# 0,60 felklassar 0,32 % av de äkta textraderna.
#
# Det här är det enda måttet i skriptet som läser SIDBILDEN, och det är också
# det avgörande: på s. 8 skiljer varken höjd eller bredd illustrationens band
# från spaltens rader, men svärtan gör det utan tvekan (0,26–0,43 mot
# 0,53–0,95).
SVARTA_GRAFIK = 0.60

# Straff för att BINDA ett element till ett band som svärtan pekat ut som
# grafik. Att bara göra sådana band billiga att hoppa över räckte inte: en
# illustrationspanel ger band som är precis lika breda som spaltens rader, så
# breddkostnaden för att lägga brödtext ovanpå bilden var noll. På s. 8 lade
# DP:n därför sjutton paragrafer på illustrationen och lät ett list-element
# svälja den riktiga textspalten. Straffet är ingen spärr — ett statblock med
# tunga linjer får vara svart — men det ska kosta mer än att hoppa över en
# hel bild.
SVART_STRAFF = 2.0

# Relativ breddavvikelse räknas inte högre än så här. Taket finns för att en
# enda grov avvikelse inte ska dränka allt annat, men det måste ligga klart
# över vad det kostar att hoppa över en illustration — annars blir det billigt
# att lägga en behållare över en hel spalt.
MAX_KOSTNAD = 6.0

# Kostnad för att lämna ett ELEMENT utan rad. Mätningen missar ibland en
# tryckt rad — en kort sista rad i ett stycke kan gå upp i ett angränsande
# illustrationsband eller falla under tröskeln. Kravet att varje element MÅSTE
# få en rad var det enskilt värsta felet i den första versionen: en missad
# mätrad sköt då hela regionen ett steg, och på s. 37 blev 63 av 80 element fel
# därför att `perfekta.` saknade band. Straffet ligger över hoppstraffet —
# normalfallet är att elementet har en rad — men under vad en genomskjuten
# region kostar.
ELEMENT_UTAN_RAD = 1.0

# Marginal mot näst bästa lösningen för ETT element: hur mycket dyrare hela
# regionen blir om just det elementet tvingas någon annanstans. Marginalen
# mäts per element och inte per region — en region kan ha femtio entydiga
# bindningar och tre tvetydiga, och då är det de tre som ska stå obundna.
# Nivån är vald ur en mätning, inte gissad. Marginalkravet svept mot bokens
# 53 facitsidor (3 473 element):
#
# Marginalen ensam räckte aldrig som spärr — den mäter om ETT element kan
# flyttas, och i en spalt med likbreda rader flyttas ett block alltid som en
# kropp. Därför är den bara halva villkoret; se FORSKJUTNING nedan, som mäter
# körningen. Nivån är satt i ett svep mot bokens facitsidor och plockar bort
# ungefär en fjärdedel av felen mot två procent färre bindningar.
MARGINAL = 0.15

# Hur mycket dyrare en körning måste bli av att skjutas ett steg för att
# räknas som uppmätt. Se `_tal_forskjutning`. Detta är den bärande spärren:
# 62 % av alla avvikelser mot facit var hela block ett steg ur led, och det är
# precis vad måttet prövar. En körning utan någon rad vars bredd förändras av
# ett steg — en kort sista rad, en centrerad rubrik, en bildgräns — har inget
# som håller den på plats och binds inte.
FORSKJUTNING = 0.50


def _rader(radboxar):
    return radboxar.get("rows") or []


def _region(el):
    return (el.get("source") or {}).get("region")


def _djuplangd(v):
    """Summan av all teckenlängd i en godtyckligt nästlad datastruktur.

    Behållarna bär sin text på olika sätt: `list` i `items`, `table` i
    `headers`/`rows`, `statblock` i `stats`/`skills`/`weapons`/`other`. En
    uppräkning av kända nycklar missade statblocken, som därmed fick längden 0
    och blev GRATIS att sträcka över hur många band som helst — på s. 30 svalde
    ett statblock 40 rader i stället för 14.
    """
    if isinstance(v, str):
        return len(v)
    if isinstance(v, dict):
        return sum(_djuplangd(k) + _djuplangd(x) for k, x in v.items())
    if isinstance(v, (list, tuple)):
        return sum(_djuplangd(x) for x in v)
    if v is None:
        return 0
    return len(str(v))


def _textlangd(el):
    """Elementets teckenlängd, också när texten bor i `data`."""
    t = el.get("text") or ""
    if t:
        return len(t)
    return _djuplangd(el.get("data") or {})


def _skala(sidor):
    """Tecken per breddenhet, mätt ur de sidor som redan har korrekt bindning.

    Skalan hämtas ur BOKEN, inte ur en konstant: den beror på sättningens grad
    och på hur mätningen normaliserar bredden. Saknas facit faller vi tillbaka
    på de sidor som ändå har enstaka bindningar.
    """
    prov = []
    for els, rows in sidor:
        for el in els:
            rr = (el.get("source") or {}).get("rader") or []
            if len(rr) != 1 or el.get("type") != "paragraph":
                continue
            i = rr[0]
            if not (0 <= i < len(rows)):
                continue
            b = rows[i].get("bbox") or []
            if len(b) == 4 and b[2] > 0.05:
                prov.append(_textlangd(el) / b[2])
    return statistics.median(prov) if len(prov) >= 30 else None


def _radkostnad(el, rows, a, b, skala, svarta=None):
    """Kostnaden för att låta `el` täcka raderna [a, b).

    None betyder omöjligt: ett element som inte är en behållare täcker per
    transkriptionskontraktet exakt EN tryckt rad.
    """
    n = b - a
    typ = el.get("type")
    if typ not in BEHALLARE and n != 1:
        return None
    faktor, tolerans = TYPSKALA.get(typ, (None, None))
    if faktor is None:
        return 0.0
    bredd = 0.0
    for j in range(a, b):
        box = rows[j].get("bbox") or []
        if len(box) != 4:
            return None
        bredd += box[2]
    if bredd <= 0:
        return None
    svart = 0.0
    if svarta:
        svart = SVART_STRAFF * sum(
            1 for j in range(a, b)
            if svarta[j] is not None and svarta[j] >= SVARTA_GRAFIK)
    väntat = _textlangd(el)
    if väntat == 0:
        return svart
    väntad_bredd = skala * faktor * bredd
    # Felet mäts mot det MINSTA av de två talen, så att spänna över för många
    # rader kostar lika mycket som att spänna över för få. Med den förväntade
    # bredden i nämnaren blev ett övertag aldrig dyrare än 1,0 — ett
    # list-element kunde då lägga sig över en hel spalt nästan gratis.
    fel = abs(väntat - väntad_bredd) / max(1e-9, min(väntat, väntad_bredd))
    # Toleransen är typens egen uppmätta spridning: inom den kostar avvikelsen
    # ingenting, utanför växer den linjärt.
    return min(max(0.0, fel - tolerans), MAX_KOSTNAD) + svart


def _svarta(rows, png):
    """Andelen svarta bildpunkter innanför varje bands box, eller None.

    Saknas bilden eller Pillow går måttet inte att räkna — då faller
    bandklassningen tillbaka på höjd och radtakt, vilket är sämre men aldrig
    farligt: resultatet blir fler obundna element, inte fler felbundna.
    """
    if not png or not Path(png).exists():
        return [None] * len(rows)
    try:
        from PIL import Image
    except ImportError:
        return [None] * len(rows)
    im = Image.open(png).convert("L").point(lambda v: 255 if v < 128 else 0)
    W, H = im.size
    ut = []
    for r in rows:
        box = r.get("bbox") or []
        if len(box) != 4:
            ut.append(None)
            continue
        x, y, w, h = box
        # y räknas från sidans NEDERKANT
        v, hö = int(x * W), int((x + w) * W)
        upp, ner = int((1 - y - h) * H), int((1 - y) * H)
        if hö <= v or ner <= upp:
            ut.append(None)
            continue
        bit = im.crop((v, upp, hö, ner))
        ut.append(bit.histogram()[255] / (bit.width * bit.height))
    return ut


def _hoppstraff(rows, svarta=None):
    """Kostnaden för att lämna varje enskilt band obundet.

    Höjden är det som skiljer en tryckt textrad från ett illustrationsband:
    på facitsidorna ligger 98 % av de bundna raderna inom 0,55–1,70 gånger
    regionens medianhöjd, medan de obundna sprider sig från 0,12 till 3,9.
    Ett bandsom ser ut som text ska alltså vara dyrt att hoppa över — annars
    kan DP:n köpa sig ur ett läge genom att låta en riktig rad falla bort, och
    resten av regionen skjuts ett steg ur led.
    """
    boxar = [r.get("bbox") if len(r.get("bbox") or []) == 4 else None
             for r in rows]
    höjder = [b[3] for b in boxar if b]
    if not höjder:
        return [HOPP_TEXT] * len(rows)
    med = statistics.median(höjder)

    # Radtakten mäts som avståndet mellan intilliggande bands överkanter.
    # y räknas från sidans nederkant, så takten är y[j] - y[j+1].
    takter = [boxar[j][1] - boxar[j + 1][1]
              for j in range(len(boxar) - 1)
              if boxar[j] and boxar[j + 1] and boxar[j][1] > boxar[j + 1][1]]
    takt = statistics.median(takter) if takter else None

    def i_takt(j):
        if takt is None or takt <= 0:
            return True
        for a, b in ((j - 1, j), (j, j + 1)):
            if 0 <= a and b < len(boxar) and boxar[a] and boxar[b]:
                d = boxar[a][1] - boxar[b][1]
                if d > 0 and abs(d - takt) / takt <= PITCH_TOL:
                    return True
        return False

    ut = []
    for j, box in enumerate(boxar):
        if not box or med <= 0:
            ut.append(HOPP_TEXT)
            continue
        rel = box[3] / med
        sv = (svarta or [None] * len(boxar))[j]
        text = (TEXT_LO <= rel <= TEXT_HI and i_takt(j)
                and not (sv is not None and sv >= SVARTA_GRAFIK))
        ut.append(HOPP_TEXT if text else HOPP_GRAFIK)
    return ut


def _losning(els, rows, skala, max_spann, svarta=None):
    """Billigaste tilldelningen med en marginal per bindning.

    Returnerar `(kostnad, [(elementindex, [radindex], marginal)])`.

    Marginalen är skillnaden mellan den optimala totalkostnaden och den
    billigaste lösning där just det elementet tilldelas NÅGOT ANNAT
    radintervall. Den räknas ur en framåt- och en bakåttabell, så varje
    alternativ värderas mot hela regionen och inte bara mot sitt eget bidrag.
    Det är skillnaden mot att jämföra två färdiga helhetslösningar: en region
    kan vara entydig på alla element utom ett, och då ska bara det ena falla.
    """
    m, k = len(els), len(rows)
    INF = float("inf")
    hopp = _hoppstraff(rows, svarta)
    hopp_svarta = svarta
    # tvingad[i]: föregående element slutar på bindestreck, alltså mitt i ett
    # ord. Då MÅSTE element i ligga på raden omedelbart efter. Villkoret är
    # kontrollerat mot facit: 218 av 220 fall håller, och de två undantagen är
    # facits egna fel (två element bundna till samma rad).
    tvingad = [False] * m
    for i in range(1, m):
        t = els[i - 1].get("text") or ""
        tvingad[i] = t.endswith("-") and not t.endswith("--")

    # svans[j] = kostnaden för att lämna alla band från j och framåt obundna
    svans = [0.0] * (k + 1)
    for j in range(k - 1, -1, -1):
        svans[j] = svans[j + 1] + hopp[j]

    # bak[i][j][f] = billigaste sättet att placera elementen i.. från rad j,
    # där f=1 betyder att element i är bundet att börja exakt på rad j.
    bak = [[[INF, INF] for _ in range(k + 1)] for _ in range(m + 1)]
    val = [[[None, None] for _ in range(k + 1)] for _ in range(m + 1)]
    for j in range(k + 1):
        bak[m][j][0] = bak[m][j][1] = svans[j]
    for i in range(m):
        # slut på band: resten av elementen står utan rad
        bak[i][k][0] = bak[i][k][1] = ELEMENT_UTAN_RAD * (m - i)

    kost = {}   # (i, j, n) -> kostnad; behövs igen när marginalerna räknas

    def nästa(i, j):
        """Tabellindex för elementet efter en bindning som slutar vid rad j."""
        return bak[i + 1][j][1 if i + 1 < m and tvingad[i + 1] else 0]

    for i in range(m - 1, -1, -1):
        for j in range(k - 1, -1, -1):
            bind_bäst, bind_val = INF, None
            for n in range(1, min(max_spann, k - j) + 1):
                c = _radkostnad(els[i], rows, j, j + n, skala, hopp_svarta)
                if c is None:
                    continue
                kost[(i, j, n)] = c
                t = c + nästa(i, j + n)
                if t < bind_bäst:
                    bind_bäst, bind_val = t, ("bind", n)
            # f=1: elementet måste börja här, alltså varken hopp eller utan
            bak[i][j][1] = bind_bäst
            val[i][j][1] = bind_val
            # f=0: bandet får hoppas över, elementet får stå utan rad
            b0, v0 = bak[i][j + 1][0] + hopp[j], ("hopp", None)
            # ett element utan rad bryter kedjan — efterföljaren binds inte
            t = ELEMENT_UTAN_RAD + bak[i + 1][j][0]
            if t < b0:
                b0, v0 = t, ("utan", None)
            if bind_bäst < b0:
                b0, v0 = bind_bäst, bind_val
            bak[i][j][0], val[i][j][0] = b0, v0
    if bak[0][0][0] == INF:
        return INF, []

    # Framåttabellerna speglar bakåttabellen och bär samma tvångsvillkor —
    # annars skulle marginalen värdera alternativ som bryter ett avstavat ord
    # som om de vore tillåtna, och de avstavade kedjorna skulle aldrig få den
    # höga marginal de faktiskt har.
    #
    #   bunden[i][j] = elementen ..i-1 ligger i raderna ..j-1 och element i-1
    #                  är BUNDET med slut exakt på rad j-1
    #   fri[i][j]    = elementen ..i-1 ligger i raderna ..j-1, hur som helst
    bunden = [[INF] * (k + 1) for _ in range(m + 1)]
    fri = [[INF] * (k + 1) for _ in range(m + 1)]
    for j in range(k + 1):
        fri[0][j] = svans[0] - svans[j]

    def start(i, j):
        """Kostnaden fram till att element i får börja på rad j."""
        return bunden[i][j] if (i < m and tvingad[i]) else fri[i][j]

    for i in range(1, m + 1):
        for j in range(1, k + 1):
            b = INF
            for n in range(1, min(max_spann, j) + 1):
                c = kost.get((i - 1, j - n, n))
                if c is None:
                    continue
                t = start(i - 1, j - n) + c
                if t < b:
                    b = t
            bunden[i][j] = b
        fri[i][0] = INF if tvingad[i - 1] else fri[i - 1][0] + ELEMENT_UTAN_RAD
        for j in range(1, k + 1):
            b = min(bunden[i][j], fri[i][j - 1] + hopp[j - 1])
            if not tvingad[i - 1]:
                b = min(b, fri[i - 1][j] + ELEMENT_UTAN_RAD)
            fri[i][j] = b
    fram = fri

    optimal = bak[0][0][0]
    ut, i, j, f = [], 0, 0, 0
    while i < m and j < k:
        steg = val[i][j][f]
        if steg is None:
            break
        slag, n = steg
        if slag == "hopp":
            j += 1
            continue
        if slag == "utan":
            i += 1
            f = 0
            continue
        alt = INF
        for jj in range(k):
            fj = start(i, jj)
            if fj == INF:
                continue
            for nn in range(1, min(max_spann, k - jj) + 1):
                if jj == j and nn == n:
                    continue
                c = kost.get((i, jj, nn))
                if c is None:
                    continue
                t = fj + c + nästa(i, jj + nn)
                if t < alt:
                    alt = t
        # ...eller att elementet inte får någon rad alls. Ett element mitt i en
        # avstavad kedja får inte falla bort, så det alternativet finns inte.
        if not tvingad[i] and not (i + 1 < m and tvingad[i + 1]):
            alt = min(alt, fri[i][j] + ELEMENT_UTAN_RAD + bak[i + 1][j][0])
        ut.append((i, list(range(j, j + n)), alt - optimal))
        i += 1
        j += n
        f = 1 if i < m and tvingad[i] else 0
    return optimal, ut


def binda_sida(els, rows, skala, max_spann=80, png=None):
    """Bind en sidas element till dess uppmätta rader, region för region.

    Returnerar `(bindningar, anmarkningar)` där bindningar är
    `{elementindex: [radindex]}`.
    """
    bindningar, anm = {}, []
    svarta = _svarta(rows, png)
    regioner = []
    for r in rows:
        if r.get("region") not in regioner:
            regioner.append(r.get("region"))
    elregioner = []
    for el in els:
        if _region(el) not in elregioner:
            elregioner.append(_region(el))

    for reg in elregioner:
        eidx = [i for i, el in enumerate(els) if _region(el) == reg]
        ridx = [j for j, r in enumerate(rows) if r.get("region") == reg]
        if not eidx:
            continue
        if not ridx:
            anm.append("region %r finns hos %d element men inte i mätningen — "
                       "lämnad obunden" % (reg, len(eidx)))
            continue
        delels = [els[i] for i in eidx]
        delrows = [rows[j] for j in ridx]
        delsv = [svarta[j] for j in ridx]
        _, lösn = _losning(delels, delrows, skala, max_spann, delsv)
        if not lösn:
            anm.append("region %r: ingen tilldelning gick att räkna fram"
                       % (reg,))
            continue
        svaga = 0
        # Varje körning prövas mot en förskjutning ett steg åt vardera hållet.
        bevis = {}
        jämnt = (len(lösn) == len(delels)
                 and sum(len(rr) for _i, rr, _m in lösn) == len(delrows))
        körningar = _kor(lösn)
        klar = []
        for körning in körningar:
            b = _tal_forskjutning(delels, delrows, skala, delsv, körning, jämnt)
            klar.append(b >= FORSKJUTNING)
            for i, _rr, _m in körning:
                bevis[i] = b
        # En körning som inte klarar förskjutningsprovet kan ändå vara FASTKILAD:
        # kan den inte flyttas åt något håll utan att krocka med en körning som
        # redan är bevisad, eller med regionens kant, finns det inget alternativ
        # kvar att förväxla den med. Kilningen sprider sig, så den räknas om
        # tills inget mer ändras. Det var så s. 8:s högerspalt gick att avgöra:
        # dess åtta första rader har inga bredder som skiljer sig åt, men de
        # ligger mot spaltens överkant och stöter nedåt direkt mot en bevisad
        # körning.
        ändrat = True
        while ändrat:
            ändrat = False
            for q, körning in enumerate(körningar):
                if klar[q]:
                    continue
                först, sist = körning[0][1][0], körning[-1][1][-1]
                vänster = först == 0 or (q > 0 and klar[q - 1]
                                         and körningar[q - 1][-1][1][-1] == först - 1)
                höger = sist == len(delrows) - 1 or (
                    q + 1 < len(körningar) and klar[q + 1]
                    and körningar[q + 1][0][1][0] == sist + 1)
                if vänster and höger:
                    klar[q] = ändrat = True
                    for i, _rr, _m in körning:
                        bevis[i] = FORSKJUTNING
        utan = len(delels) - len(lösn)
        if utan:
            anm.append("region %r: %d av %d element fick ingen rad — mätningen "
                       "saknar band där" % (reg, utan, len(delels)))
        for i, rr, marginal in lösn:
            if bevis.get(i, 0.0) < FORSKJUTNING or marginal < MARGINAL:
                svaga += 1
                continue
            bindningar[eidx[i]] = [ridx[j] for j in rr]
        if svaga:
            anm.append("region %r: %d av %d element ligger i en körning som "
                       "går att skjuta ett steg lika billigt — lämnade obundna "
                       "för advokaten" % (reg, svaga, len(lösn)))
    return bindningar, anm


def _kor(losn):
    """Dela lösningen i körningar av element som ligger på rad efter rad.

    En körning är den enhet som faktiskt kan vara fel: felen är nästan aldrig
    ett enskilt element på villovägar utan ett helt block som ligger ett steg
    ur led. Av 291 avvikelser mot facit var 180 just ±1 på hela block.
    """
    ut = []
    for post in losn:
        if ut and post[1][0] == ut[-1][-1][1][-1] + 1:
            ut[-1].append(post)
        else:
            ut.append([post])
    return ut


def _tal_forskjutning(els, rows, skala, svarta, korning, jamnt=True):
    """Hur mycket dyrare körningen blir om den skjuts ett steg åt något håll.

    Det här är körningens egen bevisbörda. En körning där varje rad är lika
    bred som grannen kan skjutas gratis och är alltså inte uppmätt utan bara
    rimlig; en körning som innehåller en kort sista rad, en centrerad rubrik
    eller en illustrationsgräns kan det inte. Det senare är en mätning.

    Ligger körningen mot regionens båda kanter går den inte att skjuta alls.
    Det räknas som bevis BARA om regionen i övrigt går jämnt ut — varje
    element har fått en rad och varje rad ett element. Finns det ett element
    utan rad kunde det ha stått var som helst i körningen, och då är
    kantläget inget bevis utan bara brist på alternativ. Det var precis fällan
    på indexsidan s. 63: punktledarna gör alla rader lika breda, mätningen har
    färre band än poster, och körningen fyllde regionen från kant till kant
    med två poster obundna — den såg bevisad ut och låg två steg fel.
    """
    bas = 0.0
    for i, rr, _m in korning:
        c = _radkostnad(els[i], rows, rr[0], rr[-1] + 1, skala, svarta)
        if c is None:
            return 0.0
        bas += c
    sämst = float("inf")
    for steg in (-1, 1):
        tot, möjligt = 0.0, True
        for i, rr, _m in korning:
            a, b = rr[0] + steg, rr[-1] + 1 + steg
            if a < 0 or b > len(rows):
                möjligt = False
                break
            c = _radkostnad(els[i], rows, a, b, skala, svarta)
            if c is None:
                möjligt = False
                break
            tot += c
        if möjligt:
            sämst = min(sämst, tot - bas)
    if sämst == float("inf") and not jamnt:
        return 0.0
    return sämst


def _union(rows, idx):
    boxar = [rows[j].get("bbox") for j in idx if (rows[j].get("bbox") or None)]
    boxar = [b for b in boxar if len(b) == 4]
    if not boxar:
        return None
    x0 = min(b[0] for b in boxar)
    y0 = min(b[1] for b in boxar)
    x1 = max(b[0] + b[2] for b in boxar)
    y1 = max(b[1] + b[3] for b in boxar)
    return [round(x0, 6), round(y0, 6), round(x1 - x0, 6), round(y1 - y0, 6)]


def _lasin(workdir):
    sidor = {}
    for f in sorted((workdir / "pages").glob("page_*.final.json")):
        n = int(f.name[5:8])
        rb = workdir / "pages" / ("page_%03d.radboxar.json" % n)
        if not rb.exists():
            continue
        png = workdir / "pages" / ("page_%03d.png" % n)
        sidor[n] = (f, json.loads(f.read_text(encoding="utf-8")),
                    _rader(json.loads(rb.read_text(encoding="utf-8"))),
                    png if png.exists() else None)
    return sidor


def _domare(el, rows, facit, mitt, skala, svarta):
    """Vilken av två bindningar som passar TRYCKET bäst: 'mitt', 'facit' — eller
    `None` när måttet inte kan skilja dem åt.

    Utan den här domen är utvärderingen missvisande. Facit är en tidigare
    transkription, inte sanning: i del II binder facit sidhuvudet `SPELLEDARENS
    UPPGIFT` till rad 60 mitt på s. 6, och element 52 till rad 1 på s. 17. En
    ren agreement-siffra hade räknat de fallen som verktygets fel. Domaren
    använder samma uppmätta breddsamband som bindningen själv — det är inte ett
    oberoende mått, men det är ett mått, och när trycket säger emot facit går
    det att se.
    """
    a = _radkostnad(el, rows, facit[0], facit[-1] + 1, skala, svarta)
    b = _radkostnad(el, rows, mitt[0], mitt[-1] + 1, skala, svarta)
    a = MAX_KOSTNAD * 10 if a is None else a
    b = MAX_KOSTNAD * 10 if b is None else b
    if abs(a - b) < 1e-9:
        return None
    return "mitt" if b < a else "facit"


def utvardera(sidor, skala):
    """Kör bindningen på sidor som REDAN har facit och redovisa träffsäkerhet.

    Det här är skriptets existensberättigande: en tilldelning som inte kan
    återskapa en känd bindning får inte skriva en okänd.

    Men avvikelsesiffran ensam duger inte som betyg, för facit är en tidigare
    transkription och inte sanning. Varje avvikelse ställs därför inför
    `_domare` och redovisas som vem av de två som passar trycket bäst. Det är
    den siffran som avgör om verktyget får köras skarpt — inte hur ofta det
    håller med.
    """
    rätt = fel = utan = 0
    dom = {"mitt": 0, "facit": 0, None: 0}
    värst = []
    for n, (_, d, rows, png) in sorted(sidor.items()):
        els = d.get("elements") or []
        facit = {i: rr for i, el in enumerate(els)
                 if (rr := (el.get("source") or {}).get("rader"))}
        if len(facit) < 10:
            continue
        rensade = []
        for el in els:
            kopia = dict(el)
            s = dict(kopia.get("source") or {})
            s.pop("rader", None)
            s.pop("bbox", None)
            kopia["source"] = s
            rensade.append(kopia)
        bind, _ = binda_sida(rensade, rows, skala, png=png)
        svarta = _svarta(rows, png)
        sid_fel = 0
        for i, rr in facit.items():
            if i not in bind:
                utan += 1
            elif bind[i] == rr:
                rätt += 1
            else:
                fel += 1
                sid_fel += 1
                dom[_domare(els[i], rows, rr, bind[i], skala, svarta)] += 1
        if sid_fel:
            värst.append((sid_fel, n, len(facit)))
    tot = rätt + fel + utan
    print("Utvärdering mot facit: %d element på %d sidor" % (tot, len(sidor)))
    if tot:
        print("  identiska med facit : %5d (%.1f %%)" % (rätt, 100 * rätt / tot))
        print("  AVVIKANDE bindning  : %5d (%.1f %%)" % (fel, 100 * fel / tot))
        print("  lämnade obundna     : %5d (%.1f %%)" % (utan, 100 * utan / tot))
    for antal, n, m in sorted(värst, reverse=True)[:10]:
        print("  s. %3d: %d av %d element avviker" % (n, antal, m))
    if fel:
        print("\nAvvikelserna dömda mot trycket (facit är inte sanning):")
        print("  verktyget passar trycket bättre : %5d" % dom["mitt"])
        print("  FACIT passar bättre             : %5d" % dom["facit"])
        print("  går inte att skilja åt          : %5d" % dom[None])
        if dom["facit"] > dom["mitt"]:
            print("\n  VARNING: facit vinner oftare än verktyget. Kör det inte "
                  "skarpt förrän kostnadsmåttet är rättat.")
    # Utfallet är godkänt när verktyget inte förlorar mot facit oftare än det
    # vinner. Att kräva noll avvikelser vore att kräva att det återger facits
    # egna fel.
    return dom["facit"] - dom["mitt"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workdir", type=Path)
    ap.add_argument("--sidor", help="t.ex. 1,8,20 eller 8-12")
    ap.add_argument("--utvardera", action="store_true",
                    help="kör mot sidor som redan har bindning och jämför")
    ap.add_argument("--verkstall", action="store_true")
    a = ap.parse_args(argv)

    wd = a.workdir
    if not (wd / "pages").is_dir():
        ap.error("%s ser inte ut som en arbetskatalog" % wd)
    alla = _lasin(wd)
    if not alla:
        ap.error("inga sidor med både final.json och radboxar.json")

    skala = _skala([(d.get("elements") or [], rows)
                    for _, d, rows, _png in alla.values()])
    if skala is None:
        ap.error("för få bundna rader i boken för att mäta tecken per bredd")
    print("Skala: %.1f tecken per breddenhet (mätt ur bokens egna bundna rader)"
          % skala)

    if a.utvardera:
        # Exitkoden speglar domen, inte avvikelseantalet: verktyget underkänns
        # när facit passar trycket bättre oftare än verktyget gör.
        return 0 if utvardera(alla, skala) <= 0 else 1

    if a.sidor:
        önskade = set()
        for bit in a.sidor.split(","):
            if "-" in bit:
                lo, hi = bit.split("-")
                önskade.update(range(int(lo), int(hi) + 1))
            else:
                önskade.add(int(bit))
        alla = {n: v for n, v in alla.items() if n in önskade}

    total = 0
    for n, (f, d, rows, png) in sorted(alla.items()):
        els = d.get("elements") or []
        redan = sum(1 for el in els if (el.get("source") or {}).get("rader"))
        bind, anm = binda_sida(els, rows, skala, png=png)
        nya = {i: rr for i, rr in bind.items()
               if not (els[i].get("source") or {}).get("rader")}
        print("\ns. %d — %d element, %d uppmätta rader, %d hade redan bindning"
              % (n, len(els), len(rows), redan))
        for m in anm:
            print("   ! %s" % m)
        if not nya:
            print("   inget att binda")
            continue
        print("   binder %d element" % len(nya))
        for i in sorted(nya)[:4]:
            t = (els[i].get("text") or "")[:46]
            print("     [%2d] %-11s rader %-14s %s" %
                  (i, els[i]["type"], str(nya[i][:3]) + ("…" if len(nya[i]) > 3 else ""), t))
        total += len(nya)
        if a.verkstall:
            for i, rr in nya.items():
                s = els[i].setdefault("source", {})
                s["rader"] = rr
                box = _union(rows, rr)
                if box:
                    s["bbox"] = box
                    s["bbox_source"] = "pipeline.rows"
            f.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    print("\n%d element %s." % (total, "bundna" if a.verkstall else
                                "skulle bindas (torrkörning)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
