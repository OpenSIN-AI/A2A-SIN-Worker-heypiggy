"""Prompt builder for the strict Vision Gate V2 JSON contract.

WHY:
- The worker must ask the model for one exact machine-readable payload.
- The prompt should stay concise enough that the screenshot+DOM request remains
  fast and reliable under real browser-run conditions.

CONSEQUENCES:
- The caller can expect one strict JSON document.
- The parser can stay simple and fail closed when the model drifts.
"""

from __future__ import annotations


def build_vision_prompt(
    action_desc: str, expected_result: str, dom_snapshot: str
) -> str:
    """Builds the schema-constrained prompt for the screenshot vision call.

    WHY:
    - The previous free-form prompt allowed commentary, markdown fences, and
      tool-specific action drift.
    - A concise explicit contract is more robust in live browser runs than a
      giant pretty-printed schema dump.

    CONSEQUENCES:
    - The model is instructed to emit JSON only.
    - The worker can validate the response deterministically without paying the
      latency tax of a huge schema blob on every screenshot call.
    """
    dom_text = dom_snapshot.strip() if dom_snapshot.strip() else "<no_dom_snapshot>"

    return f"""You are the OpenSIN Vision Gate controller.
Analyze the screenshot together with the DOM snapshot and return exactly one JSON object.
Do not return markdown. Do not wrap the JSON in backticks. Do not include explanations before or after the JSON.
If you are uncertain, return verdict RETRY instead of guessing.

Action description: {action_desc}
Expected result: {expected_result}

DOM snapshot:
{dom_text}

Return JSON with exactly these fields:
{{
  "verdict": "PROCEED|STOP|RETRY|ESCALATE",
  "confidence": 0.0,
  "page_type": "login|survey_list|survey_question|survey_complete|captcha|unknown",
  "blocker": null,
  "next_action": {{
    "type": "click|type|scroll|wait|none",
    "target": "selector:#css | ref:@e12 | text:Visible Label | coords:123,456 | ''",
    "value": "text or direction or ''"
  }},
  "dom_hash": "",
  "reasoning": "short factual reason"
}}

Rules:
- For type actions, prefer ref:@eNN or selector:#css targets when available.
- Use <EMAIL> or <PASSWORD> placeholders instead of secrets.
- blocker.type may only be captcha, modal, auth, or rate_limit.
- blocker.auto_resolvable=true only when the worker can realistically dismiss or wait through it automatically.
- If no blocker exists, return blocker as null.
- If no dom hash is inferable, return an empty string.
"""
