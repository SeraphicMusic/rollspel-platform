# Delad korrekturläsnings-workflow

Kanonisk workflow för agentbaserad korrektur. Refereras av `/extrahera` och `/korrekturläs`.
Pipelinen äger state och triage — agenterna arbetar mot dess filer.

## 1. Förbesiktning (deterministisk, ingen LLM)

```bash
python3 -m pipeline forbesikta --workdir "WD" [--sidor 40-44]
```

Skriver `page_NNN.review/heuristik.json` per väntande sida med kandidater
(`applied: false`, `source: "heuristik:<regel>"`) för mönster som är rent
mekaniska: `linjeregel-prefix`/`-suffix` (`- LYSSNA` där strecket är sidgrafik),
`raka-citattecken`, `plusminus` (`t0`/`I0`/`*0` → `±0`), `kolumnsammanslagning`
(bbox-bredd mot spaltmedianen) och `lasordning` (arrayordning mot bbox-y).

Två regler ger `needs_review`-flaggor i stället för korrektionsposter, eftersom
de gäller struktur och inte text:

- `radsammanslagning` — bbox-HÖJDEN är ~2× medianradhöjden medan glyfbredden är
  normal: elementet spänner över två tryckrader och återger bara den ena, så en
  hel rad saknas i draften.
- `tabellkandidat` — korta `paragraph`-element bildar ett rutnät som borde ha
  typats `table`. **Det är ett typningsfel, inte ett textfel** — rätta
  elementtypen, skriv aldrig en korrektionspost för det.

Filen har också `sidtyp` (löptext / tabellsida / blankett / annat). Läsordnings-
reglerna körs bara på löptext: på tabellsidor läses raderna tvärs över
spalterna och på blanketter fältgrupp för fältgrupp, så där larmade de falskt.
Skapar också `beslut.md` i arbetskatalogen om den saknas.

Agenterna ska **verifiera** kandidatlistan, inte leta upp mönstren igen — det är
skillnaden mellan en sida på 200k tokens och en på 350k.

## 2. Hämta jobb

```bash
python3 -m pipeline jobb --workdir "WD" --typ korrektur
```

Varje jobb innehåller: `page`, `validated` (input), `png` (sanningskällan),
`review_dir` (agenternas output-katalog), `output` (`page_NNN.final.json`),
`agents` (triage-resultatet), `beslut` (boknivåprecedens för hela boken) och
`heuristik` (förbesiktningens kandidater, när den körts).

## 3. Kör agenterna SYNKRONT, en i taget

**Detta är bindande och överstyr varje äldre instruktion om bakgrundskörning.**
Bakgrundsagenter dödas av 600s-watchdogen mitt i bildforensiken och hinner inte
skriva sin outputfil — arbetet går förlorat. Flera synkrona agenter i samma
meddelande ger "Connection closed mid-response".

Per sida, i strikt ordning: `sprakgranskare` → `layoutverifierare` (om jobbet
listar den) → `djavulens-advokat`. Varje anrop med `run_in_background: false`,
**ett anrop per meddelande**. Sätt ingen `model:` i anropet — agentdefinitionens
frontmatter äger modellvalet (se Regel 1).

**Verifiera review-katalogen med `ls` mellan stegen.** En agent kan rapportera
"output skriven" utan att filen finns. Dör en agent på serverfel (529 Overloaded
inträffar) — kör om samma uppdrag; övriga filer ligger kvar, så omkörningen
kostar bara den agenten.

### Fas 1 — specialisterna

```
Task(subagent_type="<agent>", run_in_background=false, prompt="
  Korrekturläs sida NNN. System: <system>.
  Input:      <validated-sökväg>  (element med ev. flaggor i review_reasons)
  PNG:        <png-sökväg>  (SANNINGSKÄLLAN — läs den, gissa aldrig på mönster)
  Beslut:     <beslut-sökväg>  (boknivåprecedens — läs först, utred inte om)
  Heuristik:  <review_dir>/heuristik.json  (kandidater att verifiera)
  Output:     <review_dir>/<agent>.json
  KONTRAKT: Skriv INTE om texten tyst. Din output är input-elementen där varje
  ändring uttrycks som en korrektionspost i elementets 'corrections'-lista:
  {original, corrected, confidence, reason, kind, source: 'agent:<agent>',
   applied: false}. Advokaten avgör vad som appliceras. Element utan ändringar
  lämnas orörda.
")
```

