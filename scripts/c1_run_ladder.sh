#!/usr/bin/env bash
# C1 - drive the scene ladder. Producer path for harness/notes/c1/ladder.json.
#
# Every rung runs TWICE (--run 1 and --run 2). That is the repeatability
# control, and it runs BEFORE any figure is trusted: a benchmark that has not
# established its own noise floor is a picture, not evidence.
#
# Each (scene, run) gets its OWN hython process. Loading a second scene over a
# first in one session leaves residue - managers, cached defs, stale stages -
# which would make run 2 differ from run 1 for reasons that have nothing to do
# with token counts.
#
# All six rungs are SideFX-authored scenes shipped with Houdini 22.0.368. None
# was built for this benchmark.
set -u

HYTHON="C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe"
HH="C:/Program Files/Side Effects Software/Houdini 22.0.368/houdini"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$REPO/.c1out}"

mkdir -p "$OUT"

# label                       path
SCENES=(
  "L1_color_falloff|$HH/help/files/color_falloff.hip"
  "L2_obj_xform|$HH/help/files/obj_xform.hip"
  "L3_RandomExample|$HH/help/files/expression_cookbook/RandomExample.hip"
  "L4_three_point_lighting|$HH/starters/three_point_lighting.hip.gz"
  "L5_ocean|$HH/help/files/pdg_examples/top_ocean/ocean.hip"
  "L6_karma_user_guide|$HH/help/files/karma_user_guide/karma_user_guide.hip"
)

# Arms, for the per-arm fallback. Houdini can SEGFAULT inside an arm, and a
# segfault is not catchable in-process - it takes the whole rung with it. When
# the combined run dies we re-run arm by arm, so the surviving arms still
# report and the crashing arm is named rather than silently missing.
ARMS=(
  "A_inspect_scene_d3"
  "A_inspect_node_detail"
  "B_network_explain_d5"
  "B_inspect_scene_deep"
  "B_usd_flatten"
  "FLAT_scene_context"
)

for run in 1 2; do
  for entry in "${SCENES[@]}"; do
    label="${entry%%|*}"
    scene="${entry#*|}"
    tag="${label}__r${run}"
    if [ ! -f "$scene" ]; then
      echo "MISSING $label -> $scene"
      continue
    fi
    echo "=== run $run : $label ==="
    start=$(date +%s)
    "$HYTHON" "$REPO/scripts/c1_token_bench.py" \
        --mode payloads --scene "$scene" --label "$tag" \
        --out "$OUT" > "$OUT/${tag}.stdout.txt" 2>&1
    rc=$?
    echo "    combined rc=$rc  $(( $(date +%s) - start ))s"

    if [ ! -f "$OUT/${tag}.meta.json" ]; then
      echo "    combined run produced no meta -> per-arm isolation"
      for arm in "${ARMS[@]}"; do
        astart=$(date +%s)
        "$HYTHON" "$REPO/scripts/c1_token_bench.py" \
            --mode payloads --scene "$scene" --label "$tag" --only "$arm" \
            --out "$OUT" > "$OUT/${tag}.${arm}.stdout.txt" 2>&1
        arc=$?
        if [ -f "$OUT/${tag}.${arm}.meta.json" ]; then
          echo "      $arm rc=$arc  $(( $(date +%s) - astart ))s"
        else
          echo "      $arm CRASHED rc=$arc  $(( $(date +%s) - astart ))s"
        fi
      done
    fi
  done
done

echo "ALL DONE -> $OUT"
