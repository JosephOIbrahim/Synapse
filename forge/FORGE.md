# FORGE: Factory for Optimized Recursive Growth Engine
## SYNAPSE Self-Improvement Loop — Claude Code Blueprint v1.0

> **Mission:** Battle-test SYNAPSE through simulated VFX production pressure using autonomous AI agents, classify every failure, generate fixes, verify improvements, and grow an institutional knowledge corpus that drives SYNAPSE toward v25.0.

> **Execution Model:** Claude Code orchestrates Task sub-agents. Each agent is a VFX production role with a persona, expertise domain, and structured reporting obligation. Agents call SYNAPSE MCP tools against live Houdini. The system is designed to be set-and-forget with progress reporting.

---

## Quick Start

```bash
# From SYNAPSE project root in Claude Code:
# 
# Run a single improvement cycle:
#   "forge cycle 15 --agents all --tier 2 --focus lighting,materials"
#
# Run continuous cycles (autonomous mode):
#   "forge run --cycles 10 --tier-ramp --report-interval 5"
#
# Check status:
#   "forge status"
#
# Review backlog (human-in-the-loop items):
#   "forge review"
#
# View metrics dashboard:
#   "forge metrics"
```

---

## Architecture

```
╔══════════════════════════════════════════════════════════════════╗
║  LAYER 3: REFACTOR ENGINE (Human-in-the-Loop)                   ║
║  Joe reviews: tool gap proposals, architecture questions,        ║
║  workflow redesigns, v25.0 milestone planning                    ║
║  Trigger: `forge review` or improvement_delta flatlines          ║
╠══════════════════════════════════════════════════════════════════╣
║  LAYER 2: IMPROVEMENT ENGINE (Automated)                         ║
║  Classifies failures → generates fixes → applies atomically →   ║
║  verifies via re-run → updates corpus → computes delta metrics   ║
╠══════════════════════════════════════════════════════════════════╣
║  LAYER 1: AGENT STUDIO (Automated)                               ║
║  5 VFX production roles run scenarios through SYNAPSE MCP tools  ║
║  against live Houdini. Structured ScenarioResult output.         ║
╚══════════════════════════════════════════════════════════════════╝

Data flows UP (results → classification → metrics → human review)
Decisions flow DOWN (human direction → engine config → agent scenarios)
Corpus grows LATERALLY (each cycle feeds the next cycle's knowledge)
```

---

## Agent Roster

| Agent | Persona File | Role | Activates On |
|-------|-------------|------|-------------|
| **SUPERVISOR** | `agents/supervisor.md` | Quality oracle. Evaluates outputs against production standards. | Quality assessment, render evaluation, artistic judgment |
| **RESEARCHER** | `agents/researcher.md` | Coverage expander. Pushes into untested territory. | Novel workflows, capability discovery, edge cases |
| **ARCHITECT** | `agents/pipeline_architect.md` | Data flow thinker. Stress-tests pipelines and composition. | USD composition, TOPS/PDG, cross-system handoffs |
| **ENGINEER** | `agents/systems_engineer.md` | Reliability hammer. Runs things N times, finds edge cases. | Stress testing, parametric variation, regression hunting |
| **PRODUCER** | `agents/producer.md` | Production viability. Measures time, throughput, blockers. | Performance, efficiency, production-readiness |

### MoE Routing (Scenario → Agent Assignment)

Scenarios are routed to **top-k agents (k=2-3)** based on feature extraction:

```
Features:
  domain:     lighting | fx | lookdev | layout | pipeline | render | general
  complexity: single_tool | workflow | cross_department | production
  focus:      quality | reliability | performance | coverage | architecture
  stage:      setup | execution | validation | handoff
```

Routing rules (see engine/router.py for implementation):
- `focus=quality` → SUPERVISOR primary
- `focus=coverage` → RESEARCHER primary
- `focus=architecture` → ARCHITECT primary
- `focus=reliability` → ENGINEER primary
- `focus=performance` → PRODUCER primary
- `complexity=cross_department` → ARCHITECT + SUPERVISOR
- `complexity=production` → All agents, PRODUCER tracks throughput
- Novel/untested domain → RESEARCHER primary, SUPERVISOR evaluates

