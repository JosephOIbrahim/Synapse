"""EXPERT — the v5.42.0 surface, exactly (Law L5).

This manifest declares the panel as it ships today: the same four regions in
the same order, every widget visible at standard prominence, faces dominant
(stretch 1), no system-prompt overlay. A diff between this file and the other
profiles IS the profile system — capability never varies, only prominence and
the prompt overlay do.
"""

# Display copy (rope L5-10). Tab label + first-run picker line, voice per
# TONE.md. The choice is the artist's; Synapse never switches on its own (L6).
TAB_LABEL = "Expert"

PICKER_COPY = (
    "The panel exactly as it ships in v5.42.0 — every widget at standard "
    "prominence, no overlay, no added narration. Dense readouts for an "
    "artist who already thinks in nodes. The other two profiles are "
    "compositions of this one."
)

MANIFEST = {
    "profile": "expert",
    "defaults": {
        "visible": True,
        "collapsed": False,
        "stretch": 0,
        "prominence": "standard",
    },
    "system_prompt_overlay": "",
    "regions": [
        {   # mark · brand · author · Stop (+ connection / corpus / activity)
            "id": "rail",
            "widgets": [
                "mark", "wordmark", "header_status", "author_token",
                "token_meter", "palette_hint", "stop",
                "connection_dot", "connection_label", "connect", "corpus",
                "activity_meter",
            ],
        },
        {"id": "context_ribbon", "widgets": ["context_label"]},
        {   # the CHAT surface label (v9.1)
            "id": "mode_bar",
            "widgets": ["chat_pill", "token_pill"],
        },
        {   # dominant — the stacked faces
            "id": "faces",
            "stretch": 1,
            "widgets": ["faces_stack"],
        },
    ],
}
