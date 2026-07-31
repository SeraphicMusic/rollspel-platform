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
        problem = _check_transcript(transcript, no)
        if problem:
            transcript.rename(str(transcript) + ".rejected")
            m.page(no)["error"] = "transkript avvisat: %s" % problem
            rejected.append((no, problem))
        else:
            m.set_state(no, "transcribed")
            ok.append(no)
    m.save()
    return ok, rejected


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
        if el["type"] not in ("heading", "paragraph", "table", "list",
                              "statblock", "boxed_text", "toc_entry",
                              "index_entry", "page_artifact", "illustration"):
            return "element %d har okänd type %r" % (i, el["type"])
        if el["type"] in ("heading", "paragraph", "boxed_text") \
                and not (el.get("text") or "").strip():
            return "element %d (%s) saknar text" % (i, el["type"])
    return None
