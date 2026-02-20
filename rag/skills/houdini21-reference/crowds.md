# Crowd Simulation

## Triggers
<!-- triggers: crowd, agent, crowd simulation, crowdsource, crowdsolver, crowd solver, crowdobject, agentclip, agentlayer, agentprep, crowd state machine, crowd trigger, crowd transition, foot locking, terrain following, locomotion, agent variation, crowd rendering, point instancer, skeletal agent, LOD, crowd LOD, agent attributes, crowd attributes, agent transform, crowd steering, style sheet, crowd material, bgeo crowd, crowd cache, ragdoll crowd -->

## Context

Houdini 21 crowd system: packed agent primitives with embedded skeleton + clips, driven by a DOP state machine. Zero Houdini required to read/run these snippets — all use `hou` Python API or VEX wrangles.

```python
# SOP-level setup chain (logical flow, not executable network builder)
# character_fbx -> agent -> agentlayer (optional) -> agentclip (additional clips)
#     -> agentprep -> crowdsource -> crowdstate
#     -> dopnet(crowdobject -> groundplane -> crowdsolver -> output)
#     -> dopimport -> filecache
# For LOPs: filecache -> sopimport LOP -> materiallibrary -> karmarendersettings
```

## Code

### Agent SOP — create agent from FBX

```python
import hou

obj = hou.node("/obj")
geo = obj.createNode("geo", "crowd_setup")
geo.moveToGoodPosition()

# agent SOP: entry point for all crowd work
agent = geo.createNode("agent", "agent1")
agent.parm("input").set(0)                    # 0=FBX File, 1=BVH, 2=Character Rig
agent.parm("fbxfile").set("/path/to/char.fbx")
agent.parm("agentname").set("soldier")
agent.parm("clipname").set("walk_cycle")
agent.parm("locomotion").set(1)               # CRITICAL: strip root translation, store as locomotion speed
agent.parm("locomotionjoint").set("Hips")     # must match root joint in skeleton
agent.parm("convertunits").set(1)             # auto-convert cm -> m (FBX usually cm)
agent.cook()
```

### agentclip SOP — add more animation clips

```python
# Wire after agent SOP to add extra clips
agentclip = geo.createNode("agentclip", "add_clips")
agentclip.setInput(0, agent)

# parms for each clip entry (multiparm, index starts at 1)
agentclip.parm("name1").set("run_cycle")
agentclip.parm("source1").set(0)              # 0=FBX Animation File
agentclip.parm("fbxfile1").set("/path/to/run.fbx")
agentclip.parm("startend1v1").set(1)          # start frame
agentclip.parm("startend1v2").set(120)        # end frame
agentclip.parm("locomotion1").set(1)          # in-place conversion
agentclip.parm("locomotionjoint1").set("Hips")

# add a second clip
agentclip.parm("numentries").set(2)
agentclip.parm("name2").set("idle_anim")
agentclip.parm("source2").set(0)
agentclip.parm("fbxfile2").set("/path/to/idle.fbx")
agentclip.parm("locomotion2").set(0)          # idle has no locomotion
```

### agentlayer SOP — geometry layers for variation

```python
# Layers allow swapping armor, helmets, weapons per agent at source/sim time
agentlayer = geo.createNode("agentlayer", "add_layer")
agentlayer.setInput(0, agentclip)

agentlayer.parm("layername").set("armor_heavy")
agentlayer.parm("source").set(0)              # 0=Current Layer (inherit), 1=Empty

# shape bindings (multiparm)
# shapetransform#: which joint this shape is bound to
# deforming#: whether the shape deforms with the skeleton (1) or is rigid (0)
agentlayer.parm("shapetransform1").set("Spine")
agentlayer.parm("deforming1").set(1)

# For multiple layers, use multiple agentlayer SOPs chained:
# agent -> agentlayer("default") -> agentlayer("armor_heavy") -> agentlayer("armor_light") -> agentprep
```

### agentprep SOP — terrain adaptation + foot locking config

