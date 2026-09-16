"""Cut v5.74.0, per docs/RELEASE_CARD.md.

build -> qualify -> suites -> compose -> commit -> gate -> tag -> push -> publish -> verify

The `bump` and `notes` steps of the previous cut scripts are ABSENT on purpose. The
working tree arrived already bumped (all six surfaces CONFORM, verified with
`scripts/sync_version.py` before this script was written) and the notes were authored
by hand rather than generated from a template, because this release's content is the
README rebuild itself. `step_preflight` re-checks the bump rather than trusting it --
a step that is skipped needs a check more than a step that is run, not less.

Every number in the notes and the three composed assets is PARSED from a measured
artifact on disk; nothing is retyped (Law 2). The script stops at the first failure
with the evidence, and never forces anything.

  python harness/notes/release-5.74.0/cut.py [--from STEP] [--until STEP]

Steps: preflight, build, qual, suites, compose, commit, tag, push, publish, verify
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time

V = "5.74.0"
PREV = "v5.73.0"
REPO = r"C:/Users/User/SYNAPSE"
BUILD = r"C:\synapse-build"
OUT = BUILD + r"\output-" + V
OUTDIR = OUT + r"\output"
HFS = r"C:\Program Files\Side Effects Software\Houdini 22.0.400"
HYTHON = HFS + r"\bin\hython.exe"
MONETA = BUILD + r"\moneta-local.zip"
MONETA_SHA = "81a3d8735c7da49ca81302725acab6a3324311091e850c34afcea92e87ea31f7"
ISCC = BUILD + r"\tools\inno\ISCC.exe"
N = os.path.join(REPO, "harness/notes/release-" + V)
LOG = os.path.join(N, "cut.log")

# The seat baseline, BY NAME. Six, not five: v5.73.0's composer listed five while its own
# seat log showed six, and `new = measured - known` therefore re-manufactured the sixth as a
# NEW regression at v5.72.0 and again at v5.73.0 -- one and two releases after it first
# appeared. All three published installer-verification.json assets say NEW_RED over it.
#
# Named, not counted. A count-only gate (`if nfail != 6`) is the NARROW shape: fix one known
# red, acquire one genuine new one, and the total is still six -- the gate passes and the
# regression ships. The composer computes the identity difference but only RECORDS it; it
# never raises. Nothing between the measurement and the tag was checking identity.
SEAT_KNOWN = (
    "test_bc_wave.py::test_chat_face_monochrome_one_accent_plus_state_marks",
    "test_bc_wave.py::test_profile_row_retired",
    "test_doctor_button.py::test_transport_discovers_only_the_running_owner_and_tracks_reconnection",
    "test_failure_trail.py::test_dead_verb_hidden",
    "test_j1_token_liveness.py::test_connected_keyed_engine_is_live_then_working_then_live",
    "test_j2_token_face.py::test_face_counts_an_ollama_task",
)
SEAT_KNOWN_REDS = len(SEAT_KNOWN)  # derived, so the count and the list cannot disagree

# The files this release ships. A hand-written add list cannot notice its own omission,
# so step_commit asserts the tree is clean AFTER staging -- anything missing from this
# list is still modified at that point, and that is what makes the omission loud.
ADD = [
    "VERSION", "pyproject.toml", "python/synapse/__init__.py", "CLAUDE.md",
    "README.md", "CHANGELOG.md", "docs/getting-started/installation.md",
    "docs/releases/v%s.md" % V,
    "harness/notes/readme_check.py",
    "tests/test_memory_seam_defects.py",
    "harness/notes/release-%s" % V,
    "harness/notes/release-5.73.0/repair_assets.py",
]

STEPS = ["preflight", "build", "qual", "suites", "gates", "compose", "commit", "tag", "push", "publish", "verify"]

os.makedirs(N, exist_ok=True)


def log(m):
    line = time.strftime("%H:%M:%S ") + m
    print(line, flush=True)
    io.open(LOG, "a", encoding="utf-8", newline="\n").write(line + "\n")


def run(args, cwd=REPO, check=True, env=None, timeout=None, out=None):
    e = dict(os.environ, PYTHONPATH=os.path.join(cwd, "python"), PYTHONIOENCODING="utf-8")
    if env:
        e.update(env)
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=e, timeout=timeout)
    if out:
        io.open(out, "w", encoding="utf-8", newline="\n").write((r.stdout or "") + (r.stderr or ""))
    if check and r.returncode:
        raise SystemExit("FAILED (%d): %s\n%s\n%s" % (r.returncode, " ".join(map(str, args)),
                                                      (r.stdout or "")[-3000:], (r.stderr or "")[-2000:]))
    return r


def read(p):
    return io.open(p, encoding="utf-8", errors="replace").read()


def summary(path):
    """pytest's own summary line, with or without the ==== bars (hytest prints it bare)."""
    for line in reversed(read(path).splitlines()):
        t = line.strip()
        m = re.search(r"=+ (.*?) =+$", t) or re.match(
            r"^((?:\d+ (?:passed|failed|skipped|xfailed|xpassed|warnings?|errors?|deselected)(?:, )?)+.*in [\d.]+s.*)$", t)
        if m and ("passed" in m.group(1) or "failed" in m.group(1)):
            return m.group(1)
    raise SystemExit("no pytest summary line in " + path)


