"""CLI för rollspelsripparen.

    python3 -m pipeline analysera <pdf> [--workdir DIR] [--system ID]
    python3 -m pipeline rendera <pdf> [--workdir DIR] [--sidor 3,5-9] [--alla] [--dpi N]
    python3 -m pipeline extrahera-text <pdf> [--workdir DIR]
    python3 -m pipeline radboxar <pdf> [--workdir DIR] [--sidor 27-29] [--force]
    python3 -m pipeline identifiera-system <pdf> [--workdir DIR]
    python3 -m pipeline jobb --workdir DIR [--typ transkription|korrektur] [--max N]
    python3 -m pipeline bokfor --workdir DIR
    python3 -m pipeline validera --workdir DIR [--system ID] [--force]
    python3 -m pipeline forbesikta --workdir DIR [--sidor 40-44] [--force]
    python3 -m pipeline sammanfoga --workdir DIR
    python3 -m pipeline rapport --workdir DIR
    python3 -m pipeline frys --workdir DIR
    python3 -m pipeline diffa --workdir DIR
    python3 -m pipeline exportera --workdir DIR [--format md,csv,alla]
    python3 -m pipeline konvertera --source BOK.JSON --from dod-t100 --to dod91
    python3 -m pipeline status --workdir DIR
    python3 -m pipeline system
"""
import argparse
import json
import sys
from pathlib import Path


def parse_pages(spec):
    if not spec:
        return None
    pages = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            pages.update(range(int(a), int(b) + 1))
        elif part:
            pages.add(int(part))
    return pages


