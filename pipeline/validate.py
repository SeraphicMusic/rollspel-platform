"""Systemspecifik validering av extraherade/transkriberade sidor.

Läser transcript/embedded per sida, kör deterministiska validatorer
(tärningsnotation, lexikon, attribut, härledda formler, statblock, struktur),
bokför korrektionsposter och skriver page_NNN.validated.json. Idempotent.
"""
import ast
import math
import re

from .corrections import (apply_corrections_to_text, make_correction,
                          repair_dice_token, repair_word, scan_dice_in_text,
                          scan_words_in_text)
from .log import setup_logging
from .manifest import Manifest, atomic_write_json, page_file, read_json

# ---------------------------------------------------------------------------
# Säker formelutvärdering: namn, heltal, + - * /, ceil(), floor()
# ---------------------------------------------------------------------------

_ALLOWED_FUNCS = {"ceil": math.ceil, "floor": math.floor}


def eval_formula(formula, values):
    """Utvärdera t.ex. 'ceil((FYS + STO) / 2)'. None om ett namn saknas."""
    tree = ast.parse(formula, mode="eval")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.BinOp) and isinstance(
                node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv)):
            a, b = ev(node.left), ev(node.right)
            if a is None or b is None:
                return None
            ops = {ast.Add: lambda: a + b, ast.Sub: lambda: a - b,
                   ast.Mult: lambda: a * b, ast.Div: lambda: a / b,
                   ast.FloorDiv: lambda: a // b}
            return ops[type(node.op)]()
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in _ALLOWED_FUNCS and len(node.args) == 1:
            arg = ev(node.args[0])
            return None if arg is None else _ALLOWED_FUNCS[node.func.id](arg)
        if isinstance(node, ast.Name):
            return values.get(node.id)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("otillåten formelnod: %r" % node)

    return ev(tree)


def _as_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        s = value.strip().replace("%", "")
        if re.fullmatch(r"-?\d+", s):
            return int(s)
    return None


# Ett tal som bär sin ENHET: `29 m/SR`, `34 år`, `12 kg`. Trycket sätter
# härledda värden så, och `_as_int` gav `None` för allihop — varvid
# `derived_checks` hoppade över formeln TYST. `KP = STO + FYS` fyrade (KP står
# som rent tal) medan `Förflyttning = FYS + SMI` aldrig gjorde det, så
# kontrollen gällde halva sin lista och rapporten såg komplett ut. På
# MUT-AVE-terminal-state räknade advokaterna formeln för hand på nitton rutor
# och fann åtta avvikelser som ingen kod hade sett.
#
# Spärren mot tärningsnotation är villkoret att siffrorna inte får följas av
# en till siffra eller av T/D: `3T6+2` ger inget värde, `29 m/SR` ger 29.
_LEDANDE_TAL = re.compile(r"-?\d+(?![\dTtDd])")


def _leading_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        m = _LEDANDE_TAL.match(value.strip())
        if m:
            return int(m.group())
    return None


# ---------------------------------------------------------------------------
# Statblock
# ---------------------------------------------------------------------------

# DoD-bestiariets tvåkolumnsform: `1T20+10 (21)` — formel + tryckt typvärde
# (Krugal BQ-009). Typvärdet är formelns avrundade medelvärde, så de två
# kolumnerna kan kontrolleras mot varandra: 1T6+6 -> 9,5 -> 10, 3T6 -> 10,5
# -> 11, 1T20+10 -> 20,5 -> 21 (alla belagda i del II/Krugal). En avvikelse
# är ett FYND (t.ex. Megas SMI `1T4+11 (4)`, Krugal s. 16), aldrig en
# rättning.
_BESTIARIE_FORM = re.compile(r"^(\d+)[Tt](\d+)\s*([+-]\s*\d+)?\s*\((\d+)\)$")


def _bestiarie_typvarde(m):
    n, sidor = int(m.group(1)), int(m.group(2))
    mod = int(m.group(3).replace(" ", "")) if m.group(3) else 0
    medel = n * (sidor + 1) / 2 + mod
    return math.floor(medel + 0.5)


def _sb_normal(value):
    """Normalisera ett SB-värde för jämförelse mot sb_table.

    Tryckets streck (`—`, `–`, `-`) och `0` betyder båda "ingen bonus";
    ett ledande `+` är typografi, inte information."""
    s = str(value).strip().replace(" ", "")
    if s in ("—", "–", "-", "0", ""):
        return "0"
    return s.lstrip("+").upper()


def _sb_forvantad(adapter, sty, sto):
    """Slå upp STY+STO i sb_table. Returnerar (summa, bonus) eller None."""
    sb_spec = adapter.system.get("sb_table")
    if not sb_spec or sty is None or sto is None:
        return None
    total = sty + sto
    for row in sb_spec.get("rows", []):
        if row["min"] <= total <= row["max"]:
            return total, row["bonus"]
    return None


def _tabellburna_stats(rows, adapter):
    """Plocka attributvärden ur bestiarietabellens `data.rows`-bärare.

    Samma tryckta form bärs av två modeller i korpusen (Krugal BQ-009):
    `statblock` med värdena i `data.stats` och `table` med raderna
    `[attribut, formel, typvärde]`. Kontrollerna måste läsa båda, annars är
    hela bestiariet en blind fläck. Returnerar ({attr: typvärde}, {attr:
    (formel, typvärde)})."""
    schema = adapter.statblock
    allowed = set(schema.get("stats_allowed", []))
    labels = schema.get("field_labels", {})
    stats, formler = {}, {}
    for row in rows or []:
        if not row or not isinstance(row[0], str):
            continue
        label = row[0].strip()
        ckey = label if label in allowed else labels.get(label.lower())
        if not ckey:
            continue
        varden = [c.strip() for c in row[1:]
                  if isinstance(c, str) and c.strip()]
        if not varden:
            continue
        if len(varden) >= 2 and _as_int(varden[-1]) is not None and \
                re.fullmatch(r"\d+[Tt]\d+\s*([+-]\s*\d+)?", varden[0]):
            formler[ckey] = (varden[0], int(varden[-1]))
        stats[ckey] = varden[-1]
    return stats, formler


def _canonical_stat_key(key, adapter):
    """Normalisera en statblock-nyckel; reparera OCR-skadade attributnamn."""
    schema = adapter.statblock
    labels = schema.get("field_labels", {})
    if key in schema.get("stats_allowed", []):
        return key, None
    mapped = labels.get(key.strip().lower())
    if mapped:
        return mapped, None
    # Teckenförväxlings-reparation mot attributnamnen (max 1 avvikande tecken)
    upper = key.strip().upper()
    candidates = []
    for attr in schema.get("stats_allowed", []):
        if len(attr) == len(upper):
            diff = sum(1 for a, b in zip(attr, upper) if a != b)
            if diff == 1:
                candidates.append(attr)
    if len(candidates) == 1:
        corr = make_correction(
            key, candidates[0], 0.92,
            "Attributnamn: 1 tecken avviker från %r" % candidates[0],
            "validator:attributes")
        return candidates[0], corr
    return key, "unknown"


def validate_statblock(el, adapter, flags, notes=None):
    if notes is None:
        notes = []
    schema = adapter.statblock
    data = el.get("data") or {}
    corrections = []
    stats = data.get("stats") or {}
    new_stats = {}
    for key, value in stats.items():
        ckey, corr = _canonical_stat_key(key, adapter)
        if isinstance(corr, dict):
            corrections.append(corr)
        elif corr == "unknown":
            flags.append("statblock: okänt fält %r" % key)
        new_stats[ckey] = value
        iv = _as_int(value)
        # Tryckets tankstreck ÄR ett värde (Krugal BQ-008): "ej tillämpligt"
        # (KAR på odöda/djur) eller "ingen bonus" (SB) — aldrig ett fel.
        if isinstance(value, str) and value.strip() in schema.get(
                "null_tokens", []):
            continue
        if ckey in adapter.attribute_names:
            lo, hi = adapter.attr_range()
            # Varelser/odöda har ett eget intervall (Krugal BQ-002):
            # DRAKE STY 100, JÄTTEBLÄCKFISK STO 125, SPÖKE STY/FYS 0.
            # Statblocket bär ingen varelseflagga, så kontrollen gäller
            # unionen av intervallen — det snäva RP-intervallet kan bara
            # dömas av en människa som vet vem rutan tillhör.
            creature = adapter.system.get("attributes", {}).get(
                "creature_range")
            if creature:
                lo = min(lo, creature.get("min", lo))
                hi = max(hi, creature.get("max", hi))
            if iv is None:
                # Bestiariets tvåkolumnsform `formel (typvärde)` är ett
                # giltigt värde OCH en gratis kontroll (Krugal BQ-009):
                # kolumnerna ska per konstruktion stämma överens.
                m = _BESTIARIE_FORM.match(str(value).strip())
                if m:
                    # Avvikelsen är en UPPLYSNING, inte needs_review: det
                    # tryckta värdet är alltid print-troget (boknivådomen
                    # »Bestiariets tvåkolumnsform … är print-trogna«).
                    typ = _bestiarie_typvarde(m)
                    if typ != int(m.group(4)):
                        notes.append(
                            "statblock: %s=%r — formelns typvärde %d ≠ "
                            "tryckt typvärde %s" % (ckey, value, typ,
                                                    m.group(4)))
                    continue
                # tärningsvärde m.m. tillåtet för SB — men inte för grundattribut
                status, dcorr = repair_dice_token(str(value), adapter.dice)
                if status != "ok":
                    flags.append("statblock: %s=%r är inte ett tal" % (ckey, value))
            elif not lo <= iv <= hi:
                flags.append("statblock: %s=%d utanför intervall %d-%d"
                             % (ckey, iv, lo, hi))
    data["stats"] = new_stats

    # Härledda formler (t.ex. KP = STO + FYS).
    #
    # Uppslaget måste gå i BÅDE `stats` och `other`. Transkriptionen lägger
    # grundegenskaperna i `stats` och de härledda värdena där trycket har dem —
    # och `Förflyttning` står i `other` i praktiskt taget varje statblock, medan
    # `KP` oftast står i `stats`. Så länge kontrollen bara läste `stats` gällde
    # den därför KP men aldrig Förflyttning, utan att något sa ifrån: en
    # kontroll som tyst gäller halva sin lista ser i rapporten ut precis som en
    # som gäller hela. Sju avvikelser låg dolda så — bl.a. FRANZ HAUSER
    # (`MUT-VRL-sieger-bauhaus-block` s. 4) helt oflaggad, medan LOKALA
    # TERRORISTER (`MUT-AVE-dodspatrullen` s. 10) hittades först av en advokat
    # för hand i 12× zoom. Det är samma jobb som formeln gör gratis.
    #
    # Värdena som formeln räknar med hämtas ur båda, av samma skäl: en formel
    # kan referera ett fält som råkat hamna i `other` hos en transkription och i
    # `stats` hos nästa, och skillnaden är inte en egenskap hos boken.
    other = data.get("other") or {}
    values = {k: _leading_int(v)
              for k, v in list(other.items()) + list(new_stats.items())}
    values = {k: v for k, v in values.items() if v is not None}
    for check in adapter.system.get("derived_checks", []):
        field, formula = check["field"], check["formula"]
        stated = _leading_int(new_stats.get(field))
        if stated is None:
            stated = _leading_int(other.get(field))
        if stated is None:
            # Fältet finns inte i rutan — kontrollen gäller inte, och det är
            # inte ett fynd. Men står fältet där utan att gå att läsa som tal
            # SKA det synas: en överhoppad kontroll får aldrig se ut som en
            # godkänd (BQ-001).
            if field in new_stats or field in other:
                flags.append("statblock: %s=%r går inte att läsa som tal — "
                             "kontrollen %s hoppades över"
                             % (field, new_stats.get(field, other.get(field)),
                                formula))
            continue
        try:
            expected = eval_formula(formula, values)
        except ValueError:
            flags.append("statblock: formeln %s gick inte att räkna — "
                         "kontrollen av %s hoppades över" % (formula, field))
            continue
        if expected is not None and int(expected) != stated:
            flags.append("statblock: %s=%d men %s = %d"
                         % (field, stated, formula, int(expected)))

    # Skadebonus är en TABELLUPPSLAGNING, inte en formel, så `derived_checks`
    # kan inte uttrycka den — och utan detta block prövades `sb_table` aldrig
    # av någon kod (Krugal BQ-004). 9 tryckta SB-avvikelser låg osedda i
    # korpusen bakom den luckan. En avvikelse FLAGGAS, aldrig rättas: ett
    # tryckt räknefel är ett fynd (AGENTER.md Regel 8a).
    sb_stated = new_stats.get("SB", other.get("SB"))
    if sb_stated is not None:
        uppslag = _sb_forvantad(adapter, values.get("STY"),
                                values.get("STO"))
        if uppslag and _sb_normal(sb_stated) != _sb_normal(uppslag[1]):
            # UPPLYSNING, inte needs_review: avvikelsen är författarens och
            # det tryckta värdet alltid print-troget (boknivådomen »SB i
            # bandet STY+STO 27–29«).
            notes.append(
                "statblock: SB=%r men STY + STO = %d ger %r enligt sb_table"
                % (sb_stated, uppslag[0], uppslag[1]))

    # Färdighetsvärden
    skills = data.get("skills") or {}
    sk_lo, sk_hi = schema.get("skills_value_range", [0, 999])
    divisible = adapter.system.get("skill_value", {}).get("divisible_by")
    for name, value in skills.items():
        iv = _as_int(value)
        if iv is None:
            continue
        if not sk_lo <= iv <= sk_hi:
            flags.append("statblock: färdighet %r=%d utanför %d-%d"
                         % (name, iv, sk_lo, sk_hi))
        elif divisible and iv % divisible != 0:
            flags.append("statblock: färdighet %r=%d ej delbar med %d"
                         % (name, iv, divisible))
    for field in schema.get("required_fields", []):
        if field == "name" and not el.get("data", {}).get("name"):
            flags.append("statblock: namn saknas")
        elif field == "stats" and not new_stats:
            flags.append("statblock: stats saknas")
    return corrections


# ---------------------------------------------------------------------------
# Element- och sidvalidering
# ---------------------------------------------------------------------------

def validate_element(el, adapter):
    flags = []
    notes = []
    corrections = []
    text = el.get("text") or ""
    if text:
        dice_corr, dice_flags = scan_dice_in_text(text, adapter.dice,
                                                  adapter.words)
        corrections.extend(dice_corr)
        flags.extend("%(issue)s: %(token)r" % f for f in dice_flags)
        corrections.extend(scan_words_in_text(text, adapter))
        el["text"] = apply_corrections_to_text(text, corrections)

    if el.get("type") == "statblock":
        corrections.extend(validate_statblock(el, adapter, flags, notes))

    if el.get("type") == "table":
        data = el.get("data") or {}
        headers, rows = data.get("headers"), data.get("rows")
        if headers and rows:
            # En orubricerad LEDARKOLUMN är tryckets egen form, inte ett
            # cellantalsfel (Krugal BQ-009ii): bestiariet sätter tre
            # datakolumner under två rubriker. Signalen är mätt, inte
            # gissad: VARJE rad bär exakt en cell mer än huvudet.
            if not all(len(r) == len(headers) + 1 for r in rows):
                for i, row in enumerate(rows):
                    if len(row) != len(headers):
                        flags.append(
                            "tabell: rad %d har %d celler, huvudet %d"
                            % (i + 1, len(row), len(headers)))
        # Bestiarievärden i `data.rows`-bäraren (Krugal BQ-004/BQ-009):
        # samma kontroller som för statblock, samma upplysningskanal.
        tstats, tformler = _tabellburna_stats(rows, adapter)
        for ckey, (formel, typ_tryckt) in tformler.items():
            m = _BESTIARIE_FORM.match("%s (%d)" % (formel, typ_tryckt))
            if m:
                typ = _bestiarie_typvarde(m)
                if typ != typ_tryckt:
                    notes.append(
                        "tabell: %s=%r — formelns typvärde %d ≠ tryckt "
                        "typvärde %d" % (ckey, formel, typ, typ_tryckt))
        if "SB" in tstats:
            uppslag = _sb_forvantad(adapter, _as_int(tstats.get("STY")),
                                    _as_int(tstats.get("STO")))
            if uppslag and _sb_normal(tstats["SB"]) != _sb_normal(uppslag[1]):
                notes.append(
                    "tabell: SB=%r men STY + STO = %d ger %r enligt sb_table"
                    % (tstats["SB"], uppslag[0], uppslag[1]))
        # Tärningar/lexikon i celler
        for row in (rows or []):
            for ci, cell in enumerate(row):
                if not isinstance(cell, str):
                    continue
                cell_corr, cell_flags = scan_dice_in_text(
                    cell, adapter.dice, adapter.words)
                cell_corr.extend(scan_words_in_text(cell, adapter))
                if cell_corr:
                    row[ci] = apply_corrections_to_text(cell, cell_corr)
                    corrections.extend(cell_corr)
                flags.extend("%(issue)s: %(token)r" % f for f in cell_flags)

    el.setdefault("corrections", []).extend(corrections)
    # Ej applicerade valideringsposter är förslag — de måste synas i
    # granskningsrapporten, annars ligger de tysta i filen och ingen dömer dem.
    for corr in corrections:
        if not corr.get("applied"):
            flags.append("valideringsförslag ej applicerat (%s): %r → %r"
                         % (corr.get("source", "?"), corr["original"],
                            corr["corrected"]))
    if flags:
        el["needs_review"] = True
        el.setdefault("review_reasons", []).extend(flags)
    # Upplysningar håller INTE elementet öppet (Krugal BQ-004/BQ-009):
    # avvikelsen är författarens, det tryckta värdet är print-troget, och
    # ingen människa behöver döma den per sida. Rapporten redovisar dem i
    # en egen sektion.
    if notes:
        befintliga = el.setdefault("validation_notes", [])
        befintliga.extend(n for n in notes if n not in befintliga)
    return len(corrections), len(flags)


def _source_file(workdir, page_no):
    for suffix in ("final.json", "transcript.json", "embedded.json"):
        path = page_file(workdir, page_no, suffix)
        if path.is_file():
            return path
    return None


def validate(workdir, adapter, pages=None, force=False):
    """Validera alla sidor som nått transcribed/extracted. Idempotent."""
    log = setup_logging(workdir)
    m = Manifest.load(workdir)
    n_pages = n_corr = n_flags = 0
    for no in m.page_numbers():
        if pages and no not in pages:
            continue
        p = m.page(no)
        out = page_file(workdir, no, "validated.json")
        if out.is_file() and not force:
            continue
        src = _source_file(workdir, no)
        if src is None or not m.state_at_least(no, "rendered"):
            continue
        try:
            page_data = read_json(src)
            elements = page_data.get("elements", page_data)
            if not isinstance(elements, list):
                raise ValueError("elements saknas i %s" % src.name)
            page_corr = page_flags = 0
            for i, el in enumerate(elements):
                el.setdefault("id", "p%03d_e%02d" % (no, i + 1))
                c, f = validate_element(el, adapter)
                page_corr += c
                page_flags += f
            result = {"page": no, "system": adapter.id,
                      "source_file": src.name,
                      "elements": elements,
                      "stats": {"corrections": page_corr, "flags": page_flags}}
            if page_data.get("skipped"):
                result["skipped"] = page_data["skipped"]
            atomic_write_json(out, result)
            p["needs_review"] = page_flags + sum(
                1 for el in elements
                for corr in el.get("corrections", []) if not corr["applied"])
            if not m.state_at_least(no, "validated"):
                m.set_state(no, "validated")
            n_pages += 1
            n_corr += page_corr
            n_flags += page_flags
        except Exception as e:
            p["error"] = "validate: %s" % e
            log.exception("sida %d kunde inte valideras", no)
    m.save()
    log.info("validera: %d sidor, %d korrektioner, %d flaggor",
             n_pages, n_corr, n_flags)
    return n_pages, n_corr, n_flags
