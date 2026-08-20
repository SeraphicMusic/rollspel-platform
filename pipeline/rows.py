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
     x-led inom sin egen spalt — utan ramens lodräta linjer, som annars sätter
     varje bands x och suddar styckeindragen (`_rule_mask`).
  7. Ett ANDRA SVEP går igenom de luckor som rymmer en rad och mäter dem mot
     luckans egen profil. Den korta, glesa slutraden (`de ting.`, `sen:`,
     `sm.`) toppar på ungefär halva grannradernas svärta och faller därför på
     den lokala tröskeln i steg 3 — se `_sparse_bands`. Banden märks `svep: 2`.

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

Ommätt 2026-08-05 ur den arkiverade PDF:en i en KASTBAR arbetskatalog (del I:s
egen `arbete/` rörs inte): 3953 kända bbox, **93,50 % före andra svepet och
ramsållningen, 95,09 % efter**. Siffran 98,5 ovan gäller den mätning som
faktiskt skrev del I:s boxar och går inte att återskapa med dagens motor — den
står kvar som historik, inte som dagens facit. Verifieringen mot del III:s
tjugotre handmätta glesa slutrader (BQ-002 a) gick samtidigt 1 → 19.

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
# Var i sidbredden en ränna får ligga för att räknas som SPALTränna. Marginaler
# och indrag ger också tomma stråk, men inte mitt på satsytan.
GUTTER_CENTRE_LO = 0.30
GUTTER_CENTRE_HI = 0.70

# Hur djup en dal i bandets svärtningsprofil måste vara för att räknas som
# ränna, som andel av profilens EGET omfång (`lo + andel * (hi - lo)`). Måttet
# är relativt därför att en absolut tröskel blir blind på en skanning med grå
# botten — se `_band_gutters`. Nivån är kalibrerad, inte gissad: svept mot 87
# sidor vars spaltantal går att läsa ur transkriptets egna regionnamn, och
# 0,45 tillsammans med rösttröskeln nedan ger 67 rätt mot den gamla mätningens
# 22. På de genuint tvåspaltiga sidorna blir den något bättre, inte sämre.
GUTTER_CONTRAST = 0.45

# Hur stor andel av de RÖSTANDE banden som måste vara tomma på samma bildkolumn
# för att den ska höra till en ränna (se `_columns`).
#
# Nivån är en AVVÄGNING mellan rännans antal och dess läge, och läget vinner.
# En lägre tröskel hittar fler rännor — 0,50 gav 69 rätt mot 67 — men släpper
# samtidigt fram BQ-013:s gamla fel: på en sida med korta rader börjar varje
# bands egen tomma yta direkt efter radens sista ord, och med hälften av banden
# korta röstas en ränna fram där texten slutar i stället för där satsytan tar
# slut. Följden är att spaltens fönster klipper av dess egen text — det som på
# del III s. 13 lade rännan vid x 0,332 i stället för 0,49. Två sidor färre med
# rätt spaltantal är billigare än en spalt som kapar sin egen sats.
COLUMN_VOTE_SHARE = 0.75
# Hur stor andel av avsnittets radband som måste ha en egen ränna på samma
# ställe för att spalterna ska räknas som verkliga. En illustration korsar
# rännan och röstar nej; brödtexten röstar ja. Uppmätt på del II: friska
# tvåspaltssidor 89–94 %, sidor med helsidesbred illustration 61–74 %, och
# titelsidan (verkligt enspaltig) 0 %. Hälften skiljer arterna med marginal.
GUTTER_VOTE_SHARE = 0.5

# Golvet för korridorens HYSTERES (se `_columns`): en 75 %-kärna utvidgas åt
# båda hållen så länge rösterna når hit. Nivån ligger i en uppmätt lucka.
# En VERKLIG rännas flanker hyvlas till 0,69–0,73 av nästan-fulla rader —
# radresten efter dem är smalare än MIN_GUTTER_WIDTH i det egna bandet och
# röstar då på ingenting (Skymningslandet s. 1: kärnan 23 px av rännans
# fysiska 42). En FALSK ränna vid korta raders slut (BQ-013) samlar högst
# ~0,58 där texten fortfarande står. 0,65 skiljer arterna åt med marginal
# åt båda hållen.
GUTTER_EDGE_VOTE_SHARE = 0.65

# --- Illustrationsblock -----------------------------------------------------
#
# Ett spaltblock kan vara en BILD, inte en textspalt: Skymningslandets svarta
# ZONEN-balk mättes som en del av högerkolumnen, och Tempokalkylatorns
# helsidesillustration blev en egen `vänsterkolumn` vars tonband bands till
# textelement (BQ-001 i båda böckerna). Två mätta signaler skiljer arterna, och
# ingen gråstatistik gör det (mellantonandelen överlappar: illustration 0,09–
# 0,40, text 0,09–0,26 — uppmätt över sex böcker):
#
#   1. BLÄCKANDELEN i blocket. Textspalter ligger på 0,05–0,25 (rastrerad tät
#      sats som mest 0,25, och med marginalgrafik inräknad som mest 0,374);
#      rena bildytor på 0,42–1,0. Tvetydiga block i 0,25–0,40 finns (text med
#      marginalgrafik, mörka rubriker) och får ALDRIG stämplas — sats som
#      klassas som bild förlorar sin geometri, och det felet är dyrare än
#      varje bildband som slinker igenom.
#   2. Y-KONTINUITETEN. Ingen textrad kan bo i en segmentlucka, och ingen sats
#      löper 16 radhöjder utan en blank profilrad (radmellanrummen är binärt
#      tomma; en tonplatta binariseras vit — uppmätt svärta 85–90 av 255 mot
#      binärgränsen 127). En illustration gör båda: Tempokalkylatorns bildyta
#      har bläck i 100 % av segmentluckans rader där texten har 0–2 %, och
#      ZONEN-balken löper obruten över hela satshöjden. Ramlinjer fejkar inte
#      kontinuitet: en linje är 1–3 px av blockbredden (minst ~235 px) och
#      når aldrig radandelen 0,05.
#
# Kriterierna nedan är prövade mot samtliga block i sex böcker (930 block):
# varje flaggat block var en verifierad bildyta (avdelarsidor, helsides-
# illustrationer, ZONEN-balken, ornamentspalter) och inte ett enda innehöll
# sats. En bildyta kan dessutom skifta karaktär mellan segmenten — samma
# målning i Tempokalkylatorn mäter 0,74 / 0,13 / 0,89 i bläckandel uppifrån
# och ned — därför PROPAGERAR flaggan i `measure_dark` till grannblock som
# hänger ihop med ett flaggat block tvärs igenom segmentgränsen.
ILLUSTRATION_INK_SHARE = 0.40
# Över den här bläckandelen är blocket en bildyta på andelen ENSAM: korpusens
# mörkaste textblock (rastrerad tät sats) når 0,25 och med marginalgrafik
# 0,374; rena bildytor utan radstruktur (Tempokalkylatorns täta bildtopp)
# ligger 0,55–1,0. Marginalen åt textsidan är 0,18.
ILLUSTRATION_SOLID_SHARE = 0.55
# Andel binärt bläck i en profilrad som gör raden BLÄCKFÖRANDE i
# kontinuitetsmätningen. En ramlinje (1–3 px + halo av ~600) når ~0,02; en
# tonyta eller balk 0,3–1,0.
ILLUSTRATION_ROW_INK = 0.05
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
# --- Andra svepet: den korta, glesa slutraden -------------------------------
#
# Den lokala tröskeln i `_profile_bands` sätts mitt emellan lokalt golv och
# lokal topp, och fönstret (3 % av sidhöjden ≈ två radavstånd) domineras av
# grannradernas fulla sats. En slutrad på två–tre glyfer når inte dit: uppmätt
# på del III s. 39 toppar `den.` på 40,0 mot tröskeln 41,6 — den föll på 1,6
# enheter. Samma art är belagd tjugosex gånger i den bokens BQ-002, med
# handmätta referenser, och kostnaden står i läsexporten: utan bbox bryter
# `_starts_paragraph` stycket mitt i det avstavade ordet (`levan-` / `de ting.`).
#
# Tröskeln kan inte bara sänkas. Dalen mellan två normala rader når aldrig
# papper (staplar och diakriter hakar i varandra, uppmätt ~44 % av toppen), och
# en glesrad toppar på ungefär samma nivå — en enda global tröskel kan alltså
# inte både skilja två rader åt och fånga den glesa. Därför ett ANDRA svep, som
# bara tittar i luckor där en rad OVER HUVUD TAGET får plats, och där mäter mot
# luckans egen profil i stället för mot grannradernas.
#
# Luckan måste rymma en rad: minst spaltens egen medianbandhöjd.
SPARSE_GAP_FACTOR = 1.0
# En osynlig rad skapar den lucka som `_segments` sedan delar avsnittet vid, så
# raden hamnar ofta PÅ avsnittsgränsen. Svepet får därför sträcka sig en radhöjd
# förbi gränsen; dubbletter mot nästa avsnitts band rensas efteråt.
SPARSE_TAIL_FACTOR = 1.0
# Bläckspärren, och den enda signal som mätningen visade skiljer arterna:
# kandidatens mörkaste pixel mot spaltens egna bands mörkaste. En gles rad är
# GLES, inte BLEK — glyferna är svarta, det är antalet som är litet. Uppmätt
# över 191 kandidater på del III:s femton facitsidor: äkta rader 0,6–1,0 (p05
# 0,9), och de två kandidater som saknade bläck helt låg på 0,48 och 0,49 (det
# grå zebrarastret på s. 26). Profilens egen topp skiljer INTE — där överlappar
# arterna fullständigt (äkta 0,23–1,28, falska 0,39–0,50).
SPARSE_INK_SHARE = 0.55
# En bildkolumn räknas som bläck i ramsållningen vid den här andelen av
# satssvärtan, och som LODRÄT LINJE när den är bläck i minst den här andelen av
# luckans höjd. En textrad fyller aldrig en hel lucka i y-led; en ramlinje gör
# ingenting annat.
RULE_INK_SHARE = 0.3
RULE_RUN_SHARE = 0.8
# Bredaste lodräta klunga som får räknas som LINJE, som andel av sidbredden.
# En ramlinje mäter 1–3 px (0,0005–0,0015); en mörk illustrationskant är
# tiotals gånger bredare. Utan taket äter masken bilden inifrån, och det var
# just det som fällde det förra försöket att sålla bort ramar (BQ-013).
MAX_RULE_WIDTH = 0.006
# Hur högt fönstret kring ett band mäts för ramlinjer, i radhöjder åt vardera
# hållet. Se `_rule_mask`: skevningen sätter taket, glyfhöjden golvet.
RULE_CONTEXT_FACTOR = 1.5
# Största andel av ett fönster som ramsållningen får maska bort. En ram är en
# eller två linjer (0,5 % av fönstret); en skrafferad illustration är dussintals
# och skulle annars ätas inifrån.
MAX_RULE_SHARE = 0.05
# En kandidat måste vara en RAD, inte en flisa. Första svepet sållar flisor mot
# `MIN_BAND_FACTOR` (0,25), men i en lucka räcker inte det: understyckena under
# en normal rad ligger 7–9 px och slapp igenom (63 falska band på s. 13).
# Uppmätt mot facit: de tjugosex handmätta glesa raderna mäter 14–26 px mot
# sidans radhöjd 24–26, alltså 0,54–1,0 — flisorna 0,27–0,35. Gränsen läggs
# däremellan.
SPARSE_HEIGHT_FACTOR = 0.45
# Hur många gånger ett fönster får skalas av och mätas om. Tre räcker för
# bokens mätta fall (rubrik + ramlinje + rad i samma lucka); djupare svep
# hittade inget nytt på facitsidorna.
SPARSE_DEPTH = 3