def resolve_workdir(args, pdf=None):
    from .manifest import default_workdir
    if getattr(args, "workdir", None):
        return Path(args.workdir)
    if pdf:
        return default_workdir(pdf)
    sys.exit("--workdir krävs för detta kommando")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rippare", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, pdf_arg=False, **kw):
        p = sub.add_parser(name, **kw)
        if pdf_arg:
            p.add_argument("pdf", help="sökväg till PDF")
        p.add_argument("--workdir", help="arbetskatalog (default arbete/<slug>)")
        return p

    p = add("analysera", pdf_arg=True,
            help="dokumenttyps-detektering + manifest (+ systemidentifiering)")
    p.add_argument("--system", help="ange regelsystem manuellt (t.ex. dod)")

    p = add("rendera", pdf_arg=True, help="rendera sidor till PNG")
    p.add_argument("--sidor", help="t.ex. 3,5-9 (default: alla som behöver)")
    p.add_argument("--alla", action="store_true",
                   help="rendera även sidor med textlager")
    p.add_argument("--dpi", type=int, default=150)
    p.add_argument("--graskala", action="store_true")

    add("extrahera-text", pdf_arg=True, help="extrahera inbäddat textlager")

    p = add("radboxar", pdf_arg=True,
            help="mät tryckta radboxar ur sidbilden (ger source.bbox)")
    p.add_argument("--sidor", help="t.ex. 27-29 (default: alla)")
    p.add_argument("--force", action="store_true",
                   help="mät om även sidor som redan har radboxar.json")

    add("identifiera-system", pdf_arg=True, help="gissa regelsystem")

    p = add("jobb", help="lista väntande jobb (JSON)")
    p.add_argument("--typ", choices=["transkription", "korrektur"],
                   default="transkription")
    p.add_argument("--max", type=int, default=None)

    add("bokfor", help="bokför inkomna transkript (schema-kontroll)")

    p = add("validera", help="systemspecifik validering + korrektioner")
    p.add_argument("--system", help="överstyr systemval")
    p.add_argument("--force", action="store_true",
                   help="validera om även redan validerade sidor")

    p = add("forbesikta", help="deterministisk förbesiktning inför korrektur")
    p.add_argument("--sidor", help="t.ex. 40-44 (default: alla som väntar)")
    p.add_argument("--force", action="store_true",
                   help="skriv om även befintliga heuristik.json")

    add("sammanfoga", help="bygg export/bok.json av bästa version per sida")
    add("frys", help="spara nuvarande bok.md som facit för ordkonservering")
    add("diffa", help="jämför bok.md mot frysningen (ordfrekvenser)")
    add("rapport", help="generera granskningsrapport")

    p = add("exportera", help="exportera md/csv från bok.json")
    p.add_argument("--format", default="alla",
                   help="kommaseparerat: md,csv,alla (docx är avvecklad)")

    p = add("arkivera",
            help="flytta käll-PDF till arkiv/ och bok.md till bibliotek/")
    p.add_argument("--namn", help="standardnamn enligt NAMNSTANDARD.md "
                                  "(SYSTEM-TYP-titel); default arbetskatalogens namn")
    p.add_argument("--verkstall", action="store_true",
                   help="utför flytten (utan flaggan bara torrkörning)")

    p = sub.add_parser(
        "konvertera",
        help="konvertera exakt ett färdigrippat äventyr till en målprofil")
    p.add_argument("--source", required=True,
                   help="exakt sökväg till källans bok.json")
    p.add_argument("--from", dest="source_profile", required=True,
                   help="källprofil (version 1: dod-t100)")
    p.add_argument("--to", dest="target_profile", required=True,
                   help="målprofil (version 1: dod91)")
    p.add_argument("--output-name",
                   help="överstyr härlett äventyrsslug")
    p.add_argument("--force", action="store_true",
                   help="bygg om från originalkällan")
    p.add_argument("--dry-run", action="store_true",
                   help="skriv analys och rapport men publicera inte MD/JSON")

    add("status", help="visa state per steg")
    sub.add_parser("system", help="lista tillgängliga systemadaptrar")

    args = ap.parse_args(argv)

    if args.cmd == "system":
        from .systems import available_systems, Adapter
        for sid in available_systems():
            a = Adapter(sid)
            print("%-12s %s (%s)" % (sid, a.system.get("name"),
                                     ", ".join(a.system.get("aliases", []))))
        return

    if args.cmd == "konvertera":
        from .convert_adventure import (SourceError, WriteError,
                                        convert_adventure)
        from .conversion_rules import ProfileError
        try:
            result = convert_adventure(
                args.source, args.source_profile, args.target_profile,
                output_name=args.output_name, force=args.force,
                dry_run=args.dry_run)
        except SourceError as exc:
            print("fel: %s" % exc, file=sys.stderr)
            return 2
        except ProfileError as exc:
            print("fel: %s" % exc, file=sys.stderr)
            return 4
        except WriteError as exc:
            print("fel: %s" % exc, file=sys.stderr)
            return 5
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 3 if result["status"] == "needs_review" else 0

    if args.cmd == "analysera":
        from .analyze import analyze
        from .detect_system import detect_and_record
        workdir = resolve_workdir(args, args.pdf)
        m = analyze(args.pdf, workdir)
        if not m.data.get("system"):
            detect_and_record(args.pdf, workdir, manual=args.system)
        elif args.system:
            detect_and_record(args.pdf, workdir, manual=args.system)
        print("arbetskatalog:", workdir)
        return

    if args.cmd == "rendera":
        from .render import render
        workdir = resolve_workdir(args, args.pdf)
        render(args.pdf, workdir, pages=parse_pages(args.sidor),
               dpi=args.dpi, all_pages=args.alla, grayscale=args.graskala)
        return

    if args.cmd == "extrahera-text":
        from .extract_text import extract_text
        workdir = resolve_workdir(args, args.pdf)
        extract_text(args.pdf, workdir)
        return

    if args.cmd == "radboxar":
        from .rows import measure
        workdir = resolve_workdir(args, args.pdf)
        for no, summering in measure(args.pdf, workdir,
                                     pages=parse_pages(args.sidor),
                                     force=args.force):
            if summering is None:
                print("sida %3d: radboxar.json finns redan (--force mäter om)"
                      % no)
            else:
                print("sida %3d: %3d rader, %2d grafikband%s"
                      % (no, summering["rader"], summering["grafik"],
                         "  VARNING: grafik dominerar, mätningen är opålitlig"
                         if summering["dominerande_grafik"] else ""))
        return

    if args.cmd == "identifiera-system":
        from .detect_system import detect
        workdir = args.workdir
        for r in detect(args.pdf, workdir):
            print("%-12s score=%-6s confidence=%-5s %s"
                  % (r["system"], r["score"], r["confidence"],
                     ", ".join(r["evidence"][:6])))
        return

    workdir = resolve_workdir(args)

    if args.cmd == "jobb":
        from .jobs import transcription_jobs, review_jobs
        jobs = (transcription_jobs(workdir, limit=args.max)
                if args.typ == "transkription"
                else review_jobs(workdir, limit=args.max))
        print(json.dumps(jobs, ensure_ascii=False, indent=2))
        return

    if args.cmd == "bokfor":
        from .jobs import ingest_transcripts
        ok, rejected = ingest_transcripts(workdir)
        print("bokförda: %d sidor %s" % (len(ok), ok if ok else ""))
        for no, problem in rejected:
            print("AVVISAD sida %d: %s" % (no, problem))
        return

    if args.cmd == "validera":
        from .validate import validate
        from .systems import load
        from .manifest import Manifest
        m = Manifest.load(workdir)
        system_id = args.system or (m.data.get("system") or {}).get("id")
        if not system_id:
            sys.exit("inget system valt — kör analysera med --system eller "
                     "ange --system här")
        validate(workdir, load(system_id), force=args.force)
        return

    if args.cmd == "forbesikta":
        from .preflight import preflight
        results = preflight(workdir, pages=parse_pages(args.sidor),
                            force=args.force)
        if not results:
            print("inga sidor väntar på korrektur")
        for no, counts in results:
            if counts is None:
                print("sida %3d: heuristik.json finns redan (--force skriver om)"
                      % no)
            else:
                total = sum(counts.values())
                print("sida %3d: %2d kandidater/flaggor  %s"
                      % (no, total,
                         ", ".join("%s=%d" % (k, v)
                                   for k, v in counts.items() if v)))
        # Typdriften är en boknivåsignal och kan inte ses i sidloopen: varje
        # enskild sida är rimlig, det är övergången mellan dem som är felet.
        from .preflight import book_pages, scan_drift
        for hit in scan_drift(book_pages(workdir)):
            print("\nTYPDRIFT: %s" % hit)
        return

    if args.cmd == "frys":
        from .freeze import freeze
        path, antal = freeze(workdir)
        print("fryst %d ord -> %s" % (antal, path))
        return

    if args.cmd == "diffa":
        from .freeze import diff, format_diff
        print(format_diff(diff(workdir)))
        return

    if args.cmd == "sammanfoga":
        from .merge import merge
        merge(workdir)
        return

    if args.cmd == "rapport":
        from .report import build_report
        print(build_report(workdir))
        return

    if args.cmd == "exportera":
        from .export import export_markdown, export_csv, export_docx
        # `alla` omfattar inte docx: markdown är läsformatet (användarbeslut
        # 2026-07-29). DOCX-generatorn saknar rendering för statblockens
        # vapentabeller och skulle annars tysta producera ofullständiga filer.
        formats = set(args.format.replace("alla", "md,csv").split(","))
        # Ett okänt format skrev tidigare ingenting och avslutade med 0:
        # `--format markdown` (i stället för `md`) såg ut som en lyckad export
        # men lämnade bok.md orörd. En tyst nolloperation på en stavfelad flagga
        # är värre än ett fel — man tror att exporten är gjord.
        okända = formats - {"md", "csv", "docx"}
        if okända:
            ap.error("okänt format: %s (giltiga: md, csv, alla; docx är "
                     "avvecklad)" % ", ".join(sorted(okända)))
        if "md" in formats:
            export_markdown(workdir)
        if "csv" in formats:
            export_csv(workdir)
        if "docx" in formats:
            export_docx(workdir)
        return

    if args.cmd == "arkivera":
        from .archive import archive
        r = archive(workdir, args.namn, verkstall=args.verkstall)
        if r["hinder"]:
            print("ARKIVERAS INTE — %d hinder:" % len(r["hinder"]))
            for h in r["hinder"]:
                print("  -", h)
            return 1
        if r["klart"]:
            print("redan arkiverad: %s" % r["namn"])
            return 0
        for slag, src, dst in r["atgarder"]:
            print("%-8s %s -> %s"
                  % (slag.upper() if args.verkstall else slag, src, dst))
        print("%s: %d åtgärder"
              % ("ARKIVERAT" if args.verkstall else "TORRKÖRNING",
                 len(r["atgarder"])))
        return 0

    if args.cmd == "status":
        from .manifest import Manifest
        m = Manifest.load(workdir)
        s = m.summary()
        print("källa: %s (%d sidor)" % (m.data["source"]["path"],
                                        m.data["source"]["pages"]))
        print("system:", (m.data.get("system") or {}).get("id", "ej valt"))
        print("dokumenttyp:", m.data.get("doc_type", {}).get("class_counts"))
        print("states:", s["states"])
        print("needs_review (manifest):", s["needs_review"])
        # Manifestets siffra ovan sätts vid bokföringen och följer inte med när
        # advokaten lägger till eller stänger en flagga. Den riktiga siffran
        # står i sidfilerna.
        from .corrections import review_flag_counts
        flaggor = review_flag_counts(workdir)
        print("granskningsflaggor: %d öppna på %d sidor, %d avgjorda"
              % (flaggor["oppna"], flaggor["sidor_med_oppna"],
                 flaggor["avgjorda"]))
        if flaggor["oppna"]:
            varst = sorted(flaggor["per_sida"].items(),
                           key=lambda kv: (-kv[1], kv[0]))[:8]
            print("   tyngst: %s%s"
                  % (", ".join("s.%d (%d)" % kv for kv in varst),
                     " …" if len(flaggor["per_sida"]) > 8 else ""))
        from .decisions import blocking_questions, tool_questions
        oppna = blocking_questions(workdir)
        if oppna:
            print("ÖPPNA BOKNIVÅFRÅGOR: %d — boken är inte avslutad" % len(oppna))
            for qid, text in oppna:
                print("   %s %s" % (qid, text))
        verktyg = tool_questions(workdir)
        if verktyg:
            print("VERKTYGSFRÅGOR: %d — blockerar INTE boken, ska lagas"
                  % len(verktyg))
            for qid, text in verktyg:
                print("   %s %s" % (qid, text[:100]))
        # Återkopplingen som saknades: en färdig bok vars käll-PDF står kvar i
        # inkorgen såg ut precis som en avslutad. Grundreglernas tre delar låg
        # kvar tills de raderades för hand, och då var den inbäddade
        # skanningen borta för all forensik.
        from .archive import unarchived_source, uncorrected_pages
        # `states: {'validated': 50}` betyder INTE att korrekturet är gjort —
        # pipelinen lyfter aldrig en sida över `validated`. Del III såg därför
        # ut precis som den färdiga del I trots att 26 av 50 sidor aldrig varit
        # hos advokaten.
        okorr = uncorrected_pages(workdir)
        if okorr:
            print("EJ KORREKTURLÄST: %d sidor saknar final.json (%s)"
                  % (len(okorr), ", ".join(str(n) for n in okorr[:12])
                     + (" …" if len(okorr) > 12 else "")))
        # En export som byggts med äldre kod ser ut precis som en färsk. Det
        # var så `bibliotek/…del2` bar brytfel som redan var lagade i koden.
        from .provenance import check_exports
        for varning in check_exports(workdir):
            print("EXPORTENS PROVENIENS: %s" % varning)
        from .archive import unarchived_source
        kvar = unarchived_source(workdir)
        if kvar:
            print("EJ ARKIVERAD: käll-PDF:en ligger kvar i import/ (%s)"
                  % kvar.name)
            print("   arkivera med: python3 -m pipeline arkivera "
                  "--workdir %s --namn <SYSTEM-TYP-titel> --verkstall"
                  % workdir)
        if s["errors"]:
            print("fel:")
            for no, err in s["errors"]:
                print("  sida %d: %s" % (no, err))
        return


if __name__ == "__main__":
    sys.exit(main())
