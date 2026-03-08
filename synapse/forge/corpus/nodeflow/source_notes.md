SYNAPSE SOLARIS TRAINING — Mario Leone / NodeFlow Series (Houdini 21)
VIDEO 1: Full USD Scene Workflow from Scratch (12:17)
What is USD & Solaris (0:19–2:07)
Solaris is Houdini's context built specifically around USD (Universal Scene Description). Before USD, artists had to juggle formats like Alembic, OBJ, and FBX — each with different capabilities for geometry, cameras, materials, and lighting. Pixar created USD as a single ecosystem that carries everything. SideFX built Solaris (also called "Stage" / LOPs — Layout Operators) as the context for scene management, organization, lighting, shading, and rendering using USD natively.
Hotkey: Press N to switch contexts → select "Solaris" (Stage/LOPs).
Node Network Architecture — Full Template
Here's the exact node chain built in the tutorial, top to bottom:
Primitive LOP
  ├── (defines Xform hierarchy: /shot/geo, /shot/LGT, /shot/MTL, /shot/cam)
  │
SOP Create (or SOP Import)
  ├── Inside: geometry + Name attribute + Output node
  │   (Name attribute gives identity: e.g., "pig_geo")
  │   (Output node ensures export regardless of display flag)
  │
  ├── Primitive Path: /shot/geo/$OS
  │
[Additional SOP Imports cascade — do NOT merge, chain sequentially]
  │
Camera LOP
  ├── Primitive Path: /shot/cam/$OS
  │   (Drag into viewport → Lock → Pilot camera)
  │
Material Library LOP
  ├── Inside: Karma Material Builder (KMB) nodes
  │   (One KMB per material, named per asset)
  ├── Primitive Path: /shot/MTL/$OS
  ├── Auto-fill Materials → assign geometry per material
  │
Karma Physical Sky LOP
  ├── Primitive Path: /shot/LGT/$OS
  │
Karma Render Settings (created via "Karma" setup node = 2 nodes)
  ├── Engine: Karma XPU (GPU)
  ├── Resolution set here
  ├── Camera: point to /shot/cam/camera1
  │
USD Render ROP
  ├── Output path: $HIP/render/$HIPNAME.png
  ├── References settings from Karma Render Settings
  └── Click "Render to Disk"
Key Workflow Rules

Cascading, not merging: Chain SOP imports sequentially (one after the other) instead of merging — this relates to USD layers
Always add an Output node inside SOP Create to ensure the name attribute and all operations export correctly regardless of display flag
Name attribute inside SOPs gives geometry an identity in the USD hierarchy
Primitive paths control where things land in the outliner: /shot/geo/$OS, /shot/LGT/$OS, /shot/MTL/$OS, /shot/cam/$OS
Primitive Kind: Set Xforms to "Group" in the Primitive LOP for proper hierarchy
Save scene (Ctrl+S) to dismiss import warnings

Template Creation
After building the network: delete specific geometry/materials, leave the skeleton with paths intact → drag network into a new Shelf Tab → name it (e.g., "Basic Template") → set input node = Primitive LOP, output = USD Render ROP → assign a hotkey for instant recall.
VIDEO 2: Intro to Component Builder (11:27)
Component Builder — The Standard Asset Pipeline
The Component Builder is the production-standard way to create properly structured USD assets in Solaris. It creates an asset with purpose, materials, variants, and export capabilities.
Node Network — Component Builder
Component Builder (subnet containing):
  │
  ├── Component Geometry (SOPs context inside)
  │     ├── File/Import → your geometry
  │     ├── Connect to "default" output (full-res render version)
  │     ├── PolyReduce (e.g., 5-10%) → connect to "proxy" output
  │     └── (Optional) sim proxy output (for physics)
  │
  ├── Material Library
  │     └── Karma Material Builder (named, e.g., "red")
  │
  ├── Component Material (auto-assigns material to geometry)
  │
  └── Component Output
        ├── Name: defines exported asset name
        ├── File path: where USD is saved
        ├── Thumbnail: View Thumbnail Camera → Generate Thumbnail
        └── Save to Disk → exports .usd file
Purpose (Critical Concept)
Purpose controls what gets shown where:

Render purpose = full-res geometry shown at render time
Proxy purpose = low-poly version shown in viewport for performance
Sim proxy = low-poly for physics/collision tools
Toggle viewport between proxy and render: Glasses icon → "Preview" vs "Final Render"

Asset Gallery / Asset Catalog

