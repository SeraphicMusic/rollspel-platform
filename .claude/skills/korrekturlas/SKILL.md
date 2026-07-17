---
name: korrekturlas
description: Korrekturläs en extraherad rollspelsbok mot source-PDF. Aktiveras med "/korrekturläs", "/korrekturlas", "korrekturläs export", "proofread export", eller när användaren vill korrekturläsa en befintlig extraktion.
allowed-tools: Read, Write, Edit, Bash(python3:*), Bash(node:*), Task, AskUserQuestion, Glob, TodoWrite
---

# Korrekturläs rollspels-export

Kör agentbaserad korrektur på en bok i pipelinens arbetskatalog (`arbete/<slug>`).

## Användning

```
/korrekturläs [workdir="arbete/<slug>"]
```

## Instruktioner

### Steg 1: Hitta arbetskatalogen

Om `workdir` inte angavs: lista kataloger under `arbete/` och fråga användaren
med AskUserQuestion. Om boken aldrig extraherats: hänvisa till `/extrahera`.

**Äldre exporter utan arbetskatalog** (JSON från gamla flödet): kör först
`python3 -m pipeline analysera "<pdf>"` + `rendera`, och be användaren bekräfta
att transkript ska återskapas via `/extrahera` — korrekturen arbetar mot
pipelinens state, inte mot lösa JSON-filer.

### Steg 2: Kontrollera state

```bash
python3 -m pipeline status --workdir "WD"
```

Sidor måste vara minst `validated`. Om de bara är `transcribed`:
kör `python3 -m pipeline validera --workdir "WD"` först.

### Steg 3: Kör korrekturen

```bash
python3 -m pipeline jobb --workdir "WD" --typ korrektur
```

Följ `.claude/skills/_shared/proofreading-workflow.md` (Fas 1: specialister
parallellt enligt jobbets `agents`-lista; Fas 2: djävulens advokat skriver
`page_NNN.final.json` med korrektionsposter). Flödet är återupptagbart —
sidor med final-fil dyker inte upp i jobblistan igen.

### Steg 4: Sammanfoga och exportera om

```bash
python3 -m pipeline sammanfoga --workdir "WD"
python3 -m pipeline rapport   --workdir "WD"
python3 -m pipeline exportera --workdir "WD" --format alla
```

### Steg 5: Rapportera

Antal korrekturlästa sidor, antal applicerade/avvisade korrektionsposter,
kvarstående granskningsposter (`export/granskningsrapport.md`), sökvägar till export.
