"""M1 truth contract, pinned registry-wide (hardening report 2026-06-09, §3 + §5 M1 item 2).

THE RULE: a tool result may not claim an outcome the handler did not observe.
Success requires a verified effect (cooked / stat'd / read back) OR a result
that says proposed / scaffolded / unverified.

The report sketched this as "grep every handler's success path" -- that is
unimplementable as literal grep: ``success=True`` is attached structurally by
``handle()`` to ANY non-raising handler (it carries zero outcome semantics),
106 of 117 handlers return claim-free data dicts, and the worst fictions
(bake / kernel scaffolds, uncooked LOPs) carry no claim STRING at all -- the
fiction is the result shape. So this test enforces the contract in three
deterministic layers over the live registry source:

  1. AST claim extraction from result-dict literals (docstrings and comments
     are structurally invisible -- no docstring false positives),
  2. a closed verification-pattern list (an in-source act of observing the
     claimed effect clears the claim),
  3. exact-pin ledgers for the known fictions, asserted EXACTLY -- the test
     fails loud in BOTH directions (new fiction appears -> fix it, don't
     ledger it; a fix lands -> remove the entry). Same coupling contract as
     tests/test_phase0b_consent_posture.py.

SCOPE (deliberate, not oversight): the handler registry only. The panel
recipe fiction ("Executed recipe ...") lives in routing/router.py and is
owned by M1 item 1's own fix + pin (tests/test_routing.py); MCP tool
descriptions in mcp_server.py / _tool_registry.py are doc surface, not
handler results. Per-function, not per-branch: a handler verifying on one
branch and claiming on another would still clear -- static-scan limit;
CRUCIBLE and live probes remain the semantic backstop.

Headless: pure source scan via inspect.getsource (precedent:
test_phase0b_consent_posture.py) + ast.walk (precedent:
test_moneta_fc4_audit.py). No hou required -- import guards handle absence.
"""

import ast
import inspect
import re
import textwrap

from synapse.server.handlers import SynapseHandler

# ---------------------------------------------------------------------------
# Vocabulary (closed lists -- additions are review decisions, not conveniences)
# ---------------------------------------------------------------------------

# Result-dict keys whose string values constitute outcome claims.
MESSAGE_KEYS = frozenset({"message", "note", "summary", "description", "detail"})

# Status values that assert a completed/active outcome. "ok"/"error" are
# deliberately excluded -- neutral results never trip the scan.
CONFIDENT_STATUSES = frozenset({
    "configured", "baked", "applied", "executed", "enabled", "rendered",
    "exported", "submitted", "completed", "installed", "cooked", "cooking",
    "created", "cancelled", "paused", "resumed", "dirtied", "generated",
    "stopped", "active", "monitoring",
})

# Confident outcome verbs -- applied to MESSAGE_KEYS values only.
CONFIDENT_VERB_RE = re.compile(
    r"\b(executed|configured|baked|applied|enabled|rendered|exported"
    r"|submitted|completed|denoised|optimized|installed|wrote|written|saved)\b",
    re.I,
)

# Honest markers: the result says it did NOT verify the outcome.
HONEST_STATUSES = frozenset({
    "proposed", "scaffolded", "unverified", "preview", "pending", "dry_run",
})
HONEST_MARKER_RE = re.compile(r"scaffold|unverified|proposed|dry[ _]run", re.I)

# In-source acts of observing the claimed effect. Keep this list tight --
# generous patterns (e.g. ".eval(") would hollow the test.
VERIFICATION_PATTERNS = (
    ".cook(",              # force-cook readback (USD mutators, LOPs)
    "cookWorkItems(",      # PDG cook
    "generateStaticItems(",
    "executeGraph(",
    "cancelCook(",
    "pauseCook(",
    "resumeCook(",
    "dirtyWorkItems(",
    "dirtyAllTasks(",
    ".dirtyTasks(",
    "performUndo(",        # rollback path = failure observed
    "performRedo(",
    "os.path.exists(",
    "os.path.isfile(",
    "os.path.isdir(",
    "os.stat(",
    ".exists()",
    ".stat()",
    "st_size",
    "workItems",           # work-item readback after generate/cook
    "addEventHandler(",    # live monitoring is its own observation
    "removeEventHandler(",
    ".errors()",
    ".warnings()",
)

# ---------------------------------------------------------------------------
# Seed ledgers (exact pins -- remove the entry in the same PR as the fix)
# ---------------------------------------------------------------------------

# Claims verified OUTSIDE the handler's visible source. Entries require
# cmd -> one-line reason naming where the verification lives. Seeded EMPTY:
# every currently-verifying claimant self-clears via VERIFICATION_PATTERNS.
VERIFIED_ALLOWLIST = {}

# Vocabulary-visible fictions awaiting their fix.
PENDING_FICTIONS = {
    "tops_configure_scheduler": (
        "report §3 #6 residual -- non-local scheduler_type now fails loudly, "
        "but the local path still returns status:'configured' while parm sets "
        "are silently skipped when maxprocs/pdg_workingdir are missing (no "
        "readback). Remove with the parm-verify fix."
    ),
}

