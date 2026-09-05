# Panel rhythm census

Source-only; no host or Qt imports. Counts are source sites, including dormant modules, not runtime widget instances.

Measurement complete: **True**. Date: 2026-09-05.

Totals: **16** spacing; **1** inline sheets; **0** raw hex / **0** distinct; **17** exemption tags. Additional grid-spacing sites: **0**.

Hex means every six-digit source occurrence outside designsystem/, including comments and token-valued fallbacks; case folded. Calls are AST calls (comments/string lookalikes excluded). Exemptions are Python comments only, associated with sites on their starting line. Values preserve expressions without evaluation. See JSON for every site, owner, line and hash.

| File (under python/synapse/panel/) | Spacing | Inline sheets | Hex raw / distinct | Ds sites / names | Exempt |
|---|---:|---:|---:|---:|---:|
| __init__.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| agent_health.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| agent_prompts.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| apex_explainer.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| apex_recipes.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| apex_trace.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| async_format.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| bookmarks.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| bridge_adapter.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| chat_display.py | 0 | 0 | 0 / 0 | 1 / 1 | 0 |
| chat_panel.py | 4 | 0 | 0 / 0 | 1 / 1 | 4 |
| claude_worker.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| command_palette.py | 0 | 0 | 0 / 0 | 4 / 4 | 0 |
| compositor.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| context_bar.py | 2 | 0 | 0 / 0 | 0 / 0 | 2 |
| cross_scene.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| decision_log.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| dependency_map.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| direct_tool.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| dnd.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| error_translator.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| explain_mode.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| exposure_seam.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| face_review.py | 2 | 0 | 0 / 0 | 9 / 4 | 2 |
| face_token.py | 0 | 0 | 0 / 0 | 11 / 6 | 0 |
| face_work.py | 2 | 0 | 0 / 0 | 3 / 2 | 2 |
| gate_stamp.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| gate_widget.py | 2 | 0 | 0 / 0 | 0 / 0 | 2 |
| hda_controller.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| hda_views.py | 0 | 0 | 0 / 0 | 18 / 16 | 0 |
| health_infographic.py | 0 | 0 | 0 / 0 | 1 / 1 | 0 |
| health_strip.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| image_prep.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| integrity_readout.py | 2 | 0 | 0 / 0 | 1 / 1 | 2 |
| manifests/__init__.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| manifests/curious.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| manifests/expert.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| manifests/ml.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| message_formatter.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| network_trace.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| performance_profiler.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| prompt_to_hda.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| providers/__init__.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| providers/anthropic_provider.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| providers/base.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| providers/catalog.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| providers/custom_provider.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| providers/gemini_provider.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| providers/gemini_translate.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| providers/nemotron_provider.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| providers/ollama_provider.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| providers/probe.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| providers/registry.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| quick_actions.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| recall_card.py | 2 | 0 | 0 / 0 | 4 / 4 | 2 |
| recipe_book.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| recipe_card.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| render_preflight.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| render_receipt.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| result_telemetry.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| retry_breaker.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| routing_log.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| save_shot.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| scene_doctor.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| scripts/probe_ui_font.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| session_integrity.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| session_journal.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| settings.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| shot_login.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| styles.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| synapse_panel.py | 0 | 1 | 0 / 0 | 17 / 15 | 1 |
| system_prompt.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| token_readout.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| tokens.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| tool_bridge.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| tool_executor.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| tool_filter.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| tool_palette.py | 0 | 0 | 0 / 0 | 5 / 5 | 0 |
| usage_sink.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| verdict.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| vex_tutor.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| vision_attach.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| voice_contract.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| worker_policy.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| working_indicator.py | 0 | 0 | 0 / 0 | 1 / 1 | 0 |
| ws_bridge.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |

Outside designsystem/: 76 Ds naming sites, 49 names. Including designsystem/: 83 sites, 55 names. Runtime Ds widget count: UNKNOWN: source sites may execute zero, one, or many times.

## Density QSS (source templates)