# --- Klungdelning: band som korsar grafiska streck (BQ-021 c) ---------------
#
# På en måttavla (del III s. 49, sju stångvapen ritade lodrätt) korsar varje
# vågrät textrad — måttetiketten `250 cm`, de lodräta vapennamnen — samtliga
# skaft, och bandet mäts från etiketten till sista skaftet: 1426 px brett med
# 232 px bläck. Kvoten bandbredd/bläckbredd skiljer arterna utan överlapp,
# uppmätt på sidans egna band: friska textrader 1,00–1,90 (per-glyf-luckorna
# försvinner när bläckrunsen klustras med en radhöjds fogavstånd), sjuka band
# 4,5–10,8. Svärtningsandel duger INTE som vakt (uppmätt i BQ-posten).
#
# Vakten mot att dela en GLES TABELLRAD i sina celler är korsningskravet:
# bandet delas bara när minst två run är streck som LÖPER IGENOM bandet
# och fortsätter på båda sidor (ett skaft går genom hela mätavlan; en
# tabellcells siffror slutar vid radens kant). Strecken är också klungornas
# GRÄNSER: en klunga fogas aldrig ÖVER ett korsande streck, och det är så
# `Bredsvärd`-etiketten skiljs från sin streckade måttlinje trots att gapet
# (30 px) är mindre än radhöjden (42) — ett gapmått klarade inte det utan
# att samtidigt dela friska raders ordmellanrum (uppmätt: 86 felaktigt
# delade band på en frisk tvåspaltssida vid fogfaktor 0,6).
SPLIT_RATIO = 2.5
# Minsta antal genomkorsande streck för delning.
SPLIT_CROSSINGS = 2
# Ett korsande STRECK är smalt: skaften på måttavlan mäter 10–25 px och de
# streckade måttlinjerna 3–4 px (0,002–0,013 av sidbredden), medan en
# ordklunga är 40+ px. Utan taket räknades ordet `Bälte` (73 px) som ett
# korsande streck — i tät sättning ligger grannradernas staplar inom tre
# pixlar ovanför och nedanför varje ord, och varje tabellrad delades.
SPLIT_MAX_CROSS_WIDTH = 0.018
# ... och största antal, per pixel bandbredd. En måttavlas skaft är GLESA
# (uppmätt: 7 skaft på 1426 px = 0,005/px; Bredsvärds två måttlinjer på
# 900 px = 0,002/px), medan en skrafferad illustrations streck korsar vart
# tionde px (uppmätt: 10 på 383 px = 0,026/px). Ett band inne i konst ska
# inte delas — dess "klungor" är skrafferingens luckor, inte innehåll.
SPLIT_MAX_CROSS_DENSITY = 0.01
# Minsta bläckandel genom bandet i en kolumn för att ett run ska räknas som
# GENOMLÖPANDE. Uppmätt: heldragna skaft 1,0; STRECKADE måttlinjer (del III
# s. 48, kring `Bredsvärd`) 0,44–0,48; en vågrät punktlinjes kolumner ~0,1.
# En bokstavsstapel når också högt, men sållas av kravet på bläck omedelbart
# OVANFÖR och NEDANFÖR bandet — det har inga glyfer, bara genomlöpande streck.
SPLIT_CROSS_RUN = 0.35

# --- Kantskugga (BQ-001, MUT-AVE-skymningsmorker) ---------------------------
#
# Skannerns gråa kantskugga ligger i pappersmarginalen och registreras som
# bläck: på s. 1 drog den fem band ut till x≈0 (facit: spaltens 0,086), på
# s. 4 slog den på HÖGERkanten (en isolerad fläck 0,93 < x < 0,985 gav e149
# bredd 0,327 mot spaltens 0,268), och på s. 5 födde den ett helt FANTOMBAND i
# nedre vänstra hörnet som sidfoten bands till. Maskeringen måste därför sitta
# FÖRE bandindelningen, inte bara i bandets x-mätning.
#
# Skuggan skiljs från sats på sin svärta: uppmätt över fem sidor toppar den
# på 0,53–0,64 av sidans satssvärta (s. 5:s hörnfläck är värst: svärta 163 mot
# ink_ref 255 i mätupplösningen), medan en kolumn genom en verklig glyf når
# nära fullsvärta — trycket är svart, det är skuggan som är grå. En bildkolumn
# eller bildrad UTAN någon pixel över den här andelen av satssvärtan innehåller
# alltså ingen sats, och närmast sidkanten är den skugga eller tom marginal —
# båda maskas riskfritt.
EDGE_INK_SHARE = 0.7
# Hur långt in från varje sidkant sådana tomma kolumner/rader får nollas, som
# andel av sidmåttet. Uppmätt: skuggorna når som längst in till x=0,085
# (textmarginalen börjar 0,086); folio och sidfot ligger innanför 0,05 från
# underkanten men har glyfsvärta och stoppar svepet själva. Taket finns för
# att en nästan tom sida inte ska få halva satsytan nollad.
EDGE_MASK_MAX = 0.12

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


def _rule_mask(block):
    """Bildkolumner som är en LODRÄT LINJE genom hela fönstret.

    En inramad sida (del III s. 13) har ramens lodräta linje inne i
    spaltfönstret, och `_extent` mäter då varje band från ramen i stället för
    från satsen: alla 47 vänsterband fick x 0,0735, och styckeindragen —
    0,018–0,019, som är hela BQ-013:s facit för indragen — försvann.

    Två krav, båda nödvändiga och båda mätta: kolumnen ska vara bläck i minst
    `RULE_RUN_SHARE` av fönstrets höjd (ingen textkolumn är det över tre
    radhöjder), och den sammanhängande klungan sådana kolumner ska vara smalare
    än `MAX_RULE_WIDTH` av sidbredden. Utan breddkravet äter masken en mörk
    illustration inifrån — det var därför det förra försöket revs upp
    (BQ-013, anteckningen om `grafik`-klassningen).

    Fönstret måste vara KORT. Mätt över ett helt avsnitt hittas ingen linje
    alls: s. 13 är skevad 0,27°, och över 2000 px vandrar ramen nio pixlar i
    sidled, så ingen enskild bildkolumn är bläck hela vägen. Över tre radhöjder
    är vandringen under en halv pixel, och en bokstav är fortfarande bara en
    tredjedel så hög som fönstret.
    """
    if block.shape[0] < 3 or not block.size:
        return None
    level = RULE_INK_SHARE * float(np.percentile(block, 99.9))
    if level <= 0:
        return None
    rule = (block >= level).mean(axis=0) >= RULE_RUN_SHARE
    if not rule.any():
        return None
    limit = max(2, int(MAX_RULE_WIDTH * block.shape[1]))
    mask = np.zeros(block.shape[1], dtype=bool)
    for a, b in _runs(rule):
        if b - a <= limit:
            mask[max(0, a - 1):b + 1] = True   # linjens halo hör till linjen
    if not mask.any():
        return None
    # En SKRAFFERAD illustration är också smala lodräta streck genom hela
    # fönstret — dussintals av dem. Masken skulle äta bildpartiet inifrån, och
    # det var precis så det förra ramförsöket föll (BQ-013): en texturerad yta
    # slutade klassas som `grafik`. En ram är en eller två linjer; går masken
    # över några få procent av fönstret är det inte en ram, och då maskas
    # ingenting.
    if mask.mean() > MAX_RULE_SHARE:
        return None
    return mask


