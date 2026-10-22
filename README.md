# PermitPulse Victoria

PermitPulse Victoria is an open-data portfolio prototype for exploring statewide building-permit activity. It converts annual Building and Plumbing Commission (BPC) workbooks into a consistent analytical dataset and an interactive Streamlit dashboard.

[Open the live PermitPulse Victoria dashboard](https://permitpulse-melbourne-victoria.streamlit.app/)

Project documentation:

- [Dashboard user guide](docs/DASHBOARD_USER_GUIDE.md)
- [Portfolio case study](docs/PERMITPULSE_CASE_STUDY.md)
- [Statewide validation](docs/STATEWIDE_VALIDATION.md)
- [Deployment guide](docs/DEPLOYMENT.md)

The current public snapshot covers the 2018–2025 BPC reporting years. It contains 871,267 source records across 87 comparable municipality and alpine-resort groups.

## Business problem

Building-permit activity is useful for market scanning, project planning and local development analysis, but the published annual files are difficult to compare directly. Their column names drift between years, costs can be misinterpreted, and the statewide files do not publish coordinates or a permit identifier.

PermitPulse provides:

- statewide municipality, region and suburb filtering;
- a municipality hotspot map using official Vicmap boundaries;
- year-to-year comparisons of permit-record volume and reported cost;
- broad and detailed cost ranges selectable in the chart;
- official nature-of-work and building-use breakdowns;
- reported new-dwelling and demolition measures;
- data-quality checks and official annual-total reconciliation;
- an aggregate-only dashboard guide with optional Groq explanations and a free fallback; and
- privacy-conscious aggregate CSV export.

This is a decision-support prototype, not a regulatory register, project-lead service or construction forecast.

## Ask PermitPulse AI guide

Select **💬 Ask PermitPulse** at the top of the dashboard sidebar to open the guide from any
view. It answers questions using the active filters and the dashboard's aggregate results, so users
can ask for help without leaving their current analysis.

Useful questions include:

- `Summarise the current filters.`
- `Compare 2025 with 2024 for permit-record volume and total reported cost.`
- `Which view should I use to compare municipalities?`
- `What does reported cost mean?`
- `Can this dataset measure permit rejection risk?`

The assistant combines two modes:

- **Groq-enhanced answers** use `openai/gpt-oss-20b` for natural-language explanations. The public
  prototype allows up to five Groq questions per browser session.
- **Built-in guidance** answers supported questions when Groq is unavailable, not configured or the
  session limit has been reached.

### AI chatbot technology stack

| Layer | Technology | Role in the assistant |
| --- | --- | --- |
| User interface | Streamlit `st.dialog`, `st.chat_input` and `st.chat_message` | Opens the assistant from the sidebar and displays the conversation without leaving the dashboard. |
| Analytical context | Python and pandas | Converts the active dashboard filters into a small set of aggregate metrics, annual summaries and category breakdowns. |
| Language model | Groq API with `openai/gpt-oss-20b` | Produces natural-language explanations from the supplied aggregate context. |
| API integration | Python standard-library `urllib` | Sends the HTTPS request directly to Groq, avoiding an additional SDK dependency. |
| Fallback | Deterministic Python responses | Keeps core metric, source and navigation guidance available when Groq cannot be used. |
| Guardrails | Python request checks and constrained model instructions | Blocks credential requests and unsupported questions such as rejection risk, forecasts and exact-address analysis. |
| Session control | Streamlit Session State | Retains the conversation, resets it when filters change and limits Groq use to five questions per browser session. |
| Secrets | Streamlit Secrets or the `GROQ_API_KEY` environment variable | Keeps the API key out of source control and the browser. |
| Testing | pytest with mocked Groq responses | Checks aggregate-only context, refusal behaviour, fallback handling and API-error messages without making live model calls. |
| Hosting | Streamlit Community Cloud | Runs the public dashboard and reads the deployment secret. |

The request flow is:

`active filters → pandas aggregates → compact JSON context → guardrail check → Groq or built-in fallback → Streamlit dialog`

This is deliberately a lightweight implementation. It does not use LangChain, an agent framework,
a vector database or retrieval-augmented generation because the assistant answers from the
dashboard's current structured aggregates rather than a separate document library.

Only aggregate summaries for the current filter selection are sent to Groq. Raw permit rows, record
identifiers and the full Parquet dataset are not sent. Guardrails prevent disclosure of credentials
or hidden configuration and reject questions the source cannot support, including refusal risk,
forecasts, realised costs, exact-address analysis and property prices.

This is a guided analytical interface, not a general-purpose chatbot. Its answers can still be
incorrect and should be checked against the dashboard charts, metric definitions and source notes.

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
- Building use is unavailable in the 2018 workbook. The dashboard preserves that gap rather than substituting another field.
- New dwellings use the published field from 2020 onward. The legacy 2018–2019 fields are not directly comparable, so those years are shown as unavailable.

## Technology

- Python and pandas for ingestion and validation
- `python-calamine` for free XLSB reading
- DuckDB and Parquet for compact analytical storage
- Streamlit and Plotly for the dashboard
- Groq `openai/gpt-oss-20b` for optional natural-language explanations
- pytest and Ruff for automated checks

The dashboard and built-in guide require no paid API or service. Groq enhancement is optional and
uses the provider's Free Plan within its current request limits. Free-tier availability and limits
can change; when Groq is unavailable, the built-in guide remains active.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

### Optional Groq assistant

The assistant works without an API key in built-in guide mode. To add free-tier natural-language
answers, create a Groq API key and copy the example secrets file:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Replace the placeholder value in `.streamlit/secrets.toml`. The real secrets file is ignored by Git
and must never be committed. The public deployment key belongs in Streamlit Community Cloud's
Secrets settings as:

```toml
GROQ_API_KEY = "your-key"
```

The application sends only aggregate summaries for the active filters. It does not send raw permit
rows, record identifiers or the full Parquet dataset. It permits at most five Groq questions per
browser session and falls back to deterministic guidance after that limit or when the API fails.

## Build the statewide snapshot

Download the annual BPC XLSB files through the official DataVic page, then run:

```bash
permitpulse build-statewide \
  --input /path/to/VBA-DataVic-Building-Permits-2018.xlsb \
  --input /path/to/VBA-DataVic-Building-Permits-2019.xlsb \
  --input /path/to/VBA-DataVic-Building-Permits-2020.xlsb \
  --input /path/to/VBA-DataVic-Building-Permits-2021-Dec.xlsb \
  --input /path/to/December-2022-Raw-data.xlsb \
  --input /path/to/20240067-Raw-Data-December-2023.xlsb \
  --input /path/to/VBA-DataVic-Building-Permits-2024-December.xlsb \
  --input /path/to/20260079-Rawdata-December-2025.xlsb \
  --output-dir data/processed \
  --as-of-date 2026-10-07
```

Repeat `--input` for each annual workbook. The pipeline detects the data sheet, handles known schema differences, converts legacy Excel date serials, validates required fields and records file checksums.

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

- Building-use analysis cannot compare 2018 with later years because the 2018 workbook does not publish that field.
- New-dwelling analysis is unavailable for 2018–2019 because the legacy before/after fields do not reconcile safely to the later definition.
- New-dwelling values are also blank for some 2020–2025 records; the dashboard reports coverage rather than treating blanks as zero.
- No permit ID means the dashboard cannot prove permit uniqueness or safely deduplicate duplicate-looking rows.
- No refusal data means the dashboard cannot measure approval probability or refusal risk.
- Municipality shading can hide within-LGA variation and should not be treated as an address hotspot.
- Ninety records use the ceased Delatite municipality label and cannot be placed on the current Vicmap boundary layer.
- Historical Moreland records are grouped under Merri-bek so year comparisons remain continuous across the council rename.
- Annual values are nominal and not adjusted for inflation or reporting-practice changes.
- Data quality depends on information submitted by building surveyors to the regulator.
- The free Carto basemap requires an internet connection in the viewer; no API key is required.
- Groq's free tier is quota-limited and not guaranteed to remain free. AI answers can still be
  incorrect, so they are constrained to aggregate context and should be checked against the charts.
