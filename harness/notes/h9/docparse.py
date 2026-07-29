"""H9 producer 2 of 4 -- the Houdini help-markup parser.

Parses one page of the shipped node reference into structure. No blobs.

    C:\\Program Files\\Side Effects Software\\Houdini 22.0.368\\houdini\\help\\nodes.zip

PAGE GRAMMAR (observed, 22.0.368)
    = Title =                     the human label
    #type: node                   directive block; order and position vary
    #context: lop                 the node type category
    #namespace: kinefx            optional
    #internal: sopcharacterimport the internal type name
    #version: 2.0                 optional
    \"\"\"summary\"\"\"               the one-line summary
    == Section ==                 prose sections
    @parameters                   the parameter block
    @inputs / @outputs / @related trailing blocks

PARAMETER BLOCK GRAMMAR
    ~~~ Folder ~~~                folder heading
    :include _primpattern:        pulls another file's parameters in wholesale
    :include _sampling#blk/:      pulls one #id-tagged block; trailing / means
                                  "contents only"
    Label:                        a parameter, at the block's base indent
        #id: a, b, c              one label may carry several real parm names
        prose...                  its description
        Menu Item:                deeper indent -- a menu value, NOT a parameter
            prose...

WHY INCLUDES ARE RESOLVED
    `:include _primpattern:` is how `primpattern` -- a real, live parameter on
    dozens of LOPs -- is documented. A parser that does not follow includes reports
    those nodes as undocumented for that parameter and then reports a doc-vs-runtime
    disagreement that is an artifact of the parser, not of the documentation. Every
    resolved parameter records which file it came from.

NAME RESOLUTION IS TWO-SOURCED ON PURPOSE
    Neither the header nor the filename is reliable alone:
      lop/cache.txt              header #internal cache + #version 2.0 -> cache::2.0  (filename silent)
      lop/backgroundplate-2.0.txt header omits #version                                (filename carries it)
    So both are decoded and the union is offered to the matcher.
"""
import os
import re
import zipfile

ZIP_PATH = (
    r"C:\Program Files\Side Effects Software\Houdini 22.0.368\houdini\help\nodes.zip"
)

_DIRECTIVE = re.compile(r"^#([A-Za-z_]+):\s*(.*)$")
_TITLE = re.compile(r"^=\s+(.*?)\s+=\s*$")
_SECTION = re.compile(r"^@([a-zA-Z_]+)\s*(.*)$")
_FOLDER = re.compile(r"^~~~\s*(.*?)\s*(?:~~~)?\s*$")
_INCLUDE = re.compile(r"^:include\s+(.+?):\s*$")
# The '::' prefix marks a render-property parameter on the karma settings pages
# ('::Enable Motion Blur:' -> '#id: karma:object:mblur'). Excluding a leading colon
# outright cost lop/rendergeometrysettings 82 of its 84 declared ids.
_LABELLINE = re.compile(
    r"^(?P<pfx>::)?(?P<label>[^\s#:][^\n]*?):\s*(?:\((?P<ctx>[^)]*)\))?\s*$"
)
_HEADING = re.compile(r"^={2,}\s*(.*?)\s*={2,}")

# Houdini help markup -> plain text
_SUB = [
    (re.compile(r"\[([^\[\]|]+)\|[^\[\]]*\]"), r"\1"),      # [Label|target]
    (re.compile(r"\[(?:Node|Image|Smallicon|Icon|Wp):([^\[\]]*)\]"), r"\1"),
    (re.compile(r"\[([^\[\]]+)\]"), r"\1"),
    (re.compile(r"__([^_]+)__"), r"\1"),                     # bold
    (re.compile(r"''([^']+)''"), r"\1"),                     # italic
    (re.compile(r"\(\(([^)]+)\)\)"), r"\1"),                 # ((Ctrl))
    (re.compile(r"`([^`]*)`"), r"\1"),                       # code
]


