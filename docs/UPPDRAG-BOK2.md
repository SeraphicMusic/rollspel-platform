# Uppdrag: rippa bok 2 — DoD Spelledarboken (1991)

Överlämning skriven 2026-07-31. Bok 1 (del I, *Rollpersonen*) är klar; bok 2 är
del II, *Spelledarboken*, 66 sidor. Verktygen är byggda och committade — det
som återstår är produktionskörningen.

Läs och följ slaviskt: [CLAUDE.md](../CLAUDE.md), [AGENTER.md](../AGENTER.md)
(särskilt Regel 5 skript-före-LLM, Regel 8a emendering, och läsdisciplinen),
samt [docs/FORTSATTNING-GRUNDREGLER.md](FORTSATTNING-GRUNDREGLER.md) för bok
1:s kostnadsmodell och mönsterkatalog.

## Utgångsläge

- Commit `7790fdc` på `main`: tabellstöd + `radboxar`. **203 tester, OK.**
- Arbetskatalog: `arbete/DOD-REG-grundregler-1991-del2-spelledarboken`
  (namnstandardenlig, till skillnad från bok 1:s).
- System `dod`, satt för hand. Alla 66 sidor är `image_with_stub_text`.
  `extrahera-text` ger **noll** sidor — textlagret innehåller bara
  vattenstämpeln. Det är normalt för de här skanningarna.
- **Alla 66 sidor har aktuell `page_NNN.radboxar.json`** (verifierat: en
  omkörning med `--force` ger bit-identisk fil).
- Renderade PNG: bara sidorna 27–30. Resten renderas vid behov.

Sidstatus:

| Sida | Läge |
|---|---|
| 27 | Transkriberad **rad-per-element**, 39 element, 33 med uppmätt bbox. Referensexemplaret. |
| 28, 29 | Transkriberade stycke-per-element, **utan bbox**. Måste göras om. |
| 30 | Renderad och uppmätt, ej transkriberad. |
| 1–26, 31–66 | Endast uppmätta. |

Under `pages/` ligger jämförelsevarianter sparade med suffixen
`.styckenivaa` och `.fore-radboxar`. **Radera dem inte** — de är belägget för
granularitetsbeslutet nedan. Radera aldrig något under `arbete/`.

## Avgjort: rad-per-element

Bok 2 transkriberas **en element per tryckt rad**, som bok 1. Mätt på sida 27,
samma sida i båda formerna:

| | Stycke-per-element | Rad-per-element |
|---|---|---|
| Element | 15 | 39 |
| `classify_page` | `annat` | `löptext` |
| `radsammanslagning` | död (7 av 8 element krävs) | körs |
| `lasordning` | död (fel sidtyp) | körs |
| `kolumnsammanslagning`, `tabellkandidat` | körs | körs |

Tre av åtta förbesiktningsregler är alltså verkningslösa med stycke-per-element
— och det är just de tre som gjorde de dyra fynden i bok 1 (saknade rader på
s. 55 och 60, sex kolumnsammanslagningar på s. 64). Läsexporten blir inte
sämre: raderna flödas tillbaka till stycken och noll avstavningar kvarstår.

Undantag från rad-per-element, enligt transkriptionskontraktet i
[.claude/skills/extrahera/SKILL.md](../.claude/skills/extrahera/SKILL.md):
**tabell, statblock och list är ETT element** med de täckta radernas union som
bbox. Dela aldrig upp en tabell i ett element per rad.

## Gör detta först (två små saker)