```python
# CRITICAL: Must be connected before dopnet. Without it, terrain + foot locking won't work.
agentprep = geo.createNode("agentprep", "agent_prep")
agentprep.setInput(0, agentlayer)             # or agentclip if no layers

# terrain adaptation
agentprep.parm("enableterrain").set(1)
agentprep.parm("hipjoint").set("Hips")        # joint to offset vertically on slopes
agentprep.parm("hipoffset").set(0.0)
agentprep.parm("backadjust").set(0)           # 0=lean, 1=tilt

# foot joints — names must match skeleton exactly
agentprep.parm("leftfoot").set("LeftFoot")
agentprep.parm("rightfoot").set("RightFoot")
agentprep.parm("leftlowerleg").set("LeftLeg")
agentprep.parm("rightlowerleg").set("RightLeg")
agentprep.parm("leftupperleg").set("LeftUpLeg")
agentprep.parm("rightupperleg").set("RightUpLeg")
agentprep.parm("ankleoffset").set(0.08)       # distance from ankle joint to foot sole (meters)
agentprep.parm("showguide").set(1)            # display collision/foot guides in viewport
```

### crowdsource SOP — scatter agents

```python
crowdsource = geo.createNode("crowdsource", "crowd_src")
crowdsource.setInput(0, agentprep)

crowdsource.parm("numagents").set(500)
crowdsource.parm("areashape").set(0)          # 0=Circle, 1=Rectangle, 2=Custom Geometry
crowdsource.parm("areasize").set(30.0)        # scatter radius (meters)
crowdsource.parm("randomize").set(1)

# formation: 0=None(random), 1=Grid, 2=Circle ring, 3=Custom Geometry points
crowdsource.parm("formation").set(0)

crowdsource.parm("initialstate").set("walk")  # starting state machine state
crowdsource.parm("initialclip").set("walk_cycle")
crowdsource.parm("randomclipoffset").set(1)   # offset clip start time so agents don't sync
crowdsource.parm("maxinitspeed").set(1.0)

# custom geometry input: wire points into input 2
# each point becomes one agent position; add @orient (quaternion) to control facing
# crowdsource.setInput(1, scatter_sop)
```

### crowdstate SOP — assign initial states before sim

```python
crowdstate_sop = geo.createNode("crowdstate", "init_state")
crowdstate_sop.setInput(0, crowdsource)

crowdstate_sop.parm("statename").set("walk")  # state name must match DOP crowdstate
crowdstate_sop.parm("group").set("")          # empty = all agents
crowdstate_sop.parm("randomize").set(0)
```

### DOP Network — crowd simulation

```python
# Build the DOP network programmatically
dopnet = geo.createNode("dopnet", "crowd_sim")
dopnet.setInput(0, crowdstate_sop)
dopnet.moveToGoodPosition()

# Enter the DOP network
dop_context = dopnet

# crowdobject: imports crowd from SOPs into DOPs
crowdobj = dopnet.createNode("crowdobject", "crowd_obj")
crowdobj.parm("soppath").set("../crowd_src")  # relative path to crowdsource SOP
crowdobj.parm("useobjecttransform").set(0)

# groundplane: flat collision surface (optional, use staticobject for terrain)
groundplane = dopnet.createNode("groundplane", "ground")

# crowdsolver: core simulation engine
solver = dopnet.createNode("crowdsolver", "crowd_solver")

# simulation tab
solver.parm("substeps").set(1)
solver.parm("maxspeed").set(2.0)              # max agent speed (m/s)
solver.parm("maxrotspeed").set(120.0)         # max turning rate (deg/s)
solver.parm("maxaccel").set(5.0)

# avoidance tab
solver.parm("avoidanceforce").set(1.0)        # inter-agent avoidance strength
solver.parm("anticipatetime").set(2.0)        # look-ahead seconds for avoidance
solver.parm("neighbordist").set(5.0)          # radius to check for neighbors
solver.parm("maxneighbors").set(6)
solver.parm("fov").set(180.0)                 # agent field of view (degrees)

# terrain tab
solver.parm("terrain").set(1)                 # enable terrain snap
solver.parm("terrainobject").set("ground")    # DOP object name or SOP path
solver.parm("enablefootlocking").set(1)       # IK foot planting
solver.parm("lockblendtime").set(0.1)
solver.parm("unlockblendtime").set(0.1)
solver.parm("adjusthips").set(1)              # lower hips when feet reach down

# wire: crowdobject + groundplane -> crowdsolver -> output
merge_node = dopnet.createNode("merge", "merge_objects")
merge_node.setInput(0, crowdobj)
merge_node.setInput(1, groundplane)
solver.setInput(0, merge_node)

output = dopnet.createNode("output", "output")
output.setInput(0, solver)
```

