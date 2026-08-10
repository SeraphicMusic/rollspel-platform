# Överlämning: ikappkörningens Etapp 6

Etapp 5 (2026-08-07 – 2026-08-10) gjorde omexporten av hela korpusen först,
körde klart ström 1 (de 16 sista okorrekturlästa sidorna), triagerade Sypox
och Krugal till noll respektive en avsiktligt öppen flagga, och kom halvvägs
genom Spindelkonungen. Kvar: **Spindelkonungens resterande sidor och
bokavslut**, sedan ström 3:s återstående 563 öppna flaggor och ström 2:s
kandidat­sidor. Siffrorna i §2–§4 är mätta 2026-08-10, inte minnesbilder.

## Prompt

> Kör vidare på Etapp 6 i docs/IKAPP-ALLA-BOCKER.md. Underlaget står i
> docs/IKAPP-ETAPP6-PROMPT.md — läs den FÖRST, och läs AGENTER.md SLAVISKT
> innan du startar en enda agent. Första jobbet är att göra klart
> DOD-AVE-spindelkonungens-pyramid-och-skelettbyns-hemlighet (§2): sidorna
> 13, 14, 18, 19, 21, 22, 23, 24, 25, 26, 27, 28 med samma advokatmall som
> hittills, sedan bokavslutet med exitkod 0 i ordgrinden. Därefter ström 3
> boken i taget i storleksordning (§3) och ström 2:s kandidatsidor (§4).
> Efter varje bok: sammanfoga, exportera, rapport, diffa, och
> `python3 scripts/oforklarade_ord.py arbete/<slug>` — exitkod 0 krävs innan
> boken lämnas — därefter `python3 scripts/uppdatera_bibliotek.py
> --verkstall`. Rapportera per bok. Stanna bara om ordkonserveringen inte
> går att döma eller om en fråga bara en människa kan svara på dyker upp —
> och mät FÖRST: går frågan att avgöra med en beskärning är den ett mätjobb,
> inte ett köärende.

## 1. Vad Etapp 5 gjorde

- **§2-omexporten är KLAR.** Alla 32 böcker om­exporterade från HEAD,
  orddiffarna dömda (fyra diffklasser, dokumenterade i 15 beslut.md-filer),
  ordgrinden grön korpusbrett, biblioteket uppdaterat.
  `uppdatera_bibliotek.py` fick `--efter-dom` (7f4b771) för de 14 dömda
  posterlösa förlusterna.
- **Ström 1 är KLAR.** Fatburen s. 1–6, Elefanten s. 1, 2, 5, 7, 9, Hacking
  s. 1–5 — fullt trevarv (språkgranskare → layoutverifierare → advokat).
  Alla tre böckerna avslutade med exitkod 0 och uppdaterat bibliotek.
- **Sypox: 204 → 1 öppen flagga** (avsiktligt: tryckt KP-räknefel, dömt
  print-fynd som ska stå öppet). **Krugal: 112 → 0**, med 8 nya
  `[verktyg]`-BQ:er som dokumenterar validator-/modell-luckor (§5).
- **Prosadoms-svepet:** 124 flaggor korpusbrett vars dom stod i prosa men
  inte i fältet flyttades mekaniskt till `resolved_reasons`
  (12-mönsters-allowlist; allt tvetydigt lämnades till per-sida-advokater).
- **Åtta verktygscommits med tester** (sviten 587 → 601+ gröna), bl.a.:
  raka-citattecken läser celler/statblockfält (61d2d16) och `data.items`
  (72d8220); ordgrinden krediterar bildelement rätt (61eab2a, c0df197);
  rapporten listar inte borttagna element som lågkonfidensposter (b2e3b50);
  titelrad blir aldrig förlaga för rubrikarv (7030d22); mutant2089-adaptern
  fick FV/SV/ITF/PCN utan gissning (bfc2687).
- **Spindelkonungen till hälften:** s. 2, 3, 4, 6, 7, 9, 10, 11, 12
  triagerade. På vägen: citatglyfdomen (BQ-001), full omparning av
  felbundna kedjor på s. 9, 11, 12, skelettdomen (INT 0/FYS 0 är notation,
  se beslut.md), utelämnande-emenderingsdomen (`nämvärt` → `nämnvärt`
  applicerad på s. 12, kind `emendering`).