def _extent(dark, top, bottom, lo, hi, ignore=None):
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
    if (ignore is not None and len(ignore) == block.shape[1]
            and not ignore.all() and block[:, ~ignore].max()):
        # Ramens lodräta linje är inte radens bläck. Utan den här maskningen
        # mäts varje band från ramen och styckeindragen försvinner (s. 13).
        block = block[:, ~ignore]
        keep = np.flatnonzero(~ignore)
    else:
        keep = None
    prof = block.max(axis=0)
    if not len(prof) or not prof.max():
        return None
    if keep is not None:
        def _out(i0, i1):
            return lo + int(keep[i0]), lo + int(keep[i1]) + 1
    else:
        def _out(i0, i1):
            return lo + int(i0), lo + int(i1) + 1
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
                return _out(hits[0], hits[-1])
        # Ingen kontrast alls: ett massivt ornament, t.ex. linjeregeln. Det
        # mäts på svärtan nedan och behåller sin fulla bredd.
    hits = np.flatnonzero(prof >= MIN_DARKNESS_SHARE * prof.max())
    if not len(hits):
        return None
    return _out(hits[0], hits[-1])


def _without_rules(block, ink_ref):
    """Fönstret utan sina LODRÄTA linjer, eller None om inget blir kvar.

    En inramad sida (del III s. 13) har ramens lodräta linje inne i varje
    spaltfönster. I första svepet spelar den ingen roll — där sätter satsen
    tröskeln — men i en tom lucka är den det enda bläcket, och då lyfter den
    profilens golv så jämnt att varje krusning blir ett band: 58 falska
    "rader" på s. 13, alla med x på ramens 0,073 och 7–9 px höga.
    Linjen känns igen på att den är bläck HELA vägen genom luckan, vilket
    ingen textrad är.
    """
    if not block.size:
        return None
    ink = block >= RULE_INK_SHARE * ink_ref
    rule = ink.mean(axis=0) >= RULE_RUN_SHARE
    # Linjens HALO hör till linjen. En 2 px bred ramlinje lämnar en gråzon på
    # var sida som inte når svärtningskravet men bär hela dess kontrast — utan
    # den här utvidgningen överlevde s. 13:s 58 falska band ramsållningen med
    # oförändrat antal.
    rule = rule | np.roll(rule, 1) | np.roll(rule, -1)
    if rule.all():
        return None
    return block[:, ~rule]


def _scan_window(dark, a, b, lo, hi, median, page_median, ink_ref, depth=0):
    """Sök rader i ETT fönster, och skala av dess starkaste struktur.

    En enda tröskel per lucka räcker inte. Ligger det en tabellramslinje eller
    en fet rubrik i luckan sätter DEN nivån, och av den glesa raden sticker
    bara topparna upp — 1–2 px höga flisor som höjdkravet med rätta sållar
    bort. Uppmätt på del III s. 40 (`den.`, nivå 35,3 mot radens 41,3 men
    dominerad av en struktur på 70,7), s. 44 (`sm.`, 34,6/35,9/69,3) och s. 45
    (`FYS.`, nivå 37,2 mot radens 32,5).

    Därför mäts fönstret om: den starkaste sammanhängande strukturen skalas
    bort och de två resterna mäts mot SIN egen profil. Det är samma princip
    som gör hela andra svepet meningsfullt — mät mot det som finns i fönstret,
    inte mot grannens sats — bara tillämpad ett steg till.
    """
    if b - a < median * SPARSE_GAP_FACTOR or depth > SPARSE_DEPTH:
        return []
    block = _without_rules(dark[a:b, lo:hi], ink_ref)
    if block is None:
        return []
    prof = row_profile(block)
    if not len(prof) or not prof.max():
        return []
    level = prof.min() + LOCAL_FRACTION * (prof.max() - prof.min())
    runs = _runs(prof >= level)
    out = []
    for r0, r1 in runs:
        top, bottom = a + int(r0), a + int(r1)
        # Höjdvakten mäter mot det MINDRE av spaltens och sidans radmått. Ett
        # segment med ett par band har ingen egen radhöjd att tala om — dess
        # "median" är rubrikens grad eller en ensam lucka. Spindelkonungen
        # s. 11 (BQ-007) föll exakt så: segmentet ovanför `säga).` har två
        # band, måttet blev 49 px mot sidans 30, och den 22 px höga raden
        # föll på 0,45 x 49 = 22,05 med fem hundradels pixel. Fönster- och
        # marginalmåtten behåller spaltens median — att sänka DEM öppnar
        # grafikblockens luckor för fragmentjakt (uppmätt: 404 svepband på
        # en omslagssida när hela måttet byttes mot sidans).
        rad_matt = min(median, page_median) if page_median else median
        if bottom - top < rad_matt * SPARSE_HEIGHT_FACTOR:
            continue  # flisa, inte rad
        if min(top - a, b - bottom) < median * MERGE_GAP_FACTOR:
            continue  # sitter ihop med grannraden: dess understycken
        if block[r0:r1].max() < SPARSE_INK_SHARE * ink_ref:
            continue  # papper eller raster, inte sats
        out.append((top, bottom, KIND_ROW))
    if runs:
        peak = int(np.argmax(prof))
        dom = next(r for r in runs if r[0] <= peak < r[1])
        for sub_a, sub_b in ((a, a + int(dom[0])), (a + int(dom[1]), b)):
            out += _scan_window(dark, sub_a, sub_b, lo, hi, median,
                                page_median, ink_ref, depth + 1)
    return out


def _sparse_bands(dark, bands, seg_top, seg_bottom, lo, hi, page_median):
    """Andra svepet: rader som den lokala tröskeln inte kunde se.

    Bara luckor som RYMMER en rad prövas, och i varje sådan lucka mäts
    profilen mot luckans egen botten och topp. Det är hela skillnaden: i
    första svepet sätts tröskeln av grannradernas fulla sats, i det andra av
    det som faktiskt finns i luckan.

    Bläckspärren gör att papper inte blir rader. En kandidat måste nå
    `SPARSE_INK_SHARE` av spaltens egen satssvärta — en gles rad är gles, inte
    blek. Den spärren är riktningen på felet värd: en box som fattas är alltid
    tillåten, en påhittad box är ett fel som ser ut som data (AGENTER.md
    Regel 9).
    """
    if not bands:
        return []
    # Radmåttet är bandhöjden ELLER luckan mellan banden, det största av dem —
    # samma degenerationstest som `_merge_and_classify` gör med MERGE_GAP_SHARE.
    # På en sida med liten grad (del I s. 34, registerlika tabeller) delas varje
    # tryckt rad i fragment, medianhöjden blir 2–4 px, och då rymmer VARJE
    # mellanrum "en rad": svepet gav 193 fragmentband på den enda sidan. Luckan
    # är i det läget det enda måttet som fortfarande mäter en rad.
    median = max(_median_height(bands), _median_gap(
        [(a, b) for a, b, *_ in bands])) or 1
    ink_ref = _median_of([float(dark[a:b, lo:hi].max()) for a, b, *_ in bands])
    if not ink_ref:
        return []
    windows = [(bands[i][1], bands[i + 1][0]) for i in range(len(bands) - 1)]
    windows.append((seg_top, bands[0][0]))
    windows.append((bands[-1][1],
                    min(seg_bottom + int(SPARSE_TAIL_FACTOR * median),
                        dark.shape[0])))
    out = []
    for a, b in windows:
        out += _scan_window(dark, a, b, lo, hi, median, page_median, ink_ref)
    # Samma rad kan hittas både före och efter avskalningen. Den högsta
    # kandidaten vinner — den är hela raden, de andra är dess delar.
    kept = []
    for top, bottom, kind in sorted(out, key=lambda r: r[0] - r[1]):
        if any(min(bottom, b) - max(top, a) > 0 for a, b, _ in kept):
            continue
        kept.append((top, bottom, kind))
    return sorted(kept)


