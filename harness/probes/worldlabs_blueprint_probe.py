#!/usr/bin/env python3
"""worldlabs_blueprint_probe.py

Replays the BLUEPRINT's own script against the live build and records what every
call does. This is the raw-record producer for
`docs/intake/worldlabs-gaussian-pipeline-audit.md`.

The blueprint is an external .docx. Its section 3 names the file
`synapse_gaussian_pipeline.py`, and that file is transcribed, line for line, into
`harness/probes/worldlabs_blueprint_original.py` next to this one. This probe does
not re-type a single call: it imports the transcription and drives it through a
recording facade over the real `hou`.

Two runs, because they answer different questions:

  STRICT   the facade is the real `hou`: a failed createNode raises, a missing
           parm is None. This is what an artist actually gets, so it shows WHERE
           a real run of the blueprint stops.

  CONTINUE the facade swallows each failure, records it, and returns a ghost so
           the script keeps going. This is what a call-by-call audit needs: it
           reaches every later call, so the table of defects is complete rather
           than truncated at the first raise.

A third measurement reads the source without running it: the blueprint's PROSE
claims a set of mechanisms (coordinate conversion, a VEX AST, graph traversal,
an FFmpeg export, path resolution, a lighting linker). The script would have
to contain the machinery for each claim to be true, so the probe counts the
terms. "The code does not implement this" becomes a count, not a reading.

The render call at the end is recorded as SKIPPED and never executed - a 60-frame
Karma XPU render is not an audit probe's job, and the blueprint never wires its
own output path anyway (F-OPEN-4).

    hython -s -P harness/probes/worldlabs_blueprint_probe.py --out records.json
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import traceback
from pathlib import Path

import hou

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE / "worldlabs_blueprint_original.py"

# The transcription ends with a PROVENANCE comment block. The blueprint's own code
# ends where that block starts, and the line numbers in the audit refer to the
# blueprint's, so both counts are recorded rather than one blended number.
TRAILER_MARK = "# PROVENANCE"


def blueprint_code_lines(src):
    """The number of lines the BLUEPRINT contributes, excluding the provenance trailer."""
    lines = src.split("\n")
    for i, line in enumerate(lines):
        if line.strip() == TRAILER_MARK:
            # the trailer is preceded by a "# ---" rule line
            return i - 1 if i and lines[i - 1].startswith("# ---") else i
    return len(lines)

SKIP = "SKIPPED"
RAISED = "RAISED"
OK = "OK"
MISSING = "MISSING_PARM"
FOUND = "FOUND"


# ---------------------------------------------------------------------------
# line attribution: every recorded call must name the blueprint line it came from
# ---------------------------------------------------------------------------

def caller_line(default=0):
    """The line in the blueprint transcription that is currently executing."""
    f = sys._getframe(1)
    while f is not None:
        if f.f_code.co_filename == str(ORIGINAL):
            return f.f_lineno
        f = f.f_back
    return default


# ---------------------------------------------------------------------------
# recording facade
# ---------------------------------------------------------------------------

class Recorder:
    """Collects one row per blueprint call."""

    def __init__(self) -> None:
        self.calls = []
        self.seq = 0

    def add(self, line, kind, target, outcome, detail="", **extra):
        self.seq += 1
        row = {"seq": self.seq, "line": line, "kind": kind, "target": target,
               "outcome": outcome, "detail": detail}
        row.update(extra)
        self.calls.append(row)
        return row


class GhostParm:
    """Stands in for a parameter that does not exist on the node."""

    def __init__(self, rec, node, name, line, ghost=False):
        self._rec = rec
        self._node = node
        self._name = name
        self._line = line
        self._ghost = ghost

    def set(self, value):
        if self._ghost:
            self._rec.add(self._line, "parm.set", "%s.%s" % (self._node, self._name), SKIP,
                          "the node was never created, so the parm was never reached")
            return self
        self._rec.add(self._line, "parm.set", "%s.%s" % (self._node, self._name), MISSING,
                      "parm does not exist on the node; .set() raises "
                      "AttributeError: 'NoneType' object has no attribute 'set'",
                      value=repr(value))
        return self

    def eval(self):
        return None

    def evalAsString(self):
        return ""


class ParmProxy:
    """A real parameter; its .set() is recorded."""

    def __init__(self, rec, parm, node, line):
        self._rec = rec
        self._parm = parm
        self._node = node
        self._line = line

    def set(self, value):
        try:
            self._parm.set(value)
        except Exception as exc:  # noqa: BLE001
            self._rec.add(self._line, "parm.set", "%s.%s" % (self._node, self._parm.name()),
                          RAISED, "%s: %s" % (type(exc).__name__, exc), value=repr(value))
            return self
        self._rec.add(self._line, "parm.set", "%s.%s" % (self._node, self._parm.name()),
                      OK, "value set", value=repr(value))
        return self

    def eval(self):
        return self._parm.eval()

    def evalAsString(self):
        return self._parm.evalAsString()

    def name(self):
        return self._parm.name()


class NodeProxy:
    """A node in the blueprint's graph. Every call on it is recorded."""

    def __init__(self, rec, node, line, label, ghost=False):
        self._rec = rec
        self._node = node
        self._line = line
        self._label = label
        self._ghost = ghost

    # -- blueprint-facing API ------------------------------------------------
    def createNode(self, type_name, name=None, **kwargs):
        line = caller_line(self._line)
        target = name or type_name
        if self._ghost:
            self._rec.add(line, "createNode", target, SKIP,
                          "the parent node was never created")
            return NodeProxy(self._rec, None, line, target, ghost=True)
        try:
            made = self._node.createNode(type_name, name, **kwargs) if name else \
                self._node.createNode(type_name, **kwargs)
        except Exception as exc:  # noqa: BLE001
            self._rec.add(line, "createNode", target, RAISED,
                          "%s: %s" % (type(exc).__name__, exc), requested_type=type_name)
            return NodeProxy(self._rec, None, line, target, ghost=True)
        self._rec.add(line, "createNode", target, OK,
                      "created %s" % made.type().name(), requested_type=type_name)
        return NodeProxy(self._rec, made, line, target)

    def setParms(self, parms):
        line = caller_line(self._line)
        if self._ghost:
            self._rec.add(line, "setParms", self._label, SKIP,
                          "the node was never created")
            return self
        try:
            self._node.setParms(parms)
        except Exception as exc:  # noqa: BLE001
            self._rec.add(line, "setParms", self._label, RAISED,
                          "%s: %s" % (type(exc).__name__, exc), parms=repr(parms))
            # Attribute the failure to a single key, so a dict with two bad names
            # does not hide the second one behind the first.
            for key, value in parms.items():
                try:
                    self._node.setParms({key: value})
                except Exception as exc2:  # noqa: BLE001
                    self._rec.add(line, "setParms[one]", "%s.%s" % (self._label, key), RAISED,
                                  "%s: %s" % (type(exc2).__name__, exc2),
                                  value=repr(value))
                else:
                    self._rec.add(line, "setParms[one]", "%s.%s" % (self._label, key), OK,
                                  "this key alone is valid", value=repr(value))
            return self
        self._rec.add(line, "setParms", self._label, OK, "parms set", parms=repr(parms))
        return self

    def setInput(self, index, other):
        line = caller_line(self._line)
        other_node = other._node if isinstance(other, NodeProxy) else other
        if self._ghost or other_node is None:
            self._rec.add(line, "setInput", self._label, SKIP,
                          "one side of the connection was never created", index=index)
            return self
        try:
            self._node.setInput(index, other_node)
        except Exception as exc:  # noqa: BLE001
            self._rec.add(line, "setInput", self._label, RAISED,
                          "%s: %s" % (type(exc).__name__, exc), index=index)
            return self
        self._rec.add(line, "setInput", self._label, OK, "input wired", index=index)
        return self

    def parm(self, name):
        line = caller_line(self._line)
        if self._ghost:
            self._rec.add(line, "parm", "%s.%s" % (self._label, name), SKIP,
                          "the node was never created")
            return GhostParm(self._rec, self._label, name, line, ghost=True)
        try:
            p = self._node.parm(name)
        except Exception as exc:  # noqa: BLE001
            self._rec.add(line, "parm", "%s.%s" % (self._label, name), RAISED,
                          "%s: %s" % (type(exc).__name__, exc))
            return GhostParm(self._rec, self._label, name, line)
        if p is None:
            self._rec.add(line, "parm", "%s.%s" % (self._label, name), MISSING,
                          "the node has no parameter with this name")
            return GhostParm(self._rec, self._label, name, line)
        self._rec.add(line, "parm", "%s.%s" % (self._label, name), FOUND, "parm exists")
        return ParmProxy(self._rec, p, self._label, line)

    def render(self, *args, **kwargs):
        line = caller_line(self._line)
        self._rec.add(line, "render", self._label, SKIP,
                      "a 60-frame Karma XPU render is out of scope for an audit probe; "
                      "not executed")
        return None

    def path(self):
        return self._node.path() if self._node is not None else "/<ghost>"

    # -- passthrough ---------------------------------------------------------
    def __getattr__(self, item):
        if self.__dict__.get("_node") is None:
            raise AttributeError(item)
        return getattr(self._node, item)

    def __str__(self):
        return self._label