### State Machine inside crowdsolver DOP — walk/run/idle example

```python
# crowdstate DOP nodes define behavioral states inside the crowdsolver subnet
# Access the solver's subnet (in Houdini 21, crowdsolver has an embedded network)

# State: idle
state_idle = solver.createNode("crowdstate", "state_idle")
state_idle.parm("statename").set("idle")
state_idle.parm("clipnames").set("idle_anim")
state_idle.parm("clipspeedmultiplier").set(1.0)
state_idle.parm("blendtime").set(0.3)         # seconds to blend from previous clip

# State: walk
state_walk = solver.createNode("crowdstate", "state_walk")
state_walk.parm("statename").set("walk")
state_walk.parm("clipnames").set("walk_cycle")
state_walk.parm("blendtime").set(0.3)
state_walk.parm("speedrange1").set(0.5)       # min speed for this state
state_walk.parm("speedrange2").set(2.0)       # max speed for this state

# State: run
state_run = solver.createNode("crowdstate", "state_run")
state_run.parm("statename").set("run")
state_run.parm("clipnames").set("run_cycle")
state_run.parm("blendtime").set(0.5)
state_run.parm("speedrange1").set(2.0)
state_run.parm("speedrange2").set(6.0)

# Trigger: time in state -> idle to walk
trig_idle_walk = solver.createNode("crowdtrigger", "trig_idle_walk")
trig_idle_walk.parm("type").set(0)            # 0=Time in State
trig_idle_walk.parm("timeinstate").set(2.0)   # fire after 2 seconds in idle

# Trigger: speed threshold -> walk to run
trig_walk_run = solver.createNode("crowdtrigger", "trig_walk_run")
trig_walk_run.parm("type").set(4)             # 4=Particle Speed
trig_walk_run.parm("speedthreshold").set(1.8)
trig_walk_run.parm("speedcompare").set(1)     # 1 = greater than

# Trigger: speed threshold -> run to walk
trig_run_walk = solver.createNode("crowdtrigger", "trig_run_walk")
trig_run_walk.parm("type").set(4)
trig_run_walk.parm("speedthreshold").set(1.2)
trig_run_walk.parm("speedcompare").set(0)     # 0 = less than

# Transition: idle -> walk
trans_ij = solver.createNode("crowdtransition", "trans_idle_walk")
trans_ij.parm("sourcestate").set("idle")
trans_ij.parm("targetstate").set("walk")
trans_ij.parm("trigger").set("trig_idle_walk")
trans_ij.parm("duration").set(0.3)
trans_ij.parm("priority").set(0)

# Transition: walk -> run
trans_wr = solver.createNode("crowdtransition", "trans_walk_run")
trans_wr.parm("sourcestate").set("walk")
trans_wr.parm("targetstate").set("run")
trans_wr.parm("trigger").set("trig_walk_run")

# Transition: run -> walk
trans_rw = solver.createNode("crowdtransition", "trans_run_walk")
trans_rw.parm("sourcestate").set("run")
trans_rw.parm("targetstate").set("walk")
trans_rw.parm("trigger").set("trig_run_walk")
```

### dopimport + filecache — bring sim results back to SOPs

```python
# After dopnet node
dopimport = geo.createNode("dopimport", "crowd_import")
dopimport.setInput(0, dopnet)
dopimport.parm("doppath").set("../crowd_sim")
dopimport.parm("import").set(0)               # 0=All Objects

filecache = geo.createNode("filecache", "crowd_cache")
filecache.setInput(0, dopimport)
filecache.parm("file").set('$HIP/cache/crowd/crowd.$F4.bgeo.sc')  # .bgeo.sc = Blosc-compressed, fastest
filecache.parm("loadfromdisk").set(0)         # 0=write mode; set to 1 to load cached frames
```

### VEX — agent variations at source time

