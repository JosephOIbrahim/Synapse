"""BP12 item 17: the README receipt runs in the normal suite, and it fails when it should.

harness/notes/readme_check.py resolves the README's diagram styling against the two-orange
palette, checks the current-release pointers against VERSION, and checks the tool count. It sat
stale for several releases because nothing ran it. Each mutation below is applied to the README
text in memory (nothing is written), and each must trip the receipt on its own channel.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_NAME = "_readme_check_under_test"


def _load():
    if _NAME in sys.modules:
        return sys.modules[_NAME]
    spec = importlib.util.spec_from_file_location(_NAME, ROOT / "harness" / "notes" / "readme_check.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_NAME] = mod
    spec.loader.exec_module(mod)
    return mod


rc = _load()
README = (ROOT / "README.md").read_text(encoding="utf-8")
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8-sig").strip()


def _failures(readme: str, version: str = VERSION) -> list[str]:
    return rc.run_checks(readme, version).failures


def _mutated(old: str, new: str, count: int = 1) -> str:
    assert old in README, old
    return README.replace(old, new, count)


def test_the_receipt_passes_on_this_tree():
    assert _failures(README) == []


def test_a_grey_stroke_is_caught():
    fails = _failures(_mutated("#D07020", "#333333"))
    assert any("resolves via class" in f and "stroke" in f for f in fails)


def test_an_off_palette_fill_is_caught():
    fails = _failures(_mutated("fill:#F6B26B", "fill:#333333"))
    assert any("resolves via class" in f for f in fails)


def test_dropping_classdef_default_leaves_nodes_unstyled():
    bare = re.sub(r"^\s*classDef default .*\n", "", README, flags=re.M)
    assert bare != README
    assert any("carry no class" in f for f in _failures(bare))


def test_dropping_linkstyle_is_caught():
    bare = re.sub(r"^\s*linkStyle default .*\n", "", README, flags=re.M)
    assert bare != README
    assert any("linkStyle" in f for f in _failures(bare))


def test_a_release_pointer_at_a_missing_page_is_caught():
    old = f"[What's new](docs/releases/v{VERSION}.md)"
    fails = _failures(_mutated(old, "[What's new](docs/releases/v5.85.9.md)"))
    assert any("do not exist" in f for f in fails)
    assert any("What's new" in f and "points at v5.85.9" in f for f in fails)


def test_a_version_the_page_never_names_is_caught():
    assert any("never names v5.99.0" in f for f in _failures(README, "5.99.0"))


def test_older_release_tags_are_history_not_failures():
    assert "v5.75.2" in README          # the installer tag the page rightly still names
    assert not any("5.75.2" in f for f in _failures(README))


def test_the_negative_controls_are_live(monkeypatch):
    monkeypatch.setattr(rc, "check_block", lambda rd, index, block: 0)
    fails = _failures(README)
    assert sum("NEGATIVE CONTROL FAILED" in f for f in fails) == len(rc.BAD_CONTROLS)
