"""NR-QC-TIMING staging (frozen rule r2 3.10 and 3.14). Run under the R4 venv.

Copies the 124 named EXRs into ``<stage-root>/<id>/<basename>``, one folder per id,
checks every copy by sha256 against its source and against the hashes on record,
confirms every copy's header with OpenImageIO against the packet's table, and
writes two files: a local manifest (absolute paths, stays outside the repo) and a
path-free summary that make_receipt.py folds into the receipt.

Placeholder bits (0x1000, 0x40000, 0x400000) are checked with ``os.stat`` right
before each copy. A source that carries one is skipped and reported; nothing opens
it, so the file is never hydrated. Sources are opened read-only and nothing is
written beside a source.

Exit codes: 0 staged and verified, 1 anything skipped, mismatched or not 124 files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence

RULE_SHA256 = "7d4c3bfecfe3adefb8db30b4455eca3266d9cbb5089d54986153489578a4e282"
PLACEHOLDER_BITS = 0x1000 | 0x40000 | 0x400000
EXPECTED_FILES = 124
#: first-file hashes of 3.1 come from the rule's own entries; these two are 3.11's.
CHAR3_ON_RECORD = {
    "0031": "35ae6eace7f46a1c238b247ece2103d07405564bbac134f57b44d42230688d4e",
    "0061": "7422ce05711c97379e7bd64362f434ef338df7a2837cb75bde60e5a92533c193",
}
#: Packet section 2 table. channels = all parts summed; display = full window.
HEADERS = {
    "char-8": dict(w=3840, h=2880, ch=4, parts=1, comp="zips", fmt="half"),
    "sib-v016": dict(w=3840, h=2880, ch=4, parts=1, comp="zips", fmt="half"),
    "sib-v017": dict(w=3840, h=2880, ch=4, parts=1, comp="zips", fmt="half"),
    "char-9": dict(w=4096, h=1716, ch=80, parts=24, comp="zips", fmt="half"),
    "char-2": dict(w=2048, h=858, ch=102, parts=31, comp="zips", fmt="half"),
    "char-3": dict(w=1280, h=536, ch=13, parts=4, comp="zips", fmt="half"),
    "char-4": dict(w=1280, h=536, ch=13, parts=4, comp="zips", fmt="half"),
    "char-10": dict(w=504, h=216, x=588, y=468, fw=1680, fh=720, ch=4, parts=1, comp="zips", fmt="half"),
    "char-13": dict(w=3840, h=1608, ch=4, parts=1, comp="piz", fmt="half"),
    "char-12": dict(w=3840, h=2160, ch=4, parts=1, comp="none", fmt="half"),
}


def extract_rule_entries(text: str) -> List[Dict[str, Any]]:
    """The ``entries`` list of the rule's machine-readable block (3.14)."""
    blocks = re.findall(r"```json\n(.*?)\n```", text, re.S)
    for b in blocks:
        try:
            doc = json.loads(b)
        except ValueError:
            continue
        if isinstance(doc, dict) and "entries" in doc:
            return list(doc["entries"])
    raise ValueError("no machine-readable block with entries in the rule")


def expand_entry(entry: Dict[str, Any]) -> List[Dict[str, str]]:
    """``####`` expanded to the entry's frame range; a single stays one file."""
    path, frames = str(entry["path"]), str(entry["frames"])
    if frames == "single":
        out = [{"frame": "single", "path": path}]
    else:
        lo, hi = frames.split("-")
        width = len(lo)
        if "####" not in path:
            raise ValueError(f"{entry['id']}: range without #### in the path")
        out = [{"frame": f"{n:0{width}d}", "path": path.replace("####", f"{n:0{width}d}")}
               for n in range(int(lo), int(hi) + 1)]
    if len(out) != int(entry["files"]):
        raise ValueError(f"{entry['id']}: {len(out)} frames expand, rule says {entry['files']}")
    return out


