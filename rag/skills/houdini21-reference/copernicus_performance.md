# Copernicus Performance & Memory — Houdini 21

GPU benchmarks, memory estimation, optimization patterns for Copernicus OpenCL processing.

## RTX 4090 Benchmark Reference

```
Benchmarks at square texture resolutions (1024^2, 2048^2, 4096^2):

Operation                      | 1K      | 2K      | 4K
-------------------------------|---------|---------|--------
Simple color math (per-pixel)  | <1ms    | <1ms    | 2ms
Gaussian blur (radius=10)      | 1ms     | 3ms     | 12ms
Sobel edge detect (3x3)        | <1ms    | 1ms     | 4ms
Growth propagation (10 iter)   | 5ms     | 18ms    | 70ms
Reaction-diffusion (10 iter)   | 3ms     | 12ms    | 45ms
Pixel sort (50 iterations)     | 8ms     | 30ms    | 120ms
Fractal noise generation       | 1ms     | 3ms     | 10ms
Full solver frame (complex)    | 10-50ms | 40-200ms| 150-800ms
JFA distance field (log2 iter) | 2ms     | 8ms     | 30ms
Directional AO (16 dirs)       | 4ms     | 15ms    | 60ms

CPU VEX equivalent comparison:
  Growth propagation (10 iter) | 500ms   | 2s      | 8s+
  Pixel sort (50 iterations)   | 200ms   | 800ms   | 3s+

GPU advantage: 10-100x consistently on RTX 4090
```

## Memory Estimation

### Per-Layer Memory

```
Formula: width * height * channels * bytes_per_channel

Bytes per channel:
  8-bit int:   1 byte
  16-bit half: 2 bytes
  32-bit float: 4 bytes (default)

Examples at 32-bit float (square texture resolutions):
  Resolution:  1K = 1024x1024    2K = 2048x2048    4K = 4096x4096

  Mono (1ch):  1K = 4 MB    2K = 16 MB    4K = 64 MB
  UV (2ch):    1K = 8 MB    2K = 32 MB    4K = 128 MB
  RGB (3ch):   1K = 12 MB   2K = 48 MB    4K = 192 MB
  RGBA (4ch):  1K = 16 MB   2K = 64 MB    4K = 256 MB

For video resolutions (non-square):
  HD 1920x1080 RGBA: 32 MB    UHD 3840x2160 RGBA: 127 MB
```

### Solver Cache Memory

```
Formula: layers_per_frame * layer_size * cached_frames

Example: 3-field solver (growth + direction + distance)
  4K, 32-bit, RGBA: 3 * 256 MB = 768 MB per frame
  100 cached frames: 75 GB (won't fit in 24GB VRAM)

Mitigation strategies:
  1. Checkpoint to disk (File COP every N frames)
  2. Simulate at lower res, upres post-sim
  3. Use 16-bit half precision (halves memory)
  4. Limit cache frame range in Block End
  5. Use Mono layers where RGBA not needed
```

### Working Set Estimation

```python
# Estimate VRAM for a COP network
def estimate_vram_mb(width, height, num_layers, channels=4,
                     precision=32, solver_frames=1):
    bytes_per_pixel = channels * (precision // 8)
    layer_mb = (width * height * bytes_per_pixel) / (1024 * 1024)
    total_mb = layer_mb * num_layers * solver_frames
    return total_mb

# Example: complex comp at 4K
print(estimate_vram_mb(3840, 2160, num_layers=15, channels=4))
# ~1,900 MB = ~1.9 GB (fits comfortably in 24GB)

# Example: solver at 4K with 100-frame cache
print(estimate_vram_mb(3840, 2160, num_layers=3, solver_frames=100))
# ~9,500 MB = ~9.5 GB (manageable but tight)
```

## Optimization: Native Math Functions

```c
// native_ variants: lower precision, MUCH faster on GPU
// Use for visual effects where exact precision doesn't matter

native_sin(x)       // ~2x faster than sin()
native_cos(x)       // ~2x faster than cos()
native_sqrt(x)      // Fast inverse square root path
native_powr(x, y)   // x^y, requires x >= 0
native_exp(x)       // e^x
native_log(x)       // ln(x), requires x > 0
native_recip(x)     // 1/x

// Use standard IEEE 754 versions when precision matters:
// Lighting calculations, color science, physical simulation
sin(x)              // Full IEEE 754 compliance
cos(x)
sqrt(x)
pow(x, y)           // Handles negative x
exp(x)
log(x)
```

## Optimization: Minimize Global Memory Access

```c
// GPU global memory reads are expensive (~400 cycles latency)
// Registers are fast (~1 cycle)

// BAD: 3 separate global memory reads for same pixel
float r = @src.x;
float g = @src.y;
float b = @src.z;

// GOOD: 1 read into register, 3 register reads
float4 c = @src;   // Single global memory read
float r = c.x;     // Register access
float g = c.y;     // Register access
float b = c.z;     // Register access

// BAD: read neighbor multiple times
for (int pass = 0; pass < 3; pass++) {
    float n = @src;  // at neighbor — reads global memory each pass
    // process...
}

// GOOD: read once, reuse
float n = @src;  // at neighbor — single read
for (int pass = 0; pass < 3; pass++) {
    // process using local 'n'
}
```

## Optimization: Avoid Divergent Branching

