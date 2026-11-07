# author_bp10.py - CTO seat (Fable 5.1), 2026-09-21. Wave BP10 = HARVEST: execute the FXHOUDINIMCP
# Harvest spec (notes/HARVEST_SPEC.md) and the Jev Integration Blueprint (notes/JEV_HARVEST_BLUEPRINT.md).
# Graph: SCAFFOLD -> CORPUS -> GUIDES -> BENCH -> CRUX -> TIDY, fully SERIAL on purpose (Joe's rule: one
# mission over many parallel runners; the second cannot start until the first's gate is green anyway).
# Routing: the three builders are `tier: auto` + `team: auto` (JEV-ROUTE / JEV-TEAM at compile time,
# ledgered under harness/jev/ledger/bp10.*.jsonl). SCAFFOLD and TIDY are literal `mechanical` (Haiku);
# CRUX is literal `referee` (blueprint rule 1: TRUST+crucible never asks Jev). Effort is `max` in the
# manifest: `ultracode` is not a level Claude Code 2.1.278 lists (low|medium|high|xhigh|max), same call
# BP4 made on 2026-09-03. This script WRITES + VALIDATES missions only. Compile, manifest, ARM are separate;
# ARM is Joe's word.
import json, sys
from pathlib import Path

AF = Path(__file__).resolve().parent
sys.path.insert(0, str(AF))
import mission_schema as ms  # noqa: E402

SPEC = "harness/battleplan/notes/HARVEST_SPEC.md"
JEVBP = "harness/battleplan/notes/JEV_HARVEST_BLUEPRINT.md"
HYTHON = r"C:\Program Files\Side Effects Software\Houdini 22.0.400\bin\hython.exe"
UPSTREAM = "https://github.com/healkeiser/fxhoudinimcp"
PIN = "29b6695b6726b90537eab3f02411e05d7c6760a5"

FENCE = ("Permission fence: scoped `git add` + `git commit` only; push/merge/checkout/reset denied; use "
         "`cd <path> && git status --short`, never `git -C`. Commit code BEFORE the receipt; the receipt is your final write. "
         "Budget discipline: run /token-saver first and keep to it - Select-String / grep for symbols, read 40-line windows "
         "around cited lines, never whole files; the two source docs are your brief, read them ONCE in full at the start "
         "and then only grep them. Houdini GUI is NOT available to you: anything that needs a live panel is UNKNOWN, never "
         "a pass. hython IS available at `" + HYTHON + "` (22.0.400) for headless gates. Minimal diff: touch only the files "
         "in `touches`. House rule: no number enters a document without a producer path beside it. Every UNKNOWN stays "
         "UNKNOWN - never a pass, never a 0.")
STD_CRUX = [
    "the crucible trusts no builder's proved_it_bites - it authors its own mutations",
    "every verdict row carries the crucible's own anchor",
    "a leg with any UNKNOWN acceptance is at best SOUND-WITH-NITS, never SOUND",
    "the crucible flips no contract feature and edits no product file",
]
JEV_INV = ("Jev invariants (JEV_BLUEPRINT.md sec. 4 + adapter.py): questions are DATA in harness/jev/questions.json; "
           "code owns every decision; fail closed (no key / timeout -> the pre-Jev output, ledgered as fallback, no "
           "fabricated probability); every call ledgered under harness/jev/ledger/bp10.<guard>.jsonl; nothing under "
           "python/synapse/ imports harness/jev (pinned by tests/test_jev_product_boundary.py). A Jev answer never "
           "promotes a chunk, never names a model, never grants consent.")

