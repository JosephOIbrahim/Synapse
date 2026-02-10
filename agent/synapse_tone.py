"""
synapse_tone.py — Coaching language for Synapse communications.

Every message the artist sees should pass the validation test:
"Would this message make an artist having a rough day want to keep going
 or close the application?"

Principles:
1. Never blame — "I couldn't find" not "you gave wrong path"
2. Plain language first — technical details can follow
3. Always offer a next step — every error suggests what to try
4. "We/I" framing — collaborative, not diagnostic
5. Forward momentum — success messages imply "what's next"
"""

import re
from typing import Any


def enrich_error_message(error: str, code: str) -> str:
    """Transform a raw error into coaching language with suggestions."""
    enriched = error

    # Node not found
    if "not found" in error.lower() or "couldn't find" in error.lower():
        path_match = re.search(r"['\"`]?(/[a-zA-Z0-9_/]+)['\"`]?", error)
        if path_match:
            path = path_match.group(1)
            enriched = (
                f"Couldn't find a node at `{path}` — it might have been renamed or "
                f"might not exist yet. I can search the scene to find the right path."
            )
        else:
            enriched = (
                "Something I expected to find wasn't there. Let me inspect the "
                "scene to get re-oriented."
            )

    # Parameter errors
    elif "parameter" in error.lower() or "parm" in error.lower():
        enriched = (
            f"Hit a parameter issue: {error}. H21 USD nodes use encoded parameter names "
            f"(like `xn__inputsintensity_i0a` instead of `intensity`). "
            f"I can inspect the node to find the exact parameter names."
        )

    # Permission / path errors
    elif "permission" in error.lower() or "writable" in error.lower():
        enriched = (
            "Couldn't write to the output path — might be a permissions issue. "
            "I'll try using C:/Users/User/.synapse/ instead."
        )

    # Type errors
    elif "NoneType" in error or "AttributeError" in error:
        enriched = (
            "Something I expected to exist wasn't there yet — likely a node or "
            "parameter that wasn't created in a previous step. Let me check "
            "the scene state and try a different approach."
        )

    # Generic fallback
    elif not any(phrase in enriched for phrase in ["I can", "I'll", "Let me"]):
        enriched = f"{error}. Let me take a different approach."

    return enriched


def format_success_message(description: str, result_data: Any) -> str:
    """Format a success result with forward momentum."""
    if not isinstance(result_data, dict):
        return f"{description} — done."

    verification = result_data.get("verification", {})
    parts = [f"{description} — done."]

    if verification and isinstance(verification, dict):
        all_ok = all(
            v.get("exists", False)
            for v in verification.values()
            if isinstance(v, dict)
        )
        error_count = sum(
            1
            for v in verification.values()
            if isinstance(v, dict) and v.get("errors")
        )
        if all_ok and error_count == 0:
            parts.append("Verified — everything checks out.")
        elif not all_ok:
            missing = [
                k
                for k, v in verification.items()
                if isinstance(v, dict) and not v.get("exists")
            ]
            parts.append(
                f"Heads up: {', '.join(missing)} didn't make it. Let me investigate."
            )

    return " ".join(parts)
