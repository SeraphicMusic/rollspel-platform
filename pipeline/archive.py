"""Arkivering av en färdig bok: käll-PDF → `arkiv/`, läsexport → `bibliotek/`.

Detta var steg 5–6 i [import/README.md](../import/README.md) — alltså en
instruktion till en agent, inte kod. Ingenting körde den, ingenting påminde om
den, och ingenting märkte att den uteblev. För DoD-grundreglernas tre delar
gjorde den aldrig det: käll-PDF:erna låg kvar i `import/` tills de raderades
för hand, och när del I:s forensik behövde den inbäddade skanningen (44 % mer
upplösning än sidbilderna i `arbete/`) fanns den inte längre.

Två regler bär modulen:

* **Flytta, aldrig radera.** PDF:en är den enda kvarvarande sanningskällan när
  en dom ska omprövas. `arkiv/` är inte en papperskorg.
* **Arkivera aldrig en oavslutad bok.** `readiness()` samlar allt som talar
  emot och `archive()` vägrar så länge listan inte är tom. En bok med öppna
  BQ-poster är inte klar — dess PDF ska ligga kvar där den är lätt att nå.

Torrkörning är default, som i `scripts/`-verktygen: utan `verkstall=True`
beskrivs bara vad som skulle hända.
"""
import re
import shutil
from pathlib import Path

from .decisions import blocking_questions
from .manifest import Manifest, page_file, read_json, sha256_file

# NAMNSTANDARD.md: `SYSTEM-TYP-titel`, t.ex. `DOD-REG-grundregler-1991-del1`.
STANDARD_NAME = re.compile(r"^[A-Z]{3}-[A-Z]{3}-[a-z0-9][a-z0-9-]*$")

# Sidor måste ha nått minst detta state för att boken ska räknas som färdig.
KLART_STATE = "validated"


def repo_root(workdir):
    """Repo-roten ur arbetskatalogen (`<rot>/arbete/<slug>`)."""
    return Path(workdir).resolve().parent.parent


def standard_name(workdir, namn=None):
    """Standardnamnet, ur `namn` eller ur arbetskatalogens egen basename.

    Namnet gissas ALDRIG fram ur boktiteln — vilken typkod som är rätt
    (REG/AVE/VRL/TAB) är ett redaktionellt beslut, inte en strängoperation.
    """
    kandidat = namn or Path(workdir).resolve().name
    if not STANDARD_NAME.match(kandidat):
        return None, ("%r följer inte NAMNSTANDARD.md (SYSTEM-TYP-titel, "
                      "t.ex. DOD-REG-grundregler-1991-del1). Ange --namn."
                      % kandidat)
    return kandidat, None


def _sidlista(nos, max_visade=8):
    if len(nos) <= max_visade:
        return ", ".join("s. %d" % n for n in nos)
    visade = ", ".join("s. %d" % n for n in nos[:max_visade])
    return "%s … och %d till" % (visade, len(nos) - max_visade)


def uncorrected_pages(workdir, manifest=None):
    """Sidor som saknar `final.json`, alltså aldrig varit hos advokaten.

    Manifestets `state` duger INTE som mått: pipelinen lyfter aldrig en sida
    över `validated`, så en bok där halva korrekturet återstår ser i statusen
    likadan ut som en färdig. Det som skiljer dem är om sidan har en
    `final.json` — `pipeline/merge.py` väljer final > validated > transcript,
    så en sida utan final bidrar med sin OKORRIGERADE maskinläsning, tyst.

    Sidor som är avförda med `skipped.reason` (t.ex. `illustration_only`) har
    aldrig något korrektur att göra och räknas inte.
    """
    workdir = Path(workdir)
    m = manifest or Manifest.load(workdir)
    ut = []
    for no in m.page_numbers():
        if page_file(workdir, no, "final.json").exists():
            continue
        data = read_json(page_file(workdir, no, "validated.json")) or {}
        if (data.get("skipped") or {}).get("reason"):
            continue
        ut.append(no)
    return ut


