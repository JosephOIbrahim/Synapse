"""EXPERT — the v5.42.0 surface, exactly (Law L5).

This manifest declares the panel as it ships today: the same three regions in
the same order (rail, context ribbon, faces - bc-wave BC-5 folded the profile
row into the overflow), every widget visible at standard prominence, faces dominant
(stretch 1), no system-prompt overlay. A diff between this file and the other
profiles IS the profile system — capability never varies, only prominence,
density and the prompt overlay do. Density "standard" is the unstyled
baseline: no QSS rule exists for it, so this profile renders v5.42.0 exactly.
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
        "density": "standard",
    },
    "system_prompt_overlay": "",
    "regions": [
        {   # bc-wave BC-2: two identities (mark+wordmark / model token), one
            # state sentence, Connect|Stop. The rail's other chrome reads
            # through the overflow; its hidden owners are NOT listed here
            # (the compositor applies visible=True to every listed id).
            "id": "rail",
            "widgets": [
                "mark", "wordmark", "header_status", "author_token",
                "stop", "connect",
            ],
        },
        {   # context + the CHAT / TOKEN pills (bc-wave BC-5: the profile
            # tab strip folded into the overflow; the pills ride the ribbon)
            "id": "context_ribbon",
            "widgets": ["context_label", "chat_pill", "token_pill"],
        },
        {   # dominant — the stacked faces
            "id": "faces",
            "stretch": 1,
            "widgets": ["faces_stack"],
        },
    ],
}
