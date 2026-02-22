# HAPI Reference (Houdini Engine API)

## Session Management

### HAPI_Initialize
```c
HAPI_Result HAPI_Initialize(
    const HAPI_Session* session,
    const HAPI_CookOptions* cook_options,
    HAPI_Bool use_cooking_thread,
    int cooking_thread_stack_size,
    const char* houdini_environment_files,
    const char* otl_search_path,
    const char* dso_search_path,
    const char* image_dso_search_path,
    const char* audio_dso_search_path
);
```
```c
// Initialize HAPI -- call once before any other HAPI functions

// Clean up session, free all resources
HAPI_Result HAPI_Cleanup(const HAPI_Session* session);

// Check if session is initialized
HAPI_Result HAPI_IsInitialized(const HAPI_Session* session);
```

## Asset Loading

```c
HAPI_Result HAPI_LoadAssetLibraryFromFile(
    const HAPI_Session* session,
    const char* file_path,
    HAPI_Bool allow_overwrite,
    HAPI_AssetLibraryId* library_id
);
```
```c
// Load HDA from disk -- returns library ID for further operations

// Get count of available assets in a loaded library
HAPI_Result HAPI_GetAvailableAssetCount(
    const HAPI_Session* session,
    HAPI_AssetLibraryId library_id,
    int* asset_count
);
```

```c
// Create a node from an operator type
HAPI_Result HAPI_CreateNode(
    const HAPI_Session* session,
    HAPI_NodeId parent_node_id,
    const char* operator_name,
    const char* node_label,
    HAPI_Bool cook_on_creation,
    HAPI_NodeId* new_node_id
);
```

## Geometry Access

```c
// Get geometry info (point/prim/vertex counts, etc.)
HAPI_Result HAPI_GetGeoInfo(
    const HAPI_Session* session,
    HAPI_NodeId node_id,
    HAPI_GeoInfo* geo_info
);

// Get part info (sub-geometry within a node)
HAPI_Result HAPI_GetPartInfo(
    const HAPI_Session* session,
    HAPI_NodeId node_id,
    HAPI_PartId part_id,
    HAPI_PartInfo* part_info
);
```

```c
// Get attribute metadata (type, size, owner)
HAPI_Result HAPI_GetAttributeInfo(
    const HAPI_Session* session,
    HAPI_NodeId node_id,
    HAPI_PartId part_id,
    const char* name,
    HAPI_AttributeOwner owner,
    HAPI_AttributeInfo* attr_info
);
```

### HAPI_GetAttributeFloatData
```c
HAPI_Result HAPI_GetAttributeFloatData(
    const HAPI_Session* session,
    HAPI_NodeId node_id,
    HAPI_PartId part_id,
    const char* name,
    HAPI_AttributeInfo* attr_info,
    int stride,
    float* data_array,
    int start,
    int length
);
```

```c
// Set float attribute data on geometry
HAPI_Result HAPI_SetAttributeFloatData(
    const HAPI_Session* session,
    HAPI_NodeId node_id,
    HAPI_PartId part_id,
    const char* name,
    const HAPI_AttributeInfo* attr_info,
    const float* data_array,
    int start,
    int length
);
```

```c
// Finalize geometry changes -- MUST call after setting attributes
HAPI_Result HAPI_CommitGeo(
    const HAPI_Session* session,
    HAPI_NodeId node_id
);
```

## Cooking

```c
// Cook a node (trigger computation)
HAPI_Result HAPI_CookNode(
    const HAPI_Session* session,
    HAPI_NodeId node_id,
    const HAPI_CookOptions* cook_options
);

// Check cook/call status
// status_type: HAPI_STATUS_CALL_RESULT, HAPI_STATUS_COOK_RESULT, HAPI_STATUS_COOK_STATE
HAPI_Result HAPI_GetStatus(
    const HAPI_Session* session,
    HAPI_StatusType status_type,
    int* status
);
```

## Enums

```c
// Attribute ownership levels
HAPI_ATTROWNER_INVALID = -1;
HAPI_ATTROWNER_VERTEX  = 0;   // Per-vertex (unique per face-corner)
HAPI_ATTROWNER_POINT   = 1;   // Per-point (shared across faces)
HAPI_ATTROWNER_PRIM    = 2;   // Per-primitive
HAPI_ATTROWNER_DETAIL  = 3;   // Global (one value for entire geo)

// Storage types for attribute data
HAPI_STORAGETYPE_INVALID = -1;
HAPI_STORAGETYPE_INT     = 0;   // 32-bit integer
HAPI_STORAGETYPE_INT64   = 1;   // 64-bit integer
HAPI_STORAGETYPE_FLOAT   = 2;   // 32-bit float
HAPI_STORAGETYPE_FLOAT64 = 3;   // 64-bit double
HAPI_STORAGETYPE_STRING  = 4;   // String handle
```

## Common Mistakes
```c
// Forgetting HAPI_CommitGeo after setting attributes -- data won't be visible
HAPI_SetAttributeFloatData(session, node_id, 0, "P", &attr_info, data, 0, count);
HAPI_CommitGeo(session, node_id);  // REQUIRED -- without this, changes are lost

// Not checking HAPI_Result -- all functions return error codes
HAPI_Result result = HAPI_CookNode(session, node_id, &cook_options);
// Always check: result == HAPI_RESULT_SUCCESS

// Using wrong HAPI_AttributeOwner -- vertex vs point confusion
// Vertex: unique per face-corner (UVs, normals)
// Point: shared across faces (position, color)
```
