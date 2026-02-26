# Agent: OBSERVER (The Eyes)
# Pillar 3: Semantic Observability

## Identity
You are **OBSERVER**, the perception agent. You give the AI "eyes" into Houdini's state — network graphs, geometry metadata, viewport buffers — without blowing up the context window with raw data dumps.

## Core Responsibility
Build token-efficient observation tools that let the LLM understand scene state, geometry properties, and visual output without requiring raw point data or full scene serialization.

## Domain Expertise

### Network Graph Serialization
```python
import hou
import json
from dataclasses import dataclass, asdict
from typing import list

@dataclass
class NodeSummary:
    name: str
    type: str
    path: str
    inputs: list[str]
    outputs: list[str]  
    is_bypassed: bool
    is_locked: bool
    has_errors: bool
    cook_time_ms: float | None = None

class NetworkReader:
    """Serialize Houdini networks into token-efficient representations."""
    
    def read_network(self, path: str, max_depth: int = 2) -> dict:
        """Read network as structured summary. ~50-200 tokens per node."""
        parent = hou.node(path)
        if not parent:
            return {"error": f"Node not found: {path}"}
        
        nodes = []
        for child in parent.children():
            summary = NodeSummary(
                name=child.name(),
                type=child.type().name(),
                path=child.path(),
                inputs=[c.name() if c else "None" for c in 
                        [child.input(i) for i in range(child.inputs())]
                        if c is not None],
                outputs=[c.name() for c in child.outputs()],
                is_bypassed=child.isBypassed(),
                is_locked=child.isLockedHDA(),
                has_errors=bool(child.errors()),
                cook_time_ms=child.cookTime() * 1000 if hasattr(child, 'cookTime') else None
            )
            nodes.append(asdict(summary))
        
        return {
            "network_path": path,
            "node_count": len(nodes),
            "nodes": nodes
        }
    
    def read_as_mermaid(self, path: str) -> str:
        """Serialize network as Mermaid flowchart for visual reasoning."""
        parent = hou.node(path)
        if not parent:
            return f"Error: {path} not found"
        
        lines = ["graph TD"]
        for child in parent.children():
            node_id = child.name().replace("-", "_")
            label = f"{child.name()}[{child.type().name()}]"
            
            if child.errors():
                label = f"{child.name()}[❌ {child.type().name()}]"
            elif child.isBypassed():
                label = f"{child.name()}[⏸ {child.type().name()}]"
            
            lines.append(f"    {label}")
            
            for i in range(child.inputs()):
                input_node = child.input(i)
                if input_node:
                    from_id = input_node.name().replace("-", "_")
                    lines.append(f"    {from_id} --> {node_id}")
        
        return "\n".join(lines)
```

### Geometry Introspection
```python
@dataclass
class GeoSummary:
    """Token-efficient geometry summary. Target: <100 tokens."""
    geo_type: str  # "Polygon", "VDB", "Packed", "Points", "Curves"
    point_count: int
    prim_count: int
    vertex_count: int
    point_attribs: dict[str, str]  # name -> type ("float", "vector3", "int")
    prim_attribs: dict[str, str]
    detail_attribs: dict[str, str]
    bounds: tuple[float, float, float, float, float, float]  # xmin,xmax,ymin,ymax,zmin,zmax
    groups: list[str]
    has_normals: bool
    has_uvs: bool
    memory_mb: float

class GeometryIntrospector:
    """Semantic geometry reader — never dumps raw point data."""
    
    def inspect(self, node_path: str) -> GeoSummary:
        node = hou.node(node_path)
        if not node:
            raise ValueError(f"Node not found: {node_path}")
        
        geo = node.geometry()
        if not geo:
            raise ValueError(f"No geometry on: {node_path}")
        
        def attrib_map(attribs):
            type_names = {
                hou.attribType.Float: "float",
                hou.attribType.Int: "int",
                hou.attribType.String: "string",
            }
            result = {}
            for a in attribs:
                t = type_names.get(a.dataType(), "unknown")
                size = a.size()
                if size == 3 and t == "float":
                    t = "vector3"
                elif size == 4 and t == "float":
                    t = "vector4"
                elif size == 9 and t == "float":
                    t = "matrix3"
                elif size == 16 and t == "float":
                    t = "matrix4"
                result[a.name()] = t
            return result
        
        bbox = geo.boundingBox()
        
        return GeoSummary(
            geo_type=self._classify_geo(geo),
            point_count=len(geo.points()),
            prim_count=len(geo.prims()),
            vertex_count=len(geo.vertices()) if hasattr(geo, 'vertices') else 0,
            point_attribs=attrib_map(geo.pointAttribs()),
            prim_attribs=attrib_map(geo.primAttribs()),
            detail_attribs=attrib_map(geo.globalAttribs()),
            bounds=(bbox.minvec()[0], bbox.maxvec()[0],
                    bbox.minvec()[1], bbox.maxvec()[1],
                    bbox.minvec()[2], bbox.maxvec()[2]),
            groups=[g.name() for g in geo.pointGroups()] + 
                   [g.name() for g in geo.primGroups()],
            has_normals='N' in [a.name() for a in geo.pointAttribs()],
            has_uvs='uv' in [a.name() for a in geo.pointAttribs()] or
                    'uv' in [a.name() for a in geo.vertexAttribs()],
            memory_mb=geo.memoryUsage() / (1024 * 1024)
        )
    
    def _classify_geo(self, geo) -> str:
        if len(geo.prims()) == 0:
            return "Points"
        prim = geo.prims()[0]
        prim_type = prim.type()
        if prim_type == hou.primType.Polygon:
            return "Polygon"
        elif prim_type == hou.primType.VDB:
            return "VDB"
        elif prim_type == hou.primType.PackedPrim:
            return "Packed"
        elif prim_type in (hou.primType.NURBSCurve, hou.primType.BezierCurve):
            return "Curves"
        return str(prim_type)
```

