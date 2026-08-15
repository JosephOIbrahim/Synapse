"""H9 -- parser and include-resolver for the shipped Houdini help corpus.

WHY THIS EXISTS
---------------
H9 harvests ``houdini/help/nodes.zip`` into semantic (D2) grounding. A page
stored as a blob is not grounding; structure has to be extracted. Two facts
found by measurement (not assumed) force a real parser rather than a regex:

1. **Identity is not the filename.** ``lop/backgroundplate-2.0.txt`` declares
   ``#internal: backgroundplate`` (UNversioned) while
   ``cop/bakegeometrytextures-2.0.txt`` declares
   ``#internal: bakegeometrytextures::2.0`` (versioned). Neither the filename
   nor the directive is reliable alone; both are collected and reconciled.

2. **Parameters arrive by reference.** 431 of 723 lop/cop/cop2 pages contain
   ``:include target:`` statements -- 2342 of them. A per-page parse that does
   not resolve includes undercounts documented parameters on 60% of pages, and
   would report the 143 cop2 pages that include
   ``/composite/_old_cops_deprecated`` as silently-undeprecated -- the exact
   R72 failure class this leg is meant to measure, manufactured by the tool
   rather than found in the source.

TRUTH TIER
----------
Everything this module produces is **VERIFIED-DOC**: read from the shipped
reference of the running build. It is NOT VERIFIED-RUNTIME. Documentation is
authored, therefore it can be stale, silent, or wrong -- R72 is the proof
(``nodes/lop/karmarenderproperties`` never says the type is deprecated; the
runtime flags it). Nothing here may be summed with probe-derived grounding.

PRODUCER: this file. Consumers: coverage.py, harvest.py, crosscheck_runtime.py.
"""

from __future__ import annotations

import os
import re
import zipfile
from pathlib import Path

# --------------------------------------------------------------------------
# Locations. A build is ADDRESSED, never discovered: resolution is by explicit
# parameter or environment override, defaulting to the current pin. Callers
# choose the build (``HelpCorpus(build=...)``); the module is never mutated to
# repoint. A wrong or absent build still FAILS LOUDLY in ``HelpCorpus._load``
# rather than silently measuring another build's corpus -- that loud failure is
# the whole point of the pin and parameterization preserves it, it does not
# soften it into a fallback.
# --------------------------------------------------------------------------
_DEFAULT_BUILD = "22.0.368"          # the current pin; overridable, never mutated


def resolve_build(build: str | None = None) -> str:
    """The build to address: explicit arg > ``SYNAPSE_HELP_BUILD`` env > default pin.

    Read at CALL time, not import time, so a caller may set the environment and
    construct a corpus without editing or mutating this module.
    """
    if build:
        return build
    return os.environ.get("SYNAPSE_HELP_BUILD", _DEFAULT_BUILD)


def _install_help_dir(build: str) -> Path:
    """The STANDARD per-build install help dir -- no environment override.

    An explicitly-named build addresses its OWN standard install path, so two
    explicit builds never collapse onto a single ``SYNAPSE_HELP_DIR``.
    """
    return Path(
        r"C:\Program Files\Side Effects Software\Houdini %s\houdini\help" % build
    )


def help_dir_for(build: str | None = None) -> Path:
    """DEFAULT-resolution ``houdini/help`` directory for a build.

    ``SYNAPSE_HELP_DIR`` overrides the location outright, for installs not on the
    default Windows path; otherwise the path is the standard per-build install
    for the resolved build. Derivation is NOT discovery: if that build is not
    installed the archive is absent and loading fails loudly
    (``HelpCorpus._load``). No fallback to another build -- serving another
    build's pages silently is the exact defect this pin exists to prevent.
    """
    override = os.environ.get("SYNAPSE_HELP_DIR")
    if override:
        return Path(override)
    return _install_help_dir(resolve_build(build))


def build_from_path(help_dir) -> str | None:
    """The build a standard install path encodes, or None if it encodes none.

    ``...\\Houdini 22.0.400\\houdini\\help`` -> ``"22.0.400"``. A custom/synthetic
    directory encodes no build and returns None. Used to keep a corpus's build
    LABEL in agreement with the pages it actually loaded whenever the location is
    overridden -- a label that disagrees with the directory is the silent
    wrong-build defect, reached via the override instead of the build selector.
    """
    m = re.search(r"Houdini\s+(\d+(?:\.\d+)+)", str(help_dir))
    return m.group(1) if m else None


