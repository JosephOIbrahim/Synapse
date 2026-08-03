"""ML — the economist's read of the same panel (Law L5: identical capability).

Every region and widget from the expert manifest, same order, all visible.
What changes: token economics steps forward (the TOKEN pill and the rail meter
go hero), density is "tight" (L5-18: controls give back one rung of air off
the existing spacing scale), and the system prompt asks for terse, technical
replies with explicit model / token awareness.
"""

# Display copy (rope L5-10). Tab label + first-run picker line, voice per
# TONE.md. The choice is the artist's; Synapse never switches on its own (L6).
TAB_LABEL = "ML"

PICKER_COPY = (
    "The economist's read of the same panel. Token and model economics "
    "step forward — the TOKEN pill and the rail meter go hero — and "
    "replies stay terse and technical. Nothing added, nothing removed; "
    "prominence and tone only."
)

MANIFEST = {
    "profile": "ml",
    "defaults": {
        "visible": True,
        "collapsed": False,
        "stretch": 0,
        "prominence": "standard",
        "density": "tight",
    },
    "system_prompt_overlay": (
        "The artist at this panel is fluent in ML tooling. Keep replies terse "
        "and technical. When a choice of model, context size, or tool budget "
        "is relevant, name it explicitly rather than abstracting it away. "
        "Terse trims words, not collaboration — still build with the artist "
        "and explain when asked. Capability is unchanged — this framing "
        "adjusts tone only."
    ),
    "regions": [
        {
            "id": "rail",
            "widgets": [
                "mark", "wordmark", "header_status", "author_token",
                {"id": "token_meter", "prominence": "hero"},
                "palette_hint", "stop",
                "connection_dot", "connection_label", "connect", "corpus",
                "activity_meter",
            ],
        },
        {"id": "context_ribbon", "widgets": ["context_label"]},
        {
            "id": "mode_bar",
            "widgets": [
                "chat_pill",
                {"id": "token_pill", "prominence": "hero"},
            ],
        },
        {"id": "faces", "stretch": 1, "widgets": ["faces_stack"]},
    ],
}
