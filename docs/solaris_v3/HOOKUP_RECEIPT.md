# RECEIPT integration handoff

Prepared against base `83ec6330857b7305e5b9ee74e74e6d92d4155200`, 2026-09-04.
These are unapplied integration patches. This worker did not edit the router,
panel entrypoint, handler, or frozen seam, and did not exercise the live GUI.

## Host ownership and contracts

Create exactly one host-owned `RequestDedup`, `EvidenceTracker`, and `ReceiptStore`
for the session. The panel receives `RecipeCard` snapshots; it does not construct
a store or run verification. No dependency on another stream's private module is
needed: all inputs are the frozen `RecipeSpec`, `RecipeInstance`, `CheckResult`,
`ApprovalBinding`, `RunRecipeRequest`, and `RunReceipt` types.

Host integration sequence:

1. Claim a validated `RunRecipeRequest` with `RequestDedup.claim(request)` before
   any effect. If `should_execute` is false, return the existing `job`; this is
   transport retry history, not evidence that a new scene is verified. Do not
   destroy this registry on panel refresh, undo, scene reset, or UI timeout.
2. Re-observe the owned scope before every new action. The injected fingerprint
   must use the SAME fingerprint definition as verifier `fingerprint_after`, and
   must describe current observations, not `RecipeInstance.authored_baseline`.
   Revision and recipe identity are checked separately. No full-stage hash on
   panel paint or the two-second UI refresh.
3. Install host-owned event adapters for `scene_load`, `undo`, `redo`, `owned_edit`,
   and `dependency_change`. Deliver `tracker.invalidate(event, at=aware_iso,
   instance_id=affected_id)`; omit the ID when scope is unknown. Scene load is
   always global. No H22 event-symbol guesses are supplied in this note.
4. Only after ALL event sources are covered call
   `tracker.set_tracking(True, since=coverage_started_at)`. Disconnect/gap calls
   `set_tracking(False)`. Reconnect cannot backdate coverage over a gap. Default
   UNKNOWN is intentional until the adapter is proven on H22. Timestamp equality
   invalidates conservatively. Supplementary scoped observation uses
   `periodic_recheck(observe)`; default interval is two seconds, minimum one.
   Schedule the hook on the host main thread before invoking it; it never
   dispatches to the host itself. Fingerprint callbacks read cheap observations.
5. For an approved render, construct `ApprovalScope` from trusted current
   instance ID/revision, engine, resolution, samples and output path. Pass it
   and trusted `ApprovalBinding` into `make_card`. An unmatched binding shows
   `AWAITING_APPROVAL`; an in-flight job remains RUNNING, with approval required
   for the next changed scope. AUTHORITY must independently recheck permission
   immediately before execution; a card is never an authorization token.
6. Transition the claimed request through `AWAITING_APPROVAL`/`RUNNING` as the
   host establishes those states. On timeout retain RUNNING until job termination
   is actually established. Never free the request ID to retry an uncertain job.
7. At terminal state, construct `make_receipt(...)` or
   `receipt_from_checks(...)`, passing all frozen-seam fields. Verifier supplies
   the checks; these helpers do not run them. Failed checks/verdicts need reasons.
   Append once with `ReceiptStore.append(receipt)` and attach it through
   `RequestDedup.transition(request_id, OperationState.TERMINAL, receipt=receipt)`.
   Persist before returning the completed response. `append` returns false for
   an exact same-run retry, rejects any changed evidence for that run, and never
   repairs malformed history. Persistence failure is not successful settlement.
8. Enumerate registry offers, including BLOCKED ones; make each card with explicit
   availability and a reason for blocking. Supply `tracker.freshness(receipt,
   instance)` and the current scope. `make_card` preserves historical verdicts
   separately from freshness. Expose `render_text` in plain-text responses and
   `render_html(card, tokens=existing_tokens)` in the panel.

The default ledger is this loaded checkout's
`harness/solaris_v3/ledger/receipts.jsonl`, configurable via the constructor path
or `SYNAPSE_RECIPE_LEDGER_DIR`. Runtime deployment must pick one stable host-owned
path; no worker wrote such a production ledger in this task. Stale `.lock` files
require established owner death before operator recovery. Host-crash/restart
dedup additionally needs a durable pending-job journal and reconciliation with
the actual renderer; the in-memory registry does not promise crash recovery.

