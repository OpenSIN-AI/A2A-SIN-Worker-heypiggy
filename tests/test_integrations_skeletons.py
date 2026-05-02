"""Contract tests for ``worker/integrations`` and ``worker/ai`` skeletons.

These tests pin the *public surface* of the Phase-2 / Phase-1 seams. They do
NOT exercise real subprocesses or HTTP — that is exactly the point: we want
green tests today against an explicit ``NotImplementedError`` so a Phase-2
PR has to actively replace the body, not change the surface.

If any of these tests start failing, that means a public type or method
shape changed and the migration plan needs to be updated alongside.
"""

from __future__ import annotations

import asyncio
import inspect

import pytest

from worker.ai.backend import (
    AIBackend,
    AIBackendError,
    AIBackendSelector,
    AICallResult,
    AICapability,
    AIGatewayBackend,
    PuterFallbackBackend,
    select_backend,
)
from worker.integrations import (
    PlaystealthClient,
    PlaystealthError,
    PlaystealthResult,
    UnmaskClient,
    UnmaskError,
    UnmaskResponse,
)
from worker.integrations.playstealth_client import PlaystealthExitCode
from worker.integrations.unmask_client import (
    UnmaskConsoleEvent,
    UnmaskElement,
    UnmaskNetworkEvent,
    _validate_jsonrpc_response,
)


# --------------------------------------------------------------------------- #
# Unmask payload parser  (real logic — tested for real)
# --------------------------------------------------------------------------- #


class TestUnmaskResponseFromPayload:
    def test_minimal_payload_parses(self) -> None:
        resp = UnmaskResponse.from_payload({"url": "https://x", "title": "T"})
        assert resp.url == "https://x"
        assert resp.title == "T"
        assert resp.elements == ()
        assert resp.network == ()
        assert resp.console == ()

    def test_full_payload_parses(self) -> None:
        payload = {
            "url": "https://example.com",
            "title": "Example",
            "elements": [
                {"selector": "#a", "label": "go", "confidence": 0.9},
                {"selector": ".b", "role": "button"},
            ],
            "network": [
                {
                    "url": "https://api/x",
                    "method": "POST",
                    "status": 200,
                    "requestHeaders": {"X": "1"},
                    "responseBody": "ok",
                }
            ],
            "console": [{"type": "warning", "text": "deprecated"}],
        }
        resp = UnmaskResponse.from_payload(payload)
        assert len(resp.elements) == 2
        assert resp.elements[0] == UnmaskElement(
            selector="#a", label="go", role=None, confidence=0.9
        )
        assert resp.network[0] == UnmaskNetworkEvent(
            url="https://api/x",
            method="POST",
            status=200,
            request_headers={"X": "1"},
            response_body="ok",
        )
        assert resp.console[0] == UnmaskConsoleEvent(type="warning", text="deprecated")

    def test_missing_url_raises_unmask_error(self) -> None:
        with pytest.raises(UnmaskError) as ei:
            UnmaskResponse.from_payload({"title": "no url"})
        assert ei.value.code == -32700
        # surface a useful hint (the keys we DID see)
        assert isinstance(ei.value.data, dict)
        assert ei.value.data.get("payload_keys") == ["title"]

    def test_garbage_element_raises(self) -> None:
        with pytest.raises(UnmaskError):
            UnmaskResponse.from_payload(
                {"url": "u", "elements": [{"label": "no selector"}]}
            )


# --------------------------------------------------------------------------- #
# JSON-RPC envelope validator  (real logic — tested for real)
# --------------------------------------------------------------------------- #


class TestValidateJsonRpcResponse:
    def test_happy_result(self) -> None:
        out = _validate_jsonrpc_response(
            {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
        )
        assert out == {"ok": True}

    def test_error_envelope(self) -> None:
        with pytest.raises(UnmaskError) as ei:
            _validate_jsonrpc_response(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {"code": -32601, "message": "method not found"},
                }
            )
        assert ei.value.code == -32601
        assert "method not found" in str(ei.value)

    def test_non_object(self) -> None:
        with pytest.raises(UnmaskError):
            _validate_jsonrpc_response("not a dict")

    def test_wrong_jsonrpc_version(self) -> None:
        with pytest.raises(UnmaskError):
            _validate_jsonrpc_response({"jsonrpc": "1.0", "result": {}})

    def test_missing_result_and_error(self) -> None:
        with pytest.raises(UnmaskError):
            _validate_jsonrpc_response({"jsonrpc": "2.0", "id": 1})


