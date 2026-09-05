"""In-memory graph controls; no hou module is installed or impersonated here."""
from copy import deepcopy
import hashlib
import json
from uuid import uuid4

import unittest
from unittest.mock import patch

from synapse.recipes.contracts import (
    ActionId, ActionSpec, CheckId, PermissionCategory, RecipeSpec, RefusalKind,
    REQUIRED_CHECKS, SlotSchema,
)
from synapse.recipes.instance import (
    BlocksObserver, InstanceLifecycle, LifecycleUnavailable, MemoryInstanceStore,
    ScopeObservation,
)


class Canonical:
    def semantic_digest(self, state, *, version):
        def semantic(value):
            if isinstance(value, dict):
                return {k: semantic(v) for k, v in value.items() if k != "position"}
            if isinstance(value, (tuple, list)):
                return [semantic(v) for v in value]
            return value
        return hashlib.sha256(json.dumps([version, semantic(state)], sort_keys=True).encode()).hexdigest()


def make_spec():
    actions = tuple(ActionSpec(a, slots, REQUIRED_CHECKS[a], scope, PermissionCategory.APPROVE)
                    for a, slots, scope in (
                        (ActionId.BUILD, (), "graph"),
                        (ActionId.LIGHT, (SlotSchema("exposure", "float", "key.exposure", -5, 5),), "field"),
                        (ActionId.MATERIAL, (SlotSchema("color", "color3", "hero.basecolor"),), "field")))
    return RecipeSpec("solaris.spine", "test-capture", "2", "22.0.400", "catalog",
                      "test-canon", "", "", {"hip": "NOT_RUN"},
                      ({"id": "key", "type": "light"}, {"id": "hero", "type": "shader"}),
                      (), actions)


class Scene:
    def __init__(self):
        self.nodes = {"/stage/artist": {"type": "null", "parms": {"note": "keep"}}}
        self.box = None
        self.store = MemoryInstanceStore()
        self.spec = make_spec()
        self.complete = True
        self.lifetime = uuid4().hex
        self.lifecycle = InstanceLifecycle("/stage", self.spec, observer=self.observe,
                                           canonicalizer=Canonical(), store=self.store,
                                           dispatch=lambda fn: fn())

    @property
    def ids(self):
        return {"key": "/stage/key", "hero": "/stage/material/hero"}

    def observe(self, stage, spec, box_name):
        return ScopeObservation(self.box is not None, self.lifetime, self.box or {},
                                {p: deepcopy(self.nodes[p]) for p in (self.box or {}).values()
                                 if p in self.nodes}, self.complete, "nested state unreadable")

    def populate(self):
        self.box = self.ids
        self.nodes.update({"/stage/key": {"type": "light", "parms": {"exposure": 0.0}},
                           "/stage/material/hero": {"type": "shader", "parms": {"basecolor": [0, 0, 1]}}})

    def committed(self):
        candidate = self.lifecycle.new_instance(self.ids)
        self.populate()
        self.lifecycle.commit(candidate, action=ActionId.BUILD, slots={}, approved=False,
                              expected_revision=0)
        return candidate


class InstanceTests(unittest.TestCase):
    def test_discovery_never_adopts_unknown_artist_state(self):
        scene = Scene()
        assert scene.lifecycle.discover() is None
        scene.populate()
        with self.assertRaisesRegex(LifecycleUnavailable, "no committed instance"):
            scene.lifecycle.discover()


    def test_semantic_digest_includes_nested_expression_and_excludes_layout(self):
        scene = Scene()
        instance = scene.committed()
        baseline = scene.lifecycle.fingerprint(instance)
        scene.nodes["/stage/material/hero"]["position"] = [8, -2]
        assert scene.lifecycle.fingerprint(instance) == baseline
        scene.nodes["/stage/material/hero"]["expression"] = "$F / 7"
        assert scene.lifecycle.fingerprint(instance) != baseline


    def test_changed_artist_state_refuses_conflict_and_preserves_opinions(self):
        scene = Scene()
        instance = scene.committed()
        scene.nodes["/stage/key"]["parms"]["exposure"] = 3.0
        before = deepcopy(scene.nodes)
        assert scene.lifecycle.check_conflict(instance).kind is RefusalKind.CONFLICT
        assert scene.nodes == before


    def test_revision_reads_store_instead_of_callers_stale_object(self):
        scene = Scene()
        instance = scene.committed()
        scene.nodes["/stage/key"]["parms"]["exposure"] = 2.0
        scene.lifecycle.commit(instance, action=ActionId.LIGHT, slots={"exposure": 2.0},
                               approved=True, expected_revision=1)
        assert scene.lifecycle.check_revision(instance, 1).kind is RefusalKind.STALE
        assert scene.lifecycle.check_revision(instance, 2) is None
        assert scene.lifecycle.check_conflict(instance) is None
        assert scene.lifecycle.discover().committed_slots == {"exposure": 2.0}


    def test_unapproved_field_commit_does_not_rebaseline(self):
        scene = Scene()
        instance = scene.committed()
        with self.assertRaisesRegex(ValueError, "approved"):
            scene.lifecycle.commit(instance, action=ActionId.MATERIAL, slots={"color": [1, 0, 0]},
                                   approved=False, expected_revision=1)
        assert instance.graph_revision == 1


    def test_recreated_box_cannot_reuse_old_instance_metadata(self):
        scene = Scene()
        instance = scene.committed()
        scene.lifetime = uuid4().hex
        assert scene.lifecycle.check_conflict(instance).kind is RefusalKind.CONFLICT
        with self.assertRaises(LifecycleUnavailable):
            scene.lifecycle.discover()


    def test_partial_observation_never_certifies_fingerprint(self):
        scene = Scene()
        instance = scene.committed()
        scene.complete = False
        with self.assertRaisesRegex(LifecycleUnavailable, "nested state unreadable"):
            scene.lifecycle.fingerprint(instance)


    def test_blocks_observer_uses_existing_ownership_snapshot(self):
        from synapse.blocks import runtime
        calls = []
        def observe(*args):
            calls.append(args)
            return {"box_present": True, "box_members": {"key": {}}}
        adapter = BlocksObserver({"nodes": []})
        with patch.object(runtime, "observe", observe), self.assertRaisesRegex(LifecycleUnavailable, "nested/expressions/port"):
            adapter("/stage", make_spec(), "BLOCKS_solaris_spine")
        assert len(calls) == 1
