# SYNAPSE Gap Remediation Blueprint
## MOE Agent Teams for Claude Code Execution

> **Purpose:** Actionable execution plan transforming the Gap Research Report into parallelizable agent workstreams using Mixture-of-Experts routing.
>
> **Execution model:** Each agent team is a specialist with a defined scope, entry gate, exit criteria, and handoff protocol. The Orchestrator routes tasks based on signal fingerprints. Agents operate on the SYNAPSE codebase at `C:\Users\User\SYNAPSE`.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                          │
│  Signal Fingerprint → Top-K Agent Selection → Dispatch  │
└──────────┬──────────┬──────────┬──────────┬─────────────┘
           │          │          │          │
     ┌─────▼───┐ ┌───▼────┐ ┌──▼───┐ ┌───▼──────┐
     │ RAG-OPS │ │ SAFETY │ │ TOPS │ │ VALIDATOR│
     │ Agent   │ │ Agent  │ │ Agent│ │ Agent    │
     └─────────┘ └────────┘ └──────┘ └──────────┘
         │            │          │          │
         ▼            ▼          ▼          ▼
     Knowledge    Atomic Ops   PDG      Frame QA
     Layer        & Guards    Pipeline   Pipeline
```

---

## Agent Definitions

### Agent 0: ORCHESTRATOR (Router)

**Role:** Sparse router. Reads task description, extracts signal fingerprint, dispatches to top-K agents.

**Signal Fingerprint Schema:**
```python
@dataclass
class TaskSignal:
    domain: Literal["rag", "safety", "tops", "validator", "agent_arch"]
    friction_id: Optional[str]  # e.g. "material_paths", "dop_wiring", "render_output"
    priority: Literal["P0", "P1", "P2", "P3"]
    depends_on: list[str]       # agent task IDs that must complete first
    estimated_files: int        # rough scope for load balancing
```

**Routing Table:**
```
Signal                          → Agent(s)         Priority
─────────────────────────────────────────────────────────────
RAG entry creation/audit        → RAG-OPS          P0
Safety pattern, atomic, undo    → SAFETY            P0
TOPS/PDG integration            → TOPS              P1
Frame validation, IQA           → VALIDATOR          P2
Agent planning, predict-verify  → TOPS + VALIDATOR   P2
Error taxonomy, recovery        → SAFETY + TOPS      P2
Temporal coherence              → VALIDATOR           P3
```

**Dispatch Protocol:**
1. Parse task into `TaskSignal`
2. Check `depends_on` — block if predecessors incomplete
3. Select top-K agents (usually 1, max 2 for cross-cutting tasks)
4. Pass task with full context to selected agent(s)
5. Collect exit artifacts, update dependency graph

---

### Agent 1: RAG-OPS (Knowledge Layer Specialist)

**Expertise:** RAG knowledge base structure, trigger design, semantic indexing, Houdini domain conventions.

**Owns:** `synapse/routing/knowledge/`, RAG markdown files, trigger definitions, semantic index entries.

**Research Backing:**
- *RAG for API Documentation* (2503.15231): Example code > prose descriptions
- *CodeRAG-Bench* (2406.14497): Retrieval for domain-specific code
- *ARKS* (2402.12317): Active retrieval from knowledge soup

#### Task 1.1: Material Assignment RAG Pack
```yaml
id: rag-materials
priority: P0
depends_on: []
estimated_files: 12-15 new markdown files
exit_criteria:
  - 10+ new RAG entries with code examples
  - Each entry has: trigger phrases, code snippet, expected scene graph
  - Coverage: Assign Material LOP, Material Library, binding strength,
    VEXpression patterns, MaterialX encoding, @elemnum vs @ptnum,
    USD path expressions vs Houdini prim patterns
```

**Execution Steps:**
1. `grep -r "material" synapse/routing/knowledge/` — inventory existing material RAG entries
2. Identify gaps against the Tier 1 material conventions list
3. For each gap, create a RAG entry following this template:

```markdown
# Material Assignment: Binding Strength Override