def strip_markup(text):
    for pat, rep in _SUB:
        text = pat.sub(rep, text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _norm(line):
    """Tabs to 4 spaces so indent arithmetic is stable."""
    out = []
    for ch in line:
        if ch == "\t":
            out.append(" " * (4 - len(out) % 4))
        else:
            out.append(ch)
    return "".join(out).rstrip()


def _indent(line):
    return len(line) - len(line.lstrip(" "))


class HelpZip:
    """Lazy reader over nodes.zip with an include resolver."""

    def __init__(self, path=ZIP_PATH):
        self.path = path
        self._zip = zipfile.ZipFile(path)
        self._names = {i.filename for i in self._zip.infolist() if not i.is_dir()}
        self._cache = {}

    def names(self, prefix=None):
        if prefix is None:
            return sorted(self._names)
        return sorted(n for n in self._names if n.startswith(prefix))

    def size(self, name):
        return self._zip.getinfo(name).file_size

    def read(self, name):
        if name not in self._cache:
            if name not in self._names:
                return None
            self._cache[name] = self._zip.read(name).decode("utf-8", "replace")
        return self._cache[name]

    def resolve_include(self, target, from_ctx, from_file=None):
        """':include _sampling#sampling_block/:' -> (filename, block_id, contents_only).

        Four target shapes occur in 22.0.368:
            _primpattern            same context directory
            #optioncount            a block in THIS file
            ../vop/kma_physicallens another context, relative
            /nodes/sop/foo          absolute inside the node reference
        Anything else (e.g. /vex/snippets) points outside nodes.zip and is
        reported unresolved rather than silently dropped.
        """
        target = target.strip().strip('"').strip("'")  # karma pages quote their targets
        contents_only = target.endswith("/")
        target = target.rstrip("/")
        block = None
        if "#" in target:
            target, block = target.split("#", 1)
        target = target.strip()
        if not target:
            return (from_file, block, contents_only) if from_file else (None, block, contents_only)
        if target.startswith("/nodes/"):
            rel = target[len("/nodes/"):]
        elif target.startswith("/"):
            rel = None  # points outside the node reference; unresolvable here
        elif target.startswith("../") or "/" in target:
            rel = os.path.normpath("%s/%s" % (from_ctx, target)).replace("\\", "/")
        else:
            rel = "%s/%s" % (from_ctx, target)
        if rel is None:
            return None, block, contents_only
        fname = rel + ".txt"
        if fname not in self._names:
            # cross-context bare target: lop/shotoutput says ':include usd#f:' and
            # means out/usd.txt. Accept ONLY when exactly one context has that page;
            # an ambiguous name stays unresolved rather than being guessed.
            leaf = os.path.basename(rel) + ".txt"
            hits = [n for n in self._names if n.endswith("/" + leaf)]
            if len(hits) == 1:
                return hits[0], block, contents_only
            return None, block, contents_only
        return fname, block, contents_only


def split_sections(text):
    """Return (preamble_lines, {section_name: [lines]}) split on '@section'."""
    lines = [_norm(l) for l in text.splitlines()]
    pre, sections, cur = [], {}, None
    for line in lines:
        m = _SECTION.match(line)
        if m and _indent(line) == 0:
            cur = m.group(1).lower()
            sections.setdefault(cur, [])
            trailing = m.group(2).strip()
            if trailing:
                sections[cur].append("    " + trailing)
            continue
        (sections[cur] if cur else pre).append(line)
    return pre, sections


def parse_header(pre_lines):
    directives, title, summary = {}, None, None
    buf, in_doc = [], False
    for line in pre_lines:
        if in_doc:
            if '"""' in line:
                buf.append(line.split('"""')[0])
                summary = strip_markup(" ".join(buf).strip())
                in_doc = False
            else:
                buf.append(line)
            continue
        stripped = line.strip()
        if stripped.startswith('"""') and summary is None:
            body = stripped[3:]
            if body.endswith('"""') and len(stripped) > 5:
                summary = strip_markup(body[:-3].strip())
            else:
                in_doc, buf = True, [body]
            continue
        m = _TITLE.match(stripped)
        if m and title is None:
            title = strip_markup(m.group(1))
            continue
        m = _DIRECTIVE.match(stripped)
        if m and _indent(line) == 0:
            directives.setdefault(m.group(1).lower(), m.group(2).strip())
    return directives, title, summary


def parse_prose_sections(pre_lines):
    """'== Overview ==' headings -> {heading: text}. Kept short; this is context, not the payload."""
    out, cur, buf = {}, None, []
    for line in pre_lines:
        m = _HEADING.match(line.strip())
        if m:
            if cur and buf:
                out[cur] = strip_markup(" ".join(buf))[:2000]
            cur, buf = strip_markup(m.group(1)), []
            continue
        if cur is not None:
            s = line.strip()
            if s and not s.startswith("#") and not s.startswith(":"):
                buf.append(s)
    if cur and buf:
        out[cur] = strip_markup(" ".join(buf))[:2000]
    return out


def parse_parm_block(lines, helpzip, ctx, source, depth=0, seen=None):
    """Walk a @parameters body into parameter records.

    Returns (records, includes_seen, unresolved_includes).
    """
    seen = seen or set()
    records, includes, unresolved = [], [], []
    body = [l for l in lines]
    nonblank = [l for l in body if l.strip()]
    if not nonblank:
        return records, includes, unresolved

    # SEGMENTATION -- the fix for a defect that cost 145 of karmarendersettings' 153
    # documented parameter ids.
    #
    # A single base indent for the whole block is wrong, because one page mixes depths:
    # lop/karmarendersettings puts 8 parameters at indent 0 and then 142 more at indent
    # 4+ underneath '== Rendering == (rendering_tab)' headings. Taking the shallowest
    # label line gives base=0, and every deeper parameter then falls through the walk
    # silently -- no record, no warning, no counter.
    #
    # So the block is split at its structural markers (headings and '~~~ folder ~~~')
    # and EACH SEGMENT computes its own base from its own label lines. A segment with
    # no label lines at all still gets a base, so a block consisting only of
    # ':include' directives -- cop/rop_image and cop2/invert -- is processed instead of
    # bailing out with zero parameters.
    segments, cur_folder, buf = [], None, []
    for line in body:
        s = line.strip()
        if not s:
            buf.append(line)
            continue
        mh, mf = _HEADING.match(s), _FOLDER.match(s)
        if mh or mf:
            if buf:
                segments.append((cur_folder, buf))
            cur_folder = strip_markup((mh or mf).group(1))
            buf = []
            continue
        buf.append(line)
    if buf:
        segments.append((cur_folder, buf))

    for folder, seg in segments:
        r, i_, u_ = _parse_segment(seg, helpzip, ctx, source, depth, seen, folder)
        records.extend(r)
        includes.extend(i_)
        unresolved.extend(u_)
    return records, includes, unresolved


def _parse_segment(body, helpzip, ctx, source, depth, seen, folder):
    """One run of a @parameters block, walked by containment rather than by a base indent.

    THERE IS NO SINGLE BASE INDENT, and assuming one loses parameters. Inside one
    segment of lop/editprototypes, 'Prim Path:' and 'Primitive Type:' sit at indent 4
    while 'Dive-Target Mask:' sits at indent 0, with no marker between them. Any single
    base drops one group or the other.

    The rule that actually holds: a label line is a PARAMETER when it is not contained
    in another label's body, and a label line IS contained when it follows a label at a
    strictly smaller indent. Menu values are exactly the contained case. So each label
    is bounded by its OWN indent, and the walk jumps past the body it just consumed --
    which means a nested label is never visited at this level and needs no test.
    """
    records, includes, unresolved = [], [], []
    if not any(l.strip() for l in body):
        return records, includes, unresolved

    i = 0
    while i < len(body):
        line = body[i]
        if not line.strip():
            i += 1
            continue
        ind = _indent(line)
        stripped = line.strip()

        if True:
            m = _INCLUDE.match(stripped)
            if m:
                target = m.group(1)
                includes.append(target)
                fname, block, _contents = helpzip.resolve_include(target, ctx, source)
                key = (fname, block)
                if fname is None or key in seen or depth >= 3:
                    if fname is None:
                        unresolved.append(target)
                    i += 1
                    continue
                seen.add(key)
                sub_text = helpzip.read(fname)
                sub_lines = _select_block([_norm(l) for l in sub_text.splitlines()], block)
                if sub_lines is None:
                    # the anchor does not exist in the target. Importing the whole file
                    # here is how foreign parameters got credited to a node.
                    unresolved.append("%s#%s [block_not_found]" % (fname, block))
                    i += 1
                    continue
                # an include file may itself carry an @parameters section
                _pre, _secs = split_sections("\n".join(sub_lines))
                target_lines = _secs.get("parameters", sub_lines)
                sub_records, sub_inc, sub_unres = parse_parm_block(
                    target_lines, helpzip, ctx, fname, depth + 1, seen
                )
                for r in sub_records:
                    r.setdefault("folder", folder)
                records.extend(sub_records)
                includes.extend(sub_inc)
                unresolved.extend(sub_unres)
                i += 1
                continue
            m = _LABELLINE.match(stripped)
            if m:
                label = strip_markup(m.group("label"))
                j = i + 1
                sub = []
                while j < len(body) and (not body[j].strip() or _indent(body[j]) > ind):
                    sub.append(body[j])
                    j += 1
                ids, desc, subdirs, body_unres = _parse_parm_body(
                    sub, helpzip, ctx, source, depth
                )
                unresolved.extend(body_unres)
                records.append(
                    {
                        "label": label,
                        "ids": ids,
                        "description": desc,
                        "folder": folder,
                        "doc_source": source,
                        "directives": subdirs,
                    }
                )
                i = j
                continue
        i += 1
    return records, includes, unresolved


_HEADING_ANCHOR = re.compile(r"^={2,}\s*(?P<title>.*?)\s*={2,}\s*\((?P<anchor>[^)]+)\)\s*$")


def _select_block(lines, block_id):
    """Pick the sub-block a ':include target#anchor:' asks for.

    TWO anchor forms exist in 22.0.368 and both must be understood:
        #id: rendering_block          a directive-tagged block
        == Rendering == (rendering_tab)   a heading-tagged block

    RETURNS None WHEN THE ANCHOR IS ABSENT. It used to return the whole file, which
    is how lop/karma -- asking karmarendersettings for nine heading anchors this
    function could not see -- pulled that entire page in nine times: 80 parameter
    records of which 66 were duplicates and 73 were sourced from a page that never
    documented lop/karma. A silent fallback to "everything" turns a missed anchor
    into fabricated grounding, so the miss is now explicit and gets counted.
    """
    if not block_id:
        return lines

    def run_after(idx, owner_indent):
        out = []
        for k in range(idx + 1, len(lines)):
            if lines[k].strip() and _indent(lines[k]) <= owner_indent:
                break
            out.append(lines[k])
        return out

    for idx, line in enumerate(lines):
        m = _DIRECTIVE.match(line.strip())
        if m and m.group(1).lower() == "id" and m.group(2).strip() == block_id:
            owner_indent = _indent(lines[idx])
            out = []
            for k in range(idx + 1, len(lines)):
                if lines[k].strip() and _indent(lines[k]) < owner_indent:
                    break
                out.append(lines[k])
            return out
    for idx, line in enumerate(lines):
        m = _HEADING_ANCHOR.match(line.strip())
        if m and m.group("anchor").strip() == block_id:
            return run_after(idx, _indent(lines[idx]))
    return None


def _parse_parm_body(sub_lines, helpzip=None, ctx=None, source=None, depth=0):
    """A parameter's own body: its #id(s), its prose, and any include nested inside it.

    A body-level include (`:include cache#behavior/:` on kinefx::sopcharacterimport)
    carries ANOTHER node's prose for the same concept. Its text is inlined; its
    `#id` is deliberately NOT adopted, because a parameter name valid on the source
    node is not evidence of a parameter name on this one. Label matching recovers
    the real id where it exists; inventing it here would be a fabricated agreement.
    """
    ids, desc_lines, directives, unresolved = [], [], {}, []
    for line in sub_lines:
        stripped = line.strip()
        m = _INCLUDE.match(stripped)
        if m and helpzip is not None and depth < 3:
            fname, block, _co = helpzip.resolve_include(m.group(1), ctx, source)
            if fname is None:
                unresolved.append(m.group(1))
                continue
            sub = helpzip.read(fname)
            if sub is None:
                unresolved.append(m.group(1))
                continue
            picked = _select_block([_norm(l) for l in sub.splitlines()], block)
            if picked is None:
                unresolved.append("%s#%s [block_not_found]" % (fname, block))
                continue
            inner_ids, inner_desc, _d, inner_unres = _parse_parm_body(
                picked, helpzip, ctx, fname, depth + 1
            )
            unresolved.extend(inner_unres)
            if inner_desc:
                desc_lines.append(inner_desc)
            continue
        m = _DIRECTIVE.match(stripped)
        if m:
            key, val = m.group(1).lower(), m.group(2).strip()
            directives[key] = val
            if key == "id":
                for piece in re.split(r"[,\s]+", val):
                    piece = piece.strip()
                    if piece:
                        ids.append(piece)
            continue
        if stripped:
            desc_lines.append(stripped)
    return ids, strip_markup(" ".join(desc_lines)), directives, unresolved


def parse_named_block(lines):
    """@inputs / @outputs style: 'name:' then indented prose."""
    out = {}
    nonblank = [l for l in lines if l.strip()]
    if not nonblank:
        return out
    base = min(_indent(l) for l in nonblank)
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() and _indent(line) == base:
            m = _LABELLINE.match(line.strip())
            if m:
                name = strip_markup(m.group("label"))
                j, buf = i + 1, []
                while j < len(lines) and (not lines[j].strip() or _indent(lines[j]) > base):
                    if lines[j].strip():
                        buf.append(lines[j].strip())
                    j += 1
                out[name] = strip_markup(" ".join(buf))[:600]
                i = j
                continue
        i += 1
    return out


def decode_filename(filename):
    """'lop/kinefx--sopcharacterimport.txt' -> ('lop', 'kinefx::sopcharacterimport')."""
    ctx = filename.split("/", 1)[0]
    base = os.path.splitext(os.path.basename(filename))[0]
    name = base.replace("--", "::")
    m = re.match(r"^(.*?)-(\d+(?:\.\d+)*)$", name)
    if m:
        name = "%s::%s" % (m.group(1), m.group(2))
    return ctx, name


def canonical_names(directives, filename):
    """Every defensible spelling of this page's node type. The matcher tries all."""
    ctx, from_file = decode_filename(filename)
    internal = directives.get("internal")
    ns = directives.get("namespace")
    ver = directives.get("version")

    header_name = None
    if internal:
        header_name = "%s::%s" % (ns, internal) if ns else internal
        if ver:
            header_name = "%s::%s" % (header_name, ver)

    # ORDER IS THE ATTRIBUTION RULE, not a convenience.
    # 14 LOP families ship one page for two live types (cache and cache::2.0 are both
    # live). An explicit `#version: 2.0` in the header is the page declaring WHICH
    # sibling it documents, so it outranks the filename. Without this, lop/cache.txt
    # binds to v1 and the version the page actually describes is scored ungrounded.
    cands = []
    if ver and header_name:
        cands.append(header_name)
    cands.append(from_file)
    if header_name:
        cands.append(header_name)
        if ns:
            cands.append("%s::%s" % (ns, internal))
        cands.append(internal)
    # filename may carry a version the header omits, and vice versa
    base_nover = re.sub(r"::\d+(\.\d+)*$", "", from_file)
    cands.append(base_nover)
    out, seen = [], set()
    for c in cands:
        if c and c.lower() not in seen:
            seen.add(c.lower())
            out.append(c)
    return ctx, out


def parse_page(helpzip, filename):
    text = helpzip.read(filename)
    if text is None:
        return None
    pre, sections = split_sections(text)
    directives, title, summary = parse_header(pre)
    ctx, cands = canonical_names(directives, filename)
    parm_lines = sections.get("parameters", [])
    parms, includes, unresolved = parse_parm_block(parm_lines, helpzip, ctx, filename)
    return {
        "doc_path": filename,
        "doc_bytes": helpzip.size(filename),
        "context_dir": ctx,
        "directives": directives,
        "title": title,
        "summary": summary,
        "candidate_type_names": cands,
        "prose_sections": parse_prose_sections(pre),
        "parameters": parms,
        "includes": includes,
        "unresolved_includes": unresolved,
        "inputs": parse_named_block(sections.get("inputs", [])),
        "outputs": parse_named_block(sections.get("outputs", [])),
        "related": [
            strip_markup(l.strip().lstrip("- "))
            for l in sections.get("related", [])
            if l.strip()
        ],
        "has_parameters_section": "parameters" in sections,
    }
