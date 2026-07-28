#!/usr/bin/env python
"""V3 producer — R133: mutation-test the controls. Prove each check can fail.

    python harness/notes/econ/v3_controls.py

Emits ``harness/notes/econ/V3_controls.json``. Exits non-zero if any control
survives its mutation.

Law 1: *state the condition under which this fails*. A test that has never been
shown failing is a decoration that will later be cited as evidence — four such
turned up in four subsystems in one session. So each control below names a
mutation of ``probe.py`` that should break it, the mutation is applied to the
real file, the named test is run against the mutant, and the control PASSES
only if the test FAILED.

A mutation that applies cleanly and leaves its test green is the finding, not
an error: it means the control pins nothing.

**Safety.** ``probe.py`` is restored from an in-memory copy in a ``finally``,
and the restored bytes are verified against a sha256 taken before the first
mutation. The digest is printed and written into the artifact so the restore is
auditable rather than merely asserted.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
TARGET = REPO / "python" / "synapse" / "panel" / "providers" / "probe.py"
TESTS = REPO / "tests" / "test_v3_provider_probe.py"


# (id, test that must break, what the mutation does, old, new)
MUTATIONS = [
    (
        "M1", "test_stale_available_row_is_grey_not_green",
        "colour_for stops consulting age and only greys a never-probed row — "
        "the exact 'available because the probe said so an hour ago' defect",
        "    if is_stale(result, now=now, ttl_s=ttl_s):\n        return COLOUR_GREY",
        "    if result.probed_at is None:\n        return COLOUR_GREY",
    ),
    (
        "M2", "test_never_probed_is_grey",
        "is_stale treats a never-probed row as fresh",
        "    age = age_s(result, now=now)\n    if age is None:\n        return True\n    return age > ttl_s or age < 0.0",
        "    age = age_s(result, now=now)\n    if age is None:\n        return False\n    return age > ttl_s or age < 0.0",
    ),
    (
        "M3", "test_future_timestamp_is_grey_not_green",
        "is_stale drops its clock-skew clause, so a future stamp reads fresh",
        "    return age > ttl_s or age < 0.0",
        "    return age > ttl_s",
    ),
    (
        "M4", "test_unknown_quota_does_not_manufacture_red",
        "an unknown quota is read as exhausted — every provider goes RED",
        "    if result.quota_remaining is not None and result.quota_remaining <= 0:\n        return COLOUR_RED",
        "    if (result.quota_remaining or 0) <= 0:\n        return COLOUR_RED",
    ),
    (
        "M5", "test_colour_is_not_a_field",
        "a colour is stored on the structure instead of computed",
        "    probed_at: Optional[float]          # epoch seconds, UTC; None ⇒ never probed",
        "    probed_at: Optional[float]          # epoch seconds, UTC; None ⇒ never probed\n    colour: str = \"green\"",
    ),
    (
        "M6", "test_no_completions_endpoint_in_executable_code",
        "a completions endpoint literal enters executable code",
        "_ANTHROPIC_HOST = \"api.anthropic.com\"",
        "_ANTHROPIC_HOST = \"api.anthropic.com\"\n_COMPLETIONS_PATH = \"/v1/chat/completions\"",
    ),
    (
        "M7", "test_unclassified_gets_no_tier_never_a_default",
        "an unclassifiable model is given a default tier — a guess wearing a "
        "tier constant",
        "    return (), \"unclassified\"",
        "    return (TIER_BALANCED,), \"unclassified\"",
    ),
    (
        "M8", "test_declared_but_absent_model_is_red",
        "declared-but-absent models are dropped instead of reported — the "
        "hou.ActiveRender pattern goes back to being invisible",
        "    for model_id in declared:\n        if model_id in seen or not model_id:\n            continue",
        "    for model_id in declared:\n        if True:\n            continue",
    ),
    (
        "M9", "test_quota_absent_is_reported_as_unobtainable_not_zero",
        "a missing rate-limit header is reported as zero headroom",
        "    return None, None, \"unavailable_at_zero_cost\"",
        "    return 0, 0, \"unavailable_at_zero_cost\"",
    ),
    (
        "M10", "test_no_tool_capability_is_a_hard_gate",
        "the tool-capability gate stops firing, so a model that cannot call "
        "tools is offered to the dispatch spine",
        "    if capabilities is not None and \"tools\" not in {str(c).lower() for c in capabilities}:",
        "    if False and capabilities is not None and \"tools\" not in {str(c).lower() for c in capabilities}:",
    ),
    (
        "M11", "test_refresh_interval_is_at_least_one_per_minute",
        "the refresh floor drops to one second — the probe becomes the thing "
        "that trips the rate limit it reports on",
        "REFRESH_INTERVAL_S = 60.0",
        "REFRESH_INTERVAL_S = 1.0",
    ),
    (
        "M12", "test_ttl_exceeds_refresh_interval",
        "TTL falls below the refresh interval, so a row greys before the layer "
        "is even allowed to re-probe it",
        "PROBE_TTL_S = 180.0",
        "PROBE_TTL_S = 30.0",
    ),
    (
        "M13", "test_cost_never_affects_colour",
        "price reaches the colour computation",
        "    if result.quota_remaining is not None and result.quota_remaining <= 0:\n        return COLOUR_RED\n    return COLOUR_GREEN",
        "    if result.quota_remaining is not None and result.quota_remaining <= 0:\n        return COLOUR_RED\n    if (result.cost_per_1k_in or 0.0) > 100.0:\n        return COLOUR_RED\n    return COLOUR_GREEN",
    ),
    (
        "M14", "test_unconfigured_provider_makes_no_network_call",
        "an unconfigured provider is probed over the network anyway",
        "    if not key:\n        return _unreachable(\"gemini\", declared, probed_at=probed_at,\n                            method=\"local:config\", reason=\"unconfigured\")",
        "    if not key:\n        key = \"placeholder\"",
    ),
    (
        "M15", "test_parameter_size_outranks_name_token",
        "the weak name signal is consulted before the published size",
        "    billions = parse_parameter_size(parameter_size)\n    if billions is not None:",
        "    billions = None if (model_id or display_name) else parse_parameter_size(parameter_size)\n    if billions is not None:",
    ),
    (
        "M16", "test_parse_parameter_size",
        "an unparseable size becomes 0.0 instead of None, which would tier a "
        "700B model as FAST",
        "    m = _PARAM_RE.match(str(text))\n    if not m:\n        return None",
        "    m = _PARAM_RE.match(str(text))\n    if not m:\n        return 0.0",
    ),
]


def run_test(test_name: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "--no-header", "-x", "%s::%s" % (TESTS.as_posix(), test_name)],
        cwd=str(REPO), capture_output=True, text=True)
    tail = (proc.stdout or "").strip().splitlines()
    return proc.returncode, (tail[-1] if tail else "")


def main() -> int:
    original = TARGET.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    # Anchors below are written with \n. The checked-out file may be CRLF, so
    # normalise before matching — an anchor that silently fails to apply would
    # report NOT-APPLIED and look like a missing control rather than a newline
    # artifact. Restoration is from the ORIGINAL bytes, so this never rewrites
    # the file's line endings.
    source = original.decode("utf-8").replace("\r\n", "\n")
    results = []
    try:
        # baseline: every targeted test must be GREEN before any mutation, or
        # a "control flipped" result would be meaningless.
        baseline = []
        for mid, test, _desc, _old, _new in MUTATIONS:
            rc, line = run_test(test)
            baseline.append({"mutation": mid, "test": test, "rc": rc, "tail": line})
        baseline_ok = all(b["rc"] == 0 for b in baseline)

        for mid, test, desc, old, new in MUTATIONS:
            occurrences = source.count(old)
            if occurrences != 1:
                results.append({
                    "mutation": mid, "test": test, "what": desc,
                    "applied": False,
                    "error": "anchor found %d times, expected exactly 1"
                             % occurrences,
                    "control_flips": False,
                })
                continue
            TARGET.write_bytes(source.replace(old, new, 1).encode("utf-8"))
            rc, line = run_test(test)
            TARGET.write_bytes(original)
            results.append({
                "mutation": mid, "test": test, "what": desc,
                "applied": True,
                "exit_code_under_mutation": rc,
                "pytest_tail": line,
                "control_flips": rc != 0,
            })
    finally:
        TARGET.write_bytes(original)

    restored = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    flipped = sum(1 for r in results if r["control_flips"])
    out = {
        "schema": "v3_controls/v1",
        "producer": "harness/notes/econ/v3_controls.py",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "rule": "R133 — a control that has never been shown failing pins nothing.",
        "target": "python/synapse/panel/providers/probe.py",
        "target_sha256_before": digest,
        "target_sha256_after_restore": restored,
        "restore_verified": digest == restored,
        "baseline_all_green_before_mutation": baseline_ok,
        "baseline": baseline,
        "mutations": len(MUTATIONS),
        "controls_that_flip": flipped,
        "all_controls_flip": flipped == len(MUTATIONS),
        "results": results,
    }
    dest = HERE.parent / "V3_controls.json"
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")

    print("wrote %s" % dest)
    print("target sha256 before : %s" % digest)
    print("target sha256 after  : %s   restored=%s" % (restored, digest == restored))
    print("baseline all green   : %s" % baseline_ok)
    for r in results:
        mark = "FLIPS" if r["control_flips"] else ("NO-FLIP" if r["applied"]
                                                   else "NOT-APPLIED")
        print("  %-4s %-8s %s" % (r["mutation"], mark, r["test"]))
        if not r["control_flips"]:
            print("        %s" % r.get("error", r.get("pytest_tail", "")))
    print("%d of %d controls flip under mutation" % (flipped, len(MUTATIONS)))
    ok = out["all_controls_flip"] and out["restore_verified"] and baseline_ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
