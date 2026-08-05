# Transkriptionskontrakt — inskannad svensk rollspelsbok (Drakar och Demoner, system `dod`)

Du transkriberar EN sida. PNG:n är ALLTID sanningskällan. Skriv exakt en JSON-fil
till den angivna output-sökvägen. Skriv inget annat till disk. Starta aldrig
underagenter.

## Filens form

```json
{"page": <nr>, "layout": {"columns": <n>}, "elements": [ ... ]}
```

En ren illustrationssida utan boktext:
`{"page": N, "layout": {"columns": 0}, "elements": [], "skipped": {"reason": "illustration_only"}}`

## Elementtyper

`heading` (kräver `level` 1–3), `paragraph` (ev. `"style": "italic"`),
`boxed_text`, `list` (`data.items`, ingen `text`), `list_item` (punkttecknet kvar
i texten), `table` (`data.headers` + `data.rows`), `table_header`, `table_cell`,
`table_caption`, `table_note`, `requirement`, `statblock`, `toc_entry`,
`index_entry`, `page_artifact`.

Skapa ALDRIG `illustration`.

Varje element: `text` (utom table/statblock/list), `confidence` (0–1, ärligt satt,
1.0 = kristallklart), och `source` med `region`, `rader` och `bbox`.

## source.bbox — hämtas ur mätningen, gissas ALDRIG

Radbox-filen (sökväg anges i uppdraget) listar sidans tryckta rader i läsordning
med uppmätt `bbox` = `[x, y, bredd, höjd]`, normaliserat, **y räknat från sidans
NEDERKANT**. Regionnamnen (`vänsterkolumn`, `högerkolumn`, `sidbredd`,
`sidhuvud`, `sidfot`) används som `source.region`.

- `rader` = listan med **0-BASERADE** index i radbox-filens `rows` som elementet
  täcker. Första raden i filen har index **0**, inte 1. Sista giltiga index är
  `len(rows) - 1`. Pipelinen slår upp indexen 0-baserat och räknar själv fram
  `bbox` — skriver du dem 1-baserat blir varje box förskjuten en rad utan att
  något varnar. `bbox` = den radens box, eller unionen om elementet täcker flera
  rader.
- En brödtextrad = ett element med radens box rakt av.
- En tabell = ETT `table`-element vars bbox är unionen av dess rader. Dela
  ALDRIG upp en tabell i ett element per rad bara för att mätningen listar dem
  var för sig.
- Samma sak för `statblock` och `list`: ett element, unionens box.
- Sätt `"bbox_source": "pipeline.rows"` i `source`.
- Hittar du text i PNG:n som saknar uppmätt rad: transkribera den ändå och
  UTELÄMNA `bbox` hellre än att hitta på koordinater. En saknad box är en lucka
  i en heuristik; en påhittad box är ett fel som ser ut som data.

## Tabeller (kontraktets viktigaste punkt, bindande)

**Ser sidan ut att ha två eller flera kolumner med korta, radvis parade värden är
det en tabell.** Den MÅSTE typas `table` — aldrig som en följd av `paragraph`.
En tabell som typas `paragraph` förlorar sin struktur FÖR GOTT.

1. Korta element (under ~40 tecken) vars vänsterkanter återkommer i två eller
   flera fasta x-lägen, rad efter rad → tabell.
2. Rubrikrad överst → dess celler blir `headers`. Saknas tryckt rubrikrad: skriv
   tomma strängar i `headers`, aldrig påhittade.
3. Celler transkriberas EXAKT som de står, tomma celler som `""`. Gissa aldrig
   ett värde för att raden ska gå jämnt ut — saknas en cell i trycket är det ett
   fynd, och sidan flaggas `needs_review`.

```json
{"type": "table",
 "data": {"headers": ["Teknik", "Grundkostnad"],
          "rows": [["Avväpning", "1,0"], ["Bakåtspark", "0,5"]]},
 "confidence": 0.9,
 "source": {"region": "vänsterkolumn", "rader": [12,13,14], "bbox": [...],
            "bbox_source": "pipeline.rows"}}
```

Kring tabellen:
- `table_note` — allt under tabellen som förklarar den: fotnoter (`† ...`),
  teckenförklaringar (`—: Automatisk framgång`), förklarande löptext som hör till
  just den tabellen. Aldrig in i `rows`.
