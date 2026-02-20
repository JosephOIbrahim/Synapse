# CHOPs (Channel Operators) Reference

## Triggers

chops channel operators animation noise wave lag spring filter export chop wrangle vex audio spectrum
frequency analysis motion capture mocap constraint lookat follow path camera shake procedural motion
secondary animation jiggle trigger envelope audio reactive chinput chstart chend chrate chnum
channelwrangle geometry chop sop to chop chop to sop export flag bake keyframes resample trim shift

## Context

CHOPs = Channel Operators. Time-based 1D data arrays sampled at a uniform rate. Located at `/ch`
or inside `chopnet` nodes. Each node outputs named channels over a time range at a given sample rate.

## Code

```python
# ── Node type strings for hou.node().createNode() ─────────────────────────────

CHOP_GENERATORS = {
    "constant":    "Output fixed value(s); one channel per value",
    "noise":       "Procedural noise: Perlin, Sparse, Alligator, Simplex",
    "wave":        "Periodic waveforms: sine, square, triangle, sawtooth, pulse",
    "channel":     "Fetch animated parameters from any scene node as channels",
    "expression":  "Evaluate Hscript expressions per sample",
    "pattern":     "Generate ramps, steps, random sequences",
    "object":      "Extract tx ty tz rx ry rz sx sy sz from OBJ nodes",
    "geometry":    "Read SOP point/prim/detail attributes as channels",
    "audiofilein": "Load audio files: WAV, AIFF, MP3",
    "audioin":     "Real-time audio input from system microphone/device",
    "midiin":      "Real-time MIDI input",
    "keyboard":    "Keyboard press events as channels",
    "mouse":       "Mouse position and button states",
}

CHOP_FILTERS = {
    "lag":      "Smooth transitions with configurable rise/fall times",
    "spring":   "Physical spring: overshoot, oscillation, damping",
    "filter":   "Low-pass, high-pass, band-pass, band-stop frequency filtering",
    "smooth":   "Rolling average — good for noisy mocap",
    "limit":    "Clamp or loop channel values within a range",
    "slope":    "Compute velocity (first derivative) of a channel",
    "speed":    "Integrate velocity → position, or differentiate position → speed",
    "resample": "Change sample rate; interpolation: linear, cubic, none",
    "trim":     "Trim or extend the time range of channels",
    "shift":    "Time-shift channels forward or backward",
    "stretch":  "Time-stretch or compress channels (speed up / slow down)",
    "trigger":  "Detect threshold crossings → attack/sustain/release envelopes",
    "envelope": "Extract amplitude envelope from a signal",
    "trail":    "Accumulate recent values into a trailing window",
    "jiggle":   "Add secondary jiggle based on velocity/acceleration",
}

CHOP_COMBINERS = {
    "math":     "Arithmetic: add, subtract, multiply, fit, clamp; multi-input",
    "merge":    "Combine channels from multiple inputs into one output",
    "blend":    "Weighted blend between inputs — slider-driven crossfade",
    "sequence": "Concatenate channel clips end-to-end over time",
    "cycle":    "Repeat channel data cyclically",
    "switch":   "Select one input based on animatable index",
    "comp":     "Layer channels with blend modes: add, multiply, replace",
    "copy":     "Duplicate and offset channels across multiple copies",
}

CHOP_CONSTRAINTS = {
    "constraintlookat":   "Aim object at a target; params: aimaxis, upaxis, upvector",
    "constraintpath":     "Move object along a curve; param: position (0-1 along path)",
    "constraintobject":   "Maintain offset from a target object's transform",
    "constraintblend":    "Blend between multiple constraint targets with weights",
    "constraintpoints":   "Constrain to SOP point positions",
    "constraintsurface":  "Constrain to SOP surface position (uv parametric)",
    "constraintparent":   "Parent-child relationship between objects",
}

CHOP_OUTPUT = {
    "null":   "Output marker and export target",
    "export": "Push channel values to scene parameters; toggle: export flag",
    "rename": "Rename channels; supports wildcards: 'tx ty tz' → 'rx ry rz'",
}
```

