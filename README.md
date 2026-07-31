# RPG Ripparen — extrahering av text ur inskannade rollspelsböcker

Deterministisk pipeline + Claude-som-vision-modell för att göra korrekta,
strukturerade och spårbara textversioner av svenska rollspelsböcker
(Drakar och Demoner, Mutant 2089 m.fl.).

Bakgrund och design: [docs/ANALYS.md](docs/ANALYS.md) →
[docs/ARKITEKTUR.md](docs/ARKITEKTUR.md) → [docs/PLAN.md](docs/PLAN.md).

## Installation

Krav: Python 3.9+.

```bash
python3 -m pip install --user pymupdf
```

## Körning

Allt state ligger i `arbete/<bok-slug>/` (manifest, PNG:er, transkript, export).
Varje steg är idempotent — avbryt när som helst och kör samma kommando igen;
färdiga sidor körs aldrig om.

```bash
# 1. Analysera: dokumenttyp per sida + systemidentifiering
python3 -m pipeline analysera "böcker/Min Bok.pdf"            # autodetektering
python3 -m pipeline analysera "böcker/Min Bok.pdf" --system dod

# 2. Rendera skannade sidor till PNG + extrahera ev. textlager
python3 -m pipeline rendera "böcker/Min Bok.pdf" --workdir "arbete/min-bok"
python3 -m pipeline extrahera-text "böcker/Min Bok.pdf" --workdir "arbete/min-bok"

# 3. Transkription (körs i Claude Code): /extrahera driver loopen
python3 -m pipeline jobb --workdir "arbete/min-bok"     # vad väntar?
python3 -m pipeline bokfor --workdir "arbete/min-bok"   # bokför inkomna transkript

# 4. Validera mot systemadaptern (spårbara OCR-rättningar)
python3 -m pipeline validera --workdir "arbete/min-bok"

# 5a. Förbesiktning: deterministiska korrekturkandidater (ingen LLM)
python3 -m pipeline radboxar "<pdf>" --workdir "arbete/min-bok"   # mät radboxar (ger source.bbox)
python3 -m pipeline forbesikta --workdir "arbete/min-bok"

# 5b. Korrektur med agent-team (körs i Claude Code): /korrekturläs

# 6. Sammanfoga, rapportera, exportera
python3 -m pipeline sammanfoga --workdir "arbete/min-bok"
python3 -m pipeline rapport   --workdir "arbete/min-bok"
python3 -m pipeline exportera --workdir "arbete/min-bok" --format alla

# Översikt när som helst
python3 -m pipeline status --workdir "arbete/min-bok"
```

I Claude Code räcker det med `/extrahera path="böcker/Min Bok.pdf"` — skillen
kör stegen ovan och agerar vision-modell i transkriptionssteget.

### Explicit konvertering till DoD91

Ett färdigrippat Drakar och Demoner-äventyr kan konverteras separat. Kommandot
läser endast den angivna `bok.json` och ändrar aldrig extraktionskällan:

```bash
python3 -m pipeline konvertera \
  --source "arbete/min-bok/export/bok.json" \
  --from dod-t100 \
  --to dod91
```

Internt state hamnar i `arbete/<slug>/konvertering/dod91/`. En konvertering
utan blockerande beslut publiceras under `konverterat/dod91/`; annars finns
resultatet endast i statekatalogen och kommandot avslutas med kod 3.
`--dry-run` skriver bara manifest, analys och rapport. DoD91-katalogerna
regenereras uttryckligen med adapterkommandot nedan och läses enbart från
`system/dod/reference/dod91/` vid konvertering.

## Output (i `arbete/<slug>/export/`)

| Fil | Innehåll |
| --- | --- |
| `bok.json` | Kanoniskt format: alla element med proveniens (sida, region, metod), confidence och korrektionsposter |
| `bok.md` | Läsbar Markdown (artefakter som sidhuvuden/vattenstämplar bortfiltrerade) |
| `tabeller/*.csv` | En CSV per extraherad tabell |
| `granskningsrapport.md` | Alla osäkra element, ej applicerade förslag och applicerade korrektioner |

## Spårbarhet

Ingen text ändras tyst. Varje rättning är en korrektionspost:

```json
{"original": "ITG", "corrected": "1T6", "applied": true, "confidence": 0.94,
 "reason": "Tärningsnotation: 2 teckensubstitution(er) ger giltig notation 1T6",
 "source": "validator:dice", "timestamp": "..."}
```

Rättningar appliceras bara vid entydig kandidat och confidence ≥ 0.9 — annars
flaggas elementet (`needs_review`) och hamnar i granskningsrapporten.

## Regelsystem

Adaptrar ligger i `system/<id>/` (ren data — ingen kod behöver ändras):

```
system/dod/           # Drakar och Demoner 1991 (även 1984-äventyr)
system/mutant2089/    # Mutant 2089 (BRP-eran; alias: "mutant")
system/_template/     # mall för nya system
```

**Nytt system:** kopiera `_template/`, fyll i `system.json` (attribut, intervall,
formler), `lexicon.json` (termer/färdigheter/vapen/egennamn + kända felvarianter),
`dice.json` (tärningsgrammatik), `statblock.schema.json` och `detection.json`
(fingeravtryck för autodetektering). Klart — `python3 -m pipeline system` listar det.

Adaptrarna kan regenereras från referensrepona:

```bash
python3 scripts/bygg_adapter.py dod        --ref "/sökväg/till/Drakar och Demoner 1991"
python3 scripts/bygg_adapter.py mutant2089 --ref "/sökväg/till/Mutant 2089 RPG"
```

Obs: `.claude/systems/` (används av de kreativa skillsen `aventyr`,
`karaktarsskapare`, `konvertera`) beskriver för `mutant` fortfarande
Mutant: År Noll — extraktionspipelinen använder enbart `system/`.

## Tester

```bash
python3 -m unittest discover -s tests -t .
```

Syntetiska PDF-fixturer (text/bild/vattenstämpel/tvåspalt) genereras av testerna;
integrationsfall körs mot pipelinens hela flöde inklusive export.
