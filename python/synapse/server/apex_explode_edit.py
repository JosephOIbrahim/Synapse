"""The explode control, as the program a rig's own node runs.

synapse_add_explode_control writes the SOURCE of the two functions below into
one Python SOP, so the scene keeps working on a seat that has no SYNAPSE.
apex_explode.node_code copies them with inspect.getsource; the copy in the
node and the functions tested here are the same text.

Rules for this file, because Houdini runs its text inside a node:

  * each function stands alone: no module-level name, no import, no helper
    from outside its own body (the second calls the first, and that is all);
  * apex and hou are handed in, never imported here;
  * a graph this cannot edit raises ValueError before anything is added;
  * no backslash, no dollar sign and no backtick anywhere in this file, in
    code, comment or docstring. Houdini expands a Python SOP's code as a
    string parameter before Python sees it: a doubled backslash arrives
    single (probe, 22.0.466), and a dollar sign or a backtick starts a
    variable or an expression. tests/test_apex_explode_tool.py holds the line.

Every apex.Graph call below was run on Houdini 22.0.466, and each callback
name (TransformObject, Vector3ToFloat, Multiply<Float>, Clamp<Float>,
sop::peak) is in the 22.0.400 catalog on record
(harness/autoresearch/runs/apex_basic_20260817_122650).
"""


def add_explode_control(g, apex, hou, *, shape_port, parent, travel, handle,
                        attribute, rest_value):
    """Add one control, explode, to an APEX rig graph, in place.

    Raising the control by travel moves every point of the rest shape by
    its own attribute vector. The move sits where the shape enters the
    graph, before anything poses it, so a posed part carries its offset along.
    Up is +Y.

    g           an apex.Graph, edited in place
    shape_port  the graph input the rest shape arrives on
    parent      name of the control the new handle follows, or None
    travel      how far up the handle goes for a full explode, in scene units
    handle      (x, y, z) where the handle rests
    attribute   per-point vector attribute on the shape: its move at full explode
    rest_value  where the control rests, 0 (closed) to 1 (open)

    Returns the names it added. Raises ValueError before adding anything when
    the graph is not one it can edit.
    """
    added = ('explode', 'EXPLODE_height', 'EXPLODE_travel', 'EXPLODE_limits',
             'EXPLODE_move')
    names = {}
    for node in g.matchNodes('*'):
        names[g.nodeName(node)] = node

    def only(callback):
        found = [n for n in names.values() if g.callbackName(n) == callback]
        if len(found) != 1:
            raise ValueError('the rig needs one %s node and has %d'
                             % (callback, len(found)))
        return found[0]

    def port(node, name, kind):
        found = g.getPort(node, '%s[%s]' % (name, kind))
        if found < 0:
            raise ValueError('%s has no %sput port named %s'
                             % (g.nodeName(node), kind, name))
        return found

    parms = only('__parms__')
    output = only('__output__')
    taken = [name for name in added if name in names]
    if taken:
        raise ValueError('the rig already has a node named %s' % ', '.join(taken))
    if g.getPort(parms, 'explode_t[out]') >= 0:
        raise ValueError('the rig already has an input named explode_t')
    for name in ('explode', 'explode_amount'):
        if g.getPort(output, '%s[in]' % name) >= 0:
            raise ValueError('the rig already has an output named %s' % name)
    travel = float(travel)
    if not travel > 0.0:
        raise ValueError('travel must be above zero')
    if parent is not None and parent not in names:
        raise ValueError('the rig has no node named %s' % parent)
    shape = port(parms, shape_port, 'out')
    readers = list(g.connectedPorts(shape))
    if not readers:
        raise ValueError('nothing in the rig reads the shape input %s' % shape_port)
    follow = None if parent is None else port(names[parent], 'xform', 'out')
    rest_value = min(1.0, max(0.0, float(rest_value)))

    def add(name, callback, values=None):
        node = g.addNode(name, callback)
        if values:
            g.setNodeParms(node, apex.Dict(values))
        return node

    # the control an animator sees
    control = add('explode', 'TransformObject',
                  {'restlocal': hou.hmath.buildTranslate(tuple(handle)),
                   's': hou.Vector3(1.0, 1.0, 1.0)})
    if follow is not None:
        g.addWire(follow, port(control, 'parent', 'in'))
    g.promoteInput(port(control, 't', 'in'), parms, 'explode_t')
    g.promoteOutput(port(control, 'xform', 'out'), output, 'explode')
    g.setNodeTag(control, 'control')

    # its height becomes an amount from 0 to 1
    height = add('EXPLODE_height', 'Vector3ToFloat')
    g.addWire(port(parms, 'explode_t', 'out'), port(height, 'vector', 'in'))
    gain = add('EXPLODE_travel', 'Multiply<Float>', {'a': 1.0 / travel})
    g.addWire(port(height, 'y', 'out'), g.addSubPort(port(gain, 'b', 'in'), 'height'))
    limits = add('EXPLODE_limits', 'Clamp<Float>', {'min': 0.0, 'max': 1.0})
    g.addWire(port(gain, 'result', 'out'), port(limits, 'val', 'in'))
    g.promoteOutput(port(limits, 'result', 'out'), output, 'explode_amount')

    # the amount moves each point of the rest shape by its own offset
    move = add('EXPLODE_move', 'sop::peak',
               {'usecustomattrib': 1, 'customattrib': attribute,
                'normalizeattrib': 0, 'updatenmls': 0})
    g.addWire(port(limits, 'result', 'out'), port(move, 'dist', 'in'))
    moved = port(move, 'geo0', 'out')
    for reader in readers:
        g.removeWires(g.portWires(reader), False)
        g.addWire(moved, reader)
    g.addWire(shape, port(move, 'geo0', 'in'))

    g.setDefaultParms(
        apex.Dict({'explode_t': hou.Vector3(0.0, rest_value * travel, 0.0)}), False)
    return list(added)


def carry_explode_control(geo, apex, hou, *, rig_folder, shape_port, parent,
                          travel, handle, attribute, rest_value):
    """Swap the rig folder in geo for a copy that has the explode control.

    geo is a packed character: one folder per part of it, named by the
    name primitive attribute. Only the rig folder is replaced. The shape,
    the skeleton and every other folder pass through untouched.
    """
    target = None
    if geo.findPrimAttrib('name') is not None:
        for prim in geo.prims():
            if prim.attribValue('name') == rig_folder:
                target = prim
                break
    if target is None:
        raise ValueError('the input has no folder named %s' % rig_folder)
    graph = apex.Graph(target.getEmbeddedGeometry())
    added = add_explode_control(
        graph, apex, hou, shape_port=shape_port, parent=parent, travel=travel,
        handle=handle, attribute=attribute, rest_value=rest_value)
    edited = hou.Geometry()
    graph.saveToGeometry(edited)
    target.setEmbeddedGeometry(edited)
    return added
