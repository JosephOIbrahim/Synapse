"""Query an externally built SideFX library; never build or download on lookup.

The publisher owns immutable generation databases and atomically replaces
``current.json``. Each lookup resolves that pointer again and owns one read-only
SQLite connection, so a generation swap and calls from different workers are
safe. This source is document evidence, never runtime symbol authority.
"""
from __future__ import annotations

from contextlib import closing
from itertools import zip_longest
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import sqlite3
import time
from typing import Any


CONFIG_PATH = Path(__file__).resolve().parents[4] / ".synapse" / "sidefx_library.json"
ROOT_ENV = "SYNAPSE_SIDEFX_CORPUS_ROOT"
CONFIG_SCHEMA = "synapse_sidefx_library/v1"
POINTER_SCHEMA = "sidefx_library_pointer/v1"
DATABASE_SCHEMA = "sidefx_library/v1"
MAX_CANDIDATES = 256
QUERY_SECONDS = 2.0
_JSON_LIMIT = 1024 * 1024


class LibraryUnavailable(ValueError):
    """An explicitly configured source cannot be safely queried."""


def _read_json(path: Path) -> dict:
    with path.open("rb") as stream:
        raw = stream.read(_JSON_LIMIT + 1)
    if len(raw) > _JSON_LIMIT:
        raise LibraryUnavailable(f"JSON manifest exceeds {_JSON_LIMIT} bytes")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise LibraryUnavailable("JSON manifest must be an object")
    return value


def _configured_root() -> Path | None:
    value = os.environ.get(ROOT_ENV)
    if value is None:
        try:
            config = _read_json(CONFIG_PATH)
        except FileNotFoundError:
            return None
        if config.get("schema") != CONFIG_SCHEMA:
            raise LibraryUnavailable("unsupported library configuration schema")
        value = config.get("root")
    if not isinstance(value, str) or not value.strip():
        raise LibraryUnavailable("library root must be a nonempty absolute local path")
    # A lookup must not turn a bad configuration into a network filesystem call.
    if value.startswith(("\\\\", "//")):
        raise LibraryUnavailable("network library roots are not supported")
    root = Path(value).expanduser()
    if not root.is_absolute():
        raise LibraryUnavailable("library root must be an absolute local path")
    return root.resolve()


