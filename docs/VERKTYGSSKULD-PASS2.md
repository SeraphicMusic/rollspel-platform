# Verktygsskulden efter passet 2026-08-17

Läget: ström 2-screeningen är AVSLUTAD (0 substantiva fel — domar i del 1:s,
del 2:s och Terminal States beslut.md), Hacking-flaggan stängd, Edsbrytarna
BQ-003 verkställd, och 11 av 22 `[verktyg]`-poster åtgärdade och committade
(`0c31820` adapterluckorna + valideringskontrollerna, `2ac85f7`
forbesikta-reglerna). Sviten 627 gröna. Kvar: 11 poster i tre klasser,
var och en ett EGET arbetspass (Etapp 7 §7). Ingen blockerar en bok.

## Prompt för nästa pass

> Kör vidare på verktygsskulden enligt docs/VERKTYGSSKULD-PASS2.md — läs den
> FÖRST, och AGENTER.md SLAVISKT innan någon agent startas. Ta klasserna i
> ordningen A → B → C. Efter varje verktygsändring: hela testsviten; efter
> varje bokdataändring: sammanfoga → exportera → rapport → diffa →
> oforklarade_ord (exitkod 0) → uppdatera_bibliotek.

## Klass A — exportkirurgi (störst nytta per timme)

- **Krugal BQ-005: statblock brutna över sidgräns.** FEM uppmätta fall med
  pixelverifierade belägg står i posten (s. 7→8, s. 8→9, s. 11→12, s. 15→16,
  s. 16→17), i BÅDA riktningarna, och fortsättningen är ibland LÖSA
  `paragraph` med fältetiketter (s. 17). Föreskrift: sidfilerna ändras ALDRIG;
  fogningen görs i `sammanfoga`/`export`, redovisas som not, och
  `scripts/oforklarade_ord.py` måste lära sig kreditera noten (fogningen tar
  bort det duplicerade namnets ord ur bok.md). Sök därefter samma signatur i
  hela korpusen (statblock med tomma `stats` sist på sida / fältetiketter
  först på nästa).
- **Krugal BQ-007: statblockets fältstruktur driver.** (a) 7 rutor bär
  `Stridsfärdigheter` hopslagna i `skills` — ordet finns inte i exporten;
  flytten kräver PNG-läsning per ruta (vilka färdigheter som står under
  rubriken) och applicerade poster som bär ordet genom grinden. (b) prosafält
  ibland i statblocket, ibland som eget `paragraph`.
- **Krugal BQ-006: rubriknivåharmonisering.** Boken saknar TOC —
  `rubriknivaer.py` går inte; nivån måste härledas ur rubrikernas MÄTTA grad
  (versalhöjd i den inbäddade skanningen), som Dödspatrullens avgjorda BQ-001
  (mätmetoden står där: bläckband i radprojektion). Hela boken i ett svep,
  `level_source` per rubrik.

## Klass B — mätmotorn (`pipeline/rows.py`), samordnas som ETT projekt

Alla fyra är samma organ: blockindelning/kolumndetektering.

- **del3 BQ-021** (+298 rader analys i posten, samordna med BQ-013): mät
  radband SPALT FÖR SPALT i spaltfönster i stället för sidgemensamma block.
  Två gratissignaler beskrivs som kan byggas UTAN omskrivningen. OBS: del3
  mäts ALDRIG om (103 handmätta boxar) — facit byggs i kastbar katalog ur
  arkiv-PDF:en.
- **Skymningslandet BQ-001**: marginalgrafik sväljs av textkolumnen
  (facitmått i posten: sats x 0,347–0,697, balk från 0,718).
- **Tempokalkylatorn BQ-001**: helsidesillustrationens tonband mäts som
  textrader på s. 1 (`sammanfattning.grafik` är 0 fast bilden fyller
  x 0,054–0,338).
- **Spindelkonungen BQ-007**: andra svepets tröskel mot luckans egen profil
  (facit: `säga).` på s. 11, profiltopp 0,031).

Trespalts-luckorna i Lovligt byte/Tanegashima/YJAP är samma klass — deras
poster pekar redan hit. Efter varje rows.py-ändring: `binda_rader
--utvardera` mot berörda böcker (verktyget måste återskapa kända bindningar)
och `forbesikta --force`-omscreening (fyra regler bygger på bbox).

## Klass C — advokatärenden + schema

- **Lovligt byte BQ-001 (rest)**: de FELKOPPLADE banden på s. 5/6/8 (t.ex.
  p006_e30, fysiskt längst ned, bbox i övre fjärdedelen) ska dömas mot PNG:n
  innan någon bindning tas bort — en advokat per sida, synkront.
- **Tanegashima BQ-003 (rest)**: felkopplingen på s. 4/5 (p004_e13 LEDTRÅDAR,
  p005_e18 DAVID ROE) — samma form.
- **Edsbrytarna BQ-001**: deterministisk styckedelare ur radboxarnas uppmätta
  indrag (mätunderlag i posten: radstarter x≈65/331–334 pt mot
  fortsättningsrader 52–54/320–322 pt). Geometriarbete, aldrig per hand.
- **Edsbrytarna BQ-004**: kursivväxling INUTI element — schemautbyggnad
  (style-spans ur PDF:ens textlager, `Times-Italic` per span är redan
  kontrollerat) + `heading`-grenen i export.py som i dag aldrig läser
  `el["style"]`.

## Öppna granskningsflaggor (avsiktliga, inga att åtgärda nu)

- del3 s. 6 + s. 9 — väntar uttryckligen på radtröskelbeslutet (klass B);
  boken mäts aldrig om.
- Lovligt byte s. 3 (p003_e25) — styckedelning, väntar på strukturpasset
  (klass C/Edsbrytarna BQ-001-verktyget kan återanvändas).

## Att INTE göra om

- Ström 2/heuristikkandidaterna är dömda — domar står i respektive beslut.md
  (2026-08-17-sektionerna). Heuristik.json-snapshoten är statisk; öppna
  flaggor räknas i final.json, inte där.
- `bygg_adapter.py --ref` REGENERERAR sb_table och tappar handkurerade fält
  (181–220-raden, `derived_checks_excluded`) — spegla ändringar för hand i
  `system/` i stället, och lägg frödata i seedarna.
