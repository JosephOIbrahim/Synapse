# CHOPs (Channel Operators) Reference

## Overview

CHOPs = Channel Operators. Houdini's context for manipulating time-based channel data: animation curves, audio waveforms, motion capture streams, procedural signals, and constraint networks. Located at `/ch` or inside `chopnet` nodes at OBJ/SOP level.

Each CHOP node outputs one or more **channels** — named 1D data arrays sampled at a uniform rate. Channels carry values over a time range (start/end) at a given sample rate (default: scene FPS). CHOPs can be wired together to filter, combine, blend, and export channel data back into the scene.

### When to Use CHOPs
- **Audio-reactive animation**: Drive parameters from audio frequency/amplitude
- **Procedural motion**: Generate noise-based, spring-based, or wave-based animation without keyframes
- **Channel filtering**: Smooth, lag, or constrain animated parameters after keyframing
- **Motion capture cleanup**: Import, retarget, and filter mocap data
- **Constraint systems**: Build OBJ-level constraints (Look At, Follow Path, Blend)
- **Real-time device input**: MIDI, OSC, joystick, mouse input
- **Parameter export**: Override any scene parameter with CHOP-driven values

### CHOP Context Globals (VEX)
| Variable | Type | Description |
|----------|------|-------------|
| `@C` | float | Current channel value at the current sample |
| `@I` | int | Current sample index |
| `@Time` | float | Current time (seconds) |
| `@TimeInc` | float | Time increment between samples (1/sample_rate) |
| `@SampleRate` | float | Sample rate of the channel |
| `@numSamples` | int | Total number of samples in the channel |
| `@channum` | int | Index of current channel (0-based) |
| `@channame` | string | Name of current channel |

## Key CHOP Node Types

### Generators (Create Channels)

| Node | Type String | Description |
|------|-------------|-------------|
| Constant | `constant` | Output fixed value(s). One channel per value. Use for static offsets or base values. |
| Noise | `noise` | Procedural noise curves. Supports Perlin, Sparse, Alligator, Simplex, etc. |
| Wave | `wave` | Periodic waveforms: sine, square, triangle, sawtooth, pulse. |
| Channel | `channel` | Fetch animated parameters from the scene as CHOP channels. |
| Expression | `expression` | Evaluate Hscript expressions per sample. Each channel defined by an expression string. |
| Pattern | `pattern` | Generate patterns: ramps, steps, random sequences. |
| Object | `object` | Extract transform channels (tx ty tz rx ry rz sx sy sz) from OBJ nodes. |
| Geometry | `geometry` | Read SOP point/prim/detail attributes as CHOP channels. |
| Audio File In | `audifilein` | Load audio files (WAV, AIFF, MP3). |
| Audio In | `audioin` | Real-time audio input from system microphone/device. |
| MIDI In | `midiin` | Real-time MIDI input from MIDI devices. |
| Keyboard | `keyboard` | Keyboard press events as channels. |
| Mouse | `mouse` | Mouse position and button states. |

### Filters (Modify Channels)

| Node | Type String | Description |
|------|-------------|-------------|
| Lag | `lag` | Smooth transitions with configurable rise/fall times. Essential for easing. |
| Spring | `spring` | Physical spring simulation — overshoot, oscillation, damping. |
| Filter | `filter` | Low-pass, high-pass, band-pass, band-stop frequency filtering. |
| Smooth | `smooth` | Rolling average smoothing. Good for noisy mocap data. |
| Limit | `limit` | Clamp or loop channel values within a range. |
| Slope | `slope` | Compute velocity (first derivative) of a channel. |
| Speed | `speed` | Integrate velocity to get position, or differentiate position to get speed. |
| Resample | `resample` | Change sample rate. Interpolation: linear, cubic, or no interpolation. |
| Trim | `trim` | Trim or extend the time range of channels. |
| Shift | `shift` | Time-shift channels forward or backward. |
| Stretch | `stretch` | Time-stretch or compress channels (speed up / slow down). |
| Trigger | `trigger` | Detect threshold crossings and generate attack/sustain/release envelopes. |
| Envelope | `envelope` | Extract amplitude envelope from a signal. |
| Trail | `trail` | Accumulate recent values into a trailing window (useful for visualization). |
| Jiggle | `jiggle` | Add secondary jiggle motion based on velocity/acceleration. |

