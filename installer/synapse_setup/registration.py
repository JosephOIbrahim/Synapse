"""One author for source-install and distributed Houdini registration."""
from pathlib import Path

UI_CORE = {
    "shelf": ("houdini/toolbar/synapse.shelf", "toolbar/synapse.shelf"),
    "panel": ("houdini/python_panels/synapse_panel.pypanel", "python_panels/synapse_panel.pypanel"),
    "shelf_callbacks": ("houdini/scripts/python/synapse_shelf.py", "scripts/python/synapse_shelf.py"),
    "tokens": ("design/tokens.py", "scripts/python/tokens.py"),
    "styles": ("design/synapse_styles.py", "scripts/python/synapse_styles.py"),
}


def ui_assets(root: Path):
    """Yield source and Houdini-relative destination, also used by the builder."""
    for source, destination in UI_CORE.values():
        yield root / source, destination
    for source in sorted((root / "design/icons/svg").glob("*_32.svg")):
        yield source, "config/Icons/SYNAPSE_" + source.name.removesuffix("_32.svg") + ".svg"


def package(root: Path, *, moneta_src=None, moneta_schema=None, backend=None):
    root = Path(root)
    env = [
        {"var": "SYNAPSE_ROOT", "value": root.as_posix()},
        {"var": "PYTHONPATH", "value": [(root / "python").as_posix(), root.as_posix()], "method": "prepend"},
    ]
    if moneta_src:
        env.append({"var": "MONETA_SRC", "value": Path(moneta_src).as_posix()})
    if moneta_schema:
        env.append({"var": "PXR_PLUGINPATH_NAME", "value": Path(moneta_schema).as_posix(), "method": "prepend"})
    if backend:
        env.append({"var": "SYNAPSE_MEMORY_BACKEND", "value": backend})
    return {"name": "synapse", "enable": True, "load_package_once": True,
            "env": env, "hpath": (root / "houdini").as_posix()}


def installed_package(root: Path, manifest: dict, user_home=None):
    moneta = manifest.get("moneta")
    result = package(root,
                   moneta_src=root / "dependencies/moneta/src" if moneta else None,
                   moneta_schema=root / "dependencies/moneta/schema" if moneta else None,
                   backend="moneta" if moneta else "jsonl")
    if moneta:
        result["env"][1]["value"].insert(0, (root / "dependencies/moneta/src").as_posix())
    if user_home:
        data = Path(user_home) / ".synapse"
        defaults = {"SYNAPSE_PANEL_SETTINGS": "panel_settings.json", "SYNAPSE_LEDGER_DIR": "ledger",
                    "SYNAPSE_PROVENANCE_DIR": "provenance", "SYNAPSE_LOOP_LEDGER_DIR": "loop/ledger",
                    "SYNAPSE_RECIPE_LEDGER_DIR": "recipes/ledger", "SYNAPSE_REPORTS_DIR": "reports"}
        for variable, relative in defaults.items():
            result["env"].append({"var": variable, "value": "${" + variable + "-" + (data / relative).as_posix() + "}", "method": "replace"})
    return result
