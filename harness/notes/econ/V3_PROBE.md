# V3 — THE PROBE LAYER

**Leg** `V3` · **Harness** `ECON-01` · **Blueprint Mile 4** · **Run** 2026-07-28
**Branch** `econ/v3-probe-layer` · **Worktree** `.claude/worktrees/v3-econ`
**Product** `python/synapse/panel/providers/probe.py` · **Guard** `tests/test_v3_provider_probe.py`
**Producers** `harness/notes/econ/v3_{probe_live,stale_demo,calibration,controls}.py`

Governed by `harness/AGENT_CONSTITUTION.md`. Every number below names the
script that emitted it (Law 2). Every check states the condition under which it
fails (Law 1).

---

## 0 · What was built

A layer that returns a structure. No panel work — §04's own ordering, and the
right one.

`ProbeResult` is the blueprint §3.3 shape verbatim — `model`,
`tier_candidates`, `available`, `quota_remaining`, `quota_total`,
`cost_per_1k_in`, `cost_per_1k_out`, `latency_ms`, `probed_at` — plus eleven
provenance fields carrying, per row, the endpoint that produced it, why
`available` is false, where the quota figure came from, where the cost figure
came from, and which evidence assigned the tier.

**There is no colour field.** Colour is `colour_for(result, now=...)`, computed
at read time, and the structure is frozen so it cannot acquire one by accident.

---

## 1 · The finding that justifies the whole design

The brief asks the layer to be probe-derived rather than config-declared. The
measured drift, live, this session:

| provider | declared in `registry.py` | served live | ratio |
|---|---|---|---|
| ollama | **1** | **13** | 13× |
| claude | **6** | **11** | 1.8× |
| nemotron | **2** | **102** | 51× |

*Producer: `v3_probe_live.py` → `V3_probe_live.install.json`.*

**117 of 127 live rows are models the config file never heard of.** A panel
routing off `registry.py` can reach 9 of them.

Two specifics worth naming.

**`claude-opus-5` is now verified.** Its registry comment carried a standing
instruction — *"model string from the assistant's own runtime context, NOT from
a live GET /v1/models call … verify against /v1/models before any release cites
it."* `GET /v1/models` returns it: `claude-opus-5`, display name *Claude Opus
5*, `created_at` 2026-07-24. All six declared Claude rows were served on
2026-07-28. The provenance gap is closed and the note is now dated, because a
dated note is the only kind that cannot silently age (R74).

**The registry's Ollama default is not free.** `glm-5:cloud` reports
`remote_host: https://ollama.com:443`. Six of the thirteen live tags do. "Ollama
is local and therefore costless" is true of seven tags and false of the one the
panel ships selected.

**Zero declared-but-absent models today.** Every declared row was live. That is
a measurement of one afternoon, not a property — which is exactly why the
mechanism ships anyway: a declared model the provider stops serving comes back
`available=False, reason="declared_but_absent"` and reads RED. `hou.ActiveRender`
as a colour instead of a support ticket. Pinned by
`test_declared_but_absent_model_is_red`; mutation M8 deletes the rows and the
test goes red (`V3_controls.json`).

---

## 2 · Colour is computed, and staleness wins

```
green   probed available
red     probed and not dispatchable right now
grey    probe stale — UNKNOWN, not assumed
```

`colour_for` reads in this order, and the order is the design:

1. **stale or never probed → GREY.** Checked *before* `available` is consulted.
2. not available → RED (`reason` says which kind of no).
3. `quota_remaining` explicitly `0` → RED. `None` means no quota signal was
   obtainable; it must not manufacture one.
4. otherwise → GREEN.

Cost never appears. A price cannot make anything green.

### Demonstrated, on real rows

`v3_stale_demo.py` reads the 127 live rows at a sweep of clock offsets. **The
rows are immutable and identical at every offset; only the clock moves.**

```
offset_s   green  red  grey   refresh?
     0.000    126    1     0   False
    30.000    126    1     0   False
    59.900    126    1     0   False
    60.000    126    1     0   True
   179.900    126    1     0   True
   180.000      0    1   126   True
   180.001      0    0   127   True
  3600.000      0    0   127   True
```

