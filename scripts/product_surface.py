"""scripts/product_surface.py -- the one definition of what "the product" is.

WHY THIS EXISTS
---------------
The release ritual proves a release carries no product change with

    git diff --stat v<prev> v<new> -- python installer

and every release since v5.70.1 copy-forwarded that pathspec into its own
``compose_assets.py`` (release-5.70.1:143, -5.71.0:143, -5.72.0:146,
-5.73.0, -5.74.0:242). The pathspec is narrower than the sentence it licenses.

Nineteen tracked ``.py`` files live at the repository root, outside both trees.
Seven of them are the shipped MCP surface -- including ``mcp_server.py``, the
exact file ``.mcp.json`` launches (``{"command": "python", "args":
["mcp_server.py"]}``).

MEASURED BLIND SPOT (2026-09-18). Commit ``c6221f3b`` (2026-08-05),
*"hardening(shipping): own the dispatch executor -- asyncio.run() was disabling
every MCP tool call under Houdini"*, changed 65 lines of ``mcp_server.py`` and
nothing under ``python/`` or ``installer/``:

    git diff --stat c6221f3b^ c6221f3b -- python installer      -> EMPTY
    git diff --stat c6221f3b^ c6221f3b -- <PRODUCT_PATHSPEC>    -> mcp_server.py | 58 +, 7 -

The narrow pathspec reports "product unchanged" over a fix to the MCP entry
point. That is the gate this module closes.

HOUSE RULES HONOURED
--------------------
* A pathspec term matching no tracked file is UNKNOWN, and **UNKNOWN REFUSES**.
  An empty diff from an empty pathspec prints identically to an empty diff from
  a tree that did not move, and git reports neither -- an abstention read as a
  pass. Every term is resolved before any diff is trusted.
* **The command string reported is the command that ran.** The copies in
  ``release-5.71.0/compose_assets.py`` record a ``check`` label naming
  ``v5.70.0`` (:143) while the subprocess one line below runs ``v5.70.1``
  (:144); ``release-5.72.0`` repeats it. The published
  ``installer-verification.json`` therefore carries a check string that is not
  the check that produced its result.
* Paths resolve from this file's location, so it runs correctly from any CWD
  (same reason ``sync_version.py`` does it).

PRODUCT vs NON-SURFACE -- NOT THE SAME DISTINCTION
--------------------------------------------------
``sync_version.py`` declares ``python/synapse/_vendor/*`` a NON-surface: upstream
packages do not carry SYNAPSE's version string, so version sync must skip them.
That does **not** make them non-product. Vendored code ships in the payload; if
it moves, the product moved. ``_vendor/`` is inside this pathspec deliberately.

Usage:
  python scripts/product_surface.py                    # resolve + self-check
  python scripts/product_surface.py --diff <a> <b>     # the product delta a..b
  python scripts/product_surface.py --list             # what counts as product

Exit 0 = checked and clean. Exit 1 = a term is dead, or the diff is non-empty
when --expect-empty was asked for. Exit 2 = the state could not be observed.
"""
from __future__ import annotations

import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# THE DEFINITION. One list. Everything that ships and that SYNAPSE authors.
# Anything added here must also be added to the payload, and vice versa.
# ---------------------------------------------------------------------------
PRODUCT_PATHSPEC = [
    "python",           # the package (INCLUDING _vendor -- it ships)
    "installer",        # the Windows setup engine
    "mcp_server.py",    # the stdio MCP entry point .mcp.json launches
    "mcp_tools_*.py",   # the six tool-registration modules
    "install.py",       # root installer entry point
    "run_panel.py",     # panel entry point
]

# Declared NON-product, with the reason each one is out. Scope is a claim too:
# a gate that quietly widens until everything is product reports a change on
# every release and stops meaning anything.
NON_PRODUCT = {
    "harness/": "evidence, boards and drivers; never shipped",
    "tests/":   "not in the payload",
    "docs/":    "shipped as text, tracked by the docs surfaces, not the product delta",
    "tools/":   "developer tooling for this repo only",
    "scripts/": "release and conformance tooling, including this file",
    "rag/":     "corpus; has its own stamp and its own size problem",
    ".claude/": "agent definitions",
    ".synapse/": "local state and contracts",
}


