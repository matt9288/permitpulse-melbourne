from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pandas as pd

DEFAULT_SOURCE_URL = (
    "https://data.melbourne.vic.gov.au/api/v2/catalog/datasets/"
    "building-permits/exports/csv?delimiter=%2C"
)

DEFAULT_ADDRESS_SOURCE_URL = (
    "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/"
    "street-addresses/exports/csv?lang=en&timezone=Australia%2FMelbourne&"
    "use_labels=false&delimiter=%2C"
)

REQUIRED_COLUMNS = [
    "council_ref",
    "permit_number",
    "issue_date",
    "address",
    "desc_of_works",
    "estimated_cost_of_works",
    "rbs_number",
    "commence_by_date",
    "completed_by_date",
    "permit_certificate_type",
]

ALLOWED_CERTIFICATE_TYPES = {
    "Building Permit",
    "Certificate of Final Inspection",
    "Occupancy Permit",
    "Certificate of Occupancy",
}

DATE_COLUMNS = ["issue_date", "commence_by_date", "completed_by_date"]

ADDRESS_REQUIRED_COLUMNS = [
    "street_no",
    "str_name",
    "suburb",
    "latitude",
    "longitude",
]

COST_BAND_ORDER = [
    "≤ $0",
    "$1–$50k",
    "$50k–$250k",
    "$250k–$1m",
    "$1m–$10m",
    "> $10m",
    "Missing",
]

WORK_CATEGORY_ORDER = [
    "Fit-out / tenancy",
    "Alteration / refurbishment",
    "Demolition",
    "Building services / safety",
    "New construction",
    "Outdoor / ancillary",
    "Signage",
    "Other / unclear",
]


class SchemaError(ValueError):
    """Raised when the source file no longer satisfies the expected contract."""


@dataclass(frozen=True)
class BuildSummary:
    source_path: str
    source_sha256: str
    as_of_date: str
    raw_rows: int
    permit_families: int
    analytic_permits: int
    certificate_events: int
    permit_addresses: int
    geocoded_permits: int
    geocoded_rate: float
    quarantine_issues: int
    output_dir: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_source(destination: Path, url: str = DEFAULT_SOURCE_URL) -> Path:
    """Download the public source atomically so a failed request keeps the prior snapshot."""
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix="permitpulse-", suffix=".csv", dir=destination.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310
            shutil.copyfileobj(response, temporary)
    temporary_path.replace(destination)
    return destination


def download_address_source(
    destination: Path,
    url: str = DEFAULT_ADDRESS_SOURCE_URL,
) -> Path:
    """Download the open City of Melbourne address-point file atomically."""
    return download_source(destination, url)


def _read_source(path: Path) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    raw = pd.read_csv(path, dtype="string", keep_default_na=True)
    missing = sorted(set(REQUIRED_COLUMNS) - set(raw.columns))
    if missing:
        raise SchemaError(f"Source is missing required columns: {', '.join(missing)}")

    raw = raw[REQUIRED_COLUMNS].copy()
    raw.insert(0, "raw_row_id", pd.RangeIndex(start=1, stop=len(raw) + 1))
    original_dates = {column: raw[column].copy() for column in DATE_COLUMNS}

    for column in REQUIRED_COLUMNS:
        if column != "estimated_cost_of_works":
            raw[column] = raw[column].str.strip().replace("", pd.NA)

    for column in DATE_COLUMNS:
        raw[column] = pd.to_datetime(raw[column], errors="coerce")
    raw["estimated_cost_of_works"] = pd.to_numeric(
        raw["estimated_cost_of_works"], errors="coerce"
    ).astype("Float64")
    return raw, original_dates


