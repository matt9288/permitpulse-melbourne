from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from permitpulse.pipeline import SchemaError, build_pipeline, geocode_permit_families


def _source_rows() -> list[dict[str, object]]:
    common = {
        "rbs_number": "RBS-1",
        "commence_by_date": "2025-12-01",
        "completed_by_date": "2027-12-01",
    }
    return [
        {
            **common,
            "council_ref": "BP-1",
            "permit_number": "P-1",
            "issue_date": "2025-01-10",
            "address": "1 TEST STREET, MELBOURNE VIC 3000",
            "desc_of_works": "Office fitout",
            "estimated_cost_of_works": 100000,
            "permit_certificate_type": "Building Permit",
        },
        {
            **common,
            "council_ref": "BP-1",
            "permit_number": "P-1",
            "issue_date": "2025-01-10",
            "address": "2 TEST STREET, MELBOURNE VIC 3000",
            "desc_of_works": "Office fitout",
            "estimated_cost_of_works": 100000,
            "permit_certificate_type": "Building Permit",
        },
        {
            **common,
            "council_ref": "BP-1",
            "permit_number": "P-1",
            "issue_date": "2025-08-01",
            "address": "1 TEST STREET, MELBOURNE VIC 3000",
            "desc_of_works": "Office fitout",
            "estimated_cost_of_works": 100000,
            "permit_certificate_type": "Certificate of Final Inspection",
        },
        {
            **common,
            "council_ref": "BP-2",
            "permit_number": "P-2",
            "issue_date": "2025-03-01",
            "address": "3 TEST STREET, CARLTON VIC 3053",
            "desc_of_works": "Alterations",
            "estimated_cost_of_works": -50,
            "permit_certificate_type": "Building Permit",
        },
        {
            **common,
            "council_ref": "BP-3",
            "permit_number": "P-3",
            "issue_date": "2027-01-01",
            "address": "4 TEST STREET, PARKVILLE VIC 3052",
            "desc_of_works": "New building",
            "estimated_cost_of_works": 500000,
            "permit_certificate_type": "Building Permit",
        },
    ]


def test_pipeline_deduplicates_permit_families_and_quarantines_invalid_rows(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.csv"
    pd.DataFrame(_source_rows()).to_csv(source, index=False)
    address_source = tmp_path / "street-addresses.csv"
    pd.DataFrame(
        {
            "street_no": ["1", "2", "3", "4"],
            "str_name": ["Test Street"] * 4,
            "suburb": ["Melbourne", "Melbourne", "Carlton", "Parkville"],
            "latitude": [-37.810, -37.811, -37.800, -37.790],
            "longitude": [144.960, 144.961, 144.970, 144.950],
        }
    ).to_csv(address_source, index=False)
    output = tmp_path / "processed"

    summary = build_pipeline(
        source,
        output,
        as_of=date(2026, 10, 1),
        address_source_path=address_source,
    )

    assert summary.raw_rows == 5
    assert summary.permit_families == 3
    assert summary.analytic_permits == 1
    assert summary.certificate_events == 4
    assert summary.permit_addresses == 4
    assert summary.geocoded_permits == 1

    metadata = json.loads((output / "source_metadata.json").read_text(encoding="utf-8"))
    serialised_metadata = json.dumps(metadata)
    assert str(tmp_path) not in serialised_metadata
    assert metadata["source_file"] == "source.csv"
    assert metadata["geospatial_source"]["source_file"] == "street-addresses.csv"

    with duckdb.connect(str(output / "permitpulse.duckdb"), read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM permit_families").fetchone()[0] == 3
        assert connection.execute(
            "SELECT COUNT(*) = COUNT(DISTINCT council_ref) FROM permit_families"
        ).fetchone()[0]
        assert (
            connection.execute(
                "SELECT estimated_cost FROM permit_families WHERE council_ref = 'BP-1'"
            ).fetchone()[0]
            == 100000
        )
        assert connection.execute(
            "SELECT cost_band, work_category_rule FROM permit_families WHERE council_ref = 'BP-1'"
        ).fetchone() == ("$50k–$250k", "Fit-out / tenancy")
        rule_ids = {
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT rule_id FROM quarantine_records"
            ).fetchall()
        }
        assert {"negative_estimated_cost", "future_issue_date"} <= rule_ids


def test_pipeline_rejects_missing_required_columns(tmp_path: Path) -> None:
    source = tmp_path / "bad.csv"
    pd.DataFrame({"council_ref": ["BP-1"]}).to_csv(source, index=False)

    with pytest.raises(SchemaError, match="missing required columns"):
        build_pipeline(source, tmp_path / "processed", as_of=date(2026, 10, 1))


def test_geocoder_uses_official_points_for_exact_addresses_and_ranges(
    tmp_path: Path,
) -> None:
    families = pd.DataFrame(
        {
            "council_ref": ["BP-1", "BP-2", "BP-3"],
            "primary_address": [
                "10 Test Street, MELBOURNE VIC 3000",
                "Example Site, 20-24 Test Street, MELBOURNE VIC 3000",
                "1 Missing Road, MELBOURNE VIC 3000",
            ],
            "suburb": ["MELBOURNE", "MELBOURNE", "MELBOURNE"],
        }
    )
    address_source = tmp_path / "street-addresses.csv"
    pd.DataFrame(
        {
            "street_no": ["10", "20", "22", "24"],
            "str_name": ["Test Street"] * 4,
            "suburb": ["Melbourne"] * 4,
            "latitude": [-37.810, -37.820, -37.822, -37.824],
            "longitude": [144.960, 144.970, 144.972, 144.974],
        }
    ).to_csv(address_source, index=False)

    located = geocode_permit_families(families, address_source)

    assert located.loc[0, "geocode_method"] == "exact address point"
    assert located.loc[0, "latitude"] == pytest.approx(-37.810)
    assert located.loc[1, "geocode_method"] == "range centroid"
    assert located.loc[1, "latitude"] == pytest.approx(-37.822)
    assert located.loc[1, "longitude"] == pytest.approx(144.972)
    assert located.loc[2, "geocode_method"] == "unmatched"
    assert pd.isna(located.loc[2, "latitude"])