def placeholder_bits(attrs: int) -> int:
    return attrs & PLACEHOLDER_BITS


def parse_checksums(text: str) -> Dict[str, str]:
    """``<sha256>  <path>`` lines (``*`` marks binary mode) -> {basename: sha256}."""
    out: Dict[str, str] = {}
    for line in text.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            out[os.path.basename(parts[1].lstrip("*").replace("\\", "/"))] = parts[0].lower()
    return out


def stage_one(src: str, dst: str, stat_fn: Callable[[str], int] = lambda p: os.stat(p).st_file_attributes
              ) -> Dict[str, Any]:
    """Check the attributes first; copy and hash only when no placeholder bit is set.

    Returns ``{"skipped": True, "attributes": n, "bits": b}`` without opening ``src``
    when a bit is set. Otherwise the source is read once (hashing while it copies)
    and the copy is hashed after.
    """
    attrs = stat_fn(src)
    bits = placeholder_bits(attrs)
    if bits:
        return {"skipped": True, "attributes": attrs, "bits": bits}
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    h = hashlib.sha256()
    size = 0
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        while True:
            chunk = fi.read(8 << 20)
            if not chunk:
                break
            h.update(chunk)
            fo.write(chunk)
            size += len(chunk)
    h2 = hashlib.sha256()
    with open(dst, "rb") as fh:
        for chunk in iter(lambda: fh.read(8 << 20), b""):
            h2.update(chunk)
    return {"skipped": False, "attributes": attrs, "bytes": size,
            "source_sha256": h.hexdigest(), "copy_sha256": h2.hexdigest()}


def read_header(path: str) -> Dict[str, Any]:
    """Header facts of a copy through OpenImageIO (headers only, no pixels)."""
    import OpenImageIO as oiio
    inp = oiio.ImageInput.open(path)
    if inp is None:
        raise ValueError(f"OpenImageIO cannot open the copy: {oiio.geterror()}")
    try:
        spec0 = inp.spec()
        parts, channels, i = 0, 0, 0
        while True:
            parts += 1
            channels += int(inp.spec().nchannels)
            i += 1
            if not inp.seek_subimage(i, 0):
                break
        rt = spec0.getattribute("renderTime")
        try:
            rt = float(rt) if rt is not None else None
        except (TypeError, ValueError):
            rt = None
        return {"w": int(spec0.width), "h": int(spec0.height), "x": int(spec0.x), "y": int(spec0.y),
                "fx": int(spec0.full_x), "fy": int(spec0.full_y), "fw": int(spec0.full_width),
                "fh": int(spec0.full_height), "ch": channels, "parts": parts,
                "comp": str(spec0.getattribute("compression") or "").split(":")[0],
                "fmt": str(spec0.format), "render_time_s": rt}
    finally:
        inp.close()


