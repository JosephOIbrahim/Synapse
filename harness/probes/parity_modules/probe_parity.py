r"""W5-PARITY — panel parity 1/2: prove every module the panel executes is the
repo copy, byte-for-byte, under the real hython.

Answers Joe's report (2026-08-16): "verify design panel is 1:1 with the repo;
panel reported stale after relaunch." Mechanical, first-hand, receipts-over-claims.

RUN (the exact recipe — never silently substitute the interpreter):

    HOUDINI_USER_PREF_DIR="C:/Users/User/OneDrive/Documents/houdini22.0" \
    QT_QPA_PLATFORM=offscreen \
    "C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe" \
    harness/probes/parity_modules/probe_parity.py

The deployed package (…/houdini22.0/packages/synapse.json) hard-codes
SYNAPSE_ROOT=C:/Users/User/SYNAPSE, so under this recipe the REAL hython imports
synapse.panel.* from the MAIN tree — i.e. what the live Houdini panel actually
executes. This probe measures that, then cross-checks it byte-for-byte against
the wave5/parity worktree it lives in.

SCOPE (precise, so the prose does not overclaim): parity is proven for the panel
subtree python/synapse/panel/**/*.py (the design panel's own code, 90 modules).
It does NOT byte-check the panel's wider import closure (synapse.core.*,
synapse.server.*, shared.*) — those load from the same main tree but are outside
this leg's frame. Per module, the load-bearing parity signal is
`worktree_matches_loaded` (worktree bytes == the bytes hython actually loaded);
`sha_match` (disk==inspect.getsource) is a fresh-process self-consistency check
and is near-tautological on its own — it is recorded because the mission names it,
not because it independently establishes drift.

Writes results.json next to this file; prints first-hand stdout (capture it to
hython_stdout.txt alongside). GUI pixel render is OUT OF SCOPE (Joe's seat).

Exit code: 0 if no acceptance predicate FAILED (UNKNOWN is allowed with a
recorded blocked step, per the harness constitution); 2 if any predicate FAILED.
"""
import os
import sys
import json
import glob
import hashlib
import inspect
import tokenize
import types
import importlib
import traceback

# Offscreen BEFORE any Qt import (belt-and-suspenders; the recipe also sets it).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def p(*a):
    print(*a, flush=True)