### Combiners (Merge/Blend Channels)

| Node | Type String | Description |
|------|-------------|-------------|
| Math | `math` | Arithmetic operations: add, subtract, multiply, fit, clamp. Multi-input. |
| Merge | `merge` | Combine channels from multiple inputs into one output. |
| Blend | `blend` | Weighted blend between inputs. Slider-driven crossfade. |
| Sequence | `sequence` | Concatenate channel clips end-to-end over time. |
| Cycle | `cycle` | Repeat channel data cyclically. |
| Switch | `switch` | Select one input based on index (animatable). |
| Composite | `comp` | Layer channels using blend modes (add, multiply, replace). |
| Copy | `copy` | Duplicate and offset channels across multiple copies. |

### Constraints (OBJ-Level)

| Node | Type String | Description |
|------|-------------|-------------|
| Look At | `constraintlookat` | Aim object at a target. `aimaxis`, `upaxis`, `upvector` params. |
| Follow Path | `constraintpath` | Move object along a curve. `position` param (0-1 along path). |
| Object Offset | `constraintobject` | Maintain offset from a target object's transform. |
| Blend | `constraintblend` | Blend between multiple constraint targets with weights. |
| Points | `constraintpoints` | Constrain to SOP point positions. |
| Surface | `constraintsurface` | Constrain to SOP surface position (uv parametric). |
| Parent | `constraintparent` | Parent-child relationship between objects. |

### Output

| Node | Type String | Description |
|------|-------------|-------------|
| Null | `null` | Output marker. Use as export target. |
| Export | `export` | Push channel values to scene parameters. Active flag: `export` toggle. |
| Rename | `rename` | Rename channels. Supports wildcards: `tx ty tz` to `rx ry rz`. |

## CHOP to SOP/DOP/LOP Workflows

### Channel CHOP (Fetch Parameters into CHOPs)

The `channel` CHOP reads animated parameters from any node and exposes them as CHOP channels for filtering.

```
channel (fetch /obj/cam1 tx ty tz) -> lag (smooth) -> export (back to cam1 or elsewhere)
```

Key parameters on `channel` CHOP:
- `nodepath` - Node to fetch from (e.g., `/obj/cam1`)
- `channelnames` - Space-separated parameter names: `tx ty tz rx ry rz`

### Export CHOP (Push Values to Parameters)

The `export` CHOP overrides scene parameters with CHOP channel values. This is the primary way to drive parameters from CHOPs.

**Export method 1 — Export flag on null:**
1. Wire your CHOP chain into a `null`
2. Set the `export` toggle on the null (or on any CHOP)
3. Set `exportpath` to target node
4. Channel names must match parameter names (`tx`, `ry`, etc.)

**Export method 2 — Channel reference:**
In any parameter field, use:
```
chop("/ch/chopnet1/null1/tx")
```
or the short form:
```
chop("../chopnet1/filter1/tx")
```

**Export method 3 — CHOP Export SOP:**
The `chopexport` SOP reads CHOP data and applies it as point attributes.

### CHOP to SOP (Geometry from Channels)

The `choptosop` node in SOPs converts CHOP channel data to point geometry:
- Each channel becomes a point attribute
- Each sample becomes a point
- Useful for waveform visualization, audio-reactive geometry

Parameters:
- `choppath` - Path to CHOP node to read
- `createaliases` - Create attribute aliases from channel names

### SOP to CHOP (Geometry CHOP)

The `geometry` CHOP reads SOP attributes as CHOP channels:
- `soppath` - Path to SOP node
- `attribscope` - Which attributes to read (`*` for all, or specific names)
- `attribtype` - Point, Primitive, Vertex, or Detail

This creates one channel per attribute component per element. For `@P` on 100 points, you get channels: `P:0:x P:0:y P:0:z P:1:x ...`

### CHOP to DOP

Use `dopimport` CHOP to read DOP simulation data as channels, or use channel references:
```
chop("/ch/chopnet1/noise1/chan1")
```
in DOP parameter fields for procedural driving of forces, velocities, etc.

