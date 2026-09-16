"""Cut v5.73.0 end to end, unattended, per docs/RELEASE_CARD.md.

build -> qualify -> suites -> notes -> commit -> gate -> tag -> push -> publish -> verify

Every number in the notes and the three composed assets is PARSED from a measured
artifact on disk; nothing is retyped (Law 2). The script stops at the first failure
with the evidence, leaving the tree committed-or-clean, and never forces anything.

  python harness/notes/release-5.73.0/cut.py [--from STEP] [--skip-wait]

Steps: wait, bump, notes, build, qual, suites, compose, commit, tag, push, publish, verify
"""
import io
import json
import os
import re
import subprocess
import sys
import time

V = "5.73.0"
PREV = "v5.72.0"
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
SEAT_KNOWN_REDS = 6  # v5.72.0 shipped six, named with a measured baseline diff in
                     # harness/notes/release-5.71.0/SEAT_REDS.md (the baseline was cut there and
                     # has not moved). A seventh stops the cut.

STEPS = ["wait", "bump", "notes", "build", "qual", "suites", "compose", "commit", "tag", "push", "publish", "verify"]

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

def write(path, text):
    # The caller computes `text` BEFORE this is entered, so a file can never be
    # truncated ahead of its own read. The assert kills the bug class outright:
    # io.open(x,'w').write(read(x)...) evaluates open() first, empties the file,
    # then reads '' back. That silently zeroed CLAUDE.md, README.md and
    # installation.md on the 2026-09-15 16:14 run -- caught pre-commit, nothing shipped.
    assert text and text.strip(), "refusing to write an empty " + path
    io.open(path, "w", encoding="utf-8", newline="\n").write(text)

def summary(path):
    """pytest's own summary line, with or without the ==== bars (hytest prints it bare)."""
    for line in reversed(read(path).splitlines()):
        t = line.strip()
        m = re.search(r"=+ (.*?) =+$", t) or re.match(
            r"^((?:\d+ (?:passed|failed|skipped|warnings?|errors?|deselected)(?:, )?)+.*in [\d.]+s.*)$", t)
        if m and ("passed" in m.group(1) or "failed" in m.group(1)):
            return m.group(1)
    raise SystemExit("no pytest summary line in " + path)

def hython_busy():
    return "hython.exe" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout

def fill_slots(text, pairs, what):
    """Substitute @@SLOT@@ tokens with measured values. Zero or one each.

    Zero is legal and expected: re-running `compose` finds the work already done,
    and a fill that insisted on its token would stop a re-run for being correct.
    Two is not legal -- it means the template grew a duplicate and one of them
    would reach the reader raw. Absent and duplicated are the two states a bare
    `.replace()` cannot tell apart, which is how both of this release's fence
    defects got through it.
    """
    for tok, val in pairs:
        n = text.count(tok)
        if n > 1:
            raise SystemExit("STOP: %s carries %d copies of %s; one would ship unfilled. "
                             "Do not tag." % (what, n, tok))
        if n:
            text = text.replace(tok, val)
    return text

