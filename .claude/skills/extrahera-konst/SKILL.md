---
name: extrahera-konst
description: This skill should be used when the user asks to "extract illustrations from RPG PDF", "extrahera rollspelsbilder", "omarbeta rollspelsbilder", "generera fantasy-illustrationer", or wants to extract and reimagine RPG book illustrations in Swedish illustrator styles (Ackegård, Bergting, Egerkrans). Works with DoD, Mutant and other Swedish TTRPGs.
allowed-tools: Read, Write, Bash(node:*), Bash(powershell:*), WebFetch, AskUserQuestion
---

# Rollspels-Illustration Extraktor & Stilkonverterare

Extraherar illustrationer från svenska rollspelsböcker (DoD, Mutant m.fl.) och omarbetar dem i klassiska svenska fantasy-illustratörers stilar.

## Målstilar

### Håkan Ackegård (DoD 1991)
- **Teknik**: Svartvit tusch, pennteckningar med hög detaljnivå
- **Karaktäristik**: Dramatiska skuggor, kraftfulla kontraster, nordisk/medeltida atmosfär
- **Motiv**: Äventyrare i mörka fängelsehålor, monster, groteskt detaljerade varelser
- **Prompt-nyckelord**: `ink illustration, black and white, high contrast, crosshatching, dramatic shadows, Nordic fantasy, medieval atmosphere, detailed linework, pen and ink, dungeon crawler aesthetic`

### Peter Bergting (The Portent, Domovoi)
- **Teknik**: Stiliserad linjekonst, grafisk novel-estetik
- **Karaktäristik**: Kraftfulla, dynamiska linjer, nordisk/vikinga-influenser, mörkare paletter
- **Motiv**: Mytologiska varelser, vikingar, götisk fantasy
- **Prompt-nyckelord**: `graphic novel style, bold linework, Nordic mythology, stylized illustration, dark fantasy, viking aesthetic, dynamic composition, moody atmosphere, limited color palette, heavy blacks`

### Johan Egerkrans (Nordiska väsen, Drakar)
- **Teknik**: Detaljerad akvarell och digital målning
- **Karaktäristik**: Atmosfärisk, mystisk, folklore-inspirerad, naturalistisk
- **Motiv**: Folktroväsen, drakar, mytologiska landskap, naturmagi
- **Prompt-nyckelord**: `watercolor illustration, atmospheric, folkloric, mystical, Scandinavian mythology, nature spirits, detailed creatures, soft lighting, muted earth tones, ethereal mood, fairy tale illustration`

## Användning

```
/extrahera-konst path="<PDF-sökväg>" pages="<sidintervall>" style="<ackegard|bergting|egerkrans|all>" system="<dod|mutant|...>"
```

### Parametrar

| Parameter | Beskrivning | Standard |
|-----------|-------------|----------|
| `path` | Sökväg till PDF-filen | (obligatorisk) |
| `pages` | Sidintervall, t.ex. "1-20" eller "5,10,15" | Alla sidor |
| `style` | Målstil för omarbetning | `all` |
| `system` | Rollspelssystem (dod, mutant, ...) | `dod` |
| `output` | Utdatamapp för genererade bilder | Samma som PDF |
| `generate` | `prompts` (bara prompts) eller `images` (generera via Gemini) | `prompts` |

### Exempel

```
/extrahera-konst path="C:\DoD\Barbia.pdf" pages="10-25" style="ackegard" system="dod"
/extrahera-konst path="C:\Mutant\Zonkompendium.pdf" style="egerkrans" system="mutant"
```

## Instruktioner

### Steg 1: Parsa argumenten

Extrahera följande från användarens input:
- `path`: Sökvägen till PDF-filen
- `pages`: Sidintervall (valfritt)
- `style`: `ackegard`, `bergting`, `egerkrans`, eller `all` (standard)
- `system`: Rollspelssystem (default: "dod")
- `generate`: `prompts` eller `images`

Om `system` inte angavs, fråga användaren vilket rollspelssystem PDF:en tillhör.
Läs sedan systemkonfigurationen:
```
Read file_path="C:\Users\kalwinde\Documents\rollspel-platform\.claude\systems\<system>\system.json"
```

Använd systemets `era`-fält för att anpassa prompternas atmosfär.

### Steg 2: PDF-förkontroll

Kör info-kommandot för att verifiera PDF:en:

```bash
node "C:\Users\kalwinde\Documents\rollspel-platform\.claude\skills\extrahera\pdf-utils.js" info "<PDF-sökväg>"
```

### Steg 3: Läs och analysera PDF:en visuellt

