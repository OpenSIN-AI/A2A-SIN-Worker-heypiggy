"""Pytest defaults for deterministic config loading."""

from __future__ import annotations

import os


# Tests should not depend on the repository's live saved credentials unless a
# specific test opts in explicitly. Production runs should prefer explicit
# runtime secrets and only load saved .env files when explicitly enabled.
os.environ.setdefault("HEYPIGGY_DISABLE_SAVED_ENV", "1")
os.environ.setdefault("INFISICAL_AUTO_PULL", "0")
