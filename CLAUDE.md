# Rollspel-platform — Svensk TTRPG-verktygslåda

Verktyg för att extrahera, bearbeta, korrekturläsa och skapa innehåll för svenska bordsrollspel (Drakar och Demoner, Mutant m.fl.).

## Extraktionspipeline (kärnan)

Deterministisk Python-pipeline i `pipeline/` — kör `python3 -m pipeline --help`.
Allt state per bok ligger i `arbete/<slug>/` (manifest + per-sida-filer + export).
Kommandon: `analysera`, `rendera`, `extrahera-text`, `radboxar`,
`identifiera-system`, `jobb`, `bokfor`, `validera`, `forbesikta`, `sammanfoga`,
`frys`, `diffa`, `rapport`, `exportera`, `arkivera`, `status`, `system`.

Principer (bindande):

- Alla steg är idempotenta — färdiga sidor körs aldrig om; avbrott återupptas med samma kommando.
- Inga tysta korrigeringar — varje rättning är en korrektionspost (original, förslag, confidence, orsak, källa, kind, applied).
- Valideringens **härledda** lexikonmatchningar är förslag (`applied: false`) — bara handkurerade alias appliceras direkt. En böjningsform som står korrekt i trycket får aldrig "rättas" tyst; advokaten dömer mot PNG:n.
- `forbesikta` hittar de mekaniska felmönstren deterministiskt (linjeregel-prefix/-suffix, raka citattecken, `±0`-garbel, `±N`-värde, punktledare, kolumnkollaps, kolumnsammanslagning, vertikal radsammanslagning, läsordning, tabellkandidat, bbox-felkoppling) och skriver kandidater till `page_NNN.review/heuristik.json`. Kör det FÖRE korrekturen — agenterna ska verifiera listan, inte leta upp mönstren igen. Läsordningsreglerna körs bara på sidor som klassificerats som tvåspaltig löptext; sidans typ står i `heuristik.json` under `sidtyp`.
- En tryckt tabell MÅSTE typas `table` (eller reservformen `table_header`/`table_cell`) — aldrig som en följd av `paragraph`. Kontraktet står i [.claude/skills/extrahera/SKILL.md](.claude/skills/extrahera/SKILL.md) §Tabeller och är bindande: typas en tabell som löptext är rad- och kolumnstrukturen förlorad för gott, och ingenting nedströms kan återskapa den. `forbesikta`-regeln `tabellkandidat` flaggar misstänkta fall som `needs_review` — fel elementtyp är ett typningsfel, aldrig en korrektionspost.
- Boknivåbeslut samlas i `arbete/<slug>/beslut.md` och delas ut av `jobb`. Bara advokaten skriver dit; alla läser den. Samma fråga ska inte utredas om på varje sida.
- Uppenbara sättningsfel emenderas automatiskt (`kind: "emendering"`); trycket bevaras i postens `original` och rättningen listas i granskningsrapporten. Gränsen är bindande och står i [AGENTER.md](AGENTER.md) Regel 8a — siffror, spelvärden, dialekt och arkaismer rättas aldrig.
- Osäkert innehåll flaggas (`needs_review`) och hamnar i granskningsrapporten i stället för att gissas.
- `source.bbox` mäts fram deterministiskt av `radboxar` (`pipeline/rows.py`) ur sidbilden — de inskannade PDF:erna har inget textlager utöver vattenstämpeln. Kör det för varje skannad bok: utan bbox är fyra av `forbesikta`s elva regler verkningslösa. Transkriptionen hämtar bbox ur mätningen och **gissar aldrig koordinater**; saknas en rad utelämnas bbox.
- Radera aldrig `arbete/`-kataloger — de är pipelinens state.
- `forbesikta` hoppar över färdiga sidor; screena en avslutad bok med
  `--sidor 1-N --force`. Reglerna kommer till efter hand, så en bok som
  extraherades innan en regel fanns har aldrig prövats mot den (del I: 66
  kandidater, varav 16 tryckta tabeller som lösa `paragraph`). Se AGENTER.md
  Regel 7a.
- **Typdrift är boknivå och syns aldrig på en enskild sida.** En lång
  transkription tappar sina egna typkonventioner mitt i boken: i del I upphörde
  `heading` efter s. 38, `boxed_text` efter s. 32, punktlistorna efter s. 37,
  och sidhuvudena bytte från `page_artifact` till `paragraph` vid s. 40 — varje
  sida för sig fullt rimlig. `forbesikta` larmar nu på två signaler: en typ som
  användes stadigt och sedan upphör, och ett återkommande sidhuvud som byter
  typ. Sektionens första sida bär ofta titeln med sidhuvudets lydelse men i
  egen grad; den skillnaden mäts, den gissas inte.
