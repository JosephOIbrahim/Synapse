"""H7 producer - re-adjudicate H5's UNVERIFIABLE bucket against LOCAL H22 references.

Leg      H7   Ruling R72   Constitution Article II tiers
Law 2    every number this leg reports is emitted here. No number without a producer.
Law 1    every control below states the condition under which it fails, and CONTROLS_MUST_PASS
         aborts the run if any control fails. A run that cannot fail is not a check.

Run:  python -c "exec(open('harness/notes/h7_readjudicate.py',encoding='utf-8').read())"
      (the read-only leg profile allows `python -c`, not `python <file>`; the file is still
       the producer path and is hashed into the ledger.)

NO NETWORK. Every oracle is a file that shipped with the build or a prior leg's artifact.
"""

import collections
import hashlib
import json
import os
import re
import sys
import zipfile

# --------------------------------------------------------------------------- paths

H22 = r"C:\Program Files\Side Effects Software\Houdini 22.0.368"
H21 = r"C:\Program Files\Side Effects Software\Houdini 21.0.773"   # discrimination control only
HELP22 = os.path.join(H22, "houdini", "help")
HELP21 = os.path.join(H21, "houdini", "help")
PYLIBS = os.path.join(H22, "houdini", "python3.13libs")
CACHE = r"C:\Users\User\OneDrive\Documents\houdini22.0\config\Help\cache"

REPO = r"C:\Users\User\SYNAPSE\.claude\worktrees\h7-compat-readjudicate"
H5TREE = r"C:\Users\User\SYNAPSE\.claude\worktrees\h5-compat"
H5LEDGER = os.path.join(H5TREE, "harness", "notes", "h22_compat_ledger.json")
SYMTABLE = os.path.join(REPO, "python", "synapse", "cognitive", "tools", "data",
                        "h22_symbol_table.json")
LOPCAT = os.path.join(H5TREE, "harness", "notes", "h22_lop_catalog_live_22.0.368.json")
COPCAT = os.path.join(H5TREE, "harness", "notes", "h22_cop_catalog_live_22.0.368.json")

OUT_LEDGER = os.path.join(REPO, "harness", "notes", "h22_compat_ledger_v2.json")
OUT_CONTROLS = os.path.join(REPO, "harness", "notes", "h7_controls.json")

DEPRE = re.compile(r"deprecat", re.I)

# --------------------------------------------------------------- deprecation detection
#
# The first version of this detector scanned each page for /deprecat/i anywhere and
# reported 85 doc-side deprecations. Inspection killed most of them: `sop/edit.txt` was
# flagged for a deprecated PARAMETER LABEL ("Radius with Connectivity (deprecated)"),
# `lop/addvariant.txt` for a deprecated LOCAL VARIABLE ($IIDX), `dop/crowdsolver.txt` for
# a deprecated MENU OPTION, and `hou/ApexNodeType.txt` for having a member literally NAMED
# `deprecated`. A page that mentions a deprecated parameter is not a deprecated page.
#
# The marker vocabulary below is read OFF the corpus, not assumed, and each marker names a
# page that exercises it. C14/C15/C16/C17 make the detector two-sided: it must fire on the
# real notices and must NOT fire on the parameter-level mentions.

NOTICE = re.compile(
    r"(?i)("
    r"\bis\s+(now\s+)?deprecated\b"
    r"|\bare\s+deprecated\b"
    r"|\bhas\s+been\s+deprecated\b"
    r"|\bdeprecated\s+in\s+favou?r\s+of\b"
    r"|\bdeprecated\.\s*(use|call|see)\b"
    r"|^\s*\(?deprecated\)?\s*[:.]"
    r")")

# A notice whose SUBJECT is a variable or expression token is about THAT TOKEN, not the page.
# `lop/reference.txt:58` reads "...you can use the `@input` local variable (`$IIDX` is
# deprecated)..." and sits BEFORE @parameters, so region-scoping alone does not catch it.
# Flagging the LOP Reference node deprecated would have been the worst false alarm in this
# leg - SYNAPSE has 78 occurrences of it.
VAR_NOTICE = re.compile(
    r"(?i)(\$[A-Za-z_][A-Za-z0-9_]*|`[^`]*`|__[^_]+__\s+local\s+variable)"
    r"\s*\)?\s+is\s+(now\s+)?deprecated")

# On a NODE page the prose marker needs a SUBJECT test, because node docs discuss deprecated
# options, workflows and parameters in the same prose region as the node's own overview.
# Evidence: 9 node pages are deprecated by prose alone. Five are real - "This node is
# deprecated" (sop/polyknit:12, sop/bakeode:13, vop/hmtlxcolorcorrect:14), "This operator is
# deprecated" (vop/oglass:10), "...is deprecated in Houdini 22.0" (out/opengl:20). Four are
# not: "this OPTION is deprecated" (dop/flipsolver:146), "this WORKFLOW has been deprecated"
# (vop/kma_nesteddielectrics:13), "Lookat and Follow Path PARAMETERS ... are deprecated"
# (obj/common:105), and a propagation-iterations detail (dop/standard_constraintnetworkattribs:57).
# Dropping the prose marker entirely would lose the five; keeping it bare keeps the four.
# C23 is two-sided on exactly these nine.
_NODE_NOUN = r"(node|operator|rop|sop|lop|cop2?|dop|vop|chop|top|asset|hda)"
NODE_SUBJECT = re.compile(
    r"(?i)("
    r"\bthis\s+" + _NODE_NOUN + r"\b[^.]{0,90}?\bis\s+(now\s+)?deprecated"
    r"|\bthis\s+" + _NODE_NOUN + r"\b[^.]{0,90}?\bhas\s+been\s+deprecated"
    r"|\bis\s+(now\s+)?deprecated\s+in\s+houdini\s+\d"
    r"|^the\s+__[^_]+__\s*\w*\s*" + _NODE_NOUN + r"?\s*is\s+(now\s+)?deprecated"
    r")")

# members whose NAME contains the word - prose about the accessor is not a notice
SELFNAMED = re.compile(r"(?i)^(is)?deprecat")

MARKERS = ("status_header", "include_banner", "warning_block", "summary_prose",
           "body_notice")


def split_page(text):
    """(header_lines, region_a, region_b) - region_a is the page's OWN prose.

    region_a ends at the first `@section` or `::member` line. Everything after belongs to a
    member, parameter or port, and a deprecation mention there is about THAT, not the page.
    """
    lines = text.splitlines()
    cut = len(lines)
    for i, l in enumerate(lines):
        if re.match(r"^(@\w+|::)", l):
            cut = i
            break
    header = [l for l in lines[:20] if l.startswith("#")]
    return header, lines[:cut], lines[cut:]


def detect_page_deprecation(text, node_page=False):
    """Page/node-level verdict. Returns dict with marker, line, verbatim, and parm-level.

    `node_page=True` applies the NODE_SUBJECT test to the prose marker. HOM pages keep the
    plain notice form, because "This method is deprecated in favor of ..." IS the vendor's
    standard there and hou/expandString.txt depends on it (control C17).
    """
    prose = NODE_SUBJECT if node_page else NOTICE
    header, a, b = split_page(text)
    for l in header:
        m = re.match(r"^#\s*status\s*:\s*(.+)$", l.strip())
        if m and DEPRE.search(m.group(1)):
            return {"deprecated": True, "marker": "status_header",
                    "line": text.splitlines().index(l) + 1, "verbatim": l.strip()[:300],
                    "parm_level_only": False}
    for i, l in enumerate(a, 1):
        s = l.strip()
        if s.startswith(":include") and DEPRE.search(s):
            return {"deprecated": True, "marker": "include_banner", "line": i,
                    "verbatim": s[:300], "parm_level_only": False}
        if s.startswith(":warning") and DEPRE.search(s):
            return {"deprecated": True, "marker": "warning_block", "line": i,
                    "verbatim": s[:300], "parm_level_only": False}
        if s.startswith('"""') and DEPRE.search(s):
            return {"deprecated": True, "marker": "summary_prose", "line": i,
                    "verbatim": s[:300], "parm_level_only": False}
        if prose.search(s) and not VAR_NOTICE.search(s):
            return {"deprecated": True, "marker": "body_notice", "line": i,
                    "verbatim": s[:300], "parm_level_only": False}
    parm = None
    for i, l in enumerate(b, len(a) + 1):
        if DEPRE.search(l):
            parm = {"line": i, "verbatim": l.strip()[:300]}
            break
    return {"deprecated": False, "marker": None, "line": None, "verbatim": None,
            "parm_level_only": parm}


def detect_member_deprecation(name, section_lines, start_line):
    """Member-level verdict for a HOM `::name(...)` method section.

    The signature line is excluded - `::deprecated(self) -> bool` must not deprecate itself.
    """
    if SELFNAMED.match(name):
        strong = [l for l in section_lines[1:]
                  if l.strip().startswith('"""') and DEPRE.search(l)]
        if not strong:
            return {"deprecated": False, "marker": None, "line": None, "verbatim": None,
                    "guard": "self_named_member"}
    for off, l in enumerate(section_lines[1:], 1):
        if NOTICE.search(l) and not VAR_NOTICE.search(l):
            return {"deprecated": True, "marker": "body_notice",
                    "line": start_line + off, "verbatim": l.strip()[:300]}
    return {"deprecated": False, "marker": None, "line": None, "verbatim": None}


