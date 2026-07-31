"""Profil- och kataloguppslag för äventyrskonvertering."""
import json
import hashlib
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE_ROOT = ROOT / "system" / "dod" / "conversion"
REFERENCE_ROOT = ROOT / "system" / "dod" / "reference"


class ProfileError(ValueError):
    pass


def normalize_name(value):
    value = unicodedata.normalize("NFKD", str(value))
    value = value.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def load_profile(source, target):
    if source != "dod-t100" or target != "dod91":
        raise ProfileError("profilen %s -> %s stöds inte" % (source, target))
    path = PROFILE_ROOT / ("%s-to-%s.json" % (source, target))
    if not path.is_file():
        raise ProfileError("konverteringsprofil saknas: %s" % path)
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProfileError("ogiltig konverteringsprofil: %s" % exc)
    required = {"id", "version", "source", "target", "fv",
                "skill_aliases", "weapon_aliases", "armor_aliases",
                "monster_aliases"}
    if required - set(profile):
        raise ProfileError("profilen saknar: %s" %
                           ", ".join(sorted(required - set(profile))))
    if profile["source"] != source or profile["target"] != target:
        raise ProfileError("profilens käll-/mål-id stämmer inte")
    if not isinstance(profile["version"], int) or profile["version"] < 1:
        raise ProfileError("profilversionen måste vara ett positivt heltal")
    fv = profile.get("fv")
    if not isinstance(fv, dict) or \
            not {"formula", "minimum", "maximum"} <= set(fv):
        raise ProfileError("profilens FV-regel är ofullständig")
    if fv["formula"] != "round(value / 5)" or \
            not isinstance(fv["minimum"], int) or \
            not isinstance(fv["maximum"], int) or \
            fv["minimum"] > fv["maximum"]:
        raise ProfileError("profilens FV-regel är ogiltig")
    for field in ("skill_aliases", "weapon_aliases", "armor_aliases",
                  "monster_aliases"):
        if not isinstance(profile[field], dict):
            raise ProfileError("%s måste vara ett objekt" % field)
    skill_splits = profile.get("skill_splits", {})
    if not isinstance(skill_splits, dict) or any(
            not isinstance(targets, list) or len(targets) < 2 or
            not all(isinstance(target, str) and target for target in targets)
            for targets in skill_splits.values()):
        raise ProfileError("skill_splits måste ange minst två målfärdigheter")
    profile["skill_splits"] = skill_splits
    shield_aliases = profile.get("shield_aliases", {})
    if not isinstance(shield_aliases, dict):
        raise ProfileError("shield_aliases måste vara ett objekt")
    profile["shield_aliases"] = shield_aliases
    return profile


def convert_fv(value, profile):
    """Symmetrisk heltalsavrundning för positiva T100-värden."""
    fv = profile["fv"]
    converted = int(float(value) / 5 + 0.5)
    return max(int(fv["minimum"]), min(int(fv["maximum"]), converted))


def convert_modifier(value, profile):
    """Modifikator i T100-procentenheter till FV-steg.

    Till skillnad från convert_fv klamps resultatet inte till FV-intervallet:
    en modifikator är ett delta på slaget, inte ett färdighetsvärde, och
    ett avdrag på -4 ligger med flit utanför [minimum, maximum].
    """
    del profile  # samma femtedelsskala som convert_fv, utan klampning
    sign = -1 if value < 0 else 1
    return sign * int(abs(float(value)) / 5 + 0.5)


