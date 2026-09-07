"""Pure routing: exact checked evidence, payload union, deterministic pinning."""
import time

import pytest

from synapse.panel.connections import ConnectionFacts, ConnectionSpec


@pytest.fixture
def routing():
    from synapse.panel import model_routing
    return model_routing


def facts(name, *, local=True, caps=("completion", "tools", "vision"), stamp=None, endpoint=None):
    spec = ConnectionSpec("ollama", name, endpoint or (
        "http://127.0.0.1:11434/v1/chat/completions" if local else "https://fixture.invalid/v1/chat/completions"))
    metadata = {"size": 128, "details": {"format": "gguf"}}
    if caps is not None:
        metadata["capabilities"] = caps
    return ConnectionFacts(spec, metadata, time.time() if stamp is None else stamp)


def test_default_uses_chosen_model_without_hidden_local_fallback(routing):
    chosen, local = facts("chosen", local=False), facts("local")
    decision = routing.choose_route(chosen, [local])
    assert decision.ok and decision.facts.spec == chosen.spec
    assert not decision.automatic and decision.requirements == frozenset({"completion"})
    assert chosen.spec.identity in decision.reason and chosen.spec.endpoint in decision.reason


@pytest.mark.parametrize("content", [
    [{"type": "image", "source": {"type": "base64", "data": "fixture"}}],
    [{"type": "image_url", "image_url": {"url": "https://fixture.invalid/image.png"}}],
    [{"type": "tool_result", "content": [{"type": "image", "source": {"data": "fixture"}}]}],
    [{"type": "input_image", "image_url": "fixture"}],
    [{"parts": [{"inline_data": {"mime_type": "image/png", "data": "fixture"}}]}],
])
def test_actual_history_and_tools_override_conversation_label(routing, content):
    requirements = routing.required_capabilities(tools=[{"name": "build"}], messages=[{"role": "user", "content": content}])
    assert requirements == frozenset({"completion", "tools", "vision"})


@pytest.mark.parametrize("need,expected", [("conversation", {"completion"}), ("tools", {"completion", "tools"}), ("images", {"completion", "vision"}), ("vision", {"completion", "vision"})])
def test_selected_need_is_part_of_union(routing, need, expected):
    assert routing.required_capabilities(need) == frozenset(expected)


def test_auto_uses_only_fresh_positive_capabilities_not_names_or_size(routing):
    now = time.time()
    chosen = facts("chosen", local=False, stamp=now)
    unknown = facts("large-vision-tools", caps=None, stamp=now)
    partial = facts("partial", caps=("completion",), stamp=now)
    stale = facts("stale", stamp=now - 181)
    good = facts("checked", stamp=now)
    decision = routing.choose_route(chosen, [unknown, partial, stale, good], mode="prefer_checked_local", tools=[{"name": "build"}], now=now)
    assert decision.ok and decision.automatic and decision.facts.spec == good.spec


def test_auto_prefers_selected_local_then_deterministic_identity(routing):
    chosen, a, z = facts("selected"), facts("a"), facts("z")
    assert routing.choose_route(chosen, [a, z], mode="prefer_checked_local").facts.spec == chosen.spec
    remote = facts("remote", local=False)
    first = routing.choose_route(remote, [z, a], mode="prefer_checked_local")
    second = routing.choose_route(remote, [a, z], mode="prefer_checked_local")
    assert first.facts.spec == second.facts.spec == a.spec


def test_no_candidate_is_actionable_and_never_falls_back(routing):
    chosen = facts("chosen", caps=None)
    decision = routing.choose_route(chosen, [], mode="prefer_checked_local", tools=[{"name": "build"}])
    assert not decision.ok and decision.facts is None
    assert "check" in decision.reason.lower()


def test_remote_candidate_is_explicitly_explained_not_granted(routing):
    chosen = facts("remote", local=False)
    decision = routing.choose_route(chosen, [], mode="prefer_checked_local")
    assert decision.ok and decision.facts.spec == chosen.spec
    assert "permission" in decision.reason.lower()


def test_chosen_unknown_is_untested_but_explicit_missing_capability_refuses(routing):
    unknown = routing.choose_route(facts("manual", caps=None), tools=[{"name": "build"}])
    assert unknown.ok and "unknown" in unknown.reason.lower()
    absent = routing.choose_route(facts("manual", caps=("completion",)), tools=[{"name": "build"}])
    assert not absent.ok and "tools" in absent.reason


def test_second_action_new_image_stops_pinned_model_without_switch(routing):
    chosen = facts("tools-only", caps=("completion", "tools"))
    initial = routing.choose_route(chosen, [], mode="prefer_checked_local", tools=[{"name": "build"}])
    upgraded_history = [{"role": "user", "content": [{"type": "tool_result", "content": [{"type": "image"}]}]}]
    followup = routing.choose_route(chosen, [facts("can-see")], mode="prefer_checked_local", pinned=initial, messages=upgraded_history)
    assert not followup.ok and followup.facts.spec == chosen.spec
    assert "vision" in followup.reason and "new task" in followup.reason.lower()
    assert followup.requirements == frozenset({"completion", "tools", "vision"})


def test_pinned_choice_stays_even_when_ui_changes_and_never_revives_failure(routing):
    initial = routing.choose_route(facts("one"), mode="prefer_checked_local")
    next_turn = routing.choose_route(facts("two"), [facts("three")], pinned=initial)
    assert next_turn.ok and next_turn.facts.spec == initial.facts.spec
    failed = routing.validate_route(initial, now=initial.facts.checked_at + 181)
    assert not failed.ok
    still_failed = routing.choose_route(facts("fresh"), [facts("fresh")], pinned=failed)
    assert not still_failed.ok and still_failed.facts.spec == initial.facts.spec


def test_same_model_different_endpoint_is_distinct_and_freshness_is_bound(routing):
    chosen = facts("same", endpoint="http://127.0.0.1:1/v1/chat/completions", caps=None)
    checked = facts("same", endpoint="http://127.0.0.1:2/v1/chat/completions")
    result = routing.choose_route(chosen, [checked], mode="prefer_checked_local")
    assert result.ok and result.facts.spec == checked.spec
    assert ":2/" in result.reason


@pytest.mark.parametrize("bad", ["auto", "random", ""])
def test_unknown_mode_refuses(routing, bad):
    decision = routing.choose_route(facts("one"), mode=bad)
    assert not decision.ok


def test_unknown_need_refuses(routing):
    with pytest.raises(ValueError):
        routing.required_capabilities("guess")


def test_newer_unknown_check_overrides_previous_supported_check(routing):
    now = time.time()
    old = facts("same", stamp=now - 10)
    newest = facts("same", stamp=now, caps=None)
    decision = routing.choose_route(old, [newest], mode="prefer_checked_local", now=now)
    assert not decision.ok


def test_future_check_cannot_expose_older_permission(routing):
    now = time.time()
    old = facts("same", stamp=now - 10)
    future = facts("same", stamp=now + 10)
    assert not routing.choose_route(old, [future], mode="prefer_checked_local", now=now).ok


def test_conflicting_simultaneous_checks_never_depend_on_order(routing):
    now = time.time()
    selected = facts("same", stamp=0, caps=None)
    one, two = facts("same", stamp=now), facts("same", stamp=now, caps=("completion",))
    for candidates in ([one, two], [two, one]):
        assert not routing.choose_route(selected, candidates, mode="prefer_checked_local", now=now).ok
