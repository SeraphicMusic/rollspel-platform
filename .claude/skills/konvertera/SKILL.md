---
name: konvertera
description: Konvertera rollspelsmaterial mellan system. Aktiveras med "/konvertera", "konvertera äventyr", "convert to Mutant", "översätt DoD till Mutant", eller när användaren vill konvertera material mellan olika TTRPG-system.
allowed-tools: Read, Write, Bash(node:*), AskUserQuestion, Glob
---

# Systemkonvertering

Konverterar rollspelsmaterial (äventyr, NPC:er, monster, föremål) mellan olika svenska TTRPG-system.

## Användning

```
/konvertera from="<källsystem>" to="<målsystem>"
```

Startar en interaktiv konverteringsprocess.

### Exempel

```
/konvertera from="dod" to="mutant"
/konvertera from="mutant" to="dod"
```

## Instruktioner

### Steg 1: Välj käll- och målsystem

Om parametrar saknas, fråga användaren:

```
Vilket system konverterar vi FRÅN?
- DoD (Drakar och Demoner)
- Mutant
- Annat
```

```
Vilket system konverterar vi TILL?
- DoD (Drakar och Demoner)
- Mutant
- Annat
```

Läs konverteringsguider och systemkonfigurationer:
```
Read file_path="C:\Users\kalwinde\Documents\rollspel-platform\.claude\systems\<from>\system.json"
Read file_path="C:\Users\kalwinde\Documents\rollspel-platform\.claude\systems\<from>\konvertering.md"
Read file_path="C:\Users\kalwinde\Documents\rollspel-platform\.claude\systems\<to>\system.json"
Read file_path="C:\Users\kalwinde\Documents\rollspel-platform\.claude\systems\<to>\statblock-format.json"
```

### Steg 2: Läs källmaterial

Fråga användaren om källmaterialet:

```
Vad ska konverteras?
- JSON-export (från /extrahera)
- PDF (jag läser och extraherar)
- Text (klistra in eller skriv)
```

Beroende på val:
- **JSON-export**: Läs filen med Read-verktyget
- **PDF**: Läs med Read-verktyget (begränsat sidintervall)
- **Text**: Användaren klistrar in materialet

### Steg 3: Analysera och mappa

Använd konverteringsguiden (`konvertering.md`) för att:

1. **Identifiera element** — NPC:er, monster, föremål, platser, regler
2. **Mappa attribut** — Konvertera grundegenskaper enligt formler
3. **Mappa färdigheter** — Översätt färdigheter till målsystemets motsvarigheter
4. **Mappa koncept** — Anpassa konceptuella element (magi → mutationer, etc.)
5. **Anpassa utrustning** — Konvertera vapen, rustning, föremål

### Steg 4: Presentera konvertering

Visa konverteringen för användaren i ett överskådligt format:

```markdown
## Konvertering: <NPC/monster-namn>

### Källsystem (<from>)
| Egenskap | Värde |
|----------|-------|
| ... | ... |

### Målsystem (<to>)
| Egenskap | Värde |
|----------|-------|
| ... | ... |

### Konverteringsnoteringar
- Attribut X konverterades till Y med formel Z
- Färdighet A har ingen direkt motsvarighet, ersatt med B
```

Be användaren granska och godkänna före export.

### Steg 5: Exportera

Skapa JSON i målsystemets statblock-format:

```json
{
  "title": "Konverterat material: <namn>",
  "sourceSystem": "<from>",
  "targetSystem": "<to>",
  "content": [
    { "type": "heading1", "text": "Konverterat material" },
    { "type": "statblock", "name": "NPC", "stats": { ... } },
    ...
  ]
}
```

Generera DOCX:
```bash
node "C:\Users\kalwinde\Documents\rollspel-platform\.claude\skills\extrahera\create-docx.js" "<json-fil>" "<output-sökväg>"
```

### Steg 6: Rapportera

Meddela användaren:
- Antal konverterade element
- Konverteringsnoteringar (element som krävde manuell anpassning)
- Var JSON och DOCX sparades

## Riktlinjer

- Följ konverteringsformler exakt (från konvertering.md)
- Flagga element som inte har direkt motsvarighet
- Bevara narrativ kontext (namn, beskrivningar, personligheter)
- Anpassa tonalitet till målsystemets genre
- Vid osäkerhet: fråga användaren om preferens
