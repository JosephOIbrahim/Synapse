"""Fixed disposable fixture producer, excluded from runtime payloads."""
from dataclasses import asdict

import json

import os

from pathlib import Path

from synapse.recipes.contracts import (ActionId, ActionSpec, PermissionCategory, RecipeSpec,
                                      RecoveryVerdict, REQUIRED_CHECKS, SlotSchema)

from synapse.recipes.instance import InstanceLifecycle, MemoryInstanceStore, on_main

from synapse.recipes.light_headless import (AuthoredCodeCanonicalizer, ClosedLightObserver,
                                          EXPOSURE, HeadlessLightBackend, authored_digest)

from synapse.recipes.transaction import BuildTransaction, PreparedOperation, ProvisionalDecision

from synapse.server.main_thread import run_on_main

class FixtureSetup(HeadlessLightBackend):
    """Qualification-only fixed-scene producer; never a runtime graph builder/gate port."""
    def __init__(self, observer):
        self.setting_up = False
        super().__init__(observer)

    def preflight(self, operations):
        assert not self.snapshot()['scope']['box_present']
        assert len(operations) == 1 and operations[0].kind == 'qualification_fixture_setup'
        return None

    def _event(self, node=None, event_type=None, **kwargs):
        if self.setting_up:
            return  # only the fixed synchronous fixture-construction code below
        super()._event(node, event_type, **kwargs)

    def apply(self, operation):
        import hou
        assert operation.kind == 'qualification_fixture_setup'
        self.setting_up = True
        try:
            stage = hou.node('/stage')
            assert not stage.children() and not stage.networkBoxes()
            light = stage.createNode('domelight::3.0', node_name=self.observer.node_path.rsplit('/', 1)[1])
            box = stage.createNetworkBox(self.observer.box_name)
            box.addItem(light)
            self.refresh_tracking()
            self._userdata = self.snapshot()["userdata"]
        finally:
            self.setting_up = False

def make_context():
    observer = ClosedLightObserver('/stage/bounded_key_light', 'bounded_light_fixture')
    slots = (SlotSchema('exposure', 'float', 'key.' + EXPOSURE, -2, 2),)
    actions = tuple(ActionSpec(action, action_slots, REQUIRED_CHECKS[action], scope, PermissionCategory.APPROVE)
                    for action, action_slots, scope in ((ActionId.BUILD, (), 'graph'), (ActionId.LIGHT, slots, 'field')))
    spec = RecipeSpec('headless.light.qualification', 'fixture-only-1', '2', '22.0.400', 'RUNTIME_SCOUTED',
                      'headless-light-authored-code-v1', '', '',
                      {'status': 'HEADLESS_FIXTURE_ONLY', 'render': 'NOT_RUN', 'artist_gui': 'NOT_QUALIFIED'},
                      ({'id': 'key', 'type': 'domelight::3.0'},), (), actions)
    lifecycle = InstanceLifecycle('/stage', spec, observer=observer, canonicalizer=AuthoredCodeCanonicalizer(),
                                  store=MemoryInstanceStore(), box_name=observer.box_name)
    instance = lifecycle.new_instance({'key': observer.node_path})
    setup = FixtureSetup(observer)
    operation = PreparedOperation('qualification_fixture_setup', observer.box_name,
                                  writes=(('nodes',), ('authored', '/stage'), ('userdata', observer.node_path), ('topology',), ('scope',)))
    txn = BuildTransaction(request_id='private-fixture-build', instance=instance, lifecycle=lifecycle,
                           backend=setup, operations=(operation,), expected_revision=0, dependencies=setup.dependencies())
    result = txn.execute()
    if result.outcome != 'committed':
        return observer, lifecycle, setup, txn, result
    setup.close()
    return observer, lifecycle, HeadlessLightBackend(observer), txn, result


def require_disposable_case(case):
    """Fail before mutation unless a fresh isolated opt-in process was selected."""
    import pytest
    if os.environ.get("SYNAPSE_HEADLESS_LIGHT_QUALIFICATION") != case:
        pytest.skip("Explicit fresh disposable H22 qualification opt-in required: " + case)
    def check():
        import hou
        import synapse
        expected = Path(__file__).resolve().parents[2] / "python/synapse/__init__.py"
        assert Path(synapse.__file__).resolve() == expected.resolve(), "Wrong source checkout; refuse before any scene edit"
        assert not hou.isUIAvailable() and hou.applicationVersionString() == "22.0.400", "Headless H22.0.400 only"
        assert os.environ.get("SYNAPSE_LOG_DIR") and os.environ.get("SYNAPSE_LOOP_LEDGER_DIR"), "Explicit disposable logs/ledger directories required"
        root = Path(os.environ["SYNAPSE_HEADLESS_LIGHT_SANDBOX"]).resolve()
        marker = json.loads((root / "LIGHT_QUALIFICATION_SANDBOX.json").read_text(encoding="utf-8"))
        assert marker == {"schema": "synapse.light.qualification-sandbox.v1", "disposable": True,
                          "case": case, "source_root": str(expected.parents[2])}, "Explicit disposable runner marker required"
        assert root.parent != root and root != Path.home().resolve() and root != expected.parents[2]
        assert Path(os.environ["SYNAPSE_LOG_DIR"]).resolve().is_relative_to(root)
        assert Path(os.environ["SYNAPSE_LOOP_LEDGER_DIR"]).resolve().is_relative_to(root)
        leaf = "protected-light-matrix" if case == "matrix" else "cancel-foreign-light"
        assert not (Path(os.environ["SYNAPSE_LOOP_LEDGER_DIR"]) / leaf).exists(), "A new owned fixture ledger directory is required"
        assert not hou.node("/stage").children() and not hou.node("/stage").networkBoxes(), "Fresh empty scene required"
    run_on_main(check, label="qualification:refuse unsafe host context")
