# Generering av illustrationer — Alternativ C & D

Dessa alternativ kräver API-åtkomst. Se `SKILL.md` för alternativ A (Google AI Studio) och B (Midjourney).

## Alternativ C: Automatisk bulk-generering (kräver Imagen-fakturering)

**Steg 1: Aktivera fakturering (engångsinställning)**
1. Gå till https://console.cloud.google.com/billing
2. Skapa eller välj ett faktureringskonto
3. Koppla det till ditt API-projekt

**Steg 2: Kör bulk-generering**
```bash
node "C:\Users\kalwinde\Documents\rollspel-platform\.claude\skills\extrahera-konst\bulk-generate.js" "<illustrations.json>" "<output-mapp>" [stil]
```

## Alternativ D: PowerShell bulk-generering (Gemini 2.5 Flash Image)

Använder `Generate-Portraits.ps1` för att generera porträtt direkt via Gemini 2.5 Flash Image (gratis tier).

**Förutsättning:** Sätt API-nyckel:
```powershell
$env:GEMINI_API_KEY = "AIza..."
```

**Testa API-anslutningen först:**
```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\kalwinde\Documents\rollspel-platform\.claude\skills\extrahera-konst\Test-GeminiApi.ps1"
```

**Kör bulk-generering:**
```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\kalwinde\Documents\rollspel-platform\.claude\skills\extrahera-konst\Generate-Portraits.ps1"
```

**Parametrar i `Generate-Portraits`:**

| Parameter | Beskrivning | Standard |
|-----------|-------------|----------|
| `StylePrompt` | Art direction-prompt för stil/palett/belysning | (obligatorisk) |
| `Subjects` | Array av motivbeskrivningar (`"BOK\|Varelse, beskrivning"`) | (obligatorisk) |
| `ApiKey` | Gemini API-nyckel | `$env:GEMINI_API_KEY` |
| `OutDir` | Utdatamapp | (obligatorisk) |
| `AspectRatio` | Bildformat: 1:1, 4:3, 16:9 etc. | `1:1` |
| `ImageSize` | Upplösning: 1K, 2K, 4K | `1K` |
| `Model` | Gemini-modell | `gemini-2.5-flash-image` |
| `ImagesPerSubject` | Antal bilder per motiv (1-4) | `1` |
| `DelaySeconds` | Paus mellan API-anrop | `2` |

**Exempel:**
```powershell
$style = "Gritty hand-painted dark fantasy portrait. Classic Swedish tabletop RPG vibe. Muted earthy palette."
$subjects = @(
    "II|Dryad, vacker ung kvinna med ljust lockigt hår, smälter samman med ett träd"
    "II|Gigant, fyra meter hög med gråsvart hud, bär plåtrustning och dubbelyxa"
)
Generate-Portraits -StylePrompt $style -Subjects $subjects -ApiKey $env:GEMINI_API_KEY -OutDir "C:\Rollspel\Porträtt"
```
