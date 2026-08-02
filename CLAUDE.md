# Rollspel-platform — Svensk TTRPG-verktygslåda

Verktyg för att extrahera, bearbeta, korrekturläsa och skapa innehåll för svenska bordsrollspel (Drakar och Demoner, Mutant m.fl.).

## Extraktionspipeline (kärnan)

Deterministisk Python-pipeline i `pipeline/` — kör `python3 -m pipeline --help`.
Allt state per bok ligger i `arbete/<slug>/` (manifest + per-sida-filer + export).
Kommandon: `analysera`, `rendera`, `extrahera-text`, `radboxar`,
`identifiera-system`, `jobb`, `bokfor`, `validera`, `forbesikta`, `sammanfoga`,
`rapport`, `exportera`, `status`, `system`.

Principer (bindande):

- Alla steg är idempotenta — färdiga sidor körs aldrig om; avbrott återupptas med samma kommando.
- Inga tysta korrigeringar — varje rättning är en korrektionspost (original, förslag, confidence, orsak, källa, kind, applied).
- Valideringens **härledda** lexikonmatchningar är förslag (`applied: false`) — bara handkurerade alias appliceras direkt. En böjningsform som står korrekt i trycket får aldrig "rättas" tyst; advokaten dömer mot PNG:n.
- `forbesikta` hittar de mekaniska felmönstren deterministiskt (linjeregel-prefix/-suffix, raka citattecken, `±0`-garbel, kolumnsammanslagning, vertikal radsammanslagning, läsordning, tabellkandidat) och skriver kandidater till `page_NNN.review/heuristik.json`. Kör det FÖRE korrekturen — agenterna ska verifiera listan, inte leta upp mönstren igen. Läsordningsreglerna körs bara på sidor som klassificerats som tvåspaltig löptext; sidans typ står i `heuristik.json` under `sidtyp`.
- En tryckt tabell MÅSTE typas `table` (eller reservformen `table_header`/`table_cell`) — aldrig som en följd av `paragraph`. Kontraktet står i [.claude/skills/extrahera/SKILL.md](.claude/skills/extrahera/SKILL.md) §Tabeller och är bindande: typas en tabell som löptext är rad- och kolumnstrukturen förlorad för gott, och ingenting nedströms kan återskapa den. `forbesikta`-regeln `tabellkandidat` flaggar misstänkta fall som `needs_review` — fel elementtyp är ett typningsfel, aldrig en korrektionspost.
- Boknivåbeslut samlas i `arbete/<slug>/beslut.md` och delas ut av `jobb`. Bara advokaten skriver dit; alla läser den. Samma fråga ska inte utredas om på varje sida.
- Uppenbara sättningsfel emenderas automatiskt (`kind: "emendering"`); trycket bevaras i postens `original` och rättningen listas i granskningsrapporten. Gränsen är bindande och står i [AGENTER.md](AGENTER.md) Regel 8a — siffror, spelvärden, dialekt och arkaismer rättas aldrig.
- Osäkert innehåll flaggas (`needs_review`) och hamnar i granskningsrapporten i stället för att gissas.
- `source.bbox` mäts fram deterministiskt av `radboxar` (`pipeline/rows.py`) ur sidbilden — de inskannade PDF:erna har inget textlager utöver vattenstämpeln. Kör det för varje skannad bok: utan bbox är fyra av `forbesikta`s åtta regler verkningslösa. Transkriptionen hämtar bbox ur mätningen och **gissar aldrig koordinater**; saknas en rad utelämnas bbox.
- Radera aldrig `arbete/`-kataloger — de är pipelinens state.
- `forbesikta` hoppar över färdiga sidor; screena en avslutad bok med
  `--sidor 1-N --force`. Reglerna kommer till efter hand, så en bok som
  extraherades innan en regel fanns har aldrig prövats mot den (del I: 66
  kandidater, varav 16 tryckta tabeller som lösa `paragraph`). Se AGENTER.md
  Regel 7a.
- Saknar de flesta av en sidas element bbox är det ett MÄTFEL, inte ett
  transkriptionsfel: läsexporten fogar då inte ihop några stycken och sidan
  faller ut som en rad per tryckt rad. `rapport` listar sådana sidor under
  *Sidor utan användbar geometri*. Se AGENTER.md Regel 9.

Efterarbete på en färdig bok (kör skriptet FÖRE agenten, AGENTER.md Regel 5):

- `python3 scripts/tabellkandidat.py <slug> [--verkstall]` — monterar de
  tabellkandidater vars rutnät är en fullständig rektangel. Ragged block rörs
  aldrig; tabellernas gränser (feta rubrikrader, flera tabeller i ett block)
  avgörs av advokaten mot PNG:n.
- `python3 scripts/rubriknivaer.py <slug> --toc <sida> [--verkstall]` — härleder
  kapitel 1 / sektion 2 / underrubrik 3 ur bokens egen innehållsförteckning
  genom att mäta dess indrag i sidbilden. Idempotent via `level_source`.
- `python3 scripts/remappa_bbox.py <arbete/slug> [--verkstall]` — kopplar om
  boxar från en föråldrad mätning till den lagade. Fragmentet ligger inuti den
  riktiga raden, så den nya mätningens rad hittas på att den täcker fragmentets
  mittpunkt. Täcker ingen rad den tas boxen BORT — en saknad box är en lucka i
  en heuristik, en påhittad är ett fel som ser ut som data.
- `python3 scripts/materialisera_kind.py <arbete/slug> [--verkstall]` — skriver
  ut `kind` på poster från tiden före fältet, med samma regel rapporten redan
  tillämpar vid läsning.
- `python3 scripts/materialisera_verdict.py <arbete/slug> [--verkstall]` —
  fältsätter `verdict: avvisad` där domen står i prosa (`AVVISAD`, `DUBBLETT`)
  men inte i fältet. Förslag utan nedskriven dom rörs aldrig.
- `python3 scripts/tomma_artefakter.py <arbete/slug> [--verkstall]` — höjer
  confidence på `page_artifact` som advokaten har tömt; de låg kvar på 0,30 och
  återkom som falska lågkonfidensposter i varje screening.

Alla fyra är idempotenta — en andra körning rör noll poster.

**Avgjorda granskningsflaggor.** `review_reasons` är öppna frågor. Är en flagga
avgjord flyttas den med `pipeline.corrections.close_review_reason()` till
`resolved_reasons` tillsammans med sin lösning och vem som fällde den, och
slutar hålla elementet öppet. Radera aldrig beläggstexten — den är det som gör
kontrollen spårbar. Rapporten räknar de avgjorda separat.

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
- Gemini API key (`GEMINI_API_KEY`) — endast för `extrahera-konst`

## Output

- Namngivning av arkiverade PDF:er, arbete-mappar och skapat/konverterat material:
  [NAMNSTANDARD.md](NAMNSTANDARD.md) (`SYSTEM-TYP-titel`, t.ex. `DOD-AVE-den-vita-duvan`)
- `arbete/<slug>/export/`: `bok.json` (kanoniskt, med proveniens/confidence/korrektioner),
  `bok.md`, `tabeller/*.csv`, `granskningsrapport.md`
- Markdown är läsformatet. DOCX-exporten är avvecklad (2026-07-29) — den ingår
  inte i `alla` och saknar statblockens vapentabeller.
- `bibliotek/`: namnstandardade läskopior av färdiga `bok.md` — det man matar
  till andra agenter/verktyg
- Illustrations: Reimagined in styles of Ackegard, Bergting, Egerkrans
- Adventures: Structured JSON + DOCX
- Characters: JSON character sheets + DOCX
