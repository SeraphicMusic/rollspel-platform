# Ikappkörning — ge alla 33 rippade böcker den senaste behandlingen

*Skriven 2026-08-05 mot HEAD `e7db599`. Underlaget är mätt, inte uppskattat —
varje siffra nedan går att räkna fram igen med kommandona i §7.*

---

## LÄGE 2026-08-06 (kväll) — Etapp 4 påbörjad, se IKAPP-ETAPP4-PROMPT.md

Första agentvågen är körd: elva sidor i fyra böcker, två böcker helt klara och
arkiverade, en feltypad tabell räddad i del II, och fem verktygslagningar.
**Siffrorna i avsnitten nedan är föråldrade** — det aktuella underlaget står i
[IKAPP-ETAPP4-PROMPT.md](IKAPP-ETAPP4-PROMPT.md), som också förklarar var de
gamla siffrorna kom ifrån och varför de inte höll:

- »63 sidor utan final.json« var 61 — två är `skipped: illustration_only`.
  48 återstår.
- »337 kandidater« var 337 *(sida, regel)-par*, inte poster, och räknade ur en
  ofullständig screening: `MUT-AVE-terminal-state` hade aldrig screenats
  (398 `heuristik.json` på 437 sidor). Omkörningen ger 443 par / 1965 poster
  på 212 åtgärdbara sidor.
- »`tabellkandidat` fyrar noll gånger« gäller inte längre, och regeln som
  faktiskt hittar feltypade tabeller i styckeformade transkript visade sig
  vara `punktledare`.

Ordgrinden är dessutom mekanisk sedan i dag: `scripts/oforklarade_ord.py`
attribuerar varje ordändring till den korrektionspost som bär den. Alla 33
böcker är gröna, alla exporter står på HEAD, och läskopiorna är i takt.

## LÄGE 2026-08-06 (morgon) — Etapp 0, 1, 3 och 5 körda; Etapp 4 återstår

Etapp 0–3 och det deterministiska avslutet är genomförda. Etapp 4 är
agentarbetet och har inte påbörjats — det är den enda etapp som kostar tokens
och lyder under AGENTER.md.

**Grundinsikten stod sig, men grinden satt ett lager ned.** §1 nedan har rätt i
att geometrin är grinden. Det den inte kunde veta är VARFÖR geometrin saknades:
`pipeline/rows.py` kunde bara mäta två spalter, och 135 av de 217 sidorna — i
25 av 29 böcker — är trespaltiga. De svenska rollspelshäftena är satta som
tidningar. Mätningen tog den första rännan den fann, så mitt- och högerspalten
slogs ihop: på Kopparringen s. 3 blev `högerkolumn` dubbelt så bred som
`vänsterkolumn`. Det är kolumnsammanslagning producerad av mätningen själv, och
ingenting nedströms kan skilja den från en verklig fullbredds rad.

### Vad som gjordes

| Steg | Utfall |
| --- | --- |
| Etapp 0 | 33 böcker frysta (263 tusen ord). 1 040 `kind`-poster, 36 `verdict`, 2 punktrader — alla idempotenta. Spindelkonungens käll-PDF till `arkiv/`, delningen till `scripts/dela_spindelkonungen.py` (+21 statblock-vapentabeller, noll ord tappade). |
| Etapp 1a | `status` räknar flaggor ur sidfilerna: **1016 öppna, 949 avgjorda** — planens siffror reproducerade exakt. |
| Etapp 1b | BQ-013 och BQ-021 (b) stängda MED LAGNING, verifierade mot facit. BQ-021 (a) lever kvar och är nedskriven som olöst, inte bortförklarad. |
| `rows.py` | Flera rännor i stället för en, tomhet mätt mot profilens eget omfång. Rätt spaltantal **21 % → 71 %** över 160 sidor med facit; hopslagna spalter 106 → 25 fall. |
| `regions.py` | Ny modul. Transkriptens **573 fria regionnamn** avbildas på mätningens vokabulär — och vägrar när namnet spänner två spalter eller när trycket och mätningen är oense om spaltantalet. |
| `binda_rader` | Ny STYCKEFORMAD regim. Skalan ur en bevarandeidentitet (validerad: 121,8 mot 122,4 och 116,9 mot 122,6), spärren mot flerradiga element släppt först när regimen är uppmätt, och raggedgränsen i stället för förskjutningsprovet. Eget facitprov, `--utvardera-stycken`. |
| Etapp 3 | Mätvågen över alla 29 (`scripts/matvag.py`). |
| Etapp 5 | Rapporter om, 21 läskopior uppdaterade (`scripts/uppdatera_bibliotek.py`), alla käll-PDF:er i `arkiv/`. |

