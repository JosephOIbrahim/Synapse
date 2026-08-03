"""CURIOUS — same panel, gentler pacing (Law L5: identical capability).

Composition-only (rope L5-6): Curious is assembled from the EXISTING widget
vocabulary plus the system-prompt overlay — no new widgets, no rewiring.
Every region and widget from the expert manifest, same order, all visible —
nothing is withheld. The diff against expert is presentation only: the two
orientation buttons (Connect / Corpus) step forward, the diagnostic chrome
(token meter, palette hint, TOKEN pill) steps back, and the overlay carries
the behaviors that have no widget of their own — error translation always
on, inline decision narration, expanded quick actions, promoted recipes,
/explain suggested after builds, confirm-on-destructive, jargon defined on
first use. Explanation rises; automation does not (L6).
"""

MANIFEST = {
    "profile": "curious",
    "defaults": {
        "visible": True,
        "collapsed": False,
        "stretch": 0,
        "prominence": "standard",
    },
    "system_prompt_overlay": (
        "The artist at this panel is still finding their footing in Houdini's "
        "deeper systems. Pace the same capability gently:\n"
        "- Always translate any Houdini or pipeline error into plain "
        "language first, then give the fix.\n"
        "- Narrate each decision inline as you make it — what you chose and "
        "why, in one sentence.\n"
        "- After each answer, spell out the obvious next quick actions in "
        "full rather than assuming them.\n"
        "- When a sequence of steps works, promote it into a named, reusable "
        "recipe the artist can ask for again.\n"
        "- After a build completes, suggest running /explain on what was "
        "just built.\n"
        "- Before any destructive operation (delete, overwrite, disk write), "
        "say what will be affected and confirm first.\n"
        "- Define jargon the first time it appears.\n"
        "Prefer small verifiable steps over large compound ones. Capability "
        "is unchanged — never refuse or downscale an operation because of "
        "this framing."
    ),
    "regions": [
        {
            "id": "rail",
            "widgets": [
                "mark", "wordmark", "header_status", "author_token",
                {"id": "token_meter", "prominence": "quiet"},
                {"id": "palette_hint", "prominence": "quiet"},
                "stop",
                "connection_dot", "connection_label",
                {"id": "connect", "prominence": "hero"},
                {"id": "corpus", "prominence": "hero"},
                "activity_meter",
            ],
        },
        {"id": "context_ribbon", "widgets": ["context_label"]},
        {
            "id": "mode_bar",
            "widgets": [
                "chat_pill",
                {"id": "token_pill", "prominence": "quiet"},
            ],
        },
        {"id": "faces", "stretch": 1, "widgets": ["faces_stack"]},
    ],
}