```json
{
  "path": "python/synapse/panel/designsystem/qss.py",
  "rule_blocks": 9,
  "selectors": 10,
  "margin_rule_blocks": 9,
  "padding_rule_blocks": 0,
  "rules": [
    {
      "line": 297,
      "selectors": [
        "#DsRoot[density=\"airy\"] QWidget#DsTabRow"
      ],
      "properties": [
        "margin-bottom"
      ],
      "body_template": "margin-bottom: EXPRpx;"
    },
    {
      "line": 298,
      "selectors": [
        "#DsRoot[density=\"tight\"] QWidget#DsTabRow"
      ],
      "properties": [
        "margin-bottom"
      ],
      "body_template": "margin-bottom: EXPRpx;"
    },
    {
      "line": 303,
      "selectors": [
        "#DsRoot[density=\"airy\"] QPushButton#DsVerb"
      ],
      "properties": [
        "margin-top",
        "margin-bottom"
      ],
      "body_template": "margin-top: EXPRpx; margin-bottom: EXPRpx;"
    },
    {
      "line": 304,
      "selectors": [
        "#DsRoot[density=\"tight\"] QPushButton#DsVerb"
      ],
      "properties": [
        "margin-top",
        "margin-bottom"
      ],
      "body_template": "margin-top: EXPRpx; margin-bottom: EXPRpx;"
    },
    {
      "line": 308,
      "selectors": [
        "#DsRoot[density=\"airy\"] QWidget#DsHeader"
      ],
      "properties": [
        "margin-bottom"
      ],
      "body_template": "margin-bottom: EXPRpx;"
    },
    {
      "line": 309,
      "selectors": [
        "#DsRoot[density=\"tight\"] QWidget#DsHeader"
      ],
      "properties": [
        "margin-bottom"
      ],
      "body_template": "margin-bottom: EXPRpx;"
    },
    {
      "line": 436,
      "selectors": [
        "#DsRoot[density=\"EXPR\"] [rhythm_role=\"label\"]"
      ],
      "properties": [
        "margin-top",
        "margin-bottom"
      ],
      "body_template": "margin-top: EXPRpx;\n    margin-bottom: EXPRpx;"
    },
    {
      "line": 436,
      "selectors": [
        "#DsRoot[density=\"EXPR\"] [rhythm_role=\"label\"]#DsParmSection"
      ],
      "properties": [
        "margin-top"
      ],
      "body_template": "margin-top: EXPRpx;"
    },
    {
      "line": 436,
      "selectors": [
        "#DsRoot[density=\"EXPR\"] [rhythm_role=\"tag\"]",
        "#DsRoot[density=\"EXPR\"] QLabel#DsBadge[rhythm_role=\"tag\"]"
      ],
      "properties": [
        "margin-left"
      ],
      "body_template": "margin-left: EXPRpx;"
    }
  ]
}
```

## Camera reachability

Flags describe direct source evidence in the listed scopes, not every child. Factory/inherited names require the region map; ABSENT/UNKNOWN never implies a clean camera path.

| Region | Status | Named | Inline styled | Layout owned | Owners |
|---|---|---|---|---|---|
| Profile tab strip | VERIFIED_STATIC | True | False | True | python/synapse/panel/synapse_panel.py:1034 SynapsePanel._build_mode_bar |
| Header/ribbon | VERIFIED_STATIC | True | False | True | python/synapse/panel/synapse_panel.py:648 SynapsePanel._build_rail; python/synapse/panel/synapse_panel.py:978 SynapsePanel._build_context_ribbon |
| Chat transcript | VERIFIED_STATIC | True | False | True | python/synapse/panel/synapse_panel.py:995 SynapsePanel._build_converse; python/synapse/panel/synapse_panel.py:1153 SynapsePanel._build_direct_face; python/synapse/panel/chat_display.py:80 ChatDisplay |
| Verb rail | VERIFIED_STATIC | True | False | True | python/synapse/panel/synapse_panel.py:1887 SynapsePanel._build_act; python/synapse/panel/synapse_panel.py:1869 SynapsePanel._verb |
| Recall result | VERIFIED_STATIC | True | False | True | python/synapse/panel/recall_card.py:1 <module> |
| TOKEN face | VERIFIED_STATIC | True | False | True | python/synapse/panel/synapse_panel.py:1108 SynapsePanel._build_token_face; python/synapse/panel/face_token.py:295 FaceToken; python/synapse/panel/face_token.py:59 TokenField; python/synapse/panel/token_readout.py:1 <module> |
