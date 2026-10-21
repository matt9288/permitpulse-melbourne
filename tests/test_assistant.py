from __future__ import annotations

import json
from datetime import date
from unittest.mock import patch

import pandas as pd

from permitpulse.assistant import (
    MAX_AI_QUESTIONS_PER_SESSION,
    answer_dashboard_question,
    build_assistant_context,
    deterministic_answer,
    request_groq_answer,
)
from permitpulse.statewide_dashboard import StatewideFilters


def _records() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "record_id": ["private-row-a", "private-row-b", "private-row-c"],
            "report_year": [2024, 2025, 2025],
            "report_month": pd.to_datetime(["2024-01-01", "2025-01-01", "2025-02-01"]),
            "municipality": ["Melbourne, City of", "Melbourne, City of", "Hume, City of"],
            "region": ["Metropolitan", "Metropolitan", "Metropolitan"],
            "suburb": ["MELBOURNE", "MELBOURNE", "SUNBURY"],
            "cost_band": ["$50k–$250k", "$250k–$1m", "> $10m"],
            "estimated_cost": [100_000, 500_000, 20_000_000],
            "nature_of_work": ["Alteration", "New building", "New building"],
            "building_use": ["Commercial", "Domestic", "Domestic"],
            "new_dwellings": [pd.NA, 2, 10],
        }
    )


def _context() -> dict:
    metadata = {
        "source_dataset": "Building Permit Activity Data",
        "source_url": "https://example.test/source",
        "as_of_date": "2026-10-07",
        "summary": {"report_years": [2024, 2025]},
        "limitations": ["No public permit identifier is present."],
    }
    filters = StatewideFilters(start_date=date(2024, 1, 1), end_date=date(2025, 12, 31))
    return build_assistant_context(_records(), filters, metadata)


def test_assistant_context_contains_aggregates_without_record_identifiers() -> None:
    context = _context()
    serialised = json.dumps(context)

    assert context["headline_metrics"]["permit_records"] == 3
    assert context["headline_metrics"]["total_reported_cost"] == 20_600_000
    assert context["annual_summary"][1]["new_dwellings"] == 12
    assert "record_id" not in serialised
    assert "private-row-a" not in serialised


def test_built_in_guide_reports_current_scope_and_data_limitations() -> None:
    context = _context()

    summary = deterministic_answer("Summarise the current filters", context)
    rejected = answer_dashboard_question("Can you predict permit rejection risk?", context)

    assert "3 permit records" in summary
    assert "$20.6m" in summary
    assert "2024-01-01 to 2025-12-31" in summary
    assert "cannot answer" in rejected.text
    assert rejected.mode == "Built-in guardrail"
    assert not rejected.used_groq


class _FakeGroqResponse:
    def __enter__(self) -> _FakeGroqResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(
            {"choices": [{"message": {"content": "A grounded aggregate answer."}}]}
        ).encode()


def test_groq_request_sends_only_the_aggregate_context() -> None:
    context = _context()
    with patch("permitpulse.assistant.request.urlopen", return_value=_FakeGroqResponse()) as call:
        answer = request_groq_answer("test-key", "What changed between the years?", context)

    sent_request = call.call_args.args[0]
    payload = json.loads(sent_request.data.decode())
    sent_text = json.dumps(payload)
    assert answer == "A grounded aggregate answer."
    assert payload["model"] == "openai/gpt-oss-20b"
    assert "record_id" not in sent_text
    assert "private-row-a" not in sent_text
    assert "test-key" not in sent_text


def test_session_limit_uses_the_free_built_in_guide_without_calling_groq() -> None:
    with patch("permitpulse.assistant.request.urlopen") as call:
        result = answer_dashboard_question(
            "Summarise the current filters",
            _context(),
            api_key="test-key",
            ai_questions_used=MAX_AI_QUESTIONS_PER_SESSION,
        )

    call.assert_not_called()
    assert not result.used_groq
    assert "session AI limit reached" in result.mode
