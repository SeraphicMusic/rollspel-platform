# Rollspel-platform — Svensk TTRPG-verktygslåda

Verktyg för att extrahera, bearbeta, korrekturläsa och skapa innehåll för svenska bordsrollspel (Drakar och Demoner, Mutant m.fl.).

## Extraktionspipeline (kärnan)

Deterministisk Python-pipeline i `pipeline/` — kör `python3 -m pipeline --help`.
Allt state per bok ligger i `arbete/<slug>/` (manifest + per-sida-filer + export).
Kommandon: `analysera`, `rendera`, `extrahera-text`, `identifiera-system`, `jobb`,
`bokfor`, `validera`, `sammanfoga`, `rapport`, `exportera`, `status`, `system`.

Principer (bindande):

- Alla steg är idempotenta — färdiga sidor körs aldrig om; avbrott återupptas med samma kommando.
- Inga tysta korrigeringar — varje rättning är en korrektionspost (original, förslag, confidence, orsak, källa, applied).
- Osäkert innehåll flaggas (`needs_review`) och hamnar i granskningsrapporten i stället för att gissas.
- Radera aldrig `arbete/`-kataloger — de är pipelinens state.

Dokumentation: [README.md](README.md), design i [docs/](docs/).
Tester: `python3 -m unittest discover -s tests -t .`

## Stödda system (extraktion)

| System | Adapter-id | Alias |
| --- | --- | --- |
| Drakar och Demoner (1991/1984) | `dod` | drakar |
| Mutant 2089 | `mutant2089` | mutant |

Adaptrar ligger i `system/<id>/` (ren data: system.json, lexicon.json, dice.json,
statblock.schema.json, detection.json). Nya system: kopiera `system/_template/`.
Regenerera från referensrepon: `python3 scripts/bygg_adapter.py <id> --ref <sökväg>`.

OBS: `.claude/systems/` (används av de kreativa skillsen nedan) beskriver för
`mutant` fortfarande Mutant: År Noll — inte samma spel som `mutant2089`.

## Skills

| Skill | Purpose |
| --- | --- |
| `extrahera` | Driver pipelinen + agerar vision-transkriberare för skannade sidor |
| `korrekturlas` | Agentbaserad korrektur mot pipelinens state (korrektionsposter) |
| `extrahera-konst` | Illustration extraction and reimagining in Swedish illustrator styles |
| `aventyr` | Interactive adventure construction with NPC:er, encounters and statblocks |
| `konvertera` | System conversion (e.g. DoD → Mutant) of material, NPCs and adventures |
| `karaktarsskapare` | Character creation with attributes, skills, equipment and backstory |

Korrektur-agenter (`.claude/agents/`): sprakgranskare, layoutverifierare,
djavulens-advokat. Kontrakt: alla ändringar uttrycks som korrektionsposter med
`applied: false`; endast advokaten applicerar, efter verifiering mot PNG:n
(sanningskällan). Advokaten äger även domänkontrollen (statblocks/terminologi)
och forensiken (svårlästa `[?]`-partier, omrendering i hög DPI).

**[AGENTER.md](AGENTER.md) — läs den och följ den SLAVISKT** varje gång du kör
eller delegerar till agenter (transkription, korrektur, allt via `Task`/`Agent`).
Den är inte en sammanfattning att skumma — modell-tiering, max 3 parallella
agenter, ingen nästling, snäva per-sida-uppdrag och läsdisciplin är bindande
regler, inte förslag. Detta repo bränner tokens fort (dussintals sidor × flera
agenter per sida) och en lös tolkning av reglerna är precis det som äter kvoten.

## Dependencies

- Python 3.9+ med PyMuPDF (`python3 -m pip install --user pymupdf`)
- Node.js (DOCX-export via `.claude/skills/extrahera/create-docx.js`; `npm install` i den katalogen)
- Gemini API key (`GEMINI_API_KEY`) — endast för `extrahera-konst`

## Output

- Namngivning av arkiverade PDF:er, arbete-mappar och skapat/konverterat material:
  [NAMNSTANDARD.md](NAMNSTANDARD.md) (`SYSTEM-TYP-titel`, t.ex. `DOD-AVE-den-vita-duvan`)
- `arbete/<slug>/export/`: `bok.json` (kanoniskt, med proveniens/confidence/korrektioner),
  `bok.md`, `bok.docx`, `tabeller/*.csv`, `granskningsrapport.md`
- `bibliotek/`: namnstandardade läskopior av färdiga `bok.md` — det man matar
  till andra agenter/verktyg
- Illustrations: Reimagined in styles of Ackegard, Bergting, Egerkrans
- Adventures: Structured JSON + DOCX
- Characters: JSON character sheets + DOCX