# ---------------------------------------------------------------- notes text
RELEASE_NOTES = """# v{V} - Readable, and the fences that failed

Six merged branches. The tool registry holds {COUNT}.

## What an artist gets

- **The quiet text is legible.** Captions, hints and metadata move to a grey that clears AA on
  every surface it can land on. The input placeholder is the biggest single jump - 3.43:1 to
  6.15:1 - and it is the first thing you read in an empty panel. It is a named token now, rather
  than whatever Qt painted at half alpha.
- **Disabled text deliberately stays below that floor, and it is the one reversal in the set.**
  Raising it to AA resolved `disabled` to the SAME ink as `tertiary` on all 32 sampled host seeds,
  turning four live rules into no-ops at 1.000:1 - a pill, the model-liveness mark, a footer link,
  and the trivial step in the network trace. WCAG 2.1 exempts text inside an inactive component,
  so the exemption is stated in the tokens instead of a floor being claimed, and the four marks
  read again. Two ACTIVE labels that had been borrowing the inert ink now name tertiary.
- **UI labels get the weight they were already asking for.** The label role drew Regular because
  the code had no branch for Medium, so the weight the bundled face ships was being discarded.
  About 25% more ink on the same letterforms at the same size.
- **The context breadcrumb shrinks from 15px to 11px** - four rungs down to where it always
  claimed to be. Five rules emitted their size in points where the rest of the sheet uses pixels,
  so the *smallest* token in the system was rendering at exactly the size of the *largest*.
- **The panel says each thing once.** Empty state, composer placeholder and footer labels stop
  repeating what the row above already said.
- **Stop gets its hover back**, inside the single action family rather than by reintroducing a
  second hue.

## For the repository

Three fences were repaired, and every one of them was found by running it rather than reading it:

- `pre-push` swept the *upstream* release commits into every rebased branch's range, so any branch
  rebased after a release was refused on a file it never touched - and the only way through was
  the override, on routine work.
- The asset composer read a hardcoded version, wrote to a path that had not existed since v5.70.1,
  and guarded its own work with a spelling its templates never emit. It reported success while
  substituting nothing.
- Fillable slots now use a delimiter that prose cannot contain, so a release note can document the
  token names without tripping the gate that checks for them.

A farm test also stopped waiting on a file *existing* and started waiting on it *parsing*.

## Verification scope

Measured on this build, alone, in this order.

- Stock suite: **@@STOCK@@**
- Panel seat suite, hython 22.0.400 offscreen: **@@SEAT@@**
- Installer unit checks: **@@INST@@**
- Installer qualification: **@@QUAL@@** against the isolated TestSetup, which carries the same
  payload sha256 as the published Setup (@@PAYLOAD@@).

## Update

`SYNAPSE-{V}-Setup.exe` upgrades in place and preserves projects, memory, credentials and custom
files - that path is one of the qualification checks.

- The installer is **unsigned**; verify it against `SHA256SUMS.txt`.
- Running from source? Pull `v{V}`. A live Houdini session holds the modules it already loaded
  until the panel is reloaded or Houdini restarts.

## Still unfinished

- **Two named greys are now nearly one grey.** Raising the quiet end to AA pushed tertiary up
  against secondary: #A0A0A0 and #9E9E9E on the headless seed, **1.0245:1** apart, and byte
  identical on 2 of 32 sampled host seeds. That is forced arithmetic, not a choice: with secondary
  fixed and the floor at 4.5 there is no room left down there. Value can no longer
  carry the quiet rung - form has to, using tracking, caps and the mono family the design system
  already owns and is not spending. Awaiting a ruling.
- **The panel renders far smaller than its host.** Measured on a 192-DPI seat, Houdini's own UI
  font is 27px while the panel's body token is 12px. The type scale is also flatter than it looks:
  of 15 visible text elements, 13 are the same size. Both are measured in
  `harness/design_review/2026-09-15/READABILITY.md`; neither is changed here.
- **The transcript reads 28.6 characters per line** against a comfortable band of 45-75, because
  message bodies render in monospace with added tracking. The remedy is measured and costs the
  artist no pane width. It is a design decision and has not been taken.
- Six panel seat tests remain red; none is new.
"""

CHANGELOG_ENTRY = """## v{V} - Readable, and the fences that failed

*Six branches. The quiet end of the text ramp is legible for the first time - captions, hints,
metadata, disabled labels and the input placeholder all clear AA on every surface they can land on,
with the placeholder going 3.43:1 to 6.15:1. UI labels finally draw the Medium the bundled face
ships, which the code was discarding for want of a branch. The context breadcrumb drops 15px to
11px, a four-rung inversion caused by five rules emitting points where the sheet uses pixels. On the
repository side three fences were repaired, each found by running it: pre-push swept upstream
release commits into every rebased branch's range; the asset composer read a hardcoded version,
wrote to a path dead since v5.70.1, and guarded with a spelling its templates never emit; and
fillable slots now use a delimiter prose cannot contain. Measured alone, in order: stock @@STOCK@@;
seat @@SEAT@@; installer units @@INST@@; qualification @@QUAL@@. Stated and unresolved: raising the
quiet end left secondary and tertiary 1.0245:1 apart, so form rather than value has to carry that
rung from here, while disabled was deliberately returned below the floor under WCAG's
inactive-component exemption after the raise collapsed four live state marks to 1.000:1. Full notes: `docs/releases/v{V}.md`.*

"""

