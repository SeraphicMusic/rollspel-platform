# Överlämning: ikappkörningens Etapp 5

*Skriven 2026-08-07 efter andra agentvågen. Allt nedan är MÄTT mot
`1cb7019` och går att räkna fram igen med kommandona i §7. Där en siffra
skiljer sig från Etapp 4-dokumentets står skälet utskrivet — det är
skillnaderna som är instruktiva.*

Klistra in avsnittet »Prompt« i en ny session. Resten är underlaget.

---

## Prompt

> Kör vidare på Etapp 4/5 i `docs/IKAPP-ALLA-BOCKER.md`. Underlaget står i
> `docs/IKAPP-ETAPP5-PROMPT.md` — läs den FÖRST, och läs `AGENTER.md` SLAVISKT
> innan du startar en enda agent. Siffrorna är mätta 2026-08-07 mot `1cb7019`
> och går att räkna fram igen med kommandona i §7; verifiera dem innan du
> planerar.
>
> **Börja med omexporten av korpusen (§2) — före all agentkorrektur.** 32 av 33
> böckers export står på `f0b8c14`, fyra commits bakom HEAD, och fyra av de
> commitsen rörde `pipeline/export.py`. Den viktigaste lagade radslutets
> bindestreck: den gamla koden läkte tryckta sammansättningsstreck till
> ord som inte finns (`40års`, `Pythonrevolvern` stod live i läskopian). 994
> radslutande bindestreck i 16 böcker avgörs annorlunda i dag, 975 av dem i
> fyra böcker. Kör bok för bok: `frys` → `exportera` → `diffa` →
> `python3 scripts/oforklarade_ord.py arbete/<slug>`. Grinden kommer att fälla
> — varje ordändring ska dömas mot PNG:n och bäras av en post, precis som på
> `MUT-AVE-terminal-state`, där samma klass avgjordes med boken själv som
> facit (§2.1). Städa `python3 scripts/uppdatera_bibliotek.py --verkstall`
> efteråt.
>
> Sedan ström 1:s sista 16 sidor, i den ordningen:
> `DOD-AVE-den-nedbrunna-fatburen` (s. 1–6), `DOD-AVE-den-stulna-elefanten`
> (s. 1, 2, 5, 7, 9), `MUT-REG-hacking-…-netrunner` (s. 1–5). Alla tre är
> INSKANNADE, inte digitala — terminal-states mekaniseringar
> (`textlager_facit.py`, `method: embedded`-undantagen) gäller inte, och de
> bbox-baserade reglerna är levande igen. Då är ström 1 tom och varje bok i
> korpusen har alla sidor korrekturlästa.
>
> Sedan ström 2 (163 sidor med åtgärdbar regel på oavslutade böcker, §4) och
> ström 3 (1029 öppna flaggor, §5 — fyra böcker bär 563 och ingen av dem har en
> enda avgjord flagga, men läs flaggtexten innan du utreder om: flera bär
> utredningen i prosa från tiden före `resolved_reasons`).
>
> **Läs §6 innan du skriver en enda agentprompt.** Där står de instruktioner som
> gav båda vågornas fynd. Den viktigaste kostar en mening: säg åt specialisten
> att fastställa vad som STÅR i trycket, inte att bedöma om draftens svenska är
> korrekt — de tysta normaliseringarna, där draften gjort trycket MER korrekt än
> det är, är den klass ingen jämförelse mot draften kan se. Näst viktigast: låt
> någon RÄKNA illustrationerna mot sidbilden. Terminal-state saknade sju bilder
> helt, och ingen regel och ingen orddiff ser den klassen.
>
> Bindande ramar: max 3 agenter samtidigt TOTALT, aldrig per sida (Regel 2).
> Ingen nästling (Regel 3). En sida per agentuppsättning, fas 1 → fas 2 i
> strikt ordning (Regel 4). Specialister på Sonnet, advokaten på Opus, modellen
> i agentens frontmatter och ALDRIG i anropet (Regel 1). Bildforensik körs
> synkront, en agent per meddelande. Skript före LLM (Regel 5) — agenterna
> verifierar kandidatlistan, de letar inte upp mönstren igen.
>
> Efter varje bok: `sammanfoga`, `exportera`, `rapport`, `diffa`, och sedan
> **`python3 scripts/oforklarade_ord.py arbete/<slug>`**. **Exitkod 0 krävs
> innan boken lämnas.** Därefter `python3 scripts/uppdatera_bibliotek.py
> --verkstall`, och `arkivera` när kön är tom.
>
> Rapportera per bok. Stanna bara om ordkonserveringen brister på ett sätt du
> inte kan döma, eller om du stöter på en fråga som BARA en människa kan svara
> på — går den att avgöra med en beskärning ur skanningen är den ett mätjobb,
> inte ett köärende. Måste den köas: `beslut.md` under `## Öppen kö`, som
> `- [ ] BQ-NNN`, märkt `[beslut]` eller `[verktyg]`, och gissa aldrig i
> frågans formulering.

