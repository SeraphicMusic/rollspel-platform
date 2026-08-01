# Uppdrag: efterarbete bok 2 (Spelledarboken)

Produktionskörningen är klar — 66 sidor transkriberade, korrekturlästa och
exporterade. Det här är vad som medvetet lämnades kvar. Ingenting nedan rör
sidornas text; allt är pipeline-, adapter- och beslutsarbete.

## Läge

- `arbete/DOD-REG-grundregler-1991-del2-spelledarboken/` — 66 `page_NNN.final.json`,
  4 217 element, 246 korrektionsposter (206 applicerade), 72 `needs_review`,
  3 735 element med uppmätt bbox.
- Export klar (`bok.md`, 49 tabell-CSV, granskningsrapport), läskopia i
  `bibliotek/DOD-REG-grundregler-1991-del2-spelledarboken.md`.
- `beslut.md` (263 rader) har allt öppet grupperat i **A–G** under rubriken
  *Sammanställt efter produktionskörningen*. Varje sidas egna förslag ligger kvar
  i `pages/page_NNN.review/beslut-forslag.md` (62 filer).
- Testsviten: 217 tester, gröna. Fem pipelinefixar är **ocommittade** tillsammans
  med två nya arbetsordrar i `docs/`.

## Bindande läsning innan du rör något

[CLAUDE.md](../CLAUDE.md), [AGENTER.md](../AGENTER.md) (särskilt **Regel 5**,
skript före LLM, och **Regel 8a**), `.claude/skills/extrahera/SKILL.md`
(§Tabeller, §source.bbox) och bokens `beslut.md` A–G.

Det mesta här är deterministiskt skriptarbete. Starta inga agenter för sådant
som ett Python-skript avgör exakt.

---

## 1. Adaptern `system/dod` (beslut F) — börja här, inga följdeffekter

Fyra luckor som produktionen blottade. Var och en är en datafil, och var och en
ska ha ett test.

1. `sb_table` saknar rad över STY+STO 180. DRAKE (s. 31) har 200 och trycket
   säger `+6T6`, vilket följer tabellens egen steglängd. Utöka tabellen enligt
   den — emendera aldrig varelsens värde.
2. `derived_labels.SV` säger `Skyddsvärde`. Bokens egen förkortningsnyckel
   (s. 62) säger **`Skolvärde`**, och nyckelsidan är auktoritativ. Rätta
   adaptern; kontrollera samtidigt om del I:s extraktion har ärvt fel etikett.
3. `dice.json:notation` accepterar bara bindestreck-minus. Trycket sätter
   tankstreck: `3T6–2` (s. 34) faller utanför. Acceptera båda.
4. `Förflyttning` går **inte** att härleda konsekvent ur del I:s tabell för
   varelsestatblock (s. 36) — lägg alltså inte in kontrollen i `derived_checks`,
   och skriv ned varför, så frågan inte utreds om.

Kör `validera` på boken efteråt och kontrollera att inget nytt falskt larm
uppstår. Se minnesposten om valideraren som felmatchar vanliga ord mot
systemtermer via ä↔a.

## 2. `pipeline/rows.py` — sex mätdefekter (beslut D)

Det här är det tunga. Defekterna står uppräknade i beslut.md D 1–6 med
sidhänvisningar; s. 55:s `beslut-forslag.md` har kandidatlistan för defekt 2.

**Varför de inte lagades under körningen:** transkripten pekar på radboxarna via
`source.rader` (radindex), och en omkörning av `radboxar --force` förskjuter
varje index. Det är också därför regeln *"kör `radboxar --force` om du ändrar
`pipeline/rows.py`"* står som den gör — den får inte kringgås.

Arbetsgång:

1. **Frys nuläget.** Kopiera alla `page_NNN.radboxar.json` till en
   scratchpad-katalog, och dumpa varje elements nuvarande `source.bbox` +
   `source.rader` till en jämförelsefil. Radera aldrig något under `arbete/`.
2. **Laga defekterna** i `rows.py` med test per defekt. `EDGE_BAND` (defekt 1)
   är roten till både 1 och 2 — laga den först och mät om hur många av de sju
   sidorna i defekt 2 som blir kvar.
