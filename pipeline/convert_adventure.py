"""Orkestrering av explicit äventyrskonvertering till DoD91."""
import hashlib
import json
from pathlib import Path

from .conversion_analysis import analyze_and_convert
from .conversion_rules import Catalog, ProfileError, load_profile
from .export_conversion import (atomic_json, atomic_write, conversion_report,
                                markdown_from_book)
from .manifest import now_iso, slugify

ROOT = Path(__file__).resolve().parent.parent


class SourceError(ValueError):
    pass


class WriteError(OSError):
    pass


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _load_source(path):
    path = Path(path)
    if path.suffix.lower() != ".json":
        raise SourceError("--source måste peka på en JSON-fil")
    if not path.is_file():
        raise SourceError("källfilen finns inte: %s" % path)
    try:
        book = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise SourceError("källfilen är inte giltig JSON: %s" % exc)
    if not isinstance(book, dict) or not isinstance(book.get("pages"), list):
        raise SourceError("källfilen följer inte pipelinens bok.json-struktur")
    required = {"source", "system", "stats", "pages"}
    if required - set(book):
        raise SourceError("bok.json saknar: %s" %
                          ", ".join(sorted(required - set(book))))
    if not isinstance(book["source"], dict) or \
            not isinstance(book["stats"], dict):
        raise SourceError("bok.json har ogiltig source- eller stats-struktur")
    system = book.get("system") or {}
    system_id = system.get("id") if isinstance(system, dict) else system
    if system_id != "dod":
        raise SourceError("källsystemet är inte Drakar och Demoner")
    missing = book["stats"].get("missing_pages")
    if not isinstance(missing, list) or missing:
        raise SourceError("källan saknar färdig sammanfogning")
    for page in book["pages"]:
        if not isinstance(page, dict) or "page" not in page or \
                not isinstance(page.get("elements"), list):
            raise SourceError("ogiltig sida i bok.json")
        if any(not isinstance(element, dict)
               for element in page["elements"]):
            raise SourceError("ogiltigt element i bok.json")
    return book, path.resolve()


def _work_root(source):
    for parent in source.parents:
        if parent.name == "export":
            return parent.parent
    raise SourceError("--source måste ligga under en arbetskatalogs export/")


def _adventure_slug(book, source, output_name=None):
    if output_name:
        candidate = output_name
    else:
        metadata = (book.get("source") or {}).get("metadata") or {}
        title = metadata.get("title")
        candidate = title or (
            source.parent.name if source.parent.name != "export"
            else source.parents[1].name)
    result = slugify(candidate)
    if result.startswith("dod-ave-"):
        result = result[len("dod-ave-"):]
    return result or "aventyr"


def _manifest_key(source_sha, profile):
    raw = "%s:%s:%s" % (
        source_sha, profile["id"], profile["version"])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _existing_review_count(book):
    stats = book.get("stats") or {}
    count = int(stats.get("needs_review") or 0)
    if count:
        return count
    return sum(1 for page in book["pages"] for element in page["elements"]
               if element.get("needs_review"))


def convert_adventure(source, source_profile, target_profile,
                      output_name=None, force=False, dry_run=False,
                      public_root=None):
    book, source_path = _load_source(source)
    profile = load_profile(source_profile, target_profile)
    catalog = Catalog(target_profile)
    source_sha = _sha256(source_path)
    work_root = _work_root(source_path)
    adventure_slug = _adventure_slug(book, source_path, output_name)
    state_dir = (work_root / "konvertering" / target_profile /
                 adventure_slug)
    manifest_path = state_dir / "manifest.json"
    key = _manifest_key(source_sha, profile)

    if manifest_path.is_file() and not force and not dry_run:
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except ValueError:
            existing = {}
        if existing.get("idempotency_key") == key and \
                existing.get("status") == "complete":
            return {"status": "complete", "skipped": True,
                    "state_dir": str(state_dir),
                    "published": existing.get("published", [])}

    converted, analysis = analyze_and_convert(book, profile, catalog)
    status = ("analyzed" if dry_run else
              "needs_review" if analysis["counts"]["blocking"]
              else "complete")
    generated = now_iso()
    conversion_metadata = {
        "source_ruleset": source_profile,
        "target_ruleset": target_profile,
        "profile": profile["id"],
        "profile_version": profile["version"],
        "source_sha256": source_sha,
        "generated": generated,
        "status": status,
        "counts": {
            key: analysis["counts"][key]
            for key in ("applied", "needs_review", "blocking", "unchanged")
        },
        "catalog": {
            "source_repository": catalog.catalog.get("source_repository"),
            "source_commit": catalog.catalog.get("source_commit"),
        },
    }
    converted["conversion"] = conversion_metadata
    converted["conversion_records"] = analysis["candidates"]

    published = []
    publish_root = Path(public_root) if public_root else ROOT / "konverterat"
    public_base = publish_root / target_profile / (
        "DOD-AVE-%s" % adventure_slug)
    if status == "complete":
        published = [str(public_base.with_suffix(".md")),
                     str(public_base.with_suffix(".json")),
                     str(public_base.with_name(
                         public_base.name + ".konverteringsrapport.md"))]
    report = conversion_report(
        source_path, source_sha, profile, analysis,
        _existing_review_count(book), status, published)
    manifest = {
        "idempotency_key": key,
        "source": str(source_path),
        "source_sha256": source_sha,
        "profile": profile["id"],
        "profile_version": profile["version"],
        "generated": generated,
        "status": status,
        "dry_run": bool(dry_run),
        "counts": conversion_metadata["counts"],
        "published": published,
    }
    try:
        atomic_json(state_dir / "analys.json", analysis)
        if not dry_run:
            atomic_json(state_dir / "bok.konverterad.json", converted)
        atomic_write(state_dir / "konverteringsrapport.md", report)
        if status == "complete":
            atomic_json(public_base.with_suffix(".json"), converted)
            atomic_write(public_base.with_suffix(".md"),
                         markdown_from_book(converted))
            atomic_write(public_base.with_name(
                public_base.name + ".konverteringsrapport.md"), report)
        # Manifestet är commit-markören och skrivs sist. En avbruten körning
        # får därmed aldrig se komplett ut vid nästa idempotenskontroll.
        atomic_json(state_dir / "manifest.json", manifest)
    except OSError as exc:
        raise WriteError("kunde inte skriva konverteringen: %s" % exc)

    return {"status": status, "skipped": False,
            "state_dir": str(state_dir), "published": published,
            "counts": conversion_metadata["counts"]}
