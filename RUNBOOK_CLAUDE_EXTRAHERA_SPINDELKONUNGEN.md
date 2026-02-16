# Runbook: Extrahera hela boken i Claude (utan OCR)

Den här runbooken är anpassad för Claude-skillen `extrahera` och undviker alternativa OCR-flöden.

## Källfil

`C:\Users\kalwinde\Downloads\03-Spindelkonungens-pyramid---äventyr--Skellettbyns-hemlighet(1983)-Andra-Upplagan_RiotMinds.pdf`

## Batch-plan (DoD)

- Batch 1: sidor `1-22`
- Batch 2: sidor `23-30`
- System: `dod`

## Körning i Claude

Kör dessa två kommandon i Claude, ett i taget:

```text
/extrahera path="C:\Users\kalwinde\Downloads\03-Spindelkonungens-pyramid---äventyr--Skellettbyns-hemlighet(1983)-Andra-Upplagan_RiotMinds.pdf" pages="1-22" system="dod"
```

```text
/extrahera path="C:\Users\kalwinde\Downloads\03-Spindelkonungens-pyramid---äventyr--Skellettbyns-hemlighet(1983)-Andra-Upplagan_RiotMinds.pdf" pages="23-30" system="dod"
```

## Förväntad output per batch

- En JSON-export med extraherat innehåll
- En DOCX-export genererad via `create-docx.js`

## Efterkontroll

1. Verifiera att båda batcher blev klara utan avbrott.
2. Öppna DOCX-filerna och kontrollera rubriker, statblocks och tabeller.
3. Om kvaliteten behöver höjas: kör `korrekturlas`-skillen mot respektive batch.

## Redan förberedda PNG-mappar (valfritt)

Dessa mappar är skapade och kan användas om du vill felsöka bildflödet:

- `temp/spindelkonungen/batch_1_22`
- `temp/spindelkonungen/batch_23_30`

De är inte ett krav för normal körning av `/extrahera`, men kan vara bra för debugging.
