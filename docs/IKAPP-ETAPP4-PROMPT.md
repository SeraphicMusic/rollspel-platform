# Överlämning: ikappkörningens Etapp 4

*Omskriven 2026-08-06 efter första agentvågen. Allt nedan är MÄTT och går att
räkna fram igen med kommandona i §7. Föregående version av det här dokumentet
hade tre siffror som inte höll — de är rättade nedan och felen förklarade, för
det är felen som är instruktiva.*

Klistra in avsnittet »Prompt« i en ny session. Resten är underlaget.

---

## Prompt

> Kör vidare på Etapp 4 i `docs/IKAPP-ALLA-BOCKER.md`. Underlaget står i
> `docs/IKAPP-ETAPP4-PROMPT.md` — läs den först, och läs `AGENTER.md` SLAVISKT
> innan du startar en enda agent.
>
> Tre arbetsströmmar:
>
> 1. **48 sidor utan `final.json`** i fyra böcker (§2). Terminal State ensam
>    står för 32 och är dessutom aldrig screenad förrän nu — den har 274
>    kandidater, flest i hela korpusen. Kör `python3 -m pipeline jobb --workdir
>    <wd> --typ korrektur` för triage och exakta sökvägar.
> 2. **212 sidor med åtgärdbara screeningkandidater** (§3), tabellfrågorna
>    först — de är den oåterkalleliga klassen. Agenterna ska VERIFIERA listan,
>    inte leta upp mönstren igen (Regel 5).
> 3. **1019 öppna granskningsflaggor** (§4). Fyra böcker bär 563 av dem, och
>    ingen av de fyra har en enda avgjord flagga.
>
> **Läs §5 innan du skriver en enda agentprompt.** Den innehåller de sex
> instruktioner som gav samtliga fynd i första vågen. Den viktigaste: säg åt
> specialisterna att fastställa vad som STÅR i trycket, inte att bedöma om
> draftens svenska är korrekt. Sex av vågens fynd var tysta normaliseringar
> som ingen jämförelse mot draften kan se.
>
> Bindande ramar: max 3 agenter samtidigt TOTALT, aldrig per sida (Regel 2).
> Ingen nästling (Regel 3). En sida per agentuppsättning (Regel 4).
> Specialister på Sonnet, advokaten på Opus, modellen i agentens frontmatter
> och aldrig i anropet (Regel 1). Bildforensik körs synkront, en i taget.
>
> Efter varje bok: `sammanfoga`, `exportera`, `rapport`, `diffa`, och sedan
> **`python3 scripts/oforklarade_ord.py arbete/<slug>`** — den grinden är
> mekanisk sedan i dag och attribuerar varje ordändring till den post som bär
> den. Exitkod 0 krävs. Därefter `python3 scripts/uppdatera_bibliotek.py
> --verkstall`. Alla 33 är gröna i dag, så varje avvikelse är din.
>
> Rapportera per bok, och stanna bara om ordkonserveringen brister eller om du
> stöter på en fråga som bara en människa kan svara på (då: `beslut.md` under
> `## Öppen kö`, som `- [ ] BQ-NNN`, och gissa aldrig i frågans formulering).

---

## 1. Vad den första vågen gjorde

Tre böcker korrekturlästa till noll öppna flaggor på de behandlade sidorna,
elva sidor totalt, och fem verktygslagningar som ändrade vad screeningen ser.

| Bok | Sidor | Utfall |
| --- | ---: | --- |
| `MUT-VRL-dark-edge-bar` | 3 | Klar, arkiverad. 0 öppna flaggor, 28 avgjorda. |
| `MUT-VRL-sieger-bauhaus-block` | 5 | Klar, arkiverad. 0 öppna, 53 avgjorda. |
| `MUT-REG-skymningslandets-riddare` | 1, 6 | Ström 1 klar. 30 öppna kvar på s.2–5, 7. |
| `MUT-REG-youre-just-a-program` | 1, 2, 6 | Ström 1 klar. 8 öppna kvar på s.2–5. |
| `DOD-REG-…del2-spelledarboken` | 25 | Tabellräddning, se §3. |

**Verktyg** (commits `bbd381c`, `1c99731`, `ece2a5f`, `707afd4`, `f0b8c14`):

