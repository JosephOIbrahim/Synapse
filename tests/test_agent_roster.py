"""Roster invariants for the live agent definitions under ``.claude/agents/``.

Anything with a ``name:`` frontmatter under ``.claude/agents/`` is a live
dispatch target: the Agent tool can invoke it and its ``tools:`` line is
runtime-enforced. Two regressions are silent without this file:

* an unquoted ``: `` inside a frontmatter value makes the YAML unparseable
  and the agent drops out of the registry with no error -- the next
  dispatch falls back to full tools;
* a retired definition creeping back in (or a stripped tool creeping back
  onto a ``tools:`` line) re-registers a dispatch target nobody re-verified.

Pins the harness review of 2026-09-15
(``harness/notes/harness-review-2026-09-15/REPORT.md``): finding G5 --
``CronCreate`` off ``flow-conductor``'s ``tools:`` line; findings R2 / R7 --
the five ``panel-relay-*`` definitions retired to
``harness/retired/agents/panel-relay/``. Acceptance row 1g names this file.

Pure-Python, zero-``hou``, file-system reads only.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"

# 39 definitions before the 2026-09-15 review, minus the five retired
# panel-relay-* definitions (REPORT.md finding R2). Update this number in the
# same commit that adds or retires a definition -- the point of the pin is
# that a roster change is a visible, reviewed change, never a side effect.
EXPECTED_DEFINITIONS = 34

# Stripped from flow-conductor by finding G5: a cron enqueued by a subagent
# lands in the main session and most plausibly fires with the main session's
# tools (unverified in the review), so a tools: line carrying it fences
# nothing. Substring match on purpose -- stricter than a token match.
FORBIDDEN_TOOLS = ("CronCreate",)

# Retired 2026-09-15 (finding R2, part of R7); the text lives on under
# harness/retired/agents/panel-relay/ and must not re-register.
RETIRED_NAME_PREFIXES = ("panel-relay-",)
RETIRED_DIR = AGENTS_DIR / "panel-relay"

_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", re.DOTALL)


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _definition_files() -> list[Path]:
    return sorted(AGENTS_DIR.rglob("*.md"))


def _frontmatter(path: Path) -> dict:
    """Parse the leading ``---`` block the way the registry does --
    ``yaml.safe_load`` on the text between the fences. A parse error here is
    the silent-unregister trap made loud."""
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    assert match, f"{_rel(path)}: no leading --- frontmatter block"
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        pytest.fail(
            f"{_rel(path)}: frontmatter is not valid YAML "
            f"(an unquoted ': ' in a value silently unregisters the agent): {exc}"
        )
    assert isinstance(data, dict), (
        f"{_rel(path)}: frontmatter is {type(data).__name__}, not a mapping"
    )
    return data


def _tools_text(value: object) -> str:
    """``tools:`` is a comma-separated string in this roster; tolerate a YAML
    list too so a future reformat cannot dodge the forbidden-tool check."""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return "" if value is None else str(value)


_FILES = _definition_files()
_IDS = [_rel(p) for p in _FILES]


def test_agents_dir_holds_definitions():
    assert AGENTS_DIR.is_dir(), f"{_rel(AGENTS_DIR)} missing -- the roster has no home"
    assert _FILES, f"no *.md under {_rel(AGENTS_DIR)}"


@pytest.mark.parametrize("path", _FILES, ids=_IDS)
def test_definition_frontmatter_is_well_formed(path: Path):
    data = _frontmatter(path)
    assert "name" in data, f"{_rel(path)}: frontmatter lacks `name`"
    assert isinstance(data["name"], str) and data["name"].strip(), (
        f"{_rel(path)}: `name` is empty or not a string"
    )
    assert "tools" in data, f"{_rel(path)}: frontmatter lacks `tools`"
    assert _tools_text(data["tools"]).strip(), f"{_rel(path)}: `tools` is empty"


@pytest.mark.parametrize("path", _FILES, ids=_IDS)
def test_definition_tools_line_carries_no_forbidden_tool(path: Path):
    tools = _tools_text(_frontmatter(path)["tools"])
    for forbidden in FORBIDDEN_TOOLS:
        assert forbidden not in tools, (
            f"{_rel(path)}: `{forbidden}` is back on the tools: line "
            f"(review 2026-09-15 finding G5)"
        )


@pytest.mark.parametrize("path", _FILES, ids=_IDS)
def test_definition_name_is_not_retired(path: Path):
    name = _frontmatter(path)["name"]
    for prefix in RETIRED_NAME_PREFIXES:
        assert not name.startswith(prefix), (
            f"{_rel(path)}: `{name}` re-registers a retired definition "
            f"(review 2026-09-15 finding R2)"
        )


def test_roster_size_is_pinned():
    assert len(_FILES) == EXPECTED_DEFINITIONS, (
        f"{len(_FILES)} definitions under {_rel(AGENTS_DIR)}, expected "
        f"{EXPECTED_DEFINITIONS}; a roster change must update this pin in the "
        f"same commit. Found: {_IDS}"
    )


def test_roster_names_are_unique():
    names = [_frontmatter(p)["name"] for p in _FILES]
    dupes = sorted({n for n in names if names.count(n) > 1})
    assert not dupes, f"duplicate agent names (the registry keeps one, silently): {dupes}"


def test_retired_panel_relay_dir_is_gone():
    assert RETIRED_DIR.exists() is False, (
        f"{_rel(RETIRED_DIR)} exists again; retired definitions live under "
        f"harness/retired/agents/panel-relay/ (review 2026-09-15 finding R2)"
    )
