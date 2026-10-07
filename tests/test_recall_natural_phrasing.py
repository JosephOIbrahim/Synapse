"""DEMO-02: a natural on-camera question finds the deposited decision first.

Recall used to require EVERY non-question word of the query to appear in the
record, so "What did we decide about the hero sphere color?" missed "We chose
blue metallic for the hero sphere" ('decide' and 'color' absent). These pin
the overlap ranking that replaced it, and the guards it must keep: whole-word
matching (no 'oral' inside 'coral'), one shared word is not a hit, an empty
store or an unrelated question finds nothing.
"""
import pytest

from synapse.memory import store as memory_store
from synapse.memory.models import Memory, MemoryType


@pytest.fixture
def memory(monkeypatch, tmp_path):
    monkeypatch.setattr(memory_store, "HOU_AVAILABLE", False)
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "jsonl")
    instance = memory_store.SynapseMemory(str(tmp_path))
    yield instance
    instance.save()


def _deposit(memory):
    """A handful of demo-shaped decisions, written in the order an artist would."""
    return {
        "sphere": memory.decision(
            "We chose blue metallic for the hero sphere.",
            "Reads cleaner against the charcoal plinth.",
        ),
        "key": memory.decision(
            "Key light moved to camera left at 45 degrees, softbox at 2 metres.",
            "Gives the torus a long highlight.",
        ),
        "engine": memory.decision(
            "Render with Karma XPU at 128 pixel samples.",
            "XPU is fast enough for lookdev turnarounds.",
        ),
        "floor": memory.decision(
            "Ground plane is a matte grey concrete with light roughness.",
            "Keeps reflections out of the product's silhouette.",
        ),
    }


@pytest.mark.parametrize("question, key", [
    ("What did we decide about the hero sphere color?", "sphere"),
    ("What colour is the hero sphere?", "sphere"),
    ("Remind me what we chose for the hero sphere", "sphere"),
    ("Which renderer settings did we land on? Karma samples?", "engine"),
    ("Where did we put the key light?", "key"),
    ("Tell me about the ground plane decision", "floor"),
    ("what did we decide about the grey ground", "floor"),
])
def test_natural_question_finds_the_decision_first(memory, question, key):
    ids = _deposit(memory)
    memory.save()
    reopened = memory_store.SynapseMemory(str(memory.project_path))
    recalled = reopened.recall(question)
    assert recalled, question
    assert recalled[0].id == ids[key].id


def test_better_overlap_outranks_fresher_record(memory):
    memory.store.add(Memory(
        id="sphere", created_at="2026-01-01", updated_at="2026-01-01",
        content="Hero sphere is blue metallic.", memory_type=MemoryType.DECISION,
    ))
    memory.store.add(Memory(
        id="torus", created_at="2026-09-09", updated_at="2026-09-09",
        content="Hero torus is copper.", memory_type=MemoryType.DECISION,
    ))
    assert [m.id for m in memory.recall("hero sphere color")] == ["sphere", "torus"]


def _deposit_overlapping(memory):
    """Records that share words on purpose, so ranking has to choose."""
    return {
        "look": memory.decision(
            "Hero sphere look: warm coral shader, copper torus beside it on a charcoal plinth.",
            "Client approved the warm palette.",
        ),
        "camera": memory.decision(
            "Shot camera uses a 50mm lens at f/2.8, focus distance on the hero sphere.",
            "Shallow depth of field isolates the product.",
        ),
        "fog": memory.decision(
            "Add a light volumetric fog in the background only, density 0.02.",
            "Gives depth behind the plinth.",
        ),
        "color": memory.decision(
            "Color pipeline: ACEScg working space, display view ACES 1.0 SDR.",
            "Matches the grading suite.",
        ),
        "backdrop": memory.decision(
            "Backdrop is a charcoal grey infinity cyc with a slight vignette.",
            "Keeps the coral sphere the brightest thing in frame.",
        ),
    }


@pytest.mark.parametrize("question, key", [
    # Tie on terms answered: the record that LEADS with the subject wins over
    # the fresher one that mentions it in passing.
    ("what did we decide about the hero sphere?", "look"),
    # Synonym groups: background ~ backdrop, atmosphere ~ fog.
    ("what did we decide about the background?", "backdrop"),
    ("what did we decide about atmosphere?", "fog"),
    ("how dense is the fog?", "fog"),
])
def test_overlapping_records_rank_the_subject_first(memory, question, key):
    ids = _deposit_overlapping(memory)
    recalled = memory.recall(question)
    assert recalled and recalled[0].id == ids[key].id, [m.content[:30] for m in recalled]


