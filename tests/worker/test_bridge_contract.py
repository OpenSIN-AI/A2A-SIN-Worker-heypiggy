from __future__ import annotations

import io
import json
from email.message import Message
import urllib.error

import pytest

from worker.bridge_contract import BridgeRequest, BridgeResponse, call_bridge_with_retry
from worker.exceptions import BridgeUnavailableError


class _FakeHttpResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self._status_code = status_code

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def getcode(self) -> int:
        return self._status_code

    def __enter__(self) -> _FakeHttpResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_bridge_request_includes_page_fingerprint() -> None:
    request = BridgeRequest(
        method="tools/call", params={"name": "tabs_list"}, page_fingerprint="hash123"
    )
    body = request.to_jsonrpc_body()

    assert body["meta"] == {"page_fingerprint": "hash123"}


def test_call_bridge_with_retry_succeeds_on_first_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: _FakeHttpResponse({"result": {"ok": True}}, status_code=200),
    )

    response = call_bridge_with_retry(
        "https://bridge.example/mcp", BridgeRequest(method="tools/call")
    )

    assert isinstance(response, BridgeResponse)
    assert response.ok is True
    assert response.attempt_count == 1


def test_call_bridge_with_retry_succeeds_on_third_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def _urlopen(request, timeout):
        calls["count"] += 1
        if calls["count"] < 3:
            raise urllib.error.URLError("temporary")
        return _FakeHttpResponse({"result": {"ok": True}}, status_code=200)

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    monkeypatch.setattr("time.sleep", lambda _: None)

    response = call_bridge_with_retry(
        "https://bridge.example/mcp", BridgeRequest(method="tools/call")
    )

    assert response.ok is True
    assert response.attempt_count == 3


def test_call_bridge_with_retry_raises_after_three_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(urllib.error.URLError("down")),
    )
    monkeypatch.setattr("time.sleep", lambda _: None)

    with pytest.raises(BridgeUnavailableError):
        call_bridge_with_retry("https://bridge.example/mcp", BridgeRequest(method="tools/call"))


def test_call_bridge_with_retry_does_not_retry_http_4xx(monkeypatch: pytest.MonkeyPatch) -> None:
    def _urlopen(request, timeout):
        raise urllib.error.HTTPError(
            url="https://bridge.example/mcp",
            code=404,
            msg="not found",
            hdrs=Message(),
            fp=io.BytesIO(b"{}"),
        )

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    with pytest.raises(BridgeUnavailableError):
        call_bridge_with_retry("https://bridge.example/mcp", BridgeRequest(method="tools/call"))
