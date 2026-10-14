# PermitPulse Victoria: Making eight years of permit data comparable

**Outcome:** An open-data portfolio prototype that converts inconsistent annual Victorian building-permit workbooks into a standardised analytical dataset and a [public interactive dashboard](https://permitpulse-melbourne-victoria.streamlit.app/).

## Business problem and target user

Victorian building-permit activity can support market scanning, project planning and local development analysis, but the regulator publishes separate annual workbooks whose structures are not fully consistent. Column and worksheet names change, some measures are unavailable in earlier years, location labels evolve, and similarly named cost fields have different business meanings. Combining the files without explicit rules could produce plausible-looking but misleading indicators.

PermitPulse was designed as a decision-support prototype for analysts and construction or property professionals who want to compare reported activity across years, regions and municipalities. It is not a regulatory register, project-lead service or construction forecast.

## My role and approach

My role centred on framing the business questions, defining and challenging metric rules, reviewing source limitations, testing outputs and iterating the dashboard requirements. I used AI-assisted development to support implementation and debugging, while keeping the data definitions, validation decisions and limitations explicit and reviewable.

## Standardising the eight-year dataset

The pipeline processes the official 2018–2025 Building and Plumbing Commission workbooks, covering 871,267 source records. It detects the relevant worksheet, maps changing source columns into a canonical schema, converts legacy Excel dates, standardises data types and records a checksum for every input file.

The canonical model supports consistent fields for reporting period, municipality, region, suburb, reported cost, nature of work, building use, new dwellings and demolitions. Historical Moreland records are normalised to Merri-bek so municipality comparisons remain continuous, while original source limitations are retained rather than silently filled.

## Business schema and rules

| Analytical decision | Business rule |
|---|---|
| Permit volume | Count source records, not claimed unique permits, because the public files have no permit identifier. |
| Reporting period | Use the BPC levy reporting month and year; retain permit issue date as a different concept. |
| Additive cost | Sum `Reported_Cost_of_works`; do not sum the project-total field because it can repeat across permit stages. |
| Typical cost | Calculate the median from positive reported costs; retain zero and negative values in record counts. |
| New dwellings | Use the comparable published field from 2020 onward; report 2018–2019 as unavailable. |
| Missing categories | Preserve unavailable building-use data in 2018 instead of substituting another field. |

These rules form a lightweight analytical contract: each dashboard metric has a defined source, calculation and interpretation boundary.

## Reconciliation and trustworthy indicators

The build process reconciles annual record counts and reported-cost totals back to each raw workbook. The 2024 and 2025 results also reconcile exactly to separate official regulator summary controls; earlier years were checked against their raw files but have not yet received the same independent-summary check.

Data-quality controls make uncertainty visible. For example, the validation identified 14,927 missing or invalid permit issue dates, 11,869 records where issue year differs from reporting year, and 16,972 duplicate-looking rows. These rows were not automatically deleted: reporting-period analysis can still use missing issue dates, timing differences may reflect delayed reporting or corrections, and duplicate-looking records cannot be safely deduplicated without a permit identifier.

## Coverage, decision boundary and outcome

The dashboard covers issued building-permit activity across Victoria and supports reporting-year, region, municipality, suburb, cost-range, nature-of-work and building-use analysis. Users can compare permit-record volume, estimated reported cost, new dwellings and demolitions, and view municipality-level geographic patterns.

It cannot measure refusal risk, approval probability, unique permit counts, exact address hotspots, realised expenditure, contractor performance, profitability, property prices or causal market drivers. Reported costs are nominal estimates, and the source depends on information submitted by building surveyors. These limits are presented in the dashboard and documentation rather than hidden behind the visualisations.

The demonstrated result is a publicly accessible prototype with a reproducible pipeline, documented metric definitions, privacy-conscious aggregate exports and automated checks. Real-world adoption and commercial impact have not been measured.

**Technology:** Python, pandas, DuckDB, Parquet, Streamlit, Plotly, pytest and Ruff. All application components use free or open-source tooling.

**Links:** [Live dashboard](https://permitpulse-melbourne-victoria.streamlit.app/) · [GitHub repository](https://github.com/matt9288/permitpulse-melbourne)
