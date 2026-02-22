# Houdini Expressions Reference

## Triggers
expression, hscript, $F, ch(), frame variable, channel reference, parameter expression,
python expression, vex ch, string variable, $HIP, $HIPNAME, oscillation, conditional

## Context
Houdini uses three expression languages: HScript (parameter fields), Python (toggle via RMB),
and VEX (wrangles). This reference covers variables, channel references, and common patterns
with code examples.

## Code

```python
# Frame and time variables -- reading in Python
import hou

frame = hou.frame()              # Current frame (float)
int_frame = hou.intFrame()       # Current frame (int)
time = hou.time()                # Current time in seconds
fps = hou.fps()                  # Frames per second
start = hou.playbar.playbackRange()[0]  # Start frame
end = hou.playbar.playbackRange()[1]    # End frame

print(f"Frame {int_frame} of {start}-{end} at {fps}fps, time={time:.3f}s")
```

```python
# HScript variable equivalents in Python
import hou

# $F  -> hou.intFrame()
# $FF -> hou.frame()
# $T  -> hou.time()
# $FPS -> hou.fps()
# $HIP -> hou.hipFile().path().rsplit("/", 1)[0]
# $HIPNAME -> hou.hipFile().basename().rsplit(".", 1)[0]
# $HIPFILE -> hou.hipFile().path()

# Expand HScript variables in a string
expanded = hou.text.expandString("$HIP/render/$HIPNAME.$F4.exr")
print(f"Expanded: {expanded}")
```

```python
# Channel references -- reading parameter values
import hou

node = hou.node("/obj/geo1/transform1")
if node:
    # Read float parm (equivalent to HScript ch("tx"))
    tx = node.evalParm("tx")

    # Read string parm (equivalent to HScript chs("file"))
    # name = node.evalParm("file")

    # Read at specific frame (equivalent to HScript chf("tx", 50))
    tx_at_50 = node.parm("tx").evalAtFrame(50)

    # Read from relative path (equivalent to ch("../other_node/tx"))
    other = node.node("../other_node")
    if other:
        other_tx = other.evalParm("tx")

    print(f"tx={tx}, tx@50={tx_at_50}")
```

```python
# Setting HScript expressions on parameters
import hou

node = hou.node("/obj/geo1/transform1")
if node:
    # Oscillation: sin($T * 360 * 2) * 5
    node.parm("ty").setExpression("sin($T * 360 * 2) * 5")

    # Random per-copy: fit01(rand($PT), 0.5, 2.0)
    # node.parm("pscale").setExpression("fit01(rand($PT), 0.5, 2.0)")

    # Conditional: if($F < 100, 0, 1)
    # node.parm("visibility").setExpression("if($F < 100, 0, 1)")

    # Channel reference to another node
    # node.parm("tx").setExpression('ch("../controller/slider")')

    # Frame-based file path
    # node.parm("file").set("$HIP/render/$HIPNAME.$F4.exr")

    print(f"Expression set: {node.parm('ty').expression()}")
```

```python
# Python expressions on parameters (toggle via RMB > Expression > Python)
import hou

node = hou.node("/obj/geo1/transform1")
if node:
    # Switch parameter to Python expression language
    parm = node.parm("ty")
    parm.setExpression(
        'hou.time() * 5.0',
        language=hou.exprLanguage.Python
    )

    # Python expression accessing other node
    # 'hou.node("../controller").evalParm("slider") * 2.0'

    # Python conditional
    # 'hou.frame() * 0.1 if hou.frame() < 100 else 10.0'
```

```python
# Geometry variables -- reading bounding box info
import hou

sop = hou.node("/obj/geo1/OUT")
if sop:
    geo = sop.geometry()
    bbox = geo.boundingBox()

    # Equivalent to $CEX, $CEY, $CEZ
    center = bbox.center()
    print(f"Centroid: ({center[0]:.2f}, {center[1]:.2f}, {center[2]:.2f})")

    # Equivalent to $SIZEX, $SIZEY, $SIZEZ
    size = bbox.sizevec()
    print(f"Size: ({size[0]:.2f}, {size[1]:.2f}, {size[2]:.2f})")

    # Equivalent to $XMIN, $XMAX, etc.
    print(f"X range: {bbox.minvec()[0]:.2f} to {bbox.maxvec()[0]:.2f}")

    # Equivalent to $NPT, $NPR
    npt = len(geo.points())
    npr = len(geo.prims())
    print(f"Points: {npt}, Prims: {npr}")
```

