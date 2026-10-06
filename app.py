from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from permitpulse.dashboard import (
    DETAILED_COST_BANDS,
    DashboardFilters,
    apply_filters,
    complete_year_pair,
    cost_band_counts,
    detailed_cost_band_values,
    detailed_cost_comparison,
    detailed_cost_summary,
    headline_metrics,
    load_parquet,
    metric_glossary,
    monthly_activity,
    opportunity_benchmarks,
    permit_map_points,
    priority_permits,
    suburb_counts,
    suburb_opportunity_summary,
    work_category_counts,
)
from permitpulse.pipeline import COST_BAND_ORDER, WORK_CATEGORY_ORDER

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"
PERMITS_PATH = DATA_DIR / "analytic_permits.parquet"
QUALITY_PATH = DATA_DIR / "data_quality_results.parquet"
METADATA_PATH = DATA_DIR / "source_metadata.json"

PLOT_COLOUR = "#176B87"
ACCENT_COLOUR = "#C56A2D"


@st.cache_data(show_spinner=False)
def load_dashboard_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    permits = load_parquet(PERMITS_PATH)
    quality = load_parquet(QUALITY_PATH)
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    return permits, quality, metadata


def currency(value: float | None) -> str:
    if value is None:
        return "Unavailable"
    if value >= 1_000_000:
        return f"${value / 1_000_000:,.1f}m"
    if value >= 1_000:
        return f"${value / 1_000:,.0f}k"
    return f"${value:,.0f}"


st.set_page_config(page_title="PermitPulse Melbourne", page_icon="🏗️", layout="wide")
st.title("PermitPulse Melbourne")
st.caption(
    "Explore City of Melbourne building-permit activity using one record per council "
    "permit reference."
)

try:
    permits, quality, metadata = load_dashboard_inputs()
except (FileNotFoundError, json.JSONDecodeError) as error:
    st.error(
        f"The processed data is unavailable. Run the PermitPulse build first. Details: {error}"
    )
    st.stop()

valid_dates = permits["permit_issue_date"].dropna()
minimum_date = valid_dates.min().date()
maximum_date = valid_dates.max().date()
default_start = max(minimum_date, date(2018, 1, 1))
default_end = min(maximum_date, date(2025, 12, 31))

st.sidebar.header("Filters")
selected_dates = st.sidebar.date_input(
    "Permit issue date",
    value=(default_start, default_end),
    min_value=minimum_date,
    max_value=maximum_date,
)
if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
    selected_start, selected_end = selected_dates
else:
    selected_start = selected_end = (
        selected_dates[0] if isinstance(selected_dates, tuple) else selected_dates
    )

suburb_options = sorted(permits["suburb"].dropna().unique().tolist())
selected_suburbs = st.sidebar.multiselect(
    "Suburbs",
    suburb_options,
    help="Choose one suburb for a focused view, several for comparison, or leave empty for all.",
)
st.sidebar.caption("The suburb selection updates the map, metrics, charts and records.")
selected_cost_bands = st.sidebar.multiselect("Estimated-cost bands", COST_BAND_ORDER)
selected_work_categories = st.sidebar.multiselect("Rule-based work categories", WORK_CATEGORY_ORDER)
text_query = st.sidebar.text_input(
    "Search permit, description or address", placeholder="e.g. fitout or BP-2025"
)

filters = DashboardFilters(
    start_date=selected_start,
    end_date=selected_end,
    suburbs=tuple(selected_suburbs),
    cost_bands=tuple(selected_cost_bands),
    work_categories=tuple(selected_work_categories),
    text_query=text_query,
)
filtered = apply_filters(permits, filters)
comparison_filters = DashboardFilters(
    start_date=selected_start,
    end_date=selected_end,
    cost_bands=tuple(selected_cost_bands),
    work_categories=tuple(selected_work_categories),
    text_query=text_query,
)
municipality_filtered = apply_filters(permits, comparison_filters)

if selected_end.year >= 2026:
    st.warning(
        "The 2026 source partition drops sharply after April and appears incomplete or delayed. "
        "Do not interpret recent counts as a market downturn."
    )

