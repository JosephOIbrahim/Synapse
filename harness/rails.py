# harness/rails.py - Harness budget rails.
#
# THE GAP THIS FILLS (surveyed 2026-08-31, BP1-RAILS bus finding).
# Five meters already exist and each is scope-distinct from per-run spend:
#   - harness/verify/token_ceiling.json  : STATIC preload budget of the tool
#         catalog (one-time context cost), unenforced - its claimed enforcer
#         checks.py::check_tool_surface_deferred does not exist.
#   - harness/memory/STATE.json spawn_ledger : cross-run AGENT-TURNS, capped by a
#         fail-closed capCheck() (.claude/workflows/memory-loop.js:250-266). Its
#         subagent_tokens field is HAND-recorded and enforced by nothing.
#   - harness/notes/econ_*.py : predicted prompt SIZE via count_tokens, plus a
#         chars/3.6 cost PROXY - an estimate, exactly what a ledger must not do.
#   - harness/orchestrate.ps1 : leg lifecycle + wall-clock deadline, no budget.
#   - .synapse/harness.py --budget : cumulative USD, boundary-only, writes no
#         receipt, always exits 0 (a budget block is not signalled as failure).
# None of them is a per-run cap with a hard stop that writes a receipt. rails.py
# is that, and only that. It reuses the fail-closed gate SHAPE from capCheck, the
# USD vocabulary from harness.py, and the REAL token source econ never reads.
#
# THE UNIT MODEL (Target 2).
# A cap is a TURNS FLOOR (always measurable - one charge = one turn, so it can
# never be UNKNOWN) plus an OPTIONAL TOKENS CEILING (preferred, enforced only
# when the runtime reports real usage). This is the structural form of the rule
# "tokens where measurable, agent-turns otherwise; a field the runtime cannot
# measure renders UNKNOWN and the cap falls back to the measurable unit, NEVER to
# unlimited": turns is the measurable unit that is always present, so an UNKNOWN
# token field downgrades the token meter to UNKNOWN and enforcement falls back to
# the turns floor - it can never fall back to unlimited, because the floor is
# always there. A tokens-only cap (no turns floor) is REFUSED at construction for
# exactly this reason.
#
# THE MEASUREMENT (Target 2, crucible criterion 1).
# tokens_in / tokens_out are MEASURED from the transcript's message.usage
# (input_tokens + cache_creation_input_tokens + cache_read_input_tokens, and
# output_tokens) - the source of truth Claude Code already writes and that no
# econ script reads. When no transcript/usage is available (a pre-dispatch gate,
# a dry run, a caller that did not measure) the field is the literal string
# UNKNOWN. Never zero. Never an estimate.
#
# THE LEDGER IS THE RECEIPT (mission tagline).
# Every run writes harness/battleplan/runs/<date>/ledger_<run>.json and prints
# it. STATUS VOCABULARY (BP2-METER T4 + REFEREE bus finding 2026-09-01): a run
# still accepting charges reads "open" - a LIVE wave must never read as finished.
# A run that would pass cap HALTS (never a silent continue) and reads "blocked",
# reason "budget", naming the leg it refused. Only an explicit close finalizes to
# "complete". The old to_dict mapped open->complete, so a running wave's ledger
# read "complete" with four legs still alive - that dishonesty is what this fixes.
# That file is the receipt.
#
# WHAT A TURN IS (Target 4). One turn = one LEG DISPATCH, charged through
# orchestrate.ps1's pre-dispatch Rails-Charge and resolved post-close by the
# settle. It is NOT a conversational turn: a self-cap of "40 turns" is 40 leg
# dispatches, not 40 chat turns (docs/BATTLEPLAN.md sec.12 R-3). The turns floor
# is the always-measurable unit; the optional tokens ceiling is MEASURED from the
# leg transcript at settle time, never estimated.
#
# Pure stdlib. Zero hou. Zero third-party. Importable as a library and callable
# as a CLI (open | charge | settle | close | resolve | tier) so
# harness/orchestrate.ps1 can drive it from PowerShell.
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import date as _date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The literal sentinel for an unobtainable measurement. A field that is this is
# neither zero nor an estimate - it is honestly not measured. Compared by value.
UNKNOWN = "UNKNOWN"

