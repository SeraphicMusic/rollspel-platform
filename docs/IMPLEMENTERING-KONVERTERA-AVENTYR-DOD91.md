# Implementering: explicit konvertering av ett äventyr till DoD91

## Status

Implementeringsspecifikation. Funktionen finns ännu inte i pipelinen.

## Syfte

En användare pekar ut **ett specifikt, färdigrippat äventyr** och begär en
regelkonvertering till Drakar och Demoner 1991. Funktionen analyserar det
utpekade äventyret, konverterar en kopia och skapar en fullständig rapport.

Konverteringen är inte en del av den automatiska extraktionskedjan. Den:

- startas endast med ett uttryckligt kommando;
- letar inte själv efter andra äventyr;
- ändrar aldrig källan eller befintligt extraktionsstate under `arbete/`;
- kör inte OCR, transkription eller korrekturläsning på nytt;
- producerar en publicerbar kopia under `konverterat/dod91/`.

Detta ger följande ansvarsfördelning:

```text
PDF → arbete/ → bibliotek/                 trogen transkription
                 │
                 └─ explicit konvertering
                              │
                              ▼
                    konverterat/dod91/     DoD91-version
                              │
                              ▼
                    import i Drakar och Demoner 1991
```

## Användargränssnitt

### Grundkommando

```bash
python3 -m pipeline konvertera \
  --source "arbete/DOD-AVE-edsbrytarna-i-erebos/export/bok.json" \
  --from dod-t100 \
  --to dod91
```

`--source` pekar på exakt den `bok.json` som ska konverteras. Detta är
avsiktligt mer precist än `--workdir`, eftersom en arbetskatalog kan innehålla
flera separat exporterade äventyr:

```bash
python3 -m pipeline konvertera \
  --source "arbete/DOD-AVE-spindelkonungens-pyramid-och-skelettbyns-hemlighet/export/aventyr/01-spindelkonungens-pyramid/bok.json" \
  --from dod-t100 \
  --to dod91
```

### Argument

| Argument | Krav | Betydelse |
| --- | --- | --- |
| `--source PATH` | Ja | Exakt `bok.json` som är sanningskälla |
| `--from PROFILE` | Ja i version 1 | Källprofil, initialt endast `dod-t100` |
| `--to PROFILE` | Ja i version 1 | Målprofil, initialt endast `dod91` |
| `--output-name SLUG` | Nej | Överstyr härlett namn vid behov |
| `--force` | Nej | Bygg om trots oförändrad källa och konverterarversion |
| `--dry-run` | Nej | Skapa analys och rapport men ingen publicerad MD/JSON |

Funktionen ska aldrig försöka avgöra vilka andra äventyr som behöver
konverteras. Valet av källa är användarens beslut.

## Förutsättningar

Kommandot ska avbryta utan att skriva publiceringsfiler om:

- `--source` inte finns eller inte är en JSON-fil;
- filen inte följer pipelinens `bok.json`-struktur;
- källsystemet inte är Drakar och Demoner;
- källan fortfarande saknar färdig sammanfogning;
- källprofilen eller målprofilen inte stöds.

`needs_review` från extraktionen är inte automatiskt ett konverteringsfel.
Rapporten ska dock återge antalet befintliga granskningsposter så att en
regelkonvertering inte misstolkas som ett godkännande av transkriptionen.

## Kataloger och filer

### Internt konverteringsstate

State sparas under arbetskatalogen, men separerat från extraktionsstate:

```text
arbete/<slug>/konvertering/dod91/<aventyrs-slug>/
├── manifest.json
├── analys.json
├── bok.konverterad.json
└── konverteringsrapport.md
```

För ett deläventyr används deläventyrets slug. Inga filer i `export/`,
`pages/` eller arbetskatalogens `book.json` får ändras.

### Publicerade läskopior

När konverteringen inte har blockerande granskningsposter skrivs:

```text
konverterat/dod91/DOD-AVE-<titel>.md
konverterat/dod91/DOD-AVE-<titel>.json
konverterat/dod91/DOD-AVE-<titel>.konverteringsrapport.md
```

Namnet följer [NAMNSTANDARD.md](../NAMNSTANDARD.md). Målsystemet bestämmer
prefixet. Källsystem, profil och proveniens sparas i metadata och behöver inte
göras till en del av filnamnet.

Vid `--dry-run` skrivs endast statefilerna `manifest.json`, `analys.json` och
`konverteringsrapport.md`.

## Konverteringsprofil

Regler och alias ska vara data, inte hårdkodade specialfall. Den första
profilen läggs exempelvis här:

```text
system/dod/conversion/dod-t100-to-dod91.json
```

