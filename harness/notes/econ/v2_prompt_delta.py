"""V2 · what the verdict contract takes OUT of the system prompt, measured exact.

    E0-F5  the cache breakpoint wraps the WHOLE system prompt — and the
           prompt is NOT static
    E0-F6  _solaris_context_block substring-matches the network path and
           APPENDS guidance, so the cached span changes the moment an
           artist navigates /stage -> /obj
    R155   the system prompt is 2,961 tokens EXACT, every turn

If the model emits STRUCTURE instead of PROSE, register instruction stops needing
to be in the prompt — and register instruction is a large part of what makes that
prompt non-static. This producer measures how much, and it measures the NET:
the schema the contract replaces the prose WITH is not free, and a saving quoted
without its cost is the same defect as a number quoted without its producer.

    python harness/notes/econ/v2_prompt_delta.py
    -> harness/notes/econ/V2_prompt_delta.json

METHOD, AND ITS LIMITS
----------------------
* Every figure is ``count_tokens`` — EXACT, free, unbilled (R155 ruling 3: the
  API budget is for ``count_tokens`` and nothing else). No completions are made.
  The proxy tokenizer is retired for anything that governs a decision.
* The "after" prompt is a COUNTERFACTUAL built by string surgery on the REAL
  output of ``build_system_prompt``. ``TONE.md`` is not modified and
  ``system_prompt.py`` is not touched — this leg does not own either file, and
  removing the tone guide is a separate, ruled decision. The measurement says
  what is available, not what has been taken.
* The reader is calibrated against R155's committed exact figure before any
  delta is reported (R60). A reader that cannot reproduce a known number has not
  earned the right to publish a new one.
"""

import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "V2_prompt_delta.json")

MODEL = "claude-sonnet-4-6"
KEY_NAMES = ("SYNAPSE_ANTHROPIC_KEY", "ANTHROPIC_API_KEY")

#: R155's committed figure for the /stage system prompt. The calibration target.
R155_SYSTEM_PROMPT_TOKENS = 2961
R155_SYSTEM_PROMPT_CHARS = 11334

CONTEXTS = [
    ("/stage", {"network": "/stage", "selection": [], "frame": 1, "hip": "x.hip"}),
    ("/obj", {"network": "/obj", "selection": [], "frame": 1, "hip": "x.hip"}),
    ("/out", {"network": "/out", "selection": [], "frame": 1, "hip": "x.hip"}),
]


def find_key():
    """The API key, from the environment or a ``.env`` beside the repo.

    The worktree has no ``.env`` (it is gitignored and lives in the main
    checkout), so the search walks up. The value is never printed, never written
    to the artifact, and never returned to a caller that logs it.
    """
    for name in KEY_NAMES:
        value = os.environ.get(name)
        if value:
            return value.strip(), "env:" + name
    seen = []
    candidates = [os.path.join(REPO, ".env")]
    root = REPO
    for _ in range(5):
        root = os.path.dirname(root)
        candidates.append(os.path.join(root, ".env"))
    for path in candidates:
        seen.append(path)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                for name in KEY_NAMES:
                    if line.startswith(name + "="):
                        return (line.split("=", 1)[1].strip().strip('"').strip("'"),
                                path)
    raise SystemExit("no API key found. Searched env %s and:\n  %s"
                     % (list(KEY_NAMES), "\n  ".join(seen)))


