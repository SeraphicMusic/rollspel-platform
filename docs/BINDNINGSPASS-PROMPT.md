# Prompt: bindningspasset — kostnadsmåttet i binda_rader + advokatbindning

> Klistra in nedanstående som uppdrag i en ny session.

---

Kör bindningspasset: verktygsskuldens alla klasser är stängda (klass B/
mätmotorn 2026-08-18, commits `71a033b` + `190572b`, utfall i
[docs/VERKTYGSSKULD-PASS2.md](VERKTYGSSKULD-PASS2.md) §UTFALL), och kvar i
hela korpusens öppna köer står BARA två smalare `[verktyg]`-poster som är
BINDNINGSARBETE, inte motorarbete:

* **Lovligt byte BQ-001** (`arbete/MUT-AVE-lovligt-byte/beslut.md`)
* **Tanegashima BQ-003** (`arbete/MUT-AVE-intriger-pa-tanegashima/beslut.md`)

Läs CLAUDE.md, AGENTER.md (SLAVISKT — särskilt Regel 9/9a om bindning) och de
två posterna i sin helhet innan du rör något. Posterna bär hela läget från
förra passet, inklusive pass 3-advokatens utpekade lediga band.

## §1 Kostnadsmåttet i `scripts/binda_rader.py` (spärren som ska lösas först)

`python3 scripts/binda_rader.py arbete/MUT-AVE-lovligt-byte --utvardera`
UNDERKÄNNER verktyget: *"facit vinner oftare än verktyget: FACIT passar
bättre 2, verktyget 1, oskiljbara 8 — kör det inte skarpt förrän
kostnadsmåttet är rättat."* Avvikelserna sitter bl.a. på s. 6 (5 av 21
element). Samma kommando på Tanegashima GODKÄNNER (3–0). Det är alltså
bokspecifikt, inte generellt.

Jobbet: hitta varför kostnadsmåttet föredrar fel tilldelning i de två fall
där facit vinner på Lovligt byte. MÄT först — utvärderingen skriver ut vilka
element som avviker; rendera radbanden och elementtexterna för exakt de
fallen och avgör mot PNG:n varför facits tilldelning är bättre, innan du rör
en konstant. Verktygets konstanter är kalibrerade (docstrings bär
mätvärdena); en ändring måste omkalibreras mot ALLA böcker med
facitbindningar, minst: Lovligt byte, Tanegashima, del2 spelledarboken,
del3 spelarboken (`--utvardera` på var och en, före och efter). del3:s och
Spindelkonungens arbete får ALDRIG mätas om eller ombindas — de är bara
utvärderingsfacit.

Grinden är absolut: **ingen bindning skrivs förrän `--utvardera` godkänner
verktyget på den bok som ska bindas.**

## §2 Bindning av Lovligt byte (efter att §1 är löst)

* `binda_rader arbete/MUT-AVE-lovligt-byte` i TORRKÖRNING först. Verifiera
  ett urval av förslagen mot PNG:n INNAN `--verkstall` — förra passets
  läxa: på Tempokalkylatorn var två av fyra förslag felskjutna (en brödtext
  bands till titeln), och de refuserades. En box som fattas är alltid
  tillåten; en felskjuten är ett fel som ser ut som data.
* Pass 3-advokaten pekade ut **fem lediga band med mått för mekanisk
  bindning** på s. 5/6/8 — måtten står i BQ-001-postens historik. Bind dem
  mot BEFINTLIG mätning. Sidorna 5/6/8 bär dömda bindningar och mäts ALDRIG
  om; `binda_rader` skriver aldrig över befintliga bindningar, så det är
  säkert att köra.
* s. 1 är redan ommätt med den lagade motorn (2026-08-18, helt obunden) —
  den binds nu som vilken sida som helst.
* Efter varje bindningsvåg: `python3 scripts/laga_radbas.py` (0/1-baskoll),
  `forbesikta --force`-omscreening av berörda sidor, frys → sammanfoga →
  exportera alla → diffa → `scripts/oforklarade_ord.py` (grind: 0
  oförklarade). Uppdatera bibliotekskopian.

## §3 Advokatbindning Tanegashima (och ev. Lovligt-rester)

Den mekaniska bindningen är UTTÖMD på Tanegashima: grinden godkänner men
enda förslaget var att binda `p005_e27` — elementet som pass 3-advokaten
TÖMDE — och det refuserades. Resten lämnas obundet av verktygets egna
spärrar: "mätningen saknar band där" (verkliga mätluckor; sidorna mäts inte
om, s. 4/5 bär pass 3-domar) och marginal-/förskjutningsspärrarna ("lämnade
obundna för advokaten").

* För de MARGINALSPÄRRADE elementen: en djävulens-advokat per sida,
  SYNKRONT (en i taget — bakgrundsagenter dödas av 600s-watchdogen), med
  snävt uppdrag: döm verktygets näst-bästa-fall mot PNG:n och bind BARA de
  element där trycket avgör entydigt vilken rad som är elementets.
  Bindningen skrivs som `source.rader` + `source.bbox` med
  `bbox_source: agent:djavulens-advokat`. Tveksamma fall lämnas obundna med
  skälet nedskrivet i posten — aldrig en gissning.
* Elementen med "mätningen saknar band där" KAN inte bindas (bandet finns
  inte och sidan mäts inte om): de bokförs som accepterat obundna i posten.
* Tomma element (`p005_e27`) binds aldrig.

## §4 Avslut

* Stäng eller smalna av BQ-posterna i respektive beslut.md med utfallet i
  siffror (vad bands, vad refuserades och varför, vad accepterades obundet).
  Kan en post inte stängas utan ett redaktionellt val — skriv om den till
  `[beslut]` och låt den nå användaren; gissa aldrig.
* Sviten (`python3 -m unittest discover -s tests -t .`, 637 grön) efter
  varje kodändring i binda_rader.
* Bokför utfallet i docs/VERKTYGSSKULD-PASS2.md §UTFALL (bindningsresterna
  omnämns där) och committa enligt repots stil.

## Att INTE göra

* Mät aldrig om dömda/bundna sidor (Lovligt s. 5/6/8, Tanegashima s. 4/5,
  hela del3 och Spindelkonungen — del3 har 103 handmätta boxar).
* Bind aldrig Tempokalkylatorn — boken har noll facitbindningar och
  styckeformad regim behöver ingen bbox (avgjort i dess BQ-001).
* `illustration`-regionen är möblemang (pipeline/regions.py) — den binds
  aldrig och räknas aldrig som spalt; ändra inte det.
* Rör inte mätmotorn (`pipeline/rows.py`) — den är facitverifierad och
  regressionsmätt; bindningsproblemen sitter inte där.
