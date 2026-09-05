"""Source ownership ratchet plus Qt-free applier/compositor controls.

The measured CENSUS sites are grandfathered, not a blanket allowance to add
348 owners. A deletion cannot mask a novel untagged site at the same count.
Real QWidget/layout assertions live in test_panel_rhythm_docking.py.
"""

import ast
from collections import Counter
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tokenize

import pytest

from synapse.panel import compositor
from synapse.panel.designsystem import qss, rhythm
from synapse.panel.manifests import get_manifest


ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "python/synapse/panel"
RESIDUAL = "harness/panel_pd/RESIDUAL.json"
CENSUS = "harness/panel_pd/runs/2026-09-04/rhythm_census.json"
METHODS = {
    "setSpacing": "spacing", "setContentsMargins": "spacing",
    "setStyleSheet": "inline_styles",
    "setHorizontalSpacing": "grid_spacing", "setVerticalSpacing": "grid_spacing",
}
HEX = re.compile(r"#[0-9a-fA-F]{6}(?![0-9a-zA-Z_])")


def _identity(path, kind, source, scope=""):
    # AST normalization survives reformatting/line shifts, but not a new owner
    # or expression. Raw hex uses the complete source line, including comments.
    text = (ast.dump(ast.parse(source), include_attributes=False)
            if kind != "hex_sites" else source.strip())
    return path, kind, scope, text


def _scan(source, path):
    tags = {}
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            match = re.search(r"#\s*rhythm-exempt:\s*(\S.*)", token.string)
            if match:
                tags[token.start[0]] = match.group(1)
    sites = []

    class Calls(ast.NodeVisitor):
        scope = ()

        def visit_scope(self, node):
            before = self.scope
            self.scope += (node.name,)
            self.generic_visit(node)
            self.scope = before

        visit_ClassDef = visit_FunctionDef = visit_AsyncFunctionDef = visit_scope

        def visit_Call(self, node):
            if isinstance(node.func, ast.Attribute) and node.func.attr in METHODS:
                kind = METHODS[node.func.attr]
                key = _identity(path, kind, ast.get_source_segment(source, node),
                                ".".join(self.scope))
                sites.append((key, node.lineno, bool(tags.get(node.lineno))))
            self.generic_visit(node)

    Calls().visit(ast.parse(source, filename=path))
    lines = source.splitlines()
    for match in HEX.finditer(source):
        line = source.count("\n", 0, match.start()) + 1
        sites.append((_identity(path, "hex_sites", lines[line - 1]),
                      line, bool(tags.get(line))))
    return sites


def _seed(census):
    allowed = Counter()
    for file in census["files"]:
        assert not file["errors"], file["path"]
        for kind in ("spacing", "inline_styles", "hex_sites", "grid_spacing"):
            for site in file[kind]:
                allowed[_identity(file["path"], kind, site["source"],
                                  site.get("scope", ""))] += 1
    return allowed


def _check(sites, allowed, ceiling, grid_ceiling=4):
    untagged = Counter(key for key, _, exempt in sites if not exempt)
    novel = untagged - allowed
    assert not novel, "new untagged rhythm owners: %r" % list(novel)
    grid = sum(key[1] == "grid_spacing" for key, _, _ in sites)
    residual = len(sites) - grid
    assert residual <= ceiling, "residual %d exceeds ceiling %d" % (residual, ceiling)
    assert grid <= grid_ceiling, "grid residual exceeds its separate ceiling"


def _check_ceiling(current, previous):
    for key in ("allowed_residual", "allowed_grid_residual"):
        assert type(current[key]) is int and 0 <= current[key] <= previous[key], (
            "residual ceiling may only decrease: %s" % key)


def test_panel_rhythm_owner_ratchet():
    limits = json.loads((ROOT / RESIDUAL).read_text(encoding="utf-8"))
    assert limits["census"] == CENSUS
    census = json.loads((ROOT / CENSUS).read_text(encoding="utf-8"))
    assert census["measurement_complete"] and not census["errors"]
    assert limits["seed_counts"] == {k: census["totals"][k] for k in limits["seed_counts"]}
    seed_total = sum(limits["seed_counts"].values())
    _check_ceiling(limits, {"allowed_residual": seed_total,
                           "allowed_grid_residual": census["totals"]["grid_spacing_sites"]})
    sites = []
    for path in sorted(PANEL.rglob("*.py")):
        if "designsystem" not in path.relative_to(PANEL).parts:
            sites.extend(_scan(path.read_text(encoding="utf-8"),
                               path.relative_to(ROOT).as_posix()))
    _check(sites, _seed(census), limits["allowed_residual"],
           limits["allowed_grid_residual"])


