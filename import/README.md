# import/ — inkorg för nya böcker

Lägg käll-PDF:er som ska rippas/extraheras **här**. En fil = en bok.

## Så här går det till

1. **Du:** släpp en eller flera PDF:er i den här mappen.
2. **Du:** säg till Claude, t.ex. *"rippa nya böcker"* / *"extrahera det som ligger i import"*.
3. **Claude** kör hela flödet per bok, från repo-roten:
   ```text
   /extrahera path="import/<filnamn>.pdf"      # analysera → rendera → transkription → validera → sammanfoga → rapport → exportera
   /korrekturläs   (agentkorrektur: sprakgranskare/layoutverifierare → djävulens advokat)
   ```
   Pipelinen äger allt state i `arbete/<slug>/` och är idempotent/återupptagbar — avbrott återupptas med samma kommando.
4. **Claude** verifierar att exporten är komplett (`python3 -m pipeline status --workdir "arbete/<slug>"` = alla sidor minst `validated`, inga fel; `export/`-filerna finns).
5. **Claude** flyttar då PDF:en hit → [`../arkiv/`](../arkiv/) och döper om den
   enligt [NAMNSTANDARD.md](../NAMNSTANDARD.md) (`SYSTEM-TYP-titel.pdf`).
   Filen **raderas aldrig**, bara flyttas.
6. **Claude** döper i samma steg om `arbete/<slug>/` till standardnamnet och
   kopierar `export/bok.md` → [`../bibliotek/`](../bibliotek/)`SYSTEM-TYP-titel.md`
   (en fil per äventyr om boken splittats i `export/aventyr/`).

## Resultatet hamnar i

`arbete/<slug>/export/`: `bok.json`, `bok.md`, `bok.docx`, `tabeller/*.csv`, `granskningsrapport.md`.
Om boken innehåller flera äventyr kan de även delas i `export/aventyr/<nr-slug>/` (härledd, rör ej pipelinens state).

## Regler

- **Flytta, aldrig radera.** `arbete/`-katalogerna är pipelinens state och rörs aldrig.
- En PDF flyttas till `arkiv/` **först när** dess extraktion är klar och verifierad.
- System (dod / mutant2089) autodetekteras; vid osäkerhet frågar Claude innan körning.
- PDF:er versionshanteras inte (se `.gitignore`) — bara den här README:n spåras.
