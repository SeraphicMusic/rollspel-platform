"""Kandidatidentifiering och minimal tillämpning i kanonisk bok-JSON."""
import copy
import math
import re

from .conversion_records import (make_record, validate_change_coverage,
                                 validate_skill_merges)
from .conversion_rules import convert_fv, convert_modifier

_PERCENT_CANDIDATE = re.compile(
    r"(?<!\w)([A-ZÅÄÖ][A-Za-zÅÄÖåäöÉé-]*"
    r"(?:\s+[A-Za-zÅÄÖåäöÉé-]+){0,2})\s+(\d{1,3})\s*%")
_SOURCE_NOTATION = re.compile(r"\(B[0-5]\)|\bB[0-5]\b", re.IGNORECASE)
_SOURCE_RULE_REFERENCE = re.compile(
    r"\b(?:1?T100|grundchans(?:en)?)\b", re.IGNORECASE)
_TARGET_RULE_REFERENCE = re.compile(
    r"\b(?:motståndstabell(?:en)?|baschans(?:en)?)\b", re.IGNORECASE)
_INT = re.compile(r"^\s*(\d{1,3})\s*%?\s*$")
_WEAPON_LINE = re.compile(
    r"(?i)\bvapen\s*:\s*([A-ZÅÄÖ][A-Za-zÅÄÖåäöÉé ()-]*?)"
    r"(?:\s*(?:,?\s*skada\s*)?(\d+T\d+(?:[+-]\d+)?))?"
    r"(?=\s*(?:[,;.\n]|$))")
_ARMOR_LINE = re.compile(
    r"(?i)\brustning\s*:\s*([A-ZÅÄÖ][A-Za-zÅÄÖåäöÉé ()-]*?)"
    r"(?:\s*,?\s*ABS\s*(\d+))?(?=\s*(?:[,;.\n]|$))")
_ATTRIBUTE_PERCENT_MODIFIER = re.compile(
    r"\b([A-ZÅÄÖ][A-Za-zÅÄÖåäöÉé-]+s\s+"
    r"(?:STY|FYS|SMI|INT|PSY|KAR|STO))\s*[x×]\s*5\s*%",
    re.IGNORECASE)
_ROLL_MODIFIER = re.compile(
    r"(?<![\w%])([+\-−–—])\s*(\d{1,3})\s*"
    r"(?:procentenheter|procent|%)?\s*"
    r"(på|i)\s+(slaget|slagen|kastet|färdighetsslaget|chansen|CL)"
    r"(?![\wÅÄÖåäö])",
    re.IGNORECASE)
_PARENTHESISED_PERCENT = re.compile(
    # "Stor sköld (85%, abs 16)" — färdighetsvärdet står inuti en parentes och
    # föregås därför inte av sitt namn, vilket gör att varken namndetektorn
    # eller _PERCENT_CANDIDATE ser det.
    r"([A-ZÅÄÖ][A-Za-zÅÄÖåäöÉé ,-]*?)\s*\(\s*(\d{1,3})\s*%")
_ABSORPTION = re.compile(r"\babs\s*\d{1,3}", re.IGNORECASE)
_CL_PERCENT_WITH_BFV = re.compile(
    r"(?<!\w)(\d{1,3})\s*%\s*CL\s*\(\s*FV\s*B([0-5])\s*\)", re.IGNORECASE)
_SOURCE_LANGUAGE_SKILL = re.compile(
    r"^(?:tala|läsa(?:\s*(?:/|och)\s*skriva))\s+\S.+$",
    re.IGNORECASE)
_LANGUAGE_PERCENT = re.compile(
    r"(?<![\wÅÄÖåäö])"
    r"((?:Tala|Läsa\s*(?:/|och)\s*skriva)\s+"
    r"[A-ZÅÄÖ][A-Za-zÅÄÖåäöÉé-]*)\s+"
    r"(?:FV\s*)?(\d{1,3})\s*%"
    r"(\s*\(B([0-5])\))?",
    re.IGNORECASE)
_LANGUAGE_SKILL_IN_PROSE = re.compile(
    # Kravet på föregående preposition skiljer färdighetsomnämnandet ("mer på
    # Läsa/Skriva Zorakiska") från verbet ("som kan tala zorakiska"), som inte
    # ska röras. Språknamnen måste vara versaliserade, därav inget IGNORECASE.
    r"(?<![\wÅÄÖåäö])(på|i)\s+"
    r"(?:[Tt]ala|[Ll]äsa\s*(?:/|och)\s*[Ss]kriva)\s+"
    r"[A-ZÅÄÖ][A-Za-zÅÄÖåäö-]*"
    r"(?:\s*,\s*[A-ZÅÄÖ][A-Za-zÅÄÖåäö-]*)*"
    r"(?:\s*(?:eller|och)\s+[A-ZÅÄÖ][A-Za-zÅÄÖåäö-]*)?")