# CLI exit codes. 0 admitted, 7 blocked-by-budget (an EXPECTED halt, distinct so
# a caller can tell it from an error), 2 a usage/config error. A caller reads
# "non-zero => do not dispatch" and so fails closed on either 7 or 2.
EXIT_OK = 0
EXIT_BLOCKED = 7
EXIT_USAGE = 2


class BudgetExceeded(Exception):
    """Raised by Rails.charge when admitting the charge would pass the cap.

    Carries the already-written ledger so the caller has the receipt in hand.
    """

    def __init__(self, message: str, ledger: dict):
        super().__init__(message)
        self.ledger = ledger


# --------------------------------------------------------------------------- #
# Cap
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Cap:
    """A per-run cap: a mandatory turns floor + an optional tokens ceiling."""

    turns: int
    tokens: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.turns, int) or isinstance(self.turns, bool):
            raise ValueError("cap.turns must be an int (the always-measurable floor)")
        if self.turns < 0:
            raise ValueError("cap.turns must be >= 0")
        if self.tokens is not None:
            if not isinstance(self.tokens, int) or isinstance(self.tokens, bool):
                raise ValueError("cap.tokens must be an int or None")
            if self.tokens < 0:
                raise ValueError("cap.tokens must be >= 0")

    def to_dict(self) -> dict:
        return {"turns": self.turns, "tokens": self.tokens}


def parse_cap(spec) -> Cap:
    """Parse a cap from a CLI string, int, or dict into a Cap.

    Accepted forms (turns is always required so the cap can never be unlimited):
        8                       -> Cap(turns=8)
        "8"      / "8turns"     -> Cap(turns=8)
        "8turns,50000tokens"    -> Cap(turns=8, tokens=50000)
        "50000tokens"           -> REFUSED (a tokens-only cap has no floor to
                                   fall back to when tokens go UNKNOWN)
        {"turns": 8, "tokens": 50000}
    """
    if isinstance(spec, Cap):
        return spec
    if isinstance(spec, dict):
        if "turns" not in spec or spec.get("turns") is None:
            raise ValueError("a cap needs a turns floor (never-unlimited guarantee)")
        return Cap(turns=int(spec["turns"]),
                   tokens=None if spec.get("tokens") is None else int(spec["tokens"]))
    if isinstance(spec, bool):
        raise ValueError("cap spec must not be a bool")
    if isinstance(spec, int):
        return Cap(turns=spec)

    turns: int | None = None
    tokens: int | None = None
    for raw in str(spec).replace(";", ",").split(","):
        tok = raw.strip().lower()
        if not tok:
            continue
        if tok.endswith("tokens"):
            tokens = int(tok[: -len("tokens")].strip())
        elif tok.endswith("token"):
            tokens = int(tok[: -len("token")].strip())
        elif tok.endswith("turns"):
            turns = int(tok[: -len("turns")].strip())
        elif tok.endswith("turn"):
            turns = int(tok[: -len("turn")].strip())
        elif tok.endswith("legs"):
            turns = int(tok[: -len("legs")].strip())
        elif tok.endswith("leg"):
            turns = int(tok[: -len("leg")].strip())
        else:
            # a bare number is turns - the always-measurable unit
            turns = int(tok)
    if turns is None:
        raise ValueError(
            f"cap {spec!r} has no turns floor - a tokens-only cap is refused because "
            "tokens can be UNKNOWN and the cap must never fall back to unlimited"
        )
    return Cap(turns=turns, tokens=tokens)


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def _usage_of(obj):
    """Pull a message.usage dict out of one transcript record, or None."""
    if not isinstance(obj, dict):
        return None
    msg = obj.get("message")
    if isinstance(msg, dict) and isinstance(msg.get("usage"), dict):
        return msg["usage"]
    if isinstance(obj.get("usage"), dict):
        return obj["usage"]
    return None