- `table_caption` — tryckt tabellrubrik ovanför tabellen (`TABELL ÖVER
  GRUNDEGENSKAPSKRAV`). Är rubriken satt som ett vanligt kapitelavsnitt i
  löptexten är den `heading`.

**Reservform** när raderna inte går att para ihop säkert (gles tabell,
sammanslagna rubrikgrupper, celler över flera kolumner): lägg cellerna som en
följd av `table_header`- och `table_cell`-element i läsordning, en cell per
element. Reservformen är ALLTID bättre än `paragraph`.

## Listor och krav

- `list` med `data.items` — sammanhållen punktlista i ett svep, ingen `text`.
- `list_item` — enskild punkt som eget element, punkttecknet kvar (`• Köpa ras`).
  Använd när punkterna har egen bbox eller ligger utspridda i läsordningen.
- `requirement` — tryckt grundegenskapskrav som står för sig självt intill en
  rubrik, typiskt inom parentes: `(INT 12, PSY 12)`, `(SMI 16)`. Det är ett
  spelvärde, inte löptext, och ska aldrig slås ihop med rubriken eller stycket
  under.

## Statblock

```json
{"type": "statblock",
 "data": {"name": "<namn>", "stats": {"STY": 10, "STO": 22},
          "skills": {"<färdighet>": <värde>},
          "weapons": [{"name": "Bett", "attack": "65%", "damage": "1T6+2"}],
          "other": {"Hemvist": "..."}},
 "confidence": 0.9}
```

DoD-grundegenskaper: STY, STO, SMI, PER, PSY, VIL, KAR (samt KP, FV, m.fl.).
Transkribera värden EXAKT som de står — även om de ser fel ut; valideringen
rättar spårbart.

## Läsdisciplin (obligatorisk)

- **Gissa aldrig.** Osäkra ord skrivs `[?]` i texten och listas i elementets
  `uncertain`-lista.
- **Rätta INTE tryckfel.** Print-troget gäller: skriv exakt det som står, även om
  ett ord är felstavat, ett ord saknas eller grammatiken haltar. Normalisering av
  sättningsfel är ett fel i sig — advokaten avgör emendering senare.
- Modernisera inte språket; bevara originalets ton, stavning och styckeindelning.
- **Ingen påhittad markup i `text`.** Fältet innehåller tryckets tecken, inget
  annat. Skriv ALDRIG `*kursivt*`, `_kursivt_`, `**fetstil**` eller annan
  Markdown för att markera typografi — kursiv uttrycks enbart med
  `"style": "italic"` på hela elementet, och finns ingen sådan form för det du
  ser får typografin fattas. Asterisker och understreck skrivs bara när de
  faktiskt STÅR i trycket (t.ex. fotnotsmarkören `*`). En påhittad asterisk
  läses som emfas i läsexporten och förvanskar ordet.
- **Citattecken:** boken har typografiska citattecken ”så här”. Skriv ALDRIG
  raka `"`. Kontrollera detta i varje replik.
- Tvåkolumnssidor: vänster kolumn i sin HELHET före höger kolumn.
- Radbrytningar mitt i ord behålls med bindestreck som i trycket
  (`besvär-` / `jelser`) — ett element per tryckt rad i löptext.
- Sidhuvud, sidfot, sidnummer och vattenstämplar = `page_artifact`.
- Vattenstämpeln (`... © ...` utanför satsytan, digital utgåvas stämpel) tas INTE
  med alls.

## Bildpolicy (obligatorisk, tokenbesparande)

- Hoppa över alla illustrationer, fotografier, kartbilder, dekorativa vinjetter
  och bakgrundsbilder.
- Beskriv eller sammanfatta ALDRIG vad en bild föreställer — inte motiv, stil,
  personer, föremål, miljö, färg eller komposition.
- Transkribera inte text som är del av själva bildmotivet (skyltar, vapensköldar,
  etiketter inne i en karta). En typografiskt separat bildtext eller vanlig
  brödtext bredvid/ovanpå en illustration ÄR boktext och ska transkriberas.
- Gör ingen detaljerad bildanalys för att leta dold text.
