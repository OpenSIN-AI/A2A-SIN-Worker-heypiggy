"""Prompt builder for the strict Vision Gate V2 JSON contract.

WHY:
- The worker must ask the model for one exact machine-readable payload.
- The prompt now embeds the canonical schema so the model sees the contract
  inline instead of inferring fields from prose.

CONSEQUENCES:
- The caller can expect one strict JSON document.
- The parser can stay simple and fail closed when the model drifts.
"""

from __future__ import annotations

import json


def build_vision_prompt(action_desc: str, expected_result: str, dom_snapshot: str) -> str:
    """Builds the schema-constrained prompt for the screenshot vision call.

    WHY:
    - The previous free-form prompt allowed commentary, markdown fences, and
      tool-specific action drift.
    - Embedding the full JSON schema makes the desired contract explicit and
      keeps the output aligned with the parser and tests.

    CONSEQUENCES:
    - The model is instructed to emit JSON only.
    - The worker can validate the response deterministically.
    """

    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "verdict",
            "confidence",
            "page_type",
            "blocker",
            "next_action",
            "dom_hash",
            "reasoning",
        ],
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["PROCEED", "STOP", "RETRY", "ESCALATE"],
            },
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "page_type": {
                "type": "string",
                "enum": [
                    "login",
                    "survey_list",
                    "survey_question",
                    "survey_complete",
                    "captcha",
                    "unknown",
                ],
            },
            "blocker": {
                "type": ["object", "null"],
                "additionalProperties": False,
                "required": ["type", "detail", "auto_resolvable"],
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["captcha", "modal", "auth", "rate_limit"],
                    },
                    "detail": {"type": "string"},
                    "auto_resolvable": {"type": "boolean"},
                },
            },
            "next_action": {
                "type": "object",
                "additionalProperties": False,
                "required": ["type", "target", "value"],
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["click", "type", "scroll", "wait", "none"],
                    },
                    "target": {"type": "string"},
                    "value": {"type": "string"},
                },
            },
            "dom_hash": {"type": "string"},
            "reasoning": {"type": "string"},
        },
    }

    pretty_schema = json.dumps(schema, ensure_ascii=False, indent=2)
    dom_text = dom_snapshot.strip() if dom_snapshot.strip() else "<no_dom_snapshot>"

    return f"""You are the OpenSIN Vision Gate controller.
Analyze the screenshot together with the DOM snapshot and return exactly one JSON object.
Do not return markdown. Do not wrap the JSON in backticks. Do not include explanations before or after the JSON.
If you are uncertain, return verdict RETRY instead of guessing.

Action description: {action_desc}
Expected result: {expected_result}

DOM snapshot:
{dom_text}

Rules for next_action:
- type=click: use target to describe the click target. Prefer selector:#css-selector, ref:@e12, text:Visible Label, or coords:123,456.
- type=type: use target as selector:#css-selector and value as the text to enter. Use <EMAIL> or <PASSWORD> placeholders instead of secrets.
- type=scroll: use value as down or up.
- type=wait: use value as a short reason such as loading or rate_limit.
- type=none: leave target and value as empty strings.

Rules for blockers:
- blocker=null when no blocker is present.
- blocker.type=captcha for captcha or challenge pages.
- blocker.type=modal for consent banners, overlays, cookie banners, or dismissible dialogs.
- blocker.type=auth for login/session barriers.
- blocker.type=rate_limit for cooldown banners or retry-later states.
- auto_resolvable=true only when the worker can realistically dismiss or wait through the blocker automatically.

The DOM hash must reflect the page state you observe. If no hash is visible in the DOM snapshot, return an empty string.
Reasoning must be concise and factual.

Return JSON that matches this exact schema:
{pretty_schema}
"""