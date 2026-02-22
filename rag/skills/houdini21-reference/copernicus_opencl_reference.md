# Copernicus OpenCL Reference — Houdini 21

GPU-accelerated image processing via OpenCL kernels in Copernicus COP context.

## #bind Syntax — Layer Bindings

```c
// Required output layer
#bind layer !dst

// Optional input with default value
#bind layer src? val=0

// Optional mask defaulting to white
#bind layer mask? val=1

// Feedback input for solver loops
#bind layer feedback? val=0
```

Modifiers: `?` = optional, `!` = required, none = optional default.

### Layer Output Types (set in Signature tab)

```
Mono   -> float     -> 1 channel
UV     -> float2    -> 2 channels
RGB    -> float3/4  -> 3 channels (packed as 4)
RGBA   -> float4    -> 4 channels
Any    -> varies    -> matches input
```

## #bind Syntax — Parameter Bindings

```c
#bind parm float threshold val=0.5       // Float slider
#bind parm int iterations val=10         // Integer
#bind parm float2 scale val={1,1}        // Vector2
#bind parm float3 color val={1,0,0}      // Vector3 (RGB)
#bind parm float4 tint val={1,1,1,1}     // Vector4 (RGBA)
```

## #bind Syntax — Ramp Bindings

```c
#bind ramp float myramp           // Scalar ramp (spline)
#bind ramp float4 colorramp       // Color ramp (RGB)

// Usage in kernel:
float val = @myramp;              // Evaluates at current position
float4 col = @colorramp;          // Color from ramp at position
```

## #bind Syntax — Volume and Geometry

```c
// Volume binding
#bind volume src_vol               // Bind a volume
#bind vdb src_vdb                  // Bind a VDB

// Geometry attribute binding
#bind geoattrib float density              // From default geo input
#bind geoattrib float density input=1      // From second geo input

// In kernel: sample at pixel world position
float d = @src_vol;
```

## Built-in Macros and Variables

```c
// Kernel macro — expands to full signature with all bindings
@KERNEL
{
    // Your code here — all bindings available via @ prefix
}

// Resolution variables
@xres        // Image width in pixels (int)
@yres        // Image height in pixels (int)
@ixres       // 1.0 / @xres (float, inverse)
@iyres       // 1.0 / @yres (float, inverse)

// Position variables
@ix          // Current pixel X (int)
@iy          // Current pixel Y (int)
@x           // Current pixel X normalized 0-1 (float)
@y           // Current pixel Y normalized 0-1 (float)

// Raw OpenCL global ID (equivalent)
int gx = get_global_id(0);   // Same as @ix
int gy = get_global_id(1);   // Same as @iy
```

## Kernel Pattern: Color Correction

```c
#bind layer src? val=0
#bind layer !dst
#bind parm float brightness val=1.0
#bind parm float contrast val=1.0
#bind parm float saturation val=1.0

@KERNEL
{
    float4 c = @src;

    // Brightness (multiplicative)
    c.xyz *= @brightness;

    // Contrast (pivot at 0.5 midpoint)
    c.xyz = (c.xyz - 0.5f) * @contrast + 0.5f;

    // Saturation (rec709 luminance weights)
    float lum = dot(c.xyz, (float3)(0.2126f, 0.7152f, 0.0722f));
    c.xyz = mix((float3)(lum), c.xyz, @saturation);

    @dst = c;
}
```

## Kernel Pattern: Edge Detection (Sobel)

```c
#bind layer src? val=0
#bind layer !dst
#bind parm float strength val=1.0

@KERNEL
{
    int2 pos = (int2)(get_global_id(0), get_global_id(1));
    int2 res = (int2)(@xres, @yres);

    float gx = 0.0f, gy = 0.0f;

    for (int dy = -1; dy <= 1; dy++) {
        for (int dx = -1; dx <= 1; dx++) {
            int2 npos = clamp(pos + (int2)(dx, dy),
                              (int2)(0), res - 1);
            // Sample luminance at neighbor
            float lum = dot(@src.xyz,
                           (float3)(0.2126f, 0.7152f, 0.0722f));

            int kx = dx * (2 - abs(dy));  // Sobel horizontal kernel
            gx += lum * (float)kx;

            int ky = dy * (2 - abs(dx));  // Sobel vertical kernel
            gy += lum * (float)ky;
        }
    }

    float edge = sqrt(gx * gx + gy * gy) * @strength;
    @dst = (float4)(edge, edge, edge, 1.0f);
}
```

