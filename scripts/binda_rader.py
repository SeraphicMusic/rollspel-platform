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

TVÅ REGIMER
-----------

Allt ovan beskriver den RADFORMADE regimen, där transkriptet har ett element
per tryckt rad. Ikappkörningens 29 äventyrsböcker är transkriberade STYCKE för
stycke: medianparagrafen är 103–525 tecken mot en tryckt rad på ungefär 50–60.
Där gick ingen tilldelning alls att räkna fram, och böckerna lämnades helt
obundna — dels för att ett element med spärren måste täcka exakt en rad, dels
för att skalan mättes ur redan bundna rader och de böckerna har noll.

Tre ändringar öppnar den styckeformade regimen, och alla tre är mätta:

* Skalan ur en BEVARANDEIDENTITET i stället för ur bundna rader
  (`_skala_ur_bevarande`). Validerad mot del II och del III, vars skalor är
  kända: 121,8 mot 122,4 och 116,9 mot 122,6.
* Spärren mot flerradiga element släpps — men bara i den regim som MÄTS fram
  av `_flerradig_regim`, aldrig på begäran.
* Ett nytt mått, RAGGEDGRÄNSEN, tar över förskjutningsprovets roll. Provet
  mäter om en körning blir dyrare av att skjutas ett steg, och i styckeregimen
  gör den inte det: ett femradigt stycke tappar en kort rad i ena änden och
  vinner en i den andra. Raggedheten pekar däremot ut gränserna direkt — ett
  stycke slutar på en kort rad och nästa börjar på en full.

Regimen har ett eget facitprov, `--utvardera-stycken`, som bygger stycken av
del I–III:s radformade transkript med pipelinens egen styckedefinition (se
`_syntetiska_stycken`). Utfall med breddsignalvakten (RAGGED_MIN_ANDEL):
del II 68,7 % identiska / 7,3 % avvikande, del III 62,1 % / 4,7 %, och i båda
vinner verktyget domen mot trycket (15 mot 12 respektive 18 mot 7). Vakten
kostar alltså ett par procentenheter träffar mot före (71,3/7,6 resp.
62,6/4,8) men refuserar de regioner vars band bär spaltbredd i stället för
bläckbredd — där band den tidigare hela kedjor ett steg ur led (mätt på
MUT-REG-youre-just-a-program s. 2 mot trycket). Den radformade regimen är
oförändrad, 85,5 % / 3,6 %.

BINDNINGSPASSET 2026-08-18 gav styckeregimen advokatens tre diskriminanter
(beslut.md Lovligt byte s. 5/6): styckeindraget (INDRAG_STRAFF, även gemen
fortsättningsstart), rubrikbandshöjden (RUBRIKHOJD_STRAFF), radrännsprovet
(RANNA_STRAFF) — plus breddförtroendet för kolumnklippta band (_betrodda),
regionöversättning av suffixade och flerspaltiga regionnamn (_oversatt,
ordningshållarna) och mätvokabulärens egen normalisering (_radregioner).
Domaren dömer nu i bokens regim med skiljetröskel (DOMSKILLNAD). Utfall mot
facitböckerna, före → efter (identiska/avvikande, dom verktyget–facit):

  Lovligt byte     67/11  1–2   →  63/1  1–0   (enda vinsten pixelverifierad:
                                                facit slukade rubrikbandet)
  Tanegashima      72/9   3–0   →  58/7  5–0   (s. 4-kedjans sex gamla fel-
                                                bindningar återskapas inte
                                                längre; s. 3:s facit är själv
                                                felbundet, pixelverifierat)
  del2             85,5 % 18–16 →  85,5 % 12–6
  del3             74,9 % 18–5  →  74,8 % 12–1
  stycken del II   68,7 % 15–12 →  52,5 % 33–18
  stycken del III  62,1 % 18–7  →  51,0 % 68–12

Täckningen i styckeproven sjunker — utskriftstaket (bindning dyrare än en
obunden lucka skrivs inte), betrodda-filtret och krockfiltret refuserar mer —
men domkvoten stiger kraftigt: verktyget byter täckning mot korrekthet, och
en box som fattas är alltid tillåten.

Torrkörning är default. Utvärdera alltid mot facit först:

    python3 scripts/binda_rader.py <arbete/slug> --utvardera
    python3 scripts/binda_rader.py <arbete/slug> --utvardera-stycken
    python3 scripts/binda_rader.py <arbete/slug> --sidor 1,8,20
    python3 scripts/binda_rader.py <arbete/slug> --sidor 1,8,20 --verkstall
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.regions import (FULL_WIDTH, FURNITURE,  # noqa: E402
                              column_count, measured_columns, normalize)

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

# Styckeindraget är styckegränsens signal från VÄNSTER, som raggedheten är
# den från höger. I de här häftena börjar varje stycke utom det första efter
# en rubrik på en indragen rad, och indraget är uppmätt av advokaten i BÅDA
# de styckeformade facitböckerna: Lovligt byte 0,0195 (beslut.md s. 5,
# brödtextkant 0,6735 mot indrag 0,6930) och Tanegashima (s. 4: mittkolumnens
# enda indragna band 113/117/123 är exakt de tre styckestarterna). Ett
# indraget band INUTI ett spann — inte som första rad — är alltså en slukad
# styckegräns, och det var precis så DP:n åt främmande text: e24 på s. 6
# spände 30 band över styckestarterna 77 och 92 utan att det kostade något.
#
# Fönstret skiljer indrag från kolumnklippning: mätningens `columns`-skivor
# klipper band så att vänsterkanten hamnar 0,08–0,17 höger om bläcket
# (Lovligt byte s. 5, band 87–90 och 110–111), och ett sådant band är inte
# en styckestart. Uppmätt på s. 5: äkta indrag 0,0190–0,0200, klippta band
# 0,1333–0,1738 — fönstret [0,010, 0,045] skiljer dem med god marginal.
# Kanten tas som medianen av regionens vänsterkanter: styckestarterna är
# omkring en femtedel av raderna, så medianen är alltid brödtextkanten.
INDRAG_MIN = 0.010
INDRAG_MAX = 0.045
INDRAG_STRAFF = 0.8

# Mörk ränna mellan två grannband i ett spann: banden är skivor av samma
# bläckblock, inte tryckta rader. En tryckt textrad har alltid en vit
# radränna mot grannraden; en illustration som mätningen delat i band har
# bläck i "rännan". Provet är advokatens eget (beslut.md s. 6: "räkna vita
# rännor i bandets y-intervall"), och det var så p006_e30 avslöjades — bunden
# till fyra band ur den övre illustrationens sammanhängande block. Uppmätt på
# s. 6: gapen mellan illustrationsskivorna 30–34 har mörk andel 0,289–0,369,
# gapen mellan äkta textrader 0,000–0,014. Tröskeln 0,15 skiljer dem med
# faktor 20 åt båda håll. Behållarna undantas — ett statblock får spänna
# över sina egna linjer.
RANNA_MORK = 0.15
RANNA_STRAFF = 1.0

# Minsta kostnadsskillnad som räknas som en DOM när en avvikelse ställs mot
# facit (`_domare`). Tröskeln 1e-9 dömde på brus: p005_e12:s två kandidater
# skilde 0,003 i kostnad — ingen mätning, men det räknades som facitseger.
# Nivån är samma som MARGINAL, alltså den skillnad bindaren själv kräver för
# att kalla två tilldelningar åtskiljbara.
DOMSKILLNAD = 0.15