1. **Läk radbrytning efter snedstreck i exporten.**
   [pipeline/export.py:184](../pipeline/export.py#L184) testar bara
   `prev.endswith("-")`, så `(liten/medelstor/` + `stor)` blir
   `(liten/medelstor/ stor)` med ett felaktigt mellanslag. Bok 2 är full av
   `(medelstor/stor)`. Kräver ett test i `tests/test_export.py`.
2. **Gör om sidorna 28 och 29 rad-per-element med bbox.** De ligger kvar i den
   gamla formen och är inkonsekventa med sida 27.

## Sedan: produktionskörningen

```bash
WD="arbete/DOD-REG-grundregler-1991-del2-spelledarboken"
PDF="import/40-Drakar-och-Demoner---grundregler,-fjärde-utgåvan-(1991)_II---Spelledarboken_RiotMinds.pdf"
python3 -m pipeline rendera    "$PDF" --workdir "$WD"
python3 -m pipeline jobb       --workdir "$WD" --max 5     # ger radboxar-sökvägen
python3 -m pipeline bokfor     --workdir "$WD"
python3 -m pipeline validera   --workdir "$WD"
python3 -m pipeline forbesikta --workdir "$WD"
```

Jobbet innehåller fältet `radboxar` — läs den filen och hämta `source.bbox`
därifrån. **Gissa aldrig koordinater.** Saknas ett band för en rad du ser i
PNG:n: transkribera raden ändå och utelämna `bbox`. Uppmätningen träffar 98,5 %
av elementen på bok 1, så luckor förekommer — särskilt korta slutrader och
rubriker som står strax under sidhuvudet.

### Korrekturet: mät innan du skalar

Bok 1 kostade **~390k tokens per sida** med tre agenter (språkgranskare →
layoutverifierare → advokat). 66 sidor blir ~26 M tokens. Innan du binder upp
det: bok 1:s egen metodslutsats säger att specialisternas värde låg i att
*snäva in* vad advokaten skulle titta på, inte i att ha rätt — och det jobbet
gör de åtta förbesiktningsreglerna nu deterministiskt.

**Kör därför `forbesikta` + advokat utan specialisterna på tre sidor och mät.**
Advokaten låg på 40–43 % av sidans tokens i bok 1, så taket är ~11 M. Räkna
inte med hela besparingen — advokaten får mer att göra när ingen snävat in åt
honom. Rapportera tokens och tid per sida och fråga användaren innan resten
körs. Agenterna körs **synkront, en i taget** (bakgrundsagenter dödas av
600s-watchdogen mitt i bildforensiken).

## Fällor som redan kostat tid

- **`radboxar` är idempotent.** Ändrar du `pipeline/rows.py` måste du köra
  `radboxar --force`, annars mäter du mot gamla koordinater. Jag höll på att
  skriva ett helt transkript mot inaktuella boxar; det upptäcktes bara för att
  ett väntat band saknades och jag beskar PNG:n för att kontrollera.
- **Manifestet heter `book.json`**, inte `manifest.json`.
- **Inline-transkription normaliserar tryckfel tyst.** Sida 27 har `svratfär-`
  och `voylm` i trycket — båda behållna print-troget och lagda i `uncertain`.
  Rätta aldrig i transkriptionssteget; det är advokatens beslut mot PNG:n.
- **Spelvärden utanför adapterns intervall är fynd, inte fel.** Jättebläckfisk
  har STO 125, FYS 42, INT 0 i trycket. Valideraren flaggar dem — de ska
  flaggas, aldrig rättas (Regel 8a).
- **Vattenstämpeln** `Drakar och Demoner är © RiotMinds AB` utelämnas
  konsekvent, enligt bok 1:s beslut. Den är märkt `/Artifact ... /Watermark` i
  PDF:en.
- **Sidnumreringen är förskjuten:** PDF-sida 27 = tryckt folio 26.

## Kända begränsningar i uppmätningen

Kalibrerat mot bok 1:s alla 67 sidor med facit (4107 element): **98,5 %**, 46
sidor på exakt 100 %. Det som INTE fungerar:

- **Blanketter.** Fältetiketter i streckade rutor är inte rader; linjalerna
  blir sidans vanligaste band och förgiftar radhöjdsmedianen (bok 1 s. 67 på
  58 %). Har bok 2 spelledarformulär: serialisera dem fältgrupp för fältgrupp
  mot PNG:n, som bok 1 gjorde. Bygg inte linjaldetektering på spekulation.
- **Grafikdominerade sidor** flaggas av mätningen själv
  (`sammanfattning.dominerande_grafik`). I bok 2 gäller det sidorna
  **1, 8, 15, 20, 24, 33, 34, 35, 36, 42, 64, 66**. Där gäller PNG:n.
- **Rubriker strax under sidhuvudet** kan hamna i ett gemensamt band med
  motsvarande rubrik i andra spalten (s. 27: `HUNDDJUR` + `KATTDJUR`).

Jaga inte de sista 1,5 procenten. Missarna sitter på blanketter och flaggade
sidor, och bok 1:s facit har egna egenheter (s. 3 har vattenstämpelns bbox på
fel sida av sidan). Vidare optimering är anpassning till bok 1, inte
förbättring för bok 2.

## Vad som INTE ingår

Bok 1:s kvarstående lista (`kind`-backfill på 1755 poster, raka citattecken på
nio sidor, de öppna boknivåbesluten). Inget av det blockerar bok 2.
