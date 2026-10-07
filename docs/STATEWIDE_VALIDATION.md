# Statewide Expansion Validation

Validation date: 7 October 2026

## Scope

The statewide dashboard now combines the official 2018–2025 BPC annual workbooks into one permit-record model.

## Source reconciliation

| Reporting year | Dashboard records | Reported cost | Source-file control | Independent summary control |
|---|---:|---:|---|---|
| 2018 | 113,287 | $39,610,817,091 | Pass | Not independently checked |
| 2019 | 101,988 | $38,284,048,987 | Pass | Not independently checked |
| 2020 | 113,430 | $40,810,014,295 | Pass | Not independently checked |
| 2021 | 127,792 | $44,635,012,065 | Pass | Not independently checked |
| 2022 | 113,625 | $47,496,953,575 | Pass | Not independently checked |
| 2023 | 100,035 | $48,301,000,994 | Pass | Not independently checked |
| 2024 | 100,400 | $49,990,056,504 | Pass | Pass |
| 2025 | 100,710 | $57,750,334,113 | Pass | Pass |

The comparison uses `BASIS_Month_Y` and `Reported_Cost_of_works`. The 2024 and 2025 values reconcile exactly to the regulator's December 2025 calendar-year summary. Earlier years reconcile to their annual raw workbooks but were not independently checked against separate summary files in this run.

## Data-quality findings

- 14,927 records have a missing or invalid permit issue date. They remain in reporting-period analysis.
- 11,869 records have an issue year different from the BPC reporting year. This may reflect delayed reporting or corrections.
- 16,972 rows match on the available public analytical fields. They were retained because the source has no permit identifier.
- 1,718 records have zero or negative reported cost. They remain in counts but are excluded from positive-cost medians.
- Municipality is populated for all 871,267 records.
- Building use is unavailable for all 113,287 records in the 2018 source.
- A comparable new-dwellings field is unavailable for the 215,275 records in the 2018 and 2019 sources. A trial legacy derivation was rejected because it produced negative values.
- A further 39,677 records from 2020–2025 have a blank new-dwellings value even though those workbooks publish the field. Dashboard totals use the available values and show field coverage.
- Ninety historical Delatite records have no equivalent feature in the current Vicmap boundary file. The other 871,177 records map to a current boundary.
- Historical Moreland labels are normalised to Merri-bek for continuous municipality comparisons.

## Privacy and public-file boundary

The public runtime excludes builder fields, street names, exact permit dates and other unused record-level fields. The dashboard exports municipality aggregates rather than source rows. This is more conservative than reproducing all fields in the source workbooks.

## Automated verification

```text
ruff check .
pytest
```

Result: 25 tests passed on 7 October 2026.

The automated checks cover dashboard startup, filters, municipality aggregation, year comparison, cost-band reaggregation, map-name alignment, runtime-file safety, annual source controls and the 2024–2025 official-summary reconciliation.

## Remaining limits

- The current runtime starts in 2018 rather than using the complete 2009–2025 archive.
- The source does not contain refused or not-granted applications.
- The statewide files do not provide a public permit identifier or point coordinates.
- Building use is unavailable in 2018, and comparable new-dwelling analysis is unavailable for 2018–2019.
- BPC states that the information depends on submissions by building surveyors and may not be complete or accurate.
