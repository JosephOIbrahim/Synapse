# PXR Plugin Path & Discovery Reference

## Environment Variables

```python
# USD plugin discovery environment variables
ENV_VARS = {
    "PXR_PLUGINPATH_NAME":       "Directories containing USD plugins (primary mechanism)",
    "PXR_AR_DEFAULT_SEARCH_PATH":"Asset resolver search paths",
    "HOUDINI_PATH":              "Houdini resource paths (includes dso/ scanning)",
}
# Separator: ';' on Windows, ':' on Linux/Mac
```

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

```python
# Includes pattern matching:
# "*/resources/"  -- matches hdFoo/resources/, usdBar/resources/
# "*/"            -- every immediate subdirectory
# "subdir/"       -- specific subdirectory only
# NOT recursive by default: */resources/ scans one level only
```

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

```python
# method values:
# "append"  -- add to end of existing path
# "prepend" -- add to beginning (higher priority)
# "set"     -- replace entirely (dangerous!)
```

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

```python
# "path" key at root level adds to HOUDINI_PATH directly (shorthand)

# Dual-location deployment:
# Source (project dir): development, git tracking -- via Documents/houdini21.0/packages/
# Runtime (dso/usd/):  production, Houdini auto-discovery -- via houdini21.0/packages/ or auto
```

### Example: hdCarWash Dual Deployment
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

```json
// Root field sets base directory for resolving LibraryPath and ResourcePath:
{
    "Root": ".",
    "LibraryPath": "lib/hdCarWash.dll",
    "ResourcePath": "resources"
}
// Root resolution:
// "."          -- directory containing this plugInfo.json
// ".."         -- parent of directory containing plugInfo.json
// Absolute     -- fixed location (avoid -- not portable)
```

### Common Layouts and Their Root Values
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

## Diagnostic Scripts

```python
# Full plugin discovery diagnostic
import os
from pxr import Plug

def diagnose_plugin_discovery(search_name=None):
    """Diagnose USD plugin discovery issues."""
    # Check environment
    pxr_path = os.environ.get("PXR_PLUGINPATH_NAME", "NOT SET")
    print(f"PXR_PLUGINPATH_NAME: {pxr_path}")

    houdini_path = os.environ.get("HOUDINI_PATH", "NOT SET")
    print(f"HOUDINI_PATH: {houdini_path}")

    # Enumerate all discovered plugins
    reg = Plug.Registry()
    all_plugins = reg.GetAllPlugins()
    print(f"\nTotal discovered plugins: {len(all_plugins)}")

    if search_name:
        matches = [p for p in all_plugins if search_name.lower() in p.name.lower()]
        if matches:
            print(f"\nPlugins matching '{search_name}':")
            for p in matches:
                print(f"  Name: {p.name}")
                print(f"  Path: {p.path}")
                print(f"  Loaded: {p.isLoaded}")
        else:
            print(f"\nNo plugins matching '{search_name}'")
            # Check if path directories exist
            if pxr_path != "NOT SET":
                for d in pxr_path.split(os.pathsep):
                    exists = os.path.isdir(d)
                    has_pluginfo = os.path.isfile(os.path.join(d, "plugInfo.json"))
                    print(f"  {d}: exists={exists}, plugInfo={has_pluginfo}")

    return all_plugins


diagnose_plugin_discovery("CarWash")
```

```python
# Create a Houdini package file for a USD plugin
import json
import os

def create_houdini_package(plugin_name, plugin_path,
                           packages_dir=None, method="prepend"):
    """Create a package JSON file for USD plugin discovery.
    method: 'prepend' (high priority), 'append' (low priority), 'set' (replace)."""
    if packages_dir is None:
        packages_dir = os.path.expandvars(
            "$HOUDINI_USER_PREF_DIR/packages")

    package = {
        "env": [
            {
                "HOUDINI_PATH": {
                    "value": plugin_path.replace("\\", "/"),
                    "method": method,
                }
            },
            {
                "PXR_PLUGINPATH_NAME": {
                    "value": plugin_path.replace("\\", "/"),
                    "method": method,
                }
            },
        ],
        "path": plugin_path.replace("\\", "/"),
    }

    os.makedirs(packages_dir, exist_ok=True)
    out_path = os.path.join(packages_dir, f"{plugin_name}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(package, f, indent=4, sort_keys=True)
    print(f"Package written: {out_path}")
    return out_path


create_houdini_package("hdCarWash", "C:/Users/User/Downloads/HDCARWAASH/HdCarWash/plugin")
```

```python
# Verify schema registration after plugin discovery
from pxr import Usd, Plug

def verify_schema(schema_name):
    """Check if a USD applied API schema is registered and list its properties."""
    defn = Usd.SchemaRegistry().FindAppliedAPIPrimDefinition(schema_name)
    if defn:
        print(f"Schema '{schema_name}' registered")
        props = defn.GetPropertyNames()
        print(f"  Properties ({len(props)}):")
        for prop in sorted(props):
            print(f"    {prop}")
        return True
    else:
        print(f"Schema '{schema_name}' NOT found")
        # List similar schemas
        reg = Plug.Registry()
        for p in reg.GetAllPlugins():
            if schema_name.lower()[:4] in p.name.lower():
                print(f"  Similar plugin: {p.name} ({p.path})")
        return False


verify_schema("MyRenderSettingsAPI")
```

## Common Mistakes
- Plugin not discovered -- PXR_PLUGINPATH_NAME missing or wrong; verify with hython diagnostic
- Schema found but delegate missing -- path points to schema dir only; point to parent with Includes
- Package not loading -- wrong packages/ directory; use houdini21.0/packages/ not versioned dir
- DLL not found despite correct path -- Root field wrong; check Root + LibraryPath resolution
- Duplicate plugin warnings -- same plugin on path twice; remove one deployment location
- Using method "set" -- replaces entire path variable; use "append" or "prepend" instead
