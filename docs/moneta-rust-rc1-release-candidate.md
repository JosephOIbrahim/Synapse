# Combined inspection and Moneta Rust release candidate

Preparation only. No release version, installer, live adoption, or publication is
approved by this document. The isolated SYNAPSE candidate starts at published
`e7a2e1e023b2788eb077b569f6f9500d3a0d9e2c` and includes the six-file inspection
change from `4ee8f2589f4865e63f3d54dca028a112aa1c343a`, plus its focused recovery
and first-party consumer controls. External consumers remain unknown. `VERSION`
remains `5.97.2` until combined scope review.

## Exact Moneta input

Use published Moneta `v1.3.0-rc1`, commit
`c33bbd96dd9c21d84096f147554eaaa3e2197a92`, through the existing
`MonetaBackedStore` and `moneta_runtime` adapter. The CI checkout is pinned to
that full commit. Its current install/import check proves Python availability
only. It does not build, load, or prove execution of the Rust extension.

The GitHub release has no binary assets. A separate preparation task owns one
bounded build from that exact commit. Release qualification must bind its clean
source state, toolchain, lockfile, wheel and extracted `.pyd` hashes. An older
wheel with unknown provenance is not an accepted input. The exact commit's
`pyproject.toml` declares `moneta` version `1.3.0rc1`, Python >=3.11, and no runtime
dependencies. SYNAPSE's optional `moneta` extra pins that full Git commit by PEP
508 direct reference; a version string alone does not pin code.

### Installation inputs for later approved qualification

Use a new disposable environment with Python >=3.11. Install the candidate's
`moneta` extra only with the existing authorized private-repository credentials;
its direct reference resolves the exact core commit above. Do not substitute a
branch, another checkout, or a version-only index lookup. The core package does
not build or bundle the Rust extension. Install the separately built
`moneta_native` wheel only after its exact-commit build receipt and wheel/`.pyd`
hashes are verified, and only into that disposable environment. This preparation
does not install anything.

An offline alternative is an already prepared clean core source copy pinned to
the same commit, explicitly placed on the qualification process's isolated
`sys.path`, plus the verified native wheel's isolated extraction path. Compare
loaded module origins and hashes; an older installed `moneta` can otherwise win
over `MONETA_SRC`. This offline path performs no live-package installation and
does not change `packages/synapse.json` or any desktop identity input.

Do not use unpublished hardening commit
`a4f2b0b812e89f522fe0220cd0364f5472e503eb`, Moneta v5 preview APIs, or invented
`require`, `native_status`, `build_info`, or counter APIs. Preserve the v1 API
and snapshot format. The existing SYNAPSE adapter continues to construct the
default VectorIndex/ECS; no adapter production code change is proposed here.

## Focused integration gates

Run only in isolated Python environments with the exact core source and
extracted native artifact explicitly placed before installed packages. Record
the actual module origins and file hashes before and after each process. Use
disposable stores, fixed finite vectors from the existing deterministic
`HashEmbedder`, and a fixed corpus with explicit memory identities and times.
No live Houdini, USD schema registration, license, model/API, or production-store
claim follows from these tests.

1. Use fresh processes with `MONETA_NATIVE=0` and `MONETA_NATIVE=1`; it is read at
   handle construction, not a live switch. Assert `handle.vector_index.backend`
   and `handle.ecs.native_decay` before and after ordinary nonempty adapter text
   recall. Setting `MONETA_NATIVE=1` alone is not a fail-closed native gate: the
   published RC can silently fall back when the extension is absent.
2. Observe the actual native bound `ScanIndex.scan` and exported `decay_batch`
   calls using standard CPython profiling, without patching Moneta or the
   production adapter. Require both `c_call` and successful `c_return` events
   for both operations during ordinary adapter recall in the native arm, and
   neither operation in the off arm. Restore the previous profiler. If this
   interpreter cannot expose those events, report an unclosed gate. The
   observability proposal has not yet been executed on these artifacts.
3. Match off/on results, payloads, counts and ranking using the same corpus and
   query order. Check finite outputs and exercise the existing keyword fallback
   deliberately as a separate case. Native completion must not be inferred from
   fallback results or from a successful import.
4. Run the relevant non-Houdini tests from `test_moneta_store.py`,
   `test_moneta_search_serialization.py`, `test_backfill.py`,
   `test_store_backend_health.py`, and `test_m3_env_conformance.py` with explicit
   pass/fail/error/skip accounting. A skipped native test does not satisfy its
   gate. Verify source/backfill inputs remain unchanged. Use an absent-extension
   negative arm to show that a claimed Rust qualification fails even though
   normal optional-backend fallback remains supported.
5. Exercise save/close/fresh-process reopen on disposable data and verify IDs,
   payloads and count. Keep crash durability, fsync, snapshot failure, B/D and
   path-L concerns explicitly open unless a specific check closes them. No
   blanket risk acceptance is implied. Time matched recall separately with
   profiling disabled; do not claim speed from instrumentation runs.

Proposed caps for parent review: 30 seconds per proof/negative process; 120
seconds per focused pytest arm; a 20-minute integration envelope including
receipt writing. Close stores in `finally`. End only exact processes created by
these runs if their individual cap expires; never discover or terminate shared
processes. Preserve every failed receipt and stop on unexpected side effects or
provenance drift. Do not expand scope to make a failing claim pass.

The source-test receipts outside this checkout record the current result. The
preserved fourth batch had 227 passing assertions but a failed overall receipt:
the guard denied two tracked-file preservation Git reads and JUnit hostname
metadata's three Windows version commands. That metadata path could also attempt
WMI before its fallback, which the old receipt did not record. It remains
unqualified. The corrected runner uses fixed metadata, blocks `_wmi` before test
imports, and permits only the two exact repository-local Git reads. No native
integration result is claimed.

## Bounded two-hour improvement loop

The clock has not started. Start only after the assembled candidate passes the
integration gates and the baseline task corpus, versions, file hashes and test
commands are frozen. The corpus is the focused inspection suite plus the fixed
Moneta adapter corpus, off/on proof, parity and disposable reopen cases above.
Use local deterministic tests first. No paid model calls are authorized outside
the separately bounded review bridge.

Budget exactly 120 minutes: first 10 minutes for the frozen baseline; up to five
cycles of at most 17 minutes each; final 25 minutes for a matched final comparison
and checkpoint. Each cycle states one small hypothesis, changes one bounded
behavior in this isolated checkout, and runs the same correctness/native gates
and comparison. Retain a change only when it preserves correctness and native
proof and improves its stated measure; otherwise restore only that cycle's owned
patch while preserving its diff and receipts. Do not run production stores,
Kestrel, live scenes, the open Claude workspaces, models or GUI. Do not extend
the clock for a promising but unfinished cycle.

The hard user cutoff is **2026-10-17 13:00 UTC** (09:00 America/New_York). Use a
conservative latest loop start of **10:30 UTC**, leaving up to 30 minutes after
the loop for final exact-SHA release checks and safe checkpointing. Start earlier
or decline the loop if remaining release work cannot fit; the deadline never
waives a gate. At cutoff, start no further SYNAPSE engineering. Preserve state
and return control for the requested lightweight robot/Solaris demo v1; Kestrel
stays paused for demo v2. Do not terminate unrelated or user processes.

Every retained loop change requires final tests and review on the exact release
SHA. Publication is coordinated by the parent after candidate evidence and Opus
review; a source pass does not publish anything automatically.
