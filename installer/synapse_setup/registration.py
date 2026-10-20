"""One author for source-install and distributed Houdini registration."""
import copy
from pathlib import Path
import re

from .safety import SetupError

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


def environment_entries(previous):
    """Normalize supported Houdini env forms without dropping user entries."""
    rows = previous.get("env", []) if previous else []
    if not isinstance(rows, list):
        raise SetupError("Existing package env is conditional or unsupported; preserve it and review migration manually.")
    result, controlled = [], set()
    for raw in rows:
        if not isinstance(raw, dict):
            raise SetupError("Existing package contains an unsupported environment entry; no choices were replaced.")
        if "var" in raw:
            row = copy.deepcopy(raw)
        elif len(raw) == 1:
            name, value = next(iter(raw.items()))
            row = {"var": name, **copy.deepcopy(value)} if isinstance(value, dict) else {"var": name, "value": copy.deepcopy(value)}
        else:
            raise SetupError("Existing package has a conditional environment entry; review migration manually.")
        name = row.get("var")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name):
            raise SetupError("Existing package has an unsupported environment variable name.")
        if name.upper() in {"SYNAPSE_ROOT", "MONETA_SRC", "PYTHONPATH", "PXR_PLUGINPATH_NAME", "MONETA_NATIVE", "SYNAPSE_MEMORY_BACKEND"}:
            name = name.upper()
            row["var"] = name
            if name in controlled:
                raise SetupError("Duplicate environment choice for " + name + "; no configuration was changed.")
            if set(row) - {"var", "value", "method"}:
                raise SetupError(name + " has conditional options; review migration manually.")
            controlled.add(name)
        result.append(row)
    return result


def native_choice(previous):
    row = next((r for r in environment_entries(previous) if r["var"] == "MONETA_NATIVE"), None)
    if row is None:
        return None
    value = row.get("value")
    if not isinstance(value, str) or value.strip().lower() not in {"0", "false", "off", "no", "", "1", "true", "on", "yes", "auto", "require"}:
        raise SetupError("MONETA_NATIVE must be a literal OFF/AUTO/REQUIRE choice; conditional values require manual review.")
    if row.get("method", "replace") != "replace":
        raise SetupError("MONETA_NATIVE needs literal replacement semantics; no configuration was changed.")
    return value


def _paths(row):
    value = row.get("value")
    paths = value.split(";") if isinstance(value, str) else value
    if (not isinstance(paths, list) or not all(isinstance(p, str) and p and "$" not in p for p in paths)
            or row.get("method", "replace") not in {"prepend", "replace"}):
        raise SetupError(row["var"] + " has conditional or unsupported paths; preserve the original package and review migration.")
    return paths


def _same_path(left, right):
    return str(left).replace("\\", "/").rstrip("/").casefold() == str(right).replace("\\", "/").rstrip("/").casefold()


def installed_package(root: Path, manifest: dict, user_home=None, *, previous=None, native_value="0", native_site=None):
    moneta = manifest.get("moneta")
    result = package(root,
                   moneta_src=root / "dependencies/moneta/src" if moneta else None,
                   moneta_schema=root / "dependencies/moneta/schema" if moneta else None,
                   backend="moneta" if moneta else "jsonl")
    if moneta:
        result["env"][1]["value"].insert(0, (root / "dependencies/moneta/src").as_posix())
    if native_site:
        result["env"][1]["value"].insert(0, Path(native_site).as_posix())
    if user_home:
        data = Path(user_home) / ".synapse"
        defaults = {"SYNAPSE_PANEL_SETTINGS": "panel_settings.json", "SYNAPSE_LEDGER_DIR": "ledger",
                    "SYNAPSE_PROVENANCE_DIR": "provenance", "SYNAPSE_LOOP_LEDGER_DIR": "loop/ledger",
                    "SYNAPSE_RECIPE_LEDGER_DIR": "recipes/ledger", "SYNAPSE_REPORTS_DIR": "reports"}
        for variable, relative in defaults.items():
            result["env"].append({"var": variable, "value": "${" + variable + "-" + (data / relative).as_posix() + "}", "method": "replace"})
    if previous:
        allowed = {"name", "enable", "load_package_once", "env", "hpath", "process_order", "synapse_setup_owner"}
        if set(previous) - allowed or not isinstance(previous.get("hpath", ""), str):
            raise SetupError("Existing package has additional paths or conditional fields; review migration manually instead of replacing them.")
        if previous.get("enable", True) is not True:
            raise SetupError("Existing package enable is conditional or disabled; no configuration was changed.")
        rows = environment_entries(previous)
        old = {row["var"]: row for row in rows}
        old_root = old.get("SYNAPSE_ROOT", {}).get("value")
        if old_root is not None and (not isinstance(old_root, str) or "$" in old_root):
            raise SetupError("Existing SYNAPSE_ROOT is conditional; no configuration was changed.")
        if (not old_root or not Path(old_root).is_absolute()
                or not _same_path(previous.get("hpath", ""), str(Path(old_root) / "houdini"))):
            raise SetupError("Existing hpath is not the canonical SYNAPSE_ROOT/houdini path; preserve this custom configuration and review migration manually.")
        replaced = {"SYNAPSE_ROOT", "MONETA_SRC", "PYTHONPATH", "PXR_PLUGINPATH_NAME", "MONETA_NATIVE"}
        for name in ("PYTHONPATH", "PXR_PLUGINPATH_NAME"):
            if name not in old:
                continue
            removed = []
            if old_root:
                removed += [old_root, str(Path(old_root) / "python"), str(Path(old_root) / "dependencies/moneta/src"), str(Path(old_root) / "dependencies/moneta/schema")]
            moneta_src = old.get("MONETA_SRC", {}).get("value")
            if isinstance(moneta_src, str) and "$" not in moneta_src:
                removed += [moneta_src, str(Path(moneta_src).parent / "schema")]
            extras = [p for p in _paths(old[name]) if not any(_same_path(p, x) for x in removed)]
            new = next((row for row in result["env"] if row["var"] == name), None)
            if new is None:
                new = {"var": name, "value": [], "method": "prepend"}
                result["env"].append(new)
            values = new["value"] if isinstance(new["value"], list) else [new["value"]]
            additions = [p for p in extras if not any(_same_path(p, x) for x in values)]
            if additions or not isinstance(new["value"], str):
                new["value"] = values + additions
            new["method"] = old[name].get("method", "replace")
        custom = [row for row in rows if row["var"] not in replaced]
        names = {row["var"] for row in custom}
        result["env"] = [row for row in result["env"] if row["var"] not in names] + custom
        for key in ("load_package_once", "process_order"):
            if key in previous:
                result[key] = copy.deepcopy(previous[key])
    if native_site:
        # H22 prepends list entries individually, reversing their precedence.
        # One path string keeps the reviewed native artifact ahead of retained
        # local paths while preserving every additional user path.
        row = next(row for row in result["env"] if row["var"] == "PYTHONPATH")
        row["value"] = ";".join(_paths(row))
    result["env"].append({"var": "MONETA_NATIVE", "value": native_value, "method": "replace"})
    return result
