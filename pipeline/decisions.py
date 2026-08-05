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

## Klassen: `[beslut]` eller `[verktyg]`

Kön är enligt CLAUDE.md till för frågor som **bara en människa kan svara på** —
mät först, fråga sedan. I praktiken drev den till en att-göra-lista: i del III
var 24 av 27 poster verktygsarbete med färdiga, uppmätta facit, och de
BLOCKERADE boken lika hårt som de tre verkliga frågorna. Följden blev att
användaren fick ta ställning till buggar i `pipeline/` för att boken skulle
kunna arkiveras, och sa ifrån: *»jag vill aldrig behöva berätta för dig att du
ska fixa uppenbara saker.«*

Regeln var alltså riktig men oframtvingad — samma sak som städningen
import/ → `arkiv/`, som var en README-punkt tills den blev `pipeline arkivera`.
Därför bär varje köpost nu en klass direkt efter sitt id:

    - [ ] BQ-014 [beslut] Ska tryckfelet bevaras eller emenderas?
    - [ ] BQ-015 [verktyg] `forbesikta`-regeln mäter fel storhet.

* **`[beslut]`** — kräver den tryckta boken eller ett redaktionellt val om vad
  utgåvan ska säga. Bara dessa blockerar boken, och bara dessa ställs till
  användaren.
* **`[verktyg]`** — en bugg eller en saknad kontroll med ett facit att bygga
  mot. Den ska lagas, inte frågas om, och den säger ingenting om huruvida
  BOKEN är klar.

En post UTAN klass räknas som `[beslut]`. Den defaulten är avsiktlig: en
oklassad post blockerar, så glömska gör kön för sträng och aldrig för slapp.
"""
import re
from pathlib import Path

QUEUE_HEADING = "## Öppen kö"
_ITEM = re.compile(r"^\s*-\s*\[( |x|X)\]\s*(\S+)\s+(.*)$")

CLASS_DECISION = "beslut"
CLASS_TOOL = "verktyg"
_CLASS = re.compile(r"^\[(beslut|verktyg)\]\s*(.*)$", re.IGNORECASE | re.DOTALL)


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
            items.append([m.group(2), m.group(3).strip(),
                          m.group(1).lower() == "x"])
        elif items and line.startswith(" ") and line.strip():
            # Indragen fortsättningsrad hör till föregående post. Utan den här
            # grenen bar posten bara sin FÖRSTA rad, och en fråga som "BQ-002
            # Särskilda förmågor 68, 72 och 77: A och vi har olika" slutade
            # mitt i meningen överallt utom i beslut.md. Frågan ska gå att
            # förstå där den visas.
            items[-1][1] += " " + line.strip()
    return [tuple(i) for i in items]


def item_class(text):
    """(klass, text utan klassmarkör) för en köposts lydelse.

    En post utan markör räknas som `beslut` — defaulten ska göra kön för sträng
    och aldrig för slapp.
    """
    m = _CLASS.match(text.strip())
    if not m:
        return CLASS_DECISION, text
    return m.group(1).lower(), m.group(2).strip()


def open_questions(workdir, klass=None):
    """Bara de obesvarade. Med `klass` filtreras de på `beslut`/`verktyg`."""
    ut = []
    for qid, text, besvarad in queue_items(workdir):
        if besvarad:
            continue
        k, ren = item_class(text)
        if klass is not None and k != klass:
            continue
        ut.append((qid, ren))
    return ut


def blocking_questions(workdir):
    """De obesvarade frågor som gör att boken INTE är avslutad.

    Bara `[beslut]`-poster blockerar. En `[verktyg]`-post är en bugg i
    pipelinen med ett facit att bygga mot — den ska lagas, inte frågas om, och
    den säger ingenting om huruvida BOKEN är klar. Att blanda ihop de två var
    det som tvingade användaren att ta ställning till buggar för att en bok
    skulle kunna arkiveras.
    """
    return open_questions(workdir, CLASS_DECISION)


def tool_questions(workdir):
    """De obesvarade `[verktyg]`-posterna — mitt arbete, inte användarens."""
    return open_questions(workdir, CLASS_TOOL)


def next_id(workdir):
    """Nästa lediga BQ-nummer, så två agenter inte tar samma."""
    hogst = 0
    for qid, _, _ in queue_items(workdir):
        m = re.fullmatch(r"BQ-(\d+)", qid)
        if m:
            hogst = max(hogst, int(m.group(1)))
    return "BQ-%03d" % (hogst + 1)


def enqueue(workdir, text, klass=CLASS_DECISION):
    """Lägg en uppskjuten fråga i kön och returnera dess id.

    `klass` är `beslut` (kräver boken eller ett redaktionellt val) eller
    `verktyg` (en bugg med ett facit). Bara `beslut` blockerar boken.

    Idempotent på texten: samma fråga läggs inte till två gånger, för samma
    boknivåfråga stöts på av en advokat per sida och skulle annars fylla kön
    med dubbletter av sig själv.
    """
    if klass not in (CLASS_DECISION, CLASS_TOOL):
        raise ValueError("okänd köklass: %r (tillåtna: %s, %s)"
                         % (klass, CLASS_DECISION, CLASS_TOOL))
    path = Path(workdir) / "beslut.md"
    text = " ".join(text.split())
    for qid, befintlig, _ in queue_items(workdir):
        if item_class(befintlig)[1] == item_class(text)[1]:
            return qid
    qid = next_id(workdir)
    rad = "- [ ] %s [%s] %s" % (qid, klass, text)
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
