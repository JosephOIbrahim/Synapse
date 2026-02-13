# Crowd Simulation

## Overview

Houdini's crowd system simulates large numbers of animated characters (agents) using a lightweight packed agent representation. Agents carry embedded animation clips, collision shapes, and layers, and are driven through a state machine in DOPs. The system is built on the Agent primitive type -- a packed prim with skeletal animation, shape libraries, and clip blending.

## SOP-Level Setup Chain

```
character_fbx -> agent -> agentlayer (optional) -> agentclip (additional clips)
    -> crowdsource -> crowdstate (initial state assignment)
    -> dopnet(crowdsolver) -> dopimport -> filecache
```

For import to LOPs: `filecache` -> `sopimport` LOP

## Agent Setup

### agent SOP

Creates an Agent primitive from an FBX/BVH/character file. This is the entry point for all crowd work.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Agent Name | `agentname` | agent1 | Unique name for this agent type |
| Input | `input` | FBX File | Source type: FBX, BVH, or Character Rig |
| FBX File | `fbxfile` | (empty) | Path to .fbx character file |
| Convert Units | `convertunits` | 1 | Auto-convert units (cm to m) |
| Clip Name | `clipname` | (auto) | Name for the default animation clip |
| Locomotion Joint | `locomotionjoint` | (auto) | Root joint for locomotion (usually Hips) |
| Locomotion | `locomotion` | 1 | Enable in-place clip conversion |

**Locomotion**: When enabled, the agent SOP strips the root joint's forward translation from the clip and stores it as `locomotion speed`. The crowd solver then moves the agent point in world space at that speed. This is essential -- without it, agents will slide or moonwalk.

### agentclip SOP

Adds additional animation clips to an existing agent.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Clip Name | `name` | clip1 | Name for this clip |
| Source | `source` | FBX Animation File | Where to get the clip |
| FBX File | `fbxfile` | (empty) | Path to FBX with animation |
| Start/End Frame | `startend` | 1/240 | Clip frame range |
| Locomotion | `locomotion` | 1 | Convert to in-place clip |
| Locomotion Joint | `locomotionjoint` | (same as agent) | Root joint name |

### agentlayer SOP

Defines geometry layers on an agent -- different shapes that can be swapped for variation.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Layer Name | `layername` | default | Name of this layer |
| Source | `source` | Current Layer | Inherit existing or start fresh |
| Shape Transform | `shapetransform#` | (varies) | Which joint a shape is bound to |
| Shape Geometry | `shapegeo#` | (varies) | Geometry for this shape |
| Deforming | `deforming#` | 1 | Whether shape deforms with skeleton |

Layers allow swapping armor pieces, helmets, weapons, or clothing per agent. Each layer is a named set of shape bindings.

### agentprep SOP

Prepares agents for simulation. Configures collision shapes, foot joints, and terrain adaptation.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Agent Name | `agentname` | (auto) | Which agent type to configure |
| Show Guide | `showguide` | 1 | Display collision/foot guides |
| Enable Terrain Adapt | `enableterrain` | 0 | Set up terrain following |
| Hip Joint | `hipjoint` | Hips | Joint for terrain offset |
| Foot Joints | `leftfoot`/`rightfoot` | (auto) | Foot joints for foot locking |
| Lower Limb Joints | `leftlowerleg`/`rightlowerleg` | (auto) | Knee joints for IK |
| Upper Limb Joints | `leftupperleg`/`rightupperleg` | (auto) | Hip joints for IK |
| Ankle Offset | `ankleoffset` | 0.0 | Vertical offset from ankle to sole |

**Critical**: Agent Prep must be connected before the DOP network. Without it, terrain adaptation and foot locking will not work. The foot/leg joint names must match the skeleton exactly.

## Crowd Source

### crowdsource SOP

