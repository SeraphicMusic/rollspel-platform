#!/usr/bin/env python3
"""Bygg/uppdatera systemadaptrar i system/ från referensrepona.

Användning:
    python3 scripts/bygg_adapter.py dod --ref "/sökväg/till/DoD RPG"
    python3 scripts/bygg_adapter.py mutant2089 --ref "/sökväg/till/Mutant 2089 RPG"

Adaptrarna är snapshots: frödata (attribut, formler, fingeravtryck) ligger här i
skriptet, lexikon utvinns ur referensrepot när det finns. Utan --ref genereras
adaptern enbart från frödata.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYSTEM_ROOT = ROOT / "system"

# Gemensam OCR-förväxlingskatalog (Mutant-repots LATHUND §1/§11 + DoD-alias):
# observerat tecken -> kandidat-kanoniska tecken.
MISREAD_TO_CANONICAL = {
    "I": ["1", "T"], "l": ["1", "T"], "i": ["1"], "|": ["1", "T"],
    "O": ["0"], "o": ["0"], "Q": ["0"],
    "S": ["5"], "s": ["5"], "B": ["8", "3"], "G": ["6"], "b": ["6"],
    "Z": ["2"], "z": ["2"], "g": ["9"], "q": ["9"], "A": ["4"],
    "7": ["T", "7"], "+": ["T", "+"], "D": ["T"], "d": ["T"], "t": ["T"],
}

# Svenska diakritiska förväxlingar för lexikonrättning: OCR-tecken -> alternativ.
DIACRITIC_CONFUSIONS = {
    "a": ["å", "ä"], "o": ["ö"], "e": ["é"], "u": ["ü"],
    "à": ["å", "ä"], "á": ["å", "ä"], "6": ["ö"],
}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
    print("skrev", path.relative_to(ROOT))


def ts_names(path, limit=None):
    """Extrahera `name: '...'`-värden ur en TypeScript-datafil."""
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    names = re.findall(r"name:\s*['\"]([^'\"]+)['\"]", text)
    seen, out = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out[:limit] if limit else out


# ---------------------------------------------------------------------------
# DoD 1991
# ---------------------------------------------------------------------------

DOD_SEED = {
    "system": {
        "id": "dod",
        "name": "Drakar och Demoner",
        "aliases": ["dod", "drakar", "dod1991", "drakar och demoner"],
        "genre": "Fantasy",
        "publisher": "Äventyrsspel / Riot Minds",
        "editions": [
            {"name": "Drakar och Demoner (1982)", "year": 1982},
            {"name": "Drakar och Demoner (1984, andra utgåvan)", "year": 1984},
            {"name": "Drakar och Demoner Expert (1985)", "year": 1985},
            {"name": "Drakar och Demoner (1991)", "year": 1991, "default": True},
        ],
        "default_edition": "1991",
        "attributes": {
            "names": ["STY", "FYS", "SMI", "INT", "PSY", "KAR", "STO"],
            "labels": {
                "STY": "Styrka", "FYS": "Fysik", "SMI": "Smidighet",
                "INT": "Intelligens", "PSY": "Psyke", "KAR": "Karisma",
                "STO": "Storlek",
            },
            "range": {"min": 1, "max": 40, "typical_min": 3, "typical_max": 18},
        },
        "derived_labels": {
            "KP": "Kroppspoäng", "SB": "Skadebonus", "SV": "Skyddsvärde",
            "FV": "Färdighetsvärde", "CL": "Chansläge", "BV": "Brytvärde",
        },
        "derived_checks": [
            {"field": "KP", "formula": "ceil((FYS + STO) / 2)",
             "note": "DoD 1991; äldre utgåvor använder andra formler",
             "editions": ["1991"]},
        ],
        "skill_value": {"style": "fv", "min": 1, "max": 25,
                        "note": "FV 1-20+ (1991); 1984 använder T100-procent"},
    },
    "dice": {
        "notation": "^(\\d+)[Tt](\\d+)([+-]\\d+)?$",
        "sides": [2, 3, 4, 6, 8, 10, 12, 20, 100],
        "misread_to_canonical": MISREAD_TO_CANONICAL,
    },
    "statblock": {
        "required_fields": ["name", "stats"],
        "stats_required": [],
        "stats_allowed": ["STY", "FYS", "SMI", "INT", "PSY", "KAR", "STO",
                          "KP", "SB", "SV", "Farlighet"],
        "skills_value_range": [1, 150],
        "field_labels": {
            "sty": "STY", "styrka": "STY", "fys": "FYS", "fysik": "FYS",
            "smi": "SMI", "smidighet": "SMI", "int": "INT",
            "intelligens": "INT", "psy": "PSY", "psyke": "PSY",
            "kar": "KAR", "karisma": "KAR", "sto": "STO", "storlek": "STO",
            "kp": "KP", "kroppspoäng": "KP", "sb": "SB", "skadebonus": "SB",
            "sv": "SV", "skyddsvärde": "SV", "förflyttning": "Förflyttning",
            "hemvist": "Hemvist", "antal": "Antal", "skräck": "Skräck",
            "farlighet": "Farlighet",
        },
    },
    "detection": {
        "filename_tokens": ["drakar", "demoner", "dod", "ereb", "altor",
                            "riotminds", "aventyrsspel"],
        "strong_terms": ["Drakar och Demoner", "Kroppspoäng", "Skadebonus",
                         "Färdighetsvärde", "Ereb Altor", "besvärjelse",
                         "Spelledarperson"],
        "weak_terms": ["FV", "KP", "SB", "SL", "PSY", "KAR"],
        "attribute_signature": ["STY", "FYS", "SMI", "INT", "PSY", "KAR", "STO"],
    },
    "core_terms": {
        "STY": "Styrka", "FYS": "Fysik", "SMI": "Smidighet",
        "INT": "Intelligens", "PSY": "Psyke", "KAR": "Karisma",
        "STO": "Storlek", "KP": "Kroppspoäng", "SB": "Skadebonus",
        "SV": "Skyddsvärde", "FV": "Färdighetsvärde", "CL": "Chansläge",
        "MP": "Magipunkter", "EP": "Erfarenhetspoäng", "BP": "Bakgrundspoäng",
        "SL": "Spelledare", "RP": "Rollperson", "SLP": "Spelledarperson",
        "SR": "Stridsrunda", "BV": "Brytvärde",
    },
    "core_words": [
        "Färdighet", "Förflyttning", "Kroppspoäng", "Skadebonus", "äventyr",
        "besvärjelse", "rustning", "sköld", "vapen", "magiker", "trollkarl",
        "dvärg", "alv", "halvling", "människa", "svartfolk", "vättar",
        "Grundegenskap", "Baschans", "Hemvist", "Vanlighet", "Naturligt skydd",
    ],
    "aliases": {
        "kortssvard": "Kortsvärd",
        "fardighet": "Färdighet",
        "forflyttning": "Förflyttning",
        "kroppspoang": "Kroppspoäng",
        "svardskonst": "Svärdskonst",
        "aventyr": "äventyr",
        "dvarg": "dvärg",
        "vattar": "vättar",
    },
}


def build_dod(ref):
    seed = DOD_SEED
    cats = {"skills": [], "weapons": [], "armor": [], "spells": [],
            "creatures": [], "races": [], "professions": []}
    sb_table = []
    if ref:
        d91 = ref / "src" / "data" / "dod91"
        cats["skills"] = ts_names(d91 / "skills.ts")
        cats["weapons"] = ts_names(d91 / "equipment.ts")
        cats["spells"] = ts_names(d91 / "spells.ts")
        cats["races"] = ts_names(d91 / "races.ts")
        cats["professions"] = ts_names(d91 / "professions.ts")
        monsters = ref / "data" / "monsters.json"
        if monsters.is_file():
            data = json.loads(monsters.read_text(encoding="utf-8"))
            cats["creatures"] = sorted(
                {m["name"] for m in data.get("monsters", [])})
        tables = d91 / "tables.ts"
        if tables.is_file():
            text = tables.read_text(encoding="utf-8")
            block = re.search(r"SKADEBONUS_TABLE[^\[]*\[(.*?)\n\]", text,
                              re.DOTALL)
            if block:
                for mn, mx, bonus in re.findall(
                        r"min:\s*(-?\d+),\s*max:\s*(\d+),\s*bonus:\s*['\"]([^'\"]*)['\"]",
                        block.group(1)):
                    sb_table.append({"min": int(mn), "max": int(mx),
                                     "bonus": bonus})

    system = dict(seed["system"])
    if sb_table:
        system["sb_table"] = {"input": "STY + STO", "rows": sb_table}

    lexicon = {
        "terms": seed["core_terms"],
        "words": seed["core_words"],
        "categories": {k: v for k, v in cats.items() if v},
        "aliases": seed["aliases"],
        "diacritic_confusions": DIACRITIC_CONFUSIONS,
    }
    out = SYSTEM_ROOT / "dod"
    write(out / "system.json", system)
    write(out / "lexicon.json", lexicon)
    write(out / "dice.json", seed["dice"])
    write(out / "statblock.schema.json", seed["statblock"])
    write(out / "detection.json", seed["detection"])


# ---------------------------------------------------------------------------
# Mutant 2089 (Mutant 2-eran, BRP-släkt — INTE Mutant: År Noll)
# ---------------------------------------------------------------------------

M2089_SEED = {
    "system": {
        "id": "mutant2089",
        "name": "Mutant 2089",
        "aliases": ["mutant", "mutant2089", "mutant 2089", "mutant2",
                    "mutant 2"],
        "genre": "Cyberpunk/postapokalyps",
        "publisher": "Äventyrsspel / Target Games",
        "editions": [
            {"name": "Mutant 2089", "year": 1989, "default": True},
        ],
        "default_edition": "2089",
        "attributes": {
            "names": ["STY", "STO", "INT", "FYS", "PER", "MST", "SMI"],
            "labels": {
                "STY": "Styrka", "STO": "Storlek", "INT": "Intelligens",
                "FYS": "Fysik", "PER": "Personlighet",
                "MST": "Mental Styrka", "SMI": "Smidighet",
            },
            "range": {"min": 1, "max": 40, "typical_min": 3, "typical_max": 18},
        },
        "derived_labels": {
            "KP": "Kroppspoäng", "SB": "Skadebonus", "GCL": "Grundchansläge",
            "CL": "Chansläge", "EP": "Erfarenhetspoäng", "SR": "Stridsrunda",
            "EV": "Eldavbrott", "BGP": "Bakgrundspoäng",
        },
        "derived_checks": [
            {"field": "KP", "formula": "STO + FYS"},
            {"field": "Förflyttning", "formula": "FYS + SMI"},
        ],
        "skill_value": {"style": "percent", "min": 0, "max": 200,
                        "divisible_by": 5,
                        "note": "GCL/CL avrundas alltid till närmaste 5 %"},
        "classes": ["NOM", "PSI", "ROB", "MUT"],
    },
    "dice": {
        "notation": "^(\\d+)[TtDd](\\d+)([+-]\\d+)?$",
        "sides": [4, 6, 8, 10, 20, 100],
        "misread_to_canonical": MISREAD_TO_CANONICAL,
    },
    "statblock": {
        "required_fields": ["name", "stats"],
        "stats_required": [],
        "stats_allowed": ["STY", "STO", "INT", "FYS", "PER", "MST", "SMI",
                          "KP", "SB"],
        "skills_value_range": [0, 200],
        "field_labels": {
            "sty": "STY", "styrka": "STY", "sto": "STO", "storlek": "STO",
            "int": "INT", "intelligens": "INT", "fys": "FYS", "fysik": "FYS",
            "per": "PER", "personlighet": "PER", "mst": "MST",
            "mental styrka": "MST", "smi": "SMI", "smidighet": "SMI",
            "kp": "KP", "kroppspoäng": "KP", "sb": "SB", "skadebonus": "SB",
            "förflyttning": "Förflyttning", "klass": "Klass",
            "ålder": "Ålder", "huvudhand": "Huvudhand",
        },
    },
    "detection": {
        "filename_tokens": ["mutant", "2089", "svot", "krim", "techno",
                            "berlin"],
        "strong_terms": ["Mutant", "Berlin City", "EuroDollar", "korporation",
                         "Mental Styrka", "Grundchansläge", "cybernetik",
                         "mutation"],
        "weak_terms": ["GCL", "CL", "KP", "EV", "PSI", "MST", "PER"],
        "attribute_signature": ["STY", "STO", "INT", "FYS", "PER", "MST",
                                "SMI"],
    },
    "core_terms": {
        "STY": "Styrka", "STO": "Storlek", "INT": "Intelligens",
        "FYS": "Fysik", "PER": "Personlighet", "MST": "Mental Styrka",
        "SMI": "Smidighet", "KP": "Kroppspoäng", "SB": "Skadebonus",
        "GCL": "Grundchansläge", "CL": "Chansläge", "EP": "Erfarenhetspoäng",
        "BGP": "Bakgrundspoäng", "SR": "Stridsrunda", "EV": "Eldavbrott",
        "SL": "Spelledare", "RP": "Rollperson", "SLP": "Spelledarperson",
        "ED": "EuroDollar",
    },
    "core_words": [
        "mutation", "cybernetik", "korporation", "syndikat", "Berlin City",
        "Infokloss", "rippare", "korp", "refugnik", "reglo", "wohner",
        "geier", "dänik", "rasnik", "blau", "flick", "MetroPol",
        "Kroppspoäng", "Förflyttning", "Färdigheter", "träffområde",
        "automateld", "eldskur",
    ],
    "aliases": {
        "sypox": "Syopox",
        "toyfox": "Toytox",
        "brandly's": "Brandy's",
        "obepansrad strid": "Obeväpnad strid",
        "obesväpnad strid": "Obeväpnad strid",
        "rörliga manövrar": "Rörliga manövrer",
        "metropolisen": "MetroPolisen",
    },
}


def build_mutant2089(ref):
    seed = M2089_SEED
    cats = {"skills": [], "weapons": [], "cybernetics": [],
            "proper_nouns": []}
    if ref:
        tab = ref / "build" / "tabeller.json"
        if tab.is_file():
            data = json.loads(tab.read_text(encoding="utf-8"))
            weapons = []
            for key, block in data.items():
                if key.startswith("vapen_") and isinstance(block, dict):
                    for row in block.get("rader", []):
                        n = row.get("namn")
                        if n and n not in weapons:
                            weapons.append(n)
            cats["weapons"] = weapons
        skills = []
        for jf in [ref / "docs" / "rollformulär" / "drex.json"] + \
                sorted((ref / "docs" / "slp").glob("*.json")) + \
                sorted((ref / "docs" / "slp" / "typer").glob("*.json")):
            if not jf.is_file() or jf.name == "relationer.json":
                continue
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
            except Exception:
                continue
            block = data.get("statblock") or data
            if not isinstance(block, dict):
                continue
            for f in block.get("fardigheter") or []:
                n = f.get("namn")
                if n and n not in skills:
                    skills.append(n)
            for c in block.get("cybernetik") or []:
                n = c.get("namn") if isinstance(c, dict) else c
                if n and n not in cats["cybernetics"]:
                    cats["cybernetics"].append(n)
        cats["skills"] = sorted(skills)
        # Egennamn ur LATHUND §10 (kanonisk kolumn)
        lathund = ref / "docs" / "LATHUND.md"
        if lathund.is_file():
            text = lathund.read_text(encoding="utf-8")
            for m in re.finditer(r"^\|\s*\*{0,2}([A-ZÅÄÖ][^|*]+?)\*{0,2}\s*\|",
                                 text, re.MULTILINE):
                name = m.group(1).strip()
                if 2 < len(name) < 40 and name not in cats["proper_nouns"]:
                    cats["proper_nouns"].append(name)

    lexicon = {
        "terms": seed["core_terms"],
        "words": seed["core_words"],
        "categories": {k: v for k, v in cats.items() if v},
        "aliases": seed["aliases"],
        "diacritic_confusions": DIACRITIC_CONFUSIONS,
    }
    out = SYSTEM_ROOT / "mutant2089"
    write(out / "system.json", seed["system"])
    write(out / "lexicon.json", lexicon)
    write(out / "dice.json", seed["dice"])
    write(out / "statblock.schema.json", seed["statblock"])
    write(out / "detection.json", seed["detection"])


BUILDERS = {"dod": build_dod, "mutant2089": build_mutant2089}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("system", choices=sorted(BUILDERS))
    ap.add_argument("--ref", help="sökväg till referensrepot", default=None)
    args = ap.parse_args()
    ref = Path(args.ref).expanduser() if args.ref else None
    if ref and not ref.is_dir():
        sys.exit("referensrepot finns inte: %s" % ref)
    BUILDERS[args.system](ref)


if __name__ == "__main__":
    main()
