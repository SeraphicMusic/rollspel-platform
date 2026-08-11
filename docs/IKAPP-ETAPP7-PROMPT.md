# Överlämning: ikappkörningens Etapp 7

Etapp 6 (2026-08-10 – 2026-08-11) gjorde klart Spindelkonungen (§2 i förra
prompten) och triagerade därefter FEMTON av ström 3:s böcker med en
Opus-advokat per sida. Pausen kom mitt i **Tanegashima** — s. 2 är klar,
s. 3/4/5 återstår, och boken har INTE fått sitt bokavslut. Siffrorna i §2–§4
är mätta 2026-08-11 vid pausen, inte minnesbilder.

## Prompt

> Kör vidare på Etapp 7 i docs/IKAPP-ALLA-BOCKER.md. Underlaget står i
> docs/IKAPP-ETAPP7-PROMPT.md — läs den FÖRST, och läs AGENTER.md SLAVISKT
> innan du startar en enda agent. Första jobbet är att göra klart
> MUT-AVE-intriger-pa-tanegashima (§2): sidorna 3, 4, 5 med advokatmallen i
> §6, sedan bokavslutet med exitkod 0 i ordgrinden. Därefter ström 3:s
> återstående böcker i storleksordning (§3) och ström 2:s kandidatsidor
> (§4). Efter varje bok: sammanfoga, exportera, rapport, diffa och
> `python3 scripts/oforklarade_ord.py arbete/<slug>` — exitkod 0 krävs innan
> boken lämnas — därefter `python3 scripts/uppdatera_bibliotek.py
> --verkstall`. Rapportera per bok. Stanna bara om ordkonserveringen inte
> går att döma eller om en fråga bara en människa kan svara på dyker upp —
> och mät FÖRST: går frågan att avgöra med en beskärning eller mot en
> etablerad korpuspraxis är den ett mät-/verkställighetsjobb, inte ett
> köärende.

## 1. Vad Etapp 6 gjorde

- **Spindelkonungen KLAR** (§2 i etapp 6-prompten): s. 13, 14, 18–19, 21–28
  triagerade, s. 7:s sista citatpar bytt. BQ-001 (citatglyfdomen, 8/8 par)
  och BQ-008 (`sjävfallet`→`självfallet`; diakritdomen fälld på seriebelägg
  → `ideer`→`idéer`) STÄNGDA. Bifynd: PDF:ens s. 19 är bitidentisk med
  s. 18 — bokens riktiga s. 19 saknas i källfilen (boknivådom).
  Ordgrind 38/38. Kvar: 13 avsiktliga flaggor + BQ-005/BQ-006 `[beslut]` (§5).
- **Fjorton ström 3-böcker triagerade och avslutade** (öppna flaggor före →
  efter; ALLA kvarvarande är dokumenterade, avsiktligt öppna print-fynd):
  Edsbrytarna 93→3 · Robotar 51→6 · Dåligt vatten 41→2 · Dödspatrullen
  40→5 · Mervyn Peak Street 33→2 · Hårda bud 32→10 · Nohstril 24→**0**
  (helt klar, kö tom, ARKIVERAD) · Gripeborg 20→**0** (kö tom) ·
  I drakens klor 20→2 · Tune in 20→1 · Skymningslandet 20→19 (boken bevarar
  ovanligt många sättningsfel; alla 19 är dömda klass C) · Lovligt byte
  18→6 · Tempokalkylatorn 17→4. Varje bok: ordgrind exitkod 0, bibliotek
  uppdaterat.
- **Tre verktygscommits med tester** (sviten 601 → 605 gröna):
  - `d7aaead` — ordgrinden krediterar inte tillagda bildelement som är
    äldre än frysningen (Gripeborg-överkrediten).
  - `858bdc6` — ordgrinden krediterar inte korrektionsposter vars ändring
    är äldre än frysningen (`_forlegad`, Skymningslandet-överkrediten).
  - `4807acf` — granskningsrapporten kraschar inte på `original: null`
    (Tempokalkylatorn).
- **Metodarv från passet** (används i mallen, §6): fyraklasstriage;
  tvåklassprövningen av print-trogna stavfel (klass 1 emenderas, klass 2
  öppet fynd); förstabandskontrollen fällde ALLA Spindelkonung-sidor;
  serieargument före beskärning; »kandidat för emendering«-poster från
  tiden före Regel 8a OMDÖMS; tysta normaliseringar i draften återställs
  print-troget med ocr-post; påhittade tabellrubriker stryks (korpuspraxis
  Robotar/Skymningslandet/Tempokalkylatorn).

