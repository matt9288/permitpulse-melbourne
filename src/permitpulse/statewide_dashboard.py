from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from permitpulse.dashboard import DETAILED_COST_BAND_ORDER, detailed_cost_band_values
from permitpulse.pipeline import COST_BAND_ORDER


@dataclass(frozen=True)
class StatewideFilters:
    start_date: date
    end_date: date
    regions: tuple[str, ...] = ()
    municipalities: tuple[str, ...] = ()
    suburbs: tuple[str, ...] = ()
    cost_bands: tuple[str, ...] = ()
    nature_of_work: tuple[str, ...] = ()
    building_uses: tuple[str, ...] = ()
    text_query: str = ""


def apply_statewide_filters(frame: pd.DataFrame, filters: StatewideFilters) -> pd.DataFrame:
    mask = frame["report_month"].between(
        pd.Timestamp(filters.start_date), pd.Timestamp(filters.end_date)
    )
    for values, column in [
        (filters.regions, "region"),
        (filters.municipalities, "municipality"),
        (filters.suburbs, "suburb"),
        (filters.cost_bands, "cost_band"),
        (filters.nature_of_work, "nature_of_work"),
        (filters.building_uses, "building_use"),
    ]:
        if values:
            mask &= frame[column].isin(values)
    query = filters.text_query.strip()
    if query:
        searchable = (
            frame["municipality"].fillna("")
            + " "
            + frame["suburb"].fillna("")
            + " "
            + frame["street_name"].fillna("")
            + " "
            + frame["nature_of_work"].fillna("")
            + " "
            + frame["building_use"].fillna("")
        )
        mask &= searchable.str.contains(query, case=False, regex=False)
    return frame.loc[mask].copy()


def headline_metrics(frame: pd.DataFrame) -> dict[str, float | int | None]:
    positive_costs = frame.loc[frame["estimated_cost"] > 0, "estimated_cost"]
    return {
        "records": len(frame),
        "reported_cost": float(frame["estimated_cost"].sum()),
        "median_positive_cost": float(positive_costs.median()) if len(positive_costs) else None,
        "municipalities": int(frame["municipality"].nunique()),
        "new_dwellings": int(frame["new_dwellings"].fillna(0).sum()),
        "high_value_share": float((frame["estimated_cost"] > 10_000_000).mean())
        if len(frame)
        else 0.0,
    }


def monthly_activity(frame: pd.DataFrame) -> pd.DataFrame:
    return (
        frame.dropna(subset=["report_month"])
        .groupby("report_month", as_index=False)
        .agg(records=("record_id", "size"), reported_cost=("estimated_cost", "sum"))
        .sort_values("report_month")
    )


def category_summary(frame: pd.DataFrame, column: str, limit: int | None = None) -> pd.DataFrame:
    summary = (
        frame.assign(**{column: frame[column].fillna("Unknown")})
        .groupby(column, as_index=False, observed=True)
        .agg(records=("record_id", "size"), reported_cost=("estimated_cost", "sum"))
        .sort_values(["records", column], ascending=[False, True])
    )
    return summary.head(limit) if limit else summary


def cost_distribution(frame: pd.DataFrame, detailed: bool = False) -> pd.DataFrame:
    population = frame.copy()
    if detailed:
        population["cost_range"] = detailed_cost_band_values(population)
        order = DETAILED_COST_BAND_ORDER
    else:
        population["cost_range"] = population["cost_band"].astype("string")
        order = COST_BAND_ORDER
    population["positive_estimated_cost"] = population["estimated_cost"].where(
        population["estimated_cost"] > 0
    )
    summary = (
        population.groupby("cost_range", as_index=False, observed=True)
        .agg(
            records=("record_id", "size"),
            total_reported_cost=("positive_estimated_cost", "sum"),
            median_reported_cost=("positive_estimated_cost", "median"),
        )
        .set_index("cost_range")
        .reindex(order)
        .rename_axis("cost_range")
        .reset_index()
    )
    summary["records"] = summary["records"].fillna(0).astype("int64")
    summary["total_reported_cost"] = summary["total_reported_cost"].fillna(0.0)
    return summary


def cost_comparison(
    frame: pd.DataFrame, focus_year: int, baseline_year: int, detailed: bool = False
) -> pd.DataFrame:
    if focus_year == baseline_year:
        raise ValueError("Comparison years must be different.")
    focus = cost_distribution(frame.loc[frame["report_year"] == focus_year], detailed).rename(
        columns={
            "records": "focus_records",
            "total_reported_cost": "focus_total_reported_cost",
            "median_reported_cost": "focus_median_reported_cost",
        }
    )
    baseline = cost_distribution(frame.loc[frame["report_year"] == baseline_year], detailed).rename(
        columns={
            "records": "baseline_records",
            "total_reported_cost": "baseline_total_reported_cost",
            "median_reported_cost": "baseline_median_reported_cost",
        }
    )
    result = focus.merge(baseline, on="cost_range", validate="one_to_one")
    result["record_change"] = (
        (result["focus_records"] - result["baseline_records"]) / result["baseline_records"]
    ).where(result["baseline_records"] > 0)
    result["reported_cost_change"] = (
        (result["focus_total_reported_cost"] - result["baseline_total_reported_cost"])
        / result["baseline_total_reported_cost"]
    ).where(result["baseline_total_reported_cost"] > 0)
    return result


