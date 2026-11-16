from datetime import UTC, datetime

import pytest

from recommerce.quality import (
    CheckDefinition,
    CheckStatus,
    Severity,
    classify_result,
    evaluate_check,
    results_as_dicts,
)


def test_zero_failures_passes() -> None:
    assert classify_result(0, 0, Severity.ERROR) == CheckStatus.PASS


def test_failure_is_fail_for_error_severity() -> None:
    assert classify_result(1, 0, Severity.ERROR) == CheckStatus.FAIL


def test_warning_severity_still_records_a_failed_check() -> None:
    assert classify_result(3, 2, Severity.WARNING) == CheckStatus.FAIL


def test_threshold_allows_expected_failures() -> None:
    assert classify_result(2, 2, Severity.ERROR) == CheckStatus.PASS


def test_evaluate_check_rejects_negative_count() -> None:
    definition = CheckDefinition("example", "Example check", "SELECT 1")
    with pytest.raises(ValueError, match="cannot be negative"):
        evaluate_check(definition, -1)


def test_results_are_json_friendly() -> None:
    definition = CheckDefinition("example", "Example check", "SELECT 1")
    checked_at = datetime(2026, 11, 15, 12, 30, tzinfo=UTC)
    result = evaluate_check(definition, 0, checked_at=checked_at)

    serialized = results_as_dicts([result])

    assert serialized == [
        {
            "name": "example",
            "description": "Example check",
            "severity": "error",
            "status": "pass",
            "failed_rows": 0,
            "max_failed_rows": 0,
            "checked_at": "2026-11-15T12:30:00+00:00",
            "error_message": None,
        }
    ]
