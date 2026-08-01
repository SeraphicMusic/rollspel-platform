"""Jobblistor för transkription och korrektur — snäva, väldefinierade enheter.

`rippare jobb` talar om exakt vilka sidor som väntar på vilket steg och vilka
filer som hör till. Transkriptionen (Claude som vision-modell) och korrekturen
(agent-teamet) konsumerar detta i stället för att själva leta i katalogerna.
"""
from pathlib import Path

from .analyze import NEEDS_VISION
from .manifest import Manifest, page_file
from .preflight import decisions_file


def transcription_jobs(workdir, limit=None):
    """Sidor som är renderade men saknar (giltigt) transkript."""
    m = Manifest.load(workdir)
    jobs = []
    for no in m.page_numbers():
        p = m.page(no)
        if p["class"] not in NEEDS_VISION:
            continue
        png = page_file(workdir, no, "png")
        transcript = page_file(workdir, no, "transcript.json")
        if not png.is_file() or transcript.is_file():
            continue
        job = {
            "page": no,
            "task": "transcribe",
            "png": str(png),
            "output": str(transcript),
            "class": p["class"],
        }
        embedded = page_file(workdir, no, "embedded.json")
        if embedded.is_file():
            job["embedded_hint"] = str(embedded)
        # Uppmätta radboxar (pipeline/rows.py). De är inget facit för texten,
        # men de ger transkriberaren `source.bbox` utan att den behöver gissa
        # koordinater — och utan bbox är halva förbesiktningen verkningslös.
        radboxar = page_file(workdir, no, "radboxar.json")
        if radboxar.is_file():
            job["radboxar"] = str(radboxar)
        jobs.append(job)
        if limit and len(jobs) >= limit:
            break
    return jobs


def review_jobs(workdir, limit=None):
    """Validerade sidor som ännu inte har page_NNN.final.json.

    Triagen (vilka specialister som behövs) härleds deterministiskt ur
    valideringsresultatet.
    """
    from .manifest import read_json
    m = Manifest.load(workdir)
    jobs = []
    for no in m.page_numbers():
        validated = page_file(workdir, no, "validated.json")
        final = page_file(workdir, no, "final.json")
        if not validated.is_file() or final.is_file():
            continue
        data = read_json(validated)
        if (data.get("skipped") or {}).get("reason") == "illustration_only":
            continue
        elements = data.get("elements", [])
        agents = ["sprakgranskare"]
        if any(el.get("type") == "table" for el in elements) or len(elements) > 8:
            agents.append("layoutverifierare")
        # Advokaten äger domänkontroll (statblocks/terminologi) och forensik
        # ([?]-partier) — den körs alltid och behöver ingen triage.
        agents.append("djavulens-advokat")
        review_dir = page_file(workdir, no, "review")
        job = {
            "page": no,
            "task": "review",
            "validated": str(validated),
            "png": str(page_file(workdir, no, "png")),
            "review_dir": str(review_dir),
            "output": str(final),
            "agents": agents,
            "needs_review": m.page(no).get("needs_review", 0),
            # Boknivåprecedens: läses av alla tre agenterna, skrivs bara av
            # advokaten. Utan den utreds samma fråga om på varje sida.
            "beslut": str(decisions_file(workdir)),
        }
        # Deterministiska kandidater från `forbesikta` — agenterna ska börja
        # från listan i stället för att leta upp mönstren själva (Regel 5).
        heuristik = Path(str(review_dir)) / "heuristik.json"
        if heuristik.is_file():
            job["heuristik"] = str(heuristik)
        jobs.append(job)
        if limit and len(jobs) >= limit:
            break
    return jobs


def ingest_transcripts(workdir):
    """Bokför inkomna transkript: schema-kontroll + statusuppdatering.

    Trasiga transkript rapporteras och sidan förblir i jobblistan
    (filen döps om till .rejected så den inte blockerar).
    """
    from .manifest import read_json
    m = Manifest.load(workdir)
    ok, rejected = [], []
    for no in m.page_numbers():
        transcript = page_file(workdir, no, "transcript.json")
        if not transcript.is_file() or m.state_at_least(no, "transcribed"):
            continue
        problem = _resolve_row_boxes(workdir, no, transcript) \
            or _check_transcript(transcript, no)
        if problem:
            transcript.rename(str(transcript) + ".rejected")
            m.page(no)["error"] = "transkript avvisat: %s" % problem
            rejected.append((no, problem))
        else:
            m.set_state(no, "transcribed")
            ok.append(no)
    m.save()
    return ok, rejected


BBOX_SAKNAS = ("Ingen uppmätt rad täcker elementet (pipeline/rows.py) — "
               "bbox utelämnas hellre än gissas.")