# Så långt utanför regionens uppmätta högerkant ett bands högerkant får ligga
# innan breddens mätevidens underkänns. Mätningens `columns`-skivor går ibland
# ut till sidkanten i stället för till bläcket: Lovligt byte s. 5, band
# 105–107 har högerkant 0,999 mot spaltens 0,958 (beslut.md: "bandbredd-larmet
# på band 105–107, bbox-högerkant 0,9990 mot bläckets 0,9596/0,7661").
KLIPP_TOL = 0.02

# Ett band i RUBRIKHÖJD inuti ett brödtextspann är en slukad rubrik. Höjden
# är advokatens tredje diskriminant (beslut.md s. 5: "rubrikernas bandhöjd
# 0,0079–0,0082 mot brödtextens 0,0039–0,0071"), och den är mätt över alla
# fyra facitböckerna som kvoten bandhöjd/regionmedian för BUNDNA element:
#
#   bok           heading p25–p75   paragraph p90
#   Lovligt byte      1,29–1,53         1,19
#   Tanegashima       1,60–1,65         1,07
#   del2              1,00–1,08         1,08
#   del3              1,04–1,50         1,08
#
# Gränsen 1,25 ligger över varje boks paragraph-p90 och under rubrikklustret
# i de styckeformade böckerna. I del2 är rubrikgraden samma som brödtextens —
# där skiljer höjden ingenting, men den larmar då inte heller falskt. Straffet
# gäller bara den styckeformade regimen; den radformade är kalibrerad utan.
# Det var det här måttet som fällde p005_e12:s sväljning av band 78 —
# rubrikstumpen »2. SIDODÖRR« (h-kvot 1,30) inne i ett styckespann.
RUBRIKHOJD_KVOT = 1.25
RUBRIKHOJD_STRAFF = 0.8


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
    och på hur mätningen normaliserar bredden.
    """
    prov = []
    for els, rows, _mat in sidor:
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


# Minsta antal element i en region för att den ska få bidra till skalan. Under
# det blir kvoten dominerad av en enda rubrik eller bildtext. Svept mot del II
# och del III: 4 ger −0,5 % respektive −4,6 % mot deras kända skalor, 8 ger
# −0,1 % och −3,7 % men halverar antalet användbara regioner i de korta
# äventyren.
_SKALA_MIN_ELEMENT = 4


def _skala_ur_bevarande(sidor):
    """Skalan UTAN någon bunden rad, ur en bevarandeidentitet per region.

    `_skala` ovan kräver minst trettio enradigt bundna paragrafer. De 29
    äventyrsböckerna har noll — de har aldrig burit `source.rader` — och utan
    skala går ingen bindning att räkna fram alls.

    Identiteten behöver ingen bindning: all sats i en region är transkriberad,
    och all transkriberad text står på regionens textband. Summeras båda sidor
    faller den okända tilldelningen bort och kvar står

        skala ≈ Σ (teckenlängd / typfaktor) / Σ bandbredd

    Regionen tas efter NORMALISERING. Med de råa namnen matchade nästan
    ingenting i de 29 böckerna — deras transkript skriver `kolumn 1` där
    mätningen skriver `vänsterkolumn` — så urvalet blev de få sidor som råkade
    använda mätningens ord, och skalan sköt över med mer än det dubbla (179,9
    mot en sättning som rymmer omkring 53 tecken på en rad av 0,425 breddenhet).

    Måttet är falsifierbart och falsifierat: kört på del II och del III, vars
    skalor är kända ur deras egna bundna rader (122,4 och 122,6). Medianen över
    regionerna tas i stället för medelvärdet — en helsidesillustration bryter
    identiteten på sin egen region, och medianen bryr sig inte.
    """
    prov = []
    for els, rows, mat in sidor:
        kolumner = measured_columns(mat or {})
        tryckta = column_count([_region(el) for el in els])
        karta = {}
        for el in els:
            rå = _region(el)
            if rå not in karta:
                karta[rå] = normalize(rå, kolumner, tryckta) or rå
        per = {}
        for r in rows:
            per.setdefault(r.get("region"), []).append(r)
        for reg, rs in per.items():
            if reg in (None, "sidhuvud", "sidfot"):
                continue
            höjder = [r["bbox"][3] for r in rs if len(r.get("bbox") or []) == 4]
            if not höjder:
                continue
            med = statistics.median(höjder)
            if med <= 0:
                continue
            bredd = sum(r["bbox"][2] for r in rs
                        if len(r.get("bbox") or []) == 4
                        and TEXT_LO <= r["bbox"][3] / med <= TEXT_HI)
            if bredd <= 0:
                continue
            tecken, n = 0.0, 0
            for el in els:
                if karta.get(_region(el)) != reg or el.get("removed"):
                    continue
                faktor = (TYPSKALA.get(el.get("type")) or (None,))[0]
                längd = _textlangd(el)
                if faktor is None or not längd:
                    continue
                tecken += längd / faktor
                n += 1
            if n >= _SKALA_MIN_ELEMENT and tecken > 0:
                prov.append(tecken / bredd)
    return statistics.median(prov) if prov else None


# Under så här stor andel av regionens FULLA radbredd är raden ragged, alltså
# ett styckes sista rad. Sättningen i de här häftena är rak: på den-vita-duvan
# s. 2 ligger p75, p90 och max alla på 0,425 medan 18–24 % av raderna är
# kortare. Klustret är så tätt att gränsen inte behöver vara känslig.
RAGGED_SHARE = 0.92

# Straff för en felplacerad styckegräns — en KORT rad inne i ett stycke, eller
# ett stycke som slutar på en FULL rad.
#
# Det här måttet är styckeregimens motsvarighet till förskjutningsprovet, och
# det behövdes: provet mäter om en körning blir dyrare av att skjutas ett steg,
# och i den radformade regimen ändrar ett steg varje elements radbredd helt. I
# den styckeformade gör det inte det. Ett femradigt stycke som skjuts ett steg
# tappar en kort rad i ena änden och vinner en i den andra, totalbredden ändras
# med omkring en tiondel, och brödtextens tolerans är 0,15 — alltså noll
# kostnad.
#
# Raggedheten pekar däremot ut gränserna direkt: ett stycke SLUTAR på en kort
# rad, och nästa börjar på en full. Det är en mätning i sidbilden, inte ett
# antagande om texten.
#
# Nivån är mätt mot styckeprovet. Utan straffet (0,0) binder verktyget 1019
# element rätt i del II; med 0,8 binder det 1215, alltså nära en femtedel fler,
# mot 129 avvikelser i stället för 100. Höjs det till 1,5 faller träffarna till
# 1146 och avvikelserna stiger till 181 — då börjar straffet styra i stället
# för att stödja.
RAGGED_STRAFF = 0.8

# Typer som sätts som rak brödtext och därför bär raggedsignalen. Rubriker är
# centrerade eller korta av andra skäl, behållarna har sin egen radstruktur.
RAGGED_TYPER = {"paragraph", "boxed_text", "list_item"}

# Så stor andel av en brödtextregions rader måste vara ragged för att
# regionens bredder alls ska räknas som uppmätta. Rak sättning slutar varje
# stycke på en kort rad — piloten ligger på 18–24 % — medan en mätning vars
# band bär spaltbredd i stället för bläckbredd ger nära noll. På
# MUT-REG-youre-just-a-program s. 2 var andelen 3 % (2 av 67, och styckeslutet
# på band 125 mättes till full spaltbredd): styckegränserna gick inte att
# mäta, förskjutningsprovet var blint, och kedjan band ett steg ur led som
# "fastkilad". Gränsen 0,10 skiljer de två världarna med god marginal åt båda
# håll.
RAGGED_MIN_ANDEL = 0.10

# Hur hårt toleransen skärps när elementet spänner FLERA rader.
#
# Typernas toleranser är mätta på ENRADIGA bindningar, där hela spridningen
# ligger i en enda rads bredd. Spänner elementet n rader summeras bredderna, och
# den slumpmässiga variationen medelvärdesbildas bort — samma tolerans blir då
# alldeles för slapp, och en styckegräns kan flyttas ett steg utan att kosta
# något. Toleransen delas därför med n upphöjt till talet nedan.
#
# Mätt mot det syntetiska styckeprovet (se `_syntetiska_stycken`), del II och
# del III, som identiska bindningar och avvikelser:
#
#   skärpning   del II            del III
#   0,0         1183 / 133        700 / 46
#   0,5         1204 / 132        707 / 49
#   1,0         1215 / 129        716 / 55
#
# 1,0 tar alltså flest rätt och för del II dessutom färst fel. Den statistiska
# normen hade varit 0,5 (felet i en summa av n växer som roten ur n), men
# mätningen säger 1,0 och mätningen får gälla.
TOLERANS_SKARPNING = 1.0

# Hur många gånger längre än en tryckt rad medianparagrafen måste vara för att
# boken ska räknas som styckeformad. Mätt: de 29 äventyrsböckerna ligger på
# 2–10 rader per paragraf, del I–III på 1. Gränsen 1,5 skiljer dem med marginal
# och kan inte råka slå om för en bok vars sättning bara är lite bredare.
FLERRADIG_FAKTOR = 1.5


def _flerradig_regim(sidor, skala):
    """Är bokens transkript styckeformat i stället för radformat?

    Regimen mäts, den sätts inte för hand. Ett radformat transkript har ett
    element per tryckt rad; ett styckeformat har ett per stycke, och då är
    medianparagrafen flera rader lång. Jämförelsen görs mot bokens EGEN
    radkapacitet — skalan gånger medianbandets bredd — så den fungerar lika bra
    för en smal trespaltig sida som för en bred tvåspaltig.
    """
    if not skala:
        return False
    langder, bredder = [], []
    for els, rows, _mat in sidor:
        for el in els:
            if el.get("type") == "paragraph" and not el.get("removed"):
                n = _textlangd(el)
                if n:
                    langder.append(n)
        for r in rows:
            b = r.get("bbox") or []
            if len(b) == 4 and b[2] > 0.05:
                bredder.append(b[2])
    if len(langder) < 10 or not bredder:
        return False
    kapacitet = skala * statistics.median(bredder)
    if kapacitet <= 0:
        return False
    return statistics.median(langder) > FLERRADIG_FAKTOR * kapacitet


def _full_bredd(rows):
    """Regionens FULLA radbredd — den raka sättningens högerkant.

    Tas som p85 och inte som max: en enstaka rad kan sticka ut över spalten
    (en tabellrubrik, ett brutet ord), och max skulle då flytta hela
    referensen. På piloten ligger p75, p90 och max alla på 0,425, så måttet är
    okänsligt för var i det intervallet gränsen läggs.
    """
    w = sorted(r["bbox"][2] for r in rows if len(r.get("bbox") or []) == 4)
    if not w:
        return None
    return w[min(int(0.85 * len(w)), len(w) - 1)] or None


def _raggedstraff(el, rows, a, b, flerradiga, full_bredd, betrodda=None,
                  indragna=None):
    """Kostnaden för styckegränser som strider mot den raka sättningen.

    Två fel, båda mätbara i sidbilden: en KORT rad inne i stycket (där slutade
    i själva verket ett stycke) och en FULL sista rad (där slutade det inte).

    Ett band utan betrodd bredd (`_betrodda`) döms aldrig: ett kolumnklippt
    band ser kort ut utan att stycket slutat där — det var så facits
    advokatdömda bindning av p005_e14 fick 2,4 i falskt straff på fyra
    klippta band. Spannets FÖRSTA rad döms inte heller när den är INDRAGEN:
    indraget äter en bit av radbredden, så en indragen styckestart är alltid
    något kort — p006_e21:s eget startband 25 mätte 0,2607 mot gränsen
    0,2616, fick 0,8 i falskt straff, och DP:n valde hellre att börja stycket
    en rad för sent än att betala för sin egen styckestart.
    """
    if not flerradiga or not full_bredd:
        return 0.0
    if el.get("type") not in RAGGED_TYPER or b - a < 2:
        return 0.0
    gräns = RAGGED_SHARE * full_bredd
    straff = 0.0
    for j in range(a, b - 1):
        if betrodda is not None and not betrodda[j]:
            continue
        if j == a and indragna is not None and indragna[j]:
            continue
        box = rows[j].get("bbox") or []
        if len(box) == 4 and box[2] < gräns:
            straff += RAGGED_STRAFF
    # En full sista rad frias när raden EFTER spannet är indragen: indraget
    # är styckegränsens direkta bevis och slår slutradens bredd. Tanegashima
    # s. 4, p004_e19: slutraden 112 mäter 0,96 av fullbredden (över
    # RAGGED_SHARE) men band 113 är indraget — stycket slutar bevisligen där,
    # och det falska straffet var med om att skjuta kedjan ett element.
    if betrodda is None or betrodda[b - 1]:
        nasta_indragen = (indragna is not None and b < len(rows)
                          and indragna[b])
        sista = rows[b - 1].get("bbox") or []
        if len(sista) == 4 and sista[2] >= gräns and not nasta_indragen:
            straff += RAGGED_STRAFF
    return min(straff, MAX_KOSTNAD)


def _indragna(rows):
    """Flagga per rad: börjar raden indragen mot regionens brödtextkant?

    Kanten är medianen av radernas vänsterkanter — styckestarterna är omkring
    en femtedel av raderna, så medianen träffar alltid den raka kanten.
    Fönstret [INDRAG_MIN, INDRAG_MAX] skiljer äkta styckeindrag från band vars
    vänsterkant klippts av mätningens kolumnskivor (se konstanterna).
    """
    xs = [r["bbox"][0] for r in rows if len(r.get("bbox") or []) == 4]
    if not xs:
        return [False] * len(rows)
    kant = statistics.median(xs)
    ut = []
    for r in rows:
        b = r.get("bbox") or []
        d = (b[0] - kant) if len(b) == 4 else 0.0
        ut.append(INDRAG_MIN <= d <= INDRAG_MAX)
    return ut


def _rubrikband(rows):
    """Flagga per rad: står bandet i rubrikhöjd mot regionens medianhöjd?"""
    hs = [r["bbox"][3] for r in rows if len(r.get("bbox") or []) == 4]
    if not hs:
        return [False] * len(rows)
    med = statistics.median(hs)
    if med <= 0:
        return [False] * len(rows)
    ut = []
    for r in rows:
        b = r.get("bbox") or []
        ut.append(len(b) == 4 and b[3] / med >= RUBRIKHOJD_KVOT)
    return ut


def _betrodda(rows):
    """Flagga per rad: bär bandets BREDD mätevidens?

    Mätningens `columns`-skivor klipper band i x, och ett klippt band mäter
    skivan i stället för bläcket: på Lovligt byte s. 5 börjar banden 87–90 och
    110–111 0,13–0,17 höger om sitt eget bläck, och 105–107 går ut till 0,999.
    Advokatens regel (beslut.md s. 5): "klippningen diskvalificerar inte
    bandet, men bara y, höjd och den OKLIPPTA kanten bär information". Utan
    den regeln förgiftade de klippta banden varje breddmått i kedjan: facits
    advokatdömda bindning av p005_e14 kostade 3,49 — nästan allt falskt
    raggedstraff på fyra klippta band — och verktyget "vann" med en bindning
    som trycket motsäger.

    Vänsterkanten underkänns när den ligger mer än INDRAG_MAX höger om
    regionens brödtextkant (medianen av vänsterkanterna): det är antingen en
    kolumnklippning (0,13–0,17) eller en centrerad rubrik — i båda fallen är
    bredden ingen brödtextevidens. Högerkanten underkänns när den går mer än
    KLIPP_TOL utanför regionens uppmätta fullbredd. En kort (ragged) rad är
    alltid betrodd — det är själva signalen.
    """
    boxar = [r.get("bbox") if len(r.get("bbox") or []) == 4 else None
             for r in rows]
    xs = [b[0] for b in boxar if b]
    if not xs:
        return [True] * len(rows)
    kant = statistics.median(xs)
    full = _full_bredd(rows)
    ut = []
    for b in boxar:
        if not b:
            ut.append(True)
            continue
        ok = b[0] - kant <= INDRAG_MAX
        if ok and full:
            ok = (b[0] + b[2]) <= kant + full + KLIPP_TOL
        ut.append(ok)
    return ut


def _morka_gap(rows, png):
    """Per grannpar i regionen: bär gapet mellan banden bläck i stället för en
    vit radränna? Då är banden skivor av samma block — en illustration som
    mätningen delat — och inget textelement får spänna över paret.

    Mäts i sidbilden, i de två bandens gemensamma x-fönster. Ett gap som inte
    rymmer en enda bildpunktsrad räknas som mörkt: två band som stöter i
    varandra utan ränna är blockskivor per definition. Utan bild eller Pillow
    returneras None — provet faller då bort, vilket ger fler felmöjligheter
    men aldrig fler spärrade sanna bindningar.
    """
    if not png or not Path(png).exists():
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    im = Image.open(png).convert("L").point(lambda v: 255 if v < 128 else 0)
    W, H = im.size
    ut = []
    for j in range(len(rows) - 1):
        b1 = rows[j].get("bbox") or []
        b2 = rows[j + 1].get("bbox") or []
        if len(b1) != 4 or len(b2) != 4:
            ut.append(False)
            continue
        # y räknas från nederkanten: gapet är övre bandets nederkant ned till
        # nedre bandets överkant.
        x0, x1 = max(b1[0], b2[0]), min(b1[0] + b1[2], b2[0] + b2[2])
        upp, ner = int((1 - b1[1]) * H), int((1 - b2[1] - b2[3]) * H)
        if x1 <= x0:
            ut.append(False)
            continue
        if ner <= upp:
            ut.append(True)
            continue
        bit = im.crop((int(x0 * W), upp, int(x1 * W), ner))
        if not bit.width or not bit.height:
            # x-fönstret rundade av till noll bildpunkter — inget att mäta
            ut.append(False)
            continue
        mork = bit.histogram()[255] / (bit.width * bit.height)
        ut.append(mork >= RANNA_MORK)
    return ut


def _radkostnad(el, rows, a, b, skala, svarta=None, flerradiga=False,
                full_bredd=None, indragna=None, hopp=None, gap=None,
                betrodda=None, rubrikband=None):
    """Kostnaden för att låta `el` täcka raderna [a, b).

    None betyder omöjligt. I den RADFORMADE regimen — den som del I–III är
    transkriberade i — täcker ett element som inte är en behållare exakt EN
    tryckt rad, och allt annat är uteslutet på förhand.

    `flerradiga` slår av den spärren för den STYCKEFORMADE regimen. De 29
    äventyrsböckerna är transkriberade stycke för stycke: medianparagrafen är
    103–525 tecken mot en tryckt rad på ungefär 50–60, alltså två till tio
    rader per element. Med spärren kvar går ingen tilldelning alls att räkna
    fram och hela boken lämnas obunden. Regimen mäts per bok i
    `_flerradig_regim`, den sätts inte för hand — och bredkostnaden nedan
    gäller oförändrat, så ett stycke som sträcker sig över för många rader
    kostar precis lika mycket som ett som täcker för få.
    """
    n = b - a
    typ = el.get("type")
    if typ not in BEHALLARE and n != 1 and not flerradiga:
        return None
    # Ett spann över en mörk ränna lägger text på skivorna av ett bläckblock —
    # illustrationens band ser ut som rader men saknar radrännor (RANNA_MORK).
    # Behållarna undantas: ett statblock spänner över sina egna linjer.
    ranna = 0.0
    if gap and n > 1 and typ not in BEHALLARE:
        ranna = RANNA_STRAFF * sum(1 for j in range(a, b - 1) if gap[j])
    faktor, tolerans = TYPSKALA.get(typ, (None, None))
    if el.get("_ordningshallare"):
        # Tvåspaltselementets text fördelar sig över två regioner i okänd
        # proportion — bredden bär ingen evidens i någon av dem.
        faktor = None
    if faktor is None:
        # Typen bär ingen breddevidens alls (punktledare, breda kolumntitlar —
        # se TYPSKALA). Då får ett extra band inte vara gratis att svälja:
        # utan kostnaden slukade sidfoten p006_e33 band 156 — ett band utan
        # en enda sidfotsink — bara för att slippa hoppstraffet. Varje band
        # utöver ett kostar precis sitt hoppstraff, så att binda och att
        # hoppa väger jämnt och elementet lämnas obundet i stället
        # (marginalen blir noll — en advokat får döma).
        extra = 0.0
        if hopp and n > 1:
            h = [hopp[j] for j in range(a, b)]
            extra = sum(h) - max(h)
        svart0 = 0.0
        if svarta:
            svart0 = SVART_STRAFF * sum(
                1 for j in range(a, b)
                if svarta[j] is not None and svarta[j] >= SVARTA_GRAFIK)
        return svart0 + extra + ranna
    bredd, n_ok = 0.0, 0
    for j in range(a, b):
        box = rows[j].get("bbox") or []
        if len(box) != 4:
            return None
        if betrodda is None or betrodda[j]:
            bredd += box[2]
            n_ok += 1
    svart = 0.0
    if svarta and typ != "heading":
        # Rubriker undantas: en displayrubrik i fet grad är nästan helsvart
        # inom sin egen täta box (Tanegashima s. 4, AVSLUTNINGEN band 106:
        # svärta över tröskeln, höjdkvot 2,54) — straffet som byggdes mot
        # illustrationspaneler gav facits rubrikbindning 2,0 i falsk kostnad
        # och sköt hela kedjan ett element ur led.
        svart = SVART_STRAFF * sum(
            1 for j in range(a, b)
            if svarta[j] is not None and svarta[j] >= SVARTA_GRAFIK)
    svart += ranna
    # Ett indraget band inuti spannet — inte som första rad — är en slukad
    # styckestart: indraget är styckegränsens signal från vänster, som
    # raggedheten är den från höger. Bara i den styckeformade regimen och
    # bara för brödtexttyperna, precis som RAGGED_STRAFF.
    if (flerradiga and indragna and typ in RAGGED_TYPER):
        if n > 1:
            svart += INDRAG_STRAFF * sum(
                1 for j in range(a + 1, b) if indragna[j])
        # ...och ett element vars text BÖRJAR med gemen — en fortsättning
        # mitt i en mening, som p005_e03 "de tagit över..." från s. 4 — kan
        # inte börja på ett indraget band: indraget är en styckestart.
        t = (el.get("text") or "").lstrip()
        if indragna[a] and t and t[:1].islower():
            svart += INDRAG_STRAFF
    # En slukad rubrik syns på HÖJDEN: ett band i rubrikhöjd hör aldrig
    # hemma i ett brödtextspann (RUBRIKHOJD_KVOT, advokatens tredje
    # diskriminant). Bara i den styckeformade regimen.
    if (flerradiga and rubrikband and typ in RAGGED_TYPER):
        svart += RUBRIKHOJD_STRAFF * sum(
            1 for j in range(a, b) if rubrikband[j])
    # Breddkostnaden räknas på de BETRODDA banden (`_betrodda`): ett
    # kolumnklippt band mäter skivan i stället för bläcket och får inte
    # vittna om bredden. Den förväntade teckenlängden skalas med den betrodda
    # andelen — samma antagande som hela måttet vilar på, att texten fördelar
    # sig jämnt över spannets rader. Utan en enda betrodd rad finns ingen
    # breddevidens alls; kvar står ordningen och straffen. Tilldelningen
    # tillåts i DP:n — att förbjuda den fragmenterade kedjorna och rev upp
    # hela regioner — men den SKRIVS aldrig: utskriftsfiltret i `binda_sida`
    # släpper inga bindningar utan ett enda betrott band.
    if n_ok == 0:
        return svart + _raggedstraff(el, rows, a, b, flerradiga, full_bredd,
                                     betrodda, indragna)
    if bredd <= 0:
        return None
    väntat = _textlangd(el)
    if väntat == 0:
        return svart
    väntat = väntat * n_ok / n
    väntad_bredd = skala * faktor * bredd
    # Felet mäts mot det MINSTA av de två talen, så att spänna över för många
    # rader kostar lika mycket som att spänna över för få. Med den förväntade
    # bredden i nämnaren blev ett övertag aldrig dyrare än 1,0 — ett
    # list-element kunde då lägga sig över en hel spalt nästan gratis.
    fel = abs(väntat - väntad_bredd) / max(1e-9, min(väntat, väntad_bredd))
    # Toleransen är typens egen uppmätta spridning: inom den kostar avvikelsen
    # ingenting, utanför växer den linjärt. Över flera rader skärps den — se
    # TOLERANS_SKARPNING. Skärpningen räknas på de betrodda raderna, som är
    # de som medelvärdesbildar bort spridningen.
    if flerradiga and n_ok > 1 and TOLERANS_SKARPNING:
        tolerans = tolerans / (n_ok ** TOLERANS_SKARPNING)
    kostnad = min(max(0.0, fel - tolerans), MAX_KOSTNAD) + svart
    return kostnad + _raggedstraff(el, rows, a, b, flerradiga, full_bredd,
                                   betrodda, indragna)


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


def _losning(els, rows, skala, max_spann, svarta=None, flerradiga=False,
             gap=None):
    full = _full_bredd(rows) if flerradiga else None
    indrag = _indragna(rows) if flerradiga else None
    betrodda = _betrodda(rows) if flerradiga else None
    rubrik = _rubrikband(rows) if flerradiga else None
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
                c = _radkostnad(els[i], rows, j, j + n, skala, hopp_svarta,
                                flerradiga, full, indrag, hopp, gap, betrodda,
                                rubrik)
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


def _radregioner(rows, kolumner):
    """Mätradernas regionnamn, normaliserade till spaltvokabulären.

    Mätningen är inte enig med sig själv: på Lovligt byte s. 5 heter
    högerspalten `högerkolumn` i de flesta y-skivorna men `kolumn 3` i skivan
    0,4389–0,4768 — och raderna 78–79 (rubriken 2. SIDODÖRR och styckets
    första rad) föll därmed ur högerkolumnens inventarium. Följden var värre
    än en lucka: facits bindning [79, 82] gick inte ens att UTTRYCKA, den
    ärliga kedjan blev omöjlig, och DP:n lät i stället rubriken ta nästa
    rubriks band (e11@83 → e13@88 → hela kedjan ur led).

    Ordinalen översätts mot mätningens egna spaltnamn i x-ordning — samma
    `normalize`, men UTAN spaltantalsvakten: den vaktar tryck mot mätning,
    och här står mätningen på båda sidor. Sidhuvud/sidfot/illustration
    returneras oförändrade av `normalize`; ett namn som inte går att
    översätta behåller sitt råa värde.
    """
    return [normalize(r.get("region"), kolumner, None) or r.get("region")
            for r in rows]


def _oversatt(els, radboxar):
    """Region i fritext -> mätningens vokabulär, för en hel sidas element.

    Returnerar `(karta, ooversatt)`. Elementets region står i fritext och
    mätningens i en kontrollerad vokabulär; `pipeline.regions` översätter, och
    lämnar det tvetydiga oöversatt (se modulens docstring). Utan
    översättningen matchar `kolumn 1` aldrig `vänsterkolumn`, och hela
    bindningen uteblir.

    Transkriptet hänger ofta en beskrivande svans på spaltnamnet —
    `högerkolumn, spelartext`, `högerkolumn, fortsättning från sida 4` — och
    ett sådant namn föll tidigare HELT ur bindningen fast spalten är entydig.
    Det var värre än en missad bindning: elementets textband stod då kvar som
    herrelöst bete i regionens inventarium, och DP:n sträckte hellre ett
    ANNAT element över dem än betalade hoppstraffet — på s. 5 åt p005_e08 sju
    av spelartextens band för att p005_e07:s region inte översattes. Därför
    prövas basnamnet före kommatecknet genom samma kedja. Ett namn som pekar
    ut TVÅ spalter (`vänster-/mittkolumn`) har inget kommatecken att klippa
    vid och förblir oöversatt — det är rätt: elementet spänner två regioner
    och kan inte bindas i en.
    """
    kolumner = measured_columns(radboxar or {})
    tryckta = column_count([_region(el) for el in els])
    uppmatta = set(kolumner) | set(FURNITURE) | {FULL_WIDTH}
    karta, ooversatt, tvaspalt = {}, set(), {}
    for el in els:
        rå = _region(el)
        if rå in karta:
            continue
        norm = normalize(rå, kolumner, tryckta)
        if norm is None and rå and "," in rå:
            bas = rå.split(",", 1)[0].strip()
            norm = normalize(bas, kolumner, tryckta)
            if norm is None and bas in uppmatta:
                norm = bas
        if norm is None:
            # Ett namn som pekar ut FLERA spalter (`vänster-/mittkolumn`)
            # binds aldrig — men de utpekade spalterna antecknas, så att
            # elementet kan hålla sin plats i läsordningen där (se
            # ordningshållarna i `binda_sida`).
            delar = _tvaspaltsdelar(rå, kolumner)
            if delar:
                tvaspalt[rå] = delar
            ooversatt.add(rå)
        karta[rå] = norm or rå
    return karta, ooversatt, tvaspalt


def _tvaspaltsdelar(rå, kolumner):
    """Spalterna ett flerspaltsnamn pekar ut, i mätningens vokabulär.

    `vänster-/mittkolumn` -> `['vänsterkolumn', 'mittkolumn']` (eller vad
    mätningen nu kallar första och mellersta spalten). Bara namn som entydigt
    refererar minst två spalter ger något; allt annat ger [].
    """
    if not rå or not kolumner:
        return []
    bas = rå.split(",", 1)[0]
    ut = []
    if "vänster" in bas:
        ut.append(kolumner[0])
    if "mitt" in bas and len(kolumner) == 3:
        ut.append(kolumner[1])
    if "höger" in bas:
        ut.append(kolumner[-1])
    # dubbletter kan uppstå i en tvåspaltsmätning ("mitt-/högerkolumn" när
    # bara två spalter mätts) — då är referensen inte entydig
    if len(ut) != len(set(ut)):
        return []
    return ut if len(ut) >= 2 else []


def binda_sida(els, rows, skala, max_spann=80, png=None, flerradiga=False,
               radboxar=None):
    """Bind en sidas element till dess uppmätta rader, region för region.

    Returnerar `(bindningar, anmarkningar)` där bindningar är
    `{elementindex: [radindex]}`.

    Ett TÖMT element (`removed: true`) och en illustration deltar aldrig:
    det tömda har inget tryckt motstycke att bindas till (Tanegashimas
    p005_e27 — 28 kartband — var verktygets enda skarpa förslag där, och det
    refuserades för hand), och illustrationens läge bär ingen breddevidens
    alls men skulle med sin kostnadsfria typ gärna svälja ett textband för
    att slippa ett hoppstraff.
    """
    bindningar, anm = {}, []
    svarta = _svarta(rows, png)
    kolumner = measured_columns(radboxar or {})
    tryckta = column_count([_region(el) for el in els])
    # Ett namn som inte gick att översätta faller tillbaka på sitt råa värde.
    # Det matchar då ingen uppmätt region och elementet lämnas obundet, vilket
    # är rätt — men det ska inte rapporteras som att regionen SAKNAS i
    # mätningen. `mittkolumn` finns i mätningens vokabulär; det som hänt är att
    # översättningen vägrade, och vägran har egna, kända skäl.
    karta, ooversatt, tvaspalt = _oversatt(els, radboxar)
    radreg = _radregioner(rows, kolumner)
    if tryckta and kolumner and tryckta != len(kolumner):
        anm.append("trycket har %d spalter, mätningen %d — spaltelementen "
                   "lämnas obundna (mätningen har slagit ihop spalter)"
                   % (tryckta, len(kolumner)))

    elregioner = []
    for el in els:
        reg = karta[_region(el)]
        if reg not in elregioner:
            elregioner.append(reg)

    def deltar(el, reg):
        """Hör elementet hemma i regionens DP — och i så fall hur?

        'bind' är ett vanligt element. 'hallare' är ett tvåspaltselement som
        deltar som ORDNINGSHÅLLARE: det håller sin plats i läsordningen och
        får ta sina egna band mot absorptionskostnad, men bredden bär ingen
        evidens (texten fördelar sig över två regioner i okänd proportion)
        och bindningen skrivs aldrig — unionen av två spalters band vore
        innehållslös. Utan hållaren stod tvåspaltselementets band som
        herrelöst bete: på s. 6 lämnade DP:n hellre tre element utan rad och
        sköt hela mittkedjan ett steg än betalade sex hoppstraff för
        p006_e18:s rader.
        """
        if el.get("removed") or el.get("type") == "illustration":
            return None
        rå = _region(el)
        if karta[rå] == reg:
            return "bind"
        if reg in tvaspalt.get(rå, ()):
            return "hallare"
        return None

    for reg in elregioner:
        eidx, hallare = [], set()
        for i, el in enumerate(els):
            roll = deltar(el, reg)
            if roll is None:
                continue
            if roll == "hallare":
                hallare.add(len(eidx))
            eidx.append(i)
        ridx = [j for j in range(len(rows)) if radreg[j] == reg]
        if not eidx:
            continue
        if not ridx:
            if reg in ooversatt:
                anm.append("region %r gick inte att översätta entydigt till "
                           "mätningens vokabulär — %d element lämnade obundna"
                           % (reg, len(eidx)))
            else:
                anm.append("region %r finns hos %d element men inte i "
                           "mätningen — lämnad obunden" % (reg, len(eidx)))
            continue
        delels = []
        for p, i in enumerate(eidx):
            el = els[i]
            if p in hallare:
                el = dict(el)
                el["_ordningshallare"] = True
            delels.append(el)
        delrows = [rows[j] for j in ridx]
        delsv = [svarta[j] for j in ridx]
        # I den styckeformade regimen är raggedheten det enda som mäter var
        # styckegränserna går — förskjutningsprovet är blint där (se
        # RAGGED_STRAFF). Bär regionens band spaltbredd i stället för
        # bläckbredd finns ingen kort rad alls, varje läge kostar lika mycket,
        # och en kedja som går jämnt ut mot kanterna ser fastkilad ut fast
        # inget läge är uppmätt: på MUT-REG-youre-just-a-program s. 2 band
        # hela mittspaltskedjan ett steg ur led med rubriken PROGRAMVARA
        # utanför mätningen, och trycket visade styckegränsen en rad upp.
        # Rak sättning har alltid ragged styckeslut (18–24 % av raderna på
        # piloten), så en brödtextregion med nära noll korta rader är inte
        # slät — den är omätt, och då binds ingenting (RAGGED_MIN_ANDEL).
        if flerradiga and any(el.get("type") in RAGGED_TYPER
                              for el in delels):
            full = _full_bredd(delrows)
            gräns = RAGGED_SHARE * (full or 0.0)
            ragged = sum(1 for r in delrows
                         if len(r.get("bbox") or []) == 4
                         and r["bbox"][2] < gräns)
            if ragged < RAGGED_MIN_ANDEL * len(delrows):
                anm.append("region %r: banden bär ingen breddsignal (%d av %d "
                           "rader ragged) — styckegränser går inte att mäta, "
                           "%d element lämnade obundna"
                           % (reg, ragged, len(delrows), len(delels)))
                continue
        gap = _morka_gap(delrows, png)
        _, lösn = _losning(delels, delrows, skala, max_spann, delsv,
                           flerradiga, gap)
        if not lösn:
            anm.append("region %r: ingen tilldelning gick att räkna fram"
                       % (reg,))
            continue
        # Varje körning prövas mot en förskjutning ett steg åt vardera hållet.
        bevis = {}
        jämnt = (len(lösn) == len(delels)
                 and sum(len(rr) for _i, rr, _m in lösn) == len(delrows))
        körningar = _kor(lösn)
        klar = []
        for körning in körningar:
            b = _tal_forskjutning(delels, delrows, skala, delsv, körning,
                                  jämnt, flerradiga, gap)
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
        # De två spärrarna redovisas var för sig. Sammanslagna sa
        # anmärkningen "går att skjuta ett steg lika billigt" också om element
        # vars körning var bevisad men vars egen marginal var för tunn, och den
        # felskyltningen kostade en timmes felsökning i fel ände av koden.
        svag_forskjutning = svag_marginal = 0
        betro = _betrodda(delrows) if flerradiga else None
        indr = _indragna(delrows) if flerradiga else None
        rubr = _rubrikband(delrows) if flerradiga else None
        fullb = _full_bredd(delrows) if flerradiga else None
        hoppk = _hoppstraff(delrows, delsv)
        otrodda = dyra = 0
        for i, rr, marginal in lösn:
            if bevis.get(i, 0.0) < FORSKJUTNING:
                svag_forskjutning += 1
                continue
            if marginal < MARGINAL:
                svag_marginal += 1
                continue
            if i in hallare:
                continue
            # En bindning utan ett enda betrott band skrivs aldrig: unionen
            # av enbart klippta band omsluter inte elementets bläck, och en
            # sådan box är ett fel som ser ut som data (advokatens dom över
            # p005_e11@78, vars enda kandidatband täckte 18,5 % av rubrikens
            # bläck, och p006_e30@153-155, vars två sista rader ligger i ett
            # sidfotstypat band). Tilldelningen behålls i DP:n för kedjans
            # stabilitet men stoppas här.
            if betro is not None and not any(betro[j] for j in rr):
                otrodda += 1
                continue
            # En bindning som kostar mer än priset för att lämna elementet
            # obundet är sämre än ingen bindning: DP:n kan ha valt den bara
            # för att slippa hoppstraffen för herrelösa band. På Tanegashima
            # s. 3 spände rubriken HOTEL GRAND JAPAN 25 band till kostnad
            # 6,0 hellre än att lämna brevlådornas rader obundna. En sådan
            # layout är omätbar för verktyget — advokaten får binda.
            k = _radkostnad(delels[i], delrows, rr[0], rr[-1] + 1, skala,
                            delsv, flerradiga, fullb, indr, hoppk, gap,
                            betro, rubr)
            if k is None or k >= ELEMENT_UTAN_RAD:
                dyra += 1
                continue
            bindningar[eidx[i]] = [ridx[j] for j in rr]
        if otrodda:
            anm.append("region %r: %d element utan ett enda betrott band — "
                       "unionen omsluter inte bläcket, lämnade obundna"
                       % (reg, otrodda))
        if dyra:
            anm.append("region %r: %d element vars bindning kostar mer än en "
                       "obunden lucka — lämnade obundna för advokaten"
                       % (reg, dyra))
        if svag_forskjutning:
            anm.append("region %r: %d av %d element ligger i en körning som "
                       "går att skjuta ett steg lika billigt — lämnade obundna "
                       "för advokaten" % (reg, svag_forskjutning, len(lösn)))
        if svag_marginal:
            anm.append("region %r: %d av %d element har en näst bästa "
                       "tilldelning som ligger för nära — lämnade obundna "
                       "för advokaten" % (reg, svag_marginal, len(lösn)))
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


def _tal_forskjutning(els, rows, skala, svarta, korning, jamnt=True,
                      flerradiga=False, gap=None):
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
    full = _full_bredd(rows) if flerradiga else None
    indrag = _indragna(rows) if flerradiga else None
    betrodda = _betrodda(rows) if flerradiga else None
    rubrik = _rubrikband(rows) if flerradiga else None
    hopp = _hoppstraff(rows, svarta)
    bas = 0.0
    for i, rr, _m in korning:
        c = _radkostnad(els[i], rows, rr[0], rr[-1] + 1, skala, svarta,
                        flerradiga, full, indrag, hopp, gap, betrodda, rubrik)
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
            c = _radkostnad(els[i], rows, a, b, skala, svarta, flerradiga,
                            full, indrag, hopp, gap, betrodda, rubrik)
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
        mat = json.loads(rb.read_text(encoding="utf-8"))
        sidor[n] = (f, json.loads(f.read_text(encoding="utf-8")),
                    _rader(mat), png if png.exists() else None, mat)
    return sidor


def _domare(el, rows, facit, mitt, skala, svarta, flerradiga=False,
            full=None, indragna=None, hopp=None, gap=None, betrodda=None,
            rubrikband=None):
    """Vilken av två bindningar som passar TRYCKET bäst: 'mitt', 'facit' — eller
    `None` när måttet inte kan skilja dem åt.

    Utan den här domen är utvärderingen missvisande. Facit är en tidigare
    transkription, inte sanning: i del II binder facit sidhuvudet `SPELLEDARENS
    UPPGIFT` till rad 60 mitt på s. 6, och element 52 till rad 1 på s. 17. En
    ren agreement-siffra hade räknat de fallen som verktygets fel. Domaren
    använder samma uppmätta breddsamband som bindningen själv — det är inte ett
    oberoende mått, men det är ett mått, och när trycket säger emot facit går
    det att se.

    Domen fälls i BOKENS regim. Utan `flerradiga` fick varje flerradigt spann
    kostnaden "omöjlig" på båda sidor och blev oskiljbart: på Lovligt byte
    dömdes 8 av 11 avvikelser till oavgjort fast facit — advokatdömt mot
    trycket band för band — vann 8 av dem i regimens eget mått. Och en dom
    kräver en mätbar skillnad (DOMSKILLNAD): 0,003 i kostnad är brus.
    """
    a = _radkostnad(el, rows, facit[0], facit[-1] + 1, skala, svarta,
                    flerradiga, full, indragna, hopp, gap, betrodda,
                    rubrikband)
    b = _radkostnad(el, rows, mitt[0], mitt[-1] + 1, skala, svarta,
                    flerradiga, full, indragna, hopp, gap, betrodda,
                    rubrikband)
    a = MAX_KOSTNAD * 10 if a is None else a
    b = MAX_KOSTNAD * 10 if b is None else b
    if abs(a - b) < DOMSKILLNAD:
        return None
    return "mitt" if b < a else "facit"


def _syntetiska_stycken(els):
    """Slå ihop enradiga paragrafer till STYCKEN, med facit bevarat.

    Styckeregimen kan inte prövas mot någon befintlig bok: del I–III är
    transkriberade rad för rad och de 29 äventyrsböckerna har ingen bindning
    alls. Utan ett prov får den flerradiga bindningen enligt repots egen regel
    inte skrivas — ett verktyg som inte kan återskapa en känd bindning får inte
    skriva en okänd.

    Provet går ändå att bygga, och det behöver inget nytt facit: en följd av
    enradiga paragrafer som hör till SAMMA tryckta stycke slås ihop till ett
    element, och facit blir unionen av deras rader. Det enda som är syntetiskt
    är elementindelningen — geometrin, texten och sanningen är verkliga.

    Var styckena går avgörs av `pipeline.export._starts_paragraph`, alltså av
    pipelinens EGEN definition och inte av en ny. Det spelar roll: slås raderna
    ihop blint, till löpande körningar, slutar de syntetiska styckena var som
    helst i satsen i stället för på en kort utsluten rad. Provet blir då både
    orättvist och orepresentativt — riktiga styckeformade transkript slutar
    alltid vid ett tryckt styckeslut, för det är vad en läsare ser.
    """
    from pipeline.export import _bbox as _ebbox, _starts_paragraph

    boxar = [b for b in (_ebbox(e) for e in els) if b]

    def samma_stycke(i):
        """Hör els[i] till samma tryckta stycke som els[i - 1]?"""
        nxt = els[i + 1] if i + 1 < len(els) else None
        return not _starts_paragraph(els[i], els[i - 1], nxt, boxar, boxar)

    def enradig(el):
        return (el.get("type") == "paragraph"
                and len((el.get("source") or {}).get("rader") or []) == 1)

    ut, i = [], 0
    while i < len(els):
        el = els[i]
        if not enradig(el):
            ut.append(el)
            i += 1
            continue
        grupp, rader = [el], list(el["source"]["rader"])
        j = i + 1
        while (j < len(els) and enradig(els[j])
               and _region(els[j]) == _region(el)
               and els[j]["source"]["rader"][0] == rader[-1] + 1
               and samma_stycke(j)):
            grupp.append(els[j])
            rader.append(els[j]["source"]["rader"][0])
            j += 1
        if len(grupp) < 2:
            ut.append(el)
            i += 1
            continue
        # Texten fogas ihop som exporten gör det: avstavning läks, annars
        # mellanslag. Teckenlängden är hela poängen med provet och måste bli
        # den ett riktigt styckeformat transkript hade haft.
        bitar = []
        for g in grupp:
            s = (g.get("text") or "").strip()
            if bitar and bitar[-1].endswith("-"):
                bitar[-1] = bitar[-1][:-1] + s
            else:
                bitar.append(s)
        källa = dict(el.get("source") or {})
        källa["rader"] = rader
        ut.append({"id": el.get("id"), "type": "paragraph",
                   "text": " ".join(bitar), "source": källa})
        i = j
    return ut


def utvardera(sidor, skala, flerradiga=False, stycken=False):
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
    for n, (_, d, rows, png, mat) in sorted(sidor.items()):
        els = d.get("elements") or []
        if stycken:
            els = _syntetiska_stycken(els)
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
        bind, _ = binda_sida(rensade, rows, skala, png=png,
                             flerradiga=flerradiga, radboxar=mat)
        svarta = _svarta(rows, png)
        # Domen fälls i samma rum som bindningen: regionens egna rader, med
        # regionens egna mått. I det globala radrummet räknades främmande
        # regioners band in i spannets bredd — facits [79, 82] på Lovligt
        # byte s. 5 spänner två vänsterspaltsrader den aldrig rör.
        karta, _oov, _tva = _oversatt(els, mat)
        radreg = _radregioner(rows, measured_columns(mat or {}))
        regmått = {}
        for reg in set(karta.values()):
            ridx = [j for j in range(len(rows)) if radreg[j] == reg]
            delrows = [rows[j] for j in ridx]
            regmått[reg] = (
                {j: p for p, j in enumerate(ridx)}, delrows,
                [svarta[j] for j in ridx],
                _full_bredd(delrows) if flerradiga else None,
                _indragna(delrows) if flerradiga else None,
                _hoppstraff(delrows, [svarta[j] for j in ridx]),
                _morka_gap(delrows, png),
                _betrodda(delrows) if flerradiga else None,
                _rubrikband(delrows) if flerradiga else None)
        sid_fel = 0
        for i, rr in facit.items():
            if i not in bind:
                utan += 1
            elif bind[i] == rr:
                rätt += 1
            else:
                fel += 1
                sid_fel += 1
                (lok, delrows, delsv, full, indrag, hopp, gap, betro,
                 rubrik) = regmått[karta[_region(els[i])]]
                if all(j in lok for j in rr) and all(j in lok for j in bind[i]):
                    dom[_domare(els[i], delrows,
                                [lok[j] for j in rr],
                                [lok[j] for j in bind[i]], skala, delsv,
                                flerradiga, full, indrag, hopp, gap,
                                betro, rubrik)] += 1
                else:
                    # Facit binder över regionvokabulärens gräns (klippta
                    # kolumnskivor) — måttet kan inte ens uttrycka den
                    # tilldelningen, alltså ingen dom.
                    dom[None] += 1
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
    ap.add_argument("--utvardera-stycken", action="store_true",
                    dest="utvardera_stycken",
                    help="samma prov, men med enradiga paragrafer hopslagna "
                         "till stycken — provar den STYCKEFORMADE regimen")
    ap.add_argument("--verkstall", action="store_true")
    a = ap.parse_args(argv)

    wd = a.workdir
    if not (wd / "pages").is_dir():
        ap.error("%s ser inte ut som en arbetskatalog" % wd)
    alla = _lasin(wd)
    if not alla:
        ap.error("inga sidor med både final.json och radboxar.json")

    sidprov = [(d.get("elements") or [], rows, mat)
               for _, d, rows, _png, mat in alla.values()]
    skala, källa = _skala(sidprov), "bokens egna bundna rader"
    if skala is None:
        skala, källa = _skala_ur_bevarande(sidprov), "bevarandeidentiteten"
    if skala is None:
        ap.error("skalan går inte att mäta: varken bundna rader eller "
                 "tillräckligt många regioner med både sats och band")
    flerradiga = _flerradig_regim(sidprov, skala)
    print("Skala: %.1f tecken per breddenhet (mätt ur %s)" % (skala, källa))
    print("Regim: %s" % ("STYCKEFORMAD — ett element spänner flera rader"
                         if flerradiga else
                         "radformad — ett element per tryckt rad"))

    if a.utvardera or a.utvardera_stycken:
        # Exitkoden speglar domen, inte avvikelseantalet: verktyget underkänns
        # när facit passar trycket bättre oftare än verktyget gör.
        läge = bool(a.utvardera_stycken) or flerradiga
        return 0 if utvardera(alla, skala, läge,
                              a.utvardera_stycken) <= 0 else 1

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
    for n, (f, d, rows, png, mat) in sorted(alla.items()):
        els = d.get("elements") or []
        redan = sum(1 for el in els if (el.get("source") or {}).get("rader"))
        bind, anm = binda_sida(els, rows, skala, png=png,
                               flerradiga=flerradiga, radboxar=mat)
        nya = {i: rr for i, rr in bind.items()
               if not (els[i].get("source") or {}).get("rader")}
        # DP:n räknar utan att se de redan skrivna bindningarna — den kan
        # alltså föreslå ett band som en DÖMD bindning redan äger (på s. 2
        # föreslogs p002_e12 på exakt de fyra band p002_e11 bär). Ett sådant
        # förslag skrivs aldrig: två ägare till samma band är ett fel som
        # ser ut som data.
        upptagna = set()
        for el in els:
            upptagna.update((el.get("source") or {}).get("rader") or [])
        krockar = {i for i, rr in nya.items() if set(rr) & upptagna}
        if krockar:
            anm.append("%d förslag krockar med redan dömda bindningar — "
                       "släppta" % len(krockar))
            nya = {i: rr for i, rr in nya.items() if i not in krockar}
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
