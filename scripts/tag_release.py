"""scripts/tag_release.py -- the refuse-dirty-tag gate (Blueprint W0).

A git tag is a claim: "this commit is vX.Y.Z." This gate refuses the claim
whenever observation contradicts it:

  1. tracked files carry uncommitted modifications  -> REFUSE
  2. scripts/sync_version.py --check fails          -> REFUSE
  3. the conformance test fails pre-tag             -> REFUSE
  4. the tag already exists                         -> REFUSE
  5. any check that cannot be observed is UNKNOWN   -> REFUSE

UNKNOWN refuses (house rule): a gate that cannot see is not an open gate.
Untracked files do NOT block -- ratified W0 pick: dirty = tracked only; the
debris ruling is its own stack item.

Running this script IS the human tag act. It never pushes; on success it
prints the push command for the operator. v5.43.0 was published against a
tree that said 5.42.0 because nothing stood between `git tag` and the
claim. This stands between.

Usage:
  python scripts/tag_release.py --check-only   # preflight only, no tag
  python scripts/tag_release.py                # preflight -> tag -> re-verify
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFORMANCE = 'tests/test_phase0c_doc1_version_conformance.py'


def _run(args, timeout=180):
    """Run a command from ROOT. None = could not be observed (UNKNOWN)."""
    try:
        return subprocess.run(
            args, cwd=ROOT, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


def canonical_version():
    try:
        v = (ROOT / 'VERSION').read_text(encoding='utf-8-sig').strip()
    except OSError:
        return None
    return v or None


def tracked_dirty():
    """Tracked-file modifications, or None when git cannot answer."""
    p = _run(['git', '-C', str(ROOT), 'status', '--porcelain'])
    if p is None or p.returncode != 0:
        return None
    return [ln for ln in p.stdout.splitlines()
            if ln.strip() and not ln.startswith('??')]


def tag_exists(tag):
    p = _run(['git', '-C', str(ROOT), 'tag', '--list', tag])
    if p is None or p.returncode != 0:
        return None
    return bool(p.stdout.strip())


def preflight():
    """All gate checks. Returns (ok, tag_name). Prints one line per check."""
    ok = True

    v = canonical_version()
    if v is None:
        print('version      UNKNOWN            REFUSE (VERSION unreadable)')
        return False, None
    tag = f'v{v}'
    print(f'version      {v:18s} OK')

    dirty = tracked_dirty()
    if dirty is None:
        print('worktree     UNKNOWN            REFUSE (git unobservable)')
        ok = False
    elif dirty:
        print(f'worktree     {len(dirty)} tracked mod(s)  REFUSE')
        for ln in dirty:
            print(f'             {ln}')
        ok = False
    else:
        print('worktree     clean (tracked)    OK')

    p = _run([sys.executable, str(ROOT / 'scripts' / 'sync_version.py'),
              '--check'])
    if p is None:
        print('sync_check   UNKNOWN            REFUSE')
        ok = False
    elif p.returncode != 0:
        print('sync_check   drift              REFUSE')
        sys.stdout.write(p.stdout)
        ok = False
    else:
        print('sync_check   all CONFORM        OK')

    exists = tag_exists(tag)
    if exists is None:
        print('tag_free     UNKNOWN            REFUSE')
        ok = False
    elif exists:
        print(f'tag_free     {tag} exists     REFUSE')
        ok = False
    else:
        print(f'tag_free     {tag}             OK')

    return ok, tag


def run_conformance(label):
    p = _run([sys.executable, '-m', 'pytest', CONFORMANCE, '-q'])
    if p is None:
        print(f'pytest_{label}  UNKNOWN            REFUSE')
        return False
    tail = p.stdout.strip().splitlines()
    print(f'pytest_{label}  {"PASS" if p.returncode == 0 else "FAIL"}'
          f'               {tail[-1] if tail else ""}')
    return p.returncode == 0


if __name__ == '__main__':
    check_only = '--check-only' in sys.argv

    ok, tag = preflight()
    if ok:
        ok = run_conformance('pre')

    if not ok:
        print('gate         REFUSED -- no tag was created')
        sys.exit(1)
    if check_only:
        print(f'gate         OPEN -- {tag} may be created (re-run without '
              '--check-only)')
        sys.exit(0)

    p = _run(['git', '-C', str(ROOT), 'tag', '-a', tag,
              '-m', f'SYNAPSE {tag} -- release-truth gate passed'])
    if p is None or p.returncode != 0:
        print('tag          UNKNOWN/FAILED     REFUSE (nothing pushed)')
        if p is not None:
            sys.stdout.write(p.stderr)
        sys.exit(1)
    print(f'tag          {tag} created      OK')

    if not run_conformance('post'):
        print(f'gate         POST-TAG FAIL -- inspect before pushing {tag}')
        sys.exit(1)

    print(f'next act     git push origin {tag}   (operator, per-act)')
    sys.exit(0)
