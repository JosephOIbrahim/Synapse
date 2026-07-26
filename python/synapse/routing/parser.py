"""
Synapse Tier 0: Command Parser

Regex-based natural language → SynapseCommand translation.
No LLM. No network. Runs in <1ms.

Patterns are compiled at import time and tried in frequency order.
First match wins. Confidence is per-pattern (never < 0.85 for a match).
"""

import re
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple

from ..core.protocol import SynapseCommand
from ..core.aliases import resolve_param_with_default
from ..core.determinism import deterministic_uuid


@dataclass
class ParseResult:
    """Result of Tier 0 command parsing."""
    matched: bool
    command: Optional[SynapseCommand] = None
    pattern_name: str = ""
    confidence: float = 0.0
    extracted: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Regex building blocks
# ---------------------------------------------------------------------------

_PATH = r"(/?[\w][\w\-./]*)"          # /obj/geo1/scatter-1
_TYPE = r"([\w:.]+)"                   # hlight::2.0
_NAME = r"([\w\-]+)"                   # key_light
_VALUE = r"(.+)"                       # 1.5, "hello", [1,2,3]
_PARM = r"([\w]+)"                     # intensity, tx
_WORDS = r"(.+?)"                      # any short text

# ---------------------------------------------------------------------------
# Pattern table  (name, regex, confidence, builder)
# Ordered by expected frequency — first match wins.
# ---------------------------------------------------------------------------

_PATTERNS: List[Tuple[str, "re.Pattern[str]", float, str]] = []


def _p(name: str, pattern: str, confidence: float, builder: str):
    """Register a pattern (compiled once at import)."""
    _PATTERNS.append((name, re.compile(pattern, re.IGNORECASE), confidence, builder))


# --- Utility / protocol ---
_p("ping",
   r"^(?:ping|status|health|healthcheck)$",
   1.0, "_build_ping")

_p("get_help",
   r"^(?:help|what can you do|commands|capabilities)\??$",
   0.95, "_build_get_help")

# --- Scene queries ---
_p("get_selection",
   r"^(?:what(?:'s| is) selected|get selection|selection|selected nodes?)\??$",
   0.95, "_build_get_selection")

_p("get_scene_info",
   r"^(?:scene info|show scene|get scene(?: info)?|scene status)\??$",
   0.95, "_build_get_scene_info")

_p("get_stage_info",
   r"^(?:stage info|show stage|get stage(?: info)?|usd stage)\??$",
   0.9, "_build_get_stage_info")

# --- Parameter operations ---
_p("set_parm",
   r"^set\s+(?:the\s+)?(?:parm(?:ameter)?|param|attr(?:ibute)?)\s+" + _PARM +
   r"\s+(?:on|of|for)\s+" + _PATH + r"\s+to\s+" + _VALUE + r"$",
   0.9, "_build_set_parm")

_p("set_parm_alt",
   r"^set\s+" + _PARM + r"\s+(?:on|of|for)\s+" + _PATH + r"\s+to\s+" + _VALUE + r"$",
   0.9, "_build_set_parm")

_p("get_parm",
   r"^get\s+(?:the\s+)?(?:parm(?:ameter)?|param|attr(?:ibute)?\s+)?" + _PARM +
   r"\s+(?:from|on|of)\s+" + _PATH + r"$",
   0.9, "_build_get_parm")

_p("get_parm_alt",
   r"^(?:what(?:'s| is) (?:the )?)" + _PARM + r"\s+(?:on|of|for)\s+" + _PATH + r"\??$",
   0.85, "_build_get_parm")

# --- Node creation ---
_p("create_node_named",
   r"^create\s+(?:a\s+)?(?:new\s+)?" + _TYPE + r"\s+(?:called|named)\s+" + _NAME +
   r"\s+(?:at|in|under)\s+" + _PATH + r"$",
   0.95, "_build_create_node_named")

_p("create_node",
   r"^create\s+(?:a\s+)?(?:new\s+)?" + _TYPE + r"\s+(?:at|in|under)\s+" + _PATH + r"$",
   0.9, "_build_create_node")

# --- Connections ---
_p("connect",
   r"^connect\s+" + _PATH + r"\s+to\s+" + _PATH + r"$",
   0.95, "_build_connect")

