"""R107: every version location must agree, and a check must enforce it.

I bumped VERSION to 5.35.0, committed, tagged and pushed - and never touched
__version__, which still read 5.33.0. The health report reads __version__, which
is why SYNAPSE reported a version two releases behind its own tag.

FOUR locations were known: VERSION, __version__, the git tag, the install stamp.
A FIFTH - pyproject.toml - surfaced only because an existing test failed the
moment __version__ was corrected. The check that found it was one somebody else
had already written, which is the argument for writing them.

harness/finalize.ps1 bumped VERSION and nothing else. The procedure was
underspecified and I followed it correctly to a wrong outcome - the same shape as
R93's `green` with zero commits.
"""
import glob as _glob
import io
import json as _json
import os as _os
import re
import sys

# WA1-TRUTH (G4): repo root anchored to THIS file (harness/verify/…) so the APEX
# stamp check is CWD-independent. The version-chain check below keeps its existing
# CWD-relative paths unchanged.
_REPO_ROOT = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

ROOT_FILES = {
    'VERSION': (None, 'VERSION'),
    '__version__': (re.compile(r'__version__\s*=\s*["\']([^"\']+)["\']'),
                    'python/synapse/__init__.py'),
    'pyproject': (re.compile(r'^version\s*=\s*["\']([^"\']+)["\']', re.M),
                  'pyproject.toml'),
    # SIXTH location. The module docstring must state it too, enforced by
    # tests/test_phase0c_doc1_version_conformance.py. Each correction surfaced
    # the next, and every one was caught by a test somebody else had written -
    # which is the argument for writing them.
    'docstring': (re.compile(r'Version:\s*([0-9]+\.[0-9]+\.[0-9]+)'),
                  'python/synapse/__init__.py'),
    # SEVENTH. The CLAUDE.md banner. tests/test_phase0c_doc1_version_conformance.py
    # already enforced the chain pyproject == __version__ == docstring == banner,
    # and it walked me through every location one failure at a time. Four were
    # known when this check was written; the other three were found by a test
    # somebody else wrote first.
    'claude_md': (re.compile(r'SYNAPSE v([0-9]+\.[0-9]+\.[0-9]+)'), 'CLAUDE.md'),
}


def _read(pat, path):
    # utf-8-SIG, never plain utf-8: VERSION carried a BOM written by
    # Set-Content -Encoding utf8 during the release itself. Read with utf-8 it
    # yields '\ufeff5.35.0', which compares unequal to everything and crashes
    # any consumer printing it on a cp1252 console.
    txt = open(path, encoding='utf-8-sig').read()
    if pat is None:
        return txt.strip()
    m = pat.search(txt)
    return m.group(1) if m else None


def read_all():
    return {k: _read(pat, path) for k, (pat, path) in ROOT_FILES.items()}


def strip_bom(path):
    raw = open(path, 'rb').read()
    if raw[:3] == b'\xef\xbb\xbf':
        with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(raw.decode('utf-8-sig'))
        return True
    return False


def _set(pat, path, value):
    txt = open(path, encoding='utf-8-sig').read()
    txt = pat.sub(lambda m: m.group(0).replace(m.group(1), value), txt, count=1)
    with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(txt)


# --- WA1-TRUTH (G4): APEX catalog-stamp agreement -----------------------------
# A SECOND, INDEPENDENT contract, additive to the version chain above. The APEX
# truth surface (apex_probes.py) carries an "APEX-TRUTH-BUILD: <build>" stamp; the
# per-build evidence artifact apex_truth_<build>.json is the receipt. If the stamp
# drifts from the freshest artifact's build, the catalog was re-run on a new build
# but the truth surface was not re-stamped — the exact stale-truth defect this leg
# exists to make a RED check instead of a silent surprise (blueprint sec.10). The
# absence of an artifact is NOT drift (nothing to compare) — unmeasurable != wrong.
APEX_PROBES_PATH = _os.path.join(_REPO_ROOT, 'python', 'synapse', 'science', 'apex_probes.py')
APEX_RUNS_GLOB = _os.path.join(_REPO_ROOT, 'harness', 'autoresearch', 'runs', '*', 'apex_truth_*.json')
_APEX_STAMP_RE = re.compile(r'APEX-TRUTH-BUILD:\s*([0-9]+\.[0-9]+\.[0-9]+)')
_APEX_ARTIFACT_RE = re.compile(r'apex_truth_(.+)\.json$')


