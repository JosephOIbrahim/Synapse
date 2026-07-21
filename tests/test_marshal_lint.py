"""Marshal-primitive ban lint — the structural half of the L8 freeze fix.

THE RULE
--------
No SYNAPSE source may call Houdini's *blocking* main-thread marshal directly.
Every marshal goes through ``synapse.server.main_thread.run_on_main``.

WHY, at the vendor level (Houdini 22.0.368,
``houdini/python3.13libs/hdefereval.py``)::

    :43  def executeInMainThreadWithResult(code, *args, **kwargs):
             return _queueDeferred(code, args, kwargs, block=True)
    :49  def _queueDeferred(code, args, kwargs, block, num_waits=0):
             ...
             _queue.append((code, block, num_waits, args, kwargs))
             if block:
    :93          _condition.wait()          # <-- no timeout, NO THREAD CHECK

``_condition`` is notified only by ``_processDeferred()``, which the vendor
docstring states is "called from Houdini's event loop callback" — it runs ON
THE MAIN THREAD. So a main-thread caller enqueues work for itself and then
parks waiting for itself to go idle: a permanent, unrecoverable self-deadlock
that no timeout parameter exists to end. That is the freeze.

A second defect in the same primitive: ``result = _last_result`` reads MODULE
GLOBALS, so two concurrent blocking marshals from different threads can swap
each other's results — silent cross-thread data corruption.

``run_on_main`` (``python/synapse/server/main_thread.py``) is immune by
construction: fast path 2 (``:240``) detects a main-thread caller and invokes
``fn()`` directly, never reaching the blocking primitive; the off-main path
uses the NON-blocking ``executeDeferred`` plus its own ``threading.Event``,
per-call result holder (no global race), timeout, and the C4 zombie-kill flag.

This lint ships the rule as an artifact of the test suite so it runs on every
CI invocation — no CI-config-only enforcement that could be skipped locally.
It is a source lint (regex over de-stringed source) in the same style as
``tests/test_cognitive_boundary.py``.

SECOND RULE — the phantom
-------------------------
``hdefereval.executeInMainThread`` **does not exist** on H22.0.368. The vendor
module defines exactly four public dispatch entry points: ``executeDeferred``,
``executeDeferredAfterWaiting``, ``executeInMainThreadWithResult``, and the
snake_case alias ``execute_in_main_thread_with_result``. Calling the phantom
raises ``AttributeError`` — and where the call sits inside a bare
``except Exception: pass`` the failure is swallowed and the marshalled work
simply never happens. That is worse than a crash: it is a silent no-op. This
lint has NO allowlist for the phantom.

MID-MIGRATION EXPECTATION
-------------------------
This lint encodes the END STATE. While the nine raw call sites are being
migrated it is expected to fail, listing exactly what remains. Do not weaken
it, do not extend the allowlist to make it green, do not mark it xfail. A
failure here is a live inventory of remaining work.
"""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent

#: Source trees under lint. ``tests/`` is deliberately excluded — test modules
#: legitimately install fake ``hdefereval`` stubs (e.g.
#: ``tests/test_cops.py`` planting ``executeInMainThreadWithResult = lambda
#: fn: fn()``), which are simulations of the primitive, not uses of it.
_SOURCE_ROOTS = (
    _REPO_ROOT / "python" / "synapse",
    _REPO_ROOT / "shared",
)

# The blocking marshal, in every spelling the vendor exposes: the camelCase
# function, its snake_case alias (hdefereval.py:45), and the private queue
# primitive with block=True. Matched as an attribute access or a bare call so
# the identifier appearing as a plain word (a dict key, a docstring already
# stripped) does not false-positive.
_BLOCKING_MARSHAL = re.compile(
    r"\b(?:executeInMainThreadWithResult|execute_in_main_thread_with_result)\s*\(",
)
_QUEUE_DEFERRED_BLOCKING = re.compile(r"\b_queueDeferred\s*\(")

# The phantom. Negative lookahead so it does not also match the real
# ``executeInMainThreadWithResult``, which shares this prefix.
_PHANTOM_MARSHAL = re.compile(r"\bexecuteInMainThread(?!WithResult)\w*\s*\(")

