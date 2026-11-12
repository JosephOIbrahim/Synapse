"""scripts/tag_release.py -- the refuse-dirty-tag gate (Blueprint W0).

A git tag is a claim: "this commit is vX.Y.Z." This gate refuses the claim
whenever observation contradicts it:

  1. tracked files carry uncommitted modifications  -> REFUSE
  2. scripts/sync_version.py --check fails          -> REFUSE
  3. the crux closure record is absent or stale     -> REFUSE
  4. the conformance test fails pre-tag             -> REFUSE
  5. the tag already exists                         -> REFUSE
  6. any check that cannot be observed is UNKNOWN   -> REFUSE

UNKNOWN refuses (house rule): a gate that cannot see is not an open gate.
Untracked files do NOT block -- ratified W0 pick: dirty = tracked only; the
debris ruling is its own stack item.

The crux closure record (2026-11-12, red team). A release held by an owner
ruling was held by memory: the ruling lived in a note and nothing read it.
This gate reads a committed record instead --

  harness/notes/release-<version>/CRUX-RECORD.json

  {"version": "5.101.0",                 # must equal VERSION
   "review": "NR-RECOVERY-RECEIPTS",     # the named review
   "reviewer": "Codex",                  # who ran it
   "reviewed_date": "2026-11-14",        # ISO date it ran
   "verdict": "PASS",                    # the receipt, for humans
   "passed": true,                       # the gate reads THIS
   "commit_range": "<base>..<tip>"}      # git SHAs the review covered

It is bound to git so it cannot go stale silently: the range's tip must be
contained in the commit being tagged, the record must be in that commit's
tree (not merely in the working directory), and the review date cannot
predate the reviewed tip. Another version, another history, an uncommitted
record, a pre-dated record or a non-passing verdict refuses. No record, no
tag.

Running this script IS the human tag act. It never pushes; on success it
prints the push command for the operator. v5.43.0 was published against a
tree that said 5.42.0 because nothing stood between `git tag` and the
claim. This stands between.

Usage:
  python scripts/tag_release.py --check-only   # preflight only, no tag
  python scripts/tag_release.py                # preflight -> tag -> re-verify
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFORMANCE = 'tests/test_phase0c_doc1_version_conformance.py'

CRUX_RECORD = 'CRUX-RECORD.json'
CRUX_STRING_FIELDS = ('version', 'review', 'reviewer', 'reviewed_date',
                      'verdict', 'commit_range')
CRUX_SHA = re.compile(r'^[0-9a-fA-F]{7,40}$')


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


def crux_record_rel(version):
    return Path('harness') / 'notes' / f'release-{version}' / CRUX_RECORD


def _git(root, *args):
    """A git call rooted at root. None = could not be observed (UNKNOWN)."""
    return _run(['git', '-C', str(root), *args])


def _sha_resolves(root, sha):
    """(full_sha, None) or (None, why-not) -- why-not also covers UNKNOWN."""
    p = _git(root, 'rev-parse', '--verify', f'{sha}^{{commit}}')
    if p is None:
        return None, 'git could not be observed'
    if p.returncode != 0:
        return None, f'{sha!r} does not resolve to a commit here'
    return p.stdout.strip(), None


def _is_ancestor(root, older, newer):
    """True/False, or None when git cannot answer."""
    p = _git(root, 'merge-base', '--is-ancestor', older, newer)
    if p is None:
        return None
    if p.returncode == 0:
        return True
    if p.returncode == 1:
        return False
    return None


def crux_record_problem(version, root=None):
    """None when the closure record opens the gate; else the refusal text.

    Fail closed: every branch that cannot read the record, cannot bind it to
    this version, or cannot bind it to this history returns text. Every
    refusal names the file and the operator's next act.
    """
    root = Path(root) if root is not None else ROOT
    rel = crux_record_rel(version)
    shown = rel.as_posix()

    def refuse(why, fix):
        return f'{why}\n  expected: {shown}\n  next act: {fix}'

    if not (root / rel).is_file():
        return refuse(f'no closure record for v{version}',
                      f'write {shown} after the crux review passes, commit '
                      f'it, then re-run')
    try:
        rec = json.loads((root / rel).read_text(encoding='utf-8'))
    except OSError as exc:
        return refuse(f'{shown} is unreadable ({exc})',
                      'make the file readable, then re-run')
    except ValueError as exc:
        return refuse(f'{shown} is not JSON ({exc})',
                      'fix the JSON, then re-run')
    if not isinstance(rec, dict):
        return refuse(f'{shown} is not a JSON object',
                      'make the record a JSON object, then re-run')

    missing = [k for k in (*CRUX_STRING_FIELDS, 'passed') if k not in rec]
    if missing:
        return refuse(f'{shown} is missing {", ".join(missing)}',
                      'fill in every field documented in tag_release.py')
    for key in CRUX_STRING_FIELDS:
        val = rec[key]
        if not isinstance(val, str) or not val.strip():
            return refuse(f'{shown} field {key!r} is not a non-empty string',
                          f'give {key!r} a value, then re-run')
    if rec['version'].strip() != version:
        return refuse(f"{shown} records version {rec['version'].strip()!r}, "
                      f'not {version!r}',
                      f'write the record for this version at '
                      f'{crux_record_rel(version).as_posix()}')
    if rec['passed'] is not True:
        return refuse(f"{shown} records passed={rec['passed']!r} "
                      f"(verdict {rec['verdict'].strip()!r})",
                      'a non-passing review cannot open the tag gate; re-run '
                      'the review and record the new verdict')
    reviewed = rec['reviewed_date'].strip()
    try:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', reviewed):
            raise ValueError('not YYYY-MM-DD')
        date.fromisoformat(reviewed)
    except ValueError:
        return refuse(f'{shown} reviewed_date {reviewed!r} is not an ISO '
                      f'date (YYYY-MM-DD)', 'record the date the review ran')

    rng = rec['commit_range'].strip()
    parts = [p.strip() for p in rng.split('..')]
    if len(parts) != 2 or not all(CRUX_SHA.match(p) for p in parts):
        return refuse(f'{shown} commit_range {rng!r} is not "<base>..<tip>" '
                      f'of git SHAs',
                      'record the range the review covered, e.g. '
                      '58f23d33..0ee8b00c')
    base, tip = parts
    base_sha, why = _sha_resolves(root, base)
    if why:
        return refuse(f'{shown} commit_range base: {why}',
                      'record SHAs from this repository, then re-run')
    tip_sha, why = _sha_resolves(root, tip)
    if why:
        return refuse(f'{shown} commit_range tip: {why}',
                      'record SHAs from this repository, then re-run')
    committed = _git(root, 'show', '-s', '--format=%cI', tip_sha)
    if committed is None or committed.returncode != 0:
        return refuse(f'{shown} could not read the commit date of {tip}',
                      'record a tip from this repository, then re-run')
    tip_day = committed.stdout.strip()[:10]
    if reviewed < tip_day:
        return refuse(f'{shown} reviewed_date {reviewed} predates the '
                      f'reviewed tip {tip} (committed {tip_day})',
                      'record the date the review ran against this code')
    ordered = _is_ancestor(root, base_sha, tip_sha)
    if ordered is None:
        return refuse(f'{shown} commit_range could not be checked '
                      f'(git unobservable)',
                      'run where git can read this repository')
    if not ordered:
        return refuse(f'{shown} commit_range does not run base -> tip '
                      f'({base} -> {tip})',
                      'record the range in base..tip order, then re-run')
    contained = _is_ancestor(root, tip_sha, 'HEAD')
    if contained is None:
        return refuse(f'{shown} could not be checked against HEAD '
                      f'(git unobservable)',
                      'run where git can read this repository')
    if not contained:
        return refuse(f'{shown} is stale: its reviewed tip {tip} is not in '
                      f'the history of the commit being tagged',
                      're-run the crux review on this release history and '
                      f'rewrite {shown}, then re-run')
    in_tree = _git(root, 'cat-file', '-e', f'HEAD:{shown}')
    if in_tree is None:
        return refuse(f'{shown} could not be checked against HEAD '
                      f'(git unobservable)',
                      'run where git can read this repository')
    if in_tree.returncode != 0:
        return refuse(f'{shown} is in the working directory but not in the '
                      f'commit being tagged',
                      'commit the record, then re-run')
    return None


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

    crux = crux_record_problem(v)
    if crux is None:
        print(f'crux_record  v{v} closure      OK')
    else:
        print('crux_record  no valid closure record  REFUSE')
        for line in crux.splitlines():
            print(f'             {line}')
        ok = False

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


def _head_sha(root):
    """HEAD's sha, or '' when git cannot be observed. Never raises.

    The gate must refuse on UNKNOWN; dereferencing _git(...).stdout raised
    AttributeError instead, which fails closed only by traceback.
    """
    p = _git(root, 'rev-parse', 'HEAD')
    if p is None or p.returncode != 0:
        return ''
    return p.stdout.strip()


def _tag_argv(root, tag, gate_sha):
    """The tag command. Named separately so a test can assert the sha is in it:
    `git tag -a <tag>` with no commit re-resolves HEAD at tag time, which is the
    race this gate exists to stop."""
    return ['git', '-C', str(root), 'tag', '-a', tag, gate_sha,
            '-m', f'SYNAPSE {tag} -- release-truth gate passed']


def _create_tag(root, tag, gate_sha):
    """Create the annotated tag on gate_sha, or refuse. Returns True on success.

    Exercises the real wiring -- refusal first, then the real argv -- so a
    regression that reopens the race fails a test rather than shipping green.
    """
    if _tag_target_refusal(root, gate_sha):
        return False
    p = _run(_tag_argv(root, tag, gate_sha))
    return p is not None and p.returncode == 0


def _tag_target_refusal(root, gate_sha):
    """True when the tag must be refused because HEAD is not the checked commit.

    Pulled out of the __main__ block so it can be pinned: a control that only
    executes when the script runs is a control nothing tests.
    """
    if not gate_sha:
        return True
    return _head_sha(root) != gate_sha


def _finish_tag(root, tag, gate_sha):
    """Create the checked tag, then re-verify it; every failure refuses.

    _create_tag returns False on refusal/failure and True on success. Keeping
    this separate from preflight lets tests drive the real git wiring in
    disposable repositories without running any release gate against SYNAPSE.
    """
    if not _create_tag(root, tag, gate_sha):
        print('tag          REFUSED/FAILED -- no tag was created (nothing pushed)')
        return 1

    print(f'tag          {tag} created      OK')
    if not run_conformance('post'):
        print(f'gate         POST-TAG FAIL -- inspect before pushing {tag}')
        return 1

    print(f'next act     git push origin {tag}   (operator, per-act)')
    return 0


if __name__ == '__main__':
    check_only = '--check-only' in sys.argv

    # Capture the commit BEFORE any check runs. Reading it after preflight left a
    # window: a commit landing between the HEAD-binding checks inside preflight
    # and this capture was tagged while the checks had judged the older commit.
    # Capturing first means any later move is caught by _tag_target_refusal
    # below, so the gate refuses rather than tagging an unchecked commit.
    gate_sha = _head_sha(ROOT)
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

    if _tag_target_refusal(ROOT, gate_sha):
        print('tag          REFUSED -- HEAD moved while the gate was running, so '
              'the tag would not name the commit that was checked. Re-run the gate.')
        sys.exit(1)
    sys.exit(_finish_tag(ROOT, tag, gate_sha))
