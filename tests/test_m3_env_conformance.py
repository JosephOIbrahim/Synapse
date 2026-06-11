"""M3-B env-var conformance (studio-operable hardening, 2026-06-11).

THE RULE (DOC-1): every ``SYNAPSE_*`` environment variable read by production
code must have a row in the '### Environment Variables' section of
docs/studio/DEPLOYMENT.md, and every documented row must correspond to a real
read. Both directions fail loud -- adding an env read without a doc row fails
CI, and a stale doc row fails CI.

Mechanism: a mechanical source scan, NOT grep. The scanner recognizes two read
shapes over python/synapse/**/*.py + **/*.pypanel (excluding _vendor) +
mcp_server.py + install.py:

  1. DIRECT -- a quoted ``SYNAPSE_*`` literal adjacent to env-call syntax
     (os.environ.get/[]/getenv/setdefault, hou.getenv). Quoted-literal
     adjacency structurally excludes every known false-positive class:
     SYNAPSE_ENC_V1 magic prefix, SYNAPSE_URL/SYNAPSE_HOST identifiers,
     __SYNAPSE_WS_PORT__ HTML token, doc-filename fragments.
  2. INDIRECT -- a module-level ``NAME = "SYNAPSE_X"`` constant where the SAME
     file also calls environ.get(NAME)/environ[NAME]/getenv(NAME). Catches
     the constant-style reads (bridge_endpoint, worker_policy, show_config,
     tool_inspect_stage).

Doc side: backticked ``SYNAPSE_*`` names in the region from the line
'### Environment Variables' to the next level-2 ('## ') heading of
docs/studio/DEPLOYMENT.md.

Headless, zero hou -- pure file scan plus one memory-module unit test.
Precedents: source-scan + closed-vocabulary + exact-pin-ledger style from
tests/test_m1_truth_contract.py; doc/code conformance from
tests/test_router_internals.py.
"""

import logging
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPLOYMENT_MD = REPO_ROOT / "docs" / "studio" / "DEPLOYMENT.md"

# ---------------------------------------------------------------------------
# Scanner (validated prototype -- found 26 vars including the two a plain
# grep missed via result truncation: SYNAPSE_MONITOR_EVENT_CAP and
# SYNAPSE_TOPS_MAX_PROCS in handlers_tops/_common.py)
# ---------------------------------------------------------------------------

DIRECT_RE = re.compile(
    r"(?:os\.environ\.get\(|os\.environ\[|os\.getenv\("
    r"|os\.environ\.setdefault\(|hou\.getenv\()"
    r"\s*[\"'](SYNAPSE_[A-Z0-9_]+)[\"']"
)

CONST_DEF_RE = re.compile(
    r"^\s*(_?[A-Z][A-Z0-9_]*)\s*=\s*[\"'](SYNAPSE_[A-Z0-9_]+)[\"']\s*$",
    re.MULTILINE,
)

DOC_VAR_RE = re.compile(r"`(SYNAPSE_[A-Z0-9_]+)`")

# Env vars read only by the test suite -- documented in the
# '#### Test-only variables' sub-table, never read by production code.
# Pinned in both directions: test_every_documented_var_is_read subtracts
# this set, and test_test_only_allowlist_is_real asserts each member is
# actually read under tests/.
TEST_ONLY = frozenset({
    "SYNAPSE_INTEGRATION",
    "SYNAPSE_LOAD_TEST",
    "SYNAPSE_INSPECTOR_LIVE_TRANSPORT_MODULE",
})


def _scan_files():
    """Production files in scope for the env scan."""
    pkg = REPO_ROOT / "python" / "synapse"
    files = []
    for pattern in ("*.py", "*.pypanel"):
        for path in sorted(pkg.rglob(pattern)):
            if "_vendor" in path.parts:
                continue
            files.append(path)
    files.append(REPO_ROOT / "mcp_server.py")
    files.append(REPO_ROOT / "install.py")
    return files


def _scan_env_reads(files):
    """Map SYNAPSE_* var name -> sorted list of 'file:line' read sites."""
    found = {}

    def _record(var, path, offset, text):
        line = text.count("\n", 0, offset) + 1
        rel = path.relative_to(REPO_ROOT).as_posix()
        found.setdefault(var, set()).add(f"{rel}:{line}")

    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in DIRECT_RE.finditer(text):
            _record(match.group(1), path, match.start(), text)
        for match in CONST_DEF_RE.finditer(text):
            name, var = match.group(1), match.group(2)
            read_re = (
                r"(?:environ\.get\(|environ\[|getenv\()\s*"
                + re.escape(name) + r"\b"
            )
            if re.search(read_re, text):
                _record(var, path, match.start(), text)
    return {var: sorted(sites) for var, sites in found.items()}


def scanned_env_vars():
    return _scan_env_reads(_scan_files())