# Module-level defaults -- the back-compatible zero-arg surface every existing
# importer (coverage.py, harvest.py, i1_extract.py, ...) already reads. FROZEN at
# the pin: environment overrides (SYNAPSE_HELP_BUILD / SYNAPSE_HELP_DIR) and the
# build= parameter act only at PER-INSTANCE resolution time (resolve_build /
# help_dir_for / HelpCorpus), never on this import-time snapshot. So a consumer
# that asserts against helpdoc.BUILD still sees a stable constant, and setting an
# override env var never silently repoints the module out from under it.
BUILD = _DEFAULT_BUILD
HELP_DIR = _install_help_dir(BUILD)
NODES_ZIP = HELP_DIR / "nodes.zip"

# Contexts this leg measures. cop == Copernicus (the live `cop` category),
# cop2 == the legacy compositing network.
CONTEXTS = ("lop", "cop", "cop2")

_MAX_INCLUDE_DEPTH = 8


def _norm(key: str) -> str:
    """Collapse '.' and '..' segments in a help path.

    Cross-context includes ship relative: lop pages reference
    ``../vop/kma_physicallens#bokeh_map``. Without this the target reads as a
    missing page and 87 shipped-and-valid includes are reported as doc defects.
    """
    parts: list[str] = []
    for seg in key.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts:
                parts.pop()
            continue
        parts.append(seg)
    return "/".join(parts)


