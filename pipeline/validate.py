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


# ---------------------------------------------------------------------------
# Statblock
# ---------------------------------------------------------------------------

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


def validate_statblock(el, adapter, flags):
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
        if ckey in adapter.attribute_names:
            lo, hi = adapter.attr_range()
            if iv is None:
                # tärningsvärde m.m. tillåtet för SB — men inte för grundattribut
                status, dcorr = repair_dice_token(str(value), adapter.dice)
                if status != "ok":
                    flags.append("statblock: %s=%r är inte ett tal" % (ckey, value))
            elif not lo <= iv <= hi:
                flags.append("statblock: %s=%d utanför intervall %d-%d"
                             % (ckey, iv, lo, hi))
    data["stats"] = new_stats

    # Härledda formler (t.ex. KP = STO + FYS)
    values = {k: _as_int(v) for k, v in new_stats.items()}
    values = {k: v for k, v in values.items() if v is not None}
    for check in adapter.system.get("derived_checks", []):
        field, formula = check["field"], check["formula"]
        stated = _as_int(new_stats.get(field))
        if stated is None:
            continue
        try:
            expected = eval_formula(formula, values)
        except ValueError:
            continue
        if expected is not None and int(expected) != stated:
            flags.append("statblock: %s=%d men %s = %d"
                         % (field, stated, formula, int(expected)))

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
        corrections.extend(validate_statblock(el, adapter, flags))

    if el.get("type") == "table":
        data = el.get("data") or {}
        headers, rows = data.get("headers"), data.get("rows")
        if headers and rows:
            for i, row in enumerate(rows):
                if len(row) != len(headers):
                    flags.append("tabell: rad %d har %d celler, huvudet %d"
                                 % (i + 1, len(row), len(headers)))
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
    if flags:
        el["needs_review"] = True
        el.setdefault("review_reasons", []).extend(flags)
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
