"""JSON-RPC Bridge: playstealth-cli ↔ unmask-cli.

This module provides a Python client for the unmask-cli JSON-RPC server,
and an adapter that playstealth-cli uses to pre-scan survey pages before
interacting with them.

Architecture:
    playstealth-cli (Python) ──JSON-RPC──→ unmask-cli (Node.js/TS)
        │                                        │
        │  scan_survey_page(url)                  │
        │ ─────────────────────────────────────→  │ launch browser
        │                                        │ scan DOM/network
        │ ←───────────────────────────────────── │ return analysis
        │                                        │
        │  Use results to optimize interaction   │
        │  (skip traps, target best reward, etc) │

Usage:
    from heypiggy_preflight import UnmaskClient

    client = UnmaskClient()
    analysis = await client.scan_survey_page("https://www.heypiggy.com/survey/123")
    print(analysis.panel_id)  # "dynata"
    print(analysis.traps)     # [{"type": "attention_check", ...}]
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SurveyAnalysis:
    """Result of a unmask-cli survey page scan."""

    url: str
    panel_id: str = "unknown"
    panel_confidence: float = 0.0
    panel_signals: list[str] = field(default_factory=list)
    amount_eur: float | None = None
    time_minutes: int | None = None
    eur_per_hour: float | None = None
    dq_probability: float = 0.0
    risk_level: str = "low"
    risk_factors: list[str] = field(default_factory=list)
    traps: list[dict[str, Any]] = field(default_factory=list)
    question_types: list[str] = field(default_factory=list)
    raw_json: dict[str, Any] = field(default_factory=dict)

    @property
    def has_attention_check(self) -> bool:
        return any(t.get("type") == "attention_check" for t in self.traps)

    @property
    def has_honeypot(self) -> bool:
        return any(t.get("type") == "honeypot" for t in self.traps)

    @property
    def should_skip(self) -> bool:
        """Should we skip this survey based on risk/reward?"""
        if self.dq_probability > 0.5 and (self.eur_per_hour or 0) < 5:
            return True  # High risk, low reward
        if self.has_honeypot and self.dq_probability > 0.3:
            return True  # Honeypots + moderate risk
        return False


class UnmaskClient:
    """Python client for unmask-cli JSON-RPC API.

    Connects to a running 'unmask serve' process via subprocess (stdio)
    or HTTP (if unmask is running separately).
    """

    def __init__(
        self,
        server_url: str | None = None,
        unmask_bin: str | None = None,
    ):
        self.server_url = server_url or os.environ.get(
            "UNMASK_SERVER_URL", ""
        )
        self.unmask_bin = unmask_bin or os.environ.get(
            "UNMASK_BIN", "unmask"
        )
        self._process: subprocess.Popen | None = None
        self._request_id = 0

    async def _call_jsonrpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Make a JSON-RPC call to unmask-cli.

        Uses subprocess mode by default (spawns 'unmask serve' on stdio).
        Falls back to HTTP if UNMASK_SERVER_URL is set.
        """
        if self.server_url:
            return await self._call_http(method, params)

        return await self._call_subprocess(method, params)

    async def _call_subprocess(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Call unmask via subprocess (stdio JSON-RPC)."""
        self._request_id += 1
        payload = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": self._request_id,
            }
        )

        process = await asyncio.create_subprocess_exec(
            self.unmask_bin,
            "serve",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(payload.encode()),
                timeout=30,
            )
        except asyncio.TimeoutError:
            process.kill()
            raise RuntimeError("unmask serve timed out")

        if process.returncode != 0:
            err = stderr.decode() if stderr else "unknown error"
            raise RuntimeError(f"unmask exited {process.returncode}: {err}")

        try:
            response = json.loads(stdout.decode())
            if "error" in response:
                raise RuntimeError(f"JSON-RPC error: {response['error']}")
            return response.get("result", {})
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON from unmask: {exc}") from exc

    async def _call_http(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Call unmask via HTTP (if server is running separately)."""
        try:
            import httpx
        except ImportError:
            raise RuntimeError("httpx required for HTTP mode. pip install httpx")

        self._request_id += 1
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self.server_url,
                json={
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params,
                    "id": self._request_id,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(f"JSON-RPC error: {data['error']}")
            return data.get("result", {})

    async def scan_survey_page(self, url: str) -> SurveyAnalysis:
        """Pre-scan a survey page before interaction.

        Returns a SurveyAnalysis with panel detection, trap scanning,
        reward estimation, risk assessment, and question classification.
        """
        # If unmask is not available, return empty analysis
        if not await self._is_unmask_available():
            return SurveyAnalysis(url=url)

        try:
            result = await self._call_jsonrpc(
                "survey.scan",
                {"url": url},
            )
            return self._parse_scan_result(url, result)
        except Exception as exc:
            print(f"⚠️  unmask scan failed for {url}: {exc}")
            return SurveyAnalysis(url=url)

    async def scan_survey_page_sync(self, url: str) -> SurveyAnalysis:
        """Synchronous wrapper that falls back to basic heuristics."""
        analysis = await self.scan_survey_page(url)
        if analysis.panel_id == "unknown":
            # Apply basic heuristics from URL only
            analysis = self._basic_url_heuristics(url)
        return analysis

    def _basic_url_heuristics(self, url: str) -> SurveyAnalysis:
        """Basic heuristics when unmask is unavailable."""
        url_lower = url.lower()
        analysis = SurveyAnalysis(url=url)

        panel_map = {
            "dynata": "dynata",
            "cint": "cint",
            "lucid": "lucid",
            "purespectrum": "purespectrum",
            "puresurvey": "purespectrum",
            "sapio": "sapio",
            "qualtrics": "qualtrics",
        }
        for token, panel in panel_map.items():
            if token in url_lower:
                analysis.panel_id = panel
                analysis.panel_confidence = 0.5
                analysis.panel_signals = [f"url:{token}"]
                break

        return analysis

    async def _is_unmask_available(self) -> bool:
        """Check if unmask CLI is available."""
        try:
            process = await asyncio.create_subprocess_exec(
                self.unmask_bin,
                "--version",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await asyncio.wait_for(process.communicate(), timeout=5)
            return process.returncode == 0
        except Exception:
            return False

    def _parse_scan_result(self, url: str, raw: dict[str, Any]) -> SurveyAnalysis:
        """Parse JSON-RPC response into SurveyAnalysis."""
        panel = raw.get("panel", {})
        reward = raw.get("reward", {})
        risk = raw.get("risk", {})
        traps = raw.get("traps", [])
        questions = raw.get("questions", [])
        risk_factors = risk.get("factors", [])

        return SurveyAnalysis(
            url=url,
            panel_id=panel.get("id", "unknown"),
            panel_confidence=panel.get("confidence", 0.0),
            panel_signals=panel.get("signals", []),
            amount_eur=reward.get("amountEur"),
            time_minutes=reward.get("timeMinutes"),
            eur_per_hour=reward.get("eurPerHour"),
            dq_probability=risk.get("dqProbability", 0.0),
            risk_level=risk.get("riskLevel", "low"),
            risk_factors=[str(f) for f in risk_factors],
            traps=traps,
            question_types=[
                str(q.get("type", "unknown")) for q in questions
            ],
            raw_json=raw,
        )
