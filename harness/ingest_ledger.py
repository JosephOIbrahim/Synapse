"""ingest_ledger — the per-context knowledge-ingest ledger (W4-GUARD, target 2).

WHY THIS EXISTS
---------------
The H22 context-knowledge recon (docs/reviews/h22-context-knowledge-recon-2026-08-15.md,
"How this runs") calls for exactly two new constructions: a freshness gate in
checks.py (W4-GUARD target 1, see check_corpus_stamp_fresh) and *"a per-context
ledger over legs.json"* — this module. The ledger answers three questions the
served node corpus (rag/corpus/h22_nodes.json) cannot answer about itself:

    which Houdini contexts are wired, at what build, behind which gate word.

The corpus is a flat bag of 659 entries; nothing in it records that cop/cop2/lop
were the contexts a human ratified into rag/corpus/, at build 22.0.368, under the
RULING-175 discharge of INGEST-01. The ledger records that provenance so a
release gate (check_ingest_ledger_single_writer) can verify it and a human can
read it.

SINGLE WRITER — ENFORCED, NOT ASSUMED (the crucible criterion)
--------------------------------------------------------------
"one writer per surface is a ratified constraint" (W4-GUARD crucible_criteria).
The recon is explicit: the ledger has ONE writer — the gate/orchestrator side —
and agents are read-only against it. This module makes that structural, not a
comment:

  * write_ledger() is the ONLY sanctioned mutator. It REJECTS any writer identity
    other than AUTHORIZED_WRITER (raises UnauthorizedWriter) — a second writer is
    turned away at the door.
  * Every valid ledger carries a blake2b digest over its own content. An
    out-of-band edit by a second writer that does not recompute that digest is
    DETECTED by verify_ledger() — the same "hand-edit fails loud" idiom every
    freshness catalog in checks.py already uses (connectivity/lop/cook catalogs).
  * verify_ledger() additionally cross-checks each wired context against the
    served corpus, so a second writer that flips `sop.wired=true` without the
    corpus actually carrying sop entries is CAUGHT — the ledger cannot lie about
    what shipped.

So a second-writer attempt is BOTH rejected (at the write API) AND detectable (at
verify). Honest boundary, stated per the truth contract: content integrity is not
a cryptographic signature. A rogue process that imports compute_digest and
perfectly re-stamps BOTH the AUTHORIZED_WRITER identity and a fresh digest is
indistinguishable from the real writer — the guarantee is "sole sanctioned API +
tamper-evidence + corpus cross-check", not "unforgeable". The strengthening path
(detached signature keyed to the orchestrator) is deliberately out of scope here.

SCHEMA  ingest_ledger/v1
------------------------
A JSON object, written ONLY by write_ledger():

    {
      "schema":         "ingest_ledger/v1",
      "writer":         "orchestrate.ps1",   # == AUTHORIZED_WRITER, the sole writer
      "revision":       <int>,               # monotone, bumped by write_ledger
      "ratified_build": "22.0.400",          # the drop.json houdini_build this ledger aligns to
      "contexts": {                          # one row per Houdini context
        "<ctx>": {
          "wired":   <bool>,                 # is this context's node knowledge served today
          "build":   "<build>" | null,       # the build its entries were ingested at (null if unwired)
          "entries": <int>,                  # count served for this context (0 if unwired)
          "gate":    "<gate word>" | null,   # the human word that authorized wiring (null if unwired)
          "leg":     "<leg id>" | null,      # the ING-<CTX> leg that produced/will produce it
          # apex only:
          "blocked_by_policy": "D-H22-2",    # never wired locally — federated to the native APEX MCP
          "note": "<why>"
        }, ...
      },
      "blake2b": "<hexdigest over the canonical payload, digest_size=16>"
    }

The blake2b covers every field EXCEPT itself, serialized canonically
(sort_keys=True), so the digest is reproducible regardless of file pretty-print.

APEX IS POLICY-BLOCKED (D-H22-2)
--------------------------------
apex is enumerated but MUST stay wired=false forever: APEX knowledge is federated
to SideFX's own APEX MCP and SYNAPSE owns no local APEX corpus by decision
(check_no_rigging_drift / check_scout_no_apex_corpus enforce the sibling rules).
verify_ledger() flags any ledger that marks a POLICY_BLOCKED context wired.

Pure Python, zero hou / zero synapse import: runs anywhere the repo does (the
orchestrator writes it; checks.py + tests read it).
"""
import hashlib
import json
import os
from collections import Counter

LEDGER_SCHEMA = "ingest_ledger/v1"

# The ONE authorized writer of this surface — the gate/orchestrator side. Any
# other identity is rejected by write_ledger() and flagged by verify_ledger().
AUTHORIZED_WRITER = "orchestrate.ps1"

