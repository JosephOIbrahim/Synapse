# "Does airy bind, or is it specification?"

**Answer: specification — and you already ruled it.** 2026-09-05, J4. The code has
enforced it since. What is open is not the decision; it is that several contracts and
suites never got the memo.

**This is a recommendation, not a ruling.** Superseding the affected contract lines
takes your word.

---

## Why this is a fact, not a preference

`tests/panel/test_j4_profiles_retired.py` quotes RULING_JOE_FIVE J4 verbatim:

> *"Curious / Expert / ML are retired from the panel for now: no Profile submenu, no
> pills, no density switch exposed. The composed profile is `expert` (the default).
> Manifests, compositor and settings keep the machinery (tests still exercise it) so it
> can return with a real difference; nothing an artist can reach shows it. Persisted
> `profile` in settings is read as `expert` regardless."*

Enforced, and verified four ways at `c217428b`:

- `synapse_panel.py:732-733` hard-sets `profile = DEFAULT_PROFILE`. The ordering is the
  load-bearing part: `__init__:618` reads the persisted profile (which *can* be
  `curious`), `:628` calls `_build_ui()`, which overwrites it at `:733` **before** the
  sole `compose()` at `:737`. The settings read is dead on arrival.
- `_select_profile` — the only route to `_recompose`, which is the only other
  `get_manifest()` call site — has **zero callers** in `python/`. Its only two references
  are its own `def` and a comment.
- `curious.py:44` is the only manifest carrying `"density": "airy"`, and it is never
  composed. The complete originator set for a non-standard density is **one line**:
  `compositor.py:254`.
- No env var. The other density writers (`qss.py:552/706/913/940`) all *propagate* from
  an ancestor and default to `"standard"`; none can originate airy.

J4's own pin passes at HEAD under hython: **2 passed**.

## The precise wording, because "unreachable" is too strong

`_select_profile` is a public importable method, `curious.py` ships inside the package,
and the panel exposes `houdini_execute_python` **ungated on the live path**. One chat
message can reach `panel._select_profile("curious")`. So:

> **Airy has no artist-reachable UI affordance and cannot be reached by settings, env, or
> any alternate entry point. The composing machinery stays public and live-callable.
> It is dormant configuration, not deleted capability.**

*(That path is verified by construction, not VERIFIED-RUNTIME — the one unexercised link
is retrieving the live `SynapsePanel` instance.)*

---

## What this actually buys: ONE collision, not four

My earlier framing oversold it. Corrected, and two of the four were never airy problems:

**Genuinely dissolves**

- **BC-5's airy red.** `test_j5_rail_air.py:139-148` already carries BC-5's own
  `share >= 0.5` predicate inside J5's test, on `_panel("expert")` — standard only. The
  airy failure is the density that reconciliation skipped. It becomes a specification
  figure with an owner.

**Downgraded, not removed**

- **D4's airy figure.** `_EDGE_TOP` is one dict entry and `tokens.gap` is multiplicative,
  so the edit moves all three densities in one line — you cannot land standard and defer
  airy. And `test_j5_rail_air.py:163-175` drives airy through `_recompose("curious")`,
  which J4 *requires* stay exercised. The airy number converts from a pixel budget into a
  spec value you still pick and still write into the test.

**Never airy problems — these survive untouched**

- **SYSTEM's `shell` 16 to 24 is a BASE TOKEN change**, not density scaling.
  `SCAFFOLD.html:288`: base 24, giving airy 36 / standard 24 / tight 18. **+8px at
  standard**, on all three shell owners — rail, ribbon and faces. I misread this.
- **D4 vs J5 at standard** (+8px, exact-dict assertion at `test_j5_rail_air.py:157`).
- **The `row` deletion trap.** Latent, not firing: the key exists today. But both F12
  options delete it and `chat_display.py:190-191` hard-indexes it from a QTextDocument
  block property. **F12's own acceptance probe (`SCAFFOLD.html:1082`) greens on exactly
  the deletion that breaks the transcript.**
