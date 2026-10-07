from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from permitpulse.dashboard import DETAILED_COST_BAND_ORDER, load_parquet
from permitpulse.pipeline import COST_BAND_ORDER
from permitpulse.statewide_dashboard import (
    StatewideFilters,
    apply_statewide_filters,
    category_summary,
    cost_comparison,
    cost_distribution,
    headline_metrics,
    metric_glossary,
    monthly_activity,
    municipality_map_summary,
    municipality_summary,
)

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"
REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"
PERMITS_PATH = DATA_DIR / "analytic_permits.parquet"
QUALITY_PATH = DATA_DIR / "data_quality_results.parquet"
METADATA_PATH = DATA_DIR / "source_metadata.json"
BOUNDARIES_PATH = REFERENCE_DIR / "victoria_lga_simplified.geojson"

PLOT_COLOUR = "#176B87"
ACCENT_COLOUR = "#C56A2D"


@st.cache_data(show_spinner=False)
def load_dashboard_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    permits = load_parquet(PERMITS_PATH)
    quality = load_parquet(QUALITY_PATH)
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    boundaries = json.loads(BOUNDARIES_PATH.read_text(encoding="utf-8"))
    return permits, quality, metadata, boundaries


def currency(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "Unavailable"
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:,.1f}bn"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:,.1f}m"
    if abs(value) >= 1_000:
        return f"${value / 1_000:,.0f}k"
    return f"${value:,.0f}"


st.set_page_config(page_title="PermitPulse Victoria", page_icon="🏗️", layout="wide")
st.title("PermitPulse Victoria")
st.caption(
    "Explore statewide building-permit activity reported to Victoria's Building and Plumbing "
    "Commission. Counts are source records, not deduplicated permits."
)

try:
    permits, quality, metadata, boundaries = load_dashboard_inputs()
except (FileNotFoundError, json.JSONDecodeError) as error:
    st.error(f"The statewide dashboard bundle is unavailable. Details: {error}")
    st.stop()

minimum_period = permits["report_month"].min().date()
maximum_period = (permits["report_month"].max() + pd.offsets.MonthEnd(0)).date()

st.sidebar.header("Filters")
selected_dates = st.sidebar.date_input(
    "BPC reporting period",
    value=(minimum_period, maximum_period),
    min_value=minimum_period,
    max_value=maximum_period,
    help=(
        "This uses the regulator's levy reporting period. Permit issue date is retained separately."
    ),
)
if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
    selected_start, selected_end = selected_dates
else:
    selected_start = selected_end = (
        selected_dates[0] if isinstance(selected_dates, tuple) else selected_dates
    )

region_options = sorted(permits["region"].dropna().unique().tolist())
selected_regions = st.sidebar.multiselect("Regions", region_options)
location_base = permits
if selected_regions:
    location_base = location_base.loc[location_base["region"].isin(selected_regions)]
municipality_options = sorted(location_base["municipality"].dropna().unique().tolist())
selected_municipalities = st.sidebar.multiselect(
    "Municipalities",
    municipality_options,
    help="Choose one municipality for a focused business profile or several for comparison.",
)
if selected_municipalities:
    location_base = location_base.loc[location_base["municipality"].isin(selected_municipalities)]
suburb_options = sorted(location_base["suburb"].dropna().unique().tolist())
selected_suburbs = st.sidebar.multiselect("Suburbs", suburb_options)
selected_cost_bands = st.sidebar.multiselect("Reported-cost bands", COST_BAND_ORDER)
selected_work = st.sidebar.multiselect(
    "Nature of work", sorted(permits["nature_of_work"].dropna().unique().tolist())
)
selected_building_uses = st.sidebar.multiselect(
    "Building use", sorted(permits["building_use"].dropna().unique().tolist())
)
text_query = st.sidebar.text_input(
    "Search location or category", placeholder="e.g. Geelong or demolition"
)

filters = StatewideFilters(
    start_date=selected_start,
    end_date=selected_end,
    regions=tuple(selected_regions),
    municipalities=tuple(selected_municipalities),
    suburbs=tuple(selected_suburbs),
    cost_bands=tuple(selected_cost_bands),
    nature_of_work=tuple(selected_work),
    building_uses=tuple(selected_building_uses),
    text_query=text_query,
)
filtered = apply_statewide_filters(permits, filters)
if filtered.empty:
    st.info(
        "No permit records match the current filters. Broaden the reporting period or "
        "clear a filter."
    )
    st.stop()

