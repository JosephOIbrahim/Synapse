# Pyro FX Setup Guide

## SOP-Level Pyro Chain

```
sphere(source) → scatter(5000pts) → attribwrangle(emission) → volumerasterizeattributes → pyrosolver
```

## Source Wrangle (VEX)

```vex
f@density = 1.0;
f@temperature = 2.0;
f@flame = 1.0;
f@pscale = 0.05;
v@v = set(0, 3, 0);  // upward velocity
```

## Volume Rasterize Setup

- Set `attributes` parm to: `density temperature flame`
- Input must have scattered points (not raw geometry)
- Points need `@pscale` attribute for volume radius

## Pyro Solver Key Parameters

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Voxel Size | `divsize` | 0.1 | Smaller = more detail, slower |
| Time Scale | `timescale` | 1.0 | Simulation speed |
| Dissipation | `dissipation` | 0.1 | Smoke fade rate |
| Temperature Cooling | `tempcooling` | 0.5 | Flame cooling speed |
| Enable Disturbance | `enable_disturbance` | 0 | Turbulence toggle |
| Disturbance | `disturbance` | 0.5 | Turbulence strength |
| Resize Padding | `resize_padding` | 0.3 | Container growth |

## Import to Solaris

Use `sopimport` LOP with `soppath` pointing to the pyrosolver node.
Wire into scene merge.

## Rendering Pyro

Karma XPU renders volumes natively. No special setup needed beyond sopimport.
For better quality: increase `samples` on karmarenderproperties.
