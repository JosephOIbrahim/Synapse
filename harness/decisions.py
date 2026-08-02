"""The consumer that did not exist: everything waiting on a human, in one place.

    python harness/decisions.py              # the board
    python harness/decisions.py --write      # also write harness/state/DECISIONS.md
    python harness/decisions.py --count      # just the number (for the statusline)

Exits 6 when any item has waited longer than SYNAPSE_DECISION_MAX_DAYS (default
30). That exit code is the whole point - see "THE AGING GATE" below.

WHY THIS EXISTS
---------------
An audit of this harness traced a finding from birth to merge and found the
arrow stops immediately:

    receipt `findings[]` and `for_ruling[]` are read by NO code, script,
    workflow, or check in the tree.                              [CONFIRMED]

Article VI of the constitution calls `for_ruling[]` "the only channel to the
human". Nothing was listening on it. 41 receipts carry findings and rulings that
no process has ever opened.

Alongside them, `harness/state/flywheel_queue.json` holds 52 improvement cycles
of which 26 sit at `ratified:false`. The triage of those 26 found only 5 to be
agent-decidable; 20 are genuine human judgement calls. So the queue is NOT
over-gated - the diagnosis that first suggested itself was wrong. The real
finding was sharper:

    24 of the 26 gate nothing mechanically. The bottleneck is triage
    ATTENTION, not authority.

Nothing was blocked. Nobody was looking. That is a different problem and it has
a different fix: not more authority, just an open count that is impossible to
miss, plus a clock.

THE AGING GATE
--------------
A queue without a clock is a queue nobody has to answer. `--count` feeds the
statusline so the number is on screen every turn, and a nonzero exit on an
over-age item makes "nobody got to it" a failing state rather than the ambient
condition.

This is the difference between a loop that is OBSERVABLE and one that is
CLOSED. Everything else here is presentation.

WHAT IT DOES NOT DO
-------------------
It does not decide, ratify, dispatch, or repair. It reads and it ranks. Gate C
(merge), the drop.json flip, and architecture rulings stay human, and
`ratified` is never written by anything in this file - `grep -n ratified` on it
returns reads only.

AGE PROVENANCE
--------------
Neither the receipt schema nor the flywheel schema records when an item was
deposited (a finding in its own right). Age is therefore DERIVED from git: the
commit date of the last change to the file carrying the item, via a single
`git log --name-only` pass. That is a lower bound on the true wait, and it is
labelled as such rather than presented as the deposit date.
"""
import argparse, hashlib, json, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RDIR = os.path.join(ROOT, "harness", "notes", "receipts")
FLYWHEEL = os.path.join(ROOT, "harness", "state", "flywheel_queue.json")
MANIFEST = os.path.join(ROOT, "harness", "legs.json")
OUT = os.path.join(ROOT, "harness", "state", "DECISIONS.md")
RESOLVED = os.path.join(ROOT, "harness", "state", "resolved.json")

MAX_DAYS = int(os.environ.get("SYNAPSE_DECISION_MAX_DAYS", 30))
EXIT_OVERDUE = 6

GREEN = {"green", "pass", "passed", "ok", "complete", "done"}
DAY = 86400.0


def _text(v, fallback="(no text)"):
    """for_ruling entries are sometimes strings and sometimes objects."""
    if isinstance(v, str):
        return v.strip() or fallback
    if isinstance(v, dict):
        for k in ("question", "ruling", "item", "text", "title", "summary",
                  "issue", "decision", "ask"):
            if isinstance(v.get(k), str) and v[k].strip():
                return v[k].strip()
        return json.dumps(v, ensure_ascii=False)[:200]
    return str(v)[:200] or fallback


def item_key(i):
    """Stable 12-hex identity for a board item.

    Derived from what the item IS (kind, source, leg, text), not from its
    position — so the key survives re-ordering and re-generation, and dies
    when the underlying text changes (a changed ruling is a new question and
    must be re-resolved, not inherit the old answer).
    """
    basis = "%s|%s|%s|%s" % (i.get("kind"), i.get("source"), i.get("leg"),
                             i.get("text"))
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:12]


def load_resolved():
    """{key: entry} from harness/state/resolved.json. Missing file = empty."""
    try:
        with open(RESOLVED, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return {}
    out = {}
    for e in (data.get("resolutions") or []):
        if isinstance(e, dict) and e.get("key"):
            out[str(e["key"])] = e
    return out


def _save_resolved(entries):
    os.makedirs(os.path.dirname(RESOLVED), exist_ok=True)
    tmp = RESOLVED + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"_doc": ("Resolution channel for the decisions board. Each entry "
                            "retires ONE board item, identified by item_key() over "
                            "(kind|source|leg|text). This file NEVER closes a flywheel "
                            "item - those close only via the human ratified flip in "
                            "flywheel_queue.json, and collect() refuses to subtract "
                            "them no matter what this file says. Append via "
                            "'python harness/decisions.py --resolve KEY --reason ...' "
                            "so every entry carries a snapshot and evidence."),
                   "resolutions": entries}, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, RESOLVED)


