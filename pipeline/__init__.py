"""Rollspelsripparen — deterministisk pipeline för extrahering av text ur rollspelsböcker.

Kör `python3 -m pipeline --help` för tillgängliga kommandon.
"""

# 2 (2026-08-18, BQ-004): `data.style_spans` — tryckets kursivväxling inuti
# element och listposter ({start, end, style} med teckenintervall, ordsnappade;
# listposter bär även {item}). Äldre exporter utan nyckeln är fortsatt giltiga
# — proveniensen varnar, spärrar aldrig.
SCHEMA_VERSION = 2