*(The single RED row is Gemini — configured with no key. It greys one tick later
than the rest because each provider stamps its own `probed_at`; the rail greys
per provider, not globally.)*

### And with `probed_at` aged artificially

Clock held still, `probed_at` pushed back past the TTL via
`dataclasses.replace`:

```
126 GREEN rows -> green=0  grey=126
negative control, re-probed -> green=126
```

The negative control is the part that makes the first line mean something.
Without it, "everything goes grey" is indistinguishable from a function that
always returns grey.

Six checks in `V3_stale_demo.json`, each with its failure condition stated:

| check | fails when |
|---|---|
| C1 colour varies with the clock alone | colour is stored, or `colour_for` ignores `probed_at` |
| C2 aged green → grey, never green | `colour_for` checks `available` before age |
| C3 aged **red** → grey too | RED is treated as terminal — an old *no* is also UNKNOWN |
| C4 re-probe restores the colour | `colour_for` always says grey and proves nothing |
| C5 future stamp → grey | `is_stale` drops its skew clause; a wrong clock pins green forever |
| C6 no colour in the structure | someone adds a colour field |

All six pass.

---

## 3 · Polling — the probe must not trip the limit it reports on

**`REFRESH_INTERVAL_S = 60` · `PROBE_TTL_S = 180`.**

**Demand-driven, not timer-driven.** Nothing here runs on a schedule.
`should_refresh(result, now)` gates the caller, so an **idle panel issues zero
probes**. That removes the failure mode structurally rather than tuning around
it — a timer polls whether or not anyone is looking.

Under continuous use the ceiling is **60 requests/hour/provider**, against
endpoints that are free and are not the completions bucket. The lowest published
Anthropic request-rate tier is far above 1 rpm.

TTL is **3×** the interval, so two consecutive probe failures are survivable and
the third greys the rail. **Maximum displayed staleness: 3 minutes** — against a
brief that names *an hour* as the failure mode. The 60s floor is pinned by
`test_refresh_interval_is_at_least_one_per_minute`, the 3× relation by
`test_ttl_exceeds_refresh_interval`; mutations M11/M12 break both.

---

## 4 · Zero completion spend

**Completions issued: 0.** Recorded in `V3_probe_live.install.json`
(`spend.completions_issued`), and enforced two ways rather than promised:

* **Allowlist.** Every endpoint the module can reach is in
  `probe.FREE_ENDPOINTS`. Every `method` a probe emits is checked against it by
  `test_every_emitted_method_is_in_the_free_allowlist`.
* **Source scan.** `test_no_completions_endpoint_in_executable_code` parses the
  module with `ast` and asserts no *non-docstring* string literal names a
  completions path. Docstrings are excluded deliberately — this module's
  documentation names those endpoints in order to say it never calls them, and
  a naive grep would flag its own disclaimer. Mutation M6 adds one literal and
  the test goes red.

Endpoints actually called: `ollama:GET /api/tags`,
`anthropic:GET /v1/models`, `nvidia:GET /v1/models`, `local:config`.

### Probes declined on cost grounds

| declined | would have measured | why not |
|---|---|---|
| `POST /v1/messages` (Anthropic, 1 token) | quota headroom — `anthropic-ratelimit-{requests,input-tokens,output-tokens}-{limit,remaining,reset}`, published **only** by the billed endpoint | it bills. The economist axis cannot credibly measure cost while being careless with it, and a liveness check that consumes the quota it reports on is self-defeating |
| `POST /v1/chat/completions` (NIM, Ollama `:cloud`) | generation latency, completions-bucket rate headers | metered by the host; the free list endpoints answer availability |

**Consequence, recorded rather than worked around:** `quota_remaining` and
`quota_total` are `None` for every metered provider, `quota_source =
"unavailable_at_zero_cost"`.

This is not an implementation gap — it is **measured**. Neither
`GET /v1/models` nor the free `POST /v1/messages/count_tokens` returns any
`anthropic-ratelimit-*` header, and NVIDIA's `GET /v1/models` returns none
either. Verified by reading the full header sets this session.