# --------------------------------------------------------------------------
# Corpus loading
# --------------------------------------------------------------------------
class HelpCorpus:
    """All shipped help text, addressed the way ``:include`` addresses it.

    Keys are help paths WITHOUT extension, rooted like the help system's own
    absolute references: ``nodes/lop/blend``, ``composite/_old_cops_deprecated``.
    ``nodes.zip`` entries are ``lop/blend.txt`` -> ``nodes/lop/blend``; every
    other ``<name>.zip`` is rooted at ``<name>/``.
    """

    def __init__(self, build: str | None = None, help_dir=None) -> None:
        # Resolve THIS corpus's location independently of the module defaults,
        # so two HelpCorpus instances for different builds can coexist in one
        # process without either mutating the module or each other. The build
        # LABEL is kept in agreement with the directory actually loaded -- a
        # label that disagrees with the pages is the silent wrong-build defect.
        #
        #   help_dir=  explicit path wins the LOCATION; label follows the path
        #              (or the explicit build=, which must not contradict it)
        #   build=     explicit build -> its STANDARD install path; the
        #              SYNAPSE_HELP_DIR *default*-location override does NOT
        #              apply, so two explicit builds never collapse onto one dir
        #   neither    default resolution; SYNAPSE_HELP_DIR overrides the
        #              location and the label follows that path
        if help_dir is not None:
            self.help_dir = Path(help_dir)
            self.build = self._label_for(build, self.help_dir)
        elif build is not None:
            self.build = resolve_build(build)
            self.help_dir = _install_help_dir(self.build)
        else:
            env_dir = os.environ.get("SYNAPSE_HELP_DIR")
            if env_dir:
                self.help_dir = Path(env_dir)
                self.build = self._label_for(None, self.help_dir)
            else:
                self.build = resolve_build(None)
                self.help_dir = _install_help_dir(self.build)
        self.nodes_zip = self.help_dir / "nodes.zip"
        self.pages: dict[str, str] = {}
        self.origin: dict[str, str] = {}  # help path -> "<zip>!<entry>"
        self._load()

    @staticmethod
    def _label_for(build: str | None, help_dir: Path) -> str:
        """The build label for an overridden LOCATION -- it must match the dir.

        The path's own build wins the label so it can never disagree with the
        pages loaded. An explicit ``build=`` that CONTRADICTS the path is a caller
        error and fails loud (never a silent mislabel). When the path encodes no
        build (a custom dir), the explicit build -- else the default resolution --
        labels it, since there is nothing to contradict.
        """
        derived = build_from_path(help_dir)
        if build and derived and build != derived:
            raise SystemExit(
                "build/help_dir disagree: build=%s but %s is build %s "
                "-- refusing to mislabel" % (build, help_dir, derived))
        return build or derived or resolve_build(None)

    def _load(self) -> None:
        if not self.nodes_zip.exists():
            # LOUD by design, and it names the missing path so the caller sees
            # WHICH build's archive is absent -- never a silent fall-through to
            # another build's corpus. SystemExit (not a swallowable Exception)
            # keeps the failure loud even inside a broad ``except Exception``.
            raise SystemExit(
                "nodes.zip absent for build %s at %s -- refusing to guess"
                % (self.build, self.nodes_zip)
            )
        for zp in sorted(self.help_dir.glob("*.zip")):
            root = zp.stem  # nodes.zip -> "nodes"
            try:
                zf = zipfile.ZipFile(zp)
            except zipfile.BadZipFile:
                continue
            with zf:
                for info in zf.infolist():
                    if info.is_dir() or not info.filename.endswith(".txt"):
                        continue
                    key = "%s/%s" % (root, info.filename[:-4])
                    if key in self.pages:
                        continue
                    try:
                        # utf-8-SIG, not utf-8: some shipped pages carry a BOM
                        # (verified: cop2/emboss.txt). A BOM makes the first
                        # line start with U+FEFF instead of '#', which silently
                        # hides the page's first directive -- for emboss that is
                        # '#type: node', so the page reads as a non-node and the
                        # type reads as undocumented. A decode flag was the whole
                        # bug.
                        text = zf.read(info).decode("utf-8-sig", "replace")
                    except Exception:
                        continue
                    self.pages[key] = text
                    self.origin[key] = "%s!%s" % (zp.name, info.filename)
        self._load_loose()

    def _load_loose(self) -> None:
        """Help that ships UNZIPPED, e.g. ``help/copernicus/``.

        Missed on the first pass, and it mattered: 8 cop pages include
        ``/copernicus/_common_notes#comp_sim/``. Loading only ``*.zip`` scored
        those as broken shipped includes -- a defect manufactured by the reader
        and then reported as a finding about the docs. Loose files lose to zip
        entries on key collision so archive content stays authoritative.
        """
        for path in self.help_dir.rglob("*.txt"):
            rel = path.relative_to(self.help_dir).as_posix()
            key = rel[:-4]
            if key in self.pages:
                continue
            try:
                self.pages[key] = path.read_text(encoding="utf-8-sig", errors="replace")
            except Exception:
                continue
            self.origin[key] = rel

    # -- resolution ------------------------------------------------------
    def resolve_path(self, target: str, base_dir: str) -> str | None:
        """Resolve an include/link target to a corpus key.

        Absolute targets start with ``/`` and are rooted at the help root.
        Relative targets resolve against the including page's directory --
        verified: ``maskparms#maskparms/`` appears only in cop2 pages and the
        file is ``cop2/maskparms.txt``.
        """
        t = target.strip().strip("/") if target.startswith("/") else target.strip()
        t = t.rstrip("/")
        if target.strip().startswith("/"):
            cand = [t]
        else:
            cand = ["%s/%s" % (base_dir, t), t, "nodes/%s" % t]
        for c in cand:
            c = _norm(c)
            if c in self.pages:
                return c
        return None


