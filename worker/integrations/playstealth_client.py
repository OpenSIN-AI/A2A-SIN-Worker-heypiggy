"""Subprocess client for SIN-CLIs/playstealth-cli.

Status: Skeleton. Phase 2 fills in the actual ``asyncio.create_subprocess_exec``
plumbing.

Design choices and why:

* **Subprocess, not in-process import.** playstealth lives in its own venv,
  has its own Playwright install, its own state directory. Importing it
  in-process would couple our deps (and any breaking change in playstealth
  would crash our test suite). Subprocess + state files keeps the seam clean.
* **JSON-first output (with stdout-text fallback).** We track upstream issue
  P-1 ("--json flag per command"). Until that lands we parse the human-readable
  stdout snapshot via small, anchored regexes; a snapshot test pins the
  format we accept. Once playstealth ships ``--json``, the parsing layer
  collapses to ``json.loads`` and we delete the regex.
* **Exit-code based classification.** Tracks issue P-2:
    0  -> ok
    64 -> soft-fail (resumable: re-call ``resume-survey``)
    65 -> hard-fail (manual intervention required)
  Until those codes are official we map any non-zero to ``hard-fail`` to
  fail closed.
* **State file hand-off.** ``playstealth state`` writes atomic JSON. We
  read that file (path from ``PLAYSTEALTH_STATE_PATH``) rather than parsing
  stdout for state — atomic, reproducible, and survives crashes.

Reference:
    https://github.com/SIN-CLIs/playstealth-cli  (README "Kernbefehle")

What is NOT in this skeleton (intentionally — Phase 2):

* The actual subprocess invocation.
* Real artefact wiring (``PLAYSTEALTH_ARTIFACTS_DIR`` upload to our blob).
* Streaming events (P-3) — feature not yet upstream.
"""

from __future__ import annotations

import enum
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence


# --------------------------------------------------------------------------- #
# Errors and result types
# --------------------------------------------------------------------------- #


class PlaystealthExitCode(enum.IntEnum):
    """Mirrors the proposed exit-code convention (upstream issue P-2)."""

    OK = 0
    SOFT_FAIL = 64  # resumable
    HARD_FAIL = 65  # manual intervention required


class PlaystealthError(RuntimeError):
    """Raised when a playstealth invocation cannot be completed.

    Carries the exit code and stderr so the worker's retry policy can
    branch on whether it's worth a ``resume-survey``.
    """

    def __init__(
        self,
        message: str,
        *,
        exit_code: int = -1,
        stderr: str = "",
        stdout: str = "",
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr = stderr
        self.stdout = stdout

    @property
    def is_resumable(self) -> bool:
        """True when the failure was a documented soft-fail.

        Until upstream P-2 ships, this is conservatively ``False`` for any
        non-zero exit. We refuse to silently "retry into a ban".
        """
        return self.exit_code == int(PlaystealthExitCode.SOFT_FAIL)


@dataclass(frozen=True)
class PlaystealthResult:
    """Outcome of one playstealth invocation.

    ``state`` is the parsed contents of the atomic state file (if present).
    ``stdout_snapshot`` is kept around for audit / debugging — never used
    for control flow once ``--json`` is available upstream.
    """

    command: str
    exit_code: int
    stdout_snapshot: str = ""
    state: Mapping[str, Any] = field(default_factory=dict)
    artefacts: Sequence[str] = field(default_factory=tuple)


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #


class PlaystealthClient:
    """High-level subprocess wrapper.

    Phase 1 stops at the typed contract; every method that would actually
    spawn a subprocess raises ``NotImplementedError`` so a half-finished
    impl can't sneak into production unnoticed.
    """

    DEFAULT_BINARY = "playstealth"

    def __init__(
        self,
        *,
        binary: str | None = None,
        state_path: str | None = None,
        artefacts_dir: str | None = None,
    ) -> None:
        self._binary = binary or os.environ.get(
            "PLAYSTEALTH_BIN", self.DEFAULT_BINARY
        )
        self._state_path = Path(
            state_path
            or os.environ.get("PLAYSTEALTH_STATE_PATH", ".playstealth/state.json")
        )
        self._artefacts_dir = Path(
            artefacts_dir
            or os.environ.get("PLAYSTEALTH_ARTIFACTS_DIR", ".playstealth/artefacts")
        )

    # ---- discovery ---- #

    def is_available(self) -> bool:
        """Cheap pre-check used by ``worker.cli`` startup gating.

        WHY a separate method: we want the worker to fail-closed at boot if
        the playstealth binary is missing on PATH. ``shutil.which`` is the
        cheapest reliable check we can do without spawning anything.
        """
        return shutil.which(self._binary) is not None

    # ---- high-level ops (filled in Phase 2) ---- #

    async def open_list(self) -> PlaystealthResult:
        """``playstealth open-list`` — open the heypiggy survey list page."""
        raise NotImplementedError(
            "PlaystealthClient.open_list() lands in Phase 2. "
            "See docs/PLANS/04-MIGRATION-ROADMAP.md"
        )

    async def click_survey(self, *, index: int) -> PlaystealthResult:
        """``playstealth click-survey --index N`` — click into a survey card.

        On success the resulting tab url + state.tab_id is in the state file.
        """
        if index < 0:
            raise ValueError(f"index must be >= 0, got {index!r}")
        raise NotImplementedError(
            "PlaystealthClient.click_survey() lands in Phase 2."
        )

    async def inspect_survey(self, *, index: int) -> PlaystealthResult:
        """``playstealth inspect-survey --index N`` — read-only DOM/state probe."""
        raise NotImplementedError("Phase 2.")

    async def answer_survey(
        self,
        *,
        index: int,
        option_index: int,
    ) -> PlaystealthResult:
        """``playstealth answer-survey --index N --option-index M``.

        WHY explicit kw-only args: the upstream CLI takes both as required
        flags; we refuse positional sloppiness so a future change to a
        third flag doesn't silently break callers.
        """
        if option_index < 0:
            raise ValueError(f"option_index must be >= 0, got {option_index!r}")
        raise NotImplementedError("Phase 2.")

    async def run_survey(
        self,
        *,
        index: int,
        max_steps: int = 5,
    ) -> PlaystealthResult:
        """``playstealth run-survey --index N --max-steps M`` — full auto-run."""
        if max_steps < 1:
            raise ValueError(f"max_steps must be >= 1, got {max_steps!r}")
        raise NotImplementedError("Phase 2.")

    async def resume_survey(self, *, max_steps: int = 5) -> PlaystealthResult:
        """``playstealth resume-survey`` — resume after soft-fail."""
        raise NotImplementedError("Phase 2.")

    # ---- introspection ---- #

    async def manifest(self) -> Mapping[str, Any]:
        """``playstealth manifest`` — JSON tool registry.

        We pin the manifest at startup and refuse to talk to a playstealth
        whose tool set drifted away from what we tested against. This is
        the cheapest defence against silent upstream changes.
        """
        raise NotImplementedError("Phase 2.")

    async def state(self) -> Mapping[str, Any]:
        """Read the atomic state file. No subprocess needed."""
        if not self._state_path.exists():
            return {}
        try:
            import json

            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise PlaystealthError(
                f"could not parse playstealth state at {self._state_path}: {e!r}"
            ) from e