So the honest capability statement: **rate-limiting is caught reactively (a 429
is detected, and a 429 *does* carry the headers); headroom is not reported
predictively.** `None` computes to neither RED nor GREEN — it carries no signal,
which is the point.

`latency_ms` is likewise **metadata-endpoint latency** (ollama 46 ms, nvidia
140 ms, anthropic 307 ms), a liveness number. It is not time-to-first-token and
must not be read as one.

---

## 5 · Cost — the one §3.3 field that cannot be probed

No provider exposes per-token pricing over its API. Verified against the live
payloads: the Anthropic model object carries `id`/`display_name`/`created_at`/
`type`; NVIDIA's carries `id`/`created`/`object`/`owned_by`; Ollama's carries no
billing field.

**So no price table ships.** A dated table typed into code is precisely the
claim-shape this module exists to refuse, and keying one by model id would also
put model names in code (blueprint invariant 1). Metered models get `None` with
`cost_source = "unprobeable:no_pricing_endpoint"`.

Where cost *can* be probed, it is:

| row | cost/1k | source |
|---|---|---|
| `gemma4:latest` and 6 other local tags | `0.0` | `probed:local_weights_no_remote_host` |
| `glm-5.2:cloud` and 5 other cloud tags | `None` | `metered:remote_host=https://ollama.com:443` |

The absence of `remote_host` in `/api/tags` establishes the weights run on this
machine, so there is no per-token vendor charge. That is a probe, not a
declaration — and it is the reason the Ollama default's cost reads unknown
rather than zero.

**Where a price table should live is a ruling, not an agent call** (`R-V3-1`).

---

## 6 · Tier candidates, derived from what the probe returned

Dispatch asks for a tier; the probe answers with whatever currently satisfies
it. Evidence is used strongest-first:

| basis | signal | rows |
|---|---|---|
| `parameter_size` | numeric, from `details.parameter_size` — only Ollama publishes it | **10** |
| `live_id_token` | family token in the id/display name the provider returned *this second* | **63** |
| `unclassified` | nothing matched → **empty tier tuple** | **54** |

*Producer: `v3_probe_live.py` → `V3_probe_live.install.json` `summary`.*

Two properties are load-bearing:

**Rules are matched against live output, never a typed list.** A model released
tomorrow is classified the moment the provider serves it. That is the property a
config-declared table structurally cannot have.

**An unclassified model gets no tier — never a default.** A default would be a
guess wearing a tier constant, and it would route work to a model nothing
established was suitable. Pinned by
`test_unclassified_gets_no_tier_never_a_default`; mutation M7 installs a default
and the test goes red.

**Tool use is a hard gate where it is known.** Ollama publishes `capabilities`;
a model without `tools` gets an empty tier tuple whatever its size. Where
capabilities are unknown (`None` — Anthropic and NVIDIA publish none) **no gate
is applied**: absence of evidence is not evidence of absence.

### The number that actually matters

54 of 127 unclassified sounds alarming and mostly is not — most are NVIDIA
embedding, safety and vision models that should never be chat-routed, and
refusing them is the classifier working.

The actionable count is over **registry-declared, panel-selectable** models:

> **10 declared models, 2 unclassified: `glm-5:cloud` and `claude-fable-5`.**

*Producer: `v3_calibration.py` → `V3_calibration.json` `declared_model_coverage`.*

`glm-5:cloud` is the panel's default Ollama pick and publishes an empty
`parameter_size`. `claude-fable-5` carries no family token. Both are live, both
are selectable, and **neither is routable by tier**. Whether tier rotation may
route to a model with no tier evidence is `R-V3-2`.

---

## 7 · Calibration (R60) and controls (R133)

### Every reader calibrated before it is trusted

`v3_calibration.py` → `V3_calibration.json`. Each block carries a **positive**
half (inputs whose correct answer is known) and a **negative** half (inputs
whose correct answer is *refusal*). A classifier with no negative half will
label anything, and its coverage number is then a statement about its own
eagerness.

