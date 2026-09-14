"""Pins the artist-facing tool labels, and the thing that let them rot.

TWO DEFECTS THIS FILE EXISTS TO PREVENT RECURRING.

1. The curated map ran at **4 of 8** and nothing reported it. Four keys were
   written against the registry's SECOND column -- the wire command name -- while
   ``tool_label`` receives the FIRST, the tool name that ``claude_worker`` emits
   as ``tool_status(tool_name, status, summary)``. A key that matches nothing
   fails silently: the artist just sees the derived label instead, which looks
   like a style choice rather than a miss.

   ``test_every_curated_key_is_a_live_tool`` is the guard. It reads the live
   registry, so a tool rename turns this red instead of quietly demoting a
   curated sentence to a derived one.

2. The fallback was ``removeprefix("houdini_").replace("_"," ").capitalize()``.
   ``.capitalize()`` lowercases everything after the first character, so
   ``houdini_create_usd_prim`` reached artists as "Create usd prim", and only the
   ``houdini_`` namespace was stripped, so every synapse_/cops_/tops_ tool led
   with a namespace an artist never needs to read.

No PySide, no Houdini: pure string work, so it runs on stock CI and cannot skip.
"""
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "python"))

from synapse.panel.activity import (  # noqa: E402
    _PLAIN, _PREFIXES, _PROPER, _TOOLS, tool_label, tool_status)

_REGISTRY = os.path.join(_ROOT, "python", "synapse", "mcp", "_tool_registry.py")


def _live_tool_names():
    """Column 1 of the registry tuples -- the names the worker actually emits."""
    src = open(_REGISTRY, encoding="utf-8").read()
    names = set(re.findall(r'\(\s*"((?:synapse|houdini|cops|tops)_[a-z0-9_]+)"', src))
    assert len(names) > 100, "registry scrape found only %d names" % len(names)
    return names


def test_every_curated_key_is_a_live_tool():
    """THE GUARD. A curated key that matches no tool is a silent demotion."""
    live = _live_tool_names()
    dead = sorted(k for k in _TOOLS if k not in live)
    assert not dead, (
        "curated labels keyed to names no tool has: %s. These were written "
        "against the registry's wire-command column; tool_label receives the "
        "tool-name column." % dead)


def test_the_four_keys_that_were_dead_are_the_live_spellings():
    """The specific repair, pinned so a revert is loud."""
    live = _live_tool_names()
    for was, now in (("houdini_get_scene_info", "houdini_scene_info"),
                     ("houdini_set_parameter", "houdini_set_parm"),
                     ("network_explain", "houdini_network_explain"),
                     ("capture_viewport", "houdini_capture_viewport")):
        assert was not in live, "%s became real; revisit this pin" % was
        assert now in live, "%s is not a live tool" % now
        assert now in _TOOLS, "%s lost its curated label" % now
        assert was not in _TOOLS, "the dead key %s came back" % was


def test_capitalize_no_longer_destroys_domain_words():
    """The defect an artist actually saw."""
    assert tool_label("houdini_create_usd_prim") == "Create USD primitive"
    assert tool_label("houdini_execute_vex") == "Execute VEX"
    assert tool_label("cops_composite_aovs") == "Composite AOVs"
    assert tool_label("cops_set_opencl") == "Set OpenCL"
    assert tool_label("cops_to_materialx") == "To MaterialX"


def test_every_namespace_is_stripped_not_just_houdini():
    for name in ("synapse_search", "cops_stylize", "tops_diagnose", "houdini_render"):
        label = tool_label(name)
        for prefix in _PREFIXES:
            assert not label.lower().startswith(prefix.rstrip("_")), (name, label)


def test_only_the_first_word_is_capitalised():
    """Capitalising a later word gives Title Case fragments like 'HDA Create'."""
    assert tool_label("houdini_hda_create") == "HDA create"
    assert tool_label("synapse_solaris_assemble_chain") == "Solaris assemble chain"
    # DERIVED labels only. A curated label is a human sentence and may carry a
    # proper noun anywhere in it -- "Check the Houdini connection" is correct and
    # is not a Title Case fragment. Asserting the derivation rule over curated
    # prose was this test's own first bug.
    for name in _live_tool_names():
        if name in _TOOLS:
            continue
        words = tool_label(name).split()
        for word in words[1:]:
            assert word[:1].islower() or word in _PROPER.values() or not word[:1].isalpha(), (
                "Title Case fragment in %r from %s" % (" ".join(words), name))


def test_abbreviations_expand_to_what_an_artist_would_say():
    assert tool_label("houdini_set_parm") == "Set a parameter"      # curated
    assert tool_label("houdini_get_parm") == "Get parameter"        # derived
    assert tool_label("houdini_query_prims") == "Query primitives"
    assert tool_label("synapse_matlib_bind") == "Material library bind"
    assert "primvar" in tool_label("houdini_set_usd_primvar"), (
        "primvar is the right word and has no plain synonym; it must not expand")


def test_no_live_tool_produces_an_empty_or_namespaced_label():
    for name in _live_tool_names():
        label = tool_label(name)
        assert label and label.strip() == label, (name, repr(label))
        assert "_" not in label, (name, label)


def test_curated_labels_win_over_the_derivation():
    assert tool_label("synapse_ping") == "Check the Houdini connection"
    assert tool_label("houdini_undo") == "Undo the last change"


def test_unknown_and_empty_names_still_answer():
    assert tool_label("some_unregistered_thing") == "Some unregistered thing"
    assert tool_label("") == "Tool"
    assert tool_label(None) == "Tool"


def test_tool_status_still_composes_its_prefix():
    assert tool_status("houdini_create_usd_prim", "running") == "Running: Create USD primitive"
    assert tool_status("houdini_undo", "done") == "Finished: Undo the last change"
    assert tool_status("cops_stylize", "error") == "Failed: Stylize"


def test_the_plain_map_never_shadows_a_proper_noun():
    """A word in both tables would resolve inconsistently."""
    assert not (set(_PLAIN) & set(_PROPER)), set(_PLAIN) & set(_PROPER)


def test_the_old_fallback_really_did_produce_the_bad_labels():
    """Characterises the defect inline, so this file proves the fix on its own.

    The old expression cannot be imported any more, so reproduce it here. If
    someone reverts the derivation, the assertions above go red; this one keeps
    the evidence of WHY they exist next to them.
    """
    def old(name):
        return str(name).removeprefix("houdini_").replace("_", " ").capitalize()

    assert old("houdini_create_usd_prim") == "Create usd prim"
    assert tool_label("houdini_create_usd_prim") == "Create USD primitive"

    assert old("synapse_solaris_shotsetup_karma_xpu") == "Synapse solaris shotsetup karma xpu"
    assert tool_label("synapse_solaris_shotsetup_karma_xpu") == "Solaris shot setup Karma XPU"

    assert old("cops_reaction_diffusion") == "Cops reaction diffusion"
    assert tool_label("cops_reaction_diffusion") == "Reaction diffusion"
