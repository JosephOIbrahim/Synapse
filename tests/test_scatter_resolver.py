"""Read-only binding evidence and refusal cases; no Houdini or live storage."""
import json
from types import SimpleNamespace

import pytest

from synapse.routing.solaris_recipes import resolve_scatter, scatter_request


class Node:
    def __init__(self, path, kind, parms=None):
        self.p = path
        self.kind = kind
        self.parms = parms or {}
        self.ancestors = []
        self.out = []
        self.before = None
        self.bypass = False
        self.record = None

    def path(self): return self.p
    def type(self): return SimpleNamespace(nameComponents=lambda: ("", "", self.kind, ""))
    def parm(self, name):
        return (SimpleNamespace(evalAsString=lambda: self.parms[name])
                if name in self.parms else None)
    def inputAncestors(self): return self.ancestors
    def outputs(self): return self.out
    def input(self, index): return self.before
    def isBypassed(self): return self.bypass
    def userData(self, key): return self.record


def prim(path, kind):
    return SimpleNamespace(GetPath=lambda: path, GetTypeName=lambda: kind, IsValid=lambda: True)


@pytest.fixture
def scene(tmp_path):
    source = tmp_path / 'world_500k.ply'
    source.write_bytes(b'fixture source')
    collider = tmp_path / 'world_collider.glb'
    collider.write_bytes(b'fixture collider')
    file = Node('/obj/world/source', 'file', {'file': str(source)})
    bake = Node('/obj/world/bake', 'bakegsplat')
    bake.ancestors = [file]
    world = Node('/stage/import', 'sopimport', {'soppath': bake.path(), 'pathprefix': '/World/w'})
    world.record = json.dumps({'grounding': {'collider': collider.name}})
    camera = Node('/stage/cam', 'camera', {'primpath': '/cameras/c'})
    camera.ancestors = [world]
    settings = Node('/stage/settings', 'rendersettings')
    settings.before = camera
    settings.ancestors = [camera, world]
    camera.out = [settings]
    prims = [prim('/cameras/c', 'Camera'), prim('/World/w', 'Xform'),
             prim('/World/w/splats', 'ParticleField3DGaussianSplat')]
    stage = SimpleNamespace(Traverse=lambda: prims,
                            GetPrimAtPath=lambda p: next((x for x in prims if x.GetPath() == p),
                                                        SimpleNamespace(IsValid=lambda: False)))
    settings.stage = lambda: stage
    parent = SimpleNamespace(displayNode=lambda: settings, children=lambda: [world, camera, settings])
    nodes = {'/stage': parent, bake.path(): bake}
    hou = SimpleNamespace(node=lambda p: nodes.get(p))
    return SimpleNamespace(hou=hou, camera=camera, settings=settings, world=world,
                           file=file, prims=prims, collider=collider, source=source, nodes=nodes)


def test_resolves_all_bindings_without_mutation(scene):
    result = resolve_scatter(scene.hou)
    assert result['status'] == 'RESOLVED'
    assert all(b['source'] and b['value'] != 'UNKNOWN' for b in result['bindings'].values())
    assert result['bindings']['UPSTREAM']['value'] == scene.camera.path()
    assert result['bindings']['COLLIDER_GLB']['value'] == scene.collider.as_posix()
    graph = result['payload']
    scatter = next(n for n in graph['nodes'] if n.get('type') == 'scatterinstances')
    assert scatter['parms']['maxangle'] == 20
    assert scatter['parms']['enabledirection'] == 1
    assert scene.settings.before is scene.camera


@pytest.mark.parametrize('fault', ['no_camera', 'two_cameras', 'missing_collider',
                                  'ambiguous_collider', 'no_provenance', 'wrong_provenance',
                                  'missing_source', 'missing_sop', 'no_world', 'two_imports',
                                  'branched_camera', 'bypassed_camera'])
def test_unknown_never_supplies_build_payload(scene, fault):
    if fault == 'no_camera': scene.prims[:] = [p for p in scene.prims if p.GetTypeName() != 'Camera']
    elif fault == 'two_cameras': scene.prims.append(prim('/cameras/other', 'Camera'))
    elif fault == 'missing_collider': scene.collider.unlink()
    elif fault == 'ambiguous_collider': scene.source.with_name('world_500k_collider.glb').write_bytes(b'other')
    elif fault == 'no_provenance': scene.world.record = None
    elif fault == 'wrong_provenance': scene.world.record = '{"grounding":{"collider":"../other.glb"}}'
    elif fault == 'missing_source': scene.source.unlink()
    elif fault == 'missing_sop': scene.nodes.clear()
    elif fault == 'no_world': scene.world.parms['pathprefix'] = '/absent'
    elif fault == 'two_imports': scene.camera.ancestors.append(scene.world)
    elif fault == 'branched_camera': scene.camera.out.append(Node('/stage/other', 'null'))
    elif fault == 'bypassed_camera': scene.camera.bypass = True
    result = scatter_request(scene.hou, {'recipe': 'scatter_instances', 'recipe_action': 'build'})
    assert result['status'] == 'UNKNOWN'
    assert result['build_allowed'] is False
    assert 'payload' not in result
    assert result['reason']


