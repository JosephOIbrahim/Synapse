# SYNAPSE Solaris Training Sprint — NodeFlow Corpus Ingestion
## Sprint Codename: **RELAY-SOLARIS**
### Source: Mario Leone / NodeFlow Series (Houdini 21) — 3 Videos, 8 Canonical Patterns

---

## Sprint Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    RELAY-SOLARIS                         │
│         "Every pattern becomes a tool that works"       │
├─────────────────────────────────────────────────────────┤
│  PHASE 1: Pattern Extraction    ██░░░░░░░░  (Research)  │
│  PHASE 2: Tool Mapping          ░░██░░░░░░  (Arch)      │
│  PHASE 3: Implementation        ░░░░████░░  (Eng)       │
│  PHASE 4: Validation            ░░░░░░░░██  (QA)        │
│  GATE: Live Houdini Smoke Test  ░░░░░░░░░█  (Prod)      │
└─────────────────────────────────────────────────────────┘
```

---

## MOE Agent Roster

| Role | Agent ID | Responsibility | Anchor Leg |
|------|----------|---------------|------------|
| **VFX Supervisor** | `AGENT-SUP` | Pattern fidelity — ensures extracted patterns match real Solaris behavior. Reviews all tool schemas for production correctness. Final sign-off. | Phase 4 Gate |
| **Researcher** | `AGENT-RES` | Corpus extraction — breaks video notes into atomic knowledge entries. Maps each pattern to USD concepts. Identifies gaps where the notes are ambiguous. | Phase 1 Lead |
| **Pipeline Architect** | `AGENT-ARC` | Tool design — maps patterns to MCP tool schemas, defines parameter interfaces, resolves ordering dependencies, designs the canonical `_SOLARIS_NODE_ORDER` extensions. | Phase 2 Lead |
| **Systems Engineer** | `AGENT-ENG` | Implementation — writes the Python `execute_python` scripts, atomic operations, idempotent guards, transaction wrappers. All code must be testable without live Houdini. | Phase 3 Lead |
| **Producer** | `AGENT-PRO` | Sprint health — monitors phase gates, flags blockers, manages the AND-node task tree, ensures no phase starts before its predecessor passes gate. | All Phases |

---

## Phase 1: Pattern Extraction (AGENT-RES leads)

### Objective
Convert the 8 canonical patterns from the NodeFlow research into FORGE-compatible knowledge entries. Each entry must be atomic, testable, and carry enough context for SYNAPSE to generate correct node networks.

### Task Tree (AND-node — ALL must complete)

```
PHASE 1 [AND]
├── P1.1 [AND] Extract Pattern 1: Canonical LOP Chain
│   ├── Node sequence with exact types and order
│   ├── Parameter defaults for each node
│   ├── Primitive path conventions (/shot/geo/$OS, etc.)
│   └── Cascading rule: chain sequentially, NEVER merge
│
├── P1.2 [AND] Extract Pattern 2: Component Builder
│   ├── Subnet structure (Geo → Material → Output)
│   ├── Purpose wiring (default→render, polyreduce→proxy, polyreduce→simproxy)
│   ├── Component Output fields (name, path, thumbnail)
│   └── Export → Reference round-trip
│
├── P1.3 [AND] Extract Pattern 3: Purpose System
│   ├── render vs proxy vs sim proxy definitions
│   ├── Viewport toggle mechanism (glasses icon mapping)
│   └── When each purpose is used in production
│
├── P1.4 [AND] Extract Pattern 4: Hierarchy Discipline
│   ├── Primitive LOP with Xform + Kind=Group
│   ├── Four canonical paths: geo, LGT, MTL, cam
│   ├── $OS variable behavior in primitive paths
│   └── How hierarchy affects render delegation
│
├── P1.5 [AND] Extract Pattern 5: Variants (Non-Destructive)
│   ├── Material variants: duplicate Component Material workflow
│   ├── Geometry variants: Component Geometry Variants node
│   ├── Explore Variants vs Set Variant distinction
│   └── Nested variant sets (geo × material)
│
├── P1.6 [AND] Extract Pattern 6: External Asset Import (Megascans)
│   ├── USDC unpack pipeline: USD Import → Transform(0.01) → Match Size
│   ├── Material import trick: Reference LOP + /materials/* wildcard
│   ├── Paste Relative Reference pattern
│   └── Save location alignment: asset/mtl/
│
├── P1.7 [AND] Extract Pattern 7: Asset Gallery + TOPs
│   ├── Asset Catalog creation workflow
│   ├── Order of ops: Thumbnail → Save → Add to Gallery
│   ├── TOPs batch node: "USD Assets to Gallery"
│   └── Shift+V shortcut for batch processing
│
└── P1.8 [AND] Extract Pattern 8: Layout + Physics
    ├── Layout LOP modes: place, line, paint, stack, scale
    ├── Critical: "Instanceable Reference" not "Point Instancer" for physics
    ├── Edit LOP → Add Physics → Use Physics
    └── Grid as static collision surface
```

### Knowledge Entry Format (per pattern)
```python
{
    "pattern_id": "SOLARIS_P1_CANONICAL_LOP_CHAIN",
    "source": "nodeflow_mario_leone_v1",
    "confidence": "high",  # direct from tutorial, not inferred
    "evolution": "charmeleon",  # structured, not yet USD-composed
    "node_sequence": [...],  # ordered list of node types
    "parameters": {...},  # default parameter values
    "constraints": [...],  # rules that must hold (e.g., "never merge SOP imports")
    "primitive_paths": {...},  # path templates
    "test_criteria": "...",  # how to verify this pattern works
    "synapse_tools": [...]  # which MCP tools this maps to
}
```

### Phase 1 Gate
- [ ] All 8 patterns extracted to knowledge entry format
- [ ] Each entry has `test_criteria` defined
- [ ] AGENT-SUP reviews for production accuracy
- [ ] No "inferred" entries — only what the source material explicitly states
- [ ] Gaps flagged with `confidence: "needs_verification"` for live Houdini testing

---

## Phase 2: Tool Mapping (AGENT-ARC leads)

### Objective
Map each pattern to existing or new SYNAPSE MCP tools. Extend `_SOLARIS_NODE_ORDER` dict. Design parameter interfaces.

### Existing Tool Audit

| Pattern | Existing Tool? | Status | Action |
|---------|---------------|--------|--------|
| P1: Canonical LOP Chain | `synapse_solaris_assemble_chain` | Partial — needs full chain template | **EXTEND** |
| P2: Component Builder | None | — | **NEW TOOL** |
| P3: Purpose System | None | — | **NEW TOOL** (or param on Component Builder) |
| P4: Hierarchy Discipline | `solaris_scene_pipeline` | Partial — primitive paths exist | **EXTEND** |
| P5: Variants | None | — | **NEW TOOL** |
| P6: External Import | None | — | **NEW TOOL** |
| P7: Gallery + TOPs | None | — | **NEW TOOL** (Phase 2 priority: low) |
| P8: Layout + Physics | None | — | **NEW TOOL** (Phase 2 priority: low) |

### New Tool Schemas

#### `synapse_solaris_component_builder`
```python
# Creates a complete Component Builder setup for a USD asset
params = {
    "asset_name": str,           # e.g., "hero_chair"
    "geometry_source": str,      # SOP path or file path
    "proxy_reduction": float,    # 0.0-1.0, default 0.05
    "materials": list[dict],     # [{"name": "wood", "type": "principled", "params": {...}}]
    "export_path": str,          # where to save .usd
    "generate_thumbnail": bool,  # default True
    "purposes": list[str],       # ["render", "proxy", "simproxy"]
}
# Returns: component builder subnet path, export path
```

#### `synapse_solaris_set_purpose`
```python
# Sets purpose on geometry within a component
params = {
    "component_path": str,       # path to component builder
    "geometry_name": str,        # which geo output
    "purpose": str,              # "render" | "proxy" | "simproxy"
}
```

#### `synapse_solaris_create_variants`
```python
# Creates material and/or geometry variants on a component
params = {
    "component_path": str,
    "variant_type": str,         # "material" | "geometry"
    "variants": list[dict],      # [{"name": "red", "material": {...}}, ...]
}
```

#### `synapse_solaris_import_megascans`
```python
# Full Megascans/Fab import pipeline
params = {
    "usdc_path": str,            # path to downloaded .usdc
    "asset_name": str,           # name for the asset
    "scale_factor": float,       # default 0.01 (Unreal→Houdini)
    "ground_asset": bool,        # Match Size justify Y minimum
    "proxy_reduction": float,    # default 0.05
    "import_materials": bool,    # use Reference LOP /materials/* trick
    "export_path": str,
}
```

#### `synapse_solaris_scene_template`
```python
# Creates the full canonical scene skeleton from Pattern 1
params = {
    "scene_name": str,           # default "shot"
    "hierarchy": dict,           # default: {"geo": [], "LGT": [], "MTL": [], "cam": []}
    "render_engine": str,        # "karma_xpu" | "karma_cpu"
    "resolution": tuple[int,int],# default (1920, 1080)
    "output_path": str,          # default "$HIP/render/$HIPNAME.png"
}
# Returns: full node chain from Primitive to USD Render ROP
```

### `_SOLARIS_NODE_ORDER` Extensions
```python
_SOLARIS_NODE_ORDER = {
    # Existing entries...
    
    # Pattern 1: Canonical LOP Chain (scene-level)
    "scene_template": [
        "primitive",          # Xform hierarchy
        "sopimport",          # Geometry (chain, don't merge)
        "materiallibrary",    # Materials
        "karmaphysicalsky",   # Lighting
        "karmarendersettings",# Render config
        "usdrender_rop",      # Final render
    ],
    
    # Pattern 2: Component Builder (asset-level)
    "component_builder": [
        "componentgeometry",
        "componentmaterial",
        "componentoutput",
    ],
    
    # Pattern 6: Megascans Import
    "megascans_import": [
        "usdimport",          # Inside SOP: unpack to polys
        "xform",              # Scale 0.01
        "matchsize",          # Ground asset
        "polyreduce",         # Proxy
        "output",             # SOP output
    ],
}
```

### Phase 2 Gate
- [ ] All patterns mapped to existing or new tools
- [ ] Tool schemas reviewed by AGENT-SUP for parameter completeness
- [ ] `_SOLARIS_NODE_ORDER` extended with no conflicts to existing entries
- [ ] Dependency graph between tools documented (e.g., component_builder depends on scene_template for hierarchy)
- [ ] Atomic operation boundaries defined for each tool

---

## Phase 3: Implementation (AGENT-ENG leads)

### Objective
Implement tool functions as atomic `execute_python` scripts with idempotent guards and transaction wrappers.

### Implementation Priority (hardest-first per AlphaProof)

```
HARDEST → EASIEST (do in this order)

1. synapse_solaris_component_builder    [HARD — subnet creation, multi-node wiring]
2. synapse_solaris_import_megascans     [HARD — SOP↔LOP bridge, material trick]
3. synapse_solaris_scene_template       [MEDIUM — extends existing assemble_chain]
4. synapse_solaris_create_variants      [MEDIUM — variant set API is well-documented]
5. synapse_solaris_set_purpose          [EASY — single parameter set]
```

### Atomic Operation Template
```python
# Every tool implementation follows this template:
def execute(params):
    """
    ATOMIC: Either all nodes are created and wired, or none are.
    IDEMPOTENT: Running twice with same params produces same result.
    PROVENANCE: Every created node gets USD custom attributes with reasoning.
    """
    import hou
    
    # 1. VALIDATE — fail fast before any mutations
    _validate_params(params)
    _validate_context()  # are we in /stage? is Solaris active?
    
    # 2. GUARD — idempotency check
    existing = _find_existing(params)
    if existing:
        return {"status": "already_exists", "path": existing}
    
    # 3. TRANSACTION — collect all operations
    ops = []
    ops.append(("create_node", {...}))
    ops.append(("set_parm", {...}))
    ops.append(("wire", {...}))
    
    # 4. EXECUTE — all or nothing
    try:
        results = _execute_batch(ops)
    except Exception as e:
        _rollback(ops)  # undo any partial work
        raise
    
    # 5. PROVENANCE — stamp reasoning
    for node in results["created_nodes"]:
        _stamp_provenance(node, {
            "tool": "synapse_solaris_component_builder",
            "params": params,
            "source_pattern": "SOLARIS_P2_COMPONENT_BUILDER",
            "reasoning": f"Created {params['asset_name']} component per NodeFlow Pattern 2",
        })
    
    return results
```

### Critical Implementation Notes

**SOP Import Chaining (Pattern 1):**
```python
# WRONG — merging SOP imports
merge = stage.createNode("merge")
for sop in sops:
    imp = stage.createNode("sopimport")
    merge.setInput(i, imp)

# RIGHT — chaining SOP imports sequentially (USD layer composition)
prev = primitive_node
for sop_path in sop_paths:
    imp = stage.createNode("sopimport")
    imp.setInput(0, prev)
    imp.parm("soppath").set(sop_path)
    imp.parm("primpath").set(f"/shot/geo/$OS")
    prev = imp  # chain continues
```

**Component Builder Subnet (Pattern 2):**
```python
# Component Builder is a subnet — must create internal structure
cb = stage.createNode("componentbuilder")  # verify with dir() first!
# If componentbuilder isn't a single node, may need manual subnet:
subnet = stage.createNode("subnet", "component_builder_" + asset_name)
# Then create internal nodes: componentgeometry, componentmaterial, componentoutput
# Wire internally, then connect subnet inputs/outputs
```

**Megascans Material Trick (Pattern 6):**
```python
# The Reference LOP trick for importing materials separately
ref = stage.createNode("reference")
ref.parm("filepath").set(usdc_path)  # same file as geometry
ref.parm("primpath").set("/materials/*")  # wildcard catches all
ref.parm("destpath").set("asset/mtl/")  # must match component hierarchy
```

### Test Strategy (without live Houdini)
```python
# Each tool gets a mock test that validates:
# 1. Parameter validation catches bad input
# 2. Node creation order matches _SOLARIS_NODE_ORDER
# 3. Wiring topology is correct (parent→child relationships)
# 4. Provenance attributes are stamped
# 5. Idempotency: calling twice returns "already_exists"
# 6. Rollback: simulated failure mid-execution leaves no orphan nodes

class TestComponentBuilder:
    def test_creates_correct_node_sequence(self):
        ops = component_builder.plan(valid_params)
        assert [op.node_type for op in ops] == [
            "componentgeometry", "componentmaterial", "componentoutput"
        ]
    
    def test_rejects_missing_asset_name(self):
        with pytest.raises(ValidationError):
            component_builder.validate({"geometry_source": "/obj/geo1"})
    
    def test_idempotent_on_existing(self, mock_stage):
        # First call creates
        r1 = component_builder.execute(params)
        assert r1["status"] == "created"
        # Second call finds existing
        r2 = component_builder.execute(params)
        assert r2["status"] == "already_exists"
    
    def test_rollback_on_failure(self, mock_stage_fails_on_wire):
        with pytest.raises(ExecutionError):
            component_builder.execute(params)
        assert mock_stage.children() == []  # no orphans
```

### Phase 3 Gate
- [ ] All 5 tools implemented with atomic/idempotent/provenance template
- [ ] Unit tests pass (mock Houdini)
- [ ] `_SOLARIS_NODE_ORDER` entries match implementation order
- [ ] No `exec(open(...).read())` — all imports are direct module imports
- [ ] All function names verified with `dir(module)` before assuming they exist
- [ ] AGENT-SUP code review passes

---

## Phase 4: Validation (AGENT-SUP leads)

### Objective
Validate against live Houdini 21.0.596 via WebSocket at `ws://localhost:9999`.

### Smoke Tests (ordered by risk)

| Test | Pattern | Pass Criteria | Blocker? |
|------|---------|--------------|----------|
| **T1: Scene Template** | P1 | Creates full chain Primitive→ROP, all paths correct | YES |
| **T2: Component Builder** | P2 | Creates subnet with geo/material/output, exports .usd | YES |
| **T3: Purpose Toggle** | P3 | Proxy visible in viewport, render geo at render time | NO |
| **T4: Hierarchy Check** | P4 | Scene Outliner shows correct tree under /shot/ | YES |
| **T5: Variant Creation** | P5 | Material variant set created, Explore Variants works | NO |
| **T6: Megascans Import** | P6 | .usdc imports at correct scale with materials | NO |
| **T7: Render Output** | P1 | USD Render ROP produces .png at $HIP/render/ | YES |

### Known Risk: BL-007 / BL-008
- **BL-007** (EXR not written to disk) — may affect T7 render output test
- **BL-008** (asset references invisible in Karma) — may affect T6 Megascans and T2 Component Builder

**Mitigation:** Run T7 and T2 early. If they fail on BL-007/BL-008, flag as architectural and don't block the sprint — the tool logic may be correct even if render output has existing bugs.

### Phase 4 Gate
- [ ] T1, T2, T4, T7 pass (blockers)
- [ ] T3, T5, T6 pass or have documented workarounds
- [ ] BL-007/BL-008 impact assessed and documented
- [ ] FORGE knowledge entries updated with any corrections from live testing
- [ ] All provenance attributes visible in USD Scene Graph Details panel

---

## FORGE Integration

### Knowledge Entry Evolution Path
```
Phase 1 output (Charmander):
  → Markdown knowledge entries, human-readable, pattern-level

Phase 3 output (Charmeleon):
  → Structured Python schemas, tool-mappable, parameter-level

Phase 4 output (Charizard — post live validation):
  → USD-composed knowledge with cross-scene query capability
  → Patterns become referenceable from any SYNAPSE session
  → FORGE can auto-generate new tools from validated patterns
```

### FORGE Ingest Command
```python
# After Phase 4 gate passes:
from synapse.forge import Runner
r = Runner()
r.ingest_corpus(
    source="nodeflow_mario_leone",
    entries=phase1_knowledge_entries,
    tools=phase3_tool_implementations,
    validation=phase4_test_results,
    confidence_floor=0.8,  # only ingest entries with high/verified confidence
)
```

---

## Sprint Metrics

| Metric | Target | Tracking |
|--------|--------|----------|
| Patterns extracted | 8/8 | Phase 1 |
| Tools designed | 5 new + 2 extended | Phase 2 |
| Tools implemented | 5/5 | Phase 3 |
| Smoke tests passing | 7/7 (4 blockers) | Phase 4 |
| Knowledge entries ingested | 8+ | Post-sprint |
| New test count | 30+ (6 per tool) | Phase 3 |
| Lines of Python | ~800-1200 est | Phase 3 |

---

## Agent Execution Instructions

### For `--dangerously-skip-permissions` autonomous runs:

```bash
# Phase 1 — Researcher
tmux new-session -s relay-solaris-p1 \
  "cd /path/to/synapse && claude-code --dangerously-skip-permissions \
   --system 'You are AGENT-RES. Your role: extract 8 Solaris patterns from the NodeFlow corpus into FORGE knowledge entries. Follow RELAY-SOLARIS Phase 1 spec exactly. Output to synapse/forge/corpus/nodeflow/. Do NOT proceed to Phase 2.'"

# Phase 2 — Architect (after P1 gate)
tmux new-session -s relay-solaris-p2 \
  "cd /path/to/synapse && claude-code --dangerously-skip-permissions \
   --system 'You are AGENT-ARC. Your role: map extracted patterns to MCP tool schemas. Read Phase 1 output from synapse/forge/corpus/nodeflow/. Design tools per RELAY-SOLARIS Phase 2 spec. Output schemas to synapse/mcp/tools/solaris/. Do NOT implement — schema only.'"

# Phase 3 — Engineer (after P2 gate)
tmux new-session -s relay-solaris-p3 \
  "cd /path/to/synapse && claude-code --dangerously-skip-permissions \
   --system 'You are AGENT-ENG. Your role: implement tool schemas from Phase 2 as atomic execute_python scripts. Read schemas from synapse/mcp/tools/solaris/. Follow the atomic operation template. Write tests. Verify function names with dir(). Do NOT merge to main.'"

# Phase 4 — Supervisor (after P3 gate)  
tmux new-session -s relay-solaris-p4 \
  "cd /path/to/synapse && claude-code --dangerously-skip-permissions \
   --system 'You are AGENT-SUP. Your role: validate Phase 3 implementations against live Houdini via ws://localhost:9999. Run smoke tests T1-T7. Flag BL-007/BL-008 if encountered. Update FORGE entries with corrections. Gate: all blocker tests must pass.'"
```

### Git Worktree Setup
```bash
# Each agent gets its own worktree
git worktree add ../synapse-p1-research relay-solaris-p1
git worktree add ../synapse-p2-arch relay-solaris-p2  
git worktree add ../synapse-p3-eng relay-solaris-p3
git worktree add ../synapse-p4-val relay-solaris-p4
```

### Producer Monitoring (AGENT-PRO)
```bash
# Run in a separate tmux pane — checks gate status
watch -n 30 'echo "=== RELAY-SOLARIS Status ===" && \
  echo "P1: $(test -f synapse/forge/corpus/nodeflow/.gate_passed && echo PASSED || echo ACTIVE)" && \
  echo "P2: $(test -f synapse/mcp/tools/solaris/.gate_passed && echo PASSED || echo ACTIVE)" && \
  echo "P3: $(test -f synapse/tests/solaris/.gate_passed && echo PASSED || echo ACTIVE)" && \
  echo "P4: $(test -f synapse/validation/solaris/.gate_passed && echo PASSED || echo ACTIVE)"'
```

---

## Hardest Branch (AlphaProof Value Propagation)

**The AND-node blocker for this sprint is Pattern 2: Component Builder.**

Why: Component Builder involves subnet creation with internal wiring — this is the pattern SYNAPSE has historically struggled with (the original Solaris assembly fix was exactly this class of problem). If the `componentbuilder` node type doesn't exist as a single createable node in Houdini 21, AGENT-ENG will need to build it as a manual subnet, which changes the entire atomic operation model.

**Action:** AGENT-ARC should verify `componentbuilder` node existence in Phase 2 before AGENT-ENG starts Phase 3. One `execute_python` call:
```python
import hou
stage = hou.node("/stage")
test = stage.createNode("componentbuilder")
print(f"EXISTS: {test is not None}, TYPE: {test.type().name()}")
test.destroy()
```

If it doesn't exist as a native node → flag as blocker, redesign as manual subnet assembly, adjust time estimate +50%.
