"""Tests für worker.modules Import Safety Net (SOTA-002 Phase 1)."""
from __future__ import annotations
import pytest


class TestModularImport:
    def test_worker_modules_imports(self):
        import worker.modules  # noqa: F811

    def test_heypiggy_monolith_imports(self):
        import heypiggy_vision_worker  # noqa: F811

    def test_worker_package_imports(self):
        from worker import cli, loop, context  # noqa: F401

    def test_modules_path_exists(self):
        from pathlib import Path
        p = Path(__file__).parent.parent / "worker" / "modules"
        assert p.exists(), f"worker/modules/ path missing: {p}"
        assert (p / "__init__.py").exists()
