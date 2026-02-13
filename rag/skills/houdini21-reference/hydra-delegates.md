# Hydra Render Delegates Reference

## Architecture Overview

```
USD Stage
  +-- UsdImagingDelegate (translates USD prims -> Hydra prims)
       +-- HdRenderIndex (scene database)
            +-- HdRenderDelegate (your renderer)
                 +-- HdRenderPass (executes rendering)
                 +-- HdRenderBuffer (stores output: color, depth, normal)
                 +-- HdRprim / HdSprim / HdBprim (scene primitives)
```

## Core Classes

### HdRendererPlugin (Entry Point)

The plugin registry discovers your renderer via `plugInfo.json`. This class creates delegates.

```cpp
#include <pxr/imaging/hd/rendererPlugin.h>

class MyRendererPlugin final : public HdRendererPlugin {
public:
    HdRenderDelegate* CreateRenderDelegate() override;
    HdRenderDelegate* CreateRenderDelegate(
        HdRenderSettingsMap const& settingsMap) override;
    void DeleteRenderDelegate(HdRenderDelegate* delegate) override;
    bool IsSupported(bool gpuEnabled = true) const override;
};
```

**plugInfo.json registration:**
```json
{
    "Plugins": [{
        "Info": {
            "Types": {
                "MyRendererPlugin": {
                    "bases": ["HdRendererPlugin"],
                    "displayName": "My Renderer",
                    "priority": 50
                }
            }
        },
        "LibraryPath": "lib/hdMyRenderer.dll",
        "Name": "hdMyRenderer",
        "ResourcePath": "resources",
        "Root": ".",
        "Type": "library"
    }]
}
```

| Field | Purpose |
|-------|---------|
| `bases` | Must be `["HdRendererPlugin"]` |
| `displayName` | Shown in Houdini renderer dropdown |
| `priority` | Higher = preferred when multiple delegates available |
| `LibraryPath` | Relative path to compiled DLL/so |
| `Type` | `"library"` for compiled delegates |

### HdRenderDelegate (Renderer Core)

```cpp
#include <pxr/imaging/hd/renderDelegate.h>

class MyRenderDelegate final : public HdRenderDelegate {
public:
    // Required overrides
    HdRenderParam* GetRenderParam() const override;
    const TfTokenVector& GetSupportedRprimTypes() const override;
    const TfTokenVector& GetSupportedSprimTypes() const override;
    const TfTokenVector& GetSupportedBprimTypes() const override;

    HdResourceRegistrySharedPtr GetResourceRegistry() const override;

    // Prim factories
    HdRprim* CreateRprim(TfToken const& typeId,
                         SdfPath const& rprimId) override;
    HdSprim* CreateSprim(TfToken const& typeId,
                         SdfPath const& sprimId) override;
    HdBprim* CreateBprim(TfToken const& typeId,
                         SdfPath const& bprimId) override;

    // Render pass
    HdRenderPassSharedPtr CreateRenderPass(
        HdRenderIndex* index,
        HdRprimCollection const& collection) override;

    // Settings
    HdRenderSettingDescriptorList GetRenderSettingDescriptors() const override;
};
```

**Prim Types:**

| Category | Class | Examples |
|----------|-------|---------|
| Rprim (renderable) | `HdRprim` | Mesh, BasisCurves, Points, Volume |
| Sprim (state) | `HdSprim` | Camera, Light, Material, RenderSettings |
| Bprim (buffer) | `HdBprim` | RenderBuffer, RenderOutput |

**Supported prim tokens (typical):**
```cpp
const TfTokenVector& MyRenderDelegate::GetSupportedRprimTypes() const {
    static TfTokenVector types = {
        HdPrimTypeTokens->mesh,
        HdPrimTypeTokens->basisCurves,
        HdPrimTypeTokens->points,
    };
    return types;
}
```

### HdRenderPass (Per-Frame Execution)

```cpp
#include <pxr/imaging/hd/renderPass.h>

class MyRenderPass final : public HdRenderPass {
protected:
    void _Execute(HdRenderPassStateSharedPtr const& renderPassState,
                  TfTokenVector const& renderTags) override;
};
```

The `_Execute` method is called each frame. It reads scene data from the render index, invokes your renderer, and writes results to render buffers.

**Typical _Execute flow:**
1. Get camera from `renderPassState`
2. Query dirty prims from render index
3. Sync scene changes (transforms, visibility, materials)
4. Render frame (your rendering logic)
5. Write pixels to `HdRenderBuffer`

### HdRenderBuffer (Output Storage)

