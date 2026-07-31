# DoD-grundreglerna (1991) — KLAR 2026-07-31

**Boken är färdigkorrekturläst. Alla 68 sidor har `final.json`.**
Detta dokument är därför inte längre en överlämning för fortsatt korrektur utan
ett utfallsprotokoll: vad arbetet kostade, vad det fann, vilka metoder som höll
och vad som fortfarande står öppet. Läs det innan du korrekturläser NÄSTA bok —
mönstren och kostnadsmodellen är återanvändbara.

Läs alltid **CLAUDE.md** och **AGENTER.md** först och följ dem slaviskt —
särskilt Regel 8a (emendering) och läsdisciplinen.

## Slutstatus (2026-07-31)

- Arbetskatalog: `arbete/40-drakar-och-demoner-grundregler-fjarde-utgavan-1991-i-rollpersonen-riotminds/`
- System: `dod`. Källa: `import/40-Drakar-och-Demoner---grundregler,-fjärde-utgåvan-(1991)_I---Rollpersonen_RiotMinds.pdf`, 68 sidor.
- **Alla 68 sidor är transkriberade, validerade och korrekturlästa.**
- Slutkörning: 68 sidor, **4304 element, 351 granskningsposter, 2368
  korrektioner, 25 tabeller**. Testsviten: **153 tester, OK**.
- **Inga `[?]` kvarstår någonstans i boken.**
- Läskopia skapad: `bibliotek/DOD-REG-grundregler-1991-del1-rollpersonen.md`
  (8198 rader). Namnet anger `del1-rollpersonen` eftersom källan är del I
  (*Rollpersonen*) — ett rent `grundregler-1991` vore missvisande om del II
  någon gång rippas.
- `beslut.md` i arbetskatalogen är bokens samlade precedens och har vuxit till
  ~60 avgjorda punkter. Den är den mest återanvändbara artefakten härifrån.

Kommandon för referens:
```bash
WD="arbete/40-drakar-och-demoner-grundregler-fjarde-utgavan-1991-i-rollpersonen-riotminds"
python3 -m pipeline forbesikta --workdir "$WD"          # körd för hela boken
python3 -m pipeline jobb --workdir "$WD" --typ korrektur --max 3   # ger nu noll jobb
```

Jobben innehåller nu två nya fält, och **båda ska in i agentprompterna**:

- **`beslut`** → `arbete/<slug>/beslut.md`. Bokens avgjorda frågor, ifylld med
  precedensen från sidorna 40–44 (vattenstämpeln, `- `-prefixet, citattecken,
  `±0`, halvfyrkant vs minustecken, signaturer, validatorns falska positiver).
  Alla tre agenterna läser den; **bara advokaten skriver till den**. Utred inte
  om det som står där — det är hela poängen med filen.
- **`heuristik`** → `page_NNN.review/heuristik.json`. Deterministiska kandidater
  (`applied: false`) från `forbesikta`, redan körd för alla återstående sidor
  (61–68). Agenterna ska **verifiera** listan mot PNG:n, inte leta upp mönstren
  igen. Erfarenheten från 53–60: listan är **tillförlitlig men inte uttömmande**
  — den missade varje saknad rad, varje saknad tabellcell, den vertikala
  radsammanslagningen och flera felplacerade element (jämförelsen hoppar över
  element vars arraygranne ligger i en annan region). Och dess citatteckenposter
  föreslår en glyftyp som måste MÄTAS, inte följas. Verifiera listan först,
  lägg sedan tiden på det den inte kan se.

## Kör agenterna SYNKRONT, en i taget

Bakgrundsagenter **dödas av 600s-watchdogen** mitt i bildforensiken och hinner
inte skriva sin outputfil — arbetet går förlorat. Att skicka flera synkrona
agenter i samma meddelande ger "Connection closed mid-response". Detta står numera
även i `.claude/skills/_shared/proofreading-workflow.md`, som tidigare sa motsatsen.

Per sida, i strikt ordning: `sprakgranskare` → `layoutverifierare` → `djavulens-advokat`,
varje anrop med `run_in_background: false`, ett anrop per meddelande.
Sätt aldrig `model:` i anropet — agentdefinitionerna äger modellvalet.

**Verifiera alltid review-katalogen med `ls` innan advokaten startas.** En agent
kan rapportera "output skriven" utan att filen finns.

Efter varje sida: kontrollera att `final.json` finns, att korrektionsposterna har
fältet `kind` och att inga `[?]` kvarstår.

**529 Overloaded inträffar.** Advokaten dog två gånger i rad på sida 40 (~102k
tokens brända, ingen fil). Kör bara om samma uppdrag — specialistfilerna ligger
kvar, så omkörningen kostar bara advokaten. Lägg dessutom in i advokatens prompt
att den ska **skriva final.json så snart bedömningen är komplett** och göra
högupplöst forensik därefter (uppdatera filen då). Det räddade sida 40.

## Advokatens prompt måste innehålla Regel 8a

Specialisterna känner inte till den nya regeln. Lägg in detta i advokatens prompt:

> Varje korrektionspost ska ha `kind`: `"ocr"` (draften avvek från trycket —
> trycket återställs) eller `"emendering"` (draften stämmer med trycket, men
> TRYCKET är fel och rättas; tryckets lydelse MÅSTE stå kvar i `original`).
> Båda `applied: true`.
>
> EMENDERA när rättningen är den enda rimliga: entydigt stavfel, egennamn som
> avviker från bokens genomgående form, saknat ord som krävs för grammatisk
> fullständighet, felaktigt ordmellanrum, typografi (raka → typografiska
> citattecken, halvfyrkant).
>
> EMENDERA ALDRIG — behåll print-troget och sätt `needs_review`: **siffror och
> spelvärden i alla former** (detta är en grundregelbok, tabeller och värden är
> kärnan — var extra strikt), dialekt, ålderdomliga men korrekta former,
> attesterade egennamn/diakriter, allt där två rättningar är lika rimliga,
> partier som inte går att läsa säkert (`[?]` kvarstår).
>
> Vid minsta tvekan: behåll och flagga. Överemendering är en bugg. Motivera i
> `reason` VARFÖR en emendering är entydig.

## Schemafakta — ge dessa till agenterna, de gissar annars