- **Frys läsexporten före varje strukturingrepp.** `python3 -m pipeline frys`
  och sedan `diffa` jämför ordfrekvenser — formen får ändras, orden aldrig
  oförklarat. Det var så de sju tabellrader upptäcktes som föll ur `bok.md`
  utan att något varnade.
- **En uppskjuten boknivåfråga måste i kön.** `beslut.md` under `## Öppen kö`,
  som `- [ ] BQ-NNN <frågan>`. `rapport` och `status` redovisar inte boken som
  avslutad medan kön har poster.
- **Kön är för frågor som BARA en människa kan svara på — mät först, fråga
  sedan.** Går frågan att avgöra med en beskärning ur skanningen är den inget
  köärende: den är ett mätjobb, och det ska göras innan posten skrivs. I del II
  hamnade tre "misstänkta OCR-fel" (`tämt tillstånd`, `kalla klima`, `Mycket
  sällsynta`) i kön, användaren läste av dem i boken och beslutade — varefter
  forensiken visade att alla tre var print-trogna och två av besluten stred mot
  Regel 8a. Frågorna kostade en avläsning som ingen behövde göra, och svaren
  gick inte att följa. Rätt sorts köärende är det motsatta: ett värde som bara
  står i den tryckta boken och som ingen bild eller intern evidens kan avgöra.
- **Gissa aldrig i frågans formulering.** Samma post löd "sannolikt tryckt
  `tamt`" — gissningen var fel och styrde svaret. En köpost ska säga vad som
  är oläst, inte vad man tror att det står.
- Saknar de flesta av en sidas element bbox är det ett MÄTFEL, inte ett
  transkriptionsfel: läsexporten fogar då inte ihop några stycken och sidan
  faller ut som en rad per tryckt rad. `rapport` listar sådana sidor under
  *Sidor utan användbar geometri*. Se AGENTER.md Regel 9.
- **Reglerna måste titta IN i tabellcellerna.** De äldre `forbesikta`-reglerna
  läste bara `el["text"]`, och därför överlevde `Dvärg PSY ±2` i del I:s
  rastabell tre agentvarv med confidence 1,0 — felet satt i `data.rows` och
  ingen regel såg dit. Det hittades först när boken diffades mot en oberoende
  rippning. `plusminus-varde`, `punktledare` och `kolumnkollaps` läser både
  texten och cellerna. (Cellen visade sig vid forensik vara print-trogen: `±2`
  står så i trycket. Regeln har ändå rätt att larma — `±N` finns inte i bokens
  notation, och domen hör hemma i `beslut.md`, inte i elementet.)
- **En gles tabell monteras ur geometrin, inte ur läsordningen.**
  `tables.assemble` fyllde tidigare celler sekventiellt, vilket bara fungerar
  på ett fullt rektangulärt rutnät. Del I:s tabell över grundegenskapskrav har
  7 attributkolumner där varje yrke fyller två–tre; 33 celler gick aldrig jämnt
  upp på 9 rubriker, tabellen skippades och bok.md skrev en rad per cell med
  kolumntillhörigheten borta. Assemblern läser nu kolumnen ur cellens uppmätta
  x-läge mot kolumnrubrikerna och raden ur y-läget, och faller tillbaka på
  läsordningen bara när bbox saknas. Varje tvetydighet (två celler i samma
  ruta, en cell utanför axeln) ger fallback och en anteckning — aldrig en
  gissning. En tom ruta flaggas alltid: geometrin kan inte skilja "tom i
  trycket" från "cell som transkriptionen tappade".
- **En export bär stämpeln av den kod som byggde den.** `bok.json` har
  `byggd_med` (git-revision + `SCHEMA_VERSION` + om arbetsträdet var smutsigt),
  och `bok.md`/`tabeller/` har sin i `export/proveniens.json` — inte i bok.md
  själv, som är ordkonserveringens facit och skulle få ett nytt "nytt ord" vid
  varje commit. `status` och `rapport` VARNAR (aldrig spärr) när stämpeln inte
  är HEAD. Utan den var felklassen tyst: `bibliotek/…del2` bar `ENER- GISTRÅLE`
  och `SMIslaget.` — brytfel som redan var lagade i `pipeline/export.py`, i en
  export som ingen kört om.