def _resolve_row_boxes(workdir, page_no, transcript):
    """Lös upp `source.rader` (radindex) till `source.bbox` ur mätningen.

    Transkriberaren anger VILKA uppmätta rader ett element täcker, aldrig
    koordinaterna själva — en påhittad box är ett fel som ser ut som data.
    Unionen räknas här, deterministiskt, ur `page_NNN.radboxar.json`:
    en brödtextrad ger sin egen box, en tabell eller ett statblock unionen av
    alla rader den spänner över. Tom lista betyder "mätningen missade raden"
    och ger `bbox_saknas` i stället för en gissning.

    Returnerar en felsträng om hänvisningen inte går att lösa (då avvisas
    sidan och transkriberas om) — annars None.
    """
    from .manifest import atomic_write_json, read_json
    try:
        data = read_json(transcript)
    except Exception:
        return None  # _check_transcript ger det bättre felmeddelandet
    elements = data.get("elements")
    if not isinstance(elements, list):
        return None
    pending = [el for el in elements if isinstance(el, dict)
               and isinstance(el.get("source"), dict)
               and "rader" in el["source"]]
    if not pending:
        return None

    measured = page_file(workdir, page_no, "radboxar.json")
    if not measured.is_file():
        return ("transkriptet hänvisar till radindex men "
                "page_%03d.radboxar.json saknas" % page_no)
    rows = read_json(measured).get("rows") or []

    for i, el in enumerate(elements):
        src = el.get("source") if isinstance(el, dict) else None
        if not (isinstance(src, dict) and "rader" in src):
            continue
        idx = src["rader"]
        if not isinstance(idx, list) or \
                not all(isinstance(n, int) for n in idx):
            return "element %d: source.rader måste vara en lista med radindex" % i
        if not idx:
            src.pop("rader")
            src["bbox_saknas"] = BBOX_SAKNAS
            continue
        if any(n < 0 or n >= len(rows) for n in idx):
            return ("element %d: source.rader %r ligger utanför mätningens "
                    "%d rader" % (i, idx, len(rows)))
        boxes = [rows[n]["bbox"] for n in idx]
        x = min(b[0] for b in boxes)
        y = min(b[1] for b in boxes)
        width = max(b[0] + b[2] for b in boxes) - x
        height = max(b[1] + b[3] for b in boxes) - y
        src["bbox"] = [round(v, 5) for v in (x, y, width, height)]
        src["bbox_source"] = "pipeline.rows"
        src.setdefault("region", rows[idx[0]].get("region"))
    atomic_write_json(transcript, data)
    return None


# Elementtyperna i transkriptionskontraktet (.claude/skills/extrahera/SKILL.md
# §Transkriptionskontrakt). Listan måste rymma HELA kontraktet: tabellens
# reservform (`table_header`/`table_cell`) och dess omgivning (`table_caption`,
# `table_note`) är föreskrivna former, och en sida som använder dem får inte
# avvisas — då är alternativet att typa tabellen som `paragraph`, vilket
# förstör rad- och kolumnstrukturen för gott. `illustration` finns kvar för
# bakåtkompatibilitet men skapas inte i nya transkript.
_ELEMENT_TYPES = (
    "heading", "paragraph", "boxed_text", "list", "list_item", "requirement",
    "table", "table_header", "table_cell", "table_caption", "table_note",
    "statblock", "toc_entry", "index_entry", "page_artifact", "illustration",
)


def _check_transcript(path, page_no):
    from .manifest import read_json
    try:
        data = read_json(path)
    except Exception as e:
        return "ogiltig JSON (%s)" % e
    if not isinstance(data, dict):
        return "toppnivån måste vara ett objekt"
    if data.get("page") != page_no:
        return "page-fältet (%r) matchar inte sidan %d" % (data.get("page"), page_no)
    elements = data.get("elements")
    if not isinstance(elements, list):
        return "elements saknas eller är inte en lista"
    if not elements:
        skipped = data.get("skipped")
        if not isinstance(skipped, dict) or \
                skipped.get("reason") != "illustration_only":
            return ("elements är tom utan "
                    "skipped.reason=illustration_only")
    for i, el in enumerate(elements):
        if not isinstance(el, dict) or "type" not in el:
            return "element %d saknar type" % i
        if el["type"] not in _ELEMENT_TYPES:
            return "element %d har okänd type %r" % (i, el["type"])
        if el["type"] in ("heading", "paragraph", "boxed_text") \
                and not (el.get("text") or "").strip():
            return "element %d (%s) saknar text" % (i, el["type"])
    return None