if filtered.empty:
    st.info(
        "No unique permits match the current filters. Broaden the date range or clear a filter."
    )
    st.stop()

metrics = headline_metrics(filtered)
kpi_columns = st.columns(4)
kpi_columns[0].metric("Unique building permits", f"{metrics['permits']:,}")
kpi_columns[1].metric("Median positive estimated cost", currency(metrics["median_positive_cost"]))
kpi_columns[2].metric("Suburbs represented", f"{metrics['suburbs']:,}")
kpi_columns[3].metric("Share above $10m", f"{metrics['high_value_share']:.1%}")

st.subheader("Permit activity map")
if selected_suburbs:
    map_scope = ", ".join(suburb.title() for suburb in selected_suburbs)
else:
    map_scope = "all suburbs"

map_points = permit_map_points(filtered)
if map_points.empty:
    st.info(
        "No address-derived coordinates are available for the current filters. "
        "The other dashboard views remain available."
    )
else:
    latitude_span = float(map_points["latitude"].max() - map_points["latitude"].min())
    longitude_span = float(map_points["longitude"].max() - map_points["longitude"].min())
    coordinate_span = max(latitude_span, longitude_span)
    if coordinate_span < 0.01:
        map_zoom = 14
    elif coordinate_span < 0.025:
        map_zoom = 13
    elif coordinate_span < 0.06:
        map_zoom = 12
    else:
        map_zoom = 11
    map_figure = px.density_map(
        map_points,
        lat="latitude",
        lon="longitude",
        z="permits",
        radius=22,
        center={
            "lat": float(filtered["latitude"].dropna().mean()),
            "lon": float(filtered["longitude"].dropna().mean()),
        },
        zoom=map_zoom,
        map_style="carto-positron",
        color_continuous_scale="YlOrRd",
        hover_name="suburb",
        hover_data={
            "permits": ":,",
            "geocode_method": True,
            "latitude": False,
            "longitude": False,
        },
        labels={
            "permits": "Unique permits",
            "geocode_method": "Location method",
        },
        title=f"Permit hotspots — {map_scope}",
        height=610,
    )
    map_figure.update_layout(
        margin=dict(l=0, r=0, t=55, b=0),
        coloraxis_colorbar_title="Permits",
    )
    st.plotly_chart(map_figure, width="stretch")
    mapped_count = int(filtered["latitude"].notna().sum())
    st.caption(
        f"Mapped {mapped_count:,} of {len(filtered):,} filtered permits "
        f"({mapped_count / len(filtered):.1%}). Hotspots use representative permit "
        "locations, not every address attached to a permit."
    )

st.subheader("Suburb opportunity profile")
try:
    analysis_date = date.fromisoformat(str(metadata.get("as_of_date")))
except ValueError:
    analysis_date = date.today()
year_pair = complete_year_pair(selected_start, selected_end, analysis_date)
if year_pair:
    profile_year, previous_year = year_pair
    profile_label = str(profile_year)
    st.caption(
        f"Business signals use the latest two complete calendar years inside the current "
        f"date range: {profile_year} versus {previous_year}. Other filters remain applied."
    )
else:
    profile_year = previous_year = None
    profile_label = "selected period"
    st.caption(
        "The current date range does not contain two complete comparable calendar years. "
        "The profile therefore summarises the selected period without a growth claim."
    )

opportunity = suburb_opportunity_summary(filtered, profile_year, previous_year)
benchmarks = opportunity_benchmarks(municipality_filtered, profile_year)

