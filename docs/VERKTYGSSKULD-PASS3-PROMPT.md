# Överlämning: verktygsskuldens pass 3 — klass C

Pass 1+2 (2026-08-17, se [VERKTYGSSKULD-PASS2.md](VERKTYGSSKULD-PASS2.md))
stängde 15 av 22 `[verktyg]`-poster. Detta pass tar **klass C**: Edsbrytarnas
styckedelare (BQ-001) och kursivspans (BQ-004), Krugal BQ-010, samt
advokatdomarna över Tanegashimas och Lovligt bytes felkopplade band.
Mätmotorns bilddetektering (klass B-resten) ingår INTE här — den är ett eget
pass med egna facit i PASS2-dokumentet.

## Prompt

> Kör verktygsskuldens pass 3 enligt docs/VERKTYGSSKULD-PASS3-PROMPT.md —
> läs den FÖRST, och AGENTER.md SLAVISKT innan någon agent startas. Ta
> posterna i ordningen §1 → §2 → §3 → §4. Skript före LLM; varje verktyg
> prövas med `--utvardera`-mönstret mot bokens egna facitsidor innan det
> får skriva något (Regel 9a: döm avvikelser mot trycket, räkna dem inte).
> Före varje strukturingrepp: `frys` är redan tagen — kontrollera med
> `diffa` att bok.md är ren FÖRE ingreppet; efteråt: sammanfoga →
> exportera → rapport → diffa → `python3 scripts/oforklarade_ord.py
> <arbete/slug>` (exitkod 0 krävs) → `python3
> scripts/uppdatera_bibliotek.py --verkstall`. Advokater körs SYNKRONT en
> i taget. Efter varje verktygsändring: hela testsviten (637 gröna vid
> överlämningen). Committa per avslutad post; pusha inte utan besked.
> Stanna bara för en fråga som BARA en människa kan svara på — mät först.

## §1 Edsbrytarna BQ-001 — deterministisk styckedelare

`arbete/DOD-AVE-edsbrytarna-i-erebos/beslut.md` BQ-001. Nio av tio sidor
har **ett element per spaltavsnitt** (s. 2 `e01` = 4 tryckta stycken i ett
element om 53 rader; likaså s. 3 `e05`, s. 4 `e01`, s. 7 `e03`/`e05`),
medan s. 1 och s. 6 är delade per tryckt stycke — `bok.md` flödar ihop
tryckets stycken. Verktyget härleder brytpunkterna ur radboxarnas UPPMÄTTA
indrag och omfördelar `source.rader` + `bbox`; texten berörs inte.

- **Mätunderlag** (står i `page_006.final.json`, `p006_e04`-posten och
  `resolved_reasons` på `e04`/`e05`/`e12`): indragna radstarter x≈65 pt i
  spalt 1 och x≈331–334 pt i spalt 2, mot fortsättningsradernas 52–54
  respektive 320–322 pt.
- **Inbyggt facit**: s. 1 och s. 6 ÄR redan styckedelade. Verktygets
  `--utvardera` ska återskapa deras befintliga delning ur enbart
  geometrin innan det får dela någon annan sida (samma mönster som
  `binda_rader --utvardera`; ett verktyg som inte kan återskapa en känd
  delning får inte skriva en okänd).
- **Verkställighet**: elementdelning är ett strukturingrepp — nya element
  med `added_by`, originalen `removed: true` + `source.merged_into`-
  motsvarighet (se hur montagen gör), aldrig raderad text. Ordgrinden ska
  ge 0 oförklarade: delningen flyttar inga ord, och `_strukturpost` i
  `scripts/oforklarade_ord.py` krediterar inte strukturposter.
- **Återbruk**: Lovligt bytes enda öppna sidflagga (s. 3 `p003_e25`,
  styckedelning med uppmätt indragsserie i flaggtexten) löses med samma
  verktyg. OBS: elementet bär 14 band mot tryckets 13 rader — verktyget
  får inte anta 1:1 utan ska refusera med skäl om raderna inte går ihop.
  Stäng flaggan med `pipeline.corrections.close_review_reason()` när
  delningen är dömd.

## §2 Advokatdomarna — felkopplade band (Tanegashima + Lovligt byte)

`djavulens-advokat` per sida, **SYNKRONT en i taget** (bakgrundsagenter
dör på 600 s-watchdogen), modell via frontmatter (aldrig i anropet).
Mandat: DÖM de utpekade bindningarna mot PNG:n/inbäddade skanningen. En
bevisat felkopplad bindning TAS BORT (`source.rader` + `source.bbox`) —
en saknad box är en lucka i en heuristik, en påhittad är ett fel som ser
ut som data. Ombindning bara där ett läge kan BEVISAS (Regel 9b: kräv att
alternativet räknas fram och är dyrare). Texten på alla sidorna är redan
kontrollerad mot trycket — inga textändringar väntas. Domar till
beslut.md; uppdatera respektive BQ-post.

- **MUT-AVE-intriger-pa-tanegashima BQ-003 (rest)**: s. 4 — `p004_e13`
  `LEDTRÅDAR` (fet rubrik som bär fel/inget band; `bbox-felkoppling` ×4,
  `förskjuten kedja` ×3). s. 5 — `p005_e18` `DAVID ROE, 46 ÅR.` bär ett
  0,264 brett textband i stället för sitt rubrikband (`bbox-felkoppling`
  ×2, `förskjuten kedja` ×4, `bandbredd` ×12).