def test_residual_cannot_increase_against_git_history():
    current = json.loads((ROOT / RESIDUAL).read_text(encoding="utf-8"))
    # Check working copy -> latest commit -> its predecessor, so committing a
    # raised ceiling does not hide the increase by making HEAD the new oracle.
    revisions = subprocess.check_output(
        ["git", "log", "-2", "--format=%H", "--", RESIDUAL], cwd=ROOT,
        text=True).splitlines()
    for rev in revisions:
        previous = json.loads(subprocess.check_output(
            ["git", "show", "%s:%s" % (rev, RESIDUAL)], cwd=ROOT, text=True))
        _check_ceiling(current, previous)
        current = previous


@pytest.mark.parametrize("method", tuple(METHODS))
def test_new_owner_cannot_spend_a_deleted_site(method):
    original = _scan("old.%s(4)" % method, "fixture.py")
    allowed = Counter(key for key, _, _ in original)
    changed = _scan("new.%s(4)" % method, "fixture.py")
    _check(original, allowed, 1)
    with pytest.raises(AssertionError, match="new untagged"):
        _check(changed, allowed, 1)


def test_new_hex_and_duplicate_existing_call_are_rejected():
    source = "w.setSpacing(4)\n"
    allowed = Counter(key for key, _, _ in _scan(source, "fixture.py"))
    for extra in (source, "color = '" + "#" + "123abc" + "'\n"):
        with pytest.raises(AssertionError, match="new untagged"):
            _check(_scan(source + extra, "fixture.py"), allowed, 3)


@pytest.mark.parametrize("source", [
    'w.setSpacing(4) # rhythm-exempt: ',
    'w.setSpacing(4); text = "# rhythm-exempt: not a comment"',
    'w.setSpacing(\n 4) # rhythm-exempt: wrong line',
])
def test_only_real_same_line_reason_exempts(source):
    with pytest.raises(AssertionError, match="new untagged"):
        _check(_scan(source, "fixture.py"), Counter(), 1)


def test_reasoned_exemption_still_counts_toward_residual():
    sites = _scan("w.setSpacing(0) # rhythm-exempt: fixed band seam", "fixture.py")
    _check(sites, Counter(), 1)
    with pytest.raises(AssertionError, match="exceeds ceiling"):
        _check(sites, Counter(), 0)
    with pytest.raises(AssertionError, match="only decrease"):
        _check_ceiling({"allowed_residual": 2, "allowed_grid_residual": 0},
                       {"allowed_residual": 1, "allowed_grid_residual": 0})


def test_scan_ignores_call_lookalikes_but_counts_hex_comments():
    assert not _scan('text="setSpacing(3)"\n# w.setStyleSheet("")\nw.resetSpacing(4)', "x.py")
    assert len(_scan("# old " + "#" + "123abc", "x.py")) == 1


def test_density_blocks_are_margin_only():
    sheet = re.sub(r"/\*.*?\*/", "", qss.stylesheet(), flags=re.S)
    blocks = [(selector, body) for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", sheet)
              if "[density=" in selector]
    assert blocks and 'density="standard"' not in sheet
    for selector, body in blocks:
        assert re.findall(r'density="(.*?)"', selector)
        for declaration in filter(str.strip, body.split(";")):
            assert declaration.split(":", 1)[0].strip() in {
                "margin", "margin-left", "margin-right", "margin-top", "margin-bottom"}


def test_generic_patterns_and_type_floor_use_existing_tokens():
    from synapse.panel.designsystem import tokens as t
    sheet = qss.stylesheet()
    for role in ("label", "tag", "row", "parm_row"):
        assert '[rhythm_role="%s"]' % role in sheet
    for name in ("DsCardHeader", "DsCardBody", "DsCardFooter", "DsParmLabel",
                 "DsParmValue", "DsParmControl", "DsRowGlyph", "DsParmSection"):
        assert "#" + name in sheet
    for scale in t.FONT_SCALE_STEPS:
        block = qss._rhythm_stylesheet(scale)
        assert all(int(px) >= max(t.FONT_FLOOR_PX, t.scaled(t.SIZE_BODY, scale))
                   for px in re.findall(r"font-size:\s*(\d+)px", block))
        assert set(map(int, re.findall(r"font-weight:\s*(\d+)", block))) == {
            t.WEIGHT_REGULAR, t.WEIGHT_MEDIUM}
    for name in ("rhythm.py", "qss.py"):
        assert not HEX.search((PANEL / "designsystem" / name).read_text(encoding="utf-8"))


def test_rhythm_import_requires_neither_qt_nor_application():
    code = """
import sys
sys.path.insert(0, 'python')
class NoQt:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('PySide6', 'PySide2', 'qtpy'):
            raise AssertionError('unexpected import: ' + fullname)
sys.meta_path.insert(0, NoQt())
from synapse.panel.designsystem import rhythm
assert rhythm.ROLE_GAPS['row'] > 0
"""
    subprocess.run([sys.executable, "-I", "-S", "-c", code], cwd=ROOT,
                   check=True, timeout=30)


