"""W4-RULING regen probe — crucible re-execution of the bookish-AST source ruling.

Runs the EXACT call chain the xref agent claimed (recon doc line 178 /
.token-saver/h22-context-recon-wave2.md:512), on the LIVE 22.0.400 build, into a
SYNAPSE-owned scratch cache (NEVER the user's OneDrive help cache), and records:

  * /nodes/ page count + error tally + wall time  (verifies C1: 5,481 / 170s / 0 err)
  * per-context page counts                        (verifies C-beyond-zip: sop1563/lop209/out78)
  * per-context attrs.id coverage on parameters_item (verifies C3: cop99/top97/lop75/sop64/vop57)
  * APEX section typing: inputs_section/outputs_section/parameters_item counts (verifies C4)
  * spot-checks: sop/xform attrs.id == t,r,s ; an apex sample (verifies C4)
  * JSON files + bytes written to the cache dir     (verifies C1 72MB / C2 6,281 files)

Truth discipline: every number here is OBSERVED by this run. STEP tracks the exact
call in flight; any exception writes a FAILED sentinel naming that step (that is the
"exact failing step" the acceptance contract asks for when a claim is UNKNOWN).

Run headless, detached, under 22.0.400 hython. Writes DONE / FAILED sentinels.
Read-only against Houdini: parses help pages, writes only to OUT (scratch).
"""
import os, sys, time, json, traceback, glob

OUT = r"C:/Users/User/AppData/Local/Temp/claude/C--Users-User-SYNAPSE--claude-worktrees-w4-ruling/eb92a224-6ea7-47b7-99bb-fd13096fd608/scratchpad/w4regen"
CACHE_DIR = os.path.join(OUT, "ast_cache")
LOG = os.path.join(OUT, "regen.log")
DONE = os.path.join(OUT, "DONE")
FAILED = os.path.join(OUT, "FAILED")
RESULT = os.path.join(OUT, "regen_result.json")

os.makedirs(CACHE_DIR, exist_ok=True)
# Hard safety: refuse to run if the cache dir is anywhere near the user's OneDrive.
assert "OneDrive" not in CACHE_DIR, "refusing to write into the user's OneDrive cache"

_logf = open(LOG, "w", encoding="utf-8", buffering=1)
def log(*a):
    msg = " ".join(str(x) for x in a)
    _logf.write(msg + "\n")

