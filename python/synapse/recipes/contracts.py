"""Frozen seam for the Solaris Recipes v3 swarm (bp5).

Every stream imports from here and nobody edits this file inside a stream
branch. A stream that needs a change writes it to
``docs/solaris_v3/CONTRACT_CHANGE_REQUESTS_<STREAM>.md``; the integrator
applies accepted changes on the base branch.

Pure Python. No ``hou``, no ``pxr``. Importable everywhere.

Vocabulary is the blueprint's (pages 04, 07, 08, 09). Field lists are the
minimum; streams may add optional fields with defaults but may not rename,
remove, or retype anything here.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol, Sequence, Tuple

CONTRACT_VERSION = "3.0.0"
SUPPORTED_BUILD = "22.0.400"          # pinned demo build (blueprint p03)
SCHEMA_VERSION = "2"                  # fixtures/solaris.spine.json schema
RECIPE_ID = "solaris.spine"           # the one owned baseline topology


# --------------------------------------------------------------------------
# Actions (blueprint p03, "Freeze one artist loop")
# --------------------------------------------------------------------------
class ActionId(str, enum.Enum):
    BUILD = "solaris.spine"                    # create captured topology, clean owned scope
    LIGHT = "solaris.iterate.light"            # exposure on the captured key light only
    MATERIAL = "solaris.iterate.material"      # hero base-color input only
    RENDER = "solaris.render.karma"            # bounded settings/output via existing approval


class PermissionCategory(str, enum.Enum):
    """Effective permission of an action. A recipe wrapper can never lower
    the gate of the effect it wraps (blueprint p06)."""
    INFORM = "inform"
    REVIEW = "review"
    APPROVE = "approve"
    CRITICAL = "critical"


PERMISSION_ORDER: Tuple[PermissionCategory, ...] = (
    PermissionCategory.INFORM,
    PermissionCategory.REVIEW,
    PermissionCategory.APPROVE,
    PermissionCategory.CRITICAL,
)


def max_permission(*cats: PermissionCategory) -> PermissionCategory:
    """The effective permission is the strictest of the wrapper and the
    wrapped effect. Never relabels a gated effect as an ordinary build."""
    return max(cats, key=PERMISSION_ORDER.index)


# --------------------------------------------------------------------------
# Card dimensions (blueprint p09)
# --------------------------------------------------------------------------
class Availability(str, enum.Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    EXPERIMENTAL = "EXPERIMENTAL"


class OperationState(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    TERMINAL = "TERMINAL"


class TerminalVerdict(str, enum.Enum):
    VERIFIED = "VERIFIED"
    REFUSED = "REFUSED"
    BROKEN = "BROKEN"
    UNKNOWN = "UNKNOWN"
    CANCELLED = "CANCELLED"


class EvidenceFreshness(str, enum.Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class RecoveryVerdict(str, enum.Enum):
    """Recorded separately from the operation result (blueprint p07).
    A clean rollback is still a failed build."""
    NOT_NEEDED = "NOT_NEEDED"
    RESTORED = "RESTORED"
    RESIDUE = "RESIDUE"
    UNKNOWN = "UNKNOWN"


# --------------------------------------------------------------------------
# Checks / predicates (blueprint p08)
# --------------------------------------------------------------------------
class CheckId(str, enum.Enum):
    P1_GRAPH = "P1"
    P2_USD = "P2"
    P3_RENDER_READY = "P3"
    P4_COMPOSITION = "P4"
    P5_IMAGE_SMOKE = "P5"
    P6_LOCALITY = "P6"


class CheckStatus(str, enum.Enum):
    """A check that was skipped, could not reach its host, or did not
    exercise the intended path is NOT_RUN / UNKNOWN -- never PASS."""
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_RUN = "NOT_RUN"


REQUIRED_CHECKS: Dict[ActionId, Tuple[CheckId, ...]] = {
    ActionId.BUILD: (CheckId.P1_GRAPH, CheckId.P2_USD, CheckId.P4_COMPOSITION, CheckId.P6_LOCALITY),
    ActionId.LIGHT: (CheckId.P1_GRAPH, CheckId.P2_USD, CheckId.P4_COMPOSITION, CheckId.P6_LOCALITY),
    ActionId.MATERIAL: (CheckId.P1_GRAPH, CheckId.P2_USD, CheckId.P4_COMPOSITION, CheckId.P6_LOCALITY),
    ActionId.RENDER: (CheckId.P2_USD, CheckId.P3_RENDER_READY, CheckId.P4_COMPOSITION, CheckId.P5_IMAGE_SMOKE),
}


@dataclass(frozen=True)
class CheckResult:
    check: CheckId
    status: CheckStatus
    reason: str = ""                       # one line; required when not PASS
    evidence: Mapping[str, Any] = field(default_factory=dict)


def verdict_from_checks(action: ActionId, results: Sequence[CheckResult]) -> TerminalVerdict:
    """No required predicate is skipped into a green result."""
    by_id = {r.check: r for r in results}
    for cid in REQUIRED_CHECKS[action]:
        r = by_id.get(cid)
        if r is None or r.status in (CheckStatus.NOT_RUN, CheckStatus.UNKNOWN):
            return TerminalVerdict.UNKNOWN
        if r.status is CheckStatus.FAIL:
            return TerminalVerdict.BROKEN
    return TerminalVerdict.VERIFIED


# --------------------------------------------------------------------------
# The three objects (blueprint p04)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SlotSchema:
    key: str
    type: str                              # "float" | "int" | "color3" | "enum" | "str"
    binding: str                           # exact field binding "<node_id>.<parm_name>" (typed, never interpolated)
    min: Optional[float] = None
    max: Optional[float] = None
    enum: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ActionSpec:
    action_id: ActionId
    slots: Tuple[SlotSchema, ...]
    required_checks: Tuple[CheckId, ...]
    effect_scope: str                      # "graph" | "field" | "render"
    permission: PermissionCategory         # declared; effective = max(declared, wrapped effect)
    phrases: Tuple[str, ...] = ()          # exact demo phrases; whole request must be consumed


@dataclass(frozen=True)
class RecipeSpec:
    """Immutable version. Owner: curated authoring + registry."""
    recipe_id: str
    version: str
    schema_version: str
    supported_build: str
    catalog_digest: str                    # digest of rag/catalog/<build>/Lop.json used to pin types
    canonicalizer: str                     # e.g. "c3" (blocks baseline canonicalizer id)
    semantic_digest: str                   # node types/parents/ports/parms/expressions/flags
    layout_digest: str                     # positions only
    golden_reference: Mapping[str, Any]    # REQUIRED: hip path, reference render, dependency record
    nodes: Tuple[Mapping[str, Any], ...]   # id,parent_id,category,type,parms,flags,position (+nested shaders)
    connections: Tuple[Mapping[str, Any], ...]  # src_id,src_output,dst_id,dst_input (captured, never guessed)
    actions: Tuple[ActionSpec, ...]
    presentation: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class RecipeInstance:
    """Scene-local identity. Owner: host runtime (BLOCKS-owned scope)."""
    instance_id: str
    recipe_id: str
    recipe_version: str
    owned_node_ids: Dict[str, str]         # spec node id -> scene node path
    committed_slots: Dict[str, Any]        # last approved slot values
    graph_revision: int                    # bumps on every committed mutation of this instance
    authored_baseline: str                 # semantic digest of the instance as last committed
    network_box: Optional[str] = None


@dataclass(frozen=True)
class ApprovalBinding:
    """Approval is bound to exactly this scope and rechecked immediately
    before starting (blueprint p06)."""
    instance_id: str
    graph_revision: int
    engine: str
    resolution: Tuple[int, int]
    samples: int
    output_path: str
    approved_by: str                       # provenance of the trusted approval
    approved_at: str                       # ISO-8601


@dataclass(frozen=True)
class RunReceipt:
    """Immutable evidence. Owner: verifier. One receipt per run."""
    run_id: str
    request_id: str
    recipe_id: str
    recipe_version: str
    action_id: ActionId
    instance_id: str
    revision_before: int
    revision_after: Optional[int]
    code_identity: Mapping[str, str]       # commit, module path, contract version
    build: str                             # e.g. "22.0.400"
    engine: Optional[str]
    dependency_identity: Mapping[str, str] # asset/plugin digests
    validated_slots: Mapping[str, Any]
    approval: Optional[ApprovalBinding]
    started_at: str
    completed_at: Optional[str]
    checks: Tuple[CheckResult, ...]
    fingerprint_before: str
    fingerprint_after: Optional[str]
    operation_state: OperationState
    verdict: TerminalVerdict
    recovery: RecoveryVerdict
    render_job: Mapping[str, Any] = field(default_factory=dict)   # job id, terminal state, output file identity
    reason: str = ""                       # one line, required when verdict != VERIFIED


# --------------------------------------------------------------------------
# The constrained interface (blueprint p06) -- not model-selected capabilities
# --------------------------------------------------------------------------
RUN_RECIPE_TOOL_NAME = "synapse_run_recipe"


@dataclass(frozen=True)
class RunRecipeRequest:
    recipe_id: str
    action_id: str
    instance_id: Optional[str]
    slots: Mapping[str, Any]
    expected_revision: Optional[int]
    request_id: str


class RefusalKind(str, enum.Enum):
    UNKNOWN_ACTION = "unknown_action"
    UNKNOWN_TOOL = "unknown_tool"
    SLOT_INVALID = "slot_invalid"
    TRAILING_CLAUSE = "trailing_clause"    # unsupported clause must not disappear
    AMBIGUOUS = "ambiguous"
    STALE = "stale"                        # expected_revision != live revision
    CONFLICT = "conflict"                  # authored state diverged from committed instance
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_MISMATCH = "approval_mismatch"
    PROFILE_CONFLICT = "profile_conflict"  # demo mode can never fall through to unrestricted
    DUPLICATE_REQUEST = "duplicate_request"


@dataclass(frozen=True)
class Refusal:
    kind: RefusalKind
    reason: str
    supported_alternative: str = ""


class Verifier(Protocol):
    """Independent of writers. Streams implement per CheckId."""
    def run(self, check: CheckId, instance: RecipeInstance, spec: RecipeSpec, **context: Any) -> CheckResult: ...


# --------------------------------------------------------------------------
# Demo phrases (blueprint p03/p06): exact, whole-request, deterministic
# --------------------------------------------------------------------------
DEMO_PHRASES: Dict[ActionId, Tuple[str, ...]] = {
    ActionId.BUILD: ("build the solaris spine",),
    ActionId.LIGHT: ("set the key light exposure to {exposure}",),
    ActionId.MATERIAL: ("make the hero {color}",),
    ActionId.RENDER: ("render the spine",),
}