```python
# ── VEX CHOP context globals ────────────────────────────────────────────────
# Available in channelwrangle nodes (runs per sample per channel)

VEX_CHOP_GLOBALS = {
    "@C":          "float  — current channel value (read/write)",
    "@I":          "int    — current sample index (0-based)",
    "@Time":       "float  — current time in seconds at this sample",
    "@TimeInc":    "float  — time increment between samples (1 / sample_rate)",
    "@SampleRate": "float  — sample rate of the channel",
    "@numSamples": "int    — total number of samples in the channel",
    "@channum":    "int    — index of current channel (0-based)",
    "@channame":   "string — name of current channel",
}

VEX_CHOP_FUNCTIONS = {
    "chinput(input, chanidx, sample)":  "Read channel value from input by index",
    'chinput(input, "name", sample)':   "Read channel value from input by name",
    "chend(input)":                     "End sample of input",
    "chstart(input)":                   "Start sample of input",
    "chrate(input)":                    "Sample rate of input",
    "chnum(input)":                     "Number of channels on input",
    "chname(input, index)":             "Channel name by index",
}
```

```python
# ── Shared CHOP parameter names (most generator/filter nodes) ────────────────

CHOP_SHARED_PARMS = {
    "start":       "Channel start (seconds or frames depending on units)",
    "end":         "Channel end",
    "rate":        "Samples per second (default: scene FPS)",
    "left":        "Extend left: Hold | Slope | Cycle | Mirror | Default",
    "right":       "Extend right: Hold | Slope | Cycle | Mirror | Default",
    "channelname": "Output channel name(s)",
    "units":       "Frames | Seconds | Samples",
}

NOISE_CHOP_PARMS = {
    "type":       "Sparse | Perlin | Original Perlin | Alligator | Simplex | Zero-Centered",
    "amp":        "Signal amplitude",
    "period":     "Noise period (seconds)",
    "offset":     "Time offset for seed/phase control",
    "rough":      "Fractal roughness (0-1)",
    "turb":       "Number of fractal octaves",
    "seed":       "Random seed",
    "constraint": "None | Zero-Slope Start | Zero-Slope End | Zero-Slope Both",
}

LAG_CHOP_PARMS = {
    "lagrise":       "Time to reach rising target (seconds)",
    "lagfall":       "Time to reach falling target (seconds)",
    "overshootrise": "Overshoot on rise (0=none, 1=full)",
    "overshootfall": "Overshoot on fall",
    "clampmin":      "Minimum output value",
    "clampmax":      "Maximum output value",
}

SPRING_CHOP_PARMS = {
    "springk":  "Spring stiffness (higher = snappier return)",
    "mass":     "Object mass (higher = slower, more overshoot)",
    "damping":  "Damping coefficient (higher = less oscillation)",
    "initval":  "Starting value",
}

TRIGGER_CHOP_PARMS = {
    "threshold":    "Trigger fires when input crosses this value",
    "triggeron":    "Rising Edge | Falling Edge | Both",
    "attack":       "Attack time (seconds)",
    "sustain":      "Sustain length (seconds, or hold while above threshold)",
    "release":      "Release/decay time (seconds)",
    "attackshape":  "Linear | Ease In | Ease Out | Ease In/Out",
    "peakvalue":    "Maximum value during attack/sustain",
    "releaseshape": "Linear | Ease In | Ease Out | Exponential",
}

MATH_CHOP_PARMS = {
    "channelop": "Off | Add | Subtract | Multiply | Divide | Fit | Clamp ...",
    "gain":      "Multiplier (default 1.0)",
    "offset":    "Additive offset (default 0.0)",
    "frommin":   "Input range min for Fit operation",
    "frommax":   "Input range max for Fit operation",
    "tomin":     "Output range min for Fit operation",
    "tomax":     "Output range max for Fit operation",
    "align":     "Combine inputs: Extend | Trim | Match",
    "multop":    "Multi-input op: Add | Multiply | Average | Min | Max",
}

FILTER_CHOP_PARMS = {
    "type":       "Low Pass | High Pass | Band Pass | Band Stop",
    "cutofffreq": "Cutoff frequency in Hz",
    "bandwidth":  "Bandwidth for band-pass/band-stop (Hz)",
    "order":      "Filter steepness (higher = sharper rolloff)",
    "passtype":   "Butterworth | Chebyshev | Bessel",
}
```