def hython_busy():
    return "hython.exe" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout


def count():
    return int(run([sys.executable, "-c",
                    "from synapse.mcp._tool_registry import TOOL_DEFS; print(len(TOOL_DEFS))"]
                   ).stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------- steps
def step_preflight():
    """Re-check what the absent bump step would have done."""
    s = run([sys.executable, "scripts/sync_version.py"]).stdout
    if "verdict=PASS" not in s or ("canonical=" + V) not in s:
        raise SystemExit("STOP: version surfaces do not conform to %s:\n%s" % (V, s))
    log("  six surfaces CONFORM at " + V)

    # The links the bump step would have rewritten. Asserted against the tree, because
    # "already done" is a claim and this is the check for it.
    rd = read(os.path.join(REPO, "README.md"))
    for what, needle, expect in (
        ("Setup download link", "releases/download/v%s/SYNAPSE-%s-Setup.exe" % (V, V), 1),
        ("SHA256SUMS link", "releases/download/v%s/SHA256SUMS.txt" % V, 1),
        ("release-notes link", "docs/releases/v%s.md" % V, 3),
        ("Latest tag line", "tags: v%s is Latest" % V, 1),
        ("New in block", "**New in %s**" % V, 1),
    ):
        n = rd.count(needle)
        if n != expect:
            raise SystemExit("STOP: README carries %d of the %s (expected %d, searched %r)"
                             % (n, what, expect, needle))
    if PREV[1:] in rd:
        raise SystemExit("STOP: README still mentions %s somewhere" % PREV[1:])
    for f in ("docs/releases/v%s.md" % V, "CHANGELOG.md"):
        if ("v%s" % V) not in read(os.path.join(REPO, f)):
            raise SystemExit("STOP: %s does not name v%s" % (f, V))
    if run(["git", "tag", "-l", "v" + V]).stdout.strip():
        raise SystemExit("STOP: tag v%s already exists" % V)
    log("  README surfaces, notes and changelog name v%s; tag is free" % V)
    log("  tool registry holds %d" % count())


def step_build():
    base = [sys.executable, "-B", "installer/build_windows.py", "--downloads", BUILD + r"\downloads",
            "--iscc", ISCC, "--output", OUT, "--moneta-bundle", MONETA, "--moneta-sha256", MONETA_SHA]
    run(base, out=os.path.join(N, "build-prod.log"), timeout=1800)
    run(base + ["--test-build"], out=os.path.join(N, "build-test.log"), timeout=1800)
    tr = OUTDIR + r"\SYNAPSE-%s-TestSetup.build.json" % V
    for kind in ("previous", "missing-dependency"):
        run([sys.executable, "-B", "installer/create_test_fixture.py", "--build-report", tr,
             "--iscc", ISCC, "--kind", kind], out=os.path.join(N, "fixture-%s.log" % kind), timeout=1800)
    p = json.load(open(OUTDIR + r"\SYNAPSE-%s-Setup.build.json" % V))
    t = json.load(open(tr))
    assert t["payload"]["sha256"] == p["payload"]["sha256"], "TestSetup payload differs from Setup"
    log("  built; payload %s id %s" % (p["payload"]["sha256"][:12], p["payload"]["payload_id"]))


def step_qual():
    root = OUT + r"\qual-%d" % (os.getpid() % 100000)
    r = run([sys.executable, "-B", "installer/test_executable.py", "--expected-version", V,
             "--setup", OUTDIR + r"\SYNAPSE-%s-TestSetup.exe" % V,
             "--previous-setup", OUTDIR + r"\SYNAPSE-fixture-previous.exe",
             "--broken-setup", OUTDIR + r"\SYNAPSE-fixture-missing-dependency.exe",
             "--root", root, "--hfs", HFS], check=False, timeout=2400,
            out=os.path.join(N, "qual-raw.txt"))
    # The raw log is written to its OWN file and never overwritten. Previously the filtered
    # summary was written back over the raw output BEFORE the gate below raised, so a failing
    # qualification reported "not 19/19" while the traceback explaining WHY had already been
    # deleted. The failure survived; its diagnosis did not. Evidence is cheap to keep and
    # impossible to recover, and the moment you most want it is the moment the gate fires.
    lines = [l for l in read(os.path.join(N, "qual-raw.txt")).splitlines() if ": " in l]
    io.open(os.path.join(N, "qual-stdout.txt"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    ok = sum(1 for l in lines if l.endswith(": PASS"))
    log("  qualification %d/%d PASS, exit %d" % (ok, len(lines), r.returncode))
    if r.returncode or ok != 19 or ok != len(lines):
        raise SystemExit("STOP: qualification not 19/19 exit 0")


def step_suites():
    # The README receipt first: it is cheap, it gates the page this release is about,
    # and its log is a producer the composer parses.
    run([sys.executable, "harness/notes/readme_check.py"], check=False, timeout=600,
        out=os.path.join(N, "readme-receipt-%s.txt" % V))
    rr = read(os.path.join(N, "readme-receipt-%s.txt" % V))
    if not re.search(r"^RESULT: PASS\b", rr, re.M):
        raise SystemExit("STOP: the README receipt did not pass:\n" + rr[-1500:])
    log("  readme receipt: PASS")

    run([sys.executable, "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider"],
        check=False, timeout=3600, out=os.path.join(N, "suite-%s.txt" % V))
    log("  stock: " + summary(os.path.join(N, "suite-%s.txt" % V)))

    for _ in range(120):
        if not hython_busy():
            break
        time.sleep(30)
    else:
        raise SystemExit("STOP: hython busy for an hour; seat suite cannot run alone")
    run([sys.executable, ".synapse/hytest.py", "tests/panel", "-q", "-p", "no:cacheprovider"],
        check=False, timeout=2400, env={"SYNAPSE_HYTHON": HYTHON},
        out=os.path.join(N, "seat-%s.txt" % V))
    log("  seat:  " + summary(os.path.join(N, "seat-%s.txt" % V)))

    run([sys.executable, "-m", "pytest", "installer/tests", "-q", "-p", "no:cacheprovider"],
        check=False, timeout=1800, out=os.path.join(N, "installer-tests-%s.txt" % V))
    log("  inst:  " + summary(os.path.join(N, "installer-tests-%s.txt" % V)))
    # No gate here: `gates` is the next step in STEPS and judges these same logs.
    # Measurement and judgement are deliberately separate -- see step_gates.


def step_gates():
    """Judge the three suite logs. Separated from running them ON PURPOSE.

    The gate below was `if "failed" in stock` in every previous cut -- a substring
    test. This is the first release to ship xfails, and "xfailed" CONTAINS "failed",
    so that gate would have stopped this cut on its own five expected xfails and
    reported them as failures. It was caught while the suites were mid-flight, when
    the running process already held the broken copy in memory.

    Splitting judgement from measurement is the fix that outlives this bug: the logs
    are expensive and deterministic, the verdict is cheap and was wrong. Re-judging
    must not mean re-measuring, or the pressure is always to skip the gate rather
    than re-run the suite.
    """
    stock = summary(os.path.join(N, "suite-%s.txt" % V))
    log("  gate stock: " + stock)
    # NOT `if "failed" in stock`. That is a substring test, and "xfailed" CONTAINS
    # "failed" -- so the gate every previous cut used would have stopped this release
    # on its own five expected xfails and called them failures. It never fired before
    # because no previous cut shipped an xfail. Match the count pytest actually prints:
    # "(\d+) failed" cannot match "5 xfailed", because the character before "failed"
    # there is "x", not the space the pattern requires.
    _fail = re.search(r"(\d+) failed", stock)
    _err = re.search(r"(\d+) errors?\b", stock)
    if (_fail and int(_fail.group(1))) or (_err and int(_err.group(1))):
        raise SystemExit("STOP: stock suite has failures or errors: " + stock)

    # A FLOOR ON PASSED. Zero failures is not the same as the suite having run. A collection
    # error that loses half the tests reports "4000 passed, 0 failed" and sails through every
    # check above -- the suite that did not run cannot fail. The floor is DERIVED from the
    # previous release's own log, not typed here, so it tracks the tree instead of going
    # stale; 5% of slack absorbs ordinary churn while still catching a suite that vanished.
    _prev_log = os.path.join(REPO, "harness/notes/release-%s/suite-%s.txt" % (PREV[1:], PREV[1:]))
    _now = int(re.search(r"(\d+) passed", stock).group(1))
    if os.path.exists(_prev_log):
        _then = int(re.search(r"(\d+) passed", summary(_prev_log)).group(1))
        log("  gate stock: %d passed vs %d at %s (%+d)" % (_now, _then, PREV, _now - _then))
        if _now < _then * 0.95:
            raise SystemExit("STOP: stock suite collected %d passing tests against %d at %s. "
                             "A drop that size is a collection error, not test removal -- the "
                             "suite that did not run cannot fail. Read the log before shipping."
                             % (_now, _then))
    else:
        log("  gate stock: no %s baseline log on disk; floor UNCHECKED (%d passed)" % (PREV, _now))
    # This release ADDS five xfails. An xfail that silently became an XPASS would mean a
    # pinned defect was fixed without deleting its marker, which is the whole point of
    # strict -- but strict only turns THAT test red, and a reader of the summary should
    # not have to work it out. Assert the shape the notes describe.
    if "xpassed" in stock:
        raise SystemExit("STOP: stock suite reports xpassed -- a NON-strict xfail passed. In this "
                         "release that is the concurrency race probe (the only non-strict one), so "
                         "either the race stopped reproducing or the marker is now wrong: " + stock)
    # Note what this does NOT catch, so nobody reads it as covering the strict four: pytest
    # reports a STRICT xfail that passes as `failed`, not `xpassed`. That case is caught by
    # the failure gate above, not here. A guard whose message names a case it cannot see is
    # how a dead check keeps looking alive.
    seat_path = os.path.join(N, "seat-%s.txt" % V)
    seat = summary(seat_path)
    log("  gate seat:  " + seat)
    m = re.search(r"(\d+) failed", seat)
    nfail = int(m.group(1)) if m else 0

    # Identity first, then count. The count alone is the narrow shape: fix one known red,
    # acquire one genuine new one, and the total is unchanged while a regression ships.
    measured = sorted({f.split("tests/panel/")[-1].split(" ")[0]
                       for f in re.findall(r"^FAILED (\S+)", read(seat_path), re.M)})
    new = sorted(set(measured) - set(SEAT_KNOWN))
    fixed = sorted(set(SEAT_KNOWN) - set(measured))
    if new:
        raise SystemExit("STOP: seat suite has %d red(s) NOT in the baseline: %s. Either a real "
                         "regression, or the baseline is stale -- both stop the tag. Do not "
                         "publish a NEW_RED you have not read." % (len(new), new))
    if fixed:
        raise SystemExit("STOP: %d baseline seat red(s) now PASS: %s. That is good news and it "
                         "still stops the cut: shipping a baseline that over-states the reds is "
                         "how v5.72.0 and v5.73.0 published a regression that had already "
                         "happened. Update SEAT_KNOWN here and in compose_assets.py, then "
                         "re-run." % (len(fixed), fixed))
    if nfail != len(measured):
        raise SystemExit("STOP: the seat summary says %d failed but %d FAILED lines were parsed "
                         "(%s). The log and its own summary disagree." % (nfail, len(measured), seat))
    log("  gate seat:  %d red(s), all named in the baseline, none newly passing" % len(measured))
    # The installer suite was measured and only LOGGED -- the stock suite got a gate, this
    # got a print. A red installer suite would ship inside an asset whose own
    # installer_unit_checks field quotes the red summary while status says PASS. Same test
    # the stock gate uses, applied to the log it was already reading.
    inst = summary(os.path.join(N, "installer-tests-%s.txt" % V))
    log("  gate inst:  " + inst)
    _if = re.search(r"(\d+) failed", inst)
    _ie = re.search(r"(\d+) errors?", inst)
    if (_if and int(_if.group(1))) or (_ie and int(_ie.group(1))):
        raise SystemExit("STOP: installer unit suite has failures or errors: " + inst)
    rr = read(os.path.join(N, "readme-receipt-%s.txt" % V))
    if not re.search(r"^RESULT: PASS\b", rr, re.M):
        raise SystemExit("STOP: the README receipt did not pass")
    log("  all suite gates pass")


def step_compose():
    run(["git", "rev-parse", "HEAD"], out=os.path.join(N, "build-rev.txt"))
    run([sys.executable, os.path.join(N, "compose_assets.py")])

    for _p in (os.path.join(REPO, "docs/releases/v%s.md" % V),
               os.path.join(N, "RELEASE_v%s.md" % V)):
        _left = re.findall(r"@@[A-Za-z0-9_]+@@", read(_p))
        if _left:
            raise SystemExit("STOP: %s still carries unfilled slots %s -- compose reported success "
                             "without substituting. Do not tag." % (_p, sorted(set(_left))))
    log("  placeholders: none left in any composed document")

    # THE CLAIM GATE. When the notes claim the product is unchanged, verify that against
    # the real diff before tagging. Only the version file may differ.
    _notes = read(os.path.join(REPO, "docs/releases/v%s.md" % V)).lower()
    _claims_docs_only = any(t in _notes for t in
                            ("documentation only", "documentation and tests only", "documentation patch",
                             "the product is unchanged", "nothing about the product changed"))
    # Compare PREV to the WORKING TREE, not to HEAD.
    #
    # `git diff PREV HEAD` is the natural-looking spelling and it is vacuous here. compose
    # runs BEFORE the release commit, and the v5.73.0 tag sits on HEAD (it was created at
    # the asset-repair commit that followed the release commit, so `git log v5.73.0..HEAD`
    # is empty). The gate therefore asked "what changed between the tag and the tag",
    # got nothing, found nothing unexpected in nothing, and reported that it had verified
    # the documentation-only claim. A gate whose input is empty has not passed; it has
    # abstained, and printing PASS for an abstention is the more dangerous of the two.
    #
    # The claim is about what this release SHIPS, and at compose time that is the working
    # tree. Omitting the second ref diffs PREV against the working tree, which is the
    # question actually being asked.
    _delta = [f for f in run(["git", "diff", "--name-only", PREV, "--", "python", "installer"],
                             check=False).stdout.split() if f.strip()]
    log("  product delta vs %s (working tree): %s" % (PREV, ", ".join(_delta) if _delta else "none"))
    if not _delta:
        raise SystemExit("STOP: the product delta against %s is EMPTY. Every release bumps the "
                         "version string in python/synapse/__init__.py, so an empty delta means "
                         "this gate is reading the wrong pair of trees, not that nothing changed. "
                         "Refusing to pass vacuously." % PREV)
    if not _claims_docs_only:
        raise SystemExit("STOP: this cut expects a documentation-and-tests-only claim in the notes "
                         "and did not find one. Either the notes changed or the release did.")
    _unexpected = [f for f in _delta if f != "python/synapse/__init__.py"]
    if _unexpected:
        raise SystemExit("STOP: the notes call this documentation-and-tests-only, but %s changed "
                         "under python/ or installer/. Either the notes are wrong or the release "
                         "is. Do not tag." % _unexpected)
    log("  claim gate: notes say documentation-and-tests-only and the diff agrees (%d file)" % len(_delta))


def step_commit():
    run(["git", "add"] + ADD)
    _dirty = [f for f in run(["git", "diff", "--name-only"]).stdout.split() if f.strip()]
    if _dirty:
        raise SystemExit("STOP: these tracked files are modified and NOT staged, so the tag would "
                         "not contain them while the release notes may describe them: %s. Stage "
                         "them or revert them. Do not tag." % _dirty)

    # THE UNTRACKED BLIND SPOT. The check above sees tracked-modified files only, and
    # scripts/tag_release.py filters worktree lines on `not ln.startswith('??')` -- so BOTH
    # gates are blind to an untracked file that belongs to the release and was left out of
    # ADD. Two independent gates, one shared blind spot, which is worse than one gate: the
    # second looks like corroboration and is not.
    #
    # docs/releases/v5.74.0.md is untracked right now and the README links it three times.
    # Drop it from ADD and both gates print clean, the tag is created, and the public README
    # carries three 404s -- which is precisely how v5.73.0 shipped a 404 download button.
    #
    # So check the thing that actually matters: every relative link in the documents this
    # release publishes must resolve to a path that is IN THE INDEX after staging.
    _idx = set(run(["git", "ls-files"]).stdout.split())
    _missing = []
    for _f in ("README.md", "CHANGELOG.md", "docs/releases/v%s.md" % V):
        _s = read(os.path.join(REPO, _f))
        for _t in re.findall(r"\]\(([^)#:]+?)(?:#[^)]*)?\)", _s):
            if _t.startswith(("http", "mailto", "#")):
                continue
            _p = _t.lstrip("./").replace("\\", "/")
            if not _p:
                continue
            if _p not in _idx and not any(k.startswith(_p.rstrip("/") + "/") for k in _idx):
                _missing.append("%s -> %s" % (_f, _p))
    if _missing:
        raise SystemExit("STOP: these documents link to paths that are NOT in the index, so the "
                         "tag would publish a page pointing at files it does not contain: %s. "
                         "Add them to ADD. Do not tag." % sorted(set(_missing)))
    log("  link gate: every relative link in the release documents resolves inside the index")
    msg = os.path.join(N, "commit-msg.txt")
    io.open(msg, "w", encoding="utf-8", newline="\n").write(
        "release: v%s -- the page, and the receipt that guards it\n"
        "\n"
        "Documentation and tests only; the registry holds %d. The one file that\n"
        "differs under python/ since %s is the version string, and this cut's claim\n"
        "gate verifies that against the real diff before it will allow a tag.\n"
        "\n"
        "The three README diagrams were drawn with unstyled nodes, which inherit the\n"
        "host theme -- so their ink and fill were whatever the visitor's GitHub was\n"
        "set to, and on one of the two settings they were hard to read. Every node\n"
        "now declares a dark fill, white text and an outline. The page itself is\n"
        "rebuilt to the ADHD convention CLAUDE.md has required of it all along:\n"
        "nothing was cut, the length moved into whitespace.\n"
        "\n"
        "The page now has a receipt that can fail. readme_check.py resolves every\n"
        "diagram node against the declared colours, checks the version strings\n"
        "against VERSION and the tool count against the module the page names as its\n"
        "producer, and carries two deliberately bad diagrams it must reject. The\n"
        "version it replaces could not fail: it printed the numbers without letting\n"
        "either reach the exit code, and asserted a README claim the README does not\n"
        "make. It proves the SOURCE declares those colours -- no browser is invoked,\n"
        "so the render stays UNKNOWN rather than verified.\n"
        "\n"
        "tests/test_memory_seam_defects.py converts a review's predictions into\n"
        "claims that execute. Four strict xfails pin reproduced defects and turn the\n"
        "suite red if one is fixed without deleting its marker; one race probe cannot\n"
        "honestly be strict; three permanent guards pin facts two agents disagreed\n"
        "about. Pinned is not fixed -- none of the four is repaired here.\n"
        "\n"
        "This cut also finished the previous one. v5.73.0 was published and marked\n"
        "Latest with zero assets attached, so the README download button returned 404\n"
        "while all four assets sat qualified on the build machine. They are attached\n"
        "now, after three provenance fields that named the pre-bump commit and a\n"
        "baseline copied forward from v5.70.0 were corrected against evidence: the\n"
        "repair re-proves the shipped payload byte-identical to the tag before it\n"
        "will write anything.\n"
        "\n"
        "Measured alone, in order -- README receipt, stock, seat, installer unit,\n"
        "19/19 qualification; numbers in docs/releases/v%s.md and\n"
        "harness/notes/release-%s/.\n"
        "\n"
        "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>\n"
        % (V, count(), PREV, V, V))
    # The pre-commit capability fence refuses a staged VERSION unless SYNAPSE_GATE_C=1.
    # Typed once, here, scoped to this command.
    run(["git", "commit", "-q", "-F", msg], env={"SYNAPSE_GATE_C": "1"})
    log("  " + run(["git", "log", "--oneline", "-1"]).stdout.strip())


def step_tag():
    log("  " + run([sys.executable, "scripts/tag_release.py", "--check-only"]).stdout.strip().splitlines()[-1])
    r = run([sys.executable, "scripts/tag_release.py"])
    log("  " + r.stdout.strip().splitlines()[-1])
    # Pass 2. Re-run the payload comparison against the TAG rather than the working tree --
    # the pre-commit run answered "does the payload match what we are about to commit", and
    # this one answers "does the payload match what we just tagged", which is the claim the
    # published asset actually makes. Then re-stamp, so source_revision is the RELEASE sha
    # and not the pre-bump one. Skipping this step is exactly how v5.73.0's assets went out
    # naming 85c8fe29.
    run([sys.executable, os.path.join(N, "payload_vs_tag.py"), "v" + V])
    log("  payload re-compared against the tag")
    run([sys.executable, os.path.join(N, "compose_assets.py")])
    _pub = json.load(open(OUTDIR + r"\SYNAPSE-%s-Setup.public-build.json" % V))
    _tagged = run(["git", "rev-list", "-n", "1", "v" + V]).stdout.strip()
    if _pub["source_revision"] != _tagged:
        raise SystemExit("STOP: composed source_revision %s is not the tagged revision %s"
                         % (_pub["source_revision"][:12], _tagged[:12]))
    log("  assets re-stamped at the tagged revision " + _tagged[:12])


def step_push():
    r = run(["git", "push", "origin", "master", "v" + V], env={"SYNAPSE_GATE_C": "1"}, timeout=600)
    log("  pushed: " + (r.stdout + r.stderr).strip().splitlines()[-1])


def step_publish():
    body = os.path.join(N, "release-body.md")
    notes = read(os.path.join(REPO, "docs/releases/v%s.md" % V))
    # DERIVED from the note's own H1, never a literal -- a hardcoded title once carried
    # the PREVIOUS release's headline against this release's notes, and nothing checked.
    _h1 = notes.split("\n", 1)[0].strip()
    _m = re.match(r"^#\s+v(\d+\.\d+\.\d+)\s*[-\u2014]\s*(.+)$", _h1)
    if not _m or _m.group(1) != V:
        raise SystemExit("STOP: the release note's H1 %r does not name v%s, so the publish title "
                         "cannot be derived from it. Do not publish." % (_h1, V))
    title = "v%s \u2014 %s" % (V, _m.group(2).strip())
    log("  title derived from the note: " + title)
    io.open(body, "w", encoding="utf-8", newline="\n").write(
        notes.split("\n", 1)[1].strip() + "\n\nFull notes: "
        "[`docs/releases/v%s.md`](https://github.com/JosephOIbrahim/Synapse/blob/v%s/docs/releases/v%s.md)\n"
        % (V, V, V))
    # NEVER chained with the gate: gh mints its own tag if the gate refused and none exists.
    run(["gh", "release", "create", "v" + V, "--latest",
         "--title", title,
         "--notes-file", body,
         OUTDIR + r"\SYNAPSE-%s-Setup.exe" % V, OUTDIR + r"\SHA256SUMS.txt",
         OUTDIR + r"\SYNAPSE-%s-Setup.public-build.json" % V, OUTDIR + r"\installer-verification.json"],
        timeout=1800)
    log("  published v" + V)


def step_verify():
    d = json.loads(run(["gh", "api", "repos/JosephOIbrahim/Synapse/releases/latest"]).stdout)
    assert d["tag_name"] == "v" + V and not d["draft"], d["tag_name"]
    names = sorted(a["name"] for a in d["assets"])
    log("  latest=%s assets=%s" % (d["tag_name"], names))
    assert len(names) == 4, names
    url = ("https://github.com/JosephOIbrahim/Synapse/releases/download/v%s/SYNAPSE-%s-Setup.exe" % (V, V))
    tmp = os.path.join(N, "served-setup.exe")
    run(["curl", "-sL", "-o", tmp, url], timeout=1800)
    served = hashlib.sha256(open(tmp, "rb").read()).hexdigest()
    qualified = read(OUTDIR + r"\SHA256SUMS.txt").split()[0]
    os.remove(tmp)
    log("  served %s == qualified %s : %s" % (served[:12], qualified[:12], served == qualified))
    if served != qualified:
        raise SystemExit("STOP: served installer does not match the qualified build")
    # The defect this whole cut opened with: a release published with no assets, whose
    # README button 404s. Check the button, not just the API.
    # Every asset, not two. RELEASE_CARD.md says "every asset 200"; checking the two most
    # obvious ones is how a release ships three good files and one that 404s.
    for a in d["assets"]:
        if a.get("state") != "uploaded" or not a.get("size"):
            raise SystemExit("STOP: asset %s is state=%s size=%s -- present in the API listing "
                             "is not the same as downloadable."
                             % (a["name"], a.get("state"), a.get("size")))
    log("  all %d assets report state=uploaded with non-zero size" % len(d["assets"]))

    # Read back the BODY that was published. v5.71.0's public body carries six double-encoded
    # em dashes that its source file does not -- introduced in transit, by a tool, and never
    # noticed because nothing after publish ever read what publish produced. This release's
    # body carries four em dashes, so it has the same vector.
    _local = read(os.path.join(N, "release-body.md"))
    _remote = d.get("body") or ""
    if _remote.strip() != _local.strip():
        _bad = sum(1 for ch in _remote if ch in "Ãâ€")
        raise SystemExit("STOP: the published body is not byte-identical to release-body.md "
                         "(%d local chars vs %d remote, %d suspicious encoding chars). "
                         "Do not leave a mangled body public." % (len(_local), len(_remote), _bad))
    log("  published body is byte-identical to release-body.md (%d chars)" % len(_local))

    for asset in [a["name"] for a in d["assets"]]:
        u = "https://github.com/JosephOIbrahim/Synapse/releases/download/v%s/%s" % (V, asset)
        code = run(["curl", "-sI", "-L", "-o", os.devnull, "-w", "%{http_code}", u],
                   timeout=600).stdout.strip()
        log("  %s -> %s" % (asset, code))
        if code != "200":
            raise SystemExit("STOP: %s is not served (%s)" % (asset, code))
    log("  RELEASE COMPLETE -- v%s is Latest and its download button resolves" % V)


if __name__ == "__main__":
    a = sys.argv[1:]
    start = a[a.index("--from") + 1] if "--from" in a else "preflight"
    seq = STEPS[STEPS.index(start):]
    if "--until" in a:
        seq = seq[:seq.index(a[a.index("--until") + 1]) + 1]
    log("cut v%s: %s" % (V, seq))
    for s in seq:
        log("== " + s)
        globals()["step_" + s]()
    log("cut done")
