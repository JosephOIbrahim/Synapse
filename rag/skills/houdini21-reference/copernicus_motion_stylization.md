# Copernicus Motion Design & Stylization — Houdini 21

Pixel sorting, risograph/print, NPR/toon shading, stamp texturing, frame blend, directional occlusion.

## Pixel Sorting

### Algorithm (4-step)

```
1. Threshold: luminance -> binary mask (sortable vs anchored)
2. Span Detection: find contiguous runs of sortable pixels per row/column
3. Sort Within Spans: sort by chosen channel, maintain span boundaries
4. Iteration: repeat N times for stronger effect
```

### GPU Implementation Strategy

```
Parallelism: across rows (each row = one work group)
Within row: serial span scan + insertion sort (small spans)
            or bitonic sort (large spans, GPU-friendly)

Performance: 10-100x faster than CPU/VEX despite serial component
Reason: parallel row processing + GPU memory bandwidth
```

### Control Parameters

```
threshold:    0.0-1.0 (luminance cutoff for sortable region)
direction:    Horizontal / Vertical / Diagonal / Radial
sort_channel: Luminance / Hue / Saturation / R / G / B / Custom
iterations:   1-100 (strength/distance of sort)
mask:         Optional external mask for regional control

Animation patterns:
  - Animate threshold -> growing/shrinking sort regions
  - Animate direction -> rotating sort effect
  - Noise as threshold modifier -> organic sort boundaries
```

### Pixel Sort OpenCL Skeleton

```c
#bind layer src? val=0
#bind layer mask? val=1        // Optional region mask
#bind layer !dst
#bind parm float threshold val=0.5
#bind parm int sort_mode val=0  // 0=luminance, 1=hue, 2=red, etc.

@KERNEL
{
    int2 pos = (int2)(get_global_id(0), get_global_id(1));
    float4 c = @src;
    float m = @mask.x;

    // Extract sort key based on mode
    float lum = dot(c.xyz, (float3)(0.2126f, 0.7152f, 0.0722f));

    // Only pixels above threshold AND inside mask are sortable
    float sortable = step(@threshold, lum) * step(0.5f, m);

    // Full sort requires shared memory or multi-pass approach
    // Single-pass approximation: compare-and-swap with neighbor
    // For production: use multi-pass bitonic sort network

    @dst = c;  // Placeholder — real sort needs multi-pass
}
```

## Risograph / Print Effects

### Pipeline Architecture

```
Input -> Color Separation -> Dither -> Ink Simulation -> Paper Composite

Layer Stack (bottom to top):
  1. Paper base (texture)
  2. Ink layer 1 (spot color 1, dithered)
  3. Ink layer 2 (spot color 2, dithered)
  4. Ink layer N
  5. Paper texture overlay (grain/fiber)
```

### Authentic Risograph Ink Colors

```c
// sRGB values for common risograph ink colors
// Fluorescent Pink
float3 RISO_PINK    = (float3)(1.000f, 0.282f, 0.690f);
// Red
float3 RISO_RED     = (float3)(1.000f, 0.267f, 0.227f);
// Blue
float3 RISO_BLUE    = (float3)(0.000f, 0.471f, 0.749f);
// Green
float3 RISO_GREEN   = (float3)(0.000f, 0.663f, 0.361f);
// Yellow
float3 RISO_YELLOW  = (float3)(1.000f, 0.910f, 0.000f);
// Black
float3 RISO_BLACK   = (float3)(0.000f, 0.000f, 0.000f);
```

### Dither Modes

```
1. Organic (blue noise):
   Blue noise dithering -> natural film-like grain
   Best for: organic subjects, photography

2. Halftone (dot pattern):
   Classic print dots, angled per channel to prevent moire:
     Cyan: 15deg, Magenta: 75deg, Yellow: 0deg, Black: 45deg
   Best for: retro print, pop art

3. Digital (error diffusion):
   Floyd-Steinberg or Atkinson diffusion
   Best for: detailed images, text
```

### Ink Mixing (Subtractive)

```c
// Risograph inks are semi-transparent — subtractive mixing
// NOT additive: result = ink1 + ink2  (WRONG)

// Correct subtractive model:
float3 paper = (float3)(0.95f, 0.93f, 0.90f);  // Off-white paper
float3 result = paper;

// Each ink layer absorbs light
result *= (1.0f - ink1_density * ink1_color);
result *= (1.0f - ink2_density * ink2_color);

// Result: Blue + Yellow -> Green (subtractive, correct)
//         Pink + Blue -> Purple
```