```python
# ── Python: create a full camera-shake CHOP chain at /ch/cam_shake ───────────
import hou

def build_camera_shake_chopnet(cam_path="/obj/cam1", amp=0.02, period=0.2):
    """
    noise -> lag -> export  (drives cam tx, ty)
    amp   : shake amplitude in world units (0.02 = subtle, 0.15 = earthquake)
    period: noise period in seconds  (0.15-0.3 = 3-8 Hz range)
    """
    ch_net = hou.node("/ch")
    if ch_net is None:
        ch_net = hou.node("/").createNode("chopnet", "ch")

    net = ch_net.createNode("chopnet", "cam_shake")

    # Noise generator — two channels for X and Y shake
    noise = net.createNode("noise", "shake_noise")
    noise.parm("type").set(0)          # Sparse
    noise.parm("amp").set(amp)
    noise.parm("period").set(period)
    noise.parm("rough").set(0.5)
    noise.parm("turb").set(3)
    noise.parm("seed").set(42)
    noise.parmTuple("channelname").set(("tx", "ty"))  # two channels

    # Lag for subtle smoothing
    lag = net.createNode("lag", "shake_lag")
    lag.parm("lagrise").set(0.03)
    lag.parm("lagfall").set(0.03)
    lag.setInput(0, noise)

    # Null as export target
    out = net.createNode("null", "OUT")
    out.setInput(0, lag)

    # Enable export to camera
    out.parm("export").set(1)
    out.parm("exportpath").set(cam_path)

    net.layoutChildren()
    return net
```

```python
# ── Python: fetch animated channels, apply lag, re-export ────────────────────
import hou

def add_lag_to_animation(node_path="/obj/geo1", parms=("tx", "ty", "tz"),
                          lag_rise=0.15, lag_fall=0.15):
    """
    channel (fetch keyframes) -> lag -> export (override original node)
    Applies non-destructive lag smoothing to existing animation.
    """
    ch_net = hou.node("/ch")
    if ch_net is None:
        ch_net = hou.node("/").createNode("chopnet", "ch")

    net = ch_net.createNode("chopnet", "lag_anim")

    # Fetch animated parameters
    fetch = net.createNode("channel", "fetch")
    fetch.parm("nodepath").set(node_path)
    fetch.parm("channelnames").set(" ".join(parms))

    # Lag
    lag = net.createNode("lag", "smooth_lag")
    lag.parm("lagrise").set(lag_rise)
    lag.parm("lagfall").set(lag_fall)
    lag.setInput(0, fetch)

    # Export back to source node
    out = net.createNode("null", "OUT")
    out.setInput(0, lag)
    out.parm("export").set(1)
    out.parm("exportpath").set(node_path)

    net.layoutChildren()
    return net
```