## Kernel Pattern: Distance Field (Jump Flooding)

```c
// JFA for SDF generation — run in solver with halving step size
#bind layer src? val=0           // Seed points (binary mask)
#bind layer feedback? val=0      // Previous JFA state
#bind layer !dst
#bind parm int step val=512      // Current step size (halves per iteration)

@KERNEL
{
    int2 pos = (int2)(get_global_id(0), get_global_id(1));
    float2 best_seed = @feedback.xy;
    float best_dist = 1e10f;

    // Check 8 neighbors at current step distance
    for (int dy = -1; dy <= 1; dy++) {
        for (int dx = -1; dx <= 1; dx++) {
            int2 npos = pos + (int2)(dx * @step, dy * @step);
            // Bounds check
            if (npos.x < 0 || npos.x >= @xres ||
                npos.y < 0 || npos.y >= @yres) continue;

            float2 nseed = @feedback.xy;  // sampled at npos
            if (nseed.x >= 0.0f) {
                float d = length(convert_float2(pos) - nseed);
                if (d < best_dist) {
                    best_dist = d;
                    best_seed = nseed;
                }
            }
        }
    }

    @dst = (float4)(best_seed.x, best_seed.y, best_dist, 1.0f);
}
```

## Kernel Pattern: Noise Generation (GPU-friendly)

```c
// Hash-based value noise — no texture lookups, pure ALU
float hash(float2 p) {
    float3 p3 = fract((float3)(p.x, p.y, p.x) * 0.1031f);
    p3 += dot(p3, p3.yzx + 33.33f);
    return fract((p3.x + p3.y) * p3.z);
}

float noise2d(float2 p) {
    float2 i = floor(p);
    float2 f = fract(p);
    f = f * f * (3.0f - 2.0f * f);  // Smoothstep interpolation

    float a = hash(i);
    float b = hash(i + (float2)(1.0f, 0.0f));
    float c = hash(i + (float2)(0.0f, 1.0f));
    float d = hash(i + (float2)(1.0f, 1.0f));

    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

// FBM (fractal Brownian motion) from noise2d
float fbm(float2 p, int octaves) {
    float value = 0.0f;
    float amplitude = 0.5f;
    float frequency = 1.0f;
    for (int i = 0; i < octaves; i++) {
        value += amplitude * noise2d(p * frequency);
        amplitude *= 0.5f;
        frequency *= 2.0f;
    }
    return value;
}
```

## Kernel Pattern: Gaussian Blur (Separable)

```c
// Horizontal pass (run vertical pass as second OpenCL node)
#bind layer src? val=0
#bind layer !dst
#bind parm int radius val=5

@KERNEL
{
    int2 pos = (int2)(get_global_id(0), get_global_id(1));
    float4 sum = (float4)(0.0f);
    float weight_sum = 0.0f;

    for (int dx = -@radius; dx <= @radius; dx++) {
        int nx = clamp(pos.x + dx, 0, @xres - 1);
        float w = exp(-0.5f * (float)(dx * dx) /
                      (float)(@radius * @radius / 4));
        // Sample @src at (nx, pos.y) — use global_id offset
        sum += @src * w;  // simplified — actual sampling needs offset
        weight_sum += w;
    }

    @dst = sum / weight_sum;
}
```

## Kernel Pattern: Threshold with Smooth Falloff

```c
#bind layer src? val=0
#bind layer !dst
#bind parm float threshold val=0.5
#bind parm float softness val=0.1

@KERNEL
{
    float4 c = @src;
    float lum = dot(c.xyz, (float3)(0.2126f, 0.7152f, 0.0722f));

    // Smooth threshold (avoid hard edges)
    float mask = smoothstep(@threshold - @softness,
                            @threshold + @softness, lum);

    @dst = (float4)(mask, mask, mask, 1.0f);
}
```

## Kernel Pattern: Rotation Transform