- **bbox ligger under `source.bbox`** som `[x, y, bredd, höjd]`, normaliserat,
  med **y räknat från sidans NEDERKANT** (y minskar framåt i läsordningen).
  Verifierat empiriskt. Normal spaltbredd är ~0,43 — markant bredare bbox
  betyder kolumnsammanslagning.
- **Inbäddad skanning ≈1950×2800 px** mot sidans PNG ≈1350×1945, dvs. ~40 % mer
  upplösning. Beskär ur den inbäddade bilden med nearest-neighbour; omrendering
  av PNG:n i hög DPI ger bara interpolation.
- **Glyfbredder vid ~236 dpi:** radbrytningsbindestreck 8–10 px, halvfyrkant
  18–20 px, helfyrkant ~36 px, plustecknets tvärslå ~15 px. Detta har avgjort
  varje streckfråga på sidorna 40–44 — låt agenterna mäta, inte gissa.

## Återkommande mönster (verifierade på sidorna 40–44, kommer igen)

- **Raka citattecken.** Trycket har genomgående `’…’` och `”…”`, **även runt
  siffror**: `slå ’6’ eller lägre`, `slår ’8’ och`, `’0’`. Föreslå aldrig att
  apostrofen framför en siffra stryks — det är oftast ett par citattecken där
  transkriptionen tappat det avslutande.
- **`- `-prefix på kapitälrubriker.** Färdighetsrubriker är kapitäler centrerade
  mellan två tunna linjeregler; linjens vänstra ände läses som ett bindestreck.
  Det är sidgrafik och ska bort (`kind: "ocr"`). `forbesikta` listar alla 41
  förekomster per sida i `heuristik.json` — sidorna 45–49, 51–57, 59, 60 och 65.
  Motsatsen gäller också: föreslå aldrig att `- ` läggs *till* en rubrik — det
  avvisades på sida 41.
- **Högerspaltsrader inklämda i början av elementarrayen.** Sida 40 hade
  högerspaltens första rad som element nr 2, före hela vänsterspalten. Samma
  defekt finns enligt förbesiktningen på sidorna **47, 48, 56, 59 och 60** — den
  syns inte i en y-jämförelse inom spalten, så den är lätt att missa.
- **`±0` i tabeller** transkriberas som `10`, `*0`, `t0`, `I0`, `+0`. Glyfen är
  ett plus med separat vågrät linje under. Verifiera forensiskt; det är `ocr`
  (tecken felläst), inte emendering av ett värde. Bekräftat på sidorna 42–44.
- **Kolumnsammanslagning.** Ett element slår ihop vänster- och högerkolumnens
  rader på samma y-höjd. Sida 41 hade sex i rad, och en hel rad
  (`Grundegenskap: SMI`) var helt osynlig inne i ett sådant element.
  Layoutverifieraren bryter ut halvorna som nya element med **uppmätt** bbox.
- **Saknade tabellceller och saknade rader.** Sida 43 saknade fyra celler i
  tabellen *Socialt stånd* plus raden `nedan:`. Låt layoutverifieraren gå
  tabeller cell för cell; låt sedan advokaten läsa varje tillagd siffra själv —
  det är spelvärden.
- **Läsordningsfel i elementarrayen.** Sidorna 41, 42 och 43 hade element som låg
  fel i arrayen (bbox-y placerade dem långt senare). Exporten följer arrayordningen
  literalt, så det är ett verkligt fel, inte kosmetik.
- **Radbrutna ord över elementgränser.** Kontrollera ALLTID föregående element
  innan du kompletterar ett ord i början av ett. `bland`→`ibland` på sida 38 hade
  dubblerat en bokstav; `ringsmaskiner` på sida 40 var korrekt just för att
  `Beläg-` avslutade föregående element.
- **`ll` kan vara `11`** (antikvans etta har snedflagga + fotserif, gement l
  saknar flagga). Bekräftat på sida 43.
- **Valideraren ger falska positiver** via diakritisk normalisering:
  `Halvlängdsmän`→`Halvlängdsman` (reverterad på sida 43), `KÖPSLA`→`Köpslå`
  (avvisad på sida 42), `vardera`→`Värdera`. Kontrollera på varje sida om en
  sådan post redan ligger `applied: true` i draften och revertera i så fall.
- **Vattenstämpeln `Drakar och Demoner är © RiotMinds AB`** under sidfoten är den
  digitala utgåvans, inte boktext, och utelämnas konsekvent i alla 68 drafter.
  Layoutverifieraren föreslår att den läggs till på i stort sett varje sida —
  avvisad på sidorna 40, 42, 43 och 44. Skriv in det i prompten från början.
- **Illustratörssignaturer inne i teckningar** (`MATOSE`, `MJADZOSICH © '91`) är
  bildartefakter, inte brödtext. Sida 43 hade en i läsordningen — tömd och
  omtypad till `page_artifact`.
- **Boknivåbeslut som ackumulerar, inte per sida:** elementtypning av sidhuvud
  (`paragraph` i stället för `page_artifact`), färdighetsrubriker utan
  `heading`-nivå, exempelrutor utan `boxed_text`, samt om negativa tabellvärden
  ska sättas med halvfyrkant (de behålls som ASCII `-` t.o.m. sida 44). Låt dem
  ligga som flaggor — de ska avgöras en gång för hela boken.

## Nya avgjorda mönster från sidorna 45–52 (står i `beslut.md`)

Läs `beslut.md` — den har vuxit betydligt. De tyngsta tillskotten:

- **`-`-SUFFIX och `•`-suffix på kapitälrubrik** är den HÖGRA linjeregelns ände,
  precis som prefixet. `- KUNSKAP OM MAGI -` har båda. (s. 45, 48, 49, 51, 52)
  **`forbesikta` fångar numera båda ändarna** (regel `linjeregel-suffix`,
  tillagd 2026-07-30) — heuristiken för sidorna 53–68 är omgenererad och listar
  10 suffixfall. Agenterna ska verifiera dem, inte leta upp dem.
- **`O.` i numrerad stegskala är siffran `0`.** Forensiskt kriterium: glyfen är
  en nolla om bredd/versalhöjd < 0,85 (uppmätta kvoter 0,69–0,74; ett versalt O
  har kvot ≈1,0). Mät på varje sida. (s. 46, 49, 50)
