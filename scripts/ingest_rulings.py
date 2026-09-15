"""Land a human's one-word rulings on the decisions board.

    python scripts/ingest_rulings.py reply.txt
    echo "A1 ratify" | python scripts/ingest_rulings.py -
    python scripts/ingest_rulings.py reply.txt --dry-run
    python scripts/ingest_rulings.py reply.txt --who joe \\
        --roster harness/design_review/2026-09-14/RULINGS-OPEN.md

WHY THIS EXISTS
---------------
harness/design_review/<date>/RULINGS-OPEN.md asks for a PR reply shaped like
`A1 ratify`. Nothing in the tree read that reply: the ruling lived in a GitHub
comment and the repo never learned it, so the same question came back weeks
later (closeout 2026-09-15, artist lens "decisions", DEC-3).

WHAT IT DOES
------------
Reads reply lines `<ID> <word...>` (file or stdin; `#` comments and blank lines
ignored), checks every ID against the roster - the `## <ID> - <title>`
headings plus the at-a-glance table - and records each ruling through
harness/decisions.py's own resolve(): the same channel a receipt ruling closes
through, into harness/state/resolved.json. Each entry carries who ruled
(--who, default "human"), when (UTC), the roster path + sha256 as evidence,
and the word verbatim. harness/state/DECISIONS.md is then re-rendered so the
derived board agrees with the record.

WHAT IT REFUSES
---------------
Loudly, and writing NOTHING, when any line is unparseable, names an id the
roster does not carry, repeats an id, or rules an item that already carries a
ruling. All lines are validated before the first write; if a write still fails
midway, resolved.json is restored to its pre-run bytes.

Exit 0 = recorded (or --dry-run), 2 = refused, 1 = unexpected error.
"""
import argparse
import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "harness"))
try:
    import decisions
finally:
    sys.path.pop(0)

DEFAULT_ROSTER_DATE = "2026-09-14"
EXIT_REFUSED = 2

# `A1 ratify` / `- B2: keep the accent` / `**C2a** ship` -> (id, verbatim word)
_LINE = re.compile(
    r"^\s*(?:[-*]\s+)?[`*_]*([A-Za-z]\d+[a-z]?)[`*_]*\s*(?:[:—–-]\s*)?(.*?)\s*$")


def parse_reply(text):
    """[(lineno, id, word)] and [error strings] for a reply body."""
    rulings, errors = [], []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _LINE.match(line)
        if not m:
            errors.append("line %d: cannot read an id at the start of %r" % (n, raw))
            continue
        rid, word = m.group(1), m.group(2)
        if not word:
            errors.append("line %d: %s carries no word - a ruling without a word "
                          "is not a ruling" % (n, rid))
            continue
        rulings.append((n, rid, word))
    return rulings, errors


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def _read_reply(src):
    if src == "-":
        return sys.stdin.read()
    with open(src, encoding="utf-8") as fh:
        return fh.read()


