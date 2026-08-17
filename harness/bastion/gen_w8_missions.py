# gen_w8_missions.py - BASTION Wave 0 (W8) mission generator + validator.
# Run from repo root: python harness/bastion/gen_w8_missions.py
# Emits harness/autorevise/missions/w8b_<tag>.json then validates each via
# mission_schema.validate_mission. House rule: missions are built by Python,
# never hand-JSON in PowerShell (BOM + value/Count array mangling).
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AR = ROOT / "harness" / "autorevise"
sys.path.insert(0, str(AR))
from mission_schema import validate_mission

DOC = "harness/bastion/PROGRAM.md"
OUT = AR / "missions"

TOKEN = ("TOKEN DISCIPLINE: read anchors not trees; externalize evidence to "
         "your receipt early; cite file:line anchors, never file dumps.")
BUS = ("BUS MANDATE - this team exists to talk: post claim at start, post "
      "each finding to the bus AS IT LANDS addressed to W8-LIBR (do not "
      "batch), explicit RELEASE at close.")
CRUC = ["evidence first-hand from your own read-only recon, never inherited",
        "unobtainable renders UNKNOWN, never zero, never estimate"]

SCOUTS = [
 ("SLIFE", "B1-LIFECYCLE", "lifecycle scout: runtime/session lifetime vs UI, undo, threads, recovery",
  "1) Map every object whose lifetime is parented to a UI surface (panel, shelf, ROP dialogs): heartbeat, session, timers, Qt signal owners. SESSCOPE (v5.51.0) changed the panel story - verify what it actually covers and what it does not. 2) Undo contract: enumerate node-creating paths and mark each covered/uncovered by the one-Ctrl+Z contract (g7 receipt is the seed, not the ceiling). 3) Qt thread discipline: trace main-thread marshaling (the _on_main class) - list every cross-thread touch. 4) Crash recovery: what survives a hard Houdini kill mid-build - observe, never assert."),
 ("STRUTH", "B2-TRUTH", "truth scout: stamping, catalogs, cook-verify, claim enforcement breadth",
  "1) Inventory every claim-producing surface (fidelity, cook results, status boards, SUPPORT_MATRIX rows) and mark each enforced-by-face_token / unenforced. 2) Stamp audit: find every artifact carrying a build stamp; list stale stamps (the H21-on-apex_probes class). 3) Catalog absence: document what a compiled per-build parameter-name catalog would gate that today goes ungated. 4) Cook-verify: list every place a cook result is claimed without measurement (lastCookTime headless 0.0 is the seed class)."),
 ("SENGINE", "B3-ENGINE", "engine scout: five-backend resilience, routing, offline, injection defense",
  "1) Map the five-backend abstraction: per-backend timeout, retry, failover, and error surface - observed from code, not docs. 2) Routing: cost/capability routing or hardcoded selection; what happens fully offline. 3) Injection defense: trace Sanitize-SQ coverage from NL input to node creation - list every entry point it does NOT wrap. 4) Key handling at the engine boundary: report location class only - never echo values."),
 ("SMEM", "B4-MEMORY", "memory scout: Moneta hardening, capsules, SQLite+FTS5 readiness",
  "1) Moneta: schema registration path, failure modes when env unset or registration fails mid-session, write-durability observations. 2) Capsule persistence: what survives restart; boot-scope semantics post-SESSCOPE. 3) SQLite+FTS5 readiness: enumerate the prereqs the old wave-6 plan assumed and their current truth. 4) Perf envelope: measure only what a readonly probe can measure; UNKNOWN the rest."),
 ("SSURF", "B5-SURFACE", "surface scout: install, first-run, UX debt, error language, operator docs",
  "1) Install path audit: packages json, prefs-dir resolution (OneDrive-redirect bug class), multi-build collision (five builds share one prefs dir, nothing pins the default). 2) First-run: what a fresh user hits before first success; error-language pass - list messages a non-builder cannot act on. 3) Panel/shelf/ROP UX debt: enumerate, do not fix. 4) Operator docs: what exists vs what an operator needs (Operator's Card gaps)."),
 ("SSHIELD", "B6-SHIELD", "shield scout: secrets, deps, telemetry, patents-pending repo hygiene",
  "1) Secrets: scan working tree AND git history for key/token/credential patterns - report locations + pattern class ONLY, never echo values, no history rewrite. 2) Dependency pinning: enumerate unpinned deps + supply-chain exposure. 3) Telemetry/privacy: what leaves the machine, where, opt-in state. 4) Public-repo hygiene vs patents-pending: flag files that disclose claim-relevant mechanisms - titles and paths only."),
 ("SSHIP", "B7-SHIP", "ship scout: g1-g9 automation map, version sync, matrix truth, CI, distribution",
  "1) g1-g9 map: per gate, automated / scripted-manual / pure-human today; cite the v5.51.0 ritual receipts. 2) VERSION-sync: is sync_version.py drift-detected anywhere or run on memory. 3) SUPPORT_MATRIX: per row, tested-in-CI / tested-once / asserted. 4) CI: what the 6587-test verify does NOT cover (GUI class, hython class); the distribution story for a non-builder."),
]

