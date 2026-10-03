# Phase 3 Validation — Permit Hotspot Map

## Decision supported

The map helps a property analyst, construction supplier or project coordinator answer:

> Where are City of Melbourne building permits clustering, and what does the selected suburb's permit profile look like?

The suburb filter applies to the map, KPI cards, time trend, comparison charts, suburb opportunity profile, records and CSV export.

The opportunity profile avoids repeating the headline cards:

- no or multiple suburb selections show a ranked comparison of complete-year activity, year-on-year movement, high-value permit count and share, median positive estimated cost, and dominant work category;
- a single suburb selection shows complete-year momentum, municipality benchmarks and the five highest estimated-cost permit records for investigation; and
- a date range without two complete comparable calendar years shows selected-period measures without a growth claim.

The dashboard also includes a 16-row metric glossary covering the permit grain, analytics-ready population, cost measures, complete-year comparison, work-category mix, municipality benchmark, priority records and map-location methods. Each entry states the definition, formula or rule, and the main responsible-use limitation.

## Open geospatial source

- Publisher: City of Melbourne
- Dataset: [Street addresses](https://data.melbourne.vic.gov.au/explore/dataset/street-addresses/)
- Licence: CC BY 4.0
- Source rows: 63,721 address points
- Downloaded: 2 October 2026
- Snapshot SHA-256: `acb4a2193341ae9fd60cdd7e98dda9f389f4cdc7ffe16393398e2dd01c52034a`

The official portal metadata retrieved on 2 October 2026 reports that the address data was processed on 13 November 2022. This is a real freshness limitation. The dashboard reports match coverage and leaves unmatched permits unplotted; it does not imply that the address register is current to 2026.

## Coordinate method

Each permit family is plotted once using its selected primary address:

1. Exact address keys use the mean of official points sharing that street number, street and suburb. This avoids duplicating permits where the address register contains multiple unit-level points.
2. Permit number ranges use the centroid of official address points inside the stated range on the same street and suburb.
3. A single street number with differing suffixes uses the centroid of official points sharing the number.
4. Records without a defensible match remain `unmatched` and do not appear on the heat map.

These are representative permit locations. They are not parcel centroids, property boundaries or coordinates for every address linked to a permit.

## Full-snapshot results

| Location method | Permit families | Share |
|---|---:|---:|
| Range centroid | 58,266 | 78.1% |
| Exact address point | 14,862 | 19.9% |
| Street-number centroid | 13 | <0.1% |
| Unmatched | 1,421 | 1.9% |
| **Total analytics-ready permits** | **74,562** | **100.0%** |

The resulting coordinate bounds are consistent with the City of Melbourne municipality: latitude -37.8496 to -37.7758 and longitude 144.9006 to 144.9909.

## Default and selected-suburb checks

| Check | Result |
|---|---:|
| Default 2018–2025 permit count | 21,437 |
| Default mapped permits | 20,904 (97.5%) |
| Default heat-map permit reconciliation | 20,904 |
| Default aggregated map points | 4,252 |
| Melbourne-filter permit count | 11,615 |
| Melbourne-filter mapped permits | 11,478 (98.8%) |
| Default opportunity-profile suburb rows | 14 |
| Melbourne 2025 permits | 1,334 |
| Melbourne 2024 permits | 1,438 |
| Melbourne year-on-year movement | -7.2% |
| Melbourne 2025 permits above $10m | 114 (8.5%) |

## Verification evidence

- Nine pytest tests passed, including exact-point, number-range, unmatched-coordinate, complete-year selection, opportunity-profile, glossary-coverage and map-reconciliation cases.
- Ruff completed with no findings.
- The processed source rebuilt successfully with 73,141 of 74,562 analytics-ready permits mapped (98.1%).
- Streamlit's application test runner loaded the dashboard with zero exceptions.
- The default state rendered four KPI cards, five Plotly charts and three data tables.
- The default opportunity profile reconciled Melbourne, Docklands and North Melbourne activity against the 2024 and 2025 source records.
- The Melbourne suburb filter rendered four additional profile metrics and five priority permit records without application exceptions.
- A partial date range omitted year-on-year fields and displayed an explicit selected-period explanation.
- An address search with 56 permits but no matched coordinates displayed a map-specific empty state while preserving the other four charts.
- The running local server returned `ok` from its health endpoint and HTTP 200 for the page.

## Remaining verification limitation

Automated visual inspection in the in-app browser was unavailable because the desktop browser-control process failed to initialise. Component execution, data reconciliation, filter behaviour and server health were checked programmatically. Map tile appearance, hover readability and narrow-screen layout still require a brief human visual pass.