@pytest.mark.parametrize('override', ['nodes', 'connections', 'template', 'maxangle', 'bindings', 'dry_run'])
def test_model_overrides_are_rejected_before_read(scene, override):
    scene.hou.node = lambda p: pytest.fail('must reject overrides before any scene read')
    with pytest.raises(ValueError, match='fixed'):
        scatter_request(scene.hou, {'recipe': 'scatter_instances', override: 45})


def test_build_rechecks_collider_after_resolution(scene):
    request = {'recipe': 'scatter_instances', 'recipe_action': 'resolve'}
    assert scatter_request(scene.hou, request)['status'] == 'RESOLVED'
    scene.collider.unlink()
    request['recipe_action'] = 'build'
    assert scatter_request(scene.hou, request)['status'] == 'UNKNOWN'


def test_three_resolutions_are_identical(scene):
    outputs = [scatter_request(scene.hou, {'recipe': 'scatter_instances'}) for _ in range(3)]
    assert outputs[0] == outputs[1] == outputs[2]


def test_invalid_provenance_is_unknown(scene):
    scene.world.record = 'broken json'
    assert resolve_scatter(scene.hou)['status'] == 'UNKNOWN'


def test_custom_parent_is_refused_before_read(scene):
    scene.hou.node = lambda p: pytest.fail('unsupported parent must not be read')
    result = resolve_scatter(scene.hou, '/other')
    assert result['status'] == 'UNKNOWN' and not result['build_allowed']


def test_host_read_failure_is_unknown(scene):
    def failed():
        raise RuntimeError('host stage read failed')
    scene.settings.stage = failed
    result = resolve_scatter(scene.hou)
    assert result['status'] == 'UNKNOWN'
    assert 'payload' not in result


def test_binding_strings_cannot_inject_graph_parameters():
    from synapse.routing.solaris_recipes import payload
    collider = '/world/a", "maxangle":45, "x":".glb'
    graph = payload('scatter_instances', UPSTREAM='cam', DOWNSTREAM='settings',
                    WORLD_PRIM='/World/w', CAMERA_PRIM='/cameras/c', COLLIDER_GLB=collider)
    reference = next(n for n in graph['nodes'] if n.get('type') == 'reference')
    scatter = next(n for n in graph['nodes'] if n.get('type') == 'scatterinstances')
    assert reference['parms']['filepath1'] == collider
    assert scatter['parms']['maxangle'] == 20


def test_karma_render_settings_is_supported(scene):
    scene.settings.kind = 'karmarendersettings'
    assert resolve_scatter(scene.hou)['status'] == 'RESOLVED'


@pytest.mark.parametrize('fault', ['missing_file_parm', 'renamed_no_metadata', 'missing_soppath'])
def test_missing_neutral_scene_evidence_fails_closed(scene, fault):
    if fault == 'missing_file_parm': scene.file.parms.clear()
    elif fault == 'renamed_no_metadata': scene.world.record = None
    else: scene.world.parms.pop('soppath')
    result = resolve_scatter(scene.hou)
    assert result['status'] == 'UNKNOWN' and not result['build_allowed']
    assert result['reason'] and 'payload' not in result


def test_named_houdini_exception_is_unknown(scene):
    class OperationFailed(Exception): pass
    scene.hou.OperationFailed = OperationFailed
    def failed(): raise OperationFailed('stale host reference')
    scene.settings.stage = failed
    assert resolve_scatter(scene.hou)['status'] == 'UNKNOWN'


def test_generic_enforcement_preserves_bindings_and_reports_every_correction():
    from synapse.routing.solaris_recipes import enforce_scatter_parameters, scatter_fixed_parameters
    nodes = [{'id': 's', 'type': 'scatterinstances',
              'parms': {'primpath': '/World/scatter_rocks', 'maxangle': 45, 'enabledirection': 0,
                        'camerapath': '/cameras/artist', 'scattertargetgeometry': '/World/target'}}]
    normalized, corrections = enforce_scatter_parameters(nodes)
    assert nodes[0]['parms']['maxangle'] == 45  # incoming request remains intact
    for name, value in scatter_fixed_parameters().items():
        assert normalized[0]['parms'][name] == value
    assert normalized[0]['parms']['camerapath'] == '/cameras/artist'
    assert normalized[0]['parms']['scattertargetgeometry'] == '/World/target'
    # primpath is what identified the node as the recipe's, so it needs no correction.
    assert {c['parm'] for c in corrections} == set(scatter_fixed_parameters()) - {'primpath'}
    assert next(c for c in corrections if c['parm'] == 'maxangle')['requested'] == 45


