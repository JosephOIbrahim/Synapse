# author_bp7.py - CTO seat (Fable 5.1), 2026-09-20. Wave BP7 = SCOUT: why chat stalls after turn 1.
# Four read-only scouts (one per Jev-ranked hypothesis, harness/jev/ledger/bp7.ranking.json) + SYNTH.
# Every leg is tier:auto (JEV-ROUTE decides). SYNTH consumes the JEV-SCREEN pre-read of the scout
# receipts (it runs jev_screen itself, since compile happens before receipts exist). Same shape as
# author_bp4.py. ARM is Joe's word (given 2026-09-20 09:44: "create a scouting team ... use the harness").
import json, subprocess, sys
from pathlib import Path

AF = Path(r"C:\Users\User\SYNAPSE\harness\battleplan")
SRC = "harness/battleplan/notes/SCOUT_CHAT_STALL.md"
RANK = json.loads((AF.parents[1] / "harness/jev/ledger/bp7.ranking.json").read_text(encoding="utf-8"))
SPAWN = {h["id"]: h for h in RANK if h["spawn"]}

FENCE = ("Permission fence: scoped `git add` + `git commit` only; push/merge/checkout/reset denied; use "
         "`cd <path> && git status --short`, never `git -C`. Commit the note BEFORE the receipt; the receipt is your final write. "
         "Self-cap: 10 turns (progress every 3). You are a SCOUT: read-only on product code, you gather evidence and write ONE "
         "note; you fix nothing. Verdict vocabulary: CONFIRMED (you reproduced or traced the mechanism to a line), REFUTED "
         "(you showed the mechanism cannot occur, with the line), UNKNOWN (needs the GUI / a live Houdini you do not have - say "
         "exactly what Joe should click). Never upgrade UNKNOWN to a guess. Token-saver: Select-String / grep for symbols, read "
         "40-line windows, never whole files. Houdini is NOT available to you; hython is at the SYNAPSE_HYTHON pin only if "
         "harness/state/drop.json names it - otherwise everything runtime is UNKNOWN.")

def scout(tag, hid, name, note, targets, touches):
    h = SPAWN[hid]
    return {
        "id": f"BP7-{tag}", "band": "TRUTH", "class": "truth", "tier": "auto",
        "name": f"SCOUT {hid} {h['name']}: {name}",
        "note": f"Hypothesis {hid} ({h['name']}), Jev plausibility {h['score']:.2f}. Mechanism under test: {h['text']} "
                f"Read {SRC} first (sec. First principles + Evidence). {note} {FENCE}",
        "targets": targets + [
            f"T-last) harness/battleplan/notes/bp7_scout_{hid}.md: header line `VERDICT: CONFIRMED|REFUTED|UNKNOWN`, then "
            "Mechanism (2-4 sentences), Evidence (file:line per claim, verbatim snippets <= 6 lines each), Reproduction "
            "(exact steps Joe runs in the Houdini GUI, < 2 minutes, with the observable that distinguishes this hypothesis "
            "from the others), Smallest fix shape (one paragraph, no code). Post one bus finding to *: "
            f"{{\"claim\": \"{hid} <VERDICT>: <one line>\", \"anchor\": \"harness/battleplan/notes/bp7_scout_{hid}.md\"}}."],
        "touches": touches + [f"harness/battleplan/notes/bp7_scout_{hid}.md"],
        "readonly": False, "deps": [],
        "crucible_criteria": ["every Evidence line greps verbatim at the cited file:line",
                              "the verdict word matches the evidence (a CONFIRMED with no reproduction or traced line is BROKEN)",
                              "no product file changed (git diff --stat master -- panel python/synapse == empty)"],
        "spawn_classes": [], "source": {"doc": SRC, "anchor": f"Hypotheses {hid}"},
        "acceptance": [
            {"predicate": "note exists with a VERDICT header and all four sections", "evidence": "check"},
            {"predicate": "every cited file:line exists and contains the quoted snippet", "evidence": "check"},
            {"predicate": "bus finding posted with the verdict", "evidence": "receipt"},
        ],
    }

M = []
if "H1" in SPAWN:
    M.append(scout("PANEL", "H1", "does the panel stay in a waiting state after turn 1",
        "Trace python/synapse/panel/chat_panel.py: _send_message sets _waiting_for_response + show_typing_indicator; find EVERY "
        "path that clears them (grep _waiting_for_response, hide_typing_indicator). Trace ws_bridge.py: how a server reply is "
        "matched to the route_chat request (command name? request id? signal?) and what happens to a reply whose command name "
        "differs or whose status is error. Check the consent/proposal card flow (tests/panel/test_consent_way_back.py names it): "
        "can a card left unsettled block or swallow the next reply? Run `python -m pytest tests/test_chat_panel.py tests/test_send_guard.py -q` "
        "and note any test that pins a second-turn path.",
        ["T1) A table of every writer of _waiting_for_response / typing indicator with file:line and the condition.",
         "T2) The reply-matching mechanism in ws_bridge.py, quoted, and whether a second route_chat reply can be dropped or mis-routed.",
         "T3) Whether an unsettled proposal/consent card changes the send or receive path (file:line or 'no such coupling')."],
        []))