def _covered_elsewhere(cand, rows):
    """Täcks andrasvepsbandet av ett band från FÖRSTA svepet någon annanstans?

    Bara första svepets band räknas som ägare. Två andrasvepsband som råkar
    överlappa varandra får leva: de kommer från olika spalter och kan vara två
    rader på samma höjd.
    """
    top, bottom = cand["_span"]
    höjd = (bottom - top) or 1
    x0, bredd = cand["bbox"][0], cand["bbox"][2]
    for r in rows:
        if r is cand or r.get("svep") == 2 or "_span" not in r:
            continue
        a, b = r["_span"]
        if min(bottom, b) - max(top, a) <= 0.5 * höjd:
            continue
        rx0, rbredd = r["bbox"][0], r["bbox"][2]
        if min(x0 + bredd, rx0 + rbredd) - max(x0, rx0) > 0:
            return True
    return False


def _drop_overlaps(rows, extra):
    """Rensa andrasvepsband som redan täcks av ett band från första svepet.

    Svansfönstret sträcker sig förbi avsnittsgränsen och kan därför nå in i
    nästa avsnitts första rad. Överlappar kandidaten ett befintligt band med
    mer än halva sin höjd är den samma rad en gång till.
    """
    kept = []
    for cand in extra:
        top, bottom = cand["_span"]
        höjd = bottom - top
        dubblett = False
        for r in rows:
            a, b = r["_span"]
            över = min(bottom, b) - max(top, a)
            if över > 0.5 * höjd or (b - a and över > 0.5 * (b - a)):
                dubblett = True
                break
        if not dubblett:
            kept.append(cand)
            rows = rows + [cand]
    return kept


def _heal_split_rows(dark, rows, boundaries, width, height,
                     page_median=None):
    """Foga en tryckt rad som en mätgräns har delat i två band (BQ-021 a).

    Blockindelningen är sidgemensam, så en zon- eller avsnittsgräns kan gå
    rakt genom en rad i den ena spalten därför att samma höjd är vitrymd i
    den andra: raden mäts då som två band vars kanter SAMMANFALLER exakt på
    gränsen (del III s. 32 `Beröring`, delad vid y 0,504286; s. 40
    `DRAKFJÄLL`, delad mot sidhuvudszonen). Grannband ur SAMMA profil ligger
    alltid minst en pixel isär, så ett exakt möte förekommer bara vid en
    mätgräns — och bara sådana par läks, mot listan över zon- och
    avsnittsgränser.

    Utbredningen mäts OM över det fogade spannet: när den ena halvan är en
    zonmätning över hela sidbredden bär den grannspaltens bläck (s. 40:
    linjeregeln i högerspalten), och en ren union av boxarna skulle ärva
    felet. Är breddskillnaden stor (≥2×) begränsas fönstret till den smala
    halvans — det är radens egen spalt.
    """
    if not rows:
        return rows
    tol = 1.5

    def px(r):
        x, y, w, h = r["bbox"]
        top = (1.0 - (y + h)) * height
        bottom = (1.0 - y) * height
        return top, bottom, x * width, (x + w) * width

    def vid_grans(axel):
        return any(abs(axel - g) <= 2.0 for g in boundaries)

    ändrat = True
    while ändrat:
        ändrat = False
        for i, a in enumerate(rows):
            if a.get("kind") != KIND_ROW:
                continue
            a_top, a_bot, a_x0, a_x1 = px(a)
            for j, b in enumerate(rows):
                if i == j or b.get("kind") != KIND_ROW:
                    continue
                b_top, b_bot, b_x0, b_x1 = px(b)
                if abs(a_bot - b_top) > tol or not vid_grans(b_top):
                    continue
                # Överlappet mäts mot den SMALARE halvan: två olika rader i
                # olika spalter kan mötas på samma gränsaxel (s. 32 band
                # 57/67) och får aldrig fogas.
                overlap = min(a_x1, b_x1) - max(a_x0, b_x0)
                if overlap < 0.5 * min(a_x1 - a_x0, b_x1 - b_x0):
                    continue
                # Och bläcket måste hänga ihop GENOM kanten i det gemensamma
                # fönstret: en linjeregel och en textrad kan mötas exakt på
                # gränsen därför att zonsnittet klipper mitt i luckan mellan
                # dem — det är två tryckta objekt, inte en delad rad.
                v0 = max(0, int(max(a_x0, b_x0)))
                v1 = min(width, int(min(a_x1, b_x1)))
                kant = int(round(b_top))
                if v1 <= v0 or kant - 1 < 0 or kant >= height:
                    continue
                ref = dark[int(a_top):int(b_bot), v0:v1].max()
                niva = MIN_DARKNESS_SHARE * ref if ref else 0
                if not ref or dark[kant - 1, v0:v1].max() < niva \
                        or dark[kant, v0:v1].max() < niva:
                    continue
                bred, smal = ((a_x0, a_x1), (b_x0, b_x1)) \
                    if (a_x1 - a_x0) >= (b_x1 - b_x0) \
                    else ((b_x0, b_x1), (a_x0, a_x1))
                if (bred[1] - bred[0]) >= 2 * (smal[1] - smal[0]):
                    lo, hi = int(smal[0]) - 2, int(smal[1]) + 2
                else:
                    lo, hi = int(min(a_x0, b_x0)), int(max(a_x1, b_x1))
                top, bottom = int(round(min(a_top, b_top))), \
                    int(round(max(a_bot, b_bot)))
                extent = _extent(dark, top, bottom, max(0, lo),
                                 min(width, hi))
                if not extent:
                    continue
                # Kroppshalvan äger region och position: spänner paret
                # zon/kropp hör raden till SPALTEN (DRAKFJÄLL är
                # vänsterspaltens rubrik, inte sidhuvud), annars vinner den
                # högre halvan.
                zoner = ("sidhuvud", "sidfot")
                if a["region"] in zoner and b["region"] not in zoner:
                    kropp = b
                elif b["region"] in zoner and a["region"] not in zoner:
                    kropp = a
                else:
                    kropp = a if (a_bot - a_top) >= (b_bot - b_top) else b
                lakt = {"region": kropp["region"], "kind": KIND_ROW,
                        "läkt": True,
                        "bbox": _box(extent[0], extent[1], top, bottom,
                                     width, height)}
                if kropp.get("svep"):
                    lakt["svep"] = kropp["svep"]
                pos = rows.index(kropp)
                rows[pos] = lakt
                rows.remove(a if kropp is b else b)
                ändrat = True
                break
            if ändrat:
                break
    # Fas B EFTER parfogningen: en kapad rad UTAN motpart (s. 32 `Beröring` — övre
    # skivan mättes aldrig, bandet är 11 px mot syskonens 15) förlängs över
    # gränsen så länge bläcket hänger ihop. En verklig grannrad stoppar
    # naturligt: raderna skiljs alltid av minst en blank profilrad, och
    # förlängningen är dessutom takad till en radhöjd.
    tak = max(4, int(page_median or 8))
    for idx, r in enumerate(rows):
        if r.get("kind") != KIND_ROW or r.get("läkt"):
            continue
        top, bottom, x0, x1 = px(r)
        top, bottom = int(round(top)), int(round(bottom))
        # Bara ONORMALT korta band förlängs. Gränsen genom en rad klipper i
        # två grader: skär den av halva radkroppen är bandet tydligt kortare
        # än sidans radmedian (s. 32 `Beröring`, 11 px mot 15) — det är
        # felet. Nafsar den bara uppstaplarnas toppar är bandet normalhögt,
        # och en förlängning skulle bara göra det omaka mot sina syskon
        # (uppmätt: 81 sådana krypningar på Lovligt byte utan gaten).
        if page_median and (bottom - top) >= 0.75 * page_median:
            continue
        lo, hi = max(0, int(x0) - 2), min(width, int(x1) + 2)
        ref = dark[top:bottom, lo:hi].max() if bottom > top else 0
        if not ref:
            continue
        grans_niva = MIN_DARKNESS_SHARE * ref
        ny_top, ny_bot = top, bottom
        if vid_grans(top):
            steg = 0
            while ny_top - 1 >= 0 and steg < tak and \
                    dark[ny_top - 1, lo:hi].max() >= grans_niva:
                ny_top -= 1
                steg += 1
        if vid_grans(bottom):
            steg = 0
            while ny_bot < height and steg < tak and \
                    dark[ny_bot, lo:hi].max() >= grans_niva:
                ny_bot += 1
                steg += 1
        if (ny_top, ny_bot) != (top, bottom):
            extent = _extent(dark, ny_top, ny_bot, lo, hi)
            if extent:
                lakt = dict(r)
                lakt["läkt"] = True
                lakt["bbox"] = _box(extent[0], extent[1], ny_top, ny_bot,
                                    width, height)
                rows[idx] = lakt

    return rows


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


def _median_of(values):
    vals = sorted(values)
    mid = len(vals) // 2
    if len(vals) % 2:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2


