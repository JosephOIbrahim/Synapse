"""H4 ORACLE (source half): the panel has exactly ONE colour authority.

The defect this pins: ``synapse.panel.tokens`` (the bridge) and
``synapse.panel.designsystem.tokens`` both declared the same colour names with
different values, so the panel rendered two different accent blues depending on
which import a given line reached for. A prior pass converted call sites but
left both modules declaring, which is why converting call sites again would not
have fixed it -- the repair has to happen at the source.

WHY THE READER IS CALIBRATED FIRST (R60)
----------------------------------------
Mutation-testing an implementation proves a pin notices a broken product. It
says nothing about whether the pin can SEE the product at all, and a blind
reader emits green pins carrying zero information -- indistinguishable from
correct ones. So every reader below is exercised against synthetic sources with
a KNOWN answer, in both directions, before any of them is pointed at the tree:

  test_reader_sees_a_redeclaration          positive control -- must FLAG
  test_reader_does_not_flag_a_pure_reexport negative control -- must NOT flag
  test_reader_resolves_a_non_t_alias        the tree uses ``_t`` and ``_ds``
  test_reader_resolves_a_function_local_import   gate_widget.py:185 does this
  test_reader_descends_into_except_arms     every bridge fallback lives in one
  test_reader_sees_hex_literals_only_as_declarations   derived != declared

If any control fails, the pins below are meaningless and the control is the
finding.
"""

import ast
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
_PANEL = os.path.join(_ROOT, "python", "synapse", "panel")

for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

BRIDGE_REL = "python/synapse/panel/tokens.py"
DS_REL = "python/synapse/panel/designsystem/tokens.py"

_HEX = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")

# The colour names the two modules both used to declare. These are what a call
# site could resolve two ways, so these are what the pins are about.
SHARED_COLOUR_NAMES = (
    "SIGNAL", "VOID", "NEAR_BLACK", "CARBON", "GRAPHITE", "SLATE", "SILVER",
    "BONE", "WHITE", "FIRE", "GROW", "WARN", "ERROR",
    "HOU_ORANGE", "HOU_DARK", "HOU_WIRE",
    "SIGNAL_HOVER", "SIGNAL_PRESS",
)


# ---------------------------------------------------------------------------
# READER 1 -- which tokens module does each alias in a source file bind to?
# ---------------------------------------------------------------------------

def alias_bindings(src, filename="<src>"):
    """``{alias_name: "bridge" | "designsystem"}`` for one module's source.

    Walks the WHOLE tree (``ast.walk``), so imports inside functions, inside
    ``try``/``except`` arms and inside ``if`` branches are all seen. A reader
    that only looked at ``tree.body`` would miss gate_widget.py:185 and every
    fallback arm in the panel, which is most of the interesting surface.

    RELATIVE imports resolve against the FILE'S OWN package, not globally.
    ``from . import tokens`` means the bridge in ``panel/styles.py`` and the
    design system in ``panel/designsystem/qss.py`` -- same five characters, two
    different modules. A reader that resolved ``.`` one way for both would
    report all 21 of qss.py's already-correct references as offenders and send
    a repair into a file that was never broken. ``filename`` is therefore
    load-bearing input, not a diagnostic label; the control is
    ``test_reader_resolves_a_relative_import_by_the_files_own_package``.
    """
    inside_designsystem = "panel/designsystem/" in filename.replace("\\", "/")
    bindings = {}
    tree = ast.parse(src, filename=filename)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            level = node.level or 0
            for a in node.names:
                if a.name != "tokens":
                    continue
                alias = a.asname or a.name
                if level:                                  # relative
                    if mod == "designsystem":              # from .designsystem
                        bindings[alias] = "designsystem"
                    elif not mod:                          # from . import tokens
                        bindings[alias] = ("designsystem" if inside_designsystem
                                           else "bridge")
                elif mod.endswith("panel.designsystem"):
                    bindings[alias] = "designsystem"
                elif mod == "synapse.panel":
                    bindings[alias] = "bridge"
        elif isinstance(node, ast.Import):
            for a in node.names:
                if not a.name.endswith(".tokens"):
                    continue
                alias = a.asname or a.name.split(".")[0]
                bindings[alias] = ("designsystem" if ".designsystem." in a.name
                                   else "bridge")
    return bindings