# --------------------------------------------------------------------------
# Line-level helpers
# --------------------------------------------------------------------------
_DIRECTIVE_RE = re.compile(r"^#(\w+):\s*(.*?)\s*$")
_TITLE_RE = re.compile(r"^=\s*(.+?)\s*=\s*$")
_ATSECTION_RE = re.compile(r"^@(\w+)\s*$")
# Leading whitespace is significant here only in that it must be TOLERATED:
# sub-section anchors ship indented, e.g. '    === Driver === (driver_tab)'.
_SECTION_RE = re.compile(r"^\s*(={2,})\s*(.+?)\s*\1\s*(?:\((\S+)\))?\s*$")
# Greedy to the FINAL colon: include targets may themselves contain colons.
_INCLUDE_RE = re.compile(r"^(\s*):include\s+(.+):\s*$")
# '#id: size, size_pixel, size_local' -- one doc entry, three internal parms.
_ID_RE = re.compile(r"^\s*#id:\s*(.+?)\s*$")
# cop2 pages name internal parms as '#channels: /diffr /diffg /diffb'. Ignoring
# this form reports every cop2 parameter as un-identifiable (emboss: 0 of 10).
_CHANNELS_RE = re.compile(r"^\s*#channels:\s*(.+?)\s*$")
# Labels may be prefixed '::' (observed lop/rendervar '::Clear Value:').
_ENTRY_RE = re.compile(r"^(\s*)(?!#)(?![-*])(?::*)(\S.*?):\s*$")
_BOXLIKE_RE = re.compile(r"^(\s*):(box|warning|tip|note|important)\s*:?(.*)$")
# Pseudo-tag anchor form, 42 occurrences corpus-wide, shipped without the
# leading '<<': 'parameters id="maskparms">>'. It anchors the cop2 mask/pixel
# fragments, which together carry ~256 of the corpus's include references.
_TAGANCHOR_RE = re.compile(r'^\s*(?:<<)?(\w+)\s+id="([^"]+)">>\s*$')


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def page_directives(text: str) -> dict[str, str]:
    """Top-level ``#key: value`` directives. Padding is tolerated (`#type:     node`)."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("#"):
            continue
        m = _DIRECTIVE_RE.match(line)
        if m and m.group(1) not in out:
            out[m.group(1)] = m.group(2)
    return out


def page_title(text: str) -> str | None:
    for line in text.splitlines():
        m = _TITLE_RE.match(line)
        if m:
            return m.group(1)
    return None


def page_summary(text: str) -> str | None:
    """The ``\"\"\"...\"\"\"`` blurb -- the authored one-line intent of the node."""
    m = re.search(r'"""(.*?)"""', text, re.S)
    if not m:
        return None
    return clean_markup(" ".join(m.group(1).split()))


def clean_markup(s: str) -> str:
    """Strip help markup, keep the words. Grounding is prose, not wiki source."""
    s = re.sub(r"\[([^\]|]+)\|[^\]]*\]", r"\1", s)   # [Label|target] -> Label
    s = re.sub(r"\[([^\]|]+)\]", r"\1", s)            # [Label]        -> Label
    s = s.replace("__", "").replace("`", "")
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


# --------------------------------------------------------------------------
# Include resolution
# --------------------------------------------------------------------------
def ids_on_line(line: str) -> list[str] | None:
    """Internal parameter names declared on one line, in either shipped form."""
    m = _ID_RE.match(line)
    if m:
        return [p.strip() for p in m.group(1).split(",") if p.strip()]
    m = _CHANNELS_RE.match(line)
    if m:
        return [p.strip().lstrip("/") for p in m.group(1).split() if p.strip("/ ")]
    return None


def _anchor_matches(anchor: str, ids: list[str]) -> bool:
    """Anchors address a parm by its LAST colon-separated component.

    Verified: ``:include rendervar#clearValue:`` targets the entry declared
    ``#id: driver:parameters:aov:husk:clearValue``. Requiring a full match
    silently dropped 20 of 86 includes on karmarenderproperties alone.
    """
    return any(anchor == i or i.rsplit(":", 1)[-1] == anchor for i in ids)