### Vad det gav

**Geometri: 12 334 av 16 097 element har bbox — 77 %, mot noll i de 29
böckerna.** Täckningen är avsiktligt ojämn (Edsbrytarna 68 %, Robotar 55 %, mot
i-drakens-klor 2 %): bindningen vägrar hellre än gissar, och de låga siffrorna
är sidor där mätningen och trycket är oense om spaltantalet.

**Screeningen vändes.** §1 mätte EN regel av sexton som fyrande. Nu fyrar tolv
och ger **337 kandidater**:

| Regel | Kandidater | | Regel | Kandidater |
| --- | ---: | --- | --- | ---: |
| `bandbredd` | 113 | | `radsammanslagning` | 7 |
| `raka-citattecken` | 91 | | `plusminus` | 6 |
| `forskjuten-kedja` | 48 | | `tomt-radband` | 4 |
| `bbox-felkoppling` | 44 | | `lasordning` | 3 |
| `kolumnsammanslagning` | 18 | | `kolumnkollaps` / `punktledare` / `plusminus-varde` | 1 var |

**Sidtypen följer med:** 119 sidor klassas nu som löptext och 21 som blankett,
mot noll tidigare. Läsordningsreglerna körs bara på tvåspaltig löptext och hade
aldrig prövats mot de här böckerna förrän nu.

**Ordkonserveringen höll.** Alla 33 böcker diffar rent mot sin frysning.

### Vad som återstår

**Överlämningen till Etapp 4 ligger i [IKAPP-ETAPP4-PROMPT.md](IKAPP-ETAPP4-PROMPT.md)**
— med sidlistor, kandidatuppdelning, flaggor per bok och en färdig prompt att
klistra in i en ny session.

1. **Etapp 4** — agentarbetet: 63 sidor utan `final.json`, 1016 öppna flaggor,
   och de 337 kandidaterna. OBS att `tabellkandidat` fyrar NOLL gånger: regeln
   letar korta element i x-kluster, en cell per element, och de här böckernas
   styckeformade transkript har inte den formen. Tabellräddningen är därmed ett
   advokatjobb mot sidbilden, inte ett mekaniskt — den mekaniska halvan finns
   inte att köra först.
2. **Bindningstäckningen** på de böcker där mätningen ännu inte hittar
   spalterna. Grind 2:s villkor 3 och 4 håller inte överallt — screeningen är
   igång på alla böcker, men *Sidor utan användbar geometri* är inte tom.
3. **BQ-021 (a)** — en avsnittsgräns kan fortfarande kapa en tryckt rad.

---

## 1. Grundinsikten: geometrin är grinden

`forbesikta` kördes 2026-08-05 på två böcker i en **kastbar** arbetskatalog
(kopior under scratch, aldrig riktigt state). Utfallet:

| Bok | Sidor | Kandidater | Regler som fyrade |
| --- | ---: | ---: | --- |
| `DOD-AVE-krugal-svylses-forbannelse` | 17 | 18 | `raka-citattecken` |
| `MUT-AVE-dodspatrullen` | 10 | 7 | `raka-citattecken` |

**En regel av sexton.** Noll på `linjeregel-prefix`, `linjeregel-suffix`,
`plusminus`, `plusminus-varde`, `punktledare`, `kolumnkollaps`,
`kolumnsammanslagning`, `lasordning`, `radsammanslagning`, `tabellkandidat`,
`bbox-felkoppling`, `tabell-svalt-titelband`, `forskjuten-kedja`, `tomt-radband`
och `bandbredd`. Inte för att böckerna är rena, utan för att de saknar geometri:
de reglerna läser bbox. Dessutom klassas varenda sida `sidtyp: annat`, så
läsordningsreglerna körs aldrig ens.

Mätningen bekräftar orsaken: de 29 böckerna har **noll** `radboxar.json`,
**noll** `source.rader` och **noll** `source.bbox`. Inte en enda uppmätt rad.

> **Konsekvens för ordningen:** att köra `forbesikta` brett innan geometrin finns
> är inte en screening — det är en linter för raka citattecken. Värre: bockar man
> av böckerna på det utfallet har man byggt en falsk trygghet, exakt den felklass
> Regel 7a finns för att förhindra.