- **Ett verktyg verifieras mot den ARKIVERADE PDF:en, aldrig mot `arbete/`.**
  Bygg en kastbar arbetskatalog (`analysera` + `radboxar --workdir <scratch>`)
  och mät där: samma skanning, samma sidor, inga domar att förstöra. Det var
  den insikten som löste upp BQ-002/013/021, som stått öppna på antagandet att
  ett facit krävde en omkörning av `radboxar` över hela boken — och därmed
  riskerade 103 handmätta boxar.
- **Mätmotorn har ett ANDRA SVEP.** En kort, gles slutrad (`de ting.`, `sen:`,
  `sm.`) toppar på ungefär halva grannradernas svärta och faller på den lokala
  tröskeln; dalen mellan två normala rader ligger på samma nivå, så tröskeln
  kan inte sänkas. Svepet tittar bara i luckor som RYMMER en rad och mäter dem
  mot luckans egen profil. Banden märks `svep: 2`. Ramens lodräta linjer
  sållas bort ur bandets x-mätning (`_rule_mask`) — annars mäts varje band från
  ramen och styckeindragen försvinner.
- **Käll-PDF:en är den sista sanningskällan — arkivera den, radera den aldrig.**
  Sidbilderna i `arbete/` är omrenderade och lägre upplösta än PDF:ens
  inbäddade skanning (del I: 1339×1941 mot 1928×2795, 44 % mer). Går PDF:en
  förlorad kan ingen dom omprövas. Städningen import/ → `arkiv/` var länge bara
  en punkt i en README, alltså en instruktion till en agent: ingenting körde
  den och ingenting märkte att den uteblev. Numera är den `python3 -m pipeline
  arkivera`, som vägrar så länge boken har en sida under `validated`, ett
  sidfel, en saknad export eller en öppen BQ-post — och `status` säger
  **EJ ARKIVERAD** så länge PDF:en står kvar i `import/`.
- **En oberoende rippning av samma bok är ett boknivåinstrument.** Diffa mot
  den när det finns en. Den hittar det som per-sida-korrekturen strukturellt
  inte kan se. Men dess avvikelser är INDICIER på var man ska titta, aldrig
  facit — jämförelsebokens egna fel är minst lika många, och varje påstående
  avgörs mot PNG:n.

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
- `python3 scripts/punktrader.py <arbete/slug> [--verkstall]` — typar om rader
  som börjar med punkttecken från `paragraph` till `list_item`. Låg de som
  löptext fogade omflödningen in dem i föregående stycke och listan försvann
  som struktur.
- `python3 scripts/binda_rader.py <arbete/slug> [--sidor N,M] [--verkstall]` —
  binder element till uppmätta rader på sidor som mätts om. Kör det efter
  varje `radboxar --force`: mätningen ger rätt band, men elementen pekar inte
  på dem, och utan `source.rader` räknar pipelinen aldrig fram någon bbox.
  Bindningen är ingen gissning utan en mätning — elementets teckenlängd mot
  radens uppmätta bredd (±12,5 % för 90 % av bokens facitrader), illustrations-
  band utpekade på svärtan (text 0,26–0,43, bildpanel 0,53–0,95), och ett
  avstavat ord som tvingar nästa element till raden omedelbart efter. Varje
  körning måste bli mätbart dyrare av att skjutas ett steg, annars lämnas den
  obunden: 62 % av alla avvikelser mot facit var hela block ett steg ur led.
  **Kör `--utvardera` först** — den prövar verktyget mot bokens redan bundna
  sidor. Ett verktyg som inte kan återskapa en känd bindning får inte skriva en
  okänd. Utvärderingen räknar inte bara avvikelser utan **dömer** dem mot
  trycket, för facit är en tidigare transkription med egna fel; se AGENTER.md
  Regel 9a.
- `python3 scripts/laga_radbas.py <arbete/slug> [--verkstall]` — lagar
  transkript vars `source.rader` skrevs 1-baserat. `pipeline/jobs.py` slår upp
  radindexen 0-baserat och räknar själv fram `bbox`, så en 1-baserad sida
  bokförs som GODKÄND med varje box förskjuten en rad — inget varnar, och felet
  syns först som obegriplig geometri nedströms. Offsetten mäts, den gissas
  inte: transkriptet bär `region` per element och mätningen `region` per rad,
  och den offset som får dem att gå ihop är den rätta. Skriptet rör bara sidor
  där 1-baserat går ihop utan fel och 0-baserat ger minst ett. Kör det efter
  varje transkriptionsvåg, före `bokfor`.

Alla är idempotenta — en andra körning rör noll poster.

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