metrics = headline_metrics(filtered)
kpi_columns = st.columns(5)
kpi_columns[0].metric("Permit records", f"{metrics['records']:,}")
kpi_columns[1].metric("Total reported cost", currency(metrics["reported_cost"]))
kpi_columns[2].metric("Median positive cost", currency(metrics["median_positive_cost"]))
kpi_columns[3].metric("Municipalities", f"{metrics['municipalities']:,}")
kpi_columns[4].metric(
    "New dwellings",
    (f"{metrics['new_dwellings']:,}" if metrics["new_dwellings"] is not None else "Unavailable"),
    help=(
        f"Comparable source field coverage: {metrics['new_dwellings_coverage']:.1%} of "
        "filtered records. The field is unavailable for 2018–2019."
    ),
)

st.subheader("Statewide permit hotspots")
map_measure = st.radio(
    "Map measure", ["Permit records", "Reported cost", "New dwellings"], horizontal=True
)
map_columns = {
    "Permit records": ("records", "Permit records"),
    "Reported cost": ("reported_cost", "Reported cost"),
    "New dwellings": ("new_dwellings", "New dwellings"),
}
value_column, value_label = map_columns[map_measure]
map_data = municipality_map_summary(filtered)
boundary_names = {feature["properties"]["lga_name"] for feature in boundaries.get("features", [])}
map_data["is_mapped"] = map_data["municipality_map_name"].isin(boundary_names)
mapped = map_data.loc[map_data["is_mapped"]].copy()
if mapped[value_column].notna().any():
    map_figure = px.choropleth_map(
        mapped,
        geojson=boundaries,
        locations="municipality_map_name",
        featureidkey="properties.lga_name",
        color=value_column,
        hover_name="municipality",
        hover_data={
            "records": ":,",
            "reported_cost": ":$,.0f",
            "new_dwellings": ":,",
            "municipality_map_name": False,
        },
        labels={
            "records": "Permit records",
            "reported_cost": "Reported cost",
            "new_dwellings": "New dwellings",
        },
        color_continuous_scale="YlOrRd",
        map_style="carto-positron",
        center={"lat": -36.9, "lon": 144.7},
        zoom=4.7,
        opacity=0.75,
        height=650,
        title=f"Municipality intensity by {value_label.lower()}",
    )
    map_figure.update_layout(margin=dict(l=0, r=0, t=55, b=0))
    st.plotly_chart(map_figure, width="stretch")
else:
    st.info(f"{value_label} data is unavailable for the selected reporting period.")
mapped_records = int(mapped["records"].sum())
st.caption(
    f"The map covers {mapped_records:,} of {len(filtered):,} filtered records "
    f"({mapped_records / len(filtered):.1%}). It uses official Vicmap municipality boundaries; "
    "the statewide source does not publish address coordinates."
)

available_years = sorted(
    filtered["report_year"].dropna().astype(int).unique().tolist(), reverse=True
)
st.subheader("Municipality business profile")
if len(available_years) >= 2:
    profile_controls = st.columns(2)
    profile_year = profile_controls[0].selectbox(
        "Profile year", available_years, key="profile_year"
    )
    profile_baselines = [year for year in available_years if year != profile_year]
    profile_baseline = profile_controls[1].selectbox(
        "Profile baseline", profile_baselines, key="profile_baseline"
    )
else:
    profile_year = available_years[0]
    profile_baseline = None

municipalities = municipality_summary(filtered, profile_year, profile_baseline)
if len(selected_municipalities) == 1 and not municipalities.empty:
    profile = municipalities.iloc[0]
    profile_columns = st.columns(5)
    activity_delta = None
    if profile_baseline and pd.notna(profile["record_change"]):
        activity_delta = f"{profile['record_change']:+.1%} vs {profile_baseline}"
    profile_columns[0].metric(
        f"{profile_year} permit records", f"{int(profile['focus_records']):,}", activity_delta
    )
    profile_columns[1].metric("Total reported cost", currency(profile["total_reported_cost"]))
    profile_columns[2].metric("Median reported cost", currency(profile["median_reported_cost"]))
    profile_columns[3].metric(
        "New dwellings",
        (
            f"{int(profile['new_dwellings']):,}"
            if pd.notna(profile["new_dwellings"])
            else "Unavailable"
        ),
    )
    profile_columns[4].metric(
        "High-value share", f"{profile['high_value_share']:.1%}", help="Reported cost above $10m"
    )
    municipality_period = filtered.loc[filtered["report_year"] == profile_year]
    mix_left, mix_right = st.columns(2)
    with mix_left:
        st.markdown("#### Nature-of-work mix")
        st.dataframe(
            category_summary(municipality_period, "nature_of_work"),
            hide_index=True,
            width="stretch",
        )
    with mix_right:
        st.markdown("#### Building-use mix")
        st.dataframe(
            category_summary(municipality_period, "building_use"),
            hide_index=True,
            width="stretch",
        )
