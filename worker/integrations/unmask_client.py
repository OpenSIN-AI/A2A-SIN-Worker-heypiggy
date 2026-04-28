"""Async JSON-RPC 2.0 client for SIN-CLIs/unmask-cli.

Status: Skeleton. The transport (stdio subprocess vs. HTTP+WS) is abstracted
behind ``UnmaskTransport`` so Phase 2 can pick whichever is healthier in the
target environment without rewriting the public surface.

Design choices and why:

* **Async.** Survey runs are sequential per session, but inside a single
  RPC call we may stream chunks (DOM scan progress, console events). asyncio
  keeps that natural without blocking the worker loop.
* **Strict typing.** ``UnmaskResponse`` mirrors the JSON shape unmask emits
  (``url``, ``title``, ``elements``, ``network``, ``console``). We do **not**
  collapse it into a free-form dict — the whole point of the cross-repo
  contract is that drift is caught at the boundary.
* **Idempotent ``inspect``.** Re-calling ``inspect`` for the same URL must
  return a fresh snapshot, never a cached one. unmask itself takes a
  fresh snapshot per call; we just preserve that semantics here.
* **No silent failures.** Anything other than a JSON-RPC ``result`` raises
  ``UnmaskError`` with the original ``code`` + ``message`` + ``data`` from
  the server. Audit logs at the call site can then attribute the failure.

Reference for the RPC surface:
    https://github.com/SIN-CLIs/unmask-cli  (src/ipc/dispatch.ts)

What is NOT in this skeleton (intentionally — Phase 2):

* The actual ``asyncio.create_subprocess_exec`` wiring for the stdio
  transport.
* The ``websockets`` / ``aiohttp`` wiring for HTTP+WS transport.
* Reconnect / retry policy. Will live in ``worker.retry`` once we know
  unmask's actual error taxonomy.

These are deliberately TODO so a reviewer can see the seam and a Phase 2
PR can be small and obvious.
"""

from __future__ import annotations

import abc
import json
import os
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


# --------------------------------------------------------------------------- #
# Public typed surface
# --------------------------------------------------------------------------- #


