# Uppdrag: tabellstöd före bok 2

Deterministiskt pipelinearbete. **Inga korrekturagenter ska köras i detta
uppdrag** — allt nedan är Python, tester och skilltext.

## Bakgrund (mätt på DoD-grundreglerna 1991, del I, 68 sidor)

Boken är färdigkorrekturläst. Under slutgranskningen visade sig ett fel som
kostar mer än alla exportbuggar tillsammans:

**Alla 25 maskinläsbara tabeller kommer från sidorna 11–39.** Från sida 40 och
framåt finns inga `table`-element alls, trots att trycket har gott om tabeller.
Transkriptionen typade dem som `paragraph`, och då är strukturen borta för
gott — ingenting nedströms kan återskapa den.

Elementtypsräkning i `export/bok.json`:

```
paragraph 3309 · heading 133 · toc_entry 128 · page_artifact 305 · boxed_text 201
list 6 · list_item 62 · table 23 · table_header 9 · table_cell 33 · table_note 6
requirement 6
```

Sidor med riktiga `table`-element: 11, 24, 25, 26, 27, 28, 29, 30, 31, 36, 37, 39.

Konkreta förluster — advokaten verifierade cellerna forensiskt, värdena är
korrekta, men de renderas som lösa stycken i `bok.md`:

| Sida | Tabell | Arbete som gjordes |
|---|---|---|
| 48 | Förfalskningstabellen | saknat modifikationsvärde återställt |
| 56 | Simtabellen | två saknade FN-celler uppmätta |
| 58 | Tekniklistan | 22 rader × 2 celler verifierade |
| 61 | Vapengrupper | 15 rader × 3 kolumner genomräknade |