- **Likhetstecken vs minustecken i räkneexempel.** `8+11-19` var `8+11=19`.
  Avgörs med pixelbandprofil: två parallella band = likhetstecken, ett = minus.
  Räkna ALDRIG fram tecknet ur aritmetiken. (s. 51, 52)
- **Apostrof intill tärningsnotation** (`+1 'T6`) är transkriptionsbrus, INTE
  halvan av ett citatpar — uttryckligt undantag från citatteckenregeln. Trycket
  var `+1T6`. (s. 47)
- **Obefogade `[?]` tas bort generellt** där raden är fullt läsbar i skanningen —
  inte bara efter `Grundegenskap:`. Läs raden i skanningen först. (s. 46, 47, 48)
- **Tryckt dittografi** (dubblerad fras) emenderas när partierna är
  teckenidentiska. (s. 49)
- **Tappad bokstav: gränsdragning.** Lexikonförd systemterm → print-troget;
  vanligt ord → emendering (`fusktilläget`, `inrikting`, s. 51).
- **En grundegenskapskod som saknas i adaptern** (`SMIL`) är transkriptionsbrus
  tills motsatsen bevisats — läs koden i skanningen. (s. 50)
- **Utelämnad slutpunkt emenderas inte** (s. 49, 52).
- **Saknade tabellceller är vanliga.** Sidorna 45, 48 och 51 saknade var sin
  cell (`±0`, `-1`, `±0`). Advokaten läser varje tillagd siffra själv.
- **Kolumnsammanslagning: hanteringsmodell.** Halvorna bryts ut som nya element
  med uppmätt bbox, originalet töms och typas `page_artifact`. Kontrollera
  radbrutna ord vid spaltgränsen. (s. 45, 47, 49, 50, 52)

## Kostnad och stopprotokoll

Du har **ingen åtkomst till användarens usage-data** — påstå inte annat. Sätt en
gräns i sidor i stället och stanna där av dig själv.

Faktiskt uppmätt för sidorna 40–44 (full omgång: 2 specialister + advokat):
**321k, 329k, 374k, 400k, 385k tokens** — alltså ~320–400k per sida, i linje med
den tidigare uppskattningen. Väggtid 24–42 min per sida. De 24 återstående
sidorna beräknas till **7,7–9,6 M tokens**. Räkna med extra spill om 529-fel
dödar en advokatkörning (~100k per avbrott).

### Utfall MED `forbesikta` + `beslut.md` (sidorna 45–52, mätt 2026-07-30)

| Sida | Språkgr. | Layout | Advokat | Totalt | Tid |
|---|---|---|---|---|---|
| 45 | 104k | 108k | 119k | **331k** | 25,7 min |
| 46 | 81k | 83k | 125k | **289k** | 17,6 min |
| 47 | 100k | 121k | 123k | **344k** | 28,6 min |
| 48 | 96k | 125k | 103k | **323k** | 24,2 min |
| 49 | 107k | 119k | 149k | **375k** | 36,8 min |
| 50 | 86k | 91k | 121k | **298k** | 21,4 min |
| 51 | 111k | 108k | 151k | **371k** | 25,9 min |
| 52 | 127k | 127k | 167k | **421k** | 32,7 min |

**Summa 8 sidor: 2 752k tokens, 3 h 33 min. Snitt 344k/sida, 26,6 min/sida.**

Slutsats: `forbesikta` + `beslut.md` sänkte INTE kostnaden per sida mätbart
(snitt 344k mot tidigare 321–400k). Väggtiden gick ned något. Förklaringen är
att arbetet flyttade i stället för att försvinna — agenterna slipper leta upp
mönstren, men lägger tokens på forensik i stället: glyfmätningar (`0` vs `O`,
likhetstecken vs minus, `±0`, linjeregel vs bindestreck), utbrytning av
kolumnsammanslagningar med uppmätt bbox, och saknade tabellceller. Det är
dyrare men det är rätt arbete — nio verkliga fynd på åtta sidor kom ur just
den forensiken. Räkna med **~344k/sida** framåt: de 16 återstående sidorna
beräknas till **5,0–5,8 M tokens** och ~7 timmars väggtid.

Ingen 529-krasch inträffade under sidorna 45–52; ingen omkörning behövdes.

### Utfall för sidorna 53–60 (mätt 2026-07-31)

| Sida | Språkgr. | Layout | Advokat | Totalt | Tid | Element |
|---|---|---|---|---|---|---|
| 53 | 116k | 101k | 208k | **425k** | 29,6 min | 106 |
| 54 | 113k | 107k | 141k | **361k** | 20,5 min | 103 |
| 55 | 86k | 94k | 137k | **318k** | 24,7 min | 75 |
| 56 | 117k | 111k | 132k | **360k** | 25,2 min | 107 |
| 57 | 96k | 115k | 150k | **361k** | 22,8 min | 77 |
| 58 | 145k | 150k | 234k | **528k** | 34,8 min | 137 |
| 59 | 96k | 117k | 157k | **371k** | 30,5 min | 73 |
| 60 | 139k | 139k | 204k | **482k** | 39,0 min | 87 |

**Summa 8 sidor: 3 205k tokens, 3 h 47 min. Snitt 401k/sida, 28,4 min/sida.**
176 korrektionsposter, varav 145 applicerade, 2 emenderingar och 3 kvarstående
`needs_review`. Ingen 529-krasch, ingen omkörning.

Kostnaden steg alltså från 344k till **401k per sida** trots att `forbesikta`
och `beslut.md` nu är fullt inarbetade. Orsakerna är mätbara och inte spill:

1. **Sidstorleken.** Kostnaden följer elementantalet nära nog linjärt. Sidorna
   58 (137 element, 528k) och 60 (87 element men elva trasiga, 482k) drar upp
   snittet; s. 55 (75 element, 318k) är billigast. Räkna kostnad per sida ur
   `len(elements)`, inte ur ett platt snitt.
2. **Advokaten gör mer forensik, inte mindre.** Hans andel växte till 40–43 %
   av sidans tokens (mot ~35 % på 45–52). Det är där fynden görs: han
   överträffade specialisterna på sex av åtta sidor.
3. **Domängränsen i prompten fungerade.** Dubblettposterna mellan
   språkgranskare och layoutverifierare försvann i praktiken — de avvisade
   posterna på 53–60 är nästan uteslutande heuristikens egna kandidater som
   ersatts av en mer exakt agentpost, inte samma fynd två gånger.

