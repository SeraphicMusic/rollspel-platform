# Runbook: Extrahera Spindelkonungens pyramid (nya pipelinen)

## Källfil

`/Users/kalle.windefalk/Claude/private/DoD RPG/docs/äventyr/04-Drakar-och-Demoner---grundregler,-andra-utgåvan-(1984)_Spindelkonungens-Pyramid-och-Skelettbyns-Hemlighet_RiotMinds.pdf`

28 sidor; 27 är inskannade bilder med enbart copyright-vattenstämpel som textlager
(klassas `image_with_stub_text`), systemet autodetekteras som `dod`.

## Körning i Claude

```text
/extrahera path="/Users/kalle.windefalk/Claude/private/DoD RPG/docs/äventyr/04-Drakar-och-Demoner---grundregler,-andra-utgåvan-(1984)_Spindelkonungens-Pyramid-och-Skelettbyns-Hemlighet_RiotMinds.pdf"
```

Skillen kör pipelinen (`analysera` → `rendera` → transkriptionsloop → `validera`
→ `sammanfoga` → `rapport` → `exportera`). Ingen batchindelning behövs — pipelinen
är per-sida och återupptagbar; avbryts körningen är det bara att köra kommandot igen.

## Förväntad output

`arbete/04-drakar-och-demoner-.../export/`: `bok.json`, `bok.md`, `bok.docx`,
`tabeller/*.csv`, `granskningsrapport.md`.

## Efterkontroll

1. `python3 -m pipeline status --workdir "arbete/04-drakar-och-demoner-..."`
   — alla sidor minst `validated`, inga fel.
2. Läs `export/granskningsrapport.md` och avgör flaggade poster.
3. Vid behov: `/korrekturläs` för agentbaserad korrektur, sedan `exportera` igen.

Obs: sida 4 är redan transkriberad och validerad som referensexempel
(statblocken SPINN/DELL) från pipelinens rökprov.