def token_references(src, filename="<src>"):
    """``[(alias, attribute, lineno)]`` for every token read through an alias.

    Catches BOTH access forms the tree uses:
      ``_t.SIGNAL``                 -- ast.Attribute
      ``getattr(_t, "TEXT", dflt)`` -- ast.Call, which is NOT an Attribute node

    context_bar.py reads three of its tokens through ``getattr`` with a default.
    An Attribute-only reader reports those lines as having no token reference at
    all, so a migration driven by it would leave them behind and the pin would
    still go green. Control: ``test_reader_sees_a_getattr_token_read``.
    """
    aliases = alias_bindings(src, filename)
    tree = ast.parse(src, filename=filename)
    refs = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in aliases):
            refs.append((node.value.id, node.attr, node.lineno))
        elif (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id in aliases
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)):
            refs.append((node.args[0].id, node.args[1].value, node.lineno))
    return refs


# ---------------------------------------------------------------------------
# READER 2 -- which names does a module DECLARE as a colour of its own?
# ---------------------------------------------------------------------------

def declared_hex_literals(src, filename="<src>"):
    """``{name: (hex, lineno)}`` for every assignment of a bare colour LITERAL.

    Declaring is assigning a hex string. DERIVING is not: ``MODE_ACTIVE_BG =
    SIGNAL + "15"`` composes from whatever the single authority says SIGNAL is,
    and ``SUCCESS_LED = GROW`` is an alias. Neither creates a second authority,
    and banning them would delete panel-specific tokens the inventory oracle
    requires be present. So the reader keys on ``ast.Constant`` targets only --
    and ``test_reader_sees_hex_literals_only_as_declarations`` proves it draws
    that line where it claims to.

    Descends into try/except/if bodies: every bridge fallback lives in one.
    """
    out = {}
    tree = ast.parse(src, filename=filename)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not (isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
                and _HEX.match(node.value.value)):
            continue
        for tgt in node.targets:
            if isinstance(tgt, ast.Name):
                out[tgt.id] = (node.value.value, node.lineno)
    return out


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _panel_sources():
    """Every .py under panel/, at any depth, as (repo_rel_path, source)."""
    for base, _dirs, files in os.walk(_PANEL):
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            full = os.path.join(base, name)
            yield os.path.relpath(full, _ROOT).replace("\\", "/"), _read(full)


# ===========================================================================
# CONTROLS -- the reader is proven able to see, before it is trusted
# ===========================================================================

_REEXPORT_SRC = (
    "from synapse.panel.designsystem.tokens import SIGNAL, GROW\n"
    "SUCCESS_LED = GROW\n"
    "MODE_ACTIVE_BG = SIGNAL + '15'\n"
)

_REDECLARE_SRC = _REEXPORT_SRC + "SIGNAL = '#00D4FF'\n"


def test_reader_sees_a_redeclaration():
    """POSITIVE CONTROL. A module that imports SIGNAL and then assigns it a hex
    literal must be flagged. Fails if the reader ignores redeclaration -- the
    exact blindness that would certify H4 while the collision survived."""
    found = declared_hex_literals(_REDECLARE_SRC)
    assert "SIGNAL" in found, (
        "reader is BLIND to a redeclaration; every pin below is vacuous"
    )
    assert found["SIGNAL"][0] == "#00D4FF"


def test_reader_does_not_flag_a_pure_reexport():
    """NEGATIVE CONTROL. Re-export + alias + derived value declare nothing.
    Fails if the reader over-reports, which would make the pin unfixable."""
    assert declared_hex_literals(_REEXPORT_SRC) == {}


def test_reader_sees_hex_literals_only_as_declarations():
    """The declared/derived line is drawn where the docstring claims. Fails if
    the reader counts ``SIGNAL + '15'`` as a declaration (it would then demand
    the panel-specific tokens be deleted) or misses a bare literal."""
    src = ("A = '#112233'\n"
           "B = A + '40'\n"
           "C = 'not a colour'\n"
           "D = '#ABC'\n")
    found = declared_hex_literals(src)
    assert set(found) == {"A", "D"}, found


def test_reader_resolves_a_non_t_alias():
    """The tree binds ``_t`` (bridge) and ``_ds`` (designsystem) as often as
    ``t``. Fails if the reader hard-codes the alias name."""
    src = ("from synapse.panel import tokens as _t\n"
           "from synapse.panel.designsystem import tokens as _ds\n"
           "X = _t.SIGNAL\nY = _ds.SIGNAL\n")
    assert alias_bindings(src) == {"_t": "bridge", "_ds": "designsystem"}
    refs = {(a, attr) for a, attr, _ln in token_references(src)}
    assert refs == {("_t", "SIGNAL"), ("_ds", "SIGNAL")}


