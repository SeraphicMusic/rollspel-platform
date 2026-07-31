# Fas 1 — Analys: nuläge och referensrepon

*Datum: 2026-07-16. Underlag för målarkitekturen i [ARKITEKTUR.md](ARKITEKTUR.md) och planen i [PLAN.md](PLAN.md).*

## 1. Det aktuella repot (RPG Ripparen)

### 1.1 Hur systemet fungerar i dag

Repot är **helt prompt-drivet**: det finns ingen pipeline-kod, utan sex Claude-skills
(`.claude/skills/`) vars SKILL.md-filer instruerar Claude att köra inbäddade
Python-enradare och två små Node-skript. Extraktionsflödet (`extrahera`) är:

1. Rendera PDF-sidor till PNG med PyMuPDF (150 DPI, max 1950 px).
2. Claude läser PNG:erna med Read-verktyget och transkriberar dem till en batch-JSON
   (innehållstyper: `heading1-3`, `paragraph`, `italic`, `statblock`, `table`, `list`, `pagebreak`).
3. Ett agent-team korrekturläser per sida (2–5 agenter enligt sidtriage):
   `sprakgranskare` (alltid), `rollspelskonstruktor` (statblock), `digital-forensiker`
   (`[?]`-markeringar), `layoutverifierare` (komplex layout) och sist `djavulens-advokat`
   som sammanfogar mot PNG:n som sanningskälla.
4. `create-docx.js` genererar DOCX från JSON.
5. Temp-mappen raderas.

OCR-motorn är alltså **Claude själv som vision-modell** — ingen Tesseract, inget externt OCR-API.
Systemkunskap ligger i `.claude/systems/<system>/` (system.json, terms.json,
statblock-format.json) och det finns en mall (`_template/`) för nya system.

### 1.2 Vad som redan är användbart

| Komponent | Bedömning |
| --- | --- |
| **Vision-LLM som OCR** (Claude läser PNG) | Rätt grundidé för svårskannade böcker med komplex layout; överlägset Tesseract på 80-talstryck med spalter och statblock. Behålls. |
| **Agentroller för korrektur** (5 specialister + advokat) | Bra ansvarsfördelning; sidtriage och transkriptionsfiler är genomtänkta token-optimeringar. Behålls i förbättrad form. |
| **Systemadapter-idén** (`.claude/systems/<system>/`) | Rätt arkitekturidé — systemkunskap separerad från flödet, mall för nya system. Innehållet är dock för tunt (se 1.3). |
| **`create-docx.js`** | Fungerande JSON→DOCX-konvertering. Behålls med mindre utbyggnad. |
| **`pdf-utils.js`** (info/split) | Trivialt men fungerande. |
| **Innehållstyps-modellen** (heading/paragraph/statblock/table/list) | Bra grund, men saknar proveniens, confidence och käll-koordinater. Byggs ut. |

### 1.3 Tekniska och arkitektoniska begränsningar

1. **Ingen körbar pipeline.** Allt "kodflöde" är instruktionstext som Claude ska följa manuellt
   varje gång. Ingen determinism, ingen reproducerbarhet, inget som kan testas.
2. **Ingen dokumenttyps-detektering.** Skillen frågar användaren om workflow A (textlager)
   eller B (PNG). Verifierat problemfall: Spindelkonungen-PDF:en har ett textlager som *bara*
   innehåller vattenstämpeln "Drakar och Demoner är © RiotMinds AB" — en naiv
   "har text → läs texten"-strategi ger 36 tecken/sida och tappar hela boken.
3. **Inget state, ingen återupptagning.** Temp-mappar raderas efter körning (`rm -rf`);
   en avbruten batch måste köras om från början. Ingen manifest- eller checkpoint-fil.
   Redan behandlade sidor körs om.
4. **Ingen spårbarhet.** Korrektioner skrivs rakt in i draften; original, ändring, orsak och
   confidence sparas inte. Tysta korrigeringar är i dag normen — tvärtemot kravet.