#: THE ALLOWLIST IS LINE-SCOPED, NOT FILE-SCOPED.
#:
#: Key is ``(repo-relative POSIX path, anchor)``, where *anchor* is a literal
#: substring that must appear on the offending source line. Only lines matching
#: that anchor are excused; every other line of the file stays under the ban.
#:
#: This shape is load-bearing. The previous file-keyed form skipped the WHOLE
#: file on a match, so one excused call site blinded the lint to every other
#: line in a 1700-line module — the largest ``hou``-marshalling file in the repo
#: was invisible to its own guardrail. A guardrail with a file-wide off switch
#: is not a guardrail.
#:
#: Anchoring on line CONTENT rather than a line NUMBER is deliberate: a raw
#: number goes stale on any edit above it and would fail for reasons unrelated
#: to the ban. The anchor names the code being excused, so it survives movement
#: and dies exactly when that code dies.
#:
#: Staleness is enforced, not hoped for: ``test_allowlists_are_documented_and_real``
#: asserts every entry still matches at least one LIVE hit. An entry covering
#: nothing fails loud instead of silently widening the ban's blind spot — that
#: assertion is the whole point of this structure.
#:
#: Every entry carries a written justification (>= 40 chars, enforced). Adding
#: one is a design decision that needs a reviewer, not a way to silence red.
#:
#: Currently EMPTY. The former ``shared/bridge.py`` entry was deleted once that
#: module's migration landed: its remaining mentions of the primitive are all
#: prose (docstrings and comments explaining the ban), which
#: ``_blank_strings_and_comments`` already removes, so the entry excused zero
#: live call sites while hiding the entire module.
_BLOCKING_ALLOWLIST: dict[tuple[str, str], str] = {}

#: Allowlist for the PHANTOM. Intentionally empty and intended to stay empty:
#: a call to a function that does not exist is never correct. Same line-scoped
#: ``(path, anchor)`` key shape as above.
_PHANTOM_ALLOWLIST: dict[tuple[str, str], str] = {}


def _blank_strings_and_comments(source: str) -> str:
    """Replace string-literal and comment characters with spaces, in place.

    Line and column positions are preserved exactly, so reported line numbers
    match what an editor shows. This is what lets the lint be a plain regex
    (idiomatic to this repo) while still ignoring prose: every module here
    discusses the banned primitive by name in its docstring, and a naive grep
    would flag the documentation that exists to explain the ban.

    On a tokenize error the raw source is returned — failing loud (a possible
    false positive) beats failing open (a missed real call).
    """
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return source

    ignorable = {tokenize.STRING, tokenize.COMMENT}
    # Python 3.12+ tokenizes f-strings as FSTRING_START/MIDDLE/END rather than
    # STRING. Blank the literal-text middles too; the interpolated expressions
    # arrive as ordinary tokens and stay visible to the lint (correct: a call
    # inside an f-string expression is a real call).
    for name in ("FSTRING_MIDDLE",):
        tok_type = getattr(tokenize, name, None)
        if tok_type is not None:
            ignorable.add(tok_type)

    lines = [list(line) for line in source.splitlines(keepends=True)]
    for tok in tokens:
        if tok.type not in ignorable:
            continue
        (start_row, start_col), (end_row, end_col) = tok.start, tok.end
        for row in range(start_row, end_row + 1):
            if not (1 <= row <= len(lines)):
                continue
            line = lines[row - 1]
            lo = start_col if row == start_row else 0
            hi = end_col if row == end_row else len(line)
            for i in range(lo, min(hi, len(line))):
                if line[i] != "\n":
                    line[i] = " "
    return "".join("".join(line) for line in lines)


