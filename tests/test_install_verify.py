"""Tests for `install_synapse_package.py --verify` — the read-only front-door check.

Standalone, no Houdini. Never plants a `hou` fake in sys.modules (the repo-wide
fake-residency trap: the alphabetically-first planter wins for the whole run).
Nothing here imports `synapse` either — the installer is deliberately import-free
so it runs on any stock python, and these tests hold it to that.

Pins four contracts:
  1. --verify is READ-ONLY (no synapse.json, no stamp, no env mutation)
  2. the key probe reports presence ONLY — never a value, prefix or suffix
  3. exit code: 0 when no programmatic check FAILs, 1 when any does
  4. MANUAL rows never render as PASS and never affect the exit code
"""

import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _load_installer():
    path = _ROOT / "scripts" / "install_synapse_package.py"
    spec = importlib.util.spec_from_file_location("install_synapse_package_verify", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


inst = _load_installer()

# A fake key that is obviously not real but is shaped like one, so a leak is
# unmistakable in the assertion output.
FAKE_KEY = "sk-ant-VERIFYLEAKCANARY0123456789"


def _make_repo(tmp_path, *, vendor=True, env_lines=None):
    """A minimal tree that satisfies every filesystem probe."""
    repo = tmp_path / "SYNAPSE"
    (repo / "python" / "synapse").mkdir(parents=True)
    (repo / "scripts").mkdir()
    (repo / "houdini" / "python_panels").mkdir(parents=True)
    (repo / "README.md").write_text("readme", encoding="utf-8")
    (repo / "houdini" / "python_panels" / "synapse_panel.pypanel").write_text(
        "<pythonPanelDocument/>", encoding="utf-8")
    (repo / "python" / "synapse" / "__init__.py").write_text(
        '__version__ = "9.9.9"\n', encoding="utf-8")
    if vendor:
        vend = repo / "python" / "synapse" / "_vendor"
        for pkg in inst.VENDOR_PKGS:
            (vend / pkg).mkdir(parents=True)
            (vend / pkg / "__init__.py").write_text("", encoding="utf-8")
        for sub, stem in inst.VENDOR_NATIVE:
            (vend / sub).mkdir(parents=True, exist_ok=True)
            for abi in (inst.H22_ABI, inst.LEGACY_ABI):
                (vend / sub / f"{stem}.{abi}.pyd").write_text("", encoding="utf-8")
    if env_lines is not None:
        (repo / ".env").write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    return repo


def _installed_pref(tmp_path, repo, name="houdini22.0"):
    """A pref dir carrying a synapse.json that points at `repo`."""
    pref = tmp_path / name
    (pref / "packages").mkdir(parents=True)
    (pref / "packages" / "synapse.json").write_text(
        json.dumps(inst.build_package(repo), indent=4), encoding="utf-8")
    return pref


def _rows(repo, prefs, monkeypatch, tmp_path):
    """collect_rows with the stamp + Houdini probes pinned to tmp state."""
    monkeypatch.setattr(inst, "stamp_path", lambda: tmp_path / "nostamp.json")
    monkeypatch.setattr(inst, "houdini_installs", lambda: [Path("Houdini 22.0.368")])
    return inst.collect_rows(repo, prefs)


# --------------------------------------------------------------- read-only ---

def test_verify_writes_nothing_anywhere(tmp_path, monkeypatch, capsys):
    """The load-bearing safety contract: --verify must not create or modify a
    single file — not the package json, not the stamp, not the .env."""
    repo = _make_repo(tmp_path, env_lines=[f"ANTHROPIC_API_KEY={FAKE_KEY}"])
    pref = _installed_pref(tmp_path, repo)
    stamp = tmp_path / "state" / "install_stamp.json"
    monkeypatch.setattr(inst, "stamp_path", lambda: stamp)
    monkeypatch.setattr(inst, "resolve_repo_root", lambda: repo)
    monkeypatch.setattr(inst, "houdini_installs", lambda: [Path("Houdini 22.0.368")])

    before = {p: p.stat().st_mtime_ns for p in sorted(tmp_path.rglob("*")) if p.is_file()}
    inst.main(["--pref-dir", str(pref), "--verify"])
    after = {p: p.stat().st_mtime_ns for p in sorted(tmp_path.rglob("*")) if p.is_file()}

    assert before == after, "--verify mutated the tree"
    assert not stamp.exists(), "--verify wrote the install stamp"
    capsys.readouterr()


def test_verify_never_writes_a_package_into_an_empty_pref_dir(tmp_path, monkeypatch, capsys):
    """A bare pref dir must stay bare — --verify reports, it does not repair."""
    repo = _make_repo(tmp_path, env_lines=[f"ANTHROPIC_API_KEY={FAKE_KEY}"])
    pref = tmp_path / "houdini22.0"
    pref.mkdir()
    monkeypatch.setattr(inst, "resolve_repo_root", lambda: repo)
    monkeypatch.setattr(inst, "stamp_path", lambda: tmp_path / "nostamp.json")
    monkeypatch.setattr(inst, "houdini_installs", lambda: [Path("Houdini 22.0.368")])

    rc = inst.main(["--pref-dir", str(pref), "--verify"])

    assert rc == 1, "an unwired pref dir must FAIL, not be silently fixed"
    assert not (pref / "packages").exists()
    capsys.readouterr()


def test_verify_does_not_mutate_the_environment(tmp_path, monkeypatch, capsys):
    """auth._load_dotenv mutates os.environ at import time. The installer's
    probe reimplements the parser instead precisely so --verify stays inert."""
    repo = _make_repo(tmp_path, env_lines=[f"ANTHROPIC_API_KEY={FAKE_KEY}",
                                           "SYNAPSE_VERIFY_CANARY=1"])
    monkeypatch.delenv("SYNAPSE_VERIFY_CANARY", raising=False)
    monkeypatch.setattr(inst, "stamp_path", lambda: tmp_path / "nostamp.json")
    monkeypatch.setattr(inst, "houdini_installs", lambda: [Path("Houdini 22.0.368")])

    import os
    inst.verify(repo, [_installed_pref(tmp_path, repo)])

    assert "SYNAPSE_VERIFY_CANARY" not in os.environ
    capsys.readouterr()


# ------------------------------------------------------------ key security ---

def test_key_probe_never_leaks_the_value(tmp_path, monkeypatch, capsys):
    """HARD SECURITY CONSTRAINT: presence only. Not the value, not a prefix,
    not a suffix — no substring of the key may reach stdout or a returned row."""
    repo = _make_repo(tmp_path, env_lines=[f"ANTHROPIC_API_KEY={FAKE_KEY}"])
    monkeypatch.setattr(inst, "stamp_path", lambda: tmp_path / "nostamp.json")
    monkeypatch.setattr(inst, "houdini_installs", lambda: [Path("Houdini 22.0.368")])

    inst.verify(repo, [_installed_pref(tmp_path, repo)])
    out = capsys.readouterr().out

    assert FAKE_KEY not in out
    # No run of 8+ chars from the secret body may appear either — that rules out
    # a "safe-looking" prefix/suffix echo, not just the whole string.
    body = FAKE_KEY[len("sk-ant-"):]
    for i in range(len(body) - 8):
        assert body[i:i + 8] not in out, f"leaked fragment {body[i:i + 8]!r}"
    assert "ANTHROPIC_API_KEY present" in out  # but it DID report presence


def test_key_probe_returns_names_only(tmp_path):
    """The .env parser must surface names, never values."""
    repo = _make_repo(tmp_path, env_lines=[
        "# a comment",
        "",
        f"export ANTHROPIC_API_KEY=\"{FAKE_KEY}\"",
        "GEMINI_API_KEY=",          # empty value -> absent
        "NOT_A_PAIR",
    ])
    names = inst._dotenv_key_names(repo)
    assert names == {"ANTHROPIC_API_KEY"}
    assert FAKE_KEY not in repr(names)


def test_key_probe_reports_absent_without_crashing(tmp_path, monkeypatch):
    """No .env, no shell var -> a clean FAIL row, not an exception."""
    repo = _make_repo(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    rows = inst.check_api_key(repo)
    key_row = [r for r in rows if r[1] == "claude key"][0]
    assert key_row[0] == inst.FAIL
    assert "absent" in key_row[2]


def test_shell_env_wins_over_dotenv(tmp_path, monkeypatch):
    """auth._load_dotenv uses setdefault, so an exported var wins. The report
    must name the same source Houdini would actually use."""
    repo = _make_repo(tmp_path, env_lines=[f"ANTHROPIC_API_KEY={FAKE_KEY}"])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-the-shell")
    assert inst._key_source("ANTHROPIC_API_KEY", inst._dotenv_key_names(repo)) == "shell env"
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert inst._key_source("ANTHROPIC_API_KEY", inst._dotenv_key_names(repo)) == ".env"


def test_dotenv_parser_has_not_drifted_from_auth():
    """The installer REIMPLEMENTS synapse.host.auth._load_dotenv rather than
    importing it (importing would fold .env into os.environ and trip the vendor
    ABI warning on stock python). Two copies of one parser drift silently — the
    exact code/corpus-divergence failure mode — so pin the semantic markers.

    Read as source, never imported: importing auth.py would pull the real repo
    .env, and this seat's actual key, into the test process.
    """
    src = (_ROOT / "python" / "synapse" / "host" / "auth.py").read_text(encoding="utf-8")
    assert "def _load_dotenv" in src, "auth._load_dotenv moved — re-check the probe"
    for marker in ('startswith("#")', 'partition("=")', 'export ', "setdefault"):
        assert marker in src, (
            f"auth._load_dotenv no longer uses {marker!r}; "
            "_dotenv_key_names in scripts/install_synapse_package.py must match it")


# --------------------------------------------------------------- exit code ---

def test_exit_zero_when_everything_passes(tmp_path, monkeypatch, capsys):
    repo = _make_repo(tmp_path, env_lines=[f"ANTHROPIC_API_KEY={FAKE_KEY}"])
    monkeypatch.setattr(inst, "stamp_path", lambda: tmp_path / "nostamp.json")
    monkeypatch.setattr(inst, "houdini_installs", lambda: [Path("Houdini 22.0.368")])
    rc = inst.verify(repo, [_installed_pref(tmp_path, repo)])
    out = capsys.readouterr().out
    assert rc == 0
    assert inst.FAIL not in out.split("\n\n")[1]  # no FAIL row in the table


def test_exit_one_when_a_programmatic_check_fails(tmp_path, monkeypatch, capsys):
    """Missing cp313 native -> H22 cannot load the brain -> non-zero."""
    repo = _make_repo(tmp_path, env_lines=[f"ANTHROPIC_API_KEY={FAKE_KEY}"])
    (repo / "python" / "synapse" / "_vendor" / "pydantic_core"
     / f"_pydantic_core.{inst.H22_ABI}.pyd").unlink()
    monkeypatch.setattr(inst, "stamp_path", lambda: tmp_path / "nostamp.json")
    monkeypatch.setattr(inst, "houdini_installs", lambda: [Path("Houdini 22.0.368")])
    rc = inst.verify(repo, [_installed_pref(tmp_path, repo)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "H22" in out and inst.H22_ABI in out


def test_stale_package_pointing_at_another_checkout_fails(tmp_path, monkeypatch):
    """The exact silent failure the OneDrive trap produced: a synapse.json that
    exists and parses, but wires a DIFFERENT tree."""
    repo = _make_repo(tmp_path, env_lines=[f"ANTHROPIC_API_KEY={FAKE_KEY}"])
    other = _make_repo(tmp_path / "elsewhere", vendor=False)
    pref = _installed_pref(tmp_path, other)
    rows = _rows(repo, [pref], monkeypatch, tmp_path)
    pkg_row = [r for r in rows if r[1] == "package file"][0]
    assert pkg_row[0] == inst.FAIL
    assert "another checkout" in pkg_row[2]


def test_missing_clone_files_fail(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    (repo / "houdini" / "python_panels" / "synapse_panel.pypanel").unlink()
    rows = inst.check_clone(repo)
    assert rows[0][0] == inst.FAIL
    assert "synapse_panel.pypanel" in rows[0][2]


def test_no_pref_dir_found_is_a_fail_row_not_an_install_message(tmp_path, monkeypatch, capsys):
    """--verify must never fall into the installer's 'pass --pref-dir' bail-out;
    an empty candidate list is a reported FAIL row."""
    repo = _make_repo(tmp_path, env_lines=[f"ANTHROPIC_API_KEY={FAKE_KEY}"])
    monkeypatch.setattr(inst, "resolve_repo_root", lambda: repo)
    monkeypatch.setattr(inst, "candidate_pref_dirs", lambda: [])
    monkeypatch.setattr(inst, "stamp_path", lambda: tmp_path / "nostamp.json")
    monkeypatch.setattr(inst, "houdini_installs", lambda: [Path("Houdini 22.0.368")])
    rc = inst.main(["--verify"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "no Houdini user pref dir found" in out
    assert "package file" in out  # reported as a row, not a bare error


# ------------------------------------------------------------ manual rows ----

def test_manual_rows_never_render_as_pass(tmp_path, monkeypatch, capsys):
    """The in-Houdini-only checks must be visibly MANUAL. A green CLI must never
    imply a green menu entry or a working 'make a box'."""
    repo = _make_repo(tmp_path, env_lines=[f"ANTHROPIC_API_KEY={FAKE_KEY}"])
    monkeypatch.setattr(inst, "stamp_path", lambda: tmp_path / "nostamp.json")
    monkeypatch.setattr(inst, "houdini_installs", lambda: [Path("Houdini 22.0.368")])
    rc = inst.verify(repo, [_installed_pref(tmp_path, repo)])
    out = capsys.readouterr().out

    assert rc == 0  # all-green run...
    for status, label, _detail in inst.manual_rows():
        assert status == inst.MANUAL
        line = [ln for ln in out.splitlines() if label in ln][0]
        assert line.strip().startswith(inst.MANUAL)
        assert inst.PASS not in line


def test_manual_rows_do_not_affect_the_exit_code(tmp_path, monkeypatch, capsys):
    """MANUAL is neither pass nor fail — it must not push the exit code either way."""
    repo = _make_repo(tmp_path, env_lines=[f"ANTHROPIC_API_KEY={FAKE_KEY}"])
    monkeypatch.setattr(inst, "stamp_path", lambda: tmp_path / "nostamp.json")
    monkeypatch.setattr(inst, "houdini_installs", lambda: [Path("Houdini 22.0.368")])
    monkeypatch.setattr(inst, "manual_rows", lambda: [])
    rc_without = inst.verify(repo, [_installed_pref(tmp_path, repo)])
    capsys.readouterr()
    assert rc_without == 0


def test_manual_rows_carry_a_concrete_action(tmp_path):
    """A MANUAL row that doesn't tell the human what to do is a fake check."""
    for status, label, detail in inst.manual_rows():
        assert status == inst.MANUAL
        assert label and len(detail) > 20, f"{label} has no actionable detail"


def test_every_row_has_a_known_status(tmp_path, monkeypatch):
    """No row may invent a fourth verdict — the exit-code math counts PASS/FAIL
    and ignores MANUAL, so an unknown status would silently vanish."""
    repo = _make_repo(tmp_path, env_lines=[f"ANTHROPIC_API_KEY={FAKE_KEY}"])
    rows = _rows(repo, [_installed_pref(tmp_path, repo)], monkeypatch, tmp_path)
    assert rows
    for status, label, detail in rows:
        assert status in (inst.PASS, inst.FAIL, inst.MANUAL), f"{label}: {status}"


def test_houdini_probe_reports_absence_honestly():
    """No Houdini discoverable -> FAIL with the $HFS remedy, never a fake PASS."""
    rows = inst.check_houdini([])
    assert rows[0][0] == inst.FAIL
    assert "HFS" in rows[0][2]


def test_pref_names_derived_from_install_dirs():
    """Houdini keys prefs on major.minor, so the install dir name decides which
    pref dir has to be wired."""
    assert inst.pref_names_for([Path("Houdini 22.0.368"), Path("Houdini 21.0.773")]) == {
        "houdini22.0", "houdini21.0"}
    assert inst.pref_names_for([Path("Houdini Server")]) == set()


def test_wired_h21_but_unwired_h22_fails(tmp_path, monkeypatch):
    """THE drop-day trap: the installer reports success, a pref dir IS wired —
    but it's the H21 one, and the installed H22 never sees the package. A bare
    'something is wired' verdict would call this green."""
    repo = _make_repo(tmp_path, env_lines=[f"ANTHROPIC_API_KEY={FAKE_KEY}"])
    wired21 = _installed_pref(tmp_path, repo, name="houdini21.0")
    bare22 = tmp_path / "houdini22.0"
    bare22.mkdir()
    monkeypatch.setattr(inst, "stamp_path", lambda: tmp_path / "nostamp.json")

    rows = inst.check_package_file(repo, [wired21, bare22], {"houdini22.0", "houdini21.0"})
    pkg_row = rows[0]
    assert pkg_row[0] == inst.FAIL
    assert "houdini22.0 is NOT wired" in pkg_row[2]

    # ...and with H22 wired too, it passes.
    _installed_pref(tmp_path, repo, name="houdini22.0")
    ok = inst.check_package_file(repo, [wired21, bare22], {"houdini22.0", "houdini21.0"})
    assert ok[0][0] == inst.PASS


def test_package_check_without_discoverable_builds_falls_back(tmp_path, monkeypatch):
    """No Houdini found -> no build to target, so 'any wired dir' is the honest
    verdict. The houdini row carries the FAIL in that case, not this one."""
    repo = _make_repo(tmp_path, env_lines=[f"ANTHROPIC_API_KEY={FAKE_KEY}"])
    monkeypatch.setattr(inst, "stamp_path", lambda: tmp_path / "nostamp.json")
    rows = inst.check_package_file(repo, [_installed_pref(tmp_path, repo)], set())
    assert rows[0][0] == inst.PASS


# --------------------------------------------------------------- install ----

def test_install_path_still_works_after_verify_was_added(tmp_path, capsys):
    """Regression guard: --verify must not have disturbed the install path."""
    pref = tmp_path / "houdini22.0"
    pref.mkdir()
    rc = inst.main(["--pref-dir", str(pref), "--dry-run"])
    assert rc == 0
    assert "would write" in capsys.readouterr().out
    assert not (pref / "packages" / "synapse.json").exists()
