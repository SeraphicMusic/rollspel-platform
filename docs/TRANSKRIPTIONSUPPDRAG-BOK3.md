# Transkriptionsuppdrag — DoD grundregler 1991, del III (Spelarboken)

Den här filen ÄR agentprompten. Ge varje transkriptionsagent sökvägen hit och
sidans tre sökvägar (PNG, radboxar, output) — klistra inte in kontraktet i
prompten, det kostar tokens per agent och riskerar att divergera mellan dem.

Arbetskatalog: `arbete/DOD-REG-grundregler-1991-del3-spelarboken/`
Modell: **Sonnet**, max 3 parallellt, en sida per agent, ingen nästling
(AGENTER.md Regel 1-4). Ge varje agent en EGEN scratchpad-underkatalog —
under bok 2:s körning skrev parallella agenter över varandras beskärningar.

Mätningen flaggar dessa sidor som bilddominerade; där gäller PNG:n och
`"rader": []` framför radlistan:
**1, 3, 13, 24, 25, 26, 27, 33, 36, 40, 41, 42, 43, 48, 49, 50.**
Spaltdetekteringen faller helt på **1, 13, 25, 27, 50**.

---

Du transkriberar EN sida ur en inskannad svensk rollspelsbok (system: `dod`).
PNG:n är ALLTID sanningskällan. Skriv exakt en JSON-fil till din output-sökväg.

## Filformat

`{"page": <nr>, "layout": {"columns": <n>}, "elements": [...]}`

En ren illustrationssida får ha tom `elements` endast tillsammans med
`"skipped": {"reason": "illustration_only"}`.

Elementtyper: `heading` (med `level` 1–3), `paragraph` (ev. `"style": "italic"`),
`boxed_text`, `list` (`data.items`), `list_item`, `table` (`data.headers` +
`data.rows`), `table_header`, `table_cell`, `table_caption`, `table_note`,
`requirement`, `statblock`, `toc_entry`, `index_entry`, `page_artifact`.
Skapa ALDRIG typen `illustration`.

Varje element: `text` (utom table/statblock/list), `confidence` (0–1),
`source.region` och `source.rader`. Osäkra ord markeras `[?]` i texten och
listas i elementets `uncertain`.

## source.rader — du anger RADINDEX, aldrig koordinater

Din radbox-fil listar sidans uppmätta rader i läsordning. Ange vilka rader ett
element täcker som `"source": {"region": "<region ur mätningen>", "rader": [3]}`.
Pipelinen räknar fram bbox deterministiskt ur dem.

- En brödtextrad → ett element, `"rader": [n]`.
- En tabell → ETT `table`-element, `"rader": [n, n+1, ...]` för alla rader den
  täcker. Dela ALDRIG upp en tabell i ett element per rad.
- Samma sak för `statblock` och `list`: ett element, alla dess rader.
- Hittar du text i PNG:n som saknar uppmätt rad: transkribera den ändå och
  sätt `"rader": []`. En saknad box är en lucka i en heuristik; en påhittad
  koordinat är ett fel som ser ut som data. **Gissa aldrig ett radindex** —
  hellre tom lista än fel rad.

Regionnamn ur mätningen: `vänsterkolumn`, `högerkolumn`, `sidbredd`,
`sidhuvud`, `sidfot`.

**Varning:** på vissa sidor har mätningen inte hittat spalterna och listar allt
som `sidbredd`. Ser radlistan uppenbart fel ut mot PNG:n — använd `"rader": []`
för sidans element i stället för att tvinga fram en koppling.

## Tabeller (kontraktets viktigaste punkt)

**Ser sidan ut att ha två eller flera kolumner med korta, radvis parade värden
är det en tabell.** Den MÅSTE typas `table` — aldrig som en följd av
`paragraph`. En tabell som typas `paragraph` förlorar sin struktur FÖR GOTT.

1. Korta element (under ~40 tecken) vars vänsterkanter återkommer i två eller
   flera fasta x-lägen, rad efter rad → tabell.
2. Rubrikrad överst → dess celler blir `headers`. Saknas tryckt rubrikrad:
   tomma strängar, inte påhittade.
3. Celler transkriberas EXAKT, tomma celler som `""`. Gissa aldrig ett värde
   för att raden ska gå jämnt ut — saknas en cell är det ett fynd.

```json
{"type": "table",
 "data": {"headers": ["Teknik", "Grundkostnad"],
          "rows": [["Avväpning", "1,0"], ["Bakåtspark", "0,5"]]},
 "confidence": 0.9,
 "source": {"region": "vänsterkolumn", "rader": [12, 13, 14]}}
```

- `table_note` — fotnoter och teckenförklaringar under tabellen. Aldrig i `rows`.
- `table_caption` — tryckt tabellrubrik ovanför tabellen.
- Går raderna inte att para ihop säkert: lägg cellerna som en följd av
  `table_header`/`table_cell` i läsordning, en cell per element. Reservformen
  är ALLTID bättre än `paragraph`.

## Listor och krav