- `validera`s `derived_checks` slog bara upp fältet i `data.stats`.
  `Förflyttning` står i `data.other`, så kontrollen gällde KP men aldrig
  Förflyttning — halva sin egen lista, utan att något sa ifrån. **Sju
  räkneavvikelser låg dolda.**
- `forbesikta`s cellmedvetna regler såg `data.rows` men inte statblockens
  `data.stats`/`skills`/`other`. `_texts` ser nu 19–23 fält per statblock i
  stället för 1.
- `scan_words_in_text` tokeniserar ord för ord, så **flerordsalias kunde aldrig
  matcha någonting** — tre av `mutant2089`:s sex handkurerade alias var döda
  sedan de skrevs. Lagat. Samtidigt togs aliaset `rörliga manövrar` bort: det
  var ett kanoniseringsalias, inte en OCR-reparation, och hade skrivit om sex
  print-trogna ställen tyst.
- `scripts/oforklarade_ord.py` är ny. `diffa` svarar på OM orden ändrats, inte
  på om ändringen var avsedd — grinden är noll *oförklarade* ändringar, och
  den skillnaden avgjordes förut genom att en människa läste ordlistan mot
  sidfilerna. Nu attribueras varje ändring till sin post. `uppdatera_bibliotek`
  använder samma regel och spärrar inte längre varje korrekturläst bok.
- `freeze.words` räknade markdowns tabellavdelare `| --- |` som nya ord.

## 2. De 48 sidorna utan `final.json`

| Bok | Sidor |
| --- | --- |
| `MUT-AVE-terminal-state-fruncon-91` | 1–14, 16–18, 20–27, 29–35 (**32 st**) |
| `DOD-AVE-den-nedbrunna-fatburen` | 1–6 |
| `DOD-AVE-den-stulna-elefanten` | 1, 2, 5, 7, 9 |
| `MUT-REG-hacking-eller-hur-man-blir-en-netrunner` | 1–5 |

**Rättelse mot föregående version.** Den listade 63 sidor i tio böcker. Två av
dem — `DOD-VRL-staden-nohstril` s.4 och `DOD-REG-…del3` s.50 — är
`skipped: illustration_only`, alltså helsidesillustrationer utan text som
varken får korrekturjobb eller `final.json`. `archive.py` räknar redan bort
dem. De ska inte stå på en åtgärdslista.

Terminal State är den enda `digital`-boken och har 98 % geometri; de övriga är
inskannade.

## 3. Screeningkandidaterna: 443 par på 212 åtgärdbara sidor

**Rättelse mot föregående version.** Den angav »337 kandidater« och listade dem
per regel. De 337 var **(sida, regel)-par**, inte kandidatposter — och siffran
var dessutom räknad ur en ofullständig screening. Omkörningen på nuvarande HEAD
ger 443 par / 1965 poster.

Skillnaden var inte marginell och den var inte slumpmässig:

- **`MUT-AVE-terminal-state` hade aldrig screenats en enda gång.** 398
  `heuristik.json` fanns på 437 sidor, och de 39 som fattades låg i den bok som
  har flest okorrekturlästa sidor. Den ger nu **274 kandidater**, flest i
  korpusen — och den enda `tabellkandidat`-träffen i hela materialet (s.14).
- **Del II:s screening var räknad ur en äldre sidversion**: 9 kandidater där en
  omkörning ger 147.

Att en screening är körd är ett påstående. Antalet `heuristik.json` mot antalet
sidor är ett mått, och det kostar en `find`. Se AGENTER.md Regel 7a.

| Regel | Par | Poster |
| --- | ---: | ---: |
| `bandbredd` | 138 | 1119 |
| `raka-citattecken` | 99 | 167 |
| `forskjuten-kedja` | 88 | 458 |
| `bbox-felkoppling` | 58 | 121 |
| `kolumnsammanslagning` | 22 | 28 |
| `radsammanslagning` | 16 | 31 |
| `plusminus` | 8 | 9 |
| `tomt-radband` | 5 | 5 |
| `lasordning` | 3 | 6 |
| `punktledare` | 2 | 17 |
| `plusminus-varde` / `kolumnkollaps` / `tabellkandidat` / `linjeregel-suffix` | 1 var | 1 var |

Av 276 sidor med kandidater har **64 bara `bandbredd`** — och de posterna är
till 1119 mot 1155 obundna band, alltså kontext och ingen kö. **212 sidor har
minst en åtgärdbar regel.**