```python
# ── Python: bake CHOP output back to keyframes ───────────────────────────────
import hou

def bake_chop_to_keyframes(chop_null_path, target_parm_path, frame_start=None, frame_end=None):
    """
    Bakes every sample in a CHOP null to keyframes on a scene parameter.
    chop_null_path  : e.g. "/ch/cam_shake/OUT"
    target_parm_path: e.g. "/obj/cam1/tx"
    """
    chop_node = hou.node(chop_null_path)
    target_parm = hou.parm(target_parm_path)

    if chop_node is None:
        raise ValueError(f"CHOP node not found: {chop_null_path}")
    if target_parm is None:
        raise ValueError(f"Parameter not found: {target_parm_path}")

    # Determine channel name from the last path component of parm
    chan_name = target_parm_path.rsplit("/", 1)[-1]

    sample_start = int(chop_node.sampleRange()[0])
    sample_end   = int(chop_node.sampleRange()[1])

    if frame_start is not None:
        sample_start = max(sample_start, int(frame_start))
    if frame_end is not None:
        sample_end = min(sample_end, int(frame_end))

    target_parm.deleteAllKeyframes()

    for sample in range(sample_start, sample_end + 1):
        time = chop_node.sampleToTime(sample)
        val  = chop_node.sample(time, chan_name)
        key  = hou.Keyframe()
        key.setTime(time)
        key.setValue(val)
        key.setExpression("bezier()")
        target_parm.setKeyframe(key)

    return sample_end - sample_start + 1  # number of keyframes set
```

```python
# ── Python: read CHOP value at current time (for LOP/SOP Python nodes) ───────
import hou

def get_chop_value(chop_path, channel_name, time=None):
    """
    Read a single channel value from a CHOP at the given time.
    Falls back to current scene time if time is None.
    chop_path    : e.g. "/ch/cam_shake/OUT"
    channel_name : e.g. "tx"
    """
    if time is None:
        time = hou.time()
    node = hou.node(chop_path)
    if node is None:
        raise ValueError(f"CHOP node not found: {chop_path}")
    return node.sample(time, channel_name)

# In a parameter expression field:
#   chop("/ch/chopnet1/null1/tx")
#   chop("../lag1/tx")           <- relative path form
```

```python
# ── Python: build an audio-reactive light-exposure chain ─────────────────────
import hou

def build_audio_reactive_light(audio_file, light_path="/obj/light1",
                                 lo_freq=80.0, hi_freq=200.0,
                                 gain=5.0, lag_rise=0.02, lag_fall=0.1,
                                 exp_min=2.0, exp_max=8.0):
    """
    audiofilein -> filter(band-pass bass) -> math(abs + gain)
                -> lag(attack/release) -> math(fit → exposure range)
                -> export(light exposure parm)

    Network:  /ch/audio_light/
    """
    ch_net = hou.node("/ch")
    if ch_net is None:
        ch_net = hou.node("/").createNode("chopnet", "ch")

    net = ch_net.createNode("chopnet", "audio_light")

    # Load audio
    audio_in = net.createNode("audiofilein", "audio")
    audio_in.parm("file").set(audio_file)

    # Band-pass filter — isolate bass frequencies
    bp = net.createNode("filter", "bass_filter")
    bp.parm("type").set(2)                 # Band Pass
    bp.parm("cutofffreq").set((lo_freq + hi_freq) / 2.0)
    bp.parm("bandwidth").set(hi_freq - lo_freq)
    bp.parm("order").set(4)
    bp.setInput(0, audio_in)

    # Rectify (abs) and apply gain
    rectify = net.createNode("math", "rectify")
    rectify.parm("channelop").set("abs")
    rectify.setInput(0, bp)

    gain_node = net.createNode("math", "gain_scale")
    gain_node.parm("channelop").set("multiply")
    gain_node.parm("gain").set(gain)
    gain_node.setInput(0, rectify)

    # Lag for smooth attack/release envelope
    lag = net.createNode("lag", "env_lag")
    lag.parm("lagrise").set(lag_rise)
    lag.parm("lagfall").set(lag_fall)
    lag.setInput(0, gain_node)

    # Fit 0-1 → exposure range
    fit = net.createNode("math", "fit_exposure")
    fit.parm("channelop").set("fit")
    fit.parm("frommin").set(0.0)
    fit.parm("frommax").set(1.0)
    fit.parm("tomin").set(exp_min)
    fit.parm("tomax").set(exp_max)
    fit.setInput(0, lag)

    # Rename channel to match exposure parm name
    ren = net.createNode("rename", "to_exposure")
    ren.parm("renamefrom").set("chan1")
    ren.parm("renameto").set("xn__inputsexposure_vya")
    ren.setInput(0, fit)

    # Export to light node
    out = net.createNode("null", "OUT")
    out.setInput(0, ren)
    out.parm("export").set(1)
    out.parm("exportpath").set(light_path)

    net.layoutChildren()
    return net
```

