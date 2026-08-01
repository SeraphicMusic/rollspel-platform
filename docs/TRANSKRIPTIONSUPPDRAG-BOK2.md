# Transkriptionsuppdrag — DoD Spelledarboken (1991), bok 2

Detta är arbetsordern för de delegerade transkriptionsagenterna i bok 2:s
produktionskörning. Den kompletterar — och ändrar inte —
[transkriptionskontraktet](../.claude/skills/extrahera/SKILL.md)
(§Transkriptionskontrakt, §Tabeller, §`source.bbox`), som är bindande och som
du ska läsa i sin helhet innan du börjar.

Boken: *Drakar och Demoner, grundregler fjärde utgåvan (1991), del II
Spelledarboken*, inskannad, 66 sidor, system `dod`. Arbetskatalog:
`arbete/DOD-REG-grundregler-1991-del2-spelledarboken/`.

## Ett element per tryckt rad

Varje tryckt textrad blir ETT element. Foga INTE ihop rader till stycken —
avstavningar och radbrytningar bevaras precis som de står. Läsexporten flödar
tillbaka raderna till stycken senare; formen är avgjord och uppmätt.

**Undantag:** `table`, `statblock` och `list` är ETT element var, aldrig ett per
rad. Tabellkontraktet i SKILL.md går före allt annat här: ser sidan ut att ha
två eller flera kolumner med korta, radvis parade värden är det en tabell och
MÅSTE typas `table` (eller reservformen `table_header`/`table_cell`) — aldrig
som en följd av `paragraph`. En tabell som typas `paragraph` förlorar sin
struktur för gott.

## `source.rader` — du anger RADER, aldrig koordinater

Sidans mätning ligger i `page_NNN.radboxar.json` med en lista `rows`: varje post
är en uppmätt tryckt rad med `region` och `bbox`, i läsordning. **Radens index
är dess position i `rows`, med 0 som första.**

Varje element får `"source": {"region": "<region>", "rader": [<index>, ...]}`:

- Brödtextrad → `"rader": [17]`, den rad elementet motsvarar.
- Tabell/statblock/list → alla rader elementet spänner över; pipelinen räknar
  ut unionsboxen deterministiskt.
- Text i PNG:n utan uppmätt rad → `"rader": []`. Elementet transkriberas ändå,
  utan box.

**Skriv aldrig `bbox` själv.** En påhittad koordinat är ett fel som ser ut som
data; en saknad box är bara en lucka i en heuristik. Pipelinen fyller i boxen
ur mätningen när sidan bokförs, och avvisar sidan om ett radindex inte finns.

Fällor som redan kostat tid:

- Mätningen träffar ~98,5 % av elementen. Den missar korta slutrader och
  rubriker strax under sidhuvudet. Då gäller `"rader": []`, aldrig grannraden.
- Ett band som spänner över BÅDA spalterna (bredd över 0,6) är två rader som
  mätningen slagit ihop — det tillhör inget enskilt element. Båda elementen
  får `"rader": []`.
- Antalet band är inget facit för antalet rader: flera tryckta rader kan ligga
  i ett gemensamt band.
- Poster märkta `"kind": "grafik"` är bildmaterial, inte textrader.
- På sidor där mätningen flaggat `dominerande_grafik` är banden opålitliga.
  Där gäller PNG:n, och `"rader": []` är oftast rätt svar.

## Bokens egna konventioner

- **Vattenstämpeln** `Drakar och Demoner är © RiotMinds AB` under sidfoten
  utelämnas helt. Den är den digitala utgåvans stämpel, inte boktext. Avgjort.
- **Sidhuvud** (`VARELSER` o.dyl.), sidfot och sidnummer typas `page_artifact`.
  Sidnumreringen är förskjuten: PDF-sida 27 bär tryckt folio 26.
- **Innehållsposter** skrivs `Titel ... 42` — titel, blanksteg, tre punkter,
  blanksteg, sidnummer. Trycket har en punktledare av varierande längd; tre
  punkter är bokseriens etablerade form (bok 1).
- **Typografiska tecken:** trycket har ”…” och ’…’, inte raka `"` och `'`, och
  tankstreck `—`, inte bindestreck. Skriv dem som de står.
- Tvåkolumnssidor läses HELA vänsterkolumnen före högerkolumnen.

## Läsdisciplin

- PNG:n är alltid sanningskällan.
- **Gissa aldrig.** Osäkra ord skrivs `[?]` i texten och listas i elementets
  `uncertain`.
- **Rätta aldrig tryckfel.** Står det `betelar` eller `voylm` i trycket skriver
  du `betelar` och `voylm`. Print-troget gäller undantagslöst. Normalisera inte
  stavning, böjning, ordföljd eller interpunktion och lägg inte till ord som
  saknas — emendering är ett senare steg som djävulens advokat äger, mot PNG:n.
- Spelvärden transkriberas exakt som de står, även när de ser orimliga ut.
- Sätt `confidence` ärligt per element.

## Bildpolicy

- Hoppa över alla illustrationer, kartbilder, vinjetter och bakgrundsbilder.
  Skapa aldrig ett element av typen `illustration`.
- Beskriv eller sammanfatta aldrig vad en bild föreställer.
- Transkribera inte text som ingår i själva bildmotivet (skyltar, föremål,
  inskriptioner, etiketter inne i en karta). Typografiskt separat bildtext och
  brödtext bredvid en illustration ÄR boktext.
- Gör ingen detaljerad bildanalys för att leta dold text.
- Består sidan enbart av en illustration utan boktext:
  `{"page": N, "layout": {"columns": 0}, "elements": [],
    "skipped": {"reason": "illustration_only"}}`

## Kända grafikdominerade sidor

1, 8, 15, 20, 24, 33, 34, 35, 36, 42, 64, 66 — där gäller PNG:n framför
mätningen.

## Arbetsordning

1. Läs SKILL.md:s transkriptionskontrakt och denna fil.
2. Läs sidans PNG med Read (sanningskällan).
3. Läs sidans `radboxar.json`.
4. Skriv exakt en JSON-fil till den angivna output-sökvägen.
5. Svara med en kort sammanfattning: antal element, typer, och vad du var
   osäker på.

Starta aldrig egna underagenter. Skriv inga andra filer, och **kör inga
pipeline-kommandon** — `bokfor`, `validera` och `forbesikta` körs av den som
delar ut jobben, efter att hela vågen är klar. En agent som bokför mitt i
vågen bokför även sina grannars halvfärdiga filer.

Behöver du förstora en detalj i sidbilden: beskär i en temporär fil under
scratchpad-katalogen med nearest-neighbour, aldrig under `arbete/`. Kontrollera
först den inbäddade skanningens faktiska pixelmått — är den inte större än
sidans PNG ger hög DPI bara interpolation.
