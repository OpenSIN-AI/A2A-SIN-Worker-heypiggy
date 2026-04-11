"""Pytest bootstrap helpers for flat repository imports.

WHY:
- The repository is a script-based layout instead of an installed Python package.
- Pytest can collect tests with `tests/` as the first import root, which would
  hide modules that live directly at the repository root.

CONSEQUENCES:
- The repository root is inserted into `sys.path` once during collection.
- Targeted commands like `pytest tests/test_vision_contract.py -v` work without
  extra shell prefixes or ad-hoc environment variables.
"""

from __future__ import annotations

import sys
from pathlib import Path


# Resolve the repository root relative to this file so imports stay stable even
# when pytest is launched from a different working directory.
REPO_ROOT = Path(__file__).resolve().parent.parent


# Insert the repository root only once to keep import resolution deterministic
# while avoiding duplicate path entries in long-running test sessions.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