def municipality_summary(
    frame: pd.DataFrame, focus_year: int, baseline_year: int | None = None
) -> pd.DataFrame:
    focus = frame.loc[frame["report_year"] == focus_year].copy()
    focus["positive_cost"] = focus["estimated_cost"].where(focus["estimated_cost"] > 0)
    focus["high_value"] = focus["estimated_cost"] > 10_000_000
    summary = focus.groupby("municipality", as_index=False, observed=True).agg(
        focus_records=("record_id", "size"),
        total_reported_cost=("estimated_cost", "sum"),
        median_reported_cost=("positive_cost", "median"),
        high_value_records=("high_value", "sum"),
        new_dwellings=("new_dwellings", "sum"),
        dwellings_demolished=("dwellings_demolished", "sum"),
    )
    summary["high_value_share"] = summary["high_value_records"] / summary["focus_records"]
    if baseline_year is not None:
        baseline = (
            frame.loc[frame["report_year"] == baseline_year]
            .groupby("municipality", as_index=False, observed=True)
            .agg(baseline_records=("record_id", "size"))
        )
        summary = summary.merge(baseline, on="municipality", how="left", validate="one_to_one")
        summary["baseline_records"] = summary["baseline_records"].fillna(0).astype(int)
        summary["record_change"] = (
            (summary["focus_records"] - summary["baseline_records"]) / summary["baseline_records"]
        ).where(summary["baseline_records"] > 0)
    else:
        summary["baseline_records"] = pd.NA
        summary["record_change"] = pd.NA
    return summary.sort_values(
        ["focus_records", "total_reported_cost", "municipality"], ascending=[False, False, True]
    )


def municipality_map_summary(frame: pd.DataFrame) -> pd.DataFrame:
    return (
        frame.dropna(subset=["municipality_map_name"])
        .groupby(["municipality_map_name", "municipality"], as_index=False, observed=True)
        .agg(
            records=("record_id", "size"),
            reported_cost=("estimated_cost", "sum"),
            new_dwellings=("new_dwellings", "sum"),
        )
    )


def metric_glossary() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "term": "Permit record",
                "explanation": "One row in the BPC annual building-permit activity file.",
                "formula_or_rule": "Count rows after filters",
                "use_with_caution": (
                    "The public source has no permit identifier, so this is not a "
                    "unique-permit count."
                ),
            },
            {
                "term": "Reporting period",
                "explanation": "The levy reporting month and year assigned by the source.",
                "formula_or_rule": "BASIS_Month_Y + BASIS_Month_M",
                "use_with_caution": (
                    "Permit issue dates can be earlier than the reporting period due to delayed "
                    "reporting or corrections."
                ),
            },
            {
                "term": "Reported cost",
                "explanation": "Estimated cost reported for the permit record.",
                "formula_or_rule": "Reported_Cost_of_works",
                "use_with_caution": (
                    "It is nominal, not inflation-adjusted, and is not realised expenditure, "
                    "contract value or revenue."
                ),
            },
            {
                "term": "Total reported cost",
                "explanation": "Sum of reported cost across filtered source records.",
                "formula_or_rule": "Sum(Reported_Cost_of_works)",
                "use_with_caution": (
                    "Large projects can dominate the total. Do not sum project-total cost "
                    "across stages because it may repeat."
                ),
            },
            {
                "term": "Median positive reported cost",
                "explanation": (
                    "Middle reported cost after excluding missing, zero and negative values."
                ),
                "formula_or_rule": "Median(reported cost where cost > 0)",
                "use_with_caution": (
                    "This inherits surveyor reporting limitations and does not show cost overruns."
                ),
            },
            {
                "term": "High-value share",
                "explanation": "Share of permit records with reported cost above $10 million.",
                "formula_or_rule": "Records above $10m / all filtered records",
                "use_with_caution": (
                    "The threshold is an analytical segment, not an official classification."
                ),
            },
            {
                "term": "Record change",
                "explanation": "Year-to-year change in permit-record volume.",
                "formula_or_rule": "(Focus records / baseline records) - 1",
                "use_with_caution": (
                    "It uses reporting year, not permit issue year, and does not measure "
                    "construction starts."
                ),
            },
            {
                "term": "Nature of work",
                "explanation": "Official source code translated using the BPC data dictionary.",
                "formula_or_rule": (
                    "1 New; 2 Re-erection; 3 Extension; 4 Alteration; 5 Change of use; "
                    "6 Demolition; 7 Removal; 8 Other"
                ),
                "use_with_caution": (
                    "It reflects the reported permit category and is not a custom predictive "
                    "classification."
                ),
            },
            {
                "term": "New dwellings",
                "explanation": (
                    "Sum of source-reported new dwellings attached to filtered permit records."
                ),
                "formula_or_rule": "Sum(Number_of_New_Dwellings__c)",
                "use_with_caution": (
                    "It is planned activity in permit records, not confirmed completions."
                ),
            },
            {
                "term": "Municipality hotspot",
                "explanation": (
                    "A municipality shaded by permit-record count, reported cost or new dwellings."
                ),
                "formula_or_rule": "Aggregate filtered records by Vicmap LGA boundary",
                "use_with_caution": (
                    "The source has no coordinates, so this is an LGA-level view rather than "
                    "an address heat map."
                ),
            },
            {
                "term": "Detailed cost band",
                "explanation": (
                    "A narrower analytical grouping of reported cost selected directly in the "
                    "cost view."
                ),
                "formula_or_rule": (
                    "$1-$50k: 3; $50k-$250k: 4; $250k-$1m: 3; $1m-$10m: 4; above $10m: 4 ranges"
                ),
                "use_with_caution": "Bands are not official project classifications.",
            },
        ]
    )