# --------------------------------------------------------------------------- #
# Skeleton surfaces — Phase-1/2 seam contracts
# --------------------------------------------------------------------------- #


class TestSkeletonContracts:
    """Make sure the seam exists and stays stable."""

    def test_unmask_client_from_env_is_not_implemented(self) -> None:
        # explicit: the seam exists, the body does not yet.
        with pytest.raises(NotImplementedError):
            UnmaskClient.from_env()

    def test_playstealth_client_constructs_without_binary(self, tmp_path) -> None:
        # is_available() must work even when the binary is missing — used at
        # boot to decide whether to fail closed.
        client = PlaystealthClient(
            binary="definitely-not-installed-xyz",
            state_path=str(tmp_path / "state.json"),
            artefacts_dir=str(tmp_path / "artefacts"),
        )
        assert client.is_available() is False

    @pytest.mark.asyncio
    async def test_playstealth_state_returns_empty_when_missing(self, tmp_path) -> None:
        client = PlaystealthClient(
            binary="x",
            state_path=str(tmp_path / "missing.json"),
        )
        assert await client.state() == {}

    @pytest.mark.asyncio
    async def test_playstealth_state_parses_existing_file(self, tmp_path) -> None:
        sf = tmp_path / "state.json"
        sf.write_text('{"tab_id": "abc", "step": 3}', encoding="utf-8")
        client = PlaystealthClient(binary="x", state_path=str(sf))
        st = await client.state()
        assert st == {"tab_id": "abc", "step": 3}

    @pytest.mark.asyncio
    async def test_playstealth_state_corrupt_raises(self, tmp_path) -> None:
        sf = tmp_path / "state.json"
        sf.write_text("not json", encoding="utf-8")
        client = PlaystealthClient(binary="x", state_path=str(sf))
        with pytest.raises(PlaystealthError):
            await client.state()

    @pytest.mark.asyncio
    async def test_playstealth_methods_are_phase_2(self) -> None:
        client = PlaystealthClient(binary="x")
        with pytest.raises(NotImplementedError):
            await client.open_list()
        with pytest.raises(NotImplementedError):
            await client.click_survey(index=0)

    def test_playstealth_argument_validation_runs_before_phase2(self) -> None:
        """Validation guards should fire even though body is NotImplementedError.

        WHY: sloppy callers shouldn't pass negative indices and only find
        out at Phase-2 review time.
        """
        client = PlaystealthClient(binary="x")
        with pytest.raises(ValueError):
            loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(
                client.click_survey(index=-1)
            )
        with pytest.raises(ValueError):
            loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(
                client.run_survey(index=0, max_steps=0)
            )

    def test_playstealth_exit_code_constants(self) -> None:
        # P-2 contract is locked in.
        assert int(PlaystealthExitCode.OK) == 0
        assert int(PlaystealthExitCode.SOFT_FAIL) == 64
        assert int(PlaystealthExitCode.HARD_FAIL) == 65

    def test_playstealth_error_resumability(self) -> None:
        soft = PlaystealthError("x", exit_code=64)
        hard = PlaystealthError("y", exit_code=65)
        unknown = PlaystealthError("z", exit_code=1)
        assert soft.is_resumable is True
        assert hard.is_resumable is False
        assert unknown.is_resumable is False  # fail-closed default

    def test_playstealth_result_is_frozen_dataclass(self) -> None:
        r = PlaystealthResult(command="ok", exit_code=0)
        with pytest.raises(Exception):
            r.exit_code = 1  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# AI backend contracts
# --------------------------------------------------------------------------- #


