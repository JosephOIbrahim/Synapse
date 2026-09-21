"""Every design token `audit_panel.py` names must exist, and no size may hide from it.

WHY THIS EXISTS. CRIT.md 2026-09-15 ranked change 1 deleted `SIZE_MICRO` from
`designsystem/tokens.py`. `audit_panel.py` kept reading `t.SIZE_MICRO` in its
readability table, so the strict audit died with an AttributeError on its FIRST
table -- and everything below that line, including the A3 seeded-contrast sweep
and two real FAIL rows, never ran again. Nothing noticed for six days, because
no test reads the audit script. The panel spec legs (2026-09-21) found it by
making the audit an acceptance line and watching it fail on master.

WHAT IT PINS. The audit is parsed, never imported (it builds Qt widgets), and
every `<alias>.NAME` attribute it reads through any alias the tokens module is
bound to is asserted to exist. A token deleted out from under the audit now
reddens here instead of silently blinding it at run time.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from synapse.panel.designsystem import tokens

AUDIT = Path(__file__).resolve().parents[1] / "audit_panel.py"


def _aliases_and_names() -> tuple[set[str], set[str]]:
    """Every local name the tokens module is bound to (module level or inside a
    function), and every CONSTANT-looking attribute read through any of them."""
    tree = ast.parse(AUDIT.read_text(encoding="utf-8"))
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("designsystem"):
            aliases |= {a.asname or a.name for a in node.names if a.name == "tokens"}
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.endswith("designsystem.tokens"):
                    aliases.add(a.asname or a.name.split(".")[-1])
    if not aliases:
        pytest.skip("audit_panel.py does not import the tokens module")
    names = {
        n.attr
        for n in ast.walk(tree)
        if isinstance(n, ast.Attribute)
        and isinstance(n.value, ast.Name)
        and n.value.id in aliases
        and n.attr.isupper()
    }
    return aliases, names


def test_audit_panel_reads_only_tokens_that_exist():
    aliases, names = _aliases_and_names()
    assert names, f"found no reads through {sorted(aliases)} in audit_panel.py -- have the aliases changed?"
    missing = sorted(n for n in names if not hasattr(tokens, n))
    assert not missing, (
        "audit_panel.py reads design tokens that no longer exist: "
        + ", ".join(missing)
        + ". The audit crashes on the first one and every check below it stops running. "
        "Drop the dead reference (or restore the token); never leave the audit blind."
    )


def test_every_distinct_size_on_the_ramp_is_audited():
    """Aliases may share a value, but no distinct size may go unprinted: a rung
    the audit never reads is a rung its readability floor cannot police."""
    _, names = _aliases_and_names()
    ramp = {n: getattr(tokens, n) for n in dir(tokens)
            if n.startswith("SIZE_") and isinstance(getattr(tokens, n), int)}
    audited = {ramp[n] for n in names if n in ramp}
    unaudited = sorted(v for v in set(ramp.values()) if v not in audited)
    assert not unaudited, (
        f"these size values exist on the ramp but audit_panel.py never prints them: {unaudited}. "
        f"Ramp is {ramp}; audit reads {sorted(n for n in names if n in ramp)}. "
        "Add a row to the readability table so the audit covers the whole ramp."
    )
