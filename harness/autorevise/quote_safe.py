"""quote_safe.py - central quoting + encoding helpers (python twin of
harness/lib/quote-safe.ps1).

Same two failure classes, same contract, so python code that emits a PowerShell
command or writes JSON has one honest tool instead of an ad-hoc fix:

  S1  unquoted-interpolation - an uncontrolled string (a leg NAME, id, branch,
      path, prompt) reaches a quoted PowerShell / shell / git context and
      shreds it.  sanitize_sq / ps_single_quote produce the same escaping the PS
      Sanitize-SQ helper does, so the test can compute the EXPECTED sanitized
      form here and assert the PS side agrees (a two-sided control).

  S8  BOM / encoding landmine - a UTF-8 BOM breaks a downstream json.load.
      write_json_no_bom writes UTF-8 with no BOM (python's default, made
      explicit and named so intent is visible at the call site).

The autorevise python surface is, as of 2026-08-16, clean by construction (its
only subprocess call uses a list argv with no shell; every json.dumps already
uses encoding="utf-8", which is BOM-free), so these are provided as the shared
helper + the test oracle rather than retrofitted over a broken call site. Use
them for any NEW python that builds a PowerShell command or writes JSON.
"""
from __future__ import annotations

import json
from pathlib import Path


def sanitize_sq(value) -> str:
    """Escape *value* for embedding inside a PowerShell SINGLE-quoted literal.

    In a single-quoted literal the only metacharacter is the single quote,
    escaped by doubling it (''). This is the exact twin of the PS Sanitize-SQ
    function; the value is meant to be placed *between* single quotes, not to
    carry them.

    >>> sanitize_sq("O'Brien")
    "O''Brien"
    >>> sanitize_sq(None)
    ''
    """
    if value is None:
        return ""
    return str(value).replace("'", "''")


def ps_single_quote(value) -> str:
    """Return a complete PowerShell single-quoted literal, quotes included.

    >>> ps_single_quote("O'Brien")
    "'O''Brien'"
    """
    return "'" + sanitize_sq(value) + "'"


def write_json_no_bom(path, obj, *, indent: int = 2) -> None:
    """Write *obj* as JSON to *path* in UTF-8 with NO byte-order mark.

    Twin of the PS Write-Utf8NoBom path. Python's ``encoding="utf-8"`` never
    emits a BOM (only ``utf-8-sig`` does), so this simply names that guarantee;
    the resulting file always parses back with a plain ``json.load``.
    """
    Path(path).write_text(
        json.dumps(obj, indent=indent, ensure_ascii=False), encoding="utf-8"
    )


def has_utf8_bom(path) -> bool:
    """True if the file at *path* starts with a UTF-8 BOM (EF BB BF).

    Handy for a lint that asserts committed JSON is BOM-free without having to
    catch the json.load exception message.
    """
    with open(path, "rb") as fh:
        return fh.read(3) == b"\xef\xbb\xbf"
