"""Pytest bootstrap helpers for local repository imports.

This file exists so the exact command requested by the issue,
`pytest tests/test_state_machine.py -v`, works without relying on an
external `PYTHONPATH=.` shell prefix.

WHY:
- Pytest may start with the tests directory as the first import root in this
  repository layout.
- `agent_state_machine.py` lives at the repository root, not inside an
  installed package.
- Without a small import bootstrap, `from agent_state_machine import ...`
  can fail during collection depending on how pytest is invoked.

CONSEQUENCES:
- We insert the repository root into `sys.path` once at collection time.
- The production worker code remains unchanged.
- The acceptance command becomes reproducible in a plain shell.
"""

from __future__ import annotations

import sys
from pathlib import Path


# Resolve the repository root relative to this file instead of relying on the
# current working directory. This keeps imports stable even if pytest is started
# from a parent directory or a tool wrapper changes cwd behavior.
REPO_ROOT = Path(__file__).resolve().parent.parent


# Insert the repository root at the front of `sys.path` only when it is not
# already present. This preserves deterministic imports while avoiding duplicate
# path entries.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