5. **Ingen kvantifierad kvalitet.** Inga confidence-värden, ingen granskningsrapport,
   ingen flaggning för manuell granskning annat än `[?]`-markörer i löptext.
6. **Trasigt på nuvarande maskin.** Alla sökvägar är hårdkodade till Windows
   (`C:\Users\kalwinde\...`), och miljön saknade PyMuPDF/Poppler (PyMuPDF nu installerat).
7. **Tunn och delvis felaktig systemkunskap.** `terms.json` för DoD innehåller
   no-op-poster ("besvärjelse"→"besvärjelse", "halvling"→"halvling", "trollkarl"→"trollkarl");
   inga färdighetslistor, inga vapentabeller, ingen tärningsnotationsgrammatik, inga
   valideringsintervall per utgåva. `rollspelskonstruktor.md` nämner Mutant-attribut
   ("SKÅ", "KÄN") som inte matchar `mutant/system.json` ("SKP", "KYL").
8. **Ingen regelsystemsidentifiering.** Systemet måste anges manuellt; ingen detektering via
   filnamn/metadata/termstatistik.
9. **Batchgränser styrs av kontextfönstret** (22 sidor, "läs 10–11 bilder åt gången") i stället
   för av en kö med per-sida-jobb — orkestratorns kontext är flaskhalsen.
10. **Ingen loggning, inga tester, ingen kostnadskontroll.**
11. **Statblock-formatet är DoD 1991-centrerat** och blandar presentationsformat (Markdown-mallar)
    med datamodell; `_template/` ärver samma svagheter.

## 2. Referensrepo: Släktforskaren (teknisk måttstock)

En minimal men disciplinerad verktygslåda: tre Python-skript + tre Markdown-dokument.
Bildtolkningen görs — precis som i RPG Ripparen — av **Claude-agenter som läser bilderna
direkt**; det som skiljer är ingenjörsdisciplinen runt omkring.

### 2.1 Mönster värda att ta rakt av

| Mönster | Implementation i Släktforskaren | Tillämpning i Ripparen |
| --- | --- | --- |
| **Idempotent, resumable hämtning** | Skip om filen finns och `st_size > 0`; skriv till `.part` + atomisk `replace()` (`fetch_volume.py:104-135`) | Samma mönster för sidrendering, transkription och korrektur — en färdig sida körs aldrig om |
| **Retry med backoff** | `get_with_retry`: 5 försök, exponentiell backoff på 429/5xx | Agent-/API-anrop och rendering |
| **Felisolering per enhet** | En trasig volym stoppar inte batchen (try/except per volym, loggas) | En trasig sida stoppar inte boken |
| **Manifest-driven identitet** | IIIF-manifest + arkivets bildnummer = filnamn; `structures[]` ger snäva jobb-intervall | `book.json`-manifest per bok; PDF-sidnummer = jobb-ID |
| **Statusdokument som resultat-DB** | `kedjan.md` med ✅ Verifierad / 🔶 Preliminär / ❌ Avfärdad + källhänvisning per påstående | Per-sida status i manifest + granskningsrapport med confidence |
| **Kostnadsdisciplin** | Modelltiering (Haiku/Sonnet/Opus efter svårighet), "skript före LLM", snäva intervall, inga nästlade agenter, korta jobb (~30 bilder) | Samma principer i orkestreringen |
| **Läsdisciplin i prompt** | "Gissa aldrig — hellre [oläsligt]"; ange alltid bildfil + position; jämför osäker glyf mot kända ord i samma hand | Transkriptions- och korrekturprompter |
| **Loggning** | `fetch.log` (DEBUG) + konsol (INFO), progress var 25:e enhet | Pipeline-logg per bok |

### 2.2 Vad Släktforskaren *inte* ger (måste byggas)

- Bildförbehandling (endast manuell PIL-crop finns; ingen deskew/binarisering/kontrast).
- Batchad LLM-anropsmodul med numerisk confidence och tokenbudget i kod.
- Automatiserad validering (allt är mänskligt via statusdokumentet).
- Parallellisering i kod (allt sekventiellt; parallellism = antal agenter, max 1–3).
- Granskningsgränssnitt (endast Markdown + zoombilder).