def apex_stamp():
    """The build apex_probes.py claims its APEX truth surface was confirmed against."""
    try:
        txt = open(APEX_PROBES_PATH, encoding='utf-8-sig').read()
    except OSError:
        return None
    m = _APEX_STAMP_RE.search(txt)
    return m.group(1) if m else None


def latest_apex_artifact():
    """The freshest apex_truth artifact as {path, file_build, meta_build}, or None."""
    paths = _glob.glob(APEX_RUNS_GLOB)
    if not paths:
        return None
    # Run dirs are timestamped (apex_basic_YYYYMMDD_HHMMSS), so lexicographic max
    # on the path is the freshest run AND is clone-deterministic (mtime is not).
    newest = max(paths)
    mfb = _APEX_ARTIFACT_RE.search(_os.path.basename(newest))
    meta_build = None
    try:
        d = _json.loads(open(newest, encoding='utf-8').read())
        meta_build = (d.get('meta') or {}).get('build')
    except Exception:
        meta_build = None
    return {'path': newest, 'file_build': (mfb.group(1) if mfb else None),
            'meta_build': meta_build}


def apex_agreement():
    """Verdict {ok, reason, stamp, artifact} for the APEX catalog stamp.

    ok is False ONLY on real drift: a missing stamp, an internally inconsistent
    artifact (filename build != meta build), or stamp != freshest artifact build.
    No artifact at all -> ok True with a 'nothing to compare' reason."""
    stamp = apex_stamp()
    art = latest_apex_artifact()
    if stamp is None:
        return {'ok': False, 'stamp': None, 'artifact': art,
                'reason': 'no APEX-TRUTH-BUILD stamp in apex_probes.py'}
    if art is None:
        return {'ok': True, 'stamp': stamp, 'artifact': None,
                'reason': 'no apex_truth artifact present (nothing to compare)'}
    if art['file_build'] and art['meta_build'] and art['file_build'] != art['meta_build']:
        return {'ok': False, 'stamp': stamp, 'artifact': art,
                'reason': "artifact filename build %s != meta build %s"
                          % (art['file_build'], art['meta_build'])}
    art_build = art['meta_build'] or art['file_build']
    agree = (stamp == art_build)
    return {'ok': agree, 'stamp': stamp, 'artifact': art,
            'reason': 'agree' if agree
                      else 'apex catalog drift: apex_probes stamp %s != freshest artifact %s'
                           % (stamp, art_build)}


if __name__ == '__main__':
    fix = '--fix' in sys.argv

    if fix and strip_bom('VERSION'):
        print('stripped a UTF-8 BOM from VERSION')

    vals = read_all()
    canonical = vals['VERSION']
    agree = len(set(vals.values())) == 1
    print('BEFORE  ' + '  '.join(f'{k}={v}' for k, v in vals.items()) + f'  agree={agree}')

    if fix and not agree:
        for k, (pat, path) in ROOT_FILES.items():
            if pat is not None and vals[k] != canonical:
                _set(pat, path, canonical)
                print(f'  set {k} -> {canonical}')
        vals = read_all()
        agree = len(set(vals.values())) == 1
        print('AFTER   ' + '  '.join(f'{k}={v}' for k, v in vals.items()) + f'  agree={agree}')

    # WA1-TRUTH (G4): the APEX catalog-stamp contract, additive to the version
    # chain. Reported always; gates the exit alongside `agree`. Never touches the
    # version-chain logic above (do-not-weaken).
    apex = apex_agreement()
    art = apex['artifact']
    art_build = (art['meta_build'] or art['file_build']) if art else None
    art_path = art['path'] if art else None
    print('APEX    stamp=%s  artifact_build=%s  ok=%s  (%s)'
          % (apex['stamp'], art_build, apex['ok'], apex['reason']))
    if art_path:
        print('APEX    artifact=%s' % art_path)

    # A check that can fail. It failed on this tree before --fix, twice - once on
    # __version__ and once on pyproject (R80: build it, or strike the ruling
    # that ordered it. This one gets built.) WA1-TRUTH adds the apex gate.
    sys.exit(0 if (agree and apex['ok']) else 1)