def scout(tag, anchor, name, scope):
    return {
        "id": "W8-" + tag, "band": "TRUTH", "name": name,
        "source": {"doc": DOC, "anchor": anchor},
        "targets": [scope,
            "5) Output: receipt harness/notes/receipts/W8-" + tag + ".json + findings ranked P0 (production-blocking) / P1 (hardening) / P2 (polish), each with a file:line anchor and first-hand observation or UNKNOWN.",
            TOKEN, BUS],
        "touches": [], "deps": [], "readonly": True,
        "crucible_criteria": CRUC, "spawn_classes": ["probe"],
        "acceptance": [
            {"predicate": "findings ranked P0/P1/P2 with file:line anchors, receipt committed on own branch", "evidence": "check"},
            {"predicate": "every claim traced to first-hand observation or named UNKNOWN", "evidence": "probe"}],
        "note": ""}

LIBR = {
    "id": "W8-LIBR", "band": "TRUTH",
    "name": "librarian SYNTHESIZER: one findings index from seven scout streams",
    "source": {"doc": DOC, "anchor": "W8-LIBRARIAN"},
    "targets": [
        "1) Consume the bus: scouts post findings addressed to you as they land - read ALL; a scout claim you cannot trace to its receipt anchor is treated as unproven.",
        "2) Dedup against prior art: existing receipts, standing rulings, and the W6 failure-class ledger - a finding already ruled or already gated is cited, not re-opened.",
        "3) Spot-check: re-observe at least one load-bearing P0 finding per scout first-hand - trust is verified, never inherited.",
        "4) Emit harness/bastion/FINDINGS_INDEX.md on your own branch: per finding - id, blueprint, rank, anchor, status (new/known/gated), one-line evidence. This index is the sole input the Chunk-C blueprints cite.",
        "5) Receipt harness/notes/receipts/W8-LIBR.json as your closing commit; RELEASE on the bus; drop flag harness/notes/h22/w8-landed.flag.",
        TOKEN],
    "touches": [], "deps": ["W8-" + t for t, _, _, _ in SCOUTS],
    "readonly": True,
    "crucible_criteria": CRUC + ["one first-hand spot-check per scout stream"],
    "spawn_classes": ["probe"],
    "acceptance": [
        {"predicate": "all scout findings consumed with per-claim trace-or-unproven status", "evidence": "check"},
        {"predicate": "one first-hand spot-check per scout, stdout in receipt", "evidence": "probe"},
        {"predicate": "FINDINGS_INDEX.md + receipt + flag landed as closing commit", "evidence": "check"}],
    "note": ""}

SMITH = {
    "id": "W8-SMITH", "band": "BUILD",
    "name": "smith: fork AUTOREVISE into BASTION harness v2 under harness/bastion/",
    "source": {"doc": DOC, "anchor": "HARNESS-V2-SMITH"},
    "targets": [
        "1) TASK 1 - resolve /rc: it is delivered by steward SendKeys and observed working across W6+W5 waves, but no rc.md exists under .claude (recursive) or the repo, and no doc mentions it. Interrogate: launch a scratch claude session in a worktree, capture /help and what typing '/rc' resolves to, document it. If unresolvable headless, escalate UNKNOWN with the transcript - never guess.",
        "2) Fork, do not rewrite: copy AUTOREVISE (mission_schema, compile_wave, make_control, bus, orchestrate pattern, arm template) into harness/bastion/, preserving every runner survival rule traced to its source file: hold-turn clause, CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0, AGENT_TEAMS env, detached Start-Process with pid capture, debom discipline.",
        "3) Schema v2: add optional skills[] (list of repo-relative or /mnt skill paths); compile injects them into the leg prompt brief. Add typed bus message kinds CLAIM/FINDING/HANDOFF/BLOCK/RELEASE with a validator on bus write.",
        "4) Arm template v2: steward arm/refresh with deadline past the wave horizon + /rc bake-in slot (fills from task 1 resolution).",
        "5) Self-test under stock pytest, pure Python, no hou: schema round-trip, compile of a fixture mission carrying skills[], bus kind validation. Skip is not pass.",
        "6) Receipt harness/notes/receipts/W8-SMITH.json; commit-before-receipt; your branch only.",
        TOKEN,
        "BUS MANDATE: post claim at start, post BLOCK immediately if /rc stays unresolved, explicit RELEASE at close."],
    "touches": ["harness/bastion/"], "deps": [], "readonly": False,
    "crucible_criteria": [
        "no phantom surface: every carried runner rule traced to its source file, never memory",
        "unobtainable renders UNKNOWN, never zero, never estimate"],
    "spawn_classes": ["probe"],
    "acceptance": [
        {"predicate": "v2 fork complete with skills[] + typed bus + steward-arm clause; pytest self-test green, skip is not pass", "evidence": "test"},
        {"predicate": "/rc resolved and documented, or UNKNOWN escalated with interrogation transcript", "evidence": "check"}],
    "note": "no W8 leg depends on smith; v2 serves the exec waves"}

def main():
    missions = [scout(*s) for s in SCOUTS] + [LIBR, SMITH]
    OUT.mkdir(parents=True, exist_ok=True)
    failures = 0
    for m in missions:
        path = OUT / ("w8b_" + m["id"].split("-")[1].lower() + ".json")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(m, f, indent=2)
            f.write("\n")
        errs = validate_mission(m)
        tag = "OK  " if not errs else "FAIL"
        print(f"{tag} {m['id']:<12} -> {path.name}")
        for e in errs:
            print("     " + e)
        failures += len(errs)
    print(f"\n{len(missions)} missions written, {failures} validation errors")
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(main())