```c
// GPU warps (32 threads) execute in lockstep
// Divergent branches cause serialization

// BAD: threads in same warp take different paths
if (condition_varies_per_pixel) {
    expensive_path_A();   // Some threads idle
} else {
    expensive_path_B();   // Other threads idle
}
// Total time = cost(A) + cost(B)

// BETTER: compute both, select result
float a = compute_a();
float b = compute_b();
float result = condition ? a : b;
// Total time = max(cost(a), cost(b))

// BEST: continuous blending (zero branching)
float result = mix(a, b, smoothstep(0.0f, 1.0f, mask));
// Total time = cost(a) + cost(b) + cost(mix)
// But no warp divergence penalty
```

## Optimization: Kernel Complexity Tiers

```
Tier 1 — Memory-bound (simple per-pixel math):
  Bottleneck: memory bandwidth, not compute
  Examples: color correction, threshold, blend
  Optimization: reduce memory reads, use fewer layers
  Target: <2ms at 4K

Tier 2 — Balanced (small neighborhood sampling):
  Bottleneck: mix of memory + compute
  Examples: 3x3 blur, edge detection, sharpen
  Optimization: cache neighborhood in registers
  Target: <15ms at 4K

Tier 3 — Compute-bound (large kernels, many samples):
  Bottleneck: ALU operations
  Examples: large-radius blur, AO, pixel sort
  Optimization: use native_math, reduce sample count
  Target: <100ms at 4K

Tier 4 — Iterative (solver sub-steps):
  Bottleneck: iteration count * per-iteration cost
  Examples: growth, R-D, JFA, flow sim
  Optimization: minimize iterations, reduce field count
  Target: <200ms per frame at 4K
```

## Optimization: Separable Filters

```c
// 2D blur with radius R: O(R^2) samples per pixel
// Separable: horizontal pass + vertical pass: O(2R) samples

// Pass 1: Horizontal blur (OpenCL node #1)
#bind layer src? val=0
#bind layer !dst
#bind parm int radius val=5

@KERNEL
{
    int2 pos = (int2)(get_global_id(0), get_global_id(1));
    float4 sum = (float4)(0.0f);
    float wsum = 0.0f;

    for (int dx = -@radius; dx <= @radius; dx++) {
        int nx = clamp(pos.x + dx, 0, @xres - 1);
        float sigma = (float)@radius * 0.33f;
        float w = exp(-0.5f * (float)(dx*dx) / (sigma*sigma));
        sum += @src * w;  // at (nx, pos.y)
        wsum += w;
    }
    @dst = sum / wsum;
}

// Pass 2: Vertical blur (OpenCL node #2, same kernel with y)
// Wire: source -> horizontal_blur -> vertical_blur -> output

// Radius 10 comparison:
//   Non-separable: 21*21 = 441 samples/pixel
//   Separable: 21 + 21 = 42 samples/pixel (10.5x faster)
```

## Optimization: Resolution Strategy

```
Production workflow:
  1. Develop at 1K (instant feedback, <5ms per operation)
  2. Test at 2K (verify detail, <50ms per operation)
  3. Final at 4K (production quality, <200ms per operation)

For solvers:
  1. Simulate at 1K-2K (fast iteration on parameters)
  2. Upres to 4K after sim completes (bicubic interpolation)
  3. Add high-frequency detail at full res (noise overlay)

Resolution independence:
  Use @x/@y (normalized 0-1) instead of @ix/@iy (pixel coords)
  Patterns scale naturally across resolutions
```

## Work Group Configuration

```
Default: automatic (Houdini manages this)
RTX 4090 specs:
  128 SMs (Streaming Multiprocessors)
  Warp size: 32 threads
  Max threads per SM: 1536
  Total concurrent threads: 196,608

For most COP work: let Houdini auto-schedule
Manual override scenarios:
  - Shared memory optimizations (rare in COPs)
  - Specific occupancy tuning (advanced)

Typical COP kernel: each pixel = one work item
  4K image: 3840 * 2160 = 8,294,400 work items
  Fills GPU completely (good occupancy)
  1K image: 1,048,576 work items (still fine)
```

## Profiling COP Networks

```python
import hou
import time

# Profile a COP node cook time
node = hou.node("/obj/copnet1/opencl1")

start = time.perf_counter()
node.cook(force=True)
elapsed = time.perf_counter() - start

print(f"Cook time: {elapsed*1000:.1f}ms")

# Profile entire network
copnet = hou.node("/obj/copnet1")
output = copnet.node("OUT")

start = time.perf_counter()
output.cook(force=True)
elapsed = time.perf_counter() - start

print(f"Full network: {elapsed*1000:.1f}ms")

# Per-node breakdown
for child in copnet.children():
    if child.type().name() != "sticky_note":
        start = time.perf_counter()
        child.cook(force=True)
        t = time.perf_counter() - start
        print(f"  {child.name()}: {t*1000:.1f}ms")
```

## Common Performance Pitfalls

```
1. Reading same layer multiple times in one kernel:
   Fix: read once into float4 local variable

2. Using sin()/cos() where native_sin()/native_cos() suffice:
   Fix: use native_ variants for visual effects

3. Non-separable filters at large radius:
   Fix: split into horizontal + vertical passes

4. Too many solver iterations:
   Fix: start with 1-4, increase only if unstable/inaccurate

5. Full RGBA when Mono suffices:
   Fix: use Mono layers for masks, heights, distances (4x less memory)

6. Developing at 4K resolution:
   Fix: iterate at 1K, upres for final only

7. Solver caching too many frames in VRAM:
   Fix: checkpoint to disk, limit cache range

8. Branching on per-pixel conditions:
   Fix: use mix() / select() / smoothstep() instead of if/else
```