Prognos för de 8 sista sidorna (61–68): **~3,2 M tokens och ~3,8 timmar**, med
reservation för att sidorna 61–68 kan vara både större och tabelltätare.

### Vad forensiken faktiskt fann på 53–60 (motiverar kostnaden)

- **s. 53:** draftens `PV` var genomgående felläst `FV` i tre element — en
  systemterm i en regelmening. Ingen specialist såg hela raden.
- **s. 55:** en HEL brödtextrad saknades (spärrad sats, tappad i
  transkriptionen), foliesiffran saknades, och vattenstämpeln hade smugit in
  som element — enda sidan i boken där det hänt.
- **s. 56:** simtabellen saknade TVÅ FN-celler; layoutverifieraren hittade en,
  advokaten den andra genom att räkna om alla rader.
- **s. 58:** fyra tekniknamn i tabellen slutade på ett `t` som i själva verket
  är fotnotstecknet `†` — det styr en spelmekanisk restriktion.
- **s. 59:** kolumnsammanslagning i ett enda ord (`råd.` från högerspalten
  svalt av ett vänsterspaltselement, hörde till `ordför-`).
- **s. 60:** vertikal radsammanslagning (ett element spände över två tryckrader
  och återgav bara den undre), plus en helt saknad `Yrken: Alla`-rad som ingen
  specialist flaggat — funnen genom att räkna bläckband mot draftens rader.

### Utfall för sidorna 61–68 (mätt 2026-07-31) — bokens sista block

| Sida | Språkgr. | Layout | Advokat | Totalt | Tid | Element |
|---|---|---|---|---|---|---|
| 61 | 94k | 108k | 174k | **377k** | 26,5 min | 75 |
| 62 | 103k | 103k | 163k | **369k** | 26,3 min | 69 |
| 63 | 121k | 98k | 102k | **320k** | 23,3 min | 26 |
| 64 | 133k | 213k | 215k | **561k** | 48,0 min | 108 |
| 65 | 154k | 198k | 244k | **595k** | 45,2 min | 119 |
| 66 | 41k | — | 69k | **110k** | 7,4 min | 1 |
| 67 | 89k | 130k | 151k | **370k** | 25,1 min | 48 |
| 68 | 91k | 151k | 157k | **399k** | 31,2 min | 41 |

**Summa 8 sidor: 3 100k tokens, 3 h 53 min. Snitt 388k/sida, 29,1 min/sida.**

**Hela sessionen (s. 53–68, 16 sidor): 6 305k tokens, 7 h 40 min.**
Prognosen i förra avsnittet sa 5,0–5,8 M — utfallet blev **6,3 M**, alltså
8–26 % över. Avvikelsen ligger nästan helt på s. 64 och 65 (1,16 M tillsammans),
båda strukturellt tunga.

### Kostnadsmodell som faktiskt håller

Elementantalet är den enda prediktor som fungerar, men bara som golv — det är
**strukturarbetet** som driver toppen:

| Sidtyp | Kostnad | Exempel |
|---|---|---|
| Pärm / nästan tom | ~110k | s. 66 (1 element) |
| Kort, ren löptext | ~320k | s. 63 (26 element) |
| Normal textsida | 360–400k | s. 54, 57, 62, 67, 68 |
| Stor eller trasig sida | 480–600k | s. 58, 60, 64, 65 |

Regeln: **en sida med kolumnsammanslagningar kostar ~50 % mer än en lika stor
sida utan.** s. 64 hade 108 element och kostade 561k; s. 56 hade 107 element och
kostade 360k. Skillnaden var sex sammanslagningar.

Layoutverifieraren blir dyrast av alla tre när sidan är strukturellt trasig
(213k på s. 64, 198k på s. 65) — annars är han den billigaste. Advokaten ligger
stabilt på 40–43 % av sidans tokens.

### Nya mönster från 53–60

Alla står i `beslut.md`, men dessa är de operativt viktigaste:

- **Vertikal radsammanslagning** (s. 60) är ett NYTT mönster som `forbesikta`
  inte fångar: bbox-HÖJDEN är ~2× medianradhöjden. Kandidat till en ny
  deterministisk regel.
- **Räkna bläckband mot draftens radantal.** Både s. 55:s och s. 60:s saknade
  rader gav sig till känna som en dubbel y-lucka. Låt layoutverifieraren göra
  det rutinmässigt.
- **Klipp `Yrken:`-rader från SPALTMARGINALEN, inte från elementets bbox** —
  på s. 60 hade draftens egen bbox redan klippt bort det inledande `Y`:et.
- **Heuristikens citatteckenposter föreslår en glyftyp och måste mätas.** På
  s. 60 föreslog den blandade `’…”`; trycket hade enkla `’…’` genomgående.
- **Ordmellanrummets absoluta pixelbredd varierar mellan rader** (3–13 px).
  Mät alltid mot ett bekräftat ordmellanrum på SAMMA rad.
- **Nollkriteriet håller** (bredd/versalhöjd < 0,85): bekräftat fem gånger till
  på s. 53, 54, 56, 59.
- **`hetslag`-felet** (radbrutet `färdig-`+`hetsslag` som tappat ett s) fanns
  igen på s. 56 och 58. Sök det på varje ny sida.
- **Gränsen för emendering har skärpts tre gånger** och håller: `talat
  tjugiska` (s. 54), `ett ta` (s. 56), `sin motståndaren` (s. 59) — alla
  behållna print-troget och flaggade, eftersom den tryckta formen är ett
  existerande ord och flera rättningar är lika rimliga. Bara 2 emenderingar på
  åtta sidor.

### Nya mönster från 61–68

- **Blocköverkastning i elementarrayen** (s. 61): hela tabellrutan (40 element)
  låg FÖRE brödtexten i arrayen men UNDER den på sidan. Heuristikens
  läsordningsregel jämför granne mot granne och ser inte att två hela block
  bytt plats. Kontrollera alltid blockens inbördes ordning separat.
- **Fullbreddsingress kontra äkta kolumnsammanslagning** (s. 64): pröva ALLTID
  den enkla förklaringen först. En äkta sammanslagning har en tom spaltränna på
  **49–54 px** mitt i x-profilen; en fullbreddsrad har jämn svärtning tvärs
  över. På s. 64 var alla sex äkta, men att felaktigt dela en fullbreddsingress
  förstör texten permanent.