Open: New Pane → Solaris → Asset Catalog
Create new database: Gear icon → "Create New Asset Database File"
Order of operations: Generate Thumbnail → Save to Disk → Add to Asset Catalog
Assets can then be dragged and dropped from the gallery into any scene

Importing Exported Assets
Use a Reference LOP → paste the exported .usd file path → asset loads from disk.
Variants — Material Variants
To create material variants:

Duplicate the Component Material nodes (e.g., "red" and "blue")
Each gets a different Karma Material Builder with different settings
Component Builder automatically creates material variant set
To preview: use Explore Variants node → switch between variants
To set permanently: select asset → right-click → choose variant → creates Set Variant node

Variants — Geometry Variants
To create geometry variants:

Duplicate Component Geometry
Modify each (e.g., "Tommy Big Hands" vs "Tommy Big Head")
Use Component Geometry Variants node to merge geometry variants
Each geometry variant can have its own material variants
Explore with Explore Variants node → switch between geometry and material variant sets independently


VIDEO 3: Create an Asset Library with Megascans (11:10)
Importing External Assets (Megascans/Fab)
Download format: USDC (high quality) from Fab/Megascans
Node Network — Megascans Import Pipeline
Component Builder:
  │
  Component Geometry (SOPs inside):
  │  ├── USD Import (unpack to polygons = ON) → load .usdc file
  │  ├── Transform (Uniform Scale: 0.01 — Unreal to Houdini units)
  │  ├── Match Size (Justify Y: Minimum — ground the asset)
  │  ├── [Optional: Transform for rotation correction]
  │  ├── Connect to "default" output
  │  ├── PolyReduce (5%) → connect to "proxy" AND "sim proxy"
  │  └── Output
  │
  Reference LOP (for materials):
  │  ├── Same .usdc file path (paste relative reference from import)
  │  ├── Primitive target: /materials/* (wildcard)
  │  └── Save location: asset/mtl/ (must match component geo hierarchy)
  │
  Component Material
  │
  Component Output
  │  ├── Name: book_01, book_02, etc.
  │  ├── Generate Thumbnail → Save to Disk
  │  └── Add to Asset Gallery
Key Material Import Trick
Megascans .usdc files contain both geometry and materials in layers. To import materials separately:

Use a Reference LOP pointing to the same .usdc file
Set primitive target to /materials/* (wildcard catches all material names)
Set save location to asset/mtl/ so Component Geometry can find them
Use Paste Relative Reference on file paths so you only change one path per asset

Batch Asset Gallery Population with TOPs
Instead of clicking "Add to Asset Gallery" on each asset manually:

Create a TOP Network
Inside: use USD Assets to Gallery node
Press Shift+V → automatically processes all assets in the folder into the gallery

Layout & Physics

Layout LOP: Drag assets from gallery into viewport

Options: place, line, paint, stack, scale
Change from "Point Instancer" to "Instanceable Reference" (required for physics)


Edit LOP: Select assets → Add Physics → Use Physics

Real-time physics interactions (collisions, gravity)
Select individual or all assets, transform with T, rotate with R, scale with E
Grid acts as static collision surface



Quick Render Setup
Layout → Edit (physics) → Karma Physical Sky → Karma Setup → Camera
Camera shortcut: click the camera shift tool icon to create a camera at current viewport angle.
SYNAPSE TRAINING SUMMARY — Key Patterns to Internalize
Pattern 1 — The Canonical LOP Chain:
Primitive → SOP Import/Create → Material Library → Lighting → Karma Render Settings → USD Render ROP
Pattern 2 — Component Builder is the standard for USD assets:
Component Geometry (SOPs) → Component Material → Component Output → Reference (to load back)
Pattern 3 — Purpose always matters:
Every asset should have render + proxy purpose. Toggle with the glasses icon.
Pattern 4 — Hierarchy discipline:
Always set primitive paths: /shot/geo/$OS, /shot/LGT/$OS, /shot/MTL/$OS, /shot/cam/$OS
Pattern 5 — Variants are non-destructive:
Material and geometry variants live inside a single asset. Explore Variants previews; Set Variant commits.
Pattern 6 — External assets (Megascans):
USDC → unpack to polygons → scale 0.01 → Match Size → separate material via Reference LOP with wildcard /materials/*
Pattern 7 — Asset Gallery + TOPs for scale:
Use TOPs' "USD Assets to Gallery" node for batch gallery population instead of manual clicking.
Pattern 8 — Layout + Physics:
Layout LOP (instanceable reference mode) → Edit LOP with physics for real-time collision-based arrangement.