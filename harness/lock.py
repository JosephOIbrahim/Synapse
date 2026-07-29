"""Leg locks - the writer for the lock file status.py has always read.

    python harness/lock.py acquire H2 --worktree .claude/worktrees/h2-requalify
    python harness/lock.py list
    python harness/lock.py heartbeat H2
    python harness/lock.py release H2
    python harness/lock.py reap                 # stale only, never a live lock

WHY THIS EXISTS
---------------
`harness/status.py:62` reads `harness/state/locks/*.lock` and reports a leg as
"running" when one is present. Nothing in the tree has ever written one. The
directory existed and was empty; the reader was the only reference to it.

So `state_of()` could never return "running", and the board printed `ready` for
a leg that had a live agent in its worktree. On 2026-07-26 a second run was
dispatched onto a leg that was already executing - two agents in one worktree,
HEAD moving under a reviewer via cherry-pick, a source file observed modified
then restored between two reads. That run halted itself and wrote the evidence
to `.claude/h2-halt/H2_HALT_EVIDENCE.md`. It was the second such collision.

Constitution Article V says every parallel agent gets its own git worktree.
That was prose. This is the enforcement.

DESIGN
------
- Acquire is atomic (`O_CREAT|O_EXCL`). Two processes racing cannot both win.
- A lock records the base commit it was taken against. The H2 defect was not
  only concurrency: that leg was dispatched onto a base that did not contain
  the fix it was told to probe. A finding that cannot name the tree it measured
  is unattributable.
- Reap NEVER steals a live lock. It requires BOTH a stale heartbeat AND a dead
  pid. When liveness cannot be determined, the holder is assumed ALIVE and the
  reap is refused - the safe direction, because a wrongly-stolen lock
  reproduces the exact defect this file exists to prevent.
- `--force` exists for the human, is never used by an agent, and records what
  it displaced in `reaped_from` so the steal is visible afterwards.

EXIT CODES
----------
    0  ok
    1  error (bad usage, unreadable state)
    3  held by another live holder  - callers branch on this
    4  stale lock present, reap refused because liveness is unknown
    5  the leg's worktree is not a real worktree - see worktree_guard.py

Law 1 - the condition under which this fails: `acquire` on a leg whose lock
file already exists and whose holder is alive exits 3 and writes nothing. If it
ever exits 0 in that situation, the fence is broken. Pinned by
`tests/test_harness_lock.py::test_second_acquire_is_refused`.
"""
import argparse, json, os, socket, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCKS = os.path.join(ROOT, "harness", "state", "locks")

# A holder that has not touched its lock in this long is a reap CANDIDATE.
# It is still not reaped unless its pid is also confirmed dead.
STALE_SECONDS = int(os.environ.get("SYNAPSE_LOCK_STALE_SECONDS", 45 * 60))


def git(*a):
    r = subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip() if r.returncode == 0 else ""


def pid_alive(pid):
    """True / False / None.

    None means undeterminable, and every caller must treat it as ALIVE. On
    Windows `os.kill(pid, 0)` is not a liveness probe - signal 0 is not
    supported and the call can terminate the target - so it is never used here.
    """
    if not isinstance(pid, int) or pid <= 0:
        return None  # not pid-bound: liveness is the heartbeat's job, not ours
    if os.name == "nt":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            SYNCHRONIZE = 0x00100000
            h = k.OpenProcess(SYNCHRONIZE, False, pid)
            if h:
                k.CloseHandle(h)
                return True
            # 5 = ERROR_ACCESS_DENIED: the process exists, we just cannot open
            # it. 87 = ERROR_INVALID_PARAMETER: no such pid.
            err = k.GetLastError()
            if err == 5:
                return True
            if err == 87:
                return False
            return None
        except Exception:
            return None
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return None


def started_epoch(d):
    """Seconds-since-epoch from EITHER implementation's timestamp field.

    orchestrate.ps1 writes `started` as an ISO-8601 string; this module writes
    `started_at` as a float. A reader fluent in only its own dialect scores the
    other's lock as age zero, which silently disables staleness entirely.
    """
    if isinstance(d.get("started_at"), (int, float)):
        return float(d["started_at"])
    s = d.get("started")
    if isinstance(s, str) and s:
        import datetime
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                    "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.datetime.strptime(s[:31], fmt).timestamp()
            except Exception:
                continue
    return 0.0


def holder_state(d):
    """'live' | 'stale' | 'unknown' - the single authority on whether a lock holds.

    Liveness is the pid, decided the same way orchestrate.ps1's Take-LegLock
    decides it (Get-Process there, OpenProcess here). A confirmed-dead pid is
    reclaimable only once the clock has ALSO gone quiet, so a dispatcher that
    died a second ago is never raced.

    Windows note: a pid from an MSYS/git-bash shell (`$$`) is NOT a Win32 pid
    and will not resolve through OpenProcess.
    """
    base = d.get("heartbeat_at")
    if not isinstance(base, (int, float)):
        base = started_epoch(d)
    idle = time.time() - base
    stale = idle >= STALE_SECONDS
    pid = d.get("pid") or 0
    if pid in (0, 4):
        # Reserved system pids always resolve. Never let one mean "live".
        return "stale" if stale else "unknown"
    alive = pid_alive(pid)
    if alive is True:
        return "live"
    if alive is None:
        return "unknown"
    return "stale" if stale else "live"


