from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from permitpulse.pipeline import COST_BAND_ORDER, WORK_CATEGORY_ORDER

DETAILED_COST_BANDS: dict[str, tuple[list[float], list[str]]] = {
    "$1–$50k": (
        [0, 10_000, 25_000, 50_000],
        ["$1–$10k", "$10k–$25k", "$25k–$50k"],
    ),
    "$50k–$250k": (
        [50_000, 100_000, 150_000, 200_000, 250_000],
        ["$50k–$100k", "$100k–$150k", "$150k–$200k", "$200k–$250k"],
    ),
    "$250k–$1m": (
        [250_000, 500_000, 750_000, 1_000_000],
        ["$250k–$500k", "$500k–$750k", "$750k–$1m"],
    ),
    "$1m–$10m": (
        [1_000_000, 2_500_000, 5_000_000, 7_500_000, 10_000_000],
        ["$1m–$2.5m", "$2.5m–$5m", "$5m–$7.5m", "$7.5m–$10m"],
    ),
    "> $10m": (
        [10_000_000, 25_000_000, 50_000_000, 100_000_000, float("inf")],
        ["$10m–$25m", "$25m–$50m", "$50m–$100m", "> $100m"],
    ),
}


@dataclass(frozen=True)
class DashboardFilters:
    start_date: date
    end_date: date
    suburbs: tuple[str, ...] = ()
    cost_bands: tuple[str, ...] = ()
    work_categories: tuple[str, ...] = ()
    text_query: str = ""


def load_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Dashboard data not found: {path}")
    with duckdb.connect() as connection:
        frame = connection.execute("SELECT * FROM read_parquet(?)", [str(path)]).df()
    for column in ["permit_issue_date", "issue_month", "commence_by_date", "completed_by_date"]:
        if column in frame:
            frame[column] = pd.to_datetime(frame[column], errors="coerce")
    return frame


def apply_filters(frame: pd.DataFrame, filters: DashboardFilters) -> pd.DataFrame:
    mask = frame["permit_issue_date"].between(
        pd.Timestamp(filters.start_date), pd.Timestamp(filters.end_date)
    )
    if filters.suburbs:
        mask &= frame["suburb"].isin(filters.suburbs)
    if filters.cost_bands:
        mask &= frame["cost_band"].isin(filters.cost_bands)
    if filters.work_categories:
        mask &= frame["work_category_rule"].isin(filters.work_categories)
    query = filters.text_query.strip()
    if query:
        searchable = (
            frame["council_ref"].fillna("")
            + " "
            + frame["desc_of_works"].fillna("")
            + " "
            + frame["primary_address"].fillna("")
        )
        mask &= searchable.str.contains(query, case=False, regex=False)
    return frame.loc[mask].copy()


def headline_metrics(frame: pd.DataFrame) -> dict[str, float | int | None]:
    positive_costs = frame.loc[frame["estimated_cost"] > 0, "estimated_cost"]
    return {
        "permits": len(frame),
        "median_positive_cost": float(positive_costs.median()) if len(positive_costs) else None,
        "suburbs": int(frame["suburb"].nunique()),
        "high_value_share": float((frame["estimated_cost"] > 10_000_000).mean())
        if len(frame)
        else 0.0,
    }


def monthly_activity(frame: pd.DataFrame) -> pd.DataFrame:
    return (
        frame.dropna(subset=["issue_month"])
        .groupby("issue_month", as_index=False)
        .agg(permits=("council_ref", "nunique"))
        .sort_values("issue_month")
    )


def category_counts(
    frame: pd.DataFrame,
    column: str,
    order: list[str] | None = None,
) -> pd.DataFrame:
    counts = (
        frame.assign(**{column: frame[column].fillna("Unknown")})
        .groupby(column, as_index=False, observed=True)
        .agg(permits=("council_ref", "nunique"))
    )
    if order:
        positions = {value: index for index, value in enumerate(order)}
        counts["_order"] = counts[column].map(positions).fillna(len(order))
        return counts.sort_values(["_order", column]).drop(columns="_order")
    return counts.sort_values(["permits", column], ascending=[False, True])