# Contexts the ledger enumerates. The recon's per-context table plus the two
# COP families the shipped corpus actually carries (cop / cop2). Ordering is
# cosmetic — verify_ledger derives truth from the corpus, not from this order.
KNOWN_CONTEXTS = (
    "cop", "cop2", "lop", "sop", "top", "vop", "dop", "obj", "rop", "chop", "apex",
)

# Never wired locally (D-H22-2): federated to the native APEX MCP.
POLICY_BLOCKED = frozenset({"apex"})

_REQUIRED_CTX_KEYS = ("wired", "build", "entries", "gate", "leg")


class UnauthorizedWriter(Exception):
    """Raised by write_ledger() when a caller stamps a writer other than
    AUTHORIZED_WRITER. Single-writer, enforced at the write boundary."""


def _payload(doc):
    """The digest-covered subset of a ledger doc: everything but the digest."""
    return {k: v for k, v in doc.items() if k != "blake2b"}


def compute_digest(doc):
    """blake2b (digest_size=16) over the canonical payload — the same scheme the
    connectivity / lop / cook catalogs use in checks.py. sort_keys makes it
    independent of dict insertion order and of the file's pretty-printing."""
    canon = json.dumps(_payload(doc), sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.blake2b(canon, digest_size=16).hexdigest()


def contexts_from_corpus(corpus, gate_wired=None, leg_wired=None):
    """Derive the per-context rows from the SERVED corpus — honest by construction.

    A context is `wired` iff the corpus actually carries entries for it; its
    `build` is then the corpus's own top-level `build` stamp (the build those
    entries were ingested at), and `entries` is the real count. Unwired contexts
    carry the future ING-<CTX> leg id so the ledger reads as a work map, not just
    a snapshot. POLICY_BLOCKED contexts are forced unwired with the federation note.
    """
    entries = (corpus or {}).get("entries") or []
    corpus_build = (corpus or {}).get("build")
    counts = Counter(e.get("context") for e in entries if isinstance(e, dict))
    rows = {}
    for ctx in sorted(set(KNOWN_CONTEXTS) | set(k for k in counts if k)):
        n = counts.get(ctx, 0)
        wired = n > 0 and ctx not in POLICY_BLOCKED
        row = {
            "wired": wired,
            "build": corpus_build if wired else None,
            "entries": n,
            "gate": (gate_wired if wired else None),
            "leg": (leg_wired if wired else "ING-%s" % ctx.upper()),
        }
        if ctx in POLICY_BLOCKED:
            row["wired"] = False
            row["leg"] = None
            row["blocked_by_policy"] = "D-H22-2"
            row["note"] = ("federated to the native APEX MCP; SYNAPSE owns no local "
                           "APEX corpus by decision — never wire this context")
        rows[ctx] = row
    return rows


def write_ledger(path, contexts, ratified_build, writer=AUTHORIZED_WRITER,
                 prev=None):
    """Atomically write a valid ledger. THE single sanctioned mutator.

    Rejects any writer identity other than AUTHORIZED_WRITER (single-writer,
    enforced). Stamps a monotone revision (bumped from `prev` if given) and the
    content digest, then writes via `.tmp` + os.replace (the atomic-persistence
    idiom RecommendationHistory uses). Returns the written doc.
    """
    if writer != AUTHORIZED_WRITER:
        raise UnauthorizedWriter(
            "ingest_ledger has ONE writer (%r); refusing write from %r"
            % (AUTHORIZED_WRITER, writer))
    revision = int((prev or {}).get("revision", 0)) + 1
    doc = {
        "schema": LEDGER_SCHEMA,
        "writer": writer,
        "revision": revision,
        "ratified_build": ratified_build,
        "contexts": contexts,
    }
    doc["blake2b"] = compute_digest(doc)
    # Race-safe write for concurrent authorized writers (crucible criterion A). Each
    # call writes to a UNIQUE temp (not a shared "%s.tmp" — that source collision
    # crashed on Windows), then os.replace (atomic on POSIX and Windows). os.replace
    # itself is atomic, but on Windows two writers racing the SAME destination can
    # transiently contend it (ERROR_ACCESS_DENIED / SHARING_VIOLATION); a bounded
    # retry turns that into last-writer-wins instead of an unhandled PermissionError.
    # Readers (via os.replace atomicity) never observe a partial file.
    import tempfile
    import time
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=os.path.basename(path) + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)
            f.write("\n")
        last = None
        for _ in range(200):
            try:
                os.replace(tmp, path)
                return doc
            except PermissionError as e:   # transient Windows destination contention
                last = e
                time.sleep(0.005)
        raise last
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_ledger(path):
    """Read + parse a ledger file. Raises on absent/malformed (the caller decides
    whether that is a FAIL — checks.py treats a missing ledger as a hard fail so
    deleting it cannot silence the gate)."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def verify_ledger(doc, corpus=None):
    """Return a list of violation strings ([] == sound).

    Detects a second/rogue writer and any tampering:
      * schema / structural malformation,
      * writer identity != AUTHORIZED_WRITER (a second writer stamped its own id),
      * blake2b mismatch (an out-of-band content edit that did not re-stamp),
    and — when `corpus` (the served rag/corpus/h22_nodes.json dict) is supplied —
    cross-checks every context claim against what actually shipped:
      * a context marked wired must be present in the corpus with the same entry
        count and the same build the corpus is stamped with,
      * a context marked unwired must carry ZERO corpus entries,
      * a corpus context the ledger does not enumerate is untracked drift,
      * a POLICY_BLOCKED context (apex) must never be wired.
    """
    v = []
    if not isinstance(doc, dict):
        return ["ledger is not a JSON object"]
    if doc.get("schema") != LEDGER_SCHEMA:
        v.append("schema=%r != %r" % (doc.get("schema"), LEDGER_SCHEMA))
    writer = doc.get("writer")
    if writer != AUTHORIZED_WRITER:
        v.append("unauthorized writer %r (single-writer surface; sole writer is %r)"
                 % (writer, AUTHORIZED_WRITER))
    if "blake2b" not in doc:
        v.append("no blake2b digest — cannot prove the content was written by the writer")
    else:
        recomputed = compute_digest(doc)
        if recomputed != doc.get("blake2b"):
            v.append("blake2b mismatch (out-of-band edit / second writer): "
                     "recomputed %s != stored %s"
                     % (recomputed[:12], str(doc.get("blake2b"))[:12]))
    if not doc.get("ratified_build"):
        v.append("no ratified_build")
    contexts = doc.get("contexts")
    if not isinstance(contexts, dict):
        return v + ["contexts is not an object — malformed ledger"]
    for ctx, row in contexts.items():
        if not isinstance(row, dict):
            v.append("context %r row is not an object" % ctx)
            continue
        for k in _REQUIRED_CTX_KEYS:
            if k not in row:
                v.append("context %r missing required key %r" % (ctx, k))
        if str(ctx).strip().lower() in POLICY_BLOCKED and row.get("wired"):
            # case/whitespace-normalized so "APEX"/"Apex"/"apex " cannot smuggle a
            # wired apex row past the pure verify (crucible finding, facet 3)
            v.append("context %r is POLICY_BLOCKED (D-H22-2) but marked wired — "
                     "APEX is federated, never wired locally" % ctx)
        if row.get("wired") and not row.get("build"):
            v.append("context %r wired but carries no build stamp" % ctx)

    if corpus is not None:
        v.extend(_cross_check_corpus(contexts, corpus))
    return v


def _cross_check_corpus(contexts, corpus):
    """Ledger claims vs the served corpus — a lying second-writer's tell."""
    v = []
    entries = (corpus or {}).get("entries") or []
    corpus_build = (corpus or {}).get("build")
    counts = Counter(e.get("context") for e in entries if isinstance(e, dict))
    for ctx, row in contexts.items():
        if not isinstance(row, dict):
            continue
        n_corpus = counts.get(ctx, 0)
        if row.get("wired"):
            if n_corpus == 0:
                v.append("context %r marked wired but the served corpus carries 0 "
                         "entries for it (ledger over-claims)" % ctx)
            elif row.get("entries") != n_corpus:
                v.append("context %r entries=%r != %d in the served corpus"
                         % (ctx, row.get("entries"), n_corpus))
            if row.get("build") not in (None, corpus_build):
                v.append("context %r build=%r != corpus build %r"
                         % (ctx, row.get("build"), corpus_build))
        else:
            if n_corpus > 0:
                v.append("context %r marked unwired but the served corpus carries "
                         "%d entries for it (ledger under-reports what shipped)"
                         % (ctx, n_corpus))
    tracked = set(contexts)
    for ctx, n in counts.items():
        if ctx and ctx not in tracked and n > 0:
            v.append("corpus context %r (%d entries) is not tracked by the ledger"
                     % (ctx, n))
    return v


