"""Granskningsrapport: allt som behöver mänskliga ögon, sorterat per sida."""
from pathlib import Path

from .corrections import KIND_EMENDATION, KIND_OCR
from .log import setup_logging
from .manifest import Manifest, export_dir, page_file, pages_dir, read_json
from .merge import best_page_file, merge

AGENTS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "agents"

# Agenter som slagits samman in i djävulens-advokat men fortfarande
# förekommer som `source` i äldre korrektionsposter.
_LEGACY_AGENT_MODELS = {
    "digital-forensiker": "opus (sammanslagen in i djavulens-advokat)",
    "rollspelskonstruktor": "opus (sammanslagen in i djavulens-advokat)",
}


def _agent_model(agent_name):
    """Modell för en agent, läst direkt ur dess frontmatter — inget självrapporterande."""
    path = AGENTS_DIR / ("%s.md" % agent_name)
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("model:"):
                return line.split(":", 1)[1].strip()
    return _LEGACY_AGENT_MODELS.get(agent_name, "okänd")


def _model_from_source(source):
    name = source.split(":", 1)[1] if source and ":" in source else source
    return _agent_model(name or "")


def _correction_kind(correction):
    """Korrektionsslag, med härledning för poster skrivna före fältet fanns.

    Boknivåbesluten var per definition avsteg från trycket, så de klassas som
    emenderingar även utan explicit `kind`. Övriga äldre poster antas vara
    OCR-rättelser — det var den enda sortens applicerade ändring som Regel 8
    tillät innan 8a infördes.
    """
    kind = correction.get("kind")
    if kind:
        return kind
    if str(correction.get("source", "")).startswith("anvandare:boknivabeslut"):
        return KIND_EMENDATION
    return KIND_OCR


GEOMETRY_SHARE = 0.5


def _geometry_section(workdir, m):
    """Sidor utan användbar geometri — läsexporten tystnar annars om dem.

    `pipeline/export.py` fogar aldrig ihop rader utan bbox: utan geometri
    finns inget facit, och då blir varje TRYCKT rad ett eget stycke i
    `bok.md`. Det ser ut som smal, ihoptryckt sättning och syns inte som ett
    fel någonstans — texten är komplett, bara styckeindelad per rad. Den
    tystnaden är farlig, för felet är osynligt i både `status` och
    granskningsrapportens övriga sektioner.

    Den vanligaste orsaken är att en helsidesbred illustration ligger i samma
    lodräta avsnitt som tvåspaltig sats: den fyller rännan, spalterna hittas
    inte, och hela sidan mäts som fullbreddsband som ingen spaltrad kan
    tilldelas (del II s. 8, 15, 20, 36, 42, 65, 66).
    """
    lines, drabbade = [], []
    for no in m.page_numbers():
        path = None
        for suffix in ("final.json", "validated.json"):
            candidate = page_file(workdir, no, suffix)
            if candidate.is_file():
                path = candidate
                break
        if path is None:
            continue
        elements = [el for el in (read_json(path).get("elements") or [])
                    if el.get("type") != "page_artifact"]
        if not elements:
            continue
        utan = sum(1 for el in elements
                   if not (el.get("source") or {}).get("bbox"))
        if utan >= GEOMETRY_SHARE * len(elements):
            drabbade.append((no, utan, len(elements)))
    if not drabbade:
        return lines
    lines.append("## Sidor utan användbar geometri")
    lines.append("")
    lines.append("Läsexporten fogar inte ihop stycken utan bbox — på de här "
                 "sidorna blir varje tryckt rad ett eget stycke i `bok.md`. "
                 "Texten är komplett; det är styckeindelningen som fattas.")
    lines.append("")
    lines.append("| Sida | Element utan bbox | Av totalt |")
    lines.append("| --- | --- | --- |")
    for no, utan, totalt in drabbade:
        lines.append("| %d | %d | %d |" % (no, utan, totalt))
    lines.append("")
    return lines