def _quarantine_rows(
    raw: pd.DataFrame,
    original_dates: dict[str, pd.Series],
    as_of: date,
) -> pd.DataFrame:
    issues: list[pd.DataFrame] = []
    is_building_permit = raw["permit_certificate_type"].eq("Building Permit")

    def add(mask: pd.Series, rule_id: str, severity: str, details: str) -> None:
        selected = raw.loc[mask.fillna(False), ["raw_row_id", "council_ref"]].copy()
        if selected.empty:
            return
        selected["record_scope"] = "raw_row"
        selected["rule_id"] = rule_id
        selected["severity"] = severity
        selected["details"] = details
        issues.append(selected)

    add(
        raw["council_ref"].isna(),
        "missing_council_ref",
        "critical",
        "Council reference is missing.",
    )
    add(raw["permit_number"].isna(), "missing_permit_number", "high", "Permit number is missing.")
    add(
        raw["permit_certificate_type"].isna(),
        "missing_certificate_type",
        "critical",
        "Permit or certificate type is missing.",
    )
    add(
        ~raw["permit_certificate_type"].isin(ALLOWED_CERTIFICATE_TYPES)
        & raw["permit_certificate_type"].notna(),
        "unexpected_certificate_type",
        "high",
        "Certificate type is outside the documented vocabulary.",
    )
    add(
        raw["issue_date"].isna(),
        "missing_or_invalid_issue_date",
        "high",
        "Issue date is missing or could not be parsed.",
    )
    add(
        raw["issue_date"] > pd.Timestamp(as_of),
        "future_issue_date",
        "high",
        f"Issue date is later than analysis date {as_of.isoformat()}.",
    )
    add(
        raw["estimated_cost_of_works"] < 0,
        "negative_estimated_cost",
        "high",
        "Estimated cost is negative.",
    )
    add(
        is_building_permit
        & raw["commence_by_date"].notna()
        & raw["issue_date"].notna()
        & (raw["commence_by_date"] < raw["issue_date"]),
        "commence_before_issue",
        "medium",
        "Commence-by date precedes issue date.",
    )
    add(
        is_building_permit
        & raw["completed_by_date"].notna()
        & raw["issue_date"].notna()
        & (raw["completed_by_date"] < raw["issue_date"]),
        "completion_before_issue",
        "medium",
        "Completed-by date precedes issue date.",
    )
    add(
        is_building_permit
        & raw["completed_by_date"].notna()
        & raw["commence_by_date"].notna()
        & (raw["completed_by_date"] < raw["commence_by_date"]),
        "completion_before_commence",
        "medium",
        "Completed-by date precedes commence-by date.",
    )

    for column, original in original_dates.items():
        add(
            original.notna() & raw[column].isna(),
            f"invalid_{column}",
            "high",
            f"{column} contains an unparseable source value.",
        )

    columns = [
        "raw_row_id",
        "council_ref",
        "record_scope",
        "rule_id",
        "severity",
        "details",
    ]
    if not issues:
        return pd.DataFrame(columns=columns)
    return pd.concat(issues, ignore_index=True)[columns]


def _certificate_events(raw: pd.DataFrame) -> pd.DataFrame:
    keys = ["council_ref", "permit_number", "issue_date", "permit_certificate_type"]
    events = raw.sort_values(keys + ["raw_row_id"], na_position="last").drop_duplicates(keys)
    events = events[keys].rename(
        columns={"issue_date": "event_date", "permit_certificate_type": "event_type"}
    )
    events = events.sort_values(
        ["council_ref", "event_date", "event_type", "permit_number"], na_position="last"
    ).reset_index(drop=True)
    events.insert(0, "event_id", pd.RangeIndex(start=1, stop=len(events) + 1))
    return events


def _permit_addresses(raw: pd.DataFrame) -> pd.DataFrame:
    addresses = raw.loc[
        raw["council_ref"].notna() & raw["address"].notna(),
        [
            "council_ref",
            "address",
        ],
    ].drop_duplicates()
    parsed = addresses["address"].str.extract(
        r",\s*([A-Z][A-Z .'-]+?)\s+VIC\s+(\d{4})\s*$", expand=True
    )
    addresses["suburb"] = parsed[0]
    addresses["postcode"] = parsed[1]
    addresses = addresses.sort_values(["council_ref", "address"]).reset_index(drop=True)
    addresses.insert(0, "address_id", pd.RangeIndex(start=1, stop=len(addresses) + 1))
    return addresses


