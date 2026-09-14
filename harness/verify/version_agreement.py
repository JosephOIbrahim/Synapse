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
    # EIGHTH (REACH R2, blueprint sec.4 R2): the README public face. The
    # '<sub>vX.Y.Z · Houdini …' banner is the version the outside world reads.
    # Anchored to the banner line so a historical version mentioned in the body
    # cannot satisfy it — same anchor as the phase0c conformance test.
    'readme_banner': (re.compile(r'<sub>v([0-9]+\.[0-9]+\.[0-9]+) · Houdini', re.M),
                      'README.md'),
}


# --- REACH R2: public-face agreement ---------------------------------------
# Blueprint docs/REACH_BLUEPRINT.md sec.4 R2 + contract
# .synapse/contracts/reach-public-agreement.yaml: the README's claimed version
# must equal the tagged version, or red. The in-tree chain above proves the
# tree agrees with itself; four locations agreeing is not a quorum when nothing
# reads the outside world — v5.43.0 was tagged against a tree that still said
# 5.42.0 (tests/test_phase0c_doc1_version_conformance.py carries that story).
# This section is that check's public half: the newest published release tag
# may never outrun the version the README shows a stranger.
#
# Tag comparison semantics mirror the phase0c conformance test: tag AHEAD of
# the public face is red (stale public face); the public face ahead of the
# newest tag is the release ritual's own window (bump lands, README syncs, tag
# is pushed after) and must stay green or every correct release fires.
import subprocess as _subprocess

_RELEASE_TAG_RE = re.compile(r'^v([0-9]+)\.([0-9]+)\.([0-9]+)$')
# A second public claim this leg found already stale on master: the README
# sub-line 'tags: v5.50.0 is latest' while v5.52.0 was published. Absence of
# the claim is allowed; a present-but-stale claim is drift, and drift is red.
_README_TAG_CLAIM_RE = re.compile(r'tags:\s*v([0-9]+\.[0-9]+\.[0-9]+)\s+is\s+latest')


def parse_version(version):
    """'5.52.0' -> (5, 52, 0). Returns None on a shape this file cannot compare."""
    m = re.match(r'^([0-9]+)\.([0-9]+)\.([0-9]+)$', str(version).strip())
    return tuple(int(g) for g in m.groups()) if m else None


def parse_release_tag(tag):
    """'v5.52.0' -> (5, 52, 0). Anything else (archive/... refs) -> None."""
    m = _RELEASE_TAG_RE.match(str(tag).strip())
    return tuple(int(g) for g in m.groups()) if m else None


def newest_release_tag(tags):
    """Highest release tag as (name, tuple), or None when there are none.

    Sorted in Python rather than by `git --sort=-v:refname` so the ordering is
    the same on every git version and is directly testable. Mirrors the phase0c
    conformance test's copy deliberately: that test pins the concept, this is
    the verifier's runtime copy.
    """
    parsed = [(t, parse_release_tag(t)) for t in (tags or [])]
    parsed = [(t, v) for t, v in parsed if v is not None]
    return max(parsed, key=lambda pair: pair[1]) if parsed else None