---

## Cycle Execution Protocol

### Phase 1: LOAD (Setup)
```
1. Read forge/metrics/cycles.json for last cycle number and state
2. Read forge/corpus/ for accumulated knowledge
3. Load scenario registry from forge/scenarios/registry.json
4. Determine which scenarios to run based on:
   - Tier level requested (or auto-ramp based on pass rate)
   - Focus area requested (or rotate through all domains)
   - Previous cycle's failure patterns (regression priority)
5. Route scenarios to agents via MoE router
```

### Phase 2: EXECUTE (Agent Studio)
```
For each agent assignment:
  1. Spawn Task sub-agent with:
     - Agent persona prompt (from agents/*.md)
     - Assigned scenario definition
     - Relevant corpus entries for this domain
     - Available SYNAPSE MCP tools list
  2. Sub-agent executes scenario against live Houdini
  3. Sub-agent produces structured ScenarioResult JSON
  4. Collect result, update progress bar

CRITICAL CONSTRAINTS:
  - Each sub-agent gets ONE scenario at a time
  - Sub-agents MUST call real MCP tools (no simulation/mocking)
  - Sub-agents MUST report even partial results if they hit errors
  - Houdini state must be clean between scenarios (scene reset)
  - Maximum 60 seconds per tool call timeout
  - Maximum 10 minutes per scenario timeout
```

### Phase 3: CLASSIFY (Improvement Engine)
```
For each ScenarioResult:
  1. If success=true:
     - Record capability confirmation
     - Check for friction_notes (worked but suboptimal)
     - Check for missing_tools suggestions
  2. If success=false:
     - Classify failure into FailureCategory
     - Check if this matches a known pattern in corpus
     - If known pattern: increment recurrence_count
     - If new pattern: create new observation
  3. For all results:
     - Extract tool_call sequences for efficiency analysis
     - Record timing data for Producer metrics
```

### Phase 4: GENERATE (Fix Production)
```
Route by FailureCategory:

  AUTOMATED (apply immediately):
    MISSING_CONVENTION   → Skill file with verified pattern
    HALLUCINATED_API     → Negative example + correct code
    WRONG_TARGET         → CLAUDE.md negative constraint
    PARAMETER_CONFUSION  → MCP tool description fix
    WRONG_ORDERING       → Ordering rule added to knowledge layer

  HUMAN REVIEW (queue in backlog):
    TOOL_GAP             → Tool specification proposal
    WORKFLOW_FRICTION    → Composite tool proposal
    MISSING_GUARDRAIL    → Safety check proposal (needs human sign-off)
    COMPOSITION_ERROR    → Architecture question
    SLOW_OPERATION       → Performance optimization proposal

  SKIP (observe only):
    PARTIAL_EXECUTION    → Log for pattern detection
    MEMORY_PRESSURE      → Log for infrastructure planning
```

### Phase 5: VERIFY (Re-run)
```
For each automated fix applied:
  1. Re-run the EXACT scenario that triggered the failure
  2. If pass → fix validated, confidence++
  3. If same failure → fix didn't work, escalate to human review
  4. If different failure → new failure record, re-enter classification
```

### Phase 6: REPORT (Metrics + Status)
```
1. Compute CycleMetrics (see engine/metrics.py)
2. Update forge/metrics/cycles.json
3. Update corpus with new entries
4. Generate progress report:

╔══════════════════════════════════════════════════════════╗
║  FORGE CYCLE {N} COMPLETE                                ║
╠══════════════════════════════════════════════════════════╣
║  Scenarios:  {run}/{total}     Pass Rate: {%} ({delta}) ║
║  Fixes:      {applied}/{generated}  Validated: {%}      ║
║  Corpus:     +{new_entries} entries  Total: {total}      ║
║  Backlog:    +{new_items} for human review               ║
║  Friction:   {score} ({delta} from last cycle)           ║
║                                                          ║
║  ████████████████████░░░░░  Cycle {N}/{total_cycles}     ║
║                                                          ║
║  Top failures:                                           ║
║    1. {category}: {count} ({description})                ║
║    2. {category}: {count} ({description})                ║
║                                                          ║
║  improvement_delta: {value}                              ║
║  {FLATLINE WARNING if delta < 0.5% for 3+ cycles}       ║
╚══════════════════════════════════════════════════════════╝
```

