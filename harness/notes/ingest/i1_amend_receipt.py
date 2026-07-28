"""Amend harness/notes/receipts/I1.json with the re-entry verification pass.

ADDITIVE ONLY. Nothing already in the receipt is removed or rewritten except:
  - oracle.corpus_sha256, which is corrected to the anchor that actually reproduces from
    the committed tree, with the original preserved beside it under its real name.

Run:  python harness/notes/ingest/i1_amend_receipt.py
"""

import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RECEIPT = os.path.join(REPO, "harness", "notes", "receipts", "I1.json")
VERIFY = os.path.join(HERE, "i1_verify_reentry.json")

r = json.load(open(RECEIPT, encoding="utf-8"))
v = json.load(open(VERIFY, encoding="utf-8"))

head = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                      capture_output=True, text=True, cwd=REPO).stdout.strip()

anchors = v["checks"]["V8"]["anchors"]

# --- 1. the re-entry block -------------------------------------------------
r["reentry_verification"] = {
    "why": ("A later orchestrator session was handed harness/prompts/i1.md and found the leg "
            "already built and committed. Accepting a committed artifact because it reports "
            "itself green is the defect Law 1 names, so every headline number was re-derived "
            "from the shipped archive and the running build rather than from this receipt."),
    "producer": "harness/notes/ingest/i1_verify_reentry.py",
    "artifact": "harness/notes/ingest/i1_verify_reentry.json",
    "model": "claude-opus-5[1m]",
    "settings_profile": ("Interactive orchestrator session. No subagents and no workflows were "
                         "dispatched: the session's standing instruction forbids both unless the "
                         "user asks, and Article V's collision on this very worktree makes a "
                         "write-capable fan-out the exact wrong instrument. pytest was NOT run "
                         "and no suite evidence is claimed; the leg touches no product code."),
    "checks_passed": "%d of %d" % (len(v["checks"]) - len(v["failed"]), len(v["checks"])),
    "failed": v["failed"],
    "checks": {k: {"title": c["title"], "ok": c["ok"]} for k, c in v["checks"].items()},
    "mutation_tested": ("The verification was itself mutation-tested: breaking one entry's tier "
                        "and inflating one reported count drove exactly V4 and V3 red with no "
                        "collateral. A check that cannot fail is a decoration (Law 1)."),
    "independently_confirmed": [
        "171 is the number: 161 slash-form + 11 bare-form links, 1 overlapping, union 171, "
        "counted off news.zip!22/copernicus.txt by a census this session wrote.",
        "All 10 node types the slash-requiring pattern drops exist in the live Cop catalogue "
        "on 22.0.368 - so 161 is a pattern artifact, not a documentation error.",
        "693 entries recompute to the reported per-context integers with zero disagreement "
        "and zero provenance violations.",
        "8 of 8 claimed live parm counts re-read by instantiating the nodes on the running build.",
        "Calibration reproduces byte-identically at 72/72; its NEGATIVE controls are real "
        "mutations of the input, not assertions of the reader's own output.",
        "Scope fence held: git diff --name-only 87a5af9..HEAD touches only "
        "harness/notes/ingest and harness/notes/receipts.",
    ],
    "conflict_adjudicated": {
        "question": "I0 named pointmerge / rop_image / usdmaterial as below the floor; this leg "
                    "names layertogeo-2.0 / pointmerge / usdmaterial. Which is right?",
        "verdict": "This leg. Both differences have an identifiable cause.",
        "rop_image": "rescued by include resolution - it carries 57 described parameters once "
                     "@section include anchors are followed; I0's reader did not follow them.",
        "layertogeo": "two distinct pages. cop/layertogeo clears with 2 described parameters but "
                      "is NOT in the named set; cop/layertogeo-2.0 IS in the named set and carries "
                      "0. Version-blind stem matching scores the wrong page.",
    },
}

# --- 2. the anchor finding -------------------------------------------------
r.setdefault("findings", []).append({
    "id": "I1-F12",
    "tier": "VERIFIED-STATIC",
    "found_by": "re-entry verification V8",
    "anchor": "harness/notes/ingest/i1_verify_reentry.json:checks.V8",
    "title": ("Both of this leg's provenance anchors were hashed on Windows CRLF working-copy "
              "bytes and neither reproduces from the committed tree."),
    "detail": ("core.autocrlf=true, so git stores LF while the producers hashed the CRLF working "
               "copy. receipt.oracle.corpus_sha256 and _i1b_calibration.json:reader_sha256 are "
               "both the CRLF variant - proven, not inferred: re-hashing the LF bytes as CRLF "
               "reproduces each recorded value exactly. Content is IDENTICAL modulo line endings, "
               "so this is a provenance defect and not tampering. reader_sha256 is the worse of "
               "the two because it is a GATE binding the corpus to the reader the calibration "
               "certified; on a fresh clone or Linux CI that binding cannot be re-established, so "
               "the gate is unverifiable off the one machine that produced it. This is Law 2 in a "
               "new costume - the producer path exists, but the value it emits cannot be "
               "reproduced from what is committed."),
    "reproducible_anchors": {
        "corpus": anchors["corpus"]["committed_blob_sha256"],
        "reader": anchors["reader"]["committed_blob_sha256"],
    },
})

