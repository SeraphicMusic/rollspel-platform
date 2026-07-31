# Fas 2 — Målarkitektur

*Bygger på [ANALYS.md](ANALYS.md). Designprinciper: bevara original, inga tysta korrigeringar,
allt spårbart, osäkert flaggas, avbrott kan återupptas, redan klara sidor körs aldrig om,
systemkunskap i adaptrar — inte i kärnflödet.*

## 1. Översikt

Kärnan är en **deterministisk Python-pipeline** (`pipeline/`) som äger allt som inte kräver
en språkmodell: PDF-analys, rendering, textlagerextraktion, state, validering, sammanfogning,
export, loggning och rapporter. **Transkriptionen av inskannade sidor görs av Claude som
vision-modell** (samma grundidé som i dag och i Släktforskaren), men Claude arbetar nu *mot
pipelinens arbetskatalog och state* i stället för mot engångs-tempmappar: pipelinen definierar
jobben, Claude levererar transkript per sida, pipelinen validerar och bokför.

```
                    ┌──────────────────────────────────────────────┐
 PDF ──► analysera ─┤ book.json (manifest: dokumenttyp/sida, state) │
                    └──────────────┬───────────────────────────────┘
                                   │
              ┌────────────────────┼─────────────────────┐
              ▼ (digital_text)     ▼ (image_*)            ▼ (ocr_layer)
        extrahera-text        rendera → PNG          båda (text = hint)
              │                    │                      │
              │                    ▼                      │
              │        Claude transkriberar sida          │
              │        (skill: /rippa — jobb-lista)       │
              └────────────┬───────┴──────────────────────┘
                           ▼
                validera (systemadapter: lexikon, tärningar,
                attributintervall, statblock-schema, struktur)
                           ▼
                korrektur (agent-team, per sida, mot PNG)
                           ▼
                sammanfoga ──► exportera (JSON, MD, DOCX, CSV)
                           └──► granskningsrapport
```

Alla steg är **idempotenta**: varje steg kontrollerar per sida om giltig output redan finns
(Släktforskaren-mönstret: skip om fil finns och är giltig; skriv till `.part`/`.tmp` +
atomisk `replace`). En avbruten körning återupptas med samma kommando.

## 2. Komponenter

### 2.1 Dokumentimport och PDF-analys (`rippare analysera`)

- Läser PDF med PyMuPDF; skriver `book.json`-manifest med: källsökväg, SHA-256,
  sidantal, metadata (titel, producent, år), kryptering.
- **Per-sida-klassificering** (verifierad prototyp mot Spindelkonungen-PDF:en):
  mäter `chars`, `text_coverage` (ordarea/sidarea), `image_coverage` och klassar sidan som
  `digital_text` | `ocr_layer` | `image_only` | `image_with_stub_text` | `empty`.
- **Boilerplate-detektering:** identisk textsträng på > 50 % av sidorna (vattenstämplar,
  copyrightrader) klassas som stub-text och räknas bort ur textmåtten.
- Utfall styr extraheringsmetod per sida — inte per bok (blandade böcker hanteras).

### 2.2 Sidextrahering

- **`rendera`**: PNG per sida, 150 DPI capped 1950 px (Claudes bildgräns), atomisk skrivning,
  skip om giltig PNG finns. Högre DPI-omrendering per sida kan begäras (forensik).
- **`extrahera-text`**: för `digital_text`/`ocr_layer`-sidor extraheras textlagret med
  PyMuPDF `get_text("dict")` → block/rader/spans med bbox, typsnitt och storlek, sparas som
  `page_NNN.embedded.json`. Läsordning sorteras kolumnmedvetet (spaltdetektering via
  x-klustring av block). För `ocr_layer` används detta som *hint* till transkriptionen,
  aldrig som sanning.

### 2.3 Bildförbehandling

Minimal per default (tryckta böcker är oftast läsbara): gråskala + autokontrast vid behov.
Per-sida-flaggor i manifestet kan begära `deskew`/`contrast`/`upscale` för problematiska
sidor — förbehandling är ett steg i kedjan, inte ett obligatoriskt pass.

### 2.4 Transkription (vision-LLM)

- `rippare jobb` listar nästa otranskriberade sidor med sökvägar (PNG, ev. embedded-hint,
  systemadapterns kontext) — snäva jobb i Släktforskaren-anda.
- Skillen `/rippa` (ersätter `extrahera`s inre) instruerar Claude att transkribera **en sida
  i taget** till `page_NNN.transcript.json` enligt elementmodellen (§ 3), med läsdisciplin:
  *gissa aldrig — markera `[?]` med confidence; ange region/position; modernisera inte språk.*