## NPR / Toon Shading via COPs

### Post-Render Toon Pipeline

```
Karma renders standard AOVs, then Copernicus stylizes:

1. Edge Detection:
   Sobel/Laplacian on depth + normal AOVs
   Combine for clean outline layer (handles silhouette + detail)

2. Color Quantization:
   Reduce continuous color to N discrete levels
   Angle Quantize COP: quantize by surface angle for cel shading

3. Hatching (H21 native):
   Cross-hatch patterns driven by luminance
   Copernicus provides dedicated hatching nodes

4. Composite:
   quantized_color * outline * hatching = final toon look
```

### Toon Edge Detection Kernel

```c
#bind layer depth? val=0        // Depth AOV from Karma
#bind layer normal? val=0       // Normal AOV from Karma
#bind layer !dst
#bind parm float depth_threshold val=0.1
#bind parm float normal_threshold val=0.3
#bind parm float line_width val=1.0

@KERNEL
{
    int2 pos = (int2)(get_global_id(0), get_global_id(1));

    // Sobel on depth
    float depth_gx = 0.0f, depth_gy = 0.0f;
    for (int dy = -1; dy <= 1; dy++) {
        for (int dx = -1; dx <= 1; dx++) {
            int2 npos = clamp(pos + (int2)(dx, dy),
                              (int2)(0), (int2)(@xres-1, @yres-1));
            float d = @depth.x;  // at npos
            int kx = dx * (2 - abs(dy));
            int ky = dy * (2 - abs(dx));
            depth_gx += d * (float)kx;
            depth_gy += d * (float)ky;
        }
    }
    float depth_edge = sqrt(depth_gx * depth_gx + depth_gy * depth_gy);

    // Sobel on normals (using dot product difference)
    float3 center_n = @normal.xyz;
    float normal_edge = 0.0f;
    for (int dy = -1; dy <= 1; dy++) {
        for (int dx = -1; dx <= 1; dx++) {
            if (dx == 0 && dy == 0) continue;
            int2 npos = clamp(pos + (int2)(dx, dy),
                              (int2)(0), (int2)(@xres-1, @yres-1));
            float3 nn = @normal.xyz;  // at npos
            float ndiff = 1.0f - dot(center_n, nn);
            normal_edge = max(normal_edge, ndiff);
        }
    }

    // Combine edges
    float edge = max(
        step(@depth_threshold, depth_edge),
        step(@normal_threshold, normal_edge)
    );

    @dst = (float4)(1.0f - edge, 1.0f - edge, 1.0f - edge, 1.0f);
}
```

## Directional Occlusion

```
Architecture:
  Input: height map or depth map
  Per-pixel: cast rays in N hemisphere directions
  Sample height along each ray
  Accumulate occlusion per direction
  Output: directional AO map

Parameters:
  directions: 8-32 (more = smoother, slower)
  radius:     sampling distance in pixels
  strength:   occlusion multiplier
  bias:       offset to prevent self-occlusion

MaterialX use cases:
  -> Cavity map for wear/dirt accumulation
  -> Edge emphasis for stylized rendering
  -> Detail enhancement for close-up shots
```

### Directional AO Kernel

```c
#bind layer height? val=0
#bind layer !dst
#bind parm int directions val=16
#bind parm float radius val=20.0
#bind parm float strength val=1.0
#bind parm float bias val=0.01

@KERNEL
{
    int2 pos = (int2)(get_global_id(0), get_global_id(1));
    float center_h = @height.x + @bias;
    float ao = 0.0f;

    for (int d = 0; d < @directions; d++) {
        float angle = (float)d / (float)@directions * 6.28318f;
        float2 dir = (float2)(cos(angle), sin(angle));

        float max_horizon = 0.0f;
        for (float r = 1.0f; r <= @radius; r += 1.0f) {
            int2 sample_pos = pos + convert_int2(dir * r);
            sample_pos = clamp(sample_pos, (int2)(0),
                               (int2)(@xres-1, @yres-1));
            float sample_h = @height.x;  // at sample_pos
            float horizon = (sample_h - center_h) / r;
            max_horizon = max(max_horizon, horizon);
        }
        ao += max_horizon;
    }

    ao = 1.0f - clamp(ao / (float)@directions * @strength, 0.0f, 1.0f);
    @dst = (float4)(ao, ao, ao, 1.0f);
}
```

## Stamp-Based Texturing

### Stamp COP Configuration