else:
    st.caption(
        "Compare municipalities by volume, estimated project value and dwelling impact. "
        "Select one municipality in the sidebar for its category mix."
    )
    st.dataframe(
        municipalities.head(25),
        hide_index=True,
        width="stretch",
        column_config={
            "municipality": "Municipality",
            "focus_records": st.column_config.NumberColumn(f"{profile_year} records", format="%d"),
            "baseline_records": st.column_config.NumberColumn(
                f"{profile_baseline} records" if profile_baseline else "Baseline records",
                format="%d",
            ),
            "record_change": st.column_config.NumberColumn("Record change", format="percent"),
            "total_reported_cost": st.column_config.NumberColumn(
                "Total reported cost", format="$%.0f"
            ),
            "median_reported_cost": st.column_config.NumberColumn(
                "Median reported cost", format="$%.0f"
            ),
            "high_value_records": st.column_config.NumberColumn("Records above $10m", format="%d"),
            "high_value_share": st.column_config.NumberColumn("High-value share", format="percent"),
            "new_dwellings": st.column_config.NumberColumn("New dwellings", format="%d"),
            "dwellings_demolished": st.column_config.NumberColumn(
                "Dwellings demolished", format="%d"
            ),
        },
    )

trend = monthly_activity(filtered)
trend_measure = st.radio("Trend measure", ["Permit records", "Reported cost"], horizontal=True)
trend_column = "records" if trend_measure == "Permit records" else "reported_cost"
trend_figure = px.line(
    trend,
    x="report_month",
    y=trend_column,
    markers=True,
    title=f"{trend_measure} by BPC reporting month",
    labels={"report_month": "Reporting month", trend_column: trend_measure},
    color_discrete_sequence=[PLOT_COLOUR],
    template="plotly_white",
)
trend_figure.update_layout(hovermode="x unified", margin=dict(l=20, r=20, t=55, b=20))
trend_figure.update_yaxes(rangemode="tozero")
if trend_column == "reported_cost":
    trend_figure.update_yaxes(tickprefix="$", separatethousands=True)
st.plotly_chart(trend_figure, width="stretch")

left, middle, right = st.columns(3)
with left:
    suburbs = category_summary(filtered, "suburb", limit=12).sort_values("records")
    figure = px.bar(
        suburbs,
        x="records",
        y="suburb",
        orientation="h",
        title="Top suburbs by permit records",
        labels={"suburb": "Suburb", "records": "Permit records"},
        color_discrete_sequence=[ACCENT_COLOUR],
        template="plotly_white",
    )
    st.plotly_chart(figure, width="stretch")
with middle:
    work = category_summary(filtered, "nature_of_work").sort_values("records")
    figure = px.bar(
        work,
        x="records",
        y="nature_of_work",
        orientation="h",
        title="Official nature of work",
        labels={"nature_of_work": "Nature of work", "records": "Permit records"},
        color_discrete_sequence=[PLOT_COLOUR],
        template="plotly_white",
    )
    st.plotly_chart(figure, width="stretch")
with right:
    uses = category_summary(filtered, "building_use").sort_values("records")
    figure = px.bar(
        uses,
        x="records",
        y="building_use",
        orientation="h",
        title="Building use",
        labels={"building_use": "Building use", "records": "Permit records"},
        color_discrete_sequence=[ACCENT_COLOUR],
        template="plotly_white",
    )
    st.plotly_chart(figure, width="stretch")

st.subheader("Reported-cost analysis")
st.caption(
    "Change the aggregation directly in this view. Year comparison uses BPC reporting year "
    "so the totals reconcile to the regulator's annual summary."
)
aggregation_control, measure_control = st.columns(2)
cost_aggregation = aggregation_control.radio(
    "Cost range aggregation", ["Broad ranges", "Detailed ranges"], horizontal=True
)
comparison_measure = measure_control.radio(
    "Comparison measure", ["Permit records", "Total reported cost"], horizontal=True
)
detailed = cost_aggregation == "Detailed ranges"
cost_order = DETAILED_COST_BAND_ORDER if detailed else COST_BAND_ORDER