## 2. FÖRSTA JOBBET: gör klart Tanegashima

Bok: `arbete/MUT-AVE-intriger-pa-tanegashima/` (mutant2089). s. 2 är klar
(dittografidomen m.fl. står i beslut.md — läs den FÖRST). Kvar:

| Sida | Öppna flaggor |
| --- | --- |
| 3 | 2 |
| 4 | 3 |
| 5 | 6 |

En advokat per sida (mallen i §6), sedan bokavslutet: `sammanfoga` →
`exportera` → `rapport` → `diffa` → `oforklarade_ord.py` (exitkod 0) →
`uppdatera_bibliotek.py --verkstall`.

## 3. Ström 3: återstående böcker (mätt 2026-08-11)

Otriagerade böcker, i storleksordning; siffran är öppna review_reasons:

```
  10  MUT-AVE-terminal-state-fruncon-91      (s.8:1, s.13:2, s.14:1, s.16:1, s.19:2, s.20:1, s.23:1, s.28:1)
   9  DOD-AVE-den-vita-duvan                 (s.2:1, s.3:2, s.4:5, s.5:1)
   9  DOD-TAB-sinkadus-31-slumptabell-...    (s.1:2, s.3:1, s.4:6)
   8  MUT-REG-youre-just-a-program           (s.2:2, s.3:1, s.4:3, s.5:2)
   4  MUT-AVE-i-skuggan-av-en-avrattning     (s.2:3, s.3:1)
   3  40-...-del1-...-riotminds              (s.37:2, s.53:1)
   3  DOD-AVE-kopparringen                   (s.4:2, s.6:1)
   2  DOD-REG-grundregler-1991-del3-...      (s.6:1, s.9:1)  OBS: mäts ALDRIG om
   2  MUT-VRL-zacks-motor                    (s.1:1, s.2:1)
```

Avsiktligt öppna (RÖRS INTE): Sypox s.8:1 (KP-räknefel), Hacking s.1:1
(BQ-001 Death Wish, `[beslut]`), samt alla kvarvarande i de färdiga
böckerna i §1. Räkna om själv i stället för att lita på listan
(`len(el["review_reasons"])` över `arbete/*/pages/page_*.final.json`).

## 4. Ström 2: screeningkandidaterna

Främst `40-…-del1-…-riotminds` (~21 sidor) och
`DOD-REG-grundregler-1991-del2-spelledarboken` (~21 sidor) plus småböcker;
dominerat av `raka-citattecken` och `bbox-felkoppling`. Räkna om ur
`arbete/*/pages/page_*.review/heuristik.json` innan du planerar.
Del3-spelarboken mäts medvetet ALDRIG om (103 handmätta boxar).

## 5. Frågor som väntar på ANVÄNDAREN (`[beslut]`)

Rapportera dessa när tillfälle ges; ingen text ändras innan svar:

- **Spindelkonungen BQ-005**: versens avskiljare (` / `, ` — ` står inte i
  trycket) — (a) behåll, (b) två element, (c) riktiga radbrytningar?
- **Spindelkonungen BQ-006**: ska bevarade sättningsfel märkas i
  läsexporten — (a) inte alls, (b) `[sic]`, (c) not med avsedd lydelse?
  (Tio belagda fall listade i bokens beslut.md; svaret är prejudikat för
  hela korpusens öppna klass C-fynd.)
- **Hacking BQ-001**: programnamnet »Death Wish 118« — kräver den tryckta
  boken.
- **Dödspatrullen BQ-001**: boken har TRE uppmätta rubrikgrader (A ~88–99,
  B ~56–63, C ~40–44 px) men mappningen har två nivåer (A+B→2, C→3) — ska
  B få en egen nivå?
- **Mervyn Peak BQ-001**: emenderingen `vanligt`→`vanliga` applicerades
  2026-07-21 på premissen »kongruensfel«; premissen är nu vederlagd
  (attesterad konstruktion). Stå kvar eller återställas till trycket?
- **ANMÄLS FÖR EFTERGRANSKNING — Tempokalkylatorn BQ-002**: posten var
  taggad `[beslut]` (godkänns syntetiska tabellrubriker?) men avgjordes i
  Etapp 6 UTAN användare, med korpuspraxisen som grund (påhittad
  tabelltext tas bort; `TILLÄGG`-rubrikerna → tomma strängar, `4–5
  (forts.)` → `""` + `fortsattning_av`). Allt är spårbart i posternas
  `original` och lätt att återställa om du dömer annorlunda.