def _git(*args: str) -> str:
    """Run git in the repo. Raises on failure -- an unobservable state is not a
    clean state."""
    out = subprocess.run(
        ["git", "-C", REPO, *args],
        capture_output=True, text=True, errors="replace",
    )
    if out.returncode != 0:
        raise RuntimeError(
            "git %s failed (%d): %s" % (" ".join(args), out.returncode, out.stderr.strip())
        )
    return out.stdout


def tracked(term: str) -> list:
    """Tracked files matching one pathspec term."""
    return [ln for ln in _git("ls-files", "--", term).splitlines() if ln.strip()]


def resolve() -> list:
    """(term, count) for every term. A zero is the abstention trap."""
    return [(t, len(tracked(t))) for t in PRODUCT_PATHSPEC]


def command(a: str, b=None) -> str:
    """The exact command `delta` runs, as a string. Reported verbatim so a
    recorded check can never name a different one than it ran.

    ``b=None`` means the WORKING TREE, and the command string omits a second ref
    accordingly. The release ritual needs that form: on the pre-commit pass the
    version bump is unstaged, so ``PREV..HEAD`` cannot see it and reports an
    empty delta -- which reads as "product unchanged" when it actually means
    "wrong pair of trees". Writing "PREV HEAD" here while running one ref is the
    same defect from the other side: a check string naming a command nobody ran.
    """
    refs = a if b is None else "%s %s" % (a, b)
    return "git diff --stat %s -- %s" % (refs, " ".join(PRODUCT_PATHSPEC))


def delta(a: str, b=None):
    """(command, stat, changed_files) for the product surface.

    Two refs compares those trees; ``b=None`` compares *a* to the working tree.
    """
    refs = [a] if b is None else [a, b]
    stat = _git("diff", "--stat", *refs, "--", *PRODUCT_PATHSPEC).rstrip()
    names = [ln for ln in _git("diff", "--name-only", *refs, "--", *PRODUCT_PATHSPEC).splitlines() if ln.strip()]
    return command(a, b), stat, names


def _self_check(verbose: bool = True) -> int:
    try:
        rows = resolve()
    except RuntimeError as exc:
        print("UNKNOWN: %s" % exc)
        return 2
    dead = [t for t, n in rows if n == 0]
    total = sum(n for _, n in rows)
    if verbose:
        for t, n in rows:
            print("  %-16s %5d tracked files%s" % (t, n, "   <-- DEAD TERM" if n == 0 else ""))
        print("  %-16s %5d" % ("TOTAL", total))
    if dead:
        print("REFUSE: %d pathspec term(s) match no tracked file: %s" % (len(dead), ", ".join(dead)))
        print("        An empty diff from a dead term is an abstention, not a pass.")
        return 1
    if verbose:
        print("verdict=PASS  (%d terms, %d tracked files)" % (len(rows), total))
    return 0


def main(argv: list) -> int:
    if "--list" in argv:
        print("PRODUCT:")
        for t, n in resolve():
            print("  %-16s %5d files" % (t, n))
        print("\nDECLARED NON-PRODUCT:")
        for k, why in NON_PRODUCT.items():
            print("  %-16s %s" % (k, why))
        return 0

    if "--diff" in argv:
        i = argv.index("--diff")
        try:
            a, b = argv[i + 1], argv[i + 2]
        except IndexError:
            print("usage: --diff <ref> <ref>")
            return 2
        rc = _self_check(verbose=False)
        if rc:
            return rc
        try:
            cmd, stat, names = delta(a, b)
        except RuntimeError as exc:
            print("UNKNOWN: %s" % exc)
            return 2
        print("command  %s" % cmd)
        print("terms    %d terms, %d tracked files" % (len(PRODUCT_PATHSPEC),
                                                       sum(n for _, n in resolve())))
        if names:
            print("result   %d file(s) changed" % len(names))
            for ln in stat.splitlines():
                print("         %s" % ln)
        else:
            print("result   no product change")
        if "--expect-empty" in argv and names:
            print("verdict=FAIL  (expected no product change)")
            return 1
        print("verdict=PASS")
        return 0

    print("product surface -- resolving every term against the index:")
    return _self_check()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
