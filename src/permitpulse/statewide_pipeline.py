from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pandas as pd

from permitpulse.pipeline import COST_BAND_ORDER

DATASET_URL = "https://discover.data.vic.gov.au/dataset/building-permit-activity-data"
BPC_DATA_URL = "https://www.bpc.vic.gov.au/about-bpc/research-reports-and-data/data"
VICMAP_URL = "https://discover.data.vic.gov.au/dataset/vicmap-admin-rest-api"

NATURE_OF_WORK = {
    "1": "New building",
    "2": "Re-erection",
    "3": "Extension",
    "4": "Alteration",
    "5": "Change of use",
    "6": "Demolition",
    "7": "Removal",
    "8": "Other",
}

OWNERSHIP_SECTOR = {
    "P": "Private",
    "L": "Local government",
    "S": "State government",
    "C": "Commonwealth government",
}

COLUMN_ALIASES = {
    "permit_stage_number": ["permit_stage_number"],
    "permit_issue_date": ["permit_date"],
    "report_year": ["BASIS_Month_Y"],
    "report_month_number": ["BASIS_Month_M"],
    "levy_paid": ["Original_Levy_Paid__c"],
    "estimated_cost": ["Reported_Cost_of_works"],
    "street_name": ["Site_street_name", "Cleaned_site_street_name"],
    "suburb": ["site_town_suburb__c"],
    "postcode": ["site_postcode__c"],
    "municipality_code": ["Site_Municipality"],
    "municipality": ["Municipal Full Name"],
    "region": ["Region"],
    "sub_region": ["Sub_Region"],
    "allotment_area": ["Allotment_Area__c"],
    "existing_dwellings": ["Number_of_Existing_Dwellings__c"],
    "new_dwellings": ["Number_of_New_Dwellings__c"],
    "storeys": ["Number_of_Storeys__c"],
    "dwellings_demolished": ["Number_of_Dwellings_Demolished__c"],
    "floor_area": ["Total_Floor_Area__c"],
    "application_date": ["Building_Permit_Application_Date__c"],
    "project_total_estimated_cost": ["Total_Estimated_Cost_of_Works__c"],
    "building_use": ["BASIS_Building_Use"],
    "nature_of_work_code": ["BASIS_NOW"],
    "bca_class": ["BASIS_BCA"],
    "ownership_sector_code": ["BASIS_Ownership_Sector"],
}

REQUIRED_CANONICAL_COLUMNS = {
    "permit_issue_date",
    "report_year",
    "report_month_number",
    "estimated_cost",
    "street_name",
    "suburb",
    "municipality",
    "region",
    "building_use",
    "nature_of_work_code",
    "bca_class",
}

OFFICIAL_ANNUAL_TOTALS = {
    2024: {"records": 100_400, "reported_cost": 49_990_056_504.0},
    2025: {"records": 100_710, "reported_cost": 57_750_334_113.0},
}


class StatewideSchemaError(ValueError):
    """Raised when a BPC annual workbook no longer satisfies the expected schema."""


@dataclass(frozen=True)
class StatewideBuildSummary:
    source_files: tuple[str, ...]
    as_of_date: str
    records: int
    report_years: tuple[int, ...]
    municipalities: int
    suburbs: int
    reported_cost: float
    quality_warnings: int
    output_dir: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalise_text(series: pd.Series, upper: bool = False) -> pd.Series:
    values = series.astype("string").str.strip().replace("", pd.NA)
    return values.str.upper() if upper else values


def municipality_map_name(value: object) -> str | None:
    """Convert BPC municipality labels to Vicmap LGA feature names."""
    if pd.isna(value):
        return None
    name = str(value).split(",", maxsplit=1)[0].strip().upper()
    aliases = {
        "COLAC-OTWAY": "COLAC OTWAY",
        "FALLS CREEK ALPINE RESORT": "FALLS CREEK ALPINE RESORT (UNINC)",
        "MT BAW BAW ALPINE RESORT": "MOUNT BAW BAW ALPINE RESORT (UNINC)",
        "MT BULLER ALPINE RESORT": "MOUNT BULLER ALPINE RESORT (UNINC)",
        "MT HOTHAM ALPINE RESORT": "MOUNT HOTHAM ALPINE RESORT (UNINC)",
    }
    return aliases.get(name, name)


