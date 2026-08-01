# Korrekturuppdrag — DoD Spelledarboken (1991), bok 2

Arbetsorder för djävulens advokat i bok 2:s produktionskörning. Den kompletterar
— och ändrar inte — din agentdefinition (`.claude/agents/djavulens-advokat.md`)
och [AGENTER.md](../AGENTER.md) Regel 8a, som båda är bindande.

Boken: *Drakar och Demoner, grundregler fjärde utgåvan (1991), del II
Spelledarboken*, inskannad, 66 sidor, system `dod`. Arbetskatalog:
`arbete/DOD-REG-grundregler-1991-del2-spelledarboken/` (kallas `WD` nedan).

## Du kör utan specialister

Ingen språkgranskare, ingen layoutverifierare — deras filer finns inte i
review-katalogen, och det är avsiktligt. Den deterministiska förbesiktningen
(`pipeline forbesikta`) har redan kört alla åtta mekaniska regler och lagt sin
kandidatlista i `WD/pages/page_NNN.review/heuristik.json`. **Verifiera den
listan, leta inte upp mönstren igen.** Rapporterar den noll träffar är det ett
resultat att bekräfta, inte en uppmaning att leta vidare mekaniskt.

Du gör hela den bärande bedömningen själv: textuell dom, domänkontroll och
forensik.

## Sidans form

Sidan är transkriberad **rad-per-element**: ett element per tryckt rad, med
avstavningar och radbrytningar bevarade. Tabell, statblock och list är ETT
element med de täckta radernas union som bbox.

Detta är avgjort och uppmätt. **Slå aldrig ihop rader till stycken och föreslå
aldrig omtypning på den grunden** — läsexporten flödar tillbaka raderna till
stycken deterministiskt.

Element utan bbox (`bbox_saknas`) är rader som uppmätningen missade. Det är
väntat på ~1,5 % av elementen, särskilt korta slutrader och rubriker strax under
sidhuvudet, och är inget fel. Gissa aldrig koordinater åt dem.

`source.rader` är radindex in i sidans `radboxar.json`; pipelinen har räknat ut
boxen ur dem. Rör dem inte.

## Vad du särskilt ska leta efter i den här boken

1. **Tyst normaliserade tryckfel.** Transkriptionen gjordes av en Sonnet-agent,
   och den rättar ibland tryckfel utan korrektionspost — `aktiviter` blev
   `aktiviteter` på s. 6. Det syns varken i validatorns eller heuristikens
   utdata. Läs ordbilden i hög upplösning och leta aktivt; hittar du ett, lägg
   posten i efterhand med trycket i `original`.
2. **Siffror.** Spelvärden, folionummer, tabellceller och tärningsnotation
   läser du själv i förstoring. En agent på Sonnet får inte vara sista instans
   för ett spelvärde. Ett tryckt räknefel är ett *fynd* — flagga, rätta aldrig.
3. **Läsordning.** Exporten följer arrayordningen literalt. En spaltrubrik som
   hamnat först i arrayen renderar hela vänsterspalten under fel rubrik (s. 4).
4. **Tabelltypning.** En tryckt tabell som typats som en följd av `paragraph`
   har förlorat sin struktur för gott. Det är ett typningsfel, aldrig en
   korrektionspost — rätta typningen.
5. **Gemeniserade rubriker.** Draften skriver återkommande kapitäl- och
   versalsatta rubriker och sidhuvuden med gemener (`Strid` i stället för
   `STRID`, `Amputation` i stället för `AMPUTATION`). Det är bokens vanligaste
   draftfel — kontrollera varje rubrik och varje `page_artifact` mot trycket.
6. **Exempelrutor utan `style: "italic"`.** Rutorna är genomgående kursivsatta;
   saknas markeringen är det en lucka, inte ett val.
7. **Tabellrubrik typad `heading`.** En halvfet, vänsterställd gemenrad tätt
   ovanför tabellens rubrikrad är `table_caption`, inte `heading` — jämför med
   sidans centrerade kapitälrubriker, som är riktiga rubriker.
8. **Ellips.** Trycket har en äkta ellipsglyf men bokens form är `...` — se
   beslut.md. Draften har ibland `…` kvar.

## Forensik

Sidans PNG är ~1240×1754. PDF:ens inbäddade skanning är ~1950×2830, alltså
~1,6× mer information: beskär ur den, med nearest-neighbour, för verklig
upplösning i stället för interpolation. Kontrollera alltid den inbäddade bildens
faktiska pixelmått först. Skriv beskärningar till scratchpad-katalogen, aldrig
under `arbete/`.

Skriv output-filen så snart de textuella posterna är dömda — med kvarstående
`needs_review` — och gör den tunga forensiken därefter, med uppdatering av
filen. En komplett fil med flaggor är oändligt mycket bättre än ingen fil.

## Boknivåbeslut — skriv i din egen fil, inte i beslut.md

`WD/beslut.md` är bokens gemensamma minne och du **läser** den innan du börjar;
står frågan avgjord där följer du den utan att utreda om.

Men tre advokater kör parallellt i varje våg, så **skriv inte i beslut.md** —
den skulle skrivas över. Lägg i stället dina avgöranden i
`WD/pages/page_NNN.review/beslut-forslag.md` med rubrikerna `## Avgjort` och
`## Öppet`, i samma form som beslut.md. Vågsamordnaren fogar in dem efteråt.

## Bokens fasta konventioner

- **Vattenstämpeln** `Drakar och Demoner är © RiotMinds AB` under sidfoten är
  den digitala utgåvans stämpel och utelämnas alltid. Detsamma gäller
  skanningskrediten `SCAN & PDF: Jonas`.
- **Tryckt folio ligger ett steg efter PDF-sidan** (PDF-sida 27 = folio 26) och
  behålls som `page_artifact`.
- **Löpande kolumntitel** typas `page_artifact`, aldrig `heading`.
- **Bildpolicyn** är bindande: illustrationer beskrivs aldrig, och text som
  ingår i själva bildmotivet transkriberas inte. Avvisa varje sådant tillägg.
- Resten av konventionerna står i `beslut.md` — läs den.

Starta aldrig egna underagenter.
