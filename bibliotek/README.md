# bibliotek/ — färdiga slutdokument

Namnstandardade läskopior (`SYSTEM-TYP-titel.md`, se
[NAMNSTANDARD.md](../NAMNSTANDARD.md)) av varje färdig extraktions
`arbete/<mapp>/export/bok.md`. Självbärande markdown — text i läsordning med
tabeller och bildbeskrivningar inline. Det är dessa filer man matar till andra
agenter/verktyg som ska läsa ett äventyr.

- Filerna är **härledda** — källan är `arbete/<mapp>/export/`; en kopia kan
  alltid tas om därifrån. Behöver du proveniens/confidence: läs `bok.json` i
  samma exportmapp.
- Böcker med flera äventyr (`export/aventyr/`) får en fil per äventyr.
- Ny bok: kopieras hit när extraktionen är klar och verifierad, i samma steg
  som PDF:en flyttas till `arkiv/`.
- Innehållet versionshanteras inte (se `.gitignore`) — bara den här README:n.
