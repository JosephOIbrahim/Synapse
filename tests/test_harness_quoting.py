"""Acceptance for W6-QUOTE - kill the injection class (S1 unquoted-interpolation
+ S8 BOM/encoding) across the harness.

Two failure classes, from lived incidents (harness/HARDENING-SPEC.md):

  S1  an uncontrolled string - a leg NAME, id, branch, or path - is interpolated
      into a quoted PowerShell / here-string context and shreds it. An apostrophe
      closes an emitted single-quoted literal and the tail becomes live
      PowerShell: the W5-PARITY/SEAT crash-loop, and the 943e5375 truncation.

  S8  PowerShell 5.1 `Set-Content -Encoding utf8` prepends a UTF-8 BOM that breaks
      a downstream json.load (resolved_lines.json) or a package load
      (the live Houdini synapse.json, 121894d9).

What this pins:

  * The adversarial-name DRY-RUN MATRIX (acceptance predicate 1). Names full of
    apostrophes, backticks, dollars, quotes, an em-dash, CJK, a newline, and an
    outright injection payload are driven through the REAL orchestrate.ps1 dry
    run; the runner it generates for each must parse CLEAN through the PowerShell
    Language Parser, carry NO BOM, and still contain the correctly-escaped name.
    Proof is first-hand parser stdout, not a regex over source.

  * Three static lints over the COMMITTED tree (acceptance predicate 2 / target 4):
      - no committed harness .ps1 builds an inline `-Command "...$..."` string;
      - every committed *.json under harness/ parses with json.load (R26, BOM-free);
      - no committed harness .ps1 writes a *.json path with the BOM-producing
        `-Encoding utf8`.
    Each lint is proven able to FAIL against a planted negative control (Law 1).

  * The central helpers themselves: the python twin (harness/autorevise/
    quote_safe.py) and its PowerShell counterpart Sanitize-SQ produce identical
    escaping (a two-sided oracle), and Write-Utf8NoBom writes no BOM.

PowerShell-driven tests SKIP (never a false pass) where no powershell/pwsh
exists - orchestrate.ps1 is a Windows-PowerShell artifact and the S8 BOM is a
PS-5.1-specific behaviour. The pure-python lints and the python-twin tests run
everywhere.
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORCH = os.path.join(ROOT, "harness", "orchestrate.ps1")
LIB = os.path.join(ROOT, "harness", "lib", "quote-safe.ps1")

sys.path.insert(0, os.path.join(ROOT, "harness", "autorevise"))
from quote_safe import sanitize_sq, ps_single_quote, write_json_no_bom, has_utf8_bom  # noqa: E402


def _powershell():
    return shutil.which("powershell") or shutil.which("pwsh")


def _fwd(p):
    return str(p).replace("\\", "/")


needs_ps = pytest.mark.skipif(
    _powershell() is None,
    reason="no powershell/pwsh on this host - orchestrate.ps1 is a PS artifact",
)

# ---------------------------------------------------------------------------
# Adversarial inputs. Each carries every metacharacter the brief names, plus
# outright injection payloads. They travel to PowerShell as JSON (BOM-free
# UTF-8) read by ConvertFrom-Json - NEVER as a .ps1 literal, which PS 5.1 would
# misdecode as ANSI (that mangling is itself the S8 class).
# ---------------------------------------------------------------------------
ADVERSARIAL_NAMES = {
    "apostrophe": "O'Brien",
    "quote-then-code": "'; Remove-Item C:\\ -Recurse; '",
    "backtick": "a`b`n`c",
    "dollar-subexpr": "x $(Remove-Item C:\\) y",
    "dollar-var": "cost $env:SECRET here",
    "double-quote": 'he said "run it"',
    "em-dash": "wave\u2014six",
    "unicode-cjk": "\u65e5\u672c\u8a9e ni\u00f1o caf\u00e9",
    "injection-combo": "q'; Write-Host 'PWNED'; '",
    "everything": "a'\"`$(x)b\u2014\u65e5\u672c",
    "newline": "line1\nline2'end",
    "trailing-apos": "danger'",
}
ADVERSARIAL_BRANCHES = {
    "br-apos": "wave6/o'brien",
    "br-meta": "feat/a`b$c'd",
}


def _legs():
    legs = [
        {"id": lbl, "name": nm, "branch": "wave6/quote",
         "worktree": ".claude/worktrees/%s" % lbl, "prompt": "harness/x.md",
         "readonly": False, "deps": []}
        for lbl, nm in ADVERSARIAL_NAMES.items()
    ]
    legs += [
        {"id": lbl, "name": "safe name", "branch": br,
         "worktree": ".claude/worktrees/%s" % lbl, "prompt": "harness/x.md",
         "readonly": False, "deps": []}
        for lbl, br in ADVERSARIAL_BRANCHES.items()
    ]
    # one read-only leg exercises the OTHER $profile branch (readonly path)
    legs.append({"id": "ro-apos", "name": "ro'leg", "branch": "wave6/quote",
                 "worktree": ".claude/worktrees/ro", "prompt": "harness/x.md",
                 "readonly": True, "deps": []})
    return legs


# The driver dot-sources the REAL orchestrate.ps1 in library mode (functions
# defined, board loop skipped) and calls the REAL Start-Leg under -DryRun.
#
# Two hard-won encoding rules, both instances of the very classes under test:
#   * the manifest is read with [System.IO.File]::ReadAllText (UTF-8), NOT
#     Get-Content, which on PS 5.1 reads a BOM-less file as ANSI and mangles
#     unicode names (S8); the result is written back with Write-Utf8NoBom so the
#     python side reads clean UTF-8 off a file, never off PS stdout.
#   * the param is $ManifestFile, NOT $Manifest/$ManifestPath: PowerShell
#     variables are case-insensitive, so $Manifest would BE orchestrate's
#     [string]$manifest, and assigning the parsed object to it would silently
#     coerce it back to a string (a variable-shadowing bug - S1's cousin).
_DRIVER = r"""
param([string]$Orch, [string]$Repo, [string]$ManifestFile, [string]$OutDir, [string]$OutJson)
$env:SYNAPSE_ORCH_LIB = '1'
$env:TEMP = $OutDir
$env:TMP = $OutDir
. $Orch -Repo $Repo -DryRun *> $null
$manifest = [System.IO.File]::ReadAllText($ManifestFile) | ConvertFrom-Json
$script:DryDispatched = @{}
$res = [ordered]@{}
foreach ($leg in @($manifest.legs)) {
    Start-Leg $leg *> $null
    $rp = Join-Path $env:TEMP ("orch_" + $leg.id + ".ps1")
    $entry = [ordered]@{}
    if (Test-Path $rp) {
        $e = $null
        [void][System.Management.Automation.Language.Parser]::ParseFile($rp, [ref]$null, [ref]$e)
        $bytes = [System.IO.File]::ReadAllBytes($rp)
        $entry.exists = $true
        $entry.count = $e.Count
        $entry.errors = @($e | ForEach-Object { $_.Message })
        $entry.bom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    } else {
        $entry.exists = $false
        $entry.count = -1
        $entry.errors = @('runner not written')
        $entry.bom = $false
    }
    $res[[string]$leg.id] = $entry
}
$res | ConvertTo-Json -Depth 6 | Write-Utf8NoBom -Path $OutJson
"""


@pytest.fixture(scope="module")
def dryrun(tmp_path_factory):
    """Run the REAL orchestrate.ps1 dry run ONCE over every adversarial leg and
    return {id: {exists, count, errors, bom, runner_text}}.

    Isolated: -Repo and $env:TEMP point at a throwaway dir, so no worktree is
    created, no lock is taken, no window is spawned (all of that is after the
    dry-run return), and Backup-Branches finds no git repo to push."""
    ps = _powershell()
    if ps is None:
        pytest.skip("no powershell")
    tmp = tmp_path_factory.mktemp("dryrun")
    man = tmp / "control.json"
    # BOM-free UTF-8 - the manifest itself must not carry the S8 landmine.
    write_json_no_bom(man, {"settings": "harness/relay-settings.json",
                            "effort": "high", "legs": _legs()})
    driver = tmp / "driver.ps1"
    driver.write_text(_DRIVER, encoding="utf-8")  # pure ASCII driver
    outjson = tmp / "results.json"
    out = subprocess.run(
        [ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", _fwd(driver), "-Orch", _fwd(ORCH), "-Repo", _fwd(tmp),
         "-ManifestFile", _fwd(man), "-OutDir", _fwd(tmp), "-OutJson", _fwd(outjson)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180,
    )
    assert out.returncode == 0, "driver failed:\nSTDOUT\n%s\nSTDERR\n%s" % (
        out.stdout, out.stderr)
    assert outjson.exists(), "driver wrote no results:\nSTDOUT\n%s\nSTDERR\n%s" % (
        out.stdout, out.stderr)
    data = json.loads(outjson.read_text(encoding="utf-8"))
    # attach the runner text (read in python, UTF-8) for content + BOM checks
    for legid, entry in data.items():
        rp = tmp / ("orch_%s.ps1" % legid)
        entry["runner_text"] = rp.read_text(encoding="utf-8") if rp.exists() else ""
        entry["py_bom"] = has_utf8_bom(rp) if rp.exists() else None
    return data


@needs_ps
@pytest.mark.parametrize("label", list(ADVERSARIAL_NAMES), ids=list(ADVERSARIAL_NAMES))
def test_adversarial_name_runner_parses_clean(dryrun, label):
    """FAILS IF: the runner orchestrate.ps1 generates for a metacharacter-laden
    leg NAME does not parse through the PowerShell Language Parser, carries a
    BOM, or drops the name.

    This is the crash-loop, pinned: before the fix, a name with an apostrophe
    emitted `--name 'SYNAPSE <id> O'Brien'`, an unterminated single-quoted
    literal, and the launcher window died on a parse error every poll."""
    name = ADVERSARIAL_NAMES[label]
    r = dryrun[label]
    assert r["exists"], "no runner generated for %r" % name
    assert r["count"] == 0, (
        "runner for name %r has %d parse error(s):\n  %s"
        % (name, r["count"], "\n  ".join(r["errors"])))
    assert not r["bom"] and not r["py_bom"], "runner for %r carries a UTF-8 BOM" % name
    # parses clean AND kept the name, correctly escaped (guards against a
    # runner that parses only because it silently dropped the payload).
    assert sanitize_sq(name) in r["runner_text"], (
        "runner for %r parsed but does not contain the escaped name %r"
        % (name, sanitize_sq(name)))


@needs_ps
@pytest.mark.parametrize("label", list(ADVERSARIAL_BRANCHES), ids=list(ADVERSARIAL_BRANCHES))
def test_adversarial_branch_runner_parses_clean(dryrun, label):
    """FAILS IF: an uncontrolled BRANCH string breaks the generated runner.
    leg.branch is interpolated into a single-quoted emitted line too, so it
    gets the same Sanitize-SQ treatment as the name."""
    br = ADVERSARIAL_BRANCHES[label]
    r = dryrun[label]
    assert r["exists"], "no runner generated for branch %r" % br
    assert r["count"] == 0, (
        "runner for branch %r has %d parse error(s):\n  %s"
        % (br, r["count"], "\n  ".join(r["errors"])))
    assert sanitize_sq(br) in r["runner_text"], (
        "runner for branch %r does not contain the escaped branch" % br)


@needs_ps
def test_every_adversarial_runner_is_clean_and_bomfree(dryrun):
    """FAILS IF: any leg in the whole matrix (names + branches + read-only)
    produced a dirty or BOM-carrying runner. One aggregate assertion so a
    regression that only bites one obscure metachar still turns the suite red."""
    dirty = {k: v for k, v in dryrun.items()
             if not v["exists"] or v["count"] != 0 or v["bom"] or v["py_bom"]}
    assert not dirty, "unclean runners:\n" + "\n".join(
        "  %s: exists=%s count=%s bom=%s errors=%s"
        % (k, v["exists"], v["count"], v["bom"] or v["py_bom"], v["errors"])
        for k, v in dirty.items())


# ---------------------------------------------------------------------------
# The python twin + the two-sided oracle.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,expect", [
    ("O'Brien", "O''Brien"),
    ("''", "''''"),
    ("plain", "plain"),
    ("a`b$c \u2014 \u65e5", "a`b$c \u2014 \u65e5"),   # only apostrophes change
    ("", ""),
    ("'", "''"),
])
def test_python_sanitize_sq(raw, expect):
    """FAILS IF: the python twin does not double every apostrophe (and nothing
    else) for a single-quoted PowerShell context."""
    assert sanitize_sq(raw) == expect
    assert ps_single_quote(raw) == "'" + expect + "'"


def test_python_sanitize_sq_none():
    assert sanitize_sq(None) == ""


def test_write_json_no_bom_roundtrips(tmp_path):
    """FAILS IF: the python BOM-free writer emits a BOM or an unparseable file."""
    p = tmp_path / "x.json"
    write_json_no_bom(p, {"name": "O'Brien", "u": "caf\u00e9\u2014\u65e5"})
    assert not has_utf8_bom(p)
    assert json.load(open(p, encoding="utf-8"))["name"] == "O'Brien"


@needs_ps
@pytest.mark.parametrize("raw", list(ADVERSARIAL_NAMES.values()))
def test_ps_and_python_sanitize_agree(raw):
    """FAILS IF: PowerShell Sanitize-SQ and python sanitize_sq disagree on any
    adversarial input - the two-sided oracle the runner test relies on.

    The value crosses to PowerShell as a JSON file (BOM-free), not a literal, so
    unicode survives; PS echoes Sanitize-SQ of it back through the same channel."""
    ps = _powershell()
    import tempfile
    d = tempfile.mkdtemp()
    try:
        inp = os.path.join(d, "in.json")
        outp = os.path.join(d, "out.json")
        write_json_no_bom(inp, {"v": raw})
        script = "\n".join([
            ". '%s'" % _fwd(LIB),
            # ReadAllText (UTF-8), never Get-Content (ANSI on PS 5.1) - else the
            # unicode input is mangled before Sanitize-SQ ever sees it.
            "$v = ([System.IO.File]::ReadAllText('%s') | ConvertFrom-Json).v" % _fwd(inp),
            "@{ v = (Sanitize-SQ $v) } | ConvertTo-Json -Compress | "
            "Write-Utf8NoBom -Path '%s'" % _fwd(outp),
        ])
        r = subprocess.run(
            [ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-Command", script],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=90)
        assert r.returncode == 0, "PS failed:\n%s\n%s" % (r.stdout, r.stderr)
        assert not has_utf8_bom(outp), "Write-Utf8NoBom emitted a BOM"
        ps_val = json.load(open(outp, encoding="utf-8"))["v"]
        assert ps_val == sanitize_sq(raw), (
            "PS Sanitize-SQ %r != python sanitize_sq %r for input %r"
            % (ps_val, sanitize_sq(raw), raw))
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# Static lints over the COMMITTED tree, each with a negative control.
# ---------------------------------------------------------------------------
import re  # noqa: E402

_RETIRED = os.path.join("harness", "retired") + os.sep
# inline `-Command "...$..."` - a double-quoted -Command arg carrying interpolation
_RE_CMD = re.compile(r'-Command\s+"[^"]*\$', re.IGNORECASE)
# a *.json path written with the BOM-producing -Encoding utf8 (not utf8NoBOM)
_RE_BOMJSON = re.compile(
    r'(Set-Content|Out-File)\b.*\.json.*-Encoding\s+utf8(?!NoBOM|NoBom)',
    re.IGNORECASE)


def _git_ls(rel_glob_ext):
    try:
        out = subprocess.run(["git", "-C", ROOT, "ls-files", "harness"],
                             capture_output=True, text=True, timeout=30)
        files = [os.path.join(ROOT, p) for p in out.stdout.splitlines()
                 if p.endswith(rel_glob_ext)]
        if files:
            return files
    except Exception:
        pass
    import glob
    return glob.glob(os.path.join(ROOT, "harness", "**", "*" + rel_glob_ext),
                     recursive=True)


def _harness_ps1(exclude_retired=True):
    files = _git_ls(".ps1")
    if exclude_retired:
        files = [f for f in files if _RETIRED not in f]
    return files


def find_command_interpolation(files):
    hits = []
    for f in files:
        try:
            for i, line in enumerate(open(f, encoding="utf-8", errors="replace"), 1):
                if _RE_CMD.search(line):
                    hits.append("%s:%d %s" % (os.path.relpath(f, ROOT), i, line.strip()))
        except OSError:
            pass
    return hits


def find_bom_json_writes(files):
    hits = []
    for f in files:
        try:
            for i, line in enumerate(open(f, encoding="utf-8", errors="replace"), 1):
                if _RE_BOMJSON.search(line):
                    hits.append("%s:%d %s" % (os.path.relpath(f, ROOT), i, line.strip()))
        except OSError:
            pass
    return hits


def find_unparseable_json(files):
    bad = []
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                json.load(fh)
        except Exception as e:
            bad.append("%s: %s" % (os.path.relpath(f, ROOT), str(e)[:80]))
    return bad


def test_lint_no_inline_command_interpolation():
    """FAILS IF: any committed harness .ps1 builds an inline
    `-Command "...$var..."` string (target 4). Such a string re-parses its
    interpolated content as code - the injection surface this leg exists to
    remove. Zero today; this keeps it zero."""
    hits = find_command_interpolation(_harness_ps1())
    assert not hits, "inline -Command interpolation found:\n  " + "\n  ".join(hits)


def test_lint_command_interpolation_control_can_fail(tmp_path):
    """Negative control (Law 1): the lint MUST flag a planted violation, else it
    is a decoration that greens on anything."""
    bad = tmp_path / "bad.ps1"
    bad.write_text('powershell -Command "Write-Host $env:SECRET"\n', encoding="utf-8")
    assert find_command_interpolation([str(bad)]), "lint failed to flag a real -Command interpolation"


def test_lint_all_harness_json_parses():
    """FAILS IF: any committed *.json under harness/ does not parse with
    json.load - R26 realized ("assert every JSON under harness/ parses"), the
    S8 gate. Catches a BOM, cp1252 mojibake, or a torn write regardless of which
    producer wrote it."""
    bad = find_unparseable_json(_git_ls(".json"))
    assert not bad, "unparseable committed JSON under harness/:\n  " + "\n  ".join(bad)


def test_lint_json_parse_control_can_fail(tmp_path):
    """Negative control: a BOM'd JSON file must be flagged."""
    p = tmp_path / "bom.json"
    with open(p, "wb") as fh:
        fh.write(b"\xef\xbb\xbf" + json.dumps({"a": 1}).encode("utf-8"))
    assert find_unparseable_json([str(p)]), "lint failed to flag a BOM'd JSON"


def test_lint_no_bom_json_writes():
    """FAILS IF: any committed harness .ps1 (outside retired/) writes a *.json
    path with the BOM-producing `-Encoding utf8` - the S8 producer, caught
    before it ever writes the file. Fixed producers pipe to Write-Utf8NoBom."""
    hits = find_bom_json_writes(_harness_ps1())
    assert not hits, "BOM-producing JSON writes found:\n  " + "\n  ".join(hits)


def test_lint_bom_json_write_control_can_fail(tmp_path):
    """Negative control: the producer lint must flag a real BOM json write."""
    bad = tmp_path / "bad.ps1"
    bad.write_text("$x | ConvertTo-Json | Set-Content foo.json -Encoding utf8\n",
                   encoding="utf-8")
    assert find_bom_json_writes([str(bad)]), "lint failed to flag a BOM json write"
