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

```cpp
// Prim categories:
// Rprim (renderable): Mesh, BasisCurves, Points, Volume
// Sprim (state):      Camera, Light, Material, RenderSettings
// Bprim (buffer):     RenderBuffer, RenderOutput
```
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

```cpp
// Typical _Execute flow:
// 1. Get camera from renderPassState
// 2. Query dirty prims from render index
// 3. Sync scene changes (transforms, visibility, materials)
// 4. Render frame (your rendering logic)
// 5. Write pixels to HdRenderBuffer
```

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

```cpp
// Common HdFormat values:
// HdFormatFloat32Vec4  -- RGBA color (HDR)
// HdFormatFloat32      -- Depth
// HdFormatFloat32Vec3  -- Normal, position AOVs
// HdFormatUNorm8Vec4   -- LDR color (8-bit)
```

### HdRenderSettingDescriptorList (Custom Settings)

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

```cpp
// Karma in Houdini 21 does NOT use SchemasForRenderers
// (Houdini handles the mapping internally for its own renderers)
// Third-party delegates should include SchemasForRenderers for auto-discovery
```

## Render Delegate Lifecycle

```cpp
// 1. Houdini starts -> PXR_PLUGINPATH_NAME scanned
// 2. PlugRegistry discovers plugInfo.json with HdRendererPlugin base
// 3. User selects renderer in Render Settings LOP dropdown
// 4. HdRendererPlugin::CreateRenderDelegate() called
// 5. Delegate creates RenderPass, RenderBuffers
// 6. Per frame: _Execute() called on RenderPass
// 7. RenderBuffer::Map() exposes pixels to Houdini viewport
// 8. On renderer switch/close: DeleteRenderDelegate()
```

## Common Mistakes
```cpp
// Renderer not in dropdown -- plugInfo.json not discovered
// Fix: check PXR_PLUGINPATH_NAME includes the plugin directory

// Settings tab missing -- schema registered but no SchemasForRenderers
// Fix: add "SchemasForRenderers": {"HdMyRenderer": ["MyRenderSettingsAPI"]} in plugInfo.json

// Black viewport -- RenderBuffer format mismatch
// Fix: match HdFormat to AOV expectations (e.g., HdFormatFloat32Vec4 for color)

// Crash on delegate create -- DLL dependencies missing
// Fix: check DLL deps with: dumpbin /dependents hdMyRenderer.dll

// Delegate loads but no render -- _Execute not called
// Fix: verify RenderPass creation and prim collection setup
```