### CHOP in LOPs

In Solaris/LOPs, CHOPs integrate via Python expressions or parameter references:
```python
# In a Python LOP wrangle
import hou
val = hou.ch("/ch/chopnet1/null1/tx")
```

Or via channel reference expressions on LOP parameters:
```
chop("/ch/chopnet1/out/intensity")
```

## Audio Workflows

### Loading Audio

```
audiofilein -> null (output)
```

`audiofilein` parameters:
- `file` - Path to audio file (WAV, AIFF, MP3)
- `rate` - Override sample rate (typically 44100 or 48000)
- `mono` - Convert stereo to mono

### Real-Time Audio Input

```
audioin -> null
```

`audioin` parameters:
- `rate` - Sample rate (44100 default)
- `device` - Audio input device index
- `seglen` - Segment length in samples

### Audio Analysis Chain

```
audiofilein -> spectrum -> null
```

The `spectrum` CHOP performs FFT analysis:
- `fftsize` - FFT window size (256, 512, 1024, 2048). Larger = better frequency resolution, worse time resolution.
- `window` - Window function: Hanning, Hamming, Blackman, Rectangular
- `outputformat` - Magnitude, Phase, Power, dB

### Audio-to-Parameter Workflow

```
audiofilein -> filter (band-pass 80-200Hz) -> math (abs + gain) -> lag (smooth) -> export
```

1. **audiofilein**: Load the audio track
2. **filter**: Isolate frequency band (bass=20-200Hz, mids=200-2kHz, highs=2k-20kHz)
3. **math**: Rectify (absolute value) and scale (multiply gain)
4. **lag**: Smooth rapid fluctuations (lagrise=0.1, lagfall=0.2)
5. **export**: Push to parameter (e.g., light intensity, scale, displacement amplitude)

### Filter CHOP Parameters

| Parameter | Name | Description |
|-----------|------|-------------|
| Filter Type | `type` | Low Pass, High Pass, Band Pass, Band Stop |
| Cutoff | `cutofffreq` | Cutoff frequency in Hz |
| Bandwidth | `bandwidth` | Width for band-pass/band-stop (Hz) |
| Order | `order` | Filter steepness (higher = sharper rolloff) |
| Pass Type | `passtype` | Butterworth, Chebyshev, Bessel |

### Spectrum-Driven Multiple Bands

For multi-band audio reactivity, use parallel filter chains:
```
audiofilein -> filter(low-pass 200Hz)   -> math -> lag -> export (bass param)
            -> filter(band-pass 200-2k) -> math -> lag -> export (mid param)
            -> filter(high-pass 2kHz)   -> math -> lag -> export (treble param)
```

## Motion Analysis and Retargeting

### Importing Motion Capture

Motion capture data (BVH, FBX, C3D) arrives as animated channels on skeleton joints.

```
file (BVH) -> agent_bvhimport (SOP) -> geometry CHOP (extract channels)
```

Or directly in CHOPs:
```
fetch (from OBJ-level imported FBX skeleton) -> null
```

### Mocap Cleanup Pipeline

```
fetch (raw mocap channels) -> smooth (remove noise) -> filter (low-pass high-frequency jitter) -> lag (ease transitions) -> null (export)
```

Key parameters for cleanup:
- `smooth` CHOP: `width` (number of samples to average), `type` (gaussian, box)
- `filter` CHOP: `cutofffreq` (8-15 Hz removes finger jitter while preserving motion)
- `lag` CHOP: `lagrise` / `lagfall` (seconds, typically 0.05-0.15 for subtle smoothing)

### Channel Retargeting with Rename

Use `rename` CHOP to map channels between different skeleton naming conventions:
```
rename:  source:Hip_tx  -> target:Hips_tx
         source:Spine1  -> target:spine_01
```

Parameters:
- `renamefrom` - Source pattern (supports wildcards: `Left*`)
- `renameto` - Target pattern (`L_*`)

### Velocity and Acceleration Analysis

```
object (track moving OBJ) -> slope (velocity) -> slope (acceleration) -> null
```

