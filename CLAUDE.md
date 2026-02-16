# Rollspel-platform — Svensk TTRPG-verktygslåda

Verktyg för att extrahera, bearbeta, korrekturläsa och skapa innehåll för svenska bordsrollspel (Drakar och Demoner, Mutant m.fl.).

## Stödda system

| System | Kort | Genre |
|--------|------|-------|
| Drakar och Demoner | `dod` | Fantasy |
| Mutant (År Noll) | `mutant` | Postapokalyps |

Systemkunskap finns under `.claude/systems/<system>/`. Nya system läggs till med mallen i `_template/`.

## Skills

| Skill | Purpose |
|-------|---------|
| `extrahera` | OCR-like text extraction from scanned PDFs to structured JSON |
| `extrahera-konst` | Illustration extraction and reimagining in Swedish illustrator styles |
| `korrekturlas` | Proofreading exported JSON against source PDF |
| `aventyr` | Interactive adventure construction with NPC:er, encounters and statblocks |
| `konvertera` | System conversion (e.g. DoD → Mutant) of material, NPCs and adventures |
| `karaktarsskapare` | Character creation with attributes, skills, equipment and backstory |

## Systemkunskap

```
.claude/systems/
├── dod/           # Drakar och Demoner
├── mutant/        # Mutant: År Noll
└── _template/     # Mall för nya system
```

Varje system innehåller:
- `system.json` — Attribut, utgåvor, genre
- `statblock-format.json` — Format för statblocks
- `terms.json` — Terminologi och OCR-fel
- `aventyr-guide.md` — Äventyrskonventioner
- `konvertering.md` — Konverteringsguider

## Dependencies

- Node.js (pdf-lib for PDF splitting, docx for DOCX generation)
- Poppler (pdftoppm for page rendering)
- Python (PyMuPDF/fitz for PDF preprocessing)
- PowerShell (Gemini image generation scripts)
- Gemini API key (`$env:GEMINI_API_KEY`)

## Output

- Extracted text: JSON with page-level structure
- Illustrations: Reimagined in styles of Ackegard, Bergting, Egerkrans
- Adventures: Structured JSON + DOCX
- Characters: JSON character sheets + DOCX
- DOCX exports via `extrahera/create-docx.js`
