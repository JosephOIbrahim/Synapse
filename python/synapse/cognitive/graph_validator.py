"""Whole-graph validation. Calls IExistenceOracle + IConnectivityOracle via
protocols — ZERO hou IMPORTS. Hard failures collect ALL errors, halt, return.
Spec §5 (v3) + amendments 1,3,4,7."""
from __future__ import annotations

from .graph_proposal import (
    GraphProposal,
    NodeKind,
    ValidationIssue,
    ValidationReport,
    ValidationStatus,
)
from .interfaces import IConnectivityOracle, IExistenceOracle


class GraphValidator:
    def __init__(
        self,
        existence: IExistenceOracle,
        connectivity: IConnectivityOracle,
        *,
        live_phases_enabled: bool = False,
    ):
        self._exist = existence
        self._conn = connectivity
        # P3-P5 touch the live runtime / connectivity oracle. They stay dark
        # until Mile 2 flips this on, so Mile 1 runs P1+P2 on mocks alone and
        # existing-node edges defer to P5 instead of being symbol-checked.
        self._live_phases_enabled = live_phases_enabled

    def validate(self, p: GraphProposal) -> ValidationReport:
        errors: list[ValidationIssue] = []
        advisories: list[ValidationIssue] = []

        # --- MILE 1: NEW-node symbol + parameter checks ---
        errors += self._phase1_symbols(p)
        errors += self._phase2_parameters(p)

        # --- MILE 2: live oracle phases (gated until connectivity is real) ---
        if self._live_phases_enabled:
            errors += self._phase3_connections(p, advisories)
            errors += self._phase4_structural(p)
            errors += self._phase5_context(p)

        status = ValidationStatus.VALID if not errors else ValidationStatus.INVALID
        return ValidationReport(
            status=status,
            proposal_id=p.proposal_id,
            errors=errors,
            advisories=advisories,
        )

    def _stamp(self, p: GraphProposal, msg: str) -> str:
        # The runtime version travels with every issue (DoD §12) so a
        # stale-runtime proposal is auditable from the error text alone.
        return f"{msg} [houdini {p.houdini_version_stamp or 'unstamped'}]"

    # ---- Phase 1 — symbol check (MILE 1) ----
    def _phase1_symbols(self, p: GraphProposal) -> list[ValidationIssue]:
        # NEW nodes only. EXISTING nodes carry a live scene_path and are checked
        # for real existence in P5 (resolve_node_type) — symbol-checking them
        # here would falsely reject a node the artist already has. Collect every
        # bad type in one pass so the model sees all hallucinations at once.
        issues: list[ValidationIssue] = []
        for n in p.nodes:
            if n.kind is not NodeKind.NEW:
                continue
            if not self._exist.node_type_exists(n.node_type, n.node_category):
                issues.append(ValidationIssue(
                    where=n.node_id,
                    message=self._stamp(
                        p, f"unknown node_type '{n.node_type}' for category '{n.node_category}'"
                    ),
                ))
        return issues

    # ---- Phase 2 — parameter check (MILE 1) ----
    def _phase2_parameters(self, p: GraphProposal) -> list[ValidationIssue]:
        # NEW nodes only; NAME existence only (override VALUES are out of scope at
        # Mile 1). EXISTING nodes must carry no overrides per contract, so they are
        # skipped here too. Each unknown parameter is reported, not just the first.
        issues: list[ValidationIssue] = []
        for n in p.nodes:
            if n.kind is not NodeKind.NEW:
                continue
            for parm_name in n.parameter_overrides:
                if not self._exist.parameter_exists(n.node_type, n.node_category, parm_name):
                    issues.append(ValidationIssue(
                        where=n.node_id,
                        message=self._stamp(
                            p, f"node_type '{n.node_type}' has no parameter '{parm_name}'"
                        ),
                    ))
        return issues

    # ---- Phase 3 — connection check, category-aware (MILE 2) ----
    def _phase3_connections(self, p: GraphProposal, advisories: list) -> list[ValidationIssue]:
        # 3a arity (all) · 3b type-compat (typed only) · 3c slot-label advisory · 3d occupied-input guard
        # Use resolve_node_type() for endpoints touching EXISTING nodes. NEVER degrade 3d to a pass.
        raise NotImplementedError("Mile 2 — spec §5.3 + amendments 1,7")

    # ---- Phase 4 — structural, pure logic (MILE 2) ----
    def _phase4_structural(self, p: GraphProposal) -> list[ValidationIssue]:
        # acyclicity (DAG) · new-vs-new name collision · node_category <-> network_type (M1 minor)
        raise NotImplementedError("Mile 2 — spec §5.4 + amendment 4, M1")

    # ---- Phase 5 — context check, host oracle (MILE 2) ----
    def _phase5_context(self, p: GraphProposal) -> list[ValidationIssue]:
        # parent exists/type · every EXISTING scene_path resolves · new-vs-existing-children names
        raise NotImplementedError("Mile 2 — spec §5.5 + amendment 4")