- **Trimning kontra tömning — kriteriet är elementets EGEN halva**, inte
  inkräktarens längd (s. 64). Trimma när elementets egen text är en fullständig,
  korrekt rad som redan ligger rätt i läsordningen; töm annars. Ordräkningen i
  den äldre s. 59-formuleringen ("ett enstaka ord") var en tillfällighet.
- **Diakritband förstör bläckbandsräkningen** (s. 62, 63). Prickarna över ä/ö
  och ringen över å blir EGNA band — och ett umlaut kan omvänt slå ihop två
  band. Räkna bort dem innan du jämför bandantal mot draftens radantal, annars
  ger metoden falska larm på varje sida med ä/ö.
- **Draften kan LÄGGA TILL en punkt** efter en versal förkortning i radslut
  (`SL`, `CL`, `FV`, `BC`) och läsa den som meningsslut (s. 62). Motsatsen till
  det tidigare kända mönstret att skiljetecken tappas.
- **Blanketter serialiseras fältgrupp för fältgrupp** (s. 67, tillämpad s. 68) —
  block hålls intakta och tas efter sitt övre vänstra hörn. Att två rutor råkar
  börja på samma y-höjd betyder INTE att de hör ihop. Både heuristikens och
  layoutverifierarens förslag byggde på det felslutet och fick avvisas.
  Radvis ordning gäller bara INOM ett block som verkligen är en tabell.
- **Pärmsidor:** förlagslogotyper i pärmgrafik töms och typas `page_artifact`
  (s. 66). Kriterier för "bokstäver är bildmotiv": gemensam konturplatta,
  överlagrat bildmärke, ®/™. En boktitel satt i fraktur på en blankett med
  satsyta är däremot TEXT och typas `heading` (s. 67) — ett av fyra kriterier
  räcker inte.
- **Ifyllningslinjer i blanketter normaliseras till `ETIKETT ( )`** (s. 68):
  linjen mellan parenteserna är grafik och stryks, men parenteserna är satta
  glyfer och behålls. En bokstavsform töms aldrig som sidgrafik.
- **`±0`-heuristiken gav noll träffar** (s. 65): alla fyra kandidaterna var
  talet `10`, mätt glyf för glyf. Regeln är korrekt konservativ — den flaggar,
  den påstår inget — men räkna inte med att kandidaterna är fynd.
- **Vattenstämpeln är märkt i PDF:en** som `/Artifact <</Subtype /Watermark
  /Type /Pagination>>` (s. 66). Filen klassar den alltså själv som
  pagineringsartefakt — ett deterministiskt belägg för att den aldrig är boktext.
- **`hetslag`-felet** dök upp igen på s. 56 och 58 men INTE på 61–68.
- **Noll emenderingar** på sidorna 57, 58, 60, 65 och 66 — nästan allt visade
  sig vara felläsningar, inte sättningsfel. Hela boken landade på ett fåtal
  emenderingar totalt. Det är rätt utfall: gränsen håller.

### Metodslutsats: advokaten är inte en kontrollstation

På tio av sexton sidor gjorde advokaten fynd som BÅDA specialisterna missade —
en saknad `(3)`-rad (s. 61), en tillagd punkt (s. 62), två saknade FN-celler
(s. 56), fyra daggerglyfer i en tabell (s. 58), en saknad `Yrken: Alla`-rad
(s. 60), `d.v. s.`→`d. v. s.` (s. 64), sidhuvudets halvfyrkant (s. 65), ett
felordnat mittblock (s. 68). Han avvisade dessutom specialistförslag som var
fel i sak på s. 60, 65, 67 och 68.

Slutsatsen är att den dyra Opus-körningen inte är en formalitet utan där
merparten av det verkliga arbetet sker. Att spara in på den vore fel
besparing. Specialisternas värde ligger i att SNÄVA IN vad advokaten måste
titta på — inte i att vara rätt.

### Pipelinefixar gjorda efter sidorna 45–52 (2026-07-30)

Två deterministiska buggar i `pipeline/preflight.py` som kostade agenttokens:

1. **`linjeregel-suffix` tillagd.** `HEADING_DASH` matchade bara `^[-–—]\s+`,
   så varje suffixfall fick hittas för hand — och `- KUNSKAP OM MAGI -` fick
   bara prefixet borttaget. Regeln täcker nu båda ändarna plus `•`, behåller
   `[?]` åt sin egen regel, och utesluter parenteser så att träfftabellens
   `MAGE (-` inte felflaggas. Sidorna 53–68: **10 suffixkandidater**.