def header_problems(eid: str, hdr: Dict[str, Any]) -> List[str]:
    want = HEADERS[eid]
    bad = []
    for k in ("w", "h", "ch", "parts", "comp", "fmt"):
        if hdr[k] != want[k]:
            bad.append(f"{k}: {hdr[k]!r} != {want[k]!r}")
    fw, fh = want.get("fw", want["w"]), want.get("fh", want["h"])
    if (hdr["fw"], hdr["fh"], hdr["fx"], hdr["fy"]) != (fw, fh, 0, 0):
        bad.append("display window differs")
    if (hdr["x"], hdr["y"]) != (want.get("x", 0), want.get("y", 0)):
        bad.append("data window origin differs")
    return bad


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--rule", required=True, help="QC-TIMING-FROZEN-RULE.r2.md")
    p.add_argument("--stage-root", required=True)
    p.add_argument("--manifest", required=True, help="local manifest to write (absolute paths)")
    p.add_argument("--summary", required=True, help="path-free summary to write")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    a = build_parser().parse_args(argv)
    with open(a.rule, "rb") as fh:
        raw = fh.read()
    if hashlib.sha256(raw).hexdigest() != RULE_SHA256:
        print("REFUSED: the rule file is not revision 2 (sha256 differs)", file=sys.stderr)
        return 1
    entries = extract_rule_entries(raw.decode("utf-8"))
    problems: List[str] = []
    skipped: List[Dict[str, Any]] = []
    files: List[Dict[str, Any]] = []
    checksums: Dict[str, str] = {}
    for e in entries:
        if e["id"] == "char-2":
            # the delivery folder that holds the exr/ folder
            ck = os.path.join(os.path.dirname(os.path.dirname(expand_entry(e)[0]["path"])), "CHECKSUMS.sha256")
            with open(ck, encoding="utf-8") as fh:
                checksums = parse_checksums(fh.read())
    for e in entries:
        for f in expand_entry(e):
            name = os.path.basename(f["path"])
            if not name.lower().endswith(".exr"):
                problems.append(f"{e['id']} {f['frame']}: not an EXR")
                continue
            dst = os.path.join(a.stage_root, e["id"], name)
            r = stage_one(f["path"], dst)
            if r["skipped"]:
                skipped.append({"id": e["id"], "frame": f["frame"], "attributes": r["attributes"]})
                continue
            rec = {"id": e["id"], "frame": f["frame"], "name": name, "bytes": r["bytes"],
                   "source_sha256": r["source_sha256"], "copy_sha256": r["copy_sha256"],
                   "source_attributes": r["attributes"], "source_path": f["path"], "staged_path": dst}
            if r["source_sha256"] != r["copy_sha256"]:
                problems.append(f"{e['id']} {f['frame']}: copy hash differs from source")
            if e["id"] == "char-2":
                rec["checksums_sha256"] = checksums.get(name)
                if checksums.get(name) != r["copy_sha256"]:
                    problems.append(f"{e['id']} {f['frame']}: differs from CHECKSUMS.sha256")
            first = expand_entry(e)[0]["frame"]
            if f["frame"] == first and r["copy_sha256"] != e["sha256_first_file"]:
                problems.append(f"{e['id']} {f['frame']}: differs from the first-file hash on record")
            if e["id"] == "char-3" and CHAR3_ON_RECORD.get(f["frame"]) not in (None, r["copy_sha256"]):
                problems.append(f"char-3 {f['frame']}: differs from the hash on record")
            try:
                hdr = read_header(dst)
                rec["render_time_s"] = hdr["render_time_s"]
                problems.extend(f"{e['id']} {f['frame']}: header {x}" for x in header_problems(e["id"], hdr))
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{e['id']} {f['frame']}: header unreadable: {type(exc).__name__}")
            files.append(rec)
    distinct = len({(x["id"], x["frame"]) for x in files})
    if distinct != EXPECTED_FILES:
        problems.append(f"{distinct} distinct files staged, need {EXPECTED_FILES}")
    with open(a.manifest, "w", encoding="utf-8") as fh:
        json.dump({"files": files, "skipped": skipped, "problems": problems}, fh, indent=1)
    keep = ("id", "frame", "name", "bytes", "source_sha256", "copy_sha256", "source_attributes",
            "checksums_sha256", "render_time_s")
    with open(a.summary, "w", encoding="utf-8") as fh:
        json.dump({"distinct_files": distinct, "skipped": len(skipped), "problems": len(problems),
                   "files": [{k: x[k] for k in keep if k in x} for x in files]}, fh, indent=1, sort_keys=True)
    for p in problems + [f"skipped {s['id']} {s['frame']} (attributes {s['attributes']:#x})" for s in skipped]:
        print(p, file=sys.stderr)
    print(f"staged {distinct} distinct files; {len(skipped)} skipped; {len(problems)} problems")
    return 0 if distinct == EXPECTED_FILES and not skipped and not problems else 1


if __name__ == "__main__":
    sys.exit(main())