3. **Kör `radboxar --force`** för hela boken.
4. **Remappa `source.rader` geometriskt**, inte numeriskt: matcha varje gammal
   radbox mot närmaste nya box och skriv om indexen. Där matchningen är
   tvetydig — flagga och lös för hand mot PNG:n; gissa aldrig.
5. **Bokför om boxarna** och diffa mot jämförelsefilen från steg 1. Varje
   ändrad bbox ska kunna hänföras till en av de sex defekterna. En bbox som
   ändras utan förklaring är en regression.
6. **Exportera om och diffa `bok.md`.** Textinnehållet ska inte ändras; kan en
   skillnad inte förklaras av läsordning som blivit rätt, är den ett fel.
7. Kör `forbesikta` igen — fyra av åtta regler bygger på bbox, så
   träffbilden ska bli bättre, inte bara annorlunda.

Slutkontroll: hela sviten grön, och `rapport` ska visa fler element med bbox än
dagens 3 735 av 4 217.

## 3. Beslut A, C, E, G — användarens avgöranden

Dessa är **inte** dina att avgöra. Läs A–G i beslut.md, formulera varje klass som
en fråga med din rekommendation och underlaget bakom, och fråga användaren. Först
därefter verkställs de.

- **A** — sex klasser som behölls print-troget med `applied: false`. Utvidgas
  Regel 8a:s vänsterkolumn, verkställs posterna mekaniskt (de ligger redan
  färdiga); annars står de kvar som fynd. Renaste testfallet är dittografin
  `som som` på s. 37.
- **C** — rubriknivåer. Rekommendationen från s. 16, mätt i bokens egen
  innehållsförteckning, är kapitel 1 / sektion 2 / underrubrik 3 för hela boken.
  Beslutet gäller hela serien och bör harmoniseras mot del I.
- **E** — fyra typningsfrågor (punktlistor `list` mot `paragraph` med tryckets
  `•`, blankettsidan s. 64, exempelrutans titelrad, tabell bruten av spaltfall).
  Ingen information går förlorad; formen bör bara vara en.
- **G** — Mutant-terminologin i s. 11 (kapitlet är återanvänt från Äventyrsspels
  Mutant-spelledarbok), grawlixen U+F8FF på s. 13 som blir tofu utanför Apple,
  och flödesschemat på s. 32 som ingen elementtyp i kontraktet kan bära.

**B rör du inte.** De sju tryckta räknefelen är fynd, inte fel att rätta. Notera
bara advokatens iakttagelse att KP-avvikelserna i varelsekapitlet konsekvent går
åt samma håll och kan vara systematiska.

Verkställs något av A/C/E blir det en korrektionspost per ändring med tryckets
form i `original` — aldrig en tyst redigering — och därefter `sammanfoga`,
`rapport`, `exportera --format alla` och ny läskopia till `bibliotek/`.

## 4. Committa

Fem pipelinefixar ligger ocommittade och är alla testtäckta:

- `jobs.py` — kontraktets elementtyper avvisades av `bokfor`; ny
  `source.rader`-brygga som räknar unionsbox deterministiskt.
- `preflight.py` — läsordningsregeln dömde på regionetikett i stället för
  geometri, och längdfiltret tystade felplacerade rubriker.
- `export.py` — snedstrecksläkning vid radbrytning, nästlade `extraStats`, och
  fältrader som limmades ihop.
- Plus `docs/TRANSKRIPTIONSUPPDRAG-BOK2.md` och `docs/KORREKTURUPPDRAG-BOK2.md`.

Dela gärna i två commits: pipelinefixarna för sig, arbetsordrarna för sig.
`arbete/` är gitignorerad — bokens state följer inte med.

## 5. Om du kör agenter

Max tre parallella, ingen nästling, Sonnet för transkription och Opus för
advokaten (AGENTER.md). **Ge varje agent en egen underkatalog i scratchpad** —
under bok 2:s körning skrev parallella advokater över varandras beskärningar,
och en fick registersidans text serverad som sin egen.
