# Konverteringsguide: Drakar och Demoner

## DoD 1991 ↔ Mutant

### Attributmappning
| DoD | Mutant | Kommentar |
|-----|--------|-----------|
| STY | STY | Direkt motsvarighet |
| FYS | — | Ingen direkt motsvarighet, fördela till KYL/STY |
| SMI | SMI | Direkt motsvarighet |
| INT | — | Ingen direkt motsvarighet i Mutant |
| PSY | KYL | Ungefärlig motsvarighet |
| KAR | SKP | Ungefärlig motsvarighet |

### Omräkningsformel (DoD → Mutant)
- DoD använder 3-18 (3T6), Mutant använder 2-5
- Formel: `Mutant-värde = Math.round(DoD-värde / 4.5) + 1`
- Eller tabell: 3-6 → 2, 7-10 → 3, 11-14 → 4, 15-18 → 5

### Färdighetsmappning
- DoD FV 1-5 → Mutant 0 (ingen utbildning)
- DoD FV 6-10 → Mutant 1
- DoD FV 11-15 → Mutant 2
- DoD FV 16-20 → Mutant 3

### Konceptmappning
| DoD-koncept | Mutant-motsvarighet |
|-------------|---------------------|
| Magi | Mutationer |
| Ras (Alv, Dvärg) | Mutanttyp |
| Guild/Fraktion | Arketyp/Klan |
| Guld/Silver | Skrot/Vatten |
| Skyddsvärde (SV) | Skydd |

## DoD 1991 ↔ DoD 2023

### Attributmappning
| DoD 1991 | DoD 2023 | Kommentar |
|----------|----------|-----------|
| STY | Styrka | Samma namn, nytt system (Year Zero) |
| FYS | Fysik | Samma namn |
| SMI | Smidighet | Samma namn |
| INT | Intelligens | Samma namn |
| PSY | Vilja | Namnbyte |
| KAR | Karisma | Samma namn |

### Systemskillnader
- 1991: BRP (d100-baserat), 2023: Year Zero Engine (d6-pooler)
- 1991: FV som procenttal, 2023: Färdighetspoäng (antal tärningar)
- Omräkning: FV / 5 ≈ antal tärningar i 2023