if "H4" in SPAWN:
    M.append(scout("ROUTER", "H4", "does the cached TieredRouter carry state that blocks or raises on turn 2",
        "Trace python/synapse/routing/router.py TieredRouter.route(): every attribute written during a call that survives to "
        "the next call (cache, planner state, LLM client, conversation/history). Find the timeout on the LLM tier and on the "
        "live path (30 s slow-op, harness/CLAUDE.md Identity): what does the SERVER return when route() exceeds it, and does "
        "chat_panel._on_response render that error or filter it? Confirm resolve_param(payload, 'content') maps the panel's "
        "'message' key (python/synapse/core/aliases.py). Run `python -m pytest tests/test_router_internals.py -q`.",
        ["T1) Cross-call state table for TieredRouter: attribute, file:line written, file:line read next turn, can it block/raise.",
         "T2) The timeout path: server-side handler/timeout file:line, the response shape on timeout, and what the panel does with it.",
         "T3) resolve_param('content') vs payload 'message': mapped or not, with the aliases.py line."],
        []))
if "H2" in SPAWN:
    M.append(scout("TRANSPORT", "H2", "does the WS socket drop after the first reply and stay down",
        "Trace python/synapse/panel/ws_bridge.py: the reconnect loop, what sets `connected` False, what sets it True again, and "
        "whether a server-side close (after a slow op, after a large reply, on an exception in the handler) is detected and "
        "recovered. Trace the server side: python/synapse/server/*.py websocket send path - any per-message size limit, any "
        "close-on-error. Then answer: after a drop, does FR-1 (send_guard) refuse with BRIDGE_DOWN_LINE, and would the artist "
        "SEE that line (chat_panel appends it as a system message - confirm the widget shows system messages). Run "
        "`python -m pytest tests/test_hda_panel.py tests/test_send_guard.py -q`.",
        ["T1) State machine of `connected` in ws_bridge.py: every transition with file:line.",
         "T2) Server-side close conditions on the /synapse path with file:line, and whether the client reconnect covers each.",
         "T3) Whether BRIDGE_DOWN_LINE is visibly rendered (widget + file:line) - if not, the artist experiences silence."],
        []))
if "H6" in SPAWN:
    M.append(scout("MEMORY", "H6", "does a degraded memory store block or raise inside turn 2",
        "Trace python/synapse/server/handlers.py _repoint_router_memory and _memory_owner; then the memory tier inside "
        "TieredRouter.route() (KnowledgeIndex._match_memory, enrich_context): which calls WRITE to the store during a chat "
        "turn, which can block (locks, file I/O, health()), and what happens when MemoryStore.health() reports not-writing or "
        "UNKNOWN (ae34ed96, 5.75.2). Is any exception from the memory tier caught, or does it escape route()? Run "
        "`python -m pytest tests/test_demo_memory_recall.py -q` and any test named for the store health.",
        ["T1) Every store call reachable from _handle_route_chat, file:line, read/write, blocking or not.",
         "T2) The degraded-store behaviour: what health() returns and what each caller does with it, file:line.",
         "T3) Exception path: caught where, or escapes to the handler (and then what the panel receives)."],
        []))

M.append({
    "id": "BP7-SYNTH", "band": "BUILD", "class": "build", "tier": "auto",
    "name": "SYNTH: read the four scout receipts through the JEV screen pre-read and write the verdict on why chat stalls after turn 1",
    "note": f"Read {SRC} (Verdict shape). FIRST run `python harness/jev/jev_screen.py --wave bp7` and read the brief lines it prints: "
            "CLEAR scouts you spot-check, REFEREE/FLAG scouts you re-derive from their cited lines yourself. Then read each "
            "harness/battleplan/notes/bp7_scout_H*.md. Do not re-scout; you may open a cited file:line to confirm a quote. "
            "Where two scouts disagree, the one with a traced line wins over the one with an argument. " + FENCE.replace("You are a SCOUT: read-only on product code, you gather evidence and write ONE note; you fix nothing. ", "You write ONE document; you fix nothing. "),
    "targets": [
        "T1) harness/battleplan/notes/BP7_VERDICT.md: one paragraph per hypothesis (H1 H2 H4 H6, plus H3/H5 as 'not scouted: Jev-refuted/unranked' with the ranking numbers from harness/jev/ledger/bp7.ranking.json), each headed CONFIRMED/REFUTED/UNKNOWN with the scout's anchor; then `## Most likely cause` (one), `## Reproduce in the GUI` (numbered, < 2 min, the observable per step), `## Smallest fix` (one paragraph, which file, no code), `## What only Joe can observe` (the UNKNOWNs, as clicks).",
        "T2) Section `## Screen pre-read` quoting the jev_screen brief lines verbatim and, per scout, whether your read agreed.",
        "T3) Post one bus finding to *: {\"claim\": \"BP7 verdict: <most likely cause, one line>\", \"anchor\": \"harness/battleplan/notes/BP7_VERDICT.md\"}. Commit the note, then the receipt.",
    ],
    "touches": ["harness/battleplan/notes/BP7_VERDICT.md"],
    "readonly": False, "deps": [m["id"] for m in M],
    "crucible_criteria": ["every hypothesis paragraph's verdict word matches its scout note's VERDICT header",
                          "the Most likely cause is one of the CONFIRMED hypotheses, or the doc says none was confirmed",
                          "no product file changed"],
    "spawn_classes": [], "source": {"doc": SRC, "anchor": "Verdict shape (SYNTH)"},
    "acceptance": [
        {"predicate": "BP7_VERDICT.md has the five sections and one paragraph per hypothesis", "evidence": "check"},
        {"predicate": "Screen pre-read section quotes bp7 screen lines", "evidence": "check"},
        {"predicate": "bus finding posted with the one-line cause", "evidence": "receipt"},
    ],
})

(AF / "missions").mkdir(exist_ok=True)
for m in M:
    (AF / "missions" / f"{m['id']}.json").write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", m["id"], "tier", m["tier"], "deps", m["deps"])
print("--", len(M), "missions; next: python compile_wave.py bp7 ; python make_control.py bp7")