---

## 1. Vad andra vågen gjorde

`MUT-AVE-terminal-state-fruncon-91` är klar: alla 36 sidor korrekturlästa,
ordgrinden på exitkod 0, exporten på HEAD, läskopian bytt, boken arkiverad.
10 öppna flaggor kvar, och alla tio är **fynd i trycket** — räkneavvikelser i
statblock som Regel 8a förbjuder att rätta. 556 avgjorda.

Boken gick från **725 `paragraph` av 792 element, noll `table`, noll
`statblock`** till 19 statblock, 59 tabeller, 65 rubriker, 32 illustrationer.
Sju bilder saknades helt i draften.

**Nio verktygsfel** hittades och lagades, alla med test (587 gröna):

| Fel | Följd |
| --- | --- |
| `source.bbox` bar två storheter under ett namn — textlagret skrev PyMuPDF:s råa punkter i ett fält resten av repot läser normaliserat | 258 av bokens 274 screeningkandidater var enhetsfel |
| `tabellkandidat` kan strukturellt inte se en tabell i en digital utgåva | ny regel `tabellrad-i-element` hittade 44 osynliga: 19 vapentabeller + 19 statblock |
| `validera`s `derived_checks` hoppade tyst över varje värde med enhet | `Förflyttning = FYS + SMI` fyrade aldrig i hela boken |
| `repair_dice_token` kunde hitta på hela notationen | `SIG` → `5T6` låg applicerad i tryckets »DET HÄR ÄR INTE ETT SPEL I SIG« |
| `export._stitch` fogade ihop tabeller på enbart lika rubriker | 19 vapentabeller med identiska rubriker räddades av en tillfällighet |
| `export._join_text` läkte tryckta sammansättningsstreck som avstavningar | `40års`, `Pythonrevolvern`, `killerkängor` stod live i läskopian — **se §2** |
| `extract_text` skrev bbox för roterad text | 34 punkter utanför sidan |
| `_statblock_md` skrev NPC-namnet två gånger och emenderade skiljetecken | dubblering i `bok.md` |
| `rendera --alla` nedgraderade `validated` → `rendered` | 29 färdiga sidor, arkiveringen tyst blockerad |

Tre mätningar mekaniserades i `scripts/textlager_facit.py`: fullständighet,
versaltypsnittens kodning (`Dave GahMan` = `DAVE GAHMAN`), och tecken som ritas
med mellanslagsglyfen.

Två gånger vände en advokat på min egen hypotes med mätning. Det är metoden som
fungerar, inte artigheten: hypotesen ska formuleras så att den går att kullkasta.

## 2. FÖRSTA JOBBET: omexporten (32 böcker)

```
revisioner: {'f0b8c14': 32, '1cb7019': 1}
```

Fyra commits efter `f0b8c14` rörde `pipeline/export.py`. Den tyngsta är
`415001f Låt boken själv avgöra radslutets bindestreck`.

Radslutande bindestreck som ligger i böckernas element, per bok:

```
   342 40-drakar-och-demoner-…-riotminds
   253 DOD-REG-grundregler-1991-del2-spelledarboken
   224 DOD-REG-grundregler-1991-del3-spelarboken
   156 DOD-AVE-edsbrytarna-i-erebos
     5 MUT-AVE-terminal-state (redan avgjorda)
   … 11 böcker med 1–2 vardera
   994 totalt i 16 böcker
```

Det är inte 994 fel — det är 994 tillfällen där gammal och ny kod svarar olika,
och där bara trycket kan avgöra vilket som är rätt. De fyra tunga böckerna är
regelverken, alltså precis de böcker vars läskopior matas till andra verktyg.

### 2.1 Hur frågan avgörs, för den är mätt en gång redan

Den gamla koden antog att ett radslutande bindestreck alltid var en avstavning
och läkte ihop orden. Den nya frågar **boken själv**: står samma ord med
bindestreck mitt på en rad någon annanstans i boken är strecket tryckets och ska
stå kvar. Det är `export.mid_line_words()`.

På terminal-state mätte advokaten bokens hela inventarium av radslutande
bindestreck — fem stycken, allihop tryckta sammansättningsstreck, bevisat med
mid-line-förekomster av samma ord — och kullkastade min hypotes att de var
brytartefakter. **Gör om den mätningen per bok.** I en 342-strecks bok är de
flesta äkta avstavningar; poängen är att skilja dem, inte att anta åt något håll.

