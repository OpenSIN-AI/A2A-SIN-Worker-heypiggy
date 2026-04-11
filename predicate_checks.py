"""DOM predicate checks used before and after browser mutations.

WHY:
- Vision alone is not enough to prove that an element is interactable.
- The worker needs a deterministic DOM-side safety check before click/type and a
  deterministic DOM hash comparison afterwards.

CONSEQUENCES:
- Pre-action checks can fail closed when a selector is invisible or occluded.
- Post-action checks can report real DOM progress even when screenshots look
  visually similar between survey steps.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from typing import Any


def _sha256_text(value: str) -> str:
    """Returns the SHA-256 hash of normalized body text."""

    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _bridge_tool_call(bridge_url: str, tool_name: str, arguments: dict[str, Any]) -> Any:
    """Executes one JSON-RPC bridge tool call over HTTP.

    WHY:
    - The worker already talks to the bridge over JSON-RPC.
    - Keeping a tiny local client here avoids importing the full worker module
      and prevents circular dependencies between helper files.
    """

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    request = urllib.request.Request(
        bridge_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read().decode("utf-8"))
    if "error" in body:
        raise RuntimeError(str(body["error"]))
    result = body.get("result", {})

    # Many bridge tools return a content array with a JSON blob wrapped as text.
    # This decoder keeps the helper robust across the bridge response variants we
    # already use in the worker.
    if isinstance(result, dict) and isinstance(result.get("content"), list):
        for entry in result["content"]:
            if isinstance(entry, dict) and isinstance(entry.get("text"), str):
                text = entry["text"].strip()
                if not text:
                    continue
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    continue
    return result


def predicate_pre_check(bridge_url, selector) -> dict:
    """Checks whether a target selector is visible, clickable, and unobscured.

    WHY:
    - Browser automation must not guess that a selector is ready to receive a
      click or text input.
    - The worker also needs the current DOM hash before the mutation so the
      subsequent post-check can prove whether the page changed.

    CONSEQUENCES:
    - Missing selectors fail closed with `ok=False`.
    - Selector-less actions return a skipped result but still include the current
      DOM hash so the caller can continue with a post-check.
    """

    selector_literal = json.dumps(selector or "")
    script = f"""
    (function() {{
        var selector = {selector_literal};
        var bodyText = (document.body && document.body.innerText) || '';
        if (!selector) {{
            return {{
                ok: false,
                skipped: true,
                reason: 'missing_selector',
                visible: false,
                clickable: false,
                not_occluded: false,
                dom_text: bodyText
            }};
        }}
        var el = document.querySelector(selector);
        if (!el) {{
            return {{
                ok: false,
                skipped: false,
                reason: 'selector_not_found',
                visible: false,
                clickable: false,
                not_occluded: false,
                dom_text: bodyText
            }};
        }}

        var rect = el.getBoundingClientRect();
        var style = window.getComputedStyle(el);
        var visible = !!(
            rect.width > 0 &&
            rect.height > 0 &&
            style.display !== 'none' &&
            style.visibility !== 'hidden' &&
            style.opacity !== '0'
        );
        var disabled = !!(el.disabled || el.getAttribute('aria-disabled') === 'true');
        var clickable = visible && !disabled && style.pointerEvents !== 'none';
        var centerX = Math.max(0, Math.floor(rect.left + rect.width / 2));
        var centerY = Math.max(0, Math.floor(rect.top + rect.height / 2));
        var topEl = document.elementFromPoint(centerX, centerY);
        var notOccluded = !!topEl && (topEl === el || el.contains(topEl) || topEl.contains(el));

        return {{
            ok: visible && clickable && notOccluded,
            skipped: false,
            reason: visible && clickable && notOccluded ? 'ok' : 'predicate_failed',
            visible: visible,
            clickable: clickable,
            not_occluded: notOccluded,
            dom_text: bodyText,
            tag_name: el.tagName,
            element_id: el.id || '',
            class_name: (el.className || '').toString().slice(0, 120)
        }};
    }})();
    """

    result = _bridge_tool_call(
        bridge_url,
        "execute_javascript",
        {"script": script},
    )

    if isinstance(result, dict) and "result" in result and isinstance(result["result"], dict):
        result = result["result"]

    if not isinstance(result, dict):
        result = {
            "ok": False,
            "skipped": False,
            "reason": "unexpected_bridge_result",
            "visible": False,
            "clickable": False,
            "not_occluded": False,
            "dom_text": "",
        }

    dom_text = str(result.pop("dom_text", "") or "")
    result["dom_hash"] = _sha256_text(dom_text)
    return result


def predicate_post_check(bridge_url, before_hash: str) -> dict:
    """Calculates the post-action DOM hash and reports whether it changed.

    WHY:
    - Survey pages often keep the same layout across many question steps.
    - Comparing the body text hash is a cheap, deterministic signal for whether
      the action produced actual page-level progress.
    """

    script = "(function() { return { dom_text: (document.body && document.body.innerText) || '' }; })();"
    result = _bridge_tool_call(bridge_url, "execute_javascript", {"script": script})
    if isinstance(result, dict) and "result" in result and isinstance(result["result"], dict):
        result = result["result"]

    dom_text = ""
    if isinstance(result, dict):
        dom_text = str(result.get("dom_text", "") or "")

    new_hash = _sha256_text(dom_text)
    return {"changed": bool(before_hash and before_hash != new_hash), "new_hash": new_hash}