- **D1 entirely.** I double-counted it — listing its airy face as an unlock and its
  standard face as a survivor inflated the tally for one defect.

---

## D1's red stands, and an attack on it was itself wrong

An adversarial pass argued the bound is `PANEL_MIN_HEIGHT = 420` (`tokens.py:636`), not
400, which would shrink the breaches to +34/+18/+10. **Checked, and it is wrong.**
`tests/test_panel_rhythm_docking.py::_bounds` reads the figure from the YAML contract and
says why:

```python
# Read the actual YAML descriptions; do not silently follow the conflicting
# 420px token.
```

There is a test named for it — `test_docking_bounds_read_the_contract_not_panel_height_token`
— asserting the contract figure is the *stricter* of the two. **400 is deliberate.**

Re-run by hand with the bundled fonts, hython 22.0.400: **3 failed, 88 passed, 222s** —
red at airy, standard and tight. The original +54 / +38 / +30 stands.

*(The attacker's own re-measure reported `QFontDatabase.families() == 0`, and the contract's
RULING-2A says a figure taken with an empty font database is not a measurement. It could not
have refuted the number even if the bound had been wrong.)*

---

## Law 1 — this is a withdrawal, not a deletion

BC-5's predicate is a claim about what an artist sees. J4 removed the artist's route to
airy, so the claim's premise is false. **A claim whose premise is false is withdrawn.**

It becomes dishonest at four points. Write all four into the ruling:

1. **If the airy assertion is removed rather than retargeted.** J4 says *"tests still
   exercise it."* A deleted airy branch violates J4 by name.
2. **If the deficit is not recorded as a number with an owner.** Then airy cannot *"return
   with a real difference"* — the gate on its return is gone and it really is a deletion.
3. **Contamination.** `test_j5_rail_air.py:163-175` runs all three densities in one
   function body. A "relax airy" edit sits one line from relaxing standard.
4. **D1 must be explicitly barred from the reclassification.** Its red is at standard too
   and is not an airy artifact.

---

## What I recommend you ratify

1. **Airy is specification**, in an artifact that supersedes the affected contract lines —
   not only in code. `docking-minimums.yaml`'s R3-01 needs the same treatment separately:
   its named remedy is *"a verb rail that collapses to icons below ~360px"* and F1 deleted
   the verb rail.
2. **Encode BC-5's airy deficit** as a density-conditional assertion carrying the number
   and an owner. Never delete the branch.
3. **Bar D1 from the reclassification**, in writing.
4. **Add the pin J4 lacks.** J4 proves the persisted-settings route is dead and the
   machinery survives. It does **not** pin that `_select_profile` has zero production
   callers — only a comment guards that today.

---

## That probe is now run, and it clears

I closed this with the measurement rather than leaving it as a worry. BC-5's headroom,
composed at 340x760 with 35 font families loaded, using `test_bc_wave`'s own helpers so
the method cannot drift from the assertion:

```
curious  density=airy      chat=367px   share=0.48289   headroom  -13.0px   FAIL
expert   density=standard  chat=407px   share=0.53553   headroom  +27.0px   PASS
ml       density=tight     chat=427px   share=0.56184   headroom  +47.0px   PASS
```

The airy row reproduces the known seat failure exactly (367 / 0.48289), which validates
the method against a figure I did not choose.

**Standard carries +27px.** The combined standard-density spend I warned about — D4's +8
plus SYSTEM's shell +8 on the faces — is **16px, and it fits with 11px to spare.** So the
spacing wave is **not** blocked at the density artists actually run. I said that probe was
twice as threatening as I first stated; measured, the threat does not land.

**The caveat that keeps this honest:** the 16px is *my arithmetic on the margins*, not a
composed measurement of the changed panel. Additive estimates understate composed layout
costs often enough that the real number has to be re-measured after the edit, not
predicted before it. +27 says "proceed and measure", not "guaranteed safe".

Producer: `harness/design_review/2026-09-14/bc5_headroom.py`, run under
hython 22.0.400 offscreen.