class _Layout:
    def __init__(self):
        self.items, self.spacing, self.margins = [], -7, (1, 2, 3, 4)

    def setSpacing(self, value):
        self.spacing = value

    def setContentsMargins(self, *values):
        self.margins = values

    def addWidget(self, widget, stretch=0):
        self.items.append(widget)

    def count(self):
        return len(self.items)

    def stretch(self, index):
        return 0

    def takeAt(self, index):
        return self.items.pop(index)

    def itemAt(self, index):
        return self.items[index]


class _Widget:
    def __init__(self, role=None):
        self.props = {"rhythm_role": role}
        self.kids, self.polished = [], 0
        self.box = _Layout()

    def property(self, key):
        return self.props.get(key)

    def setProperty(self, key, value):
        self.props[key] = value

    def layout(self):
        return self.box

    def children(self):
        return self.kids

    def style(self):
        return self

    def polish(self, widget):
        widget.polished += 1

    def unpolish(self, widget):
        pass

    def setVisible(self, visible):
        pass

    def setMaximumHeight(self, height):
        pass

    def update(self):
        pass

    def widget(self):
        return self

    def _regate_stop(self):
        # The real _recompose re-asserts the Stop state gate after compose
        # (landing r3); the Qt-bound pin for that is
        # tests/test_panel_faces.py::test_stop_gated_to_working_state.
        pass


def test_unknown_role_density_and_removed_role(caplog):
    rhythm._WARNED.clear()
    node = _Widget("misspelled")
    assert rhythm.apply(node, "airy") == 1
    assert node.box.spacing == 16 and node.box.margins == (0, 0, 0, 0)
    rhythm.apply(node, "tight")
    assert len(caplog.records) == 1
    node.setProperty("rhythm_role", "row")
    rhythm.apply(node, "invalid-density")
    assert node.box.spacing == 12
    node.setProperty("rhythm_role", None)
    assert rhythm.apply(node, "airy") == 0
    assert node.box.spacing == 12


@pytest.mark.parametrize("role,expected", [
    ("label", (18, 9, 12)), ("row", (18, 9, 12)),
    ("tag", (24, 12, 16)), ("card", (24, 12, 16)),
    ("parm_row", (6, 3, 4)), ("group", (24, 12, 16)),
    ("shell", (24, 12, 16)), ("stack", (6, 3, 4)), ("band", (0, 0, 0)),
])
def test_recorded_layout_sequence_is_derived_from_base_not_current(monkeypatch, role, expected):
    # Recording protocol only, not a Qt measurement. Real QFont and QLayout
    # behavior has its own substrate-gated probes in the docking file.
    monkeypatch.setattr(rhythm, "_apply_type", lambda widget, role: None)
    node = _Widget(role)
    unmarked = _Widget()
    node.kids.append(unmarked)
    margins = {"row": (16, 12, 16, 12), "tag": (10, 6, 10, 6), "shell": (30, 8, 30, 8)}
    for index, density in enumerate(("airy", "tight", "standard", "airy")):
        assert rhythm.apply(node, density) == 1
        assert node.box.spacing == expected[index % 3]
        assert node.box.margins == margins.get(role, (0, 0, 0, 0))
        assert (unmarked.box.spacing, unmarked.box.margins) == (-7, (1, 2, 3, 4))


def test_initial_compose_and_actual_recompose_share_post_build_rhythm(monkeypatch):
    panel = _Widget()
    for builder in compositor.REGION_BUILDERS.values():
        def build(name=builder):
            if not hasattr(panel, name + "_cached"):
                region = _Widget("row")
                nested = _Widget("group")
                region.kids.append(nested)
                panel.kids.append(region)
                setattr(panel, name + "_cached", region)
            return getattr(panel, name + "_cached")
        setattr(panel, builder, build)
    calls = []
    real_apply = rhythm.apply

    def observe(root, density):
        assert len(root.kids) == len(compositor.REGION_BUILDERS)
        assert all(w.polished for region in root.kids for w in (region, *region.kids))
        calls.append(density)
        return real_apply(root, density)

    monkeypatch.setattr(rhythm, "apply", observe)
    compositor.compose(panel, panel.layout(), get_manifest("curious"))
    identities = [id(w) for w in panel.kids]
    # Execute the actual panel method without importing host/Qt/lifecycle code.
    tree = ast.parse((PANEL / "synapse_panel.py").read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SynapsePanel")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_recompose")
    namespace = {"compose": compositor.compose, "get_manifest": get_manifest,
                 "logger": compositor.logger}
    exec(compile(ast.Module(body=[method], type_ignores=[]), "synapse_panel.py", "exec"), namespace)
    for profile, expected in (("ml", 9), ("expert", 12), ("curious", 18)):
        namespace["_recompose"](panel, profile)
        assert all(w.box.spacing == expected for w in panel.kids)
        assert [id(w) for w in panel.kids] == identities
    assert calls == ["airy", "tight", "standard", "airy"]
