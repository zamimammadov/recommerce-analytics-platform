import json
import logging

from recommerce.logging_config import JsonFormatter


def test_json_formatter_keeps_context():
    record = logging.LogRecord(
        name="pipeline",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="loaded batch",
        args=(),
        exc_info=None,
    )
    record.batch_id = "batch-2026-11-15"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "loaded batch"
    assert payload["batch_id"] == "batch-2026-11-15"
    assert payload["level"] == "INFO"