```python
# ── Python: geometry CHOP — read SOP point positions as channels ─────────────
import hou

def sop_attrib_to_chop(sop_path, attrib_name="P", attrib_type="point",
                        net_parent_path="/ch"):
    """
    geometry CHOP: one channel per attribute component per element.
    For @P on 100 points → channels: P:0:x P:0:y P:0:z P:1:x ...
    """
    ATTRIB_TYPES = {"point": 0, "primitive": 1, "vertex": 2, "detail": 3}

    ch_net = hou.node(net_parent_path)
    if ch_net is None:
        ch_net = hou.node("/").createNode("chopnet", "ch")

    geo_chop = ch_net.createNode("geometry", "sop_reader")
    geo_chop.parm("soppath").set(sop_path)
    geo_chop.parm("attribscope").set(attrib_name)
    geo_chop.parm("attribtype").set(ATTRIB_TYPES.get(attrib_type, 0))

    return geo_chop

# chop_to_sop (SOP side): reads channels back as point attributes
def chop_to_sop_example():
    """
    In a SOPs network, add a 'choptosop' node.
    choppath: path to CHOP null, e.g. "/ch/analysis/OUT"
    Each channel → a point attribute; each sample → a point.
    Useful for waveform visualization, audio-reactive geometry.
    """
    obj = hou.node("/obj")
    geo = obj.createNode("geo", "wave_geo")
    c2s = geo.createNode("choptosop")
    c2s.parm("choppath").set("/ch/analysis/OUT")
    c2s.parm("createaliases").set(1)
    return c2s
```

```python
# ── Python: mocap cleanup pipeline ───────────────────────────────────────────
import hou

def build_mocap_cleanup(source_obj_path, smooth_width=5, cutoff_hz=12.0,
                         lag_time=0.08):
    """
    fetch (raw mocap) -> smooth -> filter(low-pass) -> lag -> null(export)
    Removes high-frequency jitter while preserving natural motion.
    smooth_width : samples to average (3-7 typical)
    cutoff_hz    : low-pass cutoff; 8-15 Hz removes finger jitter
    lag_time     : subtle easing in seconds (0.05-0.15)
    """
    ch_net = hou.node("/ch")
    if ch_net is None:
        ch_net = hou.node("/").createNode("chopnet", "ch")

    net = ch_net.createNode("chopnet", "mocap_cleanup")

    # Fetch all transform channels from source object
    fetch = net.createNode("channel", "raw_mocap")
    fetch.parm("nodepath").set(source_obj_path)
    fetch.parm("channelnames").set("tx ty tz rx ry rz")

    # Rolling average — removes sample-to-sample noise
    smooth = net.createNode("smooth", "avg_smooth")
    smooth.parm("width").set(smooth_width)
    smooth.parm("type").set(0)  # Gaussian
    smooth.setInput(0, fetch)

    # Low-pass filter — removes high-frequency jitter
    lp = net.createNode("filter", "lp_filter")
    lp.parm("type").set(0)  # Low Pass
    lp.parm("cutofffreq").set(cutoff_hz)
    lp.parm("order").set(4)
    lp.setInput(0, smooth)

    # Lag — subtle easing on transitions
    lag = net.createNode("lag", "ease_lag")
    lag.parm("lagrise").set(lag_time)
    lag.parm("lagfall").set(lag_time)
    lag.setInput(0, lp)

    out = net.createNode("null", "OUT")
    out.setInput(0, lag)
    out.parm("export").set(1)
    out.parm("exportpath").set(source_obj_path)

    net.layoutChildren()
    return net
```

