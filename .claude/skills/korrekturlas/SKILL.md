---
name: korrekturlas
description: Korrekturläs en tidigare exporterad rollspelsbok mot source-PDF. Aktiveras med "/korrekturläs", "/korrekturlas", "korrekturläs export", "proofread export", eller när användaren vill korrekturläsa en befintlig JSON-export.
allowed-tools: Read, Write, Edit, Bash(python:*), Bash(node:*), Task, AskUserQuestion, Glob, TodoWrite
---

# Korrekturläs rollspels-export

Korrekturläser en tidigare exporterad JSON-fil mot source-PDF:en med specialistagenter.

## Användning

```
/korrekturläs
```

## Instruktioner

### Steg 1: Interaktiv insamling

Använd `AskUserQuestion` för att samla in:

1. **PDF-fil:** Sökväg till referens-PDF:en.
2. **JSON-fil(er):** Vilken JSON-exportfil ska korrekturläsas? Om flera batches, fråga om alla eller en specifik.
3. **Sidintervall:** Vilka PDF-sidor motsvarar JSON-filen? (t.ex. "1-17")
4. **System:** Vilket rollspelssystem? (default: "dod")

### Steg 2: Validering

```python
python -c "import fitz; doc = fitz.open(r'<PDF>'); print(f'PDF har {len(doc)} sidor'); doc.close()"
```

Läs systemets terminologi:
```
Read file_path="C:\Users\kalwinde\Documents\rollspel-platform\.claude\systems\<system>\terms.json"
```

### Steg 3: Skapa temp-mapp

Härledd från PDF-namn. Skapa undermapp `pages/`.

### Steg 4: Kör korrekturläsning

Se `.claude/skills/_shared/proofreading-workflow.md` för detaljerat workflow.

#### 4.1: Extrahera PNG:er

Alla sidor vid 150 DPI (capped vid 1950px):
```python
python -c "
import fitz, os
MAX_DIM = 1950
pdf_path = r'<PDF-sökväg>'
output_dir = r'<temp-mapp>'
os.makedirs(output_dir, exist_ok=True)
doc = fitz.open(pdf_path)
for page_num in range(<start-1>, <slut>):
    page = doc[page_num]
    w_px = page.rect.width * 150 / 72
    h_px = page.rect.height * 150 / 72
    dpi = int(150 * min(MAX_DIM / w_px, MAX_DIM / h_px)) if w_px > MAX_DIM or h_px > MAX_DIM else 150
    pix = page.get_pixmap(dpi=dpi)
    out = os.path.join(output_dir, f'page_{page_num+1:03d}.png')
    pix.save(out)
    print(f'Saved: {os.path.basename(out)} ({pix.width}x{pix.height})')
doc.close()
"
```

#### 4.2: Dela upp JSON och skriv transkriptioner

1. Dela upp batch-JSON i per-sida drafts (se delad workflow steg 1a).
2. Orchestratorn läser varje PNG EN gång och skriver `page_NNN_transcription.md` (se delad workflow steg 1b).

#### 4.3: Sidtriage

Klassificera sidtyp (se delad workflow steg 2):

| Sidtyp | Agenter |
|--------|---------|
| **Alltid** | `sprakgranskare` + `djavulens-advokat` |
| Statblock | + `rollspelskonstruktor` |
| [?]/[oläsligt] | + `digital-forensiker` |
| Komplex layout | + `layoutverifierare` |
| Enkel text | Bara 2 agenter |

#### 4.4: Fas 1 — Specialistagenter parallellt

Starta agenter baserat på triage med `run_in_background: true`.
Prompts: Se delad workflow steg 3. Alla agenter läser transkriptionsfil, inte PNG.
Undantag: `digital-forensiker` läser PNG (behöver visuell analys).

Poll med Glob tills alla output-filer finns. Kör om misslyckade agenter.

#### 4.5: Fas 2 — Djävulens advokat

Advokaten läser PNG (sanningskällan) + alla specialistoutputs.
Se delad workflow steg 5.

#### 4.6: Sammanfoga

Läs korrigerade filer (`utf-8-sig` encoding), sätt ihop med pagebreaks.
Se delad workflow steg 6.

### Steg 5: Generera DOCX

```bash
node "C:\Users\kalwinde\Documents\rollspel-platform\.claude\skills\extrahera\create-docx.js" "<json>" "<docx>"
```

### Steg 6: Rapportera

Meddela användaren: antal sidor korrekturlästa, antal agenter som behövde köras om, var DOCX sparades.

## Riktlinjer

- **`run_in_background: true`** på alla Task-anrop
- **1 sida per agent-uppsättning** — undvik multi-image-problem
- **Fas 1 → Fas 2** — advokaten körs EFTER alla specialister
- Vanliga OCR-fel: ö↔o, å↔a, ä↔a, rn↔m, ihopslagna ord
- Använd `utf-8-sig` vid inläsning av korrigerade filer (BOM-säkerhet)
