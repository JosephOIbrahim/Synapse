**SYNAPSE ****&**** WORLD LABS // TECHNICAL ARCHITECTURE SPECIFICATION**
**SYNAPSE × World Labs: Spatial Intelligence ****&**** OpenUSD Blueprint**
*First-Principles Foundation for Houdini 22 Solaris, Gaussian Radiance Fields, and Generative World Models*

| **Target Engine: **Houdini 22 Solaris (Karma XPU) | **Model Provider: **World Labs (Marble World Model) | **Protocol: **OpenUSD 24.x Component |
| --- | --- | --- |
| **Document Status: **Engineering Blueprint | **Authoring Domain: **Spatial Intelligence & Layout | **Document Revision: **v1.0 (Production Release) |

# **1. Executive Summary ****&**** First Principles**

The convergence of generative artificial intelligence and visual effects represents a fundamental paradigm shift. For decades, visual effects production has relied on deterministic, physically accurate, and hierarchically organized scene graphs. Conversely, recent breakthroughs in artificial intelligence have focused predominantly on 2D generative diffusion models—systems that generate compelling pixels but lack underlying geometric awareness, scale persistence, or physical coherence.

World Labs (founded by Dr. Fei-Fei Li) introduces world models: generative systems capable of outputting persistent, metric, three-dimensional spaces rather than ephemeral flat video streams. However, raw generative outputs cannot be dropped directly into an enterprise VFX pipeline without rigorous structural discipline. SYNAPSE serves as the critical architectural bridge, translating the stochastic outputs of world models into deterministic, highly optimized OpenUSD assets inside SideFX Houdini 22 Solaris.

| **CORE DESIGN PRINCIPLES** • Structure Before Appearance: Environments must be structurally understood and queryable long before high-density radiance fields are evaluated. • Deterministic Normalization: Coordinate transforms, metric scales, and ground offsets must be calculated idempotently with cryptographic provenance. • Zero-Cost Interactive Traversal: Viewports must remain responsive at 60 FPS by enforcing payload segregation and proxy boundaries. • Bidirectional Steerability: Artists must be able to inject coarse geometric constraints into the world model and receive structured worlds back without losing layout alignment. |
| --- |

# **2. The Substrate Split: Appearance vs. Structure**

Generative 3D models output dual-representation assets consisting of Gaussian Radiance Fields (stored as SPZ or PLY) and polygonal meshes (stored as GLB). A catastrophic architectural error is attempting to perform spatial queries, bounding checks, or procedural dressing directly on the radiance field. SYNAPSE establishes a strict functional demarcation between appearance and structure:

| **Domain** | **Appearance Substrate (The Splat)** | **Structural Substrate (The Collider)** |
| --- | --- | --- |
| **Asset Format** | Compressed SPZ or raw PLY (500k to 2M Gaussians) | Coarse manifold triangular mesh GLB (100k–200k tris) |
| **USD Purpose** | purpose = render (hidden from OpenGL viewport) | purpose = proxy (active in OpenGL / Hydra viewport) |
| **Payload Rule** | Strict USD Payload on disk; never unpacked in memory | Authored as default proxy representation for layout |
| **Memory Cost** | Up to 360 MB raw spherical harmonics (f_rest_0..44) | Lightweight (~12–25 MB mesh buffer) |
| **Primary Consumers** | Karma XPU, Husk render engine, Relight GSplats LOP | scatterinstances, spatial classifiers, physics sims |
| **Analytical Role** | Visual radiance, view-dependent color, alpha opacity | Surface normals, height fields, occlusion, collision |

# **3. Idempotent Coordinate ****&**** Frame Normalization**

Generative models natively output geometry within camera-centric coordinate spaces, typically the OpenCV convention (+Y pointing downward toward gravity, +Z pointing forward into the scene). In contrast, SideFX Houdini, Solaris, and standard OpenUSD run in a Y-Up, right-handed coordinate system (+Y pointing upward, -Z pointing forward). SYNAPSE enforces a mathematical three-stage normalization sequence in strict order:

• Metric Rescaling: Normalize synthetic units to physical meters. Multiply point centroids P and scales by metric_scale_factor (additive for log scales scale_0..2).

• Ground Plane Registration: Derive the dominant horizontal ground plane from face normals and offset Y to seat the world exactly at Y = 0.

• Frame & Chirality Transform: Apply a 180-degree rotation about the X-axis (scale Y and Z by -1) to map OpenCV coordinates into Houdini world space.

Provenance Tracking: To prevent destructive double-transformations, SYNAPSE authors customData:worldlabs:applied_transforms into the USD prim metadata, ensuring absolute idempotency across pipeline hops.

# **4. OpenUSD Component Architecture ****&**** Stage Topology**

Every generated world is packaged as a single OpenUSD component referenced by payload on disk. The component topology strictly separates the heavy radiance field from the lightweight collider:

/WL_<world_id> [Xform, kind=component]
  ├── customData:worldlabs = { world_id, metric_scale, ground_offset, coordinate_system, applied }
  ├── variantSet splatTier = { full (2M) | low (500k) }
  ├── variantSet physics   = { none | collision (UsdPhysicsCollisionAPI) }
  └── /geo
        ├── /splat    [Points/GSplat, purpose=render, payload=on-disk]
        └── /collider [Mesh, purpose=proxy, payload=on-disk]

# **5. The Spatial Intelligence Lane (Geometric Signal Fields)**

SYNAPSE replaces fragile text-guessing with deterministic spatial signal fields computed directly over the stage geometry. The spatial lane provides four core query tools:

| **Tool Name** | **Input** | **Computed Signal Field** | **Pipeline Execution** |
| --- | --- | --- | --- |
| **synapse_spatial_describe** | Stage path, prim pattern | Bounding box cache, kind/purpose hierarchy | Validates scale sanity and identifies ungrounded assets. |
| **synapse_spatial_classify** | Collider prim, angle thresholds | Normal dot product (N · Y_up) | Classifies surfaces into Floor (<35°), Wall (55°–125°), and Ceiling. |
| **synapse_spatial_openings** | Wall mesh, clearance params | Planar gaps in walls with height ≥ 2.0m | Identifies doorways, windows, and navigation portals. |
| **synapse_spatial_frustum** | Camera prim, target bounds | Pyramidal view-frustum intersection | Scores hero placement candidates and culls off-screen instancing. |

# **6. Houdini 22 Solaris Native Integration Patterns**

• Procedural Instancing: Uses Houdini 22's native scatterinstances LOP wired to the collider mesh proxy, evaluating Up Axis and Camera masks inside Hydra procedurals at render time.
• Relighting Splats: labs::relight_gsplats LOP modulates splat radiance using stage lights (Dome, Distant, Rect) and BSDF shading.
• Occlusion & Shadowing: Automatically authors Karmablockerlightfilter prims via light:filters USD relationships to prevent light leaking.
• Production Render Passes: UsdRender.Pass schema chains execute isolated foreground CG and background generative passes via husk.
