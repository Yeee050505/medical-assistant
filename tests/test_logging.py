import json
import logging

from app.core.logging import JsonFormatter, trace_id_var


def test_json_formatter_emits_structured_record():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    line = formatter.format(record)
    payload = json.loads(line)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["msg"] == "hello world"
    assert "ts" in payload and "traceId" in payload


def test_json_formatter_carries_context_trace_id():
    token = trace_id_var.set("trace-abc-123")
    try:
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="app.test",
            level=logging.WARNING,
            pathname=__file__,
            lineno=1,
            msg="with trace",
            args=None,
            exc_info=None,
        )
        payload = json.loads(formatter.format(record))
        assert payload["traceId"] == "trace-abc-123"
    finally:
        trace_id_var.reset(token)


def test_json_formatter_includes_exception():
    formatter = JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="app.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=None,
            exc_info=sys.exc_info(),
        )
        line = formatter.format(record)
    payload = json.loads(line)
    assert "exc" in payload and "ValueError: boom" in payload["exc"]