if len(selected_suburbs) == 1 and not opportunity.empty:
    selected_profile = opportunity.iloc[0]
    profile_columns = st.columns(4)
    activity_delta = None
    if pd.notna(selected_profile["activity_change"]):
        activity_delta = (
            f"{selected_profile['activity_change']:+.1%} vs {previous_year} "
            f"({int(selected_profile['previous_permits']):,})"
        )
    profile_columns[0].metric(
        f"{profile_label} unique permits",
        f"{int(selected_profile['current_permits']):,}",
        delta=activity_delta,
        delta_color="off",
    )
    profile_columns[1].metric(
        "High-value permits above $10m",
        f"{int(selected_profile['high_value_permits']):,}",
    )
    profile_columns[1].caption(
        f"{selected_profile['high_value_share']:.1%} of {profile_label} permits; "
        f"municipality benchmark {benchmarks['high_value_share']:.1%}."
    )
    cost_difference = None
    municipality_cost = benchmarks["median_positive_cost"]
    if municipality_cost and pd.notna(selected_profile["median_positive_cost"]):
        cost_difference = selected_profile["median_positive_cost"] / municipality_cost - 1
    profile_columns[2].metric(
        f"{profile_label} median estimated cost",
        currency(selected_profile["median_positive_cost"]),
        delta=f"{cost_difference:+.1%} vs municipality" if cost_difference is not None else None,
        delta_color="off",
    )
    profile_columns[3].metric(
        "Dominant work category",
        selected_profile["dominant_work_category"],
    )
    profile_columns[3].caption(
        f"{selected_profile['dominant_category_share']:.1%} of {profile_label} permits."
    )

    st.markdown("#### Priority permit records")
    st.caption(
        f"The five highest source-reported estimated costs in {profile_label}; these are "
        "investigation candidates, not confirmed commercial leads or realised expenditure."
    )
    priority = priority_permits(filtered, profile_year)
    st.dataframe(
        priority,
        width="stretch",
        hide_index=True,
        column_config={
            "council_ref": "Council reference",
            "permit_issue_date": st.column_config.DateColumn("Issue date", format="DD MMM YYYY"),
            "estimated_cost": st.column_config.NumberColumn("Estimated cost", format="$%.0f"),
            "work_category_rule": "Work category",
            "primary_address": "Primary address",
        },
    )
else:
    if selected_suburbs:
        comparison_scope = "Selected suburbs"
    else:
        comparison_scope = "All suburbs"
    st.markdown(f"#### {comparison_scope}")
    st.caption(
        f"Ranked by {profile_label} permit volume. Select one suburb for municipality "
        "benchmarks and priority permit records."
    )
    comparison_columns = [
        "suburb",
        "current_permits",
        "high_value_permits",
        "high_value_share",
        "median_positive_cost",
        "dominant_work_category",
        "dominant_category_share",
    ]
    if year_pair:
        comparison_columns[2:2] = ["previous_permits", "activity_change"]
    st.dataframe(
        opportunity[comparison_columns],
        width="stretch",
        hide_index=True,
        column_config={
            "suburb": "Suburb",
            "current_permits": st.column_config.NumberColumn(
                f"{profile_label} permits", format="%d"
            ),
            "previous_permits": st.column_config.NumberColumn(
                f"{previous_year} permits", format="%d"
            ),
            "activity_change": st.column_config.NumberColumn("Activity change", format="percent"),
            "high_value_permits": st.column_config.NumberColumn("Permits above $10m", format="%d"),
            "high_value_share": st.column_config.NumberColumn("Share above $10m", format="percent"),
            "median_positive_cost": st.column_config.NumberColumn(
                "Median estimated cost", format="$%.0f"
            ),
            "dominant_work_category": "Dominant work category",
            "dominant_category_share": st.column_config.NumberColumn(
                "Top category share", format="percent"
            ),
        },
    )

trend = monthly_activity(filtered)
trend_figure = px.line(
    trend,
    x="issue_month",
    y="permits",
    markers=True,
    title="Unique permits by issue month",
    labels={"issue_month": "Issue month", "permits": "Unique permits"},
    color_discrete_sequence=[PLOT_COLOUR],
    template="plotly_white",
)
trend_figure.update_layout(hovermode="x unified", margin=dict(l=20, r=20, t=55, b=20))
trend_figure.update_yaxes(rangemode="tozero")
st.plotly_chart(trend_figure, width="stretch")