INTERNAL = """# v{V} - how it was cut

Six branches, through a CI-gated train, then the standard ritual.

## What this cut has that the last one did not

Three fences, all repaired after being caught in use rather than in review:

1. `pre-push` now gates what a push ADDS rather than what its range sweeps in. The two-dot range
   broke on any force-push after a rebase, sweeping in the upstream release commits and refusing
   branches that touch no protected path.
2. The composer reads VERSION from the repo, targets the dated notes subdirectory, and checks the
   exact keys it was meant to substitute in the text it just built.
3. Slots are an uppercase name between `@@` delimiters. The gate matches that delimiter. Both
   were forced by measurement: stripping code spans before scanning misses a real slot, and not
   stripping fires on prose.

## Measured

- Stock suite: @@STOCK@@
- Seat suite (hython 22.0.400, `SYNAPSE_HYTHON` pinned, alone): @@SEAT@@
- Installer unit checks: @@INST@@
- Installer qualification: @@QUAL@@

The seat suite and the stock suite share a log file and must not run at the same time; they ran
alone, in that order.

## The count that matters

Four defects were found today in safety code written today. Guards are the least-exercised code in
the tree and they carry the same defect rate as what they guard. Every one was found by executing
it against the input it was written for - never by reading it.
"""

# ---------------------------------------------------------------- steps
def step_wait():
    for _ in range(240):
        st = json.loads(run(["gh", "pr", "view", "94", "--json", "state,mergeStateStatus"]).stdout)
        if st["state"] == "MERGED":
            log("  #94 merged"); break
        if st["state"] == "CLOSED":
            raise SystemExit("STOP: #94 was closed, not merged")
        time.sleep(30)
    else:
        raise SystemExit("STOP: #94 still open after 2h")
    run(["git", "pull", "-q", "--ff-only", "origin", "master"])
    log("  master " + run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip())

