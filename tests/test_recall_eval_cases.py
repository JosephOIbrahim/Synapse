"""recall-eval's SHARED paraphrase set (DEMO-02), pinned at a71eca94.

Twelve demo-shaped decisions, 65 natural questions, 15 negatives over the
full store and 5 over an empty one. Copied from the team eval's
recall_eval.py (the held-out set is not here and never was). Records get
fixed ids and distinct timestamps, so same-second ties cannot reorder them.
The xfails are the known misses at a71eca94, each with its cause.
"""
import pytest

from synapse.memory import store as memory_store
from synapse.memory.models import Memory, MemoryType

DEPOSITS = [
    ('look', 'Hero sphere look: warm coral shader with roughness 0.35, copper torus beside it on a charcoal plinth.',
     'Client approved the warm palette at the Tuesday review.'),
    ('torus_mtl', 'Torus material is brushed copper, anisotropy 0.6, roughness 0.2.',
     'Reads as metal next to the coral sphere without stealing focus.'),
    ('key_light', 'Key light is a dome light with the studio HDRI rotated 120 degrees, plus a warm rim light from camera left.',
     'Matches the reference plate the client sent.'),
    ('camera', 'Shot camera uses a 50mm lens at f/2.8, focus distance on the hero sphere.',
     'Shallow depth of field isolates the product.'),
    ('set_dressing', 'Solaris set dressing: plinth and backdrop come in as payloads under /set, hero assets live under /hero.',
     'Keeps the stage light and lets us swap set pieces per shot.'),
    ('render', 'Final renders use Karma XPU at 256 samples, 1920x1080, with the denoiser on.',
     'XPU is fast enough on the 4090 and the denoiser cleans up the glossy noise.'),
    ('scatter', 'Scatter 40k pebbles on the ground plane with a 2cm minimum distance, seed 7.',
     'Dense enough to read as gravel at the hero camera without overlap.'),
    ('naming', 'Naming convention: geometry nodes lowercase with underscores, materials prefixed mtl_, lights prefixed lgt_.',
     'Keeps the network readable and the USD prim paths predictable.'),
    ('fog', 'Add a light volumetric fog in the background only, density 0.02.',
     'Gives depth behind the plinth without flattening the hero.'),
    ('frames', 'Frame range 1001 to 1120 at 24 fps, motion blur on with a 0.5 shutter.',
     'Standard editorial handles and a filmic blur.'),
    ('color', 'Color pipeline: ACEScg working space, display view ACES 1.0 SDR.',
     'Matches the grading suite.'),
    ('backdrop', 'Backdrop is a charcoal grey infinity cyc with a slight vignette.',
     'Keeps the coral sphere the brightest thing in frame.'),
]

QUESTIONS = {
    'look': [
        'what did we decide about the hero sphere?',
        'remind me what material we chose for the sphere',
        "what's the look for the hero sphere?",
        'what color did we pick for the hero?',
        'what was the look decision?',
        'which shader are we using on the sphere?',
        'coral',
    ],
    'torus_mtl': [
        'what did we decide for the torus material?',
        "what's the torus made of?",
        'remind me how the torus is shaded',
        'what roughness is the torus?',
        'is the torus copper?',
    ],
    'key_light': [
        'what did we decide about the key light?',
        'how are we lighting the scene?',
        'which HDRI are we using?',
        "what's the lighting setup?",
        "where's the rim light coming from?",
        'remind me about the dome light decision',
    ],
    'camera': [
        'what lens did we choose?',
        'what did we decide for the camera?',
        'what focal length is the shot camera?',
        'what aperture are we shooting at?',
        'remind me of the camera settings',
        'where is focus set?',
    ],
    'set_dressing': [
        'how did we set up the Solaris set dressing?',
        'where do the set pieces live on the stage?',
        'what did we decide about payloads?',
        'how is the set organised in Solaris?',
        'where are the hero assets in the stage?',
    ],
    'render': [
        'what render settings did we decide on?',
        'how many samples are we rendering with?',
        'which renderer are we using?',
        'is the denoiser on?',
        'what resolution are the final renders?',
        'remind me of the karma settings',
    ],
    'scatter': [
        'how many pebbles did we scatter?',
        'what did we decide about the scatter?',
        'what seed is the pebble scatter on?',
        "what's the scatter density on the ground?",
        'remind me of the gravel setup',
    ],
    'naming': [
        "what's our naming convention?",
        'how should I name materials?',
        'what prefix do lights get?',
        'remind me of the node naming rules',
        'what did we decide about naming?',
    ],
    'fog': [
        'did we decide on fog?',
        'how dense is the fog?',
        'where is the volumetric fog?',
        'what did we decide about atmosphere?',
        'is there fog behind the plinth?',
    ],
    'frames': [
        "what's the frame range?",
        'what fps are we at?',
        'is motion blur on?',
        'what shutter did we pick for motion blur?',
        'remind me of the frame range decision',
    ],
    'color': [
        'what color space are we working in?',
        "what's the color pipeline?",
        'which display view do we use?',
        'did we go ACES?',
        'remind me of the OCIO decision',
    ],
    'backdrop': [
        "what's the backdrop?",
        'what did we decide about the background?',
        'what color is the cyc?',
        'remind me about the backdrop decision',
        'is there a vignette on the backdrop?',
    ],
}

