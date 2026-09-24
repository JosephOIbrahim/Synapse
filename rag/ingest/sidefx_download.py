"""Bounded, resumable archive of the official SideFX Markdown link graph.

Raw bytes live in immutable cache/web/objects/<sha256>.md files;
web_manifest.json is an atomic checkpoint. Older URL-addressed cache records
remain usable on resume and conditional 304 responses without migration.
Index captures use .txt objects; llms.txt remains a readable latest alias.
closure_complete means the discovered traversal queue was exhausted, including
failed pages. fetch_complete additionally requires every discovered page to be
verified. Neither flag claims that unlinked pages exist in the archive. APEX
pages are archived here; retrieval federation belongs to the separate builder.
This module never imports Houdini, builds search indexes, or stores credentials.
"""
from __future__ import annotations

import argparse
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
from html import unescape
from html.parser import HTMLParser
from http.client import HTTPException, IncompleteRead
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


SCHEMA = "sidefx_web_manifest/v1"
BASE_URL = "https://www.sidefx.com/docs/houdini/"
INDEX_URL = BASE_URL + "llms.txt"
_PREFIX = "/docs/houdini/"
_BUILD = re.compile(r"(?:HOUDINI\s+help|Houdini\s+(?:version|build))[^\n]{0,160}?(\d+\.\d+\.\d+)", re.I)
_MARKDOWN_LINK = re.compile(r"\]\(\s*(<[^>]+>|(?:\\.|[^()\s]|\([^()]*\))+)")
_REFERENCE_LINK = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*(<[^>]+>|\S+)", re.M)
_RESERVED = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", re.I)
_TRANSIENT = {408, 425, 429, 500, 502, 503, 504}


def _now():
    return datetime.now(timezone.utc).isoformat()


def canonical_url(value, base=INDEX_URL, *, index=False):
    """Resolve links inside the HTTPS documentation scope, stripping variants."""
    value = unescape(str(value)).strip().strip("<>")
    if not value or value.startswith("#") or any(ord(c) < 32 for c in value):
        return None
    try:
        parts = urlsplit(urljoin(base, value))
        if (parts.scheme != "https" or parts.hostname != "www.sidefx.com"
                or parts.username or parts.password or parts.port not in (None, 443)):
            return None
        path = unquote(parts.path)
        if ("\\" in path or any(ord(c) < 32 for c in path)
                or any(p in (".", "..") for p in path.split("/"))
                or re.search(r"%(?:2e|2f|5c)", path, re.I)
                or not path.startswith(_PREFIX)):
            return None
        # Local paths collapse repeated separators; give the URL the same identity.
        path = re.sub(r"/+", "/", path)
        if path == _PREFIX + "llms.txt" and index:
            pass
        elif path.endswith(".html"):
            path = path[:-5] + ".md"
        elif not path.endswith(".md"):
            return None
        return urlunsplit(("https", "www.sidefx.com", quote(path, safe="/-._~"), "", ""))
    except (TypeError, ValueError):
        return None


def relative_path(url):
    return unquote(urlsplit(url).path)[len(_PREFIX):]


