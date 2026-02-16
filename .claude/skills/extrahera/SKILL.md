---
name: extrahera
description: This skill should be used when the user asks to "extract text from RPG PDF", "extrahera text från rollspels-PDF", "skapa Word från inskannad PDF", or mentions extracting scanned TTRPG books (DoD, Mutant, etc.). Handles OCR-like extraction and DOCX generation.
allowed-tools: Read, Bash(node:*), Bash(python:*), AskUserQuestion, Task, Glob
---

# Rollspels-PDF Extraktor

Extraherar text från inskannade svenska rollspelsböcker (Drakar och Demoner, Mutant m.fl.) och skapar formaterade Word-dokument.

## Användning

```
/extrahera path="<sökväg till PDF>" pages="<sidintervall>" system="<dod|mutant|...>"
```

Exempel:
```
/extrahera path="C:\Users\kalwinde\Downloads\DoD - Kampanj - Barbia.pdf" pages="10-25" system="dod"
/extrahera path="C:\Users\kalwinde\Downloads\Mutant År Noll.pdf" pages="1-20" system="mutant"
```

## Två arbetsflöden

### Workflow A: Direkt PDF-läsning (för textbaserade PDF:er)
### Workflow B: PNG-extraktion (för inskannade böcker) — REKOMMENDERAS

**Batch-rekommendation:** Max 22 sidor per batch (t.ex. 66 sidor = 3 batches).

## Instruktioner

### Steg 0: Identifiera system

Om `system`-parametern inte angavs, fråga användaren. Läs sedan systemkonfigurationen:
```
Read file_path="C:\Users\kalwinde\Documents\rollspel-platform\.claude\systems\<system>\system.json"
Read file_path="C:\Users\kalwinde\Documents\rollspel-platform\.claude\systems\<system>\statblock-format.json"
Read file_path="C:\Users\kalwinde\Documents\rollspel-platform\.claude\systems\<system>\terms.json"
```

### Steg 1: Parsa argumenten

Extrahera `path`, `pages` (format "start-slut"), `system` (default: "dod").
Om argumenten saknas, be användaren ange dem.

### Steg 1.5: PDF-förkontroll

```python
python -c "import fitz; doc = fitz.open(r'<PDF-sökväg>'); print(f'Antal sidor: {len(doc)}'); doc.close()"
```

Om > 22 sidor: dela upp i batches om max 22. Varje batch får egen JSON + DOCX.

### Steg 2: Extrahera sidor (Workflow B - PNG)

```python
python -c "
import fitz
import os

MAX_DIM = 1950  # Under Claudes 2000px-gräns för multi-image requests
pdf_path = r'<PDF-sökväg>'
output_dir = r'<temp-mapp>'
os.makedirs(output_dir, exist_ok=True)

doc = fitz.open(pdf_path)
for page_num in range(<start-1>, <slut>):  # 0-indexed
    page = doc[page_num]
    rect = page.rect
    w_px = rect.width * 150 / 72
    h_px = rect.height * 150 / 72
    if w_px > MAX_DIM or h_px > MAX_DIM:
        dpi = int(150 * min(MAX_DIM / w_px, MAX_DIM / h_px))
    else:
        dpi = 150
    pix = page.get_pixmap(dpi=dpi)
    out_path = os.path.join(output_dir, f'page_{page_num + 1:03d}.png')
    pix.save(out_path)
    print(f'Saved: page_{page_num + 1:03d}.png ({pix.width}x{pix.height}, {dpi} DPI)')
doc.close()
"
```

### Steg 2b: Läs bilderna med Claude

```
Read file_path="<temp-mapp>/page_001.png"
Read file_path="<temp-mapp>/page_002.png"
```

**Parallellisering:** Läs gärna 10-11 bilder åt gången.

### Alternativ: Steg 2 (Workflow A - Direkt PDF)

```
Read file_path="<PDF-sökväg>"
```

