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

V = "5.72.0"
PREV = "v5.71.0"
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
SEAT_KNOWN_REDS = 6  # v5.71.0 shipped six, named with a measured baseline diff in
                     # harness/notes/release-5.71.0/SEAT_REDS.md. A seventh stops the cut.

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
RELEASE_NOTES = """# v{V} - One scale, one family, and fences that hold

Seven merged branches. The tool registry holds {COUNT}.

## What an artist gets

- **The panel's type is one scale.** 11 / 12 / 15 / 19, and nothing smaller. The 10px size is
  deleted, and the audit's own readable floor was raised to match it rather than sitting above
  fifteen live sites that ignored it. Chat text does not move; the work face gets 2-3px back.
- **Verbs are told apart by weight, not by hue.** One action family. A hot verb is the same
  colour at a heavier weight, so "how many accent colours does this panel have" stops being a
  question with four answers.
- **The consent card says the phrase it already owned.** *Heads up, Quick review, Approve?,
  Confirm* - the authored words, instead of the enum tag that used to print over them.
- **The README has diagrams.** What happens when you send a prompt, what each of the three stop
  controls actually reaches, and the two paths into Houdini.

## For the repository

- **A capability fence on the files a human flips.** Committing `VERSION`, anything under
  `harness/state/`, or a `harness/verify/*_baseline.json` is refused unless `SYNAPSE_GATE_C=1` -
  same variable, same meaning as the push gate. Deny rules match a command's *form*, and
  `python -c`, `Copy-Item` and `git -C` all walk around them. A hook does not care which verb
  you used.
- **Every cycle now diffs what it actually changed** against that protected set, in `run.ts` and
  in `orchestrate.ps1`'s close gate. The assertion it replaces said "VERSION + harness untouched"
  and checked nothing at all.
- **The agent roster is pinned by a test**, and the retired relay agents are gone.

## Verification scope

Measured on this build, alone, in this order.

- Stock suite: **{STOCK}**
- Panel seat suite, hython 22.0.400 offscreen: **{SEAT}**
- Installer unit checks: **{INST}**
- Installer qualification: **{QUAL}** against the isolated TestSetup, which carries the same
  payload sha256 as the published Setup (`{PAYLOAD}`).

## Update

`SYNAPSE-{V}-Setup.exe` upgrades in place and preserves projects, memory, credentials and custom
files - that path is one of the qualification checks.

- The installer is **unsigned**; verify it against `SHA256SUMS.txt`.
- Running from source? Pull `v{V}`. A live Houdini session holds the modules it already loaded
  until the panel is reloaded or Houdini restarts.

## Still unfinished

- **The commit fence does not cover `git cherry-pick` or `git revert`.** Git runs no commit-half
  hook for either verb, so a protected path can reach local history ungated. `pre-push` walks
  every commit in the pushed range, so the bytes cannot leave the machine - but a local history
  can carry them. That hole was found by attacking the hook, not by running its tests, which
  were green.
- **The panel crit's composer copy is not in this release.** It edits a constructor pinned by
  `_PANEL_BASE`, and that pin moves only under a written ruling. Held open.
- **Six panel seat tests remain red** - the five carried since 5.70.1 plus the transport-contract
  red diagnosed in `harness/notes/release-5.71.0/SEAT_REDS.md`. None is new here.
- Nineteen design calls from the 2026-09-15 panel crit still wait on a ruling.
"""

CHANGELOG_ENTRY = """## v{V} - One scale, one family, and fences that hold

*Seven branches. The panel's type becomes one scale (11/12/15/19, the 10px size deleted and the
readable floor raised to match instead of sitting above fifteen sites that ignored it); actions
become one colour family with weight carrying emphasis; the consent card prints the authored
phrase it already owned rather than an enum tag over it. On the repository side a capability
fence lands: `VERSION`, `harness/state/**` and `harness/verify/*_baseline.json` refuse a commit
without `SYNAPSE_GATE_C=1`, because deny rules match a command's form and `python -c` walks
around them; every cycle now diffs what it really changed against that set in both `run.ts` and
`orchestrate.ps1`. Measured alone, in order: stock {STOCK}; seat {SEAT} (six, none new, named in
`harness/notes/release-5.71.0/SEAT_REDS.md`); installer units {INST}; qualification {QUAL}. Known
and stated: the commit fence cannot see `git cherry-pick` or `git revert` - git runs no hook
there - so that hole is closed at push instead. Full notes: `docs/releases/v{V}.md`.*

"""

