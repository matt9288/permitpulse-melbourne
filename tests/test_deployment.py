from __future__ import annotations

import json
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
    assert len(app.get("plotly_chart")) == 6
    assert any(selectbox.label == "Broad range to investigate" for selectbox in app.selectbox)
    assert any(
        expander.label == "Metric definitions and responsible use" for expander in app.expander
    )