def _as_int(v) -> int:
    """A usage subfield -> a non-negative int, or 0 when absent/malformed.

    A missing cache subfield is legitimately 0 (no cache => zero cache tokens).
    A corrupted non-numeric value ("12.5", [1], {}) is treated as 0 for THIS
    field rather than crashing the whole measurement - a torn-but-JSON-valid line
    still measures what it can, never raises (crucible #1: never crashes).
    """
    if v is None or isinstance(v, bool):
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def measure_transcript_tokens(path) -> tuple:
    """MEASURE tokens_in / tokens_out from a Claude Code transcript JSONL.

    Reuses the transcript-walk scaffold of econ_transcript_cost.py but reads the
    REAL source of truth it does not: message.usage. tokens_in is the sum of all
    input the model saw (input_tokens + cache_creation_input_tokens +
    cache_read_input_tokens); tokens_out is output_tokens. These are measured
    fields summed, never a chars/3.6 proxy.

    Returns (tokens_in, tokens_out) as ints, or (UNKNOWN, UNKNOWN) when the file
    is absent, unreadable, or carries no usage record at all. A partial file
    (some lines usable) still measures what it can.
    """
    p = Path(path)
    if not p.exists():
        return UNKNOWN, UNKNOWN
    t_in = 0
    t_out = 0
    saw = False
    try:
        with p.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue  # a torn line is skipped, never fatal
                usage = _usage_of(rec)
                if usage is None:
                    continue
                # A record counts as MEASURED only when it genuinely carries an
                # input_tokens or output_tokens field. An empty/absent usage dict
                # is UNKNOWN, never a fabricated (0,0) - .get(field, 0) cannot tell
                # an absent field from a real 0, so presence is checked explicitly
                # (crucible #1: an absent token renders UNKNOWN, never 0).
                if "input_tokens" not in usage and "output_tokens" not in usage:
                    continue
                saw = True
                t_in += _as_int(usage.get("input_tokens"))
                t_in += _as_int(usage.get("cache_creation_input_tokens"))
                t_in += _as_int(usage.get("cache_read_input_tokens"))
                t_out += _as_int(usage.get("output_tokens"))
    except OSError:
        return UNKNOWN, UNKNOWN
    if not saw:
        return UNKNOWN, UNKNOWN
    return t_in, t_out


def _measured(v) -> bool:
    """True if a token field is a real measured int (not None, not UNKNOWN).

    Token counts are integers; a float or bool here is not a measured count.
    """
    return isinstance(v, int) and not isinstance(v, bool)