---

## Autonomous Mode Protocol

When running multiple cycles (`forge run --cycles N`):

```
1. Execute Cycle 1 at requested tier
2. After each cycle:
   a. If pass_rate > 90% AND tier < max_tier → tier_ramp (increase complexity)
   b. If pass_rate < 60% → hold tier, focus on failures
   c. If improvement_delta < 0.5% for 3 consecutive cycles → STOP
      → Generate comprehensive report
      → Queue architecture review for human (Layer 3)
   d. If regression_count > 3 → STOP
      → Something broke, needs human eyes
3. Between cycles:
   a. Reset Houdini scene to clean state
   b. Update corpus
   c. Display progress:

   FORGE AUTONOMOUS RUN
   ████████░░░░░░░░░░░░  Cycle 4/10  |  Pass: 84%  |  Δ: +3.2%
   Last: 2 fixes applied, 1 queued for review
   ETA: ~{minutes} remaining

4. On completion:
   → Generate full run summary
   → Export metrics CSV
   → List all human-review items
   → Generate v25.0 insight report
```

---

## Scenario Tiers

### Tier 1: Single Tool (Cycles 1-5)
Individual MCP tool calls. Does this tool work? Does it return what it should?
- Create a node
- Set a parameter
- Query scene state
- Render a single frame
- Read/write attributes

### Tier 2: Workflow (Cycles 6-15)
Multi-tool sequences that represent a real artist workflow.
- Build a 3-point light rig → assign materials → render
- Create FLIP sim → set boundary conditions → cache
- Import USD asset → set variants → compose into scene
- Set up TOPS network → configure wedges → submit

### Tier 3: Cross-Department (Cycles 16-30)
Handoffs between specialties. Where departmental assumptions clash.
- LAYOUT builds scene → LOOKDEV adds materials → LIGHTING renders
- FX creates sim → COMP extracts AOVs → validates output paths
- PIPE sets up TOPS → ENGINEER stress-tests → PRODUCER measures throughput

### Tier 4: Production Realistic (Cycles 30+)
Full shot assembly with competing concerns.
- Complete shot from asset ingestion to final render
- Multiple artists working on overlapping USD layers
- Render farm submission with wedging and quality gates
- Scene iteration with memory persistence across cycles

---

## Corpus Evolution (Pokémon Model)

```
OBSERVATION (raw)
  → Captured from single scenario failure/success
  → confidence: 0.0-0.3
  → Lives in: corpus/observations/

    ↓ (validated by 3+ scenarios across 2+ cycles)

PATTERN (validated)
  → Confirmed recurring behavior
  → confidence: 0.3-0.7
  → Lives in: corpus/patterns/

    ↓ (confidence > 0.7 AND recurrence > 5)

RULE (crystallized)
  → Promoted to SYNAPSE knowledge layer
  → Becomes: skill file, CLAUDE.md entry, or test case
  → Lives in: corpus/rules/ AND synapse source
```

---

## Safety Constraints

1. **Scene Isolation:** Every scenario runs against a fresh/clean Houdini scene. No scenario inherits state from a previous scenario unless explicitly designed to test persistence.

2. **Atomic Fixes:** All automated fixes use SYNAPSE's existing atomic operation patterns. No fix modifies more than one file. Every fix is reversible.

3. **Regression Gate:** If a cycle produces MORE failures than the previous cycle (regression_count > improvement_count), the system STOPS and flags for human review.