```vex
// Run in a wrangle after crowdsource, before dopnet
// Randomize layer per agent
string layers[] = {"default", "armor_heavy", "armor_light", "casual"};
int idx = int(random(@ptnum) * len(layers));
s@agentcurrentlayer = layers[idx];

// Randomize initial clip from multiple variants
float r = random(@ptnum + 31);
if (r < 0.33)      s@crowdinitialclip = "walk_01";
else if (r < 0.66) s@crowdinitialclip = "walk_02";
else               s@crowdinitialclip = "walk_03";

// Random clip offset so agents don't animate in sync
f@crowdinitialcliptime = random(@ptnum) * 30.0;

// Color variation (picked up by style sheets or per-agent primvars)
v@Cd = set(random(@ptnum), random(@ptnum + 7), random(@ptnum + 13));

// Slight scale variation for visual diversity
f@pscale = fit01(random(@ptnum + 99), 0.85, 1.15);

// Custom attributes for style sheet targeting
f@armor_wear = random(@ptnum + 42);   // 0=pristine, 1=heavily worn
```

### VEX — LOD layer switching by camera distance

```vex
// Run in a post-sim wrangle (after dopimport, before render)
// Requires camera world position passed via detail attribute or channel
vector cam = chv("camera_pos");   // set channel to camera position
float dist = distance(@P, cam);

if      (dist < 20.0)  s@agentcurrentlayer = "lod0";  // full mesh, full skeleton
else if (dist < 50.0)  s@agentcurrentlayer = "lod1";  // reduced mesh, skeletal
else if (dist < 100.0) s@agentcurrentlayer = "lod2";  // simple mesh, point instanced
else                   s@agentcurrentlayer = "lod3";  // billboard card, no deformation

// Freeze distant agents to save simulation cost
if (dist > 150.0) i@crowdactive = 0;
else              i@crowdactive = 1;
```

### VEX — agent introspection (read-only, in a wrangle)

```vex
// Get all clips available on this agent
string clips[] = agentclipcatalog(0, @ptnum);

// Current clip playback time
float t = agentcliptime(0, @ptnum, "walk_cycle");

// Current clip blend weight (0-1)
float w = agentclipweight(0, @ptnum, "walk_cycle");

// Clip duration in seconds
float len = agentcliplength(0, @ptnum, "walk_cycle");

// Current geometry layer name
string layer = agentcurrentlayer(0, @ptnum);

// All available geometry layers
string all_layers[] = agentlayers(0, @ptnum);

// Agent type name (set by agent SOP agentname parm)
string aname = agentname(0, @ptnum);
```

### VEX — joint/skeleton access

```vex
// World transform of a named joint
matrix xform = agentworldtransform(0, @ptnum, "Hips");

// Local transform of a joint
matrix local_xform = agentlocaltransform(0, @ptnum, "Spine1");

// Joint index by name (use for bulk operations)
int idx = agentrigfind(0, @ptnum, "LeftFoot");

// Child joints of a given joint
string children[] = agentrigchildren(0, @ptnum, "Hips");

// Parent joint name
string parent = agentrigparent(0, @ptnum, "LeftFoot");

// Bone count
int bone_count = len(agentrigchildren(0, @ptnum, ""));
```

### VEX — modify agent state at run time

```vex
// Force a specific clip and playhead position
setagentcliptime(0, @ptnum, "idle", 5.0);
setagentclipweight(0, @ptnum, "idle", 1.0);
setagentclipweight(0, @ptnum, "walk_cycle", 0.0);  // zero out other clips

// Change geometry layer (e.g. hit response: swap to damaged version)
setagentcurrentlayer(0, @ptnum, "armor_damaged");

// Override a joint transform: tilt the head
matrix m = agentworldtransform(0, @ptnum, "Head");
rotate(m, radians(15.0), {1, 0, 0});
setagentworldtransform(0, @ptnum, m, "Head");
```

### VEX — custom steering forces (POP Wrangle inside Crowd Solver)