## 2. FÖRSTA JOBBET: gör klart Spindelkonungen

Bok: `arbete/DOD-AVE-spindelkonungens-pyramid-och-skelettbyns-hemlighet/`.
Läs `beslut.md` FÖRST — den bär alla doktriner (citatglyfdomen,
skelettdomen, utelämnande-emenderingen, kolonnklippta helbredsrader,
avledningsvariantklassen, förstabandskontrollen) och den öppna kön.

### 2.1 Sidorna, med uppmätta flaggor (2026-08-10)

| Sida | Öppna flaggor | Utöver flaggorna |
| --- | --- | --- |
| 13 | 4 | + boktext-citatpar (BQ-001) |
| 14 | 6 | + BQ-008: `sjävfallet` ska räknas om till emendering |
| 18 | 8 | + boktext-citatpar (BQ-001) |
| 19 | 8 | + boktext-citatpar (BQ-001) |
| 21 | 10 | 4 skelettstatblock — skelettdomen i beslut.md stänger dem |
| 22 | 2 | |
| 23 | 10 | 4 skelettstatblock — dito |
| 24 | 8 | 2 skelettstatblock — dito |
| 25 | 2 | |
| 26 | 2 | + boktext-citatpar (BQ-001) |
| 27 | 5 | |
| 28 | 2 | + BQ-008: `ideer` — diakritklass, döms för sig |

s. 3, 4 och 6 har EN öppen flagga var — det är de avsiktliga print-fynden
bakom BQ-005/BQ-006 (`7 km`, versen, `stor`). De ska stå öppna tills
användaren beslutat; rör dem inte.

En advokat per sida, synkront, max tre agenter totalt (AGENTER.md). Mall:
fyra­klasstriage; citera beslut.md-doktrinerna; förstabandskontroll + full
parning om något band är ägarlöst; fältsätt `verdict`/`adjudicated_by` där
det saknas; spelvärden rättas ALDRIG; PNG:n är sanningskällan och
forensiken görs i nearest-neighbour ur den inbäddade skanningen
(1762×2490 > PNG); giltig UTF-8-JSON; radera aldrig beläggstext.
Citatglyfdomen är fälld — paren på s. 13/18/19/26 verifieras mot PNG:n och
byts som `kind: "ocr"` med belägg i domen, en post per par.

### 2.2 Bokavslutet

Frysningen är omtagen efter omexportdomen och är baslinjen — **frys INTE
om**. Kör: `sammanfoga` → `exportera` → `rapport` → `diffa` →
`python3 scripts/oforklarade_ord.py arbete/<slug>` (exitkod 0 krävs; s. 12:s
emendering plus triagevågens applicerade poster ska bära varje ordändring)
→ `python3 scripts/uppdatera_bibliotek.py --verkstall`. Boken kan INTE
arkiveras: BQ-005/BQ-006 `[beslut]` väntar på användaren — rapportera dem
i stället (§6).

## 3. Ström 3: 563 öppna flaggor kvar (mätt 2026-08-10)

Samma metod som Sypox/Krugal/Spindelkonungen: läs boken s beslut.md, kör
per-sida-advokater med fyraklasstriagen. **Läs flaggtexten innan du utreder
om** — flera böcker bär utredningen i prosa från tiden före
`resolved_reasons`; jobbet är då att flytta domen till fältet via
`pipeline.corrections.close_review_reason()`, inte att utreda igen.
Prosadoms-svepet är redan kört: det som är kvar var tvetydigt och SKA till
en advokat.