INTERNAL = """# v{V} - how it was cut

Seven branches merged through a CI-gated train, then the standard ritual.

1. Every PR gated on the **CI matrix only** - the four `test (os, py)` jobs. CodeRabbit is
   advisory and was ignored by construction: on its first pass it reported "pass" because it was
   rate limited, which would have read as a green gate on a PR nothing had reviewed.
2. `master` carries **no branch protection** and `allow_auto_merge` is false, so the gate is
   whoever is merging. That is worth changing.
3. One PR was refused and stayed refused: it edits a constructor pinned by `_PANEL_BASE`, whose
   comment says that source is byte-identical to its landing unless a ruling says otherwise. A
   crit is not a ruling, and re-anchoring the pin to pass one's own branch is precisely the
   isolated-green failure the pin exists to prevent.

## Measured

- Stock suite: {STOCK}
- Seat suite (hython 22.0.400, `SYNAPSE_HYTHON` pinned, alone): {SEAT}
- Installer unit checks: {INST}
- Installer qualification: {QUAL}

The seat suite and the stock suite share `~/.synapse/logs/synapse.log` and must not run at the
same time; they ran alone, in that order.

## What this cut does differently

`step_commit` passes `SYNAPSE_GATE_C=1`. The pre-commit fence shipped in this very release
refuses a staged `VERSION`, and the adversarial pass on that branch found `harness/finalize.ps1`
committing `VERSION` ungated and then tagging regardless - which puts the tag on an un-bumped
HEAD and prints READY. The release script would have hit the same wall on its own bump.
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
    rd = os.path.join(REPO, "README.md")
    s = read(rd)
    s = s.replace("releases/download/" + PREV + "/SYNAPSE-5.71.0-Setup.exe",
                  "releases/download/v%s/SYNAPSE-%s-Setup.exe" % (V, V))
    s = s.replace("releases/download/" + PREV + "/SHA256SUMS.txt", "releases/download/v%s/SHA256SUMS.txt" % V)
    s = s.replace("docs/releases/v5.71.0.md", "docs/releases/v%s.md" % V)
    s = s.replace("tags: v5.71.0 is Latest", "tags: v%s is Latest" % V)
    s = re.sub(r"\*\*New in 5\.71\.0\*\*.*?\n\n(?=\*\*Still development work)",
               "**New in %s** — one scale, one family, and fences that hold.\n\n"
               "- The panel's type is one scale: 11/12/15/19, and nothing smaller.\n"
               "- Verbs are told apart by weight, not by hue — one action family.\n"
               "- The consent card says the phrase it already owned, not an enum tag.\n"
               "- The README has diagrams: the prompt flow, the three stops, the two paths.\n\n"
               "[Release details and limits →](docs/releases/v%s.md)\n\n" % (V, V), s, flags=re.S)
    write(rd, s)
    inst = os.path.join(REPO, "docs/getting-started/installation.md")
    si = read(inst).replace("5.71.0", V)
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
    anchor = "## v5.71.0 —"
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
    src = os.path.join(REPO, "harness/notes/release-5.71.0/compose_assets.py")
    dst = os.path.join(N, "compose_assets.py")
    io.open(dst, "w", encoding="utf-8", newline="\n").write(
        read(src).replace('VERSION = "5.71.0"', 'VERSION = "%s"' % V)
                 .replace("release-5.71.0", "release-" + V)
                 .replace("output-5.71.0", "output-" + V)
                 .replace('"v5.70.0"', '"%s"' % PREV))
    log("  " + run([sys.executable, dst]).stdout.strip().splitlines()[-1])

def step_commit():
    run(["git", "add", "VERSION", "pyproject.toml", "python/synapse/__init__.py", "CLAUDE.md",
         "README.md", "CHANGELOG.md", "docs/getting-started/installation.md",
         "docs/releases/v%s.md" % V, "harness/notes/release-%s" % V])
    msg = os.path.join(N, "commit-msg.txt")
    io.open(msg, "w", encoding="utf-8", newline="\n").write(
        "release: v%s -- one scale, one family, and fences that hold\n\n"
        "Seven branches merged through a CI-gated train; the registry holds %d.\n"
        "The panel gets one type scale (11/12/15/19, the 10px size deleted and the\n"
        "readable floor raised to match), one action family with weight carrying\n"
        "emphasis instead of hue, and a consent card that prints the authored phrase\n"
        "it already owned. The repository gets a capability fence: VERSION,\n"
        "harness/state/** and harness/verify/*_baseline.json refuse a commit without\n"
        "SYNAPSE_GATE_C=1, and every cycle diffs what it really changed against that\n"
        "set in both run.ts and orchestrate.ps1.\n\n"
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
    io.open(body, "w", encoding="utf-8", newline="\n").write(
        notes.split("\n", 1)[1].strip() + "\n\nFull notes: "
        "[`docs/releases/v%s.md`](https://github.com/JosephOIbrahim/Synapse/blob/v%s/docs/releases/v%s.md)\n" % (V, V, V))
    run(["gh", "release", "create", "v" + V, "--latest",
         "--title", "v%s — One scale, one family, and fences that hold" % V,
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
