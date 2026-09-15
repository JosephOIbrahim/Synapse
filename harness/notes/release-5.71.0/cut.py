"""Cut v5.71.0 end to end, unattended, per docs/RELEASE_CARD.md.

build -> qualify -> suites -> notes -> commit -> gate -> tag -> push -> publish -> verify

Every number in the notes and the three composed assets is PARSED from a measured
artifact on disk; nothing is retyped (Law 2). The script stops at the first failure
with the evidence, leaving the tree committed-or-clean, and never forces anything.

  python harness/notes/release-5.71.0/cut.py [--from STEP] [--skip-wait]

Steps: wait, bump, notes, build, qual, suites, compose, commit, tag, push, publish, verify
"""
import io
import json
import os
import re
import subprocess
import sys
import time

V = "5.71.0"
PREV = "v5.70.1"
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
SEAT_KNOWN_REDS = 6  # five from v5.70.1 + the #85 transport-contract red, both named
                     # with a measured baseline diff in SEAT_REDS.md (Joe ruled: ship, documented)  # v5.70.1 shipped five; the notes say "none new" -- gated above
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

# ---------------------------------------------------------------- notes text
RELEASE_NOTES = """# v{V} — The farm, the receipt, and a bridge that says no

Ten merged branches. The tool registry goes 128 -> {COUNT}.

## What an artist gets

- **A render farm you can leave running.** Durable TOPs render jobs with an artist
  render workspace: submit, watch, cancel. Seven new tools (`synapse_farm_submit`, `_jobs`, `_job`, `_inspect`, `_cancel`,
  `_prepare`, `_capabilities`) joining the existing
  `synapse_render_farm_status` / `_cancel`, a `/render` command, and a Render button
  in the panel footer.
- **Undo, stated before you need it.** Every mutating handler already computed the
  answer to *what does one Ctrl+Z reverse?* as an undo-group label and threw it away.
  It now travels with the result and reaches the panel. Before this release a
  repo-wide search for `Ctrl+Z`, `undoable` or `can be undone` across every `.py`
  returned **zero** artist-facing strings.
- **The bridge says no instead of remembering.** A message typed while the bridge was
  down used to be accepted, spun on, queued with no signal, and replayed into whatever
  scene was open later. It now refuses at send time, says so, and leaves your words in
  the box. Nothing is queued; nothing replays.
- **`houdini_layout_network`** — bounded native layout: position, colour, comment and
  network boxes only, one labelled undo group, and it refuses before touching a box you
  made yourself. `dry_run` shows the plan.
- **`synapse_insert_cache`** — the action half of the cache advisor: an undoable
  boundary insertion behind the review gate, bound to the decision that asked for it.
  Ships **dark**: set `SYNAPSE_CACHE_ADVISOR_ENABLED` to try it.
- **Scoped memory.** `synapse_decide` and `synapse_recall` take `scope=scene|project|all`.

## For the repository

- **Rulings now land somewhere.** `scripts/ingest_rulings.py` reads a roster and a reply
  (`A1 ratify`), validates every id against the roster, and records each ruling through
  the existing decision board with who, when, and the roster's sha as evidence. An
  unknown id refuses and writes nothing. Before this, answering a design call changed
  nothing in the tree.
- **A session-id collision fixed** in the audit log: two `AuditLog` instances in one
  process could share a session id after garbage collection. Now they cannot, with the
  failing-then-passing test the original branch never had.
- The 2026-09-15 branch triage, harness review, first-principles audit and panel design
  crit are in the tree under `harness/notes/` and `harness/design_review/`.

## Verification scope

Measured on this build, alone, in this order.

- Stock suite: **{STOCK}**
- Panel seat suite, hython 22.0.400 offscreen: **{SEAT}** — five known reds plus ONE NEW, named and diagnosed in `harness/notes/release-5.71.0/SEAT_REDS.md`.
- Installer unit checks: **{INST}**
- Installer qualification: **{QUAL}** against the isolated TestSetup, which carries the
  same payload sha256 as the published Setup (`{PAYLOAD}`).

## Update

`SYNAPSE-{V}-Setup.exe` upgrades in place and preserves projects, memory, credentials
and custom files — that path is one of the qualification checks.

- The installer is **unsigned**; verify against `SHA256SUMS.txt`.
- Running from source? Pull `v{V}`. A live Houdini session holds the modules it already
  loaded until the panel is reloaded or Houdini restarts.
- `installer-verification.json` on the release carries the full evidence, including what
  was not run.

## Still unfinished

- **Six panel seat tests are red, and one is new.** The new one: #85 changed
  `_MCPLocalClient.available` to keep a cached port when discovery is lost instead of
  clearing it. It costs one failed request on an error path, is self-healing, and nothing
  renders the flag — but whether the resilient or the strict contract is right is an open
  ruling. Of the five others, two are recorded design conflicts awaiting a ruling and three
  are named and undiagnosed. Baseline diff, diagnosis and measured blast radius:
  `harness/notes/release-5.71.0/SEAT_REDS.md`.
- **The suite's skip population is not stable** — 21 tests are disabled by a symbol
  missing from an out-of-tree dependency and no gate here can see it
  (`harness/notes/SUITE_FLOOR_IS_NOT_STABLE.md`).
- The seven farm tools have no curated panel labels yet; they fall back to derived ones.
- The panel's emergency halt fires but does not survive a frozen main thread.
- Code signing, a clean Windows machine and native wizard qualification remain separate.
- The panel design crit ranked 19 changes; none of them ships here. Nineteen design
  calls still wait on a ruling (`harness/design_review/2026-09-15/CRIT.md`).
"""

