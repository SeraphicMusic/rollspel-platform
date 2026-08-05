"""Granskningsrapport: allt som behöver mänskliga ögon, sorterat per sida."""
import json
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


# ---------------------------------------------------------------------------
# Oapplicerade förslag: överspelade, dömda och odömda
# ---------------------------------------------------------------------------

# Ett avvisat förslag ligger kvar med `applied: false` för spårbarhetens skull.
# Rapporten listade dem alla som öppna punkter, och då drunknar det som
# verkligen väntar på någon: del I hade 336 granskningsposter, varav 131 var
# förslag vars text inte ens finns kvar i elementet.
#
# Tre lägen, i den ordningen:
#   ÖVERSPELAT  originalet finns inte längre i elementet — texten har gått
#               vidare sedan förslaget skrevs, posten är historik.
#   DÖMT        advokaten har satt `verdict` (och `adjudicated_by`). Avvisat
#               med motivering; ingen behöver titta igen.
#   ODÖMT       ingen har tagit ställning. DET är vad rapporten ska lyfta.
#
# Att `verdict` saknas på äldre poster betyder inte att ingen har läst dem —
# fältet fanns inte när del I korrekturlästes. Rapporten påstår därför inte
# att de är obedömda, den säger att domen inte är nedskriven.
VERDICT_SUPERSEDED = "överspelat"
VERDICT_JUDGED = "dömt"
VERDICT_OPEN = "odömt"


def _payload(el):
    """Elementets innehåll — utan posternas egna kopior av texten.

    Utan undantaget matchar varje förslag sig självt och inget blir någonsin
    överspelat.
    """
    return json.dumps({k: v for k, v in el.items()
                       if k not in ("corrections", "review_reasons")},
                      ensure_ascii=False)


def _proposal_state(el, correction):
    if correction.get("original") not in _payload(el):
        return VERDICT_SUPERSEDED
    if correction.get("verdict") or correction.get("adjudicated_by"):
        return VERDICT_JUDGED
    return VERDICT_OPEN


GEOMETRY_SHARE = 0.5


def _queue_section(workdir):
    """Boknivåfrågor som skjutits upp och ännu inte besvarats.

    En uppskjuten fråga utan mottagare är den tystaste av alla luckor: varje
    enskild sida ser färdig ut, och boken går att kalla klar. Del I bar ett
    trettiotal sådana i ett halvår. Kön står först i rapporten, före allt
    annat, och boken redovisas inte som avslutad medan den har poster.
    """
    from .decisions import blocking_questions, tool_questions
    oppna = blocking_questions(workdir)
    verktyg = tool_questions(workdir)
    if not oppna and not verktyg:
        return []
    lines = []
    if oppna:
        lines += ["## Öppna boknivåfrågor — boken är INTE avslutad", ""]
        lines.append("%s kräver den tryckta boken eller ett redaktionellt val "
                     "och väntar på svar. De avgörs i ett svep, inte sida för "
                     "sida — men de måste avgöras. Frågorna i sin helhet står "
                     "i `beslut.md` under `## Öppen kö`."
                     % ("1 fråga" if len(oppna) == 1
                        else "%d frågor" % len(oppna)))
        lines.append("")
        for qid, text in oppna:
            lines.append("- **%s** %s" % (qid, text))
        lines.append("")
    # Verktygsposterna redovisas separat och sägs uttryckligen INTE blockera.
    # Annars läser en människa dem som något de ska ta ställning till, och det
    # är precis det som hände i del III.
    if verktyg:
        lines += ["## Verktygsfrågor — blockerar INTE boken", ""]
        lines.append("%s är buggar eller saknade kontroller i pipelinen, var "
                     "och en med ett facit att bygga mot. De ska lagas, inte "
                     "besvaras, och de säger ingenting om huruvida boken är "
                     "klar."
                     % ("1 post" if len(verktyg) == 1
                        else "%d poster" % len(verktyg)))
        lines.append("")
        for qid, text in verktyg:
            lines.append("- **%s** %s" % (qid, text))
        lines.append("")
    return lines


def _provenance_section(workdir):
    """Exporter som är byggda med äldre kod än HEAD.

    Varning, aldrig spärr: en gammal export är läsbar och riktig så långt den
    går. Det som saknades var beskedet om att den kan sakna en lagning —
    `bibliotek/…del2` bar brytfel (`ENER- GISTRÅLE`, `SMIslaget.`) som redan
    var rättade i `pipeline/export.py`, i en `bok.md` som ingen kört om.
    """
    from .provenance import check_exports
    try:
        varningar = check_exports(workdir)
    except Exception:
        return []
    if not varningar:
        return []
    lines = ["## Exportens proveniens", ""]
    lines.append("Stämpeln i exporten säger inte att den är byggd med den kod "
                 "som står i HEAD. Innehållet kan sakna lagningar som redan "
                 "finns i pipelinen — kör `sammanfoga` och `exportera` om "
                 "innan filerna används.")
    lines.append("")
    for v in varningar:
        lines.append("- %s" % v)
    lines.append("")
    return lines