Places agents in the scene with initial positions, orientations, and state assignments.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Number of Agents | `numagents` | 10 | How many agents to scatter |
| Randomize | `randomize` | 1 | Randomize positions |
| Area Shape | `areashape` | Circle | Scatter area (Circle, Rectangle, Custom) |
| Area Size | `areasize` | 10 | Scatter radius/size |
| Formation | `formation` | None | Grid, Circle, Custom |
| Agent Group | `agentgroup` | (empty) | Assign to named group |
| Initial State | `initialstate` | (empty) | Starting state machine state |
| Initial Clip | `initialclip` | (auto) | Starting animation clip |
| Randomize Clip Offset | `randomclipoffset` | 1 | Offset clip start time per agent |
| Max Initial Speed | `maxinitspeed` | 1.0 | Random initial speed range |

### Formation Types

| Formation | Parameter Value | Description |
|-----------|----------------|-------------|
| None | `0` | Random scatter in area |
| Grid | `1` | Regular grid, set rows/columns |
| Circle | `2` | Ring formation |
| Custom Geometry | `3` | Points from input geometry define positions |

For custom formations, wire geometry with points into crowdsource input 2. Each point becomes an agent position. Add `@orient` (quaternion) on input points to control facing direction.

### crowdstate SOP

Assigns initial states to agents before simulation.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| State Name | `statename` | idle | Name of the state to assign |
| Group | `group` | (empty) | Apply to specific agent group |
| Randomize | `randomize` | 0 | Randomly assign from multiple states |

## Crowd Simulation (DOPs)

### DOP Network Setup

```
crowdsource -> dopnet -> dopimport
```

Inside the DOP network:

```
crowdobject -> groundplane (optional) -> crowdsolver -> output
```

### crowdobject DOP

Imports the crowd from SOPs into the DOP simulation.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| SOP Path | `soppath` | (auto) | Path to SOP crowd source |
| Use Object Transform | `useobjecttransform` | 0 | Apply object-level transform |

### crowdsolver DOP

The core simulation engine. Runs the state machine, blends clips, handles avoidance, applies forces.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Substeps | `substeps` | 1 | Solver substeps |
| Avoidance Force | `avoidanceforce` | 1.0 | Strength of inter-agent avoidance |
| Avoidance Radius | `anticipatetime` | 2.0 | Look-ahead time for avoidance (seconds) |
| Max Speed | `maxspeed` | 2.0 | Maximum agent speed (m/s) |
| Max Rotation Speed | `maxrotspeed` | 120 | Max turning rate (deg/s) |
| Max Accel | `maxaccel` | 5.0 | Maximum acceleration |
| Terrain Following | `terrain` | 0 | Enable terrain snap |
| Terrain Object | `terrainobject` | (empty) | DOP object or SOP path for terrain |
| Foot Locking | `enablefootlocking` | 0 | Enable IK foot plant |

### State Machine

Crowd behavior is driven by a state machine. Each state plays a clip, applies forces, and checks triggers for transitions.

#### crowdstate DOP (inside crowdsolver)

Defines a behavioral state.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| State Name | `statename` | state1 | Unique state name |
| Animation Clips | `clipnames` | (empty) | Clip(s) to play in this state |
| Clip Speed Multiplier | `clipspeedmultiplier` | 1.0 | Speed scale on clip playback |
| Blend Time | `blendtime` | 0.3 | Seconds to blend from previous clip |
| Speed Range | `speedrange` | 0/2 | Min/max agent speed in this state |
| Speed Clip Range | `speedcliprange` | (auto) | Map speed to clip blend |

#### crowdtrigger DOP

Defines conditions that cause state transitions.

