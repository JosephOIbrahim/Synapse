"""
Tool palette taxonomy -- classify tools into (verb, context) for the ⌘K palette.

RETIRED 2026-08-01 (RSI loop F): this module used to also host ``filter_tools()``,
which classified the artist's message through ``shared.router.MOERouter`` and
narrowed the tool list to the routed agent's domain. It is deleted. It had ZERO
references anywhere in the repository -- not production, not tests, not dynamic
dispatch -- while being the sole non-test call site of ``MOERouter.route()``.
Two documents written independently of the RSI harness had already recorded it
as dead (docs/RFC_agent_usd_ledger.md:307, docs/SCIENCE_HARNESS_LEDGER.md:256).
Its private support went with it: the module-level ``MOERouter`` singleton and
``_get_router()``, ``_ROUTER_AVAILABLE``, ``_BASE_TOOLS``, ``_AGENT_TOOL_MAP``,
and the ``sys.path`` bridge that existed only to import ``shared/``.

What remains is what the panel actually calls: ``classify_tool()`` plus the
two-axis palette taxonomy (``command_palette.py:69``, ``tool_palette.py:28``).
Pure, side-effect free, and with no dependency on ``shared/`` at all.
"""

from __future__ import annotations


# ── Two-axis palette taxonomy (Mile 6) ───────────────────────────
# The ⌘K palette lets the artist self-identify two ways: by what they want
# DONE (verb) and by WHERE they are (context). Pure classification — no router,
# no side effects — so both palettes can share one taxonomy.
PALETTE_VERBS = ("build", "fix", "explain", "optimize", "render")
PALETTE_CONTEXTS = ("SOP", "LOP", "COP", "Karma", "USD")

# verb keyword sets, checked in priority order; "build" is the default.
_VERB_KEYWORDS = {
    "render":   ("render", "karma", "husk", "farm", "flipbook", "rendersettings"),
    "fix":      ("fix", "repair", "diagnose", "doctor", "undo", "redo", "recover",
                 "validate", "preflight", "cleanup", "migrate", "heal"),
    "optimize": ("optim", "profile", "metric", "tune", "wedge", "batch",
                 "scheduler", "performance"),
    "explain":  ("explain", "inspect", "query", "network_explain", "trace",
                 "analyze", "lookup", "search", "recall", "describe", "status",
                 "summary", "scene_info", "stage_info", "get_", "info",
                 "capture", "monitor", "stats", "help"),
}
_VERB_ORDER = ("render", "fix", "optimize", "explain")

# context keyword sets, checked in priority order; no match → None ("Other").
_CONTEXT_KEYWORDS = {
    "COP":   ("cops_", "copernicus", "pixel_sort", "reaction_diffusion", "wetmap",
              "slap_comp", "stylize", "growth_propagation", "composite_aov",
              "temporal_analysis"),
    "Karma": ("karma", "husk", "mtlx", "materialx", "material", "light", "render",
              "farm", "flipbook", "aov", "frame"),
    # "instancer" is kept for the point_instancer tool family (the USD
    # PointInstancer prim is live H22 vocabulary — NOT the removed
    # Lop/instancer); the H22 canonical LOP renames are listed explicitly
    # (W.3: copytopoints ex-instancer, paintinstances ex-layout).
    "USD":   ("usd", "prim", "stage", "sublayer", "payload", "variant",
              "collection", "reference", "instancer", "copytopoints",
              "paintinstances"),
    "LOP":   ("solaris", "lop"),
    "SOP":   ("sop", "scatter", "vex", "wrangle", "deform"),
}
_CONTEXT_ORDER = ("COP", "Karma", "USD", "LOP", "SOP")


def classify_tool(name, title="", desc=""):
    """Classify a tool/command into ``(verb, context)`` for the two-axis palette.

    verb    ∈ PALETTE_VERBS          — what the artist wants done (default 'build')
    context ∈ PALETTE_CONTEXTS|None  — where they are (None = no clear context)

    Pure and side-effect free; safe to call from any UI thread.
    """
    text = " ".join((str(name or ""), str(title or ""), str(desc or ""))).lower()
    verb = "build"
    for v in _VERB_ORDER:
        if any(k in text for k in _VERB_KEYWORDS[v]):
            verb = v
            break
    context = None
    for ctx in _CONTEXT_ORDER:
        if any(k in text for k in _CONTEXT_KEYWORDS[ctx]):
            context = ctx
            break
    return verb, context
