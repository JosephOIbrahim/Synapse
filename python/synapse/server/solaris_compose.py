"""
SYNAPSE Solaris Compose -- LOP network-access primitive (PRD section 7.0).

Foundation for the compose tier (shotsetup_karma_xpu, matlib_bind,
shot_render_ready). Resolves /stage, creates+wires LOP nodes (phantom-guarded),
reads the composed stage, and exposes the composition-strength + composition-
error introspection the [REAL] verifiers need.

Execution model: every node mutation here is meant to run INSIDE a handler
closure that the handler itself marshals to Houdini's main thread
(``server.main_thread.run_on_main``) and wraps in ``hou.undos.group``. This
module therefore does NOT wrap undo itself -- double-wrapping is wrong; the
HANDLER owns reversibility. The panel bridge adds audit (integrity) on top.

Verified live on Houdini 21.0.671 (2026-05-30 dir() recon + mechanism probe):
  - ``subLayerPaths`` is STRONGEST-FIRST; ``Usd.Attribute.GetPropertyStack``
    returns specs strongest-first (proves which opinion WINS, not just presence).
  - ``usdrender`` LOP type is a PHANTOM -> only ``usdrender_rop`` exists.
  - ``node.stage()`` -> ``pxr.Usd.Stage`` (read-only). ``node.editableStage()``
    is None outside a cook; author via nodes+parms or a ``pythonscript`` LOP
    (where ``hou.pwd().editableStage()`` IS valid in-cook).
  - ``Usd.Stage.GetCompositionErrors`` present and empty on a clean stage.
"""

from typing import List, Optional, Tuple
import logging

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:  # standalone / CI
    hou = None
    HOU_AVAILABLE = False

try:
    from pxr import Usd
    _PXR_AVAILABLE = True
except ImportError:  # standalone / CI
    Usd = None
    _PXR_AVAILABLE = False

_log = logging.getLogger(__name__)

# LOP type names that the H21.0.671 dir() recon proved are phantoms -> the real
# type to use instead. NEVER silently create the wrong node (SF-1 / observability).
_PHANTOM_TYPE_ALIASES = {
    "usdrender": "usdrender_rop",
}

DEFAULT_STAGE_PATH = "/stage"


class ComposeError(Exception):
    """Base compose-primitive error. Always surfaced to the artist, never silent."""


class StageUnavailableError(ComposeError):
    """``/stage`` is missing, not a LopNetwork, or a node hasn't cooked."""


class PhantomNodeTypeError(ComposeError):
    """Requested a LOP type absent from the live H21 registry (SF-1 guard)."""


def _require_hou():
    if not HOU_AVAILABLE:
        raise ComposeError(
            "hou unavailable -- the compose primitive requires the live Houdini bridge"
        )


# -- Stage access -----------------------------------------------------------

def resolve_stage(path: str = DEFAULT_STAGE_PATH):
    """Return the ``/stage`` LOP network node. Raise if absent or not a LopNetwork."""
    _require_hou()
    node = hou.node(path)
    if node is None:
        raise StageUnavailableError("No node at '%s' -- is this a Solaris scene?" % path)
    if not isinstance(node, hou.LopNetwork):
        raise StageUnavailableError(
            "'%s' is %s, not a LopNetwork" % (path, node.type().name())
        )
    return node


def read_stage(lop_node):
    """Return the read-only composed ``Usd.Stage`` at a LOP node (``node.stage()``).

    Do NOT use ``editableStage()`` here -- it returns None outside a cook context.
    """
    _require_hou()
    if not hasattr(lop_node, "stage"):
        raise ComposeError("%s has no stage() -- not a LOP node?" % lop_node.path())
    stage = lop_node.stage()
    if stage is None:
        raise StageUnavailableError(
            "%s.stage() is None -- node hasn't cooked" % lop_node.path()
        )
    return stage


# -- Node creation / wiring (phantom-guarded) -------------------------------

def lop_type_exists(type_name: str) -> bool:
    """True iff a LOP node type of this exact name exists in the live registry."""
    _require_hou()
    return hou.nodeType(hou.lopNodeTypeCategory(), type_name) is not None


def canonical_type(type_name: str) -> str:
    """Map a known-phantom LOP type name to its real equivalent (logged), else
    return it unchanged."""
    real = _PHANTOM_TYPE_ALIASES.get(type_name)
    if real is not None:
        _log.warning("LOP type '%s' is a phantom on H21.0.671; using '%s'", type_name, real)
        return real
    return type_name


def create_lop(parent, type_name: str, name: Optional[str] = None):
    """Create a LOP node of a confirmed type under ``parent`` (phantom-guarded).

    Raises ``PhantomNodeTypeError`` if the (canonicalized) type is absent from the
    live registry -- never silently creates the wrong node (SF-1 / OBSERVABILITY).
    """
    _require_hou()
    t = canonical_type(type_name)
    if not lop_type_exists(t):
        raise PhantomNodeTypeError(
            "LOP type '%s'%s does not exist in the H21 LOP registry"
            % (type_name, (" (-> '%s')" % t) if t != type_name else "")
        )
    return parent.createNode(t, name) if name else parent.createNode(t)


def wire(node, src_node, input_index: int = 0):
    """Wire ``src_node`` into ``node``'s ``input_index`` (``node.setInput``)."""
    _require_hou()
    node.setInput(input_index, src_node)
    return node


def make_pythonscript_lop(parent, name: str, code: str):
    """Create a ``pythonscript`` LOP carrying ``code`` -- the authoring vehicle
    where ``hou.pwd().editableStage()`` IS valid (in-cook). Keep ``code`` flat
    (top-level statements): the LOP cook, like the bridge, can split
    globals/locals, so nested functions referencing module-level names NameError.
    """
    _require_hou()
    n = create_lop(parent, "pythonscript", name)
    for pname in ("python", "code", "script"):
        p = n.parm(pname)
        if p is not None:
            p.set(code)
            return n
    raise ComposeError(
        "pythonscript LOP %s exposes no python/code/script parm (parms: %s)"
        % (n.path(), [pp.name() for pp in n.parms()][:20])
    )


# -- Composition introspection (the [REAL] verifier backbone) ---------------

def winning_layer(stage, prim_path: str, attr_name: str) -> Tuple[object, List[str]]:
    """Return ``(resolved_value, [layer display names, strongest-first])`` for an
    attribute via ``GetPropertyStack``.

    Path-presence != strength. This proves which opinion actually WINS -- the
    GAP-1 (render layer overrides) / GAP-2 (binding wins by LIVRPS) backbone.
    """
    if not _PXR_AVAILABLE:
        raise ComposeError("pxr unavailable")
    prim = stage.GetPrimAtPath(prim_path)
    if not prim or not prim.IsValid():
        raise ComposeError("No valid prim at %s" % prim_path)
    attr = prim.GetAttribute(attr_name)
    if not attr:
        raise ComposeError("No attribute %s on %s" % (attr_name, prim_path))
    stack = attr.GetPropertyStack(Usd.TimeCode.Default())
    return attr.Get(), [s.layer.GetDisplayName() for s in stack]


def composition_errors(stage) -> List[str]:
    """List of composition error strings (empty list == clean). GAP-3 backbone.

    Distinguishes the classic 'looks fine, renders empty' case: unresolved refs
    and bad arcs show up here even when the stage otherwise traverses.
    """
    return [str(e) for e in stage.GetCompositionErrors()]