def test_reader_resolves_a_function_local_import():
    """gate_widget.py:185 imports tokens INSIDE a method. Fails if the reader
    only inspects module-level ``tree.body`` -- it would then report that file
    as having no token references at all."""
    src = ("def paint(self):\n"
           "    from synapse.panel.designsystem import tokens as t\n"
           "    return t.SIGNAL\n")
    assert alias_bindings(src) == {"t": "designsystem"}
    assert ("t", "SIGNAL", 3) in token_references(src)


def test_reader_sees_a_getattr_token_read():
    """context_bar.py reads TEXT / TEXT_DIM / HOVER via ``getattr`` with a
    default. Fails if the reader only walks ast.Attribute -- it would then
    report those lines as token-free and a migration would skip them."""
    src = ("from synapse.panel import tokens as _t\n"
           "A = _t.SIGNAL\n"
           "B = getattr(_t, 'TEXT', '#E0E0E0')\n")
    refs = {(a, attr) for a, attr, _ln in token_references(src)}
    assert refs == {("_t", "SIGNAL"), ("_t", "TEXT")}, refs


def test_reader_resolves_a_relative_import_by_the_files_own_package():
    """``from . import tokens`` is the BRIDGE in panel/ and the DESIGN SYSTEM in
    panel/designsystem/. Fails if the reader resolves ``.`` globally -- the
    defect this control was written for, found by pointing the pin at the tree
    and reading the output instead of trusting it. A globally-resolving reader
    reported designsystem/qss.py's 21 correct references as offenders."""
    src = "from . import tokens as t\nX = t.SIGNAL\n"
    assert alias_bindings(src, "python/synapse/panel/styles.py") == {"t": "bridge"}
    assert alias_bindings(
        src, "python/synapse/panel/designsystem/qss.py") == {"t": "designsystem"}


def test_reader_descends_into_except_arms():
    """Every bridge fallback is an ``except ImportError`` body. Fails if the
    reader skips handler bodies -- it would call the fallback cyan invisible."""
    src = ("try:\n"
           "    from synapse.panel.designsystem import tokens as t\n"
           "except ImportError:\n"
           "    import synapse.panel.tokens as t\n"
           "    SIGNAL = '#00D4FF'\n")
    assert alias_bindings(src)["t"] in ("bridge", "designsystem")
    assert "SIGNAL" in declared_hex_literals(src), (
        "reader cannot see inside an except arm"
    )


def test_control_suite_would_notice_a_gutted_reader():
    """Meta-control: a deliberately gutted reader (module-level only, no walk)
    must fail the controls above. This is what proves the controls have teeth
    rather than merely existing."""
    def gutted(src):
        tree = ast.parse(src)
        out = {}
        for node in tree.body:              # <- the blindness under test
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and _HEX.match(str(node.value.value)):
                        out[tgt.id] = (node.value.value, node.lineno)
        return out

    except_arm = ("try:\n"
                  "    pass\n"
                  "except ImportError:\n"
                  "    SIGNAL = '#00D4FF'\n")
    assert "SIGNAL" not in gutted(except_arm), "gutted reader is not gutted"
    assert "SIGNAL" in declared_hex_literals(except_arm), (
        "the real reader must catch what the gutted one misses"
    )


# ===========================================================================
# THE PINS -- pointed at the tree, now that the reader is calibrated
# ===========================================================================

def test_bridge_declares_no_colour_of_its_own():
    """``panel/tokens.py`` re-exports; it does not declare. Fails the moment
    any hex literal is assigned in that module again -- which is exactly how
    the two-authority defect was reintroduced last time."""
    found = declared_hex_literals(_read(os.path.join(_ROOT, *BRIDGE_REL.split("/"))),
                                  BRIDGE_REL)
    assert found == {}, (
        "%s declares its own colours -- a second authority: %s"
        % (BRIDGE_REL, sorted("%s=%s@L%d" % (k, v[0], v[1]) for k, v in found.items()))
    )