def _numeric(v) -> bool:
    """True if a duration field (wall_ms) is a real measured number.

    wall_ms is an elapsed time, so int OR float both count as measured; bool does
    not. A genuine sub-millisecond measurement (e.g. 0.021) is measured, not an
    estimate and not the forbidden bare zero-for-unobtainable.
    """
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# --------------------------------------------------------------------------- #
# Rails - the per-run meter
# --------------------------------------------------------------------------- #
@dataclass
class Rails:
    run: str
    cap: Cap
    date: str = field(default_factory=lambda: _date.today().isoformat())
    runs_dir: Path | None = None
    seam_path: Path | None = None

    # live state
    turns_spent: int = 0
    tokens_spent: int = 0            # sum of MEASURED charges only
    token_meter: str = "measured"    # -> "UNKNOWN" the first time a charge is UNKNOWN
    status: str = "open"             # open (live) -> complete (finalised) | blocked
    reason: str | None = None
    blocked_on: str | None = None    # "turns" | "tokens" - which cap halted the run
    legs: list = field(default_factory=list)

    def __post_init__(self):
        self.cap = parse_cap(self.cap)
        if self.runs_dir is None:
            self.runs_dir = ROOT / "harness" / "battleplan" / "runs"
        else:
            self.runs_dir = Path(self.runs_dir)
        if self.seam_path is None:
            self.seam_path = ROOT / "harness" / "rails_exec.json"

    # -- paths -------------------------------------------------------------- #
    def dir(self) -> Path:
        return Path(self.runs_dir) / self.date

    def ledger_path(self) -> Path:
        return self.dir() / f"ledger_{self.run}.json"

    # -- enforcement -------------------------------------------------------- #
    def _remaining(self) -> dict:
        rem_turns = self.cap.turns - self.turns_spent
        if self.cap.tokens is not None and self.token_meter == "measured":
            rem_tokens = self.cap.tokens - self.tokens_spent
        else:
            rem_tokens = UNKNOWN
        return {"turns": rem_turns, "tokens": rem_tokens}

    def charge(self, leg: str, model: str, tokens_in=None, tokens_out=None,
               wall_ms=None) -> dict:
        """Pre-admission gate for one leg/turn.

        Admitted -> append a ledger entry, advance the meters, return the entry.
        Would pass cap -> mark blocked:budget, record the refused leg, WRITE the
        ledger (the receipt), and raise BudgetExceeded. Never a silent continue.
        """
        if self.status == "blocked":
            raise BudgetExceeded(
                f"run {self.run} already halted: blocked:budget", self.to_dict())

        # normalise measured token fields
        ti = tokens_in if _measured(tokens_in) else UNKNOWN
        to = tokens_out if _measured(tokens_out) else UNKNOWN
        wm = wall_ms if _numeric(wall_ms) else UNKNOWN
        this_measured = ti is not UNKNOWN and to is not UNKNOWN

        # a single UNKNOWN token charge downgrades the run's token meter, so the
        # token ceiling can no longer be guaranteed and enforcement falls to the
        # turns floor. The floor is always there, so this is never "unlimited".
        will_meter = self.token_meter == "measured" and this_measured and self.cap.tokens is not None
        enforced_unit = "tokens" if will_meter else "turns"

        prospective_turns = self.turns_spent + 1
        turns_exceed = prospective_turns > self.cap.turns

        tokens_exceed = False
        if will_meter:
            prospective_tokens = self.tokens_spent + ti + to
            tokens_exceed = prospective_tokens > self.cap.tokens

        if turns_exceed or tokens_exceed:
            which = "turns" if turns_exceed else "tokens"
            self.status = "blocked"
            self.reason = "budget"
            self.blocked_on = which
            self.legs.append({
                "leg": leg, "model": model,
                "tokens_in": ti, "tokens_out": to, "wall_ms": wm,
                "cap": self.cap.to_dict(), "remaining": self._remaining(),
                "enforced_unit": enforced_unit, "admitted": False,
                "note": f"REFUSED: dispatching would exceed the {which} cap "
                        f"({'turn ' + str(prospective_turns) + ' > ' + str(self.cap.turns) if turns_exceed else str(self.tokens_spent + ti + to) + ' tokens > ' + str(self.cap.tokens)})",
            })
            ledger = self.close()  # write the receipt before we raise
            raise BudgetExceeded(
                f"blocked:budget - {leg} would exceed the {which} cap", ledger)

        # admitted - advance the meters
        self.turns_spent = prospective_turns
        if this_measured and self.token_meter == "measured":
            self.tokens_spent += ti + to
        elif not this_measured:
            self.token_meter = UNKNOWN  # the run can no longer guarantee tokens

        entry = {
            "leg": leg, "model": model,
            "tokens_in": ti, "tokens_out": to, "wall_ms": wm,
            "cap": self.cap.to_dict(), "remaining": self._remaining(),
            "enforced_unit": enforced_unit, "admitted": True,
        }
        self.legs.append(entry)
        return entry

    # -- post-close settle (BP2-METER T1) ----------------------------------- #
    def _rederive_token_state(self) -> None:
        """Recompute tokens_spent + token_meter from the current leg list.

        The authoritative post-settle view. tokens_spent is the sum of MEASURED
        tokens over admitted legs; token_meter is "measured" only when EVERY
        admitted leg carries measured int tokens - a still-pending reservation or
        a settled-UNKNOWN leg keeps the run honest at UNKNOWN, falling enforcement
        to the turns floor. Unlike charge()'s sticky flip this HEALS: a leg whose
        UNKNOWN reservation is later settled from a real transcript restores the
        meter, because UNKNOWN means "not currently known", never "known-bad".
        """
        admitted = [e for e in self.legs if e.get("admitted")]
        self.tokens_spent = sum(
            e["tokens_in"] + e["tokens_out"] for e in admitted
            if _measured(e.get("tokens_in")) and _measured(e.get("tokens_out")))
        fully = bool(admitted) and all(
            _measured(e.get("tokens_in")) and _measured(e.get("tokens_out"))
            for e in admitted)
        self.token_meter = "measured" if fully else UNKNOWN

    def settle(self, leg: str, model: str = "", tokens_in=None, tokens_out=None,
               wall_ms=None, transcript=None) -> dict:
        """Resolve one leg's MEASURED token cost AFTER it finished (post-close).

        If a prior charge/reservation for <leg> exists, UPDATE that entry in
        place - a settle is NOT a new turn, it is the measurement of a dispatch
        already counted, so turns are never double-charged. If none exists, the
        settle opens the turn itself (turns floor enforced), so it also works
        standalone in a proof or test.

        Measured tokens flow into the cap. A settle whose measured spend crosses
        the token ceiling HALTS the run (status blocked, reason budget, blocked_on
        tokens) - the halt the orchestrator reads before its NEXT dispatch; the
        leg that just settled already ran, so it is never retroactively refused. A
        settle with no resolvable transcript records every token field the literal
        UNKNOWN (never zero, never an estimate) and leaves enforcement on the
        turns floor.
        """
        if self.status == "blocked":
            raise BudgetExceeded(
                f"run {self.run} already halted: blocked:budget", self.to_dict())

        ti = tokens_in if _measured(tokens_in) else UNKNOWN
        to = tokens_out if _measured(tokens_out) else UNKNOWN
        wm = wall_ms if _numeric(wall_ms) else UNKNOWN

        # find this leg's entry to fill IN PLACE (never a new turn): prefer an
        # un-settled reservation; else re-settle the newest already-settled entry
        # (idempotent - a second settle for the same leg must NOT open a turn).
        target = None
        resettle = None
        for e in reversed(self.legs):
            if e.get("leg") == leg and e.get("admitted"):
                if not e.get("settled", False):
                    target = e
                    break
                if resettle is None:
                    resettle = e
        if target is None:
            target = resettle  # re-settle in place, no new turn

        if target is None:
            # no entry for this leg at all - the settle opens the turn (floor bites)
            prospective_turns = self.turns_spent + 1
            if prospective_turns > self.cap.turns:
                self.status = "blocked"
                self.reason = "budget"
                self.blocked_on = "turns"
                self.legs.append({
                    "leg": leg, "model": model,
                    "tokens_in": ti, "tokens_out": to, "wall_ms": wm,
                    "transcript": transcript, "cap": self.cap.to_dict(),
                    "remaining": self._remaining(), "enforced_unit": "turns",
                    "admitted": False, "settled": True,
                    "note": f"REFUSED: settling would exceed the turns cap "
                            f"(turn {prospective_turns} > {self.cap.turns})",
                })
                ledger = self.close()  # write the receipt before we raise
                raise BudgetExceeded(
                    f"blocked:budget - settle {leg} would exceed the turns cap", ledger)
            self.turns_spent = prospective_turns
            target = {"leg": leg, "model": model, "admitted": True, "settled": False,
                      "cap": self.cap.to_dict()}
            self.legs.append(target)

        # fill the measured values IN PLACE (no new turn)
        target["tokens_in"] = ti
        target["tokens_out"] = to
        target["wall_ms"] = wm
        if model:
            target["model"] = model
        if transcript is not None:
            target["transcript"] = transcript  # provenance: the measured source
        target["settled"] = True

        # re-derive the run token state from all admitted/settled legs
        self._rederive_token_state()

        # the token ceiling: a settle whose MEASURED spend crosses it halts the
        # run. The leg already ran (its tokens are real spend); nothing further
        # dispatches. This is the halt the orchestrator reads next poll.
        if self.cap.tokens is not None and self.tokens_spent > self.cap.tokens:
            self.status = "blocked"
            self.reason = "budget"
            self.blocked_on = "tokens"
            target["note"] = (f"HALT: measured spend {self.tokens_spent} tokens crossed "
                              f"the ceiling {self.cap.tokens} at settle - the dispatch "
                              f"already ran; nothing further dispatches")

        target["enforced_unit"] = self._run_enforced_unit()
        target["remaining"] = self._remaining()
        return target

    # -- serialisation ------------------------------------------------------ #
    def _run_enforced_unit(self) -> str:
        """The unit the RUN is enforcing on.

        "tokens" only when a ceiling is set AND >= 1 admitted leg has MEASURED
        tokens (BP2-METER T1) - an empty or all-UNKNOWN run reads "turns". A
        token-ceiling halt reports "tokens" (blocked_on) even if later legs stayed
        pending, because the halt was decided on real measured spend.
        """
        if self.blocked_on:
            return self.blocked_on
        any_measured = any(
            _measured(e.get("tokens_in")) and _measured(e.get("tokens_out"))
            for e in self.legs if e.get("admitted"))
        if self.cap.tokens is not None and self.token_meter == "measured" and any_measured:
            return "tokens"
        return "turns"

    def to_dict(self) -> dict:
        # STATUS HONESTY (REFEREE bus finding 2026-09-01, T4 class): report the
        # ACTUAL status. A live run still accepting charges reads "open" - it must
        # not read "complete" while legs are alive. Only an explicit close()
        # finalises "open" -> "complete"; "blocked" is a budget halt. The old code
        # mapped open->complete HERE, so a running wave's ledger read finished.
        run_status = self.status
        totals = {
            "turns": self.turns_spent,
            "tokens_in": UNKNOWN if self.token_meter != "measured" else
                         sum(e["tokens_in"] for e in self.legs
                             if e.get("admitted") and _measured(e["tokens_in"])),
            "tokens_out": UNKNOWN if self.token_meter != "measured" else
                          sum(e["tokens_out"] for e in self.legs
                              if e.get("admitted") and _measured(e["tokens_out"])),
        }
        return {
            "run": self.run,
            "date": self.date,
            "cap": self.cap.to_dict(),
            "status": run_status,
            "reason": self.reason,
            "enforced_unit": self._run_enforced_unit(),
            "token_meter": self.token_meter,
            "totals": totals,
            "remaining": self._remaining(),
            "legs": self.legs,
            "generated_by": "harness/rails.py",
            "seam": str(Path(self.seam_path).relative_to(ROOT)) if _under_root(self.seam_path) else str(self.seam_path),
            "note": "This ledger IS the receipt (BP1-RAILS). Every token field is "
                    "MEASURED from transcript message.usage or the literal UNKNOWN; "
                    "no field is an estimate. A turns floor guarantees the cap can "
                    "never fall back to unlimited. One turn = one leg DISPATCH "
                    "(not a conversational turn; BP2-METER T4, sec.12 R-3). Status "
                    "'open' = the wave is still live, 'complete' = a finalised "
                    "close, 'blocked' = a budget halt.",
        }

    def _persist(self) -> dict:
        """Write the current ledger to disk atomically WITHOUT finalising status.

        A live run stays "open" (REFEREE honesty: a charged-but-not-closed wave
        must not read "complete"); a halted run stays "blocked". Only close()
        maps "open" -> "complete". Used by the charge/settle CLI persistence so
        the on-disk ledger reflects the live state, never a premature "complete".
        """
        ledger = self.to_dict()
        d = self.dir()
        d.mkdir(parents=True, exist_ok=True)
        path = self.ledger_path()
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)  # atomic - the .tmp+replace pattern used across the harness
        return ledger

    def close(self) -> dict:
        """Finalise (open -> complete), write the ledger (the receipt), return it.

        The explicit terminal close: an "open" (live) run becomes "complete", a
        "blocked" run stays blocked. A charge/settle that only PERSISTS uses
        _persist() and leaves the run "open" (REFEREE status-honesty fix).
        """
        if self.status == "open":
            self.status = "complete"
        return self._persist()


