"""R107: VERSION and __version__ must agree, and a check must enforce it.

I bumped VERSION to 5.35.0, committed, tagged and pushed - and never touched
__version__, which still read 5.33.0. The health report reads __version__, which
is why it reported a version four releases behind the tag.

harness/finalize.ps1 bumps VERSION and nothing else. The procedure was
underspecified and I followed it correctly to a wrong outcome - the same shape as
R93's `green` with zero commits.
"""
import io, re, sys

VERSION_FILE = 'VERSION'
INIT_FILE = 'python/synapse/__init__.py'
PAT = re.compile(r'__version__\s*=\s*["\']([^"\']+)["\']')


def read_pair():
    # utf-8-SIG, not utf-8. The VERSION file was written with PowerShell's
    # Set-Content -Encoding utf8 during the v5.35.0 release and carries a BOM -
    # the fifth instance of that mistake in two days. Reading it with plain
    # utf-8 pulls \ufeff into the version string, which then compares unequal to
    # everything and crashes any consumer that prints it on a cp1252 console.
    v = open(VERSION_FILE, encoding='utf-8-sig').read().strip()
    m = PAT.search(open(INIT_FILE, encoding='utf-8-sig').read())
    return v, (m.group(1) if m else None)


def strip_bom(path):
    """A BOM in VERSION is itself a defect - anything parsing it gets \ufeff."""
    raw = open(path, 'rb').read()
    if raw[:3] == b'\xef\xbb\xbf':
        with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(raw.decode('utf-8-sig'))
        return True
    return False


if __name__ == '__main__':
    if '--fix' in sys.argv and strip_bom(VERSION_FILE):
        print('stripped a UTF-8 BOM from VERSION')

    v, iv = read_pair()
    print('BEFORE   VERSION=%s   __version__=%s   agree=%s' % (v, iv, v == iv))

    if '--fix' in sys.argv and v != iv:
        t = open(INIT_FILE, encoding='utf-8-sig').read()
        t = PAT.sub('__version__ = "%s"' % v, t, count=1)
        with io.open(INIT_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(t)
        v, iv = read_pair()
        print('AFTER    VERSION=%s   __version__=%s   agree=%s' % (v, iv, v == iv))

    # A check that can fail. It failed on this tree before --fix (R80: build it
    # or strike the ruling that ordered it - this one gets built).
    sys.exit(0 if v == iv else 1)
