"""Anthropic-envelope <-> Gemini translation (pure, testable, network-free).

This is the layer that makes Gemini tool-calling FAITHFUL despite the OpenAPI
subset Gemini enforces on ``functionDeclarations``. The Leg-1 probe measured
three losses; each has a repair here:

  1. **non-STRING enums** — Gemini allows ``enum`` only on STRING. Drop the enum
     (the type is kept; the value still transits).
  2. **property-less object** — Gemini rejects a nested object with no
     ``properties``. Stringify it to a JSON-object STRING and RECONSTRUCT it on
     the return path, so nested values survive (the probe's ``parms:{}`` drop).
  3. **untyped ('any') slot** — Gemini requires a type on every property. Type it
     as STRING and reconstruct via JSON on return.

Reconstruction is driven by the ORIGINAL Anthropic ``input_schema``, recursively,
so deeply-nested free-form objects (e.g. solaris ``nodes[].parms``) round-trip.
No Qt, no hou, no network.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

_DROP_KEYS = ("additionalProperties", "$schema", "default", "examples", "title")


# -- schema repair (Anthropic input_schema -> Gemini OpenAPI subset) ---------

def repair_schema(schema: Any) -> Any:
    """Return a Gemini-safe copy of a JSON-Schema node (recursive)."""
    if not isinstance(schema, dict):
        return schema
    out = {k: v for k, v in schema.items() if k not in _DROP_KEYS}
    stype = out.get("type")

    # untyped slot -> STRING (reconstructed on the return path)
    if stype is None and "enum" not in out:
        out["type"] = "string"
        stype = "string"

    # enum is only valid on STRING
    if "enum" in out and out.get("type") != "string":
        out.pop("enum", None)

    if stype == "object":
        props = out.get("properties")
        if props:
            out["properties"] = {k: repair_schema(v) for k, v in props.items()}
            if "required" in out:
                out["required"] = [r for r in out["required"] if r in out["properties"]]
        else:
            # free-form object -> stringify (Gemini rejects a property-less object)
            desc = (out.get("description", "") + " (pass a JSON object as a string)").strip()
            return {"type": "string", "description": desc}
    elif stype == "array":
        if isinstance(out.get("items"), dict):
            out["items"] = repair_schema(out["items"])
    return out


def translate_tools(anthropic_tools: List[dict]) -> List[dict]:
    """``[{name, description, input_schema}]`` -> Gemini ``functionDeclarations``."""
    decls: List[dict] = []
    for t in anthropic_tools or []:
        decl: Dict[str, Any] = {"name": t.get("name", "")}
        if t.get("description"):
            decl["description"] = t["description"]
        schema = t.get("input_schema") or {}
        if schema.get("properties"):
            repaired = repair_schema(schema)
            # top-level parameters must be an object-with-properties; otherwise
            # this is effectively a no-arg function and parameters are omitted.
            if (isinstance(repaired, dict) and repaired.get("type") == "object"
                    and repaired.get("properties")):
                decl["parameters"] = repaired
        decls.append(decl)
    return [{"function_declarations": decls}] if decls else []


# -- arg reconstruction (Gemini functionCall.args -> faithful tool input) ----

def reconstruct_args(value: Any, schema: Any) -> Any:
    """Walk ``value`` against the ORIGINAL Anthropic schema, parsing any
    stringified free-form-object / untyped slot back into structured data."""
    if not isinstance(schema, dict):
        return value
    stype = schema.get("type")
    if stype == "object":
        props = schema.get("properties")
        if not props:
            return _maybe_json(value)        # was stringified; parse back
        v = _maybe_json(value) if isinstance(value, str) else value
        if isinstance(v, dict):
            return {k: reconstruct_args(val, props.get(k, {})) for k, val in v.items()}
        return v
    if stype == "array":
        items = schema.get("items", {})
        v = value
        if isinstance(v, str):
            v = _maybe_json(v)
        if isinstance(v, list):
            return [reconstruct_args(x, items) for x in v]
        return value
    if stype is None:
        return _maybe_json(value)
    return value


def _maybe_json(value: Any) -> Any:
    if isinstance(value, str):
        s = value.strip()
        if s and s[0] in "[{":
            try:
                return json.loads(s)
            except Exception:
                return value
    return value


# -- message translation (Anthropic messages -> Gemini contents) -------------

def translate_messages(messages: List[dict]) -> List[dict]:
    """Anthropic messages -> Gemini ``contents`` (functionCall/Response parts).

    Tool-result blocks carry only a ``tool_use_id``; the function name is
    recovered from the id->name map built off the preceding assistant
    ``tool_use`` blocks.
    """
    id_to_name: Dict[str, str] = {}
    contents: List[dict] = []
    for msg in messages or []:
        role = msg.get("role", "user")
        g_role = "model" if role == "assistant" else "user"
        content = msg.get("content", "")
        parts: List[dict] = []
        if isinstance(content, str):
            if content:
                parts.append({"text": content})
        else:
            for block in content or []:
                bt = block.get("type")
                sig = block.get("_gemini_thought_signature")
                if bt == "text":
                    if block.get("text"):
                        t_part = {"text": block["text"]}
                        if sig:                       # echo the model's thought sig
                            t_part["thoughtSignature"] = sig
                        parts.append(t_part)
                elif bt == "tool_use":
                    name = block.get("name", "")
                    bid = block.get("id", "")
                    if bid:
                        id_to_name[bid] = name
                    fc_part = {"functionCall": {
                        "name": name, "args": block.get("input", {}) or {}}}
                    if sig:
                        # Gemini-3 REQUIRES the thoughtSignature echoed back as a
                        # sibling of functionCall, or turn 2+ 400s.
                        fc_part["thoughtSignature"] = sig
                    parts.append(fc_part)
                elif bt == "tool_result":
                    tuid = block.get("tool_use_id", "")
                    name = id_to_name.get(tuid, tuid)
                    parts.append({"functionResponse": {
                        "name": name, "response": _wrap_response(block.get("content", ""))}})
        if parts:
            contents.append({"role": g_role, "parts": parts})
    return contents


def _wrap_response(content: Any) -> dict:
    parsed = _maybe_json(content) if isinstance(content, str) else content
    if isinstance(parsed, dict):
        return parsed
    return {"result": parsed}
