# Verktygsskulden efter passen 2026-08-17 (två pass samma dag)

**Pass 1** stängde ström 2 (0 substantiva fel, domar i del 1:s/del 2:s/
Terminal States beslut.md), Hacking-flaggan, Edsbrytarna BQ-003 och 11 av 22
`[verktyg]`-poster (commits `0c31820`, `2ac85f7`). **Pass 2** stängde
klass A helt och halva klass B:

- **Krugal BQ-005** — sidgränsbrutna statblock fogas i läsexporten
  (`_stitch_fortsattningar`), redovisas i `export/fogningar.json`, och
  ordgrinden krediterar fogningen. Korpussvepet lagade även I drakens klor
  och Mervyn Peak Street.
- **Krugal BQ-007(a)+(c-etikett)** — Stridsfärdigheterna tillbaka i sju
  rutor (trycklästa i beskärning; gränsen skiljer per ruta), `Färdigheter &
  Förmågor` på p016_e02. Grindskärpning: `_strukturpost` känner igen
  JSON-fragment (`"nyckel": …`). Rest → **BQ-010** (prosafältdriften +
  GC-kolumnhuvudet).
- **Krugal BQ-006** — 54 rubriker harmoniserade mot bokens tre UPPMÄTTA
  grader (alla 17 sidor lästa); driften var större än posten såg.
- **del3 BQ-021 art (a)** — `rows.py::_heal_split_rows` läker rader som
  zon-/avsnittsgränser klipper. Facitverifierad i kastbar katalog (Beröring,
  DRAKFJÄLL, tabellrad 20, Pavise-regression); del3:s arbete orört.

Sviten 637 gröna. Kvar: **7 poster i två klasser.**

## Klass B-rest — mätmotorns bilddetektering (ETT samordnat pass)

Alla fyra sitter i samma organ: kolumn-/tröskelbeslut där grafik och sats
blandas. Facitvärdena nedan är REPRODUCERADE 2026-08-17 mot arkiv-PDF:erna
(kastbara kataloger; gör om med `analysera` + `radboxar --workdir <scratch>`):

- **del3 BQ-021 (c)-klustret, s. 49**: banden på vapennamnens höjd är
  1150 px breda och korsar sju skaft. Efter åtgärd: eget band per namn i
  x-fönstren 458–490, 643–685, 823–864, 1020–1062, 1209–1251, 1391–1422,
  1576–1607 (skanning 1935×2802). Vakt: kvoten bandbredd/bläckbredd (1,02
  friskt, 3,4–36 sjukt) + antal kolumngrupper; svärtningsandel får INTE
  användas (uppmätt i posten).
- **del3 BQ-021 (d)-tröskeln, s. 48**: `Bredsvärd`-etiketten (bläck py
  568–599, x 0,321–0,414 i 1967×2806) ger inget band — klingans lokala topp
  98 mot etikettens 31–62 + MIN_BAND_FACTOR sållar den. Samordna med
  Spindelkonungen BQ-007 (svepets tröskel mot luckans egen profil; facit
  `säga).` s. 11, profiltopp 0,031).
- **Tempokalkylatorn BQ-001, s. 1**: illustrationen x 0,054–0,338 mäts
  fortfarande som `vänsterkolumn` i flera segment (verifierat mot HEAD
  2026-08-17); texten står i x 0,36–0,95. Efter motorfix: `radboxar
  --force` på s. 1 + `binda_rader --utvardera` + ombindning.
- **Skymningslandet BQ-001, s. 1**: högerkolumnen mäts fortfarande till
  x 0,348–1,0 (verifierat mot HEAD 2026-08-17); satsen går 0,347–0,697 och
  ZONEN-balken börjar 0,718. Rännan 0,697–0,718 hittas inte —
  gutterdetekteringens centrumfönster/villkor. OBS: sidan varnar redan
  »grafik dominerar«.

Efter VARJE motorändring: `binda_rader --utvardera` mot bundna böcker,
`forbesikta --force`-omscreening (fyra regler bygger på bbox), och
regressionsmätning i scratch mot minst Dåligt vatten (frisk 2-spalt) och
Lovligt byte (trespaltig, kända patologier). Läkarens regressionsmetod:
jämför `läkt`-flaggade band och bandantal, inte råa boxdiffar (indexskift).

## Klass C-rest — struktur/schema + advokatärenden

- **Edsbrytarna BQ-001**: deterministisk styckedelare ur radboxarnas
  uppmätta indrag (mätunderlag i posten: radstarter x≈65/331–334 pt mot
  fortsättningsrader 52–54/320–322 pt). Verktyget kan återanvändas för
  Lovligt bytes öppna flagga s. 3 (p003_e25, styckedelning).
- **Edsbrytarna BQ-004**: kursivspans ur PDF:ens textlager
  (`Times-Italic` per span är redan kontrollerat) + `heading`-grenen i
  export.py som aldrig läser `el["style"]`.
- **Krugal BQ-010**: prosafältdriften (11 rutor other mot s. 9–10 egna
  paragraphs; enhetning = strukturingrepp med frysning) + vapenradens
  GC-kolumnhuvud (weapons-modellen saknar kolumnen).
- **Tanegashima BQ-003 (rest)** och **Lovligt byte BQ-001 (rest)**:
  felkopplade band (Tanegashima s. 4/5: p004_e13 LEDTRÅDAR, p005_e18 DAVID
  ROE; Lovligt byte s. 5/6/8: bl.a. p006_e30 med bbox i fel sidfjärdedel)
  ska DÖMAS mot PNG:n av en advokat per sida, synkront, innan någon
  bindning tas bort. Mätluckorna är klass B-restens jobb.

## Öppna sidflaggor (avsiktliga)

del3 s. 6 + s. 9 (väntar på klass B-restens tröskelarbete; boken mäts
ALDRIG om — 103 handmätta boxar), Lovligt byte s. 3 (väntar på
styckedelaren). Inga `[beslut]`-frågor väntar på användaren.

## Att INTE göra om

- Ström 2/heuristikkandidaterna är dömda (beslut.md-sektionerna
  »Screeningtriage av 2026-08-12-heuristiken«).
- `bygg_adapter.py --ref` REGENERERAR sb_table och tappar handkurerade
  fält — spegla för hand i `system/`, lägg frödata i seedarna.
- del3:s arbete röres aldrig; motorfacit byggs i kastbar katalog.
- Ordgrindens `_strukturpost` och fogningskreditering är byggda — en
  exportfogning ska redovisas i `export/fogningar.json`, inte som post.
