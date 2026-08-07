#!/usr/bin/env python3
"""Skriv ut `added_by` på element som en advokat lagt till utan att märka dem.

Ett element som saknas i `page_NNN.validated.json` men står i sidans
`final.json` har lagts till under korrekturen. Vem som gjorde det är alltså
inte en gissning utan en mätning: final-filen är advokatens produkt, och
draften är facit för vad som fanns före.

Fältet är inte kosmetik. `scripts/oforklarade_ord.py` attribuerar ordändringar
till den post som bär dem, och för ett TILLAGT element är `added_by` hela
redovisningen — ingen korrektionspost utger sig för att ha skapat orden. Utan
märkningen räknas varje räddad illustration som en oförklarad ordökning, och
grinden fäller boken för en komplettering som var riktig. På
MUT-AVE-terminal-state gällde det sju illustrationer: fem kroppsdiagram och två
porträtt som draften saknade helt.

Skriptet rör bara element som SAKNAR fältet, och bara sådana som saknas i
draften. En andra körning rör noll poster.

    python3 scripts/materialisera_added_by.py arbete/<slug> [--verkstall]
"""
import argparse
import glob
import json
import os
import sys

STANDARD = "agent:djavulens-advokat"


def _las(path):
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workdir")
    ap.add_argument("--upphovsman", default=STANDARD)
    ap.add_argument("--verkstall", action="store_true")
    args = ap.parse_args()

    rörda = 0
    filer = 0
    for final in sorted(glob.glob(os.path.join(args.workdir, "pages",
                                               "page_*.final.json"))):
        draft = final.replace(".final.json", ".validated.json")
        if not os.path.exists(draft):
            continue
        try:
            fdata, ddata = _las(final), _las(draft)
        except (ValueError, OSError):
            continue
        fanns = {el.get("id") for el in ddata.get("elements") or []}
        n = 0
        for el in fdata.get("elements") or []:
            if el.get("added_by") or el.get("removed"):
                continue
            if el.get("id") in fanns:
                continue
            # ATT SAKNAS I DRAFTEN RÄCKER INTE. En sida som monterats bär en
            # mängd nya id:n som inte är tillägg alls: utbrytningar ur ett
            # befintligt element (`p003_e03h`), delade fältrader (`p035_e01a`)
            # och `table`-element vars celler kommer ur draftens `paragraph`.
            # Deras ord fanns redan i boken. Mätt på MUT-AVE-terminal-state:
            # 117 element saknar id i draften, och bara sju av dem är tillägg.
            # Hade alla märkts hade `oforklarade_ord.py` räknat monteringens
            # ord som NYA, och grinden blivit lösare av en lagning.
            #
            # `illustration` är den enda elementtypen vars `text` är skriven av
            # agenten i stället för hämtad ur trycket — en bildbeskrivning kan
            # inte komma ur draftens ord. Det är en typregel, inte en tröskel,
            # och den kan därför inte råka märka en utbrytning.
            if el.get("type") != "illustration":
                continue
            el["added_by"] = args.upphovsman
            n += 1
            print("  %s %s %s %r" % (os.path.basename(final), el.get("id"),
                                     el.get("type"),
                                     (el.get("text") or "")[:48]))
        if n and args.verkstall:
            with open(final, "w", encoding="utf-8") as fh:
                json.dump(fdata, fh, ensure_ascii=False, indent=1)
                fh.write("\n")
        rörda += n
        filer += 1 if n else 0

    prefix = "" if args.verkstall else "TORRKÖRNING: "
    print("%s%d element märkta i %d filer" % (prefix, rörda, filer))
    return 0


if __name__ == "__main__":
    sys.exit(main())