def test_exactly_one_module_under_panel_declares_colours():
    """Across ALL of panel/ at any depth, the design system is the only module
    holding colour literals. Fails if any other panel module starts hoarding
    hexes (the shape the defect took at five call-site fallback arms)."""
    declaring = {}
    for rel, src in _panel_sources():
        found = declared_hex_literals(src, rel)
        if found:
            declaring[rel] = sorted(found)
    assert list(declaring) == [DS_REL], (
        "expected the design system to be the only colour authority; found: %r"
        % declaring
    )


def test_no_panel_module_binds_the_bridge_for_a_shared_colour():
    """No call site may reach a SHARED colour name through the bridge alias.
    Fails if any module reverts to ``from synapse.panel import tokens`` and
    then reads SIGNAL/VOID/... through it."""
    offenders = []
    for rel, src in _panel_sources():
        if rel == BRIDGE_REL:
            continue
        binds = alias_bindings(src, rel)
        for alias, attr, lineno in token_references(src, rel):
            if binds.get(alias) == "bridge" and attr in SHARED_COLOUR_NAMES:
                offenders.append("%s:%d %s.%s" % (rel, lineno, alias, attr))
    assert offenders == [], (
        "shared colour names reached through the bridge alias: %s" % offenders
    )


def test_bridge_and_designsystem_agree_at_runtime():
    """The source pins cannot see the off-repo ``~/.synapse/design`` side
    channel, which is where the live cyan actually came from. This one imports
    both modules and compares VALUES. Fails if the bridge ever re-acquires a
    divergent value from any source, in-repo or not."""
    import synapse.panel.tokens as bridge
    import synapse.panel.designsystem.tokens as ds

    divergent = {}
    for name in SHARED_COLOUR_NAMES:
        if hasattr(bridge, name) and hasattr(ds, name):
            b, d = getattr(bridge, name), getattr(ds, name)
            if b != d:
                divergent[name] = (b, d)
    assert divergent == {}, (
        "bridge and design system disagree at runtime (bridge, designsystem): %r"
        % divergent
    )


def test_runtime_check_has_something_to_check():
    """Control for the pin above: it is only meaningful if the names it
    compares actually exist on both modules. A bridge that exported none of
    them would make that test pass vacuously -- Law 1 applied to the pin's own
    input set."""
    import synapse.panel.tokens as bridge
    import synapse.panel.designsystem.tokens as ds

    compared = [n for n in SHARED_COLOUR_NAMES
                if hasattr(bridge, n) and hasattr(ds, n)]
    assert len(compared) >= len(SHARED_COLOUR_NAMES), (
        "only %d of %d shared colour names are present on BOTH modules; the "
        "runtime agreement pin would pass on a near-empty set. Missing: %r"
        % (len(compared), len(SHARED_COLOUR_NAMES),
           sorted(set(SHARED_COLOUR_NAMES) - set(compared)))
    )


def test_the_panel_has_exactly_one_font_scale_ladder():
    """The Aa control must step ONE ladder.

    Not a colour, and that is the point: the two-authority defect was never
    only about colour. The bridge declared [0.75, 1.0, 1.25, 1.5] while the
    design system declared (1.0, 1.15, 1.25, 1.4, 1.6), and synapse_panel.py
    stepped the second while chat_panel.py stepped the first -- one panel, two
    Aa controls, different stops. Fails if either module reacquires its own
    ladder, or if MIN/MAX drift off the ends of the steps they bound.
    """
    import synapse.panel.tokens as bridge
    import synapse.panel.designsystem.tokens as ds

    assert tuple(bridge.FONT_SCALE_STEPS) == tuple(ds.FONT_SCALE_STEPS)
    assert bridge.FONT_SCALE_DEFAULT == ds.FONT_SCALE_DEFAULT
    assert bridge.FONT_SCALE_DEFAULT in bridge.FONT_SCALE_STEPS, (
        "the default is not a stop on its own ladder — .index() raises"
    )
    assert bridge.FONT_SCALE_MIN == min(bridge.FONT_SCALE_STEPS)
    assert bridge.FONT_SCALE_MAX == max(bridge.FONT_SCALE_STEPS)


@pytest.mark.parametrize("name", sorted(SHARED_COLOUR_NAMES))
def test_shared_colour_is_the_same_object_from_both_paths(name):
    """Per-name form of the agreement pin, so a single divergent token names
    itself in the failure report instead of hiding in a dict."""
    import synapse.panel.tokens as bridge
    import synapse.panel.designsystem.tokens as ds
    assert getattr(bridge, name) == getattr(ds, name)
