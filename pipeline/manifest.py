"""Bok-manifest: state per sida, atomisk skrivning, idempotent återupptagning.

Sidans state-maskin:
    pending -> rendered/extracted -> transcribed -> validated -> reviewed -> final
`error` och `needs_review` är ortogonala fält och blockerar inte omkörning.
"""
import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from . import SCHEMA_VERSION

MANIFEST_NAME = "book.json"

PAGE_STATES = ["pending", "rendered", "extracted", "transcribed",
               "validated", "reviewed", "final"]


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(name):
    """Filsystemssäker slug av ett boknamn."""
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return name[:80] or "bok"


def default_workdir(pdf_path, base="arbete"):
    return Path(base) / slugify(Path(pdf_path).stem)


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            data = f.read(chunk)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def atomic_write_json(path, data):
    """Skriv JSON till .tmp och byt atomiskt — inga halvskrivna filer vid avbrott."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def read_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


class Manifest:
    def __init__(self, workdir, data=None):
        self.workdir = Path(workdir)
        self.path = self.workdir / MANIFEST_NAME
        self.data = data if data is not None else read_json(self.path)

    @classmethod
    def exists(cls, workdir):
        return (Path(workdir) / MANIFEST_NAME).is_file()

    @classmethod
    def load(cls, workdir):
        return cls(workdir)

    @classmethod
    def create(cls, workdir, source_path, n_pages, metadata=None):
        data = {
            "schema_version": SCHEMA_VERSION,
            "created": now_iso(),
            "source": {
                "path": str(Path(source_path).resolve()),
                "sha256": sha256_file(source_path),
                "pages": n_pages,
                "metadata": metadata or {},
            },
            "system": None,
            "doc_type": {},
            "pages": {
                str(i): {"class": None, "state": "pending", "steps": {},
                         "flags": [], "needs_review": 0, "error": None}
                for i in range(1, n_pages + 1)
            },
        }
        m = cls(workdir, data=data)
        m.save()
        return m

    def save(self):
        atomic_write_json(self.path, self.data)

    # -- sidhjälpare -------------------------------------------------------

    def page(self, page_no):
        return self.data["pages"][str(page_no)]

    def page_numbers(self):
        return sorted(int(k) for k in self.data["pages"])

    def set_state(self, page_no, state, error=None):
        if state not in PAGE_STATES:
            raise ValueError("okänt state: %s" % state)
        p = self.page(page_no)
        p["state"] = state
        p["steps"][state] = now_iso()
        p["error"] = error

    def state_at_least(self, page_no, state):
        """Har sidan nått (minst) detta state?"""
        cur = self.page(page_no)["state"]
        order = {s: i for i, s in enumerate(PAGE_STATES)}
        # rendered och extracted är parallella spår på samma nivå
        lvl = {"extracted": order["rendered"]}
        cur_i = lvl.get(cur, order.get(cur, 0))
        want_i = lvl.get(state, order[state])
        return cur_i >= want_i

    def source_matches(self, pdf_path):
        return self.data["source"]["sha256"] == sha256_file(pdf_path)

    def summary(self):
        counts = {}
        review = 0
        errors = []
        for no in self.page_numbers():
            p = self.page(no)
            counts[p["state"]] = counts.get(p["state"], 0) + 1
            review += p.get("needs_review", 0)
            if p.get("error"):
                errors.append((no, p["error"]))
        return {"states": counts, "needs_review": review, "errors": errors}


def pages_dir(workdir):
    d = Path(workdir) / "pages"
    d.mkdir(parents=True, exist_ok=True)
    return d


def export_dir(workdir):
    d = Path(workdir) / "export"
    d.mkdir(parents=True, exist_ok=True)
    return d


def page_file(workdir, page_no, suffix):
    """Standardiserade filnamn: page_017.transcript.json osv."""
    return pages_dir(workdir) / ("page_%03d.%s" % (page_no, suffix))
