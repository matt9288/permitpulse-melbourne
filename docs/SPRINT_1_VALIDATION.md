# Sprint 1 Validation — Data Foundation

## Scope

This record verifies the initial PermitPulse ingestion, validation and analytical modelling pipeline against the City of Melbourne building-permits snapshot downloaded on 1 October 2026.

The build used an explicit analysis date of `2026-10-01`. The results below apply to this source snapshot and must not be hard-coded as expectations for later source versions.

## Source evidence

| Field | Value |
|---|---|
| Source rows | 184,858 |
| Source bytes | 37,506,244 |
| SHA-256 | `94b8e53e42e782bf177a6b75c2a1d97018536ac778374664ab0cd655c3400a6e` |
| Analysis date | 1 October 2026 |
| Latest non-future Building Permit issue date | 10 September 2026 |

## Reconciliation

| Output | Records | Interpretation |
|---|---:|---|
| Raw source | 184,858 | Mixed permit, certificate and address grain |
| Permit families | 74,601 | One row per observed Building Permit `council_ref` |
| Analytics-ready permits | 74,562 | Families passing high-severity and cost-conflict checks |
| Permit families requiring review | 39 | Retained in the family table but excluded from the analytics view |
| Certificate events | 154,443 | Deduplicated permit and certificate events |
| Permit addresses | 88,437 | Distinct council-reference and address pairs |
| Quarantine issues | 1,493 | Issue records; one source row may trigger more than one rule |

The `permit_families.council_ref` key was unique in the executed output.

## Material data-quality findings

| Finding | Evidence | Severity | Treatment |
|---|---:|---|---|
| Mixed source grain | 165,043 rows, or 89.281%, belong to repeated council references | Critical | Do not count raw rows as projects |
| Repeated estimated cost | Raw positive cost total is 6.2762 times the permit-family total | Critical | Aggregate only from the permit-family model |
| Missing parent permit | 45 certificate references have no observed Building Permit row | High | Retain the event; flag the broken parent link |
| Future issue dates | 17 raw rows are later than the analysis date | High | Preserve in quarantine; exclude affected Building Permit families from analytics |
| Missing issue dates | 47 raw rows have no usable issue date | High | Preserve in quarantine; exclude affected Building Permit families from analytics |
| Negative estimated costs | 4 raw rows have negative values | High | Preserve in quarantine; exclude affected Building Permit families from analytics |
| Recent volume collapse | Latest three complete months average 3.52% of the preceding 12-month average | High | Treat 2026 as incomplete or delayed, not a market downturn |
| Commence-by before issue date | 1,322 Building Permit rows | Medium | Retain and flag for review; no compliance inference |
| Completed-by before issue date | 100 Building Permit rows | Medium | Retain and flag for review; no compliance inference |
| Completed-by before commence-by | 3 Building Permit rows | Medium | Retain and flag for review |

Multiple permit numbers or issue dates within a council reference are retained. The full-run review showed these are common family structures and revisions, so they are not automatically treated as invalid. Conflicting estimated-cost values remain a review condition.

## Commands executed

```bash
.venv/bin/ruff check .
.venv/bin/pytest -q
.venv/bin/permitpulse build \
  --input ../outputs/portfolio_planning/permitpulse_discovery/data/building-permits.csv \
  --output-dir data/processed \
  --as-of-date 2026-10-01
```

## Verification results

- Ruff completed with no findings.
- Two pytest tests passed.
- The full build completed successfully.
- Two independent clean builds produced identical SHA-256 checksums for all six Parquet outputs.
- Raw and processed datasets are excluded from Git; only placeholder files are tracked.

## Limitations and next gate

- The live `refresh` command is implemented but this validation used the already downloaded source snapshot so that results remained reproducible.
- The pipeline records data-review signals; it does not establish construction status, delay or legal compliance.
- The application interface has not been started. The next gate is to build the Streamlit Opportunity Explorer from `analytic_permits.parquet` and keep the data-quality warnings visible.