| reader | positive | negative | result |
|---|---|---|---|
| `parse_parameter_size` | 10 live strings → billions | 6 unparseable → `None`, never `0.0` | PASS |
| `tier_candidates_for` | 12 hand-labelled live ids | 6 that must refuse | PASS |
| `_quota_from_headers` | anthropic-style + openai-style headers | the real live header set → `None`; malformed → `None` | PASS |
| `colour_for` | 12-case truth table, all three colours exercised | — | PASS |
| `should_refresh` | 7-case truth table incl. skew | — | PASS |

The tier block also carries two paired controls: a FAST-named model the provider
says is 600B must classify FRONTIER (size outranks token), and the *same* model
string at the *same* size with and without `tools` must classify and refuse
respectively (the gate fires on evidence, not on the name).

Ground truth is hand-labelled from the recorded live payloads, and the refusal
set deliberately includes `claude-fable-5` and `glm-5:cloud` — real, live,
declared models where refusal is the correct answer.

### Every control mutation-tested

`v3_controls.py` → `V3_controls.json`. Sixteen mutations applied to the real
`probe.py`, each with the test it must break. **16 of 16 flip.**

| # | mutation | test broken |
|---|---|---|
| M1 | `colour_for` stops consulting age | `test_stale_available_row_is_grey_not_green` |
| M2 | never-probed reads fresh | `test_never_probed_is_grey` |
| M3 | skew clause dropped | `test_future_timestamp_is_grey_not_green` |
| M4 | unknown quota read as exhausted | `test_unknown_quota_does_not_manufacture_red` |
| M5 | colour stored on the structure | `test_colour_is_not_a_field` |
| M6 | completions literal added | `test_no_completions_endpoint_in_executable_code` |
| M7 | unclassified gets a default tier | `test_unclassified_gets_no_tier_never_a_default` |
| M8 | declared-but-absent rows dropped | `test_declared_but_absent_model_is_red` |
| M9 | missing header read as zero headroom | `test_quota_absent_is_reported_as_unobtainable_not_zero` |
| M10 | tool gate stops firing | `test_no_tool_capability_is_a_hard_gate` |
| M11 | refresh floor drops to 1s | `test_refresh_interval_is_at_least_one_per_minute` |
| M12 | TTL falls below the interval | `test_ttl_exceeds_refresh_interval` |
| M13 | price reaches the colour | `test_cost_never_affects_colour` |
| M14 | unconfigured provider probed anyway | `test_unconfigured_provider_makes_no_network_call` |
| M15 | name signal consulted before size | `test_parameter_size_outranks_name_token` |
| M16 | unparseable size becomes `0.0` | `test_parse_parameter_size` |

A baseline run confirms all sixteen tests are green *before* any mutation —
otherwise "the control flipped" would mean nothing. `probe.py` is restored from
in-memory bytes in a `finally` and the restore is **sha256-verified**
(`972aa070…`, before == after, recorded in the artifact).

**Near-miss, recorded rather than quietly fixed.** The first run reported 8 of
16 as NOT-APPLIED. That reads as eight missing controls; it was a newline
artifact — the anchors are written with `\n` and the checked-out `probe.py` is
CRLF. Had the harness only counted flips it would have reported "8 of 16
controls flip" as a *finding about the tests*, which is E1's C4b defect in a new
place: the control was wrong, not the thing under test. The harness now
normalises before matching and says so in a comment.

---

## 8 · Two defects found in the auth path

Neither is in this leg's `touches`. Both are reproduced with paired controls and
escalated, not fixed.

### F1 — an empty `ANTHROPIC_API_KEY` permanently shadows the repo `.env`

`python/synapse/host/auth.py:102` loads `<repo>/.env` with
`os.environ.setdefault(name, value)`. `setdefault` is a no-op when the key
**exists**, including when it exists as an empty string. `_try_env_var` then
strips and returns `None`, and the product reports itself unconfigured while
holding a valid key.

Reproduced this session with a paired control — same repo root, same `.env`,
one variable changed:

```
ANTHROPIC_API_KEY=""   (present, empty)  -> key resolved: False
ANTHROPIC_API_KEY      (absent)          -> key resolved: True
```

This is not hypothetical: the shell this leg ran in exports it empty by design.
Any launcher that blanks the variable rather than unsetting it puts the panel
into a silent unconfigured state. Tier: **VERIFIED-RUNTIME**.