```c
float2 rotate2d(float2 p, float angle) {
    float s = sin(angle);
    float c = cos(angle);
    return (float2)(p.x * c - p.y * s,
                    p.x * s + p.y * c);
}

// Usage: rotate UVs around center
float2 uv = (float2)(@x, @y) - 0.5f;   // Center origin
uv = rotate2d(uv, angle_radians);
uv += 0.5f;                              // Restore origin
```

## Border Mode Behavior

Per-layer override options (Signature tab):

| Mode     | Behavior                          |
|----------|-----------------------------------|
| Input    | Use input's border settings       |
| Constant | Zero outside bounds               |
| Clamp    | Streak edge pixels                |
| Reflect  | Mirror at boundary                |
| Wrap     | Tile seamlessly                   |

### Manual Bounds Checking in Kernels

```c
int2 npos = pos + offset;

// Clamp method
npos = clamp(npos, (int2)(0), (int2)(@xres-1, @yres-1));

// Wrap method
npos.x = ((npos.x % @xres) + @xres) % @xres;
npos.y = ((npos.y % @yres) + @yres) % @yres;

// Skip method (for accumulation kernels)
if (npos.x < 0 || npos.x >= @xres ||
    npos.y < 0 || npos.y >= @yres) continue;
```

## Performance: Native Math Functions

```c
// native_ variants: less precise, MUCH faster on GPU
float s = native_sin(x);       // ~2x faster than sin()
float c = native_cos(x);
float r = native_sqrt(x);
float p = native_powr(x, y);   // x^y, x must be >= 0
float e = native_exp(x);
float l = native_log(x);

// Use standard when precision matters (lighting, color science)
float s = sin(x);              // IEEE 754 compliant
```

## Performance: Avoid Divergent Branching

```c
// BAD: divergent threads stall the warp
if (condition_varies_per_pixel) {
    expensive_path_A();
} else {
    expensive_path_B();
}

// BETTER: compute both, select
float a = expensive_a();
float b = expensive_b();
float result = condition ? a : b;

// BEST: continuous blending (no branch at all)
float result = mix(a, b, smoothstep(0.0f, 1.0f, mask));
```

## Performance: Minimize Global Memory Access

```c
// BAD: 3 separate global memory reads
float r = @src.x;
float g = @src.y;
float b = @src.z;

// GOOD: single read into local register
float4 c = @src;
float r = c.x;
float g = c.y;
float b = c.z;
```

## Debugging OpenCL Kernels

```c
// Visual debug: output intermediate values as color
@dst = (float4)(debug_value, 0.0f, 0.0f, 1.0f);  // Red = value

// Grid overlay for coordinate verification
float grid = step(0.01f, fract(@x * 10.0f)) *
             step(0.01f, fract(@y * 10.0f));
@dst = mix((float4)(1,0,0,1), @src, grid);

// Range visualization: map value to heatmap
float t = clamp(debug_value, 0.0f, 1.0f);
float3 heat = mix((float3)(0,0,1), (float3)(1,0,0), t);  // blue->red
@dst = (float4)(heat.x, heat.y, heat.z, 1.0f);
```

### Common Compilation Errors

```
"Kernel compilation failed":
  - #bind names don't match actual connections
  - Layer types mismatch kernel expectations
  - C99 syntax only — no auto, no C++ features, no templates

"Result is all black":
  - Missing output binding: need #bind layer !dst
  - Alpha not set: always set .w = 1.0f
  - Input not connected or not cooking

"Result is wrong resolution":
  - Check metadata source (which input drives resolution)
  - Set explicitly in Signature tab if needed

"NaN artifacts":
  - Division by zero in normalize() — check length > 0
  - native_sqrt() of negative value
  - native_log() of zero or negative
```

## Work Group Configuration

```
Default: automatic (Houdini manages work groups)
RTX 4090: 128 SMs, warp size 32

For most COP work: let Houdini's scheduler handle sizing.
Manual override only for extreme optimization needs.

Typical effective throughput:
  Simple per-pixel math: memory-bandwidth bound
  Complex multi-sample kernels: compute bound
  Neighbor-sampling kernels: cache-line dependent
```
