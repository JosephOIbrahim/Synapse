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

# U.1: the probe-verified connectivity catalog (packaged copy of the
# host/introspect_connectivity.py output). Pure JSON, zero hou — loading it
# keeps this layer host-agnostic. Missing/corrupt degrades to None and P3e
# simply skips (the oracle-backed checks are never weakened).
from ..core.wiring import load_connectivity_catalog, resolve_catalog_entry
# U.5: corpus-authored, probe-cross-checked LOP/Solaris knowledge (ordering rules
# + known-absent types). Same non-strict-skip posture as the connectivity catalog.
from ..core.lop_knowledge import load_lop_catalog

# network_type (GraphProposal.network_type) -> the node categories valid inside it.
# Used by P4 for the node_category<->network_type consistency check. Unknown
# network_types are skipped (no false reject). MAT nodes are VOPs or SHOPs; COP
# spans the legacy Cop2 and the H21 Cop category.
_NETWORK_CATEGORIES: dict[str, set[str]] = {
    "SOP": {"Sop"},
    "VOP": {"Vop"},
    "MAT": {"Vop", "Shop"},
    "DOP": {"Dop"},
    "COP": {"Cop", "Cop2"},
    "SOLARIS": {"Lop"},
}


class GraphValidator:
    def __init__(
        self,
        existence: IExistenceOracle,
        connectivity: IConnectivityOracle,
        *,
        live_phases_enabled: bool = True,
        connectivity_catalog: "dict | None" = None,
        lop_catalog: "dict | None" = None,
    ):
        self._exist = existence
        self._conn = connectivity
        # P3-P5 touch the live runtime / connectivity oracle. Mile 2 is DONE, so
        # they run by default. Mile-1-style callers that only exercise the P1/P2
        # symbol path (and inject a connectivity mock that refuses connectivity
        # calls) opt out explicitly with live_phases_enabled=False.
        self._live_phases_enabled = live_phases_enabled
        # U.1 P3e: probe-verified slot semantics. Default = the packaged catalog
        # (non-strict: unusable -> None -> P3e skips, nothing else changes).
        # Injectable for tests / a future per-build override.
        self._catalog = (connectivity_catalog if connectivity_catalog is not None
                         else load_connectivity_catalog(strict=False))
        # U.5 LOP knowledge (non-strict: unusable -> None -> the LOP phase skips).
        self._lop_catalog = (lop_catalog if lop_catalog is not None
                             else load_lop_catalog(strict=False))

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
            errors += self._lop_ordering_check(p, advisories)

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

    # ---- shared endpoint resolution (P3/P5) ----
    def _endpoint_type(self, node) -> tuple[str, str] | None:
        # (node_type, category) for an edge endpoint. NEW nodes carry their own
        # type+category; EXISTING nodes are introspected via the connectivity
        # oracle (Amendment 1). A resolve failure returns None (not a crash) so
        # the type-dependent checks skip it — P5 owns reporting the bad path.
        if node.kind is NodeKind.NEW:
            return (node.node_type, node.node_category)
        try:
            t, c = self._conn.resolve_node_type(node.scene_path)
            return (str(t), str(c))
        except Exception:  # noqa: BLE001 — any resolve failure defers to P5
            return None

    @staticmethod
    def _overflows(index: int, max_count: int) -> bool:
        # A slot index overflows iff it is negative, or it reaches a FINITE cap.
        # max_count < 0 is the contract's variadic sentinel (the in-repo mock uses
        # -1; live H21 reports a large finite cap e.g. merge=9999, which 'index <
        # max' handles naturally) -> unlimited, never overflows on the high side.
        return index < 0 or (max_count >= 0 and index >= max_count)

    def _safe_occupied(self, scene_path: str, input_index: int) -> bool:
        # 3d HALTS, never degrades: if occupancy cannot be determined we treat the
        # input as OCCUPIED (reject), never as free. A false pass here severs the
        # artist's live wiring — the one place graceful degradation is forbidden.
        try:
            return bool(self._conn.input_is_occupied(scene_path, input_index))
        except Exception:  # noqa: BLE001 — fail-safe to OCCUPIED, never to a pass
            return True

    # ---- Phase 3 — connection check, category-aware (MILE 2) ----
    def _phase3_connections(self, p: GraphProposal, advisories: list) -> list[ValidationIssue]:
        # 3a arity (all) · 3b type-compat (typed only) · 3c slot-label advisory · 3d occupied-input guard.
        # Collects ALL violations (no early-out) so the model sees every wiring fault at once.
        issues: list[ValidationIssue] = []
        by_id = {n.node_id: n for n in p.nodes}
        for e in p.edges:
            src = by_id.get(e.source_node_id)
            tgt = by_id.get(e.target_node_id)
            if src is None or tgt is None:
                missing = e.source_node_id if src is None else e.target_node_id
                issues.append(ValidationIssue(
                    where=missing,
                    message=self._stamp(p, f"edge references unknown node_id '{missing}'"),
                ))
                continue

            st = self._endpoint_type(src)   # None == EXISTING source did not resolve (P5 reports it)
            tt = self._endpoint_type(tgt)   # None == EXISTING target did not resolve (P5 reports it)

            # --- 3a arity: target input index within the type's input capacity ---
            if tt is not None:
                _min_in, max_in = self._conn.input_arity(tt[0], tt[1])
                if self._overflows(e.target_input_index, max_in):
                    issues.append(ValidationIssue(
                        where=tgt.node_id,
                        message=self._stamp(
                            p, f"edge target '{tgt.node_id}' input index "
                               f"{e.target_input_index} exceeds arity (max inputs "
                               f"{max_in}) for type '{tt[0]}'"),
                    ))
                # --- 3c slot-label advisory (NOT an error) ---
                labels = self._conn.input_labels(tt[0], tt[1])
                if labels and 0 <= e.target_input_index < len(labels) and labels[e.target_input_index]:
                    advisories.append(ValidationIssue(
                        where=tgt.node_id,
                        message=self._stamp(
                            p, f"edge wires into the '{labels[e.target_input_index]}' "
                               f"input (index {e.target_input_index}) of '{tgt.node_id}'"),
                    ))

            # --- 3a arity: source output index within the type's output count ---
            if st is not None:
                out_count = self._conn.output_count(st[0], st[1])
                if self._overflows(e.source_output_index, out_count):
                    issues.append(ValidationIssue(
                        where=src.node_id,
                        message=self._stamp(
                            p, f"edge source '{src.node_id}' output index "
                               f"{e.source_output_index} exceeds output count "
                               f"({out_count}) for type '{st[0]}'"),
                    ))

            # --- 3b type-compat: TYPED categories only (VOP/MAT/CHOP) ---
            if st is not None and tt is not None and self._conn.is_typed_category(tt[1]):
                if not self._conn.types_compatible(
                        st[0], e.source_output_index, tt[0], e.target_input_index, tt[1]):
                    issues.append(ValidationIssue(
                        where=tgt.node_id,
                        message=self._stamp(
                            p, f"incompatible wire type: '{st[0]}' output "
                               f"{e.source_output_index} -> '{tt[0]}' input "
                               f"{e.target_input_index} in typed category '{tt[1]}'"),
                    ))

            # --- 3d occupied-input guard: TARGET side, EXISTING nodes only; HALTS ---
            # Amendment 3: the guard is target-side only — outputs fan out freely.
            if tgt.kind is NodeKind.EXISTING and tgt.scene_path:
                if self._safe_occupied(tgt.scene_path, e.target_input_index):
                    issues.append(ValidationIssue(
                        where=tgt.node_id,
                        message=self._stamp(
                            p, f"input {e.target_input_index} of existing node "
                               f"'{tgt.scene_path}' is already occupied — wiring it "
                               f"would sever the artist's existing connection"),
                    ))

            # --- 3e catalog slot semantics (U.1) — ADDITIVE, catalog-known types only ---
            if tt is not None:
                issues += self._catalog_slot_check(p, e, tgt, tt)
        return issues

    # ---- P3e — probe-verified slot semantics (U.1) ----
    def _catalog_slot_check(self, p: GraphProposal, e, tgt, tt) -> list[ValidationIssue]:
        # When the connectivity catalog (probe truth, not the live oracle) knows
        # the target type: reject an edge into an index >= the probe-verified
        # max_inputs, and — when the proposal NAMES a target slot label — reject
        # a label that is unknown or resolves to a different index. Adds errors
        # only; the oracle-backed 3a-3d above are untouched.
        if self._catalog is None:
            return []
        entry = resolve_catalog_entry(self._catalog, tt[1], tt[0])
        if entry is None:
            return []
        issues: list[ValidationIssue] = []
        max_in = entry.get("max_inputs")
        if max_in is not None and max_in >= 0 and (
                e.target_input_index < 0 or e.target_input_index >= max_in):
            issues.append(ValidationIssue(
                where=tgt.node_id,
                message=self._stamp(
                    p, f"edge target '{tgt.node_id}' input index "
                       f"{e.target_input_index} exceeds the probe-verified arity "
                       f"(max inputs {max_in}) for type '{tt[0]}' "
                       f"[connectivity catalog {self._catalog.get('houdini_version')}]"),
            ))
        label = getattr(e, "target_input_label", "") or ""
        labels = entry.get("input_labels") or []
        if label and labels:
            wanted = label.strip().lower()
            resolved = next((i for i, have in enumerate(labels)
                             if str(have).strip().lower() == wanted), None)
            if resolved is None:
                issues.append(ValidationIssue(
                    where=tgt.node_id,
                    message=self._stamp(
                        p, f"edge names target input label '{label}' but type "
                           f"'{tt[0]}' has no such input — probe-verified labels "
                           f"are {labels}"),
                ))
            elif resolved != e.target_input_index:
                if 0 <= e.target_input_index < len(labels):
                    wired_slot = f"'{labels[e.target_input_index]}'"
                else:
                    wired_slot = "out of the labeled range"
                issues.append(ValidationIssue(
                    where=tgt.node_id,
                    message=self._stamp(
                        p, f"edge names target input label '{label}' which lives "
                           f"at index {resolved} of '{tt[0]}', but wires index "
                           f"{e.target_input_index} ({wired_slot}) — "
                           f"label-mismatched slot"),
                ))
        return issues

    # ---- LOP known-absent (error) + ordering (advisory) (U.5) — ADDITIVE ----
    def _lop_ordering_check(self, p: GraphProposal,
                            advisories: list[ValidationIssue]) -> list[ValidationIssue]:
        # Catalog-driven, Solaris-only. Two halves at DIFFERENT severities:
        #   (a) known-absent LOP types (grid/plane) -> HARD ERROR. Those types do
        #       not exist in any build (zero false-positive surface). NEW nodes only:
        #       an EXISTING node's node_type is advisory per the ProposedNode contract
        #       and a live node cannot be an absent type. Case-insensitive so a
        #       capitalized spelling still gets the corpus remediation.
        #   (b) ordering rules (assignmaterial expects a material source upstream)
        #       -> ADVISORY. This is a common-pattern heuristic, not a provable
        #       invariant: material prims also arrive via reference/sublayer
        #       composition arcs (catalog `satisfied_by`) or a pre-composed live
        #       stage, so a hard error would false-reject valid graphs.
        # Returns errors; appends advisories in place. Never weakens the oracle phases.
        cat = self._lop_catalog
        if not isinstance(cat, dict) or p.network_type != "SOLARIS":
            return []
        # Shape-coerce every field: the checksum-gated load path can only yield a
        # well-formed catalog or None, but the lop_catalog= injection seam is not
        # gated, and the contract is "malformed -> skip, never raise".
        content = cat.get("content")
        if not isinstance(content, dict):
            return []
        absent = content.get("known_absent")
        absent = absent if isinstance(absent, dict) else {}
        raw_rules = content.get("ordering_rules")
        rules = ([r for r in raw_rules
                  if isinstance(r, dict) and r.get("relation") == "upstream"]
                 if isinstance(raw_rules, list) else [])
        if not absent and not rules:
            return []
        ver = cat.get("houdini_version")
        errors: list[ValidationIssue] = []
        by_id = {n.node_id: n for n in p.nodes}

        # (a) known-absent LOP types (NEW nodes, case-insensitive) — corpus-flagged pitfall.
        absent_lc = {k.lower(): v for k, v in absent.items()
                     if isinstance(k, str) and isinstance(v, dict)}
        for n in p.nodes:
            if n.kind is not NodeKind.NEW or n.node_category != "Lop":
                continue
            hit = absent_lc.get((n.node_type or "").lower())
            if hit is not None:
                errors.append(ValidationIssue(
                    where=n.node_id,
                    message=self._stamp(
                        p, f"'{n.node_type}' is not a real LOP node type — "
                           f"{hit.get('remediation', 'unavailable')} "
                           f"[LOP knowledge {ver}]"),
                ))

        # (b) upstream ordering rules -> ADVISORY. Fires only where the proposal
        # fully authors the upstream chain (all-NEW) and NO satisfying material
        # source is present (the required type OR any `satisfied_by` type). If the
        # chain reaches an EXISTING or undeclared node — a boundary into the
        # pre-composed live stage whose content the proposal does not model — we
        # under-advise (stay silent) rather than emit a spurious advisory. That
        # deliberately accepts a false-negative class (an unrelated existing node
        # quiets the advisory) as a reviewed trade for signal quality; this is an
        # advisory, never a block.
        if rules:
            back: dict[str, list[str]] = {}
            for e in p.edges:
                back.setdefault(e.target_node_id, []).append(e.source_node_id)

            def upstream_ids(nid: str) -> set[str]:
                seen: set[str] = set()
                stack = list(back.get(nid, []))
                while stack:
                    cur = stack.pop()
                    if cur in seen:
                        continue
                    seen.add(cur)
                    stack.extend(back.get(cur, []))
                return seen

            for rule in rules:
                on_t = rule.get("on_type")
                sb = rule.get("satisfied_by")
                satisfying = {rule.get("requires_type"),
                              *(sb if isinstance(sb, list) else [])}
                satisfying.discard(None)
                for n in p.nodes:
                    if n.node_category != "Lop" or n.node_type != on_t:
                        continue
                    up = upstream_ids(n.node_id)
                    # Boundary into the pre-composed stage -> under-advise.
                    if any(by_id.get(u) is None or by_id[u].kind is NodeKind.EXISTING
                           for u in up):
                        continue
                    up_types = {by_id[u].node_type for u in up
                                if by_id.get(u) is not None and by_id[u].node_type}
                    if not (up_types & satisfying):
                        advisories.append(ValidationIssue(
                            where=n.node_id,
                            message=self._stamp(
                                p, f"'{on_t}' node '{n.friendly_name or n.node_id}' has no "
                                   f"material source upstream (expected one of "
                                   f"{sorted(satisfying)}) — {rule.get('detail', '')} "
                                   f"[LOP knowledge {ver}]"),
                        ))
        return errors

    # ---- Phase 4 — structural, pure logic (MILE 2) ----
    def _phase4_structural(self, p: GraphProposal) -> list[ValidationIssue]:
        # acyclicity (DAG) · new-vs-new friendly_name collision · node_category <-> network_type.
        issues: list[ValidationIssue] = []
        by_id = {n.node_id: n for n in p.nodes}

        # --- acyclicity: the proposed edges must form a DAG ---
        adj: dict[str, list[str]] = {}
        for e in p.edges:
            if e.source_node_id in by_id and e.target_node_id in by_id:
                adj.setdefault(e.source_node_id, []).append(e.target_node_id)
        cycle = self._find_cycle(adj)
        if cycle is not None:
            issues.append(ValidationIssue(
                where=" -> ".join(cycle),
                message=self._stamp(p, f"cycle detected in proposed edges: "
                                       f"{' -> '.join(cycle)} (graphs must be acyclic)"),
            ))

        # --- NEW-vs-NEW friendly_name collision (EXISTING names are advisory-only) ---
        seen: dict[str, str] = {}
        for n in p.nodes:
            if n.kind is not NodeKind.NEW or not n.friendly_name:
                continue
            if n.friendly_name in seen:
                issues.append(ValidationIssue(
                    where=n.node_id,
                    message=self._stamp(
                        p, f"duplicate friendly_name '{n.friendly_name}' — also used by "
                           f"new node '{seen[n.friendly_name]}'"),
                ))
            else:
                seen[n.friendly_name] = n.node_id

        # --- node_category <-> network_type consistency (NEW nodes only) ---
        allowed = _NETWORK_CATEGORIES.get(p.network_type.upper())
        if allowed:
            for n in p.nodes:
                if n.kind is NodeKind.NEW and n.node_category not in allowed:
                    issues.append(ValidationIssue(
                        where=n.node_id,
                        message=self._stamp(
                            p, f"node_category '{n.node_category}' is invalid for a "
                               f"'{p.network_type}' network (expected one of "
                               f"{sorted(allowed)})"),
                    ))
        return issues

    @staticmethod
    def _find_cycle(adj: dict[str, list[str]]) -> list[str] | None:
        # Iterative DFS with a gray/black colouring; returns a representative cycle
        # path (for the error message) or None. Pure logic, no oracle.
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {}
        nodes = set(adj) | {t for ts in adj.values() for t in ts}
        for root in nodes:
            if color.get(root, WHITE) != WHITE:
                continue
            stack: list[tuple[str, int]] = [(root, 0)]
            path: list[str] = []
            while stack:
                node, i = stack[-1]
                if i == 0:
                    color[node] = GRAY
                    path.append(node)
                succs = adj.get(node, [])
                if i < len(succs):
                    stack[-1] = (node, i + 1)
                    nxt = succs[i]
                    c = color.get(nxt, WHITE)
                    if c == GRAY:                      # back-edge -> cycle
                        return path[path.index(nxt):] + [nxt]
                    if c == WHITE:
                        stack.append((nxt, 0))
                else:
                    color[node] = BLACK
                    path.pop()
                    stack.pop()
        return None

    # ---- Phase 5 — context check, host oracle (MILE 2) ----
    def _phase5_context(self, p: GraphProposal) -> list[ValidationIssue]:
        # parent exists (HARD) · every EXISTING scene_path resolves (HARD, never a
        # crash) · new-vs-existing children names.
        issues: list[ValidationIssue] = []

        # --- parent existence (HARD): the proposal's container must resolve. This
        # is the brief's P5 'parent exists' check — a graph cannot be built under a
        # parent that is not there, so a non-resolving parent makes the proposal
        # INVALID (not merely advisory). Parent TYPE-host compatibility (can this
        # container hold these node categories?) is a separate concern deferred to
        # the Mile-3 live builder, which re-runs P5 and where Houdini enforces it.
        try:
            self._conn.resolve_node_type(p.parent_path)
        except Exception:  # noqa: BLE001 — clean context error, never a crash
            issues.append(ValidationIssue(
                where=p.parent_path,
                message=self._stamp(
                    p, f"parent '{p.parent_path}' does not resolve in the live scene"),
            ))

        # --- every EXISTING scene_path must resolve in the live scene (HARD) ---
        existing = [n for n in p.nodes if n.kind is NodeKind.EXISTING]
        for n in existing:
            try:
                self._conn.resolve_node_type(n.scene_path)
            except Exception:  # noqa: BLE001 — clean context error, never a crash
                issues.append(ValidationIssue(
                    where=n.node_id,
                    message=self._stamp(
                        p, f"existing node '{n.node_id}' path '{n.scene_path}' does "
                           f"not resolve in the live scene"),
                ))

        # --- NEW-vs-EXISTING child name collision under the same parent ---
        # The oracle exposes no child enumeration, so the implementable check is:
        # a NEW node's friendly_name colliding with the basename of an EXISTING
        # node referenced in THIS proposal that lives under the same parent.
        existing_basenames: dict[str, str] = {}
        for n in existing:
            if not n.scene_path:
                continue
            parent, _, base = n.scene_path.rpartition("/")
            if base and parent == p.parent_path:
                existing_basenames[base] = n.scene_path
        for n in p.nodes:
            if n.kind is NodeKind.NEW and n.friendly_name in existing_basenames:
                issues.append(ValidationIssue(
                    where=n.node_id,
                    message=self._stamp(
                        p, f"new node '{n.node_id}' name '{n.friendly_name}' collides "
                           f"with existing child '{existing_basenames[n.friendly_name]}'"),
                ))
        return issues