def test_enforcement_is_idempotent_and_preserves_other_tools():
    from synapse.routing.solaris_recipes import enforce_scatter_parameters
    nodes = [{'id': 's', 'type': 'scatterinstances::1.0', 'parms': {'primpath': '/World/scatter_rocks'}},
             {'id': 'light', 'type': 'light', 'parms': {'maxangle': 45}}]
    normalized, _ = enforce_scatter_parameters(nodes)
    again, changes = enforce_scatter_parameters(normalized)
    assert again == normalized and changes == []
    assert again[1] == nodes[1]


def test_an_artists_own_scatter_is_built_as_sent():
    """Enforcement is for the recipe's node only (primpath /World/scatter_rocks)."""
    from synapse.routing.solaris_recipes import enforce_scatter_parameters, is_recipe_scatter
    trees = {'id': 't', 'type': 'scatterinstances',
             'parms': {'primpath': '/World/trees', 'maxangle': 60, 'scattercount': 500,
                       'protogroupprims0': '/prototypes/pine'}}
    bare = {'id': 'b', 'type': 'scatterinstances'}
    odd = {'id': 'o', 'type': 'scatterinstances', 'parms': 'not-an-object'}
    normalized, corrections = enforce_scatter_parameters([trees, bare, odd])
    assert normalized == [trees, bare, odd]
    assert corrections == []
    assert not any(is_recipe_scatter(n) for n in (trees, bare, odd))
    assert is_recipe_scatter({'type': 'scatterinstances::2.0', 'parms': {'primpath': '/World/scatter_rocks'}})


@pytest.fixture
def handler_env(monkeypatch, scene):
    from synapse.server import handlers_solaris_graph as graph
    from synapse.server import main_thread
    monkeypatch.setattr(graph, 'HOU_AVAILABLE', True)
    monkeypatch.setattr(graph, 'hou', scene.hou, raising=False)
    monkeypatch.setattr(main_thread, 'run_on_main', lambda fn, **kwargs: fn())
    return graph


def test_recipe_dry_run_does_not_dispatch_build(handler_env, scene):
    handler = handler_env.SolarisGraphMixin()
    result = handler._handle_solaris_build_graph({'recipe': 'scatter_instances', 'dry_run': True})
    assert result['status'] == 'RESOLVED' and scene.settings.before is scene.camera


@pytest.mark.parametrize('fault', ['camera', 'collider'])
def test_recipe_unknown_never_dispatches_generic_build(handler_env, scene, fault):
    if fault == 'camera': scene.prims[:] = []
    else: scene.collider.unlink()
    handler = handler_env.SolarisGraphMixin()
    result = handler._handle_solaris_build_graph({'recipe': 'scatter_instances'})
    assert result['status'] == 'UNKNOWN' and not result['build_allowed']
    assert scene.settings.before is scene.camera


def test_recipe_build_dispatches_only_canonical_graph(handler_env, scene):
    class Handler(handler_env.SolarisGraphMixin):
        def _handle_solaris_build_graph(self, request):
            if 'recipe' in request:
                return super()._handle_solaris_build_graph(request)
            self.built = request
            return {'status': 'created'}
    handler = Handler()
    result = handler._handle_solaris_build_graph({'recipe': 'scatter_instances'})
    assert result['status'] == 'created'
    scatter = next(n for n in handler.built['nodes'] if n.get('type') == 'scatterinstances')
    assert scatter['parms']['maxangle'] == 20
    assert result['recipe_resolution']['bindings']['CAMERA_PRIM']['source']


def test_recipe_rejects_model_nodes(handler_env):
    from synapse.core.errors import SynapseUserError
    with pytest.raises(SynapseUserError, match='fixed'):
        handler_env.SolarisGraphMixin()._handle_solaris_build_graph(
            {'recipe': 'scatter_instances', 'nodes': []})


def test_generic_build_preview_enforces_without_resolver(handler_env, monkeypatch):
    graph = handler_env
    monkeypatch.setattr(graph, '_validate_node_types', lambda *args: None)
    monkeypatch.setattr(graph, 'resolve_plan', lambda *args: {
        'bindings': {'s': None}, 'paths': {'s': '/stage/scatter'}, 'connections': []})
    monkeypatch.setattr(graph, 'observed_display', lambda parent: (None, True))
    result = graph.SolarisGraphMixin()._handle_solaris_build_graph({
        'nodes': [{'id': 's', 'type': 'scatterinstances',
                   'parms': {'primpath': '/World/scatter_rocks', 'maxangle': 45}}],
        'dry_run': True})
    correction = next(c for c in result['scatter_parameter_corrections'] if c['parm'] == 'maxangle')
    assert correction == {'node': 's', 'parm': 'maxangle', 'requested': 45, 'fixed': 20}


@pytest.mark.parametrize('nodes', [[None], [1], None, {}])
def test_malformed_nodes_have_structured_error(handler_env, nodes):
    from synapse.core.errors import SynapseUserError
    with pytest.raises(SynapseUserError, match='list of objects'):
        handler_env.SolarisGraphMixin()._handle_solaris_build_graph({'nodes': nodes})
