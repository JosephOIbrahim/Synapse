# SYNAPSE v5.45.1 — CI-green patch on the cache-advisor release

Released 2026-08-09, minutes after v5.45.0. Product code unchanged.

## Why a patch

v5.45.0's tag gate ran its own suite green locally, but the repo CI (ubuntu, no Houdini)
went red on one new test: `test_decide_cache_handles_real_host_probe_unknown_shaped_machine_profile`
*hoped* the environment would yield an unknown-shaped machine profile instead of *forcing* it.
On Linux, the probe's stdlib tier honestly reads real available RAM from `/proc/meminfo` —
the probe was correct on every platform; the test was platform-naive.

## The fix (e417c7aa)

The test now forces BOTH ram-detection tiers off (psutil and the `/proc/meminfo` stdlib
path), constructing the unknown shape by design rather than by environmental accident.
Six lines, one test file. CI green at this tag.

## Also rolled up

Wave-2 capsule documentation (in-flight W1 Moneta + insert-slice builds, autonomous
closer protocol). No runtime code changes since v5.45.0.
