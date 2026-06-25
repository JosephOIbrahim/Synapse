"""Proves the fence is a genuine boundary: scope, IP, test-integrity, floor, publish,
and the SYNAPSE phantom-API check — all as pure decide() decisions."""
from fence import decide, scan_phantom

FENCE = {
    "forbidden_paths": ["python/synapse/cognitive/**", "**/*injection*"],
    "forbidden_command_patterns": ["git push", "git tag"],
    "protected_test_globs": ["tests/**", "**/test_*.py"],
}
CONTRACT = {
    "owns": ["python/synapse/panel/**"],
    "do_not_touch": ["python/synapse/panel/claude_worker.py"],
}
PHANTOM = {
    "deny_unverified_prefixes": ["hou.", "pdg."],
    "mode": "denylist",
    "known_phantoms": ["hou.pdg", "hou.secure", "hou.lopNetworks"],
    "allowed_symbols": ["hou.node", "hou.ui", "hou.qt"],
}


def test_allow_within_owns():
    ok, _ = decide("Edit", {"file_path": "python/synapse/panel/face_work.py",
                            "new_string": "x = 1"}, FENCE, CONTRACT, PHANTOM)
    assert ok


def test_scope_deny_outside_owns():
    ok, why = decide("Edit", {"file_path": "python/synapse/other/thing.py"}, FENCE, CONTRACT, PHANTOM)
    assert not ok and "SCOPE-FENCE" in why


def test_ip_deny():
    ok, why = decide("Write", {"file_path": "python/synapse/cognitive/substrate.py"},
                     FENCE, CONTRACT, PHANTOM)
    assert not ok and "IP-FENCE" in why


def test_floor_do_not_touch_deny():
    ok, why = decide("Edit", {"file_path": "python/synapse/panel/claude_worker.py"},
                     FENCE, CONTRACT, PHANTOM)
    assert not ok and "do_not_touch" in why


def test_test_integrity_deny():
    ok, why = decide("Write", {"file_path": "tests/test_x.py"}, FENCE, CONTRACT, PHANTOM)
    assert not ok and "TEST-INTEGRITY" in why


def test_test_integrity_allowed_on_optin():
    c = dict(CONTRACT, allow_test_edits=True, owns=["tests/**"])
    ok, _ = decide("Write", {"file_path": "tests/test_x.py", "new_string": "assert True"},
                   FENCE, c, PHANTOM)
    assert ok


def test_forbidden_command_deny():
    ok, why = decide("Bash", {"command": "git push origin main"}, FENCE, CONTRACT, PHANTOM)
    assert not ok and "IP-FENCE" in why


def test_phantom_known_denied():
    ok, why = decide("Edit", {"file_path": "python/synapse/panel/face_work.py",
                              "new_string": "ctx = hou.pdg.GraphContext()"}, FENCE, CONTRACT, PHANTOM)
    assert not ok and "PHANTOM-API" in why


def test_phantom_clean_allowed():
    ok, _ = decide("Edit", {"file_path": "python/synapse/panel/face_work.py",
                            "new_string": "n = hou.node('/obj')"}, FENCE, CONTRACT, PHANTOM)
    assert ok


def test_phantom_allowlist_blocks_unverified():
    ph = dict(PHANTOM, mode="allowlist")
    ok, why = decide("Edit", {"file_path": "python/synapse/panel/face_work.py",
                              "new_string": "hou.madeUpThing()"}, FENCE, CONTRACT, ph)
    assert not ok and "PHANTOM-API" in why


def test_scan_phantom_is_pure():
    ok, _ = scan_phantom("x = hou.secure.foo()", PHANTOM)
    assert not ok
    ok2, _ = scan_phantom("x = hou.node('/obj')", PHANTOM)
    assert ok2
