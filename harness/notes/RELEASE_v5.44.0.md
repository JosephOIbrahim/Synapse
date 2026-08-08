# v5.44.0

## Honesty and hardening

- **Honest-green CI.** Master's inherited red is cured: two real-rot
  failures fixed (not skipped), environment-gated tests marked with
  visible reasons, `needs_houdini` marker introduced. A green check now
  means every test that could run, ran.
- **Fidelity indicator tells the truth.** Unmeasured renders UNKNOWN -
  never a number, never a fabricated 1.0.
- **Scout warns about stale authority.** An external / no-Houdini
  process grounding against the prior-major table now says so instead of
  reporting it fresh. (R-M5b-1)
- **Scene compose can no longer litter foreign folders.** Unsaved-scene
  writes are refused at the write site; saved-state is the oracle.
  Live-probed on 22.0.368.
- **Freeze instrumentation shipped.** Qt result-path timing + payload
  telemetry and a one-command live repro protocol (FRZ_REPRO.md).
  Attribution tooling; no behavior change.
- **Dispatcher hardening.** Per-leg base refs and per-manifest model
  honored at dispatch; the wrong-base failure class is closed.

## Known issue (disclosed, fix scheduled next release)

- The Moneta memory store fails to open when the configured embedder
  dimension mismatches the persisted index (observed 384 vs 256), and
  in this build that failure is silent - memory persistence is
  unreliable until v5.44.x. Root cause and evidence:
  harness/notes/PRST_SEAM_A_REPORT.md. All non-memory features are
  unaffected.
