#!/usr/bin/env python3
"""C1 - the token benchmark. Producer path for every figure in
``harness/notes/receipts/C1.json``.

WHAT THIS MEASURES
------------------
The claim under test is the positioning document's spine:

    "Sends only what changed - cost stays flat, even on huge scenes."
    versus the floor: "Re-sends your scene each turn - cost climbs with scene size."

An agent turn's input cost decomposes into:

    turn_tokens = FIXED(system + tool definitions)  +  VARIABLE(tool_result payload)

FIXED is scene-independent and already has a producer (``scripts/token_baseline.py``).
VARIABLE is the scene grounding a turn puts in front of the model, and it is the
only part that can climb with scene size. **This script measures VARIABLE**, on
real scenes, through the real shipped code paths, and reports the fixed part
beside it so the slope is never diluted by a large constant.

TWO ARMS
--------
arm A  SYNAPSE, inside-out. The shipped grounding surface, called with the
       arguments the shipped HANDLER passes (not the function defaults - they
       differ; see ARM_A_NOTE below).

arm B  The floor for sending-the-scene. NOT a competitor's product and not a
       strawman: it is SYNAPSE's OWN uncapped network serializer
       (``handlers_node._collect_nodes`` + ``_get_non_default_params``, the
       engine behind the shipped ``houdini_network_explain`` tool), plus the
       same ``inspect_scene`` code path as arm A with one argument changed.
       Because arm B emits only NON-DEFAULT parameters, it is a CONSERVATIVE
       floor - a naive outside-in tool that dumps every parameter pays strictly
       more. If arm B still climbs, the finding is robust in the safe direction.

MODES
-----
``--mode payloads``   Run under hython. Opens a scene, measures its size on
                      several axes, and writes the exact payload bytes each arm
                      would put on the wire. Does NOT tokenize (hython need not
                      carry tiktoken).

``--mode count``      Run under any Python with tiktoken. Tokenizes the emitted
                      payloads and writes the curve.

Splitting them keeps the tokenizer out of Houdini and gives each half its own
producer path.

TOKENIZER HONESTY
-----------------
Anthropic's exact tokenizer is an API call (``messages.count_tokens``). It is
UNAVAILABLE on this account - VERIFIED-RUNTIME 2026-07-27, HTTP 400
"credit balance is too low", which gates even the unbilled counting endpoint.
So this script reports, per payload:

    bytes, chars        exact, no caveat, re-derivable by anyone
    tokens_cl100k       tiktoken/cl100k_base - a DECLARED PROXY BPE,
                        explicitly NOT Claude's tokenizer

Same discipline and same declared proxy as the T.0 token baseline. The SHAPE of
the curve (flat vs climbing) is what the claim turns on, and shape is robust to
the tokenizer; absolute magnitudes carry the proxy caveat.

Usage:
    hython scripts/c1_token_bench.py --mode payloads --scene <path> --out <dir>
    python scripts/c1_token_bench.py --mode count --payload-dir <dir> --out <json>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "python"))

SCHEMA = "c1_token_bench/v1"

# The shipped handler passes include_geometry=False, but the FUNCTION signature
# defaults it to True (introspection.py:372 vs the handler). Calling the
# function directly with its own defaults would measure a payload the product
# never actually sends - and would flatter arm B by inflating arm A. We call
# handler-faithfully and record that we did.
ARM_A_NOTE = (
    "arm A calls the grounding functions with the arguments the SHIPPED HANDLER "
    "passes, not the function-signature defaults, which differ "
    "(introspection.py include_geometry default True vs handler False)."
)

# handlers.py:1467 - the shipped default depth for inspect_scene.
SHIPPED_INSPECT_SCENE_DEPTH = 3
# handlers_node.py:184 - network_explain clamps depth to 5.
NETWORK_EXPLAIN_MAX_DEPTH = 5


# ---------------------------------------------------------------- payloads --


def _canon(obj: Any) -> str:
    """Deterministic serialization.

    The panel worker puts tool results in front of the model via
    ``json.dumps(mcp_result, default=str)`` (claude_worker.py:263), so JSON is
    the right unit. sort_keys makes the count reproducible run-to-run, which is
    what the repeatability control (brief step B) actually tests.
    """
    return json.dumps(obj, sort_keys=True, default=str)


def _scene_axes(hou) -> Dict[str, Any]:
    """Measure scene size on several axes. 'Size' is not a number until defined,
    so we report all of them and let the receipt name which is the x-axis."""
    root = hou.node("/")
    all_nodes = list(root.allSubChildren())

    parm_count = 0
    sop = lop = 0
    for n in all_nodes:
        try:
            parm_count += len(n.parms())
        except Exception:
            pass
        try:
            cat = n.type().category().name()
            if cat == "Sop":
                sop += 1
            elif cat == "Lop":
                lop += 1
        except Exception:
            pass

    points = prims = 0
    for n in all_nodes:
        try:
            if n.type().category().name() != "Sop":
                continue
            if not n.isDisplayFlagSet():
                continue
            geo = n.geometry()
            if geo is None:
                continue
            # O(1) intrinsics - the cheap idiom shared/bridge.py:759 uses.
            points += int(geo.intrinsicValue("pointcount") or 0)
            prims += int(geo.intrinsicValue("primitivecount") or 0)
        except Exception:
            pass

    return {
        "node_count": len(all_nodes),
        "sop_node_count": sop,
        "lop_node_count": lop,
        "parm_count": parm_count,
        "displayed_point_count": points,
        "displayed_prim_count": prims,
    }


def _prime_lops(hou) -> int:
    """Cook LOP nodes so lastModifiedPrims()/errors() are populated.

    tests/test_inspect_live.py:292 records that headless hython has no viewport
    trigger; without this prime an inspect_stage payload is artificially SMALL,
    which would flatter arm A. Priming removes that bias.
    """
    cooked = 0
    try:
        stage = hou.node("/stage")
        if stage is None:
            return 0
        for n in stage.children():
            try:
                n.cook(force=False)
                cooked += 1
            except Exception:
                pass
    except Exception:
        pass
    return cooked


def _pick_target_node(hou) -> Optional[str]:
    """Deterministically pick the node an artist would most plausibly ask about:
    the one with the most parameters. Ties break by path, so the choice is
    reproducible across runs - a requirement of the repeatability control."""
    best = None
    best_key = (-1, "")
    for n in hou.node("/").allSubChildren():
        try:
            k = (len(n.parms()), n.path())
        except Exception:
            continue
        if k > best_key:
            best_key = k
            best = n
    return best.path() if best is not None else None


def emit_payloads(
    scene: Path,
    out_dir: Path,
    label: str,
    only: Optional[str] = None,
    prime: bool = True,
) -> Dict[str, Any]:
    """Open one scene and write every arm's exact wire payload.

    ``only`` restricts the run to a single named arm. A hard crash inside one
    arm (Houdini can segfault, which no ``except`` will catch) would otherwise
    take the whole rung with it — isolation lets the surviving arms still
    report, and lets the crashing one be named precisely instead of appearing
    as a blank rung.
    """
    import hou  # noqa: F401  (hython only)

    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    load_error = ""
    try:
        hou.hipFile.load(
            str(scene), suppress_save_prompt=True, ignore_load_warnings=True
        )
    except Exception as exc:  # noqa: BLE001 - a scene that will not open is a
        # finding, not a crash. Law 3: report what happened.
        load_error = f"{type(exc).__name__}: {exc}"
    load_s = time.perf_counter() - t0

    if load_error and not hou.node("/obj"):
        return {
            "label": label,
            "scene": str(scene),
            "status": "load_failed",
            "load_error": load_error,
            "load_seconds": round(load_s, 3),
        }

    cooked_lops = _prime_lops(hou) if prime else -1
    axes = _scene_axes(hou)
    target = _pick_target_node(hou)

    # -- The OUTCOME side of every measurement ------------------------------
    # Flat cost on a failed task is not a feature. The task is: "answer a
    # question about node N" - which a turn can only do if N is actually in
    # the payload. Ground truth is every node path in the scene; coverage is
    # the fraction of them a given payload puts in front of the model.
    # Cheap-because-it-answers-less is therefore visible, not hidden.
    ground_truth_paths = sorted(n.path() for n in hou.node("/").allSubChildren())

    from synapse.server.introspection import (  # noqa: E402
        inspect_scene,
        inspect_node_detail,
    )
    from synapse.server import handlers_node as hn  # noqa: E402

    payloads: Dict[str, Any] = {}
    errors: Dict[str, str] = {}

    def _run(name: str, fn) -> None:
        if only is not None and name != only:
            return
        # Flush before each arm so that if Houdini dies hard inside fn() the
        # last line on disk names the arm that killed it. A segfault cannot be
        # caught; it can only be attributed.
        sys.stderr.write(f"[c1] arm-begin {name}\n")
        sys.stderr.flush()
        try:
            payloads[name] = _canon(fn())
        except Exception as exc:  # noqa: BLE001
            errors[name] = f"{type(exc).__name__}: {exc}"
        sys.stderr.write(f"[c1] arm-end   {name}\n")
        sys.stderr.flush()

    # -- arm A: the shipped grounding surface, handler-faithful -------------
    _run(
        "A_inspect_scene_d3",
        lambda: inspect_scene(root="/", max_depth=SHIPPED_INSPECT_SCENE_DEPTH),
    )
    if target:
        _run(
            "A_inspect_node_detail",
            lambda: inspect_node_detail(
                target,
                include_code=True,
                include_geometry=False,   # handler-faithful; see ARM_A_NOTE
                include_expressions=True,
            ),
        )

    # -- arm B: the floor for sending the scene -----------------------------
    # B1: SYNAPSE's own uncapped network serializer (the engine behind the
    #     shipped houdini_network_explain tool). Conservative: non-default
    #     parms only, so a naive full-parm dump pays strictly more.
    def _b1() -> Any:
        out: List[Dict[str, Any]] = []
        for root_path in ("/obj", "/stage", "/mat", "/out"):
            root = hou.node(root_path)
            if root is None:
                continue
            for n in hn._collect_nodes(root, NETWORK_EXPLAIN_MAX_DEPTH):
                try:
                    key_params, expressions = hn._get_non_default_params(n, True)
                    entry: Dict[str, Any] = {
                        "node": n.name(),
                        "path": n.path(),
                        "type": n.type().name(),
                        "type_label": n.type().description(),
                        "inputs_from": sorted(
                            i.name() for i in n.inputs() if i is not None
                        ),
                        "outputs_to": sorted(
                            o.name() for o in n.outputs() if o is not None
                        ),
                        "key_params": key_params,
                    }
                    if expressions:
                        entry["expressions"] = expressions
                    out.append(entry)
                except Exception:
                    continue
        return {"data_flow": out, "node_count": len(out)}

    _run("B_network_explain_d5", _b1)

    # B2: the SAME code path as arm A, one argument apart. The fairest
    #     possible A/B - nothing differs but how much scene is sent.
    _run("B_inspect_scene_deep", lambda: inspect_scene(root="/", max_depth=99))

    # -- FLAT control: prove the meter can register "flat" -----------------
    # Without this the benchmark cannot distinguish "everything rises" from
    # "this particular thing rises" - and a curve that can only bend upward
    # is not an instrument (Law 1: state the condition under which it fails.
    # This arm fails if its token count varies with scene size).
    #
    # It is not a synthetic constant: it is SYNAPSE's ONE genuinely O(1)
    # grounding surface, the panel system prompt's live scene-context block
    # (system_prompt.py:224), which caps selection at 5 names + an "(+N more)"
    # count. Note what it costs to be flat: it carries no node, parm,
    # geometry or prim data, so it cannot ground a question about the scene.
    def _flat() -> Any:
        from synapse.panel.system_prompt import _format_scene_context

        return _format_scene_context({
            "network": "/obj",
            "selection": [n.name() for n in hou.selectedNodes()],
            "frame": int(hou.frame()),
            "hip": hou.hipFile.basename(),
        })

    _run("FLAT_scene_context", _flat)

    # B3: full composed USD, the honest floor for a USD-native outside-in tool.
    def _b3() -> Any:
        stage_node = hou.node("/stage")
        if stage_node is None:
            raise RuntimeError("no /stage")
        last = None
        for n in stage_node.children():
            last = n
        if last is None:
            raise RuntimeError("empty /stage")
        st = last.stage()
        if st is None:
            raise RuntimeError("node.stage() is None")
        return st.Flatten().ExportToString()

    _run("B_usd_flatten", _b3)

    written: Dict[str, Dict[str, Any]] = {}
    for name, text in payloads.items():
        p = out_dir / f"{label}__{name}.txt"
        p.write_text(text, encoding="utf-8")
        written[name] = {
            "file": p.name,
            "bytes": len(text.encode("utf-8")),
            "chars": len(text),
        }

    return {
        "label": label,
        "scene": str(scene),
        "status": "ok",
        "load_error": load_error,
        "load_seconds": round(load_s, 3),
        "cooked_lop_nodes": cooked_lops,
        "target_node": target,
        "axes": axes,
        "ground_truth_node_paths": ground_truth_paths,
        "payloads": written,
        "payload_errors": errors,
        "houdini_build": _houdini_build(),
        "arm_a_note": ARM_A_NOTE,
    }


def _houdini_build() -> str:
    try:
        import hou

        return str(hou.applicationVersionString())
    except Exception:
        return "unknown"


# ------------------------------------------------------------------ count --


def _tokenizer():
    """(method_label, count_fn). Declared proxy - Claude's tokenizer is an API
    call and this account cannot reach it (see module docstring)."""
    try:
        import tiktoken  # type: ignore

        enc = tiktoken.get_encoding("cl100k_base")
        return (
            "tiktoken/cl100k_base (proxy BPE, NOT Claude's tokenizer)",
            lambda s: len(enc.encode(s)),
        )
    except Exception:
        return (
            "chars_div_4 (proxy ratio - install tiktoken to sharpen)",
            lambda s: round(len(s) / 4.0),
        )


_QUOTED = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _model_visible(raw: str) -> str:
    """The string the MODEL is actually charged for, not the dict the tool returned.

    A tool result is encoded TWICE on the way to the model:
      1. ``mcp/tools.py:132`` wraps the result dict as
         ``{"content":[{"type":"text","text": <json of result>}]}``
      2. ``claude_worker.py:263`` then ``json.dumps`` that whole envelope,
         escaping every quote in the inner JSON.

    Counting the raw tool dict therefore UNDER-reports every arm. The
    inflation is roughly uniform, so it barely moves the A-vs-B ratio, but it
    matters for any absolute figure quoted to a studio. Both are reported.
    """
    return json.dumps(
        {"content": [{"type": "text", "text": raw}]}, default=str
    )


def _coverage(text: str, ground_truth: List[str]) -> Dict[str, Any]:
    """What fraction of the scene's nodes does this payload actually contain?

    THE OUTCOME HALF OF EVERY FIGURE. A turn cannot answer a question about a
    node it was never shown, so a payload that omits nodes is cheap and less
    capable — not cheap and equal. Reporting cost without this is the exact
    way a token benchmark flatters itself.

    Exact, not fuzzy: every arm's node-graph payload is JSON, so node paths
    appear as whole quoted string values. We take the set of quoted strings
    and intersect. No substring matching, so ``/obj/box1`` never counts as
    covering ``/obj/box10``.
    """
    if not ground_truth:
        return {"covered": 0, "total": 0, "fraction": None}
    quoted = set(_QUOTED.findall(text))
    covered = sum(1 for p in ground_truth if p in quoted)
    return {
        "covered": covered,
        "total": len(ground_truth),
        "fraction": round(covered / len(ground_truth), 4),
    }


def count(payload_dir: Path, out: Path) -> Dict[str, Any]:
    method, count_fn = _tokenizer()
    rungs: List[Dict[str, Any]] = []

    # A rung may arrive as one meta or as several partial metas, one per arm,
    # when crash isolation was needed. Merge by label so a rung reads the same
    # either way and a crashed arm shows up as a NAMED gap, not a missing rung.
    merged: Dict[str, Dict[str, Any]] = {}
    for meta_path in sorted(payload_dir.glob("*.meta.json")):
        m = json.loads(meta_path.read_text(encoding="utf-8"))
        lbl = m.get("label", meta_path.stem)
        if lbl not in merged:
            merged[lbl] = m
        else:
            merged[lbl].setdefault("payloads", {}).update(m.get("payloads", {}))
            merged[lbl].setdefault("payload_errors", {}).update(
                m.get("payload_errors", {})
            )

    for _lbl, meta in sorted(merged.items()):
        if meta.get("status") != "ok":
            rungs.append(meta)
            continue
        gt = meta.get("ground_truth_node_paths", [])
        counted: Dict[str, Any] = {}
        for name, info in sorted(meta.get("payloads", {}).items()):
            text = (payload_dir / info["file"]).read_text(encoding="utf-8")
            mv = _model_visible(text)
            raw_tok = count_fn(text)
            mv_tok = count_fn(mv)
            entry = {
                "bytes": info["bytes"],
                "chars": info["chars"],
                "tokens_cl100k": raw_tok,
                "tokens_cl100k_model_visible": mv_tok,
                "encoding_inflation": (
                    round(mv_tok / raw_tok, 4) if raw_tok else None
                ),
            }
            if name == "B_usd_flatten":
                # USDA carries PRIM paths, a different namespace from node
                # paths. Measured for COST only; scoring it for node coverage
                # would be a category error, so we say so rather than print 0.
                entry["coverage"] = {
                    "covered": None, "total": None, "fraction": None,
                    "note": "n/a - USD prim namespace, not node paths",
                }
            else:
                entry["coverage"] = _coverage(text, gt)
            counted[name] = entry
        meta = dict(meta)
        meta.pop("ground_truth_node_paths", None)  # keep the summary readable
        meta["counted"] = counted
        rungs.append(meta)

    result = {
        "schema": SCHEMA,
        "tokenizer": method,
        "tokenizer_caveat": (
            "Anthropic's exact tokenizer (messages.count_tokens) is unreachable "
            "on this account: HTTP 400 'credit balance is too low', "
            "VERIFIED-RUNTIME 2026-07-27. Absolute token figures carry this "
            "proxy caveat; bytes and chars do not, and the SHAPE of the curve "
            "is robust to tokenizer choice."
        ),
        "arm_a_note": ARM_A_NOTE,
        "rungs": rungs,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


# ------------------------------------------------------------------- main --


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("payloads", "count"), required=True)
    ap.add_argument("--scene")
    ap.add_argument("--label")
    ap.add_argument("--out", required=True)
    ap.add_argument("--payload-dir")
    ap.add_argument("--only", help="run a single named arm (crash isolation)")
    ap.add_argument("--no-prime", action="store_true",
                    help="skip the LOP cook prime (biases stage payloads SMALL)")
    args = ap.parse_args()

    if args.mode == "payloads":
        if not args.scene:
            ap.error("--mode payloads requires --scene")
        scene = Path(args.scene)
        label = args.label or scene.stem
        out_dir = Path(args.out)
        meta = emit_payloads(
            scene, out_dir, label, only=args.only, prime=not args.no_prime
        )
        suffix = f".{args.only}" if args.only else ""
        (out_dir / f"{label}{suffix}.meta.json").write_text(
            json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(json.dumps({k: v for k, v in meta.items() if k != "payloads"},
                         indent=2, sort_keys=True))
        return 0

    if not args.payload_dir:
        ap.error("--mode count requires --payload-dir")
    res = count(Path(args.payload_dir), Path(args.out))
    print(f"tokenizer: {res['tokenizer']}")
    for r in res["rungs"]:
        if r.get("status") != "ok":
            print(f"  {r.get('label')}: {r.get('status')}")
            continue
        ax = r["axes"]
        print(f"  {r['label']:<28} nodes={ax['node_count']:<6} "
              f"parms={ax['parm_count']:<7}")
        for name, c in sorted(r["counted"].items()):
            cov = c.get("coverage", {})
            frac = cov.get("fraction")
            cov_s = "  n/a" if frac is None else f"{frac * 100:5.1f}%"
            print(f"      {name:<26} {c['tokens_cl100k']:>9} tok"
                  f"  ({c['tokens_cl100k_model_visible']:>9} seen)"
                  f"   coverage {cov_s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
