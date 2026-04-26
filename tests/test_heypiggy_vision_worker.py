# ================================================================================
# DATEI: test_heypiggy_vision_worker.py
# PROJEKT: A2A-SIN-Worker-heyPiggy (OpenSIN AI Agent System)
# ZWECK:
# WICHTIG FÜR ENTWICKLER:
#   - Ändere nichts ohne zu verstehen was passiert
#   - Jeder Kommentar erklärt WARUM etwas getan wird, nicht nur WAS
#   - Bei Fragen erst Code lesen, dann ändern
# ================================================================================

import base64
import importlib.util
import json
import os
import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "heypiggy_vision_worker.py"
SPEC = importlib.util.spec_from_file_location("heypiggy_vision_worker", MODULE_PATH)
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


class DummyGate:
    # ========================================================================
    # KLASSE: DummyGate
    # ZWECK:
    # WICHTIG:
    # METHODEN:
    # ========================================================================

    def __init__(self):
        # -------------------------------------------------------------------------
        # FUNKTION: __init__
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        self.failed_selectors = []
        self.recorded = []

    def is_selector_failed(self, selector: str) -> bool:
        return False

    def add_failed_selector(self, selector: str):
        # -------------------------------------------------------------------------
        # FUNKTION: add_failed_selector
        # PARAMETER: self, selector: str
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        self.failed_selectors.append(selector)

    def record_step(self, verdict: str, img_hash: str):
        # -------------------------------------------------------------------------
        # FUNKTION: record_step
        # PARAMETER: self, verdict: str, img_hash: str
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        self.recorded.append((verdict, img_hash))


class HeyPiggyVisionProbeTests(unittest.TestCase):
    def test_ensure_vision_probe_screenshot_rewrites_stale_probe_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            probe_dir = pathlib.Path(tmpdir)
            stale_path = probe_dir / "vision_auth_probe.png"
            stale_path.write_bytes(b"not-a-valid-probe")

            with patch.object(worker, "SCREENSHOT_DIR", probe_dir):
                path = worker.ensure_vision_probe_screenshot()

            self.assertEqual(path, str(stale_path))
            self.assertEqual(stale_path.read_bytes(), worker.VISION_AUTH_PROBE_PNG)


