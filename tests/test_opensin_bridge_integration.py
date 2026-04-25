from __future__ import annotations

import asyncio

import opensin_bridge_integration as integration
from opensin_bridge.adapter import BridgeAdapter
from opensin_bridge.contract import BridgeContract
from opensin_bridge_integration import BridgeAdapterConfig
import pytest


async def _rpc(method: str, params: dict[str, object]) -> object:
    return {"method": method, "params": params}


def _contract_payload() -> dict[str, object]:
    return {
        "version": "1.2.3",
        "methods": {
            "dom.snapshot": {"idempotent": True, "description": "snapshot"},
            "dom.click": {"idempotent": False, "description": "click"},
        },
        "errorCodes": ["METHOD_NOT_FOUND", "INTERNAL"],
        "surfaceKind": "dom",
    }


def test_configure_adapter_extracts_capabilities_from_mapping() -> None:
    async def rpc(method: str, params: dict[str, object]) -> object:
        assert method == "bridge.contract"
        return _contract_payload()

    config = asyncio.run(integration.configure_adapter(rpc))

    assert isinstance(config, BridgeAdapterConfig)
    assert config.version == "1.2.3"
    assert config.methods["dom.snapshot"]["idempotent"] is True
    assert config.idempotent_methods == frozenset({"dom.snapshot"})
    assert config.error_codes == frozenset({"METHOD_NOT_FOUND", "INTERNAL"})
    assert config.tool_surface_kind == "dom"


def test_configure_adapter_accepts_list_methods() -> None:
    async def rpc(method: str, params: dict[str, object]) -> object:
        payload = _contract_payload()
        payload["methods"] = [
            {"name": "dom.snapshot", "idempotent": True},
            {"name": "dom.click", "idempotent": False},
        ]
        return payload

    config = asyncio.run(integration.configure_adapter(rpc))

    assert set(config.methods) == {"dom.snapshot", "dom.click"}
    assert config.idempotent_methods == frozenset({"dom.snapshot"})


def test_configure_adapter_rejects_major_mismatch() -> None:
    async def rpc(method: str, params: dict[str, object]) -> object:
        payload = _contract_payload()
        payload["version"] = "2.0.0"
        return payload

    with pytest.raises(integration.ContractMismatchError):
        asyncio.run(integration.configure_adapter(rpc))


def test_make_stack_defaults_to_legacy_adapter(monkeypatch) -> None:
    monkeypatch.delenv("BRIDGE_ADAPTER", raising=False)
    monkeypatch.delenv("OPENSIN_BRIDGE_V2", raising=False)
    monkeypatch.delenv("OPENSIN_V2", raising=False)

    async def fail_configure(*args, **kwargs):
        raise AssertionError("configure_adapter must not run in legacy mode")

    monkeypatch.setattr(integration, "configure_adapter", fail_configure)

    stack = integration.make_stack(_rpc, session_id="sess-1")

    assert isinstance(stack.bridge, BridgeAdapter)
    assert stack.recorder.session_id == "sess-1"
    assert stack.adapter_mode == "legacy"
    assert stack.adapter_config is None


def test_make_stack_uses_contract_negotiation_when_opted_in(monkeypatch) -> None:
    monkeypatch.setenv("BRIDGE_ADAPTER", "opensin")

    captured: dict[str, object] = {}

    class FakeBridgeAdapter:
        def __init__(self, rpc, **kwargs):
            captured["rpc"] = rpc
            captured["kwargs"] = kwargs

    
    async def fake_configure(rpc, **kwargs):
        return BridgeAdapterConfig(
            version="1.2.3",
            methods={"dom.snapshot": {"idempotent": True}},
            idempotent_methods=frozenset({"dom.snapshot"}),
            error_codes=frozenset({"METHOD_NOT_FOUND"}),
            tool_surface_kind="dom",
        )

    monkeypatch.setattr(integration, "configure_adapter", fake_configure)
    monkeypatch.setattr(integration, "BridgeAdapter", FakeBridgeAdapter)

    stack = integration.make_stack(_rpc, session_id="sess-2")

    assert captured["rpc"] is _rpc
    assert isinstance(captured["kwargs"]["contract"], BridgeContract)
    assert captured["kwargs"]["contract"].required_methods == frozenset({"dom.snapshot"})
    assert captured["kwargs"]["inject_idempotency"] is True
    assert stack.adapter_mode == "opensin_v2"
    assert stack.adapter_config is not None
    assert stack.adapter_config.version == "1.2.3"
    assert stack.recorder.session_id == "sess-2"


def test_make_stack_accepts_opensin_v2_alias(monkeypatch) -> None:
    monkeypatch.delenv("BRIDGE_ADAPTER", raising=False)
    monkeypatch.setenv("OPENSIN_BRIDGE_V2", "1")

    async def fake_configure(rpc, **kwargs):
        return BridgeAdapterConfig(
            version="1.2.3",
            methods={"dom.snapshot": {"idempotent": True}},
            idempotent_methods=frozenset({"dom.snapshot"}),
            error_codes=frozenset(),
            tool_surface_kind="dom",
        )

    monkeypatch.setattr(integration, "configure_adapter", fake_configure)

    stack = integration.make_stack(_rpc)

    assert stack.adapter_mode == "opensin_v2"
    assert stack.adapter_config is not None


def test_make_stack_explicit_legacy_wins_over_v2_flags(monkeypatch) -> None:
    monkeypatch.setenv("BRIDGE_ADAPTER", "legacy")
    monkeypatch.setenv("OPENSIN_BRIDGE_V2", "1")
    monkeypatch.setenv("OPENSIN_V2", "1")

    async def fail_configure(*args, **kwargs):
        raise AssertionError("configure_adapter must not run in legacy mode")

    monkeypatch.setattr(integration, "configure_adapter", fail_configure)

    stack = integration.make_stack(_rpc, session_id="sess-3")

    assert isinstance(stack.bridge, BridgeAdapter)
    assert stack.recorder.session_id == "sess-3"
    assert stack.adapter_mode == "legacy"
    assert stack.adapter_config is None
