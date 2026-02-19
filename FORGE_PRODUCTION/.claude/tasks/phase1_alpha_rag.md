# TEAM ALPHA — Phase 1: RAG Scan + Ingestion

> **File ownership:** `rag/skills/houdini21-reference/`, `routing/recipes.py`, `routing/parser.py`
> **Do NOT modify:** handlers, agent, tests, mcp_server

## Context

Read these first:
- `CLAUDE.md` (project conventions)
- `docs/forge/FORGE_PRODUCTION.md` (your deliverables)
- `.claude/agent.md` (task rules)

## Job 1: Catalog the Houdini RAG

Scan `G:\HOUDINI21_RAG_SYSTEM` and report:

```bash
# Directory structure (2 levels)
find "G:/HOUDINI21_RAG_SYSTEM" -maxdepth 2 -type d

# File count by extension
find "G:/HOUDINI21_RAG_SYSTEM" -type f | sed 's/.*\.//' | sort | uniq -c | sort -rn

# File listing
find "G:/HOUDINI21_RAG_SYSTEM" -type f -name "*.md" -o -name "*.txt" -o -name "*.json" | head -100
```

Report back with:
- Directory structure
- File count by type
- Topics covered — specifically flag: Solaris, TOPS/PDG, Copernicus, Karma, USD composition, MaterialX, temporal coherence, ACES
- **Wait for orchestrator review before ingesting anything**

## Job 2: Gap Analysis

Cross-reference against existing SYNAPSE RAG:

```bash
ls -la rag/skills/houdini21-reference/
```

Current files:
- `solaris_nodes.md`, `solaris_parameters.md` — Solaris reference
- `karma_rendering_guide.md` — Karma reference
- `usd_stage_composition.md` — USD composition
- `lighting.md` — lighting workflows
- `materialx_shaders.md` — MaterialX reference
- `tops_wedging.md` — TOPS wedging
- `render_farm.md` — render farm via TOPS
- `camera_workflows.md` — camera reference

Identify what the H21 RAG has that SYNAPSE doesn't. Priority gaps:
1. Solaris production workflows (lighting rigs, material pipelines, render passes)
2. TOPS advanced patterns (dynamic work items, feedback dependencies, partitioners)
3. Copernicus GPU compositing
4. USD composition debugging
5. Karma XPU vs CPU differences
6. Temporal coherence in animation
7. ACES color management in H21

## Job 3: Ingest (after orchestrator approval)

For each gap, create a new RAG file following the existing format:
- Look at any existing `.md` file in `rag/skills/houdini21-reference/` for the pattern
- Extract and restructure — never copy verbatim
- Generate SHA-256 manifest entry
- Use `_gen_` prefix for generated content, no prefix for curated

## Job 4: Production Recipes

After RAG is ingested, add 5 recipes to `routing/recipes.py`:

Read existing recipes first to match the format exactly:
```bash
cat routing/recipes.py
```

### Recipe 1: `render_turntable_production`
Full production turntable — not the basic one that exists now.
- Camera orbit (configurable radius, height, frame range)
- 3-point lighting rig (key, fill, rim — using USD light types from RAG)
- Ground plane with shadow catcher material
- Karma XPU render settings for production quality
- AOV setup: beauty, depth, normal, motion vector, crypto matte
- Output path convention: `$HIP/render/$HIPNAME/$HIPNAME.$F4.exr`
- Motion blur enabled, appropriate samples

### Recipe 2: `character_cloth_setup`
- Reference character USD asset (sublayer or reference arc)
- MaterialX material assignment for skin, cloth, hair
- Cloth sim cache reference (Vellum cache → SOP import → Solaris)
- Subdivision + displacement settings on render geometry
- Proper visibility/purpose tagging (render vs proxy)

### Recipe 3: `destruction_sequence`
- RBD sim cache import (SOP → Solaris via SOP Import LOP)
- Point instancing for debris (small pieces via instanceable prims)
- Volumetric dust/smoke cache reference
- Multi-pass render setup:
  - Beauty pass (full lighting)
  - Depth pass (camera depth)
  - Motion vectors
  - Crypto mattes (object, material, asset)
- Render layer management via USD collections

### Recipe 4: `multi_shot_composition`
- Shot-based USD layer composition
- Shared asset base layer (sublayered)
- Per-shot override layers (strongest opinion)
- Shot camera (per-shot camera prim)
- Shot-specific lighting adjustments
- Render layer management per shot

### Recipe 5: `copernicus_render_comp`
- Render pass compositing via Copernicus GPU nodes
- Input: beauty + utility AOVs
- Composite: beauty over, depth-based effects, crypto matte extraction
- Color grade: exposure, contrast, saturation (basic)
- Output: composited EXR

Each recipe must:
- Follow the exact format of existing recipes in `recipes.py`
- Reference specific node types from the RAG (not guessed)
- Use correct H21 parameter names (xn__ encoding where applicable)
- Include all required handler calls in the correct order

Also update `routing/parser.py` with regex patterns for the new recipes.

## Done Criteria

- [ ] RAG scan report delivered
- [ ] Gap analysis complete
- [ ] New RAG files created (SHA-256 manifests, proper format)
- [ ] 5 production recipes in `recipes.py`
- [ ] `parser.py` updated with new patterns
- [ ] All existing tests still pass
