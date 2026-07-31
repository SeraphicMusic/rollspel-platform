---
name: extrahera
description: This skill should be used when the user asks to "extract text from RPG PDF", "extrahera text från rollspels-PDF", "rippa bok", "skapa Word från inskannad PDF", or mentions extracting scanned TTRPG books (DoD, Mutant, etc.). Drives the deterministic pipeline and acts as vision transcriber.
allowed-tools: Read, Write, Bash(python3:*), Bash(node:*), AskUserQuestion, Task, Glob, TodoWrite
---

# Rollspels-PDF Extraktor

Extraherar text ur rollspelsböcker via den deterministiska pipelinen (`python3 -m pipeline`).
Pipelinen äger allt state — **hitta aldrig på egna tempmappar eller batchindelningar**.
Alla kommandon körs från repo-roten. Fullständig referens: [README.md](../../../README.md),
transkriptionskontrakt: se §Transkriptionskontrakt nedan.

## Användning

```
/extrahera path="<sökväg till PDF>" [system="dod|mutant2089"] [pages="10-25"] [modell="sonnet|haiku"]
```

## Modell-tiering (Släktforskaren-mönstret: billigaste modell som klarar uppgiften)

- **Pipeline-stegen** (analysera/rendera/validera/sammanfoga/exportera) är ren
  Python — **ingen LLM, noll tokens**. PyMuPDF renderar sidorna till PNG; ingen
  modell "screenshotar" något.
- **Sidor med äkta textlager** extraheras deterministiskt — ingen modell läser dem.
- **Transkription av skannade sidor** är enda steget där en modell tittar på bilder:
  - Utan `modell=`: du (sessionsmodellen) transkriberar inline — högsta trohet.
  - Med `modell="sonnet"` (rekommenderad arbetshäst för långa böcker) eller
    `modell="haiku"`: delegera transkriptionsjobben till underagenter enligt
    §Delegerad transkription nedan.
  - Haiku-varning: duger för ren löptext i bra skanning, men tabeller, statblocks
    och blek text ger fler fel — plausibla fellästa ord som inte finns i lexikonet
    passerar valideringen. Kör ALLTID `/korrekturläs` efter Haiku-transkription.
- **Illustrationer hoppas över helt.** Modellen ska bara använda sidbilden för att
  läsa bokens typografiska text; den ska aldrig beskriva, sammanfatta eller
  katalogisera bildmotiv.
- **Korrektur-agenterna** har explicita modeller i sin frontmatter
  (specialister: Sonnet; advokaten: Opus — den bärande sista bedömningen) —
  sätt aldrig `model:` i Task-anropen.

## Arbetsflöde

### Steg 1: Analysera och identifiera system

```bash
python3 -m pipeline analysera "<pdf>"            # autodetektering av system
python3 -m pipeline analysera "<pdf>" --system dod   # eller manuellt val
```

Kommandot skriver ut arbetskatalogen (`arbete/<slug>` — kallas `WD` nedan) och
klassificerar varje sida (digital_text / ocr_layer / image_only / image_with_stub_text).
Om systemdetekteringen misslyckas: fråga användaren med AskUserQuestion
(`python3 -m pipeline system` listar tillgängliga).

### Steg 2: Rendera och extrahera textlager

```bash
python3 -m pipeline rendera "<pdf>" --workdir "WD" [--sidor 10-25]
python3 -m pipeline extrahera-text "<pdf>" --workdir "WD"
```

Bägge är idempotenta — avbrutna körningar återupptas med samma kommando.

### Steg 3: Transkribera (du är vision-modellen)

```bash
python3 -m pipeline jobb --workdir "WD" --max 10
```

Ger en JSON-lista med sidor som väntar. För varje jobb:

1. Läs PNG:n med Read (läs gärna upp till 10 st parallellt).
2. Om `embedded_hint` finns: läs den som *ledtråd* — PNG:n är alltid sanningen.
3. Skriv transkriptet till `output`-sökvägen enligt kontraktet nedan.

Bokför sedan och upprepa tills `jobb` returnerar `[]`:

```bash
python3 -m pipeline bokfor --workdir "WD"
```

Avvisade transkript (schemafel) rapporteras och sidan dyker upp i `jobb` igen.

**Läsdisciplin (obligatorisk):**
- Gissa aldrig — skriv `[?]` efter osäkra ord och lista dem i `uncertain`.
- Modernisera inte språket; bevara originalets ton, stavning och styckeindelning.
- Tvåkolumnssidor: vänster kolumn i sin helhet före höger.
- Sidhuvud, sidfot, sidnummer och vattenstämplar transkriberas som `page_artifact`.
- Sätt `confidence` ärligt per element (1.0 = kristallklart).

**Bildpolicy (obligatorisk och tokenbesparande):**
- Hoppa över alla illustrationer, fotografier, kartbilder, dekorativa vinjetter,
  bakgrundsbilder och andra bildmotiv. Skapa aldrig element av typen
  `illustration`.