def _under_root(p) -> bool:
    try:
        Path(p).resolve().relative_to(ROOT)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Execution seam - a lookup, never a second orchestrator
# --------------------------------------------------------------------------- #
def resolve_model(tier: str, seam_path=None) -> str:
    """Resolve a tier (mechanical|reasoning) to a model string via rails_exec.json.

    A LOOKUP by construction: swapping in a local engine (harness/rope/
    exec_ollama.py) later means editing the JSON table, not this function.
    """
    seam_path = Path(seam_path) if seam_path else (ROOT / "harness" / "rails_exec.json")
    table = json.loads(seam_path.read_text(encoding="utf-8"))
    tiers = table.get("tiers", table)  # tolerate a flat {tier: model} table too
    if tier not in tiers:
        raise KeyError(f"unknown tier {tier!r}; rails_exec.json defines {sorted(tiers)}")
    entry = tiers[tier]
    return entry["model"] if isinstance(entry, dict) else entry


# --------------------------------------------------------------------------- #
# CLI - so harness/orchestrate.ps1 can drive rails from PowerShell
# --------------------------------------------------------------------------- #
def _state_path(run: str, date: str, runs_dir) -> Path:
    # The ledger file IS the persisted state; re-open reads it back so charges
    # accumulate across separate CLI invocations (poll to poll).
    base = Path(runs_dir) if runs_dir else (ROOT / "harness" / "battleplan" / "runs")
    return base / date / f"ledger_{run}.json"


