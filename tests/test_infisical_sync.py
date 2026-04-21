from pathlib import Path

from infisical_sync import normalize_env_file, parse_env_text


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