def cost_band_counts(frame: pd.DataFrame) -> pd.DataFrame:
    return category_counts(frame, "cost_band", COST_BAND_ORDER)


def detailed_cost_band_values(frame: pd.DataFrame) -> pd.Series:
    """Return a reader-facing detailed cost band for each permit."""
    values = pd.Series("Not detailed", index=frame.index, dtype="string")
    for broad_band, (bins, labels) in DETAILED_COST_BANDS.items():
        mask = frame["cost_band"].eq(broad_band)
        values.loc[mask] = pd.cut(
            frame.loc[mask, "estimated_cost"],
            bins=bins,
            labels=labels,
            include_lowest=False,
        ).astype("string")
    return values


def detailed_cost_summary(frame: pd.DataFrame, broad_band: str) -> pd.DataFrame:
    """Summarise permit volume and estimated cost inside one broad cost band."""
    if broad_band not in DETAILED_COST_BANDS:
        raise ValueError(f"Detailed cost breakdown is unavailable for {broad_band!r}.")
    _, labels = DETAILED_COST_BANDS[broad_band]
    population = frame.loc[frame["cost_band"].eq(broad_band)].copy()
    population["detailed_cost_band"] = detailed_cost_band_values(population)
    summary = (
        population.groupby("detailed_cost_band", as_index=False, observed=True)
        .agg(
            permits=("council_ref", "nunique"),
            total_estimated_cost=("estimated_cost", "sum"),
            median_estimated_cost=("estimated_cost", "median"),
        )
        .set_index("detailed_cost_band")
        .reindex(labels)
        .rename_axis("detailed_cost_band")
        .reset_index()
    )
    summary["permits"] = summary["permits"].fillna(0).astype("int64")
    summary["total_estimated_cost"] = summary["total_estimated_cost"].fillna(0.0)
    return summary


def detailed_cost_comparison(
    frame: pd.DataFrame,
    broad_band: str,
    current_year: int,
    previous_year: int,
) -> pd.DataFrame:
    """Compare detailed cost bands across two complete permit-issue years."""
    current = detailed_cost_summary(
        frame.loc[frame["permit_issue_date"].dt.year == current_year], broad_band
    ).rename(
        columns={
            "permits": "current_permits",
            "total_estimated_cost": "current_total_estimated_cost",
            "median_estimated_cost": "current_median_estimated_cost",
        }
    )
    previous = detailed_cost_summary(
        frame.loc[frame["permit_issue_date"].dt.year == previous_year], broad_band
    ).rename(
        columns={
            "permits": "previous_permits",
            "total_estimated_cost": "previous_total_estimated_cost",
            "median_estimated_cost": "previous_median_estimated_cost",
        }
    )
    comparison = current.merge(previous, on="detailed_cost_band", validate="one_to_one")
    comparison["permit_change"] = (
        (comparison["current_permits"] - comparison["previous_permits"])
        / comparison["previous_permits"]
    ).where(comparison["previous_permits"] > 0)
    comparison["estimated_cost_change"] = (
        (
            comparison["current_total_estimated_cost"]
            - comparison["previous_total_estimated_cost"]
        )
        / comparison["previous_total_estimated_cost"]
    ).where(comparison["previous_total_estimated_cost"] > 0)
    return comparison


def work_category_counts(frame: pd.DataFrame) -> pd.DataFrame:
    return category_counts(frame, "work_category_rule", WORK_CATEGORY_ORDER)


def suburb_counts(frame: pd.DataFrame, limit: int = 12) -> pd.DataFrame:
    return category_counts(frame, "suburb").head(limit).sort_values("permits")