def _iter_hits(patterns):
    """Yield ``(rel_path, lineno, raw_line)`` for EVERY hit, allowlist ignored.

    Deliberately unfiltered. Both the violation scan and the staleness check
    consume this, so an allowlist entry is validated against the same evidence
    it claims to excuse — the two can never drift apart.

    ``raw_line`` is the ORIGINAL source line, not the de-stringed one, so an
    anchor can be written as it appears in an editor. Matching still happens on
    lines the de-stringed pass identified, so prose mentions never reach here.
    """
    for root in _SOURCE_ROOTS:
        assert root.is_dir(), (
            f"Expected a source root at {root} — did the package get moved or "
            "deleted? Update this lint's _SOURCE_ROOTS."
        )
        for py_file in sorted(root.rglob("*.py")):
            rel = py_file.relative_to(_REPO_ROOT).as_posix()
            raw = py_file.read_text(encoding="utf-8", errors="replace")
            code = _blank_strings_and_comments(raw)
            raw_lines = raw.splitlines()
            linenos = sorted(
                {
                    code[: m.start()].count("\n") + 1
                    for pattern in patterns
                    for m in pattern.finditer(code)
                }
            )
            for lineno in linenos:
                line = raw_lines[lineno - 1] if 1 <= lineno <= len(raw_lines) else ""
                yield rel, lineno, line


def _is_allowed(rel: str, line: str, allowlist: dict[tuple[str, str], str]) -> bool:
    """True when a specific LINE is excused — never a whole file."""
    return any(
        path == rel and anchor in line for path, anchor in allowlist
    )


def _scan(patterns, allowlist: dict[tuple[str, str], str]) -> list[tuple[str, list[int]]]:
    """Return (repo-relative path, 1-indexed line numbers) for non-allowlisted hits."""
    violators: dict[str, list[int]] = {}
    for rel, lineno, line in _iter_hits(patterns):
        if _is_allowed(rel, line, allowlist):
            continue
        violators.setdefault(rel, []).append(lineno)
    return sorted(violators.items())


def _stale_entries(patterns, allowlist: dict[tuple[str, str], str]) -> list[tuple[str, str]]:
    """Allowlist keys that no longer match any live hit.

    A stale entry is worse than a useless one: it is a standing, reviewed-once
    exemption that now covers nothing while still reading like a live carve-out.
    Returning it here makes it a test failure rather than rot.
    """
    live: set[tuple[str, str]] = set()
    for rel, _lineno, line in _iter_hits(patterns):
        for key in allowlist:
            if key[0] == rel and key[1] in line:
                live.add(key)
    return [key for key in allowlist if key not in live]


def test_no_blocking_main_thread_marshal() -> None:
    """No SYNAPSE source calls the blocking marshal outside the allowlist."""
    violators = _scan(
        (_BLOCKING_MARSHAL, _QUEUE_DEFERRED_BLOCKING),
        _BLOCKING_ALLOWLIST,
    )
    assert not violators, (
        "Blocking main-thread marshal found. hdefereval."
        "executeInMainThreadWithResult -> _queueDeferred(block=True) -> "
        "_condition.wait() has NO timeout and NO thread check, so a "
        "main-thread caller parks forever waiting for itself "
        "(hdefereval.py:93, H22.0.368). It also reads _last_result from "
        "module globals, so concurrent marshals can swap results.\n\n"
        "Fix: route through synapse.server.main_thread.run_on_main, and "
        "choose the timeout consciously — a previously-unbounded long "
        "operation (render, viewport capture, flipbook) needs an explicit "
        "generous budget, not the ~10s default, or you convert a hang into a "
        "spurious failure.\n\n"
        "If a migration has not landed yet, this failure is the remaining "
        "inventory. Do NOT add an allowlist entry to silence it.\n"
        "Violations:\n"
        + "\n".join(f"  {path}: lines {lines}" for path, lines in violators)
    )


def test_no_phantom_main_thread_marshal() -> None:
    """``hdefereval.executeInMainThread`` does not exist — never call it."""
    violators = _scan((_PHANTOM_MARSHAL,), _PHANTOM_ALLOWLIST)
    assert not violators, (
        "Phantom marshal found. hdefereval.executeInMainThread does NOT "
        "exist on H22.0.368 — the vendor module defines only "
        "executeDeferred, executeDeferredAfterWaiting, "
        "executeInMainThreadWithResult, and the alias "
        "execute_in_main_thread_with_result. Calling it raises "
        "AttributeError; inside a bare `except Exception: pass` that "
        "AttributeError is swallowed and the marshalled work SILENTLY NEVER "
        "RUNS.\n\n"
        "Fix: use synapse.server.main_thread.run_on_main. If the call is "
        "fire-and-forget with no result needed, hdefereval.executeDeferred "
        "is the real non-blocking primitive.\n"
        "Violations:\n"
        + "\n".join(f"  {path}: lines {lines}" for path, lines in violators)
    )


