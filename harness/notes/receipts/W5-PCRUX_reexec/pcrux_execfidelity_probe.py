r"""W5-PCRUX independent exec-fidelity attack (target 4) - NOT the peer's logic.

The .pypanel runs its loader via exec() in Houdini's panel context, where
__file__ is undefined and a sys.modules flush forces a fresh re-import on every
panel (re)open. A crucible must prove the *audit* reproduced THAT, and that a
plain import would have masked the loader difference (import is cached; only the
exec+flush path forces a reload).

This is the PCRUX crucible's own instrument. Run:
  HOUDINI_USER_PREF_DIR="C:/Users/User/OneDrive/Documents/houdini22.0" \
  QT_QPA_PLATFORM=offscreen \
  "C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe" \
  harness/notes/receipts/W5-PCRUX_reexec/pcrux_execfidelity_probe.py
"""
import os, sys, re, types, inspect, json, traceback
import xml.etree.ElementTree as ET

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
R = {"leg": "W5-PCRUX", "attack": "exec_fidelity", "checks": {}}
def p(*a): print(*a, flush=True)

import hou
R["hou_version"] = hou.applicationVersionString()
root = (hou.getenv("SYNAPSE_ROOT") or "C:/Users/User/SYNAPSE").replace("\\", "/")
# Resolve the pypanel Houdini actually loads (authoritative), like SEAT T5.
pypanel = hou.findFile("python_panels/synapse_panel.pypanel")
R["pypanel_resolved"] = pypanel.replace("\\", "/") if pypanel else None
R["pypanel_inside_repo"] = bool(pypanel and pypanel.replace("\\","/").lower().startswith(root.lower()))
p("hou %s ; pypanel -> %s (in repo=%s)" % (R["hou_version"], R["pypanel_resolved"], R["pypanel_inside_repo"]))

cdata = None
tree = ET.parse(pypanel)
for iface in tree.getroot().iter("interface"):
    if iface.get("name") == "synapse_panel":
        scr = iface.find("script")
        if scr is not None and scr.text:
            cdata = scr.text
        break
# Offscreen QApplication BEFORE building any widget (SynapsePanel is a QWidget).
try:
    from PySide6 import QtWidgets
except ImportError:
    from PySide2 import QtWidgets  # noqa
_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
R["qt_platform_runtime"] = _app.platformName()
p("Qt platform: %s" % R["qt_platform_runtime"])

R["checks"]["cdata_parsed"] = bool(cdata)
# flush block present in the SOURCE we are about to exec (independent regex)
R["checks"]["flush_del_present"] = bool(re.search(r"del sys\.modules\[", cdata) and re.search(r"startswith\(\s*['\"]synapse\.['\"]", cdata))
R["checks"]["flush_pop_present"] = bool(re.search(r"sys\.modules\.pop\(\s*['\"]synapse['\"]", cdata))

# --- Adversarial contrast: plain import is CACHED (id stable), so it would mask
#     any loader/flush difference. Establish that baseline first.
import importlib
m1 = importlib.import_module("synapse.panel.synapse_panel")
id_import_1 = id(m1)
m2 = importlib.import_module("synapse.panel.synapse_panel")  # cached: same object
id_import_2 = id(m2)
R["checks"]["plain_import_is_cached_same_id"] = (id_import_1 == id_import_2)
p("plain import twice -> same object id: %s (import is cached; masks reload)" % R["checks"]["plain_import_is_cached_same_id"])

# --- The exec path: bare namespace with NO __file__, sentinels planted, flush runs.
synth = "synapse.__pcrux_sentinel__"
sys.modules[synth] = types.ModuleType(synth)
sys.modules.setdefault("synapse", sys.modules.get("synapse") or types.ModuleType("synapse"))
sys.modules["pcrux_control_sentinel"] = types.ModuleType("pcrux_control_sentinel")
id_before_flush = id(sys.modules.get("synapse.panel.synapse_panel"))

ns = {"__name__": "pcrux_pypanel_exec"}   # deliberately NO __file__ (panel-context faithful)
R["checks"]["ns_has_no_file_before"] = ("__file__" not in ns)
exec(compile(cdata, "<synapse_panel.pypanel:script>", "exec"), ns)  # flush executes here
R["checks"]["ns_has_no_file_after"] = ("__file__" not in ns)          # shim never sets __file__

R["checks"]["flush_evicted_synapse_dot"] = (synth not in sys.modules)
R["checks"]["flush_popped_bare_synapse"] = ("synapse" not in sys.modules)
R["checks"]["control_survived"] = ("pcrux_control_sentinel" in sys.modules)
R["checks"]["onCreateInterface_callable"] = callable(ns.get("onCreateInterface"))
R["checks"]["createInterface_alias"] = ns.get("createInterface") is ns.get("onCreateInterface")

widget = ns["onCreateInterface"]()
wcls = type(widget)
wfile = None
try:
    wfile = inspect.getfile(wcls).replace("\\", "/")
except Exception as e:
    R["checks"]["widget_file_error"] = str(e)
R["widget_class"] = wcls.__name__
R["widget_module"] = getattr(wcls, "__module__", None)
R["widget_file"] = wfile
R["checks"]["widget_from_repo"] = bool(
    wfile and wfile.lower().startswith(root.lower())
    and R["widget_module"] == "synapse.panel.synapse_panel"
    and wcls.__name__ == "SynapsePanel")

id_after_flush = id(sys.modules.get("synapse.panel.synapse_panel"))
R["checks"]["exec_flush_forced_fresh_reimport_id_changed"] = (
    id_before_flush is not None and id_after_flush is not None and id_before_flush != id_after_flush)
# If widget is the error-fallback, capture it verbatim (honesty).
if not R["checks"]["widget_from_repo"]:
    try:
        R["widget_fallback_text"] = widget.toPlainText()[:1200]
    except Exception:
        pass

p("ns has __file__ (before/after exec): %s / %s (both False = panel-context faithful)"
  % (("__file__" in ns), R["checks"]["ns_has_no_file_after"]))
p("flush evicted synapse.* sentinel : %s" % R["checks"]["flush_evicted_synapse_dot"])
p("flush popped bare 'synapse'       : %s" % R["checks"]["flush_popped_bare_synapse"])
p("non-synapse control survived      : %s" % R["checks"]["control_survived"])
p("widget %s / %s <- %s" % (R["widget_class"], R["widget_module"], R["widget_file"]))
p("widget from repo file             : %s" % R["checks"]["widget_from_repo"])
p("exec+flush forced fresh re-import (id changed): %s" % R["checks"]["exec_flush_forced_fresh_reimport_id_changed"])

ok = all(R["checks"].get(k) is True for k in (
    "cdata_parsed","flush_del_present","flush_pop_present","ns_has_no_file_after",
    "flush_evicted_synapse_dot","flush_popped_bare_synapse","control_survived",
    "widget_from_repo","exec_flush_forced_fresh_reimport_id_changed")) and R["checks"]["plain_import_is_cached_same_id"]
R["exec_fidelity_verdict"] = "pass" if ok else "FAIL"
p("== EXEC-FIDELITY VERDICT: %s ==" % R["exec_fidelity_verdict"])
open("harness/notes/receipts/W5-PCRUX_reexec/pcrux_execfidelity_results.json","w",encoding="utf-8").write(json.dumps(R, indent=2))
sys.exit(0 if ok else 2)
