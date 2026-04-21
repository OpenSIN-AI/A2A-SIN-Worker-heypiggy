"""OpenSIN Global Brain policy helpers.

WHY: Agents must never leave env/secret state scattered. They detect, normalize,
sync to Infisical, verify, then ingest a redacted fact into Global Brain so all
other agents can learn the same compliance state.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from global_brain_client import GlobalBrainClient


SYNCABLE_CLASSIFICATIONS = {"secret", "env", "credential"}
LEGACY_SOURCES = {"local", "repo", "ci", "runtime", "scan"}
SECRET_KEY_HINTS = (
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "API_KEY",
    "APIKEY",
    "PRIVATE_KEY",
    "SESSION",
    "COOKIE",
    "EMAIL",
)
ENV_KEY_HINTS = (
    "URL",
    "URI",
    "HOST",
    "PORT",
    "PATH",
    "DOMAIN",
    "MODEL",
    "TIMEOUT",
    "COUNT",
    "FLAG",
    "MODE",
)


@dataclass(slots=True)
class SecretSource:
    file: str
    path: str
    line: int
    origin: str = "local"


@dataclass(slots=True)
class InfisicalTarget:
    project_id: str
    environment: str
    folder: str
    secret_path: str | None = None
    vault: str = "infisical"


@dataclass(slots=True)
class SecretDetection:
    key: str
    value: str | None = field(default=None, repr=False)
    classification: str = "secret"
    source: SecretSource = field(default_factory=lambda: SecretSource(file="", path="", line=0))
    repo: str = ""
    branch: str = "main"
    agent_id: str = ""
    legacy_flag: bool = True
    # Rotation metadata - tracks secret lifecycle
    owner: str = ""  # Who is responsible for this secret (email, team, agent)
    ttl_days: int | None = None  # Time-to-live in days (None = never expires)
    last_verified: datetime | None = None  # Last time secret was verified/rotated
    rotation_policy: str = "manual"  # "manual", "auto_rotate", "external"


@dataclass(slots=True)
class SecretRotationMetadata:
    """Extended metadata for secret rotation tracking.

    WHY: Secrets need lifecycle management beyond just existence.
    This tracks:
    - owner: responsible party for rotation
    - ttl_days: when to rotate (None = never)
    - last_verified: last confirmation the secret still works
    - rotation_policy: how rotation happens (manual vs automated)
    """

    secret_key: str
    owner: str
    ttl_days: int | None = None
    last_verified: datetime | None = None
    last_rotated: datetime | None = None
    rotation_policy: str = "manual"  # manual | auto_rotate | external
    rotation_url: str = ""  # Link to rotation docs/external system
    notes: str = ""


def normalize_env_key(key: str) -> str:
    """Normalize env keys to the canonical secret-name form."""
    cleaned = key.strip()
    if cleaned.startswith("export "):
        cleaned = cleaned[len("export ") :].strip()
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.upper().strip("_")


def classify_env_key(key: str) -> str:
    """Classify a key so policy facts can distinguish env config from secrets.

    WHY: Uppercase alone is not a secret signal. We want a deterministic,
    conservative heuristic that treats credential-looking names as secrets.
    """
    normalized = normalize_env_key(key)
    if any(hint in normalized for hint in SECRET_KEY_HINTS):
        return "secret"
    if any(hint in normalized for hint in ENV_KEY_HINTS):
        return "env"
    # Conservative default: if it looks like a system variable but not a secret
    # keyword, keep it as env. This avoids over-classifying URLs/ports as secrets.
    return "env"


def hash_secret_value(value: str | None) -> str | None:
    """Return a stable sha256 fingerprint without ever storing the raw value."""
    if value is None:
        return None
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def redact_value(value: str | None) -> str:
    """Hide the actual secret while still preserving a visible marker."""
    return "[REDACTED]" if value else ""


def must_sync_now(
    detection: SecretDetection,
    *,
    verified_keys: set[str] | None = None,
    known_infisical_paths: set[str] | None = None,
) -> bool:
    """Decide whether this detection must be pushed to Infisical immediately."""
    verified_keys = verified_keys or set()
    known_infisical_paths = known_infisical_paths or set()

    key = normalize_env_key(detection.key)
    if detection.classification not in SYNCABLE_CLASSIFICATIONS:
        return False
    if detection.source.origin not in LEGACY_SOURCES:
        return False
    if key in verified_keys:
        return False
    if detection.source.path in known_infisical_paths:
        return False
    return True


def build_secret_fact(
    detection: SecretDetection,
    target: InfisicalTarget | None,
    *,
    event: str,
    status: str,
    notes: str = "",
) -> dict[str, Any]:
    """Build a brain-safe fact that excludes raw secret material."""
    key = normalize_env_key(detection.key)
    fact = {
        "fact_type": "secret_event",
        "fact_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_id": detection.agent_id,
        "repo": detection.repo,
        "branch": detection.branch,
        "event": event,
        "key": key,
        "classification": detection.classification,
        "source": {
            "file": detection.source.file,
            "path": detection.source.path,
            "line": detection.source.line,
            "origin": detection.source.origin,
        },
        "target": None
        if target is None
        else {
            "vault": target.vault,
            "project_id": target.project_id,
            "environment": target.environment,
            "folder": target.folder,
            "secret_path": target.secret_path or key,
        },
        "status": status,
        "legacy_flag": detection.legacy_flag,
        "hash": hash_secret_value(detection.value),
        "notes": notes,
        "redacted": True,
    }
    return fact


async def ingest_secret_event(
    brain: GlobalBrainClient,
    detection: SecretDetection,
    target: InfisicalTarget | None,
    *,
    event: str,
    status: str,
    notes: str = "",
) -> dict[str, Any]:
    """Store a redacted policy fact in Global Brain."""
    fact = build_secret_fact(detection, target, event=event, status=status, notes=notes)
    brain_text = json.dumps(
        {
            "key": fact["key"],
            "event": fact["event"],
            "status": fact["status"],
            "source": fact["source"],
            "target": fact["target"],
            "hash": fact["hash"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    await brain.ingest(
        "fact",
        brain_text,
        scope="project",
        extra={"policyFact": fact},
    )
    return fact


__all__ = [
    "InfisicalTarget",
    "SecretDetection",
    "SecretSource",
    "build_secret_fact",
    "hash_secret_value",
    "ingest_secret_event",
    "classify_env_key",
    "must_sync_now",
    "normalize_env_key",
    "redact_value",
]