4. **No Destructive Operations:** Agents NEVER delete files, purge caches, or modify SYNAPSE source code directly. They only ADD to corpus, ADD skill files, ADD test cases, and PROPOSE source changes in the backlog.

5. **Houdini Health Check:** Before each cycle, verify Houdini is responsive via a ping MCP call. If Houdini is unresponsive, wait and retry 3 times before aborting.

6. **Token Budget:** Each sub-agent Task is budgeted. If a scenario is consuming excessive tokens (agent is stuck in a loop), terminate and record as PARTIAL_EXECUTION.

---

## File Structure

```
forge/
├── FORGE.md                          # This file (Claude Code blueprint)
├── agents/
│   ├── supervisor.md                 # VFX Supervisor persona
│   ├── researcher.md                 # VFX Researcher persona
│   ├── pipeline_architect.md         # Pipeline Architect persona
│   ├── systems_engineer.md           # Systems Engineer persona
│   └── producer.md                   # Producer persona
├── scenarios/
│   ├── registry.json                 # Master scenario registry
│   ├── tier1/                        # Single-tool scenarios
│   ├── tier2/                        # Workflow scenarios
│   └── tier3/                        # Cross-department scenarios
├── engine/
│   ├── __init__.py
│   ├── schemas.py                    # All dataclasses
│   ├── classifier.py                 # Failure classification
│   ├── router.py                     # MoE scenario routing
│   ├── corpus_manager.py             # Corpus CRUD + evolution
│   ├── metrics.py                    # Delta metrics computation
│   └── reporter.py                   # Status/progress display
├── corpus/
│   ├── manifest.json                 # SHA-256 tracking
│   ├── observations/                 # Raw findings
│   ├── patterns/                     # Validated patterns
│   └── rules/                        # Crystallized rules
├── metrics/
│   └── cycles.json                   # Cycle-over-cycle data
└── backlog/
    └── human_review.json             # Items for human review
```

---

## Integration Points

### SYNAPSE MCP Tools (Available to Agents)
Agents call these via the SYNAPSE MCP server at ws://localhost:9999.
The full tool list is in SYNAPSE's MCP registry (43 tools as of v24.x).

Key tool categories agents use:
- **Scene:** create_node, set_parameter, query_scene, list_nodes
- **Render:** render_frame, render_sequence, get_render_settings
- **USD:** compose_layer, set_variant, inspect_stage, resolve_paths
- **Materials:** assign_material, create_material, inspect_material
- **TOPS:** create_top_network, configure_wedge, submit_cook
- **Memory:** save_memory, load_memory, query_memory
- **Safety:** undo, redo, checkpoint, validate_scene

### Metrics Export
`forge/metrics/cycles.json` is the persistent record. Format:
```json
{
  "cycles": [
    {
      "cycle_number": 1,
      "timestamp": "2026-02-18T10:00:00Z",
      "scenarios_run": 12,
      "pass_rate": 0.75,
      "failure_categories": {"MISSING_CONVENTION": 2, "PARAMETER_CONFUSION": 1},
      "fixes_generated": 3,
      "fixes_validated": 2,
      "fixes_failed": 1,
      "new_tool_gaps": ["composite_material_assign"],
      "friction_score": 1.8,
      "regression_count": 0,
      "improvement_delta": null,
      "corpus_entries_added": 5,
      "total_corpus_entries": 5
    }
  ]
}
```

---

## v25.0 Convergence Signal

The system is driving toward v25.0 readiness. Key milestones:

| Signal | Meaning | Action |
|--------|---------|--------|
| Pass rate > 95% at Tier 3 | Core workflows are solid | Ready for Tier 4 production scenarios |
| improvement_delta flatlines | Automated fixes exhausted | Human architecture review needed |
| Tool gaps cluster in one area | Subsystem needs redesign | v25.0 refactor target identified |
| Friction score < 1.2 | Workflows are efficient | Focus shifts to new capabilities |
| Zero regressions for 5 cycles | Stability achieved | Ready for external testing |

When ALL signals are green → v25.0 refactor scope is empirically defined, not guessed.
