#!/usr/bin/env bash
# Crank 2, second pass: run the eight closure predicates that the SWEEP could
# not execute because they were stored truncated. Serialised on purpose - the
# 2026-09-05 referee nit was that concurrent gates sharing one
# SYNAPSE_PANEL_SETTINGS file made G3 report a false FAIL.
cd "$(git rev-parse --show-toplevel)" || exit 2
export PYTHONIOENCODING=utf-8
OUT=harness/cto/runs/2026-09-06/sweep_restored.txt
: > "$OUT"
for ID in "$@"; do
  PRED=$(python -c "
import json,sys
items={i['id']:i for i in json.load(open('harness/cto/BACKLOG.json',encoding='utf-8'))['items']}
sys.stdout.write(items['$ID']['closure_predicate'])
")
  echo "=== $ID" | tee -a "$OUT"
  OUTPUT=$(timeout 300 bash -c "$PRED" 2>&1)
  RC=$?
  echo "rc=$RC" | tee -a "$OUT"
  echo "$OUTPUT" | tail -6 | tee -a "$OUT"
  echo | tee -a "$OUT"
done