```cpp
#include <pxr/imaging/hd/renderBuffer.h>

class MyRenderBuffer final : public HdRenderBuffer {
public:
    bool Allocate(GfVec3i const& dimensions,
                  HdFormat format,
                  bool multiSampled) override;
    void* Map() override;          // Get raw pixel pointer
    void Unmap() override;
    bool IsMapped() const override;
    void Resolve() override;       // Finalize (e.g., denoise, tonemap)

    unsigned int GetWidth() const override;
    unsigned int GetHeight() const override;
    unsigned int GetDepth() const override;
    HdFormat GetFormat() const override;
    bool IsMultiSampled() const override;
};
```

**Common formats:**
| HdFormat | Use |
|----------|-----|
| `HdFormatFloat32Vec4` | RGBA color (HDR) |
| `HdFormatFloat32` | Depth |
| `HdFormatFloat32Vec3` | Normal, position AOVs |
| `HdFormatUNorm8Vec4` | LDR color (8-bit) |

### HdRenderSettingDescriptorList (Custom Settings)

Exposes settings in Houdini's Render Settings LOP:

```cpp
HdRenderSettingDescriptorList
MyRenderDelegate::GetRenderSettingDescriptors() const {
    return {
        {"Steps", TfToken("carwash:steps"), VtValue(20)},
        {"CFG Scale", TfToken("carwash:cfg"), VtValue(7.0f)},
        {"Prompt", TfToken("carwash:prompt"),
         VtValue(std::string("photorealistic"))},
    };
}
```

**For full UI integration**, use a USD API schema (`CarWashRenderSettingsAPI`) deployed as a resource plugin. See `usd-schema-registration.md`.

## Houdini-Specific Patterns

### Karma Reference (Houdini 21)

Karma registers TWO plugins:
```
houdini/dso/usd_plugins/
+-- hdKarma/
|   +-- resources/plugInfo.json     <- HdRendererPlugin (delegate)
+-- usdKarma/
    +-- resources/plugInfo.json     <- API schema (render settings)
```

**hdKarma plugInfo.json** (delegate, Type=library):
```json
{
    "Plugins": [{
        "Info": {
            "Types": {
                "BRAY_HdKarma": {
                    "bases": ["HdRendererPlugin"],
                    "displayName": "Karma CPU"
                },
                "BRAY_HdKarmaXPU": {
                    "bases": ["HdRendererPlugin"],
                    "displayName": "Karma XPU"
                }
            }
        },
        "LibraryPath": "../../BRAY_HdKarma.dll",
        "Type": "library"
    }]
}
```

**usdKarma plugInfo.json** (schema, Type=resource):
```json
{
    "Plugins": [{
        "Info": {
            "Types": {
                "KarmaRenderSettingsAPI": {
                    "alias": {"UsdSchemaBase": "KarmaRenderSettingsAPI"},
                    "autoGenerated": true,
                    "bases": ["UsdAPISchemaBase"],
                    "schemaKind": "singleApplyAPI"
                }
            }
        },
        "LibraryPath": "",
        "Name": "usdKarma",
        "Type": "resource"
    }]
}
```

### hdCarWash Pattern (AI Renderer)

Same dual-plugin pattern:
```
dso/usd/
+-- hdCarWash/resources/plugInfo.json   <- Delegate DLL
+-- usdCarWash/resources/plugInfo.json  <- Schema + SchemasForRenderers
```

**SchemasForRenderers** (maps delegate -> schema for Render Settings tab):
```json
"SchemasForRenderers": {
    "HdCarWash": ["CarWashRenderSettingsAPI"]
}
```

Note: Karma in Houdini 21 does NOT use `SchemasForRenderers` (Houdini handles it internally). Third-party delegates may need it for auto-discovery.

## Render Delegate Lifecycle

```
1. Houdini starts -> PXR_PLUGINPATH_NAME scanned
2. PlugRegistry discovers plugInfo.json with HdRendererPlugin base
3. User selects renderer in Render Settings LOP dropdown
4. HdRendererPlugin::CreateRenderDelegate() called
5. Delegate creates RenderPass, RenderBuffers
6. Per frame: _Execute() called on RenderPass
7. RenderBuffer::Map() exposes pixels to Houdini viewport
8. On renderer switch/close: DeleteRenderDelegate()
```

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Renderer not in dropdown | plugInfo.json not discovered | Check PXR_PLUGINPATH_NAME |
| Settings tab missing | Schema not registered | Deploy usdSchema resource plugin |
| Black viewport | RenderBuffer format mismatch | Match HdFormat to AOV expectations |
| Crash on delegate create | DLL dependencies missing | Check DLL deps with `dumpbin /dependents` |
| Delegate loads but no render | `_Execute` not called | Verify RenderPass creation, check prim collection |

---
*Source: Pixar USD Imaging (Hd) framework. Verified against Houdini 21.0 hdKarma + hdCarWash patterns.*
*Cross-reference: usd-schema-registration.md for schema deployment, pxr-pluginpath.md for discovery.*