# --- 3. corrected oracle anchor -------------------------------------------
o = r["oracle"]
o["corpus_sha256_as_committed"] = anchors["corpus"]["committed_blob_sha256"]
o["corpus_sha256_working_copy_crlf"] = o.pop("corpus_sha256")
o["corpus_sha256_note"] = ("Use corpus_sha256_as_committed. The original field held the CRLF "
                           "working-copy hash, which no reader can re-derive from the tree "
                           "(I1-F12). Both describe byte-identical content.")

# --- 4. ruling item --------------------------------------------------------
r.setdefault("for_ruling", []).append({
    "id": "I1-R6",
    "source": "I1-F12",
    "question": ("Every producer in this harness hashes working-copy bytes on a core.autocrlf=true "
                 "Windows checkout, so every sha it records is unreproducible from the committed "
                 "tree - including reader_sha256, which is a calibration GATE. This receipt's own "
                 "anchor has been corrected, but the producers will re-emit the defect on the next "
                 "leg and on every leg after. Should hashing be normalised harness-wide?"),
    "recommendation": ("Normalise: hash open(path,'rb').read().replace(b'\\r\\n', b'\\n') in every "
                       "producer that records a sha, so the anchor matches the committed blob on "
                       "any platform. Doing it here would mean re-running i1b_merge.py and "
                       "i1b_calibrate.py, which regenerates the 8.5 MB artifact currently under "
                       "audit - churning the thing being certified to fix a field describing it. "
                       "The correction is recorded instead and the producer change is routed here "
                       "because it is harness-wide and touches a gate, which Article I keeps off "
                       "the agent's desk. Alternatively add '*.json -text' / '*.py -text' to "
                       ".gitattributes so the tree stores what the producer hashed - but that "
                       "fights the platform rather than the assumption, and the assumption is the "
                       "bug."),
})

# --- 5. drift --------------------------------------------------------------
r.setdefault("drift", []).append({
    "id": "I1-D1",
    "rule": "R127 - read committed paths, never worktree globs",
    "observed": ("I1 is gated on I0, and I0's report, its receipt and all nine of its producers "
                 "are UNTRACKED in .claude/worktrees/i0-ingest. The gate artifact could only be "
                 "read as a worktree glob, because no committed copy exists to read."),
    "why_it_was_not_a_stop": ("Cosmetic to this leg's product: the re-entry re-derived from PRIMARY "
                              "sources - the shipped archive and the running build - so no number "
                              "here rests on the uncommitted I0 text. Where the two disagreed, the "
                              "primary source adjudicated and I0 lost (I1-F3)."),
    "structural_consequence": ("I0's own numbers remain unciteable under R127 until I1-R3 narrows "
                               ".gitignore:50 so its _i0_*.py producers can be committed at all. "
                               "Already escalated as I1-R5."),
})

# --- 6. bookkeeping --------------------------------------------------------
r["commits"] = [
    "%s verify(ingest): I1 - re-derive the committed leg from primary sources, and one "
    "anchor does not reproduce" % head,
] + r.get("commits", [])
r["artifacts"]["producers"] = sorted(set(r["artifacts"]["producers"]) |
                                     {"i1_verify_reentry.py", "i1_amend_receipt.py"})
r["artifacts"]["reentry_verification"] = "harness/notes/ingest/i1_verify_reentry.json"

r["resume_token"]["skip"] = r["resume_token"]["skip"] + [
    "the re-entry verification - 7 of 8 checks green, re-derived from primary sources and "
    "itself mutation-tested; V8 is red BY DESIGN and is finding I1-F12, not a task",
    "the 171 vs 161 question - settled twice now, independently, off the shipped page and "
    "the live catalogue; do not re-open",
]
r["resume_token"]["next"] = [
    "I1-R6: normalise sha hashing to LF harness-wide, or accept unreproducible anchors",
] + r["resume_token"]["next"]

r["status_note"] = r["status_note"] + (
    "  RE-ENTRY 2026-07-27: an independent session re-derived every headline number from primary "
    "sources and confirmed the leg on 7 of 8 checks. Status stays green because the brief's oracle "
    "is met on every line and independently verified. The one red check, V8, is a defect in a "
    "receipt METADATA field - the corpus sha - not in the deliverable; it is recorded as I1-F12, "
    "the reproducible anchor is now in oracle.corpus_sha256_as_committed, and it was left red "
    "rather than softened (Law 7).")

with open(RECEIPT, "w", encoding="utf-8") as fh:
    json.dump(r, fh, indent=1, ensure_ascii=False)
    fh.write("\n")

print("amended %s" % RECEIPT)
print("  findings   : %d" % len(r["findings"]))
print("  for_ruling : %d" % len(r["for_ruling"]))
print("  drift      : %d" % len(r["drift"]))
print("  status     : %s" % r["status"])
