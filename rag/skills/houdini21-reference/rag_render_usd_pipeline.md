# USD Render Pipeline Hierarchy

## Triggers
render pipeline, RenderSettings, RenderProduct, RenderVar, render prim, render hierarchy,
USD render, render configuration, render output prim

## Context
USD defines a three-level render hierarchy: RenderSettings (global config) → RenderProduct (output image) → RenderVar (AOV channel). Karma LOP creates these automatically under /Render.

## Code

```python
# Reading the USD render pipeline hierarchy from a LOP stage
import hou

lop_node = hou.node("/stage/karmarendersettings1")
stage = lop_node.stage()

from pxr import UsdRender, Usd

# --- Find all RenderSettings prims ---
for prim in stage.Traverse():
    if prim.IsA(UsdRender.Settings):
        settings = UsdRender.Settings(prim)
        print(f"RenderSettings: {prim.GetPath()}")

        # Resolution
        res = settings.GetResolutionAttr().Get()
        print(f"  Resolution: {res[0]}x{res[1]}")

        # Pixel aspect ratio
        par = settings.GetPixelAspectRatioAttr().Get()
        print(f"  Pixel Aspect Ratio: {par}")

        # Camera binding
        camera_rel = prim.GetRelationship("camera")
        if camera_rel:
            targets = camera_rel.GetTargets()
            print(f"  Camera: {targets[0] if targets else 'NONE'}")

        # --- Find RenderProducts under this settings prim ---
        products_rel = settings.GetProductsRel()
        for product_path in products_rel.GetTargets():
            product_prim = stage.GetPrimAtPath(product_path)
            if product_prim.IsA(UsdRender.Product):
                product = UsdRender.Product(product_prim)
                print(f"  RenderProduct: {product_path}")

                # Output file path
                product_name = product.GetProductNameAttr().Get()
                print(f"    Output: {product_name}")

                # Product type (raster, deepRaster)
                product_type = product.GetProductTypeAttr().Get()
                print(f"    Type: {product_type}")

                # --- Find RenderVars (AOVs) under this product ---
                orderedVars = product.GetOrderedVarsRel()
                for var_path in orderedVars.GetTargets():
                    var_prim = stage.GetPrimAtPath(var_path)
                    if var_prim.IsA(UsdRender.Var):
                        var = UsdRender.Var(var_prim)
                        source_name = var.GetSourceNameAttr().Get()
                        data_type = var.GetDataTypeAttr().Get()
                        print(f"    RenderVar: {var_path}")
                        print(f"      Source: {source_name}, Type: {data_type}")
```

```python
# Creating render pipeline prims manually via USD API
from pxr import UsdRender, Sdf, Gf

stage = lop_node.editableStage()

# Create RenderSettings
settings_prim = UsdRender.Settings.Define(stage, "/Render/rendersettings1")
settings_prim.GetResolutionAttr().Set(Gf.Vec2i(1920, 1080))
settings_prim.GetPixelAspectRatioAttr().Set(1.0)

# Create RenderProduct (output image)
product_prim = UsdRender.Product.Define(stage, "/Render/rendersettings1/beauty")
product_prim.GetProductNameAttr().Set("$HIP/render/beauty.$F4.exr")
product_prim.GetProductTypeAttr().Set("raster")

# Link product to settings
settings_prim.GetProductsRel().AddTarget("/Render/rendersettings1/beauty")

# Create RenderVar (AOV channel)
color_var = UsdRender.Var.Define(stage, "/Render/rendersettings1/beauty/color")
color_var.GetSourceNameAttr().Set("color")
color_var.GetDataTypeAttr().Set("color3f")

# Link var to product
product_prim.GetOrderedVarsRel().AddTarget("/Render/rendersettings1/beauty/color")
```

## Expected Scene Graph
```
/Render/
  └─ rendersettings1  (UsdRenderSettings)
       ├─ resolution: (1920, 1080)
       ├─ camera → /cameras/render_cam
       └─ beauty  (UsdRenderProduct)
            ├─ productName: "$HIP/render/beauty.$F4.exr"
            ├─ productType: "raster"
            └─ color  (UsdRenderVar)
                 ├─ sourceName: "color"
                 └─ dataType: "color3f"
```

## Common Mistakes
- Querying RenderProduct without traversing the products relationship on RenderSettings
- Forgetting that RenderVar prims are linked via `orderedVars` relationship, not parenting
- Assuming productName uses husk-style `<F4>` tokens — in LOP context it uses `$F4`
- Not checking `productType` — deep renders use "deepRaster" not "raster"