def raw_sha(path):
    """sha256 of the file's raw bytes on disk (byte-for-byte)."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def norm_source_sha(path):
    """sha256 of the source as Python's own source machinery reads it
    (tokenize.open == the linecache path: encoding cookie honoured, universal
    newlines -> '\n'). Comparable to inspect.getsource() without a CRLF false
    negative on Windows."""
    with tokenize.open(path) as f:
        return hashlib.sha256(f.read().encode("utf-8")).hexdigest()


def getsource_sha(mod):
    return hashlib.sha256(inspect.getsource(mod).encode("utf-8")).hexdigest()


def norm(path):
    return os.path.normcase(os.path.abspath(path)).replace("\\", "/")


# ── Roots ────────────────────────────────────────────────────────────────
# This probe lives at <WT>/harness/probes/parity_modules/probe_parity.py
_THIS = os.path.abspath(__file__)
WT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS))))
WT_PANEL_GLOB = os.path.join(WT_ROOT, "python", "synapse", "panel", "**", "*.py")
WT_PY = os.path.join(WT_ROOT, "python")
REPO_ANCHOR = "c:/users/user/synapse"   # normcased root every __file__ must be under
RESULTS_PATH = os.path.join(os.path.dirname(_THIS), "results.json")

R = {
    "leg": "W5-PARITY",
    "probe": "harness/probes/parity_modules/probe_parity.py",
    "worktree_root": norm(WT_ROOT),
    "sections": {},
    "acceptance": [],   # [{predicate, verdict, evidence}]
}


def record_acceptance(predicate, verdict, evidence):
    R["acceptance"].append({"predicate": predicate, "verdict": verdict, "evidence": evidence})
    p("  ACCEPTANCE [{}] {}".format(verdict, predicate))


# ══════════════════════════════════════════════════════════════════════════
# Section 0 / Target 1 — real hython + real package load
# ══════════════════════════════════════════════════════════════════════════
p("=" * 78)
p("SECTION 0 — ENVIRONMENT / LOAD PROOF (target 1)")
p("=" * 78)
sec0 = {}
sec0["python_version"] = sys.version.split()[0]
sec0["executable"] = norm(sys.executable)
p("python      : " + sec0["python_version"])
p("executable  : " + sec0["executable"])

try:
    import hou
    sec0["hou_import"] = True
    sec0["hou_version"] = hou.applicationVersionString()
    p("hou version : " + sec0["hou_version"])
except Exception as e:
    sec0["hou_import"] = False
    sec0["hou_error"] = "".join(traceback.format_exception_only(type(e), e)).strip()
    p("hou import FAILED: " + sec0["hou_error"])
    R["sections"]["s0_env"] = sec0
    record_acceptance("real hython imports hou (recipe interpreter)", "FAIL", "hou import raised")
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(R, f, indent=2)
    p("PROBE_ABORTED — no hou")
    sys.exit(2)

# Package load-proof: hpath must contain the MAIN tree's houdini/ dir.
try:
    hpath = hou.getenv("HOUDINI_PATH") or ""
except Exception:
    hpath = ""
sec0["houdini_path"] = hpath.replace("\\", "/")
sec0["synapse_root_hou"] = (hou.getenv("SYNAPSE_ROOT") or "").replace("\\", "/")
sec0["synapse_root_env"] = (os.environ.get("SYNAPSE_ROOT") or "").replace("\\", "/")
sec0["pref_dir"] = (os.environ.get("HOUDINI_USER_PREF_DIR") or "").replace("\\", "/")
sec0["qt_platform"] = os.environ.get("QT_QPA_PLATFORM", "")
main_hpath_token = "c:/users/user/synapse/houdini"
sec0["package_loaded"] = main_hpath_token in sec0["houdini_path"].lower()
# which python trees are on sys.path (the real import resolution surface)
sec0["sys_path_head"] = [pp.replace("\\", "/") for pp in sys.path[:8]]
sec0["main_python_on_path"] = any(norm(pp) == norm(os.path.join("C:/Users/User/SYNAPSE", "python")) for pp in sys.path)
p("HOUDINI_PATH contains main houdini/ : {}".format(sec0["package_loaded"]))
p("SYNAPSE_ROOT (hou.getenv)           : {}".format(sec0["synapse_root_hou"]))
p("HOUDINI_USER_PREF_DIR               : {}".format(sec0["pref_dir"]))
p("QT_QPA_PLATFORM                     : {}".format(sec0["qt_platform"]))
p("main-tree python/ on sys.path       : {}".format(sec0["main_python_on_path"]))
R["sections"]["s0_env"] = sec0
record_acceptance(
    "real hython (Houdini 22.0.400) loads the deployed synapse package (hou.houdiniPath contains the main houdini/ dir)",
    "pass" if sec0["package_loaded"] else "FAIL",
    "hou.getenv('HOUDINI_PATH')={!r}".format(sec0["houdini_path"]),
)


# ══════════════════════════════════════════════════════════════════════════
# Section 2 / Target 2 — module provenance, EXHAUSTIVE
# ══════════════════════════════════════════════════════════════════════════
p("")
p("=" * 78)
p("SECTION 2 — MODULE PROVENANCE, EXHAUSTIVE (target 2)")
p("=" * 78)

wt_files = sorted(glob.glob(WT_PANEL_GLOB, recursive=True))
glob_count = len(wt_files)
p("glob python/synapse/panel/**/*.py (worktree) -> {} files".format(glob_count))


def dotted_name(pyfile, py_root):
    rel = os.path.relpath(pyfile, py_root).replace("\\", "/")
    parts = rel.split("/")
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


rows = []
for wtf in wt_files:
    dotted = dotted_name(wtf, WT_PY)
    row = {
        "module": dotted,
        "worktree_file": norm(wtf),
        "worktree_sha256": raw_sha(wtf),
        "imported": False,
        "file": None,
        "in_repo": False,
        "loaded_tree": None,
        "sha_match": None,          # normalized disk@__file__ == getsource(module)
        "loaded_sha256": None,      # raw bytes of __file__
        "worktree_matches_loaded": None,  # byte-for-byte: live panel copy == this branch
        "error": None,
    }
    try:
        mod = importlib.import_module(dotted)
        row["imported"] = True
        mf = getattr(mod, "__file__", None)
        if mf:
            row["file"] = norm(mf)
            row["in_repo"] = row["file"].startswith(REPO_ANCHOR)
            low = row["file"].lower()
            if "/.claude/worktrees/" in low:
                row["loaded_tree"] = "worktree"
            elif low.startswith("c:/users/user/synapse/python"):
                row["loaded_tree"] = "main"
            else:
                row["loaded_tree"] = "other"
            try:
                row["loaded_sha256"] = raw_sha(mf)
                row["worktree_matches_loaded"] = (row["loaded_sha256"] == row["worktree_sha256"])
            except Exception as e:
                row["error"] = "sha:" + str(e)
            try:
                row["sha_match"] = (norm_source_sha(mf) == getsource_sha(mod))
            except Exception as e:
                row["sha_match"] = None
                row["error"] = (row["error"] or "") + " getsource:" + str(e)
        else:
            row["error"] = "no __file__"
    except Exception as e:
        row["error"] = "".join(traceback.format_exception_only(type(e), e)).strip()[:300]
    rows.append(row)

R["sections"]["s2_modules"] = {
    "glob_count": glob_count,
    "row_count": len(rows),
    "scope": "python/synapse/panel/**/*.py (panel subtree only; NOT the wider import closure synapse.core.*/synapse.server.*/shared.*)",
    "parity_signal": "worktree_matches_loaded is load-bearing (cross-tree raw-byte equality); sha_match is fresh-process self-consistency, near-tautological alone",
    "rows": rows,
}

n_imported = sum(1 for r in rows if r["imported"])
n_in_repo = sum(1 for r in rows if r["in_repo"])
n_sha = sum(1 for r in rows if r["sha_match"] is True)
n_wt_match = sum(1 for r in rows if r["worktree_matches_loaded"] is True)
n_main = sum(1 for r in rows if r["loaded_tree"] == "main")
failed = [r for r in rows if not r["imported"] or not r["in_repo"]
          or r["sha_match"] is not True or r["worktree_matches_loaded"] is not True]

p("rows emitted          : {}".format(len(rows)))
p("imported OK           : {}/{}".format(n_imported, len(rows)))
p("__file__ in repo      : {}/{}".format(n_in_repo, len(rows)))
p("loaded from MAIN tree : {}/{}".format(n_main, len(rows)))
p("sha_match (disk==getsource) : {}/{}".format(n_sha, len(rows)))
p("worktree==loaded bytes      : {}/{}".format(n_wt_match, len(rows)))
if failed:
    p("NON-CLEAN ROWS ({}):".format(len(failed)))
    for r in failed[:40]:
        p("  - {} imported={} in_repo={} sha={} wt==loaded={} err={}".format(
            r["module"], r["imported"], r["in_repo"], r["sha_match"],
            r["worktree_matches_loaded"], r["error"]))

exhaustive = (glob_count == len(rows))
record_acceptance(
    "EXHAUSTIVE: glob-count == results-row-count",
    "pass" if exhaustive else "FAIL",
    "glob={} rows={}".format(glob_count, len(rows)),
)
all_clean = (n_imported == len(rows) and n_in_repo == len(rows)
             and n_sha == len(rows) and n_wt_match == len(rows))
record_acceptance(
    "every panel module imports under hython with __file__ in the repo and disk==imported sha (byte-for-byte parity w/ branch)",
    "pass" if all_clean else "FAIL",
    "imported={}/{} in_repo={}/{} sha_match={}/{} worktree==loaded={}/{}".format(
        n_imported, len(rows), n_in_repo, len(rows), n_sha, len(rows), n_wt_match, len(rows)),
)


# ══════════════════════════════════════════════════════════════════════════
# Section 3 / Target 3 — pypanel shim fidelity (exec + sentinel flush + widget)
# ══════════════════════════════════════════════════════════════════════════
p("")
p("=" * 78)
p("SECTION 3 — PYPANEL SHIM FIDELITY (target 3)")
p("=" * 78)
sec3 = {}

# The pypanel Houdini actually loads = main tree (hpath). Parse THAT; record the
# worktree copy's byte parity too.
main_root = sec0["synapse_root_hou"] or "C:/Users/User/SYNAPSE"
main_pypanel = os.path.join(main_root, "houdini", "python_panels", "synapse_panel.pypanel")
wt_pypanel = os.path.join(WT_ROOT, "houdini", "python_panels", "synapse_panel.pypanel")
pypanel_path = main_pypanel if os.path.isfile(main_pypanel) else wt_pypanel
sec3["pypanel_parsed"] = norm(pypanel_path)
sec3["pypanel_main_sha256"] = raw_sha(main_pypanel) if os.path.isfile(main_pypanel) else None
sec3["pypanel_worktree_sha256"] = raw_sha(wt_pypanel) if os.path.isfile(wt_pypanel) else None
sec3["pypanel_bytes_match"] = (sec3["pypanel_main_sha256"] == sec3["pypanel_worktree_sha256"]
                               and sec3["pypanel_main_sha256"] is not None)
p("pypanel parsed        : {}".format(sec3["pypanel_parsed"]))
p("pypanel main==worktree bytes: {}".format(sec3["pypanel_bytes_match"]))

import xml.etree.ElementTree as ET
cdata = None
try:
    tree = ET.parse(pypanel_path)
    for iface in tree.getroot().iter("interface"):
        if iface.get("name") == "synapse_panel":
            scr = iface.find("script")
            if scr is not None and scr.text:
                cdata = scr.text
            break
    sec3["cdata_len"] = len(cdata) if cdata else 0
    p("CDATA script chars    : {}".format(sec3["cdata_len"]))
except Exception as e:
    sec3["cdata_error"] = str(e)
    p("CDATA parse FAILED: {}".format(e))

# Offscreen QApplication (real PySide, the W5-PANEL pattern)
try:
    from PySide6 import QtWidgets
    _qt = "PySide6"
except ImportError:
    from PySide2 import QtWidgets  # noqa
    _qt = "PySide2"
_qapp_cls = getattr(QtWidgets, "QApplication", None)
sec3["qt_binding"] = _qt
sec3["qt_real"] = bool(isinstance(_qapp_cls, type) and "PySide" in getattr(_qapp_cls, "__module__", ""))
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
sec3["qt_platform_runtime"] = app.platformName()
p("Qt binding / platform : {} / {}".format(_qt, sec3["qt_platform_runtime"]))

# capture the id of the Section-2 import so we can prove the flush forces a fresh
# re-import on relaunch.
_before = sys.modules.get("synapse.panel.synapse_panel")
sec3["module_id_before_flush"] = id(_before) if _before is not None else None

if cdata:
    # Plant sentinels BEFORE exec: a synapse.* one that MUST be evicted, and a
    # non-synapse control that MUST survive (proves the flush is scoped, not a nuke).
    sys.modules["synapse.__parity_sentinel__"] = types.ModuleType("synapse.__parity_sentinel__")
    sys.modules.setdefault("synapse", sys.modules.get("synapse") or types.ModuleType("synapse"))
    sys.modules["parity_control_sentinel"] = types.ModuleType("parity_control_sentinel")

    ns = {"__name__": "synapse_panel_pypanel_probe"}
    exec(compile(cdata, "<synapse_panel.pypanel:script>", "exec"), ns)  # flush runs here

    sec3["flush_evicted_synapse_dot"] = "synapse.__parity_sentinel__" not in sys.modules
    sec3["flush_popped_bare_synapse"] = "synapse" not in sys.modules
    sec3["control_sentinel_survived"] = "parity_control_sentinel" in sys.modules
    sec3["onCreateInterface_defined"] = callable(ns.get("onCreateInterface"))
    sec3["createInterface_alias"] = ns.get("createInterface") is ns.get("onCreateInterface")
    p("flush evicted synapse.__parity_sentinel__ : {}".format(sec3["flush_evicted_synapse_dot"]))
    p("flush popped bare 'synapse'               : {}".format(sec3["flush_popped_bare_synapse"]))
    p("control (non-synapse) sentinel survived   : {}".format(sec3["control_sentinel_survived"]))
    p("onCreateInterface defined / aliased       : {} / {}".format(
        sec3["onCreateInterface_defined"], sec3["createInterface_alias"]))

    # Build the widget (this re-imports synapse.panel.synapse_panel fresh from disk).
    p("calling onCreateInterface() ...")
    widget = ns["onCreateInterface"]()
    wcls = type(widget)
    sec3["widget_class"] = wcls.__name__
    sec3["widget_module"] = getattr(wcls, "__module__", None)
    try:
        wfile = norm(inspect.getfile(wcls))
    except Exception as e:
        wfile = None
        sec3["widget_file_error"] = str(e)
    sec3["widget_file"] = wfile
    sec3["widget_from_repo"] = bool(
        wfile and wfile.startswith(REPO_ANCHOR)
        and sec3["widget_module"] == "synapse.panel.synapse_panel"
        and wcls.__name__ == "SynapsePanel")
    _after = sys.modules.get("synapse.panel.synapse_panel")
    sec3["module_id_after_flush"] = id(_after) if _after is not None else None
    sec3["fresh_reimport"] = (sec3["module_id_before_flush"] is not None
                              and sec3["module_id_after_flush"] is not None
                              and sec3["module_id_before_flush"] != sec3["module_id_after_flush"])
    p("widget class / module : {} / {}".format(sec3["widget_class"], sec3["widget_module"]))
    p("widget file           : {}".format(sec3["widget_file"]))
    p("widget from repo file : {}".format(sec3["widget_from_repo"]))
    p("fresh re-import (id changed across flush): {}".format(sec3["fresh_reimport"]))
    if not sec3["widget_from_repo"]:
        # error-fallback path: surface the in-panel traceback verbatim
        try:
            sec3["widget_fallback_text"] = widget.toPlainText()[:1500]
            p("WIDGET FALLBACK TEXT >>>\n" + sec3["widget_fallback_text"])
        except Exception:
            pass
    R["_built_widget"] = widget  # kept in-process for Section 4 live tie-in
else:
    sec3["exec_skipped"] = "no CDATA parsed"

R["sections"]["s3_pypanel"] = {k: v for k, v in sec3.items()}

s3_flush_ok = (sec3.get("flush_evicted_synapse_dot") and sec3.get("flush_popped_bare_synapse")
               and sec3.get("control_sentinel_survived"))
s3_widget_ok = bool(sec3.get("widget_from_repo"))
record_acceptance(
    "pypanel shim exec builds the widget from repo modules offscreen; flush sentinel evicted (synapse.* evicted, non-synapse survives)",
    "pass" if (s3_flush_ok and s3_widget_ok) else ("UNKNOWN" if cdata is None else "FAIL"),
    "flush_evicted={} popped_bare={} control_survived={} widget_from_repo={} class={} fresh_reimport={}".format(
        sec3.get("flush_evicted_synapse_dot"), sec3.get("flush_popped_bare_synapse"),
        sec3.get("control_sentinel_survived"), sec3.get("widget_from_repo"),
        sec3.get("widget_class"), sec3.get("fresh_reimport")),
)


# ══════════════════════════════════════════════════════════════════════════
# Section 4 / Target 4 — behavior pins on the live built widget (master da6d2b33)
# ══════════════════════════════════════════════════════════════════════════
p("")
p("=" * 78)
p("SECTION 4 — BEHAVIOR PINS ON THE LIVE BUILT WIDGET (target 4)")
p("=" * 78)
sec4 = {}

# Re-import the freshly-loaded panel module (post-flush) and its tokens.
spmod = importlib.import_module("synapse.panel.synapse_panel")
tk = importlib.import_module("synapse.panel.designsystem.tokens")
sec4["panel_module_file"] = norm(spmod.__file__)
sec4["tokens_module_file"] = norm(tk.__file__)

# --- (a) R1 double-site wiring: next_font_scale at BOTH sites (commit 4c1134d8)
src = inspect.getsource(spmod)
lines = src.splitlines()
larger_line = None
cycle_line = None
for i, ln in enumerate(lines, 1):
    if 'Larger text' in ln and 'next_font_scale' in ln and larger_line is None:
        larger_line = i
for i, ln in enumerate(lines, 1):
    if ln.strip().startswith("def _cycle_font_scale"):
        # scan the method body for next_font_scale
        for j in range(i, min(i + 8, len(lines))):
            if 'next_font_scale' in lines[j]:
                cycle_line = j + 1
                break
        break
sec4["r1_larger_text_line"] = larger_line
sec4["r1_cycle_font_scale_line"] = cycle_line
sec4["r1_double_site"] = bool(larger_line and cycle_line)
p("R1 'Larger text' next_font_scale @ src line : {}".format(larger_line))
p("R1 _cycle_font_scale next_font_scale @ line  : {}".format(cycle_line))
p("R1 double-site present                       : {}".format(sec4["r1_double_site"]))
record_acceptance(
    "R1 double-site wiring: next_font_scale at BOTH the 'Larger text' action and _cycle_font_scale (commit 4c1134d8)",
    "pass" if sec4["r1_double_site"] else "FAIL",
    "larger_text_line={} cycle_line={}".format(larger_line, cycle_line),
)

# --- (b) font floor: first step from host 1.3 is >= 1.3, and no state drops below
host = 1.3
step = tk.next_font_scale(tk.FONT_SCALE_DEFAULT, host)
ladder = tk.host_floored_steps(host)
# adversarial: repeated application never yields < host, from several starts
below = []
for start in (0.0, 1.0, tk.FONT_SCALE_DEFAULT, 1.3, 1.4, 1.6, 2.0):
    v = start
    for _ in range(8):
        v = tk.next_font_scale(v, host)
        if v < host - 1e-9:
            below.append((start, v))
            break
sec4["next_font_scale_first_step"] = step
sec4["ladder_host_1_3"] = list(ladder)
sec4["font_floor_never_below"] = (len(below) == 0)
sec4["font_floor_ok"] = bool(step >= host - 1e-9 and len(below) == 0)
p("next_font_scale(default, 1.3)   : {}  (>= 1.3: {})".format(step, step >= host - 1e-9))
p("host_floored_steps(1.3)         : {}".format(list(ladder)))
p("never drops below host (7 seeds x8): {}".format(sec4["font_floor_never_below"]))
record_acceptance(
    "tokens.next_font_scale first step from host 1.3 is >= 1.3 (and no reachable state drops below the host floor)",
    "pass" if sec4["font_floor_ok"] else "FAIL",
    "first_step={} ladder={} never_below={}".format(step, list(ladder), sec4["font_floor_never_below"]),
)

# --- (c) chat leading: 12 inserted lines grow document height by ~12px (+/-0.5)
from PySide6 import QtGui  # noqa

def _as_int(x):
    return int(x.value) if hasattr(x, "value") else int(x)

try:
    _LDH = QtGui.QTextBlockFormat.LineHeightType.LineDistanceHeight
    _SINGLE = QtGui.QTextBlockFormat.LineHeightType.SingleHeight
    _DOCSEL = QtGui.QTextCursor.SelectionType.Document
except AttributeError:
    _LDH = QtGui.QTextBlockFormat.LineDistanceHeight
    _SINGLE = QtGui.QTextBlockFormat.SingleHeight
    _DOCSEL = QtGui.QTextCursor.Document
_LDH_INT = _as_int(_LDH)
_SINGLE_INT = _as_int(_SINGLE)

lead = tk.chat_leading_px()

def _doc_height(doc):
    return doc.documentLayout().documentSize().height()

# 12 deterministic single-line blocks in the exact substrate ChatDisplay lays out
# in; measure with SingleHeight (baseline) vs LineDistanceHeight==chat_leading_px.
doc = QtGui.QTextDocument()
f = QtGui.QFont(); f.setPixelSize(tk.SIZE_BODY); doc.setDefaultFont(f)
doc.setTextWidth(600)  # wide: 12 blocks stay 12 laid-out lines, no wrap
cur = QtGui.QTextCursor(doc)
cur.insertText("\n".join("line {}".format(i) for i in range(12)))
doc.documentLayout().documentSize()  # force a layout pass so lineCount() is populated
n_lines = 0
b = doc.firstBlock()
while b.isValid():
    n_lines += max(1, b.layout().lineCount())  # each block is >= 1 laid-out line
    b = b.next()
# baseline
cur.select(_DOCSEL)
flat = QtGui.QTextBlockFormat(); flat.setLineHeight(0, _SINGLE_INT)
cur.mergeBlockFormat(flat)
h0 = _doc_height(doc)
# apply the chat leading
cur.select(_DOCSEL)
bf = QtGui.QTextBlockFormat(); bf.setLineHeight(lead, _LDH_INT)
cur.mergeBlockFormat(bf)
h1 = _doc_height(doc)
delta = h1 - h0
sec4["leading_px_per_line"] = lead
sec4["laid_out_lines"] = n_lines
sec4["doc_h_baseline"] = h0
sec4["doc_h_with_leading"] = h1
sec4["doc_h_delta"] = delta
# brief's specific claim: 12 lines -> +12px +/- 0.5
target_delta = 12.0 * lead
sec4["leading_delta_ok_brief"] = (abs(delta - target_delta) <= 0.5)
# W5-PANEL proven bracket (leading on every line, or only between lines)
sec4["leading_bracket_ok"] = (lead * (n_lines - 1) - 0.5 <= delta <= lead * n_lines + 0.5)
p("chat_leading_px()      : {}".format(lead))
p("laid-out lines         : {}".format(n_lines))
p("doc height baseline/led: {} / {}".format(h0, h1))
p("delta (px)             : {}  (target {:+.1f}px +/-0.5: {})".format(
    delta, target_delta, sec4["leading_delta_ok_brief"]))
record_acceptance(
    "chat leading on 12 inserted lines grows document height by 12px +/- 0.5 (W5-PANEL measured-effective method)",
    "pass" if (sec4["leading_delta_ok_brief"] and sec4["leading_bracket_ok"]) else "FAIL",
    "lines={} delta={} lead={} target={}".format(n_lines, delta, lead, target_delta),
)

# live-widget tie-in: the built SynapsePanel's chat surface carries the same
# leading token — mechanism-on-the-live-widget, not merely in a synthetic doc.
try:
    from synapse.panel.chat_display import ChatDisplay
    built = R.get("_built_widget")
    chat = getattr(built, "_chat", None)
    if chat is not None and type(chat).__name__ == "ChatDisplay":
        d = chat
        sec4["live_chat_source"] = "built SynapsePanel._chat"
    else:
        d = ChatDisplay()
        sec4["live_chat_source"] = "fresh ChatDisplay() (same repo class)"
    d.append_synapse_message("\n".join("word " * 6 for _ in range(12)))
    cdoc = d.document(); cdoc.setTextWidth(200)
    found = False
    bb = cdoc.firstBlock()
    while bb.isValid():
        bfm = bb.blockFormat()
        if _as_int(bfm.lineHeightType()) == _LDH_INT and abs(bfm.lineHeight() - lead) < 1e-6:
            found = True
            break
        bb = bb.next()
    sec4["live_chat_carries_leading"] = found
    sec4["chatdisplay_from_repo"] = norm(inspect.getfile(ChatDisplay)).startswith(REPO_ANCHOR)
    p("live ChatDisplay carries LineDistanceHeight==chat_leading_px : {} (via {})".format(
        found, sec4["live_chat_source"]))
except Exception as e:
    sec4["live_chat_error"] = "".join(traceback.format_exception_only(type(e), e)).strip()
    sec4["live_chat_carries_leading"] = None
    p("live ChatDisplay tie-in UNKNOWN: {}".format(sec4["live_chat_error"]))

R["sections"]["s4_behavior"] = sec4


# ══════════════════════════════════════════════════════════════════════════
# Verdict
# ══════════════════════════════════════════════════════════════════════════
p("")
p("=" * 78)
p("VERDICT")
p("=" * 78)
n_fail = sum(1 for a in R["acceptance"] if a["verdict"] == "FAIL")
n_unknown = sum(1 for a in R["acceptance"] if a["verdict"] == "UNKNOWN")
n_pass = sum(1 for a in R["acceptance"] if a["verdict"] == "pass")
R["summary"] = {"pass": n_pass, "fail": n_fail, "unknown": n_unknown,
                "status": "green" if (n_fail == 0 and n_unknown == 0)
                else ("green_with_findings" if n_fail == 0 else "blocked")}
p("pass={} fail={} unknown={} -> {}".format(n_pass, n_fail, n_unknown, R["summary"]["status"]))

R.pop("_built_widget", None)
with open(RESULTS_PATH, "w", encoding="utf-8") as f:
    json.dump(R, f, indent=2)
p("results.json written: " + norm(RESULTS_PATH))
p("PROBE_COMPLETE")
sys.exit(2 if n_fail else 0)