# --- Deletion ---
_p("delete",
   r"^(?:delete|remove)\s+" + _PATH + r"$",
   0.95, "_build_delete")

# --- Compositing (COPs) ---
_p("composite_over",
   r"^(?:composite|comp|merge)\s+" + _PATH + r"\s+(?:over|onto|with)\s+" + _PATH + r"$",
   0.9, "_build_composite_over")

_p("apply_cop_filter",
   r"^(?:apply\s+)?(blur|denoise|sharpen|defocus|glow|grade|color[_ ]?correct)\s+(?:to\s+)?" + _PATH + r"$",
   0.9, "_build_apply_cop_filter")

# --- Camera matching ---
_CAMERA_BODY = r"(arri[\w\s\-]*|red[\w\s\-\[\]]*|sony[\w\s\-]*|bmpcc[\w\s\-]*|blackmagic[\w\s\-]*|canon[\w\s\-]*)"

_p("camera_match",
   r"^(?:match|set up|setup|create)\s+(?:an?\s+)?" + _CAMERA_BODY + r"\s*(?:camera)?$",
   0.85, "_build_camera_match")

_p("camera_match_like",
   r"^camera\s+(?:match|like)\s+(?:an?\s+)?" + _CAMERA_BODY + r"$",
   0.85, "_build_camera_match")


def _parse_value(raw: str) -> Any:
    """Parse a raw string value into a typed Python value."""
    raw = raw.strip()
    # Try float first (handles "1.5", "-0.3")
    try:
        f = float(raw)
        # If it's a whole number, return int
        if f == int(f) and "." not in raw:
            return int(f)
        return f
    except ValueError:
        pass
    # Boolean
    if raw.lower() in ("true", "on", "yes"):
        return True
    if raw.lower() in ("false", "off", "no"):
        return False
    # Strip quotes
    if len(raw) >= 2 and raw[0] in ('"', "'") and raw[-1] == raw[0]:
        return raw[1:-1]
    return raw