def _permit_families(
    raw: pd.DataFrame,
    events: pd.DataFrame,
    addresses: pd.DataFrame,
    quarantine: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    building = raw.loc[raw["permit_certificate_type"] == "Building Permit"].copy()
    building = building.sort_values(
        ["council_ref", "issue_date", "permit_number", "address", "raw_row_id"],
        na_position="last",
    )
    representatives = building.drop_duplicates("council_ref").copy()

    family_columns = [
        "council_ref",
        "permit_number",
        "issue_date",
        "desc_of_works",
        "estimated_cost_of_works",
        "rbs_number",
        "commence_by_date",
        "completed_by_date",
    ]
    families = representatives[family_columns].rename(
        columns={
            "issue_date": "permit_issue_date",
            "estimated_cost_of_works": "estimated_cost",
        }
    )

    stats = building.groupby("council_ref", dropna=False).agg(
        building_permit_rows=("raw_row_id", "size"),
        distinct_permit_numbers=("permit_number", "nunique"),
        distinct_issue_dates=("issue_date", "nunique"),
        distinct_cost_values=("estimated_cost_of_works", "nunique"),
    )
    raw_stats = raw.groupby("council_ref", dropna=False).agg(
        raw_rows=("raw_row_id", "size"),
        certificate_type_count=("permit_certificate_type", "nunique"),
    )
    event_counts = events.groupby("council_ref").size().rename("event_count")
    address_counts = addresses.groupby("council_ref").size().rename("address_count")
    primary_address = (
        addresses.sort_values(["council_ref", "address"])
        .drop_duplicates("council_ref")
        .set_index("council_ref")[["address", "suburb", "postcode"]]
        .rename(columns={"address": "primary_address"})
    )

    families = (
        families.set_index("council_ref")
        .join(stats)
        .join(raw_stats)
        .join(event_counts)
        .join(address_counts)
        .join(primary_address)
        .reset_index()
    )
    for column in ["event_count", "address_count"]:
        families[column] = families[column].fillna(0).astype("int64")

    high_row_ids = set(
        quarantine.loc[quarantine["severity"].isin(["critical", "high"]), "raw_row_id"].dropna()
    )
    high_building_refs = set(
        building.loc[building["raw_row_id"].isin(high_row_ids), "council_ref"].dropna()
    )
    conflict_mask = families["distinct_cost_values"] > 1
    families["quality_status"] = "valid"
    families.loc[
        families["council_ref"].isin(high_building_refs) | conflict_mask,
        "quality_status",
    ] = "review"
    families["issue_year"] = families["permit_issue_date"].dt.year.astype("Int64")
    families["issue_month"] = families["permit_issue_date"].dt.to_period("M").dt.to_timestamp()
    families["cost_band"] = (
        pd.cut(
            families["estimated_cost"],
            bins=[float("-inf"), 0, 50_000, 250_000, 1_000_000, 10_000_000, float("inf")],
            labels=COST_BAND_ORDER[:-1],
            include_lowest=True,
        )
        .astype("string")
        .fillna("Missing")
    )
    families["work_category_rule"] = _classify_work_descriptions(families["desc_of_works"])
    families = families.sort_values("council_ref").reset_index(drop=True)
    analytics = families.loc[families["quality_status"] == "valid"].copy()
    return families, analytics


def _normalise_address_part(values: pd.Series) -> pd.Series:
    return (
        values.fillna("")
        .str.upper()
        .str.replace(r"[^A-Z0-9]+", " ", regex=True)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )


def geocode_permit_families(
    families: pd.DataFrame,
    address_source_path: Path | None,
) -> pd.DataFrame:
    """Add representative permit coordinates from the official open address register.

    Exact street-number matches use the mean point when the register contains multiple
    unit-level points. Number ranges use the centroid of official points within the stated
    range on the same street and suburb. Unmatched permits remain null rather than being
    assigned a fabricated location.
    """
    located = families.copy()
    located["latitude"] = pd.Series(pd.NA, index=located.index, dtype="Float64")
    located["longitude"] = pd.Series(pd.NA, index=located.index, dtype="Float64")
    located["geocode_method"] = pd.Series("unmatched", index=located.index, dtype="string")
    if address_source_path is None:
        return located

    addresses = pd.read_csv(address_source_path, dtype="string", keep_default_na=True)
    missing = sorted(set(ADDRESS_REQUIRED_COLUMNS) - set(addresses.columns))
    if missing:
        raise SchemaError("Address source is missing required columns: " + ", ".join(missing))

    source_number = addresses["street_no"].str.extract(r"^(\d+)", expand=False)
    address_points = pd.DataFrame(
        {
            "street": _normalise_address_part(addresses["str_name"]),
            "suburb": _normalise_address_part(addresses["suburb"]),
            "street_number": pd.to_numeric(source_number, errors="coerce"),
            "number_token": _normalise_address_part(addresses["street_no"]),
            "latitude": pd.to_numeric(addresses["latitude"], errors="coerce"),
            "longitude": pd.to_numeric(addresses["longitude"], errors="coerce"),
        }
    ).dropna(subset=["street_number", "latitude", "longitude"])

    without_locality = located["primary_address"].str.replace(
        r",\s*[A-Z][A-Z .'-]+?\s+VIC\s+\d{4}\s*$",
        "",
        regex=True,
    )
    street_component = without_locality.str.rsplit(",", n=1).str[-1].str.strip()
    permit_parts = street_component.str.extract(
        r"^([0-9]+(?:\s*[A-Z])?(?:-[0-9]+(?:\s*[A-Z])?)?)\s+(.+)$"
    )
    permit_keys = pd.DataFrame(
        {
            "number_token": _normalise_address_part(permit_parts[0]),
            "raw_number_token": permit_parts[0].fillna(""),
            "street": _normalise_address_part(permit_parts[1]),
            "suburb": _normalise_address_part(located["suburb"]),
        },
        index=located.index,
    )

    exact_points = address_points.groupby(["street", "suburb", "number_token"], observed=True)[
        ["latitude", "longitude"]
    ].mean()
    street_groups = {
        key: group for key, group in address_points.groupby(["street", "suburb"], observed=True)
    }
    unique_keys = permit_keys.drop_duplicates().reset_index(drop=True)

    def locate(key: pd.Series) -> pd.Series:
        exact_key = (key["street"], key["suburb"], key["number_token"])
        if exact_key in exact_points.index:
            point = exact_points.loc[exact_key]
            return pd.Series([point["latitude"], point["longitude"], "exact address point"])

        number_match = re.match(
            r"^(\d+)(?:\s*[A-Z])?(?:-(\d+))?",
            str(key["raw_number_token"]),
        )
        street_key = (key["street"], key["suburb"])
        if not number_match or street_key not in street_groups:
            return pd.Series([pd.NA, pd.NA, "unmatched"])

        lower = int(number_match.group(1))
        upper = int(number_match.group(2) or lower)
        lower, upper = min(lower, upper), max(lower, upper)
        candidates = street_groups[street_key]
        candidates = candidates.loc[candidates["street_number"].between(lower, upper)]
        if candidates.empty:
            return pd.Series([pd.NA, pd.NA, "unmatched"])
        method = "range centroid" if lower != upper else "street-number centroid"
        return pd.Series([candidates["latitude"].mean(), candidates["longitude"].mean(), method])

    coordinates = unique_keys.apply(locate, axis=1)
    coordinates.columns = ["latitude", "longitude", "geocode_method"]
    lookup = pd.concat([unique_keys, coordinates], axis=1)
    joined = permit_keys.merge(
        lookup,
        on=["number_token", "raw_number_token", "street", "suburb"],
        how="left",
        validate="many_to_one",
        sort=False,
    )
    located["latitude"] = pd.to_numeric(joined["latitude"], errors="coerce").astype("Float64")
    located["longitude"] = pd.to_numeric(joined["longitude"], errors="coerce").astype("Float64")
    located["geocode_method"] = joined["geocode_method"].fillna("unmatched").astype("string")
    return located


def _classify_work_descriptions(descriptions: pd.Series) -> pd.Series:
    """Apply transparent keyword rules until a labelled ML model is available."""
    text = descriptions.fillna("").str.lower()
    categories = pd.Series("Other / unclear", index=descriptions.index, dtype="string")
    rules = [
        ("Fit-out / tenancy", r"\bfit[ -]?out\b|\btenan(?:cy|t)\b"),
        ("Alteration / refurbishment", r"\balter|\brefurb|\brenovat|\bremodel"),
        ("Demolition", r"\bdemol"),
        (
            "Building services / safety",
            r"\bfire\b|sprinkler|electrical|mechanical service|\blift\b|essential safety",
        ),
        ("New construction", r"\bnew building\b|\bconstruction of\b|\bconstruct a\b"),
        (
            "Outdoor / ancillary",
            r"swimming pool|\bpool\b|verandah|pergola|\bfence\b|\bfencing\b|carport",
        ),
        ("Signage", r"\bsignage\b|advertising sign|business identification sign"),
    ]
    for label, pattern in rules:
        unclassified = categories.eq("Other / unclear")
        categories.loc[unclassified & text.str.contains(pattern, regex=True)] = label
    return categories


def _quality_results(
    raw: pd.DataFrame,
    families: pd.DataFrame,
    analytics: pd.DataFrame,
    events: pd.DataFrame,
    quarantine: pd.DataFrame,
    as_of: date,
) -> pd.DataFrame:
    results: list[dict[str, object]] = []

    def record(
        check_id: str,
        dimension: str,
        severity: str,
        status: str,
        affected_rows: int,
        denominator: int,
        details: str,
    ) -> None:
        results.append(
            {
                "check_id": check_id,
                "dimension": dimension,
                "severity": severity,
                "status": status,
                "affected_rows": int(affected_rows),
                "denominator": int(denominator),
                "affected_rate": float(affected_rows / denominator) if denominator else 0.0,
                "metric_value": None,
                "metric_unit": None,
                "details": details,
            }
        )

    def record_metric(
        check_id: str,
        dimension: str,
        severity: str,
        status: str,
        metric_value: float,
        metric_unit: str,
        details: str,
    ) -> None:
        results.append(
            {
                "check_id": check_id,
                "dimension": dimension,
                "severity": severity,
                "status": status,
                "affected_rows": None,
                "denominator": None,
                "affected_rate": None,
                "metric_value": float(metric_value),
                "metric_unit": metric_unit,
                "details": details,
            }
        )

    raw_count = len(raw)
    exact_duplicates = int(raw[REQUIRED_COLUMNS].duplicated().sum())
    repeated_ref_rows = int(raw["council_ref"].duplicated(keep=False).sum())
    record(
        "exact_duplicate_rows",
        "uniqueness",
        "medium",
        "pass" if exact_duplicates == 0 else "warn",
        exact_duplicates,
        raw_count,
        "Exact duplicate source rows should be investigated but are not the main "
        "mixed-grain issue.",
    )
    record(
        "rows_in_repeated_permit_references",
        "grain",
        "critical",
        "warn" if repeated_ref_rows else "pass",
        repeated_ref_rows,
        raw_count,
        "Repeated council references reflect certificate and multi-address rows; "
        "raw rows are not projects.",
    )
    duplicate_families = int(families["council_ref"].duplicated().sum())
    record(
        "permit_family_key_unique",
        "uniqueness",
        "critical",
        "pass" if duplicate_families == 0 else "fail",
        duplicate_families,
        len(families),
        "The permit_families table must contain one row per council_ref.",
    )

    for rule_id, group in quarantine.groupby("rule_id"):
        severity = str(group["severity"].iloc[0])
        affected = int(group["raw_row_id"].nunique())
        record(
            str(rule_id),
            "validity",
            severity,
            "warn" if affected else "pass",
            affected,
            raw_count,
            str(group["details"].iloc[0]),
        )

    family_refs = set(families["council_ref"].dropna())
    orphan_refs = set(events["council_ref"].dropna()) - family_refs
    record(
        "certificate_references_without_building_permit",
        "integrity",
        "high",
        "warn" if orphan_refs else "pass",
        len(orphan_refs),
        events["council_ref"].nunique(),
        "Certificate-event references without an observed Building Permit row cannot "
        "join to a permit family.",
    )

    raw_positive = raw.loc[raw["estimated_cost_of_works"] > 0, "estimated_cost_of_works"].sum()
    family_positive = families.loc[families["estimated_cost"] > 0, "estimated_cost"].sum()
    inflation = float(raw_positive / family_positive) if family_positive else 0.0
    record_metric(
        "raw_cost_total_inflation",
        "grain",
        "critical",
        "warn" if inflation > 1.05 else "pass",
        inflation,
        "ratio",
        f"Raw positive estimated-cost total is {inflation:.2f}x the permit-family total.",
    )

    nonfuture = families.loc[families["permit_issue_date"] <= pd.Timestamp(as_of)].copy()
    latest = nonfuture["permit_issue_date"].max()
    freshness_lag = (pd.Timestamp(as_of) - latest).days if pd.notna(latest) else 99999
    record_metric(
        "latest_permit_freshness",
        "timeliness",
        "medium",
        "pass" if freshness_lag <= 31 else "warn",
        freshness_lag,
        "days",
        "Latest non-future building-permit issue date is "
        f"{latest.date() if pd.notna(latest) else 'unavailable'}.",
    )

    monthly = (
        nonfuture.dropna(subset=["permit_issue_date"])
        .assign(month=lambda frame: frame["permit_issue_date"].dt.to_period("M").dt.to_timestamp())
        .groupby("month")
        .size()
    )
    anchor = pd.Timestamp(as_of).to_period("M").to_timestamp()
    recent = monthly.loc[
        (monthly.index >= anchor - pd.DateOffset(months=3)) & (monthly.index < anchor)
    ]
    baseline = monthly.loc[
        (monthly.index >= anchor - pd.DateOffset(months=15))
        & (monthly.index < anchor - pd.DateOffset(months=3))
    ]
    recent_ratio = float(recent.mean() / baseline.mean()) if len(recent) and len(baseline) else 0.0
    record_metric(
        "recent_three_month_volume",
        "timeliness",
        "high",
        "warn" if recent_ratio < 0.5 else "pass",
        recent_ratio,
        "ratio",
        f"Recent three-month average is {recent_ratio:.1%} of the preceding 12-month average.",
    )

    record(
        "analytic_permit_retention",
        "completeness",
        "medium",
        "pass" if len(analytics) / len(families) >= 0.95 else "warn",
        len(families) - len(analytics),
        len(families),
        "Permit families failing high-severity or conflicting-value checks are retained "
        "for review but excluded from the analytics view.",
    )
    return pd.DataFrame(results)


def _write_outputs(
    output_dir: Path,
    tables: dict[str, pd.DataFrame],
    metadata: dict[str, object],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    database_path = output_dir / "permitpulse.duckdb"
    connection = duckdb.connect(str(database_path))
    try:
        for name, frame in tables.items():
            connection.register("incoming_frame", frame)
            connection.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM incoming_frame")
            connection.unregister("incoming_frame")
            parquet_path = str((output_dir / f"{name}.parquet").resolve()).replace("'", "''")
            connection.execute(
                f"COPY {name} TO '{parquet_path}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
    finally:
        connection.close()
    (output_dir / "source_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )


def build_pipeline(
    source_path: Path,
    output_dir: Path,
    as_of: date | None = None,
    address_source_path: Path | None = None,
) -> BuildSummary:
    source_path = source_path.resolve()
    output_dir = output_dir.resolve()
    address_source_path = address_source_path.resolve() if address_source_path else None
    as_of = as_of or date.today()
    source_sha256 = sha256_file(source_path)
    raw, original_dates = _read_source(source_path)
    quarantine = _quarantine_rows(raw, original_dates, as_of)
    events = _certificate_events(raw)
    addresses = _permit_addresses(raw)
    families, analytics = _permit_families(raw, events, addresses, quarantine)
    families = geocode_permit_families(families, address_source_path)
    analytics = families.loc[families["quality_status"] == "valid"].copy()
    quality = _quality_results(raw, families, analytics, events, quarantine, as_of)

    geocoded_permits = int(analytics["latitude"].notna().sum())
    geocoded_rate = float(geocoded_permits / len(analytics)) if len(analytics) else 0.0

    summary = BuildSummary(
        source_path=str(source_path),
        source_sha256=source_sha256,
        as_of_date=as_of.isoformat(),
        raw_rows=len(raw),
        permit_families=len(families),
        analytic_permits=len(analytics),
        certificate_events=len(events),
        permit_addresses=len(addresses),
        geocoded_permits=geocoded_permits,
        geocoded_rate=geocoded_rate,
        quarantine_issues=len(quarantine),
        output_dir=str(output_dir),
    )
    metadata = {
        "dataset": "City of Melbourne Building Permits",
        "source_url": DEFAULT_SOURCE_URL,
        "source_file": source_path.name,
        "source_bytes": source_path.stat().st_size,
        "source_sha256": source_sha256,
        "built_at_utc": datetime.now(UTC).isoformat(),
        "as_of_date": as_of.isoformat(),
        "summary": {
            key: value
            for key, value in asdict(summary).items()
            if key not in {"source_path", "output_dir"}
        },
    }
    if address_source_path:
        metadata["geospatial_source"] = {
            "dataset": "City of Melbourne Street addresses",
            "source_url": DEFAULT_ADDRESS_SOURCE_URL,
            "source_file": address_source_path.name,
            "source_bytes": address_source_path.stat().st_size,
            "source_sha256": sha256_file(address_source_path),
            "methods": {
                "exact address point": "Mean of official points sharing the exact address key.",
                "range centroid": (
                    "Mean of official address points within the permit number range on the "
                    "same street and suburb."
                ),
                "street-number centroid": (
                    "Mean of official points sharing the street number when suffixes differ."
                ),
                "unmatched": "No coordinate assigned.",
            },
        }
    _write_outputs(
        output_dir,
        {
            "permit_families": families,
            "analytic_permits": analytics,
            "certificate_events": events,
            "permit_addresses": addresses,
            "quarantine_records": quarantine,
            "data_quality_results": quality,
        },
        metadata,
    )
    return summary
