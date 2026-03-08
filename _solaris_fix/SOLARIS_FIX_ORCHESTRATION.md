# SYNAPSE Solaris Context Fix — MOE Agent Team Orchestration
## Claude Code Implementation Plan

> **Sprint metaphor:** This is a 4×100m relay. Four specialists, clean handoffs, no dropped batons. Each leg has a clear lane — no file conflicts.

---

## Team Roster (5 Agents, 4 Active + 1 Orchestrator)

| Agent | Role | Lane (files owned) | Worktree Branch |
|-------|------|-------------------|-----------------|
| **ORCHESTRATOR** | Race director — sequences legs, validates handoffs, runs merge | `master` (read-only during sprint) | `master` |
| **ROUTING** | Planner context fix — the anchor leg | `python/synapse/routing/planner.py`, `python/synapse/routing/recipes.py` | `fix/solaris-routing` |
| **UI** | System prompt + context bar | `python/synapse/panel/system_prompt.py`, `python/synapse/panel/context_bar.py` | `fix/solaris-ui` |
| **INTELLIGENCE** | RAG documents + knowledge enrichment | `rag/skills/houdini21-reference/solaris_network_blueprint.md`, `mcp_tools_usd.py`, `mcp_tools_scene.py` | `fix/solaris-rag` |
| **VALIDATION** | Tests + end-to-end verification | `tests/test_solaris_ordering.py`, `tests/test_solaris_context.py` (new) | `fix/solaris-tests` |

---

## Phase Execution Order

### Phase 0: Setup (ORCHESTRATOR)
```bash
# Create worktrees for parallel work
cd ~/SYNAPSE
git worktree add ../SYNAPSE-routing fix/solaris-routing
git worktree add ../SYNAPSE-ui fix/solaris-ui
git worktree add ../SYNAPSE-rag fix/solaris-rag
git worktree add ../SYNAPSE-tests fix/solaris-tests

# Open tmux sessions
tmux new-session -d -s routing
tmux new-session -d -s ui
tmux new-session -d -s intel
tmux new-session -d -s validation
```

**Handoff artifact:** 4 worktrees ready, branches created from master HEAD.

---

### Phase 1: INTELLIGENCE Agent (First Leg — Leadoff)
**Why first:** RAG docs must exist before other agents can reference patterns.
No code dependencies — pure content creation.

**Tasks:**
1. Create `rag/skills/houdini21-reference/solaris_network_blueprint.md`
   - Use the artifact from this conversation as the base
   - Validate trigger words don't collide with existing RAG docs
   - Run: `grep -r "solaris setup\|create scene\|build scene" rag/skills/` to check collisions

2. Update `mcp_tools_usd.py` GROUP_KNOWLEDGE:
   ```python
   # ADD to GROUP_KNOWLEDGE string:
   "SOLARIS CHAIN: Always create LOP nodes in /stage, never /obj. "
   "Canonical order: SOPCreate → MaterialLibrary → AssignMaterial → "
   "Camera → Lights → RenderProperties → OUTPUT null. Wire linearly "
   "with setInput(0, prev). Use sopcreate (not sopimport) for new geometry. "
   ```

3. Update `mcp_tools_scene.py` GROUP_KNOWLEDGE:
   ```python
   # ADD to GROUP_KNOWLEDGE string:
   "CONTEXT AWARENESS: When creating Solaris/LOP node types (lights, cameras, "
   "materials, render settings), parent MUST be /stage. Use synapse_inspect_scene "
   "to detect current context before creating nodes. "
   ```

**Handoff artifact:** Committed RAG doc + updated knowledge preambles.
**Duration:** ~20 minutes.
**Verify:** `python -c "import yaml; print('triggers OK')"` on the new RAG doc triggers.

---

### Phase 2: ROUTING Agent (Second Leg — Workhorse)
**Why second:** Needs the RAG patterns from Phase 1 as reference.
This is the **hardest subtask** (AND-node blocker identified in diagnosis).

**Tasks:**
1. Add `_infer_parent()` and signal sets to `planner.py`:
   - Use `planner_solaris_fix.py` artifact as source
   - Place after imports, before first recipe builder function
   - Import at top: `from typing import Set, Optional`

2. **Systematic replacement** — ALL 19 locations:
   ```bash
   # Find every instance
   grep -n 'params.get("parent", "/obj")' python/synapse/routing/planner.py
   grep -n "or hou.node('/obj')" python/synapse/routing/planner.py
   ```

   Replace pattern:
   ```python
   # OLD:
   parent = params.get("parent", "/obj")
   
   # NEW:
   parent = _infer_parent(params)
   ```

   For generated code strings:
   ```python
   # OLD:
   f"parent = hou.node('{parent}') or hou.node('/obj')\n"
   
   # NEW:
   _generate_parent_line(params)
   ```

