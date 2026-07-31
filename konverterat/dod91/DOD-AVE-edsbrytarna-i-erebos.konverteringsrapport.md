# Konverteringsrapport

## Källa och profil

- Källa: `/Users/kalle.windefalk/Claude/private/RPG Ripparen/arbete/DOD-AVE-edsbrytarna-i-erebos/export/bok.json`
- SHA-256: `29e1c56d7f7b1e27282b51608bba0333a2468e0ce193008ea02b4ef853469ebb`
- Profil: `dod-t100-to-dod91` version 4
- Befintliga granskningsposter från extraktionen: 35

## Sammanfattning

- Applicerade regelkonverteringar: 29
- Blockerande konverteringsbeslut: 0
- Ej applicerade kandidater: 1
- Genomsökta element: 96

| Regelkategori | Applicerade | Behöver granskas |
| --- | ---: | ---: |
| derived_value | 2 | 0 |
| rule_reference | 0 | 0 |
| skill_value | 22 | 0 |
| weapon | 1 | 0 |
| weapon_skill | 4 | 0 |

## Applicerade konverteringar

- Sida 1, `p001_e04`: `Simma 75% 
(B4)` → `Simma FV 15 (B3)` — Explicit procentvärde kopplat till färdigheten Simma
- Sida 3, `p003_e05`: `CL 90%+ (FV B5) i Erebosiska` → `Språkkunskap FV 10` — Erebosiska är modersmålet och talas flytande; den gamla särskilda modersmålschansen ersätts av husregelns Språkkunskap FV 10
- Sida 4, `p004_e01`: `Steinars PSY x 5%` → `Steinars aktuella PSY` — T100-avdraget attribut × 5 procentenheter motsvarar attributets aktuella värde som FV-avdrag i DoD91
- Sida 6, `p006_e04`: `–20 på 
slaget` → `–4 på slaget` — Modifikatorn är angiven i T100-procentenheter och är omöjlig på FV-skalan (maximum 18); den räknas om till FV-steg
- Sida 6, `p006_e05`: `på Läsa/ 
Skriva Zorakiska, Kardiska eller Trakoriska` → `på Språkkunskap` — Uppräkningen av enskilda språkfärdigheter ersätts av DoD91-husregelns samlade Språkkunskap
- Sida 6, `p006_e05`: `50% CL (FV B3)` → `FV 10 (B2)` — T100-tröskeln uttrycks som DoD91-FV; B-nivån räknas om ur det konverterade FV:t
- Sida 9, `p009_e05`: `Köpslå 80%` → `Köpslå 16` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 9, `p009_e05`: `Övertala 70%` → `Övertala 14` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 9, `p009_e05`: `Värdesätta 76%` → `Värdera 15` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 9, `p009_e05`: `Tala Zorakiska 50%` → `Språkkunskap 10` — Strukturerat FV och verifierad DoD91-den samlade språkfärdigheten
- Sida 9, `p009_e05`: `Tala Kardiska 50%` → `Språkkunskap 10` — Strukturerat FV och verifierad DoD91-den samlade språkfärdigheten
- Sida 9, `p009_e05`: `Tala Zorakiska 50% + Tala Kardiska 50%` → `Språkkunskap 10` — 2 källfärdigheter hör till samma DoD91-färdighet Språkkunskap; högsta nivån behålls
- Sida 9, `p009_e08`: `Dolk 20%` → `Dolk 4` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 9, `p009_e08`: `Köpslå 70%` → `Köpslå 14` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 9, `p009_e08`: `Övertala 50%` → `Övertala 10` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 9, `p009_e11`: `Dolk 20%` → `Dolk 4` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 9, `p009_e11`: `Övertala 80%` → `Övertala 16` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 9, `p009_e13`: `korstvärd` → `kortsvärd` — Explicit källalias normaliserat till kanoniskt DoD91-vapen
- Sida 9, `p009_e14`: `Dolk 87%` → `Dolk 17` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 9, `p009_e14`: `Kortsvärd 77%` → `Enhandssvärd 15` — Strukturerat FV och verifierad DoD91-vapengruppen
- Sida 9, `p009_e14`: `Kastkniv 67%` → `Kastvapen 13` — Strukturerat FV och verifierad DoD91-vapengruppen
- Sida 9, `p009_e14`: `Smyga 67%` → `Smyga 13` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 9, `p009_e14`: `Gömma sig 77%` → `Gömma sig 15` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 9, `p009_e14`: `Upptäcka fara 84%` → `Upptäcka fara 17` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 9, `p009_e15`: `Bredsvärd 80%` → `Enhandssvärd 16` — Strukturerat FV och verifierad DoD91-vapengruppen
- Sida 9, `p009_e15`: `Gatuslagsmål 80%` → `Slagsmål 16` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 9, `p009_e15`: `Korstvärd 70%` → `Enhandssvärd 14` — Strukturerat FV och verifierad DoD91-vapengruppen
- Sida 9, `p009_e15`: `Upptäcka fara 60%` → `Upptäcka fara 12` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 9, `p009_e15`: `Bredsvärd 80% + Korstvärd 70%` → `Enhandssvärd 16` — 2 källfärdigheter hör till samma DoD91-färdighet Enhandssvärd; högsta nivån behålls och FV 14 går upp i den utan egen rad

## Ej applicerade förslag och omatchade termer

- Sida 4, `p004_e01` [rules-reference.target-native]: `motståndstabellen` — Regelhänvisningen finns i DoD91 och behålls oförändrad

## Publiceringsstatus

- Status: `complete`
- Konverteringen saknar blockerande beslut.
- Publicerad: `/Users/kalle.windefalk/Claude/private/RPG Ripparen/konverterat/dod91/DOD-AVE-edsbrytarna-i-erebos.md`
- Publicerad: `/Users/kalle.windefalk/Claude/private/RPG Ripparen/konverterat/dod91/DOD-AVE-edsbrytarna-i-erebos.json`
- Publicerad: `/Users/kalle.windefalk/Claude/private/RPG Ripparen/konverterat/dod91/DOD-AVE-edsbrytarna-i-erebos.konverteringsrapport.md`
