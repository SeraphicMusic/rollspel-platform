# Överlämning: ikappkörningens Etapp 4

*Skriven 2026-08-06 mot HEAD `5327e0c`. Allt nedan är MÄTT och går att räkna
fram igen med kommandona i §6. Etapp 0–3 och 5 är körda; det som står här är
det som återstår.*

Klistra in avsnittet »Prompt« nedan i en ny session. Resten av dokumentet är
underlaget den prompten hänvisar till.

---

## Prompt

> Kör Etapp 4 i `docs/IKAPP-ALLA-BOCKER.md`. Underlaget, siffrorna och
> arbetsordningen står i `docs/IKAPP-ETAPP4-PROMPT.md` — läs den först, och läs
> `AGENTER.md` SLAVISKT innan du startar en enda agent.
>
> Tre arbetsströmmar, i den här ordningen:
>
> 1. **63 sidor utan `final.json`** i 10 böcker (§1). Terminal State ensam står
>    för 32. Kör `python3 -m pipeline jobb --workdir <wd> --typ korrektur` för
>    triage och exakta sökvägar.
> 2. **337 screeningkandidater** (§2), tabellfrågorna först — de är den
>    oåterkalleliga klassen. Agenterna ska VERIFIERA listan, inte leta upp
>    mönstren igen (Regel 5).
> 3. **1016 öppna granskningsflaggor** (§3). Fyra böcker bär 563 av dem.
>
> Bindande ramar: max 3 agenter samtidigt TOTALT, aldrig per sida (Regel 2).
> Ingen nästling (Regel 3). En sida per agentuppsättning (Regel 4).
> Specialister på Sonnet, advokaten på Opus, modellen i agentens frontmatter
> och aldrig i anropet (Regel 1). Bildforensik körs synkront, en i taget —
> bakgrundsagenter dödas av 600 s-watchdogen.
>
> Efter varje bok: `sammanfoga`, `exportera`, `diffa`, `rapport`, och
> `python3 scripts/uppdatera_bibliotek.py --verkstall`. `diffa` MÅSTE visa noll
> oförklarade ordförändringar innan boken lämnas — alla 33 är rena i dag, så
> varje avvikelse är din.
>
> Kör allt i ett svep inom de ramarna, rapportera per bok, och stanna bara om
> ordkonserveringen brister eller om du stöter på en fråga som bara en människa
> kan svara på (då: `beslut.md` under `## Öppen kö`, som `- [ ] BQ-NNN`, och
> gissa aldrig i frågans formulering).

---

## 1. De 63 sidorna utan `final.json`

| Bok | Sidor |
| --- | --- |
| `MUT-AVE-terminal-state-fruncon-91` | 1–14, 16–18, 20–27, 29–35 (**32 st**) |
| `DOD-AVE-den-nedbrunna-fatburen` | 1–6 |
| `DOD-AVE-den-stulna-elefanten` | 1, 2, 5, 7, 9 |
| `MUT-REG-hacking-eller-hur-man-blir-en-netrunner` | 1–5 |
| `MUT-VRL-sieger-bauhaus-block` | 1–5 |
| `MUT-VRL-dark-edge-bar` | 1, 2, 3 |
| `MUT-REG-youre-just-a-program` | 1, 2, 6 |
| `MUT-REG-skymningslandets-riddare` | 1, 6 |
| `DOD-VRL-staden-nohstril` | 4 |
| `DOD-REG-grundregler-1991-del3-spelarboken` | 50 (baksidan — sannolikt ingen åtgärd) |

Terminal State är den enda `digital`-boken och har 98 % geometri; de övriga är
inskannade.

## 2. De 337 kandidaterna

| Regel | Antal | Tyngst |
| --- | ---: | --- |
| `bandbredd` | 113 | nohstril 9, elefanten 8, sypox 8 |
| `raka-citattecken` | 91 | skelettbyn 15, Krugal 10, elefanten 8 |
| `forskjuten-kedja` | 48 | skelettbyn 11, hårda bud 5, lovligt byte 5 |
| `bbox-felkoppling` | 44 | skelettbyn 11, Erebos 4, dödspatrullen 4 |
| `kolumnsammanslagning` | 18 | del I 14 |
| `radsammanslagning` | 7 | del I 4, del II 2 |
| `plusminus` | 6 | del I 3 |
| `tomt-radband` | 4 | Krugal 2 |
| `lasordning` | 3 | del I 3 |
| `punktledare` / `plusminus-varde` / `kolumnkollaps` | 1 var | del I, del I, del II |

Kandidaterna ligger i `arbete/<slug>/pages/page_NNN.review/heuristik.json` under
`regler`. Utöver dem finns `bandbredd_obundna` (973 poster) — band som är för
breda och som INGET element bär. De är inte fel i sig utan varningar om att
nästa bindning kan fastna i dem; behandla dem som kontext, inte som en kö.

**De 363 raka citattecknen** hör hemma här som korrektionsposter, aldrig som en
`sed` över exporterna. Bevisläget är starkt men domen är advokatens mot PNG:n:
del I–III har noll raka och 105 typografiska, medan Krugal har 50 raka OCH 100
typografiska i samma bok — intern drift, inte tryckvariation. Tyngst:
elefanten 60, Krugal 50, skelettbyn 36, Tanegashima 28, dödspatrullen 24.