# --------------------------------------------------------------------------
# Ratified-build resolution — the ONE definition of "what build is ratified",
# shared by the freshness gate (checks.py::check_corpus_stamp_fresh) and the
# seed below so the two can never disagree.
#
# Authority order, strongest first:
#   1. harness/state/drop.json  ->  houdini_build  (the human-ratified pin; the
#      constitution forbids agents from editing it). NOTE: drop.json is gitignored,
#      so it is present in the MAIN working tree but ABSENT from forked worktrees.
#   2. the HIGHEST-major committed symbol table  ->  houdini_version  (always in
#      the worktree; the SAME authority W4-KNOW's runtime load-check uses, "against
#      the live symbol-table build"). The current build is the highest committed
#      major, so the release gate needs no hython.
#
# The authority is chosen INDEPENDENTLY of the corpus under test — never keyed to
# the corpus's own major. Keying to the corpus would let a downgrade-stamped
# corpus (build "21.x") self-select an older symbol table and pass the freshness
# gate; the ratified build must come from the ratified side alone.
#
# If BOTH drop.json and the highest-major table are present and DISAGREE, that is
# ratification/host drift -> reported as an error (the gate FAILS loud; a release
# must not ship on an ambiguous ratified build). If NEITHER exists, build is None
# and the gate FAILS (block, never warn).
# --------------------------------------------------------------------------
def _highest_major_symbol_table(repo_root):
    """(build_str|None, major_str|None) for the highest-major committed symbol
    table — the current ratified build's table, chosen without reference to the
    corpus under test."""
    import glob
    import re
    data_dir = os.path.join(repo_root, "python", "synapse", "cognitive", "tools", "data")
    best_major, best_build = None, None
    for fp in glob.glob(os.path.join(data_dir, "h*_symbol_table.json")):
        m = re.search(r"h(\d+)_symbol_table\.json$", os.path.basename(fp))
        if not m:
            continue
        major = int(m.group(1))
        if best_major is not None and major <= best_major:
            continue
        try:
            with open(fp, "r", encoding="utf-8") as f:
                build = json.load(f).get("houdini_version") or None
        except Exception:
            continue
        if build:
            best_major, best_build = major, build
    return best_build, (str(best_major) if best_major is not None else None)


