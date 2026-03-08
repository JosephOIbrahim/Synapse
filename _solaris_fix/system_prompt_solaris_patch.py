"""
Solaris Context Patch — system_prompt_solaris_patch.py
=====================================================

Drop-in enhancement for python/synapse/panel/system_prompt.py
Injects Solaris-specific guidance when the artist is working in /stage.

INSTALLATION:
    1. Add _SOLARIS_CONTEXT_GUIDANCE constant
    2. Add _solaris_context_block() function
    3. Call it from build_system_prompt() after _format_scene_context()

AGENT TEAM ASSIGNMENT: UI specialist
"""

# ─────────────────────────────────────────────────────────────────────
# New constant: Solaris-specific system prompt guidance
# ─────────────────────────────────────────────────────────────────────

_SOLARIS_CONTEXT_GUIDANCE = """\
## Solaris Context — Active

You are working in the `/stage` (LOP/Solaris) context. Follow these rules:

### Node Creation
- ALL new nodes go in `/stage`. NEVER create LOP nodes under `/obj`.
- Use `sopcreate` (not `sopimport`) for new geometry — keeps everything \
self-contained in the LOP network with no cross-context dependencies.
- Only use `sopimport` when referencing geometry that ALREADY exists in `/obj`.

### Canonical Chain (wire linearly, not merged)
```
SOPCreate → MaterialLibrary → AssignMaterial → Camera → Lights → RenderProperties → OUTPUT
```
Wire each node sequentially: `node_b.setInput(0, node_a)`. Do NOT use \
merge nodes for a standard scene chain.

### Materials
- Call `matlib.cook(force=True)` BEFORE `matlib.node("name").createNode()`.
- Use MaterialX `mtlxstandard_surface` as the default shader.
- Material paths are USD prim paths (`/materials/name`), not node paths.

### Lighting Law
- Intensity is ALWAYS 1.0 on all lights.
- Control brightness ONLY via exposure (in stops).
- Enable exposure control: `xn__inputsexposure_control_wcb` = "set"
- Then set exposure: `xn__inputsexposure_vya` = desired stops value.

### Encoded Parameters
- USD/Solaris parameters use encoded names (e.g., `xn__inputsintensity_i0a`).
- ALWAYS use `synapse_inspect_node` to discover parameter names before setting.
- Never guess parameter names — inspect first.

### Display Flag
- Set display flag on the LAST node: `output.setDisplayFlag(True)`
- The viewport shows the stage at the display-flagged node.
"""

_OBJ_CONTEXT_GUIDANCE = """\
## SOP Context — Active

You are working in the `/obj` (SOP/Object) context. Standard SOP workflows apply.
- Create geometry nodes under `/obj/geo1` or similar geometry containers.
- For Solaris/rendering work, switch to `/stage` context.
"""


# ─────────────────────────────────────────────────────────────────────
# Context-aware guidance injector
# ─────────────────────────────────────────────────────────────────────

def _solaris_context_block(context: dict) -> str | None:
    """Return context-specific guidance based on current network.

    Args:
        context: Scene context dict with "network" key.

    Returns:
        Guidance string or None if no special guidance needed.
    """
    network = context.get("network", "/obj")

    if network.startswith("/stage"):
        return _SOLARIS_CONTEXT_GUIDANCE
    elif network.startswith("/obj"):
        return _OBJ_CONTEXT_GUIDANCE

    return None


# ─────────────────────────────────────────────────────────────────────
# Patched build_system_prompt (shows integration point)
# ─────────────────────────────────────────────────────────────────────

def build_system_prompt_patched(context: dict) -> str:
    """Enhanced system prompt with context-aware Solaris guidance.

    This is a reference implementation showing where to inject the
    context block. Apply the same pattern to the existing function
    in system_prompt.py.

    Args:
        context: Dict with keys: network, selection, frame, hip

    Returns:
        Complete system prompt string.
    """
    # These would come from the existing module:
    # from system_prompt import _IDENTITY, _TOOL_GUIDANCE, _load_tone, _format_scene_context

    sections = []

    # 1. Identity (existing)
    sections.append(_IDENTITY_PLACEHOLDER)

    # 2. Tone guide (existing)
    # tone = _load_tone()
    # if tone: sections.append(tone)

    # 3. Tool guidance (existing)
    sections.append(_TOOL_GUIDANCE_PLACEHOLDER)

    # 4. Scene context (existing)
    # sections.append(_format_scene_context(context))

    # 5. NEW: Context-aware guidance injection
    ctx_guidance = _solaris_context_block(context)
    if ctx_guidance:
        sections.append(ctx_guidance)

    return "\n\n".join(sections)


# Placeholders for reference (actual values come from system_prompt.py)
_IDENTITY_PLACEHOLDER = "[IDENTITY SECTION]"
_TOOL_GUIDANCE_PLACEHOLDER = "[TOOL GUIDANCE SECTION]"


# ─────────────────────────────────────────────────────────────────────
# Integration instructions for system_prompt.py
# ─────────────────────────────────────────────────────────────────────

INTEGRATION_GUIDE = """
INTEGRATION INTO system_prompt.py
=================================

Step 1: Add the constants (_SOLARIS_CONTEXT_GUIDANCE, _OBJ_CONTEXT_GUIDANCE)
        after the existing _TOOL_GUIDANCE constant.

Step 2: Add the _solaris_context_block() function after _format_scene_context().

Step 3: In build_system_prompt(), add ONE line after the scene context:

    def build_system_prompt(context: dict) -> str:
        sections = [_IDENTITY]

        tone = _load_tone()
        if tone:
            sections.append(tone)

        sections.append(_TOOL_GUIDANCE)
        sections.append(_format_scene_context(context))

        # NEW: Context-aware Solaris guidance
        ctx_guidance = _solaris_context_block(context)
        if ctx_guidance:
            sections.append(ctx_guidance)

        return "\\n\\n".join(sections)

Step 4: Ensure context_bar.py passes the "network" key correctly.
        The default in _format_scene_context is already:
            network = context.get("network", "/obj")
        Verify that the panel's context provider actually sends this.

TOTAL CHANGES: ~50 lines added, 1 line modified in build_system_prompt().
"""
