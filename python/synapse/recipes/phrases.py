"""Literal demo language, not a natural-language planner. Pure Python."""
from __future__ import annotations

import difflib
import re
from typing import Any, Mapping

from .contracts import (
    ActionId, DEMO_PHRASES, RecipeSpec, Refusal, RefusalKind, RunRecipeRequest,
)
from .authority import validate_request


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _pattern(template: str) -> re.Pattern:
    pattern = re.escape(normalize(template))
    for key in ("exposure", "color"):
        pattern = pattern.replace(re.escape("{" + key + "}"), rf"(?P<{key}>\S+)")
    return re.compile(pattern)


def match_phrase(text: str, spec: RecipeSpec, *, request_id: str,
                 instance_id: str | None = None,
                 expected_revision: int | None = None) -> RunRecipeRequest | Refusal:
    """Consume ALL input. Only case and whitespace are normalized.

    Curated ``presentation.named_colors`` maps names to color3 constants.
    ``presentation.demo_slots[action_id]`` supplies typed defaults for phrases
    without placeholders (e.g. bounded render settings). Absent defaults are
    refused by the same slot validator as panel controls; never guessed.
    """
    templates = [(action, phrase, _pattern(phrase))
                 for action, phrases in DEMO_PHRASES.items() for phrase in phrases]
    if not isinstance(text, str):
        return Refusal(RefusalKind.UNKNOWN_ACTION, "demo request must be text",
                       templates[0][1] if templates else "")
    normalized = normalize(text)
    nearest = max(templates, key=lambda item: difflib.SequenceMatcher(
        None, normalized, normalize(item[1])).ratio(), default=None)
    alternative = nearest[1] if nearest else ""
    full = [(action, phrase, pattern.fullmatch(normalized))
            for action, phrase, pattern in templates if pattern.fullmatch(normalized)]
    if len(full) > 1:
        return Refusal(RefusalKind.AMBIGUOUS, f"ambiguous demo request: {text!r}", alternative)
    if not full:
        partial = [(action, phrase, m) for action, phrase, pattern in templates
                   if (m := re.search(r"(?<!\w)" + pattern.pattern + r"(?!\w)", normalized))]
        if len({action for action, _, _ in partial}) > 1:
            return Refusal(RefusalKind.AMBIGUOUS, f"multiple actions in one request: {text!r}", alternative)
        if partial:
            _, phrase, match = partial[0]
            clauses = " ".join(p for p in (normalized[:match.start()].strip(),
                                          normalized[match.end():].strip()) if p)
            return Refusal(RefusalKind.TRAILING_CLAUSE,
                           f"unsupported clause {clauses!r}; entire request refused: {text!r}", phrase)
        return Refusal(RefusalKind.UNKNOWN_ACTION, f"off-list demo request refused: {text!r}", alternative)
    action_id, phrase, match = full[0]
    actions = [action for action in spec.actions if action.action_id == action_id]
    if len(actions) != 1:
        kind = RefusalKind.AMBIGUOUS if actions else RefusalKind.UNKNOWN_ACTION
        return Refusal(kind, "phrase has no unique action in the specification", phrase)
    action = actions[0]
    defaults = spec.presentation.get("demo_slots", {})
    if not isinstance(defaults, Mapping) or not isinstance(defaults.get(action_id.value, {}), Mapping):
        return Refusal(RefusalKind.SLOT_INVALID, "invalid curated demo slot defaults", phrase)
    slots: dict[str, Any] = dict(defaults.get(action_id.value, {}))
    extracted = match.groupdict()
    if "exposure" in extracted:
        try:
            slots["exposure"] = float(extracted["exposure"])
        except (ValueError, OverflowError):
            return Refusal(RefusalKind.SLOT_INVALID, "exposure must be a finite number", phrase)
    if "color" in extracted:
        colors = spec.presentation.get("named_colors", {})
        if not isinstance(colors, Mapping):
            return Refusal(RefusalKind.SLOT_INVALID, "specification has no named color table", phrase)
        named = [(name, value) for name, value in colors.items()
                 if isinstance(name, str) and normalize(name) == extracted["color"]]
        if len(named) > 1:
            return Refusal(RefusalKind.AMBIGUOUS, "named color is ambiguous in the specification", phrase)
        targets = [slot for slot in action.slots if slot.type == "color3"]
        if not named or len(targets) != 1:
            return Refusal(RefusalKind.SLOT_INVALID,
                           f"unsupported named color {extracted['color']!r} or nonunique color binding", phrase)
        slots[targets[0].key] = named[0][1]
    request = RunRecipeRequest(spec.recipe_id, action_id.value, instance_id, slots,
                               expected_revision, request_id)
    checked = validate_request(request, spec)
    if isinstance(checked, Refusal):
        return Refusal(checked.kind, checked.reason, phrase)
    return checked