- Illustrationer analyseras eller beskrivs inte. Text som ingår i själva bildmotivet
  hoppas också över; endast typografiskt separat boktext transkriberas. En sida som
  enbart är en illustration bokförs med tom `elements` och
  `skipped.reason = "illustration_only"`.
- Pipelinen validerar JSON-schema direkt vid inbokning; trasig output → sidan behåller
  status `rendered` och dyker upp i `jobb` igen.

### 2.5 Layoutanalys och strukturigenkänning

Två källor kombineras:
1. **Deterministiskt** (embedded-sidor): kolumndetektering, rubriknivåer via typsnittsstorlek,
   upprepade sidhuvud/sidfot/sidnummer via positionsmönster över sidor.
2. **Vision-modellen** (skannade sidor): transkriptet bär `layout`-metadata (kolumner,
   regioner, läsordning) och elementtyper (tabell, statblock, faktaruta, lista, index, TOC).

### 2.6 Regelsystemsidentifiering (`identifiera-system`)

Poängbaserad fingeravtrycksmatchning, alltid överstyrbar med `--system`:
- filnamn + PDF-metadata (titel, förlag, ISBN-mönster),
- termstatistik i tillgänglig text (embedded eller transkriberade provsidor) mot varje
  adapters `detection.json` (attributförkortningar, systemtermer, tärningsnotation),
- resultatet (system + utgåva + confidence) skrivs i manifestet.

### 2.7 Systemadaptrar och validering

All systemkunskap ligger i **data, inte kod**: `system/<id>/` (flyttas ut ur `.claude/`)
med `system.json`, `lexicon.json`, `dice.json`, `statblock.schema.json`, `detection.json`.
Valideringsmotorn är generisk och drivs av adapterdata:

| Validator | Gör | Exempel |
| --- | --- | --- |
| Tärningsnotation | Regex-grammatik per system + OCR-förväxlingsvarianter | `ITG` → `1T6` (I→1, G→6) |
| Attribut | Namn + intervall per utgåva | DoD-STY 3–18; `SIY 12` → `STY 12` |
| Lexikon | Ordlista + förväxlingsgenerator (o↔ö, a↔ä/å, 0↔O, 1↔l/I, 5↔S, 8↔B, rn↔m) | `Fardighet` → `Färdighet` endast om entydigt |
| Härledda värden | Aritmetisk korsvalidering av formler per system | Mutant 2089: KP ≠ STO+FYS ⇒ flagga; procentvärde ej delbart med 5 ⇒ flagga |
| Statblock | Schema per system | saknade/omöjliga fält flaggas |
| Struktur | Tabellkonsistens (kolumnantal), rubriknivåer, sidkontinuitet | rad med fel cellantal flaggas |

**Rättningspolicy:** entydig träff + hög confidence ⇒ rättning *föreslås och bokförs*;
tvetydig/låg confidence ⇒ ingen ändring, elementet flaggas `needs_review`. Allt enligt § 3.3.

### 2.8 Korrektur (agent-team)

Befintliga agentroller behålls men skriver in i pipelinens struktur
(`page_NNN.review/<agent>.json`) och **måste uttrycka ändringar som korrektionsposter**
(original → ny text + orsak + confidence), inte som tyst omskriven text. Advokaten
producerar `page_NNN.final.json`. Sidtriage (vilka agenter som behövs) beräknas av
pipelinen deterministiskt av valideringsresultatet.

### 2.9 Kvalitetskontroll, lagring, export

- **`sammanfoga`**: per-sida-final → `export/bok.json` (kanoniskt format, § 3).
- **`exportera`**: Markdown (per kapitel + hel bok), DOCX (via `create-docx.js`),
  CSV per tabell, allt genererat *från* kanonisk JSON.
- **`rapport`**: granskningsrapport (Markdown) med alla `needs_review`-element, låg-confidence-
  transkript, ej applicerade förslag och valideringsfel — sorterad per sida med källhänvisning.
- **`status`**: state-översikt per sida/steg.

### 2.10 Loggning, felhantering, återupptagning

- Logg per bok: `arbete/<bok>/logs/pipeline.log` (fil DEBUG, konsol INFO).
- Felisolering per sida: en trasig sida sätter `error` + orsak i manifestet och stoppar
  inte boken.
