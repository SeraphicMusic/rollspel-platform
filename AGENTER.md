# Agentregler — rollspel-extraktion & korrektur

Detta är där tokens (= pengar/kvot) bränns i det här repot. Transkription och
korrektur av inskannade rollspelsböcker involverar dussintals sidor och flera
agenter per sida — en oplanerad session kan sluka en dagskvot snabbt. Reglerna
nedan är destillerade från Släktforskaren-projektets AGENTER.md och anpassade
till pipelinens (`pipeline/`) och korrektur-teamets (`.claude/agents/`) faktiska
arbetssätt. Följ dem SLAVISKT — se [CLAUDE.md](CLAUDE.md).

## Regel 1: Billigaste modell som klarar uppgiften — sätt modellen EXPLICIT

Underagenter ärver sessionsmodellen (dyraste) om inget anges. Sätt alltid
`model:` uttryckligen i agentens frontmatter (aldrig i Task-anropet — se Regel 4).

Verktygsbegränsningen skrivs under nyckeln **`tools:`** — `allowed-tools:` hedras
INTE för subagenter (den hör till slash-kommandon). Alla tre korrekturagenter låg
med `allowed-tools:` fram till 2026-07-30 och hade därför i praktiken hela
verktygsuppsättningen, tvärtemot kontraktet att bara advokaten applicerar.
Kontrollera i agentregistret att begränsningen faktiskt syns.