def file_ages():
    """{path: seconds since its last commit}, from ONE git pass."""
    ages, now = {}, time.time()
    try:
        r = subprocess.run(
            ["git", "-C", ROOT, "log", "--format=@%ct", "--name-only",
             "--", "harness/notes/receipts", "harness/state/flywheel_queue.json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30)
        if r.returncode != 0:
            return ages
        stamp = None
        for line in r.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("@"):
                try:
                    stamp = float(line[1:])
                except ValueError:
                    stamp = None
            elif stamp is not None:
                ages.setdefault(line.replace("\\", "/"), now - stamp)
    except Exception:
        pass
    return ages


def collect(with_ages=True):
    """with_ages=False skips the git pass - the statusline calls it that way,
    because its render path must spawn no subprocess (a earlier draft of that
    file called git once per orphan and took 919ms per turn)."""
    ages = file_ages() if with_ages else {}
    items = []

    # --- receipts: for_ruling[] is the constitution's only channel to the human
    try:
        names = sorted(os.listdir(RDIR))
    except OSError:
        names = []
    for name in names:
        if not name.endswith(".json"):
            continue
        path = os.path.join(RDIR, name)
        rel = "harness/notes/receipts/" + name
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            items.append({"kind": "unreadable", "source": rel, "leg": name[:-5],
                          "text": "receipt does not parse", "age": ages.get(rel)})
            continue
        if not isinstance(d, dict):
            continue
        leg = str(d.get("leg") or name[:-5])
        age = ages.get(rel)
        for fr in (d.get("for_ruling") or []):
            items.append({"kind": "ruling", "source": rel, "leg": leg,
                          "text": _text(fr), "age": age})
        status = str(d.get("status") or "").strip().lower()
        if status and status not in GREEN:
            items.append({"kind": "receipt", "source": rel, "leg": leg,
                          "text": "receipt status is %r" % d.get("status"),
                          "age": age})
        elif not status:
            items.append({"kind": "receipt", "source": rel, "leg": leg,
                          "text": "receipt has no status field", "age": age})

    # --- flywheel: cycles awaiting a human's ratified flip
    rel = "harness/state/flywheel_queue.json"
    try:
        with open(FLYWHEEL, encoding="utf-8") as fh:
            cycles = json.load(fh).get("cycles") or []
    except Exception:
        cycles = []
    for c in cycles:
        if not isinstance(c, dict) or c.get("ratified") is not False:
            continue
        cid = str(c.get("id") or c.get("cycle") or "?")
        items.append({
            "kind": "flywheel", "source": rel, "leg": cid,
            "text": _text(c.get("title") or c.get("summary") or c.get("what")
                          or c.get("finding"), "(no title)"),
            "age": ages.get(rel),
            "flip": 'set "ratified": true on cycle %s' % cid,
        })

    # --- resolution subtraction (the closure mechanism the board never had:
    # before this, collect() only ever appended, so the count could not go
    # DOWN except by hand-editing receipt JSON — every triage sitting re-read
    # already-landed items, and CLEAR SPEC names a rising count as
    # falsification).
    for i in items:
        i["key"] = item_key(i)
    resolved = load_resolved()
    if resolved:
        kept = []
        for i in items:
            # A flywheel item NEVER closes through this file, no matter what
            # resolved.json says — its only exit is the human ratified flip in
            # flywheel_queue.json. Subtracting it here would shadow the fence.
            if i["key"] in resolved and i["kind"] != "flywheel":
                continue
            kept.append(i)
        items = kept

    # Oldest first; unknown age sorts last rather than pretending to be new.
    items.sort(key=lambda i: (i["age"] is None, -(i["age"] or 0)))
    return items


def overdue(items):
    return [i for i in items if i["age"] is not None and i["age"] > MAX_DAYS * DAY]


def render(items):
    L = []
    by = {}
    for i in items:
        by.setdefault(i["kind"], []).append(i)
    L.append("")
    L.append("  DECISIONS  %d open" % len(items))
    L.append("  " + "-" * 74)
    labels = {"ruling": "for_ruling - the constitution's only channel to you",
              "receipt": "receipts not green", "flywheel": "flywheel awaiting ratified",
              "unreadable": "unreadable"}
    for kind in ("ruling", "unreadable", "receipt", "flywheel"):
        rows = by.get(kind) or []
        if not rows:
            continue
        L.append("")
        L.append("  %s  (%d)" % (labels.get(kind, kind), len(rows)))
        for i in rows:
            age = "%4dd" % int(i["age"] / DAY) if i["age"] is not None else "   ?"
            L.append("   %s  %-8s %s" % (age, i["leg"], i["text"][:88]))
    od = overdue(items)
    L.append("")
    L.append("  " + "-" * 74)
    if od:
        L.append("  %d item(s) older than %dd - the queue has stopped moving."
                 % (len(od), MAX_DAYS))
    L.append("  age is DERIVED from the last commit to the carrying file - a")
    L.append("  lower bound. Neither schema records a deposit date.")
    L.append("")
    return "\n".join(L)


def markdown(items):
    now = time.strftime("%Y-%m-%d %H:%M")
    L = ["# Open decisions", "",
         "Generated %s by `harness/decisions.py`. Do not hand-edit - it is derived." % now,
         "", "%d open, %d older than %dd." % (len(items), len(overdue(items)), MAX_DAYS),
         "", "| age | source | id | item |", "|---|---|---|---|"]
    for i in items:
        age = "%dd" % int(i["age"] / DAY) if i["age"] is not None else "?"
        L.append("| %s | %s | `%s` | %s |"
                 % (age, i["kind"], i["leg"], i["text"][:160].replace("|", "\\|")))
    flips = [i for i in items if i.get("flip")]
    if flips:
        L += ["", "## The exact flips", "",
              "`harness/state/flywheel_queue.json` - a human sets these, never an agent:", ""]
        L += ["- %s" % i["flip"] for i in flips]
    L.append("")
    return "\n".join(L)


def resolve(key, reason, by="human"):
    """Retire ONE live board item. Refuses phantoms and flywheel items.

    Requiring the key to match a LIVE item means you cannot pre-resolve
    something that has not surfaced, cannot resolve a typo, and cannot
    resolve the same item twice — each failure mode is a distinct error.
    """
    if not reason or not reason.strip():
        return 2, "a resolution without a reason is indistinguishable from a deletion"
    live = {i["key"]: i for i in collect(with_ages=False)}
    item = live.get(key)
    if item is None:
        already = load_resolved()
        if key in already:
            return 2, "key %s is already resolved (%s)" % (key, already[key].get("resolved_at"))
        return 2, ("key %s matches no live board item - run "
                   "'python harness/decisions.py --keys' to list them" % key)
    if item["kind"] == "flywheel":
        return 2, ("flywheel items close ONLY via the human ratified flip in "
                   "flywheel_queue.json - this channel refuses them by design")
    entries = list(load_resolved().values())
    entries.append({
        "key": key,
        "resolved_at": time.strftime("%Y-%m-%d %H:%M"),
        "by": by,
        "reason": reason.strip(),
        "item_snapshot": {k: item.get(k) for k in ("kind", "source", "leg", "text")},
    })
    _save_resolved(entries)
    return 0, "resolved %s (%s: %s)" % (key, item["leg"], item["text"][:60])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--write", action="store_true")
    p.add_argument("--count", action="store_true")
    p.add_argument("--keys", action="store_true",
                   help="board with each item's resolution key")
    p.add_argument("--resolve", metavar="KEY",
                   help="retire one item (requires --reason)")
    p.add_argument("--reason", default="",
                   help="why the item is resolved - the evidence, not a mood")
    p.add_argument("--resolved", action="store_true",
                   help="list past resolutions")
    ns = p.parse_args(argv)

    if ns.resolve:
        rc, msg = resolve(ns.resolve, ns.reason)
        print(("  " if rc == 0 else "  ERROR: ") + msg)
        return rc

    if ns.resolved:
        for e in load_resolved().values():
            snap = e.get("item_snapshot") or {}
            print("  %s  %s  %-8s %s" % (e.get("key"), e.get("resolved_at"),
                                         snap.get("leg", "?"),
                                         str(e.get("reason"))[:80]))
        return 0

    items = collect()
    if ns.keys:
        for i in items:
            print("  %s  %-9s %-8s %s" % (i["key"], i["kind"], i["leg"],
                                          i["text"][:76]))
        print("  -- %d open" % len(items))
        return 0
    if ns.count:
        print(len(items))
        return EXIT_OVERDUE if overdue(items) else 0

    print(render(items))
    if ns.write:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        tmp = OUT + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(markdown(items))
        os.replace(tmp, OUT)
        print("  wrote %s" % os.path.relpath(OUT, ROOT))
    return EXIT_OVERDUE if overdue(items) else 0


if __name__ == "__main__":
    sys.exit(main())
