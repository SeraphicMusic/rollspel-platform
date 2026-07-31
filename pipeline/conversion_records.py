"""Datamodell och kontroll för spårbara regelkonverteringar."""

REQUIRED_FIELDS = {
    "kind", "element_id", "source", "original", "converted",
    "source_ruleset", "target_ruleset", "rule", "profile_version",
    "confidence", "reason", "applied", "needs_review",
}


def make_record(element_id, page, region, original, converted, rule,
                profile, reason, confidence=1.0, applied=True,
                needs_review=False, location=None, category=None,
                blocking=None):
    # `needs_review` betyder "en människa bör se det här"; `blocking` betyder
    # "en människa måste avgöra det innan publicering". De sammanfaller för
    # öppna frågor, men en post som bara redovisar ett utfall profilen redan
    # har bestämt (t.ex. att tryckta spelvärden vinner över katalogen) ska
    # synas i rapporten utan att stoppa publiceringen för alltid.
    if blocking is None:
        blocking = needs_review
    record = {
        "kind": "rules_conversion",
        "element_id": element_id,
        "source": {
            "page": page,
            "region": region or "okänd",
            "text": original,
        },
        "original": original,
        "converted": converted,
        "source_ruleset": profile["source"],
        "target_ruleset": profile["target"],
        "rule": rule,
        "profile_version": profile["version"],
        "confidence": float(confidence),
        "reason": reason,
        "applied": bool(applied),
        "needs_review": bool(needs_review),
        "blocking": bool(blocking),
    }
    if location is not None:
        record["source"]["location"] = location
    if category:
        record["category"] = category
    validate_record(record)
    return record


def validate_record(record):
    missing = REQUIRED_FIELDS - set(record)
    if missing:
        raise ValueError("konverteringspost saknar: %s" %
                         ", ".join(sorted(missing)))
    if record["kind"] != "rules_conversion":
        raise ValueError("fel kind i konverteringspost")
    if record["applied"] and record["needs_review"]:
        raise ValueError("osäker konverteringspost får inte appliceras")
    if record.get("blocking") and not record["needs_review"]:
        raise ValueError("blockerande post måste också vara needs_review")
    if not 0 <= record["confidence"] <= 1:
        raise ValueError("confidence måste ligga mellan 0 och 1")
    return record


def validate_change_coverage(records, changes):
    """Varje faktisk ändring måste ha exakt en applicerad post."""
    keys = [(r["element_id"], r["source"].get("location"), r["original"],
             r["converted"]) for r in records if r["applied"]]
    for change in changes:
        if keys.count(change) != 1:
            raise ValueError(
                "textändring saknar exakt en konverteringspost: %r" %
                (change,))


def validate_skill_merges(element_id, contributions, converted):
    """Flera källfärdigheter får kollapsa till en målfärdighet — men bara
    om den högsta nivån överlever och sammanslagningen är redovisad.

    Spärren finns för att en kollision annars blir tyst dataförlust: den som
    skrivs sist vinner, och en SLP tappar sin bästa färdighet utan att något
    syns i konverteringsrapporten.
    """
    for target, items in contributions.items():
        levels = [level for _, _, level in items]
        expected = max(levels)
        actual = converted.get(target)
        if actual != expected:
            raise ValueError(
                "%s: %s fick FV %r efter sammanslagning av %s, men högsta "
                "bidraget är FV %r — en källfärdighet har gått förlorad" % (
                    element_id, target, actual,
                    ", ".join("%s %s" % (name, value)
                              for name, value, _ in items),
                    expected))