Om > 80 sidor:
```bash
node "C:\Users\kalwinde\Documents\rollspel-platform\.claude\skills\extrahera\pdf-utils.js" split "<PDF-sökväg>" <startSida> <slutSida> "<temp-chunk-sökväg>"
```

### Steg 3: Extrahera och formatera text

Analysera varje sida:

1. **Vanlig text**: Löptext med styckeindelning.
2. **Rubriker**: `#` Kapitelrubrik, `##` Sekundär, `###` Underrubrik.
3. **NPC Statblocks**: Formatera enligt `.claude/systems/<system>/statblock-format.json`.
4. **Tabeller**: Markdown-format.
5. **Listor**: Markdown-listor.
6. **Tvåkolumnslayout**: Extrahera vänster kolumn först, sedan höger.
7. **Kursiv text**: Flavor text / beskrivningar.

### Steg 3.5: Korrekturläsning (agent-team per sida)

Inskannade böcker ger OCR-fel. Skippa detta steg för textbaserade PDF:er (Workflow A).

Se `.claude/skills/_shared/proofreading-workflow.md` för fullständigt workflow.

**Agenter (2-5 per sida beroende på sidtyp):**

| Agent | Typ | Villkor |
|-------|-----|---------|
| Språkgranskare | `sprakgranskare` | Alltid |
| Rollspelskonstruktör | `rollspelskonstruktor` | Sidan har statblocks |
| Digital forensiker | `digital-forensiker` | Sidan har [?]/[oläsligt] |
| Layoutverifierare | `layoutverifierare` | Komplex layout |
| Djävulens advokat | `djavulens-advokat` | Alltid (Fas 2) |

#### Steg 3.5.1: Dela upp draft-text per sida

```python
python -c "
import json, os
out_dir = r'<temp-mapp>/pages'
os.makedirs(out_dir, exist_ok=True)
with open(r'<batch-json>', 'r', encoding='utf-8') as f:
    data = json.load(f)
pages, current, pdf_page = [], [], <start-pdf>
for item in data['content']:
    if item.get('type') == 'pagebreak':
        if current: pages.append((pdf_page, current)); pdf_page += 1
        current = []
    else: current.append(item)
if current: pages.append((pdf_page, current))
for p, elems in pages:
    with open(os.path.join(out_dir, f'page_{p:03d}_draft.json'), 'w', encoding='utf-8') as f:
        json.dump(elems, f, ensure_ascii=False, indent=2)
    print(f'page_{p:03d}_draft.json: {len(elems)} elements')
"
```

#### Steg 3.5.2: Skriv transkriptionsfil per sida

Orchestratorn läser varje PNG (från Steg 2) **EN gång** och skriver `page_NNN_transcription.md`.
Specialistagenter läser denna textfil (~800 tokens) istället för PNG:n (~4 000 tokens).
Endast advokaten behåller PNG-åtkomst som kvalitetsgate.

Innehåll: Sidlayout, komplett text per region med stilannoteringar, illustrationspositioner,
osäkra partier markerade med [?], statblock-regioner identifierade.
Format: Se `.claude/skills/_shared/proofreading-workflow.md` steg 1b.

#### Steg 3.5.3: Sidtriage

Klassificera sidtyp och avgör vilka agenter som behövs:

```python
python -c "
import json, os, glob
pages_dir = r'<temp-mapp>/pages'
for f in sorted(glob.glob(os.path.join(pages_dir, '*_draft.json'))):
    with open(f, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    text = json.dumps(data, ensure_ascii=False)
    flags = []
    if any(item.get('type') == 'statblock' for item in data): flags.append('statblock')
    if '[?]' in text or '[oläsligt]' in text: flags.append('forensiker')
    has_table = any(item.get('type') in ('table','list') for item in data)
    has_multi = len([i for i in data if i.get('type') in ('paragraph','heading1','heading2')]) > 8
    if has_table or has_multi: flags.append('komplex')
    page = os.path.basename(f).split('_draft')[0]
    print(f'{page}: {chr(44).join(flags) if flags else \"enkel\"}')
"
```

#### Steg 3.5.4: Fas 1 — Specialistagenter parallellt