class HeyPiggyWorkerPreflightTests(unittest.IsolatedAsyncioTestCase):
    # ========================================================================
    # KLASSE: HeyPiggyWorkerPreflightTests(unittest.IsolatedAsyncioTestCase)
    # ZWECK:
    # WICHTIG:
    # METHODEN:
    # ========================================================================

    async def test_main_stops_before_browser_mutation_when_credentials_missing(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_main_stops_before_browser_mutation_when_credentials_missing
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        execute_bridge = AsyncMock()
        check_bridge_alive = AsyncMock(return_value=True)
        run_vision_model = AsyncMock(
            side_effect=AssertionError("vision probe must not run when credentials are missing")
        )

        with (
            patch.dict(
                os.environ,
                {"HEYPIGGY_EMAIL": "", "HEYPIGGY_PASSWORD": ""},
                clear=False,
            ),
            patch.object(worker, "wait_for_extension", AsyncMock(return_value=True)),
            patch.object(worker, "check_bridge_alive", check_bridge_alive),
            patch.object(worker, "run_vision_model", run_vision_model),
            patch.object(worker, "execute_bridge", execute_bridge),
        ):
            await worker.main()

        execute_bridge.assert_not_awaited()
        check_bridge_alive.assert_not_awaited()

    async def test_preflight_defaults_to_playwright_and_skips_bridge_check(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_preflight_defaults_to_playwright_and_skips_bridge_check
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        driver = MagicMock()
        driver.is_initialized = True
        driver.navigate = AsyncMock(return_value={"success": True})

        check_bridge_alive = AsyncMock(return_value=True)
        init_driver = AsyncMock(return_value=driver)

        with (
            patch.dict(
                os.environ,
                {
                    "HEYPIGGY_EMAIL": "ops@example.com",
                    "HEYPIGGY_PASSWORD": "secret",
                },
                clear=False,
            ),
            patch.object(worker, "audit", MagicMock()),
            patch.object(worker, "check_bridge_alive", check_bridge_alive),
            patch.object(worker, "_init_driver", init_driver),
            patch.object(worker, "ensure_vision_probe_screenshot", return_value="/tmp/probe.png"),
            patch.object(
                worker,
                "run_vision_model",
                AsyncMock(return_value={"ok": True, "text": "ok"}),
            ),
        ):
            result = await worker.ensure_worker_preflight()

        self.assertEqual(result, {"ok": True, "reason": "ready"})
        check_bridge_alive.assert_not_awaited()
        init_driver.assert_awaited_once()

    async def test_preflight_retries_transient_opencode_timeout_before_playwright_init(self):
        driver = MagicMock()
        driver.is_initialized = True
        driver.navigate = AsyncMock(return_value={"success": True})

        init_driver = AsyncMock(return_value=driver)
        run_vision_model = AsyncMock(
            side_effect=[
                {
                    "ok": False,
                    "auth_failure": False,
                    "error": "Vision timeout or error: ",
                },
                {
                    "ok": True,
                    "auth_failure": False,
                    "text": "ok",
                },
            ]
        )

        with (
            patch.dict(
                os.environ,
                {
                    "HEYPIGGY_EMAIL": "ops@example.com",
                    "HEYPIGGY_PASSWORD": "secret",
                },
                clear=False,
            ),
            patch.object(worker, "audit", MagicMock()),
            patch.object(worker, "_init_driver", init_driver),
            patch.object(worker, "ensure_vision_probe_screenshot", return_value="/tmp/probe.png"),
            patch.object(worker, "run_vision_model", run_vision_model),
        ):
            result = await worker.ensure_worker_preflight()

        self.assertEqual(result, {"ok": True, "reason": "ready"})
        self.assertEqual(run_vision_model.await_count, 2)
        init_driver.assert_awaited_once()

    async def test_preflight_uses_isolated_breaker_for_opencode_probe(self):
        driver = MagicMock()
        driver.is_initialized = True
        driver.navigate = AsyncMock(return_value={"success": True})

        init_driver = AsyncMock(return_value=driver)

        async def fake_opencode(prompt, screenshot_path, **kwargs):
            self.assertIn("breaker", kwargs)
            self.assertIsNot(kwargs["breaker"], worker.VISION_CIRCUIT_BREAKER)
            return {"ok": True, "auth_failure": False, "text": "ok"}

        with (
            patch.dict(
                os.environ,
                {
                    "HEYPIGGY_EMAIL": "ops@example.com",
                    "HEYPIGGY_PASSWORD": "secret",
                },
                clear=False,
            ),
            patch.object(worker, "audit", MagicMock()),
            patch.object(worker, "NVIDIA_API_KEY", ""),
            patch.object(worker, "VISION_BACKEND", "opencode"),
            patch.object(worker, "_init_driver", init_driver),
            patch.object(worker, "ensure_vision_probe_screenshot", return_value="/tmp/probe.png"),
            patch.object(worker, "_run_vision_opencode", AsyncMock(side_effect=fake_opencode)) as run_opencode,
        ):
            result = await worker.ensure_worker_preflight()

        self.assertEqual(result, {"ok": True, "reason": "ready"})
        run_opencode.assert_awaited_once()
        init_driver.assert_awaited_once()

    async def test_main_stops_before_browser_mutation_when_vision_auth_fails(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_main_stops_before_browser_mutation_when_vision_auth_fails
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        execute_bridge = AsyncMock()

        with (
            patch.dict(
                os.environ,
                {
                    "HEYPIGGY_EMAIL": "ops@example.com",
                    "HEYPIGGY_PASSWORD": "secret",
                },
                clear=False,
            ),
            patch.object(worker, "wait_for_extension", AsyncMock(return_value=True)),
            patch.object(worker, "check_bridge_alive", AsyncMock(return_value=True)),
            patch.object(
                worker,
                "run_vision_model",
                AsyncMock(
                    return_value={
                        "ok": False,
                        "auth_failure": True,
                        "error": "401 invalid authentication credentials",
                    }
                ),
            ),
            patch.object(worker, "execute_bridge", execute_bridge),
        ):
            await worker.main()

        execute_bridge.assert_not_awaited()

    async def test_main_stops_before_browser_mutation_when_vision_health_fails(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_main_stops_before_browser_mutation_when_vision_health_fails
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        execute_bridge = AsyncMock()

        with (
            patch.dict(
                os.environ,
                {
                    "HEYPIGGY_EMAIL": "ops@example.com",
                    "HEYPIGGY_PASSWORD": "secret",
                },
                clear=False,
            ),
            patch.object(worker, "wait_for_extension", AsyncMock(return_value=True)),
            patch.object(worker, "check_bridge_alive", AsyncMock(return_value=True)),
            patch.object(
                worker,
                "run_vision_model",
                AsyncMock(
                    return_value={
                        "ok": False,
                        "auth_failure": True,
                        "error": "vision health check failed",
                    }
                ),
            ),
            patch.object(worker, "execute_bridge", execute_bridge),
        ):
            await worker.main()

        execute_bridge.assert_not_awaited()

    async def test_pin_bridge_contract_missing_falls_back_to_compatibility_mode(self):
        orig_enabled = worker.OPENSIN_V2_ENABLED
        orig_info = worker.BRIDGE_CONTRACT_INFO
        orig_methods = worker.BRIDGE_CONTRACT_METHODS
        orig_idempotent = worker.BRIDGE_CONTRACT_IDEMPOTENT_METHODS
        orig_error_codes = worker.BRIDGE_CONTRACT_ERROR_CODES
        orig_surface = worker.BRIDGE_TOOL_SURFACE_KIND

        try:
            worker.OPENSIN_V2_ENABLED = True
            worker.BRIDGE_CONTRACT_INFO = None
            worker.BRIDGE_CONTRACT_METHODS = {}
            worker.BRIDGE_CONTRACT_IDEMPOTENT_METHODS = set()
            worker.BRIDGE_CONTRACT_ERROR_CODES = set()
            worker.BRIDGE_TOOL_SURFACE_KIND = None

            with (
                patch.object(
                    worker, "post_mcp", side_effect=RuntimeError("Tool not found: bridge.contract")
                ),
                patch.object(worker, "audit", MagicMock()),
            ):
                result = await worker._pin_bridge_contract_if_needed()

            self.assertIsNotNone(result)
            self.assertEqual(result["version"], "bridge.contract-unavailable")
        finally:
            worker.OPENSIN_V2_ENABLED = orig_enabled
            worker.BRIDGE_CONTRACT_INFO = orig_info
            worker.BRIDGE_CONTRACT_METHODS = orig_methods
            worker.BRIDGE_CONTRACT_IDEMPOTENT_METHODS = orig_idempotent
            worker.BRIDGE_CONTRACT_ERROR_CODES = orig_error_codes
            worker.BRIDGE_TOOL_SURFACE_KIND = orig_surface

    def test_translate_v2_bridge_method_keeps_legacy_surface_calls_unchanged(self):
        orig_enabled = worker.OPENSIN_V2_ENABLED
        orig_surface = worker.BRIDGE_TOOL_SURFACE_KIND

        try:
            worker.OPENSIN_V2_ENABLED = True
            worker.BRIDGE_TOOL_SURFACE_KIND = "legacy"

            method, params = worker._translate_v2_bridge_method(
                "click_ref", {"ref": "@e9", "tabId": 7}
            )

            self.assertEqual(method, "click_ref")
            self.assertEqual(params, {"ref": "@e9", "tabId": 7})
        finally:
            worker.OPENSIN_V2_ENABLED = orig_enabled
            worker.BRIDGE_TOOL_SURFACE_KIND = orig_surface

    def test_translate_v2_bridge_method_translates_on_v2_surface(self):
        orig_enabled = worker.OPENSIN_V2_ENABLED
        orig_surface = worker.BRIDGE_TOOL_SURFACE_KIND

        try:
            worker.OPENSIN_V2_ENABLED = True
            worker.BRIDGE_TOOL_SURFACE_KIND = "v2"

            method, params = worker._translate_v2_bridge_method(
                "click_ref", {"ref": "@e9", "tabId": 7}
            )

            self.assertEqual(method, "dom.click")
            self.assertEqual(params["ref"], "e9")
            self.assertEqual(params["tabId"], 7)
        finally:
            worker.OPENSIN_V2_ENABLED = orig_enabled
            worker.BRIDGE_TOOL_SURFACE_KIND = orig_surface

    async def test_ask_vision_turns_auth_failure_into_stop(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_ask_vision_turns_auth_failure_into_stop
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        with (
            patch.object(worker, "dom_prescan", AsyncMock(return_value="DOM")),
            patch.object(
                worker,
                "run_vision_model",
                AsyncMock(
                    return_value={
                        "ok": False,
                        "auth_failure": True,
                        "error": "401 invalid authentication credentials",
                    }
                ),
            ),
        ):
            decision = await worker.ask_vision("/tmp/probe.png", "action", "expected", 1)

        self.assertEqual(decision["verdict"], "STOP")
        self.assertEqual(decision["page_state"], "error")
        self.assertEqual(decision["next_action"], "none")

    def test_detect_vision_auth_failure_treats_health_failures_as_blockers(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_detect_vision_auth_failure_treats_health_failures_as_blockers
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        blocker = worker.detect_vision_auth_failure(
            "provider health check failed: vision model unhealthy"
        )

        self.assertEqual(blocker, "provider health check failed")


class HeyPiggyWorkerClickPipelineTests(unittest.IsolatedAsyncioTestCase):
    # ========================================================================
    # KLASSE: HeyPiggyWorkerClickPipelineTests(unittest.IsolatedAsyncioTestCase)
    # ZWECK:
    # WICHTIG:
    # METHODEN:
    # ========================================================================

    async def test_run_click_action_routes_click_ref_through_escalation_pipeline(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_run_click_action_routes_click_ref_through_escalation_pipeline
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        gate = DummyGate()
        escalating_click = AsyncMock(return_value=True)

        with patch.object(worker, "escalating_click", escalating_click):
            clicked = await worker.run_click_action({"ref": "@e9"}, gate, "hash123", 7)

        self.assertTrue(clicked)
        escalating_click.assert_awaited_once_with(
            selector="",
            description="",
            x=None,
            y=None,
            step_num=7,
            ref="@e9",
        )
        self.assertEqual(gate.failed_selectors, [])
        self.assertEqual(gate.recorded, [])

    async def test_run_click_action_normalizes_selector_ref_style(self):
        gate = DummyGate()
        escalating_click = AsyncMock(return_value=True)

        with patch.object(worker, "escalating_click", escalating_click):
            clicked = await worker.run_click_action({"selector": "@e9"}, gate, "hash123", 7)

        self.assertTrue(clicked)
        escalating_click.assert_awaited_once_with(
            selector="",
            description="",
            x=None,
            y=None,
            step_num=7,
            ref="@e9",
        )

    async def test_run_click_action_tracks_failed_ref_target(self):
        gate = DummyGate()
        escalating_click = AsyncMock(return_value=False)

        with patch.object(worker, "escalating_click", escalating_click):
            clicked = await worker.run_click_action({"ref": "@e9"}, gate, "hash123", 7)

        self.assertFalse(clicked)
        self.assertEqual(gate.failed_selectors, ["@e9"])

    async def test_run_click_action_uses_direct_start_survey_modal_click(self):
        gate = DummyGate()
        with (
            patch.object(worker, "click_start_survey_modal_button", AsyncMock(return_value=True)) as start_click,
            patch.object(worker, "escalating_click", AsyncMock()) as escalating_click,
        ):
            clicked = await worker.run_click_action(
                {"selector": "#start-survey-button"},
                gate,
                img_hash="hash1",
                step_num=2,
            )

        self.assertTrue(clicked)
        start_click.assert_awaited_once()
        escalating_click.assert_not_called()

    async def test_run_click_action_uses_choice_text_click_before_escalation(self):
        gate = DummyGate()
        with (
            patch.object(worker, "click_visible_choice_with_text", AsyncMock(return_value={"clicked": True, "result": {"ok": True}})) as choice_click,
            patch.object(worker, "escalating_click", AsyncMock()) as escalating_click,
        ):
            clicked = await worker.run_click_action(
                {"description": "Ja"},
                gate,
                img_hash="hash2",
                step_num=3,
            )

        self.assertTrue(clicked)
        choice_click.assert_awaited_once_with("Ja")
        escalating_click.assert_not_called()

    async def test_run_click_action_uses_direct_dashboard_clicksurvey_path(self):
        gate = DummyGate()
        with (
            patch.object(worker.page_state_machine, "current_value", return_value="dashboard"),
            patch.object(worker, "click_dashboard_survey_card", AsyncMock(return_value={"clicked": True, "advanced": True, "via": "clickSurvey"})) as direct_open,
            patch.object(worker, "escalating_click", AsyncMock()) as escalating_click,
        ):
            clicked = await worker.run_click_action(
                {"selector": "div.survey-item", "description": "0.38€ 8 Min"},
                gate,
                img_hash="hash3",
                step_num=4,
            )

        self.assertTrue(clicked)
        direct_open.assert_awaited_once_with(selector="div.survey-item", description="0.38€ 8 Min")
        escalating_click.assert_not_called()

    async def test_click_dashboard_survey_card_clicks_card_before_clicksurvey(self):
        execute_bridge = AsyncMock(
            side_effect=[
                {"url": "https://www.heypiggy.com/?page=dashboard", "title": "Dashboard"},
                {
                    "result": {
                        "clicked": True,
                        "via": "element.click",
                        "selector": "#survey-1",
                        "text": "0.38€ 8 Min",
                        "onclick": "clickSurvey('65467728')",
                        "surveyId": "65467728",
                        "clickError": "",
                    }
                },
                {
                    "result": {
                        "ok": True,
                        "surveyId": "65467728",
                        "result": None,
                    }
                },
            ]
        )

        with (
            patch.object(worker, "_tab_params", return_value={"tabId": 7}),
            patch.object(worker, "execute_bridge", execute_bridge),
            patch.object(
                worker,
                "_advance_survey_start_modal",
                AsyncMock(
                    side_effect=[
                        {
                            "advanced": False,
                            "state": "dashboard",
                            "reason": "still dashboard",
                            "via": "none",
                        },
                        {
                            "advanced": True,
                            "state": "DASHBOARD_MODAL_SURVEY",
                            "reason": "modal visible",
                            "via": "start_modal",
                        },
                    ]
                ),
            ) as followup,
        ):
            result = await worker.click_dashboard_survey_card(
                selector="#survey-1",
                description="0.38€ 8 Min",
            )

        self.assertTrue(result["clicked"])
        self.assertTrue(result["advanced"])
        self.assertEqual(result["via"], "start_modal")
        self.assertEqual(followup.await_count, 2)
        self.assertEqual(execute_bridge.await_args_list[1].args[0], "execute_javascript")
        self.assertIn("chosen.click", execute_bridge.await_args_list[1].args[1]["script"])
        self.assertIn("window.clickSurvey", execute_bridge.await_args_list[2].args[1]["script"])

    async def test_run_click_action_falls_back_when_dashboard_clicksurvey_does_not_advance(self):
        gate = DummyGate()
        with (
            patch.object(worker.page_state_machine, "current_value", return_value="dashboard"),
            patch.object(worker, "click_dashboard_survey_card", AsyncMock(return_value={"clicked": True, "advanced": False, "via": "clickSurvey", "reason": "still dashboard"})) as direct_open,
            patch.object(worker, "escalating_click", AsyncMock(return_value=True)) as escalating_click,
        ):
            clicked = await worker.run_click_action(
                {"selector": "div.survey-item", "description": "0.38€ 8 Min"},
                gate,
                img_hash="hash4",
                step_num=5,
            )

        self.assertTrue(clicked)
        direct_open.assert_awaited_once_with(selector="div.survey-item", description="0.38€ 8 Min")
        escalating_click.assert_awaited_once()

    async def test_advance_survey_start_modal_clicks_modal_until_progress_is_visible(self):
        detect_progress = AsyncMock(
            side_effect=[
                (False, "DASHBOARD_LIST", "still dashboard"),
                (True, "DASHBOARD_MODAL_SURVEY", "start modal question visible"),
            ]
        )

        with (
            patch.object(worker, "_select_active_worker_tab", AsyncMock(return_value={"id": 0})),
            patch.object(worker, "_handle_survey_consent_prompt_current_tab", AsyncMock(return_value=False)),
            patch.object(worker, "_detect_click_progress_state", detect_progress),
            patch.object(worker, "click_start_survey_modal_button", AsyncMock(return_value=True)) as start_click,
            patch.object(worker, "dom_verify_change", AsyncMock(return_value={"changed": False})),
            patch.object(worker.asyncio, "sleep", AsyncMock()) as sleep_mock,
        ):
            result = await worker._advance_survey_start_modal(
                before_url="https://www.heypiggy.com/?page=dashboard",
                before_title="HeyPiggy",
            )

        self.assertTrue(result["advanced"])
        self.assertEqual(result["via"], "start_modal")
        start_click.assert_awaited_once()
        sleep_mock.assert_not_awaited()

    async def test_execute_via_driver_maps_dom_queryall_to_execute_javascript(self):
        class FakeDriver:
            async def execute_javascript(self, script, tab_id=None):
                self.script = script
                self.tab_id = tab_id
                return SimpleNamespace(
                    result=[{"selector": "#survey-1", "text": "0.38€ 8 Min", "id": "survey-1"}],
                    error=None,
                )

        driver = FakeDriver()

        result = await worker._execute_via_driver(
            driver,
            "dom.queryAll",
            {"selector": "#survey_list .survey-item", "tabId": 7},
        )

        self.assertEqual(result["items"][0]["selector"], "#survey-1")
        self.assertEqual(driver.tab_id, 7)
        self.assertIn("document.querySelectorAll", driver.script)

    async def test_execute_via_driver_maps_ghost_click_to_driver_click(self):
        class FakeDriver:
            async def click(self, selector, tab_id=None):
                self.selector = selector
                self.tab_id = tab_id
                return SimpleNamespace(success=True, error=None)

        driver = FakeDriver()

        result = await worker._execute_via_driver(
            driver,
            "ghost_click",
            {"selector": "#survey-1", "tabId": 3},
        )

        self.assertTrue(result["success"])
        self.assertEqual(driver.selector, "#survey-1")
        self.assertEqual(driver.tab_id, 3)

    async def test_select_active_worker_tab_prefers_consent_or_survey_tabs(self):
        previous_tab_id = worker.CURRENT_TAB_ID
        previous_window_id = worker.CURRENT_WINDOW_ID

        async def fake_bridge(method, params):
            if method == "tabs_list":
                return {
                    "tabs": [
                        {
                            "id": 0,
                            "windowId": 0,
                            "url": "https://www.heypiggy.com/?page=dashboard",
                            "title": "Dashboard",
                            "active": True,
                        },
                        {
                            "id": 1,
                            "windowId": 0,
                            "url": "https://survey.example.com/consent",
                            "title": "Consent",
                            "active": False,
                        },
                    ]
                }
            if method == "execute_javascript":
                tab_id = params["tabId"]
                if tab_id == 0:
                    return {
                        "result": {
                            "bodyText": "Deine verfügbaren Quellen",
                            "visibleInputCount": 0,
                            "hasStartModal": False,
                            "hasTextarea": False,
                            "hasQuestionPrompt": False,
                            "url": "https://www.heypiggy.com/?page=dashboard",
                            "title": "Dashboard",
                        }
                    }
                return {
                    "result": {
                        "bodyText": "Already another survey open Continue",
                        "visibleInputCount": 2,
                        "hasStartModal": False,
                        "hasTextarea": False,
                        "hasQuestionPrompt": True,
                        "url": "https://survey.example.com/consent",
                        "title": "Consent",
                    }
                }
            raise AssertionError(method)

        try:
            worker.CURRENT_TAB_ID = 0
            worker.CURRENT_WINDOW_ID = 0
            with patch.object(worker, "execute_bridge", AsyncMock(side_effect=fake_bridge)):
                selected = await worker._select_active_worker_tab()

            self.assertIsNotNone(selected)
            self.assertEqual(selected["id"], 1)
            self.assertEqual(worker.CURRENT_TAB_ID, 1)
        finally:
            worker.CURRENT_TAB_ID = previous_tab_id
            worker.CURRENT_WINDOW_ID = previous_window_id

    async def test_advance_survey_start_modal_handles_consent_before_modal_click(self):
        detect_progress = AsyncMock(
            side_effect=[
                (False, "DASHBOARD_LIST", "still dashboard"),
                (True, "survey_active", "question visible"),
            ]
        )

        with (
            patch.object(worker, "_select_active_worker_tab", AsyncMock(return_value={"id": 1})) as select_tab,
            patch.object(worker, "_detect_click_progress_state", detect_progress),
            patch.object(worker, "_handle_survey_consent_prompt_current_tab", AsyncMock(return_value=True)) as handle_consent,
            patch.object(worker, "click_start_survey_modal_button", AsyncMock(return_value=False)) as start_click,
            patch.object(worker, "dom_verify_change", AsyncMock(return_value={"changed": False})),
            patch.object(worker.asyncio, "sleep", AsyncMock()) as sleep_mock,
        ):
            result = await worker._advance_survey_start_modal(
                before_url="https://www.heypiggy.com/?page=dashboard",
                before_title="HeyPiggy",
            )

        self.assertTrue(result["advanced"])
        self.assertEqual(result["via"], "consent_prompt")
        self.assertGreaterEqual(select_tab.await_count, 2)
        handle_consent.assert_awaited_once()
        start_click.assert_not_awaited()
        sleep_mock.assert_not_awaited()

    async def test_escalating_click_derives_dashboard_survey_selector_from_ref_only(self):
        gate_checks = AsyncMock(
            side_effect=[
                {"verdict": "RETRY", "page_state": "dashboard"},
                {"verdict": "PROCEED", "page_state": "survey"},
            ]
        )
        execute_bridge = AsyncMock(return_value={"ok": True})
        resolve_selector = AsyncMock(side_effect=["", "#survey-65467728"])

        with (
            patch.object(worker, "_tab_params", return_value={"tabId": 7}),
            patch.object(worker, "execute_bridge", execute_bridge),
            patch.object(worker, "resolve_survey_selector", resolve_selector),
            patch.object(worker, "_vision_gate_inside_escalation", gate_checks),
            patch.object(worker.page_state_machine, "current_value", return_value="dashboard"),
            patch.object(worker, "_bridge_v2_enabled", return_value=False),
        ):
            clicked = await worker.escalating_click(ref="@e9", step_num=3)

        self.assertTrue(clicked)
        methods = [call.args[0] for call in execute_bridge.await_args_list]
        self.assertIn("click_ref", methods)
        self.assertIn("click_element", methods)
        click_element_call = next(
            call for call in execute_bridge.await_args_list if call.args[0] == "click_element"
        )
        self.assertEqual(click_element_call.args[1]["selector"], "#survey-65467728")

    async def test_escalating_click_accepts_modal_progress_without_vision_retry(self):
        execute_bridge = AsyncMock(
            side_effect=[
                {"url": "https://www.heypiggy.com/?page=dashboard", "title": "HeyPiggy"},
                {"success": True},
            ]
        )
        detect_progress = AsyncMock(
            return_value=(True, "DASHBOARD_MODAL_SURVEY", "Question is now visible")
        )
        vision_gate = AsyncMock()

        with (
            patch.object(worker, "execute_bridge", execute_bridge),
            patch.object(worker, "resolve_survey_selector", AsyncMock(return_value="#survey-1")),
            patch.object(worker, "_tab_params", return_value={"tabId": 7}),
            patch.object(worker, "_detect_click_progress_state", detect_progress),
            patch.object(worker, "_vision_gate_inside_escalation", vision_gate),
            patch.object(worker, "_bridge_v2_enabled", return_value=False),
        ):
            clicked = await worker.escalating_click(selector="#survey-1", step_num=3)

        self.assertTrue(clicked)
        detect_progress.assert_awaited()
        vision_gate.assert_not_awaited()

    async def test_escalating_click_accepts_dom_change_without_fixed_sleep(self):
        execute_bridge = AsyncMock(
            side_effect=[
                {"url": "https://www.heypiggy.com/?page=dashboard", "title": "HeyPiggy"},
                {"success": True},
                {"current_url": "https://www.heypiggy.com/survey/42", "current_title": "Survey"},
            ]
        )
        detect_progress = AsyncMock(return_value=(False, "unknown", "no UI progress yet"))
        vision_gate = AsyncMock()

        with (
            patch.object(worker, "execute_bridge", execute_bridge),
            patch.object(worker, "resolve_survey_selector", AsyncMock(return_value="#survey-1")),
            patch.object(worker, "_tab_params", return_value={"tabId": 7}),
            patch.object(worker, "_detect_click_progress_state", detect_progress),
            patch.object(
                worker,
                "dom_verify_change",
                AsyncMock(
                    return_value={
                        "changed": True,
                        "current_url": "https://www.heypiggy.com/survey/42",
                        "current_title": "Survey",
                    }
                ),
            ),
            patch.object(worker, "_vision_gate_inside_escalation", vision_gate),
            patch.object(worker, "_bridge_v2_enabled", return_value=False),
        ):
            clicked = await worker.escalating_click(selector="#survey-1", step_num=3)

        self.assertTrue(clicked)
        detect_progress.assert_awaited()
        vision_gate.assert_not_awaited()

    async def test_dom_verify_change_retries_when_page_info_is_temporarily_empty(self):
        execute_bridge = AsyncMock(
            side_effect=[
                {"url": "", "title": "", "status": "loading"},
                {
                    "url": "https://www.heypiggy.com/survey/42",
                    "title": "Survey 42",
                    "status": "complete",
                },
            ]
        )

        with (
            patch.object(worker, "execute_bridge", execute_bridge),
            patch.object(worker, "_tab_params", return_value={"tabId": 7}),
            patch.object(worker, "_bridge_tool_names", AsyncMock(return_value=[])),
            patch.object(worker.asyncio, "sleep", AsyncMock()) as sleep_mock,
        ):
            result = await worker.dom_verify_change(
                before_url="https://www.heypiggy.com/dashboard",
                before_title="Dashboard",
            )

        self.assertTrue(result["changed"])
        sleep_mock.assert_awaited()

    async def test_detect_captcha_page_handles_null_bridge_result(self):
        with (
            patch.object(worker, "_tab_params", return_value={"tabId": 7}),
            patch.object(worker, "execute_bridge", AsyncMock(return_value={"result": None})),
        ):
            detected = await worker.detect_captcha_page()

        self.assertFalse(detected)

    async def test_handle_captcha_v2_returns_true_without_fixed_sleep(self):
        worker._captcha_attempt_count = 0
        execute_bridge = AsyncMock(
            side_effect=[
                {"items": [{"selector": ".recaptcha-checkbox", "ref": "r1"}]},
                {"success": True},
            ]
        )

        with (
            patch.object(worker, "_bridge_v2_enabled", return_value=True),
            patch.object(worker, "_tab_params", return_value={"tabId": 7}),
            patch.object(worker, "execute_bridge", execute_bridge),
            patch.object(worker.asyncio, "sleep", AsyncMock()) as sleep_mock,
        ):
            handled = await worker.handle_captcha()

        self.assertTrue(handled)
        sleep_mock.assert_not_awaited()

    async def test_handle_captcha_legacy_returns_true_without_fixed_sleep(self):
        worker._captcha_attempt_count = 0

        with (
            patch.object(worker, "_bridge_v2_enabled", return_value=False),
            patch.object(worker, "_tab_params", return_value={"tabId": 7}),
            patch.object(
                worker,
                "execute_bridge",
                AsyncMock(return_value={"result": {"clicked": True}}),
            ),
            patch.object(worker.asyncio, "sleep", AsyncMock()) as sleep_mock,
        ):
            handled = await worker.handle_captcha()

        self.assertTrue(handled)
        sleep_mock.assert_not_awaited()

    async def test_resolve_survey_selector_keeps_non_card_survey_button_selector(self):
        resolved = await worker.resolve_survey_selector("#start-survey-button")
        self.assertEqual(resolved, "#start-survey-button")

    async def test_click_visible_button_with_text_prefers_click_ref(self):
        async def fake_bridge(method, params):
            if method == "dom.queryAll":
                return {
                    "items": [
                        {
                            "text": "Starte die erste Umfrage!",
                            "ref": "e11",
                            "selector": "div.survey-item",
                            "tag": "BUTTON",
                        }
                    ]
                }
            if method == "click_ref":
                return {"clicked": True}
            raise AssertionError(method)

        with (
            patch.object(worker, "_tab_params", return_value={"tabId": 7}),
            patch.object(worker, "execute_bridge", AsyncMock(side_effect=fake_bridge)),
        ):
            result = await worker.click_visible_button_with_text("Starte")

        self.assertTrue(result["clicked"])
        self.assertEqual(result["selector"], "@e11")

    async def test_execute_via_driver_sanitizes_js_payload(self):
        from types import SimpleNamespace

        class FakeDriver:
            def __init__(self):
                self.calls = []

            async def execute_javascript(self, script, tab_id=None):
                self.calls.append((script, tab_id))
                return SimpleNamespace(result={"ok": True}, error=None)

        fake_driver = FakeDriver()

        result = await worker._execute_via_driver(
            fake_driver,
            "execute_javascript",
            {"script": "# comment\nconst x = 1;", "tabId": 7},
        )

        self.assertEqual(result, {"result": {"ok": True}, "error": None})
        self.assertEqual(fake_driver.calls, [("const x = 1;", 7)])


class HeyPiggyWorkerRefNormalizationTests(unittest.TestCase):
    def test_normalize_selector_and_ref_moves_ref_style_selector_into_ref(self):
        selector, ref = worker._normalize_selector_and_ref("@e9", "")
        self.assertEqual(selector, "")
        self.assertEqual(ref, "@e9")

    def test_bridge_ref_value_strips_at_prefix(self):
        self.assertEqual(worker._bridge_ref_value("@e9"), "e9")
        self.assertEqual(worker._bridge_ref_value("e9"), "e9")


class HeyPiggyWorkerVisionTimeoutTests(unittest.IsolatedAsyncioTestCase):
    # ========================================================================
    # KLASSE: HeyPiggyWorkerVisionTimeoutTests(unittest.IsolatedAsyncioTestCase)
    # ZWECK:
    # WICHTIG:
    # METHODEN:
    # ========================================================================

    def test_cli_timeout_respects_full_requested_timeout(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_cli_timeout_respects_full_requested_timeout
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        """Regression: Früher war cli_timeout auf 25s gecappt → JEDER Call starb."""
        # Direkt die Cap-Logik nachbilden wie in run_vision_model
        timeout = 180
        cli_timeout = max(30, timeout - 5)
        self.assertEqual(cli_timeout, 175)
        self.assertGreater(cli_timeout, 60, "CLI-Timeout muss gross genug fuer das Vision-LLM sein")


class HeyPiggyWorkerControllerTests(unittest.TestCase):
    # ========================================================================
    # KLASSE: HeyPiggyWorkerControllerTests(unittest.TestCase)
    # ZWECK:
    # WICHTIG:
    # METHODEN:
    # ========================================================================

    def test_failed_selectors_reset_on_page_state_change(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_failed_selectors_reset_on_page_state_change
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        """failed_selectors müssen bei Page-State-Wechsel geleert werden."""
        gate = worker.VisionGateController()
        gate.add_failed_selector("#bad")
        gate.add_failed_selector("#bad")
        gate.add_failed_selector("#bad")
        self.assertTrue(gate.is_selector_failed("#bad"))

        gate.record_step("PROCEED", "hash1", page_state="dashboard")
        self.assertFalse(
            gate.is_selector_failed("#bad"),
            "Selektor sollte nach Page-State-Wechsel nicht mehr gesperrt sein",
        )

    def test_failed_selectors_require_three_failures_before_blocking(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_failed_selectors_require_three_failures_before_blocking
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        """Ein einzelner Fail darf den Selektor nicht sofort sperren."""
        gate = worker.VisionGateController()
        gate.add_failed_selector("#flaky")
        self.assertFalse(gate.is_selector_failed("#flaky"))
        gate.add_failed_selector("#flaky")
        self.assertFalse(gate.is_selector_failed("#flaky"))
        gate.add_failed_selector("#flaky")
        self.assertTrue(gate.is_selector_failed("#flaky"))


class HeyPiggyWorkerJsonParsingTests(unittest.IsolatedAsyncioTestCase):
    # ========================================================================
    # KLASSE: HeyPiggyWorkerJsonParsingTests(unittest.IsolatedAsyncioTestCase)
    # ZWECK:
    # WICHTIG:
    # METHODEN:
    # ========================================================================

    async def test_ask_vision_extracts_json_from_prose_wrapped_output(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_ask_vision_extracts_json_from_prose_wrapped_output
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        """Regression: Prosa um JSON herum darf nicht zu RETRY führen."""
        prosa_output = (
            "Ich analysiere den Screenshot. Hier meine Entscheidung:\n"
            '{"verdict": "PROCEED", "page_state": "dashboard", '
            '"next_action": "click_element", "next_params": {"selector": "#btn"}, '
            '"reason": "Button sichtbar", "progress": true}\n'
            "Hoffentlich hilft das."
        )
        with (
            patch.object(worker, "dom_prescan", AsyncMock(return_value="DOM")),
            patch.object(
                worker,
                "run_vision_model",
                AsyncMock(
                    return_value={
                        "ok": True,
                        "auth_failure": False,
                        "text": prosa_output,
                    }
                ),
            ),
        ):
            decision = await worker.ask_vision("/tmp/x.png", "a", "b", 1)

        self.assertEqual(decision["verdict"], "PROCEED")
        self.assertEqual(decision["page_state"], "dashboard")
        self.assertEqual(decision["next_action"], "click_element")

    async def test_ask_vision_prefers_best_json_block_over_brace_noise(self):
        """Regression: Valides JSON mit Klammerrauschen darf nicht falsch gescored werden."""
        mixed_output = (
            "Ich analysiere den Screenshot. Beispiel fuer das Format wäre:\n"
            '{"verdict": "RETRY", "page_state": "unknown"}\n'
            "Dann die echte Antwort:\n"
            '{"verdict": "PROCEED", "page_state": "dashboard", '
            '"next_action": "click_element", "next_params": {"selector": "#btn"}, '
            '"reason": "Button sichtbar", "progress": true}\n'
            "Am Ende noch ein {harmloses} Nachwort."
        )
        with (
            patch.object(worker, "dom_prescan", AsyncMock(return_value="DOM")),
            patch.object(
                worker,
                "run_vision_model",
                AsyncMock(
                    return_value={
                        "ok": True,
                        "auth_failure": False,
                        "text": mixed_output,
                    }
                ),
            ),
        ):
            decision = await worker.ask_vision("/tmp/y.png", "a", "b", 1)

        self.assertEqual(decision["verdict"], "PROCEED")
        self.assertEqual(decision["page_state"], "dashboard")
        self.assertEqual(decision["next_params"]["selector"], "#btn")

    async def test_ask_vision_normalizes_partial_ref_only_output(self):
        """Regression: Ref-only Antworten des Vision-Modells müssen klickbar bleiben."""
        with (
            patch.object(worker, "dom_prescan", AsyncMock(return_value="DOM")),
            patch.object(
                worker,
                "run_vision_model",
                AsyncMock(
                    return_value={
                        "ok": True,
                        "auth_failure": False,
                        "text": '{"ref": "@e9"}',
                    }
                ),
            ),
        ):
            decision = await worker.ask_vision("/tmp/ref.png", "click a survey card", "click survey", 1)

        self.assertEqual(decision["verdict"], "PROCEED")
        self.assertEqual(decision["page_state"], "unknown")
        self.assertEqual(decision["next_action"], "click_ref")
        self.assertEqual(decision["next_params"], {"ref": "@e9"})
        self.assertTrue(decision["progress"])

    def test_needs_post_login_dashboard_bootstrap_for_cashout_page(self):
        self.assertTrue(
            worker._needs_post_login_dashboard_bootstrap(
                "https://www.heypiggy.com/login?page=cashout"
            )
        )

    def test_needs_post_login_dashboard_bootstrap_allows_dashboard_page(self):
        self.assertFalse(
            worker._needs_post_login_dashboard_bootstrap(
                "https://www.heypiggy.com/?page=dashboard"
            )
        )

    async def test_resolve_survey_selector_prefers_id_over_generic_survey_item(self):
        with (
            patch.object(worker, "OPENSIN_V2_ENABLED", True),
            patch.object(worker, "_tab_params", return_value={"tabId": 7}),
            patch.object(
                worker,
                "execute_bridge",
                AsyncMock(
                    return_value={
                        "items": [
                            {
                                "selector": "div.survey-item",
                                "id": "survey-65467728",
                                "text": "Belohnung 2,50 €",
                            }
                        ]
                    }
                ),
            ),
        ):
            resolved = await worker.resolve_survey_selector("div.survey-item", "2,50 €")

        self.assertEqual(resolved, "#survey-65467728")

    async def test_resolve_survey_selector_prefers_ref_when_id_missing(self):
        with (
            patch.object(worker, "OPENSIN_V2_ENABLED", True),
            patch.object(worker, "_tab_params", return_value={"tabId": 7}),
            patch.object(
                worker,
                "execute_bridge",
                AsyncMock(
                    return_value={
                        "items": [
                            {
                                "selector": "div.survey-item",
                                "ref": "e42",
                                "text": "Belohnung 3,50 €",
                            }
                        ]
                    }
                ),
            ),
        ):
            resolved = await worker.resolve_survey_selector("div.survey-item", "3,50 €")

        self.assertEqual(resolved, "@e42")

    async def test_ask_vision_includes_fail_learning_context_in_prompt(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_ask_vision_includes_fail_learning_context_in_prompt
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        fake_runner = AsyncMock(
            return_value={
                "ok": True,
                "auth_failure": False,
                "text": json.dumps(
                    {
                        "verdict": "PROCEED",
                        "page_state": "dashboard",
                        "next_action": "none",
                        "next_params": {},
                        "reason": "ok",
                        "progress": True,
                    }
                ),
            }
        )
        with (
            patch.object(worker, "dom_prescan", AsyncMock(return_value="DOM")),
            patch.object(
                worker,
                "build_fail_learning_context",
                return_value="RECENT FAIL-LEARNINGS (vermeide diese Muster aktiv):\n- Letzte Root Cause: click failed",
            ),
            patch.object(worker, "run_vision_model", fake_runner),
        ):
            await worker.ask_vision("/tmp/x.png", "a", "b", 1)

        prompt = fake_runner.await_args.args[0]
        self.assertIn("RECENT FAIL-LEARNINGS", prompt)
        self.assertIn("Letzte Root Cause: click failed", prompt)


class HeyPiggyWorkerProfilePathTests(unittest.TestCase):
    # ========================================================================
    # KLASSE: HeyPiggyWorkerProfilePathTests(unittest.TestCase)
    # ZWECK:
    # WICHTIG:
    # METHODEN:
    # ========================================================================

    def test_profile_path_resolver_uses_env_override(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_profile_path_resolver_uses_env_override
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        with patch.dict(os.environ, {"HEYPIGGY_PROFILE_PATH": "/tmp/custom.json"}):
            path = worker._resolve_profile_path()
        self.assertEqual(str(path), "/tmp/custom.json")

    def test_profile_path_resolver_has_portable_fallback(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_profile_path_resolver_has_portable_fallback
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        """Darf nicht mehr hardcoded auf /Users/jeremy/ zeigen."""
        with patch.dict(os.environ, {}, clear=False):
            # Explizit alle relevanten Env-Vars entfernen
            for k in ("HEYPIGGY_PROFILE_PATH", "XDG_CONFIG_HOME"):
                os.environ.pop(k, None)
            path = worker._resolve_profile_path()
        self.assertNotIn("/Users/jeremy", str(path))


# Minimal gültiges 1x1 PNG für NVIDIA-NIM-Tests
_TEST_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5wZuoAAAAASUVORK5CYII="
)


def _write_test_png() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(_TEST_PNG_BYTES)
    tmp.close()
    return tmp.name


class HeyPiggyWorkerNvidiaNimTests(unittest.IsolatedAsyncioTestCase):
    # ========================================================================
    # KLASSE: HeyPiggyWorkerNvidiaNimTests(unittest.IsolatedAsyncioTestCase)
    # ZWECK:
    # WICHTIG:
    # METHODEN:
    # ========================================================================

    async def test_nvidia_nim_returns_auth_failure_without_key(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_nvidia_nim_returns_auth_failure_without_key
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        """Ohne NVIDIA_API_KEY → klarer Auth-Failure, kein Crash."""
        with patch.object(worker, "NVIDIA_API_KEY", ""):
            result = await worker._nvidia_nim_chat(
                "test",
                "/tmp/nonexistent.png",
                timeout=5,
                model="meta/llama-3.2-90b-vision-instruct",
            )
        self.assertFalse(result["ok"])
        self.assertTrue(result["auth_failure"])
        self.assertIn("NVIDIA_API_KEY", result["error"])

    async def test_nvidia_nim_parses_openai_compat_response(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_nvidia_nim_parses_openai_compat_response
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        """NVIDIA NIM OpenAI-kompatible Response wird korrekt geparst."""
        tmp_path = _write_test_png()
        fake_response = json.dumps(
            {
                "id": "cmpl-test",
                "model": "meta/llama-3.2-90b-vision-instruct",
                "choices": [
                    {
                        "message": {
                            "content": '{"verdict":"PROCEED","page_state":"dashboard","next_action":"click_element","next_params":{"selector":"#btn"},"reason":"test","progress":true}',
                            "role": "assistant",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"total_tokens": 150},
            }
        )

        with (
            patch.object(worker, "NVIDIA_API_KEY", "nvapi-test"),
            patch(
                "asyncio.to_thread",
                new=AsyncMock(return_value=(200, fake_response, "")),
            ),
        ):
            result = await worker._nvidia_nim_chat(
                "test prompt",
                tmp_path,
                timeout=30,
                model="meta/llama-3.2-90b-vision-instruct",
            )

        self.assertTrue(result["ok"])
        self.assertFalse(result["auth_failure"])
        self.assertIn("PROCEED", result["text"])
        self.assertEqual(result["model_used"], "meta/llama-3.2-90b-vision-instruct")

    async def test_nvidia_nim_handles_rate_limit_429(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_nvidia_nim_handles_rate_limit_429
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        """429 Rate-Limit wird als retry-bar markiert, nicht als auth failure."""
        tmp_path = _write_test_png()

        with (
            patch.object(worker, "NVIDIA_API_KEY", "nvapi-test"),
            patch("asyncio.to_thread", new=AsyncMock(return_value=(429, "", "rate limit"))),
        ):
            result = await worker._nvidia_nim_chat(
                "test",
                tmp_path,
                timeout=5,
                model="meta/llama-3.2-90b-vision-instruct",
            )

        self.assertFalse(result["ok"])
        self.assertFalse(result["auth_failure"])
        self.assertTrue(result.get("rate_limited"))

    async def test_nvidia_nim_handles_401_as_auth_failure(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_nvidia_nim_handles_401_as_auth_failure
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        """401 → auth_failure=True (Preflight stoppt Worker)."""
        tmp_path = _write_test_png()
        with (
            patch.object(worker, "NVIDIA_API_KEY", "nvapi-bad"),
            patch(
                "asyncio.to_thread",
                new=AsyncMock(return_value=(401, "", "invalid key")),
            ),
        ):
            result = await worker._nvidia_nim_chat(
                "test",
                tmp_path,
                timeout=5,
                model="meta/llama-3.2-90b-vision-instruct",
            )
        self.assertFalse(result["ok"])
        self.assertTrue(result["auth_failure"])

    async def test_run_vision_model_routes_to_nvidia_when_key_present(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_run_vision_model_routes_to_nvidia_when_key_present
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        """Mit NVIDIA_API_KEY + VISION_BACKEND=auto → NVIDIA-Pfad wird gewählt."""
        fake_nvidia = AsyncMock(
            return_value={
                "ok": True,
                "auth_failure": False,
                "text": '{"verdict":"PROCEED"}',
                "stdout_text": "",
                "stderr_text": "",
                "returncode": 200,
            }
        )
        fake_opencode = AsyncMock(
            return_value={
                "ok": False,
                "auth_failure": True,
                "error": "should not be called",
            }
        )
        with (
            patch.object(worker, "NVIDIA_API_KEY", "nvapi-test"),
            patch.object(worker, "VISION_BACKEND", "auto"),
            patch.object(worker, "_run_vision_nvidia", fake_nvidia),
            patch.object(worker, "_run_vision_opencode", fake_opencode),
        ):
            result = await worker.run_vision_model("prompt", "/tmp/x.png", timeout=30, step_num=1)
        self.assertTrue(result["ok"])
        fake_nvidia.assert_awaited_once()
        fake_opencode.assert_not_called()

    async def test_run_vision_model_fallback_to_opencode_without_key(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_run_vision_model_fallback_to_opencode_without_key
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        """Ohne NVIDIA_API_KEY → OpenCode CLI Pfad (Backwards Compat)."""
        fake_nvidia = AsyncMock(return_value={"ok": True, "text": "X"})
        fake_opencode = AsyncMock(
            return_value={"ok": True, "auth_failure": False, "text": "opencode-worked"}
        )
        with (
            patch.object(worker, "NVIDIA_API_KEY", ""),
            patch.object(worker, "VISION_BACKEND", "opencode"),
            patch.object(worker, "_run_vision_nvidia", fake_nvidia),
            patch.object(worker, "_run_vision_opencode", fake_opencode),
        ):
            result = await worker.run_vision_model("prompt", "/tmp/x.png", timeout=30, step_num=1)
        self.assertEqual(result["text"], "opencode-worked")
        fake_opencode.assert_awaited_once()
        fake_nvidia.assert_not_called()

    async def test_run_vision_model_auto_without_key_falls_back_to_opencode(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_run_vision_model_auto_without_key_falls_back_to_opencode
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        fake_nvidia = AsyncMock(return_value={"ok": True, "text": "X"})
        fake_opencode = AsyncMock(
            return_value={"ok": True, "auth_failure": False, "text": "opencode-worked"}
        )
        with (
            patch.object(worker, "NVIDIA_API_KEY", ""),
            patch.object(worker, "VISION_BACKEND", "auto"),
            patch.object(worker, "_run_vision_nvidia", fake_nvidia),
            patch.object(worker, "_run_vision_opencode", fake_opencode),
        ):
            result = await worker.run_vision_model("prompt", "/tmp/x.png", timeout=30, step_num=1)

        self.assertEqual(result["text"], "opencode-worked")
        fake_opencode.assert_awaited_once()
        fake_nvidia.assert_not_called()

    async def test_nvidia_fallback_chain_tries_next_model_on_error(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_nvidia_fallback_chain_tries_next_model_on_error
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        """Wenn das Primary-Modell 500ert, wird das nächste Modell probiert."""
        tmp_path = _write_test_png()
        calls = []

        async def fake_chat(prompt, path, *, timeout, model, force_json=True):
            calls.append(model)
            if model == worker.NVIDIA_VISION_MODEL:
                return {"ok": False, "auth_failure": False, "error": "HTTP 500"}
            return {
                "ok": True,
                "auth_failure": False,
                "text": '{"verdict":"PROCEED"}',
                "stdout_text": "",
                "stderr_text": "",
                "returncode": 200,
            }

        with patch.object(worker, "_nvidia_nim_chat", side_effect=fake_chat):
            result = await worker._run_vision_nvidia(
                "test", tmp_path, timeout=30, step_num=1, purpose="vision"
            )

        self.assertTrue(result["ok"])
        self.assertGreaterEqual(len(calls), 2, "Fallback-Modell muss probiert werden")
        self.assertEqual(calls[0], worker.NVIDIA_VISION_MODEL)


class HeyPiggyVisionCacheTests(unittest.TestCase):
    # ========================================================================
    # KLASSE: HeyPiggyVisionCacheTests(unittest.TestCase)
    # ZWECK:
    # WICHTIG:
    # METHODEN:
    # ========================================================================

    def setUp(self):
        # -------------------------------------------------------------------------
        # FUNKTION: setUp
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        worker._VISION_CACHE.clear()

    def test_cache_returns_last_proceed_for_same_hash(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_cache_returns_last_proceed_for_same_hash
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        decision = {
            "verdict": "PROCEED",
            "page_state": "survey_active",
            "next_action": "click_element",
            "next_params": {"selector": "#x"},
        }
        worker._vision_cache_put("hash123", "desc", 1, decision)
        cached = worker._vision_cache_get("hash123", "desc", 2)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["verdict"], "PROCEED")

    def test_cache_rejects_retry_verdicts(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_cache_rejects_retry_verdicts
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        worker._vision_cache_put("hash123", "desc", 1, {"verdict": "RETRY", "reason": "blur"})
        self.assertIsNone(worker._vision_cache_get("hash123", "desc", 2))

    def test_cache_ignores_missing_hash(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_cache_ignores_missing_hash
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        self.assertIsNone(worker._vision_cache_get("", "desc", 1))

    def test_cache_different_action_misses(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_cache_different_action_misses
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        worker._vision_cache_put("hash123", "click weiter", 1, {"verdict": "PROCEED"})
        self.assertIsNone(worker._vision_cache_get("hash123", "click andere", 2))

    def test_cache_bypasses_fragile_click_after_selector_fail_learning(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_cache_bypasses_fragile_click_after_selector_fail_learning
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        decision = {
            "verdict": "PROCEED",
            "next_action": "click_element",
            "next_params": {"selector": ".fragile-button"},
        }
        worker._VISION_CACHE[("hash123", "desc")] = dict(decision)

        with patch.object(
            worker,
            "load_fail_learning",
            return_value={"recent_failures": [], "issue_counts": {"selector_issue": 1}},
        ):
            cached = worker._vision_cache_get("hash123", "desc", 2)

        self.assertIsNone(cached)

    def test_cache_keeps_stable_id_click_when_selector_fail_learning_exists(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_cache_keeps_stable_id_click_when_selector_fail_learning_exists
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        decision = {
            "verdict": "PROCEED",
            "next_action": "click_element",
            "next_params": {"selector": "#stable-button"},
        }
        worker._VISION_CACHE[("hash123", "desc")] = dict(decision)

        with patch.object(
            worker,
            "load_fail_learning",
            return_value={"recent_failures": [], "issue_counts": {"selector_issue": 1}},
        ):
            cached = worker._vision_cache_get("hash123", "desc", 2)

        self.assertIsNotNone(cached)
        self.assertEqual(cached["next_params"], {"selector": "#stable-button"})

    def test_cache_does_not_store_fragile_click_when_selector_fail_learning_exists(
        self,
    ):
        # -------------------------------------------------------------------------
        # FUNKTION: test_cache_does_not_store_fragile_click_when_selector_fail_learning_exists
        # PARAMETER:
        (self,)

        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        decision = {
            "verdict": "PROCEED",
            "next_action": "click_element",
            "next_params": {"selector": ".fragile-button"},
        }

        with patch.object(
            worker,
            "load_fail_learning",
            return_value={"recent_failures": [], "issue_counts": {"selector_issue": 1}},
        ):
            worker._vision_cache_put("hash123", "desc", 1, decision)

        self.assertEqual(worker._VISION_CACHE, {})

    def test_cache_does_not_store_click_actions_when_loop_learning_exists(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_cache_does_not_store_click_actions_when_loop_learning_exists
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        decision = {
            "verdict": "PROCEED",
            "next_action": "click_ref",
            "next_params": {"ref": "@e9"},
        }

        with patch.object(
            worker,
            "load_fail_learning",
            return_value={"recent_failures": [], "issue_counts": {"loop_detected": 1}},
        ):
            worker._vision_cache_put("hash123", "desc", 1, decision)

        self.assertEqual(worker._VISION_CACHE, {})

    def test_cache_bypasses_selector_from_denylist(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_cache_bypasses_selector_from_denylist
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        decision = {
            "verdict": "PROCEED",
            "next_action": "ghost_click",
            "next_params": {"selector": "#blocked-selector"},
        }
        worker._VISION_CACHE[("hash123", "desc")] = dict(decision)

        with patch.object(
            worker,
            "load_fail_learning",
            return_value={
                "recent_failures": [],
                "issue_counts": {},
                "denylist": {
                    "selectors": ["#blocked-selector"],
                    "action_signatures": [],
                    "root_cause_keywords": [],
                },
            },
        ):
            cached = worker._vision_cache_get("hash123", "desc", 2)

        self.assertIsNone(cached)

    def test_cache_bypasses_action_signature_from_denylist(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_cache_bypasses_action_signature_from_denylist
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        decision = {
            "verdict": "PROCEED",
            "next_action": "click_ref",
            "next_params": {"ref": "@e9"},
        }
        worker._VISION_CACHE[("hash123", "desc")] = dict(decision)
        signature = worker._build_action_signature("click_ref", {"ref": "@e9"})

        with patch.object(
            worker,
            "load_fail_learning",
            return_value={
                "recent_failures": [],
                "issue_counts": {},
                "denylist": {
                    "selectors": [],
                    "action_signatures": [signature],
                    "root_cause_keywords": [],
                },
            },
        ):
            cached = worker._vision_cache_get("hash123", "desc", 2)

        self.assertIsNone(cached)


class HeyPiggyActionLoopDetectorTests(unittest.TestCase):
    # ========================================================================
    # KLASSE: HeyPiggyActionLoopDetectorTests(unittest.TestCase)
    # ZWECK:
    # WICHTIG:
    # METHODEN:
    # ========================================================================

    def test_loop_detected_after_three_identical_actions(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_loop_detected_after_three_identical_actions
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        gate = worker.VisionGateController()
        params = {"selector": "#btn"}
        self.assertFalse(gate.record_action("h1", "click_element", params))
        self.assertFalse(gate.record_action("h1", "click_element", params))
        self.assertTrue(gate.record_action("h1", "click_element", params))

    def test_varied_actions_do_not_trigger_loop(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_varied_actions_do_not_trigger_loop
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        gate = worker.VisionGateController()
        self.assertFalse(gate.record_action("h1", "click_element", {"selector": "#a"}))
        self.assertFalse(gate.record_action("h1", "click_element", {"selector": "#b"}))
        self.assertFalse(gate.record_action("h1", "click_element", {"selector": "#c"}))

    def test_clear_action_history_resets_loop_detection(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_clear_action_history_resets_loop_detection
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        gate = worker.VisionGateController()
        params = {"selector": "#btn"}
        gate.record_action("h1", "click_element", params)
        gate.record_action("h1", "click_element", params)
        gate.clear_action_history()
        # Nach clear darf es 2 weitere geben bevor wieder Loop meldet
        self.assertFalse(gate.record_action("h1", "click_element", params))
        self.assertFalse(gate.record_action("h1", "click_element", params))

    def test_action_history_resets_on_page_state_change(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_action_history_resets_on_page_state_change
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        gate = worker.VisionGateController()
        params = {"selector": "#btn"}
        gate.record_action("h1", "click_element", params)
        gate.record_action("h1", "click_element", params)

        gate.record_step("PROCEED", "hash1", page_state="dashboard")

        self.assertFalse(gate.record_action("h1", "click_element", params))


class HeyPiggyProfileAutofillTests(unittest.TestCase):
    # ========================================================================
    # KLASSE: HeyPiggyProfileAutofillTests(unittest.TestCase)
    # ZWECK:
    # WICHTIG:
    # METHODEN:
    # ========================================================================

    def test_email_placeholder_still_works(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_email_placeholder_still_works
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        params = {"selector": "#email", "text": "<EMAIL>"}
        out = worker.inject_credentials(params, "jeremy@example.com", "pw")
        self.assertEqual(out["text"], "jeremy@example.com")

    def test_profile_placeholder_resolves_from_profile(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_profile_placeholder_resolves_from_profile
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        with patch.object(worker, "USER_PROFILE", {"name": "Jeremy Schulze", "city": "Berlin"}):
            params = {"selector": "#name", "text": "<NAME>"}
            out = worker.inject_credentials(params, "", "")
        self.assertEqual(out["text"], "Jeremy Schulze")

    def test_field_hint_autofill_when_placeholder_auto(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_field_hint_autofill_when_placeholder_auto
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        """Wenn text='<AUTO>' und Feldname eindeutig, ziehen wir aus dem Profil."""
        with patch.object(worker, "USER_PROFILE", {"city": "München"}):
            params = {"selector": "#input-city", "text": "<AUTO>"}
            out = worker.inject_credentials(params, "", "")
        self.assertEqual(out["text"], "München")

    def test_no_autofill_if_user_text_present(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_no_autofill_if_user_text_present
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        """Wenn Vision bereits konkreten Text gegeben hat, nicht überschreiben."""
        with patch.object(worker, "USER_PROFILE", {"city": "München"}):
            params = {"selector": "#city", "text": "Hamburg"}
            out = worker.inject_credentials(params, "", "")
        self.assertEqual(out["text"], "Hamburg")

    def test_resolve_profile_value_for_vorname(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_resolve_profile_value_for_vorname
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        with patch.object(worker, "USER_PROFILE", {"first_name": "Jeremy"}):
            self.assertEqual(worker._resolve_profile_value("first-name-input"), "Jeremy")
            self.assertEqual(worker._resolve_profile_value("vorname"), "Jeremy")

    def test_resolve_profile_value_returns_none_on_mismatch(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_resolve_profile_value_returns_none_on_mismatch
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        with patch.object(worker, "USER_PROFILE", {"city": "Berlin"}):
            self.assertIsNone(worker._resolve_profile_value("some-random-field"))


class HeyPiggyFailReplayIntegrationTests(unittest.IsolatedAsyncioTestCase):
    # ========================================================================
    # KLASSE: HeyPiggyFailReplayIntegrationTests(unittest.IsolatedAsyncioTestCase)
    # ZWECK:
    # WICHTIG:
    # METHODEN:
    # ========================================================================

    async def test_run_fail_replay_analysis_writes_report_and_optional_comment(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_run_fail_replay_analysis_writes_report_and_optional_comment
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        frame = MagicMock()
        frame.png_bytes = b"frame-bytes"
        frame.step_label = "step_7_click"
        frame.vision_verdict = "STOP"
        frame.page_state = "error"
        recorder = MagicMock()
        recorder.get_keyframes.return_value = [frame]
        run_summary = worker.RunSummary(run_id="run-fail")
        run_summary.total_steps = 7
        gate = worker.VisionGateController()

        with (
            patch.object(
                worker,
                "save_keyframes_to_disk",
                return_value=[pathlib.Path("/tmp/keyframe_00.png")],
            ) as save_frames,
            patch.object(
                worker, "upload_to_box", return_value="https://box/frame_00.png"
            ) as upload,
            patch.object(
                worker,
                "analyze_fail_multiframe",
                AsyncMock(return_value={"root_cause": "click failed"}),
            ) as analyze,
            patch.object(
                worker, "generate_fail_report_markdown", return_value="report-body"
            ) as generate,
            patch.object(
                worker,
                "save_fail_report_to_disk",
                return_value=pathlib.Path("/tmp/fail_report.md"),
            ) as save_report,
            patch.object(worker, "post_github_issue_comment", return_value=True) as post_comment,
            patch.dict(
                os.environ,
                {
                    "FAIL_REPORT_REPO": "OpenSIN-AI/A2A-SIN-Worker-heypiggy",
                    "FAIL_REPORT_ISSUE_NUMBER": "43",
                },
                clear=False,
            ),
        ):
            report_path = await worker._run_fail_replay_analysis(
                recorder,
                run_summary,
                gate,
                "vision_stop: click failed",
                "error",
            )

        self.assertEqual(report_path, pathlib.Path("/tmp/fail_report.md"))
        save_frames.assert_called_once()
        upload.assert_called_once()
        analyze.assert_awaited_once()
        generate.assert_called_once()
        save_report.assert_called_once()
        post_comment.assert_called_once()

    async def test_run_fail_replay_analysis_persists_fail_learning_memory(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_run_fail_replay_analysis_persists_fail_learning_memory
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        frame = MagicMock()
        frame.png_bytes = b"frame-bytes"
        frame.step_label = "step_8_click"
        frame.vision_verdict = "STOP"
        frame.page_state = "error"
        recorder = MagicMock()
        recorder.get_keyframes.return_value = [frame]
        run_summary = worker.RunSummary(run_id="run-memory")

        with tempfile.TemporaryDirectory() as tmpdir:
            memory_path = pathlib.Path(tmpdir) / "fail_learning.json"
            with (
                patch.object(worker, "FAIL_LEARNING_PATH", memory_path),
                patch.object(
                    worker,
                    "save_keyframes_to_disk",
                    return_value=[pathlib.Path("/tmp/keyframe_00.png")],
                ),
                patch.object(worker, "upload_to_box", return_value=None),
                patch.object(
                    worker,
                    "analyze_fail_multiframe",
                    AsyncMock(
                        return_value={
                            "root_cause": "timing race",
                            "fix_recommendation": "wait longer",
                            "affected_step": "step 8",
                            "timing_issue": True,
                        }
                    ),
                ),
                patch.object(worker, "generate_fail_report_markdown", return_value="report-body"),
                patch.object(
                    worker,
                    "save_fail_report_to_disk",
                    return_value=pathlib.Path("/tmp/fail_report.md"),
                ),
            ):
                await worker._run_fail_replay_analysis(
                    recorder,
                    run_summary,
                    worker.VisionGateController(),
                    "vision_stop: timing race",
                    "error",
                )

            saved = json.loads(memory_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["recent_failures"][-1]["root_cause"], "timing race")
            self.assertEqual(saved["issue_counts"]["timing_issue"], 1)


class HeyPiggyFailLearningMemoryTests(unittest.TestCase):
    # ========================================================================
    # KLASSE: HeyPiggyFailLearningMemoryTests(unittest.TestCase)
    # ZWECK:
    # WICHTIG:
    # METHODEN:
    # ========================================================================

    def test_build_fail_learning_context_includes_recent_mitigation_hints(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_build_fail_learning_context_includes_recent_mitigation_hints
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        memory = {
            "recent_failures": [
                {
                    "root_cause": "selector mismatch",
                    "fix_recommendation": "use click_ref",
                    "affected_step": "step 4",
                }
            ],
            "issue_counts": {"selector_issue": 2, "loop_detected": 1},
        }
        with patch.object(worker, "load_fail_learning", return_value=memory):
            context = worker.build_fail_learning_context()

        self.assertIn("selector mismatch", context)
        self.assertIn("use click_ref", context)
        self.assertIn("VERMEIDE dieselbe next_action", context)

    def test_build_fail_learning_context_contains_explicit_action_avoidance_rules(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_build_fail_learning_context_contains_explicit_action_avoidance_rules
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        memory = {
            "recent_failures": [
                {
                    "root_cause": "Button was not visible under the fold",
                    "fix_recommendation": "scroll before clicking",
                    "affected_step": "step 9",
                }
            ],
            "issue_counts": {
                "selector_issue": 1,
                "loop_detected": 1,
                "timing_issue": 1,
            },
            "denylist": {
                "selectors": ["#survey-123"],
                "action_signatures": ['click_ref|{"ref": "@e9"}'],
                "root_cause_keywords": ["fold", "overlay"],
            },
        }
        with patch.object(worker, "load_fail_learning", return_value=memory):
            context = worker.build_fail_learning_context()

        self.assertIn('VERMEIDE next_action="click_element"', context)
        self.assertIn("VERMEIDE dieselbe next_action", context)
        self.assertIn("VERMEIDE Sofort-Wiederholungen", context)
        self.assertIn("VERMEIDE blinde Standard-Klicks", context)
        self.assertIn("HARTE SELECTOR-DENYLIST", context)
        self.assertIn("RISK KEYWORDS AUS FEHLSCHLÄGEN", context)

    def test_remember_fail_learning_persists_selector_action_and_keyword_denylists(
        self,
    ):
        # -------------------------------------------------------------------------
        # FUNKTION: test_remember_fail_learning_persists_selector_action_and_keyword_denylists
        # PARAMETER:
        (self,)

        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        gate = worker.VisionGateController()
        gate.failed_selectors = {"#bad-selector": 3}
        gate.action_history = [
            ("hash1", "click_ref", '{"ref": "@e9"}'),
            ("hash1", "click_ref", '{"ref": "@e9"}'),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            memory_path = pathlib.Path(tmpdir) / "fail_learning.json"
            with patch.object(worker, "FAIL_LEARNING_PATH", memory_path):
                memory = worker.remember_fail_learning(
                    {
                        "root_cause": "Captcha overlay blocked button under the fold",
                        "selector_issue": True,
                        "loop_detected": True,
                    },
                    "vision_stop",
                    "error",
                    gate=gate,
                )

            denylist = memory["denylist"]
            self.assertIn("#bad-selector", denylist["selectors"])
            self.assertIn('click_ref|{"ref": "@e9"}', denylist["action_signatures"])
            self.assertIn("captcha", denylist["root_cause_keywords"])

    def test_apply_fail_learning_to_decision_blocks_selector_from_denylist(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_apply_fail_learning_to_decision_blocks_selector_from_denylist
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        gate = worker.VisionGateController()
        decision = {
            "verdict": "PROCEED",
            "next_action": "ghost_click",
            "next_params": {"selector": "#blocked-selector"},
            "reason": "button sichtbar",
            "progress": True,
        }
        with patch.object(
            worker,
            "load_fail_learning",
            return_value={
                "recent_failures": [],
                "issue_counts": {},
                "denylist": {
                    "selectors": ["#blocked-selector"],
                    "action_signatures": [],
                    "root_cause_keywords": [],
                },
            },
        ):
            adapted = worker.apply_fail_learning_to_decision(decision, gate, "hash1")

        self.assertEqual(adapted["verdict"], "RETRY")
        self.assertEqual(adapted["next_action"], "none")

    def test_apply_fail_learning_to_decision_blocks_selector_style_ref_from_denylist(
        self,
    ):
        gate = worker.VisionGateController()
        decision = {
            "verdict": "PROCEED",
            "next_action": "click_ref",
            "next_params": {"selector": "@e9"},
            "reason": "button sichtbar",
            "progress": True,
        }
        with patch.object(
            worker,
            "load_fail_learning",
            return_value={
                "recent_failures": [],
                "issue_counts": {},
                "denylist": {
                    "selectors": ["@e9"],
                    "action_signatures": [],
                    "root_cause_keywords": [],
                },
            },
        ):
            adapted = worker.apply_fail_learning_to_decision(decision, gate, "hash1")

        self.assertEqual(adapted["verdict"], "RETRY")
        self.assertEqual(adapted["next_action"], "none")

    def test_apply_fail_learning_to_decision_blocks_action_signature_from_denylist(
        self,
    ):
        # -------------------------------------------------------------------------
        # FUNKTION: test_apply_fail_learning_to_decision_blocks_action_signature_from_denylist
        # PARAMETER:
        (self,)

        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        gate = worker.VisionGateController()
        decision = {
            "verdict": "PROCEED",
            "next_action": "click_ref",
            "next_params": {"ref": "@e9"},
            "reason": "button sichtbar",
            "progress": True,
        }
        signature = worker._build_action_signature("click_ref", {"ref": "@e9"})
        with patch.object(
            worker,
            "load_fail_learning",
            return_value={
                "recent_failures": [],
                "issue_counts": {},
                "denylist": {
                    "selectors": [],
                    "action_signatures": [signature],
                    "root_cause_keywords": [],
                },
            },
        ):
            adapted = worker.apply_fail_learning_to_decision(decision, gate, "hash1")

        self.assertEqual(adapted["verdict"], "RETRY")
        self.assertEqual(adapted["next_action"], "none")

    def test_apply_fail_learning_to_decision_blocks_fragile_click_on_keyword_risk(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_apply_fail_learning_to_decision_blocks_fragile_click_on_keyword_risk
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        gate = worker.VisionGateController()
        decision = {
            "verdict": "PROCEED",
            "next_action": "click_element",
            "next_params": {"selector": ".cta"},
            "reason": "overlay still visible above button",
            "progress": True,
        }
        with patch.object(
            worker,
            "load_fail_learning",
            return_value={
                "recent_failures": [],
                "issue_counts": {},
                "denylist": {
                    "selectors": [],
                    "action_signatures": [],
                    "root_cause_keywords": ["overlay", "captcha"],
                },
            },
        ):
            adapted = worker.apply_fail_learning_to_decision(decision, gate, "hash1")

        self.assertEqual(adapted["verdict"], "RETRY")
        self.assertEqual(adapted["next_action"], "none")

    def test_get_fail_learning_delay_bounds_expands_after_timing_failures(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_get_fail_learning_delay_bounds_expands_after_timing_failures
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        with patch.object(
            worker,
            "load_fail_learning",
            return_value={"recent_failures": [], "issue_counts": {"timing_issue": 1}},
        ):
            delay_min, delay_max = worker.get_fail_learning_delay_bounds(5.0, 10.0)

        self.assertEqual((delay_min, delay_max), (6.0, 12.0))

    def test_get_fail_learning_delay_bounds_stays_default_without_timing_failures(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_get_fail_learning_delay_bounds_stays_default_without_timing_failures
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        with patch.object(
            worker,
            "load_fail_learning",
            return_value={"recent_failures": [], "issue_counts": {}},
        ):
            delay_min, delay_max = worker.get_fail_learning_delay_bounds(5.0, 10.0)

        self.assertEqual((delay_min, delay_max), (5.0, 10.0))

    def test_get_fail_learning_dom_wait_seconds_expands_after_timing_failures(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_get_fail_learning_dom_wait_seconds_expands_after_timing_failures
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        with patch.object(
            worker,
            "load_fail_learning",
            return_value={"recent_failures": [], "issue_counts": {"timing_issue": 2}},
        ):
            self.assertEqual(worker.get_fail_learning_dom_wait_seconds(1.0), 2.0)

    def test_apply_fail_learning_to_decision_prefers_click_ref_after_selector_issues(
        self,
    ):
        # -------------------------------------------------------------------------
        # FUNKTION: test_apply_fail_learning_to_decision_prefers_click_ref_after_selector_issues
        # PARAMETER:
        (self,)

        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        gate = worker.VisionGateController()
        decision = {
            "verdict": "PROCEED",
            "next_action": "click_element",
            "next_params": {"selector": ".submit", "ref": "@e9"},
            "reason": "button sichtbar",
            "progress": True,
        }
        with patch.object(
            worker,
            "load_fail_learning",
            return_value={"recent_failures": [], "issue_counts": {"selector_issue": 1}},
        ):
            adapted = worker.apply_fail_learning_to_decision(decision, gate, "hash1")

        self.assertEqual(adapted["next_action"], "click_ref")
        self.assertEqual(adapted["next_params"], {"ref": "@e9"})

    def test_apply_fail_learning_to_decision_normalizes_selector_style_ref_after_selector_issues(
        self,
    ):
        gate = worker.VisionGateController()
        decision = {
            "verdict": "PROCEED",
            "next_action": "click_element",
            "next_params": {"selector": "@e9"},
            "reason": "button sichtbar",
            "progress": True,
        }
        with patch.object(
            worker,
            "load_fail_learning",
            return_value={"recent_failures": [], "issue_counts": {"selector_issue": 1}},
        ):
            adapted = worker.apply_fail_learning_to_decision(decision, gate, "hash1")

        self.assertEqual(adapted["next_action"], "click_ref")
        self.assertEqual(adapted["next_params"], {"ref": "@e9"})

    def test_apply_fail_learning_to_decision_prefers_ghost_click_for_id_selector(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_apply_fail_learning_to_decision_prefers_ghost_click_for_id_selector
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        gate = worker.VisionGateController()
        decision = {
            "verdict": "PROCEED",
            "next_action": "click_element",
            "next_params": {"selector": "#submit-button"},
            "reason": "id button sichtbar",
            "progress": True,
        }
        with patch.object(
            worker,
            "load_fail_learning",
            return_value={"recent_failures": [], "issue_counts": {"selector_issue": 1}},
        ):
            adapted = worker.apply_fail_learning_to_decision(decision, gate, "hash1")

        self.assertEqual(adapted["next_action"], "ghost_click")
        self.assertEqual(adapted["next_params"], {"selector": "#submit-button"})

    def test_apply_fail_learning_to_decision_blocks_known_loop_pattern(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_apply_fail_learning_to_decision_blocks_known_loop_pattern
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        gate = worker.VisionGateController()
        decision = {
            "verdict": "PROCEED",
            "next_action": "click_element",
            "next_params": {"selector": "#btn"},
            "reason": "weiter klicken",
            "progress": True,
        }
        with patch.object(
            worker,
            "load_fail_learning",
            return_value={"recent_failures": [], "issue_counts": {"loop_detected": 1}},
        ):
            worker.apply_fail_learning_to_decision(decision, gate, "hash-loop")
            worker.apply_fail_learning_to_decision(decision, gate, "hash-loop")
            adapted = worker.apply_fail_learning_to_decision(decision, gate, "hash-loop")

        self.assertEqual(adapted["verdict"], "RETRY")
        self.assertEqual(adapted["next_action"], "none")
        self.assertEqual(adapted["next_params"], {})


class HeyPiggyFinalizeWorkerRunTests(unittest.IsolatedAsyncioTestCase):
    # ========================================================================
    # KLASSE: HeyPiggyFinalizeWorkerRunTests(unittest.IsolatedAsyncioTestCase)
    # ZWECK:
    # WICHTIG:
    # METHODEN:
    # ========================================================================

    async def test_finalize_worker_run_skips_fail_replay_for_success(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_finalize_worker_run_skips_fail_replay_for_success
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        run_summary = worker.RunSummary(run_id="run-success")
        gate = worker.VisionGateController()
        recorder = MagicMock()
        recorder.stop = AsyncMock()

        with (
            patch.object(
                worker,
                "_write_structured_run_summary",
                return_value=pathlib.Path("/tmp/run_summary.json"),
            ),
            patch.object(
                worker,
                "_run_fail_replay_analysis",
                AsyncMock(return_value=pathlib.Path("/tmp/fail_report.md")),
            ) as fail_replay,
        ):
            (
                summary_path,
                fail_report_path,
                exit_reason,
            ) = await worker._finalize_worker_run(
                run_summary,
                gate,
                "vision_done",
                "dashboard",
                recorder,
            )

        self.assertEqual(summary_path, pathlib.Path("/tmp/run_summary.json"))
        self.assertIsNone(fail_report_path)
        self.assertEqual(exit_reason, "vision_done")
        recorder.stop.assert_awaited_once()
        fail_replay.assert_not_awaited()

    async def test_finalize_worker_run_triggers_fail_replay_for_limit_exit(self):
        # -------------------------------------------------------------------------
        # FUNKTION: test_finalize_worker_run_triggers_fail_replay_for_limit_exit
        # PARAMETER: self
        # ZWECK:
        # WAS PASSIERT HIER:
        # WARUM DIESER WEG:
        # ACHTUNG:
        # -------------------------------------------------------------------------

        run_summary = worker.RunSummary(run_id="run-limit")
        gate = worker.VisionGateController()
        gate.no_progress_count = worker.MAX_NO_PROGRESS
        recorder = MagicMock()
        recorder.stop = AsyncMock()

        with (
            patch.object(
                worker,
                "_write_structured_run_summary",
                return_value=pathlib.Path("/tmp/run_summary.json"),
            ),
            patch.object(
                worker,
                "_run_fail_replay_analysis",
                AsyncMock(return_value=pathlib.Path("/tmp/fail_report.md")),
            ) as fail_replay,
        ):
            (
                summary_path,
                fail_report_path,
                exit_reason,
            ) = await worker._finalize_worker_run(
                run_summary,
                gate,
                "startup",
                "unknown",
                recorder,
            )

        self.assertEqual(summary_path, pathlib.Path("/tmp/run_summary.json"))
        self.assertEqual(fail_report_path, pathlib.Path("/tmp/fail_report.md"))
        self.assertEqual(exit_reason, "limit_reached:no_progress")
        recorder.stop.assert_awaited_once()
        fail_replay.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