class _Hrefs(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.links.append(value)


def discover_links(raw, source_url):
    """Markdown inline/reference links and inline HTML hrefs, deduplicated."""
    text = raw.decode("utf-8-sig")
    parser = _Hrefs()
    parser.feed(text)
    candidates = parser.links + _MARKDOWN_LINK.findall(text) + _REFERENCE_LINK.findall(text)
    return sorted({relative_path(url) for candidate in candidates
                   if (url := canonical_url(candidate, source_url)) is not None})


def docs_build(raw):
    match = _BUILD.search(raw.decode("utf-8-sig"))
    return match.group(1) if match else None


def _validate_markdown(raw, headers):
    """SideFX serves heading-free includes and licenses as UTF-8 text/plain."""
    text = raw.decode("utf-8-sig").strip()
    content_type = next((v for k, v in headers.items() if k.lower() == "content-type"), "")
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type and media_type not in {"text/plain", "text/markdown", "text/x-markdown"}:
        raise FetchError("response is not Markdown text: " + media_type)
    if not text or any(ord(c) < 32 and c not in "\t\r\n" for c in text):
        raise FetchError("empty or binary Markdown response")
    if re.match(r"(?is)^(?:<!--.*?-->\s*)*(?:<!doctype\s+html|<html\b|<head\b|<body\b)", text):
        raise FetchError("HTML document returned instead of Markdown")
    if re.fullmatch(r"(?is)(?:\d{3}\s+)?(?:bad gateway|gateway timeout|service unavailable|internal server error|access denied|forbidden|not found)\s*[.!]?", text):
        raise FetchError("HTTP error envelope returned instead of Markdown")
    if text.startswith(("{", "[")):
        try:
            payload = json.loads(text)
        except ValueError:
            pass
        else:
            if isinstance(payload, dict) and any(key in payload for key in ("error", "errors", "message")):
                raise FetchError("JSON error envelope returned instead of Markdown")


def cache_relative(path, root):
    """Keep ordinary paths readable; escape Windows names/case/long-path aliases."""
    parts = path.split("/")
    safe = (path == path.lower() and parts[0] != "_hashed"
            and all(re.fullmatch(r"[a-z0-9_. -]+", p) and p not in (".", "..")
                    and not p.endswith((".", " ")) and not _RESERVED.match(p) for p in parts)
            and len(str(root / "cache/web" / path)) < 230)
    if safe:
        return "cache/web/" + path
    digest = hashlib.sha256(path.encode("utf-8")).hexdigest()
    return "cache/web/_hashed/" + digest[:2] + "/" + digest + ".md"


def _atomic(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".sidefx-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


@contextmanager
def _archive_lock(root):
    """One writer; OS locks release automatically after a killed process."""
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".web_download.lock").open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("another downloader owns this archive") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


class LimitReached(RuntimeError):
    pass


class FetchError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Redirects are inspected and budgeted before another request.


class _Budget:
    def __init__(self, requests, byte_limit):
        self.max_requests, self.max_bytes = requests, byte_limit
        self.requests = self.bytes_received = self.reserved = 0
        self.lock = threading.Lock()

    def request(self):
        with self.lock:
            if self.requests >= self.max_requests:
                raise LimitReached("max_requests")
            self.requests += 1

    def read(self, response, amount):
        with self.lock:
            size = min(amount, self.max_bytes - self.bytes_received - self.reserved)
            if size <= 0:
                raise LimitReached("max_bytes")
            self.reserved += size
        raw = b""
        try:
            raw = response.read(size)
            return raw
        except IncompleteRead as error:
            raw = error.partial
            raise
        finally:
            with self.lock:
                self.reserved -= size
                self.bytes_received += len(raw)


def _retry_delay(value, attempt):
    delay = min(8.0, 0.5 * 2 ** attempt)
    if value:
        try:
            delay = max(0.0, float(value))
        except ValueError:
            try:
                delay = max(0.0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                pass
    if delay > 60:
        raise FetchError("server Retry-After exceeds 60 seconds; resume later")
    return delay


class Downloader:
    def __init__(self, root, *, workers=8, max_pages=100000, max_requests=200000,
                 max_bytes=5 * 1024 ** 3, max_page_bytes=8 * 1024 ** 2,
                 retries=3, timeout=30, checkpoint_every=100, opener_factory=None,
                 sleep=time.sleep):
        if not 1 <= workers <= 16:
            raise ValueError("workers must be in 1..16")
        if min(max_pages, max_requests, max_bytes, max_page_bytes, checkpoint_every, timeout) <= 0:
            raise ValueError("all page, request, byte, checkpoint, and timeout limits must be positive")
        if not 0 <= retries <= 5:
            raise ValueError("retries must be in 0..5")
        self.root = Path(root).resolve()
        self.workers, self.max_pages = workers, max_pages
        self.max_page_bytes, self.retries, self.timeout = max_page_bytes, retries, timeout
        self.checkpoint_every = checkpoint_every
        self.budget = _Budget(max_requests, max_bytes)
        self.opener_factory = opener_factory or (lambda: build_opener(_NoRedirect()))
        self.local = threading.local()
        self.sleep = sleep
        self.pages, self.previous = {}, {}
        self.discovered, self.processed, self.limit_reasons = set(), set(), set()
        self.index = None
        self.index_history = {}
        self.started_at = _now()

    def _path(self, relative):
        path = (self.root / relative).resolve()
        if Path(relative).is_absolute() or not path.is_relative_to(self.root):
            raise ValueError("cache path escapes archive root")
        return path

    def _cached(self, record):
        if not isinstance(record, dict) or record.get("status", "ok") != "ok":
            return None
        try:
            path = self._path(record["path"])
            if path.stat().st_size > self.max_page_bytes:
                return None
            raw = path.read_bytes()
            return raw if hashlib.sha256(raw).hexdigest() == record.get("sha256") else None
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def _fetch(self, url, prior=None, cached=None):
        headers = {"User-Agent": "SYNAPSE-DocsArchive/1.0", "Accept": "text/markdown,text/plain;q=0.9"}
        if cached is not None and prior:
            for field, header in (("etag", "If-None-Match"), ("last_modified", "If-Modified-Since")):
                if prior.get(field):
                    headers[header] = prior[field]
        if not hasattr(self.local, "opener"):
            self.local.opener = self.opener_factory()
        current, visited = url, set()
        for redirects in range(6):
            if current in visited:
                raise FetchError("redirect loop")
            visited.add(current)
            redirect = None
            for attempt in range(self.retries + 1):
                self.budget.request()
                try:
                    try:
                        response = self.local.opener.open(Request(current, headers=headers), timeout=self.timeout)
                    except HTTPError as error:
                        response = error
                    with response:
                        status = response.status if hasattr(response, "status") else response.code
                        response_headers = response.headers
                        if status in (301, 302, 303, 307, 308):
                            redirect = canonical_url(response_headers.get("Location", ""), current, index=True)
                            if redirect is None:
                                raise FetchError("redirect leaves official Markdown documentation scope")
                            break
                        if status == 304:
                            if cached is None:
                                raise FetchError("304 without a SHA256-verified cached page")
                            return cached, dict(response_headers), current, True
                        if status in _TRANSIENT and attempt < self.retries:
                            delay = _retry_delay(response_headers.get("Retry-After"), attempt)
                        elif status != 200:
                            raise FetchError("HTTP " + str(status))
                        else:
                            # A custom opener must not silently bypass redirect policy.
                            actual = canonical_url(response.geturl(), index=True)
                            if actual != current:
                                raise FetchError("unvalidated response redirect")
                            content_length = response_headers.get("Content-Length")
                            length = int(content_length) if content_length and content_length.isdigit() else None
                            if length is not None and length > self.max_page_bytes:
                                raise FetchError("max_page_bytes")
                            chunks, size = [], 0
                            while length is None or size < length:
                                amount = min(65536, self.max_page_bytes + 1 - size)
                                if length is not None:
                                    amount = min(amount, length - size)
                                raw = self.budget.read(response, amount)
                                if not raw:
                                    break
                                chunks.append(raw)
                                size += len(raw)
                                if size > self.max_page_bytes:
                                    raise FetchError("max_page_bytes")
                            if length is not None and size != length:
                                raise URLError("truncated response")
                            raw = b"".join(chunks)
                            _validate_markdown(raw, response_headers)
                            return raw, dict(response_headers), current, False
                except (URLError, TimeoutError, ConnectionError, OSError, HTTPException) as error:
                    if attempt == self.retries:
                        raise FetchError(type(error).__name__ + ": " + str(error)) from error
                    delay = _retry_delay(None, attempt)
                self.sleep(delay)
            if redirect is None:
                raise FetchError("request retries exhausted")
            current = redirect
        raise FetchError("redirect limit exceeded")

    def _record(self, key, raw, headers, source_url, prior=None, unchanged=False):
        digest = hashlib.sha256(raw).hexdigest()
        if key is None:
            target = "cache/web/objects/" + digest + ".txt"
        elif unchanged and prior and self._cached(prior) is not None:
            target = prior["path"]
        else:
            target = "cache/web/objects/" + digest + ".md"
        if self._cached({"path": target, "sha256": digest}) is None:
            _atomic(self._path(target), raw)
        if key is None and self._cached({"path": "llms.txt", "sha256": digest}) is None:
            _atomic(self._path("llms.txt"), raw)
        build = docs_build(raw)
        inferred = self.index.get("docs_build") if self.index else None
        lower = {k.lower(): v for k, v in headers.items()}
        validators = (prior or {}) if unchanged else {}
        return dict(path=target, source_url=source_url, sha256=digest,
                    docs_build=build or inferred, build_source="page" if build else "index_inferred" if inferred else "unknown",
                    fetched_at=prior.get("fetched_at") if unchanged and prior else _now(),
                    validated_at=_now(), etag=lower.get("etag", validators.get("etag")),
                    last_modified=lower.get("last-modified", validators.get("last_modified")),
                    status="ok", error=None, bytes=len(raw))

    def _checkpoint(self, final=False):
        pending = sorted(self.discovered - self.processed)
        errors = {key: value["error"] for key, value in self.pages.items() if value["status"] == "error"}
        closure = bool(final and self.index and not pending and not self.limit_reasons)
        complete = closure and not errors and len(self.pages) == len(self.discovered)
        manifest = dict(schema=SCHEMA, source=dict(index_url=INDEX_URL, scope=BASE_URL,
                        traversal="Markdown links, reference links, and HTML href; reachable pages only",
                        raw_cache="content-addressed objects; legacy URL paths reused on resume and 304"),
                        index=self.index, index_history=self.index_history,
                        pages=self.pages, started_at=self.started_at, updated_at=_now(),
                        status="complete" if complete else "incomplete" if final else "running",
                        discovered=sorted(self.discovered), pending=pending, errors=errors,
                        status_counts={"ok": len(self.pages) - len(errors), "error": len(errors)},
                        counts=dict(discovered=len(self.discovered), pending=len(pending), errors=len(errors),
                                    requests=self.budget.requests, bytes_received=self.budget.bytes_received),
                        closure_complete=closure, fetch_complete=complete,
                        limit_reasons=sorted(self.limit_reasons))
        _atomic(self._path("web_manifest.json"), (json.dumps(manifest, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))
        return manifest

    def run(self, *, index_file=None, resume=False, refresh=False):
        if resume and refresh:
            raise ValueError("choose resume or refresh, not both")
        with _archive_lock(self.root):
            return self._run(index_file, resume, refresh)

    def _run(self, index_file, resume, refresh):
        old = {}
        manifest_path = self._path("web_manifest.json")
        if manifest_path.exists():
            if not (resume or refresh):
                raise ValueError("archive exists; choose --resume or --refresh")
            old = json.loads(manifest_path.read_text(encoding="utf-8"))
            if old.get("schema") != SCHEMA or not isinstance(old.get("pages"), dict):
                raise ValueError("unsupported web manifest")
        self.previous = old.get("pages", {})
        self.index_history = old.get("index_history", {})
        if not isinstance(self.index_history, dict):
            raise ValueError("unsupported index history")
        prior_index = old.get("index")
        try:
            cached_index = self._cached(prior_index)
            if cached_index is not None:
                # Preserve the index that supplied inferred build labels before
                # changing its readable alias. Checkpoint legacy migration first
                # so a crash cannot strand the previous manifest at the alias.
                captured = dict(prior_index)
                captured["path"] = "cache/web/objects/" + captured["sha256"] + ".txt"
                if self._cached(captured) is None:
                    _atomic(self._path(captured["path"]), cached_index)
                if captured["path"] != prior_index["path"]:
                    captured.update(migrated_from=prior_index["path"], archived_at=_now())
                self.index_history[captured["sha256"]] = captured
                if captured["path"] != prior_index["path"]:
                    migration = dict(old, index=captured, index_history=self.index_history)
                    _atomic(manifest_path, (json.dumps(migration, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))
                prior_index = captured
            if index_file is not None:
                with Path(index_file).open("rb") as stream:
                    raw = stream.read(self.max_page_bytes + 1)
                if len(raw) > self.max_page_bytes or not raw.decode("utf-8-sig").lstrip().startswith("#"):
                    raise FetchError("invalid or oversized supplied index")
                self.index = self._record(None, raw, {}, INDEX_URL)
                self.index.update(acquisition="supplied_file", fetched_at=None, ingested_at=_now())
            elif resume and cached_index is not None:
                raw, self.index = cached_index, dict(prior_index)
            else:
                raw, headers, url, unchanged = self._fetch(INDEX_URL, prior_index, cached_index)
                self.index = self._record(None, raw, headers, url, prior_index, unchanged)
                self.index["acquisition"] = "http"
            index_base = canonical_url(self.index.get("source_url", ""), index=True) or INDEX_URL
            queue = deque(discover_links(raw, index_base))
            if not queue:
                raise FetchError("index contains no scoped Markdown links")
            self.discovered.update(queue)
        except (FetchError, LimitReached, OSError, UnicodeError, ValueError) as error:
            self.limit_reasons.add("index_unavailable: " + str(error))
            return self._checkpoint(final=True)
        self._checkpoint()
        futures, submitted = {}, 0
        executor = ThreadPoolExecutor(max_workers=self.workers)
        last_checkpoint = time.monotonic()
        since_checkpoint = 0

        def accept(key, raw, source_url):
            for found in discover_links(raw, source_url):
                if found not in self.discovered:
                    self.discovered.add(found)
                    queue.append(found)
            self.processed.add(key)

        try:
            while queue or futures:
                while queue and len(futures) < self.workers and not self.limit_reasons:
                    key = queue.popleft()
                    prior = self.previous.get(key)
                    cached = self._cached(prior)
                    source = BASE_URL + quote(key, safe="/-._~")
                    if resume and cached is not None:
                        self.pages[key] = dict(prior)
                        accept(key, cached, canonical_url(prior.get("source_url", "")) or source)
                        since_checkpoint += 1
                        continue
                    if submitted >= self.max_pages:
                        queue.appendleft(key)
                        self.limit_reasons.add("max_pages")
                        break
                    futures[executor.submit(self._fetch, source, prior, cached)] = (key, prior)
                    submitted += 1
                if not futures:
                    break
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    key, prior = futures.pop(future)
                    try:
                        raw, headers, url, unchanged = future.result()
                        self.pages[key] = self._record(key, raw, headers, url, prior, unchanged)
                        accept(key, raw, url)
                    except LimitReached as error:
                        self.limit_reasons.add(str(error))
                    except (FetchError, OSError, UnicodeError, ValueError) as error:
                        self.pages[key] = dict(path=cache_relative(key, self.root), source_url=BASE_URL + quote(key, safe="/-._~"),
                                               sha256=None, docs_build=self.index.get("docs_build"),
                                               build_source="index_inferred" if self.index.get("docs_build") else "unknown",
                                               fetched_at=None, etag=None, last_modified=None, status="error", error=str(error))
                        self.processed.add(key)
                    since_checkpoint += 1
                if since_checkpoint >= self.checkpoint_every or time.monotonic() - last_checkpoint >= 5:
                    self._checkpoint()
                    since_checkpoint, last_checkpoint = 0, time.monotonic()
        except KeyboardInterrupt:
            self.limit_reasons.add("interrupted")
        finally:
            executor.shutdown(wait=True, cancel_futures=True)
            result = self._checkpoint(final=True)
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--index-file")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--resume", action="store_true", help="verify hashes and reuse intact cached pages")
    mode.add_argument("--refresh", action="store_true", help="conditionally revalidate every reachable page")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-pages", type=int, default=100000, help="maximum unique page requests scheduled this run")
    parser.add_argument("--max-requests", type=int, default=200000)
    parser.add_argument("--max-bytes", type=int, default=5 * 1024 ** 3)
    parser.add_argument("--max-page-bytes", type=int, default=8 * 1024 ** 2)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--checkpoint-every", type=int, default=100)
    args = vars(parser.parse_args(argv))
    run_args = {name: args.pop(name) for name in ("index_file", "resume", "refresh")}
    try:
        result = Downloader(**args).run(**run_args)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, str(error) + "\n")
    print(json.dumps({key: result[key] for key in ("status", "counts", "status_counts", "closure_complete", "fetch_complete", "limit_reasons")}, indent=2))
    return 0 if result["fetch_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
