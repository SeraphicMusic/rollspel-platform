#!/usr/bin/env python3
"""Vilka av `diffa`s ordändringar är FÖRKLARADE av en applicerad korrektion?

`diffa` svarar på om orden ändrats. Den svarar inte på om ändringen var
avsedd — och det är den frågan grinden faktiskt ställer: *noll oförklarade
ordförändringar*. Skillnaden avgjordes hittills genom att en människa läste
diffens ordlista mot sidfilernas korrektionsposter, en bok i taget. Det är en
mekanisk jämförelse och hör därför inte hemma i en läsning (AGENTER.md Regel 5).

Metoden är att attribuera, inte att räkna. Varje applicerad korrektionspost bär
`original` och `corrected`; skillnaden mellan deras ordmängder är precis den
ordändring posten utger sig för att orsaka. Summeras det över bokens alla
applicerade poster får man den ordändring som ÄR redovisad, och det som blir
kvar när den dras från `diffa`s utfall är det som ingen post tar ansvar för.

Ett kvarvarande ord är inte automatiskt ett fel — en tabellmontering flyttar
text mellan `bok.md` och `tabeller/*.csv`, och en omtypning kan lägga till
markdown som tokeniseraren redan sållar. Men det är alltid något som ska kunna
förklaras, och att det står utskrivet är hela poängen: den felklass frysningen
finns för (sju tabellrader som föll ur del I:s `bok.md` utan att något varnade)
ser i diffen ut exakt som en avsedd rättning, ända tills man frågar vilken post
som bär den.

Skriptet ÄNDRAR INGENTING. Exitkod 0 = allt förklarat, 1 = något kvarstår.

    python3 scripts/oforklarade_ord.py arbete/<slug>
    python3 scripts/oforklarade_ord.py --alla
"""
import argparse
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pipeline.export import _samma_namn  # noqa: E402
from pipeline.freeze import diff, words  # noqa: E402


def _las(path):
    """Sidfilerna är skrivna av olika agenter över lång tid; någon har BOM."""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError):
        return None


# `freeze.words` behåller skiljetecken som sitter fast i token, eftersom den
# mäter ordMÄNGD och inte ordform. Här ska två sidor av samma rättning paras
# ihop, och då är `totalsförsvaret.` ur löptexten och `totalsförsvaret` ur
# postens `original` samma ord. Attribueringen sker därför på kärnan — men
# utskriften behåller tokenets fulla form, för det är den diffen visar.
_SKILJE = "”“’‘\"'.,;:!?()[]{}<>«»…–—-*"

# Elementtyper som `pipeline/export.py` inte skriver till `bok.md`. Sidhuvuden
# och sidfötter är sidgrafik, inte boktext, och en rättning av dem ändrar
# ingenting i den fil grinden mäter.
_EJ_I_LASEXPORTEN = {"page_artifact"}


def _karna(token):
    k = token.strip(_SKILJE)
    return k.casefold() or token.casefold()


def _elementtext(el, foregaende_rubrik=None):
    """Den text ett element bidrar med till läsexporten, grovt räknat.

    Grovt räcker: värdet används bara för att kvitta ord i ett TILLAGT element,
    och kvittningen är per ord. Tas för mycket med kvittas ord som ändå inte
    fanns i diffen, vilket inte döljer något; tas för lite med står resten kvar
    som oförklarad, vilket är åt rätt håll.
    """
    delar = [el.get("text") or ""]
    data = el.get("data")
    if isinstance(data, dict):
        # `export._statblock_md` skriver INTE ut `data.name` när rutans egen
        # rubrik står omedelbart före och bär samma namn — trycket sätter
        # NPC-namnet en gång. Räknas namnet ändå krediteras det som ett nytt
        # ord, och rubrikens gamla skrivning (`Eldritch Mercy` mot
        # `ELDRITCH MERCY`) blir en strandad förlust som ingen post kan bära.
        #
        # Villkoret ÄRVS ur exportören i stället för att skrivas av: två kopior
        # av samma regel svarar förr eller senare olika på samma bok.
        if el.get("type") == "statblock" and _samma_namn(data.get("name"),
                                                         foregaende_rubrik):
            data = {k: v for k, v in data.items() if k != "name"}
        stack = [data]
        while stack:
            nod = stack.pop()
            varden = nod.values() if isinstance(nod, dict) else nod
            for v in varden:
                if isinstance(v, (dict, list)):
                    stack.append(v)
                elif v is not None:
                    delar.append(str(v))
    return " ".join(delar)


