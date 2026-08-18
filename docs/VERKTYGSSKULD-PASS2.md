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

> **UTFALL (2026-08-18): KLASS B GENOMFÖRD — verktygsskulden är därmed
> stängd i alla klasser.** Ett samordnat pass i `pipeline/rows.py`
> (commit 71a033b) + `pipeline/regions.py` (190572b):
>
> * **Skymningslandet BQ-001**: rännkorridoren fick HYSTERES (75 %-kärna,
>   utvidgning till 65 %-kolumner, tak en halv rännbredd/sida, marginal döms
>   på kärnan) och block utan radstruktur klassas som `illustration`
>   (bläckandel ≥0,55, eller ≥0,40 + obruten y-kontinuitet; propagation
>   genom segmentgränser i överlappsfönstret; 930 block falsifierade utan
>   textoffer). s. 1 ommätt i arbetet: facitkolumnerna exakt. Smala
>   marginalremsor under MIN_GUTTER/MIN_COLUMN (s. 2/4/7) bokförda som
>   kvantifierad restbegränsning i posten. STÄNGD.
> * **Tempokalkylatorn BQ-001**: illustrationen `illustration`-flaggad i
>   alla fem segment, textspalterna heter vänster/höger som transkriptet;
>   s. 1 ommätt, de tre felbindningarna rensade; ombindning REFUSERAD efter
>   pixelkontroll (0 facitbindningar i boken; 2 av 4 förslag felskjutna).
>   STÄNGD.
> * **del3 BQ-021 (c)+(d)**: klungdelning efter läkningen (kvot ≥2,5,
>   ≥2 genomkorsande streck ≤0,018 breda, ≤0,01/px, vågräta cellinjer
>   undantagna, ramlinjemask, fragmentvakt) + täckningsstrimlor vid
>   spaltfönstertäckning <0,55. Facit i kastbar katalog: s. 49 delas per
>   skaft och mittremsans fem namn mäts; `Bredsvärd` ensam x 634–808
>   (facit 630–812); Pavise på femte decimalen. Boken orörd. STÄNGD.
> * **Spindelkonungen BQ-007**: svepets höjdvakt mot min(spaltens, sidans)
>   radmått — `säga).` föll med 0,05 px på ett tvåbandssegments uppblåsta
>   median. Facit: svep-2-band [0,0803, 0,2954, 0,0505, 0,0079]. Boken
>   orörd. STÄNGD.
> * **Lovligt byte BQ-001 / Tanegashima BQ-003 (bindningsresterna)**:
>   INTE motorarbete längre — Lovligt spärras av bindarens egen
>   utvärderingsgrind (facit vinner 2–1), Tanegashima passerar grinden men
>   mekaniken är uttömd (enda förslaget var det TÖMDA p005_e27).
>   Posterna står kvar SMALARE som bindningspass; dömda sidor mäts aldrig
>   om. Lovligt s. 1 (helt obunden) ommätt med rätt geometri.
>
> **UTFALL BINDNINGSPASSET (2026-08-18, senare samma dag): BÅDA POSTERNA
> STÄNGDA — korpusens öppna köer är därmed TOMMA.**
>
> * **§1 Kostnadsmåttet**: `scripts/binda_rader.py` fick pass 3-advokatens
>   tre diskriminanter (styckeindrag inkl. gemen fortsättningsstart,
>   rubrikbandshöjd, radrännsprov mot illustrationsskivor), breddförtroende
>   för kolumnklippta band, regionöversättning av suffixade regionnamn +
>   ordningshållare för tvåspaltselement, radvokabulärens
>   ordinalnormalisering, tre skrivfilter (obetrodd union / dyrare än lucka /
>   bandkrock) och en regimmedveten domare med skiljetröskel. Grinden på
>   Lovligt byte vände UNDERKÄND→GODKÄND (facit 2–1 → verktyget 1–0, vinsten
>   pixelverifierad); omkalibrerat: Tanegashima 3–0→5–0, del2 18–16→12–6,
>   del3 18–5→12–1. Mätvärdena står i skriptets docstrings. Sviten 637 grön
>   (45 tester i test_binda_rader, +19 nya).
> * **§2 Lovligt byte**: 20 skarpa förslag pixelverifierade — 12 skrivna,
>   8 REFUSERADE (7 felskjutna, 1 trunkerad); advokatens utpekade band
>   verkställda (e17/e27/e29/s8-e07; e20 [110,111] refuserad enligt
>   advokatens egen klippningsvarning). 86 → 102 av 189 bundna (54 %).
>   Ordgrind 6764→6764, 0 oförklarade.
> * **§3 Tanegashima**: en djävulens-advokat per sida (s. 1–5, synkront) —
>   32 nya bindningar, 3 verktygsförslag avvisade på s. 2, och på s. 3
>   avslöjades de GAMLA transkriptionsbindningarna som felkopplade: 9
>   ombindningar, 8 borttagna. De fem utpekade mekaniska (s. 4 e16/e23/e29,
>   s. 5 e20/e23) verkställda mot resolved_reasons. Tömda p005_e27 aldrig
>   bunden. 85 → 115 av 141 bundna (82 %). Ordgrind 3745→3745,
>   0 oförklarade.
> * Kvarvarande obundet i båda böckerna är KVANTIFIERADE mätluckor
>   (fullbreda sidhuvudband som slukar topprader, spalter utan band,
>   klippta enda-kandidatband) — accepterade i posterna; en box som fattas
>   är alltid tillåten.
>
> Regression: sex böcker i kastbara kataloger, läkarens metod. Dåligt
> vatten 2 ändrade sidor (kartbrus). Sviten 637 grön. Detaljerna står i
> respektive beslut.md-post.

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
