"""Avbildning av transkriptens fria regionnamn på mätningens vokabulär.

Mätningen namnger regioner på LÄGE och håller sig till sex ord:
`vänsterkolumn`, `mittkolumn`, `högerkolumn`, `sidbredd`, `sidhuvud`, `sidfot`
(fler än tre spalter namnges `kolumn 1`…`kolumn N`, se `rows._region_names`).

Transkripten gör inte det. `source.region` är ett fritextfält som vision-
agenter fyllt i medan de såg sidan, och över ikappkörningens 29 böcker finns
**573 distinkta regionnamn** på 4 716 element: `kolumn 1`, `vänsterspalt`,
`mittenkolumn`, `huvudtext`, `helbredd`, `faktaruta`, `sidfot höger`,
`äventyrsförslag-ruta (vänster)`, `vänsterkolumn (dubblett av sida 18)`.

`binda_rader` matchar element mot uppmätta rader på regionnamnet med exakt
strängjämförelse. `kolumn 1` matchar därför aldrig `vänsterkolumn`, och hela
bindningen uteblir. Den här modulen översätter — men bara när översättningen är
MÄTT, aldrig när den är rimlig:

* Ett namn som spänner två spalter (`mittkolumn–högerkolumn`, `vänsterkolumn
  nederst, fortsätter i mittkolumn`) avbildas på ingenting. Elementet står över
  en spaltgräns, och att tvinga in det i den ena vore att sätta en box som ser
  ut som data.
* Säger transkriptet fler spalter än mätningen hittade avbildas ingen
  spaltregion alls på den sidan. Det är precis fallet där mätningen slagit ihop
  två spalter, och en avbildning skulle då lägga två tryckta spalters element i
  ett gemensamt band.
* `mitt` på en sida med två uppmätta spalter är tvetydigt och avbildas inte.

Allt som inte går att avgöra ger `None`, vilket i `binda_rader` betyder att
elementet lämnas obundet. En lucka är en lucka; en påhittad box är ett fel som
ser ut som data.
"""
import re

# `illustration` är mätmotorns namn på ett spaltblock som är en BILDYTA
# (pipeline/rows.py, klass B-passet): det är ingen spalt och får aldrig
# räknas i spaltantalet — annars vägrar bindningen med "mätningen har
# slagit ihop spalter" på varje sida där en illustration står bredvid
# satsen (Tempokalkylatorn s. 1: två textspalter + en bildyta).
FURNITURE = ("sidhuvud", "sidfot", "illustration")
FULL_WIDTH = "sidbredd"

# Namn som talar om HELA satsbredden, inte om en spalt.
_FULL = re.compile(r"huvudtext|helbredd|hela sidan|helsida|sidbredd|"
                   r"över (båda|alla) (spalter|kolumner)|tvärs")

_ORDINAL = re.compile(r"\b(?:kolumn|spalt)\s*(\d+)")
_VANSTER = re.compile(r"vänster")
_HOGER = re.compile(r"höger")
_MITT = re.compile(r"\bmitt(en)?\b|mittkolumn|mittspalt|mittenkolumn")


def _tvatta(raw):
    return re.sub(r"\s+", " ", str(raw or "").strip().lower())


def _spaltreferenser(r):
    """De DISTINKTA spalter ett regionnamn pekar ut.

    Ett namn som nämner två spalter beskriver ett element som spänner en
    spaltgräns, och då är ingen enskild spalt rätt svar. Skiljetecknet duger
    inte som kriterium: `vänsterkolumn, fortsättning från föregående sida`
    innehåller ordet »fortsätt« men pekar bara ut EN spalt, medan
    `vänsterkolumn, fortsätter i mittkolumn` pekar ut två. Det är antalet
    utpekade spalter som avgör, inte hur meningen är skriven.
    """
    ref = set()
    for m in _ORDINAL.finditer(r):
        ref.add("nr%s" % m.group(1))
    if _VANSTER.search(r):
        ref.add("vänster")
    if _MITT.search(r):
        ref.add("mitt")
    if _HOGER.search(r):
        ref.add("höger")
    return ref