def readiness(workdir):
    """Allt som talar emot att boken arkiveras nu, som en lista av skäl.

    Tom lista = klar. Listan är avsiktligt fullständig i stället för att
    avbryta på första felet: den som får beskedet ska se hela återstoden.
    """
    workdir = Path(workdir)
    hinder = []
    m = Manifest.load(workdir)
    s = m.summary()

    for no in m.page_numbers():
        if not m.state_at_least(no, KLART_STATE):
            hinder.append("sida %d har state %r, inte minst %r"
                          % (no, m.page(no)["state"], KLART_STATE))
    for no, err in s["errors"]:
        hinder.append("sida %d har ett fel: %s" % (no, err))

    okorrigerade = uncorrected_pages(workdir, m)
    if okorrigerade:
        hinder.append(
            "%d av %d sidor har aldrig korrekturlästs (ingen final.json): %s. "
            "`sammanfoga` tar då sidans validated-version, alltså den "
            "omaskinellt rättade transkriptionen, och boken SER färdig ut i "
            "exporten fast halva korrekturet återstår."
            % (len(okorrigerade), len(m.page_numbers()),
               _sidlista(okorrigerade)))

    for namn in ("bok.json", "bok.md"):
        if not (workdir / "export" / namn).exists():
            hinder.append("export/%s saknas" % namn)

    # Bara `[beslut]`-poster hindrar. En `[verktyg]`-post är en bugg i
    # pipelinen med ett facit att bygga mot; den ska lagas, inte frågas om, och
    # den säger ingenting om huruvida BOKEN är klar. Att blanda ihop de två
    # tvingade användaren att ta ställning till buggar i `pipeline/` för att en
    # färdig bok skulle kunna arkiveras — se `pipeline/decisions.py`.
    for qid, text in blocking_questions(workdir):
        hinder.append("öppen boknivåfråga %s: %s" % (qid, text.strip()))

    return hinder


def plan(workdir, namn=None):
    """Vad arkiveringen skulle göra, utan att röra något.

    Returnerar en dict med `namn`, `hinder`, `atgarder` och `klart` — där
    `klart` är True när allt redan är på plats (idempotens).
    """
    workdir = Path(workdir).resolve()
    rot = repo_root(workdir)
    namn, fel = standard_name(workdir, namn)
    if fel:
        return {"namn": None, "hinder": [fel], "atgarder": [], "klart": False}

    m = Manifest.load(workdir)
    källa = Path(m.data["source"]["path"])
    mål_pdf = rot / "arkiv" / (namn + ".pdf")
    mål_md = rot / "bibliotek" / (namn + ".md")
    bok_md = workdir / "export" / "bok.md"

    hinder, atgarder = readiness(workdir), []

    if mål_pdf.exists():
        pass  # redan arkiverad
    elif not källa.exists():
        hinder.append(
            "käll-PDF:en finns varken i %s eller som %s. Den kan inte "
            "arkiveras i efterhand — lägg tillbaka filen i import/ först."
            % (källa, mål_pdf))
    elif not m.source_matches(källa):
        hinder.append(
            "%s har inte samma sha256 som manifestet bokförde. Det är inte "
            "den PDF boken extraherades ur — arkivera den inte." % källa)
    else:
        atgarder.append(("flytta", källa, mål_pdf))

    if not bok_md.exists():
        pass  # redan rapporterat som hinder ovan
    elif not mål_md.exists() or mål_md.read_bytes() != bok_md.read_bytes():
        atgarder.append(("kopiera", bok_md, mål_md))

    return {"namn": namn, "hinder": hinder, "atgarder": atgarder,
            "klart": not atgarder and not hinder}


def archive(workdir, namn=None, verkstall=False):
    """Utför arkiveringen. Vägrar så länge `readiness()` har poster.

    Returnerar samma dict som `plan()`, med `utfort` ifyllt.
    """
    p = plan(workdir, namn)
    p["utfort"] = []
    if p["hinder"] or not verkstall:
        return p
    for slag, src, dst in p["atgarder"]:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if slag == "flytta":
            # shutil.move över filsystemgränser behåller innehållet; sha256
            # kontrolleras redan i plan(). Filen raderas aldrig.
            shutil.move(str(src), str(dst))
        else:
            shutil.copy2(str(src), str(dst))
        p["utfort"].append((slag, str(src), str(dst)))
    return p


def unarchived_source(workdir):
    """Käll-PDF:ens sökväg om den ligger kvar i `import/`, annars None.

    Det här är återkopplingen som saknades: `status` kan säga att boken är
    färdig OCH att dess PDF fortfarande står i inkorgen.
    """
    workdir = Path(workdir).resolve()
    try:
        m = Manifest.load(workdir)
    except Exception:
        return None
    källa = Path(m.data["source"]["path"])
    if not källa.exists():
        return None
    return källa if källa.parent.name == "import" else None