def _load_rails(run, date, runs_dir, seam_path) -> Rails | None:
    path = _state_path(run, date, runs_dir)
    if not path.exists():
        return None
    d = json.loads(path.read_text(encoding="utf-8"))
    r = Rails(run=d["run"], cap=d["cap"], date=d["date"], runs_dir=runs_dir, seam_path=seam_path)
    r.turns_spent = d["totals"]["turns"]
    r.token_meter = d.get("token_meter", "measured")
    r.status = d["status"] if d["status"] in ("blocked",) else "open"
    r.reason = d.get("reason")
    # restore which cap halted a blocked run, so its enforced_unit stays stable
    r.blocked_on = d.get("enforced_unit") if r.status == "blocked" else None
    r.legs = d.get("legs", [])
    # rebuild tokens_spent from admitted measured entries
    if r.token_meter == "measured":
        r.tokens_spent = sum(e["tokens_in"] + e["tokens_out"] for e in r.legs
                             if e.get("admitted") and _measured(e.get("tokens_in"))
                             and _measured(e.get("tokens_out")))
    return r


def _parse_wall(v):
    """CLI wall_ms -> a measured number or None. Never fabricates a zero."""
    if v in (None, "", UNKNOWN):
        return None
    wm = float(v)
    return int(wm) if wm.is_integer() else wm