```python
# ── Python: velocity / acceleration analysis via slope CHOP ─────────────────
import hou

def build_velocity_chain(tracked_obj="/obj/ball"):
    """
    object -> slope(vel) -> slope(accel) -> null
    Use peaks in acceleration to trigger secondary effects (dust, impact).
    """
    ch_net = hou.node("/ch")
    if ch_net is None:
        ch_net = hou.node("/").createNode("chopnet", "ch")

    net = ch_net.createNode("chopnet", "vel_analysis")

    obj_chop = net.createNode("object", "track_pos")
    obj_chop.parm("rootobject").set(tracked_obj)
    obj_chop.parm("xord").set("srt")

    vel = net.createNode("slope", "velocity")
    vel.setInput(0, obj_chop)

    accel = net.createNode("slope", "acceleration")
    accel.setInput(0, vel)

    out = net.createNode("null", "OUT_accel")
    out.setInput(0, accel)

    net.layoutChildren()
    return net
```

```python
# ── Python: OBJ constraint network (lookat + blend) ──────────────────────────
import hou

def build_lookat_constraint(subject_obj="/obj/cam1", target_obj="/obj/target1",
                             aim_axis=(0, 0, -1), up_axis=(0, 1, 0)):
    """
    Creates a constraint CHOP network inside subject_obj.
    constraintlookat -> constraintblend -> null (output drives OBJ transforms)

    The constraint network's output channels (rx ry rz tx ty tz) override
    the OBJ node transforms automatically when 'Use Constraint Network' is on.
    """
    subj = hou.node(subject_obj)
    if subj is None:
        raise ValueError(f"Object not found: {subject_obj}")

    # Enable constraint network on the OBJ
    subj.parm("constraints_on").set(1)

    # Find or create the constraint CHOP network
    cnet = subj.node("constraints")
    if cnet is None:
        cnet = subj.createNode("chopnet", "constraints")

    lookat = cnet.createNode("constraintlookat", "look_at_target")
    lookat.parm("target").set(target_obj)
    lookat.parm("aimaxis").set(f"{aim_axis[0]} {aim_axis[1]} {aim_axis[2]}")
    lookat.parm("upaxis").set(f"{up_axis[0]} {up_axis[1]} {up_axis[2]}")

    # Blend node (allows mixing with other constraints by weight)
    blend = cnet.createNode("constraintblend", "blend")
    blend.setInput(0, lookat)
    blend.parm("weight0").set(1.0)

    out = cnet.createNode("null", "output0")
    out.setInput(0, blend)
    out.setDisplayFlag(True)
    out.setRenderFlag(True)

    cnet.layoutChildren()
    return cnet
```

```python
# ── Python: noise CHOP — camera shake settings presets ───────────────────────
import hou

CAMERA_SHAKE_PRESETS = {
    # name: (amp, period, rough, turb)
    "subtle":     (0.005, 0.25,  0.5, 2),
    "handheld":   (0.02,  0.18,  0.6, 3),
    "action":     (0.06,  0.12,  0.7, 4),
    "earthquake": (0.20,  0.08,  0.8, 5),
}

def apply_shake_preset(noise_chop_path, preset_name="handheld"):
    node = hou.node(noise_chop_path)
    if node is None:
        raise ValueError(f"CHOP not found: {noise_chop_path}")
    amp, period, rough, turb = CAMERA_SHAKE_PRESETS[preset_name]
    node.parm("amp").set(amp)
    node.parm("period").set(period)
    node.parm("rough").set(rough)
    node.parm("turb").set(turb)
    return node
```

```vex
// ── channelwrangle: fade in over first 2 seconds ────────────────────────────
float fade = clamp(@Time / 2.0, 0.0, 1.0);
@C *= fade;
```

