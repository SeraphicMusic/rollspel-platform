"""Ordkonservering: frys läsexporten och diffa mot frysningen.

En strukturändring — omtypning, tabellmontering, ändrad geometri — kan tappa
text utan att någonting varnar. Ett `table` vars rader hamnat på fel nyckel
renderar ingenting, men elementet har varken tom `text` eller okänd typ, så
`status` är nöjd, granskningsrapporten är tyst och JSON:en är giltig. Sju
tabellrader föll ur del I:s `bok.md` på precis det viset och upptäcktes bara
för att ordmängden råkade diffas mot en frysning: 33 ord borta.

Kontrollen är enkel nog att alltid göra, och därför ska den inte vara ett
skript man skriver om varje gång:

    python3 -m pipeline frys  --workdir WD      # före ingreppet
    ... ändra, sammanfoga, exportera ...
    python3 -m pipeline diffa --workdir WD      # efter

`diffa` jämför ordfrekvenser, inte rader. Radbrytningar och styckeindelning
ändras med flit vid en omflödning; det som aldrig får ändras oförklarat är
vilka ord som finns i boken.
"""
import collections
import re

from .manifest import export_dir

# Markdownens egen skiljetecken räknas inte som ord: `#`, `>`, `|`, `*` och `_`
# tillkommer och försvinner när rubriker, citatblock och tabeller typas om,
# och de säger ingenting om huruvida boktext gått förlorad.
#
_TOKEN = re.compile(r"[^\s|#*_`>]+")

# Listans märke räknas inte heller som ord, och lades till 2026-08-06. En rad
# som typas om från `paragraph` till `list_item` — vilket `scripts/punktrader.py`
# gör, och som är en RÄTTELSE, för som löptext fogas raden in i föregående
# stycke och listan försvinner som struktur — byter tryckets `•` mot markdownens
# `-`. Diffen larmade då för två "borta" ord i Edsbrytarna: riktigt räknat och
# fel i sak, och ett instrument som fäller en korrekt omtypning lär användaren
# att bortse från det.
#
# Bara det ENSAMMA tecknet räknas bort. Bindestreck inne i ett ord bär
# betydelse — sammansättningar, talintervall, avstavningar som exporten läker —
# och de ska fortfarande vägas.
#
# Tabellens avdelarrad `| --- | --- |` hör till samma klass och lades till
# 2026-08-06. En tryckt tabell som räddas ur löptext — del II s. 25:s
# hemvistuppställning låg som 33 `list_item` och exporten hade där slagit ihop
# skilda tabellrader — tillför sex `---` per tabell som markdownSYNTAX, inte
# som boktext. Utan undantaget rapporterar ordgrinden en korrekt tabellräddning
# som oförklarad ordökning, och ett instrument som fäller rätt ingrepp lär
# användaren att bortse från utfallet. Talstrecket `–` och tankstrecket `—`
# står kvar som ord: de förekommer ensamma i tryckta tabellceller och betyder
# där "inget värde".
_MARKERINGAR = {"-", "•"}


def _ar_markering(token):
    return token in _MARKERINGAR or (len(token) > 1 and set(token) == {"-"})

FREEZE_NAME = "bok.frysning.md"


def freeze_path(workdir):
    return export_dir(workdir) / FREEZE_NAME


def markdown_path(workdir):
    return export_dir(workdir) / "bok.md"


def words(text):
    return collections.Counter(t for t in _TOKEN.findall(text)
                               if not _ar_markering(t))


def freeze(workdir):
    """Spara nuvarande bok.md som facit. Returnerar (sökväg, antal ord)."""
    src = markdown_path(workdir)
    if not src.is_file():
        raise FileNotFoundError(
            "%s saknas — kör `exportera` innan du fryser" % src)
    text = src.read_text(encoding="utf-8")
    dst = freeze_path(workdir)
    dst.write_text(text, encoding="utf-8")
    return dst, sum(words(text).values())


def diff(workdir):
    """Jämför bok.md mot frysningen.

    Returnerar en dict med `fore`, `efter`, `borta` och `nya`, där de två
    sista är ord -> antal. Tom `borta` och tom `nya` betyder att ingen boktext
    har tillkommit eller gått förlorad, oavsett hur mycket strukturen ändrats.
    """
    frys = freeze_path(workdir)
    if not frys.is_file():
        raise FileNotFoundError(
            "%s saknas — kör `frys` före ingreppet" % frys)
    a = words(frys.read_text(encoding="utf-8"))
    b = words(markdown_path(workdir).read_text(encoding="utf-8"))
    return {"fore": sum(a.values()), "efter": sum(b.values()),
            "borta": dict((a - b).most_common()),
            "nya": dict((b - a).most_common())}


def format_diff(result, max_ord=25):
    """Diffen som text, med de vanligaste orden utskrivna."""
    lines = ["ord: %d -> %d" % (result["fore"], result["efter"])]
    for etikett, nyckel in (("BORTA", "borta"), ("NYA", "nya")):
        poster = result[nyckel]
        total = sum(poster.values())
        lines.append("%-6s %d" % (etikett, total))
        for ord_, n in list(poster.items())[:max_ord]:
            lines.append("        %-28s %d" % (ord_, n))
        if len(poster) > max_ord:
            lines.append("        … och %d ord till" % (len(poster) - max_ord))
    if not result["borta"] and not result["nya"]:
        lines.append("Ingen boktext har tillkommit eller gått förlorad.")
    return "\n".join(lines)