def _inherited_headers_section(workdir):
    """Deltabeller som fått tryckets kolumnrubriker från tabellen ovanför.

    Arvet är den enda plats där exporten skriver ut ord som inte står över
    just den deltabellen i trycket (`_inherit_headers` i `pipeline/export.py`),
    och det stod bara i en loggrad. Det var den raden som avslöjade att s. 25:s
    `Rasmodifikationer` ärvde fel rubriker. En loggrad läses av den som råkar
    ha terminalen framme; rapporten läses av den som granskar boken.
    """
    from . import tables
    from .export import _inherit_headers, _load_book
    try:
        book = _load_book(workdir)
    except SystemExit:
        return []
    rader = []
    for page in book.get("pages", []):
        elements, _ = tables.assemble(page["elements"], page["page"])
        items = _inherit_headers([(page["page"], el) for el in elements
                                  if not el.get("removed")])
        for no, el in items:
            if el.get("headers_inherited"):
                rader.append((no, el.get("id", "?"),
                              (el.get("data") or {}).get("headers") or []))
    if not rader:
        return []
    lines = ["## Ärvda kolumnrubriker", ""]
    lines.append("Rubrikraden står inte i trycket över de här deltabellerna — "
                 "den är hämtad från tabellens egen rubrik längre upp på samma "
                 "sida, sedan kolumnernas form visat sig vara densamma. "
                 "Kontrollera mot PNG:n att det är samma tryckta tabell som "
                 "fortsätter.")
    lines.append("")
    lines.append("| Sida | Element | Ärvda rubriker |")
    lines.append("| --- | --- | --- |")
    for no, eid, headers in rader:
        lines.append("| %d | `%s` | %s |"
                     % (no, eid,
                        " / ".join(str(h).replace("|", "/") for h in headers)))
    lines.append("")
    return lines


def _drift_section(workdir):
    """Typdrift: transkriptionen tappade sina egna konventioner mitt i boken."""
    from .preflight import book_pages, scan_drift
    try:
        hits = scan_drift(book_pages(workdir))
    except Exception:
        return []
    if not hits:
        return []
    lines = ["## Typdrift", ""]
    for h in hits:
        lines.append("- %s" % h)
    lines.append("")
    return lines


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

    lines.extend(_queue_section(workdir))
    lines.extend(_provenance_section(workdir))
    lines.extend(_drift_section(workdir))
    lines.extend(_geometry_section(workdir, m))
    lines.extend(_inherited_headers_section(workdir))

    n_items = n_superseded = n_judged = n_resolved = 0
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
            # En avgjord flagga ligger kvar i `resolved_reasons` med sin
            # lösning. Den håller inte elementet öppet, men den räknas — annars
            # ser en stängd fråga ut som en fråga som aldrig ställdes.
            n_resolved += len(el.get("resolved_reasons") or [])
            open_props, judged = [], []
            for c in el.get("corrections", []):
                if c.get("applied"):
                    continue
                state = _proposal_state(el, c)
                if state == VERDICT_SUPERSEDED:
                    n_superseded += 1
                elif state == VERDICT_JUDGED:
                    n_judged += 1
                    judged.append(c)
                else:
                    open_props.append(c)
            uncertain = el.get("confidence", 1.0) < 0.8
            # Ett dömt förslag lyfter inte in elementet i listan på egen hand —
            # domen är redan fälld. Står elementet där av annat skäl visas den.
            if not (el.get("needs_review") or reasons or open_props
                    or uncertain):
                continue
            page_items.append((el, reasons, open_props, judged, uncertain))
        if not page_items:
            continue
        lines.append("### Sida %d (%s)" % (no, stage))
        lines.append("")
        for el, reasons, open_props, judged, uncertain in page_items:
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
            for c in open_props:
                lines.append("  - ODÖMT förslag: `%s` → `%s` "
                             "(confidence %.2f — %s)"
                             % (c["original"], c["corrected"],
                                c["confidence"], c["reason"]))
            for c in judged:
                lines.append("  - Avvisat av %s: `%s` → `%s`"
                             % (c.get("adjudicated_by") or c.get("verdict"),
                                c["original"], c["corrected"]))
        lines.append("")
    lines.append("*%d överspelade förslag (originalet finns inte kvar i "
                 "elementet), %d förslag med nedskriven dom och %d avgjorda "
                 "flaggor är utelämnade ur listan ovan — de väntar inte på "
                 "någon.*" % (n_superseded, n_judged, n_resolved))
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
                 "(varav %d emenderingar). Utanför listan: %d överspelade och "
                 "%d dömda förslag.*"
                 % (n_items, n_corr, len(emendations), n_superseded, n_judged))
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