def _git(args, cwd):
    """One git invocation, or None when the question cannot be asked."""
    try:
        proc = _subprocess.run(['git', '-C', cwd] + args, capture_output=True,
                               text=True, encoding='utf-8', errors='replace',
                               timeout=30)
    except (OSError, _subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def git_release_tags(cwd='.'):
    """Every tag git knows about. --list, not describe: a release can be tagged
    from a branch HEAD does not contain, and the public face must not trail a
    published tag wherever it was cut."""
    out = _git(['tag', '--list'], cwd)
    if out is None:
        return None
    return [line.strip() for line in out.splitlines() if line.strip()]


def git_describe(cwd='.'):
    """`git describe --tags`-style context string, or None. Reported for
    transparency (which tag HEAD descends from); never the comparison basis."""
    out = _git(['describe', '--tags'], cwd)
    return out.strip() if out is not None else None


def readme_tag_claim(readme_path='README.md'):
    """The version in the README's 'tags: vX.Y.Z is latest' claim, or None."""
    try:
        txt = open(readme_path, encoding='utf-8-sig').read()
    except OSError:
        return None
    m = _README_TAG_CLAIM_RE.search(txt)
    return m.group(1) if m else None


def _fix_tag_claim(canonical, readme_path='README.md'):
    """--fix half of the claim check: heal a STALE claim forward to canonical.

    Only staleness is healed (claim < canonical). A claim AHEAD of canonical
    asserts a release the tree knows nothing about — that stays red for human
    eyes; fixing it down would mask the anomaly."""
    claim = readme_tag_claim(readme_path)
    if claim is None:
        return None
    c, k = parse_version(claim), parse_version(canonical)
    if c is not None and k is not None and c < k:
        _set(_README_TAG_CLAIM_RE, readme_path, canonical)
        return claim
    return None


def public_agreement(canonical=None, readme_path='README.md', tags=None,
                     git_cwd='.'):
    """Verdict {ok, checks, banner, tag_claim, newest_tag, describe} for the
    public face against the published tags.

    ok is False ONLY on real drift: no banner, banner != canonical, a published
    release tag ahead of the banner, or a present 'tags: vX is latest' claim
    naming anything but max(newest release tag, canonical). Git or release tags
    unavailable -> those checks pass with a 'nothing to compare' reason, never
    a fabricated green (unmeasurable != wrong). Tests inject `tags`; production
    asks git."""
    if canonical is None:
        canonical = _read(None, 'VERSION')
    canonical = (canonical or '').strip()
    banner = _read(ROOT_FILES['readme_banner'][0], readme_path)
    claim = readme_tag_claim(readme_path)
    if tags is None:
        tags = git_release_tags(git_cwd)
        describe = git_describe(git_cwd)
    else:
        describe = None
    newest = newest_release_tag(tags) if tags else None
    newest_name, newest_tuple = newest if newest else (None, None)
    banner_tuple = parse_version(banner) if banner else None
    canonical_tuple = parse_version(canonical) if canonical else None

    checks = []
    checks.append({
        'name': 'readme_banner_present', 'ok': banner is not None,
        # ASCII-only on purpose: this prints to cp1252 consoles live (the '·'
        # in the real banner rendered as mojibake on the first live run).
        'reason': ('README <sub>vX.Y.Z banner reads %s' % banner)
                  if banner else 'no <sub>vX.Y.Z banner in README '
                                  '(public face is silent)'})
    checks.append({
        'name': 'banner_matches_canonical',
        'ok': (banner is not None and banner == canonical),
        'reason': ('agree' if banner == canonical else
                   'README banner %s != canonical VERSION %s'
                   % (banner, canonical))})
    if tags is None:
        checks.append({'name': 'tag_not_ahead_of_banner', 'ok': True,
                       'reason': 'git unavailable - nothing to compare '
                                 '(unmeasurable != wrong)'})
    elif newest is None:
        checks.append({'name': 'tag_not_ahead_of_banner', 'ok': True,
                       'reason': 'no vX.Y.Z release tags in this checkout - '
                                 'nothing to compare (unmeasurable != wrong)'})
    elif banner_tuple is None:
        checks.append({'name': 'tag_not_ahead_of_banner', 'ok': False,
                       'reason': 'cannot compare: no banner to hold against '
                                 'newest release tag %s' % newest_name})
    else:
        ahead = newest_tuple > banner_tuple
        checks.append({
            'name': 'tag_not_ahead_of_banner', 'ok': not ahead,
            'reason': ('agree' if not ahead else
                       'public face stale: newest release tag %s outruns the '
                       'README banner %s - a release was published without '
                       'updating the public artifact' % (newest_name, banner))})
    if claim is None:
        checks.append({'name': 'tag_claim_current', 'ok': True,
                       'reason': "no 'tags: vX is latest' claim in README - "
                                 'nothing to pin'})
    else:
        claim_tuple = parse_version(claim)
        basis_label, basis_tuple = None, None
        for label, t in (('newest release tag', newest_tuple),
                         ('VERSION', canonical_tuple)):
            if t is not None and (basis_tuple is None or t > basis_tuple):
                basis_label, basis_tuple = label, t
        if basis_tuple is None:
            checks.append({'name': 'tag_claim_current', 'ok': True,
                           'reason': 'nothing to compare the claim against '
                                     '(unmeasurable != wrong)'})
        else:
            current = (claim_tuple == basis_tuple)
            basis_str = '.'.join(str(p) for p in basis_tuple)
            if current:
                reason = 'agree'
            elif claim_tuple < basis_tuple:
                reason = ("README tags-claim names v%s but the latest is v%s "
                          "(per %s) - stale public claim about the tag set"
                          % (claim, basis_str, basis_label))
            else:
                reason = ("README tags-claim names v%s ahead of anything the "
                          "tree knows (latest v%s per %s) - the README "
                          "asserts a release that does not exist"
                          % (claim, basis_str, basis_label))
            checks.append({'name': 'tag_claim_current', 'ok': current,
                           'reason': reason})
    return {'ok': all(c['ok'] for c in checks), 'checks': checks,
            'banner': banner, 'tag_claim': claim, 'newest_tag': newest_name,
            'describe': describe}


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


# --- SYN-V2 G2: observed graph truth agreement -------------------------------
# This is an offline source-to-receipt check. Only an explicitly supplied
# runtime build is compared; importing this module never imports hou or runs it.
import ast as _ast
import hashlib as _hashlib

GRAPH_SOURCE_PATHS = (
    'python/synapse/host/graph_builder.py',
    'python/synapse/host/existence_adapter.py',
    'python/synapse/host/graph_oracle.py',
)
GRAPH_RECEIPT_PATH = 'harness/notes/graph_truth_22.0.417.json'
GRAPH_QUALIFIED_BUILDS = ('22.0.400', '22.0.417')
GRAPH_RECEIPT_PATHS = {
    build: 'harness/notes/graph_truth_%s.json' % build
    for build in GRAPH_QUALIFIED_BUILDS
}
GRAPH_REQUIRED_CHECKS = (
    'runtime', 'environment_isolation', 'symbols', 'oracles',
    'proposal_rejections', 'build_readback', 'unknown_proposal',
    'toctou_refusal', 'failure_cleanup', 'scope_cleanup',
)
_GRAPH_STAMP_RE = re.compile(r'^GRAPH-TRUTH-BUILD:[ \t]*(\d+\.\d+\.\d+)[ \t]*$', re.M)

def _graph_ast_dump(node):
    """Use the compact receipt format on Python 3.11 through 3.14.

    Python 3.13 changed ast.dump() to omit empty list fields. Walk actual
    fields instead of rewriting dump text: string constants and function
    docstrings can themselves contain text such as ", keywords=[]".
    """
    if isinstance(node, _ast.AST):
        fields = []
        for name, value in _ast.iter_fields(node):
            if value is None and getattr(type(node), name, ...) is None:
                continue
            if isinstance(value, list) and not value:
                continue
            fields.append('%s=%s' % (name, _graph_ast_dump(value)))
        return '%s(%s)' % (type(node).__name__, ', '.join(fields))
    if isinstance(node, list):
        return '[%s]' % ', '.join(_graph_ast_dump(value) for value in node)
    return repr(node)


def graph_implementation_sha256(source):
    """Hash the executed AST, excluding only its module truth documentation.

    Comments and source locations do not affect the hash. Function docstrings,
    constants and all executable statements remain bound to the runtime receipt.
    """
    tree = _ast.parse(source)
    if (tree.body and isinstance(tree.body[0], _ast.Expr)
            and isinstance(tree.body[0].value, _ast.Constant)
            and isinstance(tree.body[0].value.value, str)):
        tree.body.pop(0)
    return _hashlib.sha256(
        _graph_ast_dump(tree).encode('utf-8')).hexdigest()


def _graph_build_agreement(runtime_build=None, receipt_path=None, repo_root=None):
    """Check source stamps and implementations against the qualifying receipt.

    Missing or incomplete evidence is UNKNOWN and never successful. Observable
    disagreement is FAIL. PASS qualifies only the recorded headless fixtures;
    live GUI behavior, catalogs and daemon availability are outside this check.
    """
    root = _os.fspath(repo_root) if repo_root is not None else _REPO_ROOT
    default_path = GRAPH_RECEIPT_PATHS.get(runtime_build, GRAPH_RECEIPT_PATH)
    path = _os.fspath(receipt_path) if receipt_path is not None else default_path
    if not _os.path.isabs(path):
        path = _os.path.join(root, path)
    result = {
        'ok': False, 'status': 'UNKNOWN', 'reason': '',
        'build': None, 'stamps': {}, 'artifact': _os.path.abspath(path),
        'scope': 'recorded headless graph fixtures and current source only',
        'runtime_comparison': {'status': 'UNKNOWN', 'build': runtime_build},
    }

    def finish(status, reason):
        result.update(ok=status == 'PASS', status=status, reason=reason)
        return result

    try:
        with open(path, encoding='utf-8-sig') as stream:
            receipt = _json.load(stream)
    except (OSError, ValueError) as exc:
        return finish('UNKNOWN', 'receipt unavailable or malformed: %s' % exc)
    if not isinstance(receipt, dict) or receipt.get('schema') != 'synapse.graph_truth/v1':
        return finish('UNKNOWN', 'missing or unsupported graph receipt schema')
    build = receipt.get('build')
    if not isinstance(build, str) or not re.fullmatch(r'\d+\.\d+\.\d+', build):
        return finish('UNKNOWN', 'receipt has no valid runtime build')
    result['build'] = build
    if build not in GRAPH_QUALIFIED_BUILDS:
        return finish('FAIL', 'receipt build is not declared by the source')
    if receipt.get('status') != 'PASS':
        status = 'FAIL' if receipt.get('status') == 'FAIL' else 'UNKNOWN'
        return finish(status, 'receipt is not a passing observation')
    checks = receipt.get('checks')
    if not isinstance(checks, dict):
        return finish('UNKNOWN', 'receipt has no check observations')
    for name in GRAPH_REQUIRED_CHECKS:
        item = checks.get(name)
        if not isinstance(item, dict) or item.get('status') != 'PASS':
            status = 'FAIL' if isinstance(item, dict) and item.get('status') == 'FAIL' else 'UNKNOWN'
            return finish(status, 'required check is not PASS: %s' % name)
    if checks['runtime'].get('build') != build:
        return finish('FAIL', 'runtime observation disagrees with receipt build')
    symbols = receipt.get('symbols')
    if (not isinstance(symbols, list) or not symbols
            or not all(isinstance(s, dict) and s.get('owner') and s.get('member')
                       and s.get('present') is True for s in symbols)
            or checks['symbols'].get('observations') != len(symbols)):
        return finish('UNKNOWN', 'required dir() observations are incomplete')
    seeds = receipt.get('seeds')
    if not isinstance(seeds, list) or not seeds:
        return finish('UNKNOWN', 'runtime-stamped proposal fixtures are missing')
    if not all(isinstance(s, dict) and s.get('houdini_version_stamp') == build
               for s in seeds):
        return finish('FAIL', 'proposal fixture build disagrees with receipt')
    sources = receipt.get('source')
    if not isinstance(sources, dict):
        return finish('UNKNOWN', 'receipt has no implementation hashes')
    for relative in GRAPH_SOURCE_PATHS:
        entry = sources.get(relative)
        expected = entry.get('implementation_sha256') if isinstance(entry, dict) else None
        if not isinstance(expected, str) or not re.fullmatch(r'[a-f0-9]{64}', expected):
            return finish('UNKNOWN', 'implementation hash missing or malformed: %s' % relative)
        try:
            with open(_os.path.join(root, relative), encoding='utf-8-sig') as stream:
                source = stream.read()
        except (OSError, UnicodeError) as exc:
            return finish('UNKNOWN', 'source unavailable: %s (%s)' % (relative, exc))
        stamps = _GRAPH_STAMP_RE.findall(source)
        if (tuple(sorted(stamps)) != GRAPH_QUALIFIED_BUILDS
                or source.count('GRAPH-TRUTH-BUILD:') != len(GRAPH_QUALIFIED_BUILDS)):
            return finish('FAIL', 'source needs one stamp per qualified build: %s' % relative)
        result['stamps'][relative] = sorted(stamps)
        if build not in stamps:
            return finish('FAIL', 'source stamp disagrees with receipt: %s' % relative)
        try:
            observed = graph_implementation_sha256(source)
        except (SyntaxError, ValueError) as exc:
            return finish('FAIL', 'source cannot be parsed: %s (%s)' % (relative, exc))
        if observed != expected:
            return finish('FAIL', 'implementation changed since qualification: %s' % relative)
    if runtime_build is not None:
        if runtime_build != build:
            result['runtime_comparison']['status'] = 'FAIL'
            return finish('FAIL', 'requested runtime %s != observed build %s'
                          % (runtime_build, build))
        result['runtime_comparison']['status'] = 'PASS'
    return finish('PASS', 'source stamps and implementations match the observed graph receipt')


def graph_agreement(runtime_build=None, receipt_path=None, repo_root=None):
    """Check one requested build, or every declared build for an offline audit.

    A supplied receipt is checked directly. With no runtime/receipt argument,
    every declared build needs a complete matching receipt; a second stamp alone
    cannot qualify a build. This never discovers or claims a live runtime.
    """
    if runtime_build is not None or receipt_path is not None:
        return _graph_build_agreement(runtime_build, receipt_path, repo_root)
    results = {
        build: _graph_build_agreement(build, repo_root=repo_root)
        for build in GRAPH_QUALIFIED_BUILDS
    }
    # These are receipt checks, not observations of a currently running process.
    for row in results.values():
        row['runtime_comparison'] = {'status': 'UNKNOWN', 'build': None}
    failures = [row for row in results.values() if row['status'] == 'FAIL']
    unknowns = [row for row in results.values() if row['status'] == 'UNKNOWN']
    selected = (failures or unknowns or [results[GRAPH_QUALIFIED_BUILDS[-1]]])[0]
    result = dict(selected)
    result['checked_builds'] = list(GRAPH_QUALIFIED_BUILDS)
    result['build_results'] = results
    result['scope'] = 'recorded headless graph fixtures for all declared builds and current source only'
    if result['ok']:
        result['reason'] = 'all declared source builds have matching observed receipts'
    return result


# --- G5a: packaged LOP knowledge catalog build-stamp agreement ---------------
# python/synapse/core/lop_knowledge.py:_pkg_catalog_path() resolves the packaged
# catalog by MAJOR only, and its own docstring states the law it stops short of:
#   "NO existence check and NO cross-major fallback here - wrong-major CONTEXT
#    truth is the stale-advice class itself, so a missing per-major file must
#    fail in the loader, loudly."
# The loader validates `schema` plus a blake2b over `content` and never reads
# `houdini_version`, so a WITHIN-major point-release drift passes in silence.
# This is the detector for that gap, built on the _graph_build_agreement shape.
# It REPORTS ONLY: nothing here changes what the loader or GraphValidator does
# on a mismatch. Same posture as the graph check - no `hou`, no live runtime.

LOP_CATALOG_DIR = 'python/synapse/cognitive/tools/data'
LOP_CATALOG_RE = re.compile(r'^lop_solaris_knowledge_(\d+)\.json$')
LOP_REFERENCE_NAME = 'h%s_symbol_table.json'
_LOP_BUILD_RE = re.compile(r'^(\d+)\.\d+\.\d+$')


def _houdini_version_stamp(path):
    """(build, reason) for a JSON artifact's ``houdini_version`` stamp."""
    try:
        with open(path, encoding='utf-8-sig') as stream:
            data = _json.load(stream)
    except (OSError, ValueError) as exc:
        return None, 'unreadable or malformed (%s)' % exc
    if not isinstance(data, dict):
        return None, 'artifact is not a JSON object'
    build = data.get('houdini_version')
    if not isinstance(build, str) or not _LOP_BUILD_RE.fullmatch(build):
        return None, 'no valid houdini_version stamp'
    return build, 'stamped %s' % build


def _lop_catalog_row(root, major, filename):
    """One catalog against the same-major introspected symbol table."""
    path = _os.path.join(root, LOP_CATALOG_DIR, filename)
    reference_name = LOP_REFERENCE_NAME % major
    reference_path = _os.path.join(root, LOP_CATALOG_DIR, reference_name)
    row = {'status': 'UNKNOWN', 'reason': '', 'major': major,
           'catalog': _os.path.abspath(path), 'catalog_build': None,
           'reference': _os.path.abspath(reference_path),
           'reference_build': None}

    def finish(status, reason):
        row.update(status=status, reason=reason)
        return row

    build, why = _houdini_version_stamp(path)
    if build is None:
        return finish('UNKNOWN', 'catalog %s: %s' % (filename, why))
    row['catalog_build'] = build
    if _LOP_BUILD_RE.fullmatch(build).group(1) != major:
        return finish('FAIL', 'catalog %s is stamped %s, a different major'
                              % (filename, build))
    reference, why = _houdini_version_stamp(reference_path)
    if reference is None:
        return finish('UNKNOWN', 'reference %s: %s' % (reference_name, why))
    row['reference_build'] = reference
    if reference != build:
        return finish('FAIL', 'catalog %s is stamped %s but the introspected '
                              'runtime authority %s is stamped %s'
                              % (filename, build, reference_name, reference))
    return finish('PASS', 'catalog %s agrees with %s at %s'
                          % (filename, reference_name, build))


def lop_catalog_agreement(runtime_build=None, repo_root=None):
    """Verdict for every packaged LOP knowledge catalog's build stamp.

    Each ``lop_solaris_knowledge_<major>.json`` is compared with the same-major
    ``h<major>_symbol_table.json`` beside it - the introspected existence
    authority CLAUDE.md names, regenerated on the target build by ``hython
    host/introspect_runtime.py``. Both are per-major artifacts harvested from a
    running build, so a point-release disagreement between them is a catalog
    harvested on a build the runtime has moved past.

    Observable disagreement is FAIL. Missing or unstamped evidence is UNKNOWN
    and never PASS. No live runtime is discovered or claimed: ``runtime_build``
    is compared only when a caller supplies one.
    """
    root = _os.fspath(repo_root) if repo_root is not None else _REPO_ROOT
    directory = _os.path.join(root, LOP_CATALOG_DIR)
    result = {
        'ok': False, 'status': 'UNKNOWN', 'reason': '', 'catalogs': {},
        'directory': _os.path.abspath(directory),
        'scope': 'committed per-major catalog stamps against the same-major '
                 'introspected symbol table only',
        'runtime_comparison': {'status': 'UNKNOWN', 'build': runtime_build},
    }

    def finish(status, reason):
        result.update(ok=status == 'PASS', status=status, reason=reason)
        return result

    try:
        names = sorted(_os.listdir(directory))
    except OSError as exc:
        return finish('UNKNOWN', 'catalog directory unavailable: %s' % exc)
    for name in names:
        matched = LOP_CATALOG_RE.match(name)
        if matched:
            result['catalogs'][matched.group(1)] = _lop_catalog_row(
                root, matched.group(1), name)
    rows = result['catalogs']
    if not rows:
        return finish('UNKNOWN', 'no packaged LOP knowledge catalog to compare')

    if runtime_build is not None:
        matched = (_LOP_BUILD_RE.fullmatch(runtime_build)
                   if isinstance(runtime_build, str) else None)
        if matched is None:
            result['runtime_comparison']['status'] = 'FAIL'
            return finish('FAIL', 'requested runtime build is not X.Y.Z: %r'
                                  % (runtime_build,))
        row = rows.get(matched.group(1))
        if row is None or row['catalog_build'] is None:
            return finish('UNKNOWN', row['reason'] if row else
                          'no packaged catalog for requested major %s'
                          % matched.group(1))
        if row['catalog_build'] != runtime_build:
            result['runtime_comparison']['status'] = 'FAIL'
            return finish('FAIL', 'requested runtime %s != catalog stamp %s'
                                  % (runtime_build, row['catalog_build']))
        result['runtime_comparison']['status'] = 'PASS'

    failures = [row for row in rows.values() if row['status'] == 'FAIL']
    unknowns = [row for row in rows.values() if row['status'] == 'UNKNOWN']
    if failures:
        return finish('FAIL', failures[0]['reason'])
    if unknowns:
        return finish('UNKNOWN', unknowns[0]['reason'])
    return finish('PASS', 'every packaged catalog agrees with its same-major '
                          'introspected runtime authority')


def _lop_catalog_cli(argv):
    # A separate entry like _graph_cli: no Git, no Houdini, no version chain.
    # No --fix is accepted: a stale stamp is repaired by re-harvesting the
    # catalog on the running build, never by editing the number.
    import argparse
    parser = argparse.ArgumentParser(
        description='Check packaged LOP catalog build stamps without Houdini.')
    parser.add_argument('--lop-catalog-only', action='store_true', required=True)
    parser.add_argument('--runtime-build')
    args = parser.parse_args(argv)
    result = lop_catalog_agreement(args.runtime_build)
    print(_json.dumps(result, indent=2))
    return 0 if result['ok'] else 1


def _graph_cli(argv):
    # A separate entry returns before legacy version/public checks (which use
    # Git). No --fix is accepted: a receipt cannot be repaired by changing data.
    import argparse
    parser = argparse.ArgumentParser(description='Check recorded graph truth without Git or Houdini.')
    parser.add_argument('--graph-only', action='store_true', required=True)
    parser.add_argument('--runtime-build')
    parser.add_argument('--graph-receipt')
    args = parser.parse_args(argv)
    result = graph_agreement(args.runtime_build, args.graph_receipt)
    print(_json.dumps(result, indent=2))
    return 0 if result['ok'] else 1



if __name__ == '__main__':
    if '--graph-only' in sys.argv[1:]:
        sys.exit(_graph_cli(sys.argv[1:]))

    if '--lop-catalog-only' in sys.argv[1:]:
        sys.exit(_lop_catalog_cli(sys.argv[1:]))

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

    # REACH R2: --fix also heals a stale 'tags: vX is latest' claim forward.
    healed = _fix_tag_claim(canonical) if fix else None
    if healed:
        print(f'  set readme_tag_claim {healed} -> {canonical}')

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

    # REACH R2: the public-face gate, additive alongside the version chain and
    # the APEX gate. Reported always; gates the exit. Computed AFTER the fix
    # block so --fix output reflects the healed state.
    public = public_agreement(canonical=vals['VERSION'])
    for c in public['checks']:
        print('PUBLIC  %s %s  (%s)'
              % ('ok ' if c['ok'] else 'RED', c['name'], c['reason']))
    print('PUBLIC  banner=%s  tag_claim=%s  newest_tag=%s  describe=%s'
          % (public['banner'], public['tag_claim'],
             public['newest_tag'], public['describe']))

    # A check that can fail. It failed on this tree before --fix, twice - once on
    # __version__ and once on pyproject (R80: build it, or strike the ruling
    # that ordered it. This one gets built.) WA1-TRUTH adds the apex gate.
    # REACH R2 adds the public-face gate.
    # G2 adds graph receipt agreement without weakening the earlier gates.
    graph = graph_agreement()
    print('GRAPH   %s  build=%s  (%s)'
          % (graph['status'], graph['build'], graph['reason']))

    # G5a: the packaged LOP catalog stamp, reported beside the others and
    # DELIBERATELY ABSENT from the exit gate below. harness/finalize.ps1:105
    # runs this file in the release path, and the shipped h22 catalog is in
    # observed drift right now, so gating here would stop releases on a harvest
    # that is nobody's current work. `--lop-catalog-only` exits 1 on FAIL for a
    # caller that wants the gate; wire it into the line below once the 22.x
    # catalog is re-harvested on the running build.
    lop = lop_catalog_agreement()
    print('LOPCAT  %s  (%s)' % (lop['status'], lop['reason']))
    sys.exit(0 if (agree and apex['ok'] and public['ok'] and graph['ok']) else 1)