The `slope` CHOP computes the derivative. Chain two for acceleration. Useful for:
- Detecting motion peaks for procedural effects (dust on foot plants)
- Triggering events when velocity exceeds threshold
- Analyzing simulation output for quality checks

## Keyframe and Channel Manipulation

### Fetching Keyframed Channels

```
channel -> null
```

The `channel` CHOP reads keyframed animation from any node:
- `nodepath` - Target node path
- `channelnames` - Whitespace-separated list of parameter names

### Modifying Keyframed Animation

```
channel (fetch keys) -> math (scale or offset) -> export (override original)
```

Common Math operations on animation:
- **Scale amplitude**: `channelop=multiply`, `gain=0.5` (halve motion)
- **Add offset**: `channelop=add`, `value=10` (shift up by 10 units)
- **Fit range**: `channelop=fit`, `frommin/frommax/tomin/tomax`
- **Clamp**: `channelop=clamp`, `min/max`

### Math CHOP Key Parameters

| Parameter | Name | Description |
|-----------|------|-------------|
| Channel Op | `channelop` | Off, Add, Subtract, Multiply, Divide, Fit, Clamp, etc. |
| Gain | `gain` | Multiplier (default 1.0) |
| Offset | `offset` | Additive offset (default 0.0) |
| From Range | `frommin` / `frommax` | Input range for Fit operation |
| To Range | `tomin` / `tomax` | Output range for Fit operation |
| Combine Inputs | `align` | How to combine multiple inputs: Extend, Trim, Match |
| Multi-Input Op | `multop` | Add, Multiply, Average, Min, Max across inputs |

### Baking CHOP to Keyframes

In Python, bake CHOP values back to keyframes:
```python
import hou

chop_node = hou.node("/ch/chopnet1/null1")
target_parm = hou.parm("/obj/geo1/tx")

for sample in range(int(chop_node.sampleRange()[0]), int(chop_node.sampleRange()[1]) + 1):
    time = chop_node.sampleToTime(sample)
    val = chop_node.sample(time, "tx")
    key = hou.Keyframe()
    key.setTime(time)
    key.setValue(val)
    target_parm.setKeyframe(key)
```

## Common Parameter Names in CHOPs

### Shared Across Most CHOPs

| Parameter | Name | Description |
|-----------|------|-------------|
| Start | `start` | Channel start (seconds or frames, depends on `units`) |
| End | `end` | Channel end |
| Sample Rate | `rate` | Samples per second (default: scene FPS) |
| Extend Left | `left` | Behavior before channel start: Hold, Slope, Cycle, Mirror, Default |
| Extend Right | `right` | Behavior after channel end |
| Channel Names | `channelname` | Output channel name(s) |
| Units | `units` | Frames, Seconds, or Samples |

### Noise CHOP

| Parameter | Name | Description |
|-----------|------|-------------|
| Type | `type` | Sparse, Perlin, Original Perlin, Alligator, Simplex, Zero-Centered |
| Amplitude | `amp` | Signal amplitude |
| Period | `period` | Noise period (seconds) |
| Offset | `offset` | Time offset for seed control |
| Roughness | `rough` | Fractal roughness (0-1) |
| Octaves | `turb` | Number of fractal octaves |
| Seed | `seed` | Random seed |
| Constraint | `constraint` | None, Zero-Slope Start, Zero-Slope End, Zero-Slope Both |

### Lag CHOP

| Parameter | Name | Description |
|-----------|------|-------------|
| Lag Rise | `lagrise` | Time to reach rising target (seconds) |
| Lag Fall | `lagfall` | Time to reach falling target (seconds) |
| Overshoot Rise | `overshootrise` | Overshoot on rise (0=none, 1=full) |
| Overshoot Fall | `overshootfall` | Overshoot on fall |
| Clamp Min | `clampmin` | Minimum output value |
| Clamp Max | `clampmax` | Maximum output value |

### Spring CHOP

| Parameter | Name | Description |
|-----------|------|-------------|
| Spring Constant | `springk` | Stiffness (higher = snappier return) |
| Mass | `mass` | Object mass (higher = slower, more overshoot) |
| Damping | `damping` | Damping coefficient (higher = less oscillation) |
| Initial Value | `initval` | Starting value |

