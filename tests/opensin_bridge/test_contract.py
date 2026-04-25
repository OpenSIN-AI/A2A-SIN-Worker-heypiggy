"""Unit tests for the isolated bridge contract boundary."""

from __future__ import annotations

import pytest

import bridge_retry

from opensin_bridge.contract import (
    BRIDGE_CONTRACT_VERSION,
    BridgeContract,
    BridgeRequest,
    BridgeResponse,
    ContractMismatch,
    CONTRACT_VERSION,
    DEFAULT_CONTRACT,
    IDEMPOTENT_METHODS,
    MUTATING_METHODS,
    attach_idempotency,
    classify_retry_category,
    validate_contract_version,
)


def test_default_contract_matches_current_method_sets() -> None:
    assert DEFAULT_CONTRACT.required_methods
    assert DEFAULT_CONTRACT.required_error_codes
    assert DEFAULT_CONTRACT.idempotent_methods == IDEMPOTENT_METHODS
    assert DEFAULT_CONTRACT.required_methods.issuperset(MUTATING_METHODS)


def test_validate_contract_version_accepts_minor_drift(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("WARNING")
    validate_contract_version("1.2.3")
    assert BRIDGE_CONTRACT_VERSION == CONTRACT_VERSION
    assert any("version drift" in rec.message for rec in caplog.records)


def test_validate_contract_version_rejects_major_mismatch() -> None:
    with pytest.raises(ContractMismatch) as excinfo:
        validate_contract_version("2.0.0")
    assert excinfo.value.retry_hint == "abort"


@pytest.mark.parametrize("payload", [{}, {"tool": "dom.click", "params": {}}])
def test_request_roundtrip_strictness(payload: dict[str, object]) -> None:
    if payload:
        request = BridgeRequest.from_dict(payload)
        assert request.tool == "dom.click"
        assert request.contract_version == CONTRACT_VERSION
        assert request.to_dict()["tool"] == "dom.click"
        return

    with pytest.raises(ValueError, match="missing tool"):
        BridgeRequest.from_dict(payload)


def test_response_roundtrip_strictness() -> None:
    response = BridgeResponse.from_dict({"ok": True, "result": {"x": 1}})
    assert response.ok is True
    assert response.to_dict()["ok"] is True


def test_attach_idempotency_is_deterministic_for_idempotent_methods() -> None:
    first = attach_idempotency({"tool": "dom.snapshot", "params": {"a": 1}})
    second = attach_idempotency({"tool": "dom.snapshot", "params": {"a": 1}})
    assert first["idempotency_key"] == second["idempotency_key"]


def test_attach_idempotency_generates_unique_key_for_mutating_methods() -> None:
    first = attach_idempotency({"tool": "dom.click", "params": {"a": 1}})
    second = attach_idempotency({"tool": "dom.click", "params": {"a": 1}})
    assert first["idempotency_key"] != second["idempotency_key"]


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"error": "timeout while navigating"}, "transient"),
        ({"error": "target closed"}, "transient"),
        ({"error": "unauthorized"}, "permanent"),
        ({"error": {"code": "transport_error"}}, "transient"),
        ({"error": {"code": "rpc_invalid"}}, "permanent"),
        ({"ok": False, "reason": "network error"}, "transient"),
        ({"ok": False, "reason": "invalid parameter"}, "permanent"),
    ],
)
def test_retry_category_parity(payload: object, expected: str) -> None:
    assert classify_retry_category(payload) == expected
    assert bridge_retry.classify_result(payload) == expected


def test_custom_contract_subset() -> None:
    subset = BridgeContract(
        required_methods=frozenset({"dom.snapshot"}),
        required_error_codes=frozenset({"timeout"}),
        idempotent_methods=frozenset({"dom.snapshot"}),
    )
    assert subset.is_method_supported("dom.snapshot") is True
    assert subset.is_method_supported("dom.click") is False
