# Statewide Expansion Validation

Validation date: 7 October 2026

## Scope

The deployed dashboard was changed from a City of Melbourne permit-family model to a statewide BPC permit-record model using the official 2024 and 2025 annual workbooks.

## Source reconciliation

| Reporting year | Raw permit records | Dashboard records | Official reported cost | Dashboard reported cost | Result |
|---|---:|---:|---:|---:|---|
| 2024 | 100,400 | 100,400 | $49,990,056,504 | $49,990,056,504 | Pass |
| 2025 | 100,710 | 100,710 | $57,750,334,113 | $57,750,334,113 | Pass |

The comparison uses `BASIS_Month_Y` and `Reported_Cost_of_works`, matching the regulator's calendar-year summary basis.

## Data-quality findings

- 2,638 records have a missing or invalid permit issue date. They remain in reporting-period analysis.
- 4,340 records have an issue year different from the BPC reporting year. This may reflect delayed reporting or corrections.
- 5,091 rows match on the available public analytical fields. They were retained because the source has no permit identifier.
- 16 records have zero or negative reported cost. They remain in counts but are excluded from positive-cost medians.
- Municipality is populated for all 201,110 records.
- All source municipality labels map to an official Vicmap boundary.

## Privacy and public-file boundary

The public runtime excludes builder suburb, state and postcode fields. The dashboard exports municipality aggregates rather than raw street-level rows. This is more conservative than reproducing all fields in the source workbook.

## Automated verification

```text
ruff check .
pytest
```

Result: 21 tests passed on 7 October 2026.

The automated checks cover dashboard startup, filters, municipality aggregation, year comparison, cost-band reaggregation, map-name alignment, runtime-file safety and official annual-total reconciliation.

## Remaining limits

- The current runtime covers two reporting years, not the complete historical archive.
- The source does not contain refused or not-granted applications.
- The statewide files do not provide a public permit identifier or point coordinates.
- BPC states that the information depends on submissions by building surveyors and may not be complete or accurate.