class HouFacade:
    """Stands in for the `hou` module inside the blueprint's module namespace."""

    def __init__(self, rec):
        self._rec = rec
        self._real = hou

    def node(self, path):
        real = self._real.node(path)
        if real is None:
            raise hou.OperationFailed("path %s not found" % path)
        return NodeProxy(self._rec, real, 0, path)

    def __getattr__(self, item):
        return getattr(self._real, item)


# ---------------------------------------------------------------------------
# runs
# ---------------------------------------------------------------------------

def _module_namespace(src):
    """Compile the transcription without its __main__ guard and return its namespace."""
    tree = ast.parse(src, filename=str(ORIGINAL))
    for node in tree.body:
        if (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                and getattr(node.test.left, "id", "") == "__name__"):
            tree.body.remove(node)
    ns = {"__name__": "worldlabs_blueprint_original", "__file__": str(ORIGINAL)}
    exec(compile(tree, str(ORIGINAL), "exec"), ns)
    return ns


ARGS = ("/project/splats/desert_env.ply", "/project/splats/jungle_rock.ply",
        "/project/colliders/desert_collider.glb", "/project/colliders/jungle_collider.glb",
        "/project/renders/synapse_transition_v1.mp4")


def run_strict(src):
    """Run the blueprint exactly as written and report where it stops."""
    ns = _module_namespace(src)
    ns["hou"] = hou  # the real module: no facade, no forgiveness
    result = {"died": False}
    try:
        ns["run_synapse_pipeline"](*ARGS)
    except Exception as exc:  # noqa: BLE001
        tb = traceback.extract_tb(sys.exc_info()[2])
        last = [f for f in tb if f.filename == str(ORIGINAL)]
        frame = last[-1] if last else tb[-1]
        result = {
            "died": True,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc).strip(),
            "file": os.path.basename(frame.filename),
            "line": frame.lineno,
            "statement": (frame.line or "").strip(),
        }
    return result