**Riskbilden är inte del III:s.** Del III fick inte mätas om därför att 103
handmätta boxar stod på spel (BQ-002/013/021). De 29 böckerna har inga boxar
alls — det finns ingenting att förstöra. Men de är ett *nytt regime*: deras
transkript är styckevisa och har aldrig burit `source.rader`, så `binda_rader`
ska binda något den aldrig sett. Därav piloten i Etapp 2.

## 2. Korrigering av nuläget: `status` underrapporterar granskningsflaggor

`status` redovisar `needs_review` per element och missar flaggor som ligger i
`review_reasons`. Skillnaden är inte marginell:

| Bok | `status` säger | Faktiskt öppna flaggor |
| --- | ---: | ---: |
| `DOD-AVE-edsbrytarna-i-erebos` | 0 | **112** |
| `MUT-AVE-attentat-sypox` | 28 | **204** |
| `DOD-AVE-daligt-vatten` | 0 | **49** |
| **Summa alla böcker** | 167 | **1016** |

Räknat direkt ur sidfilerna: **1016 öppna** och 949 avgjorda. Samtliga 949
avgjorda ligger i del I–III — `resolved_reasons` infördes efter att de andra
böckerna rippades, så deras flaggor har aldrig kunnat stängas spårbart.

Planen utgår från 1016. **Åtgärda dessutom `status` själv** (Etapp 1) — annars
mäter vi framsteg med ett instrument som visar en sjättedel av backloggen.

## 3. Nuläge per bok

Geometri = över hälften av elementen har `source.bbox`.
Ej korr. = sidor utan `final.json`.
Raka " räknar bara elementens `text` — de 20 som gömmer sig inne i tabellceller
syns alltså inte i kolumnen (se summan nedan).

| Bok | Sidor | Typ | Geometri | Ej korr. | Öppna flaggor | Raka " | Tabeller |
| --- | ---: | --- | :---: | ---: | ---: | ---: | ---: |
| `…del1-rollpersonen` (`40-drakar-…`) | 68 | image+stub | ja | — | 3 | — | 193 |
| `DOD-REG-grundregler-1991-del2-spelledarboken` | 66 | image+stub | ja | — | 0 | — | 83 |
| `DOD-REG-grundregler-1991-del3-spelarboken` | 50 | image+stub | ja | 1 | 2 | — | 131 |
| `MUT-AVE-terminal-state-fruncon-91` | 36 | digital | ja | **32** | 0 | 21 | — |
| `DOD-AVE-spindelkonungens-pyramid-och-skelettbyns-hemlighet` | 28 | image+stub | — | — | **125** | 30 | 5 |
| `DOD-AVE-krugal-svylses-forbannelse` | 17 | image_only | — | — | **122** | 48 | 2 |
| `DOD-AVE-edsbrytarna-i-erebos` | 10 | ocr_layer | — | — | **112** | — | — |
| `DOD-VRL-staden-nohstril` | 10 | ocr_layer | — | 1 | 24 | 2 | 11 |
| `MUT-AVE-dodspatrullen` | 10 | image_only | — | — | 42 | 24 | — |
| `MUT-AVE-i-drakens-klor` | 10 | image_only | — | — | 20 | 10 | 3 |
| `DOD-AVE-den-stulna-elefanten` | 9 | ocr_layer | — | 5 | 9 | 54 | — |
| `MUT-AVE-tune-in-turn-on-burn-out` | 9 | image_only | — | — | 20 | — | 1 |
| `MUT-AVE-attentat-sypox` | 8 | image_only | — | — | **204** | — | — |
| `MUT-AVE-harda-bud` | 8 | image_only | — | — | 33 | — | — |
| `MUT-AVE-lovligt-byte` | 8 | ocr_layer | — | — | 18 | — | — |
| `DOD-AVE-den-nedbrunna-fatburen` | 7 | ocr_layer | — | 6 | 1 | 16 | — |
| `MUT-REG-hacking-eller-hur-man-blir-en-netrunner` | 7 | image_only | — | 5 | 6 | — | 3 |
| `MUT-REG-skymningslandets-riddare` | 7 | image_only | — | 2 | 28 | — | 7 |
| `MUT-REG-youre-just-a-program` | 7 | image_only | — | 3 | 6 | — | 17 |
| `MUT-VRL-mervyn-peak-street` | 7 | ocr_layer | — | — | 45 | 10 | 1 |
| `DOD-AVE-kopparringen` | 6 | image_only | — | — | 3 | 8 | — |
| `MUT-REG-robotar` | 6 | image_only | — | — | 61 | 4 | 5 |
| `DOD-AVE-den-vita-duvan` | 5 | ocr_layer | — | — | 10 | 2 | — |
| `DOD-AVE-gripeborgs-hemlighet` | 5 | image_only | — | — | 25 | 10 | — |
| `MUT-AVE-intriger-pa-tanegashima` | 5 | image_only | — | — | 13 | 26 | — |
| `MUT-VRL-sieger-bauhaus-block` | 5 | blandad | — | 5 | 0 | 20 | — |
| `DOD-AVE-daligt-vatten` | 4 | image_only | — | — | 49 | 22 | — |
| `DOD-TAB-sinkadus-31-slumptabell-for-skatter` | 4 | image_only | — | — | 9 | 2 | 17 |
| `MUT-REG-den-malplacerade-tempokalkylatorn` | 4 | ocr_layer | — | — | 18 | — | 7 |
| `MUT-AVE-i-skuggan-av-en-avrattning` | 3 | image_only | — | — | 4 | — | — |
| `MUT-VRL-dark-edge-bar` | 3 | image_only | — | 3 | 1 | 10 | — |
| `MUT-VRL-zacks-motor` | 3 | image_only | — | — | 3 | 8 | — |
| `MUT-VRL-sex-drugs-and-hi-tech-guns` | 2 | image_only | — | — | 0 | 16 | — |