CHANGELOG_ENTRY = """## v{V} — The farm, the receipt, and a bridge that says no

*2026-09-15.* Published as **Latest** with a qualified Windows Setup ({QUAL}). Ten
branches merged; the registry goes 128 -> {COUNT} tools.

**Artist-facing.** Durable TOPs render jobs with an artist render workspace (seven farm
tools, `/render`, a footer button). The **Undo Receipt**: every mutating handler already
computed its undo-group label and discarded it — it now travels with the result and
reaches the panel, where a repo-wide grep for `Ctrl+Z|undoable|can be undone` had
returned zero artist-facing strings. The **bridge-down send guard**: a message typed
while the bridge is down is refused at send time with the text kept in the box, instead
of being queued silently and replayed into a later scene. `houdini_layout_network`
(bounded native layout, one undo group, refuses an artist's own boxes).
`synapse_insert_cache` (undoable boundary insertion behind the review gate, shipped dark
behind `SYNAPSE_CACHE_ADVISOR_ENABLED`). Scoped memory on `synapse_decide` / `_recall`.

**Repository.** `scripts/ingest_rulings.py` makes a design ruling land in the decision
board instead of nowhere — ids validated against the roster, unknown ids refuse and write
nothing. An `AuditLog` session-id collision after GC is fixed, with the failing-then-passing
test the original branch never had. The 2026-09-15 branch triage, harness review,
first-principles audit and panel design crit are in the tree.

**Measured alone, in order:** stock {STOCK}; seat suite {SEAT} (five known + ONE NEW, diagnosed in
`harness/notes/release-5.71.0/SEAT_REDS.md`);
installer unit {INST}; qualification {QUAL}. See the
[release notes](docs/releases/v{V}.md).

"""

INTERNAL = """# v{V} — how it was cut

Ten branches merged through a scripted train (`harness/notes/closeout-2026-09-15/merge_train.py`):
each PR rebased onto the moving master, the tool count recomputed from `len(TOOL_DEFS)` rather
than typed, CI gated on the test matrix only (CodeRabbit advisory), squash-merged in order.
Two needed a hand rebase: #84 (registry + RBAC union against #83's new tool) and #85 (the
handler mix-in line, plus both count lines).

## Order of operations

1. All ten merged to master first; `VERSION` {PREV_NUM} -> {V} after, propagated by
   `scripts/sync_version.py --write`; README surfaces hand-edited.
2. Moneta bundle digest checked BEFORE the build: `{MONETA_SHA}`
   — byte-identical to the reviewed, authorized 1.2.0rc1 bundle.
3. **Build, then qualify, then commit.** Stock suite, seat suite and installer unit checks ran
   serially and alone. The notes were written from the measured numbers after the build, so
   `docs/` in the payload is one edit behind the tag; `python/` and `installer/` are the tag's.
4. `scripts/tag_release.py`, then the Gate C push scoped to one command, then `gh release create`
   in a separate command — never chained with the gate.

## Measured

- Stock suite: {STOCK}
- Seat suite (hython 22.0.400, `SYNAPSE_HYTHON` pinned, alone): {SEAT}
- Installer unit checks: {INST}
- Installer qualification: {QUAL}
- Payload sha256 {PAYLOAD}; payload_id {PAYLOAD_ID}
- Tool count {COUNT} (`len(TOOL_DEFS)`, written by script)

## Traps that still hold

The seat suite and the stock suite share `~/.synapse/logs/synapse.log` and must not run at the
same time; both numbers above were measured alone, in sequence. `python` on this shell is 3.14,
not the repo's 3.13 — the stock suite runs on 3.14 with the vendored SDK inactive; the seat suite
runs on Houdini's 3.13.10; the two are not comparable and are not compared. Two Houdini 22 builds
are installed; the hytest shim was pinned to 22.0.400.

## What is NOT behind this Latest

- The installer is unsigned; no clean Windows machine; no native wizard qualification.
- The upgrade path used a synthetic prior payload, not a historical released installer.
- Six panel seat tests are red. Five are v5.70.1's exactly; one is NEW -- #85 changed
  `_MCPLocalClient.available` to keep a cached port when discovery is lost. Names, the
  re-measured v5.70.1 baseline diff, the diagnosis and the measured blast radius are in
  `SEAT_REDS.md`. Which contract is right is an open ruling, not a defect call.
- The suite's skip population is still not stable.
- The seven farm tools have no curated `activity.py` labels — derived labels only.
- PLAN Stop 5 blockers 1, 2 and 4 (build-pin vs installed 22.0.429, an uncollected harness file,
  a root-level `mcp_tools_render.py`) were out of the rebase's scope and are untouched.
- No live-Houdini introspection beyond the seat suite.
"""