def step_bump():
    io.open(os.path.join(REPO, "VERSION"), "w", encoding="utf-8", newline="\n").write(V)
    log("  " + run([sys.executable, "scripts/sync_version.py", "--write"]).stdout.strip().splitlines()[-1])
    P = PREV[1:]                       # "5.72.0" -- the version being replaced

    # Every search string below is DERIVED from PREV, and every replacement declares how
    # many times it must fire. The v5.73.0 script was generated from v5.72.1's by a global
    # "5.72.0" -> "5.73.0" replace, which also rewrote the SEARCH strings here: each one
    # then looked for the version it was about to write, matched nothing, changed nothing,
    # and this step still logged success. Same class as the composer fix in #105. A
    # declared count turns that silent no-op into a stop.
    def sub_n(text, old, new, what, expect):
        n = text.count(old)
        if n != expect:
            raise SystemExit("STOP: step_bump expected %d occurrence(s) of %s (searched %r), found %d. "
                             "Do not continue -- the bump would silently change nothing."
                             % (expect, what, old, n))
        return text.replace(old, new) if n else text

    rd = os.path.join(REPO, "README.md")
    s = read(rd)
    s = sub_n(s, "releases/download/%s/SYNAPSE-%s-Setup.exe" % (PREV, P),
                 "releases/download/v%s/SYNAPSE-%s-Setup.exe" % (V, V), "the Setup download link", 1)
    s = sub_n(s, "releases/download/%s/SHA256SUMS.txt" % PREV,
                 "releases/download/v%s/SHA256SUMS.txt" % V, "the SHA256SUMS link", 0)
    s = sub_n(s, "docs/releases/%s.md" % PREV, "docs/releases/v%s.md" % V, "the release-notes link", 3)
    s = sub_n(s, "tags: %s is Latest" % PREV, "tags: v%s is Latest" % V, "the Latest tag line", 1)
    block = ("**New in %s** — the quiet text is legible, and three fences hold.\n\n"
             "- Captions, hints and metadata clear AA; the empty panel's placeholder goes 3.43:1 to 6.15:1.\n"
             "- UI labels finally draw the Medium the bundled face ships — about 25%% more ink.\n"
             "- The context breadcrumb drops 15px to 11px: five rules were emitting points, not pixels.\n"
             "- Three repository fences were repaired, each one caught failing in use.\n\n"
             "[Release details and limits \u2192](docs/releases/v%s.md)\n\n" % (V, V))
    pat = r"\*\*New in %s\*\*.*?\n\n(?=\*\*Still development work)" % re.escape(P)
    hits = len(re.findall(pat, s, flags=re.S))
    if hits != 1:
        raise SystemExit("STOP: step_bump expected 1 'New in %s' block in README, found %d" % (P, hits))
    s = re.sub(pat, lambda _m: block, s, flags=re.S)
    write(rd, s)

    inst = os.path.join(REPO, "docs/getting-started/installation.md")
    si = read(inst)
    si = sub_n(si, P, V, "the version in installation.md", 5)  # 3 lines, 5 occurrences
    write(inst, si)
    log("  README + installation.md surfaces -> " + V + " (from " + PREV + ")")

def count():
    return int(run([sys.executable, "-c",
                    "from synapse.mcp._tool_registry import TOOL_DEFS; print(len(TOOL_DEFS))"]).stdout.strip().splitlines()[-1])