left, right = st.columns(2)
with left:
    suburbs = suburb_counts(filtered)
    suburb_figure = px.bar(
        suburbs,
        x="permits",
        y="suburb",
        orientation="h",
        title="Top suburbs by unique-permit count",
        labels={"suburb": "Suburb", "permits": "Unique permits"},
        color_discrete_sequence=[ACCENT_COLOUR],
        template="plotly_white",
    )
    suburb_figure.update_layout(margin=dict(l=20, r=20, t=55, b=20))
    suburb_figure.update_xaxes(rangemode="tozero")
    st.plotly_chart(suburb_figure, width="stretch")

with right:
    work = work_category_counts(filtered).sort_values("permits")
    work_figure = px.bar(
        work,
        x="permits",
        y="work_category_rule",
        orientation="h",
        title="Rule-based work categories",
        labels={"work_category_rule": "Work category", "permits": "Unique permits"},
        color_discrete_sequence=[PLOT_COLOUR],
        template="plotly_white",
    )
    work_figure.update_layout(margin=dict(l=20, r=20, t=55, b=20))
    work_figure.update_xaxes(rangemode="tozero")
    st.plotly_chart(work_figure, width="stretch")

st.subheader("Estimated-cost distribution")
st.caption(
    "The broad bands preserve the high-level market view. Use the detailed comparison below "
    "to inspect narrower ranges without changing the dashboard's main filters."
)
costs = cost_band_counts(filtered)
cost_figure = px.bar(
    costs,
    x="cost_band",
    y="permits",
    title="Unique-permit distribution by broad estimated-cost band",
    labels={"cost_band": "Estimated-cost band", "permits": "Unique permits"},
    color_discrete_sequence=[ACCENT_COLOUR],
    template="plotly_white",
)
cost_figure.update_layout(margin=dict(l=20, r=20, t=55, b=20))
cost_figure.update_yaxes(rangemode="tozero")
st.plotly_chart(cost_figure, width="stretch")