def test_allowlists_are_documented_and_real() -> None:
    """Every allowlist entry must name an existing file, carry a rationale, and
    STILL MATCH A LIVE HIT.

    The third condition is the one with teeth. File-existence plus a 40-char
    rationale was satisfiable by an entry that excused nothing at all: the
    former ``shared/bridge.py`` entry passed both checks for its whole life
    while its only effect was to hide a 1700-line module from the ban. An
    allowlist that cannot go stale is the entire point of this guardrail, so
    staleness is asserted against the same scan the ban itself runs.
    """
    missing_file: list[str] = []
    undocumented: list[str] = []
    for name, allowlist in (
        ("blocking", _BLOCKING_ALLOWLIST),
        ("phantom", _PHANTOM_ALLOWLIST),
    ):
        for (rel, anchor), why in allowlist.items():
            if not (_REPO_ROOT / rel).is_file():
                missing_file.append(f"{name}: {rel} (anchor {anchor!r})")
            if len(why.strip()) < 40:
                undocumented.append(f"{name}: {rel} (anchor {anchor!r})")

    assert not missing_file, (
        "Allowlist entries point at files that no longer exist — remove them "
        "so the ban is not silently narrower than it reads:\n  "
        + "\n  ".join(missing_file)
    )
    assert not undocumented, (
        "Every allowlist entry needs a written justification explaining why "
        "that site cannot self-deadlock:\n  " + "\n  ".join(undocumented)
    )

    stale = [
        f"blocking: {rel} (anchor {anchor!r})"
        for rel, anchor in _stale_entries(
            (_BLOCKING_MARSHAL, _QUEUE_DEFERRED_BLOCKING), _BLOCKING_ALLOWLIST
        )
    ] + [
        f"phantom: {rel} (anchor {anchor!r})"
        for rel, anchor in _stale_entries((_PHANTOM_MARSHAL,), _PHANTOM_ALLOWLIST)
    ]
    assert not stale, (
        "Allowlist entries that match NO live call site. The excused code is "
        "gone (or the anchor no longer matches its line), so the entry now "
        "grants a standing exemption over nothing while still reading like a "
        "reviewed carve-out. Delete it — do not re-anchor it at a different "
        "call site, which would smuggle in an unreviewed exemption:\n  "
        + "\n  ".join(stale)
    )


def test_allowlist_is_line_scoped_not_file_scoped() -> None:
    """A file-wide skip must be impossible to express.

    Pins the structural fix directly: an allowlist entry excuses ONE matching
    line, and every other hit in the same file still reports. Without this,
    nothing stops the key shape from quietly reverting to a bare path and
    re-opening the file-wide blind spot.
    """
    # Anchors are plain substrings, so the two payload names must not be
    # substrings of one another or the fixture would pass for the wrong reason.
    source = (
        "import hdefereval\n"
        "hdefereval.executeInMainThreadWithResult(alpha)\n"
        "hdefereval.executeInMainThreadWithResult(bravo)\n"
    )
    code = _blank_strings_and_comments(source)
    raw_lines = source.splitlines()
    allowlist = {("fake/mod.py", "(alpha)"): "x" * 40}

    reported = [
        lineno
        for lineno, line in enumerate(raw_lines, start=1)
        if _BLOCKING_MARSHAL.search(code.splitlines()[lineno - 1])
        and not _is_allowed("fake/mod.py", line, allowlist)
    ]
    assert reported == [3], (
        "Line 2 carries the anchor and must be excused; line 3 does not and "
        f"must still report. Got {reported}. If both were excused the "
        "allowlist has gone file-scoped again."
    )
    assert not _is_allowed("other/mod.py", raw_lines[1], allowlist), (
        "The anchor must be scoped to its declared path, not matched globally."
    )
