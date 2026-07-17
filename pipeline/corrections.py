"""Korrektionsposter och reparationsalgoritmer.

Grundprinciper (se docs/ARKITEKTUR.md §3.3):
  * Originaltexten bevaras alltid i posten — inga tysta korrigeringar.
  * En rättning appliceras bara vid entydig kandidat och confidence >= tröskeln.
  * Tvetydiga/osäkra fall flaggas för manuell granskning i stället.
"""
import itertools
import re

from .manifest import now_iso
from .systems import normalize

APPLY_THRESHOLD = 0.9

CANONICAL_DICE = re.compile(r"^(\d+)T(\d+)([+-]\d+)?$")


def make_correction(original, corrected, confidence, reason, source,
                    applied=None):
    if applied is None:
        applied = confidence >= APPLY_THRESHOLD
    return {
        "original": original,
        "corrected": corrected,
        "applied": bool(applied),
        "confidence": round(confidence, 3),
        "reason": reason,
        "source": source,
        "timestamp": now_iso(),
    }


# ---------------------------------------------------------------------------
# Tärningsnotation
# ---------------------------------------------------------------------------

def _char_candidates(ch, misread):
    """Möjliga kanoniska tecken för ett observerat tecken (inkl. det själv)."""
    cands = []
    if ch.isdigit() or ch in "+-":
        cands.append(ch)
    if ch in ("T", "t", "D", "d"):
        cands.append("T")
    for c in misread.get(ch, []):
        if c not in cands:
            cands.append(c)
    return cands


def dice_candidates(token, dice_cfg, max_count=50):
    """Alla giltiga kanoniska tärningsnotationer som token kan repareras till.

    Returnerar lista av (notation, antal_substitutioner).
    """
    sides_ok = set(dice_cfg.get("sides", []))
    misread = dice_cfg.get("misread_to_canonical", {})
    if len(token) > 9 or len(token) < 2:
        return []
    # Rena siffertal repareras aldrig (t.ex. årtal "1984" får inte bli tärning)
    if token.isdigit():
        return []
    per_char = [_char_candidates(ch, misread) for ch in token]
    if any(not c for c in per_char):
        return []
    results = {}
    n = 1
    for c in per_char:
        n *= len(c)
    if n > 400:
        return []
    for combo in itertools.product(*per_char):
        cand = "".join(combo)
        m = CANONICAL_DICE.match(cand)
        if not m:
            continue
        count, sides = int(m.group(1)), int(m.group(2))
        if sides not in sides_ok or not 1 <= count <= 30:
            continue
        subs = sum(1 for a, b in zip(token, cand) if a != b)
        if cand not in results or subs < results[cand]:
            results[cand] = subs
    return sorted(results.items(), key=lambda kv: kv[1])


def repair_dice_token(token, dice_cfg):
    """Försök reparera en misstänkt tärningstoken.

    Returnerar (status, correction_eller_None):
      'ok'        — redan giltig notation
      'fixed'     — entydig reparation (korrektionspost)
      'ambiguous' — flera kandidater (flagga)
      'invalid'   — ser ut som tärning men går inte att laga (flagga)
      'skip'      — ingen tärningstoken
    """
    m = CANONICAL_DICE.match(token)
    sides_ok = set(dice_cfg.get("sides", []))
    if m and int(m.group(2)) in sides_ok:
        return "ok", None
    cands = dice_candidates(token, dice_cfg)
    if m and not cands:
        return "invalid", None  # t.ex. 3T7 — notation men ogiltiga sidor
    if not cands:
        return "skip", None
    best_subs = cands[0][1]
    top = [c for c in cands if c[1] == best_subs]
    if len(top) > 1:
        return "ambiguous", None
    notation, subs = top[0]
    if notation == token:
        return "ok", None
    confidence = max(0.85, 1.0 - 0.03 * subs)
    corr = make_correction(
        token, notation, confidence,
        "Tärningsnotation: %d teckensubstitution(er) ger giltig notation %s"
        % (subs, notation),
        "validator:dice")
    return "fixed", corr


# Token som kan vara feltolkad tärningsnotation: minst en siffra eller
# versalblandning, begränsad teckenmängd.
DICE_TOKEN = re.compile(r"^[0-9IlOoQSsBbGgZzTtDd|+]{2,7}(?:[+-][0-9IlOSB]{1,2})?$")


def scan_dice_in_text(text, dice_cfg, lexicon_words):
    """Hitta och reparera tärningstokens i löptext. Returnerar korrektioner
    och flaggor; ändrar inte texten (det gör applicerings-steget)."""
    corrections, flags = [], []
    for raw in re.findall(r"[^\s,;:()\[\]{}!?\"']+", text):
        token = raw.strip(".")
        if not DICE_TOKEN.match(token):
            continue
        if not any(ch in "TtDd7Il|+" for ch in token):
            continue
        if normalize(token) in lexicon_words:
            continue
        status, corr = repair_dice_token(token, dice_cfg)
        if status == "fixed":
            corrections.append(corr)
        elif status in ("ambiguous", "invalid"):
            flags.append({"token": token, "issue": "tärningsnotation (%s)" % status})
    return corrections, flags


# ---------------------------------------------------------------------------
# Lexikon (termer, färdigheter, vapen, egennamn ...)
# ---------------------------------------------------------------------------

WORD_TOKEN = re.compile(r"[A-Za-zÅÄÖåäöÉéÜü0-6]{3,}")


def repair_word(word, adapter):
    """Reparera ett ord mot systemlexikonet.

    Endast ord vars normalform träffar lexikonet rättas — vanlig svenska
    lämnas orörd. Returnerar (status, correction): 'ok'|'fixed'|'ambiguous'|'skip'.
    """
    key = normalize(word)
    alias_target = adapter.aliases.get(key)
    if alias_target:
        if word.lower() == alias_target.lower():
            return "ok", None  # endast skiftlägesskillnad — rätta inte
        return "fixed", make_correction(
            word, alias_target, 0.95,
            "Känd variant i systemlexikonet (alias)", "validator:lexicon")
    candidates = adapter.words.get(key, [])
    if not candidates:
        return "skip", None
    if len(candidates) > 1:
        exact = [c for c in candidates if c == word]
        if exact:
            return "ok", None
        return "ambiguous", None
    canonical = candidates[0]
    if word == canonical or word.lower() == canonical.lower():
        return "ok", None  # endast skiftlägesskillnad — rätta inte
    # Ordet skiljer sig i diakritiska tecken e.d. men normaliserar lika
    subs = sum(1 for a, b in zip(word, canonical) if a != b) + \
        abs(len(word) - len(canonical))
    confidence = max(0.85, 0.98 - 0.02 * subs)
    return "fixed", make_correction(
        word, canonical, confidence,
        "Matchar systemterm %r efter diakritisk normalisering" % canonical,
        "validator:lexicon")


def scan_words_in_text(text, adapter):
    corrections = []
    seen = set()
    for word in WORD_TOKEN.findall(text):
        if word in seen:
            continue
        seen.add(word)
        status, corr = repair_word(word, adapter)
        if status == "fixed":
            corrections.append(corr)
    return corrections


# ---------------------------------------------------------------------------
# Applicering
# ---------------------------------------------------------------------------

def apply_corrections_to_text(text, corrections):
    """Applicera korrektioner med applied=True på en textsträng (ordgränser)."""
    for corr in corrections:
        if not corr.get("applied"):
            continue
        pattern = r"(?<![\wÅÄÖåäö])%s(?![\wÅÄÖåäö])" % re.escape(corr["original"])
        text = re.sub(pattern, corr["corrected"].replace("\\", "\\\\"), text)
    return text