def lock_path(leg):
    return os.path.join(LOCKS, "%s.lock" % leg)


def read_lock(leg):
    p = lock_path(leg)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as e:
        # A corrupt lock is still a lock. Refusing on unreadable state is the
        # safe direction; it is never silently discarded.
        return {"leg": leg, "pid": -1, "corrupt": str(e)[:120]}


def describe(d):
    if not d:
        return "(none)"
    base = d.get("heartbeat_at")
    if not isinstance(base, (int, float)):
        base = started_epoch(d)
    age = int(time.time() - base)
    return "pid=%s host=%s wt=%s base=%s idle=%ds" % (
        d.get("pid"), d.get("host", "?"), d.get("worktree", "?"),
        str(d.get("base_sha", "?"))[:8], age)


def cmd_acquire(a):
    os.makedirs(LOCKS, exist_ok=True)
    existing = read_lock(a.leg)
    if existing:
        st = holder_state(existing)
        if a.force:
            pass  # fall through, recorded in reaped_from below
        elif st == "live":
            print("REFUSED %s held: %s" % (a.leg, describe(existing)))
            return 3
        elif st == "unknown":
            print("REFUSED %s holder liveness undeterminable - assumed alive: %s"
                  % (a.leg, describe(existing)))
            return 4
        else:
            print("  reaping stale lock: %s" % describe(existing))
            os.unlink(lock_path(a.leg))

    worktree = a.worktree or os.path.relpath(os.getcwd(), ROOT)
    wt_abs = worktree if os.path.isabs(worktree) else os.path.join(ROOT, worktree)

    # ---- P0 guard. A directory that exists but is not its own git worktree
    # resolves to the MAIN repo on the LIVE branch, so an agent dispatched
    # there writes to the tree it was supposed to be isolated from.
    #
    # HONEST SCOPE, as of this commit: an earlier draft of this comment claimed
    # the lock was "the one chokepoint both dispatchers pass through". That was
    # false and an adversarial review caught it. NEITHER dispatcher calls this
    # module - orchestrate.ps1 has its own Take-LegLock, and run.ts takes no
    # lock at all. So this guard protects direct callers only. The live path is
    # covered separately at orchestrate.ps1's existence test, and that cover is
    # itself partial (one of five worktree-decision sites in that file).
    #
    # Wiring the dispatchers to this module is open work. Until then, do not
    # cite this refusal as evidence that a dispatch was isolated.
    #
    # A missing guard module WARNS rather than refuses - matching this repo's
    # existing rule that an unwired guardrail (ok:null) warns while a violated
    # one (ok:false) fails. A packaging hiccup must not brick every lock.
    if not a.allow_unregistered:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            try:
                import worktree_guard
            finally:
                sys.path.pop(0)
        except Exception as e:
            print("  warning: worktree_guard unavailable (%s) - isolation "
                  "UNVERIFIED for this acquire" % str(e)[:80])
        else:
            ok, st, why = worktree_guard.verify(worktree)
            if not ok:
                print("REFUSED %s: %s" % (a.leg, why))
                print("  worktree_guard classifies %s as '%s'." % (worktree, st))
                print("  Nothing was deleted. Classify its contents before")
                print("  reclaiming it: python harness/worktree_guard.py classify %s"
                      % worktree)
                return worktree_guard.EXIT_ARMED
    base_sha = a.base_sha
    if not base_sha:
        r = subprocess.run(["git", "-C", wt_abs, "rev-parse", "HEAD"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        base_sha = r.stdout.strip() if r.returncode == 0 else ""
    branch = a.branch
    if not branch:
        r = subprocess.run(["git", "-C", wt_abs, "rev-parse", "--abbrev-ref", "HEAD"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        branch = r.stdout.strip() if r.returncode == 0 else ""

    now = time.time()
    # `is None`, not truthiness: an explicit `--pid 0` must reach the guard
    # below rather than being silently reinterpreted as "not supplied".
    pid = os.getppid() if a.pid is None else a.pid
    # PID 0 is Idle and 4 is System on Windows. Both always resolve, so
    # `Get-Process -Id` in orchestrate.ps1 would read either as a live holder
    # forever and the leg would never be reclaimable. Refuse to write one.
    if pid in (0, 4):
        print("REFUSED: pid %d is a reserved system pid and would wedge this "
              "leg permanently. Pass a real --pid." % pid)
        return 1
    rec = {
        "leg": a.leg,
        # Interop: orchestrate.ps1 checks `Get-Process -Id $prev.pid`, so this
        # must be a real, live, Win32-visible pid - never this CLI's own, which
        # exits a millisecond later. Defaults to the caller (the dispatcher).
        "pid": pid,
        # ---- orchestrate.ps1's field names, written verbatim so the two
        # implementations read each other's locks. Take-LegLock emits
        # {leg, pid, started, machine}; everything below is additive and
        # ConvertFrom-Json ignores what it does not know.
        "started": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
        "machine": socket.gethostname(),
        "host": socket.gethostname(),
        "agent": a.agent or os.environ.get("SYNAPSE_AGENT", "unknown"),
        "worktree": worktree.replace("\\", "/"),
        "branch": branch,
        "base_sha": base_sha,
        "started_at": now,
        "heartbeat_at": now,
    }
    if a.force and existing:
        rec["reaped_from"] = {k: existing.get(k)
                              for k in ("pid", "host", "worktree", "started_at")}

    try:
        fd = os.open(lock_path(a.leg), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        # Lost a race between the check above and here. This is the branch that
        # makes the fence real rather than advisory.
        print("REFUSED %s acquired by another process mid-call" % a.leg)
        return 3
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
    if not base_sha:
        print("  warning: base_sha empty - %s is not a git worktree?" % worktree)
    print("ACQUIRED %s  %s" % (a.leg, describe(rec)))
    return 0


def cmd_release(a):
    d = read_lock(a.leg)
    if not d:
        print("not held: %s" % a.leg)
        return 0
    if not a.force and d.get("pid") not in (os.getpid(), a.pid):
        alive = pid_alive(d.get("pid"))
        if alive is not False:
            print("REFUSED release %s - held by %s, not this process. --force to override."
                  % (a.leg, describe(d)))
            return 3
    os.unlink(lock_path(a.leg))
    print("RELEASED %s" % a.leg)
    return 0


def cmd_heartbeat(a):
    d = read_lock(a.leg)
    if not d:
        print("not held: %s" % a.leg)
        return 1
    d["heartbeat_at"] = time.time()
    tmp = lock_path(a.leg) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=1)
    os.replace(tmp, lock_path(a.leg))
    return 0


def cmd_list(a):
    if not os.path.isdir(LOCKS):
        print("  no locks dir")
        return 0
    names = sorted(f[:-5] for f in os.listdir(LOCKS) if f.endswith(".lock"))
    if not names:
        print("  no legs locked")
        return 0
    for n in names:
        d = read_lock(n)
        print("  %-8s %-8s %s" % (n, holder_state(d), describe(d)))
    return 0


def cmd_reap(a):
    """Remove locks whose holder is confirmed dead AND whose heartbeat is stale.

    Both conditions, always. A stale heartbeat alone means a busy agent that
    did not check in; a dead pid alone means a lock taken moments before a
    crash that another process may already be handling.
    """
    if not os.path.isdir(LOCKS):
        return 0
    reaped = held = unknown = 0
    for f in sorted(os.listdir(LOCKS)):
        if not f.endswith(".lock"):
            continue
        leg = f[:-5]
        d = read_lock(leg)
        st = holder_state(d)
        if st == "unknown":
            print("  %-8s KEPT - liveness undeterminable, assumed alive" % leg)
            unknown += 1
        elif st == "live":
            held += 1
        else:
            os.unlink(lock_path(leg))
            print("  %-8s REAPED - %s" % (leg, describe(d)))
            reaped += 1
    print("  reaped %d, kept %d, undeterminable %d" % (reaped, held, unknown))
    return 0


def cmd_check(a):
    """Exit 3 if the leg is held by a live holder. For dispatch preflight."""
    d = read_lock(a.leg)
    if not d:
        return 0
    st = holder_state(d)
    if st == "stale":
        print("stale (reapable): %s" % describe(d))
        return 0
    print("HELD %s (%s) %s" % (a.leg, st, describe(d)))
    return 3 if st == "live" else 4


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    def leg_arg(sp):
        sp.add_argument("leg")
        sp.add_argument("--force", action="store_true")
        sp.add_argument("--pid", type=int, default=None)
        return sp

    a = leg_arg(sub.add_parser("acquire"))
    a.add_argument("--worktree", default="")
    a.add_argument("--branch", default="")
    a.add_argument("--base-sha", dest="base_sha", default="")
    a.add_argument("--agent", default="")
    a.add_argument("--allow-unregistered", dest="allow_unregistered",
                   action="store_true",
                   help="skip the worktree-isolation guard (deliberate, logged)")
    leg_arg(sub.add_parser("release"))
    leg_arg(sub.add_parser("heartbeat"))
    leg_arg(sub.add_parser("check"))
    sub.add_parser("list")
    sub.add_parser("reap")

    ns = p.parse_args(argv)
    return {
        "acquire": cmd_acquire, "release": cmd_release, "heartbeat": cmd_heartbeat,
        "list": cmd_list, "reap": cmd_reap, "check": cmd_check,
    }[ns.cmd](ns)


if __name__ == "__main__":
    sys.exit(main())