def _measure_or_explicit(transcript, tokens_in, tokens_out):
    """Resolve (tokens_in, tokens_out) for a charge/settle CLI call.

    A --transcript is MEASURED (the source of truth); otherwise the explicit
    --tokens-in/out are used, and an absent/empty/UNKNOWN value stays None so the
    field renders the literal UNKNOWN - never zero, never an estimate.
    """
    if transcript:
        ti, to = measure_transcript_tokens(transcript)
        return (None if ti is UNKNOWN else ti), (None if to is UNKNOWN else to)
    ti = None if tokens_in in (None, "", UNKNOWN) else int(tokens_in)
    to = None if tokens_out in (None, "", UNKNOWN) else int(tokens_out)
    return ti, to


def _cli(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rails.py", description="Harness budget rails")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--run", required=True)
        p.add_argument("--date", default=_date.today().isoformat())
        p.add_argument("--runs-dir", default=None)
        p.add_argument("--seam", default=None)

    po = sub.add_parser("open", help="initialise a run ledger")
    common(po)
    po.add_argument("--cap", required=True, help="e.g. 8turns or 8turns,50000tokens")

    pc = sub.add_parser("charge", help="admit or refuse one leg/turn (hard stop)")
    common(pc)
    pc.add_argument("--leg", required=True)
    pc.add_argument("--model", default="")
    pc.add_argument("--tier", default=None, help="resolve model via rails_exec.json")
    pc.add_argument("--tokens-in", "--tokens_in", dest="tokens_in", default=None)
    pc.add_argument("--tokens-out", "--tokens_out", dest="tokens_out", default=None)
    pc.add_argument("--wall-ms", "--wall_ms", dest="wall_ms", default=None)
    pc.add_argument("--transcript", default=None, help="measure tokens from this JSONL")

    # settle (BP2-METER T1): post-close, MEASURE a leg's tokens from its transcript
    # and fill in its charge entry IN PLACE (never a new turn). --wall_ms accepted
    # too so the orchestrator's brief-spelled call is honoured.
    pse = sub.add_parser("settle", help="post-close: measure + settle a leg's tokens (T1)")
    common(pse)
    pse.add_argument("--leg", required=True)
    pse.add_argument("--model", default="")
    pse.add_argument("--tier", default=None, help="resolve model via rails_exec.json")
    pse.add_argument("--tokens-in", "--tokens_in", dest="tokens_in", default=None)
    pse.add_argument("--tokens-out", "--tokens_out", dest="tokens_out", default=None)
    pse.add_argument("--wall-ms", "--wall_ms", dest="wall_ms", default=None)
    pse.add_argument("--transcript", default=None, help="measure tokens from this JSONL")

    pcl = sub.add_parser("close", help="write + print the final ledger")
    common(pcl)

    pt = sub.add_parser("tier", help="print the model string for a tier")
    pt.add_argument("--tier", required=True)
    pt.add_argument("--seam", default=None)

    # resolve <tier>: positional twin of `tier` (BP2-METER T2). orchestrate.ps1
    # calls `rails.py resolve <tier>` to turn a leg's tier into a model string.
    prs = sub.add_parser("resolve", help="print the model string for a tier (positional)")
    prs.add_argument("tier")
    prs.add_argument("--seam", default=None)

    args = ap.parse_args(argv)

    if args.cmd in ("tier", "resolve"):
        try:
            print(resolve_model(args.tier, args.seam))
            return EXIT_OK
        except (OSError, KeyError, ValueError) as e:
            print(f"rails {args.cmd} error: {e}", file=sys.stderr)
            return EXIT_USAGE

    if args.cmd == "open":
        try:
            r = Rails(run=args.run, cap=args.cap, date=args.date,
                      runs_dir=args.runs_dir, seam_path=args.seam)
        except ValueError as e:
            print(f"rails open error: {e}", file=sys.stderr)
            return EXIT_USAGE
        r._persist()  # write the empty LIVE ("open") ledger so the run exists at once
        print(f"rails open {args.run} cap={r.cap.to_dict()} -> {r.ledger_path()}")
        return EXIT_OK

    # charge / settle / close all need the persisted run
    r = _load_rails(args.run, args.date, args.runs_dir, args.seam)
    if r is None:
        print(f"rails {args.cmd} error: run {args.run} not opened (no ledger at "
              f"{_state_path(args.run, args.date, args.runs_dir)}) - fail closed",
              file=sys.stderr)
        return EXIT_USAGE

    if args.cmd == "close":
        ledger = r.close()
        print(json.dumps(ledger, indent=2, ensure_ascii=False))
        return EXIT_OK

    # charge + settle share tier resolution and token/wall parsing
    model = args.model
    if args.tier and not model:
        try:
            model = resolve_model(args.tier, args.seam)
        except (OSError, KeyError, ValueError) as e:
            print(f"rails {args.cmd} error resolving tier: {e}", file=sys.stderr)
            return EXIT_USAGE
    ti, to = _measure_or_explicit(args.transcript, args.tokens_in, args.tokens_out)
    wm = _parse_wall(args.wall_ms)

    if args.cmd == "settle":
        try:
            entry = r.settle(args.leg, model, tokens_in=ti, tokens_out=to,
                             wall_ms=wm, transcript=args.transcript)
        except BudgetExceeded as e:  # turns floor: settle opened a turn over cap
            print(f"BLOCKED:budget settle {args.leg} - receipt {r.ledger_path()}",
                  file=sys.stderr)
            print(json.dumps(e.ledger, indent=2, ensure_ascii=False))
            return EXIT_BLOCKED
        r._persist()  # persist the settled meter (stays "open" unless it halted)
        if r.status == "blocked":  # the settle crossed the TOKEN ceiling -> halt
            print(json.dumps(r.to_dict(), indent=2, ensure_ascii=False))
            print(f"BLOCKED:budget settle {args.leg} crossed the token ceiling - "
                  f"receipt {r.ledger_path()}", file=sys.stderr)
            return EXIT_BLOCKED
        print(f"settled {args.leg} model={entry.get('model') or '(none)'} "
              f"tokens_in={entry['tokens_in']} tokens_out={entry['tokens_out']} "
              f"wall_ms={entry['wall_ms']} remaining={entry['remaining']} "
              f"enforced={entry['enforced_unit']}")
        return EXIT_OK

    # charge
    try:
        entry = r.charge(args.leg, model, tokens_in=ti, tokens_out=to, wall_ms=wm)
    except BudgetExceeded as e:
        print(f"BLOCKED:budget {args.leg} - receipt {r.ledger_path()}", file=sys.stderr)
        print(json.dumps(e.ledger, indent=2, ensure_ascii=False))
        return EXIT_BLOCKED
    r._persist()  # persist the advanced meter after every admitted charge (stays open)
    print(f"admitted {args.leg} model={model or '(none)'} "
          f"remaining={entry['remaining']} enforced={entry['enforced_unit']}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(_cli())