**Summor:** 33 böcker, 29 utan geometri (**217 sidor**), **63 sidor** saknar
`final.json` i 8 böcker, **1016** öppna flaggor, **363** raka citattecken i 20
böcker, och **19 böcker har noll `table`-element**.

Av de 363 raka citattecknen står 343 i elementens `text` och **20 inne i
tabellceller**. Den skillnaden är hela poängen med CLAUDE.md:s regel att
reglerna måste titta *in* i cellerna: det var så `Dvärg PSY ±2` överlevde tre
agentvarv i del I. En kontroll som bara läser `el["text"]` missar dem alla.

De 19 tabellösa böckerna är den oroande posten. Del I hade 16 tryckta tabeller
liggande som lösa `paragraph` — och `tabellkandidat` kan inte se dem utan bbox.

---

## 4. Etapper

Etapperna är sekventiella och har varsin **grind**: nästa etapp börjar inte
förrän grinden är passerad. Etapp 0–3 är deterministiska (ingen LLM, Regel 5).
Etapp 4 är den enda som kostar tokens.

### Etapp 0 — Säkra nuläget (deterministiskt, minuter)

Ingen bok är fryst i dag. Utan frysning finns ingen kontroll på att etapp 2–3
bevarar orden.

```bash
python3 -m pipeline frys --workdir arbete/<slug>     # alla 33
```

Städskripten körs i **dry-run först**; verkställ bara där de rapporterar
poster > 0 (Regel 7a):

```bash
python3 scripts/materialisera_kind.py    arbete/<slug>
python3 scripts/materialisera_verdict.py arbete/<slug>
python3 scripts/tomma_artefakter.py      arbete/<slug>
python3 scripts/punktrader.py            arbete/<slug>
```

Passar också in här, oberoende av allt annat:

- Bygg om `bibliotek/DOD-AVE-spindelkonungens-pyramid.md` och
  `…skelettbyns-hemlighet.md` — de är från 20 juli mot en export byggd 5 augusti,
  alltså handdelade läskopior som saknar varje fix sedan dess.
- Kopiera Spindelkonungens käll-PDF till `arkiv/`. Den ligger i `DoD RPG`-repot
  och är den enda bok vars sista sanningskälla står utanför det här repot.

**Grind 0:** alla 33 har frysning. `git status` ren.

### Etapp 1 — Laga instrumenten (deterministiskt, halvdag)

Två verktygsfel måste bort innan de förökar sig över 217 sidor.

**1a. `status` ska räkna `review_reasons`.** Annars mäts hela kampanjens framsteg
fel (§2). Lägg till öppna/avgjorda flaggor i `status`-utskriften, med test.

**1b. Avgör BQ-013 och BQ-021** — `pipeline/rows.py` mäter inte spalt för spalt,
och blockindelningen är gemensam för spalterna.