```vex
// ── channelwrangle: add procedural noise jitter ──────────────────────────────
// Uses channel index as a seed offset so each channel gets different noise
float n = noise(@Time * 5.0 + @channum * 100.0) - 0.5;
@C += n * 0.1;
```

```vex
// ── channelwrangle: clamp channel values ────────────────────────────────────
@C = clamp(@C, -1.0, 1.0);
```

```vex
// ── channelwrangle: remap input range to output range ───────────────────────
// fit(value, srcmin, srcmax, dstmin, dstmax)
@C = fit(@C, -1.0, 1.0, 0.0, 10.0);
```

```vex
// ── channelwrangle: only affect rotation channels ───────────────────────────
// match() supports glob patterns: r? matches rx ry rz
if (match("r?", @channame)) {
    @C *= 0.5;  // halve all rotation values
}
```

```vex
// ── channelwrangle: simple damped spring (stateful) ─────────────────────────
// chinput(-1, ...) reads the OUTPUT of this wrangle (previous sample feedback)
// Use with caution — requires serial evaluation
float target  = chinput(0, @channum, @I);
float prev    = @I > 0 ? chinput(-1, @channum, @I - 1) : target;
float vel     = @I > 1 ? prev - chinput(-1, @channum, @I - 2) : 0.0;
float springk = 0.3;
float damp    = 0.8;
float force   = (target - prev) * springk;
vel           = (vel + force) * damp;
@C            = prev + vel;
```

```vex
// ── channelwrangle: compute 3D distance from three channels ─────────────────
// Read tx ty tz from input 0 at the current sample index
float tx = chinput(0, "tx", @I);
float ty = chinput(0, "ty", @I);
float tz = chinput(0, "tz", @I);
@C = sqrt(tx*tx + ty*ty + tz*tz);
```

```vex
// ── channelwrangle: per-sample windowed processing ──────────────────────────
// Only process samples within a time window (1.0s to 3.0s)
if (@Time >= 1.0 && @Time <= 3.0) {
    float t = fit(@Time, 1.0, 3.0, 0.0, 1.0);  // 0-1 within window
    @C *= sin(t * 3.14159);                      // bell-shaped envelope
}
```

```vex
// ── channelwrangle: cross-channel blend ─────────────────────────────────────
// Blend channel 0 and channel 1 from input, output into current channel
float a = chinput(0, 0, @I);   // first channel
float b = chinput(0, 1, @I);   // second channel
float w = fit(@Time, 0.0, 5.0, 0.0, 1.0);  // animate blend weight over 5s
@C = lerp(a, b, w);
```

```python
# ── Python: list all channels on a CHOP node ─────────────────────────────────
import hou

def inspect_chop_channels(chop_path):
    node = hou.node(chop_path)
    if node is None:
        raise ValueError(f"CHOP not found: {chop_path}")

    info = {
        "channel_count": node.numChans(),
        "sample_range":  node.sampleRange(),     # (start_sample, end_sample)
        "sample_rate":   node.sampleRate(),
        "channels": []
    }
    for i in range(node.numChans()):
        ch = node.chan(i)
        info["channels"].append({
            "name":   ch.name(),
            "length": ch.numSamples(),
            "min":    min(ch.evalAtSample(s) for s in range(ch.numSamples())),
            "max":    max(ch.evalAtSample(s) for s in range(ch.numSamples())),
        })
    return info

# Sample a CHOP channel at a specific frame
def sample_at_frame(chop_path, channel_name, frame):
    node = hou.node(chop_path)
    time = hou.frameToTime(frame)
    return node.sample(time, channel_name)
```

```python
# ── Python: disable / remove export from a CHOP to reclaim a parameter ───────
import hou

def remove_chop_export(chop_null_path):
    """
    Disables export flag so the parameter returns to its keyframed value.
    After export is removed the parameter may appear 'stuck' at last value —
    manually type a new value or set a keyframe to reclaim it.
    """
    node = hou.node(chop_null_path)
    if node is None:
        raise ValueError(f"CHOP not found: {chop_null_path}")
    node.parm("export").set(0)
    print(f"Export disabled on {chop_null_path}. "
          f"Manually set a keyframe on the target parameter to reclaim it.")
```