Slutsats: **återanvänd disciplinen och felhanteringsmönstren, men lyft dem in i en riktig
pipeline med strukturerad datamodell** — rollspelsböcker är tryckt text med komplex layout,
vilket motiverar mer automation än kyrkböckernas handstil.

## 3. Referensrepo: Drakar och Demoner 1991

Det auktoritativa DoD91-repot vars värde för Ripparen ligger i domänmodellen:

- **`src/data/dod91/`** — handverifierade regelkataloger i TypeScript med trohetskommentarer
  per bokvärde: 7 raser, 9 yrken, ~90 färdigheter, 72 besvärjelser, ~150 föremål,
  15 vapengrupper, formeltabeller (KP = ⌈(FYS+STO)/2⌉, skadebonus via STY+STO,
  baschans, förflyttning, BP-kostnad 3–18).
- **`data/monsters.json`** — 215 monster med proveniens (`source.book/file/headingPath`),
  `parseWarnings`-taxonomi (`CRITICAL: KP saknas` …) och normaliserade namn.
- **`scripts/parse-monster-docs.ts`** — en färdig OCR-tolerant statblock-parser:
  `ATTR_FIELDS` (etikett→kanonisk nyckel: `styrka`→`STY`, `kroppspoäng`→`KP` …),
  `SECTION_KEYWORDS`, flera vapenrads-regexar med `parseOk`-flagga.
- **`src/lib/game/dice.ts`** — kanonisk T-notationsparser: `^(\d+)T(\d+)([+-]\d+)?$`;
  giltiga tärningar T2–T100.
- **`data/adventure-import-aliases.json`** — de facto OCR-variantmappning
  (`"kortssvard"→"Kortsvärd"`) — exakt det format Ripparens lexikon behöver.
- **`src/lib/game/adventure/canonicalize.ts`** — mönster för värdevalidering med
  `unresolved`-rapporter (kastar aldrig, flaggar allt oupplöst).
- **`docs/grundregler/*.md`** — de tre 1991-grundböckerna som korrigerad fulltext
  (9 556 rader) — referenskorpus för terminologi.
- **Utgåva:** allt är DoD **1991** (7 egenskaper inkl. STO, FV 1–20). DoD 2023 täcks inte.
  Normaliseringsstandard genomgående: gemener, å/ä→a, ö→o.

## 4. Referensrepo: Mutant 2089

En "regeltrogen AI-spelledare" med tre lager: källböcker som Markdown (med
`ocr-status`-header!), destillat (`build/tabeller.json`, 47 datablock med `kalla`-fält
och `ocr_osaker`-flaggor) och en Python-regelmotor (`motor/`).

- **Systemet är Mutant 2 / "2091"-eran (BRP-släkt)** — *inte* Mutant: År Noll som Ripparens
  nuvarande `mutant`-konfiguration beskriver. 7 egenskaper (STY, STO, INT, FYS, PER, MST, SMI),
  procentfärdigheter (1T100 roll-under), klasser NOM/PSI/ROB/MUT.
- **Härledda formler för korsvalidering:** KP = STO+FYS, SB = STY+STO (kan vara tärning),
  Förflyttning = FYS+SMI, GCL alltid delbart med 5 (ett OCR:at "37 %" är misstänkt).
- **`docs/LATHUND.md`** — explicit byggd som OCR-facit: tärningsförväxlingar
  (`T`↔`I`,`l`,`1`,`7`,`+`), sifferförväxlingar (`0`↔`O`, `1`↔`l`↔`I`, `5`↔`S`, `8`↔`B`),
  egennamnsnormalisering med beslutslogg (Syopox/Sypox, Toytox/Toyfox …) och
  värdekonflikttabell mellan böcker.