class CommandParser:
    """
    Tier 0 command parser.

    Converts natural language text to SynapseCommand via regex matching.
    Patterns are tried in frequency order; first match wins.
    """

    def parse(self, text: str) -> ParseResult:
        """
        Parse input text into a SynapseCommand.

        Returns ParseResult with matched=False if no pattern matches.
        """
        text = text.strip()
        if not text:
            return ParseResult(matched=False)

        for name, regex, confidence, builder_name in _PATTERNS:
            m = regex.match(text)
            if m:
                builder = getattr(self, builder_name)
                command, extracted = builder(m)
                return ParseResult(
                    matched=True,
                    command=command,
                    pattern_name=name,
                    confidence=confidence,
                    extracted=extracted,
                )

        return ParseResult(matched=False)

    # ------------------------------------------------------------------
    # Builders — each returns (SynapseCommand, extracted_dict)
    # ------------------------------------------------------------------

    def _build_ping(self, m: re.Match) -> Tuple[SynapseCommand, Dict]:
        return (
            SynapseCommand(
                type="ping",
                id=deterministic_uuid("parse:ping", "cmd"),
            ),
            {},
        )

    def _build_get_help(self, m: re.Match) -> Tuple[SynapseCommand, Dict]:
        return (
            SynapseCommand(
                type="get_help",
                id=deterministic_uuid("parse:help", "cmd"),
            ),
            {},
        )

    def _build_get_selection(self, m: re.Match) -> Tuple[SynapseCommand, Dict]:
        return (
            SynapseCommand(
                type="get_selection",
                id=deterministic_uuid("parse:sel", "cmd"),
            ),
            {},
        )

    def _build_get_scene_info(self, m: re.Match) -> Tuple[SynapseCommand, Dict]:
        return (
            SynapseCommand(
                type="get_scene_info",
                id=deterministic_uuid("parse:scene", "cmd"),
            ),
            {},
        )

    def _build_get_stage_info(self, m: re.Match) -> Tuple[SynapseCommand, Dict]:
        return (
            SynapseCommand(
                type="get_stage_info",
                id=deterministic_uuid("parse:stage", "cmd"),
            ),
            {},
        )

    def _build_set_parm(self, m: re.Match) -> Tuple[SynapseCommand, Dict]:
        groups = m.groups()
        parm = groups[0]
        path = groups[1]
        value = _parse_value(groups[2])
        extracted = {"parm": parm, "node": path, "value": value}
        return (
            SynapseCommand(
                type="set_parm",
                id=deterministic_uuid(f"parse:setparm:{path}:{parm}", "cmd"),
                payload={"node": path, "parm": parm, "value": value},
            ),
            extracted,
        )

    def _build_get_parm(self, m: re.Match) -> Tuple[SynapseCommand, Dict]:
        groups = m.groups()
        parm = groups[0]
        path = groups[1]
        extracted = {"parm": parm, "node": path}
        return (
            SynapseCommand(
                type="get_parm",
                id=deterministic_uuid(f"parse:getparm:{path}:{parm}", "cmd"),
                payload={"node": path, "parm": parm},
            ),
            extracted,
        )

    def _build_create_node_named(self, m: re.Match) -> Tuple[SynapseCommand, Dict]:
        groups = m.groups()
        node_type = groups[0]
        name = groups[1]
        parent = groups[2]
        extracted = {"type": node_type, "name": name, "parent": parent}
        return (
            SynapseCommand(
                type="create_node",
                id=deterministic_uuid(f"parse:create:{node_type}:{name}", "cmd"),
                payload={"type": node_type, "name": name, "parent": parent},
            ),
            extracted,
        )

    def _build_create_node(self, m: re.Match) -> Tuple[SynapseCommand, Dict]:
        groups = m.groups()
        node_type = groups[0]
        parent = groups[1]
        extracted = {"type": node_type, "parent": parent}
        return (
            SynapseCommand(
                type="create_node",
                id=deterministic_uuid(f"parse:create:{node_type}", "cmd"),
                payload={"type": node_type, "parent": parent},
            ),
            extracted,
        )

    def _build_connect(self, m: re.Match) -> Tuple[SynapseCommand, Dict]:
        groups = m.groups()
        source = groups[0]
        target = groups[1]
        extracted = {"source": source, "target": target}
        return (
            SynapseCommand(
                type="connect_nodes",
                id=deterministic_uuid(f"parse:connect:{source}:{target}", "cmd"),
                payload={"source": source, "target": target},
            ),
            extracted,
        )

    def _build_delete(self, m: re.Match) -> Tuple[SynapseCommand, Dict]:
        groups = m.groups()
        path = groups[0]
        extracted = {"node": path}
        return (
            SynapseCommand(
                type="delete_node",
                id=deterministic_uuid(f"parse:delete:{path}", "cmd"),
                payload={"node": path},
            ),
            extracted,
        )

    def _build_composite_over(self, m: re.Match) -> Tuple[SynapseCommand, Dict]:
        groups = m.groups()
        source = groups[0]
        target = groups[1]
        extracted = {"source": source, "target": target, "domain": "compositing"}
        return (
            SynapseCommand(
                type="connect_nodes",
                id=deterministic_uuid(
                    f"parse:comp:{source}:{target}", "cmd"
                ),
                payload={"source": source, "target": target, "domain": "compositing"},
            ),
            extracted,
        )

    def _build_apply_cop_filter(self, m: re.Match) -> Tuple[SynapseCommand, Dict]:
        groups = m.groups()
        filter_type = groups[0].lower().replace(" ", "").replace("_", "")
        parent = groups[1]
        extracted = {"type": filter_type, "parent": parent, "domain": "compositing"}
        return (
            SynapseCommand(
                type="create_node",
                id=deterministic_uuid(
                    f"parse:copfilter:{filter_type}:{parent}", "cmd"
                ),
                payload={"type": filter_type, "parent": parent, "domain": "compositing"},
            ),
            extracted,
        )

    def _build_camera_match(self, m: re.Match) -> Tuple[SynapseCommand, Dict]:
        groups = m.groups()
        camera_body = groups[0].strip()
        extracted = {"camera_body": camera_body, "domain": "camera"}
        return (
            SynapseCommand(
                type="execute_python",
                id=deterministic_uuid(
                    f"parse:camera_match:{camera_body}", "cmd"
                ),
                payload={"camera_body": camera_body, "domain": "camera"},
            ),
            extracted,
        )