XFAIL_POSITIVE = {
    'how are we lighting the scene?': "homonym: 'light volumetric fog' outranks the key light",
    "what's the lighting setup?": "homonym: 'light volumetric fog' outranks the key light",
    'what aperture are we shooting at?': 'synonym: aperture vs f/2.8, beyond word matching',
    'where is focus set?': 'one of two words per record: focus (camera) vs set (set dressing)',
    'remind me of the OCIO decision': 'synonym: OCIO vs ACES, beyond word matching',
}

NEGATIVES_FULL = [
    'oral',
    'what did we decide about the oral presentation?',
    'what did we decide about the explosion sim?',
    'which ocean spectrum did we pick?',
    "what's the hair groom density?",
    'what did we decide about the crowd agents?',
    'remind me of the pyro voxel size',
    'how many RBD pieces did we fracture?',
    'what audio track are we using?',
    "what's the deadline for the client?",
    'what did we decide about the torus animation?',
    'which HDRI did we reject?',
    'what lens did we use on the turntable camera?',
    'what material is the plinth?',
    'how many samples for the preview renders?',
]

XFAIL_NEGATIVE = {
    'what material is the plinth?': 'the look decision names a shader and the plinth',
}

NEGATIVES_EMPTY = ['what did we decide about the hero sphere?', "what's the frame range?", 'coral', 'remind me', 'what render settings did we decide on?']


@pytest.fixture
def memory(monkeypatch, tmp_path):
    monkeypatch.setattr(memory_store, "HOU_AVAILABLE", False)
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "jsonl")
    instance = memory_store.SynapseMemory(str(tmp_path))
    yield instance
    instance.save()


@pytest.fixture
def filled(memory):
    # Same content shape as SynapseMemory.decision(); one minute apart, in
    # the eval's deposit order.
    for minute, (key, decision, reasoning) in enumerate(DEPOSITS):
        stamp = f"2026-10-07T10:{minute:02d}:00"
        memory.store.add(Memory(
            id=key, created_at=stamp, updated_at=stamp,
            content=f"**Decision:** {decision}\n**Reasoning:** {reasoning}",
            memory_type=MemoryType.DECISION,
        ))
    return memory


def _mark(question, reasons):
    if question in reasons:
        return pytest.param(question, marks=pytest.mark.xfail(reason=reasons[question], strict=False))
    return question


@pytest.mark.parametrize("key, question", [
    pytest.param(key, q, marks=pytest.mark.xfail(reason=XFAIL_POSITIVE[q], strict=False))
    if q in XFAIL_POSITIVE else (key, q)
    for key, qs in QUESTIONS.items() for q in qs
])
def test_natural_question_finds_its_decision_first(filled, key, question):
    recalled = filled.recall(question)
    assert recalled and recalled[0].id == key, [m.id for m in recalled]


@pytest.mark.parametrize("question", [_mark(q, XFAIL_NEGATIVE) for q in NEGATIVES_FULL])
def test_unrecorded_question_finds_nothing(filled, question):
    assert filled.recall(question) == []


@pytest.mark.parametrize("question", NEGATIVES_EMPTY)
def test_empty_store_finds_nothing(memory, question):
    assert memory.recall(question) == []