def _pa_karna(counter):
    ut = collections.Counter()
    for token, n in counter.items():
        ut[_karna(token)] += n
    return ut


def _forlegad(post, frys_text):
    """Är postens ändring redan inbakad i frysningen?

    Ja när `corrected` står ordagrant i den frysta läsexporten medan
    `original` inte gör det — då gjordes ändringen före frysningen och dess
    ordkredit har ingen motpart i diffen. Tomma strängar och strängar som
    står på BÅDA sidor (korta ord som förekommer på andra ställen) räknas
    aldrig som förlegade: hellre en synlig oförklarad rad än en tyst
    felkvittning.
    """
    corrected = (post.get("corrected") or "").strip()
    original = (post.get("original") or "").strip()
    if not corrected or corrected not in frys_text:
        return False
    return bool(original) and original not in frys_text


def redovisad_andring(workdir):
    """Ordändringen som bokens applicerade korrektionsposter tar ansvar för.

    Returnerar (borta, nya, kallor) där de två första är Counter över ord och
    den sista mappar ord -> lista av (sida, element-id, kind) så att ett
    förklarat ord går att spåra till sin post utan att man öppnar filerna.
    """
    borta, nya = collections.Counter(), collections.Counter()
    berorda = set()
    kallor = collections.defaultdict(list)
    from pipeline.freeze import freeze_path
    _frys = freeze_path(workdir)
    frys_text = _frys.read_text(encoding="utf-8") if _frys.is_file() else None
    pages = pathlib.Path(workdir) / "pages"
    for f in sorted(pages.glob("page_*.json")):
        # final.json är sidans slutversion; finns den är validated.json en
        # tidigare version av SAMMA sida och dess poster skulle dubbelräknas.
        if f.name.endswith(".validated.json"):
            if (pages / f.name.replace(".validated.", ".final.")).is_file():
                continue
        elif not f.name.endswith(".final.json"):
            continue
        data = _las(f)
        if not isinstance(data, dict):
            continue
        sida = f.name[5:8]
        # Text som gått UPP i ett annat element. En montering (statblock,
        # table) märks `added_by` av advokaten, men dess innehåll kommer ur
        # draftens egna element — de ligger kvar med `removed: true` och
        # `source.merged_into`. Räknas monteringen som ett rent tillägg
        # krediteras samma ord två gånger på nya-sidan, och den BORTA-sida som
        # hör ihop med dem blir strandad: `Eldritch`, `Mercy`, `GahMan` föll ut
        # som oförklarade förluster fast namnen stod kvar i rutans rubrik.
        uppgangen = collections.defaultdict(collections.Counter)
        senaste_rubrik = None
        for el in data.get("elements") or []:
            mal = (el.get("source") or {}).get("merged_into")
            if mal:
                uppgangen[mal] += _pa_karna(words(_elementtext(el)))
        for el in data.get("elements") or []:
            # Ett element som advokaten LADE TILL bär inga korrektionsposter —
            # dess ord är nya i boken utan att någon post utger sig för att ha
            # skapat dem. Tillägget är ändå redovisat: `added_by` säger vem som
            # gjorde det och varför. Utan den här grenen rapporteras varje
            # räddad rad som en oförklarad ordökning, och ett instrument som
            # fäller en korrekt komplettering lär användaren att bortse från
            # det. (Advokaten på sieger-bauhaus-block s. 2 fann en hel
            # illustration som saknades i draften — ingen regel och ingen
            # textjämförelse ser den, bara att bilderna räknas.)
            # En BILDBESKRIVNING är aldrig boktext. Den är skriven av agenten
            # för att säga vad som syns, och den skrivs om varje gång någon
            # tittar närmare — s. 6:s och s. 12:s föll på fem respektive fyra
            # punkter vid beskärning. Räknas dess ord som bokens ord blir
            # grinden ett brus som larmar på varje förbättrad beskrivning, och
            # ett instrument som alltid larmar slutar man läsa.
            #
            # Villkoret är elementTYPEN, inte `added_by`: en beskrivning som
            # rättats med en korrektionspost är lika lite boktext som en som
            # lagts till. Bägge sidorna redovisas — den gamla lydelsen ur
            # posternas `original` lämnar boken, den nya kommer in — så en
            # beskrivning som FÖRSVINNER syns fortfarande.
            if el.get("type") == "heading" and not el.get("removed"):
                senaste_rubrik = el.get("text")
            if el.get("type") == "illustration":
                # En post på ett element som LADES TILL efter frysningen kan
                # aldrig förklara ett bortfall: dess `original` stod aldrig i
                # den `bok.md` grinden jämför mot. `p027_e00` skrevs om efter
                # att ha lagts till, och dess gamla beskrivnings ord krediterades
                # som förluster — en överkredit som åt upp en riktig kvittning.
                #
                # Och ett ORÖRT bildelement krediteras inte alls. Dess text
                # står oförändrad på båda sidor av frysningen och nettar redan
                # till noll i `diffa` — en kredit här har ingen motpart i
                # diffen och ligger och väntar på att sluka en obesläktad
                # ändring av samma ord. Det var så `"stora` → `”stora` på
                # elefanten s. 5 strandade: kartbeskrivningen på samma sida
                # innehöll ordet `stora`, krediten åt upp nya-sidan av en
                # riktig kvittning, och citatbytets borta-sida stod kvar som
                # oförklarad. Samma överkreditklass som `TERMINAL` ×9.
                # Och ett ÄNDRAT bildelement krediterar bara postens egen
                # ordändring — original mot corrected — aldrig hela sin text.
                # Beskrivningens oförändrade del står på båda sidor av
                # frysningen och nettar redan till noll i `diffa`; krediteras
                # den ändå väntar den på att sluka en obesläktad ändring av
                # samma ord. Krugals kartbeskrivning (s. 10) innehöll orden
                # `Krugals komplex` och åt upp kvittningen för citatbytet
                # `"Krugals komplex"` → `”…”` på s. 1. Full text krediteras
                # bara för TILLAGDA element, vars ord faktiskt är nya.
                # Ett TILLAGT bildelement vars beskrivning redan står ordagrant
                # i frysningen är äldre än frysningen: orden står på båda sidor
                # och nettar redan till noll i `diffa`. Krediteras de ändå är
                # det samma överkredit som för orörda element — Gripeborgs två
                # juli-tillägg åt upp nykvittningen för fyra obesläktade
                # citatglyfbyten (`av.”`, `in”.`, `’Händer’`, `’Klor’`).
                # Frysningen avgör, inte tilläggsdatumet: beskrivningen renderas
                # oradbruten i bok.md, så substrängtestet är exakt.
                if el.get("added_by") and not (
                        frys_text and (el.get("text") or "").strip()
                        and (el.get("text") or "").strip() in frys_text):
                    for ord_, n in _pa_karna(words(_elementtext(el))).items():
                        nya[ord_] += n
                        kallor[ord_].append((sida, el.get("id"), "bildtext"))
                    continue
                for c in el.get("corrections") or []:
                    if not c.get("applied"):
                        continue
                    for ord_, n in _pa_karna(words(c.get("original") or "")).items():
                        borta[ord_] += n
                        kallor[ord_].append((sida, el.get("id"), "bildtext"))
                    for ord_, n in _pa_karna(words(c.get("corrected") or "")).items():
                        nya[ord_] += n
                        kallor[ord_].append((sida, el.get("id"), "bildtext"))
                continue
            if el.get("added_by"):
                # En UTBRYTNING är ingen tillägg. Advokaten bryter ut en rubrik
                # som låg inbakad först i sitt stycke, ger den ett nytt id och
                # märker den `added_by` — men orden fanns redan i boken, och de
                # står kvar i postens `original`. Räknas hela elementtexten som
                # ny konsumerar den nya-sidan av diffen, och den BORTA-sida som
                # hör ihop med den blir strandad: `Biobunker` föll ut som två
                # oförklarade förluster fast `BIOBUNKER` stod kvar i samma
                # rubrik. Elementets egna posters `original` dras därför bort —
                # det är precis den text som inte är ny.
                fanns = collections.Counter(uppgangen.get(el.get("id")) or {})
                for c in el.get("corrections") or []:
                    if c.get("applied"):
                        fanns += _pa_karna(words(c.get("original") or ""))
                for ord_, n in (_pa_karna(words(_elementtext(el, senaste_rubrik)))
                                - fanns).items():
                    nya[ord_] += n
                    kallor[ord_].append((sida, el.get("id"), "tillagt"))
            # En post på ett element som ALDRIG NÅR läsexporten får inte
            # krediteras. `page_artifact` renderas inte alls, och de nio tömda
            # sidfötterna på MUT-AVE-terminal-state krediterade ordet
            # `TERMINAL` nio gånger — en överkredit som tyst nollställde
            # motparten till en riktig kvittning på en helt annan sida.
            # Grinden mäter `bok.md`, och då ska bara det som hamnar där räknas.
            if el.get("type") in _EJ_I_LASEXPORTEN:
                continue
            for c in el.get("corrections") or []:
                if not c.get("applied"):
                    continue
                # En post vars ändring är ÄLDRE än frysningen krediterar
                # ingenting: dess utfall står redan på båda sidor av diffen
                # och nettar till noll. Krediten ligger annars kvar och äter
                # motparten till en obesläktad färsk ändring av samma kärna —
                # Skymningslandets juli-revert (`är inte`→`inte`) konsumerade
                # borta-sidan av s. 7:s `...är`→`... är`. Åldern mäts, den
                # gissas inte: en färsk posts `original` står i frysningen
                # (det var texten före ändringen); en förlegad posts
                # `corrected` står där medan dess `original` inte gör det.
                if frys_text and _forlegad(c, frys_text):
                    continue
                fore = _pa_karna(words(c.get("original") or ""))
                efter = _pa_karna(words(c.get("corrected") or ""))
                # Kärnor posten RÖR, utöver dem den nettoförändrar. En
                # rättning kan byta skiljetecknen runt ett ord utan att röra
                # ordet: advokaten skrev om `"N 2420"/"IN 2421"` till
                # `"…N 2421"` på sieger-bauhaus-block s. 1, och kärnan `n`
                # står då i både `original` och `corrected`, tar ut sig själv
                # i nettot — medan `diffa` ser två olika tokens och rapporterar
                # både ett bortfall och ett tillskott.
                berorda.update(fore)
                berorda.update(efter)
                for ord_, n in (fore - efter).items():
                    borta[ord_] += n
                    kallor[ord_].append((sida, el.get("id"), c.get("kind")))
                for ord_, n in (efter - fore).items():
                    nya[ord_] += n
                    kallor[ord_].append((sida, el.get("id"), c.get("kind")))
    return borta, nya, berorda, kallor


