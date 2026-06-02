"""Capture VEX wrangles written during a session as recall-able memory.

Mile 6 of the VEX-corpus goal. When a wrangle executes successfully via
``synapse_execute_vex``, deposit the snippet into memory as a *session pattern*
-- tagged vex/wrangle/session and keyworded with its @attributes -- so a later
``synapse_recall`` surfaces "patterns you wrote before", not only the static
corpus. This complements the corpus (curated, SHOW-tier) with lived,
session-scoped knowledge.

Pure helpers live here; the handler calls ``capture_vex_pattern()`` guarded so a
capture failure never affects VEX execution. Standalone-friendly (no ``hou``).
"""

from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Optional

from .models import Memory, MemoryType, MemoryTier

_MIN_CHARS = 12
_MAX_KEYWORDS = 12
_CAPTURE_TAG = "vex_session"

_ATTR_RE = re.compile(r"@[A-Za-z_][A-Za-z0-9_]*")
_FUNC_RE = re.compile(r"\b([a-z_][a-z0-9_]*)\s*\(")
# control-flow / type keywords are not useful recall triggers
_FUNC_STOP = {"if", "for", "while", "return", "int", "float", "vector",
              "vector4", "matrix", "string", "set", "foreach", "else"}


def _strip_comments(code: str) -> str:
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    code = re.sub(r"//[^\n]*", "", code)
    return code


def should_capture(vex_code: str) -> bool:
    """Capture only non-trivial wrangles: enough real code, and at least one
    attribute reference or function call."""
    if not vex_code:
        return False
    body = _strip_comments(vex_code).strip()
    if len(body) < _MIN_CHARS:
        return False
    return bool(_ATTR_RE.search(body) or _FUNC_RE.search(body))


def extract_keywords(vex_code: str) -> List[str]:
    """Trigger surface: the @attributes and VEX functions used, order-stable."""
    body = _strip_comments(vex_code)
    seen: set = set()
    kws: List[str] = []
    for m in _ATTR_RE.findall(body):
        if m.lower() not in seen:
            seen.add(m.lower())
            kws.append(m)
    for fn in _FUNC_RE.findall(body):
        if fn in _FUNC_STOP or fn.lower() in seen:
            continue
        seen.add(fn.lower())
        kws.append(fn)
        if len(kws) >= _MAX_KEYWORDS:
            break
    return kws[:_MAX_KEYWORDS]


def content_hash(vex_code: str) -> str:
    return hashlib.sha256(_strip_comments(vex_code).strip().encode("utf-8")).hexdigest()[:12]


def make_vex_memory(vex_code: str, context: Optional[Dict] = None) -> Memory:
    context = context or {}
    run_over = context.get("run_over", "")
    node = context.get("node", "")
    h = content_hash(vex_code)
    first_line = next((ln.strip() for ln in vex_code.strip().splitlines() if ln.strip()), "")
    summary = (f"VEX wrangle [{run_over}]: " if run_over else "VEX wrangle: ") + first_line[:70]
    content = (
        f"Session VEX wrangle (run over {run_over or 'points'}).\n"
        f"```vex\n{vex_code.strip()}\n```"
        + (f"\nNode: {node}" if node else "")
    )
    return Memory(
        content=content,
        memory_type=MemoryType.REFERENCE,
        tier=MemoryTier.SEQUENCE,  # session-scope: persists, but not protected like the corpus
        summary=summary,
        tags=["vex", "wrangle", "session", _CAPTURE_TAG, f"vexhash:{h}"],
        keywords=extract_keywords(vex_code),
        source="user",
    )


def capture_vex_pattern(store, vex_code: str, context: Optional[Dict] = None) -> Optional[str]:
    """Deposit a session wrangle if non-trivial and not already captured.

    Returns the new memory id, or None when skipped (trivial or duplicate).
    Dedup is by content hash and is best-effort -- a missed dedup yields a
    harmless duplicate, never an error.
    """
    if not should_capture(vex_code):
        return None
    h = content_hash(vex_code)
    try:
        from .models import MemoryQuery
        if store.search(MemoryQuery(tags=[f"vexhash:{h}"], limit=1)):
            return None
    except Exception:
        pass  # dedup is best-effort
    return store.add(make_vex_memory(vex_code, context))
