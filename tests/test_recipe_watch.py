"""Scene-exit sequences with exact identity and failures, without a live host."""
from unittest.mock import Mock
import pytest
from synapse.host.recipe_watch import RecipeWatch


def setup_watch():
    host = Mock()
    host.selection_identity.return_value = ((17, "/stage/key"),)
    host.scene_path.return_value = "shotA.hip"
    host.save_identity.return_value = {"name": "Key", "version": 1, "recipe_id": "a" * 32}
    notices = []
    return RecipeWatch(host, notices.append), host, notices


def test_no_watch_does_not_capture_scene():
    watch, host, _ = setup_watch()
    watch.event("BeforeLoad")
    watch.close()
    host.save_identity.assert_not_called()


def test_scene_change_pair_saves_once_with_original_identity_and_metadata():
    watch, host, notices = setup_watch()
    watch.arm("Key", [" Lookdev "], "Keep the rim")
    host.scene_path.return_value = "shotB.hip"
    watch.event("BeforeLoad")
    watch.event("BeforeClear")
    watch.event("AfterClear")
    watch.event("AfterLoad")
    assert host.save_identity.call_count == 1
    args = host.save_identity.call_args.kwargs
    assert args["identities"] == ((17, "/stage/key"),)
    assert args["source_scene"] == "shotA.hip"
    assert args["tags"] == ["lookdev"]
    assert not watch.armed and notices[-1]["status"] == "saved"


def test_arm_replaces_previous_selection_without_accumulating_callbacks():
    watch, host, _ = setup_watch()
    watch.arm("First", [], "")
    host.selection_identity.return_value = ((19, "/stage/fill"),)
    watch.arm("Fill", [], "")
    assert host.subscribe.call_count == 1
    watch.event("BeforeClear")
    assert host.save_identity.call_args.kwargs["name"] == "Fill"


def test_failure_is_visible_and_never_success_or_path_fallback():
    watch, host, notices = setup_watch()
    watch.arm("Key", [], "")
    host.save_identity.side_effect = ValueError("The watched node was deleted or replaced")
    watch.event("BeforeClear")
    watch.event("BeforeClear")
    assert host.save_identity.call_count == 1
    assert notices[-1]["status"] == "failed" and "replaced" in notices[-1]["message"]
    assert not watch.armed


def test_stop_watching_does_not_save():
    watch, host, _ = setup_watch()
    watch.arm("Key", [], "")
    watch.disarm()
    watch.event("BeforeLoad")
    host.save_identity.assert_not_called()


def test_close_saves_once_and_removes_exact_callback():
    watch, host, _ = setup_watch()
    watch.arm("Key", [], "")
    callback = host.subscribe.call_args.args[0]
    watch.close()
    watch.close()
    assert host.save_identity.call_count == 1
    host.unsubscribe.assert_called_once_with(callback)


def test_invalid_metadata_cannot_arm():
    watch, host, _ = setup_watch()
    with pytest.raises(ValueError):
        watch.arm("", [], "")
    assert not watch.armed
    host.subscribe.assert_not_called()


def test_notice_failure_does_not_break_houdini_callback_chain():
    watch, host, _ = setup_watch()
    watch.arm("Key", [], "")
    watch.notify = Mock(side_effect=RuntimeError("panel gone"))
    watch.event("BeforeClear")
    assert watch.last_result["status"] == "saved"


def test_destroy_without_close_captures_and_detaches_without_touching_ui():
    watch, host, notices = setup_watch()
    watch.arm("Key", [], "")
    before = len(notices)
    watch.close(notify=False)
    assert len(notices) == before
    assert host.record_notice.call_args.args[0]["status"] == "saved"
    host.unsubscribe.assert_called_once()
    assert host.save_identity.call_count == 1


def test_failed_unsubscribe_leaves_inert_callback_and_observable_problem():
    watch, host, _ = setup_watch()
    watch.arm("Key", [], "")
    callback = host.subscribe.call_args.args[0]
    host.unsubscribe.side_effect = RuntimeError("host shutting down")
    watch.close(notify=False)
    callback("BeforeClear")
    assert host.save_identity.call_count == 1
    assert "removal failed" in watch.last_result["message"]


def test_save_as_uses_observed_capture_scene_in_receipt():
    watch, host, _ = setup_watch()
    watch.arm("Key", [], "")
    host.save_identity.return_value["snapshot"] = {"source_scene": "renamedShot.hip"}
    watch.event("BeforeLoad")
    assert watch.last_result["source_scene"] == "renamedShot.hip"
    assert watch.last_result["armed_source_scene"] == "shotA.hip"


def test_destroyed_panel_receipt_failure_reaches_surviving_host():
    watch, host, notices = setup_watch()
    watch.arm("Key", [], "")
    host.record_notice.side_effect = PermissionError("read-only result file")
    before = len(notices)
    watch.close(notify=False)
    assert len(notices) == before and host.save_identity.call_count == 1
    host.report_notice_failure.assert_called_once()
    message = host.report_notice_failure.call_args.args[0]
    assert "Saved Key" in message and "read-only result file" in message
