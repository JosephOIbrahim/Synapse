"""
Synapse Protocol

Command types and data structures for the Synapse communication protocol.
Provides backwards compatibility with Nexus v3.x and Synapse v2.x protocol.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from enum import Enum

try:
    import orjson
    def _to_json_str(data: dict, pre_sorted: bool = False) -> str:
        if pre_sorted:
            return orjson.dumps(data).decode()
        return orjson.dumps(data, option=orjson.OPT_SORT_KEYS).decode()
    def _from_json(s: str) -> dict:
        return orjson.loads(s)
except ImportError:
    def _to_json_str(data: dict, pre_sorted: bool = False) -> str:
        if pre_sorted:
            return json.dumps(data)
        return json.dumps(data, sort_keys=True)
    def _from_json(s: str) -> dict:
        return json.loads(s)

# Protocol version - bumped to 4.0.0 for standalone Synapse
PROTOCOL_VERSION = "4.0.0"


class CommandType(Enum):
    """
    Command types for the Synapse protocol.

    Memory commands use simplified names (no ENGRAM_ prefix).
    Old ENGRAM_* names are accepted for backwards compatibility.
    """
    # Node operations
    CREATE_NODE = "create_node"
    DELETE_NODE = "delete_node"
    MODIFY_NODE = "modify_node"
    CONNECT_NODES = "connect_nodes"
    NETWORK_EXPLAIN = "network_explain"

    # Scene operations
    GET_SCENE_INFO = "get_scene_info"
    GET_SELECTION = "get_selection"
    SET_SELECTION = "set_selection"

    # Parameter operations
    GET_PARM = "get_parm"
    SET_PARM = "set_parm"

    # Execution
    EXECUTE_PYTHON = "execute_python"
    EXECUTE_VEX = "execute_vex"

    # USD/Solaris operations
    CREATE_USD_PRIM = "create_usd_prim"
    MODIFY_USD_PRIM = "modify_usd_prim"
    GET_STAGE_INFO = "get_stage_info"
    SET_USD_ATTRIBUTE = "set_usd_attribute"
    GET_USD_ATTRIBUTE = "get_usd_attribute"
    QUERY_PRIMS = "query_prims"
    MANAGE_VARIANT_SET = "manage_variant_set"
    MANAGE_COLLECTION = "manage_collection"
    CONFIGURE_LIGHT_LINKING = "configure_light_linking"
    SOLARIS_VALIDATE_ORDERING = "solaris_validate_ordering"

    # Utility
    PING = "ping"
    GET_NODE_TYPES = "get_node_types"
    GET_HELP = "get_help"
    GET_HEALTH = "get_health"

    # Quality validation
    VALIDATE_FRAME = "validate_frame"

    # TOPS / PDG
    TOPS_GET_WORK_ITEMS = "tops_get_work_items"
    TOPS_GET_DEPENDENCY_GRAPH = "tops_get_dependency_graph"
    TOPS_GET_COOK_STATS = "tops_get_cook_stats"
    TOPS_COOK_NODE = "tops_cook_node"
    TOPS_GENERATE_ITEMS = "tops_generate_items"
    TOPS_CONFIGURE_SCHEDULER = "tops_configure_scheduler"
    TOPS_CANCEL_COOK = "tops_cancel_cook"
    TOPS_DIRTY_NODE = "tops_dirty_node"
    TOPS_SETUP_WEDGE = "tops_setup_wedge"
    TOPS_BATCH_COOK = "tops_batch_cook"
    TOPS_QUERY_ITEMS = "tops_query_items"
    TOPS_COOK_AND_VALIDATE = "tops_cook_and_validate"
    TOPS_DIAGNOSE = "tops_diagnose"
    TOPS_PIPELINE_STATUS = "tops_pipeline_status"
    TOPS_MONITOR_STREAM = "tops_monitor_stream"
    TOPS_RENDER_SEQUENCE = "tops_render_sequence"
    TOPS_MULTI_SHOT = "tops_multi_shot"

    # Copernicus (COPs) — Foundation
    COPS_CREATE_NETWORK = "cops_create_network"
    COPS_CREATE_NODE = "cops_create_node"
    COPS_CONNECT = "cops_connect"
    COPS_SET_OPENCL = "cops_set_opencl"
    COPS_READ_LAYER_INFO = "cops_read_layer_info"

    # Copernicus (COPs) — Pipeline Integration
    COPS_TO_MATERIALX = "cops_to_materialx"
    COPS_COMPOSITE_AOVS = "cops_composite_aovs"
    COPS_ANALYZE_RENDER = "cops_analyze_render"
    COPS_SLAP_COMP = "cops_slap_comp"

    # Copernicus (COPs) — Procedural & Motion Design
    COPS_CREATE_SOLVER = "cops_create_solver"
    COPS_PROCEDURAL_TEXTURE = "cops_procedural_texture"
    COPS_GROWTH_PROPAGATION = "cops_growth_propagation"
    COPS_REACTION_DIFFUSION = "cops_reaction_diffusion"
    COPS_PIXEL_SORT = "cops_pixel_sort"
    COPS_STYLIZE = "cops_stylize"

    # Copernicus (COPs) — Advanced
    COPS_WETMAP = "cops_wetmap"
    COPS_BAKE_TEXTURES = "cops_bake_textures"
    COPS_TEMPORAL_ANALYSIS = "cops_temporal_analysis"
    COPS_STAMP_SCATTER = "cops_stamp_scatter"
    COPS_BATCH_COOK = "cops_batch_cook"

    # Autonomous render pipeline
    AUTONOMOUS_RENDER = "autonomous_render"

    # Safe / progressive render
    SAFE_RENDER = "safe_render"
    RENDER_PROGRESSIVELY = "render_progressively"

    # HDA (Houdini Digital Asset) operations
    HDA_CREATE = "hda_create"
    HDA_PROMOTE_PARM = "hda_promote_parm"
    HDA_SET_HELP = "hda_set_help"
    HDA_PACKAGE = "hda_package"
    HDA_LIST = "hda_list"

    # Chat routing
    ROUTE_CHAT = "route_chat"

    # Undo / Redo
    UNDO = "undo"
    REDO = "redo"

    # Memory operations (new simplified names)
    CONTEXT = "context"
    SEARCH = "search"
    ADD_MEMORY = "add_memory"
    DECIDE = "decide"
    RECALL = "recall"

    # Backwards compatibility - old ENGRAM_* names
    ENGRAM_CONTEXT = "engram_context"
    ENGRAM_SEARCH = "engram_search"
    ENGRAM_ADD = "engram_add"
    ENGRAM_DECIDE = "engram_decide"
    ENGRAM_RECALL = "engram_recall"

    # Protocol
    RESPONSE = "response"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    BACKPRESSURE = "backpressure"


# Command name aliases for backwards compatibility
# Maps old names to new names
COMMAND_ALIASES: Dict[str, str] = {
    "engram_context": "context",
    "engram_search": "search",
    "engram_add": "add_memory",
    "engram_decide": "decide",
    "engram_recall": "recall",
}


def normalize_command_type(command_type: str) -> str:
    """
    Normalize a command type, converting old names to new names.

    Args:
        command_type: The command type string

    Returns:
        Normalized command type string
    """
    return COMMAND_ALIASES.get(command_type.lower(), command_type)


@dataclass
class SynapseCommand:
    """
    Command structure for Synapse communication.

    Wire format name kept as SynapseCommand for protocol compatibility.
    """
    type: str
    id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    sequence: int = 0
    timestamp: float = field(default_factory=time.time)
    protocol_version: str = PROTOCOL_VERSION

    def to_json(self) -> str:
        return _to_json_str({
            "id": self.id,
            "payload": self.payload,
            "protocol_version": self.protocol_version,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "type": self.type,
        })

    @classmethod
    def from_json(cls, data: str) -> 'SynapseCommand':
        parsed = _from_json(data)
        return cls(
            type=parsed.get("type", ""),
            id=parsed.get("id", ""),
            payload=parsed.get("payload", {}),
            sequence=parsed.get("sequence", 0),
            # He2025: preserve wire timestamp; 0.0 sentinel = "not provided"
            # (avoids injecting nondeterministic time.time() on deserialization)
            timestamp=parsed.get("timestamp", 0.0),
            protocol_version=parsed.get("protocol_version", "1.0.0")
        )

    def normalized_type(self) -> str:
        """Get normalized command type (converts old names to new)."""
        return normalize_command_type(self.type)


@dataclass
class SynapseResponse:
    """
    Response structure for Synapse communication.

    Wire format name kept as SynapseResponse for protocol compatibility.
    """
    id: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    sequence: int = 0
    timestamp: float = field(default_factory=time.time)
    protocol_version: str = PROTOCOL_VERSION

    def to_json(self) -> str:
        return _to_json_str({
            "data": self.data,
            "error": self.error,
            "id": self.id,
            "protocol_version": self.protocol_version,
            "sequence": self.sequence,
            "success": self.success,
            "timestamp": self.timestamp,
        })

    @classmethod
    def from_json(cls, data: str) -> 'SynapseResponse':
        parsed = _from_json(data)
        return cls(
            id=parsed.get("id", ""),
            success=parsed.get("success", False),
            data=parsed.get("data"),
            error=parsed.get("error"),
            sequence=parsed.get("sequence", 0),
            # He2025: preserve wire timestamp; 0.0 sentinel = "not provided"
            timestamp=parsed.get("timestamp", 0.0),
            protocol_version=parsed.get("protocol_version", "1.0.0")
        )


# Timing constants
HEARTBEAT_INTERVAL = 30.0
COMMAND_TIMEOUT = 60.0
MAX_PENDING_COMMANDS = 100
MAX_PORT_RETRIES = 4
PORT_RETRY_DELAY = 0.5