3. Update `recipes.py` — Fix the SOPImport chain recipe:
   - Line 526: `sopimport_chain` recipe already has `"parent": "/stage"` ✓
   - BUT: Add a new `sopcreate_scene` recipe that builds the full canonical chain
   - Register it with higher priority triggers than the merge-based pattern

4. Run self-tests:
   ```bash
   cd ~/SYNAPSE-routing
   python -c "
   from python.synapse.routing.planner_solaris_fix import _self_test
   _self_test()
   "
   ```

**Handoff artifact:** All 19 replacements done + new recipe registered.
**Duration:** ~40 minutes (largest leg).
**Verify:** `grep -c "params.get.*parent.*obj" python/synapse/routing/planner.py` should return 0.

---

### Phase 3: UI Agent (Third Leg — Runs Parallel with Phase 2)
**Why parallel:** No file overlap with ROUTING. Touches different modules.

**Tasks:**
1. Patch `system_prompt.py`:
   - Add `_SOLARIS_CONTEXT_GUIDANCE` and `_OBJ_CONTEXT_GUIDANCE` constants
   - Add `_solaris_context_block()` function
   - Add call in `build_system_prompt()` after scene context line
   - Use `system_prompt_solaris_patch.py` artifact as source

2. Audit `context_bar.py` (if it exists):
   ```bash
   grep -n "network\|/obj\|/stage\|context" python/synapse/panel/context_bar.py
   ```
   Ensure the "network" key is actually being populated from Houdini's
   `hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor).pwd().path()`.

   If context_bar.py doesn't pass network:
   ```python
   # Add to context gathering:
   try:
       import hou
       editor = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
       network = editor.pwd().path() if editor else "/obj"
   except Exception:
       network = "/obj"
   context["network"] = network
   ```

3. Verify chat_panel.py calls build_system_prompt with context dict:
   ```bash
   grep -n "build_system_prompt\|system_prompt" python/synapse/panel/chat_panel.py
   ```

**Handoff artifact:** Patched system_prompt.py + context_bar.py verification.
**Duration:** ~20 minutes.
**Verify:** Manual check — does `/stage` context produce the Solaris guidance block?

---

### Phase 4: VALIDATION Agent (Anchor Leg — Closes It Out)
**Why last:** Needs all code changes to be committed before testing.

**Tasks:**
1. Create `tests/test_solaris_context.py`:
   ```python
   """
   Synapse — Solaris Context Inference Tests
   
   Tests _infer_parent() logic, system prompt context injection,
   and end-to-end recipe generation with Solaris awareness.
   """
   import pytest
   import sys
   import os
   
   package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
   sys.path.insert(0, os.path.join(package_root, "python"))
   
   from synapse.routing.planner import _infer_parent
   
   
   class TestInferParent:
       """Test context inference from parameters and intent."""
       
       def test_explicit_parent_wins(self):
           assert _infer_parent({"parent": "/obj/geo1"}) == "/obj/geo1"
           assert _infer_parent({"parent": "/stage"}) == "/stage"
       
       def test_current_network_stage(self):
           assert _infer_parent({}, current_network="/stage") == "/stage"
           assert _infer_parent({}, current_network="/stage/subnet") == "/stage"
       
       def test_lop_node_types_infer_stage(self):
           lop_types = [
               "domelight", "rectlight", "materiallibrary",
               "karmarenderproperties", "sopcreate", "assignmaterial",
               "camera", "spherelight", "configurestage",
           ]
           for t in lop_types:
               assert _infer_parent({"type": t}) == "/stage", f"Failed for {t}"
       
       def test_sop_node_types_infer_obj(self):
           sop_types = ["box", "scatter", "attribwrangle", "filecache"]
           for t in sop_types:
               assert _infer_parent({"type": t}) == "/obj", f"Failed for {t}"
       
       def test_intent_based_solaris(self):
           assert _infer_parent({}, intent="create a camera and light") == "/stage"
           assert _infer_parent({}, intent="set up karma render scene") == "/stage"
           assert _infer_parent({}, intent="build solaris lighting rig") == "/stage"
       
       def test_intent_based_sop(self):
           assert _infer_parent({}, intent="scatter points on grid") == "/obj"
           assert _infer_parent({}, intent="create vex wrangle") == "/obj"
       
       def test_ambiguous_defaults_obj(self):
           assert _infer_parent({}) == "/obj"
           assert _infer_parent({}, intent="do something") == "/obj"
       
       def test_no_obj_fallback_in_solaris_chain(self):
           """The critical regression test: Solaris chain must not touch /obj."""
           solaris_recipe_params = [
               {"type": "sopcreate", "name": "geo"},
               {"type": "materiallibrary", "name": "mats"},
               {"type": "assignmaterial"},
               {"type": "camera", "name": "cam"},
               {"type": "rectlight", "name": "key"},
               {"type": "domelight", "name": "dome"},
               {"type": "karmarenderproperties", "name": "karma"},
           ]
           for params in solaris_recipe_params:
               result = _infer_parent(params)
               assert result == "/stage", (
                   f"REGRESSION: {params['type']} inferred parent={result}, "
                   f"expected /stage"
               )
   
   
   class TestSystemPromptContext:
       """Test that system prompt injects correct guidance."""
       
       def test_stage_context_produces_solaris_guidance(self):
           from synapse.panel.system_prompt import _solaris_context_block
           ctx = {"network": "/stage"}
           block = _solaris_context_block(ctx)
           assert block is not None
           assert "Solaris" in block
           assert "/stage" in block
           assert "sopcreate" in block.lower()
       
       def test_obj_context_produces_sop_guidance(self):
           from synapse.panel.system_prompt import _solaris_context_block
           ctx = {"network": "/obj"}
           block = _solaris_context_block(ctx)
           assert block is not None
           assert "SOP" in block
       
       def test_default_context_fallback(self):
           from synapse.panel.system_prompt import _solaris_context_block
           ctx = {}  # No network key
           # Should not crash
           block = _solaris_context_block(ctx)
           # Default is /obj, so SOP guidance
           assert block is not None
   ```

