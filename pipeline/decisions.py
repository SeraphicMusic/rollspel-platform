"""Boknivåkön: frågor som skjutits upp måste ha en mottagare.

En advokat som stöter på en fråga som gäller hela boken ska inte avgöra den på
sin sida — den ska tas i ett svep. Problemet var att uppskjutandet inte gick
någonstans. Ett trettiotal flaggor i DoD-grundreglerna del I löd "avgörs i ett
svep för hela boken", ingen svepning fanns, och boken kallades klar med
frågorna kvar. De hittades först när rapporten byggdes om ett halvår senare.

Kön är en enkel kryssruttslista i `beslut.md`:

    ## Öppen kö

    - [ ] BQ-001 Sidhuvudens elementtyp: page_artifact eller paragraph?
    - [x] BQ-002 Halvfyrkant i negativa tabellvärden — ASCII bindestreck.

`- [ ]` är obesvarad, `- [x]` är besvarad. Formatet är avsiktligt prosanära:
filen läses av människor och skrivs av agenter, och ett eget JSON-register vid
sidan om skulle bara divergera från det som faktiskt står i beslutsfilen.

`rapport` vägrar redovisa boken som avslutad medan kön inte är tom.
"""
import re
from pathlib import Path

QUEUE_HEADING = "## Öppen kö"
_ITEM = re.compile(r"^\s*-\s*\[( |x|X)\]\s*(\S+)\s+(.*)$")


def queue_items(workdir):
    """[(id, text, besvarad)] ur beslut.md, i filens ordning.

    Poster utanför `## Öppen kö` räknas inte — beslutsfilen är full av vanliga
    punktlistor, och de är inte frågor som väntar på någon.
    """
    path = Path(workdir) / "beslut.md"
    if not path.is_file():
        return []
    items, inne = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            inne = line.strip() == QUEUE_HEADING
            continue
        if not inne:
            continue
        m = _ITEM.match(line)
        if m:
            items.append((m.group(2), m.group(3).strip(),
                          m.group(1).lower() == "x"))
    return items


def open_questions(workdir):
    """Bara de obesvarade."""
    return [(qid, text) for qid, text, besvarad in queue_items(workdir)
            if not besvarad]


def next_id(workdir):
    """Nästa lediga BQ-nummer, så två agenter inte tar samma."""
    hogst = 0
    for qid, _, _ in queue_items(workdir):
        m = re.fullmatch(r"BQ-(\d+)", qid)
        if m:
            hogst = max(hogst, int(m.group(1)))
    return "BQ-%03d" % (hogst + 1)


def enqueue(workdir, text):
    """Lägg en uppskjuten fråga i kön och returnera dess id.

    Idempotent på texten: samma fråga läggs inte till två gånger, för samma
    boknivåfråga stöts på av en advokat per sida och skulle annars fylla kön
    med dubbletter av sig själv.
    """
    path = Path(workdir) / "beslut.md"
    text = " ".join(text.split())
    for qid, befintlig, _ in queue_items(workdir):
        if befintlig == text:
            return qid
    qid = next_id(workdir)
    rad = "- [ ] %s %s" % (qid, text)
    innehall = path.read_text(encoding="utf-8") if path.is_file() else ""
    if QUEUE_HEADING in innehall:
        rader = innehall.splitlines()
        # Sist i köavsnittet, före nästa rubrik.
        start = rader.index(QUEUE_HEADING)
        slut = len(rader)
        for i in range(start + 1, len(rader)):
            if rader[i].startswith("## "):
                slut = i
                break
        while slut > start + 1 and not rader[slut - 1].strip():
            slut -= 1
        rader.insert(slut, rad)
        innehall = "\n".join(rader) + "\n"
    else:
        if innehall and not innehall.endswith("\n"):
            innehall += "\n"
        innehall += "\n%s\n\n%s\n" % (QUEUE_HEADING, rad)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(innehall, encoding="utf-8")
    return qid
