from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_FILES = [
    PROJECT_ROOT / "data" / "processed" / "analytic_permits.parquet",
    PROJECT_ROOT / "data" / "processed" / "data_quality_results.parquet",
    PROJECT_ROOT / "data" / "processed" / "source_metadata.json",
]


def test_public_runtime_bundle_is_present_and_contains_no_local_paths() -> None:
    missing = [path.name for path in RUNTIME_FILES if not path.exists()]
    assert not missing, f"Missing deployment runtime files: {', '.join(missing)}"

    metadata = json.loads(RUNTIME_FILES[-1].read_text(encoding="utf-8"))
    serialised = json.dumps(metadata)
    assert "/Users/" not in serialised
    assert "source_path" not in serialised
    assert "output_dir" not in serialised
    assert metadata["source_file"] == "BPC annual building-permit workbooks"
    assert metadata["project_scope"] == "Victoria"
    assert metadata["geospatial_source"]["source_file"] == "victoria_lga_simplified.geojson"


def test_statewide_runtime_reconciles_to_annual_source_controls() -> None:
    with duckdb.connect() as connection:
        annual = connection.execute(
            """
            SELECT report_year, count(*) AS records, sum(estimated_cost) AS reported_cost
            FROM read_parquet(?)
            GROUP BY report_year
            ORDER BY report_year
            """,
            [str(RUNTIME_FILES[0])],
        ).fetchall()

    assert annual == [
        (2018, 113_287, 39_610_817_091.0),
        (2019, 101_988, 38_284_048_987.0),
        (2020, 113_430, 40_810_014_295.0),
        (2021, 127_792, 44_635_012_065.0),
        (2022, 113_625, 47_496_953_575.0),
        (2023, 100_035, 48_301_000_994.0),
        (2024, 100_400, 49_990_056_504.0),
        (2025, 100_710, 57_750_334_113.0),
    ]


def test_public_runtime_excludes_unused_location_and_builder_fields() -> None:
    with duckdb.connect() as connection:
        columns = {
            row[0]
            for row in connection.execute(
                "DESCRIBE SELECT * FROM read_parquet(?)", [str(RUNTIME_FILES[0])]
            ).fetchall()
        }

    assert "street_name" not in columns
    assert not any(column.startswith("builder") for column in columns)


def test_new_dwelling_quality_checks_separate_unavailable_and_missing_values() -> None:
    with duckdb.connect() as connection:
        checks = dict(
            connection.execute(
                """
                SELECT check_id, affected_rows
                FROM read_parquet(?)
                WHERE check_id IN (
                    'new_dwellings_source_unavailable',
                    'missing_new_dwellings_when_available'
                )
                """,
                [str(RUNTIME_FILES[1])],
            ).fetchall()
        )

    assert checks == {
        "new_dwellings_source_unavailable": 215_275,
        "missing_new_dwellings_when_available": 39_677,
    }


def test_deployment_entrypoint_loads_from_repository_root() -> None:
    app = AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=60).run()

    assert not app.exception
    assert app.title[0].value == "PermitPulse Victoria"
    assert len(app.get("plotly_chart")) == 6
    assert any(radio.label == "Map measure" for radio in app.radio)
    assert any(radio.label == "Cost range aggregation" for radio in app.radio)
    assert any(radio.label == "Comparison measure" for radio in app.radio)
    assert any(selectbox.label == "Focus year" for selectbox in app.selectbox)
    assert any(selectbox.label == "Baseline year" for selectbox in app.selectbox)
    assert any(
        expander.label == "Metric definitions and responsible use" for expander in app.expander
    )


def test_cost_view_accepts_detailed_aggregation_and_non_adjacent_years() -> None:
    app = AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=60).run()

    next(radio for radio in app.radio if radio.label == "Cost range aggregation").set_value(
        "Detailed ranges"
    )
    next(selectbox for selectbox in app.selectbox if selectbox.label == "Focus year").set_value(
        2023
    )
    app.run()
    next(selectbox for selectbox in app.selectbox if selectbox.label == "Baseline year").set_value(
        2019
    )
    next(radio for radio in app.radio if radio.label == "Comparison measure").set_value(
        "Total reported cost"
    )
    app.run()

    assert not app.exception
    assert (
        next(selectbox for selectbox in app.selectbox if selectbox.label == "Focus year").value
        == 2023
    )
    assert (
        next(selectbox for selectbox in app.selectbox if selectbox.label == "Baseline year").value
        == 2019
    )


def test_cost_view_avoids_year_comparison_for_a_single_reporting_year() -> None:
    app = AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=60).run()

    app.date_input[0].set_value((date(2025, 1, 1), date(2025, 12, 31)))
    app.run()

    assert not app.exception
    assert not any(selectbox.label == "Focus year" for selectbox in app.selectbox)
    assert not any(selectbox.label == "Baseline year" for selectbox in app.selectbox)
    assert any(
        "Year comparison uses BPC reporting year" in caption.value for caption in app.caption
    )


def test_legacy_period_explains_unavailable_new_dwelling_map() -> None:
    app = AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=60).run()

    app.date_input[0].set_value((date(2018, 1, 1), date(2018, 12, 31)))
    app.run()
    next(radio for radio in app.radio if radio.label == "Map measure").set_value("New dwellings")
    app.run()

    assert not app.exception
    assert any("New dwellings data is unavailable" in message.value for message in app.info)
