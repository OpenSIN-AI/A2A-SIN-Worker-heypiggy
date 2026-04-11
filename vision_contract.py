"""Strict schema contract helpers for Vision Gate V2.

This module centralizes the typed contract between the screenshot-based vision
model output and the worker's decision loop.

WHY:
- The previous worker logic accepted loosely formatted JSON and then inferred
  important control-flow fields from ad-hoc string parsing.
- A single contract module makes the prompt, parser, and tests agree on one
  canonical shape.
- The worker can now fail closed with a deterministic RETRY response instead of
  branching on partially parsed free-form text.

CONSEQUENCES:
- All vision responses are normalized into the same `VisionResponse` object.
- Fallback parsing remains tolerant enough for production drift, but the worker
  always consumes the strict typed structure afterwards.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# The verdict enum is intentionally string-backed so JSON payloads from the
# model can be passed through without additional serialization glue.
class VisionVerdict(str, Enum):
    """Canonical decision outcomes for the vision gate."""

    PROCEED = "PROCEED"
    STOP = "STOP"
    RETRY = "RETRY"
    ESCALATE = "ESCALATE"


@dataclass(slots=True)
class BlockerInfo:
    """Structured description of a blocker detected by the vision layer.

    WHY:
    - Blockers need a dedicated shape so the worker can distinguish between a
      captcha, a dismissible modal, an auth gate, or a rate-limit banner.
    - `auto_resolvable` gives the execution loop a deterministic branch instead
      of guessing whether an obstacle should be handled automatically.
    """

    type: Literal["captcha", "modal", "auth", "rate_limit"]
    detail: str
    auto_resolvable: bool


@dataclass(slots=True)
class NextAction:
    """Single follow-up action proposed by the vision layer.

    WHY:
    - The worker should execute one small, explicit action at a time.
    - `target` and `value` stay generic enough to support click, type, scroll,
      wait, and no-op behaviors without re-introducing free-form parsing.
    """

    type: Literal["click", "type", "scroll", "wait", "none"]
    target: str = ""
    value: str = ""


class VisionResponse(BaseModel):
    """Validated response envelope returned to the worker loop.

    NOTE:
    - Pydantic is used for robust field coercion and nested validation.
    - Range checks that need graceful fallback behavior are enforced inside the
      parser before model construction so malformed payloads can degrade into a
      deterministic RETRY response instead of raising out of the loop.
    """

    verdict: VisionVerdict
    confidence: float = Field(..., ge=0.0, le=1.0)
    page_type: str
    blocker: BlockerInfo | None = None
    next_action: NextAction
    dom_hash: str = ""
    reasoning: str = ""


# Action aliases let the parser tolerate legacy outputs from older prompts while
# still normalizing them into the new generic action schema.
_ACTION_ALIAS_MAP = {
    "click": "click",
    "click_element": "click",
    "click_ref": "click",
    "ghost_click": "click",
    "vision_click": "click",
    "click_coordinates": "click",
    "type": "type",
    "type_text": "type",
    "scroll": "scroll",
    "scroll_down": "scroll",
    "scroll_up": "scroll",
    "wait": "wait",
    "none": "none",
    "navigate": "wait",
    "keyboard": "click",
}


def _strip_code_fences(raw_text: str) -> str:
    """Removes optional markdown fences before JSON parsing.

    WHY:
    - The prompt demands JSON-only output, but real model responses can still
      occasionally wrap the payload in triple backticks.
    - Removing the wrapper keeps the parser resilient without relaxing the
      worker's strict typed contract.
    """

    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_first_json_object(text: str) -> str | None:
    """Extracts the first balanced JSON object from a noisy response body."""

    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(text[start:], start=start):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _coerce_bool(value: Any, default: bool = False) -> bool:
    """Coerces mixed boolean-like values into an actual bool."""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _coerce_confidence(value: Any, default: float = 0.0) -> float:
    """Converts confidence to a bounded float.

    WHY:
    - The contract promises a 0.0-1.0 confidence value.
    - Bounding the value here avoids model validation errors and keeps the
      fallback path deterministic.
    """

    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, confidence))


def _normalize_next_action(candidate: Any) -> NextAction:
    """Normalizes new-schema or legacy action shapes into `NextAction`."""

    if isinstance(candidate, NextAction):
        return candidate

    if is_dataclass(candidate):
        candidate = asdict(candidate)

    if isinstance(candidate, dict):
        raw_type = str(candidate.get("type", "none") or "none").strip().lower()
        target = str(candidate.get("target", "") or "")
        value = str(candidate.get("value", "") or "")
    else:
        raw_type = str(candidate or "none").strip().lower()
        target = ""
        value = ""

    normalized_type = _ACTION_ALIAS_MAP.get(raw_type, "none")
    if normalized_type == "click" and not target and isinstance(candidate, dict):
        target = str(
            candidate.get("selector")
            or candidate.get("ref")
            or candidate.get("description")
            or candidate.get("coordinates")
            or ""
        )
    if normalized_type == "type" and not value and isinstance(candidate, dict):
        value = str(candidate.get("text") or candidate.get("value") or "")
        if not target:
            target = str(candidate.get("selector") or "")
    if normalized_type == "scroll" and not value and isinstance(candidate, dict):
        value = str(candidate.get("direction") or candidate.get("value") or "")
    return NextAction(type=normalized_type, target=target, value=value)


def _normalize_blocker(candidate: Any) -> BlockerInfo | None:
    """Normalizes blocker payloads into the strict blocker dataclass."""

    if candidate in (None, "", {}):
        return None
    if isinstance(candidate, BlockerInfo):
        return candidate
    if is_dataclass(candidate):
        candidate = asdict(candidate)
    if not isinstance(candidate, dict):
        return None

    blocker_type = str(candidate.get("type", "") or "").strip().lower()
    if blocker_type not in {"captcha", "modal", "auth", "rate_limit"}:
        return None

    return BlockerInfo(
        type=blocker_type,
        detail=str(candidate.get("detail", "") or ""),
        auto_resolvable=_coerce_bool(candidate.get("auto_resolvable"), default=False),
    )


def _candidate_from_regex(raw_text: str) -> dict[str, Any]:
    """Extracts the most important fields from malformed non-JSON text.

    WHY:
    - Production model outputs occasionally drift when rate-limited or when the
      model partially follows the prompt.
    - Regex extraction salvages enough structure for safe retries without ever
      pretending the payload was fully valid JSON.
    """

    text = raw_text or ""
    verdict_match = re.search(r"\b(PROCEED|STOP|RETRY|ESCALATE)\b", text, re.IGNORECASE)
    confidence_match = re.search(r"confidence\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    page_match = re.search(r"page(?:_state|_type)?\s*[:=]\s*[\"']?([a-z_]+)", text, re.IGNORECASE)
    dom_hash_match = re.search(r"dom_hash\s*[:=]\s*[\"']?([a-f0-9]{6,64})", text, re.IGNORECASE)
    reasoning_match = re.search(
        r"(?:reason|reasoning)\s*[:=]\s*[\"']?(.+?)(?:[\"']?$|\n(?:\w+\s*[:=]))",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    blocker_match = re.search(
        r"blocker(?:_type)?\s*[:=]\s*[\"']?(captcha|modal|auth|rate_limit)",
        text,
        re.IGNORECASE,
    )
    auto_resolvable_match = re.search(
        r"auto_resolvable\s*[:=]\s*(true|false|yes|no|1|0)",
        text,
        re.IGNORECASE,
    )
    blocker_detail_match = re.search(
        r"blocker_detail\s*[:=]\s*[\"']?(.+?)(?:[\"']?$|\n(?:\w+\s*[:=]))",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    action_type_match = re.search(
        r"next_action(?:\.type)?\s*[:=]\s*[\"']?([a-z_]+)",
        text,
        re.IGNORECASE,
    )
    action_target_match = re.search(
        r"target\s*[:=]\s*[\"']?(.+?)(?:[\"']?$|\n(?:\w+\s*[:=]))",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    action_value_match = re.search(
        r"value\s*[:=]\s*[\"']?(.+?)(?:[\"']?$|\n(?:\w+\s*[:=]))",
        text,
        re.IGNORECASE | re.DOTALL,
    )

    candidate: dict[str, Any] = {
        "verdict": (verdict_match.group(1).upper() if verdict_match else "RETRY"),
        "confidence": (
            _coerce_confidence(confidence_match.group(1), default=0.0)
            if confidence_match
            else 0.0
        ),
        "page_type": (page_match.group(1).lower() if page_match else "unknown"),
        "dom_hash": (dom_hash_match.group(1) if dom_hash_match else ""),
        "reasoning": (
            reasoning_match.group(1).strip() if reasoning_match else text.strip()[:300]
        ),
        "next_action": {
            "type": (action_type_match.group(1).lower() if action_type_match else "none"),
            "target": (action_target_match.group(1).strip() if action_target_match else ""),
            "value": (action_value_match.group(1).strip() if action_value_match else ""),
        },
    }

    if blocker_match:
        candidate["blocker"] = {
            "type": blocker_match.group(1).lower(),
            "detail": (
                blocker_detail_match.group(1).strip() if blocker_detail_match else ""
            ),
            "auto_resolvable": _coerce_bool(
                auto_resolvable_match.group(1) if auto_resolvable_match else False,
                default=False,
            ),
        }

    return candidate


def _normalize_candidate(candidate: dict[str, Any], fallback_reasoning: str) -> VisionResponse:
    """Builds a strict `VisionResponse` from a partially trusted dictionary."""

    verdict = str(candidate.get("verdict", "RETRY") or "RETRY").upper()
    if verdict not in VisionVerdict.__members__:
        verdict = VisionVerdict.RETRY.value

    page_type = str(
        candidate.get("page_type")
        or candidate.get("page_state")
        or "unknown"
    ).strip().lower()
    if page_type not in {
        "login",
        "survey_list",
        "survey_question",
        "survey_complete",
        "captcha",
        "unknown",
    }:
        page_type = "unknown"

    reasoning = str(
        candidate.get("reasoning") or candidate.get("reason") or fallback_reasoning
    ).strip()
    blocker = _normalize_blocker(candidate.get("blocker"))

    next_action_source = candidate.get("next_action")
    if next_action_source is None and "next_params" in candidate:
        next_action_source = {
            "type": candidate.get("next_action", "none"),
            **(candidate.get("next_params") or {}),
        }
    if next_action_source is None:
        next_action_source = candidate.get("next_action_type") or "none"

    return VisionResponse(
        verdict=VisionVerdict(verdict),
        confidence=_coerce_confidence(candidate.get("confidence"), default=0.0),
        page_type=page_type,
        blocker=blocker,
        next_action=_normalize_next_action(next_action_source),
        dom_hash=str(candidate.get("dom_hash", "") or ""),
        reasoning=reasoning,
    )


def parse_vision_response(raw_text: str) -> VisionResponse:
    """Parses raw model text into the strict vision response contract.

    Parsing strategy:
    1. Try direct JSON from the raw text.
    2. If that fails, extract the first balanced JSON object from noisy text.
    3. If JSON still fails, salvage core fields with regex extraction.
    4. On total failure, return a safe RETRY response.

    WHY:
    - The worker must never trust unconstrained model text directly.
    - The parser must also never crash the main loop over malformed output.

    CONSEQUENCES:
    - All caller code can operate on one typed object.
    - The failure path is deterministic and fail-closed.
    """

    cleaned = _strip_code_fences(raw_text)
    fallback_reasoning = cleaned[:300] if cleaned else "Vision output missing or unparsable."

    json_candidates = [cleaned]
    extracted = _extract_first_json_object(cleaned)
    if extracted and extracted != cleaned:
        json_candidates.append(extracted)

    for candidate_text in json_candidates:
        if not candidate_text:
            continue
        try:
            candidate = json.loads(candidate_text)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            try:
                return _normalize_candidate(candidate, fallback_reasoning)
            except Exception:
                continue

    try:
        regex_candidate = _candidate_from_regex(cleaned)
        return _normalize_candidate(regex_candidate, fallback_reasoning)
    except Exception:
        return VisionResponse(
            verdict=VisionVerdict.RETRY,
            confidence=0.0,
            page_type="unknown",
            blocker=None,
            next_action=NextAction(type="none", target="", value=""),
            dom_hash="",
            reasoning="Vision output missing or unparsable.",
        )
