"""Conservative filesystem ownership and recoverable registration transactions."""
from __future__ import annotations
import base64
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import uuid


class SetupError(RuntimeError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    return digest(Path(path).read_bytes()) if Path(path).is_file() else None


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def no_links(path):
    """Reject junctions/symlinks before resolving; never follow them on removal."""
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise SetupError(f"Linked/junction destinations are not supported: {item}. Choose a real folder.")
    return path


def inside(path, root):
    path, root = no_links(path), no_links(root)
    if not path.is_relative_to(root) or path == root:
        raise SetupError(f"Unsafe destination outside the expected folder: {path}")
    return path


def member_path(root, name):
    rel = PurePosixPath(name)
    if (not name or name != rel.as_posix() or "\\" in name or ":" in name or rel.is_absolute()
            or any(p in {"..", "."} or p.endswith((".", " ")) for p in rel.parts)):
        raise SetupError(f"Unsafe payload path: {name}")
    if any(p.split(".")[0].upper() in {"CON", "NUL", "PRN", "AUX", *("COM" + str(i) for i in range(1, 10)), *("LPT" + str(i) for i in range(1, 10))} for p in rel.parts):
        raise SetupError(f"Reserved Windows payload path: {name}")
    return inside(Path(root).joinpath(*rel.parts), root)


def atomic_write(path, data):
    path = no_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".synapse-" + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def read_json(path, default=None):
    if not Path(path).exists():
        return default
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise SetupError(f"Cannot read installation metadata: {path}: {exc}") from exc


def encode(data):
    return None if data is None else base64.b64encode(data).decode("ascii")


def decode(data):
    return None if data is None else base64.b64decode(data, validate=True)


def current(path):
    path = no_links(path)
    if path.exists() and not path.is_file():
        raise SetupError(f"A file destination is occupied by a directory: {path}")
    return path.read_bytes() if path.exists() else None


def change(path, after):
    return {"path": str(no_links(path)), "before": encode(current(path)), "after": encode(after)}


def apply_value(path, value):
    if value is None:
        no_links(path).unlink(missing_ok=True)
    else:
        atomic_write(path, value)


def recover(journal, *, keep_journal=False):
    data = read_json(journal)
    if not data:
        return False
    if data.get("schema") != "synapse-transaction-1":
        raise SetupError(f"Unrecognized recovery journal: {journal}")
    if data.get("committed"):
        if not keep_journal:
            Path(journal).unlink()
        return False
    for op in reversed(data["changes"]):
        present = current(op["path"])
        before, after = decode(op["before"]), decode(op["after"])
        if present == before:
            continue
        if present != after:
            raise SetupError(f"Recovery stopped to preserve an externally changed file: {op['path']}. Keep {journal} for diagnosis.")
        apply_value(op["path"], before)
    if not keep_journal:
        Path(journal).unlink()
    return True


def transact(journal, changes):
    if Path(journal).exists():
        raise SetupError(f"Unresolved recovery journal: {journal}")
    record = {"schema": "synapse-transaction-1", "committed": False, "changes": changes}
    atomic_write(journal, json_bytes(record))
    try:
        for op in changes:
            if current(op["path"]) != decode(op["before"]):
                raise SetupError(f"A file changed while setup was running: {op['path']}. No user changes will be overwritten.")
            apply_value(op["path"], decode(op["after"]))
        record["committed"] = True
        atomic_write(journal, json_bytes(record))
    except Exception:
        recover(journal)
        raise
    Path(journal).unlink()


@contextmanager
def maintenance_lock(app):
    app = no_links(app)
    app.mkdir(parents=True, exist_ok=True)
    path = app / ".maintenance.lock"
    no_links(path)
    stream = path.open("a+b")
    try:
        stream.seek(0)
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
            raise SetupError("Another SYNAPSE setup or uninstall is running. Let it finish, then try again.") from exc
        yield
    finally:
        stream.close()
        # Keep the zero-byte authority file: unlinking a lock introduces races.


def check_writable(path):
    path = no_links(path)
    parent = path
    while not parent.exists():
        parent = parent.parent
    if not parent.is_dir():
        raise SetupError(f"Destination parent is a file: {parent}")
    probe = parent / (".synapse-write-check-" + uuid.uuid4().hex)
    try:
        with probe.open("xb") as stream:
            stream.write(b"SYNAPSE setup write check")
        probe.unlink()
    except OSError as exc:
        raise SetupError(f"Cannot write to {parent}. Choose a writable per-user folder. {exc}") from exc