def _find_data_sheet(path: Path) -> str:
    workbook = pd.ExcelFile(path, engine="calamine")
    for sheet_name in workbook.sheet_names:
        sample = pd.read_excel(path, sheet_name=sheet_name, engine="calamine", nrows=2)
        if {"permit_date", "BASIS_Month_Y", "Reported_Cost_of_works"} <= set(sample.columns):
            return sheet_name
    raise StatewideSchemaError(f"No building-permit data sheet found in {path.name}.")


def _resolve_columns(columns: list[str]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        source = next((alias for alias in aliases if alias in columns), None)
        if source:
            resolved[canonical] = source
    missing = sorted(REQUIRED_CANONICAL_COLUMNS - set(resolved))
    if missing:
        raise StatewideSchemaError(
            "Statewide source is missing required fields: " + ", ".join(missing)
        )
    return resolved


def _cost_band(cost: pd.Series) -> pd.Series:
    bands = pd.cut(
        pd.to_numeric(cost, errors="coerce"),
        bins=[float("-inf"), 0, 50_000, 250_000, 1_000_000, 10_000_000, float("inf")],
        labels=COST_BAND_ORDER[:-1],
        include_lowest=True,
    ).astype("string")
    return bands.fillna("Missing")


def read_statewide_workbook(path: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    path = path.resolve()
    sheet_name = _find_data_sheet(path)
    source = pd.read_excel(path, sheet_name=sheet_name, engine="calamine")
    source.columns = [str(column).strip() for column in source.columns]
    resolved = _resolve_columns(source.columns.tolist())

    frame = pd.DataFrame(index=source.index)
    for canonical, source_column in resolved.items():
        frame[canonical] = source[source_column]
    for canonical in COLUMN_ALIASES:
        if canonical not in frame:
            frame[canonical] = pd.NA

    frame["permit_issue_date"] = pd.to_datetime(frame["permit_issue_date"], errors="coerce")
    frame["application_date"] = pd.to_datetime(frame["application_date"], errors="coerce")
    for column in [
        "report_year",
        "report_month_number",
        "permit_stage_number",
        "existing_dwellings",
        "new_dwellings",
        "storeys",
        "dwellings_demolished",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Int64")
    for column in [
        "levy_paid",
        "estimated_cost",
        "project_total_estimated_cost",
        "allotment_area",
        "floor_area",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Float64")

    frame["street_name"] = _normalise_text(frame["street_name"])
    frame["suburb"] = _normalise_text(frame["suburb"], upper=True)
    frame["postcode"] = _normalise_text(frame["postcode"]).str.replace(r"\.0$", "", regex=True)
    frame["municipality"] = _normalise_text(frame["municipality"])
    frame["municipality_map_name"] = (
        frame["municipality"].map(municipality_map_name).astype("string")
    )
    frame["region"] = _normalise_text(frame["region"])
    frame["sub_region"] = _normalise_text(frame["sub_region"])
    frame["building_use"] = _normalise_text(frame["building_use"])
    frame["bca_class"] = _normalise_text(frame["bca_class"])
    frame["nature_of_work_code"] = _normalise_text(frame["nature_of_work_code"]).str.replace(
        r"\.0$", "", regex=True
    )
    frame["nature_of_work"] = frame["nature_of_work_code"].map(NATURE_OF_WORK).fillna("Unknown")
    frame["ownership_sector_code"] = _normalise_text(frame["ownership_sector_code"], upper=True)
    frame["ownership_sector"] = (
        frame["ownership_sector_code"].map(OWNERSHIP_SECTOR).fillna("Unknown")
    )
    frame["report_month"] = pd.to_datetime(
        {
            "year": frame["report_year"].astype("Float64"),
            "month": frame["report_month_number"].astype("Float64"),
            "day": 1,
        },
        errors="coerce",
    )
    frame["issue_month"] = frame["permit_issue_date"].dt.to_period("M").dt.to_timestamp()
    frame["cost_band"] = _cost_band(frame["estimated_cost"])

    report_years = sorted(frame["report_year"].dropna().astype(int).unique().tolist())
    source_year = report_years[0] if len(report_years) == 1 else 0
    source_tag = hashlib.sha256(path.name.encode("utf-8")).hexdigest()[:8]
    frame.insert(
        0,
        "record_id",
        [
            f"BPC-{source_year}-{source_tag}-{row_number:06d}"
            for row_number in range(1, len(frame) + 1)
        ],
    )
    frame["source_file"] = path.name
    frame["source_row_number"] = pd.RangeIndex(start=2, stop=len(frame) + 2)

    ordered_columns = [
        "record_id",
        "report_year",
        "report_month_number",
        "report_month",
        "permit_issue_date",
        "issue_month",
        "application_date",
        "permit_stage_number",
        "municipality",
        "municipality_map_name",
        "region",
        "sub_region",
        "suburb",
        "postcode",
        "street_name",
        "estimated_cost",
        "project_total_estimated_cost",
        "cost_band",
        "levy_paid",
        "building_use",
        "nature_of_work_code",
        "nature_of_work",
        "bca_class",
        "ownership_sector_code",
        "ownership_sector",
        "existing_dwellings",
        "new_dwellings",
        "dwellings_demolished",
        "storeys",
        "floor_area",
        "allotment_area",
        "municipality_code",
        "source_file",
        "source_row_number",
    ]
    metadata = {
        "source_file": path.name,
        "source_sha256": sha256_file(path),
        "sheet_name": sheet_name,
        "rows": len(frame),
        "columns": len(source.columns),
        "report_years": report_years,
        "street_column": resolved["street_name"],
    }
    return frame[ordered_columns], metadata


def _quality_results(frame: pd.DataFrame) -> pd.DataFrame:
    total = len(frame)
    comparisons = frame[
        [
            "permit_stage_number",
            "permit_issue_date",
            "report_year",
            "report_month_number",
            "estimated_cost",
            "street_name",
            "suburb",
            "postcode",
            "municipality",
            "region",
            "building_use",
            "nature_of_work_code",
            "bca_class",
        ]
    ]
    duplicate_looking = int(comparisons.duplicated(keep=False).sum())
    date_mismatch = int(
        (
            frame["permit_issue_date"].notna()
            & frame["report_year"].notna()
            & (frame["permit_issue_date"].dt.year != frame["report_year"])
        ).sum()
    )

    checks = [
        (
            "missing_issue_date",
            int(frame["permit_issue_date"].isna().sum()),
            "medium",
            "Permit issue date is missing or invalid. Reporting-period analysis still "
            "includes the record.",
        ),
        (
            "issue_year_differs_from_report_year",
            date_mismatch,
            "medium",
            "Issue year differs from the levy reporting year. This may reflect delayed "
            "reporting or source corrections.",
        ),
        (
            "duplicate_looking_rows",
            duplicate_looking,
            "medium",
            "Rows match on the public analytical fields. They are retained because the "
            "source has no permit identifier.",
        ),
        (
            "missing_reported_cost",
            int(frame["estimated_cost"].isna().sum()),
            "medium",
            "Reported cost is missing.",
        ),
        (
            "nonpositive_reported_cost",
            int((frame["estimated_cost"].fillna(1) <= 0).sum()),
            "low",
            "Reported cost is zero or negative and is excluded from positive-cost medians.",
        ),
        (
            "missing_municipality",
            int(frame["municipality"].isna().sum()),
            "high",
            "Municipality is missing, preventing local comparison and mapping.",
        ),
    ]
    rows: list[dict[str, object]] = []
    for check_id, affected, severity, details in checks:
        rows.append(
            {
                "check_id": check_id,
                "status": "warn" if affected else "pass",
                "severity": severity,
                "affected_rows": affected,
                "affected_rate": affected / total if total else 0.0,
                "metric_value": affected,
                "metric_unit": "records",
                "details": details,
            }
        )

    for year, expected in OFFICIAL_ANNUAL_TOTALS.items():
        period = frame.loc[frame["report_year"] == year]
        if period.empty:
            continue
        actual_records = len(period)
        actual_cost = float(period["estimated_cost"].sum())
        records_match = actual_records == expected["records"]
        cost_match = abs(actual_cost - expected["reported_cost"]) < 0.5
        rows.append(
            {
                "check_id": f"official_summary_reconciliation_{year}",
                "status": "pass" if records_match and cost_match else "warn",
                "severity": "high",
                "affected_rows": 0 if records_match and cost_match else actual_records,
                "affected_rate": 0.0 if records_match and cost_match else 1.0,
                "metric_value": actual_cost,
                "metric_unit": "reported cost dollars",
                "details": (
                    f"Raw file contains {actual_records:,} records and ${actual_cost:,.0f}; "
                    f"official summary reports {expected['records']:,} and "
                    f"${expected['reported_cost']:,.0f}."
                ),
            }
        )
    return pd.DataFrame(rows)


def _write_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect() as connection:
        connection.register("output_frame", frame)
        connection.execute("COPY output_frame TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(path)])


def build_statewide_pipeline(
    source_paths: list[Path],
    output_dir: Path,
    as_of: date | None = None,
) -> StatewideBuildSummary:
    if not source_paths:
        raise ValueError("At least one statewide BPC workbook is required.")
    as_of = as_of or date.today()
    frames: list[pd.DataFrame] = []
    sources: list[dict[str, object]] = []
    for source_path in source_paths:
        frame, source_metadata = read_statewide_workbook(source_path)
        frames.append(frame)
        sources.append(source_metadata)
    records = pd.concat(frames, ignore_index=True)
    records = records.sort_values(
        ["report_year", "report_month_number", "municipality", "record_id"],
        na_position="last",
    ).reset_index(drop=True)
    if records["record_id"].duplicated().any():
        raise StatewideSchemaError("Synthetic record IDs are not unique across the supplied files.")

    quality = _quality_results(records)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_parquet(records, output_dir / "analytic_permits.parquet")
    _write_parquet(quality, output_dir / "data_quality_results.parquet")

    report_years = tuple(sorted(records["report_year"].dropna().astype(int).unique().tolist()))
    annual = []
    for year, period in records.groupby("report_year", dropna=False):
        if pd.isna(year):
            continue
        annual.append(
            {
                "report_year": int(year),
                "records": len(period),
                "reported_cost": float(period["estimated_cost"].sum()),
            }
        )
    metadata = {
        "project_scope": "Victoria",
        "as_of_date": as_of.isoformat(),
        "built_at_utc": datetime.now(UTC).isoformat(),
        "source_file": "BPC annual building-permit workbooks",
        "source_dataset": "Building Permit Activity Data",
        "source_url": DATASET_URL,
        "publisher_url": BPC_DATA_URL,
        "licence": "Creative Commons Attribution 4.0",
        "data_model": (
            "One row per source-reported permit activity record. The public files do not include "
            "a permit identifier, so records are not deduplicated and are not described as "
            "unique permits."
        ),
        "primary_period": (
            "BPC levy reporting month and year. Permit issue date is retained separately and may "
            "fall outside the reporting year."
        ),
        "sources": sources,
        "geospatial_source": {
            "dataset": "Vicmap Admin Local Government Area boundaries",
            "source_file": "victoria_lga_simplified.geojson",
            "source_url": VICMAP_URL,
            "licence": "Creative Commons Attribution 4.0",
            "geometry_note": (
                "Official polygons simplified to 0.002 degrees for dashboard performance."
            ),
        },
        "summary": {
            "records": len(records),
            "report_years": list(report_years),
            "municipalities": int(records["municipality"].nunique()),
            "suburbs": int(records["suburb"].nunique()),
            "reported_cost": float(records["estimated_cost"].sum()),
            "annual": annual,
        },
        "limitations": [
            "No public permit identifier is present, so similar-looking rows cannot be safely "
            "deduplicated.",
            "The source contains issued permit activity, not refused or not-granted applications.",
            "The source has street names but no street numbers or coordinates; the map is "
            "aggregated to municipality boundaries.",
            "Reported cost is an estimate, not realised expenditure, contract value or revenue.",
            "Data quality depends on information submitted by building surveyors to the regulator.",
        ],
    }
    (output_dir / "source_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return StatewideBuildSummary(
        source_files=tuple(path.name for path in source_paths),
        as_of_date=as_of.isoformat(),
        records=len(records),
        report_years=report_years,
        municipalities=int(records["municipality"].nunique()),
        suburbs=int(records["suburb"].nunique()),
        reported_cost=float(records["estimated_cost"].sum()),
        quality_warnings=int((quality["status"] == "warn").sum()),
        output_dir=str(output_dir),
    )


def summary_as_json(summary: StatewideBuildSummary) -> str:
    return json.dumps(asdict(summary), indent=2)
