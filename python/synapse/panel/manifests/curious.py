"""CURIOUS — same panel, gentler pacing (Law L5: identical capability).

Composition-only (rope L5-6): Curious is assembled from the EXISTING widget
vocabulary plus the system-prompt overlay — no new widgets, no rewiring.
Every region and widget from the expert manifest is present, same order —
nothing is removed, and the agent's capability is byte-identical (L5). The
diff against expert is presentation only, on two moves (L5-19): the things
that TEACH step forward — the two orientation buttons (Connect / Corpus) go
hero, the command-palette hint stands at full visibility — and the readouts
a first-session artist cannot yet act on FOLD: the rail's token economics
pair (author/token line, token meter) and the activity telemetry are
collapsed=True — present in the layout at zero height, never withheld. The
TOKEN pill stays visible (quiet), so the full numbers remain one click away
behind it, and the profile switcher restores everything in one action. The
overlay carries the behaviors that have no widget of their own — error
translation always on, inline decision narration, expanded quick actions,
promoted recipes, /explain suggested after builds, confirm-on-destructive,
jargon defined on first use. Density is "airy" (L5-18): the one panel-wide
rhythm step — replies and controls take one rung more air off the existing
spacing scale. Explanation rises; automation does not (L6).
"""

# Display copy (rope L5-10). The manifest is the single source of copy for its
# profile — tab label + first-run picker line live here, voice per TONE.md.
# The picker shows once; the choice is the artist's, and switching later is
# one click. Synapse never switches on its own (L6).
TAB_LABEL = "Curious"

PICKER_COPY = (
    "Still finding your footing in Houdini's deeper systems? This pace "
    "builds with you and explains as it goes — every decision narrated in "
    "a sentence, every error translated into plain language, jargon "
    "defined the first time it appears. Same panel, same full capability; "
    "only the pacing is gentler."
)

MANIFEST = {
    "profile": "curious",
    "defaults": {
        "visible": True,
        "collapsed": False,
        "stretch": 0,
        "prominence": "standard",
        "density": "airy",
    },
    "system_prompt_overlay": (
        "The artist at this panel is still finding their footing in Houdini's "
        "deeper systems. Build WITH them and explain as you go — the same "
        "capability, paced gently:\n"
        "- When something breaks, say what happened in plain language first "
        "— thinking out loud with a colleague, 'we' not 'you' — then offer "
        "the fix.\n"
        "- Narrate each decision inline as you make it — what you chose and "
        "why, in one sentence.\n"
        "- After each answer, spell out the obvious next quick actions in "
        "full rather than assuming them.\n"
        "- When a sequence of steps works, promote it into a named, reusable "
        "recipe the artist can ask for again.\n"
        "- After a build completes, suggest running /explain on what was "
        "built.\n"
        "- Before any destructive operation (delete, overwrite, disk write), "
        "say what will be affected and confirm first.\n"
        "- Define jargon the first time it appears — technical terms are "
        "welcome, gatekeeping is not.\n"
        "- Frame suggestions as options: 'we could try X', never 'you "
        "should'.\n"
        "Prefer small verifiable steps over large compound ones. Explanation "
        "may rise here; automation may not (L6). Capability is unchanged — "
        "never refuse or downscale an operation because of this framing."
    ),
    "regions": [
        {
            "id": "rail",
            "widgets": [
                "mark", "wordmark", "header_status",
                # Economics fold (L5-19): readouts a first-session artist
                # cannot yet act on. Collapsed, never removed — the full
                # numbers stay one click away behind the visible TOKEN pill.
                {"id": "author_token", "collapsed": True,
                 "prominence": "quiet"},
                {"id": "token_meter", "collapsed": True,
                 "prominence": "quiet"},
                # Teaching hint (L5-19): the palette hint is how commands are
                # discovered — full visibility, not quiet chrome.
                "palette_hint",
                "stop",
                "connection_dot", "connection_label",
                "connect",
                "corpus",
                # Telemetry fold (L5-19): activity chrome, same treatment as
                # the economics pair.
                {"id": "activity_meter", "collapsed": True,
                 "prominence": "quiet"},
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