def _band_gutters(dark, a, b, width):
    """ALLA rännor sedda från ETT radband, som [(x0, x1)].

    Två saker skiljer den här mätningen från den ursprungliga, och båda är
    mätta på de 29 äventyrsböckerna:

    **Alla rännor, inte den första.** Sättningen i de svenska rollspelshäftena
    är TRESPALTIG — 135 av 217 sidor i 25 av 29 böcker. Den gamla mätningen
    letade en enda ränna innanför sidans mittersta 30–70 % och tog den första
    den fann. På Kopparringen s. 3, där rännorna ligger på 0,32 och 0,62, gav
    det en `vänsterkolumn` på 0,25 av bredden och en `högerkolumn` på 0,47 —
    mitt- och högerspalten hopslagna i ett band per tryckt rad. Det är
    kolumnsammanslagning producerad av mätningen själv, och ingenting nedströms
    kan skilja den från en verklig fullbredds rad.

    **Kontrast, inte absolut tröskel.** Tomheten mättes som `prof < andel *
    prof.max()`, alltså mot profilens TOPP. En skanning med grå eller
    rastrerad botten har ett golv långt över noll: i-drakens-klor s. 5 har
    profilgolv 96 mot topp 136, och där hittades NOLL rännor trots tre tydliga
    dalar — hela sidan mättes som fullbredd. Tröskeln går därför på profilens
    eget dynamiska omfång, `lo + kontrast * (hi - lo)`, vilket gör måttet
    oberoende av hur mörkt papperet är.

    Marginalerna räknas inte som rännor; det avgörs av anroparen, som vet var
    satsytan börjar.
    """
    prof = dark[a:b, :].mean(axis=0)
    if prof.size == 0:
        return []
    lo, hi = float(prof.min()), float(prof.max())
    if hi - lo <= 0:
        return []
    empty = prof < lo + GUTTER_CONTRAST * (hi - lo)
    return [(x0, x1) for x0, x1 in _runs(empty)
            if x1 - x0 >= MIN_GUTTER_WIDTH * width]


def _columns(dark, top, bottom, width, bands=None):
    """Spaltgränser som (lo, hi) — rännorna är breda tomma lodräta stråk.

    Rännan mäts genom OMRÖSTNING bland avsnittets radband, inte på avsnittets
    medelprofil. Skälet är mätt: en helsidesbred illustration lägger bläck rakt
    över rännan, och i medelvärdet räcker det för att fylla den — spalterna
    hittas då inte, och vänster- och högerspaltens rader slås ihop till
    gemensamma fullbreddsband. Del II hade tio sådana sidor (s. 8, 20, 32–36,
    42, 64), och där föll HELA sidan ut utan geometri: läsexporten fick en rad
    per tryckt rad, avstavningarna blev kvar och styckena fogades aldrig ihop.

    Två arter av illustration måste båda fångas, och bara omröstningen klarar
    det: s. 8 är en nattscen med SVART bottenplatta (hög bläckandel) och s. 20
    en STRECKTECKNING (bläckandel som brödtext). Det de har gemensamt är att de
    korsar rännan — alltså röstar de nej, oavsett svärta.

    Rännans LÄGE mäts som den KORRIDOR som är tom i alla röstande band, inte
    som medianen av deras enskilda rännor. Skillnaden är mätt: på en sida med
    korta rader — del III s. 13, listan över magiskolor — börjar varje bands
    egen tomma yta direkt efter radens sista ord, och medianen av de starterna
    lade rännan vid x 0,332 i stället för vid satsytans verkliga 0,49. Följden
    var att vänsterspaltens fönster klippte av sin egen text, och antalet band
    blev fel i båda spalterna.

    Korridoren är robust just för att en KORT rad är tom över HELA ytan till
    höger om sig: den innehåller den riktiga rännan, och snittet med en full
    rads ränna blir därför den riktiga rännan. Beslut s. 13 formulerar samma
    sak — »en obruten vertikal korridor utan bläck över hela satsytans höjd«.
    Ett band som saknar ränna röstar redan nej och ingår inte i snittet, så en
    illustrationsrad kan inte radera korridoren.
    """
    if bands:
        röster = [_band_gutters(dark, a, b, width) for a, b in bands]
        träffar = [g for g in röster if g]
        if len(träffar) >= GUTTER_VOTE_SHARE * len(bands):
            # Korridoren mäts som en RÖSTRÄKNING per bildkolumn i stället för
            # som ett snitt. Snittet krävde att varje röstande band var tomt på
            # exakt samma punkt, vilket håller för två jämnt satta spalter men
            # inte för tre: en enda rad vars ord råkar sträcka sig in i rännan
            # raderade då hela korridoren. Räkningen tål det — en ränna är den
            # yta som är tom i minst hälften av de band som alls har en ränna.
            röstat = [0] * width
            for gutters in träffar:
                for x0, x1 in gutters:
                    for x in range(x0, x1):
                        röstat[x] += 1
            gräns = COLUMN_VOTE_SHARE * len(träffar)
            korridor = [n >= gräns for n in röstat]
            # Kärnan kräver 75 % av rösterna, men BREDDEN mäts med hysteres:
            # kärnrunnen utvidgas åt båda hållen så länge minst hälften av de
            # röstande banden är tomma där. Skälet är mätt (Skymningslandet
            # s. 1): rännan mellan satsen och ZONEN-balken är 42 px i varje
            # enskilt band, men textkantens ojämnhet och balkens halo hyvlar
            # rösterna vid kanterna, så 75 %-kärnan blev 23 px — under
            # MIN_GUTTER_WIDTH — och hela balken slogs ihop med spalten.
            # Hysteresen kan inte återinföra BQ-013:s falska rännor: en sådan
            # nådde aldrig 75 % någonstans, och utan kärna utvidgas inget —
            # och golvet 0,65 ligger över de falska rännornas ~0,58.
            mjuk = GUTTER_EDGE_VOTE_SHARE * len(träffar)
            # Utvidgningen är KANTÅTERVINNING och får därför ett längdtak på
            # en halv rännbredd per sida: hyvlingen som ska återvinnas är
            # några pixlar (Skymningslandet: 9 px vänster, 1 px höger). Utan
            # taket kedjar utvidgningen ihop rännfragment tvärs över GLES
            # LINJEKONST — ett skelett i streckteknik är "tomt" i två
            # tredjedelar av banden, och rännan på var sida om illustrationen
            # smälte ihop till en jätterun som svalde spaltdelningen
            # (Spindelkonungen s. 12).
            tak = int(MIN_GUTTER_WIDTH * width / 2)
            utvidgade = []
            for x0, x1 in _runs(np.array(korridor)):
                a, b = int(x0), int(x1)
                while a > 0 and int(x0) - a < tak and röstat[a - 1] >= mjuk:
                    a -= 1
                while b < width and b - int(x1) < tak and röstat[b] >= mjuk:
                    b += 1
                if utvidgade and a <= utvidgade[-1][1]:
                    förra = utvidgade[-1]
                    utvidgade[-1] = (förra[0], max(förra[1], b),
                                     förra[2], max(förra[3], int(x1)))
                else:
                    utvidgade.append((a, b, int(x0), int(x1)))
            # Marginalvillkoret döms på KÄRNAN, inte på utvidgningen: inne i
            # en ramad ruta är marginalen tom i nästan alla band, utvidgningen
            # vandrar då ända till kanten, och rännan mellan statblocket och
            # illustrationen förkastades som "marginal" fast dess kärna står
            # mitt på ytan (Spindelkonungen s. 12). Bredden mäts däremot på
            # utvidgningen — det är hela hysteresens poäng. Marginalerna är
            # inte rännor: en ränna har sats på BÅDA sidor om sin kärna.
            kandidater = [(x0, x1) for x0, x1, k0, k1 in utvidgade
                          if x1 - x0 >= MIN_GUTTER_WIDTH * width
                          and k0 > 0 and k1 < width]
            blocks, cursor = [], 0
            for x0, x1 in kandidater:
                blocks.append((cursor, x0))
                cursor = x1
            blocks.append((cursor, width))
            blocks = [(a, b) for a, b in blocks
                      if b - a >= MIN_COLUMN_WIDTH * width]
            if len(blocks) >= 2:
                return blocks

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