Orsaken är kontraktsdrift: `table` nämns på **en rad** i skillens typvokabulär
([SKILL.md:171](../.claude/skills/extrahera/SKILL.md#L171)) utan regel för när
den ska användas och utan någon kontroll. Sidorna 11–39 fick tabeller, sedan
drev det bort.

Nästa bok är enligt användaren **betydligt mer tabelltung**. Fixas inte detta
före den körningen upprepas felet på varje sida.

## Uppgifter, i prioritetsordning

### 1. Tabellkontrakt i transkriptionen (nödvändig)

Fil: [.claude/skills/extrahera/SKILL.md](../.claude/skills/extrahera/SKILL.md),
avsnittet "Transkriptionskontrakt" (rad ~164–194).

- Skriv ett eget stycke om tabeller med en **bindande regel**: ser sidan ut att
  ha två eller flera kolumner med korta, radvis parade värden är det en tabell
  och MÅSTE typas `table` med `data.headers` + `data.rows` — aldrig en följd av
  `paragraph`.
- Ta med ett fullständigt JSON-exempel (samma detaljnivå som statblock-exemplet
  redan har).
- Dokumentera `table_header` / `table_cell` / `table_note` som **tillåten
  reservform** när rader inte går att para ihop säkert; [pipeline/tables.py](../pipeline/tables.py)
  monterar dem. Idag saknas de helt i vokabulärlistan trots att de finns i
  produktionsdata — det är i sig en orsak till drift.
- Nämn `list` / `list_item` / `requirement` i samma svep; också odokumenterade.

Ändra inte statblock-kontraktet.

### 2. Tabelldetektor i `forbesikta` (nödvändig)

Fil: [pipeline/preflight.py](../pipeline/preflight.py). Ny sidnivåregel
`tabellkandidat`, registrerad i `RULES`, `scan_page` och räknarna.

Signal: en följd av element typade `paragraph` (eller `boxed_text`) som är
korta (~< 40 tecken) och vars vänsterkanter faller i **två eller flera täta
x-kluster** som återkommer radvis. Använd `source.bbox` — `[x, y, bredd, höjd]`,
normaliserad, **y räknat från sidans NEDERKANT**.

Utfallet är en `needs_review`-flagga med gissat kolumnantal och elementens id:n,
aldrig en korrektionspost — det är ett typningsfel, inte ett textfel.

**Kalibrera mot facit, inte mot magkänsla.** Arbetskatalogen
`arbete/40-drakar-och-demoner-grundregler-fjarde-utgavan-1991-i-rollpersonen-riotminds/`
har 68 färdiga sidor och är regressionskorpus:

- Måste slå ut på s. 48, 56, 58, 61 (kända tabeller som typades `paragraph`).
- Ska vara tyst på ren löptext (t.ex. s. 41–47, 49–55).
- Sidorna 11–39 har redan riktiga `table`-element — regeln ska inte gnälla där.

Kör som revision med `preflight.scan_page` direkt på `page_NNN.final.json`;
**skriv inte om `heuristik.json` för färdiga sidor** och radera aldrig något
under `arbete/`.

### 3. Vertikal radsammanslagning (billig, gör den)

Samma fil. Ett element vars bbox-höjd är ~2× sidans medianhöjd har slagit ihop
två tryckta rader vertikalt. Observerat på s. 60 och s. 68 och fångas inte av
någon nuvarande regel (`rule_column_merge` mäter bara bredd).

### 4. Sidtypsmedveten läsordning (billig, gör den)

`rule_reading_order` och `rule_column_interleaving` antar tvåspaltig löptext.
På tabellsidor och blanketter ger de falska larm — revisionen över den färdiga
boken gav 54 läsordningsträffar, varav de på s. 61, 64, 65, 67, 68 var falska
positiva skapade av advokatens *korrekta* omordning.

Klassificera sidan geometriskt (spaltantal, andel korta element, x-kluster)
och kör reglerna bara på tvåspaltig löptext. Falska larm är ren tokenkostnad i
korrekturen.

### 5. Bättre diagnostik i `tables.assemble` (liten)

[pipeline/tables.py:57](../pipeline/tables.py#L57) rapporterar idag bara
"33 celler går inte jämnt upp på 9 kolumner". Rapportera **vilken rad** som är
kort, så att felet går att åtgärda utan att räkna celler för hand.

## Krav på genomförandet

- Testsviten är **166 tester** och ska passera:
  `python3 -m unittest discover -s tests -t .`
- Nya regler ska ha tester i `tests/test_preflight.py` med både positiv och
  negativ kontroll (regeln slår ut / regeln är tyst).
- Följ husets principer i [CLAUDE.md](../CLAUDE.md) och
  [AGENTER.md](../AGENTER.md): idempotens, inga tysta korrigeringar,
  förbesiktningen producerar kandidater — aldrig ändringar.
- Läs [docs/FORTSATTNING-GRUNDREGLER.md](FORTSATTNING-GRUNDREGLER.md) för hela
  lägesbilden, kostnadsmodellen och listan "Kvarstående".
- Radera aldrig `arbete/`-kataloger.

## Innan du börjar

Tre commits ligger opushade (`b36813c`, `d5ad861`, `612259d`) — pushen blockerades
av behörighetsklassificeraren i förra sessionen. Fråga användaren om den ska
göras först.

## Efteråt

1. Kör revisionen över alla 68 färdiga sidor igen och redovisa vad de nya
   reglerna hittar och hur många falska positiva som försvann.
2. Uppdatera "Kvarstående" i [docs/FORTSATTNING-GRUNDREGLER.md](FORTSATTNING-GRUNDREGLER.md).
3. Föreslå att bok 2 mäts på **tre sidor** innan skalan för resten bestäms —
   bok 1 landade på ~400k tokens och ~28 minuter per sida, och strukturarbete
   var den enskilt största kostnadsdrivaren.

Bok 2:s PDF ligger ännu inte i `import/` (bara bok 1). Be om den om den behövs
för kalibrering, men kalibrera i första hand mot bok 1 där facit finns.

## Vad som INTE ingår

`kind`-backfill på s. 1–36 (1755 poster), riktad omkorrektur av bok 1, och de
öppna boknivåbesluten i granskningsrapporten. Inget av det blockerar bok 2.