```vex
// Seek toward a target point
vector target   = chv("target_pos");
float max_speed = ch("max_speed");
float seek_wt   = ch("seek_weight");
vector desired  = normalize(target - @P) * max_speed;
vector steer    = desired - @v;
@force += steer * seek_wt;

// Flee from a threat within radius
vector threat     = chv("threat_pos");
float flee_radius = ch("flee_radius");
float flee_force  = ch("flee_force");
float dist        = distance(@P, threat);
if (dist < flee_radius) {
    vector flee_dir = normalize(@P - threat);
    float falloff   = 1.0 - dist / flee_radius;
    @force += flee_dir * flee_force * falloff;
}

// Separation: push agents apart if too close (supplement built-in avoidance)
float sep_radius = ch("sep_radius");
float sep_force  = ch("sep_force");
int neighbors[] = pcfind(0, "P", @P, sep_radius, 8);
foreach (int nb; neighbors) {
    if (nb == @ptnum) continue;
    vector diff = @P - point(0, "P", nb);
    float d = length(diff);
    if (d > 0.001)
        @force += normalize(diff) * sep_force * (1.0 - d / sep_radius);
}
```

### VEX — custom VEX trigger expression

```vex
// Inside a crowdtrigger DOP with type=Custom VEX
// Return 1 to fire the trigger, 0 to stay in current state

// Example: fire when agent is within 8m of a "panic zone" defined by a detail attrib
vector panic_center = detail(0, "panic_center", 0);
float panic_radius  = detail(0, "panic_radius", 0);
float dist          = distance(@P, panic_center);
return (dist < panic_radius) ? 1 : 0;
```

### Python — crowd attribute reference dictionary

```python
# Key point attributes on crowd agent primitives (for reference in Python/VEX)
CROWD_ATTRIBS = {
    # core position/motion
    "P":                     ("vector",  "agent world position"),
    "orient":                ("vector4", "agent facing direction (quaternion)"),
    "v":                     ("vector",  "agent velocity"),
    "up":                    ("vector",  "agent up vector"),
    "pscale":                ("float",   "agent uniform scale"),

    # state machine
    "crowdstate":            ("string",  "current state machine state name"),
    "crowdinitialstate":     ("string",  "starting state at sim start"),
    "crowdinitialclip":      ("string",  "starting animation clip"),
    "crowdinitialcliptime":  ("float",   "starting clip time offset (seconds)"),

    # locomotion
    "crowdspeed":            ("float",   "current locomotion speed (m/s)"),
    "crowdturnrate":         ("float",   "current turning rate (deg/s)"),
    "crowdanimscale":        ("float",   "clip playback speed multiplier"),

    # agent type/layer
    "agentname":             ("string",  "agent type name (set by agent SOP)"),
    "agentcurrentlayer":     ("string",  "active geometry layer name"),

    # sim control
    "crowdactive":           ("int",     "1=active, 0=frozen (no sim cost)"),
    "id":                    ("int",     "unique stable agent ID across frames"),
}

# Access pattern in Python (after dopimport, on a SOP geometry)
geo = hou.node("/obj/crowd_setup/crowd_import").geometry()
for pt in geo.points():
    state = pt.attribValue("crowdstate")
    speed = pt.attribValue("crowdspeed")
    agent = pt.attribValue("agentname")
    print(f"pt {pt.number()}: agent={agent} state={state} speed={speed:.2f}")
```

### Python — crowdsolver DOP parameter reference dictionary

```python
# crowdsolver DOP parm names by tab
CROWDSOLVER_PARMS = {
    "Simulation": {
        "substeps":    "solver substeps (1 usually sufficient)",
        "maxspeed":    "maximum agent speed m/s (default 2.0)",
        "maxrotspeed": "max turning rate deg/s (default 120)",
        "maxaccel":    "maximum acceleration (default 5.0)",
    },
    "Avoidance": {
        "avoidanceforce":  "inter-agent avoidance strength (default 1.0)",
        "anticipatetime":  "look-ahead seconds for collision avoidance (default 2.0)",
        "neighbordist":    "radius to scan for neighbors (default 5.0)",
        "maxneighbors":    "max neighbors considered per agent (default 6)",
        "fov":             "agent field of view degrees (default 180)",
        "avoidanceweight": "blend avoidance vs other steering (default 1.0)",
    },
    "Terrain": {
        "terrain":          "enable terrain snap (0/1)",
        "terrainobject":    "DOP object name or SOP path for terrain",
        "enablefootlocking":"IK foot planting (0/1)",
        "lockblendtime":    "seconds to blend into locked foot position",
        "unlockblendtime":  "seconds to blend out of locked foot position",
        "adjusthips":       "lower hips when feet reach down (0/1)",
    },
    "Locomotion": {
        "locomotion":     "enable locomotion-based movement (0/1)",
        "locomotionnode": "which SOP node provides locomotion data",
        "gait":           "gait selection mode",
    },
}

# Apply recommended settings for a mid-size crowd (500-2000 agents)
solver = hou.node("/obj/crowd_setup/crowd_sim/crowd_solver")
solver.parm("substeps").set(1)
solver.parm("maxspeed").set(3.0)
solver.parm("maxrotspeed").set(90.0)
solver.parm("avoidanceforce").set(1.5)
solver.parm("anticipatetime").set(1.5)
solver.parm("maxneighbors").set(4)            # reduce for performance at scale
solver.parm("terrain").set(1)
solver.parm("enablefootlocking").set(1)
```