def build_report(workdir):
    log = setup_logging(workdir)
    m = Manifest.load(workdir)
    lines = ["# Granskningsrapport", ""]
    src = m.data["source"]
    lines.append("*Bok:* `%s` — %d sidor. *System:* %s. *Genererad av* "
                 "`rippare rapport`." % (src["path"], src["pages"],
                 (m.data.get("system") or {}).get("id", "okänt")))
    lines.append("")

    summary = m.summary()
    lines.append("## Översikt")
    lines.append("")
    lines.append("| State | Sidor |")
    lines.append("| --- | --- |")
    for state, count in sorted(summary["states"].items()):
        lines.append("| %s | %d |" % (state, count))
    lines.append("")

    if summary["errors"]:
        lines.append("## Fel")
        lines.append("")
        for no, err in summary["errors"]:
            lines.append("- Sida %d: `%s`" % (no, err))
        lines.append("")

    lines.extend(_geometry_section(workdir, m))

    n_items = 0
    lines.append("## Element som behöver granskning")
    lines.append("")
    for no in m.page_numbers():
        path, stage = best_page_file(workdir, no)
        if path is None:
            continue
        data = read_json(path)
        elements = data.get("elements", [])
        page_items = []
        for el in elements:
            reasons = list(el.get("review_reasons", []))
            unapplied = [c for c in el.get("corrections", [])
                         if not c.get("applied")]
            uncertain = el.get("confidence", 1.0) < 0.8
            if not (el.get("needs_review") or reasons or unapplied or uncertain):
                continue
            page_items.append((el, reasons, unapplied, uncertain))
        if not page_items:
            continue
        lines.append("### Sida %d (%s)" % (no, stage))
        lines.append("")
        for el, reasons, unapplied, uncertain in page_items:
            n_items += 1
            head = "- **%s** `%s`" % (el.get("type", "?"), el.get("id", "?"))
            if uncertain:
                head += " — confidence %.2f" % el.get("confidence", 0)
            lines.append(head)
            text = (el.get("text") or "").strip()
            if text:
                lines.append("  - Text: %s" % (text[:200] +
                             ("…" if len(text) > 200 else "")))
            for r in reasons:
                lines.append("  - Flagga: %s" % r)
            for c in unapplied:
                lines.append("  - Ej applicerat förslag: `%s` → `%s` "
                             "(confidence %.2f — %s)"
                             % (c["original"], c["corrected"],
                                c["confidence"], c["reason"]))
        lines.append("")

    applied_rows = []
    for no in m.page_numbers():
        path, _ = best_page_file(workdir, no)
        if path is None:
            continue
        for el in read_json(path).get("elements", []):
            for c in el.get("corrections", []):
                if c.get("applied"):
                    applied_rows.append((no, el, c))

    emendations = [row for row in applied_rows
                   if _correction_kind(row[2]) == KIND_EMENDATION]

    lines.append("## Emenderingar — avsteg från trycket")
    lines.append("")
    lines.append("Sättningsfel i originalet som rättats automatiskt enligt "
                 "AGENTER.md Regel 8. Trycket står kvar i kolumnen *Trycket*, "
                 "så den print-trogna lydelsen går alltid att återskapa. "
                 "Läs igenom och säg till om något ska tillbaka.")
    lines.append("")
    lines.append("| Sida | Element | Trycket | Rättat till | Confidence "
                 "| Källa | Orsak |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for no, el, c in emendations:
        lines.append("| %d | `%s` | `%s` | `%s` | %.2f | %s | %s |"
                     % (no, el.get("id", "?"), c["original"], c["corrected"],
                        c["confidence"], c["source"],
                        c["reason"].replace("|", "/")))
    if not emendations:
        lines.append("| — | — | — | — | — | — | — |")
    lines.append("")

    lines.append("## Applicerade korrektioner (spårbarhet)")
    lines.append("")
    lines.append("| Sida | Typ | Original | Rättat | Confidence | Källa "
                 "| Modell | Orsak |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for no, _el, c in applied_rows:
        lines.append("| %d | %s | `%s` | `%s` | %.2f | %s | %s | %s |"
                     % (no, _correction_kind(c), c["original"],
                        c["corrected"], c["confidence"], c["source"],
                        _model_from_source(c["source"]),
                        c["reason"].replace("|", "/")))
    n_corr = len(applied_rows)
    if n_corr == 0:
        lines.append("| — | — | — | — | — | — | — | — |")
    lines.append("")
    lines.append("*%d granskningsposter, %d applicerade korrektioner "
                 "(varav %d emenderingar).*"
                 % (n_items, n_corr, len(emendations)))
    lines.append("")

    lines.append("## Agenter & modeller per sida")
    lines.append("")
    lines.append("Läst direkt ur `.claude/agents/*.md`-frontmatter vid rapportgenerering "
                 "(inte agenternas egen utsago) — så här kör du upp: jämför mot vad du "
                 "förväntade dig (t.ex. `djavulens-advokat` ska stå `opus`).")
    lines.append("")
    lines.append("| Sida | Agent | Modell |")
    lines.append("| --- | --- | --- |")
    any_agent_rows = False
    for no in m.page_numbers():
        rdir = pages_dir(workdir) / ("page_%03d.review" % no)
        if rdir.is_dir():
            for f in sorted(rdir.glob("*.json")):
                any_agent_rows = True
                lines.append("| %d | %s | %s |" % (no, f.stem, _agent_model(f.stem)))
        if page_file(workdir, no, "final.json").is_file():
            any_agent_rows = True
            lines.append("| %d | djavulens-advokat | %s |"
                         % (no, _agent_model("djavulens-advokat")))
    if not any_agent_rows:
        lines.append("| — | — | — |")

    out = export_dir(workdir) / "granskningsrapport.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    log.info("rapport: %d granskningsposter, %d korrektioner -> %s",
             n_items, n_corr, out)
    return out