### Trigger CHOP

| Parameter | Name | Description |
|-----------|------|-------------|
| Threshold | `threshold` | Trigger fires when input crosses this value |
| Trigger On | `triggeron` | Rising Edge, Falling Edge, Both |
| Attack | `attack` | Attack time (seconds) |
| Sustain | `sustain` | Sustain length (seconds, or hold while above threshold) |
| Release | `release` | Release/decay time (seconds) |
| Attack Shape | `attackshape` | Linear, Ease In, Ease Out, Ease In/Out |
| Peak Value | `peakvalue` | Maximum value during attack/sustain |
| Release Shape | `releaseshape` | Linear, Ease In, Ease Out, Exponential |

## VEX in CHOPs (CHOP Wrangles)

### Channel Wrangle Node

The `channelwrangle` CHOP runs VEX per sample per channel. Create via Tab menu: "Channel Wrangle".

Bindings:
- `@C` - Current channel value (read/write)
- `@I` - Sample index
- `@Time` - Time in seconds at current sample
- `@TimeInc` - Time step between samples
- `@SampleRate` - Sample rate
- `@channum` - Current channel index
- `@channame` - Current channel name (string)

### Common VEX Snippets

**Scale amplitude by time:**
```vex
// Fade in over first 2 seconds
float fade = clamp(@Time / 2.0, 0, 1);
@C *= fade;
```

**Add noise to a channel:**
```vex
// Add subtle noise jitter
float n = noise(@Time * 5.0 + @channum * 100) - 0.5;
@C += n * 0.1;
```

**Clamp channel values:**
```vex
@C = clamp(@C, -1.0, 1.0);
```

**Remap channel range:**
```vex
@C = fit(@C, -1, 1, 0, 10);
```

**Channel-specific operations:**
```vex
// Only affect rotation channels
if (match("r?", @channame)) {
    @C *= 0.5;  // halve all rotation values
}
```

**Spring-like behavior in VEX:**
```vex
// Simple damped spring (stateful, use with caution in CHOPs)
float target = chinput(0, @channum, @I);
float prev = @I > 0 ? chinput(-1, @channum, @I - 1) : target;
float vel = @I > 1 ? prev - chinput(-1, @channum, @I - 2) : 0;
float springk = 0.3;
float damp = 0.8;
float force = (target - prev) * springk;
vel = (vel + force) * damp;
@C = prev + vel;
```

**Frequency-based selection:**
```vex
// Only process samples in a time window
if (@Time >= 1.0 && @Time <= 3.0) {
    @C = smooth(@C, 0.5);
}
```

### Accessing Multiple Channels in VEX

```vex
// Read a specific channel by name from input 0
float tx = chinput(0, "tx", @I);
float ty = chinput(0, "ty", @I);
float tz = chinput(0, "tz", @I);

// Compute distance from origin
float dist = sqrt(tx*tx + ty*ty + tz*tz);
@C = dist;
```

### VEX CHOP Functions

| Function | Description |
|----------|-------------|
| `chinput(input, chanidx, sample)` | Read channel value from input by index |
| `chinput(input, "name", sample)` | Read channel value from input by name |
| `chend(input)` | End sample of input |
| `chstart(input)` | Start sample of input |
| `chrate(input)` | Sample rate of input |
| `chnum(input)` | Number of channels on input |
| `chname(input, index)` | Channel name by index |

## Common Production Workflows

### Camera Shake

```
noise (freq 3-8Hz, amp 0.01-0.05) -> lag (subtle smoothing) -> math (scale) -> export (cam tx ty)
```

Noise CHOP settings for camera shake:
- `type`: Sparse
- `amp`: 0.02 (subtle) to 0.2 (earthquake)
- `period`: 0.15-0.3 (3-8Hz range)
- `rough`: 0.5
- `turb`: 3-4

### Follow with Lag (Smooth Camera Track)

```
object (target position) -> lag (lagrise=0.3, lagfall=0.3) -> export (camera position)
```

### Audio-Driven Light Flicker

```
audiofilein -> filter (band-pass bass) -> math (abs, gain=5) -> trigger (attack=0.02, release=0.1) -> math (fit 0-1 to 2-8 exposure) -> export (light exposure)
```