## Triggers
material binding, binding strength, material override, material not working,
material not applying, default material, stronger than descendants

## Context
When re-assigning materials in Solaris, existing bindings may take precedence.
The Assign Material LOP's Strength parameter controls binding priority.

## Code
```python
# Assign material with strength override via hou module
import hou

lop_net = hou.node("/stage")
assign_mat = lop_net.createNode("assignmaterial")

# Set primitives target
assign_mat.parm("primpattern1").set("/geo/hero_asset/**")

# Set material path (full prim path in scene graph)
assign_mat.parm("matspecpath1").set("/materials/hero_mtlx")

# CRITICAL: Override existing bindings
# Options: "weakerThanDescendants", "strongerThanDescendants"
assign_mat.parm("bindingstrength1").set("strongerThanDescendants")
```

## Expected Scene Graph
```
/geo/hero_asset/  (UsdGeomMesh)
  └─ material:binding → /materials/hero_mtlx  [strength: strongerThanDescendants]
/materials/hero_mtlx/  (UsdShadeMaterial)
  └─ mtlxsurface (UsdShadeShader)
```

## Common Mistakes
- Using `@ptnum` instead of `@elemnum` in LOP VEXpressions
- Forgetting binding strength when materials don't appear to apply
- Using relative paths instead of full scene graph prim paths
- Assigning to wrong scope (e.g., `/materials/` vs `/mtl/` — check your Material Library's configured scope)
```

4. Create entries for each sub-topic:
   - `rag_material_vexpression.md` — Dynamic assignment with VEX snippets
   - `rag_material_library_setup.md` — Creating materials in Material Library LOP
   - `rag_material_mtlx_encoding.md` — MaterialX as USD prims workflow
   - `rag_material_primvar_driven.md` — shop_materialpath / primvar-driven assignment
   - `rag_material_binding_strength.md` — Strength parameter and Unassign Material
   - `rag_material_karma_xpu.md` — XPU constraints (no VEX shaders, MaterialX only)
   - `rag_material_path_expressions.md` — USD path expressions vs Houdini prim patterns
   - `rag_material_collect_vop.md` — Multi-renderer material switching with Collect VOP
   - `rag_material_texture_override.md` — Texture overrides in Karma (CPU vs XPU differences)
   - `rag_material_common_errors.md` — Consolidated error patterns

5. Register triggers in the semantic index
6. Run existing test suite to verify no regressions

#### Task 1.2: DOP Wiring RAG Pack
```yaml
id: rag-dop
priority: P0
depends_on: []
estimated_files: 8-10 new markdown files
exit_criteria:
  - 8+ new RAG entries with code examples
  - Coverage: enforceWiringOrder, findOrCreateMergeInput, createSolver,
    simulation-enabled guards, DopData tree, freeze(), solver ordering,
    constraint network setup
```

**Execution Steps:**
1. `grep -r "dop\|DOP\|simulation" synapse/routing/knowledge/` — inventory existing
2. Create entries for each convention:
   - `rag_dop_wiring_order.md` — enforceWiringOrder + merge input patterns
   - `rag_dop_simulation_guard.md` — setSimulationEnabled wrapper pattern
   - `rag_dop_solver_creation.md` — createSolver with mergeobjects flag
   - `rag_dop_data_tree.md` — DopData hierarchy, subdata, freeze()
   - `rag_dop_rbd_setup.md` — RBD Object, Packed Object, constraint networks
   - `rag_dop_checkpoint.md` — Checkpoint intervals and recovery
   - `rag_dop_python_pattern.md` — Complete DOP network creation pattern
   - `rag_dop_common_errors.md` — Consolidated error patterns

3. Each entry must include the simulation-enabled guard pattern:
```python
# ALWAYS wrap DOP modifications in simulation guard
sim_was_enabled = hou.simulationEnabled()
try:
    hou.setSimulationEnabled(False)
    # ... DOP network modifications ...
finally:
    hou.setSimulationEnabled(sim_was_enabled)
```

#### Task 1.3: Render Output Path RAG Pack
```yaml
id: rag-render
priority: P0
depends_on: []
estimated_files: 8-10 new markdown files
exit_criteria:
  - 8+ new RAG entries with code examples
  - Coverage: RenderSettings/RenderProduct/RenderVar prims, Karma LOP unified node,
    productName attribute, frame token formats, /Render branch convention,
    karma: namespace, render delegate detection, husk CLI
```

**Execution Steps:**
1. `grep -r "render.*output\|render.*path\|productName\|husk" synapse/routing/knowledge/`
2. Create entries:
   - `rag_render_usd_pipeline.md` — RenderSettings → RenderProduct → RenderVar hierarchy
   - `rag_render_karma_lop.md` — Karma LOP as unified render configuration
   - `rag_render_output_path.md` — productName on RenderProduct, timeSamples for animation
   - `rag_render_frame_tokens.md` — `$F4` vs `<F4>` vs timeSamples (CRITICAL disambiguation)
   - `rag_render_branch_convention.md` — /Render scene graph convention
   - `rag_render_karma_namespace.md` — karma:object: property namespace
   - `rag_render_delegate_detection.md` — usdrenderers.py, aovsupport filtering
   - `rag_render_husk_cli.md` — husk command-line patterns and output overrides

3. Frame token entry is highest priority — this is the most common source of silent failures:
```markdown
# Render Output: Frame Token Formats

## Triggers
frame token, $F4, <F4>, render sequence, frame padding, output path

## CRITICAL: Three Different Frame Token Systems

| Context | Format | Example |
|---------|--------|---------|
| Houdini parameter expressions | `$F4` or `${F4}` | `$HIP/render/shot.$F4.exr` |
| husk command-line --output | `<F4>` | `output.<F4>.exr` |
| USD RenderProduct timeSamples | Explicit per-frame | `{1: "shot.0001.exr", 2: "shot.0002.exr"}` |

## Code — Reading render output path from USD stage
```python
import hou

# Get the stage from a LOP node
lop_node = hou.node("/stage/karmanode1")
stage = lop_node.stage()

# Find RenderProduct prims under /Render
from pxr import UsdRender
for prim in stage.Traverse():
    if prim.IsA(UsdRender.Product):
        product_name = prim.GetAttribute("productName")
        # For animated output, check timeSamples
        time_samples = product_name.GetTimeSamples()
        if time_samples:
            # Has per-frame paths
            for t in time_samples:
                path = product_name.Get(t)
                print(f"Frame {t}: {path}")
        else:
            # Static path with frame token
            path = product_name.Get()
            print(f"Output: {path}")
```
```

#### Task 1.4: RAG Audit — Code-to-Prose Ratio
```yaml
id: rag-audit
priority: P1
depends_on: [rag-materials, rag-dop, rag-render]
estimated_files: 0 new, 40-60 modified
exit_criteria:
  - Every RAG entry has ≥60% code content by line count
  - Every RAG entry has at least one complete, runnable code example
  - Prose sections converted to inline code comments where possible
  - Report generated: entries modified, code ratio before/after
```

**Execution Steps:**
1. Script to measure code-to-prose ratio across all 115+ RAG markdown files
2. Flag entries below 60% threshold
3. For each flagged entry: convert prose descriptions to code examples with comments
4. Re-run semantic index build
5. Run test suite

---

### Agent 2: SAFETY (Atomic Operations & Guards Specialist)

**Expertise:** Transaction safety, undo groups, idempotent guards, error recovery, partial-execution prevention.

**Owns:** `synapse/core/`, safety layers, atomic script patterns, undo group wrappers.

**Research Backing:**
- *Fission-GRPO Error Recovery* (2601.15625): Convert execution errors to corrective supervision
- *Where LLM Agents Fail* (2509.25370): Error taxonomy (planning, action, scope)
- *Agentic Rubrics* (2601.04171): Context-aware verification checklists

#### Task 2.1: Error Taxonomy Integration
```yaml
id: safety-taxonomy
priority: P2
depends_on: [rag-materials, rag-dop, rag-render]  # needs domain knowledge first
estimated_files: 3-5 new/modified
exit_criteria:
  - Error classification enum covering: planning_error, action_error, scope_error,
    domain_knowledge_gap, partial_execution, timeout
  - Each MCP tool execution logs its error class on failure
  - Error class feeds back to routing layer for agent self-correction
```

**Execution Steps:**
1. Review existing error handling in `synapse/server/` handler files
2. Define error taxonomy enum:
```python
from enum import Enum, auto

class AgentErrorClass(Enum):
    """Error taxonomy based on 'Where LLM Agents Fail' (2509.25370)"""

    # Planning errors — wrong approach selected
    PLANNING_WRONG_APPROACH = auto()     # e.g., wrong material prim pattern
    PLANNING_SCOPE_OVERFLOW = auto()     # e.g., excessive changes in one session

    # Action errors — right plan, wrong execution
    ACTION_PARAM_ERROR = auto()          # e.g., wrong parameter name/value
    ACTION_PATH_ERROR = auto()           # e.g., incorrect USD prim path
    ACTION_WIRING_ERROR = auto()         # e.g., DOP node connection order

    # Domain knowledge gaps — RAG miss
    DOMAIN_CONVENTION_MISS = auto()      # e.g., @ptnum vs @elemnum
    DOMAIN_API_MISS = auto()             # e.g., unknown hou module function

    # Execution failures
    EXEC_PARTIAL = auto()                # partial mutation before error
    EXEC_TIMEOUT = auto()                # operation exceeded time budget
    EXEC_DEPENDENCY = auto()             # missing upstream dependency
```

3. Add classification to the existing error handling pipeline
4. Create feedback path: error class → routing adaptation (if same error class hits 2+ times in a session, inject relevant RAG context proactively)
5. Write tests for each error class

#### Task 2.2: Recovery Pattern Library
```yaml
id: safety-recovery
priority: P2
depends_on: [safety-taxonomy]
estimated_files: 2-4 new
exit_criteria:
  - Recovery strategy mapped to each error class
  - Strategies: rollback, retry-with-context, escalate-to-user, skip-and-continue
  - Integration with existing undo group mechanism
```

**Recovery Strategy Map:**
```python
RECOVERY_STRATEGIES = {
    AgentErrorClass.PLANNING_WRONG_APPROACH: [
        "rollback_undo_group",
        "inject_rag_context",     # pull relevant RAG entries
        "retry_with_context",     # retry with additional domain knowledge
    ],
    AgentErrorClass.ACTION_PATH_ERROR: [
        "rollback_undo_group",
        "query_scene_graph",      # introspect actual prim paths
        "retry_with_correction",  # retry with discovered paths
    ],
    AgentErrorClass.EXEC_PARTIAL: [
        "rollback_undo_group",    # ALWAYS rollback partial execution
        "escalate_to_user",       # partial state is dangerous
    ],
    AgentErrorClass.DOMAIN_CONVENTION_MISS: [
        "log_gap",                # flag for RAG-OPS agent
        "inject_rag_context",
        "retry_with_context",
    ],
}
```

---

### Agent 3: TOPS (PDG Pipeline & Execution Engine Specialist)

**Expertise:** TOPS/PDG work items, dependency graphs, render farm scheduling, warm standby patterns.

**Owns:** `synapse/autonomy/`, TOPS handler files, PDG work item definitions.

**Research Backing:**
- *Predict Before Executing* (2601.05930): Predict-then-verify execution loop
- *Routine Planning Framework* (2507.14447): Multi-step planning with parameter passing
- *ToolPRMBench* (2601.12294): Process rewards for multi-tool chains
- *STEVE Step Verification* (2503.12532): Per-step verification pipeline

#### Task 3.1: Predict-then-Verify Pattern
```yaml
id: tops-predict-verify
priority: P1
depends_on: [rag-render]  # needs render path knowledge
estimated_files: 3-5 new
exit_criteria:
  - Pre-render verification function that checks:
    - RenderProduct prim exists and has valid productName
    - Output directory exists and is writable
    - Camera prim is valid and has reasonable frustum
    - Material bindings resolve (no unresolved references)
    - Light prims exist with non-zero intensity
  - Prediction logged before render, compared after render
  - Discrepancy triggers re-evaluation before next frame
```

**Execution Steps:**
1. Design the prediction schema:
```python
@dataclass
class RenderPrediction:
    """Pre-render prediction for verify-after-render comparison."""

    # Scene structure predictions
    render_product_path: str
    output_file_pattern: str
    expected_frame_range: tuple[int, int]
    camera_prim: str
    material_count: int
    light_count: int
    geo_prim_count: int

    # Quality predictions
    expected_resolution: tuple[int, int]
    has_motion_blur: bool
    has_displacement: bool
    estimated_render_time_seconds: float  # rough estimate for timeout

    # Verification results (filled post-render)
    actual_output_files: list[str] = field(default_factory=list)
    render_succeeded: bool = False
    discrepancies: list[str] = field(default_factory=list)
```

2. Implement pre-render verification:
```python
def verify_pre_render(stage, render_settings_path: str) -> RenderPrediction:
    """
    Introspect USD stage before render launch.
    Based on 'Predict Before Executing' (2601.05930).
    """
    from pxr import UsdRender, UsdGeom, UsdLux, UsdShade

    prediction = RenderPrediction(...)

    # Check RenderProduct exists
    render_prim = stage.GetPrimAtPath(render_settings_path)
    if not render_prim.IsValid():
        raise PreRenderError(f"RenderSettings not found at {render_settings_path}")

    # Traverse for material binding validation
    for prim in stage.Traverse():
        if prim.HasRelationship("material:binding"):
            binding = prim.GetRelationship("material:binding")
            targets = binding.GetTargets()
            for target in targets:
                mat_prim = stage.GetPrimAtPath(target)
                if not mat_prim.IsValid():
                    prediction.discrepancies.append(
                        f"Unresolved material binding: {prim.GetPath()} → {target}"
                    )

    return prediction
```

3. Implement post-render verification
4. Wire into TOPS work item chain: predict → render → verify → decide (continue/re-render/escalate)
5. Write tests with mock USD stages

#### Task 3.2: TOPS Work Item Step Verification
```yaml
id: tops-step-verify
priority: P2
depends_on: [tops-predict-verify, safety-taxonomy]
estimated_files: 4-6 new
exit_criteria:
  - Each TOPS work item type has a step verifier
  - Verifier runs before proceeding to dependent work items
  - Failed verification triggers recovery strategy from SAFETY agent
  - Step verification log persisted for debugging
```

**Work Item Verification Chain:**
```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  SCENE   │───▶│ MATERIAL │───▶│ LIGHTING │───▶│  RENDER  │───▶│  POST-   │
│  SETUP   │    │ ASSIGN   │    │  SETUP   │    │ EXECUTE  │    │  CHECK   │
└────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘
     │               │               │               │               │
  ✓ Geo exists    ✓ Bindings     ✓ Lights        ✓ File exists   ✓ Quality
  ✓ Prim count      resolve      ✓ Camera        ✓ File size       score
  ✓ Bounds        ✓ No orphan    ✓ Exposure      ✓ No crash     ✓ Temporal
    valid           shaders        valid           log              coherence
```

**Per-step verifier interface:**
```python
class StepVerifier(Protocol):
    """
    Based on STEVE (2503.12532) step verification pipeline.
    Each TOPS work item type implements this.
    """

    def verify(self, work_item: WorkItem, stage: Usd.Stage) -> StepResult:
        """Check if this step succeeded before proceeding."""
        ...

    def evidence(self, work_item: WorkItem) -> dict:
        """
        Proactive evidence gathering.
        Based on SmartSnap (2512.22322).
        """
        ...

    def on_failure(self, result: StepResult) -> RecoveryAction:
        """Map failure to recovery strategy."""
        ...
```

#### Task 3.3: Process Reward Signals for Tool Chains
```yaml
id: tops-process-rewards
priority: P2
depends_on: [tops-step-verify]
estimated_files: 2-3 new
exit_criteria:
  - Each MCP tool call in a chain gets a step-level reward score
  - Reward signals: correct_result, partial_result, wrong_result, no_result
  - Reward history informs routing adaptation (prefer tool chains with higher reward history)
  - Integrated with agent/sparse_router.py
```

**Reward Signal Schema:**
```python
@dataclass
class ToolReward:
    """
    Step-level reward for MCP tool execution.
    Based on ToolPRMBench (2601.12294).
    """
    tool_name: str
    step_index: int
    chain_id: str
    reward: float           # [-1.0, 1.0]
    evidence: dict           # what we checked
    error_class: Optional[AgentErrorClass] = None

    @staticmethod
    def score(expected, actual) -> float:
        if actual == expected:
            return 1.0
        elif actual is not None and _partial_match(expected, actual):
            return 0.5
        elif actual is None:
            return -0.5
        else:
            return -1.0
```

---

### Agent 4: VALIDATOR (Frame Quality & Temporal Coherence Specialist)

**Expertise:** Image quality assessment, temporal coherence, render artifact detection, sequence validation.

**Owns:** Frame validation pipeline, quality scoring, sequence analysis.

**Research Backing:**
- *DepictQA* (2312.08962): Multi-modal quality assessment with natural language
- *CLIP for IQA* (2207.12396): Zero-shot quality scoring
- *Video Dynamics Restoration* (2206.03753): Temporal flickering detection
- *Blind Deflickering* (2303.08120): Neural atlas artifact detection

#### Task 4.1: Frame Quality Scorer (Zero-Shot)
```yaml
id: validator-frame-qa
priority: P2
depends_on: [tops-predict-verify]
estimated_files: 3-5 new
exit_criteria:
  - Per-frame quality score using CLIP-based assessment
  - Scoring dimensions: noise, exposure, material correctness, composition
  - Score feeds back to TOPS pipeline as work item attribute
  - No model training required (zero-shot)
```

**Execution Steps:**
1. Design quality prompt templates for CLIP scoring:
```python
QUALITY_PROMPTS = {
    "overall": [
        ("a high quality rendered image with clean lighting", 1.0),
        ("a low quality rendered image with artifacts and noise", -1.0),
    ],
    "materials": [
        ("an image with realistic material surfaces and textures", 1.0),
        ("an image with missing or incorrect materials, grey default shader", -1.0),
    ],
    "lighting": [
        ("a well-lit scene with balanced exposure", 1.0),
        ("an overexposed or completely dark scene", -1.0),
    ],
    "noise": [
        ("a clean render with smooth gradients", 1.0),
        ("a noisy render with visible grain and fireflies", -1.0),
    ],
}
```

2. Implement CLIP-based scorer (runs on RTX 4090):
```python
class FrameQualityScorer:
    """
    Zero-shot frame quality assessment using CLIP.
    Based on 'Exploring CLIP for IQA' (2207.12396).
    No training required — uses prompt engineering.
    """

    def __init__(self):
        import clip
        self.model, self.preprocess = clip.load("ViT-L/14", device="cuda")

    def score_frame(self, image_path: str) -> FrameScore:
        image = self.preprocess(Image.open(image_path)).unsqueeze(0).to("cuda")
        scores = {}

        for dimension, prompts in QUALITY_PROMPTS.items():
            texts = clip.tokenize([p[0] for p in prompts]).to("cuda")
            with torch.no_grad():
                image_features = self.model.encode_image(image)
                text_features = self.model.encode_text(texts)
                similarity = (image_features @ text_features.T).softmax(dim=-1)

            # Weighted score: positive prompt similarity - negative prompt similarity
            scores[dimension] = float(similarity[0][0] - similarity[0][1])

        return FrameScore(
            path=image_path,
            overall=scores["overall"],
            materials=scores["materials"],
            lighting=scores["lighting"],
            noise=scores["noise"],
            pass_threshold=0.3,  # configurable
        )
```

3. Integration point: TOPS post-render work item calls `score_frame()` on each output
4. Write tests with known-good and known-bad renders

#### Task 4.2: Temporal Coherence Validator
```yaml
id: validator-temporal
priority: P3
depends_on: [validator-frame-qa]
estimated_files: 3-4 new
exit_criteria:
  - Sequence-level validation across frame ranges
  - Detection: flickering, sudden brightness shifts, material pops, geometry discontinuity
  - Metric: inter-frame difference normalized against expected motion
  - Threshold-based flagging with per-frame annotations
```

**Execution Steps:**
1. Implement inter-frame analysis:
```python
class TemporalCoherenceValidator:
    """
    Sequence-level temporal coherence validation.
    Based on 'Task Agnostic Restoration of Video Dynamics' (2206.03753)
    and 'Blind Video Deflickering' (2303.08120).
    """

    def validate_sequence(
        self, frame_paths: list[str], motion_vectors: Optional[list] = None
    ) -> SequenceReport:

        frames = [np.array(Image.open(p)) for p in frame_paths]
        issues = []

        for i in range(1, len(frames)):
            # Raw pixel difference
            diff = np.abs(frames[i].astype(float) - frames[i-1].astype(float))

            # Global brightness shift (flickering indicator)
            mean_diff = diff.mean()
            brightness_shift = abs(
                frames[i].mean() - frames[i-1].mean()
            )

            # Local anomaly: regions with high diff but low expected motion
            if motion_vectors:
                # Subtract expected motion contribution
                expected_diff = self._motion_compensated_diff(
                    frames[i-1], frames[i], motion_vectors[i-1]
                )
                anomaly = diff - expected_diff
            else:
                # Without motion vectors, use structural similarity
                from skimage.metrics import structural_similarity
                ssim_score = structural_similarity(
                    frames[i-1], frames[i], multichannel=True
                )
                anomaly_score = 1.0 - ssim_score

            if brightness_shift > self.flicker_threshold:
                issues.append(TemporalIssue(
                    frame=i,
                    type="flicker",
                    severity=brightness_shift / self.flicker_threshold,
                    description=f"Brightness shift of {brightness_shift:.1f} "
                                f"between frames {i-1} and {i}",
                ))

        return SequenceReport(
            frame_count=len(frames),
            issues=issues,
            overall_coherence=1.0 - (len(issues) / max(len(frames) - 1, 1)),
        )
```

2. Wire into TOPS: runs as post-sequence work item after all frames rendered
3. Write tests with synthetic flickering sequences

---

## Dependency Graph

```
Phase 0 (Parallel — No Dependencies)
├── rag-materials     [RAG-OPS]
├── rag-dop           [RAG-OPS]
└── rag-render        [RAG-OPS]

Phase 1 (Depends on Phase 0)
├── rag-audit         [RAG-OPS]     ← depends: rag-materials, rag-dop, rag-render
└── tops-predict-verify [TOPS]      ← depends: rag-render

Phase 2 (Depends on Phase 1)
├── safety-taxonomy     [SAFETY]    ← depends: rag-materials, rag-dop, rag-render
├── tops-step-verify    [TOPS]      ← depends: tops-predict-verify, safety-taxonomy
├── validator-frame-qa  [VALIDATOR] ← depends: tops-predict-verify
└── safety-recovery     [SAFETY]    ← depends: safety-taxonomy

Phase 3 (Depends on Phase 2)
├── tops-process-rewards [TOPS]      ← depends: tops-step-verify
└── validator-temporal   [VALIDATOR]  ← depends: validator-frame-qa
```

**Critical Path:** `rag-render → tops-predict-verify → tops-step-verify → tops-process-rewards`

---

## Execution Protocol for Claude Code

### Session Start
```bash
# Load this blueprint
cat SYNAPSE_MOE_Blueprint.md

# Verify codebase state
cd C:\Users\User\SYNAPSE
python -m pytest tests/ -x --tb=short  # ensure green baseline

# Check current RAG inventory
find synapse/routing/knowledge/ -name "*.md" | wc -l
```

### Agent Activation
```bash
# Phase 0: Parallel RAG creation (all three can run simultaneously)
# Each creates files, registers triggers, runs tests

# Phase 1: After Phase 0 complete
# RAG audit + predict-verify pattern

# Phase 2: After Phase 1 complete
# Error taxonomy + step verification + frame QA

# Phase 3: After Phase 2 complete
# Process rewards + temporal coherence
```

### Exit Criteria (All Agents)
Before marking any task complete:
1. All new files have docstrings and type hints
2. `python -m pytest tests/ -x` passes
3. `python -m mypy synapse/ --strict` passes (or maintains current compliance level)
4. New RAG entries have trigger coverage verified
5. Changes committed with conventional commit message: `feat(agent): description`

### Inter-Agent Handoff Protocol
When an agent completes a task that another agent depends on:
1. Write a handoff note in the task's exit artifact:
```python
# HANDOFF: rag-render → tops-predict-verify
# Completed: 8 new RAG entries for render output conventions
# Key files: synapse/routing/knowledge/rag_render_*.md
# Key insight: productName on RenderProduct uses timeSamples for animation
# Test coverage: tests/test_rag_render.py (6 new tests, all passing)
```
2. The dependent agent reads the handoff note before starting
3. If the handoff reveals a scope change, escalate to ORCHESTRATOR

---

## Metrics & Success Criteria

| Metric | Baseline (v5.5.0) | Target |
|--------|-------------------|--------|
| Friction incidents per session | 1.0 (9 in ~9 sessions) | < 0.3 |
| RAG entries with code examples | ~40% estimated | ≥ 80% |
| Material assignment success rate | ~66% (2/3 buggy) | ≥ 95% |
| DOP wiring success rate | ~50% (1/2 wrong) | ≥ 90% |
| Render output path detection | ~50% (1/2 buggy) | ≥ 95% |
| Pre-render verification coverage | 0% | 100% of render launches |
| Post-render quality scoring | 0% | 100% of completed frames |
| Temporal coherence validation | 0% | 100% of sequences > 1 frame |

---

## Research Reference Index

| ID | Paper | Agent | Task |
|----|-------|-------|------|
| R1 | RAG for API Docs (2503.15231) | RAG-OPS | 1.4 |
| R2 | CodeRAG-Bench (2406.14497) | RAG-OPS | 1.4 |
| R3 | ARKS Knowledge Soup (2402.12317) | RAG-OPS | 1.4 |
| R4 | Fission-GRPO (2601.15625) | SAFETY | 2.2 |
| R5 | Where Agents Fail (2509.25370) | SAFETY | 2.1 |
| R6 | Agentic Rubrics (2601.04171) | SAFETY | 2.1 |
| R7 | Predict Before Executing (2601.05930) | TOPS | 3.1 |
| R8 | Routine Framework (2507.14447) | TOPS | 3.2 |
| R9 | ToolPRMBench (2601.12294) | TOPS | 3.3 |
| R10 | STEVE Step Verification (2503.12532) | TOPS | 3.2 |
| R11 | SmartSnap Self-Verification (2512.22322) | TOPS | 3.2 |
| R12 | CLIP for IQA (2207.12396) | VALIDATOR | 4.1 |
| R13 | DepictQA (2312.08962) | VALIDATOR | 4.1 |
| R14 | Video Dynamics (2206.03753) | VALIDATOR | 4.2 |
| R15 | Blind Deflickering (2303.08120) | VALIDATOR | 4.2 |
| R16 | 3D-GPT (2310.12945) | ORCHESTRATOR | Architecture reference |
