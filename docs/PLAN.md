# Fas 3 — Implementeringsplan

*Prioriterad plan mot målarkitekturen i [ARKITEKTUR.md](ARKITEKTUR.md).*

## Etapp 1 — MVP (grundläggande, implementeras nu)

| # | Del | Beroende | Acceptanskriterier |
| --- | --- | --- | --- |
| 1.1 | `pipeline/manifest.py` — manifest + state-maskin, atomisk skrivning | — | Manifest överlever avbrott; omkörning ändrar inget för färdiga sidor |
| 1.2 | `pipeline/analyze.py` — dokumenttyps-detektering per sida + boilerplate | 1.1 | Spindelkonungen-PDF:en klassas 27/28 `image_with_stub_text`, vattenstämpeln identifieras; syntetisk text-PDF klassas `digital_text` |
| 1.3 | `pipeline/render.py` — PNG-rendering, idempotent/atomisk | 1.1 | Avbruten körning lämnar ingen halv PNG; omkörning hoppar över färdiga sidor |
| 1.4 | `pipeline/extract_text.py` — textlager med bbox, kolumnsortering, sidhuvud/-fot-detektering | 1.2 | Tvåspaltsida ger vänster-före-höger-läsordning; upprepad topp-/bottenrad klassas `page_artifact` |
| 1.5 | `system/` -adaptrar: `dod` (1991) + `mutant2089`, genererade via `scripts/bygg_adapter.py` | ref-repona | Lexikon ≥ 500 termer (DoD), tärningsgrammatik, attributintervall, formler, detection-fingeravtryck; gamla `mutant`-configen (År Noll) ersätts |
| 1.6 | `pipeline/detect_system.py` — fingeravtrycksidentifiering | 1.5 | Spindelkonungen → `dod` med confidence > 0.7 på filnamn+termstatistik; `--system` överstyrning fungerar |
| 1.7 | `pipeline/validate.py` + `corrections.py` — tärnings-, lexikon-, attribut-, formel-, statblock- och strukturvalidering med korrektionsposter | 1.5 | `ITG`→`1T6` föreslås med orsak; tvetydiga fall får `applied:false` + `needs_review`; original alltid bevarat |
| 1.8 | `pipeline/jobs.py` — jobblista för transkription/korrektur | 1.1–1.4 | Endast otranskriberade sidor listas, med rätt filsökvägar och adapterkontext |
| 1.9 | `pipeline/merge.py`, `report.py`, `export_md.py`, `export_csv.py`, `export_docx.py` | 1.7 | Kanonisk `bok.json` + läsbar `bok.md` + `granskningsrapport.md` + DOCX via befintlig `create-docx.js`; CSV per tabell |
| 1.10 | Tester (`tests/`, stdlib `unittest`) med syntetiska PDF-fixturer + Spindelkonungen-integrationstest | allt | `python3 -m unittest` grönt; fixturer genereras deterministiskt av testkoden |
| 1.11 | Skill-uppdatering: `extrahera` arbetar mot pipelinen (jobb → transkript → validering), agentkontrakt kräver korrektionsposter; relativa sökvägar | 1.8 | Inga Windows-sökvägar kvar; agenterna skriver `page_NNN.review/<agent>.json` |
| 1.12 | Dokumentation: README (installation, körning, nytt system), uppdaterad CLAUDE.md | allt | Nytt system kan läggas till utan kodändring enligt guiden |

## Etapp 2 — Förbättrad version

- TOC-/indexextraktion till strukturerade poster med sidhänvisningar.
- Korsreferensvalidering ("se sidan 14" — finns målet?).
- Text som flödar över sidgränser (menings-/styckekontinuitet vid sammanfogning).
- Fuzzy-matchning (Levenshtein ≤ 2) ovanpå förväxlingsgeneratorn i lexikonvalideringen.
- Per-region-transkription: begär om-transkription av enskild bbox i högre DPI (forensik).
- Kapiteluppdelad export + kapitelvis Markdown.
- `korrekturlas`-skillen helt integrerad med pipelinens state (återupptagbar korrektur).

## Etapp 3 — Avancerad version

- API-baserad batchtranskription (Anthropic Batches API) som alternativ till skill-flödet,
  med tokenbudget och kostnadslogg per bok.
- Granskningsgränssnitt (HTML-rapport med sida-vid-sida PNG + text + beslutsknappar → korrektionsposter).
- Utgåve-detektering inom system (DoD 1984 vs 1991 vs 2023) på statistik över statblockformat.
- Träningsloop: bekräftade manuella rättningar matas tillbaka in i adapterns aliaslistor.

## Tekniska risker

| Risk | Hantering |
| --- | --- |
| Python 3.9 (systemversion) — modern syntax otillgänglig | Koden skrivs 3.9-kompatibel (typing.Optional, inga `match`) |
| Endast PyMuPDF som beroende — ingen jsonschema/pytest | Egen minimal schemavalidator; stdlib `unittest` |
| Vision-transkriptens kvalitet varierar | Schema-validering vid inbokning; trasig output → sidan förblir i jobb-listan |
| Lexikon-autorättning överkorrigerar | Rättning kräver entydig kandidat + confidence ≥ 0.9; annars endast flagga |
| Referensrepona ändras/flyttas | Adaptrar är genererade *snapshots* i `system/`; generatorn är omkörbar med `--ref`-sökväg |
| Stora böcker (300+ sidor) | Allt är per sida och idempotent; ingen global batchgräns |

## Teststrategi

1. **Syntetiska fixturer** (genereras med PyMuPDF i testerna): ren text-PDF, bild-PDF
   (renderad text → bild), stub-text-PDF (vattenstämpel över bild), blandad PDF, tvåspalts-PDF.
2. **Enhetstester:** tärningsgrammatik + förväxlingsvarianter (`ITG`→`1T6`, `2I6`→`2T6`,
   `1T2O`→`1T20`), lexikonrättning (entydig vs tvetydig), attribut-/formelvalidering
   (DoD KP-formel, Mutant GCL-delbarhet), statblock-schema, manifest-statemaskin,
   korrektionspostens invarianter (original bevaras, tyst rättning omöjlig).
3. **Idempotenstester:** kör analysera+rendera två gånger — andra körningen gör noll arbete;
   avbryt mitt i (simulerad `.part`-fil) — omkörning reparerar.
4. **Integrationstest (riktig data):** Spindelkonungen-PDF:ens triage + systemdetektering.
5. **Golden-tester för adaptrar** (Mutant 2089-mönstret): kända fel→rätt-par ur
   referensreponas beslutsloggar får inte regrediera.