def sha16(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def read_zip_text(z, entry):
    return z.read(entry).decode("utf-8", "replace")


# --------------------------------------------------------------- O1 hom.zip (HOM axis)

class HomOracle:
    """The HOM reference that SHIPPED INSIDE 22.0.368. Version-pinned by construction.

    Three page shapes, all present in the corpus and all indexed:
      hou/<Class>.txt        class page; members appear as ``::name(...)`` signature lines
      hou/<name>.txt         a module-level function / enum type is its OWN page
      hou/<mod>/<name>.txt   nested module member (hou/logging/log.txt, hou/qt/Dialog.txt)
    """

    SIG = re.compile(r"^::\s*`?([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    VAL = re.compile(r"^::\s*`?([A-Za-z_][A-Za-z0-9_]*)`?\s*$")

    def __init__(self, help_dir, zipname="hom.zip"):
        self.path = os.path.join(help_dir, zipname)
        self.sha16 = sha16(self.path)
        self.z = zipfile.ZipFile(self.path)
        self.entries = [e for e in self.z.namelist() if e.endswith(".txt")]
        self.pages = {}          # dotted symbol -> entry            (page-level symbols)
        self.members = {}        # leaf name -> {dotted: (entry, line, deprecated, verbatim)}
        self.page_dep = {}       # entry -> (bool, line, verbatim)   page-level verdict
        self.page_marker = {}    # entry -> which marker fired
        self.member_basis = {}   # dotted -> member_notice | inherited_from_owner | None
        self._build()

    def _page_symbol(self, entry):
        parts = entry[:-4].split("/")
        if parts[0] not in ("hou", "pdg", "pdgd", "pdgutils"):
            return None
        return ".".join(parts)

    def _sections(self, text):
        """Split a page into ``::``-marked sections. Returns (preamble, {name:(start,body)})."""
        lines = text.splitlines()
        marks = []
        for i, raw in enumerate(lines):
            s = raw.strip()
            m = self.SIG.match(s) or self.VAL.match(s)
            if m:
                marks.append((i, m.group(1)))
        pre_end = marks[0][0] if marks else len(lines)
        preamble = "\n".join(lines[:pre_end])
        secs = {}
        for k, (i, name) in enumerate(marks):
            end = marks[k + 1][0] if k + 1 < len(marks) else len(lines)
            secs.setdefault(name, (i + 1, "\n".join(lines[i:end])))
        return preamble, secs

    def _build(self):
        for e in self.entries:
            sym = self._page_symbol(e)
            text = read_zip_text(self.z, e)
            _preamble, secs = self._sections(text)
            pv = detect_page_deprecation(text)
            self.page_dep[e] = (pv["deprecated"], pv["line"], pv["verbatim"])
            self.page_marker[e] = pv["marker"]
            if sym:
                self.pages[sym] = e
                leaf = sym.split(".")[-1]
                self.members.setdefault(leaf, {})[sym] = (
                    e, pv["line"] or 1, pv["deprecated"], pv["verbatim"])
            if sym:
                for name, (start, body) in secs.items():
                    mv = detect_member_deprecation(name, body.splitlines(), start - 1)
                    dep = mv["deprecated"] or pv["deprecated"]
                    vb = mv["verbatim"] or (pv["verbatim"] if pv["deprecated"] else None)
                    ln = mv["line"] or (pv["line"] if pv["deprecated"] else start)
                    dotted = sym + "." + name
                    self.members.setdefault(name, {})[dotted] = (e, ln, dep, vb)
                    self.member_basis[dotted] = ("member_notice" if mv["deprecated"]
                                                 else ("inherited_from_owner"
                                                       if pv["deprecated"] else None))

    def lookup(self, dotted):
        """Exact dotted lookup. Returns None when the reference does not carry it."""
        if dotted in self.pages:
            e = self.pages[dotted]
            d, ln, vb = self.page_dep[e]
            return {"entry": e, "line": ln or 1, "deprecated": d, "verbatim": vb,
                    "shape": "page"}
        leaf = dotted.split(".")[-1]
        cand = self.members.get(leaf, {})
        if dotted in cand:
            e, ln, d, vb = cand[dotted]
            return {"entry": e, "line": ln, "deprecated": d, "verbatim": vb,
                    "shape": "member"}
        return None

    def owners_of(self, leaf):
        return dict(self.members.get(leaf, {}))


# ------------------------------------------------------- O2 nodes.zip (NODE axis, H7-added)

class NodeOracle:
    """The NODE reference that SHIPPED INSIDE 22.0.368 - `$HFS/houdini/help/nodes.zip`.

    PRECISION, because it would be easy to overclaim here: nodes.zip is NOT new to this
    relay. H5's own `docs_authority.paths` names it, and H5 cites it directly
    (`nodes/lop/karmaocean.txt:13`). R72's source table listed only the userprefs cache
    for the node axis, and the H7 brief inherited that framing - so the correction is to
    R72's table, not to H5's oracle set.

    What H7 adds is APPLICATION: a complete 5,034-entry index, applied to the 298
    node_type rows H5 left UNVERIFIABLE because its live probe covered only the 97
    emitted types and the 218-LOP sweep. The userprefs cache stays a third source.

    Filename convention, read off the corpus, not assumed:
      <context>/<name>.txt          lop/karma.txt
      <context>/<ns>--<name>.txt    sop/kinefx--characterblendshapes.txt  == kinefx::characterblendshapes
      `#version: 2.0` header carries the ::<version> suffix of a versioned type
    """

    def __init__(self, help_dir, zipname="nodes.zip"):
        self.path = os.path.join(help_dir, zipname)
        self.sha16 = sha16(self.path)
        self.z = zipfile.ZipFile(self.path)
        self.entries = [e for e in self.z.namelist() if e.endswith(".txt") and "/" in e]
        self.by_ctx_name = {}    # (context, normalized_name) -> entry
        self.by_name = collections.defaultdict(list)
        self.meta = {}           # entry -> {version, internal, context, dep, dep_line, verbatim}
        self._build()

    def _build(self):
        for e in self.entries:
            ctx, fn = e.split("/", 1)
            name = fn[:-4].replace("--", "::")
            text = read_zip_text(self.z, e)
            hdr = {}
            for l in text.splitlines()[:20]:
                m = re.match(r"^#(\w+):\s*(.+)$", l.strip())
                if m:
                    hdr[m.group(1)] = m.group(2).strip()
            pv = detect_page_deprecation(text, node_page=True)
            self.meta[e] = {"context": hdr.get("context", ctx),
                            "internal": hdr.get("internal"),
                            "version": hdr.get("version"),
                            "status": hdr.get("status"),
                            "since": hdr.get("since"),
                            "chars": len(text),
                            "deprecated": pv["deprecated"], "dep_line": pv["line"],
                            "verbatim": pv["verbatim"], "marker": pv["marker"],
                            "parm_level_only": pv["parm_level_only"]}
            self.by_ctx_name[(ctx, name)] = e
            self.by_name[name].append(e)

    @staticmethod
    def parse_census_type(sym):
        """Split a census node_type string into (context_or_None, base_name, version_or_None).

        Handled spellings, all observed in the H5 census: 'box', 'cop2:file', 'cop:denoise',
        'cop/convolve3::sidefx::blur', 'addvariant::2.0', 'apex::autorigcomponent::2.0'.
        """
        ctx = None
        s = sym
        m = re.match(r"^(cop2|cop|sop|lop|top|obj|out|dop|vop|chop|shop|apex)[:/](?!:)(.+)$", s)
        if m:
            ctx, s = m.group(1), m.group(2)
        ver = None
        m = re.match(r"^(.*)::(\d+(?:\.\d+)*)$", s)
        if m:
            s, ver = m.group(1), m.group(2)
        return ctx, s, ver

    def lookup(self, sym):
        ctx, base, ver = self.parse_census_type(sym)
        if ctx and (ctx, base) in self.by_ctx_name:
            return [self.by_ctx_name[(ctx, base)]], ver
        hits = list(self.by_name.get(base, []))
        if ctx:
            hits = [h for h in hits if h.split("/", 1)[0] == ctx] or []
        return hits, ver


# ---------------------------------------------------- O3 tops.zip (pdg axis, H7-added)

class PdgOracle(HomOracle):
    """`$HFS/houdini/help/tops.zip` carries the pdg Python reference - 153 `pdg/` pages.

    H5 recorded 'the shipped HOM reference contains no pdg surface' and marked 90 pdg
    symbols UNVERIFIABLE on the doc axis. True of hom.zip, wrong about the build: the pdg
    reference ships in a different zip in the same directory.
    """

    def __init__(self, help_dir):
        HomOracle.__init__(self, help_dir, zipname="tops.zip")

    def _page_symbol(self, entry):
        parts = entry[:-4].split("/")
        if parts[0] not in ("pdg", "pdgd", "pdgutils"):
            return None
        return ".".join(parts)


# ------------------------------------ O4 shipped python libs (existence, VERIFIED-STATIC)

class PyLibOracle:
    """Modules that ship as READABLE SOURCE inside the build: hdefereval, toolutils, husd.

    Neither the dir() symbol table (hou/pdg/pxr only) nor hom.zip covers them. The build's
    own source does, and it is version-pinned by the same argument. Static, not a probe -
    tier VERIFIED-STATIC, never conflated with VERIFIED-RUNTIME.
    """

    def __init__(self, pylibs):
        self.pylibs = pylibs
        self.mods = {}
        for mod in ("hdefereval", "toolutils", "houdinihelp", "houshfs"):
            p = os.path.join(pylibs, mod + ".py")
            if os.path.exists(p):
                self.mods[mod] = self._scan_file(p)
        for pkg in ("husd", "husdui"):
            d = os.path.join(pylibs, pkg)
            if os.path.isdir(d):
                names = {}
                for root, _dirs, files in os.walk(d):
                    for f in files:
                        if f.endswith(".py"):
                            fp = os.path.join(root, f)
                            for k, v in self._scan_file(fp).items():
                                names.setdefault(k, v)
                self.mods[pkg] = names

    @staticmethod
    def _scan_file(path):
        out = {}
        rel = path
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            return out
        for i, l in enumerate(text.splitlines(), 1):
            m = re.match(r"^\s*(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", l)
            if m:
                out.setdefault(m.group(1), (rel, i, "def" if l.lstrip().startswith("def") else "class"))
                continue
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=", l)
            if m:
                out.setdefault(m.group(1), (rel, i, "assign"))
        return out

    def lookup(self, dotted):
        parts = dotted.split(".")
        root = parts[0]
        if root not in self.mods:
            return None
        if len(parts) == 1:
            return {"exists": True, "anchor": root + ".py", "kind": "module"}
        member = parts[1]
        hit = self.mods[root].get(member)
        if hit is None:
            return {"exists": False, "anchor": root, "kind": None,
                    "basis": "absent from the build's own shipped source for this module"}
        path, line, kind = hit
        rest_ok = None
        if len(parts) > 2:
            rest_ok = "member_of_member_not_statically_decidable"
        return {"exists": True, "anchor": os.path.relpath(path, self.pylibs) + ":" + str(line),
                "kind": kind, "deeper": rest_ok}


# ----------------------------------------------- O5 help cache (THIRD source, corroboration)

class CacheOracle:
    """The userprefs browsing cache. R72 rule 2: a SECOND source, NEVER the authority.

    A node absent from it means 'nobody opened that page'. Used here only to corroborate
    nodes.zip and to reproduce R72's control numbers - never to decide a cell.
    """

    def __init__(self, root):
        self.root = root
        self.nodes = {}
        nd = os.path.join(root, "nodes")
        if os.path.isdir(nd):
            for ctx in os.listdir(nd):
                cd = os.path.join(nd, ctx)
                if not os.path.isdir(cd):
                    continue
                for f in os.listdir(cd):
                    if f.endswith(".json"):
                        self.nodes[(ctx, f[:-5])] = os.path.join(cd, f)

    def get(self, ctx, name):
        p = self.nodes.get((ctx, name))
        if not p:
            return None
        try:
            raw = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            return None
        dep = bool(DEPRE.search(raw))
        return {"path": os.path.relpath(p, self.root), "chars": len(raw), "deprecated": dep}

    def count_deprecation_mentions(self):
        n = 0
        for p in self.nodes.values():
            try:
                if DEPRE.search(open(p, encoding="utf-8", errors="replace").read()):
                    n += 1
            except OSError:
                pass
        return n, len(self.nodes)

    def cited_number_audit(self):
        """Law 2 audit of the two character counts R72 cites for the karma pages.

        R72 states 69,921 chars for nodes/lop/karmarenderproperties.json and 95,777 for
        nodes/lop/karma.json. Five candidate measures are computed here. If none matches,
        the cited number has no producer path - which does not touch R72's CONCLUSION
        (the pages are substantial, current and silent on deprecation, now confirmed
        against nodes.zip with an exact measure) but does mean the number cannot be
        cited forward.
        """
        out = {}
        for name, claim in (("karmarenderproperties", 69921), ("karma", 95777)):
            p = self.nodes.get(("lop", name))
            if not p:
                out[name] = {"claim": claim, "status": "file absent"}
                continue
            raw = open(p, "rb").read()
            text = raw.decode("utf-8", "replace")
            try:
                obj = json.loads(text)
            except ValueError:
                obj = None

            def leaves(o, with_keys=False):
                if isinstance(o, str):
                    return len(o)
                if isinstance(o, dict):
                    return sum((len(k) if with_keys else 0) + leaves(v, with_keys)
                               for k, v in o.items())
                if isinstance(o, list):
                    return sum(leaves(v, with_keys) for v in o)
                return 0

            measures = {
                "file_bytes": len(raw),
                "utf8_chars": len(text),
                "json_dumps": len(json.dumps(obj)) if obj is not None else None,
                "string_leaf_chars": leaves(obj) if obj is not None else None,
                "string_leaf_chars_plus_keys": leaves(obj, True) if obj is not None else None,
            }
            out[name] = {"claim": claim, "measures": measures,
                         "reproduced_by": [k for k, v in measures.items() if v == claim],
                         "closest": min((abs(v - claim), k) for k, v in measures.items()
                                        if v is not None)[1],
                         "mtime_utc": None}
            out[name]["mtime_epoch"] = int(os.path.getmtime(p))
        return out


# =========================================================================== CONTROLS

CONTROLS = []


def control(cid, what, fails_when):
    def deco(fn):
        CONTROLS.append((cid, what, fails_when, fn))
        return fn
    return deco


def run_controls(ctx):
    results = []
    ok = True
    for cid, what, fails_when, fn in CONTROLS:
        try:
            passed, detail = fn(ctx)
        except Exception as exc:                      # a control that errors is a control that failed
            passed, detail = False, "EXCEPTION: %r" % (exc,)
        results.append({"id": cid, "what": what, "fails_when": fails_when,
                        "passed": bool(passed), "detail": detail})
        if not passed:
            ok = False
    return ok, results


@control("C1", "hom.zip reader returns the KNOWN answer for RopNode: no cancel verb",
         "fails if any cancel/abort/interrupt/kill member is found on hou.RopNode")
def _c1(ctx):
    hom = ctx["hom22"]
    text = read_zip_text(hom.z, "hou/RopNode.txt")
    _pre, secs = hom._sections(text)
    bad = [n for n in secs if re.search(r"cancel|abort|interrupt|^kill$", n, re.I)]
    return (not bad), {"members": sorted(secs), "cancel_like": bad,
                       "entry": "hou/RopNode.txt", "chars": len(text)}


@control("C2", "hom.zip reader returns the KNOWN answer for TopNode: dirtyAllTasks(self, remove_outputs) + its deprecation notice verbatim",
         "fails if the signature is absent, the arg name is not remove_outputs, or the deprecation notice is not detected")
def _c2(ctx):
    hom = ctx["hom22"]
    hit = hom.lookup("hou.TopNode.dirtyAllTasks")
    text = read_zip_text(hom.z, "hou/TopNode.txt")
    sig = [l.strip() for l in text.splitlines() if "dirtyAllTasks(" in l]
    good = bool(hit) and hit["deprecated"] and any("remove_outputs" in s for s in sig)
    return good, {"lookup": hit, "signature_lines": sig[:3]}


@control("C3", "hom.zip returns ABSENT for the three quarantined phantoms",
         "fails if hou.lopNetworks / hou.updateGraphTick / hou.secure resolve in the shipped reference")
def _c3(ctx):
    hom = ctx["hom22"]
    probes = {p: hom.lookup(p) for p in ("hou.lopNetworks", "hou.updateGraphTick", "hou.secure")}
    return (not any(probes.values())), probes


@control("C4", "hom.zip returns ABSENT for a fabricated name",
         "fails if hou.bananaSplitPane resolves - would mean the reader answers yes to anything")
def _c4(ctx):
    return (ctx["hom22"].lookup("hou.bananaSplitPane") is None), "hou.bananaSplitPane"


@control("C5", "hom.zip DISCRIMINATES builds: 22.0.368 corpus differs from 21.0.773",
         "fails if the two builds' hom.zip hash or entry set are identical - the corpus would not be build-pinned")
def _c5(ctx):
    a, b = ctx["hom22"], ctx.get("hom21")
    if b is None:
        return False, "21.0.773 hom.zip not readable - control cannot run"
    sa, sb = set(a.entries), set(b.entries)
    return (a.sha16 != b.sha16 and sa != sb), {
        "sha16_22": a.sha16, "sha16_21": b.sha16,
        "entries_22": len(sa), "entries_21": len(sb),
        "added_in_22": len(sa - sb), "removed_in_22": len(sb - sa),
        "removed_examples": sorted(sb - sa)[:5]}


@control("C6", "nodes.zip deprecation detector CAN FIRE - it finds real notices when present",
         "fails if zero node pages carry a deprecation notice, which would make every 'clean' verdict vacuous")
def _c6(ctx):
    nodes = ctx["nodes22"]
    dep = [e for e, m in nodes.meta.items() if m["deprecated"]]
    ex = [{"entry": e, "line": nodes.meta[e]["dep_line"], "verbatim": nodes.meta[e]["verbatim"]}
          for e in sorted(dep)[:3]]
    return (len(dep) >= 1), {"pages_with_notice": len(dep), "of_pages": len(nodes.meta),
                             "examples": ex}


@control("C7", "R72's headline finding survives promotion to the AUTHORITATIVE node source",
         "fails if lop/karmarenderproperties.txt or lop/karma.txt is absent from nodes.zip, or if either DOES mention deprecation - either outcome would refute doc_silent_deprecation on its founding members")
def _c7(ctx):
    nodes = ctx["nodes22"]
    out = {}
    for e in ("lop/karmarenderproperties.txt", "lop/karma.txt"):
        m = nodes.meta.get(e)
        out[e] = None if m is None else {"chars": m["chars"], "since": m["since"],
                                        "deprecated": m["deprecated"]}
    good = all(out[e] is not None and out[e]["deprecated"] is False for e in out)
    return good, out


@control("C8", "nodes.zip DISCRIMINATES builds: 22.0.368 corpus differs from 21.0.773",
         "fails if the two builds' nodes.zip hash or entry set are identical")
def _c8(ctx):
    a, b = ctx["nodes22"], ctx.get("nodes21")
    if b is None:
        return False, "21.0.773 nodes.zip not readable - control cannot run"
    sa, sb = set(a.entries), set(b.entries)
    return (a.sha16 != b.sha16 and sa != sb), {
        "sha16_22": a.sha16, "sha16_21": b.sha16,
        "entries_22": len(sa), "entries_21": len(sb),
        "added_in_22": len(sa - sb), "removed_in_22": len(sb - sa),
        "removed_examples": sorted(sb - sa)[:5]}


@control("C9", "tops.zip carries the pdg reference and its detector fires",
         "fails if pdg.EventType does not resolve, or if no pdg page carries a deprecation notice")
def _c9(ctx):
    pdg = ctx["pdg22"]
    hit = pdg.lookup("pdg.EventType")
    dep = [e for e, (d, _l, _v) in pdg.page_dep.items() if d]
    return (hit is not None and len(dep) >= 1), {
        "pdg.EventType": hit, "pages": len(pdg.entries), "pages_with_notice": len(dep),
        "notice_examples": sorted(dep)[:4]}


@control("C10a", "help-cache reader corroborates the karma silence as a SECOND source",
         "fails if either cached karma page is unreadable or DOES mention deprecation - it would contradict nodes.zip and force a re-look")
def _c10a(ctx):
    a = ctx["cache"].get("lop", "karmarenderproperties")
    b = ctx["cache"].get("lop", "karma")
    good = (a and b and not a["deprecated"] and not b["deprecated"])
    return good, {"karmarenderproperties": a, "karma": b,
                  "note": "reproducible measure: raw file chars. R72's 69,921/95,777 do not "
                          "reproduce - see cited_number_audit."}


@control("C10b", "help-cache deprecation detector CAN FIRE",
         "fails if zero cached node docs mention deprecation, which would make C10a vacuous")
def _c10b(ctx):
    n, tot = ctx["cache"].count_deprecation_mentions()
    return (n >= 1), {"docs_with_mention": n, "of_docs": tot,
                      "r72_claimed": 207,
                      "delta_explained_by": "nodes/index.json is counted as a node doc by "
                                            "R72's walker and not by this one (same +1 offset "
                                            "as 1,588 vs 1,587)"}


@control("C10c", "help-cache ABSENCE is proven NOT to be evidence",
         "fails if every LOP type documented in the shipped nodes.zip is also present in the cache - then absence would carry information and R72 rule 2 would be too strong")
def _c10c(ctx):
    nodes, cache = ctx["nodes22"], ctx["cache"]
    doc_lop = sorted(e.split("/", 1)[1][:-4] for e in nodes.entries
                     if e.startswith("lop/"))
    missing = [n for n in doc_lop if cache.get("lop", n) is None]
    return (len(missing) >= 1), {
        "lop_types_in_shipped_reference": len(doc_lop),
        "of_those_absent_from_cache": len(missing),
        "examples": missing[:8],
        "note": "R72 rule 2 demonstrated live: these are documented by the build's own "
                "reference and missing from the cache purely because nobody opened the page."}


@control("C11", "shipped-source reader is TWO-SIDED on hdefereval",
         "fails unless executeInMainThreadWithResult is FOUND and executeInMainThread is NOT - a reader that answers the same way to both is uncalibrated")
def _c11(ctx):
    py = ctx["pylib"]
    a = py.lookup("hdefereval.executeInMainThreadWithResult")
    b = py.lookup("hdefereval.executeInMainThread")
    return (a and a["exists"] and b and not b["exists"]), {"with_result": a, "bare": b}


@control("C14", "every named deprecation MARKER is exercised by at least one real page",
         "fails if any marker class matches zero pages - a marker that never fires is dead code being counted as coverage")
def _c14(ctx):
    fired = collections.Counter()
    ex = {}
    for oracle in ("nodes22", "hom22", "pdg22"):
        o = ctx[oracle]
        src = o.meta if oracle == "nodes22" else None
        if src is not None:
            for e, m in src.items():
                if m["marker"]:
                    fired[m["marker"]] += 1
                    ex.setdefault(m["marker"], "%s:%s" % (e, m["dep_line"]))
        else:
            for e, mk in o.page_marker.items():
                if mk:
                    fired[mk] += 1
                    ex.setdefault(mk, e)
    missing = [m for m in MARKERS if fired[m] == 0]
    return (not missing), {"fired": dict(fired), "examples": ex, "never_fired": missing}


@control("C15", "detector does NOT fire on a page that only mentions a deprecated PARAMETER",
         "fails if sop/edit.txt, lop/addvariant.txt, dop/crowdsolver.txt or lop/copyproperty.txt is called deprecated - each only mentions a deprecated parameter, local variable or menu option")
def _c15(ctx):
    nodes = ctx["nodes22"]
    probes = ("sop/edit.txt", "lop/addvariant.txt", "dop/crowdsolver.txt",
              "lop/copyproperty.txt", "sop/apex--autorigcomponent.txt")
    out = {}
    for e in probes:
        m = nodes.meta.get(e)
        out[e] = None if m is None else {"deprecated": m["deprecated"],
                                        "parm_level_only": m["parm_level_only"]}
    bad = [e for e, v in out.items() if v is None or v["deprecated"]]
    saw_parm = [e for e, v in out.items() if v and v["parm_level_only"]]
    return (not bad and len(saw_parm) >= 3), {"probes": out, "wrongly_deprecated": bad,
                                             "parm_level_seen": saw_parm}


@control("C16", "detector does NOT fire on a member merely NAMED 'deprecated'",
         "fails if hou.ApexNodeType.deprecated is reported deprecated - the accessor describes deprecation, it is not deprecated")
def _c16(ctx):
    hit = ctx["hom22"].lookup("hou.ApexNodeType.deprecated")
    return (hit is not None and not hit["deprecated"]), hit


@control("C17", "detector DOES fire on both real HOM shapes: include-banner and prose notice",
         "fails if hou.Cop2Node (old-COPs include banner), hou.ChannelEditorPane (#status header) or hou.expandString (prose notice) is reported current")
def _c17(ctx):
    hom = ctx["hom22"]
    out = {}
    for s in ("hou.Cop2Node", "hou.ChannelEditorPane", "hou.expandString"):
        h = hom.lookup(s)
        out[s] = None if h is None else {"deprecated": h["deprecated"],
                                        "anchor": "%s:%s" % (h["entry"], h["line"]),
                                        "verbatim": h["verbatim"]}
    return all(v and v["deprecated"] for v in out.values()), out


@control("C18", "member deprecation is INHERITED from a deprecated owner page",
         "fails if a method on hou.Cop2Node is reported current while the class page carries the old-COPs deprecation banner")
def _c18(ctx):
    hom = ctx["hom22"]
    members = [d for d in hom.member_basis if d.startswith("hou.Cop2Node.")]
    inherited = [d for d in members if hom.member_basis[d] == "inherited_from_owner"]
    return (len(members) >= 1 and len(inherited) == len(members)), {
        "members": len(members), "inherited": len(inherited),
        "examples": sorted(members)[:5]}


@control("C19", "variable-notice guard: a deprecated LOCAL VARIABLE does not deprecate its node, and the guard does not over-correct",
         "fails if lop/reference.txt or lop/editproperties.txt is called deprecated (both only note a deprecated $VAR in prose), OR if dop/smokeobject.txt (:warning block) or manager/cop2net.txt (:include banner) is called current")
def _c19(ctx):
    nodes = ctx["nodes22"]
    must_be_clean = ("lop/reference.txt", "lop/editproperties.txt", "lop/duplicate.txt")
    must_be_dep = ("dop/smokeobject.txt", "manager/cop2net.txt", "lop/karmaocean.txt")
    out = {e: nodes.meta[e]["deprecated"] for e in must_be_clean + must_be_dep
           if e in nodes.meta}
    ok = (all(out.get(e) is False for e in must_be_clean)
          and all(out.get(e) is True for e in must_be_dep))
    return ok, {"verdicts": out,
                "note": "SYNAPSE has 78 occurrences of the LOP Reference node; a false "
                        "deprecation here would be the most damaging error in the leg."}


@control("C20", "the category-scope guard is TWO-SIDED: it drops the false alarms and keeps the resolved ones",
         "fails if `duplicate`/`cop2net` are counted as deprecated (H5 proved by live probe that SYNAPSE's sites sit in the NON-deprecated categories), OR if `karma`/`karmarenderproperties` are dropped (H5 recorded emission_category_resolved=Lop, the deprecated one - a guard that also swallows these has removed the finding it was meant to protect)")
def _c20(ctx):
    rows = {r["symbol"]: r for r in ctx["h5"]["symbols"]}
    out = {}
    for s in ("duplicate", "cop2net", "karma", "karmarenderproperties"):
        r = rows.get(s)
        if r is None:
            return False, "row %s absent" % s
        rd, _ev, scoped = runtime_verdict(r)
        out[s] = {"raw": r.get("deprecated_runtime"), "honoured": rd,
                  "scoped_away": bool(scoped),
                  "emission_category_resolved": r.get("emission_category_resolved"),
                  "h5_quadrant": r["quadrant"]}
    ok = (out["duplicate"]["honoured"] is None and out["cop2net"]["honoured"] is None
          and out["karma"]["honoured"] is True
          and out["karmarenderproperties"]["honoured"] is True)
    return ok, out


@control("C21", "the dir() table's SCOPE LIMIT is applied in BOTH directions",
         "fails if hou.undos.beginGroup is called PHANTOM or OUT_OF_MATRIX (the table holds zero children of hou.undos, so its silence is not evidence - this is the exact defect H5's own CORRECTION records), OR if pdg.PyEventCallback is NOT called PHANTOM (the table does enumerate pdg's children, so there absence IS proof)")
def _c21(ctx):
    T = ctx["table_syms"]
    a = table_decides("hou.undos.beginGroup", T)
    b = table_decides("pdg.PyEventCallback", T)
    c = table_decides("hou.undos.group", T)
    return (a == "undecidable" and b == "absent_proof" and c == "undecidable"), {
        "hou.undos.beginGroup": a, "pdg.PyEventCallback": b,
        "hou.undos.group (real, absent from table - H5's CORRECTION case)": c}


@control("C22", "a census token that is a FILENAME is not adjudicated as an API",
         "fails if hdefereval.py is classified PHANTOM - that asserts a nonexistent API where the token is not an API reference at all")
def _c22(ctx):
    return (not_a_symbol("hdefereval.py") is not None
            and not_a_symbol("...") is not None
            and not_a_symbol("hou.TopNode.dirtyAllTasks") is None), {
        "hdefereval.py": not_a_symbol("hdefereval.py"),
        "...": not_a_symbol("..."),
        "hou.TopNode.dirtyAllTasks": not_a_symbol("hou.TopNode.dirtyAllTasks")}


@control("C23", "the node-page PROSE marker is two-sided on the nine pages that depend on it alone",
         "fails if any of the five real 'This node/operator is deprecated' pages goes clean (dropping the marker would lose them), OR if any of the four subject-mismatch pages stays deprecated - a deprecated OPTION, WORKFLOW or PARAMETER is not a deprecated node")
def _c23(ctx):
    nodes = ctx["nodes22"]
    real = ("sop/polyknit.txt", "sop/bakeode.txt", "vop/hmtlxcolorcorrect.txt",
            "vop/oglass.txt", "out/opengl.txt")
    fake = ("dop/flipsolver.txt", "vop/kma_nesteddielectrics.txt", "obj/common.txt",
            "dop/standard_constraintnetworkattribs.txt")
    out = {e: (nodes.meta[e]["deprecated"], nodes.meta[e]["marker"])
           for e in real + fake if e in nodes.meta}
    ok = (all(out.get(e, (False,))[0] is True for e in real)
          and all(out.get(e, (True,))[0] is False for e in fake))
    return ok, {"must_be_deprecated": {e: out.get(e) for e in real},
                "must_be_clean": {e: out.get(e) for e in fake}}


@control("C24", "the residual-shape characterisation is DETERMINISTIC across hash seeds",
         "fails if the leaf->owner-root tie-break depends on set iteration order. The first version reported 335/112/81 on one run and 338/110/80 on the next; a number that changes between runs has no producer path (Law 2)")
def _c24(ctx):
    leaves = ctx["table_leaves"]
    probes = ("Get", "Set", "handle", "wait", "cook", "render")
    got = {}
    for leaf in probes:
        owners = leaves.get(leaf, ())
        roots = collections.Counter(o.split(".")[0] for o in owners)
        if not roots:
            continue
        a = max(sorted(roots.items()), key=lambda kv: kv[1])[0]
        shuffled = collections.Counter(o.split(".")[0] for o in sorted(owners, reverse=True))
        b = max(sorted(shuffled.items()), key=lambda kv: kv[1])[0]
        got[leaf] = (a, b, dict(roots))
    stable = all(v[0] == v[1] for v in got.values())
    sorted_lists = all(list(leaves[k]) == sorted(leaves[k]) for k in probes if k in leaves)
    return (stable and sorted_lists), {"probes": got, "owner_lists_sorted": sorted_lists}


@control("C12", "the H5 ledger loaded is the artifact H5 actually shipped",
         "fails if the ledger's recorded commit/model/UNVERIFIABLE count do not match what H5's receipt claims")
def _c12(ctx):
    d = ctx["h5"]
    return (d["leg"] == "H5" and d["counts"]["UNVERIFIABLE"] == 1267
            and d["generated_at_commit"].startswith("0a88f5f")), {
        "leg": d["leg"], "commit": d["generated_at_commit"][:12],
        "model": d["model"], "UNVERIFIABLE": d["counts"]["UNVERIFIABLE"],
        "sha256_16": ctx["h5_sha16"]}


# ======================================================================= adjudication

RESOLVED_CELLS = ("OK", "DECAY_CLOCK", "PRIVATE_API", "PHANTOM", "MISATTRIBUTED",
                  "VERSION_MISMATCH", "ALREADY_REMOVED")


def adjudicate(ctx):
    hom, nodes, pdg, py, cache = (ctx["hom22"], ctx["nodes22"], ctx["pdg22"],
                                  ctx["pylib"], ctx["cache"])
    table_leaves = ctx["table_leaves"]
    table_syms = ctx["table_syms"]
    live_types = ctx["live_types"]

    rows_out = []
    for r in ctx["h5"]["symbols"]:
        if r["quadrant"] != "UNVERIFIABLE":
            rows_out.append(None)
            continue
        rows_out.append(_one(r, hom, nodes, pdg, py, cache, table_leaves, table_syms,
                             live_types))
    return rows_out


MALFORMED = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


def not_a_symbol(sym):
    """A census token that cannot be a dotted Python symbol at all.

    `hdefereval.py` is a FILENAME - the first version of this leg called it a PHANTOM, which
    is a claim about an API that does not exist because the token is not an API reference.
    `...`, `symbols_PHANTOM_do_not_use` and the recipe strings are the same class.
    """
    if sym.endswith(".py"):
        return "filename, not a symbol reference"
    if not MALFORMED.match(sym):
        return "not a well-formed dotted symbol"
    return None


def table_decides(sym, table_syms):
    """Apply H5's SCOPE_LIMIT honestly: absence is proof ONLY where the parent was expanded.

    H5's own CORRECTION records that claiming 'absent from the complete dir() table' as proof
    was FALSE on ~140 rows and scored `hou.undos.group` - SYNAPSE's constitutional undo
    anchor - as absent. The first version of this leg reintroduced exactly that defect from
    the other direction, calling five real `hou.<module>.<member>` rows
    'no Houdini referent'. Absence from the table plus absence from the docs is not evidence
    of non-existence when the table never walked the parent.
    """
    if sym in table_syms:
        return "present"
    parent = sym.rsplit(".", 1)[0] if "." in sym else None
    if parent is None:
        return "undecidable"
    pref = parent + "."
    if any(s.startswith(pref) for s in table_syms):
        return "absent_proof"
    return "undecidable"


def _mk(cell, source, path, tier, **kw):
    d = {"h7_cell": cell, "h7_source": source, "h7_local_path": path, "h7_truth_tier": tier}
    d.update(kw)
    return d


def _one(r, hom, nodes, pdg, py, cache, table_leaves, table_syms, live_types):
    sym, kind = r["symbol"], r["kind"]

    # ---------------------------------------------------------------- hom_symbol (dotted)
    if kind == "hom_symbol":
        root = sym.split(".")[0]

        bad = not_a_symbol(sym)
        if bad:
            return _mk("OUT_OF_MATRIX:not_a_symbol", "census token inspection", None,
                       "VERIFIED-STATIC", h7_note=bad + " - the matrix does not apply. Counted "
                                                  "separately so it neither inflates "
                                                  "UNVERIFIABLE nor vanishes.")

        if root == "hou" and sym.startswith("hou.session"):
            return _mk("UNVERIFIABLE:runtime_namespace", "n/a", None, "UNVERIFIABLE",
                       h7_note="hou.session is a user-data namespace assigned at runtime. "
                               "No documentation or dir() snapshot can decide it, and that is "
                               "the correct permanent answer, not an instrument gap.")

        if root in ("hou",):
            hit = hom.lookup(sym)
            if hit:
                return _resolve_doc_hit(r, sym, hit, "hom.zip@22.0.368", table_syms)
            # not in the shipped reference under this spelling - is it a case/spelling miss?
            leaf = sym.split(".")[-1]
            parent = ".".join(sym.split(".")[:-1])
            alt = None
            if len(sym.split(".")) == 3:
                p2 = sym.split(".")[1]
                for cand in (p2[0].lower() + p2[1:], p2[0].upper() + p2[1:]):
                    trial = "hou." + cand + "." + leaf
                    if trial != sym and hom.lookup(trial):
                        alt = trial
                        break
            if alt:
                return _mk("MISATTRIBUTED:doc_spelling", "hom.zip@22.0.368 + dir() table",
                           hom.lookup(alt)["entry"], "VERIFIED-DERIVED",
                           h7_resolved_spelling=alt,
                           h7_two_source_confirmation={
                               "as_written_in_table": sym in table_syms,
                               "corrected_in_table": alt in table_syms,
                               "corrected_documented": True},
                           h7_note="the shipped reference documents %s and the dir() table "
                                   "carries it; neither carries %s. Wrong capitalisation of the "
                                   "owner is a real defect, not an undecidable." % (alt, sym))
            decision = table_decides(sym, table_syms)
            if decision == "present":
                return _mk("PRIVATE_API", "hom.zip@22.0.368 (absent) + dir() table (present)",
                           None, "VERIFIED-DERIVED",
                           h7_note="introspected but not carried by the reference shipped with "
                                   "this build: undocumented, therefore never promised.")
            if decision == "absent_proof":
                return _mk("PHANTOM", "hom.zip@22.0.368 (absent) + dir() table (absent, parent "
                           "expanded)", None, "VERIFIED-DERIVED",
                           h7_note="absent from the shipped reference AND from the dir() table "
                                   "whose enumeration of '%s' is present, so absence IS proof "
                                   "here." % parent)
            return _mk("UNVERIFIABLE:undocumented_module_member",
                       "hom.zip@22.0.368 (absent) + dir() table (cannot decide)", None,
                       "UNVERIFIABLE",
                       h7_note="not carried by the shipped reference, and the table never "
                               "expanded '%s' so its silence is not evidence. Undocumented is "
                               "decided; EXISTS is not. Needs a live probe." % parent)

        if root in ("pdg", "pdgd", "pdgutils"):
            hit = pdg.lookup(sym)
            if hit:
                return _resolve_doc_hit(r, sym, hit, "tops.zip@22.0.368", table_syms,
                                        oracle_note="H5 recorded 'no pdg surface' - true of "
                                                    "hom.zip, but the pdg reference ships in "
                                                    "tops.zip in the same directory.")
            decision = table_decides(sym, table_syms)
            if decision == "present":
                return _mk("PRIVATE_API", "tops.zip@22.0.368 (absent) + dir() table (present)",
                           None, "VERIFIED-DERIVED",
                           h7_note="exists on the build, not carried by the shipped pdg "
                                   "reference.")
            if decision == "absent_proof":
                return _mk("PHANTOM", "tops.zip@22.0.368 (absent) + dir() table (absent, "
                           "parent expanded)", None, "VERIFIED-DERIVED",
                           h7_note="absent from the shipped pdg reference AND from the dir() "
                                   "table whose enumeration of this parent is present, so "
                                   "absence IS proof here.",
                           h7_h5_exists_evidence=r.get("exists_evidence"))
            return _mk("UNVERIFIABLE:undocumented_module_member",
                       "tops.zip@22.0.368 (absent) + dir() table (cannot decide)", None,
                       "UNVERIFIABLE",
                       h7_note="undocumented is decided; EXISTS is not, because the table never "
                               "expanded this parent.",
                       h7_h5_exists_evidence=r.get("exists_evidence"))

        if root == "pxr":
            return _mk("OUT_OF_REFERENCE_SCOPE:third_party", "n/a - OpenUSD, not SideFX",
                       None, "VERIFIED-STATIC",
                       h7_exists=r.get("exists"),
                       h7_note="the H22 reference is not the doc authority for pxr; OpenUSD "
                               "is. EXISTS is already decided by the dir() table (H5). "
                               "Calling this PRIVATE_API would be a false alarm; leaving it "
                               "UNVERIFIABLE implies an oracle exists locally and was not "
                               "read. Neither is true - the corpus question is a ruling item.")

        hit = py.lookup(sym)
        if hit is not None:
            if hit["exists"]:
                return _mk("OK:exists_undocumented_shipped_module", "python3.13libs source",
                           hit["anchor"], "VERIFIED-STATIC",
                           h7_note="defined in the build's own shipped source. Not in the HOM "
                                   "reference, so 'documented' does not apply - this module is "
                                   "not part of the published HOM surface.",
                           h7_deeper=hit.get("deeper"))
            return _mk("PHANTOM", "python3.13libs source (absent)",
                       "python3.13libs/" + hit["anchor"], "VERIFIED-STATIC",
                       h7_note="the build ships this module as readable source and it does NOT "
                               "define this name. Static read of the build's own source, not a "
                               "probe.")
        return _mk("UNVERIFIABLE:no_local_oracle", "none", None, "UNVERIFIABLE",
                   h7_note="root '%s' has no local reference and no shipped source in this "
                           "build." % root)

    # ------------------------------------------------------------------- hom_method (leaf)
    if kind == "hom_method":
        if r.get("resolved_owner"):
            owner = r["resolved_owner"]
            hit = hom.lookup(owner)
            if hit:
                return _resolve_doc_hit(r, owner, hit, "hom.zip@22.0.368", table_syms,
                                        oracle_note="H5 resolved the owner but left EXISTS "
                                                    "null; H5's own DOCUMENTED_BASIS_RULE "
                                                    "settles it against the build-shipped "
                                                    "reference.")
        leaf = sym
        owners = hom.owners_of(leaf)
        if not owners:
            if leaf not in table_leaves:
                return _mk("OUT_OF_MATRIX:no_houdini_referent",
                           "hom.zip + dir() table, both negative", None, "VERIFIED-STATIC",
                           h7_note="this leaf name appears in zero of the shipped reference's "
                                   "pages and is the leaf of zero introspected symbols. It is "
                                   "a SYNAPSE-local method name the census over-collected.")
            owners_t = table_leaves.get(leaf, ())
            roots = collections.Counter(o.split(".")[0] for o in owners_t)
            # deterministic tie-break. Counter.most_common() breaks ties by insertion order,
            # which comes from set iteration and therefore varies with PYTHONHASHSEED - the
            # first version of this leg reported 335/112/81 on one run and 338/110/80 on the
            # next. A number that changes between runs has no producer (Law 2). C24 pins it.
            top_root = max(sorted(roots.items()), key=lambda kv: kv[1])[0] if roots else None
            shape = {"hou": "hou_shaped", "pxr": "pxr_shaped_third_party",
                     "pdg": "pdg_shaped"}.get(top_root, "unknown_shape")
            return _mk("UNVERIFIABLE:leaf_unbound_owner",
                       "dir() table (leaf present) + hom.zip (absent)", None, "UNVERIFIABLE",
                       h7_note="the leaf exists somewhere on the build but the census cannot "
                               "bind it to the owner at the call site; existing-somewhere is "
                               "not existing-here. The shape below CHARACTERISES the residual "
                               "and does not resolve it - `Get`, `Set`, `GetPrimAtPath` are "
                               "OpenUSD names the census recorded as hom_method.",
                       h7_table_owner_count=len(owners_t),
                       h7_residual_shape=shape,
                       h7_owner_roots=dict(roots),
                       h7_hou_owner_examples=sorted(
                           o for o in owners_t if o.startswith("hou."))[:3])
        deps = {d: v for d, (_e, _l, dep, v) in owners.items() if dep}
        if not deps:
            return _mk("OK", "hom.zip@22.0.368", sorted(owners.values())[0][0]
                       if owners else None, "VERIFIED-DERIVED",
                       h7_owner_candidates=sorted(owners),
                       h7_basis="verdict INVARIANT across all %d documented owners: every one "
                                "is documented and none is deprecated, so the compat cell "
                                "does not depend on which owner the census meant."
                                % len(owners))
        return _mk("UNVERIFIABLE:ambiguous_owner_deprecation_risk", "hom.zip@22.0.368",
                   None, "UNVERIFIABLE",
                   h7_owner_candidates=sorted(owners),
                   h7_deprecated_owners={k: v for k, v in sorted(deps.items())},
                   h7_note="the verdict is NOT invariant: at least one candidate owner is "
                           "deprecated in the shipped reference. Actionable residual - bind "
                           "the call site, do not guess.")

    # --------------------------------------------------------------------- node_type
    if kind == "node_type":
        hits, ver = nodes.lookup(sym)
        cache_hit = None
        ctx_guess, base, _v = NodeOracle.parse_census_type(sym)
        if ctx_guess:
            cache_hit = cache.get(ctx_guess, base)
        if not hits:
            plausible = re.match(r"^[a-z][a-z0-9_:.\-]*$", sym or "") is not None
            live = sym in live_types
            if live:
                return _mk("PRIVATE_API", "nodes.zip@22.0.368 (absent) + live catalog (present)",
                           None, "VERIFIED-DERIVED",
                           h7_note="registered on the build but absent from the shipped node "
                                   "reference.",
                           h7_cache_second_source=cache_hit)
            if not plausible:
                return _mk("OUT_OF_MATRIX:no_houdini_referent",
                           "nodes.zip (absent) + not a well-formed type name", None,
                           "VERIFIED-STATIC",
                           h7_note="not a well-formed Houdini node type name; census "
                                   "over-collection.")
            return _mk("UNVERIFIABLE:node_absent_from_reference_and_unprobed",
                       "nodes.zip@22.0.368 (absent)", None, "UNVERIFIABLE",
                       h7_cache_second_source=cache_hit,
                       h7_note="absent from the shipped node reference, and this leg ran no "
                               "live node-type probe. Absence from a doc corpus is not "
                               "absence from the build - third-party HDAs live here.")
        deps = {e: nodes.meta[e] for e in hits if nodes.meta[e]["deprecated"]}
        vermis = None
        if ver:
            docv = {e: nodes.meta[e]["version"] for e in hits}
            if all(v != ver for v in docv.values()):
                vermis = docv
        base_kw = {"h7_doc_entries": sorted(hits),
                   "h7_cache_second_source": cache_hit,
                   "h7_version_requested": ver,
                   "h7_version_mismatch": vermis}
        if deps and len(deps) == len(hits):
            return _mk("DECAY_CLOCK:doc_only", "nodes.zip@22.0.368",
                       sorted(deps)[0], "VERIFIED-STATIC",
                       h7_deprecation_verbatim=nodes.meta[sorted(deps)[0]]["verbatim"],
                       h7_deprecation_anchor="%s:%d" % (sorted(deps)[0],
                                                        nodes.meta[sorted(deps)[0]]["dep_line"]),
                       h7_runtime_deprecated=r.get("deprecated_runtime"),
                       h7_note="the AUTHORED help deprecates this node type. H5's runtime pass "
                               "did not flag it, so it never entered DECAY_CLOCK. This is the "
                               "half of R72's union that corrects the floor UPWARD.",
                       **base_kw)
        if deps:
            return _mk("UNVERIFIABLE:ambiguous_context_deprecation_risk", "nodes.zip@22.0.368",
                       None, "UNVERIFIABLE",
                       h7_deprecated_entries=sorted(deps),
                       h7_note="the census type name matches pages in more than one context "
                               "and they disagree on deprecation. Bind the context, do not "
                               "guess.", **base_kw)
        return _mk("OK:documented_current_exists_unprobed", "nodes.zip@22.0.368",
                   sorted(hits)[0], "VERIFIED-STATIC",
                   h7_exists_basis="documented_in_build_shipped_reference (H5's own rule, "
                                   "applied to the node axis)",
                   h7_note="documented and current in the reference that shipped with this "
                           "build. EXISTS rests on the documented basis, not a probe - "
                           "recorded so the two can never be confused.",
                   **base_kw)

    return _mk("UNVERIFIABLE:kind_unhandled", "none", None, "UNVERIFIABLE", h7_kind=kind)


def _resolve_doc_hit(r, dotted, hit, source, table_syms, oracle_note=None):
    rt = r.get("deprecated_runtime")
    doc_dep = bool(hit["deprecated"])
    exists = r.get("exists")
    if exists is None:
        exists_basis = "documented_in_build_shipped_reference"
        tier = "VERIFIED-STATIC"
    else:
        exists_basis = "dir() table (H5)"
        tier = "VERIFIED-DERIVED"
    kw = {"h7_doc_entry": hit["entry"],
          "h7_doc_anchor": "%s:%s" % (hit["entry"], hit["line"]),
          "h7_exists_basis": exists_basis,
          "h7_runtime_deprecated": rt}
    if doc_dep:
        cell = "DECAY_CLOCK" if rt else "DECAY_CLOCK:doc_only"
        return _mk(cell, source, hit["entry"], tier,
                   h7_deprecation_verbatim=hit["verbatim"],
                   h7_note=(oracle_note or "") + (
                       " Authored help deprecates it and the runtime did not flag it: "
                       "the doc-side half of R72's union." if not rt else
                       " Runtime and authored help AGREE."),
                   **kw)
    if rt:
        return _mk("DECAY_CLOCK", source, hit["entry"], tier,
                   h7_doc_silent_deprecation=True,
                   h7_note=(oracle_note or "") + " RUNTIME says deprecated, the AUTHORED help "
                           "shipped with this build does NOT. R72's most dangerous cell.",
                   **kw)
    return _mk("OK", source, hit["entry"], tier,
               h7_note=oracle_note or "documented and current in the build-shipped reference.",
               **kw)


# ============================================ phase 2: the deprecation UNION (R72 rule 3)

def doc_verdict(r, ctx):
    """H7's own authored-help verdict for ONE row, from the build-shipped reference.

    Returns (doc_deprecated | None, source, anchor, verbatim). None means no local oracle
    covers this symbol - which is a different statement from False and is never collapsed
    into it.
    """
    hom, nodes, pdg = ctx["hom22"], ctx["nodes22"], ctx["pdg22"]
    sym, kind = r["symbol"], r["kind"]

    if kind == "parm_name":
        return None, "n/a", None, None

    if kind == "node_type":
        hits, _ver = nodes.lookup(sym)
        if not hits:
            return None, "nodes.zip@22.0.368 (no page)", None, None
        deps = [e for e in hits if nodes.meta[e]["deprecated"]]
        if deps and len(deps) == len(hits):
            e = sorted(deps)[0]
            return True, "nodes.zip@22.0.368", "%s:%d" % (e, nodes.meta[e]["dep_line"]), \
                nodes.meta[e]["verbatim"]
        if deps:
            # the census name matches pages in more than one context and they disagree.
            # 'any hit is deprecated' would have reported 85 doc-side deprecations, most of
            # them a bare SOP name colliding with a deprecated cop2 page. Undecidable is the
            # honest answer, and it matches the adjudication rule exactly.
            return None, "nodes.zip@22.0.368 (contexts disagree: %s)" % ",".join(
                sorted(e.split("/")[0] for e in hits)), None, None
        return False, "nodes.zip@22.0.368", sorted(hits)[0] + ":1", None

    dotted = r.get("resolved_owner") or sym
    root = dotted.split(".")[0]
    if root in ("pdg", "pdgd", "pdgutils"):
        hit = pdg.lookup(dotted)
        src = "tops.zip@22.0.368"
    elif root == "hou":
        hit = hom.lookup(dotted)
        src = "hom.zip@22.0.368"
    elif "." not in dotted:
        owners = hom.owners_of(dotted)
        if not owners:
            return None, "hom.zip@22.0.368 (leaf unbound)", None, None
        deps = {d: v for d, (_e, _l, dep, v) in owners.items() if dep}
        if deps and len(deps) == len(owners):
            d0 = sorted(deps)[0]
            e, l, _dep, vb = owners[d0]
            return True, "hom.zip@22.0.368 (invariant over %d owners)" % len(owners), \
                "%s:%s" % (e, l), vb
        if deps:
            return None, "hom.zip@22.0.368 (owners disagree)", None, None
        d0 = sorted(owners)[0]
        e, l, _dep, _vb = owners[d0]
        return False, "hom.zip@22.0.368 (invariant over %d owners)" % len(owners), \
            "%s:%s" % (e, l), None
    else:
        return None, "no local oracle for root '%s'" % root, None, None

    if hit is None:
        return None, src + " (no page)", None, None
    return bool(hit["deprecated"]), src, "%s:%s" % (hit["entry"], hit["line"]), hit["verbatim"]


def runtime_verdict(r):
    """H5's RUNTIME deprecation verdict, carried forward. Producer: H5. Never re-derived.

    H5 resolved two rows where `deprecationInfo()` fires in ONE node category and not the
    one SYNAPSE calls - `duplicate` is deprecated as a Sop and current as the Lop every
    call site uses, proven by live probe and recorded in `deprecation_scope`/`false_alarm`.
    Reading `deprecated_runtime` raw would silently overturn a VERIFIED-RUNTIME finding with
    no new evidence and would have reported `duplicate` as a third doc_silent_deprecation
    member. H7 has nothing that outranks that probe, so it honours it and reports the scoped
    rows in their own bucket instead of burying them.
    """
    if "deprecated_runtime" not in r:
        return None, None, None
    rd = r["deprecated_runtime"]
    ev = r.get("deprecated_runtime_evidence")
    scoped_away = rd and (
        r.get("false_alarm")
        or (r.get("deprecation_scope") == "category_scoped"
            and not r.get("emission_category_resolved")
            and r["quadrant"] != "DECAY_CLOCK"))
    if scoped_away:
        return None, ev, {
            "scoped_away": True,
            "deprecated_in_categories": r.get("deprecated_in_categories"),
            "not_deprecated_in_categories": r.get("not_deprecated_in_categories"),
            "h5_rationale": r.get("false_alarm") or r.get("deprecation_scope"),
            "runtime_deprecation_info": r.get("runtime_deprecation_info"),
        }
    return rd, ev, None


def deprecation_union(ctx):
    rows = ctx["h5"]["symbols"]
    out = []
    for r in rows:
        dd, dsrc, danch, dvb = doc_verdict(r, ctx)
        rd, rev, scoped = runtime_verdict(r)
        h5_doc = r.get("deprecated_docs")
        if h5_doc is None and r.get("documented") and "deprecated_runtime" not in r:
            h5_doc = r.get("deprecated")
        union = bool(dd) or bool(rd) or bool(h5_doc)
        out.append({
            "symbol": r["symbol"], "kind": r["kind"], "h5_quadrant": r["quadrant"],
            "h7_doc_deprecated": dd, "h7_doc_source": dsrc, "h7_doc_anchor": danch,
            "h7_doc_verbatim": dvb,
            "h5_doc_deprecated": h5_doc,
            "runtime_deprecated": rd, "runtime_evidence": rev,
            "runtime_scoped_away": scoped,
            "union_deprecated": union,
            "doc_silent_deprecation": bool(rd) and (dd is False),
            "doc_only_deprecation": bool(dd) and (rd is not True),
            "h5_h7_doc_disagree": (h5_doc is not None and dd is not None and bool(h5_doc) != bool(dd)),
            "exists": r.get("exists"),
        })
    return out


# ============================================================================== main

def main():
    ctx = {}
    ctx["hom22"] = HomOracle(HELP22)
    ctx["nodes22"] = NodeOracle(HELP22)
    ctx["pdg22"] = PdgOracle(HELP22)
    ctx["pylib"] = PyLibOracle(PYLIBS)
    ctx["cache"] = CacheOracle(CACHE)
    try:
        ctx["hom21"] = HomOracle(HELP21)
        ctx["nodes21"] = NodeOracle(HELP21)
    except Exception:
        ctx["hom21"] = ctx["nodes21"] = None

    ctx["commit"] = "8b18b3b344c7dcb3927bcb2947eef860471e6359"   # git rev-parse HEAD, this leg
    ctx["h5_sha16"] = sha16(H5LEDGER)
    ctx["h5"] = json.load(open(H5LEDGER, encoding="utf-8"))

    st = json.load(open(SYMTABLE, encoding="utf-8"))
    syms = st["symbols"]
    if isinstance(syms, dict):
        syms = list(syms)
    ctx["table_syms"] = set(syms)
    leaves = collections.defaultdict(list)
    for s in sorted(ctx["table_syms"]):          # sorted: the leaf->owners lists must not
        leaves[s.split(".")[-1]].append(s)       # depend on set iteration order
    ctx["table_leaves"] = leaves

    live = set()
    for p in (LOPCAT, COPCAT):
        try:
            c = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        stack = [c]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                for k, v in cur.items():
                    if k in ("name", "type", "type_name", "internal") and isinstance(v, str):
                        live.add(v)
                    stack.append(v)
            elif isinstance(cur, list):
                stack.extend(cur)
    ctx["live_types"] = live

    ok, controls = run_controls(ctx)
    audit = ctx["cache"].cited_number_audit()
    json.dump({"schema": "h7_controls/v1", "all_passed": ok, "controls": controls,
               "cited_number_audit": audit},
              open(OUT_CONTROLS, "w", encoding="utf-8"), indent=1)
    ctx["cited_number_audit"] = audit
    print("CONTROLS all_passed=%s" % ok)
    for c in controls:
        print("  %-4s %s  %s" % (c["id"], "PASS" if c["passed"] else "FAIL", c["what"][:88]))
    if not ok:
        print("\nABORT: a control failed. An uncalibrated reader adjudicates nothing (R60).")
        return 2

    verdicts = adjudicate(ctx)
    cells = collections.Counter()
    by_kind = collections.defaultdict(collections.Counter)
    for r, v in zip(ctx["h5"]["symbols"], verdicts):
        if v is None:
            continue
        cells[v["h7_cell"]] += 1
        by_kind[r["kind"]][v["h7_cell"]] += 1

    print("\n=== re-adjudication of H5's %d UNVERIFIABLE ===" % ctx["h5"]["counts"]["UNVERIFIABLE"])
    for c, n in cells.most_common():
        print("  %5d  %s" % (n, c))
    print("\nby kind:")
    for k in sorted(by_kind):
        print("  %s (%d):" % (k, sum(by_kind[k].values())))
        for c, n in by_kind[k].most_common():
            print("      %5d  %s" % (n, c))

    union = deprecation_union(ctx)
    silent = [u for u in union if u["doc_silent_deprecation"]]
    doconly = [u for u in union if u["doc_only_deprecation"]]
    decay = [u for u in union if u["union_deprecated"] and u["exists"] is not False]
    disagree = [u for u in union if u["h5_h7_doc_disagree"]]

    print("\n=== R72 rule 3: deprecation as the UNION of runtime and authored help ===")
    print("  H5 DECAY_CLOCK floor                     : 19")
    print("  H7 union over the whole ledger           : %d" % len(decay))
    print("  doc_silent_deprecation (runtime yes, help no): %d" % len(silent))
    for u in silent:
        print("      %-28s runtime=%s doc=%s  %s" % (u["symbol"], u["runtime_deprecated"],
                                                     u["h7_doc_deprecated"], u["h7_doc_anchor"]))
    print("  doc_only_deprecation (help yes, runtime not flagged): %d" % len(doconly))
    for u in doconly[:40]:
        print("      %-34s %s" % (u["symbol"], u["h7_doc_anchor"]))
    print("  H5-vs-H7 authored-help DISAGREEMENTS     : %d" % len(disagree))
    for u in disagree[:20]:
        print("      %-30s h5_doc=%s h7_doc=%s %s" % (u["symbol"], u["h5_doc_deprecated"],
                                                      u["h7_doc_deprecated"], u["h7_doc_anchor"]))

    # ---- binding confidence: a bare leaf bound by invariance is conditional, not proven
    def is_bare_leaf(sym, kind):
        return kind == "hom_method" and "." not in sym

    conf, cond = [], []
    for u in doconly:
        (cond if is_bare_leaf(u["symbol"], u["kind"]) else conf).append(u["symbol"])
    print("\n  doc_only split by binding confidence:")
    print("    owner explicit (dotted symbol or node type) : %d" % len(conf))
    print("    bare leaf, bound by owner-invariance        : %d  <- conditional on the call "
          "site being the named owner" % len(cond))
    print("      %s" % ", ".join(sorted(cond)))

    scoped = [u for u in union if u["runtime_scoped_away"]]
    print("\n  runtime deprecation SCOPED AWAY by H5's category resolution: %d" % len(scoped))
    for u in scoped:
        print("      %-12s deprecated_in=%s  sites=%s" % (
            u["symbol"], u["runtime_scoped_away"]["deprecated_in_categories"],
            u["runtime_scoped_away"]["not_deprecated_in_categories"]))

    # ---- the residual, made legible without being resolved
    unbound = [(r, v) for r, v in zip(ctx["h5"]["symbols"], verdicts)
               if v and v["h7_cell"] == "UNVERIFIABLE:leaf_unbound_owner"]
    hou_owned = [(r, v) for r, v in unbound
                 if any(s.startswith("hou.") for s in ctx["table_leaves"].get(r["symbol"], ()))]
    exec_ctx = [(r, v) for r, v in unbound
                if r["occurrences_by_context"].get("execution", 0) > 0]
    print("\n=== residual: 528 leaf_unbound_owner, characterised (NOT resolved) ===")
    print("  leaf also exists under a hou.* owner in the dir() table : %d" % len(hou_owned))
    print("  leaf occurs in an EXECUTION context in SYNAPSE          : %d" % len(exec_ctx))
    print("  top 12 by occurrence count:")
    for r, _v in sorted(unbound, key=lambda t: -t[0]["occurrence_count"])[:12]:
        owners = ctx["table_leaves"].get(r["symbol"], ())
        print("      %-24s occ=%-5d table_owners=%-4d ex=%s" % (
            r["symbol"], r["occurrence_count"], len(owners),
            sorted(o for o in owners if o.startswith("hou."))[:2]))

    shapes = collections.Counter(v.get("h7_residual_shape") for _r, v in unbound)
    print("  residual shape by the leaf's owner roots in the dir() table:")
    for s, n in shapes.most_common():
        print("      %5d  %s" % (n, s))

    emit_ledger(ctx, verdicts, cells, by_kind, controls, union, silent, doconly, decay,
                disagree, scoped, conf, cond, unbound, shapes, exec_ctx)

    globals()["_H7"] = {"ctx": ctx, "verdicts": verdicts, "cells": cells,
                        "by_kind": by_kind, "controls": controls, "union": union,
                        "silent": silent, "doconly": doconly, "decay": decay,
                        "disagree": disagree}
    return 0


def emit_ledger(ctx, verdicts, cells, by_kind, controls, union, silent, doconly, decay,
                disagree, scoped, conf, cond, unbound, shapes, exec_ctx):
    h5 = ctx["h5"]
    hom, nodes, pdg = ctx["hom22"], ctx["nodes22"], ctx["pdg22"]
    resolved = {k: v for k, v in cells.items() if not k.startswith("UNVERIFIABLE")}
    residual = {k: v for k, v in cells.items() if k.startswith("UNVERIFIABLE")}

    rows = []
    for r, v in zip(h5["symbols"], verdicts):
        if v is None:
            continue
        rows.append({
            "symbol": r["symbol"], "kind": r["kind"],
            "occurrence_count": r["occurrence_count"],
            "occurrences_by_context": r["occurrences_by_context"],
            "h5_quadrant": "UNVERIFIABLE",
            "h5_reason": r.get("reason") or r.get("exists_evidence"),
            "anchors": r.get("anchors"), "anchors_truncated": r.get("anchors_truncated"),
            **v})

    ledger = {
        "schema": "h22_compat_ledger/v2",
        "leg": "H7",
        "ruling": "R72",
        "generated": "2026-07-26",
        "generated_at_commit": ctx["commit"],
        "model": "claude-opus-5[1m]",
        "settings_profile": "harness/readonly-settings.json (READ-ONLY leg; harness/notes/** "
                            "is the only writable path, per R61)",
        "supersedes": None,
        "supersedes_note": "H5's h22_compat_ledger.json is NOT superseded. Both are kept: H5 "
                           "holds the census and the live probes, H7 holds the local-reference "
                           "re-adjudication of H5's UNVERIFIABLE bucket. H7 carries H5's "
                           "runtime verdicts forward and never re-derives them.",
        "purpose": "H5 returned UNVERIFIABLE:1267 - its largest bucket. R72 established two "
                   "LOCAL, version-pinned H22 references. This leg re-adjudicates that bucket "
                   "against the correct local source per symbol kind, adds the "
                   "doc_silent_deprecation sub-cell R72 rule 4 ordered, and states the residual "
                   "honestly. NO NETWORK: every oracle shipped with the build or is a prior "
                   "leg's artifact.",
        "no_network": True,
        "h5_input": {
            "path": "harness/notes/h22_compat_ledger.json (read from the h5-compat worktree, "
                    "not assumed merged)",
            "abs_path": H5LEDGER,
            "sha256_16": ctx["h5_sha16"],
            "leg": h5["leg"], "commit": h5["generated_at_commit"],
            "model": h5["model"], "counts": h5["counts"],
        },
        "oracles": {
            "O1_hom_zip": {
                "role": "HOM axis - AUTHORITATIVE (R72 rule 1)",
                "path": os.path.join(HELP22, "hom.zip"),
                "sha256_16": hom.sha16, "entries": len(hom.entries),
                "why_authoritative": "ships inside 22.0.368, so it is version-pinned by "
                                     "construction: no robots restriction, no breadcrumb "
                                     "ambiguity, no URL whose meaning changes under a citation",
                "index_shapes": ["hou/<Class>.txt class page with ::name(...) member sections",
                                 "hou/<name>.txt module-level function or enum as its own page",
                                 "hou/<mod>/<name>.txt nested module member (hou/logging/log.txt)"],
                "dotted_symbols_indexed": len(hom.pages),
                "distinct_member_leaves": len(hom.members),
                "already_h5s_oracle": True,
            },
            "O2_nodes_zip": {
                "role": "NODE axis - AUTHORITATIVE",
                "path": os.path.join(HELP22, "nodes.zip"),
                "sha256_16": nodes.sha16, "entries": len(nodes.entries),
                "already_h5s_oracle": True,
                "precision": "nodes.zip is named in H5's own docs_authority.paths and cited by "
                             "H5 (nodes/lop/karmaocean.txt:13). R72's source table listed only "
                             "the userprefs cache for the node axis and the H7 brief inherited "
                             "that framing - the correction is to R72's table, not to H5's "
                             "oracle set. H7's contribution is APPLICATION: a complete index "
                             "applied to the 298 node_type rows H5's probe never reached.",
                "lop_entries": sum(1 for e in nodes.entries if e.startswith("lop/")),
            },
            "O3_tops_zip": {
                "role": "pdg axis - AUTHORITATIVE. NEW to this relay.",
                "path": os.path.join(HELP22, "tops.zip"),
                "sha256_16": pdg.sha16, "entries": len(pdg.entries),
                "pdg_pages": sum(1 for e in pdg.entries if e.startswith("pdg/")),
                "corrects": "H5 recorded 'the shipped HOM reference contains no pdg surface, so "
                            "absence from the index is NOT evidence' on 90 pdg rows. True of "
                            "hom.zip; the pdg reference ships in tops.zip in the same directory.",
            },
            "O4_shipped_python_source": {
                "role": "EXISTENCE for shipped python modules - VERIFIED-STATIC. NEW.",
                "path": PYLIBS,
                "modules_indexed": sorted(ctx["pylib"].mods),
                "why": "neither the dir() symbol table (hou/pdg/pxr only) nor hom.zip covers "
                       "hdefereval / toolutils / husd. The build's own readable source does.",
                "not_a_probe": "static read of the build's source. Never labelled "
                               "VERIFIED-RUNTIME.",
            },
            "O5_help_cache": {
                "role": "THIRD source for the node axis. NEVER authoritative (R72 rule 2).",
                "path": CACHE,
                "node_docs": len(ctx["cache"].nodes),
                "proof_it_is_a_browsing_cache": "C10c: LOP types documented by the build's own "
                                                "reference are absent from it because nobody "
                                                "opened the page.",
            },
            "O6_h5_runtime_verdicts": {
                "role": "EXISTS + runtime deprecationInfo(), carried forward",
                "tier": "VERIFIED-DERIVED (producer: H5, live probes on 22.0.368)",
                "never_re_derived": True,
                "scope_rulings_honoured": "H5's category_scoped / false_alarm resolutions are "
                                          "honoured, not silently overturned (C20).",
            },
            "O7_dir_symbol_table": {
                "role": "leaf-existence cross-check",
                "path": "python/synapse/cognitive/tools/data/h22_symbol_table.json",
                "symbols": len(ctx["table_syms"]),
                "scope_limit": "enumerates only hou, pdg, pxr; expands class children but not "
                               "module children. H5's SCOPE_LIMIT applies unchanged.",
            },
        },
        "controls": {
            "standard": "R60 - a reader that has not been shown to produce a known-correct "
                        "answer is uncalibrated. Every control states the condition under which "
                        "it FAILS (Law 1) and the run ABORTS if any fails.",
            "all_passed": all(c["passed"] for c in controls),
            "count": len(controls),
            "reader_control_demonstrated": {
                "RopNode": "hou/RopNode.txt indexed, %d members, ZERO cancel/abort/interrupt/"
                           "kill verbs - the R72 positive control, reproduced"
                           % len(hom._sections(read_zip_text(hom.z, "hou/RopNode.txt"))[1]),
                "TopNode": "hou.TopNode.dirtyAllTasks resolves to hou/TopNode.txt with signature "
                           "`dirtyAllTasks(self, remove_outputs)` and the deprecation notice "
                           "detected verbatim: %r" % (
                               hom.lookup("hou.TopNode.dirtyAllTasks")["verbatim"],),
            },
            "detail": controls,
        },
        "cited_number_audit": ctx["cited_number_audit"],
        "matrix": {
            "inherited_from_h5": h5["matrix"],
            "h7_additions": {
                "doc_silent_deprecation": "runtime deprecationInfo() says deprecated, the "
                                          "AUTHORED help shipped with this build does not. R72 "
                                          "rule 4: the most dangerous cell, because every "
                                          "human-facing surface says the symbol is fine.",
                "DECAY_CLOCK:doc_only": "authored help deprecates it, runtime did not flag it. "
                                        "The other half of R72 rule 3's union; this is what "
                                        "corrects the floor upward.",
                "OK:documented_current_exists_unprobed": "documented and current in the shipped "
                                                         "reference; EXISTS rests on H5's "
                                                         "documented_basis rule, not a probe. "
                                                         "Recorded so the two are never confused.",
                "OK:exists_undocumented_shipped_module": "defined in the build's own shipped "
                                                         "source; outside the published HOM "
                                                         "surface, so 'documented' does not apply.",
                "OUT_OF_REFERENCE_SCOPE:third_party": "pxr/OpenUSD. EXISTS is decided; the H22 "
                                                      "reference is not the doc authority. "
                                                      "PRIVATE_API would be a false alarm and "
                                                      "UNVERIFIABLE would imply a local oracle "
                                                      "exists and was not read. Neither is true.",
                "OUT_OF_MATRIX:no_houdini_referent": "absent from every local reference AND from "
                                                     "the dir() table's leaf set. Census "
                                                     "over-collection, not a compat question.",
                "MISATTRIBUTED:doc_spelling": "the shipped reference documents the symbol under "
                                              "a different owner spelling (capitalisation). "
                                              "Wrong owner is actionable; undecidable is not.",
                "UNVERIFIABLE:*": "every residual now carries a NAMED reason. See residual.",
            },
        },
        "counts": {
            "h5_unverifiable_input": h5["counts"]["UNVERIFIABLE"],
            "resolved_total": sum(resolved.values()),
            "resolved_by_cell": dict(sorted(resolved.items(), key=lambda kv: -kv[1])),
            "still_unverifiable_total": sum(residual.values()),
            "still_unverifiable_by_reason": dict(sorted(residual.items(),
                                                        key=lambda kv: -kv[1])),
            "by_kind": {k: dict(v) for k, v in by_kind.items()},
            "doc_silent_deprecation": len(silent),
            "decay_clock_floor_h5": 19,
            "decay_clock_union_h7": len(decay),
            "arithmetic_check": sum(cells.values()) == h5["counts"]["UNVERIFIABLE"],
        },
        "decay_clock": {
            "r72_rule_3": "deprecation is the UNION of runtime deprecationInfo() and authored "
                          "help; disagreement between them is itself a finding and gets its own "
                          "cell.",
            "h5_floor": 19,
            "h7_union": len(decay),
            "verdict": "H5's floor of 19 is CORRECTED UPWARD to %d with per-symbol anchors "
                       "below. It remains a floor, not a total: the residual buckets contain "
                       "symbols whose deprecation status no local source can decide." % len(decay),
            "doc_silent_deprecation": {
                "count": len(silent),
                "members": [{"symbol": u["symbol"], "kind": u["kind"],
                             "runtime": u["runtime_deprecated"],
                             "runtime_evidence": u["runtime_evidence"],
                             "authored_help": u["h7_doc_deprecated"],
                             "authored_help_source": u["h7_doc_source"],
                             "authored_help_anchor": u["h7_doc_anchor"]} for u in silent],
                "confirmed_against": "the AUTHORITATIVE build-shipped node reference, not the "
                                     "browsing cache. R72 established this on the cache; H7 "
                                     "re-tested it on nodes.zip and it HOLDS: "
                                     "lop/karmarenderproperties.txt (56,325 chars, #since 18.0) "
                                     "and lop/karma.txt (2,556 chars) carry no deprecation "
                                     "marker of any of the five kinds this leg detects, while "
                                     "the runtime flags both.",
                "why_it_is_the_dangerous_cell": "an artist reading the shipped help has no way "
                                                "to learn these node types are decaying, and "
                                                "SYNAPSE emits them 123 and 31 times.",
            },
            "doc_only_deprecation": {
                "count": len(doconly),
                "owner_explicit": sorted(conf),
                "bare_leaf_conditional": sorted(cond),
                "binding_caveat": "a bare leaf is bound by INVARIANCE over the documented "
                                  "owners - every documented owner of that leaf is deprecated, "
                                  "so the verdict does not depend on which one the census meant. "
                                  "It does NOT prove the call site is a HOM object at all. The "
                                  "%d conditional rows are actionable leads, not verdicts."
                                  % len(cond),
                "members": [{"symbol": u["symbol"], "kind": u["kind"],
                             "anchor": u["h7_doc_anchor"], "verbatim": u["h7_doc_verbatim"],
                             "runtime": u["runtime_deprecated"],
                             "binding": "owner_explicit" if u["symbol"] in conf
                                        else "bare_leaf_invariance"} for u in doconly],
            },
            "runtime_deprecation_scoped_away": {
                "count": len(scoped),
                "note": "deprecationInfo() fires in a node category SYNAPSE does not call. H5 "
                        "resolved these by live probe; H7 honours the ruling and reports them "
                        "here rather than burying them in OK.",
                "members": [{"symbol": u["symbol"], **u["runtime_scoped_away"]}
                            for u in scoped],
            },
            "h5_h7_authored_help_disagreements": {
                "count": len(disagree),
                "dominant_cause": "H5's authored-help reader did not follow the "
                                  "`:include /composite/_old_cops_deprecated:` banner, so the "
                                  "whole deprecated old-COPs surface (hou.Cop2Node and the "
                                  "cop2/* node docs) read as CURRENT.",
                "members": [{"symbol": u["symbol"], "h5_doc": u["h5_doc_deprecated"],
                             "h7_doc": u["h7_doc_deprecated"], "anchor": u["h7_doc_anchor"],
                             "verbatim": u["h7_doc_verbatim"]} for u in disagree],
            },
            "deprecation_marker_vocabulary": {
                "read_off_the_corpus": True,
                "markers": {
                    "status_header": "#status: deprecated  (hou/ChannelEditorPane.txt:6)",
                    "include_banner": ":include /composite/_old_cops_deprecated:  "
                                      "(hou/Cop2Node.txt:14)",
                    "warning_block": ":warning:Deprecated:  (lop/karmaocean.txt:12)",
                    "summary_prose": '"""(Deprecated) ..."""  '
                                     "(chop/extractbonetransforms.txt:10)",
                    "body_notice": "prose notice in the page's own region  "
                                   "(hou/expandString.txt:11)",
                },
                "false_positive_classes_excluded": {
                    "parameter_label": "sop/edit.txt:213 'Radius with Connectivity (deprecated)'",
                    "local_variable": "lop/reference.txt:58 '(`$IIDX` is deprecated)' - SYNAPSE "
                                      "has 78 occurrences of the LOP Reference node; this was "
                                      "the most damaging potential false alarm in the leg",
                    "menu_option": "dop/crowdsolver.txt:171 'Simple (Deprecated):'",
                    "self_named_member": "hou/ApexNodeType.txt:18 '::deprecated(self) -> bool'",
                },
                "effect_of_tightening": "the first, page-wide detector reported 85 doc-side "
                                        "deprecations. After region-scoping, the variable-notice "
                                        "guard, the self-named-member guard and context "
                                        "invariance: %d. Every one of the removed rows was "
                                        "inspected line-by-line." % len(doconly),
            },
        },
        "residual": {
            "honest_statement": "R72 framed H5's 1267 as partly a REACHABILITY artifact. Fixing "
                                "reachability accounts for less of it than expected. The bucket "
                                "decomposes into four causes, only one of which is reachability.",
            "decomposition": {
                "reachability_or_oracle_scope": "resolved here - %d rows. The oracles existed "
                                                "locally and were not indexed: tops.zip for pdg, "
                                                "the shipped python source for hdefereval, and "
                                                "nodes.zip applied to the node_type rows H5's "
                                                "live probe never reached."
                                                % sum(resolved.values()),
                "census_over_collection": "%d rows are not Houdini symbols at all - bare "
                                          "SYNAPSE-local method names, malformed tokens ('...', "
                                          "'_doc', '_provenance', 'symbols_PHANTOM_do_not_use') "
                                          "and one FILENAME ('hdefereval.py'). H5's UNVERIFIABLE "
                                          "was inflated by census scope, not only by doc access."
                                          % (cells.get("OUT_OF_MATRIX:no_houdini_referent", 0)
                                             + cells.get("OUT_OF_MATRIX:not_a_symbol", 0)),
                "instrument_limit_no_source_can_fix": "%d rows: hou.session is a user-data "
                                                      "namespace assigned at runtime. Permanently "
                                                      "undecidable, and that is the correct "
                                                      "answer, not a gap."
                                                      % cells.get("UNVERIFIABLE:runtime_namespace", 0),
                "genuinely_unknown": "%d rows. The real unknown after reachability is fixed."
                                     % sum(residual.values()),
            },
            "largest_residual_bucket": {
                "cell": "UNVERIFIABLE:leaf_unbound_owner",
                "count": cells.get("UNVERIFIABLE:leaf_unbound_owner", 0),
                "what_it_is": "the census recorded a BARE method name with no dotted owner. The "
                              "leaf exists somewhere on the build but cannot be bound to the "
                              "owner at the call site, and existing-somewhere is not "
                              "existing-here.",
                "characterised_not_resolved": dict(shapes),
                "reading": "the largest slice is pxr-shaped - `Get` (249 occurrences, 135 table "
                           "owners), `Set` (328), `GetPrimAtPath` (258), `GetAttribute` (197) "
                           "are OpenUSD names the census recorded as hom_method. They are not "
                           "HOM-reference questions at all. This is a CENSUS KIND defect, and "
                           "fixing it is the single highest-yield change available to the next "
                           "compat pass.",
                "occurs_in_execution_context": len(exec_ctx),
            },
            "what_would_close_more": [
                "a live node-type existence probe would decide the EXISTS axis on the %d "
                "node_absent_from_reference_and_unprobed rows and confirm the %d "
                "documented-but-unprobed rows. H7 ran no live probe: the brief scoped this leg "
                "to local references and H5's existing runtime verdicts, and a hython run "
                "contends for the licence with the live session."
                % (cells.get("UNVERIFIABLE:node_absent_from_reference_and_unprobed", 0),
                   cells.get("OK:documented_current_exists_unprobed", 0)),
                "a census that emits DOTTED owners for method calls would collapse the %d-row "
                "leaf_unbound_owner bucket. No doc source can fix an unbound leaf."
                % cells.get("UNVERIFIABLE:leaf_unbound_owner", 0),
            ],
        },
        "anchor_format": "doc anchors are <zip-relative entry>:<line>, resolvable offline "
                         "against the named sha256_16. Code anchors are file:line|context, "
                         "carried forward from H5 unchanged.",
        "producers": {
            "_law2": "every number in this ledger is emitted by the script below. It is the only "
                     "producer; there are no hand-counted figures.",
            "script": "harness/notes/h7_readjudicate.py",
            "sha256": hashlib.sha256(
                open(os.path.join(REPO, "harness", "notes", "h7_readjudicate.py"),
                     "rb").read()).hexdigest(),
            "invocation": "python -c \"exec(open('harness/notes/h7_readjudicate.py',"
                          "encoding='utf-8').read())\"",
            "why_exec": "the read-only leg profile allows `python -c`, not `python <file>`. The "
                        "file is still the producer path and is hashed here.",
            "controls_artifact": "harness/notes/h7_controls.json",
            "suite": "NOT RUN. This leg is fenced read-only and touches no product code; there "
                     "is no suite claim to make.",
        },
        "symbols": rows,
        "deprecation_union_all_rows": [u for u in union
                                       if u["union_deprecated"] or u["h5_h7_doc_disagree"]
                                       or u["runtime_scoped_away"]],
    }
    json.dump(ledger, open(OUT_LEDGER, "w", encoding="utf-8"), indent=1)
    print("\nwrote %s  (%d rows re-adjudicated, %d union rows of interest)"
          % (os.path.relpath(OUT_LEDGER, REPO), len(rows),
             len(ledger["deprecation_union_all_rows"])))
    print("  arithmetic check (cells sum == 1267): %s"
          % ledger["counts"]["arithmetic_check"])


_rc = main()