| Trigger Type | Parameter | Description |
|-------------|-----------|-------------|
| Time in State | `timeinstate` | Fires after N seconds in current state |
| Proximity to Object | `objectdistance` | Fires when near a specific object |
| Proximity to Agent | `agentdistance` | Fires when near another agent |
| Bounding Box | `boundingbox` | Fires when inside a bounding box |
| Particle Speed | `particlespeed` | Fires at a speed threshold |
| Custom VEX | `customvex` | Fires based on VEX expression |
| Crowd Field | `crowdfield` | Fires based on crowd attribute value |
| Object Attribute | `objectattribute` | Fires based on object attribute |

#### crowdtransition DOP

Links a trigger to a state change.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Source State | `sourcestate` | (any) | State to transition from |
| Target State | `targetstate` | (required) | State to transition to |
| Trigger | `trigger` | (required) | Which trigger activates this |
| Duration | `duration` | 0.3 | Transition blend time |
| Priority | `priority` | 0 | Higher priority wins if multiple triggers fire |

### Example State Machine

A basic walk-to-run-to-idle cycle:

```
State: idle (clip=idle_anim, speed=0)
  Trigger: proximity_to_goal (distance < 20)
    -> Transition to: walk

State: walk (clip=walk_cycle, speed=1.0)
  Trigger: proximity_to_goal (distance < 5)
    -> Transition to: idle
  Trigger: speed_threshold (speed > 1.5)
    -> Transition to: run

State: run (clip=run_cycle, speed=2.5)
  Trigger: speed_threshold (speed < 1.2)
    -> Transition to: walk
```

## Terrain Following

### Setup Requirements

1. Agent Prep: Enable terrain adaptation, set hip/foot/leg joints
2. Crowd Solver: Enable `terrain` parm, set `terrainobject` to terrain SOP or DOP object
3. Optional: Enable `enablefootlocking` on crowd solver for IK foot plant

### Terrain Adaptation Parameters (Agent Prep)

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Hip Joint | `hipjoint` | Hips | Joint to offset vertically |
| Hip Offset | `hipoffset` | 0.0 | Additional vertical hip offset |
| Back Adjust | `backadjust` | lean | How to handle slopes: lean or tilt |
| Lean Angle | `leanangle` | 15 | Max forward/back lean in degrees |
| Left/Right Foot | `leftfoot`/`rightfoot` | (auto) | Foot joints for terrain snap |
| Ankle Offset | `ankleoffset` | 0.0 | Distance from ankle joint to foot sole |

### Foot Locking

Foot locking plants feet on the terrain during the grounded phase of a walk/run cycle. It uses IK on the leg chain to adjust foot positions.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Enable | `enablefootlocking` | 0 | Turn on foot planting |
| Lock Blend Time | `lockblendtime` | 0.1 | Blend into locked position (seconds) |
| Unlock Blend Time | `unlockblendtime` | 0.1 | Blend out of locked position |
| Adjust Hips | `adjusthips` | 1 | Lower hips when feet reach down |

**Foot lock channels**: The agent clip must have foot-lock metadata indicating which frames each foot is planted. Use `agentclip` SOP's "Locomotion" tab to auto-detect or manually set planted frames via `s@agentrig_footchannel` attributes.

### Obstacle Avoidance

Built into the crowd solver. Agents steer away from each other and from DOP objects.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Avoidance Force | `avoidanceforce` | 1.0 | Avoidance strength |
| Anticipation Time | `anticipatetime` | 2.0 | Look-ahead time (seconds) |
| Neighbor Distance | `neighbordist` | 5.0 | Radius to check for neighbors |
| Max Neighbors | `maxneighbors` | 6 | Max neighbors to consider |
| FOV | `fov` | 180 | Agent field of view (degrees) |
| Avoidance Weight | `avoidanceweight` | 1.0 | Blend vs other steering forces |

For static obstacles, add `staticobject` DOPs. For animated obstacles, use `rbdobject` or `staticobject` with deforming enabled.

## Agent Variations

### Shape Variation (Agent Layers)

Each agent type can have multiple layers. At crowdsource time, assign layers randomly:

```vex
// In a wrangle after crowdsource:
string layers[] = {"default", "armor_heavy", "armor_light", "casual"};
int idx = int(random(@ptnum) * len(layers));
s@agentcurrentlayer = layers[idx];
```

Or use the crowdsource SOP's `Layer` parameter to specify randomly from available layers.

### Clip Variation

Randomize which animation clip plays per state:

```vex
// In a wrangle on the crowd source:
float r = random(@ptnum + 31);
if (r < 0.33) s@crowdinitialclip = "walk_01";
else if (r < 0.66) s@crowdinitialclip = "walk_02";
else s@crowdinitialclip = "walk_03";

// Random clip offset so agents don't sync
f@crowdinitialcliptime = random(@ptnum) * 30.0;
```

### Material/Style Sheet Variation

Houdini uses CVEX style sheets to vary materials per agent or per shape. Style sheets are applied at render time without duplicating geometry.

Key concepts:
- **Target**: Which agents/shapes the override applies to (by agent name, group, or attribute)
- **Override**: What material property to change (diffuse color, texture path, roughness)

Style sheet JSON structure:
```json
{
  "styles": [
    {
      "target": {"group": "crowd_*", "subTarget": {"shape": "body"}},
      "overrides": {
        "material:parameter": {"diffuseColor": {"type": "random", "min": [0.3,0.2,0.1], "max": [0.8,0.6,0.4]}}
      }
    }
  ]
}
```

In production, style sheets live in a `.json` file referenced by the render settings. They run at render time (Mantra, Karma CPU) and apply material overrides without modifying agent geometry.

**Karma XPU note**: CVEX style sheets are NOT supported in Karma XPU (as of Houdini 20/21). Use MaterialX with per-agent primvars instead, or render crowds with Karma CPU.

### Color/Attribute Variation

```vex
// Vary color per agent at source time
v@Cd = set(random(@ptnum), random(@ptnum+7), random(@ptnum+13));

// Vary scale slightly
f@pscale = fit01(random(@ptnum+99), 0.85, 1.15);

// Store custom attributes for style sheets
f@armor_wear = random(@ptnum + 42);
```

## Crowd Rendering in Solaris/Karma

### SOP Import to LOPs

```
filecache (cached crowd sim) -> sopimport LOP -> materiallibrary -> assignmaterial -> karmarendersettings
```

The `sopimport` LOP brings agent primitives onto the USD stage. Houdini converts each agent to a USD `PointInstancer` or skeletal `SkelRoot` depending on the pipeline approach.

### Point Instancer Approach (Recommended for Large Crowds)

Agents render as point-instanced geometry. Each unique agent type becomes a prototype; each agent in the crowd references a prototype with per-instance transforms.

| Aspect | Detail |
|--------|--------|
| Node | `sopimport` with agent geometry |
| USD Type | `PointInstancer` |
| Prototype | One per unique agent mesh |
| Performance | Excellent -- GPU instancing, minimal memory |
| Limitation | No per-agent skeletal deformation at render time |

Best for: background crowds, distant shots, thousands of agents.

### Skeletal Agent Approach (Hero Crowds)

Each agent maintains its own skeleton and deforms at render time. More expensive but supports full animation fidelity.

| Aspect | Detail |
|--------|--------|
| USD Type | `SkelRoot` + `Skeleton` + `SkelAnimation` |
| Deformation | Full per-agent skin deformation |
| Performance | Expensive -- one draw call per agent |
| Limitation | Scales to hundreds, not thousands |

Best for: foreground/hero crowd members, close-up shots.

### LOD Strategy

Use multiple agent layers with decreasing detail:

| LOD Level | Use Case | Strategy |
|-----------|----------|----------|
| LOD0 (high) | Foreground, < 20m from camera | Full mesh, full skeleton deform |
| LOD1 (mid) | Mid-ground, 20-50m | Reduced mesh, skeletal deform |
| LOD2 (low) | Background, 50-100m | Simple mesh, point instanced |
| LOD3 (billboard) | Far background, > 100m | Card/billboard, no deformation |