Använd Read-verktyget för att läsa PDF:en. Claude analyserar varje sida visuellt och identifierar:

1. **Helsidesillustrationer** - Bilder som täcker hela eller stora delar av sidan
2. **Inramade illustrationer** - Mindre bilder inbäddade i text
3. **Vinjetter** - Små dekorativa illustrationer
4. **Kapitelillustrationer** - Bilder kopplade till specifika kapitel

För varje illustration, notera:
- **Sidnummer**
- **Position på sidan** (topp, mitten, botten, vänster, höger)
- **Ungefärlig storlek** (liten/medium/stor/helsida)
- **Motivbeskrivning** (detaljerad beskrivning av vad bilden föreställer)
- **Teknisk stil i originalet** (tusch, akvarell, etc.)
- **Stämning** (mörk, heroisk, mystisk, etc.)

### Steg 4: Generera stilprompts

För varje identifierad illustration, skapa tre prompts (eller en om specifik stil angavs):

#### Template för Ackegård-stil:
```
Create a black and white ink illustration in the style of Swedish fantasy illustrator Håkan Ackegård (1991 Drakar och Demoner).

Subject: [MOTIVBESKRIVNING]

Style requirements:
- Traditional pen and ink technique with detailed crosshatching
- High contrast with dramatic shadows
- Nordic medieval fantasy atmosphere
- Intricate line work with varying line weights
- Dungeon crawler / dark fantasy aesthetic
- No color, pure black and white

Mood: [STÄMNING]
Composition: [POSITION/STORLEK]
```

#### Template för Bergting-stil:
```
Create a stylized graphic novel illustration in the style of Swedish artist Peter Bergting (The Portent, Domovoi).

Subject: [MOTIVBESKRIVNING]

Style requirements:
- Bold, dynamic linework with heavy blacks
- Graphic novel / comic art aesthetic
- Nordic mythology and viking influences
- Limited color palette (if color: muted earth tones with accent)
- Stylized but expressive character design
- Moody, atmospheric backgrounds

Mood: [STÄMNING]
Composition: [POSITION/STORLEK]
```

#### Template för Egerkrans-stil:
```
Create a watercolor-style illustration in the manner of Swedish illustrator Johan Egerkrans (Nordiska väsen, Drakar).

Subject: [MOTIVBESKRIVNING]

Style requirements:
- Atmospheric watercolor technique with soft edges
- Scandinavian folklore and mythology inspiration
- Mystical, ethereal mood
- Muted earth tones with subtle color harmony
- Naturalistic creature design with fantastical elements
- Fairy tale book illustration quality
- Soft, diffused lighting

Mood: [STÄMNING]
Composition: [POSITION/STORLEK]
```

### Steg 5: Spara resultat

Skapa en JSON-fil med alla extraherade illustrationer och genererade prompts:

```json
{
  "source": "<PDF-filnamn>",
  "system": "<rollspelssystem>",
  "pages": "<sidintervall>",
  "extractedAt": "<timestamp>",
  "illustrations": [
    {
      "id": 1,
      "page": 12,
      "position": "top-right",
      "size": "medium",
      "originalDescription": "En beväpnad krigare...",
      "originalStyle": "svartvit tusch",
      "mood": "heroisk, dramatisk",
      "prompts": {
        "ackegard": "Create a black and white ink illustration...",
        "bergting": "Create a stylized graphic novel illustration...",
        "egerkrans": "Create a watercolor-style illustration..."
      }
    }
  ]
}
```

Spara som: `<pdf-namn>_illustrations.json`

### Steg 6: Använd genererade prompts

Prompterna kan användas på flera sätt:

#### Alternativ A: Google AI Studio (rekommenderat, gratis)
1. Öppna https://aistudio.google.com
2. Välj "Create new prompt"
3. Klistra in prompten och klicka "Generate"

#### Alternativ B: Midjourney
1. Kopiera prompten
2. Lägg till `/imagine prompt:` i Discord
3. Lägg till `--style raw --ar 4:3` för bästa resultat

#### Alternativ C & D: API-baserad bulk-generering

Se `GENERATION_OPTIONS.md` för Imagen- och Gemini-baserad bulk-generering.

### Steg 7: Rapportera resultat

Visa en sammanfattning för användaren.

## Begränsningar

- Extraherar inte bilder fysiskt från PDF - analyserar dem visuellt
- Bildgenerering kräver Gemini API-åtkomst med Imagen aktiverat
- Genererade bilder är tolkningar, inte exakta kopior
- Respektera upphovsrätt - använd endast för personligt bruk