def _cover_ink_span(dark, ink_top, ink_bottom, blocks, width):
    """Omätta strimlor när spaltfönstren inte täcker satsytan (BQ-021 c).

    På en sida där illustrationer styr rännröstningen kan blocken följa
    BILDENS klungor i stället för satsytan: del III s. 37 fick bara
    `mittkolumn` och `högerkolumn`, och de fyra bildtexterna till vänster och
    mellan dem mättes aldrig; s. 49 tappade fem av sju lodräta vapennamn.
    Signalen är BQ-postens egen och rent geometrisk: täcker spaltfönstren
    under 0,8 av bläckspannet finns en omätt strimla. Varje lucka bredare än
    en ränna blir då ett eget mätfönster. Strimlorna är mätfönster, inte
    semantiska spalter — de klassas aldrig som illustrationsblock, för de
    finns just därför att det kan stå TEXT i dem som ingen annan mäter.

    Ramens lodräta linjer räknas inte in i bläckspannet — annars blir en
    inramad sidas marginal en "omätt strimla" och ramlinjen ett högt band
    (samma felklass som BQ-013). Definitionen är `_rule_mask`s: bläck genom
    minst `RULE_RUN_SHARE` av höjden i en klunga smalare än `MAX_RULE_WIDTH`.
    """
    ink2d = dark[ink_top:ink_bottom, :] > 127
    if not ink2d.size:
        return []
    rule = ink2d.mean(axis=0) >= RULE_RUN_SHARE
    limit_w = max(2, int(MAX_RULE_WIDTH * width))
    mask = np.zeros(width, dtype=bool)
    for a, b in _runs(rule):
        if b - a <= limit_w:
            mask[max(0, a - 1):b + 1] = True
    ink = (ink2d.sum(axis=0) >= 2) & ~mask
    cols = np.flatnonzero(ink)
    if not len(cols):
        return []
    span_lo, span_hi = int(cols[0]), int(cols[-1]) + 1
    if span_hi - span_lo <= 0:
        return []
    covered = sum(hi - lo for lo, hi in blocks)
    # Tröskeln är uppmätt mot båda arterna: friska tvåspaltssidor täcker
    # 0,66 av bläckspannet (resten är rännan och satskanterna), trespaltiga
    # 0,82 — de sjuka sidorna 0,37–0,45 (s. 37, s. 49). 0,55 ligger i luckan.
    if covered >= 0.55 * (span_hi - span_lo):
        return []
    limit = MIN_GUTTER_WIDTH * width
    strips, cursor = [], span_lo
    for lo, hi in sorted(blocks):
        if lo - cursor >= limit:
            strips.append((cursor, lo))
        cursor = max(cursor, hi)
    if span_hi - cursor >= limit:
        strips.append((cursor, span_hi))
    # En strimla utan eget bläck är ingen omätt strimla utan en RÄNNA — den
    # mäts inte (uppmätt: namnremsan på s. 49 har bläck i 24 % av sina
    # bildkolumner, en spaltränna 0–4 %).
    return [(a, b) for a, b in strips if b - a and ink[a:b].mean() >= 0.1]


def _cluster_split(dark, top, bottom, lo, hi, page_median, ignore=None):
    """Klungorna i ett band som korsar grafiska streck, eller None.

    Se konstantblocket vid `SPLIT_RATIO`. Returnerar [(x0, x1)] i sidpixlar
    för varje klunga när bandet ska delas; annars None. Ramlinjer maskas med
    samma mask som `_extent` använder — de är inte bandets bläck.
    """
    if not page_median or bottom <= top:
        return None
    block = dark[top:bottom, lo:hi] > 127
    if not block.size:
        return None
    if ignore is not None and len(ignore) == block.shape[1] \
            and not ignore.all():
        block = block & ~ignore[np.newaxis, :]
    kol = block.any(axis=0)
    runs = _runs(kol)
    if len(runs) < 3:
        return None
    # Korsningskravet per run: ett GENOMLÖPANDE streck har en bildkolumn med
    # bläck genom bandet OCH bläck omedelbart ovanför och nedanför. En
    # tabellcells stapel gör det första men aldrig det andra — cellens bläck
    # slutar vid radens kant. En VÅGRÄT linje räknas inte som fortsättning:
    # i en linjerad tabell ligger cellinjer 1–3 px över och under varje rad,
    # och utan undantaget blev varje ordstapel ett "korsande streck" och
    # varje tabellrad delades i sina celler (uppmätt: 187 falska delningar
    # på en pristabellsida). Linjen känns igen på att den fyller bandets
    # hela fönster i sidled; ett skaft eller en streckad måttlinje gör inte
    # det.
    height = dark.shape[0]

    def _fortsatter(rad0, rad1, a, b):
        fönster = dark[rad0:rad1, lo:hi] > 127
        klunga = dark[rad0:rad1, lo + a:lo + b] > 127
        for i in range(fönster.shape[0]):
            if fönster[i].mean() >= 0.8:
                continue  # vågrät linje, inte strecket självt
            if klunga[i].any():
                return True
        return False

    def korsar(a, b):
        if b - a > max(3, int(SPLIT_MAX_CROSS_WIDTH * dark.shape[1])):
            return False  # bredare än ett streck: innehåll, inte korsning
        genom = block[:, a:b].mean(axis=0) >= SPLIT_CROSS_RUN
        if not genom.any():
            return False
        return _fortsatter(max(0, top - 3), top, a, b) and \
            _fortsatter(bottom, min(height, bottom + 3), a, b)

    kors = [korsar(int(a), int(b)) for a, b in runs]
    spann = int(runs[-1][1]) - int(runs[0][0])
    if sum(kors) < SPLIT_CROSSINGS or not spann \
            or sum(kors) / spann > SPLIT_MAX_CROSS_DENSITY:
        return None
    # Klustringen: korsande streck är egna klungor och fogar ALDRIG — de är
    # gränserna. Övriga run fogas med en radhöjds avstånd, som i löptext.
    kluster = []
    for (a, b), k in zip(runs, kors):
        a, b = int(a), int(b)
        if not k and kluster and not kluster[-1][2] \
                and a - kluster[-1][1] < page_median:
            kluster[-1][1] = b
        else:
            kluster.append([a, b, k])
    if len(kluster) < 2:
        return None
    bredd = kluster[-1][1] - kluster[0][0]
    black = sum(b - a for a, b, _ in kluster)
    if not black or bredd / black < SPLIT_RATIO:
        return None
    return [(lo + a, lo + b) for a, b, _ in kluster]


def _edge_continuous(dark, lo, hi, edge, page_median):
    """Bläck i VARJE profilrad i fönstret ±radhöjd kring en segmentgräns.

    Gränsen mellan två avsnitt är per definition en lucka i SATSEN, så bläck
    rakt igenom den är inte text. En rubrik ovanför en inramad illustration
    skiljs alltid av minst en blank profilrad (uppmätt: del III s. 14,
    `BESVÄRJELSER` ovanför pelarillustrationen) och smittar därför inte.
    """
    height = dark.shape[0]
    a = max(0, edge - page_median)
    b = min(height, edge + page_median)
    if a >= b:
        return False
    win = (dark[a:b, lo:hi] > 127).mean(axis=1) > ILLUSTRATION_ROW_INK
    return bool(len(win)) and bool(win.all())


def _illustration_block(dark, seg_top, seg_bottom, lo, hi, inner_edges,
                        page_median):
    """Är blocket en bildyta och inte en textspalt? Se konstantblocket.

    Tre vägar, alla med uppmätt marginal mot sats: en obruten bläckkörning på
    minst `GRAPHIC_HEIGHT_FACTOR` radhöjder (ZONEN-balken: 2486 px utan en
    enda blank profilrad; Tempokalkylatorns ljusa bildmitt: 41 radhöjder),
    en bläckandel som ingen sats når (`ILLUSTRATION_SOLID_SHARE`), eller
    måttlig bläckandel MED kontinuitet tvärs igenom en angränsande
    segmentgräns. Prövat mot 930 block i sex böcker utan ett enda textoffer.
    """
    if not page_median:
        return False
    blk = dark[seg_top:seg_bottom, lo:hi]
    if blk.size < 5000:
        return False
    ink = blk > 127
    share = float(ink.mean())
    if share >= ILLUSTRATION_SOLID_SHARE:
        return True
    if share < ILLUSTRATION_INK_SHARE:
        # Bläckgrinden är inte förhandlingsbar: TÄT sats med knappt radavstånd
        # kan hålla en obruten körning på 21,6 radhöjder (Skymningslandet
        # s. 1, högerspalten — dalarna mellan raderna snittar 0,017 men en
        # sträcka håller sig över radtröskeln), och utan grinden stämplades
        # hela spalten som bild. Inget textblock i korpusen når 0,40.
        return False
    inky = ink.mean(axis=1) > ILLUSTRATION_ROW_INK
    run = best = 0
    for v in inky:
        run = run + 1 if v else 0
        best = max(best, run)
    if best >= GRAPHIC_HEIGHT_FACTOR * page_median:
        return True
    for edge in inner_edges:
        if _edge_continuous(dark, lo, hi, edge, page_median):
            return True
    return False


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


def _region_names(blocks, width):
    """Regionnamn för ett avsnitts SAMTLIGA spalter, i x-ordning.

    Lägesnamnen räcker till tre spalter men kolliderar vid fyra: med jämnt
    fördelade spalter ligger mittpunkterna på 0,14 / 0,38 / 0,62 / 0,86, och
    `_region_name` döper då de två vänstra till `vänsterkolumn` och de två
    högra till `högerkolumn`. Två skilda spalter med samma namn slås ihop av
    varje konsument nedströms — `binda_rader` matchar element mot region på
    namnet, och två spalter under ett namn ger samma hopslagning som mätfelet
    var till för att förhindra. Fyra eller fler spalter namnges därför på
    ordningstalet, som transkriptionerna redan gör (`kolumn 1`…`kolumn 4`).
    """
    if len(blocks) >= 4:
        return ["kolumn %d" % (i + 1) for i in range(len(blocks))]
    namn = [_region_name(lo, hi, width) for lo, hi in blocks]
    if len(set(namn)) == len(namn):
        return namn
    return ["kolumn %d" % (i + 1) for i in range(len(blocks))]