In SOPs, create agent layers per LOD level using `agentlayer` SOP. Switch layers based on camera distance in a post-sim wrangle:

```vex
float dist = distance(@P, chv("camera_pos"));
if (dist < 20) s@agentcurrentlayer = "lod0";
else if (dist < 50) s@agentcurrentlayer = "lod1";
else if (dist < 100) s@agentcurrentlayer = "lod2";
else s@agentcurrentlayer = "lod3";
```

### Karma Render Settings for Crowds

| Parameter | Recommendation | Why |
|-----------|---------------|-----|
| Ray Bias | 0.01 | Avoid self-intersection on instanced geo |
| Max Ray Depth | 4-6 | Crowds rarely need deep bounces |
| Pixel Samples | 6-9 for mid, 16+ for hero | Balance noise vs render time |
| Denoiser | OIDN or OptiX | Essential for noisy crowd backgrounds |
| Motion Blur | Per-agent velocity from sim | Use `v@v` from crowd sim for correct blur |

## Key VEX Functions for Crowds

### Agent Introspection

```vex
// Get the agent's current clip name(s)
string clips[] = agentclipcatalog(0, @ptnum);

// Get the current clip time
float t = agentcliptime(0, @ptnum, "walk_cycle");

// Get the current clip weight (for blending)
float w = agentclipweight(0, @ptnum, "walk_cycle");

// Get all clip names available on this agent
string all_clips[] = agentclipcatalog(0, @ptnum);

// Get clip length
float len = agentcliplength(0, @ptnum, "walk_cycle");

// Get the agent's current layer
string layer = agentcurrentlayer(0, @ptnum);

// Get all available layers
string layers[] = agentlayers(0, @ptnum);

// Get the agent's name (type)
string name = agentname(0, @ptnum);
```

### Agent Transform Access

```vex
// Get a specific joint's world transform
matrix xform = agentworldtransform(0, @ptnum, "Hips");

// Get a joint's local transform
matrix local_xform = agentlocaltransform(0, @ptnum, "Spine1");

// Get the joint index by name
int idx = agentrigfind(0, @ptnum, "LeftFoot");

// Get all joint names
string joints[] = agentrigchildren(0, @ptnum, "Hips");

// Get parent joint
string parent = agentrigparent(0, @ptnum, "LeftFoot");
```

### Agent Modification

```vex
// Set current clip and time
setagentcliptime(0, @ptnum, "idle", 5.0);
setagentclipweight(0, @ptnum, "idle", 1.0);

// Change layer
setagentcurrentlayer(0, @ptnum, "armor_heavy");

// Override a joint transform
matrix m = agentworldtransform(0, @ptnum, "Head");
rotate(m, radians(15), {1,0,0});  // tilt head
setagentworldtransform(0, @ptnum, m, "Head");
```

### Crowd Steering (in POP Wrangle inside Crowd Solver)

```vex
// Seek toward a target
vector target = chv("target_pos");
vector desired = normalize(target - @P) * ch("max_speed");
vector steer = desired - @v;
@force += steer * ch("seek_weight");

// Flee from a point
vector threat = chv("threat_pos");
float dist = distance(@P, threat);
if (dist < ch("flee_radius")) {
    vector flee_dir = normalize(@P - threat);
    @force += flee_dir * ch("flee_force") * (1.0 - dist / ch("flee_radius"));
}
```

### Crowd Attribute Reference

Key point attributes on crowd agents:

| Attribute | Type | Description |
|-----------|------|-------------|
| `@P` | vector | Agent world position |
| `@orient` | quaternion | Agent facing direction |
| `@v` | vector | Agent velocity |
| `@up` | vector | Agent up vector |
| `@pscale` | float | Agent scale |
| `s@agentname` | string | Agent type name |
| `s@crowdstate` | string | Current state machine state |
| `s@crowdinitialstate` | string | Starting state |
| `s@crowdinitialclip` | string | Starting animation clip |
| `f@crowdinitialcliptime` | float | Starting clip time offset |
| `f@crowdspeed` | float | Current locomotion speed |
| `f@crowdturnrate` | float | Current turning rate |
| `s@agentcurrentlayer` | string | Active geometry layer |
| `i@crowdactive` | int | Whether agent is active (1) or frozen (0) |
| `f@crowdanimscale` | float | Clip playback speed multiplier |
| `i@id` | int | Unique agent ID (stable across frames) |

## Common Parameters Quick Reference

### DOP Crowd Solver Tabs

| Tab | Key Parameters |
|-----|---------------|
| Simulation | `substeps`, `maxspeed`, `maxrotspeed`, `maxaccel` |
| Avoidance | `avoidanceforce`, `anticipatetime`, `neighbordist`, `maxneighbors`, `fov` |
| Terrain | `terrain`, `terrainobject`, `enablefootlocking`, `adjusthips` |
| Locomotion | `locomotion`, `locomotionnode`, `gait` |
| Fuzzy Logic | `fuzzyvars` (override behavioral weights per-state) |

## Tips and Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| Agents slide/moonwalk | Locomotion not enabled on clip | Enable `locomotion` on `agent`/`agentclip` SOP, verify `locomotionjoint` matches root joint |
| Agents sink into ground | Missing terrain adaptation | Enable terrain on Agent Prep + Crowd Solver, verify `ankleoffset` |
| Agents all move in sync | Same clip start time | Enable `randomclipoffset` on crowdsource, or randomize `f@crowdinitialcliptime` in VEX |
| Foot sliding on terrain | Foot locking not configured | Enable `enablefootlocking` on solver, set foot/leg joints in Agent Prep |
| State machine not triggering | Trigger condition never met | Check trigger type and threshold; use custom VEX trigger for debugging |
| Agents bunch up / overlap | Avoidance too weak | Increase `avoidanceforce`, increase `anticipatetime`, check `neighbordist` |
| Agents jitter on slopes | Terrain resolution too coarse | Increase terrain heightfield resolution or smooth terrain |
| Clip blend pops | Blend time too short | Increase `blendtime` on crowdstate DOP to 0.5-1.0 seconds |
| Memory blowup with many agents | Full skeletal deform per agent | Use point instancing for background agents, LOD layers |
| Style sheets not working in Karma XPU | CVEX not supported | Use Karma CPU for crowd style sheets, or per-agent primvars with MaterialX |
| Agent missing shapes | Layer not loaded | Check `agentlayer` SOP names match what crowdsource/VEX assigns |
| Simulation is slow | Too many agents with full avoidance | Reduce `maxneighbors`, increase `neighbordist` step, disable avoidance for background agents |
| Agents don't follow path | No force toward path | Add a POP Steer Path node or use custom VEX steering force in solver |
| FBX import scale wrong | Unit mismatch (cm vs m) | Enable `convertunits` on agent SOP, or manually scale by 0.01 |

### Performance Guidelines

- **Start small**: Test with 10-20 agents before scaling to thousands
- **Cache early**: `filecache` the crowd sim before any rendering pipeline
- **LOD is essential**: No production crowd renders all agents at full quality
- **Disable avoidance for distant agents**: Group by camera distance, disable avoidance for far groups
- **Use `.bgeo.sc`**: Blosc-compressed format is fastest for agent caching
- **Clip count matters**: Each unique clip adds memory; share clips across agent types where possible
- **Terrain resolution**: Crowd terrain can be lower-res than render terrain -- agents only need slope info
- **Ragdoll transition**: Use the `crowdtrigger` -> `ragdoll` state pattern for agents that get hit/die -- transitions from animated clip to RBD simulation seamlessly
