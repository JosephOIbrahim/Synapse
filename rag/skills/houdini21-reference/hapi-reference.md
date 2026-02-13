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
Initialize HAPI. Call once before any other HAPI functions.

### HAPI_Cleanup
```c
HAPI_Result HAPI_Cleanup(const HAPI_Session* session);
```
Clean up HAPI session. Frees all resources.

### HAPI_IsInitialized
```c
HAPI_Result HAPI_IsInitialized(const HAPI_Session* session);
```
Check if session is initialized.

## Asset Loading

### HAPI_LoadAssetLibraryFromFile
```c
HAPI_Result HAPI_LoadAssetLibraryFromFile(
    const HAPI_Session* session,
    const char* file_path,
    HAPI_Bool allow_overwrite,
    HAPI_AssetLibraryId* library_id
);
```
Load HDA from disk. Returns library ID for further operations.

### HAPI_GetAvailableAssetCount
```c
HAPI_Result HAPI_GetAvailableAssetCount(
    const HAPI_Session* session,
    HAPI_AssetLibraryId library_id,
    int* asset_count
);
```

### HAPI_CreateNode
```c
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

### HAPI_GetGeoInfo
```c
HAPI_Result HAPI_GetGeoInfo(
    const HAPI_Session* session,
    HAPI_NodeId node_id,
    HAPI_GeoInfo* geo_info
);
```

### HAPI_GetPartInfo
```c
HAPI_Result HAPI_GetPartInfo(
    const HAPI_Session* session,
    HAPI_NodeId node_id,
    HAPI_PartId part_id,
    HAPI_PartInfo* part_info
);
```

### HAPI_GetAttributeInfo
```c
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

### HAPI_SetAttributeFloatData
```c
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

### HAPI_CommitGeo
```c
HAPI_Result HAPI_CommitGeo(
    const HAPI_Session* session,
    HAPI_NodeId node_id
);
```
Finalize geometry changes. Must call after setting attributes.

## Cooking

### HAPI_CookNode
```c
HAPI_Result HAPI_CookNode(
    const HAPI_Session* session,
    HAPI_NodeId node_id,
    const HAPI_CookOptions* cook_options
);
```

### HAPI_GetStatus
```c
HAPI_Result HAPI_GetStatus(
    const HAPI_Session* session,
    HAPI_StatusType status_type,
    int* status
);
```
Status types: HAPI_STATUS_CALL_RESULT, HAPI_STATUS_COOK_RESULT, HAPI_STATUS_COOK_STATE

## Enums

### HAPI_AttributeOwner
```c
HAPI_ATTROWNER_INVALID = -1
HAPI_ATTROWNER_VERTEX = 0
HAPI_ATTROWNER_POINT = 1
HAPI_ATTROWNER_PRIM = 2
HAPI_ATTROWNER_DETAIL = 3
```

### HAPI_StorageType
```c
HAPI_STORAGETYPE_INVALID = -1
HAPI_STORAGETYPE_INT = 0
HAPI_STORAGETYPE_INT64 = 1
HAPI_STORAGETYPE_FLOAT = 2
HAPI_STORAGETYPE_FLOAT64 = 3
HAPI_STORAGETYPE_STRING = 4
```

---
*Expand from hengine21.0/ Doxygen source as needed*