def resolve_ratified_build(repo_root, corpus_build=None):
    """-> {"build": str|None, "source": str, "error": str|None}.

    corpus_build is accepted for signature stability but is DELIBERATELY not used
    to select the authority (see the downgrade-attack note above)."""
    drop_build = None
    drop_path = os.path.join(repo_root, "harness", "state", "drop.json")
    if os.path.exists(drop_path):
        try:
            with open(drop_path, "r", encoding="utf-8") as f:
                drop_build = json.load(f).get("houdini_build") or None
        except Exception as e:
            return {"build": None, "source": "drop.json",
                    "error": "drop.json unreadable: %s" % (str(e)[:120])}

    sym_build, sym_major = _highest_major_symbol_table(repo_root)

    if drop_build and sym_build and drop_build != sym_build:
        return {"build": None, "source": "drop.json+symbol_table",
                "error": ("ratified-build authorities disagree: drop.json=%r vs "
                          "h%s_symbol_table.json=%r" % (drop_build, sym_major, sym_build))}
    if drop_build:
        return {"build": drop_build, "source": "harness/state/drop.json", "error": None}
    if sym_build:
        return {"build": sym_build,
                "source": "h%s_symbol_table.json (houdini_version)" % sym_major,
                "error": None}
    return {"build": None, "source": "none",
            "error": ("no ratified-build authority: neither harness/state/drop.json "
                      "nor a committed h<major>_symbol_table.json is present")}


# --------------------------------------------------------------------------
# Seed helper — writes the default ledger FROM the live corpus so the seeded
# state is honest by construction (cop/cop2/lop wired @ the corpus build, the
# rest unwired, apex policy-blocked). Invoked once by W4-GUARD; the orchestrator
# is the writer thereafter.  Usage:
#     python harness/ingest_ledger.py <repo_root>
# --------------------------------------------------------------------------
def seed_from_repo(repo_root):
    corpus_path = os.path.join(repo_root, "rag", "corpus", "h22_nodes.json")
    ledger_path = os.path.join(repo_root, "harness", "ingest_ledger.json")
    with open(corpus_path, "r", encoding="utf-8") as f:
        corpus = json.load(f)
    resolved = resolve_ratified_build(repo_root, corpus_build=corpus.get("build"))
    if resolved["error"] or not resolved["build"]:
        raise RuntimeError("cannot resolve ratified build for seed: %s"
                           % (resolved["error"] or "no authority"))
    ratified_build = resolved["build"]
    contexts = contexts_from_corpus(
        corpus,
        gate_wired="RULING-175 (INGEST-01 discharged; build-time live_type filter)",
        leg_wired="I1")
    prev = None
    if os.path.exists(ledger_path):
        try:
            prev = load_ledger(ledger_path)
        except Exception:
            prev = None
    doc = write_ledger(ledger_path, contexts, ratified_build, prev=prev)
    return ledger_path, doc


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    path, doc = seed_from_repo(root)
    wired = sorted(c for c, r in doc["contexts"].items() if r.get("wired"))
    print("wrote %s (rev %d, ratified %s)" % (path, doc["revision"], doc["ratified_build"]))
    print("  wired contexts :", ", ".join(wired) or "none")
    print("  blake2b        :", doc["blake2b"])