def plan(roster, reply_text, who):
    """Validate everything; return (records, errors). Writes nothing.

    records: [{"lineno", "id", "word", "key", "reason", "evidence", "item"}]
    """
    errors = []
    if not who or not who.strip():
        errors.append("--who is empty - a ruling needs a ruler")
    if not os.path.isfile(roster):
        errors.append("roster not found: %s" % roster)
        return [], errors

    rulings, perrs = parse_reply(reply_text)
    errors.extend(perrs)
    if not rulings and not errors:
        errors.append("the reply carries no rulings")

    # The board reads rosters only from decisions.ROSTERS/<date>/RULINGS-OPEN.md.
    # A roster it cannot see has no board item to close, so refuse rather
    # than record a ruling the board would never reflect.
    visible = {os.path.normcase(os.path.abspath(p)) for p in decisions.roster_paths()}
    if os.path.normcase(os.path.abspath(roster)) not in visible:
        errors.append("the board does not read %s - rosters live at %s/<date>/%s"
                      % (roster, decisions._rel(decisions.ROSTERS), decisions.ROSTER_NAME))
        return [], errors

    items = {i["leg"]: i for i in decisions.roster_items(roster)}
    for i in items.values():
        i["key"] = decisions.item_key(i)
    if not items:
        errors.append("roster %s carries no `## <ID> - <title>` headings" % roster)
        return [], errors

    rel = decisions._rel(roster)
    sha = _sha256(roster)
    live = {i["key"] for i in decisions.collect(with_ages=False)}
    already = decisions.load_resolved()

    records, seen = [], {}
    for lineno, rid, word in rulings:
        if rid not in items:
            errors.append("line %d: %s is not on the roster (known: %s)"
                          % (lineno, rid, ", ".join(sorted(items))))
            continue
        if rid in seen:
            errors.append("line %d: %s already ruled on line %d of this reply"
                          % (lineno, rid, seen[rid]))
            continue
        seen[rid] = lineno
        item = items[rid]
        prior = already.get(item["key"])
        if prior is not None:
            errors.append("line %d: %s already carries a ruling - %r by %s at %s"
                          % (lineno, rid, prior.get("word", prior.get("reason")),
                             prior.get("by"), prior.get("resolved_at_utc")
                             or prior.get("resolved_at")))
            continue
        if item["key"] not in live:
            errors.append("line %d: %s is not a live board item (key %s) - the "
                          "board and the roster disagree" % (lineno, rid, item["key"]))
            continue
        records.append({
            "lineno": lineno, "id": rid, "word": word, "key": item["key"],
            "item": item,
            "reason": "%s %s - ruled against %s @ sha256 %s" % (rid, word, rel, sha[:12]),
            "evidence": {"roster": rel, "sha256": sha, "id": rid, "reply_line": lineno},
        })
    return records, errors


def _snapshot(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _restore(path, snapshot):
    if snapshot is None:
        if os.path.exists(path):
            os.remove(path)
        return
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(snapshot)
    os.replace(tmp, path)


def ingest(roster, reply_text, who="human", dry_run=False, out=sys.stdout):
    """Validate, then record every ruling or none. Returns the exit code."""
    records, errors = plan(roster, reply_text, who)
    if errors:
        out.write("  REFUSED - nothing written\n")
        for e in errors:
            out.write("  ERROR: %s\n" % e)
        return EXIT_REFUSED

    verb = "would record" if dry_run else "recorded"
    if dry_run:
        out.write("  DRY RUN - nothing written\n")
    else:
        before = _snapshot(decisions.RESOLVED)
        for r in records:
            rc, msg = decisions.resolve(r["key"], r["reason"], by=who,
                                        word=r["word"], evidence=r["evidence"])
            if rc != 0:
                _restore(decisions.RESOLVED, before)
                out.write("  REFUSED at %s - %s\n  resolved.json restored; nothing written\n"
                          % (r["id"], msg))
                return EXIT_REFUSED
    for r in records:
        out.write("  %s  %-4s %s  %s\n" % (verb, r["id"], r["key"], r["word"]))
    out.write("  %d ruling(s) %s by %s against %s @ sha256 %s\n"
              % (len(records), verb, who, records[0]["evidence"]["roster"],
                 records[0]["evidence"]["sha256"][:12]))
    if not dry_run:
        out.write("  -> %s\n" % decisions._rel(decisions.RESOLVED))
        board = decisions.write_markdown(decisions.collect())
        out.write("  wrote %s (%d open)\n"
                  % (decisions._rel(board), len(decisions.collect(with_ages=False))))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("reply", nargs="?", default="-",
                   help="file of `<ID> <word>` lines, or - for stdin (default)")
    p.add_argument("--roster", default=None,
                   help="roster to validate ids against (default: harness/design_review/%s/%s)"
                        % (DEFAULT_ROSTER_DATE, decisions.ROSTER_NAME))
    p.add_argument("--who", default="human", help="who ruled (default: human)")
    p.add_argument("--dry-run", action="store_true",
                   help="print what would be recorded; write nothing")
    ns = p.parse_args(argv)
    roster = ns.roster or os.path.join(decisions.ROSTERS, DEFAULT_ROSTER_DATE,
                                       decisions.ROSTER_NAME)
    try:
        reply_text = _read_reply(ns.reply)
    except OSError as e:
        print("  ERROR: cannot read reply %s: %s" % (ns.reply, e))
        return EXIT_REFUSED
    return ingest(roster, reply_text, who=ns.who, dry_run=ns.dry_run)


if __name__ == "__main__":
    sys.exit(main())