### Python — SOP import to Solaris/LOPs for Karma rendering

```python
# Bring cached crowd into USD stage for Karma rendering
stage_context = hou.node("/stage")
if not stage_context:
    stage_context = hou.node("/obj").createNode("lopnet", "stage")

sopimport = stage_context.createNode("sopimport", "crowd_import")
sopimport.parm("soppath").set("/obj/crowd_setup/crowd_cache")
# sopimport converts agent packed prims to:
#   PointInstancer (default, recommended for large crowds: GPU instancing, low memory)
#   SkelRoot + Skeleton + SkelAnimation (hero agents, full per-agent skin deform)

matlib = stage_context.createNode("materiallibrary", "crowd_mats")
matlib.setInput(0, sopimport)
matlib.cook(force=True)                       # MUST cook matlib before adding shader children

assign = stage_context.createNode("assignmaterial", "assign_crowd")
assign.setInput(0, matlib)

karma = stage_context.createNode("karma", "karma_render")
karma.setInput(0, assign)

# Karma settings optimized for crowd background rendering
karma.parm("camera").set("/cameras/render_cam")
karma.parm("resolutionx").set(1920)
karma.parm("resolutiony").set(1080)
karma.parm("picture").set('$HIP/render/crowd.$F4.exr')

# Karma render settings for crowds
karma.parm("vm_raybias").set(0.01)            # avoid self-intersection on instanced geo
karma.parm("vm_maxraysamples").set(9)         # 6-9 for mid crowd, 16+ for hero
karma.parm("allowmotionblur").set(1)          # use v@v from crowd sim for correct blur
# Note: OIDN or OptiX denoiser essential for noisy crowd backgrounds
```

### JSON — style sheet for per-agent material variation (Karma CPU only)

```python
import json

# CVEX style sheets NOT supported in Karma XPU (Houdini 20/21)
# Use Karma CPU for crowd style sheets, or per-agent primvars with MaterialX for XPU

style_sheet = {
    "styles": [
        {
            # target agents in group "crowd_*", shape "body"
            "target": {
                "group": "crowd_*",
                "subTarget": {"shape": "body"}
            },
            "overrides": {
                "material:parameter": {
                    "diffuseColor": {
                        "type": "random",
                        "min": [0.3, 0.2, 0.1],   # dark brown
                        "max": [0.8, 0.6, 0.4]    # light tan
                    }
                }
            }
        },
        {
            # override using a custom per-agent attribute (armor_wear)
            "target": {"group": "crowd_*"},
            "overrides": {
                "material:parameter": {
                    "roughness": {
                        "type": "attribute",
                        "name": "armor_wear"        # float attrib set in VEX
                    }
                }
            }
        }
    ]
}

style_path = hou.expandString("$HIP/crowd_styles.json")
with open(style_path, "w", encoding="utf-8") as f:
    json.dump(style_sheet, f, indent=2, sort_keys=True)
print(f"Style sheet written to: {style_path}")
```

### Python — performance: disable avoidance for distant agents via groups

```python
# Group agents by camera distance, disable avoidance for far group
# Run this in a Python SOP or pre-sim expression

geo = hou.node("/obj/crowd_setup/crowd_cache").geometry().freeze(True)
cam_node = hou.node("/obj/cam1")
cam_pos  = cam_node.worldTransform().extractTranslates() if cam_node else hou.Vector3(0, 0, 0)

near_group = geo.findPointGroup("near_crowd") or geo.createPointGroup("near_crowd")
far_group  = geo.findPointGroup("far_crowd")  or geo.createPointGroup("far_crowd")

for pt in geo.points():
    dist = (pt.position() - cam_pos).length()
    if dist < 60.0:
        near_group.add(pt)
    else:
        far_group.add(pt)
        pt.setAttribValue("crowdactive", 0)   # freeze distant agents

print(f"near={near_group.numElements()} far={far_group.numElements()}")
```

