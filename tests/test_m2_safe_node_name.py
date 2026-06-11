"""M2-C (pipeline citizen, report §4.3 + §5 M2 item 4): _safe_node_name.

USD-legal-ish asset names arriving from the artist/LLM (hyphens, brackets,
spaces -- 'hero-asset [v2]') made the derived-name createNode sites raise
mid-undo-group. The ad-hoc half-sanitizers (.replace(' ','_').replace('/','_'),
path-tail slicing) missed those characters. One helper now owns the rule:
handler_helpers._safe_node_name -- [A-Za-z0-9_] only, no leading digit,
fallback on empty. Wired at the 11 derivation sites (10 handlers_usd.py +
1 handlers_material.py).

Node-name rules ONLY -- USD prim-name sanitization stays in the D-3 RFC lane
(docs/RFC_agent_usd_ledger.md). The explicit-name front doors (create_node,
cops_create_node) intentionally still pass the artist's chosen name through:
raising there is direct feedback on an explicit request, not a derived crash.
"""

import importlib
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

if "hou" not in sys.modules:
    sys.modules["hou"] = ModuleType("hou")
_h = sys.modules["hou"]
for _attr in ("undos", "node", "text", "ui"):
    if not hasattr(_h, _attr):
        setattr(_h, _attr, MagicMock())
if not hasattr(_h, "frame"):
    _h.frame = MagicMock(return_value=1)
if "hdefereval" not in sys.modules:
    _hd = ModuleType("hdefereval")
    _hd.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    sys.modules["hdefereval"] = _hd

from synapse.server.handler_helpers import _safe_node_name  # noqa: E402
from synapse.server.handlers import SynapseHandler  # noqa: E402
from synapse.server import handlers_usd as husd  # noqa: E402


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw,expected", [
    ("hero-asset", "hero_asset"),            # the report's headline case
    ("hero-asset [v2]", "hero_asset_v2"),     # brackets + space collapse
    ("key.light:rim", "key_light_rim"),       # dots and colons
    ("plain_name", "plain_name"),             # legal names pass through
    ("Aa0_", "Aa0"),                          # trailing underscore trimmed
    ("héro–asset", "h_ro_asset"),             # non-ASCII goes too
])
def test_illegal_characters_become_underscores(raw, expected):
    assert _safe_node_name(raw) == expected


def test_runs_collapse_to_one_underscore():
    assert _safe_node_name("a---b   c") == "a_b_c"


def test_empty_input_uses_fallback():
    assert _safe_node_name("") == "node"
    assert _safe_node_name("///", fallback="prim") == "prim"
    assert _safe_node_name("---", fallback="coll") == "coll"


def test_leading_digit_prefixed():
    assert _safe_node_name("42_shot") == "_42_shot"


def test_non_string_input_coerced():
    assert _safe_node_name(123) == "_123"


# ---------------------------------------------------------------------------
# Wired at the derivation sites (one representative handler-level pin;
# the 11 sites share the helper, the unit tests above carry the rules)
# ---------------------------------------------------------------------------


class _UndoGroup:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_manage_collection_node_name_sanitized(monkeypatch):
    fake_hou = SimpleNamespace(
        undos=SimpleNamespace(group=lambda label: _UndoGroup()),
        OperationFailed=type("OperationFailed", (Exception,), {}),
    )
    monkeypatch.setattr(husd, "hou", fake_hou)
    monkeypatch.setattr(husd, "HOU_AVAILABLE", True)
    mt_live = importlib.import_module("synapse.server.main_thread")
    monkeypatch.setattr(mt_live, "run_on_main", lambda fn, timeout=None: fn())
    monkeypatch.setattr(
        SynapseHandler,
        "_verify_collection_cooked",
        staticmethod(lambda *a, **k: None),
    )

    py_lop = MagicMock()
    py_lop.path.return_value = "/stage/coll_hero"
    parent = MagicMock()
    parent.createNode.return_value = py_lop
    lop = MagicMock()
    lop.parent.return_value = parent
    monkeypatch.setattr(
        SynapseHandler, "_resolve_lop_node", lambda self, p: lop, raising=False
    )

    SynapseHandler()._handle_manage_collection({
        "prim_path": "/World",
        "action": "create",
        "collection_name": "hero-asset [v2]",
        "paths": ["/World/geo"],
    })

    node_name = parent.createNode.call_args[0][1]
    assert node_name == "coll_hero_asset_v2"
