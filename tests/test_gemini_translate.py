"""Gemini translation + arg-repair (the H3 killer).

The Leg-1 probe measured Gemini dropping nested tool-call args (``parms:{}``
instead of ``{intensity:2.5}``) and rejecting the full registry on integer enums
+ property-less objects. These tests pin the repairs that make tool args faithful
again — driven against the exact ``synapse_solaris_build_graph`` case that failed.
Pure, network-free.
"""
from synapse.panel.providers import gemini_translate as gt


# -- the exact probe schema (deep: array-of-objects with free-form parms) ----
SOLARIS_SCHEMA = {
    "type": "object",
    "properties": {
        "template": {"type": "string",
                     "enum": ["multi_asset_merge", "sublayer_stack", "lighting_rig"]},
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string"},
                    "parms": {"type": "object"},          # free-form (the probe loss)
                },
                "required": ["id", "type"],
            },
        },
        "connections": {"type": "array", "items": {"type": "object"}},
    },
    "required": ["nodes", "connections"],
}


def test_repair_stringifies_freeform_object():
    repaired = gt.repair_schema({"type": "object", "description": "Entry content"})
    assert repaired["type"] == "string"          # property-less object -> string
    assert "JSON object" in repaired["description"]


def test_repair_drops_non_string_enum():
    repaired = gt.repair_schema({"type": "integer", "enum": [0, 1]})
    assert "enum" not in repaired                 # int enum dropped (Gemini: STRING only)
    assert repaired["type"] == "integer"          # type preserved


def test_repair_keeps_string_enum():
    repaired = gt.repair_schema({"type": "string", "enum": ["a", "b"]})
    assert repaired["enum"] == ["a", "b"]


def test_repair_types_untyped_slot():
    repaired = gt.repair_schema({"description": "Value to set"})  # no 'type'
    assert repaired["type"] == "string"


def test_translate_tools_omits_parameters_for_no_arg_tool():
    decls = gt.translate_tools([
        {"name": "synapse_ping", "description": "ping",
         "input_schema": {"type": "object", "properties": {}, "required": []}},
    ])
    fn = decls[0]["function_declarations"][0]
    assert fn["name"] == "synapse_ping"
    assert "parameters" not in fn                 # no-arg -> parameters omitted


def test_translate_tools_repairs_freeform_in_nested_array():
    decls = gt.translate_tools([
        {"name": "synapse_solaris_build_graph", "description": "build",
         "input_schema": SOLARIS_SCHEMA},
    ])
    params = decls[0]["function_declarations"][0]["parameters"]
    node_items = params["properties"]["nodes"]["items"]
    # the nested free-form parms is stringified so Gemini accepts the payload
    assert node_items["properties"]["parms"]["type"] == "string"


def test_reconstruct_round_trips_nested_parms_THE_H3_KILLER():
    # what Gemini returns: parms came back as a JSON-object STRING (because we
    # declared it as a string). Without reconstruction this is the probe's loss.
    gemini_args = {
        "template": "lighting_rig",
        "nodes": [
            {"id": "dome1", "type": "domelight", "parms": '{"intensity": 2.5}'},
            {"id": "rect1", "type": "rectlight", "parms": '{"exposure": 1.0}'},
        ],
        "connections": [{"from": "dome1", "to": "rect1"}],
    }
    fixed = gt.reconstruct_args(gemini_args, SOLARIS_SCHEMA)
    # nested parms reconstructed to real dicts WITH their values — not dropped
    assert fixed["nodes"][0]["parms"] == {"intensity": 2.5}
    assert fixed["nodes"][1]["parms"] == {"exposure": 1.0}
    assert fixed["template"] == "lighting_rig"
    assert fixed["connections"] == [{"from": "dome1", "to": "rect1"}]


def test_reconstruct_passes_through_already_structured():
    # if a provider returns a real dict (not stringified), leave it intact
    args = {"nodes": [{"id": "a", "type": "x", "parms": {"k": 1}}], "connections": []}
    fixed = gt.reconstruct_args(args, SOLARIS_SCHEMA)
    assert fixed["nodes"][0]["parms"] == {"k": 1}


def test_translate_messages_tool_use_and_result():
    messages = [
        {"role": "user", "content": "make a sphere"},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "toolu_9", "name": "houdini_create_node",
             "input": {"parent": "/obj", "type": "geo"}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "toolu_9",
             "content": '{"path": "/obj/geo1"}'},
        ]},
    ]
    contents = gt.translate_messages(messages)
    assert contents[0] == {"role": "user", "parts": [{"text": "make a sphere"}]}
    fc = contents[1]["parts"][0]["functionCall"]
    assert fc["name"] == "houdini_create_node"
    assert fc["args"] == {"parent": "/obj", "type": "geo"}
    fr = contents[2]["parts"][0]["functionResponse"]
    assert fr["name"] == "houdini_create_node"        # name recovered from id map
    assert fr["response"] == {"path": "/obj/geo1"}     # JSON content parsed to struct


def test_translate_messages_echoes_thought_signature():
    # Gemini-3 thinking models 400 on turn 2+ unless the model's prior functionCall
    # is echoed WITH its thoughtSignature (sibling of functionCall on the part).
    messages = [
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "gemini-x-0", "name": "synapse_project_setup",
             "input": {"name": "aurora"}, "_gemini_thought_signature": "SIGabc=="},
        ]},
    ]
    part = gt.translate_messages(messages)[0]["parts"][0]
    assert part["functionCall"]["name"] == "synapse_project_setup"
    assert part["thoughtSignature"] == "SIGabc=="          # echoed as a sibling
    assert "thoughtSignature" not in part["functionCall"]   # NOT nested inside


def test_translate_messages_no_signature_when_absent():
    messages = [{"role": "assistant", "content": [
        {"type": "tool_use", "id": "toolu_1", "name": "t", "input": {}}]}]
    part = gt.translate_messages(messages)[0]["parts"][0]
    assert "thoughtSignature" not in part                   # Claude turns stay clean
