# Anthropic SDK 2.x — the model-access guard does not speak it

**Severity:** P1 (shipped product refuses every model call under anthropic >= 2)
**Status:** Contained by a dependency pin · the 2.x migration itself is unstarted
**Filed:** 2026-10-23
**Found by:** the v5.97.7 release CI run (40055119062), 5 of 6 jobs red
**Environment:** anthropic 2.3.0 · httpx2 2.16.0 · jiter 0.18.0 · Python 3.11 and 3.14

---

## Summary

`python/synapse/model_access.py` verifies the API key on the outgoing request and refuses any
request that carries an `Authorization` header. The guard is written against the **1.x** auth
convention: the SDK sends the key in `x-api-key` and sends no `Authorization` header.

**anthropic 2.x changed both.** It sends the key as `Authorization: Bearer <key>` and drops
`x-api-key` entirely. It also moved the protocol header from `anthropic-version: 2023-06-01`
to `anthropic-version: 2026-10-21`.

So under 2.x the guard's own check fires on every request:

```
ModelAccessDenied: The model request changed after permission was checked.
```

This is not a test artifact and not a CI artifact. **Every guarded model call in the shipped
product is denied under anthropic 2.x.** The panel, the agent loop, and `agent/model_rules.py`
(which imports `guarded_create` and `make_anthropic_client` from `synapse.model_access`) all
go through this path.

## Evidence

The guard's comparison, measured on the real wire request (not inferred):

| anthropic | key header sent | `Authorization` | `anthropic-version` | result |
|---|---|---|---|---|
| 0.75.0 | — | — | — | **fails earlier**, at `_sdk_state` (`model_access.py:570`) — the SDK is too old to have the private attributes the guard inspects |
| 0.96.0 (vendored) | `x-api-key` | none | 2023-06-01 | passes |
| 1.0.0 | `x-api-key` | none | 2023-06-01 | **63 passed** |
| 1.15.0 | `x-api-key` | none | 2023-06-01 | **63 passed** |
| 1.17.0 | `x-api-key` | none | 2023-06-01 | **63 passed** |
| 2.3.0 | **absent** | **`Bearer <key>`** | **2026-10-21** | **8 failed** |

63 = the three model suites (`tests/test_model_access.py`, `tests/test_model_lanes.py`,
`tests/test_model_transports.py`) collected and passing.

## Why five of six CI jobs and not six

`python/synapse/__init__.py` prepends the committed vendored SDK tree
(`python/synapse/_vendor`, which carries **anthropic 0.96.0**) to `sys.path` — but only on an
interpreter whose ABI matches the vendored native wheels, which are `cp311`/`cp313`
**win_amd64** only.

| job | vendor active? | SDK actually used | outcome |
|---|---|---|---|
| windows / 3.11 | yes | 0.96.0 (vendored) | green |
| windows / 3.14 | no (no cp314 wheels) | 2.3.0 (pip) | red |
| macos / 3.11 | no (win_amd64 only) | 2.3.0 (pip) | red |
| macos / 3.14 | no | 2.3.0 (pip) | red |
| ubuntu / 3.11 | no | 2.3.0 (pip) | red |
| ubuntu / 3.14 | no | 2.3.0 (pip) | red |

The single green job was the only one **not** using the pip-installed SDK. It is a blind spot:
one job in the matrix exercises a different dependency set from the other five, and the release
gate reads that job's green as if it spoke for all six.

The 10-20 run (39466235090) was green for the same commit because pip resolved
**anthropic 1.15.0** that day. Nothing in the repository changed between the two runs.

## Containment (shipped in v5.97.7)

`anthropic>=1.0.0,<2` in:

- `pyproject.toml` `[project.optional-dependencies] dev` — what CI installs
- `pyproject.toml` `[project.optional-dependencies] routing` — what the product installs
- `agent/requirements.txt` — the guarded agent surface

The ceiling is the real constraint (2.x is the breaking change). The floor excludes 0.75.0,
which is also broken. The pin resolves to **1.17.0** today, which is measured passing.

## What the 2.x migration actually requires

Not a version bump. Three things, in order:

1. **The guard must learn the 2.x auth convention.** The rule exists for a real reason: an
   ambient profile/bearer token must not be able to override the key that was checked. The 2.x
   rule is *not* "no `Authorization` header" but "`Authorization`, if present, must be exactly
   `Bearer <the key digest that was checked>`". That preserves the security property exactly,
   and it needs its own tests: a bearer token that is *not* the checked key must still be
   refused, and a request carrying *both* `x-api-key` and a different `Authorization` must be
   refused.

2. **`anthropic-version: 2026-10-21` is a protocol change, not a header rename.** The panel's
   Anthropic provider has never been exercised against it. The provider's request shape,
   streaming, and tool-use behaviour need a live verification, not a green unit test.

3. **The guard reaches into private SDK internals** — `client._client`, `transport._mounts`,
   `transport._transport`, `transport.auth`, `client._prepare_url`, `client.auth_token`,
   `client.credentials`, `_base_client.httpx2`. This is the class of coupling that produced
   this ticket, and it will produce another one at the next major. The durable fix is to stop
   reading private attributes and to assert the *behaviour* the guard needs (the key arrives in
   a header the guard recognises) rather than the SDK's internal shape.

**The 1.x ceiling is a containment, not a resolution.** It holds the product on a tested SDK.
It does not make the guard future-proof.

## Also worth fixing (not blocking)

- **The matrix has one job on a different dependency set.** Windows/3.11 exercises the vendored
  SDK; the other five exercise pip's. A release gate that reads any single job's green is
  reading a number that does not describe the other five. Either every job should assert which
  SDK it is running against, or the vendored path should be exercised deliberately in its own
  job rather than as an accident of the ABI matrix.
- **The vendored tree has no cp314 wheels.** On Python 3.14 the whole vendor tree is inactive,
  so the product silently falls back to pip's SDK — which is how a product-breaking SDK major
  reached users in the first place. Either re-vendor for 3.14 or make the fallback loud.
- **`_VENDOR_ABI_RISK` already warns about this.** The warning fired on every 3.14 CI run and
  on the seat. It was not read as a blocker, because the jobs that had the vendor active were
  green and the jobs that did not were green too — until 2.x landed.