_LANGUAGE_CL = re.compile(
    r"(?<!\w)CL\s*(\d{1,3})\s*%\+?\s*"
    r"\(FV\s*B([0-5])\)\s+i\s+"
    r"([A-ZÅÄÖ][A-Za-zÅÄÖåäöÉé-]*)",
    re.IGNORECASE)


def _integer(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        match = _INT.match(value)
        if match:
            return int(match.group(1))
    return None


def _region(element):
    source = element.get("source") or {}
    return source.get("region") or element.get("region") or "okänd"


def _record(element, page, original, converted, rule, profile, reason,
            location, category, applied=True, review=False, confidence=1.0,
            blocking=None):
    return make_record(
        element.get("id", "okänt"), page, _region(element), original,
        converted, rule, profile, reason, confidence=confidence,
        applied=applied, needs_review=review, location=location,
        category=category, blocking=blocking)


def _skill_names(catalog, profile):
    names = {item["name"] for item in catalog.skills.values()}
    names.update(profile.get("skill_aliases", {}).keys())
    names.update(item["name"] for item in catalog.weapons.values())
    names.update(profile.get("weapon_aliases", {}).keys())
    return sorted(names, key=len, reverse=True)


def _skill_target(name, catalog, profile):
    target = catalog.skill(name, profile["skill_aliases"])
    if target:
        return target, "fv.divide-by-five", "skill_value", "färdigheten"
    if _SOURCE_LANGUAGE_SKILL.match(name):
        target = catalog.skill("Språkkunskap", {})
        if target:
            return (target, "skill.language-unified", "skill_value",
                    "den samlade språkfärdigheten")
    weapon = catalog.weapon(name, profile["weapon_aliases"])
    if weapon and weapon.get("weaponGroup"):
        target = catalog.skills_by_id.get(weapon["weaponGroup"])
        if target:
            return target, "fv.weapon-group", "weapon_skill", "vapengruppen"
    return None, None, None, None


def _convert_text(text, element, page, location, profile, catalog):
    """Konvertera endast säkra färdighetsintervall; returnera text och poster."""
    records = []
    changes = []
    replacements = []
    value_spans = []
    b_notation_spans = []
    names = _skill_names(catalog, profile)

    # DoD91-projektets husregel ersätter alla separata Tala- och
    # Läsa/Skriva-färdigheter med den enda färdigheten Språkkunskap.
    language_target = catalog.skill("Språkkunskap", {})
    if language_target:
        for match in _LANGUAGE_PERCENT.finditer(text):
            source_name, raw = match.group(1), match.group(2)
            converted_value = convert_fv(int(raw), profile)
            converted = "%s FV %d" % (
                language_target["name"], converted_value)
            if match.group(3):
                target_bfv = catalog.bfv(converted_value)
                if target_bfv is not None:
                    converted += " (B%d)" % target_bfv
                b_notation_spans.append((match.start(3), match.end(3)))
            original = match.group(0)
            replacements.append((match.start(), match.end(), converted))
            value_spans.append((match.start(2), match.end(2)))
            rec_location = dict(location)
            rec_location["text_range"] = [match.start(), match.end()]
            record = _record(
                element, page, original, converted,
                "skill.language-unified", profile,
                "%s ersätts av DoD91-husregelns samlade Språkkunskap" %
                source_name, rec_location, "skill_value")
            records.append(record)
            changes.append((record["element_id"],
                            record["source"]["location"],
                            original, converted))

        for match in _LANGUAGE_CL.finditer(text):
            # Erebosiska är rollpersonernas modersmål och talas redan
            # flytande enligt husregeln. Den gamla höga modersmålschansen ska
            # därför inte skapa FV 20/B5; språkkravet uttrycks med den samlade
            # normala tröskeln Språkkunskap FV 10.
            converted = "%s FV 10" % language_target["name"]
            original = match.group(0)
            replacements.append((match.start(), match.end(), converted))
            value_spans.append((match.start(), match.end()))
            b_notation_spans.append((match.start(), match.end()))
            rec_location = dict(location)
            rec_location["text_range"] = [match.start(), match.end()]
            record = _record(
                element, page, original, converted,
                "skill.language-unified", profile,
                "%s är modersmålet och talas flytande; den gamla särskilda "
                "modersmålschansen ersätts av husregelns Språkkunskap FV 10" %
                match.group(3),
                rec_location, "skill_value")
            records.append(record)
            changes.append((record["element_id"],
                            record["source"]["location"],
                            original, converted))

        # Uppräkningar av enskilda språk ("på Läsa/Skriva Zorakiska, Kardiska
        # eller Trakoriska") saknar eget värde och fångas därför varken av
        # _LANGUAGE_PERCENT eller _LANGUAGE_CL. Husregeln gäller ändå: hela
        # uppräkningen ersätts av den samlade färdigheten.
        for match in _LANGUAGE_SKILL_IN_PROSE.finditer(text):
            if any(start < match.end() and match.start() < end
                   for start, end, _ in replacements):
                continue
            original = match.group(0)
            converted = "%s %s" % (match.group(1), language_target["name"])
            replacements.append((match.start(), match.end(), converted))
            rec_location = dict(location)
            rec_location["text_range"] = [match.start(), match.end()]
            record = _record(
                element, page, original, converted,
                "skill.language-unified", profile,
                "Uppräkningen av enskilda språkfärdigheter ersätts av "
                "DoD91-husregelns samlade Språkkunskap", rec_location,
                "skill_value")
            records.append(record)
            changes.append((record["element_id"],
                            record["source"]["location"],
                            original, converted))

    if names:
        pattern = re.compile(
            r"(?<![\wÅÄÖåäö])(" +
            "|".join(re.escape(name) for name in names) +
            r")\s+(?:FV\s*)?(\d{1,3})\s*%"
            r"(\s*\(B([0-5])\))?",
            re.IGNORECASE)
        for match in pattern.finditer(text):
            if any(start < match.end() and match.start() < end
                   for start, end, _ in replacements):
                continue
            source_name, raw = match.group(1), match.group(2)
            target, rule, category, reason_kind = _skill_target(
                source_name, catalog, profile)
            if not target:
                continue
            value = int(raw)
            converted_value = convert_fv(value, profile)
            converted = "%s FV %d" % (target["name"], converted_value)
            if match.group(3):
                target_bfv = catalog.bfv(converted_value)
                if target_bfv is not None:
                    converted += " (B%d)" % target_bfv
                b_notation_spans.append((match.start(3), match.end(3)))
            original = match.group(0)
            replacements.append((match.start(), match.end(), converted))
            value_spans.append((match.start(2), match.end(2)))
            rec_location = dict(location)
            rec_location["text_range"] = [match.start(), match.end()]
            record = _record(
                element, page, original, converted, rule, profile,
                "Explicit procentvärde kopplat till %s %s" %
                (reason_kind, target["name"]), rec_location, category)
            records.append(record)
            changes.append((record["element_id"], record["source"]["location"],
                            original, converted))

    # "50% CL (FV B3)" är ett T100-tröskelvärde med DoD91-notationen redan
    # utsatt inom parentes. FV räknas om ur procenttalet; B-nivån räknas om ur
    # det nya FV:t på samma sätt som för färdighetsvärden.
    for match in _CL_PERCENT_WITH_BFV.finditer(text):
        converted_value = convert_fv(int(match.group(1)), profile)
        converted = "FV %d" % converted_value
        target_bfv = catalog.bfv(converted_value)
        if target_bfv is not None:
            converted += " (B%d)" % target_bfv
        original = match.group(0)
        replacements.append((match.start(), match.end(), converted))
        value_spans.append((match.start(), match.end()))
        b_notation_spans.append((match.start(), match.end()))
        rec_location = dict(location)
        rec_location["text_range"] = [match.start(), match.end()]
        record = _record(
            element, page, original, converted, "fv.divide-by-five", profile,
            "T100-tröskeln uttrycks som DoD91-FV; B-nivån räknas om ur det "
            "konverterade FV:t", rec_location, "skill_value")
        records.append(record)
        changes.append((record["element_id"], record["source"]["location"],
                        original, converted))

    for match in _PARENTHESISED_PERCENT.finditer(text):
        if any(start < match.end() and match.start() < end
               for start, end, _ in replacements):
            continue
        owner, raw = match.group(1).strip(), int(match.group(2))
        converted_value = convert_fv(raw, profile)
        original = match.group(0)
        shield = catalog.shield(owner, profile["shield_aliases"])
        name = shield["name"] if shield else owner
        converted = "%s (FV %d" % (name, converted_value)
        replacements.append((match.start(), match.end(), converted))
        value_spans.append((match.start(2), match.end(2)))
        rec_location = dict(location)
        rec_location["text_range"] = [match.start(), match.end()]
        record = _record(
            element, page, original, converted, "fv.divide-by-five", profile,
            "Procentvärde på T100-skalan inuti parentes efter %r räknas om "
            "till FV%s" % (owner, "; sköldnamnet normaliseras mot katalogen"
                           if shield and name != owner else ""),
            rec_location, "skill_value")
        records.append(record)
        changes.append((record["element_id"], record["source"]["location"],
                        original, converted))
        if shield and shield.get("bv") is not None:
            # Användarbeslut 2026-07-29: källans absorptionsvärde för sköldar
            # fyller samma funktion som DoD91:s brytvärde och ersätts av
            # katalogens BV. Sköldens abs är alltså INTE samma sak som en
            # rustnings abs, som lämnas orörd.
            closing = text.find(")", match.end())
            tail = _ABSORPTION.search(text, match.end())
            if tail and closing != -1 and tail.end() <= closing and not any(
                    start < tail.end() and tail.start() < end
                    for start, end, _ in replacements):
                abs_original = tail.group(0)
                abs_converted = "BV %s" % shield["bv"]
                replacements.append(
                    (tail.start(), tail.end(), abs_converted))
                abs_location = dict(location)
                abs_location["text_range"] = [tail.start(), tail.end()]
                record = _record(
                    element, page, abs_original, abs_converted,
                    "shield.absorption-to-bv", profile,
                    "DoD91-sköldar anges med brytvärde, inte absorption; "
                    "katalogens BV för %s ersätter källans %r"
                    % (shield["name"], abs_original), abs_location, "armor")
                records.append(record)
                changes.append((record["element_id"],
                                record["source"]["location"],
                                abs_original, abs_converted))
        elif not (catalog.weapon(owner, profile["weapon_aliases"])
                  or catalog.armor_item(owner, profile["armor_aliases"])
                  or catalog.skill(owner, profile["skill_aliases"])):
            # Skalan är deterministisk och konverteras; namnet är en egen
            # fråga och flaggas när katalogen inte känner igen det.
            records.append(_record(
                element, page, owner, owner, "term.unmatched", profile,
                "%r saknar motsvarighet i DoD91-katalogen; värdet är omräknat "
                "men termen behöver mänsklig kontroll" % owner, rec_location,
                "unmatched_term", applied=False, review=True, confidence=0.6))

    # Modifikatorer angivna i T100-procentenheter ("-20 på slaget") blir
    # obrukbara på FV-skalan: -20 gör slaget omöjligt på 1T20. Bara värden som
    # är omöjliga som DoD91-modifikator räknas om automatiskt — ligger värdet
    # inom FV-intervallet går det inte att avgöra vilken skala som avses, och
    # då flaggas det i stället för granskning.
    maximum = int(profile["fv"]["maximum"])
    for match in _ROLL_MODIFIER.finditer(text):
        if any(start < match.end() and match.start() < end
               for start, end, _ in replacements):
            continue
        sign, magnitude = match.group(1), int(match.group(2))
        original = match.group(0)
        rec_location = dict(location)
        rec_location["text_range"] = [match.start(), match.end()]
        if magnitude <= maximum:
            records.append(_record(
                element, page, original, original,
                "modifier.ambiguous-scale", profile,
                "Modifikatorn ryms på både T100- och FV-skalan; vilken som "
                "avses går inte att avgöra automatiskt", rec_location,
                "derived_value", applied=False, review=True, confidence=0.5))
            continue
        value = convert_modifier(-magnitude if sign != "+" else magnitude,
                                 profile)
        converted = "%s%d %s %s" % (sign, abs(value), match.group(3),
                                    match.group(4))
        replacements.append((match.start(), match.end(), converted))
        value_spans.append((match.start(), match.end()))
        record = _record(
            element, page, original, converted,
            "modifier.percent-points-to-fv", profile,
            "Modifikatorn är angiven i T100-procentenheter och är omöjlig på "
            "FV-skalan (maximum %d); den räknas om till FV-steg" % maximum,
            rec_location, "derived_value")
        records.append(record)
        changes.append((record["element_id"], record["source"]["location"],
                        original, converted))

    for match in _ATTRIBUTE_PERCENT_MODIFIER.finditer(text):
        original = match.group(0)
        owner, attribute = match.group(1).rsplit(" ", 1)
        converted = "%s aktuella %s" % (owner, attribute.upper())
        replacements.append((match.start(), match.end(), converted))
        # Hindra den generella procentdetektorn från att felklassa samma
        # intervall som ett okänt färdighetsvärde.
        value_spans.append((match.start(), match.end()))
        rec_location = dict(location)
        rec_location["text_range"] = [match.start(), match.end()]
        record = _record(
            element, page, original, converted,
            "modifier.attribute-times-five-percent", profile,
            "T100-avdraget attribut × 5 procentenheter motsvarar "
            "attributets aktuella värde som FV-avdrag i DoD91",
            rec_location, "derived_value")
        records.append(record)
        changes.append((record["element_id"], record["source"]["location"],
                        original, converted))

    for match in _PERCENT_CANDIDATE.finditer(text):
        number_span = (match.start(2), match.end(2))
        if any(a <= number_span[0] and number_span[1] <= b
               for a, b in value_spans):
            continue
        name = match.group(1)
        if normalize_candidate(name).split(" ", 1)[0] in {
                "det", "en", "ett", "den", "chansen", "sannolikheten",
                "cirka"}:
            continue
        original = match.group(0)
        rec_location = dict(location)
        rec_location["text_range"] = [match.start(), match.end()]
        records.append(_record(
            element, page, original, original, "skill.unmatched",
            profile, "Procentvärdet ser ut som FV men färdighetsnamnet %r "
            "saknar entydig katalogträff" % name, rec_location,
            "unmatched_term", applied=False, review=True, confidence=0.55))

    for match in _SOURCE_NOTATION.finditer(text):
        if any(a <= match.start() and match.end() <= b
               for a, b in b_notation_spans):
            continue
        rec_location = dict(location)
        rec_location["text_range"] = [match.start(), match.end()]
        records.append(_record(
            element, page, match.group(0), match.group(0),
            "bfv.target-native", profile,
            "B-FV är redan giltig DoD91-notation; utan ett exakt intilliggande "
            "FV behövs ingen ändring", rec_location, "skill_level",
            applied=False, review=False,
            confidence=1.0))

    for match in _SOURCE_RULE_REFERENCE.finditer(text):
        rec_location = dict(location)
        rec_location["text_range"] = [match.start(), match.end()]
        records.append(_record(
            element, page, match.group(0), match.group(0),
            "rules-reference.source-only", profile,
            "Regelhänvisningen hör till källsystemet och saknar en "
            "automatisk DoD91-översättning", rec_location, "rule_reference",
            applied=False, review=True, confidence=1.0))

    for match in _TARGET_RULE_REFERENCE.finditer(text):
        if match.group(0).lower().startswith("motstånd") and \
                not catalog.has_rule("resistance_table"):
            continue
        rec_location = dict(location)
        rec_location["text_range"] = [match.start(), match.end()]
        records.append(_record(
            element, page, match.group(0), match.group(0),
            "rules-reference.target-native", profile,
            "Regelhänvisningen finns i DoD91 och behålls oförändrad",
            rec_location, "rule_reference", applied=False, review=False,
            confidence=1.0))

    for pattern, kind in ((_WEAPON_LINE, "weapon"),
                          (_ARMOR_LINE, "armor")):
        for match in pattern.finditer(text):
            name = match.group(1).strip()
            aliases = profile["weapon_aliases" if kind == "weapon"
                              else "armor_aliases"]
            target = (catalog.weapon(name, aliases) if kind == "weapon" else
                      catalog.armor_item(name, aliases))
            original = match.group(0)
            rec_location = dict(location)
            rec_location["text_range"] = [match.start(), match.end()]
            if not target:
                records.append(_record(
                    element, page, original, original,
                    "%s.unmatched" % kind, profile,
                    "%s saknar entydig DoD91-katalogträff" %
                    ("Vapnet" if kind == "weapon" else "Rustningen"),
                    rec_location, "unmatched_term", applied=False,
                    review=True, confidence=0.7))
                continue
            if kind == "weapon":
                detail = target.get("damage")
                converted = "Vapen: %s" % target["name"]
                if detail:
                    converted += " skada %s" % detail
            else:
                detail = target.get("absorption")
                converted = "Rustning: %s" % target["name"]
                if detail is not None:
                    converted += " ABS %s" % detail
            replacements.append((match.start(), match.end(), converted))
            record = _record(
                element, page, original, converted, "%s.catalog" % kind,
                profile,
                "Kanoniska DoD91-värden hämtade ur snapshotkatalogen",
                rec_location, kind)
            records.append(record)
            changes.append((record["element_id"],
                            record["source"]["location"], original, converted))

    # Explicita profilalias får normalisera säkert identifierade vapentermer
    # även i prosa. Överlapp med redan konverterade FV-/vapenintervall hoppas
    # över så att varje ändring fortfarande får exakt en konverteringspost.
    for alias, target_name in profile["weapon_aliases"].items():
        if alias.casefold() == target_name.casefold():
            continue
        target = catalog.weapon(alias, profile["weapon_aliases"])
        if not target:
            continue
        alias_pattern = re.compile(
            r"(?<![\wÅÄÖåäö])%s(?![\wÅÄÖåäö])" % re.escape(alias),
            re.IGNORECASE)
        for match in alias_pattern.finditer(text):
            if any(start < match.end() and match.start() < end
                   for start, end, _ in replacements):
                continue
            original = match.group(0)
            canonical = target["name"]
            converted = (canonical.lower()
                         if original[:1].islower() else canonical)
            replacements.append((match.start(), match.end(), converted))
            rec_location = dict(location)
            rec_location["text_range"] = [match.start(), match.end()]
            record = _record(
                element, page, original, converted, "weapon.alias", profile,
                "Explicit källalias normaliserat till kanoniskt DoD91-vapen",
                rec_location, "weapon")
            records.append(record)
            changes.append((record["element_id"],
                            record["source"]["location"], original, converted))

    # Sortering på position, inte insättningsordning: varje detektor söker
    # igenom hela texten, så posterna kommer inte i textordning. Bakifrån och
    # framåt håller resterande offset giltiga.
    converted_text = text
    for start, end, replacement in sorted(replacements, reverse=True):
        converted_text = converted_text[:start] + replacement + \
            converted_text[end:]
    return converted_text, records, changes


def _structured_skills(element, page, profile, catalog):
    data = element.get("data") or {}
    skills = data.get("skills")
    if not isinstance(skills, dict):
        return [], []
    records, changes = [], []
    converted = {}
    # Målnamn -> [(källnamn, källvärde, konverterat FV)]. Flera källfärdigheter
    # kan hamna på samma målfärdighet (två vapen i samma vapengrupp, två språk
    # i Språkkunskap). Bidragen samlas här så att den högsta nivån vinner
    # oberoende av ordning, och så att sammanslagningen kan redovisas.
    contributions = {}

    def assign(target_name, level, source_name, source_value):
        previous = converted.get(target_name)
        contributions.setdefault(target_name, []).append(
            (source_name, source_value, level))
        converted[target_name] = (
            level if not isinstance(previous, int) else max(previous, level))

    for name, value in skills.items():
        ivalue = _integer(value)
        split_names = profile.get("skill_splits", {}).get(name, [])
        target, rule, category, reason_kind = _skill_target(
            name, catalog, profile)
        location = {"field": "data.skills.%s" % name}
        if ivalue is None:
            converted[name] = value
            continue
        if split_names:
            targets = [catalog.skill(split_name, {}) for split_name
                       in split_names]
            if all(targets):
                new_value = convert_fv(ivalue, profile)
                for split_target in targets:
                    assign(split_target["name"], new_value, name, value)
                original = "%s %s" % (name, value)
                result = ", ".join(
                    "%s %s" % (split_target["name"], new_value)
                    for split_target in targets)
                record = _record(
                    element, page, original, result, "skill.split", profile,
                    "Den sammanslagna källfärdigheten delas upp i "
                    "DoD91:s separata färdigheter", location, "skill_value")
                records.append(record)
                changes.append((
                    record["element_id"], record["source"]["location"],
                    original, result))
                continue
        if not target:
            converted[name] = value
            records.append(_record(
                element, page, "%s %s" % (name, value),
                "%s %s" % (name, value), "skill.unmatched", profile,
                "Färdigheten saknar entydig DoD91-katalogträff", location,
                "unmatched_term", applied=False, review=True, confidence=0.7))
            continue
        new_value = convert_fv(ivalue, profile)
        new_name = target["name"]
        assign(new_name, new_value, name, value)
        original = "%s %s" % (name, value)
        result = "%s %s" % (new_name, new_value)
        record = _record(
            element, page, original, result, rule, profile,
            "Strukturerat FV och verifierad DoD91-%s" % reason_kind,
            location, category)
        records.append(record)
        changes.append((record["element_id"], record["source"]["location"],
                        original, result))

    records.extend(_merge_records(element, page, profile, contributions,
                                  converted))
    validate_skill_merges(element.get("id", "okänt"), contributions, converted)
    data["skills"] = converted
    return records, changes


def _merge_records(element, page, profile, contributions, converted):
    """Redovisa varje målfärdighet som fick bidrag från flera källfärdigheter.

    Utan den här posten skulle sammanslagningen bara synas som en färdighet
    mindre i statblocket — precis en sådan tyst korrigering som pipelinen
    inte tillåter.
    """
    records = []
    for target, items in sorted(contributions.items()):
        if len(items) < 2:
            continue
        kept = converted[target]
        dropped = sorted({level for _, _, level in items if level != kept},
                         reverse=True)
        reason = ("%d källfärdigheter hör till samma DoD91-färdighet %s; "
                  "högsta nivån behålls" % (len(items), target))
        if dropped:
            reason += (" och FV %s går upp i den utan egen rad" %
                       ", ".join(str(level) for level in dropped))
        records.append(_record(
            element, page,
            " + ".join("%s %s" % (name, value) for name, value, _ in items),
            "%s %s" % (target, kept), "skill.merged-target", profile,
            reason, {"field": "data.skills.%s" % target}, "skill_value"))
    return records


def normalize_candidate(value):
    return re.sub(r"\s+", " ", value.strip().lower())


def _derived_kp(element, page, profile):
    data = element.get("data") or {}
    stats = data.get("stats")
    if not isinstance(stats, dict) or "KP" not in stats:
        return [], []
    fys, sto, current = (_integer(stats.get("FYS")),
                         _integer(stats.get("STO")),
                         _integer(stats.get("KP")))
    if fys is None or sto is None or current is None:
        return [], []
    location = {"field": "data.stats.KP"}
    exception_name = normalize_candidate(data.get("name") or "")
    named_exception = any(term in exception_name for term in (
        "odöd", "oded", "skelett", "spöke", "spoke", "ande",
        "immateriell"))
    if fys <= 0 or sto <= 0 or data.get("rules_exception") or \
            data.get("monster_exception") or named_exception:
        record = _record(
            element, page, "KP %s" % stats["KP"], "KP %s" % stats["KP"],
            "kp.exception", profile,
            "KP räknades inte om eftersom grundvärdet är noll eller "
            "statblocket anger ett regelundantag", location, "derived_value",
            applied=False, review=True, confidence=1.0)
        return [record], []
    expected = int(math.ceil((fys + sto) / 2.0))
    if expected == current:
        return [], []
    original, converted = "KP %d" % current, "KP %d" % expected
    stats["KP"] = expected
    record = _record(
        element, page, original, converted, "kp.fys-sto-average", profile,
        "DoD91 KP = ceil((FYS + STO) / 2)", location, "derived_value")
    return [record], [(record["element_id"], record["source"]["location"],
                       original, converted)]


# Bokens fältnamn för samma sak som katalogens. Anger boken värdet vinner det,
# och katalogens synonym läggs inte till bredvid.
_FIELD_SYNONYMS = {"rackvidd": "range", "räckvidd": "range",
                   "skada": "damage", "vapen": "name"}


def _merge_catalog_entry(entry, target, element, page, profile, location,
                         kind):
    """Slå ihop bokens utrustningspost med katalogposten — boken vinner.

    Katalogen bidrar bara med fält boken inte anger (vikt, pris, STY-krav,
    vapengrupp). Ett tryckt spelvärde som avviker från katalogen BEHÅLLS och
    flaggas i stället för att skrivas över: enligt AGENTER.md Regel 8a rättas
    spelvärden aldrig automatiskt. Enda undantaget är `name`, där katalogens
    kanoniska stavning vinner — det är hela poängen med alias-normaliseringen.
    """
    records, changes = [], []
    merged = copy.deepcopy(entry)
    merged["name"] = target["name"]

    attack = merged.get("attack")
    ivalue = _integer(attack) if attack is not None else None
    if ivalue is not None and isinstance(attack, str) and "%" in attack:
        # Angreppsvärdet är bärarens färdighet med vapnet, inte en egenskap hos
        # vapnet. Det ska konverteras som varje annat FV — inte kastas.
        converted_value = convert_fv(ivalue, profile)
        merged["attack"] = converted_value
        attack_location = dict(location)
        attack_location["field"] = "%s.attack" % location["field"]
        original = "%s %s" % (target["name"], attack)
        result = "%s FV %d" % (target["name"], converted_value)
        record = _record(
            element, page, original, result, "fv.divide-by-five", profile,
            "Angreppsvärdet är bärarens färdighet med vapnet och räknas om "
            "till FV", attack_location,
            "weapon_skill" if kind == "weapon" else "skill_value")
        records.append(record)
        changes.append((record["element_id"], record["source"]["location"],
                        original, result))

    stated = {_FIELD_SYNONYMS.get(key, key) for key in merged}
    for key, value in sorted(target.items()):
        if key == "name":
            continue
        if key not in stated:
            merged[key] = copy.deepcopy(value)
            continue
        printed = merged.get(key)
        if printed is None or printed == value:
            continue
        # Boken och katalogen säger olika. Trycket behålls; avvikelsen är ett
        # fynd som en människa ska se, inte något att tyst normalisera bort.
        field_location = dict(location)
        field_location["field"] = "%s.%s" % (location["field"], key)
        records.append(_record(
            element, page, "%s %s: %s" % (target["name"], key, printed),
            "%s %s: %s" % (target["name"], key, printed),
            "%s.printed-value-differs" % kind, profile,
            "Trycket anger %s %r där DoD91-katalogen har %r. Tryckta "
            "spelvärden rättas inte automatiskt (Regel 8a) — behållet som "
            "det står, avvikelsen flaggas." % (key, printed, value),
            field_location, "unmatched_term", applied=False, review=True,
            confidence=0.6, blocking=False))
    return merged, records, changes


def _equipment_entries(element, page, profile, catalog, field, kind):
    data = element.get("data") or {}
    entries = data.get(field)
    if entries is None:
        return [], []
    records, changes = [], []
    aliases = profile["weapon_aliases" if kind == "weapon"
                      else "armor_aliases"]
    if isinstance(entries, list):
        work = [(index, entry, "list") for index, entry in enumerate(entries)]
    elif isinstance(entries, str):
        work = [(None, entries, "scalar")]
    elif isinstance(entries, dict) and "name" in entries:
        work = [(None, entries, "object")]
    elif isinstance(entries, dict):
        work = [(name, value, "mapping")
                for name, value in list(entries.items())]
    else:
        return [], []

    mapping_result = {} if isinstance(entries, dict) and "name" not in entries \
        else None
    for index, entry, representation in work:
        mapping_name = index if representation == "mapping" else None
        if isinstance(entry, str):
            name = mapping_name or entry
            body_part = None
        elif isinstance(entry, dict):
            name = mapping_name or entry.get("name")
            body_part = entry.get("bodyPart") or entry.get("body_part")
        elif representation == "mapping":
            name, body_part = mapping_name, None
        else:
            continue
        if not name:
            continue
        target = (catalog.weapon(name, aliases) if kind == "weapon" else
                  catalog.armor_item(name, aliases, body_part))
        location = {"field": (
            "data.%s[%s]" % (field, index)
            if index is not None else "data.%s" % field)}
        if not target:
            if mapping_result is not None:
                mapping_result[name] = entry
            records.append(_record(
                element, page, name, name, "%s.unmatched" % kind, profile,
                "%s saknar entydig DoD91-katalogträff" %
                ("Vapnet" if kind == "weapon" else "Rustningen"),
                location, "unmatched_term", applied=False, review=True,
                confidence=0.7))
            continue
        if isinstance(entry, dict):
            original_obj = copy.deepcopy(entry)
            merged, found, changed = _merge_catalog_entry(
                entry, target, element, page, profile, location, kind)
            records.extend(found)
            changes.extend(changed)
            if representation == "mapping":
                mapping_result[merged["name"]] = merged
                original = "%s: %s" % (name, original_obj)
                converted = "%s: %s" % (merged["name"], merged)
            else:
                entry.clear()
                entry.update(merged)
                original, converted = str(original_obj), str(entry)
            if original == converted:
                continue
        else:
            # Boken anger bara ett namn; katalogposten kan då inte skriva över
            # något tryckt värde och får utgöra hela innehållet.
            canonical = copy.deepcopy(target)
            if representation == "mapping":
                mapping_result[canonical["name"]] = canonical
                original = "%s: %s" % (name, entry)
                converted = "%s: %s" % (canonical["name"], canonical)
            elif representation == "scalar":
                data[field] = canonical
                original, converted = entry, str(canonical)
            else:
                entries[index] = canonical
                original, converted = entry, str(canonical)
        record = _record(
            element, page, original, converted, "%s.catalog" % kind,
            profile, "Katalogen fyller i de DoD91-värden boken inte anger; "
            "tryckta värden behålls", location, kind)
        records.append(record)
        changes.append((record["element_id"], record["source"]["location"],
                        original, converted))
    if mapping_result is not None:
        data[field] = mapping_result
    return records, changes


def analyze_and_convert(book, profile, catalog):
    converted_book = copy.deepcopy(book)
    records, changes = [], []
    element_count = 0
    for page_block in converted_book["pages"]:
        page = page_block["page"]
        for index, element in enumerate(page_block["elements"]):
            element_count += 1
            element.setdefault("id", "p%03d_e%02d" % (page, index + 1))
            text = element.get("text")
            if isinstance(text, str) and text:
                new_text, found, changed = _convert_text(
                    text, element, page, {"field": "text"}, profile, catalog)
                element["text"] = new_text
                records.extend(found)
                changes.extend(changed)
            if element.get("type") == "table":
                table = element.get("data") or {}
                for hi, header in enumerate(table.get("headers") or []):
                    if isinstance(header, str):
                        new, found, changed = _convert_text(
                            header, element, page,
                            {"table_cell": ["header", hi]}, profile, catalog)
                        table["headers"][hi] = new
                        records.extend(found)
                        changes.extend(changed)
                for ri, row in enumerate(table.get("rows") or []):
                    for ci, cell in enumerate(row):
                        if isinstance(cell, str):
                            new, found, changed = _convert_text(
                                cell, element, page,
                                {"table_cell": [ri, ci]}, profile, catalog)
                            row[ci] = new
                            records.extend(found)
                            changes.extend(changed)
            if element.get("type") == "list":
                items = (element.get("data") or {}).get("items") or []
                for item_index, item in enumerate(items):
                    if isinstance(item, str):
                        new, found, changed = _convert_text(
                            item, element, page,
                            {"list_item": item_index}, profile, catalog)
                        items[item_index] = new
                        records.extend(found)
                        changes.extend(changed)
            if element.get("type") == "statblock":
                # Fritextfälten i statblocket (Skydd, Förflyttning, Special…)
                # innehåller ofta regelvärden och scannades tidigare inte alls.
                stat_data = element.get("data") or {}
                for section in ("other", "extraStats"):
                    values = stat_data.get(section)
                    if not isinstance(values, dict):
                        continue
                    for key, value in list(values.items()):
                        if not isinstance(value, str) or not value:
                            continue
                        new, found, changed = _convert_text(
                            value, element, page,
                            {"field": "data.%s.%s" % (section, key)},
                            profile, catalog)
                        values[key] = new
                        records.extend(found)
                        changes.extend(changed)
                for handler in (
                        _structured_skills, _derived_kp):
                    found, changed = (
                        handler(element, page, profile, catalog)
                        if handler is _structured_skills else
                        handler(element, page, profile))
                    records.extend(found)
                    changes.extend(changed)
                for field, kind in (("weapons", "weapon"),
                                    ("armor", "armor")):
                    found, changed = _equipment_entries(
                        element, page, profile, catalog, field, kind)
                    records.extend(found)
                    changes.extend(changed)

    validate_change_coverage(records, changes)
    categories = {}
    for record in records:
        category = record.get("category", "other")
        bucket = categories.setdefault(
            category, {"applied": 0, "needs_review": 0})
        bucket["applied"] += int(record["applied"])
        bucket["needs_review"] += int(record["needs_review"])
    return converted_book, {
        "candidates": records,
        "counts": {
            "applied": sum(1 for r in records if r["applied"]),
            "needs_review": sum(1 for r in records if r["needs_review"]),
            # Bara öppna frågor stoppar publicering. Poster som redovisar ett
            # utfall profilen redan bestämt räknas som needs_review men inte
            # som blockerande — annars kan en bok med en enda katalog-
            # avvikelse aldrig publiceras.
            "blocking": sum(1 for r in records if r.get("blocking")),
            "unchanged": sum(1 for r in records if not r["applied"]),
            "elements_scanned": element_count,
        },
        "categories": categories,
    }