Profilen ska minst innehålla:

```json
{
  "id": "dod-t100-to-dod91",
  "version": 1,
  "source": "dod-t100",
  "target": "dod91",
  "fv": {
    "formula": "round(value / 5)",
    "minimum": 3,
    "maximum": 18
  },
  "skill_aliases": {},
  "weapon_aliases": {},
  "armor_aliases": {},
  "monster_aliases": {}
}
```

## Auktoritativ DoD91-källa

Enda auktoritativa källan för målsystemets färdigheter, utrustning och
regelvärden är referensrepot:

```text
/Users/kalle.windefalk/Claude/private/Drakar och Demoner 1991
```

Det äldre repot `DoD RPG` får inte användas för att bygga eller uppdatera
DoD91-katalogerna.

Följande källfiler ska ingå i den första katalogexporten:

| Källfil i referensrepot | Data |
| --- | --- |
| `src/data/dod91/skills.ts` | Färdighets-ID, namn, grundegenskap, skala och typ |
| `src/data/dod91/skillChoices.ts` | Dynamiska färdighetsval, instrument och hantverk |
| `src/data/dod91/equipment.ts` | Vapen, vapengrupper, sköldar, rustningar och allmän utrustning |
| `src/data/dod91/provisions.ts` | Proviant och priser |
| `src/data/dod91/lakedroger.ts` | Läkedroger och regelvärden |
| `src/data/dod91/tables.ts` | Härledda värden och relevanta regeltabeller |

Markdown-filerna under `docs/grundregler/` används som verifierings- och
proveniensunderlag när en katalogpost behöver kontrolleras. Konverteraren ska
inte tolka dessa fria texter på nytt vid varje körning.

Referensdata exporteras som versionslåsta snapshots:

```text
system/dod/reference/dod91/
├── skills.json
├── weapons.json
├── shields.json
├── armor.json
├── equipment.json
├── provisions.json
├── lakedroger.json
├── tables.json
└── catalog.json
```

`catalog.json` ska minst bära:

```json
{
  "ruleset": "dod91",
  "source_repository": "Drakar och Demoner 1991",
  "source_path": "/Users/kalle.windefalk/Claude/private/Drakar och Demoner 1991",
  "source_commit": "<git-commit>",
  "generated": "<ISO-8601>",
  "checksums": {}
}
```

Snapshots genereras uttryckligen:

```bash
python3 scripts/bygg_adapter.py dod \
  --ref "/Users/kalle.windefalk/Claude/private/Drakar och Demoner 1991"
```

Den nuvarande adapterbyggaren extraherar huvudsakligen `name`-fält. Den måste
utökas så att de fullständiga TypeScript-objekten exporteras; namnlistor i
`lexicon.json` är inte tillräckliga för regelkonvertering. Exporten ska bland
annat bevara:

- färdighetens stabila ID, skala och kopplade grundegenskap;
- vapnets typ, skada, STY-krav, räckvidd och vapengrupp;
- rustningens ABS och kroppsdel;
- sköldars och övrig utrustnings relevanta regelvärden;
- källrepo, commit och checksumma.

Körningen av `pipeline konvertera` använder endast snapshotfilerna i
`system/dod/reference/dod91/`. Den har ingen runtime-koppling till
referensrepot. En uppdatering av referensrepot påverkar därför inte gamla
konverteringar förrän adaptern uttryckligen regenereras och profilversionen
höjs.

Kanoniska målvärden hämtas från dessa lokala DoD91-snapshots.
Alias beskriver endast hur ett källnamn hittar ett kanoniskt mål. Skada, ABS,
vapengrupp och andra målvärden ska hämtas från målkatalogen, inte dupliceras i
aliasposten.

Profilversionen ingår i idempotensnyckeln. En ändrad profil skapar en ny
konvertering från originalets `bok.json`; en tidigare konverterad fil används
aldrig som källa för nästa version.

## Analys

Analysen går igenom samtliga element och tabellceller i `bok.json`, inte bara
formella statblock. Äldre regelvärden förekommer även i löptext:

```text
En person med Simma 75% (B4) kan med ett lyckat färdighetsslag ...
```

Analysen ska identifiera kandidater inom följande kategorier:

1. färdighetsvärden i procent;
2. färdighetsnamn och färdighetskategorier;
3. vapen, vapenskada och vapenfärdighet;
4. rustning och ABS;
5. KP och andra härledda värden;
6. NPC- och monsterstatblock;
7. regelvärden i tabeller;
8. regelhänvisningar i löptext;
9. notation som endast finns i källsystemet.

Varje kandidat ska peka tillbaka på:

