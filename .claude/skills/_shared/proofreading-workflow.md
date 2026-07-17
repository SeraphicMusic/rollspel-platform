# Delad korrekturläsnings-workflow

Kanonisk workflow för agentbaserad korrektur. Refereras av `/extrahera` och `/korrekturläs`.
Pipelinen äger state och triage — agenterna arbetar mot dess filer.

## 1. Hämta jobb

```bash
python3 -m pipeline jobb --workdir "WD" --typ korrektur
```

Varje jobb innehåller: `page`, `validated` (input), `png` (sanningskällan),
`review_dir` (agenternas output-katalog), `output` (`page_NNN.final.json`) och
`agents` (triage-resultatet — vilka specialister sidan behöver).

## 2. Fas 1 — Specialistagenter parallellt

Starta de agenter jobbet listar (utom `djavulens-advokat`) med `run_in_background: true`,
**max 3 samtidigt** (fler parallella agenter bränner tokens utan att gå fortare —
Släktforskaren-lärdom). Alla får samma kontrakt:

```
Task(subagent_type="<agent>", run_in_background=true, prompt="
  Korrekturläs sida NNN. System: <system>.
  Input:  <validated-sökväg>  (element med ev. flaggor i review_reasons)
  PNG:    <png-sökväg>  (sanningskällan — läs vid behov enligt din roll)
  Output: <review_dir>/<agent>.json
  KONTRAKT: Skriv INTE om texten tyst. Din output är input-elementen där varje
  ändring uttrycks som en korrektionspost i elementets 'corrections'-lista:
  {original, corrected, confidence, reason, source: 'agent:<agent>', applied: false}.
  Advokaten avgör vad som appliceras. Element utan ändringar lämnas orörda.
")
```

Poll med Glob tills alla förväntade output-filer finns. Kör om misslyckade agenter.

## 3. Fas 2 — Djävulens advokat

När alla specialister är klara:

```
Task(subagent_type="djavulens-advokat", run_in_background=true, prompt="
  Slutgranska sida NNN. System: <system>.
  PNG (SANNINGSKÄLLAN): <png-sökväg>
  Draft: <validated-sökväg>
  Specialistförslag: <review_dir>/*.json
  Systemkonfig: system/<id>/system.json + system/<id>/lexicon.json
  Output: <final-sökväg>
")
```

Advokaten verifierar varje förslag mot PNG:n, sätter `applied: true/false` per
korrektionspost, applicerar godkända poster på texten och skriver final-filen.
Den äger dessutom **domänkontrollen** (statblocks, tärningsnotation, terminologi
mot systemkonfigen) och **forensiken** (`[?]`-partier, vid behov omrendering av
regionen i hög DPI). Alla poster — även avvisade — behålls i `corrections`
(spårbarhet).

## 4. Efter korrekturen

```bash
python3 -m pipeline sammanfoga --workdir "WD"
python3 -m pipeline rapport   --workdir "WD"
```

## Modell-tiering (Släktforskaren-mönstret)

Billigaste modell som klarar uppgiften — satt EXPLICIT i agenternas frontmatter:

| Agent | Modell | Motiv |
|---|---|---|
| sprakgranskare, layoutverifierare | `sonnet` | Arbetshästar — föreslår bara, applicerar aldrig |
| djavulens-advokat | `opus` | Bärande verifiering mot PNG:n, domänkontroll + forensik — enda som applicerar |

Sätt ingen `model:` i Task-anropet — agentdefinitionerna äger valet.
Agenter får ALDRIG själva starta underagenter (nästling hänger sig).

## Riktlinjer

- **1 sida per agent-uppsättning**; Fas 1 → Fas 2 i strikt ordning.
- **Inga tysta ändringar** — allt som skiljer sig från draften ska ha en korrektionspost.
- Vanliga OCR-fel: ö↔o, å↔a, ä↔a, rn↔m, 0↔O, 1↔l/I, 5↔S, 8↔B, ihopslagna ord.
- Vid osäkerhet: behåll draften och flagga (`needs_review: true` + `review_reasons`).
- Använd `utf-8-sig`-tolerant inläsning; skriv alltid giltig UTF-8-JSON.