def column_count(regions):
    """Antal tryckta spalter enligt transkriptets egna regionnamn, eller None.

    Facit är gratis och redan skrivet: transkriberaren namngav spalten medan
    hen såg sidan. `kolumn 2` betyder tre spalter bara om `kolumn 3` finns —
    i en tvåspaltig bok ÄR `kolumn 2` högerspalten — så räkningen går på det
    högsta ordningstalet respektive på om en mittspalt är namngiven vid namn.
    """
    tvattade = [_tvatta(r) for r in regions if r]
    if not tvattade:
        return None
    hogst = 0
    for r in tvattade:
        for m in _ORDINAL.finditer(r):
            hogst = max(hogst, int(m.group(1)))
    har_v = any(_VANSTER.search(r) for r in tvattade)
    har_h = any(_HOGER.search(r) for r in tvattade)
    har_m = any(_MITT.search(r) for r in tvattade)
    namngivna = 0
    if har_v and har_h and har_m:
        namngivna = 3
    elif har_v and har_h:
        namngivna = 2
    n = max(hogst, namngivna)
    return n or None


def measured_columns(radboxar):
    """Mätningens spaltnamn i x-ordning, tagna ur det BREDASTE avsnittet.

    En sida kan vara tvåspaltig upptill och trespaltig nedtill. Ordningstalen i
    transkriptet (`kolumn 3`) räknas mot sidans faktiska spaltantal, alltså mot
    det avsnitt som har flest — inte mot unionen av alla avsnitts namn, som
    blandar `mittkolumn` från ett avsnitt med `kolumn 1` från ett annat.
    """
    per = {}
    for c in radboxar.get("columns") or []:
        region = c.get("region")
        if region in FURNITURE or region == FULL_WIDTH:
            continue
        nyckel = (round(c.get("y", 0.0), 5), round(c.get("höjd", 0.0), 5))
        per.setdefault(nyckel, []).append((c.get("x", 0.0), region))
    if not per:
        return []
    bredast = max(per.values(), key=len)
    sedda, ut = set(), []
    for _x, region in sorted(bredast):
        if region not in sedda:
            sedda.add(region)
            ut.append(region)
    return ut


def normalize(raw, columns, transcript_columns=None):
    """Ett fritt regionnamn -> mätningens vokabulär, eller None.

    `columns` är sidans uppmätta spaltnamn i x-ordning (`measured_columns`).
    `transcript_columns` är transkriptets eget spaltantal för sidan
    (`column_count`); anges det och skiljer det sig från antalet uppmätta
    spalter avbildas ingen SPALT — mätningen och trycket är då oense om
    sidans indelning, och det är just då en avbildning skulle slå ihop två
    tryckta spalter i ett band.
    """
    r = _tvatta(raw)
    if not r:
        return None

    # Sidhuvud och sidfot först: de bär ofta ett väderstreck (`sidfot höger`)
    # som annars skulle läsas som en spalt.
    for mobel in FURNITURE:
        if r.startswith(mobel):
            return mobel

    ref = _spaltreferenser(r)
    if len(ref) > 1:
        return None

    if _FULL.search(r):
        return FULL_WIDTH

    if not columns or not ref:
        return None
    if transcript_columns is not None and transcript_columns != len(columns):
        return None

    m = _ORDINAL.search(r)
    if m:
        i = int(m.group(1)) - 1
    elif "vänster" in ref:
        i = 0
    elif "höger" in ref:
        i = len(columns) - 1
    else:
        # `mitt` är entydigt bara när det finns en mitt att peka på.
        if len(columns) != 3:
            return None
        i = 1

    if 0 <= i < len(columns):
        return columns[i]
    return None
