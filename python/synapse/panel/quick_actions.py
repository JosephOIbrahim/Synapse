"""Quick action button definitions for the Synapse chat panel."""

QUICK_ACTIONS = [
    {
        "label": "Explain",
        "icon": "BUTTONS_help",
        "prompt": (
            "Explain the selected node network. What does each node do "
            "and how does data flow through them?"
        ),
        "requires_selection": True,
        "tooltip": "Explain selected network",
    },
    {
        "label": "Make HDA",
        "icon": "COMMON_subnet",
        "prompt": (
            "Package the selected subnet into an HDA with a clean "
            "interface and help card."
        ),
        "requires_selection": True,
        "tooltip": "Convert selection to HDA",
    },
    {
        "label": "Fix Error",
        "icon": "STATUS_warning",
        "prompt": (
            "The selected node has a cook error. Diagnose the issue "
            "and suggest a fix."
        ),
        "requires_selection": True,
        "tooltip": "Diagnose cook errors",
    },
    {
        "label": "Optimize",
        "icon": "BUTTONS_resimulate",
        "prompt": (
            "Analyze this network for performance issues and suggest "
            "optimizations."
        ),
        "requires_selection": True,
        "tooltip": "Performance analysis",
    },
    {
        "label": "VEX Help",
        "icon": "SOP_attribwrangle",
        "prompt": (
            "Help me write VEX code for the selected wrangle node. "
            "What should the code do?"
        ),
        "requires_selection": True,
        "tooltip": "VEX coding assistance",
    },
]