2. Update `tests/test_solaris_ordering.py`:
   - Add test cases for merge-free linear chains
   - Verify `solaris_validate_ordering` flags merge misuse

3. Run full test suite:
   ```bash
   python -m pytest tests/test_solaris_context.py -v
   python -m pytest tests/test_solaris_ordering.py -v
   python -m pytest tests/ -k "solaris or planner or routing" -v --tb=short
   ```

4. Run mypy on changed files:
   ```bash
   mypy python/synapse/routing/planner.py python/synapse/panel/system_prompt.py --ignore-missing-imports
   ```

**Handoff artifact:** All tests pass, mypy clean.
**Duration:** ~25 minutes.
**Verify:** `pytest` exit code 0, zero mypy errors.

---

## Phase 5: Merge (ORCHESTRATOR)

```bash
# Merge in order: RAG first (no conflicts), then routing, UI, tests
cd ~/SYNAPSE
git merge fix/solaris-rag --no-ff -m "feat(rag): add solaris network blueprint + knowledge enrichment"
git merge fix/solaris-routing --no-ff -m "fix(routing): context-aware parent inference, eliminate /obj default for Solaris"
git merge fix/solaris-ui --no-ff -m "feat(ui): context-aware system prompt with Solaris guidance"
git merge fix/solaris-tests --no-ff -m "test(solaris): add context inference tests + regression guards"

# Final validation on merged master
python -m pytest tests/ -v --tb=short
mypy python/synapse/ --ignore-missing-imports

# Cleanup worktrees
git worktree remove ../SYNAPSE-routing
git worktree remove ../SYNAPSE-ui
git worktree remove ../SYNAPSE-rag
git worktree remove ../SYNAPSE-tests
```

---

## Dependency Graph (AND-node decomposition)

```
INTELLIGENCE ──→ ROUTING ──→ VALIDATION
                    ↑               ↑
               UI ──┘  ────────────┘
              (parallel)
```

- INTELLIGENCE must finish before ROUTING starts (RAG patterns needed)
- ROUTING and UI run in **parallel** (no file overlap)
- VALIDATION waits for BOTH routing and UI to merge
- ORCHESTRATOR handles all merges

**Hardest subtask (AlphaProof value):** ROUTING — 19 replacement sites, 
must not break any existing SOP recipes while adding Solaris awareness.
Surface this first, verify exhaustively.

---

## tmux Session Layout

```
┌──────────────────┬──────────────────┐
│  ORCHESTRATOR    │   ROUTING        │
│  (master)        │   (planner.py)   │
│  monitors all    │   19 edits       │
├──────────────────┼──────────────────┤
│  UI              │   VALIDATION     │
│  (system_prompt) │   (tests)        │
│  parallel w/     │   waits for      │
│  routing         │   routing + ui   │
└──────────────────┴──────────────────┘
```

Each pane runs its own Claude Code instance:
```bash
# Pane 1: ORCHESTRATOR
tmux send-keys -t routing "cd ~/SYNAPSE-routing && claude" Enter

# Pane 2: ROUTING (with agent profile)
tmux send-keys -t routing "cd ~/SYNAPSE-routing && claude --profile routing" Enter

# Pane 3: UI
tmux send-keys -t ui "cd ~/SYNAPSE-ui && claude --profile ui" Enter

# Pane 4: VALIDATION (starts idle, activated in Phase 4)
tmux send-keys -t validation "cd ~/SYNAPSE-tests && claude --profile validation" Enter
```