- element-id;
- sida och region;
- textintervall eller tabellcell;
- originaltext;
- identifierad regeltyp;
- föreslagen åtgärd;
- confidence och motivering.

Analysen ska inte ändra text.

## Klassificering och konverteringsregler

### FV-skala

Eftersom användaren uttryckligen anger `--from dod-t100` behöver motorn inte
gissa regelsystem från enskilda tal. Alla värden som analysen med säkerhet har
identifierat som FV konverteras symmetriskt:

```text
FV91 = clamp(round(FV100 / 5), 3, 18)
```

Exempel:

| T100 | DoD91 |
| ---: | ---: |
| 15 | 3 |
| 35 | 7 |
| 50 | 10 |
| 70 | 14 |
| 100 | 18 |

Ett tal konverteras aldrig enbart för att det ligger mellan 1 och 100. Det
måste vara identifierat som ett färdighetsvärde genom statblockstruktur,
etikett, procenttecken eller ett annat dokumenterat mönster.

### Färdigheter

Ordningen är:

1. normalisera källnamnet för uppslag;
2. slå upp exakt alias;
3. verifiera att målet finns i DoD91-katalogen;
4. konvertera FV;
5. skapa konverteringspost.

Omatchade eller tvetydiga färdigheter lämnas oförändrade och får
`needs_review`. Fuzzy-matchning får ge förslag men aldrig applicera en
konvertering.

### Vapen och rustning

Vid säker katalogträff ska motorn använda DoD91-katalogens:

- kanoniska namn;
- vapengrupp eller vapenfärdighet;
- skadevärde;
- eventuell pareringsinformation;
- rustningens ABS.

Generiska namn som `Svärd` eller `Spjut` kräver ett explicit alias när flera
rimliga DoD91-föremål finns. Naturliga vapen och monsterhud ska inte tvingas
in i utrustningskatalogen.

### KP och härledda värden

Härledda värden räknas endast om när alla nödvändiga grundvärden har en säker
tolkning. För vanlig DoD91-KP används:

```text
KP = ceil((FYS + STO) / 2)
```

Odöda, immateriella varelser och andra uttryckliga undantag ska hanteras av
monsterprofil eller lämnas för granskning. En generell formel får inte skriva
över ett regelundantag.

### Löptext

Konverteringen ska ändra minsta möjliga textintervall. Berättande innehåll,
egennamn, handling och miljöbeskrivningar får inte omformuleras.

Exempel:

```text
Simma 75% → Simma FV 15
```

Om `(B4)` saknar en entydig DoD91-motsvarighet ändras inte den delen tyst.
Den markeras separat för granskning även om FV-konverteringen är säker.

## Konverteringsposter

Regelkonvertering är inte OCR-korrektur och ska märkas som en egen typ. Varje
applicerad eller föreslagen ändring lagras exempelvis så här:

```json
{
  "kind": "rules_conversion",
  "element_id": "p001_e04",
  "source": {
    "page": 1,
    "region": "kolumn 1",
    "text": "Simma 75% (B4)"
  },
  "original": "Simma 75%",
  "converted": "Simma FV 15",
  "source_ruleset": "dod-t100",
  "target_ruleset": "dod91",
  "rule": "fv.divide-by-five",
  "profile_version": 1,
  "confidence": 1.0,
  "reason": "Explicit procentvärde kopplat till färdigheten Simma",
  "applied": true,
  "needs_review": false
}
```

Bindande invarianter:

- originalvärdet bevaras alltid;
- ingen ändring utan konverteringspost;
- osäkra förslag har `applied: false`;
- `needs_review` sätts för allt som kräver ett mänskligt beslut;
- rapporten skiljer befintliga OCR-korrektioner från regelkonverteringar.

## Utdataformat

### Konverterad JSON

`bok.konverterad.json` är en kopia av källans kanoniska bok med tillagd
metadata:

```json
{
  "conversion": {
    "source_ruleset": "dod-t100",
    "target_ruleset": "dod91",
    "profile": "dod-t100-to-dod91",
    "profile_version": 1,
    "source_sha256": "...",
    "generated": "...",
    "status": "complete",
    "counts": {
      "applied": 23,
      "needs_review": 0,
      "unchanged": 4
    }
  }
}
```

Tillåtna statusvärden:

| Status | Betydelse |
| --- | --- |
| `analyzed` | Analys klar, ingen konverterad fil publicerad |
| `needs_review` | Konvertering skapad internt men har blockerande beslut |
| `complete` | Alla blockerande beslut lösta; får publiceras |

### Markdown

Markdown genereras från `bok.konverterad.json`, aldrig genom direkta
ersättningar i den befintliga `bok.md`. Det gör JSON-filen kanonisk även för
den konverterade utgåvan.