### Tabellerna — läs det här innan du planerar dem

Nitton böcker har noll `table`-element, och planen kallade det den oroande
posten. Screeningen efter mätvågen ger **noll `tabellkandidat`-träffar**, och
`scripts/tabellkandidat.py` monterar följaktligen noll block i samtliga böcker.

Det betyder INTE att böckerna saknar tryckta tabeller. Regeln letar en följd av
KORTA element i x-kluster, alltså en cell per element — den formen som del I:s
feltypade tabeller hade. De här böckernas transkript är styckeformade, så en
tryckt tabellrad ligger som ETT långt `paragraph`, och regeln har ingenting att
se. Tabellräddningen är därför ett advokatjobb mot sidbilden, inte ett
mekaniskt, och den mekaniska halvan finns inte att köra först.

Kontraktet är bindande (CLAUDE.md §Tabeller): typas en tabell som löptext är
rad- och kolumnstrukturen förlorad för gott. Prioritera de böcker som enligt
plandokumentets §3 har tryckta tabeller men noll `table`-element.

## 3. De 1016 öppna flaggorna

| Bok | Flaggor | | Bok | Flaggor |
| --- | ---: | --- | --- | ---: |
| `MUT-AVE-attentat-sypox` | 204 | | `MUT-AVE-dodspatrullen` | 42 |
| `DOD-AVE-spindelkonungens…` | 125 | | `MUT-AVE-harda-bud` | 33 |
| `DOD-AVE-krugal-svylses-forbannelse` | 122 | | `MUT-REG-skymningslandets-riddare` | 28 |
| `DOD-AVE-edsbrytarna-i-erebos` | 112 | | `DOD-AVE-gripeborgs-hemlighet` | 25 |
| `MUT-REG-robotar` | 61 | | `DOD-VRL-staden-nohstril` | 24 |
| `DOD-AVE-daligt-vatten` | 49 | | *(19 böcker till med 1–20)* | |
| `MUT-VRL-mervyn-peak-street` | 45 | | | |

Varje avgjord flagga stängs med
`pipeline.corrections.close_review_reason(el, reason, resolution, closed_by)`
till `resolved_reasons`. **Radera aldrig beläggstexten** — den är det som gör
kontrollen spårbar. `python3 -m pipeline status --workdir <wd>` redovisar
öppna och avgjorda separat sedan 2026-08-06.

## 4. Vad som är gjort, så att du inte gör om det

- Alla 33 böcker är frysta, och `diffa` är **ren på alla 33**. Frysningen är
  facit för ordkonserveringen; frys inte om utan att först förklara skillnaden.
- Geometri: **12 334 av 16 097 element har bbox (77 %)**. `forbesikta` är körd
  med `--force` på nuvarande HEAD över samtliga 437 sidor.
- Exporterna är byggda på HEAD (noll proveniensvarningar), läskopiorna i
  `bibliotek/` är i takt, och alla 33 käll-PDF:er ligger i `arkiv/`.
- Städskripten (`materialisera_kind`, `materialisera_verdict`,
  `tomma_artefakter`, `punktrader`) är körda och idempotenta — noll poster vid
  en andra körning.
- Öppen BQ-kö: **en enda post**, BQ-021 i del III, märkt `[verktyg]` och
  blockerar ingen bok.

## 5. Tre kända svagheter du kommer att stöta på

1. **Bindningstäckningen är ojämn med flit.** Edsbrytarna 68 %, Robotar 55 %,
   mot `MUT-AVE-i-drakens-klor` 2 %, `DOD-VRL-staden-nohstril` 5 % och
   `DOD-AVE-kopparringen` 8 %. `binda_rader` vägrar hellre än gissar, och de
   låga siffrorna är sidor där mätningen och trycket är oense om spaltantalet
   — mätningen har då slagit ihop två spalter, och en bindning skulle lägga två
   tryckta spalters element i ett gemensamt band. Rör inte den spärren.
2. **`rows.py` hittar rätt spaltantal på 71 % av sidorna** (mot 21 % före
   2026-08-06). De återstående 29 % är den direkta orsaken till punkt 1. Vill
   du höja täckningen är det HÄR arbetet ligger, inte i `binda_rader`.
3. **BQ-021 (a) är olöst.** En avsnittsgräns kan fortfarande kapa en tryckt rad:
   `_segments` räknar gränser ur den sidbreda bandlistan, så en gräns kan hamna
   inuti en rad i den spalt som inte styr gränsen. Mätt på del III s. 32 — den
   tappade halvan bär bläckandel 0,3098 mot grannradernas 0,4166 och 0,4499.
   Spalterna mäts per avsnitt; avsnitten mäts inte per spalt.

## 6. Räkna om underlaget

```bash
python3 -m unittest discover -s tests -t .          # 537 tester
python3 -m pipeline status --workdir arbete/<slug>  # flaggor, BQ, proveniens
python3 scripts/matvag.py --bok <slug> --verkstall  # hela geometrikedjan
python3 scripts/binda_rader.py arbete/<slug> --utvardera-stycken
python3 scripts/uppdatera_bibliotek.py              # torrkörning
```

Kandidater, flaggor och geometri per bok räknas ur sidfilerna — `regler` i
`page_NNN.review/heuristik.json`, `review_reasons` mot `resolved_reasons`, och
`source.bbox` mot elementantal.
