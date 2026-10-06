# Phase 4 Validation — Detailed Cost Intelligence

## Decision supported

The dashboard now answers:

> How did permit volume and source-reported estimated cost change between the latest two complete calendar years within narrower project-cost ranges?

The existing broad estimated-cost bands remain unchanged for high-level filtering and distribution analysis. The new drill-down avoids forcing all ranges into one crowded chart.

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

- The user selects one positive broad cost range for detailed analysis.
- The chart switches between unique-permit count and total source-reported estimated cost.
- When two complete calendar years are available, grouped bars compare the latest year with the preceding year.
- The supporting table reports prior-year and current-year permit counts, permit-count change, total estimated costs, estimated-cost change and current-year median estimated cost.
- If the selected date range does not contain two complete years, the dashboard shows selected-period detail without a year-over-year claim.
- The detailed cost band is included in the record table and CSV export.

## Executed checks

- `pytest`: 13 tests passed.
- `ruff check .`: passed.
- Every positive broad band reconciled exactly to the sum of its detailed permit counts across the full analytical snapshot.
- The 2024 and 2025 permit counts and total estimated costs reconciled between the detailed tables and their filtered source populations for all five positive broad ranges.
- Streamlit application testing loaded six Plotly charts without exceptions.
- The default detailed range loaded as `$250k–$1m` with permit count selected.
- Changing the detailed range to `> $10m` and the measure to total estimated cost completed without exceptions; the detailed table reconciled to 276 permits in 2024 and 256 in 2025.
- Applying the `$1–$50k` broad sidebar filter restricted the detail selector to that compatible range without an exception.
- Restricting the date filter to calendar year 2025 switched to the selected-period table without a year-over-year claim and reconciled to 464 permits in the `$1–$50k` range.

## Responsible-use limits

- Estimated costs are source-reported, nominal values. They are not realised expenditure, approved budgets, contract value, revenue or final project cost.
- Total estimated cost can be dominated by a small number of very large permits.
- Permit issue year does not establish construction commencement or completion year.
- Percentage change is unavailable when the prior-year denominator is zero.
- Pixel-level browser inspection was not completed because the desktop browser-control service failed to initialise. Application execution, calculations, interactions and HTTP availability were checked programmatically.