- Beskriv eller sammanfatta inte vad en bild föreställer. Ange inte motiv, stil,
  personer, föremål, miljö, färg eller komposition.
- Transkribera inte text som är en del av själva bildmotivet, till exempel text
  på skyltar, föremål, vapensköldar, dekorativa inskriptioner eller etiketter
  inne i en karta. En typografiskt separat bildtext eller vanlig brödtext bredvid
  eller ovanpå en illustration är däremot boktext och ska transkriberas.
- Gör ingen detaljerad bildanalys för att leta efter dold eller svårläst text.
  Identifiera bara sidans vanliga boktext och transkribera den.
- Om sidan enbart består av en illustration och saknar vanlig boktext, skriv:
  `{"page": N, "layout": {"columns": 0}, "elements": [],
  "skipped": {"reason": "illustration_only"}}`.
- Sidklassen `image_only` betyder bara att PDF-sidan saknar textlager. Den kan
  fortfarande vara en skannad textsida och får därför inte hoppas över utan en
  snabb kontroll av PNG:n.

#### Delegerad transkription (endast med `modell=`)

Starta **max 3 underagenter parallellt** (`run_in_background: true`), en per sida —
fler går inte fortare, de bränner bara tokens. Ingen nästling: underagenten får
inte själv starta agenter.

```
Task(subagent_type="general-purpose", model="<sonnet|haiku>", run_in_background=true, prompt="
  Transkribera sida NNN ur en inskannad svensk rollspelsbok (system: <system>).
  PNG (sanningskällan): <png-sökväg>   — läs med Read.
  Ledtråd (kan vara trasig): <embedded-sökväg om den finns>
  Skriv EXAKT en JSON-fil till: <output-sökväg>
  KONTRAKT: <klistra in hela §Transkriptionskontrakt + Läsdisciplin ur denna skill>
")
```

Poll med Glob tills output-filerna finns, kör `bokfor`, upprepa tills `jobb` är tom.
Avvisade transkript (schemafel): kör om sidan — efter två misslyckanden med samma
sida tar du över den själv inline. Sidor som validera flaggar `needs_review`
verifieras alltid av djävulens advokat (Opus) i korrektursteget.

### Steg 4: Validera

```bash
python3 -m pipeline validera --workdir "WD"
```

Systemadaptern rättar entydiga OCR-fel (tärningsnotation, termer, attributnamn)
med spårbara korrektionsposter och flaggar allt osäkert för granskning.

### Steg 5: Korrektur med agent-team (för skannade sidor)

```bash
python3 -m pipeline jobb --workdir "WD" --typ korrektur
```

Varje jobb anger vilka agenter som behövs (triage är redan gjord). Följ
`.claude/skills/_shared/proofreading-workflow.md`. Agenterna skriver till
`review_dir`; djävulens advokat skriver `page_NNN.final.json`.

### Steg 6: Sammanfoga, rapportera, exportera

```bash
python3 -m pipeline sammanfoga --workdir "WD"
python3 -m pipeline rapport   --workdir "WD"
python3 -m pipeline exportera --workdir "WD" --format alla   # md,csv,docx
```

### Steg 7: Rapportera till användaren

Sammanfatta: system + confidence, sidklasser, antal transkriberade/validerade sidor,
antal applicerade korrektioner, antal granskningsposter (`export/granskningsrapport.md`),
och var exporterna ligger. Radera INTE arbetskatalogen — den är pipelinens state.

## Transkriptionskontrakt

En fil per sida: `{"page": <nr>, "layout": {"columns": <n>}, "elements": [...]}`.
En ren illustrationssida får ha tom `elements` endast tillsammans med
`"skipped": {"reason": "illustration_only"}`.

Elementtyper: `heading` (med `level` 1–3), `paragraph` (ev. `"style": "italic"`),
`boxed_text`, `list` (`data.items`), `table` (`data.headers` + `data.rows`),
`statblock`, `toc_entry`, `index_entry`, `page_artifact`. Typen `illustration`
är äldre bakåtkompatibilitet och får inte skapas i nya transkript.

Varje element: `text` (utom table/statblock/list), `confidence` (0–1), gärna
`source.region` (t.ex. "vänsterkolumn"). Osäkra ord markeras `[?]` i texten och
listas i `uncertain`.

Statblock:

```json
{"type": "statblock",
 "data": {"name": "<namn>",
          "stats": {"STY": 10, "STO": 22},
          "skills": {"<färdighet>": <värde>},
          "weapons": [{"name": "Bett", "attack": "65%", "damage": "1T6+2"}],
          "other": {"Hemvist": "..."}},
 "confidence": 0.9}
```

Attributnamnen per system: kör `python3 -m pipeline system` och läs
`system/<id>/system.json`. Transkribera värden EXAKT som de står — även om de ser
fel ut; valideringen rättar spårbart.