## 6. Advokatmallen (per sida — bindande form)

En `djavulens-advokat` per sida, SYNKRONT en i taget (bakgrundsagenter dör
på 600 s-watchdogen under bildforensik). Prompten ska innehålla:

1. Sökvägarna: PNG (sanningskällan), `page_NNN.final.json` (läs OCH skriv),
   bokens `beslut.md` (läs FÖRST; advokaten är enda som skriver dit),
   käll-PDF i `arkiv/` (kontrollera inbäddade skanningens pixelmått per
   sida med `page.get_images(full=True)` FÖRE beskärningsval;
   nearest-neighbour).
2. Kontexten: flaggorna skrevs före `resolved_reasons` — färdiga domar i
   prosa FÄLTSÄTTS via `pipeline.corrections.close_review_reason(element,
   reason, resolution, closed_by="agent:djavulens-advokat")`, utreds inte
   om. Pixelverifierade läsningar är stängda.
3. FYRAKLASSTRIAGE: A protokoll → resolved_reasons; B stängd av
   korpusregel/beslut.md-dom; C dömt print-fynd som STÅR ÖPPET med komplett
   dom (terminal-prejudikatet); D verklig fråga — utred mot PNG:n.
4. Regel 8a med TVÅKLASSPRÖVNINGEN: klass 1 (tryckets sträng är inget
   svenskt ord + exakt EN rättning — inkl. saknad/omkastad bokstav,
   ordmellanrum, diakritfel mot bokens egen serie) → emendera, `kind:
   "emendering"`, `applied: true`, trycket i `original`; klass 2
   (attesterat ord i fel form, dittografi, finita verb utan -r,
   fogemorfem, övertalig bokstav, flertydigt) → print-troget ÖPPET fynd,
   förslag `verdict: "avvisad"`. Vid tvekan klass 2. Siffror/spelvärden/
   dialekt/terminologi ALDRIG.
5. Fältsätt `verdict` + `adjudicated_by` på varje odömd korrektionspost;
   `kind` rättas ocr→emendering på poster som föreslår avsteg från trycket.
6. Domänkontroll om statblock finns (mutant2089: KP=STO+FYS,
   Förflyttning=FYS+SMI; dod: KP=uppåt((STO+FYS)/2), SB mot sb_table;
   tärningsnotation mot dice.json; celler läses i data.rows; avvikelser
   FLAGGAS, rättas ALDRIG).
7. Leta TYSTA NORMALISERINGAR (draften rättar tryckfel utan post →
   återställ print-troget med ocr-post) och påhittade tabellrubriker
   (stryks per korpuspraxis).
8. Nya boknivådomar → beslut.md `## Avgjort`; äkta människofrågor →
   `## Öppen kö` som `- [ ] BQ-NNN [beslut|verktyg] …` — mät först, gissa
   aldrig i frågans formulering. Rör INTE bbox/bindningar, ingen
   omfrysning, ingen export från agenten. Radera ALDRIG beläggstext.
   Giltig UTF-8-JSON, json.load-verifiera. Inga underagenter.

Ordgrinden är MEKANISK: en åtgärd som för in/ut ord ur `bok.md`
(omtypning till/från `page_artifact`, strukna rubriker, tillagda element)
måste bäras av en applicerad korrektionspost — beslut.md räcker inte.

## 7. Läget i övrigt

- **Opushade commits på main** (30+ sedan tidigare + tre nya). Pusha INTE
  utan att användaren ber om det.
- Testsviten: `python3 -m unittest discover -s tests -t .` — 605 gröna vid
  pausen. Kör den efter varje verktygsändring.
- Verktygs-BQ:er (blockerar inte, tas som egna arbetspass): Krugal
  BQ-001/002/004–009 (8 st), Spindelkonungen BQ-002/003/007,
  Edsbrytarna BQ-001–004, Skymningslandet BQ-001 (rows.py: marginalgrafik
  sväljs av textkolumn), Lovligt byte BQ-001 (radbindning ofullständig,
  100/189 element utan bbox), Tempokalkylatorn BQ-001 (radmätningen tolkar
  helsidesillustration som textrader), Nohstril/Gripeborg: kö tom.
- AGENTER.md är bindande: max 3 parallella agenter, ingen nästling,
  advokat på Opus via frontmatter (ALDRIG i anropet), bildforensik
  synkront en agent per meddelande, skript före LLM, snäva
  per-sida-uppdrag.
