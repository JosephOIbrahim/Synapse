# Panel rhythm census

Source-only; no host or Qt imports. Counts are source sites, including dormant modules, not runtime widget instances.

Measurement complete: **True**. Date: 2026-09-04.

Totals: **107** spacing; **106** inline sheets; **135** raw hex / **75** distinct; **0** exemption tags. Additional grid-spacing sites: **4**.

Hex means every six-digit source occurrence outside designsystem/, including comments and token-valued fallbacks; case folded. Calls are AST calls (comments/string lookalikes excluded). Exemptions are Python comments only, associated with sites on their starting line. Values preserve expressions without evaluation. See JSON for every site, owner, line and hash.

| File (under python/synapse/panel/) | Spacing | Inline sheets | Hex raw / distinct | Ds sites / names | Exempt |
|---|---:|---:|---:|---:|---:|
| __init__.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| agent_health.py | 0 | 0 | 14 / 5 | 0 / 0 | 0 |
| agent_prompts.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| apex_explainer.py | 0 | 0 | 10 / 10 | 0 / 0 | 0 |
| apex_recipes.py | 0 | 0 | 3 / 3 | 0 / 0 | 0 |
| apex_trace.py | 0 | 0 | 14 / 10 | 0 / 0 | 0 |
| async_format.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| bookmarks.py | 0 | 0 | 4 / 4 | 0 / 0 | 0 |
| bridge_adapter.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| chat_display.py | 0 | 2 | 0 / 0 | 0 / 0 | 0 |
| chat_panel.py | 16 | 20 | 0 / 0 | 0 / 0 | 0 |
| claude_worker.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| command_palette.py | 3 | 4 | 5 / 5 | 0 / 0 | 0 |
| compositor.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| context_bar.py | 7 | 10 | 4 / 4 | 0 / 0 | 0 |
| cross_scene.py | 0 | 0 | 6 / 6 | 0 / 0 | 0 |
| decision_log.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| dependency_map.py | 0 | 0 | 4 / 3 | 0 / 0 | 0 |
| direct_tool.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| dnd.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| error_translator.py | 0 | 0 | 1 / 1 | 0 / 0 | 0 |
| explain_mode.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| exposure_seam.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| face_review.py | 13 | 4 | 0 / 0 | 9 / 4 | 0 |
| face_token.py | 7 | 8 | 9 / 5 | 1 / 1 | 0 |
| face_work.py | 4 | 5 | 0 / 0 | 3 / 2 | 0 |
| gate_stamp.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| gate_widget.py | 12 | 23 | 0 / 0 | 0 / 0 | 0 |
| hda_controller.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| hda_views.py | 9 | 17 | 0 / 0 | 0 / 0 | 0 |
| health_infographic.py | 0 | 0 | 0 / 0 | 1 / 1 | 0 |
| health_strip.py | 2 | 1 | 0 / 0 | 0 / 0 | 0 |
| image_prep.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| integrity_readout.py | 2 | 0 | 0 / 0 | 1 / 1 | 0 |
| manifests/__init__.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| manifests/curious.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| manifests/expert.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| manifests/ml.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| message_formatter.py | 0 | 0 | 5 / 5 | 0 / 0 | 0 |
| network_trace.py | 0 | 0 | 9 / 6 | 0 / 0 | 0 |
| performance_profiler.py | 0 | 0 | 9 / 6 | 0 / 0 | 0 |
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
| quick_actions.py | 4 | 2 | 0 / 0 | 0 / 0 | 0 |
| recipe_book.py | 0 | 0 | 2 / 2 | 0 / 0 | 0 |
| render_preflight.py | 0 | 0 | 6 / 4 | 0 / 0 | 0 |
| render_receipt.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| result_telemetry.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| retry_breaker.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| routing_log.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| save_shot.py | 0 | 0 | 3 / 3 | 0 / 0 | 0 |
| scene_doctor.py | 0 | 0 | 7 / 6 | 0 / 0 | 0 |
| scripts/probe_ui_font.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| session_integrity.py | 0 | 0 | 3 / 3 | 0 / 0 | 0 |
| session_journal.py | 0 | 0 | 1 / 1 | 0 / 0 | 0 |
| settings.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| shot_login.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| styles.py | 0 | 0 | 1 / 1 | 0 / 0 | 0 |
| synapse_panel.py | 23 | 6 | 0 / 0 | 15 / 14 | 0 |
| system_prompt.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| token_readout.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| tokens.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| tool_bridge.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| tool_executor.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| tool_filter.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| tool_palette.py | 3 | 2 | 0 / 0 | 4 / 4 | 0 |
| usage_sink.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| verdict.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| vex_tutor.py | 0 | 0 | 15 / 13 | 0 / 0 | 0 |
| vision_attach.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| voice_contract.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| worker_policy.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |
| working_indicator.py | 2 | 2 | 0 / 0 | 0 / 0 | 0 |
| ws_bridge.py | 0 | 0 | 0 / 0 | 0 / 0 | 0 |

Outside designsystem/: 34 Ds naming sites, 18 names. Including designsystem/: 40 sites, 24 names. Runtime Ds widget count: UNKNOWN: source sites may execute zero, one, or many times.