Arbetsgång per bok:

```
python3 -m pipeline frys      --workdir arbete/<slug>
python3 -m pipeline exportera --workdir arbete/<slug>
python3 -m pipeline diffa     --workdir arbete/<slug>
python3 scripts/oforklarade_ord.py arbete/<slug>     # exitkod 0 krävs
python3 scripts/uppdatera_bibliotek.py --verkstall
```

`diffa` svarar bara på OM orden ändrats. Grinden är noll *oförklarade*, och en
lagning som ändrar ord måste bäras av en post som säger varför.

## 3. Ström 1: 16 sidor kvar utan `final.json`

| Bok | Sidor | Utgåva |
| --- | --- | --- |
| `DOD-AVE-den-nedbrunna-fatburen` | 1–6 | inskannad |
| `DOD-AVE-den-stulna-elefanten` | 1, 2, 5, 7, 9 | inskannad |
| `MUT-REG-hacking-…-netrunner` | 1–5 | inskannad |

Två sidor till saknar `final.json` och är INGA ärenden: `del3-spelarboken`
s. 50 och `staden-nohstril` s. 4 har noll element — tomma sidor.

Alla tre böckerna är inskannade. Terminal-state var korpusens enda `digital`
och dess billiga mekaniseringar följer inte med: geometrin kommer från
`radboxar`, `method: embedded`-undantagen i `preflight` gäller inte, och de
bbox-baserade reglerna är levande igen.

## 4. Ström 2: screeningkandidaterna

189 sidor bär minst en åtgärdbar regel. 26 av dem ligger i terminal-state och är
avklarade — `heuristik.json` städas inte när en sida avgörs, den är en
mätning av draften. **163 sidor återstår i praktiken.**

```
  168 raka-citattecken        44 tabellrad-i-element      6 lasordning
  121 bbox-felkoppling        33 kolumnsammanslagning     5 tomt-radband
   10 tabellkandidat           9 radsammanslagning        1 var: kolumnkollaps,
    9 plusminus                                              linjeregel-suffix,
                                                             punktledare,
                                                             plusminus-varde
```

Tyngdpunkten, sidor med åtgärdbar regel:

```
   21 DOD-REG-grundregler-1991-del2-spelledarboken
   21 DOD-AVE-spindelkonungens-pyramid-…
   21 40-drakar-och-demoner-…-riotminds
   12 DOD-AVE-krugal-svylses-forbannelse
    9 MUT-AVE-dodspatrullen
    8 DOD-AVE-den-stulna-elefanten
```

`tabellkandidat` (10) och `punktledare` (1) är den oåterkalleliga klassen —
en tryckt tabell som ligger som löptext går inte att återskapa nedströms. Ta
dem först i varje bok.

De 44 `tabellrad-i-element` är alla terminal-states och alla avgjorda; regeln
träffar bara digitala utgåvor, och korpusen har ingen annan.

`bandbredd` (1119) och `forskjuten-kedja` (222) är räknade som ICKE åtgärdbara
här: de är geometrikvalitetssignaler, inte innehållsfel, och de dränker listan.
Se dem som en karta över var mätningen är svag.

## 5. Ström 3: 1029 öppna flaggor, 1654 avgjorda

```
  204 MUT-AVE-attentat-sypox                    (0 avgjorda)
  125 DOD-AVE-spindelkonungens-pyramid-…        (0)
  122 DOD-AVE-krugal-svylses-forbannelse        (0)
  112 DOD-AVE-edsbrytarna-i-erebos              (0)
   61 MUT-REG-robotar                           (0)
   49 DOD-AVE-daligt-vatten                     (0)
   45 MUT-VRL-mervyn-peak-street                (0)
   42 MUT-AVE-dodspatrullen                     (0)
```

De fyra översta bär 563 av de 1029. Att de har noll avgjorda betyder INTE att
ingen utrett dem — `resolved_reasons` kom till efteråt. **Läs flaggtexten
först:** flera bär utredningen i prosa i elementets korrektionsposter, och då är
jobbet att flytta domen till fältet med
`pipeline.corrections.close_review_reason()`, inte att utreda om. Radera aldrig
beläggstexten.

Terminal-states 10 kvarvarande är motsatsen: de är avgjorda som FYND. Ett
tryckt räknefel som Regel 8a förbjuder att rätta ska stå kvar som öppen flagga,
inte stängas — flaggan är rapportens sätt att bära fyndet.

## 6. Instruktionerna som gav fynden

