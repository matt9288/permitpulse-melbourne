# PermitPulse Melbourne

PermitPulse Melbourne is an open-data portfolio prototype that converts the City of Melbourne building-permits register into a reliable permit-family dataset for analysis and decision support.

The project is being developed in stages. Sprint 1 provides the data foundation: source fingerprinting, schema validation, data-quality checks, permit-family normalisation, quarantine records, DuckDB tables and Parquet exports.

## Business problem

The source register mixes building permits, final inspections, occupancy certificates and multiple addresses. Treating each row as an independent project materially overstates activity and estimated value.

PermitPulse separates those grains so later application features can support:

- permit opportunity exploration by address-derived hotspot, suburb, work type and cost band;
- transparent certificate-event timelines;
- review of missing or inconsistent source records; and
- visible source freshness and data-quality warnings.

It does **not** claim to identify construction delays, legal non-compliance, realised expenditure or the complete Greater Melbourne development pipeline.

## Data source

- Publisher: City of Melbourne
- Dataset: [Building Permits](https://data.melbourne.vic.gov.au/explore/dataset/building-permits/)
- Map coordinates: [Street addresses](https://data.melbourne.vic.gov.au/explore/dataset/street-addresses/)
- Licence: CC BY
- Geographic scope: City of Melbourne municipality, not metropolitan Melbourne

Raw source files are not committed to Git. The build records the input checksum, size, extraction time and analysis date.

## Technology

- Python and pandas for ingestion and validation
- DuckDB for the analytical model
- Parquet for compact application-ready outputs
- Streamlit and Plotly for the Opportunity Explorer
- pytest and Ruff for automated checks

All Sprint 1 dependencies are open-source and require no paid services.

For the hosted application, `requirements.txt` pins the tested runtime versions and installs the local `permitpulse` package.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

## Build from an existing source snapshot

```bash
permitpulse build \
  --input /path/to/building-permits.csv \
  --address-input /path/to/street-addresses.csv \
  --output-dir data/processed \
  --as-of-date 2026-10-01
```

The explicit `--as-of-date` makes future-date and freshness checks reproducible. If omitted, the local calendar date is used.

## Download the current open file and build

```bash
permitpulse refresh \
  --raw-path data/raw/building-permits.csv \
  --output-dir data/processed
```

This command requires internet access. It replaces only the configured raw snapshot after a successful download.

## Outputs

The build creates:

- `permitpulse.duckdb` — inspectable analytical database;
- `permit_families.parquet` — one record per observed building-permit reference;
- `analytic_permits.parquet` — permit families that pass high-severity checks;
- `certificate_events.parquet` — deduplicated permit and certificate events;
- `permit_addresses.parquet` — distinct addresses linked to permit references;
- `quarantine_records.parquet` — source rows and permit families requiring review;
- `data_quality_results.parquet` — data-quality results and reconciliation metrics; and
- `source_metadata.json` — source provenance and build summary.

## Verification

```bash
pytest
ruff check .
```

## Run the Opportunity Explorer

Build the processed data first, then run:

```bash
streamlit run app.py
```

The default dashboard period is 2018–2025 because the recent 2026 source partition appears incomplete. Filters apply consistently to the heat map, suburb opportunity profile, headline measures, charts, records table and CSV download. The profile compares the latest two complete calendar years inside the selected date range; when two complete years are unavailable, it shows selected-period measures without a growth claim.

The estimated-cost section reaggregates one chart between broad market ranges and the complete detailed breakdown. Users can compare permit count or total source-reported estimated cost for any two complete calendar years inside the active date range. The supporting table shows changes relative to the selected baseline year and the focus-year median estimated cost. An in-dashboard metric glossary documents each measure, formula or rule, and its main interpretation limitation.

The map does not use a paid geocoder. It joins permit addresses to the City of Melbourne's open street-address points. Exact street-number matches use official point locations; number ranges use the centroid of official address points within the range on the same street and suburb. Unmatched permits are not plotted.

For the 1 October 2026 discovery snapshot, the pipeline should reconcile 184,858 raw rows to 74,601 unique building-permit references. These are snapshot-specific integration checks, not permanent assumptions about future source files.

The executed Sprint 1 evidence is recorded in [docs/SPRINT_1_VALIDATION.md](docs/SPRINT_1_VALIDATION.md).
The Opportunity Explorer verification is recorded in [docs/PHASE_2_VALIDATION.md](docs/PHASE_2_VALIDATION.md).
The hotspot-map verification is recorded in [docs/PHASE_3_MAP_VALIDATION.md](docs/PHASE_3_MAP_VALIDATION.md).
The detailed cost-analysis verification is recorded in [docs/PHASE_4_COST_VALIDATION.md](docs/PHASE_4_COST_VALIDATION.md).

## Deployment

The repository is prepared for Streamlit Community Cloud using `app.py` as the entrypoint and Python 3.12. Only the three reviewed runtime data files are included; raw source downloads and build artefacts remain excluded. No cloud deployment has been created yet.

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the public-file boundary, deployment settings, verification checklist and refresh workflow.

## Current limitations

- Work categories currently use transparent keyword rules; a labelled and validated classifier is a later phase.
- Map points represent one primary address per permit family and do not show every parcel or address attached to a permit.
- Address-range centroids are derived representative locations, not surveyed parcel centroids.
- The free Carto basemap requires an internet connection in the viewer; no API key is required.
- Public deployment is a later phase.
- A record in the quarantine output is a data-review signal, not evidence of regulatory failure.
- Estimated costs are source-reported estimates and must not be treated as realised expenditure.
- Estimated-cost comparisons are nominal and are not adjusted for inflation or changing reporting practices.
- Recent source periods may be incomplete because the register depends on upstream submissions.