class Catalog:
    def __init__(self, ruleset="dod91", root=None):
        self.root = Path(root) if root else REFERENCE_ROOT / ruleset
        try:
            self.catalog = self._read("catalog.json")
            self.skills_data = self._read("skills.json")
            self.weapons_data = self._read("weapons.json")
            self.armor_data = self._read("armor.json")
            self.shields_data = self._read("shields.json")
            self.tables_data = self._read("tables.json")
        except (OSError, ValueError, KeyError) as exc:
            raise ProfileError("DoD91-katalogen kunde inte läsas: %s" % exc)
        if self.catalog.get("ruleset") != ruleset:
            raise ProfileError("fel ruleset i DoD91-katalogen")
        checksums = self.catalog.get("checksums")
        if not isinstance(checksums, dict):
            raise ProfileError("DoD91-katalogen saknar checksummor")
        required_snapshots = {
            "skills.json", "weapons.json", "shields.json", "armor.json",
            "equipment.json", "provisions.json", "lakedroger.json",
            "tables.json",
        }
        if required_snapshots - set(checksums):
            raise ProfileError("DoD91-katalogen saknar snapshotchecksummor")
        for filename, expected in checksums.items():
            path = self.root / filename
            if not path.is_file() or self._sha256(path) != expected:
                raise ProfileError(
                    "checksumma stämmer inte för DoD91-snapshot %s" %
                    filename)
        self.skills = self._unique_index(
            self.skills_data.get("skills", []), "färdigheter")
        self.skills_by_id = {
            item["id"]: item for item in self.skills_data.get("skills", [])
            if item.get("id")
        }
        self.bfv_table = self.skills_data.get("bfv_table")
        if not isinstance(self.bfv_table, list) or len(self.bfv_table) != 6:
            raise ProfileError("DoD91-katalogen saknar B-FV-tabellen")
        self.weapons = self._unique_index(
            self.weapons_data.get("weapons", []), "vapen")
        self.armor = self._multi_index(self.armor_data.get("armor", []))
        self.shields = self._unique_index(
            self.shields_data.get("shields", []), "sköldar")
        resistance_table = self.tables_data.get("resistance_table")
        if not isinstance(resistance_table, dict) or \
                len(resistance_table.get("rows", [])) != 21:
            raise ProfileError("DoD91-katalogen saknar Motståndstabellen")

    def _read(self, filename):
        return json.loads((self.root / filename).read_text(encoding="utf-8"))

    @staticmethod
    def _sha256(path):
        h = hashlib.sha256()
        with open(path, "rb") as source:
            for block in iter(lambda: source.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()

    @staticmethod
    def _unique_index(items, label):
        out = {}
        for item in items:
            key = normalize_name(item["name"])
            if key in out:
                raise ProfileError("tvetydigt namn i katalogen %s: %s" %
                                   (label, item["name"]))
            out[key] = item
        return out

    @staticmethod
    def _multi_index(items):
        out = {}
        for item in items:
            out.setdefault(normalize_name(item["name"]), []).append(item)
        return out

    @staticmethod
    def _alias_target(name, aliases):
        normalized = normalize_name(name)
        normalized_aliases = {
            normalize_name(key): value for key, value in aliases.items()
        }
        return normalized_aliases.get(normalized, name)

    def skill(self, name, aliases):
        target = self._alias_target(name, aliases)
        return self.skills.get(normalize_name(target))

    def weapon(self, name, aliases):
        target = self._alias_target(name, aliases)
        return self.weapons.get(normalize_name(target))

    def shield(self, name, aliases):
        target = self._alias_target(name, aliases)
        return self.shields.get(normalize_name(target))

    def armor_item(self, name, aliases, body_part=None):
        target = self._alias_target(name, aliases)
        matches = self.armor.get(normalize_name(target), [])
        if body_part:
            matches = [item for item in matches
                       if normalize_name(item.get("bodyPart", "")) ==
                       normalize_name(body_part)]
        if len(matches) == 1:
            return matches[0]
        return None

    def bfv(self, fv):
        for row in self.bfv_table:
            if row["fv_min"] <= fv <= row["fv_max"]:
                return row["bfv"]
        return None

    def has_rule(self, rule_id):
        if rule_id == "resistance_table":
            return bool(self.tables_data.get("resistance_table"))
        return False
