"""W3-EVOLVE — charmeleon->charizard store consolidation.

RETIRED 2026-08-20 (RETIREMENT agent, refactor/memory-v51-substrates): this file
used to pin the manual, human-token-gated `synapse_evolve_memory` /
`apply_consolidation` mechanism -- a "preview, copy the approval_token, paste it
back to approve" interactive stage. THE LOOP v5.1 mandates a decay-driven memory
lifecycle with no manual prune scripts and no interactive evolution stages, so
that mechanism was retired: the `synapse_evolve_memory` MCP tool (mcp/
_tool_registry.py), the `_handle_evolve_memory` / `_handle_evolve_consolidate`
handlers (server/handlers_memory.py), and `apply_consolidation`'s `approval_token`
string-gate (memory/consolidation.py) -- including the function itself, which had
no caller left once the tool and handler were gone -- are all deleted. The
sanctioned replacement is the decay-driven `_handle_sleep_pass` /
`store.run_sleep_pass()` path, which carries a real consent gate via the
execution bridge, not a copy-pasted string.

Deleting the code deletes its tests: the 15 acceptance/crucible tests that used
to live here (dry-run audit shape, apply-without-token refusal, protected-
survivor behavior, lossless merge, Moneta honest-degradation) tested a mechanism
that no longer exists. What is asserted below instead is that the manual-gate
surface is GONE (TestEvolveConsolidationRetired) -- a test that fails loudly if
someone reintroduces it without reopening that decision. `plan_consolidation` /
`is_protected` (the pure, read-only half of consolidation.py) were never the
interactive part and survive untouched; they are not re-pinned here.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.memory import consolidation as consolidation_mod  # noqa: E402
from synapse.mcp._tool_registry import TOOL_DEFS  # noqa: E402
from synapse.server.handlers_memory import MemoryHandlerMixin  # noqa: E402


class TestEvolveConsolidationRetired:
    """The subtraction, pinned.

    The manual approval-token gate ran zero times as anything other than a
    human copy-paste step; THE LOOP v5.1 replaces it with decay-driven
    `_handle_sleep_pass`. Reintroducing any of these names silently would
    restore the retired interactive path without reopening that decision, so
    it fails here instead.
    """

    def test_tool_is_absent_from_registry(self):
        names = {t[0] for t in TOOL_DEFS}
        assert "synapse_evolve_memory" not in names, (
            "synapse_evolve_memory was retired 2026-08-20 -- THE LOOP v5.1 "
            "forbids interactive evolution stages. If it is genuinely needed "
            "again, that is a registry decision to reopen, not a re-add."
        )

    def test_handlers_are_gone(self):
        assert not hasattr(MemoryHandlerMixin, "_handle_evolve_memory"), (
            "MemoryHandlerMixin._handle_evolve_memory was retired 2026-08-20 "
            "along with the synapse_evolve_memory tool it served."
        )
        assert not hasattr(MemoryHandlerMixin, "_handle_evolve_consolidate"), (
            "MemoryHandlerMixin._handle_evolve_consolidate was retired "
            "2026-08-20 -- its only caller (_handle_evolve_memory) is gone."
        )

    def test_sleep_pass_handler_survives(self):
        """The sanctioned replacement is untouched by this retirement."""
        assert hasattr(MemoryHandlerMixin, "_handle_sleep_pass")

    def test_no_approval_token_symbol_remains_in_consolidation_module(self):
        src = Path(consolidation_mod.__file__).read_text(encoding="utf-8")
        assert "approval_token" not in src, (
            "approval_token is back in memory/consolidation.py -- the manual "
            "token gate was retired 2026-08-20; reintroducing the symbol "
            "reopens the interactive-approval question this test pins closed."
        )

    def test_apply_consolidation_and_its_exceptions_are_gone(self):
        for name in ("apply_consolidation", "ConsolidationNotApproved",
                     "ConsolidationUnsupported"):
            assert not hasattr(consolidation_mod, name), (
                f"consolidation.{name} was retired 2026-08-20 with the manual "
                "approval-token gate -- it had no caller left once "
                "_handle_evolve_consolidate was removed."
            )

    def test_dry_run_planner_survives_the_cut(self):
        """`plan_consolidation` / `is_protected` are pure and read-only -- they
        were never the interactive half, so they are not retired."""
        assert hasattr(consolidation_mod, "plan_consolidation")
        assert hasattr(consolidation_mod, "is_protected")
