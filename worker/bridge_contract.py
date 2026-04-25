# ================================================================================
# DATEI: bridge_contract.py
# PROJEKT: A2A-SIN-Worker-heyPiggy (OpenSIN AI Agent System)
# ZWECK: 
# WICHTIG FÜR ENTWICKLER: 
#   - Ändere nichts ohne zu verstehen was passiert
#   - Jeder Kommentar erklärt WARUM etwas getan wird, nicht nur WAS
#   - Bei Fragen erst Code lesen, dann ändern
# ================================================================================

from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from worker.exceptions import BridgeProtocolError, BridgeUnavailableError
from worker.logging import get_logger
from worker.retry import RetryPolicy, retry_async

_log = get_logger(__name__)

_ASYNC_RETRY_POLICY = RetryPolicy(
    max_attempts=3,
    base_delay=1.0,
    max_delay=4.0,
    jitter=0.0,
    retry_on=(
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        BridgeProtocolError,
    ),
)


@dataclass(slots=True, frozen=True)
class BridgeRequest:
    # ========================================================================
    # KLASSE: BridgeRequest
    # ZWECK: 
    # WICHTIG: 
    # METHODEN: 
    # ========================================================================
    
    method: str
    params: dict[str, object] = field(default_factory=dict)
    page_fingerprint: str = ""
    timeout_seconds: int = 30
    request_id: int = 1

    def to_jsonrpc_body(self) -> dict[str, object]:
        body: dict[str, object] = {
            "jsonrpc": "2.0",
            "method": self.method,
            "id": self.request_id,
            "meta": {"page_fingerprint": self.page_fingerprint},
        }
        if self.params:
            body["params"] = self.params
        return body


@dataclass(slots=True, frozen=True)
class BridgeResponse:
    # ========================================================================
    # KLASSE: BridgeResponse
    # ZWECK: 
    # WICHTIG: 
    # METHODEN: 
    # ========================================================================
    
    ok: bool
    result: object
    error: str = ""
    status_code: int = 200
    attempt_count: int = 1


def _perform_bridge_request(base_url: str, request: BridgeRequest) -> BridgeResponse:
    http_request = urllib.request.Request(
        base_url,
        data=json.dumps(request.to_jsonrpc_body()).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(http_request, timeout=request.timeout_seconds) as resp:
            try:
                payload = json.loads(resp.read().decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise BridgeProtocolError("bridge payload must be valid JSON") from exc
            if not isinstance(payload, dict):
                raise BridgeProtocolError("bridge payload must be object")
            if "error" in payload:
                raise BridgeProtocolError(f"bridge protocol error: {payload['error']}")
            return BridgeResponse(
                ok=True,
                result=payload.get("result", {}),
                status_code=resp.getcode(),
                attempt_count=1,
            )
    except urllib.error.HTTPError as exc:
        if 400 <= exc.code < 500:
            raise BridgeUnavailableError(
                "bridge returned caller error",
                status_code=exc.code,
                method=request.method,
            ) from exc
        raise


def call_bridge_with_retry(base_url: str, request: BridgeRequest) -> BridgeResponse:
    delays = (1, 2, 4)
    last_error = ""
    for attempt, delay in enumerate(delays, start=1):
        try:
            response = _perform_bridge_request(base_url, request)
            return BridgeResponse(
                ok=response.ok,
                result=response.result,
                error=response.error,
                status_code=response.status_code,
                attempt_count=attempt,
            )
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}: {exc.reason}"
        except (urllib.error.URLError, TimeoutError, BridgeProtocolError) as exc:
            last_error = str(exc)
        except BridgeUnavailableError:
            raise

        _log.warning(
            "bridge_retry",
            method=request.method,
            attempt=attempt,
            delay_seconds=delay,
            error=last_error,
        )
        if attempt < len(delays):
            time.sleep(delay)

    raise BridgeUnavailableError(
        "bridge failed after retries",
        method=request.method,
        error=last_error,
    )


async def call_bridge_with_retry_async(
    base_url: str,
    request: BridgeRequest,
    *,
    policy: RetryPolicy | None = None,
) -> BridgeResponse:
    """Async bridge request with cancellation-safe retry semantics."""

    chosen_policy = policy or _ASYNC_RETRY_POLICY
    attempt_counter = 0

    @retry_async(chosen_policy)
    async def _attempt() -> BridgeResponse:
        nonlocal attempt_counter
        attempt_counter += 1
        response = await asyncio.to_thread(_perform_bridge_request, base_url, request)
        return BridgeResponse(
            ok=response.ok,
            result=response.result,
            error=response.error,
            status_code=response.status_code,
            attempt_count=attempt_counter,
        )

    try:
        return await _attempt()
    except BridgeUnavailableError:
        raise
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, BridgeProtocolError) as exc:
        raise BridgeUnavailableError(
            "bridge failed after retries",
            method=request.method,
            error=str(exc),
        ) from exc


__all__ = [
    "BridgeRequest",
    "BridgeResponse",
    "call_bridge_with_retry",
    "call_bridge_with_retry_async",
]