```python
# Input references
import hou

node = hou.node("/obj/geo1/wrangle1")
if node:
    # Equivalent to opinput(".", 0)
    inputs = node.inputs()
    if inputs:
        first_input = inputs[0]
        print(f"First input: {first_input.path()}")

    # Equivalent to opninputs(".")
    num_inputs = len([i for i in node.inputs() if i is not None])
    print(f"Connected inputs: {num_inputs}")
```

```vex
// VEX channel references (in Attribute Wrangle)
// ch() in VEX reads SPARE PARMS on the wrangle node itself
// NOT the same as HScript ch() in parameter fields

// Read a float slider on the wrangle node
float threshold = ch("threshold");

// Read an integer toggle
int enabled = chi("enabled");

// Read a string path
string path = chs("filepath");

// Read a ramp (spare parm of type ramp)
float ramp_val = chramp("falloff", f@dist);

// Read a vector3 (color picker spare parm)
vector color = chv("tint_color");
```

```vex
// Common VEX expression patterns

// Oscillation (sine wave animation)
float freq = ch("frequency");
float amp = ch("amplitude");
v@P.y += sin(@Time * freq * 6.2832) * amp;

// Random per-point (stable random based on point number)
f@pscale = fit01(rand(@ptnum), 0.5, 2.0);

// Random per-point with seed for variation
f@pscale = fit01(rand(@ptnum + chi("seed") * 1000), 0.5, 2.0);

// Conditional
i@group_top = (@P.y > ch("height_threshold")) ? 1 : 0;

// Frame-based animation
float t = fit(@Frame, chi("start_frame"), chi("end_frame"), 0.0, 1.0);
t = clamp(t, 0, 1);
t = smooth(0, 1, t);  // ease in/out
```

```python
# String expression variables in context
import hou

# Expand all variables in a path string
COMMON_PATH_PATTERNS = {
    "render_output": "$HIP/render/$HIPNAME.$F4.exr",
    "cache_output":  "$HIP/cache/$OS.$F4.bgeo.sc",
    "usd_export":    "$HIP/usd/$HIPNAME.usd",
    "texture_input": "$HIP/textures/hero_basecolor.<UDIM>.exr",
}

for name, pattern in COMMON_PATH_PATTERNS.items():
    expanded = hou.text.expandString(pattern)
    print(f"  {name}: {pattern}")
    print(f"    -> {expanded}")
```

```python
# HScript vs Python vs VEX -- when to use each
EXPRESSION_GUIDE = {
    "parameter_field": {
        "language": "HScript (default)",
        "example": '$F, ch("tx"), fit(ch("slider"), 0, 1, -5, 5)',
        "when": "Simple parameter expressions, frame references",
    },
    "parameter_complex": {
        "language": "Python (toggle via RMB)",
        "example": 'hou.pwd().evalParm("tx") + math.sin(hou.time())',
        "when": "Complex logic, conditionals, accessing multiple nodes",
    },
    "attribute_wrangle": {
        "language": "VEX",
        "example": 'v@P.y += sin(@Time * ch("freq")) * ch("amp");',
        "when": "Per-element operations on geometry attributes",
    },
    "execute_python": {
        "language": "Python",
        "example": 'hou.node("/obj/geo1").cook(force=True)',
        "when": "Batch operations, file I/O, API automation",
    },
}

for context, info in EXPRESSION_GUIDE.items():
    print(f"{context}: {info['language']}")
    print(f"  Example: {info['example']}")
```

## Common Mistakes
- Confusing VEX ch() (reads spare parms on wrangle) with HScript ch() (reads node parms)
- Using $PT in parameter fields (HScript) vs @ptnum in VEX -- different contexts
- Forgetting $F4 padding in render paths -- without padding, frames overwrite each other
- Using HScript expressions in Python parameter mode (or vice versa)
- Not expanding $HIP before checking file existence -- hou.text.expandString() required
- Using @Frame in VEX (read-only float) when @Time is needed for time-based animation