def step_notes():
    n = count()
    for f in ("CLAUDE.md", "README.md"):
        p = os.path.join(REPO, f)
        sp = re.sub(r"(\b)(\d{3})( (?:MCP )?tools\b)", lambda m: m.group(1) + str(n) + m.group(3), read(p))
        write(p, sp)
    io.open(os.path.join(REPO, "docs/releases/v%s.md" % V), "w", encoding="utf-8", newline="\n").write(
        RELEASE_NOTES.replace("{V}", V).replace("{COUNT}", str(n)))
    io.open(os.path.join(N, "RELEASE_v%s.md" % V), "w", encoding="utf-8", newline="\n").write(
        INTERNAL.replace("{V}", V).replace("{PREV_NUM}", PREV[1:]).replace("{MONETA_SHA}", MONETA_SHA).replace("{COUNT}", str(n)))
    cp = os.path.join(REPO, "CHANGELOG.md")
    s = read(cp)
    anchor = "## v5.72.0 -"   # hyphen: that heading uses one, not an em dash
    assert anchor in s, "changelog anchor missing"
    io.open(cp, "w", encoding="utf-8", newline="\n").write(
        s.replace(anchor, CHANGELOG_ENTRY.replace("{V}", V).replace("{COUNT}", str(n)) + anchor, 1))
    log("  notes drafted with placeholders; tool count %d" % n)

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
            out=os.path.join(N, "qual-stdout.txt"))
    lines = [l for l in read(os.path.join(N, "qual-stdout.txt")).splitlines() if ": " in l]
    io.open(os.path.join(N, "qual-stdout.txt"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    ok = sum(1 for l in lines if l.endswith(": PASS"))
    log("  qualification %d/%d PASS, exit %d" % (ok, len(lines), r.returncode))
    if r.returncode or ok != 19 or ok != len(lines):
        raise SystemExit("STOP: qualification not 19/19 exit 0")

def step_suites():
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
    if "failed" in summary(os.path.join(N, "suite-%s.txt" % V)):
        raise SystemExit("STOP: stock suite has failures")
    # The notes assert "the known five reds, none new" about the seat suite. Until now
    # nothing checked that -- step_suites gated on the stock suite only and merely logged
    # the seat and installer numbers, so a sixth red would have published a claim that
    # contradicts the number printed beside it. Verify the assertion instead of making it.
    seat = summary(os.path.join(N, "seat-%s.txt" % V))
    m = re.search(r"(\d+) failed", seat)
    nfail = int(m.group(1)) if m else 0
    if nfail != SEAT_KNOWN_REDS:
        raise SystemExit("STOP: seat suite reports %d failed; the notes claim %d known reds "
                         "(%s). Re-read the seat log before shipping." % (nfail, SEAT_KNOWN_REDS, seat))

def step_compose():
    run(["git", "rev-parse", "HEAD"], out=os.path.join(N, "build-rev.txt"))
    # DERIVED from PREV, never a literal. A literal here is the same failure the composer
    # itself was just fixed for: a version sweep over a copied-forward script rewrote this
    # to point at THIS release's own directory, which does not exist yet.
    src = os.path.join(REPO, "harness/notes/release-%s/compose_assets.py" % PREV[1:])
    dst = os.path.join(N, "compose_assets.py")
    # EVERY search string names the SOURCE release's literals, DERIVED from PREV.
    # They were literals naming THIS release's own -- "release-5.73.0",
    # "output-5.73.0" -- which occur nowhere in the file being copied, so both
    # `.replace()` calls were silent no-ops on the 2026-09-15 19:04 run. The copy
    # would have kept BUILD pointed at output-5.72.0 while VERSION (read from the
    # file, never retyped) said 5.73.0: a 5.73.0 build report json.load-ed out of
    # the 5.72.0 directory -- FileNotFoundError, and, had that file existed, 5.73.0
    # assets written over the shipped v5.72.0 ones and the ARCHIVED
    # release-5.72.0/RELEASE_v5.72.0.md filled in. A sweep that finds nothing looks
    # exactly like one that needs nothing, so both anchors are asserted now.
    #
    # Two replacements are deliberately ABSENT, and naming why is the point: the
    # predecessor carried four, and the two dead ones are what made the live two
    # look plausible. A sweep of four that half-works reads like a sweep that works.
    #
    #   `VERSION = "..."` -- the composer reads VERSION from the repo; it has never
    #   carried that assignment.
    #
    #   `"v5.70.0"` -- that quoted literal occurs nowhere in the source. Every
    #   5.70.0 in the file sits inside a larger string, chiefly
    #   `"product_change_since_v5.70.0"`: a fixed receipt SCHEMA KEY, not a moving
    #   version. The same replacement was carried in 5.71.0, 5.72.0 and 5.72.1 and
    #   was dead in all of them for the same reason. The baseline is pinned on
    #   purpose; sweeping it would silently rename the key and the audit that reads
    #   it. If a future baseline genuinely moves, move it here and prove the key
    #   moved in the composer too -- do not let a sweep do it by pattern.
    _copy = read(src)
    for _old, _new in (("release-" + PREV[1:], "release-" + V),
                       ("output-" + PREV[1:], "output-" + V)):
        if _old not in _copy:
            raise SystemExit("STOP: the composer copy-forward cannot find %r in %s -- the source "
                             "shape moved and this sweep would change nothing. Fix the copy. "
                             "Do not tag." % (_old, src))
        _copy = _copy.replace(_old, _new)

    # THE SCOPE CLAUSE. The stock number in this receipt is only reproducible on a
    # machine whose environment does not carry Anthropic credentials, and the 2026-09-15
    # run proved that the hard way: launched from an agent harness, the suite reported
    # 30 failed / 9555 passed with every red the same `ModelAccessDenied` raised by
    # `model_access._sdk_state`. `make_anthropic_client` builds its client with an
    # explicit api_key, but the SDK *also* reads `ANTHROPIC_AUTH_TOKEN` from the
    # environment, so the client arrives carrying an auth_token the guard did not
    # authorize -- and the check refuses the client the constructor just built. Unset
    # the variable and the same 30 tests pass; master's CI is green on all four
    # required contexts for exactly that reason. The scope line is the one place a
    # reader learns that, so the measurement names its own environment rather than
    # publishing a number that looks false to whoever re-runs it.
    _scope_old = '"Local Windows, stock Python 3.14, vendored SDK inactive. Run alone."'
    _scope_new = ('"Local Windows, stock Python 3.14, vendored SDK inactive. Run alone, with '
                  'ANTHROPIC_* unset -- the SDK reads ANTHROPIC_AUTH_TOKEN from the environment '
                  'and the guarded-lane check then refuses the client it was just handed."')
    if _scope_old not in _copy:
        raise SystemExit("STOP: the composer copy-forward cannot find the stock-suite scope string "
                         "in %s, so the receipt would publish the number without its environment. "
                         "Fix the copy. Do not tag." % src)
    _copy = _copy.replace(_scope_old, _scope_new)
    io.open(dst, "w", encoding="utf-8", newline="\n").write(_copy)
    log("  " + run([sys.executable, dst]).stdout.strip().splitlines()[-1])

    # THE CHANGELOG HOLE. The entry is written back at step_notes -- before build,
    # before any number exists -- so it carries the same @@SLOT@@ tokens the notes
    # do, and it sat in neither the composer's fill loop (two files, both under
    # docs/ and harness/) nor the gate below. v5.71.0 and v5.72.0 published raw
    # {PLACEHOLDER} text exactly this way; this entry was drafted with @@STOCK@@ in
    # it, one step from the public changelog. Fill it from the verification receipt
    # the composer just wrote, so the number in the changelog is the number in the
    # document published beside the installer -- one producer, by construction.
    _receipt = os.path.join(OUTDIR, "installer-verification.json")
    if not os.path.exists(_receipt):
        raise SystemExit("STOP: compose left no %s, so the CHANGELOG entry cannot be filled "
                         "and would carry its slots to the reader. Do not tag." % _receipt)
    _ver = json.loads(read(_receipt))
    _cp = os.path.join(REPO, "CHANGELOG.md")
    write(_cp, fill_slots(read(_cp), [
        ("@@STOCK@@", _ver["local_stock_suite"]["summary"]),
        ("@@SEAT@@", _ver["installed_houdini"]["summary"]),
        ("@@INST@@", _ver["installer_unit_checks"]["summary"]),
        ("@@QUAL@@", _ver["compiled_installer"]["summary"]),
    ], "CHANGELOG.md"))
    log("  changelog entry filled from " + os.path.basename(_receipt))
    # v5.71.0 and v5.73.0 both PUBLISHED raw {PLACEHOLDER} text under the sentence
    # "Measured on this build, alone, in this order." The composer had a guard; it
    # inspected the previous release's already-filled file and passed. Fixing a
    # producer and checking a producer are different acts. Check it here too.
    import glob as _glob
    for _p in (os.path.join(REPO, "docs/releases/v%s.md" % V),
               os.path.join(N, "RELEASE_v%s.md" % V),
               _cp):
        _t = read(_p)
        _left = sorted(set(re.findall(r"@@[A-Z_]{3,}@@", _t)))
        # Matches the SLOT delimiter, never a generic uppercase-in-braces shape. The
        # shape version fired on this very document: a release note describing the
        # placeholder bug writes the token names in prose, and {PLACEHOLDER} matched
        # too. Stripping code spans instead misses real slots - v5.72.0 wrote one of
        # its five inside backticks. @@ is a delimiter prose does not contain.
        if _left:
            raise SystemExit("STOP: %s still carries unfilled placeholders %s -- the compose step "
                             "reported success without substituting. Do not tag." % (_p, sorted(set(_left))))
    log("  placeholders: none left in any composed document")

    # THE CLAIM GATE. v5.72.1's first draft said python/ and installer/ were
    # "byte-identical" to the previous release and told the reader to run
    #   git diff --stat <PREV> <this> -- python installer
    # to confirm it. That command REFUTES it: the bump step rewrites __init__.py on
    # every release, so python/ is never byte-identical. It was caught by a human
    # running the command the document recommends - which is an argument for
    # recommending one, and a worse argument for leaving the check to a human.
    # A claim that invites its own disproof is worse than a vague claim.
    #
    # So: when the notes CLAIM this is a documentation-only patch, verify that claim
    # against the real diff before tagging. Only the version file may differ.
    _notes = read(os.path.join(REPO, "docs/releases/v%s.md" % V))
    _claims_docs_only = any(t in _notes.lower() for t in
                            ("documentation only", "documentation patch", "the product is unchanged",
                             "nothing about the product changed"))
    _delta = [f for f in run(["git", "diff", "--name-only", PREV, "HEAD", "--", "python", "installer"],
                             check=False).stdout.split() if f.strip()]
    log("  product delta vs %s: %s" % (PREV, ", ".join(_delta) if _delta else "none"))
    if _claims_docs_only:
        _unexpected = [f for f in _delta if f != "python/synapse/__init__.py"]
        if _unexpected:
            raise SystemExit("STOP: the notes call this documentation-only, but %s changed under "
                             "python/ or installer/. Either the notes are wrong or the release is. "
                             "Do not tag." % _unexpected)
        log("  claim gate: notes say documentation-only and the diff agrees (%d file)" % len(_delta))

def step_commit():
    run(["git", "add", "VERSION", "pyproject.toml", "python/synapse/__init__.py", "CLAUDE.md",
         "README.md", "CHANGELOG.md", "docs/getting-started/installation.md",
         "docs/releases/v%s.md" % V, "python/synapse/panel/synapse_panel.py",
         "harness/notes/release-%s" % V])
    # THE HAND-LIST HOLE. This cut's tree carries a real product fix -- the panel footer's
    # shrink-to-fit -- and the add list above did not name its file. Nothing would have said so:
    # the fix is green in every probe run, and the notes, the changelog and the commit message
    # all describe it. The tag would have shipped a release note describing a change the commit
    # did not contain, and a checkout of that tag would not reproduce the J5 green that
    # qualified it. A hand-written add list cannot notice its own omission -- the file it forgot
    # is still modified either way. So the omission is made loud instead: after staging, the
    # working tree must be clean. A throwaway that must survive the commit gets named in the add
    # list or reverted, which is the point -- what ships stops being an implicit consequence of
    # which files happened to be edited.
    _dirty = [f for f in run(["git", "diff", "--name-only"]).stdout.split() if f.strip()]
    if _dirty:
        raise SystemExit("STOP: these tracked files are modified and NOT staged, so the tag would "
                         "not contain them while the release notes describe them: %s. Stage them "
                         "or revert them. Do not tag." % _dirty)
    msg = os.path.join(N, "commit-msg.txt")
    io.open(msg, "w", encoding="utf-8", newline="\n").write(
        "release: v%s -- readable, and the fences that failed\n\n"
        "Six branches merged through a CI-gated train; the registry holds %d.\n"
        "The panel's quiet text clears AA: captions, hints and metadata move to a\n"
        "named grey, and the empty panel's placeholder -- the first thing an artist\n"
        "reads -- goes 3.43:1 to 6.15:1. UI labels draw the Medium the bundled face\n"
        "ships, which the code had no branch for: about 25%% more ink on the same\n"
        "letterforms. The context breadcrumb drops 15px to 11px after five rules were\n"
        "found emitting their size in points where the rest of the sheet uses pixels.\n"
        "Three repository fences were repaired, each caught failing in use: pre-push\n"
        "swept the upstream release commits into every rebased branch's range; the\n"
        "asset composer read a hardcoded version, wrote to a path dead since v5.70.1,\n"
        "and guarded with a spelling its templates never emit; fillable slots now use\n"
        "a delimiter prose cannot contain.\n\n"
        "Measured alone, in order -- stock, seat, installer unit, 19/19 qualification;\n"
        "numbers in docs/releases/v%s.md and harness/notes/release-%s/.\n\n"
        "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>\n" % (V, count(), V, V))
    # #94 landed the pre-commit capability fence: a staged VERSION is refused
    # unless SYNAPSE_GATE_C=1. The refutation on that PR found finalize.ps1
    # committing VERSION ungated and tagging regardless, which would put the
    # tag on an un-bumped HEAD. Same trap, same override, typed once here.
    run(["git", "commit", "-q", "-F", msg], env={"SYNAPSE_GATE_C": "1"})
    log("  " + run(["git", "log", "--oneline", "-1"]).stdout.strip())

def step_tag():
    log("  " + run([sys.executable, "scripts/tag_release.py", "--check-only"]).stdout.strip().splitlines()[-1])
    r = run([sys.executable, "scripts/tag_release.py"])
    log("  " + r.stdout.strip().splitlines()[-1])
    run([sys.executable, os.path.join(N, "compose_assets.py")])  # re-stamp with the release sha

def step_push():
    r = run(["git", "push", "origin", "master", "v" + V], env={"SYNAPSE_GATE_C": "1"}, timeout=600)
    log("  pushed: " + (r.stdout + r.stderr).strip().splitlines()[-1])

def step_publish():
    body = os.path.join(N, "release-body.md")
    notes = read(os.path.join(REPO, "docs/releases/v%s.md" % V))
    # DERIVED from the note's own H1, never a literal. The title here was hardcoded and had been
    # carried forward unread -- "One scale, one family, and fences that hold" is v5.72.0's
    # headline, against a v5.73.0 note titled "Readable, and the fences that failed". The GitHub
    # listing would have contradicted the document it links to, and nothing checked. Same shape
    # as the composer's hardcoded version, in the one step that publishes.
    _h1 = notes.split("\n", 1)[0].strip()
    _m = re.match(r"^#\s+v(\d+\.\d+\.\d+)\s*[-—]\s*(.+)$", _h1)
    if not _m or _m.group(1) != V:
        raise SystemExit("STOP: the release note's H1 %r does not name v%s, so the publish title "
                         "cannot be derived from it. Do not publish." % (_h1, V))
    title = "v%s — %s" % (V, _m.group(2).strip())
    log("  title derived from the note: " + title)
    io.open(body, "w", encoding="utf-8", newline="\n").write(
        notes.split("\n", 1)[1].strip() + "\n\nFull notes: "
        "[`docs/releases/v%s.md`](https://github.com/JosephOIbrahim/Synapse/blob/v%s/docs/releases/v%s.md)\n" % (V, V, V))
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
    import hashlib
    url = "https://github.com/JosephOIbrahim/Synapse/releases/download/v%s/SYNAPSE-%s-Setup.exe" % (V, V)
    tmp = os.path.join(N, "served-setup.exe")
    run(["curl", "-sL", "-o", tmp, url], timeout=1800)
    served = hashlib.sha256(open(tmp, "rb").read()).hexdigest()
    qualified = read(OUTDIR + r"\SHA256SUMS.txt").split()[0]
    os.remove(tmp)
    log("  served %s == qualified %s : %s" % (served[:12], qualified[:12], served == qualified))
    if served != qualified:
        raise SystemExit("STOP: served installer does not match the qualified build")
    log("  RELEASE COMPLETE — v%s is Latest" % V)

if __name__ == "__main__":
    a = sys.argv[1:]
    start = a[a.index("--from") + 1] if "--from" in a else "bump"
    seq = STEPS[STEPS.index(start):]
    if "--skip-wait" in a and "wait" in seq:
        seq.remove("wait")
    if "--until" in a:
        seq = seq[:seq.index(a[a.index("--until") + 1]) + 1]
    log("cut v%s: %s" % (V, seq))
    for s in seq:
        log("== " + s)
        globals()["step_" + s]()
    log("cut done")