def _anchored_block(text: str, anchor: str) -> str | None:
    """Return the block an include target addresses. Body is dedented.

    Four anchor forms are shipped, all observed in the corpus:
      1. ``:box:`` + indented ``#id: sampling_block`` + indented entries
      2. a parameter entry ``Label:`` + indented ``#id: parmname``
      3. ``== Tips == (tips)`` section headers
      4. ``parameters id="maskparms">>`` pseudo-tags

    Form 2 must return the LABEL LINE TOO. Returning only the body dedents the
    parameter's menu values to the entry indent, and every one of them is then
    counted as a separate parameter -- karmarenderproperties gained four
    phantom parameters ('Manual', 'Set Width, Compute Height...') that way.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        ids = ids_on_line(line)
        if not ids or not _anchor_matches(anchor, ids):
            continue
        ind = _indent(line)
        owner = None
        for j in range(i - 1, -1, -1):
            if not lines[j].strip():
                continue
            if _indent(lines[j]) < ind and _ENTRY_RE.match(lines[j]) \
                    and not _BOXLIKE_RE.match(lines[j]):
                owner = j
            break
        if owner is not None:
            oind = _indent(lines[owner])
            body = [lines[owner]]
            for nxt in lines[owner + 1:]:
                if nxt.strip() and _indent(nxt) <= oind:
                    break
                body.append(nxt)
            return _dedent(body)
        body = []
        for nxt in lines[i + 1:]:
            if nxt.strip() and _indent(nxt) < ind:
                break
            body.append(nxt)
        return _dedent(body)
    for i, line in enumerate(lines):
        m = _SECTION_RE.match(line)
        if m and m.group(3) == anchor:
            level = len(m.group(1))
            body = []
            for nxt in lines[i + 1:]:
                m2 = _SECTION_RE.match(nxt)
                # Stop at the next section of the SAME or SHALLOWER level; a
                # deeper subsection is part of this section's content, and
                # breaking on it would truncate the parameters it holds.
                if (m2 and len(m2.group(1)) <= level) or _ATSECTION_RE.match(nxt):
                    break
                body.append(nxt)
            return _dedent(body)
    for i, line in enumerate(lines):
        m = _TAGANCHOR_RE.match(line)
        if m and m.group(2) == anchor:
            body = []
            for nxt in lines[i + 1:]:
                if _TAGANCHOR_RE.match(nxt):
                    break
                body.append(nxt)
            return _dedent(body)
    return None


def _dedent(lines: list[str]) -> str:
    real = [l for l in lines if l.strip()]
    if not real:
        return ""
    cut = min(_indent(l) for l in real)
    return "\n".join(l[cut:] if len(l) >= cut else l for l in lines)


def resolve_includes(text: str, corpus: HelpCorpus, base_dir: str,
                     depth: int = 0, seen: frozenset[str] = frozenset(),
                     stats: dict | None = None, self_key: str | None = None) -> str:
    """Expand every ``:include target:`` in place, recursively.

    Unresolvable targets are replaced by a marker rather than dropped -- a
    silently-dropped include is an undercount that looks like a clean parse.
    """
    if depth >= _MAX_INCLUDE_DEPTH:
        return text
    out: list[str] = []
    for line in text.splitlines():
        m = _INCLUDE_RE.match(line)
        if not m:
            out.append(line)
            continue
        pad, target = m.group(1), m.group(2).strip()
        # Targets whose anchor contains colons are shipped quoted:
        #   :include "/nodes/lop/rendergeometrysettings#karma:object:foo":
        if len(target) > 1 and target[0] == target[-1] and target[0] in "\"'":
            target = target[1:-1].strip()
        if stats is not None:
            stats["seen"] = stats.get("seen", 0) + 1
        page_ref, _, anchor = target.partition("#")
        # Colons inside an anchor are backslash-escaped in the shipped source:
        #   :include rendervar#karma\:plane\:utilitypathexpression:
        anchor = anchor.strip("/").strip().replace("\\:", ":")
        # ':include #anchor:' -- same-page reference, no page component.
        key = self_key if not page_ref.strip() else corpus.resolve_path(page_ref, base_dir)
        if key is None:
            if stats is not None:
                stats["unresolved"] = stats.get("unresolved", 0) + 1
                stats.setdefault("unresolved_targets", set()).add(target)
            out.append("%s<!-- UNRESOLVED-INCLUDE %s -->" % (pad, target))
            continue
        if key in seen:
            out.append("%s<!-- CYCLIC-INCLUDE %s -->" % (pad, target))
            continue
        body = corpus.pages[key]
        if anchor:
            blk = _anchored_block(body, anchor)
            if blk is None:
                if stats is not None:
                    stats["unresolved_anchor"] = stats.get("unresolved_anchor", 0) + 1
                    stats.setdefault("unresolved_targets", set()).add(target)
                out.append("%s<!-- UNRESOLVED-ANCHOR %s -->" % (pad, target))
                continue
            body = blk
        else:
            body = _strip_page_furniture(body)
        if stats is not None:
            stats["resolved"] = stats.get("resolved", 0) + 1
        body = resolve_includes(body, corpus, key.rsplit("/", 1)[0],
                                depth + 1, seen | {key}, stats)
        out.extend(pad + l if l.strip() else l for l in body.splitlines())
    return "\n".join(out)


def _strip_page_furniture(text: str) -> str:
    """Drop directives/title from an included whole page; keep its content."""
    keep = []
    for line in text.splitlines():
        if line.startswith("#") and _DIRECTIVE_RE.match(line):
            continue
        if _TITLE_RE.match(line):
            continue
        keep.append(line)
    return "\n".join(keep)


# --------------------------------------------------------------------------
# Section + parameter extraction
# --------------------------------------------------------------------------
def at_sections(text: str) -> dict[str, str]:
    """Split the ``@inputs`` / ``@parameters`` / ``@outputs`` trailer."""
    out: dict[str, list[str]] = {}
    cur: str | None = None
    for line in text.splitlines():
        m = _ATSECTION_RE.match(line)
        if m:
            cur = m.group(1).lower()
            out.setdefault(cur, [])
            continue
        if cur is not None:
            out[cur].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def _unwrap_boxes(text: str) -> str:
    """Flatten ``:box:``/``:warning:`` wrappers so their children sit at the
    parameter indent. The wrapper is presentation; the entries inside are the
    documentation."""
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        m = _BOXLIKE_RE.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        ind = _indent(lines[i])
        tail = (m.group(3) or "").strip()
        block: list[str] = []
        j = i + 1
        while j < len(lines):
            if lines[j].strip() and _indent(lines[j]) <= ind:
                break
            block.append(lines[j])
            j += 1
        if tail:
            # ":warning:Old network:" -- the tail is itself an entry label.
            out.append(" " * ind + tail)
        out.extend(l[min(_indent(l), ind + 4) - ind:] if l.strip() else l
                   for l in _dedent(block).splitlines())
        i = j
    return "\n".join(out)


def parse_entries(section_text: str) -> list[dict]:
    """Parse a parameter section into entries.

    An entry is ``Label:`` on its own line, followed by a more-indented body.
    Entries at the section's MINIMUM indent are parameters; deeper ones are
    menu values / sub-parameters and are folded into the parent's description
    (they document the parameter, they are not separate parameters).

    ``#id: <name>`` inside the body is the INTERNAL parameter name -- the only
    field in the corpus directly comparable to ``hou.ParmTemplate.name()``.
    """
    text = _unwrap_boxes(section_text)
    lines = [l for l in text.splitlines()]
    cand = [(i, l) for i, l in enumerate(lines) if _ENTRY_RE.match(l)]
    if not cand:
        return []
    base = min(_indent(l) for _, l in cand)
    entries: list[dict] = []
    for pos, (i, line) in enumerate(cand):
        if _indent(line) != base:
            continue
        m = _ENTRY_RE.match(line)
        label = clean_markup(m.group(2))
        if not label or label.startswith("<!--"):
            continue
        body: list[str] = []
        for nxt in lines[i + 1:]:
            if nxt.strip() and _indent(nxt) <= base:
                break
            body.append(nxt)
        pids: list[str] = []
        desc: list[str] = []
        for b in body:
            got = ids_on_line(b)
            if got is not None:
                # Only the entry's OWN ids, not those of nested menu values.
                if _indent(b) <= base + 8:
                    pids.extend(g for g in got if g not in pids)
                continue
            desc.append(b)
        entries.append({
            "label": label,
            "id": pids[0] if pids else None,
            "ids": pids,
            "description": clean_markup(" ".join(_dedent(desc).split())),
        })
    return entries


# --------------------------------------------------------------------------
# Whole-page structure
# --------------------------------------------------------------------------
def canonical_type_names(help_key: str, directives: dict[str, str]) -> list[str]:
    """Every type spelling this page could legitimately be keyed by.

    The help system mangles ``::`` -> ``--`` and ``::<version>`` -> ``-<version>``
    in filenames, but pages disagree about whether ``#internal:`` carries the
    version (measured, both forms present). Emitting the candidate set and
    letting the live catalogue decide is honest; picking one and hoping is not.
    """
    base = help_key.rsplit("/", 1)[-1]
    cands: list[str] = []

    fname = base
    ver = None
    mv = re.search(r"-(\d+(?:\.\d+)*)$", fname)
    if mv:
        ver = mv.group(1)
        fname = fname[: mv.start()]
    ns_f, _, nm_f = fname.rpartition("--")
    from_file = "::".join([p for p in (ns_f or None, nm_f, ver) if p])
    cands.append(from_file)

    internal = directives.get("internal")
    if internal:
        ns = directives.get("namespace")
        vr = directives.get("version")
        parts = [internal]
        if ns and not internal.startswith(ns + "::"):
            parts = [ns, internal]
        full = "::".join(parts)
        if vr and not full.endswith("::" + vr):
            full = full + "::" + vr
        cands.append(full)
        if ver and not full.endswith("::" + ver):
            cands.append(full + "::" + ver)
    seen: set[str] = set()
    return [c for c in cands if c and not (c in seen or seen.add(c))]


def parse_page(help_key: str, corpus: HelpCorpus, stats: dict | None = None) -> dict:
    """Full structured record for one help page, includes resolved."""
    raw = corpus.pages[help_key]
    directives = page_directives(raw)
    base_dir = help_key.rsplit("/", 1)[0]
    resolved = resolve_includes(raw, corpus, base_dir, stats=stats)
    secs = at_sections(resolved)
    params = parse_entries(secs.get("parameters", ""))
    inputs = parse_entries(secs.get("inputs", ""))
    outputs = parse_entries(secs.get("outputs", ""))

    body = resolved.split("@parameters")[0]
    overview = ""
    mo = re.search(r"^==\s*Overview\s*==.*?$(.*?)(?=^==|^@|\Z)", body, re.S | re.M)
    if mo:
        overview = clean_markup(" ".join(mo.group(1).split()))

    return {
        "help_key": help_key,
        "source": corpus.origin.get(help_key, help_key),
        "context": directives.get("context"),
        "page_type": directives.get("type"),
        "title": page_title(raw),
        "summary": page_summary(raw),
        "overview": overview,
        "since": directives.get("since"),
        "directives": directives,
        "type_candidates": canonical_type_names(help_key, directives),
        "parameters": params,
        "inputs": inputs,
        "outputs": outputs,
        "raw_bytes": len(raw.encode("utf-8")),
        "resolved_bytes": len(resolved.encode("utf-8")),
        "used_includes": bool(_INCLUDE_RE.search(raw) or ":include" in raw),
        "mentions_deprecated": bool(re.search(r"deprecat", raw, re.I)),
        "mentions_deprecated_resolved": bool(re.search(r"deprecat", resolved, re.I)),
    }


def is_node_page(help_key: str, text: str) -> bool:
    """Is this help key a page ABOUT A NODE, or corpus furniture?

    Neither available convention works alone, both verified against the corpus:

      * ``#type: node`` alone EXCLUDES ``nodes/lop/bakeskinning``, a real 562-byte
        node page that carries no directives whatsoever.
      * the ``_``-prefix convention alone INCLUDES ``cop2/maskparms``,
        ``cop2/pixelparms`` and ``cop2/localvars``, which are include fragments
        with no underscore -- counting them would credit coverage to three
        types that do not exist.

    So: exclude anything that DECLARES itself an include, exclude the
    ``_``-prefixed fragments and the context index, keep the rest.
    """
    base = help_key.rsplit("/", 1)[-1]
    if base.startswith("_") or base == "index":
        return False
    d = page_directives(text)
    t = d.get("type", "").strip()
    if t and t != "node":
        return False
    return True


def node_pages(corpus: HelpCorpus, contexts=CONTEXTS) -> list[str]:
    """Help keys that are node pages within the given contexts."""
    out = []
    for ctx in contexts:
        pref = "nodes/%s/" % ctx
        for k in corpus.pages:
            if not k.startswith(pref) or "/" in k[len(pref):]:
                continue
            if is_node_page(k, corpus.pages[k]):
                out.append(k)
    return sorted(out)


def all_node_contexts(corpus: HelpCorpus) -> list[str]:
    """Every ``nodes/<ctx>/`` directory in the shipped corpus.

    Needed because network managers (chopnet, dopnet, matnet, ...) appear in the
    LOP/COP catalogues but are documented once, centrally, at
    ``nodes/manager/<name>``. Searching only the three contexts under test would
    report 36 manager types as undocumented when their semantics are shipped.
    """
    ctxs = set()
    for k in corpus.pages:
        if k.startswith("nodes/"):
            rest = k[len("nodes/"):]
            if "/" in rest:
                ctxs.add(rest.split("/", 1)[0])
    return sorted(ctxs)