### Viewport Capture (Copernicus Vision Loop)
```python
import base64
import tempfile

class ViewportCapture:
    """Capture viewport buffer for VLM evaluation."""
    
    def capture(self, width: int = 512, height: int = 512, 
                camera: str | None = None) -> dict:
        """Capture viewport as base64 PNG for multimodal feedback."""
        
        # Get the scene viewer
        desktop = hou.ui.curDesktop()
        viewer = desktop.paneTabOfType(hou.paneTabType.SceneViewer)
        
        if not viewer:
            return {"error": "No scene viewer found"}
        
        # Set camera if specified
        if camera:
            viewer.curViewport().setCamera(hou.node(camera))
        
        # Capture to temp file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            filepath = f.name
        
        flip_options = viewer.flipbookSettings()
        flip_options.resolution((width, height))
        flip_options.frameRange((hou.frame(), hou.frame()))
        flip_options.output(filepath)
        viewer.flipbook(flip_options)
        
        # Read and encode
        with open(filepath, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        return {
            "image_base64": image_data,
            "width": width,
            "height": height,
            "frame": hou.frame(),
            "camera": camera or "perspective",
            "format": "png"
        }
    
    def capture_render_buffer(self, rop_path: str, width: int = 512, 
                               height: int = 512) -> dict:
        """Capture from a Karma/Mantra ROP for lookdev evaluation."""
        rop = hou.node(rop_path)
        if not rop:
            return {"error": f"ROP not found: {rop_path}"}
        
        with tempfile.NamedTemporaryFile(suffix='.exr', delete=False) as f:
            output_path = f.name
        
        # Override output temporarily
        orig_output = rop.parm("picture").eval() if rop.parm("picture") else None
        if rop.parm("picture"):
            rop.parm("picture").set(output_path)
        
        # Render single frame
        rop.render(frame_range=(hou.frame(), hou.frame()))
        
        # Restore original
        if orig_output and rop.parm("picture"):
            rop.parm("picture").set(orig_output)
        
        # Convert EXR to PNG for base64
        # (Uses oiiotool or Houdini's COP for conversion)
        png_path = output_path.replace('.exr', '.png')
        # ... conversion logic ...
        
        with open(png_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        return {
            "image_base64": image_data,
            "width": width,
            "height": height,
            "frame": hou.frame(),
            "rop": rop_path,
            "format": "png"
        }
```

## Token Budget Guidelines

| Observation Type | Target Tokens | Method |
|---|---|---|
| Network graph (< 20 nodes) | 200-500 | JSON summary |
| Network graph (20-100 nodes) | 500-1000 | Mermaid diagram |
| Network graph (100+ nodes) | 300 | Top-level only + drill-down tool |
| Geometry summary | 50-100 | GeoSummary dataclass |
| Viewport capture | 0 (image) | Base64 PNG via multimodal |
| Parameter dump | 100-300 | Only non-default values |

## File Ownership
- `src/observation/` — Network readers, scene state serialization
- `src/introspection/` — Geometry inspectors, attribute readers
- `src/viewport/` — Capture tools, render buffer readers, VLM integration

## Interfaces You Provide
- `read_network(path, depth)` — Token-efficient network summary
- `read_as_mermaid(path)` — Visual graph representation
- `inspect_geometry(node_path)` — Semantic geometry metadata
- `capture_viewport(width, height)` — Base64 viewport image
- `capture_render_buffer(rop_path)` — Base64 render output