### Tabellerna — läget är ett annat än förra dokumentet trodde

Förra versionen skrev att `tabellkandidat` fyrar noll gånger och att
tabellräddningen därför saknar mekanisk halva. Första delen stämmer inte längre
(terminal-state s.14 fyrar), och andra delen visade sig ha ett annat verktyg:

**`punktledare` är den regel som hittar feltypade tabeller i styckeformade
transkript.** Den fyrade 16 gånger på del II s.25 så snart screeningen kördes om
— en sida som varit korrekturläst och avslutad. Elementen var 33 `list_item` på
formen `1 .....REGNSKOG. Djungler och regnskogar.`, alltså en tryckt tabell där
punktledaren binder kod till hemvist.

**Skadan var inte hypotetisk.** Läsexporten hade flödat om raderna och slagit
ihop skilda tabellrader — posterna 6, 11, 13, B och D hade tappat sin
radidentitet i den fil man matar till andra verktyg. Nu två `table`-element med
tre kolumner, 111 ord in och 111 ord ut.

Kvarstående punktledarträff: **terminal-state s.27**. Plus `tabellkandidat` på
terminal-state s.14. Bägge ligger i ström 1.

De nitton böckerna med noll `table`-element är fortfarande oroande, men
layoutverifierarna har nu prövat elva sidor i fyra av dem mot sidbilden och
funnit noll tryckta tabeller. Det är evidens, inte bevis.

## 4. De 1019 öppna flaggorna

| Bok | Öppna | Avgjorda | | Bok | Öppna | Avgjorda |
| --- | ---: | ---: | --- | --- | ---: | ---: |
| `MUT-AVE-attentat-sypox` | 204 | 0 | | `MUT-AVE-dodspatrullen` | 42 | 0 |
| `DOD-AVE-spindelkonungens…` | 125 | 0 | | `MUT-AVE-harda-bud` | 33 | 0 |
| `DOD-AVE-krugal-svylses-forbannelse` | 122 | 0 | | `MUT-REG-skymningslandets-riddare` | 30 | 20 |
| `DOD-AVE-edsbrytarna-i-erebos` | 112 | 0 | | `DOD-AVE-gripeborgs-hemlighet` | 25 | 0 |
| `MUT-REG-robotar` | 61 | 0 | | `DOD-VRL-staden-nohstril` | 24 | 0 |
| `DOD-AVE-daligt-vatten` | 49 | 0 | | *(20 böcker till med 1–20)* | | |
| `MUT-VRL-mervyn-peak-street` | 45 | 0 | | | | |

Totalt **1019 öppna, 1098 avgjorda** (var 1016/949). Nettot +3 öppna är
riktigt: de nya sidorna stängde fler flaggor än de öppnade, men öppnade några
äkta redaktionella frågor.

**Att `avgjorda` är 0 i tio av de tyngsta böckerna betyder inte att inget är
utrett.** `resolved_reasons` infördes efter att de böckerna rippades, så deras
flaggor har aldrig kunnat stängas spårbart. Flera av dem bär utredningen i
prosa inuti flaggtexten. Läs flaggan innan du utreder om den.

Varje avgjord flagga stängs med
`pipeline.corrections.close_review_reason(el, reason, resolution, closed_by)`.
**Radera aldrig beläggstexten.**

## 5. De sex instruktionerna som gav vågens fynd

Skriv in dem i agentprompterna. De är billiga och de fungerade.

1. **»Fastställ vad som STÅR, inte om draftens svenska är korrekt.«** Sex av
   vågens fynd var tysta normaliseringar — draften hade gjort trycket MER
   korrekt än det är: `annalkande` för tryckets `analkande`, `på väg` för
   `påväg`, `Okay. Det kan jag fixa` för `Okay, Det kan jag Fixa,`, `detta` för
   `dessa`, plus två tryckta ord som draften utelämnat helt. Ingen jämförelse
   mot draften kan se det; en draft som ser språkligt oklanderlig ut är precis
   vad en tyst normalisering ser ut som. Be om korrektionsposten med TRYCKET
   som `original`.