class TestAIBackendSurface:
    def test_ai_gateway_capabilities(self) -> None:
        b = AIGatewayBackend(api_key="x")
        assert AICapability.VISION in b.capabilities
        assert AICapability.TEXT in b.capabilities

    def test_puter_refuses_vision(self) -> None:
        b = PuterFallbackBackend()
        assert AICapability.VISION not in b.capabilities

    @pytest.mark.asyncio
    async def test_ai_gateway_health_requires_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
        assert await AIGatewayBackend(api_key=None).health() is False
        assert await AIGatewayBackend(api_key="x").health() is True

    @pytest.mark.asyncio
    async def test_ai_gateway_call_phase1(self) -> None:
        b = AIGatewayBackend(api_key="x")
        with pytest.raises(NotImplementedError):
            await b.call("hi")

    @pytest.mark.asyncio
    async def test_ai_gateway_call_without_key_raises_backend_error(self) -> None:
        b = AIGatewayBackend(api_key=None)
        with pytest.raises(AIBackendError) as ei:
            await b.call("hi")
        assert ei.value.provider == "ai_gateway"

    @pytest.mark.asyncio
    async def test_puter_call_refuses_vision_eagerly(self) -> None:
        b = PuterFallbackBackend()
        with pytest.raises(AIBackendError):
            await b.call("hi", capability=AICapability.VISION)

    @pytest.mark.asyncio
    async def test_puter_health_disabled_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AI_BACKEND_FALLBACK", raising=False)
        assert await PuterFallbackBackend().health() is False

    @pytest.mark.asyncio
    async def test_puter_health_when_explicitly_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AI_BACKEND_FALLBACK", "puter")
        assert await PuterFallbackBackend().health() is True

    @pytest.mark.asyncio
    async def test_selector_picks_primary_when_healthy(self) -> None:
        sel = AIBackendSelector(primary=AIGatewayBackend(api_key="x"))
        chosen = await sel.select(AICapability.TEXT)
        assert chosen.name == "ai_gateway"

    @pytest.mark.asyncio
    async def test_selector_raises_when_no_fallback_and_primary_unhealthy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
        sel = AIBackendSelector(primary=AIGatewayBackend(api_key=None))
        with pytest.raises(AIBackendError):
            await sel.select(AICapability.TEXT)

    @pytest.mark.asyncio
    async def test_selector_falls_back_for_text_when_primary_unhealthy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
        monkeypatch.setenv("AI_BACKEND_FALLBACK", "puter")
        sel = AIBackendSelector(
            primary=AIGatewayBackend(api_key=None),
            fallback=PuterFallbackBackend(),
        )
        chosen = await sel.select(AICapability.TEXT)
        assert chosen.name == "puter_fallback"

    @pytest.mark.asyncio
    async def test_selector_refuses_vision_via_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Vision must NEVER fall back to puter — that's the whole policy.
        monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
        monkeypatch.setenv("AI_BACKEND_FALLBACK", "puter")
        sel = AIBackendSelector(
            primary=AIGatewayBackend(api_key=None),
            fallback=PuterFallbackBackend(),
        )
        with pytest.raises(AIBackendError):
            await sel.select(AICapability.VISION)

    def test_select_backend_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AI_BACKEND_FALLBACK", raising=False)
        sel = select_backend()
        assert isinstance(sel.primary, AIGatewayBackend)
        assert sel.fallback is None  # no fallback unless explicitly opted in

    def test_select_backend_with_puter_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AI_BACKEND_FALLBACK", "puter")
        sel = select_backend()
        assert isinstance(sel.fallback, PuterFallbackBackend)


# --------------------------------------------------------------------------- #
# Sanity: every async method is actually async (catches accidental sync defs)
# --------------------------------------------------------------------------- #


class TestAsyncSurface:
    def _async_methods(self, cls: type) -> list[str]:
        return [
            name
            for name, m in inspect.getmembers(cls, predicate=inspect.iscoroutinefunction)
            if not name.startswith("_")
        ]

    def test_unmask_client_async_methods(self) -> None:
        names = self._async_methods(UnmaskClient)
        for must in ("inspect", "self_heal", "raw"):
            assert must in names, f"{must} should be async on UnmaskClient"

    def test_playstealth_client_async_methods(self) -> None:
        names = self._async_methods(PlaystealthClient)
        for must in (
            "open_list",
            "click_survey",
            "inspect_survey",
            "answer_survey",
            "run_survey",
            "resume_survey",
            "manifest",
            "state",
        ):
            assert must in names, f"{must} should be async on PlaystealthClient"

    def test_ai_backend_call_is_async(self) -> None:
        for cls in (AIGatewayBackend, PuterFallbackBackend):
            assert inspect.iscoroutinefunction(cls.call)
