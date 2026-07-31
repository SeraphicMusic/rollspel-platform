# Konverteringsrapport

## Källa och profil

- Källa: `/Users/kalle.windefalk/Claude/private/RPG Ripparen/arbete/DOD-AVE-den-nedbrunna-fatburen/export/bok.json`
- SHA-256: `6981158375499c96b322ef9b70a454580c12eb196f5f5d5a9cf6893cf5e78471`
- Profil: `dod-t100-to-dod91` version 7
- Befintliga granskningsposter från extraktionen: 2

## Sammanfattning

- Applicerade regelkonverteringar: 76
- Blockerande konverteringsbeslut: 0
- Noteringar utan blockering: 5
- Ej applicerade kandidater: 5
- Genomsökta element: 156

| Regelkategori | Applicerade | Behöver granskas |
| --- | ---: | ---: |
| armor | 6 | 0 |
| skill_value | 34 | 0 |
| unmatched_term | 0 | 5 |
| weapon | 18 | 0 |
| weapon_skill | 18 | 0 |

## Applicerade konverteringar

- Sida 7, `p007_e10`: `Stor sköld (85%` → `Rundsköld, stor (FV 17` — Procentvärde på T100-skalan inuti parentes efter 'Stor sköld' räknas om till FV; sköldnamnet normaliseras mot katalogen
- Sida 7, `p007_e10`: `abs 16` → `BV 11` — DoD91-sköldar anges med brytvärde, inte absorption; katalogens BV för Rundsköld, stor ersätter källans 'abs 16'
- Sida 7, `p007_e10`: `Rida 70` → `Rida 14` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e10`: `Heraldik 50` → `Heraldik 10` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e10`: `Simma 60` → `Simma 12` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e10`: `Upptäcka fara 50` → `Upptäcka fara 10` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e10`: `Första hjälpen 50` → `Första hjälpen 10` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e10`: `Stridsyxa 85%` → `Stridsyxa FV 17` — Angreppsvärdet är bärarens färdighet med vapnet och räknas om till FV
- Sida 7, `p007_e10`: `{'name': 'Stridsyxa', 'attack': '85%', 'damage': '1T10+2', 'bv': 11}` → `{'name': 'Stridsyxa', 'attack': 17, 'damage': '1T10+2', 'bv': 11, 'length': 0, 'price': 450, 'styKrav': 11, 'type': 'melee', 'weaponGroup': 'enhandsyxor', 'weight': 4}` — Katalogen fyller i de DoD91-värden boken inte anger; tryckta värden behålls
- Sida 7, `p007_e10`: `Dolk 70%` → `Dolk FV 14` — Angreppsvärdet är bärarens färdighet med vapnet och räknas om till FV
- Sida 7, `p007_e10`: `{'name': 'Dolk', 'attack': '70%', 'damage': '1T4+1', 'bv': 9}` → `{'name': 'Dolk', 'attack': 14, 'damage': '1T4+1', 'bv': 9, 'length': 0, 'price': 70, 'styKrav': 1, 'type': 'melee', 'weaponGroup': 'dolkar', 'weight': 0.5}` — Katalogen fyller i de DoD91-värden boken inte anger; tryckta värden behålls
- Sida 7, `p007_e10`: `Kastspjut 70%` → `Kastspjut FV 14` — Angreppsvärdet är bärarens färdighet med vapnet och räknas om till FV
- Sida 7, `p007_e10`: `{'name': 'Kastspjut', 'attack': '70%', 'damage': '1T6+1', 'rackvidd': '18 rutor'}` → `{'name': 'Kastspjut', 'attack': 14, 'damage': '1T6+1', 'rackvidd': '18 rutor', 'price': 120, 'styKrav': 11, 'type': 'thrown', 'weaponGroup': 'kastvapen', 'weight': 1}` — Katalogen fyller i de DoD91-värden boken inte anger; tryckta värden behålls
- Sida 7, `p007_e13`: `Stor sköld (95%` → `Rundsköld, stor (FV 18` — Procentvärde på T100-skalan inuti parentes efter 'Stor sköld' räknas om till FV; sköldnamnet normaliseras mot katalogen
- Sida 7, `p007_e13`: `abs 16` → `BV 11` — DoD91-sköldar anges med brytvärde, inte absorption; katalogens BV för Rundsköld, stor ersätter källans 'abs 16'
- Sida 7, `p007_e13`: `Rida 60` → `Rida 12` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e13`: `Simma 60` → `Simma 12` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e13`: `Upptäcka fara 50` → `Upptäcka fara 10` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e13`: `Första hjälpen 50` → `Första hjälpen 10` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e13`: `Bastardsvärd 85%` → `Bastardsvärd FV 17` — Angreppsvärdet är bärarens färdighet med vapnet och räknas om till FV
- Sida 7, `p007_e13`: `{'name': 'Slagsvärd', 'attack': '85%', 'damage': '1T10+1', 'bv': 13}` → `{'name': 'Bastardsvärd', 'attack': 17, 'damage': '1T10+1', 'bv': 13, 'length': 0, 'price': 2500, 'styKrav': 17, 'type': 'melee', 'weaponGroup': 'enhandssward', 'weight': 5.5}` — Katalogen fyller i de DoD91-värden boken inte anger; tryckta värden behålls
- Sida 7, `p007_e13`: `Dolk 75%` → `Dolk FV 15` — Angreppsvärdet är bärarens färdighet med vapnet och räknas om till FV
- Sida 7, `p007_e13`: `{'name': 'Dolk', 'attack': '75%', 'damage': '1T4+1', 'bv': 9}` → `{'name': 'Dolk', 'attack': 15, 'damage': '1T4+1', 'bv': 9, 'length': 0, 'price': 70, 'styKrav': 1, 'type': 'melee', 'weaponGroup': 'dolkar', 'weight': 0.5}` — Katalogen fyller i de DoD91-värden boken inte anger; tryckta värden behålls
- Sida 7, `p007_e13`: `Kastspjut 70%` → `Kastspjut FV 14` — Angreppsvärdet är bärarens färdighet med vapnet och räknas om till FV
- Sida 7, `p007_e13`: `{'name': 'Kastspjut', 'attack': '70%', 'damage': '1T6+1', 'rackvidd': '15 rutor'}` → `{'name': 'Kastspjut', 'attack': 14, 'damage': '1T6+1', 'rackvidd': '15 rutor', 'price': 120, 'styKrav': 11, 'type': 'thrown', 'weaponGroup': 'kastvapen', 'weight': 1}` — Katalogen fyller i de DoD91-värden boken inte anger; tryckta värden behålls
- Sida 7, `p007_e16`: `Stor sköld (85%` → `Rundsköld, stor (FV 17` — Procentvärde på T100-skalan inuti parentes efter 'Stor sköld' räknas om till FV; sköldnamnet normaliseras mot katalogen
- Sida 7, `p007_e16`: `abs 16` → `BV 11` — DoD91-sköldar anges med brytvärde, inte absorption; katalogens BV för Rundsköld, stor ersätter källans 'abs 16'
- Sida 7, `p007_e16`: `Rida 60` → `Rida 12` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e16`: `Heraldik 80` → `Heraldik 16` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e16`: `Simma 60` → `Simma 12` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e16`: `Upptäcka fara 50` → `Upptäcka fara 10` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e16`: `Första hjälpen 50` → `Första hjälpen 10` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e16`: `Spela och sjunga 75` → `Spela stränginstrument 15, Sjunga 15` — Den sammanslagna källfärdigheten delas upp i DoD91:s separata färdigheter
- Sida 7, `p007_e16`: `Bredsvärd 80%` → `Bredsvärd FV 16` — Angreppsvärdet är bärarens färdighet med vapnet och räknas om till FV
- Sida 7, `p007_e16`: `{'name': 'Bredsvärd', 'attack': '80%', 'damage': '1T8+1', 'bv': 15}` → `{'name': 'Bredsvärd', 'attack': 16, 'damage': '1T8+1', 'bv': 15, 'length': 0, 'price': 1000, 'styKrav': 13, 'type': 'melee', 'weaponGroup': 'enhandssward', 'weight': 4.5}` — Katalogen fyller i de DoD91-värden boken inte anger; tryckta värden behålls
- Sida 7, `p007_e16`: `Dolk 75%` → `Dolk FV 15` — Angreppsvärdet är bärarens färdighet med vapnet och räknas om till FV
- Sida 7, `p007_e16`: `{'name': 'Dolk', 'attack': '75%', 'damage': '1T4+1', 'bv': 9}` → `{'name': 'Dolk', 'attack': 15, 'damage': '1T4+1', 'bv': 9, 'length': 0, 'price': 70, 'styKrav': 1, 'type': 'melee', 'weaponGroup': 'dolkar', 'weight': 0.5}` — Katalogen fyller i de DoD91-värden boken inte anger; tryckta värden behålls
- Sida 7, `p007_e16`: `Kastspjut 60%` → `Kastspjut FV 12` — Angreppsvärdet är bärarens färdighet med vapnet och räknas om till FV
- Sida 7, `p007_e16`: `{'name': 'Kastspjut', 'attack': '60%', 'damage': '1T6+1', 'rackvidd': '12 rutor'}` → `{'name': 'Kastspjut', 'attack': 12, 'damage': '1T6+1', 'rackvidd': '12 rutor', 'price': 120, 'styKrav': 11, 'type': 'thrown', 'weaponGroup': 'kastvapen', 'weight': 1}` — Katalogen fyller i de DoD91-värden boken inte anger; tryckta värden behålls
- Sida 7, `p007_e19`: `Stor sköld (95%` → `Rundsköld, stor (FV 18` — Procentvärde på T100-skalan inuti parentes efter 'Stor sköld' räknas om till FV; sköldnamnet normaliseras mot katalogen
- Sida 7, `p007_e19`: `abs 16` → `BV 11` — DoD91-sköldar anges med brytvärde, inte absorption; katalogens BV för Rundsköld, stor ersätter källans 'abs 16'
- Sida 7, `p007_e19`: `Rida 70` → `Rida 14` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e19`: `Heraldik 50` → `Heraldik 10` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e19`: `Simma 60` → `Simma 12` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e19`: `Upptäcka fara 50` → `Upptäcka fara 10` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e19`: `Första hjälpen 50` → `Första hjälpen 10` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e19`: `Bastardsvärd 80%` → `Bastardsvärd FV 16` — Angreppsvärdet är bärarens färdighet med vapnet och räknas om till FV
- Sida 7, `p007_e19`: `{'name': 'Slagsvärd', 'attack': '80%', 'damage': '1T10+1', 'bv': 13}` → `{'name': 'Bastardsvärd', 'attack': 16, 'damage': '1T10+1', 'bv': 13, 'length': 0, 'price': 2500, 'styKrav': 17, 'type': 'melee', 'weaponGroup': 'enhandssward', 'weight': 5.5}` — Katalogen fyller i de DoD91-värden boken inte anger; tryckta värden behålls
- Sida 7, `p007_e19`: `Dolk 75%` → `Dolk FV 15` — Angreppsvärdet är bärarens färdighet med vapnet och räknas om till FV
- Sida 7, `p007_e19`: `{'name': 'Dolk', 'attack': '75%', 'damage': '1T4+1', 'bv': 9}` → `{'name': 'Dolk', 'attack': 15, 'damage': '1T4+1', 'bv': 9, 'length': 0, 'price': 70, 'styKrav': 1, 'type': 'melee', 'weaponGroup': 'dolkar', 'weight': 0.5}` — Katalogen fyller i de DoD91-värden boken inte anger; tryckta värden behålls
- Sida 7, `p007_e19`: `Kortbåge 60%` → `Kortbåge FV 12` — Angreppsvärdet är bärarens färdighet med vapnet och räknas om till FV
- Sida 7, `p007_e19`: `{'name': 'Kortbåge', 'attack': '60%', 'damage': '1T6+1', 'rackvidd': '135 m'}` → `{'name': 'Kortbåge', 'attack': 12, 'damage': '1T6+1', 'rackvidd': '135 m', 'price': 400, 'styKrav': 17, 'type': 'ranged', 'weaponGroup': 'bagar', 'weight': 2}` — Katalogen fyller i de DoD91-värden boken inte anger; tryckta värden behålls
- Sida 7, `p007_e22`: `Stor sköld (95%` → `Rundsköld, stor (FV 18` — Procentvärde på T100-skalan inuti parentes efter 'Stor sköld' räknas om till FV; sköldnamnet normaliseras mot katalogen
- Sida 7, `p007_e22`: `abs 16` → `BV 11` — DoD91-sköldar anges med brytvärde, inte absorption; katalogens BV för Rundsköld, stor ersätter källans 'abs 16'
- Sida 7, `p007_e22`: `Första hjälpen 60` → `Första hjälpen 12` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e22`: `Sjunga 50` → `Sjunga 10` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e22`: `Rida 70` → `Rida 14` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e22`: `Simma 75` → `Simma 15` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e22`: `Stridsyxa 95%` → `Stridsyxa FV 18` — Angreppsvärdet är bärarens färdighet med vapnet och räknas om till FV
- Sida 7, `p007_e22`: `{'name': 'Stridsyxa', 'attack': '95%', 'damage': '1T10+2', 'bv': 11}` → `{'name': 'Stridsyxa', 'attack': 18, 'damage': '1T10+2', 'bv': 11, 'length': 0, 'price': 450, 'styKrav': 11, 'type': 'melee', 'weaponGroup': 'enhandsyxor', 'weight': 4}` — Katalogen fyller i de DoD91-värden boken inte anger; tryckta värden behålls
- Sida 7, `p007_e22`: `Dolk 95%` → `Dolk FV 18` — Angreppsvärdet är bärarens färdighet med vapnet och räknas om till FV
- Sida 7, `p007_e22`: `{'name': 'Dolk', 'attack': '95%', 'damage': '1T4+1', 'bv': 9}` → `{'name': 'Dolk', 'attack': 18, 'damage': '1T4+1', 'bv': 9, 'length': 0, 'price': 70, 'styKrav': 1, 'type': 'melee', 'weaponGroup': 'dolkar', 'weight': 0.5}` — Katalogen fyller i de DoD91-värden boken inte anger; tryckta värden behålls
- Sida 7, `p007_e22`: `Kastyxa 95%` → `Kastyxa FV 18` — Angreppsvärdet är bärarens färdighet med vapnet och räknas om till FV
- Sida 7, `p007_e22`: `{'name': 'Kastyxa', 'attack': '95%', 'damage': '1T6+2', 'rackvidd': '17 rutor'}` → `{'name': 'Kastyxa', 'attack': 18, 'damage': '1T6+2', 'rackvidd': '17 rutor', 'price': 90, 'styKrav': 9, 'type': 'thrown', 'weaponGroup': 'kastvapen', 'weight': 3}` — Katalogen fyller i de DoD91-värden boken inte anger; tryckta värden behålls
- Sida 7, `p007_e24`: `Stor sköld (75%` → `Rundsköld, stor (FV 15` — Procentvärde på T100-skalan inuti parentes efter 'Stor sköld' räknas om till FV; sköldnamnet normaliseras mot katalogen
- Sida 7, `p007_e24`: `abs 16` → `BV 11` — DoD91-sköldar anges med brytvärde, inte absorption; katalogens BV för Rundsköld, stor ersätter källans 'abs 16'
- Sida 7, `p007_e24`: `Rida 60` → `Rida 12` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e24`: `Simma 60` → `Simma 12` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e24`: `Upptäcka fara 50` → `Upptäcka fara 10` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e24`: `Första hjälpen 50` → `Första hjälpen 10` — Strukturerat FV och verifierad DoD91-färdigheten
- Sida 7, `p007_e24`: `Bastardsvärd 75%` → `Bastardsvärd FV 15` — Angreppsvärdet är bärarens färdighet med vapnet och räknas om till FV
- Sida 7, `p007_e24`: `{'name': 'Slagsvärd', 'attack': '75%', 'damage': '1T10+1', 'bv': 13}` → `{'name': 'Bastardsvärd', 'attack': 15, 'damage': '1T10+1', 'bv': 13, 'length': 0, 'price': 2500, 'styKrav': 17, 'type': 'melee', 'weaponGroup': 'enhandssward', 'weight': 5.5}` — Katalogen fyller i de DoD91-värden boken inte anger; tryckta värden behålls
- Sida 7, `p007_e24`: `Dolk 75%` → `Dolk FV 15` — Angreppsvärdet är bärarens färdighet med vapnet och räknas om till FV
- Sida 7, `p007_e24`: `{'name': 'Dolk', 'attack': '75%', 'damage': '1T4+1', 'bv': 9}` → `{'name': 'Dolk', 'attack': 15, 'damage': '1T4+1', 'bv': 9, 'length': 0, 'price': 70, 'styKrav': 1, 'type': 'melee', 'weaponGroup': 'dolkar', 'weight': 0.5}` — Katalogen fyller i de DoD91-värden boken inte anger; tryckta värden behålls
- Sida 7, `p007_e24`: `Kastspjut 60%` → `Kastspjut FV 12` — Angreppsvärdet är bärarens färdighet med vapnet och räknas om till FV
- Sida 7, `p007_e24`: `{'name': 'Kastspjut', 'attack': '60%', 'damage': '1T6+1', 'rackvidd': '14 rutor'}` → `{'name': 'Kastspjut', 'attack': 12, 'damage': '1T6+1', 'rackvidd': '14 rutor', 'price': 120, 'styKrav': 11, 'type': 'thrown', 'weaponGroup': 'kastvapen', 'weight': 1}` — Katalogen fyller i de DoD91-värden boken inte anger; tryckta värden behålls

## Noteringar — avgjort av profilen

Redovisas för spårbarhet men stoppar inte publicering: utfallet följer en regel som redan är fastställd.

- Sida 7, `p007_e10` [weapon.printed-value-differs]: `Stridsyxa damage: 1T10+2` — Trycket anger damage '1T10+2' där DoD91-katalogen har '1T8+2'. Tryckta spelvärden rättas inte automatiskt (Regel 8a) — behållet som det står, avvikelsen flaggas.
- Sida 7, `p007_e13` [weapon.printed-value-differs]: `Bastardsvärd bv: 13` — Trycket anger bv 13 där DoD91-katalogen har 15. Tryckta spelvärden rättas inte automatiskt (Regel 8a) — behållet som det står, avvikelsen flaggas.
- Sida 7, `p007_e19` [weapon.printed-value-differs]: `Bastardsvärd bv: 13` — Trycket anger bv 13 där DoD91-katalogen har 15. Tryckta spelvärden rättas inte automatiskt (Regel 8a) — behållet som det står, avvikelsen flaggas.
- Sida 7, `p007_e22` [weapon.printed-value-differs]: `Stridsyxa damage: 1T10+2` — Trycket anger damage '1T10+2' där DoD91-katalogen har '1T8+2'. Tryckta spelvärden rättas inte automatiskt (Regel 8a) — behållet som det står, avvikelsen flaggas.
- Sida 7, `p007_e24` [weapon.printed-value-differs]: `Bastardsvärd bv: 13` — Trycket anger bv 13 där DoD91-katalogen har 15. Tryckta spelvärden rättas inte automatiskt (Regel 8a) — behållet som det står, avvikelsen flaggas.

## Ej applicerade förslag och omatchade termer

Inga.

## Publiceringsstatus

- Status: `complete`
- Konverteringen saknar blockerande beslut.
- Publicerad: `/Users/kalle.windefalk/Claude/private/RPG Ripparen/konverterat/dod91/DOD-AVE-den-nedbrunna-fatburen.md`
- Publicerad: `/Users/kalle.windefalk/Claude/private/RPG Ripparen/konverterat/dod91/DOD-AVE-den-nedbrunna-fatburen.json`
- Publicerad: `/Users/kalle.windefalk/Claude/private/RPG Ripparen/konverterat/dod91/DOD-AVE-den-nedbrunna-fatburen.konverteringsrapport.md`