def documented_env_vars():
    """Backticked SYNAPSE_* names in the '### Environment Variables' region."""
    text = DEPLOYMENT_MD.read_text(encoding="utf-8")
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "### Environment Variables":
            start = i
            break
    assert start is not None, (
        "docs/studio/DEPLOYMENT.md lost its '### Environment Variables' "
        "heading -- the conformance test's parse anchor."
    )
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r"^## ", lines[i]):
            end = i
            break
    region = "\n".join(lines[start:end])
    return frozenset(DOC_VAR_RE.findall(region))


# ---------------------------------------------------------------------------
# Conformance tests
# ---------------------------------------------------------------------------

def test_every_source_env_read_is_documented():
    """DOC-1 forward direction: a new env read without a doc row fails CI."""
    scanned = scanned_env_vars()
    documented = documented_env_vars()
    missing = {
        var: sites for var, sites in scanned.items() if var not in documented
    }
    assert not missing, (
        "Env vars read by production code but missing from the "
        "'### Environment Variables' table in docs/studio/DEPLOYMENT.md "
        "(add a backticked row for each):\n"
        + "\n".join(
            f"  {var}: {', '.join(sites)}" for var, sites in sorted(missing.items())
        )
    )


def test_every_documented_var_is_read():
    """DOC-1 reverse direction: stale doc rows fail loud."""
    scanned = frozenset(scanned_env_vars())
    documented = documented_env_vars()
    stale = documented - scanned - TEST_ONLY
    assert not stale, (
        "Vars documented in docs/studio/DEPLOYMENT.md but read nowhere in "
        "production code (remove the row, or add to TEST_ONLY if a test "
        f"reads it): {sorted(stale)}"
    )


def test_test_only_allowlist_is_real():
    """The TEST_ONLY allowlist itself cannot go stale: every member must
    actually be read somewhere under tests/."""
    read_in_tests = set()
    for path in sorted((REPO_ROOT / "tests").rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in DIRECT_RE.finditer(text):
            read_in_tests.add(match.group(1))
    unread = TEST_ONLY - read_in_tests
    assert not unread, (
        "TEST_ONLY allowlist entries no longer read by any test "
        f"(remove them from the allowlist AND the doc sub-table): {sorted(unread)}"
    )


def test_scanner_self_check():
    """Guard against the scanner silently going blind (the failure mode that
    nearly dropped handlers_tops/_common.py from the original enumeration)."""
    scanned = scanned_env_vars()
    pins = {
        # Indirect-constant reads (CONST_DEF_RE leg must stay alive):
        "SYNAPSE_SHOW_CONFIG",
        "SYNAPSE_WORKER_TOOL_MODE",
        "SYNAPSE_BRIDGE_FILE",
        # Proves *.pypanel globbing:
        "SYNAPSE_ROOT",
        # The pair a truncated grep missed -- mechanical scan must see them:
        "SYNAPSE_MONITOR_EVENT_CAP",
        "SYNAPSE_TOPS_MAX_PROCS",
    }
    missing_pins = pins - set(scanned)
    assert not missing_pins, (
        f"Scanner self-check pins missing -- scanner regressed: {sorted(missing_pins)}"
    )
    assert len(scanned) >= 26, (
        f"Scanner found only {len(scanned)} vars; baseline is 26 "
        "(verified 2026-06-11). A drop means the scanner went blind, "
        "not that vars were removed -- verify before lowering."
    )


# ---------------------------------------------------------------------------
# Memory backend selector: unknown values warn loudly (the sqlite fiction fix)
# ---------------------------------------------------------------------------

def test_unknown_memory_backend_warns_and_falls_back(monkeypatch, tmp_path, caplog):
    """SYNAPSE_MEMORY_BACKEND=sqlite (or any unknown value) must fall back to
    JSONL with a WARNING naming the valid values -- not silently no-op."""
    from synapse.memory.store import SynapseMemory

    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "sqlite")
    with caplog.at_level(logging.WARNING, logger="synapse.memory"):
        store = SynapseMemory._make_store(
            SynapseMemory.__new__(SynapseMemory), tmp_path
        )
    assert type(store).__name__ == "MemoryStore"
    warnings = [
        rec for rec in caplog.records
        if rec.levelno >= logging.WARNING and "SYNAPSE_MEMORY_BACKEND" in rec.getMessage()
    ]
    assert len(warnings) == 1, (
        f"Expected exactly one backend warning, got {len(warnings)}: "
        f"{[rec.getMessage() for rec in warnings]}"
    )
    message = warnings[0].getMessage()
    assert "sqlite" in message
    for valid in ("jsonl", "moneta", "shadow"):
        assert valid in message


def test_default_memory_backend_stays_silent(monkeypatch, tmp_path, caplog):
    """The default (jsonl) selection must not emit any backend warning."""
    from synapse.memory.store import SynapseMemory

    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "jsonl")
    with caplog.at_level(logging.WARNING, logger="synapse.memory"):
        store = SynapseMemory._make_store(
            SynapseMemory.__new__(SynapseMemory), tmp_path
        )
    assert type(store).__name__ == "MemoryStore"
    backend_warnings = [
        rec for rec in caplog.records
        if rec.levelno >= logging.WARNING and "SYNAPSE_MEMORY_BACKEND" in rec.getMessage()
    ]
    assert not backend_warnings