def _box(x0, x1, top, bottom, width, height):
    """Normaliserad [x, y, bredd, höjd] med y från sidans NEDERKANT."""
    return [round(x0 / width, 6),
            round((height - bottom) / height, 6),
            round((x1 - x0) / width, 6),
            round((bottom - top) / height, 6)]


def _edge_shadow_clean(dark):
    """Nolla skanningens kantskugga innan någon mätning ser bilden (BQ-001).

    Svep från varje sidkant inåt: en bildkolumn (eller bildrad) vars mörkaste
    pixel aldrig når `EDGE_INK_SHARE` av sidans satssvärta innehåller ingen
    sats — närmast kanten är den skannerskugga eller tom marginal, och båda
    nollas. Svepet stannar vid första kolumn/rad med äkta bläck (en folio, en
    utfallande illustration) och når aldrig längre in än `EDGE_MASK_MAX`.

    Vinsten är trefaldig, alla tre uppmätta på MUT-AVE-skymningsmorker:
    banden slutar mätas från skuggan i stället för satsen (s. 1, s. 3, s. 5
    vänsterkant; s. 2, s. 4 högerkant), rena skuggband vid sidans över- och
    underkant uppstår inte alls (s. 3 band 0–1, s. 7 band 0), och fantombandet
    som gav sidfoten dubbel höjd (s. 5 band 219) föds aldrig.
    """
    ink_ref = float(np.percentile(dark, 99.9))
    if ink_ref <= 0:
        return dark
    level = EDGE_INK_SHARE * ink_ref
    height, width = dark.shape

    def spann(maxvarden, tak):
        i = 0
        while i < tak and maxvarden[i] < level:
            i += 1
        j = len(maxvarden)
        while j > len(maxvarden) - tak and maxvarden[j - 1] < level:
            j -= 1
        return i, j

    v, h = spann(dark.max(axis=0), int(EDGE_MASK_MAX * width))
    t, b = spann(dark.max(axis=1), int(EDGE_MASK_MAX * height))
    if v == 0 and h == width and t == 0 and b == height:
        return dark
    # Fyll med sidans egen bakgrundsnivå, inte med noll: mot en grå eller
    # rastrerad botten (i-drakens-klor s. 5) skulle en nollad marginal skapa
    # en konstgjord kontrastkant som `row_profile` läser som en rad.
    botten = float(np.median(dark))
    out = dark.copy()
    out[:, :v] = botten
    out[:, h:] = botten
    out[:t, :] = botten
    out[b:, :] = botten
    return out


def measure_dark(dark):
    """Mät radboxar ur en svärtbild. Returnerar (rader, spalter).

    Bruten ut ur `measure_page` så att den går att testa på syntetiska bilder
    utan PDF — och så att kalibrering mot en känd sida inte kräver rendering.
    """
    dark = _edge_shadow_clean(dark)
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
    # Zon- och avsnittsgränserna samlas åt radläkningen: bara ett bandpar
    # vars möteskant ligger PÅ en mätgräns är en delad rad (BQ-021 a).
    granser = [body_top, body_bottom]
    segments = _segments(body)
    seg_info = []
    for seg_idx, (seg_top, seg_bottom, ink_top, ink_bottom) in \
            enumerate(segments):
        # Spaltindelningen mäts PER AVSNITT. På s. 61 är övre halvan tvåspaltig
        # löptext och nedre halvan en fullbredds tabell som fyller rännan — en
        # enda mätning för hela sidan ger då noll spalter och slår ihop
        # vänster- och högerspaltens rader till gemensamma band.
        # BARA fönsterkanterna är skärande gränser. `ink_top`/`ink_bottom` är
        # per definition bandkanter — räknas de som gränser "ligger" varje
        # segments första och sista rad på en gräns, och läkaren kryper då
        # in i friska rader över hela korpusen (uppmätt: 963 ändrade boxar
        # på Lovligt byte innan spärren).
        granser += [seg_top, seg_bottom]
        seg_bands = [(a, b) for a, b, _ in body
                     if a >= ink_top and b <= ink_bottom]
        seg_blocks = _columns(dark, ink_top, ink_bottom, width, seg_bands)
        strips = _cover_ink_span(dark, ink_top, ink_bottom, seg_blocks, width)
        # Kontinuitet genom en INRE segmentgräns är en illustrationssignal;
        # kroppens över- och underkant har ingen granne att fortsätta in i.
        inner_edges = ([seg_top] if seg_idx > 0 else []) + \
            ([seg_bottom] if seg_idx + 1 < len(segments) else [])
        bild = {(lo, hi): _illustration_block(dark, seg_top, seg_bottom,
                                              lo, hi, inner_edges,
                                              page_median)
                for lo, hi in seg_blocks}
        # Strimlorna finns för att det kan stå omätt TEXT i dem — de
        # illustrationsklassas aldrig (se `_cover_ink_span`); korsande
        # grafik hanteras av klungdelningen i stället.
        seg_blocks = sorted(seg_blocks + strips)
        seg_info.append((seg_top, seg_bottom, seg_blocks,
                         [bild.get((lo, hi), False)
                          for lo, hi in seg_blocks],
                         set(strips)))

    # En bildyta skiftar karaktär mellan segmenten — Tempokalkylatorns målning
    # mäter 0,74 / 0,13 / 0,89 i bläckandel uppifrån och ned, och den ljusa
    # mitten når inget kriterium på egen hand. Men den hänger ihop med de
    # flaggade delarna tvärs igenom segmentgränsen, och det gör ingen sats:
    # flaggan propagerar därför till grannblock som x-överlappar ett flaggat
    # block och är bläckkontinuerliga genom den gemensamma gränsen, tills
    # ingenting mer ändras.
    if page_median:
        ändrat = True
        while ändrat:
            ändrat = False
            for si, (st, sb, blocks, bild, strips) in enumerate(seg_info):
                for bi, (lo, hi) in enumerate(blocks):
                    if bild[bi] or (lo, hi) in strips:
                        continue
                    for sj, edge in ((si - 1, st), (si + 1, sb)):
                        if not 0 <= sj < len(seg_info):
                            continue
                        nblocks, nbild = seg_info[sj][2], seg_info[sj][3]
                        # Kontinuiteten mäts i ÖVERLAPPSFÖNSTRET, inte över
                        # kandidatens fulla bredd: ett block som sträcker
                        # sig in i pappersmarginalen (Tempokalkylatorn,
                        # kolumn 1 med x från 0) har alltid blanka
                        # bildkolumner ytterst, men bildytan hänger ihop där
                        # blocken faktiskt möts.
                        träff = False
                        for bj, (nlo, nhi) in enumerate(nblocks):
                            över = min(hi, nhi) - max(lo, nlo)
                            if not nbild[bj] or \
                                    över < 0.5 * min(hi - lo, nhi - nlo):
                                continue
                            if _edge_continuous(dark, max(lo, nlo),
                                                min(hi, nhi), edge,
                                                page_median):
                                träff = True
                                break
                        if träff:
                            bild[bi] = True
                            ändrat = True
                            break

    for (seg_top, seg_bottom, ink_top, ink_bottom), \
            (_, _, seg_blocks, bild, strips) in zip(segments, seg_info):
        # Spalterna namnges bland TEXTSPALTERNA. Det är transkriptets
        # konvention: på en sida där en illustration tar vänstra tredjedelen
        # kallar transkriberaren de två textspalterna `vänsterkolumn` och
        # `högerkolumn` — lägesnamn mätta mot satsytan, inte mot papperet.
        # Utan bildblock är namngivningen exakt densamma som förut.
        if any(bild):
            text_ix = [i for i, b in enumerate(bild) if not b]
            seg_namn = ["illustration"] * len(seg_blocks)
            ordning = {1: None,
                       2: ["vänsterkolumn", "högerkolumn"],
                       3: ["vänsterkolumn", "mittkolumn", "högerkolumn"]}
            if len(text_ix) == 1:
                lo, hi = seg_blocks[text_ix[0]]
                seg_namn[text_ix[0]] = _region_name(lo, hi, width)
            elif len(text_ix) in ordning:
                for i, n in zip(text_ix, ordning[len(text_ix)]):
                    seg_namn[i] = n
            else:
                for pos, i in enumerate(text_ix):
                    seg_namn[i] = "kolumn %d" % (pos + 1)
        else:
            seg_namn = _region_names(seg_blocks, width)
        for (lo, hi), region, är_bild in zip(seg_blocks, seg_namn, bild):
            kolumn = {"region": region,
                      "x": round(lo / width, 6),
                      "bredd": round((hi - lo) / width, 6),
                      "y": round((height - seg_bottom) / height, 6),
                      "höjd": round((seg_bottom - seg_top) / height, 6)}
            if (lo, hi) in strips:
                kolumn["strimla"] = True
            columns.append(kolumn)
            # Profilen tas över SPALTEN, inte sidan: en rad i vänsterspalten
            # syns inte i en profil som medelvärdesbildas över båda.
            prof = row_profile(dark[seg_top:seg_bottom, lo:hi])
            bands = [(a + seg_top, b + seg_top)
                     for a, b in _profile_bands(prof, height)]
            first = _merge_and_classify(bands, page_median)
            # Andra svepet läggs in i SAMMA lista och sorteras på y innan
            # raderna skrivs ut: läsordningen är kontraktet nedströms, och en
            # gles slutrad hör till sitt eget stycke, inte sist i spalten.
            def rules_at(top, bottom):
                """Ramlinjer i ett kort fönster kring bandet (se _rule_mask)."""
                pad = max(4, int(RULE_CONTEXT_FACTOR * (page_median or 1)))
                a = max(seg_top, top - pad)
                b = min(seg_bottom, bottom + pad)
                return _rule_mask(dark[a:b, lo:hi])

            found = []
            for top, bottom, kind in first:
                extent = _extent(dark, top, bottom, lo, hi, rules_at(top, bottom))
                if extent:
                    found.append({"region": region, "kind": kind,
                                  "_span": (top, bottom),
                                  "bbox": _box(extent[0], extent[1], top,
                                               bottom, width, height)})
            extra = []
            for top, bottom, kind in _sparse_bands(
                    dark, first, seg_top, seg_bottom, lo, hi, page_median):
                extent = _extent(dark, top, bottom, lo, hi,
                                 rules_at(top, bottom))
                if extent and extent[1] - extent[0] >= MIN_ROW_WIDTH * width:
                    extra.append({"region": region, "kind": kind, "svep": 2,
                                  "_span": (top, bottom),
                                  "bbox": _box(extent[0], extent[1], top,
                                               bottom, width, height)})
            found += _drop_overlaps(found, extra)
            if är_bild:
                # Bildytans band är toner, inte rader — utan stämpeln binds
                # textelement till dem (Tempokalkylatorn BQ-001, band 3 =
                # blå bildyta). Banden behålls: transkriberaren ska se att
                # ytan finns, men ingenting nedströms får ta dem för sats.
                for r in found:
                    r["kind"] = KIND_GRAPHIC
            found.sort(key=lambda r: r["_span"])
            rows.extend(found)

    # Svansfönstret sträcker sig en radhöjd förbi avsnittsgränsen, så en
    # kandidat kan vara nästa avsnitts FÖRSTA rad en gång till. Den prövningen
    # går inte att göra inne i spaltloopen — nästa avsnitt är inte mätt ännu.
    rows = [r for r in rows
            if r.get("svep") != 2 or not _covered_elsewhere(r, rows)]
    for r in rows:
        r.pop("_span", None)

    zon(body_bottom, height, "sidfot")

    rows = _heal_split_rows(dark, rows, granser, width, height, page_median)

    # En läkt rad och ett andrasvepsband kan vara SAMMA tryckta rad: svepet
    # hittar raden i luckan vid mätgränsen, och läkaren bygger den samtidigt
    # ur sliverbandet på andra sidan gränsen (s. 48, `Bredsvärd`-etiketten).
    # Samma ägarprincip som `_covered_elsewhere`: första svepets och läkarens
    # band äger, dubblettsvepet stryks.
    def _lakt_dubblett(r):
        if r.get("svep") != 2:
            return False
        x, y, w, h = r["bbox"]
        for q in rows:
            if q is r or not q.get("läkt"):
                continue
            qx, qy, qw, qh = q["bbox"]
            if min(x + w, qx + qw) - max(x, qx) > 0 \
                    and min(y + h, qy + qh) - max(y, qy) > 0.5 * h:
                return True
        return False
    rows = [r for r in rows if not _lakt_dubblett(r)]

    # Klungdelningen körs EFTER läkningen (BQ-021 c och d): `Bredsvärd`-
    # etikettens band finns inte förrän läkaren har fogat halvorna över
    # segmentgränsen (s. 48), och ett rått måttlinjeband (s. 49) delas lika
    # gärna här. Fönstret är bandets egen uppmätta utsträckning, så ramar
    # utanför bandet kan inte störa. Andrasvepsband och kantzonernas band
    # prövas inte — de är redan snäva respektive korsas aldrig av streck.
    delade = []
    for r in rows:
        if r.get("kind") == KIND_ROW and not r.get("svep") \
                and r["region"] not in ("sidhuvud", "sidfot"):
            x, y, w, h = r["bbox"]
            top = int(round((1.0 - y - h) * height))
            bottom = int(round((1.0 - y) * height))
            lo = int(x * width)
            hi = int(round((x + w) * width))
            # Ett band lägre än en halv radhöjd är ett FRAGMENT (skraffering,
            # understycken), inte en rad med klungor — uppmätt: 100 falska
            # delningar ur sex fragmentband i en illustration utan vakten.
            # Och ramlinjemasken är obligatorisk: en tabells cellinjaler
            # löper genom varje rad och skulle annars dela raderna i celler
            # (uppmätt: 274 falska delningar på en tabellsida).
            if page_median and bottom - top < 0.5 * page_median:
                delade.append(r)
                continue
            pad = max(4, int(RULE_CONTEXT_FACTOR * (page_median or 1)))
            mask = _rule_mask(dark[max(0, top - pad):min(height, bottom + pad),
                                   lo:hi])
            split = _cluster_split(dark, top, bottom, lo, hi, page_median,
                                   mask)
            if split:
                for klo, khi in split:
                    extent = _extent(dark, top, bottom, klo, khi)
                    if extent:
                        ny = dict(r)
                        ny["delad"] = True
                        ny["bbox"] = _box(extent[0], extent[1], top, bottom,
                                          width, height)
                        delade.append(ny)
                continue
        delade.append(r)
    rows = delade

    # Ingen sortering: avsnitt uppifrån och ned, spalter vänster till höger och
    # rader uppifrån och ned emitteras redan i läsordning — hela vänsterspalten
    # före hela högerspalten, precis som transkriptionskontraktet kräver.
    return rows, columns