2. **»Räkna illustrationerna.«** Tre böcker hade en bild som saknades helt, och
   alla tre hade samma form: **en teckning som delar ram med ett textelement
   som redan var extraherat.** `forbesikta` läser text, och en bild utan
   element har ingen text — ingen deterministisk regel ser det. Enda motmedlet
   är att räkna. Metodvarning: leta inte bara efter halvtonsraster, för kartor
   och linjeteckningar saknar raster helt (advokatens första metod hade missat
   sieger s.4:s planritning). Skriv antalet per sida i `beslut.md` så att
   nästa sida har en serie att pröva mot.
3. **»Leta serie innan du beskär.«** Sidfötter, folier och återkommande termer
   avgörs gratis av sina grannar. `miplant` fälldes på att boken har 30
   `mioplant` och noll `miplant`; fyra sidfötter avgjordes utan en enda
   uppförstoring.
4. **Ge advokaten specialisternas NEGATIVA påståenden att pröva, inte bara
   deras fynd.** Advokaten fällde en friad sida (sieger s.2, saknad
   illustration), en rubriknivåpremiss mätt mot fel granne, ett spaltantal som
   var motstridigt nedskrivet, och en folioserie generaliserad ur ett enda
   sammanfallande fall. Regel 9b i drift.
5. **Skriv in vad som REDAN är avgjort i prompten.** Boknivåbesluten sparade
   utredning på varje efterföljande sida, och specialisterna följde dem.
6. **Sätt gränsen mot Regel 8a:s högerkolumn explicit i prompten.** Vågen
   avvisade `allt för`→`alltför` (periodkorrekt variant), `stridscenerna`
   (saknat foge-s efter substantivisk förled), `men` för `med` (läser bättre
   är inget belägg) och en obalanserad parentes med tre lika rimliga
   rättningar. Alla fyra var frestande.

## 6. Kända svagheter

1. **Bindningstäckningen är ojämn med flit.** Edsbrytarna 68 %, Robotar 55 %,
   mot `MUT-AVE-i-drakens-klor` 2 %, `DOD-VRL-staden-nohstril` 5 %.
   `binda_rader` vägrar hellre än gissar, och de låga siffrorna är sidor där
   mätningen och trycket är oense om spaltantalet. **Rör inte den spärren.**
2. **`rows.py` hittar rätt spaltantal på 71 % av sidorna.** De återstående
   29 % är den direkta orsaken till punkt 1. Vill du höja täckningen ligger
   arbetet HÄR, inte i `binda_rader`.
3. **BQ-021 (a) i del III är olöst.** En avsnittsgräns kan kapa en tryckt rad:
   `_segments` räknar gränser ur den sidbreda bandlistan, så en gräns kan hamna
   inuti en rad i den spalt som inte styr gränsen. Mätt på del III s.32.
4. **`MUT-REG-youre-just-a-program` har `radboxar.json` men inget av bokens 238
   element har `source.rader` eller `source.bbox`** (BQ-002 i den boken). Det
   är Regel 9-symptomet: läsexporten bryter varje tryckt rad som eget stycke.
   Åtgärd: `binda_rader.py --utvardera` först.
5. **`validera --force` är allt-eller-inget per bok och läser `final.json` som
   källa** — på en korrekturläst sida skriver den alltså över draften, och
   flaggorna når ändå inte exporten eftersom `merge` föredrar `final.json`.
   Den lagade `derived_checks` nådde därför bara sidor utan `final.json`. De
   fyra räkneavvikelser som ligger i redan korrekturlästa böcker
   (`MUT-AVE-harda-bud` s.8, `MUT-AVE-lovligt-byte` s.8,
   `MUT-VRL-mervyn-peak-street` s.6, `MUT-AVE-dodspatrullen` s.10 — den sista
   redan funnen för hand) måste alltså läggas i advokatens uppdrag när de
   böckerna tas.

## 7. Räkna om underlaget

```bash
python3 -m unittest discover -s tests -t .            # 571 tester
python3 scripts/oforklarade_ord.py --alla             # ordgrinden, alla 33
python3 scripts/uppdatera_bibliotek.py                # torrkörning
python3 -m pipeline status --workdir arbete/<slug>    # flaggor, BQ, proveniens
find arbete -name heuristik.json | wc -l              # screeningens TÄCKNING
```

Kandidater, flaggor och geometri per bok räknas ur sidfilerna — `regler` i
`page_NNN.review/heuristik.json`, `review_reasons` mot `resolved_reasons`, och
`source.bbox` mot elementantal.