if len(available_years) >= 2:
    cost_controls = st.columns(2)
    focus_year = cost_controls[0].selectbox("Focus year", available_years, key="cost_focus_year")
    baseline_options = [year for year in available_years if year != focus_year]
    baseline_year = cost_controls[1].selectbox(
        "Baseline year", baseline_options, key="cost_baseline_year"
    )
    comparison = cost_comparison(filtered, focus_year, baseline_year, detailed)
    comparison = comparison.loc[
        (comparison["focus_records"] > 0) | (comparison["baseline_records"] > 0)
    ].copy()
    if comparison_measure == "Permit records":
        focus_column, baseline_column, value_label = (
            "focus_records",
            "baseline_records",
            "Permit records",
        )
    else:
        focus_column, baseline_column, value_label = (
            "focus_total_reported_cost",
            "baseline_total_reported_cost",
            "Total reported cost",
        )
    chart_rows = pd.concat(
        [
            comparison[["cost_range", baseline_column]]
            .rename(columns={baseline_column: "value"})
            .assign(report_year=str(baseline_year)),
            comparison[["cost_range", focus_column]]
            .rename(columns={focus_column: "value"})
            .assign(report_year=str(focus_year)),
        ],
        ignore_index=True,
    )
    cost_figure = px.bar(
        chart_rows,
        x="cost_range",
        y="value",
        color="report_year",
        barmode="group",
        title=f"{value_label} by cost range — {focus_year} versus {baseline_year}",
        labels={
            "cost_range": "Reported-cost range",
            "value": value_label,
            "report_year": "Reporting year",
        },
        category_orders={
            "cost_range": cost_order,
            "report_year": [str(baseline_year), str(focus_year)],
        },
        color_discrete_sequence=["#9AAFB8", ACCENT_COLOUR],
        template="plotly_white",
        height=560 if detailed else 460,
    )
    cost_figure.update_layout(margin=dict(l=20, r=20, t=70, b=80))
    cost_figure.update_xaxes(tickangle=-35 if detailed else 0)
    if comparison_measure == "Total reported cost":
        cost_figure.update_yaxes(tickprefix="$", separatethousands=True)
    st.plotly_chart(cost_figure, width="stretch")
    st.dataframe(
        comparison,
        hide_index=True,
        width="stretch",
        column_config={
            "cost_range": "Reported-cost range",
            "focus_records": st.column_config.NumberColumn(f"{focus_year} records", format="%d"),
            "baseline_records": st.column_config.NumberColumn(
                f"{baseline_year} records", format="%d"
            ),
            "record_change": st.column_config.NumberColumn("Record change", format="percent"),
            "focus_total_reported_cost": st.column_config.NumberColumn(
                f"{focus_year} total cost", format="$%.0f"
            ),
            "baseline_total_reported_cost": st.column_config.NumberColumn(
                f"{baseline_year} total cost", format="$%.0f"
            ),
            "reported_cost_change": st.column_config.NumberColumn("Cost change", format="percent"),
        },
    )
else:
    distribution = cost_distribution(filtered, detailed)
    distribution = distribution.loc[distribution["records"] > 0]
    value_column = "records" if comparison_measure == "Permit records" else "total_reported_cost"
    cost_figure = px.bar(
        distribution,
        x="cost_range",
        y=value_column,
        title=f"{comparison_measure} by reported-cost range",
        category_orders={"cost_range": cost_order},
        color_discrete_sequence=[ACCENT_COLOUR],
        template="plotly_white",
    )
    st.plotly_chart(cost_figure, width="stretch")

st.subheader("Download aggregated results")
st.download_button(
    "Download municipality summary",
    data=municipalities.to_csv(index=False).encode("utf-8"),
    file_name="permitpulse_victoria_municipality_summary.csv",
    mime="text/csv",
)
st.caption(
    "The public dashboard exports aggregates rather than raw street-level source rows. This "
    "keeps the portfolio demo focused on business analysis and reduces privacy risk."
)

with st.expander("Metric definitions and responsible use"):
    st.dataframe(metric_glossary(), hide_index=True, width="stretch")

with st.expander("Source and data quality"):
    summary = metadata.get("summary", {})
    st.markdown(
        f"**Source:** {metadata.get('source_dataset', 'Unavailable')} — Building and "
        "Plumbing Commission  \n"
        f"**Licence:** {metadata.get('licence', 'Unavailable')}  \n"
        f"**Snapshot analysis date:** {metadata.get('as_of_date', 'Unavailable')}  \n"
        f"**Reporting years:** {', '.join(map(str, summary.get('report_years', [])))}  \n"
        f"**Permit records:** {summary.get('records', 0):,}  \n"
        f"**Municipalities:** {summary.get('municipalities', 0):,}  \n"
        f"**Map source:** {metadata.get('geospatial_source', {}).get('dataset', 'Unavailable')}"
    )
    st.caption(metadata.get("data_model", ""))
    st.warning(
        "This dataset does not include refused or not-granted applications. It cannot be used "
        "to estimate refusal risk without a separate authoritative open dataset."
    )
    quality_display = quality.copy()
    quality_display["affected_rate"] = quality_display["affected_rate"].map(
        lambda value: f"{value:.2%}" if pd.notna(value) else ""
    )
    st.dataframe(quality_display, hide_index=True, width="stretch")