2. **Läsordningsregeln pekade ut elementet självt** som rätt plats ("efter
   p047_e51" för e51), eftersom elementet uppfyller sitt eget `o_y >= y`.
   Layoutverifieraren avfärdade sådana som falska positiver på s. 47, 49 och
   52. Elementet utesluts nu ur urvalet; noll självreferenser kvar på 53–68.

Testsviten: 146 → **153 tester**, OK. Heuristiken för 53–68 är omgenererad med
`forbesikta --sidor 53-68 --force`.

Fråga användaren hur många sidor som ska köras innan du börjar. Rapportera
tokens och tid efter varje sida så att `/usage` kan kontrolleras löpande.

Uppskatta kostnaden ur sidans elementantal OCH dess strukturflaggor:
`python3 -c "import json;print(len(json.load(open('.../page_0NN.validated.json'))['elements']))"`
plus `heuristik.json`-räknaren `kolumnsammanslagning`. Elementantalet ger golvet,
sammanslagningarna toppen (~+50 %).

## Avslutning (körd 2026-07-31)

```bash
WD="arbete/40-drakar-och-demoner-grundregler-fjarde-utgavan-1991-i-rollpersonen-riotminds"
python3 -m pipeline sammanfoga --workdir "$WD"
python3 -m pipeline rapport   --workdir "$WD"
python3 -m pipeline exportera --workdir "$WD" --format md,csv
python3 -m unittest discover -s tests -t .
cp "$WD/export/bok.md" bibliotek/DOD-REG-grundregler-1991-del1-rollpersonen.md
```

DOCX är avvecklad — markdown är läsformatet. Läskopian är skapad.

## Exportfixarna (steg 1, gjorda 2026-07-31)

Läsexporten renderade **en tryckt rad per markdown-stycke** — hela boken, 3150
brödtextrader med tomrad emellan. Elementdatan var riktig; felet låg i
`export.py`, som skrev `[text, ""]` per element. Fyra fixar:

1. **Återflödning av rader till stycken.** Två oberoende signaler, båda uppmätta
   på boken (3510 rader): **indrag** (bbox-brus ≤0,015, styckeindrag 0,020–0,030)
   och **kort rad** (satsen är utsluten, så bara styckets sista rad understiger
   spaltbredden). Gäller `paragraph`, `boxed_text` och `list_item`; **aldrig**
   `toc_entry`/`index_entry`, där en rad är en post.
2. **Avstavningar läks** vid radslut (341 st). Ett hängande bindestreck i en
   samordning (`djur-` + `växt- och`) undantas.
3. **Tabeller fogas ihop över sidbrytning.** `tables.assemble` arbetar per sida,
   så *Särskilda förmågor* bröts mitt i rad 78 och raderna 79–81 föll ut som
   listpunkter. Tabeller med identiska rubriker slås nu ihop, och en `list` som
   fortsätter en tabell viks in — men bara om varje punkt har radens form,
   annars lämnas den orörd (hellre ful lista än tappad text).
4. **Sidmarkörerna** följer nu det block de tillhör i stället för följdens
   första sida.

Tre fällor som kostade tid och som är värda att minnas:

- **Statistiken måste vara robust.** Med `min`/`max` förgiftade ett enda
  avvikande element hela spaltens baslinje och sprängde s. 5:s högerspalt.
  Median och typvärde i stället.
- **Spaltmåtten måste räknas lokalt.** En global spaltindelning slog ihop
  tabellens högerkolumn (x≈0,49) med brödtextens (x≈0,518) på s. 61, så varje
  prosarad såg indragen ut. Baslinjen tas nu ur raderna närmast i sidled.
- **Hängande indrag har omvänd polaritet.** `Rundspark:` står i marginalen med
  fortsättningsraderna indragna (s. 59, 65). Skillnaden mot ett styckeindrag är
  att ett hängande indrag DELAS av flera rader i följd.

Utfall: 8198 → 3092 rader, 3150 enradiga stycken → 1001 riktiga stycken, noll
kvarvarande avstavningar, noll tabellrader utanför sin tabell.
**Verifierat med ordinvariant:** 30 266 ord före, 30 262 efter, och hela
skillnaden redovisad — en dubblerad tabellrubrik som försvann vid hopfogningen
(3 ord) och `INT-basera-`+`de` som läktes till `INT-baserade` (1 ord).
Testsviten: 153 → **164 tester**.

Kvar: 12 stycken som börjar med gemen, på s. 44, 48, 49, 56, 64 och 68. De är
tabellceller typade som `paragraph` och hör till den öppna elementtypningsfrågan,
inte till exporten.

## Tabellstöd inför bok 2 (2026-07-31)

Bok 2 är enligt användaren betydligt mer tabelltung. Det dyraste felet i bok 1
var att **alla 25 maskinläsbara tabeller kommer från sidorna 11–39** — från
sida 40 typade transkriptionen tabeller som `paragraph`, och då är rad- och
kolumnstrukturen borta för gott. Fem deterministiska åtgärder, inga agenter:

1. **Bindande tabellkontrakt** i `.claude/skills/extrahera/SKILL.md`. Två eller
   flera kolumner med korta, radvis parade värden MÅSTE typas `table` med
   `data.headers`/`data.rows`. `table_header`/`table_cell` dokumenteras som
   tillåten reservform, och `table_caption`/`table_note`/`list`/`list_item`/
   `requirement` är nu med i vokabulärlistan — de fanns i produktionsdata men
   inte i kontraktet, vilket i sig var en orsak till driften.
2. **Ny regel `tabellkandidat`** i `pipeline/preflight.py`. Korta
   `paragraph`/`boxed_text` vars vänsterkanter faller i två eller flera täta
   x-kluster som återkommer radvis, i sammanhängande rader. Utfallet är alltid
   `needs_review` — fel elementtyp är ett typningsfel, aldrig en korrektionspost.
3. **Ny regel `radsammanslagning`.** Höjden ensam räcker inte (en rubrik i stor
   grad är också hög); avgörande är att glyfbredden per tecken är NORMAL medan
   boxen är dubbelt så hög. Uppmätt över hela boken: sammanslagningen på s. 60
   ligger på 1,03× sidans median, rubrikerna på 1,7–9,2× och skanningsgarblet i
   illustrationerna på 0,06–0,5×.
4. **Sidtypsmedveten läsordning.** `classify_page` klassificerar sidan
   geometriskt (löptext / tabellsida / blankett / annat) och
   `rule_reading_order` + `rule_column_interleaving` körs bara på löptext.
   Dessutom bedöms inte längre element som inte renderar något (tömda av
   advokaten, `removed`) — deras plats i arrayen kan inte vara ett läsordningsfel.
5. **`tables.assemble` pekar ut raden.** I stället för "33 celler går inte
   jämnt upp på 9 kolumner" läses raderna ur bbox-geometrin och varje avvikande
   rad namnges: *rad 4 ’Lärd man’ har 2 av 9 celler (p012_e40, p012_e98)*.

Sviten: 166 → **188 tester, OK.**

### Revision över alla 68 färdiga sidor

Kört som `preflight.scan_page` direkt på `page_NNN.final.json`; ingenting under
`arbete/` skrevs eller ändrades.

| Regel | Före | Efter |
|---|---|---|
| lasordning | 54 | **9** |
| radsammanslagning | — | 1 |
| tabellkandidat | — | 16 block på 11 sidor |

**45 falska läsordningspositiver försvann** (83 %). De fördelar sig på två
orsaker: sidtypsvakten tog s. 34 (11), s. 61 (15), s. 37 (2), s. 43 (1),
s. 67 (4) och s. 68 (4), och `_renders`-filtret tog åtta larm på element som
advokaten tömt (s. 24, 26, 49, 64, 65). Kvar är 9 på s. 24, 26 och 30 — alla i
den tidiga tredjedelen, och s. 30:s fem ser ut att vara äkta: `p030_e03/e04/e05`
är märkta `högerkolumn` men ligger inklämda mitt bland vänsterkolumnens element.

`tabellkandidat` slår ut på alla fyra kända fallen (s. 48, 56, 58, 61) och
hittar därutöver **sju sidor till** med tabeller typade som `paragraph`:
s. 41 (mörkermodifikationer), 42 (Lyssna-tabellen, 29 rader), 43 (två tabeller),
44 (tre), 45 (två), 51 (rykten) och 65 (hjältedåd). Samtliga verifierade för
hand mot geometrin — inga falska positiver. Regeln är tyst på all ren löptext
(s. 46, 47, 49, 50, 52–55, 57, 59, 60, 62–64), på blanketterna (s. 67, 68) och
på de tolv sidorna som redan har riktiga `table`-element.

`radsammanslagning` ger en enda träff på den färdiga boken (s. 29, `p029_e60`)
och fångar på draftsidorna det ursprungliga fallet s. 60 `p060_e39` (2,09×).

## Radboxar: `source.bbox` mäts nu fram (2026-07-31)

Bok 2 saknade `source.bbox` helt, och det visade sig att INGET i pipelinen
producerade den — bok 1:s boxar kom från transkriptionen. Båda böckernas
PDF:er har bara vattenstämpeln i textlagret (verifierat med PyMuPDF). Utan
bbox är fyra av `forbesikta`s åtta regler verkningslösa.

Nytt kommando: `python3 -m pipeline radboxar <pdf> --workdir WD`. Det mäter
tryckta radboxar ur sidbilden med ren projektion (`pipeline/rows.py`, ingen
OCR) och `jobb` levererar filen till transkriberaren.

Tre naiva mått uteslöts genom mätning, alla värda att minnas:

1. **Per-pixel-tröskling (Otsu) faller.** Skanningen är rastrerad: 27 % av
   pixlarna i ett TOMT radmellanrum ligger under varje rimlig gråtröskel.
2. **Medelsvärta faller på gråtonade tabellrader.** Fyllningen mätte 85–90
   med OCH utan text; hela tabellen blev ett band. **Kontrasten** (spridningen
   längs raden) skilde dem: 19–25 mot 65–69.
3. **Global tröskel faller.** Raderna hakar i varandra via staplar och
   diakriter, så dalen mellan två rader ligger på ~66 av 140, inte på noll.
   Tröskeln sätts lokalt, mitt emellan lokalt golv och lokal topp.

Dessutom: spalterna måste mätas **per lodrätt avsnitt** (s. 61 är tvåspaltig
upptill och fullbredds tabell nedtill), och kantzonerna **fönstervis** (annars
dränker linjeregeln varje foliosiffra — alla 13 föll bort). Fönstervis mätning
i kroppen är däremot klart sämre: 84 % mot 98,5 %.

**Kalibrering mot alla 67 sidor med facit, 4107 element: 98,5 % täckning.**
46 sidor på exakt 100 %, 62 på minst 95 %. Av 62 missar ligger 25 på
blanketterna s. 67–68 och 6 på sidor som mätningen själv flaggar som
grafikdominerade. Blanketter förblir svagheten: linjalerna i fältrutorna blir
sidans vanligaste band och förgiftar radhöjdsmedianen.

## Kvarstående — boken är korrekturläst, men detta är inte gjort

1. **Raka citattecken kvarstår på nio redan korrekturlästa sidor** — 6, 20, 22,
   24, 26, 28, 30, 32, 36. De korrekturlästes innan typografikonventionen
   tillämpades konsekvent (sidorna 40–44 har den). Exempel: sida 30 `den '2'`,
   sida 36 `'FV B4'`, sida 32 `"Jag kallas Teval…`. Kräver en advokatkörning per
   sida, eller ett boknivåbeslut att normalisera deterministiskt. Skanna med
   `export/bok.json` — `- `-prefixet däremot finns INTE på sidorna 1–39.
2. **Mappnamnet följer inte [NAMNSTANDARD.md](../NAMNSTANDARD.md)** — det är
   PDF:ens råa namn. Bör bli `DOD-REG-grundregler-1991-del1-rollpersonen`, samma
   namn som läskopian i `bibliotek/`. `arbete/`-kataloger får aldrig raderas, så
   det är en flytt, inte en nyskapning.
3. **Sida 12: gles tabell med rubrikgrupp.** 9 rubriker men 33 celler —
   "Grundegenskapskrav" spänner över STY–STO och varje yrke har krav i bara
   några kolumner. `pipeline.tables.assemble` vägrar korrekt att gissa. Kräver
   en advokatkörning eller att en människa läser PNG:n. Rapporten namnger
   numera varje rad (`rad 4 ’Lärd man’ har 2 av 9 celler`), så arbetet går att
   göra utan att räkna celler för hand — men det är fortfarande inte gjort.
4. **Sidorna 7 och 10: monterade tabeller flaggade `needs_review`.** Cellernas
   text är oförändrad, men rad-/kolumnplaceringen bygger på läsordning och bör
   stickprovskontrolleras mot PNG:n.
5. **10 ohanterade OCR-påståenden på sidorna 2, 6, 8, 11, 15, 32, 33.**
   Confidence 0,99–1,0, men ingen advokat har fällt dom, och specialisterna ser
   inte bilden tillförlitligt. Bland dem `reslultatet`→`resultatet`,
   `ROLLERSON`→`ROLLPERSON`, `Landorisskyddade`→`Landoris skyddade`,
   `Medelalders`→`Medelålders`. Applicera dem INTE utan PNG-verifiering.
   ~1,0–1,4 M tokens att städa (sju advokatkörningar).
6. **Adapterluckorna i `system/dod/lexicon.json` är åtgärdade** (2026-07-30):
   `BC` = Baschans lades till i `terms`; `färdighetsslag`, `differensvärde`,
   `fummel`, `fumlar`, `perfekt slag`, `Primär`, `Sekundär`, `Stridskonst`,
   `Halvlängdsmän`, `orcher` i `words`; `Knytnäve` och `Spark` i
   `categories.weapons`. Samtliga attesterade i trycket. Tillägget av
   `Halvlängdsmän` gör dessutom att valideraren inte längre "rättar" pluralen
   till singular. Kvarstår: typkoden `B` (basfärdighet) saknas, och sida 44 har
   ett tryckt `färdighetslag` (ett s) flaggat som boknivåbeslut, ej emenderat.
   Samma luckor bör kontrolleras i DoD-referensrepot.
   **Nya luckor funna på s. 47–52:** `professions` saknar `Helare` och `Munk`;
   `skills` saknar `Skriva`; magiskolorna `Demonologi` och `Nekromanti` saknas.
   **Ytterligare luckor funna på s. 55–60:** `skills` saknar `Navigera`,
   `Spela instrument`, `Tala främmande språk` och `Tala modersmål`;
   `categories.weapons` saknar `Stridsklubba`.
   **Ytterligare luckor funna på s. 61–68:** `weapons` saknar `Träklubba`,
   `Tornerlans`, `Bucklare`, `Liten rundsköld`, `Stor rundsköld`, `Långsköld`,
   `Vanlig sköld`, `Romersk sköld`; `skills` saknar `Vapenfärdigheter` och
   `startfärdigheter`; `terms` saknar `HP`/`hjältepoäng`.
   `Helare` bekräftades saknad SEX gånger (s. 47, 48, 49, 57, 59, 62, 63).
   **Plus en verklig adapterbugg:** `system/dod/lexicon.json` har
   `"Enhands krosvapen"` med ett s — trycket har `Enhands krossvapen` (s. 61).
   Samtliga attesterade i trycket — komplettera evidensdrivet, emendera inte.
   Boken är nu klar, så gör den samlade genomgången mot `export/bok.json` i ett
   svep i stället för att fortsätta samla sida för sida. Kontrollera samma
   luckor i DoD-referensrepot.
7. **Valideraren "rättar" fortfarande `Halvlängdsmän`→`Halvlängdsman`** trots
   lexikontillägget — posten låg `applied: true` i draften på både s. 45 och 52
   och fick reverteras av advokaten. Kontrollera på varje ny sida med en
   raslista. Roten ligger i den diakritiska normaliseringen, inte i lexikonet.
8. **Öppna `needs_review` av samma familj — bör avgöras i ETT svep.** Alla är
   tryckta former som existerar som ord men där boken annars skriver annorlunda;
   samtliga behållna print-troget enligt Regel 8a:s tvivelsregel:
   - s. 44 (e63): `färdighetslag` med ett s — systemterm.
   - s. 52 (e43): `Färdighet måste utvecklas separat` — bestämd form väntad.
   - s. 54 (e17): `talat tjugiska` — `talar`/`har talat` båda möjliga.
   - s. 56 (e104): `om det gäller ett ta någon annans plats` — `att` väntat.
   - s. 59 (e14): `dra ned sin motståndaren på marken` — böjningsfel.
   - s. 63 (e06): `Denna färdighet i vildmarken med de resurser som` — trycket
     saknar ett helt SATSLED (verbet). Verifierat forensiskt att inget ord
     tappats i transkriptionen: raden har 7 ordmellanrum mot draftens 7.
   Frågan är principiell, inte sex separata frågor: ska tryckta böjnings- och
   ordvalsfel emenderas när den tryckta formen är ett existerande ord? Nuvarande
   svar är nej — och för s. 63 är svaret definitivt nej, eftersom ett saknat
   satsled skulle innebära att vi skriver bokens text åt författaren.
   Bekräfta eller ändra principen en gång, så slipper varje kommande bok
   utreda den.

   Utöver dessa ligger ~40 `needs_review` på s. 37–45 som nästan alla rör den
   ÖPPNA elementtypningsfrågan (rubriknivåer, `Typ:`/`Grundegenskap:`-fält,
   exempelrutor) — de avgörs i ett svep för hela boken, inte per post.
9. ~~**`forbesikta` fångar inte vertikal radsammanslagning.**~~ **ÅTGÄRDAD
   2026-07-31** — regeln `radsammanslagning` finns, se avsnittet *Tabellstöd
   inför bok 2*. Observera att tröskeln (1,8× medianhöjden) medvetet ligger
   högt: s. 60:s fall (2,09×) fångas, men s. 68:s `]0• Abs-` låg bara 27 % över
   syskonens och gör det inte. En regel som larmar vid 1,3× larmar på varje
   rubrik och varje diakritband, och kostar då mer agenttid än den sparar.
10. **1755 korrektionsposter saknar fältet `kind`** — samtliga på sidorna 1–36,
   korrekturlästa innan konventionen infördes. Sidorna 37–68 är kompletta.
   Posterna är inte fel, bara otypade: det går inte att skilja "återställde
   trycket" (`ocr`) från "avvek medvetet från trycket" (`emendering`) på den
   första drygt halva boken, och granskningsrapportens *Emenderingar*-sektion är
   därför ofullständig. Att typa om dem kräver PNG-verifiering per post, alltså
   i praktiken en advokatkörning per sida (~36 sidor). Alternativt kan de
   markeras `kind: "okänd"` deterministiskt så att luckan syns i rapporten i
   stället för att tyst se ut som `ocr`.
11. ~~**Läsordningsheuristiken bygger på tvåspaltig löptext.**~~ **ÅTGÄRDAD
   2026-07-31** — `classify_page` stänger av reglerna utanför löptext, och
   revisionen gick från 54 till 9 träffar. Kvar av grundproblemet: regeln ser
   fortfarande inte **blocköverkastning** (s. 61 — två hela block som bytt
   plats), den jämför bara granne mot granne. Sidtypsvakten gör numera att
   s. 61 är tyst i stället för att larma fel, vilket är bättre men inte samma
   sak som att felet hittas.

12. **11 sidor i bok 1 har tabeller typade som `paragraph`** — s. 41, 42, 43,
   44, 45, 48, 51, 56, 58, 61, 65, sammanlagt 16 tabellblock. Det är
   `tabellkandidat` som listat dem (se avsnittet ovan). Cellernas TEXT är
   korrekturläst och verifierad, så ingenting är fel i sak — men strukturen
   saknas, tabellerna renderas som lösa stycken i `bok.md` och de kommer aldrig
   ut i `export/tabeller/*.csv`. Att typa om dem är mekaniskt arbete mot PNG:n,
   inte omkorrektur. Det hör ihop med den öppna elementtypningsfrågan i punkt 8
   och med de 12 styckena som börjar med gemen (s. 44, 48, 49, 56, 64, 68).
   Blockerar inte bok 2.
