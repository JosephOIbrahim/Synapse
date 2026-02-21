"""HDA creation controller — orchestrates prompt -> recipe -> build -> result.

Sits between the UI views and the WebSocket bridge. Selects a recipe
based on the user's prompt, sends the build request, and relays
progress/result signals back to the views.
"""

try:
    from PySide6.QtCore import QObject, Signal
except ImportError:
    from PySide2.QtCore import QObject, Signal

from synapse.routing.hda_recipes import HDA_RECIPES, CONTEXT_TO_CATEGORY


class HdaController(QObject):
    """Orchestrates prompt -> recipe -> build -> validate -> report."""

    progress = Signal(str, int, str)   # stage_name, pct, detail
    result = Signal(dict)              # success/failure result
    error = Signal(str)                # error message

    def __init__(self, bridge=None, parent=None):
        super().__init__(parent)
        self._bridge = bridge
        self._active = False

        # Connect bridge signals if available
        if bridge is not None:
            bridge.hda_progress.connect(self._on_bridge_progress)
            bridge.hda_result.connect(self._on_bridge_result)

    def execute(self, prompt, context, options):
        """Start HDA creation from a natural language prompt.

        Parameters
        ----------
        prompt : str
            Natural language description of the desired HDA.
        context : str
            Node context — 'SOP', 'LOP', 'DOP', 'COP', 'TOP'.
        options : dict
            Options dict with keys like 'include_help', 'add_to_toolbar'.
        """
        if self._active:
            self.error.emit("HDA creation already in progress")
            return

        self._active = True
        self.progress.emit("parsing_prompt", 5, "Understanding your description...")

        # Select recipe based on prompt + context
        recipe = self._select_recipe(prompt, context)

        if recipe is None:
            self.progress.emit(
                "selecting_recipe", 10, "No matching recipe found"
            )
            self._active = False
            self.result.emit({
                "success": False,
                "error": (
                    "No recipe matches: '{}' in {} context".format(
                        prompt[:50], context
                    )
                ),
                "detail": "Try a more specific description or different context.",
            })
            return

        self.progress.emit(
            "selecting_recipe", 15,
            "Using recipe: {}".format(recipe["name"]),
        )

        # Build the hda_package payload from the recipe
        category = CONTEXT_TO_CATEGORY.get(context, "Sop")
        payload = {
            "command": "hda_package",
            "payload": {
                "description": prompt,
                "name": recipe["name"],
                "category": category,
                "save_path": "$HIP/otls/{}.hda".format(recipe["name"]),
                "nodes": [
                    {
                        "type": entry["type"],
                        "name": entry["name"],
                        "parms": entry.get("parms", {}),
                    }
                    for entry in recipe.get("node_graph", [])
                ],
                "connections": recipe.get("connections", []),
                "promoted_parms": recipe.get("promote_parameters", []),
            },
        }

        if options.get("include_help"):
            payload["payload"]["include_help"] = True

        # Send to Houdini via bridge
        if self._bridge is not None:
            self._bridge.send(payload)
        else:
            # No bridge (testing) — emit failure
            self._active = False
            self.result.emit({
                "success": False,
                "error": "Not connected to SYNAPSE server",
            })

    def _select_recipe(self, prompt, context):
        """Match prompt to best recipe by keyword overlap.

        Parameters
        ----------
        prompt : str
            User's natural language description.
        context : str
            Node context filter ('SOP', 'LOP', etc.).

        Returns
        -------
        dict or None
            Best matching recipe, or None if no match.
        """
        prompt_lower = prompt.lower()

        best = None
        best_score = 0

        for _key, recipe in HDA_RECIPES.items():
            if recipe.get("context", "SOP") != context:
                continue

            score = 0

            # Score by description keyword presence
            desc_words = recipe["description"].lower().split()
            for word in desc_words:
                if len(word) > 3 and word in prompt_lower:
                    score += 1

            # Name matches weighted higher
            name_words = recipe["name"].lower().replace("_", " ").split()
            for word in name_words:
                if word in prompt_lower:
                    score += 2

            if score > best_score:
                best_score = score
                best = recipe

        return best

    def _on_bridge_progress(self, data):
        """Handle progress updates from Houdini."""
        self.progress.emit(
            data.get("stage", ""),
            data.get("progress_pct", 0),
            data.get("detail", ""),
        )

    def _on_bridge_result(self, data):
        """Handle completion from Houdini."""
        self._active = False
        self.result.emit(data)

    def cancel(self):
        """Cancel in-progress HDA creation."""
        if self._active:
            if self._bridge is not None:
                self._bridge.send_command("undo", {})
            self._active = False

    @property
    def active(self):
        """Whether an HDA build is currently in progress."""
        return self._active
