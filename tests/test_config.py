# ================================================================================
# DATEI: test_config.py
# PROJEKT: A2A-SIN-Worker-heyPiggy (OpenSIN AI Agent System)
# ZWECK:
# WICHTIG FÜR ENTWICKLER:
#   - Ändere nichts ohne zu verstehen was passiert
#   - Jeder Kommentar erklärt WARUM etwas getan wird, nicht nur WAS
#   - Bei Fragen erst Code lesen, dann ändern
# ================================================================================

import os
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch


import config as config_module

from config import (
    ArtifactConfig,
    BridgeConfig,
    InfisicalConfig,
    VisionConfig,
    WorkerConfig,
    load_config_from_env,
)


class WorkerConfigTests(unittest.TestCase):
    # ========================================================================
    # KLASSE: WorkerConfigTests(unittest.TestCase)
    # ZWECK:
    # WICHTIG:
    # METHODEN:
    # ========================================================================

    def test_worker_config_uses_typed_nested_defaults(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_worker_config_uses_typed_nested_defaults
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        cfg = WorkerConfig()

        self.assertIsInstance(cfg.bridge, BridgeConfig)
        self.assertIsInstance(cfg.vision, VisionConfig)
        self.assertEqual(cfg.bridge.mcp_url, "https://openjerro-opensin-bridge-mcp.hf.space/mcp")
        self.assertEqual(cfg.vision.model, "meta/llama-3.2-11b-vision-instruct")
        self.assertEqual(cfg.nvidia.primary_model, "meta/llama-3.2-11b-vision-instruct")
        self.assertEqual(
            cfg.nvidia.fallback_models,
            (
                "microsoft/phi-3.5-vision-instruct",
                "microsoft/phi-3-vision-128k-instruct",
            ),
        )
        self.assertIn("click_element", cfg.click_actions)
        self.assertIn("vision_click", cfg.click_actions)
        self.assertFalse(cfg.opensin_v2)
        self.assertIsInstance(cfg.infisical, InfisicalConfig)
        self.assertTrue(cfg.infisical.enabled)
        self.assertEqual(cfg.infisical.folder_root, "/opensin/a2a-sin-worker-heypiggy")

    def test_config_objects_are_frozen_against_runtime_mutation(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_config_objects_are_frozen_against_runtime_mutation
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        cfg = WorkerConfig()

        with self.assertRaises(FrozenInstanceError):
            setattr(cfg.bridge, "mcp_url", "https://example.invalid/mcp")

        with self.assertRaises(FrozenInstanceError):
            setattr(cfg, "click_actions", ("click_element",))


class ArtifactConfigTests(unittest.TestCase):
    # ========================================================================
    # KLASSE: ArtifactConfigTests(unittest.TestCase)
    # ZWECK:
    # WICHTIG:
    # METHODEN:
    # ========================================================================

    def test_artifact_paths_are_derived_from_run_id(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_artifact_paths_are_derived_from_run_id
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        cfg = ArtifactConfig(run_id="run-123", base_dir="/tmp/heypiggy")

        self.assertEqual(cfg.artifact_dir, Path("/tmp/heypiggy/heypiggy_run_run-123"))
        self.assertEqual(
            cfg.screenshot_dir,
            Path("/tmp/heypiggy/heypiggy_run_run-123/screenshots"),
        )
        self.assertEqual(cfg.audit_dir, Path("/tmp/heypiggy/heypiggy_run_run-123/audit"))
        self.assertEqual(
            cfg.session_dir,
            Path("/tmp/heypiggy/heypiggy_run_run-123/sessions"),
        )

    def test_ensure_dirs_creates_complete_directory_tree(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_ensure_dirs_creates_complete_directory_tree
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = ArtifactConfig(run_id="run-456", base_dir=tmpdir)

            cfg.ensure_dirs()

            self.assertTrue(cfg.artifact_dir.is_dir())
            self.assertTrue(cfg.screenshot_dir.is_dir())
            self.assertTrue(cfg.audit_dir.is_dir())
            self.assertTrue(cfg.session_dir.is_dir())


class LoadConfigFromEnvTests(unittest.TestCase):
    # ========================================================================
    # KLASSE: LoadConfigFromEnvTests(unittest.TestCase)
    # ZWECK:
    # WICHTIG:
    # METHODEN:
    # ========================================================================

    def test_load_config_from_env_uses_defaults_when_env_missing(self):
        with patch.dict(os.environ, {"HEYPIGGY_DISABLE_SAVED_ENV": "1"}, clear=True):
            cfg = load_config_from_env()

        self.assertEqual(
            cfg.bridge.health_url,
            "https://openjerro-opensin-bridge-mcp.hf.space/health",
        )
        self.assertEqual(cfg.vision.max_steps, 120)
        self.assertEqual(cfg.recorder.keyframes_on_fail, 12)
        self.assertEqual(cfg.artifacts.base_dir, "/tmp")
        self.assertTrue(cfg.artifacts.run_id)

    def test_load_config_from_env_applies_overrides_and_type_casts(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_load_config_from_env_applies_overrides_and_type_casts
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        with patch.dict(
            os.environ,
            {
                "HEYPIGGY_DISABLE_SAVED_ENV": "1",
                "BRIDGE_MCP_URL": "https://bridge.example/mcp",
                "BRIDGE_HEALTH_URL": "https://bridge.example/health",
                "BRIDGE_CONNECT_TIMEOUT": "42",
                "VISION_MODEL": "google/custom-model",
                "MAX_STEPS": "77",
                "MAX_RETRIES": "9",
                "MAX_NO_PROGRESS": "11",
                "MAX_CLICK_ESCALATIONS": "6",
                "VISION_CLI_TIMEOUT": "210",
                "NVIDIA_API_KEY": "nvapi-test",
                "NVIDIA_NIM_BASE_URL": "https://nim.example/v1",
                "NVIDIA_PRIMARY_MODEL": "meta/custom-vision",
                "NVIDIA_FALLBACK_MODELS": "nvidia/microsoft/phi-3.5-vision-instruct,nvidia/microsoft/phi-3-vision-128k-instruct",
                "NVIDIA_TIMEOUT": "88",
                "NVIDIA_MAX_INLINE_BYTES": "123456",
                "RECORDER_FPS": "2.5",
                "RECORDER_BUFFER_SECONDS": "33.5",
                "RECORDER_KEYFRAMES": "7",
                "HEYPIGGY_RUN_ID": "manual-run-id",
                "HEYPIGGY_ARTIFACT_BASE": "/var/tmp/heypiggy",
                "OPENSIN_V2": "1",
                "INFISICAL_ENABLED": "1",
                "INFISICAL_DOMAIN": "https://eu.infisical.com",
                "INFISICAL_PROJECT_ID": "proj-123",
                "INFISICAL_ENV": "prod",
                "INFISICAL_FOLDER_ROOT": "/opensin/test-agent",
                "INFISICAL_AUTO_SYNC": "1",
                "INFISICAL_SYNC_ROOTS": "/Users/jeremy/dev/A2A-SIN-Worker-heypiggy,/Users/jeremy/dev/OpenSIN-Bridge",
            },
            clear=True,
        ):
            cfg = load_config_from_env()

        self.assertEqual(cfg.bridge.mcp_url, "https://bridge.example/mcp")
        self.assertEqual(cfg.bridge.health_url, "https://bridge.example/health")
        self.assertEqual(cfg.bridge.connect_timeout, 42)
        self.assertEqual(cfg.vision.model, "google/custom-model")
        self.assertEqual(cfg.vision.max_steps, 77)
        self.assertEqual(cfg.vision.max_retries, 9)
        self.assertEqual(cfg.vision.max_no_progress, 11)
        self.assertEqual(cfg.vision.max_click_escalations, 6)
        self.assertEqual(cfg.vision.cli_timeout, 210)
        self.assertEqual(cfg.nvidia.api_key, "nvapi-test")
        self.assertEqual(cfg.nvidia.base_url, "https://nim.example/v1")
        self.assertEqual(cfg.nvidia.primary_model, "meta/custom-vision")
        self.assertEqual(
            cfg.nvidia.fallback_models,
            (
                "nvidia/microsoft/phi-3.5-vision-instruct",
                "nvidia/microsoft/phi-3-vision-128k-instruct",
            ),
        )
        self.assertEqual(cfg.nvidia.timeout, 88)
        self.assertEqual(cfg.nvidia.max_inline_bytes, 123456)
        self.assertEqual(cfg.recorder.fps, 2.5)
        self.assertEqual(cfg.recorder.buffer_seconds, 33.5)
        self.assertEqual(cfg.recorder.keyframes_on_fail, 7)
        self.assertEqual(cfg.artifacts.run_id, "manual-run-id")
        self.assertEqual(cfg.artifacts.base_dir, "/var/tmp/heypiggy")
        self.assertTrue(cfg.opensin_v2)
        self.assertTrue(cfg.infisical.enabled)
        self.assertEqual(cfg.infisical.domain, "https://eu.infisical.com")
        self.assertEqual(cfg.infisical.project_id, "proj-123")
        self.assertEqual(cfg.infisical.environment, "prod")
        self.assertEqual(cfg.infisical.folder_root, "/opensin/test-agent")
        self.assertTrue(cfg.infisical.auto_sync)
        self.assertEqual(
            cfg.infisical.sync_roots,
            ("/Users/jeremy/dev/A2A-SIN-Worker-heypiggy", "/Users/jeremy/dev/OpenSIN-Bridge"),
        )

    def test_load_config_from_env_reads_saved_env_file_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        'export HEYPIGGY_EMAIL="saved@example.com"',
                        'export HEYPIGGY_PASSWORD="saved-password"',
                        'export NVIDIA_API_KEY="nvapi-saved"',
                        'export BRIDGE_MCP_URL="https://bridge.saved/mcp"',
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "HEYPIGGY_DISABLE_SAVED_ENV": "0",
                    "HEYPIGGY_ENV_FILE": str(env_file),
                },
                clear=True,
            ):
                cfg = load_config_from_env()

        self.assertEqual(cfg.nvidia.api_key, "nvapi-saved")
        self.assertEqual(cfg.bridge.mcp_url, "https://bridge.saved/mcp")

    def test_saved_env_files_require_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            home_root = root / "home"
            repo_root.mkdir()
            home_root.mkdir()

            (repo_root / ".env").write_text(
                "\n".join(
                    [
                        'export HEYPIGGY_EMAIL="repo@example.com"',
                        'export HEYPIGGY_PASSWORD="repo-password"',
                        'export NVIDIA_API_KEY="nvapi-repo"',
                    ]
                ),
                encoding="utf-8",
            )
            (home_root / ".env").write_text(
                "\n".join(
                    [
                        'export HEYPIGGY_EMAIL="home@example.com"',
                        'export HEYPIGGY_PASSWORD="home-password"',
                        'export NVIDIA_API_KEY="nvapi-home"',
                    ]
                ),
                encoding="utf-8",
            )

            with patch.object(config_module, "__file__", str(repo_root / "config.py")):
                with patch.object(config_module.Path, "home", return_value=home_root):
                    with patch.dict(os.environ, {"HEYPIGGY_DISABLE_SAVED_ENV": "0"}, clear=True):
                        loaded = config_module.ensure_saved_env_loaded()
                        self.assertFalse(loaded)
                        self.assertNotIn("HEYPIGGY_EMAIL", os.environ)

                    with patch.dict(
                        os.environ,
                        {
                            "HEYPIGGY_DISABLE_SAVED_ENV": "0",
                            "HEYPIGGY_ALLOW_SAVED_ENV": "1",
                        },
                        clear=True,
                    ):
                        loaded = config_module.ensure_saved_env_loaded()
                        self.assertTrue(loaded)
                        self.assertEqual(os.environ["HEYPIGGY_EMAIL"], "repo@example.com")
                        self.assertEqual(os.environ["HEYPIGGY_PASSWORD"], "repo-password")
                        self.assertEqual(os.environ["NVIDIA_API_KEY"], "nvapi-repo")

    def test_worker_env_loader_pulls_from_infisical_when_enabled(self):
        with patch.dict(
            os.environ,
            {
                "HEYPIGGY_DISABLE_SAVED_ENV": "1",
                "INFISICAL_AUTO_PULL": "1",
                "INFISICAL_ENABLED": "1",
                "INFISICAL_DOMAIN": "https://eu.infisical.com",
                "INFISICAL_PROJECT_ID": "fa7758b4-f84c-4297-966e-710056d531ef",
                "INFISICAL_ENV": "dev",
                "INFISICAL_FOLDER_ROOT": "/opensin/a2a-sin-worker-heypiggy",
            },
            clear=True,
        ):
            with patch(
                "infisical_sync.export_env_from_infisical",
                return_value={
                    "NVIDIA_API_KEY": "nvapi-from-infisical",
                    "HEYPIGGY_EMAIL": "agent@example.com",
                    "HEYPIGGY_PASSWORD": "secret-from-infisical",
                },
            ):
                loaded = config_module.ensure_worker_env_loaded()
                self.assertTrue(loaded)
                self.assertEqual(os.environ["NVIDIA_API_KEY"], "nvapi-from-infisical")
                self.assertEqual(os.environ["HEYPIGGY_EMAIL"], "agent@example.com")
                self.assertEqual(os.environ["HEYPIGGY_PASSWORD"], "secret-from-infisical")