# ---------------------------------------------------------------- steps
def step_wait():
    for _ in range(240):
        st = json.loads(run(["gh", "pr", "view", "85", "--json", "state,mergeStateStatus"]).stdout)
        if st["state"] == "MERGED":
            log("  #85 merged"); break
        if st["state"] == "CLOSED":
            raise SystemExit("STOP: #85 was closed, not merged")
        time.sleep(30)
    else:
        raise SystemExit("STOP: #85 still open after 2h")
    run(["git", "pull", "-q", "--ff-only", "origin", "master"])
    log("  master " + run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip())

def step_bump():
    io.open(os.path.join(REPO, "VERSION"), "w", encoding="utf-8", newline="\n").write(V)
    log("  " + run([sys.executable, "scripts/sync_version.py", "--write"]).stdout.strip().splitlines()[-1])
    rd = os.path.join(REPO, "README.md")
    s = read(rd)
    s = s.replace("releases/download/" + PREV + "/SYNAPSE-5.70.1-Setup.exe",
                  "releases/download/v%s/SYNAPSE-%s-Setup.exe" % (V, V))
    s = s.replace("releases/download/" + PREV + "/SHA256SUMS.txt", "releases/download/v%s/SHA256SUMS.txt" % V)
    s = s.replace("docs/releases/v5.70.1.md", "docs/releases/v%s.md" % V)
    s = s.replace("tags: v5.70.1 is Latest", "tags: v%s is Latest" % V)
    s = re.sub(r"\*\*New in 5\.70\.1\*\*.*?\n\n(?=\*\*Still development work)",
               "**New in %s** — the farm, the receipt, and a bridge that says no.\n\n"
               "- Durable TOPs render jobs with an artist render workspace: submit, watch, cancel.\n"
               "- Every change now says what one Ctrl+Z reverses, before you need it.\n"
               "- A message typed while the bridge is down is refused, not queued and replayed later.\n"
               "- New tools: bounded network layout, and an undoable cache insertion (dark by default).\n\n"
               "[Release details and limits →](docs/releases/v%s.md)\n\n" % (V, V), s, flags=re.S)
    write(rd, s)
    inst = os.path.join(REPO, "docs/getting-started/installation.md")
    si = read(inst).replace("5.70.1", V)
    write(inst, si)
    log("  README + installation.md surfaces -> " + V)

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
    anchor = "## v5.70.1 —"
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
    src = os.path.join(REPO, "harness/notes/release-5.70.1/compose_assets.py")
    dst = os.path.join(N, "compose_assets.py")
    io.open(dst, "w", encoding="utf-8", newline="\n").write(
        read(src).replace('VERSION = "5.70.1"', 'VERSION = "%s"' % V)
                 .replace("release-5.70.1", "release-" + V)
                 .replace("output-5.70.1", "output-" + V)
                 .replace('"v5.70.0"', '"%s"' % PREV))
    log("  " + run([sys.executable, dst]).stdout.strip().splitlines()[-1])

def step_commit():
    run(["git", "add", "VERSION", "pyproject.toml", "python/synapse/__init__.py", "CLAUDE.md",
         "README.md", "CHANGELOG.md", "docs/getting-started/installation.md",
         "docs/releases/v%s.md" % V, "harness/notes/release-%s" % V])
    msg = os.path.join(N, "commit-msg.txt")
    io.open(msg, "w", encoding="utf-8", newline="\n").write(
        "release: v%s -- the farm, the receipt, and a bridge that says no\n\n"
        "Ten branches merged through a scripted train; the registry goes 128 -> %d.\n"
        "Durable TOPs render jobs with an artist render workspace; the Undo Receipt\n"
        "(every handler already computed its undo label and discarded it); a bridge-down\n"
        "send guard that refuses instead of queueing and replaying; bounded network\n"
        "layout; an undoable cache insertion shipped dark; scoped memory; and a ruling\n"
        "ingester so a design call lands in the decision board instead of nowhere.\n\n"
        "Measured alone, in order -- stock, seat, installer unit, 19/19 qualification;\n"
        "numbers in docs/releases/v%s.md and harness/notes/release-%s/.\n\n"
        "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>\n" % (V, count(), V, V))
    run(["git", "commit", "-q", "-F", msg])
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
    io.open(body, "w", encoding="utf-8", newline="\n").write(
        notes.split("\n", 1)[1].strip() + "\n\nFull notes: "
        "[`docs/releases/v%s.md`](https://github.com/JosephOIbrahim/Synapse/blob/v%s/docs/releases/v%s.md)\n" % (V, V, V))
    run(["gh", "release", "create", "v" + V, "--latest",
         "--title", "v%s — The farm, the receipt, and a bridge that says no" % V,
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
    start = a[a.index("--from") + 1] if "--from" in a else "wait"
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
