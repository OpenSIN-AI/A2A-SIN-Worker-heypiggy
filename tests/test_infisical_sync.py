from pathlib import Path
from unittest.mock import AsyncMock

from global_brain_client import GlobalBrainClient
from global_brain_policy import InfisicalTarget
from infisical_sync import (
    discover_default_roots,
    export_env_from_infisical,
    normalize_env_file,
    parse_env_text,
    sync_env_file_to_infisical,
)


def test_parse_env_text_handles_export_and_yaml_and_empty_values():
    text = """
    export FOO=bar
    BAZ: qux
    EMPTY=
    QUOTED=""
    # comment
    """

    mapping = parse_env_text(text)

    assert mapping["FOO"] == "bar"
    assert mapping["BAZ"] == "qux"
    assert mapping["EMPTY"] == "__EMPTY__"
    assert mapping["QUOTED"] == "__EMPTY__"


def test_normalize_env_file_writes_portable_key_value_pairs(tmp_path: Path):
    source = tmp_path / ".env"
    source.write_text("export foo=bar\nhello: world\n")

    normalized = normalize_env_file(source)

    try:
        text = normalized.path.read_text()
        assert "FOO=bar" in text
        assert "HELLO=world" in text
    finally:
        normalized.path.unlink(missing_ok=True)


def test_discover_default_roots_includes_repo_and_common_agent_dirs(tmp_path: Path, monkeypatch):
    repo = tmp_path / "A2A-SIN-Worker-heypiggy"
    repo.mkdir()
    dev = tmp_path / "dev"
    dev.mkdir()
    opensin_bridge = dev / "OpenSIN-Bridge"
    opensin_bridge.mkdir()
    opencode = tmp_path / ".config" / "opencode"
    opencode.mkdir(parents=True)

    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    roots = discover_default_roots(repo)

    assert repo.resolve() in roots
    assert opensin_bridge.resolve() in roots
    assert opencode.resolve() in roots


def test_sync_env_file_to_infisical_ingests_brain_facts(tmp_path: Path, monkeypatch):
    source = tmp_path / ".env"
    source.write_text("BRIDGE_MCP_URL=https://example.invalid/mcp\n", encoding="utf-8")

    fake_brain = GlobalBrainClient(base_url="http://127.0.0.1:7070")
    fake_brain.ingest = AsyncMock(return_value={"ok": True})  # type: ignore[method-assign]

    target = InfisicalTarget(project_id="proj-1", environment="dev", folder="/opensin/test")

    monkeypatch.setattr("subprocess.run", lambda *a, **k: None)

    result = sync_env_file_to_infisical(
        source,
        target,
        token="token-123",
        brain=fake_brain,
        repo="repo-1",
        agent_id="agent-1",
    )

    assert result.brain_facts == 1
    assert fake_brain.ingest.await_count == 1


def test_export_env_from_infisical_parses_dotenv_export(monkeypatch):
    class Result:
        stdout = 'export FOO=bar\nBAR="baz"\n'

    captured = {}

    def fake_run(cmd, check, capture_output, text, env):
        captured["cmd"] = cmd
        captured["env"] = env
        return Result()

    monkeypatch.setattr("infisical_sync.subprocess.run", fake_run)

    snapshot = export_env_from_infisical(
        project_id="proj-1",
        environment="dev",
        folder_root="/opensin/test",
        domain="https://eu.infisical.com",
    )

    assert snapshot == {"FOO": "bar", "BAR": "baz"}
    assert captured["cmd"][:2] == ["infisical", "export"]
    assert captured["env"]["INFISICAL_API_URL"] == "https://eu.infisical.com"