def permit_map_points(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"latitude", "longitude", "suburb", "geocode_method", "council_ref"}
    if not required <= set(frame.columns):
        return pd.DataFrame(
            columns=["latitude", "longitude", "suburb", "geocode_method", "permits"]
        )
    mapped = frame.dropna(subset=["latitude", "longitude"]).copy()
    if mapped.empty:
        return pd.DataFrame(
            columns=["latitude", "longitude", "suburb", "geocode_method", "permits"]
        )
    return (
        mapped.groupby(
            ["latitude", "longitude", "suburb", "geocode_method"],
            as_index=False,
            dropna=False,
            observed=True,
        )
        .agg(permits=("council_ref", "nunique"))
        .sort_values("permits", ascending=False)
    )


def complete_year_pair(
    start_date: date,
    end_date: date,
    as_of_date: date,
) -> tuple[int, int] | None:
    """Return the latest two complete calendar years inside the selected range."""
    eligible_years = [
        year
        for year in range(start_date.year, end_date.year + 1)
        if year < as_of_date.year
        and date(year, 1, 1) >= start_date
        and date(year, 12, 31) <= end_date
    ]
    if len(eligible_years) < 2:
        return None
    current_year = max(eligible_years)
    previous_year = current_year - 1
    if previous_year not in eligible_years:
        return None
    return current_year, previous_year


def suburb_opportunity_summary(
    frame: pd.DataFrame,
    current_year: int | None = None,
    previous_year: int | None = None,
) -> pd.DataFrame:
    """Summarise activity, value mix and work mix by suburb."""
    columns = [
        "suburb",
        "current_permits",
        "previous_permits",
        "activity_change",
        "high_value_permits",
        "high_value_share",
        "median_positive_cost",
        "dominant_work_category",
        "dominant_category_share",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)

    if current_year is None:
        current = frame.copy()
    else:
        current = frame.loc[frame["permit_issue_date"].dt.year == current_year].copy()
    if current.empty:
        return pd.DataFrame(columns=columns)

    current = current.assign(
        _positive_cost=current["estimated_cost"].where(current["estimated_cost"] > 0),
        _high_value=current["estimated_cost"] > 10_000_000,
    )
    summary = current.groupby("suburb", as_index=False, dropna=False, observed=True).agg(
        current_permits=("council_ref", "nunique"),
        high_value_permits=("_high_value", "sum"),
        high_value_share=("_high_value", "mean"),
        median_positive_cost=("_positive_cost", "median"),
    )

    category_mix = (
        current.assign(work_category_rule=current["work_category_rule"].fillna("Unknown"))
        .groupby(["suburb", "work_category_rule"], as_index=False, observed=True)
        .agg(category_permits=("council_ref", "nunique"))
        .sort_values(
            ["suburb", "category_permits", "work_category_rule"],
            ascending=[True, False, True],
        )
        .drop_duplicates("suburb")
        .rename(columns={"work_category_rule": "dominant_work_category"})
    )
    summary = summary.merge(category_mix, on="suburb", how="left", validate="one_to_one")
    summary["dominant_category_share"] = summary["category_permits"] / summary["current_permits"]
    summary = summary.drop(columns="category_permits")

    if previous_year is not None:
        previous = (
            frame.loc[frame["permit_issue_date"].dt.year == previous_year]
            .groupby("suburb", as_index=False, dropna=False, observed=True)
            .agg(previous_permits=("council_ref", "nunique"))
        )
        summary = summary.merge(previous, on="suburb", how="left", validate="one_to_one")
    else:
        summary["previous_permits"] = pd.NA
    summary["previous_permits"] = summary["previous_permits"].astype("Int64")
    summary["activity_change"] = (
        (summary["current_permits"] - summary["previous_permits"]) / summary["previous_permits"]
    ).where(summary["previous_permits"] > 0)
    summary["suburb"] = summary["suburb"].fillna("Unknown")
    return summary[columns].sort_values(
        ["current_permits", "high_value_permits", "suburb"],
        ascending=[False, False, True],
    )


