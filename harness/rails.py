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
# it. A run that passes cap closes status "complete"; a run that would pass cap
# HALTS - it never silently continues - and closes status "blocked", reason
# "budget", naming the leg it refused. That file is the receipt.
#
# Pure stdlib. Zero hou. Zero third-party. Importable as a library and callable
# as a CLI (open | charge | close | tier) so harness/orchestrate.ps1 can drive it
# from PowerShell.
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
                saw = True
                t_in += int(usage.get("input_tokens", 0) or 0)
                t_in += int(usage.get("cache_creation_input_tokens", 0) or 0)
                t_in += int(usage.get("cache_read_input_tokens", 0) or 0)
                t_out += int(usage.get("output_tokens", 0) or 0)
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
    status: str = "open"             # open -> complete | blocked
    reason: str | None = None
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

    # -- serialisation ------------------------------------------------------ #
    def to_dict(self) -> dict:
        if self.status == "open":
            run_status = "complete"
        else:
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
            "enforced_unit": "tokens" if (self.cap.tokens is not None and
                                          self.token_meter == "measured") else "turns",
            "token_meter": self.token_meter,
            "totals": totals,
            "remaining": self._remaining(),
            "legs": self.legs,
            "generated_by": "harness/rails.py",
            "seam": str(Path(self.seam_path).relative_to(ROOT)) if _under_root(self.seam_path) else str(self.seam_path),
            "note": "This ledger IS the receipt (BP1-RAILS). Every token field is "
                    "MEASURED from transcript message.usage or the literal UNKNOWN; "
                    "no field is an estimate. A turns floor guarantees the cap can "
                    "never fall back to unlimited.",
        }

    def close(self) -> dict:
        """Finalise, write the ledger (the receipt) atomically, return it."""
        if self.status == "open":
            self.status = "complete"
        ledger = self.to_dict()
        d = self.dir()
        d.mkdir(parents=True, exist_ok=True)
        path = self.ledger_path()
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)  # atomic - the .tmp+replace pattern used across the harness
        return ledger


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
    r.legs = d.get("legs", [])
    # rebuild tokens_spent from admitted measured entries
    if r.token_meter == "measured":
        r.tokens_spent = sum(e["tokens_in"] + e["tokens_out"] for e in r.legs
                             if e.get("admitted") and _measured(e.get("tokens_in"))
                             and _measured(e.get("tokens_out")))
    return r


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
    pc.add_argument("--tokens-in", default=None)
    pc.add_argument("--tokens-out", default=None)
    pc.add_argument("--wall-ms", default=None)
    pc.add_argument("--transcript", default=None, help="measure tokens from this JSONL")

    pcl = sub.add_parser("close", help="write + print the final ledger")
    common(pcl)

    pt = sub.add_parser("tier", help="print the model string for a tier")
    pt.add_argument("--tier", required=True)
    pt.add_argument("--seam", default=None)

    args = ap.parse_args(argv)

    if args.cmd == "tier":
        try:
            print(resolve_model(args.tier, args.seam))
            return EXIT_OK
        except (OSError, KeyError, ValueError) as e:
            print(f"rails tier error: {e}", file=sys.stderr)
            return EXIT_USAGE

    if args.cmd == "open":
        try:
            r = Rails(run=args.run, cap=args.cap, date=args.date,
                      runs_dir=args.runs_dir, seam_path=args.seam)
        except ValueError as e:
            print(f"rails open error: {e}", file=sys.stderr)
            return EXIT_USAGE
        r.close()  # write the empty ledger so the run exists on disk immediately
        print(f"rails open {args.run} cap={r.cap.to_dict()} -> {r.ledger_path()}")
        return EXIT_OK

    # charge / close both need the persisted run
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

    # charge
    model = args.model
    if args.tier and not model:
        try:
            model = resolve_model(args.tier, args.seam)
        except (OSError, KeyError, ValueError) as e:
            print(f"rails charge error resolving tier: {e}", file=sys.stderr)
            return EXIT_USAGE

    ti = to = None
    if args.transcript:
        ti, to = measure_transcript_tokens(args.transcript)
        ti = None if ti is UNKNOWN else ti
        to = None if to is UNKNOWN else to
    else:
        ti = None if args.tokens_in in (None, "", UNKNOWN) else int(args.tokens_in)
        to = None if args.tokens_out in (None, "", UNKNOWN) else int(args.tokens_out)
    if args.wall_ms in (None, "", UNKNOWN):
        wm = None
    else:
        wm = float(args.wall_ms)
        if wm.is_integer():
            wm = int(wm)

    try:
        entry = r.charge(args.leg, model, tokens_in=ti, tokens_out=to, wall_ms=wm)
    except BudgetExceeded as e:
        print(f"BLOCKED:budget {args.leg} - receipt {r.ledger_path()}", file=sys.stderr)
        print(json.dumps(e.ledger, indent=2, ensure_ascii=False))
        return EXIT_BLOCKED
    r.close()  # persist the advanced meter after every admitted charge
    print(f"admitted {args.leg} model={model or '(none)'} "
          f"remaining={entry['remaining']} enforced={entry['enforced_unit']}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(_cli())