## Exact panel display patch

The existing rail uses `QtWidgets`, `Qt` and a local layout `col`; existing
health-strip construction is at `synapse_panel.py:781`. The patch below adds a
display sink only. The host's observation delivery calls `set_recipe_cards`
on the panel's Qt main thread with the full registry-derived sequence.

```diff
--- a/python/synapse/panel/synapse_panel.py
+++ b/python/synapse/panel/synapse_panel.py
@@ -785,8 +785,25 @@
         except Exception:
             self._health_strip = None
 
+        self._recipe_card_label = QtWidgets.QLabel(w)
+        self._recipe_card_label.setTextFormat(Qt.RichText)
+        self._recipe_card_label.setWordWrap(True)
+        self._recipe_card_label.setText("Recipe evidence: UNKNOWN — awaiting host observation")
+        col.addWidget(self._recipe_card_label)
+
         self._region_cache["_build_rail"] = w
         return w
+
+    def set_recipe_cards(self, cards):
+        """Observe host-produced cards on the Qt main thread; never certify."""
+        from synapse.panel.recipe_card import render_html
+        from synapse.panel.designsystem import tokens
+        label = getattr(self, "_recipe_card_label", None)
+        if label is None:
+            return
+        snapshots = tuple(cards)
+        label.setText("<br/>".join(render_html(card, tokens=tokens) for card in snapshots)
+                      if snapshots else "Recipe evidence: UNKNOWN — no registry observation")
 
     def _format_tokens(self, n):
         """Token-count display rule for the rail meter — tokens only, no $:
```

Host adapter subscription is intentionally not fabricated: its transport and
event registration belong to the integrator. The sink above does not filter out
blocked cards. Keep the normal status tick cheap; it should repaint supplied
snapshots, not construct a tracker, compute stage hashes or access memory stores.
The renderer imports neither Qt nor design tokens; it receives already-loaded
tokens because their initial import can read the live host theme.

## S8 current-scene response-cache safeguard

At the base checkout `router.py:282` replays recipe results, including commands,
responses and `success`. `_try_recipe` and `_try_plan` both store these under the
`recipe` tier (`:463`, `:530`). A repeated prompt after scene reset can therefore
return old evidence. Apply this exact conservative patch; it also ignores older
effectful entries already in memory. Pure text response caching remains.

```diff
--- a/python/synapse/routing/router.py
+++ b/python/synapse/routing/router.py
@@ -280,9 +280,11 @@
         # 0.5. Cache check (He2025)
         # ---------------------------------------------------------------
         if self._config.enable_cache:
-            for tier_name in ("recipe", "instant", "fast", "standard", "deep"):
+            for tier_name in ("instant", "fast", "standard", "deep"):
                 cached = self._cache.get(tier_name, input_text, context_hash)
                 if cached is not None:
+                    if cached.commands or cached.responses:
+                        continue
                     result = RoutingResult(
                         success=cached.success,
                         tier=cached.tier,
@@ -990,7 +992,9 @@
     def _cache_result(
         self, tier: str, text: str, context_hash: str, result: RoutingResult
     ):
-        """Store result in cache if enabled."""
+        """Cache pure text only; an operation outcome is scene-local history."""
+        if tier == "recipe" or result.commands or result.responses:
+            return
         if self._config.enable_cache:
             self._cache.put(tier, text, context_hash, result)
 
```

For v3, the four supported recipe actions should reach the dedicated constrained
handler, whose new-request path re-observes and whose retry path uses RequestDedup.
Cache compiled declarative specs with `SpecCache.put(spec_digest(spec), spec)`.
This digest includes every specification field, including build/layout metadata;
it is deliberately not just the semantic graph digest. It never includes a run
verdict. The guard also rejects outcome payloads smuggled into nested metadata.

Integrator controls for this patch (not run by this worker): route an identical
prompt under identical context, reset the scene, issue a NEW request ID and prove
the host observes/rebuilds; seed an old effectful ResponseCache entry and prove it
is ignored; retry a LOST response with the SAME request ID and prove the original
job is returned. Broader router behavior changes need its existing tests rerun.