### Fas 2 — djävulens advokat

```
Task(subagent_type="djavulens-advokat", run_in_background=false, prompt="
  Slutgranska sida NNN. System: <system>.
  PNG (SANNINGSKÄLLAN): <png-sökväg>
  Draft: <validated-sökväg>
  Specialistförslag: <review_dir>/*.json
  Beslut: <beslut-sökväg>   (följ det avgjorda; skriv in nya boknivåbeslut här)
  Systemkonfig: system/<id>/system.json + system/<id>/lexicon.json
  Källa-PDF (forensik): <pdf-sökväg>, sida NNN
  Output: <final-sökväg>
  Skriv output-filen när de textuella posterna är dömda, gör forensiken därefter.
")
```

Advokaten verifierar varje förslag mot PNG:n, sätter `applied` och `kind` per
korrektionspost, applicerar godkända poster och skriver final-filen. Den äger
dessutom **domänkontrollen** (statblocks, tärningsnotation, terminologi mot
systemkonfigen) och **forensiken** (`[?]`-partier, beskärning ur PDF:ens
inbäddade skanning). Alla poster — även avvisade — behålls i `corrections`.

Efter varje sida: kontrollera att `final.json` finns, att posterna har `kind`
och att inga `[?]` kvarstår oavsiktligt.

## 4. Efter korrekturen

```bash
python3 -m pipeline sammanfoga --workdir "WD"
python3 -m pipeline rapport   --workdir "WD"
```

## Modell-tiering (Släktforskaren-mönstret)

Billigaste modell som klarar uppgiften — satt EXPLICIT i agenternas frontmatter,
under nyckeln `tools:`/`model:` (`allowed-tools:` hedras INTE för subagenter):

| Agent | Modell | Motiv |
|---|---|---|
| sprakgranskare, layoutverifierare | `sonnet` | Arbetshästar — föreslår bara, applicerar aldrig |
| djavulens-advokat | `opus` | Bärande verifiering mot PNG:n, domänkontroll + forensik — enda som applicerar |

Sätt ingen `model:` i Task-anropet — agentdefinitionerna äger valet.
Agenter får ALDRIG själva starta underagenter (nästling hänger sig).

## Riktlinjer

- **1 sida per agent-uppsättning**; Fas 1 → Fas 2 i strikt ordning.
- **Håll specialisternas domäner isär.** Sprakgranskaren äger text (stavning,
  diakriter, `[?]`-markeringar, linjeregeländar); layoutverifieraren äger
  geometri (läsordning, kolumnsammanslagning, saknade celler, typning). När
  layoutverifieraren också föreslår `[?]`-borttagningar blir det rena
  dubbletter som advokaten måste läsa och avvisa — 38 av 72 avvisade poster på
  DoD-sidorna 45–52 var just det. Skriv domängränsen i prompten.
- Sidor med `skipped.reason = "illustration_only"` ska inte ge korrekturjobb.
  På övriga sidor ignoreras illustrationer och text inuti själva bildmotivet —
  inklusive illustratörssignaturer (`MATOSE`, `MJADZOSICH © '91`).
- Digitala utgåvors vattenstämplar under sidfoten är inte boktext och läggs
  aldrig till. Layoutverifieraren föreslår dem gärna en gång per sida.
- **Inga tysta ändringar** — allt som skiljer sig från draften ska ha en
  korrektionspost med `kind`.
- Vanliga OCR-fel: ö↔o, å↔a, ä↔a, rn↔m, 0↔O, 1↔l/I, 5↔S, 8↔B, ihopslagna ord,
  `ll` som egentligen är `11`, `±0` som `t0`/`I0`/`*0`/`+0`.
- Trycket har genomgående `’…’` och `”…”` — även runt siffror (`slå ’6’ eller
  lägre`). Stryk aldrig en apostrof framför en siffra utan att kontrollera om det
  är ett citattecken vars par tappats.
- Vid osäkerhet: behåll draften och flagga (`needs_review: true` +
  `review_reasons`).
- Använd `utf-8-sig`-tolerant inläsning; skriv alltid giltig UTF-8-JSON.
