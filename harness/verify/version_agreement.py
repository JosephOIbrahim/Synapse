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
import io, re, sys

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

    # A check that can fail. It failed on this tree before --fix, twice - once on
    # __version__ and once on pyproject (R80: build it, or strike the ruling
    # that ordered it. This one gets built.)
    sys.exit(0 if agree else 1)
