"""Regelsystemsidentifiering via fingeravtryck (filnamn, metadata, termstatistik).

Manuellt val (--system) vinner alltid över detekteringen.
"""
import re
from pathlib import Path

import fitz

from .log import setup_logging
from .manifest import Manifest
from .systems import Adapter, available_systems, normalize

SAMPLE_PAGES = 15
SAMPLE_CHARS = 40000


def gather_text(pdf_path, workdir=None):
    """Textunderlag: embedded textlager + ev. transkript i arbetskatalogen."""
    chunks = []
    doc = fitz.open(pdf_path)
    try:
        for i in range(min(SAMPLE_PAGES, len(doc))):
            chunks.append(doc[i].get_text("text"))
    finally:
        doc.close()
    if workdir:
        from .manifest import pages_dir
        for f in sorted(pages_dir(workdir).glob("*.transcript.json"))[:SAMPLE_PAGES]:
            chunks.append(f.read_text(encoding="utf-8"))
    return "\n".join(chunks)[:SAMPLE_CHARS]


def score_adapter(adapter, filename, metadata_text, sample_text):
    det = adapter.detection
    fn = normalize(filename)
    meta = normalize(metadata_text)
    score, evidence = 0.0, []

    for token in det.get("filename_tokens", []):
        if token in fn:
            score += 3.0
            evidence.append("filnamn:%s" % token)
        elif token in meta:
            score += 2.0
            evidence.append("metadata:%s" % token)

    text_n = normalize(sample_text)
    for term in det.get("strong_terms", []):
        hits = text_n.count(normalize(term))
        if hits:
            score += min(hits, 5) * 2.0
            evidence.append("term:%s×%d" % (term, min(hits, 5)))
    for term in det.get("weak_terms", []):
        hits = len(re.findall(r"\b%s\b" % re.escape(term), sample_text))
        if hits:
            score += min(hits, 10) * 0.3

    attrs = det.get("attribute_signature", [])
    present = {a for a in attrs
               if re.search(r"\b%s\b" % re.escape(a), sample_text)}
    if len(present) >= 5:
        score += 5.0
        evidence.append("attributsignatur:%d/%d" % (len(present), len(attrs)))
    elif len(present) >= 3:
        score += 2.0

    return score, evidence


def detect(pdf_path, workdir=None, root=None):
    """Rangordna systemen. Returnerar lista av dictar, bäst först."""
    filename = Path(pdf_path).name
    metadata_text = ""
    doc = fitz.open(pdf_path)
    try:
        metadata_text = " ".join(str(v) for v in doc.metadata.values() if v)
    finally:
        doc.close()
    sample = gather_text(pdf_path, workdir)

    results = []
    for sid in available_systems(root):
        adapter = Adapter(sid, root=root)
        score, evidence = score_adapter(adapter, filename, metadata_text, sample)
        results.append({"system": sid, "score": round(score, 1),
                        "evidence": evidence})
    results.sort(key=lambda r: -r["score"])
    total = sum(r["score"] for r in results) or 1.0
    for r in results:
        r["confidence"] = round(r["score"] / total, 2)
    return results


def detect_and_record(pdf_path, workdir, root=None, manual=None):
    log = setup_logging(workdir)
    m = Manifest.load(workdir)
    if manual:
        from .systems import resolve_system_id
        sid = resolve_system_id(manual, root=root)
        m.data["system"] = {"id": sid, "confidence": 1.0, "method": "manual"}
        m.save()
        log.info("system: %s (manuellt valt)", sid)
        return m.data["system"]
    results = detect(pdf_path, workdir, root=root)
    best = results[0] if results else None
    if best is None or best["score"] <= 0:
        log.warning("systemdetektering: inget system matchade — ange --system")
        return None
    m.data["system"] = {"id": best["system"],
                        "confidence": best["confidence"],
                        "method": "fingerprint",
                        "evidence": best["evidence"][:12],
                        "ranking": [(r["system"], r["score"]) for r in results]}
    m.save()
    log.info("system: %s (confidence %.2f — %s)", best["system"],
             best["confidence"], ", ".join(best["evidence"][:5]))
    return m.data["system"]
