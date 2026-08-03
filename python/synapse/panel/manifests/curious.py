"""CURIOUS — same panel, gentler pacing (Law L5: identical capability).

Every region and widget from the expert manifest, same order, all visible —
nothing is withheld. What changes: the two orientation buttons (Connect /
Corpus) step forward, the diagnostic chrome (token meter, palette hint, TOKEN
pill) steps back, and the system prompt asks for one plain sentence of intent
before each action. Explanation rises; automation does not (L6).
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
        "deeper systems. Before each tool action, say in one plain sentence "
        "what you are about to do and why. Define jargon the first time it "
        "appears. Prefer small verifiable steps over large compound ones. "
        "Capability is unchanged — never refuse or downscale an operation "
        "because of this framing."
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