## Common Mistakes

```python
# WRONG: channel name "translatex" does not match parm name "tx"
# Export silently does nothing
export_node.parm("exportpath").set("/obj/geo1")
# channel named "translatex" — will NOT drive parm "tx"

# CORRECT: channel name must exactly match the parameter name
# Use rename CHOP to fix naming before export
rename_node.parm("renamefrom").set("translatex")
rename_node.parm("renameto").set("tx")
```

```python
# WRONG: two CHOP networks exporting to the same parameter
# Last one wins, Houdini warns but does not error
net_a_out.parm("exportpath").set("/obj/geo1")  # exports "tx"
net_b_out.parm("exportpath").set("/obj/geo1")  # also exports "tx" — conflict!

# CORRECT: only one CHOP network should export to a given parameter
# Merge the chains before the single export null
```

```python
# WRONG: downsampling audio to scene FPS before spectrum analysis
# destroys frequency content above (FPS/2) Hz — Nyquist limit
audio_in = net.createNode("audiofilein", "audio")
resample_early = net.createNode("resample", "bad_resample")
resample_early.parm("rate").set(24)  # destroys everything above 12 Hz!

# CORRECT: do frequency analysis at full 44100/48000 Hz,
# then only resample the RESULT (low-rate envelope) for scene export
spectrum_node.setInput(0, audio_in)          # full rate analysis
envelope = net.createNode("envelope", "env")
envelope.setInput(0, spectrum_node)
resample_after = net.createNode("resample", "to_fps")
resample_after.parm("rate").set(hou.fps())   # resample AFTER analysis
resample_after.setInput(0, envelope)
```

```python
# WRONG: using chinput(-1, ...) in a wrangle without understanding feedback
# chinput(-1, channum, I) reads from THIS wrangle's own previous output
# Not the same as reading the upstream input's previous sample
# This creates a feedback loop — valid for spring, but unexpected otherwise

# CORRECT: use chinput(0, ...) to read from upstream input (no feedback)
# Use chinput(-1, ...) ONLY when intentional stateful feedback is needed
```

```python
# WRONG: geometry CHOP on a heavy mesh (100k points) reads all channels
# Creates 100k * 3 channels = 300k channels — extremely slow
geo_chop.parm("attribscope").set("*")  # reads every attribute

# CORRECT: scope to only needed attributes and limit point range
geo_chop.parm("attribscope").set("P N")         # only position and normal
geo_chop.parm("attribtype").set(3)               # detail attrib when possible
```

```python
# WRONG: trail CHOP with long trail on a high-sample-rate chain eats memory
# At 44100 Hz with a 10s trail = 441,000 samples stored per channel
trail.parm("length").set(10.0)  # 10 seconds at audio rate

# CORRECT: resample to scene FPS before the trail
resample = net.createNode("resample")
resample.parm("rate").set(hou.fps())  # 24/30/60 FPS
resample.setInput(0, upstream)
trail.setInput(0, resample)           # trail at scene rate, not audio rate
```

```python
# WRONG: noise CHOP looks the same every take because seed is 0 default
noise.parm("seed").set(0)  # produces identical noise every time

# CORRECT: vary seed or use $OS (operator string / node name hash)
noise.parm("seed").setExpression("opinputpath('.', 0) != '' ? 0 : $OS")
# Or simply set a distinct integer seed per noise node
noise.parm("seed").set(17)
```

```python
# WRONG: Spring CHOP never settles — damping too low or mass too high
spring.parm("damping").set(0.05)  # barely damps — oscillates forever
spring.parm("mass").set(100.0)    # huge mass = huge overshoot

# CORRECT: damping >= 0.5 for most use cases; mass 0.1-2.0 range
spring.parm("damping").set(0.7)
spring.parm("mass").set(0.5)
```
