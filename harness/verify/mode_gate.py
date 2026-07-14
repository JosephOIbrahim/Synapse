#!/usr/bin/env python3
"""mode_gate.py — read-only MODE A/B guard for the SYNAPSE → H22 harness.

The single source of truth for MODE selection is `harness/run.ts:62-63`:

    const DROP = join(REPO, "harness/state/drop.json");
    const MODE: "A" | "B" = existsSync(DROP) ? "B" : "A";

MODE is decided purely by the EXISTENCE of `harness/state/drop.json` — there is no
`mode` field. This module mirrors that decision in Python so Phase-0 (MODE A) code can
refuse, loudly and cheaply, to run MODE-B work before the human has dropped the real H22
numbers. The tracked schema lives in `harness/state/drop.json.example`:

    { houdini_build, python, usd, pyside, dropped_at, written_by }

with placeholder values ("22.0.XXX", "3.XX.X", "0.XX.XX", "6.X.X"). A placeholder — any
value carrying an uppercase 'X' — is treated as UNSET: the file existing is necessary but
not sufficient for MODE B; its version fields must also be real.

Guarantees:
  - Pure Python. Zero `hou`, zero `pxr`, zero third-party imports.
  - Read-only. Reads `drop.json` if present; NEVER writes drop.json (or anything else)
    anywhere. No side effects.
"""
from __future__ import annotations

import json
from pathlib import Path

# Default location, relative to the repo root (matches run.ts DROP).
DEFAULT_DROP_PATH = "harness/state/drop.json"

# The four version fields the post-drop queue reads (drop.json.example, gate-0.1 step 1-2).
# dropped_at / written_by are metadata, not gated.
REQUIRED_FIELDS = ("houdini_build", "python", "usd", "pyside")

# Verbatim MODE-A refusal message (asserted by tests/test_mode_gate.py).
MODE_A_MESSAGE = "MODE A holds - drop.json not present. Phase 0 only."


def _is_unset(value) -> bool:
    """A field is unset if it is null, empty, or still a placeholder.

    Placeholders are the '.XXX' / '.XX.' / 'X' tokens from drop.json.example. Any uppercase
    'X' in the string form marks the value as not-yet-filled. Checking for 'X' subsumes the
    'XXX' case. Real version numbers ("22.0.631", "3.12.4") contain no 'X'.
    """
    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    if "X" in text:
        return True
    return False


def current_mode(path: str = DEFAULT_DROP_PATH) -> str:
    """Return 'B' iff `path` exists, else 'A' — mirrors run.ts:62-63.

    Read-only existence check; creates nothing.
    """
    return "B" if Path(path).exists() else "A"


def assert_mode_b(path: str = DEFAULT_DROP_PATH) -> dict:
    """Assert the harness is legitimately in MODE B; return the parsed drop.json.

    Raises RuntimeError when:
      - the file is ABSENT (MODE A still holds), with `MODE_A_MESSAGE`;
      - the file is present but unreadable / not a JSON object;
      - any of REQUIRED_FIELDS is missing, null, empty, or a placeholder ('X'-bearing).

    On success returns the parsed dict. Never writes anything.
    """
    p = Path(path)
    if not p.exists():
        raise RuntimeError(MODE_A_MESSAGE)

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:  # JSONDecodeError is a ValueError subclass
        raise RuntimeError(f"drop.json present but unreadable: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError("drop.json present but is not a JSON object.")

    unset = [field for field in REQUIRED_FIELDS if _is_unset(data.get(field))]
    if unset:
        raise RuntimeError(
            "drop.json present but these fields are unset/placeholder: "
            + ", ".join(unset)
            + ". Fill in the real H22 numbers (drop.json.example schema) before MODE B."
        )

    return data