1. **»Fastställ vad som STÅR i trycket« — inte »bedöm om svenskan är korrekt«.**
   De tysta normaliseringarna är den klass ingen jämförelse mot draften kan se,
   för draften ser rätt ut. `FRÅN` där trycket har `FRAN` avslöjades först när
   det inbäddade typsnittet extraherades och renderades.
2. **Låt någon RÄKNA illustrationerna mot sidbilden.** En bild som delar
   inramning med ett redan extraherat textelement saknas ofta helt, och ingen
   regel och ingen orddiff ser det.
3. **Skript före LLM.** Agenten verifierar `heuristik.json`, den letar inte upp
   mönstren igen. Varje mönster som kan mätas ska mätas i Python en gång i
   stället för av en agent per sida.
4. **Ge advokaten hypotesen som en hypotes.** Två gånger den här vågen mätte
   advokaten fram att jag hade fel. Det fungerar bara om prompten säger vad
   påståendet vilar på, så att det går att kullkasta.
5. **En tabell typas `table`, aldrig som en följd av `paragraph`.** Fel typ är
   ett typningsfel, aldrig en korrektionspost, och strukturen går förlorad för
   gott.
6. **Gissa aldrig i en köposts formulering.** Säg vad som är oläst, inte vad du
   tror att det står.
7. **Ett verktyg som ändrar spelvärden är ett allvarligare fel än ett OCR-fel.**
   Fyra vägar stängdes den här vågen där ett verktyg skrev värden ingen tryckt.
   Leta efter fler: allt som »reparerar« en notation kan hitta på den.

## 7. Räkna om underlaget

```bash
# Ström 1 — sidor utan final.json
for d in arbete/*/; do s=$(basename "$d");
  n=$(ls "$d"pages/page_*.final.json 2>/dev/null | wc -l);
  v=$(ls "$d"pages/page_*.validated.json 2>/dev/null | wc -l);
  [ "$n" != "$v" ] && echo "$s final=$n validated=$v"; done

# Exportens revision per bok (§2)
python3 - <<'PY'
import json,glob,collections
c=collections.Counter()
for f in glob.glob("arbete/*/export/proveniens.json"):
    c[json.load(open(f,encoding="utf-8-sig"))["bok.md"]["git_revision"][:7]]+=1
print(dict(c))
PY

# Ström 2 — sidor med åtgärdbar regel
python3 - <<'PY'
import json,glob,collections
AKT={"tabellkandidat","punktledare","kolumnkollaps","kolumnsammanslagning",
     "radsammanslagning","lasordning","tabellrad-i-element","plusminus-varde",
     "linjeregel-prefix","linjeregel-suffix","raka-citattecken",
     "bbox-felkoppling","tabell-svalt-titelband","tomt-radband","plusminus"}
s=collections.Counter(); r=collections.Counter()
for h in glob.glob("arbete/*/pages/page_*.review/heuristik.json"):
    t={k:v for k,v in (json.load(open(h,encoding="utf-8-sig")).get("regler") or {}).items()
       if v and k in AKT}
    if t:
        s[h.split("/")[1]]+=1
        for k,v in t.items(): r[k]+=v
print(sum(s.values()), s.most_common(8), dict(r.most_common()))
PY

# Ström 3 — öppna och avgjorda flaggor
python3 - <<'PY'
import json,glob,collections
o=collections.Counter(); a=collections.Counter()
for f in glob.glob("arbete/*/pages/page_*.final.json"):
    s=f.split("/")[1]
    for el in json.load(open(f,encoding="utf-8-sig")).get("elements") or []:
        o[s]+=len(el.get("review_reasons") or [])
        a[s]+=len(el.get("resolved_reasons") or [])
print(sum(o.values()), sum(a.values())); print(o.most_common(10))
PY

# Öppna BQ-poster
grep -h "^- \[ \] BQ" arbete/*/beslut.md

python3 -m unittest discover -s tests -t .      # 587 gröna 2026-08-07
```

## 8. Läget i övrigt

- HEAD `1cb7019`, arbetsträdet rent, **21 commits opushade** mot `origin/main`.
- 33 PDF:er i `arkiv/`, `import/` tomt.
- Sex öppna BQ-poster i tre böcker, alla `[verktyg]`, ingen `[beslut]` — alltså
  ingenting som väntar på användaren.
- `arbete/MUT-AVE-terminal-state-fruncon-91/beslut.md` är korpusens fylligaste
  precedenssamling (typskala per punktstorlek, versaltypsnittens kodning,
  bindestrecksserien, plåtarnas x-förskjutning). Den gäller den boken, men
  metoden — mät serien, döm sedan hela serien på en gång — är generell.
