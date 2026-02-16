---
name: karaktarsskapare
description: Skapa rollspelskaraktärer. Aktiveras med "/karaktär", "/karaktarsskapare", "skapa karaktär", "create character", "rulla ny RP", eller när användaren vill skapa en karaktär för DoD, Mutant eller annat svenskt TTRPG.
allowed-tools: Read, Write, Bash(node:*), AskUserQuestion
---

# Karaktärsskapare

Skapar rollspelskaraktärer för svenska TTRPG-system (DoD, Mutant m.fl.) med attribut, färdigheter, utrustning och bakgrund.

## Användning

```
/karaktarsskapare system="<dod|mutant|...>"
```

Startar en interaktiv karaktärsskapandeprocess.

## Instruktioner

### Steg 1: Välj system

Om `system` inte angavs, fråga användaren:

```
Vilket rollspelssystem ska karaktären skapas för?
- DoD (Drakar och Demoner)
- Mutant (År Noll)
- Annat (ange namn)
```

Läs systemkonfigurationen:
```
Read file_path="C:\Users\kalwinde\Documents\rollspel-platform\.claude\systems\<system>\system.json"
Read file_path="C:\Users\kalwinde\Documents\rollspel-platform\.claude\systems\<system>\statblock-format.json"
```

### Steg 2: Grundkoncept

Fråga användaren om karaktärens grundkoncept:

**Namn:**
```
Vad ska karaktären heta?
```

**Ras/Art:**
Visa alternativ baserat på systemets `races` i system.json:
```
Vilken ras/art? (t.ex. Människa, Dvärg, Alv...)
```

**Klass/Arketyp:**
Visa alternativ baserat på systemet:
- DoD: Yrke (Krigare, Tjuv, Magiker, Jägare, etc.)
- Mutant: Arketyp (Kämpe, Fixare, Hund, etc.)

### Steg 3: Grundegenskaper

Fråga om metod:
```
Hur ska grundegenskaper bestämmas?
- Slå tärningar (enligt systemregler)
- Poängköp (fördela fritt)
- Standarduppsättning (förvalt)
```

Generera/tilldela attribut enligt systemets regler:
- DoD: 3T6 per egenskap (STY, FYS, SMI, INT, PSY, KAR), range 3-18
- Mutant: Fördela 14 poäng på STY, KYL, SMI, SKP (min 2, max 5)

Presentera resultatet och låt användaren justera.

### Steg 4: Färdigheter och utrustning

Baserat på klass/arketyp och system:

**Färdigheter:**
- Tilldela startfärdigheter enligt systemregler
- Visa färdighetslista med valda värden

**Utrustning:**
- Ge startutrustning baserat på klass/arketyp
- Låt användaren anpassa

### Steg 5: Bakgrund och personlighet

Fråga användaren eller generera:

```
Vill du beskriva karaktärens bakgrund själv, eller ska jag generera förslag?
- Skriv egen bakgrund
- Generera förslag
```

Vid generering, inkludera:
- **Bakgrund** — Varifrån karaktären kommer, vad den gjort
- **Personlighet** — Drag, vanor, rädslor
- **Motivation** — Varför ger sig karaktären ut på äventyr
- **Relationer** — Kopplingar till andra (NPC:er, organisationer)
- **Mörk hemlighet** (valfritt) — Något som kan driva drama

### Steg 6: Exportera

Skapa karaktärsblad som JSON:

```json
{
  "title": "<Karaktärsnamn> — Karaktärsblad",
  "system": "<system>",
  "content": [
    { "type": "heading1", "text": "<Karaktärsnamn>" },
    { "type": "paragraph", "text": "Ras: <ras> | Klass: <klass>" },
    {
      "type": "statblock",
      "name": "<Karaktärsnamn>",
      "stats": { ... },
      "skills": { ... },
      "other": { ... }
    },
    { "type": "heading2", "text": "Utrustning" },
    { "type": "list", "items": ["Svärd", "Läderrustning", ...] },
    { "type": "heading2", "text": "Bakgrund" },
    { "type": "paragraph", "text": "<bakgrundstext>" }
  ]
}
```

Generera DOCX:
```bash
node "C:\Users\kalwinde\Documents\rollspel-platform\.claude\skills\extrahera\create-docx.js" "<json-fil>" "<output-sökväg>"
```

### Steg 7: Rapportera

Visa karaktärssammanfattning:
- Namn, ras, klass
- Grundegenskaper
- Nyckel­färdigheter
- Var JSON och DOCX sparades

## Riktlinjer

- Följ systemregler exakt för attribut och färdigheter
- Ge karaktärer djup — inte bara siffror utan personlighet
- Föreslå namn som passar systemets värld och kultur
- Balansera karaktären — inte för stark eller för svag
- Skriv bakgrund på svenska, passande för systemets tonalitet