def ink_share(dark):
    """Andel svärtad yta i satsytan — hur mycket av sidan som är bläck.

    Sidmarginalerna räknas bort; de är alltid papper och skulle bara späda ut
    måttet.
    """
    height, width = dark.shape
    area = dark[int(0.06 * height):int(0.94 * height),
                int(0.05 * width):int(0.95 * width)]
    return float((area > 128).mean()) if area.size else 0.0


# Över så här mycket bläck i satsytan är sidan bilddominerad och mätningen
# opålitlig, oavsett hur banden råkar fördela sig. Uppmätt över del II och III
# (116 sidor): medianen ligger på 11 %, och svansen över 30 % är fjorton sidor
# som ALLA är kända problemsidor — helsidesillustrationer och de sidor där
# bilden fyller rännan så att spalterna inte hittas.
GRAPHIC_INK_SHARE = 0.30


def summarise(rows, share=None):
    """Sidsammanfattning — och en varning när mätningen inte går att lita på.

    En illustrationssida (pärmen, s. 66 i del I) ger hundratals band som inte
    är rader alls: bildens toner bryts upp av profilen precis som sats.

    Bandfördelningen ensam räcker inte som kriterium. En streckskrafferad
    illustration ger band som ser ut som HELT VANLIGA spaltrader: del III s. 3
    är en helsidesbild med bara en rubrik och en foliosiffra på, men mätningen
    gav 176 "rader" varav 136 i spaltregioner — andelen grafik- och
    fullbreddsband blev 24 % och flaggan tego. Bläckandelen avslöjar sidan
    direkt: 52 % mot textsidornas 9-13 %.

    Flaggan säger "läs PNG:n själv"; den påstår inget om innehållet.
    """
    body = [r for r in rows if r["region"] not in ("sidhuvud", "sidfot")]
    graphic = [r for r in body if r["kind"] == KIND_GRAPHIC]
    full = [r for r in body if r["region"] == "sidbredd"]
    andel = (len(graphic) + len(full)) / len(body) if body else 0.0
    summary = {"rader": len([r for r in rows if r["kind"] == KIND_ROW]),
               "grafik": len([r for r in rows if r["kind"] == KIND_GRAPHIC]),
               "dominerande_grafik": bool(body) and andel > 0.5}
    if share is not None:
        summary["black_andel"] = round(share, 4)
        if share > GRAPHIC_INK_SHARE:
            summary["dominerande_grafik"] = True
    return summary


def measure_page(page, measure_dim=MEASURE_DIM):
    """Rendera sidan i mäthög upplösning och mät radboxarna."""
    scale = measure_dim / max(page.rect.width, page.rect.height)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale),
                          colorspace=fitz.csGRAY)
    gray = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.stride)[:, :pix.width]
    dark = darkness(gray)
    rows, columns = measure_dark(dark)
    return {"rows": rows, "columns": columns,
            "sammanfattning": summarise(rows, ink_share(dark)),
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
