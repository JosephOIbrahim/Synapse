# TEAM ECHO — Phase 4: Camera Digital Twins

> **File ownership:** camera-specific RAG, handlers, recipes
> **Do NOT modify:** non-camera handlers, autonomy/, tests (DELTA handles tests)

## Prerequisites

Phase 3 gate must pass. The autonomous pipeline is working.

## Context

Read these first:
- `CLAUDE.md` (project conventions)
- `rag/skills/houdini21-reference/camera_workflows.md` (existing camera reference, 171 lines)
- `rag/skills/houdini21-reference/solaris_parameters.md` (USD parameter encoding patterns)
- `routing/recipes.py` (existing recipe format)
- The USD camera prim spec: horizontalAperture, verticalAperture, focalLength, fStop, clippingRange, focusDistance

## Deliverable 1: Camera Sensor Database

### File: `rag/skills/houdini21-reference/camera_sensor_database.md`

```markdown
# Camera Sensor Database — Real Camera Bodies → USD Parameters

> Maps production camera bodies to Houdini USD camera parameters.
> All sensor dimensions from manufacturer spec sheets.
> USD parameters use Houdini 21 encoding (xn__ prefix where applicable).

## Camera Bodies

### ARRI Alexa 35
- Sensor: 27.99mm × 19.22mm (4.6K Open Gate)
- Max Resolution: 4608 × 3164
- USD horizontalAperture: 27.99
- USD verticalAperture: 19.22
- Native ISO: 800
- Gate Fit: horizontal (cinema standard)
- Mount: PL / LPL
- Color Science: ARRI LogC4 / AWG4
- Common Lenses (mm): 16, 21, 25, 32, 40, 50, 65, 75, 100, 135

### ARRI Alexa Mini LF
...

### RED V-Raptor [X]
...
```

**Include at minimum these 8 cameras:**
1. ARRI Alexa 35
2. ARRI Alexa Mini LF
3. RED V-Raptor [X]
4. RED Komodo-X
5. Sony Venice 2
6. Sony FX6
7. Blackmagic URSA Mini Pro 12K
8. Canon EOS C500 Mark II

**For each camera, include:**
- Sensor dimensions (mm) — width × height at max resolution mode
- Max resolution
- USD `horizontalAperture` value (= sensor width in mm)
- USD `verticalAperture` value (= sensor height in mm)
- Native ISO range
- Gate fit mode recommendation (horizontal for cinema, fill for photo)
- Lens mount
- Color science (log curve + gamut)
- Common prime lens focal lengths (mm)
- Notes (e.g., "supports anamorphic desqueeze 2x")

**CRITICAL:** Verify sensor dimensions against manufacturer spec sheets.
Use web search if needed. Wrong sensor dimensions = wrong FOV = useless.

**USD parameter encoding note:**
In Houdini 21 Solaris, USD camera parameters may use `xn__` prefix encoding.
Check existing `solaris_parameters.md` for the exact encoding pattern.
Common mappings:
- `horizontalAperture` → check if encoded
- `verticalAperture` → check if encoded
- `focalLength` → check if encoded
- `fStop` → check if encoded
- `clippingRange` → check if encoded

---

## Deliverable 2: Camera Match Recipe

### In `routing/recipes.py`: `camera_match_real`

```python
# Recipe: camera_match_real
# Input: camera_body (str), lens_mm (int), optional overrides
# Output: handler sequence to create fully configured USD camera
#
# Steps:
# 1. Look up camera_body in sensor database
# 2. create_usd_prim — camera prim at /cameras/{camera_slug}
# 3. set_usd_attribute — horizontalAperture from database
# 4. set_usd_attribute — verticalAperture from database
# 5. set_usd_attribute — focalLength from lens_mm
# 6. set_usd_attribute — clippingRange (default: [0.1, 10000])
# 7. Optionally: fStop, focusDistance from overrides
```

### Pattern matching in `routing/parser.py`:

Add patterns for:
- "match ARRI Alexa 35" → `camera_match_real`
- "match RED V-Raptor" → `camera_match_real`
- "create camera like Sony Venice" → `camera_match_real`
- "set up ARRI at 50mm" → `camera_match_real`
- Camera body names as routing triggers

---

## Deliverable 3: Combined Recipe

### In `routing/recipes.py`: `camera_match_turntable`

Chains `camera_match_real` + `render_turntable_production` (from Phase 1):

```python
# Recipe: camera_match_turntable
# Input: camera_body, lens_mm, turntable_params
# Output: handler sequence for matched camera + full production turntable
#
# "Render a turntable with an ARRI Alexa 35 at 50mm"
# → Creates matched camera → sets up production turntable → renders
```

### Pattern matching:
- "turntable with ARRI" → `camera_match_turntable`
- "render turntable ARRI Alexa at 50mm" → `camera_match_turntable`
- "production turntable RED V-Raptor" → `camera_match_turntable`

---

## Deliverable 4: Tests (coordinate with DELTA)

Generate a test spec for DELTA to implement:

```python
# tests/test_camera_twins.py

# test_camera_database_completeness — all 8 cameras present
# test_camera_sensor_dimensions_valid — all dimensions positive, width > height
# test_camera_usd_mapping — horizontalAperture matches sensor width
# test_camera_match_recipe_exists — recipe routes correctly
# test_camera_match_arri_alexa35 — specific camera → correct params
# test_camera_match_red_vraptor — specific camera → correct params
# test_camera_match_unknown_body — unknown camera name → graceful error
# test_camera_match_turntable_chains — combined recipe produces correct sequence
# test_camera_lens_range_valid — all listed lenses are positive values
# test_camera_parameter_encoding — xn__ prefix applied where needed
```

---

## Done Criteria

- [ ] `camera_sensor_database.md` with 8+ cameras, verified specs
- [ ] `camera_match_real` recipe in `recipes.py`
- [ ] `camera_match_turntable` recipe in `recipes.py`
- [ ] `parser.py` updated with camera name patterns
- [ ] Test spec delivered to DELTA
- [ ] Existing tests still pass
