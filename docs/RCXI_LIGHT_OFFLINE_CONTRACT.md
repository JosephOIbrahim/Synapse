# Bounded light gate: offline contract

Status: **synthetic implementation contract, not ratified architecture or live qualification**. The sole protected operation proposed for host integration is `solaris.iterate.light`: change the captured recipe key-light exposure. The existing recipe executor, transaction ownership, main-thread dispatch and recovery must be checked before a host adapter is implemented.

## Operation and objective

A request identifies one recipe instance, its expected revision, its captured key-light binding and one finite exposure target. It contains no node path, code, file destination, provider call or approval token. Explicit profile bounds constrain the target. All other light values, node/edge counts and outside-state digest must remain unchanged. Unknown tracking, disabled undo or a stale revision refuses before mutation.

Success means independently observed key-light exposure has normalized error `abs(observed-target) / max(1, abs(target))` within an explicitly supplied tolerance, invariant violation is zero, and measured tension is within the supplied limit. The normalized error is an engineering objective for one scalar exposure edit; it is not image quality or a render metric.

## Six measurements

| Component | Defined offline meaning | Required future producer |
|---|---|---|
| task loss | Normalized exposure error above | Trusted host reread of captured key light |
| execution milliseconds | Reported duration of one completed trial | Host/process instrument independent of mutator |
| peak memory MB | Reported process peak for the trial's documented window | Independent known-child monitor; not a guessed Python allocation count |
| complexity delta | Change in node count plus edge count | Detached before/after host graph capture; individual counts are also invariant-checked |
| state entropy | Shannon bits of the captured recipe light-exposure histogram, using explicit fixed bin width | Trusted complete capture of that documented light set |
| invariant violation | 1 for an escaped scope, changed outside digest/topology, wrong revision/binding or unknown/changed tracking; otherwise 0 | Trusted full-scope snapshot and ownership evidence |

Entropy is a narrow histogram statistic, not scene complexity, artistic uncertainty or a claim about cognition. A synthetic snapshot is not a complete Houdini authored-state capture. Future host measurements must establish completeness rather than infer it from a matching digest.

## Calibration and decision

The profile requires all numeric choices explicitly: a six-by-six positive-definite covariance, loss weight, tension limit, loss tolerance, histogram width, exposure bounds, maximum attempts, measured-work budget and no-progress limit. There are **no production defaults**. Optional synthetic sample covariance uses the unbiased sample estimator plus six explicitly supplied positive diagonal regularizers; it does not learn thresholds.

Tension is `sqrt(delta^T covariance^-1 delta) + loss_weight * observed_loss`, computed by Cholesky solve. All six dimensions participate. Singular/invalid profiles refuse. Production constant dimensions, units, regularization, calibration population and threshold selection remain unvalidated. Copying a blueprint threshold cannot calibrate this operation.

Each trial seals an identity-bound forecast before dispatch. The synthetic ledger is volatile and labelled SYNTHETIC; its receipt proves neither durable external custody nor crash safety. A changed/missing acknowledgement or replayed trial cannot dispatch or converge. Mutator return values are ignored; a separate injected observer supplies the fixture state/costs.

Each run revalidates and copies the complete frozen profile, binds its content hash into every forecast and the returned fixture result, and uses only that copy for measurement definitions, tension, convergence and fuel. A content change through a callback refuses before dispatch or triggers guarded recovery after dispatch. Replacing the configuration with equivalent content retains the same identity. A different profile may be selected between separate runs; it cannot retroactively relax a sealed run. This is a cooperative Python fixture contract, not protection against arbitrary code changing interpreter classes or globals.

The fixture controller permits convergence only with acceptable loss, tension and invariants. Otherwise it restores the exact pre-request fixture state before another trial. A consecutive lack of measured task-loss improvement triggers thrash rollback. Attempts and accumulated observed execution time enforce fixture fuel. This does not preempt a blocked real host call or implement a process deadline.

Recovery requires a complete current snapshot equal to the observed latest state, the expected latest transaction owner, unchanged known foreign-edit epoch and enabled known undo tracking. Recovery is attempted once and checked by an independent reread. Changed/unknown ownership, failed reread or residual state quarantines rather than blindly retrying or undoing an artist action.

## Required tests and pending host work

Offline acceptance covers hand-computed correlated tension/covariance/entropy, convergence, more fuel, thrash, exhausted attempts/time, wrong forecasts, missing/tampered ledger, replay after controller replacement, incomplete measurements, escaped scope, foreign edits, failed recovery and the second composed action. Deliberate safety mutations must turn tests red.

Fixture terminal states say FIXTURE_CONVERGED, FIXTURE_ROLLED_BACK, FIXTURE_CANCELLED or FIXTURE_QUARANTINED. Cancellation is checked before and after dispatch; an already-mutated fixture must be independently restored before cancellation is reported terminal. This is not a host interruption mechanism. The live entry point always reports UNAVAILABLE. Marker strings and separate Python objects are not an operating-system trust boundary or hostile-code sandbox.

Still pending: durable external forecast/measurement custody, actual host timing/peak memory, complete Houdini captures, configured LIGHT executor, main-thread/terminal recovery integration, foreign-edit evidence, process deadlines, restart/crash recovery, calibration on representative work, safe fresh H22 qualification and independent release review. No network, live stores, scene edits or tool promotion are activated by this offline component.

The existing real `BuildTransaction` commits lifecycle state and releases ownership before returning, and its recovery skips committed outcomes. A real rejection-capable gate must therefore evaluate a provisional candidate before lifecycle acceptance while retaining proven ownership. The fixture controller does not implement that host seam. Reusing a completed transaction's snapshots cannot establish post-commit rollback, and a main-thread callback must not block on a remote model.
