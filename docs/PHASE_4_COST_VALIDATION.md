# Phase 4 Validation — Detailed Cost Intelligence

## Decision supported

The dashboard now answers:

> How did permit volume and source-reported estimated cost differ between any two complete calendar years at either a broad or detailed cost-range level?

The existing broad estimated-cost bands remain unchanged for filtering. The cost chart now reaggregates directly between the broad view and the complete detailed breakdown, so users do not need to select one broad range from a separate drop-down.

## Detailed ranges

| Broad range | Detailed ranges |
| --- | --- |
| $1–$50k | $1–$10k; $10k–$25k; $25k–$50k |
| $50k–$250k | $50k–$100k; $100k–$150k; $150k–$200k; $200k–$250k |
| $250k–$1m | $250k–$500k; $500k–$750k; $750k–$1m |
| $1m–$10m | $1m–$2.5m; $2.5m–$5m; $5m–$7.5m; $7.5m–$10m |
| Above $10m | $10m–$25m; $25m–$50m; $50m–$100m; above $100m |

Non-positive and missing costs remain data-quality categories and are not subdivided.

## Interaction and metric behaviour

- The user switches the same chart between broad and detailed cost ranges.
- The chart switches between unique-permit count and total source-reported estimated cost.
- When at least two complete calendar years are available, the focus-year and baseline-year selectors allow any two distinct years inside the active date range.
- The supporting table reports baseline-year and focus-year permit counts, permit-count change, total estimated costs, estimated-cost change and focus-year median estimated cost.
- If the selected date range does not contain two complete years, the dashboard shows selected-period detail without a year-over-year claim.
- Non-positive and missing costs remain visible in the detailed aggregation, so the detailed and broad permit totals reconcile.
- The detailed cost band is included in the record table and CSV export.

## Executed checks

- `pytest`: 16 tests passed.
- `ruff check .`: passed.
- Broad and detailed aggregations reconciled to the same permit total, including the non-positive and missing-cost categories.
- Streamlit application testing loaded five Plotly charts without exceptions; the cost analysis now uses one chart instead of separate broad and detailed charts.
- Changing the cost chart to the detailed aggregation, selecting 2023 as the focus year and 2021 as the baseline, and switching to total estimated cost completed without exceptions.
- The selectable-year helper returned every complete year from 2018 through 2025 for the default dashboard period.
- Restricting the date range to calendar year 2025 removed the year selectors and showed a selected-period distribution without a comparison claim.

## Responsible-use limits

- Estimated costs are source-reported, nominal values. They are not realised expenditure, approved budgets, contract value, revenue or final project cost.
- Total estimated cost can be dominated by a small number of very large permits.
- Permit issue year does not establish construction commencement or completion year.
- Percentage change is unavailable when the prior-year denominator is zero.
- Pixel-level browser inspection was not completed because the desktop browser-control service failed to initialise. Application execution, calculations, interactions and HTTP availability were checked programmatically.