detail_options = [
    band
    for band in DETAILED_COST_BANDS
    if not selected_cost_bands or band in selected_cost_bands
]
if detail_options:
    st.markdown("#### Detailed cost-range comparison")
    detail_control, measure_control = st.columns([2, 3])
    default_detail = (
        detail_options.index("$250k–$1m") if "$250k–$1m" in detail_options else 0
    )
    selected_detail_band = detail_control.selectbox(
        "Broad range to investigate",
        detail_options,
        index=default_detail,
        help="The selected range is divided into narrower, mutually exclusive cost bands.",
    )
    breakdown_measure = measure_control.radio(
        "Comparison measure",
        ["Permit count", "Total estimated cost"],
        horizontal=True,
    )
    detail_order = DETAILED_COST_BANDS[selected_detail_band][1]

    if year_pair:
        cost_comparison = detailed_cost_comparison(
            filtered,
            selected_detail_band,
            profile_year,
            previous_year,
        )
        if breakdown_measure == "Permit count":
            value_label = "Unique permits"
            previous_column = "previous_permits"
            current_column = "current_permits"
        else:
            value_label = "Total estimated cost"
            previous_column = "previous_total_estimated_cost"
            current_column = "current_total_estimated_cost"
        chart_rows = pd.concat(
            [
                cost_comparison[["detailed_cost_band", previous_column]]
                .rename(columns={previous_column: "value"})
                .assign(issue_year=str(previous_year)),
                cost_comparison[["detailed_cost_band", current_column]]
                .rename(columns={current_column: "value"})
                .assign(issue_year=str(profile_year)),
            ],
            ignore_index=True,
        )
        detail_figure = px.bar(
            chart_rows,
            x="detailed_cost_band",
            y="value",
            color="issue_year",
            barmode="group",
            title=(
                f"{selected_detail_band} breakdown — {profile_year} versus {previous_year}"
            ),
            labels={
                "detailed_cost_band": "Detailed estimated-cost band",
                "value": value_label,
                "issue_year": "Permit issue year",
            },
            category_orders={
                "detailed_cost_band": detail_order,
                "issue_year": [str(previous_year), str(profile_year)],
            },
            color_discrete_sequence=["#9AAFB8", ACCENT_COLOUR],
            template="plotly_white",
        )
        detail_figure.update_layout(margin=dict(l=20, r=20, t=55, b=20))
        detail_figure.update_yaxes(rangemode="tozero")
        if breakdown_measure == "Total estimated cost":
            detail_figure.update_yaxes(tickprefix="$", separatethousands=True)
        st.plotly_chart(detail_figure, width="stretch")
        st.caption(
            "Comparison uses the latest two complete calendar years inside the selected date "
            "range. All suburb, broad cost, work-category and search filters remain applied. "
            "Estimated-cost totals are nominal source-reported values, not realised expenditure."
        )
        st.dataframe(
            cost_comparison[
                [
                    "detailed_cost_band",
                    "previous_permits",
                    "current_permits",
                    "permit_change",
                    "previous_total_estimated_cost",
                    "current_total_estimated_cost",
                    "estimated_cost_change",
                    "current_median_estimated_cost",
                ]
            ],
            width="stretch",
            hide_index=True,
            column_config={
                "detailed_cost_band": "Detailed cost band",
                "previous_permits": st.column_config.NumberColumn(
                    f"{previous_year} permits", format="%d"
                ),
                "current_permits": st.column_config.NumberColumn(
                    f"{profile_year} permits", format="%d"
                ),
                "permit_change": st.column_config.NumberColumn(
                    "Permit change", format="percent"
                ),
                "previous_total_estimated_cost": st.column_config.NumberColumn(
                    f"{previous_year} total estimated cost", format="$%.0f"
                ),
                "current_total_estimated_cost": st.column_config.NumberColumn(
                    f"{profile_year} total estimated cost", format="$%.0f"
                ),
                "estimated_cost_change": st.column_config.NumberColumn(
                    "Estimated-cost change", format="percent"
                ),
                "current_median_estimated_cost": st.column_config.NumberColumn(
                    f"{profile_year} median estimated cost", format="$%.0f"
                ),
            },
        )
    else:
        cost_detail = detailed_cost_summary(filtered, selected_detail_band)
        value_column = (
            "permits" if breakdown_measure == "Permit count" else "total_estimated_cost"
        )
        value_label = (
            "Unique permits"
            if breakdown_measure == "Permit count"
            else "Total estimated cost"
        )
        detail_figure = px.bar(
            cost_detail,
            x="detailed_cost_band",
            y=value_column,
            title=f"{selected_detail_band} breakdown — selected period",
            labels={
                "detailed_cost_band": "Detailed estimated-cost band",
                value_column: value_label,
            },
            category_orders={"detailed_cost_band": detail_order},
            color_discrete_sequence=[ACCENT_COLOUR],
            template="plotly_white",
        )
        detail_figure.update_layout(margin=dict(l=20, r=20, t=55, b=20))
        detail_figure.update_yaxes(rangemode="tozero")
        if breakdown_measure == "Total estimated cost":
            detail_figure.update_yaxes(tickprefix="$", separatethousands=True)
        st.plotly_chart(detail_figure, width="stretch")
        st.caption(
            "The selected date range does not contain two complete comparable calendar years. "
            "This view therefore shows the detailed selected-period distribution without a "
            "year-over-year claim."
        )
        st.dataframe(
            cost_detail,
            width="stretch",
            hide_index=True,
            column_config={
                "detailed_cost_band": "Detailed cost band",
                "permits": st.column_config.NumberColumn("Unique permits", format="%d"),
                "total_estimated_cost": st.column_config.NumberColumn(
                    "Total estimated cost", format="$%.0f"
                ),
                "median_estimated_cost": st.column_config.NumberColumn(
                    "Median estimated cost", format="$%.0f"
                ),
            },
        )
else:
    st.info(
        "Detailed cost analysis is unavailable because the active broad cost filter contains "
        "only non-positive or missing estimated costs."
    )

