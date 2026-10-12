"""Load the intact copied Solaris mixin without running SYNAPSE package startup.

This is an integration seam, not the production panel/dispatcher/bridge. Native
execution is forbidden until a coordinated, separately pinned controller exists.
"""
import hashlib
import importlib
import importlib.abc
import json
from pathlib import Path
import sys
import types

PREFIX = "release_subject"
FORBIDDEN = ("panel", "host", "memory", "websocket", "bridge")

class SubjectImportGuard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "synapse" or fullname.startswith("synapse."):
            raise ImportError("Production package imports are excluded at this seam")
        if fullname.startswith(PREFIX + "."):
            if any(part in FORBIDDEN for part in fullname.split(".")):
                raise ImportError("Excluded subject subsystem: " + fullname)
        return None

def load_subject(source_root, manifest_path):
    source_root = Path(source_root).resolve()
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if source_root != Path(manifest["source_root"]).resolve():
        raise RuntimeError("Subject root does not match the frozen source manifest")
    for entry in manifest["files"]:
        path = (source_root / entry["path"]).resolve()
        if not path.is_relative_to(source_root):
            raise RuntimeError("Source pin outside the isolated root")
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise RuntimeError("Changed source pin: " + entry["path"])
    if any(key == PREFIX or key.startswith(PREFIX + ".") for key in sys.modules):
        raise RuntimeError("Subject already loaded; use a fresh process per tier")
    if any(key == "synapse" or key.startswith("synapse.") for key in sys.modules):
        raise RuntimeError("A production package was already imported")
    sys.meta_path.insert(0, SubjectImportGuard())
    package_root = source_root / "python" / "synapse"
    for suffix in ("", ".core", ".server", ".routing"):
        module = types.ModuleType(PREFIX + suffix)
        module.__path__ = [str(package_root.joinpath(*suffix.lstrip(".").split(".")))
                           if suffix else str(package_root)]
        module.__package__ = PREFIX + suffix
        sys.modules[module.__name__] = module
    handler = importlib.import_module(PREFIX + ".server.handlers_solaris_graph")
    planner = importlib.import_module(PREFIX + ".server.solaris_graph_plan")
    errors = importlib.import_module(PREFIX + ".core.errors")
    loaded = [name for name in sys.modules if name.startswith(PREFIX + ".")]
    if any(any(part in FORBIDDEN for part in name.split(".")) for name in loaded):
        raise RuntimeError("An excluded production subsystem was imported")
    for name in loaded:
        origin = getattr(sys.modules[name], "__file__", None)
        if origin and not Path(origin).resolve().is_relative_to(package_root):
            raise RuntimeError("Subject import origin escaped the pinned source")
    return handler.SolarisGraphMixin(), planner, errors.SynapseUserError

def imported_source_paths():
    return sorted({str(Path(module.__file__).resolve())
                   for name, module in sys.modules.items()
                   if name.startswith(PREFIX + ".") and getattr(module, "__file__", None)})
