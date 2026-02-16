# Delad korrekturläsnings-workflow

Kanonisk workflow för agentbaserad korrekturläsning. Refereras av `/extrahera` och `/korrekturläs`.

## 1. Förberedelse

### 1a. Dela upp batch-JSON i per-sida drafts

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

### 1b. Skriv transkriptionsfil per sida

Orchestratorn läser varje PNG EN gång och skriver en detaljerad `page_NNN_transcription.md`.
Specialistagenter läser denna textfil (~800 tokens) istället för PNG:n (~4 000 tokens).
Endast `djavulens-advokat` behåller PNG-åtkomst som kvalitetsgate.

Format:

```markdown
# Sida NNN — Transkription

## Layout
[En-kolumn / Tvåkolumn / Mixed]

## Region 1: [Vänster kolumn / Huvudtext / etc.]
[Komplett text med styckeindelning]
**Fetstil**, *kursiv* annoterat inline.

## Region 2: [Höger kolumn / Inramad ruta / etc.]
[Text]

## Illustrationer
- Position: [topp-höger], Storlek: [medium], Motiv: [kort beskrivning]

## Osäkra partier
- Rad X: "[?] svårtydd text" — kontext: [omgivande text]

## Statblock-regioner
- Position: [mitten-vänster], Typ: [NPC-statblock]
```

## 2. Sidtriage

Klassificera varje sida baserat på draft-innehåll:

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

Agenter per sidtyp:

| Sidtyp | Agenter |
|--------|---------|
| **Alltid** | `sprakgranskare` + `djavulens-advokat` |
| Statblock | + `rollspelskonstruktor` |
| [?]/[oläsligt] | + `digital-forensiker` |
| Komplex layout | + `layoutverifierare` |
| Enkel text | Bara 2 agenter (sprakgranskare + advokat) |

## 3. Fas 1 — Specialistagenter parallellt

Starta agenter med `run_in_background: true`. Alla läser **transkriptionsfilen** istället för PNG.

```
Task(subagent_type="sprakgranskare", run_in_background=true, prompt="
  Korrekturläs sida NNN. Filer:
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
  PNG: <temp-mapp>/page_NNN.png
  Draft: <temp-mapp>/pages/page_NNN_draft.json
  Output: <temp-mapp>/pages/page_NNN_forensiker.json
")

Task(subagent_type="layoutverifierare", run_in_background=true, prompt="
  Verifiera layout och fullständighet sida NNN. Filer:
  Transkription: <temp-mapp>/pages/page_NNN_transcription.md
  Draft: <temp-mapp>/pages/page_NNN_draft.json
  Output: <temp-mapp>/pages/page_NNN_layoutverifierare.json
")
```

**Notera:** `digital-forensiker` läser PNG (behöver visuell analys av skadade partier).

## 4. Vänta på Fas 1

Poll med Glob tills alla förväntade output-filer finns.
Misslyckade agenter (ingen output-fil efter timeout): kör om.

## 5. Fas 2 — Djävulens advokat

```
Task(subagent_type="djavulens-advokat", run_in_background=true, prompt="
  Slutgranska sida NNN. Filer:
  PNG: <temp-mapp>/page_NNN.png (SANNINGSKÄLLAN)
  Draft: <temp-mapp>/pages/page_NNN_draft.json
  Specialistoutputs: <lista alla som finns för denna sida>
  Output: <temp-mapp>/pages/page_NNN_corrected.json
")
```

Poll för `page_NNN_corrected.json`.

## 6. Sammanfoga

```python
python -c "
import json, os, glob
pages_dir = r'<temp-mapp>/pages'
content = []
for f in sorted(glob.glob(os.path.join(pages_dir, '*_corrected.json'))):
    with open(f, 'r', encoding='utf-8-sig') as fh:
        page_data = json.load(fh)
    page_num = int(os.path.basename(f).split('_')[1])
    if content: content.append({'type': 'pagebreak', 'page': page_num})
    content.extend(page_data)
with open(r'<output-json>', 'w', encoding='utf-8') as f:
    json.dump({'content': content}, f, ensure_ascii=False, indent=2)
print(f'Sammanfogat {len(glob.glob(os.path.join(pages_dir, \"*_corrected.json\")))} sidor')
"
```

## Riktlinjer

- **`run_in_background: true`** på alla Task-anrop
- **1 sida per agent-uppsättning** — undvik multi-image-problem
- **Fas 1 → Fas 2** — advokaten körs EFTER alla specialister
- **Transkriptionsfiler** sparar ~80% av image-tokens per specialist
- **Sidtriage** sparar ~30-50% av agent-spawns på enkla sidor
- Vanliga OCR-fel: ö↔o, å↔a, ä↔a, rn↔m, ihopslagna ord
- Använd `utf-8-sig` vid inläsning av korrigerade filer (BOM-säkerhet)
