# PermitPulse Victoria

PermitPulse Victoria is an open-data portfolio prototype for exploring statewide building-permit activity. It converts annual Building and Plumbing Commission (BPC) workbooks into a consistent analytical dataset and an interactive Streamlit dashboard.

The current public snapshot covers the 2024 and 2025 BPC reporting years. It contains 201,110 source records across 83 local-government and alpine-resort reporting areas.

## Business problem

Building-permit activity is useful for market scanning, project planning and local development analysis, but the published annual files are difficult to compare directly. Their column names drift between years, costs can be misinterpreted, and the statewide files do not publish coordinates or a permit identifier.

PermitPulse provides:

- statewide municipality, region and suburb filtering;
- a municipality hotspot map using official Vicmap boundaries;
- year-to-year comparisons of permit-record volume and reported cost;
- broad and detailed cost ranges selectable in the chart;
- official nature-of-work and building-use breakdowns;
- reported new-dwelling and demolition measures;
- data-quality checks and official annual-total reconciliation; and
- privacy-conscious aggregate CSV export.

This is a decision-support prototype, not a regulatory register, project-lead service or construction forecast.

## Data sources

- Publisher: Building and Plumbing Commission, formerly the Victorian Building Authority
- Permit data: [Building Permit Activity Data](https://discover.data.vic.gov.au/dataset/building-permit-activity-data)
- Data notes and annual files: [BPC research, reports and data](https://www.bpc.vic.gov.au/about-bpc/research-reports-and-data/data)
- Map boundaries: [Vicmap Admin REST API](https://discover.data.vic.gov.au/dataset/vicmap-admin-rest-api)
- Licence: Creative Commons Attribution 4.0

Raw workbooks are not committed. The repository includes only the processed public dashboard bundle and a simplified copy of the official municipality boundaries.

## Critical interpretation rules

- A dashboard count is a **permit record**, not a unique permit. The public annual files do not include a permit identifier, so similar-looking rows are retained rather than guessed away.
- The primary time field is the BPC levy reporting month and year. Permit issue date is retained separately and may fall outside that period.
- `Reported_Cost_of_works` is used for additive cost analysis. `Total_Estimated_Cost_of_Works__c` can repeat a whole-project value across stages and is not summed.
- Reported cost is an estimate, not realised expenditure, contract value, revenue or current market value.
- The source covers issued permit activity. It does not contain refused or not-granted applications.
- The statewide source has street names but no street numbers or coordinates. The map is therefore aggregated to official municipality boundaries.

## Technology

- Python and pandas for ingestion and validation
- `python-calamine` for free XLSB reading
- DuckDB and Parquet for compact analytical storage
- Streamlit and Plotly for the dashboard
- pytest and Ruff for automated checks

All application components are open-source and require no paid API or service.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

## Build the statewide snapshot

Download the annual BPC XLSB files through the official DataVic page, then run:

```bash
permitpulse build-statewide \
  --input /path/to/VBA-DataVic-Building-Permits-2024-December.xlsb \
  --input /path/to/20260079-Rawdata-December-2025.xlsb \
  --output-dir data/processed \
  --as-of-date 2026-10-07
```

Repeat `--input` for each annual workbook. The pipeline detects the data sheet, handles the known 2024/2025 street-column schema difference, validates required fields and records file checksums.

The earlier City of Melbourne build commands remain in the codebase for reproducibility of the first project phase, but the deployed application uses the statewide build.

## Runtime outputs

- `data/processed/analytic_permits.parquet` — public-safe analytical source records;
- `data/processed/data_quality_results.parquet` — quality and reconciliation checks;
- `data/processed/source_metadata.json` — provenance, scope and limitations; and
- `data/reference/victoria_lga_simplified.geojson` — simplified official LGA boundaries.

Builder location fields from the raw source are not included in the public runtime bundle. The dashboard also avoids raw street-level export.

## Run and verify

```bash
ruff check .
pytest
streamlit run app.py
```

The current validation results are documented in [docs/STATEWIDE_VALIDATION.md](docs/STATEWIDE_VALIDATION.md). Deployment guidance is in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Current limitations

- Only 2024 and 2025 are in the current statewide runtime snapshot. The pipeline supports additional annual workbooks, but earlier years have not yet been loaded and reconciled.
- No permit ID means the dashboard cannot prove permit uniqueness or safely deduplicate duplicate-looking rows.
- No refusal data means the dashboard cannot measure approval probability or refusal risk.
- Municipality shading can hide within-LGA variation and should not be treated as an address hotspot.
- Annual values are nominal and not adjusted for inflation or reporting-practice changes.
- Data quality depends on information submitted by building surveyors to the regulator.
- The free Carto basemap requires an internet connection in the viewer; no API key is required.