> Det här är kampanjens enda verkliga vägval. Byggs mätmotorn om **efter** att
> 217 sidor mätts, får de mätas om. Beslutet ska tas på mätning, inte antagande:
> piloten i Etapp 2 körs på **en tvåspaltig** och **en enspaltig** sida ur samma
> bok, och avvikelsen mellan dem säger om buggen alls biter på den här
> sidtypen. Motivet som en gång sköt upp frågan (del III:s 103 handmätta boxar)
> gäller inte här — de 29 böckerna har inga boxar att riskera.

Verifiering sker mot den **arkiverade PDF:en** i en kastbar arbetskatalog,
aldrig mot `arbete/` (metoden står i BQ-002).

**Grind 1:** `status` visar 1016 öppna flaggor. BQ-013/021 är antingen stängda
med lagning, eller stängda med skriftlig motivering att de inte biter på de här
böckerna. Testsviten grön.

### Etapp 2 — Geometripilot på EN bok (deterministiskt, timmar)

Pilotbok: **`DOD-AVE-den-vita-duvan`** — 5 sidor, färdigkorrekturläst, bara 10
öppna flaggor och 2 raka citattecken. Liten och ren, så varje avvikelse är
attribuerbar till mätningen och inte till gammalt skräp.

```bash
python3 -m pipeline radboxar arkiv/DOD-AVE-den-vita-duvan.pdf \
        --workdir arbete/DOD-AVE-den-vita-duvan
python3 scripts/binda_rader.py arbete/DOD-AVE-den-vita-duvan --utvardera
```

`--utvardera` **först**, alltid: verktyget prövas mot böcker med känd bindning
(del I–III) innan det får skriva en okänd. Ett verktyg som inte kan återskapa en
känd bindning får inte skriva en ny. Utvärderingen ska **döma** avvikelserna mot
trycket, inte räkna dem — facit är en tidigare transkription med egna fel
(Regel 9a).

Sedan, och först då:

```bash
python3 scripts/binda_rader.py arbete/DOD-AVE-den-vita-duvan --verkstall
python3 scripts/laga_radbas.py arbete/DOD-AVE-den-vita-duvan       # dry-run
python3 -m pipeline sammanfoga --workdir arbete/DOD-AVE-den-vita-duvan
python3 -m pipeline diffa      --workdir arbete/DOD-AVE-den-vita-duvan
python3 -m pipeline forbesikta --workdir arbete/DOD-AVE-den-vita-duvan --sidor 1-5 --force
```

**Grind 2 — alla fyra måste hålla:**

1. `diffa` visar noll oförklarade ordförändringar.
2. `--utvardera` klarar del I–III:s kända bindningar.
3. `forbesikta` fyrar nu på fler än en regel (annars har geometrin inte landat).
4. Ingen sida hamnar under *Sidor utan användbar geometri* i `rapport`.

Faller någon av dem: **stanna**. Etapp 3 skalas inte upp på en obevisad pilot.
Felklassen att frukta är den `binda_rader` själv dokumenterar — 62 % av alla
avvikelser mot facit var hela block ett steg ur led, vilket ser korrekt ut i
JSON och är förödande nedströms.

### Etapp 3 — Mätvåg och screening (deterministiskt, 29 böcker / 217 sidor)

Samma sekvens som piloten, bok för bok, minsta först (`sex-drugs` 2 sidor →
`spindelkonungen` 28 sidor). Små böcker först ger tidiga signaler billigt.

Per bok: `radboxar` → `binda_rader --utvardera` → `--verkstall` → `laga_radbas`
→ `sammanfoga` → `diffa` → `forbesikta --force` → `tabellkandidat.py`.

`scripts/tabellkandidat.py` monterar bara block vars rutnät är en fullständig
rektangel. Ragged block och tabellernas **gränser** (feta rubrikrader, flera
tabeller i ett block) lämnas till advokaten i Etapp 4 — de är inte mätbara.

**Driftvakten körs på boknivå.** Larmar den om typdrift ska den utredas innan
boken kallas klar; det som ser ut som en tyst konventionsändring är i praktiken
alltid en transkription som tappat sitt kontrakt mitt i körningen.

**Grind 3:** alla 33 böcker har geometri och en `heuristik.json` byggd på
nuvarande HEAD. Kandidatlistan är sammanräknad — **först nu vet vi hur stort
Etapp 4 faktiskt är.**

