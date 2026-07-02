"""Registry model-picker API — Qt-free pins for the data layer the panel's model
switcher reads. Recreates coverage for the (deleted) test_model_picker: the
helpers and build_provider(model=...) the picker, chip, and rail author depend on.
Network-free, Qt-free, hou-free.
"""
from synapse.panel.providers import registry as reg


def test_anthropic_models_listed():
    ids = [m for m, _ in reg.models_for("claude")]
    assert "claude-sonnet-5" in ids
    assert "claude-sonnet-4-6" in ids
    assert "claude-opus-4-8" in ids
    assert "claude-haiku-4-5-20251001" in ids
    assert "claude-fable-5" in ids
    assert len(ids) >= 5


def test_models_for_unknown_is_empty():
    assert reg.models_for("bogus") == ()


def test_default_model_is_registry_default():
    assert reg.default_model("claude") == reg.ANTHROPIC_MODEL
    assert reg.default_model("gemini") == reg.GEMINI_MODEL
    assert reg.default_model("nemotron") == reg.NVIDIA_MODEL
    # unknown id falls back to the Claude floor (panel never crashes on a stale id)
    assert reg.default_model("bogus") == reg.ANTHROPIC_MODEL


def test_model_label_short_and_safe():
    assert reg.model_label("claude", "claude-fable-5") == "Fable 5"
    # the dated Haiku id must read as a clean short label, not 'haiku-4.5.20251001'
    assert reg.model_label("claude", "claude-haiku-4-5-20251001") == "Haiku 4.5"
    # the long NVIDIA id must collapse to a short, slash-free chip/rail label
    lbl = reg.model_label("nemotron", "nvidia/nemotron-3-super-120b-a12b")
    assert "/" not in lbl and 0 < len(lbl) < 30
    # an unknown model id returns the id verbatim (no crash, no surgery)
    assert reg.model_label("claude", "claude-unknown-9") == "claude-unknown-9"


def test_build_provider_honours_model_override():
    p = reg.build_provider("claude", model="claude-opus-4-8")
    assert p.id == "claude" and p.model_identity == "claude-opus-4-8"
    # model=None → provider default
    assert reg.build_provider("claude").model_identity == reg.ANTHROPIC_MODEL
    # unknown provider → claude floor, never raises
    assert reg.build_provider("bogus").id == "claude"


def test_build_provider_nemotron_with_picked_model():
    n = reg.build_provider("nemotron", model="nvidia/nemotron-3-nano-30b-a3b")
    assert n.id == "nemotron"
    assert n.model_identity == "nvidia/nemotron-3-nano-30b-a3b"


def test_provider_ids_and_labels_consistent():
    assert set(reg.PROVIDER_IDS) == set(reg.PROVIDER_LABELS)
    assert set(reg.PROVIDER_IDS) == set(reg.PROVIDER_MODELS)
    assert set(reg.PROVIDER_IDS) == set(reg.PROVIDER_DEFAULT_MODEL)
    # every default is itself a selectable row for its provider; the Custom
    # engine may be UNCONFIGURED — empty rows ⇒ empty default (and only then,
    # so row/default drift on the other providers still fails here)
    for pid in reg.PROVIDER_IDS:
        ids = [m for m, _ in reg.models_for(pid)]
        if ids:
            assert reg.default_model(pid) in ids
        else:
            assert reg.default_model(pid) == ""
