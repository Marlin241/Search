from app.observability import _before_send


def test_before_send_drops_request_body():
    event = {
        "request": {
            "url": "https://x/y",
            "method": "POST",
            "data": {"cv": "secret"},
            "cookies": "a=b",
        }
    }
    out = _before_send(event, {})
    assert "data" not in out["request"] and "cookies" not in out["request"]


def test_before_send_strips_request_on_sensitive_path():
    event = {
        "request": {
            "url": "https://x/diagnostics",
            "method": "POST",
            "data": {"cv": "secret"},
            "headers": {"a": "b"},
        }
    }
    out = _before_send(event, {})
    assert set(out["request"]) <= {"url", "method"}


def test_before_send_scrubs_local_vars():
    event = {
        "exception": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [{"vars": {"cv_text": "SENSITIVE", "count": "3"}}]
                    }
                }
            ]
        }
    }
    out = _before_send(event, {})
    frame = out["exception"]["values"][0]["stacktrace"]["frames"][0]
    assert frame["vars"]["cv_text"] == "[scrubbed]"
    assert frame["vars"]["count"] == "3"


def test_before_send_is_safe_on_minimal_event():
    assert _before_send({}, {}) == {}