class Counter:
    """Exact input tokens via ``count_tokens``, baseline-subtracted.

    Every call is FREE. Errors are raised, never swallowed into a proxy: a
    producer that silently degrades to an estimate publishes an estimate wearing
    the word EXACT, which is the failure this whole leg exists downstream of.
    """

    def __init__(self, key):
        self._key = key
        self.calls = 0
        self.baseline = self._raw()

    def _raw(self, text=None, tools=None, system=None):
        body = {"model": MODEL,
                "messages": [{"role": "user", "content": text or "."}]}
        if tools:
            body["tools"] = tools
        if system:
            body["system"] = system
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages/count_tokens",
            data=json.dumps(body).encode("utf-8"),
            headers={"x-api-key": self._key,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"})
        self.calls += 1
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.load(resp)["input_tokens"]
        except urllib.error.HTTPError as exc:
            raise SystemExit(
                "count_tokens HTTP %s — %s\nNo proxy fallback: a figure that "
                "governs a decision is exact or it is absent."
                % (exc.code, exc.read()[:200].decode("utf-8", "replace")))

    def system(self, text):
        return self._raw(system=text) - self.baseline

    def tools(self, defs):
        return self._raw(tools=defs) - self.baseline


def strip_tone(prompt, tone):
    """The counterfactual prompt, with the register guide removed.

    Surgery on the REAL output, verified by reconstruction: the removed span must
    be exactly the tone guide plus the ``"\\n\\n"`` join that
    ``build_system_prompt`` inserts. Anything else and the "after" figure is
    measuring a string nobody would have shipped.
    """
    joined = "\n\n" + tone
    if joined not in prompt:
        raise SystemExit("the tone guide is not joined the way build_system_prompt "
                         "joins it — the surgery would measure a fiction")
    after = prompt.replace(joined, "", 1)
    assert len(prompt) - len(after) == len(joined), "reconstruction check failed"
    return after


def _break_even(removed, added, write_x, read_x):
    """The first API call at which the cumulative cost of the AFTER regime stops
    exceeding the BEFORE regime, or ``None`` when it never does.

        after(n)  = added*write + added*read*(n-1)      one write, then reads
        before(n) = removed*write*n                     rewritten every call

    Returns ``None`` rather than a number when the per-call saving is <= 0 — a
    regime that never breaks even must not report a break-even point.
    """
    per_call = removed * write_x - added * read_x
    if per_call <= 0:
        return None
    n = 1
    while added * write_x + added * read_x * (n - 1) > removed * write_x * n:
        n += 1
        if n > 10_000:                     # cannot happen while per_call > 0
            return None                    # pragma: no cover
    return n


def _drop_keys(node, keys):
    if isinstance(node, dict):
        return {k: _drop_keys(v, keys) for k, v in node.items() if k not in keys}
    if isinstance(node, list):
        return [_drop_keys(v, keys) for v in node]
    return node


def _strip_descriptions(node):
    """The same schema with every ``description`` removed — the structural floor.

    Measured, because the intuition was wrong: the prose in this schema is 65
    tokens and the STRUCTURE is 1,119. The register instruction did not relocate
    into the schema at meaningful cost; the cost is JSON Schema itself.
    """
    return _drop_keys(node, {"description"})


#: Constraints the constructors already enforce. Repeating them on the wire is
#: belt-and-braces that is re-sent on every request — and the contract's own
#: position is that enforcement lives in code, not in documentation. Dropping
#: them is a defensible design, so it is priced rather than argued about.
_REDUNDANT_IN_SCHEMA = {"maxLength", "minimum", "pattern", "additionalProperties"}


def _lean(node):
    """The schema reduced to what SHAPES the emission: types, enums, required.

    Everything removed here is validated by ``verdict.py`` the moment the object
    is constructed, so a violation is caught either way — the only difference is
    whether the model was also told, at a price paid on every request.
    """
    return _drop_keys(node, _REDUNDANT_IN_SCHEMA)


def main():
    sys.path.insert(0, os.path.join(REPO, "python"))
    from synapse.panel.system_prompt import (
        _SOLARIS_CONTEXT_GUIDANCE, _OBJ_CONTEXT_GUIDANCE, _load_tone,
        build_system_prompt,
    )
    from synapse.panel.verdict import tool_definition

    key, key_source = find_key()
    counter = Counter(key)

    tone = _load_tone()
    if not tone:
        raise SystemExit("TONE.md did not load — nothing to measure")
    on_disk = open(os.path.join(REPO, "TONE.md"), encoding="utf-8").read().strip()
    if tone != on_disk:
        raise SystemExit("the loaded tone guide is not the committed TONE.md")

    report = {
        "schema": "v2_prompt_delta/v1",
        "producer": "harness/notes/econ/v2_prompt_delta.py",
        "method": "anthropic count_tokens (EXACT, free, unbilled) — no completions",
        "model": MODEL,
        "key_source": key_source if key_source.startswith("env:") else "dotenv (path withheld)",
        "baseline_empty_turn_tokens": counter.baseline,
    }

    # -- calibration (R60): reproduce R155's committed figure ---------------
    stage_prompt = build_system_prompt(CONTEXTS[0][1])
    stage_tokens = counter.system(stage_prompt)
    report["calibration"] = {
        "target": "R155 — system prompt @ /stage",
        "committed_tokens": R155_SYSTEM_PROMPT_TOKENS,
        "measured_tokens": stage_tokens,
        "committed_chars": R155_SYSTEM_PROMPT_CHARS,
        "measured_chars": len(stage_prompt),
        "verdict": "PASS" if stage_tokens == R155_SYSTEM_PROMPT_TOKENS else
                   "DRIFT — the tree moved, the meter did not (report both)",
    }

    # -- what the contract lets OUT -----------------------------------------
    tone_alone = counter.system(tone)
    rows = []
    for label, ctx in CONTEXTS:
        before_text = build_system_prompt(ctx)
        after_text = strip_tone(before_text, tone)
        before = stage_tokens if label == "/stage" else counter.system(before_text)
        after = counter.system(after_text)
        rows.append({
            "network": label,
            "before_tokens": before,
            "after_tokens": after,
            "removed_tokens": before - after,
            "removed_pct": round(100.0 * (before - after) / before, 1),
            "before_chars": len(before_text),
            "after_chars": len(after_text),
        })
    report["register_instruction_out"] = {
        "what": "TONE.md — the Synapse Voice Guide, the register instruction the "
                "structured contract makes unnecessary",
        "tone_alone_tokens": tone_alone,
        "per_context": rows,
    }

    # -- what the contract puts IN ------------------------------------------
    schema_tokens = counter.tools([tool_definition()])
    bare_tokens = counter.tools([_strip_descriptions(tool_definition())])
    lean_tokens = counter.tools([_lean(tool_definition())])
    report["contract_in"] = {
        "what": "verdict.tool_definition() — the schema the agent emits against, "
                "priced as a tool definition because that is how it ships",
        "as_shipped_tokens": schema_tokens,
        "structure_only_tokens": bare_tokens,
        "description_prose_tokens": schema_tokens - bare_tokens,
        "lean_tokens": lean_tokens,
        "lean_drops": sorted(_REDUNDANT_IN_SCHEMA),
        "finding": "the added cost is JSON SCHEMA STRUCTURE, not relocated "
                   "register instruction: the rule prose is %d tokens and the "
                   "structure is %d. A verbose schema costs more than the entire "
                   "prose voice guide it replaces — so the net is a schema-design "
                   "choice, not a fixed price."
                   % (schema_tokens - bare_tokens, bare_tokens),
        "placement": "cache_control sits on the LAST tool "
                     "(anthropic_provider.py:64), so a schema appended to the "
                     "tools array lands inside the cached prefix — unlike the "
                     "tone guide, which sat in the volatile system span (E0-F5/F6).",
    }

    # -- the NET, per context ------------------------------------------------
    report["net"] = [
        {"network": r["network"],
         "removed_tokens": r["removed_tokens"],
         "added_as_shipped": schema_tokens,
         "net_as_shipped": r["removed_tokens"] - schema_tokens,
         "added_lean": lean_tokens,
         "net_lean": r["removed_tokens"] - lean_tokens,
         "direction_as_shipped": ("saving" if r["removed_tokens"] > schema_tokens
                                  else "cost"),
         "direction_lean": ("saving" if r["removed_tokens"] > lean_tokens
                            else "cost")}
        for r in rows
    ]

    # -- what this does NOT fix (E0-F5/F6) ----------------------------------
    solaris_tokens = counter.system(_SOLARIS_CONTEXT_GUIDANCE)
    obj_tokens = counter.system(_OBJ_CONTEXT_GUIDANCE)
    report["still_volatile"] = {
        "finding": "E0-F6 — _solaris_context_block swaps the guidance literal on "
                   "navigation, so the cached span still changes when an artist "
                   "moves /stage -> /obj. Removing the tone guide does NOT make "
                   "the prompt static and must not be reported as if it did.",
        "solaris_guidance_tokens": solaris_tokens,
        "obj_guidance_tokens": obj_tokens,
        "swing_stage_to_obj_tokens": solaris_tokens - obj_tokens,
        "swing_stage_to_out_tokens": solaris_tokens,
    }

    # -- price, DERIVED from E0's multipliers, with the dependency named ----
    #
    # E0's central correction was that preload tokens and price are DIFFERENT
    # QUANTITIES and that substituting one for the other is the error. It applies
    # to this leg's own premise, so the two are reported separately and the
    # derived half carries its unverified inputs on its face.
    write_x, read_x = 1.25, 0.1
    removed = rows[0]["removed_tokens"]
    report["price_derived"] = {
        "tier": "VERIFIED-DERIVED",
        "inputs_not_re_verified": [
            "E0 limit A1 — the 1.25x write / 0.1x read multipliers were not "
            "re-verified against current Anthropic pricing",
            "E0-F12 / C1-F12 — no usage reader is closed (anthropic_provider.py "
            "has no message_start branch), so cache warmth is inferred from code, "
            "never observed",
        ],
        "assumption": "E0-F5/F6 — the system span is rewritten every turn, so its "
                      "tokens are a perpetual cache WRITE that is never read back; "
                      "the tool block is stable, so its tokens are a cache READ "
                      "after the first call.",
        "before_bte_per_call": round(removed * write_x, 1),
        "after_bte_per_call": round(schema_tokens * read_x, 1),
        "after_first_write_bte": round(schema_tokens * write_x, 1),
        "steady_state_saving_bte_per_call":
            round(removed * write_x - schema_tokens * read_x, 1),
        "break_even_calls": _break_even(removed, schema_tokens, write_x, read_x),
        "break_even_derivation":
            "cumulative_after(n) = schema*write + schema*read*(n-1); "
            "cumulative_before(n) = removed*write*n; smallest whole n where "
            "after <= before. The first draft divided the one-time write by the "
            "per-call saving with floor division and added 1, which is neither "
            "the closed form nor a ceiling and lands on the right answer only by "
            "coincidence of these particular inputs (V2-F16).",
        "verdict": "a COST on preload tokens and a SAVING on price. Which one "
                   "governs is E2's call, and it cannot be settled until the "
                   "usage reader is closed (E0's prerequisite 4).",
    }

    report["count_tokens_calls"] = counter.calls
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print("calibration      : %s (measured %d vs committed %d)"
          % (report["calibration"]["verdict"], stage_tokens, R155_SYSTEM_PROMPT_TOKENS))
    print("tone guide alone : %d tokens" % tone_alone)
    for r, n in zip(rows, report["net"]):
        print("%-7s before %5d  after %5d  removed %4d (%.1f%%)  "
              "net %+d as shipped / %+d lean"
              % (r["network"], r["before_tokens"], r["after_tokens"],
                 r["removed_tokens"], r["removed_pct"],
                 n["net_as_shipped"], n["net_lean"]))
    print("schema in        : %d as shipped = %d structure + %d rule prose; "
          "%d lean" % (schema_tokens, bare_tokens, schema_tokens - bare_tokens,
                       lean_tokens))
    print("still volatile   : %d-token swing on /stage -> /obj"
          % report["still_volatile"]["swing_stage_to_obj_tokens"])
    print("price (DERIVED)  : %+.0f BTE/call steady state, break-even after %d calls"
          % (report["price_derived"]["steady_state_saving_bte_per_call"],
             report["price_derived"]["break_even_calls"]))
    print("count_tokens calls:", counter.calls, "(free, unbilled)")
    print("->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