---

## Agent Prompts (paste into each Claude Code session)

### ROUTING Agent Prompt
```
You are the ROUTING specialist for SYNAPSE. Your job is to fix the /obj default 
bias in python/synapse/routing/planner.py and recipes.py.

CONTEXT: The planner hardcodes `params.get("parent", "/obj")` in 19+ locations,
causing all Solaris network creation to land in /obj context instead of /stage.

YOUR TASK:
1. Add _infer_parent() function and SOLARIS_SIGNALS/SOP_SIGNALS sets 
   (reference: planner_solaris_fix.py in this worktree)
2. Replace ALL 19 instances of `params.get("parent", "/obj")` with _infer_parent(params)
3. Replace ALL generated code fallbacks `or hou.node('/obj')` with context-aware versions
4. Add a sopcreate_scene recipe to recipes.py for the canonical Solaris chain
5. Run self-tests to verify

DO NOT touch any files outside planner.py and recipes.py.
Verify with: grep -c 'params.get.*parent.*"/obj"' python/synapse/routing/planner.py
Target: 0 matches.
```

### UI Agent Prompt
```
You are the UI specialist for SYNAPSE. Your job is to make the system prompt 
context-aware for Solaris.

CONTEXT: system_prompt.py defaults to "/obj" and has no Solaris-specific guidance.
When an artist is in /stage, the AI doesn't know to use /stage as parent.

YOUR TASK:
1. Add _SOLARIS_CONTEXT_GUIDANCE and _OBJ_CONTEXT_GUIDANCE constants to system_prompt.py
2. Add _solaris_context_block(context) function
3. Call it from build_system_prompt() after scene context
4. Verify context_bar.py passes "network" key correctly

Reference: system_prompt_solaris_patch.py in this worktree.
DO NOT touch routing, RAG, or test files.
```

### INTELLIGENCE Agent Prompt
```
You are the INTELLIGENCE specialist for SYNAPSE. Your job is to create the 
RAG document that teaches agents canonical Solaris network patterns.

YOUR TASK:
1. Create rag/skills/houdini21-reference/solaris_network_blueprint.md
   (reference: the solaris_network_blueprint.md in this worktree)
2. Verify trigger words don't collide: grep existing triggers in rag/skills/
3. Update GROUP_KNOWLEDGE in mcp_tools_usd.py and mcp_tools_scene.py
4. Validate markdown formatting

DO NOT touch planner.py, system_prompt.py, or test files.
```

### VALIDATION Agent Prompt
```
You are the VALIDATION specialist for SYNAPSE. Your job is to write tests 
that prevent regression of the Solaris context fix.

WAIT until ROUTING and UI agents have committed their changes.

YOUR TASK:
1. Create tests/test_solaris_context.py with:
   - TestInferParent class (11+ test methods covering all inference paths)
   - TestSystemPromptContext class (3+ test methods)
2. Update tests/test_solaris_ordering.py with linear chain validation
3. Run full test suite: pytest tests/ -k "solaris" -v
4. Run mypy on all changed files

DO NOT modify any source files. Test-only changes.
```

---

## Success Criteria (PR merge checklist)

- [ ] `grep -c 'params.get.*parent.*"/obj"' python/synapse/routing/planner.py` → **0**
- [ ] `solaris_network_blueprint.md` exists with canonical chain patterns
- [ ] System prompt includes Solaris guidance when network="/stage"
- [ ] `pytest tests/test_solaris_context.py -v` → **all pass**
- [ ] `pytest tests/test_solaris_ordering.py -v` → **all pass**
- [ ] `mypy python/synapse/routing/planner.py python/synapse/panel/system_prompt.py` → **0 errors**
- [ ] Existing SOP recipes still default to `/obj` (no regression)
- [ ] No file conflicts between agent worktrees

---

## Post-Merge Verification (Manual in Houdini)

1. Open Houdini 21, navigate to `/stage`
2. Connect SYNAPSE (ws://localhost:9999)
3. Type: "Set up a simple scene with a sphere, red material, camera, and three-point lighting"
4. **Expected:** All nodes created in `/stage`, wired linearly, SOPCreate used for sphere
5. **Failure mode:** Nodes appear in `/obj`, or merge node used, or sopimport referencing `/obj/geo1`

---

*Sprint estimated duration: ~90 minutes total (20 + 40 + 20 parallel + 25 + 10 merge)*
*D1 track metaphor: 4×100m relay in 90 minutes with clean exchanges.*