with st.expander("Metric definitions and responsible use"):
    st.caption(
        "Definitions apply to the currently filtered population unless the explanation names "
        "a profile period or municipality benchmark. Use this dashboard for exploratory analysis, "
        "not regulatory, legal, valuation or procurement decisions."
    )
    st.dataframe(
        metric_glossary(),
        width="stretch",
        hide_index=True,
        height=620,
        column_config={
            "term": st.column_config.TextColumn("Term", width="medium"),
            "explanation": st.column_config.TextColumn("Explanation", width="large"),
            "formula_or_rule": st.column_config.TextColumn("Formula or rule", width="large"),
            "use_with_caution": st.column_config.TextColumn("Use with caution", width="large"),
        },
    )

st.subheader("Unique permit records")
record_columns = [
    "council_ref",
    "permit_issue_date",
    "suburb",
    "cost_band",
    "estimated_cost",
    "work_category_rule",
    "desc_of_works",
    "primary_address",
]
records = filtered[record_columns].sort_values("permit_issue_date", ascending=False)
records.insert(4, "detailed_cost_band", detailed_cost_band_values(records))
st.dataframe(
    records,
    width="stretch",
    hide_index=True,
    column_config={
        "council_ref": "Council reference",
        "permit_issue_date": st.column_config.DateColumn("Issue date", format="DD MMM YYYY"),
        "suburb": "Suburb",
        "cost_band": "Cost band",
        "detailed_cost_band": "Detailed cost band",
        "estimated_cost": st.column_config.NumberColumn("Estimated cost", format="$%.0f"),
        "work_category_rule": "Work category",
        "desc_of_works": "Description",
        "primary_address": "Primary address",
    },
)
st.download_button(
    "Download filtered records",
    data=records.to_csv(index=False).encode("utf-8"),
    file_name="permitpulse_filtered_permits.csv",
    mime="text/csv",
)

with st.expander("Source and data quality"):
    summary = metadata.get("summary", {})
    geospatial = metadata.get("geospatial_source", {})
    st.markdown(
        f"**Source:** City of Melbourne Building Permits (CC BY)  \n"
        f"**Snapshot analysis date:** {metadata.get('as_of_date', 'Unavailable')}  \n"
        f"**Source SHA-256:** `{metadata.get('source_sha256', 'Unavailable')}`  \n"
        f"**Analytics-ready unique permits:** {summary.get('analytic_permits', 0):,}  \n"
        f"**Map source:** {geospatial.get('dataset', 'Not supplied')} (CC BY)  \n"
        f"**Map-source SHA-256:** `{geospatial.get('source_sha256', 'Unavailable')}`  \n"
        f"**Mapped unique permits:** {summary.get('geocoded_permits', 0):,} "
        f"({summary.get('geocoded_rate', 0):.1%})"
    )
    st.caption(
        "Counts use one Building Permit council reference per permit family. Map coordinates "
        "come from exact City address points or the centroid of official points inside a stated "
        "street-number range; unmatched records are not plotted. These are representative permit "
        "locations, not parcel boundaries. Estimated costs are source-reported estimates, not "
        "realised expenditure. Work categories use transparent keyword rules and have not yet "
        "been replaced by a validated ML classifier."
    )
    warnings = quality.loc[
        quality["status"] == "warn",
        [
            "check_id",
            "severity",
            "affected_rows",
            "affected_rate",
            "metric_value",
            "metric_unit",
            "details",
        ],
    ].copy()
    warnings["affected_rate"] = warnings["affected_rate"].map(
        lambda value: f"{value:.2%}" if pd.notna(value) else ""
    )
    warnings = warnings.rename(
        columns={
            "check_id": "Check",
            "severity": "Severity",
            "affected_rows": "Affected rows",
            "affected_rate": "Affected rate",
            "metric_value": "Metric value",
            "metric_unit": "Metric unit",
            "details": "Interpretation",
        }
    )
    st.dataframe(
        warnings,
        width="stretch",
        hide_index=True,
        column_config={
            "Affected rows": st.column_config.NumberColumn(format="%d"),
            "Metric value": st.column_config.NumberColumn(format="%.3f"),
        },
    )
