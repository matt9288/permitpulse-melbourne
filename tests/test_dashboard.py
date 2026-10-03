from datetime import date

import pandas as pd

from permitpulse.dashboard import (
    DashboardFilters,
    apply_filters,
    complete_year_pair,
    cost_band_counts,
    headline_metrics,
    metric_glossary,
    monthly_activity,
    opportunity_benchmarks,
    permit_map_points,
    priority_permits,
    suburb_opportunity_summary,
)


def _permits() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "council_ref": ["BP-1", "BP-2", "BP-3"],
            "permit_issue_date": pd.to_datetime(["2024-01-10", "2024-02-10", "2025-01-01"]),
            "issue_month": pd.to_datetime(["2024-01-01", "2024-02-01", "2025-01-01"]),
            "suburb": ["MELBOURNE", "CARLTON", "MELBOURNE"],
            "cost_band": ["$50k–$250k", ">$10m", "$1–$50k"],
            "estimated_cost": [100_000, 20_000_000, 25_000],
            "work_category_rule": [
                "Fit-out / tenancy",
                "New construction",
                "Fit-out / tenancy",
            ],
            "desc_of_works": ["Office fitout", "New building", "Shop fit-out"],
            "primary_address": ["1 Test St", "2 Test St", "3 Test St"],
            "latitude": [-37.81, -37.80, pd.NA],
            "longitude": [144.96, 144.97, pd.NA],
            "geocode_method": ["exact address point", "range centroid", "unmatched"],
        }
    )


def test_filters_apply_one_population_to_metrics_and_trend() -> None:
    frame = _permits()
    filters = DashboardFilters(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        suburbs=("MELBOURNE",),
        work_categories=("Fit-out / tenancy",),
    )

    filtered = apply_filters(frame, filters)
    metrics = headline_metrics(filtered)
    trend = monthly_activity(filtered)

    assert filtered["council_ref"].tolist() == ["BP-1"]
    assert metrics["permits"] == 1
    assert metrics["median_positive_cost"] == 100_000
    assert trend["permits"].sum() == 1


def test_cost_band_counts_reconcile_to_selected_permits() -> None:
    counts = cost_band_counts(_permits())

    assert counts["permits"].sum() == 3
    assert counts.loc[counts["cost_band"] == ">$10m", "permits"].iloc[0] == 1


def test_map_points_reconcile_to_mapped_permits() -> None:
    frame = _permits()

    points = permit_map_points(frame)

    assert points["permits"].sum() == 2


def test_complete_year_pair_requires_two_full_years() -> None:
    assert complete_year_pair(date(2018, 1, 1), date(2025, 12, 31), date(2026, 10, 1)) == (
        2025,
        2024,
    )
    assert complete_year_pair(date(2024, 6, 1), date(2025, 12, 31), date(2026, 10, 1)) is None


def test_opportunity_profile_reconciles_activity_value_and_work_mix() -> None:
    frame = _permits()

    summary = suburb_opportunity_summary(frame, current_year=2025, previous_year=2024)
    benchmarks = opportunity_benchmarks(frame, current_year=2025)
    priority = priority_permits(frame, current_year=2024, limit=1)

    melbourne = summary.loc[summary["suburb"] == "MELBOURNE"].iloc[0]
    assert melbourne["current_permits"] == 1
    assert melbourne["previous_permits"] == 1
    assert melbourne["activity_change"] == 0
    assert melbourne["dominant_work_category"] == "Fit-out / tenancy"
    assert melbourne["dominant_category_share"] == 1
    assert benchmarks["permits"] == 1
    assert benchmarks["median_positive_cost"] == 25_000
    assert priority.loc[0, "council_ref"] == "BP-2"


def test_metric_glossary_covers_displayed_metrics_with_unique_terms() -> None:
    glossary = metric_glossary()
    required_terms = {
        "Unique building permits",
        "Median positive estimated cost",
        "Share above $10m",
        "Activity change",
        "Dominant work category",
        "Top category share",
        "Municipality benchmark",
        "Priority permit records",
        "Permit hotspot",
        "Mapped share",
    }

    assert required_terms <= set(glossary["term"])
    assert glossary["term"].is_unique
    assert not glossary[["term", "explanation", "formula_or_rule"]].isna().any().any()