- **`motor/slag.py`** — tärningsparser `^(\d+)[TtDd](\d+)([+-]\d+)?$`, konstanter i data
  (perfekt/fummel läses ur `tabeller.json`). Sidor ∈ {4, 6, 8, 10, 20, 100}.
- **SLP-JSON-schemat** (`docs/slp/*.json`) — kanonisk målstruktur för NPC-block, med
  `kalla`, `forekomster` och `_meta.rattningar` (loggade fel→rätt-par).
- **`tests/test_motor.py`** — golden-testset mot bokfacit, inkl. test som vaktar att
  OCR-flaggor inte tystas. Mönstermall för Ripparens tester.

## 5. Jämförelse och slutsatser

### 5.1 Vad referensrepona tillsammans visar

| Egenskap | RPG Ripparen i dag | Släktforskaren | Drakar och Demoner 1991 | Mutant 2089 |
| --- | --- | --- | --- | --- |
| Deterministisk kod för det deterministiska | Nej (prompt-enradare) | Ja | Ja | Ja |
| Idempotens/återupptagning | Nej | Ja (atomisk skrivning + skip) | — | — |
| Proveniens per datapost | Nej | Ja (volym+bild+rad) | Ja (`source`, trohetskommentarer) | Ja (`kalla`, `ocr_osaker`) |
| Spårbara rättningar | Nej | Ja (statusnivåer + beslutslogg) | Ja (aliasfiler, overrides) | Ja (`_meta.rattningar`, LATHUND §10) |
| OCR-felkatalog | Rudimentär | — | Implicit (alias) | Explicit (LATHUND §1, §11) |
| Domänvalidering i kod | Nej | Nej | Ja (`canonicalize.ts`) | Ja (`motor/`, formler) |
| Golden-tester | Nej | Nej | Ja | Ja |

### 5.2 Identifierade problem (prioriterad lista)

1. **P0 — Ingen körbar, deterministisk pipeline**: allt hänger på att Claude följer prosa.
2. **P0 — Ingen dokumenttyps-detektering**: stub-textlager (verifierat i Spindelkonungen) gör
   manuellt val av workflow opålitligt.
3. **P0 — Inget state / ingen återupptagning / omkörningsskydd.**
4. **P0 — Tysta korrigeringar**: korrektionsflödet saknar original/ändring/orsak/confidence.
5. **P1 — Systemkunskapen är tunn och delvis fel**: Mutant-adaptern beskriver fel spel;
   DoD-adaptern saknar färdighets-/vapen-/besvärjelselexikon och valideringsformler som
   referensrepona redan innehåller.
6. **P1 — Ingen regelsystemsidentifiering.**
7. **P1 — Ingen granskningsrapport / kvantifierad kvalitet.**
8. **P2 — Hårdkodade Windows-sökvägar; miljöberoenden odokumenterade.**
9. **P2 — Inga tester, ingen loggning, ingen kostnadsdisciplin i orkestreringen.**
10. **P2 — Export endast DOCX** (ingen Markdown/CSV, ingen sammanhängande bokfil).

### 5.3 Komponenter som återanvänds

- **Från Ripparen:** vision-LLM-transkription, agentroller (med skärpta kontrakt),
  `create-docx.js`, innehållstypsmodellen (utbyggd), systemkatalog-idén.
- **Från Släktforskaren:** idempotens-/atomicitetsmönstret, retry/backoff, felisolering per
  enhet, manifest-driven identitet, statusnivåer, kostnadsdisciplin, läsdisciplin-prompter.
- **Från Drakar och Demoner 1991:** lexikondata (färdigheter, vapen, besvärjelser, monster), formeltabeller,
  `ATTR_FIELDS`-mappningen, tärningsregex, alias-/normaliseringsmönstret, `unresolved`-rapporter.
- **Från Mutant 2089:** LATHUND:s OCR-felkatalog, formlerna (KP/SB/GCL-delbarhet),
  SLP-schemat, `ocr_osaker`-semantiken ("tysta aldrig en flagga"), golden-testmönstret.