### Konverteringsrapport

Rapporten ska innehålla:

1. källa, checksumma och profilversion;
2. befintlig granskningsstatus från extraktionen;
3. sammanfattning per regelkategori;
4. alla applicerade konverteringar;
5. alla ej applicerade förslag;
6. alla omatchade regeltermer;
7. publiceringsstatus.

## Idempotens och atomisk skrivning

Idempotensnyckeln är:

```text
sha256(source bok.json) + conversion profile id + profile version
```

Om nyckeln redan har status `complete` gör kommandot inget. `--force` bygger
om från källans `bok.json`.

Alla filer skrivs först som `.part` i målkatalogen och byter namn atomiskt när
de är fullständiga. Ett avbrott får aldrig lämna en fil som ser publicerbar ut.

Publiceringsfiler skrivs endast vid `status: complete`. Vid `needs_review`
finns resultat och rapport enbart i arbetskatalogens konverteringsstate.

## Föreslagen kodstruktur

```text
pipeline/
├── convert_adventure.py       orkestrering och idempotens
├── conversion_analysis.py     kandidatidentifiering
├── conversion_rules.py        profil- och kataloguppslag
├── conversion_records.py      schema och validering
└── export_conversion.py       JSON, Markdown och rapport

system/dod/conversion/
└── dod-t100-to-dod91.json

tests/
├── test_conversion_analysis.py
├── test_conversion_rules.py
├── test_convert_adventure.py
└── fixtures/conversion/
```

`pipeline/__main__.py` får endast det explicita kommandot `konvertera`.
`exportera`, `sammanfoga` och övriga extraktionskommandon ska inte anropa det
automatiskt.

## Felkoder

| Kod | Betydelse |
| ---: | --- |
| 0 | Konvertering komplett eller redan komplett |
| 2 | Felaktiga argument eller ogiltig källa |
| 3 | Analys/konvertering klar men mänsklig granskning krävs |
| 4 | Profil- eller adapterfel |
| 5 | Skriv-/publiceringsfel |

## Tester

### Enhetstester

- FV 50 blir 10 och FV 70 blir 14.
- FV-bandet begränsas till 3–18.
- Ett lågt FV konverteras när `--from dod-t100` är explicit.
- Vanliga tal i löptext konverteras inte utan FV-kontext.
- Färdighetsalias måste peka på en existerande DoD91-färdighet.
- Vapenalias hämtar skada och vapengrupp ur målkatalogen.
- Okänt vapen behåller originalet och får `needs_review`.
- KP räknas korrekt för vanliga varelser.
- FYS 0 och regelundantag skrivs inte över av standardformeln.
- Varje textändring har exakt en konverteringspost.

### Idempotenstester

- Två körningar med samma källa och profil gör ingen extra ändring.
- Ändrad profilversion bygger om från originalet.
- Avbruten skrivning lämnar ingen publicerad halvfil.
- `--force` bygger om men konverterar aldrig den tidigare konverterade filen.

### Integrationstester

Minst två verkliga, färdigrippade äventyr används som manuellt aktiverade
golden-fixturer:

- ett med tydliga procentbaserade färdighetsslag i löptext;
- ett med NPC-statblock, vapen, rustning och monster.

Testerna ska jämföra både konverterad JSON och konverteringsrapport.

## Acceptanskriterier

Implementationen är klar när:

1. användaren kan peka på ett enda `bok.json`;
2. inget annat äventyr läses eller konverteras;
3. källans `bok.json` och befintligt extraktionsstate är byte-identiska efter
   körningen;
4. T100-FV konverteras konsekvent till DoD91;
5. färdigheter, vapen och rustningar verifieras mot DoD91-data;
6. regelreferenser i löptext omfattas av analysen;
7. varje ändring har original, mål, regel, confidence och proveniens;
8. osäkra fall publiceras inte som färdiga;
9. en ren konvertering ger MD, JSON och rapport i `konverterat/dod91/`;
10. omkörning är idempotent;
11. hela den befintliga testsviten samt konverteringstesterna är gröna.

## Avgränsning mot Drakar och Demoner 1991

Ripparen ansvarar för regelkonverteringen. `Drakar och Demoner 1991` får
förutsätta att en publicerad fil från `konverterat/dod91/` redan använder
1991 års regler.

Mottagande repo bör kontrollera:

- `conversion.target_ruleset == "dod91"`;
- `conversion.status == "complete"`;
- `conversion.counts.needs_review == 0`.

`Drakar och Demoner 1991` får därefter strukturera äventyret till sitt eget
scen- och NPC-schema, men ska inte på nytt räkna om FV, KP, vapen eller
rustning.
