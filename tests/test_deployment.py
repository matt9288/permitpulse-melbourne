from __future__ import annotations

import json
from datetime import date
from pathlib import Path

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
    assert metadata["source_file"] == "building-permits.csv"
    assert metadata["geospatial_source"]["source_file"] == "street-addresses.csv"


def test_deployment_entrypoint_loads_from_repository_root() -> None:
    app = AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=30).run()

    assert not app.exception
    assert len(app.get("plotly_chart")) == 5
    assert any(radio.label == "Cost range aggregation" for radio in app.radio)
    assert any(radio.label == "Comparison measure" for radio in app.radio)
    assert any(selectbox.label == "Focus year" for selectbox in app.selectbox)
    assert any(selectbox.label == "Baseline year" for selectbox in app.selectbox)
    assert any(
        expander.label == "Metric definitions and responsible use" for expander in app.expander
    )


def test_cost_view_accepts_detailed_aggregation_and_non_default_years() -> None:
    app = AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=30).run()

    next(radio for radio in app.radio if radio.label == "Cost range aggregation").set_value(
        "Detailed ranges"
    )
    next(selectbox for selectbox in app.selectbox if selectbox.label == "Focus year").set_value(
        2023
    )
    app.run()
    next(
        selectbox for selectbox in app.selectbox if selectbox.label == "Baseline year"
    ).set_value(2021)
    next(radio for radio in app.radio if radio.label == "Comparison measure").set_value(
        "Total estimated cost"
    )
    app.run()

    assert not app.exception
    assert next(
        selectbox for selectbox in app.selectbox if selectbox.label == "Focus year"
    ).value == 2023
    assert next(
        selectbox for selectbox in app.selectbox if selectbox.label == "Baseline year"
    ).value == 2021


def test_cost_view_avoids_year_comparison_for_a_single_complete_year() -> None:
    app = AppTest.from_file(PROJECT_ROOT / "app.py", default_timeout=30).run()

    app.date_input[0].set_value((date(2025, 1, 1), date(2025, 12, 31)))
    app.run()

    assert not app.exception
    assert not any(selectbox.label == "Focus year" for selectbox in app.selectbox)
    assert not any(selectbox.label == "Baseline year" for selectbox in app.selectbox)
    assert any(
        "fewer than two complete calendar years" in caption.value
        for caption in app.caption
    )