def _within(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise LibraryUnavailable("library pointer escapes the configured root")
    return resolved


def _database_path(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise LibraryUnavailable("library pointer is missing its database path")
    relative = PurePosixPath(value)
    if ("\\" in value or PureWindowsPath(value).drive or relative.is_absolute()
            or ".." in relative.parts or len(relative.parts) != 2
            or relative.parts[0] != "indexes" or relative.suffix != ".sqlite3"):
        raise LibraryUnavailable("unsafe library database path; expected indexes/<generation>.sqlite3")
    return _within(root, root.joinpath(*relative.parts))


def _query_tokens(query: str) -> list[str]:
    return list(dict.fromkeys(word.casefold() for word in re.findall(r"[A-Za-z0-9_]+", query)
                              if len(word) > 1))[:24]


def _match_query(query: str, operator: str = "OR") -> str:
    # Quoting even bare words avoids interpreting AND/OR/NOT as FTS operators.
    return f" {operator} ".join(f'"{word}"' for word in _query_tokens(query))


def _title_phrases(query: str) -> dict[str, tuple[int, int]]:
    """Bounded contiguous phrases, retaining dotted names as a single subject."""
    words = re.findall(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*", query.casefold())[:24]
    # A conversational preamble is not the subject's position. Keep the
    # original FTS terms for recall; normalize only the title matching signal.
    preamble = {"how", "what", "which", "do", "does", "can", "could", "i", "we", "you",
                "use", "using", "the", "a", "an", "to", "please", "explain", "tell", "me",
                "about", "is", "are"}
    start = 0
    while start < len(words) and words[start] in preamble:
        start += 1
    words = words[start:] or words
    phrases = {}
    for start in range(len(words)):
        for end in range(start + 1, min(start + 6, len(words)) + 1):
            phrases.setdefault(" ".join(words[start:end]), (start, end - start))
        # A fully qualified member also names its owning class/module.
        parts = words[start].split(".")
        for end in range(2, len(parts)):
            phrases.setdefault(".".join(parts[:end]), (start, 1))
    return phrases


def _candidate_budget(k: int) -> int:
    return min(MAX_CANDIDATES, max(k * 4, 32))


def _precision_score(entry: dict, tokens: set[str], phrases: dict,
                     conjunctive: bool) -> float:
    """Reward the named subject and requested member, not incidental backlinks.

    These are query-shape signals, not a vocabulary of preferred node names.
    Context coverage can outweigh a short generic title; BM25 breaks equal
    scores. Related/source-directive sections remain available as recall.
    """
    title = " ".join(str(entry.get("title", "")).replace("\\", "").casefold().split())
    subject = phrases.get(title)
    # A lone descriptive word later in a query ("installation", "radius")
    # is weak evidence of a named page. Leading/multiword/code subjects are
    # specific enough to earn the title boost.
    named = subject and (subject[0] == 0 or subject[1] > 1 or "." in title or "_" in title)
    score = (4 + 2 * subject[1] + (3 if subject[0] == 0 else 0)) if named else 0
    body_tokens = set(re.findall(r"[A-Za-z0-9_]+", str(entry.get("searchable_text", "")).casefold()))
    score += 6 * len(tokens & body_tokens) / len(tokens)
    score += 2 if conjunctive else 0
    heading = str(entry.get("heading", "")).strip().casefold()
    signature = re.match(r"^[`*\s]*([a-z_][\w.]*)\s*\(", heading)
    title_tokens = set(_query_tokens(title))
    if signature and signature.group(1).split(".")[-1] in tokens - title_tokens:
        score += 10 if subject else 3
    elif heading in phrases and heading != title:
        score += 3
    if heading in {"related", "see also", "source directives (unexpanded)"} and heading not in phrases:
        score -= 12
    source_name = str(entry.get("source_url", "")).split("?", 1)[0].rsplit("/", 1)[-1]
    if (source_name in {"index.md", "index.html", "index.txt"} and tokens - title_tokens
            and not tokens & {"index", "overview", "list"}):
        score -= 12
    return score


def _citation_source(source_url: str, value: Any) -> str:
    """Accept a chunk's anchored citation only within its authoritative page."""
    if isinstance(value, str) and (value == source_url or value.startswith(source_url + "#")):
        return value
    return source_url


def _search(connection: sqlite3.Connection, query: str, domain: str,
            k: int, where: dict | None, generation: str) -> list[dict]:
    match = _match_query(query)
    if not match or k == 0:
        return []
    clauses = ["chunks_fts MATCH ?", "c.domain IN ('docs', 'vex')"]
    parameters: list[Any] = [match]
    if domain != "both":
        clauses.append("c.domain = ?")
        parameters.append(domain)
    if where and "type" in where:
        clauses.append("COALESCE(json_extract(c.metadata, '$.type'), '') = ?")
        parameters.append(where["type"])
    if where and "source_contains" in where:
        # instr is literal and case-sensitive, matching Scout's existing filter.
        # Mirror _citation_source so an anchor filter is applied before LIMIT,
        # without accepting an unrelated metadata URL as source authority.
        citation = "json_extract(c.metadata, '$.source')"
        clauses.append(
            "instr(CASE WHEN json_type(c.metadata, '$.source') = 'text' AND ("
            f"{citation} = c.source_url OR substr({citation}, 1, length(c.source_url) + 1) "
            f"= c.source_url || '#') THEN {citation} ELSE c.source_url END, ?) > 0")
        parameters.append(where["source_contains"])
    budget = _candidate_budget(k)
    phrases = _title_phrases(query)

    def candidates(expression: str, titles: bool = False) -> list:
        restrictions = list(clauses)
        values = [expression, *parameters[1:]]
        if titles:
            placeholders = ",".join("?" for _ in phrases)
            restrictions.append(f"replace(c.title, char(92), '') COLLATE NOCASE IN ({placeholders})")
            values.extend(phrases)
        return connection.execute(
            "SELECT chunks_fts.id, bm25(chunks_fts) FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.id "
            "WHERE " + " AND ".join(restrictions) + " ORDER BY bm25(chunks_fts) LIMIT ?",
            [*values, budget],
        ).fetchall()

    # Precision and recall are separate candidate sources. All-term matches
    # alone miss useful chunks that describe a concept using different words.
    title_rows = candidates(match, titles=True) if phrases else []
    all_match = _match_query(query, "AND")
    all_rows = candidates(all_match)
    broad_rows = candidates(match) if all_match != match else all_rows
    bm25 = {}
    for row in title_rows + all_rows + broad_rows:
        bm25[row[0]] = min(bm25.get(row[0], float("inf")), row[1])
    # Share a single bounded metadata budget; a long class page must not crowd
    # every broad/conjunctive candidate out before the precision comparison.
    ids = list(dict.fromkeys(row[0] for group in zip_longest(title_rows, all_rows, broad_rows)
                             for row in group if row is not None))[:budget]
    if not ids:
        return []
    # Only this shortlist crosses the Python boundary as document metadata/body.
    placeholders = ",".join("?" for _ in ids)
    rows = connection.execute(
        "SELECT id, source_url, title, body, metadata, domain FROM chunks "
        f"WHERE id IN ({placeholders})", ids,
    ).fetchall()
    entries = {}
    for row in rows:
        entry = json.loads(row[4])
        if not isinstance(entry, dict):
            raise LibraryUnavailable("shortlisted document metadata must be an object")
        identity = str(row[0])
        if not identity.startswith("sidefx_library:"):
            identity = f"sidefx_library:{identity}"
        source = _citation_source(row[1], entry.get("source"))
        entry.update(id=identity, source=source, source_url=row[1],
                     title=row[2], searchable_text=row[3], domain=row[5],
                     evidence_level="document_only", retrieval_source="sidefx_library",
                     library_generation=generation)
        entries[row[0]] = entry
    conjunctive_ids = {row[0] for row in all_rows}
    tokens = set(_query_tokens(query))
    ids.sort(key=lambda key: (-_precision_score(entries[key], tokens, phrases, key in conjunctive_ids),
                              bm25[key]))
    return [entries[key] for key in ids[:k]]


def query_library(query: str, domain: str = "both", k: int = 24,
                  where: dict | None = None) -> dict | None:
    """Return a ranked shortlist and source status, or None if not configured.

    Configured failures are explicit and allow Scout to retain its existing
    sources. Coverage is the publisher's recorded audit, not an expensive scan
    of all source files on every query. Metadata/pointer disagreement fails loud.
    """
    status: dict[str, Any] = {"status": "unavailable", "read_only": True}
    try:
        root = _configured_root()
        if root is None:
            return None
        status["root"] = str(root)
        pointer = _read_json(_within(root, root / "current.json"))
        if pointer.get("schema") != POINTER_SCHEMA:
            raise LibraryUnavailable("unsupported library pointer schema")
        generation = pointer.get("generation")
        if not isinstance(generation, str) or not generation.strip():
            raise LibraryUnavailable("library pointer is missing its generation")
        coverage = pointer.get("coverage")
        if not isinstance(coverage, dict):
            raise LibraryUnavailable("library pointer is missing its coverage audit")
        database = _database_path(root, pointer.get("database"))
        status.update(generation=generation, database=pointer["database"])
        limit = min(max(int(k), 0), MAX_CANDIDATES)
        deadline = time.monotonic() + QUERY_SECONDS
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True,
                                     timeout=1.0)) as connection:
            connection.execute("PRAGMA query_only = ON")
            connection.execute("PRAGMA trusted_schema = OFF")
            connection.set_progress_handler(lambda: time.monotonic() > deadline, 10000)
            connection.execute("BEGIN")
            meta = dict(connection.execute(
                "SELECT key, value FROM meta WHERE key IN ('schema', 'generation', 'coverage')"
            ).fetchall())
            if json.loads(meta.get("schema", "null")) != DATABASE_SCHEMA:
                raise LibraryUnavailable("unsupported library database schema")
            if "generation" not in meta or "coverage" not in meta:
                raise LibraryUnavailable("library database is missing generation/coverage metadata")
            if json.loads(meta["generation"]) != generation:
                raise LibraryUnavailable("library pointer/database generation mismatch")
            if json.loads(meta["coverage"]) != coverage:
                raise LibraryUnavailable("library pointer/database coverage mismatch")
            entries = _search(connection, query, domain, limit, where, generation)
        status.update(status="ready", coverage=coverage, candidate_limit=_candidate_budget(limit),
                      requested_limit=limit,
                      coverage_basis="published_database_metadata")
        return {"entries": entries, "source_status": status, "warnings": []}
    except (OSError, ValueError, TypeError, sqlite3.Error) as exc:
        reason = str(exc)
        status["reason"] = reason
        return {"entries": [], "source_status": status, "warnings": [
            f"[scout] SideFX library unavailable: {reason} — using existing Scout sources only."]}