- Manifestet uppdateras atomiskt; alla steg är omkörbara utan att förstöra färdigt arbete.
- Kostnadsdisciplin: transkription sker bara för sidor som behöver det; korrektur bara för
  agenter som triagen kräver; deterministiska validatorer körs *före* LLM-korrektur
  ("skript före LLM").

## 3. Datamodell

### 3.1 Manifest (`arbete/<bok>/book.json`)

```json
{
  "schema_version": 1,
  "source": {"path": "...", "sha256": "...", "pages": 28, "metadata": {"title": "..."}},
  "system": {"id": "dod", "edition": "1984", "confidence": 0.9, "method": "fingerprint|manual"},
  "doc_type": {"summary": "scanned_with_stub_text", "boilerplate": ["Drakar och Demoner är © RiotMinds AB"]},
  "pages": {
    "17": {
      "class": "image_with_stub_text",
      "state": "validated",
      "steps": {"rendered": "2026-07-16T...", "transcribed": "...", "validated": "..."},
      "flags": ["statblock", "table"],
      "needs_review": 2,
      "error": null
    }
  }
}
```

Sidans state-maskin: `pending → rendered → transcribed → validated → reviewed → final`
(embedded-sidor hoppar `rendered`→`extracted`). `error` och `needs_review` är ortogonala fält.

### 3.2 Element (kanoniskt innehållsformat)

```json
{
  "id": "p017_e03",
  "type": "statblock | heading | paragraph | table | list | boxed_text | toc_entry | index_entry | page_artifact",
  "level": 2,
  "text": "…",
  "data": {"name": "Grottroll", "stats": {"STY": 18}, "skills": {...}},
  "source": {"page": 17, "region": "vänsterkolumn", "bbox": [72, 340, 290, 512], "method": "vision-llm | embedded"},
  "confidence": 0.92,
  "corrections": [ ... se 3.3 ... ],
  "needs_review": false
}
```

`page_artifact` (sidhuvud/sidfot/sidnummer/vattenstämpel) bevaras men exkluderas ur läsexport.

### 3.3 Korrektionspost (spårbarhet)

```json
{
  "original": "ITG",
  "corrected": "1T6",
  "applied": true,
  "confidence": 0.97,
  "reason": "Tärningsnotation: I→1, G→6; '1T6' giltig i dod/dice.json",
  "source": "validator:dice | agent:sprakgranskare | manual",
  "timestamp": "2026-07-16T12:00:00Z"
}
```

- `applied: false` + `needs_review: true` när confidence < tröskel (default 0.9).
- Originaltexten finns alltid kvar i posten — inga tysta korrigeringar, full ångerbarhet.

### 3.4 Exportformat

| Format | Innehåll |
| --- | --- |
| `bok.json` | Kanoniskt: alla element med proveniens, confidence, korrektioner |
| `bok.md` | Läsbar Markdown; statblock/tabeller som MD-tabeller; artefakter utelämnade |
| `bok.docx` | Via `create-docx.js` |
| `tabeller/*.csv` | En CSV per extraherad tabell |
| `granskningsrapport.md` | Alla osäkra/flaggade element med sida + originaltext + förslag |

## 4. Representation av regelsystemskunskap

```
system/
├── _template/            # mall för nya system
├── dod/                  # DoD 1991 (primärt; 1984 nära släkt)
│   ├── system.json       # namn, utgåvor, attribut + intervall, härledda formler
│   ├── lexicon.json      # termer, färdigheter, vapen, besvärjelser, varelser, egennamn
│   ├── dice.json         # notationsgrammatik + kända OCR-förväxlingar
│   ├── statblock.schema.json  # fältkrav och värdedomäner
│   └── detection.json    # fingeravtryck: unika termer, förkortningar, viktning
└── mutant2089/ …         # OBS: ersätter dagens 'mutant' som beskrev Mutant: År Noll —
                          # fel spel relativt referensrepot (BRP-procent vs tärningspool)
```

Nya system = ny katalog från `_template/` — ingen kodändring. Adaptrarna matas dels
manuellt, dels genererat från referensrepona via `scripts/bygg_adapter.py`
(läser DoD-repots kataloger/monsters.json och Mutant-repots LATHUND/tabeller.json/SLP-filer).

## 5. Manuell granskningsprocess

1. `rippare rapport` genererar granskningsrapporten.
2. Människan (eller en granskningsskill i Claude) går igenom posterna; beslut skrivs som
   korrektionsposter med `source: "manual"`.
3. `rippare sammanfoga && rippare exportera` regenererar all export deterministiskt.
