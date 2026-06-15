"""Transport-level behavior of the stdlib model client: retry/backoff on
transient upstream failures, fail-fast on permanent ones."""

import asyncio
import io
import urllib.error
import urllib.request

import pytest

from tiles_ai.model.clients import _MAX_ATTEMPTS, ModelClientError, _post_json


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://api.test/x", code, "err", {}, io.BytesIO(b'{"error":{"message":"x"}}')
    )


class _Resp:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b'{"ok": true}'


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    # Don't actually wait out the backoff in tests.
    monkeypatch.setattr("tiles_ai.model.clients._backoff_seconds", lambda attempt: 0)


def test_retries_transient_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(req, timeout=60):
        calls["n"] += 1
        if calls["n"] < 3:
            raise _http_error(529)  # overloaded — exactly the user's error
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = asyncio.run(_post_json("https://api.test/x", {"a": 1}))
    assert result == {"ok": True}
    assert calls["n"] == 3  # two failures, third succeeds


def test_does_not_retry_permanent_errors(monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(req, timeout=60):
        calls["n"] += 1
        raise _http_error(401)  # bad key — retrying is pointless

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ModelClientError, match="401"):
        asyncio.run(_post_json("https://api.test/x", {}))
    assert calls["n"] == 1


def test_gives_up_after_max_attempts(monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(req, timeout=60):
        calls["n"] += 1
        raise _http_error(529)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ModelClientError, match="529"):
        asyncio.run(_post_json("https://api.test/x", {}))
    assert calls["n"] == _MAX_ATTEMPTS