def oforklarat_pa_karna(workdir, borta, nya):
    """Vad av ordändringen `borta`/`nya` som ingen redovisad post bär.

    Delas av `granska` (mot frysningen) och `uppdatera_bibliotek` (mot
    läskopian). De ställer samma fråga om olika jämförelsepunkter, och två
    kopior av regeln skulle förr eller senare svara olika på samma bok.
    Nycklarna i utfallet är ordKÄRNOR, inte tokens.
    """
    red_borta, red_nya, berorda, kallor = redovisad_andring(workdir)
    kvar = {"borta": _pa_karna(collections.Counter(borta)) - red_borta,
            "nya": _pa_karna(collections.Counter(nya)) - red_nya}

    # Skiljeteckensbyte runt ett ord som en post RÖRT: kärnan står kvar på
    # båda sidor och nettar till noll, men `diffa` ser två olika tokens. Det
    # förklaras — dock aldrig mer än vad som faktiskt tar ut sig självt, så en
    # verklig förlust kan inte kvittas av ett obesläktat tillskott.
    for k in set(kvar["borta"]) & set(kvar["nya"]) & berorda:
        n = min(kvar["borta"][k], kvar["nya"][k])
        kvar["borta"][k] -= n
        kvar["nya"][k] -= n
    return kvar, kallor