STEP = "init"
def fail(exc):
    payload = {"step": STEP, "error": repr(exc), "trace": traceback.format_exc()}
    with open(FAILED, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    log("FAILED at step:", STEP, repr(exc))
    log(traceback.format_exc())
    _logf.close()
    sys.exit(1)


def walk_nodes(node, fn):
    """Depth-first over the bookish AST: call fn(dict) for every dict that has a
    'type' key; recurse into every dict value and list element."""
    if isinstance(node, dict):
        if "type" in node:
            fn(node)
        for v in node.values():
            walk_nodes(v, fn)
    elif isinstance(node, list):
        for v in node:
            walk_nodes(v, fn)


try:
    STEP = "import hou"
    import hou
    appver = hou.applicationVersionString()
    log("hou.applicationVersionString() =", appver)

    STEP = "import houdinihelp.hconfig/hpages"
    from houdinihelp import hconfig, hpages

    STEP = "import bookish.util"
    import bookish.util as butil

    STEP = "read_houdini_config"
    cfg = hconfig.read_houdini_config(use_houdini_path=True)
    orig_cache = cfg.get("CACHE_DIR")
    log("default CACHE_DIR (untouched) =", orig_cache)
    cfg["CACHE_DIR"] = CACHE_DIR
    log("overridden CACHE_DIR =", cfg.get("CACHE_DIR"))

    STEP = "pages_from_config"
    pages = hpages.pages_from_config(cfg)

    STEP = "get_prefixed_paths(/nodes/)"
    allpaths = list(butil.get_prefixed_paths(pages, "/nodes/"))
    log("get_prefixed_paths yielded:", len(allpaths))

    STEP = "filter is_wiki_source/exists"
    paths = [p for p in allpaths if pages.is_wiki_source(p) and pages.exists(p)]
    log("wiki-source & exists paths:", len(paths))

    # per-context accumulators
    ctx_pages = {}          # ctx -> page count (parsed ok)
    ctx_items = {}          # ctx -> parameters_item count
    ctx_items_id = {}       # ctx -> parameters_item with attrs.id
    ctx_items_ch = {}       # ctx -> parameters_item with attrs.channels
    ctx_inputs = {}         # ctx -> inputs_section node count
    ctx_outputs = {}        # ctx -> outputs_section node count
    spot = {}               # path -> list of attrs.id on parameters_item

    def ctx_of(p):
        # "/nodes/sop/xform" -> "sop"
        parts = [s for s in p.split("/") if s]
        return parts[1] if len(parts) >= 2 and parts[0] == "nodes" else "?"

    SPOT_PATHS = {"/nodes/sop/xform", "/nodes/sop/attribwrangle", "/nodes/lop/light",
                  "/nodes/top/ropfetch", "/nodes/cop/blur"}

    STEP = "regen loop"
    t0 = time.time()
    ok = 0
    err = 0
    errors = []
    apex_pages = 0
    apex_inputs = apex_outputs = apex_params = 0
    for i, p in enumerate(paths):
        try:
            data = pages.json(p, conditional=False, postprocess=False, save_to_cache=True)
        except Exception as e:  # per-page: record, do not abort the run
            err += 1
            if len(errors) < 60:
                errors.append({"path": p, "err": repr(e)})
            continue
        ok += 1
        ctx = ctx_of(p)
        ctx_pages[ctx] = ctx_pages.get(ctx, 0) + 1

        counts = {"pi": 0, "pi_id": 0, "pi_ch": 0, "in": 0, "out": 0}
        ids_here = []
        def visit(node, _c=counts, _ids=ids_here):
            t = node.get("type")
            if t == "parameters_item":
                _c["pi"] += 1
                attrs = node.get("attrs") or {}
                _id = attrs.get("id")
                if _id:
                    _c["pi_id"] += 1
                    _ids.append(_id)
                if attrs.get("channels"):
                    _c["pi_ch"] += 1
            elif t == "inputs_section":
                _c["in"] += 1
            elif t == "outputs_section":
                _c["out"] += 1
        walk_nodes(data, visit)

        ctx_items[ctx] = ctx_items.get(ctx, 0) + counts["pi"]
        ctx_items_id[ctx] = ctx_items_id.get(ctx, 0) + counts["pi_id"]
        ctx_items_ch[ctx] = ctx_items_ch.get(ctx, 0) + counts["pi_ch"]
        ctx_inputs[ctx] = ctx_inputs.get(ctx, 0) + counts["in"]
        ctx_outputs[ctx] = ctx_outputs.get(ctx, 0) + counts["out"]

        if ctx == "apex":
            apex_pages += 1
            apex_inputs += counts["in"]
            apex_outputs += counts["out"]
            apex_params += counts["pi"]

        if p in SPOT_PATHS:
            spot[p] = ids_here

        if i % 500 == 0:
            log("  ... %d/%d  ok=%d err=%d  %.1fs" % (i, len(paths), ok, err, time.time() - t0))

    elapsed = time.time() - t0

    STEP = "count cache files"
    cache_files = glob.glob(os.path.join(CACHE_DIR, "**", "*"), recursive=True)
    cache_json = [f for f in cache_files if os.path.isfile(f)]
    cache_bytes = sum(os.path.getsize(f) for f in cache_json)

    # per-context attrs.id coverage (per parameters_item)
    ctx_cov = {}
    for c in sorted(ctx_items):
        n = ctx_items[c]
        ctx_cov[c] = round(100.0 * ctx_items_id.get(c, 0) / n, 1) if n else None

    result = {
        "appver": appver,
        "default_cache_dir": orig_cache,
        "cache_dir_used": CACHE_DIR,
        "paths_enumerated": len(allpaths),
        "paths_wiki_exists": len(paths),
        "parsed_ok": ok,
        "parse_errors": err,
        "elapsed_s": round(elapsed, 1),
        "ms_per_page": round(1000.0 * elapsed / max(ok, 1), 1),
        "cache_files_written": len(cache_json),
        "cache_bytes": cache_bytes,
        "cache_mb": round(cache_bytes / 1e6, 1),
        "ctx_pages": ctx_pages,
        "ctx_items": ctx_items,
        "ctx_items_with_id": ctx_items_id,
        "ctx_items_with_channels": ctx_items_ch,
        "ctx_id_coverage_pct": ctx_cov,
        "ctx_inputs_section": ctx_inputs,
        "ctx_outputs_section": ctx_outputs,
        "apex_pages": apex_pages,
        "apex_inputs_section": apex_inputs,
        "apex_outputs_section": apex_outputs,
        "apex_parameters_item": apex_params,
        "spot_checks": spot,
        "errors_sample": errors,
    }
    with open(RESULT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    log("RESULT written:", RESULT)
    log("pages ok=%d err=%d in %.1fs  cache_files=%d  %.1fMB"
        % (ok, err, elapsed, len(cache_json), cache_bytes / 1e6))

    with open(DONE, "w", encoding="utf-8") as f:
        f.write("ok=%d err=%d elapsed=%.1f\n" % (ok, err, elapsed))
    _logf.close()

except SystemExit:
    raise
except Exception as e:
    fail(e)