```
Stamp COP:
  Input 1: stamp image (element to scatter)
  Input 2: point geometry (scatter positions from SOP)

Per-Instance Attributes (from geometry):
  P:           position
  scale:       uniform scale
  pscale:      point scale
  orient:      quaternion orientation
  N:           normal (for auto-orientation)
  Cd:          color tint per instance
  spriterot:   rotation in degrees
  spritescale: non-uniform scale (x, y)
  spriteuv:    UV offset per instance
```

### Production Decal Pipeline

```python
import hou

# SOP: scatter points on surface
scatter = hou.node("/obj/geo1/scatter1")
scatter.parm("npts").set(200)

# COP: stamp decal at each scatter point
copnet = hou.node("/obj/copnet1")
stamp = copnet.createNode("stamp")
stamp.parm("soppath").set("/obj/geo1/scatter1")
# Input 1: decal texture (file or procedural)
decal = copnet.createNode("file")
decal.parm("filename1").set("$HIP/tex/decal_scratch.exr")
stamp.setInput(0, decal)

stamp.setDisplayFlag(True)
# Result: scattered decals composited into single layer
# -> Feed into MaterialX as detail overlay via op: path
```

## Frame Blend / Trails

### Blend Methods

```
Method 1: Weighted average (motion blur)
  frame[t] = w0*image[t] + w1*image[t-1] + w2*image[t-2]
  Weights decay exponentially: w_i = decay^i
  Result: smooth motion blur / ghosting

Method 2: Maximum hold (light trails)
  frame[t] = max(image[t], frame[t-1] * decay)
  Bright pixels persist, dark pixels fade
  Result: light painting, particle trails

Method 3: Feedback blend (solver-based)
  Block solver: mix(new_frame, feedback, ratio)
  ratio = 0.0 -> no trails, 1.0 -> infinite persistence
  Result: controllable trail length
```

### Feedback Trail Kernel

```c
#bind layer current? val=0    // New frame input
#bind layer feedback? val=0   // Previous frame (from Block End)
#bind layer !dst
#bind parm float decay val=0.95
#bind parm int mode val=0     // 0=blend, 1=max

@KERNEL
{
    float4 curr = @current;
    float4 prev = @feedback;

    float4 result;
    if (@mode == 0) {
        // Weighted blend: new frame + faded previous
        result = mix(curr, prev * @decay, @decay);
    } else {
        // Maximum hold: bright pixels persist
        result = max(curr, prev * @decay);
    }

    result.w = 1.0f;
    @dst = result;
}
```

## Animation Parameter Patterns

### Time Access in Different COP Contexts

```
OpenCL kernels:
  No direct $T access — pass time as parameter
  Parm expression: $T (current time in seconds)
                   $FF (current frame number)

Python Snippet COP:
  hou.time()      -> current time in seconds
  hou.frame()     -> current frame number

Built-in COP node parameters:
  Standard Houdini expressions work normally:
    sin($T * freq)           -> oscillation
    fit($T, 0, dur, 0, 1)   -> linear 0-1 ramp
    smooth($T, start, end)   -> smooth transition
    noise($T * freq)         -> organic variation
```

### OpenCL Time Parameter Pattern

```c
#bind layer src? val=0
#bind layer !dst
#bind parm float time val=0.0     // Expression: $T
#bind parm float freq val=2.0

@KERNEL
{
    float4 c = @src;

    // Time-based oscillation
    float pulse = sin(@time * @freq * 6.28318f) * 0.5f + 0.5f;

    // Animate brightness with time
    c.xyz *= mix(0.5f, 1.5f, pulse);

    @dst = c;
}
```

## GPU Performance Reference (RTX 4090)

```
Operation                    | 1K      | 2K      | 4K
-----------------------------|---------|---------|--------
Simple color math            | <1ms    | <1ms    | 2ms
Gaussian blur (r=10)         | 1ms     | 3ms     | 12ms
Sobel edge detect            | <1ms    | 1ms     | 4ms
Growth propagation (10 iter) | 5ms     | 18ms    | 70ms
Reaction-diffusion (10 iter) | 3ms     | 12ms    | 45ms
Pixel sort (50 iterations)   | 8ms     | 30ms    | 120ms
Noise generation (fractal)   | 1ms     | 3ms     | 10ms
Full solver frame (complex)  | 10-50ms | 40-200ms| 150-800ms

VEX CPU equivalent:
  Growth propagation (10 iter)| 500ms   | 2s      | 8s+

GPU advantage: 10-100x consistently
```