| Uppgift | Modell | Var |
|---|---|---|
| Pipeline-steg (analysera/rendera/extrahera-text/validera/sammanfoga/exportera) | **Inget LLM alls** — ren Python/PyMuPDF | `pipeline/` |
| Transkription av skannade sidor — arbetshästen | Sessionsmodellen inline, eller delegerat till **Sonnet**/**Haiku** | `/extrahera ... modell="sonnet\|haiku"` |
| Korrektur — sprakgranskare, layoutverifierare (föreslår, applicerar aldrig) | **Sonnet** | `.claude/agents/sprakgranskare.md`, `layoutverifierare.md` |
| Korrektur — djävulens advokat (dömer mot PNG:n, enda som applicerar) | **Opus** (`model: opus`) | `.claude/agents/djavulens-advokat.md` |

Princip: specialister läser/föreslår på Sonnet; advokaten gör den bärande sista
bedömningen på Opus — dyrast, men det är den enda agenten som applicerar något,
så dess dom måste hålla. Haiku duger bara för ren löptext i bra skanning —
tabeller, statblocks och blek text ger fler fel. Kör ALLTID `/korrekturläs`
efter Haiku-transkription.

## Regel 2: Max 3 agenter samtidigt

Inte 5–7. Det gäller **summan** av alla samtidigt körande agenter i en våg — inte
per sida. Fler parallella agenter på stark modell bränner tokens utan att gå fortare.
Håll koll på vågordning i sidnummer (t.ex. sida 21 → 22 → 23), inte spretande över
flera sidor på en gång.

## Regel 3: Ingen nästling

Agenter som själva delegerar till underagenter kan hänga sig (0-byte output) och
mångdubblar kostnaden. En agent = en sida, ett tydligt uppdrag. Specialister och
advokaten får ALDRIG själva starta underagenter (se respektive agentdefinition).

## Regel 4: Snäva uppdrag — en sida per agent-uppsättning

Fas 1 (specialister) → Fas 2 (advokat) i strikt ordning **per sida**, enligt
`.claude/skills/_shared/proofreading-workflow.md`. Ge aldrig en agent flera sidor
eller "läs hela kapitlet" — pipelinens `jobb --typ korrektur` ger redan triage
(vilka agenter varje sida behöver) och exakta sökvägar (`validated`, `png`,
`review_dir`, `output`). Sätt ingen `model:` i Task/Agent-anropet — agentdefinitionens
frontmatter äger modellvalet (se Regel 1).

## Regel 5: Skript före LLM

Allt som kan göras deterministiskt görs med Python i `pipeline/`, inte med en
språkmodell: rendering, textlagerextraktion, systemdetektering, sammanfogning,
export, rapport. En modell tittar ENDAST på sidor som saknar textlager (`jobb`
listar dessa) och på korrektur mot PNG:n.

Detta gäller även **inne i** korrekturen. Kör `python3 -m pipeline forbesikta`
före agenterna: felmönstren som återkom på varje sida i DoD-grundreglerna är
rent mekaniska och hittas gratis — linjeregel-prefix och -suffix (`- LYSSNA`),
raka citattecken, `±0`-garbel (`t0`/`I0`/`*0`), kolumnsammanslagning (bbox-bredd
mot spaltbredden), vertikal radsammanslagning (bbox-höjd mot medianradhöjden,
med normal glyfbredd), läsordningsfel (arrayordning mot bbox-y, samt
högerspaltsrader inklämda före vänsterspalten) och tabellkandidat (rutnät av
korta `paragraph` som borde ha varit ett `table`). Agenterna ska **verifiera**
kandidatlistan, inte leta upp mönstren igen. En layoutverifierare brände 105k tokens på att korrekt
konstatera noll strukturfel på en sida — det svaret ger skriptet på en sekund. Hitta aldrig på egna tempmappar eller
batchindelningar — pipelinen äger allt state i `arbete/<slug>/`.

## Regel 6: Inga skal-loopar i Bash-anrop (Claude Code-specifikt)

Kommandon med `for`/`while` eller `$(...)` triggar **alltid** en permission-prompt
i Claude Code, oavsett allow-regler. En agent som kör sådana fastnar på prompten =
ser ut som en hängning. Behövs loop/logik: kör pipelinens egna kommandon (de är
redan batchmedvetna, t.ex. `jobb --max N`) i stället för att bygga en egen loop.

## Regel 7: Löpande statusrapporter

Agenter hänger sig ibland tyst.
- Föredra flera **korta** agenter (en sida var) framför en lång — en hängd agent
  kostar lite och startas om lätt. Det är redan arbetsflödets grundform här.
- Poll med Glob/`ls` mot `review_dir` och `*.final.json` mellan vågor i stället för
  att gissa vad som är klart — verifiera på disk innan nästa våg startar.
- Kör om misslyckade agenter (schemafel, tom output) innan du går vidare till nästa sida.

## Regel 7a: Screena en FÄRDIG bok innan du litar på att den är klar

`forbesikta` hoppar över sidor som har `final.json` — i normalflödet rätt, de
är ju korrekturlästa. Men reglerna kommer till efter hand, och en bok som
extraherades innan en regel fanns blir aldrig prövad mot den. Kör därför

```bash
python3 -m pipeline forbesikta --workdir "WD" --sidor 1-N --force
```

på varje bok som förklarats klar. DoD-grundreglernas **del I** är
korrekturläst och avslutad — och ger 66 kandidater på sex regler: 26 raka
citattecken, **16 tryckta tabeller som ligger som lösa `paragraph`**, 9
kolumnsammanslagningar, 8 `±0`-garbel, 6 läsordningsfel och 1 radsammanslagning.
Tabellfallen är den oåterkalleliga klassen (CLAUDE.md §Tabeller).

Samma sak gäller efter varje lagning av `pipeline/rows.py`: fyra av åtta
regler bygger på bbox, så deras utfall ändras när geometrin mäts om.
`heuristik.json` bär numera `source_file`, så det går att se om en screening
räknades ur draften eller ur den färdiga sidan.

**Kör skripten före agenterna** (Regel 5) när du betar av en kandidatlista:

```bash
python3 scripts/tabellkandidat.py <slug>              # visa rutnäten
python3 scripts/tabellkandidat.py <slug> --verkstall  # montera de rektangulära
```

En färdigscreenad bok bär ofta ett lager poster som ser ut som öppna frågor
men inte är det: protokoll över kontroller som ÄR gjorda, domar som står i
prosa men inte i fältet, boxar från en mätning som sedan lagats. Städa dem
maskinellt innan du sätter en advokat på listan, annars läser agenten samma
avslutade ärende en gång till:

```bash
python3 scripts/materialisera_kind.py    arbete/<slug> --verkstall
python3 scripts/materialisera_verdict.py arbete/<slug> --verkstall
python3 scripts/tomma_artefakter.py      arbete/<slug> --verkstall
python3 scripts/remappa_bbox.py          arbete/<slug> --verkstall
```

**En avgjord flagga raderas aldrig.** Använd
`pipeline.corrections.close_review_reason()`: flaggan flyttas till
`resolved_reasons` med sin lösning och sin upphovsman. Beläggstexten är det
enda som gör kontrollen spårbar i efterhand — försvinner den ser en avslutad
utredning ut som en utredning som aldrig gjordes.

`scripts/tabellkandidat.py` monterar de block där varje rad har exakt en cell
i varje kolumn — den indelningen är uppmätt, inte tolkad. Ragged block rör den
aldrig. Det som ändå kräver en advokat med PNG:n är tabellernas GRÄNSER: feta
rubrikrader hamnar ofta utanför det uppmätta blocket, och ett block kan vara
flera tryckta tabeller i följd (del I s. 42: ett block på 29 rader var fyra
tabeller). Ge advokaten skriptets förslag i uppdraget så letar den inte upp
rutnätet igen.

`scripts/rubriknivaer.py` gör motsvarande för rubriknivåer: den läser skalan
kapitel/sektion/underrubrik ur bokens egen innehållsförteckning i stället för
att låta en agent bedöma varje rubriks grad för sig.

## Regel 8: Läsdisciplin (viktigast av allt)

- **Gissa aldrig** — osäkra ord transkriberas med `[?]` och listas i `uncertain`;
  osäkert innehåll flaggas `needs_review` i stället för att gissas.
- PNG:n (`pages/page_NNN.png`) är ALLTID sanningskällan — inte den inbäddade
  textledtråden, inte draften.
- **Läs alltid tryckets faktiska lydelse först.** Vad som står i PNG:n avgörs
  före frågan om det ska rättas. En transkription som tyst normaliserar ett
  sättningsfel är ett fel i sig — trycket måste först fastställas, sedan
  eventuellt emenderas.
- **Inga tysta korrigeringar** — varje ändring är en korrektionspost
  `{original, corrected, confidence, reason, source, kind, applied}`. Endast
  djävulens advokat sätter `applied: true`; avvisade poster behålls
  (`applied: false`) för spårbarhet. `kind` är `"ocr"` (återställer vad som
  står tryckt) eller `"emendering"` (avviker medvetet från trycket).

### Regel 8a: Uppenbara sättningsfel emenderas automatiskt

Beslut av användaren 2026-07-28. Trycket bevaras alltid i postens `original`,
så den print-trogna lydelsen går att återskapa — men bastexten rättas, och
emenderingen listas i granskningsrapportens egen sektion *Emenderingar*.

**Emenderas automatiskt** (`kind: "emendering"`, `applied: true`) när rättningen
är den enda rimliga:

| Klass | Exempel |
|---|---|
| Entydigt stavfel — bara ett svenskt ord passar | `betelar`→`betalar`, `lungt`→`lugnt`, `nätan`→`nästan`, `musikinstument`, `tredimentionell`, `kraten`→`kratern` |
| Egennamn som avviker från bokens egen genomgående form | `Ertbolsus`→`Erbolsus`, `PRna`→`RPna`, `Lannis`→`Lannos` |
| Saknad bokstav/ord som krävs för grammatisk fullständighet | `Ing försök`→`Inget försök`, `Brev är`→`Brevet är`, `passiva åse`→`passivt åse` |
| Felaktigt ordmellanrum | `Ispetsen`→`I spetsen`, `Spring källan`→`Springkällan` |
| Typografi enligt boknivåbeslutet | raka→typografiska citattecken, halvfyrkant |

**Emenderas ALDRIG** — behålls print-troget och flaggas `needs_review`:

- **Siffror och spelvärden i alla former** — statblocks, FV, skada, tärnings-
  notation, priser, avstånd, antal. Ett tryckt räknefel är ett *fynd*, inte ett
  fel att rätta. Gäller även när `derived_checks` säger att värdet inte går ihop.
- **Dialekt och medveten talspråksform** — `hävaså`, `papprena`,
  `Fö att di int sa rulla åv redet`. Repliker normaliseras inte.
- **Ålderdomliga men korrekta former** — `officieren`, `däven`, `till dags äro`.
  Slå upp innan du dömer; arkaism är inte stavfel.
- **Egennamn och världstermer som är attesterade i trycket** — `Ôdvinsson`,
  `Morëlvidyn`, `Tyreskyrkan`. Avvikande diakriter är data, inte brus.
- **Allt där två eller fler rättningar är lika rimliga.** Kan du inte peka ut
  en enda korrekt lydelse är det inte uppenbart — då gäller flagga, inte gissning.
- **Partier som inte går att läsa säkert i PNG:n** — `[?]` kvarstår.

Tvivlar du på vilken kolumn ett fall hör till: det hör till högerkolumnen.
Överemendering förstör arkivvärdet; en kvarstående flagga kostar bara en rad
i rapporten.
- Domänvärden som ser fel ut men står tryckta så (t.ex. skelett med INT=0/FYS=0)
  rättas INTE — det är advokatens domänkontroll som avgör, inte specialisterna.

## Regel 9: En sida utan bbox är ett MÄTFEL, inte ett transkriptionsfel

Saknar de flesta av en sidas element `source.bbox` har uppmätningen fallit,
och då ska sidan flaggas — inte lappas för hand. Symptomet syns först i
läsexporten och ser inte ut som ett fel: `pipeline/export.py` fogar aldrig ihop
rader utan geometri ("utan geometri finns inget facit"), så varje TRYCKT rad
blir ett eget stycke i `bok.md`. Resultatet läser som smal, ihoptryckt
sättning. Texten är komplett — det är styckeindelningen som fattas.

Den vanligaste orsaken är att en **helsidesbred illustration ligger i samma
lodräta avsnitt som tvåspaltig sats**: bilden fyller rännan och sätter dessutom
profilens tak, spalterna hittas inte, och hela sidan mäts som fullbreddsband
som ingen spaltrad kan tilldelas. Del II s. 8, 15, 20, 36, 42, 65, 66 och del I
s. 3, 33, 41, 64 är sådana sidor. `rapport` listar dem numera under
*Sidor utan användbar geometri* — läs den sektionen innan en bok förklaras klar.

Att låta boxen fattas är alltid tillåtet och aldrig fel; att mäta om den för
hand kräver att `bbox_source` säger det rent ut, annars ljuger
provenienssträngen.