# The string-less fictions a vocabulary scan cannot see: the result SHAPE
# implies an outcome the handler never observed. Pinned as explicit debt;
# the M2 cook-and-verify work (report §5 item 4) retires both entries.
# (cops_bake_textures / reaction_diffusion / pixel_sort exited this ledger
# when the M1 wave added scaffolded/honest markers to their results.)
SHAPE_FICTION_DEBT = {
    "manage_collection": "report §3 #8 -- generated LOP never cooked",
    "configure_light_linking": "report §3 #8 -- generated LOP never cooked",
}

# ---------------------------------------------------------------------------
# Enumeration + claim extraction
# ---------------------------------------------------------------------------

_handler = SynapseHandler()
_reg = _handler._registry


def _handler_map():
    """registry -> {distinct function: [command names]} (aliases deduped).

    Aliases are appended after canonicals in _register_handlers, so cmds[0]
    is the canonical name by registration order.
    """
    funcs = {}
    for cmd in _reg.registered_types:
        fn = _reg.get(cmd)
        key = getattr(fn, "__func__", fn)
        funcs.setdefault(key, []).append(cmd)
    return funcs


def _string_values(node):
    """Yield extractable string values: constants, f-string constant parts,
    and both branches of a conditional ('cooked' if blocking else 'cooking')."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, ast.JoinedStr):
        parts = [
            v.value
            for v in node.values
            if isinstance(v, ast.Constant) and isinstance(v.value, str)
        ]
        if parts:
            yield "".join(parts)
    elif isinstance(node, ast.IfExp):
        yield from _string_values(node.body)
        yield from _string_values(node.orelse)


def _extract_claims(src):
    """(key, text) pairs from result-dict literals in the handler source."""
    tree = ast.parse(textwrap.dedent(src))
    claims = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for k, v in zip(node.keys, node.values):
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                continue
            key = k.value
            if key == "status" or key in MESSAGE_KEYS:
                for text in _string_values(v):
                    claims.append((key, text))
    return claims


def _confident_claims(claims):
    out = []
    for key, text in claims:
        if key == "status":
            if text.strip().lower() in CONFIDENT_STATUSES:
                out.append((key, text))
        elif CONFIDENT_VERB_RE.search(text):
            out.append((key, text))
    return out


def _is_honest(claims):
    for key, text in claims:
        if key == "status" and text.strip().lower() in HONEST_STATUSES:
            return True
        if HONEST_MARKER_RE.search(text):
            return True
    return False


def _is_verified(src):
    return any(pat in src for pat in VERIFICATION_PATTERNS)


# ---------------------------------------------------------------------------
# The four pins
# ---------------------------------------------------------------------------


def test_no_unobserved_outcome_claims():
    flagged = {}
    for fn, cmds in _handler_map().items():
        canonical = cmds[0]
        if canonical in VERIFIED_ALLOWLIST:
            continue
        src = inspect.getsource(fn)
        claims = _extract_claims(src)
        confident = _confident_claims(claims)
        if not confident:
            continue
        if _is_verified(src) or _is_honest(claims):
            continue
        flagged[canonical] = confident

    new = set(flagged) - set(PENDING_FICTIONS)
    assert not new, (
        f"Handler(s) {sorted(new)} claim outcomes "
        f"({ {c: flagged[c] for c in sorted(new)} }) with no visible "
        "observation (cook/stat/readback) and no honest marker "
        "(proposed/scaffolded/unverified). Verify the effect or say so in "
        "the result -- do NOT silently allowlist."
    )
    fixed = set(PENDING_FICTIONS) - set(flagged)
    assert not fixed, (
        f"Fix landed for {sorted(fixed)} -- remove the entry from "
        "PENDING_FICTIONS in this same PR (the ledger pins reality, both "
        "directions)."
    )


def test_shape_fiction_debt_is_current():
    for cmd, why in SHAPE_FICTION_DEBT.items():
        fn = _reg.get(cmd)
        assert fn is not None, f"SHAPE_FICTION_DEBT key {cmd!r} is not registered"
        src = inspect.getsource(getattr(fn, "__func__", fn))
        still_fictional = not _is_verified(src) and not HONEST_MARKER_RE.search(src)
        assert still_fictional, (
            f"{cmd} ({why}) now verifies or marks honestly -- the debt is "
            "paid. Remove its SHAPE_FICTION_DEBT entry in this same PR."
        )


def test_ledger_keys_are_registered():
    for ledger_name, ledger in (
        ("PENDING_FICTIONS", PENDING_FICTIONS),
        ("SHAPE_FICTION_DEBT", SHAPE_FICTION_DEBT),
        ("VERIFIED_ALLOWLIST", VERIFIED_ALLOWLIST),
    ):
        for cmd in ledger:
            assert _reg.has(cmd), (
                f"{ledger_name} key {cmd!r} is not a registered command -- "
                "stale entry after a handler rename?"
            )


def test_scan_surface_is_alive():
    """Anti-vacuity: a conformance test that silently scans nothing is itself
    an unobserved-outcome claim."""
    funcs = _handler_map()
    assert len(funcs) >= 110, (
        f"Only {len(funcs)} distinct handlers enumerated -- the registry walk "
        "broke (expected >= 110)."
    )
    for fn, cmds in funcs.items():
        src = inspect.getsource(fn)
        assert src.strip(), f"Empty source for handler of {cmds[0]!r}"
