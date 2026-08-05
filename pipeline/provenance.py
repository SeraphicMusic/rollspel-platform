"""Proveniens: vilken KOD byggde exporten?

`export/bok.json` bar `generated` — ett klockslag — men ingenting om vilken
version av pipelinen som skrev filen. Följden är en tyst felklass: en export
som ligger kvar från före en lagning ser exakt ut som en färsk. Två mätta fall,
båda upptäckta av en människa som råkade läsa texten:

* `bibliotek/…del2` bar `ENER- GISTRÅLE` och `SMIslaget.` — brytfel som redan
  var lagade i `pipeline/export.py`, i en `bok.md` som ingen kört om.
* MUT-REG-den-malplacerade-tempokalkylatorn hade en dubblerad tabellrubrik av
  samma skäl.

Ingen varning, ingenting i `status`. Stämpeln nedan gör skillnaden mätbar:
varje byggd artefakt bär den git-revision och den `SCHEMA_VERSION` som byggde
den, och `status`/`rapport` säger ifrån när stämpeln inte är HEAD.

**Var stämpeln får sitta.** `bok.json` bär sin egen inuti sig (`byggd_med`) —
det är en datafil och tål ett fält till. `bok.md` gör det INTE: den är
ordkonserveringens facit (`frys`/`diffa` jämför ordfrekvenser), och en
revisionssträng i filen skulle ge en ny "nytt ord"-rad vid varje commit —
brus i just den kontroll vars hela värde ligger i att den är tyst. Markdownens
och CSV-katalogens stämplar ligger därför i `export/proveniens.json`.

**Smutsigt arbetsträd räknas.** Byggs en export ur oincheckade ändringar i
`pipeline/` eller `scripts/` stämmer revisionen men koden gör det inte.
Stämpeln bär då `smutsigt: true`, så att den inte påstår mer än den vet.
Bara kodkatalogerna prövas — `arbete/` ändras vid varje körning och säger
ingenting om byggaren.
"""
import subprocess
from pathlib import Path

from . import SCHEMA_VERSION
from .manifest import atomic_write_json, export_dir, now_iso, read_json

REPO_ROOT = Path(__file__).resolve().parent.parent

# Katalogerna vars innehåll ÄR byggaren. Ändringar utanför dem (en bok i
# `arbete/`, en anteckning i docs) gör inte exporten mindre trovärdig.
CODE_PATHS = ("pipeline", "scripts")

PROVENANCE_NAME = "proveniens.json"
STAMP_KEY = "byggd_med"


def _git(root, *args):
    """Kör git och returnera stdout, eller None om det inte gick."""
    try:
        out = subprocess.run(("git", "-C", str(root)) + args,
                             capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def code_revision(root=REPO_ROOT):
    """Git-revisionen för koden, eller None utanför ett arbetsträd."""
    return _git(root, "rev-parse", "HEAD") or None


def code_dirty(root=REPO_ROOT):
    """Har `pipeline/` eller `scripts/` oincheckade ändringar?"""
    out = _git(root, "status", "--porcelain", "--", *CODE_PATHS)
    if out is None:
        return None
    return bool(out)


def stamp(root=REPO_ROOT):
    """Proveniensstämpeln för en artefakt som byggs nu."""
    return {"schema_version": SCHEMA_VERSION,
            "git_revision": code_revision(root),
            "smutsigt": code_dirty(root),
            "byggd": now_iso()}


def provenance_path(workdir):
    return export_dir(workdir) / PROVENANCE_NAME


def record(workdir, artifact, root=REPO_ROOT):
    """Skriv stämpeln för en artefakt som inte kan bära den själv."""
    path = provenance_path(workdir)
    data = {}
    if path.is_file():
        try:
            data = read_json(path)
        except ValueError:
            data = {}
    data[artifact] = stamp(root)
    atomic_write_json(path, data)
    return data[artifact]


def _is_ancestor(root, rev):
    """Är `rev` en föregångare till HEAD? None = går inte att avgöra."""
    try:
        out = subprocess.run(
            ("git", "-C", str(root), "merge-base", "--is-ancestor", rev,
             "HEAD"), capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode == 0:
        return True
    if out.returncode == 1:
        return False
    return None  # okänd revision, trasigt arbetsträd


def check_stamp(mark, artifact, root=REPO_ROOT):
    """Varningar för EN artefakts stämpel. Tom lista = artefakten är aktuell.

    Varning, inte spärr: en gammal export är läsbar och riktig så långt den
    går. Det som saknas är beskedet om att den kan sakna en lagning.
    """
    head = code_revision(root)
    if not mark:
        return ["%s saknar proveniensstämpel — byggd med kod från innan "
                "stämpeln fanns; bygg om för att veta" % artifact]
    varningar = []
    rev = mark.get("git_revision")
    if head and rev and rev != head:
        # "Äldre" påstås bara när revisionen bevisligen ligger i HEAD:s
        # historia. En okänd revision (exit 128) och en revision på en annan
        # gren (exit 1) är samma sorts obekant och får samma lydelse — att
        # kalla dem gamla vore att påstå en ordning som inte är mätt.
        if _is_ancestor(root, rev) is True:
            varningar.append(
                "%s är byggd med ÄLDRE kod än HEAD (%s, HEAD är %s) — bygg om"
                % (artifact, rev[:12], head[:12]))
        else:
            varningar.append(
                "%s är byggd med kod som INTE ligger i HEAD:s historia (%s) — "
                "annan gren eller omskriven historik" % (artifact, rev[:12]))
    elif head and not rev:
        varningar.append("%s bär ingen git-revision — byggd utanför ett "
                         "arbetsträd" % artifact)
    if mark.get("schema_version") != SCHEMA_VERSION:
        varningar.append(
            "%s är byggd mot schemaversion %s, koden står på %s"
            % (artifact, mark.get("schema_version"), SCHEMA_VERSION))
    if mark.get("smutsigt"):
        varningar.append(
            "%s är byggd ur ett SMUTSIGT arbetsträd — revisionen %s säger "
            "inte vilken kod som kördes" % (artifact, (rev or "?")[:12]))
    return varningar


def check_exports(workdir, root=REPO_ROOT):
    """Varningar för bokens samtliga byggda artefakter, i byggordning."""
    varningar = []
    bok = export_dir(workdir) / "bok.json"
    if bok.is_file():
        try:
            data = read_json(bok)
        except ValueError:
            data = {}
        varningar += check_stamp(data.get(STAMP_KEY), "bok.json", root)
    sidecar = provenance_path(workdir)
    marks = {}
    if sidecar.is_file():
        try:
            marks = read_json(sidecar)
        except ValueError:
            marks = {}
    for artifact, path in (("bok.md", export_dir(workdir) / "bok.md"),
                           ("tabeller/", export_dir(workdir) / "tabeller")):
        if path.exists():
            varningar += check_stamp(marks.get(artifact), artifact, root)
    return varningar