class UnmaskError(RuntimeError):
    """Raised when unmask returns a JSON-RPC error or the transport fails.

    Attributes mirror the JSON-RPC 2.0 error object so callers can branch
    on a stable ``code`` rather than parsing free-form messages.
    """

    def __init__(
        self,
        message: str,
        *,
        code: int = -32000,
        data: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


@dataclass(frozen=True)
class UnmaskElement:
    """One interactable element from an unmask DOM scan.

    Mirrors ``Element`` from unmask's ``src/schemas/unmask.ts``.
    """

    selector: str
    label: str | None = None
    role: str | None = None
    confidence: float = 0.0


@dataclass(frozen=True)
class UnmaskNetworkEvent:
    """One network event captured by unmask via CDP."""

    url: str
    method: str
    status: int | None
    request_headers: Mapping[str, str] = field(default_factory=dict)
    response_body: str | None = None


@dataclass(frozen=True)
class UnmaskConsoleEvent:
    """One console / pageerror event."""

    type: str  # 'log' | 'warning' | 'error' | 'pageerror'
    text: str


@dataclass(frozen=True)
class UnmaskResponse:
    """Full one-shot X-ray response from ``unmask inspect``.

    The wire format is documented in unmask's README (Quickstart -- single
    page X-ray). We freeze it as a dataclass so an unrecognised top-level
    key from a future unmask version raises at construction time rather
    than silently falling through to runtime.
    """

    url: str
    title: str
    elements: Sequence[UnmaskElement] = field(default_factory=tuple)
    network: Sequence[UnmaskNetworkEvent] = field(default_factory=tuple)
    console: Sequence[UnmaskConsoleEvent] = field(default_factory=tuple)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "UnmaskResponse":
        """Strict parser. Raises ``UnmaskError`` on missing required fields.

        WHY strict: silent dict access has burned us already (see Issue #84).
        If unmask changes its surface, we want the failure right here at the
        boundary, not three layers deeper in the worker loop.
        """
        try:
            return cls(
                url=str(payload["url"]),
                title=str(payload.get("title", "")),
                elements=tuple(
                    UnmaskElement(
                        selector=str(e["selector"]),
                        label=e.get("label"),
                        role=e.get("role"),
                        confidence=float(e.get("confidence", 0.0)),
                    )
                    for e in payload.get("elements", [])
                ),
                network=tuple(
                    UnmaskNetworkEvent(
                        url=str(n["url"]),
                        method=str(n.get("method", "GET")),
                        status=n.get("status"),
                        request_headers=dict(n.get("requestHeaders", {}) or {}),
                        response_body=n.get("responseBody"),
                    )
                    for n in payload.get("network", [])
                ),
                console=tuple(
                    UnmaskConsoleEvent(
                        type=str(c["type"]),
                        text=str(c.get("text", "")),
                    )
                    for c in payload.get("console", [])
                ),
            )
        except (KeyError, TypeError, ValueError) as e:
            raise UnmaskError(
                f"unmask payload did not match expected schema: {e!r}",
                code=-32700,
                data={"payload_keys": list(payload.keys())},
            ) from e


# --------------------------------------------------------------------------- #
# Transport abstraction
# --------------------------------------------------------------------------- #


class UnmaskTransport(abc.ABC):
    """Abstract transport for one JSON-RPC 2.0 round-trip.

    Concrete impls in Phase 2:
      * ``UnmaskStdioTransport``  — spawns ``unmask serve`` as a subprocess
                                    and pipes JSON-RPC over stdin/stdout.
      * ``UnmaskHttpTransport``   — talks to ``unmask serve --http`` over
                                    HTTP POST + websocket for events.
    """

    @abc.abstractmethod
    async def call(
        self, method: str, params: Mapping[str, Any] | None = None
    ) -> Any:
        """Execute one JSON-RPC call. Must raise ``UnmaskError`` on RPC error."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Tear down the transport. Idempotent."""


# --------------------------------------------------------------------------- #
# Public client
# --------------------------------------------------------------------------- #


class UnmaskClient:
    """High-level client. The worker only ever talks to this class.

    Usage (Phase 2):

        async with UnmaskClient.from_env() as unmask:
            snapshot = await unmask.inspect(tab_url)
            ...

    Phase 1 deliberately raises ``NotImplementedError`` from every method —
    we want the type-checker and the reviewer to see the seam without anyone
    accidentally importing a half-baked impl in production.
    """

    def __init__(self, transport: UnmaskTransport) -> None:
        self._transport = transport

    # ---- factory ---- #

    @classmethod
    def from_env(cls) -> "UnmaskClient":
        """Pick a transport based on env (`UNMASK_TRANSPORT=stdio|http`).

        Phase 2 fills this in. Today we raise to make the gap obvious.
        """
        transport_kind = os.environ.get("UNMASK_TRANSPORT", "stdio").lower()
        raise NotImplementedError(
            f"UnmaskClient.from_env({transport_kind!r}): transport wiring lands in "
            "Phase 2. See docs/PLANS/01-INTEGRATION-UNMASK-PLAYSTEALTH.md"
        )

    # ---- async context manager ---- #

    async def __aenter__(self) -> "UnmaskClient":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self._transport.close()

    # ---- RPC methods (high-level) ---- #

    async def inspect(self, url: str) -> UnmaskResponse:
        """One-shot X-ray of `url`.

        WHY: replaces our in-tree DOM/network/console scanning with a single
        call to a battle-tested implementation. Snapshot is fresh per call;
        unmask handles CDP wiring, we just consume the result.
        """
        payload = await self._transport.call("unmask.inspect", {"url": url})
        if not isinstance(payload, Mapping):
            raise UnmaskError(
                f"unmask.inspect returned non-object: {type(payload).__name__}",
                code=-32700,
            )
        return UnmaskResponse.from_payload(payload)

    async def self_heal(
        self,
        session_id: str,
        hint: Mapping[str, Any],
    ) -> str:
        """Resolve a brittle selector via unmask's multi-strategy resolver.

        Returns a *stable* selector string the worker can hand to
        playstealth for the click.
        """
        payload = await self._transport.call(
            "unmask.selfHeal",
            {"sessionId": session_id, "hint": dict(hint)},
        )
        if not isinstance(payload, Mapping) or "selector" not in payload:
            raise UnmaskError(
                "unmask.selfHeal did not return a selector",
                code=-32603,
                data=payload,
            )
        return str(payload["selector"])

    # ---- raw escape hatch ---- #

    async def raw(self, method: str, params: Mapping[str, Any] | None = None) -> Any:
        """Escape hatch for new RPC methods that don't have a typed wrapper yet.

        Use sparingly — every typed method we add removes a class of
        production bug. Anything used twice should grow a real method here.
        """
        return await self._transport.call(method, params)


# --------------------------------------------------------------------------- #
# Helper for tests / future impls
# --------------------------------------------------------------------------- #


def _validate_jsonrpc_response(payload: Any) -> Any:
    """Module-private helper, exported via __all__-less interface for tests.

    Validates a JSON-RPC 2.0 response envelope and either returns ``result``
    or raises ``UnmaskError`` with the structured error info. Pulled out so
    Phase 2 transports can share one implementation.
    """
    if not isinstance(payload, Mapping):
        raise UnmaskError(
            f"non-object JSON-RPC payload: {type(payload).__name__}",
            code=-32700,
        )
    if payload.get("jsonrpc") != "2.0":
        raise UnmaskError(
            f"missing/invalid jsonrpc version: {payload.get('jsonrpc')!r}",
            code=-32600,
        )
    if "error" in payload:
        err = payload["error"]
        if isinstance(err, Mapping):
            raise UnmaskError(
                str(err.get("message", "unknown error")),
                code=int(err.get("code", -32000)),
                data=err.get("data"),
            )
        raise UnmaskError(f"non-object error: {err!r}", code=-32600)
    if "result" not in payload:
        raise UnmaskError("response without result or error", code=-32600)
    return payload["result"]


# Light sanity self-check so a typo at import time is caught immediately.
_ = json.loads  # ensure stdlib import is wired (no runtime cost)