- **MUT-AVE-lovligt-byte BQ-001 (rest)**: s. 5 — `p005_e06`/`e08`/`e10`/
  `e12` (bredd per tecken 0,00055–0,00328 mot sidmedianen 0,00112) och
  `p005_e18` (band 107, bredd 0,3265 mot bläckets 0,0927). s. 6 —
  `p006_e30` (»Harley kommer genast…«, fysiskt längst NED i högerspalten
  men bunden till banden 30–33 → bbox y-frac 0,856 = sidans ÖVRE
  fjärdedel) och `p006_e24` (banden 26–29, 45, 75–99). s. 8 — bara
  sidhuvudet bundet; band 17 bredd 0,2091 mot bläckets 0,0354.
- Efter domarna: bokavslutsflödet per bok. Borttagna bindningar ändrar
  bok.md:s STYCKEFORM (utan geometri fogar exporten inte ihop rader) —
  orden ska vara oförändrade; grinden dömer.
- OBS: mätfilerna får INTE mätas om häri — `_heal_split_rows` (ny sedan
  pass 2) ändrar bandindex vid `--force`, och böckernas bindningar pekar
  på dagens index. Mätmotorärendena (banden som SAKNAS) tillhör klass B.

## §3 Edsbrytarna BQ-004 — kursivspans

Elementschemat kan inte bära kursivväxling INUTI ett stycke; brev,
repliker, exempelstycken och fartygsnamn tappar stilen i bok.md (belagt
s. 6 `p006_e04`/`e07`/`e08`/`e12`, s. 7, s. 8; kartlegendens post 5
`p010_e08`; kapitälstilen — se domen »Kapitäler återges som VERSALER« i
beslut.md). Åtgärden är deterministisk, ingen ny tryckläsning:

- PDF:ens textlager bär fontnamn per span (`Times-Italic` mot
  `Times-Roman`, kontrollerat s. 6 2026-08-10). Härled spans ur den
  ARKIVERADE PDF:en och lagra dem i en ny schemadel (t.ex.
  `data.style_spans` med teckenintervall), matchade mot elementtexten.
- `heading`-grenen i `pipeline/export.py` läser i dag ALDRIG
  `el["style"]` — laga den samtidigt (bokens feta KURSIVA
  sektionsrubriker).
- Markdownrendering: `*…*` för kursiva spans. Det ändrar TOKENFORMER i
  bok.md (`*ordet*` mot `ordet`) — kärnorna är oförändrade, men pröva
  grinden på EN sida först och utöka `oforklarade_ord` bara om något
  strandar (asteriskerna strippas redan av `_SKILJE`/tokeniseraren).
- Schemaändring = SCHEMA_VERSION-fråga i `pipeline/` — kontrollera hur
  `byggd_med`-stämpeln och `validera` reagerar på den nya nyckeln.

## §4 Krugal BQ-010 — prosafältdriften + GC-kolumnen

`arbete/DOD-AVE-krugal-svylses-forbannelse/beslut.md` BQ-010 (utbruten ur
BQ-007 i pass 2).

- **(b) Prosafältdriften**: 11 rutor bär `Yrke`/`Utseende`/`Karaktär` i
  `data.other` medan s. 9–10:s NPC:er har dem som egna `paragraph`
  (`p009_e09`+`e11`, `p009_e18`+`p010_e02`). Enhetning till den
  print-bärande formen (etiketten som nyckel i `other`) i ETT svep:
  tryckläs per ruta, konsumera paragraferna (`removed: true` +
  `merged_into`), inga ord ändras (etiketterna står ordagrant i
  styckstexten). Grinden dömer.
- **(c-resten) GC-kolumnen**: tryckets vapenhuvud s. 16 är `Naturliga
  vapen  GC  Skada`, men ingen fältform bär `GC`. Bygg ut
  weapons-modellen (`gc`-kolumn i `_WEAPON_COLUMNS` i export.py +
  datalagring) och rekonstruera raden trycktroget (dagens lagring:
  `p016_e02.other["Naturliga vapen"] = "INT antal tentakler* 16 (skada
  Spec)."`). Orden `GC`/`Skada` är NYA i bok.md — de måste bäras av
  applicerade poster (mönstret från BQ-007-svepet: post med
  original/corrected som bär orddeltat).

## Bindande ramar (sammanfattning — AGENTER.md gäller i sin helhet)

- Max 3 parallella agenter totalt; advokater synkront en i taget; ingen
  nästling; en sida per agentuppdrag; modell i frontmatter.
- PNG:n/inbäddade skanningen är sanningskällan; inga tysta korrigeringar;
  siffror/spelvärden/dialekt rättas aldrig (Regel 8a); vid tvekan
  högerkolumnen.
- Bara advokaten skriver i beslut.md under korrektur; verkställda
  BQ-poster bockas `[x]` med verkställighetsnot, aldrig raderade.
- `bygg_adapter.py --ref` skriver över handkurerade fält — spegla för
  hand i `system/` och lägg frödata i seedarna.
- Böckerna är arkiverade: käll-PDF:erna ligger i `arkiv/`, verktygsfacit
  byggs i KASTBAR katalog (`analysera` + `radboxar --workdir <scratch>`),
  aldrig i bokens `arbete/`.
