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
5. **Städningen är ett kommando, inte en god vana:**
   ```text
   python3 -m pipeline arkivera --workdir "arbete/<slug>" \
       --namn SYSTEM-TYP-titel --verkstall
   ```
   Det flyttar PDF:en hit → [`../arkiv/`](../arkiv/) med standardnamnet enligt
   [NAMNSTANDARD.md](../NAMNSTANDARD.md) och kopierar `export/bok.md` →
   [`../bibliotek/`](../bibliotek/)`SYSTEM-TYP-titel.md`. Filen **raderas
   aldrig**, bara flyttas. Utan `--verkstall` är det en torrkörning.

   Kommandot **vägrar** så länge boken inte är klar: någon sida under
   `validated`, ett sidfel, en saknad export eller en öppen `BQ`-post i
   `beslut.md` ger avslag med hela listan av hinder och exit 1. En oavslutad
   boks PDF ska ligga kvar där forensiken lätt når den.
6. **Claude** döper i samma veva om `arbete/<slug>/` till standardnamnet (då
   behövs inte `--namn`) och delar vid behov `export/aventyr/` i en fil per
   äventyr i `bibliotek/`.

> **Varför ett kommando.** Steg 5 var länge bara den här punktlistan, alltså en
> instruktion till en agent. Ingenting körde den, ingenting påminde och
> ingenting märkte att den uteblev — DoD-grundreglernas tre käll-PDF:er blev
> kvar här tills de raderades för hand, och när del I:s forensik behövde den
> inbäddade skanningen (44 % mer upplösning än sidbilderna i `arbete/`) fanns
> den inte längre. `python3 -m pipeline status` säger numera **EJ ARKIVERAD**
> så länge en boks käll-PDF står kvar i den här mappen.

## Resultatet hamnar i

`arbete/<slug>/export/`: `bok.json`, `bok.md`, `bok.docx`, `tabeller/*.csv`, `granskningsrapport.md`.
Om boken innehåller flera äventyr kan de även delas i `export/aventyr/<nr-slug>/` (härledd, rör ej pipelinens state).

## Regler

- **Flytta, aldrig radera.** `arbete/`-katalogerna är pipelinens state och rörs aldrig.
- En PDF flyttas till `arkiv/` **först när** dess extraktion är klar och verifierad.
- System (dod / mutant2089) autodetekteras; vid osäkerhet frågar Claude innan körning.
- PDF:er versionshanteras inte (se `.gitignore`) — bara den här README:n spåras.
