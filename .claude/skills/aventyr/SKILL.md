---
name: aventyr
description: Skapa rollspelsäventyr. Aktiveras med "/äventyr", "/aventyr", "skapa äventyr", "create adventure", "bygg scenario", eller när användaren vill konstruera ett äventyr för DoD, Mutant eller annat svenskt TTRPG-system.
allowed-tools: Read, Write, Bash(node:*), AskUserQuestion
---

# Äventyrskonstruktion

Skapar strukturerade rollspelsäventyr för svenska TTRPG-system (DoD, Mutant m.fl.) med NPC:er, encounters, kartor och statblocks.

## Användning

```
/aventyr system="<dod|mutant|...>"
```

Startar en interaktiv äventyrskonstruktion.

## Instruktioner

### Steg 1: Välj system

Om `system` inte angavs, fråga användaren:

```
Vilket rollspelssystem ska äventyret skrivas för?
- DoD (Drakar och Demoner)
- Mutant (År Noll)
- Annat (ange namn)
```

Läs systemkonfigurationen:
```
Read file_path="C:\Users\kalwinde\Documents\rollspel-platform\.claude\systems\<system>\system.json"
Read file_path="C:\Users\kalwinde\Documents\rollspel-platform\.claude\systems\<system>\statblock-format.json"
Read file_path="C:\Users\kalwinde\Documents\rollspel-platform\.claude\systems\<system>\aventyr-guide.md"
```

### Steg 2: Samla koncept

Fråga användaren (med AskUserQuestion) om äventyrets grundkoncept:

**Premiss:**
```
Vad är äventyrets grundidé? Beskriv kort vad det handlar om.
```

**Ton:**
```
Vilken ton ska äventyret ha?
- Mörk och allvarlig
- Klassisk äventyrlig
- Humoristisk
- Mystisk/utforskande
```

**Längd:**
```
Hur långt ska äventyret vara?
- Oneshot (1 session, 3-4 timmar)
- Kort kampanj (2-3 sessioner)
- Kampanjmodul (5+ sessioner)
```

**Spel­arnivå:**
```
Vilken erfarenhetsnivå har rollpersonerna?
- Nybörjare (låga FV/färdigheter)
- Medel
- Erfarna (höga FV/färdigheter)
```

### Steg 3: Generera äventyrsstruktur

Baserat på koncept och systemets äventyrsguide, skapa en strukturöversikt:

1. **Introduktion** — Hook, bakgrund, uppdragsgivare
2. **Akt 1** — Första utmaningen, etablera konflikten
3. **Akt 2** — Eskalering, sidouppdrag, NPC-interaktioner
4. **Klimax** — Avgörande konfrontation
5. **Avslutning** — Konsekvenser, belöningar, uppföljningskrokar

Presentera strukturen för användaren och be om godkännande innan vidare arbete.

### Steg 4: Skriv innehåll

För varje scen/akt, generera:

- **Platsbeskriving** — Atmosfärisk beskrivning med sensoriska detaljer
- **NPC:er** — Namn, personlighet, motiv, dialog-förslag
- **Encounters** — Strid, fällor, sociala utmaningar, pussel
- **Kopplingar** — Hur scenen leder vidare, alternativa vägar
- **SL-tips** — Hur hantera oväntade spelarbeslut

### Steg 5: Generera statblocks

Skapa statblocks för alla NPC:er och monster med systemets format
(från `.claude/systems/<system>/statblock-format.json`).

Använd JSON-formatet som `extrahera/create-docx.js` förstår:
```json
{
  "type": "statblock",
  "name": "NPC-namn",
  "stats": { ... },
  "skills": { ... },
  "other": { ... }
}
```

### Steg 6: Exportera

Skapa en komplett JSON-fil med äventyret i samma format som extrahera-skillen använder:

```json
{
  "title": "<Äventyrsnamn>",
  "system": "<system>",
  "content": [
    { "type": "heading1", "text": "Äventyrsnamn" },
    { "type": "paragraph", "text": "Introduktion..." },
    { "type": "heading2", "text": "Akt 1: ..." },
    { "type": "statblock", "name": "NPC", "stats": { ... } },
    ...
  ]
}
```

Generera sedan DOCX:
```bash
node "C:\Users\kalwinde\Documents\rollspel-platform\.claude\skills\extrahera\create-docx.js" "<json-fil>" "<output-sökväg>"
```

### Steg 7: Rapportera

Meddela användaren:
- Äventyrssummering
- Antal NPC:er och encounters
- Var JSON och DOCX sparades
- Förslag på uppföljningsäventyr

## Riktlinjer

- Skriv alltid på svenska
- Följ systemets konventioner (från aventyr-guide.md)
- Skapa intressanta NPC:er med tydliga motiv
- Inkludera alternativa lösningar för varje situation
- Balansera strid, utforskning och social interaktion
- Ge SL:en verktyg att improvisera (slumptabeller, NPC-motivation)