## Common Mistakes

```python
# MISTAKE 1: locomotion not enabled -> agents slide / moonwalk
# Fix: enable locomotion on agent SOP AND each agentclip SOP
agent.parm("locomotion").set(1)
agent.parm("locomotionjoint").set("Hips")     # must match root joint exactly

# MISTAKE 2: agents sink into ground
# Fix: enable terrain on both Agent Prep AND Crowd Solver
agentprep.parm("enableterrain").set(1)
solver.parm("terrain").set(1)
solver.parm("terrainobject").set("ground")
agentprep.parm("ankleoffset").set(0.08)       # tune to character foot height

# MISTAKE 3: all agents animate in sync (visible ripple wave)
# Fix: randomize clip offset
crowdsource.parm("randomclipoffset").set(1)
# OR in VEX:
# f@crowdinitialcliptime = random(@ptnum) * 30.0;

# MISTAKE 4: foot sliding on terrain
# Fix: foot locking requires joint names set in agentprep AND enabled on solver
agentprep.parm("leftfoot").set("LeftFoot")    # must match skeleton exactly
agentprep.parm("rightfoot").set("RightFoot")
solver.parm("enablefootlocking").set(1)

# MISTAKE 5: agents bunch up / overlap
# Fix: increase avoidance parameters
solver.parm("avoidanceforce").set(2.0)
solver.parm("anticipatetime").set(2.5)
solver.parm("neighbordist").set(6.0)

# MISTAKE 6: state machine not triggering
# Debug with a custom VEX trigger that prints state:
# In crowdtrigger VEX expression (type=Custom VEX):
# printf("pt %d state=%s dist=%f\n", @ptnum, s@crowdstate, distance(@P, chv("target")));
# return 0;   // don't fire, just log

# MISTAKE 7: style sheets not working -> using Karma XPU
# Fix: CVEX style sheets require Karma CPU. Switch renderer or use per-agent primvars with MaterialX.

# MISTAKE 8: agent shapes missing after sim
# Cause: layer name in VEX doesn't match agentlayer SOP name
# Fix: check exact layer names
geo = hou.node("/obj/crowd_setup/agent_prep").geometry()
pt = geo.points()[0]
available = hou.vex.runSnippet('string l[] = agentlayers(0, @ptnum); printf("%s\\n", l);',
                               geometry=geo, ptnum=0)
# Or in a wrangle: printf("%s\n", agentlayers(0, @ptnum));

# MISTAKE 9: memory blowup with large crowd
# Fix: use point instancing (not skeletal) for background agents + LOD layers
# Full skeletal deform: use only for foreground/hero agents (< 200 agents)
# Point instancer: thousands of background agents, GPU instancing, minimal memory

# MISTAKE 10: FBX imports at wrong scale (agents too small/large)
# Fix: FBX is usually in cm, Houdini works in m
agent.parm("convertunits").set(1)             # auto cm->m
# If still wrong, manually scale:
# f@pscale = 0.01;   // or set pscale in a wrangle

# MISTAKE 11: clip blend pops (harsh transition)
# Fix: increase blendtime
state_walk.parm("blendtime").set(0.5)         # 0.5-1.0 seconds for smooth blends

# MISTAKE 12: sim caching to .bgeo is slow
# Fix: use Blosc-compressed format
filecache.parm("file").set('$HIP/cache/crowd/crowd.$F4.bgeo.sc')  # .bgeo.sc is fastest

# MISTAKE 13: agents don't follow a path
# Fix: no built-in path following — add a POP Steer Path node or custom VEX seek force
# See steering VEX example in ## Code section above

# MISTAKE 14: dopimport is slow / unresponsive
# Cause: soho_foreground=1 blocks Houdini on large sims
# Fix: cache crowd sim first with filecache, then load from disk
filecache.parm("loadfromdisk").set(1)
```