M = [
    # ------------------------------------------------------------------ SCAFFOLD (mechanical)
    {
        "id": "BP10-SCAFFOLD", "band": "BUILD", "class": "build", "tier": "mechanical", "readonly": False, "deps": [],
        "name": "Harvest scaffold: vendor tree + attribution, ADR-0001, three Jev guard stubs, jev tests into CI",
        "note": "Tier: mechanical (Haiku 4.5) - this leg copies, stubs and wires; it designs nothing. Self-cap: 15 turns "
                "(progress every 5). " + FENCE + " Source pin: " + UPSTREAM + " @ " + PIN + " (MIT, 'Copyright (c) 2026 "
                "FXHoudini-MCP Contributors'). Shallow-clone it to a temp dir outside the repo; never add it as a submodule "
                "or a pip dependency. " + JEV_INV,
        "targets": [
            "T1) python/synapse/_vendor/fxhoudinimcp/: LICENSE byte-identical to upstream; NOTICE.md (upstream URL, commit "
            + PIN + ", harvest date 2026-09-21, the list of files taken, and the sentence 'the help-archive reader in "
            "rag/ingest/help_archive.py was written after reading help_handlers.py and follows its path conventions'); "
            "guides/ = the 31 files from python/fxhoudinimcp/prompts/markdown/workflows/*.md, UNMODIFIED (sha256 per file "
            "recorded in NOTICE.md).",
            "T2) docs/decisions/ADR-0001-jev-in-harvest.md (new dir): context, decision ('Jev sits beside the harvest gates on "
            "the residual, shadow-first, through the two existing doors, and never promotes a chunk'), the four sites, the "
            "refused sites (copy the Refusals list from JEV_HARVEST_BLUEPRINT.md verbatim), invariants inherited, "
            "consequences, producer paths. Link back to JEV_BLUEPRINT.md and docs/reviews/jev-opportunities-2026-09-20.md.",
            "T3) harness/jev/questions.json: add guards.harvest, guards.rerank, guards.bench with edge / state_fields / "
            "questions / policy EXACTLY as specified in JEV_HARVEST_BLUEPRINT.md sections Site 1-3 and 'Scaffolded documents' "
            "(the entry-shape example is the contract). Every threshold lives in `policy`; criteria carry what/not_for per "
            "option. Existing six guards untouched byte-for-byte (diff proves it).",
            "T4) harness/jev/tests added to pyproject testpaths and to .github/workflows/ci.yml; `pytest harness/jev/tests` green "
            "locally on system Python (no hou).",
            "T5) harness/battleplan/notes/JEV_BLUEPRINT.md sec. 5 'Where it lives': three lines for jev_harvest.py, "
            "jev_rerank.py, jev_bench.py (planned; written by BP10-GUIDES/CORPUS/BENCH). .gitignore gains "
            "rag/corpus/h22_prose/*.jsonl. rag/ingest/tool_map.json seeded: every fxhoudinimcp tool name referenced in the "
            "31 guides (grep the backticked tool names; expect ~57 refs) as keys, all values null, with a _comment that "
            "BP10-GUIDES fills them.",
        ],
        "touches": ["python/synapse/_vendor/fxhoudinimcp/", "docs/decisions/", "harness/jev/questions.json", "pyproject.toml",
                    ".github/workflows/ci.yml", "harness/battleplan/notes/JEV_BLUEPRINT.md", ".gitignore", "rag/ingest/tool_map.json"],
        "acceptance": [
            {"predicate": "sha256 of _vendor/fxhoudinimcp/LICENSE equals sha256 of upstream LICENSE at " + PIN[:8], "evidence": "check"},
            {"predicate": "31 guide files present under _vendor/fxhoudinimcp/guides/ and each sha256 equals its upstream file's", "evidence": "check"},
            {"predicate": "questions.json parses; guards.harvest/rerank/bench each have edge, state_fields, questions, policy; the six pre-existing guards are byte-identical", "evidence": "check"},
            {"predicate": "pytest harness/jev/tests passes on system Python and harness/jev/tests appears in pyproject testpaths and ci.yml", "evidence": "test"},
            {"predicate": "ADR-0001 exists and contains all eight refusal bullets from the blueprint", "evidence": "check"},
            {"predicate": "tool_map.json keys cover every backticked fxhoudinimcp tool name found in the 31 guides (count line = grep count)", "evidence": "check"},
        ],
        "crucible_criteria": STD_CRUX + ["the crucible re-hashes LICENSE and two random guide files against a fresh upstream clone"],
        "spawn_classes": [], "source": {"doc": JEVBP, "anchor": "sec. 'Scaffolded documents' (scaffold now rows); sec. 'Order of work' step 0; HARVEST_SPEC sec. 'Provenance and attribution'"},
    },
    # ------------------------------------------------------------------ CORPUS (auto)
    {
        "id": "BP10-CORPUS", "band": "BUILD", "class": "build", "tier": "auto", "team": "auto", "readonly": False, "deps": ["BP10-SCAFFOLD"],
        "name": "M1: H22 prose corpus from the shipped help archives, stamped and gated, H21 kept as fallback; JEV-RERANK shadow before/after",
        "note": "Self-cap: 30 turns (progress every 5). " + FENCE + " Read HARVEST_SPEC.md sec. 'Target 1' and 'Gates' first; "
                "the chunk record and STAMP.json fields are the contract. SideFX help text ships under the Houdini EULA: the "
                "generated corpus is NEVER committed (gitignored by SCAFFOLD); commit the builder, the stamp, the probe results. "
                "Clean-room reader: you may read fxhoudinimcp's help_handlers.py for the three path rules (zips + loose dirs; "
                "forward-slash zip-relative key with extension dropped; utf-8 with replacement) and nothing else. The 25 adversarial "
                "probes are the ones tests/test_knowledge_retrieval_repair.py and harness/verify/checks.py already run - locate "
                "them by grep, do not invent a new set. " + JEV_INV,
        "targets": [
            "T1) rag/ingest/help_archive.py: reads $HFS/houdini/help/*.zip and the loose dirs (copernicus/, mpm/, heightfields/, "
            "ml/), skips files/ images/ videos/ licenses/ licensing/, converts SideFX wiki markup to markdown (fixture-driven: 10 "
            "hand-checked pages in tests/fixtures/help/ before trusting it on 11,000), chunks, runs the phantom gate on node names "
            "vs h22_symbol_table.json (fail -> rag/quarantine/prose/ with reason, never dropped), writes rag/corpus/h22_prose/<scope>.jsonl "
            "with the spec's chunk record, and STAMP.json (build, scope count, page count, chunk count, ingest ts, sha of help_archive.py). "
            "`--build` runs under hython.",
            "T2) phantom_gate_status reads STAMP.json and reports CURRENT on 22.0.400 / STALE when the stamp build differs. Both directions demonstrated.",
            "T3) rag/retrieval/scope_weights.py: ONE table ranking h22_prose > h21 (fallback on miss) with the guide scope slot present "
            "but inert until BP10-GUIDES; every retrieval answer carries its scope. rag/skills/houdini21-reference stays in place as fallback.",
            "T4) tests/test_help_archive.py (fixture zip + loose dir round-trip, no hou) and tests/test_scope_weights.py.",
            "T5) harness/jev/jev_rerank.py + shadow CLI per JEV_HARVEST_BLUEPRINT sec. Site 2: rel_{i} Choice per hit over the "
            "top-12 per probe, state stripped of score/rank/path, NO retrieval side effect. Run it TWICE: once on the H21-only "
            "corpus BEFORE T1 lands (baseline) and once after (delta). Output harness/notes/harvest/rerank_shadow.md whose header "
            "says judged or unjudged. Extend harness/jev/jev_grade.py with --guard rerank against the probes' expected outcomes.",
        ],
        "touches": ["rag/ingest/", "rag/retrieval/", "rag/corpus/h22_prose/STAMP.json", "rag/quarantine/", "tests/", "harness/jev/jev_rerank.py",
                    "harness/jev/jev_grade.py", "harness/notes/harvest/", "python/synapse/"],
        "acceptance": [
            {"predicate": "G0: pytest tests/test_help_archive.py tests/test_scope_weights.py green on system Python", "evidence": "test"},
            {"predicate": "G1: hython rag/ingest/help_archive.py --build writes STAMP.json with scope count >= 50, page count >= 11000, zero chunks with empty source", "evidence": "probe"},
            {"predicate": "G3: the 25 adversarial probes still read 0/25 confident-wrong with h22_prose first and H21 fallback", "evidence": "test"},
            {"predicate": "G4: phantom_gate_status reports CURRENT on 22.0.400 and STALE after the stamp build is hand-edited (both shown)", "evidence": "probe"},
            {"predicate": "rerank_shadow.md exists with a before table and an after table; header states judged or unjudged; ledger harness/jev/ledger/bp10.rerank.jsonl has one row per call or a fallback row", "evidence": "check"},
            {"predicate": "no rag/corpus/h22_prose/*.jsonl is tracked by git", "evidence": "check"},
        ],
        "crucible_criteria": STD_CRUX + [
            "the crucible edits STAMP.json build to 22.0.368 and shows phantom_gate_status goes STALE",
            "the crucible plants a fake node name in one prose chunk and shows it lands in quarantine with a reason, not in the corpus",
        ],
        "spawn_classes": [], "source": {"doc": SPEC, "anchor": "sec. 'Target 1: H22 prose corpus'; sec. 'Gates and verification' G0-G4; JEV_HARVEST_BLUEPRINT sec. 'Site 2'"},
    },
    # ------------------------------------------------------------------ GUIDES (auto)
    {
        "id": "BP10-GUIDES", "band": "BUILD", "class": "build", "tier": "auto", "team": "auto", "readonly": False, "deps": ["BP10-CORPUS"],
        "name": "M2: 31 workflow guides through the phantom gate into retrieval, with provenance; JEV-HARVEST triage of the quarantine",
        "note": "Self-cap: 30 turns (progress every 5). " + FENCE + " Read HARVEST_SPEC.md sec. 'Target 2' first: the four-step "
                "transform is the contract. Promotion out of quarantine is Joe's word - this leg sorts and writes triage.md, it "
                "NEVER moves a guide from rag/quarantine/ to rag/corpus/. tool_map.json values are the Opus-worthy hour: a wrong "
                "mapping is a wrong answer in every chunk; mark any mapping you are unsure of with \"_unsure\": true. " + JEV_INV,
        "targets": [
            "T1) rag/ingest/guides.py: for each of the 31 vendored guides - strip the Goal:{description} line and the opening "
            "'You are ...' sentence; rewrite tool refs from rag/ingest/tool_map.json (null -> drop, logged with file:line); resolve "
            "every backticked token: (1) h22_symbol_table.json exact, (2) datasheet parm/attribute names, (3) difflib cutoff 0.85; "
            "any unresolved token quarantines the WHOLE guide to rag/quarantine/guides/<name>.md with the failing tokens at the top; "
            "chunk by ## section; write rag/corpus/guides/<name>.jsonl with the spec's record plus origin=fxhoudinimcp@" + PIN[:8] + ":<path> and licence=mit.",
            "T2) Fill rag/ingest/tool_map.json: every key -> a SYNAPSE equivalent name + one-line docstring, or null with a reason.",
            "T3) rag/retrieval/scope_weights.py: activate the guide scope per the spec's rule (guide above prose for how-to phrasing, "
            "below for reference phrasing; H22 above H21 always). tests/test_guides_ingest.py with one deliberately failing fixture guide.",
            "T4) harness/jev/jev_harvest.py + shadow CLI per JEV_HARVEST_BLUEPRINT sec. Site 1: token_kind Choice + rename_target_k "
            "Nouls over ONLY the residual tokens (after the three code lookups), and equivalent_does_the_job Noul per tool ref. "
            "Policy in decide() reads thresholds from questions.json. Writes harness/notes/harvest/triage.md (sorted groups, header "
            "judged/unjudged) and harness/notes/harvest/answer_key.json as an EMPTY template for Joe's reads. jev_grade.py --guard harvest.",
            "T5) README.md 'What it knows' gains the one attribution line from HARVEST_SPEC sec. 'Provenance' item 2; nothing else in README changes.",
        ],
        "touches": ["rag/ingest/guides.py", "rag/ingest/tool_map.json", "rag/corpus/guides/", "rag/quarantine/guides/", "rag/retrieval/scope_weights.py",
                    "tests/", "harness/jev/jev_harvest.py", "harness/jev/jev_grade.py", "harness/notes/harvest/", "README.md"],
        "acceptance": [
            {"predicate": "G2: every one of the 31 guides is in exactly one of rag/corpus/guides/ or rag/quarantine/guides/; every quarantined guide lists its failing tokens", "evidence": "check"},
            {"predicate": "G0: pytest tests/test_guides_ingest.py green; the deliberately broken fixture lands in quarantine", "evidence": "test"},
            {"predicate": "G3: the 25 adversarial probes still read 0/25 confident-wrong with the guide scope active", "evidence": "test"},
            {"predicate": "every chunk in rag/corpus/guides/ carries origin and licence fields; a one-line query by origin prefix lists them all", "evidence": "check"},
            {"predicate": "triage.md exists; header says judged or unjudged; no file moved from quarantine to corpus by this leg (git diff proves it)", "evidence": "check"},
            {"predicate": "README diff is exactly one added line", "evidence": "check"},
        ],
        "crucible_criteria": STD_CRUX + [
            "the crucible flips one tool_map.json value to a wrong tool and shows the affected chunk text changes and the test reddens",
            "the crucible confirms no guide text reached rag/corpus/guides/ without passing the symbol-table step (plant a fake node name)",
        ],
        "spawn_classes": [], "source": {"doc": SPEC, "anchor": "sec. 'Target 2: workflow guides'; sec. 'Gates' G2-G3; JEV_HARVEST_BLUEPRINT sec. 'Site 1'"},
    },
    # ------------------------------------------------------------------ BENCH (auto)
    {
        "id": "BP10-BENCH", "band": "BUILD", "class": "build", "tier": "auto", "team": "auto", "readonly": False, "deps": ["BP10-GUIDES"],
        "name": "M3: outside-in benchmark harness (SYNAPSE vs fxhoudinimcp, isolated hython per arm) + JEV-BENCH verifier + prompt leak check; plumbing proven on 1 prompt, G5 held for Joe",
        "note": "Self-cap: 30 turns (progress every 5). " + FENCE + " Read HARVEST_SPEC.md sec. 'Target 3' first: the fairness rules "
                "are the contract and are written down BEFORE the first run. Isolation is the whole design: each arm gets its own "
                "hython, own port (pin both explicitly: SYNAPSE 9999, fxhoudinimcp 8100), own scene copy. fxhoudinimcp installs via "
                "`pip install fxhoudinimcp` into a SEPARATE venv + its Houdini package file pointed at a scratch packages dir - never "
                "into SYNAPSE's env, never vendored. The full G5 run (24 prompts x 2 arms x 3 runs) is SPEND and is Joe's word: this "
                "leg runs exactly ONE prompt per arm on the empty scene to prove the plumbing and STOPS. " + JEV_INV,
        "targets": [
            "T1) harness/outside_in/: run.py (--scene empty|demo|large, --runs N, --confirm-spend required for large), arms/synapse.py "
            "(panel WS path ws://localhost:9999/synapse), arms/fxhoudinimcp.py (its MCP server over stdio against its hwebserver on 8100), "
            "prompts.jsonl (24 prompts, 4 per domain: SOP, Pyro, Vellum, Solaris/LOP, Copernicus, VEX; each with a `check` block), "
            "verify.py (third hython opens the saved scene and runs the check block; never reads either arm's own success report).",
            "T2) Token accounting from the provider response (input/output), tool calls, wall-clock, pass/fail, UNKNOWN count, SYNAPSE "
            "ledger row count; same pinned Claude model string on both arms; median and range over runs, never the best.",
            "T3) harness/jev/jev_bench.py per JEV_HARVEST_BLUEPRINT sec. Site 3: on not-pass only, failure_kind Choice + named_a_limitation "
            "Noul over the last 1,500 chars + last 3 tool names; policy: refused_unsupported >= 0.70 -> UNKNOWN, else FAIL with kind; "
            "confidence < 0.60 -> FAIL/cannot_tell (never UNKNOWN); no key -> FAIL/unjudged (distinct from UNKNOWN). "
            "--leak-check: hints_a_tool_or_arm Noul over all 24 prompts; any >= 0.50 is rewritten before the run and the leak ledger committed.",
            "T4) harness/notes/outside_in/LEDGER.md with the producer command beside every table; bench_key.json empty template for hand labels.",
            "T5) Plumbing proof: run.py --scene empty --runs 1 --limit 1 (one prompt per arm) completes and writes two ledger rows with real token counts.",
        ],
        "touches": ["harness/outside_in/", "harness/jev/jev_bench.py", "harness/jev/jev_grade.py", "harness/notes/outside_in/", "harness/jev/tests/"],
        "acceptance": [
            {"predicate": "prompts.jsonl has 24 rows, 4 per domain, each with a non-empty check block", "evidence": "check"},
            {"predicate": "--leak-check ran over all 24 prompts; leak ledger committed; no prompt >= 0.50 remains (or a fallback row explains no key)", "evidence": "check"},
            {"predicate": "one prompt per arm on the empty scene produced two LEDGER rows with provider token counts and a verify.py verdict", "evidence": "probe"},
            {"predicate": "verify.py runs in a hython that is neither arm's process and reads no arm success text (code inspection + a planted false success claim is not credited)", "evidence": "test"},
            {"predicate": "run.py refuses --scene large without --confirm-spend and prints an estimate from the recorded per-turn median", "evidence": "test"},
            {"predicate": "G5 full run NOT executed by this leg (ledger has <= 2 benchmark rows)", "evidence": "check"},
        ],
        "crucible_criteria": STD_CRUX + [
            "the crucible plants 'Task complete.' in an arm's final text on a failing scene and shows verify.py still FAILs and jev_bench classifies claimed_success (or unjudged without a key)",
            "the crucible confirms the two arms never share a port, a process or a scene file",
        ],
        "spawn_classes": [], "source": {"doc": SPEC, "anchor": "sec. 'Target 3: outside-in benchmark'; sec. 'Gates' G5; JEV_HARVEST_BLUEPRINT sec. 'Site 3'"},
    },
    # ------------------------------------------------------------------ CRUX (referee)
    {
        "id": "BP10-CRUX", "band": "TRUST", "class": "crucible", "tier": "referee", "readonly": True,
        "deps": ["BP10-SCAFFOLD", "BP10-CORPUS", "BP10-GUIDES", "BP10-BENCH"],
        "name": "CRUX: adversarial re-verification of the four BP10 builder legs",
        "note": "Tier: referee (Fable 5.1). Read-only on product files. Self-cap: 25 turns. " + FENCE + " The JEV-SCREEN line in "
                "your brief (if present) tells you where evidence is thin; it never removes a read. Nothing merges on a BROKEN.",
        "targets": [
            "T1) Per builder receipt: re-run every non-GUI acceptance predicate in a fresh checkout of the leg branch; verdict rows pass|fail|UNKNOWN with your own anchors.",
            "T2) >= 2 self-authored mutations per builder leg, each named with the check it reddens -> harness/battleplan/notes/BP10-CRUX_mutations.json",
            "T3) harness/battleplan/notes/BP10-CRUX_verdicts.md: one verdict per leg (SOUND | SOUND-WITH-NITS | BROKEN) plus the screen-vs-CRUX agreement line per leg.",
            "T4) Licence audit row: confirm no SideFX help text is tracked by git and the vendored LICENSE is byte-identical to upstream.",
        ],
        "touches": [],
        "acceptance": [
            {"predicate": "one verdict per builder leg (four) with independently re-run rows and the crucible's own anchors", "evidence": "receipt"},
            {"predicate": ">= 2 self-authored mutations per builder leg, each named with the check it reddens", "evidence": "test"},
            {"predicate": "screen-vs-CRUX agreement line present for all four legs", "evidence": "receipt"},
            {"predicate": "licence audit row present: no EULA text tracked, LICENSE hash matches upstream", "evidence": "check"},
        ],
        "crucible_criteria": STD_CRUX,
        "spawn_classes": [], "source": {"doc": SPEC, "anchor": "sec. 'Gates and verification' (all gates); sec. 'Mission split'"},
    },
    # ------------------------------------------------------------------ TIDY (mechanical)
    {
        "id": "BP10-TIDY", "band": "TRUST", "class": "tidy", "tier": "mechanical", "readonly": True, "deps": ["BP10-CRUX"],
        "name": "TIDY: BP10 worktree, receipt and Jev ledger census",
        "note": "Tier: mechanical. Read-only. Self-cap: 8 turns. " + FENCE,
        "targets": [
            "T1) harness/battleplan/notes/BP10_TIDY.md: a table of BP10 worktrees (branch, HEAD, clean?), receipts (leg, status) and "
            "harness/jev/ledger/bp10.*.jsonl row counts per guard (route, team, screen, edge, drift, rerank, harvest, bench), ending in a count line per table.",
        ],
        "touches": [],
        "acceptance": [{"predicate": "every table ends with a count line that equals its row count", "evidence": "check"}],
        "crucible_criteria": STD_CRUX,
        "spawn_classes": [], "source": {"doc": JEVBP, "anchor": "sec. 'Order of work and gates' (done criteria)"},
    },
]


def main() -> int:
    out = AF / "missions"
    out.mkdir(exist_ok=True)
    errors = []
    for m in M:
        errs = ms.validate_mission(m)
        if errs:
            errors.extend(errs)
            continue
        (out / f"{m['id']}.json").write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote missions/{m['id']}.json  tier={m.get('tier')} team={m.get('team', '-')} deps={m['deps']}")
    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print("  " + e)
        return 1
    print(f"{len(M)} missions written + validated. Next (separate acts): compile_wave.py bp10 -> build_manifest_bp10.py -> ARM on Joe's word.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