def opportunity_benchmarks(
    frame: pd.DataFrame,
    current_year: int | None = None,
) -> dict[str, float | int | None]:
    period = (
        frame
        if current_year is None
        else frame.loc[frame["permit_issue_date"].dt.year == current_year]
    )
    positive_costs = period.loc[period["estimated_cost"] > 0, "estimated_cost"]
    return {
        "permits": int(period["council_ref"].nunique()),
        "high_value_share": float((period["estimated_cost"] > 10_000_000).mean())
        if len(period)
        else 0.0,
        "median_positive_cost": float(positive_costs.median()) if len(positive_costs) else None,
    }


def priority_permits(
    frame: pd.DataFrame,
    current_year: int | None = None,
    limit: int = 5,
) -> pd.DataFrame:
    period = (
        frame
        if current_year is None
        else frame.loc[frame["permit_issue_date"].dt.year == current_year]
    )
    columns = [
        "council_ref",
        "permit_issue_date",
        "estimated_cost",
        "work_category_rule",
        "primary_address",
    ]
    return (
        period[columns]
        .sort_values(
            ["estimated_cost", "permit_issue_date", "council_ref"],
            ascending=[False, False, True],
            na_position="last",
        )
        .head(limit)
        .reset_index(drop=True)
    )


def metric_glossary() -> pd.DataFrame:
    """Return reader-facing metric definitions and responsible-use guidance."""
    rows = [
        {
            "term": "Unique building permits",
            "explanation": (
                "Distinct Building Permit council references in the filtered analytics-ready "
                "population. Certificate and address rows are not counted as separate permits."
            ),
            "formula_or_rule": "Count distinct council_ref",
            "use_with_caution": (
                "A permit is an administrative record, not confirmation that construction "
                "started or finished."
            ),
        },
        {
            "term": "Analytics-ready permit",
            "explanation": (
                "A permit family that passed the pipeline's high-severity checks and did not "
                "contain conflicting estimated-cost values."
            ),
            "formula_or_rule": "quality_status = valid",
            "use_with_caution": (
                "Excluded records remain available for data-quality review; exclusion is not "
                "evidence of regulatory failure."
            ),
        },
        {
            "term": "Estimated cost",
            "explanation": "The estimated cost reported in the source permit record.",
            "formula_or_rule": "Source value; no inflation or currency adjustment",
            "use_with_caution": (
                "It is not realised expenditure, contract value, revenue or current market value."
            ),
        },
        {
            "term": "Median positive estimated cost",
            "explanation": (
                "The middle positive estimated-cost value after sorting permits in the filtered "
                "population. Zero, negative and missing values are excluded."
            ),
            "formula_or_rule": "Median(estimated_cost where estimated_cost > 0)",
            "use_with_caution": (
                "The median reduces outlier influence but still inherits source-reporting limits."
            ),
        },
        {
            "term": "High-value permit",
            "explanation": (
                "A unique permit with a source-reported estimated cost above $10 million."
            ),
            "formula_or_rule": "estimated_cost > $10,000,000",
            "use_with_caution": (
                "The threshold is an analytical segment, not an official classification."
            ),
        },
        {
            "term": "Share above $10m",
            "explanation": ("The proportion of filtered unique permits classified as high value."),
            "formula_or_rule": "High-value unique permits ÷ all filtered unique permits",
            "use_with_caution": (
                "Missing or non-positive cost values remain in the denominator and are "
                "not high value."
            ),
        },
        {
            "term": "Activity change",
            "explanation": (
                "The change in unique permit count between the latest two complete calendar years "
                "inside the selected date range."
            ),
            "formula_or_rule": (
                "(Current-year permits − previous-year permits) ÷ previous-year permits"
            ),
            "use_with_caution": (
                "Both counts are shown because large percentages can result from a small "
                "prior-year base."
            ),
        },
        {
            "term": "Dominant work category",
            "explanation": (
                "The rule-based work category with the most unique permits in the suburb and "
                "profile period."
            ),
            "formula_or_rule": "Category with the highest distinct council_ref count",
            "use_with_caution": (
                "Categories use transparent description keywords, not a validated "
                "machine-learning model."
            ),
        },
        {
            "term": "Top category share",
            "explanation": (
                "The proportion of a suburb's permits belonging to its dominant work category."
            ),
            "formula_or_rule": (
                "Permits in dominant category ÷ all suburb permits in profile period"
            ),
            "use_with_caution": (
                "It measures work-mix concentration, not cost share, revenue or market share. "
                "A work-category filter can make this 100%."
            ),
        },
        {
            "term": "Municipality benchmark",
            "explanation": (
                "The comparable measure across all City of Melbourne suburbs after applying the "
                "date, cost, work-category and search filters but ignoring the suburb selection."
            ),
            "formula_or_rule": (
                "Recalculate the metric across all suburbs under the other active filters"
            ),
            "use_with_caution": "This covers the municipality, not metropolitan Melbourne.",
        },
        {
            "term": "Priority permit records",
            "explanation": (
                "The five permit records with the highest source-reported estimated costs in the "
                "selected suburb and profile period."
            ),
            "formula_or_rule": (
                "Sort estimated_cost descending, then issue date descending; keep five"
            ),
            "use_with_caution": (
                "These are investigation candidates, not confirmed active projects or "
                "commercial leads."
            ),
        },
        {
            "term": "Broad cost band",
            "explanation": (
                "The high-level grouping of source-reported estimated cost used by the sidebar "
                "filter and overall distribution chart."
            ),
            "formula_or_rule": (
                "≤$0; $1–$50k; $50k–$250k; $250k–$1m; $1m–$10m; >$10m; Missing"
            ),
            "use_with_caution": "Bands do not indicate project profitability or procurement stage.",
        },
        {
            "term": "Detailed cost band",
            "explanation": (
                "A narrower estimated-cost range inside one selected positive broad cost band."
            ),
            "formula_or_rule": (
                "$1–$50k: 3 ranges; $50k–$250k: 4; $250k–$1m: 3; "
                "$1m–$10m: 4; >$10m: 4"
            ),
            "use_with_caution": (
                "The ranges are analytical groupings and are not official project classifications."
            ),
        },
        {
            "term": "Cost-band year-over-year change",
            "explanation": (
                "The change in permit count or total source-reported estimated cost for the same "
                "detailed cost band across the latest two complete calendar years."
            ),
            "formula_or_rule": "(Current year ÷ previous year) − 1",
            "use_with_caution": (
                "Estimated-cost totals are nominal, outlier-sensitive and not realised "
                "expenditure. No percentage is shown when the previous-year value is zero."
            ),
        },
        {
            "term": "Permit hotspot",
            "explanation": (
                "A map area where representative permit locations are concentrated under the "
                "active filters."
            ),
            "formula_or_rule": (
                "Heat intensity is weighted by unique permits at each mapped location"
            ),
            "use_with_caution": (
                "Hotspots show record concentration, not development value, parcel area "
                "or causal demand."
            ),
        },
        {
            "term": "Mapped share",
            "explanation": (
                "The proportion of filtered unique permits with an address-derived coordinate."
            ),
            "formula_or_rule": "Mapped unique permits ÷ all filtered unique permits",
            "use_with_caution": (
                "Unmatched permits remain in dashboard totals but are absent from the map."
            ),
        },
        {
            "term": "Exact address point",
            "explanation": (
                "A representative coordinate derived from official City address points sharing "
                "the exact street number, street and suburb."
            ),
            "formula_or_rule": "Mean latitude and longitude of matching official address points",
            "use_with_caution": (
                "Multiple unit-level points may be averaged so that one permit is plotted once."
            ),
        },
        {
            "term": "Range centroid",
            "explanation": (
                "A representative coordinate for a permit address containing a street-number range."
            ),
            "formula_or_rule": (
                "Mean latitude and longitude of official points inside the stated number range "
                "on the same street and suburb"
            ),
            "use_with_caution": "It is not a surveyed parcel or building-footprint centroid.",
        },
    ]
    return pd.DataFrame(rows)
