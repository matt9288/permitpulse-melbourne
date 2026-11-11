from datetime import date

import pandas as pd

from permitpulse.statewide_dashboard import (
    StatewideFilters,
    apply_statewide_filters,
    category_summary,
    cost_comparison,
    headline_metrics,
    monthly_activity,
    municipality_map_summary,
    municipality_summary,
    unavailable_category_records,
)
from permitpulse.statewide_pipeline import (
    _parse_excel_date,
    municipality_map_name,
    normalise_building_use,
)


def _records() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "record_id": ["A", "B", "C", "D"],
            "report_year": [2024, 2024, 2025, 2025],
            "report_month": pd.to_datetime(
                ["2024-01-01", "2024-02-01", "2025-01-01", "2025-02-01"]
            ),
            "municipality": [
                "Melbourne, City of",
                "Greater Geelong, City of",
                "Melbourne, City of",
                "Greater Geelong, City of",
            ],
            "municipality_map_name": [
                "MELBOURNE",
                "GREATER GEELONG",
                "MELBOURNE",
                "GREATER GEELONG",
            ],
            "region": ["Metropolitan", "Rural", "Metropolitan", "Rural"],
            "suburb": ["MELBOURNE", "GEELONG", "MELBOURNE", "GEELONG"],
            "street_name": ["A Street", "B Street", "A Street", "B Street"],
            "cost_band": ["$50k–$250k", "$250k–$1m", "$50k–$250k", "> $10m"],
            "estimated_cost": [100_000, 500_000, 200_000, 20_000_000],
            "nature_of_work": ["Alteration", "New building", "Alteration", "New building"],
            "building_use": ["Commercial", "Domestic", "Commercial", "Domestic"],
            "new_dwellings": [0, 2, 0, 10],
            "dwellings_demolished": [0, 0, 0, 1],
        }
    )


def test_statewide_filters_and_metrics_use_source_record_grain() -> None:
    filtered = apply_statewide_filters(
        _records(),
        StatewideFilters(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            regions=("Rural",),
            nature_of_work=("New building",),
        ),
    )

    metrics = headline_metrics(filtered)

    assert filtered["record_id"].tolist() == ["D"]
    assert metrics["records"] == 1
    assert metrics["reported_cost"] == 20_000_000
    assert metrics["new_dwellings"] == 10


def test_municipality_summary_and_map_reconcile_to_filtered_records() -> None:
    frame = _records()

    profile = municipality_summary(frame, 2025, 2024)
    mapped = municipality_map_summary(frame)

    geelong = profile.loc[profile["municipality"] == "Greater Geelong, City of"].iloc[0]
    assert geelong["focus_records"] == 1
    assert geelong["baseline_records"] == 1
    assert geelong["record_change"] == 0
    assert geelong["new_dwellings"] == 10
    assert geelong["reported_net_dwellings"] == 9
    assert geelong["net_dwelling_coverage"] == 1
    assert geelong["baseline_total_reported_cost"] == 500_000
    assert geelong["reported_cost_change"] == 39
    assert mapped["records"].sum() == len(frame)


def test_reported_net_dwellings_stays_unavailable_without_comparable_fields() -> None:
    legacy = _records().copy()
    legacy["report_year"] = 2019
    legacy["new_dwellings"] = pd.Series([pd.NA] * len(legacy), dtype="Int64")

    profile = municipality_summary(legacy, 2019)

    assert profile["reported_net_dwellings"].isna().all()
    assert profile["net_dwelling_coverage"].eq(0).all()


def test_monthly_activity_uses_complete_calendar_windows_for_12_month_average() -> None:
    activity = monthly_activity(_records())

    december_2024 = activity.loc[activity["report_month"] == pd.Timestamp("2024-12-01")].iloc[0]
    assert len(activity) == 14
    assert activity["records_12m_average"].iloc[:11].isna().all()
    assert december_2024["records_12m_average"] == 2 / 12
    assert december_2024["reported_cost_12m_average"] == 600_000 / 12


def test_category_summary_can_hide_unknown_and_unavailable_values() -> None:
    frame = _records().copy()
    frame["building_use"] = ["Commercial", "Unknown", "Unavailable in source year", pd.NA]

    summary = category_summary(frame, "building_use", hide_unavailable=True)

    assert summary[["building_use", "records"]].to_dict("records") == [
        {"building_use": "Commercial", "records": 1}
    ]
    assert unavailable_category_records(frame, "building_use") == 3


def test_statewide_cost_comparison_uses_reporting_year() -> None:
    comparison = cost_comparison(_records(), 2025, 2024, detailed=True)

    band = comparison.loc[comparison["cost_range"] == "$50k–$100k"].iloc[0]
    assert band["baseline_records"] == 1
    assert band["focus_records"] == 0
    assert comparison["focus_records"].sum() == 2
    assert comparison["baseline_records"].sum() == 2


def test_bpc_municipality_labels_map_to_vicmap_names() -> None:
    assert municipality_map_name("Colac-Otway, Shire of") == "COLAC OTWAY"
    assert municipality_map_name("Mt Buller Alpine Resort") == "MOUNT BULLER ALPINE RESORT (UNINC)"
    assert municipality_map_name("Melbourne, City of") == "MELBOURNE"
    assert municipality_map_name("Moreland, City of") == "MERRI-BEK"
    assert (
        municipality_map_name("Lake Mountain Alpine Resort")
        == "LAKE MOUNTAIN ALPINE RESORT (UNINC)"
    )


def test_legacy_excel_serial_dates_are_parsed_without_1970_nanosecond_dates() -> None:
    parsed = _parse_excel_date(pd.Series([43_853, 3, None], dtype="object"))

    assert parsed.iloc[0].year == 2020
    assert pd.isna(parsed.iloc[1])
    assert pd.isna(parsed.iloc[2])


def test_building_use_capitalisation_variants_are_merged() -> None:
    normalised = normalise_building_use(
        pd.Series(
            [
                "Public Buildings",
                "Public buildings",
                "public Buildings",
                " commercial ",
                "Unexpected source label",
                None,
            ]
        )
    )

    assert normalised.tolist() == [
        "Public Buildings",
        "Public Buildings",
        "Public Buildings",
        "Commercial",
        "Unexpected source label",
        "Unavailable in source year",
    ]
