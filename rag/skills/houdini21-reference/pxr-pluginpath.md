# PXR Plugin Path & Discovery Reference

## Environment Variables

| Variable | Purpose | Separator |
|----------|---------|-----------|
| `PXR_PLUGINPATH_NAME` | Directories containing USD plugins | `;` (Windows), `:` (Linux/Mac) |
| `PXR_AR_DEFAULT_SEARCH_PATH` | Asset resolver search paths | `;` / `:` |
| `HOUDINI_PATH` | Houdini resource paths (includes `dso/` scanning) | `;` / `:` |

**Primary:** `PXR_PLUGINPATH_NAME` is the main mechanism for USD plugin discovery in Houdini.

## Discovery Mechanism

### How PlugRegistry Finds Plugins

```
1. Scan each directory in PXR_PLUGINPATH_NAME
2. Look for plugInfo.json in that directory
3. If plugInfo.json has "Includes", follow those patterns
4. Parse each discovered plugInfo.json
5. Register Types based on "bases" declarations
6. Load libraries on demand (lazy loading)
```

### The Includes Directive

A `plugInfo.json` can reference subdirectories:

```json
{
    "Includes": ["*/resources/"]
}
```

This tells PlugRegistry: "scan every immediate subdirectory's `resources/` folder for more `plugInfo.json` files."

**Pattern matching:**
| Pattern | Matches |
|---------|---------|
| `*/resources/` | `hdFoo/resources/`, `usdBar/resources/` |
| `*/` | Every immediate subdirectory |
| `subdir/` | Specific subdirectory only |

**Recursive:** Includes are NOT recursive by default. `*/resources/` scans one level of subdirectories, not deeper.

### Discovery Example (hdCarWash)

```
PXR_PLUGINPATH_NAME = C:/Users/User/houdini21.0/dso/usd

dso/usd/
+-- plugInfo.json                       <- {"Includes": ["*/resources/"]}
+-- hdCarWash/
|   +-- lib/hdCarWash.dll
|   +-- resources/
|       +-- plugInfo.json               <- Delegate (Type: library)
+-- usdCarWash/
    +-- resources/
        +-- generatedSchema.usda        <- Schema definition
        +-- plugInfo.json               <- Schema (Type: resource)
```

**Result:** PlugRegistry discovers both `hdCarWash` (delegate DLL) and `usdCarWash` (schema) from a single `PXR_PLUGINPATH_NAME` entry.

### Houdini's Built-in Plugin Paths

Houdini automatically adds these to the plugin search (no manual config needed):

```
$HFS/houdini/dso/usd_plugins/          <- Karma, Storm, etc.
$HFS/houdini/dso/usd_plugins/*/resources/
$HOUDINI_USER_PREF_DIR/dso/usd/        <- User plugins (if exists)
```

Where:
- `$HFS` = Houdini install dir (e.g., `C:\Program Files\Side Effects Software\Houdini 21.0.512`)
- `$HOUDINI_USER_PREF_DIR` = User prefs (e.g., `C:\Users\User\houdini21.0`)

## Houdini Package System

### Package Files

JSON files in `packages/` directories that set environment variables before Houdini starts.

**Search locations (in order):**
```
$HOUDINI_USER_PREF_DIR/packages/        <- C:\Users\User\houdini21.0\packages\
$HOUDINI_USER_PREF_DIR/../packages/     <- C:\Users\User\Documents\houdini21.0\packages\
$HFS/packages/                          <- System-wide (rare)
```

### Package Format

```json
{
    "env": [
        {
            "PXR_PLUGINPATH_NAME": {
                "value": "C:/path/to/plugins",
                "method": "append"
            }
        }
    ]
}
```

| Field | Values | Purpose |
|-------|--------|---------|
| `method` | `"append"` | Add to end of existing path |
| `method` | `"prepend"` | Add to beginning (higher priority) |
| `method` | `"set"` | Replace entirely (dangerous) |

### Multiple Variables in One Package

```json
{
    "env": [
        {
            "HOUDINI_PATH": {
                "value": "C:/my/plugin",
                "method": "prepend"
            }
        },
        {
            "PXR_PLUGINPATH_NAME": {
                "value": "C:/my/plugin",
                "method": "prepend"
            }
        }
    ],
    "path": "C:/my/plugin"
}
```

The `"path"` key at root level adds to `HOUDINI_PATH` directly (shorthand).

## Dual-Location Deployment Pattern

### Why Two Locations

| Location | Purpose | When Loaded |
|----------|---------|-------------|
| **Source (project dir)** | Development, git tracking | Via `Documents/houdini21.0/packages/` |
| **Runtime (dso/usd/)** | Production, Houdini auto-discovery | Via `houdini21.0/packages/` or auto |

### Example: hdCarWash Dual Deployment

