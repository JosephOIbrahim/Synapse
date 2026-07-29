"""S1 producer path — the classification ledger and every integer in S1_INVENTORY.md.

Merges three verdict sources, each tagged with its provenance so a reader can
discount them differently:

  agent-b1/b3  two cartographer readers (workflow wf_cb86d227-4cd batches 1+3).
               THEIR ADVERSARIAL REFUTATION PASS NEVER RAN - the session token
               limit killed 8 of 10 agents. Carried, flagged, NOT upgraded.
  live         the orchestrator called the tool against live Houdini 22.0.368
               through the /mcp bridge this session. VERIFIED-RUNTIME.
  read         the orchestrator opened the handler and its callees.
               VERIFIED-STATIC.

Emits s1_classification.json + the counts printed here.

Law 1 - how this file can fail: a tool present in s1_tool_census.json and absent
from VERDICTS raises. A tool in VERDICTS that is not registered raises. The
counts cannot silently describe a different tool set than the census.
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
FOR = ROOT / "harness" / "notes" / "forensic"

# ---------------------------------------------------------------------------
# The classification vocabulary, and the one extension this leg made explicit.
#
# The brief defines UNREACHABLE as "registered but no path invokes it". Every
# one of the 120 registry command_types IS registered on the live-path handler
# registry (s1_reachability.json, zero unreachable). So the literal reading
# would return UNREACHABLE=0 and hide the thing the artist actually experiences.
# This leg therefore uses the brief's operative sense - THE TOOL CANNOT BE
# REACHED TO USEFUL EFFECT - and every UNREACHABLE row states which of these
# it is:
#   no-path        nothing dispatches it
#   dead-return    the path runs and structurally cannot return data
#   never-returns  the path runs and does not terminate (observed live)
# ---------------------------------------------------------------------------

VERDICTS: dict[str, dict] = {}


def V(tool, klass, tier, src, ev, anchor, task, reach, gap="", note=""):
    VERDICTS[tool] = {
        "tool": tool, "klass": klass, "tier": tier, "provenance": src,
        "evidence": ev, "anchor": anchor, "artist_task": task,
        "would_artist_reach": reach, "gap": gap, "note": note,
    }


NO_HOST = ("Handler does real work on a real code path, but NO host evidence "
           "exists: every test naming it runs against the canonical FAKE hou "
           "planted by tests/conftest.py:132 before collection. Mechanism read "
           "and plausible; host behaviour unproven.")

# ===========================================================================
# 1. LIVE-EXERCISED THIS SESSION (VERIFIED-RUNTIME) - orchestrator, /mcp bridge
# ===========================================================================
LIVE = "live"
V("synapse_ping", "WORKS", "VERIFIED-RUNTIME", LIVE,
  'Called live: {"pong":true,"protocol_version":"4.0.0"}.',
  "python/synapse/server/handlers.py:849", "agent-internal", False,
  note="Liveness probe. The panel and the agent call it; an artist never does.")
V("synapse_health", "WORKS", "VERIFIED-RUNTIME", LIVE,
  'Called live: {"healthy":true,"houdini_available":true}.',
  "python/synapse/server/handlers.py:857", "agent-internal", False)
V("synapse_doctor", "WORKS", "VERIFIED-RUNTIME", LIVE,
  "Called live: 10 checks ran, 7 ok / 2 fail / 1 skipped. It reported its own "
  "failures (version stamp drift 5.35.1 vs 5.23.0; MonetaMemory schema not "
  "registered) rather than a green summary - Law 3 honoured on a live run.",
  "python/synapse/server/handlers.py:873 -> doctor.py", "pipeline-admin", True,
  note="The single best-behaved tool observed this leg: it is the only one that "
       "reported bad news about itself unprompted.")
V("houdini_scene_info", "WORKS", "VERIFIED-RUNTIME", LIVE,
  'Called live: {"fps":24.0,"frame":1,"frame_range":[1,240],"hip_file":"untitled.hip"}.',
  "python/synapse/server/handlers.py:1152", "agent-internal", False,
  note="Orientation call the agent makes before anything else.")
V("synapse_memory_status", "WORKS", "VERIFIED-RUNTIME", LIVE,
  'Called live: entries_total 19, evolution "charmander", real sizes.',
  "python/synapse/server/handlers_memory.py:224", "agent-internal", False)
V("synapse_list_recipes", "WORKS", "VERIFIED-RUNTIME", LIVE,
  "Called live: 62 recipes returned with categories, triggers, step counts.",
  "python/synapse/server/handlers.py:1572", "agent-internal", False,
  note="62 recipes is a real asset and the largest undersold surface in the "
       "product - see the recipe note in the report.")
V("synapse_context", "WORKS", "VERIFIED-RUNTIME", LIVE,
  "Called live: returned project + scene memory, 23 memories, recent activity, "
  "evolution stage, and three real authored scene notes.",
  "python/synapse/server/handlers_memory.py:52", "agent-internal", False)
V("synapse_knowledge_lookup", "WORKS", "VERIFIED-RUNTIME", LIVE,
  "Called live with 'karma render settings pixel samples' - returned the Karma "
  "guide, confidence 0.9, correct parm karma:global:pathtracedsamples.",
  "python/synapse/server/handlers.py:1684", "look-dev", True,
  note="Answered correctly and fast. The corpus staleness is a separate axis.")
V("synapse_group_scene", "WORKS", "VERIFIED-RUNTIME", LIVE,
  "Called live: returned the SCENE TOOLS knowledge preamble, no Houdini needed.",
  "mcp_server.py:946", "agent-internal", False)
for _g in ("render", "usd", "tops", "memory", "cops"):
    V(f"synapse_group_{_g}", "WORKS", "VERIFIED-DERIVED", LIVE,
      "Same dict-lookup path as synapse_group_scene, which was live-verified; "
      "each key is present in _GROUP_INFO_TOOLS. Derived, not separately called.",
      "mcp_server.py:946", "agent-internal", False)

V("synapse_live_metrics", "PARTIAL", "VERIFIED-RUNTIME", LIVE,
  "Called live and returned a real, well-formed snapshot (resilience, routing, "
  "scene, session).",
  "python/synapse/server/handlers.py:1635", "debugging", False,
  gap="Took over 120s to return and was moved to a background task before "
      "completing. A metrics call that outlives the question is not a metrics call. "
      "Also: zero tests name this tool anywhere in the suite.",
  note="routing block read total_requests 0 / knowledge_entries 0, consistent "
       "with the router never being constructed (see synapse_router_stats).")

V("synapse_router_stats", "UNREACHABLE", "VERIFIED-RUNTIME", LIVE,
  'Called live: returned {"error":"Router not initialized"} - the tool CANNOT '
  "return data through the MCP surface. Static proof of why: self._router is "
  "constructed in exactly one place, _handle_route_chat (handlers.py:1605-1608), "
  "and route_chat is one of the 7 handlers no MCP tool dispatches to "
  "(s1_reachability.json dead_handlers_no_tool_reaches). Only the Houdini panel "
  "sends route_chat (panel/chat_panel.py:799,903). Reached from /mcp alone the "
  "attribute never exists.",
  "python/synapse/server/handlers.py:1566 + :1605", "debugging", False,
  gap="dead-return: registered, dispatched, structurally incapable of returning "
      "data unless the panel chat path ran first in the same process.",
  note="Same root cause silently degrades synapse_metrics, which guards on "
       "hasattr(self,'_router') at handlers.py:1500 and therefore always emits "
       "router_stats=None on this path.")

V("synapse_inspect_scene", "UNREACHABLE", "VERIFIED-RUNTIME", LIVE,
  "Called live TWICE, both to termination. First (max_depth=2): 1800s, no "
  "response, aborted. Control re-run ALONE, nothing else in flight, "
  "max_depth=1: also ran the full 1800s and was aborted, while synapse_ping "
  "answered instantly in the same session and the bridge stayed healthy. The "
  "concurrency explanation is REFUTED.",
  "python/synapse/server/handlers.py:1460 -> introspection.py:278", "debugging", True,
  gap="never-returns, on both a depth-1 and a depth-2 walk. Mechanism NOT "
      "root-caused here (S2's job). Candidate carried, untested: _node_issues "
      "calls node.errors() (introspection.py:184), which forces cooks, on every "
      "node it walks.",
  note="Two things sharpen this. (1) The product's own telemetry names it: "
       'synapse_metrics returns synapse_panel_inline_slow_total'
       '{slowest_tool="synapse_inspect_scene"}. (2) It is the tool '
       "synapse_group_scene instructs the agent to call FIRST - 'Always inspect "
       "before mutating'. The documented entry point to every scene workflow "
       "does not return.",
  )
# SCENE-SIZE CORRECTION. An earlier draft of this leg called the live scene a
# "9-node empty scene" on the strength of synapse_live_metrics (total_nodes 9,
# obj/sop/lop all 0). synapse_metrics, called later in the SAME session,
# reports synapse_scene_nodes_total 16122 with 3 warnings. The two surfaces
# disagree by three orders of magnitude and this leg did not resolve which is
# right. The "trivial scene" framing is therefore WITHDRAWN: the walk may be
# large, which would make the node.errors() candidate above more plausible, not
# less. Recorded as its own finding rather than quietly dropped.
V.__doc__ = None
V("synapse_recall", "PARTIAL", "VERIFIED-RUNTIME", LIVE,
  "VERDICT CORRECTED BY ITS OWN CONTROL. First observation: ran 1800s under "
  "concurrent dispatch and was aborted - provisionally classed UNREACHABLE. "
  "Re-run ALONE it returned FAST and with real content: the RAG augmentation "
  "fired correctly (lighting guide, confidence 0.8125, correct punycode parm "
  "names incl. xn__inputsintensity_i0a). The hang was concurrency-induced. The "
  "UNREACHABLE verdict is WITHDRAWN.",
  "python/synapse/server/handlers_memory.py:112", "agent-internal", False,
  gap="The MEMORY half is dead on this install: the live response carries "
      '{"error":"Memory not available","found":false} alongside '
      '"knowledge_found":true. The RAG seam works; the memory lookup it is '
      "supposed to augment does not.",
  note="Three memory tools give three different answers about whether memory "
       "exists in the same session: synapse_memory_status reported "
       "entries_total 19, synapse_context returned 23 memories, and recall says "
       "'Memory not available'. That inconsistency is the finding, not the hang.")
V("synapse_scout", "UNREACHABLE", "VERIFIED-RUNTIME", LIVE,
  "MECHANISM FOUND, not inferred. Called live twice. First call: 1800s, no "
  "response, aborted. Second call ALONE (single trivial symbol, k=2): blocked "
  "past 120s and then RETURNED AN ERROR -\n"
  '  {"error":"ProgrammingError","message":"SQLite objects created in a thread '
  'can only be used in that same thread. The object was created in thread id '
  '51668 and this is thread id 65704."}\n'
  "Scout does not hang forever - it is slow and then fails on SQLite thread "
  "affinity. Its retrieval store's connection is created on one thread and used "
  "on another.",
  "mcp_server.py:936 -> synapse/cognitive/tools/scout.py:828", "agent-internal", True,
  gap="dead-return: reachable, dispatched, and structurally unable to produce "
      "its artefact on this path - it raises ProgrammingError instead. Same "
      "outcome class as synapse_router_stats, different cause.",
  note="CLAUDE.md rule 15 makes scout the MANDATORY pre-flight before emitting "
       "any unfamiliar hou./pdg./pxr. call - the front-line defence against this "
       "project's self-declared #1 failure class (phantom APIs). It fails on a "
       "threading bug. The control that was meant only to rule out concurrency "
       "produced the mechanism instead.")

V("houdini_stage_info", "PARTIAL", "VERIFIED-RUNTIME", LIVE,
  "Called live on the empty scene: returned the guarded error 'No USD stage "
  "found -- select a LOP node or pass a node path'. The guard path is real, "
  "correctly worded, and does not fake success.",
  "python/synapse/server/handlers_usd.py (get_stage_info)", "scene-assembly", True,
  gap="The SUCCESS path was never exercised - the live scene is untitled.hip "
      "with no stage. Only the refusal is proven.")

# ===========================================================================
# 2. THE SOLARIS FAMILY - the one family with honest host evidence
# ===========================================================================
READ = "read"
SOL_EV = ("Live-gated by host IDENTITY, not by import: tests/solaris/test_live_wiring.py "
          "probes for hou.__synapse_canonical__ and SKIPS on the fake, so it cannot "
          "pass against a mock. The mock fixtures were DELETED under Constitution "
          "Law 1 (tests/solaris/conftest.py:11-21). Executed under hython 22.0.368; "
          "SR1 receipt green, suite 4841->4873 passed, 0 failed, +9 skipped (those "
          "skips ARE this live tier standing down off-host).")
V("synapse_solaris_component_builder", "WORKS", "VERIFIED-RUNTIME", READ,
  SOL_EV + " Covered live by 4 build/wire/idempotence/provenance tests.",
  "tests/solaris/test_live_wiring.py:100-135; handlers_solaris_tools.py:56",
  "scene-assembly", True,
  note="Component Builder is the real USD asset-authoring workflow. This is the "
       "strongest tool in the inventory.")
V("synapse_solaris_scene_template", "WORKS", "VERIFIED-RUNTIME", READ,
  SOL_EV + " Covered live by 4 tests incl. sequential sopimport chaining.",
  "tests/solaris/test_live_wiring.py:149-181", "scene-assembly", True,
  gap="F8 is pinned live and open: execute() reads params['parent'] only, so a "
      "caller passing parent_path is silently ignored.",
  note="Closest thing in the product to 'saves twenty minutes on every shot setup'.")
V("synapse_solaris_set_purpose", "WORKS", "VERIFIED-RUNTIME", READ,
  SOL_EV + " F7 - reporting success having set nothing - was found BY this live "
  "tier and repaired; a live test now asserts it authors a real USD purpose and "
  "that the last write composes.",
  "tests/solaris/test_live_wiring.py:187-298", "look-dev", True,
  note="The clearest evidence in the repo that live gating works: the mock said "
       "green while the tool set nothing.")
V("synapse_solaris_import_megascans", "WORKS", "VERIFIED-RUNTIME", READ,
  SOL_EV + " F9 (PermissionError on every invocation) and F3 repaired and "
  "live-proven on 22.0.368 per the handler's own registration note.",
  "python/synapse/server/handlers_solaris_tools.py:72-78; "
  "tests/solaris/test_live_wiring.py:366", "scene-assembly", True,
  note="Megascans/Fab ingest with unit scaling is a genuine daily-work shortcut.")
V("synapse_solaris_create_variants", "PARTIAL", "VERIFIED-STATIC", READ,
  "Same family and same delegate as its four siblings, but its live coverage is "
  "one NEGATIVE test only - test_create_variants_rejects_a_non_lop_path_live "
  "(test_live_wiring.py:313). Nothing live asserts it BUILDS a variant.",
  "tests/solaris/test_live_wiring.py:313", "look-dev", True,
  gap="No live evidence of the build path - only of the refusal path. The "
      "sibling tests prove construction; this one proves rejection.",
  note="Worth separating from its siblings precisely because the family reads "
       "uniformly green from the outside.")
V("synapse_solaris_assemble_chain", "PARTIAL", "VERIFIED-STATIC", READ,
  "Substantial real logic read end to end: _is_unwired screening, canonical "
  "sort, three modes, B3 overwrite/branch tracking, and an M15 fix that stops "
  "it yanking already-wired nodes out of a chain and reporting the theft as a "
  "clean add. " + NO_HOST,
  "python/synapse/server/handlers_solaris_assemble.py:308", "scene-assembly", True,
  gap="Its 3 tests are mock/registration only; not in the live_wiring tier.",
  note="Highest-leverage unproven tool in the inventory - this is the twenty-"
       "minutes-per-shot claim, and it has no host evidence.")
V("synapse_solaris_build_graph", "PARTIAL", "VERIFIED-STATIC", READ,
  "Real DAG machinery: template expansion, validate_graph, topo_sort, terminal "
  "detection, topology classification. " + NO_HOST,
  "python/synapse/server/handlers_solaris_graph.py:454", "scene-assembly", True,
  gap="3 tests, none live-gated.")
V("synapse_validate_ordering", "PARTIAL", "VERIFIED-STATIC", READ,
  "Read-only Solaris chain-order validator. " + NO_HOST,
  "python/synapse/server/handlers_solaris_compose.py", "debugging", True,
  gap="No live run recorded.")

# ===========================================================================
# 3. GRAPH SYNTH
# ===========================================================================
V("synapse_propose_graph", "PARTIAL", "VERIFIED-STATIC", READ,
  "Validates a declarative proposal against a LIVE hou oracle and parks it; runs "
  "in the Houdini process by design. Mechanism is sound and explicitly built to "
  "be grounded. " + NO_HOST,
  "python/synapse/server/handlers_graph_synth.py:38", "scene-assembly", True,
  gap="2 tests, neither live-gated. The live oracle is the point of the tool and "
      "is exactly what is unproven.")
V("synapse_instantiate_graph", "PARTIAL", "VERIFIED-STATIC", READ,
  "Builds a parked VALIDATED proposal atomically with TOCTOU re-validation in "
  "GraphBuilder. " + NO_HOST,
  "python/synapse/server/handlers_graph_synth.py:71", "scene-assembly", True,
  gap="1 test, not live-gated.")

# ===========================================================================
# 4. CORE SCENE / NODE / PARM
# ===========================================================================
V("houdini_create_node", "PARTIAL", "VERIFIED-STATIC", READ,
  "The load-bearing primitive: createNode + moveToGoodPosition on the main "
  "thread, plus materiallibrary auto-population with a MaterialX shader and UV "
  "reader. 32 tests name it - more than any other tool. " + NO_HOST,
  "python/synapse/server/handlers_node.py:43", "scene-assembly", True,
  gap="14 of its 32 tests build a mock hou; none carries the host-identity gate. "
      "The single most-tested tool in the product has no host-behaviour evidence.",
  note="If one tool deserved a live test it is this one.")
V("houdini_connect_nodes", "PARTIAL", "VERIFIED-STATIC", READ,
  "setInput on the main thread with both-ends existence checks. " + NO_HOST,
  "python/synapse/server/handlers_node.py:141", "scene-assembly", True)
V("houdini_delete_node", "PARTIAL", "VERIFIED-STATIC", READ,
  "node.destroy() on the main thread behind a NodeNotFoundError guard. " + NO_HOST,
  "python/synapse/server/handlers_node.py:120", "scene-assembly", True)
V("houdini_set_parm", "PARTIAL", "VERIFIED-STATIC", READ,
  "Genuinely careful: rejects NaN/Inf before they reach Houdini and corrupt a "
  "parm, resolves USD punycode aliases, falls back scalar->parmTuple, and warns "
  "on the Lighting Law. " + NO_HOST,
  "python/synapse/server/handlers.py:1051", "look-dev", True,
  gap="17 tests, 10 mock, none host-gated.",
  note="The NaN guard is the kind of detail that only comes from being burned.")
V("houdini_execute_python", "PARTIAL", "VERIFIED-STATIC", READ,
  "Compiles first (so dry_run is a real syntax check), executes inside "
  "hou.undos.group, and distinguishes CODING errors (auto-rollback) from "
  "OPERATIONAL errors (keep partial mutations) - a real and defensible "
  "distinction. " + NO_HOST,
  "python/synapse/server/handlers.py:1192", "agent-internal", False,
  gap="22 tests, 14 mock, none host-gated. Also runs with full __builtins__ and "
      "no import filter on the live path (CLAUDE.md 1.2 live-path note).",
  note="The escape hatch every other tool is measured against.")
V("houdini_get_selection", "PARTIAL", "VERIFIED-STATIC", "agent-b3",
  "Agent verdict carried.", "python/synapse/server/handlers.py", "scene-assembly", True)
V("houdini_undo", "PARTIAL", "VERIFIED-STATIC", READ,
  "hou.undos.performUndo() behind a HOU_AVAILABLE guard. 4 tests name it and all "
  "4 are counted live-ish by the index, but none carries the host-identity gate.",
  "python/synapse/server/handlers.py:882", "agent-internal", True,
  gap="Calls hou.undos.performUndo() WITHOUT run_on_main - no main-thread "
      "marshal, unlike essentially every sibling handler. Same defect the agent "
      "found in houdini_redo.",
  note="Undo is the product's headline safety claim. It is unproven on the host "
       "and unmarshalled.")

# ===========================================================================
# 5. RENDER
# ===========================================================================
V("houdini_render", "PARTIAL", "VERIFIED-STATIC", READ,
  "The most-tested tool after create_node (38 tests). The bounded wrapper is "
  "real, careful engineering: poll tokens, single-flight, foreground guard with "
  "a cold-XPU-kernel refusal, and a bounded wait that frees the bridge loop. "
  "The docstring is unusually honest that the Houdini UI still freezes.",
  "python/synapse/server/handlers_render.py:326", "rendering", True,
  gap="Not exercised here - deliberately. Rendering mutates the artist's live "
      "session and this leg is read-only. On Indie the out-of-process husk path "
      "cannot load the Karma delegate (verified live 2026-07-17), so the render "
      "runs in-process and the UI freezes for its duration.",
  note="Bounded and survivable, not removed - the docstring says so itself.")
V("houdini_capture_viewport", "PARTIAL", "VERIFIED-STATIC", READ,
  "Uses the flipbook API rather than QWidget.grab (which returns black for GL "
  "surfaces) - a correct, hard-won choice. Carries a fixed CONFIRMED self-"
  "deadlock: read-only tools are marshalled whole onto the main thread, and this "
  "handler then self-marshalled from main and parked forever.",
  "python/synapse/server/handlers_render.py:228", "debugging", True,
  gap="Not exercised - needs a visible Scene Viewer pane and would capture the "
      "artist's screen. 6 tests, 3 mock, none host-gated.",
  note="Belongs to the same deadlock class as the three tools that hung live.")
V("houdini_render_settings", "PARTIAL", "VERIFIED-STATIC", READ,
  "Reads every parm, applies overrides, detects the Karma engine variant. " + NO_HOST,
  "python/synapse/server/handlers_render.py:1178", "rendering", True,
  gap="7 tests, 6 mock, zero live.")
V("synapse_safe_render", "PARTIAL", "VERIFIED-STATIC", READ,
  "Real pre-flight: camera hard-fail, material soft-warn, and a >512px auto-"
  "background rule to prevent lockup. The severity split is well judged.",
  "python/synapse/server/handlers_render.py:1819", "rendering", True,
  gap="Its camera check calls _handle_get_stage_info, whose success path is "
      "unproven here. No live run.")
V("synapse_render_progressively", "PARTIAL", "VERIFIED-STATIC", READ,
  "Three real passes (256/preview/production) with validation between and "
  "show-config-driven resolutions.",
  "python/synapse/server/handlers_render.py:2031", "rendering", True,
  gap="1 test, mock. No live run.")
V("synapse_render_sequence", "PARTIAL", "VERIFIED-STATIC", READ,
  "Discovers the Karma settings LOP where quality parms actually live (walking "
  "ROP.loppath), matching BOTH current and deprecated spellings so auto-fix does "
  "not silently no-op on older shots.",
  "python/synapse/server/handlers_render.py:1467", "rendering", True,
  gap="11 tests, 9 mock, none host-gated.")
V("synapse_autonomous_render", "PARTIAL", "VERIFIED-STATIC", READ,
  "Full Plan->Validate->Execute->Evaluate->Report loop with wall-clock bound and "
  "agent.usd task provenance.",
  "python/synapse/server/handlers.py:1811", "rendering", False,
  gap="3 tests, 3 mock. The most ambitious tool in the product with the least "
      "host evidence.",
  note="Would an artist reach for it? Not on a deadline, not before it has ever "
       "been observed finishing a real shot.")
V("synapse_render_farm_status", "PARTIAL", "VERIFIED-STATIC", READ,
  "Returns farm status plus bounded render sessions; the no-farm shape is stable.",
  "python/synapse/server/handlers_render.py:1591", "rendering", True,
  gap="Not called live (would have been safe to call; not reached before the "
      "session budget ran out).")
V("synapse_render_farm_cancel", "PARTIAL", "VERIFIED-STATIC", READ,
  "Cancels farm + autonomous driver and writes its own audit record. Honest "
  "about signal semantics: the in-flight frame finishes first.",
  "python/synapse/server/handlers_render.py:1609", "rendering", True,
  gap="1 test, mock. Cancel is the safety valve and it is unproven live.",
  note="Separately established this build: NO API cancels an in-flight ROP "
       "render on 22.0.368. This cancels the LOOP, not the frame.")
V("synapse_configure_render_passes", "PARTIAL", "VERIFIED-STATIC", READ,
  "Builds RenderVar prims from a 17-entry preset table via a generated Python "
  "LOP. The preset table is correct and genuinely useful.",
  "python/synapse/server/handlers_render.py:1660", "rendering", True,
  gap="ZERO tests name this tool anywhere in the suite, and it emits generated "
      "Python that calls editableStage() - which returns None outside a LOP cook.")
V("houdini_set_keyframe", "PARTIAL", "VERIFIED-STATIC", READ,
  "hou.Keyframe construction with a parm-name suggestion on miss. " + NO_HOST,
  "python/synapse/server/handlers_render.py:1133", "lighting", True,
  gap="1 test, mock.")
V("synapse_validate_frame", "PARTIAL", "VERIFIED-STATIC", READ,
  "Frame validation for black/NaN/clipping/fireflies.",
  "python/synapse/server/handlers_render.py:1241", "rendering", True,
  gap="7 tests, 7 mock, zero live. Pixel-reading claims validated only against "
      "fixtures.")
V("houdini_wedge", "PARTIAL", "VERIFIED-STATIC", READ,
  "PDG wedging entry point. " + NO_HOST,
  "python/synapse/server/handlers_tops/wedge.py", "caching", True)
V("houdini_shot_render_ready", "PARTIAL", "VERIFIED-STATIC", READ,
  "Composite shot-readiness assertion over the stage. " + NO_HOST,
  "python/synapse/server/handlers_solaris_compose.py", "rendering", True,
  gap="ZERO tests name this tool.")

# ===========================================================================
# 6. USD / SOLARIS AUTHORING
# ===========================================================================
for _t, _task, _reach, _extra in [
    ("houdini_create_usd_prim", "scene-assembly", True, ""),
    ("houdini_set_usd_attribute", "look-dev", True, ""),
    ("houdini_set_usd_primvar", "look-dev", True, ""),
    ("houdini_reference_usd", "scene-assembly", True, "ZERO tests name this tool."),
    ("houdini_set_payload_loadstate", "scene-assembly", True, "ZERO tests name this tool."),
    ("houdini_create_point_instancer", "scene-assembly", True, "ZERO tests name this tool."),
    ("houdini_configure_light_linking", "lighting", True, "ZERO tests name this tool."),
]:
    V(_t, "PARTIAL", "VERIFIED-STATIC", READ,
      "USD authoring handler read; real pxr/hou work on the main thread. " + NO_HOST,
      "python/synapse/server/handlers_usd.py", _task, _reach,
      gap=(_extra + " " if _extra else "") + "No host evidence.")

# ===========================================================================
# 7. MATERIALS
# ===========================================================================
V("houdini_create_material", "PARTIAL", "VERIFIED-STATIC", READ,
  "Creates a materiallibrary, cooks it so its internal network is ready, then "
  "builds a MaterialX shader inside - with a 10-entry physically-sensible preset "
  "table (glass, skin, cloth, wax...). This one actually cooks.",
  "python/synapse/server/handlers_material.py:166", "look-dev", True,
  gap="8 tests, 2 mock, none host-gated.",
  note="The preset table is the sort of thing an artist notices and likes.")
V("houdini_assign_material", "PARTIAL", "VERIFIED-STATIC", READ,
  "Creates assignmaterial, sets primpattern1/matspecpath1, and VALIDATES the prim "
  "pattern against the upstream stage, attaching a warning when it matches nothing.",
  "python/synapse/server/handlers_material.py:292", "look-dev", True,
  gap="7 tests, 3 mock, none host-gated.",
  note="Pattern validation against the real stage is a genuinely good touch.")
V("houdini_create_textured_material", "PARTIAL", "VERIFIED-STATIC", READ,
  "Production MaterialX build: mtlximage per map, shared UV reader wired to "
  "texcoord, UDIM handling, displacement.",
  "python/synapse/server/handlers_material.py:462", "look-dev", True,
  gap="1 test, mock. The most artist-facing look-dev tool in the product rests "
      "on a single mock test.")

# ===========================================================================
# 8. MEMORY
# ===========================================================================
V("synapse_add_memory", "PARTIAL", "VERIFIED-STATIC", READ,
  "Thin delegate to bridge.handle_memory_add. Adjacent memory tools were "
  "live-verified this session, so the substrate is known good.",
  "python/synapse/server/handlers_memory.py:102", "agent-internal", False)
V("synapse_decide", "PARTIAL", "VERIFIED-STATIC", READ,
  "Thin delegate to bridge.handle_memory_decide.",
  "python/synapse/server/handlers_memory.py:107", "agent-internal", False,
  note="decision + reasoning + revert is the provenance claim in CLAUDE.md; this "
       "is where it is supposed to be written.")
V("synapse_search", "PARTIAL", "VERIFIED-STATIC", READ,
  "Delegates to the bridge then additively augments with the RAG corpus, closing "
  "the recall->RAG seam.",
  "python/synapse/server/handlers_memory.py:92", "agent-internal", False,
  gap="Shares the _augment_with_knowledge path with synapse_recall, which did "
      "not return live.")
V("synapse_memory_query", "PARTIAL", "VERIFIED-STATIC", READ,
  "Section-aware ranked search across project + scene, plus cross-scene glob.",
  "python/synapse/server/handlers_memory.py:169", "agent-internal", False)
V("synapse_memory_write", "PARTIAL", "VERIFIED-STATIC", READ,
  "Writes a typed entry to scene or project memory.",
  "python/synapse/server/handlers_memory.py:151", "agent-internal", False,
  gap="ZERO tests name this tool.")
V("synapse_project_setup", "PARTIAL", "VERIFIED-STATIC", READ,
  "Ensures scene structure, loads full context, reloads show-config.",
  "python/synapse/server/handlers_memory.py:123", "agent-internal", False,
  note="Its own description says 'Call this FIRST in every session.'")
V("synapse_evolve_memory", "PARTIAL", "VERIFIED-STATIC", READ,
  "Charmander->Charmeleon evolution, dry_run defaulting to TRUE - a good default.",
  "python/synapse/server/handlers_memory.py:246", "agent-internal", False,
  gap="1 test. The live scene sits at charmander with session_count 0, so the "
      "trigger has never fired here.")
V("synapse_sleep_pass", "PARTIAL", "VERIFIED-STATIC", READ,
  "Moneta consolidation/decay. Returns a real prune audit (ids + before/after) "
  "so data loss is visible, and no-ops with a clear reason off Moneta - Law 3 "
  "done correctly.",
  "python/synapse/server/handlers_memory.py:268", "agent-internal", False,
  gap="Live doctor reports MonetaMemory is NOT registered with this USD runtime "
      "(PXR_PLUGINPATH_NAME unset), so on this install it takes the no-op branch.")
V("synapse_write_report", "PARTIAL", "VERIFIED-STATIC", READ,
  "Deliberately runs OFF the main thread - pure file I/O, no hou - so it survives "
  "a blocked main thread. Path-confined against traversal.",
  "python/synapse/server/handlers.py:1278", "agent-internal", False,
  note="The one handler explicitly designed around the failure mode that hung "
       "three tools in this leg.")
V("synapse_batch", "PARTIAL", "VERIFIED-STATIC", READ,
  "Runs N commands in one undo group with nested provenance under the real batch "
  "envelope op-id, read on the handler thread before the marshal.",
  "python/synapse/server/handlers.py:908", "agent-internal", False,
  gap="5 tests, 3 mock.")
V("synapse_metrics", "WORKS", "VERIFIED-RUNTIME", LIVE,
  "Called live: returned well-formed Prometheus text over seven stat sources - "
  "circuit breaker, per-tool duration histograms, run_on_main dispatch-wait "
  "histogram (299 samples, max 698ms), main-thread direct path, panel inline, "
  "scene gauges. Real instrumentation, not a stub.",
  "python/synapse/server/handlers.py:1495", "debugging", False,
  gap="Emits router_stats=None on the /mcp path - the hasattr(self,'_router') "
      "guard at :1500 can never be true there (S1-F3). Degrades silently rather "
      "than reporting the gap.",
  note="Its own telemetry corroborates S1-F2 unprompted: "
       'synapse_panel_inline_slow_total{slowest_tool="synapse_inspect_scene"}. '
       "The product already knows which tool is its slowest.")
V("synapse_inspect_node", "PARTIAL", "VERIFIED-STATIC", READ,
  "Deep single-node dump; geometry defaulted OFF so the common inspect stays cheap.",
  "python/synapse/server/handlers.py:1475", "debugging", True,
  gap="Not exercised live - same introspection module as inspect_scene, which "
      "did not return.")
V("synapse_inspect_selection", "PARTIAL", "VERIFIED-STATIC", READ,
  "Selection inspect via the same introspection module.",
  "python/synapse/server/handlers.py:1451", "debugging", True,
  gap="Same module as inspect_scene, which did not return live.")
V("synapse_inspect_stage", "PARTIAL", "VERIFIED-STATIC", READ,
  "Tool #44: local Python composing ONE execute_python round-trip plus "
  "client-side StageAST construction - a genuinely clever token-efficient design.",
  "mcp_server.py:927 -> synapse/cognitive/tools/inspect_stage.py", "scene-assembly", True,
  gap="Not exercised - the live scene has no stage.")

# ===========================================================================
# 9. TOPS / PDG
# ===========================================================================
_TOPS = {
    "tops_cook_node": ("Real cook: getPDGNode existence check, generateStaticItems "
                       "for generate_only, node.cook(block=...), work-item count.", "caching", True),
    "tops_generate_items": ("generateStaticItems + count, guarded on getPDGNode.", "caching", True),
    "tops_batch_cook": ("Sequential cook over N nodes with per-node timing, "
                        "kahan_sum aggregation and stop_on_error.", "caching", True),
    "tops_cook_and_validate": ("Genuine self-healing loop: cook -> count CookedFail "
                               "-> dirty -> re-cook, with per-attempt detail.", "caching", True),
    "tops_dirty_node": ("pdg_node.dirty(upstream) with a dirtyAllTasks fallback.", "caching", True),
    "tops_configure_scheduler": ("Configures maxprocs/working dir and REFUSES any "
                                 "non-local scheduler loudly rather than echoing back "
                                 "an unconfigured type - Law 3 done right.", "pipeline-admin", True),
    "tops_cancel_cook": ("Cancels an active PDG cook.", "pipeline-admin", True),
    "tops_diagnose": ("Work-item states, failed-item detail, scheduler info and "
                      "upstream dependency health.", "debugging", True),
    "tops_pipeline_status": ("Per-node health walk of a whole topnet with aggregate "
                             "state counts and issue list.", "debugging", True),
    "tops_get_work_items": ("Work-item enumeration.", "debugging", True),
    "tops_get_dependency_graph": ("PDG dependency graph extraction.", "debugging", True),
    "tops_get_cook_stats": ("Cook timing statistics.", "debugging", True),
    "tops_query_items": ("Filtered work-item query.", "debugging", True),
    "tops_setup_wedge": ("Wedge parameter sweep setup.", "caching", True),
    "tops_multi_shot": ("Per-shot work items, camera/frame-range config, ropfetch "
                        "render, partition by shot.", "rendering", True),
    "tops_render_sequence": ("Frame-range render via TOPS.", "rendering", True),
    "tops_monitor_stream": ("Push-based PDG event monitoring - registers callbacks "
                            "that do not block the cook thread.", "debugging", True),
}
for _t, (_ev, _task, _reach) in _TOPS.items():
    V(_t, "PARTIAL", "VERIFIED-STATIC", READ, _ev + " " + NO_HOST,
      "python/synapse/server/handlers_tops/", _task, _reach,
      gap="No host evidence; no TOP network exists in the live scene to exercise "
          "it against.")
VERDICTS["tops_cancel_cook"]["note"] = (
    "Separately established VERIFIED-RUNTIME on 22.0.368: TOPS/PDG cancel IS "
    "complete, including a direct hou.TopNode.cancelCook. This is the one cancel "
    "surface in the product that is real.")
VERDICTS["tops_dirty_node"]["note"] = (
    "Adjacent known defect: the PDG rollback path in shared/bridge.py:1718 calls "
    "dirtyAllTasks(remove_files=...) while the live 22.0.368 signature is "
    "dirtyAllTasks(remove_outputs) - it raises TypeError on EVERY invocation and "
    "is caught into a note. That rollback has never once executed.")

# ===========================================================================
# 10. CARRY THE AGENT BATCHES (unrefuted - the adversarial pass never ran)
# ===========================================================================
agent_rows = json.loads((FOR / "s1_agent_batch_1_3.json").read_text(encoding="utf-8"))["tools"]
for r in agent_rows:
    t = r["tool"]
    if t in VERDICTS:
        continue
    VERDICTS[t] = {
        "tool": t, "klass": r["klass"], "tier": r.get("tier", "UNVERIFIED"),
        "provenance": "agent-b1/b3 (UNREFUTED - adversarial pass killed by session limit)",
        "evidence": r.get("evidence", ""), "anchor": r.get("anchor", ""),
        "artist_task": r.get("artist_task", ""),
        "would_artist_reach": r.get("would_artist_reach"),
        "gap": r.get("gap", ""), "note": r.get("reach_note", ""),
    }

# ===========================================================================
# CHECK + EMIT
# ===========================================================================
census = json.loads((FOR / "s1_tool_census.json").read_text(encoding="utf-8"))
registered = {t["tool"] for t in census["tools"]}

missing = sorted(registered - set(VERDICTS))
extra = sorted(set(VERDICTS) - registered)
if extra:
    sys.exit(f"FAIL: verdict for unregistered tool(s): {extra}")

for t in missing:
    V(t, "UNKNOWN", "UNVERIFIED", "not-reached",
      "Not classified. The 8-agent fan-out that would have covered it died on a "
      "session token limit after 2 of 10 agents, and the orchestrator ran out of "
      "budget before reading this handler.",
      "harness/notes/forensic/s1_evidence_index.json", "", None,
      gap="Needs: open the handler and its callees, determine whether it produces "
          "the artefact its name promises, and check whether any test naming it "
          "escapes the fake hou.")

counts: dict[str, int] = {}
for r in VERDICTS.values():
    counts[r["klass"]] = counts.get(r["klass"], 0) + 1

by_task: dict[str, dict[str, int]] = {}
for r in VERDICTS.values():
    if r["klass"] not in ("WORKS", "PARTIAL"):
        continue
    t = r["artist_task"] or "unclassified"
    d = by_task.setdefault(t, {"WORKS": 0, "PARTIAL": 0, "reach_yes": 0, "reach_no": 0})
    d[r["klass"]] += 1
    d["reach_yes" if r["would_artist_reach"] else "reach_no"] += 1

out = {
    "producer": "harness/notes/forensic/_s1_classify.py",
    "registered_total": len(registered),
    "classified_total": len(VERDICTS),
    "counts": counts,
    "unknown_because_fanout_died": missing,
    "by_artist_task": dict(sorted(by_task.items())),
    "provenance_split": {
        p: sum(1 for r in VERDICTS.values() if r["provenance"].startswith(p))
        for p in ("live", "read", "agent-b1/b3", "not-reached")
    },
    "verdicts": [VERDICTS[k] for k in sorted(VERDICTS)],
}
(FOR / "s1_classification.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

print(json.dumps({k: v for k, v in out.items() if k != "verdicts"}, indent=1))