def test_equal_score_falls_back_to_fresher_first(memory):
    for record_id, date in [("old", "2026-01-01"), ("new", "2026-09-09")]:
        memory.store.add(Memory(
            id=record_id, created_at=date, updated_at=date,
            content="Hero sphere is blue metallic.", memory_type=MemoryType.DECISION,
        ))
    assert [m.id for m in memory.recall("what colour is the hero sphere?")] == ["new", "old"]


def test_whole_word_guard_holds(memory):
    memory.decision("Coral hero display", "Approved product look.")
    assert memory.recall("oral") == []
    assert memory.recall("What did we decide about the oral?") == []


def test_one_shared_word_of_two_is_not_a_hit(memory):
    memory.decision("Coral hero display", "Approved product look.")
    assert memory.recall("coral submarine") == []


def test_empty_store_finds_nothing(memory):
    assert memory.recall("What did we decide about the hero sphere color?") == []


@pytest.mark.parametrize("question", [
    "What did we decide about the explosion sim?",
    "Which fog density did we choose?",
    "What did we decide?",
    "Remind me what we decided about this project",
])
def test_unrelated_or_empty_question_finds_nothing(memory, question):
    _deposit(memory)
    assert memory.recall(question) == []


def test_handler_shape_is_unchanged(memory):
    from synapse.session import tracker

    bridge = tracker.SynapseBridge.__new__(tracker.SynapseBridge)
    bridge._synapse = memory
    bridge._markdown_sync = None
    bridge._context_cache = None
    ids = _deposit(memory)
    out = bridge.handle_memory_recall({"query": "What did we decide about the hero sphere color?"})
    assert set(out) == {"query", "found", "count", "matches"}
    assert out["found"] is True
    assert out["matches"][0]["id"] == ids["sphere"].id
    miss = bridge.handle_memory_recall({"query": "Which fog density did we choose?"})
    assert miss["found"] is False and miss["count"] == 0 and miss["matches"] == []


def test_coverage_guard_refuses_a_never_recorded_subject(memory):
    # "turntable" is in no record: the question is about something never
    # decided, so the nearest camera decision must not be offered instead.
    memory.decision("Shot camera uses a 50mm lens at f/2.8.", "Shallow depth of field.")
    assert memory.recall("what lens did we use on the turntable camera?") == []
    assert memory.recall("what lens did we use on the shot camera?")


def test_value_words_are_not_required(memory):
    # The record answers "focal length" with "50mm"; the question is about the camera.
    decision = memory.decision("Shot camera uses a 50mm lens at f/2.8.", "Shallow depth of field.")
    assert [m.id for m in memory.recall("what focal length is the shot camera?")] == [decision.id]


def test_restated_decision_outranks_the_one_it_replaced(memory):
    for record_id, date, mm in [("old", "2026-01-01", "50mm"), ("new", "2026-09-09", "85mm")]:
        memory.store.add(Memory(
            id=record_id, created_at=date, updated_at=date,
            content=f"**Decision:** Hero lens is {mm}.", memory_type=MemoryType.DECISION,
        ))
    assert [m.id for m in memory.recall("what lens did we pick for the hero?")] == ["new", "old"]


def test_changed_decision_beats_the_old_one_despite_incidental_overlap(memory):
    # recall-eval's runsheet probe: the old camera record also says "hero"
    # (in its focus clause); the newer decision is the one the artist means.
    memory.store.add(Memory(
        id="old", created_at="2026-10-07T10:00:00", updated_at="2026-10-07T10:00:00",
        content="**Decision:** Shot camera uses a 50mm lens at f/2.8, focus distance on the hero sphere.",
        memory_type=MemoryType.DECISION,
    ))
    memory.store.add(Memory(
        id="new", created_at="2026-10-07T11:00:00", updated_at="2026-10-07T11:00:00",
        content="**Decision:** Remember this for the project: the hero lens is 35mm because the set is tight.",
        memory_type=MemoryType.DECISION,
    ))
    for question in ("What was our hero lens?", "which lens are we using?", "what's the hero lens?"):
        assert memory.recall(question)[0].id == "new", question


def test_which_side_asks_for_a_value(memory):
    decision = memory.decision("Key light stays warm from frame left; rim is a cool kicker.", "Look.")
    assert [m.id for m in memory.recall("Which side is the key light on?")] == [decision.id]