def run_continue(src):
    """Run the blueprint call by call, recording every outcome."""
    rec = Recorder()
    ns = _module_namespace(src)
    ns["hou"] = HouFacade(rec)
    fatal = None
    try:
        ns["run_synapse_pipeline"](*ARGS)
    except Exception as exc:  # noqa: BLE001
        tb = traceback.extract_tb(sys.exc_info()[2])
        last = [f for f in tb if f.filename == str(ORIGINAL)]
        frame = last[-1] if last else tb[-1]
        fatal = {"exception_type": type(exc).__name__,
                 "exception_message": str(exc).strip(),
                 "line": frame.lineno, "statement": (frame.line or "").strip()}
    return rec.calls, fatal


def static_findings(src):
    """Things that can be read off the source without running it."""
    tree = ast.parse(src)
    findings = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        used = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        for a in [x.arg for x in fn.args.args]:
            if a not in used:
                findings.append({
                    "kind": "unused_parameter",
                    "function": fn.name,
                    "parameter": a,
                    "detail": "the blueprint accepts %r and never uses it" % a,
                })
    imported = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                imported.add((a.asname or a.name).split(".")[0])
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    used |= {n.value.id for n in ast.walk(tree)
             if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
    for name in sorted(imported - used):
        findings.append({"kind": "unused_import", "name": name,
                         "detail": "imported but never referenced"})
    return findings


# The blueprint's prose claims a set of mechanisms. Each claim names something the
# script would have to contain for the claim to be true. Counting the occurrences
# turns "the code does not implement this" into a measurement instead of a reading.
#
# Terms are matched case-INsensitively but only on WORD boundaries. The boundary is
# the part that matters: a plain substring count would read "ast" inside "last" and
# "bind" inside "binder", and a claim that survives only because of a substring is
# not a claim. One spelling per term keeps the record parseable by tools whose
# JSON readers are case-insensitive.
PROSE_CLAIMS = [
    ("F-OPEN-1", "coordinate-space conversion via UsdGeom.XformOp",
     ["XformOp", "xform", "upaxis", "up_axis", "convert", "UsdGeom"]),
    ("F-OPEN-2", "a pre-compiled VEX AST with a Moneta v5 schema gate",
     ["ast", "parse", "moneta", "schema", "precompile", "pre_compile"]),
    ("F-OPEN-3", "programmatic graph traversal and disconnection",
     ["disconnect", "traverse", "traversal", "walk", "inputs("]),
    ("F-OPEN-4", "a Karma XPU 4D time-sample render and an FFmpeg export",
     ["ffmpeg", "mp4", "video", "timesample", "time_sample", "sequence"]),
    ("F-OPEN-6", "automated absolute path resolution",
     ["os.path", "expanduser", "abspath", "realpath", "resolve", "dirname", "join",
      "environ", "getenv"]),
    ("F-OPEN-7", "an automated lighting relationship-linking pass",
     ["UsdShade", "shade", "collection", "bind", "binding",
      "relationship", "linker"]),
]


def _count_term(src, term):
    """Occurrences of a term on word boundaries, ignoring case."""
    pat = re.escape(term)
    if term and (term[0].isalnum() or term[0] == "_"):
        pat = r"(?<![A-Za-z0-9_])" + pat
    if term and (term[-1].isalnum() or term[-1] == "_"):
        pat = pat + r"(?![A-Za-z0-9_])"
    return len(re.findall(pat, src, re.IGNORECASE))


def prose_claim_scan(src):
    """Count, in the blueprint's own source, the terms each prose claim needs."""
    out = []
    for cid, claim, terms in PROSE_CLAIMS:
        counts = {t: _count_term(src, t) for t in terms}
        out.append({
            "claim_id": cid,
            "claim": claim,
            "term_counts": counts,
            "total_occurrences": sum(counts.values()),
        })
    return out


def node_surfaces():
    """The parm lists the audit's claims rest on, read off the live build."""
    out = {}
    env = hou.node("/obj").createNode("geo", "PROBE_SURFACE")
    stage = hou.node("/stage")
    for key, factory in (
        ("attribwrangle", lambda: env.createNode("attribwrangle", "s_wrangle")),
        ("gltf", lambda: env.createNode("gltf", "s_gltf")),
        ("karmarendersettings", lambda: stage.createNode("karmarendersettings", "s_krs")),
        ("distantlight", lambda: stage.createNode("distantlight", "s_dl")),
        ("usdrender_rop", lambda: stage.createNode("usdrender_rop", "s_rop")),
        ("blast", lambda: env.createNode("blast", "s_blast")),
        ("sopimport", lambda: stage.createNode("sopimport", "s_sopimport")),
        ("labs::normals_from_gsplats::1.0",
         lambda: env.createNode("labs::normals_from_gsplats::1.0", "s_norm")),
    ):
        try:
            n = factory()
            out[key] = {
                "resolved_type": n.type().name(),
                "parms": sorted(p.name() for p in n.parms()),
                "inputs": len(n.inputs()),
            }
        except Exception as exc:  # noqa: BLE001
            out[key] = {"error": "%s: %s" % (type(exc).__name__, exc)}
    resolution = {}
    for type_name in ("labs::bake_gsplat", "labs::normals_from_gsplat",
                      "labs::normals_from_gsplats::1.0", "bakegsplat",
                      "usdrender", "usdrender_rop"):
        entry = {}
        for ctx, parent in (("sop", env), ("lop", stage)):
            try:
                n = parent.createNode(type_name, "s_type")
                entry[ctx] = {"resolved": True, "resolved_type": n.type().name()}
            except Exception as exc:  # noqa: BLE001
                entry[ctx] = {"resolved": False,
                              "error": "%s: %s" % (type(exc).__name__, exc)}
        resolution[type_name] = entry
    out["type_resolution"] = resolution
    return out


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(HERE / "worldlabs_blueprint_records.json"))
    a = ap.parse_args(argv)

    src = ORIGINAL.read_text(encoding="utf-8")
    code_lines = blueprint_code_lines(src)
    print("blueprint transcription: %s (%d blueprint lines, %d file lines)"
          % (ORIGINAL.name, code_lines, src.count("\n")))

    print("\n--- STRICT run: the real thing, no facade ---")
    strict = run_strict(src)
    if strict.get("died"):
        print("  DIED at %s line %s" % (strict["file"], strict["line"]))
        print("  %s: %s" % (strict["exception_type"], strict["exception_message"]))
        print("  statement: %s" % strict["statement"])
    else:
        print("  completed without raising")

    print("\n--- CONTINUE run: every call recorded ---")
    calls, fatal = run_continue(src)
    for row in calls:
        if row["outcome"] not in (OK, FOUND):
            print("  line %3s  %-12s %-38s %s"
                  % (row["line"], row["outcome"], row["target"], row["detail"]))
    print("  %d calls recorded" % len(calls))

    print("\n--- static reading of the source ---")
    static = static_findings(src)
    for f in static:
        print("  %-18s %s" % (f["kind"], f["detail"]))

    print("\n--- prose claims vs the source that would have to implement them ---")
    prose = prose_claim_scan(src)
    for p in prose:
        hits = ", ".join("%s=%d" % (t, c) for t, c in p["term_counts"].items() if c)
        print("  %-10s %-58s %s" % (p["claim_id"], p["claim"][:58],
                                   hits if hits else "NO TERM FOUND"))

    print("\n--- live node surfaces ---")
    surfaces = node_surfaces()
    for key, val in surfaces.items():
        if key == "type_resolution":
            for tname, ctxs in val.items():
                print("  %-32s %s" % (tname, " | ".join(
                    "%s=%s" % (c, ("%s" % v.get("resolved_type")) if v.get("resolved")
                               else v.get("error", "?").splitlines()[0])
                    for c, v in ctxs.items())))
        else:
            print("  %-32s %s" % (key, val.get("resolved_type", val.get("error"))))

    record = {
        "houdini": hou.applicationVersionString(),
        "blueprint_source": ORIGINAL.name,
        "blueprint_lines": code_lines,
        "file_lines": src.count("\n"),
        "strict_run": strict,
        "continue_run": {"calls": calls, "fatal": fatal},
        "static_findings": static,
        "prose_claims": prose,
        "node_surfaces": surfaces,
    }
    out = Path(a.out)
    out.write_text(json.dumps(record, indent=1), encoding="utf-8")
    print("\nwrote %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