### Procedural Secondary Motion

```
object (primary animation) -> jiggle (mass=1, stiffness=50, damping=0.1) -> export (secondary geo)
```

Jiggle CHOP simulates a mass-spring system driven by the input motion. Heavier mass = more lag, lower stiffness = more wobble.

### Constraint Network (OBJ Level)

Inside an OBJ node's `constraints` CHOP network:
```
constraintlookat (aim at target) -> constraintblend (weight with other constraints) -> null (output)
```

The constraints network on an OBJ is a special CHOP network. Its output channels (`rx ry rz tx ty tz`) override the OBJ transforms.

## Tips and Gotchas

### Sample Rate Mismatches

CHOPs operate at their own sample rate, independent of scene FPS. When connecting CHOPs with different rates, Houdini resamples automatically, but this can introduce artifacts.

- **Audio data**: 44100 Hz or 48000 Hz. Do NOT downsample to scene FPS (24-60) before analysis -- do the frequency analysis at full rate, then export the result at scene FPS.
- **Animation data**: Typically at scene FPS (24, 25, 30, 60).
- Use `resample` CHOP explicitly when you need control over interpolation method.
- The `rate` parameter on generator CHOPs sets their native rate.

### Channel Scope and Naming

- Channel names must **exactly match** parameter names for export to work. `tx` exports to `tx`, not `translatex`.
- Use `rename` CHOP to fix naming mismatches.
- Wildcard patterns in channel scope: `t?` matches `tx ty tz`, `r?` matches `rx ry rz`.
- `*` matches all channels. `chan[0-3]` matches `chan0` through `chan3`.

### Export Flag Behavior

- Only ONE CHOP network can export to a given parameter. If two CHOPs export to the same parm, the last one wins and Houdini warns.
- The export flag (star icon) on a CHOP node must be active for export to work.
- Exported parameters show a **green background** in the parameter editor.
- To stop exporting: disable the export flag, or delete the CHOP. The parameter returns to its original value or keyframes.
- **Export does not create keyframes** -- it overrides the parameter value live per frame.

### Performance Considerations

- CHOPs evaluate at their sample rate every frame. A 44100 Hz audio chain evaluates 44100 samples per frame even at 24 FPS. Keep audio processing in a separate chopnet and only export the final low-rate result.
- `geometry` CHOP reading thousands of points creates thousands of channels -- scope to only the attributes and point range you need.
- `trail` CHOP accumulates data over time and can use significant memory on long trails.
- CHOP networks cook independently of SOPs. Unused CHOP networks still cook if they have active export flags.

### Time Range Pitfalls

- Generator CHOPs default to the scene frame range. If your scene range changes, CHOP output may unexpectedly clip.
- Use `start` and `end` parameters explicitly, or set `range` to "Use Full Animation Range" to avoid surprises.
- `trim` and `shift` CHOPs affect the time range metadata but do not change sample count unless combined with `resample`.

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Export not working | Export flag off or channel name mismatch | Enable star icon, verify channel names match target parm names |
| Parameter stuck after removing export | Houdini caches last exported value | Set parameter to a keyframe or type a value manually to reclaim |
| Audio sounds wrong / aliased | Sample rate mismatch | Set CHOP `rate` to match audio file rate (44100/48000) |
| Jittery motion after lag/spring | Sample rate too low for fast motion | Increase CHOP sample rate, or increase lag/damping values |
| Constraint flips at gimbal lock | Rotation order / up-vector alignment | Change rotation order on OBJ, or adjust `upvector` on constraintlookat |
| Geometry CHOP too slow | Reading too many points/attribs | Scope to specific attributes, use detail attribs where possible |
| Channel Wrangle not running | No input connected or zero samples | Connect an input CHOP, or set explicit sample range on the wrangle |
| CHOP reference returns 0 | Wrong path or channel name in `chop()` | Verify path with middle-click on CHOP node, check exact channel name |
| Noise looks same every take | Same seed value | Change `seed` parameter or add `$OS` to offset expression |
| Spring never settles | Damping too low or mass too high | Increase `damping` to 0.5+, reduce `mass` |