- `list` med `data.items` — sammanhållen punktlista i ett svep, ingen `text`.
- `list_item` — enskild punkt som eget element, punkttecknet kvar (`• Köpa ras`).
- `requirement` — tryckt grundegenskapskrav som står för sig, typiskt inom
  parentes: `(INT 12, PSY 12)`. Aldrig ihopslaget med rubriken eller stycket.

## Statblock

```json
{"type": "statblock",
 "data": {"name": "<namn>", "stats": {"STY": 10, "STO": 22},
          "skills": {"<färdighet>": <värde>},
          "weapons": [{"name": "Bett", "attack": "65%", "damage": "1T6+2"}],
          "other": {"Hemvist": "..."}},
 "confidence": 0.9}
```

Attribut i dod: STY, FYS, SMI, INT, PSY, KAR, STO. Transkribera värden EXAKT
som de står — även om de ser fel ut. Valideringen rättar spårbart.

## Läsdisciplin (obligatorisk)

- **Gissa aldrig** — osäkra ord skrivs `[?]` och listas i `uncertain`.
- **Normalisera INTE tryckfel.** Står det `aktiviter` i trycket skriver du
  `aktiviter`, inte `aktiviteter`. Att tyst rätta ett sättningsfel är ett fel i
  sig — trycket måste först fastställas. Detta är det vanligaste felet vi ser.
- **Typografiska citattecken.** Trycket sätter ”…” (U+201D) och ’…’, inte raka
  "…" eller '…'. Kontrollera varje citattecken; raka tecken är en återkommande
  felkälla i den här bokserien.
- Modernisera inte språket; bevara ton, stavning och styckeindelning.
- Tvåkolumnssidor: HELA vänsterspalten före högerspalten.
- Sidhuvud, sidfot, sidnummer och vattenstämpeln transkriberas som
  `page_artifact`. Vattenstämpeln `Drakar och Demoner är © RiotMinds AB` under
  sidfoten transkriberas INTE — den är digitala utgåvans stämpel, utanför
  satsytan.
- Linjeregler kring sidhuvudet är ornament och transkriberas aldrig.
- En rubrik som bryts av radfall är ETT `heading`-element, inte ett per rad.
- Ellips återges som `...` (tre punkter), inte som `…`.
- Förkortningar sätts med blanksteg mellan delarna: `t. ex.`, `m. m.`, `o. s. v.`
- Sätt `confidence` ärligt per element (1.0 = kristallklart).

## Seriens boknivåbeslut — redan avgjorda, följ dem

Del I och II är klara. Följande är avgjort för HELA serien och ska inte
utredas om. Avvik aldrig från dem utan att flagga.

- **Punktledare i innehållsförteckningen normaliseras till `Titel ... N`** —
  tre punkter med blanksteg omkring, oavsett hur många punkter trycket sätter.
  Titel och sidnummer återges exakt som tryckt; bara ledaren normaliseras.
- **Löpande kolumntitel** (kapitelnamnet mellan linjeregelraderna överst) typas
  `page_artifact`, aldrig `heading`. Bara kapitelöppningens stora titel på egen
  uppslagssida är `heading` nivå 1.
- **Versaler och kapitäler är ingen nivåskillnad.** Trycket blandar dem för
  jämnstora avsnittsrubriker; båda ligger på samma nivå. Versalsatta rubriker
  och sidhuvuden skrivs med VERSALER — gemenisera dem inte.
- **Exempelrutor är genomgående kursiva** och får `"style": "italic"` på varje
  rad. Saknas markeringen är det en lucka, inte ett val.
- **Betoningskursiv inne i en rad återges inte.** Schemat har bara
  element-nivå `style`. Helt kursiva rader får `style`; kursiv på enstaka ord
  mitt i en rad skrivs som vanlig text. Samma sak för fetstilta punktetiketter.
  Ingen korrektionspost — det är ingen felavläsning.
- **Dubbla mellanslag i satsen normaliseras till ett.**
- **Vapenrader hör i statblockets `weapons`, inte `skills`.** Formen
  `2 Klor (1T6) 16` delas: `attack` = FV-siffran, `damage` = parentesens
  innehåll. Rader utan tärning (`Beröra offer 18`) stannar i `skills`.

## Bildpolicy (obligatorisk)

- Hoppa över alla illustrationer, vinjetter och bildmotiv.
- Beskriv eller sammanfatta ALDRIG vad en bild föreställer.
- Transkribera inte text som är en del av bildmotivet (skyltar, föremål,
  inskriptioner, etiketter inne i en karta). En typografiskt separat bildtext
  eller vanlig brödtext bredvid en illustration ÄR boktext och tas med.
- Gör ingen detaljerad bildanalys för att leta dold text.
- Är sidan enbart illustration utan boktext:
  `{"page": N, "layout": {"columns": 0}, "elements": [],
    "skipped": {"reason": "illustration_only"}}`

## Utdata

Skriv filen. Svara sedan med EN rad: sidnummer, antal element, och eventuella
osäkerheter. Skriv inte ut transkriptet i svaret — det är slöseri.