**Location 1: Source (git-tracked)**
```
C:\Users\User\Downloads\HDCARWAASH\HdCarWash\plugin\
+-- plugInfo.json                   <- Includes + delegate
+-- lib\hdCarWash.dll
+-- usdCarWash\resources\
    +-- generatedSchema.usda
    +-- plugInfo.json
```

Package: `Documents\houdini21.0\packages\hdCarWash.json`
```json
{
    "env": [
        {"HOUDINI_PATH": {"value": "C:/Users/.../plugin", "method": "prepend"}},
        {"PXR_PLUGINPATH_NAME": {"value": "C:/Users/.../plugin", "method": "prepend"}}
    ]
}
```

**Location 2: Runtime (user prefs)**
```
C:\Users\User\houdini21.0\dso\usd\
+-- plugInfo.json                   <- Includes
+-- hdCarWash\resources\...
+-- usdCarWash\resources\...
```

Package: `houdini21.0\packages\hdCarWash.json`
```json
{
    "env": [{
        "PXR_PLUGINPATH_NAME": {
            "value": "C:/Users/User/houdini21.0/dso/usd",
            "method": "append"
        }
    }]
}
```

**Important:** If both packages exist, both paths are added. Houdini uses the first plugin it finds with a given name. Use `prepend` for the location you want to take priority.

## Verifying Discovery (hython)

```python
# Check what plugins are registered
from pxr import Plug
reg = Plug.Registry()
all_plugins = reg.GetAllPlugins()
print(f"Total plugins: {len(all_plugins)}")

# Find specific plugin
for p in all_plugins:
    if "CarWash" in p.name or "Karma" in p.name:
        print(f"  {p.name}: {p.path}")

# Check if schema is registered
from pxr import Usd
defn = Usd.SchemaRegistry().FindAppliedAPIPrimDefinition("MyRenderSettingsAPI")
if defn:
    print("Schema registered!")
    for prop in defn.GetPropertyNames():
        print(f"  {prop}")
else:
    print("Schema NOT found")

# Check environment
import os
print("PXR_PLUGINPATH_NAME:", os.environ.get("PXR_PLUGINPATH_NAME", "NOT SET"))
```

### hython Quick Verification Script

```bash
# Windows (from Houdini bin/)
hython -c "from pxr import Plug; [print(p.name) for p in Plug.Registry().GetAllPlugins() if 'CarWash' in p.name]"
```

## plugInfo.json Root and Path Resolution

### Root Field

The `Root` field in `plugInfo.json` sets the base directory for resolving `LibraryPath` and `ResourcePath`:

```json
{
    "Root": ".",
    "LibraryPath": "lib/hdCarWash.dll",
    "ResourcePath": "resources"
}
```

| Root | Resolves Relative To |
|------|---------------------|
| `"."` | Directory containing this `plugInfo.json` |
| `".."` | Parent of directory containing `plugInfo.json` |
| Absolute path | Fixed location (avoid -- not portable) |

### Common Layouts and Their Root Values

**Flat layout** (plugInfo.json next to lib/):
```
plugin/
+-- plugInfo.json           <- Root: "."
+-- lib/hdFoo.dll           <- LibraryPath: "lib/hdFoo.dll"
+-- resources/
    +-- generatedSchema.usda
```

**Nested layout** (plugInfo.json inside resources/):
```
usdFoo/
+-- resources/
|   +-- plugInfo.json       <- Root: ".."
|   +-- generatedSchema.usda
+-- lib/
    +-- usdFoo.dll          <- LibraryPath: "lib/usdFoo.dll" (relative to Root="..")
```

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Plugin not discovered | PXR_PLUGINPATH_NAME missing or wrong | Check `hython -c "import os; print(os.environ.get('PXR_PLUGINPATH_NAME'))"` |
| Schema found but delegate missing | Path points to schema dir only | Point to parent with Includes, not individual resource dir |
| Package not loading | Wrong packages/ directory | Use `houdini21.0/packages/` (not `houdini21.0.512/packages/`) |
| DLL not found despite correct path | Root field wrong | Check Root + LibraryPath concatenation resolves correctly |
| Duplicate plugin warnings | Same plugin on path twice | Remove one of the dual deployment locations |
| `method: set` overrides everything | Replaces entire path variable | Use `append` or `prepend` instead |

## Path Priority (Highest First)

```
1. PXR_PLUGINPATH_NAME (prepend entries)     <- User overrides
2. PXR_PLUGINPATH_NAME (append entries)      <- Additional plugins
3. $HFS/houdini/dso/usd_plugins/            <- Houdini built-in (Karma, Storm)
4. $HOUDINI_USER_PREF_DIR/dso/usd/          <- User prefs auto-scan
```

Within each path, the first-discovered plugin with a given name wins.

---
*Source: Pixar USD PlugRegistry + Houdini 21.0 package system. Verified against hdCarWash dual-location deployment.*
*Cross-reference: hydra-delegates.md for what gets discovered, usd-schema-registration.md for plugInfo.json contents.*