```
   93  DOD-AVE-edsbrytarna-i-erebos
   51  MUT-REG-robotar
   41  DOD-AVE-daligt-vatten
   40  MUT-AVE-dodspatrullen
   33  MUT-VRL-mervyn-peak-street
   32  MUT-AVE-harda-bud
   24  DOD-VRL-staden-nohstril
   20  DOD-AVE-gripeborgs-hemlighet
   20  MUT-AVE-i-drakens-klor
   20  MUT-AVE-tune-in-turn-on-burn-out
   20  MUT-REG-skymningslandets-riddare
   18  MUT-AVE-lovligt-byte
   17  MUT-REG-den-malplacerade-tempokalkylatorn
   12  MUT-AVE-intriger-pa-tanegashima
   10  MUT-AVE-terminal-state-fruncon-91
    9  DOD-AVE-den-vita-duvan
    9  DOD-TAB-sinkadus-31-slumptabell-for-skatter
    8  MUT-REG-youre-just-a-program
    4  MUT-AVE-i-skuggan-av-en-avrattning
    3  40-…-del1-…-riotminds
    3  DOD-AVE-kopparringen
    2  DOD-REG-grundregler-1991-del3-spelarboken
    2  MUT-VRL-zacks-motor
    1  MUT-AVE-attentat-sypox        (avsiktlig: dömt KP-print-fynd)
    1  MUT-REG-hacking-…-netrunner   (avsiktlig: BQ-001 Death Wish)
```

Räkna om siffrorna själv i stället för att lita på listan:

```python
# per bok: summera len(el["review_reasons"]) över arbete/*/pages/page_*.final.json
```

OBS: en dömd print-avvikelse (tryckt räknefel, bevarat sättningsfel) SKA
stå kvar som öppen flagga — terminal-state-prejudikatet. Målet är inte
noll, målet är att varje flagga antingen är avgjord i fältet eller
avsiktligt öppen med dokumenterad dom.

## 4. Ström 2: screeningkandidaterna kvar

Kandidat­sidor med åtgärdbar `forbesikta`-regel återstår främst på
`40-…-del1-…-riotminds` (~21 sidor) och
`DOD-REG-grundregler-1991-del2-spelledarboken` (~21 sidor) plus småböcker;
dominerat av `raka-citattecken` och `bbox-felkoppling`. Den irreversibla
klassen (tabell-som-löptext) är TOM. Räkna om ur
`arbete/*/pages/page_*.review/heuristik.json` innan du planerar.
Del3-spelarboken mäts medvetet ALDRIG om (103 handmätta boxar).

## 5. Krugals öppna verktygs-BQ:er

`arbete/DOD-AVE-krugal-…/beslut.md` har 8 öppna `[verktyg]`-poster
(BQ-001/002/004–009): sb_table-kontroll, attributes.range-modellering för
varelser, statblock-sidbrytnings-sammanfogning, rubrikdrift-svep,
fältstruktur-svep, tankstreck-värden, bestiarieform. Spindelkonungen har
därtill BQ-002 (förskjuten-kedja mäter fel storhet), BQ-003 (ägarlöst
förstaband saknar regel), BQ-007 (andra svepets tröskel mot luckans egen
profil) och BQ-008 (räkna om `sjävfallet`/`ideer`). Större verktygsjobb —
ta dem som egna arbetspass, inte i förbifarten under en boktriage.

## 6. Frågor som väntar på ANVÄNDAREN (`[beslut]`)

Rapportera dessa när tillfälle ges; ingen text ändras innan svar:

- **Hacking BQ-001**: programnamnet »Death Wish 118« — tryckt värde som
  bara boken kan bekräfta.
- **Spindelkonungen BQ-005**: versens avskiljare (` / ` och ` — ` står inte
  i trycket) — (a) behåll, (b) två element, (c) riktiga radbrytningar?
- **Spindelkonungen BQ-006**: ska bevarade sättningsfel märkas i
  läsexporten — (a) inte alls, (b) `[sic]`, (c) not med avsedd lydelse?

## 7. Läget i övrigt

- **Minst 30 opushade commits** på main. Pusha INTE utan att användaren
  ber om det.
- Scratchpad-skripten från Etapp 5 (prosadoms-svepet, rubriksvepet,
  omexportdrivrutinerna) låg i sessionens scratchpad och är BORTA i en ny
  session. Det varaktiga ligger i `scripts/` och `pipeline/`. Behövs ett
  svep igen: skriv om det, och låt allowlisten vara snäv.
- Testsviten: `python3 -m unittest discover -s tests -t .` — 601+ gröna
  vid överlämningen. Kör den efter varje verktygsändring.
- AGENTER.md är bindande: max 3 parallella agenter, ingen nästling,
  specialister Sonnet/advokat Opus via agent-frontmatter (ALDRIG i
  anropet), bildforensik synkront en agent per meddelande, skript före
  LLM, snäva per-sida-uppdrag.
