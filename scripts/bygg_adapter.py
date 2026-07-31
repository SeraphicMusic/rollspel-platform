#!/usr/bin/env python3
"""Bygg/uppdatera systemadaptrar i system/ från referensrepona.

Användning:
    python3 scripts/bygg_adapter.py dod --ref "/sökväg/till/Drakar och Demoner 1991"
    python3 scripts/bygg_adapter.py mutant2089 --ref "/sökväg/till/Mutant 2089 RPG"

Adaptrarna är snapshots: frödata (attribut, formler, fingeravtryck) ligger här i
skriptet, lexikon utvinns ur referensrepot när det finns. Utan --ref genereras
adaptern enbart från frödata.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
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


class _TSLiteralParser:
    """Liten parser för datalitteralerna i referensrepots TypeScript-filer.

    Den tolkar bara JSON-liknande arrayer/objekt och identifierarvärden. Kod
    exekveras aldrig, vilket gör snapshotbygget deterministiskt och säkert.
    """

    def __init__(self, text):
        self.text = text
        self.pos = 0

    def _skip(self):
        while self.pos < len(self.text):
            if self.text[self.pos].isspace():
                self.pos += 1
            elif self.text.startswith("//", self.pos):
                end = self.text.find("\n", self.pos)
                self.pos = len(self.text) if end < 0 else end + 1
            elif self.text.startswith("/*", self.pos):
                end = self.text.find("*/", self.pos + 2)
                if end < 0:
                    raise ValueError("oavslutad TypeScript-kommentar")
                self.pos = end + 2
            else:
                break

    def _string(self):
        quote = self.text[self.pos]
        self.pos += 1
        out = []
        while self.pos < len(self.text):
            char = self.text[self.pos]
            self.pos += 1
            if char == quote:
                return "".join(out)
            if char == "\\":
                if self.pos >= len(self.text):
                    break
                escaped = self.text[self.pos]
                self.pos += 1
                out.append({"n": "\n", "r": "\r", "t": "\t"}.get(
                    escaped, escaped))
            else:
                out.append(char)
        raise ValueError("oavslutad TypeScript-sträng")

    def _identifier(self):
        match = re.match(r"[A-Za-z_$ÅÄÖåäö][\w$ÅÄÖåäö]*",
                         self.text[self.pos:])
        if not match:
            raise ValueError("förväntade identifierare vid %d" % self.pos)
        self.pos += len(match.group(0))
        return match.group(0)

    def parse(self):
        self._skip()
        if self.pos >= len(self.text):
            raise ValueError("oväntat slut på TypeScript-litteral")
        char = self.text[self.pos]
        if char in "'\"`":
            return self._string()
        if char == "[":
            return self._array()
        if char == "{":
            return self._object()
        number = re.match(r"-?(?:\d+\.\d+|\d+)", self.text[self.pos:])
        if number:
            token = number.group(0)
            self.pos += len(token)
            return float(token) if "." in token else int(token)
        ident = self._identifier()
        if ident == "true":
            return True
        if ident == "false":
            return False
        if ident in ("null", "undefined"):
            return None
        return ident

    def _array(self):
        self.pos += 1
        out = []
        while True:
            self._skip()
            if self.text[self.pos] == "]":
                self.pos += 1
                return out
            if self.text.startswith("...", self.pos):
                self._skip_expression()
                continue
            out.append(self.parse())
            self._skip()
            if self.text[self.pos] == ",":
                self.pos += 1
                continue
            if self.text[self.pos] != "]":
                raise ValueError("förväntade ',' eller ']' vid %d" % self.pos)

    def _skip_expression(self):
        """Hoppa över ett beräknat spread-uttryck fram till nästa arraykomma."""
        depths = {"(": 0, "[": 0, "{": 0}
        closing = {")": "(", "]": "[", "}": "{"}
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char in "'\"`":
                self._string()
                continue
            if self.text.startswith("//", self.pos) or \
                    self.text.startswith("/*", self.pos):
                self._skip()
                continue
            if char in depths:
                depths[char] += 1
            elif char in closing:
                opener = closing[char]
                if char == "]" and not any(depths.values()):
                    return
                depths[opener] -= 1
            elif char == "," and not any(depths.values()):
                self.pos += 1
                return
            self.pos += 1

    def _object(self):
        self.pos += 1
        out = {}
        while True:
            self._skip()
            if self.text[self.pos] == "}":
                self.pos += 1
                return out
            if self.text[self.pos] in "'\"`":
                key = self._string()
            else:
                number = re.match(r"-?\d+(?:\.\d+)?", self.text[self.pos:])
                if number:
                    key = number.group(0)
                    self.pos += len(key)
                else:
                    key = self._identifier()
            self._skip()
            if self.text[self.pos] != ":":
                raise ValueError("förväntade ':' vid %d" % self.pos)
            self.pos += 1
            out[str(key)] = self.parse()
            self._skip()
            if self.text[self.pos] == ",":
                self.pos += 1
                continue
            if self.text[self.pos] != "}":
                raise ValueError("förväntade ',' eller '}' vid %d" % self.pos)


def ts_literal(path, name):
    """Läs en namngiven const-litteral utan att exekvera TypeScript."""
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"(?:export\s+)?const\s+%s(?:\s*:[^=]+)?\s*=" % re.escape(name),
        text)
    if not match:
        raise ValueError("%s saknas i %s" % (name, path))
    return _TSLiteralParser(text[match.end():]).parse()


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _source_commit(ref):
    result = subprocess.run(
        ["git", "-C", str(ref), "rev-parse", "HEAD"],
        capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError("kunde inte läsa git-commit för %s" % ref)
    return result.stdout.strip()


def build_dod91_reference(ref):
    """Exportera fullständiga, versionslåsta DoD91-kataloger."""
    d91 = ref / "src" / "data" / "dod91"
    required = {
        "skills": d91 / "skills.ts",
        "skill_choices": d91 / "skillChoices.ts",
        "equipment": d91 / "equipment.ts",
        "provisions": d91 / "provisions.ts",
        "lakedroger": d91 / "lakedroger.ts",
        "tables": d91 / "tables.ts",
        "rules_markdown": (
            ref / "docs" / "grundregler" /
            "Drakar och Demoner 1991 - Rollpersonen.md"),
        "gm_rules_markdown": (
            ref / "docs" / "grundregler" /
            "Drakar och Demoner 1991 - Spelledarboken.md"),
    }
    missing = [str(path) for path in required.values() if not path.is_file()]
    if missing:
        raise ValueError("DoD91-referensfiler saknas: %s" % ", ".join(missing))

    skills = (ts_literal(required["skills"], "PRIMARY_SKILLS") +
              ts_literal(required["skills"], "SECONDARY_SKILLS"))
    rules_text = required["rules_markdown"].read_text(encoding="utf-8")
    bfv_section = rules_text.split(
        "#### Tabell: B-färdighetsvärden", 1)
    if len(bfv_section) != 2:
        raise ValueError("B-färdighetstabellen saknas i Rollpersonen.md")
    bfv_rows = []
    for fv_text, bfv_text in re.findall(
            r"^\|\s*(\d+(?:[–-]\d+)?)\s*\|\s*(\d)\s*\|",
            bfv_section[1].split("####", 1)[0], re.MULTILINE):
        bounds = re.split(r"[–-]", fv_text)
        bfv_rows.append({
            "fv_min": int(bounds[0]),
            "fv_max": int(bounds[-1]),
            "bfv": int(bfv_text),
        })
    if len(bfv_rows) != 6:
        raise ValueError("kunde inte läsa hela B-färdighetstabellen")
    gm_rules_text = required["gm_rules_markdown"].read_text(encoding="utf-8")
    resistance_section = gm_rules_text.split(
        "## **MOTSTÅNDSTABELLEN**", 1)
    if len(resistance_section) != 2:
        raise ValueError("Motståndstabellen saknas i Spelledarboken.md")
    resistance_rows = []
    resistance_block = resistance_section[1].split(
        "### **Svårighetsgrader", 1)[0]
    for line in resistance_block.splitlines():
        cells = [cell.strip().replace("*", "")
                 for cell in line.strip().strip("|").split("|")]
        if not cells or not cells[0].isdigit() or len(cells) != 22:
            continue
        chances = []
        for cell in cells[1:]:
            token = cell.replace("\\", "")
            if token == "—":
                chances.append("automatic_success")
            elif token == "†":
                chances.append("automatic_failure")
            elif token.isdigit():
                chances.append(int(token))
            else:
                raise ValueError(
                    "okänd cell i Motståndstabellen: %r" % cell)
        resistance_rows.append({
            "resistance": int(cells[0]),
            "chances": chances,
        })
    if len(resistance_rows) != 21:
        raise ValueError("kunde inte läsa hela Motståndstabellen")
    choices = {
        "languages": ts_literal(required["skill_choices"], "LANGUAGES"),
        "instrument_groups": ts_literal(
            required["skill_choices"], "INSTRUMENT_GROUPS"),
        "crafts": ts_literal(required["skill_choices"], "CRAFTS"),
        "martial_techniques": ts_literal(
            required["skill_choices"], "MARTIAL_TECHNIQUES"),
        "magic_schools": ts_literal(
            required["skill_choices"], "MAGIC_SCHOOLS"),
        "weapon_groups": ts_literal(
            required["skill_choices"], "WEAPON_GROUPS"),
    }
    for group in choices["instrument_groups"]:
        skills.append({
            "id": "spela_" + re.sub(r"[^a-z0-9]+", "_",
                                     _ascii_lower(group["name"])).strip("_"),
            "name": "Spela " + group["name"].lower(),
            "linkedAttribute": "KAR",
            "scale": "A",
            "isPrimary": False,
            "dynamic": "instrument",
        })
    for craft in choices["crafts"]:
        skills.append({
            "id": "hantverk:" + re.sub(r"[^a-z0-9]+", "_",
                                        _ascii_lower(craft["name"])).strip("_"),
            "name": craft["name"],
            "linkedAttribute": craft["linkedAttribute"],
            "scale": "A",
            "isPrimary": False,
            "dynamic": "craft",
        })

    equipment_path = required["equipment"]
    weapons = []
    for variable, weapon_type in (
            ("MELEE_WEAPONS", "melee"), ("RANGED_WEAPONS", "ranged"),
            ("THROWN_WEAPONS", "thrown")):
        for item in ts_literal(equipment_path, variable):
            item["type"] = weapon_type
            weapons.append(item)
    weapon_groups = ts_literal(equipment_path, "WEAPON_TO_GROUP")
    for weapon in weapons:
        weapon["weaponGroup"] = weapon_groups.get(weapon["name"])

    armor = []
    for variable, armor_type in (
            ("FULL_ARMORS", "full"), ("HELMETS", "helmet"),
            ("ARM_GUARDS", "arm"), ("LEG_GUARDS", "leg"),
            ("TORSO_ARMOR", "torso")):
        for item in ts_literal(equipment_path, variable):
            item["type"] = armor_type
            armor.append(item)

    snapshots = {
        "skills.json": {"ruleset": "dod91", "skills": skills,
                        "choices": choices, "bfv_table": bfv_rows},
        "weapons.json": {"ruleset": "dod91", "weapons": weapons},
        "shields.json": {"ruleset": "dod91", "shields": ts_literal(
            equipment_path, "SHIELDS")},
        "armor.json": {"ruleset": "dod91", "armor": armor},
        "equipment.json": {"ruleset": "dod91", "equipment": ts_literal(
            equipment_path, "GENERAL_ITEMS"),
                           "lodging": ts_literal(equipment_path, "LODGING")},
        "provisions.json": {"ruleset": "dod91", "provisions": ts_literal(
            required["provisions"], "PROVISIONS")},
        "lakedroger.json": {"ruleset": "dod91", "lakedroger": ts_literal(
            required["lakedroger"], "LAKEDROGER")},
        "tables.json": {
            "ruleset": "dod91",
            "attribute_bp_cost": ts_literal(
                required["tables"], "ATTRIBUTE_BP_COST"),
            "sto_increase_cost": ts_literal(
                required["tables"], "STO_INCREASE_COST"),
            "sto_decrease_refund": ts_literal(
                required["tables"], "STO_DECREASE_REFUND"),
            "skadebonus": ts_literal(required["tables"], "SKADEBONUS_TABLE"),
            "startkapital": ts_literal(
                required["tables"], "STARTKAPITAL_TABLE"),
            "kp_locations": ts_literal(
                required["tables"], "KP_LOCATION_TABLE"),
            "movement": ts_literal(
                required["tables"], "FORFLYTTNING_TABLE"),
            "age_modifiers": ts_literal(required["tables"], "AGE_MODIFIERS"),
            "age_ranges": ts_literal(required["tables"], "AGE_RANGES"),
            "special_abilities": ts_literal(
                required["tables"], "SARSKILDA_FORMAGOR_TABLE"),
            "sto_weight": ts_literal(
                required["tables"], "STO_WEIGHT_TABLE"),
            "resistance_table": {
                "die": "1T20",
                "success": "roll <= chance",
                "active_values": list(range(1, 22)),
                "rows": resistance_rows,
            },
        },
    }
    out = SYSTEM_ROOT / "dod" / "reference" / "dod91"
    checksums = {}
    for filename, data in snapshots.items():
        write(out / filename, data)
        checksums[filename] = _sha256(out / filename)
    catalog = {
        "ruleset": "dod91",
        "source_repository": "Drakar och Demoner 1991",
        "source_path": str(ref.resolve()),
        "source_commit": _source_commit(ref),
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checksums": checksums,
        "source_checksums": {
            path.name: _sha256(path) for path in required.values()
        },
    }
    write(out / "catalog.json", catalog)


def _ascii_lower(value):
    import unicodedata
    return unicodedata.normalize("NFKD", value).encode(
        "ascii", "ignore").decode("ascii").lower()


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
    # Ritualmodifierare — skrivs i versaler i äventyrstext ("FÖRTROLLA VAPEN
    # E1 s15, SIGILL med PERMANENS"). Finns inte i dod91-datan i referensrepot,
    # därför frödata här så de överlever en regenerering.
    "ritual_terms": ["SIGILL", "PERMANENS", "NEXUS"],
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
            "creatures": [], "races": [], "professions": [],
            "ritual_terms": list(seed["ritual_terms"])}
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
    if ref:
        build_dod91_reference(ref)


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
        # 2 och 3 ingår: Mutant-materialet använder 1T3 (slå 1T6, halvera
        # uppåt), t.ex. Sinkadus 34 "efter ytterligare 1T3 dagar", och 1T2,
        # t.ex. Sinkadus 1989 "I drakens klor" ("1T2 Personal", "1T2-1 man").
        # Utan dem flaggar valideraren varje förekomst som ogiltig notation.
        "sides": [2, 3, 4, 6, 8, 10, 20, 100],
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
        # OBS: inget "sypox"-alias. Referensrepots LATHUND §10 normaliserar
        # Sypox -> Syopox ("Syopox ×9 i prosan"), men den räkningen är själv en
        # OCR-artefakt: trycket i Attentat Sypox säger Sypox i både displaytitel
        # och prosa (pixelverifierat vid 6-20x på den inbäddade skanningen).
        # Ett alias hit skulle rätta FRÅN den tryckta formen, inte till den.
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