Starta agenter baserat på triage-resultat med `run_in_background: true`:

```
Task(subagent_type="sprakgranskare", run_in_background=true, prompt="
  Korrekturläs sida NNN i <systemnamn>-bok. Filer:
  Transkription: <temp-mapp>/pages/page_NNN_transcription.md
  Draft: <temp-mapp>/pages/page_NNN_draft.json
  Terms: <terms.json-sökväg>
  Output: <temp-mapp>/pages/page_NNN_sprakgranskare.json
")

Task(subagent_type="rollspelskonstruktor", run_in_background=true, prompt="
  Korrekturläs sida NNN. System: <system>, <era>.
  Attribut: <attributlista>. Range: <range>. Kända OCR-fel: ö↔o, å↔a, ä↔a.
  Filer:
  Transkription: <temp-mapp>/pages/page_NNN_transcription.md
  Draft: <temp-mapp>/pages/page_NNN_draft.json
  Output: <temp-mapp>/pages/page_NNN_rollspel.json
")

Task(subagent_type="digital-forensiker", run_in_background=true, prompt="
  Reparera [?]/[oläsligt] på sida NNN. Filer:
  PNG: <temp-mapp>/page_NNN.png  |  Draft: <temp-mapp>/pages/page_NNN_draft.json
  Output: <temp-mapp>/pages/page_NNN_forensiker.json
")

Task(subagent_type="layoutverifierare", run_in_background=true, prompt="
  Verifiera layout och fullständighet sida NNN. Filer:
  Transkription: <temp-mapp>/pages/page_NNN_transcription.md
  Draft: <temp-mapp>/pages/page_NNN_draft.json
  Output: <temp-mapp>/pages/page_NNN_layoutverifierare.json
")
```

Poll med Glob tills alla förväntade output-filer finns. Kör om misslyckade agenter.

#### Steg 3.5.5: Fas 2 — Djävulens advokat

```
Task(subagent_type="djavulens-advokat", run_in_background=true, prompt="
  Slutgranska sida NNN. Filer:
  PNG: <temp-mapp>/page_NNN.png (SANNINGSKÄLLAN)
  Draft: <temp-mapp>/pages/page_NNN_draft.json
  Specialistoutputs: <lista alla som finns för denna sida>
  Output: <temp-mapp>/pages/page_NNN_corrected.json
")
```

#### Steg 3.5.6: Sammanfoga

Läs korrigerade filer (`utf-8-sig` encoding), sätt ihop med pagebreaks, spara som batch-JSON.

**Riktlinjer:**
- **1 sida per agent-uppsättning** — undvik multi-image-problem
- **6 subagenter parallellt** per våg (matchar rate limits)
- **Fas 1 → Fas 2** — advokaten körs EFTER alla specialister

### Steg 4: Skapa Word-dokument

Skapa en JSON-fil med den extraherade datan. Innehållstyper:
`heading1`, `heading2`, `heading3`, `paragraph`, `italic`, `pagebreak`, `statblock`, `table`, `list`.
Statblock-format: Se `.claude/systems/<system>/statblock-format.json`.

```bash
node "C:\Users\kalwinde\Documents\rollspel-platform\.claude\skills\extrahera\create-docx.js" "<json-fil>" "<output-sökväg>"
```

Output: `<pdf-namn>_pages_<sidintervall>.docx`

### Steg 5: Städa upp

```bash
rm -rf "<temp-mapp>"
```

### Steg 6: Rapportera resultat

Meddela användaren:
- Vilket system som identifierades
- Vilka sidor som extraherades
- Var Word-dokumentet sparades
- Eventuella problem eller varningar
- Om fler batches behövs: vilka sidor som återstår

## Innehållstyper

Attribut och terminologi: Se `.claude/systems/<system>/system.json`.
Vanliga layoutelement:
- Tvåkolumnslayout (vänster kolumn först, sedan höger)
- Inramade textrutor (äventyrsintroduktioner)
- Kursiv text för berättartext/flavor text
- Fet text för viktiga termer och namn