### F2 — key resolution is checkout-dependent

`auth.py:76` resolves the repo root as `Path(__file__).resolve().parents[3]`. In
a git worktree that is the *worktree* root, which carries no `.env`. Measured,
same machine, same minute, two runs of the same producer:

| run | configured |
|---|---|
| `V3_probe_live.worktree.json` | `ollama` only |
| `V3_probe_live.install.json` | `ollama`, `claude`, `nemotron` |

Same shape as E1-F8 (a digest computed over working-tree bytes): an answer that
depends on which checkout asks. Harmless for a normal install, and it makes
every worktree, CI checkout and clean clone report two providers unconfigured.
Tier: **VERIFIED-RUNTIME**.

The probe records `env.auth_repo_root` and an `empty_string_shadow_check` in
every artifact, so a future reader can tell "provider is down" from "this
checkout cannot see the key" without re-deriving it.

---

## 9 · Suite

Measured on both sides, not asserted. The **before** number comes from a clean
detached checkout of `b92b0d4` in a scratch worktree, run and then removed —
because "the suite still passes" is a claim about a state nobody had actually
run.

| | passed | failed | skipped |
|---|---|---|---|
| before — clean `b92b0d4` | **5031** | 0 | 137 |
| after — this leg | **5080** | 0 | 137 |
| delta | **+49** | 0 | 0 |

+49 is exactly the test count of `tests/test_v3_provider_probe.py`
(`pytest --collect-only`: 49 collected). Nothing else moved. Law 6 holds by
measurement.

Interpreter: **Python 3.14.2**, the non-shipping interpreter (Ruling 1a), so
this is labelled `VERIFIED-RUNTIME (non-shipping interpreter)`. The vendor tree
is inactive at this Python. `probe.py` is stdlib-only and imports nothing
vendored, so the ABI gap does not reach it — but that is an argument, not a
measurement, and it is labelled as one.

### One red on the way, and what it was

The first full run came back **1 failed**:
`test_m3_egress_docs.py::test_remote_egress_sites_are_frozen` — *"New raw-HTTPS
egress site(s): {'panel/providers/probe.py'} — document in
docs/studio/EGRESS.md, then extend this pin."*

That is the pin working. `probe.py` genuinely does open TLS connections, and
the alarm exists to make a new one impossible to add silently.

Fixed forward, per the pin's own instruction: the lane is documented in
`EGRESS.md` (no new host — the same three, `GET`-only, empty bodies, metadata
only, demand-driven), and the frozen set was extended by exactly one entry with
a dated comment. **No assertion was weakened and nothing was skipped.**

Extending an allowlist does spend a little of the alarm's power, so the leg pays
it back: `test_egress_doc_documents_the_probe_lane` fails if the EGRESS.md
paragraph that justified the entry is ever removed. The allowlist entry cannot
outlive its justification.

---

## 10 · What this leg did not do

* **No panel work.** T.4's freeze holds until V2 also lands. No rail, no
  rendering, no widget. The layer returns a structure and `summarize()` returns
  counts; both are data.
* **No price table**, for the reason in §5.
* **No behaviour change in `registry.py`.** The edits are documentation:
  a header stating the tables are a selection list rather than an availability
  claim, the closed `claude-opus-5` provenance instruction, and the re-measured
  Ollama drift. `models_for`, `default_model`, `model_label` and
  `build_provider` are byte-identical.
* **No consumer wired.** Nothing calls `probe.py` yet. That is deliberate: the
  first consumer is a panel rail, and the panel is frozen.

---

## 11 · Reproduce

```
python harness/notes/econ/v3_probe_live.py --label install --env-from C:/Users/User/SYNAPSE
python harness/notes/econ/v3_stale_demo.py
python harness/notes/econ/v3_calibration.py     # exits non-zero if a reader drifted
python harness/notes/econ/v3_controls.py        # exits non-zero if a control survives
python -m pytest tests/test_v3_provider_probe.py -q
```

`--env-from` loads that directory's `.env` by **assignment**, which is what
routes around F1. Without it the producer measures the worktree's reality, which
is also a true answer to a different question — both artifacts are kept.
