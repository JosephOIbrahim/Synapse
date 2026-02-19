# TEAM DELTA — Phase 1: Recipe Test Scaffolding

> **File ownership:** `tests/` (all test files)
> **Do NOT modify:** any non-test files

## Context

Read these first:
- `CLAUDE.md` (project conventions)
- `docs/forge/FORGE_PRODUCTION.md` (your deliverables)
- Existing test patterns: `tests/test_routing.py`

## Job: Test scaffolding for production recipes

TEAM ALPHA is creating 5 production recipes in `routing/recipes.py`.
You work in parallel — write tests based on the recipe specifications below.

### Test file: `tests/test_forge_recipes.py`

```python
"""Tests for FORGE-PRODUCTION Solaris production recipes."""
import pytest
# Follow existing test_routing.py patterns for imports and fixtures
```

### Tests per recipe

For EACH of these 5 recipes, write tests that verify:

1. **Recipe exists and returns valid handler sequence**
   ```python
   def test_{recipe_name}_returns_handler_sequence():
       # Call recipe, verify it returns a non-empty list of handler names
   ```

2. **All referenced node types exist in routing knowledge base**
   ```python
   def test_{recipe_name}_node_types_valid():
       # Extract node type references from recipe
       # Verify each exists in the knowledge base
   ```

3. **Parameter names match H21 conventions**
   ```python
   def test_{recipe_name}_parameter_encoding():
       # Check xn__ prefix where applicable
       # Verify parameter names match known Solaris/Karma parameters
   ```

4. **Recipe dependencies are satisfiable**
   ```python
   def test_{recipe_name}_no_circular_deps():
       # Verify handler sequence has no circular dependencies
   ```

5. **Recipe handles missing optional parameters gracefully**
   ```python
   def test_{recipe_name}_default_params():
       # Call with minimal params, verify defaults are sane
   ```

### The 5 recipes to test:

1. `render_turntable_production` — turntable with camera orbit, 3-point lighting, Karma XPU, AOVs
2. `character_cloth_setup` — character USD ref, MaterialX, cloth cache, subdivision
3. `destruction_sequence` — RBD cache, instancing, volumetrics, multi-pass render
4. `multi_shot_composition` — shot-based USD layers, per-shot overrides
5. `copernicus_render_comp` — render pass comp via Copernicus GPU nodes

### Important

- Do NOT test Houdini execution (no hou module required)
- Test the recipe LOGIC and routing integration only
- Follow naming: `test_{recipe}_{what}_{expected}`
- Mock any external dependencies
- If ALPHA hasn't finished recipes yet, write tests against the spec above — they'll verify once recipes land

## Done Criteria

- [ ] `tests/test_forge_recipes.py` exists
- [ ] 25+ tests (5 per recipe × 5 recipes)
- [ ] All tests that can run without recipes pass (mocked)
- [ ] Tests that depend on recipes are clearly marked
- [ ] Existing tests still pass
