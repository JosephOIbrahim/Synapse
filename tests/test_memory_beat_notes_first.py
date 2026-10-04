"""The memory beat does not depend on the model guessing which tool holds the notes.

On 2026-10-04, on the relaunched take build, "What do you remember about how
this world was landed?" was answered from synapse_recall and synapse_search
alone. Both missed the landing record (the doorway assumption, the 1.2897 m
offset, the -0.016 m ground height), which lives in the scene's memory notes
and comes back only from synapse_project_setup. The same session returned the
record at once when project setup was asked for by name. The panel's prompt now
names that tool for questions about what is remembered of a scene.
"""
from synapse.panel.system_prompt import build_system_prompt


def test_the_prompt_sends_scene_memory_questions_to_project_setup():
    prompt = build_system_prompt({})
    assert "call synapse_project_setup first" in prompt
    assert "synapse_search and synapse_recall do not cover those notes" in prompt


def test_the_prompt_asks_for_recall_to_be_labelled_as_recall():
    prompt = build_system_prompt({})
    assert "recalled from the scene's notes rather than read from the live stage" in prompt
