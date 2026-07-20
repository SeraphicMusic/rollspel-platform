# Namnstandard

Gäller käll-PDF:er i `arkiv/` samt allt skapat/konverterat material (äventyr,
karaktärer, konverteringar). Format:

```text
SYSTEM-TYP-titel.ext
```

Exempel: `DOD-AVE-den-vita-duvan.pdf`, `MUT-AVE-attentat-sypox.pdf`,
`DOD-TAB-sinkadus-31-slumptabell-for-skatter.pdf`

## Systemkoder

| Kod | System |
| --- | --- |
| `DOD` | Drakar och Demoner |
| `MUT` | Mutant 2089 |

`MUT` avser **Mutant 2089** — inte Mutant: År Noll (annat spel). Om material
för fler Mutant-versioner tillkommer: byt till `M89` respektive `MYN` för att
skilja dem åt.

## Typkoder

| Kod | Typ |
| --- | --- |
| `AVE` | Äventyr (fristående scenario, inkl. turneringsmoduler) |
| `KMP` | Kampanj (flera länkade äventyr) |
| `REG` | Regelmodul (regelbeskrivning, t.ex. grundregler) |
| `VRL` | Världsbeskrivning (platser, fraktioner, setting) |
| `MON` | Monster/bestiarium |
| `SLP` | Spelledarpersoner |
| `RPK` | Rollpersoner (spelade karaktärer) |
| `TAB` | Tabeller (slumptabeller m.m.) |
| `ART` | Tidningsartikel (Sinkadus-material o.dyl. som inte är någon av ovanstående) |

Innehållet styr, inte källan: en slumptabell ur Sinkadus är `TAB`, inte `ART`.
Inga fler koder utan att uppdatera den här filen.

## Formregler

- System- och typkod i versaler, tre tecken, bindestreck mellan alla delar.
- Titeln i gemener, kebab-case, utan å/ä/ö (å→a, ä→a, ö→o) — samma
  translitterering som pipelinens sluggar.
- Konverterat material får **målsystemets** prefix. Ursprunget kan anges sist:
  `MUT-AVE-den-vita-duvan-fran-dod`.

## Vad som INTE döps om

- `arbete/<slug>/` — pipelinens state, röres aldrig (sluggen behåller det namn
  den skapades med, även om det skiljer sig från arkivnamnet).
- Filer i `import/` — de behåller sitt originalnamn tills extraktionen är klar
  och verifierad; standardnamnet sätts när filen flyttas till `arkiv/`.
