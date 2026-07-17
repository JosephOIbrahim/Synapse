"""MaterialX emitted-spelling conformance (C-MTLX, proof-leg PL-M1 §G1b).

Pins the repo's emitted MaterialX node-type strings to the probe-verified
22.0.368 truth, so spelling drift fails loud instead of raising at an artist's
``createNode`` (the BL-007 / phantom-API class). Two probes ground the fixture:
N-6 (`docs/reviews/h22-now-probes-2026-07-16.md:149`) and the C-MTLX hython
re-probe (2026-07-17, 22.0.368) — both confirm ``mtlxstandard_volume`` ABSENT
and ``mtlxvolume`` present (volume *shader*: parms ``vdf``/``edf``).

Pure-python — no ``hou``. Live resolution stays with
``synapse.core.mtlx_types.mtlx_type_survival()``; this fixture freezes the
*spellings* so an edit that resurrects the phantom (or typos a survivor) is
caught in CI.
"""

from __future__ import annotations

from pathlib import Path

from synapse.core.mtlx_types import (
    MTLX_GEOMPROPVALUE,
    MTLX_IMAGE,
    MTLX_NORMALMAP,
    MTLX_STANDARD_SURFACE,
    MTLX_TYPES,
    MTLX_TYPES_RAG_UNDOCUMENTED,
    MTLX_VOLUME,
)

_REPO = Path(__file__).resolve().parent.parent

# Frozen fixture — the probe-verified emitted surface on 22.0.368. Changing
# this list is a deliberate act that must ride a probe, never a drive-by edit.
_VERIFIED_EMITTED_SPELLINGS = frozenset(
    {
        "mtlxstandard_surface",
        "mtlximage",
        "mtlxnormalmap",
        "mtlxgeompropvalue",
        "mtlxvolume",
    }
)

# Confirmed-absent on 22.0.368 (N-6 + C-MTLX re-probe). Re-litigation requires
# new empirical evidence from a newer build (the phantom-quarantine rule).
_PHANTOM = "mtlxstandard_volume"


def test_emitted_surface_matches_probe_fixture() -> None:
    """MTLX_TYPES is exactly the probe-verified spelling set — no phantom, no
    unprobed addition sneaks into the emitted surface."""
    assert set(MTLX_TYPES) == set(_VERIFIED_EMITTED_SPELLINGS)
    assert len(MTLX_TYPES) == len(set(MTLX_TYPES)), "duplicate spelling in MTLX_TYPES"


def test_phantom_not_emitted() -> None:
    """The removed pre-1.39 volume shader never re-enters the emitted set."""
    assert _PHANTOM not in MTLX_TYPES
    assert _PHANTOM not in MTLX_TYPES_RAG_UNDOCUMENTED


def test_volume_constant_is_the_h22_survivor() -> None:
    """MTLX_VOLUME carries the probe-verified shader spelling (not the
    ``mtlxvolumematerial`` binder, not the dead phantom)."""
    assert MTLX_VOLUME == "mtlxvolume"


def test_named_constants_match_their_spellings() -> None:
    assert MTLX_STANDARD_SURFACE == "mtlxstandard_surface"
    assert MTLX_IMAGE == "mtlximage"
    assert MTLX_NORMALMAP == "mtlxnormalmap"
    assert MTLX_GEOMPROPVALUE == "mtlxgeompropvalue"


def test_render_recipes_emit_no_phantom() -> None:
    """The single historical call site (render_recipes.py:701, the destruction
    recipe's dust_shader) emits the survivor and never the phantom literal."""
    src = (
        _REPO / "python" / "synapse" / "routing" / "recipes" / "render_recipes.py"
    ).read_text(encoding="utf-8")
    assert _PHANTOM not in src, (
        "render_recipes.py references the mtlxstandard_volume phantom — "
        "ABSENT on 22.0.368; emit MTLX_VOLUME (mtlxvolume) instead"
    )
    assert "MTLX_VOLUME" in src, "dust_shader call site should emit MTLX_VOLUME"


def test_recipe_registry_emits_survivor_in_destruction_recipe() -> None:
    """Behavioral pin: the registered destruction recipe's generated code
    creates ``mtlxvolume`` (named dust_shader) — the emitted text an artist
    actually runs, not just the module source."""
    from synapse.routing.recipes.base import RecipeRegistry

    registry = RecipeRegistry()
    all_code: list[str] = []
    for recipe in registry.recipes:  # public copy-returning property (base.py:173)
        for step in getattr(recipe, "steps", []) or []:
            template = getattr(step, "payload_template", None) or {}
            for value in template.values():
                if isinstance(value, str):
                    all_code.append(value)
    joined = "\n".join(all_code)
    assert _PHANTOM not in joined, "a registered recipe still emits the phantom"
    assert "'mtlxvolume', 'dust_shader'" in joined, (
        "destruction recipe should create mtlxvolume as dust_shader"
    )