## Density QSS (source templates)

```json
{
  "path": "python/synapse/panel/designsystem/qss.py",
  "rule_blocks": 13,
  "selectors": 15,
  "margin_rule_blocks": 6,
  "padding_rule_blocks": 7,
  "rules": [
    {
      "line": 293,
      "selectors": [
        "#DsRoot[density=\"airy\"] QTextBrowser"
      ],
      "properties": [
        "padding-top",
        "padding-bottom"
      ],
      "body_template": "padding-top: EXPRpx; padding-bottom: EXPRpx;"
    },
    {
      "line": 296,
      "selectors": [
        "#DsRoot[density=\"airy\"] QWidget#DsHeader"
      ],
      "properties": [
        "padding-top",
        "padding-bottom"
      ],
      "body_template": "padding-top: EXPRpx; padding-bottom: EXPRpx;"
    },
    {
      "line": 299,
      "selectors": [
        "#DsRoot[density=\"airy\"] QWidget#DsTabRow"
      ],
      "properties": [
        "padding-top",
        "padding-bottom"
      ],
      "body_template": "padding-top: EXPRpx; padding-bottom: EXPRpx;"
    },
    {
      "line": 302,
      "selectors": [
        "#DsRoot[density=\"airy\"] QPushButton#DsButton"
      ],
      "properties": [
        "padding"
      ],
      "body_template": "padding: EXPRpx EXPRpx;"
    },
    {
      "line": 305,
      "selectors": [
        "#DsRoot[density=\"airy\"] QTextEdit#DsInput",
        "#DsRoot[density=\"airy\"] QLineEdit#DsField"
      ],
      "properties": [
        "padding-top",
        "padding-bottom"
      ],
      "body_template": "padding-top: EXPRpx; padding-bottom: EXPRpx;"
    },
    {
      "line": 310,
      "selectors": [
        "#DsRoot[density=\"tight\"] QPushButton#DsButton"
      ],
      "properties": [
        "padding"
      ],
      "body_template": "padding: EXPRpx EXPRpx;"
    },
    {
      "line": 313,
      "selectors": [
        "#DsRoot[density=\"tight\"] QTextEdit#DsInput",
        "#DsRoot[density=\"tight\"] QLineEdit#DsField"
      ],
      "properties": [
        "padding-top",
        "padding-bottom"
      ],
      "body_template": "padding-top: EXPRpx; padding-bottom: EXPRpx;"
    },
    {
      "line": 336,
      "selectors": [
        "#DsRoot[density=\"airy\"] QWidget#DsTabRow"
      ],
      "properties": [
        "margin-bottom"
      ],
      "body_template": "margin-bottom: EXPRpx;"
    },
    {
      "line": 337,
      "selectors": [
        "#DsRoot[density=\"tight\"] QWidget#DsTabRow"
      ],
      "properties": [
        "margin-bottom"
      ],
      "body_template": "margin-bottom: EXPRpx;"
    },
    {
      "line": 342,
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
      "line": 343,
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
      "line": 347,
      "selectors": [
        "#DsRoot[density=\"airy\"] QWidget#DsHeader"
      ],
      "properties": [
        "margin-bottom"
      ],
      "body_template": "margin-bottom: EXPRpx;"
    },
    {
      "line": 348,
      "selectors": [
        "#DsRoot[density=\"tight\"] QWidget#DsHeader"
      ],
      "properties": [
        "margin-bottom"
      ],
      "body_template": "margin-bottom: EXPRpx;"
    }
  ]
}
```

## Camera reachability

Flags describe direct source evidence in the listed scopes, not every child. Factory/inherited names require the region map; ABSENT/UNKNOWN never implies a clean camera path.

| Region | Status | Named | Inline styled | Layout owned | Owners |
|---|---|---|---|---|---|
| Profile tab strip | VERIFIED_STATIC | True | False | True | python/synapse/panel/synapse_panel.py:981 SynapsePanel._build_mode_bar |
| Header/ribbon | VERIFIED_STATIC | True | True | True | python/synapse/panel/synapse_panel.py:608 SynapsePanel._build_rail; python/synapse/panel/synapse_panel.py:927 SynapsePanel._build_context_ribbon |
| Chat transcript | VERIFIED_STATIC | False | True | True | python/synapse/panel/synapse_panel.py:942 SynapsePanel._build_converse; python/synapse/panel/synapse_panel.py:1098 SynapsePanel._build_direct_face; python/synapse/panel/chat_display.py:80 ChatDisplay |
| Verb rail | VERIFIED_STATIC | True | False | True | python/synapse/panel/synapse_panel.py:1804 SynapsePanel._build_act; python/synapse/panel/synapse_panel.py:1787 SynapsePanel._verb |
| Recall result | ABSENT | UNKNOWN | UNKNOWN | UNKNOWN | ABSENT |
| TOKEN face | VERIFIED_STATIC | True | True | True | python/synapse/panel/synapse_panel.py:1053 SynapsePanel._build_token_face; python/synapse/panel/face_token.py:295 FaceToken; python/synapse/panel/face_token.py:59 TokenField; python/synapse/panel/token_readout.py:1 <module> |