def granska(workdir):
    d = diff(workdir)
    kvar, kallor = oforklarat_pa_karna(workdir, d["borta"], d["nya"])
    ut = {"fore": d["fore"], "efter": d["efter"], "kallor": kallor}
    for etikett in ("borta", "nya"):
        # Attribuera på kärnan, men redovisa tokenets fulla form: det är den
        # `diffa` skriver ut, och en rad som inte går att söka i diffens
        # utskrift hjälper ingen.
        oforklarat, forklarat = collections.Counter(), collections.Counter()
        for token, n in collections.Counter(d[etikett]).items():
            k = _karna(token)
            o = min(n, kvar[etikett][k])
            kvar[etikett][k] -= o
            if o:
                oforklarat[token] += o
            if n - o:
                forklarat[token] += n - o
        ut["oforklarat_" + etikett] = oforklarat
        ut["forklarat_" + etikett] = forklarat
    return ut


def skriv(namn, r, utforlig=False):
    ob, on = r["oforklarat_borta"], r["oforklarat_nya"]
    fb, fn = r["forklarat_borta"], r["forklarat_nya"]
    rent = not ob and not on
    forklarat = sum(fb.values()) + sum(fn.values())
    oforklarat = sum(ob.values()) + sum(on.values())
    print("%-62s ord %d -> %d   förklarat %d/%d   OFÖRKLARAT %d  %s" % (
        namn, r["fore"], r["efter"], forklarat, forklarat + oforklarat,
        oforklarat, "" if rent else "<-- GRANSKA"))
    for etikett, poster in (("BORTA", ob), ("NYA", on)):
        for ord_, n in poster.most_common():
            print("        OFÖRKLARAT %-6s %-28s %d" % (etikett, ord_, n))
    if utforlig:
        for etikett, poster in (("BORTA", fb), ("NYA", fn)):
            for ord_, n in poster.most_common():
                sp = r["kallor"].get(_karna(ord_)) or []
                var = ", ".join("s.%s %s [%s]" % k for k in sp[:3])
                print("        förklarat  %-6s %-28s %d   %s" % (etikett, ord_, n, var))
    return rent


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workdir", nargs="?", help="arbete/<slug>")
    ap.add_argument("--alla", action="store_true", help="alla böcker under arbete/")
    ap.add_argument("--utforlig", action="store_true",
                    help="skriv ut även de förklarade orden med sin källpost")
    a = ap.parse_args()

    if a.alla:
        wds = [p for p in sorted(pathlib.Path("arbete").iterdir())
               if (p / "export" / "bok.frysning.md").is_file()]
    elif a.workdir:
        wds = [pathlib.Path(a.workdir)]
    else:
        ap.error("ange en arbetskatalog eller --alla")

    allt_rent = True
    for wd in wds:
        try:
            r = granska(wd)
        except FileNotFoundError as e:
            print("%-62s HOPPAS ÖVER: %s" % (wd.name, e))
            continue
        allt_rent &= skriv(wd.name, r, a.utforlig)
    return 0 if allt_rent else 1


if __name__ == "__main__":
    sys.exit(main())
