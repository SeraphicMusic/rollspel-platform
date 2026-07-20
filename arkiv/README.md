# arkiv/ — färdigbehandlade käll-PDF:er

Hit flyttar Claude käll-PDF:en **när dess extraktion är klar och verifierad**
(alla sidor `validated`, `export/`-filerna finns). Filen flyttas från
[`../import/`](../import/) — den **raderas aldrig** — och döps vid flytten om
enligt [NAMNSTANDARD.md](../NAMNSTANDARD.md) (`SYSTEM-TYP-titel.pdf`, t.ex.
`DOD-AVE-den-vita-duvan.pdf`).

Att en PDF ligger här betyder: "den här boken är rippad." Själva resultatet
(bok.json/md/docx, tabeller, granskningsrapport) ligger i motsvarande
`arbete/<slug>/export/`.

Vill du köra om en bok: flytta tillbaka PDF:en till `import/` och säg till.
Pipelinen är idempotent — färdiga sidor körs inte om, men `--force` finns per steg.

PDF:er versionshanteras inte (se `.gitignore`) — bara den här README:n spåras.
