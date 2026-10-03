# Phase 2 Validation — Opportunity Explorer

## Decision supported

The Opportunity Explorer helps a property analyst, construction supplier or project coordinator answer:

> Which City of Melbourne locations, work categories and estimated-cost bands contain permit activity worth investigating?

The dashboard uses the analytics-ready permit-family table. It does not count certificate or address rows as separate projects and does not display a total estimated construction value.

## Default view

The default period is 1 January 2018 to 31 December 2025. The incomplete 2026 period is available for inspection but is not included in the opening view.

| Measure | Default value |
|---|---:|
| Permit families | 21,437 |
| Median positive estimated cost | $285,000 |
| Suburbs represented | 14 |
| Share above $10 million | 12.97% |

The four headline values were independently reconciled between the dashboard calculation functions and DuckDB SQL.

## Views and controls

- Issue-date range filter
- Multi-select suburb filter
- Multi-select estimated-cost-band filter
- Multi-select rule-based work-category filter
- Literal text search across council reference, description and primary address
- Monthly permit-family trend
- Top-suburb comparison
- Rule-based work-category comparison
- Estimated-cost-band distribution
- Filtered permit-family records table
- Filtered CSV download
- Source metadata and data-quality warnings

Every control applies to the same population used by the KPI cards, four charts, records table and CSV export.

## Verification evidence

- Ruff completed with no findings.
- Four pytest tests passed.
- Python compilation completed for the application and dashboard module.
- Streamlit's application test runner loaded the app with zero exceptions.
- The default state rendered four KPI metrics, four Plotly charts and two data tables.
- Selecting `MELBOURNE` produced 11,615 permit families; resetting to all suburbs restored 21,437.
- Selecting a 2026 date range displayed the incomplete-partition warning.
- A search with no matches displayed an explicit empty state rather than zero-filled charts.
- The running local server returned `ok` from Streamlit's health endpoint.

## Remaining verification limitation

The in-app browser was opened, but automated visual inspection was unavailable because the local computer-use browser process failed to initialise. Component execution, filter behaviour and server health were checked programmatically; clipping, narrow-screen layout and hover presentation still require a human visual pass.

## Scope boundary

The current work category is a transparent keyword rule, not an AI model. It is labelled accordingly in the interface. The next phase should add location mapping and create a labelled description sample before training an explainable classifier.