### Etapp 4 — Agentarbetet (kostar tokens — enda etappen som gör det)

Prioriterad av Etapp 3:s utfall, inte av den här listan. Tre arbetsströmmar:

**4a. 63 sidor utan `final.json`** i 8 böcker. Terminal State ensam står för 32.
Normalflödet: `jobb --typ korrektur` ger triage och exakta sökvägar.

**4b. 1016 öppna granskningsflaggor.** Fyra böcker bär 563 av dem — Sypox (204),
Spindelkonungen (125), Krugal (122), Edsbrytarna (112). Varje avgjord flagga
stängs med `close_review_reason()` till `resolved_reasons` med lösning och
upphovsman. **Radera aldrig beläggstexten.**

**4c. Etapp 3:s kandidatlista**, tabellgränserna först — det är den
oåterkalleliga klassen (CLAUDE.md §Tabeller).

De 363 raka citattecknen hör hemma här som korrektionsposter, aldrig som en
`sed` över exporterna. Bevisläget är ovanligt starkt men domen är fortfarande
advokatens mot PNG:n: del I–III har noll raka och 105 typografiska, medan Krugal
har 50 raka **och** 100 typografiska i samma bok — intern drift, inte
tryckvariation.

**Bindande ramar (AGENTER.md):** max 3 agenter samtidigt totalt, aldrig per sida
(Regel 2). Ingen nästling (Regel 3). En sida per agentuppsättning (Regel 4).
Specialister på Sonnet, advokaten på Opus, modellen i agentens frontmatter och
aldrig i anropet (Regel 1). Skript före LLM (Regel 5) — agenterna **verifierar**
kandidatlistan, de letar inte upp mönstren igen. Bildforensik körs synkront, en i
taget: bakgrundsagenter dödas av 600 s-watchdogen.

**Grind 4:** noll öppna flaggor som inte antingen är avgjorda i
`resolved_reasons` eller köade som `[beslut]` i `beslut.md`.

### Etapp 5 — Avslut per bok (deterministiskt)

```bash
python3 -m pipeline exportera --workdir arbete/<slug>
python3 -m pipeline rapport   --workdir arbete/<slug>
python3 -m pipeline arkivera  --workdir arbete/<slug>
```

Kopiera om `bibliotek/<NAMN>.md`. Kontrollera att `bok.json`s `byggd_med` och
`export/proveniens.json` står på HEAD.

---

## 5. Definition av klar (per bok)

En bok är ikapp när **alla åtta** gäller:

1. Geometri mätt; ingen sida under *Sidor utan användbar geometri*.
2. `forbesikta --force` körd på nuvarande HEAD över samtliga sidor.
3. Driftvakten tyst, eller larmet utrett och nedskrivet i `beslut.md`.
4. Alla sidor har `final.json`.
5. Noll öppna `review_reasons` — avgjorda ligger i `resolved_reasons` med belägg.
6. `beslut.md`s öppna kö saknar `[beslut]`-poster.
7. `frys` + `diffa` visar noll oförklarade ordförändringar.
8. Export stämplad på HEAD, käll-PDF i `arkiv/`, läskopia i `bibliotek/`.

## 6. Vad som INTE ska göras

- **Inte** batcha Etapp 3 utan att Grind 2 hållit.
- **Inte** köra `forbesikta` brett före geometrin och bocka av böcker på utfallet
  (§1) — det producerar en falsk trygghet, inte en screening.
- **Inte** mäta om del I–III. Del III:s 103 handmätta boxar är oersättliga och
  boken mäts medvetet inte om.
- **Inte** rätta raka citattecken maskinellt över exporterna.
- **Inte** skriva köposter för sådant som går att mäta. Går frågan att avgöra med
  en beskärning ur skanningen är den ett mätjobb, inte ett köärende — och
  formulera aldrig en köpost med en gissning i.
- **Inte** radera något under `arbete/`. Det är pipelinens state.

## 7. Räkna om underlaget

```bash
python3 -m pipeline status --workdir arbete/<slug>          # OBS: se §2
python3 -m unittest discover -s tests -t .                  # 484 tester
```

Öppna flaggor, geometritäckning och raka citattecken räknas ur sidfilerna
(`final.json` där den finns, annars `validated.json`) — `review_reasons` mot
`resolved_reasons`, `source.bbox` mot elementantal, `"` i elementens `text`.
Efter Etapp 1a gör `status` det själv.
