#!/usr/bin/env python3
"""K.6 Phase 1  -  vex-corpus re-wire ASSESSMENT (go/no-go scorecard).

Read-only. Writes ONLY a report (never rag/). Answers the standing question
"should we ever re-wire vex-corpus?" with a measured number instead of a debate:

  raw code blocks
    -> canonical exact-dedup        (how much is trivial duplication?)
    -> vcc compile-gate             (how much is VALID VEX? ground truth, not vibes)
    -> redundancy vs existing rag/  (how much is NET-NEW vs what we already have?)
    = usable-entry count            (re-wiring adds ~this many real entries)

The VEX gate mirrors scout's "dir() is a hard gate" for hou.*: each snippet is
translated (@attr -> context globals / declared locals), wrapped as a context
function, and compiled with the real vcc. exit 0 = valid; nonzero = rejected with
its Error code. This deterministically rejects the broken VEX the last sync shipped
(`vector pts = pts[];` -> Error 1019).

Full contract: harness/notes/spec-K6-rewire-admission.md

Usage:
    python scripts/rewire_assess.py
    python scripts/rewire_assess.py --limit 100          # quick sample
    python scripts/rewire_assess.py --no-embed           # skip redundancy (no torch)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_CORPUS = Path(r"C:\Users\User\vex-corpus\output\corpus\merged_corpus.jsonl")
DEFAULT_VCC = Path(r"C:\Program Files\Side Effects Software\Houdini 21.0.671\bin\vcc.exe")
DEFAULT_RAG = REPO_ROOT / "rag"

# --- VEX @attr translation (authoritative sop globals from `vcc --list-context-json=sop`) ---
SOP_GLOBALS = {"Cd", "Frame", "N", "Npt", "P", "Pw", "Time", "TimeInc",
               "accel", "age", "id", "life", "pstate", "ptnum", "v"}
PREFIX_TYPE = {"f": "float", "i": "int", "v": "vector", "p": "vector4",
               "u": "vector2", "s": "string", "2": "matrix2", "3": "matrix3",
               "4": "matrix", "m": "matrix", "d": "dict"}
# common bare (prefix-less) custom attrs, so a valid snippet does not type-fail
COMMON_ATTR_TYPE = {"pscale": "float", "uv": "vector", "orient": "vector4",
                    "up": "vector", "rest": "vector", "width": "float",
                    "density": "float", "temperature": "float", "name": "string",
                    "scale": "vector", "pivot": "vector", "rot": "vector4",
                    "area": "float", "dist": "float", "mass": "float"}

_ATTR = re.compile(r"([fivpusmd234])?@([A-Za-z_][A-Za-z0-9_]*)")
_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)


def translate_and_wrap(code: str, context: str = "sop") -> tuple[str, str]:
    """Turn an artist wrangle snippet into a compilable .vfl unit.
    Returns (wrapped_vfl, error)  -  error non-empty means the translator itself
    couldn't handle it (a HARNESS limitation, reported separately from a compile
    reject so we never inflate 'invalid' with our own gaps)."""
    declared: dict[str, str] = {}

    def repl(m: re.Match) -> str:
        prefix, name = m.group(1), m.group(2)
        if name in SOP_GLOBALS:
            return name                                  # context global; ignore any prefix
        if prefix:
            declared.setdefault(name, PREFIX_TYPE[prefix])
        elif name in COMMON_ATTR_TYPE:
            declared.setdefault(name, COMMON_ATTR_TYPE[name])
        else:
            declared.setdefault(name, "float")           # VEX default for a bare unknown attr
        return name

    body = _ATTR.sub(repl, code)
    # strip v@group_* / @group_* leftovers that aren't attrs  -  rare; leave as-is.
    decls = "".join(f"  {t} {n} = 0;\n" for n, t in sorted(declared.items()))
    ctx = context if context in ("sop", "surface", "cvex", "displace", "fog") else "sop"
    vfl = f"{ctx}\nwrangle() {{\n{decls}{body}\n}}\n"
    return vfl, ""


def vcc_compile(vfl: str, vcc: Path) -> tuple[bool, str]:
    """Compile a wrapped .vfl. Returns (ok, detail). ok=True iff exit 0."""
    with tempfile.NamedTemporaryFile("w", suffix=".vfl", delete=False, encoding="utf-8") as f:
        f.write(vfl)
        tmp = f.name
    try:
        p = subprocess.run([str(vcc), "-o", ("NUL" if sys.platform == "win32" else "/dev/null"), tmp],
                           capture_output=True, text=True, timeout=30)
        if p.returncode == 0:
            return True, ""
        err = (p.stderr or p.stdout).strip().splitlines()
        # extract "Error <code>: <msg>"
        line = next((l for l in err if "Error" in l), err[-1] if err else "unknown")
        m = re.search(r"Error\s+(\d+):\s*(.*)", line)
        return False, (f"Error {m.group(1)}: {m.group(2)[:80]}" if m else line[:100])
    except subprocess.TimeoutExpired:
        return False, "vcc timeout"
    finally:
        try:
            Path(tmp).unlink()
        except OSError:
            pass


def canonical(code: str) -> str:
    """Cheap canonical form for exact-dedup: strip comments, collapse whitespace.
    Conservative (undercounts dups) -> the 'unique' count is an UPPER bound on real
    distinct snippets, the honest direction for a go/no-go. alpha-rename is Phase 2."""
    return re.sub(r"\s+", " ", _COMMENT.sub(" ", code)).strip()


def _atomic_snippets(code: str) -> list[str]:
    """Split a code_block into ATOMIC snippets on blank-line boundaries. A single
    multi-line snippet (loop/if) has no internal blank line and stays intact; several
    tutorial examples glued into one block get separated  -  without this each block
    compiles as one unit and independent snippets that reuse a var name (`float d`)
    false-reject with Error 1074 (multiple-declaration), a CHUNKING artifact not bad VEX.
    Comment-only / whitespace-only fragments are dropped (they are not knowledge)."""
    out = []
    for frag in re.split(r"\n\s*\n", code):
        if canonical(frag):                    # non-empty after stripping comments/ws
            out.append(frag.strip())
    return out


def extract_candidates(corpus_fp: Path, limit: int | None) -> list[dict]:
    """One candidate per ATOMIC snippet (code_block split on blank lines)."""
    out: list[dict] = []
    for line in corpus_fp.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        c = json.loads(line)
        blocks = c.get("code_blocks") or []
        vc = c.get("vex_context")
        ctx = (vc[0] if isinstance(vc, list) and vc else vc) or "sop"
        for i, b in enumerate(blocks):
            raw = b.get("code", "") if isinstance(b, dict) else str(b)
            for j, snip in enumerate(_atomic_snippets(raw)):
                out.append({"id": f"{c.get('id','?')}#{i}.{j}", "code": snip,
                            "context": ctx, "source": c.get("source_id", "?")})
        if limit and len(out) >= limit:
            return out[:limit]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    ap.add_argument("--vcc", default=str(DEFAULT_VCC))
    ap.add_argument("--rag", default=str(DEFAULT_RAG))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--redundancy-threshold", type=float, default=0.85)
    ap.add_argument("--no-embed", action="store_true")
    ap.add_argument("--out", default=str(REPO_ROOT / "harness" / "notes" / "rewire_assessment.json"))
    args = ap.parse_args()

    corpus_fp, vcc = Path(args.corpus), Path(args.vcc)
    if not corpus_fp.is_file():
        print(f"[rewire_assess] corpus not found: {corpus_fp}", file=sys.stderr)
        return 1
    have_vcc = vcc.is_file()

    cands = extract_candidates(corpus_fp, args.limit)
    print(f"[1/4] {len(cands)} code blocks from {corpus_fp.name}")

    # exact-dedup by canonical form
    by_canon: dict[str, dict] = {}
    dup_mult: Counter = Counter()
    for c in cands:
        k = canonical(c["code"])
        dup_mult[k] += 1
        by_canon.setdefault(k, c)
    uniq = list(by_canon.values())
    print(f"[2/4] {len(uniq)} unique snippets (exact-dedup collapsed {len(cands)-len(uniq)} dups)")

    # vcc validate
    valid, invalid, wrapfail = [], [], []
    err_codes: Counter = Counter()
    if have_vcc:
        for n, c in enumerate(uniq):
            if n and n % 200 == 0:
                print(f"      ...compiled {n}/{len(uniq)}")
            vfl, werr = translate_and_wrap(c["code"], c["context"])
            if werr:
                wrapfail.append(c)
                continue
            ok, detail = vcc_compile(vfl, vcc)
            if ok:
                valid.append(c)
            elif "Error 1109" in detail:
                # "Unknown token '@'"  -  our @attr translator missed a pattern
                # (e.g. @group:x, @arr[0], matrix prefixes). A HARNESS gap, not bad
                # VEX; bucket as wrap-limited so it never inflates the reject count.
                wrapfail.append({**c, "why": detail})
            else:
                invalid.append({**c, "why": detail})
                m = re.match(r"(Error \d+)", detail)
                err_codes[m.group(1) if m else "other"] += 1
        print(f"[3/4] {len(valid)} compile-valid / {len(invalid)} rejected / {len(wrapfail)} wrap-limited")
    else:
        print("[3/4] vcc absent  -  validity SKIPPED (degraded). Run on a Houdini host for the real gate.")
        valid = uniq

    # redundancy vs existing rag/
    redundant, net_new = [], []
    max_sims: list[float] = []
    if not args.no_embed and valid:
        try:
            sys.path.insert(0, str(REPO_ROOT / "python"))
            from sentence_transformers import SentenceTransformer
            import numpy as np
            emb_fp = Path(args.rag) / "semantic_index" / "embeddings.npy"
            existing = np.load(emb_fp).astype("float32")           # (N,384) L2-normalized
            model = SentenceTransformer("all-MiniLM-L6-v2")
            texts = [c["code"] for c in valid]
            vecs = np.asarray(model.encode(texts, normalize_embeddings=True), dtype="float32")
            sims = vecs @ existing.T                                 # cosine (both normalized)
            mx = sims.max(axis=1)
            for c, s in zip(valid, mx):
                max_sims.append(float(s))
                (redundant if s >= args.redundancy_threshold else net_new).append({**c, "max_sim": round(float(s), 3)})
            print(f"[4/4] {len(net_new)} net-new / {len(redundant)} likely-redundant "
                  f"(cos>={args.redundancy_threshold} vs existing rag/)")
        except ImportError:
            print("[4/4] sentence-transformers absent  -  redundancy SKIPPED (no-embed).")
            net_new = valid
    else:
        net_new = valid

    # scorecard
    def pct(a, b):
        return round(100 * a / b, 1) if b else 0.0

    # Honesty: redundancy on WHOLE-FILE vectors is blind at snippet granularity
    # (a one-line snippet cannot match its own 34KB source file). 0-redundant is
    # blindness, not cleanliness  -  so net_new is an UPPER BOUND, never a clean count.
    redundancy_reliable = False   # always False in Phase 1 (whole-file embeddings)
    dup_pct = pct(len(cands) - len(uniq), len(cands))
    vrate = pct(len(valid), len(uniq)) if have_vcc else None
    # computed verdict  -  the re-wire question, answered by measurement
    reasons = []
    if dup_pct >= 20:
        reasons.append(f"{dup_pct}% exact duplication (higher with alpha-rename)")
    if vrate is not None and vrate < 80:
        reasons.append(f"only {vrate}% compile standalone  -  dominated by context-dependent "
                       "teaching fragments (vars from prior lines), not self-contained patterns")
    if not redundancy_reliable:
        reasons.append("redundancy vs existing rag/ is UNMEASURED (whole-file embedding blind "
                       "at snippet granularity); known-high Joy-of-VEX overlap unfiltered")
    verdict = "DO_NOT_REWIRE_AS_IS" if reasons else "ASSESS_FURTHER"

    scorecard = {
        "schema": "rewire_assessment/v1",
        "corpus": str(corpus_fp),
        "vcc_available": have_vcc,
        "raw_code_blocks": len(cands),
        "unique_snippets": len(uniq),
        "duplication_rate_pct": pct(len(cands) - len(uniq), len(cands)),
        "compile_valid": len(valid),
        "compile_rejected": len(invalid),
        "wrap_limited": len(wrapfail),
        "valid_rate_pct": pct(len(valid), len(uniq)) if have_vcc else None,
        "net_new": len(net_new),
        "likely_redundant": len(redundant),
        "redundancy_threshold": args.redundancy_threshold,
        "redundancy_reliable": redundancy_reliable,
        "redundancy_note": ("Phase 1 uses WHOLE-FILE embeddings; a snippet cannot match its "
                            "own source file, so 0-redundant is BLINDNESS not cleanliness. "
                            "True net-new << compile_valid (K.4 recon: ~65% is Joy-of-VEX "
                            "already in rag/). Needs Phase 3 section-level embeddings to measure."),
        "usable_entries_estimate": len(net_new),
        "usable_entries_note": ("UPPER BOUND only  -  = compile-valid unique, NOT redundancy-"
                                "filtered. Also includes trivial one-liners + tutorial fragments "
                                "too atomic/context-bound to be useful standalone RAG entries."),
        "usable_rate_vs_raw_pct": pct(len(net_new), len(cands)),
        "verdict": verdict,
        "verdict_reasons": reasons,
        "structural_finding": ("vex-corpus output is a chopped TUTORIAL TRANSCRIPT (sequential "
                               "fragments that reference vars/context from prior lines  -  Error "
                               "1067 x the plurality), NOT a library of standalone VEX patterns. "
                               "Re-wiring needs vex-corpus to emit self-contained patterns first."),
        "top_reject_errors": err_codes.most_common(8),
        "sample_rejects": [{"id": c["id"], "code": c["code"][:80], "why": c["why"]} for c in invalid[:10]],
        "sample_net_new": [{"id": c["id"], "code": c["code"][:80], "max_sim": c.get("max_sim")} for c in net_new[:10]],
        "most_duplicated": [{"code": k[:70], "count": n} for k, n in dup_mult.most_common(8)],
    }
    Path(args.out).write_text(json.dumps(scorecard, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 66)
    print("  RE-WIRE ASSESSMENT (K.6 Phase 1)")
    print("=" * 66)
    print(f"  raw code blocks         {scorecard['raw_code_blocks']:>6}")
    print(f"  unique snippets         {scorecard['unique_snippets']:>6}  ({scorecard['duplication_rate_pct']}% duplication)")
    if have_vcc:
        print(f"  compile-VALID (vcc)     {scorecard['compile_valid']:>6}  ({scorecard['valid_rate_pct']}% of unique)")
        print(f"  compile-REJECTED        {scorecard['compile_rejected']:>6}   {dict(err_codes)}")
        print(f"  wrap-limited (harness)  {scorecard['wrap_limited']:>6}")
    if not args.no_embed:
        print(f"  net-new vs rag/         {scorecard['net_new']:>6}")
        print(f"  likely-redundant        {scorecard['likely_redundant']:>6}")
    print("-" * 66)
    print(f"  usable est. (UPPER bound){scorecard['usable_entries_estimate']:>5}   "
          f"(redundancy UNMEASURED  -  whole-file blind)")
    print("=" * 66)
    print(f"  VERDICT: {verdict}")
    for r in reasons:
        print(f"    - {r}")
    print("=" * 66)
    print(f"  scorecard -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
