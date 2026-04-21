from pathlib import Path

import pytest

from global_brain_policy import (
    InfisicalTarget,
    SecretDetection,
    SecretSource,
    build_secret_fact,
    classify_env_key,
    hash_secret_value,
    must_sync_now,
    normalize_env_key,
)


def test_normalize_env_key():
    assert normalize_env_key(" export Bridge-MCP-Url ") == "BRIDGE_MCP_URL"


def test_hash_secret_value_is_stable():
    assert hash_secret_value("abc") == hash_secret_value("abc")
    assert hash_secret_value("abc").startswith("sha256:")


def test_must_sync_now_on_legacy_secret_detection():
    detection = SecretDetection(
        key="bridge_mcp_url",
        value="https://example.invalid",
        classification="secret",
        source=SecretSource(file=".env", path="/repo/.env", line=1, origin="local"),
        repo="OpenSIN-Bridge",
        branch="main",
        agent_id="agent-1",
    )

    assert must_sync_now(detection) is True


def test_build_secret_fact_redacts_and_hashes():
    detection = SecretDetection(
        key="NVIDIA_API_KEY",
        value="super-secret",
        classification="secret",
        source=SecretSource(file=".env", path="/repo/.env", line=2, origin="local"),
        repo="A2A-SIN-Worker-heypiggy",
        branch="main",
        agent_id="agent-2",
    )
    target = InfisicalTarget(
        project_id="proj-123",
        environment="dev",
        folder="/opensin/a2a-sin-worker-heypiggy",
    )

    fact = build_secret_fact(detection, target, event="sync_success", status="verified")

    assert fact["redacted"] is True
    assert fact["hash"].startswith("sha256:")
    assert fact["target"]["vault"] == "infisical"
    assert fact["key"] == "NVIDIA_API_KEY"


def test_classify_env_key_is_secret_aware():
    assert classify_env_key("NVIDIA_API_KEY") == "secret"
    assert classify_env_key("HEYPIGGY_EMAIL") == "secret"
    assert classify_env_key("BRIDGE_MCP_URL") == "env"
